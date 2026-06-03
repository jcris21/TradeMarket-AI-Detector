## ADDED Requirements

### Requirement: PerformanceSummaryPanel renders phase-gated metrics
The system SHALL render a `PerformanceSummaryPanel` component that displays performance metrics only after 30+ conclusive signals, showing a calibration progress bar otherwise.

#### Scenario: Calibration state below 30 signals
- **WHEN** `phase_gate_active` is `true` (fewer than 30 conclusive signals)
- **THEN** the panel displays "Phase 0 — Calibration: {n}/30 signals"
- **THEN** a progress bar is shown reflecting `calibration_count / 30`
- **THEN** no metric rows (Hit Ratio, Profit Factor, Realized R/R) are rendered

#### Scenario: Metrics state with 30+ signals
- **WHEN** `phase_gate_active` is `false`
- **THEN** Hit Ratio is displayed as `{hits}/{total} = {hr:.0%}`
- **THEN** Profit Factor is displayed as `${gains:.0f} / ${losses:.0f} = {pf:.2f}`
- **THEN** Realized R/R is displayed as `avg win / avg loss = {rr:.1f}x`

#### Scenario: Hit Ratio green threshold
- **WHEN** `hr_status` is `"green"` (hit_ratio >= 0.35)
- **THEN** Hit Ratio value is rendered with `text-green-400` class

#### Scenario: Hit Ratio red threshold
- **WHEN** `hr_status` is `"red"` (hit_ratio < 0.25)
- **THEN** Hit Ratio value is rendered with `text-red-400` class

#### Scenario: Profit Factor green threshold
- **WHEN** `pf_status` is `"green"` (profit_factor >= 1.3)
- **THEN** Profit Factor value is rendered with `text-green-400` class

#### Scenario: Profit Factor red threshold
- **WHEN** `pf_status` is `"red"` (profit_factor < 1.0)
- **THEN** Profit Factor value is rendered with `text-red-400` class

#### Scenario: Realized R/R green threshold
- **WHEN** `rr_status` is `"green"` (realized_rr >= 2.1)
- **THEN** Realized R/R value is rendered with `text-green-400` class

### Requirement: Break-even warning displayed when HR below threshold
The panel SHALL display a warning message when `below_breakeven` is `true`.

#### Scenario: Warning shown below break-even
- **WHEN** `below_breakeven` is `true` (hit_ratio < 0.25)
- **THEN** the panel displays "Below break-even at R/R 3.0"
- **THEN** the warning is rendered in a visually distinct style (amber/red)

#### Scenario: No warning above break-even
- **WHEN** `below_breakeven` is `false`
- **THEN** no break-even warning is rendered

### Requirement: usePerformance hook fetches and refreshes performance data
The `usePerformance()` hook SHALL fetch `GET /api/analysis/performance` on mount and re-fetch whenever an analysis run transitions from `running` to `done`.

#### Scenario: Initial load on mount
- **WHEN** a component using `usePerformance()` mounts
- **THEN** `GET /api/analysis/performance` is called
- **THEN** `performance` is populated with the API response

#### Scenario: Re-fetch after analysis run completes
- **WHEN** the analysis `status` transitions from `"running"` to `"done"`
- **THEN** `GET /api/analysis/performance` is called again
- **THEN** `performance` is updated with the latest data

#### Scenario: Loading state exposed
- **WHEN** the fetch is in-flight
- **THEN** `isLoading` is `true`
- **THEN** once the response arrives, `isLoading` is `false`

### Requirement: PerformanceSummaryPanel integrated in OpportunitiesPanel
The `PerformanceSummaryPanel` SHALL be rendered inside `OpportunitiesPanel`, below the tab bar and above the signal table, always visible (not collapsible).

#### Scenario: Panel always visible regardless of tab
- **WHEN** either the "Oportunidades" or "Archivo" tab is active
- **THEN** `PerformanceSummaryPanel` is visible above the signal table

#### Scenario: Skeleton shown while loading
- **WHEN** `isLoading` from `usePerformance()` is `true`
- **THEN** a skeleton or spinner placeholder is rendered in place of the panel
