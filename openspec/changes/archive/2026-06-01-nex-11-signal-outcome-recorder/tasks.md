# Tasks — nex-11-signal-outcome-recorder

## Backend

- [x] Fix hit-ratio denominator in `OutcomeDetector._compute_summary`: divide by `target_hits + stop_hits` instead of `total`
- [x] Add `orphaned_count` field to `PerformanceSummary` dataclass
- [x] Add `_compute_summary` orphaned count query (rows where `outcome IS NULL` and `analyzed_at` > 35 days ago)
- [x] Add `support_break_level TEXT` column to `analysis_results` CREATE TABLE in `backend/app/db/schema.py`
- [x] Add index `idx_analysis_outcome ON analysis_results(outcome)` to schema SQL
- [x] Create migration `backend/db/migrations/003_outcome_support_break_level.sql` with `ALTER TABLE analysis_results ADD COLUMN support_break_level TEXT`
- [x] Update `update_outcome_atomic` in `backend/app/db/repository.py` to accept optional `support_break_level` parameter and include it in the UPDATE
- [x] Update `OutcomeDetector.run()` to pass `support_break_level='S1'` when outcome is STOP_HIT
- [x] Add `get_performance_summary` function to `backend/app/db/repository.py`
- [x] Add `GET /api/analysis/performance` endpoint to `backend/app/routes/analysis.py` returning performance summary
- [x] Install `apscheduler` dependency via `uv add apscheduler`
- [x] Wire APScheduler nightly job into FastAPI lifespan in `backend/app/main.py` (cron at `OUTCOME_DETECTOR_CRON_HOUR`, default 2)
- [x] Update `.env.example` with `OUTCOME_DETECTOR_CRON_HOUR=2`

## Frontend

- [x] Add `outcome` field to `AssetAnalysis` interface in `frontend/lib/types.ts`
- [x] Add `OrphanedBadge` component and render it in `OpportunitiesPanel` for signals where `outcome` is null and `analyzed_at` > 35 days ago

## Docs

- [x] Update `docs/api-spec.yml` with `GET /api/analysis/performance` endpoint
