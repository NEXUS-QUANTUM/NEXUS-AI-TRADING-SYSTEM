"""
tests/integration/test_broker_integration.py

NEXUS AI Trading System - Broker Integration Tests

This test suite verifies the integration of broker adapters with the backend.
It tests:

- Broker factory: creating correct broker instances
- Alpaca broker: account info, positions, orders, error handling
- Binance broker: account info, positions, orders, error handling
- Order conversion: converting internal order models to broker-specific formats
- Response parsing: converting broker responses to internal models
- Error mapping: mapping broker errors to internal error types
- Syncing: fetching and syncing account data from broker

All tests mock the actual broker API calls to ensure deterministic testing.

Copyright © 2026 NEXUS QUANTUM LTD
"""

import pytest
import json
from unittest.mock import patch, MagicMock, PropertyMock
from typing import Dict, Any, List
from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.brokers.base import BaseBroker
from backend.brokers.broker_factory import BrokerFactory
from backend.brokers.alpaca import AlpacaBroker
from backend.brokers.binance import BinanceBroker
from backend.brokers.exceptions import (
    BrokerConnectionError,
    BrokerAuthenticationError,
    BrokerOrderError,
    BrokerSymbolError,
    BrokerInsufficientFundsError,
)
from backend.models.broker_account import BrokerAccount
from backend.models.order import Order
from backend.core.config import settings

from tests.integration.conftest import (
    db_session,
    override_get_db,
    client,
    test_user,
    test_user_token,
    auth_headers,
    test_portfolio,
    test_broker_account,
    mock_alpaca_broker,
    mock_binance_broker,
)


# ----- Fixtures -----

@pytest.fixture
def alpaca_config():
    """Provide test Alpaca configuration."""
    return {
        "api_key": "PK_TEST123",
        "api_secret": "SK_TEST456",
        "paper": True,
        "base_url": "https://paper-api.alpaca.markets",
    }


@pytest.fixture
def binance_config():
    """Provide test Binance configuration."""
    return {
        "api_key": "BINANCE_TEST_KEY",
        "api_secret": "BINANCE_TEST_SECRET",
        "testnet": True,
        "base_url": "https://testnet.binance.vision",
    }


@pytest.fixture
def broker_factory():
    """Return a BrokerFactory instance."""
    return BrokerFactory()


@pytest.fixture
def mock_alpaca_trading_client():
    """Mock the alpaca-trade-api TradingClient."""
    with patch('backend.brokers.alpaca.TradingClient') as mock:
        mock_instance = mock.return_value
        # Set up common responses
        mock_instance.get_account.return_value = MagicMock(
            id="test-account-id",
            cash="100000.00",
            portfolio_value="100000.00",
            buying_power="100000.00",
            equity="100000.00",
            pattern_day_trader=False,
        )
        # Mock position list
        mock_instance.list_positions.return_value = [
            MagicMock(
                symbol="AAPL",
                qty="10",
                avg_entry_price="150.50",
                current_price="155.00",
                unrealized_pl="45.00",
                unrealized_plpc="0.03",
            ),
            MagicMock(
                symbol="MSFT",
                qty="5",
                avg_entry_price="300.00",
                current_price="310.00",
                unrealized_pl="50.00",
                unrealized_plpc="0.033",
            ),
        ]
        # Mock order submission
        mock_order = MagicMock(
            id="order-123",
            symbol="AAPL",
            qty="10",
            side="buy",
            type="market",
            status="filled",
            filled_qty="10",
            filled_avg_price="150.00",
            created_at=datetime.now().isoformat(),
        )
        mock_instance.submit_order.return_value = mock_order
        # Mock cancel order
        mock_instance.cancel_order.return_value = None

        yield mock_instance


