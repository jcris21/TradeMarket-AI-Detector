## Why

The core `OutcomeDetector` engine (atomic write, NaN guard, idempotency) was completed in TECH-004/NEX-19, but STORY-003 is still missing the pieces that make outcomes visible and useful: no scheduler drives the nightly run, no API endpoint exposes `PerformanceSummary` to the frontend, the hit-ratio formula silently includes EXPIRED signals in the denominator (inflating apparent losses), `support_break_level` is referenced in the DoD but absent from schema and code, and the "Orphaned" state (35+ days unresolved) has no UI representation. These gaps leave the entire outcome-recorder pipeline built but disconnected.

## What Changes

- **Fix hit-ratio denominator** — `_compute_summary` divides by `total` (includes EXPIRED); must divide by `target_hits + stop_hits` only so EXPIRED signals are truly excluded from HR and PF as the DoD specifies
- **Nightly APScheduler job** — wire `OutcomeDetector().run()` as a cron job in FastAPI `lifespan` (02:00 UTC, configurable via `OUTCOME_DETECTOR_CRON_HOUR` env var)
- **New endpoint `GET /api/analysis/performance`** — returns `PerformanceSummarySchema` with HR, PF, outcome counts, and `orphaned_count`
- **Schema migration + `support_break_level`** — `ALTER TABLE analysis_results ADD COLUMN support_break_level TEXT`; populate with `'S1'` / `'SMA20'` / `'BB_LOWER'` in the STOP_HIT path
- **Orphaned badge in `OpportunitiesPanel`** — amber `⚠ Orphaned` badge for signals where `outcome IS NULL` and `hold_days > 35`; tooltip "No outcome detected after 35 trading days — review manually"

## Capabilities

### New Capabilities

- `outcome-performance-api`: REST endpoint and Pydantic schema that exposes aggregated performance metrics (hit-ratio, profit-factor, outcome counts, orphaned count) derived from `analysis_results`
- `signal-orphaned-state`: Detection and frontend display of signals that have been unresolved for 35+ calendar days — surfaced as an amber warning badge in `OpportunitiesPanel`

### Modified Capabilities

- `outcome-detector`: Hit-ratio denominator bug fix (EXPIRED exclusion); nightly APScheduler cron integration; `support_break_level` field population in STOP_HIT path

## Impact

- **Files modified**: `backend/app/analysis/outcome_detector.py` (hit-ratio fix, support_break_level), `backend/app/main.py` (scheduler lifespan), `backend/app/db/schema.py` (support_break_level column), `frontend/components/OpportunitiesPanel.tsx` (Orphaned badge)
- **New files**: `backend/app/routers/analysis.py`, `backend/app/schemas/analysis.py`, `backend/db/migrations/003_outcome_support_break_level.sql`
- **New dependency**: `apscheduler` via `uv add apscheduler`
- **API contract**: New `GET /api/analysis/performance` added to `docs/api-spec.yml`
- **DB schema**: Additive-only migration — `support_break_level TEXT` nullable column, no data loss
