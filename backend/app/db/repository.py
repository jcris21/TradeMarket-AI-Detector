"""CRUD operations for all database tables."""

import json
import logging
import uuid
from datetime import datetime, timezone

import aiosqlite

from .connection import get_connection
from .schema import DEFAULT_USER_ID

logger = logging.getLogger(__name__)

FRESHNESS_THRESHOLDS = {"fresh": 2.0, "active": 5.0, "aged": 24.0}


def _compute_phase(conclusive: int) -> tuple[int, str]:
    """Map a conclusive-signal count to a (phase, banner) tuple."""
    if conclusive < 30:
        return 0, f"📊 Fase 0: Calibración — {conclusive}/30 trades resueltos · Métricas disponibles al completar"
    if conclusive < 100:
        return 1, f"📊 Fase 1: Piloto — {conclusive}/100 trades resueltos · Paper trading recomendado"
    if conclusive < 300:
        return 2, f"📊 Fase 2: Evaluación — {conclusive}/300 trades resueltos · Capital real pequeño OK"
    return 3, f"📊 Fase 3: Confianza — {conclusive} trades resueltos · Asignación normal"


def compute_freshness(analyzed_at: str) -> dict:
    """Return freshness_status and freshness_age_hours derived from an ISO UTC timestamp."""
    dt = datetime.fromisoformat(analyzed_at.replace("Z", "+00:00"))
    age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    if age_hours < FRESHNESS_THRESHOLDS["fresh"]:
        status = "fresh"
    elif age_hours < FRESHNESS_THRESHOLDS["active"]:
        status = "active"
    elif age_hours < FRESHNESS_THRESHOLDS["aged"]:
        status = "aged"
    else:
        status = "expired"
    return {"freshness_status": status, "freshness_age_hours": round(age_hours, 2)}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


# --- Users Profile ---


async def get_cash_balance(user_id: str = DEFAULT_USER_ID) -> float:
    """Get the user's cash balance."""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row["cash_balance"] if row else 0.0
    finally:
        await db.close()


async def update_cash_balance(amount: float, user_id: str = DEFAULT_USER_ID) -> float:
    """Set the user's cash balance to the given amount. Returns the new balance."""
    db = await get_connection()
    try:
        await db.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?", (amount, user_id)
        )
        await db.commit()
        return amount
    finally:
        await db.close()


# --- Watchlist ---


async def get_watchlist(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """Get all watchlist tickers for a user."""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT id, ticker, added_at FROM watchlist WHERE user_id = ? ORDER BY added_at",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def add_to_watchlist(ticker: str, user_id: str = DEFAULT_USER_ID) -> dict:
    """Add a ticker to the watchlist. Returns the new entry."""
    ticker = ticker.upper()
    entry = {"id": _uuid(), "user_id": user_id, "ticker": ticker, "added_at": _now()}
    db = await get_connection()
    try:
        await db.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (entry["id"], user_id, ticker, entry["added_at"]),
        )
        await db.commit()
        return entry
    finally:
        await db.close()


async def remove_from_watchlist(ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    """Remove a ticker from the watchlist. Returns True if a row was deleted."""
    ticker = ticker.upper()
    db = await get_connection()
    try:
        cursor = await db.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# --- Positions ---


async def get_positions(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """Get all positions for a user."""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT id, ticker, quantity, avg_cost, updated_at FROM positions "
            "WHERE user_id = ? ORDER BY ticker",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_position(ticker: str, user_id: str = DEFAULT_USER_ID) -> dict | None:
    """Get a single position by ticker."""
    ticker = ticker.upper()
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT id, ticker, quantity, avg_cost, updated_at FROM positions "
            "WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def upsert_position(
    ticker: str, quantity: float, avg_cost: float, user_id: str = DEFAULT_USER_ID
) -> dict:
    """Create or update a position. Returns the position dict."""
    ticker = ticker.upper()
    now = _now()
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT id FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        )
        existing = await cursor.fetchone()

        if existing:
            await db.execute(
                "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? WHERE id = ?",
                (quantity, avg_cost, now, existing["id"]),
            )
            pos_id = existing["id"]
        else:
            pos_id = _uuid()
            await db.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (pos_id, user_id, ticker, quantity, avg_cost, now),
            )

        await db.commit()
        return {
            "id": pos_id,
            "ticker": ticker,
            "quantity": quantity,
            "avg_cost": avg_cost,
            "updated_at": now,
        }
    finally:
        await db.close()


