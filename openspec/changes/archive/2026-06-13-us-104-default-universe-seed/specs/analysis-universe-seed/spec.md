## ADDED Requirements

### Requirement: Seed ticker source of truth
`backend/app/analysis/seed_tickers.py` SHALL export `SEED_TICKERS` (list of 100 dicts with `ticker`, `sector`, `sub_sector` keys), `SEED_VERSION` (string constant, initial value `"v1"`), and `LEGACY_TICKERS` (frozenset of the original 10 tickers: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX). The file SHALL have zero imports from `db/` or `app/` modules.

#### Scenario: SEED_TICKERS has exactly 100 entries
- **WHEN** `SEED_TICKERS` is imported from `seed_tickers.py`
- **THEN** `len(SEED_TICKERS) == 100`

#### Scenario: No duplicate tickers in seed list
- **WHEN** `SEED_TICKERS` is imported from `seed_tickers.py`
- **THEN** all `ticker` values are unique (no duplicates)

#### Scenario: Every ticker has valid sector and sub_sector
- **WHEN** `SEED_TICKERS` is imported from `seed_tickers.py`
- **THEN** every entry has non-empty `ticker`, `sector`, and `sub_sector` strings

#### Scenario: LEGACY_TICKERS matches original 10-ticker set exactly
- **WHEN** `LEGACY_TICKERS` is imported from `seed_tickers.py`
- **THEN** `LEGACY_TICKERS == frozenset({"AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"})`

### Requirement: Analysis tickers table schema migration
`init_db()` SHALL add `sector TEXT`, `sub_sector TEXT`, and `seed_version TEXT` columns to `analysis_tickers` using the existing duplicate-column guard pattern (catching `duplicate column name` error) before executing any seed upgrade logic.

#### Scenario: Fresh database gains all three columns
- **WHEN** `init_db()` runs on a database with no `analysis_tickers` table
- **THEN** the table is created with `sector`, `sub_sector`, and `seed_version` columns present

#### Scenario: Existing database gets additive column migration
- **WHEN** `init_db()` runs on an existing `analysis_tickers` table that lacks the new columns
- **THEN** all three columns are added without error or data loss

#### Scenario: Migration is idempotent
- **WHEN** `init_db()` runs a second time on a database that already has the new columns
- **THEN** no error is raised and existing data is unchanged

### Requirement: Legacy install upgrade (truncate and replace)
When `init_db()` detects that the existing `analysis_tickers` rows for `user_id = "default"` form a frozenset equal to `LEGACY_TICKERS`, it SHALL DELETE all rows for that user and INSERT all 100 seed tickers, wrapping the DELETE + INSERT in an explicit transaction.

#### Scenario: Legacy 10-ticker install is upgraded to 100 tickers
- **WHEN** `analysis_tickers` contains exactly the 10 legacy tickers for `user_id = "default"`
- **THEN** after `init_db()` completes, the table contains all 100 seed tickers for that user
- **THEN** `sector`, `sub_sector`, and `seed_version` are populated for every row

#### Scenario: Upgrade transaction is atomic
- **WHEN** the DELETE succeeds but an INSERT fails during the legacy upgrade path
- **THEN** the entire transaction is rolled back (no partial state persisted)

### Requirement: Fresh install seeds all 100 tickers
When `init_db()` detects that `analysis_tickers` is empty for `user_id = "default"`, it SHALL INSERT all 100 seed tickers using `INSERT OR IGNORE`.

#### Scenario: Empty table receives full 100-ticker seed
- **WHEN** `analysis_tickers` has zero rows for `user_id = "default"`
- **THEN** after `init_db()` completes, the table contains 100 rows with sector, sub_sector, and seed_version populated

### Requirement: Custom-ticker install uses additive merge only
When `init_db()` detects that the existing tickers for `user_id = "default"` differ from `LEGACY_TICKERS` and the table is non-empty, it SHALL INSERT only the tickers from `SEED_TICKERS` that are not already present, using `INSERT OR IGNORE`. It SHALL NOT DELETE any existing rows.

#### Scenario: Custom tickers are preserved during merge
- **WHEN** `analysis_tickers` contains the 10 legacy tickers plus one custom ticker (e.g., `CUSTOM_XYZ`)
- **THEN** after `init_db()` completes, `CUSTOM_XYZ` remains in the table
- **THEN** all 100 seed tickers are also present

#### Scenario: Merge is idempotent
- **WHEN** `init_db()` runs on a database that already contains all 100 seed tickers plus a custom ticker
- **THEN** no rows are deleted and no duplicates are inserted

### Requirement: Seed version stamped on all inserted rows
Every row inserted by the upgrade-seed logic SHALL have `seed_version` set to `SEED_VERSION` (e.g., `"v1"`). Rows already present before a merge are not retroactively updated.

#### Scenario: Freshly inserted rows carry seed_version
- **WHEN** any of the three upgrade paths executes and inserts rows
- **THEN** each inserted row has `seed_version = "v1"`
