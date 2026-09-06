# tests/brokers/conftest.py
"""
Pytest configuration and shared fixtures for broker tests.

This file provides fixtures for:
- Mock broker clients (Binance, Bybit, Alpaca, etc.)
- Test broker accounts and credentials
- Broker factory and service instances
- Test orders, positions, and market data
- Configuration loading for broker test environment

All fixtures are designed to work with both sync and async tests.
"""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from decimal import Decimal
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Broker module imports (adjust paths as needed)
from backend.brokers.base_broker import BaseBroker
from backend.brokers.broker_factory import BrokerFactory
from backend.brokers.alpaca.alpaca_broker import AlpacaBroker
from backend.brokers.binance.binance_broker import BinanceBroker
from backend.brokers.bybit.bybit_broker import BybitBroker
from backend.brokers.coinbase.coinbase_broker import CoinbaseBroker
from backend.brokers.kraken.kraken_broker import KrakenBroker
from backend.brokers.oanda.oanda_broker import OandaBroker
from backend.brokers.interactive_brokers.interactive_brokers_broker import InteractiveBrokersBroker
from backend.core.config import settings

# Test environment variables
os.environ["BROKER_ENVIRONMENT"] = "test"
os.environ["TEST_BINANCE_API_KEY"] = os.getenv("TEST_BINANCE_API_KEY", "test_binance_key")
os.environ["TEST_BINANCE_API_SECRET"] = os.getenv("TEST_BINANCE_API_SECRET", "test_binance_secret")
os.environ["TEST_BYBIT_API_KEY"] = os.getenv("TEST_BYBIT_API_KEY", "test_bybit_key")
os.environ["TEST_BYBIT_API_SECRET"] = os.getenv("TEST_BYBIT_API_SECRET", "test_bybit_secret")
os.environ["TEST_ALPACA_API_KEY"] = os.getenv("TEST_ALPACA_API_KEY", "test_alpaca_key")
os.environ["TEST_ALPACA_API_SECRET"] = os.getenv("TEST_ALPACA_API_SECRET", "test_alpaca_secret")


# ---------------------------- Mock Broker Clients ----------------------------

class MockBrokerClient:
    """Base mock broker client with common methods."""

    def __init__(self, **kwargs):
        self.api_key = kwargs.get("api_key", "test_key")
        self.api_secret = kwargs.get("api_secret", "test_secret")
        self.base_url = kwargs.get("base_url", "https://test-api.example.com")
        self.connected = True

    def get_account(self):
        return {"id": "test_account", "balance": 10000.0, "currency": "USD"}

    def get_positions(self):
        return []

    def get_orders(self):
        return []

    def place_order(self, symbol, side, order_type, quantity, price=None):
        return {
            "id": "test_order_123",
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
            "price": price,
            "status": "filled",
        }

    def cancel_order(self, order_id):
        return {"status": "cancelled"}

    def get_order_status(self, order_id):
        return {"id": order_id, "status": "filled"}

    def get_market_data(self, symbol, timeframe="1m", limit=100):
        return {"symbol": symbol, "data": []}


@pytest.fixture(scope="function")
def mock_binance_client():
    """Return a mock Binance client."""
    client = MockBrokerClient()
    # Add Binance-specific mock methods
    client.get_exchange_info = MagicMock(return_value={"symbols": [{"symbol": "BTCUSDT", "status": "TRADING"}]})
    client.get_klines = MagicMock(return_value=[])
    return client


@pytest.fixture(scope="function")
def mock_bybit_client():
    """Return a mock Bybit client."""
    client = MockBrokerClient()
    client.get_wallet_balance = MagicMock(return_value={"result": {"balance": 10000.0}})
    return client


@pytest.fixture(scope="function")
def mock_alpaca_client():
    """Return a mock Alpaca client."""
    client = MockBrokerClient()
    client.get_account = MagicMock(return_value={"id": "alpaca_acc", "cash": "10000.0"})
    client.list_positions = MagicMock(return_value=[])
    client.submit_order = MagicMock(return_value={"id": "alpaca_ord_123", "status": "filled"})
    return client


@pytest.fixture(scope="function")
def mock_coinbase_client():
    """Return a mock Coinbase client."""
    client = MockBrokerClient()
    client.get_accounts = MagicMock(return_value=[{"id": "coinbase_acc", "balance": {"amount": "10000.0"}}])
    return client


@pytest.fixture(scope="function")
def mock_oanda_client():
    """Return a mock Oanda client."""
    client = MockBrokerClient()
    client.get_accounts = MagicMock(return_value={"accounts": [{"id": "oanda_acc"}]})
    client.get_prices = MagicMock(return_value={"prices": []})
    return client


@pytest.fixture(scope="function")
def mock_ib_client():
    """Return a mock Interactive Brokers client."""
    client = MockBrokerClient()
    client.reqAccountSummary = MagicMock(return_value={"TotalCashBalance": 10000.0})
    return client


# ---------------------------- Broker Instances (mocked) ----------------------------

@pytest.fixture(scope="function")
def alpaca_broker(mock_alpaca_client):
    """Return an AlpacaBroker instance with mocked client."""
    broker = AlpacaBroker(
        api_key="test_key",
        api_secret="test_secret",
        paper=True,
    )
    # Replace the internal client with mock
    broker.client = mock_alpaca_client
    return broker


@pytest.fixture(scope="function")
def binance_broker(mock_binance_client):
    """Return a BinanceBroker instance with mocked client."""
    broker = BinanceBroker(
        api_key="test_key",
        api_secret="test_secret",
        testnet=True,
    )
    broker.client = mock_binance_client
    return broker