@pytest.fixture
def mock_binance_client():
    """Mock the python-binance Client."""
    with patch('backend.brokers.binance.Client') as mock:
        mock_instance = mock.return_value
        # Account info
        mock_instance.get_account.return_value = {
            "balances": [
                {"asset": "BTC", "free": "0.50000000", "locked": "0.10000000"},
                {"asset": "USD", "free": "50000.00000000", "locked": "0.00000000"},
            ],
            "makerCommission": 10,
            "takerCommission": 10,
            "buyerCommission": 0,
            "sellerCommission": 0,
        }
        # Ticker price
        mock_instance.get_symbol_ticker.return_value = {"symbol": "BTCUSDT", "price": "50000.00"}
        # Order placement
        mock_order = {
            "symbol": "BTCUSDT",
            "orderId": 12345,
            "clientOrderId": "test-123",
            "price": "0.00000000",
            "origQty": "0.00100000",
            "executedQty": "0.00100000",
            "status": "FILLED",
            "type": "MARKET",
            "side": "BUY",
            "time": int(datetime.now().timestamp() * 1000),
        }
        mock_instance.create_order.return_value = mock_order
        # Cancel order
        mock_instance.cancel_order.return_value = {"orderId": 12345, "status": "CANCELED"}
        # Order status
        mock_instance.get_order.return_value = mock_order

        yield mock_instance


# ----- Broker Factory Tests -----

class TestBrokerFactory:
    """Test the BrokerFactory class."""

    def test_create_alpaca_broker(self, broker_factory, alpaca_config):
        """Test creating an Alpaca broker instance."""
        broker = broker_factory.create_broker("alpaca", alpaca_config)
        assert isinstance(broker, AlpacaBroker)
        assert broker.api_key == "PK_TEST123"
        assert broker.api_secret == "SK_TEST456"
        assert broker.paper is True

    def test_create_binance_broker(self, broker_factory, binance_config):
        """Test creating a Binance broker instance."""
        broker = broker_factory.create_broker("binance", binance_config)
        assert isinstance(broker, BinanceBroker)
        assert broker.api_key == "BINANCE_TEST_KEY"
        assert broker.api_secret == "BINANCE_TEST_SECRET"
        assert broker.testnet is True

    def test_create_unknown_broker(self, broker_factory):
        """Test creating an unknown broker type."""
        with pytest.raises(ValueError, match="Unsupported broker type: unknown"):
            broker_factory.create_broker("unknown", {})

    def test_broker_registry(self, broker_factory):
        """Test broker registration and listing."""
        registry = broker_factory.get_registered_brokers()
        assert "alpaca" in registry
        assert "binance" in registry
        assert "bybit" in registry


# ----- Alpaca Broker Tests -----

