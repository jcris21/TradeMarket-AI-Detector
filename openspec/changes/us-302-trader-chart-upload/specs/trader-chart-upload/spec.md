## ADDED Requirements

### Requirement: POST /api/analysis/enrich/{ticker} accepts trader_chart enrichment type
The API SHALL accept `POST /api/analysis/enrich/{ticker}` with body `{"enrichment_type": "trader_chart", "chart_image": "<base64 string>"}`. It SHALL validate the image (max 10 MB decoded, PNG or JPEG only), call `VisionAgent.extract_levels()`, apply proximity filtering, create an `enrichments` row with `status="pending_confirmation"`, and return HTTP 200 with `{"enrichment_id": "<uuid>", "extracted_levels": [...], "status": "pending_confirmation"}`.

#### Scenario: Valid trader chart upload
- **WHEN** `POST /api/analysis/enrich/AAPL` with `{"enrichment_type": "trader_chart", "chart_image": "<valid base64 PNG>"}` and ticker has a recent analysis row
- **THEN** HTTP 200 with `{"enrichment_id": "<uuid>", "extracted_levels": [{type, price, confidence}, ...], "status": "pending_confirmation"}`

#### Scenario: Image exceeds 10 MB
- **WHEN** decoded base64 image is larger than 10 MB
- **THEN** HTTP 400 with error message "chart_image exceeds maximum size of 10 MB"

#### Scenario: Non-image content type
- **WHEN** decoded bytes do not have a PNG or JPEG magic number
- **THEN** HTTP 400 with error message "chart_image must be PNG or JPEG"

#### Scenario: VisionAgent extraction returns empty list
- **WHEN** VisionAgent cannot identify any S/R levels in the image
- **THEN** HTTP 200 with `{"enrichment_id": "<uuid>", "extracted_levels": [], "status": "pending_confirmation"}`

#### Scenario: Ticker has no analysis row
- **WHEN** no `analysis_results` row exists for the ticker
- **THEN** HTTP 404 is returned and no enrichment job is created

### Requirement: VisionAgent extract_levels uses constrained prompt
`VisionAgent.extract_levels(image_bytes: bytes) -> List[ExtractedLevel]` SHALL call the vision model with the constrained prompt: `"List every horizontal support or resistance line visible in this chart. Return ONLY a JSON array where each element has: 'type' (string: 'support' or 'resistance'), 'price' (float: the price level), 'confidence' (float: 0.0 to 1.0). Do not describe the chart. Do not include any other text. Only the JSON array."`. It SHALL NOT run the full analysis pipeline. It SHALL return `[]` on any parse error or model exception.

#### Scenario: Model returns valid JSON array
- **WHEN** vision model responds with a valid JSON array of level objects
- **THEN** `extract_levels()` returns a `List[ExtractedLevel]` parsed from that array

#### Scenario: Model returns malformed JSON
- **WHEN** vision model response cannot be parsed as a JSON array
- **THEN** `extract_levels()` returns `[]` without raising

#### Scenario: Model includes narrative text
- **WHEN** model response includes explanation text alongside or instead of JSON
- **THEN** `extract_levels()` attempts JSON extraction; returns `[]` if extraction fails

#### Scenario: Model call times out (>8 seconds)
- **WHEN** vision model call exceeds 8 seconds
- **THEN** `extract_levels()` returns `[]` with the enrichments row status set to `"extraction_failed"`

### Requirement: Proximity filter discards out-of-range levels
`filter_by_proximity(levels, current_price, max_pct=0.15)` SHALL discard any level where `abs(level.price - current_price) / current_price > 0.15`. The filtered list SHALL be used in the response and stored as the candidate set for confirmation.

#### Scenario: Level within proximity threshold
- **WHEN** `level.price = 195.0` and `current_price = 200.0` (2.5% away)
- **THEN** level is retained in filtered list

#### Scenario: Level outside proximity threshold
- **WHEN** `level.price = 170.0` and `current_price = 200.0` (15.0% away — exactly at boundary)
- **THEN** level is retained (boundary is inclusive: `<= 0.15`)

#### Scenario: Level beyond proximity threshold
- **WHEN** `level.price = 169.0` and `current_price = 200.0` (15.5% away)
- **THEN** level is discarded

### Requirement: POST /api/analysis/enrich/{ticker}/confirm stores confirmed levels and triggers scoring
`POST /api/analysis/enrich/{ticker}/confirm` with `{"enrichment_id": "<uuid>", "confirmed_indices": [int, ...]}` SHALL: validate `enrichment_id` exists and belongs to the ticker; validate all indices are in bounds; cap confirmed levels to max 2; call `ScoringAgent._apply_custom_levels()` to compute `enrichment_delta` and `custom_levels_applied`; store confirmed levels to `analysis_tickers.custom_levels` JSON; set `custom_levels_expires_at` to `trading_days_from_now(CUSTOM_LEVEL_TTL_DAYS)`; update `analysis_results.custom_levels_applied`; update `analysis_results.enrichment_delta`; update `enrichments.status="completed"`; return HTTP 200 with `{"custom_levels_applied": int, "enrichment_delta": float, "score_quant": float, "score_enriched": float}`.

