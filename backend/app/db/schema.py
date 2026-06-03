"""Database schema SQL and default seed data."""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users_profile (
    id TEXT PRIMARY KEY,
    cash_balance REAL NOT NULL DEFAULT 10000.0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    added_at TEXT NOT NULL,
    UNIQUE(user_id, ticker)
);

CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    quantity REAL NOT NULL,
    avg_cost REAL NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, ticker)
);

CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    executed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    total_value REAL NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    actions TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    run_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    rank INTEGER,
    score REAL,
    score_delta REAL,
    signal TEXT,
    confidence REAL,
    risk_reward_ratio REAL,
    entry_price REAL,
    target_price REAL,
    stop_loss REAL,
    support_validated INTEGER NOT NULL DEFAULT 0,
    argument TEXT,
    indicators_summary TEXT,
    screenshot_path TEXT,
    analyzed_at TEXT NOT NULL,
    expected_gain_per10 REAL,
    expected_loss_per10 REAL,
    expected_value_per10 REAL,
    hit_rate_used REAL,
    hit_rate_source TEXT,
    outcome TEXT,
    actual_gain_pct REAL,
    actual_loss_pct REAL,
    hold_days REAL,
    support_break_level TEXT
);

CREATE TABLE IF NOT EXISTS analysis_tickers (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    added_at TEXT NOT NULL,
    UNIQUE(user_id, ticker)
);
"""

DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]
DEFAULT_CASH_BALANCE = 10000.0
DEFAULT_USER_ID = "default"
