"""
Swing Bot Decision Model
==========================

This module provides decision-making models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class DecisionCriteria:
    """Decision criteria data structure."""
    criterion: str
    weight: float
    value: float
    threshold: float
    score: float
    is_met: bool


@dataclass
class DecisionResult:
    """Decision result data structure."""
    timestamp: datetime
    decision: str  # 'buy', 'sell', 'hold', 'short', 'cover'
    confidence: float
    criteria_results: List[DecisionCriteria]
    overall_score: float
    reasoning: str


@dataclass
class DecisionSignal:
    """Decision trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    decision: DecisionResult
    indicators: Dict[str, Any] = field(default_factory=dict)


class DecisionModel:
    """
    Decision-making model for trading actions.
    
    Implements multi-criteria decision analysis.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the decision model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.criteria = self.config.get('criteria', [
            {'name': 'trend', 'weight': 0.25, 'threshold': 0.5},
            {'name': 'momentum', 'weight': 0.20, 'threshold': 0.5},
            {'name': 'volatility', 'weight': 0.15, 'threshold': 0.5},
            {'name': 'volume', 'weight': 0.10, 'threshold': 0.5},
            {'name': 'sentiment', 'weight': 0.10, 'threshold': 0.5},
            {'name': 'risk_reward', 'weight': 0.10, 'threshold': 0.5},
            {'name': 'technical', 'weight': 0.10, 'threshold': 0.5}
        ])
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.decision_history: List[DecisionResult] = []
        
    def analyze(self, df: pd.DataFrame, signals: List[Dict[str, Any]]) -> DecisionResult:
        """
        Analyze and make a trading decision.
        
        Args:
            df: OHLCV data
            signals: List of signals from various models
            
        Returns:
            DecisionResult object
        """
        if len(df) < 20:
            return self._get_default_decision()
        
        # Evaluate each criterion
        criteria_results = []
        overall_score = 0
        
        for criterion in self.criteria:
            value = self._evaluate_criterion(criterion['name'], df, signals)
            threshold = criterion['threshold']
            weight = criterion['weight']
            
            # Calculate score (0-1)
            score = min(max(value, 0), 1)
            
            # Check if criterion is met
            is_met = value >= threshold
            
            criterion_result = DecisionCriteria(
                criterion=criterion['name'],
                weight=weight,
                value=value,
                threshold=threshold,
                score=score,
                is_met=is_met
            )
            criteria_results.append(criterion_result)
            overall_score += weight * score
        
        # Determine decision
        decision = self._determine_decision(criteria_results, overall_score)
        
        # Calculate confidence
        confidence = min(max(overall_score, 0), 1)
        
        # Generate reasoning
        reasoning = self._generate_reasoning(criteria_results, decision)
        
        result = DecisionResult(
            timestamp=datetime.now(),
            decision=decision,
            confidence=confidence,
            criteria_results=criteria_results,
            overall_score=overall_score,
            reasoning=reasoning
        )
        
        self.decision_history.append(result)
        
        return result
    
    def _evaluate_criterion(self, criterion: str, df: pd.DataFrame,
                           signals: List[Dict[str, Any]]) -> float:
        """
        Evaluate a specific criterion.
        
        Args:
            criterion: Criterion name
            df: OHLCV data
            signals: List of signals
            
        Returns:
            Score (0-1)
        """
        close = df['close'].values
        
        if criterion == 'trend':
            # Evaluate trend strength
            if len(close) < 20:
                return 0.5
            
            slope, intercept = MathUtils.linear_regression(
                np.arange(20),
                close[-20:]
            )
            r2 = MathUtils.r_squared(np.arange(20), close[-20:])
            
            trend_score = (min(abs(slope) * 10, 1.0) * 0.5 + r2 * 0.5)
            return trend_score
            
        elif criterion == 'momentum':
            # Evaluate momentum
            if len(close) < 10:
                return 0.5
            
            momentum = (close[-1] - close[-10]) / close[-10]
            return min(abs(momentum) * 10, 1.0)
            
        elif criterion == 'volatility':
            # Evaluate volatility
            if len(close) < 20:
                return 0.5
            
            returns = np.diff(np.log(close))
            volatility = np.std(returns[-20:]) * np.sqrt(252)
            
            # Lower volatility is better
            return 1 - min(volatility, 1.0)
            
        elif criterion == 'volume':
            # Evaluate volume
            if 'volume' not in df.columns:
                return 0.5
            
            volume = df['volume'].values
            if len(volume) < 20:
                return 0.5
            
            volume_ma = np.mean(volume[-20:])
            volume_score = min(volume[-1] / (volume_ma + 1e-10), 1.0)
            return volume_score
            
        elif criterion == 'sentiment':
            # Evaluate sentiment from signals
            sentiment_signals = [s for s in signals if s.get('type') == 'sentiment']
            if not sentiment_signals:
                return 0.5
            
            avg_sentiment = np.mean([s.get('value', 0.5) for s in sentiment_signals])
            return avg_sentiment
            
        elif criterion == 'risk_reward':
            # Evaluate risk-reward ratio
            if not signals:
                return 0.5
            
            risk_reward_signals = [s for s in signals if s.get('type') == 'risk_reward']
            if not risk_reward_signals:
                return 0.5
            
            avg_rr = np.mean([s.get('value', 0.5) for s in risk_reward_signals])
            return avg_rr
            
        elif criterion == 'technical':
            # Evaluate technical indicators
            if len(close) < 20:
                return 0.5
            
            # Combine RSI, MACD, etc.
            rsi = self._calculate_rsi(close)
            macd = self._calculate_macd(close)
            
            rsi_score = 1 - abs(rsi - 50) / 50
            macd_score = 0.5 + 0.5 * np.tanh(macd)
            
            return (rsi_score + macd_score) / 2
            
        return 0.5
    
    def _calculate_rsi(self, close: np.ndarray) -> float:
        """
        Calculate RSI.
        
        Args:
            close: Close prices
            
        Returns:
            RSI value
        """
        if len(close) < 15:
            return 50.0
        
        returns = np.diff(close)
        gains = np.where(returns > 0, returns, 0)
        losses = np.where(returns < 0, -returns, 0)
        
        avg_gain = np.mean(gains[-14:])
        avg_loss = np.mean(losses[-14:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_macd(self, close: np.ndarray) -> float:
        """
        Calculate MACD.
        
        Args:
            close: Close prices
            
        Returns:
            MACD value
        """
        if len(close) < 26:
            return 0.0
        
        # Calculate EMAs
        ema12 = self._calculate_ema(close, 12)
        ema26 = self._calculate_ema(close, 26)
        
        if len(ema12) == 0 or len(ema26) == 0:
            return 0.0
        
        return ema12[-1] - ema26[-1]
    
    def _calculate_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """
        Calculate EMA.
        
        Args:
            data: Input data
            period: EMA period
            
        Returns:
            EMA values
        """
        if len(data) < period:
            return np.array([])
        
        alpha = 2 / (period + 1)
        ema = np.zeros(len(data))
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
        
        return ema
    
    def _determine_decision(self, criteria_results: List[DecisionCriteria],
                           overall_score: float) -> str:
        """
        Determine the trading decision.
        
        Args:
            criteria_results: List of criteria results
            overall_score: Overall score
            
        Returns:
            Decision string
        """
        if overall_score > 0.7:
            return 'buy'
        elif overall_score > 0.6:
            return 'buy' if criteria_results[0].value > 0.5 else 'hold'
        elif overall_score > 0.4:
            return 'hold'
        elif overall_score > 0.3:
            return 'sell' if criteria_results[0].value < 0.5 else 'hold'
        else:
            return 'sell'
    
    def _generate_reasoning(self, criteria_results: List[DecisionCriteria],
                          decision: str) -> str:
        """
        Generate reasoning for the decision.
        
        Args:
            criteria_results: List of criteria results
            decision: Decision string
            
        Returns:
            Reasoning string
        """
        # Find best and worst criteria
        best_criterion = max(criteria_results, key=lambda x: x.score)
        worst_criterion = min(criteria_results, key=lambda x: x.score)
        
        reasoning = f"Decision: {decision.upper()}. "
        reasoning += f"Best criterion: {best_criterion.criterion} ({best_criterion.score:.2f}). "
        reasoning += f"Worst criterion: {worst_criterion.criterion} ({worst_criterion.score:.2f}). "
        
        # Add overall assessment
        if decision in ['buy', 'sell']:
            reasoning += f"Strong {decision} signal with {best_criterion.criterion} driving the decision."
        else:
            reasoning += f"Mixed signals, holding position."
        
        return reasoning
    
    def _get_default_decision(self) -> DecisionResult:
        """
        Get default decision.
        
        Returns:
            Default DecisionResult object
        """
        return DecisionResult(
            timestamp=datetime.now(),
            decision='hold',
            confidence=0.5,
            criteria_results=[],
            overall_score=0.5,
            reasoning='Insufficient data for decision'
        )
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[DecisionSignal]:
        """
        Generate trading signal from decision.
        
        Args:
            df: OHLCV data
            
        Returns:
            DecisionSignal or None
        """
        # Get signals from other models (placeholder)
        signals = []
        
        # Make decision
        decision = self.analyze(df, signals)
        
        if decision.confidence < self.confidence_threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        if decision.decision in ['buy', 'sell', 'short', 'cover']:
            if decision.decision == 'buy':
                target = current_price * 1.02
                stop_loss = current_price * 0.98
            elif decision.decision == 'sell':
                target = current_price * 0.98
                stop_loss = current_price * 1.02
            elif decision.decision == 'short':
                target = current_price * 0.98
                stop_loss = current_price * 1.02
            else:  # cover
                target = current_price * 1.02
                stop_loss = current_price * 0.98
            
            return DecisionSignal(
                symbol=symbol,
                timestamp=datetime.now(),
                signal_type=decision.decision,
                confidence=decision.confidence,
                price=current_price,
                target=target,
                stop_loss=stop_loss,
                reason=decision.reasoning,
                decision=decision,
                indicators={
                    'overall_score': decision.overall_score,
                    'criteria_results': decision.criteria_results
                }
            )
        
        return None
    
    def get_decision_summary(self) -> Dict[str, Any]:
        """
        Get decision summary.
        
        Returns:
            Decision summary
        """
        if not self.decision_history:
            return {'status': 'no_decisions'}
        
        latest = self.decision_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_decision': latest.decision,
            'latest_confidence': latest.confidence,
            'decision_distribution': {
                'buy': len([d for d in self.decision_history if d.decision == 'buy']),
                'sell': len([d for d in self.decision_history if d.decision == 'sell']),
                'hold': len([d for d in self.decision_history if d.decision == 'hold']),
                'short': len([d for d in self.decision_history if d.decision == 'short']),
                'cover': len([d for d in self.decision_history if d.decision == 'cover'])
            },
            'average_confidence': np.mean([d.confidence for d in self.decision_history]),
            'latest_reasoning': latest.reasoning,
            'history_length': len(self.decision_history)
        }


def create_decision_model(config: Optional[Dict[str, Any]] = None) -> DecisionModel:
    """
    Create a decision model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        DecisionModel instance
    """
    return DecisionModel(config)


__all__ = [
    'DecisionCriteria',
    'DecisionResult',
    'DecisionSignal',
    'DecisionModel',
    'create_decision_model'
]
