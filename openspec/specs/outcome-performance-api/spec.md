# Spec: outcome-performance-api

## Purpose

The `outcome-performance-api` capability exposes aggregated outcome metrics from `analysis_results` via a REST endpoint, allowing the frontend and consumers to retrieve a performance summary (hit ratio, profit factor, counts) in a single call.

---

## Requirements

### Requirement: GET /api/analysis/performance returns aggregated outcome metrics
The system SHALL expose a `GET /api/analysis/performance` endpoint that returns a `PerformanceResponse` JSON object aggregating all resolved signal outcomes from `analysis_results`. The response SHALL include phase gate state, calibration count, realized R/R, and color-status fields in addition to the existing counts.

#### Scenario: Endpoint returns correct outcome counts
- **WHEN** `GET /api/analysis/performance` is called
- **THEN** the response contains `total_signals`, `target_hits`, `stop_hits`, `expired`, `orphaned_count`, `hit_ratio`, `profit_factor`, `phase_gate_active`, `calibration_count`, `realized_rr`, `hr_status`, `pf_status`, `rr_status`, `below_breakeven`
- **THEN** HTTP status is 200

#### Scenario: hit_ratio excludes EXPIRED from denominator
- **WHEN** `analysis_results` contains 3 TARGET_HIT, 1 STOP_HIT, and 2 EXPIRED rows
- **THEN** `hit_ratio` is `3 / (3 + 1) = 0.75`
- **THEN** EXPIRED rows do NOT appear in the denominator

#### Scenario: profit_factor is 999.0 sentinel when total losses are zero
- **WHEN** all resolved signals are TARGET_HIT (no STOP_HIT rows)
- **THEN** `profit_factor` is `999.0` (not `null` or infinity)

#### Scenario: Empty analysis_results returns zero summary
- **WHEN** no rows exist in `analysis_results`
- **THEN** all counts are `0`, `hit_ratio` is `null`, `profit_factor` is `null`, `phase_gate_active` is `true`, `calibration_count` is `0`

#### Scenario: Phase gate active below 30 conclusive signals
- **WHEN** `target_hits + stop_hits < 30`
- **THEN** `phase_gate_active` is `true`
- **THEN** `hit_ratio`, `profit_factor`, `realized_rr`, `hr_status`, `pf_status`, `rr_status` are all `null`
- **THEN** `below_breakeven` is `false`

#### Scenario: Phase gate inactive at 30+ conclusive signals
- **WHEN** `target_hits + stop_hits >= 30`
- **THEN** `phase_gate_active` is `false`
- **THEN** all metric fields are computed and non-null

#### Scenario: realized_rr computed from average gain and average loss
- **WHEN** `target_hits > 0` and `stop_hits > 0`
- **THEN** `realized_rr = round(total_gain / target_hits / (total_loss / stop_hits), 2)`

#### Scenario: below_breakeven set when HR below 25%
- **WHEN** `hit_ratio < 0.25` and `phase_gate_active` is `false`
- **THEN** `below_breakeven` is `true`

#### Scenario: hr_status reflects threshold bands
- **WHEN** `hit_ratio >= 0.35`
- **THEN** `hr_status` is `"green"`
- **WHEN** `hit_ratio < 0.25`
- **THEN** `hr_status` is `"red"`
- **WHEN** `0.25 <= hit_ratio < 0.35`
- **THEN** `hr_status` is `"neutral"`

### Requirement: orphaned_count reflects signals unresolved after 35 days
The `GET /api/analysis/performance` response SHALL include an `orphaned_count` field equal to the number of rows where `outcome IS NULL` and more than 35 calendar days have elapsed since `analyzed_at`.

#### Scenario: Orphaned count increments when threshold crossed
- **WHEN** a signal row has `outcome IS NULL` and `analyzed_at` is 36+ days ago
- **THEN** `orphaned_count` includes that row

#### Scenario: Recently unresolved signals not counted as orphaned
- **WHEN** a signal row has `outcome IS NULL` and `analyzed_at` is 10 days ago
- **THEN** `orphaned_count` does NOT include that row

### Requirement: Performance summary index for query performance
The system SHALL maintain an index on `analysis_results(outcome)` to keep the summary aggregation fast as the table grows.

#### Scenario: Index present in schema
- **WHEN** the database is initialized
- **THEN** `CREATE INDEX IF NOT EXISTS idx_analysis_outcome ON analysis_results(outcome)` exists

