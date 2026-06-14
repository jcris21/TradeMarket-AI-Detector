## Context

The batch analysis pipeline (`ScoringAgent._compute_score()`) currently produces a single composite score mixing quantitative indicators with an LLM confidence value (30% weight). The v3 architecture removes LLM from the batch run entirely. This design separates scoring into two explicit layers:

1. **`score_quant`** — pure deterministic score, computed every batch run, used exclusively for ranking.
2. **`enrichment_delta`** — optional LLM-derived increment, applied on-demand via a new HTTP endpoint, bounded at ±15 pts, stored separately, never affects sort order.

Current state in `backend/app/analysis/`:
- `scoring_agent.py`: `_compute_score()` uses `asset.indicators_summary["llm_confidence"]` for 40% of the score. Removing this changes ranking output.
- `models.py`: `AssetAnalysis` has `score: float | None` and `score_delta: float | None`.
- `data_agent.py`: `TechnicalIndicators` lacks SMA-50 and Bollinger Band fields required by the new formula.
- `schema.py` / `connection.py`: `analysis_results` has `score` and `score_delta` columns; no `score_quant`, `score_legacy`, or `enrichment_delta`.

## Goals / Non-Goals

**Goals:**
- Replace the LLM-dependent composite formula with a deterministic 8-component `score_quant`.
- Add `sma_50`, `bb_upper`, `bb_lower`, `bb_bandwidth`, `bb_pct_b` to `TechnicalIndicators`.
- Store `score_legacy` (old formula) in parallel for 30-day A/B monitoring.
- Deliver `POST /api/analysis/{ticker}/enrich` that calls VisionAgent and writes `enrichment_delta`.
- Keep the `score` column and existing API fields intact during the transition period.

**Non-Goals:**
- Removing `score_legacy` or `score` columns (deferred migration, out of scope).
- Changing Stage 1–3 orchestration timing or parallelism.
- Multi-user support.
- Auto-expiry of the 30-day A/B window.

## Decisions

### Decision 1: `score_quant` computed in `ScoringAgent`, not `OrchestratorAgent`

**Choice:** All score arithmetic stays in `scoring_agent.py`. The orchestrator injects new indicator fields into `indicators_summary` before calling the scoring stage (single injection point).

**Alternative considered:** Compute `score_quant` inside `OrchestratorAgent` alongside Stage 1 data. Rejected — it blurs the boundary between data gathering and scoring, complicating unit testing of the formula in isolation.

### Decision 2: New indicator fields injected via `indicators_summary` dict, not added as top-level `AssetAnalysis` fields

**Choice:** After Stage 1, the orchestrator copies `sma_50`, `bb_upper`, `bb_lower`, `bb_bandwidth`, `bb_pct_b` from the `TechnicalIndicators` dataclass into the existing `indicators_summary` dict. `_compute_score_quant()` reads them from there.

**Alternative considered:** Add them directly as named parameters to `_compute_score_quant()`. Rejected — `indicators_summary` is already the established interface between data and scoring; adding per-field parameters would require a large function signature and break the pattern.

### Decision 3: `enrichment_delta` stored in `analysis_results`, not a separate table

**Choice:** Add `enrichment_delta REAL` column to the existing `analysis_results` table, `NULL` after each batch run, set on-demand by the enrich endpoint.

**Alternative considered:** Separate `enrichment_events` table with a FK to `analysis_results`. Rejected — single-user, single-result-per-run pattern makes a join unnecessary; denormalizing is simpler and sufficient.

### Decision 4: `score_enriched` is a computed property, never stored

**Choice:** `AssetAnalysis.score_enriched` is a `@property` returning `score_quant + enrichment_delta` at read time. Not persisted.

**Rationale:** Storing a derived value creates consistency risk (must be kept in sync). Since `score_quant` and `enrichment_delta` are both stored, the derived sum is always recomputable.

### Decision 5: `ENRICHMENT_MAX_DELTA` read from env var at call-site

**Choice:** `max_delta = float(os.environ.get("ENRICHMENT_MAX_DELTA", "15"))` read inside the enrich endpoint handler, not cached at module import.

**Rationale:** Allows runtime configuration in tests and different deployment environments without restarting the worker.

### Decision 6: `score_delta` tracks `score_quant` run-over-run

**Choice:** `_get_prior_scores()` now queries `score_quant` from the previous run (not `score`). `score_delta` semantics update to reflect `score_quant` delta.

**Rationale:** `score_delta` is used for trend indicators in the UI. Since `score_quant` is the new canonical ranking field, delta should track it.

## Risks / Trade-offs

- **Ranking shift on deploy** → `score_quant` formula produces different values than the old composite. Top 20 ordering will change on first batch run after deploy. Mitigated by `score_legacy` side-by-side logging at DEBUG level for comparison.
- **`pandas_ta` Bollinger Band API stability** → column name format (`BBU_20_2`, `BBL_20_2`, `BBB_20_2`, `BBP_20_2`) may change between minor versions. Mitigated by pinning `pandas_ta` version in `pyproject.toml` and wrapping the call in a try/except that sets all five fields to `None` on any error.
- **60-bar minimum** → SMA-50 requires at least 50 bars; the existing 60-bar minimum guard (NEX-29) is sufficient. No change needed.
- **`enrichment_delta = NULL` reset on each batch run** → A trader who enriches a ticker, then triggers a new batch before viewing results, will lose the delta. Mitigated by the batch run logging a warning per affected ticker; acceptable for v1.
- **`score` column diverges** → The old `score` column is no longer updated by `_compute_score_legacy()` results (it stays as-is from the previous batch). After 30 days, a migration drops it. Mitigated by making `to_db_row()` omit `score` from INSERT/UPDATE after this story ships.

## Migration Plan

1. **DB migration is automatic on container start** — `connection.py` runs three idempotent `ALTER TABLE` statements; duplicate-column errors are silenced. No manual step.
2. **Deploy order**: backend → frontend. No downtime; columns are nullable so old rows are valid.
3. **Rollback**: revert the image tag. Old code reads `score` column (still present); new columns are ignored. `score_delta` will revert to tracking `score`, but data is not lost.
4. **30-day cleanup** (out of scope): separate story to `DROP COLUMN score`, `DROP COLUMN score_legacy`, remove `score_legacy` from `AssetAnalysis`.

## Open Questions

- **R8 (score breakdown bar)**: The Linear issue marks this P1 but doesn't specify the breakdown granularity. Should the bar show all 8 components, or grouped (RR + confluence vs. adjustments)? Recommend 4 grouped bars for readability — needs product sign-off before frontend work starts.
- **Enrich endpoint auth**: Currently no auth on any endpoint. The enrich endpoint calls VisionAgent (LLM cost). Should it be rate-limited or require a header token? Out of scope for this story but worth flagging.
