## 1. API Client

- [x] 1.1 Add `TraderChartEnrichResponse` type to `frontend/lib/types.ts`: `{ enrichment_id: string; extracted_levels: ExtractedLevel[]; status: string }`
- [x] 1.2 Add `ExtractedLevel` type to `frontend/lib/types.ts`: `{ type: "support" | "resistance"; price: number; confidence: number }`
- [x] 1.3 Add `LevelConfirmResult` type to `frontend/lib/types.ts`: `{ custom_levels_applied: number; enrichment_delta: number; score_quant: number; score_enriched: number }`
- [x] 1.4 Add `enrichTraderChart(ticker: string, chartImageB64: string): Promise<TraderChartEnrichResponse>` to `frontend/lib/api.ts` — POSTs `{ enrichment_type: "trader_chart", chart_image: chartImageB64 }` to `/api/analysis/enrich/{ticker}`
- [x] 1.5 Add `confirmLevels(ticker: string, enrichmentId: string, confirmedIndices: number[]): Promise<LevelConfirmResult>` to `frontend/lib/api.ts` — POSTs `{ enrichment_id, confirmed_indices }` to `/api/analysis/enrich/{ticker}/confirm`

## 2. TraderChartUpload Component

- [x] 2.1 Create `frontend/components/TraderChartUpload.tsx` accepting props `{ ticker: string; onConfirmed: (result: LevelConfirmResult) => void }`
- [x] 2.2 Implement client-side file validation in `TraderChartUpload`: reject files > 10 MB with error "File must be under 10 MB"; reject non-PNG/JPEG with error "Only PNG and JPEG images are supported"; show error inline, make no API call
- [x] 2.3 Implement base64 encoding via `FileReader.readAsDataURL()`, strip `data:<mime>;base64,` prefix before use
- [x] 2.4 Implement extraction phase in `TraderChartUpload`: on valid file selected, call `enrichTraderChart()`; show spinner with label "Extracting levels…" and disable the upload button while in flight
- [x] 2.5 Handle extraction success with non-empty levels: clear loading state, render level review UI (task 3)
- [x] 2.6 Handle extraction success with empty levels (`extracted_levels: []`): show "No levels detected in this chart. Try a clearer image." with a "Re-upload" link that resets state to initial
- [x] 2.7 Handle API 400 error: show the server error message inline
- [x] 2.8 Handle network error during extraction: show "Could not reach server. Please try again." inline

## 3. Level Review UI (inside TraderChartUpload)

- [x] 3.1 Render each extracted level as a row: checkbox, type badge ("Support" in green / "Resistance" in red), price formatted to 2 decimal places (`$XXX.XX`), confidence as percentage (e.g. `82%`) with a thin confidence bar
- [x] 3.2 Track selected indices in local state; cap selection at 2 — once 2 are checked, disable all unchecked checkboxes; deselecting re-enables them
- [x] 3.3 Render "Confirm Levels" button; disable it when no levels are selected
- [x] 3.4 On "Confirm Levels" click: call `confirmLevels()`; disable button and show spinner while in flight
- [x] 3.5 On confirm success: call `onConfirmed(result)` prop and transition to result card (task 4)
- [x] 3.6 On confirm HTTP 404: show "Session expired. Please re-upload your chart." with re-upload option
- [x] 3.7 On confirm HTTP 422: show "Invalid level selection. Please re-upload and try again." with re-upload option

## 4. Result Card (inside TraderChartUpload)

- [x] 4.1 Render result card after successful confirmation showing: enrichment delta formatted as `+X.X pts` (amber color), enriched score formatted to 1 decimal, levels applied count (e.g. "2 levels applied")
- [x] 4.2 Render "Re-upload" link on the result card that resets component state to initial upload button

## 5. Integration into OpportunitiesPanel

- [x] 5.1 Import `TraderChartUpload` in `frontend/components/OpportunitiesPanel.tsx`
- [x] 5.2 Add `TraderChartUpload` component inside the expanded ticker detail section (line ~330) below the existing enrichment delta display
- [x] 5.3 On `onConfirmed` callback, invalidate / refetch the analysis data for the ticker so `score_enriched` and `enrichment_delta` update in the panel without a full page reload

## 6. Tests

- [x] 6.1 Write unit test: client-side validation rejects file > 10 MB — no API call made, error message shown
- [x] 6.2 Write unit test: client-side validation rejects non-PNG/JPEG — error message shown
- [x] 6.3 Write unit test: valid PNG triggers `enrichTraderChart` call and shows loading spinner
- [x] 6.4 Write unit test: empty `extracted_levels` response shows "No levels detected" message
- [x] 6.5 Write unit test: selecting 2 levels disables remaining checkboxes; deselecting re-enables them
- [x] 6.6 Write unit test: `confirmLevels` called with correct `confirmed_indices` on submit
- [x] 6.7 Write unit test: result card shows correct `enrichment_delta` and `score_enriched` values
- [x] 6.8 Write unit test: "Re-upload" link on result card resets to initial state
