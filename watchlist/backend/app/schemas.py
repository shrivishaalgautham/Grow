import math
import re
import unicodedata
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

SYMBOL_PATTERN = r"^[A-Z0-9&-]{1,20}\.(NS|BO)$"
DISPLAY_NAME_PATTERN = r"^[a-z0-9_-]{3,32}$"

SymbolStr = Annotated[str, StringConstraints(pattern=SYMBOL_PATTERN)]

MarketStatus = Literal["open", "closed", "pre_open"]
QuoteSource = Literal["yahoo", "bse"]
Confidence = Literal["fresh", "delayed", "stale", "disputed", "closed"]
SignalType = Literal[
    "EXCESS_MOVE",
    "VOLUME_CONFIRMED",
    "LEVEL_BREAK",
    "SINCE_SEEN_MOVE",
    "USER_RULE",
    "GAP",
    "SMA_CROSSOVER",
    "RSI_EXTREME",
]
Attention = Literal["high", "notable", "quiet"]
PeerMethod = Literal["cluster", "beta"]
CatalystStatus = Literal["not_fetched", "pending", "found", "none_found", "unavailable"]
BriefingSource = Literal["llm", "template"]
LevelName = Literal["52w_high", "52w_low", "prev_high", "prev_low"]
RuleField = Literal[
    "residual_pct",
    "abs_residual_pct",
    "z_score",
    "rvol",
    "peer_return_pct",
    "abs_peer_return_pct",
    "gap_pct",
    "abs_gap_pct",
    "level_break",
    "has_catalyst",
]
RuleOp = Literal[">=", "<=", "=="]
ErrorCode = Literal[
    "unauthorized",
    "session_expired",
    "not_surfaced",
    "invalid_symbol",
    "not_in_universe",
    "watchlist_full",
    "invalid_rule",
    "already_added",
    "rate_limited",
    "internal_error",
    "not_in_watchlist",
    "not_seeded",
    "invalid_request",
    "invalid_oauth_state",
    "oauth_failed",
]

NUMERIC_BOUNDS: dict[str, tuple[float, float]] = {
    "rvol": (0, 100),
    "z_score": (0, 20),
    "residual_pct": (-100, 100),
    "abs_residual_pct": (-100, 100),
    "peer_return_pct": (-100, 100),
    "abs_peer_return_pct": (-100, 100),
    "gap_pct": (-100, 100),
    "abs_gap_pct": (-100, 100),
}
NON_NEGATIVE_FIELDS = {"abs_residual_pct", "abs_peer_return_pct", "abs_gap_pct", "rvol", "z_score"}


def normalize_display_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    if not re.fullmatch(DISPLAY_NAME_PATTERN, normalized):
        raise ValueError("display_name must match ^[a-z0-9_-]{3,32}$ after NFKC casefold")
    return normalized


class AltQuote(BaseModel):
    price: float
    source: QuoteSource
    as_of: datetime


class Quote(BaseModel):
    price: float
    prev_close: float
    open: float | None = None
    day_high: float
    day_low: float
    volume: int
    as_of: datetime
    source: QuoteSource
    staleness_seconds: int
    confidence: Confidence
    alt: AltQuote | None
    divergence_pct: float | None


class Signal(BaseModel):
    type: SignalType
    headline: str
    detail: str
    fired_at: datetime
    trading_date: date
    rule_id: str | None


class Levels(BaseModel):
    high_52w: float
    low_52w: float
    prev_high: float
    prev_low: float


