"""FastAPI routes for the technical analysis feature."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import (
    add_analysis_ticker,
    get_analysis_by_ticker,
    get_analysis_tickers,
    get_latest_analysis,
    get_performance_summary,
    remove_analysis_ticker,
)
from app.analysis.models import InvestingComAuthError, PerformanceResponse
from app.analysis.orchestrator import run_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class RunRequest(BaseModel):
    tickers: list[str] | None = None


class AddTickerRequest(BaseModel):
    ticker: str


@router.post("/run")
async def trigger_analysis(body: RunRequest):
    """Trigger a full analysis run. Uses configured tickers if none provided."""
    tickers = body.tickers
    if not tickers:
        tickers = await get_analysis_tickers()
    if not tickers:
        raise HTTPException(status_code=422, detail="No tickers configured for analysis")

    tickers = [t.upper() for t in tickers]

    try:
        result = await run_analysis(tickers)
    except InvestingComAuthError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to investing.com: {exc}. Check INVESTING_COM_EMAIL and INVESTING_COM_PASSWORD in .env",
        )

    return {
        "run_id": result.run_id,
        "analyzed_at": result.analyzed_at,
        "duration_seconds": result.duration_seconds,
        "top_5": [a.model_dump() for a in result.top_5],
        "assets": [a.model_dump() for a in result.assets],
        "errors": result.errors,
    }


@router.get("/latest")
async def get_latest():
    """Return the most recent cached analysis results."""
    rows = await get_latest_analysis()
    return {"results": rows}


@router.get("/tickers")
async def list_tickers():
    """Return the current list of tickers configured for analysis."""
    tickers = await get_analysis_tickers()
    return {"tickers": tickers}


@router.post("/tickers")
async def add_ticker(body: AddTickerRequest):
    """Add a ticker to the analysis list."""
    ticker = body.ticker.upper()
    if not ticker.isalpha() or len(ticker) > 10:
        raise HTTPException(status_code=422, detail=f"Invalid ticker: {ticker}")
    added = await add_analysis_ticker(ticker)
    return {"ticker": ticker, "added": added}


@router.delete("/tickers/{ticker}")
async def remove_ticker(ticker: str):
    """Remove a ticker from the analysis list."""
    ticker = ticker.upper()
    removed = await remove_analysis_ticker(ticker)
    if not removed:
        raise HTTPException(status_code=404, detail=f"{ticker} not in analysis list")
    return {"ticker": ticker, "removed": True}


@router.get("/performance", response_model=PerformanceResponse)
async def get_performance():
    """Return aggregated outcome performance metrics."""
    return await get_performance_summary()


@router.get("/{ticker}")
async def get_ticker_analysis(ticker: str):
    """Return the latest analysis result for a specific ticker."""
    ticker = ticker.upper()
    result = await get_analysis_by_ticker(ticker)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"No analysis found for {ticker}. Run /api/analysis/run first."
        )
    return result
