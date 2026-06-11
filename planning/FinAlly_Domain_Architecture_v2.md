# Domain Architecture — FinAlly MVP
**Skill**: L4-B Domain Architecture Diagrams  
**Scope**: STORY-001 → STORY-007 integradas en el sistema existente  
**Framework**: DDD (Evans) + DDIA (Kleppmann) + Evaluación Sistémica  
**Date**: 2026-05-23

---

## 1. Existing Domain Inventory

Baseline antes de cualquier story. Todo lo nuevo es **aditivo** sobre esta tabla.

| Name | DDD Type | Python Type | File | Key Fields |
|------|----------|-------------|------|------------|
| `TechnicalIndicators` | Value Object | `frozen dataclass` | `data_agent.py` | ticker, macd_signal, rsi, volume_ratio, support_1/2, resistance_1/2 |
| `AssetAnalysis` | Entity | `Pydantic BaseModel` | `models.py` | ticker, signal, confidence, entry/target/stop, rr, support_validated, score, rank |
| `AnalysisResult` | Aggregate Root | `Pydantic BaseModel` | `models.py` | run_id, analyzed_at, assets[], top_5[], errors[], duration_seconds |
| `PriceUpdate` | Value Object | `frozen dataclass (slots)` | `market/models.py` | ticker, price, previous_price, timestamp, change, direction |
| `PriceCache` | Domain Service | `class` | `market/cache.py` | _prices, _version, _lock |

| Agent | File | Stage | Input → Output | Status |
|-------|------|-------|----------------|--------|
| `OrchestratorAgent` | `orchestrator.py` | Root | `[tickers]` → `AnalysisResult` | ✅ spec completo |
| `DataAgent` | `data_agent.py` | Stage 1 ‖ | `ticker` → `TechnicalIndicators` | ✅ spec completo |
| `ScreenshotAgent` | `screenshot_agent.py` | Stage 2 → | `[tickers]` → `dict[str, bytes]` | ✅ spec completo |
| `VisionAgent` | `vision_agent.py` | Stage 3 ‖ | `ticker + indicators + bytes` → `AssetAnalysis` | ✅ spec completo |
| `ScoringAgent` | `scoring_agent.py` | Stage 4 | `[AssetAnalysis]` → `[ranked]` | 🔄 Enhancement v3 en progreso |

---

## 2. Class Diagram

`AnalysisResult` es el aggregate root (DDD): agrupa `AssetAnalysis` y garantiza la consistencia de un run completo. Las stories STORY-001 a STORY-007 son puramente aditivas — 7 campos opcionales nuevos en `AssetAnalysis` (write path, pre-computados por `ScoringAgent`), 4 campos en `TechnicalIndicators` (value object inmutable extendido en DataAgent), y 9 columnas NULL-safe en `analysis_results` (una sola migración). `SignalOutcome` es un nuevo value object que se escribe exactamente una vez por `OutcomeDetector` (DDIA: idempotency). `PerformanceSummary` es un read model derivado puro — compuesto mediante SQL `GROUP BY` en cada request, nunca persistido (DDIA: read path separada del write path).

```mermaid
classDiagram
  direction TB

  class TechnicalIndicators {
    dataclass frozen
    +str ticker
    +float current_price
    +str macd_signal
    +float rsi
    +float volume_ratio
    +float support_1
    +float resistance_1
    +float atr_14
    +float atr_14_pct
    +float sma_20
    +float sma_50
  }

  class AssetAnalysis {
    BaseModel Entity
    +str ticker
    +Literal signal
    +float confidence
    +float entry_price
    +float target_price
    +float stop_loss
    +float risk_reward_ratio
    +bool support_validated
    +Optional score
    +Optional rank
    +bool stop_viable
    +float expected_gain_per10
    +float expected_loss_per10
    +float expected_value_per10
    +float score_delta
    +int trend_score
  }

  class AnalysisResult {
    BaseModel AggregateRoot
    +str run_id
    +datetime analyzed_at
    +list assets
    +list top_5
    +list errors
    +float duration_seconds
  }

  class SignalOutcome {
    dataclass NEW STORY-003
    +str outcome
    +float actual_gain_pct
    +float actual_loss_pct
    +int hold_days
    +str support_break_level
  }

  class PerformanceSummary {
    BaseModel ReadModel NEW
    +int total_signals
    +int hits
    +float hit_ratio
    +float profit_factor
    +float realized_rr
    +int phase
    +bool metrics_unlocked
  }

  class analysis_results {
    SQLite Table Repository
    +TEXT id PK
    +TEXT run_id
    +TEXT ticker
    +REAL score
    +TEXT analyzed_at
    +REAL expected_gain_per10
    +REAL expected_loss_per10
    +REAL expected_value_per10
    +REAL score_delta
    +TEXT outcome
    +REAL actual_gain_pct
    +REAL actual_loss_pct
    +INTEGER hold_days
    +TEXT support_break_level
  }

  AnalysisResult "1" *-- "0..*" AssetAnalysis : contains
  AssetAnalysis "1" --> "1" TechnicalIndicators : derived from
  AssetAnalysis "1" --> "0..1" SignalOutcome : resolved by
  analysis_results ..> AssetAnalysis : persists
  analysis_results ..> SignalOutcome : persists outcome
  PerformanceSummary ..> analysis_results : aggregates via SQL GROUP BY
```

