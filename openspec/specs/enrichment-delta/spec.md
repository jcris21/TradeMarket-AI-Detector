## ADDED Requirements

### Requirement: POST /api/analysis/{ticker}/enrich endpoint
The API SHALL expose `POST /api/analysis/{ticker}/enrich` that loads the most recent `analysis_results` row for the ticker, calls `VisionAgent.analyze_asset()`, maps the LLM confidence to a clamped delta, writes it to the DB, and returns `score_enriched`.

#### Scenario: Successful enrichment
- **WHEN** a valid ticker with a recent analysis row is enriched
- **THEN** response is `{"ticker": "AAPL", "enrichment_delta": 7.5, "score_quant": 68.4, "score_enriched": 75.9}` with HTTP 200

#### Scenario: Ticker has no analysis row
- **WHEN** no `analysis_results` row exists for the ticker
- **THEN** HTTP 404 is returned with a descriptive error message

#### Scenario: VisionAgent call fails
- **WHEN** VisionAgent raises an exception
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
