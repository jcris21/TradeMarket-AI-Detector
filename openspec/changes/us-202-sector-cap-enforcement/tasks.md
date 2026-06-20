## 1. Model Changes

- [x] 1.1 Add `rank_exclusion_reason: str | None = None` to `AssetAnalysis` in `backend/app/analysis/models.py` (runtime-only, not in `to_db_row()`)
- [x] 1.2 Add `sector_cap_exclusions: dict[str, int] = {}` to `AnalysisResult` in `backend/app/analysis/models.py`

## 2. Seed Data

- [x] 2.1 Add ETF entries (SPY, QQQ, IWM, GLD, TLT) to `backend/app/analysis/seed_tickers.py` with `sector="etf"`

## 3. Sector Cap Logic in ScoringAgent

- [x] 3.1 Add `_BYPASS_SECTORS: frozenset[str] = frozenset({"unknown", "etf"})` constant to `backend/app/analysis/scoring_agent.py`
- [x] 3.2 Add `_sector_cap() -> int` function: read `ANALYSIS_SECTOR_CAP` env var at call time, wrap `int()` in `try/except ValueError`, clamp to [1, 5], default 2
- [x] 3.3 Add `_apply_sector_cap(qualifying, cap) -> tuple[list[AssetAnalysis], list[AssetAnalysis], dict[str, int]]` function: greedy walk, skip bypass sectors, set `rank=None` + `rank_exclusion_reason` on excluded assets, return `(accepted, excluded, exclusion_counts)`
- [x] 3.4 Update `score_and_rank_with_errors()`: call `_apply_sector_cap()` after sort, before `[:top_n]` slice; fold `cap_excluded` into `not_qualifying`; return 3-tuple `(ranked_all, structural_errors, sector_cap_exclusions)`
- [x] 3.5 Update `score_and_rank()` wrapper to unpack 3-tuple and discard `sector_cap_exclusions` (preserve existing 2-tuple return for callers)

## 4. Orchestrator Integration

- [x] 4.1 Update Stage 4 call in `backend/app/analysis/orchestrator.py` to unpack 3-tuple from `score_and_rank_with_errors()`
- [x] 4.2 Pass `sector_cap_exclusions` to `AnalysisResult` constructor
- [x] 4.3 Add `sector_cap_exclusions` to Stage 4 `stage_complete` log entry

## 5. Tests

- [x] 5.1 Write `test_sector_cap_limits_per_sector_to_cap` — 5 Tech assets, cap=2 → 2 ranked, 3 excluded with `rank_exclusion_reason="sector_cap:Technology"`
- [x] 5.2 Write `test_sector_cap_unknown_bypasses_cap` — 5 `sector="unknown"` assets, cap=2 → all 5 ranked
- [x] 5.3 Write `test_sector_cap_etf_bypasses_cap` — 3 `sector="etf"` assets, cap=2 → all 3 ranked
- [x] 5.4 Write `test_sector_cap_mixed_sectors` — 3 Tech + 2 Financials + 1 Energy, cap=2 → 5 accepted
- [x] 5.5 Write `test_sector_cap_exclusions_counted_in_result` — verify `sector_cap_exclusions` dict has correct per-sector counts
- [x] 5.6 Write `test_sector_cap_respects_score_order` — lower-scored ticker excluded before higher-scored in same sector
- [x] 5.7 Write `test_sector_cap_env_clamping` — cap=0 → effective 1; cap=10 → effective 5
- [x] 5.8 Write `test_sector_cap_default_is_2` — no env var → cap=2
- [x] 5.9 Write `test_sector_cap_rank_exclusion_reason_format` — excluded asset has `rank_exclusion_reason == "sector_cap:Technology"`
- [x] 5.10 Write `test_existing_top_n_still_applied_after_sector_cap` — top_n=5 limits accepted list to 5 after cap
- [x] 5.11 Verify all existing `test_scoring_agent.py` tests pass without modification

## 6. Verification

- [x] 6.1 Run full test suite; confirm 0 regressions in `test_scoring_agent.py` and `test_orchestrator.py`
- [x] 6.2 Verify `/api/analysis/run` response JSON includes `sector_cap_exclusions` field
- [x] 6.3 Confirm `rank_exclusion_reason` is absent from `analysis_results` DB columns (not persisted)
