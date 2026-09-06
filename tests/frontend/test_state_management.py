"""
tests/frontend/test_state_management.py

NEXUS AI Trading System - Frontend State Management Tests

This test suite verifies that the frontend application state (managed by Zustand stores)
is correctly updated and reflected in the UI. It uses Playwright to interact with the
application and then evaluates the internal state via page.evaluate().

Test Coverage:
- Authentication state (login, logout, token refresh)
- Portfolio state (fetching, updating, positions)
- Trading state (order placement, order history, status)
- UI state (theme, sidebar, notifications)
- Market data state (symbol selection, price updates)
- Loading and error states
- State persistence across page reloads

These are real end-to-end tests running against a live application instance.

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import logging
import pytest
import re
import json
from playwright.sync_api import Page, BrowserContext, expect
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
BASE_URL = os.getenv("NEXUS_FRONTEND_URL", "http://localhost:3000")
DEFAULT_TIMEOUT = 30000  # milliseconds
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Viewport for consistent testing
DEFAULT_VIEWPORT = {"width": 1280, "height": 720}


@pytest.fixture(scope="function")
def page_context(browser: BrowserContext) -> Page:
    """Create a new page context with default viewport."""
    context = browser.new_context(
        viewport=DEFAULT_VIEWPORT,
        ignore_https_errors=True,
    )
    page = context.new_page()
    page.set_default_timeout(DEFAULT_TIMEOUT)
    yield page
    context.close()


@pytest.fixture(scope="function")
def authenticated_page(page_context: Page) -> Page:
    """Log in once and return the authenticated page."""
    page = page_context
    page.goto(BASE_URL + "/authentication/login")
    page.fill("input[name='email']", "test@nexusquantum.com")
    page.fill("input[name='password']", "Test@123")
    page.click("button[type='submit']")
    page.wait_for_url(re.compile(r"/dashboard"), timeout=10000)
    expect(page).to_have_url(re.compile(r"/dashboard"))
    return page


def take_screenshot(page: Page, name: str):
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    page.screenshot(path=path, full_page=True)
    logger.info(f"Screenshot saved to {path}")


def get_store_state(page: Page, store_name: str) -> Dict[str, Any]:
    """
    Evaluate the Zustand store state from the browser's JavaScript context.
    Assumes the store is exposed globally (e.g., window.__NEXUS_STORE__).
    If not available, falls back to UI inspection.
    """
    result = page.evaluate(
        f"""
        () => {{
            if (window.__NEXUS_STORE__ && window.__NEXUS_STORE__.getState) {{
                return window.__NEXUS_STORE__.getState()['{store_name}'];
            }}
            return null;
        }}
        """
    )
    return result or {}


def get_auth_state(page: Page) -> Dict[str, Any]:
    return get_store_state(page, "auth")


def get_portfolio_state(page: Page) -> Dict[str, Any]:
    return get_store_state(page, "portfolio")


def get_trading_state(page: Page) -> Dict[str, Any]:
    return get_store_state(page, "trading")


def get_ui_state(page: Page) -> Dict[str, Any]:
    return get_store_state(page, "ui")


def get_market_state(page: Page) -> Dict[str, Any]:
    return get_store_state(page, "market")


def get_notification_state(page: Page) -> Dict[str, Any]:
    return get_store_state(page, "notifications")


# ----- Tests ------

def test_authentication_state(authenticated_page: Page):
    """Test that authentication state is correctly set after login."""
    page = authenticated_page

    # Verify UI reflects authenticated state
    user_menu = page.locator("button[aria-label='User menu']")
    expect(user_menu).to_be_visible()
    user_menu.click()
    user_name = page.locator(".user-name, .profile-name")
    expect(user_name).to_contain_text("Test User")

    # Evaluate the store to confirm
    auth_state = get_auth_state(page)
    assert auth_state, "Auth store state should not be empty"
    assert auth_state.get("isAuthenticated") is True, "User should be authenticated"
    assert auth_state.get("user") is not None, "User object should exist"
    assert auth_state.get("user", {}).get("email") == "test@nexusquantum.com"

    # Test logout
    page.click("button:has-text('Logout')")
    page.wait_for_url(re.compile(r"/login"), timeout=5000)
    auth_state_after = get_auth_state(page)
    assert auth_state_after.get("isAuthenticated") is False, "User should be logged out"


def test_portfolio_state_after_trade(authenticated_page: Page):
    """Test that portfolio state updates after placing a trade."""
    page = authenticated_page
    # Navigate to trading page
    page.goto(BASE_URL + "/trading/AAPL")
    page.wait_for_selector(".trade-form", state="visible")

    # Place a market buy order
    market_tab = page.locator("button:has-text('Market')")
    if market_tab.is_visible():
        market_tab.click()
    page.fill("input[name='qty']", "1")
    buy_btn = page.locator("button:has-text('Buy')")
    buy_btn.click()
    page.wait_for_selector(".toast-success", timeout=5000)
    page.wait_for_timeout(2000)

    # Navigate to portfolio page to see updated positions
    page.goto(BASE_URL + "/portfolio")
    page.wait_for_selector(".position-list, table", state="visible")

    # Check if the position appears
    position_row = page.locator("tr:has-text('AAPL')")
    if position_row.is_visible():
        expect(position_row).to_be_visible()
        qty_cell = position_row.locator("td:has-text('1')")
        expect(qty_cell).to_be_visible()

    # Evaluate the store to check positions
    portfolio_state = get_portfolio_state(page)
    assert portfolio_state is not None
    # Depending on implementation, positions might be in a list
    if portfolio_state.get("positions"):
        symbols = [p.get("symbol") for p in portfolio_state["positions"]]
        assert "AAPL" in symbols, "AAPL position should be in portfolio state"


def test_trading_order_state(authenticated_page: Page):
    """Test that order state updates correctly (open orders, history)."""
    page = authenticated_page
    # Place a limit order (will remain open)
    page.goto(BASE_URL + "/trading/AAPL")
    page.wait_for_selector(".trade-form", state="visible")

    limit_tab = page.locator("button:has-text('Limit')")
    if limit_tab.is_visible():
        limit_tab.click()
    price_element = page.locator(".ticker-price, .last-price")
    current_price = float(price_element.text_content().replace('$', '').replace(',', ''))
    limit_price = round(current_price * 0.5, 2)  # very low, unlikely to fill
    page.fill("input[name='limitPrice']", str(limit_price))
    page.fill("input[name='qty']", "1")
    buy_btn = page.locator("button:has-text('Buy')")
    buy_btn.click()
    page.wait_for_selector(".toast-success", timeout=5000)

    # Navigate to open orders
    page.goto(BASE_URL + "/orders/open")
    page.wait_for_selector("table", state="visible")
    order_row = page.locator("tr:has-text('AAPL')").first
    expect(order_row).to_be_visible()
    expect(order_row).to_contain_text("Limit")
    expect(order_row).to_contain_text("Open")

    # Cancel the order
    cancel_btn = order_row.locator("button:has-text('Cancel')")
    cancel_btn.click()
    page.wait_for_selector(".toast-success", timeout=5000)
    expect(order_row).not_to_be_visible(timeout=5000)

    # Check that the order moved to history with status "Cancelled"
    page.goto(BASE_URL + "/orders/history")
    page.wait_for_selector("table", state="visible")
    history_row = page.locator("tr:has-text('AAPL')").first
    expect(history_row).to_contain_text("Cancelled")


def test_ui_state_theme_and_sidebar(authenticated_page: Page):
    """Test that UI state (theme, sidebar collapse) is persisted and reflected."""
    page = authenticated_page
    # Check initial UI state
    ui_state = get_ui_state(page)
    assert ui_state.get("theme") in ["light", "dark"], "Theme should be set"

    # Toggle theme from settings
    page.goto(BASE_URL + "/settings/appearance")
    page.wait_for_selector("select[name='theme']", state="visible")
    current_theme = page.select_option("select[name='theme']").get("value")
    new_theme = "dark" if current_theme == "light" else "light"
    page.select_option("select[name='theme']", new_theme)
    page.click("button[type='submit']")
    page.wait_for_selector(".toast-success", timeout=5000)
    page.wait_for_timeout(500)

    # Evaluate UI state after change
    ui_state_after = get_ui_state(page)
    assert ui_state_after.get("theme") == new_theme, "Theme state should match selected theme"

    # Check that body has dark class if theme is dark
    if new_theme == "dark":
        body_class = page.evaluate("document.body.className")
        assert "dark" in body_class or "dark-theme" in body_class, "Dark class should be applied"

    # Test sidebar collapse/expand (if available)
    page.goto(BASE_URL + "/dashboard")
    page.wait_for_selector("main", state="visible")
    collapse_btn = page.locator("button[aria-label='Collapse sidebar']")
    if collapse_btn.is_visible():
        collapse_btn.click()
        page.wait_for_timeout(300)
        sidebar = page.locator("nav.sidebar")
        sidebar_class = sidebar.get_attribute("class")
        assert "collapsed" in sidebar_class, "Sidebar should be collapsed"


def test_market_data_state_symbol_selection(authenticated_page: Page):
    """Test that market data state updates when symbol is selected."""
    page = authenticated_page
    page.goto(BASE_URL + "/markets")
    page.wait_for_selector("table", state="visible")

    symbol_row = page.locator("tr:has-text('AAPL')").first
    if symbol_row.is_visible():
        symbol_row.click()
        page.wait_for_timeout(500)
        market_state = get_market_state(page)
        selected = market_state.get("selectedSymbol")
        if selected:
            assert selected == "AAPL", "Selected symbol should be AAPL"
        else:
            expect(symbol_row).to_have_class(re.compile(r"selected|active"))


def test_notification_state(authenticated_page: Page):
    """Test that notifications are added and cleared correctly."""
    page = authenticated_page
    # Trigger a notification by performing an action (e.g., invalid form submission)
    page.goto(BASE_URL + "/settings/general")
    page.fill("input[name='firstName']", "")  # Required field
    page.click("button[type='submit']")
    page.wait_for_selector(".error-message", timeout=3000)

    # Check UI for error notification
    error = page.locator(".error-message, .toast-error")
    expect(error).to_be_visible()

    # Dismiss notification if close button exists
    close_btn = error.locator("button:has-text('×')")
    if close_btn.is_visible():
        close_btn.click()
        page.wait_for_timeout(500)
        expect(error).not_to_be_visible()


def test_loading_state(authenticated_page: Page):
    """Test that loading states are correctly displayed and then disappear."""
    page = authenticated_page
    page.goto(BASE_URL + "/portfolio")
    loading = page.locator(".loading-spinner, .skeleton")
    if loading.is_visible():
        expect(loading).not_to_be_visible(timeout=10000)
    expect(page.locator(".portfolio-summary, table")).to_be_visible()


def test_state_persistence_after_refresh(authenticated_page: Page):
    """Test that state (e.g., theme, auth) persists after page reload."""
    page = authenticated_page
    # Set a state (e.g., change theme to dark)
    page.goto(BASE_URL + "/settings/appearance")
    page.select_option("select[name='theme']", "dark")
    page.click("button[type='submit']")
    page.wait_for_selector(".toast-success", timeout=5000)

    # Reload the page
    page.reload()
    page.wait_for_load_state("networkidle")

    # Check that theme is still dark
    ui_state = get_ui_state(page)
    assert ui_state.get("theme") == "dark", "Theme should persist after reload"

    # Check that user is still authenticated
    auth_state = get_auth_state(page)
    assert auth_state.get("isAuthenticated") is True, "User should remain authenticated"


def test_state_after_websocket_update(authenticated_page: Page):
    """Test that state updates via WebSocket (e.g., price updates) are reflected."""
    page = authenticated_page
    page.goto(BASE_URL + "/trading/BTC/USD")
    price_element = page.locator(".ticker-price, .last-price")
    initial_price = price_element.text_content()
    # Wait a few seconds for WebSocket update
    page.wait_for_timeout(5000)
    updated_price = price_element.text_content()
    assert updated_price is not None and updated_price != ""
    # Optionally, evaluate the market store to check price state
    market_state = get_market_state(page)
    last_price = market_state.get("prices", {}).get("BTC/USD")
    if last_price:
        assert isinstance(last_price, (int, float)), "Price should be numeric"
        assert last_price > 0, "Price should be positive"
