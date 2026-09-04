import json
import re

from app.cache import cache

LEAK_PATTERN = re.compile(r"https?://|://|Traceback|Exception|Error|password|redis://", re.I)


def test_providers_health_exposes_exactly_the_contract_fields(client, seeded):
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
