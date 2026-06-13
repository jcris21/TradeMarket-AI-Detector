"""Database connection management with lazy initialization."""

import json
import os
import uuid
from datetime import datetime, timezone

import aiosqlite

from .schema import DEFAULT_CASH_BALANCE, DEFAULT_TICKERS, DEFAULT_USER_ID, SCHEMA_SQL

# ── Mock analysis seed ────────────────────────────────────────────────────────
# GOOGL: confidence=0.88, rr=4.8, 3/3 indicators → score 88.20 (Rank 1)
# AMZN:  confidence=0.74, rr=3.3, 2/3 indicators → score 65.52 (Rank 2)
# Scores verified against scoring_agent._compute_score() formula:
#   score = confidence×40 + min(rr/6,1)×100×0.35 + confluence×0.25
# Signals for the "current" run (analyzed_at = now for GOOGL/AMZN,
# analyzed_at = 38 days ago for AAPL so it triggers the ⚠ Orphaned badge).
#
# ATR badge showcase (3 states):
#   GOOGL: atr_14_pct=2.0%, stop_distance=3.53% > boost threshold (1.5×2%)=3.0% → ✔ ATR
#   AMZN:  atr_14_pct=5.5%, stop_distance=3.89% < soft_floor (0.8×5.5%)=4.4%   → ❌ ATR
#   AAPL:  atr_14_pct=None (no ATR data)                                         → —
_MOCK_ANALYSIS_SEED = [
    {
        "ticker": "GOOGL",
        "rank": 1,
        "score": 88.2,
        "signal": "BUY",
        "confidence": 0.88,
        "risk_reward_ratio": 4.8,
        "entry_price": 178.50,
        "target_price": 208.54,
        "stop_loss": 172.20,
        "support_validated": 1,
        "argument": (
            "GOOGL muestra un cruce alcista de MACD con histograma positivo creciente, "
            "RSI en zona de sobreventa técnica (44.2) con espacio para subida, y volumen "
            "1.45× sobre la media — confluencia de 3/3 indicadores. El soporte S1 en "
            "$172.20 está validado visualmente en el gráfico. Ratio riesgo/beneficio de "
            "4.8:1 desde entrada $178.50 hasta resistencia $208.54."
        ),
        "indicators_summary": json.dumps({
            "macd": "bullish_crossover",
            "rsi": 44.2,
            "volume": 1.45,
            "macd_histogram": 0.82,
            "support_1": 172.20,
            "resistance_1": 208.54,
        }),
        "expected_gain_per10": 1.68,
        "expected_loss_per10": 0.35,
        "expected_value_per10": round(0.35 * 1.68 - 0.65 * 0.35, 2),
        "hit_rate_used": 0.35,
        "hit_rate_source": "assumed",
        "analyzed_at_days_ago": 0,
        "atr_14_pct": 0.020,  # stop 3.53% > boost threshold 3.0% → ✔ ATR
        "stop_viable": 1,
    },
    {
        "ticker": "AMZN",
        "rank": 2,
        "score": 65.52,
        "signal": "BUY",
        "confidence": 0.74,
        "risk_reward_ratio": 3.3,
        "entry_price": 198.20,
        "target_price": 223.61,
        "stop_loss": 190.50,
        "support_validated": 1,
        "argument": (
            "AMZN presenta cruce alcista de MACD y RSI neutral-positivo (52.1), pero el "
            "volumen está por debajo de la media (0.98×) lo que reduce la convicción "
            "— confluencia parcial 2/3. Soporte S1 en $190.50 identificado en los últimos "
            "20 períodos. Ratio riesgo/beneficio de 3.3:1, por encima del mínimo requerido "
            "pero inferior a GOOGL."
        ),
        "indicators_summary": json.dumps({
            "macd": "bullish_crossover",
            "rsi": 52.1,
            "volume": 0.98,
            "macd_histogram": 0.41,
            "support_1": 190.50,
            "resistance_1": 223.61,
        }),
        "expected_gain_per10": 1.28,
        "expected_loss_per10": 0.39,
        "expected_value_per10": round(0.35 * 1.28 - 0.65 * 0.39, 2),
        "hit_rate_used": 0.35,
        "hit_rate_source": "assumed",
        "analyzed_at_days_ago": 0,
        "atr_14_pct": 0.055,  # stop 3.89% < soft_floor 4.4% → ❌ ATR (penalty band)
        "stop_viable": 0,
    },
    # AAPL: same run, but analyzed 38 days ago with no outcome → ⚠ Orphaned badge
    {
        "ticker": "AAPL",
        "rank": 3,
        "score": 71.80,
        "signal": "BUY",
        "confidence": 0.78,
        "risk_reward_ratio": 3.5,
        "entry_price": 172.40,
        "target_price": 195.80,
        "stop_loss": 165.50,
        "support_validated": 1,
        "argument": (
            "AAPL presenta RSI en 41.3 con divergencia alcista en timeframe diario y "
            "MACD cerca del cruce positivo — confluencia 2/3. El soporte S1 en $165.50 "
            "ha sido testado 3 veces sin ruptura. Ratio riesgo/beneficio de 3.5:1. "
            "⚠ Sin confirmación de outcome tras 38 días — revisar manualmente."
        ),
        "indicators_summary": json.dumps({
            "macd": "near_crossover",
            "rsi": 41.3,
            "volume": 1.12,
            "macd_histogram": 0.15,
            "support_1": 165.50,
            "resistance_1": 195.80,
        }),
        "expected_gain_per10": 1.36,
        "expected_loss_per10": 0.40,
        "expected_value_per10": round(0.35 * 1.36 - 0.65 * 0.40, 2),
        "hit_rate_used": 0.35,
        "hit_rate_source": "assumed",
        "analyzed_at_days_ago": 38,  # triggers Orphaned badge (> 35 days, outcome=NULL)
        "atr_14_pct": None,   # no ATR data → —
        "stop_viable": None,
    },
]

