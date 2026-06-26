## Why

The existing screenshot enrichment path (`enrichment_type="screenshot"`) applies a symmetric delta formula `(confidence - 0.5) * 30` designed for the legacy manual path, not for a dedicated automated visual analysis flow. US-303 introduces `enrichment_type="auto_screenshot"` as a first-class enrichment path (Path B2) with its own delta formula, `enrichment_type` field persistence for outcome segmentation, and side-by-side score display — enabling traders and the system to separately track how automated visual analysis impacts signal quality over time.

## What Changes

- **New discriminator value** `"auto_screenshot"` added to `POST /api/analysis/{ticker}/enrich`; `"screenshot"` retained as backward-compat alias
- **B2 delta formula** replaces the existing formula for this path: `min(confidence × 15 + support_validated_bonus, 15)` (was `(confidence - 0.5) * 30`)
- **`AssetAnalysis.enrichment_type`** field added (`Optional[Literal["trader_chart", "auto_screenshot"]]`) — persisted in `analysis_results.enrichment_type` column
- **`argument` display prefix** `"💬 Visual analysis: "` prepended before persisting the narrative field
- **B1 + B2 conflict resolution**: when both trader_chart and auto_screenshot deltas exist for same ticker/run, `max(delta_b1, delta_b2)` is applied
- **Idempotency guard**: duplicate enrichment request for same ticker + type while a job is `pending`/`processing` returns the existing `enrichment_id` (no new Playwright session)
- **Outcome segmentation**: `GET /api/analysis/performance` gains optional `b2_enriched` and `non_enriched` blocks once 30 resolved signals exist per segment
- **Frontend**: signal detail panel shows `score_quant` and `score_enriched (+N visual, auto screenshot)` side by side

## Capabilities

### New Capabilities

- `auto-screenshot-enrichment`: New `enrichment_type="auto_screenshot"` discriminator with B2 delta formula (`confidence × ENRICHMENT_MAX_DELTA + support_validated_bonus`, capped at 15), `"💬 Visual analysis: "` argument prefix, idempotency guard for duplicate in-flight jobs, and B1+B2 `max()` conflict resolution
- `enrichment-type-field`: `AssetAnalysis.enrichment_type` field (`Optional[Literal["trader_chart", "auto_screenshot"]]`), corresponding `analysis_results.enrichment_type` TEXT column with migration guard, and persistence through `to_db_row()` / `update_enrichment_delta`

### Modified Capabilities

- `outcome-performance-api`: Performance summary response gains `b2_enriched` and `non_enriched` sub-objects, each with `total`, `hit_ratio`, `profit_factor`, `realized_rr`, gated behind a 30-signal minimum per segment

## Impact

**Backend files**:
- `backend/app/analysis/models.py` — `AssetAnalysis`, `AutoScreenshotEnrichRequest`, `EnrichRequest` union, `EnrichmentType` literal, `PerformanceResponse`
- `backend/app/routes/analysis.py` — `enrich_ticker()` handler, `_run_screenshot_enrichment()` task
- `backend/app/db/schema.py` — `analysis_results` DDL
- `backend/app/db/connection.py` — migration guard for new column
- `backend/app/db/repository.py` — `update_enrichment_delta`, `set_analysis_enrichment_status`, `get_performance_summary`

**Frontend files**:
- Signal detail panel component — side-by-side score display, argument prefix rendering

**API contract changes**: `POST /api/analysis/{ticker}/enrich` now accepts `enrichment_type="auto_screenshot"` (additive, non-breaking). `GET /api/analysis/performance` response gains optional fields (non-breaking).

**Dependencies**: US-201 (ScreenshotAgent/Playwright), US-301 (`enrichment_delta` field), US-302 (`trader_chart` path — B1+B2 max logic depends on this existing).
