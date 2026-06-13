
## 1. Seed Ticker Source of Truth

- [x] 1.1 Create `backend/app/analysis/seed_tickers.py` exporting `SEED_TICKERS` (100 dicts with ticker/sector/sub_sector), `SEED_VERSION = "v1"`, and `LEGACY_TICKERS` frozenset — zero imports from `db/` or `app/`

## 2. Schema Update

- [x] 2.1 Update `analysis_tickers` DDL in `backend/app/db/schema.py` to include `sector TEXT`, `sub_sector TEXT`, `seed_version TEXT` columns
- [x] 2.2 Replace the `DEFAULT_TICKERS` list in `schema.py` with an import of `SEED_TICKERS` from `seed_tickers.py`

## 3. Migration and Upgrade Seed Logic

- [x] 3.1 Add `ALTER TABLE analysis_tickers ADD COLUMN sector/sub_sector/seed_version` migration loop in `init_db()` using the existing duplicate-column guard pattern
- [x] 3.2 Add frozenset comparison logic to detect legacy install (existing tickers == LEGACY_TICKERS)
- [x] 3.3 Implement legacy upgrade path: wrap DELETE all + INSERT 100 in explicit transaction
- [x] 3.4 Implement fresh-install path: INSERT OR IGNORE all 100 tickers when table is empty
- [x] 3.5 Implement additive merge path: INSERT OR IGNORE only missing tickers when custom tickers are present

## 4. Unit Tests (offline)

- [x] 4.1 Create `backend/tests/test_seed_tickers.py` covering: len == 100, no duplicate tickers, all entries have non-empty sector/sub_sector, LEGACY_TICKERS equals the original 10-ticker frozenset

## 5. Integration Tests (async)

- [x] 5.1 Create `backend/tests/test_seed_migration.py` covering: fresh install seeds 100 rows, legacy upgrade truncates and replaces, additive merge preserves custom tickers, column migration is idempotent, seed_version is stamped on inserted rows
