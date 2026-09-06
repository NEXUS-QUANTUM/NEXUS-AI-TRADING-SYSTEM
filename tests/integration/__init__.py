"""
tests/integration/__init__.py

NEXUS AI Trading System - Integration Test Suite

This package contains comprehensive integration tests for the backend
API, database, external services, and all core functionality.

It includes:
- AI/ML integration (predictions, models, training)
- API endpoint integration (authentication, trading, portfolio, etc.)
- Broker integration (Alpaca, Binance)
- Cache integration (Redis)
- Database integration (models, relationships, constraints)
- End-to-end user journeys
- External services (market data, sentiment, payment, email, storage, webhooks)
- Portfolio management (summary, positions, performance, rebalancing)
- Risk management (limits, stop-loss, drawdown, circuit breaker)
- WebSocket integration (real-time updates)

Fixtures and shared configurations are defined in `conftest.py` and
are automatically discovered by pytest.

Copyright © 2026 NEXUS QUANTUM LTD
"""

# Import fixtures and shared utilities from conftest to make them available
# when importing the integration package or running tests with pytest.
from .conftest import *

# Explicitly list test modules for clarity and potential programmatic discovery
__all__ = [
    # Test modules
    "test_ai_integration",
    "test_api_integration",
    "test_broker_integration",
    "test_cache_integration",
    "test_database_integration",
    "test_end_to_end",
    "test_external_services",
    "test_portfolio_integration",
    "test_risk_integration",
    "test_websocket_integration",
]

# Package metadata
__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
__description__ = "Integration test suite for NEXUS AI Trading System"

# Package-level logger
import logging
logger = logging.getLogger(__name__)
logger.info(f"Loaded integration test suite version {__version__}")
