"""DataAgent — fetches historical prices and computes technical indicators."""

import asyncio
import logging
import os
import time as _time

import pandas as pd
import yfinance as yf

try:
    import pandas_ta as ta
except ImportError:
    ta = None  # type: ignore[assignment]

from .models import DataFetchError, TechnicalIndicators

logger = logging.getLogger(__name__)


def _swing_levels(
    high: pd.Series, low: pd.Series, n: int = 5
) -> tuple[list[float], list[float]]:
    """Fractal swing detector: returns (support_lows, resistance_highs).

    A swing high at bar i means high[i] is the maximum over [i-n, i+n].
    A swing low at bar i means low[i] is the minimum over [i-n, i+n].
    """
    arr_h = high.to_numpy()
    arr_l = low.to_numpy()
    supports: list[float] = []
    resistances: list[float] = []
    for i in range(n, len(arr_h) - n):
        if arr_h[i] == arr_h[i - n : i + n + 1].max():
            resistances.append(float(arr_h[i]))
        if arr_l[i] == arr_l[i - n : i + n + 1].min():
            supports.append(float(arr_l[i]))
    return supports, resistances


def _volume_profile_levels(
    close: pd.Series, volume: pd.Series, n_bins: int = 30, top_n: int = 6
) -> list[float]:
    """Volume profile: price levels where the most volume traded.

    Returns up to top_n price levels sorted ascending.
    """
    p_min, p_max = float(close.min()), float(close.max())
    if p_max <= p_min:
        return []
    bin_size = (p_max - p_min) / n_bins
    vol_acc: dict[int, float] = {}
    price_acc: dict[int, float] = {}
    for p, v in zip(close.to_numpy(), volume.to_numpy()):
        b = min(int((float(p) - p_min) / bin_size), n_bins - 1)
        vol_acc[b] = vol_acc.get(b, 0.0) + float(v)
        price_acc[b] = float(p)
    top_bins = sorted(vol_acc, key=lambda b: vol_acc[b], reverse=True)[:top_n]
    return sorted(price_acc[b] for b in top_bins)


def _cluster_levels(levels: list[float], threshold_pct: float = 0.015) -> list[float]:
    """Merge levels within threshold_pct of each other into their average."""
    if not levels:
        return []
    merged: list[float] = []
    group: list[float] = [levels[0]]
    for lvl in levels[1:]:
        if (lvl - group[-1]) / group[-1] <= threshold_pct:
            group.append(lvl)
        else:
            merged.append(sum(group) / len(group))
            group = [lvl]
    merged.append(sum(group) / len(group))
    return merged


def _pick_nearest(levels: list[float], price: float, above: bool, n: int = 2) -> list[float]:
    """Select the n closest clustered levels above or below price."""
    gap = price * 0.003  # ignore levels within 0.3% of current price
    if above:
        candidates = sorted(l for l in levels if l > price + gap)
    else:
        candidates = sorted((l for l in levels if l < price - gap), reverse=True)
    return candidates[:n]


def _compute_indicators(ticker: str, df: pd.DataFrame) -> TechnicalIndicators:
    """Compute MACD, RSI, volume ratio, and S/R levels from OHLCV DataFrame."""
    if ta is None:
        raise DataFetchError("pandas-ta is not installed (requires Python 3.12+)")
    if df.empty or len(df) < 60:
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

    current_price = float(close.iloc[-1])
    if current_price <= 0:
        raise DataFetchError(ticker)

    # ATR (14) — absolute and as % of current price
    atr_14: float | None = None
    atr_14_pct: float | None = None
    try:
        atr_series = ta.atr(high, low, close, length=14)
        if atr_series is not None and not pd.isna(atr_series.iloc[-1]) and current_price > 0:
            atr_14 = round(float(atr_series.iloc[-1]), 4)
            atr_14_pct = round(atr_14 / current_price, 6)
    except Exception:
        atr_14 = None
        atr_14_pct = None

    # Support / Resistance — swing levels + volume profile, clustered
    swing_sup, swing_res = _swing_levels(high, low, n=5)
    vp_levels = _volume_profile_levels(close, volume, n_bins=30, top_n=6)

    all_supports = _cluster_levels(sorted(swing_sup + [l for l in vp_levels if l < current_price]))
    all_resistances = _cluster_levels(sorted(swing_res + [l for l in vp_levels if l > current_price]))

    nearest_sup = _pick_nearest(all_supports, current_price, above=False, n=2)
    nearest_res = _pick_nearest(all_resistances, current_price, above=True, n=2)

    # Hard fallbacks using period range lows/highs if not enough levels found
    if len(nearest_sup) < 1:
        nearest_sup = [float(low.iloc[-20:].min())]
    if len(nearest_sup) < 2:
        nearest_sup.append(float(low.iloc[-40:].min() if len(low) >= 40 else low.min()))
    if len(nearest_res) < 1:
        nearest_res = [float(high.iloc[-20:].max())]
    if len(nearest_res) < 2:
        nearest_res.append(float(high.iloc[-40:].max() if len(high) >= 40 else high.max()))

    return TechnicalIndicators(
        ticker=ticker,
        current_price=current_price,
        macd_signal=macd_signal,
        macd_histogram=round(hist_val, 4),
        rsi=round(rsi, 2),
        volume_ratio=round(volume_ratio, 3),
        support_1=round(nearest_sup[0], 2),
        support_2=round(nearest_sup[1], 2),
        resistance_1=round(nearest_res[0], 2),
        resistance_2=round(nearest_res[1], 2),
        atr_14=atr_14,
        atr_14_pct=atr_14_pct,
    )


