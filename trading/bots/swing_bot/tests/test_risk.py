"""
Swing Bot Risk Tests
=====================

This module contains unit tests for the risk management components of the Swing Bot trading system.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from trading.bots.swing_bot.risk_management import (
    RiskManager,
    PositionSizer,
    DrawdownController,
    StopLossManager,
    TakeProfitManager,
    CircuitBreaker,
    ValueAtRisk
)
from trading.bots.swing_bot.core import Signal, SignalType, OrderSide, Position
from trading.bots.swing_bot.utils.validators import validate_data

from .fixtures import get_config_fixture, get_market_data_fixture


class TestRiskManager:
    """Tests for RiskManager."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def risk_manager(self, config):
        """Create a RiskManager instance."""
        return RiskManager(config=config)
    
    def test_initialization(self, risk_manager):
        """Test risk manager initialization."""
        assert risk_manager.config is not None
        assert risk_manager.max_position_size == 0.10
        assert risk_manager.max_drawdown == 0.10
        assert risk_manager.max_leverage == 2.0
        assert risk_manager.var_confidence == 0.95
    
    def test_check_position_size(self, risk_manager):
        """Test position size checking."""
        # Test valid position size
        assert risk_manager._check_position_size(0.05) is True
        
        # Test invalid position size
        assert risk_manager._check_position_size(0.15) is False
    
    def test_check_leverage(self, risk_manager):
        """Test leverage checking."""
        # Test valid leverage
        assert risk_manager._check_leverage(1.5) is True
        
        # Test invalid leverage
        assert risk_manager._check_leverage(2.5) is False
    
    @pytest.mark.asyncio
    async def test_check_risk(self, risk_manager):
        """Test overall risk check."""
        # Create test position
        position = Position(
            symbol="AAPL",
            quantity=100,
            entry_price=150.0,
            current_price=155.0
        )
        
        # Test risk check
        result = await risk_manager.check_risk(position)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_calculate_position_size(self, risk_manager):
        """Test position size calculation."""
        # Create test signal
        signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.BUY,
            price=150.0,
            confidence=0.85,
            timestamp=datetime.now()
        )
        
        # Calculate position size
        size = await risk_manager.calculate_position_size(signal)
        
        assert size > 0
        assert size <= risk_manager.max_position_size * 100000  # Account size * max position
    
    @pytest.mark.asyncio
    async def test_risk_limits(self, risk_manager):
        """Test risk limits."""
        # Set up risk limits
        risk_manager.max_position_size = 0.05
        risk_manager.max_leverage = 1.5
        risk_manager.max_drawdown = 0.08
        
        # Test limits
        assert risk_manager.max_position_size == 0.05
        assert risk_manager.max_leverage == 1.5
        assert risk_manager.max_drawdown == 0.08


class TestPositionSizer:
    """Tests for PositionSizer."""
    
    @pytest.fixture
    def position_sizer(self):
        """Create a PositionSizer instance."""
        return PositionSizer(
            risk_per_trade=0.02,
            max_position_size=0.10,
            min_position_size=0.01
        )
    
    def test_initialization(self, position_sizer):
        """Test position sizer initialization."""
        assert position_sizer.risk_per_trade == 0.02
        assert position_sizer.max_position_size == 0.10
        assert position_sizer.min_position_size == 0.01
    
    def test_calculate_size(self, position_sizer):
        """Test position size calculation."""
        # Test with account size
        account_size = 100000
        price = 150.0
        stop_loss = 145.0
        
        size = position_sizer.calculate_size(
            account_size=account_size,
            price=price,
            stop_loss=stop_loss
        )
        
        assert size > 0
        assert size <= position_sizer.max_position_size * account_size / price
    
    def test_kelly_sizing(self, position_sizer):
        """Test Kelly criterion sizing."""
        # Test with win rate and win/loss ratio
        win_rate = 0.60
        win_loss_ratio = 1.5
        
        size = position_sizer.calculate_kelly_size(
            win_rate=win_rate,
            win_loss_ratio=win_loss_ratio
        )
        
        assert size >= 0
        assert size <= 0.25  # Kelly fraction cap
    
    def test_volatility_sizing(self, position_sizer):
        """Test volatility-based sizing."""
        # Create test data
        prices = np.random.randn(100) * 5 + 100
        
        size = position_sizer.calculate_volatility_size(
            prices=prices,
            account_size=100000,
            volatility_multiplier=1.0
        )
        
        assert size > 0
        assert size <= position_sizer.max_position_size * 100000 / prices[-1]


