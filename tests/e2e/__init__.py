"""
NEXUS AI Trading System - End-to-End Test Suite

This package contains comprehensive end-to-end tests for the NEXUS AI Trading System.
It covers all critical user journeys including:

- Authentication and authorization flows
- Trading operations (market, limit, stop orders)
- Portfolio and position management
- Settings configuration (general, security, brokers, risk, etc.)
- Responsive design across all device sizes
- Cross-browser compatibility (Chromium, Firefox, WebKit)
- Error handling and edge cases
- Performance and load testing

All tests run against a real or mocked backend using Playwright for browser automation.
Fixtures and configuration are defined in conftest.py and are automatically discovered.

Copyright © 2026 NEXUS QUANTUM LTD
"""

# Import fixtures and shared utilities from conftest to make them available
# when importing the e2e package or running tests with pytest.
from .conftest import *  # noqa: F401, F403

# Explicitly list test modules for clarity and potential programmatic discovery
__all__ = [
    "test_auth_flow",
    "test_cross_browser",
    "test_error_scenarios",
    "test_market_data_flow",
    "test_performance_e2e",
    "test_portfolio_flow",
    "test_responsive",
    "test_settings_flow",
    "test_trading_flow",
]

# Package metadata
__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
__description__ = "End-to-end test suite for NEXUS AI Trading System"
