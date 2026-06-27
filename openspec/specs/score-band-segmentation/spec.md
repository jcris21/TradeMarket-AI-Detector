## ADDED Requirements

### Requirement: Score band classification utility
The frontend SHALL expose a `getScoreBand(score)` function that maps a numeric score to one of four bands: `"ELITE"`, `"STRONG"`, `"QUALIFYING"`, or `"NONE"`. Thresholds apply to `score_quant`; when `score_quant` is absent the function SHALL fall back to `score`. When both are null or undefined, the function SHALL return `"NONE"`.

Band thresholds:
- `ELITE`: score ≥ 75 — color `#ECAD0A` (accent-yellow)
- `STRONG`: 60 ≤ score < 75 — color `#209DD7` (accent-blue)
- `QUALIFYING`: 50 ≤ score < 60 — color `#888888` (grey)
- `NONE`: score < 50 or absent — color `#444444`

#### Scenario: Score ≥ 75 classified as ELITE
- **WHEN** `getScoreBand(75)` is called
- **THEN** returns `"ELITE"`

#### Scenario: Score 60–74 classified as STRONG
- **WHEN** `getScoreBand(67)` is called
- **THEN** returns `"STRONG"`

#### Scenario: Score 50–59 classified as QUALIFYING
- **WHEN** `getScoreBand(52)` is called
- **THEN** returns `"QUALIFYING"`

#### Scenario: Score below 50 classified as NONE
- **WHEN** `getScoreBand(48)` is called
- **THEN** returns `"NONE"`

#### Scenario: Null score classified as NONE
- **WHEN** `getScoreBand(null)` is called
- **THEN** returns `"NONE"`

#### Scenario: Falls back to score when score_quant absent
- **WHEN** an AssetAnalysis has score_quant=null and score=80
- **THEN** the band displayed is ELITE

### Requirement: ScoreBandBadge per signal row
The OpportunitiesPanel signal table SHALL render a `ScoreBandBadge` component in each row. The badge SHALL display the band label (`ELITE`, `STRONG`, or `QUALIFYING`) as text with a border matching the band color. When the band is `"NONE"`, no badge SHALL be rendered.

#### Scenario: ELITE badge renders with gold color
- **WHEN** a signal row has score_quant=82
- **THEN** a badge reading "ELITE" with color #ECAD0A border is shown

#### Scenario: STRONG badge renders with blue color
- **WHEN** a signal row has score_quant=65
- **THEN** a badge reading "STRONG" with color #209DD7 border is shown

#### Scenario: QUALIFYING badge renders with grey color
- **WHEN** a signal row has score_quant=54
- **THEN** a badge reading "QUALIFYING" with color #888888 border is shown

#### Scenario: No badge rendered for NONE band
- **WHEN** a signal row has score_quant=45
- **THEN** no ScoreBandBadge is rendered in that row

### Requirement: MiniScoreBar inline with numeric score
Each signal row SHALL display a `MiniScoreBar` component consisting of:
1. The numeric `score_quant` value in the band color
2. A 64px wide, 6px tall horizontal bar where fill width = `score_quant / 100 * 64px`, fill color = band color
3. An optional delta overlay: when `enrichment_delta` is non-zero, an extension or contraction segment in green (#22c55e, positive) or red (#ef4444, negative) starting at the base score position. The delta segment SHALL NOT extend past 100% of bar width.

#### Scenario: Base bar fills proportionally
- **WHEN** score_quant=60 (STRONG)
- **THEN** the base bar fill is 60% width with color #209DD7

#### Scenario: Delta overlay extends bar when enrichment is positive
- **WHEN** score_quant=60 and enrichment_delta=10
- **THEN** a green segment of 10% width appears at position 60%–70% of the bar

#### Scenario: Delta overlay cannot exceed 100% bar width
- **WHEN** score_quant=95 and enrichment_delta=15
- **THEN** the delta segment is capped so combined width does not exceed 100%

#### Scenario: No delta overlay when enrichment_delta is zero or absent
- **WHEN** score_quant=70 and enrichment_delta is null
- **THEN** only the base bar renders, no delta segment

### Requirement: Band dividers between rows on band transition
When rendering the signal table within a page, a visual divider row SHALL be inserted between any two consecutive rows where the band changes (e.g., ELITE → STRONG). The divider SHALL display the name of the new band (lower band) with a horizontal rule in the band color. Dividers SHALL NOT appear before the first row of a page.

#### Scenario: Divider inserted between ELITE and STRONG rows
- **WHEN** row N has band ELITE and row N+1 has band STRONG
- **THEN** a divider row labeled "── STRONG ──────────" appears between them

#### Scenario: No divider at top of page
- **WHEN** the first signal on a page is ELITE
- **THEN** no divider appears above that row

#### Scenario: No divider between same-band consecutive rows
- **WHEN** rows N and N+1 are both STRONG
- **THEN** no divider appears between them

#### Scenario: Divider color matches new band
- **WHEN** a STRONG→QUALIFYING transition occurs
- **THEN** the divider text and rule use color #888888

### Requirement: Band counts in summary line (P1)
The summary line SHALL include band counts after the signal totals in the format: `"Showing N of M signals · ELITE: X · STRONG: Y · QUALIFYING: Z"`. Only bands with count > 0 SHALL appear. Counts SHALL reflect all `displayedSignals` (not just the current page).

#### Scenario: Band counts reflect full signal list
- **WHEN** 20 signals include 3 ELITE, 11 STRONG, 6 QUALIFYING and page 1 is shown
- **THEN** summary shows "ELITE: 3 · STRONG: 11 · QUALIFYING: 6" regardless of current page

#### Scenario: Zero-count bands omitted from summary
- **WHEN** no ELITE signals are present
- **THEN** "ELITE: 0" does not appear in the summary line
