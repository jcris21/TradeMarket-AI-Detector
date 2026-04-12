# Technical Analysis Multi-Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a multi-agent technical analysis pipeline that fetches indicators via yfinance, captures investing.com chart screenshots via Playwright, analyzes them with LLM vision, and surfaces Top 5 buy opportunities (≥3:1 R/R) in a dedicated frontend panel.

**Architecture:** OrchestratorAgent coordinates 4 stages: parallel DataAgent calls (yfinance + pandas-ta) → sequential ScreenshotAgent (single Playwright session) → parallel VisionAgent calls (LiteLLM vision) → ScoringAgent (filter + rank). Results cached in SQLite, served via 6 new API endpoints.

**Tech Stack:** yfinance, pandas-ta, playwright (async), litellm (vision), aiosqlite, FastAPI, Next.js/TypeScript

**Spec:** `docs/superpowers/specs/2026-04-11-technical-analysis-multiagent-design.md`
**Agents contract:** `planning/AGENTS.md`

---

## File Map

**New backend files:**
- `backend/app/analysis/__init__.py`
- `backend/app/analysis/models.py`
- `backend/app/analysis/data_agent.py`
- `backend/app/analysis/screenshot_agent.py`
- `backend/app/analysis/vision_agent.py`
- `backend/app/analysis/scoring_agent.py`
- `backend/app/analysis/orchestrator.py`
- `backend/app/routes/analysis.py`
- `backend/tests/analysis/__init__.py`
- `backend/tests/analysis/test_data_agent.py`
- `backend/tests/analysis/test_screenshot_agent.py`
- `backend/tests/analysis/test_vision_agent.py`
- `backend/tests/analysis/test_scoring_agent.py`
- `backend/tests/analysis/test_orchestrator.py`

**Modified backend files:**
- `backend/pyproject.toml` — add yfinance, pandas-ta, playwright, pydantic
- `backend/app/db/schema.py` — add analysis_results, analysis_tickers SQL
- `backend/app/db/connection.py` — seed analysis_tickers in init_db()
- `backend/app/db/repository.py` — add analysis CRUD functions
- `backend/app/db/__init__.py` — export new functions
- `backend/app/main.py` — register analysis router

**New frontend files:**
- `frontend/lib/use-analysis.ts`
- `frontend/components/OpportunitiesPanel.tsx`
- `frontend/__tests__/OpportunitiesPanel.test.tsx`

**Modified frontend files:**
- `frontend/lib/types.ts` — add analysis types
- `frontend/lib/api.ts` — add analysis API functions
- `frontend/app/page.tsx` — add OpportunitiesPanel

**Infrastructure:**
- `Dockerfile` — add playwright chromium install

---

## Task 1: Add Python dependencies

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add dependencies**

In `backend/pyproject.toml`, add to the `dependencies` list:

```toml
[project]
name = "finally-backend"
version = "0.1.0"
description = "FinAlly backend - AI Trading Workstation"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "numpy>=2.0.0",
    "massive>=1.0.0",
    "rich>=13.0.0",
    "aiosqlite>=0.22.1",
    "litellm>=1.81.10",
    "yfinance>=0.2.50",
    "pandas-ta>=0.3.14b",
    "playwright>=1.40.0",
    "pydantic>=2.0.0",
]
```

- [ ] **Step 2: Install dependencies**

```bash
cd backend
uv sync --extra dev
playwright install chromium
```

Expected: dependencies install without error. Playwright installs Chromium browser.

- [ ] **Step 3: Verify imports work**

```bash
uv run python -c "import yfinance; import pandas_ta; from playwright.async_api import async_playwright; print('OK')"
```

Expected output: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "feat: add yfinance, pandas-ta, playwright dependencies for analysis module"
```

---

## Task 2: Extend DB schema

**Files:**
- Modify: `backend/app/db/schema.py`
- Modify: `backend/app/db/connection.py`

- [ ] **Step 1: Write failing test for schema**

Create `backend/tests/analysis/__init__.py` (empty file), then write `backend/tests/analysis/test_db_schema.py`:

```python
"""Tests for analysis DB schema and seeding."""
import pytest
from app.db import get_connection, init_db, set_db_path


@pytest.fixture(autouse=True)
async def tmp_db(tmp_path):
    set_db_path(str(tmp_path / "test.db"))
    await init_db()


async def test_analysis_results_table_exists():
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_results'"
        )
        row = await cursor.fetchone()
        assert row is not None
    finally:
        await db.close()


async def test_analysis_tickers_table_exists():
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_tickers'"
        )
        row = await cursor.fetchone()
        assert row is not None
    finally:
        await db.close()


async def test_analysis_tickers_seeded_with_defaults():
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT ticker FROM analysis_tickers WHERE user_id = 'default' ORDER BY ticker"
        )
        rows = await cursor.fetchall()
        tickers = [r[0] for r in rows]
        assert "AAPL" in tickers
        assert "NVDA" in tickers
        assert len(tickers) == 10
    finally:
        await db.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
