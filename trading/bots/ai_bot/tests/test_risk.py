# trading/bots/ai_bot/tests/test_risk.py
"""
NEXUS AI TRADING SYSTEM - Risk Management Test Suite
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Comprehensive test suite for risk management components.
Tests include:
    - Position sizing and allocation
    - Stop-loss and take-profit management
    - Drawdown control
    - Portfolio risk metrics
    - Risk limits and constraints
    - VaR and CVaR calculations
    - Stress testing
    - Circuit breakers
    - Risk-adjusted performance metrics
    - Correlation and concentration risk
    - Leverage and margin management
"""

import os
import sys
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from unittest.mock import Mock, patch, MagicMock
import json
import logging
import math
from scipy import stats

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trading.bots.ai_bot.tests.fixtures import (
    NEXUS_FIXTURES,
    load_all_fixtures,
    get_test_symbols,
    get_test_timeframes,
    FIXTURES_DIR
)
from trading.bots.ai_bot.risk import (
    RiskManager,
    PositionSizer,
    StopLossManager,
    TakeProfitManager,
    DrawdownController,
    PortfolioRiskAnalyzer,
    VarCalculator,
    CVaRCalculator,
    StressTester,
    CircuitBreaker,
    RiskMetrics,
    RiskLimits,
    RiskCalculator,
    CorrelationAnalyzer,
    ConcentrationAnalyzer,
    LeverageManager,
    MarginManager,
    RiskConfig
)
from trading.bots.ai_bot.config import BotConfig

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test constants
NEXUS_QUANTUM = "NEXUS QUANTUM LTD"
COPYRIGHT = "Copyright © 2026 NEXUS QUANTUM LTD"
CEO = "Dr X..."
TEST_SYMBOLS = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'ADA-USD']
INITIAL_CAPITAL = 100000.0
MAX_POSITIONS = 5
MAX_RISK_PER_TRADE = 0.02
MAX_DRAWDOWN = 0.20
STOP_LOSS = 0.02
TAKE_PROFIT = 0.04
RISK_REWARD_RATIO = 2.0
CONFIDENCE_LEVEL = 0.95


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def fixtures():
    """Load all test fixtures."""
    return load_all_fixtures(force_reload=False)


@pytest.fixture
def test_data(fixtures):
    """Get test data."""
    return fixtures.test_data


@pytest.fixture
def risk_config():
    """Create risk configuration."""
    return {
        'risk': {
            'max_drawdown': MAX_DRAWDOWN,
            'max_positions': MAX_POSITIONS,
            'max_risk_per_trade': MAX_RISK_PER_TRADE,
            'stop_loss': STOP_LOSS,
            'take_profit': TAKE_PROFIT,
            'risk_reward_ratio': RISK_REWARD_RATIO,
            'confidence_level': CONFIDENCE_LEVEL,
            'max_leverage': 1.0,
            'position_concentration': 0.25,
            'daily_loss_limit': 0.05,
            'circuit_breaker_enabled': True,
            'var_enabled': True,
            'stress_test_enabled': True
        },
        'trading': {
            'symbols': TEST_SYMBOLS,
            'initial_capital': INITIAL_CAPITAL,
            'max_positions': MAX_POSITIONS
        }
    }


@pytest.fixture
def risk_manager(risk_config):
    """Create risk manager instance."""
    config = BotConfig(**risk_config)
    return RiskManager(config)


@pytest.fixture
def position_sizer(risk_config):
    """Create position sizer instance."""
    config = BotConfig(**risk_config)
    return PositionSizer(config)


@pytest.fixture
def stop_loss_manager(risk_config):
    """Create stop loss manager instance."""
    config = BotConfig(**risk_config)
    return StopLossManager(config)


@pytest.fixture
def drawdown_controller(risk_config):
    """Create drawdown controller instance."""
    config = BotConfig(**risk_config)
    return DrawdownController(config)


@pytest.fixture
def portfolio_risk_analyzer(risk_config):
    """Create portfolio risk analyzer instance."""
    config = BotConfig(**risk_config)
    return PortfolioRiskAnalyzer(config)


