# FinAlly — Technical Analysis Multi-Agent Feature Design

**Date:** 2026-04-11
**Status:** Approved
**Feature:** AI-powered technical analysis with multi-agent orchestration, prioritized opportunities table, and investing.com chart integration

---

## 1. Overview

This document specifies the design for a multi-agent technical analysis subsystem added to the FinAlly trading workstation. The feature analyzes a configurable list of tech assets using MACD, RSI, Volume, and Support/Resistance levels, filters opportunities by a minimum 3:1 risk/reward ratio, and surfaces the Top 5 prioritized buy opportunities in a dedicated UI panel. Clicking any asset in the table injects the cached analysis argument into the AI chat.

---

## 2. User Experience

### Opportunities Panel

A new panel appears below the main chart area, coexisting with it. It contains:

- **Top Opportunities table** — ranks up to 5 assets with columns: Rank, Ticker, Score, R/R Ratio, Entry Price, Signal badge
- **"Analizar" button** — triggers on-demand analysis; disables with spinner and progress text (~40s estimate) while running
- **"↻ Refresh" button** — forces re-analysis using cached investing.com session if available; otherwise re-logs in
- **"Last analyzed: X min ago"** timestamp label
- **"+ Add ticker to analysis"** — text input with autocomplete to add new assets to the default list

### Interactions

**Click on table row:**
1. Selects the ticker in the main chart area
2. Injects a pre-filled message into the AI chat: *"Muéstrame el análisis técnico de {TICKER}"*
3. Chat responds with the `argument` field from the cached `analysis_results` row — no new LLM call

**Analizar button flow:**
1. Button disables, shows spinner
2. Progress label cycles: "Obteniendo datos…" → "Capturando gráficos…" → "Analizando con AI…"
3. On completion, table updates with fade-in animation
4. On error (investing.com unreachable, LLM failure), shows inline error message

**Add ticker:**
- Adds ticker to analysis list persisted in SQLite (`analysis_tickers` table)
- Included in next "Analizar" run
- If it scores Top 5, it appears in the table immediately after analysis

---

## 3. Architecture

### Agent Pipeline (4 Stages)

```
POST /api/analysis/run
        │
        ▼
┌─── OrchestratorAgent ─────────────────────────────────────┐
│                                                           │
│  Stage 1 — asyncio.gather (parallel, all tickers)        │
│  └── DataAgent × N → MACD, RSI, Volume, pivot points     │
│                                                           │
│  Stage 2 — sequential (single Playwright browser session) │
│  └── ScreenshotAgent → dict[ticker, screenshot_bytes]    │
│                                                           │
│  Stage 3 — asyncio.gather (parallel, all tickers)        │
│  └── VisionAgent × N → signals, S/R validated, argument  │
│                                                           │
│  Stage 4 — single                                        │
│  └── ScoringAgent → filter R/R ≥ 3.0, rank, Top 5       │
└───────────────────────────────────────────────────────────┘
        │
        ▼
  Persist to analysis_results (SQLite)
  Return JSON to frontend
```

### Module Layout

```
backend/app/analysis/
├── __init__.py
├── models.py           # Pydantic: TechnicalIndicators, AssetAnalysis, AnalysisResult
├── data_agent.py       # yfinance fetch + pandas-ta: MACD, RSI, Volume, pivot points
├── screenshot_agent.py # Playwright → investing.com login → chart screenshots
├── vision_agent.py     # LiteLLM vision call → structured AssetAnalysis output
├── scoring_agent.py    # Filter R/R ≥ 3.0, score formula, rank Top 5
└── orchestrator.py     # Coordinates 4 stages, per-asset error isolation
```

---

## 4. Data Agent

**Source:** `yfinance` — free, no API key required, fetches daily OHLCV history.

**Indicators computed with `pandas-ta`:**

| Indicator | Parameters | Signal rule |
|---|---|---|
| MACD | fast=12, slow=26, signal=9 | Bullish if MACD > signal line and histogram positive |
| RSI | period=14 | Oversold <40 (buy zone), Overbought >70 (avoid) |
| Volume | 20-day SMA | Bullish confirmation if current volume > 1.2× SMA |
| Pivot Points | High/Low of last 20 periods | S1/S2 (stop candidates), R1/R2 (target candidates) |

**Output per ticker:**
```python
@dataclass
class TechnicalIndicators:
    ticker: str
    current_price: float
    macd_signal: str          # "bullish_crossover" | "bearish_crossover" | "neutral"
    macd_histogram: float
    rsi: float
    volume_ratio: float       # current / 20D SMA
    support_1: float          # S1 pivot
    support_2: float          # S2 pivot
    resistance_1: float       # R1 pivot
    resistance_2: float       # R2 pivot
```

