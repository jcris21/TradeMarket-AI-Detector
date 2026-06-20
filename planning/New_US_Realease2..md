# FinAlly — User Stories: 100-Ticker Scale-Up, Top Opportunities UX & Scoring Architecture
## Consolidated Feature Specs v3 | Engineering-Ready | Kaabar Back-Test Validated

> **Context:** The FinAlly scoring system currently analyzes 10 tickers per run with a
> 4-stage pipeline (DataAgent → ScreenshotAgent → VisionAgent → ScoringAgent).
>
> **Architectural decision adopted in v3:** ScreenshotAgent and VisionAgent are removed
> from the batch analysis run entirely. The run pipeline is now two stages:
> DataAgent × N → ScoringAgent (quantitative-only). Visual enrichment becomes an
> on-demand flow, triggered manually by the trader on a specific signal after reviewing
> the Top 20 results. This resolves the latency bottleneck at 100 tickers, produces a
> 100% back-testeable base score, and eliminates confirmation bias from the batch loop.
>
> **Two enrichment paths exist post-signal-review:**
> - **Enrichment A:** Trader uploads their own annotated chart → constrained S/R extraction
> - **Enrichment B:** Trader requests auto-screenshot of a web source → full VisionAgent analysis
>
> Both paths produce an `enrichment_delta` added to the base `score_quant`, stored
> separately, and visible in the UI as a scored increment — not as a replacement of the
> base score.

---

## Architecture: Before vs After

```
BEFORE (v2) — batch pipeline, all tickers, blocking
────────────────────────────────────────────────────
Trigger run
  ├── Stage 1: DataAgent × N      parallel, asyncio.gather
  ├── Stage 2: ScreenshotAgent    serial, one browser, 30-90s per 10 tickers
  ├── Stage 3: VisionAgent × N    parallel, LLM API calls
  └── Stage 4: ScoringAgent       confidence(30%) + quant(70%)
  Total at 100 tickers: 400–900 seconds estimated

AFTER (v3) — split pipeline: batch quant + on-demand visual
────────────────────────────────────────────────────────────
FLOW A: Batch Analysis Run (always, automated)
  ├── Stage 1: DataAgent × 100    parallel, asyncio.Semaphore(20)
  └── Stage 2: ScoringAgent       quantitative-only, score_quant (0–100)
  Total at 100 tickers: 30–90 seconds

FLOW B: Signal Enrichment (manual, on-demand, per signal)
  ├── Trigger: trader selects signal from Top 20
  ├── Path B1 — Trader chart upload
  │     └── VisionAgent           constrained S/R extraction, no Playwright
  │     └── ScoringAgent patch    score_quant + enrichment_delta_b1
  └── Path B2 — Auto screenshot request
        ├── ScreenshotAgent       Playwright, single ticker, single URL
        ├── VisionAgent           full analysis on screenshot
        └── ScoringAgent patch    score_quant + enrichment_delta_b2

score_enriched = score_quant + enrichment_delta  (displayed as: "82 → 89 (+7 visual)")
```

---

## Epic Map (v3)

```
EPIC 1 — DATA LAYER SCALE-UP
  US-101  Ticker Universe Management (add/remove with concentration guardrails)  <- UPDATED v4
  US-102  DataAgent Parallelism (fan-out to 100 tickers without timeout)
  US-103  yfinance Rate-Limit Resilience
  US-104  Default Universe Seed (100 diversified tickers replacing 10-ticker seed) <- NEW v4

EPIC 2 — PIPELINE SCALE-UP
  US-201  ScreenshotAgent On-Demand (replaces Browser Pool - REVISED v3)
  US-202  ScoringAgent Sector Cap Enforcement
  US-203  Regime Gate (SMA200 + VIX pre-filter)
  US-204  Analysis Run Observability (progress + partial results)

EPIC 3 — SCORING INTEGRITY (TWO-LAYER SCORE ARCHITECTURE)
  US-301  Two-Layer Score: score_quant + enrichment_delta (REVISED v3)
  US-302  Signal Enrichment: Trader Chart Upload (Path B1)
  US-303  Signal Enrichment: Auto Screenshot Request (Path B2)

EPIC 4 — TOP OPPORTUNITIES PANEL UX
  US-401  Top 20 Signal Display with Pagination (10 per page)
  US-402  Collapsible Top Opportunities Section
  US-403  Score Band Visual Segmentation
  US-404  Signal Freshness & Decay Indicator
```

> **v4 changes from v3:**
> - US-101 updated: adds soft concentration warning (R8) and universe diversity score (R9)
>   for on-demand ticker additions; removes erroneous "backfill 10 existing seed tickers"
>   requirement — seed is fully replaced by US-104, not patched incrementally
> - US-104 added: defines the Proportional Sector Seed of 100 diversified tickers that
>   replaces the current 10-ticker seed at first install; includes sector allocation table,
>   liquidity selection criteria, and DataAgent validation rules per ticker
> - Dependency map and sprint order updated: US-104 ships in Sprint 0 (database migration,
>   no code dependencies); US-101 diversity warning uses the seed distribution as its baseline

---

## EPIC 1 — Data Layer Scale-Up

---

### US-101 — Ticker Universe Management (v4: + Concentration Guardrails)

> **v4 update:** R4 no longer backfills the existing 10-ticker seed — those tickers are
> fully replaced by US-104's 100-ticker seed. The `sector` field arrives pre-populated
> via US-104's migration. R8 (soft warning) and R9 (diversity score) are new requirements
> that operate exclusively on **trader-initiated additions**, not on the seed itself.

**As a** swing trader using FinAlly,
**I want** to add, remove, and manage tickers in my analysis universe through the UI and API,
and receive a soft warning when my additions push a sector above the recommended concentration
threshold,
**so that** I can curate my universe freely while staying informed about concentration risk
before it manifests as correlated stop-outs in the Top 20.

#### Problem Statement

When the system initialises with the US-104 seed (100 diversified tickers), the sector
distribution is balanced by design. But as the trader adds tickers over time under demand
— a new earnings play, a sector rotation idea, a tip from a research report — the
universe can drift toward concentration without the trader noticing. The system currently
has no mechanism to surface this drift at the moment of addition, when it is cheapest to
address.

The sector cap (US-202) mitigates concentration at the ranking level, but it silently
discards valid signals. The correct prevention layer is earlier: inform the trader at
ingestion time when a sector is becoming over-represented, so they can choose to balance
before the cap is needed.

#### Goals

- Trader can add and remove tickers freely; no hard block on sector composition
- Trader is informed when a sector exceeds the recommended threshold during bulk add
- Universe diversity is visible at a glance without navigating to a separate report page
- Sector metadata is always present for ScoringAgent sector cap (US-202) and regime gate (US-203)

#### Non-Goals

- Hard-blocking adds that exceed a sector threshold (soft warning only — trader autonomy preserved)
- Automatic rebalancing or ticker suggestions to restore diversity (future v2)
- Real-time streaming price data for all 100 tickers (market data subsystem scope)
- Portfolio management or position tracking for the expanded universe

#### Requirements

**P0 — Must Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R1 | Universe hard cap | `POST /api/analysis/tickers` returns HTTP 422 with `"max_tickers": 100` when universe has 100 entries. Count check before any DB write. |
| R2 | Bulk add endpoint | `POST /api/analysis/tickers/bulk` accepts `{"tickers": [...], "sector": "tech"}`. Max 20 per request. Returns `{"added": [...], "rejected": [...], "already_existed": [...], "concentration_warnings": [...], "reason": {...}}`. |
| R3 | Ticker validation on add | DataAgent fetches 60 days of daily data, asserts `len(df) >= 50` and `avg_volume >= 500_000` (liquidity floor). Failure → rejected with `"reason": "insufficient_data"` or `"reason": "insufficient_liquidity"`. |
| R4 | Sector field | `analysis_tickers` has `sector TEXT NOT NULL DEFAULT 'unknown'`. Field arrives pre-populated for seed tickers via US-104 migration. No backfill of existing 10-ticker seed required — US-104 replaces it entirely. |
| R5 | Bulk remove endpoint | `DELETE /api/analysis/tickers/bulk` accepts `{"tickers": [...]}`. Does not affect `watchlist` table. |

