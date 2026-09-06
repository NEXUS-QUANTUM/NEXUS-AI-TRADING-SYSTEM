"""
tests/performance/__init__.py

NEXUS AI Trading System - Performance Test Suite

This package contains comprehensive performance/benchmark tests for the system.
It includes:

- API latency benchmarks (authentication, portfolio, market data, etc.)
- API throughput benchmarks (requests per second, concurrency)
- Backtesting engine performance (backtest execution, metrics, optimization)
- Cache performance (Redis, MemoryCache)
- Concurrent request performance (scalability, connection pooling)
- Database performance (queries, bulk operations, transactions)
- Market data performance (quotes, historical, order book)
- Order execution performance (placement, cancellation, validation)
- Resource usage (CPU, memory, memory leak detection)
- WebSocket performance (connection, subscription, throughput)

All tests use pytest-benchmark for statistical measurement and regression tracking.

Fixtures and shared configurations are defined in `conftest.py` and
are automatically discovered by pytest.

Copyright © 2026 NEXUS QUANTUM LTD
"""

# Import fixtures and shared utilities from conftest to make them available
# when importing the performance package or running tests with pytest.
from .conftest import *

# Explicitly list test modules for clarity and potential programmatic discovery
__all__ = [
    # Test modules
    "test_api_latency",
    "test_api_throughput",
    "test_backtest_perf",
    "test_cache_perf",
    "test_concurrent_perf",
    "test_database_perf",
    "test_market_data_perf",
    "test_order_execution_perf",
    "test_resource_usage",
    "test_websocket_perf",
]

# Package metadata
__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
__description__ = "Performance and benchmark test suite for NEXUS AI Trading System"

# Package-level logger
import logging
logger = logging.getLogger(__name__)
logger.info(f"Loaded performance test suite version {__version__}")