async def delete_position(ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    """Delete a position. Returns True if a row was deleted."""
    ticker = ticker.upper()
    db = await get_connection()
    try:
        cursor = await db.execute(
            "DELETE FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# --- Trades ---


async def insert_trade(
    ticker: str, side: str, quantity: float, price: float, user_id: str = DEFAULT_USER_ID
) -> dict:
    """Record a trade. Returns the trade dict."""
    ticker = ticker.upper()
    trade = {
        "id": _uuid(),
        "user_id": user_id,
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": price,
        "executed_at": _now(),
    }
    db = await get_connection()
    try:
        await db.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trade["id"], user_id, ticker, side, quantity, price, trade["executed_at"]),
        )
        await db.commit()
        return trade
    finally:
        await db.close()


# --- Portfolio Snapshots ---


async def insert_snapshot(total_value: float, user_id: str = DEFAULT_USER_ID) -> dict:
    """Record a portfolio value snapshot."""
    snapshot = {
        "id": _uuid(),
        "user_id": user_id,
        "total_value": total_value,
        "recorded_at": _now(),
    }
    db = await get_connection()
    try:
        await db.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            (snapshot["id"], user_id, total_value, snapshot["recorded_at"]),
        )
        await db.commit()
        return snapshot
    finally:
        await db.close()


async def get_portfolio_history(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """Get portfolio value snapshots ordered by time."""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT id, total_value, recorded_at FROM portfolio_snapshots "
            "WHERE user_id = ? ORDER BY recorded_at",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


# --- Chat Messages ---


async def insert_chat_message(
    role: str, content: str, actions: str | None = None, user_id: str = DEFAULT_USER_ID
) -> dict:
    """Store a chat message. actions is a JSON string or None."""
    msg = {
        "id": _uuid(),
        "user_id": user_id,
        "role": role,
        "content": content,
        "actions": actions,
        "created_at": _now(),
    }
    db = await get_connection()
    try:
        await db.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (msg["id"], user_id, role, content, actions, msg["created_at"]),
        )
        await db.commit()
        return msg
    finally:
        await db.close()


