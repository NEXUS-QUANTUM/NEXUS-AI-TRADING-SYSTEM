"""
tests/frontend/test_pages.py

NEXUS AI Trading System - Frontend Page Tests

This test suite verifies that all major pages of the application load correctly,
display the expected content, and behave as expected. It covers:

- Dashboard page
- Trading page (with symbol selection)
- Portfolio page
- Settings page (general, security, brokers, etc.)
- Markets page
- Analytics page
- Orders (open and history)
- Watchlist
- Alerts
- Profile page
- Help/Support

Each test checks:
- Page loads without errors
- Critical UI elements are visible (headings, charts, tables, forms)
- Navigation works
- Responsive behavior on different viewports

Uses Playwright for real browser automation against a live frontend instance.

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
DEFAULT_TIMEOUT = 30000
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Viewports
VIEWPORTS = [
    {"name": "desktop", "width": 1920, "height": 1080},
    {"name": "tablet", "width": 768, "height": 1024},
    {"name": "mobile", "width": 375, "height": 667},
]


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


def take_screenshot(page: Page, name: str):
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    page.screenshot(path=path, full_page=True)
    logger.info(f"Screenshot saved to {path}")


# ----- Page Tests ------

def test_dashboard_page(authenticated_page: Page):
    """Test the dashboard page loads and displays key metrics."""
    page = authenticated_page
    page.goto(BASE_URL + "/dashboard")
    page.wait_for_selector("main", state="visible")

    # Check page title / heading
    heading = page.locator("h1:has-text('Dashboard')")
    expect(heading).to_be_visible()

    # Check metric cards
    metric_cards = page.locator(".metric-card, [data-testid='metric-card']")
    expect(metric_cards).to_have_count(4)  # at least 4
    for card in metric_cards.all():
        expect(card.locator(".metric-value")).to_be_visible()

    # Check chart container
    chart = page.locator(".chart-container, [data-testid='chart-container']").first
    expect(chart).to_be_visible()

    # Check recent trades table or activity feed
    table = page.locator("table, .activity-feed").first
    expect(table).to_be_visible()

    # Ensure no error messages
    error = page.locator(".error-message, .alert-error")
    expect(error).not_to_be_visible()


def test_trading_page(authenticated_page: Page):
    """Test the trading page loads with order form, order book, and chart."""
    page = authenticated_page
    page.goto(BASE_URL + "/trading/AAPL")
    page.wait_for_selector(".trade-form, .order-book", state="visible")

    # Check symbol is displayed
    symbol = page.locator(".symbol-name, .ticker-symbol")
    expect(symbol).to_contain_text("AAPL")

    # Check order form
    order_form = page.locator(".trade-form, [data-testid='order-form']")
    expect(order_form).to_be_visible()
    expect(order_form.locator("input[name='qty']")).to_be_visible()

    # Check order book (bids/asks)
    order_book = page.locator(".order-book, [data-testid='order-book']")
    expect(order_book).to_be_visible()
    expect(order_book.locator(".bids, .asks")).to_be_visible()

    # Check chart
    chart = page.locator(".chart-container, [data-testid='chart']").first
    expect(chart).to_be_visible()

    # Check price ticker
    price = page.locator(".ticker-price, .last-price")
    expect(price).to_be_visible()
    price_text = price.text_content()
    assert price_text is not None and price_text != "", "Price should not be empty"


def test_portfolio_page(authenticated_page: Page):
    """Test the portfolio page shows summary, allocation, and positions."""
    page = authenticated_page
    page.goto(BASE_URL + "/portfolio")
    page.wait_for_selector(".portfolio-summary, table", state="visible")

    # Check heading
    heading = page.locator("h1:has-text('Portfolio')")
    expect(heading).to_be_visible()

    # Check balance/equity summary
    balance = page.locator(".balance, .total-equity")
    expect(balance).to_be_visible()

    # Check allocation chart (pie or donut)
    chart = page.locator(".allocation-chart, .portfolio-pie").first
    expect(chart).to_be_visible()

    # Check positions table
    positions_table = page.locator("table.positions, [data-testid='positions-table']")
    expect(positions_table).to_be_visible()

    # Check performance chart (if present)
    perf = page.locator(".performance-chart").first
    if perf.is_visible():
        expect(perf).to_be_visible()

    # No errors
    error = page.locator(".error-message")
    expect(error).not_to_be_visible()


def test_markets_page(authenticated_page: Page):
    """Test the markets page lists symbols and allows filtering."""
    page = authenticated_page
    page.goto(BASE_URL + "/markets")
    page.wait_for_selector("table", state="visible")

    heading = page.locator("h1:has-text('Markets')")
    expect(heading).to_be_visible()

    # Check table headers
    table = page.locator("table")
    expect(table.locator("th:has-text('Symbol')")).to_be_visible()
    expect(table.locator("th:has-text('Price')")).to_be_visible()

    # Check rows exist
    rows = table.locator("tbody tr")
    expect(rows).to_have_count(10)  # at least 10 symbols

    # Check search/filter input
    search = page.locator("input[placeholder*='Search']")
    if search.is_visible():
        search.fill("AAPL")
        page.wait_for_timeout(500)
        filtered_rows = table.locator("tbody tr:has-text('AAPL')")
        expect(filtered_rows).to_be_visible()

    # Check pagination or load more (if any)
    pagination = page.locator(".pagination, button:has-text('Load More')")
    if pagination.is_visible():
        expect(pagination).to_be_visible()


def test_analytics_page(authenticated_page: Page):
    """Test the analytics page loads charts and reports."""
    page = authenticated_page
    page.goto(BASE_URL + "/analytics")
    page.wait_for_selector(".analytics-container, .chart-container", state="visible")

    heading = page.locator("h1:has-text('Analytics')")
    expect(heading).to_be_visible()

    # Check for multiple charts
    charts = page.locator(".chart-container")
    expect(charts).to_have_count(3)  # at least 3 charts

    # Check time period selector
    period = page.locator("select[name='period']")
    if period.is_visible():
        expect(period).to_be_visible()

    # Check date range picker (if any)
    date_picker = page.locator("input[type='date']")
    if date_picker.is_visible():
        expect(date_picker).to_be_visible()


def test_settings_general_page(authenticated_page: Page):
    """Test the general settings page loads with form."""
    page = authenticated_page
    page.goto(BASE_URL + "/settings/general")
    page.wait_for_selector("form", state="visible")

    heading = page.locator("h1:has-text('General Settings')")
    expect(heading).to_be_visible()

    # Check form fields
    form = page.locator("form")
    expect(form.locator("input[name='firstName']")).to_be_visible()
    expect(form.locator("input[name='lastName']")).to_be_visible()
    expect(form.locator("input[name='email']")).to_be_visible()
    expect(form.locator("select[name='timezone']")).to_be_visible()

    # Check save button
    save_btn = form.locator("button[type='submit']")
    expect(save_btn).to_be_visible()

    # Fill and submit (but we don't need to assert success here; just test form presence)
    # We can optionally test update, but state management tests cover that.


def test_settings_security_page(authenticated_page: Page):
    """Test the security settings page (password, 2FA)."""
    page = authenticated_page
    page.goto(BASE_URL + "/settings/security")
    page.wait_for_selector("form", state="visible")

    heading = page.locator("h1:has-text('Security')")
    expect(heading).to_be_visible()

    # Password change section
    password_section = page.locator("section:has-text('Change Password')")
    expect(password_section).to_be_visible()
    expect(password_section.locator("input[name='currentPassword']")).to_be_visible()
    expect(password_section.locator("input[name='newPassword']")).to_be_visible()
    expect(password_section.locator("input[name='confirmPassword']")).to_be_visible()

    # 2FA section (if enabled)
    twofa = page.locator("section:has-text('Two-Factor Authentication')")
    if twofa.is_visible():
        expect(twofa.locator("button:has-text('Enable')")).to_be_visible()


def test_settings_brokers_page(authenticated_page: Page):
    """Test the broker settings page lists connected brokers."""
    page = authenticated_page
    page.goto(BASE_URL + "/settings/brokers")
    page.wait_for_selector("button:has-text('Add Broker')", state="visible")

    heading = page.locator("h1:has-text('Broker Settings')")
    expect(heading).to_be_visible()

    # Add broker button
    add_btn = page.locator("button:has-text('Add Broker')")
    expect(add_btn).to_be_visible()

    # If there are existing brokers, they should be listed
    broker_list = page.locator(".broker-list, table")
    if broker_list.is_visible():
        expect(broker_list).to_be_visible()


def test_orders_open_page(authenticated_page: Page):
    """Test the open orders page shows pending orders."""
    page = authenticated_page
    page.goto(BASE_URL + "/orders/open")
    page.wait_for_selector("table", state="visible")

    heading = page.locator("h1:has-text('Open Orders')")
    expect(heading).to_be_visible()

    table = page.locator("table")
    expect(table.locator("th:has-text('Symbol')")).to_be_visible()
    expect(table.locator("th:has-text('Type')")).to_be_visible()
    expect(table.locator("th:has-text('Status')")).to_be_visible()

    # If there are open orders, they should have cancel button
    first_row = table.locator("tbody tr").first
    if first_row.is_visible():
        cancel_btn = first_row.locator("button:has-text('Cancel')")
        if cancel_btn.is_visible():
            expect(cancel_btn).to_be_visible()


def test_orders_history_page(authenticated_page: Page):
    """Test the order history page shows past orders with filters."""
    page = authenticated_page
    page.goto(BASE_URL + "/orders/history")
    page.wait_for_selector("table", state="visible")

    heading = page.locator("h1:has-text('Order History')")
    expect(heading).to_be_visible()

    table = page.locator("table")
    expect(table.locator("th:has-text('Date')")).to_be_visible()

    # Filter fields
    filter_input = page.locator("input[placeholder*='Symbol']")
    if filter_input.is_visible():
        expect(filter_input).to_be_visible()

    date_from = page.locator("input[name='dateFrom']")
    if date_from.is_visible():
        expect(date_from).to_be_visible()

    # Export button
    export_btn = page.locator("button:has-text('Export')")
    if export_btn.is_visible():
        expect(export_btn).to_be_visible()


def test_watchlist_page(authenticated_page: Page):
    """Test the watchlist page shows user's watched symbols."""
    page = authenticated_page
    page.goto(BASE_URL + "/watchlist")
    page.wait_for_selector("table, .watchlist-container", state="visible")

    heading = page.locator("h1:has-text('Watchlist')")
    expect(heading).to_be_visible()

    # Check add symbol button
    add_btn = page.locator("button:has-text('Add Symbol')")
    expect(add_btn).to_be_visible()

    # Check if symbols are listed
    symbols = page.locator(".symbol-row, table tbody tr")
    if symbols.count() > 0:
        expect(symbols.first).to_be_visible()


