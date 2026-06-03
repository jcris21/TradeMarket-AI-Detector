## 1. Backend — Fix _get_hit_rate() bug

- [x] 1.1 In `backend/app/analysis/scoring_agent.py`, replace the broken `signal_outcomes` query in `_get_hit_rate()` with a query against `analysis_results` that counts `TARGET_HIT` and `STOP_HIT` rows for `user_id = 'default'`
- [x] 1.2 Return `(round(hits / conclusive, 4), "observed")` when `conclusive >= 30`, else `(0.35, "assumed")`
- [x] 1.3 Verify the fix with `uv run pytest backend/tests/` — no existing tests should regress

## 2. Backend — Extend get_performance_summary()

- [x] 2.1 In `backend/app/db/repository.py`, extend `get_performance_summary()` to compute `conclusive = target_hits + stop_hits` and set `phase_gate_active = conclusive < 30`
- [x] 2.2 Add `calibration_count = conclusive` to the returned dict
- [x] 2.3 When `phase_gate_active` is `True`, set `hit_ratio`, `profit_factor`, `realized_rr`, `hr_status`, `pf_status`, `rr_status` to `None` and `below_breakeven` to `False`
- [x] 2.4 When `phase_gate_active` is `False`, compute `realized_rr = round((total_gain / target_hits) / (total_loss / stop_hits), 2)` when `stop_hits > 0`, else `None`
- [x] 2.5 Fix zero-division: when `total_loss == 0` and `total_gain > 0`, set `profit_factor = 999.0` instead of `None`
- [x] 2.6 Compute `hr_status`: `"green"` if `hit_ratio >= 0.35`, `"red"` if `hit_ratio < 0.25`, else `"neutral"`
- [x] 2.7 Compute `pf_status`: `"green"` if `profit_factor >= 1.3`, `"red"` if `profit_factor < 1.0`, else `None`
- [x] 2.8 Compute `rr_status`: `"green"` if `realized_rr >= 2.1`, else `None`
- [x] 2.9 Compute `below_breakeven = hit_ratio < 0.25 and not phase_gate_active`

## 3. Backend — Extend PerformanceSummary dataclass

- [x] 3.1 In `backend/app/analysis/outcome_detector.py`, add the new fields to the `PerformanceSummary` dataclass: `phase_gate_active: bool`, `calibration_count: int`, `realized_rr: float | None`, `hr_status: str | None`, `pf_status: str | None`, `rr_status: str | None`, `below_breakeven: bool`

## 4. Backend — Add PerformanceResponse Pydantic model and wire to route

- [x] 4.1 In `backend/app/analysis/models.py`, add a `PerformanceResponse(BaseModel)` class with all fields typed (`float | None` for nullable metrics, `str | None` for status fields)
- [x] 4.2 In `backend/app/routes/analysis.py`, import `PerformanceResponse` and add `response_model=PerformanceResponse` to the `@router.get("/performance")` decorator
- [x] 4.3 Confirm `GET /api/analysis/performance` returns HTTP 200 with all new fields via `curl` or a quick pytest

## 5. Backend — Tests for performance panel

- [x] 5.1 Create `backend/tests/analysis/test_performance_panel.py` with an in-memory aiosqlite DB fixture
- [x] 5.2 Write `test_0_signals`: assert `phase_gate_active=True`, `calibration_count=0`, all metrics `None`
- [x] 5.3 Write `test_15_signals`: seed 10 TARGET_HIT + 5 STOP_HIT, assert `phase_gate_active=True`, `calibration_count=15`
- [x] 5.4 Write `test_30_signals`: seed 20 TARGET_HIT + 10 STOP_HIT, assert `phase_gate_active=False`, `hit_ratio` approx 0.667, `realized_rr` is not None
- [x] 5.5 Write `test_100_signals`: seed 60 TARGET_HIT + 30 STOP_HIT + 10 EXPIRED, assert EXPIRED excluded, `calibration_count=90`
- [x] 5.6 Write `test_profit_factor_sentinel`: seed TARGET_HIT only (no STOP_HIT), assert `profit_factor=999.0`
- [x] 5.7 Run `uv run pytest backend/tests/analysis/test_performance_panel.py -v` — all pass

## 6. Frontend — Types and hook

- [x] 6.1 In `frontend/lib/types.ts`, add the `PerformanceSummary` TypeScript interface with all fields matching the `PerformanceResponse` Pydantic model
- [x] 6.2 In `frontend/lib/api.ts`, add `getPerformanceSummary(): Promise<PerformanceSummary>` that calls `GET /api/analysis/performance`
- [x] 6.3 Create `frontend/lib/use-performance.ts` with `usePerformance(status: AnalysisStatus)` hook that fetches on mount and re-fetches when `status` transitions to `"done"`
- [x] 6.4 Hook returns `{ performance: PerformanceSummary | null, isLoading: boolean }`

## 7. Frontend — PerformanceSummaryPanel component

- [x] 7.1 Create `frontend/components/PerformanceSummaryPanel.tsx` accepting `{ summary: PerformanceSummary }` props
- [x] 7.2 Implement calibration state: render "Phase 0 — Calibration: {n}/30 signals" with a `<progress>` or div-based bar when `phase_gate_active === true`
- [x] 7.3 Implement metrics state: render Hit Ratio, Profit Factor, Realized R/R rows with values and color classes when `phase_gate_active === false`
- [x] 7.4 Apply color classes: `text-green-400` for `"green"` status, `text-red-400` for `"red"` status, default muted for `"neutral"` or `null`
- [x] 7.5 Render break-even warning (amber/red styling) when `below_breakeven === true`
- [x] 7.6 When `profit_factor === 999.0`, display as `∞` in the UI

## 8. Frontend — Integrate panel into OpportunitiesPanel

- [x] 8.1 In `frontend/components/OpportunitiesPanel.tsx`, import `usePerformance` and `PerformanceSummaryPanel`
- [x] 8.2 Call `usePerformance(status)` where `status` comes from `useAnalysis()`
- [x] 8.3 Render `<PerformanceSummaryPanel summary={performance} />` below the tab bar and above the signal table — always visible regardless of active tab
- [x] 8.4 Show a loading skeleton (e.g., a gray animated bar) while `isLoading === true` and `performance === null`

## 9. Frontend — Tests for PerformanceSummaryPanel

- [x] 9.1 Create `frontend/__tests__/PerformanceSummaryPanel.test.tsx`
- [x] 9.2 Test calibration state: render with `phase_gate_active=true`, assert "Phase 0 — Calibration" text present, no metric rows
- [x] 9.3 Test metrics state: render with `phase_gate_active=false` and valid metrics, assert all 3 metric labels and values present
- [x] 9.4 Test green/red colors: assert correct CSS class on HR row for `hr_status="green"` and `hr_status="red"`
- [x] 9.5 Test break-even warning: assert warning visible when `below_breakeven=true`, not present when `false`
- [x] 9.6 Test `profit_factor=999.0` renders as `∞`
- [x] 9.7 Run `npm test -- --testPathPattern PerformanceSummaryPanel` — all pass

## 10. Verification

- [x] 10.1 Start backend locally (`uv run uvicorn app.main:app --port 8000`) and confirm `GET /api/analysis/performance` returns all new fields
- [x] 10.2 Start frontend dev server (`npm run dev`) and verify `PerformanceSummaryPanel` renders in the app with seed data (GOOGL/AMZN = phase gate active since only 6 total seed signals)
- [x] 10.3 Run full backend test suite: `uv run pytest backend/tests/ -v` — no regressions
- [x] 10.4 Run frontend type check: `npm run type-check` (or `tsc --noEmit`) — no errors
