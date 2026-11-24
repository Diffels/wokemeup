from datetime import datetime, timezone

from pipeline.config import load_config
from pipeline.http import FetchError
from pipeline.sources import fetch_all
from tests.conftest import FakeHttp, fixture_bytes

NOW = datetime(2026, 11, 25, 5, 0, tzinfo=timezone.utc)


def test_missing_guardian_key_does_not_stop_le_monde() -> None:
    config = load_config()
    config.sources["lemonde"]["feeds"] = [
        {"url": "https://www.lemonde.fr/rss/une.xml", "section": "une", "verified": True}
    ]
    http = FakeHttp({"https://www.lemonde.fr/rss/une.xml": fixture_bytes("lemonde_une.xml")})

    guardian_result, lemonde_result = fetch_all(config, NOW, http, env={})

    assert guardian_result.error == "GUARDIAN_API_KEY is not set"
    assert lemonde_result.error is None and len(lemonde_result.items) == 2


def test_guardian_failure_is_reported_not_raised() -> None:
    config = load_config()
    config.sources["lemonde"]["feeds"] = []
    http = FakeHttp({config.sources["guardian"]["endpoint"]: FetchError("HTTP 401")})
    guardian_result, _ = fetch_all(config, NOW, http, env={"GUARDIAN_API_KEY": "k"})
    assert guardian_result.error == "HTTP 401"
