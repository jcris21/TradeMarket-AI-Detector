## 1. Data Model — TechnicalIndicators & AssetAnalysis

- [x] 1.1 Add `sma_50`, `bb_upper`, `bb_lower`, `bb_bandwidth`, `bb_pct_b` (all `float | None`) to `TechnicalIndicators` frozen dataclass in `models.py`
- [x] 1.2 Add `score_quant: float | None`, `score_legacy: float | None`, `enrichment_delta: float | None` fields to `AssetAnalysis` in `models.py`
- [x] 1.3 Add `score_enriched` computed `@property` to `AssetAnalysis` returning `score_quant + enrichment_delta` when both non-None, else `None`
- [x] 1.4 Update `AssetAnalysis.to_db_row()` to include `score_quant`, `score_legacy`, `enrichment_delta`; omit `score` from new writes

## 2. DB Migration

- [x] 2.1 Add `score_quant REAL`, `score_legacy REAL`, `enrichment_delta REAL` columns to `analysis_results` DDL in `schema.py`
- [x] 2.2 Add three idempotent `ALTER TABLE analysis_results ADD COLUMN` statements in `connection.py` startup migration; silence duplicate-column errors

## 3. DataAgent — New Indicator Computation

- [x] 3.1 Compute `sma_50` via `ta.sma(close, length=50).iloc[-1]` in `_compute_indicators()` in `data_agent.py`; wrap in try/except returning `None` on any error
- [x] 3.2 Compute `bb_upper`, `bb_lower`, `bb_bandwidth`, `bb_pct_b` via `ta.bbands(close, length=20, std=2)` columns in `_compute_indicators()`; share one `bbands()` call; all five BB fields default to `None` on any error

## 4. OrchestratorAgent — Indicator Injection

- [x] 4.1 After Stage 1 completes, copy `sma_50`, `bb_upper`, `bb_lower`, `bb_bandwidth`, `bb_pct_b` from each asset's `TechnicalIndicators` into `asset.indicators_summary` dict before the scoring stage

## 5. ScoringAgent — score_quant Formula

- [x] 5.1 Rename existing `_compute_score()` to `_compute_score_legacy()` — formula unchanged
- [x] 5.2 Implement `_compute_score_quant(asset, indicators_summary)` with all 8 components: rr_component (0–30), confluence_component (0–20), trend_alignment (0/3/6/10), atr_viability (−15/0/+8), bb_squeeze (0/+8), quant_support (0/5/10), quant_resistance (−5/0/+8), regime_adjustment (−10/−5/0/+5); clamp result to [0, 100]
- [x] 5.3 Add `# score_quant formula:` block comment in `scoring_agent.py` documenting all 8 components, their ranges, and conditions (PR acceptance gate)
- [x] 5.4 Update `score_and_rank_with_errors()` to compute both `score_quant` (via `_compute_score_quant`) and `score_legacy` (via `_compute_score_legacy`) per asset; sort by `score_quant` descending
- [x] 5.5 Update `_get_prior_scores()` to query `score_quant` column from the previous run; update `score_delta` to track `score_quant` run-over-run
- [x] 5.6 Log `score_quant` and `score_legacy` side-by-side at DEBUG level per ticker

## 6. Repository — Enrichment Delta Write

- [x] 6.1 Add `update_enrichment_delta(ticker: str, run_id: str, delta: float)` to `repository.py` that writes `enrichment_delta` to the matching `analysis_results` row
- [x] 6.2 Update `save_analysis_results` to write `score_quant`, `score_legacy`, `enrichment_delta`; set `enrichment_delta = NULL` on each batch save
- [x] 6.3 Update `get_latest_analysis` and related queries to return `score_quant`, `score_legacy`, `enrichment_delta`; compute `score_enriched` in the `AssetAnalysis` constructor or response serializer

## 7. API — Enrich Endpoint & Response Updates

- [x] 7.1 Add `POST /api/analysis/{ticker}/enrich` route in `routes/analysis.py`: load latest row, call VisionAgent, compute `raw_delta = (confidence - 0.5) * 30`, clamp to `±ENRICHMENT_MAX_DELTA` (env var, default 15), call `update_enrichment_delta`, return `{ticker, enrichment_delta, score_quant, score_enriched}`
- [x] 7.2 Include `score_quant`, `score_legacy`, `enrichment_delta`, `score_enriched` in `GET /api/analysis/latest` and `GET /api/analysis/{ticker}` responses

## 8. Docs

- [ ] 8.1 Update `docs/api-spec.yml` with `POST /api/analysis/{ticker}/enrich` endpoint spec and updated response schemas for existing analysis endpoints
- [ ] 8.2 Update `docs/data-model.md` with note that back-test scripts must read `score_quant` (not `score`); document `enrichment_delta` and `score_enriched`

## 9. Unit Tests

- [x] 9.1 Test each of the 8 `_compute_score_quant()` components in isolation (rr, confluence, trend_alignment, atr_viability, bb_squeeze, quant_support, quant_resistance, regime_adjustment)
- [x] 9.2 Test score clamping: component sum > 100 → 100; sum < 0 → 0
- [x] 9.3 Test `_compute_score_quant()` with `None` indicator fields (trend_alignment graceful degradation)
- [ ] 9.4 Test `enrichment_delta` clamping: confidence=1.0 → +15, confidence=0.0 → −15, confidence=0.5 → 0.0; custom `ENRICHMENT_MAX_DELTA`
- [x] 9.5 Test `AssetAnalysis.score_enriched` property: both set → sum; `enrichment_delta=None` → `None`
- [x] 9.6 Test ranking: two assets — verify sort by `score_quant`, not `score_legacy`
- [ ] 9.7 Test idempotent migration: running startup twice does not error
- [x] 9.8 Test `_get_prior_scores()` queries `score_quant` column; `score_delta` reflects `score_quant` delta

## 10. Frontend — Score Breakdown Bar (R8)

- [ ] 10.1 Add score breakdown bar to signal detail view: stacked bar showing component contributions (rr, confluence, adjustments); amber glow indicator when `enrichment_delta` is non-null
- [ ] 10.2 Display `score_enriched` in signal card when present; fall back to `score_quant` label otherwise
