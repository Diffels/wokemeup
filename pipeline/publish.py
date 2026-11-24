"""Write pipeline output to docs/ (GitHub Pages root)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from pipeline.models import Briefing

log = logging.getLogger(__name__)


def briefing_json(briefing: Briefing) -> str:
    return json.dumps(briefing.to_dict(), ensure_ascii=False, indent=2) + "\n"


def write_briefing(briefing: Briefing, docs_dir: Path) -> Path:
    """Write docs/briefing.json atomically, so a crash never leaves a partial file."""
    docs_dir.mkdir(parents=True, exist_ok=True)
    target = docs_dir / "briefing.json"
    fd, tmp = tempfile.mkstemp(dir=docs_dir, prefix=".briefing-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(briefing_json(briefing))
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    log.info("Wrote %s", target)
    return target