**P1 — Should Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R6 | Sector breakdown in list | `GET /api/analysis/tickers` response includes `sector_breakdown: {"tech": 35, "finance": 12, ...}` and `total: 100` at top level. |
| R7 | Duplicate detection | Tickers already in universe silently skipped, counted in `"already_existed"`. |
| R8 | Soft concentration warning on add | Before committing a bulk add, compute post-add sector percentages. If any sector would exceed `UNIVERSE_SECTOR_WARN_PCT` (default: 30%), include in response: `"concentration_warnings": [{"sector": "tech", "current_pct": 28, "post_add_pct": 34, "threshold_pct": 30, "message": "Tech would reach 34% of your universe (recommended max: 30%). Proceeding — consider adding tickers from other sectors to reduce concentration risk."}]`. The add still succeeds. No HTTP error raised. |
| R9 | Universe Diversity Score in UI | The ticker management page displays a persistent **Universe Diversity Score** (0–100) updated after each add or remove. Calculation: `100 - (sum of squared sector deviation from S&P 500 weights) × scaling_factor`. Score ≥ 70: green. 50–69: amber. < 50: red with label "High concentration risk". Score shown as a single number with a colour indicator — no detailed chart required for v1. |

**P2 — Future**

- CSV import of ticker lists
- Smart rebalancing suggestions: "Add 3 Healthcare tickers to improve your score from 58 to 74"
- Scheduled universe drift alerts (weekly email if diversity score drops below threshold)

#### Acceptance Criteria (Story Level)

```gherkin
Given the universe has 28 tech tickers out of 80 (35%)
And UNIVERSE_SECTOR_WARN_PCT = 30
When the trader bulk-adds 5 more tech tickers
Then all 5 are added (no block)
And the response includes concentration_warnings for tech
And the warning shows post_add_pct = 41% and threshold_pct = 30%
And the Universe Diversity Score in the UI updates and drops to amber

Given the universe has 20 tech tickers out of 80 (25%)
When the trader bulk-adds 3 tech tickers
Then all 3 are added
And concentration_warnings is an empty array (28/83 = 33.7% > 30% threshold)
-- correction: 23/83 = 27.7% < 30% threshold, so no warning
And the Diversity Score remains green

Given the universe has exactly 100 tickers
When the trader attempts to add 1 more ticker
Then HTTP 422 is returned with "max_tickers": 100
And no DB write occurs
```

#### Open Questions

- **[Engineering]** Should validation (R3) be synchronous or async? 20 tickers ≈ 10 seconds with yfinance. Async with status polling is cleaner UX but adds complexity.
- **[Product]** Sector field: free-text or enum? Free-text supports international tickers and edge cases. Enum enforces consistency for sector cap logic. Recommended: enum with an `"other"` escape hatch.
- **[Product]** `UNIVERSE_SECTOR_WARN_PCT` default of 30%: is this the right threshold? At 30%, a universe of 100 would warn when a sector hits 30 tickers — which is already 3× the sector cap of 2 per Top 20. A trader could argue 40% is more reasonable. Should be configurable per the env var pattern used throughout.

---

### US-102 — DataAgent Parallelism at 100 Tickers

**As a** trader who has configured a 100-ticker universe,
**I want** the batch analysis run to complete within 90 seconds at full scale,
**so that** I can review quantitative signals before the trading day begins without
the pipeline becoming a bottleneck.

#### Problem Statement

With ScreenshotAgent and VisionAgent removed from the batch run (v3 architecture),
Stage 1 (DataAgent × 100) and Stage 2 (ScoringAgent) are the entire pipeline.
The latency target drops from "< 5 minutes" to "< 90 seconds" because there is no
longer a Playwright stage to account for. However, yfinance has undocumented rate-limiting
behavior that causes silent empty-DataFrame responses at 100 concurrent requests.
Unthrottled parallel calls at 100 tickers produce 30–50% data failures.

#### Goals

- Batch analysis run (DataAgent × 100 + ScoringAgent) completes in under 90 seconds
- Zero silent data failures: every ticker returns valid data or appears in `errors`
- Partial results returned if ≥ 70 of 100 tickers succeed

#### Non-Goals

- Switching from yfinance to a paid real-time data feed
- Sub-second data freshness (daily candles sufficient for swing trading)

#### Requirements

**P0 — Must Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R1 | Concurrency limit | Stage 1 uses `asyncio.Semaphore(20)`. Configurable via `ANALYSIS_DATA_CONCURRENCY` (default: 20). |
| R2 | Per-ticker retry | Each DataAgent call retries up to 2 times with 1-second backoff. Third failure recorded in `errors`. |
| R3 | Data validation assertion | DataAgent asserts `len(df) >= 60` and `current_price > 0`. Fails with `DataFetchError` otherwise. |
| R4 | Minimum viable run | OrchestratorAgent proceeds if `len(completed) >= 0.7 * len(tickers)`. Below 70%: HTTP 503 `"insufficient_data_coverage"`. |
| R5 | Duration in response | `AnalysisResult.duration_seconds` surfaced in `GET /api/analysis/latest`. |

**P1 — Should Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R6 | Staggered batch start | Calls dispatched in batches of 20 with 0.5-second delay between batches. |
| R7 | Per-ticker timing | `errors` list includes `duration_ms` per failed ticker. |

#### Acceptance Criteria (Story Level)

```gherkin
Given a 100-ticker universe is configured
When the trader triggers an analysis run
Then Stage 1 (DataAgent × 100) completes within 60 seconds
And Stage 2 (ScoringAgent quant-only) completes within 10 seconds
And total run completes in under 90 seconds
And errors list contains only tickers where yfinance genuinely returned no data

Given yfinance returns empty DataFrame for 5 tickers mid-run
When Stage 1 completes
Then those 5 tickers appear in errors with "reason": "empty_dataframe"
And the remaining 95 tickers produce valid AssetAnalysis with score_quant populated
And AnalysisResult is returned without HTTP 500
```

---

### US-103 — yfinance Rate-Limit Resilience

**As a** trader running daily analysis on 100 tickers,
**I want** the system to handle yfinance rate limiting gracefully without crashing,
**so that** a transient API issue does not silently corrupt signal quality.

#### Requirements

**P0 — Must Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R1 | Detect HTTP 429 | DataAgent catches `YFRateLimitError` and raises `DataFetchError(ticker, reason="rate_limited")`. |
| R2 | Exponential backoff | On rate-limit: wait `2^attempt` seconds (2s, 4s) before retry. Max 2 retries. |
| R3 | Rate-limit telemetry | `errors` distinguishes `"reason": "rate_limited"` from `"reason": "empty_dataframe"`. |

**P1 — Should Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R4 | Staleness fallback | All retries fail → check `analysis_results` for last 24h result. If found, use cached indicators with `is_stale: true`. Stale signals show a warning badge in UI. |

---

### US-104 — Default Universe Seed (100 Diversified Tickers)

> **New in v4.** This story defines the 100-ticker default universe that replaces the
> existing 10-ticker seed (`AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX`)
> which has a 70% tech concentration. The new seed is the starting point every new
> FinAlly installation begins with. It is a data migration and a product decision about
> what "balanced by default" means — not a user-facing feature.

**As a** new FinAlly user launching the system for the first time,
**I want** the analysis universe to be pre-populated with 100 diversified tickers
selected for liquidity and sector balance,
**so that** my first analysis run immediately surfaces opportunities across multiple
sectors without requiring manual curation, and without the concentration risk of the
current 70%-tech seed.

#### Problem Statement

The current seed (`PLAN.md §7`) has 10 tickers: 7 tech, 2 finance, 1 EV/auto — a 70%
tech concentration that violates the sector cap (US-202) before the trader has added
a single ticker. A strong tech day generates 5–7 tech signals, all but 2 discarded
by the cap, wasting the analysis budget on correlated opportunities.

