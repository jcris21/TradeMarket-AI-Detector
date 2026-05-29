## ADDED Requirements

### Requirement: Bet-size metrics pre-computed at analysis write time
The `ScoringAgent` SHALL compute `expected_gain_per10`, `expected_loss_per10`, `expected_value_per10`, `hit_rate_used`, and `hit_rate_source` for every `AssetAnalysis` and persist them to `analysis_results`.

#### Scenario: Standard BUY signal with valid prices
- **WHEN** `ScoringAgent.score_and_rank()` processes an asset with `entry_price > 0`, `target_price`, and `stop_loss`
- **THEN** `expected_gain_per10 = round(10 * (target - entry) / entry, 2)`
- **THEN** `expected_loss_per10 = round(10 * (entry - stop) / entry, 2)`
- **THEN** `expected_value_per10 = round(hit_rate * gain_10 - (1 - hit_rate) * loss_10, 2)`

#### Scenario: Division-by-zero guard
- **WHEN** `entry_price <= 0`
- **THEN** `expected_gain_per10 = 0.0`, `expected_loss_per10 = 0.0`, `expected_value_per10 = 0.0`

### Requirement: Hit rate switches from assumed to realized at 30 outcomes
The system SHALL use a 35% assumed hit rate until 30 or more outcomes are recorded in `signal_outcomes`, at which point it SHALL use the realized hit rate.

#### Scenario: Fewer than 30 historical outcomes
- **WHEN** `signal_outcomes` has fewer than 30 rows for `user_id = 'default'`
- **THEN** `hit_rate_used = 0.35` and `hit_rate_source = 'assumed'`

#### Scenario: 30 or more historical outcomes
- **WHEN** `signal_outcomes` has 30 or more rows for `user_id = 'default'`
- **THEN** `hit_rate_used = wins / total` and `hit_rate_source = 'realized'`

#### Scenario: signal_outcomes table does not exist
- **WHEN** `signal_outcomes` table is absent (TECH-003 not yet deployed)
- **THEN** system falls back to `hit_rate_used = 0.35`, `hit_rate_source = 'assumed'` without raising an error

### Requirement: analysis_results stores five new nullable columns
The `analysis_results` table SHALL have five new nullable columns applied via lazy migration at startup.

#### Scenario: Fresh database initialization
- **WHEN** the container starts with a new or existing `finally.db`
- **THEN** `ALTER TABLE` adds `expected_gain_per10 REAL`, `expected_loss_per10 REAL`, `expected_value_per10 REAL`, `hit_rate_used REAL`, `hit_rate_source TEXT` without error

#### Scenario: Migration on existing database
- **WHEN** columns already exist from a previous run
- **THEN** startup completes without error (duplicate column error is silently ignored)

### Requirement: AssetAnalysis model exposes bet-size fields
The `AssetAnalysis` Pydantic model SHALL include five optional fields that are serialized in all existing analysis API responses.

#### Scenario: Analysis response includes bet-size fields
- **WHEN** `GET /api/analysis/latest` or `GET /api/analysis/{ticker}` is called after a run that computed bet-size metrics
- **THEN** response JSON includes `expected_gain_per10`, `expected_loss_per10`, `expected_value_per10`, `hit_rate_used`, `hit_rate_source`

#### Scenario: Legacy rows with NULL bet-size fields
- **WHEN** the API returns a row that predates the migration
- **THEN** bet-size fields are `null` in the response (no error)

### Requirement: BetSizeCell component renders monetary values for BUY signals
The `OpportunitiesPanel` SHALL display a `BetSizeCell` component in a dedicated "Bet Size" column for rows where `signal = "BUY"`.

#### Scenario: BUY signal with populated bet-size data
- **WHEN** an asset row has `signal = "BUY"` and non-null `expected_gain_per10`
- **THEN** the cell shows `+$X.XX` in green, `-$X.XX` in red, and `EV $X.XX @ {pct}% {source}` in amber

#### Scenario: Non-BUY signal row
- **WHEN** an asset row has `signal != "BUY"`
- **THEN** the Bet Size cell renders `—`

#### Scenario: BUY signal with null bet-size data (legacy row)
- **WHEN** an asset row has `signal = "BUY"` but `expected_gain_per10 = null`
- **THEN** the Bet Size cell renders `—`

### Requirement: EV badge shows hit rate basis with tooltip
The EV value SHALL include a label indicating whether the hit rate is assumed or realized, with a tooltip providing an explanation.

#### Scenario: Assumed hit rate display
- **WHEN** `hit_rate_source = 'assumed'`
- **THEN** EV badge reads `EV $X.XX @ 35% assumed` with tooltip `"Based on 35% assumed hit rate (< 30 historical signals)"`

#### Scenario: Realized hit rate display
- **WHEN** `hit_rate_source = 'realized'`
- **THEN** EV badge reads `EV $X.XX @ {pct}% realized` with tooltip `"Based on realized hit rate from historical signal outcomes"`
