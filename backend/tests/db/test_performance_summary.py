"""Tests for get_performance_summary and update_outcome_atomic with support_break_level."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db import init_db, set_db_path
from app.db.connection import get_connection
from app.db.repository import _compute_phase, get_performance_summary, update_outcome_atomic


@pytest.fixture(autouse=True)
async def temp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    set_db_path(db_path)
    await init_db()
    db = await get_connection()
    try:
        await db.execute("DELETE FROM analysis_results")
        await db.commit()
    finally:
        await db.close()
    yield db_path
    set_db_path(db_path)


async def _insert_signal(
    analyzed_at: str | None = None,
    entry_price: float = 180.0,
    target_price: float = 200.0,
    stop_loss: float = 165.0,
) -> str:
    sid = str(uuid.uuid4())
    at = analyzed_at or datetime.now(timezone.utc).isoformat()
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


class TestGetPerformanceSummary:
    async def test_empty_db_returns_zeros(self):
        result = await get_performance_summary()
        assert result["total_signals"] == 0
        assert result["target_hits"] == 0
        assert result["stop_hits"] == 0
        assert result["expired"] == 0
        assert result["orphaned_count"] == 0
        assert result["phase_gate_active"] is True
        assert result["calibration_count"] == 0
        assert result["hit_ratio"] is None
        assert result["profit_factor"] is None

    async def test_correct_outcome_counts(self):
        for _ in range(3):
            sid = await _insert_signal()
            await update_outcome_atomic(sid, "TARGET_HIT", 5.0, 2.0, 30.0)
        sid = await _insert_signal()
        await update_outcome_atomic(sid, "STOP_HIT", 2.0, 5.0, 30.0)
        for _ in range(2):
            sid = await _insert_signal()
            await update_outcome_atomic(sid, "EXPIRED", 0.5, 0.5, 30.0)

        result = await get_performance_summary()
        assert result["total_signals"] == 6
        assert result["target_hits"] == 3
        assert result["stop_hits"] == 1
        assert result["expired"] == 2

    async def test_hit_ratio_excludes_expired(self):
        """EXPIRED excluded from denominator. Below 30 conclusive → phase gate active."""
        for _ in range(3):
            sid = await _insert_signal()
            await update_outcome_atomic(sid, "TARGET_HIT", 5.0, 2.0, 30.0)
        sid = await _insert_signal()
        await update_outcome_atomic(sid, "STOP_HIT", 2.0, 5.0, 30.0)
        for _ in range(2):
            sid = await _insert_signal()
            await update_outcome_atomic(sid, "EXPIRED", 0.5, 0.5, 30.0)

        result = await get_performance_summary()
        # 4 conclusive signals — phase gate active
        assert result["phase_gate_active"] is True
        assert result["hit_ratio"] is None
        assert result["calibration_count"] == 4  # 3 TARGET + 1 STOP

    async def test_all_expired_hit_ratio_zero(self):
        for _ in range(3):
            sid = await _insert_signal()
            await update_outcome_atomic(sid, "EXPIRED", 0.5, 0.5, 30.0)

        result = await get_performance_summary()
        assert result["phase_gate_active"] is True
        assert result["hit_ratio"] is None
        assert result["calibration_count"] == 0

    async def test_profit_factor_null_when_no_stop_hits(self):
        """All TARGET_HIT but below 30 conclusive → phase gate active → profit_factor=None."""
        for _ in range(3):
            sid = await _insert_signal()
            await update_outcome_atomic(sid, "TARGET_HIT", 5.0, 2.0, 30.0)

        result = await get_performance_summary()
        assert result["phase_gate_active"] is True
        assert result["profit_factor"] is None

    async def test_profit_factor_zero_when_no_signals(self):
        result = await get_performance_summary()
        assert result["phase_gate_active"] is True
        assert result["profit_factor"] is None

    async def test_profit_factor_computed_correctly(self):
        """2 conclusive signals → phase gate active; profit_factor=None."""
        sid = await _insert_signal()
        await update_outcome_atomic(sid, "TARGET_HIT", 10.0, 2.0, 30.0)
        sid = await _insert_signal()
        await update_outcome_atomic(sid, "STOP_HIT", 3.0, 5.0, 30.0)

        result = await get_performance_summary()
        assert result["phase_gate_active"] is True
        assert result["profit_factor"] is None

    async def test_orphaned_count_over_35_days(self):
        old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
        recent = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        await _insert_signal(analyzed_at=old)     # orphaned
        await _insert_signal(analyzed_at=recent)  # not orphaned (< 35 days)

        result = await get_performance_summary()
        assert result["orphaned_count"] == 1

    async def test_resolved_signal_not_orphaned(self):
        """Even an old resolved signal is not counted as orphaned."""
        old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
        sid = await _insert_signal(analyzed_at=old)
        await update_outcome_atomic(sid, "TARGET_HIT", 5.0, 2.0, 30.0)

        result = await get_performance_summary()
        assert result["orphaned_count"] == 0


class TestUpdateOutcomeAtomicSupportBreakLevel:
    async def test_support_break_level_saved(self):
        sid = await _insert_signal()
        await update_outcome_atomic(sid, "STOP_HIT", 2.0, 5.0, 30.0, support_break_level="S1")

        db = await get_connection()
        try:
            cursor = await db.execute(
                "SELECT support_break_level FROM analysis_results WHERE id = ?", (sid,)
            )
            row = await cursor.fetchone()
        finally:
            await db.close()

        assert row["support_break_level"] == "S1"

    async def test_support_break_level_default_is_null(self):
        """Calling without support_break_level leaves it NULL."""
        sid = await _insert_signal()
        await update_outcome_atomic(sid, "TARGET_HIT", 5.0, 2.0, 30.0)

        db = await get_connection()
        try:
            cursor = await db.execute(
                "SELECT support_break_level FROM analysis_results WHERE id = ?", (sid,)
            )
            row = await cursor.fetchone()
        finally:
            await db.close()

        assert row["support_break_level"] is None

    async def test_support_break_level_not_overwritten_on_second_write(self):
        """Idempotency guard — second write is skipped, first support_break_level preserved."""
        sid = await _insert_signal()
        await update_outcome_atomic(sid, "STOP_HIT", 2.0, 5.0, 30.0, support_break_level="S1")
        await update_outcome_atomic(sid, "TARGET_HIT", 5.0, 2.0, 30.0, support_break_level=None)

        db = await get_connection()
        try:
            cursor = await db.execute(
                "SELECT outcome, support_break_level FROM analysis_results WHERE id = ?", (sid,)
            )
            row = await cursor.fetchone()
        finally:
            await db.close()

        assert row["outcome"] == "STOP_HIT"
        assert row["support_break_level"] == "S1"


@pytest.mark.parametrize(
    "conclusive,expected_phase,banner_substring",
    [
        (0,   0, "Calibration"),
        (1,   0, "Calibration"),
        (29,  0, "Calibration"),
        (30,  1, "Pilot"),
        (99,  1, "Pilot"),
        (100, 2, "Evaluation"),
        (299, 2, "Evaluation"),
        (300, 3, "Confident"),
    ],
)
def test_compute_phase(conclusive, expected_phase, banner_substring):
    phase, banner = _compute_phase(conclusive)
    assert phase == expected_phase
    assert banner_substring in banner


class TestGetPerformanceSummaryPhaseFields:
    async def test_phase_and_banner_present_in_dict(self):
        result = await get_performance_summary()
        assert "phase" in result
        assert "phase_banner" in result
        assert isinstance(result["phase"], int)
        assert isinstance(result["phase_banner"], str)

    async def test_phase_0_below_30_conclusive(self):
        result = await get_performance_summary()
        assert result["phase"] == 0
        assert "Calibration" in result["phase_banner"]

    async def test_phase_1_at_30_conclusive(self):
        for _ in range(16):
            sid = await _insert_signal()
            await update_outcome_atomic(sid, "TARGET_HIT", 5.0, 2.0, 30.0)
        for _ in range(14):
            sid = await _insert_signal()
            await update_outcome_atomic(sid, "STOP_HIT", 2.0, 5.0, 30.0)

        result = await get_performance_summary()
        assert result["phase"] == 1
        assert "Pilot" in result["phase_banner"]
        assert result["phase_gate_active"] is False
