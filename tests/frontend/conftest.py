"""
tests/frontend/conftest.py

NEXUS AI Trading System - Frontend Test Configuration

This module provides shared fixtures and configuration for all frontend tests.
It leverages Playwright's built-in fixtures and adds custom ones for:
- Authentication (logging in via UI)
- Test data setup and teardown
- Screenshot capture on test failure
- Global configuration via environment variables

All fixtures are scoped appropriately for test isolation and performance.

Copyright © 2026 NEXUS QUANTUM LTD
"""

import os
import logging
import pytest
import re
from typing import Dict, Any, Optional, Generator, Callable
from playwright.sync_api import Page, BrowserContext, Browser, Playwright, expect
from _pytest.fixtures import FixtureRequest
from _pytest.nodes import Item
from _pytest.reports import TestReport

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables with defaults
BASE_URL = os.getenv("NEXUS_FRONTEND_URL", "http://localhost:3000")
API_URL = os.getenv("NEXUS_API_URL", "http://localhost:8000")
HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "1") == "1"
SLOW_MO = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))
TEST_USER = {
    "email": os.getenv("TEST_USER_EMAIL", "test@nexusquantum.com"),
    "password": os.getenv("TEST_USER_PASSWORD", "Test@123"),
}

# Screenshot directory
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


# ----- Pytest configuration hooks -----

def pytest_configure(config):
    """Register custom markers and set up global config."""
    config.addinivalue_line("markers", "visual: mark test as visual regression test")
    config.addinivalue_line("markers", "accessibility: mark test as accessibility test")
    config.addinivalue_line("markers", "slow: mark test as slow (long-running)")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "smoke: mark test as smoke test")

    # Store base URL in config for use in fixtures
    config._base_url = BASE_URL
    config._api_url = API_URL
    config._test_user = TEST_USER


def pytest_addoption(parser):
    """Add command-line options for test execution."""
    parser.addoption(
        "--update-baseline",
        action="store_true",
        default=False,
        help="Update baseline screenshots for visual regression tests",
    )
    parser.addoption(
        "--headless",
        action="store_true",
        default=HEADLESS,
        help="Run tests in headless mode",
    )
    parser.addoption(
        "--slow-mo",
        type=int,
        default=SLOW_MO,
        help="Slow down Playwright operations by given milliseconds",
    )


def pytest_collection_modifyitems(config, items):
    """Apply markers based on test file names or paths."""
    # Example: add 'integration' marker to tests in 'tests/frontend/integration/'
    for item in items:
        if "integration" in item.fspath.strpath:
            item.add_marker(pytest.mark.integration)
        if "smoke" in item.fspath.strpath or "test_auth_flow" in item.fspath.strpath:
            item.add_marker(pytest.mark.smoke)


# ----- Fixtures -----

