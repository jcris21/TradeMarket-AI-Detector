## 1. Backend — Model & Scoring (US-401)

- [x] 1.1 In `backend/app/analysis/models.py`: add `top_n: list[AssetAnalysis] = []` and `total_analyzed: int = 0` fields to `AnalysisResult`; keep `top_5: list[AssetAnalysis] = []` as deprecated alias
- [x] 1.2 In `backend/app/analysis/scoring_agent.py`: change `ANALYSIS_TOP_N` default from `"5"` to `"20"`; clamp value to range 5–20
- [x] 1.3 In `backend/app/analysis/orchestrator.py`: populate `top_n=top_n_results`, `top_5=top_n_results`, and `total_analyzed=len(analyses)` in `AnalysisResult(...)` constructor call
- [x] 1.4 In `backend/app/routes/analysis.py`: include `total_analyzed` in the serialised `/api/analysis/latest` response

## 2. Backend — prior_score_quant (US-404 P1)

- [x] 2.1 In `backend/app/db/repository.py`: implement `get_prior_scores(conn, run_id: str) -> dict[str, float]` — find the last completed run before `run_id`, return `{ticker: score_quant}` dict; return `{}` when no prior run exists
- [x] 2.2 In `backend/app/routes/analysis.py`: call `get_prior_scores()` and inject `prior_score_quant` onto each item in `top_n` before serialisation; field is `null` when ticker not in prior run

## 3. Frontend — Types (US-401, US-404)

- [x] 3.1 In `frontend/lib/types.ts`: add `top_n?: AssetAnalysis[]` and `total_analyzed?: number` to `AnalysisResponse`
- [x] 3.2 In `frontend/lib/types.ts`: add `prior_score_quant?: number | null` to `AssetAnalysis` (for US-404 P1)

## 4. Frontend — Score Band Utilities (US-403)

- [x] 4.1 Define `ScoreBand` type and `getScoreBand(score)` utility function in `OpportunitiesPanel.tsx` (or a shared util file); thresholds: ELITE ≥75, STRONG 60–74, QUALIFYING 50–59, NONE otherwise
- [x] 4.2 Define `BAND_COLORS` constant map: ELITE→`#ECAD0A`, STRONG→`#209DD7`, QUALIFYING→`#888888`, NONE→`#444444`
- [x] 4.3 Implement `ScoreBandBadge` component: renders badge with band label, colored border; returns null for NONE band
- [x] 4.4 Implement `MiniScoreBar` component: numeric score in band color + 64px bar at score_quant% fill + optional delta overlay capped at 100%
- [x] 4.5 Add band divider logic in signal row loop: compare current row band to previous row band; insert `<tr>` divider row with band label when band changes

## 5. Frontend — Pagination (US-401)

- [x] 5.1 Add `currentPage` state (default 1) and `PAGE_SIZE = 10` constant to `OpportunitiesPanel`
- [x] 5.2 Add `useEffect` on `lastAnalyzedAt` (or equivalent run-complete signal) to reset `currentPage` to 1 on new run
- [x] 5.3 Compute `totalPages = Math.ceil(displayedSignals.length / PAGE_SIZE)` and `pageSignals = displayedSignals.slice(...)` for current page
- [x] 5.4 Render summary line above table: `"Showing N of M qualified signals (K analyzed)"` — omit `(K analyzed)` when `total_analyzed` is 0 or absent
- [x] 5.5 Render pagination controls (`← Prev`, `Page N of M`, `Next →`, page dots) below table only when `totalPages > 1`; disable Prev on page 1, Next on last page
- [x] 5.6 Add `onKeyDown` handler on panel div for `ArrowLeft`/`ArrowRight` to change page; add `tabIndex={0}` on panel div for focus
- [x] 5.7 Add `EnrichmentBadge` component and render it per row (empty when no `enrichment_delta`, `+N visual` green or `-N visual` red otherwise)

## 6. Frontend — Collapsible Panel (US-402)

