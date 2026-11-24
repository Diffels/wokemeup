import pytest

from pipeline.config import load_config
from pipeline.http import FetchError
from pipeline.sources import lemonde_rss
from tests.conftest import FakeHttp, fixture_bytes

UNE = "https://www.lemonde.fr/rss/une.xml"
INTERNATIONAL = "https://www.lemonde.fr/international/rss_full.xml"


def _config(feeds: list[dict]):
    config = load_config()
    config.sources["lemonde"]["feeds"] = feeds
    return config


def test_parse_feed_normalizes_and_skips_items_without_date() -> None:
    items = lemonde_rss.parse_feed(fixture_bytes("lemonde_une.xml"), "une")
    assert len(items) == 2
    assert items[0].title == "Exemple : un sommet sur le climat s’ouvre à Bruxelles"
    assert items[1].summary == "Les chefs de la diplomatie « restent prudents »."
    assert items[0].published_at.isoformat() == "2026-11-24T19:15:00+00:00"
    assert all(i.outlet == "Le Monde" and i.section == "une" for i in items)


def test_parse_feed_rejects_invalid_xml() -> None:
    with pytest.raises(FetchError):
        lemonde_rss.parse_feed(b"<rss><channel>", "une")


def test_fetch_merges_feeds_and_prefers_specific_section() -> None:
    config = _config([
        {"url": UNE, "section": "une", "verified": True},
        {"url": INTERNATIONAL, "section": "international", "verified": True},
        {"url": "https://example.invalid/unverified.xml", "section": "x", "verified": False},
    ])
    http = FakeHttp({UNE: fixture_bytes("lemonde_une.xml"), INTERNATIONAL: fixture_bytes("lemonde_international.xml")})

    items = lemonde_rss.fetch(config, http)

    assert len(http.calls) == 2  # unverified feed never requested
    by_title = {i.title: i.section for i in items}
    assert len(items) == 3
    assert by_title["Exemple : la diplomatie européenne face à une nouvelle crise"] == "international"


def test_fetch_survives_one_failing_feed_but_not_all() -> None:
    feeds = [
        {"url": UNE, "section": "une", "verified": True},
        {"url": INTERNATIONAL, "section": "international", "verified": True},
    ]
    http = FakeHttp({UNE: FetchError("down"), INTERNATIONAL: fixture_bytes("lemonde_international.xml")})
    assert len(lemonde_rss.fetch(_config(feeds), http)) == 2

    http = FakeHttp({UNE: FetchError("down"), INTERNATIONAL: FetchError("down")})
    with pytest.raises(FetchError):
        lemonde_rss.fetch(_config(feeds), http)