# =============================================================================
# Risk Manager Tests
# =============================================================================

class TestRiskManager:
    """Test risk manager functionality."""

    def test_risk_manager_initialization(self, risk_manager):
        """Test risk manager initialization."""
        assert risk_manager is not None
        assert risk_manager.config is not None
        assert risk_manager.risk_limits is not None
        assert risk_manager.risk_metrics is not None

    def test_validate_trade(self, risk_manager):
        """Test trade validation."""
        trade = {
            'symbol': 'BTC-USD',
            'side': 'buy',
            'quantity': 0.1,
            'price': 43000.0,
            'stop_loss': 42140.0,
            'take_profit': 44720.0
        }
        
        is_valid, errors = risk_manager.validate_trade(trade)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_trade_risk_limits(self, risk_manager):
        """Test trade validation against risk limits."""
        # Over-leveraged trade
        trade = {
            'symbol': 'BTC-USD',
            'side': 'buy',
            'quantity': 10.0,  # Too large
            'price': 43000.0,
            'stop_loss': 42140.0,
            'take_profit': 44720.0
        }
        
        is_valid, errors = risk_manager.validate_trade(trade)
        assert is_valid is False
        assert len(errors) > 0

    def test_risk_limits_check(self, risk_manager):
        """Test risk limits checking."""
        # Check position limit
        current_positions = [
            {'symbol': 'BTC-USD', 'quantity': 0.1},
            {'symbol': 'ETH-USD', 'quantity': 1.0},
            {'symbol': 'SOL-USD', 'quantity': 5.0},
            {'symbol': 'ADA-USD', 'quantity': 100.0},
            {'symbol': 'DOT-USD', 'quantity': 10.0}
        ]
        
        can_open = risk_manager.can_open_position(current_positions)
        assert can_open is False  # Max positions reached

    def test_daily_loss_limit(self, risk_manager):
        """Test daily loss limit enforcement."""
        # Simulate losses
        for i in range(3):
            risk_manager.record_pnl(-1000.0 * i)
        
        can_trade = risk_manager.can_trade_today()
        assert can_trade is False  # Daily loss limit exceeded

    def test_risk_metrics_update(self, risk_manager):
        """Test risk metrics update."""
        # Update with trades
        for i in range(10):
            pnl = np.random.randn() * 100
            risk_manager.record_pnl(pnl)
        
        metrics = risk_manager.get_risk_metrics()
        assert metrics is not None
        assert 'current_risk' in metrics
        assert 'daily_pnl' in metrics
        assert 'drawdown' in metrics
        assert 'sharpe_ratio' in metrics


# =============================================================================
# Position Sizer Tests
# =============================================================================

class TestPositionSizer:
    """Test position sizing functionality."""

    def test_position_sizer_initialization(self, position_sizer):
        """Test position sizer initialization."""
        assert position_sizer is not None
        assert position_sizer.config is not None

    def test_fixed_position_sizing(self, position_sizer):
        """Test fixed position sizing."""
        capital = 100000.0
        risk_per_trade = 0.02
        stop_loss = 0.02
        entry_price = 43000.0
        
        size = position_sizer.calculate_fixed_size(
            capital, risk_per_trade, stop_loss, entry_price
        )
        
        expected_size = capital * risk_per_trade / (stop_loss * entry_price)
        assert size == expected_size
        assert size > 0

    def test_kelly_position_sizing(self, position_sizer):
        """Test Kelly criterion position sizing."""
        win_rate = 0.55
        avg_win = 100.0
        avg_loss = -50.0
        
        kelly_fraction = position_sizer.calculate_kelly(win_rate, avg_win, avg_loss)
        
        # Kelly formula: (win_rate * avg_win - (1-win_rate) * avg_loss) / avg_win
        expected = (0.55 * 100 - 0.45 * 50) / 100
        assert kelly_fraction == expected
        assert 0 <= kelly_fraction <= 1

    def test_risk_parity_sizing(self, position_sizer):
        """Test risk parity position sizing."""
        symbols = TEST_SYMBOLS
        volatilities = {
            'BTC-USD': 0.02,
            'ETH-USD': 0.03,
            'SOL-USD': 0.05,
            'ADA-USD': 0.04
        }
        correlations = np.array([
            [1.0, 0.7, 0.5, 0.6],
            [0.7, 1.0, 0.6, 0.7],
            [0.5, 0.6, 1.0, 0.8],
            [0.6, 0.7, 0.8, 1.0]
        ])
        
        weights = position_sizer.calculate_risk_parity(
            symbols, volatilities, correlations
        )
        
        assert len(weights) == len(symbols)
        assert abs(sum(weights) - 1.0) < 0.01

    def test_volatility_adjusted_sizing(self, position_sizer):
        """Test volatility-adjusted position sizing."""
        capital = 100000.0
        risk_per_trade = 0.02
        volatility = 0.03
        
        size = position_sizer.calculate_volatility_adjusted(
            capital, risk_per_trade, volatility
        )
        
        # Higher volatility = smaller position
        small_volatility = 0.01
        small_size = position_sizer.calculate_volatility_adjusted(
            capital, risk_per_trade, small_volatility
        )
        
        assert size < small_size
        assert size > 0


