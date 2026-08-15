"""
Swing Bot Recommendation Model
================================

This module provides recommendation models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class Recommendation:
    """Recommendation data structure."""
    recommendation_id: str
    type: str  # 'buy', 'sell', 'hold', 'short', 'cover'
    symbol: str
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    timestamp: datetime
    priority: int  # 1-10, 10 being highest
    status: str = 'active'  # 'active', 'executed', 'expired', 'cancelled'


@dataclass
class RecommendationSignal:
    """Recommendation trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    recommendation: Recommendation
    indicators: Dict[str, Any] = field(default_factory=dict)


class RecommendationModel:
    """
    Recommendation model for trading suggestions.
    
    Implements scoring and ranking of trading recommendations.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the recommendation model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.recommendations: List[Recommendation] = []
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.max_recommendations = self.config.get('max_recommendations', 10)
        
    def generate_recommendation(self, df: pd.DataFrame) -> Optional[Recommendation]:
        """
        Generate a trading recommendation.
        
        Args:
            df: OHLCV data
            
        Returns:
            Recommendation or None
        """
        if len(df) < 50:
            return None
        
        # Analyze market conditions
        analysis = self._analyze_market(df)
        
        if analysis['confidence'] < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        recommendation = Recommendation(
            recommendation_id=f"rec_{int(datetime.now().timestamp())}",
            type=analysis['type'],
            symbol=symbol,
            confidence=analysis['confidence'],
            price=current_price,
            target=analysis['target'],
            stop_loss=analysis['stop_loss'],
            reason=analysis['reason'],
            timestamp=datetime.now(),
            priority=analysis['priority']
        )
        
        self.recommendations.append(recommendation)
        
        return recommendation
    
    def _analyze_market(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze market conditions for recommendation.
        
        Args:
            df: OHLCV data
            
        Returns:
            Analysis dictionary
        """
        close = df['close'].values
        
        # Calculate indicators
        ma20 = np.mean(close[-20:])
        ma50 = np.mean(close[-50:]) if len(close) >= 50 else ma20
        
        # Trend analysis
        trend = 'neutral'
        if ma20 > ma50:
            trend = 'bullish'
        elif ma20 < ma50:
            trend = 'bearish'
        
        # Momentum analysis
        momentum = (close[-1] - close[-5]) / close[-5] if len(close) >= 5 else 0
        
        # Volatility analysis
        volatility = np.std(close[-20:]) / np.mean(close[-20:])
        
        # Determine recommendation
        confidence = 0.5
        type = 'hold'
        reason = "No clear signal"
        priority = 5
        
        if trend == 'bullish' and momentum > 0.02:
            type = 'buy'
            confidence = 0.7 + min(momentum * 2, 0.2)
            reason = "Bullish trend with positive momentum"
            priority = 8
            target = close[-1] * 1.05
            stop_loss = close[-1] * 0.97
        elif trend == 'bearish' and momentum < -0.02:
            type = 'sell'
            confidence = 0.7 + min(abs(momentum) * 2, 0.2)
            reason = "Bearish trend with negative momentum"
            priority = 8
            target = close[-1] * 0.95
            stop_loss = close[-1] * 1.03
        elif volatility > 0.05:
            type = 'hold'
            confidence = 0.6
            reason = "High volatility, wait for clearer signal"
            priority = 3
            target = close[-1]
            stop_loss = close[-1]
        
        return {
            'type': type,
            'confidence': confidence,
            'target': target,
            'stop_loss': stop_loss,
            'reason': reason,
            'priority': priority
        }
    
    def rank_recommendations(self) -> List[Recommendation]:
        """
        Rank recommendations by confidence and priority.
        
        Returns:
            Ranked list of recommendations
        """
        active_recs = [r for r in self.recommendations if r.status == 'active']
        
        # Sort by confidence (descending) and priority (descending)
        ranked = sorted(active_recs, key=lambda x: (x.confidence, x.priority), reverse=True)
        
        return ranked[:self.max_recommendations]
    
    def execute_recommendation(self, recommendation_id: str) -> bool:
        """
        Mark a recommendation as executed.
        
        Args:
            recommendation_id: Recommendation ID
            
        Returns:
            True if executed, False otherwise
        """
        for rec in self.recommendations:
            if rec.recommendation_id == recommendation_id:
                rec.status = 'executed'
                return True
        return False
    
    def cancel_recommendation(self, recommendation_id: str) -> bool:
        """
        Cancel a recommendation.
        
        Args:
            recommendation_id: Recommendation ID
            
        Returns:
            True if cancelled, False otherwise
        """
        for rec in self.recommendations:
            if rec.recommendation_id == recommendation_id:
                rec.status = 'cancelled'
                return True
        return False
    
    def expire_recommendations(self) -> None:
        """Expire old recommendations."""
        now = datetime.now()
        for rec in self.recommendations:
            if rec.status == 'active':
                # Expire after 24 hours
                if (now - rec.timestamp).total_seconds() > 86400:
                    rec.status = 'expired'
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[RecommendationSignal]:
        """
        Generate trading signal from recommendation.
        
        Args:
            df: OHLCV data
            
        Returns:
            RecommendationSignal or None
        """
        recommendation = self.generate_recommendation(df)
        
        if not recommendation:
            return None
        
        if recommendation.confidence < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        return RecommendationSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=recommendation.type,
            confidence=recommendation.confidence,
            price=current_price,
            target=recommendation.target,
            stop_loss=recommendation.stop_loss,
            reason=recommendation.reason,
            recommendation=recommendation,
            indicators={
                'priority': recommendation.priority,
                'recommendation_id': recommendation.recommendation_id
            }
        )
    
    def get_recommendation_summary(self) -> Dict[str, Any]:
        """
        Get recommendation summary.
        
        Returns:
            Recommendation summary
        """
        active_recs = [r for r in self.recommendations if r.status == 'active']
        executed_recs = [r for r in self.recommendations if r.status == 'executed']
        expired_recs = [r for r in self.recommendations if r.status == 'expired']
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_recommendations': len(self.recommendations),
            'active_recommendations': len(active_recs),
            'executed_recommendations': len(executed_recs),
            'expired_recommendations': len(expired_recs),
            'top_recommendations': self.rank_recommendations()[:5],
            'recommendation_types': {
                'buy': len([r for r in self.recommendations if r.type == 'buy']),
                'sell': len([r for r in self.recommendations if r.type == 'sell']),
                'hold': len([r for r in self.recommendations if r.type == 'hold']),
                'short': len([r for r in self.recommendations if r.type == 'short']),
                'cover': len([r for r in self.recommendations if r.type == 'cover'])
            }
        }


def create_recommendation_model(config: Optional[Dict[str, Any]] = None) -> RecommendationModel:
    """
    Create a recommendation model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        RecommendationModel instance
    """
    return RecommendationModel(config)


__all__ = [
    'Recommendation',
    'RecommendationSignal',
    'RecommendationModel',
    'create_recommendation_model'
]
