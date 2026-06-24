## 1. Dependencies & Infrastructure

- [x] 1.1 Add `playwright` to `pyproject.toml` via `uv add playwright` and commit updated `uv.lock`
- [x] 1.2 Add `RUN uv run playwright install chromium --with-deps` to Dockerfile after `uv sync` step
- [x] 1.3 Verify `docker build` succeeds with Playwright installed (chromium binary present)

## 2. Schema & Repository

- [x] 2.1 Add `CREATE TABLE IF NOT EXISTS enrichments (...)` to `backend/app/db/schema.py`
- [x] 2.2 Add idempotent `ALTER TABLE analysis_tickers ADD COLUMN preferred_chart_url TEXT` startup migration (catch `OperationalError` on duplicate column)
- [x] 2.3 Add idempotent `ALTER TABLE analysis_results ADD COLUMN enrichment_status TEXT DEFAULT 'none'` startup migration
- [x] 2.4 Add `create_enrichment_job(ticker, enrichment_type, source_url) -> str` to `backend/app/db/repository.py`
- [x] 2.5 Add `get_enrichment_job(enrichment_id) -> dict | None` to repository
- [x] 2.6 Add `update_enrichment_job(enrichment_id, status, enrichment_delta, error_message, completed_at)` to repository
- [x] 2.7 Add `set_ticker_preferred_url(ticker, url)` to repository
- [x] 2.8 Add `reset_stale_enrichments()` to repository (sets `pending`/`processing` → `failed` with `error_message="server restarted"`)
- [x] 2.9 Call `reset_stale_enrichments()` in backend startup lifespan event

## 3. Models

- [x] 3.1 Add `EnrichmentType` enum (`screenshot`, `trader_chart`) to `backend/app/analysis/models.py`
- [x] 3.2 Add `ScreenshotEnrichRequest` Pydantic model (`enrichment_type: EnrichmentType`, `source_url: str`)
- [x] 3.3 Add `EnrichmentJobResponse` Pydantic model (`enrichment_id: str`, `status: str`)
- [x] 3.4 Add `EnrichmentStatus` literal type (`"none"`, `"pending"`, `"processing"`, `"completed"`, `"failed"`)

## 4. URL Validation

- [x] 4.1 Implement `validate_source_url(url: str) -> None` in `backend/app/analysis/screenshot_agent.py` — raises `HTTPException(400)` for non-HTTPS or block-listed hosts
- [x] 4.2 Define `URL_BLOCK_LIST` constant with all private/loopback ranges

## 5. ScreenshotAgent

- [x] 5.1 Create `backend/app/analysis/screenshot_agent.py` with `ScreenshotAgent` class
- [x] 5.2 Implement `async capture(source_url: str, timeout_ms: int = 30_000) -> bytes` — single Playwright session, `try/finally` browser close
- [x] 5.3 Define `ScreenshotTimeoutError` and `ScreenshotError` exception classes
- [x] 5.4 Map `playwright.errors.TimeoutError` → `ScreenshotTimeoutError`; all other Playwright errors → `ScreenshotError`

## 6. VisionAgent Extension

- [x] 6.1 Add `screenshot_bytes: bytes | None = None` parameter to `VisionAgent.analyze()` in `backend/app/analysis/vision_agent.py`
- [x] 6.2 Implement priority logic: `screenshot_bytes` (encode as base64 for LLM) > disk path > text-only fallback
- [x] 6.3 Ensure existing callers (no `screenshot_bytes` arg) are unaffected

## 7. Route & Background Task

- [x] 7.1 Extend `POST /api/analysis/enrich/{ticker}` in `backend/app/routes/analysis.py` to accept `BackgroundTasks` parameter
- [x] 7.2 Add dispatch logic: no `enrichment_type` → existing sync path; `"screenshot"` → async path; other → 422
- [x] 7.3 Implement async path: validate URL → `create_enrichment_job` → `background_tasks.add_task(run_screenshot_enrichment, ...)` → return 202 `EnrichmentJobResponse`
- [x] 7.4 Implement `run_screenshot_enrichment(ticker, enrichment_id, source_url)` background task function: capture → load analysis → VisionAgent(bytes) → update enrichment + analysis_results + preferred_chart_url
- [x] 7.5 On any exception in background task: set `enrichments.status="failed"`, set `error_message`, leave `enrichment_delta` unchanged
- [x] 7.6 Update `GET /api/analysis/{ticker}` response to include `enrichment_status` field from `analysis_results`

## 8. Unit Tests

- [x] 8.1 Test `validate_source_url`: valid HTTPS URL passes; `http://` raises 400; each block-list entry raises 400
- [x] 8.2 Test `ScreenshotAgent.capture()` with mocked Playwright: success returns bytes; `TimeoutError` raises `ScreenshotTimeoutError`; other error raises `ScreenshotError`; browser always closed in `finally`
- [x] 8.3 Test `VisionAgent.analyze()`: `screenshot_bytes` takes priority over disk path; text-only fallback when neither provided
- [x] 8.4 Test `run_screenshot_enrichment` background task with mocked `ScreenshotAgent` and `VisionAgent`: success updates enrichment + analysis_results + preferred_chart_url; capture failure sets status=failed without touching enrichment_delta
- [x] 8.5 Test `reset_stale_enrichments()`: pending/processing rows → failed; completed rows untouched
- [x] 8.6 Test route dispatch: no `enrichment_type` → 200 (sync path); `"screenshot"` → 202 with `enrichment_id`; unknown type → 422; ticker not found → 404

## 9. Integration & Verification

- [x] 9.1 Run full test suite (`uv run pytest`) — all tests green
- [ ] 9.2 Build Docker image and verify `playwright install chromium` succeeds inside container
- [ ] 9.3 Manual smoke test: POST screenshot enrichment → 202 → poll GET until `enrichment_status="completed"` → verify `enrichment_delta` non-null and `preferred_chart_url` set
