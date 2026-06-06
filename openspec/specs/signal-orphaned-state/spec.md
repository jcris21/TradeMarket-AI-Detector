# Spec: signal-orphaned-state

## Purpose

The `signal-orphaned-state` capability defines the visual treatment for signals that have remained unresolved for an extended period. An amber "Orphaned" badge is shown in the `OpportunitiesPanel` to flag signals requiring manual review, without blocking normal signal interactions.

---

## Requirements

### Requirement: Orphaned signals displayed with amber badge in OpportunitiesPanel
The `OpportunitiesPanel` component SHALL display an amber `⚠ Orphaned` badge on any signal row where the signal has been unresolved (`outcome IS NULL`) for more than 35 calendar days, derived from the `analyzed_at` timestamp.

#### Scenario: Badge renders for signal older than 35 days with no outcome
- **WHEN** `OpportunitiesPanel` receives a signal row with `outcome: null` and `analyzed_at` more than 35 days ago
- **THEN** an amber badge with text `⚠ Orphaned` is rendered on that row
- **THEN** the badge has a tooltip with text `"No outcome detected after 35 trading days — review manually"`

#### Scenario: Badge does not render for recently unresolved signal
- **WHEN** `OpportunitiesPanel` receives a signal row with `outcome: null` and `analyzed_at` 10 days ago
- **THEN** no Orphaned badge is rendered

#### Scenario: Badge does not render for resolved signal
- **WHEN** `OpportunitiesPanel` receives a signal row with `outcome: 'TARGET_HIT'`
- **THEN** no Orphaned badge is rendered regardless of `analyzed_at` age

#### Scenario: Badge renders consistently after page refresh
- **WHEN** the user refreshes the page
- **THEN** Orphaned badges for eligible rows are visible without any user interaction

### Requirement: Orphaned state does not block other signal interactions
Rows displaying the Orphaned badge SHALL remain fully interactive (clickable, expandable) and SHALL NOT show an error state — only a diagnostic warning.

#### Scenario: Orphaned row is still clickable
- **WHEN** a row has the Orphaned badge
- **THEN** clicking the row opens the signal detail as normal
- **THEN** no error state or disabled styling is applied to the row