### Requirement: _get_hit_rate reads from analysis_results
The `scoring_agent._get_hit_rate()` function SHALL query `analysis_results` for conclusive outcomes and return the observed hit rate when 30+ conclusive signals exist, falling back to `0.35, "assumed"` otherwise.

#### Scenario: Returns observed rate at 30+ conclusive signals
- **WHEN** `analysis_results` contains >= 30 rows with `outcome IN ('TARGET_HIT', 'STOP_HIT')`
- **THEN** `_get_hit_rate()` returns `(hits / conclusive, "observed")`

#### Scenario: Falls back to assumed rate below 30 signals
- **WHEN** `analysis_results` contains fewer than 30 conclusive rows
- **THEN** `_get_hit_rate()` returns `(0.35, "assumed")`

#### Scenario: EV badge source transitions at signal 30
- **WHEN** the 30th conclusive signal is recorded
- **THEN** subsequent analysis runs produce `hit_rate_source = "observed"` in `analysis_results`

### Requirement: PerformanceResponse Pydantic model on the route
The `GET /api/analysis/performance` route SHALL declare `response_model=PerformanceResponse`, where `PerformanceResponse` is a Pydantic model with all fields explicitly typed (including `float | None` for nullable metrics).

#### Scenario: Response schema enforced by Pydantic
- **WHEN** `get_performance_summary()` returns a dict with all required keys
- **THEN** FastAPI serializes the response using `PerformanceResponse` field definitions
- **THEN** missing optional fields default to `null` in the JSON response

### Requirement: GET /api/analysis/performance returns B2-segmented outcome blocks
When at least 30 signals with `enrichment_type = "auto_screenshot"` have resolved outcomes (`target_hits + stop_hits >= 30` within that segment), the response SHALL include a `b2_enriched` object with `total`, `hit_ratio`, `profit_factor`, `realized_rr`. When at least 30 signals with `enrichment_type IS NULL OR enrichment_type != "auto_screenshot"` have resolved outcomes, the response SHALL include a `non_enriched` object with the same structure. Each block is independently gated by its own 30-signal minimum; a block is `null` when its segment has fewer than 30 resolved signals.

#### Scenario: B2 segment not yet at 30 signals
- **WHEN** fewer than 30 signals have `enrichment_type="auto_screenshot"` with resolved outcomes
- **THEN** `b2_enriched` is `null` in the response

#### Scenario: B2 segment has 30+ resolved signals
- **WHEN** 32 signals with `enrichment_type="auto_screenshot"` have resolved outcomes
- **THEN** `b2_enriched` is non-null with `total=32`, `hit_ratio`, `profit_factor`, `realized_rr` computed from those rows only

#### Scenario: non_enriched segment has 30+ resolved signals
- **WHEN** 35 signals with `enrichment_type IS NULL` have resolved outcomes
- **THEN** `non_enriched` is non-null with `total=35` and metrics computed from unenriched rows only

#### Scenario: both segments present simultaneously
- **WHEN** both B2 and non-enriched segments each have 30+ resolved outcomes
- **THEN** response includes both `b2_enriched` and `non_enriched` as non-null objects

#### Scenario: segment metrics follow same formula as top-level
- **WHEN** B2 segment has 20 TARGET_HIT and 10 STOP_HIT
- **THEN** `b2_enriched.hit_ratio = 0.67` (20 / 30), `b2_enriched.total = 30`

#### Scenario: B2 profit_factor sentinel when no stop hits in segment
- **WHEN** B2 segment has TARGET_HIT rows only
- **THEN** `b2_enriched.profit_factor = 999.0`

### Requirement: PerformanceResponse includes optional b2_enriched and non_enriched fields
The `PerformanceResponse` Pydantic model SHALL include two optional fields: `b2_enriched: Optional[SegmentPerformance] = None` and `non_enriched: Optional[SegmentPerformance] = None`. A new `SegmentPerformance` model SHALL be defined with `total: int`, `hit_ratio: Optional[float]`, `profit_factor: Optional[float]`, `realized_rr: Optional[float]`.

#### Scenario: PerformanceResponse serializes segment blocks
- **WHEN** `b2_enriched` is populated and response is serialized to JSON
- **THEN** JSON includes `"b2_enriched": {"total": 32, "hit_ratio": 0.72, "profit_factor": 2.1, "realized_rr": 1.8}`

#### Scenario: PerformanceResponse omits null segment blocks cleanly
- **WHEN** `b2_enriched` is `None`
- **THEN** JSON response includes `"b2_enriched": null` (field present, value null — not omitted)
