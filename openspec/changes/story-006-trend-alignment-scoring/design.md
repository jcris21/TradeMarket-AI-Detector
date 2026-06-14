## Context

The analysis pipeline consists of `DataAgent` (computes `TechnicalIndicators` from OHLCV data via `yfinance` + `pandas_ta`) and `ScoringAgent` (applies a composite score formula and ranks `AssetAnalysis` objects). Currently the scoring formula uses confidence (40%), risk/reward ratio (35%), and an indicator confluence score (25%); the confluence scorer evaluates RSI against a fixed 40–65 zone with no regard to prevailing trend direction.

Two SMA values (SMA-20 and SMA-50) are standard, low-cost trend filters. Their relationship (SMA-20 vs SMA-50) and the price's position relative to SMA-20 provide a three-tier trend alignment signal that can be additively integrated into the existing formula without altering any existing field semantics.

`TechnicalIndicators` is a frozen dataclass. Adding fields with `field(default=None)` is fully backward-compatible: all existing construction sites (unit tests, integration code) continue to work without modification because keyword-only defaults do not affect positional construction.

## Goals / Non-Goals

**Goals:**
- Surface SMA-20 and SMA-50 in `TechnicalIndicators` so downstream consumers can use them
- Reward fully aligned BUY signals and penalize counter-trend BUY signals via an additive `trend_score`
- Make the RSI bullish zone adaptive (50–75 in uptrend, 40–65 in ranging) to reduce false confluence on counter-trend setups
- Guard against edge cases: `sma_50 == 0` division-by-zero, fewer than 50 candles (dropna removes incomplete rows), `None` SMAs (neutral score, no crash)

**Non-Goals:**
- Short/SELL side trend scoring — only BUY signal trend alignment is in scope
- Changing or replacing the composite score formula weighting (confidence 40%, R/R 35%, confluence 25% remain unchanged)
- Adding SMA fields to the `AssetAnalysis` or `AnalysisResult` models — SMA values flow through `TechnicalIndicators` only
- Multi-timeframe trend detection or EMA-based alternatives

## Decisions

### D1: Additive trend_score rather than a new scoring component

**Decision**: `trend_score` is added to the composite score raw value rather than becoming a fourth weighted component.

**Rationale**: The current weighting (40% + 35% + 25% = 100%) is calibrated. Introducing a fourth component would require rebalancing all weights, risking regression against existing backtests. An additive ±10/+5/−8 bonus/penalty is self-contained and bounded — the effect is visible but cannot overwhelm the base score on its own.

**Alternative considered**: Re-weight the confluence component to 20% and allocate 5% to a new trend component. Rejected because it alters scores for all signals, including those with no SMA data.

### D2: Optional SMA fields with `field(default=None)` on the frozen dataclass

**Decision**: Add `sma_20: Optional[float] = field(default=None)` and `sma_50: Optional[float] = field(default=None)` to `TechnicalIndicators`.

**Rationale**: Frozen dataclasses with `field(default=None)` are backward-compatible: all existing construction calls using keyword arguments continue to work. Code that constructs `TechnicalIndicators` without the new fields receives `None`, which maps to `trend_score = 0` (neutral).

**Alternative considered**: Separate `TrendIndicators` dataclass. Rejected — it adds an indirection layer that all three files must import and pass around, for no meaningful isolation gain at this scale.

### D3: Single `dropna()` after all indicator computations in DataAgent

**Decision**: Call `dropna()` once after all indicator series (MACD, RSI, volume SMA, SMA-20, SMA-50) have been appended to the DataFrame.

**Rationale**: Multiple intermediate `dropna()` calls can discard rows that would be valid once all series are available, especially for longer-period indicators (SMA-50 needs 50 rows). A single final `dropna()` is deterministic and avoids the asymmetry.

**Alternative considered**: Keep existing per-indicator approach and add separate dropna for SMA series. Rejected — inconsistent behavior across indicators is a latent bug.

### D4: `_is_uptrend` threshold of 0.5% (0.005)

**Decision**: Uptrend condition: `(sma_20 - sma_50) / sma_50 > 0.005`.

**Rationale**: A strict `sma_20 > sma_50` check would fire on any positive spread, including near-zero ones that are essentially flat. The 0.5% threshold filters noise and aligns with standard retail trend-filter conventions.

**Alternative considered**: Fixed threshold of 1% (0.01). Less sensitive — would miss early-stage uptrends. Rejected in favor of 0.5% as specified in the acceptance criteria.

## Risks / Trade-offs

- **Score inflation for aligned signals**: Adding up to +10 on top of an already high base score could push fully aligned signals near or above 100. → Mitigation: the formula result is not capped in the current implementation; this is consistent with existing behavior (no cap enforced). Document the unbounded range.

- **Score deflation for counter-trend signals**: A −8 penalty may drop marginal signals below the `min_rr` qualification threshold. → Mitigation: This is the intended behavior — counter-trend signals should rank lower. No mitigation needed.

- **Fewer than 50 candles**: With `period="3mo"` (~63 trading days) this should not occur in production for liquid tickers, but can happen for very new listings or fetches during market data outages. → Mitigation: `dropna()` removes incomplete rows; the `len(df) < 30` early-exit guard in `_compute_indicators` already handles pathologically short series.

- **SMA fields visible in `TechnicalIndicators` but not in `AssetAnalysis.indicators_summary`**: Downstream consumers that read `indicators_summary` (e.g., the LLM system prompt) will not automatically see SMA values. → Accept: out of scope for this story; can be added when the LLM context builder is updated.

## Migration Plan

1. Deploy as a single atomic change — no migration steps required; all field additions are backward-compatible.
2. Existing rows in `analysis_results` are unaffected; `score` values will shift slightly for signals where SMA data is available; this is expected and desired.
3. Rollback: revert the three modified files; scores return to pre-change values immediately with no database cleanup needed.

## Open Questions

- Should the `trend_score` be stored as a separate column in `analysis_results` for audit/debugging? Currently it is absorbed into the composite `score`. Deferred to a future story.
- Should `sma_20` and `sma_50` values be included in `AssetAnalysis.indicators_summary` for LLM context? Deferred — requires the LLM context builder to be updated separately.
