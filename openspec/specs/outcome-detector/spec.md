# Spec: outcome-detector

## Purpose

The `OutcomeDetector` capability evaluates completed signal rows in `analysis_results` and writes back the realized outcome (gain/loss percentages, hold duration, win/loss classification). It is designed to be safe under concurrent execution and idempotent across repeated runs.

---

## Requirements

### Requirement: Atomic outcome write with idempotency guard
`OutcomeDetector` SHALL update `analysis_results` rows using a single atomic UPDATE statement with `AND outcome IS NULL` in the WHERE clause, so that concurrent or restarted runs never overwrite an already-written outcome.

#### Scenario: First run writes outcome successfully
- **WHEN** `OutcomeDetector` processes a signal row where `outcome IS NULL`
- **THEN** the UPDATE executes and `rowcount == 1`
- **THEN** `outcome`, `actual_gain_pct`, `actual_loss_pct`, `hold_days` are persisted to the row
- **THEN** the function returns `True`

#### Scenario: Second run skips already-written row
- **WHEN** `OutcomeDetector` processes a signal row where `outcome` is already set
- **THEN** the UPDATE matches zero rows (`rowcount == 0`)
- **THEN** the skip is logged at INFO severity (not WARNING or ERROR)
- **THEN** the function returns `False`
- **THEN** the row's existing outcome value is unchanged

#### Scenario: Two concurrent instances — one writes, one skips
- **WHEN** two `OutcomeDetector` instances read the same signal_id simultaneously
- **THEN** exactly one instance commits the outcome (rowcount == 1)
- **THEN** the other instance observes rowcount == 0 and skips
- **THEN** only one outcome row exists for that signal_id after both complete

### Requirement: NaN guard on actual_gain_pct before write
`OutcomeDetector` SHALL validate that `actual_gain_pct` is a finite float (not NaN, not None, not infinity) before calling `update_outcome_atomic`. Invalid values SHALL cause the row to be skipped with a WARNING log; the UPDATE SHALL NOT execute.

#### Scenario: yfinance returns NaN for actual_gain_pct
- **WHEN** the fetched closing price produces a NaN `actual_gain_pct`
- **THEN** `update_outcome_atomic` is NOT called for that signal
- **THEN** a WARNING is logged identifying the ticker and signal_id
- **THEN** the `analysis_results` row's `outcome` remains NULL

#### Scenario: Valid actual_gain_pct passes guard
- **WHEN** `actual_gain_pct` is a finite float (e.g., 4.2 or -1.8)
- **THEN** `update_outcome_atomic` is called normally
- **THEN** the row is updated if `outcome IS NULL`

### Requirement: hit_ratio excludes EXPIRED from denominator
`PerformanceSummary.hit_ratio` SHALL be computed as `target_hits / (target_hits + stop_hits)`, where the denominator includes only conclusive outcomes. EXPIRED signals SHALL NOT appear in the denominator.

#### Scenario: EXPIRED signals excluded from hit-ratio denominator
- **WHEN** `analysis_results` contains 4 TARGET_HIT, 1 STOP_HIT, and 3 EXPIRED rows
- **THEN** `hit_ratio` is `4 / (4 + 1) = 0.80`
- **THEN** the 3 EXPIRED rows do not affect the denominator

#### Scenario: All signals EXPIRED yields hit_ratio of 0.0
- **WHEN** all resolved signals have `outcome = 'EXPIRED'`
- **THEN** `hit_ratio` is `0.0` (no conclusive outcomes)

#### Scenario: No resolved signals yields hit_ratio of 0.0
- **WHEN** `analysis_results` has no rows with non-NULL outcome
- **THEN** `hit_ratio` is `0.0`

### Requirement: Idempotent PerformanceSummary across repeated runs
Running `OutcomeDetector` twice on the same dataset SHALL produce an identical `PerformanceSummary` (hit_ratio, profit_factor, total_signals) on both runs.

#### Scenario: Two sequential runs on the same analysis_results dataset
- **WHEN** `OutcomeDetector.run()` is called once and completes
- **WHEN** `OutcomeDetector.run()` is called a second time on the same dataset
- **THEN** `PerformanceSummary` after run 1 equals `PerformanceSummary` after run 2
- **THEN** no duplicate outcome rows exist in `analysis_results`

### Requirement: Idempotent skip logged at INFO
When `update_outcome_atomic` returns `False` (row already written), the detector SHALL log the skip at INFO level, not WARNING or ERROR.

#### Scenario: Skipped row logging severity
- **WHEN** `rowcount == 0` after the atomic UPDATE
- **THEN** a log entry at level INFO is emitted containing the signal_id and ticker
- **THEN** no WARNING or ERROR log is emitted for this event

### Requirement: Nightly OutcomeDetector job scheduled via APScheduler
The system SHALL schedule `OutcomeDetector().run()` as a cron job at 02:00 UTC via `AsyncIOScheduler`, registered in the FastAPI `lifespan` context manager. The cron hour SHALL be configurable via the `OUTCOME_DETECTOR_CRON_HOUR` environment variable (default: `2`).

#### Scenario: Scheduler starts with the application
- **WHEN** the FastAPI application starts
- **THEN** `AsyncIOScheduler` is started
- **THEN** the `outcome_detector` job is registered with cron trigger `hour=OUTCOME_DETECTOR_CRON_HOUR`

#### Scenario: Scheduler shuts down cleanly on application stop
- **WHEN** the FastAPI application receives a shutdown signal
- **THEN** `AsyncIOScheduler.shutdown()` is called
- **THEN** no background tasks are left running

#### Scenario: Job error does not crash the scheduler
- **WHEN** `OutcomeDetector().run()` raises an exception during a scheduled run
- **THEN** the exception is logged at ERROR level
- **THEN** the scheduler continues and fires the job again at the next scheduled time

### Requirement: support_break_level populated on STOP_HIT outcomes
When `OutcomeDetector` writes a `STOP_HIT` outcome, it SHALL also set `support_break_level` to `'S1'` on the `analysis_results` row. For TARGET_HIT and EXPIRED outcomes, `support_break_level` SHALL remain NULL.

#### Scenario: STOP_HIT writes support_break_level = 'S1'
- **WHEN** the outcome is determined to be `STOP_HIT`
- **THEN** `update_outcome_atomic` is called with `support_break_level = 'S1'`
- **THEN** the `analysis_results` row has `support_break_level = 'S1'`

#### Scenario: TARGET_HIT leaves support_break_level NULL
- **WHEN** the outcome is determined to be `TARGET_HIT`
- **THEN** `support_break_level` is NOT set (remains NULL)

#### Scenario: EXPIRED leaves support_break_level NULL
- **WHEN** the outcome is determined to be `EXPIRED`
- **THEN** `support_break_level` is NOT set (remains NULL)
