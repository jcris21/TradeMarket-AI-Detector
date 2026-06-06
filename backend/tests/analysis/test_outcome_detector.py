"""Tests for OutcomeDetector — atomic outcome resolution (NEX-19)."""

import math
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.db import connection as conn_module
from app.db.connection import get_connection
from app.db.repository import update_outcome_atomic
from app.analysis.outcome_detector import (
    OutcomeDetector,
    PerformanceSummary,
    OUTCOME_TARGET_HIT,
    OUTCOME_STOP_HIT,
    OUTCOME_EXPIRED,
    _determine_outcome,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _setup_db(tmp_path) -> str:
    path = str(tmp_path / "test.db")
    conn_module.set_db_path(path)
    await conn_module.init_db()
    # Clear seed analysis rows so tests start with a clean slate
    db = await get_connection()
    try:
        await db.execute("DELETE FROM analysis_results")
        await db.commit()
    finally:
        await db.close()
    return path


async def _insert_signal(
    signal_id: str | None = None,
    ticker: str = "AAPL",
    entry_price: float = 180.0,
    target_price: float = 200.0,
    stop_loss: float = 165.0,
    analyzed_at: str = "2024-01-01T00:00:00+00:00",
) -> str:
    sid = signal_id or str(uuid.uuid4())
    db = await get_connection()
    try:
        await db.execute(
            "INSERT INTO analysis_results "
            "(id, user_id, run_id, ticker, rank, score, signal, confidence, "
            "risk_reward_ratio, entry_price, target_price, stop_loss, "
            "support_validated, analyzed_at) "
            "VALUES (?, 'default', ?, ?, 1, 75.0, 'BUY', 0.8, 4.0, ?, ?, ?, 1, ?)",
            (sid, str(uuid.uuid4()), ticker, entry_price, target_price, stop_loss, analyzed_at),
        )
        await db.commit()
    finally:
        await db.close()
    return sid


# ── Unit tests: _determine_outcome ───────────────────────────────────────────


def test_determine_outcome_target_hit():
    outcome, gain_pct, loss_pct = _determine_outcome(
        max_high=205.0, min_low=175.0,
        entry_price=180.0, target_price=200.0, stop_loss=165.0,
    )
    assert outcome == OUTCOME_TARGET_HIT
    assert math.isfinite(gain_pct)
    assert math.isfinite(loss_pct)


def test_determine_outcome_stop_hit():
    outcome, gain_pct, loss_pct = _determine_outcome(
        max_high=185.0, min_low=160.0,
        entry_price=180.0, target_price=200.0, stop_loss=165.0,
    )
    assert outcome == OUTCOME_STOP_HIT
    assert math.isfinite(gain_pct)
    assert math.isfinite(loss_pct)


def test_determine_outcome_expired():
    outcome, gain_pct, loss_pct = _determine_outcome(
        max_high=190.0, min_low=175.0,
        entry_price=180.0, target_price=200.0, stop_loss=165.0,
    )
    assert outcome == OUTCOME_EXPIRED


def test_determine_outcome_both_hit_target_closer():
    # target is closer to entry than stop → TARGET_HIT
    outcome, _, _ = _determine_outcome(
        max_high=205.0, min_low=160.0,
        entry_price=180.0, target_price=185.0, stop_loss=165.0,
    )
    assert outcome == OUTCOME_TARGET_HIT


# ── Unit tests: update_outcome_atomic ────────────────────────────────────────


async def test_update_outcome_atomic_first_write_returns_true(tmp_path):
    await _setup_db(tmp_path)
    sid = await _insert_signal()

    written = await update_outcome_atomic(sid, OUTCOME_TARGET_HIT, 5.0, 2.0, 30.0)
    assert written is True


async def test_update_outcome_atomic_second_write_returns_false(tmp_path):
    await _setup_db(tmp_path)
    sid = await _insert_signal()

    first = await update_outcome_atomic(sid, OUTCOME_TARGET_HIT, 5.0, 2.0, 30.0)
    second = await update_outcome_atomic(sid, OUTCOME_STOP_HIT, 1.0, 3.0, 35.0)

    assert first is True
    assert second is False


async def test_update_outcome_atomic_preserves_first_write(tmp_path):
    await _setup_db(tmp_path)
    sid = await _insert_signal()

    await update_outcome_atomic(sid, OUTCOME_TARGET_HIT, 5.0, 2.0, 30.0)
    await update_outcome_atomic(sid, OUTCOME_STOP_HIT, 1.0, 3.0, 35.0)

    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT outcome, actual_gain_pct FROM analysis_results WHERE id = ?", (sid,)
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    assert row["outcome"] == OUTCOME_TARGET_HIT
    assert abs(row["actual_gain_pct"] - 5.0) < 1e-9


# ── Idempotency test ──────────────────────────────────────────────────────────


async def test_idempotency_two_runs_produce_identical_summary(tmp_path):
    """Running OutcomeDetector twice on the same dataset yields identical PerformanceSummary."""
    await _setup_db(tmp_path)
    await _insert_signal(ticker="AAPL", entry_price=180.0, target_price=200.0, stop_loss=165.0)
    await _insert_signal(ticker="MSFT", entry_price=400.0, target_price=440.0, stop_loss=375.0)

    # Mock price fetch: AAPL hits target, MSFT hits stop
    async def fake_fetch(ticker, since_dt):
        if ticker == "AAPL":
            return 210.0, 172.0, 30  # max_high > target → TARGET_HIT
        return 395.0, 368.0, 30      # min_low < stop → STOP_HIT

    detector = OutcomeDetector()

    with patch(
        "app.analysis.outcome_detector._fetch_price_range_since",
        side_effect=fake_fetch,
    ):
        summary1 = await detector.run()
        summary2 = await detector.run()

    assert summary1 == summary2
    assert summary1.total_signals == 2
    assert summary1.target_hits == 1
    assert summary1.stop_hits == 1


async def test_idempotency_no_duplicate_rows(tmp_path):
    """Two runs do not create duplicate outcome rows."""
    await _setup_db(tmp_path)
    sid = await _insert_signal()

    async def fake_fetch(ticker, since_dt):
        return 210.0, 172.0, 30

    detector = OutcomeDetector()
    with patch(
        "app.analysis.outcome_detector._fetch_price_range_since",
        side_effect=fake_fetch,
    ):
        await detector.run()
        await detector.run()

    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM analysis_results WHERE id = ? AND outcome IS NOT NULL",
            (sid,),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    assert row["cnt"] == 1


# ── Concurrency test ──────────────────────────────────────────────────────────


async def test_concurrency_one_writes_other_skips(tmp_path):
    """Two detector instances on the same signal: exactly one writes, one skips."""
    await _setup_db(tmp_path)
    sid = await _insert_signal()

    first = await update_outcome_atomic(sid, OUTCOME_TARGET_HIT, 5.0, 2.0, 30.0)
    second = await update_outcome_atomic(sid, OUTCOME_TARGET_HIT, 5.0, 2.0, 30.0)

    assert first is True
    assert second is False

    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM analysis_results WHERE id = ? AND outcome IS NOT NULL",
            (sid,),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    assert row["cnt"] == 1


# ── NaN guard test ────────────────────────────────────────────────────────────


async def test_nan_guard_skips_update_and_logs_warning(tmp_path, caplog):
    """When gain_pct is NaN, update_outcome_atomic is NOT called and a WARNING is logged."""
    await _setup_db(tmp_path)
    sid = await _insert_signal()

    import logging

    async def nan_fetch(ticker, since_dt):
        return float("nan"), float("nan"), 30

    detector = OutcomeDetector()
    with patch(
        "app.analysis.outcome_detector._fetch_price_range_since",
        side_effect=nan_fetch,
    ):
        with patch(
            "app.analysis.outcome_detector.update_outcome_atomic",
        ) as mock_update:
            with caplog.at_level(logging.WARNING, logger="app.analysis.outcome_detector"):
                await detector.run()

    mock_update.assert_not_called()
    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    assert any("not finite" in m or "No price data" in m for m in warning_msgs)


async def test_nan_guard_outcome_remains_null(tmp_path):
    """When gain_pct is NaN, the signal's outcome column stays NULL."""
    await _setup_db(tmp_path)
    sid = await _insert_signal()

    async def nan_fetch(ticker, since_dt):
        return float("nan"), float("nan"), 30

    detector = OutcomeDetector()
    with patch(
        "app.analysis.outcome_detector._fetch_price_range_since",
        side_effect=nan_fetch,
    ):
        await detector.run()

    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT outcome FROM analysis_results WHERE id = ?", (sid,)
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    assert row["outcome"] is None


# ── Idempotent skip logging ───────────────────────────────────────────────────


async def test_idempotent_skip_logged_at_info_not_warning(tmp_path, caplog):
    """rowcount == 0 (simulated race: another instance already wrote) logs at INFO not WARNING."""
    import logging

    await _setup_db(tmp_path)
    await _insert_signal()  # one unresolved signal

    async def fake_fetch(ticker, since_dt):
        return 210.0, 172.0, 30

    # Simulate the race: update_outcome_atomic returns False (another writer committed first)
    async def already_written(*args, **kwargs):
        return False

    detector = OutcomeDetector()
    with patch(
        "app.analysis.outcome_detector._fetch_price_range_since",
        side_effect=fake_fetch,
    ):
        with patch(
            "app.analysis.outcome_detector.update_outcome_atomic",
            side_effect=already_written,
        ):
            with caplog.at_level(logging.DEBUG, logger="app.analysis.outcome_detector"):
                await detector.run()

    info_msgs = [r.message for r in caplog.records if r.levelno == logging.INFO]
    warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
    error_msgs = [r.message for r in caplog.records if r.levelno == logging.ERROR]

    # The skip message must appear at INFO
    assert any("idempotent" in m or "already written" in m for m in info_msgs)
    # Must NOT appear at WARNING or ERROR
    assert not any("idempotent" in m or "already written" in m for m in warning_msgs)
    assert not any("idempotent" in m or "already written" in m for m in error_msgs)
