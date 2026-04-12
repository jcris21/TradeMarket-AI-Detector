"""VisionAgent — analyzes chart screenshots + numerical indicators via LLM vision."""

import asyncio
import base64
import json
import logging

from litellm import completion
from pydantic import ValidationError

from .models import AssetAnalysis, TechnicalIndicators

logger = logging.getLogger(__name__)

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

_SYSTEM_PROMPT = """You are an expert technical analyst. You will receive:
1. A chart screenshot from investing.com (when available)
2. Pre-computed numerical indicators (MACD, RSI, Volume, pivot points)

Your task:
- Validate the support and resistance levels visible in the chart
- Calculate the risk/reward ratio: (target_price - entry_price) / (entry_price - stop_loss)
- entry_price = current price
- stop_loss = nearest validated support (S1 or S2)
- target_price = nearest validated resistance (R1 or R2)
- Assess signal as BUY (clear bullish setup), WAIT (mixed signals), or AVOID (bearish)

Respond ONLY with valid JSON matching this exact schema:
{
  "ticker": string,
  "signal": "BUY" | "WAIT" | "AVOID",
  "confidence": float (0.0-1.0),
  "entry_price": float,
  "target_price": float,
  "stop_loss": float,
  "risk_reward_ratio": float,
  "support_validated": boolean,
  "indicators_summary": {"macd": string, "rsi": float, "volume": string},
  "argument": string (2-4 sentences explaining the setup)
}"""


def _build_messages(indicators: TechnicalIndicators, screenshot: bytes | None) -> list[dict]:
    """Build the LLM messages list with optional vision content."""
    numeric_text = (
        f"Ticker: {indicators.ticker}\n"
        f"Current Price: ${indicators.current_price:.2f}\n"
        f"MACD Signal: {indicators.macd_signal} (histogram: {indicators.macd_histogram})\n"
        f"RSI(14): {indicators.rsi:.1f}\n"
        f"Volume Ratio vs 20D SMA: {indicators.volume_ratio:.2f}x\n"
        f"Support S1: ${indicators.support_1:.2f} | S2: ${indicators.support_2:.2f}\n"
        f"Resistance R1: ${indicators.resistance_1:.2f} | R2: ${indicators.resistance_2:.2f}\n"
    )

    if screenshot is not None:
        b64 = base64.b64encode(screenshot).decode()
        user_content = [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": f"Numerical indicators:\n{numeric_text}\nAnalyze and respond with JSON."},
        ]
    else:
        user_content = (
            f"No chart screenshot available. Use only numerical indicators:\n"
            f"{numeric_text}\nAnalyze and respond with JSON."
        )

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _degraded_result(ticker: str) -> AssetAnalysis:
    return AssetAnalysis(
        ticker=ticker,
        signal="AVOID",
        confidence=0.0,
        entry_price=0.0,
        target_price=0.0,
        stop_loss=0.0,
        risk_reward_ratio=0.0,
        support_validated=False,
        indicators_summary={},
        argument="Analysis unavailable due to an error.",
    )


async def analyze_asset(
    indicators: TechnicalIndicators,
    screenshot: bytes | None,
) -> AssetAnalysis:
    """Call the LLM to analyze one asset. Never raises — returns degraded result on error."""
    messages = _build_messages(indicators, screenshot)

    try:
        response = await asyncio.to_thread(
            completion,
            model=MODEL,
            messages=messages,
            reasoning_effort="low",
            extra_body=EXTRA_BODY,
        )
        content = response.choices[0].message.content
        result = AssetAnalysis.model_validate_json(content)

        # Force support_validated=False when no screenshot was provided
        if screenshot is None:
            result = result.model_copy(update={"support_validated": False})

        return result

    except (ValidationError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("VisionAgent parse error for %s: %s", indicators.ticker, exc)
        return _degraded_result(indicators.ticker)
    except Exception as exc:
        logger.warning("VisionAgent LLM error for %s: %s", indicators.ticker, exc)
        return _degraded_result(indicators.ticker)
