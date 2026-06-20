## ADDED Requirements

### Requirement: AssetAnalysis carries rank_exclusion_reason (runtime-only)
The `AssetAnalysis` Pydantic model SHALL include `rank_exclusion_reason: str | None = None`. This field is runtime-only and SHALL NOT be persisted by `to_db_row()`. It SHALL be set to `"sector_cap:<sector>"` for sector-capped assets.

#### Scenario: Sector-capped asset has reason set
- **WHEN** an asset is excluded by the sector cap with `sector="Technology"`
- **THEN** `asset.rank_exclusion_reason == "sector_cap:Technology"`

#### Scenario: Non-excluded asset has reason None
- **WHEN** an asset is ranked normally
- **THEN** `asset.rank_exclusion_reason is None`

### Requirement: score_and_rank_with_errors returns 3-tuple
`score_and_rank_with_errors()` SHALL return `(ranked_all: list[AssetAnalysis], structural_errors: list[dict[str, str]], sector_cap_exclusions: dict[str, int])`. The public `score_and_rank()` wrapper SHALL unpack the 3-tuple and discard `sector_cap_exclusions`, preserving its existing call signature.

#### Scenario: Wrapper preserves backward compatibility
- **WHEN** `score_and_rank()` is called
- **THEN** it returns `(ranked_all, structural_errors)` unchanged and does not raise

#### Scenario: Direct caller receives all three values
- **WHEN** `score_and_rank_with_errors()` is called with qualifying assets
- **THEN** the return value unpacks as `(ranked, errors, exclusions)` where `exclusions` is a dict
