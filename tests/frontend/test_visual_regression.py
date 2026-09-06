"""
tests/frontend/test_visual_regression.py

NEXUS AI Trading System - Visual Regression Tests

This test suite captures screenshots of critical UI components and pages
and compares them against approved baseline images to detect unintended
visual changes.

It covers:
- Dashboard, Trading, Portfolio, Settings, and Authentication pages
- Light and dark themes
- Responsive views (desktop, tablet, mobile)
- Interactive states (hover, active, focus)
- Dynamic content (charts, order books, etc.)

Uses Playwright's built-in screenshot comparison with configurable thresholds.

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import logging
import pytest
from playwright.sync_api import Page, BrowserContext, expect
from typing import Dict, Any, Optional
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
BASE_URL = os.getenv("NEXUS_FRONTEND_URL", "http://localhost:3000")
API_URL = os.getenv("NEXUS_API_URL", "http://localhost:8000")
DEFAULT_TIMEOUT = 30000

# Screenshot directories
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
BASELINE_DIR = os.path.join(os.path.dirname(__file__), "baseline")
DIFF_DIR = os.path.join(os.path.dirname(__file__), "diff")

# Ensure directories exist
for d in [SCREENSHOT_DIR, BASELINE_DIR, DIFF_DIR]:
    os.makedirs(d, exist_ok=True)

# Viewport configurations
VIEWPORTS = [
    {"name": "desktop", "width": 1920, "height": 1080},
    {"name": "tablet", "width": 768, "height": 1024},
    {"name": "mobile", "width": 375, "height": 667},
]

# Pages to test
PAGES = [
    {"path": "/dashboard", "name": "dashboard"},
    {"path": "/trading/AAPL", "name": "trading"},
    {"path": "/portfolio", "name": "portfolio"},
    {"path": "/settings/general", "name": "settings"},
    {"path": "/markets", "name": "markets"},
    {"path": "/analytics", "name": "analytics"},
]

# Components to test on the dashboard
COMPONENTS = [
    {"selector": ".metric-card", "name": "metric_card"},
    {"selector": ".chart-container", "name": "chart"},
    {"selector": ".recent-trades", "name": "recent_trades"},
    {"selector": ".open-positions", "name": "open_positions"},
]

# Snapshot configuration
SNAPSHOT_CONFIG = {
    "threshold": 0.2,  # 0.2% pixel difference allowed
    "max_diff_pixels": 100,  # max number of differing pixels
    "output": DIFF_DIR,
}


@pytest.fixture(scope="function")
def page_context(browser: BrowserContext) -> Page:
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )
    page = context.new_page()
    page.set_default_timeout(DEFAULT_TIMEOUT)
    yield page
    context.close()


@pytest.fixture(scope="function")
def authenticated_page(page_context: Page) -> Page:
    """Log in once for authenticated pages."""
    page = page_context
    page.goto(BASE_URL + "/authentication/login")
    page.fill("input[name='email']", "test@nexusquantum.com")
    page.fill("input[name='password']", "Test@123")
    page.click("button[type='submit']")
    page.wait_for_url(re.compile(r"/dashboard"), timeout=10000)
    expect(page).to_have_url(re.compile(r"/dashboard"))
    return page


def take_screenshot(page: Page, name: str, baseline: bool = False):
    """Capture a screenshot and optionally save as baseline."""
    path = os.path.join(BASELINE_DIR if baseline else SCREENSHOT_DIR, f"{name}.png")
    page.screenshot(path=path, full_page=True)
    logger.info(f"Screenshot saved to {path}")
    return path


def compare_screenshot(page: Page, name: str):
    """Use Playwright's built-in screenshot comparison."""
    # This will compare against a baseline image in the baseline directory.
    # The baseline image should be named {name}.png.
    try:
        expect(page).to_have_screenshot(
            os.path.join(BASELINE_DIR, f"{name}.png"),
            threshold=SNAPSHOT_CONFIG["threshold"],
            max_diff_pixels=SNAPSHOT_CONFIG["max_diff_pixels"],
        )
        logger.info(f"Screenshot comparison passed for {name}")
        return True
    except AssertionError as e:
        logger.error(f"Screenshot comparison failed for {name}: {e}")
        # Save the diff for manual inspection
        page.screenshot(path=os.path.join(DIFF_DIR, f"{name}.diff.png"), full_page=True)
        raise