uv run --extra dev pytest tests/analysis/test_db_schema.py -v
```

Expected: FAIL — tables don't exist yet.

- [ ] **Step 3: Add SQL to schema.py**

Append to the `SCHEMA_SQL` string in `backend/app/db/schema.py` (before the closing `"""`):

```python
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
    analyzed_at TEXT NOT NULL
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
```

- [ ] **Step 4: Seed analysis_tickers in init_db()**

In `backend/app/db/connection.py`, extend `init_db()` to seed `analysis_tickers` when the default user is created. Add this block right after the watchlist seeding loop (before `await db.commit()`):

```python
            # Seed default analysis tickers (same as watchlist)
            for ticker in DEFAULT_TICKERS:
                await db.execute(
                    "INSERT OR IGNORE INTO analysis_tickers (id, user_id, ticker, added_at) "
                    "VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, now),
                )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend
uv run --extra dev pytest tests/analysis/test_db_schema.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/schema.py backend/app/db/connection.py backend/tests/analysis/
git commit -m "feat: add analysis_results and analysis_tickers tables to schema"
```

---

## Task 3: Analysis DB repository functions

**Files:**
- Modify: `backend/app/db/repository.py`
- Modify: `backend/app/db/__init__.py`

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/analysis/test_db_schema.py`:

```python
from app.db.repository import (
    get_analysis_tickers,
    add_analysis_ticker,
    remove_analysis_ticker,
    save_analysis_results,
    get_latest_analysis,
    get_analysis_by_ticker,
)


async def test_get_analysis_tickers_returns_defaults():
    tickers = await get_analysis_tickers()
    assert len(tickers) == 10
    assert "NVDA" in tickers


async def test_add_and_remove_analysis_ticker():
    await add_analysis_ticker("PYPL")
    tickers = await get_analysis_tickers()
    assert "PYPL" in tickers

    removed = await remove_analysis_ticker("PYPL")
    assert removed is True
    tickers = await get_analysis_tickers()
    assert "PYPL" not in tickers


async def test_add_duplicate_analysis_ticker_is_idempotent():
    await add_analysis_ticker("AAPL")  # already seeded
    tickers = await get_analysis_tickers()
    assert tickers.count("AAPL") == 1


async def test_save_and_retrieve_analysis_results():
    rows = [
        {
            "run_id": "run-1",
            "ticker": "NVDA",
            "rank": 1,
            "score": 88.5,
            "signal": "BUY",
            "confidence": 0.9,
            "risk_reward_ratio": 4.2,
            "entry_price": 890.0,
            "target_price": 930.0,
            "stop_loss": 880.0,
            "support_validated": True,
            "argument": "Strong bullish setup",
            "indicators_summary": '{"macd": "bullish"}',
            "screenshot_path": None,
        }
    ]
    await save_analysis_results(rows)

    results = await get_latest_analysis()
    assert len(results) == 1
    assert results[0]["ticker"] == "NVDA"
    assert results[0]["rank"] == 1


async def test_get_analysis_by_ticker_returns_latest():
    rows = [
        {
            "run_id": "run-2",
            "ticker": "AAPL",
            "rank": 2,
            "score": 75.0,
            "signal": "BUY",
            "confidence": 0.8,
            "risk_reward_ratio": 3.5,
            "entry_price": 190.0,
            "target_price": 210.0,
            "stop_loss": 184.0,
            "support_validated": True,
            "argument": "RSI bounce off support",
            "indicators_summary": "{}",
            "screenshot_path": None,
        }
    ]
    await save_analysis_results(rows)
    result = await get_analysis_by_ticker("AAPL")
    assert result is not None
    assert result["ticker"] == "AAPL"


async def test_get_analysis_by_ticker_returns_none_when_missing():
    result = await get_analysis_by_ticker("ZZZZ")
    assert result is None
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend
uv run --extra dev pytest tests/analysis/test_db_schema.py -v -k "ticker or analysis"
```

Expected: FAIL — functions not defined.

- [ ] **Step 3: Add functions to repository.py**

Append to the end of `backend/app/db/repository.py`:

```python
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
) -> None:
    """Persist a batch of analysis results. Each dict matches analysis_results columns."""
    db = await get_connection()
    try:
        for row in rows:
            await db.execute(
                "INSERT INTO analysis_results "
                "(id, user_id, run_id, ticker, rank, score, signal, confidence, "
                "risk_reward_ratio, entry_price, target_price, stop_loss, "
                "support_validated, argument, indicators_summary, screenshot_path, analyzed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    _uuid(),
                    user_id,
                    row["run_id"],
                    row["ticker"],
                    row.get("rank"),
                    row.get("score"),
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
                ),
            )
        await db.commit()
    finally:
        await db.close()


async def get_latest_analysis(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """Return all rows from the most recent analysis run, ordered by rank."""
    db = await get_connection()
    try:
        # Find the most recent run_id
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
        return [dict(r) for r in rows]
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
        return dict(row) if row else None
    finally:
        await db.close()
```

- [ ] **Step 4: Export from db/__init__.py**

Add these imports to `backend/app/db/__init__.py`:

```python
from .repository import (
    # ... existing imports ...
    add_analysis_ticker,
    get_analysis_tickers,
    get_analysis_by_ticker,
    get_latest_analysis,
    remove_analysis_ticker,
    save_analysis_results,
)
```

And add to `__all__`:
```python
    "add_analysis_ticker",
    "get_analysis_tickers",
    "get_analysis_by_ticker",
    "get_latest_analysis",
    "remove_analysis_ticker",
    "save_analysis_results",
```

- [ ] **Step 5: Run all schema tests**

```bash
cd backend
uv run --extra dev pytest tests/analysis/test_db_schema.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/repository.py backend/app/db/__init__.py backend/tests/analysis/test_db_schema.py
git commit -m "feat: add analysis DB repository functions (tickers + results CRUD)"
```

---

## Task 4: Analysis models

**Files:**
- Create: `backend/app/analysis/__init__.py`
- Create: `backend/app/analysis/models.py`

- [ ] **Step 1: Create the package**

Create `backend/app/analysis/__init__.py`:

```python
"""Multi-agent technical analysis subsystem."""
```

- [ ] **Step 2: Create models.py**

Create `backend/app/analysis/models.py`:

```python
"""Data models for the technical analysis pipeline."""

import json
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel


@dataclass(frozen=True)
class TechnicalIndicators:
    """Computed technical indicators for one ticker."""

    ticker: str
    current_price: float
    macd_signal: Literal["bullish_crossover", "bearish_crossover", "neutral"]
    macd_histogram: float
    rsi: float
    volume_ratio: float  # current volume / 20-day SMA
    support_1: float     # 20-period low
    support_2: float     # 40-period low
    resistance_1: float  # 20-period high
    resistance_2: float  # 40-period high


class AssetAnalysis(BaseModel):
    """LLM analysis output for one ticker, with optional scoring."""

    ticker: str
    signal: Literal["BUY", "WAIT", "AVOID"]
    confidence: float
    entry_price: float
    target_price: float
    stop_loss: float
    risk_reward_ratio: float
    support_validated: bool
    indicators_summary: dict
    argument: str
    score: float | None = None
    rank: int | None = None

    def to_db_row(self, run_id: str) -> dict:
        """Convert to a dict suitable for save_analysis_results()."""
        return {
            "run_id": run_id,
            "ticker": self.ticker,
            "rank": self.rank,
            "score": self.score,
            "signal": self.signal,
            "confidence": self.confidence,
            "risk_reward_ratio": self.risk_reward_ratio,
            "entry_price": self.entry_price,
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "support_validated": self.support_validated,
            "argument": self.argument,
            "indicators_summary": json.dumps(self.indicators_summary),
            "screenshot_path": None,
        }


class AnalysisResult(BaseModel):
    """Complete output of one analysis run."""

    run_id: str
    analyzed_at: str
    assets: list[AssetAnalysis]   # all analyzed (ranked + unranked)
    top_5: list[AssetAnalysis]    # filtered and sorted Top N
    errors: list[dict]            # [{ticker, error_message}]
    duration_seconds: float


class DataFetchError(Exception):
    """Raised when yfinance returns no data for a ticker."""

    def __init__(self, ticker: str) -> None:
        super().__init__(f"No data available for {ticker}")
        self.ticker = ticker


class InvestingComAuthError(Exception):
    """Raised when Playwright cannot log in to investing.com."""
    pass
```

- [ ] **Step 3: Verify import works**

```bash
cd backend
uv run python -c "from app.analysis.models import TechnicalIndicators, AssetAnalysis, AnalysisResult; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/analysis/
git commit -m "feat: add analysis package with Pydantic/dataclass models"
```

---

## Task 5: DataAgent

**Files:**
- Create: `backend/app/analysis/data_agent.py`
- Create: `backend/tests/analysis/test_data_agent.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/analysis/test_data_agent.py`:

```python
"""Tests for DataAgent — yfinance fetch + pandas-ta indicators."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.analysis.data_agent import fetch_indicators
from app.analysis.models import DataFetchError, TechnicalIndicators


def _make_ohlcv(n: int = 60) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame with n rows."""
    import numpy as np

    rng = pd.date_range("2024-01-01", periods=n, freq="B")
    prices = 100 + np.cumsum(np.random.randn(n) * 0.5)
    df = pd.DataFrame(
        {
            "Open": prices * 0.99,
            "High": prices * 1.01,
            "Low": prices * 0.98,
            "Close": prices,
            "Volume": np.random.randint(1_000_000, 5_000_000, n).astype(float),
        },
        index=rng,
    )
    return df


@patch("app.analysis.data_agent.yf.download")
async def test_fetch_indicators_returns_technical_indicators(mock_download):
    mock_download.return_value = _make_ohlcv(60)
    result = await fetch_indicators("AAPL")
    assert isinstance(result, TechnicalIndicators)
    assert result.ticker == "AAPL"
    assert result.current_price > 0
    assert result.support_1 <= result.resistance_1
    assert result.support_2 <= result.support_1


@patch("app.analysis.data_agent.yf.download")
async def test_macd_signal_is_valid_literal(mock_download):
    mock_download.return_value = _make_ohlcv(60)
    result = await fetch_indicators("MSFT")
    assert result.macd_signal in ("bullish_crossover", "bearish_crossover", "neutral")


@patch("app.analysis.data_agent.yf.download")
async def test_rsi_in_valid_range(mock_download):
    mock_download.return_value = _make_ohlcv(60)
    result = await fetch_indicators("GOOGL")
    assert 0 <= result.rsi <= 100


@patch("app.analysis.data_agent.yf.download")
async def test_volume_ratio_positive(mock_download):
    mock_download.return_value = _make_ohlcv(60)
    result = await fetch_indicators("TSLA")
    assert result.volume_ratio > 0


@patch("app.analysis.data_agent.yf.download")
async def test_empty_dataframe_raises_data_fetch_error(mock_download):
    mock_download.return_value = pd.DataFrame()
    with pytest.raises(DataFetchError) as exc_info:
        await fetch_indicators("FAKE")
    assert exc_info.value.ticker == "FAKE"
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend
uv run --extra dev pytest tests/analysis/test_data_agent.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement data_agent.py**

Create `backend/app/analysis/data_agent.py`:

```python
"""DataAgent — fetches historical prices and computes technical indicators."""

import asyncio
import logging

import pandas as pd
import pandas_ta as ta
import yfinance as yf

from .models import DataFetchError, TechnicalIndicators

logger = logging.getLogger(__name__)


def _compute_indicators(ticker: str, df: pd.DataFrame) -> TechnicalIndicators:
    """Compute MACD, RSI, volume ratio, and pivot points from OHLCV DataFrame."""
    if df.empty or len(df) < 30:
        raise DataFetchError(ticker)

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # MACD (12, 26, 9)
    macd_df = ta.macd(close, fast=12, slow=26, signal=9)
    if macd_df is None or macd_df.empty:
        raise DataFetchError(ticker)

    macd_col = [c for c in macd_df.columns if c.startswith("MACD_")][0]
    signal_col = [c for c in macd_df.columns if c.startswith("MACDs_")][0]
    hist_col = [c for c in macd_df.columns if c.startswith("MACDh_")][0]

    macd_val = float(macd_df[macd_col].iloc[-1])
    signal_val = float(macd_df[signal_col].iloc[-1])
    hist_val = float(macd_df[hist_col].iloc[-1])

    prev_hist = float(macd_df[hist_col].iloc[-2]) if len(macd_df) >= 2 else 0.0

    if macd_val > signal_val and hist_val > 0 and prev_hist <= 0:
        macd_signal = "bullish_crossover"
    elif macd_val < signal_val and hist_val < 0 and prev_hist >= 0:
        macd_signal = "bearish_crossover"
    else:
        macd_signal = "neutral"

    # RSI (14)
    rsi_series = ta.rsi(close, length=14)
    rsi = float(rsi_series.iloc[-1]) if rsi_series is not None else 50.0

    # Volume ratio: current vs 20-day SMA
    vol_sma = ta.sma(volume, length=20)
    current_vol = float(volume.iloc[-1])
    sma_vol = float(vol_sma.iloc[-1]) if vol_sma is not None else current_vol
    volume_ratio = current_vol / sma_vol if sma_vol > 0 else 1.0

    # Pivot points: 20-period and 40-period ranges
    support_1 = float(low.iloc[-20:].min())
    resistance_1 = float(high.iloc[-20:].max())
    support_2 = float(low.iloc[-40:].min()) if len(low) >= 40 else support_1
    resistance_2 = float(high.iloc[-40:].max()) if len(high) >= 40 else resistance_1

    current_price = float(close.iloc[-1])

    return TechnicalIndicators(
        ticker=ticker,
        current_price=current_price,
        macd_signal=macd_signal,
        macd_histogram=round(hist_val, 4),
        rsi=round(rsi, 2),
        volume_ratio=round(volume_ratio, 3),
        support_1=round(support_1, 2),
        support_2=round(support_2, 2),
        resistance_1=round(resistance_1, 2),
        resistance_2=round(resistance_2, 2),
    )


async def fetch_indicators(ticker: str) -> TechnicalIndicators:
    """Fetch 60 days of OHLCV data and compute technical indicators.

    Raises DataFetchError if no data is available for the ticker.
    """
    logger.debug("Fetching indicators for %s", ticker)
    df = await asyncio.to_thread(
        yf.download, ticker, period="3mo", interval="1d", progress=False, auto_adjust=True
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return _compute_indicators(ticker, df)
```

- [ ] **Step 4: Run tests**

```bash
cd backend
uv run --extra dev pytest tests/analysis/test_data_agent.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/analysis/data_agent.py backend/tests/analysis/test_data_agent.py
git commit -m "feat: add DataAgent with yfinance + pandas-ta indicator computation"
```

---

## Task 6: ScreenshotAgent

**Files:**
- Create: `backend/app/analysis/screenshot_agent.py`
- Create: `backend/tests/analysis/test_screenshot_agent.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/analysis/test_screenshot_agent.py`:

```python
"""Tests for ScreenshotAgent — Playwright screenshot capture."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.analysis.models import InvestingComAuthError
from app.analysis.screenshot_agent import capture_charts


