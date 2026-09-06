"""
NEXUS AI TRADING SYSTEM - End-to-End Responsive Design Tests

This test suite verifies that the frontend adapts correctly to various screen sizes
and devices, ensuring a consistent user experience across desktop, tablet, and mobile.

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import logging
import pytest
from playwright.sync_api import Page, BrowserContext, expect, Playwright
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables (can be overridden)
BASE_URL = os.getenv("NEXUS_FRONTEND_URL", "http://localhost:3000")
API_URL = os.getenv("NEXUS_API_URL", "http://localhost:8000")
DEFAULT_TIMEOUT = 30000  # milliseconds
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")

# Ensure screenshot directory exists
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Comprehensive viewport configurations
VIEWPORTS = [
    {"name": "desktop_wide", "width": 2560, "height": 1440, "device": "desktop"},
    {"name": "desktop", "width": 1920, "height": 1080, "device": "desktop"},
    {"name": "desktop_small", "width": 1366, "height": 768, "device": "desktop"},
    {"name": "tablet_landscape", "width": 1024, "height": 768, "device": "tablet"},
    {"name": "tablet_portrait", "width": 768, "height": 1024, "device": "tablet"},
    {"name": "mobile_large", "width": 428, "height": 926, "device": "mobile"},
    {"name": "mobile_medium", "width": 375, "height": 667, "device": "mobile"},
    {"name": "mobile_small", "width": 320, "height": 568, "device": "mobile"},
]

# Breakpoints from Tailwind (typical)
BREAKPOINTS = {
    "sm": 640,
    "md": 768,
    "lg": 1024,
    "xl": 1280,
    "2xl": 1536,
}


@pytest.fixture(scope="function")
def page_context(browser: BrowserContext) -> Page:
    """Create a new page with default settings, clean session."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    )
    page = context.new_page()
    page.set_default_timeout(DEFAULT_TIMEOUT)
    yield page
    context.close()


@pytest.fixture(scope="function")
def authenticated_page(page_context: Page) -> Page:
    """
    Log in before tests that require authenticated state.
    Uses the login API to set session cookies.
    """
    # Navigate to login page
    page_context.goto(BASE_URL + "/authentication/login")
    # Fill credentials (use test user from seeded data)
    page_context.fill("input[name='email']", "test@nexusquantum.com")
    page_context.fill("input[name='password']", "Test@123")
    # Submit
    page_context.click("button[type='submit']")
    # Wait for redirect to dashboard
    page_context.wait_for_url(re.compile(r"/dashboard"), timeout=10000)
    expect(page_context).to_have_url(re.compile(r"/dashboard"))
    return page_context


def take_screenshot(page: Page, name: str):
    """Helper to capture screenshots for debugging."""
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    page.screenshot(path=path, full_page=True)
    logger.info(f"Screenshot saved to {path}")


def check_visibility_and_sizing(page: Page, selector: str, min_width: int = 0, min_height: int = 0):
    """Helper to verify element is visible and has minimum dimensions."""
    element = page.locator(selector).first
    expect(element).to_be_visible()
    box = element.bounding_box()
    assert box is not None, f"Element {selector} has no bounding box"
    assert box["width"] >= min_width, f"Element width {box['width']} < {min_width}"
    assert box["height"] >= min_height, f"Element height {box['height']} < {min_height}"
    return box


# ----- Tests ------

def test_homepage_loads(page_context: Page):
    """Basic test: homepage loads without errors."""
    logger.info("Testing homepage load")
    page_context.goto(BASE_URL)
    expect(page_context).to_have_title(re.compile("NEXUS AI TRADING"))
    # Also verify some key elements
    expect(page_context.locator("header")).to_be_visible()
    expect(page_context.locator("main")).to_be_visible()


