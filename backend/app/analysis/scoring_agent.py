"""ScoringAgent — filter, score, and rank asset analyses."""

import os
from typing import List

import aiosqlite

from .models import AssetAnalysis, ConfirmedLevel

# Sectors that bypass the per-sector cap (index proxies / unclassified)
_BYPASS_SECTORS: frozenset[str] = frozenset({"unknown", "etf"})

ENRICHMENT_MAX_DELTA = float(os.environ.get("ENRICHMENT_MAX_DELTA", "15.0"))

# ATR viability constants
_ATR_HARD_FLOOR = 0.5
_ATR_BOOST_THRESHOLD = 1.5
_ATR_PENALTY_PTS = -15.0
_ATR_BOOST_PTS = 8.0


def _atr_floor_factor() -> float:
    """Return the ATR soft-penalty floor factor from env var, default 0.8."""
    return float(os.environ.get("ANALYSIS_ATR_FLOOR", "0.8"))


def _sector_cap() -> int:
    """Return the per-sector cap from ANALYSIS_SECTOR_CAP (clamped to [1, 5], default 2)."""
    try:
        cap = int(os.environ.get("ANALYSIS_SECTOR_CAP", "2"))
    except ValueError:
        return 2
    return max(1, min(5, cap))


def _apply_sector_cap(
    qualifying: list[AssetAnalysis], cap: int
) -> tuple[list[AssetAnalysis], list[AssetAnalysis], dict[str, int]]:
    """Greedily enforce a per-sector cap over score-sorted qualifying assets.

    Assumes `qualifying` is already sorted by score_quant descending. Sectors in
    `_BYPASS_SECTORS` (and empty/None sectors, which map to "unknown") are never capped.
    Excluded assets get rank=None and rank_exclusion_reason="sector_cap:<sector>".

    Returns (accepted, excluded, exclusion_counts).
    """
    accepted: list[AssetAnalysis] = []
    excluded: list[AssetAnalysis] = []
    exclusion_counts: dict[str, int] = {}
    sector_counts: dict[str, int] = {}

    for asset in qualifying:
        sector = (asset.sector or "unknown").strip()
        normalized = sector.lower()
        if normalized in _BYPASS_SECTORS:
            accepted.append(asset)
            continue
        count = sector_counts.get(normalized, 0)
        if count >= cap:
            excluded.append(
                asset.model_copy(update={
                    "rank": None,
                    "rank_exclusion_reason": f"sector_cap:{sector}",
                })
            )
            exclusion_counts[sector] = exclusion_counts.get(sector, 0) + 1
        else:
            sector_counts[normalized] = count + 1
            accepted.append(asset)

    return accepted, excluded, exclusion_counts


def _compute_atr_viability(asset: AssetAnalysis) -> tuple[bool, bool, float]:
    """Compute ATR stop viability.

    Returns (hard_disqualify, stop_viable, atr_viability_pts).
    """
    if asset.atr_14_pct is None:
        # ATR unavailable — pass through, no penalty
        return False, True, 0.0

    if asset.entry_price <= 0:
        return False, True, 0.0

    stop_distance_pct = (asset.entry_price - asset.stop_loss) / asset.entry_price
    atr = asset.atr_14_pct
    floor_factor = _atr_floor_factor()

    hard_floor = _ATR_HARD_FLOOR * atr
    soft_floor = floor_factor * atr
    boost_threshold = _ATR_BOOST_THRESHOLD * atr

    if stop_distance_pct < hard_floor:
        # Hard disqualify: stop inside ATR noise floor
        return True, False, 0.0

    if stop_distance_pct < soft_floor:
        # Soft penalty band
        return False, False, _ATR_PENALTY_PTS

    if stop_distance_pct > boost_threshold:
        # Boost band: well-placed stop
        return False, True, _ATR_BOOST_PTS

    # Neutral band
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
        "score_quant": None,
        "score_legacy": None,
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


