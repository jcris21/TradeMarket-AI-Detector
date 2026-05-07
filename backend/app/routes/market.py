"""Market data API endpoints (historical prices for chart)."""

import asyncio
import logging

import yfinance as yf
import pandas as pd
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/history/{ticker}")
async def get_ticker_history(ticker: str, period: str = "3mo"):
    """Return daily close prices for a ticker as [{time, value}] pairs.

    Used by the frontend PriceChart to show historical context.
    `time` is a Unix timestamp (seconds) aligned to day boundaries.
    """
    ticker = ticker.upper()
    valid_periods = {"1mo", "3mo", "6mo", "1y"}
    if period not in valid_periods:
        period = "3mo"

    try:
        df: pd.DataFrame = await asyncio.to_thread(
            yf.download,
            ticker,
            period=period,
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
    except Exception as exc:
        logger.warning("yfinance error for %s: %s", ticker, exc)
        raise HTTPException(status_code=502, detail=f"Could not fetch history for {ticker}")

    if df.empty:
        raise HTTPException(status_code=404, detail=f"No historical data for {ticker}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df["Close"].dropna()
    data = [
        {"time": int(idx.timestamp()), "value": round(float(price), 2)}
        for idx, price in close.items()
    ]

    return {"ticker": ticker, "period": period, "data": data}