# =============================================================================
# Stop Loss Tests
# =============================================================================

class TestStopLossManager:
    """Test stop loss management."""

    def test_stop_loss_initialization(self, stop_loss_manager):
        """Test stop loss manager initialization."""
        assert stop_loss_manager is not None
        assert stop_loss_manager.config is not None

    def test_fixed_stop_loss(self, stop_loss_manager):
        """Test fixed stop loss calculation."""
        entry_price = 43000.0
        stop_loss_pct = 0.02
        
        stop_loss = stop_loss_manager.calculate_fixed_stop(
            entry_price, stop_loss_pct
        )
        
        assert stop_loss == entry_price * (1 - stop_loss_pct)
        assert stop_loss < entry_price

    def test_trailing_stop_loss(self, stop_loss_manager):
        """Test trailing stop loss calculation."""
        entry_price = 43000.0
        trailing_pct = 0.02
        current_price = 45000.0
        
        stop_loss = stop_loss_manager.calculate_trailing_stop(
            entry_price, current_price, trailing_pct
        )
        
        expected = current_price * (1 - trailing_pct)
        assert stop_loss == expected
        assert stop_loss > entry_price  # Trailing stop moves up

    def test_dynamic_stop_loss(self, stop_loss_manager):
        """Test dynamic stop loss based on volatility."""
        entry_price = 43000.0
        volatility = 0.03
        
        stop_loss = stop_loss_manager.calculate_dynamic_stop(
            entry_price, volatility
        )
        
        # Higher volatility = wider stop
        low_volatility = 0.01
        narrow_stop = stop_loss_manager.calculate_dynamic_stop(
            entry_price, low_volatility
        )
        
        assert stop_loss < narrow_stop
        assert stop_loss < entry_price

    def test_stop_loss_activation(self, stop_loss_manager):
        """Test stop loss activation."""
        entry_price = 43000.0
        stop_loss = 42140.0
        current_price = 42000.0
        
        triggered = stop_loss_manager.should_trigger_stop(
            entry_price, stop_loss, current_price
        )
        
        assert triggered is True

    def test_volatility_adjusted_stop(self, stop_loss_manager):
        """Test volatility-adjusted stop loss."""
        entry_price = 43000.0
        atr = 500.0
        
        stop_loss = stop_loss_manager.calculate_atr_stop(
            entry_price, atr, multiplier=2.0
        )
        
        expected = entry_price - 2.0 * atr
        assert stop_loss == expected
        assert stop_loss < entry_price


# =============================================================================
# Take Profit Tests
# =============================================================================

