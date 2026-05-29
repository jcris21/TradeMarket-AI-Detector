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
        # Bet-size: gain=round(10*(208.54-178.50)/178.50,2)=1.68, loss=round(10*(178.50-172.20)/178.50,2)=0.35
        "expected_gain_per10": 1.68,
        "expected_loss_per10": 0.35,
        "expected_value_per10": round(0.35 * 1.68 - 0.65 * 0.35, 2),
        "hit_rate_used": 0.35,
        "hit_rate_source": "assumed",
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
        # Bet-size: gain=round(10*(223.61-198.20)/198.20,2)=1.28, loss=round(10*(198.20-190.50)/198.20,2)=0.39
        "expected_gain_per10": 1.28,
        "expected_loss_per10": 0.39,
        "expected_value_per10": round(0.35 * 1.28 - 0.65 * 0.39, 2),
        "hit_rate_used": 0.35,
        "hit_rate_source": "assumed",
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


async def init_db() -> None:
    """Create tables and seed default data if needed."""
    db = await get_connection()
    try:
        await db.executescript(SCHEMA_SQL)

        # Lazy migration: add columns if not already present
        for col, col_type in _BET_SIZE_COLUMNS:
            try:
                await db.execute(
                    f"ALTER TABLE analysis_results ADD COLUMN {col} {col_type}"
                )
            except aiosqlite.OperationalError as e:
                if "duplicate column name" not in str(e):
                    raise

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

            # Seed default analysis tickers (same as watchlist)
            for ticker in DEFAULT_TICKERS:
                await db.execute(
                    "INSERT OR IGNORE INTO analysis_tickers (id, user_id, ticker, added_at) "
                    "VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, now),
                )

            # Seed mock analysis results so the UI renders on first launch
            seed_run_id = str(uuid.uuid4())
            for row in _MOCK_ANALYSIS_SEED:
                await db.execute(
                    """
                    INSERT INTO analysis_results (
                        id, user_id, run_id, ticker, rank, score, signal, confidence,
                        risk_reward_ratio, entry_price, target_price, stop_loss,
                        support_validated, argument, indicators_summary,
                        screenshot_path, analyzed_at,
                        expected_gain_per10, expected_loss_per10, expected_value_per10,
                        hit_rate_used, hit_rate_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
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
                        now,
                        row["expected_gain_per10"],
                        row["expected_loss_per10"],
                        row["expected_value_per10"],
                        row["hit_rate_used"],
                        row["hit_rate_source"],
                    ),
                )

            await db.commit()
    finally:
        await db.close()
