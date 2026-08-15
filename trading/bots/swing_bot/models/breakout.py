"""
Swing Bot Breakout Model
==========================

This module provides breakout pattern analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class BreakoutPattern:
    """Breakout pattern data structure."""
    pattern_type: str  # 'range_breakout', 'trendline_breakout', 'pivot_breakout'
    direction: str  # 'bullish', 'bearish'
    start_date: datetime
    end_date: datetime
    breakout_price: float
    target_price: float
    stop_loss: float
    confidence: float
    volume_confirmation: bool
    strength: float


@dataclass
class BreakoutSignal:
    """Breakout trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    pattern_type: str
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class BreakoutModel:
    """
    Breakout pattern analysis model.
    
    Identifies and analyzes various breakout patterns:
    - Range breakouts
    - Trendline breakouts
    - Pivot breakouts
    - Volume breakouts
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the breakout model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 20)
        self.breakout_threshold = self.config.get('breakout_threshold', 0.02)
        self.volume_threshold = self.config.get('volume_threshold', 1.5)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.min_range_width = self.config.get('min_range_width', 0.02)
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze breakout patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            Breakout analysis results
        """
        if len(df) < self.lookback_period:
            return {'patterns': [], 'signals': []}
        
        # Detect patterns
        patterns = self._detect_patterns(df)
        
        # Generate signals
        signals = self._generate_signals(df, patterns)
        
        return {
            'patterns': patterns,
            'signals': signals,
            'current_pattern': patterns[-1] if patterns else None,
            'market_character': self._get_market_character(df, patterns)
        }
    
    def _detect_patterns(self, df: pd.DataFrame) -> List[BreakoutPattern]:
        """
        Detect breakout patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of BreakoutPattern objects
        """
        patterns = []
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        volume = df['volume'].values
        
        # Range breakouts
        range_patterns = self._detect_range_breakouts(df)
        patterns.extend(range_patterns)
        
        # Trendline breakouts
        trendline_patterns = self._detect_trendline_breakouts(df)
        patterns.extend(trendline_patterns)
        
        # Pivot breakouts
        pivot_patterns = self._detect_pivot_breakouts(df)
        patterns.extend(pivot_patterns)
        
        # Volume breakouts
        volume_patterns = self._detect_volume_breakouts(df)
        patterns.extend(volume_patterns)
        
        return patterns
    
    def _detect_range_breakouts(self, df: pd.DataFrame) -> List[BreakoutPattern]:
        """
        Detect range breakouts.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of range breakout patterns
        """
        patterns = []
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        volume = df['volume'].values
        
        if len(df) < self.lookback_period:
            return patterns
        
        # Calculate range
        high_range = np.max(high[-self.lookback_period:])
        low_range = np.min(low[-self.lookback_period:])
        range_width = (high_range - low_range) / low_range
        
        if range_width < self.min_range_width:
            return patterns
        
        current_price = close[-1]
        
        # Check for breakout above resistance
        if current_price > high_range * (1 + self.breakout_threshold):
            # Check volume confirmation
            avg_volume = np.mean(volume[-self.lookback_period:])
            volume_confirm = volume[-1] > avg_volume * self.volume_threshold
            
            confidence = min((current_price - high_range) / (high_range * self.breakout_threshold), 1.0)
            if volume_confirm:
                confidence *= 1.2
            
            patterns.append(BreakoutPattern(
                pattern_type='range_breakout',
                direction='bullish',
                start_date=df.index[-self.lookback_period] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                end_date=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                breakout_price=high_range,
                target_price=high_range + (high_range - low_range),
                stop_loss=high_range * 0.98,
                confidence=min(confidence, 1.0),
                volume_confirmation=volume_confirm,
                strength=range_width * 5
            ))
        
        # Check for breakout below support
        elif current_price < low_range * (1 - self.breakout_threshold):
            # Check volume confirmation
            avg_volume = np.mean(volume[-self.lookback_period:])
            volume_confirm = volume[-1] > avg_volume * self.volume_threshold
            
            confidence = min((low_range - current_price) / (low_range * self.breakout_threshold), 1.0)
            if volume_confirm:
                confidence *= 1.2
            
            patterns.append(BreakoutPattern(
                pattern_type='range_breakout',
                direction='bearish',
                start_date=df.index[-self.lookback_period] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                end_date=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                breakout_price=low_range,
                target_price=low_range - (high_range - low_range),
                stop_loss=low_range * 1.02,
                confidence=min(confidence, 1.0),
                volume_confirmation=volume_confirm,
                strength=range_width * 5
            ))
        
        return patterns
    
    def _detect_trendline_breakouts(self, df: pd.DataFrame) -> List[BreakoutPattern]:
        """
        Detect trendline breakouts.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of trendline breakout patterns
        """
        patterns = []
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        volume = df['volume'].values
        
        if len(df) < self.lookback_period:
            return patterns
        
        # Find trendline
        indices = np.arange(len(high))
        slope, intercept = MathUtils.linear_regression(indices[-self.lookback_period:], 
                                                       high[-self.lookback_period:])
        
        current_price = close[-1]
        trendline_value = slope * (len(high) - 1) + intercept
        
        # Check for breakout above downtrend line
        if slope < 0 and current_price > trendline_value * (1 + self.breakout_threshold):
            # Check volume confirmation
            avg_volume = np.mean(volume[-self.lookback_period:])
            volume_confirm = volume[-1] > avg_volume * self.volume_threshold
            
            confidence = min((current_price - trendline_value) / (trendline_value * self.breakout_threshold), 1.0)
            if volume_confirm:
                confidence *= 1.2
            
            patterns.append(BreakoutPattern(
                pattern_type='trendline_breakout',
                direction='bullish',
                start_date=df.index[-self.lookback_period] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                end_date=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                breakout_price=trendline_value,
                target_price=trendline_value + (current_price - trendline_value) * 2,
                stop_loss=trendline_value * 0.98,
                confidence=min(confidence, 1.0),
                volume_confirmation=volume_confirm,
                strength=abs(slope) * 10
            ))
        
        # Check for breakout below uptrend line
        slope2, intercept2 = MathUtils.linear_regression(indices[-self.lookback_period:], 
                                                         low[-self.lookback_period:])
        
        if slope2 > 0 and current_price < (slope2 * (len(low) - 1) + intercept2) * (1 - self.breakout_threshold):
            trendline_value2 = slope2 * (len(low) - 1) + intercept2
            
            # Check volume confirmation
            avg_volume = np.mean(volume[-self.lookback_period:])
            volume_confirm = volume[-1] > avg_volume * self.volume_threshold
            
            confidence = min((trendline_value2 - current_price) / (trendline_value2 * self.breakout_threshold), 1.0)
            if volume_confirm:
                confidence *= 1.2
            
            patterns.append(BreakoutPattern(
                pattern_type='trendline_breakout',
                direction='bearish',
                start_date=df.index[-self.lookback_period] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                end_date=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                breakout_price=trendline_value2,
                target_price=trendline_value2 - (trendline_value2 - current_price) * 2,
                stop_loss=trendline_value2 * 1.02,
                confidence=min(confidence, 1.0),
                volume_confirmation=volume_confirm,
                strength=abs(slope2) * 10
            ))
        
        return patterns
    
    def _detect_pivot_breakouts(self, df: pd.DataFrame) -> List[BreakoutPattern]:
        """
        Detect pivot breakouts.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of pivot breakout patterns
        """
        patterns = []
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        volume = df['volume'].values
        
        if len(df) < 10:
            return patterns
        
        # Find pivot points
        pivots = self._find_pivots(df)
        
        if not pivots['highs'] or not pivots['lows']:
            return patterns
        
        # Get recent pivot high and low
        recent_pivot_high = max(pivots['highs'], key=lambda x: x['price'])
        recent_pivot_low = min(pivots['lows'], key=lambda x: x['price'])
        
        current_price = close[-1]
        
        # Check for breakout above pivot high
        if current_price > recent_pivot_high['price'] * (1 + self.breakout_threshold):
            # Check volume confirmation
            avg_volume = np.mean(volume[-self.lookback_period:])
            volume_confirm = volume[-1] > avg_volume * self.volume_threshold
            
            confidence = min((current_price - recent_pivot_high['price']) / 
                           (recent_pivot_high['price'] * self.breakout_threshold), 1.0)
            if volume_confirm:
                confidence *= 1.2
            
            patterns.append(BreakoutPattern(
                pattern_type='pivot_breakout',
                direction='bullish',
                start_date=df.index[recent_pivot_high['index']] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                end_date=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                breakout_price=recent_pivot_high['price'],
                target_price=recent_pivot_high['price'] + (recent_pivot_high['price'] - recent_pivot_low['price']),
                stop_loss=recent_pivot_high['price'] * 0.98,
                confidence=min(confidence, 1.0),
                volume_confirmation=volume_confirm,
                strength=abs(recent_pivot_high['price'] - recent_pivot_low['price']) / recent_pivot_low['price'] * 5
            ))
        
        # Check for breakout below pivot low
        elif current_price < recent_pivot_low['price'] * (1 - self.breakout_threshold):
            # Check volume confirmation
            avg_volume = np.mean(volume[-self.lookback_period:])
            volume_confirm = volume[-1] > avg_volume * self.volume_threshold
            
            confidence = min((recent_pivot_low['price'] - current_price) / 
                           (recent_pivot_low['price'] * self.breakout_threshold), 1.0)
            if volume_confirm:
                confidence *= 1.2
            
            patterns.append(BreakoutPattern(
                pattern_type='pivot_breakout',
                direction='bearish',
                start_date=df.index[recent_pivot_low['index']] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                end_date=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                breakout_price=recent_pivot_low['price'],
                target_price=recent_pivot_low['price'] - (recent_pivot_high['price'] - recent_pivot_low['price']),
                stop_loss=recent_pivot_low['price'] * 1.02,
                confidence=min(confidence, 1.0),
                volume_confirmation=volume_confirm,
                strength=abs(recent_pivot_high['price'] - recent_pivot_low['price']) / recent_pivot_low['price'] * 5
            ))
        
        return patterns
    
    def _detect_volume_breakouts(self, df: pd.DataFrame) -> List[BreakoutPattern]:
        """
        Detect volume breakouts.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of volume breakout patterns
        """
        patterns = []
        close = df['close'].values
        volume = df['volume'].values
        
        if len(df) < self.lookback_period:
            return patterns
        
        avg_volume = np.mean(volume[-self.lookback_period:])
        volume_ratio = volume[-1] / avg_volume
        
        if volume_ratio > self.volume_threshold:
            # Calculate price change
            price_change = (close[-1] - close[-2]) / close[-2] if len(close) >= 2 else 0
            
            if price_change > self.breakout_threshold:
                patterns.append(BreakoutPattern(
                    pattern_type='volume_breakout',
                    direction='bullish',
                    start_date=df.index[-self.lookback_period] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    end_date=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    breakout_price=close[-2],
                    target_price=close[-1] * (1 + price_change * 0.5),
                    stop_loss=close[-1] * 0.98,
                    confidence=min(volume_ratio / self.volume_threshold, 1.0),
                    volume_confirmation=True,
                    strength=min(price_change * 10, 1.0)
                ))
            elif price_change < -self.breakout_threshold:
                patterns.append(BreakoutPattern(
                    pattern_type='volume_breakout',
                    direction='bearish',
                    start_date=df.index[-self.lookback_period] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    end_date=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    breakout_price=close[-2],
                    target_price=close[-1] * (1 + price_change * 0.5),
                    stop_loss=close[-1] * 1.02,
                    confidence=min(volume_ratio / self.volume_threshold, 1.0),
                    volume_confirmation=True,
                    strength=min(abs(price_change) * 10, 1.0)
                ))
        
        return patterns
    
    def _find_pivots(self, df: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
        """
        Find pivot highs and lows.
        
        Args:
            df: OHLCV data
            
        Returns:
            Dictionary of pivot highs and lows
        """
        high = df['high'].values
        low = df['low'].values
        lookback = 5
        
        pivots = {'highs': [], 'lows': []}
        
        for i in range(lookback, len(df) - lookback):
            # Check for pivot high
            is_high = True
            for j in range(lookback):
                if high[i] <= high[i - j - 1] or high[i] <= high[i + j + 1]:
                    is_high = False
                    break
            if is_high:
                pivots['highs'].append({
                    'index': i,
                    'price': high[i],
                    'timestamp': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
                })
            
            # Check for pivot low
            is_low = True
            for j in range(lookback):
                if low[i] >= low[i - j - 1] or low[i] >= low[i + j + 1]:
                    is_low = False
                    break
            if is_low:
                pivots['lows'].append({
                    'index': i,
                    'price': low[i],
                    'timestamp': df.index[i] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
                })
        
        return pivots
    
    def _generate_signals(self, df: pd.DataFrame,
                         patterns: List[BreakoutPattern]) -> List[BreakoutSignal]:
        """
        Generate trading signals from breakout patterns.
        
        Args:
            df: OHLCV data
            patterns: List of breakout patterns
            
        Returns:
            List of BreakoutSignal objects
        """
        signals = []
        
        if not patterns:
            return signals
        
        latest_pattern = patterns[-1]
        
        if latest_pattern.confidence < self.confidence_threshold:
            return signals
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        if latest_pattern.direction == 'bullish':
            signal_type = 'buy'
            reason = f"{latest_pattern.pattern_type.replace('_', ' ').title()} detected"
            target = latest_pattern.target_price
            stop_loss = latest_pattern.stop_loss
        else:
            signal_type = 'sell'
            reason = f"{latest_pattern.pattern_type.replace('_', ' ').title()} detected"
            target = latest_pattern.target_price
            stop_loss = latest_pattern.stop_loss
        
        signal = BreakoutSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            pattern_type=latest_pattern.pattern_type,
            confidence=latest_pattern.confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            indicators={
                'breakout_price': latest_pattern.breakout_price,
                'volume_confirmation': latest_pattern.volume_confirmation,
                'strength': latest_pattern.strength
            }
        )
        signals.append(signal)
        
        return signals
    
    def _get_market_character(self, df: pd.DataFrame,
                             patterns: List[BreakoutPattern]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            patterns: List of breakout patterns
            
        Returns:
            Market character description
        """
        if not patterns:
            return "No breakout patterns detected"
        
        latest = patterns[-1]
        
        direction_names = {
            'bullish': 'Bullish breakout',
            'bearish': 'Bearish breakout'
        }
        
        strength = latest.strength
        strength_names = {
            'weak': 'Weak',
            'moderate': 'Moderate',
            'strong': 'Strong',
            'very_strong': 'Very Strong'
        }
        
        strength_level = 'moderate'
        if strength > 0.75:
            strength_level = 'very_strong'
        elif strength > 0.50:
            strength_level = 'strong'
        elif strength > 0.25:
            strength_level = 'moderate'
        else:
            strength_level = 'weak'
        
        return f"{strength_names[strength_level]} {direction_names[latest.direction]} in {latest.pattern_type.replace('_', ' ')}"


def create_breakout_model(config: Optional[Dict[str, Any]] = None) -> BreakoutModel:
    """
    Create a breakout model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        BreakoutModel instance
    """
    return BreakoutModel(config)


__all__ = [
    'BreakoutPattern',
    'BreakoutSignal',
    'BreakoutModel',
    'create_breakout_model'
]