class TestTakeProfitManager:
    """Test take profit management."""

    def test_take_profit_initialization(self, risk_config):
        """Test take profit manager initialization."""
        config = BotConfig(**risk_config)
        manager = TakeProfitManager(config)
        assert manager is not None

    def test_fixed_take_profit(self, risk_config):
        """Test fixed take profit calculation."""
        config = BotConfig(**risk_config)
        manager = TakeProfitManager(config)
        
        entry_price = 43000.0
        take_profit_pct = 0.04
        
        take_profit = manager.calculate_fixed_take_profit(
            entry_price, take_profit_pct
        )
        
        assert take_profit == entry_price * (1 + take_profit_pct)
        assert take_profit > entry_price

    def test_risk_reward_take_profit(self, risk_config):
        """Test risk-reward based take profit."""
        config = BotConfig(**risk_config)
        manager = TakeProfitManager(config)
        
        entry_price = 43000.0
        stop_loss = 42140.0
        risk_reward = 2.0
        
        take_profit = manager.calculate_risk_reward_take_profit(
            entry_price, stop_loss, risk_reward
        )
        
        risk = entry_price - stop_loss
        expected = entry_price + risk * risk_reward
        assert take_profit == expected
        assert take_profit > entry_price

    def test_fibonacci_take_profit(self, risk_config):
        """Test Fibonacci-based take profit."""
        config = BotConfig(**risk_config)
        manager = TakeProfitManager(config)
        
        entry_price = 43000.0
        high = 45000.0
        low = 42000.0
        level = 0.618  # Fibonacci retracement
        
        take_profit = manager.calculate_fibonacci_take_profit(
            high, low, entry_price, level
        )
        
        assert take_profit > entry_price
        assert take_profit < high


# =============================================================================
# Drawdown Controller Tests
# =============================================================================

class TestDrawdownController:
    """Test drawdown control functionality."""

    def test_drawdown_initialization(self, drawdown_controller):
        """Test drawdown controller initialization."""
        assert drawdown_controller is not None
        assert drawdown_controller.config is not None
        assert drawdown_controller.max_drawdown == MAX_DRAWDOWN

    def test_drawdown_calculation(self, drawdown_controller):
        """Test drawdown calculation."""
        equity_curve = [100000.0, 105000.0, 98000.0, 95000.0, 102000.0]
        
        max_drawdown = drawdown_controller.calculate_max_drawdown(equity_curve)
        
        # Peak = 105000, Trough = 95000, Drawdown = (105000 - 95000) / 105000
        expected_drawdown = (105000 - 95000) / 105000
        assert max_drawdown == expected_drawdown

    def test_drawdown_limit_exceeded(self, drawdown_controller):
        """Test drawdown limit exceed detection."""
        equity_curve = [100000.0, 110000.0, 85000.0, 82000.0]
        
        exceeded = drawdown_controller.is_drawdown_exceeded(equity_curve)
        assert exceeded is True

    def test_drawdown_recovery(self, drawdown_controller):
        """Test drawdown recovery."""
        equity_curve = [100000.0, 90000.0, 95000.0, 102000.0]
        
        recovery = drawdown_controller.calculate_drawdown_recovery(equity_curve)
        assert recovery is not None
        assert 'recovery_time' in recovery
        assert 'recovery_rate' in recovery


# =============================================================================
# VaR and CVaR Tests
# =============================================================================

class TestVaRCalculator:
    """Test Value at Risk calculation."""

    def test_var_initialization(self, risk_config):
        """Test VaR calculator initialization."""
        config = BotConfig(**risk_config)
        var_calc = VarCalculator(config)
        assert var_calc is not None

    def test_historical_var(self, risk_config):
        """Test historical VaR calculation."""
        config = BotConfig(**risk_config)
        var_calc = VarCalculator(config)
        
        # Generate historical returns
        returns = np.random.normal(0, 0.02, 1000)
        
        var = var_calc.calculate_historical_var(returns, confidence=0.95)
        
        assert var is not None
        assert var > 0

    def test_parametric_var(self, risk_config):
        """Test parametric VaR calculation."""
        config = BotConfig(**risk_config)
        var_calc = VarCalculator(config)
        
        # Generate historical returns
        returns = np.random.normal(0.001, 0.02, 1000)
        
        var = var_calc.calculate_parametric_var(returns, confidence=0.95)
        
        assert var is not None
        assert var > 0

    def test_monte_carlo_var(self, risk_config):
        """Test Monte Carlo VaR calculation."""
        config = BotConfig(**risk_config)
        var_calc = VarCalculator(config)
        
        # Generate historical returns
        returns = np.random.normal(0.001, 0.02, 1000)
        
        var = var_calc.calculate_monte_carlo_var(
            returns, confidence=0.95, n_simulations=10000
        )
        
        assert var is not None
        assert var > 0


