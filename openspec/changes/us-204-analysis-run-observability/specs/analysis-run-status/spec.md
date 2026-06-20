## ADDED Requirements

### Requirement: POST /api/analysis/run returns 202 Accepted with run_id immediately
`POST /api/analysis/run` SHALL return HTTP 202 with `{run_id: string, tickers_total: int, started_at: ISO8601}` within milliseconds of being called, before the analysis completes. The analysis SHALL be dispatched as a background task. The request body SHALL accept `{tickers: string[]}` (1–100 tickers, validated).

#### Scenario: Immediate 202 response
- **WHEN** `POST /api/analysis/run` is called with a valid ticker list
- **THEN** the response is HTTP 202 with `run_id`, `tickers_total`, and `started_at` within 200 ms

#### Scenario: Invalid request body rejected
- **WHEN** `POST /api/analysis/run` is called with an empty `tickers` array
- **THEN** the response is HTTP 422 with a validation error

### Requirement: Run registry tracks live run state in memory
An in-memory registry (`_registry: dict[str, RunState]`) SHALL store active and recently completed runs. `RunState` SHALL include `run_id`, `stage` (data|scoring|complete|failed), `tickers_total`, `tickers_completed`, `errors_so_far`, `started_at`, `completed_at`. Registry mutations SHALL be protected by `asyncio.Lock`. Completed/failed runs SHALL be evicted 10 minutes after `completed_at`.

#### Scenario: Run state updated per ticker completion
- **WHEN** a ticker completes the data stage
- **THEN** `RunState.tickers_completed` increments by 1

#### Scenario: Completed run evicted after 10 minutes
- **WHEN** 10 minutes have elapsed since `completed_at`
- **THEN** the run entry is removed from the registry

### Requirement: GET /api/analysis/run/{run_id}/status returns live progress
`GET /api/analysis/run/{run_id}/status` SHALL return HTTP 200 with `{run_id, stage, tickers_completed, tickers_total, errors_so_far, started_at, estimated_remaining_seconds}`. The endpoint SHALL respond in < 10 ms (in-memory read, no DB query). `estimated_remaining_seconds` SHALL be `null` when `tickers_completed == 0`. The endpoint SHALL return HTTP 404 when `run_id` is not in the registry.

#### Scenario: Status during active run
- **WHEN** `GET /api/analysis/run/{run_id}/status` is called during an active run with 42 of 100 tickers completed
- **THEN** response has `stage` reflecting current stage, `tickers_completed=42`, `tickers_total=100`, and a numeric `estimated_remaining_seconds`

#### Scenario: ETA is null before any ticker completes
- **WHEN** `tickers_completed == 0`
- **THEN** `estimated_remaining_seconds` is `null`

#### Scenario: Unknown run_id returns 404
- **WHEN** `GET /api/analysis/run/unknown-id/status` is called
- **THEN** response is HTTP 404

### Requirement: 409 Conflict when a run is already in progress
`POST /api/analysis/run` SHALL return HTTP 409 with `{error: "run_already_in_progress", run_id: string}` if a run with stage not in `{complete, failed}` already exists in the registry.

#### Scenario: Duplicate run rejected
- **WHEN** a run is active (stage="data") and `POST /api/analysis/run` is called again
- **THEN** response is HTTP 409 with `run_already_in_progress` error and the existing `run_id`

### Requirement: GET /api/analysis/latest?partial=true returns in-progress scored results
When `partial=true` is passed to `GET /api/analysis/latest`, the endpoint SHALL return the top-20 scored tickers from the currently active run, sorted by final score descending. Tickers not yet scored (still in the `data` stage) SHALL be excluded. If no run is active or no tickers are scored, SHALL return `{results: [], partial: true}`. The existing `GET /api/analysis/latest` (without `partial`) SHALL be unchanged.

#### Scenario: Partial results during scoring stage
- **WHEN** 30 tickers have been scored and `GET /api/analysis/latest?partial=true` is called
- **THEN** up to 20 scored tickers are returned sorted by score descending with `partial: true`

#### Scenario: No active run returns empty partial
- **WHEN** no run is active and `GET /api/analysis/latest?partial=true` is called
- **THEN** response is `{results: [], partial: true}` with HTTP 200

### Requirement: Frontend polls run status and renders progress UI
The frontend analysis panel SHALL call `POST /api/analysis/run` to start a run, store `run_id`, and poll `GET /api/analysis/run/{run_id}/status` every 3 seconds. Polling SHALL stop when `stage === "complete"` or `stage === "failed"`. The UI SHALL render a stage badge (DATA or SCORING), a progress bar (`tickers_completed / tickers_total`), and an ETA label. A "Preview Top 20" button SHALL appear once `tickers_completed >= 20`.

#### Scenario: Progress bar reflects current completion
- **WHEN** `tickers_completed=42` and `tickers_total=100`
- **THEN** the progress bar fills to 42%

#### Scenario: Polling stops on complete
- **WHEN** the status response has `stage === "complete"`
- **THEN** polling stops and full results are fetched from `GET /api/analysis/latest`

#### Scenario: Error banner on failed run
- **WHEN** the status response has `stage === "failed"` with non-empty `errors_so_far`
- **THEN** an error banner is displayed listing the errors