Beyond concentration risk, a 10-ticker seed means the system reaches Kaabar's 30-signal
statistical minimum only after 5+ days at 2–4 signals/run. A 100-ticker seed reaches 30
signals in under 2 days even at conservative hit rates, enabling the back-test validation
plan to begin meaningfully in the first trading week.

The seed is not random and not "the 100 most liquid US equities" — that would produce
~40 tech tickers. The seed uses a **Proportional Sector Allocation** based on S&P 500
sector weights, with a floor per sector to ensure no sector is absent, and tickers
selected by market cap descending within each sector to maximise liquidity and yfinance
data reliability.

#### Goals

- First analysis run on a fresh install analyzes a sector-balanced universe with no setup required
- All 100 seed tickers pass DataAgent validation (≥ 50 rows daily data, avg volume ≥ 500k)
- Seed is reproducible: same 100 tickers installed on every fresh deployment
- Seed is maintainable: a single `seed_tickers.py` file defines the list, updatable without schema changes
- Existing user data is preserved: migration is additive if the trader has already added custom tickers

#### Non-Goals

- Dynamic seed that auto-updates when S&P 500 composition changes (future v2 — seed is static)
- International tickers (US equities only for v1 — yfinance coverage is consistent)
- Cryptocurrency or futures (out of scope for swing trading)
- Modifying the `watchlist` table seed (separate concern — `PLAN.md §7` watchlist seed unchanged)

#### Sector Allocation Table

| Sector | S&P 500 Weight | Seed Tickers | Floor | Selection Criteria |
|--------|---------------|--------------|-------|-------------------|
| Technology | 28% | 22 | 5 | Top 22 by market cap: AAPL, MSFT, NVDA, AVGO, ORCL, CSCO, ADBE, CRM, AMD, INTC, QCOM, TXN, INTU, NOW, AMAT, MU, KLAC, LRCX, PANW, SNPS, CDNS, MRVL |
| Finance / Banking | 13% | 13 | 5 | Top 13: JPM, V, MA, BAC, WFC, GS, MS, BLK, SPGI, AXP, C, CB, PGR |
| Healthcare | 12% | 12 | 5 | Top 12: UNH, LLY, JNJ, ABBV, MRK, TMO, ABT, DHR, BMY, AMGN, PFE, GILD |
| Consumer Discretionary | 10% | 10 | 5 | Top 10: AMZN, TSLA, HD, MCD, NKE, LOW, TJX, SBUX, BKNG, ABNB |
| Industrials | 8% | 8 | 5 | Top 8: GE, CAT, RTX, HON, UNP, BA, DE, LMT |
| Communication Services | 8% | 8 | 5 | Top 8: GOOGL, META, NFLX, DIS, CHTR, T, VZ, TMUS |
| Consumer Staples | 7% | 7 | 5 | Top 7: PG, KO, PEP, WMT, COST, PM, MDLZ |
| Energy | 4% | 4 | 4 | Top 4: XOM, CVX, COP, EOG |
| Real Estate | 3% | 3 | 3 | Top 3: PLD, AMT, EQIX |
| Materials | 3% | 3 | 3 | Top 3: LIN, SHW, ECL |
| Utilities | 3% | 3 | 3 | Top 3: NEE, DUK, SO |
| Index ETFs | — | 5 | 5 | SPY, QQQ, IWM, GLD, TLT |
| **TOTAL** | **100%** | **100** | | |

> **ETFs rationale:** SPY and QQQ provide market-wide context for the regime gate (US-203).
> GLD and TLT have negative/low correlation with equities — natural diversifiers and
> risk-off canaries. IWM (small cap) covers a segment absent from the large-cap sectors.
> ETFs are not subject to sector cap (US-202) since they have no equity sector assignment.

#### Requirements

**P0 — Must Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R1 | Seed file as single source of truth | `backend/app/analysis/seed_tickers.py` contains `SEED_UNIVERSE: list[dict]` — 100 entries, each `{"ticker": str, "sector": str, "sub_sector": str}`. No hardcoded ticker lists anywhere else in the codebase. |
| R2 | Migration: replace legacy 10-ticker seed | If `analysis_tickers` contains exactly the legacy 10 tickers and nothing else: truncate and insert 100 seed tickers. If the table has any trader-added tickers beyond the legacy 10: additive merge only — insert seed tickers not already present, preserve trader-added tickers. |
| R3 | All seed tickers pass DataAgent validation | CI test: for every ticker in `SEED_UNIVERSE`, yfinance returns `len(df) >= 50` rows of daily data and `df["Volume"].mean() >= 500_000`. Uses 30-day window. Any failure blocks the merge. |
| R4 | Sector field pre-populated | All seed tickers inserted with their `sector` value from `SEED_UNIVERSE`. No seed ticker has `sector = "unknown"`. |
| R5 | Fresh install seeds 100 tickers | On a fresh SQLite DB, lazy init creates `analysis_tickers` and inserts all 100. `GET /api/analysis/tickers` returns 100 on first request. |
| R6 | Seed version tracked | `analysis_tickers` adds `seed_version TEXT DEFAULT NULL`. All US-104-inserted tickers: `seed_version = "v1"`. Trader-added tickers: `seed_version = NULL`. Enables differential future seed updates. |

**P1 — Should Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R7 | Startup log | On seeding: `"Seeded analysis universe: 100 tickers across 12 sectors (v1). Tech: 22%, Finance: 13%, ..."` |
| R8 | SEED badge in UI | Ticker management page shows a `SEED` badge on tickers with `seed_version = "v1"`. Trader-added tickers have no badge. |

**P2 — Future**

- Seed v2: annual refresh reflecting index rebalancing
- Auto-replace delisted seed tickers with next market-cap ticker in same sector
- Configurable seed presets: "Balanced (S&P weighted)", "Momentum (high beta)", "Defensive (low vol)"

#### Acceptance Criteria (Story Level)

```gherkin
Given a fresh FinAlly installation with empty analysis_tickers
When the backend starts and lazy init runs
Then 100 tickers are inserted from SEED_UNIVERSE
And each ticker has a non-null sector value and seed_version = "v1"
And GET /api/analysis/tickers returns sector_breakdown with 12 sectors

Given an existing install with exactly the legacy 10 tickers and no custom additions
When the migration script runs
Then analysis_tickers is truncated
And 100 seed tickers are inserted with seed_version = "v1"

Given an existing install with the legacy 10 tickers plus 5 trader-added tickers
When the migration script runs
Then the 5 trader-added tickers are preserved with seed_version = NULL
And seed tickers not already present are inserted additively
And no trader-added ticker is deleted or modified

Given the CI test runs against SEED_UNIVERSE
When yfinance is queried for all 100 tickers
Then every ticker returns len(df) >= 50 rows with avg_volume >= 500_000
And any failing ticker causes the CI build to fail with the ticker name and failure reason
```

#### Open Questions

- **[Product]** Should ETFs be subject to sector cap (US-202)? Recommended: no — they have `sector = "etf"` and the sector cap logic skips tickers with sector not in the equity sector list.
- **[Engineering]** Migration detection: define "exactly the legacy 10 tickers" as: `set(current_tickers) == {"AAPL","GOOGL","MSFT","AMZN","TSLA","NVDA","META","JPM","V","NFLX"}`. Any deviation from this exact set = user-customised = additive merge.
- **[Data]** The 100 tickers named in the allocation table must be validated by CI (R3) before merge. Replace any that fail with the next highest market-cap ticker in the same sector. Document replacements in `REJECTED_FROM_SEED` comment in `seed_tickers.py`.

---


## EPIC 2 — Pipeline Scale-Up

---

### US-201 — ScreenshotAgent On-Demand (Single Ticker)

> **v3 change:** The Browser Pool story (v2 US-201) is **replaced** by this story.
> ScreenshotAgent is no longer part of the batch analysis run. It activates only when
> the trader explicitly requests a screenshot enrichment for a specific signal (Flow B,
> Path B2 — see US-303). This eliminates the need for browser pooling entirely and
> reduces ScreenshotAgent to a lightweight single-invocation service.

