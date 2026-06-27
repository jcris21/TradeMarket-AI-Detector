## ADDED Requirements

### Requirement: Panel collapse toggle via header click
The OpportunitiesPanel header SHALL function as a clickable toggle that collapses or expands the panel body. The header itself SHALL always remain visible. A chevron icon (`▶` collapsed, `▼` expanded) SHALL appear in the header label. Clicking anywhere in the header area (except the Analizar button) SHALL toggle collapsed state. The Analizar button SHALL stop click propagation so it does not trigger collapse.

#### Scenario: Click on header collapses expanded panel
- **WHEN** the panel is expanded and the user clicks the header
- **THEN** the panel body animates to hidden (maxHeight 0px) and chevron changes to ▶

#### Scenario: Click on header expands collapsed panel
- **WHEN** the panel is collapsed and the user clicks the header
- **THEN** the panel body animates to visible and chevron changes to ▼

#### Scenario: Clicking Analizar button does not toggle collapse
- **WHEN** the user clicks the Analizar button while the panel is expanded
- **THEN** analysis starts and the panel remains expanded

#### Scenario: aria-expanded reflects collapse state
- **WHEN** the panel is collapsed
- **THEN** the header element has aria-expanded="false"

### Requirement: Collapsed state persisted in localStorage
The `collapsed` state SHALL be initialised from `localStorage.getItem("finally_top_opps_collapsed")` on mount. On each toggle, the new value SHALL be written to `localStorage`. Access to `localStorage` SHALL be gated behind `typeof window !== "undefined"` for SSR safety.

#### Scenario: Collapsed state survives page reload
- **WHEN** the user collapses the panel and reloads the page
- **THEN** the panel re-opens in collapsed state

#### Scenario: Expanded state survives page reload
- **WHEN** the user expands the panel and reloads the page
- **THEN** the panel re-opens in expanded state

#### Scenario: No localStorage key defaults to expanded
- **WHEN** no "finally_top_opps_collapsed" key exists in localStorage
- **THEN** the panel renders expanded

### Requirement: Collapse animation via CSS max-height transition
The panel body wrapper SHALL apply `overflow-hidden` and `transition-all duration-200 ease-out`. It SHALL use `maxHeight: "0px"` when collapsed and `maxHeight: "2000px"` when expanded. No JavaScript animation frame or ResizeObserver is required.

#### Scenario: Body invisible while collapsed
- **WHEN** collapsed is true
- **THEN** the body div's maxHeight is "0px" and overflow is hidden, making content invisible

#### Scenario: Body visible while expanded
- **WHEN** collapsed is false
- **THEN** the body div's maxHeight is "2000px" and content is visible

### Requirement: Collapsed badge shows signal count
When the panel is collapsed, the header SHALL display a signal count badge in the format `[N]` beside the title, where N is the count of currently displayed signals. The badge SHALL update when a new run completes, without requiring expansion.

#### Scenario: Count badge visible when collapsed
- **WHEN** 15 signals are loaded and panel is collapsed
- **THEN** the header shows "[15]" beside the title

#### Scenario: Count badge absent when expanded
- **WHEN** the panel is expanded
- **THEN** no "[N]" count badge appears in the header

#### Scenario: Count badge updates on new run without expansion
- **WHEN** panel is collapsed, a new run completes returning 18 signals
- **THEN** the header badge updates to "[18]" without expanding the panel

### Requirement: Auto-expand on new run completion (unless manually collapsed during run)
When a new analysis run completes, the panel SHALL auto-expand if and only if the panel was in expanded state when the run began. If the user manually collapsed the panel during the run, the panel SHALL remain collapsed on completion.

#### Scenario: Panel auto-expands when it was expanded at run start
- **WHEN** the panel is expanded when Analizar is clicked and the run completes
- **THEN** the panel expands (or remains expanded) and an inline banner appears

#### Scenario: Panel stays collapsed when manually collapsed during run
- **WHEN** the user collapses the panel while a run is in progress and the run completes
- **THEN** the panel remains collapsed and no auto-expand occurs

### Requirement: Inline status banner on run completion
On new run completion, an inline banner SHALL appear inside the panel header for 5 seconds displaying the format `"Analysis complete — N new signals available"`. After 5 seconds, the banner SHALL disappear. The banner SHALL only show when the panel is expanded.

#### Scenario: Banner appears on run completion
- **WHEN** a run completes and panel is expanded
- **THEN** a banner with the new signal count appears in the header

#### Scenario: Banner disappears after 5 seconds
- **WHEN** the banner appears
- **THEN** it is removed from DOM after approximately 5000ms

#### Scenario: Banner does not appear when panel is collapsed
- **WHEN** a run completes and the panel is collapsed
- **THEN** no banner is shown

### Requirement: Regime gate badge in header (P1)
When `regime_gate_active: true` is returned in the analysis response, the panel header SHALL display an amber badge reading `"⚠ Regime gate active"` in place of or beside the signal count. The badge color SHALL be `#C47A00`.

#### Scenario: Regime gate badge shown when active
- **WHEN** analysis response includes regime_gate_active=true
- **THEN** the header shows the amber "⚠ Regime gate active" badge

#### Scenario: Regime gate badge absent when not active
- **WHEN** regime_gate_active is false or absent
- **THEN** no regime gate badge is shown

### Requirement: Shift+O keyboard shortcut to toggle collapse (P1)
Pressing `Shift+O` globally SHALL toggle the panel's collapsed state, equivalent to clicking the header.

#### Scenario: Shift+O expands collapsed panel
- **WHEN** panel is collapsed and user presses Shift+O
- **THEN** panel expands

#### Scenario: Shift+O collapses expanded panel
- **WHEN** panel is expanded and user presses Shift+O
- **THEN** panel collapses
