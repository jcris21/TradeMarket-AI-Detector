## Why

A batch analysis run on 100 tickers takes 30–90 seconds; without a progress signal the trader cannot distinguish a working run from a silent crash, leading to duplicate trigger attempts and confusion. Converting to async dispatch with polling gives immediate confirmation and real-time visibility into pipeline progress.

## What Changes

- `POST /api/analysis/run` becomes a **202 Accepted** endpoint that returns `run_id` immediately and dispatches the analysis as a background task
- New in-memory **run registry** (`RunState` dataclass + `_registry` dict) tracks `stage`, `tickers_completed`, `tickers_total`, `errors_so_far`, `started_at`, `completed_at`; runs evicted after 10 minutes
- New `GET /api/analysis/run/{run_id}/status` endpoint returns full `RunState` as JSON including `estimated_remaining_seconds`; responds in < 10 ms (no DB query); returns 404 for unknown `run_id`
- `GET /api/analysis/latest?partial=true` returns top-20 scored tickers from the active in-progress run
- 409 Conflict returned if a run is already active (stage ≠ `complete`/`failed`)
- Frontend polls `/status` every 3 s, renders stage badge + progress bar + ETA; stops on `complete`/`failed`; shows "Preview Top 20" once ≥ 20 tickers are scored
- **No DB persistence** for run state — ephemeral, lost on restart (scope of this story)

## Capabilities

### New Capabilities

- `analysis-run-status`: Async run dispatch with an in-memory run registry, a status polling endpoint, ETA calculation, partial-results preview, and concurrency guard (409 if run already active).

### Modified Capabilities

- `score-quant`: `POST /api/analysis/run` response shape changes from blocking JSON to `{run_id, tickers_total, started_at}` (202); **BREAKING** for any client that expected the full result synchronously.

## Impact

- **Backend files created**: `backend/app/analysis/run_registry.py`
- **Backend files modified**: `backend/app/analysis/runner.py`, `backend/app/routers/analysis.py`, `backend/app/main.py`
- **Frontend files modified**: `frontend/src/components/AnalysisPanel.tsx`, `frontend/src/lib/api.ts`, `frontend/src/types/analysis.ts`
- **API contract change** (`POST /api/analysis/run`): response becomes 202 + `run_id` — **BREAKING** for existing sync callers
- **No DB migration required** — run state is in-memory only
- Ships independently in Sprint 2 with no hard dependencies on US-202/US-203
