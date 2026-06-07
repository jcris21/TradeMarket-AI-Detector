# Spec: Asset Analysis Guardrails

## Purpose

Validate every LLM-produced `AssetAnalysis` for structural trading invariants before downstream scoring, bet-size computation, qualification, and ranking. Surface guardrail failures through the existing `AnalysisResult.errors` collection.

## Requirements

### Requirement: Validate AssetAnalysis before scoring
The system SHALL validate every LLM-produced `AssetAnalysis` for structural trading invariants before ScoringAgent computes scores, bet-size values, qualification, or rank.

#### Scenario: Valid asset reaches scoring unchanged
- **WHEN** ScoringAgent receives an asset with `entry_price > 0`, `stop_loss < entry_price`, `target_price > entry_price`, and `risk_reward_ratio >= 0`
- **THEN** the asset remains eligible for existing score computation, bet-size computation, qualification, and ranking behavior

#### Scenario: Invalid entry price is rejected
- **WHEN** ScoringAgent receives an asset with `entry_price <= 0`
- **THEN** the asset MUST have `rank=None`
- **THEN** the asset MUST NOT receive score, score_delta, or bet-size values computed from the invalid prices
- **THEN** the analysis result errors MUST include a structural invalid error for that ticker

#### Scenario: Inverted stop loss is rejected
- **WHEN** ScoringAgent receives an asset with `stop_loss >= entry_price`
- **THEN** the asset MUST have `rank=None`
- **THEN** the asset MUST NOT receive score, score_delta, or bet-size values computed from the invalid prices
- **THEN** the analysis result errors MUST include a structural invalid error for that ticker

#### Scenario: Inverted target price is rejected
- **WHEN** ScoringAgent receives an asset with `target_price <= entry_price`
- **THEN** the asset MUST have `rank=None`
- **THEN** the asset MUST NOT receive score, score_delta, or bet-size values computed from the invalid prices
- **THEN** the analysis result errors MUST include a structural invalid error for that ticker

#### Scenario: Negative risk reward ratio is rejected
- **WHEN** ScoringAgent receives an asset with `risk_reward_ratio < 0`
- **THEN** the asset MUST have `rank=None`
- **THEN** the asset MUST NOT receive score, score_delta, or bet-size values computed from the invalid analysis
- **THEN** the analysis result errors MUST include a structural invalid error for that ticker

### Requirement: Surface structural validation errors
The system SHALL surface guardrail failures through the existing `AnalysisResult.errors` collection using deterministic per-ticker error messages.

#### Scenario: Structural error message format
- **WHEN** an asset fails structural validation before scoring
- **THEN** `AnalysisResult.errors` MUST include an item with the asset ticker
- **THEN** the error message MUST begin with `structural_invalid:`
- **THEN** the error message MUST include the failed invariant reason

#### Scenario: Multiple invalid assets are reported independently
- **WHEN** multiple assets fail structural validation in the same analysis run
- **THEN** `AnalysisResult.errors` MUST include one structural invalid error item per invalid asset
- **THEN** valid assets in the same run MUST continue through normal scoring and ranking
