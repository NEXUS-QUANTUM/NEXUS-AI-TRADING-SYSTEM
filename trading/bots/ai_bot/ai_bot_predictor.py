# trading/bots/ai_bot/ai_bot_predictor.py
# NEXUS AI TRADING SYSTEM - AI Bot Predictor
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
AI Bot Predictor for NEXUS AI Trading System.
Provides comprehensive prediction capabilities including:
- Multi-model prediction ensemble
- Real-time prediction generation
- Prediction confidence scoring
- Prediction caching and optimization
- Multi-timeframe predictions
- Sentiment analysis integration
- Technical indicator-based predictions
- ML/DL model predictions
- Prediction validation and backtesting
- Prediction performance tracking
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from collections import deque, defaultdict

import numpy as np
import pandas as pd

# NEXUS Imports
from trading.bots.ai_bot.config.bot_configs import BotConfig
from trading.bots.ai_bot.data.data_storage import DataStorage
from trading.bots.ai_bot.metrics.metrics_engine import MetricsEngine
from trading.bots.ai_bot.models.model_factory import ModelFactory
from trading.bots.ai_bot.models.model_predictor import ModelPredictor
from trading.bots.ai_bot.feature_engine.feature_engineering_engine import FeatureEngineeringEngine
from shared.utilities.logger import get_logger
from shared.utilities.cache_utils import CacheManager

logger = get_logger("nexus.trading.bot.predictor")


# ============================================================================
# Enums & Constants
# ============================================================================

class PredictionType(str, Enum):
    """Prediction types."""
    PRICE = "price"
    DIRECTION = "direction"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    SENTIMENT = "sentiment"
    TREND = "trend"
    TURNING_POINT = "turning_point"
    RISK = "risk"
    CUSTOM = "custom"


class PredictionHorizon(str, Enum):
    """Prediction horizons."""
    SHORT = "short"      # Minutes to hours
    MEDIUM = "medium"    # Hours to days
    LONG = "long"        # Days to weeks
    VERY_LONG = "very_long"  # Weeks to months


