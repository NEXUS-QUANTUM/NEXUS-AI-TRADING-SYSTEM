"""
Swing Bot Reversal Model
==========================

This module provides reversal pattern analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class ReversalPattern:
    """Reversal pattern data structure."""
    pattern_type: str  # 'double_top', 'double_bottom', 'head_shoulders', 'rounded', 'divergence'
    direction: str  # 'bullish', 'bearish'
    start_price: float
    end_price: float
    breakout_price: float
    target_price: float
    stop_loss: float
    confidence: float
    timestamp: datetime
    indicators: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReversalSignal:
    """Reversal trading signal."""
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


class ReversalModel:
    """
    Reversal pattern analysis model.
    
    Identifies and analyzes reversal patterns:
    - Double Top/Bottom
    - Head and Shoulders
    - Rounded Tops/Bottoms
    - Divergence patterns
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the reversal model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 100)
        self.min_pattern_length = self.config.get('min_pattern_length', 10)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.volume_threshold = self.config.get('volume_threshold', 1.5)
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze reversal patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            Reversal analysis results
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
    
    def _detect_patterns(self, df: pd.DataFrame) -> List[ReversalPattern]:
        """
        Detect reversal patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of ReversalPattern objects
        """
        patterns = []
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        volume = df['volume'].values
        
        # Find swing points
        swing_highs = self._find_swing_points(high, 'high')
        swing_lows = self._find_swing_points(low, 'low')
        
        # Double Top
        double_top = self._detect_double_top(df, swing_highs)
        if double_top:
            patterns.append(double_top)
        
        # Double Bottom
        double_bottom = self._detect_double_bottom(df, swing_lows)
        if double_bottom:
            patterns.append(double_bottom)
        
        # Head and Shoulders
        head_shoulders = self._detect_head_shoulders(df, swing_highs, swing_lows)
        if head_shoulders:
            patterns.extend(head_shoulders)
        
        # Rounded patterns
        rounded = self._detect_rounded_patterns(df)
        if rounded:
            patterns.extend(rounded)
        
        # Divergence
        divergence = self._detect_divergence(df)
        if divergence:
            patterns.extend(divergence)
        
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
    
    def _detect_double_top(self, df: pd.DataFrame,
                          swing_highs: List[Dict[str, Any]]) -> Optional[ReversalPattern]:
        """
        Detect double top pattern.
        
        Args:
            df: OHLCV data
            swing_highs: Swing highs
            
        Returns:
            ReversalPattern or None
        """
        if len(swing_highs) < 2:
            return None
        
        # Get last two highs
        high1 = swing_highs[-2]
        high2 = swing_highs[-1]
        
        # Check if they are similar
        price_diff = abs(high1['price'] - high2['price']) / high1['price']
        if price_diff > 0.02:
            return None
        
        # Check distance between highs
        distance = high2['index'] - high1['index']
        if distance < self.min_pattern_length:
            return None
        
        # Check for trough between highs
        trough_idx = int((high1['index'] + high2['index']) / 2)
        trough_price = df['low'].iloc[trough_idx]
        
        # Calculate target
        target = high1['price'] + (high1['price'] - trough_price)
        
        # Calculate confidence
        confidence = self._calculate_double_pattern_confidence(df, high1, high2, trough_price)
        
        if confidence < self.confidence_threshold:
            return None
        
        return ReversalPattern(
            pattern_type='double_top',
            direction='bearish',
            start_price=high1['price'],
            end_price=high2['price'],
            breakout_price=trough_price,
            target_price=target,
            stop_loss=high2['price'] * 1.02,
            confidence=confidence,
            timestamp=datetime.now(),
            indicators={
                'price_diff': price_diff,
                'distance': distance,
                'trough_price': trough_price
            }
        )
    
    def _detect_double_bottom(self, df: pd.DataFrame,
                             swing_lows: List[Dict[str, Any]]) -> Optional[ReversalPattern]:
        """
        Detect double bottom pattern.
        
        Args:
            df: OHLCV data
            swing_lows: Swing lows
            
        Returns:
            ReversalPattern or None
        """
        if len(swing_lows) < 2:
            return None
        
        # Get last two lows
        low1 = swing_lows[-2]
        low2 = swing_lows[-1]
        
        # Check if they are similar
        price_diff = abs(low1['price'] - low2['price']) / low1['price']
        if price_diff > 0.02:
            return None
        
        # Check distance between lows
        distance = low2['index'] - low1['index']
        if distance < self.min_pattern_length:
            return None
        
        # Check for peak between lows
        peak_idx = int((low1['index'] + low2['index']) / 2)
        peak_price = df['high'].iloc[peak_idx]
        
        # Calculate target
        target = low1['price'] - (peak_price - low1['price'])
        
        # Calculate confidence
        confidence = self._calculate_double_pattern_confidence(df, low1, low2, peak_price)
        
        if confidence < self.confidence_threshold:
            return None
        
        return ReversalPattern(
            pattern_type='double_bottom',
            direction='bullish',
            start_price=low1['price'],
            end_price=low2['price'],
            breakout_price=peak_price,
            target_price=target,
            stop_loss=low2['price'] * 0.98,
            confidence=confidence,
            timestamp=datetime.now(),
            indicators={
                'price_diff': price_diff,
                'distance': distance,
                'peak_price': peak_price
            }
        )
    
    def _detect_head_shoulders(self, df: pd.DataFrame,
                             swing_highs: List[Dict[str, Any]],
                             swing_lows: List[Dict[str, Any]]) -> List[ReversalPattern]:
        """
        Detect head and shoulders patterns.
        
        Args:
            df: OHLCV data
            swing_highs: Swing highs
            swing_lows: Swing lows
            
        Returns:
            List of ReversalPattern objects
        """
        patterns = []
        
        if len(swing_highs) < 3:
            return patterns
        
        # Check for head and shoulders (bearish)
        left_shoulder = swing_highs[-3]
        head = swing_highs[-2]
        right_shoulder = swing_highs[-1]
        
        if (head['price'] > left_shoulder['price'] and
            head['price'] > right_shoulder['price'] and
            abs(left_shoulder['price'] - right_shoulder['price']) / left_shoulder['price'] < 0.03):
            
            # Find neckline
            neckline = min(swing_lows, key=lambda x: abs(x['index'] - head['index']))
            
            # Calculate target
            target = neckline['price'] - (head['price'] - neckline['price'])
            
            # Calculate confidence
            confidence = self._calculate_head_shoulders_confidence(df, left_shoulder, head, right_shoulder, neckline)
            
            if confidence > self.confidence_threshold:
                patterns.append(ReversalPattern(
                    pattern_type='head_shoulders',
                    direction='bearish',
                    start_price=left_shoulder['price'],
                    end_price=right_shoulder['price'],
                    breakout_price=neckline['price'],
                    target_price=target,
                    stop_loss=head['price'] * 1.02,
                    confidence=confidence,
                    timestamp=datetime.now(),
                    indicators={
                        'left_shoulder': left_shoulder['price'],
                        'head': head['price'],
                        'right_shoulder': right_shoulder['price'],
                        'neckline': neckline['price']
                    }
                ))
        
        return patterns
    
    def _detect_rounded_patterns(self, df: pd.DataFrame) -> List[ReversalPattern]:
        """
        Detect rounded patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of ReversalPattern objects
        """
        patterns = []
        
        # Check for rounded top
        if len(df) < 30:
            return patterns
        
        # Detect rounded top (bearish)
        close = df['close'].values
        segment = close[-30:]
        
        # Check for curved shape
        curvature = self._calculate_curvature(segment)
        
        if curvature > 0.5:
            # Rounded top
            patterns.append(ReversalPattern(
                pattern_type='rounded',
                direction='bearish',
                start_price=segment[0],
                end_price=segment[-1],
                breakout_price=segment[0] * 0.98,
                target_price=segment[-1] * 0.95,
                stop_loss=segment[0] * 1.02,
                confidence=curvature,
                timestamp=datetime.now(),
                indicators={'curvature': curvature}
            ))
        
        return patterns
    
    def _detect_divergence(self, df: pd.DataFrame) -> List[ReversalPattern]:
        """
        Detect divergence patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of ReversalPattern objects
        """
        patterns = []
        close = df['close'].values
        rsi = self._calculate_rsi(close)
        
        # Find swing points in price and RSI
        price_swings = self._find_swing_points(close, 'low')
        rsi_swings = self._find_swing_points(rsi, 'low')
        
        if len(price_swings) < 2 or len(rsi_swings) < 2:
            return patterns
        
        # Bullish divergence
        if (price_swings[-1]['price'] < price_swings[-2]['price'] and
            rsi_swings[-1]['price'] > rsi_swings[-2]['price']):
            patterns.append(ReversalPattern(
                pattern_type='divergence',
                direction='bullish',
                start_price=price_swings[-2]['price'],
                end_price=price_swings[-1]['price'],
                breakout_price=price_swings[-1]['price'] * 1.01,
                target_price=price_swings[-1]['price'] * 1.05,
                stop_loss=price_swings[-1]['price'] * 0.98,
                confidence=0.7,
                timestamp=datetime.now(),
                indicators={
                    'price_low': price_swings[-1]['price'],
                    'rsi_low': rsi_swings[-1]['price']
                }
            ))
        
        return patterns
    
    def _calculate_curvature(self, prices: np.ndarray) -> float:
        """
        Calculate curvature of a price segment.
        
        Args:
            prices: Price array
            
        Returns:
            Curvature value (0-1)
        """
        if len(prices) < 3:
            return 0.0
        
        # Fit quadratic
        x = np.arange(len(prices))
        coeffs = np.polyfit(x, prices, 2)
        
        # Check if concave (rounded top) or convex (rounded bottom)
        if coeffs[0] < 0:
            curvature = 1 - min(abs(coeffs[0]) * 10, 1.0)
        else:
            curvature = min(abs(coeffs[0]) * 10, 1.0)
        
        return curvature
    
    def _calculate_rsi(self, close: np.ndarray) -> np.ndarray:
        """
        Calculate RSI.
        
        Args:
            close: Close prices
            
        Returns:
            RSI values
        """
        if len(close) < 15:
            return np.zeros(len(close))
        
        returns = np.diff(close)
        gains = np.where(returns > 0, returns, 0)
        losses = np.where(returns < 0, -returns, 0)
        
        rsi = np.zeros(len(close))
        avg_gain = np.mean(gains[:14])
        avg_loss = np.mean(losses[:14])
        
        for i in range(14, len(close)):
            if avg_loss == 0:
                rsi[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi[i] = 100 - (100 / (1 + rs))
            
            avg_gain = (avg_gain * 13 + gains[i]) / 14
            avg_loss = (avg_loss * 13 + losses[i]) / 14
        
        return rsi
    
    def _calculate_double_pattern_confidence(self, df: pd.DataFrame,
                                            point1: Dict[str, Any],
                                            point2: Dict[str, Any],
                                            mid_price: float) -> float:
        """
        Calculate confidence for double top/bottom pattern.
        
        Args:
            df: OHLCV data
            point1: First point
            point2: Second point
            mid_price: Middle price
            
        Returns:
            Confidence score (0-1)
        """
        # Price similarity
        price_sim = 1 - abs(point1['price'] - point2['price']) / point1['price']
        
        # Volume confirmation
        volume1 = df['volume'].iloc[point1['index']]
        volume2 = df['volume'].iloc[point2['index']]
        volume_ratio = min(volume1 / volume2, volume2 / volume1) if volume2 > 0 else 0
        
        # Distance ratio
        distance = point2['index'] - point1['index']
        distance_score = min(distance / 20, 1.0)
        
        # Weighted combination
        confidence = (price_sim * 0.4 + volume_ratio * 0.3 + distance_score * 0.3)
        
        return min(max(confidence, 0.0), 1.0)
    
    def _calculate_head_shoulders_confidence(self, df: pd.DataFrame,
                                            left_shoulder: Dict[str, Any],
                                            head: Dict[str, Any],
                                            right_shoulder: Dict[str, Any],
                                            neckline: Dict[str, Any]) -> float:
        """
        Calculate confidence for head and shoulders pattern.
        
        Args:
            df: OHLCV data
            left_shoulder: Left shoulder point
            head: Head point
            right_shoulder: Right shoulder point
            neckline: Neckline point
            
        Returns:
            Confidence score (0-1)
        """
        # Shoulder symmetry
        shoulder_diff = abs(left_shoulder['price'] - right_shoulder['price']) / left_shoulder['price']
        symmetry = 1 - min(shoulder_diff * 10, 0.5)
        
        # Head height
        head_height = (head['price'] - neckline['price']) / neckline['price']
        height_score = min(head_height * 5, 1.0)
        
        # Volume pattern (right shoulder should have lower volume)
        volume_left = df['volume'].iloc[left_shoulder['index']]
        volume_head = df['volume'].iloc[head['index']]
        volume_right = df['volume'].iloc[right_shoulder['index']]
        
        volume_pattern = 0.5
        if volume_right < volume_head:
            volume_pattern = 0.7
        if volume_right < volume_left:
            volume_pattern = 0.9
        
        # Weighted combination
        confidence = (symmetry * 0.3 + height_score * 0.3 + volume_pattern * 0.4)
        
        return min(max(confidence, 0.0), 1.0)
    
    def _generate_signals(self, df: pd.DataFrame,
                         patterns: List[ReversalPattern]) -> List[ReversalSignal]:
        """
        Generate trading signals from reversal patterns.
        
        Args:
            df: OHLCV data
            patterns: List of reversal patterns
            
        Returns:
            List of ReversalSignal objects
        """
        signals = []
        
        if not patterns:
            return signals
        
        latest_pattern = patterns[-1]
        
        if latest_pattern.confidence < self.confidence_threshold:
            return signals
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check if pattern has confirmed
        if latest_pattern.direction == 'bullish':
            if current_price > latest_pattern.breakout_price:
                signal_type = 'buy'
                reason = f"Bullish {latest_pattern.pattern_type} reversal confirmed"
                target = latest_pattern.target_price
                stop_loss = latest_pattern.stop_loss
            else:
                return None
        else:
            if current_price < latest_pattern.breakout_price:
                signal_type = 'sell'
                reason = f"Bearish {latest_pattern.pattern_type} reversal confirmed"
                target = latest_pattern.target_price
                stop_loss = latest_pattern.stop_loss
            else:
                return None
        
        signal = ReversalSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            pattern_type=latest_pattern.pattern_type,
            confidence=latest_pattern.confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            indicators=latest_pattern.indicators
        )
        signals.append(signal)
        
        return signals
    
    def _get_market_character(self, df: pd.DataFrame,
                            patterns: List[ReversalPattern]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            patterns: List of reversal patterns
            
        Returns:
            Market character description
        """
        if not patterns:
            return "No reversal patterns detected"
        
        latest = patterns[-1]
        
        direction_names = {
            'bullish': 'Bullish reversal',
            'bearish': 'Bearish reversal'
        }
        
        pattern_names = {
            'double_top': 'Double Top',
            'double_bottom': 'Double Bottom',
            'head_shoulders': 'Head and Shoulders',
            'rounded': 'Rounded',
            'divergence': 'Divergence'
        }
        
        return f"{direction_names[latest.direction]} - {pattern_names.get(latest.pattern_type, latest.pattern_type)}"


def create_reversal_model(config: Optional[Dict[str, Any]] = None) -> ReversalModel:
    """
    Create a reversal model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        ReversalModel instance
    """
    return ReversalModel(config)


__all__ = [
    'ReversalPattern',
    'ReversalSignal',
    'ReversalModel',
    'create_reversal_model'
]
