## Why

Traders checking the dashboard hours after a signal run cannot tell which signals are still actionable. `analyzed_at` is already persisted in `analysis_results`, but the UI presents every signal with equal visual weight regardless of age, creating risk of acting on stale data.

## What Changes

- A `compute_freshness()` helper is added to the repository layer that derives a `freshness_status` (`fresh` / `active` / `aged` / `expired`) and `freshness_age_hours` float from `analyzed_at` at read time — zero schema migration.
- `_parse_analysis_row()` is updated to inject both fields into every analysis result row returned by the DB layer.
- `GET /api/analysis/latest` and `GET /api/analysis/{ticker}` automatically include the new fields (no route changes needed).
- A `FreshnessBadge` React component renders a color-coded badge + age label with a tooltip per state.
- `OpportunitiesPanel` gains a Freshness column, dims the score cell for `aged`/`expired` signals, and splits into two tabs: **Oportunidades** (active signals) and **Archivo** (expired signals).

## Capabilities

### New Capabilities

- `signal-freshness`: Per-signal freshness computation (backend helper + API field injection) and visual freshness indicator (badge, score dimming, archive tab) on the OpportunitiesPanel.

### Modified Capabilities

<!-- No existing spec-level behavior changes — this is additive only. -->

## Impact

- **Backend**: `backend/app/db/repository.py` — new `compute_freshness()` helper + updated `_parse_analysis_row()`.
- **API response shape**: `GET /api/analysis/latest` and `GET /api/analysis/{ticker}` gain `freshness_status` and `freshness_age_hours` fields (non-breaking, additive).
- **Frontend**: `frontend/lib/types.ts` (extend `AssetAnalysis`), new `frontend/components/FreshnessBadge.tsx`, updated `frontend/components/OpportunitiesPanel.tsx`.
- **No schema migration**: `analyzed_at` already exists in `analysis_results`.
- **No new dependencies**.
