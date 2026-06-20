"""Tests for OrchestratorAgent — coordinates all analysis stages."""

import logging
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.analysis.models import AssetAnalysis, DataFetchError, TechnicalIndicators
from app.analysis.orchestrator import run_analysis

@pytest.fixture(autouse=True)
def _mock_vix_low():
    """Default: VIX fetch returns a calm value (gate inactive) and never hits the network.

    Individual tests override this by patching app.analysis.orchestrator._fetch_vix.
    """
    with patch(
        "app.analysis.orchestrator._fetch_vix", new_callable=AsyncMock, return_value=18.0
    ):
        yield


_INDICATORS = TechnicalIndicators(
    ticker="NVDA", current_price=890.0, macd_signal="bullish_crossover",
    macd_histogram=0.5, rsi=58.0, volume_ratio=1.3,
    support_1=875.0, support_2=860.0, resistance_1=920.0, resistance_2=940.0,
    sma_200=800.0,
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


_RANKED = _ANALYSIS.model_copy(update={"rank": 1, "score": 88.0})


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.get_connection", new_callable=AsyncMock)
@patch("app.analysis.orchestrator._get_prior_scores", new_callable=AsyncMock)
@patch("app.analysis.orchestrator._get_hit_rate", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.score_and_rank_with_errors")
@patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.analyze_asset", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_stage_logs_emitted(
    mock_save, mock_vision, mock_data,
    mock_score_rank, mock_hit_rate, mock_prior_scores, mock_get_conn,
    caplog,
):
    mock_save.return_value = []
    mock_data.return_value = {"NVDA": _INDICATORS}
    mock_vision.return_value = _ANALYSIS
    mock_hit_rate.return_value = (0.4, "db")
    mock_prior_scores.return_value = {}
    mock_score_rank.return_value = ([_RANKED], [])

    mock_conn = MagicMock()
    mock_conn.close = AsyncMock()
    mock_get_conn.return_value = mock_conn

    with caplog.at_level(logging.INFO, logger="app.analysis.orchestrator"):
        result = await run_analysis(["NVDA"])

    stage_records = [r for r in caplog.records if r.getMessage() == "stage_complete"]
    run_complete_records = [r for r in caplog.records if r.getMessage() == "run_complete"]

    assert len(stage_records) == 4
    assert len(run_complete_records) == 1

    for rec in stage_records:
        d = rec.__dict__
        for field in ("stage", "run_id", "duration_ms", "tickers_total", "tickers_ok", "tickers_error"):
            assert field in d, f"missing field '{field}' in stage_complete record"
        assert isinstance(d["duration_ms"], int)

    rc = run_complete_records[0].__dict__
    for field in ("run_id", "total_ms", "signals_generated", "error_count"):
        assert field in rc, f"missing field '{field}' in run_complete record"

    stage_run_ids = {r.__dict__["run_id"] for r in stage_records}
    assert len(stage_run_ids) == 1
    assert rc["run_id"] == next(iter(stage_run_ids))
    assert isinstance(rc["total_ms"], int)
    assert rc["total_ms"] >= 0
    assert result.run_id is not None


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_early_exit_run_complete(mock_save, mock_data, caplog):
    mock_save.return_value = []
    mock_data.return_value = {"NVDA": DataFetchError("NVDA")}

    with caplog.at_level(logging.INFO, logger="app.analysis.orchestrator"):
        result = await run_analysis(["NVDA"])

    stage_records = [r for r in caplog.records if r.getMessage() == "stage_complete"]
    run_complete_records = [r for r in caplog.records if r.getMessage() == "run_complete"]

    assert len(stage_records) == 1
    assert len(run_complete_records) == 1
    assert run_complete_records[0].__dict__.get("signals_generated") == 0
    assert result.assets == []


# ── US-103 tests ─────────────────────────────────────────────────────────────

@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.get_analysis_by_ticker", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_orchestrator_errors_include_reason(mock_save, mock_data, mock_cached):
    """DataFetchError.reason is propagated into errors[n]['reason'].

    When no cached result is available the error stays in the errors list.
    """
    mock_save.return_value = []
    mock_data.return_value = {
        "AAPL": DataFetchError("AAPL", reason="rate_limited"),
    }
    mock_cached.return_value = None  # no cached row → staleness fallback skipped

    result = await run_analysis(["AAPL"])

    assert len(result.errors) == 1
    assert result.errors[0]["ticker"] == "AAPL"
    assert result.errors[0]["reason"] == "rate_limited"


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.get_analysis_by_ticker", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_staleness_fallback_uses_cached_result(mock_save, mock_data, mock_cached):
    """Rate-limited ticker with a <24h cached result is recovered as is_stale=True."""
    mock_save.return_value = []
    mock_data.return_value = {
        "AAPL": DataFetchError("AAPL", reason="rate_limited"),
    }
    two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    mock_cached.return_value = {
        "ticker": "AAPL",
        "signal": "BUY",
        "confidence": 0.8,
        "entry_price": 150.0,
        "target_price": 180.0,
        "stop_loss": 140.0,
        "risk_reward_ratio": 3.0,
        "support_validated": True,
        "indicators_summary": {},
        "argument": "Cached signal",
        "analyzed_at": two_hours_ago,
        "score": 80.0,
        "rank": 1,
    }

    result = await run_analysis(["AAPL"])

    assert "AAPL" in result.stale_tickers
    stale = next((a for a in result.assets if a.ticker == "AAPL"), None)
    assert stale is not None
    assert stale.is_stale is True
    # Recovered stale assets are removed from errors
    assert not any(e["ticker"] == "AAPL" for e in result.errors)


# ── US-203 regime gate tests ─────────────────────────────────────────────────

_INDICATORS_BELOW_SMA = TechnicalIndicators(
    ticker="NVDA", current_price=750.0, macd_signal="bullish_crossover",
    macd_histogram=0.5, rsi=58.0, volume_ratio=1.3,
    support_1=740.0, support_2=720.0, resistance_1=780.0, resistance_2=800.0,
    sma_200=800.0,
)

_INDICATORS_NO_SMA = TechnicalIndicators(
    ticker="NVDA", current_price=750.0, macd_signal="bullish_crossover",
    macd_histogram=0.5, rsi=58.0, volume_ratio=1.3,
    support_1=740.0, support_2=720.0, resistance_1=780.0, resistance_2=800.0,
    sma_200=None,
)


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.analyze_asset", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_regime_sma200_below_suppresses_buy(mock_save, mock_vision, mock_data):
    """Ticker with current_price <= sma_200 is suppressed before Stage 2."""
    mock_save.return_value = []
    mock_data.return_value = {"NVDA": _INDICATORS_BELOW_SMA}
    mock_vision.return_value = _ANALYSIS  # should never be reached for NVDA

    result = await run_analysis(["NVDA"])

    nvda = next((a for a in result.assets if a.ticker == "NVDA"), None)
    assert nvda is not None
    assert nvda.signal == "AVOID"
    assert nvda.rank is None
    assert nvda.rank_exclusion_reason == "regime_bearish"
    assert nvda not in result.top_5
    # Vision/LLM stage was never invoked for the excluded ticker
    mock_vision.assert_not_called()
    # Not persisted to DB — never appears in any saved batch
    for call in mock_save.call_args_list:
        saved_rows = call.args[0]
        assert all(r["ticker"] != "NVDA" for r in saved_rows)


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.analyze_asset", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_regime_sma200_above_passes_through(mock_save, mock_vision, mock_data):
    """Ticker with current_price > sma_200 proceeds to Stage 2+."""
    mock_save.return_value = []
    mock_data.return_value = {"NVDA": _INDICATORS}  # price 890 > sma 800
    mock_vision.return_value = _ANALYSIS

    result = await run_analysis(["NVDA"])

    mock_vision.assert_called_once()
    nvda = next((a for a in result.assets if a.ticker == "NVDA"), None)
    assert nvda is not None
    assert nvda.rank_exclusion_reason != "regime_bearish"


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.analyze_asset", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_sma200_none_passes_through(mock_save, mock_vision, mock_data):
    """sma_200 is None → fail open, ticker not excluded."""
    mock_save.return_value = []
    mock_data.return_value = {"NVDA": _INDICATORS_NO_SMA}
    mock_vision.return_value = _ANALYSIS

    result = await run_analysis(["NVDA"])

    mock_vision.assert_called_once()
    nvda = next((a for a in result.assets if a.ticker == "NVDA"), None)
    assert nvda is not None
    assert nvda.rank_exclusion_reason != "regime_bearish"


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.ANALYSIS_VIX_THRESHOLD", 25.0)
@patch("app.analysis.orchestrator._fetch_vix", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.analyze_asset", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_vix_gate_active_suppresses_buys(mock_save, mock_vision, mock_data, mock_vix):
    """VIX=27.0 > threshold 25.0 → all BUY converted to AVOID, top_5 empty."""
    mock_save.return_value = []
    mock_vix.return_value = 27.0
    mock_data.return_value = {"NVDA": _INDICATORS}
    mock_vision.return_value = _ANALYSIS  # signal=BUY

    result = await run_analysis(["NVDA"])

    assert result.regime_gate_active is True
    assert result.vix_value == 27.0
    assert result.top_5 == []
    nvda = next((a for a in result.assets if a.ticker == "NVDA"), None)
    assert nvda is not None
    assert nvda.signal == "AVOID"
    assert nvda.rank_exclusion_reason == "regime_vix"


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.ANALYSIS_VIX_THRESHOLD", 25.0)
@patch("app.analysis.orchestrator._fetch_vix", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.analyze_asset", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_vix_gate_inactive_below_threshold(mock_save, mock_vision, mock_data, mock_vix):
    """VIX=20.0 < threshold 25.0 → BUY signals preserved."""
    mock_save.return_value = []
    mock_vix.return_value = 20.0
    mock_data.return_value = {"NVDA": _INDICATORS}
    mock_vision.return_value = _ANALYSIS

    result = await run_analysis(["NVDA"])

    assert result.regime_gate_active is False
    assert result.vix_value == 20.0
    nvda = next((a for a in result.assets if a.ticker == "NVDA"), None)
    assert nvda is not None
    assert nvda.signal == "BUY"
    assert nvda.rank_exclusion_reason != "regime_vix"


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.ANALYSIS_VIX_THRESHOLD", 25.0)
@patch("app.analysis.orchestrator._fetch_vix", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.analyze_asset", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_vix_fetch_failure_fail_open(mock_save, mock_vision, mock_data, mock_vix, caplog):
    """VIX fetch returns None → gate inactive, BUY preserved."""
    mock_save.return_value = []
    mock_vix.return_value = None
    mock_data.return_value = {"NVDA": _INDICATORS}
    mock_vision.return_value = _ANALYSIS

    result = await run_analysis(["NVDA"])

    assert result.regime_gate_active is False
    assert result.vix_value is None
    nvda = next((a for a in result.assets if a.ticker == "NVDA"), None)
    assert nvda is not None
    assert nvda.signal == "BUY"


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.ANALYSIS_VIX_THRESHOLD", 999.0)
@patch("app.analysis.orchestrator._fetch_vix", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.analyze_asset", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_vix_gate_disabled_at_999(mock_save, mock_vision, mock_data, mock_vix):
    """ANALYSIS_VIX_THRESHOLD=999 → gate inactive regardless of VIX value."""
    mock_save.return_value = []
    mock_vix.return_value = 50.0  # extreme, but threshold disabled
    mock_data.return_value = {"NVDA": _INDICATORS}
    mock_vision.return_value = _ANALYSIS

    result = await run_analysis(["NVDA"])

    assert result.regime_gate_active is False
    nvda = next((a for a in result.assets if a.ticker == "NVDA"), None)
    assert nvda is not None
    assert nvda.signal == "BUY"


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.ANALYSIS_VIX_THRESHOLD", 25.0)
@patch("app.analysis.orchestrator._fetch_vix", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.get_analysis_by_ticker", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.fetch_indicators_batch", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_stale_buy_suppressed_by_vix_gate(mock_save, mock_data, mock_cached, mock_vix):
    """A stale fallback BUY asset is converted to AVOID when the VIX gate is active."""
    mock_save.return_value = []
    mock_vix.return_value = 30.0
    mock_data.return_value = {"AAPL": DataFetchError("AAPL", reason="rate_limited")}
    two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    mock_cached.return_value = {
        "ticker": "AAPL",
        "signal": "BUY",
        "confidence": 0.8,
        "entry_price": 150.0,
        "target_price": 180.0,
        "stop_loss": 140.0,
        "risk_reward_ratio": 3.0,
        "support_validated": True,
        "indicators_summary": {},
        "argument": "Cached signal",
        "analyzed_at": two_hours_ago,
        "score": 80.0,
        "rank": 1,
    }

    result = await run_analysis(["AAPL"])

    assert result.regime_gate_active is True
    aapl = next((a for a in result.assets if a.ticker == "AAPL"), None)
    assert aapl is not None
    assert aapl.signal == "AVOID"
    assert aapl.rank_exclusion_reason == "regime_vix"
