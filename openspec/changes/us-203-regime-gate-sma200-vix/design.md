## Context

The analysis pipeline runs in four stages: (1) data fetch, (2) screenshot, (3) VisionAgent LLM, (4) scoring. Without a macro pre-filter, regime changes cause all lagging indicators to lag confirmation — meaning LLM tokens are spent on setups that will immediately receive AVOID. Two independent gates address this:

- **Per-ticker SMA-200 gate** (Layer 1): tickers trading below their 200-day moving average are structurally bearish; suppress before Stage 2 to avoid LLM cost.
- **VIX gate** (Layer 2): when market-wide volatility exceeds the threshold, all BUY signals are converted to AVOID regardless of individual technical setup.

US-102 adds `sma_200` to `TechnicalIndicators` (same story or coordinated PR). This story assumes that field is present.

## Goals / Non-Goals

**Goals:**
- Zero LLM token spend on below-SMA-200 tickers during bear conditions
- System-wide BUY suppression when VIX > threshold, including stale fallback assets
- `rank_exclusion_reason` persisted to DB for observability across runs
- Fail-open on all network/data errors (no suppression on uncertainty)

**Non-Goals:**
- SELL signal generation (out of scope; signals are BUY/AVOID only)
- Historical backtesting of regime filter effectiveness
- Per-ticker VIX correlation (system-wide gate only)
- SMA period configurability (SMA-200 is fixed; period = 1y download)

## Decisions

**Decision 1 — VIX fetch via asyncio.gather with Stage 1, not sequential**
Fetching VIX after Stage 1 would add yfinance latency to the critical path. Parallelising with `asyncio.gather` means zero added latency in the happy path. Risk: if VIX fetch races with Stage 1 and Stage 1 is much faster, `vix_value` may not be available before regime exclusion — mitigated by gather semantics (both must complete before proceeding).

**Decision 2 — VIX gate applied after Stage 4, not before Stage 2**
Applying before Stage 2 would save more LLM tokens but requires knowing the VIX result before the Stage 1 batch completes. Since VIX is fetched in parallel with Stage 1, the result is available before Stage 2 begins. Implementation chooses to apply VIX gate after Stage 4 (post-scoring) to keep stage transitions clean and to allow the scorer to still produce data; the gate just converts the final signals. This is a deliberate trade-off: LLM tokens are spent even under gate, but the architecture is simpler and less risky.

> Revisit: if LLM cost under VIX gate becomes significant, move VIX gate to pre-Stage-2 by checking `vix_gate_active` before dispatching to VisionAgent.

**Decision 3 — `rank_exclusion_reason` persisted to DB (this story)**
US-202 marks it runtime-only. This story escalates it to persistent because regime exclusion is operationally significant — being able to query "how many tickers were regime-excluded in the last 7 days" is a key observability requirement. Migration is idempotent and safe on existing DBs.

**Decision 4 — Fail-open on all data errors**
VIX fetch failure → `vix_gate_active = False`. `sma_200 is None` → ticker passes. This prevents a network blip from silently suppressing all signals — the system prefers false positives over false negatives in signal generation.

**Decision 5 — `ANALYSIS_VIX_THRESHOLD >= 999` disables gate**
Using a sentinel value rather than a boolean env var keeps the config surface small. The 999 sentinel is unambiguous in logs and `.env.example`.

## Risks / Trade-offs

[Risk: `period="1y"` increases yfinance download payload ~4× per ticker] → Mitigation: measure and document p50/p99 Stage 1 latency delta in the PR. If latency exceeds 10% degradation, explore caching or reducing to `period="250d"`.

[Risk: `^VIX` not available in all market hours / non-US sessions] → Mitigation: fail-open — if VIX fetch returns empty, `vix_value=None`, gate inactive. WARNING logged for on-call visibility.

[Risk: US-102 PR conflict on `period="3mo"` → `"1y"` in `data_agent.py`] → Mitigation: coordinate branches; if US-102 ships first, US-203 PR skips that line change.

[Risk: Stale fallback BUY signals bypassing VIX gate] → Mitigation: explicitly apply `_apply_vix_gate()` to `stale_analyses` list after Stage 4, same as `ranked`.

## Migration Plan

1. Add `sma_200` to `TechnicalIndicators`, `rank_exclusion_reason` to `AssetAnalysis`, `regime_gate_active`/`vix_value` to `AnalysisResult` in `models.py`
2. Update `data_agent.py`: compute SMA-200, change period to `"1y"`
3. Add `rank_exclusion_reason TEXT` column + migration guard in `schema.py`
4. Update `orchestrator.py`: add `_fetch_vix()`, gather with Stage 1, partition `successful` by SMA-200, apply VIX gate post-Stage-4, populate `AnalysisResult` fields
5. Update `routes/analysis.py` to include new fields in response
6. Update frontend analysis panel — add regime gate banner
7. Write all tests

Rollback: revert `orchestrator.py`, `data_agent.py`, `routes/analysis.py`, frontend component. The `rank_exclusion_reason` column in DB is nullable — no data loss if reverted.

## Open Questions

- Should regime-excluded tickers appear in the API response `assets` array (with `rank=None`) or be omitted entirely? Current design: included (matches sector cap behavior in US-202). Confirm with product.
- Is `period="1y"` the correct fix or should US-102 handle this separately? Coordinate with US-102 author before merging.