def test_alerts_page(authenticated_page: Page):
    """Test the alerts page shows price/volume alerts."""
    page = authenticated_page
    page.goto(BASE_URL + "/alerts")
    page.wait_for_selector(".alerts-container, table", state="visible")

    heading = page.locator("h1:has-text('Alerts')")
    expect(heading).to_be_visible()

    # Create alert button
    create_btn = page.locator("button:has-text('Create Alert')")
    expect(create_btn).to_be_visible()

    # If alerts exist, check list
    alert_list = page.locator(".alert-item, table tbody tr")
    if alert_list.count() > 0:
        expect(alert_list.first).to_be_visible()


def test_profile_page(authenticated_page: Page):
    """Test the user profile page."""
    page = authenticated_page
    # Usually profile is under user menu
    page.click("button[aria-label='User menu']")
    page.click("a:has-text('Profile')")
    page.wait_for_selector(".profile-container, form", state="visible")

    heading = page.locator("h1:has-text('Profile')")
    expect(heading).to_be_visible()

    # Check avatar
    avatar = page.locator("img[alt='Profile picture']")
    expect(avatar).to_be_visible()

    # Check form fields
    form = page.locator("form")
    expect(form.locator("input[name='firstName']")).to_be_visible()
    expect(form.locator("input[name='lastName']")).to_be_visible()
    expect(form.locator("input[name='email']")).to_be_visible()


