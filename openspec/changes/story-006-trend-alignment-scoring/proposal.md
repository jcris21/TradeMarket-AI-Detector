## Why

The scoring formula currently treats all BUY signals equally regardless of their relationship to the prevailing trend, rewarding counter-trend entries as highly as with-trend ones. Adding trend alignment scoring ensures signals aligned with the dominant SMA trend score higher and rank first, improving signal quality without disrupting existing scoring logic.

## What Changes

- Add `sma_20` and `sma_50` fields (optional float, default None) to `TechnicalIndicators` frozen dataclass
- Extend `DataAgent._compute_indicators()` to compute SMA-20 and SMA-50 via `pandas_ta`, with a single `dropna()` after all indicators
- Add `_is_uptrend(indicators)` helper to `ScoringAgent` (guards against `sma_50 == 0` division-by-zero)
- Add `_compute_trend_score(asset, indicators)` helper with three branches: full alignment (+10), partial alignment (+5), counter-trend (−8); returns 0 when SMAs are None
- Integrate `trend_score` additively into `_compute_score()` — no existing field is removed or renamed
- Update `_indicator_confluence_score()` RSI zone to be adaptive: 50–75 in uptrend, 40–65 in ranging
- Add parametrized unit tests covering all three trend score branches and both RSI regimes

## Capabilities

### New Capabilities
- `trend-alignment-scoring`: Computes per-asset trend alignment score (+10/+5/−8) using SMA-20 vs SMA-50 relationship and integrates it additively into the composite score; also makes the RSI bullish zone adaptive to uptrend vs ranging conditions.

### Modified Capabilities
- None — no existing spec-level requirements change; this is a purely additive extension.

## Impact

- `backend/app/analysis/models.py` — `TechnicalIndicators` dataclass gains two optional fields (`sma_20`, `sma_50`)
- `backend/app/analysis/data_agent.py` — `_compute_indicators()` computes and returns the new SMA fields; single `dropna()` consolidation
- `backend/app/analysis/scoring_agent.py` — new helper functions; composite score formula updated; RSI zone becomes adaptive
- `backend/tests/analysis/test_data_agent.py` — new assertions for SMA fields in returned `TechnicalIndicators`
- `backend/tests/analysis/test_scoring_agent.py` — parametrized tests for trend score branches and RSI regimes
- No API contract changes; no database schema changes; no breaking changes to any existing field
