"""Tests for OrchestratorAgent — coordinates all analysis stages."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from app.analysis.models import AssetAnalysis, DataFetchError, TechnicalIndicators
from app.analysis.orchestrator import run_analysis

_INDICATORS = TechnicalIndicators(
    ticker="NVDA", current_price=890.0, macd_signal="bullish_crossover",
    macd_histogram=0.5, rsi=58.0, volume_ratio=1.3,
    support_1=875.0, support_2=860.0, resistance_1=920.0, resistance_2=940.0,
)

_ANALYSIS = AssetAnalysis(
    ticker="NVDA", signal="BUY", confidence=0.85, entry_price=890.0,
    target_price=920.0, stop_loss=875.0, risk_reward_ratio=4.0,
    support_validated=True, indicators_summary={"macd": "bullish_crossover", "rsi": 58.0, "volume": "above_avg"},
    argument="Strong bullish setup.",
)


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.analyze_asset", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_run_analysis_returns_analysis_result(mock_save, mock_vision, mock_data):
    mock_save.return_value = []
    mock_data.return_value = {"NVDA": _INDICATORS}
    mock_vision.return_value = _ANALYSIS.model_copy(update={"rank": 1, "score": 88.0})

    result = await run_analysis(["NVDA"])

    assert result.run_id is not None
    assert len(result.assets) == 1
    assert result.errors == []
    mock_save.assert_called_once()


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.analyze_asset", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_data_fetch_error_is_isolated(mock_save, mock_vision, mock_data):
    """A DataFetchError for one ticker should not abort the whole run."""
    mock_save.return_value = []
    mock_data.return_value = {
        "FAKE": DataFetchError("FAKE"),
        "NVDA": _INDICATORS,
    }
    mock_vision.return_value = _ANALYSIS

    result = await run_analysis(["FAKE", "NVDA"])

    assert len(result.errors) == 1
    assert result.errors[0]["ticker"] == "FAKE"
    assert len(result.assets) == 1  # NVDA succeeded


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.analyze_asset", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_duration_seconds_is_positive(mock_save, mock_vision, mock_data):
    mock_save.return_value = []
    mock_data.return_value = {"NVDA": _INDICATORS}
    mock_vision.return_value = _ANALYSIS

    result = await run_analysis(["NVDA"])
    assert result.duration_seconds >= 0


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.analyze_asset", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_orchestrator_surfaces_write_errors(mock_save, mock_vision, mock_data):
    """DB write errors returned by save_analysis_results appear in AnalysisResult.errors."""
    mock_save.return_value = [{"ticker": "NVDA", "error_message": "disk I/O error"}]
    mock_data.return_value = {"NVDA": _INDICATORS}
    mock_vision.return_value = _ANALYSIS

    result = await run_analysis(["NVDA"])

    assert any(e["ticker"] == "NVDA" for e in result.errors)
    assert any("disk I/O error" in e.get("error_message", "") for e in result.errors)
