## ADDED Requirements

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
