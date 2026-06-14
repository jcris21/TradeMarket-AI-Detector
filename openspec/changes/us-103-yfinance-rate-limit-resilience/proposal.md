## Why

The analysis pipeline wraps `yf.download()` in a bare `except Exception`, so HTTP 429 rate-limit errors from Yahoo Finance are silently swallowed, produce no retry, and are indistinguishable in telemetry from missing-data failures — corrupting signal quality for traders without any visible warning. With a 100-ticker universe, transient rate-limiting is expected and must be handled explicitly.

## What Changes

- `DataFetchError.__init__` gains an optional `reason: str = "empty_dataframe"` kwarg stored as `self.reason` — all existing callers remain unchanged.
- A new `_download_with_retry()` helper in `data_agent.py` wraps `yf.download()` with 3-attempt exponential backoff (0s, 2s, 4s) on `YFRateLimitError`; non-429 errors propagate immediately.
- `fetch_indicators_batch` catches `YFRateLimitError` explicitly before the generic handler and raises `DataFetchError(..., reason="rate_limited")`.
- `orchestrator.py` Stage-1 loop inspects `exc.reason` to populate differentiated `reason` fields in the `errors` list and logs `rate_limited_count` alongside `tickers_error`.
- `AssetAnalysis` gains `is_stale: bool = False` (runtime flag, not persisted).
- `AnalysisResult` gains `stale_tickers: list[str] = []`.
- Orchestrator staleness fallback: rate-limited tickers whose DB cache (`analysis_results`) is < 24 h old are served as `is_stale=True` assets and flow through stages 2–4 normally.
- Frontend analysis card renders an accent-yellow `"Stale data"` badge when `is_stale=True`.

## Capabilities

### New Capabilities

- `yf-rate-limit-resilience`: Explicit detection of `YFRateLimitError`, exponential-backoff retry (max 2 retries), and differentiated `reason` telemetry (`"rate_limited"` vs `"empty_dataframe"`) in the Stage-1 error list and structured logs.
- `stale-data-fallback`: When all retries are exhausted for a rate-limited ticker, the orchestrator falls back to the most-recent `analysis_results` DB row (if < 24 h old), marks it `is_stale=True`, and surfaces a warning badge in the UI.

### Modified Capabilities

<!-- No existing spec-level requirements are changing — this is additive resilience layered on top of existing analysis flow. -->

## Impact

- **Backend files**: `backend/app/analysis/models.py`, `backend/app/analysis/data_agent.py`, `backend/app/analysis/orchestrator.py`
- **Backend tests**: `backend/tests/test_data_agent.py` (6 new unit tests)
- **Frontend**: analysis card component — `is_stale` badge (accent-yellow `#ecad0a`)
- **No new Python dependencies** — uses `yfinance.exceptions.YFRateLimitError` (yfinance ≥ 0.2.x) and `asyncio.sleep`
- **No schema migration** — `is_stale` is a runtime-only field; no DB column added
