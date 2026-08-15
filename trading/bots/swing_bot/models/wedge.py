"""
Swing Bot Wedge Model
=======================

This module provides wedge pattern analysis models for the Swing Bot trading system.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
from trading.bots.swing_bot.utils.validators import Validator


@dataclass
class WedgePattern:
    """Wedge pattern data structure."""
    pattern_type: str  # 'rising', 'falling'
    direction: str  # 'bullish', 'bearish', 'neutral'
    start_date: datetime
    end_date: datetime
    start_price: float
    end_price: float
    upper_trendline: List[Tuple[float, float]]
    lower_trendline: List[Tuple[float, float]]
    strength: float
    confidence: float
    breakout_price: float
    target_price: float
    volume_profile: Dict[str, float]


@dataclass
class WedgeSignal:
    """Wedge trading signal."""
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


class WedgeModel:
    """
    Wedge pattern analysis model.
    
    Identifies and analyzes rising and falling wedge patterns.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the wedge model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.min_pattern_length = self.config.get('min_pattern_length', 10)
        self.max_pattern_length = self.config.get('max_pattern_length', 50)
        self.min_price_range = self.config.get('min_price_range', 0.02)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.volume_threshold = self.config.get('volume_threshold', 1.5)
        self.max_trendline_error = self.config.get('max_trendline_error', 0.02)
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze wedge patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            Wedge analysis results
        """
        if len(df) < self.min_pattern_length:
            return {'patterns': [], 'signals': []}
        
        patterns = []
        signals = []
        
        # Detect wedges
        wedges = self._detect_wedges(df)
        patterns.extend(wedges)
        
        # Generate signals
        for wedge in wedges:
            signal = self._generate_signal(df, wedge)
            if signal:
                signals.append(signal)
        
        return {
            'patterns': patterns,
            'signals': signals,
            'current_pattern': patterns[-1] if patterns else None,
            'market_character': self._get_market_character(df, patterns)
        }
    
    def _detect_wedges(self, df: pd.DataFrame) -> List[WedgePattern]:
        """
        Detect wedge patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of wedge patterns
        """
        wedges = []
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        volume = df['volume'].values
        
        # Find swing points
        swing_highs = self._find_swing_points(high, 'high')
        swing_lows = self._find_swing_points(low, 'low')
        
        # Analyze wedge patterns
        for start_idx in range(len(swing_highs) - self.min_pattern_length):
            for end_idx in range(start_idx + self.min_pattern_length, 
                               min(start_idx + self.max_pattern_length + 1, len(swing_highs))):
                
                # Get segment data
                start = swing_highs[start_idx]
                end = swing_highs[end_idx]
                segment = df.iloc[start['index']:end['index'] + 1]
                
                if len(segment) < self.min_pattern_length:
                    continue
                
                # Check for rising wedge
                rising_wedge = self._check_rising_wedge(segment, swing_highs[start_idx:end_idx+1])
                if rising_wedge:
                    wedges.append(rising_wedge)
                    continue
                
                # Check for falling wedge
                falling_wedge = self._check_falling_wedge(segment, swing_lows[start_idx:end_idx+1])
                if falling_wedge:
                    wedges.append(falling_wedge)
        
        return wedges
    
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
    
    def _check_rising_wedge(self, segment: pd.DataFrame, swings: List[Dict[str, Any]]) -> Optional[WedgePattern]:
        """
        Check for rising wedge pattern.
        
        Args:
            segment: Price segment
            swings: Swing points
            
        Returns:
            WedgePattern or None
        """
        if len(segment) < self.min_pattern_length:
            return None
        
        # Get upper and lower trendlines
        upper_points = [(s['index'], s['price']) for s in swings if s['price'] > segment['close'].mean()]
        lower_points = [(s['index'], s['price']) for s in swings if s['price'] < segment['close'].mean()]
        
        if len(upper_points) < 2 or len(lower_points) < 2:
            return None
        
        # Fit trendlines
        upper_slope, upper_intercept = self._fit_trendline(upper_points)
        lower_slope, lower_intercept = self._fit_trendline(lower_points)
        
        # Check if both trendlines are rising
        if upper_slope <= 0 or lower_slope <= 0:
            return None
        
        # Check if trendlines are converging
        if upper_slope <= lower_slope:
            return None
        
        # Calculate pattern metrics
        convergence_point = self._find_convergence(upper_slope, upper_intercept, 
                                                   lower_slope, lower_intercept)
        
        if convergence_point is None:
            return None
        
        # Calculate pattern strength
        strength = self._calculate_pattern_strength(segment, upper_slope, lower_slope)
        confidence = self._calculate_confidence(segment, upper_points, lower_points)
        
        # Check if pattern is valid
        if confidence < self.confidence_threshold:
            return None
        
        # Determine direction
        direction = 'bearish' if segment['close'].iloc[-1] > segment['close'].mean() else 'neutral'
        
        return WedgePattern(
            pattern_type='rising',
            direction=direction,
            start_date=segment.index[0] if isinstance(segment.index, pd.DatetimeIndex) else datetime.now(),
            end_date=segment.index[-1] if isinstance(segment.index, pd.DatetimeIndex) else datetime.now(),
            start_price=segment['close'].iloc[0],
            end_price=segment['close'].iloc[-1],
            upper_trendline=upper_points,
            lower_trendline=lower_points,
            strength=strength,
            confidence=confidence,
            breakout_price=segment['close'].iloc[-1],
            target_price=self._calculate_target(segment, convergence_point, direction),
            volume_profile=self._calc_volume_profile(segment)
        )
    
    def _check_falling_wedge(self, segment: pd.DataFrame, swings: List[Dict[str, Any]]) -> Optional[WedgePattern]:
        """
        Check for falling wedge pattern.
        
        Args:
            segment: Price segment
            swings: Swing points
            
        Returns:
            WedgePattern or None
        """
        if len(segment) < self.min_pattern_length:
            return None
        
        # Get upper and lower trendlines
        upper_points = [(s['index'], s['price']) for s in swings if s['price'] > segment['close'].mean()]
        lower_points = [(s['index'], s['price']) for s in swings if s['price'] < segment['close'].mean()]
        
        if len(upper_points) < 2 or len(lower_points) < 2:
            return None
        
        # Fit trendlines
        upper_slope, upper_intercept = self._fit_trendline(upper_points)
        lower_slope, lower_intercept = self._fit_trendline(lower_points)
        
        # Check if both trendlines are falling
        if upper_slope >= 0 or lower_slope >= 0:
            return None
        
        # Check if trendlines are converging
        if upper_slope >= lower_slope:
            return None
        
        # Calculate pattern metrics
        convergence_point = self._find_convergence(upper_slope, upper_intercept,
                                                   lower_slope, lower_intercept)
        
        if convergence_point is None:
            return None
        
        # Calculate pattern strength
        strength = self._calculate_pattern_strength(segment, upper_slope, lower_slope)
        confidence = self._calculate_confidence(segment, upper_points, lower_points)
        
        # Check if pattern is valid
        if confidence < self.confidence_threshold:
            return None
        
        # Determine direction
        direction = 'bullish' if segment['close'].iloc[-1] < segment['close'].mean() else 'neutral'
        
        return WedgePattern(
            pattern_type='falling',
            direction=direction,
            start_date=segment.index[0] if isinstance(segment.index, pd.DatetimeIndex) else datetime.now(),
            end_date=segment.index[-1] if isinstance(segment.index, pd.DatetimeIndex) else datetime.now(),
            start_price=segment['close'].iloc[0],
            end_price=segment['close'].iloc[-1],
            upper_trendline=upper_points,
            lower_trendline=lower_points,
            strength=strength,
            confidence=confidence,
            breakout_price=segment['close'].iloc[-1],
            target_price=self._calculate_target(segment, convergence_point, direction),
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
                                   upper_slope: float, lower_slope: float) -> float:
        """Calculate wedge pattern strength."""
        # Price range
        price_range = (segment['high'].max() - segment['low'].min()) / segment['close'].mean()
        
        # Trendline convergence
        convergence_rate = abs(upper_slope - lower_slope)
        
        # Volume trend
        volume_trend = segment['volume'].pct_change().mean()
        
        strength = (price_range * 0.4 + convergence_rate * 0.3 + volume_trend * 0.3)
        return min(max(strength, 0.0), 1.0)
    
    def _calculate_confidence(self, segment: pd.DataFrame,
                            upper_points: List[Tuple[int, float]],
                            lower_points: List[Tuple[int, float]]) -> float:
        """Calculate pattern confidence."""
        # Point alignment
        upper_align = self._check_alignment(upper_points)
        lower_align = self._check_alignment(lower_points)
        
        # Volume confirmation
        volume_confirm = self._check_volume_confirm(segment)
        
        # Price movement
        price_movement = abs(segment['close'].iloc[-1] - segment['close'].iloc[0]) / segment['close'].iloc[0]
        
        confidence = (upper_align * 0.3 + lower_align * 0.3 + volume_confirm * 0.2 + price_movement * 0.2)
        return min(max(confidence, 0.0), 1.0)
    
    def _check_alignment(self, points: List[Tuple[int, float]]) -> float:
        """Check alignment of points to trendline."""
        if len(points) < 2:
            return 0.0
        
        slope, intercept = self._fit_trendline(points)
        
        errors = []
        for x, y in points:
            predicted = slope * x + intercept
            error = abs(y - predicted) / y
            errors.append(error)
        
        avg_error = np.mean(errors)
        return max(0.0, 1.0 - avg_error / self.max_trendline_error)
    
    def _check_volume_confirm(self, segment: pd.DataFrame) -> float:
        """Check volume confirmation."""
        # Check volume increasing toward breakout
        if len(segment) < 5:
            return 0.0
        
        recent_volume = segment['volume'].tail(3).mean()
        past_volume = segment['volume'].head(3).mean()
        
        if past_volume == 0:
            return 0.0
        
        ratio = recent_volume / past_volume
        return min(ratio / self.volume_threshold, 1.0)
    
    def _calculate_target(self, segment: pd.DataFrame, convergence: float, direction: str) -> float:
        """Calculate price target."""
        if direction == 'bullish':
            target = segment['high'].max() + (segment['high'].max() - segment['low'].min())
        elif direction == 'bearish':
            target = segment['low'].min() - (segment['high'].max() - segment['low'].min())
        else:
            target = segment['close'].iloc[-1]
        
        return target
    
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
    
    def _generate_signal(self, df: pd.DataFrame, wedge: WedgePattern) -> Optional[WedgeSignal]:
        """
        Generate trading signal from wedge pattern.
        
        Args:
            df: OHLCV data
            wedge: Wedge pattern
            
        Returns:
            WedgeSignal or None
        """
        if wedge.confidence < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        breakout_price = wedge.breakout_price
        target = wedge.target_price
        
        # Determine signal type
        if wedge.pattern_type == 'falling' and wedge.direction == 'bullish':
            signal_type = 'buy'
            reason = f"Falling wedge breakout - bull trend"
            stop_loss = min([p[1] for p in wedge.lower_trendline]) * 0.98
            
        elif wedge.pattern_type == 'rising' and wedge.direction == 'bearish':
            signal_type = 'sell'
            reason = f"Rising wedge breakdown - bear trend"
            stop_loss = max([p[1] for p in wedge.upper_trendline]) * 1.02
            
        else:
            return None
        
        # Check if signal is valid
        if current_price <= breakout_price and signal_type == 'buy':
            return None
        if current_price >= breakout_price and signal_type == 'sell':
            return None
        
        return WedgeSignal(
            symbol=df.get('symbol', [''])[0] if 'symbol' in df.columns else '',
            timestamp=datetime.now(),
            signal_type=signal_type,
            pattern_type=wedge.pattern_type,
            confidence=wedge.confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            indicators={
                'pattern_strength': wedge.strength,
                'breakout_price': breakout_price,
                'volume_profile': wedge.volume_profile
            }
        )
    
    def _get_market_character(self, df: pd.DataFrame, patterns: List[WedgePattern]) -> str:
        """Get market character description."""
        if not patterns:
            return "No wedge patterns detected"
        
        latest = patterns[-1]
        return f"{latest.pattern_type.capitalize()} wedge - {latest.direction.capitalize()}"
    
    def get_wedge_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get wedge statistics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Wedge statistics
        """
        analysis = self.analyze(df)
        patterns = analysis['patterns']
        
        if not patterns:
            return {'total_patterns': 0}
        
        stats = {
            'total_patterns': len(patterns),
            'rising_wedges': len([p for p in patterns if p.pattern_type == 'rising']),
            'falling_wedges': len([p for p in patterns if p.pattern_type == 'falling']),
            'bullish_signals': len([p for p in patterns if p.direction == 'bullish']),
            'bearish_signals': len([p for p in patterns if p.direction == 'bearish']),
            'avg_confidence': np.mean([p.confidence for p in patterns]),
            'avg_strength': np.mean([p.strength for p in patterns])
        }
        
        return stats


def create_wedge_model(config: Optional[Dict[str, Any]] = None) -> WedgeModel:
    """
    Create a wedge model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        WedgeModel instance
    """
    return WedgeModel(config)


__all__ = [
    'WedgePattern',
    'WedgeSignal',
    'WedgeModel',
    'create_wedge_model'
]
