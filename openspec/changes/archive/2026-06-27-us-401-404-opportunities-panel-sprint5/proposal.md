## Why

The Top Opportunities panel currently caps at 5 signals with no pagination, no collapse option, no score-band differentiation, and no per-row freshness context. Sprint 5 expands this panel to surface 20 ranked signals, adds UX controls for space management and scanability, and completes the freshness display layer so traders can instantly judge signal actuality.

## What Changes

- `ANALYSIS_TOP_N` default raised from 5 → 20; `AnalysisResult` gains a canonical `top_n` field (alias `top_5` kept for backward compat)
- `/api/analysis/latest` returns `total_analyzed` count and, for P1, `prior_score_quant` per ticker
- `OpportunitiesPanel` gains client-side 10-per-page pagination with prev/next controls, page dots, and keyboard nav
- `OpportunitiesPanel` header becomes a collapse toggle with `localStorage` persistence; body animates with `max-height` CSS transition
- Each signal row gains: `ScoreBandBadge` (ELITE/STRONG/QUALIFYING), `MiniScoreBar`, freshness dot + age label
- Band dividers inserted between rows on band transition within the current page
- Expired rows in archive tab styled at 40% opacity with ticker strikethrough and `EXPIRED` badge
- Backend gains `get_prior_scores()` to populate `prior_score_quant` (P1)

## Capabilities

### New Capabilities

- `signal-pagination`: 10-per-page client-side pagination of the Top Opportunities table — state, controls, keyboard nav, auto-reset on new run, summary line with total counts
- `collapsible-opportunities-panel`: Collapse/expand the panel via header click or `Shift+O`; `localStorage` persistence; auto-expand on run completion (unless manually collapsed during run); inline 5-second status banner; regime gate badge
- `score-band-segmentation`: ELITE/STRONG/QUALIFYING badge per row, `MiniScoreBar` with enrichment delta overlay, band dividers between rows, band counts in summary (P1)
- `signal-freshness-row-indicator`: Per-row freshness dot + live age label updated every 60s; expired row styling (opacity + strikethrough + EXPIRED badge); `ScoreQuantDelta` for prior-run comparison (P1)

### Modified Capabilities

- `signal-freshness`: Extended from standalone badge to per-row inline dot + age label; adds `prior_score_quant` backend field and `get_prior_scores()` repository function (P1)

## Impact

- **Backend**: `scoring_agent.py`, `models.py`, `orchestrator.py`, `routes/analysis.py`, `db/repository.py`
- **Frontend**: `components/OpportunitiesPanel.tsx` (all 4 features), `lib/types.ts`
- **E2E tests**: Assert `top_n` field; verify `top_5` alias still passes
- **No new API endpoints** — `/api/analysis/latest` response shape extended with `total_analyzed` and `prior_score_quant`
- **No schema migration** — `prior_score_quant` is computed at query time, not stored
