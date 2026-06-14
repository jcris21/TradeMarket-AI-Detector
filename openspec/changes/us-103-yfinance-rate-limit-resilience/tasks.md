## 1. Model Extensions

- [ ] 1.1 Add `reason: str = "empty_dataframe"` kwarg to `DataFetchError.__init__` in `models.py`; store as `self.reason`
- [ ] 1.2 Add `is_stale: bool = False` field to `AssetAnalysis` in `models.py`; exclude from `to_db_row()`
- [ ] 1.3 Add `stale_tickers: list[str] = []` field to `AnalysisResult` in `models.py`

## 2. Download Retry Helper

- [ ] 2.1 Add `from yfinance.exceptions import YFRateLimitError` import at top of `data_agent.py`
- [ ] 2.2 Implement `_download_with_retry(tickers, **kwargs) -> pd.DataFrame` in `data_agent.py` with 3-attempt loop (`time.sleep(2**attempt)` for attempts 1 and 2)
- [ ] 2.3 Add `import time` to `data_agent.py` (for `time.sleep` inside the thread worker)
- [ ] 2.4 Emit WARNING structured log `{"event": "yf_rate_limit_retry", "attempt": n, "wait_s": w, "tickers_count": k}` on each retry inside `_download_with_retry`

## 3. fetch_indicators_batch Update

- [ ] 3.1 Replace bare `yf.download()` call in `fetch_indicators_batch` with `_download_with_retry()`
- [ ] 3.2 Add explicit `except YFRateLimitError` block before `except Exception` that raises `DataFetchError(ticker, reason="rate_limited")`

## 4. Orchestrator — Differentiated Telemetry

- [ ] 4.1 In `orchestrator.py` Stage-1 loop, inspect `exc.reason` when catching `DataFetchError`; set `"reason"` field in the appended `errors` entry accordingly
- [ ] 4.2 Accumulate a `rate_limited_count` counter in Stage 1; include it in the `stage_complete` structured log event

## 5. Orchestrator — Staleness Fallback

- [ ] 5.1 Define `STALE_THRESHOLD_HOURS = 24` constant in `orchestrator.py`
- [ ] 5.2 After the Stage-1 batch result loop, iterate tickers with `reason="rate_limited"`; call `await get_analysis_by_ticker(ticker)` for each
- [ ] 5.3 If a DB row is returned and `analyzed_at` is within 24 h, reconstruct `AssetAnalysis` with `is_stale=True`, add ticker to `successful`, and append to a local `stale_tickers` set
- [ ] 5.4 Pass `stale_tickers=list(stale_tickers)` to the final `AnalysisResult` constructor

## 6. Unit Tests

- [ ] 6.1 Create (or update) `backend/tests/test_data_agent.py`
- [ ] 6.2 Write `test_rate_limit_retry_succeeds_on_second_attempt` — mock `yf.download` to raise `YFRateLimitError` once then return a valid DataFrame; assert one retry and one WARNING log
- [ ] 6.3 Write `test_rate_limit_all_retries_exhausted` — mock `yf.download` to always raise `YFRateLimitError`; assert exactly 3 calls, total sleep 6 s, and re-raised exception
- [ ] 6.4 Write `test_data_fetch_error_reason_field` — assert default reason is `"empty_dataframe"` and explicit `reason="rate_limited"` is stored correctly
- [ ] 6.5 Write `test_orchestrator_errors_include_reason` — mock batch returning `DataFetchError(..., reason="rate_limited")`; assert `errors[0]["reason"] == "rate_limited"`
- [ ] 6.6 Write `test_staleness_fallback_uses_cached_result` — mock rate-limit failure and `get_analysis_by_ticker` returning a 2 h-old row; assert ticker in `stale_tickers` and `is_stale=True`
- [ ] 6.7 Write `test_staleness_fallback_ignores_expired_cache` — same setup with `analyzed_at` 25 h ago; assert ticker remains in `errors`

## 7. Frontend Stale Badge

- [ ] 7.1 Add `is_stale?: boolean` to the analysis signal TypeScript type/interface
- [ ] 7.2 In the analysis card component, render a `"Stale data"` badge with `color: #ecad0a` when `is_stale === true`
- [ ] 7.3 Verify badge does not render when `is_stale` is `false` or absent

## 8. Verification

- [ ] 8.1 Run `uv run --extra dev pytest backend/tests/test_data_agent.py -v` — all 6 new tests pass
- [ ] 8.2 Run `uv run --extra dev pytest -v` — no regressions in existing tests
