## 1. Repository Layer

- [x] 1.1 Verify `analysis_results` schema has `outcome`, `actual_gain_pct`, `actual_loss_pct`, `hold_days` columns in `backend/app/db/schema.py`
- [x] 1.2 Add `update_outcome_atomic(signal_id, outcome, gain_pct, loss_pct, hold_days) -> bool` to `backend/app/db/repository.py` using `UPDATE … WHERE id = ? AND outcome IS NULL` and returning `cursor.rowcount > 0`
- [x] 1.3 Export `update_outcome_atomic` from `backend/app/db/__init__.py`

## 2. OutcomeDetector Module

- [x] 2.1 Create `backend/app/analysis/outcome_detector.py` with `OutcomeDetector` class
- [x] 2.2 Implement `OutcomeDetector.run()` that queries rows with `outcome IS NULL` from `analysis_results`
- [x] 2.3 Add NaN guard: validate `actual_gain_pct` is finite before calling `update_outcome_atomic`; log WARNING and skip if invalid
- [x] 2.4 Call `update_outcome_atomic` per signal; log INFO when `rowcount == 0` (idempotent skip)
- [x] 2.5 Export `OutcomeDetector` from `backend/app/analysis/__init__.py`

## 3. Tests

- [x] 3.1 Create `backend/tests/test_outcome_detector.py`
- [x] 3.2 Write idempotency test: seed two `analysis_results` rows, run `OutcomeDetector` twice, assert `PerformanceSummary` is identical after both runs and no duplicates exist
- [x] 3.3 Write concurrency test: simulate two detector instances reading the same signal_id simultaneously — assert exactly one writes, the other skips (rowcount check)
- [x] 3.4 Write NaN guard test: mock yfinance to return NaN; assert UPDATE is not called and WARNING is logged
- [x] 3.5 Run `uv run --extra dev pytest backend/tests/test_outcome_detector.py -v` — all tests must pass

## 4. Verification

- [x] 4.1 Run full test suite `uv run --extra dev pytest` to confirm no regressions
- [x] 4.2 Run `uv run --extra dev ruff check backend/app/analysis/outcome_detector.py backend/app/db/repository.py` — zero lint errors
