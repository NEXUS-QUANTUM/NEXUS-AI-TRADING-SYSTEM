"""
Swing Bot Core Tests
=====================

This module contains unit tests for the core components of the Swing Bot trading system.
"""

import pytest
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from trading.bots.swing_bot.core import (
    Engine,
    StrategyBase,
    Signal,
    SignalType,
    OrderSide,
    OrderType,
    OrderStatus,
    Position,
    Trade,
    Portfolio,
    MarketData,
    Event,
    EventType
)
from trading.bots.swing_bot.utils.validators import validate_data
from trading.bots.swing_bot.utils.converters import to_datetime

from .fixtures import get_config_fixture, get_market_data_fixture


class TestEngine:
    """Tests for the Engine class."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def engine(self, config):
        """Create an Engine instance."""
        return Engine(config=config)
    
    def test_initialization(self, engine):
        """Test engine initialization."""
        assert engine.config is not None
        assert engine.is_running is False
        assert engine.strategies == []
        assert engine.risk_manager is None
        assert engine.execution_engine is None
    
    def test_start_stop(self, engine):
        """Test starting and stopping the engine."""
        engine.start()
        assert engine.is_running is True
        
        engine.stop()
        assert engine.is_running is False
    
    def test_register_strategy(self, engine):
        """Test strategy registration."""
        strategy = StrategyBase()
        engine.register_strategy(strategy)
        assert strategy in engine.strategies
    
    def test_process_data(self, engine, market_data):
        """Test data processing."""
        df = pd.DataFrame(market_data)
        
        # Register a strategy
        strategy = StrategyBase()
        engine.register_strategy(strategy)
        
        # Process data
        result = engine.process_data(df)
        assert result is not None


class TestStrategyBase:
    """Tests for the StrategyBase class."""
    
    @pytest.fixture
    def strategy(self):
        """Create a StrategyBase instance."""
        return StrategyBase()
    
    def test_initialization(self, strategy):
        """Test strategy initialization."""
        assert strategy.name == "StrategyBase"
        assert strategy.is_active is True
    
    def test_generate_signals(self, strategy, market_data):
        """Test signal generation."""
        df = pd.DataFrame(market_data)
        signals = strategy.generate_signals(df)
        assert signals is not None
        assert isinstance(signals, list)
    
    def test_validate_signal(self, strategy):
        """Test signal validation."""
        signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.BUY,
            price=150.0
        )
        assert strategy.validate_signal(signal) is True
    
    def test_invalid_signal(self, strategy):
        """Test invalid signal validation."""
        signal = Signal(
            symbol="",
            signal_type=SignalType.BUY,
            price=-150.0
        )
        assert strategy.validate_signal(signal) is False


class TestSignal:
    """Tests for the Signal class."""
    
    def test_signal_creation(self):
        """Test signal creation."""
        signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.BUY,
            price=150.0,
            confidence=0.85
        )
        assert signal.symbol == "AAPL"
        assert signal.signal_type == SignalType.BUY
        assert signal.price == 150.0
        assert signal.confidence == 0.85
    
    def test_signal_to_dict(self):
        """Test signal to dict conversion."""
        signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.BUY,
            price=150.0,
            confidence=0.85
        )
        data = signal.to_dict()
        assert data["symbol"] == "AAPL"
        assert data["signal_type"] == "BUY"
        assert data["price"] == 150.0
        assert data["confidence"] == 0.85
    
    def test_signal_from_dict(self):
        """Test signal from dict conversion."""
        data = {
            "symbol": "AAPL",
            "signal_type": "BUY",
            "price": 150.0,
            "confidence": 0.85
        }
        signal = Signal.from_dict(data)
        assert signal.symbol == "AAPL"
        assert signal.signal_type == SignalType.BUY
        assert signal.price == 150.0
        assert signal.confidence == 0.85


class TestPosition:
    """Tests for the Position class."""
    
    def test_position_creation(self):
        """Test position creation."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            entry_price=150.0
        )
        assert position.symbol == "AAPL"
        assert position.quantity == 100
        assert position.entry_price == 150.0
        assert position.current_price == 150.0
    
    def test_position_pnl(self):
        """Test position PnL calculation."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            entry_price=150.0,
            current_price=155.0
        )
        assert position.calculate_pnl() == 500.0
        assert position.calculate_pnl_percent() == 0.03333333333333333
    
    def test_position_update(self):
        """Test position update."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            entry_price=150.0
        )
        position.update_price(155.0)
        assert position.current_price == 155.0


