## ADDED Requirements

### Requirement: Detect rate-limit errors explicitly
The system SHALL catch `yfinance.exceptions.YFRateLimitError` before the generic `except Exception` handler in `fetch_indicators_batch` and raise `DataFetchError(ticker, reason="rate_limited")`. `DataFetchError.__init__` SHALL accept an optional `reason: str = "empty_dataframe"` kwarg stored as `self.reason`; all existing callers with no `reason` argument SHALL continue to work unchanged.

#### Scenario: YFRateLimitError is raised by yf.download
- **WHEN** `yf.download()` raises `yfinance.exceptions.YFRateLimitError` after all retries are exhausted
- **THEN** `fetch_indicators_batch` raises `DataFetchError` with `reason="rate_limited"` for that ticker

#### Scenario: DataFetchError default reason is preserved
- **WHEN** `DataFetchError(ticker)` is constructed without a `reason` argument
- **THEN** `exc.reason` equals `"empty_dataframe"`

#### Scenario: Other exceptions are not affected
- **WHEN** `yf.download()` raises a non-429 exception (e.g., `ValueError`)
- **THEN** the exception propagates to the generic handler without being wrapped as `"rate_limited"`

### Requirement: Exponential backoff with maximum two retries
The system SHALL extract a helper `_download_with_retry(tickers, **kwargs)` in `data_agent.py` that wraps `yf.download()` with a 3-attempt retry loop. On each `YFRateLimitError`, it SHALL wait `2^attempt` seconds before the next attempt (attempt 0: no wait, attempt 1: 2 s, attempt 2: 4 s). After 3 consecutive `YFRateLimitError` exceptions it SHALL re-raise the last `YFRateLimitError`. Non-429 exceptions SHALL NOT be retried and SHALL propagate immediately.

#### Scenario: First attempt succeeds
- **WHEN** `yf.download()` succeeds on attempt 0
- **THEN** `_download_with_retry` returns the DataFrame with no sleep and no retry

#### Scenario: Rate limit on first attempt, success on second
- **WHEN** `yf.download()` raises `YFRateLimitError` on attempt 0 then returns a valid DataFrame on attempt 1
- **THEN** `_download_with_retry` sleeps 2 s, retries once, and returns the DataFrame

#### Scenario: All three attempts fail with rate-limit error
- **WHEN** `yf.download()` raises `YFRateLimitError` on all three attempts
- **THEN** `_download_with_retry` calls `yf.download()` exactly 3 times, sleeps a total of 6 s, and re-raises `YFRateLimitError`

#### Scenario: Non-rate-limit exception is not retried
- **WHEN** `yf.download()` raises `ValueError` on attempt 0
- **THEN** `_download_with_retry` propagates the `ValueError` immediately without sleeping or retrying

### Requirement: Structured WARNING log on each retry
The system SHALL log a WARNING event for each retry attempt with structured fields `{"event": "yf_rate_limit_retry", "attempt": n, "wait_s": w, "tickers_count": k}` using the existing JSON logging format.

#### Scenario: Retry event is logged
- **WHEN** `_download_with_retry` catches a `YFRateLimitError` and waits before a retry
- **THEN** a WARNING log entry is emitted with `event="yf_rate_limit_retry"`, the attempt number, wait duration, and ticker count

### Requirement: Differentiated reason in errors list and stage logs
The system SHALL inspect `exc.reason` in the orchestrator Stage-1 loop when a `DataFetchError` is caught. Tickers with `reason="rate_limited"` SHALL produce `{"ticker": t, "error_message": ..., "reason": "rate_limited"}` in the `errors` list; tickers with `reason="empty_dataframe"` SHALL produce `{"ticker": t, "error_message": ..., "reason": "empty_dataframe"}`. The `stage_complete` log event SHALL include a `rate_limited_count` field.

#### Scenario: Rate-limited ticker recorded with correct reason
- **WHEN** `fetch_indicators_batch` returns `DataFetchError` with `reason="rate_limited"` for a ticker
- **THEN** `AnalysisResult.errors` contains an entry for that ticker with `"reason": "rate_limited"`

#### Scenario: Empty-dataframe ticker recorded with correct reason
- **WHEN** `fetch_indicators_batch` returns `DataFetchError` with `reason="empty_dataframe"` for a ticker
- **THEN** `AnalysisResult.errors` contains an entry for that ticker with `"reason": "empty_dataframe"`

#### Scenario: Stage log includes rate_limited_count
- **WHEN** Stage 1 completes with at least one rate-limited ticker
- **THEN** the `stage_complete` structured log includes `rate_limited_count` equal to the number of rate-limited tickers
