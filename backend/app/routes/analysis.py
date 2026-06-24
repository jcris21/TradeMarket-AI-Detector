"""FastAPI routes for the technical analysis feature."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from pydantic import BaseModel

from app.analysis.models import (
    AutoScreenshotEnrichRequest,
    ConfirmedLevel,
    EnrichmentJobResponse,
    EnrichRequest,
    LevelConfirmationRequest,
    PerformanceResponse,
    ScreenshotEnrichRequest,
    TraderChartEnrichResponse,
    filter_by_proximity,
)
from app.analysis.orchestrator import run_analysis
from app.analysis.run_registry import (
    RunState,
    evict_expired_runs,
    get_active_run,
    get_run,
    register_run,
)
from app.db import (
    add_analysis_ticker,
    create_enrichment_job,
    find_pending_enrichment_job,
    get_analysis_by_ticker,
    get_analysis_tickers,
    get_enrichment_job,
    get_latest_analysis,
    get_performance_summary,
    remove_analysis_ticker,
    set_analysis_enrichment_status,
    set_ticker_preferred_url,
    store_custom_levels,
    update_analysis_result_custom_levels,
    update_enrichment_delta,
    update_enrichment_job,
)
from app.utils import validate_chart_image, validate_source_url

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


class ManualDeltaRequest(BaseModel):
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


@router.get("/debug/extract-levels-last")
async def debug_extract_levels_last():
    """Temporary debug endpoint — returns last extract_levels raw model response."""
    import pathlib
    path = pathlib.Path("extract_levels_debug.txt")
    if not path.exists():
        return {"debug": "No debug file yet — upload a chart first after restarting the backend."}
    return {"debug": path.read_text(encoding="utf-8")}


async def _run_screenshot_enrichment(
    enrichment_id: str, ticker: str, source_url: str
) -> None:
    """Background task: capture screenshot → VisionAgent → store B2 delta."""
    import os

    from app.analysis.screenshot_agent import ScreenshotAgent
    from app.analysis.vision_agent import analyze_asset
    from app.db import get_analysis_by_ticker as _get_by_ticker

    try:
        await update_enrichment_job(enrichment_id, "processing")
        await set_analysis_enrichment_status(ticker, "processing")
        logger.info("screenshot_enrichment_started", extra={"enrichment_id": enrichment_id, "ticker": ticker, "enrichment_path": "B2"})

        agent = ScreenshotAgent()
        png_bytes = await agent.capture(source_url)
        logger.info("screenshot_captured", extra={"enrichment_id": enrichment_id, "ticker": ticker, "enrichment_path": "B2"})

        latest = await _get_by_ticker(ticker)
        if latest is None:
            raise ValueError(f"No analysis row found for {ticker} — cannot enrich")

        existing_delta: float = latest.get("enrichment_delta") or 0.0

        from app.analysis.models import TechnicalIndicators
        indicators = TechnicalIndicators(
            ticker=ticker,
            current_price=latest.get("entry_price", 0.0),
            macd_signal="neutral",
            macd_histogram=0.0,
            rsi=50.0,
            volume_ratio=1.0,
            support_1=latest.get("stop_loss", 0.0),
            support_2=latest.get("stop_loss", 0.0),
            resistance_1=latest.get("target_price", 0.0),
            resistance_2=latest.get("target_price", 0.0),
        )

        analysis = await analyze_asset(indicators, screenshot_bytes=png_bytes)
        logger.info("vision_analysis_done", extra={"enrichment_id": enrichment_id, "ticker": ticker, "enrichment_path": "B2", "confidence": analysis.confidence})

        # B2 formula (read env at execution time so tests can override)
        enrichment_max_delta = float(os.environ.get("ENRICHMENT_MAX_DELTA", "15"))
        support_validated_bonus = float(os.environ.get("SUPPORT_VALIDATED_BONUS", "2.0"))
        enrichment_delta_b2 = round(
            min(
                analysis.confidence * enrichment_max_delta
                + (support_validated_bonus if analysis.support_validated else 0.0),
                enrichment_max_delta,
            ),
            2,
        )

        # B1 + B2 conflict resolution: take max of new B2 delta and existing delta
        final_delta = max(enrichment_delta_b2, existing_delta)

        # Argument display prefix
        argument_display = f"💬 Visual analysis: {analysis.argument}"

        completed_at = datetime.now(timezone.utc).isoformat()
        await update_enrichment_job(
            enrichment_id,
            "completed",
            enrichment_delta=final_delta,
            completed_at=completed_at,
        )
        await set_analysis_enrichment_status(
            ticker,
            "completed",
            enrichment_delta=final_delta,
            enrichment_type="auto_screenshot",
            argument=argument_display,
        )
        await set_ticker_preferred_url(ticker, source_url)
        logger.info("screenshot_enrichment_completed", extra={"enrichment_id": enrichment_id, "ticker": ticker, "enrichment_path": "B2", "final_delta": final_delta})

    except Exception as exc:
        logger.exception("screenshot_enrichment_failed", extra={"enrichment_id": enrichment_id, "ticker": ticker, "enrichment_path": "B2"})
        await update_enrichment_job(
            enrichment_id,
            "failed",
            error_message=str(exc),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        await set_analysis_enrichment_status(ticker, "failed")


@router.post("/{ticker}/enrich", status_code=200)
async def enrich_ticker(
    ticker: str,
    background_tasks: BackgroundTasks,
    body: EnrichRequest | ManualDeltaRequest,
):
    """Enrich a ticker.

    - No enrichment_type (ManualDeltaRequest): apply manual delta; returns 200.
    - enrichment_type="screenshot": async screenshot + VisionAgent; returns 202.
    - Unknown enrichment_type: returns 422.
    """
    ticker = ticker.upper()

    if isinstance(body, ManualDeltaRequest):
        if not (-15.0 <= body.delta <= 15.0):
            raise HTTPException(status_code=422, detail="delta must be between -15 and +15")
        updated = await update_enrichment_delta(ticker, body.run_id, body.delta)
        if not updated:
            raise HTTPException(
                status_code=404,
                detail=f"No analysis row found for {ticker} in run {body.run_id}",
            )
        result = await get_analysis_by_ticker(ticker)
        return {
            "ticker": ticker,
            "run_id": body.run_id,
            "enrichment_delta": body.delta,
            "score_enriched": result.get("score_enriched") if result else None,
        }

    if isinstance(body, (AutoScreenshotEnrichRequest, ScreenshotEnrichRequest)):
        existing = await get_analysis_by_ticker(ticker)
        if existing is None:
            raise HTTPException(
                status_code=404,
                detail=f"No analysis found for {ticker}. Run /api/analysis/run first.",
            )
        validate_source_url(body.source_url)

        # Idempotency: return existing in-flight job if one is already pending/processing
        in_flight = await find_pending_enrichment_job(ticker)
        if in_flight is not None:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=202,
                content=EnrichmentJobResponse(enrichment_id=in_flight["id"], status="pending").model_dump(),
            )

        enrichment_id = await create_enrichment_job(ticker, "auto_screenshot", body.source_url)
        await set_analysis_enrichment_status(ticker, "pending")
        background_tasks.add_task(_run_screenshot_enrichment, enrichment_id, ticker, body.source_url)
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=202,
            content=EnrichmentJobResponse(enrichment_id=enrichment_id, status="pending").model_dump(),
        )

    if body.enrichment_type == "trader_chart":
        existing = await get_analysis_by_ticker(ticker)
        if existing is None:
            raise HTTPException(
                status_code=404,
                detail=f"No analysis found for {ticker}. Run /api/analysis/run first.",
            )
        image_bytes = validate_chart_image(body.chart_image)

        from app.analysis.vision_agent import extract_levels
        levels = await extract_levels(image_bytes)

        current_price = existing.get("entry_price") or 0.0
        filtered = filter_by_proximity(levels, current_price)

        import json as _json
        levels_json = _json.dumps([lv.model_dump() for lv in filtered])
        enrichment_id = await create_enrichment_job(
            ticker,
            "trader_chart",
            status="pending_confirmation",
            extracted_levels=levels_json,
        )
        return TraderChartEnrichResponse(
            enrichment_id=enrichment_id,
            extracted_levels=filtered,
            status="pending_confirmation",
        )

    raise HTTPException(status_code=422, detail=f"Unknown enrichment_type: {body.enrichment_type}")


@router.post("/{ticker}/enrich/confirm")
async def confirm_enrichment(ticker: str, body: LevelConfirmationRequest):
    """Confirm trader-selected S/R levels, apply scoring, and persist with TTL.

    Returns updated score_quant, enrichment_delta, and score_enriched.
    """
    import json as _json
    import os

    ticker = ticker.upper()

    job = await get_enrichment_job(body.enrichment_id)
    if job is None or job["ticker"] != ticker:
        raise HTTPException(status_code=404, detail="Enrichment job not found for this ticker")

    # Idempotency: already confirmed → return existing result
    if job["status"] == "completed":
        latest = await get_analysis_by_ticker(ticker)
        sq = (latest or {}).get("score_quant") or 0.0
        ed = (latest or {}).get("enrichment_delta") or 0.0
        return {
            "custom_levels_applied": (latest or {}).get("custom_levels_applied") or 0,
            "enrichment_delta": ed,
            "score_quant": sq,
            "score_enriched": round(sq + ed, 2),
        }

    raw_levels = _json.loads(job.get("extracted_levels") or "[]")
    extracted_count = len(raw_levels)

    # Validate indices
    for idx in body.confirmed_indices:
        if idx < 0 or idx >= extracted_count:
            raise HTTPException(
                status_code=422, detail="confirmed_indices contains out-of-range values"
            )

    # Cap to first 2
    capped_indices = body.confirmed_indices[:2]
    confirmed_levels = [
        ConfirmedLevel(type=raw_levels[i]["type"], price=raw_levels[i]["price"])
        for i in capped_indices
    ]

    latest = await get_analysis_by_ticker(ticker)
    if latest is None:
        raise HTTPException(
            status_code=404, detail=f"No analysis found for {ticker}"
        )
    entry_price = latest.get("entry_price") or 0.0
    target_price = latest.get("target_price") or 0.0
    atr_14_pct = latest.get("atr_14_pct") or 0.0
    atr_14 = atr_14_pct * entry_price if (atr_14_pct and entry_price) else 0.0

    from app.analysis.scoring_agent import _apply_custom_levels
    enrichment_delta, applied_count = _apply_custom_levels(
        entry_price, target_price, atr_14, confirmed_levels
    )

    ttl_days = int(os.environ.get("CUSTOM_LEVEL_TTL_DAYS", "5"))
    from app.utils import trading_days_from_now
    expires_at = trading_days_from_now(ttl_days).isoformat()

    await store_custom_levels(ticker, confirmed_levels, expires_at)
    await update_analysis_result_custom_levels(ticker, applied_count, enrichment_delta)
    await update_enrichment_job(body.enrichment_id, "completed")

    score_quant = latest.get("score_quant") or 0.0
    return {
        "custom_levels_applied": applied_count,
        "enrichment_delta": enrichment_delta,
        "score_quant": score_quant,
        "score_enriched": round(score_quant + enrichment_delta, 2),
    }


@router.get("/{ticker}")
async def get_ticker_analysis(ticker: str):
    """Return the latest analysis result for a specific ticker."""
    ticker = ticker.upper()
    result = await get_analysis_by_ticker(ticker)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"No analysis found for {ticker}. Run /api/analysis/run first."
        )
    if "enrichment_status" not in result:
        result["enrichment_status"] = "none"
    return result

