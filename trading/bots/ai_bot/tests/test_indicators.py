# trading/bots/ai_bot/tests/test_indicators.py
"""
NEXUS AI TRADING SYSTEM - Technical Indicators Test Suite
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Comprehensive test suite for technical indicators used in the AI Bot.
Tests include:
    - Trend indicators (SMA, EMA, MACD, ADX)
    - Momentum indicators (RSI, Stochastic, CCI, ROC)
    - Volatility indicators (Bollinger Bands, ATR, Standard Deviation)
    - Volume indicators (OBV, MFI, Volume Profile)
    - Custom NEXUS indicators
    - Indicator combinations and crossovers
    - Performance and accuracy tests
    - Edge case handling
"""

import os
import sys
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
import json
import logging
import math

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trading.bots.ai_bot.tests.fixtures import (
    NEXUS_FIXTURES,
    load_all_fixtures,
    get_test_symbols,
    get_test_timeframes,
    FIXTURES_DIR
)
from trading.bots.ai_bot.indicators import (
    TechnicalIndicators,
    TrendIndicators,
    MomentumIndicators,
    VolatilityIndicators,
    VolumeIndicators,
    CustomIndicators,
    IndicatorCalculator,
    IndicatorValidator,
    IndicatorSignal,
    IndicatorRegistry
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
TEST_SYMBOLS = ['BTC-USD', 'ETH-USD', 'SOL-USD']
TEST_PERIODS = [14, 20, 50, 200]
SAMPLE_DATA_LENGTH = 500


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
def sample_price_data():
    """Generate sample price data for testing."""
    np.random.seed(42)
    n = SAMPLE_DATA_LENGTH
    
    # Generate synthetic price data with trends and cycles
    t = np.linspace(0, 100, n)
    trend = 42000 + t * 10  # Uptrend
    cycle = 500 * np.sin(t / 10)  # Cyclical component
    noise = np.random.normal(0, 100, n)  # Random noise
    
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


@pytest.fixture
def indicators(sample_price_data):
    """Create technical indicators instance."""
    config = BotConfig({
        'indicators': {
            'default_period': 14,
            'rsi_period': 14,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'bb_period': 20,
            'bb_std': 2,
            'atr_period': 14
        }
    })
    return TechnicalIndicators(config, sample_price_data)


# =============================================================================
# Technical Indicators Tests
# =============================================================================

class TestTechnicalIndicators:
    """Main test class for technical indicators."""

    def test_indicators_initialization(self, indicators):
        """Test technical indicators initialization."""
        assert indicators is not None
        assert indicators.config is not None
        assert indicators.data is not None
        assert len(indicators.data) > 0

    def test_sma_calculation(self, indicators):
        """Test Simple Moving Average calculation."""
        period = 20
        sma = indicators.sma('close', period)
        
        assert sma is not None
        assert len(sma) == len(indicators.data)
        assert sma.iloc[period-1] == indicators.data['close'].iloc[:period].mean()
        assert not sma.iloc[:period-1].isna().any()

    def test_ema_calculation(self, indicators):
        """Test Exponential Moving Average calculation."""
        period = 20
        ema = indicators.ema('close', period)
        
        assert ema is not None
        assert len(ema) == len(indicators.data)
        assert ema.iloc[0] == indicators.data['close'].iloc[0]
        
        # EMA should smooth price data
        assert ema.std() < indicators.data['close'].std()

    def test_rsi_calculation(self, indicators):
        """Test Relative Strength Index calculation."""
        period = 14
        rsi = indicators.rsi('close', period)
        
        assert rsi is not None
        assert len(rsi) == len(indicators.data)
        assert rsi.min() >= 0
        assert rsi.max() <= 100
        
        # Overbought/Oversold levels
        assert (rsi > 70).any() or (rsi < 30).any()

    def test_macd_calculation(self, indicators):
        """Test MACD calculation."""
        fast = 12
        slow = 26
        signal = 9
        
        macd_line, signal_line, histogram = indicators.macd('close', fast, slow, signal)
        
        assert macd_line is not None
        assert signal_line is not None
        assert histogram is not None
        
        assert len(macd_line) == len(indicators.data)
        assert len(signal_line) == len(indicators.data)
        assert len(histogram) == len(indicators.data)

    def test_bollinger_bands_calculation(self, indicators):
        """Test Bollinger Bands calculation."""
        period = 20
        std_dev = 2
        
        upper, middle, lower = indicators.bollinger_bands('close', period, std_dev)
        
        assert upper is not None
        assert middle is not None
        assert lower is not None
        
        assert len(upper) == len(indicators.data)
        assert len(middle) == len(indicators.data)
        assert len(lower) == len(indicators.data)
        
        # Upper band should be above middle, lower below
        assert (upper > middle).all()
        assert (lower < middle).all()
        
        # Band width should be proportional to volatility
        band_width = upper - lower
        assert band_width.std() > 0

    def test_atr_calculation(self, indicators):
        """Test Average True Range calculation."""
        period = 14
        atr = indicators.atr('high', 'low', 'close', period)
        
        assert atr is not None
        assert len(atr) == len(indicators.data)
        assert atr.min() > 0

    def test_adx_calculation(self, indicators):
        """Test Average Directional Index calculation."""
        period = 14
        adx = indicators.adx('high', 'low', 'close', period)
        
        assert adx is not None
        assert len(adx) == len(indicators.data)
        assert adx.min() >= 0
        assert adx.max() <= 100

    def test_stochastic_calculation(self, indicators):
        """Test Stochastic Oscillator calculation."""
        k_period = 14
        d_period = 3
        
        k, d = indicators.stochastic('high', 'low', 'close', k_period, d_period)
        
        assert k is not None
        assert d is not None
        assert len(k) == len(indicators.data)
        assert len(d) == len(indicators.data)
        assert k.min() >= 0
        assert k.max() <= 100
        assert d.min() >= 0
        assert d.max() <= 100

    def test_cci_calculation(self, indicators):
        """Test Commodity Channel Index calculation."""
        period = 20
        cci = indicators.cci('high', 'low', 'close', period)
        
        assert cci is not None
        assert len(cci) == len(indicators.data)
        assert not cci.isna().all()

    def test_roc_calculation(self, indicators):
        """Test Rate of Change calculation."""
        period = 12
        roc = indicators.roc('close', period)
        
        assert roc is not None
        assert len(roc) == len(indicators.data)
        assert roc.iloc[period] == ((indicators.data['close'].iloc[period] / 
                                     indicators.data['close'].iloc[0] - 1) * 100)

    def test_obv_calculation(self, indicators):
        """Test On-Balance Volume calculation."""
        obv = indicators.obv('close', 'volume')
        
        assert obv is not None
        assert len(obv) == len(indicators.data)
        
        # OBV should change with price direction
        price_change = indicators.data['close'].diff()
        volume = indicators.data['volume']
        
        # Check first few OBV values
        for i in range(1, len(obv)):
            if price_change.iloc[i] > 0:
                assert obv.iloc[i] >= obv.iloc[i-1]
            elif price_change.iloc[i] < 0:
                assert obv.iloc[i] <= obv.iloc[i-1]

    def test_mfi_calculation(self, indicators):
        """Test Money Flow Index calculation."""
        period = 14
        mfi = indicators.mfi('high', 'low', 'close', 'volume', period)
        
        assert mfi is not None
        assert len(mfi) == len(indicators.data)
        assert mfi.min() >= 0
        assert mfi.max() <= 100

    def test_ichimoku_calculation(self, indicators):
        """Test Ichimoku Cloud calculation."""
        tenkan = 9
        kijun = 26
        senkou_b = 52
        
        tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span = indicators.ichimoku(
            'high', 'low', 'close', tenkan, kijun, senkou_b
        )
        
        assert tenkan_sen is not None
        assert kijun_sen is not None
        assert senkou_span_a is not None
        assert senkou_span_b is not None
        assert chikou_span is not None
        
        assert len(tenkan_sen) == len(indicators.data)
        assert len(kijun_sen) == len(indicators.data)

    def test_vwap_calculation(self, indicators):
        """Test Volume Weighted Average Price calculation."""
        vwap = indicators.vwap('high', 'low', 'close', 'volume')
        
        assert vwap is not None
        assert len(vwap) == len(indicators.data)
        assert vwap.min() >= indicators.data['low'].min()
        assert vwap.max() <= indicators.data['high'].max()

    def test_parabolic_sar_calculation(self, indicators):
        """Test Parabolic SAR calculation."""
        step = 0.02
        max_step = 0.2
        
        sar = indicators.parabolic_sar('high', 'low', step, max_step)
        
        assert sar is not None
        assert len(sar) == len(indicators.data)
        assert not sar.isna().all()


class TestTrendIndicators:
    """Test trend indicators."""

    def test_trend_indicators_initialization(self, sample_price_data):
        """Test trend indicators initialization."""
        config = BotConfig({})
        trend = TrendIndicators(config, sample_price_data)
        assert trend is not None

    def test_trend_detection(self, sample_price_data):
        """Test trend detection."""
        config = BotConfig({})
        trend = TrendIndicators(config, sample_price_data)
        
        # Detect trend direction
        direction = trend.detect_trend()
        assert direction in ['up', 'down', 'sideways']
        
        # Get trend strength
        strength = trend.get_trend_strength()
        assert 0 <= strength <= 1

    def test_support_resistance(self, sample_price_data):
        """Test support and resistance levels."""
        config = BotConfig({})
        trend = TrendIndicators(config, sample_price_data)
        
        support, resistance = trend.find_support_resistance(period=50)
        assert support is not None
        assert resistance is not None
        assert support < resistance

    def test_trendline_analysis(self, sample_price_data):
        """Test trendline analysis."""
        config = BotConfig({})
        trend = TrendIndicators(config, sample_price_data)
        
        trendlines = trend.analyze_trendlines()
        assert trendlines is not None
        assert 'up_trendline' in trendlines or 'down_trendline' in trendlines


class TestMomentumIndicators:
    """Test momentum indicators."""

    def test_momentum_initialization(self, sample_price_data):
        """Test momentum indicators initialization."""
        config = BotConfig({})
        momentum = MomentumIndicators(config, sample_price_data)
        assert momentum is not None

    def test_momentum_calculation(self, sample_price_data):
        """Test momentum calculation."""
        config = BotConfig({})
        momentum = MomentumIndicators(config, sample_price_data)
        
        mom = momentum.calculate_momentum(period=14)
        assert mom is not None
        assert len(mom) == len(sample_price_data)

    def test_divergence_detection(self, sample_price_data):
        """Test divergence detection."""
        config = BotConfig({})
        momentum = MomentumIndicators(config, sample_price_data)
        
        # Check for divergences between price and RSI
        divergences = momentum.detect_divergence('rsi', period=14)
        assert divergences is not None
        assert 'bullish_divergence' in divergences or 'bearish_divergence' in divergences

    def test_momentum_score(self, sample_price_data):
        """Test momentum score calculation."""
        config = BotConfig({})
        momentum = MomentumIndicators(config, sample_price_data)
        
        score = momentum.get_momentum_score()
        assert -100 <= score <= 100


class TestVolatilityIndicators:
    """Test volatility indicators."""

    def test_volatility_initialization(self, sample_price_data):
        """Test volatility indicators initialization."""
        config = BotConfig({})
        volatility = VolatilityIndicators(config, sample_price_data)
        assert volatility is not None

    def test_volatility_calculation(self, sample_price_data):
        """Test volatility calculation."""
        config = BotConfig({})
        volatility = VolatilityIndicators(config, sample_price_data)
        
        # Historical volatility
        hist_vol = volatility.historical_volatility(period=30)
        assert hist_vol is not None
        assert len(hist_vol) == len(sample_price_data)
        assert hist_vol.min() >= 0
        
        # GARCH volatility
        garch_vol = volatility.garch_volatility()
        assert garch_vol is not None

    def test_volatility_regime(self, sample_price_data):
        """Test volatility regime detection."""
        config = BotConfig({})
        volatility = VolatilityIndicators(config, sample_price_data)
        
        regime = volatility.detect_volatility_regime()
        assert regime in ['low', 'medium', 'high']


class TestVolumeIndicators:
    """Test volume indicators."""

    def test_volume_initialization(self, sample_price_data):
        """Test volume indicators initialization."""
        config = BotConfig({})
        volume = VolumeIndicators(config, sample_price_data)
        assert volume is not None

    def test_volume_analysis(self, sample_price_data):
        """Test volume analysis."""
        config = BotConfig({})
        volume = VolumeIndicators(config, sample_price_data)
        
        # Volume moving average
        vol_sma = volume.volume_sma(period=20)
        assert vol_sma is not None
        assert len(vol_sma) == len(sample_price_data)
        
        # Volume spike detection
        spikes = volume.detect_volume_spikes(threshold=2.0)
        assert spikes is not None

    def test_volume_price_analysis(self, sample_price_data):
        """Test volume-price analysis."""
        config = BotConfig({})
        volume = VolumeIndicators(config, sample_price_data)
        
        # Volume weighted price
        vwap = volume.volume_weighted_price()
        assert vwap is not None
        
        # Volume profile
        profile = volume.volume_profile()
        assert profile is not None


class TestCustomIndicators:
    """Test NEXUS custom indicators."""

    def test_custom_initialization(self, sample_price_data):
        """Test custom indicators initialization."""
        config = BotConfig({})
        custom = CustomIndicators(config, sample_price_data)
        assert custom is not None

    def test_nexus_trend_signal(self, sample_price_data):
        """Test NEXUS trend signal indicator."""
        config = BotConfig({})
        custom = CustomIndicators(config, sample_price_data)
        
        signal = custom.nexus_trend_signal()
        assert signal is not None
        assert signal in ['buy', 'sell', 'neutral']

    def test_nexus_momentum_score(self, sample_price_data):
        """Test NEXUS momentum score indicator."""
        config = BotConfig({})
        custom = CustomIndicators(config, sample_price_data)
        
        score = custom.nexus_momentum_score()
        assert score is not None
        assert -100 <= score <= 100

    def test_nexus_risk_metric(self, sample_price_data):
        """Test NEXUS risk metric indicator."""
        config = BotConfig({})
        custom = CustomIndicators(config, sample_price_data)
        
        risk = custom.nexus_risk_metric()
        assert risk is not None
        assert 0 <= risk <= 1

    def test_nexus_confidence_score(self, sample_price_data):
        """Test NEXUS confidence score indicator."""
        config = BotConfig({})
        custom = CustomIndicators(config, sample_price_data)
        
        confidence = custom.nexus_confidence_score()
        assert confidence is not None
        assert 0 <= confidence <= 1


class TestIndicatorCalculator:
    """Test indicator calculator utility."""

    def test_calculator_initialization(self):
        """Test calculator initialization."""
        calculator = IndicatorCalculator()
        assert calculator is not None

    def test_basic_calculations(self):
        """Test basic calculations."""
        data = np.random.randn(100)
        
        # Moving average
        ma = IndicatorCalculator.moving_average(data, 10)
        assert ma is not None
        assert len(ma) == len(data)
        
        # Standard deviation
        std = IndicatorCalculator.standard_deviation(data, 10)
        assert std is not None
        assert len(std) == len(data)
        assert std.min() >= 0

    def test_advanced_calculations(self):
        """Test advanced calculations."""
        data = np.random.randn(100)
        
        # Rolling correlation
        corr = IndicatorCalculator.rolling_correlation(data, data[::-1], 20)
        assert corr is not None
        assert len(corr) == len(data)
        assert -1 <= corr.min() <= 1
        assert -1 <= corr.max() <= 1
        
        # Z-score
        z_score = IndicatorCalculator.z_score(data, 20)
        assert z_score is not None
        assert len(z_score) == len(data)


class TestIndicatorValidator:
    """Test indicator validator component."""

    def test_validator_initialization(self):
        """Test validator initialization."""
        validator = IndicatorValidator()
        assert validator is not None

    def test_data_validation(self, sample_price_data):
        """Test data validation."""
        validator = IndicatorValidator()
        
        # Valid data
        valid, errors = validator.validate_data(sample_price_data)
        assert valid is True
        assert len(errors) == 0
        
        # Invalid data - missing columns
        invalid_data = pd.DataFrame({'close': [1, 2, 3]})
        valid, errors = validator.validate_data(invalid_data)
        assert valid is False
        assert len(errors) > 0

    def test_indicator_parameters_validation(self):
        """Test indicator parameters validation."""
        validator = IndicatorValidator()
        
        # Valid parameters
        params = {'period': 14, 'std_dev': 2}
        valid, errors = validator.validate_parameters(params)
        assert valid is True
        assert len(errors) == 0
        
        # Invalid parameters
        params = {'period': -1, 'std_dev': 0}
        valid, errors = validator.validate_parameters(params)
        assert valid is False
        assert len(errors) > 0


class TestIndicatorSignal:
    """Test indicator signal generation."""

    def test_signal_initialization(self):
        """Test signal initialization."""
        signal = IndicatorSignal()
        assert signal is not None

    def test_signal_generation(self, sample_price_data):
        """Test signal generation."""
        signal = IndicatorSignal()
        
        # Generate signals from indicators
        signals = signal.generate_signals(sample_price_data)
        assert signals is not None
        assert 'trend' in signals
        assert 'momentum' in signals
        assert 'volatility' in signals
        assert 'volume' in signals

    def test_signal_confidence(self, sample_price_data):
        """Test signal confidence calculation."""
        signal = IndicatorSignal()
        
        confidence = signal.calculate_confidence(sample_price_data)
        assert confidence is not None
        assert 0 <= confidence <= 1


class TestIndicatorRegistry:
    """Test indicator registry component."""

    def test_registry_initialization(self):
        """Test registry initialization."""
        registry = IndicatorRegistry()
        assert registry is not None

    def test_indicator_registration(self):
        """Test indicator registration."""
        registry = IndicatorRegistry()
        
        # Register indicator
        registry.register('test_indicator', lambda x: x)
        assert 'test_indicator' in registry.get_all()
        
        # Get indicator
        func = registry.get('test_indicator')
        assert func is not None
        assert callable(func)

    def test_indicator_listing(self):
        """Test indicator listing."""
        registry = IndicatorRegistry()
        
        indicators = registry.get_all()
        assert indicators is not None
        assert len(indicators) > 0


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for indicators."""

    def test_full_indicator_suite(self, sample_price_data):
        """Test full indicator suite."""
        config = BotConfig({})
        indicators = TechnicalIndicators(config, sample_price_data)
        
        # Calculate all indicators
        results = indicators.calculate_all()
        assert results is not None
        assert len(results) > 0
        
        # Check indicator consistency
        for name, result in results.items():
            if isinstance(result, (pd.Series, np.ndarray)):
                assert len(result) == len(sample_price_data)

    def test_indicator_combination(self, sample_price_data):
        """Test indicator combinations."""
        config = BotConfig({})
        indicators = TechnicalIndicators(config, sample_price_data)
        
        # Combine multiple indicators
        combined = indicators.combine_indicators(['rsi', 'macd', 'bb'])
        assert combined is not None
        assert 'rsi' in combined
        assert 'macd' in combined
        assert 'bb' in combined

    def test_signal_generation_pipeline(self, sample_price_data):
        """Test complete signal generation pipeline."""
        config = BotConfig({})
        indicators = TechnicalIndicators(config, sample_price_data)
        
        # Generate signals
        signals = indicators.get_trading_signals()
        assert signals is not None
        assert 'overall_signal' in signals
        assert 'confidence' in signals
        assert 'indicators' in signals
        
        # Verify signal types
        assert signals['overall_signal'] in ['buy', 'sell', 'neutral']


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Performance tests for indicators."""

    def test_indicator_calculation_speed(self, sample_price_data):
        """Test indicator calculation speed."""
        import time
        
        config = BotConfig({})
        indicators = TechnicalIndicators(config, sample_price_data)
        
        iterations = 100
        start_time = time.time()
        
        for _ in range(iterations):
            indicators.rsi('close', 14)
            indicators.macd('close', 12, 26, 9)
            indicators.bollinger_bands('close', 20, 2)
        
        elapsed = time.time() - start_time
        avg_time = elapsed / iterations
        
        # Should be under 10ms per indicator set
        assert avg_time < 0.01
        logger.info(f"Average indicator calculation time: {avg_time * 1000:.2f}ms")

    def test_large_dataset_handling(self):
        """Test handling of large datasets."""
        # Generate large dataset
        n = 10000
        data = pd.DataFrame({
            'close': np.random.randn(n) * 100 + 42000,
            'high': np.random.randn(n) * 100 + 42200,
            'low': np.random.randn(n) * 100 + 41800,
            'volume': np.random.randn(n) * 100000 + 1000000
        })
        
        config = BotConfig({})
        indicators = TechnicalIndicators(config, data)
        
        # Calculate indicators on large dataset
        rsi = indicators.rsi('close', 14)
        assert rsi is not None
        assert len(rsi) == n


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Edge case tests for indicators."""

    def test_insufficient_data(self):
        """Test handling of insufficient data."""
        data = pd.DataFrame({
            'close': [1, 2, 3],
            'high': [2, 3, 4],
            'low': [0, 1, 2],
            'volume': [100, 200, 150]
        })
        
        config = BotConfig({})
        indicators = TechnicalIndicators(config, data)
        
        # Should return None or empty for indicators requiring more data
        rsi = indicators.rsi('close', 14)
        assert rsi is not None
        assert rsi.isna().all()

    def test_constant_price_handling(self):
        """Test handling of constant prices."""
        data = pd.DataFrame({
            'close': [42000] * 100,
            'high': [42100] * 100,
            'low': [41900] * 100,
            'volume': [1000000] * 100
        })
        
        config = BotConfig({})
        indicators = TechnicalIndicators(config, data)
        
        # RSI should be 50 (neutral) for constant prices
        rsi = indicators.rsi('close', 14)
        assert rsi.iloc[-1] == 50.0

    def test_zero_volume_handling(self):
        """Test handling of zero volume."""
        data = pd.DataFrame({
            'close': np.random.randn(100) * 100 + 42000,
            'high': np.random.randn(100) * 100 + 42200,
            'low': np.random.randn(100) * 100 + 41800,
            'volume': [0] * 100
        })
        
        config = BotConfig({})
        indicators = TechnicalIndicators(config, data)
        
        # Should handle zero volume gracefully
        obv = indicators.obv('close', 'volume')
        assert obv is not None
        assert (obv == 0).all()

    def test_nan_handling(self):
        """Test handling of NaN values."""
        data = pd.DataFrame({
            'close': np.random.randn(100) * 100 + 42000,
            'high': np.random.randn(100) * 100 + 42200,
            'low': np.random.randn(100) * 100 + 41800,
            'volume': np.random.randn(100) * 100000 + 1000000
        })
        
        # Introduce NaN values
        data.iloc[10:20, :] = np.nan
        
        config = BotConfig({})
        indicators = TechnicalIndicators(config, data)
        
        # Should handle NaN values
        rsi = indicators.rsi('close', 14)
        assert rsi is not None
        assert len(rsi) == len(data)


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == '__main__':
    # Run pytest programmatically
    print("=" * 80)
    print("NEXUS AI TRADING SYSTEM - Technical Indicators Test Suite")
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
    print("✅ Technical Indicators Test Suite Complete")
    print("=" * 80)
