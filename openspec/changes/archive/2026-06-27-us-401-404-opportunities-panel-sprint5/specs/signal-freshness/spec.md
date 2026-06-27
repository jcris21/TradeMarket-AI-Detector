## MODIFIED Requirements

### Requirement: Expired signals separated into Signal Archive tab
The OpportunitiesPanel SHALL display two tabs: **Oportunidades** (default) and **Archivo**.

- **Oportunidades** tab: shows signals where `freshness_status !== "expired"`.
- **Archivo** tab: shows only signals where `freshness_status === "expired"`.

Filtering is performed client-side from the existing `results` array in `useAnalysis()`. No additional API call is made.

Expired rows in the **Archivo** tab SHALL additionally receive the following visual treatment (US-404):
- Row opacity: 40% (`opacity: 0.4`)
- Ticker text: `text-decoration: line-through`
- Score band badge replaced by an `EXPIRED` badge with grey (#6B7280) border and text

#### Scenario: Default tab excludes expired signals
- **WHEN** the OpportunitiesPanel renders with a mix of fresh, active, aged, and expired results
- **THEN** the Oportunidades tab shows only fresh, active, and aged signals

#### Scenario: Archive tab shows only expired signals
- **WHEN** the user clicks the Archivo tab
- **THEN** only signals with `freshness_status="expired"` are displayed

#### Scenario: Archive tab is empty when no expired signals exist
- **WHEN** all results have freshness_status of fresh, active, or aged
- **THEN** the Archivo tab renders an empty state message

#### Scenario: Missing freshness_status does not break rendering
- **WHEN** a result is returned without freshness_status (e.g., older cached data)
- **THEN** no badge is rendered for that row and the row appears in the Oportunidades tab by default

#### Scenario: Expired rows in archive tab have reduced opacity
- **WHEN** an expired signal is displayed in the Archivo tab
- **THEN** the row's opacity is 0.4 and the ticker has line-through decoration

#### Scenario: Expired rows show EXPIRED badge not score band badge
- **WHEN** an expired signal is displayed in the Archivo tab
- **THEN** the EXPIRED badge (grey) appears in the badge column; no ScoreBandBadge renders

## ADDED Requirements

### Requirement: prior_score_quant per ticker in API response (P1)
`GET /api/analysis/latest` SHALL include a `prior_score_quant` field (nullable float) on each item in `top_n`. This value represents the `score_quant` for the same ticker from the immediately preceding completed run. When no prior run exists, or the ticker was not in the prior run, the field SHALL be `null`.

The backend SHALL implement a `get_prior_scores(conn, run_id: str) -> dict[str, float]` function in `db/repository.py` that:
1. Finds the last completed `analysis_run` with id < current `run_id`
2. Fetches all `analysis_results.score_quant` for that prior run
3. Returns a dict of `{ticker: score_quant}`

#### Scenario: prior_score_quant populated for known ticker
- **WHEN** AAPL had score_quant=65 in the previous run and score_quant=72 in the current run
- **THEN** the AAPL entry in top_n has prior_score_quant=65

#### Scenario: prior_score_quant is null when no prior run
- **WHEN** the current run is the first completed run
- **THEN** all items have prior_score_quant=null

#### Scenario: prior_score_quant is null for new ticker not in prior run
- **WHEN** a ticker appears in the current run but was not in the previous run
- **THEN** that ticker's prior_score_quant is null

#### Scenario: get_prior_scores handles missing prior run gracefully
- **WHEN** no prior run row exists in analysis_runs
- **THEN** function returns an empty dict and no exception is raised
