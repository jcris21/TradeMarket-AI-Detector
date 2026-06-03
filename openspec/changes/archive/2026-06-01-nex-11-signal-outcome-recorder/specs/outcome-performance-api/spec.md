## ADDED Requirements

### Requirement: GET /api/analysis/performance returns aggregated outcome metrics
The system SHALL expose a `GET /api/analysis/performance` endpoint that returns a `PerformanceSummarySchema` JSON object aggregating all resolved signal outcomes from `analysis_results`.

#### Scenario: Endpoint returns correct outcome counts
- **WHEN** `GET /api/analysis/performance` is called
- **THEN** the response contains `total_signals`, `target_hits`, `stop_hits`, `expired`, `orphaned_count`, `hit_ratio`, `profit_factor`
- **THEN** HTTP status is 200

#### Scenario: hit_ratio excludes EXPIRED from denominator
- **WHEN** `analysis_results` contains 3 TARGET_HIT, 1 STOP_HIT, and 2 EXPIRED rows
- **THEN** `hit_ratio` is `3 / (3 + 1) = 0.75`
- **THEN** EXPIRED rows do NOT appear in the denominator

#### Scenario: profit_factor is inf when total losses are zero
- **WHEN** all resolved signals are TARGET_HIT (no STOP_HIT rows)
- **THEN** `profit_factor` is serialized as `null` or a sentinel value agreed with the frontend (not a JSON parse error)

#### Scenario: Empty analysis_results returns zero summary
- **WHEN** no rows exist in `analysis_results`
- **THEN** all counts are `0`, `hit_ratio` is `0.0`, `profit_factor` is `0.0`

### Requirement: orphaned_count reflects signals unresolved after 35 days
The `GET /api/analysis/performance` response SHALL include an `orphaned_count` field equal to the number of rows where `outcome IS NULL` and more than 35 calendar days have elapsed since `analyzed_at`.

#### Scenario: Orphaned count increments when threshold crossed
- **WHEN** a signal row has `outcome IS NULL` and `analyzed_at` is 36+ days ago
- **THEN** `orphaned_count` includes that row

#### Scenario: Recently unresolved signals not counted as orphaned
- **WHEN** a signal row has `outcome IS NULL` and `analyzed_at` is 10 days ago
- **THEN** `orphaned_count` does NOT include that row

### Requirement: Performance summary index for query performance
The system SHALL maintain an index on `analysis_results(outcome)` to keep the summary aggregation fast as the table grows.

#### Scenario: Index present in schema
- **WHEN** the database is initialized
- **THEN** `CREATE INDEX IF NOT EXISTS idx_analysis_outcome ON analysis_results(outcome)` exists
