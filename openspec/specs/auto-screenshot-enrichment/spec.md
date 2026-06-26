# Spec: auto-screenshot-enrichment

## Purpose

The `auto-screenshot-enrichment` capability defines the B2 enrichment path: accepting `auto_screenshot` enrichment requests, applying the B2 delta formula (confidence × max_delta + optional support_validated bonus, capped at max_delta), persisting the `argument` with a visual analysis prefix, resolving B1/B2 conflicts by taking the maximum delta, and guarding against duplicate in-flight enrichment jobs.

---

## Requirements

### Requirement: POST /api/analysis/{ticker}/enrich accepts auto_screenshot enrichment type
The endpoint SHALL accept `enrichment_type="auto_screenshot"` in addition to the existing `"screenshot"` value. Both SHALL be routed to the same background task `_run_screenshot_enrichment`. The `enrichments` table row SHALL store `enrichment_type="auto_screenshot"` for both values (normalized at write time).

#### Scenario: auto_screenshot request returns 202
- **WHEN** `POST /api/analysis/AAPL/enrich` with `{"enrichment_type": "auto_screenshot", "source_url": "https://example.com/chart"}`
- **THEN** response is HTTP 202 with `{"enrichment_id": "<uuid>", "status": "pending"}` and `enrichments` row has `enrichment_type="auto_screenshot"`

#### Scenario: legacy screenshot alias still accepted
- **WHEN** `POST /api/analysis/AAPL/enrich` with `{"enrichment_type": "screenshot", "source_url": "https://example.com/chart"}`
- **THEN** response is HTTP 202 and the `enrichments` row stores `enrichment_type="auto_screenshot"` (normalized)

#### Scenario: Ticker has no analysis row
- **WHEN** no `analysis_results` row exists for the ticker
- **THEN** HTTP 404 is returned and no enrichment job is created

### Requirement: B2 delta formula applied on auto_screenshot path
`_run_screenshot_enrichment` SHALL compute the enrichment delta using the B2 formula: `min(confidence × ENRICHMENT_MAX_DELTA + (SUPPORT_VALIDATED_BONUS if support_validated else 0.0), ENRICHMENT_MAX_DELTA)` where `ENRICHMENT_MAX_DELTA = float(os.environ.get("ENRICHMENT_MAX_DELTA", "15"))` and `SUPPORT_VALIDATED_BONUS = float(os.environ.get("SUPPORT_VALIDATED_BONUS", "2.0"))`.

#### Scenario: Nominal B2 delta without support_validated bonus
- **WHEN** VisionAgent returns `confidence=0.87` and `support_validated=False`
- **THEN** `enrichment_delta = 13.05` (0.87 × 15 = 13.05)

#### Scenario: B2 delta with support_validated bonus
- **WHEN** VisionAgent returns `confidence=0.87` and `support_validated=True`
- **THEN** `enrichment_delta = 15.0` (min(0.87 × 15 + 2.0, 15) = 15.0)

#### Scenario: B2 delta capped at ENRICHMENT_MAX_DELTA
- **WHEN** VisionAgent returns `confidence=1.0` and `support_validated=True`
- **THEN** `enrichment_delta = 15.0` (capped at 15)

#### Scenario: Low confidence yields small but non-negative delta
- **WHEN** VisionAgent returns `confidence=0.1` and `support_validated=False`
- **THEN** `enrichment_delta = 1.5` (0.1 × 15)

#### Scenario: Custom ENRICHMENT_MAX_DELTA env var respected
- **WHEN** `ENRICHMENT_MAX_DELTA=10` and `confidence=0.8` and `support_validated=False`
- **THEN** `enrichment_delta = 8.0` (0.8 × 10)

### Requirement: argument stored with visual analysis prefix
After VisionAgent analysis, the `argument` field SHALL be stored as `"💬 Visual analysis: {analysis.argument}"` in `analysis_results.argument` for the ticker's row.

#### Scenario: argument prefix applied on successful enrichment
- **WHEN** VisionAgent returns `argument="Strong breakout above resistance with volume confirmation"`
- **THEN** `analysis_results.argument` for the ticker is updated to `"💬 Visual analysis: Strong breakout above resistance with volume confirmation"`

#### Scenario: argument not modified on VisionAgent failure
- **WHEN** VisionAgent raises an exception
- **THEN** `analysis_results.argument` retains its prior value

### Requirement: B1 + B2 conflict resolved by taking max delta
When a `trader_chart` enrichment delta already exists for the same ticker, the `auto_screenshot` background task SHALL read the current `analysis_results.enrichment_delta` and apply `max(b2_delta, existing_delta)` before writing.

#### Scenario: B2 delta higher than existing B1 delta
- **WHEN** `analysis_results.enrichment_delta = 8.0` (from B1) and B2 computes `enrichment_delta = 13.05`
- **THEN** `analysis_results.enrichment_delta` is updated to `13.05`

#### Scenario: B1 delta higher than B2 delta
- **WHEN** `analysis_results.enrichment_delta = 14.5` (from B1) and B2 computes `enrichment_delta = 9.0`
- **THEN** `analysis_results.enrichment_delta` remains `14.5`

#### Scenario: No prior B1 enrichment
- **WHEN** `analysis_results.enrichment_delta` is NULL and B2 computes `enrichment_delta = 11.0`
- **THEN** `analysis_results.enrichment_delta` is set to `11.0`

### Requirement: Idempotency guard prevents duplicate in-flight enrichment jobs
Before creating a new enrichment job, the endpoint SHALL query for any existing `enrichments` row with matching `ticker` and `enrichment_type IN ("auto_screenshot", "screenshot")` and `status IN ("pending", "processing")`. If found, the endpoint SHALL return HTTP 202 with the existing `enrichment_id`.

#### Scenario: Duplicate request while job is pending
- **WHEN** an enrichment job for AAPL with `enrichment_type="auto_screenshot"` is already `status="pending"`
- **THEN** the second request returns HTTP 202 with the same `enrichment_id` and no new `enrichments` row is created

#### Scenario: Duplicate request while job is processing
- **WHEN** an enrichment job for AAPL is `status="processing"`
- **THEN** the second request returns HTTP 202 with the existing `enrichment_id`

#### Scenario: New request after prior job completed
- **WHEN** the previous enrichment job is `status="completed"`
- **THEN** a new enrichment job is created and a new `enrichment_id` is returned
