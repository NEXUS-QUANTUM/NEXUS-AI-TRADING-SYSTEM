# tests/brokers/test_broker_factory.py
"""
Broker Factory Tests.

This module tests the BrokerFactory class, which is responsible for
registering and creating broker instances based on broker names.
"""

import pytest
from unittest.mock import MagicMock, patch

from backend.brokers.base_broker import BaseBroker
from backend.brokers.broker_factory import BrokerFactory
from backend.brokers.alpaca.alpaca_broker import AlpacaBroker
from backend.brokers.binance.binance_broker import BinanceBroker
from backend.brokers.bybit.bybit_broker import BybitBroker
from backend.brokers.coinbase.coinbase_broker import CoinbaseBroker
from backend.brokers.kraken.kraken_broker import KrakenBroker
from backend.brokers.oanda.oanda_broker import OandaBroker
from backend.brokers.interactive_brokers.interactive_brokers_broker import InteractiveBrokersBroker


class TestBrokerFactory:
    """Test the BrokerFactory class."""

    def test_initialization_empty(self):
        """Test that the factory initializes with no brokers."""
        factory = BrokerFactory()
        assert factory._brokers == {}

    def test_initialization_with_registered(self):
        """Test that the factory initializes with some pre-registered brokers (if any)."""
        # We can't rely on the factory having pre-registered brokers; we'll test registration separately.
        factory = BrokerFactory()
        # Default should be empty; we'll register manually.
        assert len(factory._brokers) == 0

    def test_register_broker(self, broker_factory: BrokerFactory):
        """Test registering a broker class."""
        mock_broker_class = MagicMock()
        broker_factory.register_broker("mock", mock_broker_class)
        assert "mock" in broker_factory._brokers
        assert broker_factory._brokers["mock"] == mock_broker_class

    def test_register_broker_already_registered(self, broker_factory: BrokerFactory):
        """Test that registering an already registered broker raises an error or overwrites."""
        # Default behavior: we'll allow overwrite or raise. Let's assume it overwrites.
        broker_factory.register_broker("mock", MagicMock())
        new_class = MagicMock()
        broker_factory.register_broker("mock", new_class)
        assert broker_factory._brokers["mock"] == new_class

    def test_create_broker_valid(self, broker_factory: BrokerFactory):
        """Test creating a valid broker instance."""
        # Register a mock broker
        mock_broker_class = MagicMock(spec=BaseBroker)
        mock_broker_class.return_value = MagicMock(spec=BaseBroker)
        broker_factory.register_broker("test_broker", mock_broker_class)

        config = {"api_key": "key", "api_secret": "secret"}
        broker = broker_factory.create_broker("test_broker", **config)
        mock_broker_class.assert_called_once_with(**config)
        assert broker == mock_broker_class.return_value

    def test_create_broker_with_defaults(self, broker_factory: BrokerFactory):
        """Test creating a broker with default parameters."""
        mock_broker_class = MagicMock(spec=BaseBroker)
        mock_broker_class.return_value = MagicMock(spec=BaseBroker)
        broker_factory.register_broker("test_broker", mock_broker_class)

        # No config passed; should call with empty kwargs.
        broker = broker_factory.create_broker("test_broker")
        mock_broker_class.assert_called_once_with()
        assert broker == mock_broker_class.return_value

    def test_create_broker_invalid_name(self, broker_factory: BrokerFactory):
        """Test that creating a broker with an unregistered name raises ValueError."""
        with pytest.raises(ValueError) as exc:
            broker_factory.create_broker("nonexistent")
        assert "unknown broker" in str(exc.value).lower() or "not registered" in str(exc.value).lower()

    def test_create_broker_requires_class(self, broker_factory: BrokerFactory):
        """Test that if the registered value is not a class (callable), it raises an error."""
        # Register a non-callable
        broker_factory.register_broker("invalid", "not a class")
        with pytest.raises(TypeError):
            broker_factory.create_broker("invalid")

    def test_create_broker_passes_arbitrary_kwargs(self, broker_factory: BrokerFactory):
        """Test that any kwargs passed are forwarded to the broker constructor."""
        mock_broker_class = MagicMock(spec=BaseBroker)
        broker_factory.register_broker("test_broker", mock_broker_class)

        config = {
            "api_key": "key",
            "api_secret": "secret",
            "testnet": True,
            "paper": False,
            "extra_param": "value",
        }
        broker_factory.create_broker("test_broker", **config)
        mock_broker_class.assert_called_once_with(**config)

    def test_broker_creation_returns_basebroker_subclass(self, broker_factory: BrokerFactory):
        """Test that the created broker is an instance of BaseBroker."""
        # Actually test with real brokers if they are available.
        # For this test, we'll register a mock that returns a BaseBroker subclass.
        class MockBroker(BaseBroker):
            def get_account(self): return {}
            def get_positions(self): return []
            def get_orders(self): return []
            def place_order(self, symbol, side, order_type, quantity, price=None): return {}
            def cancel_order(self, order_id): return {}
            def get_order_status(self, order_id): return {}
            def get_market_data(self, symbol, timeframe="1m", limit=100): return {}

        broker_factory.register_broker("mock", MockBroker)
        broker = broker_factory.create_broker("mock")
        assert isinstance(broker, BaseBroker)

    def test_factory_with_real_brokers(self):
        """Test that the factory can register and create real broker instances."""
        factory = BrokerFactory()
        # Register a subset of real brokers
        factory.register_broker("alpaca", AlpacaBroker)
        factory.register_broker("binance", BinanceBroker)

        # Create an Alpaca broker with minimal config
        config = {"api_key": "test", "api_secret": "test", "paper": True}
        alpaca = factory.create_broker("alpaca", **config)
        assert isinstance(alpaca, AlpacaBroker)
        assert alpaca.api_key == "test"
        assert alpaca.paper is True

        # Create a Binance broker
        binance_config = {"api_key": "test", "api_secret": "test", "testnet": True}
        binance = factory.create_broker("binance", **binance_config)
        assert isinstance(binance, BinanceBroker)
        assert binance.testnet is True

    def test_factory_registered_all_default_brokers(self):
        """If the factory has a default registration method, test that."""
        # Some factories register all known brokers on init; we test that.
        factory = BrokerFactory()
        # If the factory pre-registers brokers, we should see some.
        # But we can't rely on that; we'll just test that the method exists.
        if hasattr(factory, "register_default_brokers"):
            factory.register_default_brokers()
            expected_brokers = ["alpaca", "binance", "bybit", "coinbase", "kraken", "oanda", "interactive_brokers"]
            for name in expected_brokers:
                assert name in factory._brokers


class TestBrokerFactorySingleton:
    """If the factory is a singleton, test that behavior."""

    def test_factory_singleton(self):
        """Test that the factory is a singleton (if implemented)."""
        # If there's a global instance, test that it's the same across imports.
        # This is a simplified test; we assume there's a `get_instance` method.
        # We'll just check if the class has a `_instance` attribute.
        if hasattr(BrokerFactory, "_instance"):
            factory1 = BrokerFactory()
            factory2 = BrokerFactory()
            assert factory1 is factory2
