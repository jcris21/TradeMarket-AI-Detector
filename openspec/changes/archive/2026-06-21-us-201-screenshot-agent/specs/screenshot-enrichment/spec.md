## ADDED Requirements

### Requirement: POST /api/analysis/enrich/{ticker} accepts screenshot enrichment type
The API SHALL accept `POST /api/analysis/enrich/{ticker}` with body `{"enrichment_type": "screenshot", "source_url": str}`. It SHALL validate the URL, create an `enrichments` row with `status="pending"`, enqueue a background task, and return HTTP 202 with `{"enrichment_id": "<uuid>", "status": "pending"}`.

#### Scenario: Valid screenshot enrichment request
- **WHEN** `POST /api/analysis/enrich/AAPL` with `{"enrichment_type": "screenshot", "source_url": "https://example.com/chart"}`
- **THEN** response is HTTP 202 with `{"enrichment_id": "<uuid>", "status": "pending"}` and a background task is enqueued

#### Scenario: Ticker has no analysis row
- **WHEN** no `analysis_results` row exists for the ticker
- **THEN** HTTP 404 is returned and no enrichment job is created

### Requirement: URL validation blocks non-HTTPS and private/internal addresses
The endpoint SHALL reject any `source_url` that does not start with `https://` or that contains any string from the block list: `["localhost", "127.0.0.1", "0.0.0.0", "169.254.", "10.", "192.168.", "172.16.", "::1"]`.

#### Scenario: Non-HTTPS URL rejected
- **WHEN** `source_url` starts with `http://`
- **THEN** HTTP 400 is returned with message "source_url must use https"

#### Scenario: Localhost URL rejected
- **WHEN** `source_url` contains "localhost"
- **THEN** HTTP 400 is returned with message "source_url targets a disallowed host"

#### Scenario: Private IP rejected
- **WHEN** `source_url` contains "192.168."
- **THEN** HTTP 400 is returned with a disallowed host message

#### Scenario: Valid HTTPS public URL accepted
- **WHEN** `source_url` is "https://finance.yahoo.com/chart/AAPL"
- **THEN** validation passes and request proceeds

### Requirement: ScreenshotAgent captures chart via single headless Chromium session
`ScreenshotAgent.capture(source_url, timeout_ms=30_000)` SHALL launch one headless Chromium browser, navigate to `source_url` with `wait_until="networkidle"`, capture a full-viewport PNG screenshot, close the browser (in a `try/finally`), and return raw PNG bytes.

#### Scenario: Successful capture
- **WHEN** `source_url` loads within 30 seconds
- **THEN** PNG bytes are returned and browser is closed

#### Scenario: Page load timeout
- **WHEN** page does not reach `networkidle` within 30 seconds
- **THEN** `ScreenshotTimeoutError` is raised and browser is still closed via `finally`

#### Scenario: Navigation error (DNS failure, connection refused)
- **WHEN** Playwright raises a non-timeout navigation error
- **THEN** `ScreenshotError` is raised and browser is closed via `finally`

### Requirement: Background task runs capture → VisionAgent → store delta
The background task SHALL: (1) call `ScreenshotAgent.capture()`, (2) load the latest `AssetAnalysis` for the ticker, (3) call `VisionAgent.analyze()` with `screenshot_bytes=<bytes>`, (4) update the `enrichments` row to `status="completed"` with the computed `enrichment_delta`, (5) update `analysis_results` row with `enrichment_delta` and `enrichment_status="completed"`.

#### Scenario: Successful enrichment pipeline
- **WHEN** screenshot capture and VisionAgent analysis both succeed
- **THEN** `enrichments.status="completed"`, `enrichments.enrichment_delta` is set, `analysis_results.enrichment_delta` and `enrichment_status="completed"` are updated

#### Scenario: Screenshot capture fails (timeout)
- **WHEN** `ScreenshotAgent.capture()` raises `ScreenshotTimeoutError`
- **THEN** `enrichments.status="failed"`, `enrichments.error_message` is set, `analysis_results.enrichment_delta` is unchanged

#### Scenario: VisionAgent fails
- **WHEN** VisionAgent raises an exception during analysis
- **THEN** `enrichments.status="failed"`, `analysis_results.enrichment_delta` is unchanged

### Requirement: enrichments table tracks async job lifecycle
The `enrichments` table SHALL be created on startup with columns: `id TEXT PRIMARY KEY`, `ticker TEXT NOT NULL`, `run_id TEXT`, `enrichment_type TEXT NOT NULL`, `source_url TEXT`, `status TEXT NOT NULL DEFAULT 'pending'`, `error_message TEXT`, `enrichment_delta REAL`, `created_at TEXT NOT NULL`, `completed_at TEXT`. Creation SHALL be idempotent (`CREATE TABLE IF NOT EXISTS`).

#### Scenario: Enrichment job created on request
- **WHEN** a valid screenshot enrichment request is received
- **THEN** an `enrichments` row with `status="pending"` and a UUID `id` is inserted

#### Scenario: Enrichment job updated on completion
- **WHEN** background task completes successfully
- **THEN** `enrichments` row has `status="completed"`, `enrichment_delta` set, `completed_at` set

#### Scenario: Table already exists on restart
- **WHEN** `enrichments` table already exists from a prior run
- **THEN** startup completes without error (CREATE TABLE IF NOT EXISTS)

### Requirement: preferred_chart_url saved on successful enrichment
On successful background task completion, `analysis_tickers.preferred_chart_url` SHALL be updated to the `source_url` used in the enrichment.

#### Scenario: Preferred URL saved after success
- **WHEN** screenshot enrichment completes successfully for ticker "AAPL" with `source_url="https://example.com/chart"`
- **THEN** `analysis_tickers` row for "AAPL" has `preferred_chart_url="https://example.com/chart"`

#### Scenario: Preferred URL not updated on failure
- **WHEN** screenshot enrichment fails
- **THEN** `analysis_tickers.preferred_chart_url` is unchanged

### Requirement: enrichment_status exposed on GET /api/analysis/{ticker}
`GET /api/analysis/{ticker}` SHALL include `enrichment_status` in its response (values: `"none"`, `"pending"`, `"processing"`, `"completed"`, `"failed"`). It SHALL reflect the value from `analysis_results.enrichment_status`.

#### Scenario: No enrichment run
- **WHEN** no enrichment has been triggered for the ticker
- **THEN** `enrichment_status` is `"none"` in the GET response

#### Scenario: Enrichment in progress
- **WHEN** background task is running
- **THEN** `enrichment_status` is `"pending"` or `"processing"` in the GET response

#### Scenario: Enrichment complete
- **WHEN** background task has completed
- **THEN** `enrichment_status` is `"completed"` and `enrichment_delta` is non-null

### Requirement: VisionAgent accepts screenshot_bytes parameter
`VisionAgent.analyze()` SHALL accept `screenshot_bytes: bytes | None = None`. When non-None, it SHALL use those bytes as the image input instead of loading from disk. Priority order: `screenshot_bytes` > disk path > text-only fallback.

#### Scenario: screenshot_bytes takes priority over disk path
- **WHEN** `screenshot_bytes` is provided and `screenshots/AAPL.png` also exists on disk
- **THEN** `screenshot_bytes` is used; disk file is not loaded

#### Scenario: text-only fallback when neither source available
- **WHEN** `screenshot_bytes=None` and no disk file exists
- **THEN** VisionAgent proceeds with text-only analysis (existing behavior)
