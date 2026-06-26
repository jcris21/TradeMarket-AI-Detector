### Requirement: POST /api/analysis/{ticker}/enrich endpoint
The API SHALL expose `POST /api/analysis/{ticker}/enrich` that dispatches based on the `enrichment_type` field in the request body:
- If `enrichment_type` is absent or `null`: legacy synchronous path — loads the most recent `analysis_results` row, calls `VisionAgent.analyze()` in text-only mode, maps confidence to a clamped delta, writes it to the DB, and returns `score_enriched` in HTTP 200.
- If `enrichment_type == "screenshot"`: async path — validates URL (HTTPS required, block list enforced), creates an `enrichments` job row, enqueues a background task via FastAPI `BackgroundTasks`, and returns HTTP 202 with `{enrichment_id, status: "pending"}`.
- If `enrichment_type == "trader_chart"`: synchronous extraction path (US-302).
- If `enrichment_type` has any other value: HTTP 422 Unprocessable Entity.

#### Scenario: Legacy enrichment (no enrichment_type)
- **WHEN** `POST /api/analysis/enrich/AAPL` with no `enrichment_type` field
- **THEN** response is HTTP 200 with `{"ticker": "AAPL", "enrichment_delta": <float>, "score_quant": <float>, "score_enriched": <float>}`

#### Scenario: Screenshot enrichment type
- **WHEN** `POST /api/analysis/enrich/AAPL` with `{"enrichment_type": "screenshot", "source_url": "https://example.com"}`
- **THEN** response is HTTP 202 with `{"enrichment_id": "<uuid>", "status": "pending"}`

#### Scenario: Unknown enrichment_type
- **WHEN** `POST /api/analysis/enrich/AAPL` with `{"enrichment_type": "unknown_type"}`
- **THEN** HTTP 422 is returned

#### Scenario: Ticker has no analysis row (all paths)
- **WHEN** no `analysis_results` row exists for the ticker regardless of enrichment_type
- **THEN** HTTP 404 is returned

#### Scenario: VisionAgent call fails (legacy path)
- **WHEN** VisionAgent raises an exception on the legacy path
- **THEN** HTTP 500 is returned; `enrichment_delta` in DB is unchanged

### Requirement: enrichment_delta clamped to ±ENRICHMENT_MAX_DELTA
The enrich endpoint SHALL apply `max_delta = float(os.environ.get("ENRICHMENT_MAX_DELTA", "15"))` at call time and clamp: `enrichment_delta = round(max(-max_delta, min(max_delta, raw_delta)), 2)` where `raw_delta = (confidence - 0.5) * 30`.

#### Scenario: Confidence maps to positive delta within bounds
- **WHEN** VisionAgent returns `confidence=1.0`
- **THEN** `enrichment_delta == 15.0` (ceiling)

#### Scenario: Confidence maps to negative delta at floor
- **WHEN** VisionAgent returns `confidence=0.0`
- **THEN** `enrichment_delta == -15.0` (floor)

#### Scenario: Neutral confidence maps to zero delta
- **WHEN** VisionAgent returns `confidence=0.5`
- **THEN** `enrichment_delta == 0.0`

#### Scenario: Custom ENRICHMENT_MAX_DELTA env var
- **WHEN** `ENRICHMENT_MAX_DELTA=10` and `confidence=1.0`
- **THEN** `enrichment_delta == 10.0` (clamped at custom bound)

### Requirement: enrichment_delta reset to NULL on each batch run
The batch run SHALL set `enrichment_delta = NULL` for all assets in `analysis_results`. The batch run SHALL NOT call VisionAgent.

#### Scenario: Batch run clears prior enrichment
- **WHEN** a batch run completes for a ticker that previously had `enrichment_delta=7.5`
- **THEN** the new row has `enrichment_delta = NULL`

### Requirement: score_enriched returned in GET analysis endpoints
`GET /api/analysis/latest` and `GET /api/analysis/{ticker}` SHALL include `score_enriched` in their response payloads. It SHALL be `null` when `enrichment_delta` is `NULL` in the DB.

#### Scenario: enrichment_delta set
- **WHEN** a ticker's `enrichment_delta=7.5` and `score_quant=68.4`
- **THEN** GET response includes `"score_enriched": 75.9`

#### Scenario: enrichment_delta null
- **WHEN** `enrichment_delta` is `NULL`
- **THEN** GET response includes `"score_enriched": null`

### Requirement: enrichment_delta never affects ranking
The ranking sort in `score_and_rank_with_errors()` SHALL use `score_quant` only. `enrichment_delta` and `score_enriched` SHALL NOT be used as sort keys.

#### Scenario: Enriched asset not re-sorted
- **WHEN** an asset has `score_quant=60` and `enrichment_delta=15.0` (score_enriched=75.0) while another asset has `score_quant=65` and `enrichment_delta=None`
- **THEN** the asset with `score_quant=65` ranks higher