---

## 3. Architecture Diagram

El sistema vive en un único contenedor Docker — restricción hard del repo (DDIA: single-node architecture con SQLite como store único). Las stories no rompen este boundary: cero nuevos servicios, cero nuevos puertos. El `OrchestratorAgent` es el application service (DDD) que coordina los agentes de dominio; FastAPI es la interfaz de entrada sin lógica de negocio. Los dos componentes nuevos se insertan sin fricción: `OutcomeDetector` es un background job nocturno que escribe en `analysis_results`, y `GET /api/analysis/performance` es lectura pura. El nodo `GuardrailValidator` (TECH-005) representa el boundary explícito entre decisión agéntica (VisionAgent) y reglas duras de negocio (RR ≥ 3.0, ATR floor, stop < entry).

```mermaid
flowchart TD
  subgraph DOCKER["Docker Container — port 8000"]
    subgraph FE["Frontend Layer — Next.js static export"]
      UI["Dashboard UI\nBet-Size · Freshness · Score Delta\nPerf Panel · Phase Gate  NEW"]
    end

    subgraph BE["Backend Layer — FastAPI"]
      A1["analysis/ routes\nGET /latest · POST /run\nGET /performance  NEW"]
      A2["portfolio/ routes\nGET · POST /trade"]
      A3["market/ routes\nGET /stream/prices SSE"]
      A4["chat/ routes\nPOST /chat"]
    end

    subgraph AGENTS["Agent Layer — analysis/"]
      ORCH["OrchestratorAgent\nEXISTING"]
      DA["DataAgent\n+ atr_14 · sma_20 · sma_50  EXTENDED"]
      SA["ScreenshotAgent\nEXISTING"]
      VA["VisionAgent\nEXISTING  timeout=15s TECH-002"]
      GV["GuardrailValidator\nstop lt entry · RR ge 3.0  NEW TECH-005"]
      SC["ScoringAgent\nv3 formula + Bet-Size  EXTENDED"]
      OD["OutcomeDetector\nyfinance walk-forward  NEW nightly"]
    end

    subgraph MKT["Market Layer — market/"]
      SIM["SimulatorDataSource or MassiveDataSource"]
      PC["PriceCache  thread-safe"]
      SIM --> PC
    end

    subgraph DB["Data Layer — SQLite finally.db"]
      AR[("analysis_results\n+ 9 new columns")]
      TR[("trades")]
      POS[("positions")]
      CM[("chat_messages")]
    end
  end

  subgraph EXT["External Services"]
    YF["yfinance API"]
    INV["investing.com  Playwright"]
    LLM["OpenRouter Cerebras"]
  end

  UI -->|"REST /api/*"| A1 & A2
  UI -->|"SSE EventSource"| A3
  ORCH --> DA & SA
  DA & SA --> VA
  VA --> GV --> SC
  SC --> AR
  OD --> AR
  PC --> A3
  DA -->|"yfinance"| YF
  SA -->|"Playwright"| INV
  VA & A4 -->|"LiteLLM"| LLM
  OD -->|"yfinance walk-forward"| YF
```

---

## 4. Orchestration Diagram

La pipeline de 4 stages es el **write path** (DDIA): transforma datos externos en `AssetAnalysis` persistidos en `analysis_results`, costosa en tiempo (~45s batch), ejecutada una vez por run. Los dashboards son el **read path**: lecturas pre-computadas sub-200ms. Las stories solo tocan Stage 4 (ScoringAgent extendido) y el nightly batch (OutcomeDetector nuevo) — no modifican la topología ni agregan latencia al critical path del trader. Los nodos de TECH-001 a TECH-004 son visibles como anotaciones en el diagrama porque son precondiciones de corrección, no opcionales.

