"""
Swing Bot Strategy Tests
=========================

This module contains unit tests for the Swing Bot trading strategies.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

from trading.bots.swing_bot.strategies import (
    MomentumStrategy,
    MeanReversionStrategy,
    BreakoutStrategy,
    ReversalStrategy,
    SniperStrategy,
    SwingStrategy
)
from trading.bots.swing_bot.core import Signal, SignalType, OrderSide
from trading.bots.swing_bot.utils.validators import validate_data

from .fixtures import get_market_data_df_fixture


class TestMomentumStrategy:
    """Tests for MomentumStrategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create a MomentumStrategy instance."""
        return MomentumStrategy(
            fast_ma_period=10,
            slow_ma_period=30,
            rsi_period=14,
            threshold=0.02
        )
    
    @pytest.fixture
    def market_data(self):
        """Get market data for testing."""
        return get_market_data_df_fixture()
    
    def test_initialization(self, strategy):
        """Test strategy initialization."""
        assert strategy.fast_ma_period == 10
        assert strategy.slow_ma_period == 30
        assert strategy.rsi_period == 14
        assert strategy.threshold == 0.02
    
    def test_generate_signals(self, strategy, market_data):
        """Test signal generation."""
        signals = strategy.generate_signals(market_data)
        
        assert len(signals) > 0
        assert all(isinstance(s, Signal) for s in signals)
        
        # Check signal types
        signal_types = [s.signal_type for s in signals]
        assert any(t in [SignalType.BUY, SignalType.SELL, SignalType.HOLD] for t in signal_types)
    
    def test_buy_signal_conditions(self, strategy):
        """Test buy signal conditions."""
        # Create data that should trigger a buy signal
        data = pd.DataFrame({
            'close': [100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120],
            'volume': [1000000] * 11
        })
        
        signals = strategy.generate_signals(data)
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        
        assert len(buy_signals) > 0
    
    def test_sell_signal_conditions(self, strategy):
        """Test sell signal conditions."""
        # Create data that should trigger a sell signal
        data = pd.DataFrame({
            'close': [120, 118, 116, 114, 112, 110, 108, 106, 104, 102, 100],
            'volume': [1000000] * 11
        })
        
        signals = strategy.generate_signals(data)
        sell_signals = [s for s in signals if s.signal_type == SignalType.SELL]
        
        assert len(sell_signals) > 0


class TestMeanReversionStrategy:
    """Tests for MeanReversionStrategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create a MeanReversionStrategy instance."""
        return MeanReversionStrategy(
            bb_period=20,
            bb_std_dev=2.0,
            rsi_period=14,
            rsi_oversold=30,
            rsi_overbought=70
        )
    
    @pytest.fixture
    def market_data(self):
        """Get market data for testing."""
        return get_market_data_df_fixture()
    
    def test_initialization(self, strategy):
        """Test strategy initialization."""
        assert strategy.bb_period == 20
        assert strategy.bb_std_dev == 2.0
        assert strategy.rsi_period == 14
        assert strategy.rsi_oversold == 30
        assert strategy.rsi_overbought == 70
    
    def test_generate_signals(self, strategy, market_data):
        """Test signal generation."""
        signals = strategy.generate_signals(market_data)
        
        assert len(signals) > 0
        assert all(isinstance(s, Signal) for s in signals)
    
    def test_mean_reversion_buy(self, strategy):
        """Test mean reversion buy signal."""
        # Create data showing oversold conditions
        data = pd.DataFrame({
            'close': [100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90],
            'volume': [1000000] * 11
        })
        
        signals = strategy.generate_signals(data)
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        
        # Should generate buy signals when oversold
        assert len(buy_signals) > 0
    
    def test_mean_reversion_sell(self, strategy):
        """Test mean reversion sell signal."""
        # Create data showing overbought conditions
        data = pd.DataFrame({
            'close': [90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100],
            'volume': [1000000] * 11
        })
        
        signals = strategy.generate_signals(data)
        sell_signals = [s for s in signals if s.signal_type == SignalType.SELL]
        
        # Should generate sell signals when overbought
        assert len(sell_signals) > 0


class TestBreakoutStrategy:
    """Tests for BreakoutStrategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create a BreakoutStrategy instance."""
        return BreakoutStrategy(
            lookback_period=20,
            breakout_threshold=0.02,
            volume_multiplier=1.5
        )
    
    @pytest.fixture
    def market_data(self):
        """Get market data for testing."""
        return get_market_data_df_fixture()
    
    def test_initialization(self, strategy):
        """Test strategy initialization."""
        assert strategy.lookback_period == 20
        assert strategy.breakout_threshold == 0.02
        assert strategy.volume_multiplier == 1.5
    
    def test_generate_signals(self, strategy, market_data):
        """Test signal generation."""
        signals = strategy.generate_signals(market_data)
        
        assert len(signals) > 0
        assert all(isinstance(s, Signal) for s in signals)
    
    def test_breakout_buy(self, strategy):
        """Test breakout buy signal."""
        # Create data showing a breakout above resistance
        data = pd.DataFrame({
            'high': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 115],
            'close': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 115],
            'volume': [1000000] * 11
        })
        
        signals = strategy.generate_signals(data)
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        
        assert len(buy_signals) > 0
    
    def test_breakout_sell(self, strategy):
        """Test breakout sell signal."""
        # Create data showing a breakout below support
        data = pd.DataFrame({
            'low': [110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 95],
            'close': [110, 109, 108, 107, 106, 105, 104, 103, 102, 101, 95],
            'volume': [1000000] * 11
        })
        
        signals = strategy.generate_signals(data)
        sell_signals = [s for s in signals if s.signal_type == SignalType.SELL]
        
        assert len(sell_signals) > 0


class TestReversalStrategy:
    """Tests for ReversalStrategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create a ReversalStrategy instance."""
        return ReversalStrategy(
            pattern_confidence=0.70,
            divergence_lookback=20,
            volume_confirmation=True
        )
    
    @pytest.fixture
    def market_data(self):
        """Get market data for testing."""
        return get_market_data_df_fixture()
    
    def test_initialization(self, strategy):
        """Test strategy initialization."""
        assert strategy.pattern_confidence == 0.70
        assert strategy.divergence_lookback == 20
        assert strategy.volume_confirmation is True
    
    def test_generate_signals(self, strategy, market_data):
        """Test signal generation."""
        signals = strategy.generate_signals(market_data)
        
        assert len(signals) > 0
        assert all(isinstance(s, Signal) for s in signals)
    
    def test_reversal_pattern_detection(self, strategy):
        """Test reversal pattern detection."""
        # Create data with reversal patterns
        data = pd.DataFrame({
            'open': [100, 101, 102, 103, 104, 105, 104, 103, 102, 101, 100],
            'high': [101, 102, 103, 104, 105, 106, 105, 104, 103, 102, 101],
            'low': [99, 100, 101, 102, 103, 104, 103, 102, 101, 100, 99],
            'close': [100, 101, 102, 103, 104, 105, 104, 103, 102, 101, 100],
            'volume': [1000000] * 11
        })
        
        signals = strategy.generate_signals(data)
        
        # Should detect reversal patterns
        assert len(signals) > 0


class TestSniperStrategy:
    """Tests for SniperStrategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create a SniperStrategy instance."""
        return SniperStrategy(
            precision_threshold=0.01,
            entry_timeout=10,
            max_spread=0.005
        )
    
    @pytest.fixture
    def market_data(self):
        """Get market data for testing."""
        return get_market_data_df_fixture()
    
    def test_initialization(self, strategy):
        """Test strategy initialization."""
        assert strategy.precision_threshold == 0.01
        assert strategy.entry_timeout == 10
        assert strategy.max_spread == 0.005
    
    def test_generate_signals(self, strategy, market_data):
        """Test signal generation."""
        signals = strategy.generate_signals(market_data)
        
        assert len(signals) > 0
        assert all(isinstance(s, Signal) for s in signals)
    
    def test_precision_entry(self, strategy):
        """Test precision entry conditions."""
        # Create data with precise entry conditions
        data = pd.DataFrame({
            'open': [100, 100.5, 101, 101.5, 102, 102.5, 103, 103.5, 104, 104.5, 105],
            'high': [100.5, 101, 101.5, 102, 102.5, 103, 103.5, 104, 104.5, 105, 105.5],
            'low': [99.5, 100, 100.5, 101, 101.5, 102, 102.5, 103, 103.5, 104, 104.5],
            'close': [100, 100.5, 101, 101.5, 102, 102.5, 103, 103.5, 104, 104.5, 105],
            'volume': [1000000] * 11
        })
        
        signals = strategy.generate_signals(data)
        
        # Should generate precise entry signals
        assert len(signals) > 0


class TestSwingStrategy:
    """Tests for SwingStrategy."""
    
    @pytest.fixture
    def strategy(self):
        """Create a SwingStrategy instance."""
        return SwingStrategy(
            min_swing_period=5,
            max_swing_period=30,
            trend_confirmation=True,
            volume_confirmation=True
        )
    
    @pytest.fixture
    def market_data(self):
        """Get market data for testing."""
        return get_market_data_df_fixture()
    
    def test_initialization(self, strategy):
        """Test strategy initialization."""
        assert strategy.min_swing_period == 5
        assert strategy.max_swing_period == 30
        assert strategy.trend_confirmation is True
        assert strategy.volume_confirmation is True
    
    def test_generate_signals(self, strategy, market_data):
        """Test signal generation."""
        signals = strategy.generate_signals(market_data)
        
        assert len(signals) > 0
        assert all(isinstance(s, Signal) for s in signals)
    
    def test_swing_trading_buy(self, strategy):
        """Test swing trading buy signal."""
        # Create data with swing low
        data = pd.DataFrame({
            'high': [105, 106, 107, 108, 107, 106, 105, 104, 103, 102, 101],
            'low': [104, 105, 106, 107, 106, 105, 104, 103, 102, 101, 100],
            'close': [105, 106, 107, 108, 107, 106, 105, 104, 103, 102, 101],
            'volume': [1000000] * 11
        })
        
        signals = strategy.generate_signals(data)
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        
        assert len(buy_signals) > 0
    
    def test_swing_trading_sell(self, strategy):
        """Test swing trading sell signal."""
        # Create data with swing high
        data = pd.DataFrame({
            'high': [101, 102, 103, 104, 105, 106, 107, 108, 107, 106, 105],
            'low': [100, 101, 102, 103, 104, 105, 106, 107, 106, 105, 104],
            'close': [101, 102, 103, 104, 105, 106, 107, 108, 107, 106, 105],
            'volume': [1000000] * 11
        })
        
        signals = strategy.generate_signals(data)
        sell_signals = [s for s in signals if s.signal_type == SignalType.SELL]
        
        assert len(sell_signals) > 0


# Integration tests
class TestStrategyIntegration:
    """Integration tests for strategies."""
    
    @pytest.fixture
    def market_data(self):
        """Get market data for testing."""
        return get_market_data_df_fixture()
    
    def test_strategy_chain(self, market_data):
        """Test chaining multiple strategies."""
        # Create strategies
        momentum = MomentumStrategy()
        mean_reversion = MeanReversionStrategy()
        breakout = BreakoutStrategy()
        
        # Generate signals from each strategy
        momentum_signals = momentum.generate_signals(market_data)
        mean_reversion_signals = mean_reversion.generate_signals(market_data)
        breakout_signals = breakout.generate_signals(market_data)
        
        # Combine signals
        all_signals = momentum_signals + mean_reversion_signals + breakout_signals
        
        # Verify signals
        assert len(all_signals) > 0
        assert all(isinstance(s, Signal) for s in all_signals)
        
        # Check for conflicting signals
        buy_count = sum(1 for s in all_signals if s.signal_type == SignalType.BUY)
        sell_count = sum(1 for s in all_signals if s.signal_type == SignalType.SELL)
        
        assert buy_count >= 0
        assert sell_count >= 0
    
    def test_signal_confidence(self, market_data):
        """Test signal confidence calculation."""
        strategy = SwingStrategy()
        signals = strategy.generate_signals(market_data)
        
        for signal in signals:
            assert 0.0 <= signal.confidence <= 1.0
    
    def test_signal_metadata(self, market_data):
        """Test signal metadata."""
        strategy = SwingStrategy()
        signals = strategy.generate_signals(market_data)
        
        for signal in signals:
            assert hasattr(signal, 'symbol')
            assert hasattr(signal, 'timestamp')
            assert hasattr(signal, 'price')
            assert hasattr(signal, 'reason')
    
    def test_strategy_parameters(self):
        """Test strategy parameter validation."""
        # Valid parameters
        try:
            strategy = SwingStrategy(
                min_swing_period=5,
                max_swing_period=30
            )
            assert strategy.min_swing_period == 5
            assert strategy.max_swing_period == 30
        except ValueError:
            pytest.fail("Valid parameters should not raise ValueError")
        
        # Invalid parameters
        with pytest.raises(ValueError):
            SwingStrategy(min_swing_period=-1)
        
        with pytest.raises(ValueError):
            SwingStrategy(max_swing_period=0)
    
    def test_strategy_performance(self, market_data):
        """Test strategy performance metrics."""
        strategy = MomentumStrategy()
        signals = strategy.generate_signals(market_data)
        
        # Calculate performance metrics
        total_signals = len(signals)
        buy_signals = sum(1 for s in signals if s.signal_type == SignalType.BUY)
        sell_signals = sum(1 for s in signals if s.signal_type == SignalType.SELL)
        
        assert total_signals > 0
        assert buy_signals >= 0
        assert sell_signals >= 0
        
        # Check signal distribution
        total_actionable = buy_signals + sell_signals
        if total_actionable > 0:
            buy_ratio = buy_signals / total_actionable
            assert 0.0 <= buy_ratio <= 1.0


if __name__ == "__main__":
    pytest.main([__file__])
