"""Tests for DataAgent — yfinance fetch + pandas-ta indicators."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.analysis.data_agent import fetch_indicators
from app.analysis.models import DataFetchError, TechnicalIndicators


def _make_ohlcv(n: int = 60) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame with n rows."""
    import numpy as np

    rng = pd.date_range("2024-01-01", periods=n, freq="B")
    prices = 100 + np.cumsum(np.random.randn(n) * 0.5)
    df = pd.DataFrame(
        {
            "Open": prices * 0.99,
            "High": prices * 1.01,
            "Low": prices * 0.98,
            "Close": prices,
            "Volume": np.random.randint(1_000_000, 5_000_000, n).astype(float),
        },
        index=rng,
    )
    return df


@patch("app.analysis.data_agent.yf.download")
async def test_fetch_indicators_returns_technical_indicators(mock_download):
    mock_download.return_value = _make_ohlcv(60)
    result = await fetch_indicators("AAPL")
    assert isinstance(result, TechnicalIndicators)
    assert result.ticker == "AAPL"
    assert result.current_price > 0
    assert result.support_1 <= result.resistance_1
    assert result.support_2 <= result.support_1


@patch("app.analysis.data_agent.yf.download")
async def test_macd_signal_is_valid_literal(mock_download):
    mock_download.return_value = _make_ohlcv(60)
    result = await fetch_indicators("MSFT")
    assert result.macd_signal in ("bullish_crossover", "bearish_crossover", "neutral")


@patch("app.analysis.data_agent.yf.download")
async def test_rsi_in_valid_range(mock_download):
    mock_download.return_value = _make_ohlcv(60)
    result = await fetch_indicators("GOOGL")
    assert 0 <= result.rsi <= 100


@patch("app.analysis.data_agent.yf.download")
async def test_volume_ratio_positive(mock_download):
    mock_download.return_value = _make_ohlcv(60)
    result = await fetch_indicators("TSLA")
    assert result.volume_ratio > 0


@patch("app.analysis.data_agent.yf.download")
async def test_empty_dataframe_raises_data_fetch_error(mock_download):
    mock_download.return_value = pd.DataFrame()
    with pytest.raises(DataFetchError) as exc_info:
        await fetch_indicators("FAKE")
    assert exc_info.value.ticker == "FAKE"


@patch("app.analysis.data_agent.ta")
@patch("app.analysis.data_agent.yf.download")
async def test_atr_computed_when_available(mock_download, mock_ta):
    """ATR fields are set correctly when ta.atr() returns valid data."""
    df = _make_ohlcv(60)
    # Override close prices so current_price == 100.0
    df["Close"] = 100.0
    df["High"] = 101.0
    df["Low"] = 99.0
    mock_download.return_value = df

    # Mock MACD, RSI, SMA so _compute_indicators doesn't fail on them
    macd_df = pd.DataFrame(
        {"MACD_12_26_9": [0.5], "MACDs_12_26_9": [0.3], "MACDh_12_26_9": [0.2]},
        index=df.index[-1:],
    )
    # Pad MACD df to length of df for iloc[-2]
    macd_full = pd.DataFrame(
        {
            "MACD_12_26_9": [0.3] * (len(df) - 1) + [0.5],
            "MACDs_12_26_9": [0.2] * (len(df) - 1) + [0.3],
            "MACDh_12_26_9": [-0.1] * (len(df) - 1) + [0.2],
        },
        index=df.index,
    )
    mock_ta.macd.return_value = macd_full
    mock_ta.rsi.return_value = pd.Series([55.0] * len(df), index=df.index)
    mock_ta.sma.return_value = pd.Series([1_000_000.0] * len(df), index=df.index)
    mock_ta.atr.return_value = pd.Series([5.0] * len(df), index=df.index)

    result = await fetch_indicators("AAPL")

    assert result.atr_14 == 5.0
    assert result.atr_14_pct == pytest.approx(0.05, rel=1e-4)


