# FinAlly — Technical Analysis Multi-Agent System

## Overview

This document defines the multi-agent design pattern, technology stack, tools, and implementation considerations for the Technical Analysis feature in FinAlly. It serves as the shared contract for any agent implementing `backend/app/analysis/`.

Reference spec: `docs/superpowers/specs/2026-04-11-technical-analysis-multiagent-design.md`

---

## Design Pattern: Staged Fan-out Pipeline

The system uses a **Staged Fan-out Pipeline** pattern — a common pattern for AI agent orchestration where:

1. Independent work is parallelized across agents
2. Shared bottlenecks (browser session) are serialized in a dedicated stage
3. Results are aggregated by a single scoring agent

This pattern is preferred over a pure sequential pipeline (too slow) and a fully parallel pipeline (browser resource contention).

```
Orchestrator
    │
    ├── Stage 1: Fan-out (parallel asyncio tasks)
    │   └── DataAgent × N tickers
    │
    ├── Stage 2: Serialized resource (single session)
    │   └── ScreenshotAgent (one Playwright browser)
    │
    ├── Stage 3: Fan-out (parallel asyncio tasks)
    │   └── VisionAgent × N tickers
    │
    └── Stage 4: Aggregation (single)
        └── ScoringAgent → Top 5 ranked results
```

### Key principle: per-asset error isolation