async def get_chat_history(limit: int = 50, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """Get recent chat messages ordered oldest-first."""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT id, role, content, actions, created_at FROM chat_messages "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        # Reverse so oldest is first
        return [dict(row) for row in reversed(rows)]
    finally:
        await db.close()


# --- Analysis Tickers ---


async def get_analysis_tickers(user_id: str = DEFAULT_USER_ID) -> list[str]:
    """Get the list of tickers configured for analysis."""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT ticker FROM analysis_tickers WHERE user_id = ? ORDER BY added_at",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [row["ticker"] for row in rows]
    finally:
        await db.close()


async def add_analysis_ticker(ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    """Add a ticker to the analysis list. Returns True if added, False if already present."""
    ticker = ticker.upper()
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT id FROM analysis_tickers WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        )
        if await cursor.fetchone():
            return False
        await db.execute(
            "INSERT INTO analysis_tickers (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (_uuid(), user_id, ticker, _now()),
        )
        await db.commit()
        return True
    finally:
        await db.close()


async def remove_analysis_ticker(ticker: str, user_id: str = DEFAULT_USER_ID) -> bool:
    """Remove a ticker from the analysis list. Returns True if removed."""
    ticker = ticker.upper()
    db = await get_connection()
    try:
        cursor = await db.execute(
            "DELETE FROM analysis_tickers WHERE user_id = ? AND ticker = ?",
            (user_id, ticker),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# --- Analysis Results ---


async def save_analysis_results(
    rows: list[dict], user_id: str = DEFAULT_USER_ID
) -> list[dict]:
    """Persist a batch of analysis results. Returns per-ticker write errors (if any)."""
    db = await get_connection()
    write_errors: list[dict] = []
    try:
        for row in rows:
            try:
                await db.execute(
                    "INSERT INTO analysis_results "
                    "(id, user_id, run_id, ticker, rank, score, score_delta, signal, confidence, "
                    "risk_reward_ratio, entry_price, target_price, stop_loss, "
                    "support_validated, argument, indicators_summary, screenshot_path, analyzed_at, "
                    "expected_gain_per10, expected_loss_per10, expected_value_per10, "
                    "hit_rate_used, hit_rate_source, stop_viable, atr_14_pct, "
                    "score_quant, score_legacy, enrichment_delta, rank_exclusion_reason) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        _uuid(),
                        user_id,
                        row["run_id"],
                        row["ticker"],
                        row.get("rank"),
                        row.get("score"),
                        row.get("score_delta"),
                        row.get("signal"),
                        row.get("confidence"),
                        row.get("risk_reward_ratio"),
                        row.get("entry_price"),
                        row.get("target_price"),
                        row.get("stop_loss"),
                        1 if row.get("support_validated") else 0,
                        row.get("argument"),
                        row.get("indicators_summary"),
                        row.get("screenshot_path"),
                        _now(),
                        row.get("expected_gain_per10"),
                        row.get("expected_loss_per10"),
                        row.get("expected_value_per10"),
                        row.get("hit_rate_used"),
                        row.get("hit_rate_source"),
                        row.get("stop_viable"),
                        row.get("atr_14_pct"),
                        row.get("score_quant"),
                        row.get("score_legacy"),
                        row.get("enrichment_delta"),
                        row.get("rank_exclusion_reason"),
                    ),
                )
                await db.commit()
            except aiosqlite.Error as e:
                logger.error("DB write failed for %s: %s", row.get("ticker"), e)
                write_errors.append({"ticker": row.get("ticker", "unknown"), "error_message": str(e)})
    finally:
        await db.close()
    return write_errors


async def get_prior_scores(run_id: str, user_id: str = DEFAULT_USER_ID) -> dict[str, float]:
    """Return {ticker: score_quant} from the run immediately before run_id.

    Finds the last completed run whose analyzed_at precedes the current run's
    analyzed_at, then returns score_quant for each ticker in that prior run.
    Returns {} when no prior run exists or on any DB error.
    """
    db = await get_connection()
    try:
        cur = await db.execute(
            "SELECT MIN(analyzed_at) AS run_start FROM analysis_results "
            "WHERE user_id = ? AND run_id = ?",
            (user_id, run_id),
        )
        row = await cur.fetchone()
        if not row or not row["run_start"]:
            return {}
        current_run_start = row["run_start"]

        cur = await db.execute(
            "SELECT run_id FROM analysis_results WHERE user_id = ? AND run_id != ? "
            "GROUP BY run_id HAVING MAX(analyzed_at) < ? "
            "ORDER BY MAX(analyzed_at) DESC LIMIT 1",
            (user_id, run_id, current_run_start),
        )
        prior_row = await cur.fetchone()
        if not prior_row:
            return {}
        prior_run_id = prior_row["run_id"]

        cur = await db.execute(
            "SELECT ticker, score_quant FROM analysis_results "
            "WHERE user_id = ? AND run_id = ?",
            (user_id, prior_run_id),
        )
        rows = await cur.fetchall()
        return {r["ticker"]: r["score_quant"] for r in rows if r["score_quant"] is not None}
    except aiosqlite.OperationalError:
        return {}
    finally:
        await db.close()


async def update_outcome_atomic(
    signal_id: str,
    outcome: str,
    gain_pct: float,
    loss_pct: float,
    hold_days: float,
    support_break_level: str | None = None,
) -> bool:
    """Write outcome for a signal only if outcome IS NULL (atomic guard).

    Returns True if the row was updated, False if already written (idempotent skip).
    """
    db = await get_connection()
    try:
        cursor = await db.execute(
            "UPDATE analysis_results "
            "SET outcome = ?, actual_gain_pct = ?, actual_loss_pct = ?, hold_days = ?, "
            "support_break_level = ? "
            "WHERE id = ? AND outcome IS NULL",
            (outcome, gain_pct, loss_pct, hold_days, support_break_level, signal_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


def _compute_segment_performance(rows: list) -> "dict | None":
    """Compute hit_ratio/profit_factor/realized_rr for a list of resolved outcome rows.

    Returns None when fewer than 30 conclusive signals (TARGET_HIT + STOP_HIT).
    """
    target_hits = sum(1 for r in rows if r["outcome"] == "TARGET_HIT")
    stop_hits = sum(1 for r in rows if r["outcome"] == "STOP_HIT")
    conclusive = target_hits + stop_hits
    if conclusive < 30:
        return None
    total_gain = sum(
        r["actual_gain_pct"] for r in rows
        if r["outcome"] == "TARGET_HIT" and r["actual_gain_pct"] is not None
    )
    total_loss = sum(
        r["actual_loss_pct"] for r in rows
        if r["outcome"] == "STOP_HIT" and r["actual_loss_pct"] is not None
    )
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
    return {
        "total": len(rows),
        "hit_ratio": hit_ratio,
        "profit_factor": profit_factor,
        "realized_rr": realized_rr,
    }


async def get_performance_summary(user_id: str = DEFAULT_USER_ID) -> dict:
    """Compute aggregated outcome metrics from analysis_results."""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT outcome, actual_gain_pct, actual_loss_pct FROM analysis_results "
            "WHERE user_id = ? AND outcome IS NOT NULL",
            (user_id,),
        )
        rows = await cursor.fetchall()
        orphan_cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM analysis_results "
            "WHERE user_id = ? AND outcome IS NULL "
            "AND (julianday('now') - julianday(analyzed_at)) > 35",
            (user_id,),
        )
        orphan_row = await orphan_cursor.fetchone()
        orphaned_count = orphan_row["cnt"] if orphan_row else 0

        # B2 segmentation queries
        b2_cursor = await db.execute(
            "SELECT outcome, actual_gain_pct, actual_loss_pct FROM analysis_results "
            "WHERE user_id = ? AND outcome IS NOT NULL AND enrichment_type = 'auto_screenshot'",
            (user_id,),
        )
        b2_rows = await b2_cursor.fetchall()

        non_b2_cursor = await db.execute(
            "SELECT outcome, actual_gain_pct, actual_loss_pct FROM analysis_results "
            "WHERE user_id = ? AND outcome IS NOT NULL "
            "AND (enrichment_type IS NULL OR enrichment_type != 'auto_screenshot')",
            (user_id,),
        )
        non_b2_rows = await non_b2_cursor.fetchall()
    finally:
        await db.close()

    b2_segment = _compute_segment_performance(b2_rows)
    non_enriched_segment = _compute_segment_performance(non_b2_rows)

    target_hits = sum(1 for r in rows if r["outcome"] == "TARGET_HIT")
    stop_hits = sum(1 for r in rows if r["outcome"] == "STOP_HIT")
    expired = sum(1 for r in rows if r["outcome"] == "EXPIRED")

    conclusive = target_hits + stop_hits
    phase, phase_banner = _compute_phase(conclusive)
    phase_gate_active = phase == 0

    total_gain = sum(
        r["actual_gain_pct"] for r in rows
        if r["outcome"] == "TARGET_HIT" and r["actual_gain_pct"] is not None
    )
    total_loss = sum(
        r["actual_loss_pct"] for r in rows
        if r["outcome"] == "STOP_HIT" and r["actual_loss_pct"] is not None
    )

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

    logger.debug(
        "get_performance_summary: conclusive=%d phase_gate_active=%s",
        conclusive, phase_gate_active,
    )

    return {
        "total_signals": len(rows),
        "target_hits": target_hits,
        "stop_hits": stop_hits,
        "expired": expired,
        "orphaned_count": orphaned_count,
        "phase_gate_active": phase_gate_active,
        "phase": phase,
        "phase_banner": phase_banner,
        "calibration_count": conclusive,
        "hit_ratio": hit_ratio,
        "profit_factor": profit_factor,
        "realized_rr": realized_rr,
        "hr_status": hr_status,
        "pf_status": pf_status,
        "rr_status": rr_status,
        "below_breakeven": below_breakeven,
        "b2_enriched": b2_segment,
        "non_enriched": non_enriched_segment,
    }


def _parse_analysis_row(row) -> dict:
    """Convert a DB analysis_results row to a frontend-compatible dict."""
    d = dict(row)
    raw = d.get("indicators_summary")
    if isinstance(raw, str):
        try:
            d["indicators_summary"] = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            d["indicators_summary"] = {}
    if d.get("analyzed_at"):
        d.update(compute_freshness(d["analyzed_at"]))
    # Parse stop_viable: 1 -> True, 0 -> False, NULL -> None
    sv = d.get("stop_viable")
    if sv is not None:
        d["stop_viable"] = bool(sv)
    # Compute score_enriched = score_quant + enrichment_delta
    sq = d.get("score_quant")
    ed = d.get("enrichment_delta")
    d["score_enriched"] = round(sq + ed, 2) if (sq is not None and ed is not None) else None
    return d


async def get_latest_analysis(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """Return all rows from the most recent analysis run, ordered by rank."""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT run_id FROM analysis_results WHERE user_id = ? "
            "ORDER BY analyzed_at DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return []
        run_id = row["run_id"]

        cursor = await db.execute(
            "SELECT * FROM analysis_results WHERE user_id = ? AND run_id = ? "
            "ORDER BY CASE WHEN rank IS NULL THEN 999 ELSE rank END",
            (user_id, run_id),
        )
        rows = await cursor.fetchall()
        return [_parse_analysis_row(r) for r in rows]
    finally:
        await db.close()


async def get_outcomes_history(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """Return all ranked signals with a resolved outcome, newest first."""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT * FROM analysis_results "
            "WHERE user_id = ? AND outcome IS NOT NULL AND rank IS NOT NULL "
            "ORDER BY analyzed_at DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [_parse_analysis_row(r) for r in rows]
    finally:
        await db.close()


async def update_enrichment_delta(
    ticker: str,
    run_id: str,
    delta: float,
    enrichment_type: str | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> bool:
    """Set enrichment_delta (and optionally enrichment_type) for a ticker within a run."""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "UPDATE analysis_results SET enrichment_delta = ?, enrichment_type = ? "
            "WHERE user_id = ? AND ticker = ? AND run_id = ?",
            (delta, enrichment_type, user_id, ticker.upper(), run_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def get_analysis_by_ticker(
    ticker: str, user_id: str = DEFAULT_USER_ID
) -> dict | None:
    """Return the most recent analysis result for a specific ticker."""
    ticker = ticker.upper()
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT * FROM analysis_results WHERE user_id = ? AND ticker = ? "
            "ORDER BY analyzed_at DESC LIMIT 1",
            (user_id, ticker),
        )
        row = await cursor.fetchone()
        return _parse_analysis_row(row) if row else None
    finally:
        await db.close()


# --- Enrichment Jobs ---


async def create_enrichment_job(
    ticker: str,
    enrichment_type: str,
    source_url: str | None = None,
    status: str = "pending",
    extracted_levels: str | None = None,
) -> str:
    """Insert a new enrichment job row. Returns the UUID id."""
    job_id = _uuid()
    created_at = _now()
    db = await get_connection()
    try:
        await db.execute(
            "INSERT INTO enrichments "
            "(id, ticker, enrichment_type, source_url, status, created_at, extracted_levels) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (job_id, ticker.upper(), enrichment_type, source_url, status, created_at, extracted_levels),
        )
        await db.commit()
        return job_id
    finally:
        await db.close()


async def get_enrichment_job(enrichment_id: str) -> dict | None:
    """Return the enrichment job row as a dict, or None if not found."""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT * FROM enrichments WHERE id = ?", (enrichment_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_enrichment_job(
    enrichment_id: str,
    status: str,
    enrichment_delta: float | None = None,
    error_message: str | None = None,
    completed_at: str | None = None,
) -> None:
    """Update status (and optionally delta/error/completed_at) on an enrichment job."""
    db = await get_connection()
    try:
        await db.execute(
            "UPDATE enrichments SET status = ?, enrichment_delta = ?, "
            "error_message = ?, completed_at = ? WHERE id = ?",
            (status, enrichment_delta, error_message, completed_at, enrichment_id),
        )
        await db.commit()
    finally:
        await db.close()


async def set_ticker_preferred_url(ticker: str, url: str) -> None:
    """Save source_url as preferred_chart_url for a ticker in analysis_tickers."""
    db = await get_connection()
    try:
        await db.execute(
            "UPDATE analysis_tickers SET preferred_chart_url = ? WHERE ticker = ?",
            (url, ticker.upper()),
        )
        await db.commit()
    finally:
        await db.close()


async def reset_stale_enrichments() -> None:
    """Set status='failed' for any pending/processing enrichment jobs on startup."""
    db = await get_connection()
    try:
        await db.execute(
            "UPDATE enrichments SET status = 'failed', error_message = 'server restarted' "
            "WHERE status IN ('pending', 'processing')"
        )
        await db.commit()
    finally:
        await db.close()


async def store_custom_levels(
    ticker: str, levels: list, expires_at: str
) -> None:
    """Persist confirmed S/R levels with TTL in analysis_tickers.custom_levels."""
    levels_json = json.dumps([{"type": lv.type, "price": lv.price} for lv in levels])
    db = await get_connection()
    try:
        await db.execute(
            "UPDATE analysis_tickers SET custom_levels = ?, custom_levels_expires_at = ? "
            "WHERE ticker = ?",
            (levels_json, expires_at, ticker.upper()),
        )
        await db.commit()
    finally:
        await db.close()


async def load_active_custom_levels(ticker: str) -> list:
    """Return confirmed levels for a ticker if not expired; else []."""
    from app.analysis.models import ConfirmedLevel

    now = _now()
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT custom_levels, custom_levels_expires_at FROM analysis_tickers "
            "WHERE ticker = ?",
            (ticker.upper(),),
        )
        row = await cursor.fetchone()
        if not row:
            return []
        raw = row["custom_levels"]
        expires = row["custom_levels_expires_at"]
        if not raw or not expires or expires < now:
            return []
        items = json.loads(raw)
        return [ConfirmedLevel(type=i["type"], price=i["price"]) for i in items]
    finally:
        await db.close()


async def expire_stale_levels() -> None:
    """NULL custom_levels and expires_at for all tickers past their TTL."""
    now = _now()
    db = await get_connection()
    try:
        await db.execute(
            "UPDATE analysis_tickers "
            "SET custom_levels = NULL, custom_levels_expires_at = NULL "
            "WHERE custom_levels_expires_at IS NOT NULL AND custom_levels_expires_at < ?",
            (now,),
        )
        await db.commit()
    finally:
        await db.close()


async def update_analysis_result_custom_levels(
    ticker: str,
    custom_levels_applied: int,
    enrichment_delta: float,
    user_id: str = DEFAULT_USER_ID,
) -> bool:
    """Update custom_levels_applied and enrichment_delta on the latest analysis row."""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "UPDATE analysis_results SET custom_levels_applied = ?, enrichment_delta = ? "
            "WHERE user_id = ? AND ticker = ? AND id = ("
            "  SELECT id FROM analysis_results WHERE user_id = ? AND ticker = ? "
            "  ORDER BY analyzed_at DESC LIMIT 1"
            ")",
            (custom_levels_applied, enrichment_delta, user_id, ticker.upper(), user_id, ticker.upper()),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def set_analysis_enrichment_status(
    ticker: str,
    status: str,
    enrichment_delta: float | None = None,
    enrichment_type: str | None = None,
    argument: str | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> None:
    """Update enrichment_status and optionally enrichment_delta/enrichment_type/argument."""
    set_clauses = ["enrichment_status = ?"]
    params: list = [status]
    if enrichment_delta is not None:
        set_clauses.append("enrichment_delta = ?")
        params.append(enrichment_delta)
    if enrichment_type is not None:
        set_clauses.append("enrichment_type = ?")
        params.append(enrichment_type)
    if argument is not None:
        set_clauses.append("argument = ?")
        params.append(argument)
    set_sql = ", ".join(set_clauses)
    subquery = (
        "SELECT id FROM analysis_results WHERE user_id = ? AND ticker = ? "
        "ORDER BY analyzed_at DESC LIMIT 1"
    )
    params += [user_id, ticker.upper(), user_id, ticker.upper()]
    db = await get_connection()
    try:
        await db.execute(
            f"UPDATE analysis_results SET {set_sql} "
            f"WHERE user_id = ? AND ticker = ? AND id = ({subquery})",
            params,
        )
        await db.commit()
    finally:
        await db.close()


async def find_pending_enrichment_job(ticker: str) -> dict | None:
    """Return an in-flight enrichment job for ticker (pending or processing), or None."""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT id, enrichment_type, status FROM enrichments "
            "WHERE ticker = ? AND enrichment_type IN ('auto_screenshot', 'screenshot') "
            "AND status IN ('pending', 'processing') "
            "ORDER BY created_at DESC LIMIT 1",
            (ticker.upper(),),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()

