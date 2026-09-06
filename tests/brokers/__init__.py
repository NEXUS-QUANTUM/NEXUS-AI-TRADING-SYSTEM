# tests/brokers/__init__.py
"""
Broker Module Tests for the NEXUS AI Trading System.

This package contains all unit and integration tests for the broker
services, including broker implementations (Alpaca, Binance, Bybit, Coinbase, Kraken),
broker factory, broker manager, and integration tests.

All tests adhere to the NEXUS development standards and use shared fixtures
from conftest.py.
"""

# Import test modules to make them available as submodules
from . import conftest
from . import test_all_brokers
from . import test_alpaca_broker
from . import test_base_broker
from . import test_binance_broker
from . import test_broker_factory
from . import test_broker_integration
from . import test_broker_manager
from . import test_bybit_broker
from . import test_coinbase_broker
from . import test_kraken_broker

# Expose test modules for easy import
__all__ = [
    "conftest",
    "test_all_brokers",
    "test_alpaca_broker",
    "test_base_broker",
    "test_binance_broker",
    "test_broker_factory",
    "test_broker_integration",
    "test_broker_manager",
    "test_bybit_broker",
    "test_coinbase_broker",
    "test_kraken_broker",
]

# Optional: package metadata
__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
