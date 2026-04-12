"""DataAgent — fetches historical prices and computes technical indicators."""

import asyncio
import logging

import pandas as pd
import pandas_ta as ta
import yfinance as yf

from .models import DataFetchError, TechnicalIndicators

logger = logging.getLogger(__name__)


def _compute_indicators(ticker: str, df: pd.DataFrame) -> TechnicalIndicators:
    """Compute MACD, RSI, volume ratio, and pivot points from OHLCV DataFrame."""
    if df.empty or len(df) < 30:
        raise DataFetchError(ticker)

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # MACD (12, 26, 9)
    macd_df = ta.macd(close, fast=12, slow=26, signal=9)
    if macd_df is None or macd_df.empty:
        raise DataFetchError(ticker)

    macd_col = [c for c in macd_df.columns if c.startswith("MACD_")][0]
    signal_col = [c for c in macd_df.columns if c.startswith("MACDs_")][0]
    hist_col = [c for c in macd_df.columns if c.startswith("MACDh_")][0]

    macd_val = float(macd_df[macd_col].iloc[-1])
    signal_val = float(macd_df[signal_col].iloc[-1])
    hist_val = float(macd_df[hist_col].iloc[-1])

    prev_hist = float(macd_df[hist_col].iloc[-2]) if len(macd_df) >= 2 else 0.0

    if macd_val > signal_val and hist_val > 0 and prev_hist <= 0:
        macd_signal = "bullish_crossover"
    elif macd_val < signal_val and hist_val < 0 and prev_hist >= 0:
        macd_signal = "bearish_crossover"
    else:
        macd_signal = "neutral"

    # RSI (14)
    rsi_series = ta.rsi(close, length=14)
    rsi = float(rsi_series.iloc[-1]) if rsi_series is not None else 50.0

    # Volume ratio: current vs 20-day SMA
    vol_sma = ta.sma(volume, length=20)
    current_vol = float(volume.iloc[-1])
    sma_vol = float(vol_sma.iloc[-1]) if vol_sma is not None else current_vol
    volume_ratio = current_vol / sma_vol if sma_vol > 0 else 1.0

    # Pivot points: 20-period and 40-period ranges
    support_1 = float(low.iloc[-20:].min())
    resistance_1 = float(high.iloc[-20:].max())
    support_2 = float(low.iloc[-40:].min()) if len(low) >= 40 else support_1
    resistance_2 = float(high.iloc[-40:].max()) if len(high) >= 40 else resistance_1

    current_price = float(close.iloc[-1])

    return TechnicalIndicators(
        ticker=ticker,
        current_price=current_price,
        macd_signal=macd_signal,
        macd_histogram=round(hist_val, 4),
        rsi=round(rsi, 2),
        volume_ratio=round(volume_ratio, 3),
        support_1=round(support_1, 2),
        support_2=round(support_2, 2),
        resistance_1=round(resistance_1, 2),
        resistance_2=round(resistance_2, 2),
    )


async def fetch_indicators(ticker: str) -> TechnicalIndicators:
    """Fetch 60 days of OHLCV data and compute technical indicators.

    Raises DataFetchError if no data is available for the ticker.
    """
    logger.debug("Fetching indicators for %s", ticker)
    df = await asyncio.to_thread(
        yf.download, ticker, period="3mo", interval="1d", progress=False, auto_adjust=True
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return _compute_indicators(ticker, df)
