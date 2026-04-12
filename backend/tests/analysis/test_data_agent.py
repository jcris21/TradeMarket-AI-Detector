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
