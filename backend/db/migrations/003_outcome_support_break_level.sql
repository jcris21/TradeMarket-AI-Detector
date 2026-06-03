-- Migration 003: Add support_break_level column to analysis_results
-- Additive-only change: existing rows get NULL, no data loss.
ALTER TABLE analysis_results ADD COLUMN support_break_level TEXT;

CREATE INDEX IF NOT EXISTS idx_analysis_outcome ON analysis_results(outcome);
