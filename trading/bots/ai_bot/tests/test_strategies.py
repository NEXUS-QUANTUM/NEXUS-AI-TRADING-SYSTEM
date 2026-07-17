# trading/bots/ai_bot/tests/test_strategies.py
"""
NEXUS AI TRADING SYSTEM - Trading Strategies Test Suite
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Comprehensive test suite for trading strategies used in the AI Bot.
Tests include:
    - Strategy initialization and configuration
    - Strategy execution and performance
    - Technical indicator strategies
    - Machine learning strategies
    - Ensemble strategies
    - Custom strategy development
    - Backtesting and validation
    - Strategy optimization
    - Performance metrics
    - Risk-adjusted returns
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
from dataclasses import dataclass, field

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trading.bots.ai_bot.tests.fixtures import (
    NEXUS_FIXTURES,
    load_all_fixtures,
    get_test_symbols,
    get_test_timeframes,
    FIXTURES_DIR
)
from trading.bots.ai_bot.strategies import (
    BaseStrategy,
    StrategyFactory,
    StrategyRegistry,
    StrategyRunner,
    StrategyOptimizer,
    StrategyBacktester,
    StrategyMetrics,
    MovingAverageCrossover,
    RSIStrategy,
    MACDStrategy,
    BollingerBandsStrategy,
    BreakoutStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    GridTradingStrategy,
    ArbitrageStrategy,
    MartingaleStrategy,
    AIStrategy,
    EnsembleStrategy,
    CustomStrategy
)
from trading.bots.ai_bot.config import BotConfig
from trading.bots.ai_bot.indicators import TechnicalIndicators

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
TEST_SYMBOLS = ['BTC-USD', 'ETH-USD', 'SOL-USD']
TEST_TIMEFRAMES = ['1h', '4h', '1d']
INITIAL_CAPITAL = 100000.0
BACKTEST_DAYS = 30
STRATEGY_PERIODS = [14, 20, 50, 200]


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
def strategy_config():
    """Create strategy configuration."""
    return {
        'strategies': {
            'enabled': ['ma_crossover', 'rsi', 'macd', 'bollinger'],
            'default': 'ma_crossover',
            'optimization': {
                'enabled': True,
                'iterations': 100,
                'metric': 'sharpe_ratio'
            },
            'backtesting': {
                'enabled': True,
                'initial_capital': INITIAL_CAPITAL,
                'commission': 0.001,
                'slippage': 0.001
            }
        },
        'ma_crossover': {
            'fast_period': 20,
            'slow_period': 50,
            'signal_period': 10
        },
        'rsi': {
            'period': 14,
            'overbought': 70,
            'oversold': 30,
            'signal_period': 3
        },
        'macd': {
            'fast_period': 12,
            'slow_period': 26,
            'signal_period': 9
        },
        'bollinger': {
            'period': 20,
            'std_dev': 2,
            'signal_period': 10
        },
        'trading': {
            'symbols': TEST_SYMBOLS,
            'initial_capital': INITIAL_CAPITAL,
            'max_positions': 5,
            'max_risk_per_trade': 0.02
        }
    }


@pytest.fixture
def strategy_metrics():
    """Create strategy metrics collector."""
    return StrategyMetrics()


@pytest.fixture
def backtest_data():
    """Generate backtest data."""
    np.random.seed(42)
    n = 1000
    
    # Generate synthetic price data
    t = np.linspace(0, 100, n)
    trend = 42000 + t * 10
    cycle = 500 * np.sin(t / 10)
    noise = np.random.normal(0, 100, n)
    
    close = trend + cycle + noise
    high = close + np.abs(np.random.normal(50, 30, n))
    low = close - np.abs(np.random.normal(50, 30, n))
    volume = np.random.normal(1000000, 200000, n)
    
    return pd.DataFrame({
        'timestamp': pd.date_range(start='2026-01-01', periods=n, freq='1h'),
        'open': close - np.random.normal(20, 10, n),
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })


# =============================================================================
# Base Strategy Tests
# =============================================================================

class TestBaseStrategy:
    """Test base strategy functionality."""

    def test_strategy_initialization(self, strategy_config):
        """Test strategy initialization."""
        config = BotConfig(**strategy_config)
        strategy = BaseStrategy(config)
        assert strategy is not None
        assert strategy.config is not None
        assert strategy.name == "BaseStrategy"

    def test_strategy_config_validation(self, strategy_config):
        """Test strategy configuration validation."""
        config = BotConfig(**strategy_config)
        strategy = BaseStrategy(config)
        assert strategy.validate_config() is True

    def test_strategy_name(self, strategy_config):
        """Test strategy name handling."""
        config = BotConfig(**strategy_config)
        
        class TestStrategy(BaseStrategy):
            def __init__(self, config):
                super().__init__(config)
                self.name = "TestStrategy"
        
        strategy = TestStrategy(config)
        assert strategy.name == "TestStrategy"

    def test_strategy_parameters(self, strategy_config):
        """Test strategy parameters."""
        config = BotConfig(**strategy_config)
        strategy = BaseStrategy(config)
        
        params = strategy.get_parameters()
        assert params is not None
        assert isinstance(params, dict)


# =============================================================================
# Moving Average Crossover Strategy Tests
# =============================================================================

class TestMovingAverageCrossover:
    """Test Moving Average Crossover strategy."""

    def test_strategy_initialization(self, strategy_config):
        """Test strategy initialization."""
        config = BotConfig(**strategy_config)
        strategy = MovingAverageCrossover(config)
        assert strategy is not None
        assert strategy.fast_period == 20
        assert strategy.slow_period == 50

    def test_generate_signals(self, strategy_config, backtest_data):
        """Test signal generation."""
        config = BotConfig(**strategy_config)
        strategy = MovingAverageCrossover(config)
        
        signals = strategy.generate_signals(backtest_data)
        assert signals is not None
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(backtest_data)
        assert set(signals.unique()) <= {1, 0, -1}  # Buy, Hold, Sell

    def test_crossover_detection(self, strategy_config, backtest_data):
        """Test crossover detection."""
        config = BotConfig(**strategy_config)
        strategy = MovingAverageCrossover(config)
        
        # Calculate moving averages
        fast_ma = backtest_data['close'].rolling(strategy.fast_period).mean()
        slow_ma = backtest_data['close'].rolling(strategy.slow_period).mean()
        
        # Detect crossovers
        crossovers = strategy.detect_crossovers(fast_ma, slow_ma)
        assert crossovers is not None
        assert len(crossovers) == len(backtest_data)

    def test_signal_strength(self, strategy_config, backtest_data):
        """Test signal strength calculation."""
        config = BotConfig(**strategy_config)
        strategy = MovingAverageCrossover(config)
        
        signals = strategy.generate_signals(backtest_data)
        strength = strategy.calculate_signal_strength(signals, backtest_data)
        
        assert strength is not None
        assert 0 <= strength <= 1


# =============================================================================
# RSI Strategy Tests
# =============================================================================

class TestRSIStrategy:
    """Test RSI strategy."""

    def test_strategy_initialization(self, strategy_config):
        """Test strategy initialization."""
        config = BotConfig(**strategy_config)
        strategy = RSIStrategy(config)
        assert strategy is not None
        assert strategy.period == 14
        assert strategy.overbought == 70
        assert strategy.oversold == 30

    def test_generate_signals(self, strategy_config, backtest_data):
        """Test signal generation."""
        config = BotConfig(**strategy_config)
        strategy = RSIStrategy(config)
        
        signals = strategy.generate_signals(backtest_data)
        assert signals is not None
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(backtest_data)

    def test_rsi_calculation(self, strategy_config, backtest_data):
        """Test RSI calculation."""
        config = BotConfig(**strategy_config)
        strategy = RSIStrategy(config)
        
        rsi = strategy.calculate_rsi(backtest_data['close'], strategy.period)
        assert rsi is not None
        assert len(rsi) == len(backtest_data)
        assert rsi.min() >= 0
        assert rsi.max() <= 100

    def test_overbought_oversold_signals(self, strategy_config, backtest_data):
        """Test overbought/oversold signal generation."""
        config = BotConfig(**strategy_config)
        strategy = RSIStrategy(config)
        
        rsi = strategy.calculate_rsi(backtest_data['close'], strategy.period)
        
        # Force overbought condition
        rsi.iloc[-10:] = 80
        
        signals = strategy.generate_signals(backtest_data, rsi)
        assert signals is not None
        assert (signals == -1).any()  # Sell signals for overbought


# =============================================================================
# MACD Strategy Tests
# =============================================================================

class TestMACDStrategy:
    """Test MACD strategy."""

    def test_strategy_initialization(self, strategy_config):
        """Test strategy initialization."""
        config = BotConfig(**strategy_config)
        strategy = MACDStrategy(config)
        assert strategy is not None
        assert strategy.fast_period == 12
        assert strategy.slow_period == 26
        assert strategy.signal_period == 9

    def test_generate_signals(self, strategy_config, backtest_data):
        """Test signal generation."""
        config = BotConfig(**strategy_config)
        strategy = MACDStrategy(config)
        
        signals = strategy.generate_signals(backtest_data)
        assert signals is not None
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(backtest_data)

    def test_macd_calculation(self, strategy_config, backtest_data):
        """Test MACD calculation."""
        config = BotConfig(**strategy_config)
        strategy = MACDStrategy(config)
        
        macd_line, signal_line, histogram = strategy.calculate_macd(
            backtest_data['close'],
            strategy.fast_period,
            strategy.slow_period,
            strategy.signal_period
        )
        
        assert macd_line is not None
        assert signal_line is not None
        assert histogram is not None
        assert len(macd_line) == len(backtest_data)

    def test_histogram_crossovers(self, strategy_config, backtest_data):
        """Test histogram crossover detection."""
        config = BotConfig(**strategy_config)
        strategy = MACDStrategy(config)
        
        macd_line, signal_line, histogram = strategy.calculate_macd(
            backtest_data['close'],
            strategy.fast_period,
            strategy.slow_period,
            strategy.signal_period
        )
        
        signals = strategy.detect_histogram_crossovers(histogram)
        assert signals is not None
        assert len(signals) == len(backtest_data)


# =============================================================================
# Bollinger Bands Strategy Tests
# =============================================================================

class TestBollingerBandsStrategy:
    """Test Bollinger Bands strategy."""

    def test_strategy_initialization(self, strategy_config):
        """Test strategy initialization."""
        config = BotConfig(**strategy_config)
        strategy = BollingerBandsStrategy(config)
        assert strategy is not None
        assert strategy.period == 20
        assert strategy.std_dev == 2

    def test_generate_signals(self, strategy_config, backtest_data):
        """Test signal generation."""
        config = BotConfig(**strategy_config)
        strategy = BollingerBandsStrategy(config)
        
        signals = strategy.generate_signals(backtest_data)
        assert signals is not None
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(backtest_data)

    def test_band_calculation(self, strategy_config, backtest_data):
        """Test Bollinger Bands calculation."""
        config = BotConfig(**strategy_config)
        strategy = BollingerBandsStrategy(config)
        
        upper, middle, lower = strategy.calculate_bands(
            backtest_data['close'],
            strategy.period,
            strategy.std_dev
        )
        
        assert upper is not None
        assert middle is not None
        assert lower is not None
        assert len(upper) == len(backtest_data)
        assert (upper > middle).all()
        assert (lower < middle).all()

    def test_band_signals(self, strategy_config, backtest_data):
        """Test band touch signals."""
        config = BotConfig(**strategy_config)
        strategy = BollingerBandsStrategy(config)
        
        upper, middle, lower = strategy.calculate_bands(
            backtest_data['close'],
            strategy.period,
            strategy.std_dev
        )
        
        signals = strategy.detect_band_touches(
            backtest_data['close'], upper, lower
        )
        assert signals is not None
        assert len(signals) == len(backtest_data)


# =============================================================================
# Breakout Strategy Tests
# =============================================================================

class TestBreakoutStrategy:
    """Test Breakout strategy."""

    def test_strategy_initialization(self, strategy_config):
        """Test strategy initialization."""
        config = BotConfig(**strategy_config)
        strategy = BreakoutStrategy(config)
        assert strategy is not None

    def test_generate_signals(self, strategy_config, backtest_data):
        """Test signal generation."""
        config = BotConfig(**strategy_config)
        strategy = BreakoutStrategy(config)
        
        signals = strategy.generate_signals(backtest_data)
        assert signals is not None
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(backtest_data)

    def test_resistance_breakout(self, strategy_config, backtest_data):
        """Test resistance breakout detection."""
        config = BotConfig(**strategy_config)
        strategy = BreakoutStrategy(config)
        
        # Calculate resistance level
        resistance = backtest_data['high'].rolling(20).max()
        
        signals = strategy.detect_resistance_breakout(
            backtest_data['close'], resistance
        )
        assert signals is not None
        assert len(signals) == len(backtest_data)

    def test_support_breakout(self, strategy_config, backtest_data):
        """Test support breakout detection."""
        config = BotConfig(**strategy_config)
        strategy = BreakoutStrategy(config)
        
        # Calculate support level
        support = backtest_data['low'].rolling(20).min()
        
        signals = strategy.detect_support_breakout(
            backtest_data['close'], support
        )
        assert signals is not None
        assert len(signals) == len(backtest_data)


# =============================================================================
# Mean Reversion Strategy Tests
# =============================================================================

class TestMeanReversionStrategy:
    """Test Mean Reversion strategy."""

    def test_strategy_initialization(self, strategy_config):
        """Test strategy initialization."""
        config = BotConfig(**strategy_config)
        strategy = MeanReversionStrategy(config)
        assert strategy is not None

    def test_generate_signals(self, strategy_config, backtest_data):
        """Test signal generation."""
        config = BotConfig(**strategy_config)
        strategy = MeanReversionStrategy(config)
        
        signals = strategy.generate_signals(backtest_data)
        assert signals is not None
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(backtest_data)

    def test_z_score_calculation(self, strategy_config, backtest_data):
        """Test Z-score calculation."""
        config = BotConfig(**strategy_config)
        strategy = MeanReversionStrategy(config)
        
        z_scores = strategy.calculate_z_scores(
            backtest_data['close'], window=20
        )
        assert z_scores is not None
        assert len(z_scores) == len(backtest_data)

    def test_reversion_signals(self, strategy_config, backtest_data):
        """Test reversion signals."""
        config = BotConfig(**strategy_config)
        strategy = MeanReversionStrategy(config)
        
        z_scores = strategy.calculate_z_scores(
            backtest_data['close'], window=20
        )
        
        signals = strategy.detect_reversion_signals(z_scores)
        assert signals is not None
        assert len(signals) == len(backtest_data)


# =============================================================================
# Momentum Strategy Tests
# =============================================================================

class TestMomentumStrategy:
    """Test Momentum strategy."""

    def test_strategy_initialization(self, strategy_config):
        """Test strategy initialization."""
        config = BotConfig(**strategy_config)
        strategy = MomentumStrategy(config)
        assert strategy is not None

    def test_generate_signals(self, strategy_config, backtest_data):
        """Test signal generation."""
        config = BotConfig(**strategy_config)
        strategy = MomentumStrategy(config)
        
        signals = strategy.generate_signals(backtest_data)
        assert signals is not None
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(backtest_data)

    def test_momentum_calculation(self, strategy_config, backtest_data):
        """Test momentum calculation."""
        config = BotConfig(**strategy_config)
        strategy = MomentumStrategy(config)
        
        momentum = strategy.calculate_momentum(
            backtest_data['close'], period=14
        )
        assert momentum is not None
        assert len(momentum) == len(backtest_data)

    def test_momentum_signals(self, strategy_config, backtest_data):
        """Test momentum signals."""
        config = BotConfig(**strategy_config)
        strategy = MomentumStrategy(config)
        
        momentum = strategy.calculate_momentum(
            backtest_data['close'], period=14
        )
        
        signals = strategy.detect_momentum_signals(momentum)
        assert signals is not None
        assert len(signals) == len(backtest_data)


# =============================================================================
# Grid Trading Strategy Tests
# =============================================================================

class TestGridTradingStrategy:
    """Test Grid Trading strategy."""

    def test_strategy_initialization(self, strategy_config):
        """Test strategy initialization."""
        config = BotConfig(**strategy_config)
        strategy = GridTradingStrategy(config)
        assert strategy is not None

    def test_generate_signals(self, strategy_config, backtest_data):
        """Test signal generation."""
        config = BotConfig(**strategy_config)
        strategy = GridTradingStrategy(config)
        
        signals = strategy.generate_signals(backtest_data)
        assert signals is not None
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(backtest_data)

    def test_grid_levels(self, strategy_config, backtest_data):
        """Test grid level calculation."""
        config = BotConfig(**strategy_config)
        strategy = GridTradingStrategy(config)
        
        levels = strategy.calculate_grid_levels(
            backtest_data['close'],
            grid_size=10,
            range_pct=0.10
        )
        assert levels is not None
        assert len(levels) == 10

    def test_grid_signals(self, strategy_config, backtest_data):
        """Test grid signals."""
        config = BotConfig(**strategy_config)
        strategy = GridTradingStrategy(config)
        
        levels = strategy.calculate_grid_levels(
            backtest_data['close'],
            grid_size=10,
            range_pct=0.10
        )
        
        signals = strategy.detect_grid_signals(
            backtest_data['close'], levels
        )
        assert signals is not None
        assert len(signals) == len(backtest_data)


# =============================================================================
# Strategy Backtesting Tests
# =============================================================================

class TestStrategyBacktester:
    """Test strategy backtester functionality."""

    def test_backtester_initialization(self, strategy_config):
        """Test backtester initialization."""
        config = BotConfig(**strategy_config)
        backtester = StrategyBacktester(config)
        assert backtester is not None
        assert backtester.config is not None

    def test_backtest_execution(self, strategy_config, backtest_data):
        """Test backtest execution."""
        config = BotConfig(**strategy_config)
        backtester = StrategyBacktester(config)
        
        # Create strategy
        strategy = MovingAverageCrossover(config)
        
        # Run backtest
        results = backtester.run_backtest(strategy, backtest_data)
        
        assert results is not None
        assert 'total_return' in results
        assert 'sharpe_ratio' in results
        assert 'max_drawdown' in results
        assert 'win_rate' in results
        assert 'total_trades' in results

    def test_performance_metrics(self, strategy_config, backtest_data):
        """Test performance metrics calculation."""
        config = BotConfig(**strategy_config)
        backtester = StrategyBacktester(config)
        
        # Create strategy
        strategy = MovingAverageCrossover(config)
        
        # Run backtest
        results = backtester.run_backtest(strategy, backtest_data)
        
        # Calculate metrics
        metrics = backtester.calculate_metrics(results)
        
        assert metrics is not None
        assert 'total_return' in metrics
        assert 'annual_return' in metrics
        assert 'volatility' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'max_drawdown' in metrics
        assert 'win_rate' in metrics
        assert 'profit_factor' in metrics

    def test_equity_curve(self, strategy_config, backtest_data):
        """Test equity curve generation."""
        config = BotConfig(**strategy_config)
        backtester = StrategyBacktester(config)
        
        # Create strategy
        strategy = MovingAverageCrossover(config)
        
        # Run backtest
        results = backtester.run_backtest(strategy, backtest_data)
        
        # Generate equity curve
        equity_curve = backtester.generate_equity_curve(results)
        
        assert equity_curve is not None
        assert isinstance(equity_curve, pd.Series)
        assert len(equity_curve) > 0
        assert equity_curve.iloc[0] == INITIAL_CAPITAL


# =============================================================================
# Strategy Optimization Tests
# =============================================================================

class TestStrategyOptimizer:
    """Test strategy optimizer functionality."""

    def test_optimizer_initialization(self, strategy_config):
        """Test optimizer initialization."""
        config = BotConfig(**strategy_config)
        optimizer = StrategyOptimizer(config)
        assert optimizer is not None
        assert optimizer.config is not None

    def test_parameter_optimization(self, strategy_config, backtest_data):
        """Test parameter optimization."""
        config = BotConfig(**strategy_config)
        optimizer = StrategyOptimizer(config)
        
        # Create strategy
        strategy = MovingAverageCrossover(config)
        
        # Define parameter grid
        param_grid = {
            'fast_period': [10, 20, 30],
            'slow_period': [40, 50, 60]
        }
        
        # Run optimization
        best_params = optimizer.optimize(
            strategy, backtest_data, param_grid
        )
        
        assert best_params is not None
        assert 'fast_period' in best_params
        assert 'slow_period' in best_params

    def test_optimization_metric(self, strategy_config, backtest_data):
        """Test optimization metric selection."""
        config = BotConfig(**strategy_config)
        optimizer = StrategyOptimizer(config)
        
        # Different optimization metrics
        metrics = ['sharpe_ratio', 'total_return', 'win_rate', 'profit_factor']
        
        for metric in metrics:
            optimizer.set_optimization_metric(metric)
            assert optimizer.optimization_metric == metric

    def test_bayesian_optimization(self, strategy_config, backtest_data):
        """Test Bayesian optimization."""
        config = BotConfig(**strategy_config)
        optimizer = StrategyOptimizer(config)
        
        # Create strategy
        strategy = MovingAverageCrossover(config)
        
        # Define parameter space
        param_space = {
            'fast_period': [10, 50],
            'slow_period': [30, 100]
        }
        
        # Run Bayesian optimization
        best_params = optimizer.bayesian_optimize(
            strategy, backtest_data, param_space, n_iter=10
        )
        
        assert best_params is not None
        assert len(best_params) > 0


# =============================================================================
# Ensemble Strategy Tests
# =============================================================================

class TestEnsembleStrategy:
    """Test ensemble strategy functionality."""

    def test_ensemble_initialization(self, strategy_config):
        """Test ensemble strategy initialization."""
        config = BotConfig(**strategy_config)
        
        # Create individual strategies
        strategies = [
            MovingAverageCrossover(config),
            RSIStrategy(config),
            MACDStrategy(config)
        ]
        
        # Create ensemble
        ensemble = EnsembleStrategy(config, strategies)
        
        assert ensemble is not None
        assert len(ensemble.strategies) == 3

    def test_ensemble_signals(self, strategy_config, backtest_data):
        """Test ensemble signal generation."""
        config = BotConfig(**strategy_config)
        
        # Create individual strategies
        strategies = [
            MovingAverageCrossover(config),
            RSIStrategy(config),
            MACDStrategy(config)
        ]
        
        # Create ensemble
        ensemble = EnsembleStrategy(config, strategies)
        
        # Generate signals
        signals = ensemble.generate_signals(backtest_data)
        
        assert signals is not None
        assert isinstance(signals, pd.Series)
        assert len(signals) == len(backtest_data)

    def test_voting_mechanism(self, strategy_config, backtest_data):
        """Test voting mechanism."""
        config = BotConfig(**strategy_config)
        
        # Create individual strategies
        strategies = [
            MovingAverageCrossover(config),
            RSIStrategy(config),
            MACDStrategy(config)
        ]
        
        # Create ensemble with voting
        ensemble = EnsembleStrategy(config, strategies, voting_method='majority')
        
        # Generate individual signals
        signals_list = []
        for strategy in strategies:
            signals = strategy.generate_signals(backtest_data)
            signals_list.append(signals)
        
        # Apply voting
        ensemble_signals = ensemble.apply_voting(signals_list)
        
        assert ensemble_signals is not None
        assert len(ensemble_signals) == len(backtest_data)

    def test_weighted_ensemble(self, strategy_config, backtest_data):
        """Test weighted ensemble."""
        config = BotConfig(**strategy_config)
        
        # Create individual strategies
        strategies = [
            MovingAverageCrossover(config),
            RSIStrategy(config),
            MACDStrategy(config)
        ]
        
        # Create weighted ensemble
        weights = [0.5, 0.3, 0.2]
        ensemble = EnsembleStrategy(config, strategies, weights=weights)
        
        # Generate signals
        signals = ensemble.generate_signals(backtest_data)
        
        assert signals is not None
        assert len(signals) == len(backtest_data)


# =============================================================================
# AI Strategy Tests
# =============================================================================

class TestAIStrategy:
    """Test AI-based strategy."""

    def test_ai_strategy_initialization(self, strategy_config):
        """Test AI strategy initialization."""
        config = BotConfig(**strategy_config)
        strategy = AIStrategy(config)
        assert strategy is not None
        assert strategy.config is not None

    def test_generate_signals(self, strategy_config, backtest_data):
        """Test signal generation."""
        config = BotConfig(**strategy_config)
        strategy = AIStrategy(config)
        
        # Mock AI model
        with patch.object(strategy, '_predict') as mock_predict:
            mock_predict.return_value = np.random.choice([1, 0, -1], len(backtest_data))
            
            signals = strategy.generate_signals(backtest_data)
            
            assert signals is not None
            assert isinstance(signals, pd.Series)
            assert len(signals) == len(backtest_data)

    def test_feature_preparation(self, strategy_config, backtest_data):
        """Test feature preparation."""
        config = BotConfig(**strategy_config)
        strategy = AIStrategy(config)
        
        features = strategy.prepare_features(backtest_data)
        assert features is not None
        assert features.shape[0] == len(backtest_data)
        assert features.shape[1] > 0

    def test_model_prediction(self, strategy_config, backtest_data):
        """Test model prediction."""
        config = BotConfig(**strategy_config)
        strategy = AIStrategy(config)
        
        features = strategy.prepare_features(backtest_data)
        
        # Generate predictions
        predictions = strategy._predict(features)
        assert predictions is not None
        assert len(predictions) == len(backtest_data)


# =============================================================================
# Custom Strategy Tests
# =============================================================================

class TestCustomStrategy:
    """Test custom strategy development."""

    def test_custom_strategy_initialization(self, strategy_config):
        """Test custom strategy initialization."""
        config = BotConfig(**strategy_config)
        
        # Create custom strategy class
        class MyCustomStrategy(BaseStrategy):
            def __init__(self, config):
                super().__init__(config)
                self.name = "MyCustomStrategy"
                self.parameters = {'custom_param': 10}
            
            def generate_signals(self, data):
                # Simple custom logic
                signals = pd.Series(0, index=data.index)
                signals[data['close'] > data['close'].rolling(20).mean()] = 1
                signals[data['close'] < data['close'].rolling(20).mean()] = -1
                return signals
        
        strategy = MyCustomStrategy(config)
        assert strategy is not None
        assert strategy.name == "MyCustomStrategy"
        assert strategy.parameters['custom_param'] == 10

    def test_custom_signals(self, strategy_config, backtest_data):
        """Test custom strategy signals."""
        config = BotConfig(**strategy_config)
        
        # Create custom strategy
        class MyCustomStrategy(BaseStrategy):
            def generate_signals(self, data):
                # Custom logic
                signals = pd.Series(0, index=data.index)
                signals[data['close'] > data['close'].rolling(20).mean()] = 1
                signals[data['close'] < data['close'].rolling(20).mean()] = -1
                return signals
        
        strategy = MyCustomStrategy(config)
        signals = strategy.generate_signals(backtest_data)
        
        assert signals is not None
        assert len(signals) == len(backtest_data)
        assert set(signals.unique()) <= {1, 0, -1}


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for strategies."""

    def test_full_strategy_workflow(self, strategy_config, backtest_data):
        """Test full strategy workflow."""
        config = BotConfig(**strategy_config)
        
        # Create strategy
        strategy = MovingAverageCrossover(config)
        
        # Initialize components
        indicators = TechnicalIndicators(config, backtest_data)
        backtester = StrategyBacktester(config)
        
        # Generate signals
        signals = strategy.generate_signals(backtest_data)
        assert signals is not None
        
        # Calculate indicators
        rsi = indicators.rsi('close', 14)
        assert rsi is not None
        
        # Run backtest
        results = backtester.run_backtest(strategy, backtest_data)
        assert results is not None
        
        # Validate results
        assert results['total_trades'] > 0
        assert results['total_return'] is not None

    def test_multi_strategy_comparison(self, strategy_config, backtest_data):
        """Test comparison of multiple strategies."""
        config = BotConfig(**strategy_config)
        
        strategies = [
            MovingAverageCrossover(config),
            RSIStrategy(config),
            MACDStrategy(config)
        ]
        
        backtester = StrategyBacktester(config)
        results = {}
        
        for strategy in strategies:
            result = backtester.run_backtest(strategy, backtest_data)
            results[strategy.name] = result
        
        assert len(results) == len(strategies)
        assert all('total_return' in r for r in results.values())


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Performance tests for strategies."""

    def test_strategy_execution_speed(self, strategy_config, backtest_data):
        """Test strategy execution speed."""
        import time
        
        config = BotConfig(**strategy_config)
        strategy = MovingAverageCrossover(config)
        
        iterations = 100
        start_time = time.time()
        
        for _ in range(iterations):
            strategy.generate_signals(backtest_data)
        
        elapsed = time.time() - start_time
        avg_time = elapsed / iterations
        
        assert avg_time < 0.01  # Less than 10ms
        logger.info(f"Average strategy execution time: {avg_time * 1000:.3f}ms")

    def test_backtest_speed(self, strategy_config, backtest_data):
        """Test backtest speed."""
        import time
        
        config = BotConfig(**strategy_config)
        strategy = MovingAverageCrossover(config)
        backtester = StrategyBacktester(config)
        
        iterations = 10
        start_time = time.time()
        
        for _ in range(iterations):
            backtester.run_backtest(strategy, backtest_data)
        
        elapsed = time.time() - start_time
        avg_time = elapsed / iterations
        
        assert avg_time < 1.0  # Less than 1 second
        logger.info(f"Average backtest time: {avg_time:.3f}s")


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Edge case tests for strategies."""

    def test_insufficient_data(self, strategy_config):
        """Test handling of insufficient data."""
        config = BotConfig(**strategy_config)
        strategy = MovingAverageCrossover(config)
        
        # Create insufficient data
        data = pd.DataFrame({
            'close': [1, 2, 3],
            'high': [2, 3, 4],
            'low': [0, 1, 2],
            'volume': [100, 200, 150]
        })
        
        signals = strategy.generate_signals(data)
        assert signals is not None
        assert len(signals) == len(data)

    def test_constant_price(self, strategy_config):
        """Test handling of constant prices."""
        config = BotConfig(**strategy_config)
        strategy = MovingAverageCrossover(config)
        
        # Create constant price data
        data = pd.DataFrame({
            'close': [100] * 100,
            'high': [101] * 100,
            'low': [99] * 100,
            'volume': [1000] * 100
        })
        
        signals = strategy.generate_signals(data)
        assert signals is not None
        assert len(signals) == len(data)
        assert (signals == 0).all()  # No signals

    def test_missing_columns(self, strategy_config):
        """Test handling of missing columns."""
        config = BotConfig(**strategy_config)
        strategy = MovingAverageCrossover(config)
        
        # Create data with missing columns
        data = pd.DataFrame({
            'close': np.random.randn(100)
        })
        
        with pytest.raises(KeyError):
            strategy.generate_signals(data)


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == '__main__':
    # Run pytest programmatically
    print("=" * 80)
    print("NEXUS AI TRADING SYSTEM - Trading Strategies Test Suite")
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
    print("✅ Trading Strategies Test Suite Complete")
    print("=" * 80)
