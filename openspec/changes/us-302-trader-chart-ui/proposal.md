## Why

US-302 implemented the full backend for trader chart upload (extract S/R levels, confirm, score), but no frontend UI exists to drive it. Traders cannot use this capability without a way to upload their annotated chart and review the extracted levels from the browser.

## What Changes

- New `TraderChartUpload` React component: file picker button scoped to the analysis panel of a ticker, accepts PNG/JPEG, encodes to base64, calls `POST /api/analysis/enrich/{ticker}` with `enrichment_type: "trader_chart"`
- New `LevelConfirmation` UI: displays the list of extracted S/R levels returned by the API (type, price, confidence), lets trader select up to 2, then calls `POST /api/analysis/enrich/{ticker}/confirm`
- Feedback on confirmation result: shows `enrichment_delta`, `score_enriched`, and count of levels applied inline in the analysis panel
- Error states: oversized image (>10 MB), wrong file type, extraction failure (`[]` returned), network errors — all surfaced with clear inline messages
- Loading states: spinner while extraction is in progress (synchronous ~3-5s call)

## Capabilities

### New Capabilities

- `trader-chart-upload-ui`: Two-step frontend flow — file upload → level review/confirm — wired to the US-302 backend API; includes file validation, loading states, error handling, and result display

### Modified Capabilities

- `enrichment-delta`: No requirement changes — backend contract is unchanged. Frontend now consumes the `enrichment_delta` and `score_enriched` values returned by the confirm endpoint and displays them.

## Impact

- `frontend/` — new component(s) in the analysis panel area; new API client calls for enrich and confirm endpoints
- No backend changes — all API contracts are already implemented by US-302
- No schema or Docker changes