def _extract_ticker_df(batch_df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Extract a single ticker's OHLCV DataFrame from a multi-ticker batch download."""
    if isinstance(batch_df.columns, pd.MultiIndex):
        # yfinance batch with group_by='ticker': level 0 = ticker, level 1 = price type
        tickers_in_data = batch_df.columns.get_level_values(0).unique().tolist()
        if ticker not in tickers_in_data:
            return pd.DataFrame()
        ticker_df = batch_df.loc[:, batch_df.columns.get_level_values(0) == ticker].copy()
        ticker_df.columns = ticker_df.columns.get_level_values(1)  # price types become column names
        return ticker_df
    # Single ticker download (shouldn't happen in batch path, but handle it)
    return batch_df.copy()


async def fetch_indicators_batch(tickers: list[str]) -> dict[str, TechnicalIndicators | Exception]:
    """Fetch indicators using chunked sequential batch downloads with per-ticker retry.

    Splits tickers into chunks of ANALYSIS_DATA_CHUNK_SIZE (default 20), downloads each
    chunk sequentially via yf.download with ANALYSIS_DATA_CHUNK_DELAY_S (default 0.5s)
    between chunks. Any ticker whose DataFrame is empty after the batch pass gets one
    individual yf.download retry before being recorded as a DataFetchError.

    Env vars are read at call-site so tests can override without module reload.
    """
    if not tickers:
        return {}

    chunk_size = int(os.environ.get("ANALYSIS_DATA_CHUNK_SIZE", "20"))
    chunk_delay = float(os.environ.get("ANALYSIS_DATA_CHUNK_DELAY_S", "0.5"))
    chunks = [tickers[i:i + chunk_size] for i in range(0, len(tickers), chunk_size)]

    logger.debug(
        "fetch_indicators_batch: %d tickers in %d chunks of %d",
        len(tickers), len(chunks), chunk_size,
    )

    # Step 1: Chunked sequential batch downloads
    ticker_dfs: dict[str, pd.DataFrame] = {}
    for idx, chunk in enumerate(chunks):
        if idx > 0:
            await asyncio.sleep(chunk_delay)
        batch_df: pd.DataFrame = await asyncio.to_thread(
            yf.download,
            chunk,
            period="3mo",
            interval="1d",
            progress=False,
            auto_adjust=True,
            group_by="ticker",
        )
        for ticker in chunk:
            ticker_dfs[ticker] = _extract_ticker_df(batch_df, ticker)

    # Step 2: Per-ticker retry for any empty DataFrame from the batch pass
    empty_tickers = [t for t, df in ticker_dfs.items() if df.empty]
    if empty_tickers:
        logger.debug("Retrying %d tickers that returned empty DataFrames", len(empty_tickers))
    for ticker in empty_tickers:
        try:
            retry_df: pd.DataFrame = await asyncio.to_thread(
                yf.download,
                ticker,
                period="3mo",
                interval="1d",
                progress=False,
                auto_adjust=True,
                group_by="ticker",
            )
            ticker_dfs[ticker] = _extract_ticker_df(retry_df, ticker)
        except Exception as exc:
            logger.warning("Individual retry download failed for %s: %s", ticker, exc)
            ticker_dfs[ticker] = pd.DataFrame()

    # Step 3: Compute indicators with per-ticker wall-clock timing
    results: dict[str, TechnicalIndicators | Exception] = {}
    for ticker in tickers:
        t_start = _time.monotonic()
        try:
            results[ticker] = _compute_indicators(ticker, ticker_dfs.get(ticker, pd.DataFrame()))
        except DataFetchError as exc:
            exc.duration_ms = int((_time.monotonic() - t_start) * 1000)
            results[ticker] = exc
        except Exception as exc:
            logger.warning("Indicator computation failed for %s: %s", ticker, exc)
            err = DataFetchError(ticker)
            err.duration_ms = int((_time.monotonic() - t_start) * 1000)
            results[ticker] = err

    return results


async def fetch_indicators(ticker: str) -> TechnicalIndicators:
    """Fetch indicators for a single ticker.

    NOTE: Do NOT call this concurrently for multiple tickers — use fetch_indicators_batch
    instead to avoid yfinance thread-safety issues with parallel downloads.
    """
    logger.debug("Fetching indicators for %s", ticker)
    df = await asyncio.to_thread(
        yf.download, ticker, period="3mo", interval="1d", progress=False, auto_adjust=True
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return _compute_indicators(ticker, df)