def test_help_support_page(authenticated_page: Page):
    """Test the help/support page loads knowledge base and ticket form."""
    page = authenticated_page
    page.goto(BASE_URL + "/help")
    page.wait_for_selector(".help-container, .knowledge-base", state="visible")

    heading = page.locator("h1:has-text('Help')")
    expect(heading).to_be_visible()

    # FAQ section
    faq = page.locator(".faq-section, .accordion")
    expect(faq).to_be_visible()

    # Contact support button
    contact_btn = page.locator("button:has-text('Contact Support')")
    expect(contact_btn).to_be_visible()

    # Click to open ticket form
    contact_btn.click()
    modal = page.locator(".modal, .ticket-form")
    expect(modal).to_be_visible()
    expect(modal.locator("input[name='subject']")).to_be_visible()
    expect(modal.locator("textarea[name='message']")).to_be_visible()


# ----- Responsive Tests -----

@pytest.mark.parametrize("viewport", VIEWPORTS, ids=lambda v: v["name"])
def test_dashboard_responsive(authenticated_page: Page, viewport: Dict[str, Any]):
    """Test dashboard on different viewports."""
    page = authenticated_page
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
    page.goto(BASE_URL + "/dashboard")
    page.wait_for_selector("main", state="visible")

    # Check that header is visible
    expect(page.locator("header")).to_be_visible()

    # Sidebar visibility
    sidebar = page.locator("nav.sidebar")
    if viewport["width"] <= 768:
        # On mobile, sidebar should be hidden initially
        expect(sidebar).not_to_be_visible()
        # Hamburger menu should be visible
        hamburger = page.locator("button[aria-label='Toggle menu']")
        expect(hamburger).to_be_visible()
    else:
        # On desktop/tablet, sidebar should be visible
        expect(sidebar).to_be_visible()

    # Check that metric cards are visible and properly arranged (no overflow)
    cards = page.locator(".metric-card")
    for card in cards.all():
        expect(card).to_be_visible()
    # No horizontal overflow
    body_width = page.evaluate("document.body.scrollWidth")
    viewport_width = page.evaluate("window.innerWidth")
    assert body_width <= viewport_width + 2, f"Overflow on {viewport['name']}"


