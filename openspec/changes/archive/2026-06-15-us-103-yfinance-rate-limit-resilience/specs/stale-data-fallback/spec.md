## ADDED Requirements

### Requirement: AssetAnalysis carries is_stale flag
The `AssetAnalysis` Pydantic model SHALL include `is_stale: bool = False`. This field is a runtime-only flag and SHALL NOT be persisted by `to_db_row()`. All existing code constructing `AssetAnalysis` without `is_stale` SHALL continue to work unchanged (default `False`).

#### Scenario: Default AssetAnalysis is not stale
- **WHEN** `AssetAnalysis` is constructed without `is_stale`
- **THEN** `asset.is_stale` equals `False`

#### Scenario: Stale asset carries flag
- **WHEN** `AssetAnalysis` is constructed with `is_stale=True`
- **THEN** `asset.is_stale` equals `True`

### Requirement: AnalysisResult tracks stale tickers
The `AnalysisResult` Pydantic model SHALL include `stale_tickers: list[str] = []`. This field lists every ticker that was served from cache in the current run.

#### Scenario: No stale tickers by default
- **WHEN** `AnalysisResult` is constructed without `stale_tickers`
- **THEN** `result.stale_tickers` equals `[]`

### Requirement: Staleness fallback for exhausted rate-limited tickers
The system SHALL implement a staleness fallback in the orchestrator Stage-1 loop. For each ticker whose `DataFetchError` has `reason="rate_limited"` (i.e., all retries exhausted), the system SHALL call `await get_analysis_by_ticker(ticker)`. If a DB row is returned and its `analyzed_at` timestamp is within the last 24 hours, the system SHALL reconstruct an `AssetAnalysis` from that row with `is_stale=True`, add the ticker to the `successful` set so it flows through stages 2–4, and append the ticker to `stale_tickers`. If no DB row exists or the row is older than 24 hours, the ticker SHALL remain in `errors` and SHALL NOT be added to `stale_tickers`.

#### Scenario: Valid cached result within 24 hours is used
- **WHEN** a ticker fails with `reason="rate_limited"` and `get_analysis_by_ticker` returns a row with `analyzed_at` 2 hours ago
- **THEN** the ticker is added to `stale_tickers`, its `AssetAnalysis.is_stale` equals `True`, and it is not present in `AnalysisResult.errors`

#### Scenario: Cached result older than 24 hours is rejected
- **WHEN** a ticker fails with `reason="rate_limited"` and `get_analysis_by_ticker` returns a row with `analyzed_at` 25 hours ago
- **THEN** the ticker remains in `AnalysisResult.errors` and is not added to `stale_tickers`

#### Scenario: No cached result available
- **WHEN** a ticker fails with `reason="rate_limited"` and `get_analysis_by_ticker` returns `None`
- **THEN** the ticker remains in `AnalysisResult.errors` and is not added to `stale_tickers`

#### Scenario: Empty-dataframe errors do not trigger fallback
- **WHEN** a ticker fails with `reason="empty_dataframe"`
- **THEN** `get_analysis_by_ticker` is not called for that ticker

### Requirement: Frontend warning badge for stale signals
The frontend analysis card component SHALL render a visible warning badge with text `"Stale data"` styled with accent-yellow (`#ecad0a`) when a signal has `is_stale=True`. No other UI changes are required for stale assets.

#### Scenario: Stale signal shows badge
- **WHEN** an analysis card receives a signal with `is_stale=True`
- **THEN** the card displays a `"Stale data"` badge in accent-yellow (`#ecad0a`)

#### Scenario: Non-stale signal shows no badge
- **WHEN** an analysis card receives a signal with `is_stale=False` or `is_stale` absent
- **THEN** no stale badge is rendered on the card