# Historical resolved outcomes seeded in a separate older run.
# These populate GET /api/analysis/performance with real metrics:
#   target_hits=1, stop_hits=1, expired=1
#   hit_ratio = 1/(1+1) = 0.50
#   profit_factor = 20.0 / 9.17 ≈ 2.18
_MOCK_RESOLVED_SEED = [
    {
        "ticker": "TSLA",
        "rank": 1,
        "score": 82.40,
        "signal": "BUY",
        "confidence": 0.84,
        "risk_reward_ratio": 4.2,
        "entry_price": 215.60,
        "target_price": 258.72,
        "stop_loss": 205.20,
        "support_validated": 1,
        "argument": "TSLA: cruce MACD alcista + RSI 38.4 en soporte — TARGET alcanzado.",
        "indicators_summary": json.dumps({"macd": "bullish_crossover", "rsi": 38.4, "volume": 1.62}),
        "expected_gain_per10": 2.00,
        "expected_loss_per10": 0.48,
        "expected_value_per10": round(0.35 * 2.00 - 0.65 * 0.48, 2),
        "hit_rate_used": 0.35,
        "hit_rate_source": "assumed",
        "analyzed_at_days_ago": 60,
        "outcome": "TARGET_HIT",
        "actual_gain_pct": 20.0,   # (258.72 - 215.60) / 215.60 * 100
        "actual_loss_pct": 3.8,
        "hold_days": 45.0,
        "support_break_level": None,
    },
    {
        "ticker": "NVDA",
        "rank": 2,
        "score": 69.30,
        "signal": "BUY",
        "confidence": 0.72,
        "risk_reward_ratio": 3.1,
        "entry_price": 118.40,
        "target_price": 137.34,
        "stop_loss": 112.20,
        "support_validated": 1,
        "argument": "NVDA: MACD alcista pero volumen débil — STOP alcanzado en S1.",
        "indicators_summary": json.dumps({"macd": "bullish_crossover", "rsi": 55.1, "volume": 0.91}),
        "expected_gain_per10": 1.60,
        "expected_loss_per10": 0.52,
        "expected_value_per10": round(0.35 * 1.60 - 0.65 * 0.52, 2),
        "hit_rate_used": 0.35,
        "hit_rate_source": "assumed",
        "analyzed_at_days_ago": 60,
        "outcome": "STOP_HIT",
        "actual_gain_pct": 5.2,
        "actual_loss_pct": 9.17,   # (118.40 - 107.54) / 118.40 * 100
        "hold_days": 30.0,
        "support_break_level": "S1",
    },
    {
        "ticker": "MSFT",
        "rank": 3,
        "score": 58.10,
        "signal": "BUY",
        "confidence": 0.65,
        "risk_reward_ratio": 3.0,
        "entry_price": 415.20,
        "target_price": 466.80,
        "stop_loss": 398.00,
        "support_validated": 0,
        "argument": "MSFT: señal débil — precio lateral durante 42 días, EXPIRADO.",
        "indicators_summary": json.dumps({"macd": "neutral", "rsi": 49.8, "volume": 0.85}),
        "expected_gain_per10": 1.24,
        "expected_loss_per10": 0.41,
        "expected_value_per10": round(0.35 * 1.24 - 0.65 * 0.41, 2),
        "hit_rate_used": 0.35,
        "hit_rate_source": "assumed",
        "analyzed_at_days_ago": 60,
        "outcome": "EXPIRED",
        "actual_gain_pct": 1.8,
        "actual_loss_pct": 1.2,
        "hold_days": 42.0,
        "support_break_level": None,
    },
]

