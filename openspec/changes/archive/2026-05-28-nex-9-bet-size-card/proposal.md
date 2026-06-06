## Why

Swing traders reviewing AI signals need to instantly evaluate monetary risk/reward without mental math. Currently the OpportunitiesPanel shows R/R ratios but no dollar figures, forcing traders to calculate manually. Adding a Bet-Size Card (gain/loss/EV per $10 invested) pre-computed at write time eliminates this friction and makes signal value immediately scannable.

## What Changes

- **New column** "Bet Size" added to OpportunitiesPanel table (BUY rows only): shows `+$X.XX` gain, `-$X.XX` loss, and `EV $X.XX` per $10 invested
- **ScoringAgent extended** with `_compute_bet_size()` and `_get_hit_rate()` — computed at write path, zero read overhead
- **5 new nullable columns** added to `analysis_results` via lazy migration at startup: `expected_gain_per10`, `expected_loss_per10`, `expected_value_per10`, `hit_rate_used`, `hit_rate_source`
- **AssetAnalysis Pydantic model** extended with 5 optional fields (backward compatible)
- **EV switch**: uses 35% assumed hit rate until 30+ historical outcomes exist, then switches to realized HR from `signal_outcomes` table (TECH-003 dependency — graceful fallback if table absent)
- **New frontend component** `BetSizeCell.tsx` with tooltip explaining EV basis

## Capabilities

### New Capabilities

- `bet-size-card`: Per-signal monetary bet sizing — gain/loss/EV per $10 invested, displayed as a column in the opportunities table with EV badge showing assumed vs realized hit rate

### Modified Capabilities

- (none — existing endpoints serialize new fields automatically via optional Pydantic fields)

## Impact

- **Backend files**: `app/analysis/models.py`, `app/analysis/scoring_agent.py`, `app/db/connection.py`
- **Frontend files**: `components/OpportunitiesPanel.tsx` (new column), `components/BetSizeCell.tsx` (new), `lib/types.ts` (new fields)
- **Tests**: `tests/analysis/test_scoring_agent.py` (new parametrized cases)
- **DB**: 5 nullable columns added to `analysis_results` — no breaking schema change, existing rows get NULL values
- **APIs**: `/api/analysis/latest`, `/api/analysis/{ticker}` — no route change, new fields appear in response
- **Dependencies**: None new (pure arithmetic, existing recharts for tooltip via native HTML `title`)