- [x] 6.1 Add `collapsed` state initialised from `localStorage.getItem("finally_top_opps_collapsed")`; gate localStorage access behind `typeof window !== "undefined"`
- [x] 6.2 Implement `toggleCollapsed` callback that updates state and writes to localStorage
- [x] 6.3 Wrap panel body in `<div className="overflow-hidden transition-all duration-200 ease-out" style={{ maxHeight: collapsed ? "0px" : "2000px" }}>` 
- [x] 6.4 Update header: add chevron (`▶`/`▼`), `cursor-pointer`, `select-none`, `onClick={toggleCollapsed}`, `aria-expanded={!collapsed}`
- [x] 6.5 Add collapsed count badge `[N]` in header; show only when collapsed and signal count > 0
- [x] 6.6 Add `e.stopPropagation()` on the Analizar button click handler so it does not toggle collapse
- [x] 6.7 Capture `collapsed` value at run-start via `useRef`; on run completion, auto-expand only if not manually collapsed during run; show inline 5-second banner via `setTimeout`
- [x] 6.8 Add global `keydown` listener for `Shift+O` to call `toggleCollapsed`; clean up listener on unmount (P1)
- [x] 6.9 Add regime gate badge in amber (#C47A00) to header when `regime_gate_active: true` (P1)

## 7. Frontend — Freshness Row Indicators (US-404)

- [x] 7.1 Add `now` state with `setInterval` updating every 60s in `OpportunitiesPanel`; implement `formatAge(analyzedAt, nowMs)` utility returning `"Xm ago"` / `"Xh Ym ago"`
- [x] 7.2 Implement `FreshnessDot` component: 8px circle with color from `FRESHNESS_DOT_COLOR` map (fresh→`#22c55e`, active/aged/stale→amber/red, expired→`#6B7280`)
- [x] 7.3 Render `<FreshnessDot>` + age label inline per row; omit entirely when `freshness_status` is absent
- [x] 7.4 Apply expired row styling in archive tab: `opacity: 0.4`, `text-decoration: line-through` on ticker, render `ExpiredBadge` instead of `ScoreBandBadge`
- [x] 7.5 Implement `ScoreQuantDelta` component: absent when no `prior_score_quant`; `=` grey for |delta| ≤ 3; `▲ +N` green or `▼ -N` red otherwise (P1)
- [x] 7.6 Render `ScoreQuantDelta` per row in signal table (P1)
- [x] 7.7 Ensure `clearInterval` is called in `useEffect` cleanup for the 60s interval

## 8. Tests

- [x] 8.1 Backend unit test: `get_prior_scores()` returns correct dict for known prior run; returns `{}` when no prior run
- [x] 8.2 Backend unit test: `ANALYSIS_TOP_N=20` default — scoring_agent returns up to 20 results; `top_5` alias equals `top_n`
- [x] 8.3 Backend unit test: `total_analyzed` in API response matches asset count passed to scoring
- [x] 8.4 Frontend unit test: `getScoreBand()` returns correct band for boundary values (50, 60, 75, 74.9, 49.9)
- [x] 8.5 Frontend unit test: `formatAge()` formats correctly for <60m, ≥60m, and exact hours
- [x] 8.6 Frontend unit test: `ScoreBandBadge` renders correct color and label; returns null for NONE
- [x] 8.7 Frontend unit test: `MiniScoreBar` base fill width and delta overlay capped at 100%
- [x] 8.8 E2E test: assert `top_n` field present in analysis response; assert `top_5` alias equals `top_n`
- [x] 8.9 E2E test: pagination controls hidden when ≤10 signals; visible and functional when >10 signals
- [x] 8.10 E2E test: panel collapse persists after page reload via localStorage

## 9. Cleanup & Docs

- [x] 9.1 Update `docs/api-spec.yml` to document `top_n`, `total_analyzed`, and `prior_score_quant` fields on `/api/analysis/latest` response
- [x] 9.2 Mark `top_5` field in `models.py` with deprecation comment referencing Sprint 6 removal
- [x] 9.3 Create Linear issue for Sprint 6 to remove `top_5` alias and update E2E tests
