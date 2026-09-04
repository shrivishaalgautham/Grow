import uuid
from datetime import datetime

from sqlalchemy import select

from app.models import UserSymbolState
from tests.api.support import start_session


def test_reading_the_digest_never_changes_it(client, seeded):
    headers, _ = start_session(client, start_with_sample=True)

    counts = [
        client.get("/api/watchlist/digest", headers=headers).json()["changed_count"]
        for _ in range(3)
    ]

    assert counts[0] >= 1
    assert counts == [counts[0]] * 3


def test_mark_all_reviewed_clears_the_digest_and_advances_last_reviewed_at(client, seeded):
    headers, _ = start_session(client, start_with_sample=True)
    before = datetime.fromisoformat(
        client.get("/api/auth/me", headers=headers).json()["last_reviewed_at"]
    )

    seen = client.post("/api/watchlist/seen", json={"symbols": "all"}, headers=headers)
    assert seen.status_code == 200, seen.text
    assert seen.json()["marked"] == 12

    digest = client.get("/api/watchlist/digest", headers=headers).json()
    assert digest["changed_count"] == 0
    assert datetime.fromisoformat(digest["last_reviewed_at"]) > before


def test_marking_one_symbol_only_advances_that_symbol(client, db, seeded):
    headers, body = start_session(client, start_with_sample=True)
    me_before = client.get("/api/auth/me", headers=headers).json()
    digest = client.get("/api/watchlist/digest", headers=headers).json()
    reliance = next(item for item in digest["items"] if item["symbol"] == "RELIANCE.NS")

    seen = client.post("/api/watchlist/seen", json={"symbols": ["RELIANCE.NS"]}, headers=headers)
    assert seen.status_code == 200, seen.text
    assert seen.json()["marked"] == 1

    states = db.scalars(
        select(UserSymbolState).where(UserSymbolState.user_id == uuid.UUID(body["user"]["id"]))
    ).all()
    assert [s.symbol for s in states] == ["RELIANCE.NS"]
    assert states[0].last_seen_price == reliance["quote"]["price"]
    me_after = client.get("/api/auth/me", headers=headers).json()
    assert me_after["last_reviewed_at"] == me_before["last_reviewed_at"]
    after = client.get("/api/watchlist/digest", headers=headers).json()
    assert after["changed_count"] == digest["changed_count"]
    seen_item = next(item for item in after["items"] if item["symbol"] == "RELIANCE.NS")
    assert seen_item["last_seen_at"] is not None
    assert seen_item["change_since_seen_pct"] == 0.0