**As a** trader who wants a deeper visual analysis of a specific ranked signal,
**I want** to trigger an on-demand screenshot capture of that ticker's chart from a
specified web source,
**so that** the VisionAgent can perform a full analysis on fresh chart data for that
signal without blocking the initial 100-ticker batch run.

#### Problem Statement

In v2, ScreenshotAgent ran in the batch pipeline for all N tickers — a serial bottleneck
of 30–90 seconds for 10 tickers, estimated 300–900 seconds for 100 tickers. In v3,
screenshots are decoupled from the batch run. The trader receives the Top 20 quantitative
results immediately (< 90 seconds), then optionally requests a screenshot enrichment for
one or more signals they want to investigate further.

A single-ticker screenshot via Playwright takes 5–15 seconds. There is no parallelism
requirement for a single-signal request. The complexity of the browser pool (Playwright
async concurrency spike, memory guards, per-browser auth isolation) is no longer needed.

#### Goals

- Trader can trigger a screenshot enrichment for any ranked signal within 2 clicks
- Screenshot capture + VisionAgent full analysis completes within 30 seconds per signal
- ScreenshotAgent remains off by default; activates only on explicit trader request

#### Non-Goals

- Batch screenshot capture for all 100 tickers (permanently removed from batch flow)
- Browser pooling (single-ticker use case requires exactly one browser instance)
- Auto-triggering screenshots based on score threshold (trader opts in manually)

#### Requirements

**P0 — Must Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R1 | Enrichment trigger endpoint | `POST /api/analysis/enrich/{ticker}` with body `{"source_url": str, "enrichment_type": "screenshot"}`. Returns `{enrichment_id, status: "pending"}` immediately. |
| R2 | Single-browser Playwright session | ScreenshotAgent launches one headless Chromium browser, navigates to `source_url`, screenshots the chart region, closes browser. All in one invocation. |
| R3 | Configurable source URL | `source_url` is trader-provided per request. Not hardcoded to investing.com. Trader can point to TradingView, Finviz, or any chart URL they use. Validated: must be `https://` and from a domain not in a block list. |
| R4 | Screenshot passed to VisionAgent | Screenshot bytes passed to VisionAgent for full analysis (signal + argument + support validation). VisionAgent returns full `AssetAnalysis` enrichment output. |
| R5 | Enrichment stored separately | Results stored as `enrichment_delta` in `analysis_results` alongside `score_quant`. Score shown in UI as `"82 → 89 (+7)"`. |
| R6 | Timeout and error handling | Per-request timeout: 30 seconds. On timeout or navigation failure, `enrichment_status: "failed"` returned. Score remains `score_quant` unchanged. |

**P1 — Should Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R7 | Default URL per ticker | Trader can save a preferred chart URL per ticker in `analysis_tickers.preferred_chart_url`. Pre-filled in the enrichment request form. |
| R8 | Enrichment status in UI | The signal row in Top 20 shows enrichment status badge: `Enriching...` (spinner) → `+7 visual` (on complete) → `Failed` (on error). |

#### Acceptance Criteria (Story Level)

```gherkin
Given the trader selects AAPL from the Top 20 and clicks "Request Screenshot Enrichment"
And enters source_url = "https://www.tradingview.com/chart/?symbol=AAPL"
When POST /api/analysis/enrich/AAPL is called
Then ScreenshotAgent launches one Chromium instance
And navigates to the TradingView URL
And captures a screenshot of the chart region
And passes the screenshot to VisionAgent
And VisionAgent returns enrichment_delta (confidence, argument, support_validated)
And the AAPL row in Top 20 updates from "score: 82" to "score: 82 → 89 (+7 visual)"
And total time from request to score update is under 30 seconds

Given ScreenshotAgent fails to load the page within 30 seconds
When the timeout fires
Then enrichment_status = "failed" for the ticker
And score_quant (82) remains the displayed score
And the signal row shows "Enrichment failed — retry?"
```

#### Open Questions

- **[Product]** Should the trader be required to provide a URL, or should the system attempt to auto-resolve the ticker to a known chart URL (investing.com, TradingView)?
- **[Security]** `source_url` is trader-provided. What is the block list policy? At minimum: localhost, internal network ranges (RFC 1918), and known data-exfiltration domains.

---

### US-202 — ScoringAgent Sector Cap Enforcement

**As a** trader using FinAlly's Top Opportunities panel,
**I want** the system to automatically enforce a maximum of 2 signals per sector in the
ranked results,
**so that** my Top 20 is never silently concentrated in a single sector when tech stocks
all move together.

#### Problem Statement

With 100 tickers and ~40 tech (correlated at r=0.6), a strong tech day produces 20–28
qualifying tech signals. Without a cap the Top 20 would be overwhelmingly tech, creating
Pareto Scenario 2 (Critical Analysis Report): a single negative tech catalyst stops out
15+ positions simultaneously.

#### Requirements

**P0 — Must Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R1 | Sector cap in Top-N selection | After scoring, ScoringAgent selects Top N by `score_quant` descending, enforcing max `ANALYSIS_SECTOR_CAP` (default: 2) per sector. Tickers beyond cap get `rank=None`. |
| R2 | Configurable cap | `ANALYSIS_SECTOR_CAP` env var. Allowed: 1–5. Default: 2. |
| R3 | Cap reason in output | `AssetAnalysis.rank_exclusion_reason: Optional[str]`. Sector-capped tickers: `"sector_cap:tech"`. |
| R4 | Unknown sector passes freely | `sector == "unknown"` → not subject to cap. |

**P1 — Should Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R5 | Cap summary in response | `AnalysisResult.sector_cap_exclusions: {"tech": 12, "finance": 3}`. |

---

### US-203 — Regime Gate: SMA200 + VIX Pre-Filter

**As a** trader using FinAlly,
**I want** the system to automatically suppress BUY signals during bear market regimes,
**so that** the run does not generate high-scoring setups that will overwhelmingly stop
out due to macro conditions rather than pattern failure.

#### Problem Statement

Without a regime gate, a bear market day generates 15–20 high-scoring BUY signals that
all fail for the same reason — macro environment. This destroys the hit ratio and
potentially causes the trader to abandon the system prematurely. This is the P1 mitigation
from the Critical Analysis Report (Scenario 1: Regime Change).

#### Requirements

**P0 — Must Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R1 | SMA200 per-ticker check | DataAgent adds `regime_bullish: bool` to `TechnicalIndicators`: True if `current_price > SMA200`. |
| R2 | SMA200 gate in ScoringAgent | `regime_bullish == False` → `signal="AVOID"`, `rank=None`, `rank_exclusion_reason="regime_bearish"`. |
| R3 | VIX system-wide gate | OrchestratorAgent fetches `^VIX` at run start. If `VIX > ANALYSIS_VIX_THRESHOLD` (default: 25.0), all BUY signals suppressed. `AnalysisResult` includes `regime_gate_active: bool` and `vix_value: float`. |
| R4 | Configurable threshold | `ANALYSIS_VIX_THRESHOLD` env var (default: 25.0). Set to 999 to disable. |

**P1 — Should Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R5 | Regime banner in UI | When `regime_gate_active: true`, Top Opportunities panel shows: `"⚠️ Regime gate active (VIX: 27.3) — BUY signals suppressed."` |

#### Acceptance Criteria (Story Level)

```gherkin
Given VIX closes at 28.5
When an analysis run is triggered
Then regime_gate_active = true in AnalysisResult
And all 100 tickers have signal="AVOID" or signal="WAIT"
And no ticker receives rank 1–20

Given VIX is 18.0 and NVDA has current_price < SMA200
When NVDA is scored
Then NVDA.regime_bullish = false
And NVDA.signal = "AVOID"
And NVDA.rank_exclusion_reason = "regime_bearish"
```

---

### US-204 — Analysis Run Observability