# ----- Tests ------

@pytest.mark.visual
@pytest.mark.parametrize("viewport", VIEWPORTS, ids=lambda v: v["name"])
def test_dashboard_visual_consistency(authenticated_page: Page, viewport: Dict[str, Any]):
    """Verify the dashboard UI remains visually consistent across viewports."""
    page = authenticated_page
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
    page.goto(BASE_URL + "/dashboard")
    page.wait_for_selector("main", state="visible")
    # Wait for any dynamic content (charts, loading)
    page.wait_for_load_state("networkidle")

    name = f"dashboard_{viewport['name']}"
    compare_screenshot(page, name)
    # Also save the screenshot for debugging
    take_screenshot(page, name, baseline=False)


@pytest.mark.visual
@pytest.mark.parametrize("viewport", VIEWPORTS, ids=lambda v: v["name"])
def test_trading_page_visual_consistency(authenticated_page: Page, viewport: Dict[str, Any]):
    """Verify the trading page UI across viewports."""
    page = authenticated_page
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
    page.goto(BASE_URL + "/trading/AAPL")
    page.wait_for_selector(".order-book, .trade-form", state="visible")
    page.wait_for_load_state("networkidle")

    name = f"trading_{viewport['name']}"
    compare_screenshot(page, name)
    take_screenshot(page, name, baseline=False)


@pytest.mark.visual
@pytest.mark.parametrize("viewport", VIEWPORTS, ids=lambda v: v["name"])
def test_portfolio_page_visual_consistency(authenticated_page: Page, viewport: Dict[str, Any]):
    """Verify the portfolio page UI across viewports."""
    page = authenticated_page
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
    page.goto(BASE_URL + "/portfolio")
    page.wait_for_selector(".portfolio-summary, table", state="visible")
    page.wait_for_load_state("networkidle")

    name = f"portfolio_{viewport['name']}"
    compare_screenshot(page, name)
    take_screenshot(page, name, baseline=False)


@pytest.mark.visual
@pytest.mark.parametrize("viewport", VIEWPORTS, ids=lambda v: v["name"])
def test_settings_page_visual_consistency(authenticated_page: Page, viewport: Dict[str, Any]):
    """Verify the settings page UI across viewports."""
    page = authenticated_page
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
    page.goto(BASE_URL + "/settings/general")
    page.wait_for_selector("form", state="visible")
    page.wait_for_load_state("networkidle")

    name = f"settings_{viewport['name']}"
    compare_screenshot(page, name)
    take_screenshot(page, name, baseline=False)


@pytest.mark.visual
def test_dark_theme_visual_consistency(authenticated_page: Page):
    """Verify dark theme UI consistency."""
    page = authenticated_page
    page.set_viewport_size({"width": 1920, "height": 1080})
    # Navigate to settings and switch to dark mode
    page.goto(BASE_URL + "/settings/appearance")
    page.wait_for_selector("select[name='theme']", state="visible")
    page.select_option("select[name='theme']", "dark")
    page.click("button[type='submit']")
    page.wait_for_selector(".toast-success", timeout=5000)
    # Wait for dark mode to apply (might need to wait a moment)
    page.wait_for_timeout(500)

    # Go to dashboard
    page.goto(BASE_URL + "/dashboard")
    page.wait_for_selector("main", state="visible")
    page.wait_for_load_state("networkidle")

    # Check that body has dark class
    body_class = page.evaluate("document.body.className")
    assert "dark" in body_class or "dark-theme" in body_class, "Dark mode not applied"

    compare_screenshot(page, "dashboard_dark")
    take_screenshot(page, "dashboard_dark", baseline=False)


