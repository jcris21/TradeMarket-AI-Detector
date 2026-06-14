## Context

`fetch_indicators_batch()` in `backend/app/analysis/data_agent.py` makes a single `yf.download(all_tickers, ...)` call for the full 100-ticker universe. At this scale, yfinance silently returns empty DataFrames for 30–50% of tickers without raising exceptions. The root cause is yfinance's internal thread-pool hitting rate limits when downloading many tickers simultaneously — it swallows the error and returns an empty result.

The existing minimum-bars validation gate is set at `len(df) < 30`, which is too low for MACD-26 calculations (which need at least 60 bars plus a buffer). The orchestrator does not enforce a minimum success ratio; a run where 60% of tickers fail returns silently with a partial result, indistinguishable from a healthy run.

`duration_seconds` is computed during `run_analysis()` but not persisted; it is unavailable on `GET /api/analysis/latest`.

## Goals / Non-Goals

**Goals:**
- Eliminate silent empty-DataFrame failures by chunking the 100-ticker download into sequential batches of 20 with a configurable inter-chunk delay
- Provide one per-ticker retry for tickers that return empty in the batch pass, before declaring them failures
- Raise data validation threshold to 60 bars minimum and add `current_price > 0` guard
- Enforce a 70% minimum viable run threshold; surface HTTP 503 if the threshold is not met
- Persist per-run metadata (duration, ticker counts, error count) and expose via `GET /api/analysis/latest`
- Add `duration_ms` to error dict entries for per-ticker timing visibility

**Non-Goals:**
- `asyncio.Semaphore` / true async concurrency for yfinance calls — yfinance is not thread-safe for concurrent per-ticker calls; chunked sequential batches are the correct fix
- ScreenshotAgent / VisionAgent (removed in v3 architecture)
- Frontend UI changes to display `run_metadata` (additive API data; frontend may choose to display it later)
- Live liquidity validation (covered by US-104)

## Decisions

### D1: Chunked sequential batches over async concurrency

**Decision**: Split tickers into chunks of `ANALYSIS_DATA_CHUNK_SIZE` (default 20), download each chunk sequentially with `await asyncio.sleep(ANALYSIS_DATA_CHUNK_DELAY_S)` between chunks.

**Rationale**: yfinance uses a thread pool internally and is not safe for concurrent per-ticker calls. The original single-batch call hits rate limits at 100 tickers and silently drops results. Chunked sequential batches give yfinance time to cool down between bursts and keep the implementation simple (no semaphore, no task management).

**Alternative considered**: `asyncio.Semaphore(20)` with 100 individual `yf.download(ticker)` calls. Rejected because yfinance's internal threading still causes race conditions even with an asyncio semaphore wrapping the calls; the silent failure mode is not eliminated.

### D2: One retry per failed ticker, not two

**Decision**: After the chunked loop, any ticker with an empty DataFrame gets exactly one individual `yf.download(ticker)` retry. A second retry would double the tail latency for tickers that are genuinely unavailable without meaningfully improving coverage.

**Rationale**: yfinance empty results in the batch pass are caused by rate limiting, not data absence. A single retry after the batch completes (when rate limits have reset) captures most recoverable failures. The Linear story originally specified 2 retries but the Enhanced spec corrected it to 1.

### D3: `analysis_runs` table in SQLite, not in-memory state

**Decision**: Add an `analysis_runs` table to SQLite (via the existing `duplicate column` guard migration pattern). `orchestrator.run_analysis()` inserts one row per run after `save_analysis_results()`. `repository.get_latest_analysis()` JOINs this table.

**Rationale**: In-memory state is lost on container restart and unavailable to `GET /api/analysis/latest` which reads from the DB. A small append-only table with one row per run is the minimal viable approach and consistent with how other entities are stored.

**Alternative considered**: Storing `duration_seconds` as a column on `analysis_results`. Rejected because run-level metadata (total_tickers, successful_tickers, error_count) doesn't have a natural home in a per-ticker results table.

### D4: Env vars read at call-site via `os.environ.get()`

**Decision**: `ANALYSIS_DATA_CHUNK_SIZE` and `ANALYSIS_DATA_CHUNK_DELAY_S` are read inside `fetch_indicators_batch()` via `os.environ.get()` rather than module-level constants.

**Rationale**: Module-level constants are captured at import time, requiring module reload to change in tests. Call-site reads allow test overrides with `os.environ["ANALYSIS_DATA_CHUNK_SIZE"] = "5"` without reload, as specified in the Linear story's non-functional requirements.

## Risks / Trade-offs

- **[Risk] Stage 1 target may not be met on cold yfinance sessions** → Each chunk of 20 tickers takes ~11s empirically; 5 chunks + 2s delay = ~57s. This is within the 60s Stage 1 target but leaves little margin. If yfinance degrades, individual retries push total time higher. Mitigation: configurable `ANALYSIS_DATA_CHUNK_DELAY_S` allows tuning down to 0.1s if needed.

- **[Risk] 70% threshold blocks valid but data-sparse runs** → If a sector's tickers are temporarily delisted or yfinance has a regional outage, a legitimate run may hit 503. Mitigation: the threshold is explicit (not silent), giving the user actionable feedback. Threshold is hardcoded at 70% per spec; making it configurable is a future option.

- **[Risk] `analysis_runs` table grows unboundedly** → One row per run; at multiple runs per day this is low volume. No retention policy is defined in this story (consistent with the PLAN.md note about `portfolio_snapshots`). Mitigation: a future pruning task can be added; table is append-only so pruning is safe.

- **[Trade-off] Sequential chunks are slower than concurrent calls** → True parallelism would be faster but is unsafe with yfinance. The 60s Stage 1 target was set with chunked sequential in mind. Accept the trade-off.

## Migration Plan

1. Add `analysis_runs` DDL to `db/schema.py` and wire into `connection.py` using the existing migration pattern — no manual step needed, `init_db()` runs on startup
2. Deploy new container image — `init_db()` creates the table automatically on first request
3. First `POST /api/analysis/run` after deploy populates `analysis_runs`; subsequent `GET /api/analysis/latest` includes `run_metadata`
4. Rollback: revert to previous image; `analysis_runs` table remains but is not read by the old code (harmless)

## Open Questions

- Should `GET /api/analysis/latest` return `run_metadata: null` when no run exists yet, or omit the key entirely? (Recommendation: return `null` for explicit client handling)
- Is 60-bar minimum (`len(df) < 60`) correct for MACD-26 with a 34-bar buffer, or should it be adjusted? (The Linear story is definitive on 60; no open question here — documenting for implementor awareness)
