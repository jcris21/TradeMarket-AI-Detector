## 1. Schema & Dependencies

- [x] 1.1 Add `playwright` to `pyproject.toml` and run `uv lock`
- [x] 1.2 Add `playwright install chromium --with-deps` step to `Dockerfile` after `uv sync`
- [x] 1.3 Add `CREATE TABLE IF NOT EXISTS enrichments (...)` DDL to `backend/app/db/schema.py`
- [x] 1.4 Add idempotent `ALTER TABLE analysis_tickers ADD COLUMN preferred_chart_url TEXT` to startup migrations in `schema.py`
- [x] 1.5 Add idempotent `ALTER TABLE analysis_results ADD COLUMN enrichment_status TEXT DEFAULT 'none'` to startup migrations in `schema.py`

## 2. Models

- [x] 2.1 Add `EnrichmentType = Literal["screenshot", "trader_chart"]` to `backend/app/analysis/models.py`
- [x] 2.2 Add `ScreenshotEnrichRequest(BaseModel)` with fields `enrichment_type: Literal["screenshot"]` and `source_url: str`
- [x] 2.3 Add `EnrichmentJobResponse(BaseModel)` with fields `enrichment_id: str` and `status: str`
- [x] 2.4 Add `EnrichRequest` union type dispatching on `enrichment_type` discriminator for route validation

## 3. ScreenshotAgent

- [x] 3.1 Create `backend/app/analysis/screenshot_agent.py` with `ScreenshotTimeoutError` and `ScreenshotError` exception classes
- [x] 3.2 Implement `ScreenshotAgent.capture(source_url: str, timeout_ms: int = 30_000) -> bytes` using `async_playwright()`, `try/finally` browser close, `wait_until="networkidle"`
- [x] 3.3 Write unit tests for `ScreenshotAgent`: mock `async_playwright` — test successful capture returns bytes, timeout raises `ScreenshotTimeoutError`, navigation error raises `ScreenshotError`, browser always closed in `finally`

## 4. URL Validation

- [x] 4.1 Implement `validate_source_url(url: str) -> None` in `backend/app/routes/analysis.py` (or a shared utils module): raise `HTTPException(400)` for non-`https://` and for block-list matches
- [x] 4.2 Write unit tests: valid public HTTPS URL passes, `http://` rejected, `localhost` rejected, `127.0.0.1` rejected, `192.168.1.1` rejected, `10.0.0.1` rejected, `169.254.x.x` rejected

## 5. Repository

- [x] 5.1 Add `create_enrichment_job(ticker, enrichment_type, source_url) -> str` (returns UUID) to `backend/app/db/repository.py`
- [x] 5.2 Add `get_enrichment_job(enrichment_id) -> dict | None` to `repository.py`
- [x] 5.3 Add `update_enrichment_job(enrichment_id, status, enrichment_delta=None, error_message=None, completed_at=None)` to `repository.py`
- [x] 5.4 Add `set_ticker_preferred_url(ticker, url)` to `repository.py`
- [x] 5.5 Add `set_analysis_enrichment_status(ticker, status, enrichment_delta=None)` to `repository.py`

## 6. VisionAgent Update

- [x] 6.1 Add `screenshot_bytes: bytes | None = None` parameter to `VisionAgent.analyze()` in `backend/app/analysis/vision_agent.py`
- [x] 6.2 Implement priority logic: use `screenshot_bytes` if not None; else fall back to disk path; else text-only
- [x] 6.3 Write unit tests: `screenshot_bytes` takes priority over disk file, text-only fallback when neither provided

## 7. Route: Enrich Endpoint

- [x] 7.1 Refactor `POST /api/analysis/enrich/{ticker}` (or `/{ticker}/enrich`) in `backend/app/routes/analysis.py` to dispatch on `enrichment_type`
- [x] 7.2 Add `screenshot` branch: call `validate_source_url()`, call `create_enrichment_job()`, add background task, return HTTP 202 `EnrichmentJobResponse`
- [x] 7.3 Preserve legacy path: no `enrichment_type` → existing synchronous VisionAgent text-only flow
- [x] 7.4 Return HTTP 422 for unknown `enrichment_type` values

## 8. Background Task

- [x] 8.1 Implement `_run_screenshot_enrichment(enrichment_id, ticker, source_url)` background task function in `backend/app/routes/analysis.py` or a dedicated module
- [x] 8.2 Task flow: update job to `processing` → `ScreenshotAgent.capture()` → load latest `AssetAnalysis` → `VisionAgent.analyze(screenshot_bytes=bytes)` → compute delta → update job to `completed` + write delta → update `analysis_results` → call `set_ticker_preferred_url()`
- [x] 8.3 On any exception: update job to `failed` with `error_message`; do not update `enrichment_delta` in `analysis_results`
- [x] 8.4 Write integration tests: mock `ScreenshotAgent` and `VisionAgent` — test success path updates both `enrichments` and `analysis_results`; test failure path leaves `analysis_results.enrichment_delta` unchanged

## 9. GET Response Update

- [x] 9.1 Ensure `GET /api/analysis/{ticker}` response includes `enrichment_status` field sourced from `analysis_results.enrichment_status`
- [x] 9.2 Write test: enrichment_status is `"none"` when no enrichment triggered; `"completed"` after background task succeeds

## 10. Final Verification

- [x] 10.1 Run `pytest` — all new and existing tests pass
- [x] 10.2 Run `ruff check backend/` — no lint errors
- [x] 10.3 Verify `uv lock` is up to date with playwright added
- [x] 10.4 Confirm Dockerfile builds successfully with `playwright install chromium --with-deps`
