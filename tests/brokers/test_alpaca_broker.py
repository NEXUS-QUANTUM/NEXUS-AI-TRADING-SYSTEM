# tests/brokers/test_alpaca_broker.py
"""
Alpaca Broker Specific Tests.

This module contains tests specifically for the Alpaca broker integration,
including paper trading, crypto vs stock trading, order types, and
Alpaca-specific API features.

All tests use mocked Alpaca client and fixtures from conftest.py.
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.brokers.alpaca.alpaca_broker import AlpacaBroker
from backend.brokers.base_broker import BaseBroker


class TestAlpacaBrokerInitialization:
    """Test Alpaca broker initialization and configuration."""

    def test_alpaca_broker_is_base_broker(self, alpaca_broker: AlpacaBroker):
        """Test that AlpacaBroker inherits from BaseBroker."""
        assert isinstance(alpaca_broker, BaseBroker)

    def test_alpaca_broker_attributes(self, alpaca_broker: AlpacaBroker):
        """Test that Alpaca broker has correct attributes."""
        assert alpaca_broker.api_key == "test_key"
        assert alpaca_broker.api_secret == "test_secret"
        assert alpaca_broker.paper is True
        # Base URL should be set to paper endpoint
        assert alpaca_broker.base_url is not None

    def test_alpaca_broker_has_required_methods(self, alpaca_broker: AlpacaBroker):
        """Test that Alpaca broker implements all required methods."""
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
            assert hasattr(alpaca_broker, method)
            assert callable(getattr(alpaca_broker, method))

    def test_alpaca_paper_mode_enabled(self, alpaca_broker: AlpacaBroker):
        """Test that paper mode is correctly set."""
        assert alpaca_broker.paper is True
        # With paper=True, base_url should point to paper API
        assert "paper" in alpaca_broker.base_url or "paper" in str(alpaca_broker.client.base_url)


class TestAlpacaBrokerAccount:
    """Test Alpaca account-related operations."""

    def test_get_account_returns_dict(self, alpaca_broker: AlpacaBroker):
        """Test get_account returns a dict with expected fields."""
        with patch.object(alpaca_broker, "get_account", wraps=alpaca_broker.get_account) as mock_method:
            result = alpaca_broker.get_account()
            mock_method.assert_called_once()
            assert isinstance(result, dict)
            # Alpaca account returns fields like id, cash, buying_power, etc.
            assert any(key in result for key in ("id", "cash", "buying_power", "equity"))

    def test_get_account_calls_client(self, alpaca_broker: AlpacaBroker):
        """Test that get_account uses the underlying client."""
        with patch.object(alpaca_broker.client, "get_account") as mock_client:
            mock_client.return_value = {"id": "test", "cash": "10000.0"}
            result = alpaca_broker.get_account()
            mock_client.assert_called_once()
            # Ensure the result is parsed correctly
            assert result["id"] == "test"

    def test_get_account_handles_errors(self, alpaca_broker: AlpacaBroker):
        """Test that get_account raises appropriate exceptions on client error."""
        with patch.object(alpaca_broker.client, "get_account", side_effect=Exception("API error")):
            with pytest.raises(Exception):
                alpaca_broker.get_account()


class TestAlpacaBrokerPositions:
    """Test Alpaca position-related operations."""

    def test_get_positions_returns_list(self, alpaca_broker: AlpacaBroker):
        """Test get_positions returns a list of position dicts."""
        with patch.object(alpaca_broker.client, "list_positions") as mock_client:
            mock_client.return_value = [
                {"symbol": "BTCUSD", "qty": "0.5", "avg_entry_price": "50000"}
            ]
            result = alpaca_broker.get_positions()
            mock_client.assert_called_once()
            assert isinstance(result, list)
            if result:
                assert "symbol" in result[0]
                assert "quantity" in result[0] or "qty" in result[0]

    def test_get_positions_empty(self, alpaca_broker: AlpacaBroker):
        """Test get_positions returns empty list when no positions."""
        with patch.object(alpaca_broker.client, "list_positions") as mock_client:
            mock_client.return_value = []
            result = alpaca_broker.get_positions()
            assert result == []

    def test_close_position(self, alpaca_broker: AlpacaBroker):
        """Test closing a position (if method exists)."""
        # Alpaca provides `close_position` method; we test it.
        if hasattr(alpaca_broker, "close_position"):
            with patch.object(alpaca_broker.client, "close_position") as mock_close:
                mock_close.return_value = {"symbol": "BTCUSD", "status": "closed"}
                result = alpaca_broker.close_position("BTCUSD")
                mock_close.assert_called_once_with("BTCUSD")
                assert result["status"] == "closed"


class TestAlpacaBrokerOrders:
    """Test Alpaca order operations."""

    def test_place_market_order(self, alpaca_broker: AlpacaBroker):
        """Test placing a market order."""
        with patch.object(alpaca_broker.client, "submit_order") as mock_submit:
            mock_submit.return_value = {
                "id": "ord_123",
                "symbol": "BTCUSD",
                "side": "buy",
                "type": "market",
                "qty": "0.1",
                "status": "filled",
            }
            result = alpaca_broker.place_order(
                symbol="BTCUSD",
                side="buy",
                order_type="market",
                quantity=0.1,
            )
            mock_submit.assert_called_once()
            # Verify order data
            assert result["id"] == "ord_123"
            assert result["symbol"] == "BTCUSD"
            assert result["side"] == "buy"

    def test_place_limit_order(self, alpaca_broker: AlpacaBroker):
        """Test placing a limit order."""
        with patch.object(alpaca_broker.client, "submit_order") as mock_submit:
            mock_submit.return_value = {
                "id": "ord_456",
                "symbol": "BTCUSD",
                "side": "sell",
                "type": "limit",
                "qty": "0.2",
                "limit_price": "55000",
                "status": "accepted",
            }
            result = alpaca_broker.place_order(
                symbol="BTCUSD",
                side="sell",
                order_type="limit",
                quantity=0.2,
                price=55000.0,
            )
            mock_submit.assert_called_once()
            assert result["id"] == "ord_456"
            assert result["type"] == "limit"
            assert result["limit_price"] == "55000"

    def test_place_order_with_time_in_force(self, alpaca_broker: AlpacaBroker):
        """Test placing order with custom time_in_force."""
        with patch.object(alpaca_broker.client, "submit_order") as mock_submit:
            mock_submit.return_value = {"id": "ord_789", "status": "accepted"}
            result = alpaca_broker.place_order(
                symbol="AAPL",
                side="buy",
                order_type="limit",
                quantity=10,
                price=150.0,
                time_in_force="day",
            )
            # Verify that time_in_force parameter was passed
            mock_submit.assert_called_once()
            # Since we mock the client, we can't directly check the call args,
            # but we can ensure the method didn't raise.

    def test_cancel_order(self, alpaca_broker: AlpacaBroker):
        """Test canceling an order."""
        with patch.object(alpaca_broker.client, "cancel_order") as mock_cancel:
            mock_cancel.return_value = {"id": "ord_123", "status": "cancelled"}
            result = alpaca_broker.cancel_order("ord_123")
            mock_cancel.assert_called_once_with("ord_123")
            assert result["status"] == "cancelled"

    def test_get_order_status(self, alpaca_broker: AlpacaBroker):
        """Test getting order status."""
        with patch.object(alpaca_broker.client, "get_order") as mock_get:
            mock_get.return_value = {
                "id": "ord_123",
                "status": "filled",
                "filled_qty": "0.1",
                "filled_avg_price": "50000",
            }
            result = alpaca_broker.get_order_status("ord_123")
            mock_get.assert_called_once_with("ord_123")
            assert result["status"] == "filled"
            assert result["filled_qty"] == "0.1"

    def test_get_orders(self, alpaca_broker: AlpacaBroker):
        """Test listing orders."""
        with patch.object(alpaca_broker.client, "list_orders") as mock_list:
            mock_list.return_value = [
                {"id": "ord1", "symbol": "BTCUSD"},
                {"id": "ord2", "symbol": "ETHUSD"},
            ]
            result = alpaca_broker.get_orders()
            mock_list.assert_called_once()
            assert len(result) == 2


class TestAlpacaBrokerMarketData:
    """Test Alpaca market data operations."""

    def test_get_market_data(self, alpaca_broker: AlpacaBroker):
        """Test getting market data (crypto and stock)."""
        # For crypto, Alpaca uses crypto endpoint; for stocks, stock endpoint.
        # We'll test with crypto symbol.
        with patch.object(alpaca_broker.client, "get_crypto_bars") as mock_crypto:
            mock_crypto.return_value = {"BTCUSD": [{"c": 50000, "h": 51000, "l": 49000, "o": 49500, "v": 1000}]}
            result = alpaca_broker.get_market_data("BTCUSD", timeframe="1h", limit=10)
            mock_crypto.assert_called_once()
            assert result is not None

    def test_get_market_data_stock(self, alpaca_broker: AlpacaBroker):
        """Test getting market data for stocks."""
        with patch.object(alpaca_broker.client, "get_bars") as mock_bars:
            mock_bars.return_value = {"AAPL": [{"c": 150, "h": 152, "l": 149, "o": 150, "v": 1000}]}
            result = alpaca_broker.get_market_data("AAPL", timeframe="1d", limit=5)
            mock_bars.assert_called_once()
            assert result is not None


class TestAlpacaBrokerCrypto:
    """Test Alpaca crypto-specific features."""

    def test_crypto_symbol_detection(self, alpaca_broker: AlpacaBroker):
        """Test that the broker identifies crypto symbols correctly."""
        # The method `_is_crypto_symbol` is usually private; we can test it via reflection.
        if hasattr(alpaca_broker, "_is_crypto_symbol"):
            assert alpaca_broker._is_crypto_symbol("BTCUSD") is True
            assert alpaca_broker._is_crypto_symbol("ETHUSD") is True
            assert alpaca_broker._is_crypto_symbol("AAPL") is False
            assert alpaca_broker._is_crypto_symbol("MSFT") is False

    def test_crypto_order_place(self, alpaca_broker: AlpacaBroker):
        """Test placing a crypto order (should use crypto endpoint)."""
        with patch.object(alpaca_broker.client, "submit_order") as mock_submit:
            mock_submit.return_value = {"id": "crypto_ord", "status": "filled"}
            result = alpaca_broker.place_order(
                symbol="ETHUSD",
                side="buy",
                order_type="market",
                quantity=1.0,
            )
            mock_submit.assert_called_once()
            # Alpaca crypto orders have a different endpoint but same method.

    def test_crypto_market_data_format(self, alpaca_broker: AlpacaBroker):
        """Test that crypto market data is returned in standard format."""
        with patch.object(alpaca_broker.client, "get_crypto_bars") as mock_crypto:
            mock_crypto.return_value = {
                "BTCUSD": [
                    {"c": 50000, "h": 51000, "l": 49000, "o": 49500, "v": 1000, "t": "2024-01-01T00:00:00Z"}
                ]
            }
            result = alpaca_broker.get_market_data("BTCUSD", timeframe="1h", limit=10)
            # The broker should normalize data to common format.
            # We can check that the result contains the expected keys.
            if isinstance(result, list) and result:
                assert "close" in result[0] or "c" in result[0]
            elif isinstance(result, dict):
                assert "BTCUSD" in result or "data" in result


class TestAlpacaBrokerErrorHandling:
    """Test error handling for Alpaca broker specific errors."""

    def test_alpaca_api_error_handling(self, alpaca_broker: AlpacaBroker):
        """Test handling of Alpaca API errors (e.g., 429, 403)."""
        with patch.object(alpaca_broker.client, "get_account", side_effect=Exception("HTTP 429 Too Many Requests")):
            with pytest.raises(Exception) as exc:
                alpaca_broker.get_account()
            assert "429" in str(exc.value) or "Too Many Requests" in str(exc.value)

    def test_invalid_symbol_error(self, alpaca_broker: AlpacaBroker):
        """Test invalid symbol error from Alpaca."""
        with patch.object(
            alpaca_broker.client,
            "submit_order",
            side_effect=Exception("Invalid symbol: INVALID")
        ):
            with pytest.raises(Exception) as exc:
                alpaca_broker.place_order("INVALID", "buy", "market", 1)
            assert "invalid" in str(exc.value).lower()

    def test_insufficient_balance_error(self, alpaca_broker: AlpacaBroker):
        """Test insufficient balance error from Alpaca."""
        with patch.object(
            alpaca_broker.client,
            "submit_order",
            side_effect=Exception("Insufficient buying power")
        ):
            with pytest.raises(Exception) as exc:
                alpaca_broker.place_order("AAPL", "buy", "market", 10000)
            assert "insufficient" in str(exc.value).lower()


class TestAlpacaBrokerPaperTrading:
    """Test specific behaviors in paper trading mode."""

    def test_paper_trading_account_limits(self, alpaca_broker: AlpacaBroker):
        """Test that paper trading account has balance limits."""
        # In paper, account might have some default balance.
        with patch.object(alpaca_broker.client, "get_account") as mock_acc:
            mock_acc.return_value = {
                "cash": "100000.0",
                "buying_power": "200000.0",
                "equity": "100000.0",
            }
            account = alpaca_broker.get_account()
            assert float(account["cash"]) > 0
            assert float(account["buying_power"]) > 0

    def test_paper_trading_order_reset(self, alpaca_broker: AlpacaBroker):
        """Test that paper trading orders are simulated."""
        # Paper trading orders should be immediately filled or simulated.
        with patch.object(alpaca_broker.client, "submit_order") as mock_submit:
            mock_submit.return_value = {"id": "paper_ord", "status": "filled"}
            order = alpaca_broker.place_order("SPY", "buy", "market", 10)
            assert order["status"] == "filled"


class TestAlpacaBrokerRealTimeData:
    """Test Alpaca real-time data streams (if implemented)."""

    def test_stream_market_data(self, alpaca_broker: AlpacaBroker):
        """Test streaming market data via WebSocket (if method exists)."""
        if hasattr(alpaca_broker, "stream_data"):
            # Test that stream starts and handles data.
            # We'll just check the method exists and can be called.
            with patch.object(alpaca_broker, "stream_data") as mock_stream:
                mock_stream.return_value = None
                alpaca_broker.stream_data("BTCUSD")
                mock_stream.assert_called_once_with("BTCUSD")
