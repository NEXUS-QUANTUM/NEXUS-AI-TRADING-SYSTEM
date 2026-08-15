"""
Swing Bot Excellence Model
============================

This module provides excellence and optimization models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class ExcellenceMetric:
    """Excellence metric data structure."""
    name: str
    value: float
    target: float
    deviation: float
    status: str  # 'excellent', 'good', 'needs_improvement', 'poor'
    weight: float
    timestamp: datetime


@dataclass
class ExcellenceReport:
    """Excellence report data structure."""
    timestamp: datetime
    overall_score: float
    metrics: List[ExcellenceMetric]
    areas_for_improvement: List[str]
    strengths: List[str]
    recommendation: str


@dataclass
class ExcellenceSignal:
    """Excellence trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    report: ExcellenceReport
    indicators: Dict[str, Any] = field(default_factory=dict)


class ExcellenceModel:
    """
    Excellence model for trading system optimization.
    
    Implements metrics and optimization for trading excellence.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the excellence model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.metrics: Dict[str, Dict[str, Any]] = {}
        self.reports: List[ExcellenceReport] = []
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
        # Define excellence metrics
        self._register_metrics()
        
    def _register_metrics(self) -> None:
        """Register excellence metrics."""
        self.metrics = {
            'sharpe_ratio': {
                'target': 1.0,
                'weight': 0.20,
                'current': 0.0
            },
            'win_rate': {
                'target': 0.60,
                'weight': 0.15,
                'current': 0.0
            },
            'profit_factor': {
                'target': 1.5,
                'weight': 0.15,
                'current': 0.0
            },
            'max_drawdown': {
                'target': 0.10,
                'weight': 0.15,
                'current': 0.0
            },
            'risk_reward_ratio': {
                'target': 2.0,
                'weight': 0.15,
                'current': 0.0
            },
            'execution_quality': {
                'target': 0.95,
                'weight': 0.10,
                'current': 0.0
            },
            'consistency': {
                'target': 0.80,
                'weight': 0.10,
                'current': 0.0
            }
        }
    
    def analyze(self, performance_data: Dict[str, float]) -> ExcellenceReport:
        """
        Analyze excellence metrics.
        
        Args:
            performance_data: Performance metrics data
            
        Returns:
            ExcellenceReport object
        """
        if not performance_data:
            return self._get_default_report()
        
        # Update metrics with current values
        for metric_name, value in performance_data.items():
            if metric_name in self.metrics:
                self.metrics[metric_name]['current'] = value
        
        # Calculate excellence metrics
        excellence_metrics = []
        overall_score = 0
        
        for metric_name, metric_data in self.metrics.items():
            current = metric_data['current']
            target = metric_data['target']
            weight = metric_data['weight']
            
            # Calculate deviation
            if target > 0:
                deviation = (current - target) / target
            else:
                deviation = current - target
            
            # Determine status
            if abs(deviation) < 0.05:
                status = 'excellent'
            elif abs(deviation) < 0.15:
                status = 'good'
            elif abs(deviation) < 0.30:
                status = 'needs_improvement'
            else:
                status = 'poor'
            
            # Calculate score
            if target > 0:
                score = min(max(current / target, 0), 2.0)
            else:
                score = 0.0
            
            excellence_metric = ExcellenceMetric(
                name=metric_name,
                value=current,
                target=target,
                deviation=deviation,
                status=status,
                weight=weight,
                timestamp=datetime.now()
            )
            
            excellence_metrics.append(excellence_metric)
            overall_score += min(score, 1.0) * weight
        
        # Identify strengths and areas for improvement
        strengths = []
        areas_for_improvement = []
        
        for metric in excellence_metrics:
            if metric.status in ['excellent', 'good']:
                strengths.append(metric.name)
            else:
                areas_for_improvement.append(metric.name)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(areas_for_improvement, strengths)
        
        report = ExcellenceReport(
            timestamp=datetime.now(),
            overall_score=overall_score,
            metrics=excellence_metrics,
            areas_for_improvement=areas_for_improvement,
            strengths=strengths,
            recommendation=recommendation
        )
        
        self.reports.append(report)
        
        return report
    
    def _generate_recommendation(self, areas_for_improvement: List[str],
                               strengths: List[str]) -> str:
        """
        Generate recommendation based on analysis.
        
        Args:
            areas_for_improvement: Areas needing improvement
            strengths: Areas of strength
            
        Returns:
            Recommendation string
        """
        if not areas_for_improvement:
            return "All metrics are performing well. Maintain current strategy."
        
        if len(areas_for_improvement) <= 2:
            return f"Focus on improving: {', '.join(areas_for_improvement)}. Current strengths: {', '.join(strengths)}."
        else:
            return f"Significant improvement needed in: {', '.join(areas_for_improvement)}. Consider strategy review."
    
    def _get_default_report(self) -> ExcellenceReport:
        """
        Get default report.
        
        Returns:
            Default ExcellenceReport object
        """
        return ExcellenceReport(
            timestamp=datetime.now(),
            overall_score=0.0,
            metrics=[],
            areas_for_improvement=[],
            strengths=[],
            recommendation="Insufficient data for analysis"
        )
    
    def generate_signal(self, df: pd.DataFrame, performance_data: Dict[str, float]) -> Optional[ExcellenceSignal]:
        """
        Generate trading signal from excellence analysis.
        
        Args:
            df: OHLCV data
            performance_data: Performance metrics
            
        Returns:
            ExcellenceSignal or None
        """
        report = self.analyze(performance_data)
        
        if report.overall_score < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Determine signal based on excellence
        if report.overall_score > 0.8:
            signal_type = 'buy'
            reason = f"Excellent performance score ({report.overall_score:.2f})"
            confidence = report.overall_score
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif report.overall_score < 0.4:
            signal_type = 'sell'
            reason = f"Poor performance score ({report.overall_score:.2f})"
            confidence = 1 - report.overall_score
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            return None
        
        return ExcellenceSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            report=report,
            indicators={
                'overall_score': report.overall_score,
                'strengths': report.strengths,
                'areas_for_improvement': report.areas_for_improvement,
                'recommendation': report.recommendation
            }
        )
    
    def get_excellence_summary(self) -> Dict[str, Any]:
        """
        Get excellence summary.
        
        Returns:
            Excellence summary
        """
        if not self.reports:
            return {'status': 'no_reports'}
        
        latest = self.reports[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_report': latest,
            'total_reports': len(self.reports),
            'average_score': np.mean([r.overall_score for r in self.reports]),
            'best_score': max([r.overall_score for r in self.reports]),
            'worst_score': min([r.overall_score for r in self.reports]),
            'current_status': 'improving' if latest.overall_score > np.mean([r.overall_score for r in self.reports]) else 'declining'
        }


def create_excellence_model(config: Optional[Dict[str, Any]] = None) -> ExcellenceModel:
    """
    Create an excellence model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        ExcellenceModel instance
    """
    return ExcellenceModel(config)


__all__ = [
    'ExcellenceMetric',
    'ExcellenceReport',
    'ExcellenceSignal',
    'ExcellenceModel',
    'create_excellence_model'
]
