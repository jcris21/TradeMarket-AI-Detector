## Context

The existing `POST /api/analysis/{ticker}/enrich` endpoint is synchronous: it calls VisionAgent in text-only mode, computes a confidence-mapped delta, and writes it in the request cycle. This works for sub-second LLM calls but cannot accommodate the 5–30 second latency of headless browser screenshot capture.

Playwright is not currently a backend dependency. The Docker image has no browser binaries. Adding Playwright introduces a ~200 MB image-size increase and a new process-level subprocess during request handling.

The `enrichments` table does not yet exist. This design introduces it as the shared async job tracker for all enrichment types (screenshot here, trader_chart in US-302/NEX-36).

## Goals / Non-Goals

**Goals:**
- Trader triggers on-demand screenshot capture of a ticker chart from a URL they specify
- Request returns 202 immediately; screenshot + VisionAgent run as a background task
- SSRF-safe URL validation
- Enrichment status polled via existing `GET /api/analysis/{ticker}` response
- `enrichments` table introduced for durable async job tracking
- `analysis_tickers.preferred_chart_url` saved on first successful enrichment

**Non-Goals:**
- Browser pooling or persistent browser sessions
- Batch screenshot for all tickers
- Auto-triggering screenshots based on score thresholds
- Websocket/SSE push for enrichment completion (polling is sufficient)
- Screenshot cropping to chart region (full viewport capture is acceptable for V1)

## Decisions

### Decision: FastAPI BackgroundTasks over Celery/Redis
`BackgroundTasks` runs in the same process after the response is sent — no queue infrastructure needed. The single-user nature of FinAlly means at most one enrichment runs at a time in practice; there is no need for a distributed worker. If concurrency becomes an issue post-launch, a task queue can be introduced without changing the API contract.

**Alternative considered**: `asyncio.create_task` — same process, but not tied to FastAPI's lifespan; risk of tasks running after shutdown. BackgroundTasks integrates cleanly with FastAPI's shutdown hooks.

### Decision: Single Playwright process per request, no pooling
Open browser → navigate → screenshot → close. This adds ~2–5s overhead but eliminates shared mutable state, zombie processes, and race conditions from concurrent enrichments. Given the on-demand, low-frequency nature of this feature, pooling complexity is not justified.

**Alternative considered**: Persistent browser instance in lifespan — eliminates startup overhead but requires locks for concurrent requests and complicates Docker health checks.

### Decision: `enrichments` table as canonical job tracker (shared with US-302)
A dedicated table is cleaner than overloading `analysis_results` with status columns. Jobs are append-only (no updates to ticker analysis rows until completion). US-302 reuses the same table with `enrichment_type = "trader_chart"`.

**Alternative considered**: In-memory dict keyed by `enrichment_id` — lost on container restart, invisible to DB queries, can't support future multi-user.

### Decision: URL validation: block-list over allow-list
An allow-list of chart providers would break trader freedom (R3 explicitly says trader-supplied, not hardcoded). A block-list of private IP ranges + localhost prevents SSRF while allowing any HTTPS public URL. Block-list is validated before redirect follow; Playwright's `goto()` does not follow to blocked hosts.

**Alternative considered**: DNS resolution check before launch — adds latency and is bypassable via DNS rebinding. Block-list at the URL string level is simpler and sufficient.

### Decision: VisionAgent `screenshot_bytes` parameter (not temp file)
Passing bytes in-process avoids disk I/O, temp file cleanup, and naming collisions. The existing disk-path path (`screenshots/{ticker}.png`) is retained as a fallback; the parameter priority is `screenshot_bytes > disk_path > text-only`.

## Risks / Trade-offs

- [Risk] Sites block headless Chromium (Cloudflare, Akamai) → Mitigation: enrichment fails with `status: "failed"` and clear error message; trader can try another URL. Not fixable without browser fingerprint spoofing (out of scope).
- [Risk] Playwright adds ~200 MB to Docker image → Mitigation: use `--with-deps` minimal install (Chromium only, not Firefox/WebKit). Acceptable for a trading workstation image.
- [Risk] Long-running background task delays Python event loop → Mitigation: Playwright's async API is used throughout; `async_playwright()` does not block the event loop. The subprocess runs in a separate OS process.
- [Risk] Concurrent enrichments → Both complete independently since each opens its own browser. `enrichments` table rows are independent. Last-write-wins on `analysis_results.enrichment_delta` is acceptable for single-user.

## Migration Plan

1. `schema.py` — add `enrichments` table DDL + two idempotent `ALTER TABLE` statements (startup-safe)
2. `pyproject.toml` — add `playwright` dependency; run `uv lock`
3. `Dockerfile` — add `playwright install chromium --with-deps` layer after `uv sync`
4. Backend code changes (no data migration — new table, new columns with defaults)
5. Rebuild Docker image; volume-mounted `db/finally.db` preserves existing data

Rollback: revert Dockerfile and code; `enrichments` table and new columns are additive (no breaking changes to existing rows).

## Open Questions

- Should `GET /api/analysis/enrich/{enrichment_id}` be a dedicated status endpoint, or is polling via `GET /api/analysis/{ticker}` sufficient? Current design uses the latter (simpler); add dedicated endpoint only if frontend polling proves awkward.
- Should `preferred_chart_url` be editable via a separate PATCH endpoint, or only set on successful enrichment? Currently set on success only.
