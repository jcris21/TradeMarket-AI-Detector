## Why

The ScoringAgent currently ranks setups without regard to whether the stop-loss placement is structurally sound relative to intraday volatility. A stop placed inside the ATR noise floor is statistically likely to be triggered by normal price movement rather than a genuine signal failure, producing false positives that pollute the dashboard. This feature eliminates those invalid setups before they reach users by introducing an ATR-based viability gate directly in the scoring pipeline.

## What Changes

- `TechnicalIndicators` dataclass gains two optional fields: `atr_14` (absolute ATR value) and `atr_14_pct` (ATR as % of price), computed by `DataAgent` using `pandas-ta`
- `AssetAnalysis` model gains `stop_viable: bool | None` flag and `atr_14_pct` field, persisted to `analysis_results` DB table
- `ScoringAgent` gains `_compute_atr_viability()` implementing a four-band check: hard disqualify (stop < 0.5× ATR), soft penalty −15 pts (stop < `ATR_FLOOR_FACTOR` × ATR), neutral (0.8×–1.5×), and boost +8 pts (stop > 1.5× ATR)
- Hard-disqualified assets receive `rank = None` and are logged as `atr_disqualify:` errors — distinct from TECH-005's `structural_invalid:` prefix
- `ATR_FLOOR_FACTOR` configurable via `ANALYSIS_ATR_FLOOR` env var (default `0.8`)
- DB schema and lazy migration list updated with `stop_viable INTEGER` column
- Frontend `SignalTable` displays ATR badge (✔ ATR viable / ❌ ATR WARNING) per signal

## Capabilities

### New Capabilities
- `atr-stop-viability`: ATR noise-floor guard in the scoring pipeline — computes ATR in DataAgent, evaluates four-band stop viability in ScoringAgent, exposes `stop_viable` flag on AssetAnalysis, persists to DB, and renders badge in OpportunitiesPanel

### Modified Capabilities
- *(none — no existing spec-level requirements are changing; TECH-005 GuardrailValidator is already merged and its interface is consumed unchanged)*

## Impact

- **Backend — `backend/app/analysis/models.py`**: `TechnicalIndicators` and `AssetAnalysis` dataclasses extended; `to_db_row()` updated
- **Backend — `backend/app/analysis/data_agent.py`**: `_compute_indicators()` computes `atr_14`/`atr_14_pct` via `ta.atr()`
- **Backend — `backend/app/analysis/orchestrator.py`**: enriches `AssetAnalysis` with ATR values post-Stage-3
- **Backend — `backend/app/analysis/scoring_agent.py`**: new `_compute_atr_viability()` helper; `_compute_score()` gains `atr_viability_pts` param; `score_and_rank_with_errors()` integrates ATR gate
- **Backend — `backend/app/db/schema.py`, `connection.py`, `repository.py`**: schema, lazy migration, and INSERT/parse updated for `stop_viable`
- **Frontend — `frontend/lib/types.ts`**: `AssetAnalysis` interface extended
- **Frontend — `frontend/components/OpportunitiesPanel.tsx`**: ATR badge column added to `SignalTable`
- **Tests — `test_data_agent.py`, `test_scoring_agent.py`**: new/updated unit tests covering all ATR branches
- **Dependencies**: `pandas-ta` already installed; zero new external dependencies; zero extra network I/O (reuses existing yfinance OHLCV batch download)
- **Backward compatibility**: all new fields default to `None`; existing fixtures compile and pass without modification
