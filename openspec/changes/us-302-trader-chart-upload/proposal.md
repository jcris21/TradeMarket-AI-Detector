## Why

Traders draw support and resistance lines on their own charts during analysis. The system currently has no way to ingest these hand-drawn levels. Allowing chart upload lets traders contribute their chart knowledge as concrete price coordinates that drive a quantified `enrichment_delta` — not a vague confidence float.

## What Changes

- `POST /api/analysis/enrich/{ticker}` extended to accept `{"enrichment_type": "trader_chart", "chart_image": base64}` — synchronous response with extracted S/R levels; status `pending_confirmation`
- New `POST /api/analysis/enrich/{ticker}/confirm` endpoint — trader approves levels; scoring recomputed
- New VisionAgent `extract_levels(image_bytes)` method: constrained prompt, returns `List[ExtractedLevel]`; no narrative, no full analysis pipeline
- Proximity filter: discard levels where `abs(level.price - current_price) / current_price > 0.15`
- ScoringAgent `_apply_custom_levels()` post-pass: confirmed support within 1 ATR → +4 pts; resistance near target → +3 pts; max 2 levels; capped at `ENRICHMENT_MAX_DELTA`
- `analysis_tickers.custom_levels TEXT` + `custom_levels_expires_at TEXT` — TTL-based storage (default 5 trading days via `CUSTOM_LEVEL_TTL_DAYS` env var)
- `analysis_results.custom_levels_applied INTEGER` — count of levels that scored (0, 1, or 2)
- Security: base64 image validated for size (max 10 MB decoded), PNG/JPEG content-type only

## Capabilities

### New Capabilities

- `trader-chart-upload`: Two-step upload → confirm flow; VisionAgent constrained level extraction; proximity filtering; TTL-governed persistence of confirmed levels

### Modified Capabilities

- `enrichment-delta`: `trader_chart` type added to enrich endpoint dispatch; enrichment_delta now computed from discrete scoring rules (not confidence mapping)
- `score-quant`: Custom level scoring post-pass in ScoringAgent applied after confirmation; capped at ENRICHMENT_MAX_DELTA ceiling

## Impact

- `backend/app/analysis/vision_agent.py` — add `extract_levels()` method
- `backend/app/analysis/scoring_agent.py` — add `_apply_custom_levels()` post-pass
- `backend/app/routes/analysis.py` — trader_chart branch + confirm endpoint
- `backend/app/db/schema.py` — two new columns on `analysis_tickers`, one on `analysis_results`
- `backend/app/db/repository.py` — custom level CRUD + expiry
- `backend/app/analysis/models.py` — `ExtractedLevel`, `LevelConfirmationRequest`, `ConfirmedLevel`
- Shares `enrichments` table introduced by US-201