class TestAlpacaBroker:
    """Test the Alpaca broker implementation."""

    def test_init(self, alpaca_config):
        """Test Alpaca broker initialization."""
        broker = AlpacaBroker(alpaca_config)
        assert broker.api_key == "PK_TEST123"
        assert broker.api_secret == "SK_TEST456"
        assert broker.paper is True

    def test_get_account(self, alpaca_config, mock_alpaca_trading_client):
        """Test fetching account information."""
        broker = AlpacaBroker(alpaca_config)
        account = broker.get_account()
        assert account["id"] == "test-account-id"
        assert account["cash"] == "100000.00"
        assert account["portfolio_value"] == "100000.00"
        assert account["buying_power"] == "100000.00"
        mock_alpaca_trading_client.get_account.assert_called_once()

    def test_get_positions(self, alpaca_config, mock_alpaca_trading_client):
        """Test fetching positions."""
        broker = AlpacaBroker(alpaca_config)
        positions = broker.get_positions()
        assert len(positions) == 2
        assert positions[0]["symbol"] == "AAPL"
        assert positions[0]["quantity"] == "10"
        assert positions[0]["avg_entry_price"] == "150.50"
        assert positions[0]["unrealized_pl"] == "45.00"

    def test_place_market_order(self, alpaca_config, mock_alpaca_trading_client):
        """Test placing a market order."""
        broker = AlpacaBroker(alpaca_config)
        order = broker.place_order(
            symbol="AAPL",
            side="buy",
            quantity=10,
            order_type="market",
        )
        assert order["id"] == "order-123"
        assert order["symbol"] == "AAPL"
        assert order["side"] == "buy"
        assert order["status"] == "filled"
        assert order["filled_quantity"] == "10"
        mock_alpaca_trading_client.submit_order.assert_called_once()

    def test_place_limit_order(self, alpaca_config, mock_alpaca_trading_client):
        """Test placing a limit order."""
        broker = AlpacaBroker(alpaca_config)
        order = broker.place_order(
            symbol="AAPL",
            side="sell",
            quantity=5,
            order_type="limit",
            limit_price=160.0,
        )
        assert order["id"] == "order-123"
        # We can verify that the order request had limit_price set
        call_args = mock_alpaca_trading_client.submit_order.call_args[0][0]
        assert call_args.limit_price == "160.0"
        assert call_args.type == "limit"

    def test_place_stop_order(self, alpaca_config, mock_alpaca_trading_client):
        """Test placing a stop order."""
        broker = AlpacaBroker(alpaca_config)
        order = broker.place_order(
            symbol="AAPL",
            side="buy",
            quantity=5,
            order_type="stop",
            stop_price=155.0,
        )
        call_args = mock_alpaca_trading_client.submit_order.call_args[0][0]
        assert call_args.stop_price == "155.0"
        assert call_args.type == "stop"

    def test_cancel_order(self, alpaca_config, mock_alpaca_trading_client):
        """Test cancelling an order."""
        broker = AlpacaBroker(alpaca_config)
        result = broker.cancel_order("order-123")
        assert result is None  # Success
        mock_alpaca_trading_client.cancel_order.assert_called_once_with("order-123")

    def test_get_order(self, alpaca_config, mock_alpaca_trading_client):
        """Test fetching order status."""
        broker = AlpacaBroker(alpaca_config)
        order = broker.get_order("order-123")
        assert order["id"] == "order-123"
        assert order["status"] == "filled"
        mock_alpaca_trading_client.get_order.assert_called_once_with("order-123")

    def test_get_order_not_found(self, alpaca_config, mock_alpaca_trading_client):
        """Test fetching a non-existent order."""
        mock_alpaca_trading_client.get_order.side_effect = Exception("Order not found")
        broker = AlpacaBroker(alpaca_config)
        with pytest.raises(BrokerOrderError, match="Order not found"):
            broker.get_order("invalid-id")

    def test_connection_error(self, alpaca_config, mock_alpaca_trading_client):
        """Test handling of connection errors."""
        mock_alpaca_trading_client.get_account.side_effect = Exception("Connection timeout")
        broker = AlpacaBroker(alpaca_config)
        with pytest.raises(BrokerConnectionError, match="Connection timeout"):
            broker.get_account()

    def test_insufficient_funds(self, alpaca_config, mock_alpaca_trading_client):
        """Test handling of insufficient funds error."""
        # Alpaca may raise a specific error
        from alpaca.trading.exceptions import APIError
        mock_alpaca_trading_client.submit_order.side_effect = APIError(
            message="Insufficient buying power",
            status_code=422,
        )
        broker = AlpacaBroker(alpaca_config)
        with pytest.raises(BrokerInsufficientFundsError, match="Insufficient buying power"):
            broker.place_order(symbol="AAPL", side="buy", quantity=1000000, order_type="market")

    def test_invalid_symbol(self, alpaca_config, mock_alpaca_trading_client):
        """Test handling of invalid symbol error."""
        from alpaca.trading.exceptions import APIError
        mock_alpaca_trading_client.submit_order.side_effect = APIError(
            message="Invalid symbol: INVALID",
            status_code=400,
        )
        broker = AlpacaBroker(alpaca_config)
        with pytest.raises(BrokerSymbolError, match="Invalid symbol"):
            broker.place_order(symbol="INVALID", side="buy", quantity=1, order_type="market")

    def test_map_internal_order_to_alpaca(self, alpaca_config):
        """Test converting internal order to Alpaca request."""
        broker = AlpacaBroker(alpaca_config)
        internal_order = {
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 10,
            "order_type": "limit",
            "limit_price": 150.0,
        }
        alpaca_order = broker._map_to_alpaca_order(internal_order)
        assert alpaca_order.symbol == "AAPL"
        assert alpaca_order.side == "buy"
        assert alpaca_order.qty == "10"
        assert alpaca_order.type == "limit"
        assert alpaca_order.limit_price == "150.0"

    def test_parse_alpaca_order_to_internal(self, alpaca_config):
        """Test parsing Alpaca order response to internal model."""
        broker = AlpacaBroker(alpaca_config)
        alpaca_order = MagicMock(
            id="order-123",
            symbol="AAPL",
            side="buy",
            type="market",
            status="filled",
            filled_qty="10",
            filled_avg_price="150.00",
            created_at=datetime.now().isoformat(),
        )
        internal = broker._parse_alpaca_order(alpaca_order)
        assert internal["id"] == "order-123"
        assert internal["symbol"] == "AAPL"
        assert internal["side"] == "buy"
        assert internal["status"] == "filled"
        assert internal["filled_quantity"] == "10"
        assert internal["filled_price"] == "150.00"


