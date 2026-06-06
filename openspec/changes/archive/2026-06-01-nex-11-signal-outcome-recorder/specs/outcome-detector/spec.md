## MODIFIED Requirements

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

## ADDED Requirements

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
