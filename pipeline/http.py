"""Minimal HTTP GET with a response cache and backoff (CLAUDE.md §6.1).

Secrets passed as query parameters are never logged, cached by name, or put in
error messages: every user-visible URL goes through `redact`.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

log = logging.getLogger(__name__)

USER_AGENT = "wokemeup-briefing/0.1 (personal, non-commercial)"
SECRET_PARAMS = frozenset({"api-key"})
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_RETRY_AFTER_S = 60.0

Opener = Callable[[Request, float], bytes]


class FetchError(RuntimeError):
    """A source could not be fetched or parsed. The message never contains secrets."""


def _default_opener(request: Request, timeout: float) -> bytes:
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 (https URLs from config)
        return response.read()


def redact(url: str, params: dict[str, str]) -> str:
    safe = {k: ("***" if k in SECRET_PARAMS else v) for k, v in params.items()}
    return f"{url}?{urlencode(safe)}" if safe else url


def _retry_after(error: HTTPError) -> float | None:
    value = error.headers.get("Retry-After") if error.headers else None
    try:
        return min(float(value), MAX_RETRY_AFTER_S) if value is not None else None
    except ValueError:
        return None


class HttpClient:
    def __init__(
        self,
        cache_dir: Path | None = None,
        cache_ttl_s: float = 1800.0,
        retries: int = 3,
        timeout_s: float = 20.0,
        opener: Opener = _default_opener,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.cache_dir = cache_dir
        self.cache_ttl_s = cache_ttl_s
        self.retries = retries
        self.timeout_s = timeout_s
        self._opener = opener
        self._sleep = sleep
        self._clock = clock

    def _cache_path(self, shown_url: str) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / (hashlib.sha256(shown_url.encode()).hexdigest()[:32] + ".cache")

    def get(self, url: str, params: dict[str, str] | None = None) -> bytes:
        params = params or {}
        shown = redact(url, params)

        cache_path = self._cache_path(shown)
        if cache_path is not None and cache_path.exists():
            if self._clock() - cache_path.stat().st_mtime < self.cache_ttl_s:
                log.debug("Cache hit %s", shown)
                return cache_path.read_bytes()

        request = Request(f"{url}?{urlencode(params)}" if params else url, headers={"User-Agent": USER_AGENT})
        for attempt in range(self.retries + 1):
            try:
                body = self._opener(request, self.timeout_s)
                break
            except HTTPError as e:
                if e.code not in RETRY_STATUSES or attempt == self.retries:
                    raise FetchError(f"GET {shown} failed: HTTP {e.code}") from None
                delay = _retry_after(e) or float(2**attempt)
                log.warning("GET %s returned HTTP %s, retrying in %.0fs", shown, e.code, delay)
            except (URLError, TimeoutError) as e:
                reason = getattr(e, "reason", e)
                if attempt == self.retries:
                    raise FetchError(f"GET {shown} failed: {reason}") from None
                delay = float(2**attempt)
                log.warning("GET %s failed (%s), retrying in %.0fs", shown, reason, delay)
            self._sleep(delay)

        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(body)
        log.info("GET %s (%d bytes)", shown, len(body))
        return body
