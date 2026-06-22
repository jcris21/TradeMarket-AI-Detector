## Why

The current enrichment endpoint re-runs VisionAgent in text-only mode. Traders need visual chart analysis — the ability to point the system at a live chart URL and have VisionAgent analyze the actual rendered chart image, not just price indicators. This unlocks richer pattern recognition without blocking the batch pipeline.

## What Changes

- New `ScreenshotAgent` class: single headless Chromium session via Playwright — navigate to trader-supplied URL, capture PNG screenshot, close browser
- `POST /api/analysis/enrich/{ticker}` extended to accept `{"enrichment_type": "screenshot", "source_url": str}` and return 202 immediately; screenshot + VisionAgent run as a FastAPI background task
- New `enrichments` table for async job tracking (shared with US-302): `id`, `ticker`, `enrichment_type`, `source_url`, `status`, `enrichment_delta`, `created_at`, `completed_at`
- `analysis_tickers.preferred_chart_url TEXT` — saved default URL per ticker on successful enrichment
- `analysis_results.enrichment_status TEXT` — exposes job lifecycle (`none` / `pending` / `processing` / `completed` / `failed`) on GET responses
- VisionAgent signature extended: `screenshot_bytes: bytes | None = None` — takes priority over disk-path loading
- `playwright` added to `pyproject.toml`; `playwright install chromium --with-deps` added to Dockerfile
- SSRF-safe URL validation: must be `https://`; blocked for RFC-1918, localhost, link-local ranges

## Capabilities

### New Capabilities

- `screenshot-enrichment`: On-demand async screenshot capture + VisionAgent vision analysis for a single ticker; trader supplies URL; result stored as `enrichment_delta`; status polled via GET

### Modified Capabilities

- `enrichment-delta`: Endpoint now dispatches on `enrichment_type`; screenshot type is async (202); existing synchronous raw-delta path remains for backward compatibility

## Impact

- `backend/app/analysis/screenshot_agent.py` — new file
- `backend/app/analysis/vision_agent.py` — add `screenshot_bytes` parameter
- `backend/app/routes/analysis.py` — enrich endpoint refactored
- `backend/app/db/schema.py` — new `enrichments` table + two new columns
- `backend/app/db/repository.py` — enrichment job CRUD
- `backend/app/analysis/models.py` — new request/response models
- `pyproject.toml` — playwright dependency
- `Dockerfile` — playwright chromium install
