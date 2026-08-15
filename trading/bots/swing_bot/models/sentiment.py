"""
Swing Bot Sentiment Model
===========================

This module provides sentiment analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
import requests
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class SentimentMetrics:
    """Sentiment metrics data structure."""
    timestamp: datetime
    overall_sentiment: float  # -1 to 1
    bullish_score: float
    bearish_score: float
    neutral_score: float
    fear_greed_index: float
    put_call_ratio: float
    vix_index: float
    social_sentiment: float
    news_sentiment: float
    institutional_sentiment: float


@dataclass
class SentimentSignal:
    """Sentiment trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    sentiment: SentimentMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class SentimentModel:
    """
    Sentiment analysis model for market psychology.
    
    Implements sentiment analysis from various sources.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the sentiment model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.news_api_key = self.config.get('news_api_key', '')
        self.social_api_key = self.config.get('social_api_key', '')
        
        self.metrics_history: List[SentimentMetrics] = []
        
    def analyze(self, df: pd.DataFrame, external_data: Optional[Dict[str, Any]] = None) -> SentimentMetrics:
        """
        Analyze sentiment from various sources.
        
        Args:
            df: OHLCV data
            external_data: External sentiment data
            
        Returns:
            SentimentMetrics object
        """
        # Calculate market sentiment from price/volume
        market_sentiment = self._calculate_market_sentiment(df)
        
        # Get news sentiment
        news_sentiment = self._get_news_sentiment(external_data) if external_data else 0.0
        
        # Get social sentiment
        social_sentiment = self._get_social_sentiment(external_data) if external_data else 0.0
        
        # Get institutional sentiment
        institutional_sentiment = self._get_institutional_sentiment(external_data) if external_data else 0.0
        
        # Combine all sentiments
        overall_sentiment = self._combine_sentiments(
            market_sentiment,
            news_sentiment,
            social_sentiment,
            institutional_sentiment
        )
        
        # Calculate additional metrics
        fear_greed_index = self._calculate_fear_greed(df)
        put_call_ratio = self._calculate_put_call_ratio(df)
        vix_index = self._calculate_vix(df)
        
        metrics = SentimentMetrics(
            timestamp=datetime.now(),
            overall_sentiment=overall_sentiment,
            bullish_score=max(overall_sentiment, 0),
            bearish_score=abs(min(overall_sentiment, 0)),
            neutral_score=1 - abs(overall_sentiment),
            fear_greed_index=fear_greed_index,
            put_call_ratio=put_call_ratio,
            vix_index=vix_index,
            social_sentiment=social_sentiment,
            news_sentiment=news_sentiment,
            institutional_sentiment=institutional_sentiment
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _calculate_market_sentiment(self, df: pd.DataFrame) -> float:
        """
        Calculate sentiment from market data.
        
        Args:
            df: OHLCV data
            
        Returns:
            Market sentiment (-1 to 1)
        """
        if len(df) < self.lookback_period:
            return 0.0
        
        close = df['close'].values
        volume = df['volume'].values
        high = df['high'].values
        low = df['low'].values
        
        # Price momentum
        price_change = (close[-1] - close[-self.lookback_period]) / close[-self.lookback_period]
        momentum_score = min(price_change * 10, 1.0)
        
        # Volume trend
        volume_ma = np.mean(volume[-self.lookback_period:])
        volume_trend = (volume[-1] - volume_ma) / volume_ma if volume_ma > 0 else 0
        volume_score = min(volume_trend * 2, 1.0)
        
        # Volatility
        returns = np.diff(np.log(close))
        volatility = np.std(returns[-self.lookback_period:]) * np.sqrt(252)
        volatility_score = 1 - min(volatility, 0.5) * 2
        
        # Price position (within range)
        price_range = high[-1] - low[-1]
        if price_range > 0:
            position = (close[-1] - low[-1]) / price_range
        else:
            position = 0.5
        position_score = (position - 0.5) * 2
        
        # Combine scores
        sentiment = (momentum_score * 0.3 + volume_score * 0.2 + 
                    volatility_score * 0.2 + position_score * 0.3)
        
        return max(-1, min(1, sentiment))
    
    def _get_news_sentiment(self, external_data: Dict[str, Any]) -> float:
        """
        Get sentiment from news data.
        
        Args:
            external_data: External data
            
        Returns:
            News sentiment (-1 to 1)
        """
        # This would use actual news API in production
        # Placeholder implementation
        if 'news_sentiment' in external_data:
            return external_data['news_sentiment']
        return 0.0
    
    def _get_social_sentiment(self, external_data: Dict[str, Any]) -> float:
        """
        Get sentiment from social media.
        
        Args:
            external_data: External data
            
        Returns:
            Social sentiment (-1 to 1)
        """
        # This would use actual social media API in production
        # Placeholder implementation
        if 'social_sentiment' in external_data:
            return external_data['social_sentiment']
        return 0.0
    
    def _get_institutional_sentiment(self, external_data: Dict[str, Any]) -> float:
        """
        Get institutional sentiment.
        
        Args:
            external_data: External data
            
        Returns:
            Institutional sentiment (-1 to 1)
        """
        # This would use actual institutional data in production
        # Placeholder implementation
        if 'institutional_sentiment' in external_data:
            return external_data['institutional_sentiment']
        return 0.0
    
    def _combine_sentiments(self, market: float, news: float, 
                           social: float, institutional: float) -> float:
        """
        Combine multiple sentiment sources.
        
        Args:
            market: Market sentiment
            news: News sentiment
            social: Social sentiment
            institutional: Institutional sentiment
            
        Returns:
            Combined sentiment (-1 to 1)
        """
        # Weighted average
        weights = {
            'market': 0.3,
            'news': 0.2,
            'social': 0.2,
            'institutional': 0.3
        }
        
        sentiment = (market * weights['market'] + 
                    news * weights['news'] + 
                    social * weights['social'] + 
                    institutional * weights['institutional'])
        
        return max(-1, min(1, sentiment))
    
    def _calculate_fear_greed(self, df: pd.DataFrame) -> float:
        """
        Calculate Fear & Greed Index approximation.
        
        Args:
            df: OHLCV data
            
        Returns:
            Fear & Greed Index (0-100)
        """
        close = df['close'].values
        volume = df['volume'].values
        
        # Calculate components
        # Price momentum (0-100)
        price_change = (close[-1] - close[-20]) / close[-20] if len(close) >= 20 else 0
        momentum = 50 + price_change * 100
        
        # Volume (0-100)
        volume_ma = np.mean(volume[-20:]) if len(volume) >= 20 else 1
        volume_ratio = volume[-1] / volume_ma if volume_ma > 0 else 1
        volume_score = 50 + (volume_ratio - 1) * 50
        
        # Volatility (0-100)
        returns = np.diff(np.log(close))
        volatility = np.std(returns[-20:]) * np.sqrt(252) if len(returns) >= 20 else 0.2
        volatility_score = 50 - volatility * 100
        
        # Combine
        fear_greed = (momentum * 0.4 + volume_score * 0.3 + volatility_score * 0.3)
        return max(0, min(100, fear_greed))
    
    def _calculate_put_call_ratio(self, df: pd.DataFrame) -> float:
        """
        Calculate Put/Call ratio approximation.
        
        Args:
            df: OHLCV data
            
        Returns:
            Put/Call ratio
        """
        # This would use actual options data in production
        # Placeholder implementation
        return 0.8
    
    def _calculate_vix(self, df: pd.DataFrame) -> float:
        """
        Calculate VIX approximation.
        
        Args:
            df: OHLCV data
            
        Returns:
            VIX approximation
        """
        close = df['close'].values
        
        if len(close) < 22:
            return 15.0
        
        returns = np.diff(np.log(close))
        volatility = np.std(returns[-22:]) * np.sqrt(252)
        vix = 15 + volatility * 30
        
        return max(10, min(60, vix))
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[SentimentSignal]:
        """
        Generate trading signal from sentiment.
        
        Args:
            df: OHLCV data
            
        Returns:
            SentimentSignal or None
        """
        metrics = self.analyze(df)
        
        if abs(metrics.overall_sentiment) < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Generate signal based on sentiment
        if metrics.overall_sentiment > 0.3:
            signal_type = 'buy'
            reason = f"Bullish sentiment detected ({metrics.overall_sentiment:.2f})"
            confidence = metrics.overall_sentiment
            target = current_price * (1 + confidence * 0.03)
            stop_loss = current_price * (1 - confidence * 0.02)
        elif metrics.overall_sentiment < -0.3:
            signal_type = 'sell'
            reason = f"Bearish sentiment detected ({metrics.overall_sentiment:.2f})"
            confidence = abs(metrics.overall_sentiment)
            target = current_price * (1 - confidence * 0.03)
            stop_loss = current_price * (1 + confidence * 0.02)
        else:
            return None
        
        return SentimentSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            sentiment=metrics,
            indicators={
                'fear_greed': metrics.fear_greed_index,
                'put_call_ratio': metrics.put_call_ratio,
                'vix': metrics.vix_index
            }
        )
    
    def get_sentiment_summary(self) -> Dict[str, Any]:
        """
        Get sentiment summary.
        
        Returns:
            Sentiment summary
        """
        if not self.metrics_history:
            return {'status': 'no_data'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_sentiment': {
                'overall': latest.overall_sentiment,
                'bullish': latest.bullish_score,
                'bearish': latest.bearish_score,
                'neutral': latest.neutral_score
            },
            'indicators': {
                'fear_greed': latest.fear_greed_index,
                'put_call_ratio': latest.put_call_ratio,
                'vix': latest.vix_index
            },
            'sources': {
                'social': latest.social_sentiment,
                'news': latest.news_sentiment,
                'institutional': latest.institutional_sentiment
            },
            'trend': self._calculate_sentiment_trend(),
            'history_length': len(self.metrics_history)
        }
    
    def _calculate_sentiment_trend(self) -> str:
        """
        Calculate sentiment trend.
        
        Returns:
            Sentiment trend string
        """
        if len(self.metrics_history) < 5:
            return 'stable'
        
        recent = np.mean([m.overall_sentiment for m in self.metrics_history[-5:]])
        past = np.mean([m.overall_sentiment for m in self.metrics_history[-10:-5]])
        
        if recent > past + 0.1:
            return 'improving'
        elif recent < past - 0.1:
            return 'declining'
        else:
            return 'stable'


def create_sentiment_model(config: Optional[Dict[str, Any]] = None) -> SentimentModel:
    """
    Create a sentiment model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        SentimentModel instance
    """
    return SentimentModel(config)


__all__ = [
    'SentimentMetrics',
    'SentimentSignal',
    'SentimentModel',
    'create_sentiment_model'
]
