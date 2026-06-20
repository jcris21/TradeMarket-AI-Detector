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
