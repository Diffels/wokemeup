"""The Guardian Content API source (CLAUDE.md §6.1).

Fetches headline and trail text only. `bodyText` is never requested here.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from pipeline.config import Config
from pipeline.http import FetchError, HttpClient
from pipeline.models import NewsItem
from pipeline.normalize import clean_text, parse_iso_utc

log = logging.getLogger(__name__)

OUTLET = "The Guardian"
KEPT_TYPES = frozenset({"article", "liveblog"})


def sections_from_topics(topics: list[dict[str, Any]]) -> list[str]:
    """Union of the Guardian sections named in config/topics.yaml, in topic order."""
    sections: list[str] = []
    for topic in topics:
        for section in topic.get("guardian", {}).get("sections", []):
            if section not in sections:
                sections.append(section)
    return sections


def parse_search(payload: dict[str, Any]) -> tuple[list[NewsItem], int]:
    """Return the normalized items of one search page and the total page count."""
    response = payload.get("response") or {}
    if response.get("status") != "ok":
        raise FetchError(f"Guardian response status is {response.get('status')!r}")

    items: list[NewsItem] = []
    for result in response.get("results", []):
        if result.get("type") not in KEPT_TYPES:
            continue
        fields = result.get("fields") or {}
        title = clean_text(fields.get("headline") or result.get("webTitle"))
        url = (result.get("webUrl") or "").strip()
        published = result.get("webPublicationDate")
        if not (title and url and published):
            log.debug("Skipping incomplete Guardian result %s", result.get("id"))
            continue
        items.append(
            NewsItem(
                title=title,
                summary=clean_text(fields.get("trailText")),
                url=url,
                outlet=OUTLET,
                published_at=parse_iso_utc(published),
                section=str(result.get("sectionId", "")),
            )
        )
    return items, int(response.get("pages") or 1)


def fetch(config: Config, api_key: str, now: datetime, http: HttpClient) -> list[NewsItem]:
    settings = config.sources["guardian"]
    since = now - timedelta(hours=int(config.sources["briefing"]["max_age_hours"]))
    params = {
        "api-key": api_key,
        "section": "|".join(sections_from_topics(config.topics)),
        "from-date": since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "order-by": "newest",
        "page-size": str(settings["page_size"]),
        "show-fields": str(settings["show_fields"]),
    }

    items: list[NewsItem] = []
    page, pages = 1, 1
    while page <= min(pages, int(settings["max_pages"])):
        body = http.get(settings["endpoint"], {**params, "page": str(page)})
        try:
            page_items, pages = parse_search(json.loads(body))
        except (ValueError, KeyError, TypeError) as e:
            raise FetchError(f"Guardian page {page} is not valid search JSON: {e}") from None
        items.extend(page_items)
        page += 1
    log.info("Guardian: %d items from %d page(s)", len(items), page - 1)
    return items
