## Context

US-302 delivered a complete backend for trader chart upload: `POST /api/analysis/enrich/{ticker}` (with `enrichment_type: "trader_chart"`) and `POST /api/analysis/enrich/{ticker}/confirm`. The backend returns extracted S/R levels and, after confirmation, a revised `enrichment_delta` and `score_enriched`. No frontend surface exists yet.

The frontend is a Next.js static export styled as a Bloomberg-style terminal (dark theme, `#0d1117` backgrounds, accent yellow `#ecad0a`). The analysis panel already displays `score_quant` and `score_enriched` for a selected ticker; this change adds the upload flow inline to that panel.

## Goals / Non-Goals

**Goals:**
- Single-file drop or click-to-browse file picker, PNG/JPEG only, client-side size guard (10 MB)
- Base64 encode the file in the browser and POST to the enrich endpoint
- Display extracted levels as a selectable checklist (type badge, price, confidence bar)
- Allow trader to select up to 2 levels and submit confirmation
- Show delta result (`enrichment_delta`, `score_enriched`) inline after confirm
- Clear loading and error states at every step

**Non-Goals:**
- Drag-and-drop zone (click-to-browse is sufficient for V1)
- Preview rendering of the uploaded chart image in the UI
- Persisting previously confirmed levels across page refreshes (backend TTL handles persistence; UI resets on reload)
- Multi-ticker batch upload

## Decisions

### Decision: Inline panel, not a modal
The level review step requires the trader to compare extracted prices against the main chart already visible on screen. A modal would obscure that chart. An inline collapsible section within the analysis panel keeps the chart visible alongside the level list.

**Alternative considered**: Full-screen modal — rejected because it hides the chart the trader needs to validate levels against.

### Decision: Client-side file validation before upload
Validate file type (MIME or extension) and size (<= 10 MB) in the browser before encoding and sending. This avoids a round-trip for a trivially rejectable file and keeps the 400 error path for server-side edge cases only.

**Alternative considered**: Send everything and rely on the server 400 — wastes bandwidth on large files and gives a slower error feedback loop.

### Decision: Base64 encoding in the browser via FileReader API
`FileReader.readAsDataURL()` returns `data:<mime>;base64,<data>`. Strip the prefix before sending. No server-side upload endpoint needed; the existing enrich endpoint already accepts the base64 string in the JSON body.

**Alternative considered**: `multipart/form-data` upload — would require a new backend endpoint or middleware; not worth the complexity when the API already accepts base64 JSON.

### Decision: Selection capped at 2 with UI enforcement
Checkboxes; once 2 are selected, remaining unchecked items are disabled. On deselect, they re-enable. This mirrors the backend cap (first 2 indices) and removes ambiguity about which levels will be used.

**Alternative considered**: Allow selecting any number and let the backend silently cap at 2 — confusing for the trader who doesn't know which two were used.

### Decision: Confirm result replaces the upload section
After a successful confirm, the upload/review UI is replaced by a result summary card (`enrichment_delta`, `score_enriched`, levels applied count) with a "Re-upload" link to restart the flow. This avoids UI clutter from keeping both upload and result visible simultaneously.

## Risks / Trade-offs

- [Risk] Extraction takes 3-5s — trader may think the UI is frozen → Mitigation: spinner with label "Extracting levels…" shown immediately on POST; disable the upload button during the request
- [Risk] VisionAgent returns `[]` (no levels detected) → Mitigation: show an explicit "No levels detected in this chart. Try a clearer image." message with a re-upload option
- [Risk] Confidence values from the model may cluster near 0.5 making the bar unhelpful → Mitigation: display the raw confidence percentage alongside the bar; trader can still confirm any level regardless of confidence
- [Risk] Large PNG files (~8-10 MB) produce very long base64 strings in the JSON body → Mitigation: client-side size guard at 10 MB; server enforces the same limit; acceptable for V1 single-user use

## Migration Plan

1. Add new React component(s) under `frontend/src/` (exact directory per frontend conventions)
2. Wire into the existing analysis panel for the selected ticker
3. No backend, schema, or Docker changes required
4. Deploy by rebuilding the Docker image (Next.js static export step picks up new components)

Rollback: revert frontend files; no data migration needed.
