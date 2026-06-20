## MODIFIED Requirements

### Requirement: Staleness fallback for exhausted rate-limited tickers
The system SHALL implement a staleness fallback in the orchestrator Stage-1 loop. For each ticker whose `DataFetchError` has `reason="rate_limited"` (i.e., all retries exhausted), the system SHALL call `await get_analysis_by_ticker(ticker)`. If a DB row is returned and its `analyzed_at` timestamp is within the last 24 hours, the system SHALL reconstruct an `AssetAnalysis` from that row with `is_stale=True`, add the ticker to the `successful` set so it flows through stages 2–4, and append the ticker to `stale_tickers`. If no DB row exists or the row is older than 24 hours, the ticker SHALL remain in `errors` and SHALL NOT be added to `stale_tickers`.

Stale fallback assets with `signal="BUY"` SHALL be subject to the VIX gate transformation after Stage 4. If the VIX gate is active, `signal` SHALL be converted to `"AVOID"` and `rank_exclusion_reason` set to `"regime_vix"`.

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

#### Scenario: Stale BUY asset suppressed when VIX gate is active
- **WHEN** a stale fallback asset has `signal="BUY"` and `regime_gate_active=True`
- **THEN** the stale asset has `signal="AVOID"` and `rank_exclusion_reason="regime_vix"` in the final result
