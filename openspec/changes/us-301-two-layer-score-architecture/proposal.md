## Why

The current scoring formula bakes LLM confidence (30% weight) into the batch-run score, making it non-reproducible and untestable. The v3 architecture removes LLM from the batch run entirely, so the formula must be rewritten as a pure quantitative score — and the visual-enrichment layer's contribution must be explicit, bounded, and stored separately so it never distorts rankings.

## What Changes

- **New `score_quant` field** on `AssetAnalysis`: an 8-component formula using only `TechnicalIndicators` fields (no LLM input), clamped 0–100, used exclusively for ranking and back-test plans.
- **New `enrichment_delta` field** on `AssetAnalysis`: optional ±15-pt increment set on-demand via a new `POST /api/analysis/{ticker}/enrich` endpoint that calls VisionAgent; `NULL` during and after batch runs; never re-sorts the Top 20.
- **Derived `score_enriched` property**: `score_quant + enrichment_delta`, computed at read time, not stored.
- **New `score_legacy` field**: the old confidence-weighted formula kept in parallel for 30-day A/B comparison, then dropped.
- **New indicator fields** on `TechnicalIndicators`: `sma_50`, `bb_upper`, `bb_lower`, `bb_bandwidth`, `bb_pct_b` — all required by the new formula's trend-alignment and squeeze components.
- **Three new DB columns** on `analysis_results`: `score_quant REAL`, `score_legacy REAL`, `enrichment_delta REAL`; added via idempotent `ALTER TABLE`.
- **`score_delta` now tracks `score_quant`** run-over-run (not the old `score`).
- **BREAKING**: Ranking and back-test scripts must read `score_quant`; `score` column remains during transition but is no longer the sort key.

## Capabilities

### New Capabilities

- `score-quant`: Pure-quantitative 8-component scoring formula, new indicator fields, `AssetAnalysis` model additions, DB migration, and ranking sort-key change.
- `enrichment-delta`: On-demand visual enrichment workflow — `POST /api/analysis/{ticker}/enrich`, VisionAgent call, delta clamping, DB write, and `score_enriched` derived field.

### Modified Capabilities

- `score-delta`: `score_delta` now tracks `score_quant` delta run-over-run instead of the legacy composite `score`.

## Impact

- **`backend/app/analysis/models.py`** — `TechnicalIndicators` (5 new fields), `AssetAnalysis` (3 new fields + `score_enriched` property + updated `to_db_row()`)
- **`backend/app/analysis/data_agent.py`** — `_compute_indicators()` computes SMA-50 and Bollinger Band fields via `pandas_ta`
- **`backend/app/analysis/scoring_agent.py`** — new `_compute_score_quant()`, rename existing to `_compute_score_legacy()`, update `score_and_rank_with_errors()` and `_get_prior_scores()`
- **`backend/app/analysis/orchestrator.py`** — injects new indicator fields into `indicators_summary` before scoring stage
- **`backend/app/db/schema.py`** — 3 new columns in `analysis_results` DDL
- **`backend/app/db/connection.py`** — idempotent `ALTER TABLE` migration
- **`backend/app/db/repository.py`** — new `update_enrichment_delta()`, updated `save_analysis_results` and `get_latest_analysis`
- **`backend/app/routes/analysis.py`** — new enrich endpoint; `score_enriched` in GET responses
- **`docs/api-spec.yml`** — enrich endpoint and updated response schemas
- **`docs/data-model.md`** — back-test compatibility note (`score_quant` is canonical)
- **`frontend/`** — score breakdown bar in signal detail view (R8); amber glow on enriched score
