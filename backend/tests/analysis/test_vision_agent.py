"""Tests for VisionAgent — LLM vision analysis."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.analysis.models import AssetAnalysis, TechnicalIndicators
from app.analysis.vision_agent import analyze_asset

_INDICATORS = TechnicalIndicators(
    ticker="NVDA",
    current_price=890.0,
    macd_signal="bullish_crossover",
    macd_histogram=0.42,
    rsi=58.0,
    volume_ratio=1.23,
    support_1=875.0,
    support_2=860.0,
    resistance_1=920.0,
    resistance_2=940.0,
)

_VALID_LLM_JSON = json.dumps({
    "ticker": "NVDA",
    "signal": "BUY",
    "confidence": 0.85,
    "entry_price": 890.0,
    "target_price": 920.0,
    "stop_loss": 875.0,
    "risk_reward_ratio": 2.0,
    "support_validated": True,
    "indicators_summary": {"macd": "bullish_crossover", "rsi": 58.0, "volume": "above_avg"},
    "argument": "Strong bullish setup with MACD crossover.",
})

_MOCK_PNG = b"\x89PNG\r\n"


def _make_call_llm_mock(json_content: str) -> AsyncMock:
    return AsyncMock(return_value=json_content)


@patch("app.analysis.vision_agent._call_llm")
async def test_analyze_asset_returns_asset_analysis(mock_call_llm):
    mock_call_llm.return_value = _VALID_LLM_JSON
    result = await analyze_asset(_INDICATORS, _MOCK_PNG)
    assert isinstance(result, AssetAnalysis)
    assert result.ticker == "NVDA"
    assert result.signal == "BUY"
    assert result.confidence == pytest.approx(0.85)


@patch("app.analysis.vision_agent._call_llm")
async def test_analyze_asset_without_screenshot_still_returns_result(mock_call_llm):
    mock_call_llm.return_value = _VALID_LLM_JSON
    result = await analyze_asset(_INDICATORS, None)
    assert isinstance(result, AssetAnalysis)
    assert result.support_validated is False  # forced False when no screenshot


@patch("app.analysis.vision_agent._call_llm")
async def test_malformed_llm_response_returns_avoid(mock_call_llm):
    mock_call_llm.return_value = "not valid json {{{{"
    result = await analyze_asset(_INDICATORS, _MOCK_PNG)
    assert result.signal == "AVOID"
    assert result.confidence == 0.0
    assert "unavailable" in result.argument.lower()


@patch("app.analysis.vision_agent._call_llm")
async def test_llm_exception_returns_avoid(mock_call_llm):
    mock_call_llm.side_effect = Exception("OpenRouter timeout")
    result = await analyze_asset(_INDICATORS, _MOCK_PNG)
    assert result.signal == "AVOID"
    assert result.confidence == 0.0


@patch("app.analysis.vision_agent._call_llm")
async def test_screenshot_bytes_parameter_accepted(mock_call_llm):
    """screenshot_bytes kwarg takes priority; the call succeeds."""
    mock_call_llm.return_value = _VALID_LLM_JSON
    result = await analyze_asset(_INDICATORS, screenshot_bytes=_MOCK_PNG)
    assert isinstance(result, AssetAnalysis)
    assert result.ticker == "NVDA"


@patch("app.analysis.vision_agent._call_llm")
async def test_text_only_fallback_when_no_screenshot(mock_call_llm):
    """Without screenshot_bytes, falls back to text-only (support_validated forced False)."""
    mock_call_llm.return_value = _VALID_LLM_JSON
    result = await analyze_asset(_INDICATORS, screenshot_bytes=None)
    assert result.support_validated is False