**As a** trader who has triggered an analysis run on 100 tickers,
**I want** to see real-time progress during the run,
**so that** I know the system is working and can estimate when results will be available.

#### Problem Statement

With v3 architecture, the batch run is 30–90 seconds (much faster than v2). However, at
100 tickers with a semaphore of 20, the run takes noticeably longer than the current
10-ticker run. A progress indicator is still needed to confirm the system is processing
and to surface per-ticker errors as they occur.

#### Requirements

**P0 — Must Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R1 | Run status endpoint | `GET /api/analysis/run/{run_id}/status` returns `{run_id, stage: "data\|scoring\|complete", tickers_completed, tickers_total, errors_so_far, started_at}`. Note: only two stages now ("data" and "scoring") — no "screenshot" or "vision" stages. |
| R2 | run_id returned immediately | `POST /api/analysis/run` returns `run_id` before run completes. |
| R3 | Frontend polls status | Frontend polls every 3 seconds. Displays stage label + progress bar `(tickers_completed / tickers_total)`. |

**P1 — Should Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R4 | Estimated time remaining | Status endpoint includes `estimated_remaining_seconds`. |
| R5 | Partial Top 20 visible early | Once ScoringAgent processes first 20 tickers, preliminary ranked results available at `GET /api/analysis/latest?partial=true`. |

---

## EPIC 3 — Scoring Integrity (Two-Layer Score Architecture)

> **Why this epic exists:** Removing ScreenshotAgent and VisionAgent from the batch run
> has a direct consequence on the scoring formula: the `confidence` float from VisionAgent
> no longer exists at batch time. The scoring formula must be rebuilt as a
> quantitative-only base (`score_quant`), with the LLM layer becoming an explicit optional
> increment (`enrichment_delta`) added post-hoc when the trader requests enrichment.
> This separation is architecturally clean, back-testeable, and honest about what each
> layer contributes.

---

### US-301 — Two-Layer Score Architecture: score_quant + enrichment_delta

> **v3 change:** This story replaces "LLM Confidence Weight Reduction (30% → 12%)".
> The old problem was that LLM weight was too high. The new solution is structural:
> the LLM layer is removed from the batch formula entirely and lives only in the
> optional enrichment flow. There is no LLM weight to reduce — there is no LLM
> component in `score_quant` at all.

**As a** FinAlly product owner and back-test engineer,
**I want** the scoring system to produce a fully quantitative base score (`score_quant`)
during the batch run and a separate optional enrichment increment (`enrichment_delta`)
when the trader requests visual analysis,
**so that** the base score is 100% reproducible and back-testeable, and the visual layer's
contribution is explicit, bounded, and traceable against actual trade outcomes.

#### Problem Statement

The current formula mixes quantitative indicators (MACD, RSI, ATR, SMA, BB, volume)
with a VisionAgent LLM confidence float in a single atomic score. This creates three
problems identified in the Critical Analysis Report:

1. **Confirmation bias at the formula level:** The LLM sees an already-bullish chart
   (DataAgent pre-confirmed bullish conditions) and echoes the bullish assessment back
   as a 30-point contribution. The score is counting the same evidence twice.

2. **The base score is not back-testeable:** A signal with `score=78` in history could
   have been 78 because of strong quantitative evidence or because the LLM happened to
   be confident. There is no way to separate these contributions for back-test analysis.

3. **The scoring formula cannot be reproduced:** Running the same ticker data through the
   formula a second time may produce a different LLM confidence float due to LLM
   non-determinism, making the formula non-reproducible.

With v3 architecture (no VisionAgent in batch), the problem dissolves structurally.
This story formalizes the two-layer design and defines the `enrichment_delta` contract.

#### Goals

- `score_quant` is fully deterministic, reproducible, and back-testeable
- `enrichment_delta` is explicitly bounded (max ±15 pts) and always displayed separately
- The trader always knows which layer drove the score they are acting on
- Score comparisons across runs and tickers use `score_quant` as the canonical baseline

#### Non-Goals

- Re-introducing LLM confidence into the batch formula (structurally prevented in v3)
- Changing the R/R minimum gate (remains 3.0)
- Changing the quantitative indicator weights in this story (separate tuning task)

#### Requirements

**P0 — Must Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R1 | score_quant field in AssetAnalysis | `AssetAnalysis` adds `score_quant: float` — the pure quantitative score computed during batch run. This is the ranking field for Top 20. |
| R2 | enrichment_delta field | `AssetAnalysis` adds `enrichment_delta: Optional[float]` — set to None until an enrichment run completes for this signal. |
| R3 | score_enriched derived field | `score_enriched: Optional[float] = score_quant + enrichment_delta` when enrichment_delta is not None. Read-only derived field, not stored separately. |
| R4 | Ranking uses score_quant | ScoringAgent ranks Top 20 by `score_quant` exclusively. `score_enriched` never affects ranking position (to avoid the trader gaming rankings by enriching signals). |
| R5 | score_quant formula documented | `scoring_agent.py` has a structured comment block listing every component, its weight, and its data source. Required as PR acceptance gate. |
| R6 | enrichment_delta ceiling | `abs(enrichment_delta) <= ENRICHMENT_MAX_DELTA` (default: 15). Enrichment results exceeding this are clamped. Prevents a single LLM call from dominating the score. |
| R7 | score_quant is legacy-compatible | For the first 30 days after deployment, `AssetAnalysis` also returns `score_legacy: float` — the old formula with VisionAgent confidence at 30% applied to the last cached VisionAgent output (if any). Allows A/B comparison. After 30 days, `score_legacy` deprecated. |

**P1 — Should Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R8 | Score breakdown in UI | Signal detail panel (on row click) shows: `score_quant components breakdown bar` + `enrichment_delta bar` (shown only if enrichment has run). |
| R9 | Back-test uses score_quant | Back-test plans (backtest_swing.md, backtest_daytrading.md) score signals using `score_quant` exclusively. Enrichment contribution tracked separately in outcome records. |

#### score_quant Formula

```
score_quant = (min(rr_ratio / 6.0, 1.0) × 100 × 0.30)   # R/R ratio
            + (indicator_confluence_score × 0.20)          # MACD + RSI + Volume
            + trend_alignment_score                        # -8 to +14
            + atr_viability_pts                            # -15 to +8 (hard disqualify at 0.5×)
            + bb_squeeze_pts                               # 0 to +5 / -6
            + quantitative_support_score                   # 0 to +18 (Pivot S1 + SMA + BB lower)
            + quantitative_resistance_score                # -3 to +8
            + regime_adjustment                            # 0 or disqualify

# No LLM component. Maximum achievable ≈ 100.
# enrichment_delta is added post-hoc, bounded at ±15.
```

#### Acceptance Criteria (Story Level)

```gherkin
Given a batch analysis run completes for 100 tickers
When the Top 20 results are returned
Then every AssetAnalysis has score_quant populated
And enrichment_delta is None for all (no enrichment has run)
And score_enriched is None for all
And rankings are determined by score_quant exclusively

Given the trader requests enrichment for AAPL (Path B1 or B2)
When enrichment completes with enrichment_delta = +7
Then AAPL.enrichment_delta = 7
And AAPL.score_enriched = score_quant + 7
And AAPL.rank in Top 20 is unchanged (ranking not re-sorted)
And UI shows "82 → 89 (+7 visual enrichment)"

Given enrichment returns a delta of +22 (exceeds ceiling)
When enrichment_delta is stored
Then enrichment_delta is clamped to ENRICHMENT_MAX_DELTA (15)
And score_enriched = score_quant + 15
```

#### Trade-off Registry

| Decision | Alternative | Why Rejected |
|----------|-------------|--------------|
| Ranking by score_quant only | Re-rank after enrichment | Re-ranking after enrichment creates incentive for traders to enrich all signals to game their position, defeating the purpose of the objective quantitative ranking |
| enrichment_delta ceiling ±15 | No ceiling | No ceiling allows a single LLM call to contribute more than the ATR stop viability check (8 pts) or the full confluence score (20 pts) — structurally unbalanced |
| score_legacy for 30 days | Permanent dual score | Two permanent scores creates ongoing confusion about which score to trust. 30-day window enables A/B comparison then forces a clean transition |

