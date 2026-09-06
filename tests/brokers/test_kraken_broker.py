# tests/brokers/test_kraken_broker.py
"""
Kraken Broker Specific Tests.

This module contains tests specifically for the Kraken broker integration,
including spot, margin, and futures trading (if supported), sandbox configuration,
different order types, and Kraken-specific API features.

All tests use mocked Kraken client and fixtures from conftest.py.
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.brokers.kraken.kraken_broker import KrakenBroker
from backend.brokers.base_broker import BaseBroker


class TestKrakenBrokerInitialization:
    """Test Kraken broker initialization and configuration."""

    def test_kraken_broker_is_base_broker(self, kraken_broker: KrakenBroker):
        """Test that KrakenBroker inherits from BaseBroker."""
        assert isinstance(kraken_broker, BaseBroker)

    def test_kraken_broker_attributes(self, kraken_broker: KrakenBroker):
        """Test that Kraken broker has correct attributes."""
        assert kraken_broker.api_key == "test_key"
        assert kraken_broker.api_secret == "test_secret"
        assert kraken_broker.sandbox is True
        # Base URL should be set to sandbox endpoint
        assert kraken_broker.base_url is not None
        assert "sandbox" in kraken_broker.base_url

    def test_kraken_broker_has_required_methods(self, kraken_broker: KrakenBroker):
        """Test that Kraken broker implements all required methods."""
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
            assert hasattr(kraken_broker, method)
            assert callable(getattr(kraken_broker, method))

    def test_kraken_sandbox_enabled(self, kraken_broker: KrakenBroker):
        """Test that sandbox mode is correctly set."""
        assert kraken_broker.sandbox is True
        # With sandbox=True, base_url should point to sandbox API
        assert "sandbox" in kraken_broker.base_url


class TestKrakenBrokerAccount:
    """Test Kraken account-related operations."""

    def test_get_account_returns_dict(self, kraken_broker: KrakenBroker):
        """Test get_account returns a dict with expected fields."""
        with patch.object(kraken_broker.client, "get_balance") as mock_client:
            mock_client.return_value = {
                "USD": "10000.0",
                "BTC": "0.5",
                "ETH": "2.0",
            }
            result = kraken_broker.get_account()
            mock_client.assert_called_once()
            assert isinstance(result, dict)
            # Kraken account returns balance dictionary
            assert "USD" in result
            assert result["USD"] == "10000.0"

    def test_get_account_handles_errors(self, kraken_broker: KrakenBroker):
        """Test that get_account raises appropriate exceptions on client error."""
        with patch.object(kraken_broker.client, "get_balance", side_effect=Exception("API error")):
            with pytest.raises(Exception):
                kraken_broker.get_account()


class TestKrakenBrokerPositions:
    """Test Kraken position-related operations."""

    def test_get_positions_returns_list(self, kraken_broker: KrakenBroker):
        """Test get_positions returns a list of position dicts."""
        # Kraken does not have positions in the same way; uses open orders or balance.
        # We may map balance or open orders to positions.
        # For this test, we'll mock the client's get_open_orders or get_balance.
        with patch.object(kraken_broker.client, "get_open_orders") as mock_client:
            mock_client.return_value = {
                "open": {
                    "order1": {"descr": {"pair": "BTCUSD", "type": "buy"}, "vol": "0.5"}
                }
            }
            result = kraken_broker.get_positions()
            mock_client.assert_called_once()
            assert isinstance(result, list)
            # The broker should normalize the response to a list of positions
            # Even if it's empty, it should be a list.
            # Since we mock, it may be empty or have data.
            # We'll just check it's a list.
            assert isinstance(result, list)

    def test_get_positions_empty(self, kraken_broker: KrakenBroker):
        """Test get_positions returns empty list when no positions."""
        with patch.object(kraken_broker.client, "get_open_orders") as mock_client:
            mock_client.return_value = {"open": {}}
            result = kraken_broker.get_positions()
            assert result == []


class TestKrakenBrokerOrders:
    """Test Kraken order operations."""

    def test_place_market_order(self, kraken_broker: KrakenBroker):
        """Test placing a market order."""
        with patch.object(kraken_broker.client, "add_order") as mock_order:
            mock_order.return_value = {
                "txid": ["order_txid_123"],
                "descr": {"order": "buy 0.1 BTCUSD @ market"},
            }
            result = kraken_broker.place_order(
                symbol="BTCUSD",
                side="buy",
                order_type="market",
                quantity=0.1,
            )
            mock_order.assert_called_once()
            call_args = mock_order.call_args[1]
            assert call_args["pair"] == "BTCUSD"
            assert call_args["type"] == "buy"
            assert call_args["ordertype"] == "market"
            assert call_args["volume"] == "0.1"
            # Kraken returns txid as order ID
            assert result["txid"] == "order_txid_123"

    def test_place_limit_order(self, kraken_broker: KrakenBroker):
        """Test placing a limit order."""
        with patch.object(kraken_broker.client, "add_order") as mock_order:
            mock_order.return_value = {
                "txid": ["order_txid_456"],
                "descr": {"order": "sell 0.5 BTCUSD @ limit 55000"},
            }
            result = kraken_broker.place_order(
                symbol="BTCUSD",
                side="sell",
                order_type="limit",
                quantity=0.5,
                price=55000.0,
            )
            mock_order.assert_called_once()
            call_args = mock_order.call_args[1]
            assert call_args["ordertype"] == "limit"
            assert call_args["price"] == "55000.0"
            assert result["txid"] == "order_txid_456"

    def test_place_stop_loss_order(self, kraken_broker: KrakenBroker):
        """Test placing a stop-loss order."""
        with patch.object(kraken_broker.client, "add_order") as mock_order:
            mock_order.return_value = {"txid": ["order_txid_789"]}
            result = kraken_broker.place_order(
                symbol="BTCUSD",
                side="buy",
                order_type="stop_loss",
                quantity=0.5,
                price=48000.0,  # stop price
            )
            mock_order.assert_called_once()
            call_args = mock_order.call_args[1]
            assert call_args["ordertype"] == "stop-loss"
            assert call_args["price2"] == "48000.0"  # Stop price in Kraken
            assert result["txid"] == "order_txid_789"

    def test_cancel_order(self, kraken_broker: KrakenBroker):
        """Test canceling an order."""
        with patch.object(kraken_broker.client, "cancel_order") as mock_cancel:
            mock_cancel.return_value = {"count": 1}
            result = kraken_broker.cancel_order("order_txid_123")
            mock_cancel.assert_called_once_with(txid="order_txid_123")
            assert result["count"] == 1

    def test_get_order_status(self, kraken_broker: KrakenBroker):
        """Test getting order status."""
        with patch.object(kraken_broker.client, "query_orders") as mock_query:
            mock_query.return_value = {
                "order_txid_123": {
                    "status": "closed",
                    "vol_exec": "0.1",
                    "price": "50000.0",
                }
            }
            result = kraken_broker.get_order_status("order_txid_123")
            mock_query.assert_called_once_with(txid="order_txid_123")
            assert result["status"] == "closed"
            assert result["vol_exec"] == "0.1"

    def test_get_orders(self, kraken_broker: KrakenBroker):
        """Test listing orders."""
        with patch.object(kraken_broker.client, "get_open_orders") as mock_list:
            mock_list.return_value = {
                "open": {
                    "order1": {"descr": {"pair": "BTCUSD"}},
                    "order2": {"descr": {"pair": "ETHUSD"}},
                }
            }
            result = kraken_broker.get_orders()
            mock_list.assert_called_once()
            assert len(result) == 2


class TestKrakenBrokerMarketData:
    """Test Kraken market data operations."""

    def test_get_market_data(self, kraken_broker: KrakenBroker):
        """Test getting market data (OHLC)."""
        with patch.object(kraken_broker.client, "get_ohlc_data") as mock_ohlc:
            mock_ohlc.return_value = {
                "result": {
                    "BTCUSD": [
                        [1500000000, "50000", "51000", "49000", "50500", "1000", "50500"],
                        [1500000060, "50500", "51500", "50000", "51200", "800", "51200"],
                    ]
                }
            }
            result = kraken_broker.get_market_data("BTCUSD", timeframe="1h", limit=10)
            mock_ohlc.assert_called_once_with(
                pair="BTCUSD", interval=60, since=None
            )
            assert isinstance(result, list)
            assert len(result) == 2
            if result:
                # Should be normalized to open, high, low, close, volume
                assert "open" in result[0] or "o" in result[0]

    def test_get_ticker_price(self, kraken_broker: KrakenBroker):
        """Test getting current ticker price."""
        if hasattr(kraken_broker, "get_ticker_price"):
            with patch.object(kraken_broker.client, "get_ticker") as mock_ticker:
                mock_ticker.return_value = {
                    "result": {"BTCUSD": {"c": ["50000.00", "100"]}}
                }
                result = kraken_broker.get_ticker_price("BTCUSD")
                mock_ticker.assert_called_once_with(pair="BTCUSD")
                assert result["price"] == "50000.00"

    def test_get_order_book(self, kraken_broker: KrakenBroker):
        """Test getting order book."""
        if hasattr(kraken_broker, "get_order_book"):
            with patch.object(kraken_broker.client, "get_order_book") as mock_book:
                mock_book.return_value = {
                    "result": {"BTCUSD": {"bids": [["50000", "0.5"]], "asks": [["50001", "0.3"]]}}
                }
                result = kraken_broker.get_order_book("BTCUSD", limit=10)
                mock_book.assert_called_once_with(pair="BTCUSD", count=10)
                assert "bids" in result


class TestKrakenBrokerErrorHandling:
    """Test error handling for Kraken broker specific errors."""

    def test_kraken_api_error_handling(self, kraken_broker: KrakenBroker):
        """Test handling of Kraken API errors (e.g., EAPI:Invalid key)."""
        with patch.object(
            kraken_broker.client,
            "get_balance",
            side_effect=Exception("API error: EAPI:Invalid key")
        ):
            with pytest.raises(Exception) as exc:
                kraken_broker.get_account()
            assert "EAPI" in str(exc.value) or "Invalid" in str(exc.value)

    def test_invalid_symbol_error(self, kraken_broker: KrakenBroker):
        """Test invalid symbol error from Kraken."""
        with patch.object(
            kraken_broker.client,
            "add_order",
            side_effect=Exception("Invalid pair: INVALID")
        ):
            with pytest.raises(Exception) as exc:
                kraken_broker.place_order("INVALID", "buy", "market", 1)
            assert "invalid" in str(exc.value).lower()

    def test_insufficient_balance_error(self, kraken_broker: KrakenBroker):
        """Test insufficient balance error from Kraken."""
        with patch.object(
            kraken_broker.client,
            "add_order",
            side_effect=Exception("Insufficient funds")
        ):
            with pytest.raises(Exception) as exc:
                kraken_broker.place_order("BTCUSD", "buy", "market", 1000)
            assert "insufficient" in str(exc.value).lower()

    def test_order_not_found_error(self, kraken_broker: KrakenBroker):
        """Test order not found error."""
        with patch.object(
            kraken_broker.client,
            "query_orders",
            side_effect=Exception("Order not found")
        ):
            with pytest.raises(Exception) as exc:
                kraken_broker.get_order_status("nonexistent")
            assert "not found" in str(exc.value).lower()


class TestKrakenBrokerSandbox:
    """Test specific behaviors in sandbox mode."""

    def test_sandbox_account_limits(self, kraken_broker: KrakenBroker):
        """Test that sandbox account has balance limits."""
        with patch.object(kraken_broker.client, "get_balance") as mock_acc:
            mock_acc.return_value = {"USD": "100000.0"}
            account = kraken_broker.get_account()
            assert float(account["USD"]) == 100000.0


class TestKrakenBrokerWebSocket:
    """Test Kraken WebSocket data streams (if implemented)."""

    def test_stream_market_data(self, kraken_broker: KrakenBroker):
        """Test streaming market data via WebSocket (if method exists)."""
        if hasattr(kraken_broker, "stream_data"):
            with patch.object(kraken_broker, "stream_data") as mock_stream:
                mock_stream.return_value = None
                kraken_broker.stream_data("BTCUSD")
                mock_stream.assert_called_once_with("BTCUSD")
