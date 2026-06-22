"""Integration tests for save_analysis_run, get_latest_analysis, and the /api/analysis/latest route.

All repository tests use a real in-memory aiosqlite connection.
Each test opens a fresh DB, patches get_connection, and lets the repository
close the connection itself — no db.close mocking.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest

from app.db.schema import SCHEMA_SQL

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _open_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.executescript(SCHEMA_SQL)
    await db.commit()
    return db


def _run_row(run_id: str | None = None) -> dict:
    return {
        "run_id": run_id or str(uuid.uuid4()),
        "user_id": "default",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": 12.5,
        "total_tickers": 100,
        "successful_tickers": 90,
        "error_count": 10,
    }


async def _seed_analysis_result(db: aiosqlite.Connection, run_id: str, ticker: str) -> None:
    await db.execute(
        """INSERT INTO analysis_results
           (id, user_id, run_id, ticker, analyzed_at, signal, confidence,
            entry_price, target_price, stop_loss, risk_reward_ratio,
            support_validated, argument, indicators_summary, rank, score)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), "default", run_id, ticker,
         datetime.now(timezone.utc).isoformat(),
         "BUY", 0.75, 100.0, 120.0, 90.0, 2.0, 0, "test", "{}", 1, 70.0),
    )
    await db.commit()


async def _seed_analysis_run(db: aiosqlite.Connection, row: dict) -> None:
    await db.execute(
        """INSERT INTO analysis_runs
           (run_id, user_id, analyzed_at, duration_seconds,
            total_tickers, successful_tickers, error_count)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (row["run_id"], row.get("user_id", "default"), row["analyzed_at"],
         row["duration_seconds"], row["total_tickers"],
         row["successful_tickers"], row["error_count"]),
    )
    await db.commit()


# ── Repository tests (10.3) ───────────────────────────────────────────────────
# Each test owns its DB. The repository calls db.close() itself; the test's
# finally block is only a safety net in case the repository raises before close.


@pytest.mark.asyncio
async def test_save_analysis_run_persists_row():
    """save_analysis_run writes the row; verified by querying a separate connection."""
    import os
    import tempfile

    row = _run_row()
    run_id = row["run_id"]

    # Use a temp file so we can open a second connection to verify
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # Seed schema
        seed_db = await aiosqlite.connect(db_path)
        seed_db.row_factory = aiosqlite.Row
        await seed_db.executescript(SCHEMA_SQL)
        await seed_db.commit()
        await seed_db.close()

        # Call repository via patched get_connection
        async def _open_named() -> aiosqlite.Connection:
            c = await aiosqlite.connect(db_path)
            c.row_factory = aiosqlite.Row
            return c

        with patch("app.db.repository.get_connection", side_effect=_open_named):
            from app.db.repository import save_analysis_run
            await save_analysis_run(row)

        # Verify with independent connection
        verify_db = await aiosqlite.connect(db_path)
        verify_db.row_factory = aiosqlite.Row
        cursor = await verify_db.execute(
            "SELECT * FROM analysis_runs WHERE run_id = ?", (run_id,)
        )
        saved = await cursor.fetchone()
        await verify_db.close()

        assert saved is not None
        assert saved["run_id"] == run_id
        assert saved["total_tickers"] == 100
        assert saved["successful_tickers"] == 90
        assert saved["error_count"] == 10
        assert abs(saved["duration_seconds"] - 12.5) < 0.001
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_get_latest_analysis_returns_run_metadata():
    """get_latest_analysis includes run_metadata.duration_seconds after a run is saved."""
    import os
    import tempfile

    row = _run_row()
    run_id = row["run_id"]

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        seed_db = await aiosqlite.connect(db_path)
        seed_db.row_factory = aiosqlite.Row
        await seed_db.executescript(SCHEMA_SQL)
        await seed_db.commit()
        await _seed_analysis_result(seed_db, run_id, "AAPL")
        await _seed_analysis_run(seed_db, row)
        await seed_db.close()

        async def _open_named() -> aiosqlite.Connection:
            c = await aiosqlite.connect(db_path)
            c.row_factory = aiosqlite.Row
            return c

        with patch("app.db.repository.get_connection", side_effect=_open_named):
            from app.db.repository import get_latest_analysis
            results, run_metadata = await get_latest_analysis()

        assert len(results) >= 1
        assert run_metadata is not None
        assert "duration_seconds" in run_metadata
        assert abs(run_metadata["duration_seconds"] - 12.5) < 0.001
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_get_latest_analysis_returns_none_run_metadata_when_no_run():
    """get_latest_analysis returns run_metadata=None when analysis_runs has no matching row."""
    import os
    import tempfile

    run_id = str(uuid.uuid4())

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        seed_db = await aiosqlite.connect(db_path)
        seed_db.row_factory = aiosqlite.Row
        await seed_db.executescript(SCHEMA_SQL)
        await seed_db.commit()
        await _seed_analysis_result(seed_db, run_id, "MSFT")
        await seed_db.close()

        async def _open_named() -> aiosqlite.Connection:
            c = await aiosqlite.connect(db_path)
            c.row_factory = aiosqlite.Row
            return c

        with patch("app.db.repository.get_connection", side_effect=_open_named):
            from app.db.repository import get_latest_analysis
            results, run_metadata = await get_latest_analysis()

        assert len(results) >= 1
        assert run_metadata is None
    finally:
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_get_latest_analysis_empty_when_no_results():
    """get_latest_analysis returns ([], None) when the DB has no analysis rows."""
    import os
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        seed_db = await aiosqlite.connect(db_path)
        seed_db.row_factory = aiosqlite.Row
        await seed_db.executescript(SCHEMA_SQL)
        await seed_db.commit()
        await seed_db.close()

        async def _open_named() -> aiosqlite.Connection:
            c = await aiosqlite.connect(db_path)
            c.row_factory = aiosqlite.Row
            return c

        with patch("app.db.repository.get_connection", side_effect=_open_named):
            from app.db.repository import get_latest_analysis
            results, run_metadata = await get_latest_analysis()

        assert results == []
        assert run_metadata is None
    finally:
        os.unlink(db_path)


# ── API route tests (10.1, 10.2) ─────────────────────────────────────────────


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app
    return TestClient(app)


def test_latest_route_includes_run_metadata_after_run(client):
    """GET /api/analysis/latest returns run_metadata with duration_seconds."""
    run_metadata = {
        "run_id": "test-run-001",
        "analyzed_at": "2026-06-13T12:00:00+00:00",
        "duration_seconds": 42.1,
        "total_tickers": 100,
        "successful_tickers": 85,
    }
    mock_results = [{"ticker": "AAPL", "signal": "BUY"}]

    with patch("app.routes.analysis.get_latest_analysis", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = (mock_results, run_metadata)
        response = client.get("/api/analysis/latest")

    assert response.status_code == 200
    body = response.json()
    assert "run_metadata" in body
    assert body["run_metadata"]["duration_seconds"] == pytest.approx(42.1)
    assert body["run_metadata"]["run_id"] == "test-run-001"
    assert len(body["results"]) == 1


def test_latest_route_returns_null_run_metadata_when_empty(client):
    """GET /api/analysis/latest returns run_metadata: null when no run exists."""
    with patch("app.routes.analysis.get_latest_analysis", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = ([], None)
        response = client.get("/api/analysis/latest")

    assert response.status_code == 200
    body = response.json()
    assert body["results"] == []
    assert body["run_metadata"] is None
