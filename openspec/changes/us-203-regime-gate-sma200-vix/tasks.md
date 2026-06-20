## 1. Model Changes

- [x] 1.1 Add `sma_200: float | None = None` to `TechnicalIndicators` in `backend/app/analysis/models.py` (after `sma_50`)
- [x] 1.2 Add `rank_exclusion_reason: str | None = None` to `AssetAnalysis`; include it in `to_db_row()`
- [x] 1.3 Add `regime_gate_active: bool = False` and `vix_value: float | None = None` to `AnalysisResult`

## 2. DB Migration

- [x] 2.1 Add `rank_exclusion_reason TEXT` (nullable) column to `CREATE TABLE analysis_results` DDL in `backend/db/schema.py` (or equivalent schema file)
- [x] 2.2 Add idempotent migration guard: `ALTER TABLE analysis_results ADD COLUMN rank_exclusion_reason TEXT` wrapped in `try/except` to silence duplicate-column errors on existing DBs

## 3. DataAgent — SMA-200 and Period Fix

- [x] 3.1 In `backend/app/analysis/data_agent.py` `_compute_indicators()`, add SMA-200 computation using `ta.sma(close, length=200)` with same exception-safe pattern as `sma_50`; add `sma_200=sma_200` to `TechnicalIndicators(...)` constructor
- [x] 3.2 Change `period="3mo"` to `period="1y"` in `fetch_indicators_batch()` download call
- [x] 3.3 Change `period="3mo"` to `period="1y"` in `fetch_indicators()` (single-ticker path)

## 4. Orchestrator — SMA-200 Regime Gate

- [x] 4.1 After Stage 1 in `backend/app/analysis/orchestrator.py`, partition `successful` dict: tickers with `current_price <= sma_200` → `regime_excluded`; `sma_200 is None` → `regime_passed` (fail-open)
- [x] 4.2 Build synthetic `AssetAnalysis` objects for `regime_excluded` tickers with `signal="AVOID"`, `rank=None`, `rank_exclusion_reason="regime_bearish"`; log at DEBUG per ticker
- [x] 4.3 Set `successful = regime_passed` so only passed tickers continue to Stages 2–4
- [x] 4.4 Collect `regime_excluded_analyses` list for inclusion in final `AnalysisResult.assets`

## 5. Orchestrator — VIX Gate

- [x] 5.1 Add `_fetch_vix() -> float | None` async helper in `orchestrator.py`: download `^VIX` via `asyncio.to_thread(yf.download, ...)`, return last Close, return `None` on any exception/empty result with WARNING log
- [x] 5.2 Add `ANALYSIS_VIX_THRESHOLD = float(os.environ.get("ANALYSIS_VIX_THRESHOLD", "25.0"))` at module level
- [x] 5.3 Gather VIX fetch concurrently with Stage 1: `(batch_results, vix_value) = await asyncio.gather(fetch_indicators_batch(tickers), _fetch_vix())`
- [x] 5.4 Compute `vix_gate_active` after gather; log `vix_gate_checked` structured event (fields: `vix_value`, `threshold`, `gate_active`)
- [x] 5.5 After Stage 4, if `vix_gate_active`, apply `_apply_vix_gate()` to both `ranked` and `stale_analyses`; clear `top_5 = []`
- [x] 5.6 Add `_apply_vix_gate(asset) -> AssetAnalysis`: convert `signal="BUY"` → `"AVOID"`, `rank=None`, `rank_exclusion_reason="regime_vix"`; return non-BUY assets unchanged
- [x] 5.7 Populate `AnalysisResult(regime_gate_active=vix_gate_active, vix_value=vix_value, ...)`

## 6. API Route

- [x] 6.1 In `backend/app/routes/analysis.py`, add `"regime_gate_active": result.regime_gate_active` and `"vix_value": result.vix_value` to the `/api/analysis/run` response dict

## 7. Frontend

- [x] 7.1 In the analysis panel component, read `regime_gate_active` and `vix_value` from the run response
- [x] 7.2 Render a persistent yellow warning banner above the results panel when `regime_gate_active === true`, displaying the VIX value
- [x] 7.3 Clear the banner when the next run response has `regime_gate_active === false`

## 8. Tests

- [x] 8.1 Write `test_sma200_computed` in `test_data_agent.py` — 250-day mock DataFrame → `sma_200` is float
- [x] 8.2 Write `test_sma200_none_insufficient_bars` in `test_data_agent.py` — 150-day mock → `sma_200 is None`
- [x] 8.3 Update existing `test_data_agent.py` mocks asserting `period="3mo"` → `period="1y"`
- [x] 8.4 Write `test_regime_sma200_below_suppresses_buy` — `current_price < sma_200` → `signal="AVOID"`, `rank_exclusion_reason="regime_bearish"`, not in `top_5`, not persisted
- [x] 8.5 Write `test_regime_sma200_above_passes_through` — `current_price > sma_200` → proceeds to Stage 2+
- [x] 8.6 Write `test_sma200_none_passes_through` — `sma_200=None` → fail open, ticker not excluded
- [x] 8.7 Write `test_vix_gate_active_suppresses_buys` — VIX=27.0, threshold=25.0 → all BUY → AVOID with `rank_exclusion_reason="regime_vix"`, `top_5=[]`
- [x] 8.8 Write `test_vix_gate_inactive_below_threshold` — VIX=20.0, threshold=25.0 → BUY signals preserved
- [x] 8.9 Write `test_vix_fetch_failure_fail_open` — VIX fetch raises → `regime_gate_active=False`, BUY preserved, WARNING logged
- [x] 8.10 Write `test_vix_gate_disabled_at_999` — `ANALYSIS_VIX_THRESHOLD=999` → `regime_gate_active=False`
- [x] 8.11 Write `test_stale_buy_suppressed_by_vix_gate` — stale fallback `signal="BUY"` → AVOID when gate active

## 9. Verification

- [x] 9.1 Run full test suite; confirm 0 regressions
- [x] 9.2 Verify `rank_exclusion_reason` is written to `analysis_results` DB row for regime-excluded assets
- [x] 9.3 Verify idempotent migration runs cleanly on both fresh and existing DBs
- [x] 9.4 Verify `/api/analysis/run` response includes `regime_gate_active` and `vix_value`
- [x] 9.5 Add `ANALYSIS_VIX_THRESHOLD` to `.env.example` with default 25.0 and disable note (set to 999)
