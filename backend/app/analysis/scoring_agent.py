"""ScoringAgent — filter, score, and rank asset analyses."""

import os

import aiosqlite

from .models import AssetAnalysis


_ATR_HARD_FLOOR = 0.5
_ATR_BOOST_THRESHOLD = 1.5
_ATR_PENALTY_PTS = -15.0
_ATR_BOOST_PTS = 8.0


def _atr_floor_factor() -> float:
    try:
        return float(os.environ.get("ANALYSIS_ATR_FLOOR", "0.8"))
    except ValueError:
        return 0.8


def _compute_atr_viability(asset: AssetAnalysis) -> tuple[bool, bool, float]:
    """Return (hard_disqualify, stop_viable, score_delta).

    When atr_14_pct is None, passes through unchanged: (False, True, 0.0).
    """
    if asset.atr_14_pct is None or asset.entry_price <= 0:
        return False, True, 0.0

    stop_distance_pct = (asset.entry_price - asset.stop_loss) / asset.entry_price
    atr = asset.atr_14_pct
    floor_factor = _atr_floor_factor()

    if stop_distance_pct < _ATR_HARD_FLOOR * atr:
        return True, False, 0.0
    if stop_distance_pct < floor_factor * atr:
        return False, False, _ATR_PENALTY_PTS
    if stop_distance_pct > _ATR_BOOST_THRESHOLD * atr:
        return False, True, _ATR_BOOST_PTS
    return False, True, 0.0


def validate_asset_analysis(asset: AssetAnalysis) -> tuple[bool, str]:
    """Guardrail layer: validate structural invariants from LLM output."""
    if asset.entry_price <= 0:
        return False, "entry_price <= 0"
    if asset.stop_loss >= asset.entry_price:
        return False, "stop_loss >= entry_price (inverted stop)"
    if asset.target_price <= asset.entry_price:
        return False, "target_price <= entry_price (inverted target)"
    if asset.risk_reward_ratio < 0:
        return False, "negative risk_reward_ratio"
    return True, ""


def _quarantine_invalid_asset(asset: AssetAnalysis) -> AssetAnalysis:
    """Return an unranked asset with no derived scoring fields."""
    return asset.model_copy(update={
        "score": None,
        "score_delta": None,
        "rank": None,
        "expected_gain_per10": None,
        "expected_loss_per10": None,
        "expected_value_per10": None,
        "hit_rate_used": None,
        "hit_rate_source": None,
    })


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


def _compute_score(asset: AssetAnalysis, atr_viability_pts: float = 0.0) -> float:
    """Composite score 0–100 plus ATR adjustment."""
    confidence_component = asset.confidence * 40
    rr_normalized = min(asset.risk_reward_ratio / 6.0, 1.0) * 100
    rr_component = rr_normalized * 0.35
    confluence = _indicator_confluence_score(asset.indicators_summary)
    confluence_component = confluence * 0.25
    return round(confidence_component + rr_component + confluence_component + atr_viability_pts, 2)


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
    """Return (hit_rate, source). Falls back to 0.35 'assumed' if conclusive < 30."""
    try:
        cursor = await db.execute(
            "SELECT "
            "  SUM(CASE WHEN outcome = 'TARGET_HIT' THEN 1 ELSE 0 END) AS hits, "
            "  SUM(CASE WHEN outcome IN ('TARGET_HIT', 'STOP_HIT') THEN 1 ELSE 0 END) AS conclusive "
            "FROM analysis_results "
            "WHERE user_id = 'default' AND outcome IN ('TARGET_HIT', 'STOP_HIT')"
        )
        row = await cursor.fetchone()
        conclusive = int(row["conclusive"]) if row and row["conclusive"] else 0
        hits = int(row["hits"]) if row and row["hits"] else 0
        if conclusive >= 30:
            return round(hits / conclusive, 4), "observed"
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
    ranked, _errors = score_and_rank_with_errors(
        analyses,
        hit_rate=hit_rate,
        hit_rate_source=hit_rate_source,
        prior_scores=prior_scores,
        min_rr=min_rr,
        top_n=top_n,
    )
    return ranked


def score_and_rank_with_errors(
    analyses: list[AssetAnalysis],
    hit_rate: float = 0.35,
    hit_rate_source: str = "assumed",
    prior_scores: dict[str, float] | None = None,
    min_rr: float | None = None,
    top_n: int | None = None,
) -> tuple[list[AssetAnalysis], list[dict[str, str]]]:
    """Filter, score, and rank analyses, returning structural validation errors."""
    if min_rr is None:
        min_rr = float(os.environ.get("ANALYSIS_MIN_RR_RATIO", "3.0"))
    if top_n is None:
        top_n = int(os.environ.get("ANALYSIS_TOP_N", "5"))

    _prior = prior_scores or {}
    scored: list[AssetAnalysis] = []
    errors: list[dict[str, str]] = []
    for asset in analyses:
        valid, reason = validate_asset_analysis(asset)
        if not valid:
            errors.append({
                "ticker": asset.ticker,
                "error_message": f"structural_invalid: {reason}",
            })
            scored.append(_quarantine_invalid_asset(asset))
            continue

        hard_disqualify, stop_viable, atr_pts = _compute_atr_viability(asset)
        if hard_disqualify:
            errors.append({
                "ticker": asset.ticker,
                "error_message": f"atr_disqualify: stop inside ATR noise floor",
            })
            scored.append(_quarantine_invalid_asset(asset).model_copy(update={"stop_viable": False}))
            continue

        s = _compute_score(asset, atr_viability_pts=atr_pts)
        delta = round(s - _prior.get(asset.ticker, s), 2)
        with_score = asset.model_copy(update={"score": s, "score_delta": delta, "stop_viable": stop_viable})
        scored.append(_compute_bet_size(with_score, hit_rate, hit_rate_source))

    # Separate qualifying from non-qualifying
    def qualifies(a: AssetAnalysis) -> bool:
        return (
            a.score is not None
            and a.risk_reward_ratio >= min_rr
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

    return ranked, errors
