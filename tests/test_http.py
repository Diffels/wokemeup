import time
from email.message import Message
from urllib.error import HTTPError

import pytest

from pipeline.http import FetchError, HttpClient


def _http_error(code: int, retry_after: str | None = None) -> HTTPError:
    headers = Message()
    if retry_after:
        headers["Retry-After"] = retry_after
    return HTTPError("https://api.example/x?api-key=secret", code, "err", headers, None)


class Opener:
    def __init__(self, outcomes: list) -> None:
        self.outcomes = outcomes
        self.urls: list[str] = []

    def __call__(self, request, timeout):
        self.urls.append(request.full_url)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_retries_on_429_honouring_retry_after() -> None:
    sleeps: list[float] = []
    opener = Opener([_http_error(429, "7"), b"ok"])
    client = HttpClient(opener=opener, sleep=sleeps.append)
    assert client.get("https://api.example/x", {"api-key": "secret"}) == b"ok"
    assert sleeps == [7.0]
    assert "api-key=secret" in opener.urls[0]  # the real request carries the key


def test_error_message_never_contains_the_secret() -> None:
    client = HttpClient(opener=Opener([_http_error(401)]), sleep=lambda s: None)
    with pytest.raises(FetchError) as info:
        client.get("https://api.example/x", {"api-key": "secret", "q": "a"})
    assert "secret" not in str(info.value)
    assert "api-key=%2A%2A%2A" in str(info.value)
    assert info.value.__cause__ is None and info.value.__suppress_context__


def test_gives_up_after_retries() -> None:
    client = HttpClient(retries=2, opener=Opener([_http_error(503)] * 3), sleep=lambda s: None)
    with pytest.raises(FetchError, match="HTTP 503"):
        client.get("https://api.example/x")


def test_cache_avoids_second_request_and_hides_secret(tmp_path) -> None:
    opener = Opener([b"body"])
    client = HttpClient(cache_dir=tmp_path, cache_ttl_s=600, opener=opener)
    assert client.get("https://api.example/x", {"api-key": "secret"}) == b"body"
    assert client.get("https://api.example/x", {"api-key": "secret"}) == b"body"
    assert len(opener.urls) == 1
    for path in tmp_path.iterdir():
        assert "secret" not in path.name and b"secret" not in path.read_bytes()


def test_expired_cache_is_refetched(tmp_path) -> None:
    opener = Opener([b"old", b"new"])
    client = HttpClient(cache_dir=tmp_path, cache_ttl_s=600, opener=opener)
    client.get("https://api.example/x")
    client._clock = lambda: time.time() + 601
    assert client.get("https://api.example/x") == b"new"
