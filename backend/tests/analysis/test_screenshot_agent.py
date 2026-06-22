"""Tests for ScreenshotAgent — headless Chromium capture."""

from unittest.mock import AsyncMock, patch

import pytest

from app.analysis.screenshot_agent import ScreenshotAgent, ScreenshotError, ScreenshotTimeoutError


def _make_playwright_mock(page_screenshot: bytes | None = b"\x89PNG\r\n", nav_exc: Exception | None = None):
    """Build a mock async_playwright context that returns a page yielding png_bytes."""
    page = AsyncMock()
    if nav_exc is not None:
        page.goto.side_effect = nav_exc
    else:
        page.goto.return_value = None
    page.screenshot.return_value = page_screenshot

    browser = AsyncMock()
    browser.new_page.return_value = page
    browser.close = AsyncMock()

    pw = AsyncMock()
    pw.chromium.launch.return_value = browser

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=pw)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, browser


@patch("app.analysis.screenshot_agent.async_playwright")
async def test_capture_returns_png_bytes(mock_pw):
    cm, _ = _make_playwright_mock(b"\x89PNG\r\n")
    mock_pw.return_value = cm
    agent = ScreenshotAgent()
    result = await agent.capture("https://example.com/chart")
    assert result == b"\x89PNG\r\n"


@patch("app.analysis.screenshot_agent.async_playwright")
async def test_capture_timeout_raises_screenshot_timeout_error(mock_pw):
    class TimeoutError(Exception):
        pass

    cm, browser = _make_playwright_mock(nav_exc=TimeoutError("Timeout 30000ms exceeded"))
    mock_pw.return_value = cm
    agent = ScreenshotAgent()
    with pytest.raises(ScreenshotTimeoutError):
        await agent.capture("https://example.com/chart", timeout_ms=30_000)
    browser.close.assert_called_once()


@patch("app.analysis.screenshot_agent.async_playwright")
async def test_capture_navigation_error_raises_screenshot_error(mock_pw):
    cm, browser = _make_playwright_mock(nav_exc=ConnectionRefusedError("Connection refused"))
    mock_pw.return_value = cm
    agent = ScreenshotAgent()
    with pytest.raises(ScreenshotError):
        await agent.capture("https://example.com/chart")
    browser.close.assert_called_once()


@patch("app.analysis.screenshot_agent.async_playwright")
async def test_browser_always_closed_in_finally_on_success(mock_pw):
    cm, browser = _make_playwright_mock(b"\x89PNG\r\n")
    mock_pw.return_value = cm
    agent = ScreenshotAgent()
    await agent.capture("https://example.com/chart")
    browser.close.assert_called_once()
