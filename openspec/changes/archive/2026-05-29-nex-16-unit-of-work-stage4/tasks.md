## Implementation Tasks — NEX-16 / TECH-001

## 1. Tests (TDD — write first)

- [x] 1.1 Add `test_save_analysis_results_partial_failure` to `backend/tests/` — mock one INSERT raising `aiosqlite.OperationalError`, verify other rows committed and error returned in list
- [x] 1.2 Add `test_save_analysis_results_all_fail` — all INSERTs raise, verify empty result set returned without exception
- [x] 1.3 Add `test_orchestrator_surfaces_write_errors` — mock `save_analysis_results` returning write errors, verify they appear in `AnalysisResult.errors`

## 2. Repository — save_analysis_results

- [x] 2.1 Change return type of `save_analysis_results()` from `None` to `list[dict]` in `backend/app/db/repository.py`
- [x] 2.2 Wrap each INSERT in `try/except aiosqlite.Error` — log error, append `{"ticker": ..., "error_message": ...}` to `write_errors`
- [x] 2.3 Move `await db.commit()` inside the try block (per-row commit instead of single batch commit)
- [x] 2.4 Return `write_errors` at end of function

## 3. Orchestrator — collect write errors

- [x] 3.1 Update `await save_analysis_results(db_rows)` call in `orchestrator.py` to capture return value: `write_errors = await save_analysis_results(db_rows)`
- [x] 3.2 Extend errors list: `errors.extend(write_errors)`

## 4. Verification

- [x] 4.1 Run `uv run python -m pytest backend/tests/ -v` — all tests pass
- [x] 4.2 Confirm HTTP 200 returned when DB write fails (not HTTP 500)
