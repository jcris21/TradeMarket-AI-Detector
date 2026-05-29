"""OrchestratorAgent — coordinates the 4-stage analysis pipeline."""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.db import get_connection, save_analysis_results

from .data_agent import fetch_indicators_batch
from .models import AnalysisResult, AssetAnalysis, TechnicalIndicators
from .scoring_agent import _get_hit_rate, _get_prior_scores, score_and_rank
from .vision_agent import analyze_asset

logger = logging.getLogger(__name__)


async def run_analysis(tickers: list[str]) -> AnalysisResult:
    """Run the full 4-stage analysis pipeline and return an AnalysisResult.

    Saves all results to the DB before returning.
    """
    run_id = str(uuid.uuid4())
    start = time.monotonic()
    errors: list[dict] = []

    # Stage 1: Batch indicator fetch (single yfinance call avoids thread-safety race)
    logger.info("Stage 1: batch-fetching indicators for %d tickers", len(tickers))
    batch_results = await fetch_indicators_batch(tickers)

    successful: dict[str, TechnicalIndicators] = {}
    for ticker, result in batch_results.items():
        if isinstance(result, Exception):
            errors.append({"ticker": ticker, "error_message": str(result)})
        else:
            successful[ticker] = result

    if not successful:
        return AnalysisResult(
            run_id=run_id,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            assets=[],
            top_5=[],
            errors=errors,
            duration_seconds=round(time.monotonic() - start, 2),
        )

    # Stage 2: Load pre-captured screenshots from the screenshots folder
    logger.info("Stage 2: loading pre-captured screenshots for %d tickers", len(successful))
    screenshots_dir = Path(__file__).parents[3] / "screenshots"
    screenshots: dict[str, bytes | None] = {}
    for ticker in successful:
        png = screenshots_dir / f"{ticker}.png"
        screenshots[ticker] = png.read_bytes() if png.exists() else None
    loaded = sum(1 for v in screenshots.values() if v is not None)
    logger.info("Loaded %d/%d screenshots from %s", loaded, len(successful), screenshots_dir)

    # Stage 3: Parallel vision analysis
    logger.info("Stage 3: running vision analysis for %d tickers", len(successful))

    async def _vision_one(ticker: str) -> AssetAnalysis:
        indicators = successful[ticker]
        screenshot = screenshots.get(ticker)
        return await analyze_asset(indicators, screenshot)

    vision_tasks = [_vision_one(t) for t in successful]
    analyses: list[AssetAnalysis] = await asyncio.gather(*vision_tasks)

    # Stage 4: Score and rank (with bet-size pre-computation)
    logger.info("Stage 4: scoring and ranking %d analyses", len(analyses))
    db = await get_connection()
    try:
        hit_rate, hit_rate_source = await _get_hit_rate(db)
        prior_scores = await _get_prior_scores(db)
    finally:
        await db.close()
    ranked = score_and_rank(
        analyses,
        hit_rate=hit_rate,
        hit_rate_source=hit_rate_source,
        prior_scores=prior_scores,
    )
    top_5 = [a for a in ranked if a.rank is not None]

    # Persist results
    db_rows = [a.to_db_row(run_id) for a in ranked]
    write_errors = await save_analysis_results(db_rows)
    errors.extend(write_errors)

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
