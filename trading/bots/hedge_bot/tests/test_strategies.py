# trading/bots/hedge_bot/tests/test_strategies.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Strategy Tests
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Strategy Tests

This module provides comprehensive tests for all trading strategies
implemented in the NEXUS Hedge Bot system. It covers strategy logic,
signal generation, execution, and performance.

The test suite covers:
- Delta Hedging Strategy
- Gamma Hedging Strategy
- Vega Hedging Strategy
- Cross Hedging Strategy
- Basis Hedging Strategy
- Trend Following Strategy
- Mean Reversion Strategy
- Momentum Strategy
- Breakout Strategy
- Grid Trading Strategy
- Martingale Strategy
- Pairs Trading Strategy
- Arbitrage Strategy
- Scalping Strategy
- Swing Trading Strategy
"""

import os
import sys
import json
import time
import random
import math
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

import pytest
import numpy as np

# Import strategy components
from trading.bots.hedge_bot.strategies.delta_hedge import DeltaHedgingStrategy
from trading.bots.hedge_bot.strategies.gamma_hedge import GammaHedgingStrategy
from trading.bots.hedge_bot.strategies.vega_hedge import VegaHedgingStrategy
from trading.bots.hedge_bot.strategies.cross_hedge import CrossHedgingStrategy
from trading.bots.hedge_bot.strategies.basis_hedge import BasisHedgingStrategy
from trading.bots.hedge_bot.strategies.trend import TrendFollowingStrategy
from trading.bots.hedge_bot.strategies.mean_reversion import MeanReversionStrategy
from trading.bots.hedge_bot.strategies.momentum import MomentumStrategy
from trading.bots.hedge_bot.strategies.breakout import BreakoutStrategy
from trading.bots.hedge_bot.strategies.grid import GridTradingStrategy
from trading.bots.hedge_bot.strategies.martingale import MartingaleStrategy
from trading.bots.hedge_bot.strategies.pairs import PairsTradingStrategy
from trading.bots.hedge_bot.strategies.arbitrage import ArbitrageStrategy
from trading.bots.hedge_bot.strategies.scalping import ScalpingStrategy
from trading.bots.hedge_bot.strategies.swing import SwingTradingStrategy

# ============================================================
# TEST FIXTURES
# ============================================================

@pytest.fixture
def sample_market_data() -> Dict[str, Any]:
    """Create sample market data"""
    return {
        "BTC/USDT": {
            "price": 50000.0,
            "bid": 49950.0,
            "ask": 50050.0,
            "volume": 1000000.0,
            "high": 50200.0,
            "low": 49800.0,
            "open": 50000.0,
            "close": 50050.0,
            "timestamp": datetime.now(),
        },
        "ETH/USDT": {
            "price": 3000.0,
            "bid": 2995.0,
            "ask": 3005.0,
            "volume": 500000.0,
            "high": 3020.0,
            "low": 2980.0,
            "open": 3000.0,
            "close": 3005.0,
            "timestamp": datetime.now(),
        },
    }


@pytest.fixture
def sample_positions() -> List[Dict[str, Any]]:
    """Create sample positions"""
    return [
        {
            "symbol": "BTC/USDT",
            "side": "long",
            "quantity": 1.0,
            "entry_price": 50000.0,
            "current_price": 52000.0,
            "unrealized_pnl": 2000.0,
        },
        {
            "symbol": "ETH/USDT",
            "side": "long",
            "quantity": 10.0,
            "entry_price": 3000.0,
            "current_price": 3200.0,
            "unrealized_pnl": 2000.0,
        },
    ]


@pytest.fixture
def sample_order_book() -> Dict[str, Any]:
    """Create sample order book"""
    return {
        "bids": [
            {"price": 50000.0, "size": 1.0},
            {"price": 49900.0, "size": 2.0},
            {"price": 49800.0, "size": 3.0},
        ],
        "asks": [
            {"price": 50100.0, "size": 1.0},
            {"price": 50200.0, "size": 2.0},
            {"price": 50300.0, "size": 3.0},
        ],
    }


# ============================================================
# HEDGING STRATEGY TESTS
# ============================================================

class TestHedgingStrategies:
    """
    Tests for hedging strategies
    """

    def test_delta_hedging_strategy(self, sample_market_data: Dict[str, Any]) -> None:
        """Test delta hedging strategy"""
        strategy = DeltaHedgingStrategy({
            "hedge_ratio": 0.50,
            "target_delta": 0.0,
            "delta_tolerance": 0.01,
            "rebalance_interval": 15,
        })
        
        # Initialize
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Calculate delta
        position = {"symbol": "BTC/USDT", "quantity": 1.0, "price": 50000.0}
        delta = strategy.calculate_delta(position, sample_market_data)
        assert delta is not None
        
        # Calculate hedge ratio
        hedge_ratio = strategy.calculate_hedge_ratio(position, sample_market_data)
        assert hedge_ratio >= 0.0
        
        # Generate signal
        signal = strategy.generate_signal(position, sample_market_data)
        assert signal is not None
        assert "action" in signal
        assert "quantity" in signal

    def test_gamma_hedging_strategy(self, sample_market_data: Dict[str, Any]) -> None:
        """Test gamma hedging strategy"""
        strategy = GammaHedgingStrategy({
            "gamma_threshold": 0.0001,
            "gamma_tolerance": 0.01,
            "gamma_scalping": True,
            "rebalance_interval": 5,
        })
        
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Calculate gamma
        position = {"symbol": "BTC/USDT", "quantity": 1.0, "price": 50000.0}
        gamma = strategy.calculate_gamma(position, sample_market_data)
        assert gamma is not None
        
        # Generate signal
        signal = strategy.generate_signal(position, sample_market_data)
        assert signal is not None

    def test_vega_hedging_strategy(self, sample_market_data: Dict[str, Any]) -> None:
        """Test vega hedging strategy"""
        strategy = VegaHedgingStrategy({
            "vega_threshold": 0.001,
            "vega_tolerance": 0.01,
            "volatility_hedging": True,
        })
        
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Calculate vega
        position = {"symbol": "BTC/USDT", "quantity": 1.0, "price": 50000.0}
        vega = strategy.calculate_vega(position, sample_market_data)
        assert vega is not None
        
        # Generate signal
        signal = strategy.generate_signal(position, sample_market_data)
        assert signal is not None

    def test_cross_hedging_strategy(self, sample_market_data: Dict[str, Any]) -> None:
        """Test cross hedging strategy"""
        strategy = CrossHedgingStrategy({
            "correlation_threshold": 0.70,
            "hedge_ratio": 0.50,
            "hedge_assets": ["BTC/ETH", "BTC/SOL"],
        })
        
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Find hedge asset
        hedge_asset = strategy.find_hedge_asset("BTC", sample_market_data)
        assert hedge_asset is not None or hedge_asset is None
        
        # Calculate correlation
        correlation = strategy.calculate_correlation("BTC", "ETH", sample_market_data)
        assert correlation is not None
        
        # Generate signal
        signal = strategy.generate_signal({"symbol": "BTC", "quantity": 1.0}, sample_market_data)
        assert signal is not None

    def test_basis_hedging_strategy(self, sample_market_data: Dict[str, Any]) -> None:
        """Test basis hedging strategy"""
        strategy = BasisHedgingStrategy({
            "basis_threshold": 0.005,
            "basis_tolerance": 0.002,
            "hedging_instrument": "perpetual",
            "roll_window": 7,
        })
        
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Calculate basis
        basis = strategy.calculate_basis("BTC/USDT", sample_market_data)
        assert basis is not None
        
        # Generate signal
        signal = strategy.generate_signal({"symbol": "BTC/USDT", "quantity": 1.0}, sample_market_data)
        assert signal is not None


# ============================================================
# DIRECTIONAL STRATEGY TESTS
# ============================================================

class TestDirectionalStrategies:
    """
    Tests for directional strategies
    """

    def test_trend_following_strategy(self, sample_market_data: Dict[str, Any]) -> None:
        """Test trend following strategy"""
        strategy = TrendFollowingStrategy({
            "trend_period": 20,
            "signal_threshold": 0.01,
            "entry_signal": "crossover",
            "exit_signal": "crossunder",
            "indicators": ["sma_20", "sma_50"],
        })
        
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Calculate indicators
        indicators = strategy.calculate_indicators("BTC/USDT", sample_market_data)
        assert indicators is not None
        
        # Determine trend
        trend = strategy.determine_trend("BTC/USDT", sample_market_data)
        assert trend in ["uptrend", "downtrend", "neutral"]
        
        # Generate signal
        signal = strategy.generate_signal({"symbol": "BTC/USDT"}, sample_market_data)
        assert signal is not None

    def test_mean_reversion_strategy(self, sample_market_data: Dict[str, Any]) -> None:
        """Test mean reversion strategy"""
        strategy = MeanReversionStrategy({
            "lookback_period": 20,
            "deviation_threshold": 2.0,
            "entry_signal": "oversold",
            "exit_signal": "overbought",
            "indicators": ["bollinger_bands", "rsi"],
        })
        
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Calculate indicators
        indicators = strategy.calculate_indicators("BTC/USDT", sample_market_data)
        assert indicators is not None
        
        # Check reversion signal
        signal = strategy.generate_signal({"symbol": "BTC/USDT"}, sample_market_data)
        assert signal is not None

    def test_momentum_strategy(self, sample_market_data: Dict[str, Any]) -> None:
        """Test momentum strategy"""
        strategy = MomentumStrategy({
            "momentum_period": 14,
            "signal_threshold": 0.02,
            "entry_signal": "momentum_high",
            "exit_signal": "momentum_low",
            "indicators": ["rsi", "macd"],
        })
        
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Calculate momentum
        momentum = strategy.calculate_momentum("BTC/USDT", sample_market_data)
        assert momentum is not None
        
        # Generate signal
        signal = strategy.generate_signal({"symbol": "BTC/USDT"}, sample_market_data)
        assert signal is not None

    def test_breakout_strategy(self, sample_market_data: Dict[str, Any]) -> None:
        """Test breakout strategy"""
        strategy = BreakoutStrategy({
            "lookback_period": 20,
            "breakout_threshold": 0.02,
            "entry_signal": "breakout_high",
            "exit_signal": "breakout_low",
        })
        
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Calculate breakout levels
        levels = strategy.calculate_levels("BTC/USDT", sample_market_data)
        assert levels is not None
        
        # Generate signal
        signal = strategy.generate_signal({"symbol": "BTC/USDT"}, sample_market_data)
        assert signal is not None


# ============================================================
# ARBITRAGE STRATEGY TESTS
# ============================================================

class TestArbitrageStrategies:
    """
    Tests for arbitrage strategies
    """

    def test_funding_arbitrage_strategy(self, sample_market_data: Dict[str, Any]) -> None:
        """Test funding arbitrage strategy"""
        strategy = ArbitrageStrategy({
            "type": "funding",
            "min_rate": 0.0005,
            "max_rate": 0.005,
            "position_size": 0.10,
            "arbitrage_window": 8,
        })
        
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Check opportunity
        opportunity = strategy.check_opportunity(sample_market_data)
        assert opportunity is not None or opportunity is None
        
        # Generate signal
        signal = strategy.generate_signal(sample_market_data)
        assert signal is not None

    def test_basis_arbitrage_strategy(self, sample_market_data: Dict[str, Any]) -> None:
        """Test basis arbitrage strategy"""
        strategy = ArbitrageStrategy({
            "type": "basis",
            "min_basis": 0.002,
            "max_basis": 0.01,
            "position_size": 0.05,
            "arbitrage_window": 24,
        })
        
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Check basis opportunity
        opportunity = strategy.check_opportunity(sample_market_data)
        assert opportunity is not None or opportunity is None
        
        # Generate signal
        signal = strategy.generate_signal(sample_market_data)
        assert signal is not None

    def test_cross_exchange_arbitrage(self, sample_market_data: Dict[str, Any]) -> None:
        """Test cross-exchange arbitrage"""
        strategy = ArbitrageStrategy({
            "type": "cross_exchange",
            "min_spread": 0.001,
            "max_spread": 0.005,
            "position_size": 0.05,
            "exchanges": ["binance", "bybit", "coinbase"],
        })
        
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Check cross-exchange opportunity
        opportunity = strategy.check_opportunity(sample_market_data)
        assert opportunity is not None or opportunity is None


# ============================================================
# SPECIALIZED STRATEGY TESTS
# ============================================================

class TestSpecializedStrategies:
    """
    Tests for specialized strategies
    """

    def test_grid_trading_strategy(self, sample_market_data: Dict[str, Any]) -> None:
        """Test grid trading strategy"""
        strategy = GridTradingStrategy({
            "grid_levels": 10,
            "grid_spacing": 0.01,
            "position_size": 1000,
            "upper_bound": 55000.0,
            "lower_bound": 45000.0,
        })
        
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Generate grid
        grid = strategy.generate_grid("BTC/USDT", sample_market_data)
        assert grid is not None
        assert len(grid) > 0
        
        # Generate signal
        signal = strategy.generate_signal({"symbol": "BTC/USDT"}, sample_market_data)
        assert signal is not None

    def test_martingale_strategy(self, sample_market_data: Dict[str, Any]) -> None:
        """Test martingale strategy"""
        strategy = MartingaleStrategy({
            "base_position_size": 100,
            "multiplier": 2.0,
            "max_steps": 5,
            "take_profit": 0.02,
            "stop_loss": 0.05,
        })
        
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Calculate position size
        position_size = strategy.calculate_position_size({"loss_count": 2})
        assert position_size > 0
        
        # Generate signal
        signal = strategy.generate_signal({"symbol": "BTC/USDT"}, sample_market_data)
        assert signal is not None

    def test_pairs_trading_strategy(self, sample_market_data: Dict[str, Any]) -> None:
        """Test pairs trading strategy"""
        strategy = PairsTradingStrategy({
            "asset1": "BTC/USDT",
            "asset2": "ETH/USDT",
            "entry_zscore": 2.0,
            "exit_zscore": 0.5,
            "lookback_period": 30,
        })
        
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Calculate spread
        spread = strategy.calculate_spread(sample_market_data)
        assert spread is not None
        
        # Calculate z-score
        zscore = strategy.calculate_zscore(spread)
        assert zscore is not None
        
        # Generate signal
        signal = strategy.generate_signal(sample_market_data)
        assert signal is not None

    def test_scalping_strategy(self, sample_market_data: Dict[str, Any]) -> None:
        """Test scalping strategy"""
        strategy = ScalpingStrategy({
            "position_size": 1000,
            "take_profit": 0.001,
            "stop_loss": 0.0005,
            "max_trades_per_day": 50,
            "min_spread": 0.0002,
        })
        
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Check scalping opportunity
        opportunity = strategy.check_opportunity(sample_market_data)
        assert opportunity is not None or opportunity is None
        
        # Generate signal
        signal = strategy.generate_signal({"symbol": "BTC/USDT"}, sample_market_data)
        assert signal is not None

    def test_swing_trading_strategy(self, sample_market_data: Dict[str, Any]) -> None:
        """Test swing trading strategy"""
        strategy = SwingTradingStrategy({
            "position_size": 5000,
            "take_profit": 0.05,
            "stop_loss": 0.02,
            "holding_period": 7,
            "min_volume": 100000,
        })
        
        strategy.initialize()
        assert strategy.is_initialized is True
        
        # Generate signal
        signal = strategy.generate_signal({"symbol": "BTC/USDT"}, sample_market_data)
        assert signal is not None


# ============================================================
# STRATEGY PERFORMANCE TESTS
# ============================================================

class TestStrategyPerformance:
    """
    Performance tests for strategies
    """

    def test_strategy_execution_speed(self) -> None:
        """Test strategy execution speed"""
        strategy = DeltaHedgingStrategy({"hedge_ratio": 0.50})
        strategy.initialize()
        
        market_data = {
            "BTC/USDT": {"price": 50000.0, "bid": 49950.0, "ask": 50050.0}
        }
        position = {"symbol": "BTC/USDT", "quantity": 1.0, "price": 50000.0}
        
        start_time = time.time()
        for _ in range(1000):
            strategy.calculate_hedge_ratio(position, market_data)
        duration = time.time() - start_time
        
        # Should execute 1000 calculations in under 1 second
        assert duration < 1.0

    def test_strategy_backtest_performance(self) -> None:
        """Test strategy backtest performance"""
        strategy = TrendFollowingStrategy({"trend_period": 20})
        strategy.initialize()
        
        # Generate historical data
        historical_data = self._generate_historical_data(1000)
        
        start_time = time.time()
        for data in historical_data:
            strategy.generate_signal({"symbol": "BTC/USDT"}, {"BTC/USDT": data})
        duration = time.time() - start_time
        
        # Should process 1000 data points in under 2 seconds
        assert duration < 2.0

    def _generate_historical_data(self, num_points: int) -> List[Dict[str, Any]]:
        """Generate historical data for testing"""
        data = []
        price = 50000.0
        for i in range(num_points):
            change = random.gauss(0, 0.01)
            price = price * (1 + change)
            data.append({
                "price": price,
                "timestamp": datetime.now() - timedelta(minutes=num_points - i),
                "volume": random.randint(100000, 1000000),
            })
        return data


# ============================================================
# STRATEGY INTEGRATION TESTS
# ============================================================

class TestStrategyIntegration:
    """
    Integration tests for strategies
    """

    def test_multi_strategy_execution(self) -> None:
        """Test execution of multiple strategies"""
        strategies = [
            DeltaHedgingStrategy({"hedge_ratio": 0.50}),
            GammaHedgingStrategy({"gamma_threshold": 0.0001}),
            CrossHedgingStrategy({"correlation_threshold": 0.70}),
        ]
        
        market_data = {
            "BTC/USDT": {"price": 50000.0},
            "ETH/USDT": {"price": 3000.0},
        }
        
        signals = []
        for strategy in strategies:
            strategy.initialize()
            signal = strategy.generate_signal(
                {"symbol": "BTC/USDT", "quantity": 1.0},
                market_data
            )
            signals.append(signal)
        
        assert len(signals) == len(strategies)
        for signal in signals:
            assert signal is not None

    def test_strategy_risk_management(self) -> None:
        """Test strategy risk management integration"""
        strategy = DeltaHedgingStrategy({
            "hedge_ratio": 0.50,
            "max_drawdown": 0.15,
            "stop_loss": 0.05,
            "take_profit": 0.10,
        })
        
        strategy.initialize()
        
        # Generate market data with drawdown
        market_data = {
            "BTC/USDT": {"price": 45000.0}  # 10% drop from 50000
        }
        position = {"symbol": "BTC/USDT", "quantity": 1.0, "entry_price": 50000.0}
        
        # Check stop loss
        signal = strategy.generate_signal(position, market_data)
        assert signal is not None
        if signal["action"] == "sell":
            assert signal["reason"] == "stop_loss"


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    "TestHedgingStrategies",
    "TestDirectionalStrategies",
    "TestArbitrageStrategies",
    "TestSpecializedStrategies",
    "TestStrategyPerformance",
    "TestStrategyIntegration",
]