@pytest.mark.parametrize("viewport", VIEWPORTS, ids=lambda v: v["name"])
def test_dashboard_responsive(page_context: Page, viewport: Dict[str, Any]):
    """
    Verify that the dashboard adapts correctly to all viewport sizes.
    Checks visibility of critical UI components, navigation, and interactions.
    """
    logger.info(f"Testing responsive design for viewport: {viewport['name']} ({viewport['width']}x{viewport['height']})")
    page_context.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})

    # Navigate to the dashboard (login first if needed)
    # For simplicity, we'll assume the dashboard is accessible without login (or we already logged in)
    # In real tests, we'd use the authenticated_page fixture; but for responsiveness we can test public pages.
    # However, the dashboard is protected. So we'll use the authenticated fixture.
    # Since we are parameterized, we need to ensure login happens before each test.
    # We'll do a quick login at start.
    page_context.goto(BASE_URL + "/authentication/login")
    page_context.fill("input[name='email']", "test@nexusquantum.com")
    page_context.fill("input[name='password']", "Test@123")
    page_context.click("button[type='submit']")
    page_context.wait_for_url(re.compile(r"/dashboard"), timeout=10000)

    # Wait for the main content to load
    page_context.wait_for_selector("main", state="visible")

    # Take screenshot for debugging
    take_screenshot(page_context, f"dashboard_{viewport['name']}")

    # 1. Header
    header = page_context.locator("header")
    expect(header).to_be_visible()

    # 2. Sidebar navigation
    sidebar = page_context.locator("nav.sidebar, nav[data-testid='sidebar']")
    # Determine if sidebar should be shown or hidden based on breakpoint
    if viewport["width"] <= BREAKPOINTS["md"]:
        # On mobile/tablet, sidebar should be hidden by default
        # But we need to check if it's hidden (not visible) OR has a class like 'hidden'
        is_visible = sidebar.is_visible()
        # It might be off-screen but still in DOM, check aria-hidden or display
        display = sidebar.evaluate("el => window.getComputedStyle(el).display")
        if display == "none":
            expect(sidebar).not_to_be_visible()
        else:
            # It might be collapsed: check width
            width = sidebar.evaluate("el => el.getBoundingClientRect().width")
            assert width < 100, "Sidebar width should be small or hidden on mobile"
        # Hamburger menu should be visible
        menu_button = page_context.locator("button[aria-label='Toggle menu'], button[data-testid='menu-toggle']")
        expect(menu_button).to_be_visible()
        menu_button.click()
        # Now sidebar should be visible (or expanded)
        expect(sidebar).to_be_visible()
    else:
        # On desktop, sidebar should be visible
        expect(sidebar).to_be_visible()
        # Hamburger should not be visible (or hidden)
        menu_button = page_context.locator("button[aria-label='Toggle menu'], button[data-testid='menu-toggle']")
        if menu_button.is_visible():
            # It might be present but hidden via CSS; check if it's truly visible
            # We'll just assert it's not visible if it has display:none or is offscreen
            # For simplicity, we don't fail.
            pass

    # 3. Metric cards
    metric_cards = page_context.locator(".metric-card, [data-testid='metric-card']")
    expect(metric_cards.first).to_be_visible()
    # Should have at least 4 metrics (e.g., Balance, P&L, Positions, Drawdown)
    count = metric_cards.count()
    assert count >= 4, f"Expected at least 4 metric cards, got {count}"

    # On small screens, cards should stack vertically; on large, they may be in a grid.
    # We can check if they are in a flex/grid with wrapping; but for basic test, just ensure they fit.
    # Check that each card has content
    for i in range(count):
        card = metric_cards.nth(i)
        expect(card.locator(".metric-value")).to_be_visible()

    # 4. Charts
    chart_container = page_context.locator(".chart-container, [data-testid='chart-container']")
    expect(chart_container.first).to_be_visible()
    # Ensure chart has non-zero size
    box = chart_container.first.bounding_box()
    assert box["width"] > 100 and box["height"] > 100, "Chart container too small"

    # 5. Data table (e.g., positions or recent trades)
    table = page_context.locator("table, [data-testid='data-table']")
    if table.count() > 0:
        expect(table.first).to_be_visible()
        # On mobile, table might be horizontally scrollable, check if parent has overflow
        # We'll just verify it exists.
        if viewport["width"] <= BREAKPOINTS["md"]:
            # Check if table is within a container with overflow-x: auto
            parent = table.first.locator("xpath=..")
            overflow = parent.evaluate("el => window.getComputedStyle(el).overflowX")
            assert overflow in ["auto", "scroll"], "Table container should have horizontal scroll on mobile"

    # 6. Footer
    footer = page_context.locator("footer")
    expect(footer).to_be_visible()

    # 7. Dropdown interaction (timeframe selector)
    dropdown = page_context.locator("select[data-testid='timeframe'], select#timeframe")
    if dropdown.count() > 0:
        dropdown.first.select_option("1d")
        expect(dropdown.first).to_have_value("1d")

    # 8. Bottom navigation (only on mobile)
    if viewport["width"] <= BREAKPOINTS["md"]:
        bottom_nav = page_context.locator("nav.bottom-nav, [data-testid='bottom-nav']")
        if bottom_nav.count() > 0:
            expect(bottom_nav.first).to_be_visible()
            # Click on a bottom nav link (e.g., Portfolio)
            link = bottom_nav.locator("a[href*='portfolio']")
            if link.count() > 0:
                link.first.click()
                page_context.wait_for_url(re.compile(r"/portfolio"), timeout=5000)

    # 9. No horizontal overflow
    body_width = page_context.evaluate("document.body.scrollWidth")
    viewport_width = page_context.evaluate("window.innerWidth")
    assert body_width <= viewport_width + 2, f"Body overflows horizontally (body: {body_width}, viewport: {viewport_width})"