@pytest.fixture
def mock_page():
    page = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"\x89PNG\r\n")
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.click = AsyncMock()
    page.fill = AsyncMock()
    return page


@pytest.fixture
def mock_playwright_ctx(mock_page):
    browser = AsyncMock()
    context = AsyncMock()
    context.new_page = AsyncMock(return_value=mock_page)
    browser.new_context = AsyncMock(return_value=context)

    chromium = MagicMock()
    chromium.launch = AsyncMock(return_value=browser)

    pw = AsyncMock()
    pw.__aenter__ = AsyncMock(return_value=pw)
    pw.__aexit__ = AsyncMock(return_value=None)
    pw.chromium = chromium
    return pw


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
async def test_mock_mode_returns_png_bytes_for_all_tickers():
    result = await capture_charts(["AAPL", "MSFT"])
    assert set(result.keys()) == {"AAPL", "MSFT"}
    for v in result.values():
        assert isinstance(v, bytes)
        assert len(v) > 0


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": ""})
@patch.dict(os.environ, {"INVESTING_COM_EMAIL": "", "INVESTING_COM_PASSWORD": ""})
async def test_missing_credentials_raises_auth_error():
    with pytest.raises(InvestingComAuthError):
        await capture_charts(["AAPL"])


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": ""})
@patch.dict(os.environ, {
    "INVESTING_COM_EMAIL": "test@example.com",
    "INVESTING_COM_PASSWORD": "pass"
})
@patch("app.analysis.screenshot_agent.async_playwright")
async def test_login_failure_raises_auth_error(mock_pw_factory, mock_playwright_ctx, mock_page):
    # Simulate login form not found
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))
    mock_playwright_ctx.chromium.launch = AsyncMock(
        return_value=AsyncMock(new_context=AsyncMock(return_value=AsyncMock(new_page=AsyncMock(return_value=mock_page))))
    )
    mock_pw_factory.return_value = mock_playwright_ctx

    with pytest.raises(InvestingComAuthError):
        await capture_charts(["AAPL"])
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend
uv run --extra dev pytest tests/analysis/test_screenshot_agent.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement screenshot_agent.py**

Create `backend/app/analysis/screenshot_agent.py`:

```python
"""ScreenshotAgent — captures investing.com chart screenshots via Playwright."""

import logging
import os

from playwright.async_api import async_playwright

from .models import InvestingComAuthError

logger = logging.getLogger(__name__)

# Minimal 1x1 transparent PNG for mock mode
_MOCK_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)

# investing.com slug mapping for default tickers
_TICKER_SLUGS: dict[str, str] = {
    "AAPL": "apple-computer-inc",
    "GOOGL": "alphabet-inc",
    "MSFT": "microsoft-corp",
    "AMZN": "amazon-com-inc",
    "TSLA": "tesla-motors",
    "NVDA": "nvidia-corp",
    "META": "meta-platforms-inc",
    "JPM": "jpmorgan-chase",
    "V": "visa",
    "NFLX": "netflix-inc",
}

_CHART_INTERVAL_MAP = {
    "1D": "1D",
    "1W": "1W",
    "1M": "1M",
}

SCREENSHOT_TIMEOUT = 30_000  # ms


async def _login(page) -> None:
    """Log in to investing.com. Raises InvestingComAuthError on failure."""
    email = os.environ.get("INVESTING_COM_EMAIL", "")
    password = os.environ.get("INVESTING_COM_PASSWORD", "")
    if not email or not password:
        raise InvestingComAuthError("INVESTING_COM_EMAIL and INVESTING_COM_PASSWORD must be set")

    try:
        await page.goto("https://www.investing.com/", wait_until="domcontentloaded", timeout=30_000)
        # Accept cookies if banner present
        try:
            await page.click("#onetrust-accept-btn-handler", timeout=5_000)
        except Exception:
            pass

        # Open sign-in form
        await page.click('[data-test="sign-in-btn"]', timeout=10_000)
        await page.wait_for_selector('input[name="email"]', timeout=10_000)
        await page.fill('input[name="email"]', email)
        await page.fill('input[name="password"]', password)
        await page.click('[data-test="submit-btn"]', timeout=10_000)
        # Wait for login to complete (user menu appears)
        await page.wait_for_selector('[data-test="user-menu"]', timeout=15_000)
        logger.info("Logged in to investing.com")
    except InvestingComAuthError:
        raise
    except Exception as exc:
        raise InvestingComAuthError(f"Login failed: {exc}") from exc


async def _get_slug(page, ticker: str) -> str | None:
    """Return the investing.com URL slug for a ticker, or None if not found."""
    if ticker in _TICKER_SLUGS:
        return _TICKER_SLUGS[ticker]
    # Attempt search for unknown tickers
    try:
        await page.goto(
            f"https://www.investing.com/search/?q={ticker}",
            wait_until="domcontentloaded",
            timeout=15_000,
        )
        await page.wait_for_selector(".js-inner-all-results-quote-item", timeout=8_000)
        href = await page.get_attribute(".js-inner-all-results-quote-item a", "href")
        if href and "/equities/" in href:
            return href.split("/equities/")[1].split("?")[0].rstrip("/")
    except Exception:
        pass
    return None


async def _capture_one(page, ticker: str, interval: str) -> bytes | None:
    """Navigate to a ticker chart page and return a screenshot, or None on failure."""
    slug = await _get_slug(page, ticker)
    if slug is None:
        logger.warning("No slug found for %s — skipping screenshot", ticker)
        return None

    try:
        url = f"https://www.investing.com/equities/{slug}"
        await page.goto(url, wait_until="domcontentloaded", timeout=SCREENSHOT_TIMEOUT)

        # Set chart interval if controls are visible
        try:
            interval_label = _CHART_INTERVAL_MAP.get(interval, "1D")
            await page.click(f'[data-period="{interval_label}"]', timeout=5_000)
        except Exception:
            pass

        await page.wait_for_load_state("networkidle", timeout=SCREENSHOT_TIMEOUT)

        # Screenshot the chart canvas area
        chart_el = await page.query_selector("#technicalChart, canvas.chart-canvas, #chart")
        if chart_el:
            screenshot = await chart_el.screenshot(timeout=SCREENSHOT_TIMEOUT)
        else:
            # Fall back to full viewport screenshot
            screenshot = await page.screenshot(full_page=False, timeout=SCREENSHOT_TIMEOUT)

        logger.debug("Captured screenshot for %s (%d bytes)", ticker, len(screenshot))
        return screenshot

    except Exception as exc:
        logger.warning("Screenshot failed for %s: %s", ticker, exc)
        return None


async def capture_charts(
    tickers: list[str],
    interval: str | None = None,
) -> dict[str, bytes | None]:
    """Capture chart screenshots for all tickers in a single Playwright session.

    If PLAYWRIGHT_MOCK=true, returns dummy PNG bytes without launching a browser.
    Raises InvestingComAuthError if credentials are missing or login fails.
    Returns dict[ticker, bytes | None] — None when a ticker's screenshot failed.
    """
    if os.environ.get("PLAYWRIGHT_MOCK", "").lower() == "true":
        return {t: _MOCK_PNG for t in tickers}

    chart_interval = interval or os.environ.get("INVESTING_COM_CHART_INTERVAL", "1D")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        await _login(page)

        results: dict[str, bytes | None] = {}
        for ticker in tickers:
            results[ticker] = await _capture_one(page, ticker, chart_interval)

        await browser.close()

    return results
```

