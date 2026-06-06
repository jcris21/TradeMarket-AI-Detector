## Why

Traders accumulating signal outcomes have no way to evaluate whether the scoring system is actually working. Without a visible hit ratio, profit factor, and realized R/R, they cannot make an informed decision to trust or scale up on the system's recommendations. The `GET /api/analysis/performance` endpoint already exists and returns aggregated data, but there is no frontend panel consuming it — and a critical bug in `scoring_agent._get_hit_rate()` means the EV badge never transitions from "35% assumed" to real observed data.

## What Changes

- **New `PerformanceSummaryPanel` component** renders a rolling performance summary below the OpportunitiesPanel tab bar, always visible.
- **Phase gate logic**: no metrics are shown until 30+ conclusive signals (TARGET_HIT or STOP_HIT) are accumulated — displays a calibration progress bar instead.
- **Extended `get_performance_summary()`** adds `phase_gate_active`, `calibration_count`, `realized_rr`, and color-status fields (`hr_status`, `pf_status`, `rr_status`, `below_breakeven`) to the existing response.
- **Bug fix in `scoring_agent._get_hit_rate()`**: replaces a broken query against a non-existent `signal_outcomes` table with a correct query against `analysis_results`, enabling the EV badge to transition from "assumed" → "observed" at signal #30.
- **`PerformanceResponse` Pydantic model** added to `analysis/models.py` and wired to the `/api/analysis/performance` route with `response_model=`.
- **`usePerformance()` hook** fetches the performance endpoint on mount and re-fetches after each analysis run.
- **`PerformanceSummary` TypeScript interface** added to `frontend/lib/types.ts`.
- Unit and component tests covering 0, 15, 30, and 100 signal scenarios.

## Capabilities

### New Capabilities

- `rolling-performance-panel`: Frontend panel displaying phase-gated performance metrics (Hit Ratio, Profit Factor, Realized R/R) with color-coded thresholds and a break-even warning. Includes `usePerformance()` hook and `PerformanceSummaryPanel` component.

### Modified Capabilities

- `outcome-performance-api`: Extends the existing `/api/analysis/performance` response with `phase_gate_active`, `calibration_count`, `realized_rr`, `hr_status`, `pf_status`, `rr_status`, and `below_breakeven`. Also fixes the `profit_factor = 999.0` zero-division sentinel and the `_get_hit_rate()` bug in `scoring_agent.py`.

## Impact

- **Backend files modified**: `backend/app/db/repository.py`, `backend/app/analysis/outcome_detector.py`, `backend/app/analysis/scoring_agent.py`, `backend/app/routes/analysis.py`, `backend/app/analysis/models.py`, `backend/app/db/__init__.py`
- **Frontend files modified/created**: `frontend/lib/types.ts`, `frontend/lib/use-performance.ts` (new), `frontend/components/PerformanceSummaryPanel.tsx` (new), `frontend/components/OpportunitiesPanel.tsx`
- **Tests**: `backend/tests/analysis/test_performance_panel.py` (new), `frontend/__tests__/PerformanceSummaryPanel.test.tsx` (new)
- **No schema changes**: pure read-path aggregation over existing `analysis_results` table — zero new tables or migrations.
- **Depends on**: STORY-003 (outcome recorder, NEX-11) for real outcome data; works with seed data in MVP.
