## Context

`score_and_rank_with_errors()` in `scoring_agent.py` currently sorts qualifying assets by `score_quant` descending and slices to `[:top_n]`. With 100 tickers in a correlated sector (40 tech, r=0.6) a strong tech day can fill all 20 ranked slots with tech signals. US-101 has already added `sector: str` to `AssetAnalysis` so the field is available at the scoring stage.

## Goals / Non-Goals

**Goals:**
- Enforce a per-sector maximum in the ranked Top-N, configurable via env var, applied greedily in score order
- Surface exclusion metadata (`rank_exclusion_reason`, `sector_cap_exclusions`) in the API response and Stage 4 logs
- Keep O(n) complexity — no extra DB calls, no retry logic

**Non-Goals:**
- Storing `rank_exclusion_reason` to the database (runtime-only this story; open a separate migration story if needed)
- Weighted or proportional allocation across sectors (greedy cap is deliberately simple)
- Frontend rendering of sector cap metadata (telemetry only for now)

## Decisions

**Decision 1 — Greedy walk, not proportional allocation**
Greedy preserves `score_quant` ordering — the highest-scoring asset in each sector always wins. Proportional allocation would require a second pass and could admit lower-scoring assets from over-represented sectors. Tradeoff: in a universe with few non-tech tickers the cap may shrink the ranked list below `top_n`; this is acceptable and expected.

**Decision 2 — Cap read at call time, not module load**
Reading `ANALYSIS_SECTOR_CAP` inside `_sector_cap()` on every call means tests can override the env var without monkey-patching. Caching at module load would require test teardown. Cost is negligible (a single `os.environ.get` per run).

**Decision 3 — `rank_exclusion_reason` as runtime field, no DB migration**
The exclusion reason is diagnostic metadata for the current run. Persisting it creates a migration dependency. If future observability requires it (e.g., tracking how often a sector fills the cap) that warrants its own story and migration.

**Decision 4 — `score_and_rank_with_errors` returns 3-tuple**
Returning `(ranked_all, structural_errors, sector_cap_exclusions)` avoids a mutable side-channel. The public `score_and_rank` wrapper absorbs the third element so all existing callers are unaffected.

**Decision 5 — ETFs bypass cap via `sector="etf"`**
ETFs are index proxies, not sector concentration. Assigning `sector="etf"` and treating it as a bypass sector (alongside `"unknown"`) keeps the logic uniform without special-casing tickers by name.

## Risks / Trade-offs

[Risk: Top-N list shorter than requested after cap] → Mitigation: This is correct behavior — the cap trades list length for sector diversity. Document in the API response that `len(ranked) < top_n` is possible.

[Risk: `ANALYSIS_SECTOR_CAP` misconfigured as non-integer] → Mitigation: wrap `int()` in `try/except ValueError`, fall back to default 2. Score silently, never raise on misconfiguration.

[Risk: `sector` field is empty string or None] → Mitigation: coerce with `(asset.sector or "unknown").strip().lower()` — empty strings map to `"unknown"` and bypass the cap.

[Risk: test_scoring_agent.py regressions from 3-tuple return] → Mitigation: update `score_and_rank` wrapper before any test changes; all callers of the public wrapper are unaffected.

## Migration Plan

1. Add fields to `models.py` — no DB migration
2. Add `_sector_cap()`, `_apply_sector_cap()`, `_BYPASS_SECTORS` to `scoring_agent.py`
3. Update `score_and_rank_with_errors` to call cap, return 3-tuple
4. Update `score_and_rank` wrapper to unpack 3-tuple
5. Update `orchestrator.py` Stage 4 call and `AnalysisResult` constructor
6. Add ETF entries to `seed_tickers.py`
7. Write tests, verify all existing tests pass

Rollback: revert `scoring_agent.py` and `orchestrator.py`; no DB changes to undo.

## Open Questions

- Should `sector_cap_exclusions` also include sectors that hit the cap but still had slots (i.e., show the full per-sector accepted count, not just excluded)? Current spec: excluded-only counts. Confirm with product.
