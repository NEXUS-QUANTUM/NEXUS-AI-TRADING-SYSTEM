# trading/strategies/ai_ensemble.py
"""
NEXUS AI TRADING SYSTEM - AI Ensemble Strategy
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements an AI ensemble trading strategy that combines
multiple AI models and technical indicators to generate trading signals.
The ensemble uses a weighted voting system with dynamic weight adjustment
based on model performance.

Key Features:
- Multiple AI models (LSTM, Transformer, XGBoost, etc.)
- Dynamic weight allocation based on performance
- Confidence scoring
- Risk-aware position sizing
- Adaptive model selection
"""

import asyncio
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable, Awaitable
from collections import deque, defaultdict

import numpy as np
import pandas as pd

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType, TimeInForce
from shared.types.trading import Order, Position, Trade, MarketData
from shared.types.ai import ModelPrediction, ModelConfidence, ModelType
from .base import BaseStrategy, StrategyConfig, Signal, SignalType, SignalStrength

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class EnsembleMethod(str, Enum):
    """Ensemble combination methods"""
    WEIGHTED_VOTE = "weighted_vote"
    MAJORITY_VOTE = "majority_vote"
    AVERAGE = "average"
    STACKING = "stacking"
    BOOSTING = "boosting"
    BAGGING = "bagging"
    DYNAMIC = "dynamic"


class ModelWeightStrategy(str, Enum):
    """Strategies for model weight allocation"""
    EQUAL = "equal"
    PERFORMANCE_BASED = "performance_based"
    RECENCY_BASED = "recency_based"
    CONFIDENCE_BASED = "confidence_based"
    ADAPTIVE = "adaptive"
    OPTIMIZED = "optimized"


@dataclass
class EnsembleConfig:
    """Configuration for ensemble strategy"""
    method: EnsembleMethod = EnsembleMethod.DYNAMIC
    weight_strategy: ModelWeightStrategy = ModelWeightStrategy.ADAPTIVE
    min_models_required: int = 2
    max_models: int = 10
    confidence_threshold: float = 0.6
    signal_threshold: float = 0.5
    rebalance_interval: int = 100  # Number of predictions between rebalancing
    performance_window: int = 100  # Window for performance tracking
    decay_factor: float = 0.95  # Decay factor for historical performance
    enable_adaptive_weights: bool = True
    min_weight: float = 0.05
    max_weight: float = 0.5
    fallback_to_best: bool = True
    use_confidence: bool = True


@dataclass
class ModelPerformance:
    """Performance tracking for a model"""
    model_id: str
    model_type: ModelType
    total_predictions: int = 0
    correct_predictions: int = 0
    accuracy: float = 0.0
    weight: float = 1.0
    confidence_avg: float = 0.0
    latency_avg: float = 0.0
    last_prediction: Optional[datetime] = None
    performance_history: deque = field(default_factory=lambda: deque(maxlen=100))
    weight_history: deque = field(default_factory=lambda: deque(maxlen=50))
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 1.0
    max_drawdown: float = 0.0


@dataclass
class EnsemblePrediction:
    """Prediction from the ensemble"""
    model_predictions: List[ModelPrediction]
    ensemble_signal: Signal
    confidence: float
    weight_distribution: Dict[str, float]
    method_used: EnsembleMethod
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# AI ENSEMBLE STRATEGY
# ============================================================================

