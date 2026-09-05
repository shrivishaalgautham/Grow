from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.engine.baselines import Baseline
from app.engine.signals import SessionFacts

IST = ZoneInfo("Asia/Kolkata")
FIRST_SESSION = "2025-06-02"
TRADING_DATE = date(2026, 9, 2)
FIRED_AT = datetime(2026, 9, 2, 15, 30, tzinfo=IST)


def trading_dates(count: int) -> pd.DatetimeIndex:
    return pd.bdate_range(FIRST_SESSION, periods=count)


def bars_from_returns(
    returns, volume=1_000_000.0, spread: float = 0.005, start_price: float = 100.0
) -> pd.DataFrame:
    returns = np.asarray(returns, dtype=float)
    close = start_price * np.cumprod(1 + returns)
    opened = np.concatenate([[start_price], close[:-1]])
    volumes = np.full(len(returns), volume, dtype=float) if np.isscalar(volume) else volume
    return pd.DataFrame(
        {
            "open": opened,
            "high": np.maximum(opened, close) * (1 + spread),
            "low": np.minimum(opened, close) * (1 - spread),
            "close": close,
            "volume": np.asarray(volumes, dtype=float),
        },
        index=trading_dates(len(returns)),
    )


def make_baseline(**overrides) -> Baseline:
    fields = dict(
        beta=1.0,
        residual_sigma=0.01,
        raw_mean_20=0.0,
        raw_sigma_20=0.01,
        sigma_daily_90=0.01,
        avg_volume_20d=1_000_000.0,
        sma_20=100.0,
        sma_50=100.0,
        sma_200=100.0,
        rsi_14=50.0,
        high_52w=120.0,
        low_52w=80.0,
        prev_close=100.0,
        prev_high=102.0,
        prev_low=98.0,
        confidence="ok",
        sessions=300,
    )
    return Baseline(**{**fields, **overrides})


def make_facts(**overrides) -> SessionFacts:
    fields = dict(
        symbol="TMPV.NS",
        price=100.0,
        prev_close=100.0,
        open=100.0,
        day_high=100.0,
        day_low=100.0,
        volume=1_000_000.0,
        index_return=0.0,
        peer_return=None,
        peer_cluster_id=None,
        minutes_since_open=None,
        trading_date=TRADING_DATE,
        fired_at=FIRED_AT,
    )
    return SessionFacts(**{**fields, **overrides})
