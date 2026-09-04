import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from app.schemas import (
    BriefingOut,
    CatalystsOut,
    DigestOut,
    EvidenceOut,
    HistoryOut,
    PeersOut,
    ProvidersHealthOut,
    RuleListItem,
    SymbolSearchOut,
)

FIXTURES = Path(__file__).resolve().parents[3] / "ui" / "src" / "fixtures"
CONTRACT = {
    "digest.json": DigestOut,
    "briefing.json": BriefingOut,
    "evidence.json": EvidenceOut,
    "history.json": HistoryOut,
    "peers.json": PeersOut,
    "catalysts.found.json": CatalystsOut,
    "catalysts.none_found.json": CatalystsOut,
    "catalysts.pending.json": CatalystsOut,
    "catalysts.unavailable.json": CatalystsOut,
    "rules.json": list[RuleListItem],
    "search.json": list[SymbolSearchOut],
    "health.json": ProvidersHealthOut,
}


@pytest.mark.parametrize(("name", "model"), CONTRACT.items())
def test_every_frontend_fixture_parses_into_its_response_model(name, model):
    payload = json.loads((FIXTURES / name).read_text())

    parsed = TypeAdapter(model).validate_python(payload)

    assert parsed is not None


def test_digest_fixture_covers_every_signal_type_and_confidence_state():
    digest = DigestOut.model_validate(json.loads((FIXTURES / "digest.json").read_text()))

    signal_types = {s.type for item in digest.items for s in item.signals}
    confidences = {item.quote.confidence for item in digest.items}
    assert {"EXCESS_MOVE", "VOLUME_CONFIRMED", "LEVEL_BREAK", "SINCE_SEEN_MOVE"} <= signal_types
    assert {"disputed", "stale"} <= confidences or {"disputed", "delayed"} <= confidences
    assert any(item.low_confidence for item in digest.items)