class SmaDistance(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sma_20: float = Field(alias="20")
    sma_50: float = Field(alias="50")
    sma_200: float = Field(alias="200")


class Peer(BaseModel):
    method: PeerMethod
    cluster_id: str | None
    size: int
    members: list[str]


class Item(BaseModel):
    symbol: SymbolStr
    name: str
    industry: str
    quote: Quote
    today_change_pct: float
    peer_change_pct: float
    residual_pct: float
    z_score: float
    raw_z_score: float
    rvol: float
    rvol_is_approximate: bool
    change_since_seen_pct: float | None
    last_seen_at: datetime | None
    attention: Attention
    is_changed: bool
    low_confidence: bool
    signals: list[Signal]
    levels: Levels
    sma_distance_pct: SmaDistance
    peer: Peer
    catalyst_status: CatalystStatus


class RuleCondition(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    field: RuleField
    op: RuleOp
    value: float | str | bool

    @model_validator(mode="after")
    def check_value_for_field(self) -> "RuleCondition":
        if self.field == "level_break":
            return self._check_level_break()
        if self.field == "has_catalyst":
            return self._check_has_catalyst()
        return self._check_numeric()

    def _check_level_break(self) -> "RuleCondition":
        if self.op != "==" or self.value not in LevelName.__args__:
            raise ValueError(
                "level_break requires op == and one of 52w_high, 52w_low, prev_high, prev_low"
            )
        return self

    def _check_has_catalyst(self) -> "RuleCondition":
        if self.op != "==" or not isinstance(self.value, bool):
            raise ValueError("has_catalyst requires op == and a boolean value")
        return self

    def _check_numeric(self) -> "RuleCondition":
        if isinstance(self.value, bool) or not isinstance(self.value, int | float):
            raise ValueError(f"{self.field} requires a numeric value")
        if not math.isfinite(self.value):
            raise ValueError(f"{self.field} value must be finite")
        low, high = NUMERIC_BOUNDS[self.field]
        if not low <= self.value <= high:
            raise ValueError(f"{self.field} value must be within [{low}, {high}]")
        return self

    @property
    def is_always_true(self) -> bool:
        return (
            self.field in NON_NEGATIVE_FIELDS
            and self.op == ">="
            and isinstance(self.value, int | float)
            and self.value <= 0
        )


class Rule(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    symbols: list[SymbolStr] | Literal["all"] = Field(max_length=20)
    all: list[RuleCondition] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def reject_vacuous_universe_rule(self) -> "Rule":
        if self.symbols == "all" and any(c.is_always_true for c in self.all):
            raise ValueError(
                "a rule over all symbols cannot contain a condition that is always true"
            )
        return self


class SessionCreate(BaseModel):
    display_name: str | None = None
    start_with_sample: bool = False

    @field_validator("display_name")
    @classmethod
    def normalize(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_display_name(value)


class UserOut(BaseModel):
    id: str
    display_name: str
    is_sample: bool


class SessionOut(BaseModel):
    token: str
    expires_at: datetime
    user: UserOut


class MeOut(BaseModel):
    id: str
    display_name: str
    is_sample: bool
    email: str | None
    last_reviewed_at: datetime | None
    expires_at: datetime


class DigestOut(BaseModel):
    now: datetime
    market_status: MarketStatus
    replay_date: date | None
    latest_bar_date: date
    away_duration_seconds: int | None
    last_reviewed_at: datetime | None
    changed_count: int
    total_count: int
    items: list[Item]
    providers_degraded: bool


class ItemAdd(BaseModel):
    symbol: SymbolStr


class SeenIn(BaseModel):
    symbols: list[SymbolStr] | Literal["all"] = Field(max_length=100)


class SeenOut(BaseModel):
    marked: int
    reviewed_at: datetime


class BriefingOut(BaseModel):
    text: str = Field(max_length=600)
    source: BriefingSource
    generated_at: datetime
    was_cached: bool


class SymbolSearchOut(BaseModel):
    symbol: SymbolStr
    name: str
    industry: str


class HistoryBar(BaseModel):
    date: date
    close: float
    volume: int
    today_change_pct: float
    residual_pct: float


class SmaSeries(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sma_20: list[float | None] = Field(alias="20")
    sma_50: list[float | None] = Field(alias="50")
    sma_200: list[float | None] = Field(alias="200")


class HistoryOut(BaseModel):
    bars: list[HistoryBar]
    levels: Levels
    sma: SmaSeries


class PeerMember(BaseModel):
    symbol: SymbolStr
    name: str
    today_change_pct: float


class PeersOut(BaseModel):
    method: PeerMethod
    cluster_id: str | None
    size: int
    peer_change_pct: float
    members: list[PeerMember]


class CatalystItem(BaseModel):
    headline: str
    source: str
    url: str
    published_at: datetime | None


class CatalystsOut(BaseModel):
    status: Literal["found", "none_found", "unavailable", "pending"]
    fetched_at: datetime | None
    items: list[CatalystItem]


class ExplanationOut(BaseModel):
    status: Literal["ready", "pending"]
    text: str | None = Field(default=None, max_length=600)
    source: BriefingSource | None
    catalyst_status: CatalystStatus
    items: list[CatalystItem]
    generated_at: datetime | None
    was_cached: bool


EMAIL_PATTERN = r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$"
EmailStr = Annotated[str, StringConstraints(pattern=EMAIL_PATTERN, max_length=254)]

ChannelStatus = Literal["pending", "verified", "disabled"]


class EmailSubscribeIn(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def lowercase(cls, value: str) -> str:
        return value.strip().lower()


class VerifyIn(BaseModel):
    token: str = Field(min_length=16, max_length=128)


class EmailChannelOut(BaseModel):
    address_masked: str
    status: ChannelStatus
    verify_expires_at: datetime | None
    last_notified_at: datetime | None


class NotificationsOut(BaseModel):
    email: EmailChannelOut | None


class VerifyOut(BaseModel):
    status: Literal["verified"]
    address_masked: str


class RuleCompileIn(BaseModel):
    text: str = Field(min_length=1, max_length=200)


class RuleCompileOut(BaseModel):
    rule: Rule | None
    preview: str | None
    error: str | None = Field(default=None, max_length=200)


class RuleCreateIn(BaseModel):
    nl_text: str = Field(min_length=1, max_length=200)
    rule: Rule


class RuleOut(BaseModel):
    id: str
    nl_text: str
    rule: Rule
    preview: str
    enabled: bool
    created_at: datetime


class RuleListItem(BaseModel):
    id: str
    nl_text: str
    preview: str
    enabled: bool
    created_at: datetime
    matched_today: list[str]


class AlertCount(BaseModel):
    alerts: int


class Suppressed(BaseModel):
    total: int
    market_wide: int
    below_floor: int
    within_noise: int


class CaughtExtra(BaseModel):
    symbol: SymbolStr
    date: date
    today_change_pct: float
    peer_change_pct: float
    residual_pct: float
    z_score: float
    rvol: float


class EvidenceOut(BaseModel):
    days: int
    symbols_count: int
    from_date: date
    to_date: date
    computed_at: datetime
    naive_pct_2: AlertCount
    raw_z_2: AlertCount
    engine: AlertCount
    suppressed: Suppressed
    caught_extra: list[CaughtExtra]


class HealthOut(BaseModel):
    ok: Literal[True]


class ProviderHealth(BaseModel):
    provider: str
    circuit_state: Literal["closed", "open", "half_open"]
    last_success_at: datetime | None
    consecutive_failures: int


class SchedulerHealth(BaseModel):
    last_refresh_at: datetime | None


class ProvidersHealthOut(BaseModel):
    providers: list[ProviderHealth]
    scheduler: SchedulerHealth
    redis: Literal["ok", "down", "disabled"]
    db: Literal["ok", "down"]


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    retry_after_seconds: int | None = None


class ErrorOut(BaseModel):
    error: ErrorBody
