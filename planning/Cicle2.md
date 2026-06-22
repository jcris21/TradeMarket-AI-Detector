  Overlap & Conflict Map for /worktree

  Files touched by multiple changes

  File: backend/app/analysis/models.py
  US-202: Add rank_exclusion_reason (runtime-only), sector_cap_exclusions to AnalysisResult
  US-203: Add sma_200 to TechnicalIndicators, rank_exclusion_reason (persisted), regime_gate_active/vix_value to
    AnalysisResult
  US-204: —
  Conflict risk: HIGH — US-202 and US-203 both add rank_exclusion_reason to AssetAnalysis with different persistence
    semantics. US-203 escalates it to persisted; whichever merges second must reconcile
  ────────────────────────────────────────
  File: backend/app/analysis/scoring_agent.py
  US-202: Core changes — _apply_sector_cap(), 3-tuple return
  US-203: —
  US-204: —
  Conflict risk: Low (single owner)
  ────────────────────────────────────────
  File: backend/app/analysis/orchestrator.py
  US-202: Unpack 3-tuple from scoring, add sector_cap_exclusions to AnalysisResult
  US-203: Add VIX fetch, SMA-200 gate, VIX gate, populate regime_gate_active/vix_value
  US-204: —
  Conflict risk: HIGH — Both stories modify score_and_rank_with_errors() call site and AnalysisResult constructor in
    orchestrator.py. Line-level conflict likely
  ────────────────────────────────────────
  File: backend/app/routes/analysis.py
  US-202: Add sector_cap_exclusions to response dict
  US-203: Add regime_gate_active, vix_value to response dict
  US-204: BREAKING — change POST /api/analysis/run to 202 async
  Conflict risk: HIGH — All three touch this file. US-204 is a structural rewrite of the POST handler; US-202 and US-203
  add
     fields to the response. Merge order matters
  ────────────────────────────────────────
  File: backend/db/schema.py
  US-202: No change
  US-203: Add rank_exclusion_reason TEXT column + migration guard
  US-204: —
  Conflict risk: Low (single owner)
  ────────────────────────────────────────
  File: openspec/specs/score-quant/spec.md
  US-202: Delta: rank_exclusion_reason runtime-only, 3-tuple return
  US-203: Delta: rank_exclusion_reason persisted, DB column
  US-204: Delta: POST /api/analysis/run BREAKING change
  Conflict risk: MEDIUM — All three write delta specs for score-quant. At archive time openspec merges these deltas; the
    rank_exclusion_reason persistence conflict (US-202 says runtime, US-203 says persisted) must be resolved by archiving
    US-203 after US-202 so the later delta wins
  ────────────────────────────────────────
  File: backend/tests/analysis/test_scoring_agent.py
  US-202: 10 new tests + verify no regressions
  US-203: —
  US-204: —
  Conflict risk: Low
  ────────────────────────────────────────
  File: backend/tests/analysis/test_orchestrator.py
  US-202: Verify 3-tuple unpack
  US-203: 8 new tests for regime gate + VIX
  US-204: —
  Conflict risk: MEDIUM — Both stories add/modify orchestrator tests; merge conflict possible in test file
  ────────────────────────────────────────
  File: backend/tests/analysis/test_data_agent.py
  US-202: —
  US-203: 2 new tests + period mock updates
  US-204: —
  Conflict risk: Low
  ────────────────────────────────────────
  File: backend/app/analysis/data_agent.py
  US-202: —
  US-203: SMA-200 computation, period="1y" change
  US-204: —
  Conflict risk: Low (US-102 coordinate risk)
  ────────────────────────────────────────
  File: backend/app/analysis/runner.py
  US-202: —
  US-203: —
  US-204: Convert to async background task
  Conflict risk: Low (single owner)
  ────────────────────────────────────────
  File: backend/app/routers/analysis.py
  US-202: —
  US-203: —
  US-204: New endpoints, 202 response
  Conflict risk: Low (but see above)
  ────────────────────────────────────────
  File: frontend/src/components/AnalysisPanel.tsx
  US-202: —
  US-203: Regime gate banner
  US-204: Polling UI, progress bar, stage badge
  Conflict risk: MEDIUM — Both add UI elements to the same component

  Recommended worktree isolation strategy

  ┌───────────┬───────────────────────────────────┬─────────────────────────────────────────────────────────────────────┐
  │ Worktree  │              Change               │                         Safe to run alone?                          │
  ├───────────┼───────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
  │ wt/us-202 │ us-202-sector-cap-enforcement     │ Yes — only models.py, scoring_agent.py, orchestrator.py (cap        │
  │           │                                   │ section), routes/analysis.py (one field)                            │
  ├───────────┼───────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
  │           │                                   │ Yes — but coordinate merge order with US-202 on models.py and       │
  │ wt/us-203 │ us-203-regime-gate-sma200-vix     │ orchestrator.py; US-203 must resolve rank_exclusion_reason          │
  │           │                                   │ persistence conflict with US-202                                    │
  ├───────────┼───────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
  │           │                                   │ Yes — independent backend architecture, but merge last due to       │
  │ wt/us-204 │ us-204-analysis-run-observability │ routes/analysis.py structural rewrite; US-202 and US-203 response   │
  │           │                                   │ field additions must be re-applied into US-204's new handler        │
  └───────────┴───────────────────────────────────┴─────────────────────────────────────────────────────────────────────┘

  Critical merge order

  US-202 → US-203 → US-204

  - US-202 first: establishes rank_exclusion_reason on AssetAnalysis (runtime), score_and_rank_with_errors 3-tuple
  - US-203 second: escalates rank_exclusion_reason to persisted + DB column; picks up US-202's 3-tuple return
  - US-204 last: rewrites the run endpoint; picks up all response fields from US-202 and US-203 before finalizing the 202
  handler

