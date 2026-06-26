## ADDED Requirements

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
