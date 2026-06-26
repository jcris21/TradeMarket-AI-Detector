## ADDED Requirements

### Requirement: AssetAnalysis model carries enrichment_type field
`AssetAnalysis` SHALL include `enrichment_type: Optional[Literal["trader_chart", "auto_screenshot"]] = None`. The field SHALL be included in `to_db_row()` output under the key `"enrichment_type"`.

#### Scenario: enrichment_type populated after auto_screenshot enrichment
- **WHEN** `_run_screenshot_enrichment` completes and updates the analysis row
- **THEN** `analysis_results.enrichment_type = "auto_screenshot"` for that ticker

#### Scenario: enrichment_type populated after trader_chart enrichment
- **WHEN** `confirm_enrichment` completes for a `trader_chart` job
- **THEN** `analysis_results.enrichment_type = "trader_chart"` for that ticker

#### Scenario: enrichment_type null for unenriched signals
- **WHEN** a signal has never been enriched
- **THEN** `analysis_results.enrichment_type` is NULL and API response includes `"enrichment_type": null`

### Requirement: analysis_results table has enrichment_type column
The `analysis_results` table DDL SHALL include `enrichment_type TEXT` column. For existing databases lacking this column, a migration guard SHALL execute `ALTER TABLE analysis_results ADD COLUMN enrichment_type TEXT` at app startup.

#### Scenario: Fresh database has enrichment_type column
- **WHEN** a fresh SQLite database is initialized
- **THEN** `analysis_results` table includes `enrichment_type TEXT` column

#### Scenario: Migration guard adds column to existing database
- **WHEN** an existing database without `enrichment_type` column is present at startup
- **THEN** startup completes successfully and the column is added without data loss

#### Scenario: Migration guard is idempotent
- **WHEN** `enrichment_type` column already exists
- **THEN** startup completes without error (OperationalError from duplicate column is silently caught)

### Requirement: enrichment_type exposed in GET /api/analysis/{ticker} response
`GET /api/analysis/{ticker}` SHALL include `"enrichment_type"` in its response payload, reflecting the value from `analysis_results.enrichment_type` (null if unenriched).

#### Scenario: enrichment_type present in ticker response
- **WHEN** ticker AAPL has `analysis_results.enrichment_type = "auto_screenshot"`
- **THEN** `GET /api/analysis/AAPL` response includes `"enrichment_type": "auto_screenshot"`

#### Scenario: enrichment_type null in ticker response
- **WHEN** ticker has not been enriched
- **THEN** `GET /api/analysis/AAPL` response includes `"enrichment_type": null`

### Requirement: enrichment_type exposed in GET /api/analysis/latest response
`GET /api/analysis/latest` SHALL include `"enrichment_type"` in each result row's payload.

#### Scenario: Latest results include enrichment_type
- **WHEN** some tickers are enriched and some are not
- **THEN** each result in the `results` array includes `"enrichment_type"` (non-null for enriched, null for unenriched)
