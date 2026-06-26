## Why

The batch analysis pipeline (DataAgent × 100 + ScoringAgent) must stay fast (30–90 s); adding browser-based screenshot capture to that loop is too slow and blocks signal delivery. US-201 moves ScreenshotAgent out of the batch entirely, making it an on-demand enrichment that a trader triggers explicitly for a single high-interest ticker after the batch run completes.

## What Changes

- New async `POST /api/analysis/enrich/{ticker}` path for `enrichment_type: "screenshot"` — returns HTTP 202 immediately, runs capture + VisionAgent in a background task
- New `ScreenshotAgent` class — single headless Chromium session per request via Playwright, 30 s timeout, SSRF-safe URL validation
- `VisionAgent.analyze()` extended with `screenshot_bytes: bytes | None` parameter — async background tasks pass bytes directly instead of reading from disk
- New `enrichments` table — tracks async job lifecycle (`pending → processing → completed / failed`)
- Schema additions: `analysis_tickers.preferred_chart_url`, `analysis_results.enrichment_status`
- Playwright added to `pyproject.toml`; `playwright install chromium --with-deps` added to Dockerfile
- `GET /api/analysis/{ticker}` exposes `enrichment_status` and `enrichment_delta` (already in enrichment-delta spec)

## Capabilities

### New Capabilities

- `screenshot-enrichment`: On-demand ScreenshotAgent pipeline — URL validation, single Playwright session, background task orchestration (capture → VisionAgent → delta store), enrichments table lifecycle, preferred_chart_url persistence

### Modified Capabilities

- `enrichment-delta`: The unified `POST /api/analysis/enrich/{ticker}` endpoint gains an async dispatch branch for `enrichment_type="screenshot"` (returns 202) alongside the existing synchronous legacy path (returns 200); unknown types return 422

## Impact

- **Backend — new file**: `backend/app/analysis/screenshot_agent.py`
- **Backend — modified**: `backend/app/routes/analysis.py`, `backend/app/analysis/vision_agent.py`, `backend/app/analysis/models.py`, `backend/app/db/schema.py`, `backend/app/db/repository.py`
- **Deps**: `pyproject.toml` (add `playwright`), `Dockerfile` (add chromium install step)
- **No frontend changes** in this US — enrichment_status badge is US-303 scope
- **No batch pipeline changes** — ScreenshotAgent is explicitly removed from the batch flow
