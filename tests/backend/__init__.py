# tests/backend/__init__.py
"""
Backend Module Tests for the NEXUS AI Trading System.

This package contains all unit and integration tests for the backend services,
including API endpoints, authentication, database models, middleware, services,
tasks, validators, and WebSocket functionality.

All tests adhere to the NEXUS development standards and use shared fixtures
from conftest.py.
"""

# Import test modules to make them available as submodules
from . import conftest
from . import test_api
from . import test_auth
from . import test_database
from . import test_exceptions
from . import test_middleware
from . import test_services
from . import test_tasks
from . import test_validators
from . import test_websocket

# Expose test modules for easy import
__all__ = [
    "conftest",
    "test_api",
    "test_auth",
    "test_database",
    "test_exceptions",
    "test_middleware",
    "test_services",
    "test_tasks",
    "test_validators",
    "test_websocket",
]

# Optional: package metadata
__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
