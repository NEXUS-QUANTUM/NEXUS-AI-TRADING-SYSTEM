"""
Swing Bot Channel Model
=========================

This module provides channel pattern analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class ChannelPattern:
    """Channel pattern data structure."""
    channel_type: str  # 'ascending', 'descending', 'horizontal'
    upper_line: Tuple[float, float]  # slope, intercept
    lower_line: Tuple[float, float]  # slope, intercept
    start_price: float
    end_price: float
    width: float
    strength: float
    confidence: float
    timestamp: datetime
    touches_upper: int = 0
    touches_lower: int = 0


@dataclass
class ChannelSignal:
    """Channel trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    pattern: ChannelPattern
    indicators: Dict[str, Any] = field(default_factory=dict)


class ChannelModel:
    """
    Channel pattern analysis model.
    
    Identifies and analyzes price channels:
    - Ascending channels
    - Descending channels
    - Horizontal channels
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the channel model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.min_channel_length = self.config.get('min_channel_length', 10)
        self.max_trendline_error = self.config.get('max_trendline_error', 0.02)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze channel patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            Channel analysis results
        """
        if len(df) < self.min_channel_length:
            return {'patterns': [], 'signals': []}
        
        # Detect channels
        patterns = self._detect_channels(df)
        
        # Generate signals
        signals = self._generate_signals(df, patterns)
        
        return {
            'patterns': patterns,
            'signals': signals,
            'current_pattern': patterns[-1] if patterns else None,
            'market_character': self._get_market_character(df, patterns)
        }
    
    def _detect_channels(self, df: pd.DataFrame) -> List[ChannelPattern]:
        """
        Detect channel patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of ChannelPattern objects
        """
        patterns = []
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        # Find swing points
        swing_highs = self._find_swing_points(high, 'high')
        swing_lows = self._find_swing_points(low, 'low')
        
        # Detect channels
        for i in range(len(swing_highs) - self.min_channel_length):
            for j in range(i + self.min_channel_length, len(swing_highs)):
                # Get points for upper and lower channels
                upper_points = swing_highs[i:j+1]
                lower_points = swing_lows[i:j+1]
                
                if len(upper_points) < 2 or len(lower_points) < 2:
                    continue
                
                # Fit lines
                upper_slope, upper_intercept = self._fit_line(upper_points)
                lower_slope, lower_intercept = self._fit_line(lower_points)
                
                # Check if lines are roughly parallel
                slope_diff = abs(upper_slope - lower_slope)
                if slope_diff > 0.001:
                    continue
                
                # Determine channel type
                avg_slope = (upper_slope + lower_slope) / 2
                
                if avg_slope > 0.001:
                    channel_type = 'ascending'
                elif avg_slope < -0.001:
                    channel_type = 'descending'
                else:
                    channel_type = 'horizontal'
                
                # Calculate channel width
                width = self._calculate_channel_width(df, upper_slope, upper_intercept, 
                                                     lower_slope, lower_intercept)
                
                # Calculate strength
                strength = self._calculate_channel_strength(df, upper_slope, upper_intercept,
                                                           lower_slope, lower_intercept)
                
                # Calculate confidence
                confidence = self._calculate_channel_confidence(df, upper_slope, upper_intercept,
                                                               lower_slope, lower_intercept)
                
                if confidence < self.confidence_threshold:
                    continue
                
                # Count touches
                touches_upper = self._count_touches(df, upper_slope, upper_intercept, 'upper')
                touches_lower = self._count_touches(df, lower_slope, lower_intercept, 'lower')
                
                patterns.append(ChannelPattern(
                    channel_type=channel_type,
                    upper_line=(upper_slope, upper_intercept),
                    lower_line=(lower_slope, lower_intercept),
                    start_price=close[i],
                    end_price=close[j],
                    width=width,
                    strength=strength,
                    confidence=confidence,
                    timestamp=datetime.now(),
                    touches_upper=touches_upper,
                    touches_lower=touches_lower
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
    
    def _fit_line(self, points: List[Dict[str, Any]]) -> Tuple[float, float]:
        """
        Fit a line to points.
        
        Args:
            points: List of swing points
            
        Returns:
            Tuple of (slope, intercept)
        """
        if len(points) < 2:
            return (0.0, 0.0)
        
        x = [p['index'] for p in points]
        y = [p['price'] for p in points]
        
        return MathUtils.linear_regression(x, y)
    
    def _calculate_channel_width(self, df: pd.DataFrame, upper_slope: float,
                                upper_intercept: float, lower_slope: float,
                                lower_intercept: float) -> float:
        """
        Calculate channel width.
        
        Args:
            df: OHLCV data
            upper_slope: Upper line slope
            upper_intercept: Upper line intercept
            lower_slope: Lower line slope
            lower_intercept: Lower line intercept
            
        Returns:
            Channel width
        """
        last_index = len(df) - 1
        
        upper_price = upper_slope * last_index + upper_intercept
        lower_price = lower_slope * last_index + lower_intercept
        
        return upper_price - lower_price
    
    def _calculate_channel_strength(self, df: pd.DataFrame, upper_slope: float,
                                   upper_intercept: float, lower_slope: float,
                                   lower_intercept: float) -> float:
        """
        Calculate channel strength.
        
        Args:
            df: OHLCV data
            upper_slope: Upper line slope
            upper_intercept: Upper line intercept
            lower_slope: Lower line slope
            lower_intercept: Lower line intercept
            
        Returns:
            Strength score (0-1)
        """
        close = df['close'].values
        indices = np.arange(len(close))
        
        # Calculate errors from upper and lower lines
        upper_errors = []
        lower_errors = []
        
        for i in range(len(close)):
            upper_price = upper_slope * i + upper_intercept
            lower_price = lower_slope * i + lower_intercept
            
            upper_errors.append(abs(close[i] - upper_price) / upper_price if upper_price > 0 else 0)
            lower_errors.append(abs(close[i] - lower_price) / lower_price if lower_price > 0 else 0)
        
        avg_upper_error = np.mean(upper_errors)
        avg_lower_error = np.mean(lower_errors)
        
        # Strength is inversely proportional to error
        strength = 1 - (avg_upper_error + avg_lower_error) / 2
        
        return max(0, min(1, strength))
    
    def _calculate_channel_confidence(self, df: pd.DataFrame, upper_slope: float,
                                    upper_intercept: float, lower_slope: float,
                                    lower_intercept: float) -> float:
        """
        Calculate channel confidence.
        
        Args:
            df: OHLCV data
            upper_slope: Upper line slope
            upper_intercept: Upper line intercept
            lower_slope: Lower line slope
            lower_intercept: Lower line intercept
            
        Returns:
            Confidence score (0-1)
        """
        # Count touches
        touches_upper = self._count_touches(df, upper_slope, upper_intercept, 'upper')
        touches_lower = self._count_touches(df, lower_slope, lower_intercept, 'lower')
        
        # Calculate touch score
        total_touches = touches_upper + touches_lower
        touch_score = min(total_touches / 6, 1.0)
        
        # Calculate price consistency
        close = df['close'].values
        indices = np.arange(len(close))
        
        upper_prices = upper_slope * indices + upper_intercept
        lower_prices = lower_slope * indices + lower_intercept
        
        # Check if price stays within channel
        in_channel = 0
        for i in range(len(close)):
            if lower_prices[i] <= close[i] <= upper_prices[i]:
                in_channel += 1
        
        consistency = in_channel / len(close)
        
        # Combined confidence
        confidence = touch_score * 0.5 + consistency * 0.5
        
        return max(0, min(1, confidence))
    
    def _count_touches(self, df: pd.DataFrame, slope: float,
                      intercept: float, line_type: str) -> int:
        """
        Count touches to a line.
        
        Args:
            df: OHLCV data
            slope: Line slope
            intercept: Line intercept
            line_type: 'upper' or 'lower'
            
        Returns:
            Number of touches
        """
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        threshold = 0.005
        
        touches = 0
        
        for i in range(len(close)):
            line_price = slope * i + intercept
            
            if line_type == 'upper':
                if abs(high[i] - line_price) / line_price < threshold:
                    touches += 1
            else:  # lower
                if abs(low[i] - line_price) / line_price < threshold:
                    touches += 1
        
        return touches
    
    def _generate_signals(self, df: pd.DataFrame,
                         patterns: List[ChannelPattern]) -> List[ChannelSignal]:
        """
        Generate trading signals from channel patterns.
        
        Args:
            df: OHLCV data
            patterns: List of channel patterns
            
        Returns:
            List of ChannelSignal objects
        """
        signals = []
        
        if not patterns:
            return signals
        
        latest_pattern = patterns[-1]
        
        if latest_pattern.confidence < self.confidence_threshold:
            return signals
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        last_index = len(df) - 1
        upper_price = latest_pattern.upper_line[0] * last_index + latest_pattern.upper_line[1]
        lower_price = latest_pattern.lower_line[0] * last_index + latest_pattern.lower_line[1]
        
        # Check for breakouts
        if current_price > upper_price * 1.01:
            signal_type = 'buy' if latest_pattern.channel_type != 'descending' else 'sell'
            reason = f"Breakout above channel in {latest_pattern.channel_type} channel"
            confidence = latest_pattern.confidence
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif current_price < lower_price * 0.99:
            signal_type = 'sell' if latest_pattern.channel_type != 'ascending' else 'buy'
            reason = f"Breakout below channel in {latest_pattern.channel_type} channel"
            confidence = latest_pattern.confidence
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            # Channel bounce
            if current_price > upper_price * 0.98:
                signal_type = 'sell'
                reason = f"Upper channel bounce in {latest_pattern.channel_type} channel"
                confidence = latest_pattern.confidence * 0.8
                target = current_price * 0.98
                stop_loss = current_price * 1.01
                
            elif current_price < lower_price * 1.02:
                signal_type = 'buy'
                reason = f"Lower channel bounce in {latest_pattern.channel_type} channel"
                confidence = latest_pattern.confidence * 0.8
                target = current_price * 1.02
                stop_loss = current_price * 0.99
            else:
                return signals
        
        signals.append(ChannelSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            pattern=latest_pattern,
            indicators={
                'channel_width': latest_pattern.width,
                'touches_upper': latest_pattern.touches_upper,
                'touches_lower': latest_pattern.touches_lower
            }
        ))
        
        return signals
    
    def _get_market_character(self, df: pd.DataFrame,
                            patterns: List[ChannelPattern]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            patterns: List of channel patterns
            
        Returns:
            Market character description
        """
        if not patterns:
            return "No channels detected"
        
        latest = patterns[-1]
        
        channel_names = {
            'ascending': 'Ascending channel',
            'descending': 'Descending channel',
            'horizontal': 'Horizontal channel'
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
        
        return f"{strength_names[strength_level]} {channel_names.get(latest.channel_type, latest.channel_type)}"


def create_channel_model(config: Optional[Dict[str, Any]] = None) -> ChannelModel:
    """
    Create a channel model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        ChannelModel instance
    """
    return ChannelModel(config)


__all__ = [
    'ChannelPattern',
    'ChannelSignal',
    'ChannelModel',
    'create_channel_model'
]
