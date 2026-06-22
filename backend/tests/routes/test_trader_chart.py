"""Integration tests for the trader_chart enrichment and confirm endpoints."""

import base64
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.db import init_db, set_db_path
from app.routes.analysis import router as analysis_router

_VALID_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
_VALID_PNG_B64 = base64.b64encode(_VALID_PNG).decode()

_EXTRACTED_LEVELS = [{"type": "support", "price": 175.0, "confidence": 0.8}]
_LEVELS_JSON = json.dumps(_EXTRACTED_LEVELS)

_PATCH_EXTRACT = "app.analysis.vision_agent._call_extract_llm"


@pytest.fixture
async def client(tmp_path):
    db_path = str(tmp_path / "trader_chart_test.db")
    set_db_path(db_path)
    await init_db()

    app = FastAPI()
    app.include_router(analysis_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- Enrich endpoint tests ---

@patch(_PATCH_EXTRACT, new_callable=AsyncMock)
async def test_valid_chart_upload_returns_enrichment_id_and_levels(mock_call, client):
    mock_call.return_value = _LEVELS_JSON
    resp = await client.post(
        "/api/analysis/GOOGL/enrich",
        json={"enrichment_type": "trader_chart", "chart_image": _VALID_PNG_B64},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "enrichment_id" in body
    assert "extracted_levels" in body
    assert body["status"] == "pending_confirmation"


async def test_oversized_chart_returns_400(client):
    oversized = b"\x89PNG" + b"\x00" * (10 * 1024 * 1024 + 1)
    b64 = base64.b64encode(oversized).decode()
    resp = await client.post(
        "/api/analysis/GOOGL/enrich",
        json={"enrichment_type": "trader_chart", "chart_image": b64},
    )
    assert resp.status_code == 400


@patch(_PATCH_EXTRACT, new_callable=AsyncMock)
async def test_extraction_returns_empty_levels_still_200(mock_call, client):
    mock_call.return_value = "[]"
    resp = await client.post(
        "/api/analysis/GOOGL/enrich",
        json={"enrichment_type": "trader_chart", "chart_image": _VALID_PNG_B64},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["extracted_levels"] == []
    assert "enrichment_id" in body


async def test_no_analysis_row_returns_404(client):
    resp = await client.post(
        "/api/analysis/FAKEXYZ/enrich",
        json={"enrichment_type": "trader_chart", "chart_image": _VALID_PNG_B64},
    )
    assert resp.status_code == 404


# --- Confirm endpoint tests ---

async def _insert_pending_job(ticker: str, levels: list) -> str:
    from app.db import create_enrichment_job
    levels_json = json.dumps(levels)
    return await create_enrichment_job(
        ticker, "trader_chart", status="pending_confirmation", extracted_levels=levels_json
    )


async def test_confirm_two_levels_scores_correctly(client):
    levels = [
        {"type": "support", "price": 175.0, "confidence": 0.8},
        {"type": "resistance", "price": 208.0, "confidence": 0.7},
    ]
    enrichment_id = await _insert_pending_job("GOOGL", levels)

    resp = await client.post(
        "/api/analysis/GOOGL/enrich/confirm",
        json={"enrichment_id": enrichment_id, "confirmed_indices": [0, 1]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "enrichment_delta" in body
    assert "score_quant" in body
    assert "score_enriched" in body
    assert body["custom_levels_applied"] >= 0


async def test_confirm_zero_levels_delta_is_zero(client):
    enrichment_id = await _insert_pending_job("GOOGL", [
        {"type": "support", "price": 175.0, "confidence": 0.8},
    ])
    resp = await client.post(
        "/api/analysis/GOOGL/enrich/confirm",
        json={"enrichment_id": enrichment_id, "confirmed_indices": []},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["enrichment_delta"] == 0.0
    assert body["custom_levels_applied"] == 0


async def test_confirm_out_of_range_index_returns_422(client):
    enrichment_id = await _insert_pending_job("GOOGL", [
        {"type": "support", "price": 175.0, "confidence": 0.8},
    ])
    resp = await client.post(
        "/api/analysis/GOOGL/enrich/confirm",
        json={"enrichment_id": enrichment_id, "confirmed_indices": [5]},
    )
    assert resp.status_code == 422


async def test_confirm_unknown_enrichment_id_returns_404(client):
    resp = await client.post(
        "/api/analysis/GOOGL/enrich/confirm",
        json={"enrichment_id": "00000000-0000-0000-0000-000000000000", "confirmed_indices": [0]},
    )
    assert resp.status_code == 404


async def test_confirm_second_call_is_idempotent(client):
    enrichment_id = await _insert_pending_job("GOOGL", [
        {"type": "support", "price": 175.0, "confidence": 0.8},
    ])
    resp1 = await client.post(
        "/api/analysis/GOOGL/enrich/confirm",
        json={"enrichment_id": enrichment_id, "confirmed_indices": [0]},
    )
    assert resp1.status_code == 200

    resp2 = await client.post(
        "/api/analysis/GOOGL/enrich/confirm",
        json={"enrichment_id": enrichment_id, "confirmed_indices": [0]},
    )
    assert resp2.status_code == 200
