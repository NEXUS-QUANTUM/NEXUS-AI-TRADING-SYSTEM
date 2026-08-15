"""
Swing Bot Adaptation Model
============================

This module provides adaptation and learning models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import json
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class AdaptationState:
    """Adaptation state data structure."""
    timestamp: datetime
    parameters: Dict[str, Any]
    performance: Dict[str, float]
    regime: str  # 'trending', 'ranging', 'volatile', 'quiet'
    confidence: float
    adaptation_count: int


@dataclass
class LearningSample:
    """Learning sample data structure."""
    features: np.ndarray
    target: float
    weight: float
    timestamp: datetime
    outcome: Optional[float] = None


@dataclass
class AdaptationSignal:
    """Adaptation trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'adapt', 'learn', 'switch'
    action: str
    confidence: float
    reason: str
    parameters: Dict[str, Any] = field(default_factory=dict)


class AdaptationModel:
    """
    Adaptation and learning model for market condition changes.
    
    Implements adaptive algorithms for changing market conditions.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the adaptation model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.learning_rate = self.config.get('learning_rate', 0.01)
        self.decay_rate = self.config.get('decay_rate', 0.99)
        self.max_samples = self.config.get('max_samples', 1000)
        self.adaptation_threshold = self.config.get('adaptation_threshold', 0.10)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
        # State tracking
        self.state_history: List[AdaptationState] = []
        self.samples: List[LearningSample] = []
        self.parameters: Dict[str, Any] = {}
        self.performance_history: Dict[str, List[float]] = {
            'accuracy': [],
            'sharpe': [],
            'win_rate': [],
            'drawdown': []
        }
        
        # Regime detection
        self.regimes = ['trending', 'ranging', 'volatile', 'quiet']
        self.current_regime = 'unknown'
        self.regime_history: List[Tuple[datetime, str]] = []
        
    def update(self, market_data: pd.DataFrame, performance: Dict[str, float]) -> AdaptationState:
        """
        Update adaptation model with new data.
        
        Args:
            market_data: Market data
            performance: Performance metrics
            
        Returns:
            AdaptationState object
        """
        # Detect regime
        regime = self._detect_regime(market_data)
        
        # Update parameters
        self._update_parameters(market_data, performance, regime)
        
        # Update performance history
        for key, value in performance.items():
            if key in self.performance_history:
                self.performance_history[key].append(value)
        
        # Create state
        state = AdaptationState(
            timestamp=datetime.now(),
            parameters=self.parameters.copy(),
            performance=performance,
            regime=regime,
            confidence=self._calculate_confidence(),
            adaptation_count=len(self.state_history)
        )
        
        self.state_history.append(state)
        self.current_regime = regime
        self.regime_history.append((datetime.now(), regime))
        
        # Trim history
        if len(self.state_history) > self.max_samples:
            self.state_history = self.state_history[-self.max_samples:]
        
        return state
    
    def _detect_regime(self, market_data: pd.DataFrame) -> str:
        """
        Detect market regime.
        
        Args:
            market_data: Market data
            
        Returns:
            Regime string
        """
        if len(market_data) < 20:
            return 'unknown'
        
        close = market_data['close'].values
        volume = market_data['volume'].values
        
        # Calculate metrics
        returns = np.diff(np.log(close))
        volatility = np.std(returns[-20:]) * np.sqrt(252)
        
        # Trend detection
        slope, intercept = MathUtils.linear_regression(
            np.arange(len(close[-20:])),
            close[-20:]
        )
        trend_strength = MathUtils.r_squared(
            np.arange(len(close[-20:])),
            close[-20:]
        )
        
        # Volume analysis
        volume_ma = np.mean(volume[-20:])
        volume_std = np.std(volume[-20:])
        
        # Determine regime
        if trend_strength > 0.6 and abs(slope) > 0.01:
            regime = 'trending'
        elif volatility > 0.30:
            regime = 'volatile'
        elif volatility < 0.15:
            regime = 'quiet'
        else:
            regime = 'ranging'
        
        return regime
    
    def _update_parameters(self, market_data: pd.DataFrame,
                          performance: Dict[str, float],
                          regime: str) -> None:
        """
        Update model parameters based on new data.
        
        Args:
            market_data: Market data
            performance: Performance metrics
            regime: Current regime
        """
        # Update learning rate
        self.learning_rate *= self.decay_rate
        
        # Update parameters based on regime
        if regime == 'trending':
            self._update_trending_parameters(market_data, performance)
        elif regime == 'ranging':
            self._update_ranging_parameters(market_data, performance)
        elif regime == 'volatile':
            self._update_volatile_parameters(market_data, performance)
        elif regime == 'quiet':
            self._update_quiet_parameters(market_data, performance)
    
    def _update_trending_parameters(self, market_data: pd.DataFrame,
                                   performance: Dict[str, float]) -> None:
        """Update parameters for trending regime."""
        # Increase trend-following parameters
        self.parameters['trend_weight'] = min(
            self.parameters.get('trend_weight', 0.6) + self.learning_rate,
            1.0
        )
        self.parameters['mean_reversion_weight'] = max(
            self.parameters.get('mean_reversion_weight', 0.4) - self.learning_rate,
            0.0
        )
    
    def _update_ranging_parameters(self, market_data: pd.DataFrame,
                                  performance: Dict[str, float]) -> None:
        """Update parameters for ranging regime."""
        # Increase mean-reversion parameters
        self.parameters['mean_reversion_weight'] = min(
            self.parameters.get('mean_reversion_weight', 0.4) + self.learning_rate,
            1.0
        )
        self.parameters['trend_weight'] = max(
            self.parameters.get('trend_weight', 0.6) - self.learning_rate,
            0.0
        )
    
    def _update_volatile_parameters(self, market_data: pd.DataFrame,
                                   performance: Dict[str, float]) -> None:
        """Update parameters for volatile regime."""
        # Reduce position sizing
        self.parameters['position_size_multiplier'] = max(
            self.parameters.get('position_size_multiplier', 1.0) - self.learning_rate * 2,
            0.5
        )
        # Increase stop loss distance
        self.parameters['stop_loss_multiplier'] = min(
            self.parameters.get('stop_loss_multiplier', 1.0) + self.learning_rate * 2,
            2.0
        )
    
    def _update_quiet_parameters(self, market_data: pd.DataFrame,
                                performance: Dict[str, float]) -> None:
        """Update parameters for quiet regime."""
        # Increase position sizing
        self.parameters['position_size_multiplier'] = min(
            self.parameters.get('position_size_multiplier', 1.0) + self.learning_rate,
            1.5
        )
        # Reduce stop loss distance
        self.parameters['stop_loss_multiplier'] = max(
            self.parameters.get('stop_loss_multiplier', 1.0) - self.learning_rate,
            0.5
        )
    
    def _calculate_confidence(self) -> float:
        """Calculate adaptation confidence."""
        if not self.state_history:
            return 0.5
        
        # Check recent performance
        recent_performance = self.performance_history.get('win_rate', [])
        if recent_performance:
            avg_win_rate = np.mean(recent_performance[-10:])
        else:
            avg_win_rate = 0.5
        
        # Check regime stability
        if len(self.regime_history) > 10:
            recent_regimes = [r for _, r in self.regime_history[-10:]]
            regime_changes = sum(1 for i in range(1, len(recent_regimes))
                               if recent_regimes[i] != recent_regimes[i-1])
            stability = 1 - (regime_changes / 10)
        else:
            stability = 0.5
        
        # Combine factors
        confidence = avg_win_rate * 0.6 + stability * 0.4
        
        return min(max(confidence, 0.0), 1.0)
    
    def learn(self, sample: LearningSample) -> None:
        """
        Learn from a new sample.
        
        Args:
            sample: Learning sample
        """
        self.samples.append(sample)
        
        # Trim samples
        if len(self.samples) > self.max_samples:
            self.samples = self.samples[-self.max_samples:]
    
    def predict(self, features: np.ndarray) -> float:
        """
        Make prediction based on learned patterns.
        
        Args:
            features: Feature vector
            
        Returns:
            Prediction value
        """
        if not self.samples:
            return 0.0
        
        # Simple weighted average of nearest samples
        predictions = []
        weights = []
        
        for sample in self.samples:
            similarity = self._calculate_similarity(features, sample.features)
            predictions.append(sample.target)
            weights.append(similarity * sample.weight)
        
        if sum(weights) == 0:
            return np.mean(predictions)
        
        return np.average(predictions, weights=weights)
    
    def _calculate_similarity(self, features1: np.ndarray,
                             features2: np.ndarray) -> float:
        """
        Calculate similarity between two feature vectors.
        
        Args:
            features1: First feature vector
            features2: Second feature vector
            
        Returns:
            Similarity score (0-1)
        """
        if len(features1) != len(features2):
            return 0.0
        
        # Cosine similarity
        norm1 = np.linalg.norm(features1)
        norm2 = np.linalg.norm(features2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = np.dot(features1, features2) / (norm1 * norm2)
        return (similarity + 1) / 2  # Normalize to 0-1
    
    def get_adaptation_signal(self, market_data: pd.DataFrame,
                            current_performance: Dict[str, float]) -> Optional[AdaptationSignal]:
        """
        Generate adaptation signal based on current conditions.
        
        Args:
            market_data: Market data
            current_performance: Current performance metrics
            
        Returns:
            AdaptationSignal or None
        """
        # Detect regime change
        current_regime = self._detect_regime(market_data)
        
        if current_regime != self.current_regime:
            # Regime change detected
            confidence = self._calculate_confidence()
            
            if confidence > self.confidence_threshold:
                return AdaptationSignal(
                    symbol=market_data.get('symbol', [''])[0] if 'symbol' in market_data.columns else '',
                    timestamp=datetime.now(),
                    signal_type='switch',
                    action=f'switch_to_{current_regime}',
                    confidence=confidence,
                    reason=f"Regime change detected: {self.current_regime} -> {current_regime}",
                    parameters={
                        'old_regime': self.current_regime,
                        'new_regime': current_regime,
                        'parameters': self.parameters.copy()
                    }
                )
        
        # Check performance degradation
        if len(self.performance_history.get('win_rate', [])) > 10:
            recent_win_rate = np.mean(self.performance_history['win_rate'][-5:])
            previous_win_rate = np.mean(self.performance_history['win_rate'][-10:-5])
            
            if previous_win_rate > 0 and recent_win_rate < previous_win_rate * 0.8:
                # Performance degradation detected
                confidence = self._calculate_confidence()
                
                if confidence > self.confidence_threshold:
                    return AdaptationSignal(
                        symbol=market_data.get('symbol', [''])[0] if 'symbol' in market_data.columns else '',
                        timestamp=datetime.now(),
                        signal_type='adapt',
                        action='adjust_parameters',
                        confidence=confidence,
                        reason=f"Performance degradation detected: {previous_win_rate:.2f} -> {recent_win_rate:.2f}",
                        parameters={
                            'previous_win_rate': previous_win_rate,
                            'current_win_rate': recent_win_rate,
                            'suggested_parameters': self.parameters.copy()
                        }
                    )
        
        return None
    
    def get_state_summary(self) -> Dict[str, Any]:
        """
        Get summary of current adaptation state.
        
        Returns:
            State summary dictionary
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'current_regime': self.current_regime,
            'parameters': self.parameters,
            'confidence': self._calculate_confidence(),
            'samples_count': len(self.samples),
            'state_history_count': len(self.state_history),
            'performance_summary': {
                key: {
                    'current': values[-1] if values else 0,
                    'mean': np.mean(values) if values else 0,
                    'std': np.std(values) if values else 0,
                    'min': np.min(values) if values else 0,
                    'max': np.max(values) if values else 0
                }
                for key, values in self.performance_history.items()
                if values
            }
        }


def create_adaptation_model(config: Optional[Dict[str, Any]] = None) -> AdaptationModel:
    """
    Create an adaptation model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        AdaptationModel instance
    """
    return AdaptationModel(config)


__all__ = [
    'AdaptationState',
    'LearningSample',
    'AdaptationSignal',
    'AdaptationModel',
    'create_adaptation_model'
]