@pytest.mark.visual
def test_login_page_visual_consistency(page_context: Page):
    """Verify login page visual consistency."""
    page = page_context
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(BASE_URL + "/authentication/login")
    page.wait_for_selector("form", state="visible")

    compare_screenshot(page, "login_desktop")
    take_screenshot(page, "login_desktop", baseline=False)

    # Also test mobile
    page.set_viewport_size({"width": 375, "height": 667})
    compare_screenshot(page, "login_mobile")
    take_screenshot(page, "login_mobile", baseline=False)


@pytest.mark.visual
def test_markets_page_visual_consistency(authenticated_page: Page):
    """Verify markets page visual consistency."""
    page = authenticated_page
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(BASE_URL + "/markets")
    page.wait_for_selector("table", state="visible")
    page.wait_for_load_state("networkidle")

    compare_screenshot(page, "markets_desktop")
    take_screenshot(page, "markets_desktop", baseline=False)


@pytest.mark.visual
def test_charts_interaction_visual(authenticated_page: Page):
    """Test visual consistency when interacting with charts (e.g., timeframe change)."""
    page = authenticated_page
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(BASE_URL + "/trading/AAPL")
    page.wait_for_selector(".chart-container", state="visible")

    # Change timeframe to 1h
    timeframe_selector = page.locator("select[name='timeframe']")
    if timeframe_selector.is_visible():
        timeframe_selector.select_option("1h")
        page.wait_for_timeout(1000)  # Wait for chart update

        compare_screenshot(page, "trading_chart_1h")
        take_screenshot(page, "trading_chart_1h", baseline=False)

    # Change to 1d
    if timeframe_selector.is_visible():
        timeframe_selector.select_option("1d")
        page.wait_for_timeout(1000)
        compare_screenshot(page, "trading_chart_1d")
        take_screenshot(page, "trading_chart_1d", baseline=False)


@pytest.mark.visual
def test_hover_states_visual(authenticated_page: Page):
    """Test visual appearance of hover states."""
    page = authenticated_page
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(BASE_URL + "/dashboard")

    # Hover over a metric card
    card = page.locator(".metric-card").first
    card.hover()
    page.wait_for_timeout(300)  # Allow hover style to apply
    compare_screenshot(page, "metric_card_hover")
    take_screenshot(page, "metric_card_hover", baseline=False)

    # Hover over a navigation link
    nav_link = page.locator("nav a").first
    nav_link.hover()
    page.wait_for_timeout(300)
    compare_screenshot(page, "nav_link_hover")
    take_screenshot(page, "nav_link_hover", baseline=False)

    # Hover over a button
    btn = page.locator("button:has-text('Trade')").first
    if btn.is_visible():
        btn.hover()
        page.wait_for_timeout(300)
        compare_screenshot(page, "button_hover")
        take_screenshot(page, "button_hover", baseline=False)


@pytest.mark.visual
def test_responsive_menu_collapse(authenticated_page: Page):
    """Test visual consistency when menu is collapsed/expanded."""
    page = authenticated_page
    # Start with desktop
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(BASE_URL + "/dashboard")
    page.wait_for_selector("main", state="visible")

    # Collapse sidebar if not already
    collapse_btn = page.locator("button[aria-label='Collapse sidebar']")
    if collapse_btn.is_visible():
        collapse_btn.click()
        page.wait_for_timeout(500)
        compare_screenshot(page, "sidebar_collapsed")
        take_screenshot(page, "sidebar_collapsed", baseline=False)

        # Expand again
        expand_btn = page.locator("button[aria-label='Expand sidebar']")
        if expand_btn.is_visible():
            expand_btn.click()
            page.wait_for_timeout(500)
            compare_screenshot(page, "sidebar_expanded")
            take_screenshot(page, "sidebar_expanded", baseline=False)

    # Mobile view: menu hidden then opened
    page.set_viewport_size({"width": 375, "height": 667})
    page.reload()
    page.wait_for_selector("main", state="visible")
    # Menu should be hidden; open via hamburger
    hamburger = page.locator("button[aria-label='Toggle menu']")
    expect(hamburger).to_be_visible()
    compare_screenshot(page, "mobile_menu_hidden")
    take_screenshot(page, "mobile_menu_hidden", baseline=False)

    hamburger.click()
    page.wait_for_timeout(500)
    compare_screenshot(page, "mobile_menu_open")
    take_screenshot(page, "mobile_menu_open", baseline=False)


