"""
tests/load/__init__.py

NEXUS AI Trading System - Load Test Suite

This package contains comprehensive load and performance tests for the system.
It includes:

- Baseline performance tests (benchmarking)
- Data-intensive endpoint tests (large datasets)
- Endurance/stability tests (long-running)
- Mixed workload tests (different user profiles)
- Ramp load tests (gradual increase/decrease)
- Recovery tests (failure and recovery scenarios)
- Scalability tests (horizontal scaling)
- Spike load tests (sudden traffic increases)
- Stress tests (extreme conditions)

All tests can be run via pytest or Locust, with configurable parameters
via environment variables.

Fixtures and shared configurations are defined in `conftest.py` and
are automatically discovered by pytest.

Copyright © 2026 NEXUS QUANTUM LTD
"""

# Import fixtures and shared utilities from conftest to make them available
# when importing the load package or running tests with pytest.
from .conftest import *

# Explicitly list test modules for clarity and potential programmatic discovery
__all__ = [
    # Test modules
    "test_load_baseline",
    "test_load_data",
    "test_load_endurance",
    "test_load_mixed",
    "test_load_ramp",
    "test_load_recovery",
    "test_load_scalability",
    "test_load_spike",
    "test_load_stress",
]

# Package metadata
__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
__description__ = "Load and performance test suite for NEXUS AI Trading System"

# Package-level logger
import logging
logger = logging.getLogger(__name__)
logger.info(f"Loaded load test suite version {__version__}")
