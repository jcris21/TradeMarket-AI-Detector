## Why

Lagging indicators (MACD, RSI, SMA, ATR, BB) confirm regime changes after the fact, so during a bear market or volatility spike all signals fail simultaneously (Pareto Scenario 1). Adding a pre-filter that suppresses signals before they reach the scoring/LLM stages avoids wasted LLM spend and protects the trader from a homogeneous slate of AVOID recommendations without context.

## What Changes

- `DataAgent` computes `sma_200` using `pandas-ta` (same pattern as `sma_50`) and the download period changes from `period="3mo"` to `period="1y"` in both `fetch_indicators_batch()` and `fetch_indicators()` to guarantee ≥ 200 daily bars
- `OrchestratorAgent` adds a **per-ticker SMA-200 regime gate** after Stage 1: tickers with `current_price ≤ sma_200` are excluded from Stages 2–4 with `signal="AVOID"`, `rank_exclusion_reason="regime_bearish"`; `sma_200 is None` → fail open
- `OrchestratorAgent` adds a **system-wide VIX gate**: `^VIX` is fetched concurrently with Stage 1 via `asyncio.gather`; if `vix_value > ANALYSIS_VIX_THRESHOLD` (default 25.0), all BUY signals (new + stale) are converted to AVOID with `rank_exclusion_reason="regime_vix"` after Stage 4
- New env var `ANALYSIS_VIX_THRESHOLD` (float, default 25.0; set to 999 to disable)
- `AssetAnalysis` gains `rank_exclusion_reason: str | None` (persisted to DB — migration required)
- `AnalysisResult` gains `regime_gate_active: bool` and `vix_value: float | None` (API response only, no DB column)
- DB schema adds `rank_exclusion_reason TEXT` column to `analysis_results` with idempotent migration guard
- Frontend renders a yellow warning banner when `regime_gate_active: true`

## Capabilities

### New Capabilities

- `regime-gate`: Two-layer macro pre-filter — per-ticker SMA-200 gate suppressing below-trend tickers before LLM stages, plus a system-wide VIX gate suppressing all BUY signals when volatility exceeds a configurable threshold.

### Modified Capabilities

- `score-quant`: `AssetAnalysis` gains `rank_exclusion_reason` (persisted); `AnalysisResult` gains `regime_gate_active` and `vix_value`; DB migration adds `rank_exclusion_reason` column.
- `stale-data-fallback`: Stale fallback assets with `signal="BUY"` are subject to VIX gate transformation after Stage 4.

## Impact

- **Backend files**: `backend/app/analysis/models.py`, `backend/app/analysis/data_agent.py`, `backend/app/analysis/orchestrator.py`, `backend/db/schema.py`, `backend/app/routes/analysis.py`
- **Frontend**: analysis panel component — add regime gate warning banner
- **Tests**: `backend/tests/analysis/test_data_agent.py` (2 new + period mock updates), `backend/tests/analysis/test_orchestrator.py` (8 new)
- **DB migration**: idempotent `ALTER TABLE analysis_results ADD COLUMN rank_exclusion_reason TEXT`
- **Depends on US-102** — coordinate `period="1y"` change to avoid duplicate PR
- **Performance**: VIX fetch parallelised with Stage 1 — zero serial latency added; `period="1y"` increases per-ticker payload ~4×