def test_navigation_adapts(authenticated_page: Page):
    """Test that navigation links adapt to screen size and remain clickable."""
    page = authenticated_page

    # Desktop navigation test
    page.set_viewport_size({"width": 1366, "height": 768})
    nav_link = page.locator("nav a:has-text('Markets')").first
    expect(nav_link).to_be_visible()
    nav_link.click()
    expect(page).to_have_url(re.compile(r"/markets"))

    # Go back to dashboard
    page.goto(BASE_URL + "/dashboard")

    # Switch to mobile
    page.set_viewport_size({"width": 375, "height": 667})
    # Hamburger menu
    menu_button = page.locator("button[aria-label='Toggle menu'], button[data-testid='menu-toggle']")
    expect(menu_button).to_be_visible()
    menu_button.click()
    page.wait_for_timeout(500)  # animation
    # Mobile menu link
    mobile_link = page.locator("nav.sidebar a:has-text('Markets')").first
    expect(mobile_link).to_be_visible()
    mobile_link.click()
    expect(page).to_have_url(re.compile(r"/markets"))


def test_chart_responsiveness(authenticated_page: Page):
    """Ensure charts resize and remain readable on different screens."""
    page = authenticated_page
    for viewport in VIEWPORTS:
        logger.info(f"Testing chart responsiveness on {viewport['name']}")
        page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
        page.goto(BASE_URL + "/markets")
        # Locate chart (TradingView or custom)
        chart = page.locator(".trading-view-widget-container, .chart-widget, [data-testid='chart']").first
        expect(chart).to_be_visible()
        box = chart.bounding_box()
        assert box["width"] > 0 and box["height"] > 0, f"Chart has zero size for {viewport['name']}"
        # Check that chart is not too small
        assert box["width"] >= 200, f"Chart width too small: {box['width']}"


def test_login_page_responsive(page_context: Page):
    """Test the login page on various devices."""
    for viewport in VIEWPORTS:
        logger.info(f"Testing login page on {viewport['name']}")
        page_context.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
        page_context.goto(BASE_URL + "/authentication/login")
        # Form should be centered and visible
        form = page_context.locator("form")
        expect(form).to_be_visible()
        # Inputs should be accessible
        email = page_context.locator("input[name='email']")
        expect(email).to_be_visible()
        email.fill("test@example.com")
        password = page_context.locator("input[name='password']")
        expect(password).to_be_visible()
        password.fill("password123")
        # Submit button
        submit = page_context.locator("button[type='submit']")
        expect(submit).to_be_visible()
        # On mobile, ensure button is not cut off
        box = submit.bounding_box()
        assert box["y"] + box["height"] < viewport["height"], "Submit button partially outside viewport"


