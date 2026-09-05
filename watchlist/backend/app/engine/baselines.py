import math
from dataclasses import dataclass
from typing import Literal

import pandas as pd

BETA_WINDOW = 90
RAW_WINDOW = 20
VOLUME_WINDOW = 20
YEAR_SESSIONS = 252
MIN_SESSIONS = 60
MIN_RESIDUAL_SIGMA = 1e-4
RSI_WINDOW = 14


@dataclass(frozen=True)
class Baseline:
    beta: float
    residual_sigma: float
    raw_mean_20: float
    raw_sigma_20: float
    sigma_daily_90: float
    avg_volume_20d: float
    sma_20: float | None
    sma_50: float | None
    sma_200: float | None
    rsi_14: float | None
    high_52w: float | None
    low_52w: float | None
    prev_close: float
    prev_high: float
    prev_low: float
    confidence: Literal["ok", "low"]
    sessions: int


def daily_returns(close: pd.Series) -> pd.Series:
    return close.pct_change().dropna()


def compute_baseline(
    bars: pd.DataFrame, index_returns: pd.Series, peer_returns: pd.Series | None = None
) -> Baseline:
    if len(bars) < 2:
        raise ValueError(f"need at least 2 bars to compute a baseline, got {len(bars)}")
    returns = daily_returns(bars["close"])
    beta = _beta(returns, index_returns)
    is_beta_usable = math.isfinite(beta)
    if not is_beta_usable:
        beta = 1.0
    residual_sigma = _std(_residuals(returns, index_returns, beta, peer_returns).tail(BETA_WINDOW))
    raw_20 = returns.tail(RAW_WINDOW)
    year_high = _year_window(bars["high"])
    year_low = _year_window(bars["low"])
    last = bars.iloc[-1]
    is_low = len(bars) < MIN_SESSIONS or residual_sigma < MIN_RESIDUAL_SIGMA or not is_beta_usable
    return Baseline(
        beta=1.0 if is_low else beta,
        residual_sigma=residual_sigma,
        raw_mean_20=float(raw_20.mean()),
        raw_sigma_20=_std(raw_20),
        sigma_daily_90=_std(returns.tail(BETA_WINDOW)),
        avg_volume_20d=float(bars["volume"].tail(VOLUME_WINDOW).median()),
        sma_20=_trailing_mean(bars["close"], 20),
        sma_50=_trailing_mean(bars["close"], 50),
        sma_200=_trailing_mean(bars["close"], 200),
        rsi_14=_rsi(bars["close"]),
        high_52w=float(year_high.max()) if year_high is not None else None,
        low_52w=float(year_low.min()) if year_low is not None else None,
        prev_close=float(last["close"]),
        prev_high=float(last["high"]),
        prev_low=float(last["low"]),
        confidence="low" if is_low else "ok",
        sessions=len(bars),
    )


def _beta(returns: pd.Series, index_returns: pd.Series) -> float:
    aligned = pd.concat([returns, index_returns], axis=1, join="inner").tail(BETA_WINDOW)
    if len(aligned) < 2:
        return math.nan
    stock, index = aligned.iloc[:, 0], aligned.iloc[:, 1]
    variance = index.var()
    if not variance or not math.isfinite(variance):
        return math.nan
    return float(stock.cov(index) / variance)


def _residuals(
    returns: pd.Series, index_returns: pd.Series, beta: float, peer_returns: pd.Series | None
) -> pd.Series:
    reference = peer_returns if peer_returns is not None else beta * index_returns
    return (returns - reference).dropna()


def _std(values: pd.Series) -> float:
    if len(values) < 2:
        return 0.0
    result = float(values.std())
    return result if math.isfinite(result) else 0.0


def _trailing_mean(close: pd.Series, window: int) -> float | None:
    if len(close) < window:
        return None
    return float(close.tail(window).mean())


def _year_window(values: pd.Series) -> pd.Series | None:
    if len(values) < YEAR_SESSIONS:
        return None
    return values.tail(YEAR_SESSIONS)


def _rsi(close: pd.Series) -> float | None:
    if len(close) < RSI_WINDOW + 1:
        return None
    delta = close.diff().dropna()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    smoothing = {"alpha": 1 / RSI_WINDOW, "min_periods": RSI_WINDOW, "adjust": False}
    avg_gain = gains.ewm(**smoothing).mean().iloc[-1]
    avg_loss = losses.ewm(**smoothing).mean().iloc[-1]
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return float(100 - 100 / (1 + rs))
