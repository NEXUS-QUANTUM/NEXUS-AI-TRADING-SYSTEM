# tests/brokers/test_binance_broker.py
"""
Binance Broker Specific Tests.

This module contains tests specifically for the Binance broker integration,
including spot, margin, and futures trading, testnet configuration,
different order types, and Binance-specific API features.

All tests use mocked Binance client and fixtures from conftest.py.
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.brokers.binance.binance_broker import BinanceBroker
from backend.brokers.base_broker import BaseBroker


class TestBinanceBrokerInitialization:
    """Test Binance broker initialization and configuration."""

    def test_binance_broker_is_base_broker(self, binance_broker: BinanceBroker):
        """Test that BinanceBroker inherits from BaseBroker."""
        assert isinstance(binance_broker, BaseBroker)

    def test_binance_broker_attributes(self, binance_broker: BinanceBroker):
        """Test that Binance broker has correct attributes."""
        assert binance_broker.api_key == "test_key"
        assert binance_broker.api_secret == "test_secret"
        assert binance_broker.testnet is True
        # Base URL should be set to testnet endpoint
        assert binance_broker.base_url is not None
        assert "testnet" in binance_broker.base_url

    def test_binance_broker_has_required_methods(self, binance_broker: BinanceBroker):
        """Test that Binance broker implements all required methods."""
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
            assert hasattr(binance_broker, method)
            assert callable(getattr(binance_broker, method))

    def test_binance_testnet_enabled(self, binance_broker: BinanceBroker):
        """Test that testnet mode is correctly set."""
        assert binance_broker.testnet is True
        # With testnet=True, base_url should point to testnet API
        assert "testnet" in binance_broker.base_url


class TestBinanceBrokerAccount:
    """Test Binance account-related operations."""

    def test_get_account_returns_dict(self, binance_broker: BinanceBroker):
        """Test get_account returns a dict with expected fields."""
        with patch.object(binance_broker.client, "get_account") as mock_client:
            mock_client.return_value = {
                "balances": [{"asset": "BTC", "free": "0.5", "locked": "0.0"}],
                "canTrade": True,
                "canWithdraw": True,
            }
            result = binance_broker.get_account()
            mock_client.assert_called_once()
            assert isinstance(result, dict)
            # Binance account returns balances, etc.
            assert "balances" in result
            assert result["canTrade"] is True

    def test_get_account_handles_errors(self, binance_broker: BinanceBroker):
        """Test that get_account raises appropriate exceptions on client error."""
        with patch.object(binance_broker.client, "get_account", side_effect=Exception("API error")):
            with pytest.raises(Exception):
                binance_broker.get_account()

    def test_get_balance(self, binance_broker: BinanceBroker):
        """Test get_balance if implemented (Binance-specific)."""
        if hasattr(binance_broker, "get_balance"):
            with patch.object(binance_broker.client, "get_account") as mock_client:
                mock_client.return_value = {
                    "balances": [
                        {"asset": "BTC", "free": "0.5", "locked": "0.0"},
                        {"asset": "USDT", "free": "10000.0", "locked": "0.0"},
                    ]
                }
                result = binance_broker.get_balance()
                mock_client.assert_called_once()
                assert isinstance(result, dict)
                assert "BTC" in result
                assert result["BTC"]["free"] == "0.5"


class TestBinanceBrokerPositions:
    """Test Binance position-related operations (for futures)."""

    def test_get_positions_returns_list(self, binance_broker: BinanceBroker):
        """Test get_positions returns a list of position dicts."""
        with patch.object(binance_broker.client, "futures_position_information") as mock_client:
            mock_client.return_value = [
                {"symbol": "BTCUSDT", "positionAmt": "0.5", "entryPrice": "50000", "unRealizedProfit": "100"}
            ]
            result = binance_broker.get_positions()
            mock_client.assert_called_once()
            assert isinstance(result, list)
            if result:
                assert "symbol" in result[0]
                assert "positionAmt" in result[0]

    def test_get_positions_empty(self, binance_broker: BinanceBroker):
        """Test get_positions returns empty list when no positions."""
        with patch.object(binance_broker.client, "futures_position_information") as mock_client:
            mock_client.return_value = []
            result = binance_broker.get_positions()
            assert result == []


class TestBinanceBrokerOrders:
    """Test Binance order operations."""

    def test_place_market_order(self, binance_broker: BinanceBroker):
        """Test placing a market order."""
        with patch.object(binance_broker.client, "order_market_buy") as mock_order:
            mock_order.return_value = {
                "symbol": "BTCUSDT",
                "orderId": "123",
                "status": "FILLED",
                "executedQty": "0.1",
                "cummulativeQuoteQty": "5000",
            }
            result = binance_broker.place_order(
                symbol="BTCUSDT",
                side="buy",
                order_type="market",
                quantity=0.1,
            )
            mock_order.assert_called_once_with(symbol="BTCUSDT", quantity=0.1)
            assert result["orderId"] == "123"
            assert result["status"] == "FILLED"

    def test_place_market_sell_order(self, binance_broker: BinanceBroker):
        """Test placing a market sell order."""
        with patch.object(binance_broker.client, "order_market_sell") as mock_order:
            mock_order.return_value = {"symbol": "BTCUSDT", "orderId": "456", "status": "FILLED"}
            result = binance_broker.place_order(
                symbol="BTCUSDT",
                side="sell",
                order_type="market",
                quantity=0.2,
            )
            mock_order.assert_called_once_with(symbol="BTCUSDT", quantity=0.2)
            assert result["orderId"] == "456"

    def test_place_limit_order(self, binance_broker: BinanceBroker):
        """Test placing a limit order."""
        with patch.object(binance_broker.client, "order_limit_buy") as mock_order:
            mock_order.return_value = {"symbol": "BTCUSDT", "orderId": "789", "status": "NEW"}
            result = binance_broker.place_order(
                symbol="BTCUSDT",
                side="buy",
                order_type="limit",
                quantity=0.5,
                price=50000.0,
            )
            mock_order.assert_called_once_with(symbol="BTCUSDT", quantity=0.5, price=50000.0)
            assert result["orderId"] == "789"

    def test_place_limit_sell_order(self, binance_broker: BinanceBroker):
        """Test placing a limit sell order."""
        with patch.object(binance_broker.client, "order_limit_sell") as mock_order:
            mock_order.return_value = {"symbol": "BTCUSDT", "orderId": "101", "status": "NEW"}
            result = binance_broker.place_order(
                symbol="BTCUSDT",
                side="sell",
                order_type="limit",
                quantity=0.5,
                price=55000.0,
            )
            mock_order.assert_called_once_with(symbol="BTCUSDT", quantity=0.5, price=55000.0)
            assert result["orderId"] == "101"

    def test_place_stop_loss_order(self, binance_broker: BinanceBroker):
        """Test placing a stop-loss order (Binance uses STOP_LOSS)."""
        # Binance order types: STOP_LOSS, STOP_LOSS_LIMIT, TAKE_PROFIT, etc.
        with patch.object(binance_broker.client, "order_stop_loss_buy") as mock_order:
            mock_order.return_value = {"symbol": "BTCUSDT", "orderId": "202", "status": "NEW"}
            result = binance_broker.place_order(
                symbol="BTCUSDT",
                side="buy",
                order_type="stop_loss",
                quantity=0.5,
                price=48000.0,  # stop price
            )
            mock_order.assert_called_once_with(symbol="BTCUSDT", quantity=0.5, stopPrice=48000.0)
            assert result["orderId"] == "202"

    def test_cancel_order(self, binance_broker: BinanceBroker):
        """Test canceling an order."""
        with patch.object(binance_broker.client, "cancel_order") as mock_cancel:
            mock_cancel.return_value = {"symbol": "BTCUSDT", "orderId": "123", "status": "CANCELED"}
            result = binance_broker.cancel_order("123")
            mock_cancel.assert_called_once_with(symbol="BTCUSDT", orderId="123")
            assert result["status"] == "CANCELED"

    def test_get_order_status(self, binance_broker: BinanceBroker):
        """Test getting order status."""
        with patch.object(binance_broker.client, "get_order") as mock_get:
            mock_get.return_value = {"symbol": "BTCUSDT", "orderId": "123", "status": "FILLED"}
            result = binance_broker.get_order_status("123")
            mock_get.assert_called_once_with(symbol="BTCUSDT", orderId="123")
            assert result["status"] == "FILLED"

    def test_get_orders(self, binance_broker: BinanceBroker):
        """Test listing orders."""
        with patch.object(binance_broker.client, "get_open_orders") as mock_list:
            mock_list.return_value = [
                {"symbol": "BTCUSDT", "orderId": "1"},
                {"symbol": "ETHUSDT", "orderId": "2"},
            ]
            result = binance_broker.get_orders()
            mock_list.assert_called_once()
            assert len(result) == 2


class TestBinanceBrokerMarketData:
    """Test Binance market data operations."""

    def test_get_market_data(self, binance_broker: BinanceBroker):
        """Test getting market data (klines)."""
        with patch.object(binance_broker.client, "get_klines") as mock_klines:
            mock_klines.return_value = [
                [1500000000000, "50000", "51000", "49000", "50500", "1000"],
                [1500000060000, "50500", "51500", "50000", "51200", "800"],
            ]
            result = binance_broker.get_market_data("BTCUSDT", timeframe="1h", limit=10)
            mock_klines.assert_called_once_with(symbol="BTCUSDT", interval="1h", limit=10)
            assert isinstance(result, list)
            assert len(result) == 2
            # The format should be normalized to include open, high, low, close, volume
            if result:
                assert "open" in result[0] or "o" in result[0]

    def test_get_ticker_price(self, binance_broker: BinanceBroker):
        """Test getting current ticker price."""
        if hasattr(binance_broker, "get_ticker_price"):
            with patch.object(binance_broker.client, "get_symbol_ticker") as mock_ticker:
                mock_ticker.return_value = {"symbol": "BTCUSDT", "price": "50000.00"}
                result = binance_broker.get_ticker_price("BTCUSDT")
                mock_ticker.assert_called_once_with(symbol="BTCUSDT")
                assert result["price"] == "50000.00"

    def test_get_order_book(self, binance_broker: BinanceBroker):
        """Test getting order book."""
        if hasattr(binance_broker, "get_order_book"):
            with patch.object(binance_broker.client, "get_order_book") as mock_book:
                mock_book.return_value = {"bids": [["50000", "0.5"]], "asks": [["50001", "0.3"]]}
                result = binance_broker.get_order_book("BTCUSDT", limit=10)
                mock_book.assert_called_once_with(symbol="BTCUSDT", limit=10)
                assert "bids" in result


class TestBinanceBrokerFutures:
    """Test Binance futures-specific features."""

    def test_futures_account(self, binance_broker: BinanceBroker):
        """Test getting futures account info."""
        if hasattr(binance_broker, "get_futures_account"):
            with patch.object(binance_broker.client, "futures_account") as mock_acc:
                mock_acc.return_value = {"totalCrossUnPnl": "100", "totalWalletBalance": "10000"}
                result = binance_broker.get_futures_account()
                mock_acc.assert_called_once()
                assert "totalWalletBalance" in result

    def test_futures_order(self, binance_broker: BinanceBroker):
        """Test placing a futures order."""
        if hasattr(binance_broker, "place_futures_order"):
            with patch.object(binance_broker.client, "futures_create_order") as mock_order:
                mock_order.return_value = {"orderId": "fut_123", "status": "NEW"}
                result = binance_broker.place_futures_order(
                    symbol="BTCUSDT", side="buy", order_type="market", quantity=0.1
                )
                mock_order.assert_called_once()
                assert result["orderId"] == "fut_123"


class TestBinanceBrokerErrorHandling:
    """Test error handling for Binance broker specific errors."""

    def test_binance_api_error_handling(self, binance_broker: BinanceBroker):
        """Test handling of Binance API errors (e.g., 429, 403)."""
        with patch.object(binance_broker.client, "get_account", side_effect=Exception("HTTP 429 Too Many Requests")):
            with pytest.raises(Exception) as exc:
                binance_broker.get_account()
            assert "429" in str(exc.value) or "Too Many Requests" in str(exc.value)

    def test_invalid_symbol_error(self, binance_broker: BinanceBroker):
        """Test invalid symbol error from Binance."""
        with patch.object(
            binance_broker.client,
            "order_market_buy",
            side_effect=Exception("Invalid symbol: INVALID")
        ):
            with pytest.raises(Exception) as exc:
                binance_broker.place_order("INVALID", "buy", "market", 1)
            assert "invalid" in str(exc.value).lower()

    def test_insufficient_balance_error(self, binance_broker: BinanceBroker):
        """Test insufficient balance error from Binance."""
        with patch.object(
            binance_broker.client,
            "order_market_buy",
            side_effect=Exception("Balance insufficient")
        ):
            with pytest.raises(Exception) as exc:
                binance_broker.place_order("BTCUSDT", "buy", "market", 1000)
            assert "insufficient" in str(exc.value).lower()

    def test_order_not_found_error(self, binance_broker: BinanceBroker):
        """Test order not found error."""
        with patch.object(
            binance_broker.client,
            "get_order",
            side_effect=Exception("Order does not exist")
        ):
            with pytest.raises(Exception) as exc:
                binance_broker.get_order_status("nonexistent")
            assert "not exist" in str(exc.value).lower()


class TestBinanceBrokerTestnet:
    """Test specific behaviors in testnet mode."""

    def test_testnet_account_limits(self, binance_broker: BinanceBroker):
        """Test that testnet account has balance limits."""
        with patch.object(binance_broker.client, "get_account") as mock_acc:
            mock_acc.return_value = {
                "balances": [{"asset": "USDT", "free": "100000.0", "locked": "0.0"}]
            }
            account = binance_broker.get_account()
            assert float(account["balances"][0]["free"]) == 100000.0


class TestBinanceBrokerWebSocket:
    """Test Binance WebSocket data streams (if implemented)."""

    def test_stream_market_data(self, binance_broker: BinanceBroker):
        """Test streaming market data via WebSocket (if method exists)."""
        if hasattr(binance_broker, "stream_data"):
            with patch.object(binance_broker, "stream_data") as mock_stream:
                mock_stream.return_value = None
                binance_broker.stream_data("BTCUSDT")
                mock_stream.assert_called_once_with("BTCUSDT")
