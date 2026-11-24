"""Dataclasses for news items and the published briefing (CLAUDE.md §5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Literal

SCHEMA_VERSION = 1
TOPIC_ORDER: tuple[str, ...] = ("geopolitique", "energie", "numerique", "bonne-nouvelle")

Status = Literal["ok", "fallback"]


def _iso_utc(value: datetime) -> str:
    """Format a datetime as ISO 8601 UTC with a trailing 'Z'."""
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class NewsItem:
    """A normalized item from any source, before summarization."""

    title: str
    summary: str
    url: str
    outlet: str
    published_at: datetime
    section: str = ""
    extra_outlets: list[str] = field(default_factory=list)


@dataclass
class BriefingItem:
    """A summarized story as published in briefing.json."""

    title_fr: str
    summary_fr: str
    outlet: str
    published_at: datetime
    source_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "title_fr": self.title_fr,
            "summary_fr": self.summary_fr,
            "outlet": self.outlet,
            "published_at": _iso_utc(self.published_at),
            "source_url": self.source_url,
        }


@dataclass
class Topic:
    id: str
    title: str
    items: list[BriefingItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "items": [i.to_dict() for i in self.items]}


@dataclass
class Briefing:
    date: date
    generated_at: datetime
    timezone: str
    status: Status
    audio_url: str | None
    topics: list[Topic]

    def to_dict(self) -> dict[str, Any]:
        order = {topic_id: i for i, topic_id in enumerate(TOPIC_ORDER)}
        topics = sorted(self.topics, key=lambda t: order.get(t.id, len(order)))
        return {
            "schema_version": SCHEMA_VERSION,
            "date": self.date.isoformat(),
            "generated_at": _iso_utc(self.generated_at),
            "timezone": self.timezone,
            "status": self.status,
            "audio_url": self.audio_url,
            "topics": [t.to_dict() for t in topics],
        }