────────────────────────────────────────────────────────────────────────────────
  Overlap & Conflict Map — Cycle 3: US-201 × US-302
  (us-201-screenshot-agent / us-302-trader-chart-upload)
────────────────────────────────────────────────────────────────────────────────

  Dependency declaration (explicit in both proposals)
  ─────────────────────────────────────────────────
  US-302 is a HARD downstream consumer of US-201. Three shared foundations:
    1. `enrichments` table — created by US-201, consumed by US-302 to store
       trader_chart jobs with status="pending_confirmation"
    2. `EnrichRequest` union type — created by US-201 (discriminated on
       enrichment_type), extended by US-302 to add TraderChartEnrichRequest
    3. Enrich endpoint dispatch — US-201 restructures POST /api/analysis/enrich/
       {ticker} from sync to async dispatch; US-302 adds its branch into that
       same dispatch structure

  If US-302 is started in a parallel worktree without US-201 merged first, all
  three foundations are missing and US-302 cannot compile cleanly.

  Files touched by multiple changes
  ──────────────────────────────────

  File: backend/app/analysis/models.py
  US-201: adds EnrichmentType literal, ScreenshotEnrichRequest, EnrichmentJobResponse,
          EnrichRequest discriminated union (enrichment_type dispatcher)
  US-302: adds ExtractedLevel, TraderChartEnrichRequest, LevelConfirmationRequest,
          ConfirmedLevel, TraderChartEnrichResponse; extends EnrichRequest union with
          TraderChartEnrichRequest
  Conflict risk: HIGH — US-302 must extend the EnrichRequest union created by US-201.
    In parallel worktrees the union definition diverges: US-201's worktree has
    Union[ScreenshotEnrichRequest], US-302's worktree extends it to
    Union[ScreenshotEnrichRequest, TraderChartEnrichRequest]. Merge produces a
    duplicate/conflicting union definition. US-201 must merge first.
  ────────────────────────────────────────
  File: backend/app/routes/analysis.py
  US-201: Major structural rewrite — adds enrichment_type dispatch block, screenshot
          branch (202 async), URL validation helper, BackgroundTasks wiring;
          also adds _run_screenshot_enrichment() background task function
  US-302: Adds trader_chart branch inside the same dispatch block; adds new
          POST /api/analysis/enrich/{ticker}/confirm endpoint
  Conflict risk: HIGH — both stories refactor the same route file's enrich handler.
    US-302's trader_chart branch is syntactically inserted inside the dispatch block
    US-201 creates. In parallel worktrees this file diverges structurally; merging
    requires manual reconciliation of the dispatch block and import list.
    US-201 must merge first; US-302 applies its branch to the already-restructured
    handler.
  ────────────────────────────────────────
  File: backend/app/db/schema.py
  US-201: CREATE TABLE enrichments (...); ALTER TABLE analysis_tickers ADD COLUMN
          preferred_chart_url TEXT; ALTER TABLE analysis_results ADD COLUMN
          enrichment_status TEXT DEFAULT 'none'
  US-302: ALTER TABLE analysis_tickers ADD COLUMN custom_levels TEXT;
          ALTER TABLE analysis_tickers ADD COLUMN custom_levels_expires_at TEXT;
          ALTER TABLE analysis_results ADD COLUMN custom_levels_applied INTEGER DEFAULT 0
  Conflict risk: MEDIUM — different columns, different tables sections, but startup
    migration blocks are typically grouped; merge conflict possible if both add ALTER
    statements in adjacent lines of the same migration function. The enrichments DDL
    (US-201) and the analysis_tickers/analysis_results ALTERs (US-302) are additive;
    ordering within migration is not significant as long as enrichments table creation
    lands before US-302's job writes.
  ────────────────────────────────────────
  File: backend/app/analysis/vision_agent.py
  US-201: adds screenshot_bytes: bytes | None = None parameter to VisionAgent.analyze();
          implements priority logic (screenshot_bytes > disk_path > text-only)
  US-302: adds LEVEL_EXTRACTION_PROMPT constant; adds async extract_levels(image_bytes:
          bytes) -> List[ExtractedLevel] method; adds 8-second timeout guard
  Conflict risk: LOW — US-201 modifies the existing analyze() signature; US-302 adds a
    brand-new method. No line-level conflict as long as both are applied cleanly to the
    same base. If in parallel worktrees, the analyze() signature in US-201's worktree
    diverges from base; US-302's worktree adds extract_levels() to base without the
    screenshot_bytes param. Merge is straightforward (different methods/lines) but
    must be reviewed manually to confirm the priority logic from US-201 is preserved.
  ────────────────────────────────────────
  File: backend/app/db/repository.py
  US-201: adds create_enrichment_job(), get_enrichment_job(), update_enrichment_job(),
          set_ticker_preferred_url(), set_analysis_enrichment_status() (5 functions)
  US-302: adds store_custom_levels(), load_active_custom_levels(), expire_stale_levels()
          (3 functions); also calls create_enrichment_job() (US-201's function) in its
          route handler
  Conflict risk: LOW — all additive, entirely different function names, no overlap in
    implementation. US-302 has a runtime call dependency on create_enrichment_job()
    existing at merge time.
  ────────────────────────────────────────
  File: backend/app/analysis/scoring_agent.py
  US-201: no changes
  US-302: adds _apply_custom_levels(entry_price, target_price, atr_14,
          confirmed_levels) -> tuple[float, int]
  Conflict risk: Low (single owner)
  ────────────────────────────────────────
  File: backend/app/main.py
  US-201: no startup wiring required
  US-302: wires expire_stale_levels() into application startup
  Conflict risk: Low (single owner for this change)
  ────────────────────────────────────────
  File: pyproject.toml / Dockerfile
  US-201: adds playwright dependency; adds playwright install chromium --with-deps
          layer in Dockerfile
  US-302: no new dependencies
  Conflict risk: Low (single owner)
  ────────────────────────────────────────
  Semantic conflict: analysis_results.enrichment_delta column
  US-201: background task writes enrichment_delta after VisionAgent screenshot analysis
          (confidence-mapped float)
  US-302: confirm endpoint writes enrichment_delta after discrete scoring rules
          (+4/+3 integer points)
  Conflict risk: MEDIUM (semantic, not merge) — both types write to the same column;
    last-write-wins at DB level. The design accepts this (single-user, single active
    enrichment type assumed). However, if a trader runs a screenshot enrichment then
    immediately confirms a trader_chart, the second write overwrites the first without
    warning. Needs explicit documentation in whichever story merges second.

  Recommended worktree isolation strategy

  ┌────────────┬────────────────────────────────────┬────────────────────────────────────────────────────────────────────┐
  │  Worktree  │              Change                │                       Safe to run alone?                           │
  ├────────────┼────────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
  │ wt/us-201  │ us-201-screenshot-agent            │ Yes — self-contained; introduces all shared foundations            │
  │            │                                    │ (enrichments table, EnrichRequest union, dispatch structure,        │
  │            │                                    │ Playwright dep). No upstream dependencies.                          │
  ├────────────┼────────────────────────────────────┼────────────────────────────────────────────────────────────────────┤
  │ wt/us-302  │ us-302-trader-chart-upload         │ NO — cannot safely run in isolation. Hard dependency on            │
  │            │                                    │ enrichments table, EnrichRequest union, and enrich endpoint         │
  │            │                                    │ dispatch from US-201. Must be built on top of merged US-201         │
  │            │                                    │ branch, not on main directly.                                       │
  └────────────┴────────────────────────────────────┴────────────────────────────────────────────────────────────────────┘

  Critical merge order

  US-201 → US-302  (strict sequential — not parallelizable)

  - US-201 first: creates enrichments table; builds EnrichRequest discriminated union;
    restructures enrich endpoint into dispatch; adds ScreenshotAgent + Playwright;
    adds VisionAgent.analyze() screenshot_bytes parameter
  - US-302 second (branch off merged US-201): adds TraderChartEnrichRequest to the
    existing union; adds trader_chart branch to existing dispatch; adds /confirm
    endpoint; adds VisionAgent.extract_levels(); adds ScoringAgent._apply_custom_levels();
    adds custom_levels columns; wires TTL expiry into startup

  There is no safe parallel execution path for this pair. The coupling is too deep:
  three shared extension points (union type, dispatch block, enrichments table) all
  require US-201's artifacts to exist before US-302 can compile or test cleanly.
