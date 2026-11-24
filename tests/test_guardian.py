import json
from datetime import datetime, timezone

import pytest

from pipeline.config import load_config
from pipeline.http import FetchError
from pipeline.sources import guardian
from tests.conftest import FakeHttp, fixture_bytes

NOW = datetime(2026, 11, 25, 5, 0, tzinfo=timezone.utc)


def test_parse_search_normalizes_and_skips_unsupported_types() -> None:
    items, pages = guardian.parse_search(json.loads(fixture_bytes("guardian_search_page1.json")))
    assert pages == 2
    assert [i.section for i in items] == ["world", "business"]  # interactive skipped
    first = items[0]
    assert first.outlet == "The Guardian"
    assert first.summary == "Delegations from both sides met for a second day & agreed on a timetable"
    assert first.published_at == datetime(2026, 11, 24, 19, 2, 11, tzinfo=timezone.utc)
    assert items[1].title == "Example energy prices – live"  # falls back to webTitle


def test_parse_search_rejects_error_status() -> None:
    with pytest.raises(FetchError):
        guardian.parse_search({"response": {"status": "error", "message": "bad"}})


def test_fetch_pages_through_results_with_expected_params() -> None:
    config = load_config()
    endpoint = config.sources["guardian"]["endpoint"]
    http = FakeHttp({endpoint: [fixture_bytes("guardian_search_page1.json"), fixture_bytes("guardian_search_page2.json")]})

    items = guardian.fetch(config, "secret-key", NOW, http)

    assert len(items) == 3
    assert [c[1]["page"] for c in http.calls] == ["1", "2"]
    params = http.calls[0][1]
    assert params["api-key"] == "secret-key"
    assert params["section"] == "world|business|environment|technology"
    assert params["from-date"] == "2026-11-24T05:00:00Z"
    assert "bodyText" not in params["show-fields"]


def test_fetch_stops_at_max_pages() -> None:
    config = load_config()
    config.sources["guardian"]["max_pages"] = 1
    endpoint = config.sources["guardian"]["endpoint"]
    http = FakeHttp({endpoint: [fixture_bytes("guardian_search_page1.json")]})
    assert len(guardian.fetch(config, "k", NOW, http)) == 2
    assert len(http.calls) == 1


def test_fetch_wraps_invalid_json() -> None:
    config = load_config()
    http = FakeHttp({config.sources["guardian"]["endpoint"]: b"<html>oops</html>"})
    with pytest.raises(FetchError):
        guardian.fetch(config, "k", NOW, http)