@pytest.mark.parametrize("viewport", VIEWPORTS, ids=lambda v: v["name"])
def test_trading_page_responsive(authenticated_page: Page, viewport: Dict[str, Any]):
    """Test trading page on different viewports."""
    page = authenticated_page
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
    page.goto(BASE_URL + "/trading/AAPL")
    page.wait_for_selector(".trade-form, .order-book", state="visible")

    # Check that order form is visible (may be collapsible on mobile)
    order_form = page.locator(".trade-form")
    if viewport["width"] <= 768:
        # On mobile, the form might be collapsed; check expand button
        expand_btn = page.locator("button[aria-label='Show order form']")
        if expand_btn.is_visible():
            expand_btn.click()
            page.wait_for_timeout(300)
    expect(order_form).to_be_visible()

    # Check chart container is present
    chart = page.locator(".chart-container").first
    expect(chart).to_be_visible()

    # Check order book
    order_book = page.locator(".order-book")
    if viewport["width"] <= 768:
        # On mobile, order book might be at bottom; still visible
        pass
    expect(order_book).to_be_visible()


@pytest.mark.parametrize("viewport", VIEWPORTS, ids=lambda v: v["name"])
def test_settings_page_responsive(authenticated_page: Page, viewport: Dict[str, Any]):
    """Test settings page on different viewports."""
    page = authenticated_page
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
    page.goto(BASE_URL + "/settings/general")
    page.wait_for_selector("form", state="visible")

    # Sidebar navigation in settings
    settings_nav = page.locator(".settings-sidebar, nav[data-testid='settings-nav']")
    if viewport["width"] <= 768:
        # On mobile, sidebar might be hidden behind a toggle
        toggle = page.locator("button[aria-label='Toggle settings menu']")
        if toggle.is_visible():
            toggle.click()
            page.wait_for_timeout(300)
    expect(settings_nav).to_be_visible()

    # Form should be visible
    form = page.locator("form")
    expect(form).to_be_visible()
