"""CLI entry point. Keep this thin: logic lives in the modules.

Usage:
    python -m pipeline.main --dry-run   # build and print, write nothing
    python -m pipeline.main             # build and write docs/briefing.json
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline.config import REPO_ROOT, load_config
from pipeline.models import Briefing, Topic
from pipeline.publish import briefing_json, write_briefing

log = logging.getLogger("pipeline")


def build_briefing(now: datetime) -> Briefing:
    """M0: an empty briefing with every topic present. Sources arrive in M1."""
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline.main", description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print the briefing, write nothing")
    parser.add_argument("--docs-dir", type=Path, default=REPO_ROOT / "docs")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    briefing = build_briefing(datetime.now(timezone.utc))
    if args.dry_run:
        sys.stdout.write(briefing_json(briefing))
    else:
        write_briefing(briefing, args.docs_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
