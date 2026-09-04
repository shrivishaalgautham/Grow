import uuid

from app.cache import cache
from app.models import Symbol, WatchlistItem
from tests.api.support import start_session


def test_fifty_first_symbol_is_rejected(client, db, seeded):
    headers, body = start_session(client)
    user_id = uuid.UUID(body["user"]["id"])
    fillers = [f"FILL{i:02d}.NS" for i in range(50)]
    db.add_all(Symbol(symbol=s, name=s, industry="Filler", isin="") for s in fillers)
    db.flush()
    db.add_all(WatchlistItem(user_id=user_id, symbol=s) for s in fillers)
    db.commit()

    response = client.post("/api/watchlist/items", json={"symbol": "RELIANCE.NS"}, headers=headers)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "watchlist_full"


def test_duplicate_add_conflicts(client, seeded):
    headers, _ = start_session(client)
    assert (
        client.post("/api/watchlist/items", json={"symbol": "TCS.NS"}, headers=headers).status_code
        == 201
    )

    response = client.post("/api/watchlist/items", json={"symbol": "TCS.NS"}, headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_added"


def test_add_requests_a_one_off_refresh(client, seeded):
    headers, _ = start_session(client)

    response = client.post("/api/watchlist/items", json={"symbol": "INFY.NS"}, headers=headers)

    assert response.status_code == 201, response.text
    assert response.json()["symbol"] == "INFY.NS"
    assert response.json()["catalyst_status"] == "not_fetched"
    assert cache.get("refresh:req:INFY.NS") == "1"
