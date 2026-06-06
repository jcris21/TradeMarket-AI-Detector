## 1. Backend — Tests (TDD: write first)

- [x] 1.1 Add `test_bet_size_rr_3` to `backend/tests/analysis/test_scoring_agent.py` — entry=100, target=130, stop=90 → gain=3.0, loss=1.0
- [x] 1.2 Add `test_bet_size_rr_2` — entry=100, target=120, stop=90 → gain=2.0, loss=1.0
- [x] 1.3 Add `test_bet_size_rr_6` — entry=100, target=160, stop=90 → gain=6.0, loss=1.0
- [x] 1.4 Add `test_bet_size_division_by_zero` — entry=0 → gain=0.0, loss=0.0, ev=0.0
- [x] 1.5 Add `test_ev_switch_assumed` — < 30 outcomes → hit_rate_used=0.35, hit_rate_source='assumed'
- [x] 1.6 Add `test_ev_switch_realized` — >= 30 outcomes → hit_rate_used=real ratio, hit_rate_source='realized'
- [x] 1.7 Add `test_get_hit_rate_fallback` — missing `signal_outcomes` table → returns (0.35, 'assumed') without error

## 2. Backend — Model

- [x] 2.1 Add 5 optional fields to `AssetAnalysis` in `backend/app/analysis/models.py`: `expected_gain_per10`, `expected_loss_per10`, `expected_value_per10`, `hit_rate_used`, `hit_rate_source`
- [x] 2.2 Update `AssetAnalysis.to_db_row()` to include the 5 new fields in the returned dict

## 3. Backend — ScoringAgent

- [x] 3.1 Add `_compute_bet_size(asset, hit_rate, source) -> AssetAnalysis` to `backend/app/analysis/scoring_agent.py`
- [x] 3.2 Add `_get_hit_rate(db) -> tuple[float, str]` with `try/except` fallback for missing table
- [x] 3.3 Call `_get_hit_rate` and `_compute_bet_size` inside `score_and_rank()` for every asset

## 4. Backend — Database Migration

- [x] 4.1 Add lazy `ALTER TABLE analysis_results ADD COLUMN` for all 5 columns in `backend/app/db/connection.py` `init_db()` (silent on duplicate column error)
- [x] 4.2 Update `_MOCK_ANALYSIS_SEED` rows in `connection.py` to include `expected_gain_per10`, `expected_loss_per10`, `expected_value_per10`, `hit_rate_used`, `hit_rate_source` so first-launch UI renders with data

## 5. Frontend — Types

- [x] 5.1 Add 5 optional fields to `AssetAnalysis` interface in `frontend/lib/types.ts`: `expected_gain_per10?`, `expected_loss_per10?`, `expected_value_per10?`, `hit_rate_used?`, `hit_rate_source?`

## 6. Frontend — BetSizeCell Component

- [x] 6.1 Create `frontend/components/BetSizeCell.tsx` with props `gain`, `loss`, `ev`, `hrUsed`, `hrSrc`
- [x] 6.2 Render `+$X.XX` in `text-gain` bold tabular-nums
- [x] 6.3 Render `-$X.XX` in `text-loss` tabular-nums
- [x] 6.4 Render EV badge in `text-accent-yellow` with native `title` tooltip (assumed vs realized text)
- [x] 6.5 Render `—` when any field is null

## 7. Frontend — OpportunitiesPanel

- [x] 7.1 Add "Bet Size" column header to table in `frontend/components/OpportunitiesPanel.tsx`
- [x] 7.2 Add `<BetSizeCell>` in each row — passes null for non-BUY signals

## 8. Verification

- [x] 8.1 Run `uv run --extra dev pytest backend/tests/analysis/test_scoring_agent.py -v` — all new tests pass
- [ ] 8.2 Start the app and verify BetSizeCell renders in OpportunitiesPanel with mock seed data
- [x] 8.3 Verify null fields render `—` (no crash for legacy rows)
