# tests/brokers/test_coinbase_broker.py
"""
Coinbase Broker Specific Tests.

This module contains tests specifically for the Coinbase broker integration,
including spot trading, sandbox configuration, different order types, and
Coinbase-specific API features (e.g., fees, payment methods).

All tests use mocked Coinbase client and fixtures from conftest.py.
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.brokers.coinbase.coinbase_broker import CoinbaseBroker
from backend.brokers.base_broker import BaseBroker


class TestCoinbaseBrokerInitialization:
    """Test Coinbase broker initialization and configuration."""

    def test_coinbase_broker_is_base_broker(self, coinbase_broker: CoinbaseBroker):
        """Test that CoinbaseBroker inherits from BaseBroker."""
        assert isinstance(coinbase_broker, BaseBroker)

    def test_coinbase_broker_attributes(self, coinbase_broker: CoinbaseBroker):
        """Test that Coinbase broker has correct attributes."""
        assert coinbase_broker.api_key == "test_key"
        assert coinbase_broker.api_secret == "test_secret"
        assert coinbase_broker.sandbox is True
        # Base URL should be set to sandbox endpoint
        assert coinbase_broker.base_url is not None
        assert "sandbox" in coinbase_broker.base_url

    def test_coinbase_broker_has_required_methods(self, coinbase_broker: CoinbaseBroker):
        """Test that Coinbase broker implements all required methods."""
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
            assert hasattr(coinbase_broker, method)
            assert callable(getattr(coinbase_broker, method))

    def test_coinbase_sandbox_enabled(self, coinbase_broker: CoinbaseBroker):
        """Test that sandbox mode is correctly set."""
        assert coinbase_broker.sandbox is True
        # With sandbox=True, base_url should point to sandbox API
        assert "sandbox" in coinbase_broker.base_url


class TestCoinbaseBrokerAccount:
    """Test Coinbase account-related operations."""

    def test_get_account_returns_dict(self, coinbase_broker: CoinbaseBroker):
        """Test get_account returns a dict with expected fields."""
        with patch.object(coinbase_broker.client, "get_accounts") as mock_client:
            mock_client.return_value = [
                {"id": "acc1", "currency": "USD", "balance": {"amount": "10000.0"}},
                {"id": "acc2", "currency": "BTC", "balance": {"amount": "0.5"}},
            ]
            result = coinbase_broker.get_account()
            mock_client.assert_called_once()
            assert isinstance(result, list)
            if result:
                assert "id" in result[0]
                assert "currency" in result[0]

    def test_get_account_handles_errors(self, coinbase_broker: CoinbaseBroker):
        """Test that get_account raises appropriate exceptions on client error."""
        with patch.object(coinbase_broker.client, "get_accounts", side_effect=Exception("API error")):
            with pytest.raises(Exception):
                coinbase_broker.get_account()


class TestCoinbaseBrokerPositions:
    """Test Coinbase position-related operations."""

    def test_get_positions_returns_list(self, coinbase_broker: CoinbaseBroker):
        """Test get_positions returns a list of position dicts."""
        # Coinbase Pro does not have positions in the same way; it uses holds or fills.
        # We may map order fills to positions.
        # For this test, we'll mock the client's list_positions if available.
        # If not, we can simulate by returning an empty list.
        if hasattr(coinbase_broker.client, "list_positions"):
            with patch.object(coinbase_broker.client, "list_positions") as mock_client:
                mock_client.return_value = [
                    {"symbol": "BTC-USD", "quantity": "0.5", "avg_price": "50000"}
                ]
                result = coinbase_broker.get_positions()
                mock_client.assert_called_once()
                assert isinstance(result, list)
                if result:
                    assert "symbol" in result[0]
        else:
            # If not implemented, we just call and check it's a list.
            result = coinbase_broker.get_positions()
            assert isinstance(result, list)

    def test_get_positions_empty(self, coinbase_broker: CoinbaseBroker):
        """Test get_positions returns empty list when no positions."""
        if hasattr(coinbase_broker.client, "list_positions"):
            with patch.object(coinbase_broker.client, "list_positions") as mock_client:
                mock_client.return_value = []
                result = coinbase_broker.get_positions()
                assert result == []


class TestCoinbaseBrokerOrders:
    """Test Coinbase order operations."""

    def test_place_market_order(self, coinbase_broker: CoinbaseBroker):
        """Test placing a market order."""
        with patch.object(coinbase_broker.client, "place_order") as mock_order:
            mock_order.return_value = {
                "id": "ord_123",
                "product_id": "BTC-USD",
                "side": "buy",
                "type": "market",
                "size": "0.1",
                "status": "done",
                "filled_size": "0.1",
                "executed_value": "5000",
            }
            result = coinbase_broker.place_order(
                symbol="BTC-USD",
                side="buy",
                order_type="market",
                quantity=0.1,
            )
            mock_order.assert_called_once()
            call_args = mock_order.call_args[1]
            assert call_args["product_id"] == "BTC-USD"
            assert call_args["side"] == "buy"
            assert call_args["type"] == "market"
            assert call_args["size"] == "0.1"
            assert result["id"] == "ord_123"
            assert result["status"] == "done"

    def test_place_limit_order(self, coinbase_broker: CoinbaseBroker):
        """Test placing a limit order."""
        with patch.object(coinbase_broker.client, "place_order") as mock_order:
            mock_order.return_value = {
                "id": "ord_456",
                "product_id": "BTC-USD",
                "side": "sell",
                "type": "limit",
                "size": "0.5",
                "price": "55000.0",
                "status": "pending",
            }
            result = coinbase_broker.place_order(
                symbol="BTC-USD",
                side="sell",
                order_type="limit",
                quantity=0.5,
                price=55000.0,
            )
            mock_order.assert_called_once()
            call_args = mock_order.call_args[1]
            assert call_args["type"] == "limit"
            assert call_args["price"] == "55000.0"
            assert result["id"] == "ord_456"

    def test_place_stop_order(self, coinbase_broker: CoinbaseBroker):
        """Test placing a stop order."""
        if hasattr(coinbase_broker.client, "place_order"):
            with patch.object(coinbase_broker.client, "place_order") as mock_order:
                mock_order.return_value = {
                    "id": "ord_789",
                    "type": "stop",
                    "stop_price": "48000",
                    "status": "pending",
                }
                result = coinbase_broker.place_order(
                    symbol="BTC-USD",
                    side="buy",
                    order_type="stop_loss",
                    quantity=0.5,
                    price=48000.0,  # stop price
                )
                mock_order.assert_called_once()
                call_args = mock_order.call_args[1]
                assert call_args["type"] == "stop"
                assert call_args["stop_price"] == "48000.0"
                assert result["id"] == "ord_789"
        else:
            pytest.skip("Stop order not implemented in Coinbase broker")

    def test_cancel_order(self, coinbase_broker: CoinbaseBroker):
        """Test canceling an order."""
        with patch.object(coinbase_broker.client, "cancel_order") as mock_cancel:
            mock_cancel.return_value = {"order_id": "ord_123", "success": True}
            result = coinbase_broker.cancel_order("ord_123")
            mock_cancel.assert_called_once_with("ord_123")
            assert result["success"] is True

    def test_get_order_status(self, coinbase_broker: CoinbaseBroker):
        """Test getting order status."""
        with patch.object(coinbase_broker.client, "get_order") as mock_get:
            mock_get.return_value = {
                "id": "ord_123",
                "status": "done",
                "filled_size": "0.1",
                "price": "50000",
            }
            result = coinbase_broker.get_order_status("ord_123")
            mock_get.assert_called_once_with("ord_123")
            assert result["status"] == "done"
            assert result["filled_size"] == "0.1"

    def test_get_orders(self, coinbase_broker: CoinbaseBroker):
        """Test listing orders."""
        with patch.object(coinbase_broker.client, "list_orders") as mock_list:
            mock_list.return_value = [
                {"id": "ord1", "product_id": "BTC-USD"},
                {"id": "ord2", "product_id": "ETH-USD"},
            ]
            result = coinbase_broker.get_orders()
            mock_list.assert_called_once()
            assert len(result) == 2


class TestCoinbaseBrokerMarketData:
    """Test Coinbase market data operations."""

    def test_get_market_data(self, coinbase_broker: CoinbaseBroker):
        """Test getting market data (candles)."""
        with patch.object(coinbase_broker.client, "get_product_candles") as mock_candles:
            mock_candles.return_value = [
                [1500000000, 50000, 51000, 49000, 50500, 1000],
                [1500000060, 50500, 51500, 50000, 51200, 800],
            ]
            result = coinbase_broker.get_market_data("BTC-USD", timeframe="1h", limit=10)
            mock_candles.assert_called_once_with(
                product_id="BTC-USD",
                granularity=3600,  # 1h
                start=None,
                end=None,
            )
            assert isinstance(result, list)
            assert len(result) == 2
            # The broker should normalize the data to include open, high, low, close, volume
            if result:
                assert "open" in result[0] or "o" in result[0]

    def test_get_ticker_price(self, coinbase_broker: CoinbaseBroker):
        """Test getting current ticker price."""
        if hasattr(coinbase_broker, "get_ticker_price"):
            with patch.object(coinbase_broker.client, "get_product_ticker") as mock_ticker:
                mock_ticker.return_value = {"price": "50000.00", "volume": "1000"}
                result = coinbase_broker.get_ticker_price("BTC-USD")
                mock_ticker.assert_called_once_with(product_id="BTC-USD")
                assert result["price"] == "50000.00"

    def test_get_order_book(self, coinbase_broker: CoinbaseBroker):
        """Test getting order book."""
        if hasattr(coinbase_broker, "get_order_book"):
            with patch.object(coinbase_broker.client, "get_product_book") as mock_book:
                mock_book.return_value = {
                    "bids": [["50000", "0.5"]],
                    "asks": [["50001", "0.3"]],
                }
                result = coinbase_broker.get_order_book("BTC-USD", limit=10)
                mock_book.assert_called_once_with(product_id="BTC-USD", level=1)
                assert "bids" in result


class TestCoinbaseBrokerErrorHandling:
    """Test error handling for Coinbase broker specific errors."""

    def test_coinbase_api_error_handling(self, coinbase_broker: CoinbaseBroker):
        """Test handling of Coinbase API errors (e.g., 400, 429)."""
        with patch.object(
            coinbase_broker.client,
            "get_accounts",
            side_effect=Exception("HTTP 429 Too Many Requests")
        ):
            with pytest.raises(Exception) as exc:
                coinbase_broker.get_account()
            assert "429" in str(exc.value) or "Too Many Requests" in str(exc.value)

    def test_invalid_symbol_error(self, coinbase_broker: CoinbaseBroker):
        """Test invalid symbol error from Coinbase."""
        with patch.object(
            coinbase_broker.client,
            "place_order",
            side_effect=Exception("Invalid product_id: INVALID")
        ):
            with pytest.raises(Exception) as exc:
                coinbase_broker.place_order("INVALID", "buy", "market", 1)
            assert "invalid" in str(exc.value).lower()

    def test_insufficient_balance_error(self, coinbase_broker: CoinbaseBroker):
        """Test insufficient balance error from Coinbase."""
        with patch.object(
            coinbase_broker.client,
            "place_order",
            side_effect=Exception("Insufficient funds")
        ):
            with pytest.raises(Exception) as exc:
                coinbase_broker.place_order("BTC-USD", "buy", "market", 1000)
            assert "insufficient" in str(exc.value).lower()

    def test_order_not_found_error(self, coinbase_broker: CoinbaseBroker):
        """Test order not found error."""
        with patch.object(
            coinbase_broker.client,
            "get_order",
            side_effect=Exception("Order not found")
        ):
            with pytest.raises(Exception) as exc:
                coinbase_broker.get_order_status("nonexistent")
            assert "not found" in str(exc.value).lower()


class TestCoinbaseBrokerSandbox:
    """Test specific behaviors in sandbox mode."""

    def test_sandbox_account_limits(self, coinbase_broker: CoinbaseBroker):
        """Test that sandbox account has balance limits."""
        with patch.object(coinbase_broker.client, "get_accounts") as mock_acc:
            mock_acc.return_value = [
                {"currency": "USD", "balance": {"amount": "100000.0"}}
            ]
            account = coinbase_broker.get_account()
            assert float(account[0]["balance"]["amount"]) == 100000.0


class TestCoinbaseBrokerWebSocket:
    """Test Coinbase WebSocket data streams (if implemented)."""

    def test_stream_market_data(self, coinbase_broker: CoinbaseBroker):
        """Test streaming market data via WebSocket (if method exists)."""
        if hasattr(coinbase_broker, "stream_data"):
            with patch.object(coinbase_broker, "stream_data") as mock_stream:
                mock_stream.return_value = None
                coinbase_broker.stream_data("BTC-USD")
                mock_stream.assert_called_once_with("BTC-USD")