class TestCVaRCalculator:
    """Test Conditional Value at Risk calculation."""

    def test_cvar_initialization(self, risk_config):
        """Test CVaR calculator initialization."""
        config = BotConfig(**risk_config)
        cvar_calc = CVaRCalculator(config)
        assert cvar_calc is not None

    def test_cvar_calculation(self, risk_config):
        """Test CVaR calculation."""
        config = BotConfig(**risk_config)
        cvar_calc = CVaRCalculator(config)
        
        # Generate returns with VaR
        returns = np.random.normal(0, 0.02, 1000)
        var = np.percentile(returns, 5)  # 95% VaR
        
        cvar = cvar_calc.calculate_cvar(returns, confidence=0.95)
        
        assert cvar is not None
        assert cvar <= var  # CVaR should be more extreme than VaR


# =============================================================================
# Stress Testing Tests
# =============================================================================

class TestStressTester:
    """Test stress testing functionality."""

    def test_stress_tester_initialization(self, risk_config):
        """Test stress tester initialization."""
        config = BotConfig(**risk_config)
        tester = StressTester(config)
        assert tester is not None

    def test_scenario_analysis(self, risk_config):
        """Test scenario analysis."""
        config = BotConfig(**risk_config)
        tester = StressTester(config)
        
        portfolio = {
            'BTC-USD': {'value': 50000.0, 'quantity': 1.0},
            'ETH-USD': {'value': 30000.0, 'quantity': 10.0},
            'SOL-USD': {'value': 20000.0, 'quantity': 100.0}
        }
        
        scenarios = {
            'crypto_crash': {'BTC-USD': -0.30, 'ETH-USD': -0.40, 'SOL-USD': -0.50},
            'flash_crash': {'BTC-USD': -0.20, 'ETH-USD': -0.15, 'SOL-USD': -0.25}
        }
        
        results = tester.run_scenario_analysis(portfolio, scenarios)
        
        assert results is not None
        assert len(results) == len(scenarios)
        assert 'crypto_crash' in results
        assert 'flash_crash' in results

    def test_monte_carlo_stress(self, risk_config):
        """Test Monte Carlo stress testing."""
        config = BotConfig(**risk_config)
        tester = StressTester(config)
        
        portfolio = {
            'BTC-USD': {'value': 50000.0, 'quantity': 1.0},
            'ETH-USD': {'value': 30000.0, 'quantity': 10.0}
        }
        
        results = tester.run_monte_carlo_stress(
            portfolio, n_simulations=1000, time_horizon=252
        )
        
        assert results is not None
        assert 'value_at_risk' in results
        assert 'expected_shortfall' in results
        assert 'max_loss' in results


# =============================================================================
# Circuit Breaker Tests
# =============================================================================

class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_initialization(self, risk_config):
        """Test circuit breaker initialization."""
        config = BotConfig(**risk_config)
        breaker = CircuitBreaker(config)
        assert breaker is not None

    def test_circuit_breaker_states(self, risk_config):
        """Test circuit breaker states."""
        config = BotConfig(**risk_config)
        breaker = CircuitBreaker(config)
        
        # Initial state
        assert breaker.state == 'closed'
        
        # Trip circuit
        breaker.trip()
        assert breaker.state == 'open'
        
        # Reset circuit
        breaker.reset()
        assert breaker.state == 'closed'

    def test_circuit_breaker_conditions(self, risk_config):
        """Test circuit breaker triggering conditions."""
        config = BotConfig(**risk_config)
        breaker = CircuitBreaker(config)
        
        # Simulate error conditions
        for i in range(10):
            breaker.record_failure()
        
        assert breaker.should_trip() is True
        assert breaker.state == 'open'

    def test_circuit_breaker_recovery(self, risk_config):
        """Test circuit breaker recovery."""
        config = BotConfig(**risk_config)
        breaker = CircuitBreaker(config)
        
        # Trip circuit
        breaker.trip()
        assert breaker.state == 'open'
        
        # Wait for recovery
        with patch('time.time') as mock_time:
            mock_time.return_value = time.time() + 60  # 60 seconds later
            breaker.check_recovery()
            assert breaker.state == 'half_open'


