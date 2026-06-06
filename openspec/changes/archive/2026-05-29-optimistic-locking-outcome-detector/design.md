## Context

`analysis_results` rows are written by `save_analysis_results()` with `outcome IS NULL`. A future background job — `OutcomeDetector` — is expected to later fetch closing prices via yfinance and write the actual outcome (`TARGET_HIT`, `STOP_HIT`, `EXPIRED`) plus `actual_gain_pct`, `actual_loss_pct`, `hold_days` for each signal.

The bug (NEX-19): if `OutcomeDetector` restarts mid-run or two instances are running simultaneously (e.g., during a rolling deploy), both instances read rows where `outcome IS NULL` before either has committed a write. The second write on the same row is silently redundant — or, worse, overwrites a first write with different price data, producing double-counted gains in hit ratio and profit factor.

The fix is a single-line change to the UPDATE statement: adding `AND outcome IS NULL` as a WHERE predicate converts a blind write into an atomic compare-and-swap at the SQLite level.

## Goals / Non-Goals

**Goals:**
- Guarantee that each `analysis_results` row is written with an outcome at most once, even under restart or concurrent execution.
- Log idempotent skips at INFO severity (not WARNING) so operators do not get noise on normal re-runs.
- Validate `actual_gain_pct` is a finite float before writing (guard against yfinance returning NaN).
- Provide two new test scenarios: idempotency (two sequential runs → identical summary) and simulated concurrency (one writes, one skips).

**Non-Goals:**
- Serializable isolation or distributed locking — SQLite's per-file write lock already serializes concurrent writes; the `AND outcome IS NULL` guard is sufficient for idempotency.
- Retry logic for yfinance fetch failures — out of scope; failures are logged and skipped.
- Changes to the analysis pipeline, scoring, or frontend.

## Decisions

### Decision 1: Atomic UPDATE with `AND outcome IS NULL` over SELECT + UPDATE

**Chosen**: Single `UPDATE … WHERE id = ? AND outcome IS NULL`.

**Rationale**: SQLite executes this atomically within its write lock. `cursor.rowcount == 0` after the UPDATE means another writer already committed the outcome — the row is cleanly skipped. No transaction management or advisory lock needed.

**Alternatives considered**:
- **SELECT then UPDATE** (current implicit pattern): non-atomic; races exist even with SQLite's write lock if SELECT and UPDATE are in separate statements across reconnects.
- **UPSERT (INSERT OR REPLACE)**: would reset all columns on conflict, including the initial analysis data. Not safe.
- **Application-level mutex**: complicates multi-process deployments (gunicorn workers, Docker restarts). Unnecessary given SQLite already serializes writes.

### Decision 2: `update_outcome_atomic()` function in `repository.py`

**Chosen**: Add a new function `update_outcome_atomic(signal_id, outcome, gain_pct, loss_pct, hold_days) -> bool` that returns `True` if the row was updated, `False` if skipped.

**Rationale**: Keeps the atomic guard in the repository layer (same pattern as all other DB operations). `OutcomeDetector` calls this per-signal and handles the skip logic at the caller level.

### Decision 3: NaN guard before UPDATE

**Chosen**: Validate `actual_gain_pct is not None and math.isfinite(actual_gain_pct)` before calling `update_outcome_atomic`. Rows that fail validation are logged at WARNING and skipped.

**Rationale**: yfinance can return NaN price data for delisted or thinly-traded tickers. Writing NaN to the DB would corrupt all downstream calculations that assume finite floats. The guard is 2 lines in `outcome_detector.py`; adding a DB constraint would require a schema migration.

## Risks / Trade-offs

- **SQLite WAL mode required for true concurrency** → Mitigation: project already uses aiosqlite which defaults to WAL; the guard is still correct in journal mode (writes are fully serialized anyway).
- **`rowcount` reliability** → aiosqlite proxies sqlite3 cursor; `cursor.rowcount` is reliable for UPDATE statements. No mitigation needed.
- **yfinance rate limits** → Outcome detection fetches closing prices for potentially many tickers. Mitigation: out of scope for this change; caller is responsible for batching.

## Migration Plan

1. Add `update_outcome_atomic()` to `backend/app/db/repository.py`.
2. Create `backend/app/analysis/outcome_detector.py` with the `OutcomeDetector` class.
3. Add `backend/tests/test_outcome_detector.py` with idempotency and concurrency tests.
4. Run `uv run pytest backend/tests/test_outcome_detector.py` — all tests must pass before merging.
5. No schema migration — `outcome` column already exists on `analysis_results`.
6. No Docker rebuild required — pure Python change.

**Rollback**: Delete `outcome_detector.py`; revert `repository.py` addition. No data is at risk since the feature only adds an atomic guard to an update path.

## Open Questions

*(none — the implementation spec in NEX-19 is fully prescriptive)*
