from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


class FakeHttp:
    """Stands in for HttpClient: maps a URL to fixture bytes and records calls."""

    def __init__(self, responses: dict[str, bytes | Exception | list[bytes]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, params: dict[str, str] | None = None) -> bytes:
        self.calls.append((url, dict(params or {})))
        response = self.responses[url]
        if isinstance(response, list):
            response = response[len([c for c in self.calls if c[0] == url]) - 1]
        if isinstance(response, Exception):
            raise response
        return response


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.fixture
def fake_http():
    return FakeHttp