```mermaid
flowchart TD
  CRON(["Pre-market cron\nor POST /api/analysis/run"])
  ORCH["OrchestratorAgent\norchestrator.py\nEXISTING · NO CHANGE"]

  subgraph S1["Stage 1 — asyncio.gather parallel"]
    DA["DataAgent x N\nyfinance + pandas-ta\nTechnicalIndicators\n+ atr_14 · sma_20 · sma_50  EXTENDED"]
  end

  subgraph S2["Stage 2 — Serial 1 browser session"]
    SA["ScreenshotAgent\nPlaywright\nEXISTING · NO CHANGE"]
  end

  subgraph S3["Stage 3 — asyncio.gather parallel"]
    VA["VisionAgent x N\nLiteLLM Cerebras\nAssetAnalysis + stop_viable  EXTENDED\ntimeout=15s · fallback=AVOID  TECH-002"]
  end

  subgraph S4["Stage 4 — Aggregation"]
    GV["GuardrailValidator\nvalida stop · target · RR\nantes de scoring  TECH-005  NEW"]
    SC["ScoringAgent\nv3 formula + Bet-Size fields\nscore_delta batch SQL  TECH-003  EXTENDED"]
    WR["Unit of Work write\nINSERT analysis_results\n9 new columns  TECH-001  NEW"]
  end

  subgraph NIGHTLY["Nightly Batch — STORY-003  NEW"]
    OD["OutcomeDetector\nyfinance walk-forward\nper active trade"]
    OC{{"high_j >= target?\nlow_j <= stop?\n30d elapsed?"}}
    OW["UPDATE optimistic lock\nWHERE outcome IS NULL\nTECH-004"]
  end

  subgraph READS["Dashboard Reads — deterministic  NEW"]
    API1["GET /api/analysis/latest\n+ Bet-Size · freshness · delta\nSTORY-001 · STORY-002"]
    API2["GET /api/analysis/performance\nSQL GROUP BY outcome\nPerformanceSummary\nSTORY-004 · STORY-007"]
  end

  UI["Next.js Dashboard\nBet-Size · Freshness · Delta · Perf Panel  NEW"]

  CRON --> ORCH
  ORCH --> S1
  S1 -->|"TechnicalIndicators + ATR + SMA"| S2
  S2 -->|"dict ticker PNG bytes"| S3
  S3 -->|"AssetAnalysis list + stop_viable"| S4
  GV --> SC --> WR
  WR --> API1
  WR -.->|"analyzed_at stored"| NIGHTLY
  OD --> OC
  OC -->|"TARGET_HIT"| OW
  OC -->|"STOP_HIT"| OW
  OC -->|"EXPIRED"| OW
  OW --> API2
  API1 & API2 --> UI
```

---

## 5. Sequence Diagram

