"""VisionAgent — analyzes chart screenshots + numerical indicators via LLM vision."""

import asyncio
import base64
import json
import logging
import re
from typing import List

from pydantic import ValidationError

from .models import AssetAnalysis, ExtractedLevel, TechnicalIndicators

logger = logging.getLogger(__name__)

MODEL_VISION = "openrouter/openai/gpt-4o"
MODEL_TEXT = "openrouter/openai/gpt-4o-mini"

LEVEL_EXTRACTION_PROMPT = (
    "Analyze this trading chart and identify key support and resistance price levels. "
    "Include both: (1) any horizontal lines already drawn on the chart, and "
    "(2) natural S/R levels visible from price action (swing highs, swing lows, consolidation zones, round numbers). "
    "Return ONLY a JSON array — no explanation, no markdown, no extra text — where each element has exactly these fields: "
    "'type' (string: 'support' or 'resistance'), "
    "'price' (float: the exact price level), "
    "'confidence' (float between 0.0 and 1.0). "
    "Example: [{\"type\": \"support\", \"price\": 195.5, \"confidence\": 0.85}]. "
    "If no levels are identifiable, return an empty array: []."
)

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


def _build_messages(indicators: TechnicalIndicators, screenshot_bytes: bytes | None) -> list[dict]:
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

    if screenshot_bytes is not None:
        b64 = base64.b64encode(screenshot_bytes).decode()
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


def _extract_json(content: str) -> str:
    """Extract JSON from model response, handling code fences and inline text."""
    content = content.strip()
    # 1. Code fence: ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    # 2. Find the first [...] array in the text (model adds narrative around it)
    match = re.search(r"(\[.*\])", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return content


def _validate_prices(result: AssetAnalysis, indicators: TechnicalIndicators) -> AssetAnalysis:
    """Override LLM prices with real DataAgent values to prevent hallucination."""
    entry = indicators.current_price
    stop = result.stop_loss if 0 < result.stop_loss < entry else indicators.support_1
    target = result.target_price if result.target_price > entry else indicators.resistance_1
    rr = round((target - entry) / (entry - stop), 2) if (entry - stop) > 0.01 else 0.0
    return result.model_copy(update={
        "entry_price": round(entry, 2),
        "stop_loss": round(stop, 2),
        "target_price": round(target, 2),
        "risk_reward_ratio": rr,
    })


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


async def _call_llm(messages: list[dict], use_vision: bool) -> str:
    """Call the appropriate model. Vision calls use gpt-4o; text-only uses Cerebras."""
    from litellm import completion

    if use_vision:
        response = await asyncio.to_thread(
            completion,
            model=MODEL_VISION,
            messages=messages,
            max_tokens=400,
        )
    else:
        response = await asyncio.to_thread(
            completion,
            model=MODEL_TEXT,
            messages=messages,
            max_tokens=300,
        )
    return response.choices[0].message.content


async def _call_extract_llm(messages: list) -> str:
    """Call the vision model for level extraction. Isolated for testing."""
    from litellm import completion
    response = await asyncio.to_thread(
        completion,
        model=MODEL_VISION,
        messages=messages,
        max_tokens=512,
    )
    return response.choices[0].message.content


async def extract_levels(image_bytes: bytes) -> List[ExtractedLevel]:
    """Extract support/resistance levels from a trader-uploaded chart image.

    Returns a list of ExtractedLevel objects, or [] on any error or timeout.
    """
    mime = "image/jpeg" if image_bytes[:2] == b"\xff\xd8" else "image/png"
    b64 = base64.b64encode(image_bytes).decode()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": LEVEL_EXTRACTION_PROMPT},
            ],
        }
    ]

    try:
        content = await asyncio.wait_for(_call_extract_llm(messages), timeout=45.0)
        # Write raw response to debug file for inspection
        try:
            import pathlib
            pathlib.Path("extract_levels_debug.txt").write_text(
                f"content type: {type(content)}\ncontent: {content!r}\n", encoding="utf-8"
            )
        except Exception:
            pass
        logger.info("extract_levels raw response: %r", content[:500] if content else None)
        if not content:
            logger.warning("extract_levels: model returned empty/None content")
            return []
        cleaned = _extract_json(content)
        raw = json.loads(cleaned)
        if not isinstance(raw, list):
            logger.warning("extract_levels: response is not a list, got %s", type(raw))
            return []
        return [ExtractedLevel.model_validate(item) for item in raw]
    except asyncio.TimeoutError:
        logger.warning("extract_levels timed out after 45s")
        return []
    except (json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
        logger.warning("extract_levels parse error (%s): %s", type(exc).__name__, exc)
        try:
            import pathlib
            pathlib.Path("extract_levels_debug.txt").write_text(
                f"PARSE ERROR: {type(exc).__name__}: {exc}\ncontent was: {content!r}\n",
                encoding="utf-8"
            )
        except Exception:
            pass
        return []
    except Exception as exc:
        logger.warning("extract_levels model error (%s): %s", type(exc).__name__, exc)
        try:
            import pathlib
            pathlib.Path("extract_levels_debug.txt").write_text(
                f"MODEL ERROR: {type(exc).__name__}: {exc}\n", encoding="utf-8"
            )
        except Exception:
            pass
        return []


async def analyze_asset(
    indicators: TechnicalIndicators,
    screenshot_bytes: bytes | None = None,
) -> AssetAnalysis:
    """Call the LLM to analyze one asset. Never raises — returns degraded result on error.

    Priority: screenshot_bytes > disk path (loaded upstream) > text-only fallback.
    """
    has_screenshot = screenshot_bytes is not None
    messages = _build_messages(indicators, screenshot_bytes)

    try:
        content = _extract_json(await _call_llm(messages, use_vision=has_screenshot))
        result = AssetAnalysis.model_validate_json(content)

        if not has_screenshot:
            result = result.model_copy(update={"support_validated": False})

        return _validate_prices(result, indicators)

    except (ValidationError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("VisionAgent parse error for %s: %s", indicators.ticker, exc)
        return _degraded_result(indicators.ticker)
    except Exception as exc:
        logger.warning("VisionAgent LLM error for %s: %s — retrying text-only", indicators.ticker, exc)
        # Retry without image if vision call failed
        if has_screenshot:
            try:
                text_messages = _build_messages(indicators, None)
                content = _extract_json(await _call_llm(text_messages, use_vision=False))
                result = AssetAnalysis.model_validate_json(content)
                result = result.model_copy(update={"support_validated": False})
                return _validate_prices(result, indicators)
            except Exception as retry_exc:
                logger.warning("VisionAgent text-only retry failed for %s: %s", indicators.ticker, retry_exc)
        return _degraded_result(indicators.ticker)
