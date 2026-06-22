"""Tests for analysis repository — save_analysis_results write resilience (NEX-16)."""

from unittest.mock import patch

import aiosqlite
import pytest

from app.db.repository import save_analysis_results


def _make_row(ticker: str, run_id: str = "run-1") -> dict:
    return {
        "run_id": run_id,
        "ticker": ticker,
        "rank": 1,
        "score": 75.0,
        "score_delta": 0.0,
        "signal": "BUY",
        "confidence": 0.8,
        "risk_reward_ratio": 4.0,
        "entry_price": 100.0,
        "target_price": 130.0,
        "stop_loss": 90.0,
        "support_validated": True,
        "argument": "test",
        "indicators_summary": "{}",
        "screenshot_path": None,
        "expected_gain_per10": 3.0,
        "expected_loss_per10": 1.0,
        "expected_value_per10": 0.4,
        "hit_rate_used": 0.35,
        "hit_rate_source": "assumed",
    }


@pytest.mark.asyncio
async def test_save_analysis_results_partial_failure(tmp_path):
    """One INSERT raising OperationalError should not prevent others from committing."""
    call_count = 0
    original_execute = aiosqlite.Connection.execute

    async def patched_execute(self, sql, params=None):
        nonlocal call_count
        if "INSERT INTO analysis_results" in sql:
            call_count += 1
            if call_count == 1:
                raise aiosqlite.OperationalError("disk I/O error")
        if params is not None:
            return await original_execute(self, sql, params)
        return await original_execute(self, sql)

    from app.db import connection as conn_module
    db_path = str(tmp_path / "test.db")
    conn_module.set_db_path(db_path)
    await conn_module.init_db()

    with patch.object(aiosqlite.Connection, "execute", patched_execute):
        errors = await save_analysis_results([_make_row("AAPL"), _make_row("MSFT")])

    assert len(errors) == 1
    assert errors[0]["ticker"] == "AAPL"
    assert "disk I/O error" in errors[0]["error_message"]


@pytest.mark.asyncio
async def test_save_analysis_results_all_fail(tmp_path):
    """All INSERTs raising should return all errors without raising."""
    from app.db import connection as conn_module
    db_path = str(tmp_path / "test.db")
    conn_module.set_db_path(db_path)
    await conn_module.init_db()

    original_execute = aiosqlite.Connection.execute

    async def always_fail(self, sql, params=None):
        if "INSERT INTO analysis_results" in sql:
            raise aiosqlite.OperationalError("table locked")
        if params is not None:
            return await original_execute(self, sql, params)
        return await original_execute(self, sql)

    with patch.object(aiosqlite.Connection, "execute", always_fail):
        errors = await save_analysis_results([_make_row("AAPL"), _make_row("MSFT")])

    assert len(errors) == 2
    tickers = {e["ticker"] for e in errors}
    assert tickers == {"AAPL", "MSFT"}


@pytest.mark.asyncio
async def test_save_analysis_results_success_returns_empty_list(tmp_path):
    """Successful writes return an empty error list."""
    from app.db import connection as conn_module
    db_path = str(tmp_path / "test.db")
    conn_module.set_db_path(db_path)
    await conn_module.init_db()

    errors = await save_analysis_results([_make_row("NVDA")])
    assert errors == []
