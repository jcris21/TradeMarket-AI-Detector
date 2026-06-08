"""OutcomeDetector — atomically resolves trade signal outcomes."""

import asyncio
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone

import yfinance as yf

from app.db import get_connection, update_outcome_atomic
from app.db.repository import _compute_phase

logger = logging.getLogger(__name__)

OUTCOME_TARGET_HIT = "TARGET_HIT"
OUTCOME_STOP_HIT = "STOP_HIT"
OUTCOME_EXPIRED = "EXPIRED"


@dataclass
class PerformanceSummary:
    total_signals: int
    target_hits: int
    stop_hits: int
    expired: int
    orphaned_count: int
    phase_gate_active: bool
    calibration_count: int
    hit_ratio: float | None
    profit_factor: float | None
    realized_rr: float | None
    hr_status: str | None
    pf_status: str | None
    rr_status: str | None
    below_breakeven: bool
    phase: int = 0
    phase_banner: str = ""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PerformanceSummary):
            return NotImplemented
        return (
            self.total_signals == other.total_signals
            and self.target_hits == other.target_hits
            and self.stop_hits == other.stop_hits
            and self.expired == other.expired
            and self.orphaned_count == other.orphaned_count
            and self.phase_gate_active == other.phase_gate_active
            and self.calibration_count == other.calibration_count
            and self.hit_ratio == other.hit_ratio
            and self.profit_factor == other.profit_factor
            and self.realized_rr == other.realized_rr
            and self.hr_status == other.hr_status
            and self.pf_status == other.pf_status
            and self.rr_status == other.rr_status
            and self.below_breakeven == other.below_breakeven
        )


async def _fetch_price_range_since(
    ticker: str, since_dt: datetime
) -> tuple[float | None, float | None, int]:
    """Return (max_high, min_low, hold_days) for a ticker since since_dt.

    Returns (None, None, 0) when no price data is available.
    """
    since_date = since_dt.date()
    today = datetime.now(timezone.utc).date()
    hold_days = (today - since_date).days

    if hold_days <= 0:
        return None, None, 0

    try:
        df = await asyncio.to_thread(
            yf.download,
            ticker,
            start=since_date.isoformat(),
            end=today.isoformat(),
            progress=False,
            auto_adjust=True,
        )
    except Exception as exc:
        logger.warning("yfinance fetch failed for %s: %s", ticker, exc)
        return None, None, 0

    if df is None or df.empty:
        return None, None, 0

    try:
        max_high = float(df["High"].max())
        min_low = float(df["Low"].min())
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Price column extraction failed for %s: %s", ticker, exc)
        return None, None, 0

    return max_high, min_low, hold_days


def _determine_outcome(
    max_high: float,
    min_low: float,
    entry_price: float,
    target_price: float,
    stop_loss: float,
) -> tuple[str, float, float]:
    """Classify outcome and compute actual gain/loss percentages.

    When both target and stop are triggered in the same window, the level
    closer to entry_price is assumed to have been reached first.
    """
    target_hit = max_high >= target_price
    stop_hit = min_low <= stop_loss

    if target_hit and stop_hit:
        target_dist = abs(target_price - entry_price)
        stop_dist = abs(stop_loss - entry_price)
        outcome = OUTCOME_TARGET_HIT if target_dist <= stop_dist else OUTCOME_STOP_HIT
    elif target_hit:
        outcome = OUTCOME_TARGET_HIT
    elif stop_hit:
        outcome = OUTCOME_STOP_HIT
    else:
        outcome = OUTCOME_EXPIRED

    gain_pct = (max_high - entry_price) / entry_price * 100
    loss_pct = (entry_price - min_low) / entry_price * 100

    return outcome, round(gain_pct, 4), round(loss_pct, 4)


