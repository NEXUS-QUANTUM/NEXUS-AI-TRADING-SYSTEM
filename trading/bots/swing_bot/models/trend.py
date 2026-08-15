"""
Swing Bot Trend Model
=======================

This module provides trend analysis models for the Swing Bot trading system.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
import talib


@dataclass
class TrendIndicator:
    """Trend indicator data structure."""
    name: str
    value: float
    timestamp: datetime
    signal_type: Optional[str] = None
    confidence: float = 0.0


@dataclass
class TrendAnalysis:
    """Trend analysis results."""
    direction: str  # 'up', 'down', 'sideways'
    strength: float
    duration: int
    start_price: float
    end_price: float
    slope: float
    r2: float
    indicators: Dict[str, float]
    timestamp: datetime


@dataclass
class TrendSignal:
    """Trend trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    direction: str
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class TrendModel:
    """
    Trend analysis model for market direction.
    
    Analyzes trends using various indicators and methods.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the trend model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.trend_threshold = self.config.get('trend_threshold', 0.02)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.ma_periods = self.config.get('ma_periods', [10, 20, 50, 200])
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze market trends.
        
        Args:
            df: OHLCV data
            
        Returns:
            Trend analysis results
        """
        if len(df) < self.lookback_period:
            return {'indicators': [], 'trend': None, 'signals': []}
        
        # Calculate trend indicators
        indicators = self._calculate_indicators(df)
        
        # Analyze trend
        trend = self._analyze_trend(df, indicators)
        
        # Generate signals
        signals = self._generate_signals(df, trend)
        
        return {
            'indicators': indicators,
            'trend': trend,
            'signals': signals,
            'market_character': self._get_market_character(df, trend)
        }
    
    def _calculate_indicators(self, df: pd.DataFrame) -> List[TrendIndicator]:
        """
        Calculate trend indicators.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of TrendIndicator objects
        """
        indicators = []
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # Moving averages
        for period in self.ma_periods:
            ma = talib.MA(close, timeperiod=period)
            indicators.append(TrendIndicator(
                name=f'ma_{period}',
                value=ma[-1],
                timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
            ))
        
        # ADX (Average Directional Index)
        adx = talib.ADX(high, low, close, timeperiod=14)
        indicators.append(TrendIndicator(
            name='adx',
            value=adx[-1],
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        
        # MACD
        macd, macd_signal, macd_hist = talib.MACD(close)
        indicators.append(TrendIndicator(
            name='macd',
            value=macd[-1],
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        indicators.append(TrendIndicator(
            name='macd_signal',
            value=macd_signal[-1],
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        indicators.append(TrendIndicator(
            name='macd_histogram',
            value=macd_hist[-1],
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        
        # Ichimoku Cloud
        ichimoku = self._calculate_ichimoku(df)
        indicators.append(TrendIndicator(
            name='ichimoku_senkou_a',
            value=ichimoku['senkou_a'][-1],
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        indicators.append(TrendIndicator(
            name='ichimoku_senkou_b',
            value=ichimoku['senkou_b'][-1],
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        indicators.append(TrendIndicator(
            name='ichimoku_tenkan',
            value=ichimoku['tenkan'][-1],
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        indicators.append(TrendIndicator(
            name='ichimoku_kijun',
            value=ichimoku['kijun'][-1],
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        
        # Linear regression
        slope, intercept = MathUtils.linear_regression(
            np.arange(len(close)),
            close
        )
        r2 = MathUtils.r_squared(np.arange(len(close)), close)
        indicators.append(TrendIndicator(
            name='regression_slope',
            value=slope,
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        indicators.append(TrendIndicator(
            name='regression_r2',
            value=r2,
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        
        return indicators
    
    def _calculate_ichimoku(self, df: pd.DataFrame) -> Dict[str, np.ndarray]:
        """
        Calculate Ichimoku Cloud indicators.
        
        Args:
            df: OHLCV data
            
        Returns:
            Dictionary of Ichimoku components
        """
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        # Tenkan-sen (Conversion Line)
        tenkan_period = 9
        tenkan = (talib.MAX(high, tenkan_period) + talib.MIN(low, tenkan_period)) / 2
        
        # Kijun-sen (Base Line)
        kijun_period = 26
        kijun = (talib.MAX(high, kijun_period) + talib.MIN(low, kijun_period)) / 2
        
        # Senkou Span A (Leading Span A)
        senkou_a = (tenkan + kijun) / 2
        senkou_a = np.roll(senkou_a, 26)
        
        # Senkou Span B (Leading Span B)
        senkou_b_period = 52
        senkou_b = (talib.MAX(high, senkou_b_period) + talib.MIN(low, senkou_b_period)) / 2
        senkou_b = np.roll(senkou_b, 26)
        
        return {
            'tenkan': tenkan,
            'kijun': kijun,
            'senkou_a': senkou_a,
            'senkou_b': senkou_b
        }
    
    def _analyze_trend(self, df: pd.DataFrame, indicators: List[TrendIndicator]) -> TrendAnalysis:
        """
        Analyze trend direction and strength.
        
        Args:
            df: OHLCV data
            indicators: List of indicators
            
        Returns:
            TrendAnalysis object
        """
        close = df['close'].values
        indices = np.arange(len(close))
        
        # Get indicator values
        ind_dict = {i.name: i.value for i in indicators}
        
        # Direction analysis
        direction = self._determine_direction(df, ind_dict)
        
        # Strength analysis
        strength = self._calculate_trend_strength(df, ind_dict)
        
        # Duration
        duration = self._calculate_trend_duration(df)
        
        # Slope and R2
        slope, intercept = MathUtils.linear_regression(indices[-self.lookback_period:],
                                                       close[-self.lookback_period:])
        r2 = MathUtils.r_squared(indices[-self.lookback_period:],
                                close[-self.lookback_period:])
        
        return TrendAnalysis(
            direction=direction,
            strength=strength,
            duration=duration,
            start_price=close[-duration] if duration > 0 else close[-1],
            end_price=close[-1],
            slope=slope,
            r2=r2,
            indicators=ind_dict,
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        )
    
    def _determine_direction(self, df: pd.DataFrame, indicators: Dict[str, float]) -> str:
        """
        Determine trend direction.
        
        Args:
            df: OHLCV data
            indicators: Indicator values
            
        Returns:
            Trend direction ('up', 'down', 'sideways')
        """
        close = df['close'].values
        recent_price = close[-1]
        past_price = close[-self.lookback_period] if len(close) > self.lookback_period else close[0]
        
        price_change = (recent_price - past_price) / past_price
        
        # Check ADX for trend strength
        adx = indicators.get('adx', 0)
        
        # Check moving averages
        ma_20 = indicators.get('ma_20', recent_price)
        ma_50 = indicators.get('ma_50', recent_price)
        
        # Check MACD
        macd = indicators.get('macd', 0)
        macd_signal = indicators.get('macd_signal', 0)
        
        # Determine direction
        if abs(price_change) < self.trend_threshold and adx < 25:
            direction = 'sideways'
        elif price_change > self.trend_threshold and recent_price > ma_20 > ma_50:
            direction = 'up'
        elif price_change < -self.trend_threshold and recent_price < ma_20 < ma_50:
            direction = 'down'
        elif macd > macd_signal and recent_price > ma_20:
            direction = 'up'
        elif macd < macd_signal and recent_price < ma_20:
            direction = 'down'
        else:
            direction = 'sideways'
        
        return direction
    
    def _calculate_trend_strength(self, df: pd.DataFrame, indicators: Dict[str, float]) -> float:
        """
        Calculate trend strength.
        
        Args:
            df: OHLCV data
            indicators: Indicator values
            
        Returns:
            Strength score (0-1)
        """
        close = df['close'].values
        indices = np.arange(len(close))
        
        # ADX strength
        adx = indicators.get('adx', 0)
        adx_score = min(adx / 50, 1.0)
        
        # R2 strength
        slope, intercept = MathUtils.linear_regression(indices[-self.lookback_period:],
                                                       close[-self.lookback_period:])
        r2 = MathUtils.r_squared(indices[-self.lookback_period:],
                                 close[-self.lookback_period:])
        r2_score = min(r2 / 0.8, 1.0)
        
        # Moving average alignment
        ma_20 = indicators.get('ma_20', close[-1])
        ma_50 = indicators.get('ma_50', close[-1])
        ma_200 = indicators.get('ma_200', close[-1])
        
        ma_align = 0
        if close[-1] > ma_20 > ma_50:
            ma_align = 1
        elif close[-1] < ma_20 < ma_50:
            ma_align = 1
        else:
            ma_align = 0.5
        
        # MACD strength
        macd = indicators.get('macd', 0)
        macd_signal = indicators.get('macd_signal', 0)
        macd_score = min(abs(macd - macd_signal) / 2, 1.0) if macd != macd_signal else 0
        
        # Weighted average
        strength = (adx_score * 0.3 + r2_score * 0.3 +
                   ma_align * 0.2 + macd_score * 0.2)
        
        return min(max(strength, 0.0), 1.0)
    
    def _calculate_trend_duration(self, df: pd.DataFrame) -> int:
        """
        Calculate trend duration in bars.
        
        Args:
            df: OHLCV data
            
        Returns:
            Trend duration in bars
        """
        close = df['close'].values
        duration = 0
        
        # Find the start of the current trend
        for i in range(len(close) - 1, 0, -1):
            if i > 0:
                diff = close[i] - close[i-1]
                if abs(diff) / close[i-1] > self.trend_threshold:
                    duration += 1
                else:
                    break
        
        return duration
    
    def _generate_signals(self, df: pd.DataFrame, trend: TrendAnalysis) -> List[TrendSignal]:
        """
        Generate trading signals from trend analysis.
        
        Args:
            df: OHLCV data
            trend: Trend analysis
            
        Returns:
            List of TrendSignal objects
        """
        signals = []
        
        if trend.strength < self.confidence_threshold:
            return signals
        
        current_price = df['close'].iloc[-1]
        
        # Generate signals based on trend direction
        if trend.direction == 'up':
            signal_type = 'buy'
            reason = f"Uptrend detected (strength: {trend.strength:.2f})"
            target = current_price * (1 + trend.strength * 0.5)
            stop_loss = current_price * (1 - trend.strength * 0.25)
            
        elif trend.direction == 'down':
            signal_type = 'sell'
            reason = f"Downtrend detected (strength: {trend.strength:.2f})"
            target = current_price * (1 - trend.strength * 0.5)
            stop_loss = current_price * (1 + trend.strength * 0.25)
            
        else:
            return signals
        
        signal = TrendSignal(
            symbol=df.get('symbol', [''])[0] if 'symbol' in df.columns else '',
            timestamp=datetime.now(),
            signal_type=signal_type,
            direction=trend.direction,
            confidence=trend.strength,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            indicators=trend.indicators
        )
        signals.append(signal)
        
        return signals
    
    def _get_market_character(self, df: pd.DataFrame, trend: Optional[TrendAnalysis]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            trend: Trend analysis
            
        Returns:
            Market character description
        """
        if not trend:
            return "No trend detected"
        
        direction_names = {
            'up': 'Bullish',
            'down': 'Bearish',
            'sideways': 'Sideways'
        }
        
        strength_names = {
            'weak': 'Weak',
            'moderate': 'Moderate',
            'strong': 'Strong',
            'very_strong': 'Very Strong'
        }
        
        strength_level = 'weak'
        if trend.strength > 0.75:
            strength_level = 'very_strong'
        elif trend.strength > 0.50:
            strength_level = 'strong'
        elif trend.strength > 0.30:
            strength_level = 'moderate'
        
        return f"{strength_names[strength_level]} {direction_names[trend.direction]} trend"
    
    def get_trend_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get trend statistics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Trend statistics
        """
        close = df['close'].values
        returns = np.diff(np.log(close))
        
        # Calculate trend metrics
        trend_metrics = {
            'current_trend': self._analyze_trend(df, []),
            'returns_mean': np.mean(returns),
            'returns_std': np.std(returns),
            'returns_skew': MathUtils.skewness(returns),
            'returns_kurtosis': MathUtils.kurtosis(returns),
            'auto_correlation': np.corrcoef(returns[:-1], returns[1:])[0, 1],
            'hurst_exponent': MathUtils.hurst_exponent(close)
        }
        
        return trend_metrics


def create_trend_model(config: Optional[Dict[str, Any]] = None) -> TrendModel:
    """
    Create a trend model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        TrendModel instance
    """
    return TrendModel(config)


__all__ = [
    'TrendIndicator',
    'TrendAnalysis',
    'TrendSignal',
    'TrendModel',
    'create_trend_model'
]
