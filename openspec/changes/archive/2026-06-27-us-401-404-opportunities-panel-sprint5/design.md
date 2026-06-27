## Context

`OpportunitiesPanel.tsx` (627 lines) is the primary signal-discovery UI. It currently shows a Top 5 list in a fixed-height non-collapsible panel with no band differentiation and no per-row freshness context. Sprint 5 ships four coordinated enhancements across this component: pagination (US-401), collapse (US-402), score bands (US-403), and freshness row indicators (US-404). All four share the same render loop and must interoperate without conflicts.

Backend: `scoring_agent.py` uses `ANALYSIS_TOP_N` env var (default 5). `AnalysisResult` holds `top_5: list[AssetAnalysis]`. `GET /api/analysis/latest` serialises this. No pagination, no `total_analyzed`, no `prior_score_quant` today.

## Goals / Non-Goals

**Goals:**
- Expand signal display to 20 with 10-per-page client-side pagination
- Make the panel collapsible with `localStorage` persistence
- Add score band badges, mini bars, and band dividers per row
- Add per-row freshness dot + live age label; style expired rows distinctly
- Keep backward compatibility: `top_5` alias, existing E2E tests pass unchanged
- Single-origin API — no new endpoints, only response shape extensions

**Non-Goals:**
- Server-side pagination (all signals loaded in one response)
- Global toast system (inline banner inside panel is sufficient)
- Multi-user considerations (`user_id = "default"` unchanged)
- Storing `prior_score_quant` in the database (computed at query time)
- Theming or layout changes outside `OpportunitiesPanel`

## Decisions

### D1: `top_n` canonical field + `top_5` deprecated alias
**Decision:** Add `top_n: list[AssetAnalysis]` to `AnalysisResult`; set `top_5 = top_n` in `orchestrator.py`. Both fields carry the same list reference.
**Why:** E2E tests assert `top_5`; renaming would break them this sprint. Alias costs zero and can be removed in Sprint 6 cleanup.
**Alternative considered:** Keep only `top_5`, rename in Sprint 6 — rejected because `top_20` was an original requirement and `top_n` communicates intent better.

### D2: Client-side pagination only
**Decision:** Slice `displayedSignals` in the React component. No API call per page turn.
**Why:** 20 signals is trivially small. Client-side is instant and avoids added backend complexity. A `useEffect` on `lastAnalyzedAt` resets `currentPage` to 1 on each new run.

### D3: Inline status banner, not a global toast
**Decision:** 5-second fade banner inside the panel header on run completion. No global toast infrastructure.
**Why:** Avoids adding a new global primitive to a single-container, single-page app. The notification is co-located with the panel it describes. Aligns with the FinAlly "data-dense, no chrome" aesthetic.
**Alternative considered:** Global toast (react-hot-toast) — rejected for over-engineering scope.

### D4: `max-height` CSS transition for collapse animation
**Decision:** Wrap panel body in `<div style={{ maxHeight: collapsed ? "0px" : "2000px" }}>` with `transition-all duration-200 ease-out`.
**Why:** Pure CSS, zero JS animation frames, no ResizeObserver. The 2000px cap is large enough for 10 rows + pagination. Known limitation: initial expand animates from 0→2000px (full duration) regardless of actual content height.

### D5: Auto-expand behavior on new run
**Decision:** Capture `collapsed` value at run-start via `useRef`. Auto-expand only if the panel was not manually collapsed during the run.
**Why:** Prevents the panel from hijacking trader screen space when they deliberately minimised it to watch the chart during a live run.

### D6: `prior_score_quant` is a query-time join, not stored
**Decision:** `get_prior_scores(run_id)` queries `analysis_runs` for the immediately prior completed run, then fetches `score_quant` from `analysis_results`. Result is a dict injected at serialisation time.
**Why:** No schema migration needed. Data is derived from existing tables. One extra O(N) query per `/api/analysis/latest` call — acceptable.

### D7: Score band uses `score_quant`, falls back to `score`
**Decision:** `getScoreBand(score_quant ?? score)` — `score_quant` is the normative source; `score` is the legacy fallback for rows that predate US-301.
**Why:** Keeps band display functional on older cached data without crashing.

## Risks / Trade-offs

- **`max-height` animation feels slow on short lists** → Acceptable; 200ms is brief enough at 10 rows. Could switch to `height` with `useRef` measurement if reported as jarring.
- **`ANALYSIS_TOP_N` raised to 20 increases scoring compute** → Negligible; 100 tickers × 20-item slice is still O(N log N) sort, same data.
- **`prior_score_quant` query adds DB round-trip** → One extra indexed query per API call. `analysis_runs` table is small (one row per run). Acceptable.
- **E2E tests asserting `top_5` length ≤ 5** → Tests may fail if they assert exact count. Mitigation: tests should assert `top_5` exists and is a list; count assertions should move to `top_n`.
- **`localStorage` access in Next.js SSR** → Gated behind `typeof window !== "undefined"` in initial state. Safe.

## Migration Plan

1. Backend changes deploy first (env var default, model field alias, `total_analyzed`, `prior_score_quant`)
2. Frontend changes deploy in same image build — no intermediate state where frontend expects fields the backend doesn't return
3. Existing `ANALYSIS_TOP_N` env var overrides continue to work; operators who set `ANALYSIS_TOP_N=5` keep the old behavior
4. Rollback: revert env var to `5`; `top_5` alias keeps frontend working; no DB migration to undo

## Open Questions

- **`top_5` alias removal sprint**: Propose Sprint 6 cleanup issue to remove alias and update E2E tests. Should be tracked in Linear.
- **Keyboard nav scope**: `→`/`←` for pagination — should these be scoped to panel focus or global? Currently proposed as panel-scoped `onKeyDown`. Confirm with UX.
- **Band divider on page boundary**: If band changes across a page boundary (last row of page 1 is STRONG, first row of page 2 is QUALIFYING), the divider won't appear. Acceptable for V1 since bands are sorted by `score_quant` and pages are sequential.
