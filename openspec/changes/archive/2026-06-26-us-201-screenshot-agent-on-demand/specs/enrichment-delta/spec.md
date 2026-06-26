## MODIFIED Requirements

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
