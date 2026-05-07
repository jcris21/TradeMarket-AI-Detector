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
│  Stage 2 — synchronous disk load (pre-captured PNGs)      │
│  └── Load finally/screenshots/{TICKER}.png → dict        │
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
├── vision_agent.py     # LiteLLM vision call → structured AssetAnalysis output
├── scoring_agent.py    # Filter R/R ≥ 3.0, score formula, rank Top 5
└── orchestrator.py     # Coordinates 4 stages, per-asset error isolation
```

> **MVP note:** `screenshot_agent.py` was removed. Stage 2 loads pre-captured PNGs from `finally/screenshots/{TICKER}.png`. Place screenshots there before running analysis.

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

## 5. Pre-captured Screenshots (MVP)

**Approach:** Screenshots are loaded from disk instead of captured at runtime via Playwright.

**Location:** `finally/screenshots/{TICKER}.png` (e.g., `AAPL.png`, `MSFT.png`)

**Flow in orchestrator (Stage 2):**
```python
screenshots_dir = Path(__file__).parents[3] / "screenshots"
screenshots = {
    ticker: (screenshots_dir / f"{ticker}.png").read_bytes()
    if (screenshots_dir / f"{ticker}.png").exists() else None
    for ticker in tickers
}
```

**Error handling:**
- Missing PNG for a ticker → `None` passed to VisionAgent; it proceeds with numeric data only and sets `support_validated = False`
- No Playwright dependency, no credentials required, no network calls in Stage 2

> **Future:** If live screenshot capture is re-enabled, restore `screenshot_agent.py` with Playwright + camoufox and update Stage 2 in `orchestrator.py` accordingly. The `INVESTING_COM_EMAIL` / `INVESTING_COM_PASSWORD` env vars and the Dockerfile `playwright install` step would also need to be re-added.

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

### 7.1 Cálculo del R/R Ratio

El ratio riesgo/beneficio se calcula a partir de tres precios definidos en el momento del análisis:

```
R/R = (target_price - entry_price) / (entry_price - stop_loss)
```

| Variable | Fuente | Descripción |
|---|---|---|
| `entry_price` | `TechnicalIndicators.current_price` | Precio de mercado en el momento del análisis |
| `target_price` | Resistencia R1 validada por VisionAgent | Primer nivel de resistencia de los últimos 20 períodos, confirmado visualmente en el gráfico |
| `stop_loss` | Soporte S1 validado por VisionAgent | Primer nivel de soporte de los últimos 20 períodos, confirmado visualmente en el gráfico |

**Ejemplo con GOOGL del seed:**
```
entry  = $178.50
target = $208.54  →  recorrido alcista = $30.04
stop   = $172.20  →  riesgo asumido   =  $6.30

