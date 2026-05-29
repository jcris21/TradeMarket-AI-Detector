## Why

A DB write failure during Stage 4 aborts the entire analysis run even when Stages 1–3 completed successfully — the trader opens the dashboard with no results and no explanation. The `AnalysisResult.errors[]` field already exists but is only populated for vision-analysis failures, not for DB write failures.

## What Changes

- `save_analysis_results()` in `repository.py` wraps each INSERT in `try/except aiosqlite.Error` so a single-ticker write failure does not abort the batch
- Failed tickers are appended to `errors[]` with their DB error message and their rank is set to `None`
- `orchestrator.py` returns partial `AnalysisResult` (with `errors` populated) instead of raising on write failure
- The analysis API endpoint returns HTTP 200 with a non-empty `errors` array instead of HTTP 500 when all writes fail but the pipeline ran

## Capabilities

### New Capabilities
- `db-write-resilience`: Per-ticker DB write failure isolation — run continues, failed tickers appear in `errors[]`, partial results are returned to the frontend

### Modified Capabilities
<!-- No existing spec-level requirements change — this adds resilience without altering the observable happy-path behavior -->

## Impact

- `backend/app/db/repository.py` — `save_analysis_results()` becomes per-row fault-tolerant
- `backend/app/analysis/orchestrator.py` — catches write errors and surfaces them via `errors[]`
- `backend/tests/` — new test for `aiosqlite.OperationalError` during write
- No frontend changes required — `errors[]` is already part of the API response schema