class TestTrade:
    """Tests for the Trade class."""
    
    def test_trade_creation(self):
        """Test trade creation."""
        trade = Trade(
            order_id="ORD123",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            price=150.0
        )
        assert trade.order_id == "ORD123"
        assert trade.symbol == "AAPL"
        assert trade.side == OrderSide.BUY
        assert trade.quantity == 100
        assert trade.price == 150.0
    
    def test_trade_to_dict(self):
        """Test trade to dict conversion."""
        trade = Trade(
            order_id="ORD123",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            price=150.0
        )
        data = trade.to_dict()
        assert data["order_id"] == "ORD123"
        assert data["symbol"] == "AAPL"
        assert data["side"] == "BUY"
        assert data["quantity"] == 100
        assert data["price"] == 150.0


class TestPortfolio:
    """Tests for the Portfolio class."""
    
    def test_portfolio_creation(self):
        """Test portfolio creation."""
        portfolio = Portfolio(
            account_id="ACC123",
            cash=100000.0
        )
        assert portfolio.account_id == "ACC123"
        assert portfolio.cash == 100000.0
        assert portfolio.positions == []
    
    def test_add_position(self):
        """Test adding a position."""
        portfolio = Portfolio(account_id="ACC123")
        position = Position(symbol="AAPL", quantity=100, entry_price=150.0)
        portfolio.add_position(position)
        assert len(portfolio.positions) == 1
    
    def test_portfolio_value(self):
        """Test portfolio value calculation."""
        portfolio = Portfolio(
            account_id="ACC123",
            cash=100000.0,
            positions=[
                Position(symbol="AAPL", quantity=100, entry_price=150.0, current_price=155.0),
                Position(symbol="GOOGL", quantity=50, entry_price=2500.0, current_price=2600.0)
            ]
        )
        assert portfolio.calculate_total_value() == 100000.0 + 100*155.0 + 50*2600.0


class TestMarketData:
    """Tests for the MarketData class."""
    
    def test_market_data_creation(self):
        """Test market data creation."""
        market_data = MarketData(
            symbol="AAPL",
            timestamp=datetime.now(),
            open=150.0,
            high=155.0,
            low=148.0,
            close=153.0,
            volume=1000000
        )
        assert market_data.symbol == "AAPL"
        assert market_data.open == 150.0
        assert market_data.high == 155.0
        assert market_data.low == 148.0
        assert market_data.close == 153.0
        assert market_data.volume == 1000000
    
    def test_market_data_validation(self):
        """Test market data validation."""
        market_data = MarketData(
            symbol="AAPL",
            timestamp=datetime.now(),
            open=150.0,
            high=155.0,
            low=148.0,
            close=153.0,
            volume=1000000
        )
        assert validate_data(market_data.to_dict(), "market")[0] is True


class TestEvent:
    """Tests for the Event class."""
    
    def test_event_creation(self):
        """Test event creation."""
        event = Event(
            event_type=EventType.SIGNAL,
            data={"symbol": "AAPL", "signal_type": "BUY"},
            timestamp=datetime.now()
        )
        assert event.event_type == EventType.SIGNAL
        assert event.data["symbol"] == "AAPL"
        assert event.data["signal_type"] == "BUY"
    
    def test_event_to_dict(self):
        """Test event to dict conversion."""
        event = Event(
            event_type=EventType.SIGNAL,
            data={"symbol": "AAPL", "signal_type": "BUY"}
        )
        data = event.to_dict()
        assert data["event_type"] == "SIGNAL"
        assert data["data"]["symbol"] == "AAPL"
        assert data["data"]["signal_type"] == "BUY"


class TestCoreIntegration:
    """Integration tests for core components."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def engine(self, config):
        """Create an Engine instance."""
        return Engine(config=config)
    
    def test_engine_with_strategies(self, engine, market_data):
        """Test engine with registered strategies."""
        df = pd.DataFrame(market_data)
        
        # Register strategies
        strategy1 = StrategyBase()
        strategy2 = StrategyBase()
        engine.register_strategy(strategy1)
        engine.register_strategy(strategy2)
        
        # Process data
        engine.start()
        result = engine.process_data(df)
        engine.stop()
        
        assert result is not None
        assert len(engine.strategies) == 2
    
    def test_signal_flow(self, engine, market_data):
        """Test signal flow through the engine."""
        df = pd.DataFrame(market_data)
        
        # Create a custom strategy that generates signals
        class TestStrategy(StrategyBase):
            def generate_signals(self, data):
                return [
                    Signal(
                        symbol="AAPL",
                        signal_type=SignalType.BUY,
                        price=data['close'].iloc[-1],
                        confidence=0.8,
                        timestamp=datetime.now()
                    )
                ]
        
        strategy = TestStrategy()
        engine.register_strategy(strategy)
        
        engine.start()
        result = engine.process_data(df)
        engine.stop()
        
        assert result is not None
        assert "signals" in result or isinstance(result, list)


if __name__ == "__main__":
    pytest.main([__file__])
