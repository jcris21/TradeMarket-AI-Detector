"""OrchestratorAgent — coordinates the 4-stage analysis pipeline."""

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

from app.db import get_connection, save_analysis_results
from app.db.repository import get_analysis_by_ticker

from .data_agent import fetch_indicators_batch
from .models import AnalysisResult, AssetAnalysis, TechnicalIndicators
from .scoring_agent import _get_hit_rate, _get_prior_scores, score_and_rank_with_errors
from .vision_agent import analyze_asset

logger = logging.getLogger(__name__)

# VIX gate threshold. Set >= 999 to disable the gate entirely.
ANALYSIS_VIX_THRESHOLD = float(os.environ.get("ANALYSIS_VIX_THRESHOLD", "25.0"))


async def _fetch_vix() -> float | None:
    """Fetch the latest ^VIX close. Returns None on any error/empty result (fail-open)."""
    try:
        df = await asyncio.to_thread(
            yf.download,
            "^VIX",
            period="5d",
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
        if df is None or df.empty:
            logger.warning("vix_fetch_empty", extra={"event": "vix_fetch_empty"})
            return None
        close = df["Close"]
        if hasattr(close, "columns"):  # MultiIndex columns when single ticker via yfinance
            close = close.iloc[:, 0]
        return float(close.iloc[-1])
    except Exception as exc:
        logger.warning("vix_fetch_failed", extra={"event": "vix_fetch_failed", "error": str(exc)})
        return None


def _apply_vix_gate(asset: AssetAnalysis) -> AssetAnalysis:
    """Convert a BUY asset to AVOID under an active VIX gate. Non-BUY assets unchanged."""
    if asset.signal != "BUY":
        return asset
    return asset.model_copy(update={
        "signal": "AVOID",
        "rank": None,
        "rank_exclusion_reason": "regime_vix",
    })


async def run_analysis(tickers: list[str]) -> AnalysisResult:
    """Run the full 4-stage analysis pipeline and return an AnalysisResult.

    Saves all results to the DB before returning.
    """
    run_id = str(uuid.uuid4())
    start = time.monotonic()
    errors: list[dict] = []

    # Stage 1: Batch indicator fetch (single yfinance call avoids thread-safety race).
    # VIX is fetched concurrently so it adds zero latency to the critical path.
    t1 = time.monotonic()
    batch_results, vix_value = await asyncio.gather(
        fetch_indicators_batch(tickers),
        _fetch_vix(),
    )

    vix_gate_active = vix_value is not None and vix_value > ANALYSIS_VIX_THRESHOLD
    logger.info("vix_gate_checked", extra={
        "event": "vix_gate_checked",
        "vix_value": vix_value,
        "threshold": ANALYSIS_VIX_THRESHOLD,
        "gate_active": vix_gate_active,
    })

    successful: dict[str, TechnicalIndicators] = {}
    rate_limited_count = 0
    for ticker, result in batch_results.items():
        if isinstance(result, Exception):
            reason = getattr(result, "reason", "unknown")
            if reason == "rate_limited":
                rate_limited_count += 1
            errors.append({
                "ticker": ticker,
                "error_message": str(result),
                "duration_ms": getattr(result, "duration_ms", 0),
                "reason": reason,
            })
        else:
            successful[ticker] = result

    logger.info("stage_complete", extra={
        "stage": 1, "run_id": run_id,
        "duration_ms": int((time.monotonic() - t1) * 1000),
        "tickers_total": len(tickers),
        "tickers_ok": len(successful),
        "tickers_error": len(tickers) - len(successful),
        "rate_limited_count": rate_limited_count,
    })

    # SMA-200 regime gate: tickers trading at/below their 200-day SMA are structurally
    # bearish and suppressed before Stages 2–4 (zero LLM spend). sma_200 is None → fail open.
    regime_passed: dict[str, TechnicalIndicators] = {}
    regime_excluded_analyses: list[AssetAnalysis] = []
    for ticker, indic in successful.items():
        if indic.sma_200 is not None and indic.current_price <= indic.sma_200:
            logger.debug(
                "regime_gate_excluded",
                extra={
                    "ticker": ticker,
                    "current_price": indic.current_price,
                    "sma_200": indic.sma_200,
                },
            )
            regime_excluded_analyses.append(AssetAnalysis(
                ticker=ticker,
                signal="AVOID",
                confidence=0.0,
                entry_price=indic.current_price,
                target_price=indic.current_price,
                stop_loss=indic.current_price,
                risk_reward_ratio=0.0,
                support_validated=False,
                indicators_summary={"sma_200": indic.sma_200, "current_price": indic.current_price},
                argument="Suppressed by SMA-200 regime gate: price at or below 200-day moving average.",
                rank=None,
                rank_exclusion_reason="regime_bearish",
            ))
        else:
            regime_passed[ticker] = indic
    successful = regime_passed

    # Staleness fallback: for rate-limited tickers with a <24h cached result,
    # recover the prior AssetAnalysis and include it in the final result.
    stale_tickers: list[str] = []
    stale_analyses: list[AssetAnalysis] = []
    rate_limited_ticker_list = [e["ticker"] for e in errors if e.get("reason") == "rate_limited"]
    if rate_limited_ticker_list:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        for ticker in rate_limited_ticker_list:
            cached = await get_analysis_by_ticker(ticker)
            if cached is None:
                continue
            analyzed_at_str = cached.get("analyzed_at")
            if not analyzed_at_str:
                continue
            try:
                analyzed_at_dt = datetime.fromisoformat(analyzed_at_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            if analyzed_at_dt < cutoff:
                continue
            try:
                stale_asset = AssetAnalysis(
                    ticker=cached["ticker"],
                    signal=cached.get("signal", "WAIT"),
                    confidence=cached.get("confidence", 0.0),
                    entry_price=cached.get("entry_price", 0.0),
                    target_price=cached.get("target_price", 0.0),
                    stop_loss=cached.get("stop_loss", 0.0),
                    risk_reward_ratio=cached.get("risk_reward_ratio", 0.0),
                    support_validated=bool(cached.get("support_validated", False)),
                    indicators_summary=cached.get("indicators_summary", {}),
                    argument=cached.get("argument", ""),
                    score=cached.get("score"),
                    score_delta=cached.get("score_delta"),
                    rank=cached.get("rank"),
                    expected_gain_per10=cached.get("expected_gain_per10"),
                    expected_loss_per10=cached.get("expected_loss_per10"),
                    expected_value_per10=cached.get("expected_value_per10"),
                    hit_rate_used=cached.get("hit_rate_used"),
                    hit_rate_source=cached.get("hit_rate_source"),
                    atr_14_pct=cached.get("atr_14_pct"),
                    stop_viable=cached.get("stop_viable"),
                    is_stale=True,
                )
            except Exception as exc:
                logger.warning(
                    "staleness_fallback_reconstruct_failed",
                    extra={"ticker": ticker, "error": str(exc)},
                )
                continue
            stale_tickers.append(ticker)
            stale_analyses.append(stale_asset)
            errors = [e for e in errors if e["ticker"] != ticker]
            logger.info(
                "staleness_fallback_recovered",
                extra={"ticker": ticker, "analyzed_at": analyzed_at_str},
            )

    if not successful:
        duration = round(time.monotonic() - start, 2)
        logger.info("run_complete", extra={
            "run_id": run_id,
            "total_ms": int(duration * 1000),
            "signals_generated": 0,
            "error_count": len(errors),
        })
        early_stale = [_apply_vix_gate(a) for a in stale_analyses] if vix_gate_active else stale_analyses
        return AnalysisResult(
            run_id=run_id,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            assets=early_stale + regime_excluded_analyses,
            top_5=[],
            errors=errors,
            duration_seconds=duration,
            stale_tickers=stale_tickers,
            regime_gate_active=vix_gate_active,
            vix_value=vix_value,
        )

    # Stage 2: Load pre-captured screenshots from the screenshots folder
    t2 = time.monotonic()
    screenshots_dir = Path(__file__).parents[3] / "screenshots"
    screenshots: dict[str, bytes | None] = {}
    for ticker in successful:
        png = screenshots_dir / f"{ticker}.png"
        screenshots[ticker] = png.read_bytes() if png.exists() else None
    loaded = sum(1 for v in screenshots.values() if v is not None)
    logger.info("stage_complete", extra={
        "stage": 2, "run_id": run_id,
        "duration_ms": int((time.monotonic() - t2) * 1000),
        "tickers_total": len(successful),
        "tickers_ok": loaded,
        "tickers_error": len(successful) - loaded,
    })

    # Stage 3: Parallel vision analysis
    t3 = time.monotonic()

    async def _vision_one(ticker: str) -> AssetAnalysis:
        indicators = successful[ticker]
        screenshot = screenshots.get(ticker)
        return await analyze_asset(indicators, screenshot)

    ticker_list = list(successful.keys())
    vision_tasks = [_vision_one(t) for t in ticker_list]
    vision_results = await asyncio.gather(*vision_tasks, return_exceptions=True)
    raw_analyses: list[AssetAnalysis] = []
    vision_errors = 0
    for ticker, res in zip(ticker_list, vision_results):
        if isinstance(res, Exception):
            errors.append({"ticker": ticker, "error_message": str(res)})
            vision_errors += 1
        else:
            raw_analyses.append(res)
    ticker_list = [t for t, r in zip(ticker_list, vision_results) if not isinstance(r, Exception)]
    logger.info("stage_complete", extra={
        "stage": 3, "run_id": run_id,
        "duration_ms": int((time.monotonic() - t3) * 1000),
        "tickers_total": len(successful),
        "tickers_ok": len(raw_analyses),
        "tickers_error": vision_errors,
    })

    # Inject ATR + SMA-50 + Bollinger Band values from Stage-1 indicators
    analyses: list[AssetAnalysis] = [
        asset.model_copy(update={
            "atr_14": successful[ticker].atr_14,
            "atr_14_pct": successful[ticker].atr_14_pct,
            "indicators_summary": {
                **asset.indicators_summary,
                "sma_50": successful[ticker].sma_50,
                "bb_upper": successful[ticker].bb_upper,
                "bb_lower": successful[ticker].bb_lower,
                "bb_bandwidth": successful[ticker].bb_bandwidth,
                "bb_pct_b": successful[ticker].bb_pct_b,
            },
        })
        for ticker, asset in zip(ticker_list, raw_analyses)
    ]

    # Stage 4: Score and rank (with bet-size pre-computation)
    t4 = time.monotonic()
    db = await get_connection()
    try:
        hit_rate, hit_rate_source = await _get_hit_rate(db)
        prior_scores = await _get_prior_scores(db)
    finally:
        await db.close()
    ranked, structural_errors = score_and_rank_with_errors(
        analyses,
        hit_rate=hit_rate,
        hit_rate_source=hit_rate_source,
        prior_scores=prior_scores,
    )
    errors.extend(structural_errors)

    # VIX system-wide gate: when active, convert all BUY signals (new + stale) to AVOID.
    if vix_gate_active:
        ranked = [_apply_vix_gate(a) for a in ranked]
        stale_analyses = [_apply_vix_gate(a) for a in stale_analyses]
        top_5 = []
    else:
        top_5 = [a for a in ranked if a.rank is not None]

    # Persist results
    db_rows = [a.to_db_row(run_id) for a in ranked]
    write_errors = await save_analysis_results(db_rows)
    errors.extend(write_errors)

    logger.info("stage_complete", extra={
        "stage": 4, "run_id": run_id,
        "duration_ms": int((time.monotonic() - t4) * 1000),
        "tickers_total": len(analyses),
        "tickers_ok": len(ranked),
        "tickers_error": len(structural_errors),
    })

    duration = round(time.monotonic() - start, 2)
    logger.info("run_complete", extra={
        "run_id": run_id,
        "total_ms": int(duration * 1000),
        "signals_generated": len(top_5),
        "error_count": len(errors),
    })

    return AnalysisResult(
        run_id=run_id,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        assets=ranked + stale_analyses + regime_excluded_analyses,
        top_5=top_5,
        errors=errors,
        duration_seconds=duration,
        stale_tickers=stale_tickers,
        regime_gate_active=vix_gate_active,
        vix_value=vix_value,
    )
