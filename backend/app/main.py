"""FastAPI application for FinAlly."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.analysis.outcome_detector import OutcomeDetector
from app.db import get_cash_balance, get_positions, get_watchlist, init_db, insert_snapshot
from app.db.repository import expire_stale_levels, reset_stale_enrichments
from app.logging_config import configure_logging
from app.market import PriceCache, create_market_data_source, create_stream_router
from app.routes import analysis, chat, market, portfolio, watchlist

logger = logging.getLogger(__name__)

# Module-level PriceCache — shared between SSE router and the rest of the app
price_cache = PriceCache()


async def _snapshot_loop(cache: PriceCache):
    """Background task: record portfolio snapshot every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        try:
            cash = await get_cash_balance()
            positions = await get_positions()
            total_value = cash
            for pos in positions:
                price = cache.get_price(pos["ticker"]) or pos["avg_cost"]
                total_value += price * pos["quantity"]
            await insert_snapshot(round(total_value, 2))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error recording portfolio snapshot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    configure_logging()
    await init_db()
    await expire_stale_levels()
    await reset_stale_enrichments()

    source = create_market_data_source(price_cache)

    app.state.price_cache = price_cache
    app.state.market_source = source

    # Start market data with watchlist tickers
    wl = await get_watchlist()
    tickers = [entry["ticker"] for entry in wl]
    await source.start(tickers)
    logger.info("Market data source started with %d tickers", len(tickers))

    # Start snapshot background task
    snapshot_task = asyncio.create_task(_snapshot_loop(price_cache))

    # Record initial snapshot
    cash = await get_cash_balance()
    await insert_snapshot(round(cash, 2))

    # Start nightly outcome detector scheduler
    cron_hour = int(os.environ.get("OUTCOME_DETECTOR_CRON_HOUR", "2"))
    scheduler = AsyncIOScheduler()

    async def _run_outcome_detector():
        try:
            await OutcomeDetector().run()
        except Exception:
            logger.exception("OutcomeDetector scheduled run failed")

    scheduler.add_job(_run_outcome_detector, "cron", hour=cron_hour)
    scheduler.start()
    logger.info("OutcomeDetector scheduler started (hour=%d UTC)", cron_hour)

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    snapshot_task.cancel()
    try:
        await snapshot_task
    except asyncio.CancelledError:
        pass

    await source.stop()
    logger.info("Market data source stopped")


app = FastAPI(title="FinAlly", lifespan=lifespan)

# API routes
app.include_router(portfolio.router)
app.include_router(watchlist.router)
app.include_router(chat.router)
app.include_router(analysis.router)
app.include_router(market.router)

# SSE streaming — uses the module-level price_cache
stream_router = create_stream_router(price_cache)
app.include_router(stream_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/debug/cache")
async def debug_cache(request: Request):
    import os
    cache = getattr(request.app.state, "price_cache", None)
    source = getattr(request.app.state, "market_source", None)
    prices = cache.get_all() if cache else {}
    return {
        "cache_set": cache is not None,
        "source_type": type(source).__name__ if source else None,
        "massive_api_key": repr(os.environ.get("MASSIVE_API_KEY", "NOT_SET")),
        "price_count": len(prices),
        "sample": {k: round(v.price, 2) for k, v in list(prices.items())[:3]},
    }


# Static files serving (frontend) — mount last so API routes take priority
_static_dir = Path(__file__).parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")