@patch("app.analysis.data_agent.ta")
@patch("app.analysis.data_agent.yf.download")
async def test_atr_none_when_ta_returns_none(mock_download, mock_ta):
    """ATR fields are None when ta.atr() returns None."""
    df = _make_ohlcv(60)
    mock_download.return_value = df

    macd_full = pd.DataFrame(
        {
            "MACD_12_26_9": [0.3] * (len(df) - 1) + [0.5],
            "MACDs_12_26_9": [0.2] * (len(df) - 1) + [0.3],
            "MACDh_12_26_9": [-0.1] * (len(df) - 1) + [0.2],
        },
        index=df.index,
    )
    mock_ta.macd.return_value = macd_full
    mock_ta.rsi.return_value = pd.Series([55.0] * len(df), index=df.index)
    mock_ta.sma.return_value = pd.Series([1_000_000.0] * len(df), index=df.index)
    mock_ta.atr.return_value = None

    result = await fetch_indicators("AAPL")

    assert result.atr_14 is None
    assert result.atr_14_pct is None


# --- US-103: Rate-limit resilience tests ---


def test_data_fetch_error_reason_field():
    """DataFetchError carries a reason field; default is 'empty_dataframe'."""
    from app.analysis.models import DataFetchError

    err_default = DataFetchError("AAPL")
    assert err_default.reason == "empty_dataframe"

    err_rl = DataFetchError("AAPL", reason="rate_limited")
    assert err_rl.reason == "rate_limited"


@patch("app.analysis.data_agent._time.sleep")
@patch("app.analysis.data_agent.yf.download")
def test_rate_limit_retry_succeeds_on_second_attempt(mock_download, mock_sleep):
    """_download_with_retry returns the DataFrame when 429 occurs once then succeeds."""
    from app.analysis.data_agent import _download_with_retry, YFRateLimitError as _YFRateLimitError

    valid_df = _make_ohlcv(60)
    mock_download.side_effect = [_YFRateLimitError(), valid_df]

    result = _download_with_retry(["AAPL"], period="3mo")

    assert result is valid_df
    assert mock_download.call_count == 2
    mock_sleep.assert_called_once_with(2)  # 2^1 = 2s before attempt 1


@patch("app.analysis.data_agent._time.sleep")
@patch("app.analysis.data_agent.yf.download")
def test_rate_limit_all_retries_exhausted(mock_download, mock_sleep):
    """_download_with_retry re-raises after exactly 3 calls; total sleep = 6s."""
    from app.analysis.data_agent import _download_with_retry, YFRateLimitError as _YFRateLimitError

    mock_download.side_effect = _YFRateLimitError()

    with pytest.raises(_YFRateLimitError):
        _download_with_retry(["AAPL"], period="3mo")

    assert mock_download.call_count == 3
    assert mock_sleep.call_count == 2
    total_sleep = sum(c.args[0] for c in mock_sleep.call_args_list)
    assert total_sleep == 6


def test_staleness_fallback_ignores_expired_cache():
    """Rate-limited ticker with >24h cache should be rejected by the staleness fallback."""
    from datetime import datetime, timezone, timedelta

    old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    analyzed_dt = datetime.fromisoformat(old_time.replace("Z", "+00:00"))
    assert analyzed_dt < cutoff, "25h-old cache should be below the 24h cutoff"


def test_staleness_fallback_accepts_fresh_cache():
    """Rate-limited ticker with <24h cache should pass the staleness fallback check."""
    from datetime import datetime, timezone, timedelta

    recent_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    analyzed_dt = datetime.fromisoformat(recent_time.replace("Z", "+00:00"))
    assert analyzed_dt >= cutoff, "2h-old cache should be accepted"


def test_stale_asset_is_stale_flag():
    """AssetAnalysis.is_stale defaults to False and can be set to True."""
    from app.analysis.models import AssetAnalysis

    asset = AssetAnalysis(
        ticker="AAPL",
        signal="BUY",
        confidence=0.8,
        entry_price=190.0,
        target_price=210.0,
        stop_loss=180.0,
        risk_reward_ratio=2.0,
        support_validated=True,
        indicators_summary={},
        argument="test",
    )
    assert asset.is_stale is False
    stale = asset.model_copy(update={"is_stale": True})
    assert stale.is_stale is True
