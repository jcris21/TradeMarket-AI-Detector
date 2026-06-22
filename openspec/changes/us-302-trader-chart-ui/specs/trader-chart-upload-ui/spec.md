## ADDED Requirements

### Requirement: Trader can upload an annotated chart image for a selected ticker
The frontend SHALL render a "Upload Chart" button in the analysis panel of the currently selected ticker. Clicking it SHALL open a native file picker restricted to PNG and JPEG files. After the trader selects a file, the frontend SHALL validate client-side (size ≤ 10 MB, MIME type image/png or image/jpeg) before encoding.

#### Scenario: Button visible in analysis panel
- **WHEN** a ticker is selected and an analysis result exists
- **THEN** an "Upload Chart" button is visible in the analysis panel

#### Scenario: File picker opens on click
- **WHEN** trader clicks "Upload Chart"
- **THEN** the native file picker opens, filtered to accept only PNG and JPEG files

#### Scenario: Oversized file rejected client-side
- **WHEN** trader selects a file larger than 10 MB
- **THEN** the file picker closes and an inline error "File must be under 10 MB" is shown; no API call is made

#### Scenario: Non-image file rejected client-side
- **WHEN** trader selects a file that is not PNG or JPEG
- **THEN** an inline error "Only PNG and JPEG images are supported" is shown; no API call is made

### Requirement: Frontend encodes image and calls the enrich endpoint
After client-side validation passes, the frontend SHALL encode the file as base64 (stripping the `data:<mime>;base64,` prefix), POST to `POST /api/analysis/enrich/{ticker}` with `{"enrichment_type": "trader_chart", "chart_image": "<base64>"}`, and display a loading state during the request.

#### Scenario: Loading state shown during extraction
- **WHEN** a valid file has been selected and the POST is in flight
- **THEN** the "Upload Chart" button is disabled and a spinner with label "Extracting levels…" is visible

#### Scenario: Successful extraction returns level list
- **WHEN** the API returns HTTP 200 with `extracted_levels` containing one or more items
- **THEN** the loading state clears and the level review UI is displayed with the extracted levels

#### Scenario: API returns empty extracted_levels
- **WHEN** the API returns HTTP 200 with `extracted_levels: []`
- **THEN** the loading state clears and the message "No levels detected in this chart. Try a clearer image." is shown with a "Re-upload" link

#### Scenario: API returns HTTP 400 (image validation failure)
- **WHEN** the API returns HTTP 400
- **THEN** the error message from the response body is shown inline; the trader can re-upload

#### Scenario: Network error during extraction
- **WHEN** the fetch call fails due to a network error
- **THEN** an inline error "Could not reach server. Please try again." is shown

### Requirement: Trader reviews extracted levels and selects up to 2 to confirm
The frontend SHALL display each extracted level as a selectable row showing: type badge ("Support" or "Resistance"), price formatted to 2 decimal places, and a confidence percentage. The trader SHALL be able to select up to 2 levels via checkboxes. Once 2 are selected, all unselected checkboxes SHALL be disabled. Deselecting a level SHALL re-enable the remaining checkboxes.

#### Scenario: Level list rendered with type, price, confidence
- **WHEN** extraction returns `[{type: "support", price: 195.50, confidence: 0.82}, ...]`
- **THEN** each level shows a "Support" or "Resistance" badge, price "$195.50", and "82%" confidence

#### Scenario: Selecting 2 levels disables remaining checkboxes
- **WHEN** trader checks 2 levels
- **THEN** all unchecked level checkboxes become disabled

#### Scenario: Deselecting a level re-enables checkboxes
- **WHEN** trader unchecks one of 2 already-selected levels
- **THEN** all unchecked checkboxes are re-enabled

#### Scenario: Confirm button disabled with no levels selected
- **WHEN** no levels are selected
- **THEN** the "Confirm Levels" button is disabled

### Requirement: Trader submits confirmed levels and sees scoring result
When the trader clicks "Confirm Levels", the frontend SHALL POST to `POST /api/analysis/enrich/{ticker}/confirm` with `{"enrichment_id": "<uuid>", "confirmed_indices": [<selected indices>]}`. On success, the upload/review UI SHALL be replaced by a result summary card.

#### Scenario: Confirm request sent with correct payload
- **WHEN** trader selects levels at indices [0, 2] and clicks "Confirm Levels"
- **THEN** POST is sent with `{"enrichment_id": "<uuid>", "confirmed_indices": [0, 2]}`

#### Scenario: Loading state shown during confirmation
- **WHEN** the confirm POST is in flight
- **THEN** the "Confirm Levels" button is disabled and shows a spinner

#### Scenario: Result card shown after successful confirmation
- **WHEN** the confirm API returns HTTP 200
- **THEN** the review UI is replaced by a card showing: enrichment delta (e.g. "+7 pts"), enriched score, and levels applied count (e.g. "2 levels applied")

#### Scenario: Result card shows zero delta when no levels scored
- **WHEN** confirmed levels exist but none met scoring criteria (`enrichment_delta: 0`)
- **THEN** the card shows "0 pts", the enriched score, and "0 levels applied"

#### Scenario: Re-upload link resets the flow
- **WHEN** trader clicks "Re-upload" on the result card
- **THEN** the result card is replaced by the upload button in its initial state

#### Scenario: Confirm API returns HTTP 404
- **WHEN** the confirm POST returns HTTP 404 (unknown enrichment_id)
- **THEN** an inline error "Session expired. Please re-upload your chart." is shown with a re-upload option

#### Scenario: Confirm API returns HTTP 422
- **WHEN** the confirm POST returns HTTP 422 (out-of-range index)
- **THEN** an inline error "Invalid level selection. Please re-upload and try again." is shown
