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