class TestDrawdownController:
    """Tests for DrawdownController."""
    
    @pytest.fixture
    def drawdown_controller(self):
        """Create a DrawdownController instance."""
        return DrawdownController(
            max_drawdown=0.10,
            warning_threshold=0.05,
            recovery_threshold=0.08
        )
    
    def test_initialization(self, drawdown_controller):
        """Test drawdown controller initialization."""
        assert drawdown_controller.max_drawdown == 0.10
        assert drawdown_controller.warning_threshold == 0.05
        assert drawdown_controller.recovery_threshold == 0.08
    
    def test_calculate_drawdown(self, drawdown_controller):
        """Test drawdown calculation."""
        # Create price series with drawdown
        prices = [100, 110, 120, 115, 105, 95, 90, 85, 80]
        
        drawdown = drawdown_controller.calculate_drawdown(prices)
        
        assert drawdown > 0
        assert drawdown <= 1.0
    
    def test_check_drawdown(self, drawdown_controller):
        """Test drawdown checking."""
        # Test within limit
        assert drawdown_controller.check_drawdown(0.05) is True
        
        # Test exceeding limit
        assert drawdown_controller.check_drawdown(0.12) is False
    
    def test_warning_level(self, drawdown_controller):
        """Test drawdown warning level."""
        # Test warning threshold
        assert drawdown_controller.check_warning(0.06) is True
        assert drawdown_controller.check_warning(0.04) is False


class TestStopLossManager:
    """Tests for StopLossManager."""
    
    @pytest.fixture
    def stop_loss_manager(self):
        """Create a StopLossManager instance."""
        return StopLossManager(
            default_stop_percent=0.02,
            volatility_multiplier=2.0,
            trailing_stop_activation=0.02,
            trailing_stop_distance=0.01
        )
    
    def test_initialization(self, stop_loss_manager):
        """Test stop loss manager initialization."""
        assert stop_loss_manager.default_stop_percent == 0.02
        assert stop_loss_manager.volatility_multiplier == 2.0
        assert stop_loss_manager.trailing_stop_activation == 0.02
        assert stop_loss_manager.trailing_stop_distance == 0.01
    
    def test_calculate_stop_loss(self, stop_loss_manager):
        """Test stop loss calculation."""
        # Test fixed stop
        stop = stop_loss_manager.calculate_stop_loss(
            entry_price=150.0,
            stop_type="fixed"
        )
        assert stop == 147.0
        
        # Test volatility-based stop
        prices = np.random.randn(50) * 5 + 150
        stop = stop_loss_manager.calculate_stop_loss(
            entry_price=150.0,
            stop_type="volatility",
            prices=prices
        )
        assert stop < 150.0
    
    def test_trailing_stop(self, stop_loss_manager):
        """Test trailing stop calculation."""
        # Test trailing stop activation
        price = 152.0
        highest_price = 155.0
        
        stop = stop_loss_manager.calculate_trailing_stop(
            current_price=price,
            highest_price=highest_price
        )
        
        assert stop < price
        assert stop < highest_price
    
    def test_update_stop_loss(self, stop_loss_manager):
        """Test stop loss update."""
        # Initial stop
        current_stop = 147.0
        highest_price = 155.0
        current_price = 153.0
        
        new_stop = stop_loss_manager.update_stop_loss(
            current_stop=current_stop,
            highest_price=highest_price,
            current_price=current_price
        )
        
        assert new_stop >= current_stop


class TestTakeProfitManager:
    """Tests for TakeProfitManager."""
    
    @pytest.fixture
    def take_profit_manager(self):
        """Create a TakeProfitManager instance."""
        return TakeProfitManager(
            default_profit_percent=0.04,
            risk_reward_ratio=2.0,
            scaling_targets=[
                {"level": 0.50, "at_multiple": 1.0},
                {"level": 0.30, "at_multiple": 2.0},
                {"level": 0.20, "at_multiple": 3.0}
            ]
        )
    
    def test_initialization(self, take_profit_manager):
        """Test take profit manager initialization."""
        assert take_profit_manager.default_profit_percent == 0.04
        assert take_profit_manager.risk_reward_ratio == 2.0
        assert len(take_profit_manager.scaling_targets) == 3
    
    def test_calculate_take_profit(self, take_profit_manager):
        """Test take profit calculation."""
        # Test fixed take profit
        tp = take_profit_manager.calculate_take_profit(
            entry_price=150.0,
            profit_type="fixed"
        )
        assert tp == 156.0
        
        # Test risk-reward ratio
        stop_loss = 145.0
        tp = take_profit_manager.calculate_take_profit(
            entry_price=150.0,
            profit_type="risk_reward",
            stop_loss=stop_loss
        )
        assert tp > 150.0
    
    def test_scaling_targets(self, take_profit_manager):
        """Test scaling targets."""
        entry_price = 150.0
        targets = take_profit_manager.get_scaling_targets(entry_price)
        
        assert len(targets) == 3
        assert targets[0]["price"] == 150.0
        assert targets[1]["price"] > 150.0
        assert targets[2]["price"] > targets[1]["price"]


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""
    
    @pytest.fixture
    def circuit_breaker(self):
        """Create a CircuitBreaker instance."""
        return CircuitBreaker(
            max_loss_per_day=0.05,
            max_loss_per_week=0.10,
            max_loss_per_month=0.15,
            max_positions=10,
            max_trades_per_day=20
        )
    
    def test_initialization(self, circuit_breaker):
        """Test circuit breaker initialization."""
        assert circuit_breaker.max_loss_per_day == 0.05
        assert circuit_breaker.max_loss_per_week == 0.10
        assert circuit_breaker.max_loss_per_month == 0.15
        assert circuit_breaker.max_positions == 10
        assert circuit_breaker.max_trades_per_day == 20
    
    def test_check_loss_limits(self, circuit_breaker):
        """Test loss limit checking."""
        # Test within limits
        assert circuit_breaker.check_loss_limits(0.02) is True
        
        # Test exceeding day limit
        assert circuit_breaker.check_loss_limits(0.06) is False
    
    def test_check_position_limits(self, circuit_breaker):
        """Test position limit checking."""
        # Test within limits
        assert circuit_breaker.check_position_limits(5) is True
        
        # Test exceeding limit
        assert circuit_breaker.check_position_limits(12) is False
    
    def test_check_trade_limits(self, circuit_breaker):
        """Test trade limit checking."""
        # Test within limits
        assert circuit_breaker.check_trade_limits(15) is True
        
        # Test exceeding limit
        assert circuit_breaker.check_trade_limits(25) is False


