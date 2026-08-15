"""
Swing Bot Trendline Model
===========================

This module provides trendline analysis models for the Swing Bot trading system.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class Trendline:
    """Trendline data structure."""
    trend_type: str  # 'support', 'resistance', 'trend'
    direction: str  # 'up', 'down', 'horizontal'
    start_date: datetime
    end_date: datetime
    start_price: float
    end_price: float
    slope: float
    intercept: float
    touch_count: int
    strength: float
    confidence: float
    points: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TrendlineSignal:
    """Trendline trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    trendline_type: str
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class TrendlineModel:
    """
    Trendline analysis model.
    
    Identifies and analyzes support and resistance trendlines.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the trendline model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.min_touch_points = self.config.get('min_touch_points', 2)
        self.max_trendline_error = self.config.get('max_trendline_error', 0.02)
        self.lookback_period = self.config.get('lookback_period', 100)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.touch_threshold = self.config.get('touch_threshold', 0.005)
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze trendlines.
        
        Args:
            df: OHLCV data
            
        Returns:
            Trendline analysis results
        """
        if len(df) < self.lookback_period:
            return {'trendlines': [], 'signals': []}
        
        # Detect trendlines
        trendlines = self._detect_trendlines(df)
        
        # Generate signals
        signals = self._generate_signals(df, trendlines)
        
        return {
            'trendlines': trendlines,
            'signals': signals,
            'current_trendline': trendlines[-1] if trendlines else None,
            'market_character': self._get_market_character(df, trendlines)
        }
    
    def _detect_trendlines(self, df: pd.DataFrame) -> List[Trendline]:
        """
        Detect trendlines.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of Trendline objects
        """
        trendlines = []
        
        # Find swing points
        swing_highs = self._find_swing_points(df['high'].values, 'high')
        swing_lows = self._find_swing_points(df['low'].values, 'low')
        
        # Detect support trendlines (from lows)
        support_lines = self._find_support_lines(df, swing_lows)
        trendlines.extend(support_lines)
        
        # Detect resistance trendlines (from highs)
        resistance_lines = self._find_resistance_lines(df, swing_highs)
        trendlines.extend(resistance_lines)
        
        # Detect trend lines (using closing prices)
        trend_lines = self._find_trend_lines(df)
        trendlines.extend(trend_lines)
        
        return trendlines
    
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
    
    def _find_support_lines(self, df: pd.DataFrame, lows: List[Dict[str, Any]]) -> List[Trendline]:
        """
        Find support trendlines.
        
        Args:
            df: OHLCV data
            lows: Swing lows
            
        Returns:
            List of support trendlines
        """
        support_lines = []
        
        for i in range(len(lows) - self.min_touch_points):
            for j in range(i + self.min_touch_points, len(lows)):
                # Get points for trendline
                points = lows[i:j+1]
                
                # Fit trendline
                slope, intercept = self._fit_trendline([(p['index'], p['price']) for p in points])
                
                # Check if slope is positive (support should be rising) or zero
                if slope < -0.0001:
                    continue
                
                # Check if points are well aligned
                alignment_score = self._check_alignment(points, slope, intercept)
                if alignment_score < 0.5:
                    continue
                
                # Check if trendline is valid (not broken)
                if self._is_trendline_broken(df, slope, intercept, 'support'):
                    continue
                
                # Calculate trendline strength
                strength = self._calculate_strength(points, df, slope, intercept, 'support')
                
                # Create trendline
                trendline = Trendline(
                    trend_type='support',
                    direction='up' if slope > 0.001 else 'horizontal',
                    start_date=df.index[points[0]['index']] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    end_date=df.index[points[-1]['index']] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    start_price=points[0]['price'],
                    end_price=points[-1]['price'],
                    slope=slope,
                    intercept=intercept,
                    touch_count=len(points),
                    strength=strength,
                    confidence=alignment_score,
                    points=points
                )
                support_lines.append(trendline)
        
        return support_lines
    
    def _find_resistance_lines(self, df: pd.DataFrame, highs: List[Dict[str, Any]]) -> List[Trendline]:
        """
        Find resistance trendlines.
        
        Args:
            df: OHLCV data
            highs: Swing highs
            
        Returns:
            List of resistance trendlines
        """
        resistance_lines = []
        
        for i in range(len(highs) - self.min_touch_points):
            for j in range(i + self.min_touch_points, len(highs)):
                # Get points for trendline
                points = highs[i:j+1]
                
                # Fit trendline
                slope, intercept = self._fit_trendline([(p['index'], p['price']) for p in points])
                
                # Check if slope is negative (resistance should be falling) or zero
                if slope > 0.0001:
                    continue
                
                # Check if points are well aligned
                alignment_score = self._check_alignment(points, slope, intercept)
                if alignment_score < 0.5:
                    continue
                
                # Check if trendline is valid (not broken)
                if self._is_trendline_broken(df, slope, intercept, 'resistance'):
                    continue
                
                # Calculate trendline strength
                strength = self._calculate_strength(points, df, slope, intercept, 'resistance')
                
                # Create trendline
                trendline = Trendline(
                    trend_type='resistance',
                    direction='down' if slope < -0.001 else 'horizontal',
                    start_date=df.index[points[0]['index']] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    end_date=df.index[points[-1]['index']] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    start_price=points[0]['price'],
                    end_price=points[-1]['price'],
                    slope=slope,
                    intercept=intercept,
                    touch_count=len(points),
                    strength=strength,
                    confidence=alignment_score,
                    points=points
                )
                resistance_lines.append(trendline)
        
        return resistance_lines
    
    def _find_trend_lines(self, df: pd.DataFrame) -> List[Trendline]:
        """
        Find trend lines using linear regression on closing prices.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of trendlines
        """
        trend_lines = []
        
        # Use closing prices for trend lines
        close = df['close'].values
        indices = np.arange(len(df))
        
        # Check for uptrend
        slope, intercept = self._fit_trendline(list(zip(indices, close)))
        
        if slope > 0.001:
            # Check if trend is strong
            r2 = MathUtils.r_squared(indices, close)
            if r2 > 0.5:
                trendline = Trendline(
                    trend_type='trend',
                    direction='up',
                    start_date=df.index[0] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    end_date=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    start_price=close[0],
                    end_price=close[-1],
                    slope=slope,
                    intercept=intercept,
                    touch_count=len(df),
                    strength=r2,
                    confidence=r2,
                    points=[{'index': i, 'price': p} for i, p in enumerate(close)]
                )
                trend_lines.append(trendline)
        
        elif slope < -0.001:
            # Check if trend is strong
            r2 = MathUtils.r_squared(indices, close)
            if r2 > 0.5:
                trendline = Trendline(
                    trend_type='trend',
                    direction='down',
                    start_date=df.index[0] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    end_date=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    start_price=close[0],
                    end_price=close[-1],
                    slope=slope,
                    intercept=intercept,
                    touch_count=len(df),
                    strength=r2,
                    confidence=r2,
                    points=[{'index': i, 'price': p} for i, p in enumerate(close)]
                )
                trend_lines.append(trendline)
        
        return trend_lines
    
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
    
    def _check_alignment(self, points: List[Dict[str, Any]],
                        slope: float, intercept: float) -> float:
        """
        Check alignment of points to trendline.
        
        Args:
            points: Swing points
            slope: Trendline slope
            intercept: Trendline intercept
            
        Returns:
            Alignment score (0-1)
        """
        if len(points) < 2:
            return 0.0
        
        errors = []
        for p in points:
            predicted = slope * p['index'] + intercept
            error = abs(p['price'] - predicted) / p['price']
            errors.append(error)
        
        avg_error = np.mean(errors)
        return max(0.0, 1.0 - avg_error / self.max_trendline_error)
    
    def _is_trendline_broken(self, df: pd.DataFrame, slope: float,
                            intercept: float, trend_type: str) -> bool:
        """
        Check if trendline has been broken.
        
        Args:
            df: OHLCV data
            slope: Trendline slope
            intercept: Trendline intercept
            trend_type: 'support' or 'resistance'
            
        Returns:
            True if broken, False otherwise
        """
        close = df['close'].values
        
        if trend_type == 'support':
            # Check if price has broken below support
            for i in range(len(close)):
                trend_value = slope * i + intercept
                if close[i] < trend_value * (1 - self.touch_threshold):
                    return True
        else:  # resistance
            # Check if price has broken above resistance
            for i in range(len(close)):
                trend_value = slope * i + intercept
                if close[i] > trend_value * (1 + self.touch_threshold):
                    return True
        
        return False
    
    def _calculate_strength(self, points: List[Dict[str, Any]], df: pd.DataFrame,
                           slope: float, intercept: float, trend_type: str) -> float:
        """
        Calculate trendline strength.
        
        Args:
            points: Swing points
            df: OHLCV data
            slope: Trendline slope
            intercept: Trendline intercept
            trend_type: 'support' or 'resistance'
            
        Returns:
            Strength score (0-1)
        """
        # Number of touches
        touch_score = min(len(points) / 5, 1.0)
        
        # Price range
        price_range = (df['high'].max() - df['low'].min()) / df['close'].mean()
        range_score = min(price_range * 5, 1.0)
        
        # Trend duration
        duration = len(df)
        duration_score = min(duration / 50, 1.0)
        
        # Volume confirmation
        volume_score = self._check_volume_confirmation(df, slope, intercept, trend_type)
        
        # Weighted average
        strength = (touch_score * 0.3 + range_score * 0.2 +
                   duration_score * 0.2 + volume_score * 0.3)
        
        return min(max(strength, 0.0), 1.0)
    
    def _check_volume_confirmation(self, df: pd.DataFrame, slope: float,
                                  intercept: float, trend_type: str) -> float:
        """
        Check volume confirmation for trendline.
        
        Args:
            df: OHLCV data
            slope: Trendline slope
            intercept: Trendline intercept
            trend_type: 'support' or 'resistance'
            
        Returns:
            Volume confirmation score (0-1)
        """
        volume = df['volume'].values
        close = df['close'].values
        
        # Check volume at touch points
        touch_volumes = []
        for i in range(len(close)):
            trend_value = slope * i + intercept
            if trend_type == 'support':
                if abs(close[i] - trend_value) / trend_value < self.touch_threshold:
                    touch_volumes.append(volume[i])
            else:  # resistance
                if abs(close[i] - trend_value) / trend_value < self.touch_threshold:
                    touch_volumes.append(volume[i])
        
        if not touch_volumes:
            return 0.0
        
        avg_volume = np.mean(touch_volumes)
        overall_avg = np.mean(volume)
        
        if overall_avg == 0:
            return 0.0
        
        ratio = avg_volume / overall_avg
        return min(ratio / 1.5, 1.0)
    
    def _generate_signal(self, df: pd.DataFrame, trendline: Trendline) -> Optional[TrendlineSignal]:
        """
        Generate trading signal from trendline.
        
        Args:
            df: OHLCV data
            trendline: Trendline
            
        Returns:
            TrendlineSignal or None
        """
        if trendline.confidence < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        current_index = len(df) - 1
        trend_value = trendline.slope * current_index + trendline.intercept
        
        # Check for bounce or breakout
        if trendline.trend_type == 'support':
            if current_price > trend_value * (1 + self.touch_threshold):
                # Bounce off support
                signal_type = 'buy'
                reason = f"Bounce off support trendline"
                target = trend_value + (trend_value - df['low'].min())
                stop_loss = trend_value * 0.98
            elif current_price < trend_value * (1 - self.touch_threshold):
                # Break below support
                signal_type = 'sell'
                reason = f"Break below support trendline"
                target = trend_value - (df['high'].max() - trend_value)
                stop_loss = trend_value * 1.02
            else:
                return None
                
        elif trendline.trend_type == 'resistance':
            if current_price > trend_value * (1 + self.touch_threshold):
                # Break above resistance
                signal_type = 'buy'
                reason = f"Break above resistance trendline"
                target = trend_value + (trend_value - df['low'].min())
                stop_loss = trend_value * 0.98
            elif current_price < trend_value * (1 - self.touch_threshold):
                # Rejection from resistance
                signal_type = 'sell'
                reason = f"Rejection from resistance trendline"
                target = trend_value - (df['high'].max() - trend_value)
                stop_loss = trend_value * 1.02
            else:
                return None
        else:
            return None
        
        return TrendlineSignal(
            symbol=df.get('symbol', [''])[0] if 'symbol' in df.columns else '',
            timestamp=datetime.now(),
            signal_type=signal_type,
            trendline_type=trendline.trend_type,
            confidence=trendline.confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            indicators={
                'trendline_strength': trendline.strength,
                'slope': trendline.slope,
                'touch_count': trendline.touch_count
            }
        )
    
    def _get_market_character(self, df: pd.DataFrame, trendlines: List[Trendline]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            trendlines: List of Trendline objects
            
        Returns:
            Market character description
        """
        if not trendlines:
            return "No significant trendlines detected"
        
        latest = trendlines[-1]
        
        if latest.trend_type == 'trend':
            if latest.direction == 'up':
                return f"Uptrend (strength: {latest.strength:.2f})"
            else:
                return f"Downtrend (strength: {latest.strength:.2f})"
        else:
            return f"{latest.trend_type.capitalize()} trendline ({latest.direction})"
    
    def get_trendline_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get trendline statistics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Trendline statistics
        """
        analysis = self.analyze(df)
        trendlines = analysis['trendlines']
        
        if not trendlines:
            return {'total_trendlines': 0}
        
        stats = {
            'total_trendlines': len(trendlines),
            'support_lines': len([t for t in trendlines if t.trend_type == 'support']),
            'resistance_lines': len([t for t in trendlines if t.trend_type == 'resistance']),
            'trend_lines': len([t for t in trendlines if t.trend_type == 'trend']),
            'uptrends': len([t for t in trendlines if t.direction == 'up']),
            'downtrends': len([t for t in trendlines if t.direction == 'down']),
            'horizontal_lines': len([t for t in trendlines if t.direction == 'horizontal']),
            'avg_strength': np.mean([t.strength for t in trendlines]),
            'avg_confidence': np.mean([t.confidence for t in trendlines]),
            'avg_touch_count': np.mean([t.touch_count for t in trendlines])
        }
        
        return stats


def create_trendline_model(config: Optional[Dict[str, Any]] = None) -> TrendlineModel:
    """
    Create a trendline model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        TrendlineModel instance
    """
    return TrendlineModel(config)


__all__ = [
    'Trendline',
    'TrendlineSignal',
    'TrendlineModel',
    'create_trendline_model'
]
