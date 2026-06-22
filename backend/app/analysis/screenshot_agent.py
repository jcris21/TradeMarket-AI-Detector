"""ScreenshotAgent — captures chart screenshots via headless Chromium (Playwright)."""

import logging

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


class ScreenshotTimeoutError(Exception):
    """Raised when page navigation does not reach networkidle within timeout_ms."""


class ScreenshotError(Exception):
    """Raised when a non-timeout navigation or browser error occurs."""


class ScreenshotAgent:
    """Captures a full-viewport PNG screenshot of a URL using a single headless Chromium session."""

    async def capture(self, source_url: str, timeout_ms: int = 30_000) -> bytes:
        """Navigate to source_url and return raw PNG bytes.

        Opens one browser instance, captures the screenshot, and always closes
        the browser via try/finally — even on error.
        """
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                try:
                    await page.goto(
                        source_url,
                        wait_until="networkidle",
                        timeout=timeout_ms,
                    )
                except Exception as exc:
                    exc_name = type(exc).__name__
                    if "Timeout" in exc_name or "timeout" in str(exc).lower():
                        raise ScreenshotTimeoutError(
                            f"Page did not reach networkidle within {timeout_ms}ms: {source_url}"
                        ) from exc
                    raise ScreenshotError(
                        f"Navigation failed for {source_url}: {exc}"
                    ) from exc
                png_bytes: bytes = await page.screenshot(full_page=False)
                return png_bytes
            finally:
                await browser.close()
