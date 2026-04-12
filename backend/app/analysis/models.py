"""Data models for the technical analysis pipeline."""

import json
from dataclasses import dataclass
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
    rank: int | None = None

    def to_db_row(self, run_id: str) -> dict:
        """Convert to a dict suitable for save_analysis_results()."""
        return {
            "run_id": run_id,
            "ticker": self.ticker,
            "rank": self.rank,
            "score": self.score,
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
