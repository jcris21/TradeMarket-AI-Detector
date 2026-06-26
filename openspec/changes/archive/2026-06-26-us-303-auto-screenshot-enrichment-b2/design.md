## Context

The existing `POST /api/analysis/{ticker}/enrich` route already handles automated screenshot enrichment under the `enrichment_type="screenshot"` discriminator (`routes/analysis.py:284`). That implementation uses `ScreenshotAgent` (Playwright headless Chromium) and `VisionAgent` with the full `_SYSTEM_PROMPT`, but applies the legacy delta formula `(confidence - 0.5) * 2 * 15`.

US-303 (Path B2) requires:
1. A new canonical discriminator `"auto_screenshot"` (replacing `"screenshot"` for new callers)
2. The B2 formula: `min(confidence × 15 + support_validated_bonus, 15)`
3. `enrichment_type` tracked on `AssetAnalysis` and persisted to `analysis_results`
4. B1 + B2 `max()` conflict resolution
5. Outcome tracking segmentation by `enrichment_type`

The `enrichment-delta` spec currently defines the formula as `(confidence - 0.5) * 30` — this applies only to the legacy (no `enrichment_type`) path and is NOT changed by this story.

## Goals / Non-Goals

**Goals:**
- Add `"auto_screenshot"` as a first-class discriminator with the B2 delta formula
- Persist `enrichment_type` through the full data path (model → DB → API response)
- Implement `max(delta_b1, delta_b2)` conflict resolution atomically at task completion time
- Add `b2_enriched` / `non_enriched` segmentation to the performance summary (behind 30-signal gate)
- Prepend `"💬 Visual analysis: "` to the argument before persisting
- Idempotency: return existing `enrichment_id` when a same-type job is already in flight

**Non-Goals:**
- Changing the VisionAgent prompt — B2 already uses `_SYSTEM_PROMPT` (full analysis); no prompt change needed
- Changing the `"screenshot"` formula retroactively for existing DB rows
- Introducing parallel Playwright sessions or job queuing
- Real-time score push via SSE on enrichment completion

## Decisions

### D1: Keep `"screenshot"` as a backward-compat alias, not a renamed discriminator

**Decision**: The route handler accepts both `"screenshot"` and `"auto_screenshot"` and routes both to `_run_screenshot_enrichment`. The `enrichments` table stores `"auto_screenshot"` for both, normalizing at write time.

**Alternatives considered**:
- *Hard rename*: Break existing callers (frontend and any scripts using `"screenshot"`). Rejected — too risky mid-sprint.
- *Parallel handlers*: Two separate code paths for `"screenshot"` and `"auto_screenshot"`. Rejected — duplicates logic without benefit.

### D2: Apply B2 formula only on the `auto_screenshot` / `screenshot` path; leave legacy formula unchanged

**Decision**: `_run_screenshot_enrichment` uses `confidence × 15 + support_validated_bonus`. The legacy path (no `enrichment_type`) retains `(confidence - 0.5) * 30` from the `enrichment-delta` spec.

**Rationale**: The two paths serve different UX flows. Changing the legacy formula would alter existing test expectations and outcome tracking baselines.

### D3: B1 + B2 `max()` resolution at task completion, not at query time

**Decision**: At the end of `_run_screenshot_enrichment`, read the current `analysis_results.enrichment_delta` for the ticker and apply `max(b2_delta, existing_delta)` before calling `update_enrichment_delta`.

**Alternatives considered**:
- *Query-time max*: Compute `max` in the DB query on every GET. Rejected — adds complexity to every read path.
- *Separate columns*: Store `enrichment_delta_b1` and `enrichment_delta_b2` separately. Rejected — downstream consumers (score display, outcome tracking) would need updating everywhere.

### D4: `enrichment_type` column added via migration guard, not in initial DDL only

**Decision**: Add `enrichment_type TEXT` to the `analysis_results` DDL and add an `ALTER TABLE ... ADD COLUMN` migration guard in `connection.py` for existing databases that lack the column.

