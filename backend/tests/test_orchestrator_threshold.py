"""Tests for orchestrator 70% minimum viable run threshold and save_analysis_run gating."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.analysis.models import AssetAnalysis, DataFetchError, TechnicalIndicators
from app.analysis.orchestrator import run_analysis


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_indicator(ticker: str) -> TechnicalIndicators:
    return TechnicalIndicators(
        ticker=ticker,
        current_price=100.0,
        macd_signal="neutral",
        macd_histogram=0.0,
        rsi=50.0,
        volume_ratio=1.0,
        support_1=90.0,
        support_2=85.0,
        resistance_1=110.0,
        resistance_2=115.0,
    )


def _make_batch_results(tickers: list[str], success_count: int) -> dict:
    results = {}
    for i, t in enumerate(tickers):
        if i < success_count:
            results[t] = _make_indicator(t)
        else:
            err = DataFetchError(t)
            err.duration_ms = 50
            results[t] = err
    return results


def _make_asset(ticker: str) -> AssetAnalysis:
    return AssetAnalysis(
        ticker=ticker,
        signal="BUY",
        confidence=0.75,
        entry_price=100.0,
        target_price=120.0,
        stop_loss=90.0,
        risk_reward_ratio=2.0,
        support_validated=True,
        indicators_summary={},
        argument="test",
        score=70.0,
        rank=1,
    )


# ── Threshold tests ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_503_when_below_threshold():
    """69/100 successful tickers should raise HTTPException(503)."""
    tickers = [f"T{i:03d}" for i in range(100)]
    batch = _make_batch_results(tickers, success_count=69)

    with patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock) as mock_batch:
        mock_batch.return_value = batch
        with pytest.raises(HTTPException) as exc_info:
            await run_analysis(tickers)

    assert exc_info.value.status_code == 503
    assert "69/100" in exc_info.value.detail


@pytest.mark.asyncio
async def test_no_503_at_exactly_threshold():
    """70/100 successful tickers should proceed without raising HTTPException."""
    tickers = [f"T{i:03d}" for i in range(100)]
    batch = _make_batch_results(tickers, success_count=70)
    successful_tickers = [t for t in tickers[:70]]

    mock_asset = _make_asset(successful_tickers[0])
    mock_db = AsyncMock()

    with patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock) as mock_batch, \
         patch("app.analysis.orchestrator.analyze_asset", new_callable=AsyncMock) as mock_vision, \
         patch("app.analysis.orchestrator.get_connection", new_callable=AsyncMock, return_value=mock_db), \
         patch("app.analysis.orchestrator._get_hit_rate", new_callable=AsyncMock, return_value=(0.35, "assumed")), \
         patch("app.analysis.orchestrator._get_prior_scores", new_callable=AsyncMock, return_value={}), \
         patch("app.analysis.orchestrator.score_and_rank_with_errors", return_value=([mock_asset], [])), \
         patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock, return_value=[]), \
         patch("app.analysis.orchestrator.save_analysis_run", new_callable=AsyncMock):
        mock_batch.return_value = batch
        mock_vision.return_value = mock_asset

        result = await run_analysis(tickers)

    assert result is not None


@pytest.mark.asyncio
async def test_save_analysis_run_not_called_on_503():
    """save_analysis_run must NOT be called when the run raises HTTP 503."""
    tickers = [f"T{i:03d}" for i in range(100)]
    batch = _make_batch_results(tickers, success_count=69)

    with patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock) as mock_batch, \
         patch("app.analysis.orchestrator.save_analysis_run", new_callable=AsyncMock) as mock_save_run:
        mock_batch.return_value = batch
        with pytest.raises(HTTPException) as exc_info:
            await run_analysis(tickers)

    assert exc_info.value.status_code == 503
    mock_save_run.assert_not_called()
