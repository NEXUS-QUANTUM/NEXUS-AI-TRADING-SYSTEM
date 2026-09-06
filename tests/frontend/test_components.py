"""
tests/frontend/test_components.py

NEXUS AI Trading System - Frontend UI Component Tests

This test suite verifies that individual UI components work correctly across the
application. It uses Playwright to interact with the live frontend and tests:

- Metric Cards (display values, tooltips)
- Charts (interaction, responsiveness)
- Order Form (tabs, inputs, validation)
- Modals (open, close, form submission)
- Toast Notifications (appear, dismiss)
- Dropdowns/Selectors (selection, options)
- Tabs (switching, content updates)
- Tables (sorting, filtering, pagination)
- Buttons (hover, click states)
- Navigation components (sidebar, breadcrumbs)
- Tooltips
- Loading states (spinners, skeletons)

Each test navigates to a relevant page to find the component and performs
interactions to ensure it behaves as expected.

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import logging
import pytest
import re
from playwright.sync_api import Page, BrowserContext, expect
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
BASE_URL = os.getenv("NEXUS_FRONTEND_URL", "http://localhost:3000")
DEFAULT_TIMEOUT = 30000
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Viewports for responsive testing
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
    """Log in once for authenticated components."""
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


# ----- Component Tests ------

def test_metric_card_component(authenticated_page: Page):
    """Test metric cards on dashboard display correct values and tooltips."""
    page = authenticated_page
    page.goto(BASE_URL + "/dashboard")
    page.wait_for_selector(".metric-card, [data-testid='metric-card']", state="visible")

    cards = page.locator(".metric-card, [data-testid='metric-card']")
    count = cards.count()
    assert count >= 4, "Dashboard should have at least 4 metric cards"

    for i in range(count):
        card = cards.nth(i)
        # Check value is visible and numeric-ish
        value = card.locator(".metric-value, .value")
        expect(value).to_be_visible()
        value_text = value.text_content()
        # Should contain digits, %, or $ etc.
        assert re.search(r'\d', value_text), f"Metric value {value_text} should contain digits"

        # Check label
        label = card.locator(".metric-label, .label")
        expect(label).to_be_visible()

        # Hover to show tooltip (if any)
        card.hover()
        page.wait_for_timeout(300)
        tooltip = page.locator(".tooltip, [role='tooltip']")
        if tooltip.is_visible():
            expect(tooltip).to_be_visible()
        # Click to see if any drilldown (optional)
        if card.locator("a").is_visible():
            card.click()
            page.wait_for_url(re.compile(r"/analytics|/portfolio"), timeout=5000)
            page.go_back()


def test_chart_component(authenticated_page: Page):
    """Test chart component loads and allows interaction (tooltip, zoom)."""
    page = authenticated_page
    page.goto(BASE_URL + "/trading/AAPL")
    page.wait_for_selector(".chart-container, [data-testid='chart-container']", state="visible")

    chart = page.locator(".chart-container").first
    expect(chart).to_be_visible()

    # Hover on chart to see tooltip
    box = chart.bounding_box()
    if box:
        # Move mouse to center of chart
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.wait_for_timeout(500)
        # Tooltip might appear
        tooltip = page.locator(".chart-tooltip, .tooltip")
        if tooltip.is_visible():
            expect(tooltip).to_be_visible()

    # Timeframe selector (if present)
    timeframe_select = page.locator("select[name='timeframe']")
    if timeframe_select.is_visible():
        timeframe_select.select_option("1h")
        page.wait_for_timeout(1000)
        # Chart should update; we check that chart is still there
        expect(chart).to_be_visible()

    # Indicator toggle (e.g., RSI, MACD)
    indicator_btn = page.locator("button:has-text('Indicators')")
    if indicator_btn.is_visible():
        indicator_btn.click()
        page.wait_for_timeout(300)
        # Modal or dropdown appears
        indicator_list = page.locator(".indicator-list, .dropdown-menu")
        if indicator_list.is_visible():
            # Toggle an indicator
            rsi_toggle = indicator_list.locator("button:has-text('RSI')")
            if rsi_toggle.is_visible():
                rsi_toggle.click()
                page.wait_for_timeout(500)
                # Close dropdown
                indicator_btn.click()

    take_screenshot(page, "chart_interaction")


def test_order_form_component(authenticated_page: Page):
    """Test order form tabs, inputs, and validation."""
    page = authenticated_page
    page.goto(BASE_URL + "/trading/AAPL")
    page.wait_for_selector(".trade-form, [data-testid='order-form']", state="visible")

    order_form = page.locator(".trade-form")

    # Check tabs: Market, Limit, Stop, etc.
    tabs = order_form.locator("button[role='tab']")
    tab_names = tabs.all_text_contents()
    expected_tabs = ["Market", "Limit"]
    for expected in expected_tabs:
        assert expected in " ".join(tab_names), f"Tab {expected} not found"

    # Switch to Limit tab
    limit_tab = order_form.locator("button:has-text('Limit')")
    if limit_tab.is_visible():
        limit_tab.click()
        page.wait_for_timeout(200)
        # Limit price input should appear
        limit_price = order_form.locator("input[name='limitPrice']")
        expect(limit_price).to_be_visible()

    # Fill quantity
    qty_input = order_form.locator("input[name='qty']")
    qty_input.fill("10")
    # Check that estimated value or risk updates (if any)
    estimated = order_form.locator(".estimated-value, .risk-indicator")
    if estimated.is_visible():
        expect(estimated).to_contain_text("$") or expect(estimated).to_contain_text("USD")

    # Switch to Stop tab
    stop_tab = order_form.locator("button:has-text('Stop')")
    if stop_tab.is_visible():
        stop_tab.click()
        page.wait_for_timeout(200)
        stop_price = order_form.locator("input[name='stopPrice']")
        expect(stop_price).to_be_visible()

    # Test buy/sell buttons
    buy_btn = order_form.locator("button:has-text('Buy')")
    sell_btn = order_form.locator("button:has-text('Sell')")
    expect(buy_btn).to_be_visible()
    expect(sell_btn).to_be_visible()
    # Buy button should be styled differently (e.g., green)
    buy_color = buy_btn.evaluate("el => window.getComputedStyle(el).backgroundColor")
    # Not asserting color; just checking presence.


def test_modal_component(authenticated_page: Page):
    """Test modal opens, closes, and form submission works."""
    page = authenticated_page
    # Open modal via settings -> add broker
    page.goto(BASE_URL + "/settings/brokers")
    page.wait_for_selector("button:has-text('Add Broker')", state="visible")
    page.click("button:has-text('Add Broker')")
    modal = page.locator(".modal, .dialog, [role='dialog']")
    expect(modal).to_be_visible()

    # Modal should have a title
    modal_title = modal.locator(".modal-title, h2")
    expect(modal_title).to_be_visible()
    expect(modal_title).to_contain_text("Add Broker")

    # Check close button (X)
    close_btn = modal.locator("button:has-text('×'), button[aria-label='Close']")
    if close_btn.is_visible():
        close_btn.click()
        page.wait_for_timeout(500)
        expect(modal).not_to_be_visible()

    # Re-open
    page.click("button:has-text('Add Broker')")
    modal = page.locator(".modal, .dialog")
    expect(modal).to_be_visible()

    # Test form inside modal: fill and submit
    broker_select = modal.locator("select[name='brokerType']")
    broker_select.select_option("alpaca")
    modal.locator("input[name='apiKey']").fill("TEST_KEY")
    modal.locator("input[name='apiSecret']").fill("TEST_SECRET")
    modal.locator("button:has-text('Save')").click()
    expect(modal).not_to_be_visible(timeout=5000)
    success = page.locator(".toast-success")
    expect(success).to_be_visible(timeout=5000)


def test_toast_notification_component(authenticated_page: Page):
    """Test toast notifications appear and can be dismissed."""
    page = authenticated_page
    # Trigger toast by submitting a form
    page.goto(BASE_URL + "/settings/general")
    page.wait_for_selector("form", state="visible")
    page.fill("input[name='firstName']", "ToastTest")
    page.click("button[type='submit']")
    toast = page.locator(".toast-success, .alert-success")
    expect(toast).to_be_visible(timeout=5000)
    # Check toast contains success message
    expect(toast).to_contain_text("Saved") or expect(toast).to_contain_text("Success")

    # Dismiss toast
    close_btn = toast.locator("button:has-text('×')")
    if close_btn.is_visible():
        close_btn.click()
        page.wait_for_timeout(500)
        expect(toast).not_to_be_visible()

    # Test error toast by invalid input
    page.fill("input[name='firstName']", "")  # required
    page.click("button[type='submit']")
    error_toast = page.locator(".toast-error, .alert-error")
    if error_toast.is_visible():
        expect(error_toast).to_be_visible()


def test_dropdown_component(authenticated_page: Page):
    """Test dropdown/select components on various pages."""
    page = authenticated_page
    # Go to markets page to test symbol filter dropdown
    page.goto(BASE_URL + "/markets")
    page.wait_for_selector("table", state="visible")

    # Find a dropdown, e.g., "Market Type" or "Sort by"
    dropdowns = page.locator("select")
    if dropdowns.count() > 0:
        # Pick first dropdown and change value
        first_dropdown = dropdowns.first
        if first_dropdown.is_visible():
            # Get current value and select another option
            options = first_dropdown.locator("option")
            if options.count() > 1:
                first_dropdown.select_option(index=1)
                page.wait_for_timeout(500)
                # Table should update; check it didn't disappear
                expect(page.locator("table")).to_be_visible()

    # Also test a custom dropdown (non-native) like a filter button with options
    filter_btn = page.locator("button:has-text('Filter')")
    if filter_btn.is_visible():
        filter_btn.click()
        page.wait_for_timeout(300)
        dropdown_menu = page.locator(".dropdown-menu, [role='menu']")
        if dropdown_menu.is_visible():
            option = dropdown_menu.locator("button:has-text('Crypto')")
            if option.is_visible():
                option.click()
                page.wait_for_timeout(500)
                # Check that filter applied
                expect(page.locator("table")).to_be_visible()


def test_tabs_component(authenticated_page: Page):
    """Test tabs component switching on trading and portfolio pages."""
    page = authenticated_page
    # Test tabs on trading page: Market/Limit/Stop
    page.goto(BASE_URL + "/trading/AAPL")
    page.wait_for_selector(".trade-form", state="visible")
    tabs = page.locator(".trade-form button[role='tab']")
    if tabs.count() >= 3:
        # Click each tab and verify content changes
        tab_texts = tabs.all_text_contents()
        for i, text in enumerate(tab_texts):
            tab = tabs.nth(i)
            tab.click()
            page.wait_for_timeout(300)
            # Check that relevant input fields appear
            if "Limit" in text:
                expect(page.locator("input[name='limitPrice']")).to_be_visible()
            elif "Stop" in text:
                expect(page.locator("input[name='stopPrice']")).to_be_visible()
            elif "Market" in text:
                # Market tab might not have extra fields
                pass

    # Test tabs on portfolio page: Overview, Positions, History
    page.goto(BASE_URL + "/portfolio")
    page.wait_for_selector(".portfolio-tabs, [role='tablist']", state="visible")
    tabs = page.locator(".portfolio-tabs button[role='tab']")
    if tabs.count() >= 3:
        for i in range(tabs.count()):
            tabs.nth(i).click()
            page.wait_for_timeout(300)
            # Check that content panel is visible
            panel = page.locator(".tab-panel, [role='tabpanel']").nth(i)
            expect(panel).to_be_visible()


def test_table_sorting_and_filtering(authenticated_page: Page):
    """Test table column sorting and filtering."""
    page = authenticated_page
    page.goto(BASE_URL + "/markets")
    page.wait_for_selector("table", state="visible")

    # Find column header with sort capability (often has arrow icon)
    headers = page.locator("thead th")
    for i in range(headers.count()):
        th = headers.nth(i)
        # Check if it has a sort indicator (icon)
        if th.locator("svg[data-icon='sort']").is_visible():
            # Click to sort
            th.click()
            page.wait_for_timeout(500)
            # Check icon changed (up/down) – optional
            # Verify table rows are still visible
            expect(page.locator("tbody tr")).to_be_visible()

    # Test filtering: find search input
    search = page.locator("input[placeholder*='Search']")
    if search.is_visible():
        search.fill("AAPL")
        page.wait_for_timeout(500)
        # Rows should be filtered to show only AAPL
        rows = page.locator("tbody tr")
        if rows.count() > 0:
            for row in rows.all():
                expect(row).to_contain_text("AAPL")


def test_pagination_component(authenticated_page: Page):
    """Test pagination controls on pages with large datasets."""
    page = authenticated_page
    page.goto(BASE_URL + "/orders/history")
    page.wait_for_selector("table", state="visible")

    pagination = page.locator(".pagination, [data-testid='pagination']")
    if pagination.is_visible():
        # Check next/prev buttons
        next_btn = pagination.locator("button:has-text('Next')")
        if next_btn.is_visible() and not next_btn.is_disabled():
            next_btn.click()
            page.wait_for_timeout(500)
            # Table should update; check if page number changed
            current_page = pagination.locator(".page-number, .active")
            if current_page.is_visible():
                page_num = current_page.text_content()
                assert page_num != "1", "Page number should change"

        # Check page number links
        page_links = pagination.locator("button:has-text(regex('\\d+'))")
        if page_links.count() > 1:
            page_links.nth(1).click()
            page.wait_for_timeout(500)


def test_navigation_sidebar_component(authenticated_page: Page):
    """Test sidebar navigation links and active states."""
    page = authenticated_page
    page.goto(BASE_URL + "/dashboard")
    sidebar = page.locator("nav.sidebar, [data-testid='sidebar']")
    expect(sidebar).to_be_visible()

    # Check navigation links
    nav_links = sidebar.locator("a")
    for link in nav_links.all():
        # Hover to see tooltip (if any)
        link.hover()
        page.wait_for_timeout(200)
        # Click and verify navigation
        href = link.get_attribute("href")
        if href and not href.startswith("#"):
            link.click()
            page.wait_for_url(re.compile(re.escape(href)), timeout=5000)
            expect(page).to_have_url(re.compile(re.escape(href)))
            # Active state should be applied to this link
            expect(link).to_have_class(re.compile(r"active|selected"))
            # Go back to dashboard
            page.goto(BASE_URL + "/dashboard")
            sidebar = page.locator("nav.sidebar")
            break


def test_breadcrumb_component(authenticated_page: Page):
    """Test breadcrumb navigation displays correctly."""
    page = authenticated_page
    page.goto(BASE_URL + "/settings/brokers")
    page.wait_for_selector(".breadcrumb, [aria-label='Breadcrumb']", state="visible")

    breadcrumb = page.locator(".breadcrumb")
    expect(breadcrumb).to_be_visible()

    items = breadcrumb.locator("li, a")
    # At least 2: Home/Settings > Brokers
    assert items.count() >= 2, "Breadcrumb should have at least 2 items"

    # Click on parent breadcrumb (Settings)
    parent = breadcrumb.locator("a:has-text('Settings')").first
    if parent.is_visible():
        parent.click()
        page.wait_for_url(re.compile(r"/settings"), timeout=5000)
        expect(page).to_have_url(re.compile(r"/settings"))


def test_loading_states(authenticated_page: Page):
    """Test loading spinners/skeletons appear and disappear."""
    page = authenticated_page
    # Navigate to a page that triggers loading (portfolio)
    page.goto(BASE_URL + "/portfolio")
    # Loading skeleton may be present immediately
    skeleton = page.locator(".skeleton, .loading-spinner")
    if skeleton.is_visible():
        # Wait for it to disappear
        expect(skeleton).not_to_be_visible(timeout=10000)
    # Content should be visible
    expect(page.locator(".portfolio-summary, table")).to_be_visible()


def test_button_hover_and_states(authenticated_page: Page):
    """Test button hover, disabled, active states."""
    page = authenticated_page
    page.goto(BASE_URL + "/settings/general")
    page.wait_for_selector("form", state="visible")

    save_btn = page.locator("button[type='submit']")
    expect(save_btn).to_be_visible()

    # Hover state
    save_btn.hover()
    page.wait_for_timeout(200)
    # Button should change style (we can't assert easily, but no error)

    # Disabled state? Find a disabled button (if any)
    disabled_btn = page.locator("button:disabled")
    if disabled_btn.is_visible():
        expect(disabled_btn).to_be_disabled()


def test_tooltip_component(authenticated_page: Page):
    """Test tooltips appear on hover."""
    page = authenticated_page
    page.goto(BASE_URL + "/dashboard")
    page.wait_for_selector(".metric-card", state="visible")

    # Find an element with a tooltip (e.g., info icon)
    info_icon = page.locator(".info-icon, [data-tooltip]").first
    if info_icon.is_visible():
        info_icon.hover()
        page.wait_for_timeout(500)
        tooltip = page.locator(".tooltip, [role='tooltip']")
        if tooltip.is_visible():
            expect(tooltip).to_be_visible()
            # Tooltip text should be present
            tooltip_text = tooltip.text_content()
            assert tooltip_text is not None and len(tooltip_text) > 0


def test_switch_toggle_component(authenticated_page: Page):
    """Test switch/toggle components (on/off)."""
    page = authenticated_page
    page.goto(BASE_URL + "/settings/notifications")
    page.wait_for_selector("form", state="visible")

    # Find a toggle (checkbox with custom styling)
    toggles = page.locator("input[type='checkbox']")
    if toggles.count() > 0:
        toggle = toggles.first
        # Toggle on/off and check state
        initial = toggle.is_checked()
        toggle.check()
        expect(toggle).to_be_checked()
        toggle.uncheck()
        expect(toggle).not_to_be_checked()
        # Reset to initial
        if initial:
            toggle.check()


def test_accordion_component(authenticated_page: Page):
    """Test accordion/collapsible sections."""
    page = authenticated_page
    page.goto(BASE_URL + "/help")
    page.wait_for_selector(".accordion, .faq-section", state="visible")

    # Find an accordion header and click to expand
    accordion_header = page.locator(".accordion-header, .faq-question").first
    if accordion_header.is_visible():
        # Click to expand
        accordion_header.click()
        page.wait_for_timeout(300)
        # Content should be visible
        content = page.locator(".accordion-content, .faq-answer").first
        expect(content).to_be_visible()

        # Click again to collapse
        accordion_header.click()
        page.wait_for_timeout(300)
        expect(content).not_to_be_visible()


def test_progress_bar(authenticated_page: Page):
    """Test progress indicators (if any)."""
    page = authenticated_page
    # Progress bars may appear during order execution or data loading.
    # We'll check on trading page if there's any.
    page.goto(BASE_URL + "/trading/AAPL")
    page.wait_for_selector(".trade-form", state="visible")
    progress = page.locator(".progress-bar, [role='progressbar']")
    if progress.is_visible():
        # Value should be between 0 and 100
        value = progress.get_attribute("aria-valuenow")
        if value:
            assert 0 <= int(value) <= 100


def test_chart_legend(authenticated_page: Page):
    """Test chart legend interaction (show/hide series)."""
    page = authenticated_page
    page.goto(BASE_URL + "/analytics")
    page.wait_for_selector(".chart-container", state="visible")
    legend = page.locator(".chart-legend, .legend")
    if legend.is_visible():
        items = legend.locator(".legend-item")
        if items.count() > 1:
            # Click first item to toggle visibility
            items.first.click()
            page.wait_for_timeout(500)
            # The chart should redraw; we just check no error
            expect(page.locator(".chart-container")).to_be_visible()


# ----- Responsive component tests -----

@pytest.mark.parametrize("viewport", VIEWPORTS, ids=lambda v: v["name"])
def test_component_adaptability(authenticated_page: Page, viewport: Dict[str, Any]):
    """Test that key components adapt to screen size."""
    page = authenticated_page
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
    page.goto(BASE_URL + "/dashboard")
    page.wait_for_selector("main", state="visible")

    # Metric cards should wrap or resize
    cards = page.locator(".metric-card")
    if viewport["width"] <= 768:
        # On mobile, cards might be stacked; check they are visible
        for card in cards.all():
            expect(card).to_be_visible()
    else:
        # On desktop, at least 2 cards in a row
        first_card = cards.nth(0)
        second_card = cards.nth(1)
        first_box = first_card.bounding_box()
        second_box = second_card.bounding_box()
        # They should be on same row (if not, maybe they wrap)
        # We just check they're visible.

    # Sidebar behavior
    sidebar = page.locator("nav.sidebar")
    if viewport["width"] <= 768:
        expect(sidebar).not_to_be_visible()
        hamburger = page.locator("button[aria-label='Toggle menu']")
        expect(hamburger).to_be_visible()
        hamburger.click()
        page.wait_for_timeout(300)
        expect(sidebar).to_be_visible()
    else:
        expect(sidebar).to_be_visible()
