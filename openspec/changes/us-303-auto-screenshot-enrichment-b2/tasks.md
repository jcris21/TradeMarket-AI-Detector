## 1. Models & Schema

- [x] 1.1 Add `enrichment_type: Optional[Literal["trader_chart", "auto_screenshot"]] = None` field to `AssetAnalysis` in `backend/app/analysis/models.py`
- [x] 1.2 Include `"enrichment_type": self.enrichment_type` in `AssetAnalysis.to_db_row()` method
- [x] 1.3 Add `class AutoScreenshotEnrichRequest(BaseModel)` with `enrichment_type: Literal["auto_screenshot"]` and `source_url: str` to `models.py`
- [x] 1.4 Update `EnrichRequest` discriminated union in `models.py` to include `AutoScreenshotEnrichRequest` (place before `ScreenshotEnrichRequest`)
- [x] 1.5 Update `EnrichmentType` literal to `Literal["screenshot", "trader_chart", "auto_screenshot"]`
- [x] 1.6 Add `class SegmentPerformance(BaseModel)` with `total: int`, `hit_ratio: Optional[float]`, `profit_factor: Optional[float]`, `realized_rr: Optional[float]` to `models.py`
- [x] 1.7 Add `b2_enriched: Optional[SegmentPerformance] = None` and `non_enriched: Optional[SegmentPerformance] = None` to `PerformanceResponse` in `models.py`
- [x] 1.8 Add `enrichment_type TEXT` column to `analysis_results` DDL in `backend/app/db/schema.py`

## 2. Database Migration

- [x] 2.1 Add migration guard in `backend/app/db/connection.py`: `ALTER TABLE analysis_results ADD COLUMN enrichment_type TEXT` wrapped in `try/except OperationalError` (duplicate column silently ignored)
- [x] 2.2 Update `update_enrichment_delta` in `backend/app/db/repository.py` to also write `enrichment_type` parameter to `analysis_results`
- [x] 2.3 Update `set_analysis_enrichment_status` in `repository.py` to accept and write an optional `enrichment_type` parameter

## 3. Route Handler — auto_screenshot Discriminator

- [x] 3.1 Add `AutoScreenshotEnrichRequest` to imports in `backend/app/routes/analysis.py`
- [x] 3.2 Add idempotency query in `enrich_ticker()`: before `create_enrichment_job`, check for existing `enrichments` row with `ticker=ticker`, `enrichment_type IN ("auto_screenshot","screenshot")`, `status IN ("pending","processing")`; if found, return 202 with existing `enrichment_id`
- [x] 3.3 Add `elif isinstance(body, AutoScreenshotEnrichRequest)` branch in `enrich_ticker()` that routes to `_run_screenshot_enrichment` with `enrichment_type="auto_screenshot"`
- [x] 3.4 Ensure `isinstance(body, ScreenshotEnrichRequest)` branch normalizes to `enrichment_type="auto_screenshot"` when calling `create_enrichment_job`

## 4. Background Task — B2 Formula & Conflict Resolution

- [x] 4.1 Replace the delta formula in `_run_screenshot_enrichment` with B2 formula: `min(confidence * ENRICHMENT_MAX_DELTA + (SUPPORT_VALIDATED_BONUS if analysis.support_validated else 0.0), ENRICHMENT_MAX_DELTA)`
- [x] 4.2 Read `ENRICHMENT_MAX_DELTA` and `SUPPORT_VALIDATED_BONUS` from `os.environ` at task execution time (not module load) with defaults `"15"` and `"2.0"` respectively
- [x] 4.3 After computing `enrichment_delta_b2`, read current `analysis_results.enrichment_delta` for the ticker and apply `final_delta = max(enrichment_delta_b2, existing_delta or 0.0)`
- [x] 4.4 Store `argument_display = f"💬 Visual analysis: {analysis.argument}"` and pass it to `update_enrichment_job` / write directly to `analysis_results.argument` for the ticker
- [x] 4.5 Pass `enrichment_type="auto_screenshot"` to `update_enrichment_delta` and `set_analysis_enrichment_status` calls in the background task
- [x] 4.6 Add `enrichment_path="B2"` structured field to all `logger` calls inside `_run_screenshot_enrichment`

## 5. Performance Summary — B2 Segmentation

- [x] 5.1 Extend `get_performance_summary()` in `repository.py` to run a second query for `enrichment_type = "auto_screenshot"` rows with resolved outcomes
- [x] 5.2 Extend `get_performance_summary()` to run a third query for non-B2 rows (`enrichment_type IS NULL OR enrichment_type != "auto_screenshot"`) with resolved outcomes
- [x] 5.3 Apply same 30-signal minimum gate per segment (`target_hits + stop_hits < 30` → segment block is `None`)
- [x] 5.4 Populate `b2_enriched` and `non_enriched` fields on the returned `PerformanceResponse`

## 6. Unit Tests

- [x] 6.1 Test B2 formula: `confidence=0.87, support_validated=False` → `enrichment_delta=13.05`
- [x] 6.2 Test B2 formula: `confidence=0.87, support_validated=True` → `enrichment_delta=15.0` (capped)
- [x] 6.3 Test B2 formula: `confidence=1.0, support_validated=True` → `enrichment_delta=15.0` (cap)
- [x] 6.4 Test B2 formula: `confidence=0.1, support_validated=False` → `enrichment_delta=1.5`
- [x] 6.5 Test B1+B2 `max()`: existing delta `8.0`, B2 delta `13.05` → final `13.05`
- [x] 6.6 Test B1+B2 `max()`: existing delta `14.5`, B2 delta `9.0` → final `14.5`
- [x] 6.7 Test `validate_source_url` blocks: `file://`, `http://`, `localhost`, `127.0.0.1`, `10.0.0.1`, `192.168.1.1`, `169.254.x.x`
- [x] 6.8 Test idempotency: second request for same ticker while status=`"pending"` returns existing `enrichment_id` without creating a new row
- [x] 6.9 Test `argument` display prefix: VisionAgent argument `"Breakout"` → stored as `"💬 Visual analysis: Breakout"`
- [x] 6.10 Test `SegmentPerformance` and `PerformanceResponse` serialization with and without segment blocks

## 7. Integration Tests

- [x] 7.1 POST `enrichment_type="auto_screenshot"` returns 202 and `enrichments` row has `enrichment_type="auto_screenshot"`
- [x] 7.2 POST `enrichment_type="screenshot"` (alias) also creates row with `enrichment_type="auto_screenshot"`
- [x] 7.3 POST with unknown ticker returns 404 and no `enrichments` row created
- [x] 7.4 `GET /api/analysis/{ticker}` response includes `enrichment_type` field after enrichment completes
- [x] 7.5 `GET /api/analysis/latest` response includes `enrichment_type` per row
- [x] 7.6 Migration guard: existing DB without `enrichment_type` column starts up cleanly and column is present after startup
- [x] 7.7 B1 (`trader_chart`) flow still works end-to-end with no regression

## 8. Frontend — Signal Detail Panel

- [x] 8.1 Update signal detail panel to display `score_quant` and `score_enriched` side by side with label `"+{delta} visual, auto screenshot"` when `enrichment_type="auto_screenshot"`
- [x] 8.2 Render `argument` field as-is (prefix `"💬 Visual analysis: "` is already embedded in the stored value — no additional formatting needed in frontend)
- [x] 8.3 Hide `score_enriched` side-by-side block when `enrichment_type` is null or `enrichment_delta` is null
