## ADDED Requirements

### Requirement: ANALYSIS_TOP_N default raised to 20
The backend SHALL default `ANALYSIS_TOP_N` to `"20"` (previously `"5"`). Valid range is 5–20; values outside this range SHALL be clamped. `AnalysisResult` SHALL expose a canonical `top_n: list[AssetAnalysis]` field populated by `orchestrator.py`. A deprecated alias `top_5` SHALL be set to the same list for backward compatibility and removed in the next sprint.

#### Scenario: Default run returns up to 20 signals
- **WHEN** `ANALYSIS_TOP_N` is not set and a 100-ticker analysis completes
- **THEN** `AnalysisResult.top_n` contains up to 20 ranked signals and `top_5` contains the same list

#### Scenario: Override via env var is respected
- **WHEN** `ANALYSIS_TOP_N=10` and a 100-ticker analysis completes
- **THEN** `AnalysisResult.top_n` contains at most 10 signals

#### Scenario: Value above 20 is clamped to 20
- **WHEN** `ANALYSIS_TOP_N=50`
- **THEN** at most 20 signals are returned

#### Scenario: Backward compat alias top_5 equals top_n
- **WHEN** the API response is serialised
- **THEN** `top_5` and `top_n` contain identical items in identical order

### Requirement: total_analyzed count in API response
`GET /api/analysis/latest` SHALL include a `total_analyzed` integer field in the response body representing the count of all assets passed to scoring in that run (before top-N filtering).

#### Scenario: total_analyzed reflects full asset count
- **WHEN** 100 tickers were analyzed and 18 qualified
- **THEN** `total_analyzed` is 100 and `top_n` has 18 items (assuming 18 ≤ top_n_limit)

#### Scenario: total_analyzed is 0 for no-run state
- **WHEN** no analysis run has completed
- **THEN** `total_analyzed` is 0 or absent from response

### Requirement: Client-side pagination of Top Opportunities table
The OpportunitiesPanel SHALL display `displayedSignals` in pages of 10. `currentPage` state starts at 1, resets to 1 whenever a new analysis run completes, and persists while the user browses between tabs in the same session.

#### Scenario: First page shows ranks 1–10
- **WHEN** 15 qualified signals are available and currentPage is 1
- **THEN** the table renders signals with ranks 1 through 10

#### Scenario: Second page shows ranks 11–20
- **WHEN** 15 qualified signals are available and the user clicks Next
- **THEN** the table renders signals with ranks 11 through 15 (remainder of list)

#### Scenario: Page resets to 1 on new run
- **WHEN** the user is on page 2 and a new analysis run completes
- **THEN** currentPage resets to 1 and signals 1–10 are shown

### Requirement: Pagination controls visible when count exceeds 10
The OpportunitiesPanel SHALL render `← Prev  Page N of M  Next →` controls below the table only when `totalPages > 1`. Page dots (● / ○) SHALL appear beside the page counter.

#### Scenario: Controls hidden when 10 or fewer signals
- **WHEN** 8 qualified signals are displayed
- **THEN** no pagination controls are rendered

#### Scenario: Controls rendered when more than 10 signals
- **WHEN** 15 qualified signals are displayed
- **THEN** Prev, Next buttons and "Page 1 of 2" label appear below the table

#### Scenario: Prev button disabled on first page
- **WHEN** currentPage is 1
- **THEN** the Prev button has the disabled attribute (or equivalent opacity)

#### Scenario: Next button disabled on last page
- **WHEN** currentPage equals totalPages
- **THEN** the Next button has the disabled attribute

#### Scenario: Keyboard arrow navigation changes page
- **WHEN** the panel is focused and the user presses ArrowRight
- **THEN** currentPage increments by 1 (if not already last page)

### Requirement: Summary line above table
The OpportunitiesPanel SHALL display a summary line above the signal table with format: `"Showing N of M qualified signals (K analyzed)"`. The `(K analyzed)` suffix SHALL appear only when `total_analyzed > 0`.

#### Scenario: Summary reflects current page slice
- **WHEN** 18 signals are available, total_analyzed=100, currentPage=1
- **THEN** summary reads "Showing 10 of 18 qualified signals (100 analyzed)"

#### Scenario: Summary on last page shows remainder
- **WHEN** 18 signals, currentPage=2
- **THEN** summary reads "Showing 8 of 18 qualified signals (100 analyzed)"

#### Scenario: Summary omits analyzed count when zero
- **WHEN** total_analyzed is 0 or absent
- **THEN** summary reads "Showing N of M qualified signals" without parenthetical

### Requirement: Enrichment badge per signal row
Each signal row SHALL display an enrichment indicator:
- No badge when `enrichment_delta` is absent or null (not enriched)
- `+N visual` badge (green border) when `enrichment_delta > 0`
- `-N visual` badge (red border) when `enrichment_delta < 0`

The badge value SHALL be `Math.round(enrichment_delta)`.

#### Scenario: No badge for unenriched signal
- **WHEN** an AssetAnalysis row has no enrichment_delta
- **THEN** no enrichment badge is rendered in that row

#### Scenario: Positive enrichment badge rendered in green
- **WHEN** enrichment_delta is 7.3
- **THEN** a badge reading "+7 visual" with green styling is shown

#### Scenario: Negative enrichment delta renders red badge
- **WHEN** enrichment_delta is -4.2
- **THEN** a badge reading "-4 visual" with red styling is shown
