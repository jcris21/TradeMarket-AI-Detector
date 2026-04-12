"""Tests for ScreenshotAgent — Playwright screenshot capture."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.analysis.models import InvestingComAuthError
from app.analysis.screenshot_agent import capture_charts


@pytest.fixture
def mock_page():
    page = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"\x89PNG\r\n")
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.click = AsyncMock()
    page.fill = AsyncMock()
    return page


@pytest.fixture
def mock_playwright_ctx(mock_page):
    browser = AsyncMock()
    context = AsyncMock()
    context.new_page = AsyncMock(return_value=mock_page)
    browser.new_context = AsyncMock(return_value=context)

    chromium = MagicMock()
    chromium.launch = AsyncMock(return_value=browser)

    pw = AsyncMock()
    pw.__aenter__ = AsyncMock(return_value=pw)
    pw.__aexit__ = AsyncMock(return_value=None)
    pw.chromium = chromium
    return pw


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "true"})
async def test_mock_mode_returns_png_bytes_for_all_tickers():
    result = await capture_charts(["AAPL", "MSFT"])
    assert set(result.keys()) == {"AAPL", "MSFT"}
    for v in result.values():
        assert isinstance(v, bytes)
        assert len(v) > 0


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "", "INVESTING_COM_EMAIL": "", "INVESTING_COM_PASSWORD": ""})
async def test_missing_credentials_raises_auth_error():
    with pytest.raises(InvestingComAuthError):
        await capture_charts(["AAPL"])


@patch.dict(os.environ, {"PLAYWRIGHT_MOCK": "", "INVESTING_COM_EMAIL": "test@example.com", "INVESTING_COM_PASSWORD": "pass"})
@patch("app.analysis.screenshot_agent.async_playwright")
async def test_login_failure_raises_auth_error(mock_pw_factory, mock_playwright_ctx, mock_page):
    # Simulate login form not found
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))
    mock_playwright_ctx.chromium.launch = AsyncMock(
        return_value=AsyncMock(new_context=AsyncMock(return_value=AsyncMock(new_page=AsyncMock(return_value=mock_page))))
    )
    mock_pw_factory.return_value = mock_playwright_ctx

    with pytest.raises(InvestingComAuthError):
        await capture_charts(["AAPL"])