---

## 5. Screenshot Agent

**Tool:** Playwright (async, headless Chromium).

**Flow:**
1. Launch single `chromium` instance (headless)
2. Login to investing.com once using `INVESTING_COM_EMAIL` / `INVESTING_COM_PASSWORD`
3. For each ticker, navigate to the equity page, set chart interval (`INVESTING_COM_CHART_INTERVAL`, default `1D`), wait for `networkidle`, capture screenshot of chart region
4. Close browser, return `dict[str, bytes]`

**Error handling:**
- Ticker not found on investing.com → log warning, pass `None` screenshot; VisionAgent proceeds with numeric data only
- Login failure → raise `InvestingComAuthError`; orchestrator returns HTTP 503 with descriptive message
- Per-ticker timeout (30s) → skip screenshot for that ticker, continue

**Dockerfile addition (Stage 2 / Python):**
```dockerfile
RUN playwright install chromium --with-deps
```

---

## 6. Vision Agent

**Model:** Same as existing chat — `openrouter/openai/gpt-oss-120b` via Cerebras (LiteLLM + OpenRouter), using the `cerebras-inference` skill pattern.

**Input:** Screenshot bytes (base64) + `TechnicalIndicators` struct.

**System prompt excerpt:**
> "You are an expert technical analyst. Analyze the provided chart screenshot alongside the numerical indicators. Validate the support and resistance levels visible in the chart. Calculate the risk/reward ratio from current price to the nearest validated support (stop loss) and resistance (target). Respond only with valid JSON matching the required schema."

**Structured output schema:**
```python
class AssetAnalysis(BaseModel):
    ticker: str
    signal: Literal["BUY", "WAIT", "AVOID"]
    confidence: float           # 0.0–1.0
    entry_price: float
    target_price: float         # validated resistance
    stop_loss: float            # validated support
    risk_reward_ratio: float    # (target - entry) / (entry - stop)
    support_validated: bool     # LLM confirms S/R visible in chart
    indicators_summary: dict    # macd, rsi, volume keys
    argument: str               # narrative explanation, 2–4 sentences
```

**Fallback:** If screenshot is `None`, vision call is skipped; LLM receives numeric data only (text-only prompt). `support_validated` is set to `False`.

---

## 7. Scoring Agent

**Filter (mandatory):**
- `risk_reward_ratio >= 3.0`
- `signal in ["BUY", "WAIT"]`
- `support_validated == True` (unless no screenshot available, then accepted with penalty)

**Score formula (0–100):**
```
score = (confidence × 40) + (rr_ratio_normalized × 35) + (indicator_confluence × 25)

rr_ratio_normalized = min(rr_ratio / 6.0, 1.0) × 100   # cap at 6:1
indicator_confluence = count of bullish signals / 3 × 100  # MACD + RSI + Volume
```

**Output:** Sorted list of up to 5 `AssetAnalysis` objects with assigned ranks. Assets not meeting minimum R/R are included in the full response with `rank: null` so the frontend can optionally show them with a "Did not qualify" badge.

---

## 8. API Endpoints

### New endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/analysis/run` | Triggers full pipeline. Body: `{tickers?: string[]}`. Uses watchlist if omitted. Returns `AnalysisResult`. |
| `GET` | `/api/analysis/latest` | Returns most recent cached result from `analysis_results`. |
| `GET` | `/api/analysis/{ticker}` | Returns latest `AssetAnalysis` for a specific ticker (for chat injection). Returns 404 if no analysis exists yet. |
| `GET` | `/api/analysis/tickers` | Returns current list of tickers configured for analysis. |
| `POST` | `/api/analysis/tickers` | Adds a ticker to the analysis list. Body: `{ticker: string}`. |
| `DELETE` | `/api/analysis/tickers/{ticker}` | Removes a ticker from the analysis list. |

### Error responses

- `503` — investing.com login failed (auth error)
- `422` — invalid ticker in request body
- `200` with partial results — some tickers failed individually; response includes `errors` array

---

## 9. Database Schema Addition

### `analysis_results` table

| Column | Type | Description |
|---|---|---|
| `id` | TEXT PK | UUID |
| `user_id` | TEXT | default: `"default"` |
| `ticker` | TEXT | Asset symbol |
| `rank` | INTEGER | 1–5, or NULL if did not qualify |
| `score` | REAL | 0–100 composite score |
| `signal` | TEXT | `"BUY"` \| `"WAIT"` \| `"AVOID"` |
| `confidence` | REAL | 0.0–1.0 |
| `risk_reward_ratio` | REAL | Calculated R/R |
| `entry_price` | REAL | Price at analysis time |
| `target_price` | REAL | Validated resistance |
| `stop_loss` | REAL | Validated support |
| `argument` | TEXT | Narrative from VisionAgent |
| `indicators_summary` | TEXT | JSON blob |
| `screenshot_path` | TEXT | Path in `/tmp/` or NULL |
| `analyzed_at` | TEXT | ISO timestamp |
| `run_id` | TEXT | UUID grouping one full analysis run |

