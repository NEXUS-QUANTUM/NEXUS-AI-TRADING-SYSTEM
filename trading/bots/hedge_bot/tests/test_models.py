# trading/bots/hedge_bot/tests/test_models.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Model Tests
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Model Tests

This module provides comprehensive tests for the data models used in the
NEXUS Hedge Bot system. It covers all model classes, their validation,
serialization, and database operations.

The test suite covers:
- Position models
- Order models
- Trade models
- Portfolio models
- Risk models
- Strategy models
- Market data models
- User models
- Configuration models
- Validation and serialization
"""

import os
import sys
import json
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

import pytest
from pydantic import ValidationError

# Import models under test
from trading.bots.hedge_bot.models.position import Position, PositionSide, PositionStatus
from trading.bots.hedge_bot.models.order import Order, OrderSide, OrderType, OrderStatus, TimeInForce
from trading.bots.hedge_bot.models.trade import Trade, TradeSide, TradeStatus
from trading.bots.hedge_bot.models.portfolio import Portfolio, PortfolioMetrics, Allocation
from trading.bots.hedge_bot.models.risk import RiskMetrics, VaR, CVaR, Drawdown
from trading.bots.hedge_bot.models.strategy import Strategy, StrategyType, StrategyStatus, StrategyParameters
from trading.bots.hedge_bot.models.market import MarketData, OHLCV, Ticker, OrderBook
from trading.bots.hedge_bot.models.user import User, UserRole, UserPreferences
from trading.bots.hedge_bot.models.config import BotConfig, ExchangeConfig, TradingConfig

# ============================================================
# TEST FIXTURES
# ============================================================

@pytest.fixture
def sample_position_data() -> Dict[str, Any]:
    """Create sample position data"""
    return {
        "id": str(uuid.uuid4()),
        "symbol": "BTC/USDT",
        "side": PositionSide.LONG,
        "quantity": Decimal("1.0"),
        "entry_price": Decimal("50000.0"),
        "current_price": Decimal("52000.0"),
        "unrealized_pnl": Decimal("2000.0"),
        "realized_pnl": Decimal("500.0"),
        "status": PositionStatus.OPEN,
        "created_at": datetime.now() - timedelta(days=7),
        "updated_at": datetime.now(),
    }


@pytest.fixture
def sample_order_data() -> Dict[str, Any]:
    """Create sample order data"""
    return {
        "id": str(uuid.uuid4()),
        "symbol": "BTC/USDT",
        "side": OrderSide.BUY,
        "type": OrderType.LIMIT,
        "quantity": Decimal("1.0"),
        "price": Decimal("50000.0"),
        "stop_price": None,
        "filled_quantity": Decimal("0.5"),
        "status": OrderStatus.PARTIALLY_FILLED,
        "time_in_force": TimeInForce.GTC,
        "client_order_id": "client_123456",
        "created_at": datetime.now() - timedelta(hours=1),
        "updated_at": datetime.now(),
    }


@pytest.fixture
def sample_trade_data() -> Dict[str, Any]:
    """Create sample trade data"""
    return {
        "id": str(uuid.uuid4()),
        "order_id": str(uuid.uuid4()),
        "symbol": "BTC/USDT",
        "side": TradeSide.BUY,
        "quantity": Decimal("1.0"),
        "price": Decimal("50000.0"),
        "fee": Decimal("50.0"),
        "fee_currency": "USDT",
        "pnl": Decimal("0.0"),
        "status": TradeStatus.COMPLETED,
        "executed_at": datetime.now() - timedelta(minutes=30),
    }


@pytest.fixture
def sample_portfolio_data() -> Dict[str, Any]:
    """Create sample portfolio data"""
    return {
        "id": str(uuid.uuid4()),
        "name": "Test Portfolio",
        "currency": "USD",
        "initial_balance": Decimal("100000.0"),
        "current_balance": Decimal("125000.0"),
        "total_pnl": Decimal("25000.0"),
        "total_pnl_percent": Decimal("0.25"),
        "daily_pnl": Decimal("1500.0"),
        "daily_pnl_percent": Decimal("0.012"),
        "created_at": datetime.now() - timedelta(days=30),
        "updated_at": datetime.now(),
    }


@pytest.fixture
def sample_risk_metrics_data() -> Dict[str, Any]:
    """Create sample risk metrics data"""
    return {
        "portfolio_id": str(uuid.uuid4()),
        "var_95": Decimal("25000.0"),
        "var_99": Decimal("40000.0"),
        "cvar_95": Decimal("35000.0"),
        "expected_shortfall": Decimal("32000.0"),
        "max_drawdown": Decimal("0.08"),
        "current_drawdown": Decimal("0.02"),
        "sharpe_ratio": Decimal("1.85"),
        "sortino_ratio": Decimal("2.10"),
        "calmar_ratio": Decimal("1.65"),
        "timestamp": datetime.now(),
    }


# ============================================================
# POSITION MODEL TESTS
# ============================================================

class TestPositionModel:
    """
    Tests for Position model
    """

    def test_position_creation(self, sample_position_data: Dict[str, Any]) -> None:
        """Test position creation"""
        position = Position(**sample_position_data)
        assert position.id is not None
        assert position.symbol == "BTC/USDT"
        assert position.side == PositionSide.LONG
        assert position.quantity == Decimal("1.0")
        assert position.entry_price == Decimal("50000.0")
        assert position.status == PositionStatus.OPEN

    def test_position_validation(self) -> None:
        """Test position validation"""
        # Invalid quantity (negative)
        with pytest.raises(ValidationError):
            Position(
                symbol="BTC/USDT",
                side=PositionSide.LONG,
                quantity=Decimal("-1.0"),
                entry_price=Decimal("50000.0"),
            )
        
        # Invalid price (zero)
        with pytest.raises(ValidationError):
            Position(
                symbol="BTC/USDT",
                side=PositionSide.LONG,
                quantity=Decimal("1.0"),
                entry_price=Decimal("0.0"),
            )
        
        # Invalid symbol (empty)
        with pytest.raises(ValidationError):
            Position(
                symbol="",
                side=PositionSide.LONG,
                quantity=Decimal("1.0"),
                entry_price=Decimal("50000.0"),
            )

    def test_position_calculations(self, sample_position_data: Dict[str, Any]) -> None:
        """Test position calculations"""
        position = Position(**sample_position_data)
        
        # Test value calculation
        assert position.value == Decimal("52000.0")
        
        # Test PnL calculation
        assert position.unrealized_pnl == Decimal("2000.0")
        
        # Test PnL percentage
        pnl_percent = position.unrealized_pnl / (position.entry_price * position.quantity)
        assert position.unrealized_pnl_percent == pnl_percent

    def test_position_short_calculations(self) -> None:
        """Test short position calculations"""
        position = Position(
            symbol="BTC/USDT",
            side=PositionSide.SHORT,
            quantity=Decimal("1.0"),
            entry_price=Decimal("50000.0"),
            current_price=Decimal("48000.0"),
        )
        
        # Test value calculation
        assert position.value == Decimal("48000.0")
        
        # Test PnL calculation (short profit when price drops)
        assert position.unrealized_pnl == Decimal("2000.0")

    def test_position_status_update(self, sample_position_data: Dict[str, Any]) -> None:
        """Test position status update"""
        position = Position(**sample_position_data)
        assert position.status == PositionStatus.OPEN
        
        position.status = PositionStatus.CLOSED
        assert position.status == PositionStatus.CLOSED
        
        position.status = PositionStatus.LIQUIDATED
        assert position.status == PositionStatus.LIQUIDATED

    def test_position_serialization(self, sample_position_data: Dict[str, Any]) -> None:
        """Test position serialization"""
        position = Position(**sample_position_data)
        
        # Test dict serialization
        data = position.model_dump()
        assert data["symbol"] == "BTC/USDT"
        assert data["side"] == "LONG"
        
        # Test JSON serialization
        json_data = position.model_dump_json()
        assert "BTC/USDT" in json_data
        assert "LONG" in json_data


# ============================================================
# ORDER MODEL TESTS
# ============================================================

class TestOrderModel:
    """
    Tests for Order model
    """

    def test_order_creation(self, sample_order_data: Dict[str, Any]) -> None:
        """Test order creation"""
        order = Order(**sample_order_data)
        assert order.id is not None
        assert order.symbol == "BTC/USDT"
        assert order.side == OrderSide.BUY
        assert order.type == OrderType.LIMIT
        assert order.quantity == Decimal("1.0")
        assert order.price == Decimal("50000.0")
        assert order.status == OrderStatus.PARTIALLY_FILLED

    def test_order_validation(self) -> None:
        """Test order validation"""
        # Invalid quantity
        with pytest.raises(ValidationError):
            Order(
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                type=OrderType.LIMIT,
                quantity=Decimal("-1.0"),
                price=Decimal("50000.0"),
            )
        
        # Invalid price for LIMIT order
        with pytest.raises(ValidationError):
            Order(
                symbol="BTC/USDT",
                side=OrderSide.BUY,
                type=OrderType.LIMIT,
                quantity=Decimal("1.0"),
                price=Decimal("0.0"),
            )
        
        # Valid MARKET order without price
        order = Order(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            type=OrderType.MARKET,
            quantity=Decimal("1.0"),
        )
        assert order.price is None

    def test_order_fill_calculations(self, sample_order_data: Dict[str, Any]) -> None:
        """Test order fill calculations"""
        order = Order(**sample_order_data)
        
        # Test filled quantity
        assert order.filled_quantity == Decimal("0.5")
        
        # Test remaining quantity
        assert order.remaining_quantity == Decimal("0.5")
        
        # Test is_filled
        assert order.is_filled() is False
        
        # Test fill ratio
        assert order.fill_ratio() == Decimal("0.5")

    def test_order_complete_fill(self) -> None:
        """Test complete order fill"""
        order = Order(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            price=Decimal("50000.0"),
            filled_quantity=Decimal("1.0"),
            status=OrderStatus.FILLED,
        )
        
        assert order.is_filled() is True
        assert order.fill_ratio() == Decimal("1.0")
        assert order.remaining_quantity == Decimal("0.0")

    def test_order_cancellation(self) -> None:
        """Test order cancellation"""
        order = Order(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            price=Decimal("50000.0"),
            status=OrderStatus.CANCELLED,
        )
        
        assert order.status == OrderStatus.CANCELLED
        assert order.is_cancelled() is True
        assert order.is_active() is False

    def test_order_time_in_force(self) -> None:
        """Test order time in force"""
        order = Order(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            price=Decimal("50000.0"),
            time_in_force=TimeInForce.IOC,
        )
        
        assert order.time_in_force == TimeInForce.IOC
        
        # Test expire calculation
        order_expired = order.is_expired()
        assert order_expired is False

    def test_order_serialization(self, sample_order_data: Dict[str, Any]) -> None:
        """Test order serialization"""
        order = Order(**sample_order_data)
        
        data = order.model_dump()
        assert data["symbol"] == "BTC/USDT"
        assert data["side"] == "BUY"
        assert data["type"] == "LIMIT"


# ============================================================
# TRADE MODEL TESTS
# ============================================================

class TestTradeModel:
    """
    Tests for Trade model
    """

    def test_trade_creation(self, sample_trade_data: Dict[str, Any]) -> None:
        """Test trade creation"""
        trade = Trade(**sample_trade_data)
        assert trade.id is not None
        assert trade.symbol == "BTC/USDT"
        assert trade.side == TradeSide.BUY
        assert trade.quantity == Decimal("1.0")
        assert trade.price == Decimal("50000.0")
        assert trade.status == TradeStatus.COMPLETED

    def test_trade_pnl_calculation(self) -> None:
        """Test trade PnL calculation"""
        # Buy trade
        buy_trade = Trade(
            symbol="BTC/USDT",
            side=TradeSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("50000.0"),
        )
        assert buy_trade.pnl == Decimal("0.0")
        
        # Sell trade
        sell_trade = Trade(
            symbol="BTC/USDT",
            side=TradeSide.SELL,
            quantity=Decimal("1.0"),
            price=Decimal("52000.0"),
        )
        
        # Set buy price for PnL calculation
        sell_trade.buy_price = Decimal("50000.0")
        assert sell_trade.pnl == Decimal("2000.0")

    def test_trade_validation(self) -> None:
        """Test trade validation"""
        # Invalid quantity
        with pytest.raises(ValidationError):
            Trade(
                symbol="BTC/USDT",
                side=TradeSide.BUY,
                quantity=Decimal("-1.0"),
                price=Decimal("50000.0"),
            )
        
        # Invalid price
        with pytest.raises(ValidationError):
            Trade(
                symbol="BTC/USDT",
                side=TradeSide.BUY,
                quantity=Decimal("1.0"),
                price=Decimal("-50000.0"),
            )

    def test_trade_serialization(self, sample_trade_data: Dict[str, Any]) -> None:
        """Test trade serialization"""
        trade = Trade(**sample_trade_data)
        
        data = trade.model_dump()
        assert data["symbol"] == "BTC/USDT"
        assert data["side"] == "BUY"
        assert data["status"] == "COMPLETED"


# ============================================================
# PORTFOLIO MODEL TESTS
# ============================================================

class TestPortfolioModel:
    """
    Tests for Portfolio model
    """

    def test_portfolio_creation(self, sample_portfolio_data: Dict[str, Any]) -> None:
        """Test portfolio creation"""
        portfolio = Portfolio(**sample_portfolio_data)
        assert portfolio.id is not None
        assert portfolio.name == "Test Portfolio"
        assert portfolio.currency == "USD"
        assert portfolio.initial_balance == Decimal("100000.0")
        assert portfolio.current_balance == Decimal("125000.0")

    def test_portfolio_metrics(self, sample_portfolio_data: Dict[str, Any]) -> None:
        """Test portfolio metrics"""
        portfolio = Portfolio(**sample_portfolio_data)
        
        # Test total PnL
        assert portfolio.total_pnl == Decimal("25000.0")
        assert portfolio.total_pnl_percent == Decimal("0.25")
        
        # Test daily PnL
        assert portfolio.daily_pnl == Decimal("1500.0")
        assert portfolio.daily_pnl_percent == Decimal("0.012")

    def test_portfolio_validation(self) -> None:
        """Test portfolio validation"""
        # Invalid currency
        with pytest.raises(ValidationError):
            Portfolio(
                name="Test Portfolio",
                currency="INVALID",
                initial_balance=Decimal("100000.0"),
            )
        
        # Invalid balance
        with pytest.raises(ValidationError):
            Portfolio(
                name="Test Portfolio",
                currency="USD",
                initial_balance=Decimal("-100000.0"),
            )

    def test_portfolio_allocation(self) -> None:
        """Test portfolio allocation"""
        allocation = Allocation(
            asset="BTC/USDT",
            weight=Decimal("0.40"),
            value=Decimal("50000.0"),
        )
        
        assert allocation.asset == "BTC/USDT"
        assert allocation.weight == Decimal("0.40")
        assert allocation.value == Decimal("50000.0")

    def test_portfolio_serialization(self, sample_portfolio_data: Dict[str, Any]) -> None:
        """Test portfolio serialization"""
        portfolio = Portfolio(**sample_portfolio_data)
        
        data = portfolio.model_dump()
        assert data["name"] == "Test Portfolio"
        assert data["currency"] == "USD"
        assert data["initial_balance"] == 100000.0


# ============================================================
# RISK MODEL TESTS
# ============================================================

class TestRiskModels:
    """
    Tests for Risk models
    """

    def test_risk_metrics_creation(self, sample_risk_metrics_data: Dict[str, Any]) -> None:
        """Test risk metrics creation"""
        metrics = RiskMetrics(**sample_risk_metrics_data)
        assert metrics.var_95 == Decimal("25000.0")
        assert metrics.var_99 == Decimal("40000.0")
        assert metrics.cvar_95 == Decimal("35000.0")
        assert metrics.sharpe_ratio == Decimal("1.85")

    def test_var_creation(self) -> None:
        """Test VaR creation"""
        var = VaR(
            confidence=Decimal("0.95"),
            horizon=1,
            value=Decimal("25000.0"),
            percentage=Decimal("0.05"),
        )
        
        assert var.confidence == Decimal("0.95")
        assert var.horizon == 1
        assert var.value == Decimal("25000.0")
        assert var.percentage == Decimal("0.05")

    def test_drawdown_creation(self) -> None:
        """Test drawdown creation"""
        drawdown = Drawdown(
            current=Decimal("0.02"),
            max=Decimal("0.08"),
            duration=30,
            recovery_time=15,
        )
        
        assert drawdown.current == Decimal("0.02")
        assert drawdown.max == Decimal("0.08")
        assert drawdown.duration == 30

    def test_risk_metrics_validation(self) -> None:
        """Test risk metrics validation"""
        # Invalid VaR (negative)
        with pytest.raises(ValidationError):
            RiskMetrics(
                var_95=Decimal("-25000.0"),
                var_99=Decimal("40000.0"),
            )
        
        # Invalid Sharpe ratio
        with pytest.raises(ValidationError):
            RiskMetrics(
                var_95=Decimal("25000.0"),
                var_99=Decimal("40000.0"),
                sharpe_ratio=Decimal("-1.0"),
            )


# ============================================================
# STRATEGY MODEL TESTS
# ============================================================

class TestStrategyModel:
    """
    Tests for Strategy model
    """

    def test_strategy_creation(self) -> None:
        """Test strategy creation"""
        strategy = Strategy(
            id=str(uuid.uuid4()),
            name="Delta Hedging Strategy",
            type=StrategyType.HEDGE,
            status=StrategyStatus.RUNNING,
            parameters=StrategyParameters(
                hedge_ratio=Decimal("0.50"),
                rebalance_interval=15,
            ),
        )
        
        assert strategy.name == "Delta Hedging Strategy"
        assert strategy.type == StrategyType.HEDGE
        assert strategy.status == StrategyStatus.RUNNING

    def test_strategy_validation(self) -> None:
        """Test strategy validation"""
        # Invalid strategy type
        with pytest.raises(ValidationError):
            Strategy(
                name="Invalid Strategy",
                type="INVALID_TYPE",  # type: ignore
                status=StrategyStatus.RUNNING,
            )
        
        # Invalid status
        with pytest.raises(ValidationError):
            Strategy(
                name="Invalid Strategy",
                type=StrategyType.HEDGE,
                status="INVALID_STATUS",  # type: ignore
            )

    def test_strategy_parameters(self) -> None:
        """Test strategy parameters"""
        params = StrategyParameters(
            hedge_ratio=Decimal("0.50"),
            rebalance_interval=15,
            threshold=Decimal("0.01"),
            leverage=Decimal("1.0"),
        )
        
        assert params.hedge_ratio == Decimal("0.50")
        assert params.rebalance_interval == 15
        assert params.threshold == Decimal("0.01")

    def test_strategy_serialization(self) -> None:
        """Test strategy serialization"""
        strategy = Strategy(
            name="Delta Hedging Strategy",
            type=StrategyType.HEDGE,
            status=StrategyStatus.RUNNING,
            parameters=StrategyParameters(hedge_ratio=Decimal("0.50")),
        )
        
        data = strategy.model_dump()
        assert data["name"] == "Delta Hedging Strategy"
        assert data["type"] == "HEDGE"


# ============================================================
# MARKET DATA MODEL TESTS
# ============================================================

class TestMarketDataModels:
    """
    Tests for Market Data models
    """

    def test_ticker_creation(self) -> None:
        """Test ticker creation"""
        ticker = Ticker(
            symbol="BTC/USDT",
            bid=Decimal("50000.0"),
            ask=Decimal("50100.0"),
            last=Decimal("50050.0"),
            volume=Decimal("1000000.0"),
        )
        
        assert ticker.symbol == "BTC/USDT"
        assert ticker.bid == Decimal("50000.0")
        assert ticker.ask == Decimal("50100.0")
        assert ticker.spread() == Decimal("100.0")
        assert ticker.mid_price() == Decimal("50050.0")

    def test_ohlcv_creation(self) -> None:
        """Test OHLCV creation"""
        ohlcv = OHLCV(
            symbol="BTC/USDT",
            open=Decimal("50000.0"),
            high=Decimal("50200.0"),
            low=Decimal("49800.0"),
            close=Decimal("50100.0"),
            volume=Decimal("1000000.0"),
            timestamp=datetime.now(),
        )
        
        assert ohlcv.symbol == "BTC/USDT"
        assert ohlcv.open == Decimal("50000.0")
        assert ohlcv.high == Decimal("50200.0")
        assert ohlcv.close == Decimal("50100.0")

    def test_order_book_creation(self) -> None:
        """Test order book creation"""
        order_book = OrderBook(
            symbol="BTC/USDT",
            bids=[(Decimal("50000.0"), Decimal("1.0"))],
            asks=[(Decimal("50100.0"), Decimal("1.0"))],
            timestamp=datetime.now(),
        )
        
        assert order_book.symbol == "BTC/USDT"
        assert len(order_book.bids) == 1
        assert len(order_book.asks) == 1
        
        # Test top of book
        best_bid = order_book.best_bid()
        assert best_bid == Decimal("50000.0")
        
        best_ask = order_book.best_ask()
        assert best_ask == Decimal("50100.0")


# ============================================================
# USER MODEL TESTS
# ============================================================

class TestUserModel:
    """
    Tests for User model
    """

    def test_user_creation(self) -> None:
        """Test user creation"""
        user = User(
            id=str(uuid.uuid4()),
            username="test_user",
            email="test@example.com",
            role=UserRole.TRADER,
            preferences=UserPreferences(
                theme="dark",
                notifications_enabled=True,
                default_currency="USD",
            ),
        )
        
        assert user.username == "test_user"
        assert user.email == "test@example.com"
        assert user.role == UserRole.TRADER

    def test_user_validation(self) -> None:
        """Test user validation"""
        # Invalid email
        with pytest.raises(ValidationError):
            User(
                username="test_user",
                email="invalid_email",
                role=UserRole.TRADER,
            )
        
        # Invalid role
        with pytest.raises(ValidationError):
            User(
                username="test_user",
                email="test@example.com",
                role="INVALID_ROLE",  # type: ignore
            )

    def test_user_preferences(self) -> None:
        """Test user preferences"""
        prefs = UserPreferences(
            theme="dark",
            notifications_enabled=True,
            default_currency="USD",
        )
        
        assert prefs.theme == "dark"
        assert prefs.notifications_enabled is True
        assert prefs.default_currency == "USD"

    def test_user_serialization(self) -> None:
        """Test user serialization"""
        user = User(
            username="test_user",
            email="test@example.com",
            role=UserRole.TRADER,
        )
        
        data = user.model_dump()
        assert data["username"] == "test_user"
        assert data["email"] == "test@example.com"
        assert data["role"] == "TRADER"


# ============================================================
# CONFIG MODEL TESTS
# ============================================================

class TestConfigModels:
    """
    Tests for Configuration models
    """

    def test_bot_config_creation(self) -> None:
        """Test bot config creation"""
        config = BotConfig(
            id="test_bot",
            name="Test Bot",
            version="2.0.0",
            enabled=True,
            environment="testing",
        )
        
        assert config.id == "test_bot"
        assert config.name == "Test Bot"
        assert config.enabled is True
        assert config.environment == "testing"

    def test_exchange_config_creation(self) -> None:
        """Test exchange config creation"""
        config = ExchangeConfig(
            name="binance",
            type="spot",
            sandbox=True,
            api_key="test_key",
            api_secret="test_secret",
        )
        
        assert config.name == "binance"
        assert config.type == "spot"
        assert config.sandbox is True

    def test_trading_config_creation(self) -> None:
        """Test trading config creation"""
        config = TradingConfig(
            max_leverage=Decimal("3.0"),
            max_positions=10,
            target_hedge_ratio=Decimal("0.50"),
            min_hedge_ratio=Decimal("0.20"),
            max_hedge_ratio=Decimal("0.80"),
        )
        
        assert config.max_leverage == Decimal("3.0")
        assert config.max_positions == 10
        assert config.target_hedge_ratio == Decimal("0.50")

    def test_config_validation(self) -> None:
        """Test config validation"""
        # Invalid leverage
        with pytest.raises(ValidationError):
            TradingConfig(
                max_leverage=Decimal("0.0"),
                max_positions=10,
            )
        
        # Invalid positions
        with pytest.raises(ValidationError):
            TradingConfig(
                max_leverage=Decimal("3.0"),
                max_positions=-1,
            )

    def test_config_serialization(self) -> None:
        """Test config serialization"""
        config = BotConfig(
            id="test_bot",
            name="Test Bot",
            enabled=True,
            environment="testing",
        )
        
        data = config.model_dump()
        assert data["id"] == "test_bot"
        assert data["name"] == "Test Bot"


# ============================================================
# MODEL INTEGRATION TESTS
# ============================================================

class TestModelIntegration:
    """
    Integration tests for models
    """

    def test_position_order_integration(self) -> None:
        """Test position and order integration"""
        # Create order
        order = Order(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            type=OrderType.LIMIT,
            quantity=Decimal("1.0"),
            price=Decimal("50000.0"),
            status=OrderStatus.FILLED,
            filled_quantity=Decimal("1.0"),
        )
        
        # Create position from order
        position = Position(
            symbol=order.symbol,
            side=PositionSide.LONG,
            quantity=order.filled_quantity,
            entry_price=order.price,
            current_price=order.price,
        )
        
        assert position.symbol == order.symbol
        assert position.quantity == order.filled_quantity
        assert position.entry_price == order.price

    def test_trade_portfolio_integration(self) -> None:
        """Test trade and portfolio integration"""
        # Create trade
        trade = Trade(
            symbol="BTC/USDT",
            side=TradeSide.BUY,
            quantity=Decimal("1.0"),
            price=Decimal("50000.0"),
            status=TradeStatus.COMPLETED,
        )
        
        # Update portfolio with trade
        portfolio = Portfolio(
            name="Test Portfolio",
            currency="USD",
            initial_balance=Decimal("100000.0"),
            current_balance=Decimal("100000.0"),
        )
        
        # Simulate PnL update
        trade_pnl = Decimal("2000.0")
        portfolio.current_balance += trade_pnl
        portfolio.total_pnl += trade_pnl
        
        assert portfolio.current_balance == Decimal("102000.0")
        assert portfolio.total_pnl == Decimal("2000.0")

    def test_risk_portfolio_integration(self) -> None:
        """Test risk and portfolio integration"""
        # Create portfolio
        portfolio = Portfolio(
            name="Test Portfolio",
            currency="USD",
            initial_balance=Decimal("100000.0"),
            current_balance=Decimal("125000.0"),
            total_pnl=Decimal("25000.0"),
        )
        
        # Calculate risk metrics
        risk_metrics = RiskMetrics(
            var_95=Decimal("25000.0"),
            var_99=Decimal("40000.0"),
            cvar_95=Decimal("35000.0"),
            max_drawdown=Decimal("0.08"),
            current_drawdown=Decimal("0.02"),
            sharpe_ratio=Decimal("1.85"),
        )
        
        # Check risk vs portfolio
        assert risk_metrics.var_95 < portfolio.current_balance
        assert risk_metrics.max_drawdown < Decimal("0.15")
        assert risk_metrics.sharpe_ratio > Decimal("1.0")


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    "TestPositionModel",
    "TestOrderModel",
    "TestTradeModel",
    "TestPortfolioModel",
    "TestRiskModels",
    "TestStrategyModel",
    "TestMarketDataModels",
    "TestUserModel",
    "TestConfigModels",
    "TestModelIntegration",
]
