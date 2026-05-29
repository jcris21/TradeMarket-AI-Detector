"""Tests for ScoringAgent — filter, score, and rank assets."""

import pytest
import aiosqlite

from app.analysis.models import AssetAnalysis
from app.analysis.scoring_agent import _compute_bet_size, _get_hit_rate, _get_prior_scores, score_and_rank


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


# ── Bet-size tests (Nex 9) ────────────────────────────────────────────────────

def _make_asset(entry: float, target: float, stop: float) -> AssetAnalysis:
    return AssetAnalysis(
        ticker="TEST",
        signal="BUY",
        confidence=0.8,
        entry_price=entry,
        target_price=target,
        stop_loss=stop,
        risk_reward_ratio=3.0,
        support_validated=True,
        indicators_summary={},
        argument="test",
    )


@pytest.mark.parametrize(
    "entry,target,stop,expected_gain,expected_loss",
    [
        (100.0, 130.0, 90.0, 3.0, 1.0),   # test_bet_size_rr_3
        (100.0, 120.0, 90.0, 2.0, 1.0),   # test_bet_size_rr_2
        (100.0, 160.0, 90.0, 6.0, 1.0),   # test_bet_size_rr_6
    ],
    ids=["rr_3", "rr_2", "rr_6"],
)
def test_bet_size_gain_loss(entry, target, stop, expected_gain, expected_loss):
    result = _compute_bet_size(_make_asset(entry, target, stop), 0.35, "assumed")
    assert result.expected_gain_per10 == expected_gain
    assert result.expected_loss_per10 == expected_loss


def test_bet_size_division_by_zero():
    result = _compute_bet_size(_make_asset(0.0, 130.0, 90.0), 0.35, "assumed")
    assert result.expected_gain_per10 == 0.0
    assert result.expected_loss_per10 == 0.0
    assert result.expected_value_per10 == 0.0


async def _db_with_outcomes(n_total: int, n_wins: int) -> aiosqlite.Connection:
    db = await aiosqlite.connect(":memory:")
    await db.execute(
        "CREATE TABLE signal_outcomes (id TEXT PRIMARY KEY, user_id TEXT, outcome TEXT)"
    )
    for i in range(n_total):
        outcome = "win" if i < n_wins else "loss"
        await db.execute(
            "INSERT INTO signal_outcomes VALUES (?, 'default', ?)", (str(i), outcome)
        )
    await db.commit()
    return db


@pytest.mark.asyncio
async def test_ev_switch_assumed():
    db = await _db_with_outcomes(5, 2)
    try:
        rate, source = await _get_hit_rate(db)
    finally:
        await db.close()
    assert rate == 0.35
    assert source == "assumed"


@pytest.mark.asyncio
async def test_ev_switch_realized():
    db = await _db_with_outcomes(30, 12)
    try:
        rate, source = await _get_hit_rate(db)
    finally:
        await db.close()
    assert rate == pytest.approx(12 / 30)
    assert source == "realized"


@pytest.mark.asyncio
async def test_get_hit_rate_fallback():
    db = await aiosqlite.connect(":memory:")
    try:
        rate, source = await _get_hit_rate(db)
    finally:
        await db.close()
    assert rate == 0.35
    assert source == "assumed"


# ── Score-delta tests (NEX-18) ────────────────────────────────────────────────

async def _db_with_two_runs(prior_ticker_scores: dict[str, float]) -> aiosqlite.Connection:
    """In-memory DB with a prior run and a more recent current run."""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute(
        "CREATE TABLE analysis_results "
        "(id TEXT, run_id TEXT, ticker TEXT, score REAL, analyzed_at TEXT)"
    )
    for ticker, score in prior_ticker_scores.items():
        await db.execute(
            "INSERT INTO analysis_results VALUES (?, 'run-prior', ?, ?, '2026-01-01T00:00:00')",
            (ticker, ticker, score),
        )
    # More recent "current" run so OFFSET 1 picks the prior run
    await db.execute(
        "INSERT INTO analysis_results VALUES ('x', 'run-current', 'DUMMY', 50.0, '2026-01-02T00:00:00')"
    )
    await db.commit()
    return db


@pytest.mark.asyncio
async def test_score_delta_between_runs():
    db = await _db_with_two_runs({"AAPL": 60.0})
    try:
        prior = await _get_prior_scores(db)
    finally:
        await db.close()
    assert prior == {"AAPL": 60.0}

    asset = _make_analysis("AAPL")
    ranked = score_and_rank([asset], min_rr=3.0, top_n=5, prior_scores=prior)
    aapl = next(a for a in ranked if a.ticker == "AAPL")
    assert aapl.score_delta == round((aapl.score or 0) - 60.0, 2)


@pytest.mark.asyncio
async def test_score_delta_first_run():
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute(
        "CREATE TABLE analysis_results "
        "(id TEXT, run_id TEXT, ticker TEXT, score REAL, analyzed_at TEXT)"
    )
    await db.commit()
    try:
        prior = await _get_prior_scores(db)
    finally:
        await db.close()
    assert prior == {}

    asset = _make_analysis("AAPL")
    ranked = score_and_rank([asset], min_rr=3.0, top_n=5, prior_scores=prior)
    aapl = next(a for a in ranked if a.ticker == "AAPL")
    assert aapl.score_delta == 0.0


@pytest.mark.asyncio
async def test_score_delta_db_error():
    db = await aiosqlite.connect(":memory:")
    try:
        prior = await _get_prior_scores(db)
    finally:
        await db.close()
    assert prior == {}

    asset = _make_analysis("AAPL")
    ranked = score_and_rank([asset], min_rr=3.0, top_n=5, prior_scores=prior)
    aapl = next(a for a in ranked if a.ticker == "AAPL")
    assert aapl.score_delta == 0.0