# =============================================================================
# Portfolio Risk Tests
# =============================================================================

class TestPortfolioRiskAnalyzer:
    """Test portfolio risk analysis."""

    def test_portfolio_risk_initialization(self, portfolio_risk_analyzer):
        """Test portfolio risk analyzer initialization."""
        assert portfolio_risk_analyzer is not None
        assert portfolio_risk_analyzer.config is not None

    def test_portfolio_risk_metrics(self, portfolio_risk_analyzer):
        """Test portfolio risk metrics calculation."""
        portfolio = {
            'BTC-USD': {'value': 50000.0, 'quantity': 1.0, 'price': 50000.0},
            'ETH-USD': {'value': 30000.0, 'quantity': 10.0, 'price': 3000.0},
            'SOL-USD': {'value': 20000.0, 'quantity': 100.0, 'price': 200.0}
        }
        
        metrics = portfolio_risk_analyzer.calculate_risk_metrics(portfolio)
        
        assert metrics is not None
        assert 'total_value' in metrics
        assert 'concentration' in metrics
        assert 'diversification_score' in metrics
        assert 'beta' in metrics

    def test_concentration_analysis(self, portfolio_risk_analyzer):
        """Test concentration risk analysis."""
        portfolio = {
            'BTC-USD': {'value': 80000.0},
            'ETH-USD': {'value': 10000.0},
            'SOL-USD': {'value': 5000.0},
            'ADA-USD': {'value': 5000.0}
        }
        
        concentration = portfolio_risk_analyzer.analyze_concentration(portfolio)
        
        assert concentration is not None
        assert 'top_holding' in concentration
        assert 'concentration_ratio' in concentration
        assert 'herfindahl_index' in concentration

    def test_correlation_analysis(self, portfolio_risk_analyzer):
        """Test correlation analysis."""
        returns_data = {
            'BTC-USD': np.random.normal(0, 0.02, 100),
            'ETH-USD': np.random.normal(0, 0.03, 100),
            'SOL-USD': np.random.normal(0, 0.04, 100)
        }
        
        correlations = portfolio_risk_analyzer.calculate_correlations(returns_data)
        
        assert correlations is not None
        assert isinstance(correlations, pd.DataFrame)
        assert correlations.shape == (3, 3)


# =============================================================================
# Leverage and Margin Tests
# =============================================================================

class TestLeverageManager:
    """Test leverage management."""

    def test_leverage_initialization(self, risk_config):
        """Test leverage manager initialization."""
        config = BotConfig(**risk_config)
        manager = LeverageManager(config)
        assert manager is not None

    def test_leverage_calculation(self, risk_config):
        """Test leverage calculation."""
        config = BotConfig(**risk_config)
        manager = LeverageManager(config)
        
        portfolio_value = 100000.0
        loan_amount = 50000.0
        
        leverage = manager.calculate_leverage(portfolio_value, loan_amount)
        assert leverage == 1.5  # 1.5x leverage

    def test_max_leverage_limit(self, risk_config):
        """Test maximum leverage limit."""
        config = BotConfig(**risk_config)
        manager = LeverageManager(config)
        
        max_leverage = manager.get_max_leverage()
        assert max_leverage == config.get('risk', {}).get('max_leverage', 1.0)


