"""
Swing Bot Perception Model
============================

This module provides perception and market awareness models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
import warnings
warnings.filterwarnings('ignore')


@dataclass
class MarketPerception:
    """Market perception data structure."""
    timestamp: datetime
    price_awareness: float
    volume_awareness: float
    volatility_awareness: float
    momentum_awareness: float
    trend_awareness: float
    sentiment_awareness: float
    liquidity_awareness: float
    risk_awareness: float
    overall_perception: float


@dataclass
class PerceptionSignal:
    """Perception trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    perception: MarketPerception
    indicators: Dict[str, Any] = field(default_factory=dict)


class PerceptionModel:
    """
    Market perception model for comprehensive market awareness.
    
    Integrates multiple market dimensions for holistic perception.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the perception model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.perception_history: List[MarketPerception] = []
        
    def analyze(self, df: pd.DataFrame) -> MarketPerception:
        """
        Analyze market perception.
        
        Args:
            df: OHLCV data
            
        Returns:
            MarketPerception object
        """
        if len(df) < self.lookback_period:
            return self._get_default_perception()
        
        # Calculate perception components
        price_awareness = self._calculate_price_awareness(df)
        volume_awareness = self._calculate_volume_awareness(df)
        volatility_awareness = self._calculate_volatility_awareness(df)
        momentum_awareness = self._calculate_momentum_awareness(df)
        trend_awareness = self._calculate_trend_awareness(df)
        sentiment_awareness = self._calculate_sentiment_awareness(df)
        liquidity_awareness = self._calculate_liquidity_awareness(df)
        risk_awareness = self._calculate_risk_awareness(df)
        
        # Calculate overall perception
        overall_perception = np.mean([
            price_awareness,
            volume_awareness,
            volatility_awareness,
            momentum_awareness,
            trend_awareness,
            sentiment_awareness,
            liquidity_awareness,
            risk_awareness
        ])
        
        perception = MarketPerception(
            timestamp=datetime.now(),
            price_awareness=price_awareness,
            volume_awareness=volume_awareness,
            volatility_awareness=volatility_awareness,
            momentum_awareness=momentum_awareness,
            trend_awareness=trend_awareness,
            sentiment_awareness=sentiment_awareness,
            liquidity_awareness=liquidity_awareness,
            risk_awareness=risk_awareness,
            overall_perception=overall_perception
        )
        
        self.perception_history.append(perception)
        
        return perception
    
    def _calculate_price_awareness(self, df: pd.DataFrame) -> float:
        """
        Calculate price awareness.
        
        Args:
            df: OHLCV data
            
        Returns:
            Price awareness score (0-1)
        """
        close = df['close'].values
        
        if len(close) < self.lookback_period:
            return 0.5
        
        # Price movement
        price_change = (close[-1] - close[-self.lookback_period]) / close[-self.lookback_period]
        price_score = min(abs(price_change) * 5, 1.0)
        
        # Price volatility
        price_std = np.std(close[-self.lookback_period:])
        volatility_score = min(price_std * 10, 1.0)
        
        # Combine
        awareness = (price_score + volatility_score) / 2
        
        return min(max(awareness, 0.0), 1.0)
    
    def _calculate_volume_awareness(self, df: pd.DataFrame) -> float:
        """
        Calculate volume awareness.
        
        Args:
            df: OHLCV data
            
        Returns:
            Volume awareness score (0-1)
        """
        volume = df['volume'].values
        
        if len(volume) < self.lookback_period:
            return 0.5
        
        # Volume trend
        recent_volume = np.mean(volume[-self.lookback_period//2:])
        past_volume = np.mean(volume[:self.lookback_period//2])
        volume_trend = (recent_volume - past_volume) / past_volume if past_volume > 0 else 0
        volume_score = min(abs(volume_trend) * 2, 1.0)
        
        # Volume consistency
        volume_std = np.std(volume[-self.lookback_period:])
        consistency_score = 1 - min(volume_std / np.mean(volume[-self.lookback_period:]) if np.mean(volume[-self.lookback_period:]) > 0 else 1, 1.0)
        
        # Combine
        awareness = (volume_score + consistency_score) / 2
        
        return min(max(awareness, 0.0), 1.0)
    
    def _calculate_volatility_awareness(self, df: pd.DataFrame) -> float:
        """
        Calculate volatility awareness.
        
        Args:
            df: OHLCV data
            
        Returns:
            Volatility awareness score (0-1)
        """
        close = df['close'].values
        
        if len(close) < self.lookback_period:
            return 0.5
        
        # Historical volatility
        returns = np.diff(np.log(close))
        vol = np.std(returns[-self.lookback_period:]) * np.sqrt(252)
        vol_score = min(vol * 5, 1.0)
        
        # Volatility clustering
        vol_cluster = self._calculate_volatility_clustering(returns)
        
        # Combine
        awareness = (vol_score + vol_cluster) / 2
        
        return min(max(awareness, 0.0), 1.0)
    
    def _calculate_volatility_clustering(self, returns: np.ndarray) -> float:
        """
        Calculate volatility clustering.
        
        Args:
            returns: Returns array
            
        Returns:
            Volatility clustering score (0-1)
        """
        if len(returns) < 20:
            return 0.5
        
        vol = np.abs(returns)
        correlation = np.corrcoef(vol[:-1], vol[1:])[0, 1]
        
        return min(max(correlation, 0.0), 1.0)
    
    def _calculate_momentum_awareness(self, df: pd.DataFrame) -> float:
        """
        Calculate momentum awareness.
        
        Args:
            df: OHLCV data
            
        Returns:
            Momentum awareness score (0-1)
        """
        close = df['close'].values
        
        if len(close) < self.lookback_period:
            return 0.5
        
        # Price momentum
        returns = np.diff(close) / close[:-1]
        momentum = np.mean(returns[-self.lookback_period:])
        momentum_score = min(abs(momentum) * 20, 1.0)
        
        # Momentum consistency
        momentum_std = np.std(returns[-self.lookback_period:])
        consistency_score = 1 - min(momentum_std * 5, 1.0)
        
        # Combine
        awareness = (momentum_score + consistency_score) / 2
        
        return min(max(awareness, 0.0), 1.0)
    
    def _calculate_trend_awareness(self, df: pd.DataFrame) -> float:
        """
        Calculate trend awareness.
        
        Args:
            df: OHLCV data
            
        Returns:
            Trend awareness score (0-1)
        """
        close = df['close'].values
        
        if len(close) < self.lookback_period:
            return 0.5
        
        # Linear regression for trend
        indices = np.arange(len(close[-self.lookback_period:]))
        slope, intercept = MathUtils.linear_regression(
            indices,
            close[-self.lookback_period:]
        )
        r2 = MathUtils.r_squared(indices, close[-self.lookback_period:])
        
        # Trend strength
        trend_strength = min(abs(slope) * 10, 1.0)
        
        # R2 for trend reliability
        r2_score = min(r2 * 2, 1.0)
        
        # Combine
        awareness = (trend_strength + r2_score) / 2
        
        return min(max(awareness, 0.0), 1.0)
    
    def _calculate_sentiment_awareness(self, df: pd.DataFrame) -> float:
        """
        Calculate sentiment awareness.
        
        Args:
            df: OHLCV data
            
        Returns:
            Sentiment awareness score (0-1)
        """
        close = df['close'].values
        volume = df['volume'].values
        
        if len(close) < self.lookback_period:
            return 0.5
        
        # Price-volume relationship
        price_change = (close[-1] - close[-self.lookback_period]) / close[-self.lookback_period]
        volume_change = (volume[-1] - np.mean(volume[-self.lookback_period:])) / np.mean(volume[-self.lookback_period:]) if np.mean(volume[-self.lookback_period:]) > 0 else 0
        
        # Sentiment indicator
        sentiment = 0.5
        
        if price_change > 0 and volume_change > 0:
            sentiment = 0.7  # Bullish sentiment
        elif price_change < 0 and volume_change > 0:
            sentiment = 0.3  # Bearish sentiment
        elif price_change > 0 and volume_change < 0:
            sentiment = 0.6  # Weak bullish
        elif price_change < 0 and volume_change < 0:
            sentiment = 0.4  # Weak bearish
        
        return sentiment
    
    def _calculate_liquidity_awareness(self, df: pd.DataFrame) -> float:
        """
        Calculate liquidity awareness.
        
        Args:
            df: OHLCV data
            
        Returns:
            Liquidity awareness score (0-1)
        """
        volume = df['volume'].values
        close = df['close'].values
        
        if len(volume) < self.lookback_period:
            return 0.5
        
        # Volume level
        volume_level = volume[-1] / np.mean(volume[-self.lookback_period:]) if np.mean(volume[-self.lookback_period:]) > 0 else 1
        volume_score = min(volume_level, 2.0) / 2
        
        # Spread (using price range as proxy)
        price_range = (df['high'].iloc[-1] - df['low'].iloc[-1]) / close[-1]
        spread_score = 1 - min(price_range * 10, 1.0)
        
        # Combine
        awareness = (volume_score + spread_score) / 2
        
        return min(max(awareness, 0.0), 1.0)
    
    def _calculate_risk_awareness(self, df: pd.DataFrame) -> float:
        """
        Calculate risk awareness.
        
        Args:
            df: OHLCV data
            
        Returns:
            Risk awareness score (0-1)
        """
        close = df['close'].values
        
        if len(close) < self.lookback_period:
            return 0.5
        
        # Volatility risk
        returns = np.diff(np.log(close))
        vol = np.std(returns[-self.lookback_period:]) * np.sqrt(252)
        vol_risk = min(vol * 5, 1.0)
        
        # Drawdown risk
        drawdown = MathUtils.max_drawdown(close)[0]
        drawdown_risk = min(drawdown * 5, 1.0)
        
        # Combine
        risk = (vol_risk + drawdown_risk) / 2
        
        return min(max(risk, 0.0), 1.0)
    
    def _get_default_perception(self) -> MarketPerception:
        """
        Get default perception values.
        
        Returns:
            Default MarketPerception object
        """
        return MarketPerception(
            timestamp=datetime.now(),
            price_awareness=0.5,
            volume_awareness=0.5,
            volatility_awareness=0.5,
            momentum_awareness=0.5,
            trend_awareness=0.5,
            sentiment_awareness=0.5,
            liquidity_awareness=0.5,
            risk_awareness=0.5,
            overall_perception=0.5
        )
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[PerceptionSignal]:
        """
        Generate trading signal based on perception.
        
        Args:
            df: OHLCV data
            
        Returns:
            PerceptionSignal or None
        """
        perception = self.analyze(df)
        
        if perception.overall_perception < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Determine signal based on perception components
        bullish_score = (
            perception.price_awareness * 0.2 +
            perception.volume_awareness * 0.15 +
            perception.momentum_awareness * 0.2 +
            perception.trend_awareness * 0.2 +
            perception.sentiment_awareness * 0.15 +
            (1 - perception.risk_awareness) * 0.1
        )
        
        if bullish_score > 0.6:
            signal_type = 'buy'
            reason = "Bullish market perception detected"
            target = current_price * (1 + 0.02)
            stop_loss = current_price * (1 - 0.01)
        elif bullish_score < 0.4:
            signal_type = 'sell'
            reason = "Bearish market perception detected"
            target = current_price * (1 - 0.02)
            stop_loss = current_price * (1 + 0.01)
        else:
            return None
        
        return PerceptionSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=perception.overall_perception,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            perception=perception,
            indicators={
                'bullish_score': bullish_score,
                'perception_components': {
                    'price': perception.price_awareness,
                    'volume': perception.volume_awareness,
                    'volatility': perception.volatility_awareness,
                    'momentum': perception.momentum_awareness,
                    'trend': perception.trend_awareness,
                    'sentiment': perception.sentiment_awareness,
                    'liquidity': perception.liquidity_awareness,
                    'risk': perception.risk_awareness
                }
            }
        )
    
    def get_perception_stats(self) -> Dict[str, Any]:
        """
        Get perception statistics.
        
        Returns:
            Perception statistics
        """
        if not self.perception_history:
            return {'history_length': 0}
        
        stats = {
            'history_length': len(self.perception_history),
            'latest_perception': self.perception_history[-1],
            'avg_perception': {
                'price': np.mean([p.price_awareness for p in self.perception_history]),
                'volume': np.mean([p.volume_awareness for p in self.perception_history]),
                'volatility': np.mean([p.volatility_awareness for p in self.perception_history]),
                'momentum': np.mean([p.momentum_awareness for p in self.perception_history]),
                'trend': np.mean([p.trend_awareness for p in self.perception_history]),
                'sentiment': np.mean([p.sentiment_awareness for p in self.perception_history]),
                'liquidity': np.mean([p.liquidity_awareness for p in self.perception_history]),
                'risk': np.mean([p.risk_awareness for p in self.perception_history]),
                'overall': np.mean([p.overall_perception for p in self.perception_history])
            },
            'trend': self._calculate_perception_trend()
        }
        
        return stats
    
    def _calculate_perception_trend(self) -> str:
        """
        Calculate perception trend.
        
        Returns:
            Trend string
        """
        if len(self.perception_history) < 5:
            return 'stable'
        
        recent = np.mean([p.overall_perception for p in self.perception_history[-5:]])
        past = np.mean([p.overall_perception for p in self.perception_history[-10:-5]])
        
        if recent > past * 1.1:
            return 'improving'
        elif recent < past * 0.9:
            return 'declining'
        else:
            return 'stable'


def create_perception_model(config: Optional[Dict[str, Any]] = None) -> PerceptionModel:
    """
    Create a perception model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        PerceptionModel instance
    """
    return PerceptionModel(config)


__all__ = [
    'MarketPerception',
    'PerceptionSignal',
    'PerceptionModel',
    'create_perception_model'
]
