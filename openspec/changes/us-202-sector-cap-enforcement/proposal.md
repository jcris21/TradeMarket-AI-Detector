## Why

Without a per-sector cap, a strong correlated day (e.g., 40 tech tickers with r=0.6) can fill the entire Top 20 with signals from a single sector, giving the trader a false sense of diversification and maximising drawdown when the sector reverses. Sprint 2 enforces a configurable cap so the ranked results are structurally diversified.

## What Changes

- `ScoringAgent` applies a greedy sector cap after sorting qualifying assets by `score_quant` descending and before the `[:top_n]` slice — assets exceeding the cap per sector receive `rank=None` and a `rank_exclusion_reason`
- New env var `ANALYSIS_SECTOR_CAP` (int, 1–5, default 2) read at call time with clamping and error-safe fallback
- `AssetAnalysis` gains `rank_exclusion_reason: str | None` (runtime-only, no DB migration)
- `AnalysisResult` gains `sector_cap_exclusions: dict[str, int]` — per-sector excluded count surfaced in the API response and Stage 4 log
- `seed_tickers.py` adds ETF entries (SPY, QQQ, IWM, GLD, TLT) with `sector="etf"` so they bypass the cap
- `score_and_rank_with_errors` return type changes from 2-tuple to 3-tuple; `score_and_rank` wrapper updated to unpack and discard extras (no breaking change for callers)

## Capabilities

### New Capabilities

- `sector-cap-enforcement`: Greedy post-sort filter in ScoringAgent that enforces a configurable per-sector maximum in ranked results, with bypass logic for `unknown` and `etf` sectors and per-sector exclusion telemetry.

### Modified Capabilities

- `score-quant`: Ranking now produces a 3-tuple `(ranked_all, structural_errors, sector_cap_exclusions)`; `AnalysisResult` includes `sector_cap_exclusions`; `AssetAnalysis` includes `rank_exclusion_reason`.

## Impact

- **Backend files**: `backend/app/analysis/models.py`, `backend/app/analysis/scoring_agent.py`, `backend/app/analysis/orchestrator.py`, `backend/app/analysis/seed_tickers.py`
- **Tests**: `backend/tests/analysis/test_scoring_agent.py` (10 new test cases)
- **API**: `/api/analysis/run` response gains `sector_cap_exclusions` field
- **No DB migration required** — `rank_exclusion_reason` is runtime-only in this story
- **Depends on US-101** — `AssetAnalysis.sector` must be populated before `score_and_rank_with_errors` is called