**Rationale**: Existing deployed containers have the table without the column. `CREATE TABLE IF NOT EXISTS` does not add missing columns to existing tables.

### D5: `SUPPORT_VALIDATED_BONUS` as env-var with default `2.0`

**Decision**: `SUPPORT_VALIDATED_BONUS = float(os.environ.get("SUPPORT_VALIDATED_BONUS", "2.0"))` read at task execution time (not module load) so it can be overridden without restart in tests.

**Rationale**: The value is a tunable hyperparameter. Hardcoding it would require a code change to adjust after observing B2 outcomes.

### D6: Idempotency check before creating new enrichment job

**Decision**: Before `create_enrichment_job`, query `enrichments` for any row with `ticker=<ticker>` AND `enrichment_type IN ("auto_screenshot", "screenshot")` AND `status IN ("pending", "processing")`. If found, return the existing `enrichment_id` with `status="pending"` (202).

**Rationale**: Prevents duplicate Playwright browser sessions for the same ticker, which would waste resources and produce non-deterministic results.

### D7: Outcome segmentation via `enrichment_type` filter in `get_performance_summary`

**Decision**: Extend `get_performance_summary()` to run a second query filtered by `enrichment_type = 'auto_screenshot'` and a third for `enrichment_type IS NULL OR enrichment_type != 'auto_screenshot'`. Add `b2_enriched` and `non_enriched` optional fields to `PerformanceResponse`. Both blocks require ≥ 30 resolved signals before being non-null.

**Alternatives considered**:
- *New endpoint `GET /api/analysis/performance/b2`*: Cleaner separation but requires frontend changes and increases API surface. Rejected for MVP.

## Risks / Trade-offs

- **B2 formula produces higher deltas than legacy formula**: `confidence=0.8` → B2 gives `12.0 pts` vs legacy `9.0 pts`. Traders may notice enriched scores jump more than before. Mitigation: the 15-pt cap limits the maximum impact; document the change in the sprint notes.
- **Migration guard failure on locked DB**: `ALTER TABLE` under SQLite with concurrent connections could fail. Mitigation: migration runs at app startup before any request is served; single-container architecture means no parallel migrations.
- **`max()` resolution reads stale data**: If B1 completes between the B2 task's read and write, the stale read could discard a higher B1 delta. Mitigation: SQLite's default serialized write mode makes this window very small; no distributed lock needed for MVP.
- **`"screenshot"` alias creates two enrichment records with different types for same ticker**: If a caller uses `"screenshot"` then `"auto_screenshot"`, idempotency only catches in-flight jobs of the same normalized type. Mitigation: idempotency query checks both discriminator values.

## Migration Plan

1. Deploy new container — `connection.py` migration guard runs `ALTER TABLE analysis_results ADD COLUMN enrichment_type TEXT` if the column doesn't exist (silently no-ops on fresh DBs).
2. Existing `enrichments` rows with `enrichment_type="screenshot"` continue to work; query logic treats `"screenshot"` and `"auto_screenshot"` equivalently for outcome segmentation.
3. No data backfill needed — `analysis_results.enrichment_type` for old rows is `NULL`; they appear in the `non_enriched` segment of the performance summary.
4. Rollback: revert container image. Old code ignores the new column silently (extra columns in SQLite are harmless).

## Open Questions

1. **`SUPPORT_VALIDATED_BONUS` default**: Proposing `2.0` pts. Confirm before sprint start so unit tests can assert the exact boundary value.
2. **Outcome tracking readiness**: Does `OutcomeDetector` currently write `enrichment_type` to any outcome row, or does the performance query need to join `analysis_results` on `ticker + run_id` to get the type? Determines whether the segmentation query is a simple filter or a JOIN.
3. **Frontend label format**: `"+13 visual, auto screenshot"` vs `"+13 pts (B2)"` — confirm before frontend implementation.
