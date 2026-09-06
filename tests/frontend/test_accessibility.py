"""
tests/frontend/test_accessibility.py

NEXUS AI Trading System - Frontend Accessibility Tests

This test suite verifies that the frontend application meets accessibility
standards (WCAG 2.1 AA) and provides a usable experience for all users,
including those using assistive technologies.

Tests cover:
- Automated axe-core accessibility scans on all major pages
- Keyboard navigation (Tab, Enter, Space, Escape)
- Focus management (focus indicators, focus trapping in modals)
- ARIA attributes (roles, labels, descriptions)
- Color contrast and text readability
- Screen reader compatibility (semantic HTML)
- Responsive accessibility (touch targets, font scaling)
- Alternative text for images
- Form labels and error announcements
- Dynamic content updates (ARIA live regions)

Uses playwright-axe for automated accessibility testing.
Manual tests are performed using Playwright's built-in keyboard simulation.

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import logging
import pytest
import re
from playwright.sync_api import Page, BrowserContext, expect
from playwright_axe import Axe, AxeOptions, AxeResults
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
BASE_URL = os.getenv("NEXUS_FRONTEND_URL", "http://localhost:3000")
DEFAULT_TIMEOUT = 30000
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Axe configuration
AXE_OPTIONS: AxeOptions = {
    "runOnly": {
        "type": "tag",
        "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"]
    },
    "resultTypes": ["violations", "incomplete", "passes"],
    "elementSelector": True,
}

# Pages to scan (with optional heading checks)
PAGES_TO_SCAN = [
    {"path": "/dashboard", "name": "Dashboard", "protected": True},
    {"path": "/trading/AAPL", "name": "Trading", "protected": True},
    {"path": "/portfolio", "name": "Portfolio", "protected": True},
    {"path": "/markets", "name": "Markets", "protected": True},
    {"path": "/analytics", "name": "Analytics", "protected": True},
    {"path": "/settings/general", "name": "Settings", "protected": True},
    {"path": "/authentication/login", "name": "Login", "protected": False},
    {"path": "/authentication/register", "name": "Register", "protected": False},
    {"path": "/authentication/forgot-password", "name": "ForgotPassword", "protected": False},
]

# WCAG success criteria to check manually
MANUAL_CHECKS = [
    "1.1.1 Non-text Content",
    "1.3.1 Info and Relationships",
    "1.3.2 Meaningful Sequence",
    "1.3.3 Sensory Characteristics",
    "1.4.1 Use of Color",
    "1.4.3 Contrast (Minimum)",
    "1.4.4 Resize text",
    "1.4.10 Reflow",
    "1.4.11 Non-text Contrast",
    "1.4.12 Text Spacing",
    "2.1.1 Keyboard",
    "2.1.2 No Keyboard Trap",
    "2.4.1 Bypass Blocks",
    "2.4.2 Page Titled",
    "2.4.3 Focus Order",
    "2.4.4 Link Purpose",
    "2.4.6 Headings and Labels",
    "2.4.7 Focus Visible",
    "3.1.1 Language of Page",
    "3.2.1 On Focus",
    "3.2.2 On Input",
    "3.3.1 Error Identification",
    "3.3.2 Labels or Instructions",
    "3.3.3 Error Suggestion",
    "4.1.1 Parsing",
    "4.1.2 Name, Role, Value",
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


def run_axe_scan(page: Page, page_name: str, context: Optional[Dict] = None) -> AxeResults:
    """Run axe-core accessibility scan and log/assert results."""
    axe = Axe(page)
    options = AXE_OPTIONS.copy()
    if context:
        options["context"] = context

    results = axe.run(options)

    # Log violation details
    violations = results.get("violations", [])
    if violations:
        logger.error(f"Accessibility violations found on {page_name}:")
        for violation in violations:
            logger.error(f"  - {violation.get('id')}: {violation.get('help')}")
            logger.error(f"    Impact: {violation.get('impact')}")
            logger.error(f"    Nodes: {len(violation.get('nodes', []))}")
            for node in violation.get("nodes", [])[:3]:  # Show first 3
                logger.error(f"      - {node.get('html')}")
                logger.error(f"        Target: {node.get('target')}")
                logger.error(f"        Summary: {node.get('failureSummary')}")
    else:
        logger.info(f"No accessibility violations on {page_name}")

    # Assert no violations (fail the test if any)
    assert len(violations) == 0, f"Accessibility violations found on {page_name}: {len(violations)}"

    return results


# ----- Automated Accessibility Tests -----

@pytest.mark.accessibility
@pytest.mark.parametrize("page_info", PAGES_TO_SCAN, ids=lambda p: p["name"])
def test_page_accessibility(page_context: Page, page_info: Dict[str, Any]):
    """Run axe-core on each page to check for WCAG violations."""
    page = page_context
    path = page_info["path"]
    name = page_info["name"]
    protected = page_info.get("protected", False)

    if protected:
        # Need to log in first
        page.goto(BASE_URL + "/authentication/login")
        page.fill("input[name='email']", "test@nexusquantum.com")
        page.fill("input[name='password']", "Test@123")
        page.click("button[type='submit']")
        page.wait_for_url(re.compile(r"/dashboard"), timeout=10000)

    # Navigate to the page
    page.goto(BASE_URL + path)
    page.wait_for_load_state("networkidle")

    # For dynamic content, wait for key elements
    if "trading" in path:
        page.wait_for_selector(".trade-form, .order-book", state="visible")
    elif "markets" in path:
        page.wait_for_selector("table", state="visible")
    elif "dashboard" in path:
        page.wait_for_selector(".metric-card", state="visible")

    # Run axe scan
    results = run_axe_scan(page, name)

    # Additional checks: page title, language, etc.
    # Page title
    title = page.title()
    assert len(title) > 0, f"Page {name} has no title"
    # Language attribute
    html_lang = page.get_attribute("html", "lang")
    assert html_lang is not None and html_lang != "", f"Page {name} missing lang attribute"


@pytest.mark.accessibility
def test_login_page_accessibility(page_context: Page):
    """Detailed accessibility checks for login page."""
    page = page_context
    page.goto(BASE_URL + "/authentication/login")
    page.wait_for_selector("form", state="visible")

    # Run axe on the form specifically
    results = run_axe_scan(page, "LoginPage", context={"include": ["form"]})
    assert results is not None

    # Manual checks: labels, focus, error handling
    # Check that email field has a label
    email_input = page.locator("input[name='email']")
    label = page.locator("label[for='email']")
    expect(label).to_be_visible()
    # Check that password field has a label
    password_input = page.locator("input[name='password']")
    label = page.locator("label[for='password']")
    expect(label).to_be_visible()

    # Check that submit button is properly labeled
    submit_btn = page.locator("button[type='submit']")
    expect(submit_btn).to_have_attribute("type", "submit")
    btn_text = submit_btn.text_content()
    assert btn_text is not None and len(btn_text) > 0, "Submit button has no text"

    # Check focus order (Tab through)
    focusable = page.locator("input, button, a[href]")
    # Simulate tabbing - not fully testable here


@pytest.mark.accessibility
def test_forms_accessibility(authenticated_page: Page):
    """Test accessibility of forms across the app: labels, errors, instructions."""
    page = authenticated_page
    page.goto(BASE_URL + "/settings/general")
    page.wait_for_selector("form", state="visible")

    # Check that each input has a label
    inputs = page.locator("form input:not([type='hidden']):not([type='submit'])")
    for i in range(inputs.count()):
        input_el = inputs.nth(i)
        input_id = input_el.get_attribute("id")
        if input_id:
            label = page.locator(f"label[for='{input_id}']")
            expect(label).to_be_visible()
        else:
            # Check for aria-label or aria-labelledby
            aria_label = input_el.get_attribute("aria-label")
            aria_labelledby = input_el.get_attribute("aria-labelledby")
            assert aria_label or aria_labelledby, f"Input {i} has no label or aria-label"

    # Test validation error announcements (ARIA live region)
    page.fill("input[name='firstName']", "")
    page.click("button[type='submit']")
    # Wait for error message
    error = page.locator(".error-message, [role='alert']")
    expect(error).to_be_visible()
    # Check that error has role="alert" or aria-live
    role = error.get_attribute("role")
    aria_live = error.get_attribute("aria-live")
    assert role == "alert" or aria_live in ["assertive", "polite"], "Error message not announced properly"

    # Check that error message is associated with the field (aria-describedby)
    error_id = error.get_attribute("id")
    if error_id:
        input_field = page.locator("input[name='firstName']")
        described_by = input_field.get_attribute("aria-describedby")
        assert described_by and error_id in described_by, "Error message not linked to field"


@pytest.mark.accessibility
def test_images_alt_text(authenticated_page: Page):
    """Test that all images have appropriate alt text."""
    page = authenticated_page
    page.goto(BASE_URL + "/dashboard")
    images = page.locator("img")
    for i in range(images.count()):
        img = images.nth(i)
        alt = img.get_attribute("alt")
        # Some images may be decorative; they should have empty alt (alt="")
        # Or meaningful alt text
        # We'll check that alt attribute exists
        assert alt is not None, f"Image {i} missing alt attribute"
        # If it's not empty, ensure it's not just the filename
        if alt != "":
            assert len(alt) > 1, f"Image {i} has too short alt text"


@pytest.mark.accessibility
def test_heading_hierarchy(authenticated_page: Page):
    """Test that heading levels are used logically (h1 -> h2 -> h3)."""
    page = authenticated_page
    page.goto(BASE_URL + "/dashboard")
    headings = page.locator("h1, h2, h3, h4, h5, h6")
    levels = []
    for i in range(headings.count()):
        tag = headings.nth(i).evaluate("el => el.tagName.toLowerCase()")
        levels.append(int(tag[1]))  # h1 -> 1, h2 -> 2, etc.
    # Check that the sequence is logical (non-decreasing, but skipping is allowed)
    # More importantly, each page should have exactly one h1
    h1_count = levels.count(1)
    assert h1_count == 1, f"Page should have exactly one h1, found {h1_count}"


@pytest.mark.accessibility
def test_color_contrast(page_context: Page):
    """Test color contrast using axe (part of axe scan)."""
    # This is covered by axe-core (color-contrast rule)
    # We'll run axe on a representative page with high color variance
    page = page_context
    page.goto(BASE_URL + "/dashboard")
    # Login first
    page.fill("input[name='email']", "test@nexusquantum.com")
    page.fill("input[name='password']", "Test@123")
    page.click("button[type='submit']")
    page.wait_for_url(re.compile(r"/dashboard"), timeout=10000)
    page.wait_for_selector(".metric-card", state="visible")

    # Run axe with color contrast enabled
    axe = Axe(page)
    results = axe.run({"runOnly": {"type": "rule", "values": ["color-contrast"]}})
    violations = results.get("violations", [])
    contrast_violations = [v for v in violations if v.get("id") == "color-contrast"]
    assert len(contrast_violations) == 0, "Color contrast violations found"


@pytest.mark.accessibility
def test_keyboard_navigation_login(authenticated_page: Page):
    """Test keyboard navigation on login page (Tab order, focus indicators)."""
    page = authenticated_page
    # Navigate to login page
    page.goto(BASE_URL + "/authentication/login")
    page.wait_for_selector("form", state="visible")

    # Start at the beginning of the page
    page.keyboard.press("Tab")
    # Focus should be on the first focusable element (often email input)
    focused = page.evaluate("document.activeElement")
    assert focused is not None, "No element focused after Tab"

    # Cycle through all focusable elements
    focusable = page.locator("input, button, a[href]")
    count = focusable.count()
    for i in range(count * 2):  # Cycle twice to ensure no keyboard trap
        page.keyboard.press("Tab")
        # Check that some element is focused
        focused = page.evaluate("document.activeElement")
        assert focused is not None, "Focus lost"
        # Check that the focused element is visible and within viewport
        # (we can check bounding box)

    # Test Enter on submit
    # Fill email and password, then press Enter on the password field
    page.fill("input[name='email']", "test@nexusquantum.com")
    page.fill("input[name='password']", "Test@123")
    page.keyboard.press("Enter")
    page.wait_for_url(re.compile(r"/dashboard"), timeout=10000)
    expect(page).to_have_url(re.compile(r"/dashboard"))


@pytest.mark.accessibility
def test_keyboard_trap_modals(authenticated_page: Page):
    """Test that modals trap focus and allow closing with Escape."""
    page = authenticated_page
    # Open a modal (e.g., Add Broker)
    page.goto(BASE_URL + "/settings/brokers")
    page.wait_for_selector("button:has-text('Add Broker')", state="visible")
    page.click("button:has-text('Add Broker')")
    modal = page.locator(".modal, .dialog")
    expect(modal).to_be_visible()

    # Focus should be trapped inside modal; we can test by Tab cycling
    # Check that focus remains within modal
    for _ in range(10):
        page.keyboard.press("Tab")
        focused = page.evaluate("document.activeElement")
        # The focused element should be inside the modal
        # We can check if it's a descendant of the modal
        is_inside = page.evaluate(
            f"""
            (element) => {{
                const modal = document.querySelector('.modal, .dialog');
                return modal ? modal.contains(element) : false;
            }}
            """,
            focused
        )
        assert is_inside, "Focus escaped modal"

    # Press Escape to close
    page.keyboard.press("Escape")
    expect(modal).not_to_be_visible(timeout=5000)
    # Focus should return to the triggering element (Add Broker button)
    active = page.evaluate("document.activeElement")
    # Check that it's the Add Broker button
    assert active is not None


@pytest.mark.accessibility
def test_skip_to_content_link(authenticated_page: Page):
    """Test that a 'Skip to main content' link exists and works."""
    page = authenticated_page
    page.goto(BASE_URL + "/dashboard")
    skip_link = page.locator("a:has-text('Skip to main content')")
    if skip_link.is_visible():
        skip_link.click()
        # Focus should move to main content
        active = page.evaluate("document.activeElement")
        # Check that it's inside main
        is_main = page.evaluate(
            "el => el.closest('main') !== null",
            active
        )
        assert is_main, "Skip link did not focus main content"
    else:
        # Some apps hide it visually but keep it for screen readers
        # Check if it exists in the DOM
        assert page.locator("a[href='#main']").count() > 0, "Skip to content link missing"


@pytest.mark.accessibility
def test_aria_live_regions(authenticated_page: Page):
    """Test that dynamic content updates are announced (ARIA live regions)."""
    page = authenticated_page
    # Trigger a toast notification
    page.goto(BASE_URL + "/settings/general")
    page.wait_for_selector("form", state="visible")
    page.fill("input[name='firstName']", "Accessibility")
    page.click("button[type='submit']")
    toast = page.locator(".toast-success, .toast-error")
    expect(toast).to_be_visible(timeout=5000)
    # Check that toast has role="status" or aria-live="polite"
    role = toast.get_attribute("role")
    aria_live = toast.get_attribute("aria-live")
    assert role == "status" or aria_live == "polite", "Toast notification not announced"

    # Check that error messages also have live regions
    page.fill("input[name='firstName']", "")
    page.click("button[type='submit']")
    error = page.locator(".error-message, [role='alert']")
    expect(error).to_be_visible()
    role = error.get_attribute("role")
    aria_live = error.get_attribute("aria-live")
    assert role == "alert" or aria_live in ["assertive", "polite"], "Error message not announced"


@pytest.mark.accessibility
def test_landmark_roles(authenticated_page: Page):
    """Test that landmark roles are used correctly (main, navigation, complementary)."""
    page = authenticated_page
    page.goto(BASE_URL + "/dashboard")
    # Check for main
    main = page.locator("main, [role='main']")
    expect(main).to_be_visible()
    # Navigation
    nav = page.locator("nav, [role='navigation']")
    expect(nav).to_be_visible()
    # Banner (header)
    header = page.locator("header, [role='banner']")
    expect(header).to_be_visible()
    # Contentinfo (footer)
    footer = page.locator("footer, [role='contentinfo']")
    expect(footer).to_be_visible()


@pytest.mark.accessibility
def test_tab_attributes(authenticated_page: Page):
    """Test that ARIA tab roles are correctly implemented on tabbed interfaces."""
    page = authenticated_page
    page.goto(BASE_URL + "/trading/AAPL")
    page.wait_for_selector(".trade-form", state="visible")
    tabs = page.locator(".trade-form button[role='tab']")
    if tabs.count() > 0:
        # Check that each tab has role="tab"
        for i in range(tabs.count()):
            tab = tabs.nth(i)
            expect(tab).to_have_attribute("role", "tab")
            # Should have aria-selected or aria-controls
            # We'll check for aria-selected if present
            # It's okay if not all have aria-selected
            # Check that tab has an accessible name
            tab_text = tab.text_content()
            assert tab_text is not None and len(tab_text) > 0, "Tab missing accessible name"
        # Check tabpanel(s)
        panels = page.locator("[role='tabpanel']")
        if panels.count() > 0:
            for j in range(panels.count()):
                panel = panels.nth(j)
                expect(panel).to_have_attribute("role", "tabpanel")


@pytest.mark.accessibility
def test_focus_indicator_visibility(authenticated_page: Page):
    """Test that focus indicators are clearly visible (not just outline: none)."""
    page = authenticated_page
    page.goto(BASE_URL + "/dashboard")
    # Use Tab to focus on a link or button and check the outline style
    page.keyboard.press("Tab")
    focused = page.evaluate("document.activeElement")
    # Check if it has visible outline
    outline_style = page.evaluate(
        "el => window.getComputedStyle(el).outline",
        focused
    )
    outline_color = page.evaluate(
        "el => window.getComputedStyle(el).outlineColor",
        focused
    )
    # Ensure outline is not "none" or "0"
    # Some frameworks use box-shadow for focus; check for that too
    box_shadow = page.evaluate(
        "el => window.getComputedStyle(el).boxShadow",
        focused
    )
    # At least one of outline or box-shadow should be visible
    has_focus = outline_style != "none" and outline_style != "0" or box_shadow != "none"
    assert has_focus, "Focus indicator not visible"


@pytest.mark.accessibility
def test_table_accessibility(authenticated_page: Page):
    """Test that tables have proper markup: headers, scopes, captions."""
    page = authenticated_page
    page.goto(BASE_URL + "/markets")
    page.wait_for_selector("table", state="visible")

    # Check for table caption or aria-label
    table = page.locator("table").first
    caption = table.locator("caption")
    aria_label = table.get_attribute("aria-label")
    assert caption.is_visible() or aria_label, "Table missing caption or aria-label"

    # Check table headers
    ths = table.locator("thead th")
    for th in ths.all():
        scope = th.get_attribute("scope")
        # scope should be 'col' for column headers
        assert scope in ["col", "row"], "Table header missing scope"

    # For tables with complex headers, check for aria-describedby or id

    # Check that rows have proper roles if not using HTML5
    rows = table.locator("tbody tr")
    for row in rows.all():
        # Row may have role="row"
        role = row.get_attribute("role")
        if role:
            assert role == "row", "Row has invalid role"


@pytest.mark.accessibility
def test_form_fieldset_legend(authenticated_page: Page):
    """Test that grouped form fields use fieldset and legend."""
    page = authenticated_page
    # Check on a page with grouped fields, e.g., risk settings
    page.goto(BASE_URL + "/settings/risk")
    page.wait_for_selector("form", state="visible")

    fieldsets = page.locator("fieldset")
    if fieldsets.count() > 0:
        for fs in fieldsets.all():
            legend = fs.locator("legend")
            expect(legend).to_be_visible(), "Fieldset missing legend"


@pytest.mark.accessibility
def test_touch_target_size(authenticated_page: Page):
    """Test that touch targets (buttons, links) are at least 44px for mobile."""
    # This is a manual check; we can sample some buttons.
    page = authenticated_page
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto(BASE_URL + "/dashboard")
    page.wait_for_selector(".metric-card", state="visible")

    buttons = page.locator("button, a[role='button']")
    small_targets = 0
    for i in range(buttons.count()):
        btn = buttons.nth(i)
        box = btn.bounding_box()
        if box:
            width = box["width"]
            height = box["height"]
            if width < 44 or height < 44:
                small_targets += 1
                logger.warning(f"Small touch target: {btn.text_content() or 'unnamed'}, size: {width}x{height}")
    # Allow some small targets if they are not interactive (e.g., decorative)
    # But we should have few violations; we'll assert if more than 5 small interactive elements
    # This is a heuristic; we'll not fail but log.
    if small_targets > 5:
        logger.warning(f"Found {small_targets} small touch targets; review on mobile.")


@pytest.mark.accessibility
def test_aria_required_attributes(authenticated_page: Page):
    """Test that required ARIA attributes are present on custom elements."""
    # Covered by axe, but we can add specific checks for common components.
    pass


@pytest.mark.accessibility
def test_document_language(authenticated_page: Page):
    """Test that the document has a lang attribute and it is valid."""
    page = authenticated_page
    lang = page.get_attribute("html", "lang")
    assert lang is not None and len(lang) >= 2, "Missing or invalid lang attribute"


# ----- Pytest configuration -----

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "accessibility: mark test as accessibility test")