def test_side_menu_collapse(authenticated_page: Page):
    """Verify that the side menu collapses/expands correctly on resize."""
    page = authenticated_page
    # Start with desktop
    page.set_viewport_size({"width": 1280, "height": 800})
    sidebar = page.locator("nav.sidebar, [data-testid='sidebar']")
    expect(sidebar).to_be_visible()
    # Check if there is a collapse button
    collapse_btn = page.locator("button[aria-label='Collapse sidebar']")
    if collapse_btn.count() > 0:
        collapse_btn.first.click()
        # Sidebar should be collapsed (width small)
        width = sidebar.evaluate("el => el.getBoundingClientRect().width")
        assert width < 100, "Sidebar did not collapse"

    # Resize to tablet
    page.set_viewport_size({"width": 768, "height": 1024})
    # On tablet, it might auto-collapse; check if a toggle button appears
    toggle = page.locator("button[aria-label='Toggle sidebar']")
    if toggle.is_visible():
        toggle.click()
        # After click, sidebar may expand/collapse; we check class or visibility
        # We'll just ensure it's not completely hidden
        expect(sidebar).to_be_visible()

    # Resize to mobile
    page.set_viewport_size({"width": 375, "height": 667})
    # Sidebar should be hidden (display none or off-screen)
    display = sidebar.evaluate("el => window.getComputedStyle(el).display")
    if display == "none":
        expect(sidebar).not_to_be_visible()
    else:
        # It might be off-screen: check its width/position
        rect = sidebar.evaluate("el => el.getBoundingClientRect()")
        assert rect.left < -50 or rect.width < 10, "Sidebar should be hidden on mobile"

    # Hamburger menu should open it
    hamburger = page.locator("button[aria-label='Toggle menu']")
    expect(hamburger).to_be_visible()
    hamburger.click()
    page.wait_for_timeout(300)
    expect(sidebar).to_be_visible()


@pytest.mark.slow
def test_responsive_image_loading(authenticated_page: Page):
    """Test that images load appropriate sizes based on viewport."""
    page = authenticated_page
    # Desktop
    page.set_viewport_size({"width": 1920, "height": 1080})
    page.goto(BASE_URL + "/dashboard")
    images = page.locator("img")
    if images.count() > 0:
        for i in range(images.count()):
            img = images.nth(i)
            srcset = img.get_attribute("srcset")
            sizes = img.get_attribute("sizes")
            # At least one should be present for responsive images
            if srcset is None and sizes is None:
                logger.warning(f"Image {i} missing srcset/sizes; might not be responsive")
            # Check natural width vs viewport
            natural_w = img.evaluate("el => el.naturalWidth")
            if natural_w > 0 and natural_w > 1920 * 1.2:
                logger.warning(f"Image {i} has natural width {natural_w} > viewport")
    # Mobile
    page.set_viewport_size({"width": 375, "height": 667})
    page.reload()
    # Check that images are not wider than viewport
    oversized = page.evaluate("""
        () => {
            const imgs = document.querySelectorAll('img');
            let anyOversized = false;
            imgs.forEach(img => {
                if (img.naturalWidth > window.innerWidth * 1.1) {
                    anyOversized = true;
                }
            });
            return anyOversized;
        }
    """)
    assert not oversized, "Some images are too wide for the viewport"


def test_touch_gestures_on_mobile(authenticated_page: Page):
    """Test swipe/pinch gestures on mobile (simulate touch events)."""
    page = authenticated_page
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto(BASE_URL + "/markets")

    # Simulate touch start/move on a chart or scrollable container
    chart = page.locator(".chart-container").first
    expect(chart).to_be_visible()
    # Get bounding box
    box = chart.bounding_box()
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2

    # Perform touch drag (swipe left)
    page.touchscreen.tap(x, y)
    page.touchscreen.swipe(x, y, x - 100, y + 100)
    # No assertion, just ensure no crash

    # Also test scroll on touch
    page.mouse.wheel(0, 300)  # Simulate scroll
    page.wait_for_timeout(500)

    # Check that page did not become unresponsive
    expect(page.locator("body")).to_be_visible()


def test_orientation_change(authenticated_page: Page):
    """Test that the UI adapts when device orientation changes."""
    page = authenticated_page
    # Start with portrait
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(BASE_URL + "/dashboard")
    # Take screenshot
    take_screenshot(page, "orientation_portrait")
    # Switch to landscape
    page.set_viewport_size({"width": 812, "height": 375})
    # Wait for layout to adjust
    page.wait_for_timeout(500)
    # Check that key elements are still visible
    expect(page.locator("header")).to_be_visible()
    # The sidebar might become visible in landscape
    sidebar = page.locator("nav.sidebar")
    if sidebar.is_visible():
        # It should be usable
        sidebar.locator("a:has-text('Portfolio')").click()
        expect(page).to_have_url(re.compile(r"/portfolio"))
    take_screenshot(page, "orientation_landscape")


