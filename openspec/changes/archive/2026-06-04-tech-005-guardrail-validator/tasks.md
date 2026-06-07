## 1. Tests

- [x] 1.1 Add unit tests for `validate_asset_analysis()` covering valid asset, `entry_price <= 0`, `stop_loss >= entry_price`, `target_price <= entry_price`, and `risk_reward_ratio < 0`.
- [x] 1.2 Add ScoringAgent tests proving invalid assets keep `rank=None` and do not receive computed score, score_delta, or bet-size fields.
- [x] 1.3 Add a regression test proving valid assets still score, rank, compute score_delta, and compute bet-size fields as before.
- [x] 1.4 Add an orchestration-level or scoring-result test proving structural invalid errors are surfaced with ticker and `structural_invalid:` reason.

## 2. Guardrail Implementation

- [x] 2.1 Implement `validate_asset_analysis(asset: AssetAnalysis) -> tuple[bool, str]` in `backend/app/analysis/scoring_agent.py`.
- [x] 2.2 Execute validation before the scoring loop and quarantine invalid assets before score or bet-size computation.
- [x] 2.3 Ensure invalid assets remain in the returned assets list with `rank=None`.
- [x] 2.4 Add an error-producing scoring path or result shape so invalid assets produce per-ticker structural errors without changing the public API response shape.

## 3. Orchestrator Integration

- [x] 3.1 Update `backend/app/analysis/orchestrator.py` to append structural validation errors to the existing `AnalysisResult.errors` list.
- [x] 3.2 Preserve persistence behavior for ranked/unranked assets and avoid computing or persisting derived scoring fields for structurally invalid assets.

## 4. Verification

- [x] 4.1 Run the focused backend tests for ScoringAgent and orchestrator analysis behavior.
- [x] 4.2 Run OpenSpec validation/status for `tech-005-guardrail-validator`.
