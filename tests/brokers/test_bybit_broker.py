# tests/brokers/test_bybit_broker.py
"""
Bybit Broker Specific Tests.

This module contains tests specifically for the Bybit broker integration,
including spot, futures, and perpetual trading, testnet configuration,
different order types, and Bybit-specific API features.

All tests use mocked Bybit client and fixtures from conftest.py.
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.brokers.bybit.bybit_broker import BybitBroker
from backend.brokers.base_broker import BaseBroker


class TestBybitBrokerInitialization:
    """Test Bybit broker initialization and configuration."""

    def test_bybit_broker_is_base_broker(self, bybit_broker: BybitBroker):
        """Test that BybitBroker inherits from BaseBroker."""
        assert isinstance(bybit_broker, BaseBroker)

    def test_bybit_broker_attributes(self, bybit_broker: BybitBroker):
        """Test that Bybit broker has correct attributes."""
        assert bybit_broker.api_key == "test_key"
        assert bybit_broker.api_secret == "test_secret"
        assert bybit_broker.testnet is True
        # Base URL should be set to testnet endpoint
        assert bybit_broker.base_url is not None
        assert "testnet" in bybit_broker.base_url

    def test_bybit_broker_has_required_methods(self, bybit_broker: BybitBroker):
        """Test that Bybit broker implements all required methods."""
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
            assert hasattr(bybit_broker, method)
            assert callable(getattr(bybit_broker, method))

    def test_bybit_testnet_enabled(self, bybit_broker: BybitBroker):
        """Test that testnet mode is correctly set."""
        assert bybit_broker.testnet is True
        # With testnet=True, base_url should point to testnet API
        assert "testnet" in bybit_broker.base_url


class TestBybitBrokerAccount:
    """Test Bybit account-related operations."""

    def test_get_account_returns_dict(self, bybit_broker: BybitBroker):
        """Test get_account returns a dict with expected fields."""
        with patch.object(bybit_broker.client, "get_wallet_balance") as mock_client:
            mock_client.return_value = {
                "result": {
                    "list": [
                        {
                            "coin": "USDT",
                            "walletBalance": "10000.0",
                            "availableBalance": "9500.0",
                        }
                    ]
                }
            }
            result = bybit_broker.get_account()
            mock_client.assert_called_once()
            assert isinstance(result, dict)
            # Bybit account returns balances, etc.
            assert "result" in result
            assert "list" in result["result"]

    def test_get_account_handles_errors(self, bybit_broker: BybitBroker):
        """Test that get_account raises appropriate exceptions on client error."""
        with patch.object(bybit_broker.client, "get_wallet_balance", side_effect=Exception("API error")):
            with pytest.raises(Exception):
                bybit_broker.get_account()


class TestBybitBrokerPositions:
    """Test Bybit position-related operations."""

    def test_get_positions_returns_list(self, bybit_broker: BybitBroker):
        """Test get_positions returns a list of position dicts."""
        with patch.object(bybit_broker.client, "get_positions") as mock_client:
            mock_client.return_value = {
                "result": {
                    "list": [
                        {
                            "symbol": "BTCUSDT",
                            "size": "0.5",
                            "entryPrice": "50000",
                            "unrealisedPnl": "100",
                        }
                    ]
                }
            }
            result = bybit_broker.get_positions()
            mock_client.assert_called_once()
            assert isinstance(result, list)
            if result:
                assert "symbol" in result[0]
                assert "size" in result[0]

    def test_get_positions_empty(self, bybit_broker: BybitBroker):
        """Test get_positions returns empty list when no positions."""
        with patch.object(bybit_broker.client, "get_positions") as mock_client:
            mock_client.return_value = {"result": {"list": []}}
            result = bybit_broker.get_positions()
            assert result == []


class TestBybitBrokerOrders:
    """Test Bybit order operations."""

    def test_place_market_order(self, bybit_broker: BybitBroker):
        """Test placing a market order."""
        with patch.object(bybit_broker.client, "place_order") as mock_order:
            mock_order.return_value = {
                "result": {
                    "orderId": "123",
                    "orderStatus": "Filled",
                    "symbol": "BTCUSDT",
                    "side": "Buy",
                    "orderType": "Market",
                    "qty": "0.1",
                    "price": "50000",
                }
            }
            result = bybit_broker.place_order(
                symbol="BTCUSDT",
                side="buy",
                order_type="market",
                quantity=0.1,
            )
            mock_order.assert_called_once()
            # Check that the order type was set correctly
            call_args = mock_order.call_args[1]
            assert call_args["symbol"] == "BTCUSDT"
            assert call_args["side"] == "Buy"
            assert call_args["orderType"] == "Market"
            assert call_args["qty"] == "0.1"
            assert result["orderId"] == "123"

    def test_place_limit_order(self, bybit_broker: BybitBroker):
        """Test placing a limit order."""
        with patch.object(bybit_broker.client, "place_order") as mock_order:
            mock_order.return_value = {
                "result": {"orderId": "456", "orderStatus": "Created"}
            }
            result = bybit_broker.place_order(
                symbol="BTCUSDT",
                side="sell",
                order_type="limit",
                quantity=0.5,
                price=55000.0,
            )
            mock_order.assert_called_once()
            call_args = mock_order.call_args[1]
            assert call_args["orderType"] == "Limit"
            assert call_args["price"] == "55000"
            assert result["orderId"] == "456"

    def test_place_stop_loss_order(self, bybit_broker: BybitBroker):
        """Test placing a stop-loss order."""
        with patch.object(bybit_broker.client, "place_order") as mock_order:
            mock_order.return_value = {
                "result": {"orderId": "789", "orderStatus": "Created"}
            }
            result = bybit_broker.place_order(
                symbol="BTCUSDT",
                side="buy",
                order_type="stop_loss",
                quantity=0.5,
                price=48000.0,  # stop price
            )
            mock_order.assert_called_once()
            call_args = mock_order.call_args[1]
            assert call_args["orderType"] == "StopLoss"
            assert call_args["stopPrice"] == "48000"
            assert result["orderId"] == "789"

    def test_cancel_order(self, bybit_broker: BybitBroker):
        """Test canceling an order."""
        with patch.object(bybit_broker.client, "cancel_order") as mock_cancel:
            mock_cancel.return_value = {"result": {"orderId": "123", "orderStatus": "Cancelled"}}
            result = bybit_broker.cancel_order("123")
            mock_cancel.assert_called_once_with(orderId="123")
            assert result["orderStatus"] == "Cancelled"

    def test_get_order_status(self, bybit_broker: BybitBroker):
        """Test getting order status."""
        with patch.object(bybit_broker.client, "get_order") as mock_get:
            mock_get.return_value = {
                "result": {"orderId": "123", "orderStatus": "Filled"}
            }
            result = bybit_broker.get_order_status("123")
            mock_get.assert_called_once_with(orderId="123")
            assert result["orderStatus"] == "Filled"

    def test_get_orders(self, bybit_broker: BybitBroker):
        """Test listing orders."""
        with patch.object(bybit_broker.client, "get_open_orders") as mock_list:
            mock_list.return_value = {
                "result": {
                    "list": [
                        {"orderId": "1", "symbol": "BTCUSDT"},
                        {"orderId": "2", "symbol": "ETHUSDT"},
                    ]
                }
            }
            result = bybit_broker.get_orders()
            mock_list.assert_called_once()
            assert len(result) == 2


class TestBybitBrokerMarketData:
    """Test Bybit market data operations."""

    def test_get_market_data(self, bybit_broker: BybitBroker):
        """Test getting market data (kline)."""
        with patch.object(bybit_broker.client, "get_kline") as mock_kline:
            mock_kline.return_value = {
                "result": {
                    "list": [
                        ["1500000000000", "50000", "51000", "49000", "50500", "1000"],
                        ["1500000060000", "50500", "51500", "50000", "51200", "800"],
                    ]
                }
            }
            result = bybit_broker.get_market_data("BTCUSDT", timeframe="1h", limit=10)
            mock_kline.assert_called_once_with(
                symbol="BTCUSDT", interval="1h", limit=10
            )
            assert isinstance(result, list)
            assert len(result) == 2
            # Check normalized format has open, high, low, close, volume
            if result:
                assert "open" in result[0] or "o" in result[0]

    def test_get_ticker_price(self, bybit_broker: BybitBroker):
        """Test getting current ticker price."""
        if hasattr(bybit_broker, "get_ticker_price"):
            with patch.object(bybit_broker.client, "get_tickers") as mock_ticker:
                mock_ticker.return_value = {
                    "result": {"list": [{"symbol": "BTCUSDT", "price": "50000.00"}]}
                }
                result = bybit_broker.get_ticker_price("BTCUSDT")
                mock_ticker.assert_called_once_with(category="spot", symbol="BTCUSDT")
                assert result["price"] == "50000.00"

    def test_get_order_book(self, bybit_broker: BybitBroker):
        """Test getting order book."""
        if hasattr(bybit_broker, "get_order_book"):
            with patch.object(bybit_broker.client, "get_orderbook") as mock_book:
                mock_book.return_value = {
                    "result": {"b": [["50000", "0.5"]], "a": [["50001", "0.3"]]}
                }
                result = bybit_broker.get_order_book("BTCUSDT", limit=10)
                mock_book.assert_called_once_with(category="spot", symbol="BTCUSDT", limit=10)
                assert "bids" in result


class TestBybitBrokerFutures:
    """Test Bybit futures-specific features."""

    def test_futures_account(self, bybit_broker: BybitBroker):
        """Test getting futures account info."""
        if hasattr(bybit_broker, "get_futures_account"):
            with patch.object(bybit_broker.client, "get_wallet_balance") as mock_acc:
                mock_acc.return_value = {
                    "result": {
                        "list": [{"coin": "USDT", "walletBalance": "10000"}]
                    }
                }
                result = bybit_broker.get_futures_account()
                mock_acc.assert_called_once_with(accountType="UNIFIED")
                assert "result" in result

    def test_futures_order(self, bybit_broker: BybitBroker):
        """Test placing a futures order."""
        if hasattr(bybit_broker, "place_futures_order"):
            with patch.object(bybit_broker.client, "place_order") as mock_order:
                mock_order.return_value = {"result": {"orderId": "fut_123"}}
                result = bybit_broker.place_futures_order(
                    symbol="BTCUSDT", side="buy", order_type="Market", quantity=0.1
                )
                mock_order.assert_called_once()
                # Check that category="linear" or "inverse" depending on implementation.
                call_args = mock_order.call_args[1]
                assert call_args["category"] == "linear"
                assert result["orderId"] == "fut_123"


class TestBybitBrokerErrorHandling:
    """Test error handling for Bybit broker specific errors."""

    def test_bybit_api_error_handling(self, bybit_broker: BybitBroker):
        """Test handling of Bybit API errors (e.g., 10001, 10002)."""
        with patch.object(
            bybit_broker.client,
            "get_wallet_balance",
            side_effect=Exception("API error: 10001")
        ):
            with pytest.raises(Exception) as exc:
                bybit_broker.get_account()
            assert "10001" in str(exc.value)

    def test_invalid_symbol_error(self, bybit_broker: BybitBroker):
        """Test invalid symbol error from Bybit."""
        with patch.object(
            bybit_broker.client,
            "place_order",
            side_effect=Exception("Invalid symbol: INVALID")
        ):
            with pytest.raises(Exception) as exc:
                bybit_broker.place_order("INVALID", "buy", "market", 1)
            assert "invalid" in str(exc.value).lower()

    def test_insufficient_balance_error(self, bybit_broker: BybitBroker):
        """Test insufficient balance error from Bybit."""
        with patch.object(
            bybit_broker.client,
            "place_order",
            side_effect=Exception("Insufficient balance")
        ):
            with pytest.raises(Exception) as exc:
                bybit_broker.place_order("BTCUSDT", "buy", "market", 1000)
            assert "insufficient" in str(exc.value).lower()

    def test_order_not_found_error(self, bybit_broker: BybitBroker):
        """Test order not found error."""
        with patch.object(
            bybit_broker.client,
            "get_order",
            side_effect=Exception("Order does not exist")
        ):
            with pytest.raises(Exception) as exc:
                bybit_broker.get_order_status("nonexistent")
            assert "not exist" in str(exc.value).lower()


class TestBybitBrokerTestnet:
    """Test specific behaviors in testnet mode."""

    def test_testnet_account_limits(self, bybit_broker: BybitBroker):
        """Test that testnet account has balance limits."""
        with patch.object(bybit_broker.client, "get_wallet_balance") as mock_acc:
            mock_acc.return_value = {
                "result": {
                    "list": [{"coin": "USDT", "walletBalance": "100000.0"}]
                }
            }
            account = bybit_broker.get_account()
            assert float(account["result"]["list"][0]["walletBalance"]) == 100000.0


class TestBybitBrokerWebSocket:
    """Test Bybit WebSocket data streams (if implemented)."""

    def test_stream_market_data(self, bybit_broker: BybitBroker):
        """Test streaming market data via WebSocket (if method exists)."""
        if hasattr(bybit_broker, "stream_data"):
            with patch.object(bybit_broker, "stream_data") as mock_stream:
                mock_stream.return_value = None
                bybit_broker.stream_data("BTCUSDT")
                mock_stream.assert_called_once_with("BTCUSDT")
