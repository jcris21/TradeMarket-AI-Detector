## ADDED Requirements

### Requirement: TechnicalIndicators exposes SMA-20 and SMA-50
`TechnicalIndicators` SHALL include `sma_20: Optional[float]` and `sma_50: Optional[float]` fields, both defaulting to `None`, so that downstream scoring logic can access moving-average trend context.

#### Scenario: SMA fields present when sufficient data exists
- **WHEN** `_compute_indicators` processes a DataFrame with 50 or more rows
- **THEN** the returned `TechnicalIndicators` has non-None `sma_20` and `sma_50` values equal to the 20-period and 50-period simple moving averages of close price on the most recent bar

#### Scenario: SMA fields are None when fewer than 50 candles available
- **WHEN** `_compute_indicators` processes a DataFrame where dropna() leaves fewer than 50 rows
- **THEN** the returned `TechnicalIndicators` has `sma_50 = None` (and `sma_20` may also be None)

#### Scenario: Backward compatibility — construction without SMA fields
- **WHEN** `TechnicalIndicators` is constructed without providing `sma_20` or `sma_50`
- **THEN** both fields default to `None` and no error is raised


### Requirement: DataAgent computes SMA-20 and SMA-50 with single dropna
`DataAgent._compute_indicators()` SHALL compute `sma_20` and `sma_50` using `pandas_ta.sma(close, length=20)` and `pandas_ta.sma(close, length=50)`, and SHALL call `dropna()` once after all indicator series are computed rather than per-indicator.

#### Scenario: SMA values match pandas_ta computation
- **WHEN** `fetch_indicators_batch` is called with a ticker that has at least 50 days of historical data
- **THEN** `TechnicalIndicators.sma_20` equals `round(float(ta.sma(close, 20).iloc[-1]), 2)` and `sma_50` equals `round(float(ta.sma(close, 50).iloc[-1]), 2)`

#### Scenario: dropna() removes rows where any indicator is incomplete
- **WHEN** the OHLCV DataFrame has 60 rows
- **THEN** after a single dropna(), the effective series length accounts for the SMA-50 warm-up period (50 rows) and other indicator look-backs, and no NaN values reach indicator extraction


### Requirement: ScoringAgent computes trend_score for BUY signals
`ScoringAgent._compute_trend_score()` SHALL return an integer trend adjustment based on the relationship between price, SMA-20, and SMA-50 for BUY signals:
- Full alignment (SMA-20 > SMA-50 AND price > SMA-20): `+10`
- Partial alignment (price > SMA-20 AND SMA-20 ≤ SMA-50): `+5`
- Counter-trend (price < SMA-20): `−8`
- Either SMA is None: `0` (neutral, no crash)

#### Scenario: Full trend alignment yields +10
- **WHEN** `sma_20 > sma_50` AND `current_price > sma_20`
- **THEN** `_compute_trend_score` returns `10`

#### Scenario: Partial alignment yields +5
- **WHEN** `current_price > sma_20` AND `sma_20 <= sma_50`
- **THEN** `_compute_trend_score` returns `5`

#### Scenario: Counter-trend yields -8
- **WHEN** `current_price < sma_20` (regardless of SMA-20 vs SMA-50 relationship)
- **THEN** `_compute_trend_score` returns `-8`

#### Scenario: None SMAs yield neutral score
- **WHEN** `sma_20` is None OR `sma_50` is None
- **THEN** `_compute_trend_score` returns `0` without raising an exception

#### Scenario: trend_score is added to composite score
- **WHEN** `_compute_score` is called for a BUY signal with full trend alignment
- **THEN** the returned score equals the base formula result plus `10`


### Requirement: ScoringAgent._is_uptrend guards against division by zero
`ScoringAgent._is_uptrend()` SHALL return `True` when `(sma_20 - sma_50) / sma_50 > 0.005`, and SHALL return `False` when `sma_50 == 0` or either SMA is None, without raising a ZeroDivisionError or TypeError.

#### Scenario: Uptrend detected with positive spread above threshold
- **WHEN** `sma_20 = 105.0` and `sma_50 = 100.0` (spread = 5%)
- **THEN** `_is_uptrend` returns `True`

#### Scenario: Ranging detected with spread at or below threshold
- **WHEN** `sma_20 = 100.3` and `sma_50 = 100.0` (spread = 0.3%)
- **THEN** `_is_uptrend` returns `False`

#### Scenario: Division-by-zero guard
- **WHEN** `sma_50 == 0`
- **THEN** `_is_uptrend` returns `False` without raising ZeroDivisionError


### Requirement: RSI bullish zone is adaptive to trend regime
`ScoringAgent._indicator_confluence_score()` SHALL evaluate RSI against an adaptive zone:
- Uptrend (`_is_uptrend` returns True): RSI bullish zone is 50–75
- Ranging (`_is_uptrend` returns False): RSI bullish zone is 40–65

The function SHALL accept `indicators: TechnicalIndicators | None = None` to support adaptive zone selection.

#### Scenario: RSI in uptrend zone scores bullish in uptrend
- **WHEN** RSI = 60 and the asset is in an uptrend (sma_20 > sma_50 by >0.5%)
- **THEN** RSI contributes to `bullish_count` in the confluence calculation

#### Scenario: RSI below uptrend zone does not score bullish in uptrend
- **WHEN** RSI = 45 and the asset is in an uptrend
- **THEN** RSI does NOT contribute to `bullish_count` (45 < 50, outside uptrend zone)

#### Scenario: RSI in ranging zone scores bullish in ranging market
- **WHEN** RSI = 55 and the asset is ranging (sma_20 ≤ sma_50 by 0.5% threshold)
- **THEN** RSI contributes to `bullish_count` (55 is within 40–65)

#### Scenario: RSI in ranging zone does not score bullish when in uptrend zone only
- **WHEN** RSI = 42 and the asset is ranging
- **THEN** RSI contributes to `bullish_count` (42 is within 40–65 ranging zone)
