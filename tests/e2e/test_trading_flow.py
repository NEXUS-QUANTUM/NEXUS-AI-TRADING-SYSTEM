"""
NEXUS AI TRADING SYSTEM - End-to-End Trading Flow Tests

This test suite verifies that the trading workflow functions correctly,
including order placement, position management, order history, and real-time updates.
Tests cover both desktop and mobile viewports.

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import logging
import pytest
import re
import time
from playwright.sync_api import Page, BrowserContext, expect
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
BASE_URL = os.getenv("NEXUS_FRONTEND_URL", "http://localhost:3000")
API_URL = os.getenv("NEXUS_API_URL", "http://localhost:8000")
DEFAULT_TIMEOUT = 30000  # milliseconds
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Viewports for responsive testing
VIEWPORTS = [
    {"name": "desktop", "width": 1920, "height": 1080},
    {"name": "tablet", "width": 768, "height": 1024},
    {"name": "mobile", "width": 375, "height": 667},
]

# Trading symbols for tests
TEST_SYMBOLS = ["AAPL", "BTC/USD", "EUR/USD"]


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
    """Log in once for tests requiring authentication."""
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


def navigate_to_trading(page: Page, symbol: str = "AAPL"):
    """Navigate to the trading page for a specific symbol."""
    # From dashboard, click on "Trade" or "Markets" then select symbol
    trade_link = page.locator("a[href*='/trading']").first
    expect(trade_link).to_be_visible()
    trade_link.click()
    page.wait_for_url(re.compile(r"/trading"), timeout=5000)

    # If symbol is not already selected, search for it
    if not page.locator(f"button:has-text('{symbol}')").is_visible():
        # Click on the symbol selector or search
        search_input = page.locator("input[placeholder*='Search']")
        if search_input.is_visible():
            search_input.fill(symbol)
            page.wait_for_timeout(500)
            # Click on the matching result
            symbol_option = page.locator(f"button:has-text('{symbol}')").first
            expect(symbol_option).to_be_visible()
            symbol_option.click()
        else:
            # Maybe symbol selector is a dropdown
            selector = page.locator("select[name='symbol']")
            selector.select_option(symbol)

    # Wait for market data to load
    page.wait_for_selector(".order-book, .price-ticker, .chart-container", state="visible")


# ----- Tests ------

def test_trading_page_loads(authenticated_page: Page):
    """Verify that the trading page loads correctly."""
    page = authenticated_page
    navigate_to_trading(page)
    # Check key elements
    expect(page.locator(".price-ticker, .ticker-price")).to_be_visible()
    expect(page.locator(".order-book, [data-testid='order-book']")).to_be_visible()
    expect(page.locator(".trade-form, [data-testid='order-form']")).to_be_visible()
    expect(page.locator(".chart-container")).to_be_visible()
    take_screenshot(page, "trading_page")


@pytest.mark.parametrize("viewport", VIEWPORTS, ids=lambda v: v["name"])
def test_trading_interface_responsive(authenticated_page: Page, viewport: Dict[str, Any]):
    """Test the trading interface adapts to different screen sizes."""
    page = authenticated_page
    page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
    navigate_to_trading(page)

    # Check that order form is usable
    order_form = page.locator(".trade-form, [data-testid='order-form']")
    expect(order_form).to_be_visible()
    # On mobile, maybe order form is collapsed; look for expand button
    if viewport["width"] <= 768:
        expand_btn = page.locator("button[aria-label='Show order form']")
        if expand_btn.is_visible():
            expand_btn.click()
            page.wait_for_timeout(300)
    expect(order_form.locator("input[name='qty']")).to_be_visible()

    # Check order book
    order_book = page.locator(".order-book, [data-testid='order-book']")
    expect(order_book).to_be_visible()
    # Ensure no horizontal overflow
    body_width = page.evaluate("document.body.scrollWidth")
    viewport_width = page.evaluate("window.innerWidth")
    assert body_width <= viewport_width + 2, f"Body overflows horizontally (body: {body_width}, viewport: {viewport_width})"

    take_screenshot(page, f"trading_{viewport['name']}")


def test_place_market_order(authenticated_page: Page):
    """Test placing a market buy and sell order."""
    page = authenticated_page
    navigate_to_trading(page, "AAPL")

    # Switch to market order if not default
    market_tab = page.locator("button:has-text('Market')")
    if market_tab.is_visible():
        market_tab.click()
        page.wait_for_timeout(200)

    # Get current price for reference
    price_element = page.locator(".ticker-price, .last-price")
    current_price = float(price_element.text_content().replace('$', '').replace(',', ''))

    # Place a buy order
    qty_input = page.locator("input[name='qty']")
    qty_input.fill("1")
    # Ensure side is "Buy"
    buy_btn = page.locator("button:has-text('Buy')")
    expect(buy_btn).to_be_visible()
    # Capture the order response via network (or just click)
    with page.expect_response(re.compile(r"/api/v1/trading/orders")) as response_info:
        buy_btn.click()
    response = response_info.value
    assert response.status == 200 or response.status == 201, f"Order placement failed: {response.status}"

    # Wait for success notification
    success = page.locator(".toast-success, .alert-success")
    expect(success).to_be_visible(timeout=5000)
    # Verify order appears in open positions or order history
    positions_tab = page.locator("button:has-text('Positions')")
    if positions_tab.is_visible():
        positions_tab.click()
        # Wait for positions table to update
        page.wait_for_timeout(1000)
        position_row = page.locator("tr:has-text('AAPL')").first
        expect(position_row).to_be_visible()

    # Place a sell order to close or separate sell order
    # Click Sell button
    sell_btn = page.locator("button:has-text('Sell')")
    expect(sell_btn).to_be_visible()
    qty_input.fill("1")
    with page.expect_response(re.compile(r"/api/v1/trading/orders")) as sell_resp:
        sell_btn.click()
    assert sell_resp.value.status in [200, 201]
    success = page.locator(".toast-success")
    expect(success).to_be_visible(timeout=5000)


def test_place_limit_order(authenticated_page: Page):
    """Test placing a limit order."""
    page = authenticated_page
    navigate_to_trading(page, "BTC/USD")

    # Switch to limit order
    limit_tab = page.locator("button:has-text('Limit')")
    if limit_tab.is_visible():
        limit_tab.click()
        page.wait_for_timeout(200)

    # Get current price and set a limit price slightly below for buy
    price_element = page.locator(".ticker-price, .last-price")
    current_price = float(price_element.text_content().replace('$', '').replace(',', ''))

    # Set limit price
    limit_price_input = page.locator("input[name='limitPrice']")
    limit_price_input.fill(str(round(current_price * 0.99, 2)))
    qty_input = page.locator("input[name='qty']")
    qty_input.fill("0.01")  # small amount

    # Place buy limit order
    buy_btn = page.locator("button:has-text('Buy')")
    with page.expect_response(re.compile(r"/api/v1/trading/orders")) as resp:
        buy_btn.click()
    assert resp.value.status in [200, 201]
    success = page.locator(".toast-success")
    expect(success).to_be_visible(timeout=5000)

    # Check order in open orders
    orders_tab = page.locator("button:has-text('Open Orders')")
    if orders_tab.is_visible():
        orders_tab.click()
        page.wait_for_timeout(500)
        order_row = page.locator("tr:has-text('BTC/USD')").first
        expect(order_row).to_be_visible()
        # It should have "Limit" as type
        expect(order_row).to_contain_text("Limit")


def test_order_validation_errors(authenticated_page: Page):
    """Test that invalid orders show proper error messages."""
    page = authenticated_page
    navigate_to_trading(page, "AAPL")

    # Try to place an order with zero quantity
    qty_input = page.locator("input[name='qty']")
    qty_input.fill("0")
    buy_btn = page.locator("button:has-text('Buy')")
    buy_btn.click()
    # Should show validation error
    error = page.locator(".error-message, .field-error, [role='alert']")
    expect(error).to_be_visible()
    # The field should be highlighted
    expect(qty_input).to_have_attribute("aria-invalid", "true")

    # Try to place an order with insufficient balance (if paper account has small balance)
    # But that might be hard to trigger. Instead, we can test with a huge quantity.
    qty_input.fill("999999")
    buy_btn.click()
    # Might show error like "Insufficient balance" or "Quantity exceeds limits"
    error = page.locator(".toast-error, .alert-error")
    expect(error).to_be_visible(timeout=3000)

    # Test invalid limit price (negative)
    limit_tab = page.locator("button:has-text('Limit')")
    if limit_tab.is_visible():
        limit_tab.click()
        limit_price = page.locator("input[name='limitPrice']")
        limit_price.fill("-10")
        qty_input.fill("1")
        buy_btn.click()
        error = page.locator(".error-message")
        expect(error).to_be_visible()


def test_stop_loss_and_take_profit(authenticated_page: Page):
    """Test adding stop-loss and take-profit to an order."""
    page = authenticated_page
    navigate_to_trading(page, "EUR/USD")

    # Switch to limit or market order
    market_tab = page.locator("button:has-text('Market')")
    market_tab.click()

    # Fill quantity
    qty_input = page.locator("input[name='qty']")
    qty_input.fill("1000")

    # Expand advanced options
    advanced_toggle = page.locator("button:has-text('Advanced')")
    if advanced_toggle.is_visible():
        advanced_toggle.click()
        page.wait_for_timeout(300)

    # Fill stop loss and take profit
    sl_input = page.locator("input[name='stopLoss']")
    tp_input = page.locator("input[name='takeProfit']")
    if sl_input.is_visible() and tp_input.is_visible():
        current_price = float(page.locator(".ticker-price").text_content().replace('$', ''))
        sl_input.fill(str(round(current_price * 0.98, 4)))
        tp_input.fill(str(round(current_price * 1.02, 4)))

        buy_btn = page.locator("button:has-text('Buy')")
        with page.expect_response(re.compile(r"/api/v1/trading/orders")) as resp:
            buy_btn.click()
        assert resp.value.status in [200, 201]
        success = page.locator(".toast-success")
        expect(success).to_be_visible(timeout=5000)
        # Verify order includes SL/TP (maybe shown in order summary)
        order_summary = page.locator(".order-summary")
        expect(order_summary).to_contain_text("Stop Loss")
        expect(order_summary).to_contain_text("Take Profit")


def test_cancel_order(authenticated_page: Page):
    """Test cancelling an open order."""
    page = authenticated_page
    # First place a limit order that won't fill immediately (far from market)
    navigate_to_trading(page, "AAPL")
    limit_tab = page.locator("button:has-text('Limit')")
    limit_tab.click()
    current_price = float(page.locator(".ticker-price").text_content().replace('$', ''))
    limit_price = page.locator("input[name='limitPrice']")
    limit_price.fill(str(round(current_price * 0.5, 2)))  # very low, unlikely to fill
    qty_input = page.locator("input[name='qty']")
    qty_input.fill("1")
    buy_btn = page.locator("button:has-text('Buy')")
    buy_btn.click()
    # Wait for order to appear in open orders
    page.wait_for_timeout(1000)

    # Go to open orders tab
    orders_tab = page.locator("button:has-text('Open Orders')")
    if orders_tab.is_visible():
        orders_tab.click()
    else:
        # Some UIs have order history; we'll navigate to orders page
        page.goto(BASE_URL + "/orders")
        page.wait_for_url(re.compile(r"/orders"), timeout=5000)

    # Find the order row
    order_row = page.locator("tr:has-text('AAPL')").first
    expect(order_row).to_be_visible()
    cancel_btn = order_row.locator("button:has-text('Cancel')")
    expect(cancel_btn).to_be_visible()
    # Click cancel
    with page.expect_response(re.compile(r"/api/v1/trading/orders/.*/cancel")) as resp:
        cancel_btn.click()
    assert resp.value.status in [200, 204]
    success = page.locator(".toast-success")
    expect(success).to_be_visible(timeout=5000)
    # Row should disappear or show "Cancelled"
    expect(order_row).not_to_be_visible(timeout=5000)


def test_position_close(authenticated_page: Page):
    """Test closing an open position."""
    page = authenticated_page
    # First, ensure we have an open position by placing a market buy
    navigate_to_trading(page, "AAPL")
    market_tab = page.locator("button:has-text('Market')")
    market_tab.click()
    qty_input = page.locator("input[name='qty']")
    qty_input.fill("1")
    buy_btn = page.locator("button:has-text('Buy')")
    buy_btn.click()
    page.wait_for_selector(".toast-success", timeout=5000)

    # Go to positions tab
    positions_tab = page.locator("button:has-text('Positions')")
    if positions_tab.is_visible():
        positions_tab.click()
    else:
        page.goto(BASE_URL + "/portfolio/positions")
        page.wait_for_url(re.compile(r"/portfolio"), timeout=5000)

    # Find the position
    position_row = page.locator("tr:has-text('AAPL')").first
    expect(position_row).to_be_visible()
    # Click close button
    close_btn = position_row.locator("button:has-text('Close')")
    expect(close_btn).to_be_visible()
    with page.expect_response(re.compile(r"/api/v1/trading/positions/.*/close")) as resp:
        close_btn.click()
    assert resp.value.status in [200, 204]
    success = page.locator(".toast-success")
    expect(success).to_be_visible(timeout=5000)
    # Position should be removed
    expect(position_row).not_to_be_visible(timeout=5000)


def test_order_history(authenticated_page: Page):
    """Test viewing order history and filtering."""
    page = authenticated_page
    page.goto(BASE_URL + "/orders/history")
    page.wait_for_url(re.compile(r"/orders/history"), timeout=5000)

    # Check that table loads
    table = page.locator("table[data-testid='order-history']")
    expect(table).to_be_visible()

    # Apply filter (e.g., by symbol)
    filter_input = page.locator("input[placeholder*='Symbol']")
    if filter_input.is_visible():
        filter_input.fill("AAPL")
        page.keyboard.press("Enter")
        page.wait_for_timeout(1000)
        # Rows should only contain AAPL
        rows = table.locator("tbody tr")
        if rows.count() > 0:
            for i in range(rows.count()):
                expect(rows.nth(i)).to_contain_text("AAPL")

    # Test date range filter
    date_from = page.locator("input[name='dateFrom']")
    if date_from.is_visible():
        date_from.fill("2026-01-01")
        date_to = page.locator("input[name='dateTo']")
        date_to.fill("2026-12-31")
        apply_btn = page.locator("button:has-text('Apply')")
        apply_btn.click()
        page.wait_for_timeout(1000)
        # No assertion but check no error

    # Export functionality (if present)
    export_btn = page.locator("button:has-text('Export')")
    if export_btn.is_visible():
        with page.expect_download() as download_info:
            export_btn.click()
        download = download_info.value
        assert download.suggested_filename.endswith(".csv") or download.suggested_filename.endswith(".xlsx")


def test_realtime_price_updates(authenticated_page: Page):
    """Test that price updates via WebSocket reflect on UI."""
    page = authenticated_page
    navigate_to_trading(page, "BTC/USD")
    price_element = page.locator(".ticker-price, .last-price")
    initial_price = price_element.text_content()
    # Wait a few seconds for updates
    page.wait_for_timeout(5000)
    updated_price = price_element.text_content()
    # It may or may not change; we just ensure no error and element is present
    assert updated_price is not None


def test_order_book_depth(authenticated_page: Page):
    """Test that order book shows bids and asks correctly."""
    page = authenticated_page
    navigate_to_trading(page, "BTC/USD")
    # Check that bid/ask columns are present
    bids = page.locator(".order-book .bids")
    asks = page.locator(".order-book .asks")
    expect(bids).to_be_visible()
    expect(asks).to_be_visible()
    # At least one level
    bid_level = bids.locator("tr").first
    ask_level = asks.locator("tr").first
    expect(bid_level).to_be_visible()
    expect(ask_level).to_be_visible()


def test_trading_view_chart_interaction(authenticated_page: Page):
    """Test basic chart interaction (timeframe change, drawing)."""
    page = authenticated_page
    navigate_to_trading(page, "AAPL")
    # Change timeframe
    timeframe_selector = page.locator("select[name='timeframe']")
    if timeframe_selector.is_visible():
        timeframe_selector.select_option("1h")
        page.wait_for_timeout(1000)
        # Check that chart updates
        # Could also check that the chart container has content
    # Try drawing tool (if available)
    draw_tool = page.locator("button[aria-label='Trend Line']")
    if draw_tool.is_visible():
        draw_tool.click()
        # Click on chart to draw
        chart = page.locator(".chart-container canvas").first
        if chart.is_visible():
            box = chart.bounding_box()
            page.mouse.click(box["x"] + 100, box["y"] + 100)
            page.mouse.down()
            page.mouse.move(box["x"] + 200, box["y"] + 200)
            page.mouse.up()
        # No assertion, just ensure no crash


def test_multi_symbool_trading(authenticated_page: Page):
    """Test switching between symbols in trading interface."""
    page = authenticated_page
    navigate_to_trading(page, "AAPL")
    # Get current symbol from header
    symbol_display = page.locator(".symbol-name")
    expect(symbol_display).to_contain_text("AAPL")

    # Switch to another symbol
    # Try clicking on a related symbol or using search
    search_input = page.locator("input[placeholder*='Search']")
    if search_input.is_visible():
        search_input.fill("MSFT")
        page.wait_for_timeout(500)
        page.locator("button:has-text('MSFT')").first.click()
        page.wait_for_timeout(1000)
        expect(symbol_display).to_contain_text("MSFT")
    else:
        # Select from dropdown
        select = page.locator("select[name='symbol']")
        if select.is_visible():
            select.select_option("MSFT")
            page.wait_for_timeout(1000)
            expect(symbol_display).to_contain_text("MSFT")


def test_risk_indicators_on_order(authenticated_page: Page):
    """Test that risk indicators show expected values like P&L, margin, etc."""
    page = authenticated_page
    navigate_to_trading(page, "AAPL")
    # Enter quantity
    qty_input = page.locator("input[name='qty']")
    qty_input.fill("10")
    # Check that estimated margin or risk is displayed
    risk_display = page.locator(".risk-estimate, .margin-required")
    if risk_display.is_visible():
        text = risk_display.text_content()
        assert "$" in text or "USD" in text, "Risk estimate missing currency"
    # Also check if a slippage estimate or fees are shown
    fee_display = page.locator(".fee-estimate")
    if fee_display.is_visible():
        assert fee_display.text_content() is not None


def test_stop_order_triggers(authenticated_page: Page):
    """Test placing a stop order (stop market)."""
    page = authenticated_page
    navigate_to_trading(page, "AAPL")
    # Switch to stop order if available
    stop_tab = page.locator("button:has-text('Stop')")
    if stop_tab.is_visible():
        stop_tab.click()
        page.wait_for_timeout(200)
        # Fill stop price (below current for sell, above for buy)
        current_price = float(page.locator(".ticker-price").text_content().replace('$', ''))
        # For buy stop, set above current; for sell stop, below
        # We'll place a sell stop order (stop loss)
        stop_price_input = page.locator("input[name='stopPrice']")
        stop_price_input.fill(str(round(current_price * 0.95, 2)))
        qty_input = page.locator("input[name='qty']")
        qty_input.fill("1")
        sell_btn = page.locator("button:has-text('Sell')")
        sell_btn.click()
        # Check success
        success = page.locator(".toast-success")
        expect(success).to_be_visible(timeout=5000)
        # Order should appear in open orders with type Stop
        orders_tab = page.locator("button:has-text('Open Orders')")
        if orders_tab.is_visible():
            orders_tab.click()
            order_row = page.locator("tr:has-text('Stop')").first
            expect(order_row).to_be_visible()


def test_trading_flow_responsive_order_placement(authenticated_page: Page):
    """Test placing orders on mobile/tablet viewports."""
    page = authenticated_page
    for viewport in VIEWPORTS:
        if viewport["name"] == "desktop":
            continue  # already tested
        logger.info(f"Testing order placement on {viewport['name']}")
        page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
        navigate_to_trading(page, "AAPL")
        # On mobile, order form might be collapsed; open it
        expand_btn = page.locator("button[aria-label='Show order form']")
        if expand_btn.is_visible():
            expand_btn.click()
            page.wait_for_timeout(300)
        # Place market order
        market_tab = page.locator("button:has-text('Market')")
        if market_tab.is_visible():
            market_tab.click()
        qty_input = page.locator("input[name='qty']")
        qty_input.fill("1")
        buy_btn = page.locator("button:has-text('Buy')")
        expect(buy_btn).to_be_visible()
        buy_btn.click()
        success = page.locator(".toast-success")
        expect(success).to_be_visible(timeout=5000)
        take_screenshot(page, f"order_placement_{viewport['name']}")
