import json
import re
from pathlib import Path

from app.schemas import SYMBOL_PATTERN

UNIVERSE = Path(__file__).resolve().parent.parent / "app" / "data" / "universe.json"


def load() -> list[dict]:
    return json.loads(UNIVERSE.read_text())


def test_universe_has_150_symbols():
    assert len(load()) == 150


def test_universe_reflects_tata_motors_demerger():
    symbols = {row["symbol"] for row in load()}
    assert "TMPV.NS" in symbols
    assert "TATAMOTORS.NS" not in symbols


def test_every_row_is_well_formed():
    for row in load():
        assert re.fullmatch(SYMBOL_PATTERN, row["symbol"]), row
        assert row["name"] and row["industry"] and row["isin"], row


def test_universe_is_sorted_and_unique():
    symbols = [row["symbol"] for row in load()]
    assert symbols == sorted(set(symbols))
