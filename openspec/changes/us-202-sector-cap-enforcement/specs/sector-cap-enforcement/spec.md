## ADDED Requirements

### Requirement: ScoringAgent enforces configurable per-sector cap on ranked results
After sorting qualifying assets by `score_quant` descending, `ScoringAgent` SHALL apply a greedy sector cap before the `[:top_n]` slice. Assets whose sector has already filled the cap SHALL receive `rank=None` and `rank_exclusion_reason="sector_cap:<sector>"`. The cap limit SHALL be read from `ANALYSIS_SECTOR_CAP` env var (int, clamped to [1, 5], default 2). Sectors `"unknown"` and `"etf"` SHALL bypass the cap entirely.

#### Scenario: Sector exceeds cap
- **WHEN** 5 qualifying assets all have `sector="Technology"` and `ANALYSIS_SECTOR_CAP=2`
- **THEN** exactly 2 assets receive rank assignments and the remaining 3 have `rank=None` with `rank_exclusion_reason="sector_cap:Technology"`

#### Scenario: Unknown sector bypasses cap
- **WHEN** 5 qualifying assets all have `sector="unknown"` and `ANALYSIS_SECTOR_CAP=2`
- **THEN** all 5 assets receive rank assignments (no cap applied)

#### Scenario: ETF sector bypasses cap
- **WHEN** 3 qualifying assets have `sector="etf"` and `ANALYSIS_SECTOR_CAP=2`
- **THEN** all 3 assets receive rank assignments

#### Scenario: Mixed sectors respect cap independently per sector
- **WHEN** qualifying assets include 3 Technology, 2 Financials, and 1 Energy, with `ANALYSIS_SECTOR_CAP=2`
- **THEN** 2 Technology + 2 Financials + 1 Energy are accepted (5 total); 1 Technology receives `rank=None`

#### Scenario: Greedy walk preserves score order within sector
- **WHEN** a higher-scoring Technology asset and a lower-scoring Technology asset are both qualifying, and cap=1
- **THEN** the higher-scoring asset receives a rank and the lower-scoring one is excluded

### Requirement: ANALYSIS_SECTOR_CAP env var with safe clamping
`ScoringAgent` SHALL read `ANALYSIS_SECTOR_CAP` at call time (not module load). Invalid values (non-integer, below 1, above 5) SHALL be silently clamped or defaulted without raising an exception.

#### Scenario: Cap value below minimum is clamped
- **WHEN** `ANALYSIS_SECTOR_CAP=0`
- **THEN** effective cap is 1

#### Scenario: Cap value above maximum is clamped
- **WHEN** `ANALYSIS_SECTOR_CAP=10`
- **THEN** effective cap is 5

#### Scenario: Non-integer value falls back to default
- **WHEN** `ANALYSIS_SECTOR_CAP=two`
- **THEN** effective cap is 2 (default) and no exception is raised

#### Scenario: Env var absent uses default
- **WHEN** `ANALYSIS_SECTOR_CAP` is not set
- **THEN** effective cap is 2

### Requirement: sector_cap_exclusions surfaced in AnalysisResult and logs
`AnalysisResult` SHALL include `sector_cap_exclusions: dict[str, int]` (sector → number of excluded assets). This field SHALL be populated from the return value of `_apply_sector_cap()` and included in the Stage 4 `stage_complete` log entry.

#### Scenario: Exclusion counts per sector
- **WHEN** 3 Technology assets and 2 Financials assets are sector-capped
- **THEN** `sector_cap_exclusions == {"Technology": 3, "Financials": 2}`

#### Scenario: No exclusions yields empty dict
- **WHEN** no assets are excluded by the sector cap
- **THEN** `sector_cap_exclusions == {}`

### Requirement: ETFs added to seed_tickers with sector="etf"
`seed_tickers.py` SHALL include entries for SPY, QQQ, IWM, GLD, and TLT with `sector="etf"`. These entries SHALL be present after a fresh DB seed.

#### Scenario: ETF tickers seeded
- **WHEN** the database is seeded from `seed_tickers.py`
- **THEN** tickers SPY, QQQ, IWM, GLD, TLT exist in `analysis_tickers` with `sector="etf"`
