"""ScoringAgent — filter, score, and rank asset analyses."""

import os

import aiosqlite

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


def _compute_bet_size(asset: AssetAnalysis, hit_rate: float, source: str) -> AssetAnalysis:
    """Return asset with expected_gain_per10, expected_loss_per10, expected_value_per10 populated."""
    entry = asset.entry_price
    if entry <= 0:
        return asset.model_copy(update={
            "expected_gain_per10": 0.0,
            "expected_loss_per10": 0.0,
            "expected_value_per10": 0.0,
            "hit_rate_used": hit_rate,
            "hit_rate_source": source,
        })
    gain = round(10 * (asset.target_price - entry) / entry, 2)
    loss = round(10 * (entry - asset.stop_loss) / entry, 2)
    ev = round(hit_rate * gain - (1 - hit_rate) * loss, 2)
    return asset.model_copy(update={
        "expected_gain_per10": gain,
        "expected_loss_per10": loss,
        "expected_value_per10": ev,
        "hit_rate_used": hit_rate,
        "hit_rate_source": source,
    })


async def _get_prior_scores(db: aiosqlite.Connection) -> dict[str, float]:
    """Batch-fetch scores from the previous run. Returns {} on first run or DB error."""
    try:
        cursor = await db.execute(
            "SELECT ticker, score FROM analysis_results "
            "WHERE run_id = ("
            "  SELECT run_id FROM analysis_results "
            "  GROUP BY run_id ORDER BY MAX(analyzed_at) DESC LIMIT 1 OFFSET 1"
            ")"
        )
        rows = await cursor.fetchall()
        return {row["ticker"]: row["score"] for row in rows if row["score"] is not None}
    except aiosqlite.OperationalError:
        return {}


async def _get_hit_rate(db: aiosqlite.Connection) -> tuple[float, str]:
    """Query signal_outcomes for realized hit rate. Falls back to 35% assumed if table absent or < 30 rows."""
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) AS wins "
            "FROM signal_outcomes WHERE user_id = 'default'"
        )
        row = await cursor.fetchone()
        total = row[0] if row else 0
        wins = int(row[1]) if row and row[1] is not None else 0
        if total >= 30:
            return wins / total, "realized"
    except aiosqlite.OperationalError:
        pass
    return 0.35, "assumed"


def score_and_rank(
    analyses: list[AssetAnalysis],
    hit_rate: float = 0.35,
    hit_rate_source: str = "assumed",
    prior_scores: dict[str, float] | None = None,
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

    _prior = prior_scores or {}
    scored: list[AssetAnalysis] = []
    for asset in analyses:
        s = _compute_score(asset)
        delta = round(s - _prior.get(asset.ticker, s), 2)
        with_score = asset.model_copy(update={"score": s, "score_delta": delta})
        scored.append(_compute_bet_size(with_score, hit_rate, hit_rate_source))

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
