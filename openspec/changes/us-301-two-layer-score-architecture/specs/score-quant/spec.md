## ADDED Requirements

### Requirement: TechnicalIndicators carries Bollinger Band and SMA-50 fields
The `TechnicalIndicators` frozen dataclass SHALL include five new optional fields: `sma_50`, `bb_upper`, `bb_lower`, `bb_bandwidth`, `bb_pct_b` (all `float | None`), computed in `_compute_indicators()` via `pandas_ta`. Any exception or `None` result from `pandas_ta` SHALL set all five fields to `None` without raising.

#### Scenario: Sufficient data for all indicators
- **WHEN** `_compute_indicators()` runs with 60+ bars of OHLCV data
- **THEN** `sma_50`, `bb_upper`, `bb_lower`, `bb_bandwidth`, `bb_pct_b` are all non-None floats

#### Scenario: pandas_ta raises an exception
- **WHEN** `pandas_ta` raises any exception during Bollinger Band or SMA computation
- **THEN** all five fields are set to `None` and no exception propagates to the caller

#### Scenario: Fewer than 50 bars available
- **WHEN** fewer than 50 bars of data are present (below SMA-50 minimum)
- **THEN** `sma_50` is `None`; other fields may also be `None`

### Requirement: score_quant computed with 8-component formula, no LLM input
The `ScoringAgent` SHALL implement `_compute_score_quant(asset, indicators_summary)` that computes a score from eight components using only `TechnicalIndicators`-derived fields. The result SHALL be clamped to `[0, 100]`. The complete formula SHALL be documented in a `# score_quant formula:` block comment in `scoring_agent.py`.

#### Scenario: All indicators present, strong signal
- **WHEN** `rr_ratio=6.0`, trend bullish, BB squeeze present, entry near support, target below resistance, RSI in optimal zone
- **THEN** `score_quant` is in the upper range (≥70)

#### Scenario: ATR hard-disqualify
- **WHEN** `atr_viability` component returns -15 pts (ATR disqualified)
- **THEN** the -15 pts penalty is applied and the asset may still rank but with reduced score

#### Scenario: Missing optional indicators
- **WHEN** `sma_50` is `None` (insufficient data)
- **THEN** trend_alignment component contributes 0 pts; formula does not raise

#### Scenario: Score clamped at boundaries
- **WHEN** component sum exceeds 100 or falls below 0
- **THEN** `score_quant` is clamped to exactly 100 or 0 respectively

### Requirement: score_quant is the exclusive ranking key
`score_and_rank_with_errors()` SHALL sort qualifying assets by `score_quant` descending. `score_legacy` SHALL NOT influence sort order. Assets with `score_quant = None` SHALL be excluded from the ranked list.

#### Scenario: Ranking by score_quant
- **WHEN** two assets have `score_quant=80` and `score_quant=60`
- **THEN** the asset with `score_quant=80` ranks higher regardless of `score_legacy` values

### Requirement: score_legacy preserved for 30-day A/B comparison
`ScoringAgent` SHALL also compute `score_legacy` by calling `_compute_score_legacy()` (the renamed pre-existing formula). Both `score_quant` and `score_legacy` SHALL be stored to `analysis_results` and returned in API responses. Both SHALL be logged side-by-side at DEBUG level per ticker.

#### Scenario: Both scores computed per asset
- **WHEN** `score_and_rank_with_errors()` processes an asset
- **THEN** `AssetAnalysis.score_quant` and `AssetAnalysis.score_legacy` are both non-None floats

### Requirement: AssetAnalysis model carries score_quant, score_legacy, score_enriched
The `AssetAnalysis` Pydantic model SHALL add `score_quant: float | None`, `score_legacy: float | None`, and a `@property score_enriched: float | None` (returns `score_quant + enrichment_delta` when both are non-None, else `None`). `to_db_row()` SHALL include `score_quant` and `score_legacy`; `score_enriched` is NOT stored.

#### Scenario: score_enriched when both fields set
- **WHEN** `score_quant=68.4` and `enrichment_delta=7.5`
- **THEN** `score_enriched == 75.9`

#### Scenario: score_enriched when enrichment_delta is None
- **WHEN** `enrichment_delta is None`
- **THEN** `score_enriched is None`

### Requirement: Three new DB columns added via idempotent migration
`analysis_results` SHALL gain `score_quant REAL`, `score_legacy REAL`, and `enrichment_delta REAL` columns. The migration SHALL run at startup via idempotent `ALTER TABLE` statements in `connection.py` that silently ignore duplicate-column errors.

#### Scenario: First deploy (columns absent)
- **WHEN** columns do not yet exist on startup
- **THEN** all three are added and startup completes without error

#### Scenario: Subsequent deploy (columns present)
- **WHEN** columns already exist
- **THEN** startup completes without error (duplicate column error silenced)

### Requirement: New indicator fields injected into indicators_summary before scoring
The `OrchestratorAgent` SHALL copy `sma_50`, `bb_upper`, `bb_lower`, `bb_bandwidth`, `bb_pct_b` from each asset's `TechnicalIndicators` into `asset.indicators_summary` after Stage 1 completes, before the scoring stage runs.

#### Scenario: Injection before scoring
- **WHEN** Stage 1 completes and scoring begins
- **THEN** `asset.indicators_summary` contains `sma_50`, `bb_upper`, `bb_lower`, `bb_bandwidth`, `bb_pct_b` keys (values may be `None` if indicators were unavailable)
