import pytest
from fastapi.testclient import TestClient

from app.deps import ApiError
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()

    def explode() -> None:
        raise RuntimeError("secret internal detail")

    def api_error() -> None:
        raise ApiError(429, "rate_limited", "too many requests", retry_after_seconds=17)

    app.add_api_route("/api/_explode", explode, methods=["GET"])
    app.add_api_route("/api/_api_error", api_error, methods=["GET"])
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_unhandled_error_returns_generic_shape_without_traceback(client):
    response = client.get("/api/_explode")
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "internal_error", "message": "internal error"}}
    assert "secret internal detail" not in response.text
    assert "Traceback" not in response.text


def test_api_error_maps_to_contract_shape(client):
    response = client.get("/api/_api_error")
    assert response.status_code == 429
    assert response.json() == {
        "error": {"code": "rate_limited", "message": "too many requests", "retry_after_seconds": 17}
    }


def test_cors_preflight_allowed_origin(client):
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-credentials" not in response.headers


def test_cors_preflight_disallowed_origin(client):
    response = client.options(
        "/api/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in response.headers
