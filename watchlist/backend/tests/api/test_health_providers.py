import json
import re

import pytest

from app.cache import cache
from app.config import settings

LEAK_PATTERN = re.compile(r"https?://|://|Traceback|Exception|Error|password|redis://", re.I)


@pytest.fixture
def redis_disabled(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(cache, "_redis", None)
    monkeypatch.setattr(cache, "mode", "memory")


def test_providers_health_exposes_exactly_the_contract_fields(client, seeded, redis_disabled):
    cache.set_many({"scheduler:last_refresh_at": "2026-09-04T10:15:00+05:30"}, ttl=60)

    response = client.get("/api/health/providers")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"providers", "scheduler", "redis", "db"}
    assert [p["provider"] for p in body["providers"]] == ["yahoo", "bse"]
    for provider in body["providers"]:
        assert set(provider) == {
            "provider",
            "circuit_state",
            "last_success_at",
            "consecutive_failures",
        }
        assert provider["circuit_state"] == "closed"
    assert set(body["scheduler"]) == {"last_refresh_at"}
    assert body["scheduler"]["last_refresh_at"].startswith("2026-09-04T10:15:00")
    assert body["redis"] == "disabled"
    assert body["db"] == "ok"
    assert not LEAK_PATTERN.search(json.dumps(body))


@pytest.mark.parametrize(
    ("mode", "ping", "expected"),
    [("memory", True, "down"), ("redis", False, "down"), ("redis", True, "ok")],
)
def test_redis_status_reflects_configured_reachability(
    client, seeded, monkeypatch, mode, ping, expected
):
    monkeypatch.setattr(settings, "redis_url", "redis://configured.example:6379/0")
    monkeypatch.setattr(cache, "mode", mode)
    monkeypatch.setattr(cache, "ping", lambda: ping)

    response = client.get("/api/health/providers")

    assert response.status_code == 200
    assert response.json()["redis"] == expected
