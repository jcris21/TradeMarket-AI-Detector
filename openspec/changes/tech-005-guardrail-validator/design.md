## Context

The technical analysis pipeline treats VisionAgent output as an `AssetAnalysis` object and then passes it to ScoringAgent for score computation, bet-size pre-computation, filtering, and ranking. Pydantic validates the output shape, but it does not enforce trading invariants such as `stop_loss < entry_price < target_price`.

Because VisionAgent is backed by an LLM, malformed but schema-valid values can cross the agentic boundary. The guardrail belongs immediately before scoring because ScoringAgent is the first deterministic business-rule layer after the LLM output.

## Goals / Non-Goals

**Goals:**
- Validate every `AssetAnalysis` before score computation, bet-size computation, qualification, and ranking.
- Mark structurally invalid assets with `rank=None`.
- Surface structural validation failures through the existing `AnalysisResult.errors` channel.
- Keep valid-asset scoring, rank ordering, bet-size fields, and score-delta behavior unchanged.

**Non-Goals:**
- Do not change VisionAgent prompting or LLM response parsing.
- Do not add frontend behavior or dashboard copy.
- Do not change the database schema or public API response shape.
- Do not reject semantically weak but structurally valid analyses, such as low confidence or low risk/reward ratio; those remain scoring/filtering concerns.

## Decisions

1. Add a pure `validate_asset_analysis(asset: AssetAnalysis) -> tuple[bool, str]` helper in `scoring_agent.py`.

   Rationale: A pure helper is simple to unit test and keeps the guardrail colocated with the deterministic scoring boundary. It avoids coupling validation to the orchestrator, repository, or dashboard.

   Alternative considered: enforce invariants in the `AssetAnalysis` Pydantic model. That would make degraded or diagnostic assets harder to represent and could cause VisionAgent parsing to fail earlier than desired. The requirement is to quarantine invalid analyses before scoring, not to make the model globally unrepresentable.

2. Run validation before the scoring loop.

   Rationale: Invalid assets must not receive score, score_delta, expected gain/loss/value, or rank values derived from inverted prices. This makes the guardrail a hard boundary between LLM output and business scoring.

   Alternative considered: validate inside the `qualifies()` filter. That would still allow invalid assets to receive computed scores and bet-size values, which weakens the boundary.

3. Preserve `score_and_rank()` compatibility where practical and add an error-producing scoring path for orchestration.

   Rationale: Existing tests and callers expect a ranked asset list. The orchestration layer already has `AnalysisResult.errors`, so structural errors should be appended there without changing the public API response shape.

   Implementation can use a small result object, tuple, or companion helper as long as:
   - `score_and_rank()` continues to return `list[AssetAnalysis]` for existing callers, or all callers/tests are updated consistently.
   - `run_analysis()` includes structural invalid errors in `AnalysisResult.errors`.
   - Invalid assets remain present in `assets` with `rank=None`.

4. Use stable error messages prefixed with `structural_invalid:`.

   Rationale: Tests and downstream diagnostics need deterministic messages. The prefix separates guardrail failures from data-fetch and database-write errors.

## Risks / Trade-offs

- Invalid assets may no longer get score or bet-size fields populated -> This is intentional because those values would be computed from corrupt trade parameters.
- Some existing tests may assume every valid-looking `AssetAnalysis` receives a score -> Add focused regression coverage for valid assets and adjust only tests that intentionally create invalid data.
- The current implementation has no separate scoring error return -> Implement the smallest compatible integration so orchestration can append guardrail errors to the existing `errors` list.
