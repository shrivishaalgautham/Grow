import pytest

from app.engine.residual import decompose
from tests.synthetic import make_baseline


def test_pure_market_move_has_no_residual():
    baseline = make_baseline(beta=1.2)

    d = decompose(price=102.4, prev_close=100.0, index_return=0.02, peer_return=None, b=baseline)

    assert d.peer_method == "beta"
    assert d.today_change_pct == pytest.approx(2.4)
    assert d.peer_change_pct == pytest.approx(2.4)
    assert d.residual_pct == pytest.approx(0.0, abs=1e-9)
    assert d.z_score == pytest.approx(0.0, abs=1e-9)


def test_stock_specific_move_is_entirely_residual():
    baseline = make_baseline(residual_sigma=0.01)

    d = decompose(price=103.0, prev_close=100.0, index_return=0.0, peer_return=0.0, b=baseline)

    assert d.peer_method == "cluster"
    assert d.residual_pct == pytest.approx(3.0)
    assert d.z_score == pytest.approx(3.0)


def test_z_scores_are_absolute_and_capped_at_twenty():
    baseline = make_baseline(residual_sigma=1e-6, raw_sigma_20=1e-6)

    d = decompose(price=97.0, prev_close=100.0, index_return=0.0, peer_return=None, b=baseline)

    assert d.residual_pct == pytest.approx(-3.0)
    assert d.z_score == 20.0
    assert d.raw_z_score == 20.0


def test_zero_sigma_yields_zero_z():
    baseline = make_baseline(residual_sigma=0.0, raw_sigma_20=0.0)

    d = decompose(price=103.0, prev_close=100.0, index_return=0.0, peer_return=None, b=baseline)

    assert (d.z_score, d.raw_z_score) == (0.0, 0.0)


def test_non_positive_prev_close_is_rejected():
    with pytest.raises(ValueError, match="prev_close"):
        decompose(
            price=100.0, prev_close=0.0, index_return=0.0, peer_return=None, b=make_baseline()
        )