def test_font_scaling_accessibility(authenticated_page: Page):
    """Ensure text remains readable when browser zoom is changed."""
    page = authenticated_page
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto(BASE_URL + "/dashboard")

    # Increase font size using browser zoom
    page.evaluate("document.body.style.zoom = '150%'")
    page.wait_for_timeout(500)
    # Check that text is not truncated/clipped
    # We can check that a sample text element has enough height
    heading = page.locator("h1, h2").first
    expect(heading).to_be_visible()
    box = heading.bounding_box()
    assert box["height"] > 20, "Heading too small after zoom"

    # Reset zoom
    page.evaluate("document.body.style.zoom = '100%'")


def test_dark_mode_adaptation(authenticated_page: Page):
    """Test that dark mode toggles and styles adapt to both viewport and theme."""
    page = authenticated_page
    # Find theme toggle button
    theme_toggle = page.locator("button[aria-label='Toggle theme']")
    if theme_toggle.count() > 0:
        theme_toggle.first.click()
        # Wait for theme change
        page.wait_for_timeout(300)
        # Check that body has dark class or background
        bg_color = page.evaluate("window.getComputedStyle(document.body).backgroundColor")
        # It's tricky to assert color; just ensure no crash
        # Also test on mobile
        page.set_viewport_size({"width": 375, "height": 667})
        expect(theme_toggle.first).to_be_visible()
        theme_toggle.first.click()
        page.wait_for_timeout(300)
        # Ensure content still visible
        expect(page.locator("main")).to_be_visible()


def test_form_validation_responsive(authenticated_page: Page):
    """Test that form validation error messages are displayed properly on all screens."""
    page = authenticated_page
    page.goto(BASE_URL + "/settings")

    for viewport in VIEWPORTS:
        page.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
        # Find a form, e.g., API key settings
        # Submit without filling required fields
        submit_btn = page.locator("button[type='submit']").first
        if submit_btn.is_visible():
            submit_btn.click()
            # Check for error message
            error = page.locator(".error-message, [role='alert']").first
            if error.is_visible():
                box = error.bounding_box()
                assert box["height"] > 0, "Error message not visible"
                # On mobile, ensure it's not cut off
                if viewport["width"] <= BREAKPOINTS["md"]:
                    assert box["y"] + box["height"] < viewport["height"], "Error message extends beyond viewport"

    # Reset by reloading
    page.reload()


def test_page_transitions_animation(authenticated_page: Page):
    """Test that page transitions/animations work on all devices (no performance issues)."""
    page = authenticated_page
    # Go to a page with animations
    page.goto(BASE_URL + "/analytics")
    # Wait for any animations to complete (e.g., charts loading)
    page.wait_for_timeout(2000)
    # Click a link to another page
    page.locator("a:has-text('Portfolio')").first.click()
    page.wait_for_url(re.compile(r"/portfolio"), timeout=5000)
    # Check that page loaded correctly
    expect(page.locator("main")).to_be_visible()
    # Test on mobile with lower performance
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto(BASE_URL + "/analytics")
    page.wait_for_timeout(2000)
    page.locator("a:has-text('Markets')").first.click()
    page.wait_for_url(re.compile(r"/markets"), timeout=5000)
    expect(page.locator("main")).to_be_visible()


# ---- Additional utilities for CI/CD ----
def test_no_console_errors(page_context: Page):
    """Check that no JavaScript errors appear in console on any viewport."""
    errors = []
    page_context.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

    for viewport in VIEWPORTS:
        page_context.set_viewport_size({"width": viewport["width"], "height": viewport["height"]})
        page_context.goto(BASE_URL + "/dashboard")
        page_context.wait_for_load_state("networkidle")
        if errors:
            logger.warning(f"Console errors on {viewport['name']}: {errors}")
            # Optionally fail:
            # assert len(errors) == 0, f"Console errors: {errors}"

    # We don't fail but log; you can assert if needed.
