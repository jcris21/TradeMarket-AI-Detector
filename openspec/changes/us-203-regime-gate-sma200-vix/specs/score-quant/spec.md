## MODIFIED Requirements

### Requirement: AssetAnalysis carries score_quant, score_legacy, score_enriched
The `AssetAnalysis` Pydantic model SHALL add `score_quant: float | None`, `score_legacy: float | None`, `rank_exclusion_reason: str | None = None`, and a `@property score_enriched: float | None` (returns `score_quant + enrichment_delta` when both are non-None, else `None`). `to_db_row()` SHALL include `score_quant`, `score_legacy`, and `rank_exclusion_reason`. `score_enriched` is NOT stored.

#### Scenario: score_enriched when both fields set
- **WHEN** `score_quant=68.4` and `enrichment_delta=7.5`
- **THEN** `score_enriched == 75.9`

#### Scenario: score_enriched when enrichment_delta is None
- **WHEN** `enrichment_delta is None`
- **THEN** `score_enriched is None`

#### Scenario: rank_exclusion_reason persisted
- **WHEN** an asset has `rank_exclusion_reason="regime_bearish"` and is saved via `to_db_row()`
- **THEN** `rank_exclusion_reason` appears in the returned dict with value `"regime_bearish"`

#### Scenario: rank_exclusion_reason None for normal assets
- **WHEN** an asset is ranked normally and `rank_exclusion_reason` is not set
- **THEN** `to_db_row()` includes `rank_exclusion_reason: None`

### Requirement: Three new DB columns added via idempotent migration
`analysis_results` SHALL gain `score_quant REAL`, `score_legacy REAL`, `enrichment_delta REAL`, and `rank_exclusion_reason TEXT` columns. The migration SHALL run at startup via idempotent `ALTER TABLE` statements in `schema.py` (or `connection.py`) that silently ignore duplicate-column errors.

#### Scenario: First deploy (columns absent)
- **WHEN** all four columns do not yet exist on startup
- **THEN** all four are added and startup completes without error

#### Scenario: Subsequent deploy (columns present)
- **WHEN** all columns already exist
- **THEN** startup completes without error (duplicate column error silenced)
