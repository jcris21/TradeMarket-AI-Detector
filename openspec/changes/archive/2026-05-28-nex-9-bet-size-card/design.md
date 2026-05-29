## Context

OpportunitiesPanel currently shows R/R ratio as a multiplier (e.g. `4.8x`) but no monetary figures. The ScoringAgent already computes `entry_price`, `target_price`, and `stop_loss` per asset. All bet-size math is pure arithmetic — no external dependencies needed.

The system uses a write-path pre-computation pattern (DDIA Alt 1): values are computed once by `ScoringAgent` at analysis time and stored in `analysis_results`, so the dashboard read path stays zero-overhead.

SQLite column additions are nullable and applied lazily at startup via `ALTER TABLE IF NOT EXISTS`-equivalent pattern (try/except on duplicate column error), keeping the single-container deployment model intact.

## Goals / Non-Goals

**Goals:**
- Pre-compute `gain_10`, `loss_10`, `ev_10` in `ScoringAgent` at write time
- Store 5 new nullable columns in `analysis_results` (backward-compatible migration)
- Extend `AssetAnalysis` Pydantic model with 5 optional fields
- Render a `BetSizeCell` component in OpportunitiesPanel (BUY rows only)
- EV uses 35% assumed HR until 30+ outcomes exist, then switches to realized HR

**Non-Goals:**
- Outcome recording UI (`signal_outcomes` table — deferred to TECH-003)
- Score delta between runs (deferred to TECH-003)
- Mobile / responsive layout changes
- Fractional share sizing (always normalized to $10 basis)

## Decisions

### Decision 1: Write-path pre-computation vs. read-path calculation

**Chosen:** Pre-compute in `ScoringAgent`, store in DB.

**Alternatives considered:**
- *Read-path calculation (frontend)*: Simpler but duplicates business logic in TypeScript; breaks if formula changes.
- *Read-path calculation (API)*: No DB change needed, but adds latency to every dashboard load and couples API to formula.

**Rationale:** Consistent with existing write-path pattern for `score` and `rank`. Single source of truth. Zero dashboard overhead. Formula lives in one place (Python).

### Decision 2: 5 nullable columns vs. separate table

**Chosen:** 5 nullable columns on `analysis_results`.

**Alternatives considered:**
- *Separate `bet_size_results` table*: Cleaner schema, but adds a JOIN on every analysis fetch. Overkill for 5 scalar values on the same entity.

**Rationale:** These values are 1:1 with each analysis row. Nullable columns keep the fetch query unchanged and the migration non-destructive.

### Decision 3: Native HTML `title` tooltip vs. Radix/Headless UI

**Chosen:** Native `title` attribute on the EV badge.

**Alternatives considered:**
- *Recharts `<Tooltip>`*: Already in project but designed for chart overlays, not table cells.
- *Radix UI Tooltip*: Best DX but requires a new dependency.

**Rationale:** Zero new dependencies. The tooltip content is informational only (not interactive). Native `title` is accessible and sufficient.

### Decision 4: `_get_hit_rate` fallback strategy

**Chosen:** `try/except` around `signal_outcomes` query — returns `(0.35, "assumed")` if table absent.

**Rationale:** `signal_outcomes` table depends on TECH-003 (not yet implemented). Hard-coding a graceful fallback means NEX-9 can ship independently without blocking on TECH-003.

## Risks / Trade-offs

- **`signal_outcomes` table absent** → Mitigation: `try/except` in `_get_hit_rate()` always falls back to 35% assumed. No crash, clear `hit_rate_source` label in UI.
- **Division by zero (`entry_price = 0`)** → Mitigation: explicit guard in `_compute_bet_size()`, returns `0.0` for all fields.
- **Mock seed data in `connection.py` lacks new columns** → Mitigation: Add `expected_gain_per10`, `expected_loss_per10`, `expected_value_per10`, `hit_rate_used`, `hit_rate_source` to seed rows so first-launch UI renders with data.
- **Existing `analysis_results` rows have NULL bet-size fields** → Accepted trade-off. UI renders `—` for null values. Next real analysis run populates them.

## Migration Plan

1. On container startup, `init_db()` runs `ALTER TABLE analysis_results ADD COLUMN ...` for each new column (silently ignores "duplicate column" error).
2. Existing rows get NULL — frontend renders `—` gracefully.
3. Next analysis run populates all new columns.
4. No rollback needed — nullable columns are additive and ignored by old code.

## Open Questions

- Should `BetSizeCell` be visible on `WAIT` signal rows too (with a visual indicator that the signal isn't actionable)? **Current decision:** BUY only, per Linear ticket spec.
- Once TECH-003 ships, should `_get_hit_rate` be extracted to a shared utility? **Yes** — defer until TECH-003 is in scope.
