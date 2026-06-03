## Context

`analysis_results` stores `analyzed_at` (ISO UTC string) for every signal row, written at run time. Currently, `GET /api/analysis/latest` returns the raw DB row without any freshness metadata, so the frontend renders all signals with identical visual weight regardless of age. Traders have no indication of whether a signal is 20 minutes old or 20 hours old.

The change is purely additive: no schema migration, no new tables, no background jobs.

## Goals / Non-Goals

**Goals:**
- Compute `freshness_status` and `freshness_age_hours` in the API layer at read time and include them in every analysis result payload.
- Render a color-coded `FreshnessBadge` per row in `OpportunitiesPanel` with a tooltip explaining each state.
- Dim the `score` cell for `aged` and `expired` signals to reduce visual salience.
- Separate expired signals into a dedicated "Archivo" tab so the default view only shows actionable signals.

**Non-Goals:**
- Persisting freshness state (it is always derived, never stored).
- Server-push freshness updates via SSE (polling-on-render is sufficient).
- Changing the analysis run schedule or signal generation logic.
- Supporting configurable thresholds via UI or env vars (constants in code are sufficient for MVP).

## Decisions

### D1 — Compute freshness in the repository layer, not in the route

**Decision**: Add `compute_freshness()` to `backend/app/db/repository.py` and call it from `_parse_analysis_row()`.

**Rationale**: `_parse_analysis_row()` is the single place where every DB row is deserialized. Injecting freshness there ensures it is available on all read paths (`get_latest_analysis`, `get_analysis_by_ticker`) without touching route handlers. Route handlers remain thin.

**Alternative considered**: Compute in the route handler. Rejected because it requires duplicating logic across two route functions and breaks the "repository owns row shape" invariant.

### D2 — Four discrete states with fixed UTC thresholds

**Decision**:
```
age_hours < 2    → fresh
2 ≤ age_hours < 5  → active
5 ≤ age_hours < 24 → aged
age_hours ≥ 24   → expired
```

**Rationale**: The thresholds align with typical intraday trading windows (2 h for optimal entry, 5 h for caution, 24 h for discard). They are expressed as UTC-based elapsed hours to avoid DST edge cases and calendar arithmetic.

**Alternative considered**: "Same calendar day vs. previous day" for the expired boundary. Rejected because it is timezone-dependent and behaves inconsistently for sessions that cross midnight.

### D3 — Filter expired signals on the frontend, not via a new API parameter

**Decision**: `GET /api/analysis/latest` always returns all results including expired ones. The frontend filters them into the archive tab.

**Rationale**: The API payload is small (≤ 20 rows). Adding a query parameter (`?include_expired=false`) adds surface area with no performance benefit. The frontend already holds the full result set in `useAnalysis()`; client-side filtering is O(n) with negligible cost.

**Alternative considered**: Add `?status=active` query filter to the endpoint. Rejected for now — keep the API surface minimal.

### D4 — `FreshnessBadge` as a standalone component

**Decision**: Extract badge rendering into `frontend/components/FreshnessBadge.tsx`.

**Rationale**: The badge needs four rendering variants, a tooltip, and two unit test surface areas (badge color + score dimming). A standalone component isolates this complexity from `OpportunitiesPanel` and makes it independently testable.

## Risks / Trade-offs

- **Clock skew between container and client** → Freshness is computed server-side at the moment of the GET request, so the displayed age is the server's view. Acceptable: single-container deployment means server and client are on the same host.
- **Stale freshness after page load** → The badge reflects the age at the time the user loaded/refreshed the panel, not a live counter. Mitigation: `useAnalysis()` re-fetches on manual "Analizar" trigger; badge updates on re-fetch. A live countdown is out of scope for MVP.
- **Threshold constants in code** → Changing the window sizes requires a code change. Acceptable for MVP; can be moved to env vars if product requirements change.
