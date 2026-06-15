## Context

The analysis pipeline fetches OHLCV data for up to 100 tickers via `yf.download()` inside `fetch_indicators_batch` (`data_agent.py`). The current error handling uses a bare `except Exception` that converts all failures — including transient HTTP 429 rate-limit responses — into `DataFetchError` with no retry, no reason discrimination, and no fallback. `YFRateLimitError` is a subclass of `Exception` already available in yfinance ≥ 0.2.x; it simply needs to be caught before the generic handler.

Cached analysis results are already persisted to `analysis_results` via `get_analysis_by_ticker()` in `repository.py`. The data needed for a staleness fallback exists; it is just never consulted on failure.

## Goals / Non-Goals

**Goals:**
- Explicitly detect `YFRateLimitError` before the generic handler
- Retry with exponential backoff (max 2 retries: 2s, 4s) at the download layer
- Surface `reason` discrimination (`"rate_limited"` vs `"empty_dataframe"`) in the `errors` list and structured logs
- Fall back to DB-cached indicators (< 24 h) when all retries fail, marking results `is_stale=True`
- Show a visible warning badge in the frontend for stale signals

**Non-Goals:**
- Persistent retry queues or circuit-breaker patterns
- Rate-limit awareness across concurrent requests (no token-bucket or global rate limiter)
- WebSocket or alternative data feeds as a fallback
- Persisting `is_stale` to the database (runtime flag only)
- Altering the behavior of `_compute_indicators` or Stage 2–4 orchestration logic

## Decisions

### 1. Retry logic lives in `_download_with_retry`, not in the orchestrator

Placing the retry loop inside a dedicated helper in `data_agent.py` keeps retry semantics co-located with the download call. The orchestrator stays responsible for routing errors; `data_agent` stays responsible for resilient fetching. Alternative — retrying at the orchestrator loop — would scatter download concerns across two files.

### 2. `asyncio.sleep` inside `asyncio.to_thread` worker

`fetch_indicators_batch` runs inside `asyncio.to_thread`. Using `asyncio.sleep` from within that thread requires calling it via `asyncio.get_event_loop().run_until_complete()` or using `time.sleep`. Since the retry waits (2s, 4s) are short and the thread is already blocking on network I/O, `time.sleep` is the correct choice here — it does not deadlock and keeps the code simple. This is the only place `time.sleep` is acceptable; all other async delays use `asyncio.sleep`.

### 3. Staleness threshold: 24 hours

A 24 h window matches the daily cadence of the analysis job. Results older than 24 h have too much drift to be useful as a live substitute; they are treated as no-cache. This threshold is hardcoded as a named constant (`STALE_THRESHOLD_HOURS = 24`) to make future adjustment straightforward.

### 4. `is_stale` is a runtime-only flag; no schema migration

`AssetAnalysis.is_stale` is added to the Pydantic model with `default=False` but is intentionally excluded from `to_db_row()`. DB rows always represent the freshest successfully computed result. The stale flag only exists to communicate across the orchestrator→API→frontend boundary within a single run. This avoids any migration cost.

### 5. Stale tickers are promoted into `successful`, not kept in `errors`

Once a valid cached result is found, the ticker is treated as a successful signal (with a warning) rather than an error. This ensures stale assets flow through stages 2–4 (scoring, ranking, etc.) with their cached indicators, and the consumer (API, frontend) does not need to merge two separate lists.

## Risks / Trade-offs

- **Blocking worker thread during retries** — `time.sleep(2)` and `time.sleep(4)` hold the `asyncio.to_thread` worker for up to 6s total per rate-limited batch. For the background analysis job this is acceptable; it would be problematic in a latency-sensitive request path. Mitigation: document that `_download_with_retry` is not suitable for use in request handlers.
- **Stale data silently accepted** — a trader may act on a 23 h-old signal thinking it is fresh. Mitigation: the `"Stale data"` badge in the UI and the `stale_tickers` field in `AnalysisResult` make the staleness explicit. The 24 h hard cutoff prevents very old data from being used.
- **Cache miss on first run** — if `analysis_results` has no prior row for a rate-limited ticker, there is no fallback and the ticker remains in `errors`. This is correct behavior; surfacing an accurate error is better than fabricating data.
- **YFRateLimitError import path** — `yfinance.exceptions.YFRateLimitError` must be imported explicitly; if a future yfinance version moves it, tests will catch the import error. Mitigation: import it at module level so failures are immediate and obvious.

## Migration Plan

No database migration is required. Deployment is a standard image rebuild and container restart. Rollback is reverting the commit and rebuilding.