---

### US-302 — Signal Enrichment: Trader Chart Upload (Path B1)

**As a** trader who has drawn support and resistance lines on my own chart,
**I want** to upload a screenshot of my annotated chart for a specific ranked signal,
**so that** the system extracts my custom S/R levels, validates them against current
price structure, and adds them as an `enrichment_delta` to that signal's `score_quant` —
giving me a personalized score that reflects my own market structure analysis without
replacing the objective base score.

#### Problem Statement

The Critical Analysis Report identifies exactly one scenario where chart images add
genuine independent value that formulas cannot capture: when the trader provides their
own annotated chart with custom S/R lines drawn, not a default investing.com screenshot.

The batch run cannot use trader charts because: (a) charts are personal and per-signal,
(b) extracting S/R levels requires human validation before scoring, (c) the trader may
not have drawn lines for every ticker in the universe. This flow is correctly on-demand.

**Critical design principle:** The uploaded chart contributes to `enrichment_delta` via
explicit price coordinates — not via a vague confidence float. The VisionAgent's role
here is constrained extraction, not general chart interpretation.

#### Goals

- Trader can upload an annotated chart for any ranked signal within 3 clicks
- System extracts S/R levels as explicit floats, shows them for trader confirmation
- Confirmed levels contribute to `enrichment_delta` in a bounded, auditable way
- Outcome tracking enables empirical validation: do custom chart signals outperform?

#### Non-Goals

- General LLM chart interpretation (separate from this extraction-only flow)
- Mobile camera upload (desktop drag-and-drop only for v1)
- Real-time S/R updates (upload is a point-in-time snapshot)
- Replacing DataAgent's quantitative S/R calculation (additive only)

#### Requirements

**P0 — Must Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R1 | Upload endpoint | `POST /api/analysis/enrich/{ticker}` with `{"enrichment_type": "trader_chart", "chart_image": base64}`. Returns `{enrichment_id, extracted_levels: [{type, price, confidence}], status: "pending_confirmation"}`. |
| R2 | Constrained extraction prompt | VisionAgent receives image with prompt: `"List every horizontal support and resistance line visible in this chart as a price level. Return ONLY a JSON array of {type: 'support'\|'resistance', price: float}. Do not describe the chart. Do not assess direction. Only extract lines."` |
| R3 | Extracted levels as floats | VisionAgent output: `ExtractedLevels = List[{type, price, confidence}]`. No narrative. No overall confidence float. |
| R4 | Proximity validation | Each level validated: `abs(level.price - current_price) / current_price <= 0.15`. Levels outside 15% discarded before showing to trader. |
| R5 | Trader confirmation UI | UI displays extracted levels overlaid on a price chart (lightweight-charts component). Trader deletes false positives. Only confirmed levels stored and scored. |
| R6 | Storage | Confirmed levels in `analysis_tickers.custom_levels` JSON: `[{"type": "support", "price": 185.40, "confirmed_at": "..."}]`. Expire after `CUSTOM_LEVEL_TTL_DAYS` (default: 5 trading days). |
| R7 | enrichment_delta contribution | Each confirmed support level within 1 ATR of entry → +4 pts. Each resistance level near target → +3 pts. Max 2 custom levels count (max +8 pts from support, +6 from resistance). Total max from this path: +14 pts, within ENRICHMENT_MAX_DELTA ceiling. |
| R8 | custom_levels_applied in AssetAnalysis | `AssetAnalysis.custom_levels_applied: int` (0, 1, or 2). Shows trader that their chart influenced the enrichment_delta. |

**P1 — Should Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R9 | Extraction quality warning | > 8 levels extracted → `"⚠️ 11 levels detected — unusually high. Please review and delete false positives."` |
| R10 | Level expiry badge | Tickers with active custom levels show `"Custom S/R: 3d remaining"` in ticker management UI. |
| R11 | Outcome tracking | When signal stop or target is hit, record `custom_levels_applied` in outcome record. After 30 signals: `"Signals with custom chart: HR 41% | Without: HR 33%"`. |

**P2 — Future**

- TradingView chart embed with direct S/R line import (bypassing image extraction)
- Multi-chart upload for different timeframes

#### Acceptance Criteria (Story Level)

```gherkin
Given the trader uploads a PNG of AAPL's chart with 3 visible S/R lines
When POST /api/analysis/enrich/AAPL is called with enrichment_type="trader_chart"
Then VisionAgent runs the constrained extraction prompt
And response contains extracted_levels with type and price for each line
And no overall chart confidence float is returned

Given extracted_levels has a level at price=310.00 and current_price=191.20
When validation runs
Then (310.00 - 191.20) / 191.20 = 62.2% > 15%
And the level is discarded before the trader confirmation step

Given trader confirms one support level at 188.20 with entry_price=191.50 and ATR=3.80
When ScoringAgent patches the enrichment_delta
Then 188.20: distance = 3.30 = 0.87x ATR → within 1 ATR → +4 pts
And enrichment_delta += 4
And custom_levels_applied = 1
And UI shows "82 → 86 (+4 visual)"
```

---

### US-303 — Signal Enrichment: Auto Screenshot Request (Path B2)

**As a** trader who wants a full visual analysis of a specific ranked signal,
**I want** to request an automated screenshot capture of that ticker's chart from a
web source I specify, followed by a full VisionAgent analysis,
**so that** I can get the LLM's narrative argument and visual support validation for
that specific signal without it having contaminated the base quantitative score.

#### Problem Statement

With ScreenshotAgent removed from the batch run, the trader loses the automatic visual
analysis that previously ran for every ticker. For most signals, the quantitative
`score_quant` is sufficient to make a decision. But for signals the trader wants to
investigate deeper — especially high-ranked signals before a significant capital
allocation — the trader should be able to request a full screenshot + VisionAgent
analysis on demand.

Path B2 uses the same ScreenshotAgent infrastructure as US-201, but from a different
trigger: the trader's explicit request on a specific ranked signal, not an automated
batch invocation.

#### Goals

