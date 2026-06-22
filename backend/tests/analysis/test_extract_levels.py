"""Tests for VisionAgent.extract_levels — level extraction from chart images."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.analysis.models import ExtractedLevel
from app.analysis.vision_agent import extract_levels

_VALID_LEVELS_JSON = json.dumps([
    {"type": "support", "price": 175.0, "confidence": 0.85},
    {"type": "resistance", "price": 185.0, "confidence": 0.72},
])

_SAMPLE_IMAGE = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64

_PATCH = "app.analysis.vision_agent._call_extract_llm"


@patch(_PATCH, new_callable=AsyncMock)
async def test_valid_json_array_parsed(mock_call):
    mock_call.return_value = _VALID_LEVELS_JSON
    result = await extract_levels(_SAMPLE_IMAGE)
    assert len(result) == 2
    assert all(isinstance(lv, ExtractedLevel) for lv in result)
    assert result[0].type == "support"
    assert result[0].price == pytest.approx(175.0)
    assert result[1].type == "resistance"


@patch(_PATCH, new_callable=AsyncMock)
async def test_malformed_json_returns_empty(mock_call):
    mock_call.return_value = "not valid json {{{"
    result = await extract_levels(_SAMPLE_IMAGE)
    assert result == []


@patch(_PATCH, new_callable=AsyncMock)
async def test_model_exception_returns_empty(mock_call):
    mock_call.side_effect = RuntimeError("model unavailable")
    result = await extract_levels(_SAMPLE_IMAGE)
    assert result == []


@patch(_PATCH, new_callable=AsyncMock)
async def test_timeout_returns_empty(mock_call):
    mock_call.side_effect = asyncio.TimeoutError()
    result = await extract_levels(_SAMPLE_IMAGE)
    assert result == []


@patch(_PATCH, new_callable=AsyncMock)
async def test_non_list_response_returns_empty(mock_call):
    mock_call.return_value = '{"type": "support"}'
    result = await extract_levels(_SAMPLE_IMAGE)
    assert result == []
