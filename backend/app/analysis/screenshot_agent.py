"""ScreenshotAgent — captures investing.com chart screenshots via Playwright."""

import logging
import os

from playwright.async_api import async_playwright

from .models import InvestingComAuthError

logger = logging.getLogger(__name__)

# Minimal 1x1 transparent PNG for mock mode
_MOCK_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)

# investing.com slug mapping for default tickers
_TICKER_SLUGS: dict[str, str] = {
    "AAPL": "apple-computer-inc",
    "GOOGL": "alphabet-inc",
    "MSFT": "microsoft-corp",
    "AMZN": "amazon-com-inc",
    "TSLA": "tesla-motors",
    "NVDA": "nvidia-corp",
    "META": "meta-platforms-inc",
    "JPM": "jpmorgan-chase",
    "V": "visa",
    "NFLX": "netflix-inc",
}

_CHART_INTERVAL_MAP = {
    "1D": "1D",
    "1W": "1W",
    "1M": "1M",
}

SCREENSHOT_TIMEOUT = 30_000  # ms


async def _login(page) -> None:
    """Log in to investing.com. Raises InvestingComAuthError on failure."""
    email = os.environ.get("INVESTING_COM_EMAIL", "")
    password = os.environ.get("INVESTING_COM_PASSWORD", "")
    if not email or not password:
        raise InvestingComAuthError("INVESTING_COM_EMAIL and INVESTING_COM_PASSWORD must be set")

    try:
        await page.goto("https://www.investing.com/", wait_until="domcontentloaded", timeout=30_000)
        # Accept cookies if banner present
        try:
            await page.click("#onetrust-accept-btn-handler", timeout=5_000)
        except Exception:
            pass

        # Open sign-in form
        await page.click('[data-test="sign-in-btn"]', timeout=10_000)
        await page.wait_for_selector('input[name="email"]', timeout=10_000)
        await page.fill('input[name="email"]', email)
        await page.fill('input[name="password"]', password)
        await page.click('[data-test="submit-btn"]', timeout=10_000)
        # Wait for login to complete (user menu appears)
        await page.wait_for_selector('[data-test="user-menu"]', timeout=15_000)
        logger.info("Logged in to investing.com")
    except InvestingComAuthError:
        raise
    except Exception as exc:
        raise InvestingComAuthError(f"Login failed: {exc}") from exc


async def _get_slug(page, ticker: str) -> str | None:
    """Return the investing.com URL slug for a ticker, or None if not found."""
    if ticker in _TICKER_SLUGS:
        return _TICKER_SLUGS[ticker]
    # Attempt search for unknown tickers
    try:
        await page.goto(
            f"https://www.investing.com/search/?q={ticker}",
            wait_until="domcontentloaded",
            timeout=15_000,
        )
        await page.wait_for_selector(".js-inner-all-results-quote-item", timeout=8_000)
        href = await page.get_attribute(".js-inner-all-results-quote-item a", "href")
        if href and "/equities/" in href:
            return href.split("/equities/")[1].split("?")[0].rstrip("/")
    except Exception:
        pass
    return None


async def _capture_one(page, ticker: str, interval: str) -> bytes | None:
    """Navigate to a ticker chart page and return a screenshot, or None on failure."""
    slug = await _get_slug(page, ticker)
    if slug is None:
        logger.warning("No slug found for %s — skipping screenshot", ticker)
        return None

    try:
        url = f"https://www.investing.com/equities/{slug}"
        await page.goto(url, wait_until="domcontentloaded", timeout=SCREENSHOT_TIMEOUT)

        # Set chart interval if controls are visible
        try:
            interval_label = _CHART_INTERVAL_MAP.get(interval, "1D")
            await page.click(f'[data-period="{interval_label}"]', timeout=5_000)
        except Exception:
            pass

        await page.wait_for_load_state("networkidle", timeout=SCREENSHOT_TIMEOUT)

        # Screenshot the chart canvas area
        chart_el = await page.query_selector("#technicalChart, canvas.chart-canvas, #chart")
        if chart_el:
            screenshot = await chart_el.screenshot(timeout=SCREENSHOT_TIMEOUT)
        else:
            # Fall back to full viewport screenshot
            screenshot = await page.screenshot(full_page=False, timeout=SCREENSHOT_TIMEOUT)

        logger.debug("Captured screenshot for %s (%d bytes)", ticker, len(screenshot))
        return screenshot

    except Exception as exc:
        logger.warning("Screenshot failed for %s: %s", ticker, exc)
        return None


async def capture_charts(
    tickers: list[str],
    interval: str | None = None,
) -> dict[str, bytes | None]:
    """Capture chart screenshots for all tickers in a single Playwright session.

    If PLAYWRIGHT_MOCK=true, returns dummy PNG bytes without launching a browser.
    Raises InvestingComAuthError if credentials are missing or login fails.
    Returns dict[ticker, bytes | None] — None when a ticker's screenshot failed.
    """
    if os.environ.get("PLAYWRIGHT_MOCK", "").lower() == "true":
        return {t: _MOCK_PNG for t in tickers}

    chart_interval = interval or os.environ.get("INVESTING_COM_CHART_INTERVAL", "1D")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        await _login(page)

        results: dict[str, bytes | None] = {}
        for ticker in tickers:
            results[ticker] = await _capture_one(page, ticker, chart_interval)

        await browser.close()

    return results
