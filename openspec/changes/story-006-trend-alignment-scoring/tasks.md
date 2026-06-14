## 1. Data Model — TechnicalIndicators

- [ ] 1.1 Add `sma_20: Optional[float] = field(default=None)` to `TechnicalIndicators` frozen dataclass in `backend/app/analysis/models.py`
- [ ] 1.2 Add `sma_50: Optional[float] = field(default=None)` to `TechnicalIndicators` frozen dataclass in `backend/app/analysis/models.py`
- [ ] 1.3 Add `from typing import Optional` import if not already present in `models.py`

## 2. DataAgent — SMA Computation

- [ ] 2.1 In `_compute_indicators()` in `backend/app/analysis/data_agent.py`, compute `sma_20_series = ta.sma(close, length=20)` after the existing volume SMA computation
- [ ] 2.2 Compute `sma_50_series = ta.sma(close, length=50)` immediately after SMA-20
- [ ] 2.3 Extract scalar values: `sma_20 = round(float(sma_20_series.iloc[-1]), 2) if sma_20_series is not None else None` and equivalently for `sma_50`
- [ ] 2.4 Consolidate all `dropna()` calls — remove any per-series dropna and add a single `df = df.dropna()` (or equivalent on the close series) after all indicator series are computed, before extracting `.iloc[-1]` values
- [ ] 2.5 Pass `sma_20=sma_20` and `sma_50=sma_50` in the `TechnicalIndicators(...)` constructor call at the end of `_compute_indicators()`

## 3. ScoringAgent — Trend Score Helpers

- [ ] 3.1 Add `_is_uptrend(sma_20: float | None, sma_50: float | None) -> bool` function to `backend/app/analysis/scoring_agent.py`; return `False` if either is None or `sma_50 == 0`; return `(sma_20 - sma_50) / sma_50 > 0.005`
- [ ] 3.2 Add `_compute_trend_score(indicators_summary: dict) -> int` (or accept the SMA values directly) that returns `+10` for full alignment, `+5` for partial, `−8` for counter-trend, `0` for None SMAs
- [ ] 3.3 Integrate `trend_score` additively in `_compute_score()`: `return round(confidence_component + rr_component + confluence_component + trend_score, 2)`

## 4. ScoringAgent — Adaptive RSI Zone

- [ ] 4.1 Update `_indicator_confluence_score(summary: dict)` signature to accept an optional `indicators` parameter (or derive uptrend from `summary` keys `sma_20`/`sma_50` if passed there)
- [ ] 4.2 Replace the fixed RSI check `40 <= rsi <= 65` with an adaptive check: `50 <= rsi <= 75` when `_is_uptrend(sma_20, sma_50)` is True, `40 <= rsi <= 65` otherwise
- [ ] 4.3 Ensure `_indicator_confluence_score` call site in `_compute_score` passes the necessary SMA context

## 5. Tests — DataAgent

- [ ] 5.1 Add test in `backend/tests/analysis/test_data_agent.py` that mocks a DataFrame with ≥50 rows and asserts `TechnicalIndicators.sma_20` and `sma_20` are non-None floats matching the last SMA value
- [ ] 5.2 Add test that mocks a DataFrame with <50 rows and asserts `sma_50` is None (dropna removes incomplete rows, insufficient for SMA-50)
- [ ] 5.3 Verify existing tests pass without modification (backward compatibility with no SMA fields in fixture construction)

## 6. Tests — ScoringAgent

- [ ] 6.1 Add parametrized test in `backend/tests/analysis/test_scoring_agent.py` for `_compute_trend_score` covering: full alignment → +10, partial alignment → +5, counter-trend → −8, None SMAs → 0
- [ ] 6.2 Add parametrized test for `_is_uptrend`: spread > 0.5% → True, spread ≤ 0.5% → False, sma_50=0 → False (no ZeroDivisionError), None input → False
- [ ] 6.3 Add test for adaptive RSI zone: RSI=60 with uptrend → bullish, RSI=45 with uptrend → not bullish, RSI=55 with ranging → bullish, RSI=42 with ranging → bullish
- [ ] 6.4 Add integration test for `score_and_rank` that confirms a fully aligned BUY signal scores higher than an equivalent counter-trend BUY signal (delta ≥ 18 points)
