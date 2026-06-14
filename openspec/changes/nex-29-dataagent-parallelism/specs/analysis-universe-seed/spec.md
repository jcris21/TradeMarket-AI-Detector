## ADDED Requirements

### Requirement: Chunked sequential batch download
`fetch_indicators_batch()` SHALL split the ticker list into sequential chunks of size `int(os.environ.get("ANALYSIS_DATA_CHUNK_SIZE", "20"))`. Each chunk is downloaded with one `yf.download(chunk, ...)` call. After each chunk (except the last), the function SHALL `await asyncio.sleep(float(os.environ.get("ANALYSIS_DATA_CHUNK_DELAY_S", "0.5")))`. All chunks execute sequentially (no concurrent downloads). Env vars SHALL be read at call-site so tests can override without module reload.

#### Scenario: 100 tickers split into 5 chunks of 20
- **WHEN** `fetch_indicators_batch()` is called with 100 tickers and `ANALYSIS_DATA_CHUNK_SIZE=20`
- **THEN** `yf.download` is called exactly 5 times during the chunk pass (excluding retries)

#### Scenario: Configurable chunk size via env var
- **WHEN** `ANALYSIS_DATA_CHUNK_SIZE` is set to `"10"` before calling `fetch_indicators_batch()`
- **THEN** `yf.download` is called 10 times for 100 tickers during the chunk pass

#### Scenario: Inter-chunk sleep is applied between chunks
- **WHEN** `fetch_indicators_batch()` runs with 2 or more chunks
- **THEN** `asyncio.sleep` is called `(chunk_count - 1)` times with the configured delay value

### Requirement: Per-ticker retry for empty batch results
After the chunked loop, `fetch_indicators_batch()` SHALL collect all tickers for which `_extract_ticker_df()` returned an empty DataFrame. For each such ticker, it SHALL issue exactly one individual `yf.download(ticker, ...)` retry call. If the retry also returns empty or raises an exception, the ticker SHALL be recorded in `errors` as a `DataFetchError`. Maximum 1 retry per ticker.

#### Scenario: Ticker failing in batch succeeds on retry
- **WHEN** `yf.download(chunk)` returns an empty DataFrame for ticker X but `yf.download(X)` returns valid data
- **THEN** ticker X is included in successful results, not in `errors`

#### Scenario: Ticker failing in both batch and retry goes to errors
- **WHEN** both the batch pass and the individual retry for ticker X return empty DataFrames
- **THEN** ticker X appears in `errors` with `error_message` and `duration_ms` fields

#### Scenario: Retry is not applied to tickers with valid batch data
- **WHEN** ticker Y returns a non-empty DataFrame in the batch pass
- **THEN** no individual retry call is made for ticker Y

### Requirement: Raised data validation threshold in _compute_indicators
`_compute_indicators` SHALL raise `DataFetchError(ticker)` when `len(df) < 60` (raised from the previous threshold of 30 bars) or when `current_price <= 0`. Both checks SHALL be evaluated before any indicator computation.

#### Scenario: DataFrame with fewer than 60 rows raises DataFetchError
- **WHEN** `_compute_indicators` receives a DataFrame with 59 rows
- **THEN** `DataFetchError` is raised for that ticker

#### Scenario: DataFrame with exactly 60 rows passes validation
- **WHEN** `_compute_indicators` receives a DataFrame with 60 rows and a positive current_price
- **THEN** no validation error is raised

#### Scenario: Zero or negative current_price raises DataFetchError
- **WHEN** `_compute_indicators` is called with `current_price = 0`
- **THEN** `DataFetchError` is raised for that ticker

### Requirement: Minimum viable run threshold (70%)
`orchestrator.run_analysis()` SHALL raise `HTTPException(status_code=503, detail=f"Insufficient data: {len(successful)}/{len(tickers)} tickers returned valid data")` when `len(successful) < 0.7 * len(tickers)` after Stage 1 completes.

#### Scenario: Run with >= 70% success proceeds normally
- **WHEN** 70 of 100 tickers return valid data
- **THEN** `run_analysis()` completes normally and returns results

#### Scenario: Run with < 70% success raises 503
- **WHEN** only 69 of 100 tickers return valid data
- **THEN** `POST /api/analysis/run` returns HTTP 503 with a detail message stating the count

### Requirement: Per-ticker duration_ms in error entries
`fetch_indicators_batch()` SHALL record wall-clock elapsed time for `_compute_indicators` per ticker. Error dict entries SHALL include `duration_ms` (integer, milliseconds). Successful tickers do not require timing to be surfaced.

#### Scenario: Error dict includes duration_ms
- **WHEN** `_compute_indicators` raises `DataFetchError` for a ticker
- **THEN** the error entry in the `errors` list contains a `"duration_ms"` key with a non-negative integer value

#### Scenario: duration_ms is present even on immediate validation failure
- **WHEN** validation fails immediately (e.g., `len(df) < 60`)
- **THEN** `duration_ms` still appears in the error entry (may be 0 ms)