class TestMarginManager:
    """Test margin management."""

    def test_margin_initialization(self, risk_config):
        """Test margin manager initialization."""
        config = BotConfig(**risk_config)
        manager = MarginManager(config)
        assert manager is not None

    def test_margin_requirement(self, risk_config):
        """Test margin requirement calculation."""
        config = BotConfig(**risk_config)
        manager = MarginManager(config)
        
        position_value = 100000.0
        margin_requirement = manager.calculate_margin_requirement(position_value)
        
        assert margin_requirement > 0
        assert margin_requirement <= position_value

    def test_margin_call(self, risk_config):
        """Test margin call detection."""
        config = BotConfig(**risk_config)
        manager = MarginManager(config)
        
        # Simulate margin call condition
        equity = 50000.0
        margin_required = 60000.0
        
        should_call = manager.should_margin_call(equity, margin_required)
        assert should_call is True


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for risk management."""

    def test_full_risk_pipeline(self, risk_manager, test_data):
        """Test full risk management pipeline."""
        # Simulate trading
        for i in range(20):
            # Generate random trade
            trade = {
                'symbol': np.random.choice(TEST_SYMBOLS),
                'side': 'buy' if np.random.random() > 0.5 else 'sell',
                'quantity': np.random.uniform(0.01, 0.5),
                'price': np.random.uniform(40000, 50000),
                'stop_loss': 0.02,
                'take_profit': 0.04
            }
            
            # Validate trade
            is_valid, errors = risk_manager.validate_trade(trade)
            
            if is_valid:
                # Record PnL
                pnl = np.random.randn() * 100
                risk_manager.record_pnl(pnl)
        
        # Get risk metrics
        metrics = risk_manager.get_risk_metrics()
        assert metrics is not None
        assert 'current_risk' in metrics
        assert 'drawdown' in metrics
        assert 'win_rate' in metrics


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Performance tests for risk management."""

    def test_risk_calculation_speed(self, risk_manager):
        """Test risk calculation speed."""
        import time
        
        iterations = 1000
        trades = []
        
        for i in range(iterations):
            trade = {
                'symbol': np.random.choice(TEST_SYMBOLS),
                'side': 'buy' if np.random.random() > 0.5 else 'sell',
                'quantity': np.random.uniform(0.01, 0.5),
                'price': np.random.uniform(40000, 50000),
                'stop_loss': 0.02,
                'take_profit': 0.04
            }
            trades.append(trade)
        
        start_time = time.time()
        
        for trade in trades:
            risk_manager.validate_trade(trade)
        
        elapsed = time.time() - start_time
        avg_time = elapsed / iterations
        
        assert avg_time < 0.001  # Less than 1ms per validation
        logger.info(f"Average risk validation time: {avg_time * 1000:.3f}ms")


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Edge case tests for risk management."""

    def test_zero_price(self, risk_manager):
        """Test handling of zero price."""
        trade = {
            'symbol': 'BTC-USD',
            'side': 'buy',
            'quantity': 0.1,
            'price': 0,
            'stop_loss': 0.02,
            'take_profit': 0.04
        }
        
        is_valid, errors = risk_manager.validate_trade(trade)
        assert is_valid is False
        assert len(errors) > 0

    def test_negative_quantity(self, risk_manager):
        """Test handling of negative quantity."""
        trade = {
            'symbol': 'BTC-USD',
            'side': 'buy',
            'quantity': -0.1,
            'price': 43000.0,
            'stop_loss': 0.02,
            'take_profit': 0.04
        }
        
        is_valid, errors = risk_manager.validate_trade(trade)
        assert is_valid is False
        assert len(errors) > 0

    def test_extreme_volatility(self, risk_manager):
        """Test handling of extreme volatility."""
        trade = {
            'symbol': 'BTC-USD',
            'side': 'buy',
            'quantity': 0.1,
            'price': 43000.0,
            'volatility': 0.50,
            'stop_loss': 0.02,
            'take_profit': 0.04
        }
        
        # Should adjust risk based on volatility
        risk_metric = risk_manager.calculate_risk_metric(trade)
        assert risk_metric is not None
        assert risk_metric > 0


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == '__main__':
    # Run pytest programmatically
    print("=" * 80)
    print("NEXUS AI TRADING SYSTEM - Risk Management Test Suite")
    print("=" * 80)
    print(f"Copyright: {COPYRIGHT}")
    print(f"CEO: {CEO}")
    print("-" * 80)
    
    # Run all tests
    pytest.main([
        __file__,
        '-v',
        '--tb=short',
        '--maxfail=1',
        '-x'
    ])
    
    print("\n" + "=" * 80)
    print("✅ Risk Management Test Suite Complete")
    print("=" * 80)
