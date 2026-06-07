## Why

VisionAgent output is LLM-generated and can be structurally valid JSON while still violating trading invariants, such as an inverted stop loss or target price. ScoringAgent needs an explicit guardrail boundary before scoring so corrupted trade parameters cannot reach ranking or the dashboard as actionable signals.

## What Changes

- Add a GuardrailValidator layer in `scoring_agent.py` that validates every `AssetAnalysis` before score computation and ranking.
- Reject structurally invalid assets with `rank=None` and a machine-readable `structural_invalid` error reason.
- Preserve existing scoring, filtering, bet-size, and score-delta behavior for valid assets.
- Add focused ScoringAgent tests covering invalid entry price, inverted stop loss, inverted target price, negative risk/reward ratio, and a valid-asset regression.

## Capabilities

### New Capabilities
- `asset-analysis-guardrails`: Validates structural invariants on LLM-produced asset analyses before ScoringAgent computes scores or ranks assets.

### Modified Capabilities
- None.

## Impact

- Affected backend code: `backend/app/analysis/scoring_agent.py`.
- Affected backend tests: `backend/tests/analysis/test_scoring_agent.py`.
- No API contract, database schema, frontend, or dependency changes are expected.
