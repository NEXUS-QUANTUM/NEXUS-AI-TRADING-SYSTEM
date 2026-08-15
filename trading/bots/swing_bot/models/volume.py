"""
Swing Bot Volume Model
=======================

This module provides volume analysis models for the Swing Bot trading system.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
import talib


@dataclass
class VolumeIndicator:
    """Volume indicator data structure."""
    name: str
    value: float
    timestamp: datetime
    signal_type: Optional[str] = None
    confidence: float = 0.0


@dataclass
class VolumePattern:
    """Volume pattern data structure."""
    pattern_type: str  # 'volume_spike', 'volume_climax', 'volume_divergence'
    direction: str  # 'bullish', 'bearish', 'neutral'
    start_date: datetime
    end_date: datetime
    volume_ratio: float
    price_change: float
    confidence: float


@dataclass
class VolumeSignal:
    """Volume trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    pattern_type: str
    confidence: float
    price: float
    volume: float
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class VolumeModel:
    """
    Volume analysis model for market activity.
    
    Analyzes volume patterns, indicators, and signals.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the volume model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.min_volume = self.config.get('min_volume', 100000)
        self.lookback_period = self.config.get('lookback_period', 20)
        self.volume_spike_threshold = self.config.get('volume_spike_threshold', 2.0)
        self.volume_climax_threshold = self.config.get('volume_climax_threshold', 3.0)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze volume patterns and indicators.
        
        Args:
            df: OHLCV data
            
        Returns:
            Volume analysis results
        """
        if len(df) < self.lookback_period:
            return {'indicators': [], 'patterns': [], 'signals': []}
        
        # Calculate volume indicators
        indicators = self._calculate_indicators(df)
        
        # Detect volume patterns
        patterns = self._detect_patterns(df)
        
        # Generate signals
        signals = self._generate_signals(df, patterns)
        
        return {
            'indicators': indicators,
            'patterns': patterns,
            'signals': signals,
            'current_volume': df['volume'].iloc[-1],
            'volume_ma': df['volume'].rolling(self.lookback_period).mean().iloc[-1],
            'volume_ratio': df['volume'].iloc[-1] / df['volume'].rolling(self.lookback_period).mean().iloc[-1],
            'market_character': self._get_market_character(df, patterns)
        }
    
    def _calculate_indicators(self, df: pd.DataFrame) -> List[VolumeIndicator]:
        """
        Calculate volume indicators.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of VolumeIndicator objects
        """
        indicators = []
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values
        
        # On-Balance Volume (OBV)
        obv = talib.OBV(close, volume)
        indicators.append(VolumeIndicator(
            name='obv',
            value=obv[-1],
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        
        # Chaikin Money Flow (CMF)
        cmf = talib.ADOSC(high, low, close, volume, fastperiod=3, slowperiod=10)
        indicators.append(VolumeIndicator(
            name='cmf',
            value=cmf[-1],
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        
        # Money Flow Index (MFI)
        mfi = talib.MFI(high, low, close, volume, timeperiod=14)
        indicators.append(VolumeIndicator(
            name='mfi',
            value=mfi[-1],
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        
        # Volume Weighted Average Price (VWAP)
        vwap = self._calculate_vwap(df)
        indicators.append(VolumeIndicator(
            name='vwap',
            value=vwap,
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        
        # Accumulation/Distribution Line
        ad = talib.AD(high, low, close, volume)
        indicators.append(VolumeIndicator(
            name='ad_line',
            value=ad[-1],
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        
        # Volume Velocity
        vol_vel = self._calculate_volume_velocity(volume)
        indicators.append(VolumeIndicator(
            name='volume_velocity',
            value=vol_vel,
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        
        return indicators
    
    def _calculate_vwap(self, df: pd.DataFrame) -> float:
        """
        Calculate Volume Weighted Average Price.
        
        Args:
            df: OHLCV data
            
        Returns:
            VWAP value
        """
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = np.sum(typical_price * df['volume']) / np.sum(df['volume'])
        return vwap
    
    def _calculate_volume_velocity(self, volume: np.ndarray) -> float:
        """
        Calculate volume velocity (rate of change).
        
        Args:
            volume: Volume array
            
        Returns:
            Volume velocity
        """
        if len(volume) < 10:
            return 0.0
        
        recent_avg = np.mean(volume[-5:])
        past_avg = np.mean(volume[-10:-5])
        
        if past_avg == 0:
            return 0.0
        
        return (recent_avg - past_avg) / past_avg
    
    def _detect_patterns(self, df: pd.DataFrame) -> List[VolumePattern]:
        """
        Detect volume patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of VolumePattern objects
        """
        patterns = []
        volume = df['volume'].values
        close = df['close'].values
        timestamps = df.index if isinstance(df.index, pd.DatetimeIndex) else [datetime.now()] * len(df)
        
        # Volume spike
        spike_patterns = self._detect_volume_spikes(df)
        patterns.extend(spike_patterns)
        
        # Volume climax
        climax_patterns = self._detect_volume_climax(df)
        patterns.extend(climax_patterns)
        
        # Volume divergence
        divergence_patterns = self._detect_volume_divergence(df)
        patterns.extend(divergence_patterns)
        
        return patterns
    
    def _detect_volume_spikes(self, df: pd.DataFrame) -> List[VolumePattern]:
        """
        Detect volume spike patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of VolumePattern objects
        """
        patterns = []
        volume = df['volume'].values
        close = df['close'].values
        ma_volume = df['volume'].rolling(self.lookback_period).mean()
        
        for i in range(self.lookback_period, len(df)):
            if volume[i] > ma_volume.iloc[i] * self.volume_spike_threshold:
                # Determine direction
                price_change = (close[i] - close[i-1]) / close[i-1]
                
                if price_change > 0:
                    direction = 'bullish'
                elif price_change < 0:
                    direction = 'bearish'
                else:
                    direction = 'neutral'
                
                # Calculate confidence
                confidence = min(volume[i] / (ma_volume.iloc[i] * self.volume_spike_threshold), 1.0)
                
                patterns.append(VolumePattern(
                    pattern_type='volume_spike',
                    direction=direction,
                    start_date=df.index[i-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    end_date=df.index[i] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    volume_ratio=volume[i] / ma_volume.iloc[i],
                    price_change=price_change,
                    confidence=confidence
                ))
        
        return patterns
    
    def _detect_volume_climax(self, df: pd.DataFrame) -> List[VolumePattern]:
        """
        Detect volume climax patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of VolumePattern objects
        """
        patterns = []
        volume = df['volume'].values
        close = df['close'].values
        ma_volume = df['volume'].rolling(self.lookback_period).mean()
        
        for i in range(self.lookback_period, len(df)):
            if volume[i] > ma_volume.iloc[i] * self.volume_climax_threshold:
                # Check if it's a climax (extreme volume with price reversal)
                price_change = (close[i] - close[i-1]) / close[i-1]
                
                # Check for reversal
                if i < len(df) - 1:
                    next_price_change = (close[i+1] - close[i]) / close[i]
                    if abs(price_change) > 0.02 and abs(next_price_change) > 0.02 and price_change * next_price_change < 0:
                        direction = 'bullish' if next_price_change > 0 else 'bearish'
                    else:
                        direction = 'neutral'
                else:
                    direction = 'neutral'
                
                patterns.append(VolumePattern(
                    pattern_type='volume_climax',
                    direction=direction,
                    start_date=df.index[i-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    end_date=df.index[i] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    volume_ratio=volume[i] / ma_volume.iloc[i],
                    price_change=price_change,
                    confidence=min(volume[i] / (ma_volume.iloc[i] * self.volume_climax_threshold), 1.0)
                ))
        
        return patterns
    
    def _detect_volume_divergence(self, df: pd.DataFrame) -> List[VolumePattern]:
        """
        Detect volume divergence patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of VolumePattern objects
        """
        patterns = []
        close = df['close'].values
        volume = df['volume'].values
        obv = talib.OBV(close, volume)
        
        # Find swing points
        swing_highs = self._find_swing_points(close, 'high')
        swing_lows = self._find_swing_points(close, 'low')
        
        # Check for bullish divergence (price lower low, OBV higher low)
        for i in range(len(swing_lows) - 1):
            low1 = swing_lows[i]
            low2 = swing_lows[i + 1]
            
            if low1['price'] > low2['price']:
                obv1 = obv[low1['index']]
                obv2 = obv[low2['index']]
                
                if obv1 < obv2:
                    patterns.append(VolumePattern(
                        pattern_type='volume_divergence',
                        direction='bullish',
                        start_date=df.index[low1['index']] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                        end_date=df.index[low2['index']] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                        volume_ratio=volume[low2['index']] / volume[low1['index']],
                        price_change=(low2['price'] - low1['price']) / low1['price'],
                        confidence=0.70
                    ))
        
        # Check for bearish divergence (price higher high, OBV lower high)
        for i in range(len(swing_highs) - 1):
            high1 = swing_highs[i]
            high2 = swing_highs[i + 1]
            
            if high1['price'] < high2['price']:
                obv1 = obv[high1['index']]
                obv2 = obv[high2['index']]
                
                if obv1 > obv2:
                    patterns.append(VolumePattern(
                        pattern_type='volume_divergence',
                        direction='bearish',
                        start_date=df.index[high1['index']] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                        end_date=df.index[high2['index']] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                        volume_ratio=volume[high2['index']] / volume[high1['index']],
                        price_change=(high2['price'] - high1['price']) / high1['price'],
                        confidence=0.70
                    ))
        
        return patterns
    
    def _find_swing_points(self, prices: np.ndarray, point_type: str) -> List[Dict[str, Any]]:
        """
        Find swing high or low points.
        
        Args:
            prices: Price array
            point_type: 'high' or 'low'
            
        Returns:
            List of swing points
        """
        swings = []
        lookback = 5
        
        for i in range(lookback, len(prices) - lookback):
            if point_type == 'high':
                is_swing = True
                for j in range(lookback):
                    if prices[i] <= prices[i - j - 1] or prices[i] <= prices[i + j + 1]:
                        is_swing = False
                        break
                if is_swing:
                    swings.append({'index': i, 'price': prices[i]})
            else:
                is_swing = True
                for j in range(lookback):
                    if prices[i] >= prices[i - j - 1] or prices[i] >= prices[i + j + 1]:
                        is_swing = False
                        break
                if is_swing:
                    swings.append({'index': i, 'price': prices[i]})
        
        return swings
    
    def _generate_signals(self, df: pd.DataFrame, patterns: List[VolumePattern]) -> List[VolumeSignal]:
        """
        Generate trading signals from volume patterns.
        
        Args:
            df: OHLCV data
            patterns: List of VolumePattern objects
            
        Returns:
            List of VolumeSignal objects
        """
        signals = []
        
        if not patterns:
            return signals
        
        latest_pattern = patterns[-1]
        
        if latest_pattern.confidence < self.confidence_threshold:
            return signals
        
        # Generate signal based on pattern type and direction
        if latest_pattern.pattern_type == 'volume_spike':
            if latest_pattern.direction == 'bullish':
                signal_type = 'buy'
                reason = "Bullish volume spike detected"
            elif latest_pattern.direction == 'bearish':
                signal_type = 'sell'
                reason = "Bearish volume spike detected"
            else:
                return signals
                
        elif latest_pattern.pattern_type == 'volume_climax':
            if latest_pattern.direction == 'bullish':
                signal_type = 'buy'
                reason = "Bullish volume climax detected"
            elif latest_pattern.direction == 'bearish':
                signal_type = 'sell'
                reason = "Bearish volume climax detected"
            else:
                return signals
                
        elif latest_pattern.pattern_type == 'volume_divergence':
            if latest_pattern.direction == 'bullish':
                signal_type = 'buy'
                reason = "Bullish volume divergence detected"
            elif latest_pattern.direction == 'bearish':
                signal_type = 'sell'
                reason = "Bearish volume divergence detected"
            else:
                return signals
                
        else:
            return signals
        
        signal = VolumeSignal(
            symbol=df.get('symbol', [''])[0] if 'symbol' in df.columns else '',
            timestamp=datetime.now(),
            signal_type=signal_type,
            pattern_type=latest_pattern.pattern_type,
            confidence=latest_pattern.confidence,
            price=df['close'].iloc[-1],
            volume=df['volume'].iloc[-1],
            reason=reason,
            indicators={
                'volume_ratio': latest_pattern.volume_ratio,
                'price_change': latest_pattern.price_change
            }
        )
        signals.append(signal)
        
        return signals
    
    def _get_market_character(self, df: pd.DataFrame, patterns: List[VolumePattern]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            patterns: List of VolumePattern objects
            
        Returns:
            Market character description
        """
        if not patterns:
            return "Normal volume activity"
        
        latest = patterns[-1]
        
        if latest.pattern_type == 'volume_spike':
            return f"Volume spike - {latest.direction.capitalize()}"
        elif latest.pattern_type == 'volume_climax':
            return f"Volume climax - {latest.direction.capitalize()}"
        elif latest.pattern_type == 'volume_divergence':
            return f"Volume divergence - {latest.direction.capitalize()}"
        
        return "Normal volume activity"
    
    def get_volume_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get volume statistics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Volume statistics
        """
        volume = df['volume'].values
        
        stats = {
            'current_volume': volume[-1],
            'average_volume': np.mean(volume),
            'median_volume': np.median(volume),
            'volume_std': np.std(volume),
            'volume_range': (np.min(volume), np.max(volume)),
            'volume_percentile': np.percentile(volume, [25, 50, 75]).tolist(),
            'volume_velocity': self._calculate_volume_velocity(volume)
        }
        
        return stats


def create_volume_model(config: Optional[Dict[str, Any]] = None) -> VolumeModel:
    """
    Create a volume model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        VolumeModel instance
    """
    return VolumeModel(config)


__all__ = [
    'VolumeIndicator',
    'VolumePattern',
    'VolumeSignal',
    'VolumeModel',
    'create_volume_model'
]