- [ ] **Step 4: Run tests**

```bash
cd backend
uv run --extra dev pytest tests/analysis/test_screenshot_agent.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/analysis/screenshot_agent.py backend/tests/analysis/test_screenshot_agent.py
git commit -m "feat: add ScreenshotAgent with Playwright investing.com integration + mock mode"
```

---

## Task 7: VisionAgent

**Files:**
- Create: `backend/app/analysis/vision_agent.py`
- Create: `backend/tests/analysis/test_vision_agent.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/analysis/test_vision_agent.py`:

```python
"""Tests for VisionAgent — LLM vision analysis."""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from app.analysis.models import AssetAnalysis, TechnicalIndicators
from app.analysis.vision_agent import analyze_asset

_INDICATORS = TechnicalIndicators(
    ticker="NVDA",
    current_price=890.0,
    macd_signal="bullish_crossover",
    macd_histogram=0.42,
    rsi=58.0,
    volume_ratio=1.23,
    support_1=875.0,
    support_2=860.0,
    resistance_1=920.0,
    resistance_2=940.0,
)

_VALID_LLM_JSON = json.dumps({
    "ticker": "NVDA",
    "signal": "BUY",
    "confidence": 0.85,
    "entry_price": 890.0,
    "target_price": 920.0,
    "stop_loss": 875.0,
    "risk_reward_ratio": 2.0,
    "support_validated": True,
    "indicators_summary": {"macd": "bullish_crossover", "rsi": 58.0, "volume": "above_avg"},
    "argument": "Strong bullish setup with MACD crossover.",
})

_MOCK_PNG = b"\x89PNG\r\n"


def _make_mock_completion(json_content: str):
    mock_choice = MagicMock()
    mock_choice.message.content = json_content
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    return mock_resp


@patch("app.analysis.vision_agent.completion")
async def test_analyze_asset_returns_asset_analysis(mock_completion):
    mock_completion.return_value = _make_mock_completion(_VALID_LLM_JSON)
    result = await analyze_asset(_INDICATORS, _MOCK_PNG)
    assert isinstance(result, AssetAnalysis)
    assert result.ticker == "NVDA"
    assert result.signal == "BUY"
    assert result.confidence == pytest.approx(0.85)


@patch("app.analysis.vision_agent.completion")
async def test_analyze_asset_without_screenshot_still_returns_result(mock_completion):
    mock_completion.return_value = _make_mock_completion(_VALID_LLM_JSON)
    result = await analyze_asset(_INDICATORS, None)
    assert isinstance(result, AssetAnalysis)
    assert result.support_validated is False  # forced False when no screenshot


@patch("app.analysis.vision_agent.completion")
async def test_malformed_llm_response_returns_avoid(mock_completion):
    mock_completion.return_value = _make_mock_completion("not valid json {{{{")
    result = await analyze_asset(_INDICATORS, _MOCK_PNG)
    assert result.signal == "AVOID"
    assert result.confidence == 0.0
    assert "unavailable" in result.argument.lower()


@patch("app.analysis.vision_agent.completion")
async def test_llm_exception_returns_avoid(mock_completion):
    mock_completion.side_effect = Exception("OpenRouter timeout")
    result = await analyze_asset(_INDICATORS, _MOCK_PNG)
    assert result.signal == "AVOID"
    assert result.confidence == 0.0
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend
uv run --extra dev pytest tests/analysis/test_vision_agent.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement vision_agent.py**

Create `backend/app/analysis/vision_agent.py`:

```python
"""VisionAgent — analyzes chart screenshots + numerical indicators via LLM vision."""

import asyncio
import base64
import json
import logging

from litellm import completion
from pydantic import ValidationError

from .models import AssetAnalysis, TechnicalIndicators

logger = logging.getLogger(__name__)

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

_SYSTEM_PROMPT = """You are an expert technical analyst. You will receive:
1. A chart screenshot from investing.com (when available)
2. Pre-computed numerical indicators (MACD, RSI, Volume, pivot points)

Your task:
- Validate the support and resistance levels visible in the chart
- Calculate the risk/reward ratio: (target_price - entry_price) / (entry_price - stop_loss)
- entry_price = current price
- stop_loss = nearest validated support (S1 or S2)
- target_price = nearest validated resistance (R1 or R2)
- Assess signal as BUY (clear bullish setup), WAIT (mixed signals), or AVOID (bearish)

Respond ONLY with valid JSON matching this exact schema:
{
  "ticker": string,
  "signal": "BUY" | "WAIT" | "AVOID",
  "confidence": float (0.0-1.0),
  "entry_price": float,
  "target_price": float,
  "stop_loss": float,
  "risk_reward_ratio": float,
  "support_validated": boolean,
  "indicators_summary": {"macd": string, "rsi": float, "volume": string},
  "argument": string (2-4 sentences explaining the setup)
}"""


def _build_messages(indicators: TechnicalIndicators, screenshot: bytes | None) -> list[dict]:
    """Build the LLM messages list with optional vision content."""
    numeric_text = (
        f"Ticker: {indicators.ticker}\n"
        f"Current Price: ${indicators.current_price:.2f}\n"
        f"MACD Signal: {indicators.macd_signal} (histogram: {indicators.macd_histogram})\n"
        f"RSI(14): {indicators.rsi:.1f}\n"
        f"Volume Ratio vs 20D SMA: {indicators.volume_ratio:.2f}x\n"
        f"Support S1: ${indicators.support_1:.2f} | S2: ${indicators.support_2:.2f}\n"
        f"Resistance R1: ${indicators.resistance_1:.2f} | R2: ${indicators.resistance_2:.2f}\n"
    )

    if screenshot is not None:
        b64 = base64.b64encode(screenshot).decode()
        user_content = [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": f"Numerical indicators:\n{numeric_text}\nAnalyze and respond with JSON."},
        ]
    else:
        user_content = (
            f"No chart screenshot available. Use only numerical indicators:\n"
            f"{numeric_text}\nAnalyze and respond with JSON."
        )

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _degraded_result(ticker: str) -> AssetAnalysis:
    return AssetAnalysis(
        ticker=ticker,
        signal="AVOID",
        confidence=0.0,
        entry_price=0.0,
        target_price=0.0,
        stop_loss=0.0,
        risk_reward_ratio=0.0,
        support_validated=False,
        indicators_summary={},
        argument="Analysis unavailable due to an error.",
    )


