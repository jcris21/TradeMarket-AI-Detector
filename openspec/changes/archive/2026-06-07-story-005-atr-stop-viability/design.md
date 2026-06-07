## Context

The ScoringAgent pipeline currently scores asset setups based on LLM confidence, risk/reward ratio, and indicator confluence. It has no mechanism to validate whether a stop-loss placement is physically viable given the asset's volatility regime. TECH-005 (GuardrailValidator) introduced structural validation of LLM outputs, but left statistical/financial validity to a future pass. This feature adds that pass: an ATR-based noise-floor check that runs deterministically after DataAgent completes and before the scoring formula executes.

Current state: `TechnicalIndicators` and `AssetAnalysis` carry no ATR data. `DataAgent` already batch-downloads OHLCV history via yfinance and computes indicators via `pandas-ta` — ATR is a natural addition with zero new I/O. `ScoringAgent.score_and_rank_with_errors()` applies TECH-005 structural guardrails; ATR viability slots in immediately after as a second gate.

## Goals / Non-Goals

**Goals:**
- Hard-disqualify setups where `stop_distance_pct < 0.5 × atr_14_pct` (stop inside ATR noise floor)
- Apply a −15 point soft penalty when stop distance is between 0.5× and `ATR_FLOOR_FACTOR` × ATR
- Award a +8 point boost when stop distance exceeds 1.5× ATR (well-placed stop)
- Expose `stop_viable: bool | None` on `AssetAnalysis` and persist it to `analysis_results`
- Make the soft-penalty floor configurable via `ANALYSIS_ATR_FLOOR` env var (default 0.8)
- Display per-signal ATR badge in the frontend `SignalTable`
- Maintain full backward compatibility: missing ATR data passes through unchanged

**Non-Goals:**
- Dynamic ATR window lengths (14-period only)
- Per-ticker ATR thresholds (single global threshold)
- Real-time ATR recalculation mid-session (computed once per DataAgent cycle)
- Multi-user or concurrency concerns (single-user system)
- Changing the LLM prompt or structured output schema

## Decisions

### Decision 1: ATR computed in DataAgent, not ScoringAgent

**Choice:** DataAgent owns ATR computation; ScoringAgent only consumes it.

**Rationale:** DataAgent already holds the OHLCV series required by `ta.atr()`. Pushing computation into ScoringAgent would require passing raw price series downstream, violating the existing stage boundary where Stage 1 (DataAgent) produces indicators and Stage 4 (ScoringAgent) consumes them. Keeping the computation in DataAgent also means ATR is available for any future stage that needs it, not just scoring.

**Alternative considered:** Compute ATR inside `_compute_atr_viability()` by re-fetching prices. Rejected: extra network I/O, duplicated yfinance logic, and harder to test in isolation.

### Decision 2: ATR unavailability is a pass-through, not an error

**Choice:** When `atr_14_pct is None`, `_compute_atr_viability()` returns `(False, True, 0.0)` — the asset is not penalized.

**Rationale:** ATR can legitimately be unavailable for tickers with insufficient history (e.g., newly listed assets, illiquid names, or yfinance outages). Penalizing these would produce false negatives. The `stop_viable = None` value in the DB distinguishes "ATR unavailable" from "ATR checked and passed" for downstream observability.

**Alternative considered:** Treat unavailable ATR as a soft penalty. Rejected: too aggressive for data availability issues outside the pipeline's control.

### Decision 3: Four-band threshold as code constants, floor as env var

**Choice:** Hard floor (0.5×) and boost threshold (1.5×) are compile-time constants; soft floor (`ATR_FLOOR_FACTOR`) is `ANALYSIS_ATR_FLOOR` env var.

**Rationale:** The hard floor and boost represent financial/statistical invariants unlikely to need production tuning. The soft floor is a portfolio-risk preference that operators may want to adjust without a deploy. Making all three env vars would add configuration surface area with no benefit; making all three constants would impede legitimate tuning.

### Decision 4: `atr_disqualify:` error prefix distinct from `structural_invalid:`

**Choice:** ATR disqualifications use prefix `atr_disqualify:` in `AnalysisResult.errors`.

**Rationale:** Enables log filtering and alerting by error type. Operators can independently monitor structural failures (TECH-005) vs. viability failures (this feature). Merging them would obscure the signal ratio between LLM-quality issues and stop-placement issues.

### Decision 5: Lazy migration for `stop_viable` column

**Choice:** Add `("stop_viable", "INTEGER")` to the existing lazy migration list in `connection.py`.

**Rationale:** Follows the established pattern already used for `bet_size` and `outcome` columns. No migration script needed; the column is added on first startup after deploy, with `NULL` for all existing rows (maps to `stop_viable = None` in Python, treated as "check skipped").

## Risks / Trade-offs

- **[Risk] `ta.atr()` returns all-NaN for short histories** → Mitigation: `atr_series.iloc[-1]` is wrapped in `pd.isna()` guard; falls back to `None` cleanly.
- **[Risk] `entry_price = 0` causes division-by-zero in `atr_14_pct`** → Mitigation: guard `if current_price > 0` already present in proposed code.
- **[Risk] Env var `ANALYSIS_ATR_FLOOR` set to a value outside [0.5, 1.5]** → Mitigation: no runtime validation specified; operators are expected to understand the domain. A value ≥ 1.5 would collapse soft-penalty and boost bands — acceptable edge case for power users.
- **[Trade-off] Hard floor (0.5×) is not runtime-tunable** → this means an erroneous constant requires a code change and redeploy. Accepted: the 0.5× hard floor is a well-established rule-of-thumb in technical analysis; changing it should require a code review, not an env var tweak.
- **[Trade-off] `stop_viable = None` stored as SQL NULL** → frontend must handle `null` as a distinct state from `false`. The badge component uses `!= null` check before rendering, correctly showing "—" for unavailable ATR.

## Migration Plan

1. Deploy new backend image — lazy migration adds `stop_viable INTEGER NULL` to `analysis_results` on first request; existing rows get `NULL` (no disruption)
2. New analyses populate `stop_viable` immediately
3. Frontend deploy adds ATR badge column; rows with `NULL` show neutral "—" dash
4. No rollback schema change needed — `NULL` column is ignored by old code if rolled back

## Open Questions

- None blocking implementation. The `atr_14_pct` calculation uses `atr_14 / current_price`; verify this matches the convention used by `stop_distance_pct` (which uses `entry_price`). If `current_price != entry_price` at scoring time, the comparison bands may be slightly off — acceptable for V1.
