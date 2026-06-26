## Context

The batch pipeline currently runs DataAgent × 100 + ScoringAgent only (30–90 s). A previous architecture included ScreenshotAgent in the batch; US-201 permanently removes it from that path. Instead, ScreenshotAgent activates on explicit trader request for a single ticker via a new async enrichment endpoint. The existing `POST /api/analysis/enrich/{ticker}` endpoint handles synchronous (text-only) enrichment; this change extends it to dispatch on `enrichment_type` and handle the async `"screenshot"` path. Playwright is not currently in the backend dependency tree or Dockerfile.

## Goals / Non-Goals

**Goals:**
- Async `"screenshot"` enrichment path on `POST /api/analysis/enrich/{ticker}` — returns 202 immediately
- Single headless Chromium session per request (open → capture → close), no pooling
- SSRF-safe URL validation before any network call
- `enrichments` table as canonical async job tracker (shared with US-302)
- VisionAgent gains `screenshot_bytes` parameter so background tasks skip disk I/O
- `analysis_tickers.preferred_chart_url` saved on success
- `analysis_results.enrichment_status` column for polling support

**Non-Goals:**
- Browser pooling or connection reuse
- Batch screenshot for all tickers
- Auto-trigger based on score thresholds
- Frontend enrichment-status badge (US-303 scope)
- Redirect-following SSRF mitigation beyond host block list (acceptable for MVP)

## Decisions

**FastAPI BackgroundTasks over Celery/asyncio.create_task**
FastAPI's built-in `BackgroundTasks` runs after the response is sent, in the same process. No broker, no worker, no additional infrastructure — consistent with the single-container constraint. Risk: if the container restarts mid-enrichment the job stays `pending` forever. Acceptable for MVP; the `enrichments` table records state so stale rows are visible.

**`try/finally` browser lifecycle, no pool**
One Playwright `async_playwright()` context per request: launch → capture → close in `try/finally`. Simple, stateless, no shared mutable state across concurrent requests. Each enrichment request runs its own browser process. Concurrency is naturally limited by Playwright's process spawn cost — acceptable given on-demand (not batch) usage pattern.

**`screenshot_bytes: bytes | None` on VisionAgent instead of temp file**
Passing bytes in-memory avoids temp file management, race conditions on concurrent enrichments, and disk cleanup. Priority: `screenshot_bytes` > disk path > text-only. This is a backward-compatible extension; existing callers that pass no bytes continue to work.

**Unified dispatch in existing route, not a new route**
Extending `POST /api/analysis/enrich/{ticker}` with `enrichment_type` dispatch (None → legacy sync, `"screenshot"` → async, `"trader_chart"` → US-302 sync) keeps a single endpoint contract. Avoids duplicating ticker-not-found checks and auth patterns. Unknown `enrichment_type` → 422.

**Idempotent schema migrations via `ALTER TABLE IF NOT EXISTS` pattern**
`enrichments` table: `CREATE TABLE IF NOT EXISTS`. New columns on existing tables (`preferred_chart_url`, `enrichment_status`): wrapped in a try/except on `ALTER TABLE` at startup (SQLite has no `ADD COLUMN IF NOT EXISTS` before 3.37; catch `OperationalError` and ignore "duplicate column" errors). Keeps migrations zero-downtime and self-healing on cold start.

**Block list for SSRF, no redirect resolution**
Block list covers the standard private ranges and localhost. Not following redirects to private IPs is a known gap — acceptable for MVP since this is a trader-facing tool, not a public API. Post-MVP: validate resolved IP after DNS lookup.

## Risks / Trade-offs

**Stale `pending` jobs on container restart** → Mitigation: on startup, query `enrichments` for rows with `status IN ('pending', 'processing')` and set them to `failed` with `error_message="server restarted"`. Prevents phantom pending states after redeploy.

**Playwright binary size (~300 MB with Chromium)** → Mitigation: `playwright install chromium --with-deps` in the Dockerfile; no full browser suite. Acceptable Docker image size increase for a trading workstation container.

**Long-running background task blocks event loop on CPU-bound ops** → Mitigation: Playwright uses asyncio throughout; `page.goto` and `page.screenshot` are async. VisionAgent LLM call is already async. No `run_in_executor` needed.

**`asyncio.wait_for` + Playwright timeout interaction** → Use Playwright's native `page.goto(timeout=timeout_ms)` rather than wrapping in `asyncio.wait_for` — Playwright's timeout raises `playwright.errors.TimeoutError` which we catch and convert to `ScreenshotTimeoutError`. Avoids double-timeout complexity.

**Concurrent enrichment requests for same ticker** → Two jobs for the same ticker can run simultaneously; last write wins on `preferred_chart_url` and `enrichment_delta`. No locking needed at MVP scale.

## Migration Plan

1. `uv add playwright` → updates `pyproject.toml` and `uv.lock`
2. Add `RUN uv run playwright install chromium --with-deps` to Dockerfile after `uv sync`
3. Deploy: `enrichments` table created on startup; `ALTER TABLE` migrations add new columns idempotently
4. No data backfill required — `enrichment_status` defaults to `"none"`, `preferred_chart_url` defaults to NULL
5. Rollback: remove Playwright from `pyproject.toml`, drop the new route branch — existing sync enrichment path is untouched

## Open Questions

- Should concurrent screenshot enrichment for the same ticker be deduplicated (return existing `pending` job ID) or always create a new job? Current design: always create a new job (simpler).
- What is the polling mechanism for the frontend to discover enrichment completion? Current answer: `GET /api/analysis/{ticker}` exposes `enrichment_status` — client polls. SSE-based push is a future enhancement.