class OutcomeDetector:
    """Resolves outcomes for analysis_results rows where outcome IS NULL.

    Uses an atomic UPDATE … WHERE outcome IS NULL guard so that concurrent
    or restarted runs never double-write an outcome.
    """

    async def _get_unresolved_signals(self) -> list[dict]:
        db = await get_connection()
        try:
            cursor = await db.execute(
                "SELECT id, ticker, entry_price, target_price, stop_loss, analyzed_at "
                "FROM analysis_results WHERE outcome IS NULL ORDER BY analyzed_at"
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            await db.close()

    async def run(self) -> PerformanceSummary:
        """Process all unresolved signals and return a PerformanceSummary."""
        signals = await self._get_unresolved_signals()
        logger.info("OutcomeDetector: %d unresolved signals to process", len(signals))

        written = 0
        skipped = 0

        for signal in signals:
            signal_id = signal["id"]
            ticker = signal["ticker"]
            entry_price = signal["entry_price"]
            target_price = signal["target_price"]
            stop_loss = signal["stop_loss"]
            analyzed_at_str = signal["analyzed_at"]

            try:
                analyzed_dt = datetime.fromisoformat(
                    analyzed_at_str.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                logger.warning(
                    "Invalid analyzed_at for signal %s (%s) — skipping",
                    signal_id, ticker,
                )
                continue

            max_high, min_low, hold_days = await _fetch_price_range_since(
                ticker, analyzed_dt
            )

            if max_high is None or min_low is None:
                logger.warning(
                    "No price data for signal %s (%s) since %s — skipping",
                    signal_id, ticker, analyzed_at_str,
                )
                continue

            outcome, gain_pct, loss_pct = _determine_outcome(
                max_high, min_low, entry_price, target_price, stop_loss
            )

            if not math.isfinite(gain_pct):
                logger.warning(
                    "actual_gain_pct is not finite for signal %s (%s) — skipping",
                    signal_id, ticker,
                )
                continue

            sbl = "S1" if outcome == OUTCOME_STOP_HIT else None
            updated = await update_outcome_atomic(
                signal_id, outcome, gain_pct, loss_pct, float(hold_days),
                support_break_level=sbl,
            )

            if updated:
                written += 1
                logger.debug(
                    "Outcome written for signal %s (%s): %s", signal_id, ticker, outcome
                )
            else:
                skipped += 1
                logger.info(
                    "Outcome already written for signal %s (%s) — skipping (idempotent)",
                    signal_id,
                    ticker,
                )

        logger.info(
            "OutcomeDetector complete: %d written, %d skipped", written, skipped
        )
        return await self._compute_summary()

    async def _compute_summary(self) -> PerformanceSummary:
        db = await get_connection()
        try:
            cursor = await db.execute(
                "SELECT outcome, actual_gain_pct, actual_loss_pct "
                "FROM analysis_results WHERE outcome IS NOT NULL"
            )
            rows = await cursor.fetchall()
            orphan_cursor = await db.execute(
                "SELECT COUNT(*) as cnt FROM analysis_results "
                "WHERE outcome IS NULL "
                "AND (julianday('now') - julianday(analyzed_at)) > 35"
            )
            orphan_row = await orphan_cursor.fetchone()
            orphaned_count = orphan_row["cnt"] if orphan_row else 0
        finally:
            await db.close()

        total = len(rows)
        target_hits = sum(1 for r in rows if r["outcome"] == OUTCOME_TARGET_HIT)
        stop_hits = sum(1 for r in rows if r["outcome"] == OUTCOME_STOP_HIT)
        expired = sum(1 for r in rows if r["outcome"] == OUTCOME_EXPIRED)

        conclusive = target_hits + stop_hits
        phase, phase_banner = _compute_phase(conclusive)
        phase_gate_active = phase == 0

        gains = [
            r["actual_gain_pct"]
            for r in rows
            if r["outcome"] == OUTCOME_TARGET_HIT and r["actual_gain_pct"] is not None
        ]
        losses = [
            r["actual_loss_pct"]
            for r in rows
            if r["outcome"] == OUTCOME_STOP_HIT and r["actual_loss_pct"] is not None
        ]
        total_gain = sum(gains)
        total_loss = sum(losses)

        if phase_gate_active:
            hit_ratio: float | None = None
            profit_factor: float | None = None
            realized_rr: float | None = None
            hr_status: str | None = None
            pf_status: str | None = None
            rr_status: str | None = None
            below_breakeven = False
        else:
            hit_ratio = round(target_hits / conclusive, 4)
            if total_loss > 0:
                profit_factor = round(total_gain / total_loss, 4)
            elif total_gain > 0:
                profit_factor = 999.0
            else:
                profit_factor = 0.0
            avg_gain = total_gain / target_hits if target_hits > 0 else 0.0
            avg_loss = total_loss / stop_hits if stop_hits > 0 else 0.0
            realized_rr = round(avg_gain / avg_loss, 2) if avg_loss > 0 else None
            if hit_ratio >= 0.35:
                hr_status = "green"
            elif hit_ratio < 0.25:
                hr_status = "red"
            else:
                hr_status = "neutral"
            if profit_factor >= 1.3:
                pf_status = "green"
            elif profit_factor < 1.0:
                pf_status = "red"
            else:
                pf_status = None
            rr_status = "green" if realized_rr is not None and realized_rr >= 2.1 else None
            below_breakeven = hit_ratio < 0.25

        return PerformanceSummary(
            total_signals=total,
            target_hits=target_hits,
            stop_hits=stop_hits,
            expired=expired,
            orphaned_count=orphaned_count,
            phase_gate_active=phase_gate_active,
            phase=phase,
            phase_banner=phase_banner,
            calibration_count=conclusive,
            hit_ratio=hit_ratio,
            profit_factor=profit_factor,
            realized_rr=realized_rr,
            hr_status=hr_status,
            pf_status=pf_status,
            rr_status=rr_status,
            below_breakeven=below_breakeven,
        )
