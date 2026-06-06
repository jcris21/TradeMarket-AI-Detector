## Proposal: Batch SQL for score_delta in ScoringAgent

**Source**: NEX-18 / TECH-003 — Finding #9 (Critical System Evaluation)
**Linear**: https://linear.app/nexusaipro/issue/NEX-18/tech-003-batch-sql-para-score_delta-en-scoringagent

### Problem

The `score_delta` SQL lookup was performed inside the per-ticker loop in Stage 4 of the analysis pipeline. With 30 tickers this meant 30 sequential SQLite queries, growing O(N) with the ticker universe.

### Solution

Replace N inline queries with a single batch query executed once before the scoring loop, storing results in a `prior_scores` dict. The dict is passed into `score_and_rank()` as a parameter, keeping the function pure and testable without a database.

### Outcome

- Batch latency reduced from O(N × RTT_sqlite) to O(1 query)
- `score_delta` field added to `AssetAnalysis`, DB schema, and API responses
- All existing tests continue to pass; 3 new tests added
