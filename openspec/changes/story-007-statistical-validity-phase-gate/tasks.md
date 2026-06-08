## 1. Backend — Pure Function

- [x] 1.1 Add `_compute_phase(conclusive: int) -> tuple[int, str]` as a module-level function in `backend/app/db/repository.py` returning (phase 0–3, banner string) per spec thresholds (0–29 / 30–99 / 100–299 / 300+)

## 2. Backend — get_performance_summary

- [x] 2.1 Replace the `phase_gate_active = conclusive < 30` line in `get_performance_summary()` with `phase, phase_banner = _compute_phase(conclusive)` and `phase_gate_active = phase == 0`
- [x] 2.2 Add `"phase": phase` and `"phase_banner": phase_banner` to the returned dict in `get_performance_summary()`

## 3. Backend — PerformanceResponse Model

- [x] 3.1 Add `phase: int` and `phase_banner: str` fields to the `PerformanceResponse` Pydantic model in `backend/app/analysis/models.py`

## 4. Backend — PerformanceSummary Dataclass

- [x] 4.1 Add `phase: int = 0` and `phase_banner: str = ""` fields to the `PerformanceSummary` dataclass in `backend/app/analysis/outcome_detector.py`
- [x] 4.2 In `_compute_summary()`, replace the `phase_gate_active = conclusive < 30` line with `phase, phase_banner = _compute_phase(conclusive)` and `phase_gate_active = phase == 0`; import `_compute_phase` from `app.db.repository`
- [x] 4.3 Populate `phase=phase` and `phase_banner=phase_banner` in the `PerformanceSummary(...)` constructor call

## 5. Backend — Unit Tests

- [x] 5.1 Add parametrized `test_compute_phase` to `backend/tests/db/test_performance_summary.py` covering all 8 boundary values: `(0, 0)`, `(1, 0)`, `(29, 0)`, `(30, 1)`, `(99, 1)`, `(100, 2)`, `(299, 2)`, `(300, 3)` — asserting phase integer and a key substring in the banner
- [x] 5.2 Add integration test asserting `get_performance_summary()` dict contains keys `"phase"` and `"phase_banner"` with correct values at boundaries 29→30 and 99→100
- [ ] 5.3 Verify all existing `test_performance_summary.py` and `test_performance_panel.py` tests still pass (regression guard)

## 6. Frontend — TypeScript Types

- [x] 6.1 Add `phase: number` and `phase_banner: string` to the `PerformanceSummary` interface in `frontend/lib/types.ts`

## 7. Frontend — PerformanceSummaryPanel Component

- [x] 7.1 In the Phase 0 branch of `PerformanceSummaryPanel.tsx`, replace the hardcoded `"Phase 0 — Calibration"` span and `"{n}/30 signals"` span with `{summary.phase_banner}` rendered as a single string
- [x] 7.2 In the Phase 1+ branch, replace the hardcoded `"Phase 1 Performance (…)"` header string with a label derived from `summary.phase`: `const phaseLabel = ["Calibration", "Pilot", "Evaluation", "Confident"][summary.phase] ?? "Unknown"` and render `Phase ${summary.phase}: ${phaseLabel}`
- [x] 7.3 Add a defensive fallback `summary.phase ?? 0` when reading the `phase` field to guard against older API responses that may not include it
