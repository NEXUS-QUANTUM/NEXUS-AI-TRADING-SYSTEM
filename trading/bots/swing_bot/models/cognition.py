"""
Swing Bot Cognition Model
===========================

This module provides cognitive analysis models for the Swing Bot trading system.
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
class CognitiveState:
    """Cognitive state data structure."""
    timestamp: datetime
    attention_score: float
    memory_retention: float
    learning_rate: float
    pattern_recognition: float
    decision_confidence: float
    adaptability: float
    cognitive_load: float


@dataclass
class CognitiveSignal:
    """Cognitive trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    cognitive_state: CognitiveState
    indicators: Dict[str, Any] = field(default_factory=dict)


class CognitionModel:
    """
    Cognitive analysis model for market psychology and behavior.
    
    Implements cognitive metrics for trading decisions.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the cognition model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.lookback_period = self.config.get('lookback_period', 50)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.cognitive_state_history: List[CognitiveState] = []
        
    def analyze(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze cognitive metrics.
        
        Args:
            df: OHLCV data
            
        Returns:
            Cognitive analysis results
        """
        if len(df) < self.lookback_period:
            return {'state': self._get_default_state(), 'signals': []}
        
        # Calculate cognitive state
        state = self._calculate_cognitive_state(df)
        
        # Generate signals
        signals = self._generate_signals(df, state)
        
        return {
            'state': state,
            'signals': signals,
            'status': self._get_status(state),
            'market_character': self._get_market_character(df, state)
        }
    
    def _calculate_cognitive_state(self, df: pd.DataFrame) -> CognitiveState:
        """
        Calculate cognitive state.
        
        Args:
            df: OHLCV data
            
        Returns:
            CognitiveState object
        """
        close = df['close'].values
        volume = df['volume'].values
        
        # Calculate attention score
        attention = self._calculate_attention(close, volume)
        
        # Calculate memory retention
        memory = self._calculate_memory_retention(close)
        
        # Calculate learning rate
        learning = self._calculate_learning_rate(close)
        
        # Calculate pattern recognition
        pattern = self._calculate_pattern_recognition(close)
        
        # Calculate decision confidence
        decision = self._calculate_decision_confidence(close)
        
        # Calculate adaptability
        adaptability = self._calculate_adaptability(close)
        
        # Calculate cognitive load
        cognitive_load = self._calculate_cognitive_load(close)
        
        state = CognitiveState(
            timestamp=datetime.now(),
            attention_score=attention,
            memory_retention=memory,
            learning_rate=learning,
            pattern_recognition=pattern,
            decision_confidence=decision,
            adaptability=adaptability,
            cognitive_load=cognitive_load
        )
        
        self.cognitive_state_history.append(state)
        
        return state
    
    def _calculate_attention(self, close: np.ndarray, volume: np.ndarray) -> float:
        """
        Calculate attention score.
        
        Args:
            close: Close prices
            volume: Volume data
            
        Returns:
            Attention score (0-1)
        """
        if len(close) < 20:
            return 0.5
        
        # Calculate price volatility
        volatility = np.std(close[-20:]) / np.mean(close[-20:])
        volatility_score = min(volatility * 10, 1.0)
        
        # Calculate volume spike
        volume_ma = np.mean(volume[-20:])
        volume_spike = volume[-1] / volume_ma if volume_ma > 0 else 1
        volume_score = min(volume_spike / 2, 1.0)
        
        # Combined attention
        attention = (volatility_score * 0.5 + volume_score * 0.5)
        
        return max(0, min(1, attention))
    
    def _calculate_memory_retention(self, close: np.ndarray) -> float:
        """
        Calculate memory retention.
        
        Args:
            close: Close prices
            
        Returns:
            Memory retention score (0-1)
        """
        if len(close) < 50:
            return 0.5
        
        # Calculate trend persistence
        returns = np.diff(np.log(close))
        autocorrelation = np.corrcoef(returns[:-1], returns[1:])[0, 1]
        
        # Memory retention based on autocorrelation
        memory = (autocorrelation + 1) / 2
        
        return max(0, min(1, memory))
    
    def _calculate_learning_rate(self, close: np.ndarray) -> float:
        """
        Calculate learning rate.
        
        Args:
            close: Close prices
            
        Returns:
            Learning rate (0-1)
        """
        if len(close) < 20:
            return 0.5
        
        # Calculate how quickly the market adapts to new patterns
        returns = np.diff(np.log(close))
        
        # Calculate rolling volatility
        vol_window = 10
        rolling_vol = []
        
        for i in range(vol_window, len(returns)):
            rolling_vol.append(np.std(returns[i-vol_window:i]))
        
        if len(rolling_vol) < 2:
            return 0.5
        
        # Learning rate based on volatility adaptation
        vol_change = np.diff(rolling_vol)
        adaptation = np.mean(np.abs(vol_change) / (np.array(rolling_vol[:-1]) + 1e-10))
        
        learning = 1 - min(adaptation, 1.0)
        
        return max(0, min(1, learning))
    
    def _calculate_pattern_recognition(self, close: np.ndarray) -> float:
        """
        Calculate pattern recognition score.
        
        Args:
            close: Close prices
            
        Returns:
            Pattern recognition score (0-1)
        """
        if len(close) < 30:
            return 0.5
        
        # Detect simple patterns
        patterns_found = 0
        total_patterns = 0
        
        # Check for support/resistance
        for i in range(1, len(close)-1):
            # Simple support/resistance detection
            if (close[i] > close[i-1] and close[i] > close[i+1]):
                patterns_found += 1
            elif (close[i] < close[i-1] and close[i] < close[i+1]):
                patterns_found += 1
            total_patterns += 1
        
        if total_patterns == 0:
            return 0.5
        
        pattern_score = patterns_found / total_patterns
        
        return max(0, min(1, pattern_score))
    
    def _calculate_decision_confidence(self, close: np.ndarray) -> float:
        """
        Calculate decision confidence.
        
        Args:
            close: Close prices
            
        Returns:
            Decision confidence (0-1)
        """
        if len(close) < 20:
            return 0.5
        
        # Calculate trend strength
        slope, intercept = MathUtils.linear_regression(
            np.arange(20),
            close[-20:]
        )
        r2 = MathUtils.r_squared(np.arange(20), close[-20:])
        
        # Confidence based on trend strength and reliability
        trend_strength = min(abs(slope) * 10, 1.0)
        reliability = r2
        
        confidence = (trend_strength * 0.5 + reliability * 0.5)
        
        return max(0, min(1, confidence))
    
    def _calculate_adaptability(self, close: np.ndarray) -> float:
        """
        Calculate adaptability score.
        
        Args:
            close: Close prices
            
        Returns:
            Adaptability score (0-1)
        """
        if len(close) < 30:
            return 0.5
        
        # Calculate how quickly price adapts to new levels
        returns = np.diff(np.log(close))
        volatility = np.std(returns[-20:])
        
        # Adaptability based on volatility relative to historical
        historical_vol = np.std(returns[:-20]) if len(returns) > 20 else volatility
        
        if historical_vol == 0:
            return 0.5
        
        vol_ratio = volatility / historical_vol
        adaptability = 1 / (1 + vol_ratio)
        
        return max(0, min(1, adaptability))
    
    def _calculate_cognitive_load(self, close: np.ndarray) -> float:
        """
        Calculate cognitive load.
        
        Args:
            close: Close prices
            
        Returns:
            Cognitive load score (0-1)
        """
        if len(close) < 20:
            return 0.5
        
        # Calculate complexity of price movements
        returns = np.diff(np.log(close))
        
        # Entropy as measure of complexity
        hist, _ = np.histogram(returns, bins=10)
        hist = hist / len(returns)
        entropy = -np.sum(hist * np.log(hist + 1e-10))
        
        # Normalize entropy
        max_entropy = np.log(10)
        cognitive_load = entropy / max_entropy
        
        return max(0, min(1, cognitive_load))
    
    def _get_default_state(self) -> CognitiveState:
        """
        Get default cognitive state.
        
        Returns:
            Default CognitiveState object
        """
        return CognitiveState(
            timestamp=datetime.now(),
            attention_score=0.5,
            memory_retention=0.5,
            learning_rate=0.5,
            pattern_recognition=0.5,
            decision_confidence=0.5,
            adaptability=0.5,
            cognitive_load=0.5
        )
    
    def _generate_signals(self, df: pd.DataFrame,
                         state: CognitiveState) -> List[CognitiveSignal]:
        """
        Generate trading signals from cognitive state.
        
        Args:
            df: OHLCV data
            state: CognitiveState object
            
        Returns:
            List of CognitiveSignal objects
        """
        signals = []
        
        current_price = df['close'].iloc[-1]
        symbol = df.get('symbol', [''])[0] if 'symbol' in df.columns else ''
        
        # Check cognitive state for signal generation
        if state.decision_confidence < self.confidence_threshold:
            return signals
        
        # Determine signal based on cognitive metrics
        if state.pattern_recognition > 0.6 and state.attention_score > 0.5:
            signal_type = 'buy'
            reason = "Strong pattern recognition with high attention"
            confidence = state.decision_confidence
            target = current_price * 1.02
            stop_loss = current_price * 0.98
            
        elif state.pattern_recognition < 0.4 and state.attention_score > 0.5:
            signal_type = 'sell'
            reason = "Weak pattern recognition with high attention"
            confidence = state.decision_confidence
            target = current_price * 0.98
            stop_loss = current_price * 1.02
            
        else:
            return signals
        
        signals.append(CognitiveSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            cognitive_state=state,
            indicators={
                'attention': state.attention_score,
                'pattern_recognition': state.pattern_recognition,
                'cognitive_load': state.cognitive_load,
                'adaptability': state.adaptability
            }
        ))
        
        return signals
    
    def _get_status(self, state: CognitiveState) -> str:
        """
        Get status from cognitive state.
        
        Args:
            state: CognitiveState object
            
        Returns:
            Status string
        """
        if state.decision_confidence > 0.7 and state.attention_score > 0.6:
            return 'confident'
        elif state.decision_confidence < 0.4 or state.attention_score < 0.3:
            return 'uncertain'
        else:
            return 'neutral'
    
    def _get_market_character(self, df: pd.DataFrame,
                            state: CognitiveState) -> str:
        """
        Get market character description.
        
        Args:
            df: OHLCV data
            state: CognitiveState object
            
        Returns:
            Market character description
        """
        status = self._get_status(state)
        status_map = {
            'confident': 'High confidence market with strong patterns',
            'uncertain': 'Uncertain market with weak patterns',
            'neutral': 'Neutral market with moderate patterns'
        }
        
        return status_map.get(status, 'Unknown')
    
    def get_state_summary(self) -> Dict[str, Any]:
        """
        Get cognitive state summary.
        
        Returns:
            State summary
        """
        if not self.cognitive_state_history:
            return {'status': 'no_state'}
        
        latest = self.cognitive_state_history[-1]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'latest_state': latest,
            'average_confidence': np.mean([s.decision_confidence for s in self.cognitive_state_history]),
            'average_attention': np.mean([s.attention_score for s in self.cognitive_state_history]),
            'average_pattern_recognition': np.mean([s.pattern_recognition for s in self.cognitive_state_history]),
            'status': self._get_status(latest),
            'history_length': len(self.cognitive_state_history)
        }


def create_cognition_model(config: Optional[Dict[str, Any]] = None) -> CognitionModel:
    """
    Create a cognition model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        CognitionModel instance
    """
    return CognitionModel(config)


__all__ = [
    'CognitiveState',
    'CognitiveSignal',
    'CognitionModel',
    'create_cognition_model'
]
