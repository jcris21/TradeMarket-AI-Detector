## Context

`OutcomeDetector` (TECH-004/NEX-19) writes back TARGET_HIT/STOP_HIT/EXPIRED outcomes to `analysis_results` atomically. The engine is complete and tested, but it has no trigger, no consumer, and two correctness gaps: the hit-ratio formula and the missing `support_break_level` column. This design connects the engine to the rest of the system.

Current state at implementation start:
- `backend/app/analysis/outcome_detector.py` — fully implemented, passes all tests
- `analysis_results` has `outcome`, `actual_gain_pct`, `actual_loss_pct`, `hold_days` columns
- No scheduler, no API route, no frontend representation

## Goals / Non-Goals

**Goals:**
- Drive nightly outcome detection without manual invocation
- Expose aggregated performance metrics to the frontend via a single REST endpoint
- Fix the hit-ratio denominator so EXPIRED signals are truly excluded
- Add `support_break_level` to complete the STOP_HIT data model
- Show "Orphaned" status for signals unresolved after 35 days

**Non-Goals:**
- Real-time/intraday outcome detection (nightly cadence is sufficient for MVP)
- Multi-user isolation (single default user for MVP)
- Historical performance charts beyond what the existing `portfolio_snapshots` endpoint covers
- Changing the outcome detection logic itself (already implemented and tested)

## Decisions

### Decision: APScheduler over FastAPI BackgroundTasks for the nightly job

**Choice**: `apscheduler` with `AsyncIOScheduler` wired into FastAPI `lifespan`.

**Rationale**: `BackgroundTasks` in FastAPI are request-scoped — they can't trigger independently at 02:00 UTC. APScheduler integrates cleanly with asyncio and is the standard pattern for periodic tasks in single-container Python apps. No external scheduler (Celery, cron daemon) needed.

**Alternative considered**: Plain `asyncio.create_task` with an infinite `asyncio.sleep` loop. Rejected because it lacks cron semantics, has no missed-run handling, and is harder to test.

**Alternative considered**: System cron + CLI entry point. Rejected because it requires container-level cron setup that complicates the Dockerfile and ties scheduling to OS config.

### Decision: `_compute_summary` is called on-demand per API request (no caching)

**Choice**: `GET /api/analysis/performance` runs the summary query on every call.

**Rationale**: At MVP scale (hundreds of rows), the query is fast (<10ms). Caching adds complexity and stale-reads risk. Add an index on `outcome` if row count grows.

**Alternative considered**: Cache `PerformanceSummary` in memory and invalidate after each `OutcomeDetector.run()`. Rejected as premature optimization.

### Decision: `support_break_level` populated from signal metadata only, no live S/R computation

**Choice**: Use `stop_loss` price as the reference; label the break level based on which stored field it aligns with (`stop_loss` field name becomes `'S1'` as a fixed label for MVP).

**Rationale**: Computing live S/R levels (SMA20, Bollinger) requires additional yfinance calls per signal and adds complexity out of scope for this story. For MVP, `support_break_level = 'S1'` when STOP_HIT, `None` otherwise, satisfies the DoD.

**Future path**: Replace with real S/R computation in a follow-up story when performance analytics are prioritized.

### Decision: Orphaned detection is query-based, not a stored flag

**Choice**: `orphaned_count` is computed via SQL on each `GET /api/analysis/performance` call; the `OpportunitiesPanel` uses the `analyzed_at` timestamp from existing data to determine the badge, not a dedicated column.

**Rationale**: Avoids a new column and migration. The orphaned condition is purely derived (`outcome IS NULL AND days_since > 35`). If the detector eventually resolves the signal, the badge disappears automatically.

## Risks / Trade-offs

**[Risk] APScheduler job fires during a yfinance outage** → The per-ticker error handling already skips failed fetches with WARNING and continues. No data corruption. The scheduler logs the run summary; ops can detect missing outcomes via the `orphaned_count` rising.

**[Risk] APScheduler persistence** — By default, APScheduler does not persist job state across restarts. If the container restarts at 01:59 and comes back at 02:01, the job fires immediately on next start (next day at 02:00). For MVP, this is acceptable. If missed-run detection is needed, add a SQLite job store.

**[Risk] `support_break_level = 'S1'` is a placeholder** → This is intentional and documented. The column exists in schema so future analysis queries don't break when real values arrive.

**[Trade-off] No authentication on `/api/analysis/performance`** → Consistent with the rest of the single-user MVP API. No change needed.

## Migration Plan

1. `uv add apscheduler` — new dependency, no breaking change
2. Run migration `003_outcome_support_break_level.sql` — additive `ALTER TABLE`, existing rows get `NULL`, no data loss
3. Deploy: scheduler starts with the container, fires first at 02:00 UTC
4. **Rollback**: remove the scheduler from `lifespan` and drop the `support_break_level` column (SQLite: recreate table without column; acceptable risk at MVP scale)

## Open Questions

- Should `OUTCOME_DETECTOR_CRON_HOUR` default to `2` (02:00 UTC) or be configurable per-deployment in `.env.example`? → Assumed `2` as default; add to `.env.example`.
- Should the Orphaned badge appear in `OpportunitiesPanel` only, or also in the positions table? → Scoped to `OpportunitiesPanel` for this story; positions table is a follow-up.
