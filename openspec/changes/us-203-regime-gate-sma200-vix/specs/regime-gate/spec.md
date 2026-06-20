## ADDED Requirements

### Requirement: SMA-200 per-ticker regime gate suppresses below-trend tickers
After Stage 1 completes, `OrchestratorAgent` SHALL partition the `successful` ticker dict. Any ticker whose `current_price <= sma_200` SHALL be excluded from Stages 2–4 and represented as a synthetic `AssetAnalysis` with `signal="AVOID"`, `rank=None`, `rank_exclusion_reason="regime_bearish"`. Tickers with `sma_200 is None` SHALL pass through (fail-open).

#### Scenario: Price below SMA-200 suppressed before Stage 2
- **WHEN** a ticker has `current_price=150.0` and `sma_200=200.0`
- **THEN** the ticker does not enter Stage 2; its synthetic `AssetAnalysis` has `signal="AVOID"`, `rank=None`, `rank_exclusion_reason="regime_bearish"`

#### Scenario: Price above SMA-200 passes through
- **WHEN** a ticker has `current_price=210.0` and `sma_200=200.0`
- **THEN** the ticker proceeds to Stage 2 unchanged

#### Scenario: SMA-200 unavailable — fail open
- **WHEN** a ticker's `sma_200 is None` (fewer than 200 bars)
- **THEN** the ticker proceeds to Stage 2 unchanged (not excluded)

#### Scenario: Regime-excluded assets not persisted to DB
- **WHEN** a ticker is excluded by the SMA-200 gate
- **THEN** no row is written to `analysis_results` for that ticker in this run

### Requirement: VIX system-wide gate suppresses all BUY signals when threshold exceeded
`OrchestratorAgent` SHALL fetch `^VIX` concurrently with Stage 1 using `asyncio.gather`. If the latest VIX close exceeds `ANALYSIS_VIX_THRESHOLD` (float, default 25.0), all assets with `signal="BUY"` in the final ranked list (including stale fallback assets) SHALL be converted to `signal="AVOID"`, `rank=None`, `rank_exclusion_reason="regime_vix"`. Setting `ANALYSIS_VIX_THRESHOLD >= 999` SHALL disable the gate entirely.

#### Scenario: VIX above threshold suppresses all BUY signals
- **WHEN** `vix_value=27.3` and `ANALYSIS_VIX_THRESHOLD=25.0`
- **THEN** every asset with `signal="BUY"` in `ranked` is converted to `signal="AVOID"` with `rank_exclusion_reason="regime_vix"`; `top_5 == []`

#### Scenario: VIX below threshold — BUY signals preserved
- **WHEN** `vix_value=20.0` and `ANALYSIS_VIX_THRESHOLD=25.0`
- **THEN** BUY signals are unchanged; `regime_gate_active == False`

#### Scenario: VIX fetch failure — fail open
- **WHEN** the `^VIX` yfinance fetch raises an exception or returns empty
- **THEN** `vix_value=None`, `regime_gate_active=False`, a WARNING is logged, and no BUY signals are suppressed

#### Scenario: VIX threshold set to 999 disables gate
- **WHEN** `ANALYSIS_VIX_THRESHOLD=999`
- **THEN** `regime_gate_active=False` regardless of actual VIX value

#### Scenario: Stale fallback BUY signals subject to VIX gate
- **WHEN** a stale fallback asset has `signal="BUY"` and the VIX gate is active
- **THEN** the stale asset is converted to `signal="AVOID"` with `rank_exclusion_reason="regime_vix"`

### Requirement: AnalysisResult carries regime gate fields
`AnalysisResult` SHALL include `regime_gate_active: bool = False` and `vix_value: float | None = None`. These fields SHALL be populated from the orchestrator run and included in the `/api/analysis/run` response. They SHALL NOT be stored to DB.

#### Scenario: Gate active — fields populated
- **WHEN** `vix_value=27.3` and threshold is exceeded
- **THEN** `result.regime_gate_active == True` and `result.vix_value == 27.3`

#### Scenario: Gate inactive — fields reflect current values
- **WHEN** `vix_value=20.0` and threshold is not exceeded
- **THEN** `result.regime_gate_active == False` and `result.vix_value == 20.0`

### Requirement: SMA-200 computed in TechnicalIndicators
`TechnicalIndicators` SHALL include `sma_200: float | None = None`. `DataAgent._compute_indicators()` SHALL compute it via `pandas_ta.sma(close, length=200)` using the same exception-safe pattern as `sma_50`. The download period SHALL be `"1y"` in both `fetch_indicators()` and `fetch_indicators_batch()` to guarantee ≥ 200 bars.

#### Scenario: Sufficient data — SMA-200 computed
- **WHEN** `_compute_indicators()` runs with 250+ bars of daily data
- **THEN** `sma_200` is a non-None float

#### Scenario: Insufficient data — SMA-200 is None
- **WHEN** fewer than 200 bars are available
- **THEN** `sma_200 is None` and no exception propagates

### Requirement: rank_exclusion_reason persisted to analysis_results
`AssetAnalysis.to_db_row()` SHALL include `rank_exclusion_reason`. The `analysis_results` table SHALL have a `rank_exclusion_reason TEXT` nullable column added via an idempotent `ALTER TABLE` migration guard on startup.

#### Scenario: Regime-excluded asset reason persisted
- **WHEN** an asset has `rank_exclusion_reason="regime_bearish"` and is written to DB
- **THEN** `SELECT rank_exclusion_reason FROM analysis_results WHERE ticker=?` returns `"regime_bearish"`

#### Scenario: Idempotent migration on existing DB
- **WHEN** the column already exists and the migration guard runs again
- **THEN** startup completes without error

### Requirement: Frontend regime gate warning banner
When the `/api/analysis/run` response includes `regime_gate_active: true`, the frontend SHALL render a persistent yellow warning banner above the results panel displaying the VIX value. The banner SHALL clear when the next run returns `regime_gate_active: false`.

#### Scenario: Banner shown when gate is active
- **WHEN** the analysis run response has `regime_gate_active: true` and `vix_value: 27.3`
- **THEN** a yellow banner is displayed with text indicating VIX is 27.3 and BUY signals are suppressed

#### Scenario: Banner cleared when gate is inactive
- **WHEN** the next analysis run response has `regime_gate_active: false`
- **THEN** the banner is no longer displayed
