"""ScoringAgent — filter, score, and rank asset analyses."""

import os

from .models import AssetAnalysis


def _indicator_confluence_score(summary: dict) -> float:
    """Return 0–100 based on how many indicators are bullish."""
    bullish_count = 0

    macd = summary.get("macd", "")
    if macd == "bullish_crossover":
        bullish_count += 1

    rsi = summary.get("rsi", 50.0)
    if isinstance(rsi, (int, float)) and 40 <= rsi <= 65:
        bullish_count += 1

    volume = summary.get("volume", "")
    if isinstance(volume, str) and "above" in volume.lower():
        bullish_count += 1
    elif isinstance(volume, (int, float)) and volume > 1.2:
        bullish_count += 1

    return (bullish_count / 3) * 100


def _compute_score(asset: AssetAnalysis) -> float:
    """Composite score 0–100."""
    confidence_component = asset.confidence * 40
    rr_normalized = min(asset.risk_reward_ratio / 6.0, 1.0) * 100
    rr_component = rr_normalized * 0.35
    confluence = _indicator_confluence_score(asset.indicators_summary)
    confluence_component = confluence * 0.25
    return round(confidence_component + rr_component + confluence_component, 2)


def score_and_rank(
    analyses: list[AssetAnalysis],
    min_rr: float | None = None,
    top_n: int | None = None,
) -> list[AssetAnalysis]:
    """Filter, score, and rank a list of AssetAnalysis objects.

    Returns all assets (not just Top N) with .rank and .score populated.
    Assets that don't qualify have rank=None.
    """
    if min_rr is None:
        min_rr = float(os.environ.get("ANALYSIS_MIN_RR_RATIO", "3.0"))
    if top_n is None:
        top_n = int(os.environ.get("ANALYSIS_TOP_N", "5"))

    scored: list[AssetAnalysis] = []
    for asset in analyses:
        s = _compute_score(asset)
        scored.append(asset.model_copy(update={"score": s}))

    # Separate qualifying from non-qualifying
    def qualifies(a: AssetAnalysis) -> bool:
        return (
            a.risk_reward_ratio >= min_rr
            and a.signal in ("BUY", "WAIT")
        )

    qualifying = [a for a in scored if qualifies(a)]
    not_qualifying = [a for a in scored if not qualifies(a)]

    qualifying.sort(key=lambda a: a.score or 0, reverse=True)
    qualifying = qualifying[:top_n]

    ranked: list[AssetAnalysis] = []
    for i, asset in enumerate(qualifying, start=1):
        ranked.append(asset.model_copy(update={"rank": i}))

    for asset in not_qualifying:
        ranked.append(asset.model_copy(update={"rank": None}))

    return ranked