El único punto de sincronización bloqueante para el trader es `GET /api/analysis/latest` — pero los datos son pre-computados (DDIA: materialized view), por lo que el request es trivialmente rápido. El `POST /api/portfolio/trade` es el punto de irreversibilidad (DDIA: write que no puede deshacerse fácilmente) — flanqueado por blocking confirmation dialog. `OutcomeDetector` es completamente asíncrono respecto al trader. La secuencia expone el score_delta loop como cuello de botella (TECH-003) y el intent-abandoned como estado huérfano sin definir (finding #10).

```mermaid
sequenceDiagram
  actor Trader
  participant UI as Dashboard UI
  participant API as FastAPI /analysis
  participant SC as ScoringAgent
  participant DB as analysis_results
  participant OD as OutcomeDetector
  participant PerfAPI as FastAPI /analysis/performance

  Note over SC,DB: PRE-MARKET batch run ~45s

  activate SC
  SC->>SC: Stages 1-3 pipeline
  SC->>SC: compute atr_14 · Bet-Size · score_delta batch SQL
  Note right of SC: STORY-001 · STORY-005 · STORY-006
  SC->>SC: GuardrailValidator validate stop·target·RR
  Note right of SC: TECH-005 antes del write
  SC->>DB: Unit of Work INSERT 9 new cols
  Note right of SC: TECH-001 try/except sqlite3.Error
  deactivate SC

  Note over Trader,UI: TRADER SESSION

  Trader->>UI: opens dashboard
  UI->>API: GET /api/analysis/latest
  activate API
  API->>DB: SELECT * ORDER BY score DESC
  DB-->>API: rows with expected_gain_per10 · score_delta · analyzed_at
  API->>API: freshness_status = f(NOW - analyzed_at)
  Note right of API: STORY-002 derived at read time zero storage
  API-->>UI: signals + Bet-Size + freshness + delta
  deactivate API
  UI->>Trader: renders signal list with Bet-Size Cards

  Note over Trader,UI: HITL Step 8 — Human Only

  Trader->>UI: clicks Enter Trade on AAPL
  UI->>Trader: blocking dialog entry · stop · target · ATR ok · R/R
  Note right of Trader: HUMAN ONLY no automation L3-A classification

  alt Trader confirms
    Trader->>UI: confirms entry
    UI->>API: POST /api/portfolio/trade
    activate API
    API->>DB: INSERT INTO trades
    API-->>UI: trade confirmed
    deactivate API
  else Trader abandons
    Note right of UI: no write — intent abandoned finding 10
  end

  Note over OD,DB: NIGHTLY BATCH STORY-003

  activate OD
  OD->>DB: SELECT WHERE outcome IS NULL
  loop per active trade max 30 days
    OD->>OD: yfinance walk-forward
    OD->>DB: UPDATE outcome WHERE outcome IS NULL
    Note right of OD: TECH-004 optimistic lock rowcount check
  end
  deactivate OD

  Note over Trader,PerfAPI: PERFORMANCE REVIEW

  Trader->>UI: opens performance panel
  UI->>PerfAPI: GET /api/analysis/performance
  activate PerfAPI
  PerfAPI->>DB: GROUP BY outcome WHERE outcome != EXPIRED
  DB-->>PerfAPI: aggregated HR · PF · realized_rr
  PerfAPI->>PerfAPI: phase gate count lt 30 suppress metrics
  Note right of PerfAPI: STORY-007
  PerfAPI-->>UI: PerformanceSummary
  deactivate PerfAPI
  UI->>Trader: rolling panel OR Phase-0 banner
```

---

## 6. Use Case Diagram

Las 7 nuevas capacidades del trader pertenecen todas al Analysis Bounded Context (DDD) — no cruzan ninguna frontera de contexto. Los casos de uso del nightly batch son domain services sin actor humano. `See stop-out diagnosis` tiene una pre-condition de dominio estricta: solo disponible cuando `outcome = STOP_HIT` ha sido escrito — la UI debe ocultarla hasta entonces. `Execute simulated trade` es el único caso existente que cruza al Portfolio Context, usando los campos `entry_price/stop_loss/target_price` ya presentes en `AssetAnalysis`.

```mermaid
flowchart LR
  TRADER(["Swing Trader"])
  BATCH(["Nightly Batch"])
  YF(["yfinance API"])

  subgraph SYSTEM["Sistema FinAlly"]
    direction TB

    subgraph EXISTING["Capacidades existentes"]
      UC1(["Run analysis on 30 tickers"])
      UC2(["Stream live prices SSE"])
      UC3(["Chat with AI assistant"])
      UC4(["Execute simulated trade"])
      UC5(["Manage watchlist"])
    end

    subgraph NEW_UC["Nuevas capacidades STORY-001 a 007"]
      UC6(["See expected gain per $10\nSTORY-001"])
      UC7(["Check signal freshness\nSTORY-002"])
      UC8(["See score building or fading\nSTORY-001"])
      UC9(["Verify ATR stop viability\nSTORY-005"])
      UC10(["View rolling HR PF R/R\nSTORY-004"])
      UC11(["Know system validation phase\nSTORY-007"])
      UC12(["See stop-out diagnosis\nSTORY-003\nrequires outcome=STOP_HIT"])
    end

    subgraph SYS_UC["Capacidades del sistema sin actor humano"]
      UC13(["Detect trade outcomes nightly\nSTORY-003"])
      UC14(["Pre-compute Bet-Size at signal write\nSTORY-001"])
    end
  end

  TRADER --> UC1 & UC2 & UC3 & UC4 & UC5
  TRADER --> UC6 & UC7 & UC8 & UC9 & UC10 & UC11 & UC12
  BATCH  --> UC13
  UC13   --> YF
  UC14   -.->|"include"| UC1
  UC6    -.->|"include"| UC14
  UC8    -.->|"include"| UC14
  UC10   -.->|"include"| UC13
  UC11   -.->|"include"| UC13
  UC12   -.->|"extend only if STOP_HIT"| UC13
```

---

## 7. Agent State Diagram

Una señal tiene dos ciclos de vida **ortogonales y simultáneos** (DDD: múltiples facetas del mismo agregado). Freshness se deriva de `analyzed_at` en tiempo de lectura — DDIA: derived data, cero escrituras adicionales. Outcome se escribe exactamente una vez por `OutcomeDetector` — DDIA: idempotent write con guard `WHERE outcome IS NULL`. El estado `Excluded` es terminal e irreversible por diseño (regla CLT de Kaabar). El estado `Orphaned` (nuevo, TECH-006 finding #12) cubre el caso de edge donde el OutcomeDetector falla persistentemente.

```mermaid
stateDiagram-v2
  direction LR

  [*] --> Generated : ScoringAgent INSERT analyzed_at=NOW()

  state "Freshness lifecycle derived at read time STORY-002" as FG {
    Generated --> Fresh   : age lt 2h
    Fresh     --> Active  : 2h elapsed
    Active    --> Aged    : age gt 6h same day
    Aged      --> Expired : next trading day
  }

  note right of Fresh
    Badge verde score opaco
    Bet-Size Card visible
    EV @ 35% assumed
  end note

  note right of Expired
    Removida de lista activa
    Retenida en archivo
    NO cuenta en HR/PF
  end note

  state "Outcome lifecycle written by OutcomeDetector STORY-003" as OG {
    Generated --> Pending    : trader confirma entrada
    Pending   --> TargetHit  : high_j >= target_price
    Pending   --> StopHit    : low_j <= stop_loss
    Pending   --> TimedOut   : 30 trading days sin resolución
    Pending   --> Orphaned   : 35 dias OutcomeDetector falla
  }

  TargetHit --> Resolved : outcome=TARGET_HIT actual_gain_pct hold_days
  StopHit   --> Resolved : outcome=STOP_HIT actual_loss_pct support_break_level
  TimedOut  --> Excluded : outcome=EXPIRED excluido de HR/PF
  Orphaned  --> [*]      : visible en UI diagnóstico revisar manualmente

  Resolved  --> [*] : contado en HR PF R/R
  Excluded  --> [*] : no contado en ninguna métrica

  note right of StopHit
    Detecta qué nivel rompió:
    S1 SMA20 BB_lower
    writes support_break_level
  end note

  note right of Resolved
    PerformanceSummary recalcula
    EV badge transiciona a HR real
    en señal número 30
  end note
```

---

## 8. Bounded Context Map

Todas las stories (STORY-001 a STORY-007) son internas al **Analysis Context** — no cruzan fronteras. La única frontera cruzada por las stories es el pre-fill de `entry_price/stop_loss/target_price` desde Analysis al Portfolio Context en Step 9. El Chat Context requiere dos **Anti-Corruption Layers** (DDD): una para traducir `AssetAnalysis` al vocabulario natural del LLM, y otra para traducir `positions` del Portfolio Context.

```mermaid
flowchart TB

  subgraph MARKET["Market Context  market/"]
    direction TB
    MC_SIM["SimulatorDataSource or MassiveDataSource"]
    MC_PC["PriceCache\nfuente de verdad precios en vivo"]
    MC_SSE["SSE Stream GET /api/stream/prices"]
    MC_SIM -->|"write tick 500ms"| MC_PC
    MC_PC  -->|"version-gated push"| MC_SSE
  end

  subgraph ANALYSIS["Analysis Context  analysis/  TODAS LAS STORIES AQUI"]
    direction TB
    AC_DA["DataAgent\n+ atr_14 sma_20  EXTENDED"]
    AC_VA["VisionAgent\n+ stop_viable  EXTENDED"]
    AC_GV["GuardrailValidator  NEW TECH-005"]
    AC_SC["ScoringAgent\n+ Bet-Size fields  EXTENDED"]
    AC_AR[("analysis_results\nfuente de verdad señales\n+ 9 new columns")]
    AC_OD["OutcomeDetector  NEW"]
    AC_PP["PerformanceSummary\nread model derivado"]
    AC_DA --> AC_VA --> AC_GV --> AC_SC --> AC_AR
    AC_AR --> AC_OD --> AC_AR
    AC_AR --> AC_PP
  end

  subgraph PORTFOLIO["Portfolio Context  portfolio/"]
    direction TB
    PF_TR[("trades\nfuente de verdad ejecuciones")]
    PF_POS[("positions\nholdings agregados")]
    PF_TR --> PF_POS
  end

  subgraph CHAT["Chat Context  chat/"]
    direction TB
    CH_ACL1["ACL AssetAnalysis to LLM vocab"]
    CH_LLM["Copilot Handler\nLiteLLM Cerebras  NEW"]
    CH_ACL2["ACL positions to trading context"]
    CH_MSG[("chat_messages")]
    CH_ACL1 & CH_ACL2 --> CH_LLM --> CH_MSG
  end

  MARKET   -->|"PriceCache.get_price() sync read"| ANALYSIS
  MARKET   -->|"precio para P&L"| PORTFOLIO
  ANALYSIS -->|"entry stop target pre-fill orden\nread no write coupling"| PORTFOLIO
  ANALYSIS -->|"AssetAnalysis fields\nrequiere ACL"| CHAT
  PORTFOLIO -->|"positions cash\nrequiere ACL"| CHAT
```

---

## 9. Systemic Impact Summary

### Write Path Changes

| Story | Escribe | Tabla | Consumidor | Riesgo |
|-------|---------|-------|-----------|--------|
| STORY-001 | `expected_gain_per10`, `score_delta` | `analysis_results` | Dashboard API, EV badge | LOW — NULL-safe, aditivo |
| STORY-003 | `outcome`, `actual_gain_pct`, `hold_days`, `support_break_level` | `analysis_results` | PerformanceSummary, Diagnosis card | MED — debe ser idempotente |
| STORY-005 | `atr_14`, `stop_viable` | `TechnicalIndicators` (in-memory) | ScoringAgent | LOW — sin persistencia |
| STORY-006 | `sma_20`, `sma_50` | `TechnicalIndicators` (in-memory) | ScoringAgent | LOW — sin persistencia |

### Schema Migration (una sola transacción)

```sql
BEGIN TRANSACTION;
ALTER TABLE analysis_results ADD COLUMN expected_gain_per10  REAL;
ALTER TABLE analysis_results ADD COLUMN expected_loss_per10  REAL;
ALTER TABLE analysis_results ADD COLUMN expected_value_per10 REAL;
ALTER TABLE analysis_results ADD COLUMN score_delta          REAL;
ALTER TABLE analysis_results ADD COLUMN outcome              TEXT;
ALTER TABLE analysis_results ADD COLUMN actual_gain_pct      REAL;
ALTER TABLE analysis_results ADD COLUMN actual_loss_pct      REAL;
ALTER TABLE analysis_results ADD COLUMN hold_days            INTEGER;
ALTER TABLE analysis_results ADD COLUMN support_break_level  TEXT;
CREATE INDEX idx_outcome ON analysis_results(outcome);
COMMIT;
```

### What Could Break

| Escenario | Probabilidad | Mitigación |
|-----------|-------------|------------|
| `score_delta` NULL en primer run por ticker | CERTEZA | `COALESCE(score_delta, 0.0)`, UI muestra Stable |
| OutcomeDetector duplica outcome | ALTA si reinicia | `UPDATE WHERE outcome IS NULL` — TECH-004 |
| EV badge no transiciona en señal #30 | MEDIA off-by-one | Test boundary 29 assumed 30 actual |
| `actual_gain_pct` NULL si yfinance retorna NaN | MEDIA | Validar NOT NULL antes de write en OD |
| Migration falla mid-deploy | BAJA | Envolver en transacción test en dev DB primero |

---

## 10. Critical System Evaluation

### Evaluación: Architecture Diagram

**System Type**: Hybrid — Core determinista (85%) + capa agéntica (VisionAgent, Copilot)  
**DDD/DDIA Lens**: DDIA single-node architecture · DDD bounded contexts · Agentic reliability patterns

| # | Dimensión | Hallazgo | Severidad |
|---|-----------|---------|----------|
| 1 | Acoplamiento Determinista | `ScoringAgent` escribe a DB dentro del pipeline — fallo de DB en Stage 4 aborta el run aunque Stages 1-3 completaron. | 🟠 Alta |
| 2 | Cuello de botella Determinista | `analysis_results` es el único punto de escritura. Con múltiples runs simultáneos, SQLite write lock es el cuello de botella sistémico. | 🟡 Media |
| 3 | Guardrails agénticos | No hay boundary arquitectónico explícito entre decisión agéntica (VisionAgent) y reglas duras de negocio. Un LLM puede generar `stop_loss > entry_price`. | 🟠 Alta |
| 4 | Observabilidad | No hay componente de telemetría visible. Sin logging por stage, un run lento no puede diagnosticarse. | 🟠 Alta |

**Design Patterns**:
- Finding 1 → **Unit of Work**: envolver INSERT en `try/except sqlite3.Error`, asset fallido va a `errors[]`, run continúa.
- Finding 3 → **Explicit Guardrail Layer**: nodo `GuardrailValidator` entre VisionAgent y ScoringAgent que valida invariantes estructurales.
- Finding 4 → **Structured Logging**: componente `AnalysisTelemetry` que registra `duration_ms`, `error_count`, y `signals_generated` por stage y por run.

---

### Evaluación: Orchestration Diagram

**System Type**: Hybrid — Staged Fan-out determinista + VisionAgent agéntico  
**DDD/DDIA Lens**: DDIA write path optimization · Agentic reliability patterns

| # | Dimensión | Hallazgo | Severidad |
|---|-----------|---------|----------|
| 5 | Error Compounding Agéntico | 4 stages en secuencia × N tickers. Con 90% éxito/agente y 4 stages: tasa de éxito completo ≈ 65%. No visible en el diagrama. | 🔴 Crítico |
| 6 | Timeout Agéntico | Sin timeout explícito en VisionAgent. LLM lento congela el run completo. | 🔴 Crítico |
| 7 | Fallback Path Agéntico | Solo happy path visible. Sin ruta alternativa si ScreenshotAgent falla o VisionAgent retorna JSON inválido. | 🔴 Crítico |
| 8 | Race condition Determinista | `OutcomeDetector` sin optimistic lock — dos instancias simultáneas pueden escribir outcomes duplicados. | 🟠 Alta |

**Design Patterns**:
- Findings 5, 6, 7 → **Reliability Engineering**: timeout configurable vía env var + degraded fallback visible en el diagrama. Per-asset error isolation (ya soportado por `errors[]`) debe ser explícito en el diagrama.
- Finding 8 → **Optimistic Locking**: `UPDATE SET outcome=? WHERE id=? AND outcome IS NULL`. Si `rowcount == 0`, skip con INFO log.

---

### Evaluación: Sequence Diagram

**System Type**: Hybrid — flujo del trader determinista + copilot agéntico  
**DDD/DDIA Lens**: DDIA synchronous coordination · DDD aggregate invariants

| # | Dimensión | Hallazgo | Severidad |
|---|-----------|---------|----------|
| 9 | Cuello de botella Determinista | `score_delta` SQL lookup síncrono dentro del loop de Stage 4 — 30 queries secuenciales con 30 tickers. | 🟡 Media |
| 10 | Estado huérfano Determinista | Sin estado definido para "trader abre dashboard, pre-llena orden, cierra sin confirmar". El trade nunca se registra pero el usuario puede creer que sí entró. | 🟡 Media |
| 11 | Gap de notificación Agéntico | `OutcomeDetector` escribe outcomes de noche pero no hay push notification. El trader debe refrescar manualmente. | 🟡 Media |

**Design Patterns**:
- Finding 9 → **Batch SQL**: una sola query al inicio de Stage 4, resultado en dict Python, sin I/O dentro del loop.
- Finding 10 → Documentar en L3-D UX spec como edge case del Step 9 — "intent abandoned timeout".
- Finding 11 → Evaluar SSE outcome event cuando OutcomeDetector detecta TARGET_HIT o STOP_HIT.

---

### Evaluación: Agent State Diagram

**System Type**: Deterministic — transiciones gobernadas por reglas matemáticas exactas  
**DDD/DDIA Lens**: DDD aggregate invariants · DDIA idempotency

| # | Dimensión | Hallazgo | Severidad |
|---|-----------|---------|----------|
| 12 | Estado huérfano Determinista | `Pending` sin transición de recovery si `OutcomeDetector` falla persistentemente 35+ días. Trade queda en limbo sin diagnóstico. | 🟠 Alta |
| 13 | Idempotencia Determinista | `actual_gain_pct` puede escribirse como NULL si yfinance retorna NaN para una barra específica. | 🟡 Media |
| 14 | Coexistencia de estados Determinista | Señal `Expired` (freshness) con `outcome=Pending` (activo). La UI no debe filtrar outcomes por freshness en el historial de trades. | 🟡 Media |

**Design Patterns**:
- Finding 12 → Estado `Orphaned` como transición de recovery. Si OutcomeDetector no resuelve un trade después de 35 días, transicionar a Orphaned visible en UI con diagnóstico "revisar manualmente".
- Finding 13 → Validar `actual_gain_pct IS NOT NULL` antes del write. Si NaN, skip y retry en próximo run.
- Finding 14 → Filtro de freshness aplica solo a lista activa. Historial de outcomes muestra todas las señales con outcome independientemente de freshness.

---

## 11. Technical Tasks from Evaluation

### TECH-001: Unit of Work en Stage 4
**Source**: Finding #1 — Architecture Diagram · **Severidad**: 🟠 Alta · **System type**: Deterministic  
**Finding**: Fallo de DB en Stage 4 aborta run completo aunque Stages 1-3 completaron.  
**Riesgo**: Runs parcialmente exitosos no se persisten; trader no ve resultados en fallos transitorios.

```python
# scoring_agent.py
try:
    cursor.execute("INSERT INTO analysis_results ...", values)
    conn.commit()
except sqlite3.Error as e:
    logger.error("DB write failed for %s: %s", ticker, e)
    asset.rank = None
    errors.append({"ticker": ticker, "error": str(e)})
```

**Acceptance criteria**:
- [ ] Fallo de INSERT para un ticker → run continúa con los demás tickers
- [ ] Ticker fallido aparece en `AnalysisResult.errors[]`
- [ ] `test_scoring_agent.py` cubre `sqlite3.OperationalError` durante write
- [ ] `OrchestratorAgent` retorna resultados parciales con errors[]

**Effort**: Low 2-3h · **Sprint**: Slice 0 · **Blocks**: STORY-001, STORY-003

---

### TECH-002: Timeout + Fallback explícito en VisionAgent
**Source**: Findings #6, #7 — Orchestration Diagram · **Severidad**: 🔴 Crítico · **System type**: Agentic  
**Finding**: Sin timeout, LLM lento congela el run. Sin fallback visible, excepción colapsa el análisis del ticker.

```python
# vision_agent.py
try:
    response = litellm.completion(
        model=MODEL, messages=prompt,
        response_format=AssetAnalysis,
        timeout=int(os.getenv("VISION_AGENT_TIMEOUT", 15))
    )
except litellm.Timeout:
    logger.warning("VisionAgent timeout for %s", ticker)
    return AssetAnalysis(ticker=ticker, signal="AVOID",
                         confidence=0, argument="Analysis unavailable — timeout")
```

**Acceptance criteria**:
- [ ] `timeout` configurable vía `VISION_AGENT_TIMEOUT` env var (default: 15)
- [ ] Timeout retorna degraded `AssetAnalysis`, nunca propaga excepción
- [ ] `test_vision_agent.py`: mock `litellm.Timeout` → degraded result
- [ ] Diagrama de orquestación actualizado con ruta de fallback visible

**Effort**: Low 1-2h · **Sprint**: Slice 0 · **Blocks**: ninguno

---

### TECH-003: Batch SQL para score_delta
**Source**: Finding #9 — Sequence Diagram · **Severidad**: 🟡 Media · **System type**: Deterministic  
**Finding**: 30 queries secuenciales para `score_delta` dentro del loop de Stage 4.

```python
# scoring_agent.py — ANTES del loop
prior = db.execute(
    "SELECT ticker, score FROM analysis_results WHERE run_id = "
    "(SELECT run_id FROM analysis_results ORDER BY analyzed_at DESC LIMIT 1 OFFSET 1)"
).fetchall()
prior_scores = {r["ticker"]: r["score"] for r in prior}

# DENTRO del loop (sin I/O):
score_delta = round(score - prior_scores.get(ticker, score), 2)
```

**Acceptance criteria**:
- [ ] Una sola query SQL fuera del loop (no N queries dentro)
- [ ] `score_delta = 0.0` cuando no hay run previo
- [ ] Test: delta correcto entre dos runs consecutivos

**Effort**: Low 1h · **Sprint**: Slice 1

---

### TECH-004: Optimistic locking en OutcomeDetector
**Source**: Finding #8 — Orchestration Diagram · **Severidad**: 🟠 Alta · **System type**: Deterministic  
**Finding**: Dos instancias simultáneas pueden escribir outcomes duplicados corrompiendo HR/PF.

```python
# outcome_detector.py
rows = db.execute(
    "UPDATE analysis_results SET outcome=?, actual_gain_pct=?, hold_days=? "
    "WHERE id=? AND outcome IS NULL",
    (outcome, gain_pct, hold_days, signal_id)
).rowcount

if rows == 0:
    logger.info("Outcome already written for %s — skipping (idempotent)", ticker)
```

**Acceptance criteria**:
- [ ] `UPDATE WHERE outcome IS NULL` — atómico
- [ ] `rowcount == 0` logueado como INFO, no como error
- [ ] Test: 2 runs → métricas idénticas

**Effort**: Low 1h · **Sprint**: Slice 0 · **Blocks**: STORY-004

---

### TECH-005: GuardrailValidator entre VisionAgent y ScoringAgent
**Source**: Finding #3 — Architecture Diagram · **Severidad**: 🟠 Alta · **System type**: Agentic  
**Finding**: LLM puede generar `AssetAnalysis` con `stop_loss > entry_price` que llegaría al dashboard.

```python
# scoring_agent.py
def validate_asset_analysis(asset: AssetAnalysis) -> tuple[bool, str]:
    if asset.entry_price <= 0:          return False, "entry_price <= 0"
    if asset.stop_loss >= asset.entry_price:   return False, "stop_loss >= entry_price"
    if asset.target_price <= asset.entry_price: return False, "target_price <= entry_price"
    if asset.risk_reward_ratio < 0:     return False, "negative R/R"
    return True, ""

# Antes del loop de scoring:
valid, reason = validate_asset_analysis(asset)
if not valid:
    asset.rank = None
    errors.append({"ticker": asset.ticker, "error": f"structural_invalid: {reason}"})
    continue
```

**Acceptance criteria**:
- [ ] `validate_asset_analysis` ejecuta antes del scoring loop
- [ ] Assets inválidos tienen `rank=None` y aparecen en `errors[]`
- [ ] `test_scoring_agent.py` cubre los 4 casos de validación fallida
- [ ] Architecture Diagram actualizado con nodo `GuardrailValidator`

**Effort**: Low 2h · **Sprint**: Slice 0 · **Blocks**: ninguno

---

### TECH-006: Structured logging por stage en OrchestratorAgent
**Source**: Finding #4 — Architecture Diagram · **Severidad**: 🟠 Alta · **System type**: Hybrid  
**Finding**: Sin logging estructurado por stage, un run lento no puede diagnosticarse en producción.

```python
# orchestrator.py
import time, logging
logger = logging.getLogger("finally.orchestrator")

t_stage = time.time()
# al finalizar cada stage:
logger.info("stage_complete", extra={
    "stage": 1, "run_id": run_id,
    "duration_ms": int((time.time() - t_stage) * 1000),
    "tickers": len(tickers),
    "errors": sum(1 for r in results if isinstance(r, Exception))
})
# al finalizar el run:
logger.info("run_complete", extra={
    "run_id": run_id,
    "total_ms": int((time.time() - t_start) * 1000),
    "signals_generated": len(top_5),
    "error_count": len(errors)
})
```

**Acceptance criteria**:
- [ ] Cada stage emite: `duration_ms`, `tickers`, `error_count`
- [ ] Run completo emite: `run_id`, `total_ms`, `signals_generated`, `error_count`
- [ ] Logs son JSON estructurado (no f-strings)
- [ ] `AnalysisResult.duration_seconds` lleno con tiempo real del run

**Effort**: Medium 3-4h · **Sprint**: Slice 1

---

## 12. Pre-Development Checklist

**Schema & Data Layer**
- [ ] Migration (9 ALTER TABLE) ejecutada en transacción, testeada en dev DB
- [ ] Index `idx_outcome` creado
- [ ] SQLite ≥ 3.35 confirmada en Docker image

**ScoringAgent (STORY-001, 005, 006)**
- [ ] `score_delta` batch SQL (TECH-003) — una query, no N queries
- [ ] `expected_value_per10` guarded: `if entry_price > 0`
- [ ] `GuardrailValidator` antes de scoring (TECH-005)
- [ ] Unit of Work en write (TECH-001)
- [ ] `test_scoring_agent.py` actualizado: batch delta, validación estructural, DB error

**DataAgent (STORY-005, 006)**
- [ ] `atr_14`, `atr_14_pct`, `sma_20`, `sma_50` en `TechnicalIndicators`
- [ ] `dropna()` después de toda computación de indicadores
- [ ] `test_data_agent.py` actualizado con NaN en mock yfinance

**VisionAgent**
- [ ] `timeout=15` vía `VISION_AGENT_TIMEOUT` (TECH-002)
- [ ] Degraded fallback testeado con `litellm.Timeout` mock

**OutcomeDetector (STORY-003)**
- [ ] Optimistic locking `UPDATE WHERE outcome IS NULL` (TECH-004)
- [ ] `actual_gain_pct` validado NOT NULL antes de write
- [ ] Test idempotencia: 2 runs → mismos resultados

**OrchestratorAgent**
- [ ] Structured logging por stage (TECH-006)
- [ ] Per-asset error isolation: fallo de un ticker no aborta run

**PerformanceSummary (STORY-004, 007)**
- [ ] Phase gate: 29 → sin métricas, 30 → unlocked
- [ ] EXPIRED excluidos del HR/PF
- [ ] Zero-division guard: `sum_losses = 0` → 999.0
- [ ] EV badge boundary: 29 → "@ 35% assumed", 30 → "@ N% realized"
