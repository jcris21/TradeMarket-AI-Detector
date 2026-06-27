## ADDED Requirements

### Requirement: Per-row inline freshness dot and live age label
The OpportunitiesPanel signal table SHALL display a colored dot and a relative age string (e.g., `"2h 14m ago"`) in each signal row. The age string SHALL update every 60 seconds via a `setInterval` (cleaned up on unmount). The dot color SHALL map from `freshness_status`:
- `"fresh"`: `#22c55e` (green)
- `"active"`: `#F59E0B` (amber)
- `"aged"`: `#ef4444` (red)
- `"stale"`: `#ef4444` (red, treated same as aged for display)
- `"expired"`: `#6B7280` (grey)

Age string format:
- Under 60 minutes: `"Xm ago"`
- 60+ minutes: `"Xh Ym ago"` (omit minutes part if exactly 0 minutes)

When `freshness_status` is absent from a row, the dot and age label SHALL be omitted and no error SHALL occur.

#### Scenario: Fresh signal shows green dot and age
- **WHEN** a signal has freshness_status="fresh" and analyzed_at was 90 minutes ago
- **THEN** a green dot (#22c55e) and "1h 30m ago" label appear in the row

#### Scenario: Age label shows only hours when minutes are zero
- **WHEN** analyzed_at was exactly 2 hours ago
- **THEN** label reads "2h ago" (not "2h 0m ago")

#### Scenario: Aged/stale signal shows red dot
- **WHEN** freshness_status is "aged" or "stale"
- **THEN** dot color is #ef4444

#### Scenario: Expired signal shows grey dot
- **WHEN** freshness_status is "expired"
- **THEN** dot color is #6B7280

#### Scenario: Age label updates every 60 seconds
- **WHEN** 60 seconds elapse after the component mounts
- **THEN** the age labels re-render with updated elapsed time

#### Scenario: Row without freshness_status renders without crash
- **WHEN** an AssetAnalysis row has no freshness_status field
- **THEN** no dot or age label is rendered and no console error occurs

#### Scenario: setInterval is cleaned up on unmount
- **WHEN** the OpportunitiesPanel unmounts
- **THEN** the 60-second interval is cleared to prevent memory leaks

### Requirement: Expired row visual treatment in archive tab
In the Signal Archive tab (rows with `freshness_status === "expired"`), each row SHALL be displayed at 40% opacity, the ticker text SHALL have line-through decoration, and the score band badge position SHALL show an `EXPIRED` badge (grey `#6B7280` border and text) instead of the standard `ScoreBandBadge`.

#### Scenario: Expired row rendered at 40% opacity
- **WHEN** an expired signal is rendered in the archive tab
- **THEN** the row element has opacity: 0.4 applied

#### Scenario: Expired row ticker has strikethrough
- **WHEN** an expired signal is rendered in the archive tab
- **THEN** the ticker text cell has text-decoration: line-through

#### Scenario: EXPIRED badge replaces score band badge
- **WHEN** an expired signal is rendered in the archive tab
- **THEN** an "EXPIRED" badge with grey #6B7280 styling appears; no ScoreBandBadge is shown

#### Scenario: Non-expired rows in active tab are unaffected
- **WHEN** a fresh or aged signal is rendered in the Oportunidades tab
- **THEN** opacity is 1.0 and no strikethrough or EXPIRED badge appears

### Requirement: ScoreQuantDelta component for prior-run comparison (P1)
Each signal row SHALL display a `ScoreQuantDelta` component comparing the current `score_quant` to `prior_score_quant` from the previous run. Display rules:
- `prior_score_quant` is absent: render nothing
- `|delta| ≤ 3`: render `=` in grey (#6B7280) — dead-zone for floating-point noise
- `delta > 3`: render `▲ +N` in green (#22c55e) where N = `Math.round(delta)`
- `delta < -3`: render `▼ -N` in red (#ef4444) where N = `Math.round(|delta|)`

#### Scenario: No delta component when prior_score_quant is absent
- **WHEN** an AssetAnalysis has no prior_score_quant
- **THEN** no delta indicator is rendered in the row

#### Scenario: Equal indicator when delta is within dead-zone
- **WHEN** score_quant=65 and prior_score_quant=63 (delta=2)
- **THEN** renders "=" in grey

#### Scenario: Up arrow with positive delta above dead-zone
- **WHEN** score_quant=72 and prior_score_quant=65 (delta=7)
- **THEN** renders "▲ +7" in green

#### Scenario: Down arrow with negative delta above dead-zone
- **WHEN** score_quant=60 and prior_score_quant=66 (delta=-6)
- **THEN** renders "▼ -6" in red

#### Scenario: Delta at exactly ±3 uses dead-zone
- **WHEN** delta is exactly 3 or -3
- **THEN** renders "=" in grey (not an arrow)
