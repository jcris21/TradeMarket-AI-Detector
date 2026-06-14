## ADDED Requirements

### Requirement: analysis_runs table stores per-run metadata
The system SHALL maintain an `analysis_runs` table in SQLite with the following schema:

```sql
CREATE TABLE IF NOT EXISTS analysis_runs (
    run_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    analyzed_at TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    total_tickers INTEGER NOT NULL,
    successful_tickers INTEGER NOT NULL,
    error_count INTEGER NOT NULL
);
```

`init_db()` SHALL create this table using the existing migration pattern (idempotent DDL).

#### Scenario: Fresh database gets analysis_runs table
- **WHEN** `init_db()` runs on a database with no `analysis_runs` table
- **THEN** the table is created with all seven columns present

#### Scenario: Existing database migration is idempotent
- **WHEN** `init_db()` runs on a database that already has `analysis_runs`
- **THEN** no error is raised and existing rows are unchanged

### Requirement: run_analysis inserts a run metadata row
After `save_analysis_results()` completes, `orchestrator.run_analysis()` SHALL call `repository.save_analysis_run(row)` with a dict containing `run_id` (UUID), `user_id` (`"default"`), `analyzed_at` (ISO timestamp), `duration_seconds` (wall-clock time for the full pipeline), `total_tickers` (len of input ticker list), `successful_tickers` (len of tickers that passed validation), and `error_count` (len of error list).

#### Scenario: Successful run persists metadata
- **WHEN** `run_analysis()` completes with at least 70% successful tickers
- **THEN** one row is inserted into `analysis_runs` with correct counts and `duration_seconds > 0`

#### Scenario: Failed run (503) does not persist metadata
- **WHEN** `run_analysis()` raises HTTP 503 due to < 70% successful tickers
- **THEN** no row is inserted into `analysis_runs`

### Requirement: GET /api/analysis/latest includes run_metadata
The response from `GET /api/analysis/latest` SHALL include a `run_metadata` key. When a run exists, its value SHALL be an object with `run_id`, `analyzed_at`, `duration_seconds`, `total_tickers`, and `successful_tickers`. When no run exists, `run_metadata` SHALL be `null`.

#### Scenario: run_metadata present after first run
- **WHEN** at least one analysis run has completed
- **THEN** `GET /api/analysis/latest` response body contains `"run_metadata"` with `duration_seconds` as a positive number

#### Scenario: run_metadata is null before any run
- **WHEN** no analysis run has ever been recorded
- **THEN** `GET /api/analysis/latest` response body contains `"run_metadata": null`

#### Scenario: run_metadata reflects the most recent run
- **WHEN** multiple runs have been recorded
- **THEN** `run_metadata.analyzed_at` matches the timestamp of the most recently completed run
