"""
Swing Bot Models Tests
=======================

This module contains unit tests for the data models used in the Swing Bot trading system.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import json
from typing import Any, Dict, List

from trading.bots.swing_bot.core import (
    Signal,
    SignalType,
    OrderSide,
    OrderType,
    OrderStatus,
    Position,
    Trade,
    Portfolio,
    MarketData
)
from trading.bots.swing_bot.utils.validators import validate_data
from trading.bots.swing_bot.utils.converters import to_datetime, to_decimal


class TestSignal:
    """Tests for Signal model."""
    
    def test_signal_creation(self):
        """Test signal creation."""
        signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.BUY,
            price=150.0,
            confidence=0.85,
            timestamp=datetime.now(),
            reason="RSI oversold"
        )
        
        assert signal.symbol == "AAPL"
        assert signal.signal_type == SignalType.BUY
        assert signal.price == 150.0
        assert signal.confidence == 0.85
        assert signal.reason == "RSI oversold"
    
    def test_signal_defaults(self):
        """Test signal default values."""
        signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.BUY,
            price=150.0
        )
        
        assert signal.confidence is None
        assert signal.timestamp is not None
        assert signal.reason is None
    
    def test_signal_validation(self):
        """Test signal validation."""
        # Valid signal
        signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.BUY,
            price=150.0
        )
        assert validate_data(signal.to_dict(), "signal")[0] is True
        
        # Invalid signal - missing symbol
        with pytest.raises(ValueError):
            Signal(
                symbol="",
                signal_type=SignalType.BUY,
                price=150.0
            )
    
    def test_signal_to_dict(self):
        """Test signal to dict conversion."""
        signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.BUY,
            price=150.0,
            confidence=0.85,
            reason="Test"
        )
        
        data = signal.to_dict()
        assert data["symbol"] == "AAPL"
        assert data["signal_type"] == "BUY"
        assert data["price"] == 150.0
        assert data["confidence"] == 0.85
        assert data["reason"] == "Test"
        assert "timestamp" in data
    
    def test_signal_from_dict(self):
        """Test signal from dict conversion."""
        data = {
            "symbol": "AAPL",
            "signal_type": "BUY",
            "price": 150.0,
            "confidence": 0.85,
            "timestamp": datetime.now().isoformat(),
            "reason": "Test"
        }
        
        signal = Signal.from_dict(data)
        assert signal.symbol == "AAPL"
        assert signal.signal_type == SignalType.BUY
        assert signal.price == 150.0
        assert signal.confidence == 0.85
        assert signal.reason == "Test"


class TestPosition:
    """Tests for Position model."""
    
    def test_position_creation(self):
        """Test position creation."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            entry_price=150.0,
            current_price=155.0,
            entry_time=datetime.now(),
            side=OrderSide.BUY
        )
        
        assert position.symbol == "AAPL"
        assert position.quantity == 100
        assert position.entry_price == 150.0
        assert position.current_price == 155.0
        assert position.side == OrderSide.BUY
    
    def test_position_defaults(self):
        """Test position default values."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            entry_price=150.0
        )
        
        assert position.current_price == 150.0
        assert position.entry_time is not None
        assert position.side == OrderSide.BUY
    
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
    
    def test_position_validation(self):
        """Test position validation."""
        # Valid position
        position = Position(
            symbol="AAPL",
            quantity=100,
            entry_price=150.0
        )
        assert validate_data(position.to_dict(), "position")[0] is True
        
        # Invalid position - negative quantity
        with pytest.raises(ValueError):
            Position(
                symbol="AAPL",
                quantity=-100,
                entry_price=150.0
            )
    
    def test_position_to_dict(self):
        """Test position to dict conversion."""
        position = Position(
            symbol="AAPL",
            quantity=100,
            entry_price=150.0,
            current_price=155.0
        )
        
        data = position.to_dict()
        assert data["symbol"] == "AAPL"
        assert data["quantity"] == 100
        assert data["entry_price"] == 150.0
        assert data["current_price"] == 155.0
        assert data["side"] == "BUY"
        assert "entry_time" in data


class TestTrade:
    """Tests for Trade model."""
    
    def test_trade_creation(self):
        """Test trade creation."""
        trade = Trade(
            order_id="ORD123",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            price=150.0,
            executed_at=datetime.now(),
            commission=10.0
        )
        
        assert trade.order_id == "ORD123"
        assert trade.symbol == "AAPL"
        assert trade.side == OrderSide.BUY
        assert trade.quantity == 100
        assert trade.price == 150.0
        assert trade.commission == 10.0
    
    def test_trade_defaults(self):
        """Test trade default values."""
        trade = Trade(
            order_id="ORD123",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            price=150.0
        )
        
        assert trade.commission == 0.0
        assert trade.executed_at is not None
    
    def test_trade_validation(self):
        """Test trade validation."""
        # Valid trade
        trade = Trade(
            order_id="ORD123",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            price=150.0
        )
        assert validate_data(trade.to_dict(), "trade")[0] is True
        
        # Invalid trade - missing order_id
        with pytest.raises(ValueError):
            Trade(
                order_id="",
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=100,
                price=150.0
            )
    
    def test_trade_to_dict(self):
        """Test trade to dict conversion."""
        trade = Trade(
            order_id="ORD123",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            price=150.0,
            commission=10.0
        )
        
        data = trade.to_dict()
        assert data["order_id"] == "ORD123"
        assert data["symbol"] == "AAPL"
        assert data["side"] == "BUY"
        assert data["quantity"] == 100
        assert data["price"] == 150.0
        assert data["commission"] == 10.0
        assert "executed_at" in data


class TestPortfolio:
    """Tests for Portfolio model."""
    
    def test_portfolio_creation(self):
        """Test portfolio creation."""
        portfolio = Portfolio(
            account_id="ACC123",
            cash=100000.0,
            positions=[Position(symbol="AAPL", quantity=100, entry_price=150.0)]
        )
        
        assert portfolio.account_id == "ACC123"
        assert portfolio.cash == 100000.0
        assert len(portfolio.positions) == 1
    
    def test_portfolio_defaults(self):
        """Test portfolio default values."""
        portfolio = Portfolio(account_id="ACC123")
        
        assert portfolio.cash == 0.0
        assert portfolio.positions == []
    
    def test_portfolio_calculation(self):
        """Test portfolio calculations."""
        positions = [
            Position(symbol="AAPL", quantity=100, entry_price=150.0, current_price=155.0),
            Position(symbol="GOOGL", quantity=50, entry_price=2500.0, current_price=2600.0)
        ]
        portfolio = Portfolio(
            account_id="ACC123",
            cash=100000.0,
            positions=positions
        )
        
        assert portfolio.calculate_total_value() == 100000.0 + 100*155.0 + 50*2600.0
        assert portfolio.calculate_total_pnl() > 0
    
    def test_portfolio_validation(self):
        """Test portfolio validation."""
        portfolio = Portfolio(
            account_id="ACC123",
            cash=100000.0
        )
        assert validate_data(portfolio.to_dict(), "portfolio")[0] is True
    
    def test_portfolio_to_dict(self):
        """Test portfolio to dict conversion."""
        portfolio = Portfolio(
            account_id="ACC123",
            cash=100000.0,
            positions=[Position(symbol="AAPL", quantity=100, entry_price=150.0)]
        )
        
        data = portfolio.to_dict()
        assert data["account_id"] == "ACC123"
        assert data["cash"] == 100000.0
        assert len(data["positions"]) == 1


class TestMarketData:
    """Tests for MarketData model."""
    
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
    
    def test_market_data_defaults(self):
        """Test market data default values."""
        market_data = MarketData(
            symbol="AAPL",
            timestamp=datetime.now()
        )
        
        assert market_data.open == 0.0
        assert market_data.high == 0.0
        assert market_data.low == 0.0
        assert market_data.close == 0.0
        assert market_data.volume == 0
    
    def test_market_data_validation(self):
        """Test market data validation."""
        # Valid data
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
        
        # Invalid data - high < low
        with pytest.raises(ValueError):
            MarketData(
                symbol="AAPL",
                timestamp=datetime.now(),
                open=150.0,
                high=140.0,
                low=148.0,
                close=153.0,
                volume=1000000
            )
    
    def test_market_data_to_dict(self):
        """Test market data to dict conversion."""
        market_data = MarketData(
            symbol="AAPL",
            timestamp=datetime.now(),
            open=150.0,
            high=155.0,
            low=148.0,
            close=153.0,
            volume=1000000
        )
        
        data = market_data.to_dict()
        assert data["symbol"] == "AAPL"
        assert data["open"] == 150.0
        assert data["high"] == 155.0
        assert data["low"] == 148.0
        assert data["close"] == 153.0
        assert data["volume"] == 1000000
        assert "timestamp" in data


class TestModelIntegration:
    """Integration tests for models."""
    
    def test_model_serialization(self):
        """Test model serialization and deserialization."""
        # Create a complex model
        portfolio = Portfolio(
            account_id="ACC123",
            cash=100000.0,
            positions=[
                Position(
                    symbol="AAPL",
                    quantity=100,
                    entry_price=150.0,
                    current_price=155.0,
                    entry_time=datetime.now()
                ),
                Position(
                    symbol="GOOGL",
                    quantity=50,
                    entry_price=2500.0,
                    current_price=2600.0
                )
            ]
        )
        
        # Convert to dict and back
        data = portfolio.to_dict()
        new_portfolio = Portfolio.from_dict(data)
        
        assert new_portfolio.account_id == portfolio.account_id
        assert new_portfolio.cash == portfolio.cash
        assert len(new_portfolio.positions) == len(portfolio.positions)
    
    def test_model_json_serialization(self):
        """Test model JSON serialization."""
        signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.BUY,
            price=150.0,
            confidence=0.85,
            timestamp=datetime.now()
        )
        
        # Convert to JSON and back
        json_str = signal.to_json()
        new_signal = Signal.from_json(json_str)
        
        assert new_signal.symbol == signal.symbol
        assert new_signal.signal_type == signal.signal_type
        assert new_signal.price == signal.price
        assert new_signal.confidence == signal.confidence
    
    def test_model_timestamp_handling(self):
        """Test model timestamp handling."""
        now = datetime.now()
        
        signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.BUY,
            price=150.0,
            timestamp=now
        )
        
        data = signal.to_dict()
        assert "timestamp" in data
        
        # Parse timestamp
        parsed_time = to_datetime(data["timestamp"])
        assert abs((parsed_time - now).total_seconds()) < 1
    
    def test_model_validation_chain(self):
        """Test validation chain across models."""
        # Create signal
        signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.BUY,
            price=150.0
        )
        
        # Create position from signal
        position = Position(
            symbol=signal.symbol,
            quantity=100,
            entry_price=signal.price
        )
        
        # Create trade from position
        trade = Trade(
            order_id="ORD123",
            symbol=position.symbol,
            side=OrderSide.BUY,
            quantity=position.quantity,
            price=position.entry_price
        )
        
        # Create portfolio
        portfolio = Portfolio(
            account_id="ACC123",
            cash=100000.0,
            positions=[position]
        )
        
        # All models should be valid
        assert validate_data(signal.to_dict(), "signal")[0] is True
        assert validate_data(position.to_dict(), "position")[0] is True
        assert validate_data(trade.to_dict(), "trade")[0] is True
        assert validate_data(portfolio.to_dict(), "portfolio")[0] is True


if __name__ == "__main__":
    pytest.main([__file__])
