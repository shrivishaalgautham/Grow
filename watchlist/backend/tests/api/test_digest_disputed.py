import json
import uuid
from datetime import datetime

from app.cache import cache
from app.models import UserRule
from tests.api.support import EVENT_SYMBOL, start_session
from tests.synthetic import IST

ALWAYS_TRUE_FOR_SYMBOL = {
    "symbols": [EVENT_SYMBOL],
    "all": [{"field": "rvol", "op": ">=", "value": 0}],
}


def _item(client, headers, symbol):
    digest = client.get("/api/watchlist/digest", headers=headers).json()
    return next(item for item in digest["items"] if item["symbol"] == symbol)


def test_disputed_quote_drops_live_signals_but_keeps_persisted_ones(client, db, seeded):
    headers, body = start_session(client, start_with_sample=True)
    db.add(
        UserRule(
            user_id=uuid.UUID(body["user"]["id"]),
            nl_text="alert me on any adani volume",
            compiled=ALWAYS_TRUE_FOR_SYMBOL,
            preview="Alert on ADANIENT when its relative volume is at least 0x.",
        )
    )
    db.commit()
    before = _item(client, headers, EVENT_SYMBOL)
    assert {s["type"] for s in before["signals"]} == {"EXCESS_MOVE", "USER_RULE"}

    disputed = {**before["quote"], "confidence": "disputed", "as_of": datetime.now(IST).isoformat()}
    cache.set_many({f"q:{EVENT_SYMBOL}": json.dumps(disputed)}, ttl=60)
    after = _item(client, headers, EVENT_SYMBOL)

    assert after["quote"]["confidence"] == "disputed"
    assert [s["type"] for s in after["signals"]] == ["EXCESS_MOVE"] * 3
    assert after["is_changed"] is True