- Trader can get full LLM visual analysis for any Top 20 signal within 30 seconds
- The LLM analysis enriches the score transparently, not silently
- The narrative `argument` field (the LLM's trade thesis explanation) is surfaced in the UI

#### Non-Goals

- Auto-triggering Path B2 for all Top 20 signals (defeats the on-demand principle)
- Replacing the quantitative base score with the LLM output (enrichment_delta only)
- Scheduling periodic screenshot refresh (point-in-time only)

#### Requirements

**P0 — Must Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R1 | Enrichment trigger endpoint | `POST /api/analysis/enrich/{ticker}` with `{"enrichment_type": "auto_screenshot", "source_url": str}`. (Shares endpoint with US-201, different `enrichment_type`.) |
| R2 | Full VisionAgent analysis prompt | VisionAgent receives screenshot with the **standard analysis prompt** (not the constrained extraction prompt from B1): full signal + confidence + argument + support_validated. |
| R3 | enrichment_delta from VisionAgent | `enrichment_delta_b2 = (confidence × ENRICHMENT_MAX_DELTA) + support_validated_bonus`. Capped at ENRICHMENT_MAX_DELTA (15 pts). |
| R4 | Argument surfaced in UI | `argument` field from VisionAgent displayed in signal detail panel as the LLM's trade thesis. Shown as a quote block: `"💬 Visual analysis: [argument text]"`. |
| R5 | Enrichment type recorded | `AssetAnalysis.enrichment_type: Optional[Literal["trader_chart", "auto_screenshot"]]` — so back-test outcome tracking can separate the two paths' performance. |
| R6 | Confidence capping | Raw VisionAgent `confidence` (0–1) contributes `confidence × 15` to enrichment_delta, capped at 15. A confidence of 0.87 → +13.05 pts enrichment_delta. |

**P1 — Should Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R7 | Side-by-side score display | Signal detail panel shows: `score_quant: 82 (quantitative)` and `score_enriched: 95 (+13 visual, auto screenshot)` in two labeled rows. |
| R8 | Path B2 outcome tracking | Separate outcome record for `enrichment_type="auto_screenshot"` after 30 signals: `"Auto screenshot enriched signals: HR 38% | Not enriched: HR 34%"`. |

#### Acceptance Criteria (Story Level)

```gherkin
Given the trader selects NVDA from Top 20 and requests auto screenshot enrichment
With source_url = "https://www.tradingview.com/chart/?symbol=NVDA"
When POST /api/analysis/enrich/NVDA with enrichment_type="auto_screenshot"
Then ScreenshotAgent (US-201) captures chart screenshot
And VisionAgent runs full analysis prompt on the screenshot
And returns {confidence: 0.87, argument: "NVDA shows breakout from BB squeeze...", support_validated: true}
And enrichment_delta = (0.87 × 15) + 2 (support_validated bonus) = 15.05 → clamped to 15
And score_enriched = score_quant + 15
And UI shows "82 → 97 (+15 visual)" with the argument text in detail panel

Given VisionAgent returns confidence=0.30 (low conviction)
When enrichment_delta is computed
Then enrichment_delta = 0.30 × 15 = 4.5
And score_enriched = score_quant + 4.5
And the low enrichment visually signals low additional conviction to the trader

Given Path B2 enrichment completes for 5 signals over 3 weeks
When outcome tracking aggregates results
Then separate hit ratio shown for enriched vs non-enriched signals
And the data is available in the back-test results CSV
```

#### Open Questions

- **[Product]** Should the trader be able to request both B1 and B2 for the same signal? If both run, how are their enrichment_deltas combined? (Suggested: `enrichment_delta = max(delta_b1, delta_b2)` — take the higher of the two, not sum.)
- **[Engineering]** US-201 and US-303 share the same `POST /api/analysis/enrich/{ticker}` endpoint with `enrichment_type` as the discriminator. The routing to ScreenshotAgent vs. direct VisionAgent call happens inside OrchestratorAgent's `enrich_signal()` method.

---

## EPIC 4 — Top Opportunities Panel UX

---

### US-401 — Top 20 Signal Display with Pagination

**As a** trader reviewing analysis results after a 100-ticker run,
**I want** the Top Opportunities panel to show up to 20 ranked signals with pagination
(10 signals per page),
**so that** I can review more opportunities without being overwhelmed, and without missing
high-quality signals that fall outside the current Top 5.

#### Problem Statement

Current panel shows exactly 5 rows (`ANALYSIS_TOP_N=5`). With 100 tickers generating
15–65 qualifying signals per run, showing only 5 misses up to 60 validated opportunities.
All rankings now use `score_quant` exclusively (US-301), so the Top 20 is a clean,
back-testeable ranked list.

#### Goals

- Trader can review all Top 20 signals within 3 clicks
- Page 1 loads in the same time as the current Top 5 panel
- Score band is immediately scannable without reading individual numbers

#### Non-Goals

- Infinite scroll (pagination creates natural review cadence)
- Sorting or filtering within the panel (score_quant already determines order)
- Showing more than 20 signals in this panel

#### Requirements

**P0 — Must Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R1 | Top N configurable to 20 | `ANALYSIS_TOP_N` accepts 5–20. Default changes to 20. ScoringAgent returns top 20 in `top_20` (rename from `top_5`). |
| R2 | Pagination: 10 per page | Page 1: ranks 1–10. Page 2: ranks 11–20. |
| R3 | Pagination controls | `← Prev  Page 1 of 2  Next →` below table. Visible only when result count > 10. |
| R4 | Page resets on new run | Current page resets to 1 when a new run completes. |
| R5 | Signal count summary | Above table: `"Showing 10 of 20 qualified signals (65 analyzed)"`. |
| R6 | Enrichment indicator per row | Each row shows enrichment status: empty (not enriched), `+7 visual` badge (B1 enriched), `+13 visual` badge (B2 enriched). Badge links to detail panel. |

**P1 — Should Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R7 | Keyboard navigation | `→` / `←` navigate pages when panel focused. |
| R8 | Page indicator dots | ● ○ / ○ ● as visual complement to text controls. |

#### Acceptance Criteria (Story Level)

```gherkin
Given a run produces 23 qualifying signals
When the panel renders
Then "Showing 10 of 20 qualified signals (23 analyzed, 3 above threshold not shown)"
And ranks 1–10 visible on page 1
And "Page 1 of 2" shown in controls
And clicking "Next →" shows ranks 11–20

Given the trader enriched AAPL via Path B1 (+4 pts)
When the Top 20 renders
Then AAPL row shows score_quant and a "+4 visual" badge
And AAPL's rank position is unchanged (ranking uses score_quant)

Given a run produces only 7 qualifying signals
When the panel renders
Then all 7 shown on single page
And pagination controls hidden
```

#### Open Questions

- **[Design]** Should page 2 signals be visually dimmed to indicate "second tier"?
- **[Product]** `top_5` referenced in E2E tests. Rename to `top_20` or keep as alias?

---

### US-402 — Collapsible Top Opportunities Section

**As a** trader monitoring live prices and portfolio P&L,
**I want** to collapse and expand the Top Opportunities panel with a single click,
**so that** I can maximize screen space for the live chart and positions table during
active trading hours.

#### Requirements

**P0 — Must Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R1 | Toggle | Panel header has chevron (`▼` / `▶`). Click anywhere in header toggles panel. |
| R2 | Collapsed badge | Header shows `"Top Opportunities  [20]"` when collapsed. Updates on new run without expansion. |
| R3 | Content hidden | Signal table, pagination, summary hidden when collapsed. Header remains. |
| R4 | Preference persisted | `localStorage` key `finally_top_opps_collapsed`. Restored on reload. |
| R5 | Smooth animation | `max-height` CSS transition, 200ms ease-out. |
| R6 | Auto-expand on new run | New run completing auto-expands panel and scrolls into view. Toast: `"Analysis complete — 18 new signals available"`. |

**P1 — Should Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R7 | Regime gate badge | `regime_gate_active: true` → `"⚠️ Regime gate active"` in amber replaces signal count. |
| R8 | Keyboard shortcut | `Shift+O` toggles collapse state. |

#### Acceptance Criteria (Story Level)

```gherkin
Given the panel is expanded
When the trader clicks the header
Then table collapses with 200ms animation
And header shows "Top Opportunities [20]"
And localStorage "finally_top_opps_collapsed" = "true"

Given regime_gate_active = true
When the panel is collapsed
Then header shows "⚠️ Regime gate active" in amber (#C47A00)

Given the panel is collapsed
When a new run completes with 14 qualifying signals
Then panel auto-expands
And toast: "Analysis complete — 14 new signals available"
```

#### Open Questions

- **[Design]** Should auto-expand be suppressible for traders managing an active position?
- **[Engineering]** No toast system exists in FinAlly. Is a toast the right primitive or should the chat panel handle system notifications?

---

### US-403 — Score Band Visual Segmentation

**As a** trader scanning 20 ranked signals,
**I want** signals visually grouped by score band (Elite ≥75, Strong 60–74, Qualifying 50–59),
**so that** I can immediately identify the highest-conviction opportunities by the
`score_quant` bands without reading individual numbers.

#### Requirements

**P0 — Must Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R1 | Score band badge | `ELITE` (≥75, gold `#ECAD0A`), `STRONG` (60–74, blue `#209DD7`), `QUALIFYING` (50–59, grey `#888888`). Applied to `score_quant`. |
| R2 | Visual divider between bands | Subtle rule with band label when band changes within visible 10 rows: `── STRONG ──────────────`. |
| R3 | Score bar | Mini-bar proportional to `score_quant` next to numeric score. Enriched signals show a second delta bar in a different color. |

**P1 — Should Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R4 | Band count in summary | `"Showing 10 of 20 signals  ·  ELITE: 3  ·  STRONG: 11  ·  QUALIFYING: 6"`. |

---

### US-404 — Signal Freshness & Decay Indicator

**As a** trader reviewing Top Opportunities during the trading day,
**I want** each signal to display how long ago it was generated and a visual freshness
indicator,
**so that** I know whether the `score_quant` is still actionable or has aged beyond
its reliable entry window.

#### Requirements

**P0 — Must Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R1 | Age since signal | Each row shows `"2h 14m ago"`, updated every minute. |
| R2 | Freshness color | 0–2h: green dot. 2–6h: amber dot. >6h same day: red dot. Next trading day: grey + "Expired". |
| R3 | Expired rows greyed | Prior-day signals at 40% opacity, ticker strikethrough, `"EXPIRED"` badge. |

**P1 — Should Have**

| # | Requirement | Acceptance Criteria |
|---|-------------|-------------------|
| R4 | score_quant delta | Prior run comparison on `score_quant`: `▲ +6` (green), `▼ -4` (red), `=` (grey) if within ±3 pts. |

---

## Dependency Map (v3)

```
US-104 (Default Universe Seed)
  └─ foundational pre-requisite: must migrate before any analysis run at 100 tickers
  └─ blocks US-101 (diversity warning baseline uses the seed distribution)
  └─ blocks US-202 (sector cap requires sector field — seeded by US-104)
  └─ no code dependencies: pure data migration + seed_tickers.py file

US-101 (Ticker Universe Management)
  └─ depends on US-104 (sector field pre-populated; diversity score uses seed as baseline)
  └─ blocks US-202 (sector cap needs sector metadata on trader-added tickers)

US-102 (DataAgent Parallelism)
  └─ required for any meaningful 100-ticker test
  └─ blocks US-203 (SMA200 computed in DataAgent)
  └─ NOTE: does NOT block US-201 — ScreenshotAgent no longer in batch pipeline

US-103 (yfinance Resilience)
  └─ parallel with US-102 (same DataAgent layer, different failure mode)

US-201 (ScreenshotAgent On-Demand)
  └─ completely decoupled from batch run (v3 architecture)
  └─ required by US-303 (Path B2 uses ScreenshotAgent infrastructure)
  └─ no longer a pipeline bottleneck — single ticker, on-demand only

US-202 (Sector Cap)
  └─ depends on US-101 (sector field)
  └─ depends on US-301 (ranking uses score_quant; cap applied to score_quant ranking)

US-203 (Regime Gate)
  └─ depends on US-102 (SMA200 in DataAgent indicators)

US-204 (Observability)
  └─ independent of all above, ships in parallel
  └─ NOTE: stage labels change in v3 — only "data" and "scoring" stages now,
           no "screenshot" or "vision" stages in batch run

US-301 (Two-Layer Score Architecture)
  └─ foundational — must ship before US-302, US-303, US-401, US-403
  └─ defines score_quant and enrichment_delta fields used by all subsequent stories
  └─ independent of data/pipeline epics (formula change only)

US-302 (Trader Chart Upload — Path B1)
  └─ depends on US-301 (enrichment_delta field and ceiling)
  └─ independent of US-201 (no Playwright used in B1)
  └─ independent of US-202, US-203

US-303 (Auto Screenshot Request — Path B2)
  └─ depends on US-301 (enrichment_delta contract)
  └─ depends on US-201 (reuses ScreenshotAgent on-demand infrastructure)
  └─ independent of US-202, US-203

US-401 (Top 20 Pagination)
  └─ depends on US-301 (ranking uses score_quant; enrichment badges need enrichment_delta)
  └─ depends on US-202 (sector cap affects qualifying count)
  └─ depends on US-203 (regime gate affects signal count)

US-402 (Collapsible Panel)
  └─ independent of US-401 but ships together (same component)

US-403 (Score Bands)
  └─ depends on US-301 (score bands applied to score_quant specifically)
  └─ ships with US-401

US-404 (Freshness Indicator)
  └─ independent, ships with US-401
```

---

## Recommended Sprint Order (v3)

| Sprint | Stories | Rationale |
|--------|---------|-----------|
| **Sprint 0** | US-104 | **Seed migration before anything else.** US-104 is a database migration + a new `seed_tickers.py` file. No code dependencies, no blocking stories. Ships as a pre-Sprint 1 migration to ensure all 100 tickers are available for testing from day one. CI validation (R3) must pass before merge. |
| **Sprint 1** | US-101, US-102, US-103 | Unblock the 100-ticker data layer. US-101 now depends on US-104 (sector field pre-populated; diversity score baseline). US-102 and US-103 are independent. All three can be developed in parallel within the sprint. |
| **Sprint 2** | US-301, US-202, US-203, US-204 | **Score architecture before UX.** US-301 (two-layer score) must land before any UX story references `score_quant` or `enrichment_delta`. Sector cap (US-202) depends on US-101 sector field from Sprint 1. All four can be developed in parallel within the sprint. |
| **Sprint 3** | US-201, US-302 | ScreenshotAgent on-demand (single ticker, simple) and Trader Chart Upload (Path B1) ship together. B1 needs enrichment_delta from US-301 but no Playwright. US-201 is small enough to pair with B1. |
| **Sprint 4** | US-303 | Auto Screenshot Request (Path B2) depends on US-201 (Playwright infrastructure) and US-301 (enrichment_delta contract). Ships after both are stable. |
| **Sprint 5** | US-401, US-402, US-403, US-404 | All UX stories share the same component. Ship together once the scoring formula (US-301) and enrichment paths (US-302, US-303) are stable. UX built on a stable score is built once. |

> **Key changes from v3:**
> - Sprint 0 added: US-104 (Default Universe Seed) ships as a pre-sprint migration
> - Sprint 1 unchanged in stories but US-101 now has a soft dependency on US-104
> - Sprint order for Sprints 2–5 unchanged

---

## Success Metrics (v3)

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| Seed installation success | Legacy 10-ticker seed (70% tech) | 100 diversified tickers installed on migration, all passing CI validation | US-104 R3 CI test pass rate |
| Universe diversity score at install | N/A (10 tickers) | ≥ 70 (green) on Diversity Score immediately after seed | US-101 R9 diversity score on fresh install |
| Sector warning trigger rate | N/A | Concentration warning triggered when sector exceeds 30% on trader additions | `concentration_warnings` non-empty in bulk-add responses |
| Batch run duration (100 tickers) | 68–186 sec (10 tickers) | **< 90 sec** (100 tickers, quant-only) | `AnalysisResult.duration_seconds` |
| Data fetch success rate | ~100% (10 tickers) | ≥ 95% (100 tickers) | `errors` length / total tickers |
| Qualifying signals per run | 2–7 | 15–35 typical / 40–65 strong-trend | `len(top_20)` over 30 days |
| Sector concentration in Top 20 | Up to 5/5 single sector | Max 2 per sector | `sector_cap_exclusions` |
| Regime gate accuracy | N/A | 0 BUY signals during VIX > 25 days | Manual verification |
| score_quant back-test coverage | 0% (formula not testeable) | 100% (no LLM component) | Back-test plans run end-to-end |
| enrichment_delta adoption | N/A | ≥ 30% of Top 20 signals enriched per session | `enrichment_delta != null` count |
| Path B1 HR lift vs non-enriched | N/A | HR with custom chart ≥ HR without + 5 pts (after 30 signals) | US-302 R11 outcome tracking |
| Path B2 HR lift vs non-enriched | N/A | HR with auto screenshot ≥ HR without + 4 pts (after 30 signals) | US-303 R8 outcome tracking |
| Enrichment time (B1 — chart upload) | N/A | < 8 seconds (VisionAgent only, no Playwright) | Enrichment request duration |
| Enrichment time (B2 — screenshot) | N/A | < 30 seconds (Playwright + VisionAgent) | Enrichment request duration |
| Panel collapse toggle usage | N/A | ≥ 50% of sessions | Frontend event `top_opps_collapsed` |
| Time to review Top 20 | N/A | < 90 seconds per session | Session recording |