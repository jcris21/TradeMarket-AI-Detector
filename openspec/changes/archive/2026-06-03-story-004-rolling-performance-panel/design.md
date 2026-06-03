## Context

The `GET /api/analysis/performance` endpoint already exists (`backend/app/routes/analysis.py:95-98`) and calls `get_performance_summary()` (`backend/app/db/repository.py:452-504`). The current response includes `total_signals`, `target_hits`, `stop_hits`, `expired`, `orphaned_count`, `hit_ratio`, and `profit_factor`. The frontend has no component consuming this data.

A critical bug exists in `scoring_agent._get_hit_rate()`: it queries a non-existent `signal_outcomes` table, silently catches the `OperationalError`, and always returns `0.35, "assumed"` — the EV badge never transitions to real observed data.

The existing `PerformanceSummary` dataclass in `outcome_detector.py` is used internally to model the response but does not yet include phase gate or color-status fields.

## Goals / Non-Goals

**Goals:**

- Add `PerformanceSummaryPanel` component to the frontend that renders phase-gated performance metrics
- Extend `get_performance_summary()` to return `phase_gate_active`, `calibration_count`, `realized_rr`, and color-status fields without changing the existing field names
- Fix `_get_hit_rate()` to read from `analysis_results` so the EV badge transitions at signal #30
- Add a `PerformanceResponse` Pydantic model to the performance route for typed API contracts
- Add `usePerformance()` hook that re-fetches after analysis runs complete
- Achieve 80%+ test coverage for the new backend function and frontend component

**Non-Goals:**

- No new database tables or schema migrations
- No WebSocket or SSE push for performance updates — polling on run completion is sufficient
- No historical performance charting (out of scope for MVP)
- No per-ticker breakdown — summary only
- No authentication or multi-user scoping beyond the existing `user_id = "default"` pattern

## Decisions

### Decision: Extend response in-place vs. new endpoint

**Chosen:** Extend the existing `GET /api/analysis/performance` response with new fields.

**Rationale:** The endpoint is not yet consumed by any frontend, so there are no breaking clients. Adding fields to the response is backward-compatible (additive JSON). A second endpoint would duplicate the aggregation query and split the contract.

**Alternative considered:** `GET /api/analysis/performance/v2` — rejected because versioning adds complexity with no benefit when the v1 consumer count is zero.

---

### Decision: Phase gate threshold at 30 conclusive signals (not total_signals)

**Chosen:** `conclusive = target_hits + stop_hits`. EXPIRED signals are excluded from the denominator for all metrics and from the gate count.

**Rationale:** Matches the Kaabar CLT heuristic cited in NEX-12: you need 30 resolved (binary outcome) events to make CLT-valid inferences. An EXPIRED signal provides no information about the system's predictive accuracy.

**Alternative considered:** Using `total_signals` including EXPIRED — rejected because it inflates the count with uninformative data and understates calibration needs.

---

### Decision: `profit_factor = 999.0` sentinel instead of `null` when stop_hits = 0

**Chosen:** Return `999.0` (a finite float) when `total_loss == 0` and `total_gain > 0`.

**Rationale:** `float("inf")` is not valid JSON; `null` would require the frontend to handle a special case inline in formatted strings. `999.0` is a well-understood sentinel (common in trading software) that renders naturally as a large number and signals "infinite" to the user without breaking JSON parsing.

**Alternative considered:** `null` + frontend special-case — rejected because it adds conditional rendering logic in two places (backend serialization + frontend display).

---

### Decision: Color-status fields computed in the repository, not the frontend

**Chosen:** `hr_status`, `pf_status`, `rr_status`, `below_breakeven` are computed in `get_performance_summary()` and returned as strings.

**Rationale:** Threshold logic (≥35% green, <25% red) is a domain rule that belongs to the backend. Keeping it there means the frontend is a pure renderer; thresholds can be tuned without a frontend deploy.

**Alternative considered:** Raw numbers only, frontend applies threshold logic — rejected because it duplicates business rules and makes the frontend harder to test in isolation.

---

### Decision: `usePerformance()` re-fetches by watching analysis `status` transition

**Chosen:** The hook listens to the `status` field from `useAnalysis()`. When `status` transitions from `"running"` to `"done"`, trigger a re-fetch of `/api/analysis/performance`.

**Rationale:** Simple, avoids polling. Analysis runs are infrequent (manual trigger); a single re-fetch on completion is sufficient and cheap.

**Alternative considered:** Interval polling every 30s — rejected as wasteful given runs are manual.

---

### Decision: `_get_hit_rate()` reads `analysis_results`, not a separate table

**Chosen:** Replace the broken `signal_outcomes` query with a direct `SELECT … FROM analysis_results WHERE outcome IN ('TARGET_HIT', 'STOP_HIT')`.

**Rationale:** The `analysis_results` table is the authoritative source for outcomes. There is no `signal_outcomes` table in the schema; it was a planning artifact that was never materialized.

## Risks / Trade-offs

- **Stale EV badge during a run** — the `_get_hit_rate()` fix will be evaluated once per analysis run, not live. Users who complete run #30 and immediately trigger another run will see the badge update on that second run. Acceptable for MVP.
- **Phase gate UX** — showing "0/30 signals" on first launch may be confusing without context about what "30" means. The calibration bar label includes "Phase 0 — Calibration" to signal this is expected behavior, not an error.
- **`profit_factor = 999.0` display** — may look odd if rendered without truncation. Frontend should cap display at "∞" or "999" with a tooltip.
- **SQLite performance at scale** — the `idx_analysis_outcome` index (already created in `init_db`) keeps the aggregation fast. At 10,000 rows (~10 years of signals) the query is still sub-millisecond.

## Migration Plan

1. Backend changes are additive — no DB migration, no breaking API changes.
2. Deploy backend: new fields appear in `/api/analysis/performance` response.
3. Deploy frontend: `usePerformance()` and `PerformanceSummaryPanel` are new files; `OpportunitiesPanel` import is additive.
4. Rollback: revert frontend files; backend new fields are ignored by old frontend.

## Open Questions

- Should `realized_rr` display as `—` or be hidden entirely when `phase_gate_active === true`? Current design: entire metrics section is hidden; calibration bar is shown instead.
- Should the panel be collapsible in a future iteration? Out of scope for MVP — always visible.