_DB_PATH: str | None = None


def get_db_path() -> str:
    """Return the configured database path."""
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = os.environ.get(
            "FINALLY_DB_PATH",
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "db", "finally.db"),
        )
    return _DB_PATH


def set_db_path(path: str) -> None:
    """Override the database path (for testing)."""
    global _DB_PATH
    _DB_PATH = path


async def get_connection() -> aiosqlite.Connection:
    """Open a connection to the database."""
    db = await aiosqlite.connect(get_db_path())
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


_BET_SIZE_COLUMNS = [
    ("expected_gain_per10", "REAL"),
    ("expected_loss_per10", "REAL"),
    ("expected_value_per10", "REAL"),
    ("hit_rate_used", "REAL"),
    ("hit_rate_source", "TEXT"),
    ("score_delta", "REAL"),
]

_OUTCOME_COLUMNS = [
    ("outcome", "TEXT"),
    ("actual_gain_pct", "REAL"),
    ("actual_loss_pct", "REAL"),
    ("hold_days", "REAL"),
]

_ATR_COLUMNS = [
    ("stop_viable", "INTEGER"),
    ("atr_14_pct", "REAL"),
]

_ANALYSIS_TICKERS_COLUMNS = [
    ("sector", "TEXT"),
    ("sub_sector", "TEXT"),
    ("seed_version", "TEXT"),
]