R/R = 30.04 / 6.30 = 4.77 ≈ 4.8
```

El VisionAgent es responsable de validar que los niveles S1/R1 calculados numéricamente por el DataAgent sean visibles y respetados en el gráfico — si no lo son, `support_validated = False` y el asset recibe una penalización en el filtro de calificación.

---

### 7.2 Por qué el umbral mínimo es 3:1 y el cap de normalización es 6:1

Estos dos números tienen **roles distintos** en el pipeline:

#### Umbral mínimo: `ANALYSIS_MIN_RR_RATIO = 3.0` (variable de entorno)

Es la **puerta de entrada** — cualquier asset con R/R < 3.0 queda descalificado y no recibe rank, independientemente de su confianza o confluencia de indicadores.

**Justificación del 3:1 como apetito de riesgo aceptable:**
- En trading técnico, un mínimo de 2:1 es el estándar básico para que la estrategia sea matemáticamente viable con una tasa de acierto del 50 %. A 3:1 se puede ser rentable con solo el 40 % de operaciones ganadoras.
- El 3:1 como piso refleja el apetito de riesgo configurado: *"Solo me interesan oportunidades donde el beneficio potencial triplica el riesgo asumido."*
- Es configurable via `ANALYSIS_MIN_RR_RATIO` para que el usuario pueda subir (más selectivo) o bajar (más permisivo) según su perfil.

#### Cap de normalización: `6:1`

Es el **techo de excelencia** para el componente de scoring — marca el punto a partir del cual un R/R mayor no añade puntuación extra.

**Justificación del 6:1 como cap:**
- Un R/R de 6:1 implica que el target está muy lejos del entry, lo que en la práctica suele señalar que el target está en una resistencia estructural más débil o que el setup tiene baja probabilidad de completarse.
- Penalizar implícitamente los R/R excesivos evita que un asset con R/R=10:1 (poco realista) desplace a uno con R/R=4:1 + alta confianza + 3/3 indicadores.
- El rango útil de R/R en análisis técnico de corto/medio plazo es tipicamente 3:1–6:1. Por encima, el recorrido esperado raramente se materializa en el horizonte temporal analizado.

#### La interacción entre ambos números

```
R/R < 3.0        → DESCALIFICADO (no aparece en el Top 5)
3.0 ≤ R/R < 6.0  → Score crece linealmente: 3.0→17.5 pts, 4.5→26.25 pts, 6.0→35 pts
R/R ≥ 6.0        → Score fijo en 35 pts (techo, sin beneficio extra)
```

Esto produce un sistema de dos niveles: el 3:1 **filtra** (gate), y el 6:1 **normaliza** (scale). Un asset pasa el filtro con el mínimo aceptable y compite en score contra otros que superan ese mínimo — el score decide el ranking dentro de los calificados.

---

### 7.3 Por qué un score compuesto en vez de ordenar solo por R/R

Ordenar únicamente por R/R produciría rankings incorrectos. Estos tres casos ilustran el problema:

| Asset | R/R | Confianza | Indicadores | Score compuesto | Rank por R/R solo |
|---|---|---|---|---|---|
| A | 5.5:1 | 0.45 | 1/3 (solo MACD) | 52.8 | 1 ❌ |
| B | 4.0:1 | 0.90 | 3/3 | 89.3 | 3 |
| C | 3.2:1 | 0.82 | 2/3 | 71.4 | 4 |

**Asset A** tiene el R/R más alto, pero baja confianza (el VisionAgent no ve el patrón claramente) y solo un indicador alineado. Ordenar por R/R lo pondría primero — un falso positivo con alto riesgo de fallo.

**Asset B** tiene una confianza muy alta y 3/3 indicadores confluentes — el setup es sólido. El score compuesto lo prioriza correctamente.

**Los tres componentes del score capturan dimensiones independientes:**

| Componente | Peso | Qué mide | Por qué no es sustituible por R/R |
|---|---|---|---|
| `confidence × 40` | 40 % | Calidad del patrón visual (LLM vision) — claridad del setup, respeto de S/R en el gráfico | R/R no dice si el patrón es limpio o ruidoso |
| `rr_normalized × 35` | 35 % | Potencial matemático de la operación | Único componente relacionado con R/R, pero limitado al 35 % del score total |
| `confluence × 25` | 25 % | Convergencia de señales independientes (MACD + RSI + Volumen) | R/R no captura si varios indicadores confirman o contradicen el movimiento |

**Regla práctica:** El R/R define si una oportunidad *es aceptable*. El score compuesto define *cuál oportunidad aceptable es mejor*.

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
# Optional tuning
ANALYSIS_MIN_RR_RATIO=3.0          # Minimum risk/reward to qualify
ANALYSIS_TOP_N=5                   # Number of top opportunities to show
```

> **Removed:** `INVESTING_COM_EMAIL`, `INVESTING_COM_PASSWORD`, and `INVESTING_COM_CHART_INTERVAL` are no longer required — screenshots are pre-loaded from disk for the MVP.

---

## 12. Testing Strategy

### Unit tests (`backend/tests/analysis/`)

