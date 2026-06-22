## ADDED Requirements

### Requirement: ScoringAgent applies custom level scoring as enrichment_delta post-pass
`ScoringAgent` SHALL expose `_apply_custom_levels(entry_price: float, target_price: float, atr_14: float, confirmed_levels: List[ConfirmedLevel]) -> tuple[float, int]` that computes a discrete integer score boost from trader-confirmed S/R levels and returns `(enrichment_delta, applied_count)`. This method is called from the confirm endpoint, not from the batch scoring pipeline.

#### Scenario: Method exists and is callable from routes
- **WHEN** `ScoringAgent._apply_custom_levels()` is called with valid inputs
- **THEN** it returns a tuple of `(float, int)` without raising

#### Scenario: Batch scoring pipeline unaffected
- **WHEN** `score_and_rank_with_errors()` runs as part of a batch analysis run
- **THEN** `_apply_custom_levels()` is NOT called; `custom_levels_applied` on new `analysis_results` rows remains 0

### Requirement: custom_levels_applied column added to analysis_results
`analysis_results` SHALL gain `custom_levels_applied INTEGER DEFAULT 0` via idempotent `ALTER TABLE` on startup.

#### Scenario: Column added on first deploy
- **WHEN** column does not exist at startup
- **THEN** `ALTER TABLE` adds it with `DEFAULT 0` and startup completes

#### Scenario: Column already present on subsequent deploy
- **WHEN** column already exists
- **THEN** startup completes without error

### Requirement: custom_levels columns added to analysis_tickers
`analysis_tickers` SHALL gain `custom_levels TEXT` (nullable JSON) and `custom_levels_expires_at TEXT` (nullable ISO datetime) via idempotent `ALTER TABLE` on startup.

#### Scenario: Columns added on first deploy
- **WHEN** columns do not exist at startup
- **THEN** both are added as nullable with no default; startup completes

#### Scenario: Columns already present
- **WHEN** both columns already exist
- **THEN** startup completes without error
