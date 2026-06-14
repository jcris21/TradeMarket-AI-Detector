"""Data models for the technical analysis pipeline."""

import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel


@dataclass(frozen=True)
class TechnicalIndicators:
    """Computed technical indicators for one ticker."""

    ticker: str
    current_price: float
    macd_signal: Literal["bullish_crossover", "bearish_crossover", "neutral"]
    macd_histogram: float
    rsi: float
    volume_ratio: float  # current volume / 20-day SMA
    support_1: float     # 20-period low
    support_2: float     # 40-period low
    resistance_1: float  # 20-period high
    resistance_2: float  # 40-period high
    atr_14: float | None = field(default=None)
    atr_14_pct: float | None = field(default=None)


class AssetAnalysis(BaseModel):
    """LLM analysis output for one ticker, with optional scoring."""

    ticker: str
    signal: Literal["BUY", "WAIT", "AVOID"]
    confidence: float
    entry_price: float
    target_price: float
    stop_loss: float
    risk_reward_ratio: float
    support_validated: bool
    indicators_summary: dict
    argument: str
    score: float | None = None
    score_delta: float | None = None
    rank: int | None = None
    expected_gain_per10: float | None = None
    expected_loss_per10: float | None = None
    expected_value_per10: float | None = None
    hit_rate_used: float | None = None
    hit_rate_source: str | None = None
    atr_14: float | None = None
    atr_14_pct: float | None = None
    stop_viable: bool | None = None

    def to_db_row(self, run_id: str) -> dict:
        """Convert to a dict suitable for save_analysis_results()."""
        return {
            "run_id": run_id,
            "ticker": self.ticker,
            "rank": self.rank,
            "score": self.score,
            "score_delta": self.score_delta,
            "signal": self.signal,
            "confidence": self.confidence,
            "risk_reward_ratio": self.risk_reward_ratio,
            "entry_price": self.entry_price,
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "support_validated": self.support_validated,
            "argument": self.argument,
            "indicators_summary": json.dumps(self.indicators_summary),
            "screenshot_path": None,
            "expected_gain_per10": self.expected_gain_per10,
            "expected_loss_per10": self.expected_loss_per10,
            "expected_value_per10": self.expected_value_per10,
            "hit_rate_used": self.hit_rate_used,
            "hit_rate_source": self.hit_rate_source,
            "atr_14_pct": self.atr_14_pct,
            "stop_viable": int(self.stop_viable) if self.stop_viable is not None else None,
        }


class AnalysisResult(BaseModel):
    """Complete output of one analysis run."""

    run_id: str
    analyzed_at: str
    assets: list[AssetAnalysis]   # all analyzed (ranked + unranked)
    top_5: list[AssetAnalysis]    # filtered and sorted Top N
    errors: list[dict]            # [{ticker, error_message}]
    duration_seconds: float


class DataFetchError(Exception):
    """Raised when yfinance returns no data for a ticker."""

    def __init__(self, ticker: str) -> None:
        super().__init__(f"No data available for {ticker}")
        self.ticker = ticker


class InvestingComAuthError(Exception):
    """Raised when Playwright cannot log in to investing.com."""
    pass


class PerformanceResponse(BaseModel):
    """Response shape for GET /api/analysis/performance."""

    phase_gate_active: bool
    phase: int = 0
    phase_banner: str = ""
    calibration_count: int
    total_signals: int
    target_hits: int
    stop_hits: int
    expired: int
    orphaned_count: int
    hit_ratio: float | None
    profit_factor: float | None
    realized_rr: float | None
    hr_status: str | None
    pf_status: str | None
    rr_status: str | None
    below_breakeven: bool