| File | What it tests |
|---|---|
| `test_data_agent.py` | MACD/RSI/pivot calculations with mocked yfinance responses |
| `test_scoring_agent.py` | R/R filter (3.0 threshold), score formula, ranking order, 0-asset edge case |
| `test_vision_agent.py` | Structured output parsing, fallback when screenshot is None, malformed LLM response handling |
| `test_orchestrator.py` | Per-asset error isolation (one failure doesn't abort run), correct stage sequencing, missing PNG handled as None |

**Stage 2** requires no mocking — it reads PNGs from `finally/screenshots/`. Tests can place fixture PNGs there or rely on the `None` fallback path.

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
| §11 Docker | No Playwright dependency needed for MVP (screenshots pre-loaded from disk) |
| §12 Testing | Analysis unit tests and E2E scenarios |

---

## 15. Orchestration Framework Decision

### Two independent orchestration layers

This feature uses two distinct orchestration mechanisms. Neither layer depends on an external framework (LangChain, AutoGen, CrewAI, LangGraph, Celery, Ray).

---

### Layer 1 — Implementation agents (Claude Code Agent Teams)

The 5 specialist agents that **build** this feature are native Claude Code agents:

| Agent file | Tasks | Responsibility |
|---|---|---|
| `infra-engineer.md` | 1, 16, 17 | pyproject.toml deps, Dockerfile, .env.example |
| `db-engineer.md` | 2–3 | `analysis_results` / `analysis_tickers` schema + repository |
| `analysis-engineer.md` | 4–9 | models, DataAgent, ScreenshotAgent, VisionAgent, ScoringAgent, Orchestrator |
| `api-engineer.md` | 10 | FastAPI router + `main.py` registration |
| `frontend-engineer.md` | 11–15 | TypeScript types, API client, hook, OpportunitiesPanel, E2E test |

**Activation mechanism:**
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` (set in `finally/.claude/settings.json`)
- `teammateMode: "in-process"` — agents run in the same Claude Code process
- No external process, no network call, no serialization overhead
- Agents are invoked by Claude Code based on task context and agent `description` frontmatter

**Why no external orchestration framework here:** These agents execute once per feature and share the same file system. Claude Code's built-in agent team dispatch is sufficient; adding a framework would introduce setup cost with zero benefit for a one-shot implementation workflow.

---

### Layer 2 — Analysis pipeline (Python asyncio)

The runtime orchestration of the 4-stage analysis pipeline is pure Python:

```python
# Stage 1: parallel data fetch — no I/O blocking between tickers
indicators: list[TechnicalIndicators] = await asyncio.gather(
    *[fetch_data(ticker) for ticker in tickers],
    return_exceptions=True,  # per-asset error isolation
)

# Stage 2: load pre-captured PNGs from finally/screenshots/{TICKER}.png
screenshots: dict[str, bytes | None] = load_screenshots(tickers)

# Stage 3: parallel LLM vision calls — each call is independent
analyses: list[AssetAnalysis] = await asyncio.gather(
    *[analyze_asset(ind, screenshots.get(ind.ticker)) for ind in indicators],
    return_exceptions=True,
)

# Stage 4: single synchronous pass — CPU-only, no I/O
results: AnalysisResult = score_and_rank(analyses)
```

**Sync-in-async bridge:**
- `yfinance.download()` is synchronous → wrapped with `asyncio.to_thread()`
- `litellm.completion()` is synchronous → wrapped with `asyncio.to_thread()`
- No blocking of the FastAPI event loop

**Why not LangGraph / Celery / Ray:**
La orquestación del análisis de activos es Python puro con asyncio:


# Stage 1: paralelo
indicators = await asyncio.gather(*[fetch_data(t) for t in tickers])

# Stage 2: secuencial (un solo browser)
screenshots = await capture_charts(tickers)

# Stage 3: paralelo
analyses = await asyncio.gather(*[analyze_asset(t) for t in tickers])

# Stage 4: secuencial
results = score_and_rank(analyses)
asyncio.gather() → paralelismo
asyncio.to_thread() → wrappea llamadas síncronas (yfinance, litellm)
Sin LangGraph, sin Celery, sin ray — todo en memoria dentro del proceso FastAPI

¿Por qué no un framework de orquestación? Para ~10 activos, asyncio es suficiente, más simple, sin dependencias extra, y evita overhead de serialización. Un framework como LangGraph agregaría valor si los agentes necesitaran estado persistente entre pasos o reintentos complejos.

| Option | Why rejected |
|---|---|
| LangGraph | Adds state graph overhead; our 4-stage sequence is linear and doesn't need conditional branching or checkpointing |
| Celery | Requires a broker (Redis/RabbitMQ); overkill for 10 assets, ~40s total runtime within a single HTTP request |
| Ray | Distributed compute for a workload that fits in a single process; dependency weight (~500MB) not justified |
| asyncio (chosen) | Zero extra dependencies, integrates natively with FastAPI, sufficient for N≤20 tickers |

**Scaling threshold:** If the ticker list grows beyond ~50 assets or analysis needs to run on a schedule (not on-demand), introduce a task queue (Celery + Redis) and promote ScoringAgent to a separate worker. For the current scope (10 default + user additions), asyncio is the correct choice.

---

## 14. Open Questions (resolved)

| Question | Decision |
|---|---|
| Data source for indicators | Hybrid: yfinance (numeric) + investing.com (visual) |
| Screenshot source | Pre-captured PNGs in `finally/screenshots/` (MVP); Playwright path removed |
| Analysis trigger | On-demand + SQLite cache + manual refresh |
| UI placement | Dedicated panel below main chart, coexists with it |
| S/R detection | Numerical pivot points + LLM visual validation |
| Agent architecture | 4-stage pipeline: parallel data → sequential screenshots → parallel vision → scoring |
| Minimum R/R ratio | 3.0 (configurable via env var) |
| Default assets | Same 10 as watchlist seed |
| Top N shown | 5 (configurable via env var) |