@pytest.fixture(scope="session")
def playwright_instance() -> Generator[Playwright, None, None]:
    """Session-scoped Playwright instance."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser_type(playwright_instance: Playwright, request) -> str:
    """Determine browser type from command line or environment."""
    browser_name = os.getenv("PLAYWRIGHT_BROWSER", "chromium")
    return browser_name


@pytest.fixture(scope="session")
def browser_context_args(browser_type: str, request) -> Dict[str, Any]:
    """Common browser context arguments for all tests."""
    args = {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
        "locale": "en-US",
        "timezone_id": "America/New_York",
        "permissions": ["notifications"],
    }
    # Add slow_mo if set
    slow_mo = request.config.getoption("--slow-mo")
    if slow_mo:
        args["slow_mo"] = slow_mo
    # Headless mode from config
    headless = request.config.getoption("--headless")
    args["headless"] = headless
    return args


@pytest.fixture(scope="function")
def page_context(browser: Browser, browser_context_args: Dict[str, Any]) -> Generator[Page, None, None]:
    """
    Create a new page with a clean context for each test.
    This is the primary fixture for frontend tests.
    """
    context = browser.new_context(**browser_context_args)
    page = context.new_page()
    page.set_default_timeout(30000)  # 30 seconds
    yield page
    # Clean up
    context.close()


@pytest.fixture(scope="function")
def authenticated_page(page_context: Page) -> Page:
    """
    Return an authenticated page (logged in as test user).
    This fixture performs login via the UI and waits for the dashboard to load.
    """
    page = page_context
    logger.info(f"Logging in as {TEST_USER['email']}...")
    page.goto(BASE_URL + "/authentication/login")
    page.fill("input[name='email']", TEST_USER["email"])
    page.fill("input[name='password']", TEST_USER["password"])
    page.click("button[type='submit']")
    # Wait for redirect to dashboard
    page.wait_for_url(re.compile(r"/dashboard"), timeout=10000)
    expect(page).to_have_url(re.compile(r"/dashboard"))
    # Ensure the page is fully loaded
    page.wait_for_selector("main", state="visible")
    logger.info("Login successful.")
    return page


@pytest.fixture(scope="function")
def api_client(request) -> Callable:
    """
    Return a function that makes direct API calls to the backend.
    Useful for test setup (e.g., creating test data) and teardown.
    Requires requests library; if not available, we use Playwright's APIRequestContext.
    """
    # Use Playwright's APIRequestContext for making API calls
    from playwright.sync_api import APIRequestContext
    # The API client is bound to the page context; we can use the browser's request context.
    # We'll create a fixture that returns a request context.

    # However, we need to create a context that is shared. For simplicity, we'll create a new one per test.
    # We'll implement a simple wrapper using requests if available, else use Playwright.
    try:
        import requests
        session = requests.Session()
        # We could login and get token first, but we'll keep it simple.
        def api_request(method: str, path: str, **kwargs):
            url = f"{API_URL}{path}"
            # Add authorization header if token is available
            # For simplicity, we assume the test user is already authenticated or we don't need auth.
            # In many tests, we will just use the UI for actions, but this fixture can be used for setup.
            response = session.request(method, url, **kwargs)
            return response
        return api_request
    except ImportError:
        # Fallback: use Playwright's APIRequestContext via a new context
        # We'll create a new API context per test (may be slow, but okay for tests)
        @pytest.fixture(scope="function")
        def api_client(browser: Browser) -> Generator:
            from playwright.sync_api import APIRequestContext
            api_context = browser.context.request.new_context(base_url=API_URL)
            yield api_context
            api_context.dispose()
        return api_client


@pytest.fixture(scope="function")
def take_screenshot(request: FixtureRequest):
    """
    Fixture that returns a function to take screenshots during tests.
    Also automatically captures a screenshot on test failure.
    """
    def _take_screenshot(page: Page, name: str):
        path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
        page.screenshot(path=path, full_page=True)
        logger.info(f"Screenshot saved to {path}")
        return path

    # Store the function for use in test
    return _take_screenshot


@pytest.fixture(autouse=True)
def capture_screenshot_on_failure(request: FixtureRequest, page_context: Page):
    """Automatically capture a screenshot when a test fails."""
    yield
    if request.node.rep_call and request.node.rep_call.failed:
        test_name = request.node.name
        logger.info(f"Test {test_name} failed, capturing screenshot...")
        path = os.path.join(SCREENSHOT_DIR, f"{test_name}_failure.png")
        page_context.screenshot(path=path, full_page=True)
        logger.info(f"Screenshot saved to {path}")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: Item, call):
    """Hook to capture test result for the autouse fixture."""
    outcome = yield
    rep = outcome.get_result()
    # Store the result in the item for later use in the fixture
    setattr(item, "rep_" + rep.when, rep)


# ----- Helper functions for tests -----

def get_store_state(page: Page, store_name: str) -> Dict[str, Any]:
    """
    Retrieve the state of a specific Zustand store from the browser.
    Assumes the store is exposed as window.__NEXUS_STORE__.
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


def wait_for_api(page: Page, pattern: str, timeout: int = 5000):
    """
    Wait for an API request/response matching a pattern.
    Returns the response object.
    """
    return page.wait_for_response(lambda r: re.search(pattern, r.url) is not None, timeout=timeout)


def wait_for_websocket(page: Page, timeout: int = 10000):
    """
    Wait for a WebSocket connection to be established.
    Returns the WebSocket object.
    """
    return page.wait_for_event("websocket", timeout=timeout)


# ----- Fixture for test data setup/teardown -----

@pytest.fixture(scope="function")
def test_data_cleanup(authenticated_page: Page):
    """
    Fixture that sets up test data and cleans up after the test.
    Can be used to create positions, orders, etc. for testing.
    """
    # Setup: maybe we need to place a position or order for testing
    # This is a placeholder; actual implementation depends on the app.
    yield
    # Teardown: close any open positions, cancel orders, etc.
    # We can use the authenticated page or API to do this.
    # For simplicity, we'll just log a message.
    logger.info("Cleaning up test data (placeholder).")
