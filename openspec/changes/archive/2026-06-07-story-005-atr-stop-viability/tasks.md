## 1. Data Model — TechnicalIndicators and AssetAnalysis

- [x] 1.1 Add `atr_14: float | None = field(default=None)` to `TechnicalIndicators` frozen dataclass in `backend/app/analysis/models.py`
- [x] 1.2 Add `atr_14_pct: float | None = field(default=None)` to `TechnicalIndicators` frozen dataclass in `backend/app/analysis/models.py`
- [x] 1.3 Add `atr_14: float | None = None`, `atr_14_pct: float | None = None`, `stop_viable: bool | None = None` fields to `AssetAnalysis` in `backend/app/analysis/models.py`
- [x] 1.4 Update `AssetAnalysis.to_db_row()` to include `stop_viable` (as `int` or `None`) and `atr_14_pct`

## 2. DataAgent — ATR Computation

- [x] 2.1 Add ATR computation block in `DataAgent._compute_indicators()` in `backend/app/analysis/data_agent.py` using `ta.atr(high, low, close, length=14)`
- [x] 2.2 Apply `pd.isna()` guard and `current_price > 0` guard; set both fields to `None` on any failure
- [x] 2.3 Pass `atr_14=atr_14, atr_14_pct=atr_14_pct` to the `TechnicalIndicators(...)` constructor call

## 3. Orchestrator — ATR Enrichment

- [x] 3.1 After `asyncio.gather(*vision_tasks)` in `backend/app/analysis/orchestrator.py`, inject `atr_14` and `atr_14_pct` from Stage-1 results into each `AssetAnalysis` via `model_copy(update={...})`

## 4. ScoringAgent — ATR Viability Check

- [x] 4.1 Add module-level constants `_ATR_HARD_FLOOR = 0.5`, `_ATR_BOOST_THRESHOLD = 1.5`, `_ATR_PENALTY_PTS = -15.0`, `_ATR_BOOST_PTS = 8.0` in `backend/app/analysis/scoring_agent.py`
- [x] 4.2 Add `_atr_floor_factor()` function reading `ANALYSIS_ATR_FLOOR` env var with default `"0.8"`
- [x] 4.3 Implement `_compute_atr_viability(asset: AssetAnalysis) -> tuple[bool, bool, float]` returning `(hard_disqualify, stop_viable, atr_viability_pts)` per the four-band logic
- [x] 4.4 Update `_compute_score()` signature to accept `atr_viability_pts: float = 0.0` and add it to the composite score
- [x] 4.5 Integrate ATR gate into `score_and_rank_with_errors()`: call `_compute_atr_viability()`, handle hard-disqualify path (append `atr_disqualify:` error, set `rank=None`, `stop_viable=False`, continue), pass `atr_pts` to `_compute_score()`, set `stop_viable` on scored asset

## 5. Database — Schema and Migration

- [x] 5.1 Add `stop_viable INTEGER` column to the `analysis_results` CREATE TABLE statement in `backend/app/db/schema.py`
- [x] 5.2 Add `("stop_viable", "INTEGER")` to the lazy migration column list in `backend/app/db/connection.py`
- [x] 5.3 Add `stop_viable` to the INSERT statement in `backend/app/db/repository.py`
- [x] 5.4 Update `_parse_analysis_row()` in `backend/app/db/repository.py` to parse `stop_viable` as `bool | None` (convert `1`→`True`, `0`→`False`, `NULL`→`None`)

## 6. Frontend — Types and ATR Badge

- [x] 6.1 Add `atr_14_pct?: number | null` and `stop_viable?: boolean | null` to the `AssetAnalysis` interface in `frontend/lib/types.ts`
- [x] 6.2 Add ATR badge `<td>` column to `SignalTable` row in `frontend/components/OpportunitiesPanel.tsx`: "✔ ATR" (`text-gain`) when `stop_viable === true`, "❌ ATR" (`text-loss`) when `stop_viable === false`, "—" (`text-text-muted`) when `atr_14_pct == null`

## 7. Tests — DataAgent

- [x] 7.1 Add test in `backend/tests/analysis/test_data_agent.py`: mock `ta.atr()` returning `Series([5.0])` with price `100.0` → assert `atr_14 == 5.0` and `atr_14_pct == 0.00005`
- [x] 7.2 Add test in `backend/tests/analysis/test_data_agent.py`: mock `ta.atr()` returning `None` → assert `atr_14 is None` and `atr_14_pct is None`

## 8. Tests — ScoringAgent

- [x] 8.1 Add parametrized test covering hard-disqualify branch: `stop_distance_pct=0.03`, `atr_14_pct=0.08` → `rank is None`, error contains `atr_disqualify:`
- [x] 8.2 Add parametrized test covering soft-penalty branch: `stop_distance_pct=0.05`, `atr_14_pct=0.08` → `stop_viable=False`, score 15 pts below baseline
- [x] 8.3 Add parametrized test covering neutral band: `stop_distance_pct=0.08`, `atr_14_pct=0.08` → `stop_viable=True`, no score delta
- [x] 8.4 Add parametrized test covering boost branch: `stop_distance_pct=0.15`, `atr_14_pct=0.08` → `stop_viable=True`, score 8 pts above baseline
- [x] 8.5 Add `test_atr_none_fallback`: asset with `atr_14_pct=None` passes scoring with unchanged score and `stop_viable=None`
- [x] 8.6 Add regression test: signals that passed scoring before this feature (with default ATR-neutral stop distances) continue to pass with the same rank order
