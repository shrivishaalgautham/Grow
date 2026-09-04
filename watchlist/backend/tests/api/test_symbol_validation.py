import pytest

from tests.api.support import start_session

BAD_SYMBOLS = [
    "reliance.ns",
    "RELIANCE.XX",
    "RELIANCE.NS%3Frange%3Dmax",
    "%5ENSEI.NS",
    "%5ENSEI",
    "ZZZZ.NS",
]


def _symbol_routes(client, headers, symbol):
    return (
        client.delete(f"/api/watchlist/items/{symbol}", headers=headers),
        client.get(f"/api/symbols/{symbol}/history", headers=headers),
        client.get(f"/api/symbols/{symbol}/peers", headers=headers),
    )


@pytest.mark.parametrize("symbol", BAD_SYMBOLS)
def test_bad_symbols_are_rejected_on_every_symbol_route(client, seeded, symbol):
    headers, _ = start_session(client)

    for response in _symbol_routes(client, headers, symbol):
        assert response.status_code == 404, response.text
        assert response.json()["error"]["code"] == "invalid_symbol"


def test_path_traversal_never_reaches_a_handler(client, seeded):
    headers, _ = start_session(client)

    for response in _symbol_routes(client, headers, "%2E%2E%2Fetc"):
        assert response.status_code == 404, response.text
        assert "etc" not in response.text


def test_adding_a_symbol_outside_the_universe_is_rejected(client, seeded):
    headers, _ = start_session(client)

    response = client.post("/api/watchlist/items", json={"symbol": "ZZZZ.NS"}, headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "invalid_symbol"


def test_index_symbol_is_hidden_from_search(client, seeded):
    headers, _ = start_session(client)

    response = client.get("/api/symbols/search", params={"q": "NSEI"}, headers=headers)

    assert response.status_code == 200
    assert response.json() == []
