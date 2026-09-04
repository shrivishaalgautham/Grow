import json
from datetime import date, datetime
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import respx
from fastapi.testclient import TestClient
from sqlalchemy import insert
from sqlalchemy.orm import Session

from app import clock
from app.ai.client import CHAT_URL
from app.api.sample import DEMO_SYMBOLS
from app.engine.baselines import compute_baseline, daily_returns
from app.models import Baseline, DailyBar, PeerCluster, SignalEvent, Symbol
from app.quotes import INDEX_SYMBOL
from tests.synthetic import IST, bars_from_returns

UNIVERSE = Path(__file__).resolve().parents[2] / "app" / "data" / "universe.json"
SESSIONS = 300
DEMO = [f"{name}.NS" for name in DEMO_SYMBOLS]
CLUSTER_ID = "c00"
CLUSTER = ["TCS.NS", "INFY.NS", "TMPV.NS", "MARUTI.NS"]
EVENT_SYMBOL = "ADANIENT.NS"
EVENT_HEADLINE = "Unusually large stock-specific move"
EVENT_MAGNITUDES = [4.5, 3.2, 2.8]


def seed_market(session: Session, seed: int = 7) -> date:
    rng = np.random.default_rng(seed)
    universe = {row["symbol"]: row for row in json.loads(UNIVERSE.read_text())}
    session.add(
        Symbol(symbol=INDEX_SYMBOL, name="NIFTY 50", industry="Index", isin="", is_active=False)
    )
    session.add_all(Symbol(**universe[symbol]) for symbol in DEMO)
    session.flush()

    index_returns = rng.normal(0, 0.01, SESSIONS)
    index_bars = bars_from_returns(index_returns, start_price=25_000.0)
    _insert_bars(session, INDEX_SYMBOL, index_bars)
    bars = {
        symbol: bars_from_returns(
            index_returns * 0.9 + rng.normal(0, 0.012, SESSIONS),
            start_price=float(rng.uniform(200, 3_000)),
        )
        for symbol in DEMO
    }
    for symbol, frame in bars.items():
        _insert_bars(session, symbol, frame)
    _insert_baselines(session, bars, daily_returns(index_bars["close"]))
    _insert_events(session, bars[EVENT_SYMBOL])
    session.flush()
    return bars[EVENT_SYMBOL].index[-1].date()


def start_session(client: TestClient, **payload) -> tuple[dict[str, str], dict]:
    response = client.post("/api/auth/session", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['token']}"}, body


def mock_llm(content: str) -> respx.Route:
    body = {"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 42}}
    return respx.post(CHAT_URL).mock(return_value=httpx.Response(200, json=body))


def _insert_bars(session: Session, symbol: str, frame: pd.DataFrame) -> None:
    session.execute(
        insert(DailyBar),
        [
            {
                "symbol": symbol,
                "date": day.date(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": int(row["volume"]),
            }
            for day, row in frame.iterrows()
        ],
    )


def _insert_baselines(session: Session, bars: dict[str, pd.DataFrame], index: pd.Series) -> None:
    computed_at = datetime.now(IST)
    for symbol, frame in bars.items():
        in_cluster = symbol in CLUSTER
        peers = _peer_median(bars, symbol) if in_cluster else None
        b = compute_baseline(frame, index, peers)
        session.add(
            Baseline(
                symbol=symbol,
                beta=b.beta,
                residual_sigma=b.residual_sigma,
                raw_mean_20=b.raw_mean_20,
                raw_sigma_20=b.raw_sigma_20,
                sigma_daily_90=b.sigma_daily_90,
                avg_volume_20d=b.avg_volume_20d,
                sma_20=b.sma_20,
                sma_50=b.sma_50,
                sma_200=b.sma_200,
                high_52w=b.high_52w,
                low_52w=b.low_52w,
                prev_close=b.prev_close,
                prev_high=b.prev_high,
                prev_low=b.prev_low,
                cluster_id=CLUSTER_ID if in_cluster else None,
                confidence=b.confidence,
                computed_at=computed_at,
            )
        )
        if in_cluster:
            session.add(PeerCluster(cluster_id=CLUSTER_ID, symbol=symbol, computed_at=computed_at))


def _peer_median(bars: dict[str, pd.DataFrame], symbol: str) -> pd.Series:
    others = pd.DataFrame(
        {other: daily_returns(bars[other]["close"]) for other in CLUSTER if other != symbol}
    )
    return others.median(axis=1)


def _insert_events(session: Session, frame: pd.DataFrame) -> None:
    for magnitude, day in zip(EVENT_MAGNITUDES, reversed(frame.index[-3:]), strict=True):
        trading_date = day.date()
        session.add(
            SignalEvent(
                symbol=EVENT_SYMBOL,
                signal_type="EXCESS_MOVE",
                trading_date=trading_date,
                fired_at=datetime.combine(trading_date, clock.CLOSE, tzinfo=IST),
                magnitude=magnitude,
                payload={
                    "today_change_pct": -9.4,
                    "peer_change_pct": -0.4,
                    "residual_pct": -9.0,
                    "z_score": magnitude,
                    "raw_z_score": 3.1,
                    "rvol": 2.4,
                    "headline": EVENT_HEADLINE,
                    "detail": "Down 9.4% while its peer group averaged -0.4%.",
                },
            )
        )
