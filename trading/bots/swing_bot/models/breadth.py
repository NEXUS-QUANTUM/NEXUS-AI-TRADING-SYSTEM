"""
Swing Bot Breadth Model
=========================

This module provides market breadth analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class BreadthIndicator:
    """Market breadth indicator data structure."""
    name: str
    value: float
    timestamp: datetime
    signal_type: Optional[str] = None
    confidence: float = 0.0


@dataclass
class BreadthSignal:
    """Market breadth trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    breadth_indicator: str
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class BreadthModel:
    """
    Market breadth analysis model.
    
    Analyzes market internals and breadth indicators.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the breadth model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 20)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.overbought_threshold = self.config.get('overbought_threshold', 70)
        self.oversold_threshold = self.config.get('oversold_threshold', 30)
        
        self.breadth_data: Dict[str, List[float]] = {}
        self.history: List[Dict[str, Any]] = []
        
    def analyze(self, market_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Analyze market breadth.
        
        Args:
            market_data: Dictionary of market data by symbol
            
        Returns:
            Breadth analysis results
        """
        if not market_data:
            return {'indicators': [], 'signals': [], 'breadth_status': 'unknown'}
        
        # Calculate breadth indicators
        indicators = self._calculate_indicators(market_data)
        
        # Generate signals
        signals = self._generate_signals(market_data, indicators)
        
        return {
            'indicators': indicators,
            'signals': signals,
            'breadth_status': self._get_breadth_status(indicators),
            'market_character': self._get_market_character(indicators)
        }
    
    def _calculate_indicators(self, market_data: Dict[str, pd.DataFrame]) -> List[BreadthIndicator]:
        """
        Calculate breadth indicators.
        
        Args:
            market_data: Dictionary of market data
            
        Returns:
            List of BreadthIndicator objects
        """
        indicators = []
        close_data = {}
        
        # Extract close prices
        for symbol, df in market_data.items():
            if len(df) > 0:
                close_data[symbol] = df['close'].values
        
        if not close_data:
            return indicators
        
        # Advance/Decline Line
        adv_dec_line = self._calculate_advance_decline_line(close_data)
        indicators.append(BreadthIndicator(
            name='advance_decline_line',
            value=adv_dec_line[-1] if adv_dec_line else 0,
            timestamp=datetime.now()
        ))
        
        # Advance/Decline Ratio
        adv_dec_ratio = self._calculate_advance_decline_ratio(close_data)
        indicators.append(BreadthIndicator(
            name='advance_decline_ratio',
            value=adv_dec_ratio,
            timestamp=datetime.now()
        ))
        
        # New Highs/Lows
        new_highs_lows = self._calculate_new_highs_lows(close_data)
        indicators.append(BreadthIndicator(
            name='new_highs_lows',
            value=new_highs_lows,
            timestamp=datetime.now()
        ))
        
        # Percentage Above Moving Average
        pct_above_ma = self._calculate_pct_above_ma(close_data)
        indicators.append(BreadthIndicator(
            name='pct_above_ma',
            value=pct_above_ma,
            timestamp=datetime.now()
        ))
        
        # Breadth Thrust
        breadth_thrust = self._calculate_breadth_thrust(close_data)
        indicators.append(BreadthIndicator(
            name='breadth_thrust',
            value=breadth_thrust,
            timestamp=datetime.now()
        ))
        
        # McClellan Oscillator
        mcclellan = self._calculate_mcclellan_oscillator(close_data)
        indicators.append(BreadthIndicator(
            name='mcclellan_oscillator',
            value=mcclellan,
            timestamp=datetime.now()
        ))
        
        # Bullish Percent Index
        bullish_pct = self._calculate_bullish_percent(close_data)
        indicators.append(BreadthIndicator(
            name='bullish_percent',
            value=bullish_pct,
            timestamp=datetime.now()
        ))
        
        # Store breadth data
        for indicator in indicators:
            if indicator.name not in self.breadth_data:
                self.breadth_data[indicator.name] = []
            self.breadth_data[indicator.name].append(indicator.value)
        
        return indicators
    
    def _calculate_advance_decline_line(self, close_data: Dict[str, np.ndarray]) -> List[float]:
        """
        Calculate Advance/Decline Line.
        
        Args:
            close_data: Dictionary of close prices
            
        Returns:
            Advance/Decline Line values
        """
        # Find common length
        min_length = min(len(v) for v in close_data.values())
        
        adv_dec_line = [0]
        
        for i in range(1, min_length):
            advances = 0
            declines = 0
            
            for symbol, close in close_data.items():
                if len(close) > i:
                    change = close[i] - close[i-1]
                    if change > 0:
                        advances += 1
                    elif change < 0:
                        declines += 1
            
            adv_dec_line.append(adv_dec_line[-1] + (advances - declines))
        
        return adv_dec_line
    
    def _calculate_advance_decline_ratio(self, close_data: Dict[str, np.ndarray]) -> float:
        """
        Calculate Advance/Decline Ratio.
        
        Args:
            close_data: Dictionary of close prices
            
        Returns:
            Advance/Decline Ratio
        """
        advances = 0
        declines = 0
        
        for symbol, close in close_data.items():
            if len(close) >= 2:
                change = close[-1] - close[-2]
                if change > 0:
                    advances += 1
                elif change < 0:
                    declines += 1
        
        if declines == 0:
            return advances
        return advances / declines
    
    def _calculate_new_highs_lows(self, close_data: Dict[str, np.ndarray]) -> float:
        """
        Calculate New Highs/Lows ratio.
        
        Args:
            close_data: Dictionary of close prices
            
        Returns:
            New Highs/Lows ratio
        """
        new_highs = 0
        new_lows = 0
        
        for symbol, close in close_data.items():
            if len(close) >= self.lookback_period + 1:
                recent_high = np.max(close[-self.lookback_period:])
                recent_low = np.min(close[-self.lookback_period:])
                
                if close[-1] > recent_high:
                    new_highs += 1
                elif close[-1] < recent_low:
                    new_lows += 1
        
        if new_highs + new_lows == 0:
            return 0.5
        
        return new_highs / (new_highs + new_lows)
    
    def _calculate_pct_above_ma(self, close_data: Dict[str, np.ndarray]) -> float:
        """
        Calculate Percentage Above Moving Average.
        
        Args:
            close_data: Dictionary of close prices
            
        Returns:
            Percentage Above MA
        """
        if self.lookback_period < 2:
            return 0.0
        
        above_ma = 0
        total = 0
        
        for symbol, close in close_data.items():
            if len(close) >= self.lookback_period:
                ma = np.mean(close[-self.lookback_period:])
                if close[-1] > ma:
                    above_ma += 1
                total += 1
        
        if total == 0:
            return 0.0
        
        return above_ma / total
    
    def _calculate_breadth_thrust(self, close_data: Dict[str, np.ndarray]) -> float:
        """
        Calculate Breadth Thrust indicator.
        
        Args:
            close_data: Dictionary of close prices
            
        Returns:
            Breadth Thrust value
        """
        if self.lookback_period < 2:
            return 0.0
        
        # Calculate 10-day advance-decline line
        adv_dec = self._calculate_advance_decline_line(close_data)
        
        if len(adv_dec) < self.lookback_period + 1:
            return 0.0
        
        # Calculate 10-day average of advances
        advances = []
        for i in range(1, min(len(adv_dec), self.lookback_period + 1)):
            if adv_dec[i] > adv_dec[i-1]:
                advances.append(1)
            else:
                advances.append(0)
        
        if not advances:
            return 0.0
        
        return np.mean(advances)
    
    def _calculate_mcclellan_oscillator(self, close_data: Dict[str, np.ndarray]) -> float:
        """
        Calculate McClellan Oscillator.
        
        Args:
            close_data: Dictionary of close prices
            
        Returns:
            McClellan Oscillator value
        """
        # Calculate 19-day and 39-day EMAs of advances-declines
        adv_dec = self._calculate_advance_decline_line(close_data)
        
        if len(adv_dec) < 40:
            return 0.0
        
        # Calculate advances-declines difference
        diff = []
        for i in range(1, len(adv_dec)):
            diff.append(adv_dec[i] - adv_dec[i-1])
        
        if not diff:
            return 0.0
        
        # Calculate EMAs
        ema19 = self._calculate_ema(diff, 19)
        ema39 = self._calculate_ema(diff, 39)
        
        if len(ema19) == 0 or len(ema39) == 0:
            return 0.0
        
        return ema19[-1] - ema39[-1]
    
    def _calculate_ema(self, data: List[float], period: int) -> List[float]:
        """
        Calculate Exponential Moving Average.
        
        Args:
            data: Input data
            period: EMA period
            
        Returns:
            EMA values
        """
        if len(data) < period:
            return []
        
        alpha = 2 / (period + 1)
        ema = [data[0]]
        
        for i in range(1, len(data)):
            ema.append(alpha * data[i] + (1 - alpha) * ema[-1])
        
        return ema
    
    def _calculate_bullish_percent(self, close_data: Dict[str, np.ndarray]) -> float:
        """
        Calculate Bullish Percent Index.
        
        Args:
            close_data: Dictionary of close prices
            
        Returns:
            Bullish Percent Index
        """
        bullish = 0
        total = 0
        
        for symbol, close in close_data.items():
            if len(close) >= 2:
                # Check if stock is in bullish pattern (higher highs and higher lows)
                if close[-1] > close[-2] and close[-1] > np.mean(close[-self.lookback_period:]):
                    bullish += 1
                total += 1
        
        if total == 0:
            return 0.0
        
        return bullish / total * 100
    
    def _generate_signals(self, market_data: Dict[str, pd.DataFrame],
                         indicators: List[BreadthIndicator]) -> List[BreadthSignal]:
        """
        Generate trading signals from breadth indicators.
        
        Args:
            market_data: Dictionary of market data
            indicators: List of breadth indicators
            
        Returns:
            List of BreadthSignal objects
        """
        signals = []
        
        # Get indicator values
        ind_dict = {i.name: i.value for i in indicators}
        
        # Check key indicators
        breadth_thrust = ind_dict.get('breadth_thrust', 0)
        bullish_pct = ind_dict.get('bullish_percent', 50)
        adv_dec_ratio = ind_dict.get('advance_decline_ratio', 0)
        pct_above_ma = ind_dict.get('pct_above_ma', 0)
        
        # Generate signals based on breadth conditions
        signal_type = None
        confidence = 0
        reason = ""
        
        # Oversold condition
        if breadth_thrust < 0.3 and bullish_pct < 30:
            signal_type = 'buy'
            confidence = min((30 - bullish_pct) / 30, 1.0) * 0.7 + (0.3 - breadth_thrust) * 0.3
            reason = "Oversold breadth conditions"
        
        # Overbought condition
        elif breadth_thrust > 0.7 and bullish_pct > 70:
            signal_type = 'sell'
            confidence = min((bullish_pct - 70) / 30, 1.0) * 0.7 + (breadth_thrust - 0.7) * 0.3
            reason = "Overbought breadth conditions"
        
        # Bullish divergence
        elif adv_dec_ratio > 1.5 and pct_above_ma < 0.5:
            signal_type = 'buy'
            confidence = min(adv_dec_ratio / 2, 1.0) * 0.6 + (0.5 - pct_above_ma) * 0.4
            reason = "Bullish breadth divergence"
        
        # Bearish divergence
        elif adv_dec_ratio < 0.5 and pct_above_ma > 0.5:
            signal_type = 'sell'
            confidence = min(abs(adv_dec_ratio) * 2, 1.0) * 0.6 + (pct_above_ma - 0.5) * 0.4
            reason = "Bearish breadth divergence"
        
        if signal_type and confidence > self.confidence_threshold:
            # Get first symbol for price
            symbol = next(iter(market_data.keys()))
            price = market_data[symbol]['close'].iloc[-1]
            
            signal = BreadthSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type=signal_type,
                breadth_indicator='composite',
                confidence=confidence,
                price=price,
                target=price * (1 + confidence * 0.5) if signal_type == 'buy' else price * (1 - confidence * 0.5),
                stop_loss=price * (1 - confidence * 0.25) if signal_type == 'buy' else price * (1 + confidence * 0.25),
                reason=reason,
                indicators=ind_dict
            )
            signals.append(signal)
        
        return signals
    
    def _get_breadth_status(self, indicators: List[BreadthIndicator]) -> str:
        """
        Get overall breadth status.
        
        Args:
            indicators: List of breadth indicators
            
        Returns:
            Breadth status string
        """
        ind_dict = {i.name: i.value for i in indicators}
        
        bullish_count = 0
        bearish_count = 0
        
        # Check each indicator
        if ind_dict.get('advance_decline_ratio', 0) > 1:
            bullish_count += 1
        else:
            bearish_count += 1
        
        if ind_dict.get('new_highs_lows', 0) > 0.5:
            bullish_count += 1
        else:
            bearish_count += 1
        
        if ind_dict.get('pct_above_ma', 0) > 0.5:
            bullish_count += 1
        else:
            bearish_count += 1
        
        if ind_dict.get('breadth_thrust', 0) > 0.5:
            bullish_count += 1
        else:
            bearish_count += 1
        
        if ind_dict.get('bullish_percent', 50) > 50:
            bullish_count += 1
        else:
            bearish_count += 1
        
        if bullish_count > bearish_count:
            return 'bullish'
        elif bearish_count > bullish_count:
            return 'bearish'
        else:
            return 'neutral'
    
    def _get_market_character(self, indicators: List[BreadthIndicator]) -> str:
        """
        Get market character description.
        
        Args:
            indicators: List of breadth indicators
            
        Returns:
            Market character description
        """
        status = self._get_breadth_status(indicators)
        status_names = {
            'bullish': 'Bullish breadth',
            'bearish': 'Bearish breadth',
            'neutral': 'Neutral breadth'
        }
        
        ind_dict = {i.name: i.value for i in indicators}
        strength = ind_dict.get('breadth_thrust', 0)
        
        if strength > 0.7:
            return f"Strong {status_names.get(status, 'Neutral')}"
        elif strength > 0.4:
            return f"Moderate {status_names.get(status, 'Neutral')}"
        else:
            return f"Weak {status_names.get(status, 'Neutral')}"
    
    def get_breadth_stats(self) -> Dict[str, Any]:
        """
        Get breadth statistics.
        
        Returns:
            Breadth statistics
        """
        stats = {}
        
        for name, values in self.breadth_data.items():
            if values:
                stats[name] = {
                    'current': values[-1],
                    'mean': np.mean(values),
                    'std': np.std(values),
                    'min': np.min(values),
                    'max': np.max(values),
                    'history_length': len(values)
                }
        
        return stats


def create_breadth_model(config: Optional[Dict[str, Any]] = None) -> BreadthModel:
    """
    Create a breadth model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        BreadthModel instance
    """
    return BreadthModel(config)


__all__ = [
    'BreadthIndicator',
    'BreadthSignal',
    'BreadthModel',
    'create_breadth_model'
]
