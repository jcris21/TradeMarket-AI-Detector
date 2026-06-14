## 1. Database Schema

- [x] 1.1 Add `analysis_runs` DDL to `backend/app/db/schema.py` (7 columns: run_id, user_id, analyzed_at, duration_seconds, total_tickers, successful_tickers, error_count)
- [x] 1.2 Wire `analysis_runs` table creation into `backend/app/db/connection.py` using the existing idempotent migration pattern

## 2. Repository Layer

- [x] 2.1 Add `save_analysis_run(row: dict)` to `backend/app/db/repository.py` — INSERT one row into `analysis_runs`
- [x] 2.2 Update `get_latest_analysis()` in `repository.py` to LEFT JOIN `analysis_runs` on `run_id` and return `run_metadata` dict (or `None`)

## 3. Data Agent — Chunked Download

- [x] 3.1 Replace the single `yf.download(all_tickers, ...)` call in `fetch_indicators_batch()` with a chunked sequential loop; read `ANALYSIS_DATA_CHUNK_SIZE` via `os.environ.get("ANALYSIS_DATA_CHUNK_SIZE", "20")` at call-site
- [x] 3.2 Add `await asyncio.sleep(float(os.environ.get("ANALYSIS_DATA_CHUNK_DELAY_S", "0.5")))` between chunks (not after the last chunk)

## 4. Data Agent — Per-Ticker Retry

- [x] 4.1 After the chunk loop, collect tickers where `_extract_ticker_df()` returned an empty DataFrame
- [x] 4.2 For each empty-result ticker, issue one individual `yf.download(ticker, ...)` retry; on second empty or exception, record as `DataFetchError` in `errors`

## 5. Data Agent — Validation & Timing

- [x] 5.1 Raise minimum-bars threshold in `_compute_indicators` from `len(df) < 30` to `len(df) < 60`
- [x] 5.2 Add `current_price <= 0` guard in `_compute_indicators` that raises `DataFetchError(ticker)`
- [x] 5.3 Wrap `_compute_indicators` call per ticker with wall-clock timing; store elapsed ms; include `"duration_ms": int` in every error dict entry

## 6. Orchestrator Changes

- [x] 6.1 After Stage 1, check `len(successful) < 0.7 * len(tickers)` and raise `HTTPException(503, detail=f"Insufficient data: {len(successful)}/{len(tickers)} tickers returned valid data")` if threshold not met
- [x] 6.2 After `save_analysis_results()`, call `repository.save_analysis_run(...)` with run_id (UUID), analyzed_at, duration_seconds, total_tickers, successful_tickers, and error_count

## 7. API Route

- [x] 7.1 Update `GET /api/analysis/latest` handler in `backend/app/routes/analysis.py` to include `run_metadata` key in response (value is the dict from `get_latest_analysis()`, or `null`)
- [x] 7.2 Update `docs/api-spec.yml` to document the new `run_metadata` field on `GET /api/analysis/latest`

## 8. Tests — Data Agent

- [x] 8.1 Create `backend/tests/test_data_agent_chunking.py` — mock `yf.download`, assert chunk call count matches `ANALYSIS_DATA_CHUNK_SIZE` env override
- [x] 8.2 Test inter-chunk sleep is called `chunk_count - 1` times (mock `asyncio.sleep`)
- [x] 8.3 Test per-ticker retry: batch returns empty → retry returns valid data → ticker in results, not errors
- [x] 8.4 Test per-ticker retry: both batch and retry empty → ticker in errors with `error_message` and `duration_ms`
- [x] 8.5 Test `_compute_indicators` raises `DataFetchError` when `len(df) == 59`
- [x] 8.6 Test `_compute_indicators` raises `DataFetchError` when `current_price == 0`
- [x] 8.7 Test error dict contains `duration_ms` integer for failed tickers

## 9. Tests — Orchestrator Threshold

- [x] 9.1 Create `backend/tests/test_orchestrator_threshold.py` — mock Stage 1 to return 69/100 successful; assert HTTP 503 is raised
- [x] 9.2 Test that 70/100 successful proceeds without raising 503
- [x] 9.3 Test that `save_analysis_run` is NOT called when 503 is raised

## 10. Tests — API & Repository

- [x] 10.1 Test `GET /api/analysis/latest` response includes `run_metadata` with `duration_seconds` after a run
- [x] 10.2 Test `GET /api/analysis/latest` returns `run_metadata: null` when no run exists
- [x] 10.3 Test `save_analysis_run` and `get_latest_analysis` repository methods against a real in-memory SQLite connection
