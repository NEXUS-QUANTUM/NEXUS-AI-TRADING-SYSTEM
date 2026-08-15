"""
Swing Bot Fundamental Model
=============================

This module provides fundamental analysis models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class FundamentalMetrics:
    """Fundamental metrics data structure."""
    timestamp: datetime
    pe_ratio: float
    pb_ratio: float
    ps_ratio: float
    peg_ratio: float
    dividend_yield: float
    roe: float
    roa: float
    debt_equity: float
    current_ratio: float
    eps_growth: float
    revenue_growth: float
    profit_margin: float
    operating_margin: float
    free_cash_flow: float


@dataclass
class FundamentalSignal:
    """Fundamental trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    metrics: FundamentalMetrics
    indicators: Dict[str, Any] = field(default_factory=dict)


class FundamentalModel:
    """
    Fundamental analysis model for company valuation.
    
    Implements fundamental analysis for trading decisions.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the fundamental model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.metrics_history: List[FundamentalMetrics] = []
        
        # Define thresholds
        self.thresholds = {
            'pe_ratio': {'max': 30, 'min': 5},
            'pb_ratio': {'max': 5, 'min': 0.5},
            'ps_ratio': {'max': 10, 'min': 0.5},
            'peg_ratio': {'max': 2, 'min': 0.5},
            'dividend_yield': {'min': 0.02},
            'roe': {'min': 0.10},
            'roa': {'min': 0.05},
            'debt_equity': {'max': 1.0},
            'current_ratio': {'min': 1.5},
            'eps_growth': {'min': 0.05},
            'revenue_growth': {'min': 0.05},
            'profit_margin': {'min': 0.05},
            'operating_margin': {'min': 0.05}
        }
        
    def analyze(self, df: pd.DataFrame, fundamental_data: Dict[str, float]) -> Dict[str, Any]:
        """
        Analyze fundamental metrics.
        
        Args:
            df: OHLCV data
            fundamental_data: Dictionary of fundamental metrics
            
        Returns:
            Fundamental analysis results
        """
        if not fundamental_data:
            return {'metrics': self._get_default_metrics(), 'signals': []}
        
        # Calculate metrics
        metrics = self._calculate_metrics(fundamental_data)
        
        # Generate signals
        signals = self._generate_signals(df, metrics)
        
        return {
            'metrics': metrics,
            'signals': signals,
            'status': self._get_status(metrics),
            'market_character': self._get_market_character(df, metrics)
        }
    
    def _calculate_metrics(self, data: Dict[str, float]) -> FundamentalMetrics:
        """
        Calculate fundamental metrics.
        
        Args:
            data: Dictionary of fundamental data
            
        Returns:
            FundamentalMetrics object
        """
        metrics = FundamentalMetrics(
            timestamp=datetime.now(),
            pe_ratio=data.get('pe_ratio', 0),
            pb_ratio=data.get('pb_ratio', 0),
            ps_ratio=data.get('ps_ratio', 0),
            peg_ratio=data.get('peg_ratio', 0),
            dividend_yield=data.get('dividend_yield', 0),
            roe=data.get('roe', 0),
            roa=data.get('roa', 0),
            debt_equity=data.get('debt_equity', 0),
            current_ratio=data.get('current_ratio', 0),
            eps_growth=data.get('eps_growth', 0),
            revenue_growth=data.get('revenue_growth', 0),
            profit_margin=data.get('profit_margin', 0),
            operating_margin=data.get('operating_margin', 0),
            free_cash_flow=data.get('free_cash_flow', 0)
        )
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _get_default_metrics(self) -> FundamentalMetrics:
        """
        Get default metrics.
        
        Returns:
            Default FundamentalMetrics object
        """
        return FundamentalMetrics(
            timestamp=datetime.now(),
            pe_ratio=0.0,
            pb_ratio=0.0,
            ps_ratio=0.0,
            peg_ratio=0.0,
            dividend_yield=0.0,
            roe=0.0,
            roa=0.0,
            debt_equity=0.0,
            current_ratio=0.0,
            eps_growth=0.0,
            revenue_growth=0.0,
            profit_margin=0.0,
            operating_margin=0.0,
            free_cash_flow=0.0
        )
    
    def _generate_signals(self, df: pd.DataFrame,
                         metrics: FundamentalMetrics) -> List[FundamentalSignal]:
        """
        Generate trading signals from fundamental metrics.
        
        Args:
            df: OHLCV data
            metrics: FundamentalMetrics object
            
        Returns:
            List of FundamentalSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Calculate overall fundamental score
        score = self._calculate_fundamental_score(metrics)
        confidence = score
        
        if confidence < self.confidence_threshold:
            return signals
        
        # Generate signal based on score
        if score > 0.7:
            signal_type = 'buy'
            reason = "Strong fundamentals - attractive valuation"
            target = current_price * 1.05
            stop_loss = current_price * 0.95
            
        elif score < 0.3:
            signal_type = 'sell'
            reason = "Weak fundamentals - poor valuation"
            confidence = 1 - score
            target = current_price * 0.95
            stop_loss = current_price * 1.05
            
        else:
            return signals
        
        signals.append(FundamentalSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            metrics=metrics,
            indicators={
                'score': score,
                'pe_ratio': metrics.pe_ratio,
                'roe': metrics.roe,
                'growth': metrics.eps_growth
            }
        ))
        
        return signals
    
    def _calculate_fundamental_score(self, metrics: FundamentalMetrics) -> float:
        """
        Calculate overall fundamental score.
        
        Args:
            metrics: FundamentalMetrics object
            
        Returns:
            Score (0-1)
        """
        scores = []
        
        # PE Ratio
        if metrics.pe_ratio > 0:
            if metrics.pe_ratio < 15:
                scores.append(1.0)
            elif metrics.pe_ratio < 20:
                scores.append(0.7)
            elif metrics.pe_ratio < 30:
                scores.append(0.4)
            else:
                scores.append(0.2)
        
        # ROE
        if metrics.roe > 0.15:
            scores.append(1.0)
        elif metrics.roe > 0.10:
            scores.append(0.7)
        elif metrics.roe > 0.05:
            scores.append(0.4)
        else:
            scores.append(0.2)
        
        # Growth
        if metrics.eps_growth > 0.15:
            scores.append(1.0)
        elif metrics.eps_growth > 0.10:
            scores.append(0.7)
        elif metrics.eps_growth > 0.05:
            scores.append(0.4)
        else:
            scores.append(0.2)
        
        # Debt to Equity
        if metrics.debt_equity < 0.5:
            scores.append(1.0)
        elif metrics.debt_equity < 1.0:
            scores.append(0.7)
        elif metrics.debt_equity < 1.5:
            scores.append(0.4)
        else:
            scores.append(0.2)
        
        # Profit Margin
        if metrics.profit_margin > 0.15:
            scores.append(1.0)
        elif metrics.profit_margin > 0.10:
            scores.append(0.7)
        elif metrics.profit_margin > 0.05:
            scores.append(0.4)
        else:
            scores.append(0.2)
        
        # Average scores
        if scores:
            return np.mean(scores)
        else:
            return 0.5
    
    def _get_status(self, metrics: FundamentalMetrics) -> str:
        """
        Get status from fundamental metrics.
        
        Args:
            metrics: FundamentalMetrics object
            
        Returns:
            Status string
        """
        score = self._calculate_fundamental_score(metrics)
        
        if score > 0.7:
            return 'attractive'
        elif score > 0.5:
            return 'fair'
        else:
            return 'unattractive'
    
    def _get_market_character(self, df: pd.DataFrame,
                            metrics: FundamentalMetrics) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            metrics: FundamentalMetrics object
            
        Returns:
            Market character description
        """
        status = self._get_status(metrics)
        status_map = {
            'attractive': "Fundamentally attractive - strong metrics",
            'fair': "Fundamentally fair - average metrics",
            'unattractive': "Fundamentally unattractive - weak metrics"
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get fundamental metrics summary.
        
        Returns:
            Metrics summary
        """
        if not self.metrics_history:
            return {'status': 'no_metrics'}
        
        latest = self.metrics_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_metrics': latest,
            'average_pe': np.mean([m.pe_ratio for m in self.metrics_history]),
            'average_roe': np.mean([m.roe for m in self.metrics_history]),
            'average_growth': np.mean([m.eps_growth for m in self.metrics_history]),
            'average_score': np.mean([self._calculate_fundamental_score(m) for m in self.metrics_history]),
            'status': self._get_status(latest),
            'history_length': len(self.metrics_history)
        }


def create_fundamental_model(config: Optional[Dict[str, Any]] = None) -> FundamentalModel:
    """
    Create a fundamental model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        FundamentalModel instance
    """
    return FundamentalModel(config)


__all__ = [
    'FundamentalMetrics',
    'FundamentalSignal',
    'FundamentalModel',
    'create_fundamental_model'
]
