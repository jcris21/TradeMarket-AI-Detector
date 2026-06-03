## 1. Backend — Freshness Helper

- [x] 1.1 Add `FRESHNESS_THRESHOLDS` constant dict and `compute_freshness(analyzed_at: str) -> dict` pure function to `backend/app/db/repository.py`
- [x] 1.2 Update `_parse_analysis_row()` in `backend/app/db/repository.py` to call `compute_freshness()` and merge `freshness_status` + `freshness_age_hours` into the returned dict when `analyzed_at` is present
- [x] 1.3 Write `backend/tests/test_freshness.py` with 8 parametrized pytest cases covering all 4 states and both threshold boundaries (2h, 5h, 24h)
- [x] 1.4 Run `uv run --extra dev pytest backend/tests/test_freshness.py -v` and confirm all 8 cases pass

## 2. Backend — API Verification

- [x] 2.1 Manually verify `GET /api/analysis/latest` response includes `freshness_status` and `freshness_age_hours` per result row (run a fresh analysis if needed via `POST /api/analysis/run`)
- [x] 2.2 Update `docs/api-spec.yml` to document `freshness_status` (enum: fresh/active/aged/expired) and `freshness_age_hours` (number) fields in the `/api/analysis/latest` response schema

## 3. Frontend — Types

- [x] 3.1 Add `FreshnessStatus = "fresh" | "active" | "aged" | "expired"` type alias to `frontend/lib/types.ts`
- [x] 3.2 Add optional `freshness_status?: FreshnessStatus` and `freshness_age_hours?: number` fields to the `AssetAnalysis` interface in `frontend/lib/types.ts`

## 4. Frontend — FreshnessBadge Component

- [x] 4.1 Create `frontend/components/FreshnessBadge.tsx` — renders icon, label, age label (`formatAge()`), color classes, and `title` tooltip per state (4 variants: fresh/active/aged/expired)
- [x] 4.2 Implement `formatAge(hours: number): string` helper in the same file: 1 decimal when `hours < 10`, integer otherwise
- [x] 4.3 Write `frontend/__tests__/FreshnessBadge.test.tsx` with 4 tests (one per state) asserting: icon, age label format, `title` tooltip text, and `opacity-40` class presence for aged/expired
- [x] 4.4 Run `npm test -- FreshnessBadge` and confirm all 4 tests pass

## 5. Frontend — OpportunitiesPanel Updates

- [x] 5.1 Add "Freshness" column header to the signal table in `frontend/components/OpportunitiesPanel.tsx`
- [x] 5.2 Render `<FreshnessBadge>` in each signal row cell when `freshness_status` is present; render `—` otherwise
- [x] 5.3 Apply `opacity-40` class to the score `<td>` when `freshness_status` is `"aged"` or `"expired"`
- [x] 5.4 Add tab state (`"active" | "archive"`) to the component; render two tab buttons ("Oportunidades" / "Archivo") styled with `border-b-2 border-accent-yellow` for the active tab
- [x] 5.5 Derive `activeSignals` and `archivedSignals` arrays by filtering `results` on `freshness_status !== "expired"` and `=== "expired"` respectively
- [x] 5.6 Render the signal table using `activeSignals` when tab is `"active"` and `archivedSignals` when tab is `"archive"`; show an empty-state message when the archive list is empty

## 6. Quality Gate

- [x] 6.1 Run `uv run --extra dev ruff check backend/app/db/repository.py backend/tests/test_freshness.py` — zero errors
- [x] 6.2 Run `npm run --prefix frontend type-check` (or `tsc --noEmit`) — zero new TypeScript errors (3 pre-existing errors in OpportunitiesPanel.test.tsx unrelated to this change)
- [x] 6.3 Run full backend test suite `uv run --extra dev pytest -v` — all tests pass (36 passed)
- [x] 6.4 Run full frontend test suite `npm test --prefix frontend` — all tests pass (45 passed)
- [x] 6.5 Start the app locally and verify visually: Freshness column visible, score dimmed for aged/expired rows, Archivo tab shows only expired signals