@pytest.fixture(scope="function")
def bybit_broker(mock_bybit_client):
    """Return a BybitBroker instance with mocked client."""
    broker = BybitBroker(
        api_key="test_key",
        api_secret="test_secret",
        testnet=True,
    )
    broker.client = mock_bybit_client
    return broker


@pytest.fixture(scope="function")
def coinbase_broker(mock_coinbase_client):
    """Return a CoinbaseBroker instance with mocked client."""
    broker = CoinbaseBroker(
        api_key="test_key",
        api_secret="test_secret",
        sandbox=True,
    )
    broker.client = mock_coinbase_client
    return broker


@pytest.fixture(scope="function")
def kraken_broker():
    """Return a KrakenBroker instance with mocked client."""
    # Kraken uses a different client; we'll mock the underlying methods.
    broker = KrakenBroker(
        api_key="test_key",
        api_secret="test_secret",
        sandbox=True,
    )
    # Mock the client
    broker.client = MockBrokerClient()
    broker.client.get_balance = MagicMock(return_value={"USD": 10000.0})
    broker.client.get_open_orders = MagicMock(return_value=[])
    broker.client.add_order = MagicMock(return_value={"txid": ["kraken_ord_123"]})
    return broker


@pytest.fixture(scope="function")
def oanda_broker(mock_oanda_client):
    """Return an OandaBroker instance with mocked client."""
    broker = OandaBroker(
        api_key="test_key",
        account_id="test_account",
        practice=True,
    )
    broker.client = mock_oanda_client
    return broker


@pytest.fixture(scope="function")
def interactive_brokers_broker(mock_ib_client):
    """Return an InteractiveBrokersBroker instance with mocked client."""
    broker = InteractiveBrokersBroker(
        host="localhost",
        port=7497,
        client_id=1,
    )
    broker.client = mock_ib_client
    return broker


# ---------------------------- Broker Factory Fixture ----------------------------

@pytest.fixture(scope="function")
def broker_factory():
    """Return a BrokerFactory instance with mocked brokers."""
    factory = BrokerFactory()
    # Register mock broker classes
    factory.register_broker("alpaca", AlpacaBroker)
    factory.register_broker("binance", BinanceBroker)
    factory.register_broker("bybit", BybitBroker)
    factory.register_broker("coinbase", CoinbaseBroker)
    factory.register_broker("kraken", KrakenBroker)
    factory.register_broker("oanda", OandaBroker)
    factory.register_broker("interactive_brokers", InteractiveBrokersBroker)
    return factory


@pytest.fixture(scope="function")
def test_broker_account_data():
    """Return test broker account data for connecting."""
    return {
        "broker_name": "binance",
        "api_key": "test_api_key",
        "api_secret": "test_api_secret",
        "label": "Test Account",
        "testnet": True,
    }


# ---------------------------- Configuration Fixtures ----------------------------

@pytest.fixture(scope="session")
def test_broker_config():
    """Return a test broker configuration."""
    return {
        "alpaca": {
            "paper": True,
            "base_url": "https://paper-api.alpaca.markets",
        },
        "binance": {
            "testnet": True,
            "base_url": "https://testnet.binance.vision",
        },
        "bybit": {
            "testnet": True,
            "base_url": "https://api-testnet.bybit.com",
        },
        "coinbase": {
            "sandbox": True,
            "base_url": "https://api-public.sandbox.pro.coinbase.com",
        },
        "kraken": {
            "sandbox": True,
            "base_url": "https://api.sandbox.kraken.com",
        },
        "oanda": {
            "practice": True,
            "base_url": "https://api-fxpractice.oanda.com",
        },
        "interactive_brokers": {
            "host": "localhost",
            "port": 7497,
            "client_id": 1,
        },
    }


@pytest.fixture(scope="function")
def test_order_data():
    """Return test order data."""
    return {
        "symbol": "BTC-USD",
        "side": "buy",
        "order_type": "limit",
        "quantity": 0.5,
        "price": 50000.0,
        "time_in_force": "GTC",
    }


@pytest.fixture(scope="function")
def test_market_data_request():
    """Return test market data request parameters."""
    return {
        "symbol": "BTC-USD",
        "timeframe": "1h",
        "limit": 100,
    }


# ---------------------------- Shared Test Account Fixture (DB) ----------------------------

# We'll reuse the database fixtures from backend conftest if needed.
# But for broker tests we might not need a full DB; we can use mocks.
# However, we may want to test broker account persistence, so we include DB.

@pytest.fixture(scope="function")
def broker_account_model():
    """Return a mock broker account model for testing."""
    from backend.models.broker_account import BrokerAccount
    account = BrokerAccount(
        id=1,
        user_id=1,
        broker_name="binance",
        account_id="test_acc_123",
        api_key="encrypted_key",
        api_secret_encrypted="encrypted_secret",
        is_active=True,
        label="Test",
    )
    return account


# ---------------------------- Async Fixtures ----------------------------

@pytest_asyncio.fixture(scope="function")
async def async_broker_factory(broker_factory):
    """Provide an async-ready broker factory."""
    yield broker_factory


# ---------------------------- Cleanup Fixtures ----------------------------

@pytest.fixture(autouse=True)
def clean_up_broker_mocks():
    """Automatically clean up any broker mock state after each test."""
    yield
    # No explicit cleanup needed, but we can reset mocks if required.


# ---------------------------- Main Test Configuration ----------------------------

# Override the broker factory dependency for FastAPI
# This can be used in tests to inject mock brokers into the app.
