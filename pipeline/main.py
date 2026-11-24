"""CLI entry point. Keep this thin: logic lives in the modules.

Usage:
    python -m pipeline.main --dry-run   # fetch sources and print items, write nothing
    python -m pipeline.main             # build and write docs/briefing.json
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline.config import REPO_ROOT, Config, load_config, load_dotenv
from pipeline.http import HttpClient
from pipeline.models import Briefing, Topic
from pipeline.publish import write_briefing
from pipeline.sources import SourceResult, fetch_all

log = logging.getLogger("pipeline")


def build_briefing(now: datetime) -> Briefing:
    """Topics stay empty until summaries exist (M3): raw items are never published."""
    config = load_config()
    local_date = now.astimezone(ZoneInfo(config.timezone)).date()
    topics = [Topic(id=t["id"], title=t["title"]) for t in config.topics]
    return Briefing(
        date=local_date,
        generated_at=now,
        timezone=config.timezone,
        status="ok",
        audio_url=None,
        topics=topics,
    )


def make_http(config: Config) -> HttpClient:
    settings = config.sources["http"]
    return HttpClient(
        cache_dir=REPO_ROOT / ".cache" / "http",
        cache_ttl_s=float(settings["cache_ttl_minutes"]) * 60,
        retries=int(settings["retries"]),
        timeout_s=float(settings["timeout_seconds"]),
    )


def format_results(results: list[SourceResult]) -> str:
    lines: list[str] = []
    for result in results:
        if result.error:
            lines.append(f"== {result.name}: FAILED ({result.error})")
            continue
        lines.append(f"== {result.name}: {len(result.items)} items")
        for item in sorted(result.items, key=lambda i: i.published_at, reverse=True):
            when = item.published_at.strftime("%Y-%m-%d %H:%MZ")
            lines.append(f"{when}  {item.section:<14} {item.title}")
            lines.append(f"{'':33}{item.url}")
    return "\n".join(lines) + "\n"


def dry_run(now: datetime) -> int:
    config = load_config()
    results = fetch_all(config, now, make_http(config))
    sys.stdout.write(format_results(results))
    return 1 if all(r.error for r in results) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline.main", description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="fetch and print items, write nothing")
    parser.add_argument("--docs-dir", type=Path, default=REPO_ROOT / "docs")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv()

    now = datetime.now(timezone.utc)
    if args.dry_run:
        return dry_run(now)
    write_briefing(build_briefing(now), args.docs_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
