## Why

The current `analysis_tickers` seed ships 10 tickers (7 tech = 70%), creating a sector-biased Phase 0 calibration universe from day one. This violates the sector cap constraint before the trader adds anything and delays Kaabar's 30-signal minimum to 5+ days at the typical 2-4 signals/run pace. Expanding to a 100-ticker, proportionally-diversified universe resolves the bias at the database layer with zero frontend impact.

## What Changes

- New file `backend/app/analysis/seed_tickers.py` becomes the single source of truth for the 100-ticker universe (with `sector`, `sub_sector`, `SEED_VERSION`, and `LEGACY_TICKERS` exports)
- `analysis_tickers` table gains three new columns: `sector TEXT`, `sub_sector TEXT`, `seed_version TEXT`
- `backend/app/db/schema.py` DDL updated; `DEFAULT_TICKERS` list replaced by import from `seed_tickers.py`
- `backend/app/db/connection.py` `init_db()` gains:
  - Lazy `ALTER TABLE` migration for the three new columns (using the existing duplicate-column guard pattern)
  - Upgrade-seed logic: exact frozenset match against legacy 10 → truncate + replace; custom tickers present → additive merge only; empty → fresh-install all 100
- Two new test files: `backend/tests/test_seed_tickers.py` (offline unit) and `backend/tests/test_seed_migration.py` (async integration)
- CI liquidity gate (R3: `len(df) >= 50`, `avg_volume >= 500_000`) placed in a separate optional script gated by `RUN_LIQUIDITY_TESTS=true` — never in standard pytest

## Capabilities

### New Capabilities

- `analysis-universe-seed`: 100-ticker diversified seed for `analysis_tickers`, with sector/sub_sector metadata and `seed_version` stamping, plus upgrade migration logic for existing installs

### Modified Capabilities

*(none — no existing spec-level behavior changes; watchlist seed and all frontend behavior are unchanged)*

## Impact

- **`backend/app/analysis/seed_tickers.py`** — new file (source of truth)
- **`backend/app/db/schema.py`** — DDL + constant replacement
- **`backend/app/db/connection.py`** — migration loop + upgrade-seed logic in `init_db()`
- **`backend/tests/test_seed_tickers.py`** — new offline unit tests
- **`backend/tests/test_seed_migration.py`** — new async integration tests
- **No API endpoint changes**, no frontend changes, no `watchlist` table changes
- SQLite schema is additive (new nullable columns); existing databases upgrade in-place