class AIEnsembleStrategy(BaseStrategy):
    """
    AI Ensemble Trading Strategy.
    
    Combines multiple AI models to generate robust trading signals.
    Uses dynamic weighting based on model performance and confidence.
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        ensemble_config: Optional[EnsembleConfig] = None,
    ):
        """
        Initialize the ensemble strategy.
        
        Args:
            config: Strategy configuration
            ensemble_config: Ensemble configuration
        """
        super().__init__(config)
        self.ensemble_config = ensemble_config or EnsembleConfig()
        
        # Model registry
        self._models: Dict[str, Any] = {}
        self._model_performance: Dict[str, ModelPerformance] = {}
        self._model_weights: Dict[str, float] = {}
        
        # Prediction history
        self._prediction_history: deque = deque(maxlen=1000)
        self._signal_history: deque = deque(maxlen=500)
        
        # Performance tracking
        self._ensemble_performance = {
            "total_predictions": 0,
            "correct_predictions": 0,
            "accuracy": 0.0,
            "sharpe_ratio": 0.0,
            "win_rate": 0.0,
            "profit_factor": 1.0,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Last predictions
        self._last_prediction: Optional[EnsemblePrediction] = None
        self._last_signal: Optional[Signal] = None
        
        self.logger = logger
    
    # ========================================================================
    # MODEL MANAGEMENT
    # ========================================================================
    
    def register_model(
        self,
        model_id: str,
        model: Any,
        model_type: ModelType,
        initial_weight: Optional[float] = None,
    ) -> None:
        """
        Register a model with the ensemble.
        
        Args:
            model_id: Unique model identifier
            model: Model instance
            model_type: Type of model
            initial_weight: Initial weight (default: equal distribution)
        """
        if model_id in self._models:
            self.logger.warning(f"Model {model_id} already registered, overwriting")
        
        self._models[model_id] = model
        
        # Initialize performance tracking
        performance = ModelPerformance(
            model_id=model_id,
            model_type=model_type,
            weight=initial_weight or 1.0,
        )
        self._model_performance[model_id] = performance
        
        # Initialize weight
        if initial_weight is None:
            self._model_weights[model_id] = 1.0
        else:
            self._model_weights[model_id] = initial_weight
        
        self.logger.info(f"Registered model {model_id} ({model_type.value})")
        
        # Rebalance weights after adding a model
        if self.ensemble_config.enable_adaptive_weights:
            self._rebalance_weights()
    
    def unregister_model(self, model_id: str) -> bool:
        """
        Unregister a model from the ensemble.
        
        Args:
            model_id: Model identifier
            
        Returns:
            bool: True if model was unregistered
        """
        if model_id not in self._models:
            return False
        
        del self._models[model_id]
        del self._model_performance[model_id]
        del self._model_weights[model_id]
        
        self.logger.info(f"Unregistered model {model_id}")
        return True
    
    def get_models(self) -> List[str]:
        """
        Get list of registered models.
        
        Returns:
            List[str]: List of model IDs
        """
        return list(self._models.keys())
    
    def get_model_performance(self, model_id: str) -> Optional[ModelPerformance]:
        """
        Get performance metrics for a model.
        
        Args:
            model_id: Model identifier
            
        Returns:
            Optional[ModelPerformance]: Performance metrics
        """
        return self._model_performance.get(model_id)
    
    def get_all_performance(self) -> Dict[str, ModelPerformance]:
        """
        Get performance metrics for all models.
        
        Returns:
            Dict[str, ModelPerformance]: Performance by model ID
        """
        return dict(self._model_performance)
    
    # ========================================================================
    # WEIGHT MANAGEMENT
    # ========================================================================
    
    def _rebalance_weights(self) -> None:
        """
        Rebalance model weights based on the configured strategy.
        """
        if not self._models:
            return
        
        # Get model IDs
        model_ids = list(self._models.keys())
        
        if self.ensemble_config.weight_strategy == ModelWeightStrategy.EQUAL:
            # Equal weights
            weight = 1.0 / len(model_ids)
            for model_id in model_ids:
                self._model_weights[model_id] = weight
        
        elif self.ensemble_config.weight_strategy == ModelWeightStrategy.PERFORMANCE_BASED:
            # Based on historical performance
            performances = []
            for model_id in model_ids:
                perf = self._model_performance[model_id]
                score = perf.accuracy * 0.5 + perf.win_rate * 0.3 + perf.profit_factor * 0.2
                performances.append((model_id, max(0.01, score)))
            
            total = sum(score for _, score in performances)
            if total > 0:
                for model_id, score in performances:
                    self._model_weights[model_id] = score / total
        
        elif self.ensemble_config.weight_strategy == ModelWeightStrategy.CONFIDENCE_BASED:
            # Based on average confidence
            confidences = []
            for model_id in model_ids:
                perf = self._model_performance[model_id]
                conf = max(0.1, perf.confidence_avg)
                confidences.append((model_id, conf))
            
            total = sum(conf for _, conf in confidences)
            if total > 0:
                for model_id, conf in confidences:
                    self._model_weights[model_id] = conf / total
        
        elif self.ensemble_config.weight_strategy == ModelWeightStrategy.RECENCY_BASED:
            # Based on recent performance
            for model_id in model_ids:
                perf = self._model_performance[model_id]
                history = list(perf.performance_history)
                if history:
                    # Weight recent results more heavily
                    weights = [self.ensemble_config.decay_factor ** i for i in range(len(history))]
                    weighted_score = sum(h * w for h, w in zip(history, reversed(weights)))
                    self._model_weights[model_id] = max(0.01, weighted_score)
                else:
                    self._model_weights[model_id] = 1.0
            
            total = sum(self._model_weights.values())
            if total > 0:
                for model_id in model_ids:
                    self._model_weights[model_id] /= total
        
        elif self.ensemble_config.weight_strategy == ModelWeightStrategy.ADAPTIVE:
            # Combine multiple factors
            for model_id in model_ids:
                perf = self._model_performance[model_id]
                
                # Performance score
                perf_score = perf.accuracy * 0.35 + perf.win_rate * 0.25 + perf.profit_factor * 0.15
                
                # Confidence score
                conf_score = min(1.0, perf.confidence_avg / 0.7) * 0.25
                
                # Recency score
                recency_score = 0.0
                history = list(perf.performance_history)
                if history:
                    recent = sum(history[-10:]) / min(len(history), 10)
                    recency_score = recent * 0.15
                
                self._model_weights[model_id] = max(0.01, perf_score + conf_score + recency_score)
            
            total = sum(self._model_weights.values())
            if total > 0:
                for model_id in model_ids:
                    self._model_weights[model_id] /= total
        
        elif self.ensemble_config.weight_strategy == ModelWeightStrategy.OPTIMIZED:
            # Optimize weights (placeholder - would require backtesting)
            # For now, use performance-based as fallback
            self._rebalance_weights()
        
        # Apply min/max constraints
        for model_id in model_ids:
            weight = self._model_weights[model_id]
            weight = max(self.ensemble_config.min_weight, weight)
            weight = min(self.ensemble_config.max_weight, weight)
            self._model_weights[model_id] = weight
        
        # Normalize after constraints
        total = sum(self._model_weights.values())
        if total > 0:
            for model_id in model_ids:
                self._model_weights[model_id] /= total
        
        # Update performance records
        for model_id in model_ids:
            self._model_performance[model_id].weight = self._model_weights[model_id]
            self._model_performance[model_id].weight_history.append(self._model_weights[model_id])
    
    def get_weights(self) -> Dict[str, float]:
        """
        Get current model weights.
        
        Returns:
            Dict[str, float]: Weights by model ID
        """
        return dict(self._model_weights)
    
    def set_weights(self, weights: Dict[str, float]) -> None:
        """
        Manually set model weights.
        
        Args:
            weights: Weights by model ID
        """
        total = sum(weights.values())
        if total == 0:
            raise ValueError("Total weight must be greater than 0")
        
        self._model_weights = {k: v / total for k, v in weights.items()}
        self.logger.info("Manually set model weights")
    
    # ========================================================================
    # PREDICTION AND SIGNAL GENERATION
    # ========================================================================
    
    async def _predict_models(
        self,
        market_data: List[MarketData],
        features: Optional[pd.DataFrame] = None,
    ) -> List[ModelPrediction]:
        """
        Get predictions from all models.
        
        Args:
            market_data: Market data for prediction
            features: Optional precomputed features
            
        Returns:
            List[ModelPrediction]: Model predictions
        """
        predictions = []
        
        for model_id, model in self._models.items():
            try:
                # Get prediction from model
                if hasattr(model, "predict_async"):
                    prediction = await model.predict_async(market_data, features)
                elif hasattr(model, "predict"):
                    prediction = model.predict(market_data, features)
                else:
                    raise ValueError(f"Model {model_id} has no predict method")
                
                # Convert to ModelPrediction if needed
                if not isinstance(prediction, ModelPrediction):
                    prediction = self._convert_to_prediction(model_id, prediction)
                
                predictions.append(prediction)
                
                # Update performance
                if model_id in self._model_performance:
                    perf = self._model_performance[model_id]
                    perf.total_predictions += 1
                    perf.last_prediction = datetime.utcnow()
                    
            except Exception as e:
                self.logger.error(f"Model {model_id} prediction failed: {e}")
                # Continue with other models
        
        return predictions
    
    def _convert_to_prediction(
        self,
        model_id: str,
        raw_prediction: Any,
    ) -> ModelPrediction:
        """
        Convert raw model output to ModelPrediction.
        
        Args:
            model_id: Model identifier
            raw_prediction: Raw prediction output
            
        Returns:
            ModelPrediction: Standardized prediction
        """
        # If it's already a dict
        if isinstance(raw_prediction, dict):
            return ModelPrediction(
                model_id=model_id,
                model_type=self._model_performance.get(model_id, ModelPerformance(
                    model_id=model_id,
                    model_type=ModelType.CUSTOM,
                )).model_type,
                prediction=raw_prediction.get("prediction", 0.0),
                confidence=raw_prediction.get("confidence", 0.5),
                metadata=raw_prediction,
            )
        
        # If it's a tuple/list of (prediction, confidence)
        if isinstance(raw_prediction, (tuple, list)) and len(raw_prediction) >= 2:
            return ModelPrediction(
                model_id=model_id,
                model_type=self._model_performance.get(model_id, ModelPerformance(
                    model_id=model_id,
                    model_type=ModelType.CUSTOM,
                )).model_type,
                prediction=float(raw_prediction[0]),
                confidence=float(raw_prediction[1]),
            )
        
        # If it's just a number
        if isinstance(raw_prediction, (int, float)):
            return ModelPrediction(
                model_id=model_id,
                model_type=self._model_performance.get(model_id, ModelPerformance(
                    model_id=model_id,
                    model_type=ModelType.CUSTOM,
                )).model_type,
                prediction=float(raw_prediction),
                confidence=0.5,
            )
        
        # Fallback
        return ModelPrediction(
            model_id=model_id,
            model_type=self._model_performance.get(model_id, ModelPerformance(
                model_id=model_id,
                model_type=ModelType.CUSTOM,
            )).model_type,
            prediction=0.0,
            confidence=0.5,
            metadata={"raw": str(raw_prediction)},
        )
    
    async def _combine_predictions(
        self,
        predictions: List[ModelPrediction],
    ) -> Tuple[float, float, Dict[str, float]]:
        """
        Combine predictions using the ensemble method.
        
        Args:
            predictions: List of model predictions
            
        Returns:
            Tuple[float, float, Dict[str, float]]: (combined_value, confidence, weights_used)
        """
        if not predictions:
            return 0.0, 0.0, {}
        
        method = self.ensemble_config.method
        
        if method == EnsembleMethod.WEIGHTED_VOTE:
            return self._weighted_vote(predictions)
        elif method == EnsembleMethod.MAJORITY_VOTE:
            return self._majority_vote(predictions)
        elif method == EnsembleMethod.AVERAGE:
            return self._average(predictions)
        elif method == EnsembleMethod.STACKING:
            return self._stacking(predictions)
        elif method == EnsembleMethod.DYNAMIC:
            return self._dynamic_combine(predictions)
        else:
            # Fallback to weighted vote
            return self._weighted_vote(predictions)
    
    def _weighted_vote(
        self,
        predictions: List[ModelPrediction],
    ) -> Tuple[float, float, Dict[str, float]]:
        """
        Weighted voting combination.
        
        Args:
            predictions: List of predictions
            
        Returns:
            Tuple: (combined_value, confidence, weights_used)
        """
        total_weight = 0.0
        weighted_sum = 0.0
        weighted_confidence = 0.0
        weights_used = {}
        
        for pred in predictions:
            weight = self._model_weights.get(pred.model_id, 1.0 / len(predictions))
            weights_used[pred.model_id] = weight
            
            value = pred.prediction
            confidence = pred.confidence if self.ensemble_config.use_confidence else 1.0
            
            # Apply confidence weighting
            effective_weight = weight * confidence
            
            weighted_sum += value * effective_weight
            weighted_confidence += confidence * effective_weight
            total_weight += effective_weight
        
        if total_weight == 0:
            return 0.0, 0.0, weights_used
        
        combined = weighted_sum / total_weight
        confidence = weighted_confidence / total_weight
        
        # Normalize confidence to [0, 1]
        confidence = min(1.0, max(0.0, confidence))
        
        return combined, confidence, weights_used
    
    def _majority_vote(
        self,
        predictions: List[ModelPrediction],
    ) -> Tuple[float, float, Dict[str, float]]:
        """
        Majority vote combination.
        
        Args:
            predictions: List of predictions
            
        Returns:
            Tuple: (combined_value, confidence, weights_used)
        """
        # Count votes for buy/sell/neutral
        votes = {"buy": 0, "sell": 0, "neutral": 0}
        
        for pred in predictions:
            signal_type = pred.prediction
            if signal_type > 0.3:
                votes["buy"] += 1
            elif signal_type < -0.3:
                votes["sell"] += 1
            else:
                votes["neutral"] += 1
        
        # Determine majority
        total = len(predictions)
        if votes["buy"] > total / 2:
            combined = 1.0
            confidence = votes["buy"] / total
        elif votes["sell"] > total / 2:
            combined = -1.0
            confidence = votes["sell"] / total
        else:
            combined = 0.0
            confidence = max(votes["buy"], votes["sell"]) / total
        
        # Equal weights for all
        weights_used = {p.model_id: 1.0 / len(predictions) for p in predictions}
        
        return combined, confidence, weights_used
    
    def _average(
        self,
        predictions: List[ModelPrediction],
    ) -> Tuple[float, float, Dict[str, float]]:
        """
        Simple average combination.
        
        Args:
            predictions: List of predictions
            
        Returns:
            Tuple: (combined_value, confidence, weights_used)
        """
        if not predictions:
            return 0.0, 0.0, {}
        
        total_value = sum(p.prediction for p in predictions)
        total_confidence = sum(p.confidence for p in predictions)
        
        n = len(predictions)
        combined = total_value / n
        confidence = total_confidence / n
        
        weights_used = {p.model_id: 1.0 / n for p in predictions}
        
        return combined, confidence, weights_used
    
    def _stacking(
        self,
        predictions: List[ModelPrediction],
    ) -> Tuple[float, float, Dict[str, float]]:
        """
        Stacking combination (meta-model).
        
        Args:
            predictions: List of predictions
            
        Returns:
            Tuple: (combined_value, confidence, weights_used)
        """
        # Simple stacking: use weighted vote with performance-based weights
        # In a real implementation, this would use a meta-model
        return self._weighted_vote(predictions)
    
    def _dynamic_combine(
        self,
        predictions: List[ModelPrediction],
    ) -> Tuple[float, float, Dict[str, float]]:
        """
        Dynamic combination that adapts based on conditions.
        
        Args:
            predictions: List of predictions
            
        Returns:
            Tuple: (combined_value, confidence, weights_used)
        """
        # Check consensus
        values = [p.prediction for p in predictions]
        avg = sum(values) / len(values)
        std = math.sqrt(sum((v - avg) ** 2 for v in values) / len(values)) if len(values) > 1 else 0
        
        # If high consensus, use average
        if std < 0.2:
            return self._average(predictions)
        
        # If predictions are diverse, use weighted vote
        return self._weighted_vote(predictions)
    
    # ========================================================================
    # SIGNAL GENERATION
    # ========================================================================
    
    async def generate_signal(
        self,
        market_data: List[MarketData],
        features: Optional[pd.DataFrame] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Signal]:
        """
        Generate a trading signal from the ensemble.
        
        Args:
            market_data: Market data for prediction
            features: Optional precomputed features
            context: Additional context
            
        Returns:
            Optional[Signal]: Generated signal
        """
        if len(self._models) < self.ensemble_config.min_models_required:
            self.logger.warning(
                f"Insufficient models ({len(self._models)} < {self.ensemble_config.min_models_required})"
            )
            return None
        
        # Get predictions from all models
        predictions = await self._predict_models(market_data, features)
        
        if len(predictions) < self.ensemble_config.min_models_required:
            self.logger.warning(
                f"Insufficient predictions ({len(predictions)} < {self.ensemble_config.min_models_required})"
            )
            return None
        
        # Combine predictions
        combined_value, confidence, weights_used = await self._combine_predictions(predictions)
        
        # Check confidence threshold
        if confidence < self.ensemble_config.confidence_threshold:
            self.logger.debug(f"Confidence {confidence:.2f} below threshold {self.ensemble_config.confidence_threshold}")
            return None
        
        # Determine signal type and strength
        signal_type = SignalType.NEUTRAL
        strength = SignalStrength.MEDIUM
        
        if combined_value > self.ensemble_config.signal_threshold:
            signal_type = SignalType.BUY
            if combined_value > 0.7:
                strength = SignalStrength.STRONG
            elif combined_value > 0.5:
                strength = SignalStrength.MEDIUM
            else:
                strength = SignalStrength.WEAK
        elif combined_value < -self.ensemble_config.signal_threshold:
            signal_type = SignalType.SELL
            if combined_value < -0.7:
                strength = SignalStrength.STRONG
            elif combined_value < -0.5:
                strength = SignalStrength.MEDIUM
            else:
                strength = SignalStrength.WEAK
        
        # Skip neutral signals
        if signal_type == SignalType.NEUTRAL:
            return None
        
        # Create signal
        signal = Signal(
            symbol=market_data[-1].symbol if market_data else "",
            signal_type=signal_type,
            strength=strength,
            confidence=confidence,
            price=market_data[-1].last if market_data else 0,
            timestamp=datetime.utcnow(),
            metadata={
                "ensemble_method": self.ensemble_config.method.value,
                "model_count": len(predictions),
                "combined_value": combined_value,
                "weights_used": weights_used,
                "model_predictions": [
                    {
                        "model_id": p.model_id,
                        "model_type": p.model_type.value,
                        "prediction": p.prediction,
                        "confidence": p.confidence,
                    }
                    for p in predictions
                ],
            },
        )
        
        # Update ensemble prediction
        ensemble_prediction = EnsemblePrediction(
            model_predictions=predictions,
            ensemble_signal=signal,
            confidence=confidence,
            weight_distribution=weights_used,
            method_used=self.ensemble_config.method,
            metadata=context or {},
        )
        
        self._last_prediction = ensemble_prediction
        self._last_signal = signal
        
        # Update performance history
        self._prediction_history.append(ensemble_prediction)
        self._signal_history.append(signal)
        
        self._ensemble_performance["total_predictions"] += 1
        
        # Rebalance weights periodically
        if self._ensemble_performance["total_predictions"] % self.ensemble_config.rebalance_interval == 0:
            self._rebalance_weights()
        
        return signal
    
    # ========================================================================
    # PERFORMANCE UPDATE
    # ========================================================================
    
    async def update_performance(
        self,
        trade: Trade,
        signal: Signal,
    ) -> None:
        """
        Update performance metrics based on trade outcome.
        
        Args:
            trade: Completed trade
            signal: Signal that generated the trade
        """
        # Determine if trade was profitable
        profit = trade.pnl if hasattr(trade, "pnl") else 0
        is_profit = profit > 0
        
        # Update each model's performance
        if signal.metadata and "model_predictions" in signal.metadata:
            for pred_info in signal.metadata["model_predictions"]:
                model_id = pred_info.get("model_id")
                if not model_id or model_id not in self._model_performance:
                    continue
                
                perf = self._model_performance[model_id]
                perf.correct_predictions += 1 if is_profit else 0
                
                # Update accuracy
                perf.accuracy = perf.correct_predictions / max(1, perf.total_predictions)
                
                # Update win rate
                recent_trades = list(perf.performance_history)[-20:] if perf.performance_history else []
                if recent_trades:
                    perf.win_rate = sum(1 for t in recent_trades if t > 0) / len(recent_trades)
                
                # Store performance history
                perf.performance_history.append(1.0 if is_profit else 0.0)
        
        # Update ensemble performance
        self._ensemble_performance["correct_predictions"] += 1 if is_profit else 0
        self._ensemble_performance["accuracy"] = (
            self._ensemble_performance["correct_predictions"] /
            max(1, self._ensemble_performance["total_predictions"])
        )
        
        # Rebalance weights based on performance
        if self.ensemble_config.enable_adaptive_weights:
            self._rebalance_weights()
    
    # ========================================================================
    # POSITION SIZING
    # ========================================================================
    
    def calculate_position_size(
        self,
        signal: Signal,
        account_balance: float,
        risk_percent: float = 1.0,
    ) -> float:
        """
        Calculate position size based on signal confidence.
        
        Args:
            signal: Trading signal
            account_balance: Account balance
            risk_percent: Risk percentage
            
        Returns:
            float: Position size
        """
        # Base position size
        base_size = account_balance * (risk_percent / 100)
        
        # Adjust based on confidence
        confidence_multiplier = max(0.5, signal.confidence)
        
        # Adjust based on signal strength
        strength_multiplier = {
            SignalStrength.WEAK: 0.5,
            SignalStrength.MEDIUM: 1.0,
            SignalStrength.STRONG: 1.5,
        }.get(signal.strength, 1.0)
        
        # Adjust based on ensemble confidence
        ensemble_multiplier = 1.0
        if self._last_prediction:
            ensemble_multiplier = max(0.5, min(2.0, self._last_prediction.confidence / 0.5))
        
        position_size = base_size * confidence_multiplier * strength_multiplier * ensemble_multiplier
        
        # Apply risk limits
        max_position = account_balance * 0.2  # Max 20% per position
        position_size = min(position_size, max_position)
        
        # Apply minimum position
        min_position = account_balance * 0.001  # Min 0.1%
        position_size = max(position_size, min_position)
        
        return position_size
    
    # ========================================================================
    # METRICS AND REPORTING
    # ========================================================================
    
    def get_ensemble_metrics(self) -> Dict[str, Any]:
        """
        Get ensemble performance metrics.
        
        Returns:
            Dict: Ensemble metrics
        """
        model_metrics = {}
        for model_id, perf in self._model_performance.items():
            model_metrics[model_id] = {
                "model_type": perf.model_type.value,
                "accuracy": perf.accuracy,
                "win_rate": perf.win_rate,
                "weight": perf.weight,
                "total_predictions": perf.total_predictions,
                "confidence_avg": perf.confidence_avg,
                "sharpe_ratio": perf.sharpe_ratio,
            }
        
        return {
            "ensemble": {
                "method": self.ensemble_config.method.value,
                "weight_strategy": self.ensemble_config.weight_strategy.value,
                "total_predictions": self._ensemble_performance["total_predictions"],
                "accuracy": self._ensemble_performance["accuracy"],
                "win_rate": self._ensemble_performance["win_rate"],
                "active_models": len(self._models),
                "min_models_required": self.ensemble_config.min_models_required,
            },
            "models": model_metrics,
            "weights": self._model_weights,
            "last_prediction": self._last_prediction.timestamp.isoformat() if self._last_prediction else None,
        }
    
    # ========================================================================
    # STRATEGY METHODS
    # ========================================================================
    
    async def on_start(self) -> None:
        """Called when the strategy starts."""
        self.logger.info(f"AI Ensemble Strategy started with {len(self._models)} models")
        self._rebalance_weights()
    
    async def on_stop(self) -> None:
        """Called when the strategy stops."""
        self.logger.info("AI Ensemble Strategy stopped")
    
    async def on_trade(self, trade: Trade) -> None:
        """
        Called when a trade is completed.
        
        Args:
            trade: Completed trade
        """
        # Find the signal that generated this trade
        if self._last_signal:
            await self.update_performance(trade, self._last_signal)
    
    async def on_position_update(self, position: Position) -> None:
        """
        Called when a position is updated.
        
        Args:
            position: Updated position
        """
        # Update stop loss/take profit if needed
        if position.side and position.entry_price > 0:
            # Update take profit based on ensemble confidence
            if self._last_signal and self._last_signal.confidence > 0.7:
                # Widen take profit for high confidence signals
                pass
    
    # ========================================================================
    # HELPERS
    # ========================================================================
    
    def get_model_ids(self) -> List[str]:
        """
        Get list of registered model IDs.
        
        Returns:
            List[str]: Model IDs
        """
        return list(self._models.keys())
    
    def get_model_count(self) -> int:
        """
        Get number of registered models.
        
        Returns:
            int: Number of models
        """
        return len(self._models)
    
    def is_ready(self) -> bool:
        """
        Check if the strategy is ready to generate signals.
        
        Returns:
            bool: True if ready
        """
        return len(self._models) >= self.ensemble_config.min_models_required


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "EnsembleMethod",
    "ModelWeightStrategy",
    
    # Models
    "EnsembleConfig",
    "ModelPerformance",
    "EnsemblePrediction",
    
    # Strategy
    "AIEnsembleStrategy",
]
