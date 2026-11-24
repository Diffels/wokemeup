"""Load non-secret configuration from config/."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from pipeline.models import TOPIC_ORDER

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"


@dataclass
class Config:
    sources: dict[str, Any]
    topics: list[dict[str, Any]]
    wake: dict[str, Any]

    @property
    def timezone(self) -> str:
        return str(self.sources["briefing"]["timezone"])

    @property
    def max_items_per_topic(self) -> int:
        return int(self.sources["briefing"]["max_items_per_topic"])


def load_config(config_dir: Path = CONFIG_DIR) -> Config:
    sources = yaml.safe_load((config_dir / "sources.yaml").read_text(encoding="utf-8"))
    topics = yaml.safe_load((config_dir / "topics.yaml").read_text(encoding="utf-8"))["topics"]
    wake = json.loads((config_dir / "wake.json").read_text(encoding="utf-8"))

    ids = tuple(t["id"] for t in topics)
    if ids != TOPIC_ORDER:
        raise ValueError(f"config/topics.yaml topic ids must be {TOPIC_ORDER}, got {ids}")

    return Config(sources=sources, topics=topics, wake=wake)


def load_dotenv(path: Path = REPO_ROOT / ".env") -> None:
    """Load KEY=VALUE lines from a local .env (gitignored) without overriding the environment."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ.setdefault(key.strip(), value)
