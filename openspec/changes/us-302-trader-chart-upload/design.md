## Context

Traders annotate their own charts with support and resistance lines. The existing enrichment endpoint runs full VisionAgent analysis (signal + confidence + entry/target/stop) — a general-purpose path not suited for constrained level extraction. US-302 adds a new VisionAgent method (`extract_levels`) that calls the vision model with a narrow, structured prompt and returns only price coordinates.

The scoring impact must be deterministic: each confirmed level is worth a fixed number of points (not a confidence float), so the trader understands exactly what they are confirming. The two-step flow (extract → confirm) is required so traders can review and remove false positives before they affect the score.

The `enrichments` table is created by US-201 (NEX-31); US-302 reuses it.

## Goals / Non-Goals

**Goals:**
- Trader uploads a base64 PNG/JPEG of an annotated chart
- VisionAgent returns JSON array of `{type, price, confidence}` — no narrative text
- Proximity filter discards levels >15% from current price
- Trader reviews extracted levels and confirms a subset (max 2)
- Confirmed levels drive a discrete `enrichment_delta` via fixed scoring rules in ScoringAgent
- Custom levels persist in `analysis_tickers.custom_levels` with 5-trading-day TTL
- `analysis_results.custom_levels_applied` records count of levels that scored

**Non-Goals:**
- Automated level detection without trader upload
- Rerunning the full VisionAgent analysis pipeline
- Storing chart images (bytes are not persisted after extraction)
- Browser or screenshot capture (that is US-201's domain)
- Float confidence mapping (enrichment_delta is computed from discrete integer rules)

## Decisions

### Decision: Synchronous extraction (200 OK, not 202 Accepted)
VisionAgent `extract_levels()` is a fast, focused call (~3-5s on Cerebras). The trader needs the extracted levels immediately to perform confirmation. A 202 + polling cycle would add UX friction with no benefit. If extraction exceeds 8s, return `[]` with `status: "extraction_failed"` — still synchronous, still 200.

**Alternative considered**: Background task like US-201 — unnecessary latency for trader who is actively waiting to review.

### Decision: Constrained prompt with structured output schema, not free-form
The `LEVEL_EXTRACTION_PROMPT` instructs the model to return ONLY a JSON array and nothing else. Structured output (Pydantic schema) is enforced via LiteLLM — parse failures fall back to `[]`. This prevents narrative leakage and ensures the frontend always receives a typed array.

**Alternative considered**: Ask the model to describe the chart and parse S/R levels from prose — too fragile, model often omits levels or adds commentary.

### Decision: Discrete scoring rules (fixed integers) over confidence float
`+4 for support within 1 ATR of entry, +3 for resistance within 2% of target` is transparent and auditable. The trader knows what each confirmed level is worth. A confidence float (like the existing enrichment_delta formula) would be opaque.

**Alternative considered**: `enrichment_delta = (avg_confidence - 0.5) * 30 * level_count` — not interpretable by the trader; violates the design principle stated in the Linear ticket.

### Decision: Max 2 confirmed levels, scoring cap at ENRICHMENT_MAX_DELTA
Caps prevent over-weighting trader annotation relative to quantitative scoring. 2 levels maximum forces traders to choose their most significant S/R levels. The ENRICHMENT_MAX_DELTA (15 pt) ceiling is shared with all enrichment types to preserve score_quant as the primary ranking signal.

### Decision: Trading-day TTL (not calendar-day)
S/R levels are market concepts — a level drawn on Friday should still be active Monday. Calendar-day TTL would expire levels over the weekend incorrectly. Trading-day TTL (skip Sat/Sun) is simple to implement and correct for the use case. No holiday calendar needed for V1.

### Decision: Idempotent confirmation
A second confirm call for the same `enrichment_id` returns the existing result without re-applying scoring. This prevents accidental double-scoring from network retries or UI re-submissions.

## Risks / Trade-offs

- [Risk] LLM extracts wrong price levels (misread chart scale) → Mitigation: trader confirmation step is the primary safeguard; proximity filter removes obviously wrong levels (>15% from current price); max 2 levels limits blast radius
- [Risk] Proximity filter is too aggressive for highly volatile assets → Mitigation: 15% threshold is configurable via future env var `CUSTOM_LEVEL_PROXIMITY_PCT` if needed; hardcoded for V1
- [Risk] VisionAgent model refuses structured output for unusual chart images → Mitigation: `extract_levels()` returns `[]` on any parse/model error; trader sees "No levels detected" and can try a different chart
- [Risk] `custom_levels` TTL expiry misses levels on dormant instances → Mitigation: expiry check runs on startup AND on every confirm call; levels also filtered at scoring time by checking `custom_levels_expires_at`
- [Risk] US-301 enrichment_delta contract not finalized before scoring integration → Mitigation: feature flag `CUSTOM_LEVELS_SCORING_ENABLED` (default `true`) gates scoring recompute; extraction and confirmation work independently

## Migration Plan

1. `schema.py` — add `custom_levels TEXT`, `custom_levels_expires_at TEXT` to `analysis_tickers`; add `custom_levels_applied INTEGER DEFAULT 0` to `analysis_results` (idempotent ALTER TABLE)
2. Backend code changes — all additive
3. No Docker changes (no new dependencies beyond existing LiteLLM stack)
4. Rebuild container; existing data unaffected

Rollback: revert code; new columns are additive with defaults.

## Open Questions

- Should `ENRICHMENT_MAX_DELTA` be a shared env var across all enrichment types (screenshot + trader chart), or separate per type? Current design: shared ceiling, single env var.
- Should the confirm endpoint require re-supplying the `enrichment_id` (current design) or use a ticker-scoped URL (`POST /api/analysis/{ticker}/confirm`) without enrichment_id? Current design uses body-supplied `enrichment_id` for explicit tracing.