async def init_db() -> None:
    """Create tables and seed default data if needed."""
    # Lazy import avoids circular dependency: app.analysis -> outcome_detector -> app.db
    from app.analysis.seed_tickers import LEGACY_TICKERS, SEED_TICKERS, SEED_VERSION
    from datetime import timedelta
    db = await get_connection()
    try:
        await db.executescript(SCHEMA_SQL)

        # Lazy migration: add columns if not already present
        for col, col_type in _BET_SIZE_COLUMNS + _OUTCOME_COLUMNS + _ATR_COLUMNS:
            try:
                await db.execute(
                    f"ALTER TABLE analysis_results ADD COLUMN {col} {col_type}"
                )
            except aiosqlite.OperationalError as e:
                if "duplicate column name" not in str(e):
                    raise

        # Create outcome index after column migration (safe to run multiple times)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_analysis_outcome ON analysis_results(outcome)"
        )

        # Lazy migration: add sector/sub_sector/seed_version to analysis_tickers
        for col, col_type in _ANALYSIS_TICKERS_COLUMNS:
            try:
                await db.execute(
                    f"ALTER TABLE analysis_tickers ADD COLUMN {col} {col_type}"
                )
            except aiosqlite.OperationalError as e:
                if "duplicate column name" not in str(e):
                    raise

        # Upgrade-seed: 3-path logic to keep analysis_tickers at 100-ticker universe
        cursor = await db.execute(
            "SELECT ticker FROM analysis_tickers WHERE user_id = ?", (DEFAULT_USER_ID,)
        )
        rows = await cursor.fetchall()
        existing = frozenset(row[0] for row in rows)
        seed_now = datetime.now(timezone.utc).isoformat()

        if existing == LEGACY_TICKERS:
            # Exact legacy 10-ticker install: truncate and replace with all 100
            await db.execute(
                "DELETE FROM analysis_tickers WHERE user_id = ?", (DEFAULT_USER_ID,)
            )
            await db.executemany(
                "INSERT INTO analysis_tickers "
                "(id, user_id, ticker, added_at, sector, sub_sector, seed_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (str(uuid.uuid4()), DEFAULT_USER_ID, e["ticker"], seed_now,
                     e["sector"], e["sub_sector"], SEED_VERSION)
                    for e in SEED_TICKERS
                ],
            )
            await db.commit()
        elif not existing:
            # Fresh install or empty table: seed all 100
            await db.executemany(
                "INSERT OR IGNORE INTO analysis_tickers "
                "(id, user_id, ticker, added_at, sector, sub_sector, seed_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (str(uuid.uuid4()), DEFAULT_USER_ID, e["ticker"], seed_now,
                     e["sector"], e["sub_sector"], SEED_VERSION)
                    for e in SEED_TICKERS
                ],
            )
            await db.commit()
        else:
            # Custom tickers present: additive merge only, never DELETE
            missing = [e for e in SEED_TICKERS if e["ticker"] not in existing]
            if missing:
                await db.executemany(
                    "INSERT OR IGNORE INTO analysis_tickers "
                    "(id, user_id, ticker, added_at, sector, sub_sector, seed_version) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [
                        (str(uuid.uuid4()), DEFAULT_USER_ID, e["ticker"], seed_now,
                         e["sector"], e["sub_sector"], SEED_VERSION)
                        for e in missing
                    ],
                )
                await db.commit()

        # Check if default user exists
        cursor = await db.execute(
            "SELECT id FROM users_profile WHERE id = ?", (DEFAULT_USER_ID,)
        )
        user = await cursor.fetchone()

        if user is None:
            now = datetime.now(timezone.utc).isoformat()

            # Create default user
            await db.execute(
                "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
                (DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, now),
            )

            # Seed default watchlist
            for ticker in DEFAULT_TICKERS:
                await db.execute(
                    "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, now),
                )

            # Seed current run — GOOGL/AMZN fresh + AAPL orphaned (38 days ago)
            seed_run_id = str(uuid.uuid4())
            for row in _MOCK_ANALYSIS_SEED:
                days_ago = row.get("analyzed_at_days_ago", 0)
                row_ts = (
                    datetime.now(timezone.utc) - timedelta(days=days_ago)
                ).isoformat()
                await db.execute(
                    """
                    INSERT INTO analysis_results (
                        id, user_id, run_id, ticker, rank, score, signal, confidence,
                        risk_reward_ratio, entry_price, target_price, stop_loss,
                        support_validated, argument, indicators_summary,
                        screenshot_path, analyzed_at,
                        expected_gain_per10, expected_loss_per10, expected_value_per10,
                        hit_rate_used, hit_rate_source, stop_viable, atr_14_pct
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        DEFAULT_USER_ID,
                        seed_run_id,
                        row["ticker"],
                        row["rank"],
                        row["score"],
                        row["signal"],
                        row["confidence"],
                        row["risk_reward_ratio"],
                        row["entry_price"],
                        row["target_price"],
                        row["stop_loss"],
                        row["support_validated"],
                        row["argument"],
                        row["indicators_summary"],
                        row_ts,
                        row["expected_gain_per10"],
                        row["expected_loss_per10"],
                        row["expected_value_per10"],
                        row["hit_rate_used"],
                        row["hit_rate_source"],
                        row.get("stop_viable"),
                        row.get("atr_14_pct"),
                    ),
                )

            # Seed historical resolved run (60 days ago) for performance metrics
            hist_run_id = str(uuid.uuid4())
            hist_ts = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
            for row in _MOCK_RESOLVED_SEED:
                await db.execute(
                    """
                    INSERT INTO analysis_results (
                        id, user_id, run_id, ticker, rank, score, signal, confidence,
                        risk_reward_ratio, entry_price, target_price, stop_loss,
                        support_validated, argument, indicators_summary,
                        screenshot_path, analyzed_at,
                        expected_gain_per10, expected_loss_per10, expected_value_per10,
                        hit_rate_used, hit_rate_source,
                        outcome, actual_gain_pct, actual_loss_pct, hold_days,
                        support_break_level
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?,
                              ?, ?, ?, ?, ?,
                              ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        DEFAULT_USER_ID,
                        hist_run_id,
                        row["ticker"],
                        row["rank"],
                        row["score"],
                        row["signal"],
                        row["confidence"],
                        row["risk_reward_ratio"],
                        row["entry_price"],
                        row["target_price"],
                        row["stop_loss"],
                        row["support_validated"],
                        row["argument"],
                        row["indicators_summary"],
                        hist_ts,
                        row["expected_gain_per10"],
                        row["expected_loss_per10"],
                        row["expected_value_per10"],
                        row["hit_rate_used"],
                        row["hit_rate_source"],
                        row["outcome"],
                        row["actual_gain_pct"],
                        row["actual_loss_pct"],
                        row["hold_days"],
                        row["support_break_level"],
                    ),
                )

            await db.commit()
    finally:
        await db.close()
