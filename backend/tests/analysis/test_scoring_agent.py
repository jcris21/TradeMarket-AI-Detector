"""Tests for ScoringAgent — filter, score, and rank assets."""

import pytest

from app.analysis.models import AssetAnalysis
from app.analysis.scoring_agent import score_and_rank


def _make_analysis(
    ticker: str,
    signal: str = "BUY",
    confidence: float = 0.8,
    rr_ratio: float = 4.0,
    support_validated: bool = True,
    macd: str = "bullish_crossover",
    rsi: float = 55.0,
    volume: str = "above_avg",
) -> AssetAnalysis:
    return AssetAnalysis(
        ticker=ticker,
        signal=signal,
        confidence=confidence,
        entry_price=100.0,
        target_price=130.0,
        stop_loss=90.0,
        risk_reward_ratio=rr_ratio,
        support_validated=support_validated,
        indicators_summary={"macd": macd, "rsi": rsi, "volume": volume},
        argument="Test argument.",
    )


def test_filters_below_min_rr():
    assets = [
        _make_analysis("AAPL", rr_ratio=2.9),  # below 3.0
        _make_analysis("MSFT", rr_ratio=3.0),  # exactly at limit — passes
    ]
    ranked = score_and_rank(assets, min_rr=3.0, top_n=5)
    qualifiers = [a for a in ranked if a.rank is not None]
    assert len(qualifiers) == 1
    assert qualifiers[0].ticker == "MSFT"


def test_filters_avoid_signal():
    assets = [
        _make_analysis("AAPL", signal="AVOID"),
        _make_analysis("MSFT", signal="BUY"),
    ]
    ranked = score_and_rank(assets, min_rr=3.0, top_n=5)
    qualifiers = [a for a in ranked if a.rank is not None]
    assert len(qualifiers) == 1
    assert qualifiers[0].ticker == "MSFT"


def test_ranked_by_score_descending():
    assets = [
        _make_analysis("LOW", confidence=0.5, rr_ratio=3.0),
        _make_analysis("HIGH", confidence=0.9, rr_ratio=5.0),
        _make_analysis("MID", confidence=0.7, rr_ratio=4.0),
    ]
    ranked = score_and_rank(assets, min_rr=3.0, top_n=5)
    qualifiers = [a for a in ranked if a.rank is not None]
    assert qualifiers[0].ticker == "HIGH"
    assert qualifiers[-1].ticker == "LOW"


def test_top_n_limits_ranked_count():
    assets = [_make_analysis(f"T{i}", rr_ratio=3.0 + i) for i in range(8)]
    ranked = score_and_rank(assets, min_rr=3.0, top_n=5)
    qualifiers = [a for a in ranked if a.rank is not None]
    assert len(qualifiers) == 5


def test_zero_qualifying_assets_returns_all_unranked():
    assets = [_make_analysis("AAPL", signal="AVOID"), _make_analysis("MSFT", rr_ratio=1.0)]
    ranked = score_and_rank(assets, min_rr=3.0, top_n=5)
    assert all(a.rank is None for a in ranked)


def test_wait_signal_qualifies():
    assets = [_make_analysis("AAPL", signal="WAIT", rr_ratio=3.5)]
    ranked = score_and_rank(assets, min_rr=3.0, top_n=5)
    qualifiers = [a for a in ranked if a.rank is not None]
    assert len(qualifiers) == 1


def test_score_uses_indicator_confluence():
    # All bullish → higher score than partial
    all_bullish = _make_analysis(
        "FULL", confidence=0.8, rr_ratio=4.0,
        macd="bullish_crossover", rsi=55.0, volume="above_avg"
    )
    partial = _make_analysis(
        "PART", confidence=0.8, rr_ratio=4.0,
        macd="neutral", rsi=75.0, volume="below_avg"
    )
    ranked = score_and_rank([all_bullish, partial], min_rr=3.0, top_n=5)
    full_score = next(a.score for a in ranked if a.ticker == "FULL")
    part_score = next(a.score for a in ranked if a.ticker == "PART")
    assert full_score > part_score
