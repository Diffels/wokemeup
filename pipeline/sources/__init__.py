"""News sources. Each module exposes one `fetch` returning normalized items (CLAUDE.md §12)."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from pipeline.config import Config
from pipeline.http import FetchError, HttpClient
from pipeline.models import NewsItem
from pipeline.sources import guardian, lemonde_rss

log = logging.getLogger(__name__)


@dataclass
class SourceResult:
    name: str
    items: list[NewsItem] = field(default_factory=list)
    error: str | None = None


def fetch_all(
    config: Config, now: datetime, http: HttpClient, env: Mapping[str, str] = os.environ
) -> list[SourceResult]:
    """Fetch every source. One failing source does not stop the others."""
    results: list[SourceResult] = []

    key_env = config.sources["guardian"]["api_key_env"]
    api_key = env.get(key_env, "").strip()
    if not api_key:
        results.append(SourceResult(guardian.OUTLET, error=f"{key_env} is not set"))
    else:
        try:
            results.append(SourceResult(guardian.OUTLET, guardian.fetch(config, api_key, now, http)))
        except FetchError as e:
            results.append(SourceResult(guardian.OUTLET, error=str(e)))

    try:
        results.append(SourceResult(lemonde_rss.OUTLET, lemonde_rss.fetch(config, http)))
    except FetchError as e:
        results.append(SourceResult(lemonde_rss.OUTLET, error=str(e)))

    for result in results:
        if result.error:
            log.error("%s: %s", result.name, result.error)
    return results