# ----- Binance Broker Tests -----

class TestBinanceBroker:
    """Test the Binance broker implementation."""

    def test_init(self, binance_config):
        """Test Binance broker initialization."""
        broker = BinanceBroker(binance_config)
        assert broker.api_key == "BINANCE_TEST_KEY"
        assert broker.api_secret == "BINANCE_TEST_SECRET"
        assert broker.testnet is True

    def test_get_account(self, binance_config, mock_binance_client):
        """Test fetching account information."""
        broker = BinanceBroker(binance_config)
        account = broker.get_account()
        assert "balances" in account
        assert account["balances"]["BTC"] == {"free": 0.5, "locked": 0.1}
        assert account["balances"]["USD"] == {"free": 50000.0, "locked": 0.0}
        mock_binance_client.get_account.assert_called_once()

    def test_get_positions(self, binance_config, mock_binance_client):
        """Test fetching positions (for Binance, we consider balances)."""
        broker = BinanceBroker(binance_config)
        # Binance doesn't have positions in the same sense; we compute from balances
        positions = broker.get_positions()
        # Should return only non-zero balances of tradeable assets
        # For BTC, we have 0.5 free, so a position
        assert len(positions) >= 1
        btc_position = next((p for p in positions if p["symbol"] == "BTC"), None)
        assert btc_position is not None
        assert btc_position["quantity"] == 0.5
        assert btc_position["free"] == 0.5
        assert btc_position["locked"] == 0.1

    def test_place_market_order(self, binance_config, mock_binance_client):
        """Test placing a market order."""
        broker = BinanceBroker(binance_config)
        order = broker.place_order(
            symbol="BTCUSDT",
            side="buy",
            quantity=0.001,
            order_type="market",
        )
        assert order["id"] == 12345
        assert order["symbol"] == "BTCUSDT"
        assert order["side"] == "buy"
        assert order["status"] == "filled"
        mock_binance_client.create_order.assert_called_once()

    def test_place_limit_order(self, binance_config, mock_binance_client):
        """Test placing a limit order."""
        broker = BinanceBroker(binance_config)
        order = broker.place_order(
            symbol="BTCUSDT",
            side="sell",
            quantity=0.001,
            order_type="limit",
            limit_price=51000.0,
        )
        call_args = mock_binance_client.create_order.call_args[1]
        assert call_args["symbol"] == "BTCUSDT"
        assert call_args["side"] == "SELL"
        assert call_args["type"] == "LIMIT"
        assert call_args["price"] == "51000.00"
        assert call_args["quantity"] == "0.001"

    def test_place_stop_order(self, binance_config, mock_binance_client):
        """Test placing a stop order (stop-loss)."""
        broker = BinanceBroker(binance_config)
        order = broker.place_order(
            symbol="BTCUSDT",
            side="buy",
            quantity=0.001,
            order_type="stop",
            stop_price=49000.0,
        )
        call_args = mock_binance_client.create_order.call_args[1]
        assert call_args["type"] == "STOP_LOSS_LIMIT"  # Binance uses STOP_LOSS_LIMIT
        assert call_args["stopPrice"] == "49000.00"

    def test_cancel_order(self, binance_config, mock_binance_client):
        """Test cancelling an order."""
        broker = BinanceBroker(binance_config)
        result = broker.cancel_order("12345")
        assert result["orderId"] == 12345
        assert result["status"] == "CANCELED"
        mock_binance_client.cancel_order.assert_called_once_with(symbol="BTCUSDT", orderId=12345)

    def test_get_order(self, binance_config, mock_binance_client):
        """Test fetching order status."""
        broker = BinanceBroker(binance_config)
        order = broker.get_order("12345")
        assert order["orderId"] == 12345
        assert order["status"] == "FILLED"
        mock_binance_client.get_order.assert_called_once_with(symbol="BTCUSDT", orderId=12345)

    def test_connection_error(self, binance_config, mock_binance_client):
        """Test handling of connection errors."""
        from binance.exceptions import BinanceAPIException
        mock_binance_client.get_account.side_effect = BinanceAPIException({"code": -1000, "msg": "Connection error"})
        broker = BinanceBroker(binance_config)
        with pytest.raises(BrokerConnectionError, match="Connection error"):
            broker.get_account()

    def test_authentication_error(self, binance_config, mock_binance_client):
        """Test authentication error (invalid API key)."""
        from binance.exceptions import BinanceAPIException
        mock_binance_client.get_account.side_effect = BinanceAPIException({"code": -2015, "msg": "Invalid API-key"})
        broker = BinanceBroker(binance_config)
        with pytest.raises(BrokerAuthenticationError, match="Invalid API-key"):
            broker.get_account()

    def test_insufficient_funds(self, binance_config, mock_binance_client):
        """Test insufficient funds error."""
        from binance.exceptions import BinanceAPIException
        mock_binance_client.create_order.side_effect = BinanceAPIException({"code": -2010, "msg": "Account has insufficient balance"})
        broker = BinanceBroker(binance_config)
        with pytest.raises(BrokerInsufficientFundsError, match="insufficient balance"):
            broker.place_order(symbol="BTCUSDT", side="buy", quantity=1000, order_type="market")

    def test_symbol_not_found(self, binance_config, mock_binance_client):
        """Test invalid symbol error."""
        from binance.exceptions import BinanceAPIException
        mock_binance_client.create_order.side_effect = BinanceAPIException({"code": -1121, "msg": "Invalid symbol"})
        broker = BinanceBroker(binance_config)
        with pytest.raises(BrokerSymbolError, match="Invalid symbol"):
            broker.place_order(symbol="INVALID", side="buy", quantity=1, order_type="market")


