"""Text and date normalization shared by all sources (CLAUDE.md §6.3 step 1)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

_WHITESPACE = re.compile(r"\s+")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean_text(value: str | None) -> str:
    """Strip HTML tags, decode entities, and collapse whitespace."""
    if not value:
        return ""
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    return _WHITESPACE.sub(" ", "".join(parser.parts)).strip()


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_iso_utc(value: str) -> datetime:
    """Parse ISO 8601 (e.g. the Guardian's '2026-11-24T19:02:11Z') to aware UTC."""
    return _to_utc(datetime.fromisoformat(value.strip().replace("Z", "+00:00")))


def parse_rfc822_utc(value: str) -> datetime:
    """Parse an RSS pubDate (e.g. 'Tue, 24 Nov 2026 16:49:52 +0100') to aware UTC."""
    return _to_utc(parsedate_to_datetime(value.strip()))
