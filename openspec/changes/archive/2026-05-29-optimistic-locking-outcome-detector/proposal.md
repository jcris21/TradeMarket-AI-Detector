## Why

`OutcomeDetector` — the background job that evaluates whether past signals hit their target or stop — has no concurrency guard. If two instances run simultaneously (or a job restarts mid-run), both can read the same `analysis_results` rows where `outcome IS NULL` and write duplicate outcomes, silently inflating hit ratio and profit factor metrics.

This is a High-severity correctness bug (NEX-19) because corrupted hit ratio and profit factor directly feed the bet-size card and signal confidence scoring that users act on.

## What Changes

- **New module `backend/app/analysis/outcome_detector.py`** — implements `OutcomeDetector` with an atomic `UPDATE … WHERE id = ? AND outcome IS NULL` pattern; skips rows whose outcome is already written (idempotent).
- **Guard against yfinance NaN** — `actual_gain_pct` validated as a finite float before the UPDATE executes; rows with NaN price data are skipped with a WARNING log, not written.
- **Idempotent skip logging** — `rowcount == 0` logged at INFO (not WARNING/ERROR) to distinguish intentional skips from real failures.
- **Tests** — idempotency test (two sequential runs produce identical `PerformanceSummary`) and concurrency test (two simulated instances: one writes, one skips).

## Capabilities

### New Capabilities

- `outcome-detector`: Atomic outcome resolution for `analysis_results` rows — reads rows with `outcome IS NULL`, fetches closing prices via yfinance, and writes `outcome`, `actual_gain_pct`, `actual_loss_pct`, `hold_days` using an atomic UPDATE with `AND outcome IS NULL` guard.

### Modified Capabilities

*(none — no existing spec-level behavior changes)*

## Impact

- **`backend/app/analysis/outcome_detector.py`** — new file (primary change)
- **`backend/app/db/repository.py`** — add `update_outcome_atomic()` function using `rowcount` check
- **`backend/tests/test_outcome_detector.py`** — new test file (idempotency + concurrency scenarios)
- **`backend/app/db/schema.py`** — verify `outcome`, `actual_gain_pct`, `actual_loss_pct`, `hold_days` columns exist on `analysis_results` (read-only impact; no schema change expected)
- No API changes, no frontend changes, no Docker changes
