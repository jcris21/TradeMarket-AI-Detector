## ADDED Requirements

### Requirement: Freshness computation from analyzed_at
The system SHALL compute a `freshness_status` and `freshness_age_hours` for every analysis result at read time using the existing `analyzed_at` UTC timestamp. No schema change is required.

Thresholds (UTC elapsed hours since `analyzed_at`):
- `fresh`: age_hours < 2
- `active`: 2 ≤ age_hours < 5
- `aged`: 5 ≤ age_hours < 24
- `expired`: age_hours ≥ 24

#### Scenario: Signal within 2 hours returns fresh status
- **WHEN** `GET /api/analysis/latest` is called and a result has `analyzed_at` 1.5 hours ago
- **THEN** the response includes `"freshness_status": "fresh"` and `freshness_age_hours` ≈ 1.5 for that result

#### Scenario: Signal between 2 and 5 hours returns active status
- **WHEN** `GET /api/analysis/latest` is called and a result has `analyzed_at` 3 hours ago
- **THEN** the response includes `"freshness_status": "active"` and `freshness_age_hours` ≈ 3.0

#### Scenario: Signal between 5 and 24 hours returns aged status
- **WHEN** `GET /api/analysis/latest` is called and a result has `analyzed_at` 7 hours ago
- **THEN** the response includes `"freshness_status": "aged"` and `freshness_age_hours` ≈ 7.0

#### Scenario: Signal older than 24 hours returns expired status
- **WHEN** `GET /api/analysis/latest` is called and a result has `analyzed_at` 25 hours ago
- **THEN** the response includes `"freshness_status": "expired"` and `freshness_age_hours` ≈ 25.0

#### Scenario: Boundary at exactly 2 hours is active not fresh
- **WHEN** freshness is computed for a signal exactly 2.0 hours old
- **THEN** `freshness_status` is `"active"`

#### Scenario: Boundary at exactly 5 hours is aged not active
- **WHEN** freshness is computed for a signal exactly 5.0 hours old
- **THEN** `freshness_status` is `"aged"`

#### Scenario: Boundary at exactly 24 hours is expired
- **WHEN** freshness is computed for a signal exactly 24.0 hours old
- **THEN** `freshness_status` is `"expired"`

### Requirement: Freshness badge displayed per signal row
The frontend SHALL render a color-coded `FreshnessBadge` component in the OpportunitiesPanel signal table for each result that includes `freshness_status` and `freshness_age_hours`.

Badge appearance by state:
- `fresh`: green (`text-green-400`), icon `✅`, label `"Fresh"`, age `"1.5h ago"`
- `active`: yellow (`text-yellow-400`), icon `⚠️`, label `"Active"`, age `"3.0h ago"`
- `aged`: orange (`text-orange-400`), icon `⌛`, label `"Aged"`, age `"7h ago"`
- `expired`: gray (`text-gray-500`), icon `❌`, label `"Expired"`, age `"25h ago"`

Age label formatting: 1 decimal place when `age_hours < 10`, integer otherwise.

Each badge SHALL include a `title` tooltip attribute explaining the state.

#### Scenario: Fresh badge renders with correct color and age
- **WHEN** `FreshnessBadge` is rendered with `status="fresh"` and `ageHours=1.5`
- **THEN** the component displays `"✅"`, `"Fresh"`, `"1.5h ago"`, uses green color classes, and `title` contains `"optimal entry window"`

#### Scenario: Active badge renders with warning tooltip
- **WHEN** `FreshnessBadge` is rendered with `status="active"` and `ageHours=3.0`
- **THEN** the component displays `"⚠️"`, `"Active"`, `"3.0h ago"`, uses yellow color classes, and `title` contains `"Verify"`

#### Scenario: Aged badge renders with dimmed indicator
- **WHEN** `FreshnessBadge` is rendered with `status="aged"` and `ageHours=7.0`
- **THEN** the component displays `"⌛"`, `"Aged"`, `"7h ago"`, uses orange color classes

#### Scenario: Expired badge renders with gray color
- **WHEN** `FreshnessBadge` is rendered with `status="expired"` and `ageHours=25.0`
- **THEN** the component displays `"❌"`, `"Expired"`, `"25h ago"`, uses gray color classes

#### Scenario: Age label uses integer for values >= 10 hours
- **WHEN** `FreshnessBadge` is rendered with `ageHours=12.7`
- **THEN** the age label displays `"13h ago"` (not `"12.7h ago"`)

### Requirement: Score cell dimmed for aged and expired signals
The OpportunitiesPanel score cell SHALL apply `opacity-40` when `freshness_status` is `"aged"` or `"expired"`.

#### Scenario: Score cell is full opacity for fresh signal
- **WHEN** a signal with `freshness_status="fresh"` is rendered in the table
- **THEN** the score cell does NOT have the `opacity-40` class

#### Scenario: Score cell is dimmed for aged signal
- **WHEN** a signal with `freshness_status="aged"` is rendered in the table
- **THEN** the score cell has the `opacity-40` class applied

#### Scenario: Score cell is dimmed for expired signal
- **WHEN** a signal with `freshness_status="expired"` is rendered in the table
- **THEN** the score cell has the `opacity-40` class applied

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