Each agent wraps its per-ticker work in a try/except. A failure for one ticker (e.g., investing.com doesn't have it, yfinance returns no data) does NOT abort the full run. The orchestrator collects partial results and includes an `errors` list in the response.

---

## Agents

### OrchestratorAgent (`orchestrator.py`)

**Purpose:** Coordinates the 4 stages. Owns the lifecycle of a single analysis run.

**Inputs:** List of tickers, user_id  
**Outputs:** `AnalysisResult` (persisted to SQLite, returned to API)

**Responsibilities:**
- Launch Stage 1 with `asyncio.gather`
- Pass Stage 1 results + Stage 2 results to Stage 3
- Invoke Stage 4 with all completed analyses
- Persist final results to `analysis_results` table with a shared `run_id`
- Surface per-asset errors without aborting the run

**Does NOT:**
- Know about HTTP — it is invoked by the FastAPI route handler, not the other way around
- Retry failed agents (fail fast, surface error)

---

### DataAgent (`data_agent.py`)

**Purpose:** Fetches historical price data and computes technical indicators numerically.

**Inputs:** Single ticker (str)  
**Outputs:** `TechnicalIndicators` dataclass

**Tools used:**
- `yfinance` — fetch 60 days of daily OHLCV data (free, no API key)
- `pandas-ta` — compute MACD (12/26/9), RSI (14), Volume SMA (20), Pivot Points (20-period High/Low)

**Signal rules:**
| Indicator | Bullish condition |
|---|---|
| MACD | MACD line > signal line AND histogram > 0 |
| RSI | 40 ≤ RSI ≤ 65 (entry zone; >70 = overbought, avoid) |
| Volume | Current volume > 1.2× 20-day SMA |
| Pivot S1 | Most recent 20-period low (stop loss candidate) |
| Pivot R1 | Most recent 20-period high (target candidate) |

**Error handling:** If yfinance returns empty data (ticker not found, market closed), raises `DataFetchError(ticker)`. Orchestrator catches and records in `errors`.

---

### ScreenshotAgent (`screenshot_agent.py`)

**Purpose:** Captures chart screenshots from investing.com for all tickers in a single browser session.

**Inputs:** List of tickers, chart interval (from env)  
**Outputs:** `dict[str, bytes]` — ticker → PNG screenshot bytes (None if ticker not found)

**Tools used:**
- `playwright` (async API, headless Chromium)
- `INVESTING_COM_EMAIL` / `INVESTING_COM_PASSWORD` env vars

**Flow:**
1. Launch Chromium (headless=True)
2. Login once at `https://www.investing.com` — reuse session for all tickers
3. For each ticker: navigate to equity chart page → set interval → `wait_for_load_state("networkidle")` → screenshot chart region
4. Return dict; close browser

**Ticker slug resolution:** investing.com URLs use slugs (e.g., `apple-computer-inc` for AAPL). Maintain a hardcoded mapping for the default 10 tickers; for unknown tickers, attempt `https://www.investing.com/search/?q={ticker}` to find the slug.

**Critical considerations:**
- investing.com may change its HTML structure. Use stable CSS selectors where possible (chart canvas element IDs tend to be stable).
- Do NOT parallelize browser tabs — sequential navigation in one browser is faster and less resource-intensive than multiple browser instances in a container.
- Per-ticker timeout: 30 seconds. On timeout, record `None` for that ticker and continue.
- Login failure raises `InvestingComAuthError` — propagated as HTTP 503 by the API route.

**Testing:** Use a Playwright mock (`AsyncMock`) in tests. Never connect to investing.com in CI.

---

### VisionAgent (`vision_agent.py`)

**Purpose:** Analyzes a chart screenshot combined with numerical indicators to produce trading signals, validated support/resistance levels, and a narrative argument.

**Inputs:** Ticker, `TechnicalIndicators`, screenshot bytes (or None)  
**Outputs:** `AssetAnalysis` Pydantic model

**Tools used:**
- LiteLLM → OpenRouter → Cerebras inference
- Model: `openrouter/openai/gpt-oss-120b`
- Pattern: cerebras-inference skill (`finally/.claude/skills/cerebras/SKILL.md`)
- Structured output via `response_format=AssetAnalysis`

**Prompt strategy:**
- System: expert technical analyst role, instructions to validate S/R visually and calculate R/R ratio
- User: base64-encoded screenshot (if available) + serialized `TechnicalIndicators` as JSON
- If screenshot is None: text-only prompt, `support_validated` forced to `False` in output

**Structured output fields:**
```python
class AssetAnalysis(BaseModel):
    ticker: str
    signal: Literal["BUY", "WAIT", "AVOID"]
    confidence: float           # 0.0–1.0
    entry_price: float
    target_price: float
    stop_loss: float
    risk_reward_ratio: float    # (target - entry) / (entry - stop_loss)
    support_validated: bool
    indicators_summary: dict    # keys: macd, rsi, volume
    argument: str               # 2–4 sentence narrative for chat display
```

**Error handling:** If LLM returns malformed JSON or validation fails, return a default `AssetAnalysis` with `signal="AVOID"`, `confidence=0`, `argument="Analysis unavailable"`. Never raise from VisionAgent — always return a usable (if degraded) result.

---

### ScoringAgent (`scoring_agent.py`)

**Purpose:** Filters, scores, and ranks asset analyses to produce the Top 5 opportunities.

**Inputs:** List of `AssetAnalysis`  
**Outputs:** List of `AssetAnalysis` with `rank` assigned (1–5), sorted by score descending

**Filter criteria (all must pass to qualify):**
- `risk_reward_ratio >= ANALYSIS_MIN_RR_RATIO` (default: 3.0, from env)
- `signal in ["BUY", "WAIT"]`
- `signal != "AVOID"`

**Score formula (0–100):**
```
score = (confidence × 40)
      + (min(rr_ratio / 6.0, 1.0) × 100 × 0.35)
      + (indicator_confluence_score × 25)

indicator_confluence_score:
  = count_of_bullish_signals / 3 × 100
  where bullish signals = [macd_bullish, rsi_in_entry_zone, volume_above_avg]
```

**Output contract:** Returns ALL analyses, not just Top 5. Assets that did not qualify have `rank=None`. The frontend decides whether to show non-qualifying assets.

---

## Data Models (`models.py`)

```python
from dataclasses import dataclass
from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime

@dataclass(frozen=True)
class TechnicalIndicators:
    ticker: str
    current_price: float
    macd_signal: str          # "bullish_crossover" | "bearish_crossover" | "neutral"
    macd_histogram: float
    rsi: float
    volume_ratio: float       # current volume / 20D SMA
    support_1: float
    support_2: float
    resistance_1: float
    resistance_2: float

class AssetAnalysis(BaseModel):
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
    score: Optional[float] = None
    rank: Optional[int] = None

class AnalysisResult(BaseModel):
    run_id: str
    analyzed_at: datetime
    assets: list[AssetAnalysis]   # all analyzed, ranked and unranked
    top_5: list[AssetAnalysis]    # filtered, sorted
    errors: list[dict]            # [{ticker, error_message}]
    duration_seconds: float
```

---

## Technology Stack

| Component | Technology | Why |
|---|---|---|
| Orchestration | Python `asyncio` | Native async, no extra framework needed; `asyncio.gather` for parallelism |
| Numeric data | `yfinance` | Free, no API key, reliable for daily OHLCV |
| Technical indicators | `pandas-ta` | Comprehensive TA library, pandas-native, well-maintained |
| Browser automation | `playwright` (async) | Modern, fast, async-native; headless Chromium in Docker |
| Vision + LLM | LiteLLM → OpenRouter → Cerebras | Already in project; same pattern as chat feature |
| Structured output | Pydantic `BaseModel` | Already in project (cerebras-inference skill pattern) |
| Persistence | SQLite (existing `finally.db`) | Consistent with project architecture |
| Frontend state | React hook (`useAnalysis.ts`) | Consistent with project patterns |

### New dependencies (`pyproject.toml`)

```toml
"yfinance>=0.2",
"pandas-ta>=0.3",
"playwright>=1.40",
```

### Dockerfile addition (Python stage)

```dockerfile
RUN playwright install chromium --with-deps
```

---

## API Contract

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/analysis/run` | none | Trigger analysis. Body: `{tickers?: string[]}` |
| `GET` | `/api/analysis/latest` | none | Latest cached result |
| `GET` | `/api/analysis/{ticker}` | none | Single ticker analysis (404 if not found) |
| `GET` | `/api/analysis/tickers` | none | Current analysis ticker list |
| `POST` | `/api/analysis/tickers` | none | Add ticker. Body: `{ticker: string}` |
| `DELETE` | `/api/analysis/tickers/{ticker}` | none | Remove ticker |

**Error codes:**
- `503` — investing.com login failed
- `422` — invalid ticker format
- `200` with `errors` array — partial success (some tickers failed)

---

## SQLite Schema

### `analysis_results`

```sql
CREATE TABLE analysis_results (
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
    support_validated INTEGER,
    argument TEXT,
    indicators_summary TEXT,  -- JSON
    screenshot_path TEXT,
    analyzed_at TEXT NOT NULL
);
```

### `analysis_tickers`

```sql
CREATE TABLE analysis_tickers (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    added_at TEXT NOT NULL,
    UNIQUE(user_id, ticker)
);
```

**Seed data:** Same 10 tickers as `watchlist` — AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX.

---

## Environment Variables

```bash
# Required for screenshot capture
INVESTING_COM_EMAIL=your@email.com
INVESTING_COM_PASSWORD=yourpassword

# Optional tuning (with defaults)
INVESTING_COM_CHART_INTERVAL=1D     # 1D | 1W | 1M
ANALYSIS_MIN_RR_RATIO=3.0           # Minimum risk/reward ratio to qualify
ANALYSIS_TOP_N=5                    # Number of top results to surface
```

---

## Testing Strategy

### Unit tests (`backend/tests/analysis/`)

| File | Coverage target |
|---|---|
| `test_data_agent.py` | MACD/RSI/pivot calculations with mocked yfinance; DataFetchError on empty data |
| `test_screenshot_agent.py` | Playwright mocked; login flow; per-ticker timeout handling; None on not-found |
| `test_vision_agent.py` | Structured output parsing; None screenshot fallback; malformed LLM response returns degraded result |
| `test_scoring_agent.py` | R/R filter threshold; score formula; ranking order; 0-qualifying-asset edge case |
| `test_orchestrator.py` | Per-asset error isolation; stage sequencing; partial results when N tickers fail |

### E2E tests (`test/`)

Run with `LLM_MOCK=true` and a dummy 1×1 PNG as the mock screenshot:

- Opportunities table renders on load (cached data)
- "Analizar" button triggers run, table updates to 5 rows
- Click row → main chart changes + chat shows argument
- Add ticker via input → included in next run
- Auth failure → inline error message, no crash

---

## Known Constraints & Considerations

1. **investing.com ToS** — Automated login and screenshot capture may violate terms of service. This feature is for personal/educational use only.

2. **Playwright in Docker** — Adding Chromium increases the image size by ~500MB. Consider a multi-stage build where Chromium is only installed in a "with-playwright" image variant if size is a concern.

3. **investing.com UI stability** — Chart selectors may break if investing.com updates its frontend. The `ScreenshotAgent` should use the most stable available selectors (canvas element IDs, not class names) and fail gracefully.

4. **yfinance rate limits** — yfinance proxies Yahoo Finance data. Batching requests and adding a short delay between tickers (~0.5s) avoids rate limiting. The 10-ticker default set stays well within free limits.

5. **LLM vision cost** — Each `VisionAgent` call sends a screenshot image. At 10 tickers per run, this is ~10 vision calls per analysis. With Cerebras/OpenRouter pricing this is acceptable but should be noted.

6. **Analysis freshness** — Results are cached indefinitely until a new run. The `analyzed_at` timestamp is always displayed to the user so they know how fresh the data is.

7. **Mock mode for testing** — `LLM_MOCK=true` must also mock Playwright. Add `PLAYWRIGHT_MOCK=true` env var that makes `ScreenshotAgent` return a 1×1 transparent PNG for all tickers without launching a browser.
