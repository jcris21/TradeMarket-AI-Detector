## 1. Schema Migrations

- [x] 1.1 Add idempotent `ALTER TABLE analysis_tickers ADD COLUMN custom_levels TEXT` to startup migrations in `backend/app/db/schema.py`
- [x] 1.2 Add idempotent `ALTER TABLE analysis_tickers ADD COLUMN custom_levels_expires_at TEXT` to startup migrations in `schema.py`
- [x] 1.3 Add idempotent `ALTER TABLE analysis_results ADD COLUMN custom_levels_applied INTEGER DEFAULT 0` to startup migrations in `schema.py`

## 2. Models

- [x] 2.1 Add `ExtractedLevel(BaseModel)` with fields `type: Literal["support", "resistance"]`, `price: float`, `confidence: float` to `backend/app/analysis/models.py`
- [x] 2.2 Add `TraderChartEnrichRequest(BaseModel)` with fields `enrichment_type: Literal["trader_chart"]` and `chart_image: str`
- [x] 2.3 Add `LevelConfirmationRequest(BaseModel)` with fields `enrichment_id: str` and `confirmed_indices: List[int]`
- [x] 2.4 Add `ConfirmedLevel` dataclass/model (type, price) for storage in `analysis_tickers.custom_levels` JSON
- [x] 2.5 Add `TraderChartEnrichResponse(BaseModel)` with fields `enrichment_id: str`, `extracted_levels: List[ExtractedLevel]`, `status: str`

## 3. Image Validation Utility

- [x] 3.1 Implement `validate_chart_image(b64_str: str) -> bytes` in a shared utils module: decode base64, check size ≤ 10 MB, sniff PNG (`\x89PNG`) or JPEG (`\xff\xd8`) magic bytes; raise `HTTPException(400)` on failure; return raw bytes
- [x] 3.2 Write unit tests: valid PNG passes, valid JPEG passes, oversized image rejected, non-image bytes rejected, invalid base64 rejected

## 4. VisionAgent: extract_levels

- [x] 4.1 Add `LEVEL_EXTRACTION_PROMPT` constant to `backend/app/analysis/vision_agent.py`
- [x] 4.2 Implement `async extract_levels(self, image_bytes: bytes) -> List[ExtractedLevel]` using the constrained prompt and structured output schema (`List[ExtractedLevel]`); return `[]` on parse error or model exception
- [x] 4.3 Add 8-second timeout guard around the LiteLLM call in `extract_levels()`; return `[]` on timeout
- [x] 4.4 Write unit tests: mock LiteLLM — valid JSON array parsed to `List[ExtractedLevel]`; malformed JSON returns `[]`; model exception returns `[]`; timeout returns `[]`

## 5. Proximity Filter

- [x] 5.1 Implement `filter_by_proximity(levels: List[ExtractedLevel], current_price: float, max_pct: float = 0.15) -> List[ExtractedLevel]` in `backend/app/analysis/models.py` or a utils module
- [x] 5.2 Write unit tests: level at 2.5% → retained; level at exactly 15% → retained (inclusive); level at 15.5% → discarded; empty list returns empty

## 6. ScoringAgent: _apply_custom_levels

- [x] 6.1 Add `_apply_custom_levels(self, entry_price: float, target_price: float, atr_14: float, confirmed_levels: List[ConfirmedLevel]) -> tuple[float, int]` to `backend/app/analysis/scoring_agent.py`
- [x] 6.2 Implement: +4 for support within 1 ATR of entry; +3 for resistance within 2% of target; max 2 levels evaluated; result clamped to `[0, ENRICHMENT_MAX_DELTA]`
- [x] 6.3 Write unit tests: one support near entry → delta=4; one resistance near target → delta=3; support too far → delta=0; two levels both score → delta=7; cap enforcement; empty levels → (0.0, 0)

## 7. Repository: Custom Levels

- [x] 7.1 Add `store_custom_levels(ticker: str, levels: List[ConfirmedLevel], expires_at: str)` to `backend/app/db/repository.py`
- [x] 7.2 Add `load_active_custom_levels(ticker: str) -> List[ConfirmedLevel]` (returns `[]` if NULL or expired)
- [x] 7.3 Add `expire_stale_levels()` that NULLs `custom_levels` and `custom_levels_expires_at` for all tickers where `custom_levels_expires_at < datetime.utcnow().isoformat()`
- [x] 7.4 Wire `expire_stale_levels()` into application startup in `backend/app/main.py`

## 8. TTL Utility

- [x] 8.1 Implement `trading_days_from_now(n: int) -> datetime` in a utils module: iterate forward skipping weekdays 5 and 6 (Sat/Sun); return UTC datetime
- [x] 8.2 Write unit tests: from Monday, n=1 → Tuesday; from Friday, n=1 → Monday; from Friday, n=5 → next Friday; n=0 → same day

## 9. Route: Enrich Endpoint — trader_chart branch

- [x] 9.1 Add `trader_chart` branch to `POST /api/analysis/enrich/{ticker}` in `backend/app/routes/analysis.py`: call `validate_chart_image()`, call `VisionAgent.extract_levels()`, call `filter_by_proximity()`, call `create_enrichment_job()` with `status="pending_confirmation"` and extracted levels stored in job row, return `TraderChartEnrichResponse`
- [x] 9.2 Store extracted levels (JSON) in `enrichments` row for retrieval at confirmation time
- [x] 9.3 Write integration tests: valid PNG upload returns enrichment_id + extracted_levels; oversized image → 400; extraction returns `[]` → 200 with empty levels

## 10. Route: Confirm Endpoint

- [x] 10.1 Add `POST /api/analysis/enrich/{ticker}/confirm` route accepting `LevelConfirmationRequest`
- [x] 10.2 Validate: `enrichment_id` exists and belongs to ticker → 404 if not; all `confirmed_indices` in bounds → 422 if not; `status == "pending_confirmation"` or already confirmed → idempotency path
- [x] 10.3 Cap confirmed indices to first 2; retrieve confirmed levels from enrichments row
- [x] 10.4 Load latest `AssetAnalysis` for ticker to get `entry_price`, `target_price`, `atr_14`
- [x] 10.5 Call `ScoringAgent._apply_custom_levels()` → `(enrichment_delta, applied_count)`
- [x] 10.6 Store confirmed levels to `analysis_tickers.custom_levels` + set `custom_levels_expires_at`
- [x] 10.7 Update `analysis_results`: `custom_levels_applied = applied_count`, `enrichment_delta = enrichment_delta`
- [x] 10.8 Update `enrichments.status = "completed"`
- [x] 10.9 Return `{"custom_levels_applied": int, "enrichment_delta": float, "score_quant": float, "score_enriched": float}`
- [x] 10.10 Write integration tests: confirm 2 levels scores correctly; confirm 0 levels → delta=0; out-of-range index → 422; unknown enrichment_id → 404; second confirm same id → idempotent 200

## 11. OutcomeDetector Integration

- [x] 11.1 Wire `expire_stale_levels()` into `OutcomeDetector` nightly run in `backend/app/analysis/outcome_detector.py`

## 12. Final Verification

- [x] 12.1 Run `pytest` — all new and existing tests pass
- [x] 12.2 Run `ruff check backend/` — no lint errors
- [x] 12.3 Confirm `expire_stale_levels()` runs on startup without error on a cold DB
- [x] 12.4 Verify idempotent `ALTER TABLE` migrations do not fail on a DB that already has the columns
