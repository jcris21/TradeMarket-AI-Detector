## 1. Dependency

- [x] 1.1 Add `python-json-logger>=3.0.0` to `dependencies` in `backend/pyproject.toml`
- [ ] 1.2 Run `uv lock` inside `backend/` to update the lockfile

## 2. JSON Log Formatter

- [x] 2.1 Create `backend/app/logging_config.py` with `configure_logging()` that installs `JsonFormatter` from `pythonjsonlogger.json` when `LOG_FORMAT` env var is `"json"` (or unset), and skips installation when `LOG_FORMAT=text`
- [x] 2.2 Import `configure_logging` in `backend/app/main.py` lifespan and call it as the first statement before `await init_db()`

## 3. Orchestrator Instrumentation

- [x] 3.1 Add `t_start = time.monotonic()` and `run_id = str(uuid4())` at the top of `run_analysis()` (verify `uuid4` is already imported or add it)
- [x] 3.2 Wrap Stage 1 (`fetch_indicators_batch`) with `t1 = time.monotonic()` before the call; emit `logger.info("stage_complete", extra={"stage": 1, "run_id": run_id, "duration_ms": int((time.monotonic() - t1) * 1000), "tickers_total": len(tickers), "tickers_ok": len(successful), "tickers_error": len(tickers) - len(successful)})` after the `successful` dict is built
- [x] 3.3 Add `run_complete` emission on the early-exit path (when no successful tickers after Stage 1): `logger.info("run_complete", extra={"run_id": run_id, "total_ms": int((time.monotonic() - t_start) * 1000), "signals_generated": 0, "error_count": len(tickers)})` before the early return
- [x] 3.4 Wrap Stage 2 (screenshot loading loop) with `t2 = time.monotonic()` before the loop; emit `stage_complete` with `stage=2` after the loop, with `tickers_ok` equal to the count of successfully loaded screenshots
- [x] 3.5 Wrap Stage 3 (`asyncio.gather(*vision_tasks)`) with `t3 = time.monotonic()` before the gather; emit `stage_complete` with `stage=3` after gather returns
- [x] 3.6 Wrap Stage 4 (scoring + `save_analysis_results`) with `t4 = time.monotonic()` before scoring; emit `stage_complete` with `stage=4` after `save_analysis_results` returns, with `tickers_ok=len(top_5)` and `tickers_error=len(structural_errors)`
- [x] 3.7 Replace the existing final `logger.info` call with `logger.info("run_complete", extra={"run_id": run_id, "total_ms": int(duration * 1000), "signals_generated": len(top_5), "error_count": len(errors)})`

## 4. Tests

- [x] 4.1 Add `test_stage_logs_emitted` to `backend/tests/analysis/test_orchestrator.py` using `caplog.at_level(logging.INFO, logger="app.analysis.orchestrator")`; assert exactly 4 `stage_complete` records and 1 `run_complete` record per normal run
- [x] 4.2 Assert each `stage_complete` record has `run_id`, `duration_ms` (int), `tickers_total`, `tickers_ok`, `tickers_error` attributes
- [x] 4.3 Assert the `run_complete` record has `run_id` matching the stage records, `total_ms > 0`, `signals_generated`, `error_count`
- [x] 4.4 Add `test_early_exit_run_complete` to verify that when Stage 1 returns no successful tickers, one `run_complete` record is still emitted
- [ ] 4.5 Run `pytest backend/tests/analysis/test_orchestrator.py` and confirm all tests pass (including pre-existing tests)

## 5. Verification

- [ ] 5.1 Build Docker image locally and run `docker logs <container> | jq 'select(.message == "stage_complete") | .duration_ms'` to confirm JSON output is parseable
- [ ] 5.2 Confirm `LOG_FORMAT=text` produces human-readable (non-JSON) log lines
