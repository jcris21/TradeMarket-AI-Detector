"""OrchestratorAgent — coordinates the 4-stage analysis pipeline."""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

from app.db import save_analysis_results

from .data_agent import fetch_indicators
from .models import AnalysisResult, AssetAnalysis, DataFetchError, TechnicalIndicators
from .scoring_agent import score_and_rank
from .screenshot_agent import capture_charts
from .vision_agent import analyze_asset

logger = logging.getLogger(__name__)


async def _fetch_one(ticker: str) -> tuple[str, TechnicalIndicators | None, str | None]:
    """Fetch indicators for one ticker. Returns (ticker, result_or_None, error_or_None)."""
    try:
        indicators = await fetch_indicators(ticker)
        return ticker, indicators, None
    except DataFetchError as exc:
        return ticker, None, str(exc)
    except Exception as exc:
        logger.warning("Unexpected error fetching %s: %s", ticker, exc)
        return ticker, None, str(exc)


async def run_analysis(tickers: list[str]) -> AnalysisResult:
    """Run the full 4-stage analysis pipeline and return an AnalysisResult.

    Saves all results to the DB before returning.
    """
    run_id = str(uuid.uuid4())
    start = time.monotonic()
    errors: list[dict] = []

    # Stage 1: Parallel indicator fetch
    logger.info("Stage 1: fetching indicators for %d tickers", len(tickers))
    fetch_tasks = [_fetch_one(t) for t in tickers]
    fetch_results = await asyncio.gather(*fetch_tasks)

    successful: dict[str, TechnicalIndicators] = {}
    for ticker, indicators, error in fetch_results:
        if indicators is not None:
            successful[ticker] = indicators
        else:
            errors.append({"ticker": ticker, "error_message": error or "Unknown error"})

    if not successful:
        return AnalysisResult(
            run_id=run_id,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            assets=[],
            top_5=[],
            errors=errors,
            duration_seconds=round(time.monotonic() - start, 2),
        )

    # Stage 2: Sequential screenshots (single Playwright session)
    logger.info("Stage 2: capturing screenshots for %d tickers", len(successful))
    screenshots: dict[str, bytes | None] = {}
    try:
        screenshots = await capture_charts(list(successful.keys()))
    except Exception as exc:
        logger.error("Screenshot capture failed: %s", exc)
        screenshots = {t: None for t in successful}

    # Stage 3: Parallel vision analysis
    logger.info("Stage 3: running vision analysis for %d tickers", len(successful))

    async def _vision_one(ticker: str) -> AssetAnalysis:
        indicators = successful[ticker]
        screenshot = screenshots.get(ticker)
        return await analyze_asset(indicators, screenshot)

    vision_tasks = [_vision_one(t) for t in successful]
    analyses: list[AssetAnalysis] = await asyncio.gather(*vision_tasks)

    # Stage 4: Score and rank
    logger.info("Stage 4: scoring and ranking %d analyses", len(analyses))
    ranked = score_and_rank(analyses)
    top_5 = [a for a in ranked if a.rank is not None]

    # Persist results
    db_rows = [a.to_db_row(run_id) for a in ranked]
    await save_analysis_results(db_rows)

    duration = round(time.monotonic() - start, 2)
    logger.info("Analysis complete in %.1fs — %d top opportunities", duration, len(top_5))

    return AnalysisResult(
        run_id=run_id,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        assets=ranked,
        top_5=top_5,
        errors=errors,
        duration_seconds=duration,
    )
