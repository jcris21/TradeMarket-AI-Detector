## Context

`analysis_tickers` is seeded from `DEFAULT_TICKERS` (a 10-entry list in `backend/app/db/schema.py`) during `init_db()` in `backend/app/db/connection.py`. The seed only runs when `users_profile` has no `"default"` row (i.e., first-ever install). The table has no `sector`, `sub_sector`, or `seed_version` columns today.

The `init_db()` function already runs a lazy `ALTER TABLE` migration loop using a `duplicate column name` guard for `analysis_results`. This pattern is the canonical approach in this codebase for additive column migrations.

`LEGACY_TICKERS` = `{"AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"}` — the exact current seed set.

## Goals / Non-Goals

**Goals:**
- Replace the 10-ticker seed with a 100-ticker, sector-diversified universe on fresh installs
- Upgrade existing installs that still have the exact legacy 10 tickers (auto-truncate + replace)
- Add `sector`, `sub_sector`, `seed_version` columns to `analysis_tickers` via safe additive migration
- Keep `seed_tickers.py` as the single source of truth (no duplicated lists)
- Protect users who have added custom tickers (additive merge only)
- Cover all paths with offline unit + async integration tests

**Non-Goals:**
- Dynamic seed refresh from external data sources
- International equities, crypto, futures, or options
- Changes to the `watchlist` table or its 10-ticker seed
- Frontend UI changes
- Live liquidity validation in standard CI (optional separate script only)

## Decisions

### D1: `seed_tickers.py` as single source of truth (not inline in `schema.py`)

**Chosen:** New file `backend/app/analysis/seed_tickers.py` exports `SEED_TICKERS`, `SEED_VERSION`, `LEGACY_TICKERS`. `schema.py` imports from it.

**Alternative considered:** Inline the 100-entry list directly in `schema.py`.

**Rationale:** `schema.py` already mixes DDL SQL strings and Python constants — adding a 100-entry structured list there makes it unwieldy. Placing it in `analysis/` co-locates it with the analysis domain that consumes it. The `analysis` package already owns `data_agent.py`, `scoring_agent.py`, etc.

### D2: Frozenset comparison for legacy detection (not count-based)

**Chosen:** Compare `existing == LEGACY_TICKERS` (frozenset equality) to identify a legacy install.

**Alternative considered:** `len(existing) == 10` (count-based).

**Rationale:** A user who deleted 2 tickers manually leaves 8 rows. Count-based detection would mis-classify them as "not legacy" and trigger the additive merge, missing the upgrade. Frozenset equality is exact — only installations with the unmodified original 10 get the truncate-and-replace path.

### D3: Upgrade logic runs every `init_db()` (not only on first install)

**Chosen:** The upgrade-seed block executes on every `init_db()` call, after column migration.

**Alternative considered:** Guard with a flag column or a separate `seed_migrations` table.

**Rationale:** `init_db()` is already idempotent (all DDL uses `IF NOT EXISTS`, `INSERT OR IGNORE`, `duplicate column` guards). Adding the upgrade check here is zero-cost on subsequent runs (frozenset comparison on a tiny table) and avoids introducing a new migrations tracking table for a one-time upgrade.

### D4: Three separate migration paths (replace / fresh / additive)

**Chosen:**
1. `existing == LEGACY_TICKERS` → DELETE all + INSERT 100
2. `not existing` → INSERT OR IGNORE all 100 (fresh install)
3. else → INSERT only missing tickers (additive merge, never DELETE)

**Rationale:** Covers all real-world states. Path 3 ensures custom tickers (e.g., `CUSTOM_XYZ` added by the user) are never silently deleted, which would break the user's analysis universe.

### D5: CI liquidity gate is a separate optional script

**Chosen:** R3 (`len(df) >= 50`, `avg_volume >= 500_000`) lives in a script gated by `RUN_LIQUIDITY_TESTS=true`, not in `pytest`.

**Rationale:** Live market data calls are non-deterministic, network-dependent, and slow. They cannot be part of standard CI. The offline unit tests in `test_seed_tickers.py` (count, no duplicates, no unknown sectors) are the merge gate.

## Risks / Trade-offs

- **[Risk] SQLite concurrent write during upgrade** — `init_db()` runs at startup; if the container restarts mid-migration the partial state could be inconsistent.
  → Mitigation: Wrap the DELETE + INSERT 100 block in an explicit `BEGIN` / `COMMIT` transaction (or rely on aiosqlite's auto-commit after `executemany`). The existing pattern uses `await db.commit()` after bulk inserts — follow the same convention.

- **[Risk] Import cycle** — `schema.py` imports from `analysis/seed_tickers.py`; `connection.py` imports from `schema.py`.
  → Mitigation: `analysis/seed_tickers.py` must have zero imports from `db/` or `app/` to avoid a cycle. It is pure data (a list of dicts and two constants).

- **[Risk] Future seed version bump** — upgrading to `v2` later requires another migration path.
  → Trade-off accepted: `SEED_VERSION` column plus the existing version constant makes this detectable. A `v2` migration can check `seed_version != "v2"` as the trigger. Out of scope for this story.

- **[Risk] `_MOCK_ANALYSIS_SEED` in `connection.py` references only legacy tickers** — the mock seed data for dev/demo does not need to change (it covers specific tickers for UI demo purposes, not the full universe). No action required.

## Migration Plan

1. Container starts → `init_db()` runs
2. `ALTER TABLE analysis_tickers ADD COLUMN sector/sub_sector/seed_version` (idempotent via `duplicate column` guard)
3. Frozenset comparison on `analysis_tickers` rows for `user_id = "default"`
4. Execute the appropriate path (replace / fresh / additive)
5. Application is ready — no downtime, no manual steps

**Rollback:** Columns are nullable and additive — removing them is the only schema rollback needed. The extra 90 rows in `analysis_tickers` are benign if rolled back (they won't break any existing query). A rollback simply reverts the code; the extra rows and columns are harmless.

## Open Questions

- None blocking implementation.
