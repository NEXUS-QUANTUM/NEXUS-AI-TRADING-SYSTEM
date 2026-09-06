"""
tests/frontend/__init__.py

NEXUS AI Trading System - Frontend Test Suite

This package contains comprehensive end-to-end and integration tests for the
frontend application of the NEXUS AI Trading System.

It includes:
- Component tests (individual UI components)
- Form tests (validation, submission)
- Page tests (load, navigation)
- Routing tests (URLs, redirects, protected routes)
- State management tests (Zustand stores via UI interactions)
- Visual regression tests (screenshot comparison)
- Accessibility tests (WCAG 2.1 AA compliance)
- API integration tests (network requests, responses)
- WebSocket client tests (connection, messages, reconnection)

All tests are executed against a real browser instance using Playwright,
against a live frontend server (configurable via environment variables).

Fixtures and shared configurations are defined in `conftest.py` and
are automatically discovered by pytest.

Copyright © 2026 NEXUS QUANTUM LTD
"""

# Import fixtures and shared utilities from conftest to make them available
# when importing the frontend package or running tests with pytest.
from .conftest import *

# Explicitly list test modules for clarity and potential programmatic discovery
__all__ = [
    # Test modules
    "test_components",
    "test_forms",
    "test_pages",
    "test_routing",
    "test_state_management",
    "test_visual_regression",
    "test_accessibility",
    "test_api_integration",
    "test_websocket_client",
]

# Package metadata
__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
__description__ = "Frontend test suite for NEXUS AI Trading System"

# Package-level logger
import logging
logger = logging.getLogger(__name__)
logger.info(f"Loaded frontend test suite version {__version__}")
