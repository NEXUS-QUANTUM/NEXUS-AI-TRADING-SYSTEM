"""
Swing Bot Continuation Model
==============================

This module provides continuation pattern analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class ContinuationPattern:
    """Continuation pattern data structure."""
    pattern_type: str  # 'flag', 'pennant', 'wedge', 'triangle'
    direction: str  # 'bullish', 'bearish', 'neutral'
    start_price: float
    end_price: float
    high_price: float
    low_price: float
    duration: int
    strength: float
    confidence: float
    timestamp: datetime
    breakout_price: Optional[float] = None
    target_price: Optional[float] = None


@dataclass
class ContinuationSignal:
    """Continuation trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    pattern: ContinuationPattern
    indicators: Dict[str, Any] = field(default_factory=dict)


class ContinuationModel:
    """
    Continuation pattern analysis model.
    
    Identifies and analyzes continuation patterns:
    - Flags
    - Pennants
    - Wedges
    - Triangles
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the continuation model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.min_duration = self.config.get('min_duration', 5)
        self.max_duration = self.config.get('max_duration', 30)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.volume_threshold = self.config.get('volume_threshold', 1.5)
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze continuation patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            Continuation analysis results
        """
        if len(df) < self.min_duration:
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
    
    def _detect_patterns(self, df: pd.DataFrame) -> List[ContinuationPattern]:
        """
        Detect continuation patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of ContinuationPattern objects
        """
        patterns = []
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        volume = df['volume'].values
        
        # Find swing points
        swing_highs = self._find_swing_points(high, 'high')
        swing_lows = self._find_swing_points(low, 'low')
        
        # Detect patterns
        for i in range(len(swing_highs) - self.min_duration):
            for j in range(i + self.min_duration, min(i + self.max_duration + 1, len(swing_highs))):
                # Get segment
                start_idx = swing_highs[i]['index']
                end_idx = swing_highs[j]['index']
                segment = df.iloc[start_idx:end_idx + 1]
                
                if len(segment) < self.min_duration:
                    continue
                
                # Check for flag pattern
                flag = self._check_flag(segment)
                if flag:
                    patterns.append(flag)
                    continue
                
                # Check for pennant pattern
                pennant = self._check_pennant(segment)
                if pennant:
                    patterns.append(pennant)
                    continue
                
                # Check for wedge pattern
                wedge = self._check_wedge(segment)
                if wedge:
                    patterns.append(wedge)
                    continue
                
                # Check for triangle pattern
                triangle = self._check_triangle(segment)
                if triangle:
                    patterns.append(triangle)
        
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
    
    def _check_flag(self, segment: pd.DataFrame) -> Optional[ContinuationPattern]:
        """
        Check for flag pattern.
        
        Args:
            segment: Price segment
            
        Returns:
            ContinuationPattern or None
        """
        if len(segment) < self.min_duration:
            return None
        
        high = segment['high'].values
        low = segment['low'].values
        close = segment['close'].values
        volume = segment['volume'].values
        
        # Check for flag characteristics
        # 1. Quick price movement (pole)
        pole_start = close[0]
        pole_end = close[-1]
        pole_change = (pole_end - pole_start) / pole_start
        
        # 2. Consolidation (flag)
        flag_high = np.max(high)
        flag_low = np.min(low)
        flag_width = (flag_high - flag_low) / flag_low
        
        # 3. Volume decrease during flag
        volume_ma = np.mean(volume)
        volume_end = volume[-1]
        
        if abs(pole_change) < 0.02:
            return None
        
        if flag_width > 0.05:
            return None
        
        if volume_end > volume_ma:
            return None
        
        # Determine direction
        direction = 'bullish' if pole_change > 0 else 'bearish'
        
        # Calculate strength
        strength = self._calculate_strength(segment, 'flag')
        
        # Calculate confidence
        confidence = self._calculate_confidence(segment, 'flag')
        
        if confidence < self.confidence_threshold:
            return None
        
        # Calculate breakout and target
        breakout_price = flag_high if direction == 'bullish' else flag_low
        target_price = pole_end + (pole_end - pole_start) if direction == 'bullish' else pole_end - (pole_start - pole_end)
        
        return ContinuationPattern(
            pattern_type='flag',
            direction=direction,
            start_price=close[0],
            end_price=close[-1],
            high_price=flag_high,
            low_price=flag_low,
            duration=len(segment),
            strength=strength,
            confidence=confidence,
            timestamp=datetime.now(),
            breakout_price=breakout_price,
            target_price=target_price
        )
    
    def _check_pennant(self, segment: pd.DataFrame) -> Optional[ContinuationPattern]:
        """
        Check for pennant pattern.
        
        Args:
            segment: Price segment
            
        Returns:
            ContinuationPattern or None
        """
        if len(segment) < self.min_duration:
            return None
        
        high = segment['high'].values
        low = segment['low'].values
        close = segment['close'].values
        
        # Check for pennant characteristics
        # 1. Quick price movement (pole)
        pole_start = close[0]
        pole_end = close[-1]
        pole_change = (pole_end - pole_start) / pole_start
        
        # 2. Symmetrical consolidation (pennant)
        pennant_high = np.max(high)
        pennant_low = np.min(low)
        pennant_width = (pennant_high - pennant_low) / pennant_low
        
        # 3. Converging trendlines
        slope_high, intercept_high = MathUtils.linear_regression(
            np.arange(len(high)),
            high
        )
        slope_low, intercept_low = MathUtils.linear_regression(
            np.arange(len(low)),
            low
        )
        
        if abs(pole_change) < 0.02:
            return None
        
        if pennant_width > 0.05:
            return None
        
        # Check convergence
        if slope_high - slope_low > 0:
            return None
        
        # Determine direction
        direction = 'bullish' if pole_change > 0 else 'bearish'
        
        # Calculate strength
        strength = self._calculate_strength(segment, 'pennant')
        
        # Calculate confidence
        confidence = self._calculate_confidence(segment, 'pennant')
        
        if confidence < self.confidence_threshold:
            return None
        
        # Calculate breakout and target
        breakout_price = pennant_high if direction == 'bullish' else pennant_low
        target_price = pole_end + (pole_end - pole_start) if direction == 'bullish' else pole_end - (pole_start - pole_end)
        
        return ContinuationPattern(
            pattern_type='pennant',
            direction=direction,
            start_price=close[0],
            end_price=close[-1],
            high_price=pennant_high,
            low_price=pennant_low,
            duration=len(segment),
            strength=strength,
            confidence=confidence,
            timestamp=datetime.now(),
            breakout_price=breakout_price,
            target_price=target_price
        )
    
    def _check_wedge(self, segment: pd.DataFrame) -> Optional[ContinuationPattern]:
        """
        Check for wedge pattern.
        
        Args:
            segment: Price segment
            
        Returns:
            ContinuationPattern or None
        """
        if len(segment) < self.min_duration:
            return None
        
        high = segment['high'].values
        low = segment['low'].values
        close = segment['close'].values
        
        # Check for wedge characteristics
        # 1. Converging trendlines
        slope_high, intercept_high = MathUtils.linear_regression(
            np.arange(len(high)),
            high
        )
        slope_low, intercept_low = MathUtils.linear_regression(
            np.arange(len(low)),
            low
        )
        
        # 2. Both trendlines moving in same direction
        if slope_high * slope_low < 0:
            return None
        
        # 3. Converging
        if abs(slope_high - slope_low) < 0.001:
            return None
        
        # Determine type
        if slope_high > 0 and slope_low > 0:
            pattern_type = 'rising_wedge'
        elif slope_high < 0 and slope_low < 0:
            pattern_type = 'falling_wedge'
        else:
            return None
        
        # Determine direction
        direction = 'bullish' if pattern_type == 'falling_wedge' else 'bearish'
        
        # Calculate strength
        strength = self._calculate_strength(segment, 'wedge')
        
        # Calculate confidence
        confidence = self._calculate_confidence(segment, 'wedge')
        
        if confidence < self.confidence_threshold:
            return None
        
        # Calculate breakout and target
        if direction == 'bullish':
            breakout_price = np.max(high)
            target_price = breakout_price + (breakout_price - np.min(low))
        else:
            breakout_price = np.min(low)
            target_price = breakout_price - (np.max(high) - breakout_price)
        
        return ContinuationPattern(
            pattern_type=pattern_type,
            direction=direction,
            start_price=close[0],
            end_price=close[-1],
            high_price=np.max(high),
            low_price=np.min(low),
            duration=len(segment),
            strength=strength,
            confidence=confidence,
            timestamp=datetime.now(),
            breakout_price=breakout_price,
            target_price=target_price
        )
    
    def _check_triangle(self, segment: pd.DataFrame) -> Optional[ContinuationPattern]:
        """
        Check for triangle pattern.
        
        Args:
            segment: Price segment
            
        Returns:
            ContinuationPattern or None
        """
        if len(segment) < self.min_duration:
            return None
        
        high = segment['high'].values
        low = segment['low'].values
        close = segment['close'].values
        
        # Check for triangle characteristics
        # 1. Converging trendlines
        slope_high, intercept_high = MathUtils.linear_regression(
            np.arange(len(high)),
            high
        )
        slope_low, intercept_low = MathUtils.linear_regression(
            np.arange(len(low)),
            low
        )
        
        # 2. Both trendlines moving toward each other
        if slope_high - slope_low < 0:
            return None
        
        # 3. Price making lower highs and higher lows
        if np.diff(high)[-1] > 0 or np.diff(low)[-1] < 0:
            return None
        
        # Determine type
        if slope_high < 0 and slope_low > 0:
            pattern_type = 'symmetrical'
        elif slope_high < 0 and slope_low < 0:
            pattern_type = 'descending'
        elif slope_high > 0 and slope_low > 0:
            pattern_type = 'ascending'
        else:
            return None
        
        # Determine direction
        direction = 'neutral'
        if pattern_type == 'ascending':
            direction = 'bullish'
        elif pattern_type == 'descending':
            direction = 'bearish'
        
        # Calculate strength
        strength = self._calculate_strength(segment, 'triangle')
        
        # Calculate confidence
        confidence = self._calculate_confidence(segment, 'triangle')
        
        if confidence < self.confidence_threshold:
            return None
        
        # Calculate breakout and target
        if direction == 'bullish':
            breakout_price = np.max(high)
            target_price = breakout_price + (breakout_price - np.min(low))
        elif direction == 'bearish':
            breakout_price = np.min(low)
            target_price = breakout_price - (np.max(high) - breakout_price)
        else:
            breakout_price = (np.max(high) + np.min(low)) / 2
            target_price = breakout_price
        
        return ContinuationPattern(
            pattern_type=pattern_type,
            direction=direction,
            start_price=close[0],
            end_price=close[-1],
            high_price=np.max(high),
            low_price=np.min(low),
            duration=len(segment),
            strength=strength,
            confidence=confidence,
            timestamp=datetime.now(),
            breakout_price=breakout_price,
            target_price=target_price
        )
    
    def _calculate_strength(self, segment: pd.DataFrame, pattern_type: str) -> float:
        """
        Calculate continuation pattern strength.
        
        Args:
            segment: Price segment
            pattern_type: Pattern type
            
        Returns:
            Strength score (0-1)
        """
        volume = segment['volume'].values
        
        # Volume pattern
        volume_ma = np.mean(volume)
        volume_end = volume[-1]
        volume_score = 1 - min(volume_end / (volume_ma + 1e-10), 1.0)
        
        # Duration factor
        duration_score = min(len(segment) / 15, 1.0)
        
        # Pattern recognition score
        pattern_scores = {
            'flag': 0.8,
            'pennant': 0.7,
            'wedge': 0.6,
            'triangle': 0.5
        }
        pattern_score = pattern_scores.get(pattern_type, 0.5)
        
        # Combine
        strength = (volume_score * 0.3 +
                   duration_score * 0.3 +
                   pattern_score * 0.4)
        
        return max(0, min(1, strength))
    
    def _calculate_confidence(self, segment: pd.DataFrame, pattern_type: str) -> float:
        """
        Calculate continuation pattern confidence.
        
        Args:
            segment: Price segment
            pattern_type: Pattern type
            
        Returns:
            Confidence score (0-1)
        """
        high = segment['high'].values
        low = segment['low'].values
        close = segment['close'].values
        
        # Price consistency
        price_std = np.std(close)
        price_mean = np.mean(close)
        consistency = 1 - min(price_std / (price_mean + 1e-10), 1.0)
        
        # Pattern recognition score
        pattern_scores = {
            'flag': 0.9,
            'pennant': 0.8,
            'wedge': 0.7,
            'triangle': 0.6
        }
        pattern_score = pattern_scores.get(pattern_type, 0.5)
        
        # Duration factor
        duration_score = min(len(segment) / 20, 1.0)
        
        # Combine
        confidence = (consistency * 0.3 +
                     pattern_score * 0.4 +
                     duration_score * 0.3)
        
        return max(0, min(1, confidence))
    
    def _generate_signals(self, df: pd.DataFrame,
                         patterns: List[ContinuationPattern]) -> List[ContinuationSignal]:
        """
        Generate trading signals from continuation patterns.
        
        Args:
            df: OHLCV data
            patterns: List of continuation patterns
            
        Returns:
            List of ContinuationSignal objects
        """
        signals = []
        
        if not patterns:
            return signals
        
        latest_pattern = patterns[-1]
        
        if latest_pattern.confidence < self.confidence_threshold:
            return signals
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check if pattern is still valid
        if latest_pattern.breakout_price is None:
            return signals
        
        # Determine signal
        if latest_pattern.direction == 'bullish':
            if current_price > latest_pattern.breakout_price:
                signal_type = 'buy'
                reason = f"Bullish continuation from {latest_pattern.pattern_type}"
                confidence = latest_pattern.confidence
                target = latest_pattern.target_price
                stop_loss = latest_pattern.low_price * 0.98
            else:
                return signals
        elif latest_pattern.direction == 'bearish':
            if current_price < latest_pattern.breakout_price:
                signal_type = 'sell'
                reason = f"Bearish continuation from {latest_pattern.pattern_type}"
                confidence = latest_pattern.confidence
                target = latest_pattern.target_price
                stop_loss = latest_pattern.high_price * 1.02
            else:
                return signals
        else:
            return signals
        
        signals.append(ContinuationSignal(
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
                'pattern_type': latest_pattern.pattern_type,
                'duration': latest_pattern.duration,
                'strength': latest_pattern.strength
            }
        ))
        
        return signals
    
    def _get_market_character(self, df: pd.DataFrame,
                            patterns: List[ContinuationPattern]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            patterns: List of continuation patterns
            
        Returns:
            Market character description
        """
        if not patterns:
            return "No continuation patterns detected"
        
        latest = patterns[-1]
        
        pattern_names = {
            'flag': 'Flag',
            'pennant': 'Pennant',
            'rising_wedge': 'Rising Wedge',
            'falling_wedge': 'Falling Wedge',
            'symmetrical': 'Symmetrical Triangle',
            'ascending': 'Ascending Triangle',
            'descending': 'Descending Triangle'
        }
        
        direction_names = {
            'bullish': 'Bullish',
            'bearish': 'Bearish',
            'neutral': 'Neutral'
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
        
        pattern_name = pattern_names.get(latest.pattern_type, latest.pattern_type)
        direction_name = direction_names.get(latest.direction, '')
        
        return f"{strength_names[strength_level]} {direction_name} {pattern_name} continuation"


def create_continuation_model(config: Optional[Dict[str, Any]] = None) -> ContinuationModel:
    """
    Create a continuation model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        ContinuationModel instance
    """
    return ContinuationModel(config)


__all__ = [
    'ContinuationPattern',
    'ContinuationSignal',
    'ContinuationModel',
    'create_continuation_model'
]
