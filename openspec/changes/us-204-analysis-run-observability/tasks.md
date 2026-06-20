## 1. Run Registry

- [x] 1.1 Create `backend/app/analysis/run_registry.py` with `RunStage` Literal type and `RunState` dataclass (fields: `run_id`, `stage`, `tickers_total`, `tickers_completed`, `errors_so_far`, `started_at`, `completed_at`)
- [x] 1.2 Add `_registry: dict[str, RunState]` singleton and `_lock: asyncio.Lock` in `run_registry.py`
- [x] 1.3 Add `get_active_run() -> RunState | None` helper: returns first run where stage not in `{complete, failed}`
- [x] 1.4 Add `evict_expired_runs()` helper: remove runs where `completed_at` is set and > 10 minutes ago

## 2. Backend Route Changes

- [x] 2.1 In `backend/app/routers/analysis.py`, change `POST /api/analysis/run` to return HTTP 202 with `{run_id, tickers_total, started_at}`; dispatch background task via `BackgroundTasks`
- [x] 2.2 Add 409 Conflict guard: if `get_active_run()` returns a non-None run, return `{"error": "run_already_in_progress", "run_id": existing_id}` with status 409
- [x] 2.3 Add `GET /api/analysis/run/{run_id}/status` endpoint: look up registry, return 404 if not found, else return full `RunState` JSON including `estimated_remaining_seconds`
- [x] 2.4 Implement `estimated_remaining_seconds` formula: `(elapsed / completed) * (total - completed)`; return `null` when `tickers_completed == 0`
- [x] 2.5 Update `GET /api/analysis/latest` to accept `?partial=true` query param; when true, return top-20 scored tickers from active run (from in-memory state), sorted by score descending; return `{results: [], partial: true}` when no active run or no scored tickers

## 3. Background Task / Runner

- [x] 3.1 Modify `backend/app/analysis/runner.py` (or equivalent) to accept a `RunState` reference and update `stage`, `tickers_completed`, `errors_so_far` at each step
- [x] 3.2 Update `stage="data"` per ticker, increment `tickers_completed` after each ticker's data fetch
- [x] 3.3 Transition `stage="scoring"` when data phase completes; reset `tickers_completed=0` for the scoring phase (or keep cumulative — document choice)
- [x] 3.4 Set `stage="complete"` and `completed_at=datetime.utcnow()` when run finishes
- [x] 3.5 Wrap entire background task body in `try/except Exception`: on unhandled error set `stage="failed"`, append error to `errors_so_far`, set `completed_at`

## 4. Main App Wiring

- [x] 4.1 Import and register updated analysis router in `backend/app/main.py`
- [x] 4.2 Add startup hook or middleware to call `evict_expired_runs()` periodically (or call it lazily on each status request)

## 5. TypeScript Types

- [x] 5.1 Add `RunStage` type (`"data" | "scoring" | "complete" | "failed"`) to `frontend/src/types/analysis.ts`
- [x] 5.2 Add `RunStatus` interface to `frontend/src/types/analysis.ts` matching `GET /run/{run_id}/status` response shape

## 6. Frontend API Helpers

- [x] 6.1 Add `startAnalysisRun(tickers: string[]): Promise<{run_id: string, tickers_total: number, started_at: string}>` to `frontend/src/lib/api.ts`
- [x] 6.2 Add `getRunStatus(runId: string): Promise<RunStatus>` to `frontend/src/lib/api.ts`
- [x] 6.3 Add `getLatestPartial(): Promise<{results: AssetAnalysis[], partial: boolean}>` to `frontend/src/lib/api.ts`

## 7. Frontend AnalysisPanel Component

- [x] 7.1 Update "Run Analysis" button handler to call `startAnalysisRun()`, store `run_id` in component state
- [x] 7.2 Start polling `getRunStatus(runId)` every 3 s using `setInterval` (or `useEffect` + `setTimeout` chain) on successful run start
- [x] 7.3 Stop polling when `stage === "complete"` or `stage === "failed"`
- [x] 7.4 Render stage badge (DATA or SCORING) as styled pill during active run
- [x] 7.5 Render progress bar with fill `(tickers_completed / tickers_total * 100)%`
- [x] 7.6 Render ETA label `~{estimated_remaining_seconds}s remaining` (hidden when null)
- [x] 7.7 Render error count badge when `errors_so_far.length > 0`; tooltip shows error list
- [x] 7.8 Show "Preview Top 20" button when `tickers_completed >= 20`; clicking calls `getLatestPartial()` and renders preview
- [x] 7.9 On `stage === "complete"`: fetch full results from `GET /api/analysis/latest` and render normally
- [x] 7.10 On `stage === "failed"`: display inline error banner with `errors_so_far`

## 8. Tests

- [x] 8.1 Unit: `RunState` ETA formula — normal case (`completed=42, total=100, elapsed=12s`) and zero-completed edge case (`null`)
- [x] 8.2 Unit: 409 Conflict when `get_active_run()` returns an active run
- [x] 8.3 Unit: partial results returns only scored tickers sorted by score descending
- [x] 8.4 Integration: full lifecycle `POST /run` → poll `GET /status` → `stage=complete` → `GET /latest`
- [x] 8.5 Integration: `GET /status` returns 404 for unknown `run_id`
- [x] 8.6 Frontend: progress bar renders correct fill % given mocked status response
- [x] 8.7 Frontend: polling stops when `stage === "complete"` or `"failed"`
- [x] 8.8 Update any existing tests that called `POST /api/analysis/run` expecting a sync result

## 9. Verification

- [x] 9.1 Run full test suite; confirm 0 regressions in existing analysis tests
- [x] 9.2 Verify `POST /api/analysis/run` returns HTTP 202 (not 200) with `run_id`
- [x] 9.3 Verify status endpoint responds in < 10 ms under load
- [x] 9.4 Verify 409 is returned when run already active
- [x] 9.5 Verify completed runs are evicted from registry after 10 minutes
