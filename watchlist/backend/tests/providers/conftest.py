import json
from pathlib import Path

import pytest

from app.cache import cache
from app.providers.ratelimit import TokenBucket

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_cache():
    cache._memory.clear()
    yield
    cache._memory.clear()


@pytest.fixture
def bypass_bucket(monkeypatch):
    monkeypatch.setattr(TokenBucket, "acquire", lambda self, timeout_s=10.0: None)


def load_json(name: str) -> dict | list:
    return json.loads((FIXTURES / name).read_text())


def load_text(name: str) -> str:
    return (FIXTURES / name).read_text()
