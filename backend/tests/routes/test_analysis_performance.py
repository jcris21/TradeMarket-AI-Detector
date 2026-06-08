"""Tests for GET /api/analysis/performance endpoint.

Note: we do NOT import app.routes.analysis directly because it transitively
imports app.analysis.orchestrator (Playwright), which hangs on this environment.
Instead, we build a minimal test app that wires the same function — verifying
the endpoint contract (status, shape, values) without the orchestrator dependency.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.db import init_db, set_db_path
from app.db.connection import get_connection
from app.db.repository import get_performance_summary, update_outcome_atomic


# ── Minimal test app (mirrors routes/analysis.py performance endpoint) ────────

_test_app = FastAPI()


@_test_app.get("/api/analysis/performance")
async def _get_performance():
    return await get_performance_summary()


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def test_db(tmp_path):
    db_path = str(tmp_path / "perf_route_test.db")
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


@pytest.fixture
async def client(test_db):
    async with AsyncClient(transport=ASGITransport(app=_test_app), base_url="http://test") as ac:
        yield ac


async def _insert_signal(
    outcome: str | None = None,
    analyzed_at: str | None = None,
    gain_pct: float = 5.0,
    loss_pct: float = 2.0,
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
            "VALUES (?, 'default', ?, 'AAPL', 1, 75.0, 'BUY', 0.8, 4.0, 180.0, 200.0, 165.0, 1, ?)",
            (sid, str(uuid.uuid4()), at),
        )
        await db.commit()
    finally:
        await db.close()
    if outcome is not None:
        await update_outcome_atomic(sid, outcome, gain_pct, loss_pct, 30.0)
    return sid


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestPerformanceEndpoint:
    async def test_returns_200(self, client):
        resp = await client.get("/api/analysis/performance")
        assert resp.status_code == 200

    async def test_empty_db_all_zeros(self, client):
        resp = await client.get("/api/analysis/performance")
        data = resp.json()

        assert data["total_signals"] == 0
        assert data["target_hits"] == 0
        assert data["stop_hits"] == 0
        assert data["expired"] == 0
        assert data["orphaned_count"] == 0
        assert data["hit_ratio"] is None
        assert data["profit_factor"] is None

    async def test_response_has_all_required_fields(self, client):
        resp = await client.get("/api/analysis/performance")
        data = resp.json()
        required = {
            "total_signals", "target_hits", "stop_hits",
            "expired", "orphaned_count", "hit_ratio", "profit_factor",
            "phase", "phase_banner",
        }
        assert required <= data.keys()
        assert data["phase"] == 0
        assert "Calibration" in data["phase_banner"]

    async def test_hit_ratio_correct_with_mixed_outcomes(self, client):
        await _insert_signal("TARGET_HIT", gain_pct=5.0, loss_pct=2.0)
        await _insert_signal("TARGET_HIT", gain_pct=5.0, loss_pct=2.0)
        await _insert_signal("STOP_HIT", gain_pct=2.0, loss_pct=5.0)
        await _insert_signal("EXPIRED", gain_pct=0.5, loss_pct=0.5)

        resp = await client.get("/api/analysis/performance")
        data = resp.json()

        assert data["target_hits"] == 2
        assert data["stop_hits"] == 1
        assert data["expired"] == 1
        assert abs(data["hit_ratio"] - 2 / 3) < 1e-4  # 2 / (2 + 1), rounded to 4 dp

    async def test_profit_factor_null_when_no_losses(self, client):
        """All TARGET_HIT (no STOP_HIT) → profit_factor serialized as null in JSON."""
        for _ in range(3):
            await _insert_signal("TARGET_HIT")

        resp = await client.get("/api/analysis/performance")
        data = resp.json()

        assert data["profit_factor"] is None

    async def test_orphaned_count_in_response(self, client):
        old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
        await _insert_signal(None, analyzed_at=old)  # orphaned
        await _insert_signal("TARGET_HIT")           # resolved, not orphaned

        resp = await client.get("/api/analysis/performance")
        data = resp.json()

        assert data["orphaned_count"] == 1
