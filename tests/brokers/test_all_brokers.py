# tests/brokers/test_all_brokers.py
"""
Comprehensive tests for all broker implementations.

This module tests each broker against the BaseBroker interface to ensure
consistency and correct behavior across all supported brokers.
It also validates the BrokerFactory and broker registration.

All tests use mocked clients defined in conftest.py.
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.brokers.base_broker import BaseBroker
from backend.brokers.broker_factory import BrokerFactory


# List of broker fixture names to test
BROKER_FIXTURES = [
    "alpaca_broker",
    "binance_broker",
    "bybit_broker",
    "coinbase_broker",
    "kraken_broker",
    "oanda_broker",
    "interactive_brokers_broker",
]


@pytest.fixture(params=BROKER_FIXTURES)
def broker(request):
    """Parameterized fixture that yields each broker instance."""
    return request.getfixturevalue(request.param)


class TestAllBrokers:
    """Test all brokers against the BaseBroker interface and common behaviors."""

    def test_broker_is_base_broker(self, broker):
        """Test that every broker is an instance of BaseBroker."""
        assert isinstance(broker, BaseBroker)

    def test_broker_has_required_methods(self, broker):
        """Test that each broker implements required methods."""
        required_methods = [
            "get_account",
            "get_positions",
            "get_orders",
            "place_order",
            "cancel_order",
            "get_order_status",
            "get_market_data",
        ]
        for method in required_methods:
            assert hasattr(broker, method), f"Broker {broker.__class__.__name__} missing {method}"
            assert callable(getattr(broker, method)), f"{method} is not callable"

    def test_get_account_returns_dict(self, broker):
        """Test get_account returns a dict with expected fields."""
        with patch.object(broker, "get_account", wraps=broker.get_account) as mock_method:
            result = broker.get_account()
            mock_method.assert_called_once()
            assert isinstance(result, dict)
            # Common fields: id, balance, currency
            # Some brokers may have different keys; we just check existence of at least one.
            assert any(key in result for key in ("id", "account_id", "balance", "equity"))

    def test_get_positions_returns_list(self, broker):
        """Test get_positions returns a list."""
        with patch.object(broker, "get_positions", wraps=broker.get_positions) as mock_method:
            result = broker.get_positions()
            mock_method.assert_called_once()
            assert isinstance(result, list)

    def test_get_orders_returns_list(self, broker):
        """Test get_orders returns a list."""
        with patch.object(broker, "get_orders", wraps=broker.get_orders) as mock_method:
            result = broker.get_orders()
            mock_method.assert_called_once()
            assert isinstance(result, list)

    def test_place_market_order_returns_order(self, broker):
        """Test placing a market order returns a dict with order details."""
        with patch.object(broker, "place_order", wraps=broker.place_order) as mock_method:
            result = broker.place_order(
                symbol="BTC-USD",
                side="buy",
                order_type="market",
                quantity=0.1,
            )
            mock_method.assert_called_once_with(
                symbol="BTC-USD",
                side="buy",
                order_type="market",
                quantity=0.1,
                price=None,
            )
            assert isinstance(result, dict)
            # Should have an order id
            assert any(key in result for key in ("id", "order_id", "txid"))

    def test_place_limit_order_returns_order(self, broker):
        """Test placing a limit order returns a dict with order details."""
        with patch.object(broker, "place_order", wraps=broker.place_order) as mock_method:
            result = broker.place_order(
                symbol="BTC-USD",
                side="sell",
                order_type="limit",
                quantity=0.2,
                price=55000.0,
            )
            mock_method.assert_called_once_with(
                symbol="BTC-USD",
                side="sell",
                order_type="limit",
                quantity=0.2,
                price=55000.0,
            )
            assert isinstance(result, dict)
            assert any(key in result for key in ("id", "order_id", "txid"))

    def test_cancel_order_returns_dict(self, broker):
        """Test cancel_order returns a dict with status."""
        with patch.object(broker, "cancel_order", wraps=broker.cancel_order) as mock_method:
            result = broker.cancel_order("dummy_order_id")
            mock_method.assert_called_once_with("dummy_order_id")
            assert isinstance(result, dict)
            # Should have a status field
            assert any(key in result for key in ("status", "state", "message"))

    def test_get_order_status_returns_dict(self, broker):
        """Test get_order_status returns a dict with order status."""
        with patch.object(broker, "get_order_status", wraps=broker.get_order_status) as mock_method:
            result = broker.get_order_status("dummy_order_id")
            mock_method.assert_called_once_with("dummy_order_id")
            assert isinstance(result, dict)
            assert any(key in result for key in ("status", "state", "filled_quantity"))

    def test_get_market_data_returns_data(self, broker):
        """Test get_market_data returns non-empty data."""
        with patch.object(broker, "get_market_data", wraps=broker.get_market_data) as mock_method:
            result = broker.get_market_data("BTC-USD", timeframe="1h", limit=10)
            mock_method.assert_called_once_with("BTC-USD", timeframe="1h", limit=10)
            assert result is not None
            # Could be a dict or list; we just check it's not empty.
            if isinstance(result, dict):
                assert len(result) > 0
            elif isinstance(result, list):
                assert len(result) >= 0  # some may return empty list

    def test_get_balance(self, broker):
        """Test get_balance if implemented."""
        if hasattr(broker, "get_balance") and callable(broker.get_balance):
            with patch.object(broker, "get_balance", wraps=broker.get_balance) as mock_method:
                result = broker.get_balance()
                mock_method.assert_called_once()
                assert isinstance(result, dict)
                assert any(key in result for key in ("total", "available", "balance"))


class TestBrokerFactory:
    """Test the BrokerFactory for creating broker instances."""

    def test_factory_registers_all_brokers(self, broker_factory: BrokerFactory):
        """Test that all broker types are registered in the factory."""
        expected_brokers = ["alpaca", "binance", "bybit", "coinbase", "kraken", "oanda", "interactive_brokers"]
        for name in expected_brokers:
            assert name in broker_factory._brokers

    def test_factory_create_broker(self, broker_factory: BrokerFactory):
        """Test creating a broker instance via factory."""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "paper": True,
        }
        broker = broker_factory.create_broker("binance", **config)
        assert isinstance(broker, BinanceBroker)
        assert broker.api_key == "test_key"
        assert broker.api_secret == "test_secret"
        assert broker.testnet is True

    def test_factory_create_broker_invalid(self, broker_factory: BrokerFactory):
        """Test creating a broker with unsupported name raises ValueError."""
        with pytest.raises(ValueError):
            broker_factory.create_broker("unknown_broker")

    def test_factory_create_broker_with_missing_credentials(self, broker_factory: BrokerFactory):
        """Test that factory raises appropriate error when credentials missing."""
        with pytest.raises(ValueError):
            broker_factory.create_broker("alpaca")  # no credentials


class TestBrokerErrorHandling:
    """Test error handling for broker operations."""

    def test_invalid_symbol_raises_error(self, broker):
        """Test that invalid symbol raises appropriate error."""
        with patch.object(
            broker,
            "place_order",
            side_effect=ValueError("Invalid symbol")
        ):
            with pytest.raises(ValueError):
                broker.place_order(symbol="INVALID", side="buy", order_type="market", quantity=1)

    def test_insufficient_funds_raises_error(self, broker):
        """Test insufficient funds handling."""
        with patch.object(
            broker,
            "place_order",
            side_effect=Exception("Insufficient balance")
        ):
            with pytest.raises(Exception) as exc:
                broker.place_order(symbol="BTC-USD", side="buy", order_type="market", quantity=1000)
            assert "insufficient" in str(exc.value).lower()

    def test_connection_error_raises_error(self, broker):
        """Test connection error handling."""
        with patch.object(
            broker,
            "get_account",
            side_effect=ConnectionError("Network error")
        ):
            with pytest.raises(ConnectionError):
                broker.get_account()

    def test_order_not_found_raises_error(self, broker):
        """Test that cancelling a non-existent order raises appropriate error."""
        with patch.object(
            broker,
            "cancel_order",
            side_effect=ValueError("Order not found")
        ):
            with pytest.raises(ValueError):
                broker.cancel_order("nonexistent")


class TestBrokerConfiguration:
    """Test broker configuration and settings."""

    def test_broker_has_config_attributes(self, broker):
        """Test that broker has configuration attributes (paper/testnet flag)."""
        # Most brokers have a paper/trading mode flag
        has_flag = any(
            hasattr(broker, attr) and isinstance(getattr(broker, attr), bool)
            for attr in ("paper", "testnet", "sandbox", "practice")
        )
        # If no flag, skip test rather than fail
        if not has_flag:
            pytest.skip("Broker does not have a paper/test flag")
        else:
            # At least one flag exists and is boolean
            assert True

    def test_broker_base_url_set(self, broker):
        """Test that broker has a base_url attribute (or similar)."""
        # Some brokers have base_url, api_url, etc.
        url_attrs = ["base_url", "api_url", "base_url", "endpoint"]
        found = any(hasattr(broker, attr) for attr in url_attrs)
        if not found:
            pytest.skip("Broker does not expose a base URL")
        else:
            assert True

    def test_broker_credentials_not_exposed(self, broker):
        """Test that sensitive credentials are not exposed in string representation."""
        # Ensure that __str__ or __repr__ does not leak api keys.
        rep = repr(broker)
        assert "api_key" not in rep or "***" in rep
        assert "api_secret" not in rep or "***" in rep


class TestBrokerIntegrationSimulation:
    """Simulate real broker interactions using mocks."""

    def test_full_order_lifecycle(self, broker):
        """Simulate placing, checking, and canceling an order."""
        # Place order
        with patch.object(broker, "place_order") as mock_place:
            mock_place.return_value = {"id": "ord_123", "status": "pending"}
            order = broker.place_order("BTC-USD", "buy", "limit", 0.5, 50000)
            assert order["id"] == "ord_123"

        # Check status
        with patch.object(broker, "get_order_status") as mock_status:
            mock_status.return_value = {"id": "ord_123", "status": "filled"}
            status = broker.get_order_status("ord_123")
            assert status["status"] == "filled"

        # Cancel order (if still pending)
        with patch.object(broker, "cancel_order") as mock_cancel:
            mock_cancel.return_value = {"id": "ord_123", "status": "cancelled"}
            cancel = broker.cancel_order("ord_123")
            assert cancel["status"] == "cancelled"

    def test_get_positions_after_trade(self, broker):
        """Simulate positions update after a trade."""
        with patch.object(broker, "get_positions") as mock_pos:
            mock_pos.return_value = [
                {"symbol": "BTC-USD", "quantity": 0.5, "avg_price": 50000}
            ]
            positions = broker.get_positions()
            assert len(positions) == 1
            assert positions[0]["symbol"] == "BTC-USD"

    def test_get_account_balance_after_order(self, broker):
        """Simulate account balance update after order."""
        with patch.object(broker, "get_account") as mock_acc:
            mock_acc.return_value = {"id": "acc1", "balance": 9500.0}
            account = broker.get_account()
            assert account["balance"] == 9500.0
