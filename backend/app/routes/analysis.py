"""FastAPI routes for the technical analysis feature."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from pydantic import BaseModel

from app.db import (
    add_analysis_ticker,
    get_analysis_by_ticker,
    get_analysis_tickers,
    get_latest_analysis,
    get_performance_summary,
    remove_analysis_ticker,
    update_enrichment_delta,
)
from app.analysis.models import PerformanceResponse
from app.analysis.orchestrator import run_analysis
from app.analysis.run_registry import (
    RunState,
    evict_expired_runs,
    get_active_run,
    get_run,
    register_run,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

_PARTIAL_TOP_N = 20


async def _run_analysis_task(tickers: list[str], state: RunState) -> None:
    """Background task wrapper — runs the pipeline and marks failure on error."""
    try:
        await run_analysis(tickers, state=state)
    except Exception as exc:  # noqa: BLE001 — terminal failure must always be recorded
        logger.exception("analysis_run_failed", extra={"run_id": state.run_id})
        state.errors_so_far = [
            *state.errors_so_far,
            {"ticker": "*", "error_message": str(exc), "reason": "unhandled"},
        ]
        state.stage = "failed"
        if state.completed_at is None:
            state.completed_at = datetime.now(timezone.utc).isoformat()


class RunRequest(BaseModel):
    tickers: list[str] | None = None


class AddTickerRequest(BaseModel):
    ticker: str


class EnrichRequest(BaseModel):
    run_id: str
    delta: float


@router.post("/run", status_code=202)
async def trigger_analysis(body: RunRequest, background_tasks: BackgroundTasks, response: Response):
    """Dispatch a full analysis run as a background task (202 Accepted).

    Returns ``{run_id, tickers_total, started_at}`` immediately. Clients poll
    ``GET /api/analysis/run/{run_id}/status`` for completion, then fetch results
    from ``GET /api/analysis/latest``. Returns 409 if a run is already active.
    """
    evict_expired_runs()

    existing = get_active_run()
    if existing is not None:
        response.status_code = 409
        return {"error": "run_already_in_progress", "run_id": existing.run_id}

    tickers = body.tickers
    if not tickers:
        tickers = await get_analysis_tickers()
    if not tickers:
        raise HTTPException(status_code=422, detail="No tickers configured for analysis")

    tickers = [t.upper() for t in tickers]

    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()
    state = RunState(
        run_id=run_id,
        stage="data",
        tickers_total=len(tickers),
        started_at=started_at,
    )
    register_run(state)

    background_tasks.add_task(_run_analysis_task, tickers, state)

    return {
        "run_id": run_id,
        "tickers_total": len(tickers),
        "started_at": started_at,
    }


@router.get("/run/{run_id}/status")
async def get_run_status(run_id: str):
    """Return live progress for a run. 404 if unknown. In-memory read (< 10 ms)."""
    evict_expired_runs()
    state = get_run(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"No run found with id {run_id}")
    return state.to_status_dict()


@router.get("/latest")
async def get_latest(partial: bool = Query(False)):
    """Return cached analysis results, or in-progress top-20 when partial=true."""
    if partial:
        active = get_active_run()
        if active is None or not active.scored:
            return {"results": [], "partial": True}
        ranked = sorted(
            active.scored,
            key=lambda a: a.get("score_quant") or 0,
            reverse=True,
        )
        return {"results": ranked[:_PARTIAL_TOP_N], "partial": True}

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


@router.post("/{ticker}/enrich")
async def enrich_ticker(ticker: str, body: EnrichRequest):
    """Apply a post-hoc enrichment_delta to a ticker's score within a specific run.

    delta must be in [-15, +15]. Returns 404 if no matching row found.
    """
    ticker = ticker.upper()
    if not (-15.0 <= body.delta <= 15.0):
        raise HTTPException(status_code=422, detail="delta must be between -15 and +15")
    updated = await update_enrichment_delta(ticker, body.run_id, body.delta)
    if not updated:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis row found for {ticker} in run {body.run_id}",
        )
    result = await get_analysis_by_ticker(ticker)
    return {"ticker": ticker, "run_id": body.run_id, "enrichment_delta": body.delta, "score_enriched": result.get("score_enriched") if result else None}


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