#### Scenario: Successful confirmation with 2 levels
- **WHEN** `confirmed_indices=[0, 1]` and both levels score
- **THEN** HTTP 200 with `custom_levels_applied=2`, `enrichment_delta` > 0, `score_enriched = score_quant + enrichment_delta`

#### Scenario: Confirmation with 0 levels (clear all)
- **WHEN** `confirmed_indices=[]`
- **THEN** HTTP 200 with `custom_levels_applied=0`, `enrichment_delta=0.0`

#### Scenario: More than 2 indices provided
- **WHEN** `confirmed_indices=[0, 1, 2]`
- **THEN** only first 2 indices are used; third is ignored

#### Scenario: Out-of-range index
- **WHEN** `confirmed_indices=[5]` and `extracted_levels` has only 3 items
- **THEN** HTTP 422 with error "confirmed_indices contains out-of-range values"

#### Scenario: Unknown enrichment_id
- **WHEN** `enrichment_id` does not exist in `enrichments` table
- **THEN** HTTP 404

#### Scenario: Already-confirmed enrichment_id (idempotency)
- **WHEN** confirm is called a second time for the same `enrichment_id`
- **THEN** HTTP 200 with the existing stored result, no re-scoring

### Requirement: Custom levels scored by ScoringAgent with discrete integer rules
`ScoringAgent._apply_custom_levels(entry_price, target_price, atr_14, confirmed_levels)` SHALL compute: +4 pts for each confirmed support level where `abs(level.price - entry_price) <= atr_14`; +3 pts for each confirmed resistance level where `abs(level.price - target_price) / target_price <= 0.02`. Maximum 2 levels evaluated. Result clamped to `[0, ENRICHMENT_MAX_DELTA]`. Returns `(enrichment_delta: float, applied_count: int)`.

#### Scenario: One support near entry
- **WHEN** one confirmed support at `entry_price + 0.5 * atr_14`
- **THEN** `enrichment_delta = 4.0`, `applied_count = 1`

#### Scenario: One resistance near target
- **WHEN** one confirmed resistance at `target_price * 1.01` (1% from target)
- **THEN** `enrichment_delta = 3.0`, `applied_count = 1`

#### Scenario: Support too far from entry
- **WHEN** support at `entry_price + 2 * atr_14`
- **THEN** no points awarded for that level

#### Scenario: Delta capped at ENRICHMENT_MAX_DELTA
- **WHEN** two levels each earn max points and sum exceeds ceiling
- **THEN** `enrichment_delta == ENRICHMENT_MAX_DELTA`

#### Scenario: No confirmed levels
- **WHEN** `confirmed_levels=[]`
- **THEN** `enrichment_delta = 0.0`, `applied_count = 0`

### Requirement: Custom levels stored with TTL in analysis_tickers
Confirmed levels SHALL be stored as JSON in `analysis_tickers.custom_levels`. `custom_levels_expires_at` SHALL be set to `trading_days_from_now(CUSTOM_LEVEL_TTL_DAYS)` where `CUSTOM_LEVEL_TTL_DAYS` defaults to 5. `expire_stale_levels()` SHALL NULL both columns for all tickers where `custom_levels_expires_at < NOW()`. It SHALL run on app startup and be callable by `OutcomeDetector` nightly scheduler.

#### Scenario: Levels stored after confirmation
- **WHEN** confirm succeeds with levels `[{type: "support", price: 195.0}]`
- **THEN** `analysis_tickers.custom_levels` contains the JSON array; `custom_levels_expires_at` is set to 5 trading days from now (skipping weekends)

#### Scenario: TTL skips weekends
- **WHEN** today is Friday and `CUSTOM_LEVEL_TTL_DAYS=1`
- **THEN** `custom_levels_expires_at` is set to Monday (not Saturday)

#### Scenario: Expired levels cleared on startup
- **WHEN** `custom_levels_expires_at` is in the past at startup
- **THEN** `expire_stale_levels()` sets `custom_levels=NULL` and `custom_levels_expires_at=NULL`

### Requirement: custom_levels_applied recorded in analysis_results
`analysis_results.custom_levels_applied INTEGER DEFAULT 0` SHALL be set to the count of custom levels that contributed points to `enrichment_delta` at confirmation time.

#### Scenario: Two levels scored
- **WHEN** two confirmed levels each earn points
- **THEN** `analysis_results.custom_levels_applied = 2`

#### Scenario: No levels scored
- **WHEN** confirmed levels exist but none meet scoring criteria
- **THEN** `analysis_results.custom_levels_applied = 0`
