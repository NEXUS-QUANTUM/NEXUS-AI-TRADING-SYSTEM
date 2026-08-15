"""
Swing Bot Triangle Model
==========================

This module provides triangle pattern analysis models for the Swing Bot trading system.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class TrianglePattern:
    """Triangle pattern data structure."""
    pattern_type: str  # 'ascending', 'descending', 'symmetrical', 'expanding'
    direction: str  # 'bullish', 'bearish', 'neutral'
    start_date: datetime
    end_date: datetime
    start_price: float
    end_price: float
    upper_trendline: List[Tuple[float, float]]
    lower_trendline: List[Tuple[float, float]]
    apex_price: float
    breakout_price: float
    target_price: float
    strength: float
    confidence: float
    volume_profile: Dict[str, float]


@dataclass
class TriangleSignal:
    """Triangle trading signal."""
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


class TriangleModel:
    """
    Triangle pattern analysis model.
    
    Identifies and analyzes various triangle patterns:
    - Ascending triangle
    - Descending triangle
    - Symmetrical triangle
    - Expanding triangle
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the triangle model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.min_pattern_length = self.config.get('min_pattern_length', 15)
        self.max_pattern_length = self.config.get('max_pattern_length', 60)
        self.min_price_range = self.config.get('min_price_range', 0.02)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.volume_threshold = self.config.get('volume_threshold', 1.5)
        self.max_trendline_error = self.config.get('max_trendline_error', 0.02)
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze triangle patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            Triangle analysis results
        """
        if len(df) < self.min_pattern_length:
            return {'patterns': [], 'signals': []}
        
        patterns = []
        signals = []
        
        # Detect triangles
        triangles = self._detect_triangles(df)
        patterns.extend(triangles)
        
        # Generate signals
        for triangle in triangles:
            signal = self._generate_signal(df, triangle)
            if signal:
                signals.append(signal)
        
        return {
            'patterns': patterns,
            'signals': signals,
            'current_pattern': patterns[-1] if patterns else None,
            'market_character': self._get_market_character(df, patterns)
        }
    
    def _detect_triangles(self, df: pd.DataFrame) -> List[TrianglePattern]:
        """
        Detect triangle patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of TrianglePattern objects
        """
        triangles = []
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        # Find swing points
        swing_highs = self._find_swing_points(high, 'high')
        swing_lows = self._find_swing_points(low, 'low')
        
        # Analyze triangle patterns
        for start_idx in range(len(swing_highs) - self.min_pattern_length):
            for end_idx in range(start_idx + self.min_pattern_length,
                               min(start_idx + self.max_pattern_length + 1, len(swing_highs))):
                
                # Get segment data
                start = swing_highs[start_idx]
                end = swing_highs[end_idx]
                segment = df.iloc[start['index']:end['index'] + 1]
                
                if len(segment) < self.min_pattern_length:
                    continue
                
                # Check for ascending triangle
                ascending = self._check_ascending_triangle(segment, swing_highs[start_idx:end_idx+1])
                if ascending:
                    triangles.append(ascending)
                    continue
                
                # Check for descending triangle
                descending = self._check_descending_triangle(segment, swing_lows[start_idx:end_idx+1])
                if descending:
                    triangles.append(descending)
                    continue
                
                # Check for symmetrical triangle
                symmetrical = self._check_symmetrical_triangle(segment, swing_highs[start_idx:end_idx+1],
                                                               swing_lows[start_idx:end_idx+1])
                if symmetrical:
                    triangles.append(symmetrical)
                    continue
                
                # Check for expanding triangle
                expanding = self._check_expanding_triangle(segment, swing_highs[start_idx:end_idx+1],
                                                           swing_lows[start_idx:end_idx+1])
                if expanding:
                    triangles.append(expanding)
        
        return triangles
    
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
        lookback = self.config.get('swing_lookback', 5)
        
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
    
    def _check_ascending_triangle(self, segment: pd.DataFrame,
                                  highs: List[Dict[str, Any]]) -> Optional[TrianglePattern]:
        """
        Check for ascending triangle pattern.
        
        Args:
            segment: Price segment
            highs: Swing highs
            
        Returns:
            TrianglePattern or None
        """
        if len(segment) < self.min_pattern_length:
            return None
        
        # Get resistance level (flat top)
        resistance = max([h['price'] for h in highs]) if highs else 0
        if resistance == 0:
            return None
        
        # Get support trendline (rising bottom)
        lower_points = self._find_swing_points(segment['low'].values, 'low')
        if len(lower_points) < 2:
            return None
        
        lower_slope, lower_intercept = self._fit_trendline([(p['index'], p['price']) for p in lower_points])
        
        # Check if support is rising
        if lower_slope <= 0:
            return None
        
        # Check if price is approaching resistance
        if segment['close'].iloc[-1] < resistance * 0.95:
            return None
        
        # Calculate pattern metrics
        strength = self._calculate_pattern_strength(segment, resistance, lower_slope)
        confidence = self._calculate_confidence(segment, lower_points, resistance)
        
        if confidence < self.confidence_threshold:
            return None
        
        # Calculate targets
        breakout_price = resistance
        target_price = resistance + (resistance - lower_points[-1]['price'])
        
        return TrianglePattern(
            pattern_type='ascending',
            direction='bullish',
            start_date=segment.index[0] if isinstance(segment.index, pd.DatetimeIndex) else datetime.now(),
            end_date=segment.index[-1] if isinstance(segment.index, pd.DatetimeIndex) else datetime.now(),
            start_price=segment['close'].iloc[0],
            end_price=segment['close'].iloc[-1],
            upper_trendline=[(0, resistance), (len(segment), resistance)],
            lower_trendline=[(p['index'], p['price']) for p in lower_points],
            apex_price=resistance,
            breakout_price=breakout_price,
            target_price=target_price,
            strength=strength,
            confidence=confidence,
            volume_profile=self._calc_volume_profile(segment)
        )
    
    def _check_descending_triangle(self, segment: pd.DataFrame,
                                   lows: List[Dict[str, Any]]) -> Optional[TrianglePattern]:
        """
        Check for descending triangle pattern.
        
        Args:
            segment: Price segment
            lows: Swing lows
            
        Returns:
            TrianglePattern or None
        """
        if len(segment) < self.min_pattern_length:
            return None
        
        # Get support level (flat bottom)
        support = min([l['price'] for l in lows]) if lows else 0
        if support == 0:
            return None
        
        # Get resistance trendline (falling top)
        upper_points = self._find_swing_points(segment['high'].values, 'high')
        if len(upper_points) < 2:
            return None
        
        upper_slope, upper_intercept = self._fit_trendline([(p['index'], p['price']) for p in upper_points])
        
        # Check if resistance is falling
        if upper_slope >= 0:
            return None
        
        # Check if price is approaching support
        if segment['close'].iloc[-1] > support * 1.05:
            return None
        
        # Calculate pattern metrics
        strength = self._calculate_pattern_strength(segment, support, abs(upper_slope))
        confidence = self._calculate_confidence(segment, upper_points, support)
        
        if confidence < self.confidence_threshold:
            return None
        
        # Calculate targets
        breakout_price = support
        target_price = support - (upper_points[-1]['price'] - support)
        
        return TrianglePattern(
            pattern_type='descending',
            direction='bearish',
            start_date=segment.index[0] if isinstance(segment.index, pd.DatetimeIndex) else datetime.now(),
            end_date=segment.index[-1] if isinstance(segment.index, pd.DatetimeIndex) else datetime.now(),
            start_price=segment['close'].iloc[0],
            end_price=segment['close'].iloc[-1],
            upper_trendline=[(p['index'], p['price']) for p in upper_points],
            lower_trendline=[(0, support), (len(segment), support)],
            apex_price=support,
            breakout_price=breakout_price,
            target_price=target_price,
            strength=strength,
            confidence=confidence,
            volume_profile=self._calc_volume_profile(segment)
        )
    
    def _check_symmetrical_triangle(self, segment: pd.DataFrame,
                                   highs: List[Dict[str, Any]],
                                   lows: List[Dict[str, Any]]) -> Optional[TrianglePattern]:
        """
        Check for symmetrical triangle pattern.
        
        Args:
            segment: Price segment
            highs: Swing highs
            lows: Swing lows
            
        Returns:
            TrianglePattern or None
        """
        if len(segment) < self.min_pattern_length:
            return None
        
        if len(highs) < 2 or len(lows) < 2:
            return None
        
        # Fit trendlines
        upper_slope, upper_intercept = self._fit_trendline([(h['index'], h['price']) for h in highs])
        lower_slope, lower_intercept = self._fit_trendline([(l['index'], l['price']) for l in lows])
        
        # Check if trendlines are converging
        if upper_slope >= lower_slope:
            return None
        
        # Check if both trendlines are sloping toward each other
        if upper_slope > 0 and lower_slope > 0:
            # Rising triangle (could be symmetrical or ascending)
            if abs(upper_slope) > abs(lower_slope):
                return None  # Probably an ascending triangle
        elif upper_slope < 0 and lower_slope < 0:
            # Falling triangle (could be symmetrical or descending)
            if abs(upper_slope) < abs(lower_slope):
                return None  # Probably a descending triangle
        
        # Calculate pattern metrics
        convergence_point = self._find_convergence(upper_slope, upper_intercept,
                                                   lower_slope, lower_intercept)
        
        if convergence_point is None:
            return None
        
        strength = self._calculate_pattern_strength(segment, upper_slope, lower_slope)
        confidence = self._calculate_confidence(segment, highs + lows, None)
        
        if confidence < self.confidence_threshold:
            return None
        
        # Determine direction based on price position
        current_price = segment['close'].iloc[-1]
        upper_price = upper_slope * len(segment) + upper_intercept
        lower_price = lower_slope * len(segment) + lower_intercept
        mid_price = (upper_price + lower_price) / 2
        
        if current_price > mid_price:
            direction = 'bullish'
            breakout_price = upper_price
            target_price = upper_price + (upper_price - lower_price)
        else:
            direction = 'bearish'
            breakout_price = lower_price
            target_price = lower_price - (upper_price - lower_price)
        
        return TrianglePattern(
            pattern_type='symmetrical',
            direction=direction,
            start_date=segment.index[0] if isinstance(segment.index, pd.DatetimeIndex) else datetime.now(),
            end_date=segment.index[-1] if isinstance(segment.index, pd.DatetimeIndex) else datetime.now(),
            start_price=segment['close'].iloc[0],
            end_price=segment['close'].iloc[-1],
            upper_trendline=[(h['index'], h['price']) for h in highs],
            lower_trendline=[(l['index'], l['price']) for l in lows],
            apex_price=convergence_point,
            breakout_price=breakout_price,
            target_price=target_price,
            strength=strength,
            confidence=confidence,
            volume_profile=self._calc_volume_profile(segment)
        )
    
    def _check_expanding_triangle(self, segment: pd.DataFrame,
                                 highs: List[Dict[str, Any]],
                                 lows: List[Dict[str, Any]]) -> Optional[TrianglePattern]:
        """
        Check for expanding triangle pattern.
        
        Args:
            segment: Price segment
            highs: Swing highs
            lows: Swing lows
            
        Returns:
            TrianglePattern or None
        """
        if len(segment) < self.min_pattern_length:
            return None
        
        if len(highs) < 2 or len(lows) < 2:
            return None
        
        # Fit trendlines
        upper_slope, upper_intercept = self._fit_trendline([(h['index'], h['price']) for h in highs])
        lower_slope, lower_intercept = self._fit_trendline([(l['index'], l['price']) for l in lows])
        
        # Check if trendlines are diverging
        if upper_slope <= lower_slope:
            return None
        
        # Calculate pattern metrics
        strength = self._calculate_pattern_strength(segment, upper_slope, lower_slope)
        confidence = self._calculate_confidence(segment, highs + lows, None)
        
        if confidence < self.confidence_threshold:
            return None
        
        # Determine direction based on price position
        current_price = segment['close'].iloc[-1]
        upper_price = upper_slope * len(segment) + upper_intercept
        lower_price = lower_slope * len(segment) + lower_intercept
        mid_price = (upper_price + lower_price) / 2
        
        if current_price > mid_price:
            direction = 'bullish'
            breakout_price = upper_price
            target_price = upper_price + (upper_price - lower_price)
        else:
            direction = 'bearish'
            breakout_price = lower_price
            target_price = lower_price - (upper_price - lower_price)
        
        return TrianglePattern(
            pattern_type='expanding',
            direction=direction,
            start_date=segment.index[0] if isinstance(segment.index, pd.DatetimeIndex) else datetime.now(),
            end_date=segment.index[-1] if isinstance(segment.index, pd.DatetimeIndex) else datetime.now(),
            start_price=segment['close'].iloc[0],
            end_price=segment['close'].iloc[-1],
            upper_trendline=[(h['index'], h['price']) for h in highs],
            lower_trendline=[(l['index'], l['price']) for l in lows],
            apex_price=0,  # Expanding triangles don't converge
            breakout_price=breakout_price,
            target_price=target_price,
            strength=strength,
            confidence=confidence,
            volume_profile=self._calc_volume_profile(segment)
        )
    
    def _fit_trendline(self, points: List[Tuple[int, float]]) -> Tuple[float, float]:
        """
        Fit a linear trendline to points.
        
        Args:
            points: List of (x, y) points
            
        Returns:
            Tuple of (slope, intercept)
        """
        if len(points) < 2:
            return (0.0, 0.0)
        
        x = [p[0] for p in points]
        y = [p[1] for p in points]
        
        return MathUtils.linear_regression(x, y)
    
    def _find_convergence(self, slope1: float, intercept1: float,
                         slope2: float, intercept2: float) -> Optional[float]:
        """
        Find the convergence point of two trendlines.
        
        Args:
            slope1: Slope of first line
            intercept1: Intercept of first line
            slope2: Slope of second line
            intercept2: Intercept of second line
            
        Returns:
            Convergence point or None
        """
        if slope1 == slope2:
            return None
        
        x = (intercept2 - intercept1) / (slope1 - slope2)
        return x
    
    def _calculate_pattern_strength(self, segment: pd.DataFrame,
                                   slope1: float, slope2: float) -> float:
        """Calculate triangle pattern strength."""
        # Price range
        price_range = (segment['high'].max() - segment['low'].min()) / segment['close'].mean()
        
        # Trendline convergence/divergence
        convergence_rate = abs(slope1 - slope2)
        
        # Volume trend
        volume_trend = segment['volume'].pct_change().mean()
        
        strength = (price_range * 0.4 + convergence_rate * 0.3 + volume_trend * 0.3)
        return min(max(strength, 0.0), 1.0)
    
    def _calculate_confidence(self, segment: pd.DataFrame,
                            points: List[Dict[str, Any]],
                            flat_level: Optional[float]) -> float:
        """Calculate pattern confidence."""
        # Point alignment
        align_score = self._check_alignment(points)
        
        # Volume confirmation
        volume_confirm = self._check_volume_confirm(segment)
        
        # Price movement
        price_movement = abs(segment['close'].iloc[-1] - segment['close'].iloc[0]) / segment['close'].iloc[0]
        
        confidence = (align_score * 0.3 + volume_confirm * 0.2 + price_movement * 0.2)
        return min(max(confidence, 0.0), 1.0)
    
    def _check_alignment(self, points: List[Dict[str, Any]]) -> float:
        """Check alignment of points to trendline."""
        if len(points) < 2:
            return 0.0
        
        # Use first and last point to create trendline
        p1 = points[0]
        p2 = points[-1]
        
        if p2['index'] == p1['index']:
            return 0.0
        
        slope = (p2['price'] - p1['price']) / (p2['index'] - p1['index'])
        intercept = p1['price'] - slope * p1['index']
        
        errors = []
        for p in points:
            predicted = slope * p['index'] + intercept
            error = abs(p['price'] - predicted) / p['price']
            errors.append(error)
        
        avg_error = np.mean(errors)
        return max(0.0, 1.0 - avg_error / self.max_trendline_error)
    
    def _check_volume_confirm(self, segment: pd.DataFrame) -> float:
        """Check volume confirmation."""
        if len(segment) < 5:
            return 0.0
        
        recent_volume = segment['volume'].tail(3).mean()
        past_volume = segment['volume'].head(3).mean()
        
        if past_volume == 0:
            return 0.0
        
        ratio = recent_volume / past_volume
        return min(ratio / self.volume_threshold, 1.0)
    
    def _calc_volume_profile(self, segment: pd.DataFrame) -> Dict[str, float]:
        """Calculate volume profile."""
        price_range = segment['high'].max() - segment['low'].min()
        if price_range == 0:
            return {}
        
        bins = 10
        volume_profile = {}
        
        for i in range(bins):
            low = segment['low'].min() + (i / bins) * price_range
            high = segment['low'].min() + ((i + 1) / bins) * price_range
            
            mask = (segment['high'] >= low) & (segment['low'] <= high)
            volume = segment.loc[mask, 'volume'].sum()
            
            volume_profile[f"{low:.2f}-{high:.2f}"] = volume
        
        return volume_profile
    
    def _generate_signal(self, df: pd.DataFrame, triangle: TrianglePattern) -> Optional[TriangleSignal]:
        """
        Generate trading signal from triangle pattern.
        
        Args:
            df: OHLCV data
            triangle: Triangle pattern
            
        Returns:
            TriangleSignal or None
        """
        if triangle.confidence < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        breakout_price = triangle.breakout_price
        target = triangle.target_price
        
        # Determine signal type
        if triangle.direction == 'bullish':
            if current_price > breakout_price:
                signal_type = 'buy'
                reason = f"Bullish {triangle.pattern_type} triangle breakout"
                stop_loss = min([p[1] for p in triangle.lower_trendline]) * 0.98
            else:
                return None
                
        elif triangle.direction == 'bearish':
            if current_price < breakout_price:
                signal_type = 'sell'
                reason = f"Bearish {triangle.pattern_type} triangle breakdown"
                stop_loss = max([p[1] for p in triangle.upper_trendline]) * 1.02
            else:
                return None
        else:
            return None
        
        return TriangleSignal(
            symbol=df.get('symbol', [''])[0] if 'symbol' in df.columns else '',
            timestamp=datetime.now(),
            signal_type=signal_type,
            pattern_type=triangle.pattern_type,
            confidence=triangle.confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            indicators={
                'pattern_strength': triangle.strength,
                'breakout_price': breakout_price,
                'volume_profile': triangle.volume_profile
            }
        )
    
    def _get_market_character(self, df: pd.DataFrame, patterns: List[TrianglePattern]) -> str:
        """Get market character description."""
        if not patterns:
            return "No triangle patterns detected"
        
        latest = patterns[-1]
        return f"{latest.pattern_type.capitalize()} triangle - {latest.direction.capitalize()}"
    
    def get_triangle_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get triangle statistics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Triangle statistics
        """
        analysis = self.analyze(df)
        patterns = analysis['patterns']
        
        if not patterns:
            return {'total_patterns': 0}
        
        stats = {
            'total_patterns': len(patterns),
            'ascending_triangles': len([p for p in patterns if p.pattern_type == 'ascending']),
            'descending_triangles': len([p for p in patterns if p.pattern_type == 'descending']),
            'symmetrical_triangles': len([p for p in patterns if p.pattern_type == 'symmetrical']),
            'expanding_triangles': len([p for p in patterns if p.pattern_type == 'expanding']),
            'bullish_signals': len([p for p in patterns if p.direction == 'bullish']),
            'bearish_signals': len([p for p in patterns if p.direction == 'bearish']),
            'avg_confidence': np.mean([p.confidence for p in patterns]),
            'avg_strength': np.mean([p.strength for p in patterns])
        }
        
        return stats


def create_triangle_model(config: Optional[Dict[str, Any]] = None) -> TriangleModel:
    """
    Create a triangle model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        TriangleModel instance
    """
    return TriangleModel(config)


__all__ = [
    'TrianglePattern',
    'TriangleSignal',
    'TriangleModel',
    'create_triangle_model'
]
