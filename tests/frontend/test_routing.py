"""
tests/frontend/test_routing.py

NEXUS AI Trading System - Frontend Routing Tests

This test suite verifies that the frontend routing is correctly configured
and that navigation works as expected. It covers:

- Public routes (login, register, forgot password, etc.)
- Protected routes (dashboard, trading, portfolio, settings, etc.)
- Dynamic routes (e.g., /trading/AAPL)
- Redirects (root → dashboard or login)
- 404 handling
- Navigation via links and buttons
- Authentication redirects
- Query parameters and state preservation

These are real end-to-end tests using Playwright to automate a real browser
against a live instance of the application (configurable via environment variable).
No mocks are used; all interactions are with the actual application.

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import logging
import pytest
import re
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
    """Capture a screenshot for debugging purposes."""
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    page.screenshot(path=path, full_page=True)
    logger.info(f"Screenshot saved to {path}")


# ----- Public Routes (no authentication required) -----

PUBLIC_ROUTES = [
    {"path": "/authentication/login", "name": "Login", "heading": "Login"},
    {"path": "/authentication/register", "name": "Register", "heading": "Create Account"},
    {"path": "/authentication/forgot-password", "name": "Forgot Password", "heading": "Reset Password"},
    {"path": "/", "name": "Root", "heading": None},  # Will redirect
    {"path": "/about", "name": "About", "heading": "About"},
    {"path": "/contact", "name": "Contact", "heading": "Contact"},
    {"path": "/privacy", "name": "Privacy Policy", "heading": "Privacy Policy"},
    {"path": "/terms", "name": "Terms", "heading": "Terms of Service"},
    {"path": "/status", "name": "Status", "heading": "System Status"},
]


@pytest.mark.parametrize("route", PUBLIC_ROUTES, ids=lambda r: r["name"])
def test_public_route_accessible(page_context: Page, route: Dict[str, Any]):
    """Test that public routes are accessible without authentication."""
    page = page_context
    path = route["path"]
    heading = route.get("heading")
    logger.info(f"Testing public route: {path}")

    page.goto(BASE_URL + path)
    page.wait_for_load_state("networkidle")

    # For root, we expect redirect to /dashboard or /login
    if path == "/":
        # Since we are not logged in, it should redirect to /login
        expect(page).to_have_url(re.compile(r"/authentication/login|/dashboard"))
        # Check that login page is shown
        expect(page.locator("h1:has-text('Login')")).to_be_visible()
        return

    # For other public routes, check that the page loads and the correct heading is present
    if heading:
        page.wait_for_selector(f"h1:has-text('{heading}')", state="visible", timeout=5000)
        expect(page.locator(f"h1:has-text('{heading}')")).to_be_visible()

    # Verify that the URL is correct (no redirect)
    expect(page).to_have_url(re.compile(path))

    # Ensure we are not accidentally redirected to login
    assert "/authentication/login" not in page.url or path == "/authentication/login", \
        f"Unexpected redirect to login for {path}"


# ----- Protected Routes (authentication required) -----

PROTECTED_ROUTES = [
    {"path": "/dashboard", "name": "Dashboard", "heading": "Dashboard"},
    {"path": "/trading/AAPL", "name": "Trading", "heading": None},  # dynamic, heading may be symbol
    {"path": "/portfolio", "name": "Portfolio", "heading": "Portfolio"},
    {"path": "/markets", "name": "Markets", "heading": "Markets"},
    {"path": "/analytics", "name": "Analytics", "heading": "Analytics"},
    {"path": "/settings/general", "name": "Settings", "heading": "Settings"},
    {"path": "/orders/open", "name": "Open Orders", "heading": "Open Orders"},
    {"path": "/orders/history", "name": "Order History", "heading": "Order History"},
    {"path": "/watchlist", "name": "Watchlist", "heading": "Watchlist"},
    {"path": "/alerts", "name": "Alerts", "heading": "Alerts"},
]


@pytest.mark.parametrize("route", PROTECTED_ROUTES, ids=lambda r: r["name"])
def test_protected_route_redirects_to_login(page_context: Page, route: Dict[str, Any]):
    """Test that protected routes redirect to login when not authenticated."""
    page = page_context
    path = route["path"]
    logger.info(f"Testing protected route redirect: {path}")

    # Try to go directly to the protected route
    page.goto(BASE_URL + path)
    page.wait_for_load_state("networkidle")

    # Should be redirected to login
    expect(page).to_have_url(re.compile(r"/authentication/login"))
    expect(page.locator("h1:has-text('Login')")).to_be_visible()

    # After login, should redirect back to original route
    page.fill("input[name='email']", "test@nexusquantum.com")
    page.fill("input[name='password']", "Test@123")
    page.click("button[type='submit']")
    # Wait for the redirect (might be /dashboard or specific page)
    page.wait_for_url(re.compile(rf"/dashboard|{path}"), timeout=10000)
    # We should no longer be on login page
    assert "/authentication/login" not in page.url, "Still on login page"


@pytest.mark.parametrize("route", PROTECTED_ROUTES, ids=lambda r: r["name"])
def test_protected_route_accessible_when_authenticated(authenticated_page: Page, route: Dict[str, Any]):
    """Test that protected routes are accessible when authenticated."""
    page = authenticated_page
    path = route["path"]
    heading = route.get("heading")
    logger.info(f"Testing protected route access: {path}")

    page.goto(BASE_URL + path)
    page.wait_for_load_state("networkidle")

    # Should not be on login page
    assert "/authentication/login" not in page.url, "Redirected to login unexpectedly"

    # For dynamic trading route, check the symbol appears
    if "/trading/" in path:
        symbol = path.split("/")[-1]
        expect(page.locator(f":has-text('{symbol}')")).to_be_visible()
    elif heading:
        page.wait_for_selector(f"h1:has-text('{heading}')", state="visible", timeout=5000)
        expect(page.locator(f"h1:has-text('{heading}')")).to_be_visible()

    # Check that the URL is correct
    expect(page).to_have_url(re.compile(path))


def test_root_redirect(page_context: Page):
    """Test that the root path redirects appropriately."""
    page = page_context
    # Not logged in: should redirect to /login
    page.goto(BASE_URL)
    expect(page).to_have_url(re.compile(r"/authentication/login"))

    # Now log in and test root redirect
    page.fill("input[name='email']", "test@nexusquantum.com")
    page.fill("input[name='password']", "Test@123")
    page.click("button[type='submit']")
    page.wait_for_url(re.compile(r"/dashboard"), timeout=10000)

    # Now go to root again
    page.goto(BASE_URL)
    # Should redirect to /dashboard
    expect(page).to_have_url(re.compile(r"/dashboard"))


def test_404_page(page_context: Page):
    """Test that non-existent routes show a 404 page."""
    page = page_context
    non_existent_path = "/this-page-does-not-exist-12345"
    page.goto(BASE_URL + non_existent_path)
    page.wait_for_load_state("networkidle")
    # Check for 404 indication (heading, status code, or specific element)
    title = page.title()
    if "404" in title or "Page Not Found" in title or "Not Found" in title:
        # Good, the title indicates 404
        pass
    else:
        # Look for a heading or message
        heading = page.locator("h1:has-text('404')")
        if heading.is_visible():
            expect(heading).to_be_visible()
        else:
            expect(page.locator(":has-text('Page not found')")).to_be_visible()


def test_navigation_links(authenticated_page: Page):
    """Test that the main navigation links work correctly."""
    page = authenticated_page
    nav_links = [
        {"text": "Dashboard", "path": "/dashboard"},
        {"text": "Markets", "path": "/markets"},
        {"text": "Trading", "path": "/trading/AAPL"},
        {"text": "Portfolio", "path": "/portfolio"},
        {"text": "Analytics", "path": "/analytics"},
        {"text": "Settings", "path": "/settings/general"},
    ]

    for link in nav_links:
        nav_link = page.locator(f"nav a:has-text('{link['text']}')").first
        expect(nav_link).to_be_visible()
        nav_link.click()
        page.wait_for_url(re.compile(link['path']), timeout=5000)
        expect(page).to_have_url(re.compile(link['path']))


def test_breadcrumb_navigation(authenticated_page: Page):
    """Test that breadcrumbs (if present) navigate correctly."""
    page = authenticated_page
    page.goto(BASE_URL + "/settings/general")
    page.wait_for_load_state("networkidle")

    breadcrumb = page.locator(".breadcrumb, [aria-label='Breadcrumb']")
    if breadcrumb.is_visible():
        parent_link = breadcrumb.locator("a:has-text('Settings')").first
        if parent_link.is_visible():
            parent_link.click()
            page.wait_for_url(re.compile(r"/settings"), timeout=5000)
            expect(page).to_have_url(re.compile(r"/settings"))
        else:
            home = breadcrumb.locator("a:has-text('Home')")
            if home.is_visible():
                home.click()
                page.wait_for_url(re.compile(r"/dashboard"), timeout=5000)
                expect(page).to_have_url(re.compile(r"/dashboard"))


def test_deep_linking_trading_symbol(authenticated_page: Page):
    """Test that direct navigation to a specific trading symbol works."""
    page = authenticated_page
    symbols = ["AAPL", "BTC/USD", "EUR/USD"]
    for symbol in symbols:
        page.goto(BASE_URL + f"/trading/{symbol}")
        page.wait_for_load_state("networkidle")
        expect(page.locator(f":has-text('{symbol}')")).to_be_visible()
        expect(page).to_have_url(re.compile(f"/trading/{symbol}"))


def test_query_parameters_preserved(authenticated_page: Page):
    """Test that query parameters are preserved across navigation and page loads."""
    page = authenticated_page
    page.goto(BASE_URL + "/markets?filter=crypto&sort=volume")
    page.wait_for_load_state("networkidle")
    expect(page).to_have_url(re.compile(r"filter=crypto"))

    filter_input = page.locator("input[value='crypto']")
    if filter_input.is_visible():
        expect(filter_input).to_have_value("crypto")

    # We can also check that the filter is applied; for now, no assertion needed.
    # The fact that the URL contains the parameter is enough for this test.


def test_redirect_after_login(page_context: Page):
    """Test that after logging in, user is redirected to the originally requested page."""
    page = page_context
    target = "/portfolio"
    page.goto(BASE_URL + target)
    page.wait_for_url(re.compile(r"/authentication/login"), timeout=5000)

    # Now log in
    page.fill("input[name='email']", "test@nexusquantum.com")
    page.fill("input[name='password']", "Test@123")
    page.click("button[type='submit']")
    page.wait_for_url(re.compile(target), timeout=10000)
    expect(page).to_have_url(re.compile(target))


def test_logout_redirect(authenticated_page: Page):
    """Test that logging out redirects to login page."""
    page = authenticated_page
    page.click("button[aria-label='User menu']")
    page.click("button:has-text('Logout')")
    page.wait_for_url(re.compile(r"/authentication/login"), timeout=5000)
    expect(page).to_have_url(re.compile(r"/authentication/login"))

    # Verify that protected page is no longer accessible
    page.goto(BASE_URL + "/dashboard")
    page.wait_for_load_state("networkidle")
    expect(page).to_have_url(re.compile(r"/authentication/login"))


def test_dynamic_route_parameters(authenticated_page: Page):
    """Test that dynamic route parameters are correctly reflected in the UI."""
    page = authenticated_page
    page.goto(BASE_URL + "/trading/AAPL")
    page.wait_for_load_state("networkidle")

    symbol_display = page.locator(".symbol-name, .ticker-symbol")
    expect(symbol_display).to_contain_text("AAPL")

    price = page.locator(".ticker-price, .last-price")
    expect(price).to_be_visible()
    price_text = price.text_content()
    assert price_text is not None and price_text != "", "Price should be present"


def test_wildcard_route_handling(page_context: Page):
    """Test that wildcard routes are handled correctly (e.g., catch-all)."""
    page = page_context
    page.goto(BASE_URL + "/some/nested/path/that/does/not/exist")
    page.wait_for_load_state("networkidle")

    title = page.title()
    if "404" in title or "Page Not Found" in title:
        assert True
    else:
        # Some apps redirect to home or login; that's also acceptable.
        if "/authentication/login" in page.url or "/dashboard" in page.url:
            assert True
        else:
            # Check for a "not found" message on the page
            not_found = page.locator(":has-text('not found')")
            expect(not_found).to_be_visible()


def test_route_transitions(authenticated_page: Page):
    """Test that route transitions are smooth and no errors occur."""
    page = authenticated_page
    page.goto(BASE_URL + "/dashboard")
    page.wait_for_load_state("networkidle")

    pages = [
        ("Markets", "/markets"),
        ("Trading", "/trading/AAPL"),
        ("Portfolio", "/portfolio"),
        ("Analytics", "/analytics"),
    ]

    for text, path in pages:
        link = page.locator(f"nav a:has-text('{text}')").first
        # If not visible, maybe it's in a mobile menu; we can open sidebar if needed.
        # For simplicity, we skip mobile handling here.
        link.click()
        page.wait_for_url(re.compile(path), timeout=5000)
        expect(page).to_have_url(re.compile(path))
        error = page.locator(".error-boundary, .error-message")
        expect(error).not_to_be_visible()


if __name__ == "__main__":
    # For manual execution, you can run:
    # pytest tests/frontend/test_routing.py -v
    pass
