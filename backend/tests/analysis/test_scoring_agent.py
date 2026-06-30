"""Tests for ScoringAgent — filter, score, and rank assets."""

import aiosqlite
import pytest

from app.analysis.models import AssetAnalysis
from app.analysis.scoring_agent import (
    _compute_bet_size,
    _compute_score_quant,
    _get_hit_rate,
    _get_prior_scores,
    score_and_rank,
    score_and_rank_with_errors,
    validate_asset_analysis,
)


def _make_analysis(
    ticker: str,
    signal: str = "BUY",
    confidence: float = 0.8,
    rr_ratio: float = 4.0,
    support_validated: bool = True,
    macd: str = "bullish_crossover",
    rsi: float = 55.0,
    volume: str = "above_avg",
    entry_price: float = 100.0,
    target_price: float = 130.0,
    stop_loss: float = 90.0,
) -> AssetAnalysis:
    return AssetAnalysis(
        ticker=ticker,
        signal=signal,
        confidence=confidence,
        entry_price=entry_price,
        target_price=target_price,
        stop_loss=stop_loss,
        risk_reward_ratio=rr_ratio,
        support_validated=support_validated,
        indicators_summary={"macd": macd, "rsi": rsi, "volume": volume},
        argument="Test argument.",
    )


@pytest.mark.parametrize(
    "asset,expected_valid,expected_reason",
    [
        (_make_analysis("VALID"), True, ""),
        (_make_analysis("ENTRY", entry_price=0.0), False, "entry_price <= 0"),
        (
            _make_analysis("STOP", entry_price=100.0, stop_loss=100.0),
            False,
            "stop_loss >= entry_price (inverted stop)",
        ),
        (
            _make_analysis("TARGET", entry_price=100.0, target_price=100.0),
            False,
            "target_price <= entry_price (inverted target)",
        ),
        (_make_analysis("RR", rr_ratio=-1.0), False, "negative risk_reward_ratio"),
    ],
)
def test_validate_asset_analysis_guardrails(asset, expected_valid, expected_reason):
    valid, reason = validate_asset_analysis(asset)
    assert valid is expected_valid
    assert reason == expected_reason


@pytest.mark.parametrize(
    "asset,reason_fragment",
    [
        (_make_analysis("ENTRY", entry_price=0.0), "entry_price <= 0"),
        (_make_analysis("STOP", entry_price=100.0, stop_loss=101.0), "inverted stop"),
        (_make_analysis("TARGET", entry_price=100.0, target_price=99.0), "inverted target"),
        (_make_analysis("RR", rr_ratio=-0.1), "negative risk_reward_ratio"),
    ],
)
def test_structurally_invalid_assets_are_not_scored_or_ranked(asset, reason_fragment):
    ranked, errors, _ = score_and_rank_with_errors([asset], min_rr=3.0, top_n=5)

    assert len(ranked) == 1
    result = ranked[0]
    assert result.rank is None
    assert result.score is None
    assert result.score_delta is None
    assert result.expected_gain_per10 is None
    assert result.expected_loss_per10 is None
    assert result.expected_value_per10 is None
    assert errors == [
        {
            "ticker": asset.ticker,
            "error_message": f"structural_invalid: {validate_asset_analysis(asset)[1]}",
        }
    ]
    assert reason_fragment in errors[0]["error_message"]


def test_valid_asset_guardrail_regression_preserves_scoring_bet_size_and_delta():
    asset = _make_analysis("AAPL")

    ranked, errors, _ = score_and_rank_with_errors(
        [asset],
        hit_rate=0.35,
        hit_rate_source="assumed",
        prior_scores={"AAPL": 60.0},
        min_rr=3.0,
        top_n=5,
    )

    assert errors == []
    assert len(ranked) == 1
    result = ranked[0]
    assert result.rank == 1
    assert result.score is not None
    assert result.score_delta == round(result.score - 60.0, 2)
    assert result.expected_gain_per10 == 30.0
    assert result.expected_loss_per10 == 10.0
    assert result.expected_value_per10 is not None
    assert result.hit_rate_used == 0.35
    assert result.hit_rate_source == "assumed"


