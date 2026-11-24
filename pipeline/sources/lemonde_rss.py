"""Le Monde RSS source (CLAUDE.md §6.2).

Uses only title, description, link, and pubDate. Article pages are never fetched.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from pipeline.config import Config
from pipeline.http import FetchError, HttpClient
from pipeline.models import NewsItem
from pipeline.normalize import clean_text, parse_rfc822_utc

log = logging.getLogger(__name__)

OUTLET = "Le Monde"
GENERIC_SECTION = "une"  # the front-page feed mixes all sections


def parse_feed(data: bytes, section: str) -> list[NewsItem]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise FetchError(f"Le Monde feed {section!r} is not valid XML: {e}") from None

    items: list[NewsItem] = []
    for node in root.iterfind("./channel/item"):
        title = clean_text(node.findtext("title"))
        url = (node.findtext("link") or node.findtext("guid") or "").strip()
        published = node.findtext("pubDate")
        if not (title and url and published):
            log.debug("Skipping incomplete Le Monde item in %s", section)
            continue
        try:
            published_at = parse_rfc822_utc(published)
        except (TypeError, ValueError):
            log.debug("Skipping Le Monde item with bad date %r", published)
            continue
        items.append(
            NewsItem(
                title=title,
                summary=clean_text(node.findtext("description")),
                url=url,
                outlet=OUTLET,
                published_at=published_at,
                section=section,
            )
        )
    return items


def fetch(config: Config, http: HttpClient) -> list[NewsItem]:
    """Fetch every verified feed. The same article often appears in several feeds:
    keep one copy, preferring a specific section over the front page."""
    feeds = [f for f in config.sources["lemonde"]["feeds"] if f.get("verified")]
    by_url: dict[str, NewsItem] = {}
    failures: list[str] = []
    for feed in feeds:
        try:
            feed_items = parse_feed(http.get(feed["url"]), feed["section"])
        except FetchError as e:
            log.warning("%s", e)
            failures.append(feed["section"])
            continue
        for item in feed_items:
            existing = by_url.get(item.url)
            if existing is None or (existing.section == GENERIC_SECTION and item.section != GENERIC_SECTION):
                by_url[item.url] = item

    if feeds and len(failures) == len(feeds):
        raise FetchError(f"All Le Monde feeds failed: {', '.join(failures)}")
    log.info("Le Monde: %d items from %d feed(s)", len(by_url), len(feeds) - len(failures))
    return list(by_url.values())
