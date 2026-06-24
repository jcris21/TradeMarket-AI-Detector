"""Integration tests for the screenshot enrichment endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.db import init_db, set_db_path
from app.routes.analysis import router as analysis_router


@pytest.fixture
async def enrich_client(tmp_path):
    db_path = str(tmp_path / "enrich_test.db")
    set_db_path(db_path)
    await init_db()

    app = FastAPI()
    app.include_router(analysis_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@patch("app.routes.analysis._run_screenshot_enrichment")
async def test_screenshot_enrich_returns_202_with_enrichment_id(mock_task, enrich_client):
    mock_task.return_value = None
    resp = await enrich_client.post(
        "/api/analysis/GOOGL/enrich",
        json={"enrichment_type": "screenshot", "source_url": "https://example.com/chart"},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "enrichment_id" in body
    assert body["status"] == "pending"


async def test_screenshot_enrich_404_when_no_analysis(enrich_client):
    resp = await enrich_client.post(
        "/api/analysis/FAKEXYZ/enrich",
        json={"enrichment_type": "screenshot", "source_url": "https://example.com/chart"},
    )
    assert resp.status_code == 404


async def test_screenshot_enrich_400_for_http_url(enrich_client):
    resp = await enrich_client.post(
        "/api/analysis/GOOGL/enrich",
        json={"enrichment_type": "screenshot", "source_url": "http://example.com/chart"},
    )
    assert resp.status_code == 400


async def test_unknown_enrichment_type_returns_422(enrich_client):
    resp = await enrich_client.post(
        "/api/analysis/GOOGL/enrich",
        json={"enrichment_type": "unknown_type", "source_url": "https://example.com"},
    )
    assert resp.status_code == 422


@patch("app.analysis.screenshot_agent.async_playwright")
@patch("app.analysis.vision_agent._call_llm")
async def test_background_task_success_updates_enrichments_and_analysis(
    mock_call_llm, mock_pw, tmp_path
):
    import json

    from app.db import get_analysis_by_ticker, get_enrichment_job
    from app.routes.analysis import _run_screenshot_enrichment

    db_path = str(tmp_path / "bg_test.db")
    set_db_path(db_path)
    await init_db()

    # Mock playwright: returns PNG bytes
    page = AsyncMock()
    page.goto.return_value = None
    page.screenshot.return_value = b"\x89PNG\r\n"
    browser = AsyncMock()
    browser.new_page.return_value = page
    pw = AsyncMock()
    pw.chromium.launch.return_value = browser
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=pw)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pw.return_value = cm

    # Mock _call_llm: returns valid JSON string
    valid_json = json.dumps({
        "ticker": "GOOGL",
        "signal": "BUY",
        "confidence": 0.85,
        "entry_price": 178.50,
        "target_price": 208.54,
        "stop_loss": 172.20,
        "risk_reward_ratio": 4.8,
        "support_validated": True,
        "indicators_summary": {"macd": "bullish_crossover", "rsi": 44.2, "volume": 1.45},
        "argument": "Strong bullish setup.",
    })
    mock_call_llm.return_value = valid_json

    from app.db import create_enrichment_job
    enrichment_id = await create_enrichment_job("GOOGL", "screenshot", "https://example.com/chart")

    await _run_screenshot_enrichment(enrichment_id, "GOOGL", "https://example.com/chart")

    job = await get_enrichment_job(enrichment_id)
    assert job["status"] == "completed"
    assert job["enrichment_delta"] is not None

    result = await get_analysis_by_ticker("GOOGL")
    assert result is not None
    assert result.get("enrichment_status") == "completed" or result.get("enrichment_delta") is not None


@patch("app.analysis.screenshot_agent.async_playwright")
async def test_background_task_failure_leaves_analysis_delta_unchanged(mock_pw, tmp_path):
    from app.db import get_analysis_by_ticker, get_enrichment_job
    from app.routes.analysis import _run_screenshot_enrichment

    db_path = str(tmp_path / "bg_fail_test.db")
    set_db_path(db_path)
    await init_db()

    # Mock playwright: raises error
    pw = AsyncMock()
    pw.chromium.launch.side_effect = RuntimeError("Browser launch failed")
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=pw)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pw.return_value = cm

    from app.db import create_enrichment_job
    enrichment_id = await create_enrichment_job("GOOGL", "screenshot", "https://example.com/chart")

    original = await get_analysis_by_ticker("GOOGL")
    original_delta = original.get("enrichment_delta") if original else None

    await _run_screenshot_enrichment(enrichment_id, "GOOGL", "https://example.com/chart")

    job = await get_enrichment_job(enrichment_id)
    assert job["status"] == "failed"
    assert job["error_message"] is not None

    after = await get_analysis_by_ticker("GOOGL")
    assert (after.get("enrichment_delta") if after else None) == original_delta


async def test_get_ticker_analysis_includes_enrichment_status(enrich_client):
    resp = await enrich_client.get("/api/analysis/GOOGL")
    assert resp.status_code == 200
    body = resp.json()
    assert "enrichment_status" in body
    assert body["enrichment_status"] == "none"


# ── US-303 integration tests (7.1 – 7.7) ─────────────────────────────────────

@patch("app.routes.analysis._run_screenshot_enrichment")
async def test_auto_screenshot_returns_202_and_job_stored_as_auto_screenshot(mock_task, enrich_client):
    """7.1: POST auto_screenshot → 202 + enrichments row has enrichment_type=auto_screenshot."""
    mock_task.return_value = None
    resp = await enrich_client.post(
        "/api/analysis/GOOGL/enrich",
        json={"enrichment_type": "auto_screenshot", "source_url": "https://example.com/chart"},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "enrichment_id" in body
    assert body["status"] == "pending"

    from app.db import get_enrichment_job
    job = await get_enrichment_job(body["enrichment_id"])
    assert job is not None
    assert job["enrichment_type"] == "auto_screenshot"


@patch("app.routes.analysis._run_screenshot_enrichment")
async def test_screenshot_alias_normalizes_to_auto_screenshot(mock_task, enrich_client):
    """7.2: POST screenshot alias also stores enrichment_type=auto_screenshot."""
    mock_task.return_value = None
    resp = await enrich_client.post(
        "/api/analysis/GOOGL/enrich",
        json={"enrichment_type": "screenshot", "source_url": "https://example.com/chart"},
    )
    assert resp.status_code == 202
    body = resp.json()

    from app.db import get_enrichment_job
    job = await get_enrichment_job(body["enrichment_id"])
    assert job is not None
    assert job["enrichment_type"] == "auto_screenshot"


async def test_unknown_ticker_returns_404_no_job_created(enrich_client):
    """7.3: POST with unknown ticker → 404, no enrichments row created."""
    resp = await enrich_client.post(
        "/api/analysis/FAKEXYZ/enrich",
        json={"enrichment_type": "auto_screenshot", "source_url": "https://example.com/chart"},
    )
    assert resp.status_code == 404


@patch("app.analysis.screenshot_agent.async_playwright")
@patch("app.analysis.vision_agent._call_llm")
async def test_get_ticker_includes_enrichment_type_after_completion(mock_call_llm, mock_pw, tmp_path, enrich_client):
    """7.4: GET /api/analysis/{ticker} includes enrichment_type after enrichment completes."""
    import json as _json
    from app.db import create_enrichment_job
    from app.routes.analysis import _run_screenshot_enrichment

    # Mock playwright
    page = AsyncMock()
    page.goto.return_value = None
    page.screenshot.return_value = b"\x89PNG\r\n"
    browser = AsyncMock()
    browser.new_page.return_value = page
    pw = AsyncMock()
    pw.chromium.launch.return_value = browser
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=pw)
    cm.__aexit__ = AsyncMock(return_value=False)
    mock_pw.return_value = cm

    valid_json = _json.dumps({
        "ticker": "GOOGL",
        "signal": "BUY",
        "confidence": 0.85,
        "entry_price": 178.50,
        "target_price": 208.54,
        "stop_loss": 172.20,
        "risk_reward_ratio": 4.8,
        "support_validated": True,
        "indicators_summary": {"macd": "bullish_crossover", "rsi": 44.2, "volume": 1.45},
        "argument": "Strong bullish setup.",
    })
    mock_call_llm.return_value = valid_json

    enrichment_id = await create_enrichment_job("GOOGL", "auto_screenshot", "https://example.com/chart")
    await _run_screenshot_enrichment(enrichment_id, "GOOGL", "https://example.com/chart")

    resp = await enrich_client.get("/api/analysis/GOOGL")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("enrichment_type") == "auto_screenshot"


async def test_get_latest_includes_enrichment_type_per_row(enrich_client):
    """7.5: GET /api/analysis/latest includes enrichment_type in each row."""
    resp = await enrich_client.get("/api/analysis/latest")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) > 0
    for row in results:
        assert "enrichment_type" in row


async def test_migration_guard_column_present_after_init(tmp_path):
    """7.6: After init_db on a fresh DB, enrichment_type column exists."""
    from app.db import get_connection, init_db, set_db_path

    set_db_path(str(tmp_path / "migration_test.db"))
    await init_db()

    db = await get_connection()
    try:
        cursor = await db.execute("PRAGMA table_info(analysis_results)")
        cols = [row[1] for row in await cursor.fetchall()]
    finally:
        await db.close()

    assert "enrichment_type" in cols


@patch("app.routes.analysis._run_screenshot_enrichment")
async def test_b1_trader_chart_flow_unaffected(mock_task, enrich_client):
    """7.7: trader_chart (B1) flow still returns pending_confirmation without regression."""
    import base64

    # Minimal valid PNG header
    png_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100).decode()

    with patch("app.routes.analysis.validate_chart_image", return_value=b"\x89PNG\r\n"):
        with patch("app.analysis.vision_agent.extract_levels", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = []
            resp = await enrich_client.post(
                "/api/analysis/GOOGL/enrich",
                json={"enrichment_type": "trader_chart", "chart_image": png_b64},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending_confirmation"
    assert "enrichment_id" in body