def test_structural_errors_are_reported_per_ticker():
    assets = [
        _make_analysis("BAD_STOP", stop_loss=100.0),
        _make_analysis("BAD_TARGET", target_price=100.0),
        _make_analysis("VALID"),
    ]

    ranked, errors, _ = score_and_rank_with_errors(assets, min_rr=3.0, top_n=5)

    assert {error["ticker"] for error in errors} == {"BAD_STOP", "BAD_TARGET"}
    assert all(error["error_message"].startswith("structural_invalid:") for error in errors)
    assert next(asset for asset in ranked if asset.ticker == "VALID").rank == 1


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
        (100.0, 130.0, 90.0, 30.0, 10.0),   # test_bet_size_rr_3
        (100.0, 120.0, 90.0, 20.0, 10.0),   # test_bet_size_rr_2
        (100.0, 160.0, 90.0, 60.0, 10.0),   # test_bet_size_rr_6
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


async def _db_with_outcomes(n_total: int, n_hits: int) -> aiosqlite.Connection:
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute(
        "CREATE TABLE analysis_results "
        "(id TEXT PRIMARY KEY, user_id TEXT, outcome TEXT)"
    )
    for i in range(n_total):
        outcome = "TARGET_HIT" if i < n_hits else "STOP_HIT"
        await db.execute(
            "INSERT INTO analysis_results VALUES (?, 'default', ?)", (str(i), outcome)
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
    assert source == "observed"


@pytest.mark.asyncio
async def test_get_hit_rate_fallback():
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
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
        "(id TEXT, run_id TEXT, ticker TEXT, score REAL, score_quant REAL, analyzed_at TEXT)"
    )
    for ticker, score in prior_ticker_scores.items():
        await db.execute(
            "INSERT INTO analysis_results VALUES (?, 'run-prior', ?, ?, ?, '2026-01-01T00:00:00')",
            (ticker, ticker, score, score),
        )
    # More recent "current" run so OFFSET 1 picks the prior run
    await db.execute(
        "INSERT INTO analysis_results VALUES ('x', 'run-current', 'DUMMY', 50.0, 50.0, '2026-01-02T00:00:00')"
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


# ── ATR viability tests (story-005) ──────────────────────────────────────────

def _make_atr_analysis(
    ticker: str,
    stop_distance_pct: float,
    atr_14_pct: float | None,
    rr_ratio: float = 4.0,
    confidence: float = 0.8,
) -> AssetAnalysis:
    """Build an AssetAnalysis with given stop_distance_pct and atr_14_pct."""
    entry = 100.0
    stop = round(entry * (1.0 - stop_distance_pct), 4)
    # Set target so RR = rr_ratio
    target = round(entry + rr_ratio * (entry - stop), 4)
    return AssetAnalysis(
        ticker=ticker,
        signal="BUY",
        confidence=confidence,
        entry_price=entry,
        target_price=target,
        stop_loss=stop,
        risk_reward_ratio=rr_ratio,
        support_validated=True,
        indicators_summary={"macd": "bullish_crossover", "rsi": 55.0, "volume": "above_avg"},
        argument="ATR test.",
        atr_14_pct=atr_14_pct,
    )


def test_atr_hard_disqualify():
    """stop_distance_pct < 0.5 * atr_14_pct → rank=None, error contains atr_disqualify:"""
    # stop_dist=0.03, atr=0.08 → 0.03 < 0.04 (hard floor)
    asset = _make_atr_analysis("HARD", stop_distance_pct=0.03, atr_14_pct=0.08)
    ranked, errors, _ = score_and_rank_with_errors([asset], min_rr=3.0, top_n=5)

    assert len(ranked) == 1
    result = ranked[0]
    assert result.rank is None
    assert result.stop_viable is False
    assert any("atr_disqualify:" in e["error_message"] for e in errors)
    assert errors[0]["ticker"] == "HARD"


def test_atr_soft_penalty():
    """stop_distance_pct in soft-penalty band → stop_viable=False, score 15 pts below baseline"""
    # stop_dist=0.05, atr=0.08 → 0.05 in [0.04, 0.064) → soft penalty -15 pts
    asset = _make_atr_analysis("SOFT", stop_distance_pct=0.05, atr_14_pct=0.08, rr_ratio=4.0)
    baseline_asset = _make_atr_analysis("BASE", stop_distance_pct=0.05, atr_14_pct=None, rr_ratio=4.0)

    ranked_soft, _, _ = score_and_rank_with_errors([asset], min_rr=3.0, top_n=5)
    ranked_base, _, _ = score_and_rank_with_errors([baseline_asset], min_rr=3.0, top_n=5)

    soft_score = next(a.score for a in ranked_soft if a.ticker == "SOFT")
    base_score = next(a.score for a in ranked_base if a.ticker == "BASE")

    assert soft_score is not None
    assert base_score is not None
    assert abs((base_score - soft_score) - 15.0) < 0.01
    soft_result = next(a for a in ranked_soft if a.ticker == "SOFT")
    assert soft_result.stop_viable is False


def test_atr_neutral_band():
    """stop_distance_pct in neutral band → stop_viable=True, score unchanged"""
    # stop_dist=0.08, atr=0.08 → 0.08 in [0.064, 0.12] → neutral
    asset = _make_atr_analysis("NEUTRAL", stop_distance_pct=0.08, atr_14_pct=0.08, rr_ratio=4.0)
    baseline_asset = _make_atr_analysis("BASE", stop_distance_pct=0.08, atr_14_pct=None, rr_ratio=4.0)

    ranked_neutral, _, _ = score_and_rank_with_errors([asset], min_rr=3.0, top_n=5)
    ranked_base, _, _ = score_and_rank_with_errors([baseline_asset], min_rr=3.0, top_n=5)

    neutral_score = next(a.score for a in ranked_neutral if a.ticker == "NEUTRAL")
    base_score = next(a.score for a in ranked_base if a.ticker == "BASE")

    assert neutral_score == base_score
    neutral_result = next(a for a in ranked_neutral if a.ticker == "NEUTRAL")
    assert neutral_result.stop_viable is True


def test_atr_boost():
    """stop_distance_pct > 1.5 * atr_14_pct → stop_viable=True, score 8 pts above baseline"""
    # stop_dist=0.15, atr=0.08 → 0.15 > 0.12 → boost +8 pts
    asset = _make_atr_analysis("BOOST", stop_distance_pct=0.15, atr_14_pct=0.08, rr_ratio=4.0)
    baseline_asset = _make_atr_analysis("BASE", stop_distance_pct=0.15, atr_14_pct=None, rr_ratio=4.0)

    ranked_boost, _, _ = score_and_rank_with_errors([asset], min_rr=3.0, top_n=5)
    ranked_base, _, _ = score_and_rank_with_errors([baseline_asset], min_rr=3.0, top_n=5)

    boost_score = next(a.score for a in ranked_boost if a.ticker == "BOOST")
    base_score = next(a.score for a in ranked_base if a.ticker == "BASE")

    assert boost_score is not None
    assert base_score is not None
    assert abs((boost_score - base_score) - 8.0) < 0.01
    boost_result = next(a for a in ranked_boost if a.ticker == "BOOST")
    assert boost_result.stop_viable is True


def test_atr_none_fallback():
    """Asset with atr_14_pct=None passes scoring unchanged with stop_viable=None."""
    asset = _make_atr_analysis("NOATR", stop_distance_pct=0.10, atr_14_pct=None, rr_ratio=4.0)

    ranked, errors, _ = score_and_rank_with_errors([asset], min_rr=3.0, top_n=5)
    result = next(a for a in ranked if a.ticker == "NOATR")

    # No ATR errors
    atr_errors = [e for e in errors if "atr_disqualify" in e.get("error_message", "")]
    assert atr_errors == []

    # stop_viable should be None (ATR data unavailable)
    assert result.stop_viable is None

    # score == score_quant with no ATR adjustment
    baseline_score = _compute_score_quant(asset, atr_viability_pts=0.0)
    assert result.score == baseline_score
    assert result.score_quant == baseline_score


def test_atr_regression_rank_order_preserved():
    """Signals with ATR-neutral stop distances maintain rank order from pre-feature baseline."""
    # These signals all have stop_distance_pct in the neutral band (no ATR adjustment).
    # Rank order should follow score formula as before.
    assets = [
        _make_atr_analysis("HIGH", stop_distance_pct=0.10, atr_14_pct=0.08,
                            confidence=0.9, rr_ratio=5.0),
        _make_atr_analysis("MID", stop_distance_pct=0.10, atr_14_pct=0.08,
                            confidence=0.7, rr_ratio=4.0),
        _make_atr_analysis("LOW", stop_distance_pct=0.10, atr_14_pct=0.08,
                            confidence=0.5, rr_ratio=3.0),
    ]

    ranked, errors, _ = score_and_rank_with_errors(assets, min_rr=3.0, top_n=5)
    atr_errors = [e for e in errors if "atr_disqualify" in e.get("error_message", "")]
    assert atr_errors == []

    qualifiers = [a for a in ranked if a.rank is not None]
    assert len(qualifiers) == 3
    assert qualifiers[0].ticker == "HIGH"
    assert qualifiers[1].ticker == "MID"
    assert qualifiers[2].ticker == "LOW"


# ── US-301: Two-Layer Score Architecture tests ────────────────────────────────

def _make_quant_analysis(
    ticker: str = "T",
    rr: float = 4.0,
    macd: str = "bullish_crossover",
    rsi: float = 55.0,
    volume: str = "above_avg",
    support_validated: bool = True,
    sma_50: float | None = None,
    bb_bandwidth: float | None = None,
    support_1: float | None = None,
    resistance_1: float | None = None,
    entry_price: float = 100.0,
    atr_14_pct: float | None = None,
) -> AssetAnalysis:
    """Build an AssetAnalysis with all quant scoring fields in indicators_summary."""
    summary: dict = {"macd": macd, "rsi": rsi, "volume": volume}
    if sma_50 is not None:
        summary["sma_50"] = sma_50
    if bb_bandwidth is not None:
        summary["bb_bandwidth"] = bb_bandwidth
    if support_1 is not None:
        summary["support_1"] = support_1
    if resistance_1 is not None:
        summary["resistance_1"] = resistance_1
    return AssetAnalysis(
        ticker=ticker,
        signal="BUY",
        confidence=0.8,
        entry_price=entry_price,
        target_price=entry_price + rr * 10,
        stop_loss=entry_price - 10,
        risk_reward_ratio=rr,
        support_validated=support_validated,
        indicators_summary=summary,
        argument="quant test",
        atr_14_pct=atr_14_pct,
    )


@pytest.mark.parametrize(
    "rr,expected_pts",
    [(1.5, 0.0), (2.0, 14.0), (3.0, 22.0), (4.0, 30.0), (5.0, 30.0)],
    ids=["below_2", "at_2", "at_3", "at_4", "above_4"],
)
def test_score_quant_rr_thresholds(rr, expected_pts):
    """RR component isolation: compare each rr against a rr=1.0 baseline (0 rr_pts)."""
    # All other inputs identical → difference is purely the RR component
    base = _make_quant_analysis(rr=1.0, macd="neutral", rsi=55.0, volume="below_avg",
                                 support_validated=False)
    asset = _make_quant_analysis(rr=rr, macd="neutral", rsi=55.0, volume="below_avg",
                                  support_validated=False)
    sq_base = _compute_score_quant(base, atr_viability_pts=0.0)
    sq = _compute_score_quant(asset, atr_viability_pts=0.0)
    assert round(sq - sq_base, 2) == expected_pts


def test_score_quant_trend_above_sma50_and_bullish_macd():
    asset = _make_quant_analysis(entry_price=120.0, sma_50=100.0, macd="bullish_crossover")
    sq = _compute_score_quant(asset, atr_viability_pts=0.0)
    # trend_pts should be 10 (above SMA-50 AND bullish MACD)
    asset_no_sma = _make_quant_analysis(entry_price=120.0, sma_50=None, macd="bullish_crossover")
    sq_no_sma = _compute_score_quant(asset_no_sma, atr_viability_pts=0.0)
    assert sq - sq_no_sma == 4.0  # 10 - 6 = 4 pts difference


def test_score_quant_bb_squeeze_adds_8_pts():
    with_squeeze = _make_quant_analysis(bb_bandwidth=5.0)
    without_squeeze = _make_quant_analysis(bb_bandwidth=None)
    sq_with = _compute_score_quant(with_squeeze, atr_viability_pts=0.0)
    sq_without = _compute_score_quant(without_squeeze, atr_viability_pts=0.0)
    assert sq_with - sq_without == 8.0


def test_score_quant_bb_no_squeeze_above_threshold():
    no_squeeze = _make_quant_analysis(bb_bandwidth=15.0)
    sq = _compute_score_quant(no_squeeze, atr_viability_pts=0.0)
    base = _make_quant_analysis(bb_bandwidth=None)
    sq_base = _compute_score_quant(base, atr_viability_pts=0.0)
    assert sq == sq_base  # no bonus


def test_score_quant_support_proximity_10pts_when_close():
    # price=100, support_1=98 → proximity=(100-98)/100=2% < 3% → 10 pts
    close = _make_quant_analysis(entry_price=100.0, support_1=98.0, support_validated=True)
    far = _make_quant_analysis(entry_price=100.0, support_1=90.0, support_validated=True)
    sq_close = _compute_score_quant(close, atr_viability_pts=0.0)
    sq_far = _compute_score_quant(far, atr_viability_pts=0.0)
    assert sq_close - sq_far == 5.0  # 10 - 5 = 5 pts difference


def test_score_quant_regime_overbought_penalty():
    # Overbought (rsi>70) always scores less than neutral (rsi=55) — delta includes
    # both the -10 regime penalty AND the loss of confluence (rsi=75 outside [40,65]).
    overbought = _make_quant_analysis(rsi=75.0)
    neutral = _make_quant_analysis(rsi=55.0)
    sq_ob = _compute_score_quant(overbought, atr_viability_pts=0.0)
    sq_n = _compute_score_quant(neutral, atr_viability_pts=0.0)
    assert sq_n > sq_ob  # overbought always scores lower

    # Isolate just the regime penalty: compare two RSI values both outside [40,65]
    # rsi=80 → regime=-10; rsi=67 → regime=-5; neither contributes to confluence
    rsi80 = _make_quant_analysis(rsi=80.0)
    rsi67 = _make_quant_analysis(rsi=67.0)
    sq80 = _compute_score_quant(rsi80, atr_viability_pts=0.0)
    sq67 = _compute_score_quant(rsi67, atr_viability_pts=0.0)
    assert sq67 - sq80 == 5.0  # pure regime diff: -5 vs -10


def test_score_quant_and_legacy_both_populated():
    asset = _make_quant_analysis()
    ranked, _, _ = score_and_rank_with_errors([asset], min_rr=3.0, top_n=5)
    result = ranked[0]
    assert result.score_quant is not None
    assert result.score_legacy is not None
    assert result.score == result.score_quant  # backward compat


def test_score_enriched_computed_from_score_quant_plus_delta():
    asset = _make_quant_analysis()
    ranked, _, _ = score_and_rank_with_errors([asset], min_rr=3.0, top_n=5)
    result = ranked[0]
    # Without enrichment_delta, score_enriched is None
    assert result.enrichment_delta is None
    enriched = result.model_copy(update={"enrichment_delta": 10.0})
    assert enriched.score_enriched == round((enriched.score_quant or 0) + 10.0, 2)


# ── US-202: Sector cap enforcement tests ──────────────────────────────────────

def _make_sector_analysis(
    ticker: str,
    sector: str | None,
    rr_ratio: float = 4.0,
    confidence: float = 0.8,
) -> AssetAnalysis:
    """Build a qualifying AssetAnalysis with a given sector."""
    asset = _make_analysis(ticker, rr_ratio=rr_ratio, confidence=confidence)
    return asset.model_copy(update={"sector": sector})


def test_sector_cap_limits_per_sector_to_cap(monkeypatch):
    monkeypatch.setenv("ANALYSIS_SECTOR_CAP", "2")
    assets = [_make_sector_analysis(f"T{i}", "Technology") for i in range(5)]
    ranked, _errors, _excl = score_and_rank_with_errors(assets, min_rr=3.0, top_n=20)

    accepted = [a for a in ranked if a.rank is not None]
    excluded = [a for a in ranked if a.rank is None]
    assert len(accepted) == 2
    assert len(excluded) == 3
    assert all(a.rank_exclusion_reason == "sector_cap:Technology" for a in excluded)


def test_sector_cap_unknown_bypasses_cap(monkeypatch):
    monkeypatch.setenv("ANALYSIS_SECTOR_CAP", "2")
    assets = [_make_sector_analysis(f"U{i}", "unknown") for i in range(5)]
    ranked, _errors, _excl = score_and_rank_with_errors(assets, min_rr=3.0, top_n=20)

    accepted = [a for a in ranked if a.rank is not None]
    assert len(accepted) == 5


def test_sector_cap_etf_bypasses_cap(monkeypatch):
    monkeypatch.setenv("ANALYSIS_SECTOR_CAP", "2")
    assets = [_make_sector_analysis(f"E{i}", "etf") for i in range(3)]
    ranked, _errors, _excl = score_and_rank_with_errors(assets, min_rr=3.0, top_n=20)

    accepted = [a for a in ranked if a.rank is not None]
    assert len(accepted) == 3


def test_sector_cap_mixed_sectors(monkeypatch):
    monkeypatch.setenv("ANALYSIS_SECTOR_CAP", "2")
    assets = (
        [_make_sector_analysis(f"TECH{i}", "Technology") for i in range(3)]
        + [_make_sector_analysis(f"FIN{i}", "Financials") for i in range(2)]
        + [_make_sector_analysis("ENRG0", "Energy")]
    )
    ranked, _errors, _excl = score_and_rank_with_errors(assets, min_rr=3.0, top_n=20)

    accepted = [a for a in ranked if a.rank is not None]
    excluded = [a for a in ranked if a.rank is None]
    assert len(accepted) == 5  # 2 Tech + 2 Fin + 1 Energy
    assert len(excluded) == 1  # 1 Tech dropped
    assert excluded[0].rank_exclusion_reason == "sector_cap:Technology"


def test_sector_cap_exclusions_counted_in_result(monkeypatch):
    monkeypatch.setenv("ANALYSIS_SECTOR_CAP", "2")
    assets = (
        [_make_sector_analysis(f"TECH{i}", "Technology") for i in range(5)]
        + [_make_sector_analysis(f"FIN{i}", "Financials") for i in range(4)]
    )
    _ranked, _errors, exclusions = score_and_rank_with_errors(assets, min_rr=3.0, top_n=20)

    assert exclusions == {"Technology": 3, "Financials": 2}


def test_sector_cap_respects_score_order(monkeypatch):
    monkeypatch.setenv("ANALYSIS_SECTOR_CAP", "1")
    high = _make_sector_analysis("HIGH", "Technology", confidence=0.9, rr_ratio=5.0)
    low = _make_sector_analysis("LOW", "Technology", confidence=0.5, rr_ratio=3.0)
    ranked, _errors, _excl = score_and_rank_with_errors([low, high], min_rr=3.0, top_n=20)

    accepted = [a for a in ranked if a.rank is not None]
    excluded = [a for a in ranked if a.rank is None]
    assert len(accepted) == 1
    assert accepted[0].ticker == "HIGH"
    assert excluded[0].ticker == "LOW"


def test_sector_cap_env_clamping(monkeypatch):
    # cap=0 → clamped to 1
    monkeypatch.setenv("ANALYSIS_SECTOR_CAP", "0")
    assets = [_make_sector_analysis(f"T{i}", "Technology") for i in range(3)]
    ranked, _e, _x = score_and_rank_with_errors(assets, min_rr=3.0, top_n=20)
    assert len([a for a in ranked if a.rank is not None]) == 1

    # cap=10 → clamped to 5
    monkeypatch.setenv("ANALYSIS_SECTOR_CAP", "10")
    assets = [_make_sector_analysis(f"T{i}", "Technology") for i in range(7)]
    ranked, _e, _x = score_and_rank_with_errors(assets, min_rr=3.0, top_n=20)
    assert len([a for a in ranked if a.rank is not None]) == 5


def test_sector_cap_default_is_2(monkeypatch):
    monkeypatch.delenv("ANALYSIS_SECTOR_CAP", raising=False)
    assets = [_make_sector_analysis(f"T{i}", "Technology") for i in range(5)]
    ranked, _errors, _excl = score_and_rank_with_errors(assets, min_rr=3.0, top_n=20)
    assert len([a for a in ranked if a.rank is not None]) == 2


def test_sector_cap_rank_exclusion_reason_format(monkeypatch):
    monkeypatch.setenv("ANALYSIS_SECTOR_CAP", "1")
    assets = [_make_sector_analysis(f"T{i}", "Technology") for i in range(2)]
    ranked, _errors, _excl = score_and_rank_with_errors(assets, min_rr=3.0, top_n=20)

    excluded = [a for a in ranked if a.rank is None]
    assert excluded[0].rank_exclusion_reason == "sector_cap:Technology"


def test_existing_top_n_still_applied_after_sector_cap(monkeypatch):
    monkeypatch.setenv("ANALYSIS_SECTOR_CAP", "5")
    # 6 distinct sectors so the cap never bites; top_n=5 must limit accepted to 5
    sectors = ["Technology", "Financials", "Energy", "Healthcare", "Industrials", "Materials"]
    assets = [_make_sector_analysis(f"S{i}", sec) for i, sec in enumerate(sectors)]
    ranked, _errors, _excl = score_and_rank_with_errors(assets, min_rr=3.0, top_n=5)

    assert len([a for a in ranked if a.rank is not None]) == 5


# ── US-401: ANALYSIS_TOP_N=20 default and top_5 alias (task 8.2) ──────────────

def test_analysis_top_n_default_returns_up_to_20(monkeypatch):
    """ANALYSIS_TOP_N default=20: scoring returns up to 20 results."""
    monkeypatch.delenv("ANALYSIS_TOP_N", raising=False)
    # Create 25 qualifying assets
    assets = [_make_analysis(f"T{i}", rr_ratio=3.0 + (i % 5) * 0.1) for i in range(25)]
    ranked, _errors, _excl = score_and_rank_with_errors(assets, min_rr=3.0)
    qualifiers = [a for a in ranked if a.rank is not None]
    assert len(qualifiers) == 20


def test_analysis_top_n_clamp_above_20(monkeypatch):
    """ANALYSIS_TOP_N=50 is clamped to 20."""
    monkeypatch.setenv("ANALYSIS_TOP_N", "50")
    assets = [_make_analysis(f"T{i}", rr_ratio=3.0) for i in range(25)]
    ranked, _errors, _excl = score_and_rank_with_errors(assets, min_rr=3.0)
    qualifiers = [a for a in ranked if a.rank is not None]
    assert len(qualifiers) == 20


def test_analysis_top_n_clamp_below_5(monkeypatch):
    """ANALYSIS_TOP_N=2 is clamped to 5."""
    monkeypatch.setenv("ANALYSIS_TOP_N", "2")
    assets = [_make_analysis(f"T{i}", rr_ratio=3.0) for i in range(10)]
    ranked, _errors, _excl = score_and_rank_with_errors(assets, min_rr=3.0)
    qualifiers = [a for a in ranked if a.rank is not None]
    assert len(qualifiers) == 5


# ── US-404: get_prior_scores in repository (task 8.1) ─────────────────────────

@pytest.mark.asyncio
async def test_repository_get_prior_scores_returns_correct_dict():
    """get_prior_scores() returns {ticker: score_quant} for known prior run."""
    import aiosqlite
    from app.db.repository import get_prior_scores
    from unittest.mock import patch

    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute(
        "CREATE TABLE analysis_results "
        "(id TEXT, user_id TEXT, run_id TEXT, ticker TEXT, score_quant REAL, analyzed_at TEXT)"
    )
    # Prior run (older timestamp)
    await db.execute(
        "INSERT INTO analysis_results VALUES ('1', 'default', 'run-prior', 'AAPL', 65.0, '2026-01-01T10:00:00')"
    )
    await db.execute(
        "INSERT INTO analysis_results VALUES ('2', 'default', 'run-prior', 'MSFT', 72.0, '2026-01-01T10:00:00')"
    )
    # Current run (newer timestamp)
    await db.execute(
        "INSERT INTO analysis_results VALUES ('3', 'default', 'run-current', 'AAPL', 70.0, '2026-01-02T10:00:00')"
    )
    await db.commit()

    # Patch get_connection to return our in-memory db
    async def _get_conn():
        return db

    with patch("app.db.repository.get_connection", _get_conn):
        result = await get_prior_scores("run-current")

    await db.close()
    assert result == {"AAPL": 65.0, "MSFT": 72.0}


@pytest.mark.asyncio
async def test_repository_get_prior_scores_returns_empty_when_no_prior():
    """get_prior_scores() returns {} when no prior run exists."""
    import aiosqlite
    from app.db.repository import get_prior_scores
    from unittest.mock import patch

    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute(
        "CREATE TABLE analysis_results "
        "(id TEXT, user_id TEXT, run_id TEXT, ticker TEXT, score_quant REAL, analyzed_at TEXT)"
    )
    # Only one run — no prior
    await db.execute(
        "INSERT INTO analysis_results VALUES ('1', 'default', 'run-only', 'AAPL', 65.0, '2026-01-01T10:00:00')"
    )
    await db.commit()

    async def _get_conn():
        return db

    with patch("app.db.repository.get_connection", _get_conn):
        result = await get_prior_scores("run-only")

    await db.close()
    assert result == {}

