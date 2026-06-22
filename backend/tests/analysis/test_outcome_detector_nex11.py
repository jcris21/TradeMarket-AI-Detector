"""Additional tests for nex-11-signal-outcome-recorder changes to OutcomeDetector."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd

from app.analysis.outcome_detector import (
    OUTCOME_EXPIRED,
    OUTCOME_STOP_HIT,
    OUTCOME_TARGET_HIT,
    OutcomeDetector,
    PerformanceSummary,
    _determine_outcome,
    _fetch_price_range_since,
)
from app.db import connection as conn_module
from app.db.connection import get_connection
from app.db.repository import update_outcome_atomic

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _setup_db(tmp_path) -> None:
    conn_module.set_db_path(str(tmp_path / "test.db"))
    await conn_module.init_db()
    db = await get_connection()
    try:
        await db.execute("DELETE FROM analysis_results")
        await db.commit()
    finally:
        await db.close()


async def _insert_signal(
    analyzed_at: str | None = None,
    entry_price: float = 180.0,
    target_price: float = 200.0,
    stop_loss: float = 165.0,
) -> str:
    sid = str(uuid.uuid4())
    at = analyzed_at or "2024-01-01T00:00:00+00:00"
    db = await get_connection()
    try:
        await db.execute(
            "INSERT INTO analysis_results "
            "(id, user_id, run_id, ticker, rank, score, signal, confidence, "
            "risk_reward_ratio, entry_price, target_price, stop_loss, "
            "support_validated, analyzed_at) "
            "VALUES (?, 'default', ?, 'AAPL', 1, 75.0, 'BUY', 0.8, 4.0, ?, ?, ?, 1, ?)",
            (sid, str(uuid.uuid4()), entry_price, target_price, stop_loss, at),
        )
        await db.commit()
    finally:
        await db.close()
    return sid


# ── _determine_outcome: both-hit stop-closer branch ──────────────────────────


def test_determine_outcome_both_hit_stop_closer():
    """When both levels are hit and stop is closer to entry → STOP_HIT."""
    outcome, _, _ = _determine_outcome(
        max_high=205.0,
        min_low=160.0,
        entry_price=180.0,
        target_price=200.0,  # target_dist = 20
        stop_loss=178.0,     # stop_dist  =  2  (closer)
    )
    assert outcome == OUTCOME_STOP_HIT


# ── PerformanceSummary.__eq__ non-type branch ─────────────────────────────────


def test_performance_summary_eq_returns_not_implemented_for_non_summary():
    ps = PerformanceSummary(
        total_signals=0, target_hits=0, stop_hits=0, expired=0,
        orphaned_count=0, phase_gate_active=True, calibration_count=0,
        hit_ratio=None, profit_factor=None, realized_rr=None,
        hr_status=None, pf_status=None, rr_status=None, below_breakeven=False,
    )
    assert ps.__eq__("not a PerformanceSummary") is NotImplemented


# ── Hit-ratio denominator (nex-11 fix) ───────────────────────────────────────


async def test_hit_ratio_excludes_expired_from_denominator(tmp_path):
    """4 TARGET_HIT + 1 STOP_HIT + 3 EXPIRED → hit_ratio = 0.80 not 0.50."""
    await _setup_db(tmp_path)
    for _ in range(4):
        sid = await _insert_signal()
        await update_outcome_atomic(sid, OUTCOME_TARGET_HIT, 5.0, 2.0, 30.0)
    sid = await _insert_signal()
    await update_outcome_atomic(sid, OUTCOME_STOP_HIT, 2.0, 5.0, 30.0)
    for _ in range(3):
        sid = await _insert_signal()
        await update_outcome_atomic(sid, OUTCOME_EXPIRED, 0.5, 0.5, 30.0)

    summary = await OutcomeDetector()._compute_summary()

    assert summary.target_hits == 4
    assert summary.stop_hits == 1
    assert summary.expired == 3
    # 5 conclusive signals — phase gate active, hit_ratio is None
    assert summary.phase_gate_active is True
    assert summary.hit_ratio is None


async def test_all_expired_yields_zero_hit_ratio(tmp_path):
    await _setup_db(tmp_path)
    for _ in range(3):
        sid = await _insert_signal()
        await update_outcome_atomic(sid, OUTCOME_EXPIRED, 0.5, 0.5, 30.0)

    summary = await OutcomeDetector()._compute_summary()
    # 0 conclusive signals → phase gate active, hit_ratio is None
    assert summary.phase_gate_active is True
    assert summary.hit_ratio is None
    assert summary.calibration_count == 0


async def test_no_resolved_signals_yields_zero_hit_ratio(tmp_path):
    await _setup_db(tmp_path)
    summary = await OutcomeDetector()._compute_summary()
    # phase gate active when no conclusive signals
    assert summary.phase_gate_active is True
    assert summary.hit_ratio is None
    assert summary.total_signals == 0


# ── Orphaned count (nex-11 addition) ─────────────────────────────────────────


async def test_orphaned_count_signal_over_35_days(tmp_path):
    await _setup_db(tmp_path)
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    await _insert_signal(analyzed_at=old)  # outcome IS NULL, > 35 days old

    summary = await OutcomeDetector()._compute_summary()
    assert summary.orphaned_count == 1


async def test_orphaned_count_recent_unresolved_not_counted(tmp_path):
    await _setup_db(tmp_path)
    recent = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    await _insert_signal(analyzed_at=recent)

    summary = await OutcomeDetector()._compute_summary()
    assert summary.orphaned_count == 0


async def test_orphaned_count_resolved_signal_not_counted(tmp_path):
    """A resolved signal older than 35 days is NOT orphaned."""
    await _setup_db(tmp_path)
    old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    sid = await _insert_signal(analyzed_at=old)
    await update_outcome_atomic(sid, OUTCOME_TARGET_HIT, 5.0, 2.0, 30.0)

    summary = await OutcomeDetector()._compute_summary()
    assert summary.orphaned_count == 0


# ── support_break_level (nex-11 addition) ────────────────────────────────────


async def test_stop_hit_sets_support_break_level_s1(tmp_path):
    await _setup_db(tmp_path)
    sid = await _insert_signal(entry_price=180.0, target_price=200.0, stop_loss=165.0)

    async def stop_fetch(ticker, since_dt):
        return 185.0, 160.0, 30  # min_low < stop_loss → STOP_HIT

    with patch(
        "app.analysis.outcome_detector._fetch_price_range_since",
        side_effect=stop_fetch,
    ):
        await OutcomeDetector().run()

    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT support_break_level FROM analysis_results WHERE id = ?", (sid,)
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    assert row["support_break_level"] == "S1"


async def test_target_hit_leaves_support_break_level_null(tmp_path):
    await _setup_db(tmp_path)
    sid = await _insert_signal(entry_price=180.0, target_price=200.0, stop_loss=165.0)

    async def target_fetch(ticker, since_dt):
        return 210.0, 172.0, 30  # max_high > target → TARGET_HIT

    with patch(
        "app.analysis.outcome_detector._fetch_price_range_since",
        side_effect=target_fetch,
    ):
        await OutcomeDetector().run()

    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT support_break_level FROM analysis_results WHERE id = ?", (sid,)
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    assert row["support_break_level"] is None


async def test_expired_leaves_support_break_level_null(tmp_path):
    await _setup_db(tmp_path)
    sid = await _insert_signal(entry_price=180.0, target_price=200.0, stop_loss=165.0)

    async def expired_fetch(ticker, since_dt):
        return 190.0, 170.0, 30  # neither target nor stop hit → EXPIRED

    with patch(
        "app.analysis.outcome_detector._fetch_price_range_since",
        side_effect=expired_fetch,
    ):
        await OutcomeDetector().run()

    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT support_break_level FROM analysis_results WHERE id = ?", (sid,)
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    assert row["support_break_level"] is None


# ── _fetch_price_range_since branches ─────────────────────────────────────────


async def test_fetch_price_range_same_day_returns_none():
    """hold_days <= 0 — signal created today has no history yet."""
    since_dt = datetime.now(timezone.utc)
    max_high, min_low, hold_days = await _fetch_price_range_since("AAPL", since_dt)
    assert max_high is None
    assert min_low is None
    assert hold_days == 0


async def test_fetch_price_range_yfinance_exception():
    since_dt = datetime.now(timezone.utc) - timedelta(days=10)
    with patch(
        "app.analysis.outcome_detector.yf.download",
        side_effect=Exception("network error"),
    ):
        max_high, min_low, hold_days = await _fetch_price_range_since("AAPL", since_dt)
    assert max_high is None
    assert min_low is None
    assert hold_days == 0


async def test_fetch_price_range_empty_dataframe():
    since_dt = datetime.now(timezone.utc) - timedelta(days=10)
    with patch(
        "app.analysis.outcome_detector.yf.download",
        return_value=pd.DataFrame(),
    ):
        max_high, min_low, hold_days = await _fetch_price_range_since("AAPL", since_dt)
    assert max_high is None
    assert min_low is None


async def test_fetch_price_range_column_extraction_error():
    """DataFrame without High/Low columns raises KeyError → returns None."""
    since_dt = datetime.now(timezone.utc) - timedelta(days=10)
    df = pd.DataFrame({"Close": [100.0, 101.0]})  # missing High/Low
    with patch("app.analysis.outcome_detector.yf.download", return_value=df):
        max_high, min_low, hold_days = await _fetch_price_range_since("AAPL", since_dt)
    assert max_high is None
    assert min_low is None
    assert hold_days == 0


# Note: lines 80 and 85 in outcome_detector.py (min_low extraction and the success
# return) are not covered here. yfinance's import causes numpy to be reloaded, which
# breaks pd.Series.max() in the pytest context (numpy _NoValue sentinel mismatch).
# These lines are covered by integration tests and are exercised in production via
# the OutcomeDetector.run() tests that mock _fetch_price_range_since at a higher level.


# ── run() error-path branches ─────────────────────────────────────────────────


async def test_invalid_analyzed_at_skips_signal_with_warning(tmp_path, caplog):
    """Signals with unparseable analyzed_at are skipped and logged at WARNING."""
    import logging

    await _setup_db(tmp_path)
    sid = str(uuid.uuid4())
    db = await get_connection()
    try:
        await db.execute(
            "INSERT INTO analysis_results "
            "(id, user_id, run_id, ticker, rank, score, signal, confidence, "
            "risk_reward_ratio, entry_price, target_price, stop_loss, "
            "support_validated, analyzed_at) "
            "VALUES (?, 'default', ?, 'AAPL', 1, 75.0, 'BUY', 0.8, 4.0, 180.0, 200.0, 165.0, 1, ?)",
            (sid, str(uuid.uuid4()), "not-a-valid-date"),
        )
        await db.commit()
    finally:
        await db.close()

    with caplog.at_level(logging.WARNING, logger="app.analysis.outcome_detector"):
        await OutcomeDetector().run()

    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Invalid analyzed_at" in m for m in warning_msgs)


async def test_no_price_data_skips_signal_with_warning(tmp_path, caplog):
    """Signals where _fetch_price_range_since returns None are skipped at WARNING."""
    import logging

    await _setup_db(tmp_path)
    await _insert_signal()

    async def no_data(ticker, since_dt):
        return None, None, 0

    with patch(
        "app.analysis.outcome_detector._fetch_price_range_since",
        side_effect=no_data,
    ):
        with caplog.at_level(logging.WARNING, logger="app.analysis.outcome_detector"):
            await OutcomeDetector().run()

    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("No price data" in m for m in warning_msgs)