def _compute_score_legacy(asset: AssetAnalysis, atr_viability_pts: float = 0.0) -> float:
    """Legacy LLM-confidence composite score 0–100 (kept for comparison)."""
    confidence_component = asset.confidence * 40
    rr_normalized = min(asset.risk_reward_ratio / 6.0, 1.0) * 100
    rr_component = rr_normalized * 0.35
    confluence = _indicator_confluence_score(asset.indicators_summary)
    confluence_component = confluence * 0.25
    raw = confidence_component + rr_component + confluence_component + atr_viability_pts
    return round(max(0.0, min(100.0, raw)), 2)


def _compute_score_quant(asset: AssetAnalysis, atr_viability_pts: float = 0.0) -> float:
    """Pure quantitative score 0–100 — no LLM confidence.

    Components:
      RR           0/14/22/30 pts  (thresholds: ≥2 / ≥3 / ≥4)
      Confluence   0–20 pts        (bullish indicator count)
      Trend        0/3/6/10 pts    (SMA-50 position + MACD signal)
      ATR          -15/0/+8 pts    (pre-computed by _compute_atr_viability)
      BB squeeze   0/+8 pts        (BBB < 10 signals pending breakout)
      Support      0/5/10 pts      (validated + price proximity)
      Resistance   -5/0/+8 pts     (room above current price)
      Regime       -10/-5/0/+5 pts (RSI zone)
    """
    summary = asset.indicators_summary
    current_price = float(summary.get("current_price", asset.entry_price) or asset.entry_price)

    # RR component (0–30 pts)
    rr = asset.risk_reward_ratio
    if rr >= 4.0:
        rr_pts = 30.0
    elif rr >= 3.0:
        rr_pts = 22.0
    elif rr >= 2.0:
        rr_pts = 14.0
    else:
        rr_pts = 0.0

    # Confluence component (0–20 pts)
    conf_pts = _indicator_confluence_score(summary) * 0.20

    # Trend alignment (0/3/6/10 pts)
    macd = summary.get("macd", "neutral")
    sma_50_raw = summary.get("sma_50")
    above_sma50 = (
        sma_50_raw is not None
        and current_price > 0
        and current_price > float(sma_50_raw)
    )
    macd_bullish = macd == "bullish_crossover"
    macd_bearish = macd == "bearish_crossover"

    if above_sma50 and macd_bullish:
        trend_pts = 10.0
    elif above_sma50 or macd_bullish:
        trend_pts = 6.0
    elif not macd_bearish:
        trend_pts = 3.0
    else:
        trend_pts = 0.0

    # BB squeeze (0/+8 pts) — low bandwidth = pending breakout
    bb_bw = summary.get("bb_bandwidth")
    bb_pts = 8.0 if (bb_bw is not None and float(bb_bw) < 10.0) else 0.0

    # Quant support (0/5/10 pts)
    if asset.support_validated:
        s1_raw = summary.get("support_1")
        if s1_raw is not None and current_price > 0:
            proximity = (current_price - float(s1_raw)) / current_price
            support_pts = 10.0 if proximity < 0.03 else 5.0
        else:
            support_pts = 5.0
    else:
        support_pts = 0.0

    # Quant resistance (-5/0/+8 pts)
    r1_raw = summary.get("resistance_1")
    if r1_raw is not None and current_price > 0:
        dist = (float(r1_raw) - current_price) / current_price
        if dist > 0.05:
            resistance_pts = 8.0
        elif dist > 0.01:
            resistance_pts = 0.0
        else:
            resistance_pts = -5.0
    else:
        resistance_pts = 0.0

    # Regime adjustment (-10/-5/0/+5 pts)
    rsi = summary.get("rsi", 50.0)
    if isinstance(rsi, (int, float)):
        if rsi > 70:
            regime_pts = -10.0
        elif rsi > 60:
            regime_pts = -5.0
        elif 30 <= rsi < 50:
            regime_pts = 5.0
        else:
            regime_pts = 0.0
    else:
        regime_pts = 0.0

    raw = (
        rr_pts + conf_pts + trend_pts + atr_viability_pts
        + bb_pts + support_pts + resistance_pts + regime_pts
    )
    return round(max(0.0, min(100.0, raw)), 2)


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
            "SELECT ticker, COALESCE(score_quant, score) AS score FROM analysis_results "
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