class TestValueAtRisk:
    """Tests for ValueAtRisk."""
    
    @pytest.fixture
    def var_calculator(self):
        """Create a ValueAtRisk instance."""
        return ValueAtRisk(
            confidence_level=0.95,
            time_horizon=1,
            lookback_period=252
        )
    
    def test_initialization(self, var_calculator):
        """Test VaR calculator initialization."""
        assert var_calculator.confidence_level == 0.95
        assert var_calculator.time_horizon == 1
        assert var_calculator.lookback_period == 252
    
    def test_calculate_historical_var(self, var_calculator):
        """Test historical VaR calculation."""
        # Create sample returns
        returns = np.random.randn(252) * 0.02
        
        var = var_calculator.calculate_historical_var(returns)
        
        assert var > 0
        assert var <= 1.0
    
    def test_calculate_parametric_var(self, var_calculator):
        """Test parametric VaR calculation."""
        # Create sample returns
        returns = np.random.randn(252) * 0.02
        portfolio_value = 100000
        
        var = var_calculator.calculate_parametric_var(returns, portfolio_value)
        
        assert var > 0
        assert var < portfolio_value
    
    def test_calculate_monte_carlo_var(self, var_calculator):
        """Test Monte Carlo VaR calculation."""
        portfolio_value = 100000
        expected_return = 0.05
        volatility = 0.20
        
        var = var_calculator.calculate_monte_carlo_var(
            portfolio_value=portfolio_value,
            expected_return=expected_return,
            volatility=volatility,
            iterations=1000
        )
        
        assert var > 0
        assert var < portfolio_value


class TestRiskIntegration:
    """Integration tests for risk management."""
    
    @pytest.fixture
    def config(self):
        """Get test configuration."""
        return get_config_fixture()
    
    @pytest.fixture
    def risk_manager(self, config):
        """Create a RiskManager instance."""
        return RiskManager(config=config)
    
    @pytest.fixture
    def market_data(self):
        """Get market data for testing."""
        return get_market_data_fixture()
    
    def test_risk_manager_integration(self, risk_manager, market_data):
        """Test risk manager integration with other components."""
        # Convert to DataFrame
        df = pd.DataFrame(market_data)
        
        # Create test position
        position = Position(
            symbol="AAPL",
            quantity=100,
            entry_price=df['close'].iloc[0],
            current_price=df['close'].iloc[-1]
        )
        
        # Test risk checks
        assert risk_manager.check_risk(position) is True
        assert risk_manager.check_drawdown(position) is True
    
    @pytest.mark.asyncio
    async def test_full_risk_workflow(self, risk_manager):
        """Test full risk management workflow."""
        # Create test signal
        signal = Signal(
            symbol="AAPL",
            signal_type=SignalType.BUY,
            price=150.0,
            confidence=0.85,
            timestamp=datetime.now()
        )
        
        # Check risk
        risk_check = await risk_manager.check_risk(signal)
        assert risk_check is True
        
        # Calculate position size
        position_size = await risk_manager.calculate_position_size(signal)
        assert position_size > 0
        
        # Create position
        position = Position(
            symbol="AAPL",
            quantity=position_size,
            entry_price=150.0,
            current_price=150.0
        )
        
        # Check position risk
        assert risk_manager.check_position_risk(position) is True


if __name__ == "__main__":
    pytest.main([__file__])