@pytest.mark.visual
def test_form_validation_visual(authenticated_page: Page):
    """Test visual display of form validation errors."""
    page = authenticated_page
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(BASE_URL + "/settings/general")
    page.wait_for_selector("form", state="visible")

    # Clear required field and submit
    page.fill("input[name='firstName']", "")
    page.click("button[type='submit']")
    page.wait_for_selector(".error-message", timeout=3000)
    compare_screenshot(page, "form_validation_error")
    take_screenshot(page, "form_validation_error", baseline=False)


@pytest.mark.visual
def test_toast_notifications_visual(authenticated_page: Page):
    """Test visual appearance of toast notifications."""
    page = authenticated_page
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(BASE_URL + "/settings/general")
    # Trigger a success toast by saving
    page.fill("input[name='firstName']", "Test")
    page.click("button[type='submit']")
    page.wait_for_selector(".toast-success", timeout=5000)
    page.wait_for_timeout(500)  # Ensure toast is fully visible
    compare_screenshot(page, "toast_success")
    take_screenshot(page, "toast_success", baseline=False)


@pytest.mark.visual
def test_order_form_visual(authenticated_page: Page):
    """Test visual appearance of the order form in different states."""
    page = authenticated_page
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(BASE_URL + "/trading/AAPL")
    page.wait_for_selector(".trade-form", state="visible")

    # Market order
    market_tab = page.locator("button:has-text('Market')")
    if market_tab.is_visible():
        market_tab.click()
        page.wait_for_timeout(200)
        compare_screenshot(page, "order_form_market")
        take_screenshot(page, "order_form_market", baseline=False)

    # Limit order
    limit_tab = page.locator("button:has-text('Limit')")
    if limit_tab.is_visible():
        limit_tab.click()
        page.wait_for_timeout(200)
        # Fill some values
        page.fill("input[name='qty']", "10")
        page.fill("input[name='limitPrice']", "150.00")
        compare_screenshot(page, "order_form_limit_filled")
        take_screenshot(page, "order_form_limit_filled", baseline=False)

    # Stop order (if available)
    stop_tab = page.locator("button:has-text('Stop')")
    if stop_tab.is_visible():
        stop_tab.click()
        page.wait_for_timeout(200)
        page.fill("input[name='stopPrice']", "145.00")
        compare_screenshot(page, "order_form_stop")
        take_screenshot(page, "order_form_stop", baseline=False)


@pytest.mark.visual
def test_modal_dialog_visual(authenticated_page: Page):
    """Test visual consistency of modal dialogs."""
    page = authenticated_page
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(BASE_URL + "/settings/brokers")
    page.wait_for_selector("button:has-text('Add Broker')", state="visible")
    page.click("button:has-text('Add Broker')")
    page.wait_for_selector(".modal", state="visible")
    compare_screenshot(page, "modal_add_broker")
    take_screenshot(page, "modal_add_broker", baseline=False)

    # Close modal
    page.click(".modal button:has-text('Cancel')")
    page.wait_for_selector(".modal", state="hidden")


# ----- Baseline generation helper (optional) -----
# To generate baseline images, run with --update-baseline flag
@pytest.mark.skip(reason="Helper to generate baselines, not run by default")
def test_generate_baselines(authenticated_page: Page):
    """Generate baseline screenshots for all test cases."""
    # This will run all tests in "baseline mode" by taking screenshots and saving to baseline dir.
    # To run: pytest tests/frontend/test_visual_regression.py -k test_generate_baselines --update-baseline
    pass


# ----- Integration with CI (optional) -----
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "visual: mark test as visual regression test")


def pytest_addoption(parser):
    """Add command-line option to update baseline images."""
    parser.addoption(
        "--update-baseline",
        action="store_true",
        default=False,
        help="Update baseline screenshots",
    )


@pytest.fixture(scope="session")
def update_baseline(request):
    """Fixture to check if baseline update is requested."""
    return request.config.getoption("--update-baseline")
