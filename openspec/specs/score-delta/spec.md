## MODIFIED Requirements

### Requirement: score_delta computed via single batch SQL query
The `ScoringAgent` SHALL compute `score_delta` for every `AssetAnalysis` using a single batch query executed before the scoring loop. `score_delta` SHALL track `score_quant` delta run-over-run (not the legacy composite `score`). `_get_prior_scores()` SHALL query `score_quant` from the second-most-recent run.

#### Scenario: Standard run with prior run in DB
- **WHEN** `score_and_rank()` is called with `prior_scores` dict populated from the previous run's `score_quant` values
- **THEN** `score_delta = round(current_score_quant - prior_score_quant, 2)` for each ticker present in the prior run

#### Scenario: New ticker not in prior run
- **WHEN** a ticker appears in the current run but not in `prior_scores`
- **THEN** `score_delta = 0.0` (no change baseline)

#### Scenario: First run — no prior run in DB
- **WHEN** `_get_prior_scores()` finds no second-most-recent run (`OFFSET 1` returns empty)
- **THEN** `prior_scores = {}` and all `score_delta = 0.0`

#### Scenario: DB error during batch query
- **WHEN** `analysis_results` table does not exist or raises `aiosqlite.OperationalError`
- **THEN** `prior_scores = {}` and all `score_delta = 0.0` without raising

### Requirement: analysis_results stores score_delta column
The `analysis_results` table SHALL have a `score_delta REAL` nullable column applied via lazy migration at startup.

#### Scenario: Migration on existing database
- **WHEN** column already exists from a previous run
- **THEN** startup completes without error (duplicate column name error silently ignored; all other errors propagate)

### Requirement: AssetAnalysis model exposes score_delta
The `AssetAnalysis` Pydantic model SHALL include `score_delta: float | None` serialized in all analysis API responses.
