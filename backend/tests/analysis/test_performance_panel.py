"""Tests for get_performance_summary() — phase gate, metrics, and sentinel values."""

import uuid
from datetime import datetime, timezone

import aiosqlite
import pytest

from app.db.connection import set_db_path
from app.db.repository import get_performance_summary


@pytest.fixture
async def perf_db(tmp_path):
    """In-memory aiosqlite DB with analysis_results schema, patched into repository."""
    db_path = str(tmp_path / "test_perf.db")
    set_db_path(db_path)

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute(
        """
        CREATE TABLE analysis_results (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            run_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            rank INTEGER,
            score REAL,
            score_delta REAL,
            signal TEXT,
            confidence REAL,
            risk_reward_ratio REAL,
            entry_price REAL,
            target_price REAL,
            stop_loss REAL,
            support_validated INTEGER NOT NULL DEFAULT 0,
            argument TEXT,
            indicators_summary TEXT,
            screenshot_path TEXT,
            analyzed_at TEXT NOT NULL,
            expected_gain_per10 REAL,
            expected_loss_per10 REAL,
            expected_value_per10 REAL,
            hit_rate_used REAL,
            hit_rate_source TEXT,
            outcome TEXT,
            actual_gain_pct REAL,
            actual_loss_pct REAL,
            hold_days REAL,
            support_break_level TEXT
        )
        """
    )
    await db.commit()
    await db.close()
    yield db_path


async def _seed(db_path: str, rows: list[dict]) -> None:
    """Insert rows into analysis_results."""
    db = await aiosqlite.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid.uuid4())
    for row in rows:
        await db.execute(
            "INSERT INTO analysis_results "
            "(id, user_id, run_id, ticker, analyzed_at, outcome, actual_gain_pct, actual_loss_pct) "
            "VALUES (?, 'default', ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                run_id,
                row.get("ticker", "TEST"),
                row.get("analyzed_at", now),
                row.get("outcome"),
                row.get("actual_gain_pct"),
                row.get("actual_loss_pct"),
            ),
        )
    await db.commit()
    await db.close()


@pytest.mark.asyncio
async def test_0_signals(perf_db):
    result = await get_performance_summary()

    assert result["phase_gate_active"] is True
    assert result["calibration_count"] == 0
    assert result["total_signals"] == 0
    assert result["hit_ratio"] is None
    assert result["profit_factor"] is None
    assert result["realized_rr"] is None
    assert result["hr_status"] is None
    assert result["pf_status"] is None
    assert result["rr_status"] is None
    assert result["below_breakeven"] is False


@pytest.mark.asyncio
async def test_15_signals(perf_db):
    rows = (
        [{"outcome": "TARGET_HIT", "actual_gain_pct": 10.0, "actual_loss_pct": 3.0}] * 10
        + [{"outcome": "STOP_HIT", "actual_gain_pct": 2.0, "actual_loss_pct": 5.0}] * 5
    )
    await _seed(perf_db, rows)

    result = await get_performance_summary()

    assert result["phase_gate_active"] is True
    assert result["calibration_count"] == 15
    assert result["hit_ratio"] is None
    assert result["profit_factor"] is None
    assert result["realized_rr"] is None


@pytest.mark.asyncio
async def test_30_signals(perf_db):
    rows = (
        [{"outcome": "TARGET_HIT", "actual_gain_pct": 15.0, "actual_loss_pct": 2.0}] * 20
        + [{"outcome": "STOP_HIT", "actual_gain_pct": 1.0, "actual_loss_pct": 6.0}] * 10
    )
    await _seed(perf_db, rows)

    result = await get_performance_summary()

    assert result["phase_gate_active"] is False
    assert result["calibration_count"] == 30
    assert result["hit_ratio"] == pytest.approx(20 / 30, rel=1e-3)
    assert result["profit_factor"] is not None
    assert result["profit_factor"] > 0
    assert result["realized_rr"] is not None
    assert result["realized_rr"] > 0
    assert result["hr_status"] == "green"  # 0.667 >= 0.35


@pytest.mark.asyncio
async def test_100_signals_expired_excluded(perf_db):
    rows = (
        [{"outcome": "TARGET_HIT", "actual_gain_pct": 12.0, "actual_loss_pct": 2.0}] * 60
        + [{"outcome": "STOP_HIT", "actual_gain_pct": 1.5, "actual_loss_pct": 4.0}] * 30
        + [{"outcome": "EXPIRED", "actual_gain_pct": 0.5, "actual_loss_pct": 0.5}] * 10
    )
    await _seed(perf_db, rows)

    result = await get_performance_summary()

    assert result["phase_gate_active"] is False
    assert result["calibration_count"] == 90  # EXPIRED excluded
    assert result["total_signals"] == 100
    assert result["expired"] == 10
    assert result["hit_ratio"] == pytest.approx(60 / 90, rel=1e-3)


@pytest.mark.asyncio
async def test_profit_factor_sentinel(perf_db):
    """When only TARGET_HIT rows exist (no STOP_HIT), profit_factor should be 999.0."""
    rows = [
        {"outcome": "TARGET_HIT", "actual_gain_pct": 20.0, "actual_loss_pct": 1.0}
    ] * 30
    await _seed(perf_db, rows)

    result = await get_performance_summary()

    assert result["phase_gate_active"] is False
    assert result["profit_factor"] == 999.0


@pytest.mark.asyncio
async def test_below_breakeven(perf_db):
    """hit_ratio < 0.25 sets below_breakeven=True and hr_status='red'."""
    rows = (
        [{"outcome": "TARGET_HIT", "actual_gain_pct": 10.0, "actual_loss_pct": 2.0}] * 6
        + [{"outcome": "STOP_HIT", "actual_gain_pct": 1.0, "actual_loss_pct": 5.0}] * 24
    )
    await _seed(perf_db, rows)

    result = await get_performance_summary()

    assert result["phase_gate_active"] is False
    assert result["below_breakeven"] is True
    assert result["hr_status"] == "red"


@pytest.mark.asyncio
async def test_hr_status_neutral(perf_db):
    """hit_ratio between 0.25 and 0.35 gives hr_status='neutral'."""
    rows = (
        [{"outcome": "TARGET_HIT", "actual_gain_pct": 10.0, "actual_loss_pct": 2.0}] * 9
        + [{"outcome": "STOP_HIT", "actual_gain_pct": 1.0, "actual_loss_pct": 5.0}] * 21
    )
    await _seed(perf_db, rows)

    result = await get_performance_summary()

    assert result["phase_gate_active"] is False
    hr = result["hit_ratio"]
    assert hr is not None
    assert 0.25 <= hr < 0.35
    assert result["hr_status"] == "neutral"
    assert result["below_breakeven"] is False
