## ADDED Requirements

### Requirement: Per-ticker DB write isolation in save_analysis_results
Each INSERT in `save_analysis_results()` SHALL be wrapped in its own try/except and committed immediately, so a failure on one ticker does not prevent others from being persisted.

#### Scenario: Single ticker INSERT fails
- **WHEN** `aiosqlite.Error` is raised for one ticker's INSERT during `save_analysis_results()`
- **THEN** that ticker is NOT persisted to DB
- **THEN** all other tickers in the batch ARE persisted successfully
- **THEN** the failed ticker is returned in the write_errors list with its error message
- **THEN** `save_analysis_results()` does NOT raise

#### Scenario: All ticker INSERTs succeed
- **WHEN** all INSERTs complete without error
- **THEN** `save_analysis_results()` returns an empty list
- **THEN** all rows are committed to `analysis_results`

### Requirement: Write errors surface in AnalysisResult.errors
The `OrchestratorAgent` SHALL merge DB write errors into `AnalysisResult.errors[]` so the frontend and caller can distinguish analysis failures from persistence failures.

#### Scenario: One ticker write fails during orchestration
- **WHEN** `save_analysis_results()` returns a non-empty write_errors list
- **THEN** `AnalysisResult.errors` contains entries for each failed ticker
- **THEN** `AnalysisResult.assets` contains the ranked results for successfully written tickers

#### Scenario: All tickers fail to write
- **WHEN** every INSERT fails
- **THEN** `AnalysisResult.assets = []`, `top_5 = []`, `errors` is non-empty
- **THEN** the API returns HTTP 200 with the partial result (not HTTP 500)

### Requirement: Analysis API returns HTTP 200 on partial persistence failure
The `POST /api/analysis/run` endpoint SHALL return HTTP 200 with a populated `errors[]` array when DB writes fail — it SHALL NOT return HTTP 500 unless the pipeline itself raises an unhandled exception.
