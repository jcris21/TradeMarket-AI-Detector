## ADDED Requirements

### Requirement: ATR indicators computed by DataAgent
The system SHALL compute `atr_14` (14-period Average True Range, absolute) and `atr_14_pct` (`atr_14 / current_price`) for every asset processed by DataAgent using `pandas-ta`. Both fields SHALL be appended as optional tail fields (defaulting to `None`) on the `TechnicalIndicators` frozen dataclass to preserve backward compatibility with existing instantiations.

#### Scenario: ATR successfully computed
- **WHEN** DataAgent processes an asset with sufficient OHLCV history (≥14 bars)
- **THEN** `TechnicalIndicators.atr_14` SHALL be a non-null positive float rounded to 4 decimal places
- **THEN** `TechnicalIndicators.atr_14_pct` SHALL be `atr_14 / current_price` rounded to 6 decimal places

#### Scenario: ATR unavailable due to insufficient history or data error
- **WHEN** `ta.atr()` returns `None` or an all-NaN series
- **THEN** `TechnicalIndicators.atr_14` SHALL be `None`
- **THEN** `TechnicalIndicators.atr_14_pct` SHALL be `None`

#### Scenario: Current price is zero or negative
- **WHEN** `current_price` is zero or negative at ATR computation time
- **THEN** `atr_14_pct` SHALL be `None` (division guard applied)
- **THEN** `atr_14` SHALL still be set if computable

### Requirement: AssetAnalysis carries ATR viability fields
The system SHALL expose `atr_14_pct: float | None`, and `stop_viable: bool | None` on `AssetAnalysis`. `stop_viable = None` SHALL represent "ATR check skipped" (data unavailable), `True` SHALL represent "stop clears the viability threshold", and `False` SHALL represent "stop fails the viability threshold". Both fields SHALL be included in `to_db_row()` output and persisted to `analysis_results`.

#### Scenario: ATR viability check passes
- **WHEN** `stop_distance_pct >= ATR_FLOOR_FACTOR × atr_14_pct`
- **THEN** `AssetAnalysis.stop_viable` SHALL be `True`

#### Scenario: ATR viability check fails (soft)
- **WHEN** `0.5 × atr_14_pct <= stop_distance_pct < ATR_FLOOR_FACTOR × atr_14_pct`
- **THEN** `AssetAnalysis.stop_viable` SHALL be `False`

#### Scenario: ATR check skipped
- **WHEN** `atr_14_pct` is `None`
- **THEN** `AssetAnalysis.stop_viable` SHALL be `None`

### Requirement: ATR hard disqualification removes setup from ranking
The system SHALL hard-disqualify any asset setup where `stop_distance_pct < 0.5 × atr_14_pct`. A hard-disqualified asset SHALL receive `rank = None` and SHALL NOT appear in any ranked list returned to the dashboard.

#### Scenario: Stop inside ATR hard floor
- **WHEN** `(entry_price - stop_loss) / entry_price < 0.5 × atr_14_pct`
- **THEN** asset `rank` SHALL be `None`
- **THEN** an error with prefix `atr_disqualify:` SHALL be appended to `AnalysisResult.errors`
- **THEN** `AssetAnalysis.stop_viable` SHALL be `False`

#### Scenario: Stop at exactly the hard floor boundary
- **WHEN** `stop_distance_pct == 0.5 × atr_14_pct` (equality)
- **THEN** the asset SHALL NOT be hard-disqualified (boundary is exclusive lower bound)

### Requirement: ATR soft penalty applied to score
The system SHALL apply a −15 point deduction to the composite score when `stop_distance_pct` is between the hard floor (0.5× ATR) and `ATR_FLOOR_FACTOR × ATR` (exclusive upper bound).

#### Scenario: Stop in soft-penalty band
- **WHEN** `0.5 × atr_14_pct <= stop_distance_pct < ATR_FLOOR_FACTOR × atr_14_pct`
- **THEN** composite score SHALL be reduced by exactly 15 points relative to the no-ATR baseline
- **THEN** `stop_viable` SHALL be `False`

#### Scenario: Stop in neutral band
- **WHEN** `ATR_FLOOR_FACTOR × atr_14_pct <= stop_distance_pct <= 1.5 × atr_14_pct`
- **THEN** composite score SHALL have zero ATR adjustment
- **THEN** `stop_viable` SHALL be `True`

### Requirement: ATR boost awarded for well-placed stops
The system SHALL award +8 points to the composite score when `stop_distance_pct > 1.5 × atr_14_pct`.

#### Scenario: Stop beyond boost threshold
- **WHEN** `stop_distance_pct > 1.5 × atr_14_pct`
- **THEN** composite score SHALL be increased by exactly 8 points relative to the no-ATR baseline
- **THEN** `stop_viable` SHALL be `True`

### Requirement: ATR floor factor configurable via environment variable
The system SHALL read `ATR_FLOOR_FACTOR` from the `ANALYSIS_ATR_FLOOR` environment variable at runtime with a default of `0.8`.

#### Scenario: Env var set to custom value
- **WHEN** `ANALYSIS_ATR_FLOOR=1.0` is set before process start
- **THEN** the soft-penalty upper bound SHALL use `1.0 × atr_14_pct` as the threshold

#### Scenario: Env var absent
- **WHEN** `ANALYSIS_ATR_FLOOR` is not set
- **THEN** `ATR_FLOOR_FACTOR` SHALL default to `0.8`

### Requirement: ATR unavailability is a scoring pass-through
The system SHALL NOT penalize or disqualify an asset when `atr_14_pct` is `None`. The asset SHALL be scored as if no ATR check were applied, with `stop_viable = None`.

#### Scenario: Asset with no ATR data passes scoring unchanged
- **WHEN** `AssetAnalysis.atr_14_pct` is `None`
- **THEN** `_compute_atr_viability()` SHALL return `(False, True, 0.0)` — no disqualify, no score delta
- **THEN** the asset's score SHALL equal the baseline score with zero ATR adjustment

### Requirement: DB schema persists stop_viable
The system SHALL store `stop_viable` as an `INTEGER` column in `analysis_results`. The column SHALL be added via the existing lazy migration mechanism on first startup after deploy. Existing rows SHALL have `NULL` for this column, interpreted by the application as `stop_viable = None`.

#### Scenario: New analysis row persisted
- **WHEN** a new `AssetAnalysis` is written to `analysis_results`
- **THEN** `stop_viable` SHALL be stored as `1` (True), `0` (False), or `NULL` (None)

#### Scenario: Existing row read after migration
- **WHEN** an existing row with `stop_viable = NULL` is retrieved
- **THEN** `_parse_analysis_row()` SHALL return `stop_viable = None`

### Requirement: Frontend displays ATR viability badge per signal
The system SHALL render an ATR badge in the `SignalTable` for each signal row. The badge SHALL show "✔ ATR" (green) when `stop_viable` is `true`, "❌ ATR" (red/loss color) when `stop_viable` is `false`, and "—" (muted) when `stop_viable` is `null` or `atr_14_pct` is `null`.

#### Scenario: Viable stop badge
- **WHEN** `asset.stop_viable === true` and `asset.atr_14_pct != null`
- **THEN** badge SHALL display "✔ ATR" in the `text-gain` color class

#### Scenario: Non-viable stop badge
- **WHEN** `asset.stop_viable === false`
- **THEN** badge SHALL display "❌ ATR" in the `text-loss` color class

#### Scenario: ATR data absent
- **WHEN** `asset.atr_14_pct == null`
- **THEN** badge SHALL display "—" in the `text-text-muted` color class
