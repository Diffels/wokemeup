from datetime import datetime, timezone

from pipeline.normalize import clean_text, parse_iso_utc, parse_rfc822_utc


def test_clean_text_strips_tags_entities_and_whitespace() -> None:
    raw = "<p>Les chefs &laquo;&nbsp;restent\n  prudents&nbsp;&raquo; &amp; <b>calmes</b></p>"
    assert clean_text(raw) == "Les chefs « restent prudents » & calmes"
    assert clean_text(None) == ""


def test_dates_parse_to_aware_utc() -> None:
    expected = datetime(2026, 11, 24, 15, 49, 52, tzinfo=timezone.utc)
    assert parse_rfc822_utc("Tue, 24 Nov 2026 16:49:52 +0100") == expected
    assert parse_iso_utc("2026-11-24T15:49:52Z") == expected