# ----- Broker Integration with API Endpoints -----

class TestBrokerAPIEndpoints:
    """Test broker-related API endpoints with mock broker."""

    def test_connect_broker_endpoint(self, client: TestClient, auth_headers: Dict, test_user: User):
        """Test POST /api/v1/brokers/connect with valid config."""
        payload = {
            "broker_type": "alpaca",
            "api_key": "PK_TEST_KEY",
            "api_secret": "SK_TEST_SECRET",
            "paper_trading": True,
        }
        response = client.post("/api/v1/brokers/connect", json=payload, headers=auth_headers)
        assert response.status_code == 201
        data = response.json()
        assert data["broker_type"] == "alpaca"
        assert data["is_active"] is True
        assert data["is_paper"] is True
        assert "id" in data

    def test_connect_broker_invalid_credentials(self, client: TestClient, auth_headers: Dict):
        """Test connecting with invalid broker credentials (mock auth error)."""
        with patch('backend.brokers.alpaca.TradingClient') as mock_trading:
            mock_trading.side_effect = Exception("Authentication failed")
            payload = {
                "broker_type": "alpaca",
                "api_key": "invalid",
                "api_secret": "invalid",
                "paper_trading": True,
            }
            response = client.post("/api/v1/brokers/connect", json=payload, headers=auth_headers)
            assert response.status_code == 401
            data = response.json()
            assert "authentication" in data["detail"].lower() or "credentials" in data["detail"].lower()

    def test_sync_broker_endpoint(self, client: TestClient, auth_headers: Dict, test_broker_account: BrokerAccount, mock_alpaca_trading_client):
        """Test POST /api/v1/brokers/{broker_id}/sync."""
        response = client.post(f"/api/v1/brokers/{test_broker_account.id}/sync", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "synced"
        # Should have updated portfolio positions
        # Check if positions were created/updated
        db = next(override_get_db())
        positions = db.query(Position).filter(Position.broker_account_id == test_broker_account.id).all()
        assert len(positions) >= 1
        # Should have AAPL and MSFT from mock
        symbols = [p.symbol for p in positions]
        assert "AAPL" in symbols
        assert "MSFT" in symbols

    def test_disconnect_broker_endpoint(self, client: TestClient, auth_headers: Dict, test_broker_account: BrokerAccount):
        """Test DELETE /api/v1/brokers/{broker_id}."""
        response = client.delete(f"/api/v1/brokers/{test_broker_account.id}", headers=auth_headers)
        assert response.status_code == 204
        # Verify deactivated
        db = next(override_get_db())
        account = db.query(BrokerAccount).filter(BrokerAccount.id == test_broker_account.id).first()
        assert account is None or account.is_active is False


# ----- Broker Configuration Tests -----

class TestBrokerConfiguration:
    """Test broker configuration loading and validation."""

    def test_load_config_alpaca(self):
        """Test loading Alpaca configuration from environment."""
        # We can simulate settings
        with patch('backend.core.config.settings') as mock_settings:
            mock_settings.ALPACA_API_KEY = "ENV_KEY"
            mock_settings.ALPACA_SECRET_KEY = "ENV_SECRET"
            mock_settings.ALPACA_PAPER = True
            from backend.brokers.alpaca import get_alpaca_config
            config = get_alpaca_config()
            assert config["api_key"] == "ENV_KEY"
            assert config["api_secret"] == "ENV_SECRET"
            assert config["paper"] is True

    def test_load_config_binance(self):
        """Test loading Binance configuration from environment."""
        with patch('backend.core.config.settings') as mock_settings:
            mock_settings.BINANCE_API_KEY = "ENV_BINANCE_KEY"
            mock_settings.BINANCE_SECRET_KEY = "ENV_BINANCE_SECRET"
            mock_settings.BINANCE_TESTNET = True
            from backend.brokers.binance import get_binance_config
            config = get_binance_config()
            assert config["api_key"] == "ENV_BINANCE_KEY"
            assert config["api_secret"] == "ENV_BINANCE_SECRET"
            assert config["testnet"] is True


# ----- Broker Error Mapping Tests -----

class TestBrokerErrorMapping:
    """Test mapping of broker-specific errors to common exceptions."""

    def test_alpaca_error_mapping(self, alpaca_config):
        """Test mapping Alpaca APIError to common exceptions."""
        from alpaca.trading.exceptions import APIError
        broker = AlpacaBroker(alpaca_config)
        # Insufficient funds
        with pytest.raises(BrokerInsufficientFundsError):
            broker._handle_error(APIError(message="Insufficient buying power", status_code=422))
        # Invalid symbol
        with pytest.raises(BrokerSymbolError):
            broker._handle_error(APIError(message="Invalid symbol: XYZ", status_code=400))
        # Authentication
        with pytest.raises(BrokerAuthenticationError):
            broker._handle_error(APIError(message="Invalid API key", status_code=401))
        # General order error
        with pytest.raises(BrokerOrderError):
            broker._handle_error(APIError(message="Order rejected", status_code=403))

    def test_binance_error_mapping(self, binance_config):
        """Test mapping Binance APIException to common exceptions."""
        from binance.exceptions import BinanceAPIException
        broker = BinanceBroker(binance_config)
        # Insufficient funds
        with pytest.raises(BrokerInsufficientFundsError):
            broker._handle_error(BinanceAPIException({"code": -2010, "msg": "Account has insufficient balance"}))
        # Invalid symbol
        with pytest.raises(BrokerSymbolError):
            broker._handle_error(BinanceAPIException({"code": -1121, "msg": "Invalid symbol"}))
        # Authentication
        with pytest.raises(BrokerAuthenticationError):
            broker._handle_error(BinanceAPIException({"code": -2015, "msg": "Invalid API-key"}))
        # General order error
        with pytest.raises(BrokerOrderError):
            broker._handle_error(BinanceAPIException({"code": -1100, "msg": "Order failed"}))
