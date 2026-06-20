## Context

`POST /api/analysis/run` currently blocks until the full run completes (30–90 s for 100 tickers), then returns the complete JSON result. FastAPI runs on a single-process Uvicorn server; the blocking call ties up the event loop for the run duration. The frontend has no progress feedback and cannot distinguish a working run from a crash.

Two pipeline stages in v3: `data` (yfinance + enrichment per ticker) and `scoring` (quantitative score computation). No screenshot/VisionAgent stages in batch mode.

## Goals / Non-Goals

**Goals:**
- Return `run_id` within milliseconds of triggering a run
- Allow polling for real-time stage + per-ticker progress + ETA
- Support partial Top-20 preview once scoring begins
- Prevent duplicate parallel runs (409 guard)
- Clean up ephemeral run state automatically (10-minute eviction)

**Non-Goals:**
- Persisting run state to SQLite (ephemeral only; run history is out of scope)
- WebSocket or SSE push for status (polling is simpler, sufficient for 3 s interval)
- Multi-user isolation (single `"default"` user; run registry is global)
- Resumable runs after server restart

## Decisions

**Decision 1 — In-memory registry, not DB**
A SQLite write per ticker-completion (up to 100 writes per run) would add I/O pressure during a CPU/network-bound phase. In-memory dict is O(1) per update, < 1 μs, no contention. Tradeoff: state lost on restart. Acceptable — runs are short-lived and the UI can simply re-trigger.

**Decision 2 — FastAPI BackgroundTasks over asyncio.create_task**
`BackgroundTasks` is idiomatic FastAPI; it integrates with the request lifecycle and is easier to test with `TestClient`. `asyncio.create_task` would require managing the event loop reference manually. Both run in the same process.

**Decision 3 — 202 Accepted, not 200**
HTTP semantics: 202 signals "accepted for processing, result not yet ready." Using 200 with a `run_id` would be technically incorrect and confusing for clients expecting the full result.

**Decision 4 — asyncio.Lock for registry mutations**
The background task runs in the same event loop as the FastAPI handler. Using `asyncio.Lock` (not `threading.Lock`) prevents concurrent mutations during `await` points inside the background task. A `threading.Lock` would deadlock if `to_thread` is used inside the task.

**Decision 5 — ETA formula: simple elapsed-based linear extrapolation**
`(elapsed / completed) * remaining` is fast, zero dependencies, and good enough for a progress bar UX. ML-based ETA is overkill. Return `null` when `completed == 0` to avoid division-by-zero.

**Decision 6 — 409 guards a single active run, not per-user**
Single-user app; a global "one active run at a time" constraint is simpler and prevents accidental double-triggers from the UI. The client stores `run_id` in component state and polls it.

**Decision 7 — Partial results from in-memory state, not DB**
`GET /api/analysis/latest?partial=true` reads the in-progress scored tickers from the registry (not from DB) to return results before the run completes and persists. This is consistent with the ephemeral-state design.

## Risks / Trade-offs

[Risk: Background task exception leaves run in non-terminal stage forever] → Mitigation: wrap entire task body in `try/except Exception`; set `stage="failed"` and `completed_at` in `finally` block.

[Risk: 10-minute eviction fires while client is still polling] → Mitigation: client receives 404, interprets as "run expired, re-trigger if needed." Document this in the API spec.

[Risk: Frontend polling at 3 s interval floods the status endpoint] → Mitigation: status endpoint is pure in-memory read (< 10 ms). At 3 s interval with one client, throughput is 0.3 RPS — negligible.

[Risk: Breaking change to `POST /api/analysis/run` — existing callers expect sync result] → Mitigation: document as BREAKING in proposal. Any internal caller (e.g., tests hitting the endpoint directly) must be updated to poll for `complete` before reading results.

## Migration Plan

1. Create `backend/app/analysis/run_registry.py` with `RunState`, `_registry`, `asyncio.Lock`
2. Modify `backend/app/analysis/runner.py` — convert sync run to async, accept `RunState` ref, update registry at each step
3. Modify `backend/app/routers/analysis.py` — `POST /run` (202), `GET /run/{run_id}/status`, update `GET /latest` to support `?partial=true`
4. Modify `backend/app/main.py` — include updated router
5. Modify frontend `AnalysisPanel.tsx` — dispatch, poll, render progress bar + stage badge + ETA
6. Add typed helpers to `frontend/src/lib/api.ts`; add `RunStatus`, `RunStage` to `frontend/src/types/analysis.ts`
7. Write all tests; update any existing tests that called `POST /run` and expected a sync result

Rollback: revert `routers/analysis.py` to blocking endpoint. No DB changes to undo. Frontend reverts to simple "submit and wait" button.

## Open Questions

- Should the 10-minute eviction timer start from `completed_at` or `started_at`? Current design: `completed_at` (so very slow runs don't evict before the client reads). Confirm.
- Do E2E tests need a special header to bypass the 409 guard between test runs, or is the `LLM_MOCK=true` path fast enough that runs complete before the next test triggers?
