import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol

SYMBOL_RE = re.compile(r"^[A-Z0-9&-]{1,20}\.(NS|BO)$")
INDEX_SYMBOL = "^NSEI"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
HEADLINE_MAX_CHARS = 160
CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
URL_RE = re.compile(r"https?://", re.IGNORECASE)


@dataclass(frozen=True)
class Bar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True)
class LiveQuote:
    symbol: str
    price: float
    prev_close: float
    day_high: float
    day_low: float
    volume: int
    as_of: datetime
    source: Literal["yahoo", "bse"]


@dataclass(frozen=True)
class Catalyst:
    headline: str
    source: str
    url: str
    published_at: datetime


class ProviderError(Exception):
    def __init__(
        self, provider: str, message: str, status: int | None = None, retryable: bool = False
    ) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider
        self.status = status
        self.retryable = retryable


class QuoteProvider(Protocol):
    name: str

    def quotes(self, symbols: Sequence[str]) -> dict[str, LiveQuote]: ...

    def history(self, symbol: str, range_: str = "1y") -> list[Bar]: ...


def validate_symbol(symbol: str) -> str:
    if symbol != INDEX_SYMBOL and not SYMBOL_RE.fullmatch(symbol):
        raise ValueError(f"invalid symbol {symbol!r}")
    return symbol


def sanitize_headline(raw: str) -> str | None:
    if URL_RE.search(raw):
        return None
    cleaned = " ".join(CONTROL_CHARS_RE.sub(" ", raw).split())
    if not cleaned:
        return None
    return cleaned[:HEADLINE_MAX_CHARS]