### `analysis_tickers` table

| Column | Type | Description |
|---|---|---|
| `id` | TEXT PK | UUID |
| `user_id` | TEXT | default: `"default"` |
| `ticker` | TEXT | Asset symbol |
| `added_at` | TEXT | ISO timestamp |

UNIQUE constraint on `(user_id, ticker)`.

**Default seed:** Same 10 tickers as watchlist — AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX.

---

## 10. Frontend Components

```
frontend/src/components/OpportunitiesPanel/
├── OpportunitiesPanel.tsx    # Root panel container, layout wrapper
├── OpportunitiesTable.tsx    # Table: rank, ticker, score, R/R, entry, signal badge
├── AnalysisControls.tsx      # "Analizar" button, Refresh, timestamp, Add ticker input
└── useAnalysis.ts            # Hook: GET /api/analysis/latest, POST /api/analysis/run
```

**`useAnalysis` hook responsibilities:**
- On mount: fetch `/api/analysis/latest` to populate table from cache
- `runAnalysis()`: POST `/api/analysis/run`, poll for completion, update state
- `addTicker(ticker)`: POST `/api/analysis/tickers`, refresh ticker list

**Chat injection on row click:**
- Parent component passes `onTickerSelect(ticker, argument)` callback
- OpportunitiesPanel calls it on row click
- Parent populates chat input with pre-filled message and submits against `/api/analysis/{ticker}` (returns cached argument, no LLM call)

---

## 11. Environment Variables (additions)

```bash
# Required for screenshot capture
INVESTING_COM_EMAIL=your@email.com
INVESTING_COM_PASSWORD=yourpassword

# Optional tuning
INVESTING_COM_CHART_INTERVAL=1D    # Chart timeframe: 1D, 1W, 1M
ANALYSIS_MIN_RR_RATIO=3.0          # Minimum risk/reward to qualify
ANALYSIS_TOP_N=5                   # Number of top opportunities to show
```

---

## 12. Testing Strategy

### Unit tests (`backend/tests/analysis/`)

| File | What it tests |
|---|---|
| `test_data_agent.py` | MACD/RSI/pivot calculations with mocked yfinance responses |
| `test_scoring_agent.py` | R/R filter (3.0 threshold), score formula, ranking order, 0-asset edge case |
| `test_vision_agent.py` | Structured output parsing, fallback when screenshot is None, malformed LLM response handling |
| `test_orchestrator.py` | Per-asset error isolation (one failure doesn't abort run), correct stage sequencing |

**ScreenshotAgent** is tested with a Playwright mock — no live connection to investing.com in CI.

### E2E tests (`test/`)

Run with `LLM_MOCK=true` + deterministic mock screenshot (1×1 PNG):

- Opportunities panel renders on load with cached data
- "Analizar" button triggers run, table populates with 5 rows
- Click row → main chart changes to that ticker + chat shows argument
- Add ticker → appears in next analysis run
- Error state: mock auth failure → inline error message shown

---

## 13. Additions to PLAN.md

The following sections of PLAN.md require amendments when this feature is implemented:

| Section | Addition |
|---|---|
| §2 User Experience | Opportunities panel description, click-to-chat interaction |
| §5 Environment Variables | `INVESTING_COM_*` and `ANALYSIS_*` vars |
| §7 Database | `analysis_results` and `analysis_tickers` tables |
| §8 API Endpoints | Analysis endpoint group |
| §10 Frontend Design | OpportunitiesPanel component group |
| §11 Docker | `playwright install chromium --with-deps` in Stage 2 |
| §12 Testing | Analysis unit tests and E2E scenarios |

---

## 14. Open Questions (resolved)

| Question | Decision |
|---|---|
| Data source for indicators | Hybrid: yfinance (numeric) + investing.com (visual) |
| Screenshot source | investing.com via Playwright with user credentials |
| Analysis trigger | On-demand + SQLite cache + manual refresh |
| UI placement | Dedicated panel below main chart, coexists with it |
| S/R detection | Numerical pivot points + LLM visual validation |
| Agent architecture | 4-stage pipeline: parallel data → sequential screenshots → parallel vision → scoring |
| Minimum R/R ratio | 3.0 (configurable via env var) |
| Default assets | Same 10 as watchlist seed |
| Top N shown | 5 (configurable via env var) |
