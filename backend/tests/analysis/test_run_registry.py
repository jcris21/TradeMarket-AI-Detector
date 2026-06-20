"""Unit tests for the US-204 run registry: ETA formula, active-run lookup, eviction."""

from datetime import datetime, timedelta, timezone

import pytest

from app.analysis import run_registry
from app.analysis.run_registry import (
    RunState,
    evict_expired_runs,
    get_active_run,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    run_registry.clear_registry()
    yield
    run_registry.clear_registry()


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def test_eta_normal_case():
    """completed=42, total=100, elapsed≈12s → ETA ≈ (12/42)*58 ≈ 16.6s."""
    started = datetime.now(timezone.utc) - timedelta(seconds=12)
    state = RunState(
        run_id="r1",
        stage="data",
        tickers_total=100,
        tickers_completed=42,
        started_at=_iso(started),
    )
    eta = state.estimated_remaining_seconds()
    assert eta is not None
    expected = (12 / 42) * (100 - 42)
    assert abs(eta - expected) < 1.0


def test_eta_zero_completed_is_none():
    state = RunState(
        run_id="r2",
        stage="data",
        tickers_total=100,
        tickers_completed=0,
        started_at=_iso(datetime.now(timezone.utc)),
    )
    assert state.estimated_remaining_seconds() is None


def test_eta_all_completed_is_zero():
    state = RunState(
        run_id="r3",
        stage="scoring",
        tickers_total=10,
        tickers_completed=10,
        started_at=_iso(datetime.now(timezone.utc) - timedelta(seconds=5)),
    )
    assert state.estimated_remaining_seconds() == 0.0


def test_get_active_run_returns_non_terminal():
    run_registry.register_run(
        RunState(run_id="done", stage="complete", tickers_total=5)
    )
    active = RunState(run_id="live", stage="data", tickers_total=5)
    run_registry.register_run(active)
    assert get_active_run() is active


def test_get_active_run_none_when_all_terminal():
    run_registry.register_run(
        RunState(run_id="c", stage="complete", tickers_total=1)
    )
    run_registry.register_run(
        RunState(run_id="f", stage="failed", tickers_total=1)
    )
    assert get_active_run() is None


def test_eviction_removes_old_completed_run():
    old = datetime.now(timezone.utc) - timedelta(minutes=11)
    run_registry.register_run(
        RunState(
            run_id="old",
            stage="complete",
            tickers_total=1,
            completed_at=_iso(old),
        )
    )
    evict_expired_runs()
    assert run_registry.get_run("old") is None


def test_eviction_keeps_recent_completed_run():
    recent = datetime.now(timezone.utc) - timedelta(minutes=2)
    run_registry.register_run(
        RunState(
            run_id="recent",
            stage="complete",
            tickers_total=1,
            completed_at=_iso(recent),
        )
    )
    evict_expired_runs()
    assert run_registry.get_run("recent") is not None


def test_eviction_keeps_active_run_without_completed_at():
    run_registry.register_run(
        RunState(run_id="active", stage="data", tickers_total=1)
    )
    evict_expired_runs()
    assert run_registry.get_run("active") is not None
