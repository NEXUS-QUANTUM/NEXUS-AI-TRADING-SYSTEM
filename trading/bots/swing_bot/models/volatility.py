"""
Swing Bot Volatility Model
============================

This module provides volatility analysis models for the Swing Bot trading system.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from scipy import stats
from trading.bots.swing_bot.utils.math_utils import MathUtils
import talib


@dataclass
class VolatilityIndicator:
    """Volatility indicator data structure."""
    name: str
    value: float
    timestamp: datetime
    signal_type: Optional[str] = None
    confidence: float = 0.0


@dataclass
class VolatilityRegime:
    """Volatility regime data structure."""
    regime: str  # 'low', 'normal', 'high', 'extreme'
    start_date: datetime
    end_date: datetime
    volatility_level: float
    trend: str  # 'increasing', 'decreasing', 'stable'
    confidence: float


@dataclass
class VolatilitySignal:
    """Volatility trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    regime: str
    confidence: float
    price: float
    volatility: float
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class VolatilityModel:
    """
    Volatility analysis model for market risk assessment.
    
    Analyzes volatility patterns, regimes, and provides trading signals.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the volatility model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 20)
        self.volatility_window = self.config.get('volatility_window', 10)
        self.regime_threshold_low = self.config.get('regime_threshold_low', 0.10)
        self.regime_threshold_high = self.config.get('regime_threshold_high', 0.30)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze volatility patterns and regimes.
        
        Args:
            df: OHLCV data
            
        Returns:
            Volatility analysis results
        """
        if len(df) < self.lookback_period:
            return {'indicators': [], 'regimes': [], 'signals': []}
        
        # Calculate volatility indicators
        indicators = self._calculate_indicators(df)
        
        # Detect volatility regimes
        regimes = self._detect_regimes(df)
        
        # Generate signals
        signals = self._generate_signals(df, regimes)
        
        return {
            'indicators': indicators,
            'regimes': regimes,
            'signals': signals,
            'current_volatility': indicators[-1].value if indicators else 0,
            'current_regime': regimes[-1].regime if regimes else 'unknown',
            'volatility_trend': regimes[-1].trend if regimes else 'stable',
            'market_character': self._get_market_character(df, regimes)
        }
    
    def _calculate_indicators(self, df: pd.DataFrame) -> List[VolatilityIndicator]:
        """
        Calculate volatility indicators.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of VolatilityIndicator objects
        """
        indicators = []
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # Historical volatility
        returns = np.diff(np.log(close))
        hist_vol = np.std(returns) * np.sqrt(252)
        indicators.append(VolatilityIndicator(
            name='historical_volatility',
            value=hist_vol,
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        
        # ATR (Average True Range)
        atr = talib.ATR(high, low, close, timeperiod=self.volatility_window)
        indicators.append(VolatilityIndicator(
            name='atr',
            value=atr[-1],
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        
        # Bollinger Bands width
        upper, middle, lower = talib.BBANDS(close, timeperiod=self.volatility_window, nbdevup=2, nbdevdn=2)
        bb_width = (upper[-1] - lower[-1]) / middle[-1]
        indicators.append(VolatilityIndicator(
            name='bollinger_width',
            value=bb_width,
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        
        # Volatility ratio
        vol_ratio = self._calculate_volatility_ratio(returns)
        indicators.append(VolatilityIndicator(
            name='volatility_ratio',
            value=vol_ratio,
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        
        # Volatility skew
        vol_skew = self._calculate_volatility_skew(returns)
        indicators.append(VolatilityIndicator(
            name='volatility_skew',
            value=vol_skew,
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        
        # Volatility clustering
        vol_cluster = self._calculate_volatility_clustering(returns)
        indicators.append(VolatilityIndicator(
            name='volatility_clustering',
            value=vol_cluster,
            timestamp=df.index[-1] if isinstance(df.index, pd.DatetimeIndex) else datetime.now()
        ))
        
        return indicators
    
    def _calculate_volatility_ratio(self, returns: np.ndarray) -> float:
        """
        Calculate volatility ratio (recent vs historical).
        
        Args:
            returns: Returns array
            
        Returns:
            Volatility ratio
        """
        if len(returns) < self.volatility_window * 2:
            return 0.0
        
        recent_vol = np.std(returns[-self.volatility_window:])
        hist_vol = np.std(returns[:-self.volatility_window])
        
        if hist_vol == 0:
            return 0.0
        
        return recent_vol / hist_vol
    
    def _calculate_volatility_skew(self, returns: np.ndarray) -> float:
        """
        Calculate volatility skew (up vs down volatility).
        
        Args:
            returns: Returns array
            
        Returns:
            Volatility skew
        """
        if len(returns) < self.volatility_window:
            return 0.0
        
        up_returns = returns[returns > 0]
        down_returns = returns[returns < 0]
        
        if len(up_returns) < 2 or len(down_returns) < 2:
            return 0.0
        
        up_vol = np.std(up_returns)
        down_vol = np.std(down_returns)
        
        if down_vol == 0:
            return 0.0
        
        return up_vol / down_vol
    
    def _calculate_volatility_clustering(self, returns: np.ndarray) -> float:
        """
        Calculate volatility clustering (autocorrelation).
        
        Args:
            returns: Returns array
            
        Returns:
            Volatility clustering
        """
        if len(returns) < 20:
            return 0.0
        
        vol = np.abs(returns)
        return np.corrcoef(vol[:-1], vol[1:])[0, 1]
    
    def _detect_regimes(self, df: pd.DataFrame) -> List[VolatilityRegime]:
        """
        Detect volatility regimes.
        
        Args:
            df: OHLCV data
            
        Returns:
            List of VolatilityRegime objects
        """
        regimes = []
        
        # Calculate rolling volatility
        returns = np.diff(np.log(df['close'].values))
        rolling_vol = pd.Series(returns).rolling(self.volatility_window).std() * np.sqrt(252)
        
        # Determine regimes
        for i in range(self.volatility_window, len(rolling_vol)):
            if np.isnan(rolling_vol.iloc[i]):
                continue
            
            vol = rolling_vol.iloc[i]
            prev_vol = rolling_vol.iloc[i-1] if i > 0 else vol
            
            # Determine regime
            if vol > self.regime_threshold_high:
                regime = 'extreme'
            elif vol > self.regime_threshold_low:
                regime = 'high'
            elif vol > 0.05:
                regime = 'normal'
            else:
                regime = 'low'
            
            # Determine trend
            if vol > prev_vol * 1.1:
                trend = 'increasing'
            elif vol < prev_vol * 0.9:
                trend = 'decreasing'
            else:
                trend = 'stable'
            
            # Calculate confidence
            confidence = min(vol / 0.50, 1.0)
            
            regimes.append(VolatilityRegime(
                regime=regime,
                start_date=df.index[i-self.volatility_window] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                end_date=df.index[i] if isinstance(df.index, pd.DatetimeIndex) else datetime.now(),
                volatility_level=vol,
                trend=trend,
                confidence=confidence
            ))
        
        return regimes
    
    def _generate_signals(self, df: pd.DataFrame, regimes: List[VolatilityRegime]) -> List[VolatilitySignal]:
        """
        Generate trading signals from volatility regimes.
        
        Args:
            df: OHLCV data
            regimes: List of VolatilityRegime objects
            
        Returns:
            List of VolatilitySignal objects
        """
        signals = []
        
        if not regimes:
            return signals
        
        latest_regime = regimes[-1]
        
        if latest_regime.confidence < self.confidence_threshold:
            return signals
        
        # Generate signals based on regime
        if latest_regime.regime == 'low':
            if latest_regime.trend == 'increasing':
                signal_type = 'buy'
                reason = "Volatility increasing from low regime - potential breakout"
            else:
                signal_type = 'buy'
                reason = "Low volatility regime - potential consolidation"
                
        elif latest_regime.regime == 'high' or latest_regime.regime == 'extreme':
            if latest_regime.trend == 'decreasing':
                signal_type = 'sell'
                reason = "Volatility decreasing from high regime - potential reversal"
            else:
                signal_type = 'sell'
                reason = "High volatility regime - increased risk"
                
        elif latest_regime.regime == 'normal':
            if latest_regime.trend == 'increasing':
                signal_type = 'buy'
                reason = "Normal volatility with increasing trend"
            elif latest_regime.trend == 'decreasing':
                signal_type = 'sell'
                reason = "Normal volatility with decreasing trend"
            else:
                return signals
                
        else:
            return signals
        
        signal = VolatilitySignal(
            symbol=df.get('symbol', [''])[0] if 'symbol' in df.columns else '',
            timestamp=datetime.now(),
            signal_type=signal_type,
            regime=latest_regime.regime,
            confidence=latest_regime.confidence,
            price=df['close'].iloc[-1],
            volatility=latest_regime.volatility_level,
            reason=reason,
            indicators={
                'volatility_trend': latest_regime.trend,
                'volatility_level': latest_regime.volatility_level
            }
        )
        signals.append(signal)
        
        return signals
    
    def _get_market_character(self, df: pd.DataFrame, regimes: List[VolatilityRegime]) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            regimes: List of VolatilityRegime objects
            
        Returns:
            Market character description
        """
        if not regimes:
            return "Volatility: Unknown"
        
        latest = regimes[-1]
        
        regime_names = {
            'low': 'Low volatility',
            'normal': 'Normal volatility',
            'high': 'High volatility',
            'extreme': 'Extreme volatility'
        }
        
        return f"{regime_names.get(latest.regime, 'Unknown')} ({latest.trend})"
    
    def get_volatility_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Get volatility statistics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Volatility statistics
        """
        close = df['close'].values
        returns = np.diff(np.log(close))
        
        stats = {
            'historical_volatility': np.std(returns) * np.sqrt(252),
            'recent_volatility': np.std(returns[-self.volatility_window:]) * np.sqrt(252),
            'volatility_ratio': np.std(returns[-self.volatility_window:]) / np.std(returns[:-self.volatility_window]) if len(returns) > self.volatility_window else 0,
            'volatility_skew': self._calculate_volatility_skew(returns),
            'volatility_clustering': self._calculate_volatility_clustering(returns),
            'volatility_percentile': np.percentile(np.abs(returns), [25, 50, 75]).tolist(),
            'max_drawdown': MathUtils.max_drawdown(close)[0],
            'sharpe_ratio': MathUtils.sharpe_ratio(returns)
        }
        
        return stats


def create_volatility_model(config: Optional[Dict[str, Any]] = None) -> VolatilityModel:
    """
    Create a volatility model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        VolatilityModel instance
    """
    return VolatilityModel(config)


__all__ = [
    'VolatilityIndicator',
    'VolatilityRegime',
    'VolatilitySignal',
    'VolatilityModel',
    'create_volatility_model'
]
