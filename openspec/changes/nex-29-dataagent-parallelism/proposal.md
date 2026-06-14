## Why

At 100 tickers, the current `yf.download(all_tickers, ...)` single-batch call silently returns empty DataFrames for 30–50% of tickers without raising exceptions, making Stage 1 unreliable and masking pipeline failures. The 90-second total runtime target also requires chunked sequential downloads with per-ticker retry to replace the brittle single-call approach.

## What Changes

- `fetch_indicators_batch()` in `data_agent.py` is refactored from a single `yf.download(all_100)` call to N sequential chunk downloads with inter-chunk sleep, followed by a per-ticker retry pass for any ticker that returned an empty DataFrame
- Data validation in `_compute_indicators` raises the minimum bars threshold from 30 → 60 and adds a `current_price > 0` guard
- `orchestrator.run_analysis()` gains a 70% minimum viable threshold — fewer than 70% successful tickers raises HTTP 503 instead of silently returning a partial result
- A new `analysis_runs` table records per-run metadata (duration, ticker counts); `GET /api/analysis/latest` response gains a `run_metadata` block with `duration_seconds`
- Error dicts in the `errors` list gain a `duration_ms` field for per-ticker timing visibility

## Capabilities

### New Capabilities

- `analysis-run-metadata`: Stores and surfaces per-run execution metadata (duration, ticker counts, error count) via a new `analysis_runs` DB table and `run_metadata` key on `GET /api/analysis/latest`

### Modified Capabilities

- `analysis-universe-seed`: Existing spec covers the 100-ticker universe seeding; this change modifies how that universe is consumed by `fetch_indicators_batch()` — chunked sequential download replaces the single-batch call, changing the performance and reliability contract

## Impact

- **Backend files**: `data_agent.py`, `orchestrator.py`, `models.py`, `db/schema.py`, `db/connection.py`, `db/repository.py`, `routes/analysis.py`
- **New DB table**: `analysis_runs` (added via existing migration pattern in `connection.py`)
- **API change**: `GET /api/analysis/latest` response shape gains `run_metadata` key — additive, non-breaking
- **Env vars**: `ANALYSIS_DATA_CHUNK_SIZE` (default 20) and `ANALYSIS_DATA_CHUNK_DELAY_S` (default 0.5) — new, read at call-site via `os.environ.get()` so tests can override without module reload
- **No frontend changes** — `run_metadata` is new data the frontend may display but no existing UI breaks
- **yfinance** behavior at scale is the external dependency being worked around; no version change required
