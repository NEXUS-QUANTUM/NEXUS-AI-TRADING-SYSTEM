"""
Swing Bot Industry Model
==========================

This module provides industry analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class IndustryMetrics:
    """Industry metrics data structure."""
    timestamp: datetime
    industry: str
    performance: float
    momentum: float
    relative_strength: float
    valuation: float
    sentiment: float
    flow: float
    volatility: float
    correlation: float


@dataclass
class IndustrySignal:
    """Industry trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    industry: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class IndustryModel:
    """
    Industry analysis model for sector-specific trading.
    
    Implements industry-level analysis for trading decisions.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the industry model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.industries = self.config.get('industries', [
            'technology', 'financials', 'healthcare', 'energy',
            'consumer', 'industrials', 'utilities', 'materials',
            'real_estate', 'communication'
        ])
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.industry_history: Dict[str, List[IndustryMetrics]] = {}
        
        for industry in self.industries:
            self.industry_history[industry] = []
        
    def analyze(self, df_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Analyze industry metrics.
        
        Args:
            df_dict: Dictionary of industry dataframes
            
        Returns:
            Industry analysis results
        """
        if not df_dict:
            return {'metrics': [], 'signals': []}
        
        # Calculate metrics for each industry
        metrics = []
        for industry, df in df_dict.items():
            if industry in self.industries:
                metric = self._calculate_industry_metrics(industry, df)
                metrics.append(metric)
                if industry in self.industry_history:
                    self.industry_history[industry].append(metric)
        
        # Generate signals
        signals = self._generate_signals(df_dict, metrics)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'top_industries': self._get_top_industries(metrics),
            'bottom_industries': self._get_bottom_industries(metrics),
            'market_character': self._get_market_character(metrics)
        }
    
    def _calculate_industry_metrics(self, industry: str, df: pd.DataFrame) -> IndustryMetrics:
        """
        Calculate metrics for an industry.
        
        Args:
            industry: Industry name
            df: Industry data
            
        Returns:
            IndustryMetrics object
        """
        if len(df) < self.lookback_period:
            return IndustryMetrics(
                timestamp=datetime.now(),
                industry=industry,
                performance=0.0,
                momentum=0.0,
                relative_strength=0.0,
                valuation=0.0,
                sentiment=0.0,
                flow=0.0,
                volatility=0.0,
                correlation=0.0
            )
        
        close = df['close'].values
        volume = df['volume'].values
        
        # Calculate performance
        performance = (close[-1] - close[-self.lookback_period]) / close[-self.lookback_period]
        
        # Calculate momentum
        momentum = (close[-1] - close[-10]) / close[-10] if len(close) >= 10 else 0
        
        # Calculate relative strength
        relative_strength = performance * 0.5 + momentum * 0.5
        
        # Calculate valuation (placeholder)
        valuation = 0.5
        
        # Calculate sentiment (placeholder)
        sentiment = 0.5
        
        # Calculate flow
        flow = volume[-1] / np.mean(volume[-self.lookback_period:]) if np.mean(volume[-self.lookback_period:]) > 0 else 1
        
        # Calculate volatility
        returns = np.diff(np.log(close))
        volatility = np.std(returns[-self.lookback_period:]) * np.sqrt(252)
        
        # Calculate correlation with market (placeholder)
        correlation = 0.5
        
        return IndustryMetrics(
            timestamp=datetime.now(),
            industry=industry,
            performance=performance,
            momentum=momentum,
            relative_strength=relative_strength,
            valuation=valuation,
            sentiment=sentiment,
            flow=flow,
            volatility=volatility,
            correlation=correlation
        )
    
    def _generate_signals(self, df_dict: Dict[str, pd.DataFrame],
                         metrics: List[IndustryMetrics]) -> List[IndustrySignal]:
        """
        Generate trading signals from industry metrics.
        
        Args:
            df_dict: Dictionary of industry dataframes
            metrics: List of industry metrics
            
        Returns:
            List of IndustrySignal objects
        """
        signals = []
        
        if not metrics:
            return signals
        
        # Sort industries by performance
        sorted_industries = sorted(metrics, key=lambda x: x.performance, reverse=True)
        
        if len(sorted_industries) < 2:
            return signals
        
        # Get best and worst industries
        best_industry = sorted_industries[0]
        worst_industry = sorted_industries[-1]
        
        # Check if difference is significant
        performance_diff = best_industry.performance - worst_industry.performance
        confidence = min(abs(performance_diff) * 5, 1.0)
        
        if confidence < self.confidence_threshold:
            return signals
        
        # Generate signal for best industry
        if best_industry.industry in df_dict:
            df = df_dict[best_industry.industry]
            if len(df) > 0:
                current_price = df['close'].iloc[-1]
                symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
                
                signal_type = 'buy'
                reason = f"Leading industry {best_industry.industry}"
                target = current_price * (1 + confidence * 0.05)
                stop_loss = current_price * (1 - confidence * 0.03)
                
                signals.append(IndustrySignal(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    signal_type=signal_type,
                    confidence=confidence,
                    price=current_price,
                    target=target,
                    stop_loss=stop_loss,
                    reason=reason,
                    industry=best_industry.industry,
                    indicators={
                        'performance': best_industry.performance,
                        'momentum': best_industry.momentum,
                        'relative_strength': best_industry.relative_strength
                    }
                ))
        
        # Generate signal for worst industry
        if worst_industry.industry in df_dict:
            df = df_dict[worst_industry.industry]
            if len(df) > 0:
                current_price = df['close'].iloc[-1]
                symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
                
                signal_type = 'sell'
                reason = f"Underperforming industry {worst_industry.industry}"
                target = current_price * (1 - confidence * 0.05)
                stop_loss = current_price * (1 + confidence * 0.03)
                
                signals.append(IndustrySignal(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    signal_type=signal_type,
                    confidence=confidence,
                    price=current_price,
                    target=target,
                    stop_loss=stop_loss,
                    reason=reason,
                    industry=worst_industry.industry,
                    indicators={
                        'performance': worst_industry.performance,
                        'momentum': worst_industry.momentum,
                        'relative_strength': worst_industry.relative_strength
                    }
                ))
        
        return signals
    
    def _get_top_industries(self, metrics: List[IndustryMetrics]) -> List[Dict[str, Any]]:
        """
        Get top performing industries.
        
        Args:
            metrics: List of industry metrics
            
        Returns:
            List of top industries
        """
        if not metrics:
            return []
        
        sorted_metrics = sorted(metrics, key=lambda x: x.performance, reverse=True)
        return [
            {
                'industry': m.industry,
                'performance': m.performance,
                'momentum': m.momentum,
                'relative_strength': m.relative_strength,
                'volatility': m.volatility
            }
            for m in sorted_metrics[:3]
        ]
    
    def _get_bottom_industries(self, metrics: List[IndustryMetrics]) -> List[Dict[str, Any]]:
        """
        Get bottom performing industries.
        
        Args:
            metrics: List of industry metrics
            
        Returns:
            List of bottom industries
        """
        if not metrics:
            return []
        
        sorted_metrics = sorted(metrics, key=lambda x: x.performance)
        return [
            {
                'industry': m.industry,
                'performance': m.performance,
                'momentum': m.momentum,
                'relative_strength': m.relative_strength,
                'volatility': m.volatility
            }
            for m in sorted_metrics[:3]
        ]
    
    def _get_market_character(self, metrics: List[IndustryMetrics]) -> str:
        """
        Get market character description.
        
        Args:
            metrics: List of industry metrics
            
        Returns:
            Market character description
        """
        if not metrics:
            return "No industry data available"
        
        # Calculate average performance
        avg_performance = np.mean([m.performance for m in metrics])
        
        if avg_performance > 0.05:
            return "Bullish market - strong industry performance"
        elif avg_performance > 0.0:
            return "Moderate market - slight industry gains"
        elif avg_performance > -0.05:
            return "Moderate market - slight industry losses"
        else:
            return "Bearish market - weak industry performance"
    
    def get_industry_summary(self) -> Dict[str, Any]:
        """
        Get industry summary.
        
        Returns:
            Industry summary
        """
        summary = {
            'timestamp': datetime.now().isoformat(),
            'industries': {}
        }
        
        for industry, history in self.industry_history.items():
            if history:
                latest = history[-1]
                summary['industries'][industry] = {
                    'performance': latest.performance,
                    'momentum': latest.momentum,
                    'relative_strength': latest.relative_strength,
                    'volatility': latest.volatility,
                    'correlation': latest.correlation,
                    'trend': 'up' if latest.momentum > 0 else 'down',
                    'history_length': len(history)
                }
        
        return summary


def create_industry_model(config: Optional[Dict[str, Any]] = None) -> IndustryModel:
    """
    Create an industry model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        IndustryModel instance
    """
    return IndustryModel(config)


__all__ = [
    'IndustryMetrics',
    'IndustrySignal',
    'IndustryModel',
    'create_industry_model'
]