def _apply_custom_levels(
    entry_price: float,
    target_price: float,
    atr_14: float,
    confirmed_levels: List[ConfirmedLevel],
) -> tuple[float, int]:
    """Compute enrichment_delta from trader-confirmed S/R levels.

    Scoring rules (max 2 levels evaluated):
      +4 pts for support within 1 ATR of entry_price
      +3 pts for resistance within 2% of target_price
    Result is clamped to [0, ENRICHMENT_MAX_DELTA].

    Returns (enrichment_delta, applied_count).
    """
    delta = 0.0
    applied = 0

    for level in confirmed_levels[:2]:
        if level.type == "support":
            if abs(level.price - entry_price) <= atr_14:
                delta += 4.0
                applied += 1
        elif level.type == "resistance":
            if target_price > 0 and abs(level.price - target_price) / target_price <= 0.02:
                delta += 3.0
                applied += 1

    delta = round(max(0.0, min(ENRICHMENT_MAX_DELTA, delta)), 2)
    return delta, applied


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
    ranked, _errors, _exclusions = score_and_rank_with_errors(
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
) -> tuple[list[AssetAnalysis], list[dict[str, str]], dict[str, int]]:
    """Filter, score, and rank analyses, returning structural validation errors.

    Returns (ranked_all, structural_errors, sector_cap_exclusions).
    """
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

        # ATR viability gate
        hard_disqualify, stop_viable, atr_pts = _compute_atr_viability(asset)
        if hard_disqualify:
            errors.append({
                "ticker": asset.ticker,
                "error_message": "atr_disqualify: stop inside ATR noise floor",
            })
            quarantined = _quarantine_invalid_asset(asset)
            scored.append(quarantined.model_copy(update={"stop_viable": False}))
            continue

        sq = _compute_score_quant(asset, atr_viability_pts=atr_pts)
        sl = _compute_score_legacy(asset, atr_viability_pts=atr_pts)
        prior_sq = _prior.get(asset.ticker)
        delta = round(sq - prior_sq, 2) if prior_sq is not None else 0.0
        # stop_viable=None means ATR data was unavailable (pass-through)
        actual_stop_viable = stop_viable if asset.atr_14_pct is not None else None
        with_score = asset.model_copy(update={
            "score": sq,          # backward compat — UI reads this field
            "score_quant": sq,
            "score_legacy": sl,
            "score_delta": delta,
            "stop_viable": actual_stop_viable,
        })
        scored.append(_compute_bet_size(with_score, hit_rate, hit_rate_source))

    # Separate qualifying from non-qualifying
    def qualifies(a: AssetAnalysis) -> bool:
        return (
            a.score_quant is not None
            and a.risk_reward_ratio >= min_rr
            and a.signal in ("BUY", "WAIT")
        )

    qualifying = [a for a in scored if qualifies(a)]
    not_qualifying = [a for a in scored if not qualifies(a)]

    qualifying.sort(key=lambda a: a.score_quant or 0, reverse=True)

    accepted, cap_excluded, sector_cap_exclusions = _apply_sector_cap(qualifying, _sector_cap())
    not_qualifying.extend(cap_excluded)
    accepted = accepted[:top_n]

    ranked: list[AssetAnalysis] = []
    for i, asset in enumerate(accepted, start=1):
        ranked.append(asset.model_copy(update={"rank": i}))

    for asset in not_qualifying:
        ranked.append(asset.model_copy(update={"rank": None}))

    return ranked, errors, sector_cap_exclusions