async def analyze_asset(
    indicators: TechnicalIndicators,
    screenshot: bytes | None,
) -> AssetAnalysis:
    """Call the LLM to analyze one asset. Never raises — returns degraded result on error."""
    messages = _build_messages(indicators, screenshot)

    try:
        response = await asyncio.to_thread(
            completion,
            model=MODEL,
            messages=messages,
            reasoning_effort="low",
            extra_body=EXTRA_BODY,
        )
        content = response.choices[0].message.content
        result = AssetAnalysis.model_validate_json(content)

        # Force support_validated=False when no screenshot was provided
        if screenshot is None:
            result = result.model_copy(update={"support_validated": False})

        return result

    except (ValidationError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("VisionAgent parse error for %s: %s", indicators.ticker, exc)
        return _degraded_result(indicators.ticker)
    except Exception as exc:
        logger.warning("VisionAgent LLM error for %s: %s", indicators.ticker, exc)
        return _degraded_result(indicators.ticker)
```

- [ ] **Step 4: Run tests**

```bash
cd backend
uv run --extra dev pytest tests/analysis/test_vision_agent.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/analysis/vision_agent.py backend/tests/analysis/test_vision_agent.py
git commit -m "feat: add VisionAgent with LLM vision analysis and graceful degradation"
```

---

## Task 8: ScoringAgent

**Files:**
- Create: `backend/app/analysis/scoring_agent.py`
- Create: `backend/tests/analysis/test_scoring_agent.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/analysis/test_scoring_agent.py`:

```python
"""Tests for ScoringAgent — filter, score, and rank assets."""

import pytest

from app.analysis.models import AssetAnalysis
from app.analysis.scoring_agent import score_and_rank


def _make_analysis(
    ticker: str,
    signal: str = "BUY",
    confidence: float = 0.8,
    rr_ratio: float = 4.0,
    support_validated: bool = True,
    macd: str = "bullish_crossover",
    rsi: float = 55.0,
    volume: str = "above_avg",
) -> AssetAnalysis:
    return AssetAnalysis(
        ticker=ticker,
        signal=signal,
        confidence=confidence,
        entry_price=100.0,
        target_price=130.0,
        stop_loss=90.0,
        risk_reward_ratio=rr_ratio,
        support_validated=support_validated,
        indicators_summary={"macd": macd, "rsi": rsi, "volume": volume},
        argument="Test argument.",
    )


def test_filters_below_min_rr():
    assets = [
        _make_analysis("AAPL", rr_ratio=2.9),  # below 3.0
        _make_analysis("MSFT", rr_ratio=3.0),  # exactly at limit — passes
    ]
    ranked = score_and_rank(assets, min_rr=3.0, top_n=5)
    qualifiers = [a for a in ranked if a.rank is not None]
    assert len(qualifiers) == 1
    assert qualifiers[0].ticker == "MSFT"


def test_filters_avoid_signal():
    assets = [
        _make_analysis("AAPL", signal="AVOID"),
        _make_analysis("MSFT", signal="BUY"),
    ]
    ranked = score_and_rank(assets, min_rr=3.0, top_n=5)
    qualifiers = [a for a in ranked if a.rank is not None]
    assert len(qualifiers) == 1
    assert qualifiers[0].ticker == "MSFT"


def test_ranked_by_score_descending():
    assets = [
        _make_analysis("LOW", confidence=0.5, rr_ratio=3.0),
        _make_analysis("HIGH", confidence=0.9, rr_ratio=5.0),
        _make_analysis("MID", confidence=0.7, rr_ratio=4.0),
    ]
    ranked = score_and_rank(assets, min_rr=3.0, top_n=5)
    qualifiers = [a for a in ranked if a.rank is not None]
    assert qualifiers[0].ticker == "HIGH"
    assert qualifiers[-1].ticker == "LOW"


def test_top_n_limits_ranked_count():
    assets = [_make_analysis(f"T{i}", rr_ratio=3.0 + i) for i in range(8)]
    ranked = score_and_rank(assets, min_rr=3.0, top_n=5)
    qualifiers = [a for a in ranked if a.rank is not None]
    assert len(qualifiers) == 5


def test_zero_qualifying_assets_returns_all_unranked():
    assets = [_make_analysis("AAPL", signal="AVOID"), _make_analysis("MSFT", rr_ratio=1.0)]
    ranked = score_and_rank(assets, min_rr=3.0, top_n=5)
    assert all(a.rank is None for a in ranked)


def test_wait_signal_qualifies():
    assets = [_make_analysis("AAPL", signal="WAIT", rr_ratio=3.5)]
    ranked = score_and_rank(assets, min_rr=3.0, top_n=5)
    qualifiers = [a for a in ranked if a.rank is not None]
    assert len(qualifiers) == 1


def test_score_uses_indicator_confluence():
    # All bullish → higher score than partial
    all_bullish = _make_analysis(
        "FULL", confidence=0.8, rr_ratio=4.0,
        macd="bullish_crossover", rsi=55.0, volume="above_avg"
    )
    partial = _make_analysis(
        "PART", confidence=0.8, rr_ratio=4.0,
        macd="neutral", rsi=75.0, volume="below_avg"
    )
    ranked = score_and_rank([all_bullish, partial], min_rr=3.0, top_n=5)
    full_score = next(a.score for a in ranked if a.ticker == "FULL")
    part_score = next(a.score for a in ranked if a.ticker == "PART")
    assert full_score > part_score
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend
uv run --extra dev pytest tests/analysis/test_scoring_agent.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement scoring_agent.py**

Create `backend/app/analysis/scoring_agent.py`:

```python
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
```

- [ ] **Step 4: Run tests**

```bash
cd backend
uv run --extra dev pytest tests/analysis/test_scoring_agent.py -v
```

Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/analysis/scoring_agent.py backend/tests/analysis/test_scoring_agent.py
git commit -m "feat: add ScoringAgent with R/R filter, score formula, and ranking"
```

---

## Task 9: Orchestrator

**Files:**
- Create: `backend/app/analysis/orchestrator.py`
- Create: `backend/tests/analysis/test_orchestrator.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/analysis/test_orchestrator.py`:

```python
"""Tests for OrchestratorAgent — coordinates all analysis stages."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from app.analysis.models import AssetAnalysis, DataFetchError, TechnicalIndicators
from app.analysis.orchestrator import run_analysis

_INDICATORS = TechnicalIndicators(
    ticker="NVDA", current_price=890.0, macd_signal="bullish_crossover",
    macd_histogram=0.5, rsi=58.0, volume_ratio=1.3,
    support_1=875.0, support_2=860.0, resistance_1=920.0, resistance_2=940.0,
)

_ANALYSIS = AssetAnalysis(
    ticker="NVDA", signal="BUY", confidence=0.85, entry_price=890.0,
    target_price=920.0, stop_loss=875.0, risk_reward_ratio=4.0,
    support_validated=True, indicators_summary={"macd": "bullish_crossover", "rsi": 58.0, "volume": "above_avg"},
    argument="Strong bullish setup.",
)


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.fetch_indicators", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.analyze_asset", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_run_analysis_returns_analysis_result(mock_save, mock_vision, mock_data):
    mock_data.return_value = _INDICATORS
    mock_vision.return_value = _ANALYSIS.model_copy(update={"rank": 1, "score": 88.0})

    result = await run_analysis(["NVDA"])

    assert result.run_id is not None
    assert len(result.assets) == 1
    assert result.errors == []
    mock_save.assert_called_once()


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.fetch_indicators", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.analyze_asset", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_data_fetch_error_is_isolated(mock_save, mock_vision, mock_data):
    """A DataFetchError for one ticker should not abort the whole run."""
    mock_data.side_effect = [DataFetchError("FAKE"), _INDICATORS]
    mock_vision.return_value = _ANALYSIS

    result = await run_analysis(["FAKE", "NVDA"])

    assert len(result.errors) == 1
    assert result.errors[0]["ticker"] == "FAKE"
    assert len(result.assets) == 1  # NVDA succeeded


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
@patch("app.analysis.orchestrator.fetch_indicators", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.analyze_asset", new_callable=AsyncMock)
@patch("app.analysis.orchestrator.save_analysis_results", new_callable=AsyncMock)
async def test_duration_seconds_is_positive(mock_save, mock_vision, mock_data):
    mock_data.return_value = _INDICATORS
    mock_vision.return_value = _ANALYSIS

    result = await run_analysis(["NVDA"])
    assert result.duration_seconds >= 0
```

- [ ] **Step 2: Run to verify failure**

```bash
cd backend
uv run --extra dev pytest tests/analysis/test_orchestrator.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement orchestrator.py**

Create `backend/app/analysis/orchestrator.py`:

```python
"""OrchestratorAgent — coordinates the 4-stage analysis pipeline."""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

from app.db import save_analysis_results

from .data_agent import fetch_indicators
from .models import AnalysisResult, AssetAnalysis, DataFetchError, TechnicalIndicators
from .scoring_agent import score_and_rank
from .screenshot_agent import capture_charts
from .vision_agent import analyze_asset

logger = logging.getLogger(__name__)


async def _fetch_one(ticker: str) -> tuple[str, TechnicalIndicators | None, str | None]:
    """Fetch indicators for one ticker. Returns (ticker, result_or_None, error_or_None)."""
    try:
        indicators = await fetch_indicators(ticker)
        return ticker, indicators, None
    except DataFetchError as exc:
        return ticker, None, str(exc)
    except Exception as exc:
        logger.warning("Unexpected error fetching %s: %s", ticker, exc)
        return ticker, None, str(exc)


async def run_analysis(tickers: list[str]) -> AnalysisResult:
    """Run the full 4-stage analysis pipeline and return an AnalysisResult.

    Saves all results to the DB before returning.
    """
    run_id = str(uuid.uuid4())
    start = time.monotonic()
    errors: list[dict] = []

    # Stage 1: Parallel indicator fetch
    logger.info("Stage 1: fetching indicators for %d tickers", len(tickers))
    fetch_tasks = [_fetch_one(t) for t in tickers]
    fetch_results = await asyncio.gather(*fetch_tasks)

    successful: dict[str, TechnicalIndicators] = {}
    for ticker, indicators, error in fetch_results:
        if indicators is not None:
            successful[ticker] = indicators
        else:
            errors.append({"ticker": ticker, "error_message": error or "Unknown error"})

    if not successful:
        return AnalysisResult(
            run_id=run_id,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            assets=[],
            top_5=[],
            errors=errors,
            duration_seconds=round(time.monotonic() - start, 2),
        )

    # Stage 2: Sequential screenshots (single Playwright session)
    logger.info("Stage 2: capturing screenshots for %d tickers", len(successful))
    screenshots: dict[str, bytes | None] = {}
    try:
        screenshots = await capture_charts(list(successful.keys()))
    except Exception as exc:
        logger.error("Screenshot capture failed: %s", exc)
        screenshots = {t: None for t in successful}

    # Stage 3: Parallel vision analysis
    logger.info("Stage 3: running vision analysis for %d tickers", len(successful))

    async def _vision_one(ticker: str) -> AssetAnalysis:
        indicators = successful[ticker]
        screenshot = screenshots.get(ticker)
        return await analyze_asset(indicators, screenshot)

    vision_tasks = [_vision_one(t) for t in successful]
    analyses: list[AssetAnalysis] = await asyncio.gather(*vision_tasks)

    # Stage 4: Score and rank
    logger.info("Stage 4: scoring and ranking %d analyses", len(analyses))
    ranked = score_and_rank(analyses)
    top_5 = [a for a in ranked if a.rank is not None]

    # Persist results
    db_rows = [a.to_db_row(run_id) for a in ranked]
    await save_analysis_results(db_rows)

    duration = round(time.monotonic() - start, 2)
    logger.info("Analysis complete in %.1fs — %d top opportunities", duration, len(top_5))

    return AnalysisResult(
        run_id=run_id,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        assets=ranked,
        top_5=top_5,
        errors=errors,
        duration_seconds=duration,
    )
```

- [ ] **Step 4: Run tests**

```bash
cd backend
uv run --extra dev pytest tests/analysis/test_orchestrator.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Run full analysis test suite**

```bash
cd backend
uv run --extra dev pytest tests/analysis/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/analysis/orchestrator.py backend/tests/analysis/test_orchestrator.py
git commit -m "feat: add OrchestratorAgent coordinating 4-stage analysis pipeline"
```

---

## Task 10: API routes

**Files:**
- Create: `backend/app/routes/analysis.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create analysis.py router**

Create `backend/app/routes/analysis.py`:

```python
"""FastAPI routes for the technical analysis feature."""

import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import (
    add_analysis_ticker,
    get_analysis_by_ticker,
    get_analysis_tickers,
    get_latest_analysis,
    remove_analysis_ticker,
)
from app.analysis.models import InvestingComAuthError
from app.analysis.orchestrator import run_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class RunRequest(BaseModel):
    tickers: list[str] | None = None


class AddTickerRequest(BaseModel):
    ticker: str


@router.post("/run")
async def trigger_analysis(body: RunRequest):
    """Trigger a full analysis run. Uses configured tickers if none provided."""
    tickers = body.tickers
    if not tickers:
        tickers = await get_analysis_tickers()
    if not tickers:
        raise HTTPException(status_code=422, detail="No tickers configured for analysis")

    tickers = [t.upper() for t in tickers]

    try:
        result = await run_analysis(tickers)
    except InvestingComAuthError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to investing.com: {exc}. Check INVESTING_COM_EMAIL and INVESTING_COM_PASSWORD in .env",
        )

    return {
        "run_id": result.run_id,
        "analyzed_at": result.analyzed_at,
        "duration_seconds": result.duration_seconds,
        "top_5": [a.model_dump() for a in result.top_5],
        "assets": [a.model_dump() for a in result.assets],
        "errors": result.errors,
    }


@router.get("/latest")
async def get_latest():
    """Return the most recent cached analysis results."""
    rows = await get_latest_analysis()
    return {"results": rows}


@router.get("/tickers")
async def list_tickers():
    """Return the current list of tickers configured for analysis."""
    tickers = await get_analysis_tickers()
    return {"tickers": tickers}


@router.post("/tickers")
async def add_ticker(body: AddTickerRequest):
    """Add a ticker to the analysis list."""
    ticker = body.ticker.upper()
    if not ticker.isalpha() or len(ticker) > 10:
        raise HTTPException(status_code=422, detail=f"Invalid ticker: {ticker}")
    added = await add_analysis_ticker(ticker)
    return {"ticker": ticker, "added": added}


@router.delete("/tickers/{ticker}")
async def remove_ticker(ticker: str):
    """Remove a ticker from the analysis list."""
    ticker = ticker.upper()
    removed = await remove_analysis_ticker(ticker)
    if not removed:
        raise HTTPException(status_code=404, detail=f"{ticker} not in analysis list")
    return {"ticker": ticker, "removed": True}


@router.get("/{ticker}")
async def get_ticker_analysis(ticker: str):
    """Return the latest analysis result for a specific ticker."""
    ticker = ticker.upper()
    result = await get_analysis_by_ticker(ticker)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"No analysis found for {ticker}. Run /api/analysis/run first."
        )
    return result
```

- [ ] **Step 2: Register router in main.py**

In `backend/app/main.py`, add the import and router registration:

```python
from app.routes import analysis, chat, portfolio, watchlist

# ...existing code...

# API routes
app.include_router(portfolio.router)
app.include_router(watchlist.router)
app.include_router(chat.router)
app.include_router(analysis.router)   # ← add this line
```

- [ ] **Step 3: Verify server starts**

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 &
sleep 3
curl -s http://localhost:8001/api/analysis/tickers
kill %1
```

Expected: JSON response with 10 tickers.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routes/analysis.py backend/app/main.py
git commit -m "feat: add analysis API routes (run, latest, tickers CRUD, per-ticker)"
```

---

## Task 11: Frontend types and API client

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Add types to types.ts**

Append to `frontend/lib/types.ts`:

```typescript
/** Technical analysis signal */
export type AnalysisSignal = "BUY" | "WAIT" | "AVOID";

/** Single asset analysis result */
export interface AssetAnalysis {
  ticker: string;
  signal: AnalysisSignal;
  confidence: number;
  entry_price: number;
  target_price: number;
  stop_loss: number;
  risk_reward_ratio: number;
  support_validated: boolean;
  indicators_summary: Record<string, unknown>;
  argument: string;
  score: number | null;
  rank: number | null;
  analyzed_at?: string;
}

/** Response from POST /api/analysis/run */
export interface AnalysisRunResponse {
  run_id: string;
  analyzed_at: string;
  duration_seconds: number;
  top_5: AssetAnalysis[];
  assets: AssetAnalysis[];
  errors: Array<{ ticker: string; error_message: string }>;
}

/** Response from GET /api/analysis/latest */
export interface AnalysisLatestResponse {
  results: AssetAnalysis[];
}
```

- [ ] **Step 2: Add API functions to api.ts**

Append to `frontend/lib/api.ts`:

```typescript
import type {
  // ...existing imports...
  AnalysisRunResponse,
  AnalysisLatestResponse,
  AssetAnalysis,
} from "./types";

export async function runAnalysis(tickers?: string[]): Promise<AnalysisRunResponse> {
  return request<AnalysisRunResponse>("/analysis/run", {
    method: "POST",
    body: JSON.stringify({ tickers: tickers ?? null }),
  });
}

export async function getLatestAnalysis(): Promise<AnalysisLatestResponse> {
  return request<AnalysisLatestResponse>("/analysis/latest");
}

export async function getTickerAnalysis(ticker: string): Promise<AssetAnalysis> {
  return request<AssetAnalysis>(`/analysis/${ticker}`);
}

export async function getAnalysisTickers(): Promise<{ tickers: string[] }> {
  return request<{ tickers: string[] }>("/analysis/tickers");
}

export async function addAnalysisTicker(ticker: string): Promise<void> {
  await request("/analysis/tickers", {
    method: "POST",
    body: JSON.stringify({ ticker }),
  });
}

export async function removeAnalysisTicker(ticker: string): Promise<void> {
  await request(`/analysis/tickers/${ticker}`, { method: "DELETE" });
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts
git commit -m "feat: add analysis types and API client functions to frontend"
```

---

## Task 12: Frontend hook

**Files:**
- Create: `frontend/lib/use-analysis.ts`

- [ ] **Step 1: Create use-analysis.ts**

Create `frontend/lib/use-analysis.ts`:

```typescript
"use client";

import { useCallback, useEffect, useState } from "react";
import {
  addAnalysisTicker,
  getLatestAnalysis,
  getTickerAnalysis,
  runAnalysis,
} from "./api";
import type { AssetAnalysis } from "./types";

type AnalysisStatus = "idle" | "running" | "done" | "error";

interface UseAnalysisReturn {
  results: AssetAnalysis[];
  top5: AssetAnalysis[];
  status: AnalysisStatus;
  lastAnalyzedAt: string | null;
  errorMessage: string | null;
  triggerRun: () => Promise<void>;
  addTicker: (ticker: string) => Promise<void>;
  getArgument: (ticker: string) => Promise<string | null>;
}

export function useAnalysis(): UseAnalysisReturn {
  const [results, setResults] = useState<AssetAnalysis[]>([]);
  const [status, setStatus] = useState<AnalysisStatus>("idle");
  const [lastAnalyzedAt, setLastAnalyzedAt] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const top5 = results.filter((a) => a.rank !== null).sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99));

  // Load cached results on mount
  useEffect(() => {
    getLatestAnalysis()
      .then(({ results: rows }) => {
        if (rows.length > 0) {
          setResults(rows);
          setLastAnalyzedAt(rows[0].analyzed_at ?? null);
          setStatus("done");
        }
      })
      .catch(() => {
        // No cached results yet — stay idle
      });
  }, []);

  const triggerRun = useCallback(async () => {
    setStatus("running");
    setErrorMessage(null);
    try {
      const data = await runAnalysis();
      setResults(data.assets);
      setLastAnalyzedAt(data.analyzed_at);
      setStatus("done");
    } catch (err: unknown) {
      setStatus("error");
      setErrorMessage(err instanceof Error ? err.message : "Analysis failed");
    }
  }, []);

  const addTicker = useCallback(async (ticker: string) => {
    await addAnalysisTicker(ticker.toUpperCase());
  }, []);

  const getArgument = useCallback(async (ticker: string): Promise<string | null> => {
    try {
      const data = await getTickerAnalysis(ticker);
      return data.argument;
    } catch {
      return null;
    }
  }, []);

  return { results, top5, status, lastAnalyzedAt, errorMessage, triggerRun, addTicker, getArgument };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/use-analysis.ts
git commit -m "feat: add useAnalysis hook with run, cache load, and addTicker"
```

---

## Task 13: OpportunitiesPanel component

**Files:**
- Create: `frontend/components/OpportunitiesPanel.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/components/OpportunitiesPanel.tsx`:

```typescript
"use client";

import { useCallback, useState } from "react";
import { useAnalysis } from "@/lib/use-analysis";
import type { AssetAnalysis } from "@/lib/types";

interface OpportunitiesPanelProps {
  onTickerSelect: (ticker: string) => void;
  onInjectChat: (message: string) => void;
}

function SignalBadge({ signal }: { signal: string }) {
  const colors: Record<string, string> = {
    BUY: "bg-green-900 text-green-300 border border-green-700",
    WAIT: "bg-yellow-900 text-yellow-300 border border-yellow-700",
    AVOID: "bg-red-900 text-red-300 border border-red-700",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold ${colors[signal] ?? ""}`}>
      {signal}
    </span>
  );
}

function ProgressLabel({ status }: { status: string }) {
  const labels: Record<string, string> = {
    idle: "",
    running: "Analizando...",
    done: "",
    error: "",
  };
  return labels[status] ? (
    <span className="text-xs text-text-muted animate-pulse">{labels[status]}</span>
  ) : null;
}

export default function OpportunitiesPanel({
  onTickerSelect,
  onInjectChat,
}: OpportunitiesPanelProps) {
  const { top5, results, status, lastAnalyzedAt, errorMessage, triggerRun, addTicker, getArgument } =
    useAnalysis();
  const [newTicker, setNewTicker] = useState("");
  const [addError, setAddError] = useState<string | null>(null);

  const handleRowClick = useCallback(
    async (asset: AssetAnalysis) => {
      onTickerSelect(asset.ticker);
      const arg = await getArgument(asset.ticker);
      if (arg) {
        onInjectChat(`Muéstrame el análisis técnico de ${asset.ticker}: ${arg}`);
      } else {
        onInjectChat(`Muéstrame el análisis técnico de ${asset.ticker}`);
      }
    },
    [onTickerSelect, onInjectChat, getArgument]
  );

  const handleAddTicker = useCallback(async () => {
    const t = newTicker.trim().toUpperCase();
    if (!t) return;
    setAddError(null);
    try {
      await addTicker(t);
      setNewTicker("");
    } catch {
      setAddError(`No se pudo agregar ${t}`);
    }
  }, [newTicker, addTicker]);

  const minutesAgo =
    lastAnalyzedAt
      ? Math.round((Date.now() - new Date(lastAnalyzedAt).getTime()) / 60_000)
      : null;

  return (
    <div className="flex flex-col h-full border-t border-border bg-bg-panel">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-accent-yellow">TOP OPORTUNIDADES</span>
          {minutesAgo !== null && (
            <span className="text-xs text-text-muted">
              actualizado hace {minutesAgo} min
            </span>
          )}
          <ProgressLabel status={status} />
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={triggerRun}
            disabled={status === "running"}
            className="px-3 py-1 text-xs bg-purple-secondary text-white rounded hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed font-mono"
          >
            {status === "running" ? "Analizando..." : "🔍 Analizar"}
          </button>
        </div>
      </div>

      {/* Error state */}
      {errorMessage && (
        <div className="mx-4 mt-2 px-3 py-2 bg-red-900/40 border border-red-700 rounded text-xs text-red-300">
          {errorMessage}
        </div>
      )}

      {/* Table */}
      <div className="flex-1 overflow-auto min-h-0">
        {top5.length === 0 && status !== "running" ? (
          <div className="flex items-center justify-center h-full text-text-muted text-sm">
            {status === "idle"
              ? 'Presiona "Analizar" para obtener oportunidades'
              : "Sin oportunidades con ratio ≥ 3:1"}
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-bg-panel border-b border-border">
              <tr className="text-text-muted text-left">
                <th className="px-3 py-2 w-8">#</th>
                <th className="px-3 py-2">Ticker</th>
                <th className="px-3 py-2">Score</th>
                <th className="px-3 py-2">R/R</th>
                <th className="px-3 py-2">Entry</th>
                <th className="px-3 py-2">Target</th>
                <th className="px-3 py-2">Stop</th>
                <th className="px-3 py-2">Señal</th>
              </tr>
            </thead>
            <tbody>
              {top5.map((asset) => (
                <tr
                  key={asset.ticker}
                  onClick={() => handleRowClick(asset)}
                  className="border-b border-border hover:bg-bg-hover cursor-pointer transition-colors"
                >
                  <td className="px-3 py-2 text-text-muted font-mono">{asset.rank}</td>
                  <td className="px-3 py-2 font-mono font-bold text-blue-primary">{asset.ticker}</td>
                  <td className="px-3 py-2 font-mono">{asset.score?.toFixed(0) ?? "—"}</td>
                  <td className="px-3 py-2 font-mono text-accent-yellow">
                    {asset.risk_reward_ratio.toFixed(1)}x
                  </td>
                  <td className="px-3 py-2 font-mono">${asset.entry_price.toFixed(2)}</td>
                  <td className="px-3 py-2 font-mono text-green-400">${asset.target_price.toFixed(2)}</td>
                  <td className="px-3 py-2 font-mono text-red-400">${asset.stop_loss.toFixed(2)}</td>
                  <td className="px-3 py-2">
                    <SignalBadge signal={asset.signal} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Add ticker input */}
      <div className="flex items-center gap-2 px-4 py-2 border-t border-border shrink-0">
        <input
          type="text"
          value={newTicker}
          onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === "Enter" && handleAddTicker()}
          placeholder="+ Agregar ticker (ej: PYPL)"
          className="flex-1 bg-bg-input border border-border rounded px-2 py-1 text-xs font-mono focus:outline-none focus:border-blue-primary"
        />
        <button
          onClick={handleAddTicker}
          className="px-2 py-1 text-xs bg-bg-hover border border-border rounded hover:border-blue-primary font-mono"
        >
          Agregar
        </button>
        {addError && <span className="text-xs text-red-400">{addError}</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/OpportunitiesPanel.tsx
git commit -m "feat: add OpportunitiesPanel component with table, controls, and chat injection"
```

---

## Task 14: Wire OpportunitiesPanel into page.tsx

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Update page.tsx**

In `frontend/app/page.tsx`, add the import and wire the panel. The panel goes below the main chart in the center column, above the bottom row. The full updated center column section:

```typescript
// Add import at top with other component imports
import OpportunitiesPanel from "@/components/OpportunitiesPanel";

// Add state for chat injection inside the Home component:
const [chatInjectedMessage, setChatInjectedMessage] = useState<string | null>(null);

// Update the return JSX center column — replace the existing center column div:
{/* Center: Charts + Opportunities + Positions */}
<div className="flex-1 flex flex-col min-w-0">
  {/* Top row: Price Chart + Portfolio Heatmap */}
  <div className="flex-[1] flex min-h-0">
    <div className="flex-[2] border-r border-border min-w-0">
      <PriceChart ticker={selectedTicker} getHistory={getHistory} />
    </div>
    <div className="flex-1 min-w-0">
      <PortfolioHeatmap positions={portfolio?.positions ?? []} />
    </div>
  </div>

  {/* Opportunities Panel */}
  <div className="h-48 border-t border-border shrink-0">
    <OpportunitiesPanel
      onTickerSelect={setUserSelectedTicker}
      onInjectChat={setChatInjectedMessage}
    />
  </div>

  {/* Bottom row: Positions + P&L Chart */}
  <div className="h-[35%] flex border-t border-border min-h-0">
    <div className="flex-1 border-r border-border min-w-0">
      <PositionsTable positions={portfolio?.positions ?? []} />
    </div>
    <div className="flex-1 min-w-0">
      <PnlChart />
    </div>
  </div>
</div>
```

Also update the ChatPanel to accept and clear the injected message. Pass it as a prop:

```typescript
<ChatPanel
  onTradeExecuted={refreshAll}
  injectedMessage={chatInjectedMessage}
  onInjectedMessageConsumed={() => setChatInjectedMessage(null)}
/>
```

- [ ] **Step 2: Update ChatPanel to accept injectedMessage prop**

In `frontend/components/ChatPanel.tsx`, add the prop interface additions and a `useEffect` that pre-fills and submits when `injectedMessage` changes. Read the file first, then add to the component interface:

```typescript
interface ChatPanelProps {
  onTradeExecuted: () => void;
  injectedMessage?: string | null;
  onInjectedMessageConsumed?: () => void;
}
```

And inside the component, add a `useEffect`:

```typescript
useEffect(() => {
  if (injectedMessage) {
    setInput(injectedMessage);
    onInjectedMessageConsumed?.();
  }
}, [injectedMessage, onInjectedMessageConsumed]);
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/page.tsx frontend/components/ChatPanel.tsx
git commit -m "feat: wire OpportunitiesPanel into main layout with chat injection"
```

---

## Task 15: Frontend test

**Files:**
- Create: `frontend/__tests__/OpportunitiesPanel.test.tsx`

- [ ] **Step 1: Write test**

Create `frontend/__tests__/OpportunitiesPanel.test.tsx`:

```typescript
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { jest } from "@jest/globals";
import OpportunitiesPanel from "@/components/OpportunitiesPanel";

// Mock the hook
jest.mock("@/lib/use-analysis", () => ({
  useAnalysis: () => ({
    top5: [
      {
        ticker: "NVDA",
        signal: "BUY",
        confidence: 0.85,
        entry_price: 890,
        target_price: 920,
        stop_loss: 875,
        risk_reward_ratio: 4.2,
        support_validated: true,
        indicators_summary: {},
        argument: "Strong bullish setup.",
        score: 88,
        rank: 1,
        analyzed_at: new Date().toISOString(),
      },
    ],
    results: [],
    status: "done",
    lastAnalyzedAt: new Date().toISOString(),
    errorMessage: null,
    triggerRun: jest.fn(),
    addTicker: jest.fn(),
    getArgument: jest.fn().mockResolvedValue("Strong bullish setup."),
  }),
}));

describe("OpportunitiesPanel", () => {
  it("renders top5 table with ticker row", () => {
    render(
      <OpportunitiesPanel
        onTickerSelect={jest.fn()}
        onInjectChat={jest.fn()}
      />
    );
    expect(screen.getByText("NVDA")).toBeInTheDocument();
    expect(screen.getByText("4.2x")).toBeInTheDocument();
    expect(screen.getByText("BUY")).toBeInTheDocument();
  });

  it("calls onTickerSelect and onInjectChat when row is clicked", async () => {
    const onTickerSelect = jest.fn();
    const onInjectChat = jest.fn();
    render(
      <OpportunitiesPanel
        onTickerSelect={onTickerSelect}
        onInjectChat={onInjectChat}
      />
    );
    fireEvent.click(screen.getByText("NVDA"));
    await waitFor(() => {
      expect(onTickerSelect).toHaveBeenCalledWith("NVDA");
      expect(onInjectChat).toHaveBeenCalledWith(expect.stringContaining("NVDA"));
    });
  });

  it("shows idle message when status is idle and no top5", () => {
    const { useAnalysis } = jest.requireMock("@/lib/use-analysis") as any;
    const original = useAnalysis();
    jest.spyOn(
      jest.requireMock("@/lib/use-analysis"),
      "useAnalysis"
    ).mockReturnValue({ ...original, top5: [], status: "idle" });

    render(
      <OpportunitiesPanel onTickerSelect={jest.fn()} onInjectChat={jest.fn()} />
    );
    expect(screen.getByText(/Presiona/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend
npm test -- --testPathPattern=OpportunitiesPanel --watchAll=false
```

Expected: 3 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/__tests__/OpportunitiesPanel.test.tsx
git commit -m "test: add OpportunitiesPanel component tests"
```

---

## Task 16: Dockerfile update

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Add Playwright Chromium install**

In the `Dockerfile`, after `uv sync --frozen --no-dev`, add:

```dockerfile
# Stage 2: Python backend + static frontend
FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app/backend

# Install Python dependencies (README.md needed by hatchling build)
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev

# Install Playwright Chromium and its system dependencies
RUN uv run playwright install chromium --with-deps

# Copy backend source
COPY backend/ ./

# Copy frontend static build output
COPY --from=frontend-build /app/frontend/out ./static/

# Create db directory for SQLite volume mount
RUN mkdir -p /app/db

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Build Docker image to verify**

```bash
cd ..   # project root (finally/)
docker build -t finally-test .
```

Expected: build succeeds. Note: Chromium install adds ~500MB to image.

- [ ] **Step 3: Commit**

```bash
git add Dockerfile
git commit -m "feat: add playwright chromium install to Dockerfile for screenshot capture"
```

---

## Task 17: Environment variable documentation

**Files:**
- Modify: `finally/.env.example` (or create if missing)

- [ ] **Step 1: Update .env.example**

Add to `.env.example`:

```bash
# Required: OpenRouter API key for LLM chat and analysis
OPENROUTER_API_KEY=your-openrouter-api-key-here

# Optional: Massive (Polygon.io) API key for real market data
MASSIVE_API_KEY=

# Optional: Set to "true" for deterministic mock LLM responses (testing)
LLM_MOCK=false

# Optional: Set to "true" to skip Playwright browser launch (testing)
PLAYWRIGHT_MOCK=false

# Required for technical analysis chart screenshots
INVESTING_COM_EMAIL=your@email.com
INVESTING_COM_PASSWORD=yourpassword

# Optional: Chart timeframe for investing.com screenshots (1D, 1W, 1M)
INVESTING_COM_CHART_INTERVAL=1D

# Optional: Minimum risk/reward ratio to qualify (default: 3.0)
ANALYSIS_MIN_RR_RATIO=3.0

# Optional: Number of top opportunities to surface (default: 5)
ANALYSIS_TOP_N=5
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add investing.com and analysis env vars to .env.example"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Hybrid data: yfinance numeric (Task 5) + investing.com visual (Task 6)
- [x] Screenshots via Playwright with login (Task 6)
- [x] On-demand trigger + SQLite cache + manual refresh (Tasks 9, 10, 12)
- [x] Dedicated panel below main chart (Task 13, 14)
- [x] Numerical pivot points + LLM visual validation (Tasks 5, 7)
- [x] 4-stage pipeline: parallel → sequential → parallel → scoring (Task 9)
- [x] R/R ≥ 3.0 filter (Task 8)
- [x] Top 5 display (Task 8, 13)
- [x] Click row → select ticker + inject analysis into chat (Tasks 13, 14)
- [x] Add ticker to analysis list (Tasks 3, 10, 12, 13)
- [x] All 6 API endpoints (Task 10)
- [x] DB tables analysis_results + analysis_tickers (Task 2, 3)
- [x] Mock modes: LLM_MOCK + PLAYWRIGHT_MOCK (Tasks 6, 7)
- [x] Dockerfile Chromium install (Task 16)
- [x] InvestingComAuthError → HTTP 503 (Task 10)

**No placeholders found.**

**Type consistency verified:** `AssetAnalysis.to_db_row()` returns dict matching `save_analysis_results()` parameter shape. `TechnicalIndicators` frozen dataclass used consistently across data_agent → vision_agent → orchestrator.
