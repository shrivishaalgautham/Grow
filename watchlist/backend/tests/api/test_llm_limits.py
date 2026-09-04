from fastapi import Depends
from fastapi.testclient import TestClient

from app.api.ratelimit import llm_global_daily
from app.config import settings
from app.main import create_app


def test_global_daily_llm_cap_returns_429_once_exhausted():
    app = create_app()
    app.add_api_route(
        "/api/_llm", lambda: {"ok": True}, methods=["GET"], dependencies=[Depends(llm_global_daily)]
    )
    with TestClient(app) as client:
        for _ in range(settings.llm_global_daily_cap):
            assert client.get("/api/_llm").status_code == 200

        response = client.get("/api/_llm")

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert 1 <= response.json()["error"]["retry_after_seconds"] <= 86400
