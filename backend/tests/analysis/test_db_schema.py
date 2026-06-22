"""Tests for analysis DB schema, seeding, and repository functions."""
import pytest

from app.db import get_connection, init_db, set_db_path
from app.db.repository import (
    add_analysis_ticker,
    get_analysis_by_ticker,
    get_analysis_tickers,
    get_latest_analysis,
    remove_analysis_ticker,
    save_analysis_results,
    update_enrichment_delta,
)


@pytest.fixture(autouse=True)
async def tmp_db(tmp_path):
    set_db_path(str(tmp_path / "test.db"))
    await init_db()


async def test_analysis_results_table_exists():
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_results'"
        )
        row = await cursor.fetchone()
        assert row is not None
    finally:
        await db.close()


async def test_analysis_tickers_table_exists():
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_tickers'"
        )
        row = await cursor.fetchone()
        assert row is not None
    finally:
        await db.close()


async def test_analysis_tickers_seeded_with_defaults():
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT ticker FROM analysis_tickers WHERE user_id = 'default' ORDER BY ticker"
        )
        rows = await cursor.fetchall()
        tickers = [r[0] for r in rows]
        assert "AAPL" in tickers
        assert "NVDA" in tickers
        assert len(tickers) >= 10
    finally:
        await db.close()


async def test_get_analysis_tickers_returns_defaults():
    tickers = await get_analysis_tickers()
    assert len(tickers) >= 10
    assert "NVDA" in tickers


async def test_add_and_remove_analysis_ticker():
    await add_analysis_ticker("PYPL")
    tickers = await get_analysis_tickers()
    assert "PYPL" in tickers

    removed = await remove_analysis_ticker("PYPL")
    assert removed is True
    tickers = await get_analysis_tickers()
    assert "PYPL" not in tickers


async def test_add_duplicate_analysis_ticker_is_idempotent():
    await add_analysis_ticker("AAPL")  # already seeded
    tickers = await get_analysis_tickers()
    assert tickers.count("AAPL") == 1


async def test_save_and_retrieve_analysis_results():
    rows = [
        {
            "run_id": "run-1",
            "ticker": "NVDA",
            "rank": 1,
            "score": 88.5,
            "signal": "BUY",
            "confidence": 0.9,
            "risk_reward_ratio": 4.2,
            "entry_price": 890.0,
            "target_price": 930.0,
            "stop_loss": 880.0,
            "support_validated": True,
            "argument": "Strong bullish setup",
            "indicators_summary": '{"macd": "bullish"}',
            "screenshot_path": None,
        }
    ]
    await save_analysis_results(rows)

    results = await get_latest_analysis()
    assert len(results) == 1
    assert results[0]["ticker"] == "NVDA"
    assert results[0]["rank"] == 1


async def test_get_analysis_by_ticker_returns_latest():
    rows = [
        {
            "run_id": "run-2",
            "ticker": "AAPL",
            "rank": 2,
            "score": 75.0,
            "signal": "BUY",
            "confidence": 0.8,
            "risk_reward_ratio": 3.5,
            "entry_price": 190.0,
            "target_price": 210.0,
            "stop_loss": 184.0,
            "support_validated": True,
            "argument": "RSI bounce off support",
            "indicators_summary": "{}",
            "screenshot_path": None,
        }
    ]
    await save_analysis_results(rows)
    result = await get_analysis_by_ticker("AAPL")
    assert result is not None
    assert result["ticker"] == "AAPL"


async def test_get_analysis_by_ticker_returns_none_when_missing():
    result = await get_analysis_by_ticker("ZZZZ")
    assert result is None


# ── Task 9.4 — enrichment_delta clamping (US-301) ────────────────────────────

def _enrichment_row(ticker: str = "AAPL", run_id: str = "run-enrich") -> dict:
    return {
        "run_id": run_id,
        "ticker": ticker,
        "rank": 1,
        "score": 80.0,
        "score_quant": 80.0,
        "score_legacy": 72.0,
        "signal": "BUY",
        "confidence": 0.8,
        "risk_reward_ratio": 3.5,
        "entry_price": 150.0,
        "target_price": 180.0,
        "stop_loss": 140.0,
        "support_validated": True,
        "argument": "test",
        "indicators_summary": "{}",
        "screenshot_path": None,
    }


async def test_update_enrichment_delta_positive_boundary():
    """delta=+15 (max) is accepted and persisted; score_enriched = score_quant + 15."""
    await save_analysis_results([_enrichment_row()])
    updated = await update_enrichment_delta("AAPL", "run-enrich", 15.0)
    assert updated is True
    result = await get_analysis_by_ticker("AAPL")
    assert result is not None
    assert result["enrichment_delta"] == 15.0
    assert result["score_enriched"] == round(80.0 + 15.0, 2)


async def test_update_enrichment_delta_negative_boundary():
    """delta=-15 (min) is accepted and persisted; score_enriched = score_quant - 15."""
    await save_analysis_results([_enrichment_row()])
    updated = await update_enrichment_delta("AAPL", "run-enrich", -15.0)
    assert updated is True
    result = await get_analysis_by_ticker("AAPL")
    assert result is not None
    assert result["enrichment_delta"] == -15.0
    assert result["score_enriched"] == round(80.0 - 15.0, 2)


async def test_update_enrichment_delta_zero():
    """delta=0.0 maps to no change; score_enriched == score_quant."""
    await save_analysis_results([_enrichment_row()])
    await update_enrichment_delta("AAPL", "run-enrich", 0.0)
    result = await get_analysis_by_ticker("AAPL")
    assert result is not None
    assert result["enrichment_delta"] == 0.0
    assert result["score_enriched"] == 80.0


async def test_update_enrichment_delta_wrong_run_id_returns_false():
    """Non-existent run_id returns False (no row updated)."""
    await save_analysis_results([_enrichment_row()])
    updated = await update_enrichment_delta("AAPL", "no-such-run", 10.0)
    assert updated is False


async def test_update_enrichment_delta_wrong_ticker_returns_false():
    """Non-existent ticker for a valid run_id returns False."""
    await save_analysis_results([_enrichment_row()])
    updated = await update_enrichment_delta("ZZZZ", "run-enrich", 5.0)
    assert updated is False


async def test_score_enriched_none_when_score_quant_missing():
    """Row without score_quant yields score_enriched=None even after enrichment."""
    row = _enrichment_row()
    row["score_quant"] = None  # pre-US-301 style row
    await save_analysis_results([row])
    await update_enrichment_delta("AAPL", "run-enrich", 10.0)
    result = await get_analysis_by_ticker("AAPL")
    assert result is not None
    assert result["score_enriched"] is None


# ── Task 9.7 — idempotent migration (US-301) ─────────────────────────────────

async def test_init_db_twice_does_not_error(tmp_path):
    """Calling init_db() twice on the same database must not raise."""
    set_db_path(str(tmp_path / "idempotent.db"))
    await init_db()
    await init_db()  # second call — ALTER TABLE duplicate-column errors must be silenced

    db = await get_connection()
    try:
        cursor = await db.execute("PRAGMA table_info(analysis_results)")
        cols = {row[1] for row in await cursor.fetchall()}
        assert "score_quant" in cols
        assert "score_legacy" in cols
        assert "enrichment_delta" in cols
    finally:
        await db.close()