class ConfidenceLevel(str, Enum):
    """Confidence levels."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class Prediction:
    """Prediction data."""
    prediction_id: str
    symbol: str
    prediction_type: PredictionType
    value: float
    confidence: float
    confidence_level: ConfidenceLevel
    horizon: PredictionHorizon
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    model_name: Optional[str] = None
    features: Dict[str, float] = field(default_factory=dict)
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    ensemble_predictions: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class PredictionSummary:
    """Prediction summary."""
    total_predictions: int
    by_type: Dict[str, int]
    by_horizon: Dict[str, int]
    by_confidence: Dict[str, int]
    average_confidence: float
    latest_predictions: List[Prediction]
    performance_metrics: Dict[str, float]
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ============================================================================
# AI Bot Predictor
# ============================================================================

class AIBotPredictor:
    """
    Advanced AI Bot Predictor for NEXUS AI Trading System.
    """

    def __init__(
        self,
        config: BotConfig,
        model_factory: ModelFactory,
        model_predictor: ModelPredictor,
        feature_engine: FeatureEngineeringEngine,
        data_storage: DataStorage,
        metrics_engine: MetricsEngine,
        cache_manager: CacheManager,
    ):
        """
        Initialize AI bot predictor.

        Args:
            config: Bot configuration
            model_factory: Model factory instance
            model_predictor: Model predictor instance
            feature_engine: Feature engineering engine
            data_storage: Data storage instance
            metrics_engine: Metrics engine instance
            cache_manager: Cache manager instance
        """
        self.config = config
        self.model_factory = model_factory
        self.model_predictor = model_predictor
        self.feature_engine = feature_engine
        self.data_storage = data_storage
        self.metrics_engine = metrics_engine
        self.cache_manager = cache_manager

        # Prediction storage
        self._predictions: Dict[str, Prediction] = {}
        self._prediction_history: deque = deque(maxlen=10000)
        self._active_predictions: Dict[str, Prediction] = {}

        # Model instances
        self._models: Dict[str, Any] = {}
        self._ensemble_weights: Dict[str, float] = {}

        # Performance metrics
        self._performance = {
            "predictions_generated": 0,
            "predictions_used": 0,
            "predictions_expired": 0,
            "average_confidence": 0.0,
            "accuracy": 0.0,
            "by_type": defaultdict(int),
            "by_horizon": defaultdict(int),
        }

        # Prediction cache
        self._prediction_cache: Dict[str, Tuple[Prediction, float]] = {}
        self._cache_ttl = config.get("prediction_cache_ttl", 60)

        # Prediction ID generation
        self._prediction_id_counter = 0

        # Event handlers
        self._event_handlers: Dict[str, List[Callable]] = {
            "prediction_generated": [],
            "prediction_updated": [],
            "prediction_expired": [],
        }

        # Initialize models
        self._initialize_models()

        logger.info(
            "AIBotPredictor initialized",
            extra={
                "models_loaded": len(self._models),
                "cache_ttl": self._cache_ttl,
            }
        )

    # ========================================================================
    # Model Initialization
    # ========================================================================

    def _initialize_models(self) -> None:
        """Initialize prediction models."""
        # Load models from configuration
        model_configs = self.config.get("models", {})

        for model_name, model_config in model_configs.items():
            try:
                model = self.model_factory.create_model(
                    model_type=model_config.get("type"),
                    **model_config.get("params", {}),
                )

                # Load pre-trained weights if available
                if model_config.get("weights_path"):
                    # Would load weights
                    pass

                self._models[model_name] = model

                # Set ensemble weight
                self._ensemble_weights[model_name] = model_config.get("weight", 1.0)

                logger.info(f"Model initialized: {model_name}")

            except Exception as e:
                logger.error(f"Error initializing model {model_name}: {e}")

        # Normalize ensemble weights
        total_weight = sum(self._ensemble_weights.values())
        if total_weight > 0:
            for name in self._ensemble_weights:
                self._ensemble_weights[name] /= total_weight

    # ========================================================================
    # Prediction Generation
    # ========================================================================

    async def generate_prediction(
        self,
        symbol: str,
        prediction_type: PredictionType,
        horizon: PredictionHorizon,
        data: pd.DataFrame,
        models: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Prediction]:
        """
        Generate a prediction.

        Args:
            symbol: Trading symbol
            prediction_type: Prediction type
            horizon: Prediction horizon
            data: Input data
            models: Specific models to use
            metadata: Additional metadata
            tags: Prediction tags

        Returns:
            Prediction or None
        """
        start_time = time.time()

        # Generate prediction ID
        self._prediction_id_counter += 1
        prediction_id = f"pred_{int(time.time() * 1000)}_{self._prediction_id_counter}"

        try:
            # Get features
            features = await self.feature_engine.compute_features(data)

            if features.empty:
                logger.warning(f"No features available for {symbol}")
                return None

            # Get models to use
            model_names = models or list(self._models.keys())

            if not model_names:
                logger.warning("No models available for prediction")
                return None

            # Generate predictions from each model
            model_predictions = []
            confidences = []

            for model_name in model_names:
                if model_name not in self._models:
                    continue

                try:
                    model = self._models[model_name]

                    # Generate prediction
                    pred_result = await self.model_predictor.predict(
                        model=model,
                        features=features,
                        prediction_type=prediction_type,
                    )

                    if pred_result and "value" in pred_result:
                        model_predictions.append({
                            "model": model_name,
                            "value": pred_result["value"],
                            "confidence": pred_result.get("confidence", 0.5),
                            "weight": self._ensemble_weights.get(model_name, 1.0),
                        })
                        confidences.append(pred_result.get("confidence", 0.5))

                except Exception as e:
                    logger.error(f"Error in model {model_name}: {e}")

            if not model_predictions:
                logger.warning(f"No predictions generated for {symbol}")
                return None

            # Ensemble predictions
            final_value, final_confidence = self._ensemble_predictions(
                model_predictions,
                prediction_type,
            )

            # Determine confidence level
            confidence_level = self._get_confidence_level(final_confidence)

            # Calculate range
            range_low, range_high = self._calculate_prediction_range(
                final_value,
                final_confidence,
                prediction_type,
                data,
            )

            # Create prediction
            prediction = Prediction(
                prediction_id=prediction_id,
                symbol=symbol,
                prediction_type=prediction_type,
                value=final_value,
                confidence=final_confidence,
                confidence_level=confidence_level,
                horizon=horizon,
                timestamp=datetime.utcnow(),
                expires_at=datetime.utcnow() + self._get_horizon_delta(horizon),
                metadata=metadata or {},
                features={k: float(v) for k, v in features.iloc[-1].items() if isinstance(v, (int, float))},
                range_low=range_low,
                range_high=range_high,
                ensemble_predictions=model_predictions,
                tags=tags or [],
                model_name="ensemble" if len(model_predictions) > 1 else model_predictions[0]["model"],
            )

            # Store prediction
            self._predictions[prediction_id] = prediction
            self._prediction_history.append(prediction)
            self._active_predictions[prediction_id] = prediction

            # Update performance
            self._performance["predictions_generated"] += 1
            self._performance["by_type"][prediction_type.value] += 1
            self._performance["by_horizon"][horizon.value] += 1
            self._performance["average_confidence"] = (
                (self._performance["average_confidence"] *
                 (self._performance["predictions_generated"] - 1) +
                 final_confidence) /
                self._performance["predictions_generated"]
            )

            # Cache prediction
            self._prediction_cache[prediction_id] = (prediction, time.time())

            # Update metrics
            await self.metrics_engine.collect_metrics({
                f"prediction_{prediction_type.value}": final_value,
                f"prediction_confidence_{prediction_type.value}": final_confidence,
                "predictions_total": 1,
            }, metadata={"symbol": symbol, "horizon": horizon.value})

            # Emit event
            self._emit_event("prediction_generated", prediction)

            # Log prediction
            logger.info(
                f"Prediction generated: {prediction_id} - {symbol} - "
                f"{prediction_type.value}: {final_value:.4f} (conf: {final_confidence:.2%})"
            )

            return prediction

        except Exception as e:
            logger.error(f"Error generating prediction: {e}")
            return None

    async def generate_batch_predictions(
        self,
        requests: List[Dict[str, Any]],
    ) -> List[Optional[Prediction]]:
        """
        Generate batch predictions.

        Args:
            requests: List of prediction requests

        Returns:
            List of Predictions
        """
        tasks = []

        for request in requests:
            task = self.generate_prediction(
                symbol=request["symbol"],
                prediction_type=request["prediction_type"],
                horizon=request["horizon"],
                data=request["data"],
                models=request.get("models"),
                metadata=request.get("metadata"),
                tags=request.get("tags"),
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        predictions = []
        for result in results:
            if isinstance(result, Prediction):
                predictions.append(result)

        logger.info(f"Generated {len(predictions)} batch predictions")
        return predictions

    # ========================================================================
    # Ensemble Methods
    # ========================================================================

    def _ensemble_predictions(
        self,
        predictions: List[Dict[str, Any]],
        prediction_type: PredictionType,
    ) -> Tuple[float, float]:
        """
        Ensemble predictions from multiple models.

        Args:
            predictions: List of model predictions
            prediction_type: Prediction type

        Returns:
            (final_value, final_confidence)
        """
        if not predictions:
            return 0.0, 0.0

        # For price predictions, use weighted average
        if prediction_type in [PredictionType.PRICE, PredictionType.VOLATILITY, PredictionType.VOLUME]:
            total_weight = sum(p.get("weight", 1.0) for p in predictions)
            weighted_value = sum(p["value"] * p.get("weight", 1.0) for p in predictions) / total_weight

            # Weighted confidence
            weighted_confidence = sum(
                p["confidence"] * p.get("weight", 1.0)
                for p in predictions
            ) / total_weight

            return weighted_value, weighted_confidence

        # For direction predictions, use majority voting
        elif prediction_type == PredictionType.DIRECTION:
            # Count directions
            directions = defaultdict(float)
            weights = defaultdict(float)

            for p in predictions:
                direction = "up" if p["value"] > 0 else "down"
                directions[direction] += p.get("weight", 1.0)
                weights[direction] += p.get("weight", 1.0) * p["confidence"]

            if directions["up"] > directions["down"]:
                final_value = 1.0  # Up
                final_confidence = weights["up"] / directions["up"] if directions["up"] > 0 else 0.5
            else:
                final_value = -1.0  # Down
                final_confidence = weights["down"] / directions["down"] if directions["down"] > 0 else 0.5

            return final_value, final_confidence

        # For other types
        else:
            # Average with weights
            total_weight = sum(p.get("weight", 1.0) for p in predictions)
            weighted_value = sum(p["value"] * p.get("weight", 1.0) for p in predictions) / total_weight
            weighted_confidence = sum(
                p["confidence"] * p.get("weight", 1.0)
                for p in predictions
            ) / total_weight

            return weighted_value, weighted_confidence

    # ========================================================================
    # Prediction Management
    # ========================================================================

    async def update_prediction(
        self,
        prediction_id: str,
        new_value: Optional[float] = None,
        new_confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update an existing prediction.

        Args:
            prediction_id: Prediction ID
            new_value: New prediction value
            new_confidence: New confidence
            metadata: Additional metadata

        Returns:
            True if updated successfully
        """
        prediction = self._predictions.get(prediction_id)

        if not prediction:
            logger.warning(f"Prediction not found: {prediction_id}")
            return False

        if new_value is not None:
            prediction.value = new_value

        if new_confidence is not None:
            prediction.confidence = new_confidence
            prediction.confidence_level = self._get_confidence_level(new_confidence)

        if metadata:
            prediction.metadata.update(metadata)

        self._emit_event("prediction_updated", prediction)

        # Update cache
        self._prediction_cache[prediction_id] = (prediction, time.time())

        logger.info(f"Prediction updated: {prediction_id}")
        return True

    async def expire_prediction(self, prediction_id: str) -> bool:
        """
        Expire a prediction.

        Args:
            prediction_id: Prediction ID

        Returns:
            True if expired successfully
        """
        prediction = self._predictions.get(prediction_id)

        if not prediction:
            logger.warning(f"Prediction not found: {prediction_id}")
            return False

        if prediction_id in self._active_predictions:
            del self._active_predictions[prediction_id]

        self._performance["predictions_expired"] += 1
        self._emit_event("prediction_expired", prediction)

        logger.info(f"Prediction expired: {prediction_id}")
        return True

    def get_prediction(self, prediction_id: str) -> Optional[Prediction]:
        """
        Get prediction by ID.

        Args:
            prediction_id: Prediction ID

        Returns:
            Prediction or None
        """
        return self._predictions.get(prediction_id)

    def get_predictions(
        self,
        symbol: Optional[str] = None,
        prediction_type: Optional[PredictionType] = None,
        horizon: Optional[PredictionHorizon] = None,
        min_confidence: float = 0.0,
        limit: int = 100,
    ) -> List[Prediction]:
        """
        Get predictions.

        Args:
            symbol: Filter by symbol
            prediction_type: Filter by type
            horizon: Filter by horizon
            min_confidence: Minimum confidence
            limit: Maximum number

        Returns:
            List of Prediction
        """
        predictions = list(self._predictions.values())

        if symbol:
            predictions = [p for p in predictions if p.symbol == symbol]

        if prediction_type:
            predictions = [p for p in predictions if p.prediction_type == prediction_type]

        if horizon:
            predictions = [p for p in predictions if p.horizon == horizon]

        if min_confidence > 0:
            predictions = [p for p in predictions if p.confidence >= min_confidence]

        return sorted(predictions, key=lambda p: p.timestamp, reverse=True)[:limit]

    def get_active_predictions(
        self,
        symbol: Optional[str] = None,
        prediction_type: Optional[PredictionType] = None,
    ) -> List[Prediction]:
        """
        Get active predictions.

        Args:
            symbol: Filter by symbol
            prediction_type: Filter by type

        Returns:
            List of Prediction
        """
        predictions = list(self._active_predictions.values())

        if symbol:
            predictions = [p for p in predictions if p.symbol == symbol]

        if prediction_type:
            predictions = [p for p in predictions if p.prediction_type == prediction_type]

        return sorted(predictions, key=lambda p: p.timestamp, reverse=True)

    def get_latest_prediction(
        self,
        symbol: str,
        prediction_type: PredictionType,
        horizon: PredictionHorizon,
    ) -> Optional[Prediction]:
        """
        Get latest prediction for criteria.

        Args:
            symbol: Symbol
            prediction_type: Prediction type
            horizon: Prediction horizon

        Returns:
            Prediction or None
        """
        predictions = self.get_predictions(
            symbol=symbol,
            prediction_type=prediction_type,
            horizon=horizon,
            limit=1,
        )
        return predictions[0] if predictions else None

    # ========================================================================
    # Prediction Validation
    # ========================================================================

    async def validate_prediction(
        self,
        prediction_id: str,
        actual_value: float,
    ) -> Dict[str, Any]:
        """
        Validate a prediction against actual value.

        Args:
            prediction_id: Prediction ID
            actual_value: Actual value

        Returns:
            Validation results
        """
        prediction = self._predictions.get(prediction_id)

        if not prediction:
            logger.warning(f"Prediction not found: {prediction_id}")
            return {"valid": False, "error": "Prediction not found"}

        # Calculate error
        error = abs(actual_value - prediction.value)
        percentage_error = (error / abs(actual_value)) * 100 if actual_value != 0 else 100

        # Check if within range
        in_range = False
        if prediction.range_low and prediction.range_high:
            in_range = prediction.range_low <= actual_value <= prediction.range_high

        # Determine accuracy
        is_accurate = error <= (abs(actual_value) * 0.02)  # Within 2%

        # Determine direction accuracy
        direction_correct = (actual_value - 0) * (prediction.value - 0) > 0

        # Update prediction
        prediction.metadata["validation"] = {
            "actual_value": actual_value,
            "error": error,
            "percentage_error": percentage_error,
            "in_range": in_range,
            "is_accurate": is_accurate,
            "direction_correct": direction_correct,
            "validated_at": datetime.utcnow().isoformat(),
        }

        # Update performance
        if is_accurate:
            self._performance["accuracy"] = (
                (self._performance["accuracy"] *
                 (self._performance["predictions_generated"] - 1) +
                 1) /
                self._performance["predictions_generated"]
            )

        # Update metrics
        await self.metrics_engine.collect_metrics({
            f"prediction_{prediction.prediction_type.value}_error": error,
            "prediction_accuracy": 1 if is_accurate else 0,
            "prediction_direction_accuracy": 1 if direction_correct else 0,
        }, metadata={"prediction_id": prediction_id})

        return {
            "valid": True,
            "error": error,
            "percentage_error": percentage_error,
            "in_range": in_range,
            "is_accurate": is_accurate,
            "direction_correct": direction_correct,
        }

    # ========================================================================
    # Prediction Summary
    # ========================================================================

    def get_prediction_summary(self) -> PredictionSummary:
        """
        Get prediction summary.

        Returns:
            PredictionSummary
        """
        all_predictions = list(self._predictions.values())

        # Count by type
        by_type = defaultdict(int)
        by_horizon = defaultdict(int)
        by_confidence = defaultdict(int)

        for p in all_predictions:
            by_type[p.prediction_type.value] += 1
            by_horizon[p.horizon.value] += 1
            by_confidence[p.confidence_level.value] += 1

        # Calculate average confidence
        avg_confidence = (
            sum(p.confidence for p in all_predictions) /
            len(all_predictions) if all_predictions else 0
        )

        # Get latest predictions
        latest = sorted(all_predictions, key=lambda p: p.timestamp, reverse=True)[:10]

        # Performance metrics
        performance_metrics = {
            "accuracy": self._performance["accuracy"],
            "average_confidence": avg_confidence,
            "predictions_generated": self._performance["predictions_generated"],
            "predictions_expired": self._performance["predictions_expired"],
        }

        return PredictionSummary(
            total_predictions=len(all_predictions),
            by_type=dict(by_type),
            by_horizon=dict(by_horizon),
            by_confidence=dict(by_confidence),
            average_confidence=avg_confidence,
            latest_predictions=latest,
            performance_metrics=performance_metrics,
            timestamp=datetime.utcnow(),
        )

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _get_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """
        Get confidence level from confidence score.

        Args:
            confidence: Confidence score (0-1)

        Returns:
            ConfidenceLevel
        """
        if confidence >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif confidence >= 0.75:
            return ConfidenceLevel.HIGH
        elif confidence >= 0.6:
            return ConfidenceLevel.MEDIUM
        elif confidence >= 0.4:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    def _calculate_prediction_range(
        self,
        value: float,
        confidence: float,
        prediction_type: PredictionType,
        data: pd.DataFrame,
    ) -> Tuple[float, float]:
        """
        Calculate prediction range.

        Args:
            value: Prediction value
            confidence: Confidence score
            prediction_type: Prediction type
            data: Input data

        Returns:
            (range_low, range_high)
        """
        if prediction_type == PredictionType.PRICE:
            # Calculate from historical volatility
            if "close" in data.columns:
                returns = data["close"].pct_change().dropna()
                volatility = returns.std() * np.sqrt(252)
                range_size = value * volatility * (1 - confidence) * 2
            else:
                range_size = value * 0.02 * (1 - confidence) * 2

        elif prediction_type == PredictionType.VOLATILITY:
            range_size = value * 0.2 * (1 - confidence) * 2

        elif prediction_type == PredictionType.VOLUME:
            range_size = value * 0.3 * (1 - confidence) * 2

        else:
            range_size = abs(value) * 0.1 * (1 - confidence) * 2

        return value - range_size / 2, value + range_size / 2

    def _get_horizon_delta(self, horizon: PredictionHorizon) -> timedelta:
        """
        Get time delta for horizon.

        Args:
            horizon: Prediction horizon

        Returns:
            timedelta
        """
        deltas = {
            PredictionHorizon.SHORT: timedelta(hours=1),
            PredictionHorizon.MEDIUM: timedelta(days=1),
            PredictionHorizon.LONG: timedelta(weeks=1),
            PredictionHorizon.VERY_LONG: timedelta(weeks=4),
        }
        return deltas.get(horizon, timedelta(days=1))

    # ========================================================================
    # Event System
    # ========================================================================

    def on(self, event: str, handler: Callable) -> None:
        """
        Register an event handler.

        Args:
            event: Event name
            handler: Event handler
        """
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    def off(self, event: str, handler: Callable) -> None:
        """
        Remove an event handler.

        Args:
            event: Event name
            handler: Event handler
        """
        if event in self._event_handlers and handler in self._event_handlers[event]:
            self._event_handlers[event].remove(handler)

    def _emit_event(self, event: str, data: Any) -> None:
        """
        Emit an event.

        Args:
            event: Event name
            data: Event data
        """
        if event in self._event_handlers:
            for handler in self._event_handlers[event]:
                try:
                    handler(data)
                except Exception as e:
                    logger.error(f"Error in event handler: {e}")

    # ========================================================================
    # Performance Metrics
    # ========================================================================

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.

        Returns:
            Performance metrics
        """
        return {
            **self._performance,
            "total_predictions": len(self._predictions),
            "active_predictions": len(self._active_predictions),
            "cached_predictions": len(self._prediction_cache),
            "by_type": dict(self._performance["by_type"]),
            "by_horizon": dict(self._performance["by_horizon"]),
        }

    def clear_cache(self) -> None:
        """Clear prediction cache."""
        self._prediction_cache.clear()
        logger.info("Prediction cache cleared")

    # ========================================================================
    # Persistence
    # ========================================================================

    async def save_predictions(self) -> bool:
        """
        Save predictions to storage.

        Returns:
            True if saved successfully
        """
        try:
            data = {
                "predictions": [
                    {
                        "prediction_id": p.prediction_id,
                        "symbol": p.symbol,
                        "prediction_type": p.prediction_type.value,
                        "value": p.value,
                        "confidence": p.confidence,
                        "confidence_level": p.confidence_level.value,
                        "horizon": p.horizon.value,
                        "timestamp": p.timestamp.isoformat(),
                        "expires_at": p.expires_at.isoformat() if p.expires_at else None,
                        "metadata": p.metadata,
                        "model_name": p.model_name,
                        "features": p.features,
                        "range_low": p.range_low,
                        "range_high": p.range_high,
                        "tags": p.tags,
                    }
                    for p in self._predictions.values()
                ],
                "active_predictions": [p.prediction_id for p in self._active_predictions.values()],
            }

            key = f"predictions:{datetime.utcnow().isoformat()}"
            return await self.data_storage.save_data(key, data)

        except Exception as e:
            logger.error(f"Error saving predictions: {e}")
            return False

    async def load_predictions(self) -> bool:
        """
        Load predictions from storage.

        Returns:
            True if loaded successfully
        """
        try:
            keys = await self.data_storage.list_keys("predictions:*")

            if not keys:
                return True

            latest_key = sorted(keys)[-1]
            data = await self.data_storage.load_data(latest_key)

            if not data:
                return True

            for pred_data in data.get("predictions", []):
                prediction = Prediction(
                    prediction_id=pred_data["prediction_id"],
                    symbol=pred_data["symbol"],
                    prediction_type=PredictionType(pred_data["prediction_type"]),
                    value=pred_data["value"],
                    confidence=pred_data["confidence"],
                    confidence_level=ConfidenceLevel(pred_data["confidence_level"]),
                    horizon=PredictionHorizon(pred_data["horizon"]),
                    timestamp=datetime.fromisoformat(pred_data["timestamp"]),
                    expires_at=datetime.fromisoformat(pred_data["expires_at"]) if pred_data.get("expires_at") else None,
                    metadata=pred_data.get("metadata", {}),
                    model_name=pred_data.get("model_name"),
                    features=pred_data.get("features", {}),
                    range_low=pred_data.get("range_low"),
                    range_high=pred_data.get("range_high"),
                    tags=pred_data.get("tags", []),
                )

                self._predictions[prediction.prediction_id] = prediction

                if prediction.expires_at is None or prediction.expires_at > datetime.utcnow():
                    self._active_predictions[prediction.prediction_id] = prediction

                self._prediction_history.append(prediction)

            logger.info(f"Loaded {len(self._predictions)} predictions")
            return True

        except Exception as e:
            logger.error(f"Error loading predictions: {e}")
            return False

    # ========================================================================
    # Lifecycle Management
    # ========================================================================

    async def start(self) -> None:
        """Start the predictor."""
        await self.load_predictions()

        # Start expiration cleanup task
        asyncio.create_task(self._cleanup_expired_predictions())

        logger.info("AIBotPredictor started")

    async def stop(self) -> None:
        """Stop the predictor."""
        await self.save_predictions()
        self.clear_cache()
        logger.info("AIBotPredictor stopped")

    async def _cleanup_expired_predictions(self) -> None:
        """Clean up expired predictions periodically."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                now = datetime.utcnow()
                expired = []

                for prediction_id, prediction in self._active_predictions.items():
                    if prediction.expires_at and prediction.expires_at < now:
                        expired.append(prediction_id)

                for prediction_id in expired:
                    await self.expire_prediction(prediction_id)

                if expired:
                    logger.info(f"Cleaned up {len(expired)} expired predictions")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)


# ============================================================================
# Factory Function
# ============================================================================

def create_ai_bot_predictor(
    config: BotConfig,
    model_factory: ModelFactory,
    model_predictor: ModelPredictor,
    feature_engine: FeatureEngineeringEngine,
    data_storage: DataStorage,
    metrics_engine: MetricsEngine,
    cache_manager: CacheManager,
) -> AIBotPredictor:
    """
    Factory function to create an AIBotPredictor instance.

    Args:
        config: Bot configuration
        model_factory: Model factory instance
        model_predictor: Model predictor instance
        feature_engine: Feature engineering engine
        data_storage: Data storage instance
        metrics_engine: Metrics engine instance
        cache_manager: Cache manager instance

    Returns:
        AIBotPredictor instance
    """
    return AIBotPredictor(
        config=config,
        model_factory=model_factory,
        model_predictor=model_predictor,
        feature_engine=feature_engine,
        data_storage=data_storage,
        metrics_engine=metrics_engine,
        cache_manager=cache_manager,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the AI bot predictor
    pass
