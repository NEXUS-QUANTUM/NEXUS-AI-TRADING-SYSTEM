"""
Swing Bot Accumulation Model
==============================

This module provides accumulation analysis models for the Swing Bot trading system.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import talib
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class AccumulationSignal:
    """Accumulation signal data structure."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'accumulation', 'distribution', 'neutral'
    confidence: float
    price: float
    volume: float
    indicators: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass
class AccumulationMetrics:
    """Accumulation metrics."""
    accumulation_score: float
    distribution_score: float
    net_accumulation: float
    volume_velocity: float
    money_flow: float
    smart_money_score: float


class AccumulationModel:
    """
    Accumulation and distribution analysis model.
    
    This model identifies smart money accumulation and distribution patterns
    using various volume and price indicators.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the accumulation model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.min_volume = self.config.get('min_volume', 100000)
        self.lookback_period = self.config.get('lookback_period', 50)
        self.accumulation_threshold = self.config.get('accumulation_threshold', 0.60)
        self.distribution_threshold = self.config.get('distribution_threshold', -0.60)
        
    def analyze(self, df: pd.DataFrame) -> List[AccumulationSignal]:
        """
        Analyze accumulation/distribution patterns.
        
        Args:
            df: OHLCV data with columns ['open', 'high', 'low', 'close', 'volume']
            
        Returns:
            List of accumulation signals
        """
        if len(df) < self.lookback_period:
            return []
        
        signals = []
        
        # Calculate indicators
        indicators = self._calculate_indicators(df)
        
        # Calculate accumulation scores
        scores = self._calculate_scores(df, indicators)
        
        # Generate signals
        for i in range(self.lookback_period, len(df)):
            if i >= len(scores):
                break
                
            score = scores[i]
            if score > self.accumulation_threshold:
                signal_type = 'accumulation'
                reason = f"Accumulation score {score:.2f}"
            elif score < self.distribution_threshold:
                signal_type = 'distribution'
                reason = f"Distribution score {score:.2f}"
            else:
                signal_type = 'neutral'
                reason = "No significant accumulation or distribution"
            
            if signal_type != 'neutral':
                signal = AccumulationSignal(
                    symbol=df.get('symbol', [''])[0] if 'symbol' in df.columns else '',
                    timestamp=df.index[i] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                    signal_type=signal_type,
                    confidence=abs(score),
                    price=df['close'].iloc[i],
                    volume=df['volume'].iloc[i],
                    indicators=indicators[i] if i < len(indicators) else {},
                    reason=reason
                )
                signals.append(signal)
        
        return signals
    
    def _calculate_indicators(self, df: pd.DataFrame) -> List[Dict[str, float]]:
        """Calculate accumulation indicators."""
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values
        
        indicators = []
        
        for i in range(len(df)):
            idx = i + 1 if i < len(df) else i
            current_close = close[i] if i < len(close) else close[-1]
            current_high = high[i] if i < len(high) else high[-1]
            current_low = low[i] if i < len(low) else low[-1]
            current_volume = volume[i] if i < len(volume) else volume[-1]
            
            ind = {
                'accumulation_distribution_line': self._calc_ad_line(close[:idx], volume[:idx]),
                'chaikin_money_flow': self._calc_chaikin_mf(high[:idx], low[:idx], close[:idx], volume[:idx]),
                'money_flow_index': self._calc_mfi(high[:idx], low[:idx], close[:idx], volume[:idx]),
                'on_balance_volume': self._calc_obv(close[:idx], volume[:idx]),
                'volume_velocity': self._calc_volume_velocity(volume[:idx]),
                'price_volume_trend': self._calc_pvt(close[:idx], volume[:idx])
            }
            indicators.append(ind)
        
        return indicators
    
    def _calculate_scores(self, df: pd.DataFrame, indicators: List[Dict[str, float]]) -> List[float]:
        """Calculate accumulation scores."""
        scores = []
        
        for i in range(len(indicators)):
            ind = indicators[i]
            
            # Normalize indicators
            ad_score = self._normalize_score(ind.get('accumulation_distribution_line', 0))
            cmf_score = self._normalize_score(ind.get('chaikin_money_flow', 0))
            mfi_score = self._normalize_score(ind.get('money_flow_index', 50) - 50) / 50
            obv_score = self._normalize_score(ind.get('on_balance_volume', 0))
            vol_vel_score = self._normalize_score(ind.get('volume_velocity', 0))
            pvt_score = self._normalize_score(ind.get('price_volume_trend', 0))
            
            # Weighted combination
            score = (
                ad_score * 0.20 +
                cmf_score * 0.20 +
                mfi_score * 0.20 +
                obv_score * 0.15 +
                vol_vel_score * 0.15 +
                pvt_score * 0.10
            )
            
            scores.append(score)
        
        return scores
    
    def _calc_ad_line(self, close: np.ndarray, volume: np.ndarray) -> float:
        """Calculate Accumulation/Distribution Line."""
        if len(close) < 2:
            return 0.0
        try:
            return talib.AD(high=close, low=close, close=close, volume=volume)[-1]
        except:
            return 0.0
    
    def _calc_chaikin_mf(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray) -> float:
        """Calculate Chaikin Money Flow."""
        if len(close) < 21:
            return 0.0
        try:
            return talib.ADOSC(high=high, low=low, close=close, volume=volume, fastperiod=3, slowperiod=10)[-1]
        except:
            return 0.0
    
    def _calc_mfi(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray) -> float:
        """Calculate Money Flow Index."""
        if len(close) < 14:
            return 50.0
        try:
            return talib.MFI(high=high, low=low, close=close, volume=volume, timeperiod=14)[-1]
        except:
            return 50.0
    
    def _calc_obv(self, close: np.ndarray, volume: np.ndarray) -> float:
        """Calculate On-Balance Volume."""
        if len(close) < 2:
            return 0.0
        try:
            return talib.OBV(close=close, volume=volume)[-1]
        except:
            return 0.0
    
    def _calc_volume_velocity(self, volume: np.ndarray) -> float:
        """Calculate volume velocity (rate of change)."""
        if len(volume) < 10:
            return 0.0
        recent_avg = np.mean(volume[-5:])
        past_avg = np.mean(volume[-10:-5])
        if past_avg == 0:
            return 0.0
        return (recent_avg - past_avg) / past_avg
    
    def _calc_pvt(self, close: np.ndarray, volume: np.ndarray) -> float:
        """Calculate Price Volume Trend."""
        if len(close) < 2:
            return 0.0
        pvt = 0.0
        for i in range(1, len(close)):
            if close[i-1] != 0:
                pvt += volume[i] * (close[i] - close[i-1]) / close[i-1]
        return pvt
    
    def _normalize_score(self, value: float) -> float:
        """Normalize score to [-1, 1] range."""
        return np.clip(value, -1, 1)


class SmartMoneyModel(AccumulationModel):
    """
    Smart money flow analysis model.
    
    Extends accumulation model with additional smart money indicators.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.smart_money_threshold = self.config.get('smart_money_threshold', 0.70)
    
    def analyze_smart_money(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze smart money flow patterns.
        
        Args:
            df: OHLCV data
            
        Returns:
            Smart money analysis results
        """
        if len(df) < self.lookback_period:
            return {'smart_money_score': 0, 'pattern': 'insufficient_data'}
        
        # Calculate base accumulation scores
        signals = self.analyze(df)
        
        # Calculate additional smart money indicators
        smart_money_flow = self._calc_smart_money_flow(df)
        institutional_flow = self._calc_institutional_flow(df)
        whale_activity = self._calc_whale_activity(df)
        
        # Calculate overall smart money score
        score = (
            smart_money_flow * 0.35 +
            institutional_flow * 0.35 +
            whale_activity * 0.30
        )
        
        # Determine pattern
        if score > self.smart_money_threshold:
            pattern = 'strong_accumulation'
        elif score > 0.30:
            pattern = 'weak_accumulation'
        elif score < -self.smart_money_threshold:
            pattern = 'strong_distribution'
        elif score < -0.30:
            pattern = 'weak_distribution'
        else:
            pattern = 'neutral'
        
        return {
            'smart_money_score': score,
            'pattern': pattern,
            'smart_money_flow': smart_money_flow,
            'institutional_flow': institutional_flow,
            'whale_activity': whale_activity,
            'signals': signals
        }
    
    def _calc_smart_money_flow(self, df: pd.DataFrame) -> float:
        """Calculate smart money flow indicator."""
        # Placeholder - implement actual smart money flow calculation
        signals = self.analyze(df)
        if not signals:
            return 0.0
        return np.mean([s.confidence for s in signals if s.signal_type == 'accumulation']) or 0.0
    
    def _calc_institutional_flow(self, df: pd.DataFrame) -> float:
        """Calculate institutional flow indicator."""
        # Placeholder - implement actual institutional flow calculation
        return 0.0
    
    def _calc_whale_activity(self, df: pd.DataFrame) -> float:
        """Calculate whale activity indicator."""
        # Placeholder - implement actual whale activity calculation
        return 0.0


def create_accumulation_model(config: Optional[Dict[str, Any]] = None) -> AccumulationModel:
    """
    Create an accumulation model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        AccumulationModel instance
    """
    return AccumulationModel(config)


def create_smart_money_model(config: Optional[Dict[str, Any]] = None) -> SmartMoneyModel:
    """
    Create a smart money model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        SmartMoneyModel instance
    """
    return SmartMoneyModel(config)


__all__ = [
    'AccumulationSignal',
    'AccumulationMetrics',
    'AccumulationModel',
    'SmartMoneyModel',
    'create_accumulation_model',
    'create_smart_money_model'
]
