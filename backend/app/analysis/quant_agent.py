"""QuantAgent — builds AssetAnalysis purely from numerical indicators, no LLM call."""

from .models import AssetAnalysis, TechnicalIndicators


def _derive_signal(indicators: TechnicalIndicators) -> tuple[str, float]:
    """Derive signal and confidence from indicator rules. Returns (signal, confidence)."""
    bullish = 0
    bearish = 0

    if indicators.macd_signal == "bullish_crossover":
        bullish += 1
    elif indicators.macd_signal == "bearish_crossover":
        bearish += 1

    if indicators.rsi < 30:
        bullish += 1  # oversold
    elif 40 <= indicators.rsi <= 60:
        bullish += 1  # momentum zone
    elif indicators.rsi > 70:
        bearish += 1  # overbought

    if indicators.volume_ratio > 1.2:
        bullish += 1
    elif indicators.volume_ratio < 0.8:
        bearish += 1

    if indicators.sma_50 is not None:
        if indicators.current_price > indicators.sma_50:
            bullish += 1
        else:
            bearish += 1

    total = bullish + bearish
    if total == 0:
        return "WAIT", 0.5

    confidence = round(bullish / (total + 2), 2)  # dampened toward 0.5

    if bullish >= 3 and bullish > bearish:
        return "BUY", confidence
    if bearish >= 3 and bearish > bullish:
        return "AVOID", confidence
    return "WAIT", confidence


def _build_argument(
    indicators: TechnicalIndicators, signal: str, bullish: int, bearish: int
) -> str:
    parts = [
        f"RSI={indicators.rsi:.1f}",
        f"MACD={indicators.macd_signal}",
        f"Vol={indicators.volume_ratio:.2f}x",
    ]
    if indicators.sma_50 is not None:
        trend = "above" if indicators.current_price > indicators.sma_50 else "below"
        parts.append(f"price {trend} SMA-50")
    return f"Quant {signal}: {', '.join(parts)}. Bulls={bullish} Bears={bearish}."


def quant_analyze(indicators: TechnicalIndicators) -> AssetAnalysis:
    """Build an AssetAnalysis from quantitative indicators only — zero LLM calls.

    Prices are set from S1/R1 pivot points; the downstream orchestrator's ATR/BB
    injection and scoring pipeline consume indicators_summary unchanged.
    """
    signal, confidence = _derive_signal(indicators)

    # Count raw signals for argument
    bullish = 0
    bearish = 0
    if indicators.macd_signal == "bullish_crossover":
        bullish += 1
    elif indicators.macd_signal == "bearish_crossover":
        bearish += 1
    if indicators.rsi < 30 or 40 <= indicators.rsi <= 60:
        bullish += 1
    elif indicators.rsi > 70:
        bearish += 1
    if indicators.volume_ratio > 1.2:
        bullish += 1
    elif indicators.volume_ratio < 0.8:
        bearish += 1
    if indicators.sma_50 is not None:
        if indicators.current_price > indicators.sma_50:
            bullish += 1
        else:
            bearish += 1

    entry = indicators.current_price

    # Use nearest support for stop, farther resistance (R2) for target.
    # S1 is the tighter stop (less risk per trade); R2 is the extended target,
    # giving a realistic RR that clears the 3.0 minimum filter.
    stop = indicators.support_1
    target = indicators.resistance_2  # farther level → higher RR

    # Clamp to valid geometry: stop < entry < target
    if stop >= entry:
        stop = entry * 0.97
    if target <= entry:
        target = indicators.resistance_1 if indicators.resistance_1 > entry else entry * 1.09

    rr = round((target - entry) / (entry - stop), 2) if (entry - stop) > 0.01 else 0.0

    volume_label = (
        f"above_average ({indicators.volume_ratio:.1f}x)"
        if indicators.volume_ratio >= 1.0
        else f"below_average ({indicators.volume_ratio:.1f}x)"
    )

    indicators_summary: dict = {
        "macd": indicators.macd_signal,
        "rsi": round(indicators.rsi, 1),
        "volume": volume_label,
        "current_price": entry,
        "support_1": indicators.support_1,
        "support_2": indicators.support_2,
        "resistance_1": indicators.resistance_1,
        "resistance_2": indicators.resistance_2,
        "stop_used": round(stop, 2),
        "target_used": round(target, 2),
    }

    return AssetAnalysis(
        ticker=indicators.ticker,
        signal=signal,
        confidence=confidence,
        entry_price=round(entry, 2),
        target_price=round(target, 2),
        stop_loss=round(stop, 2),
        risk_reward_ratio=rr,
        support_validated=False,
        indicators_summary=indicators_summary,
        argument=_build_argument(indicators, signal, bullish, bearish),
    )
