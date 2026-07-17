"""
NEXUS AI TRADING SYSTEM - Model Predictor
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced model prediction engine with real-time inference, batch processing,
prediction caching, and multi-model ensemble support.
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
from prometheus_client import Counter, Gauge, Histogram

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
PREDICTION_COUNTER = Counter(
    "nexus_predictions_total",
    "Total number of predictions made",
    ["model_type", "mode", "status"],
)
PREDICTION_DURATION = Histogram(
    "nexus_prediction_duration_seconds",
    "Duration of predictions",
    ["model_type", "mode"],
)
PREDICTION_CACHE_HITS = Counter(
    "nexus_prediction_cache_hits_total",
    "Total number of prediction cache hits",
    ["model_type"],
)
PREDICTION_ACCURACY = Gauge(
    "nexus_prediction_accuracy",
    "Current prediction accuracy",
    ["model_type"],
)
PREDICTION_LATENCY = Histogram(
    "nexus_prediction_latency_ms",
    "Prediction latency in milliseconds",
    ["model_type"],
)


class PredictionMode(Enum):
    """Prediction modes."""

    REAL_TIME = "realtime"
    BATCH = "batch"
    STREAMING = "streaming"
    ENSEMBLE = "ensemble"
    MULTI_MODEL = "multi_model"


class PredictionType(Enum):
    """Types of predictions."""

    PRICE = "price"
    DIRECTION = "direction"
    VOLATILITY = "volatility"
    SIGNAL = "signal"
    RISK = "risk"
    SENTIMENT = "sentiment"
    QUANTILE = "quantile"


@dataclass
class PredictionRequest:
    """Prediction request."""

    model_id: str
    input_data: Union[np.ndarray, torch.Tensor, Dict[str, Any]]
    prediction_type: PredictionType
    mode: PredictionMode = PredictionMode.REAL_TIME
    cache_key: Optional[str] = None
    ttl_seconds: int = 60
    batch_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PredictionResult:
    """Prediction result."""

    model_id: str
    prediction_type: PredictionType
    value: Any
    confidence: float
    timestamp: datetime
    inference_time_ms: float
    metadata: Dict[str, Any]
    is_cached: bool = False
    ensemble_members: Optional[List[Dict[str, Any]]] = None
    quantiles: Optional[Dict[str, float]] = None
    raw_outputs: Optional[Any] = None


class ModelPredictor:
    """
    Advanced model prediction engine with real-time and batch inference.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        model_loader: Optional[Any] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the model predictor.

        Args:
            config: Configuration dictionary
            model_loader: Model loader instance
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
        """
        self.config = config or {}
        self.model_loader = model_loader
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._lock = asyncio.Lock()
        self._batch_queue: deque = deque()
        self._batch_processor_task: Optional[asyncio.Task] = None
        self._prediction_history: Dict[str, List[PredictionResult]] = {}

        # Load configuration
        self.predictor_config = self.config.get("predictor", {})
        self.batch_size = self.predictor_config.get("batch_size", 32)
        self.max_batch_queue = self.predictor_config.get("max_batch_queue", 1000)
        self.batch_interval_seconds = self.predictor_config.get(
            "batch_interval_seconds", 0.1
        )
        self.default_confidence_threshold = self.predictor_config.get(
            "default_confidence_threshold", 0.5
        )
        self.cache_enabled = self.predictor_config.get("cache_enabled", True)
        self.history_size = self.predictor_config.get("history_size", 1000)

        # Initialize batch processor
        self._start_batch_processor()

        logger.info("ModelPredictor initialized with config: %s", config)

    def _start_batch_processor(self):
        """Start the batch processing loop."""
        if self._batch_processor_task is None or self._batch_processor_task.done():
            self._batch_processor_task = asyncio.create_task(
                self._process_batches()
            )
            logger.info("Batch processor started")

    async def _process_batches(self):
        """Process batches of prediction requests."""
        while True:
            try:
                if self._batch_queue:
                    # Collect batch
                    batch = []
                    batch_size = min(self.batch_size, len(self._batch_queue))

                    for _ in range(batch_size):
                        if self._batch_queue:
                            batch.append(self._batch_queue.popleft())

                    # Process batch
                    if batch:
                        await self._execute_batch_predictions(batch)

                # Small sleep to prevent busy waiting
                await asyncio.sleep(self.batch_interval_seconds)

            except Exception as e:
                logger.error(f"Error in batch processor: {e}")
                await asyncio.sleep(1)

    async def _execute_batch_predictions(self, batch: List[PredictionRequest]):
        """Execute batch predictions."""
        if not batch:
            return

        start_time = time.time()

        try:
            # Group by model ID
            grouped = {}
            for request in batch:
                if request.model_id not in grouped:
                    grouped[request.model_id] = []
                grouped[request.model_id].append(request)

            # Process each model group
            for model_id, requests in grouped.items():
                try:
                    # Load model
                    model, metadata = await self.model_loader.load_model(model_id)

                    # Prepare batch input
                    batch_inputs = []
                    for req in requests:
                        input_data = self._prepare_input(req.input_data)
                        batch_inputs.append(input_data)

                    # Stack inputs
                    if len(batch_inputs) > 1:
                        stacked_input = np.stack(batch_inputs, axis=0)
                    else:
                        stacked_input = batch_inputs[0]

                    # Convert to tensor
                    input_tensor = torch.tensor(stacked_input, dtype=torch.float32)

                    # Perform inference
                    with torch.no_grad():
                        if hasattr(model, "predict"):
                            outputs = model.predict(input_tensor)
                        else:
                            outputs = model(input_tensor)

                    if isinstance(outputs, torch.Tensor):
                        outputs = outputs.cpu().numpy()

                    # Process results
                    for i, request in enumerate(requests):
                        if len(outputs.shape) > 1:
                            output = outputs[i]
                        else:
                            output = outputs

                        # Get confidence
                        confidence = self._calculate_confidence(
                            output, request.prediction_type
                        )

                        result = PredictionResult(
                            model_id=model_id,
                            prediction_type=request.prediction_type,
                            value=output,
                            confidence=confidence,
                            timestamp=datetime.utcnow(),
                            inference_time_ms=(
                                (time.time() - start_time) * 1000
                            ) / len(batch),
                            metadata=request.metadata,
                            is_cached=False,
                        )

                        # Store history
                        await self._store_prediction_history(result)

                        # Return result via callback if provided
                        if "callback" in request.metadata:
                            callback = request.metadata["callback"]
                            if asyncio.iscoroutinefunction(callback):
                                await callback(result)
                            else:
                                callback(result)

                except Exception as e:
                    logger.error(f"Error processing batch for model {model_id}: {e}")
                    # Return error results
                    for request in requests:
                        error_result = PredictionResult(
                            model_id=model_id,
                            prediction_type=request.prediction_type,
                            value=None,
                            confidence=0.0,
                            timestamp=datetime.utcnow(),
                            inference_time_ms=0.0,
                            metadata={"error": str(e), **request.metadata},
                            is_cached=False,
                        )
                        if "callback" in request.metadata:
                            callback = request.metadata["callback"]
                            if asyncio.iscoroutinefunction(callback):
                                await callback(error_result)
                            else:
                                callback(error_result)

        except Exception as e:
            logger.error(f"Error in batch execution: {e}")

    async def predict(
        self,
        request: PredictionRequest,
    ) -> PredictionResult:
        """
        Perform a prediction.

        Args:
            request: Prediction request

        Returns:
            Prediction result
        """
        start_time = time.time()

        # Check cache
        if self.cache_enabled and request.cache_key:
            cached = await self._get_cached_prediction(request.cache_key)
            if cached:
                PREDICTION_CACHE_HITS.labels(
                    model_type=request.model_id.split("_")[0] if "_" in request.model_id else "unknown"
                ).inc()
                return cached

        try:
            # Load model
            model, metadata = await self.model_loader.load_model(request.model_id)

            # Prepare input
            input_data = self._prepare_input(request.input_data)

            # Convert to tensor if needed
            if not isinstance(input_data, torch.Tensor):
                input_tensor = torch.tensor(input_data, dtype=torch.float32)
            else:
                input_tensor = input_data

            # Add batch dimension if needed
            if len(input_tensor.shape) == 1:
                input_tensor = input_tensor.unsqueeze(0)

            # Perform inference
            inference_start = time.time()

            with torch.no_grad():
                if hasattr(model, "predict"):
                    output = model.predict(input_tensor)
                else:
                    output = model(input_tensor)

            inference_time = (time.time() - inference_start) * 1000

            # Process output
            if isinstance(output, torch.Tensor):
                output = output.cpu().numpy()

            # Remove batch dimension if single sample
            if output.shape[0] == 1:
                output = output.squeeze(0)

            # Calculate confidence
            confidence = self._calculate_confidence(output, request.prediction_type)

            # Create result
            result = PredictionResult(
                model_id=request.model_id,
                prediction_type=request.prediction_type,
                value=output,
                confidence=confidence,
                timestamp=datetime.utcnow(),
                inference_time_ms=inference_time,
                metadata=request.metadata,
                is_cached=False,
            )

            # Store in cache
            if self.cache_enabled and request.cache_key:
                await self._cache_prediction(request.cache_key, result, request.ttl_seconds)

            # Store history
            await self._store_prediction_history(result)

            # Record metrics
            PREDICTION_DURATION.labels(
                model_type=request.model_id.split("_")[0] if "_" in request.model_id else "unknown",
                mode=request.mode.value,
            ).observe((time.time() - start_time))
            PREDICTION_COUNTER.labels(
                model_type=request.model_id.split("_")[0] if "_" in request.model_id else "unknown",
                mode=request.mode.value,
                status="success",
            ).inc()
            PREDICTION_LATENCY.observe(inference_time)

            return result

        except Exception as e:
            PREDICTION_COUNTER.labels(
                model_type=request.model_id.split("_")[0] if "_" in request.model_id else "unknown",
                mode=request.mode.value,
                status="error",
            ).inc()
            logger.error(f"Prediction error: {e}")
            raise

    async def predict_batch(
        self,
        requests: List[PredictionRequest],
        parallel: bool = True,
    ) -> List[PredictionResult]:
        """
        Perform batch predictions.

        Args:
            requests: List of prediction requests
            parallel: Whether to process in parallel

        Returns:
            List of prediction results
        """
        if parallel:
            # Process in parallel
            tasks = [self.predict(req) for req in requests]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle errors
            final_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    final_results.append(
                        PredictionResult(
                            model_id=requests[i].model_id,
                            prediction_type=requests[i].prediction_type,
                            value=None,
                            confidence=0.0,
                            timestamp=datetime.utcnow(),
                            inference_time_ms=0.0,
                            metadata={"error": str(result)},
                            is_cached=False,
                        )
                    )
                else:
                    final_results.append(result)

            return final_results
        else:
            # Sequential processing
            results = []
            for request in requests:
                result = await self.predict(request)
                results.append(result)
            return results

    async def predict_streaming(
        self,
        request: PredictionRequest,
        callback: Callable,
    ):
        """
        Perform streaming prediction.

        Args:
            request: Prediction request
            callback: Callback function for streaming results
        """
        # Add to batch queue for streaming processing
        request.metadata["callback"] = callback
        request.mode = PredictionMode.STREAMING

        async with self._lock:
            if len(self._batch_queue) >= self.max_batch_queue:
                raise ValueError("Batch queue is full")

            self._batch_queue.append(request)

    async def ensemble_predict(
        self,
        requests: List[PredictionRequest],
        weights: Optional[List[float]] = None,
        aggregation: str = "weighted_average",
    ) -> PredictionResult:
        """
        Perform ensemble prediction.

        Args:
            requests: List of prediction requests for different models
            weights: Optional weights for each model
            aggregation: Aggregation method ("average", "weighted_average", "vote", "max")

        Returns:
            Ensemble prediction result
        """
        if not requests:
            raise ValueError("At least one prediction request required")

        # Get predictions from all models
        results = await self.predict_batch(requests)

        # Extract values
        values = [r.value for r in results]
        confidences = [r.confidence for r in results]

        # Calculate weights
        if weights is None:
            weights = [c / sum(confidences) for c in confidences]

        # Aggregate predictions
        if aggregation == "average":
            aggregated_value = np.mean(values, axis=0)
            aggregated_confidence = np.mean(confidences)
        elif aggregation == "weighted_average":
            aggregated_value = np.average(values, weights=weights, axis=0)
            aggregated_confidence = np.average(confidences, weights=weights)
        elif aggregation == "vote":
            # For classification
            if all(isinstance(v, (int, float)) for v in values):
                aggregated_value = max(set(values), key=values.count)
            else:
                aggregated_value = np.mean(values, axis=0)
            aggregated_confidence = np.max(confidences)
        elif aggregation == "max":
            best_idx = np.argmax(weights)
            aggregated_value = values[best_idx]
            aggregated_confidence = confidences[best_idx]
        else:
            raise ValueError(f"Unsupported aggregation: {aggregation}")

        # Create ensemble result
        model_ids = [r.model_id for r in results]
        ensemble_result = PredictionResult(
            model_id=f"ensemble_{'_'.join(model_ids)}",
            prediction_type=requests[0].prediction_type,
            value=aggregated_value,
            confidence=aggregated_confidence,
            timestamp=datetime.utcnow(),
            inference_time_ms=sum(r.inference_time_ms for r in results) / len(results),
            metadata={
                "ensemble_members": model_ids,
                "weights": weights,
                "aggregation": aggregation,
            },
            is_cached=False,
            ensemble_members=[r.to_dict() for r in results],
        )

        return ensemble_result

    def _prepare_input(
        self,
        input_data: Union[np.ndarray, torch.Tensor, Dict[str, Any]],
    ) -> Union[np.ndarray, torch.Tensor]:
        """
        Prepare input data for prediction.

        Args:
            input_data: Raw input data

        Returns:
            Prepared input
        """
        if isinstance(input_data, dict):
            # Extract features from dict
            if "features" in input_data:
                return np.array(input_data["features"])
            elif "sequence" in input_data:
                return np.array(input_data["sequence"])
            else:
                # Convert dict to array
                return np.array(list(input_data.values()))

        if isinstance(input_data, torch.Tensor):
            return input_data

        if isinstance(input_data, list):
            return np.array(input_data)

        if isinstance(input_data, (int, float)):
            return np.array([input_data])

        return input_data

    def _calculate_confidence(
        self,
        output: Any,
        prediction_type: PredictionType,
    ) -> float:
        """
        Calculate confidence score for prediction.

        Args:
            output: Model output
            prediction_type: Type of prediction

        Returns:
            Confidence score (0-1)
        """
        try:
            if prediction_type == PredictionType.DIRECTION:
                # For binary classification, confidence is probability
                if isinstance(output, (np.ndarray, torch.Tensor)):
                    if len(output) > 0:
                        output_flat = output.flatten()
                        if output_flat.size > 0:
                            # Sigmoid to get probability
                            prob = 1 / (1 + np.exp(-float(output_flat[0])))
                            return max(prob, 1 - prob)
                return 0.5

            elif prediction_type == PredictionType.PRICE:
                # For price prediction, confidence based on prediction interval
                if hasattr(self, '_get_prediction_interval'):
                    interval = self._get_prediction_interval(output)
                    width = interval[1] - interval[0]
                    if width > 0:
                        confidence = 1 / (1 + width)
                        return min(1.0, confidence)
                return 0.6

            elif prediction_type == PredictionType.VOLATILITY:
                # For volatility, confidence based on relative error
                if isinstance(output, (int, float)):
                    if output > 0:
                        return 1 / (1 + output)
                return 0.5

            elif prediction_type == PredictionType.SIGNAL:
                # Signal strength as confidence
                if isinstance(output, (int, float)):
                    return min(1.0, abs(output))
                elif isinstance(output, np.ndarray):
                    return min(1.0, float(np.mean(np.abs(output))))
                return 0.5

            else:
                # Default confidence
                if isinstance(output, (np.ndarray, torch.Tensor)):
                    if output.size > 0:
                        return min(1.0, float(np.mean(np.abs(output))))
                return 0.5

        except Exception as e:
            logger.warning(f"Error calculating confidence: {e}")
            return 0.5

    async def _get_cached_prediction(
        self,
        cache_key: str,
    ) -> Optional[PredictionResult]:
        """
        Get cached prediction.

        Args:
            cache_key: Cache key

        Returns:
            Cached prediction result or None
        """
        try:
            cached = await self.cache_manager.get(cache_key)
            if cached:
                # Deserialize
                if isinstance(cached, dict):
                    result = PredictionResult(
                        model_id=cached["model_id"],
                        prediction_type=PredictionType(cached["prediction_type"]),
                        value=cached["value"],
                        confidence=cached["confidence"],
                        timestamp=datetime.fromisoformat(cached["timestamp"]),
                        inference_time_ms=cached["inference_time_ms"],
                        metadata=cached.get("metadata", {}),
                        is_cached=True,
                    )
                    return result
        except Exception as e:
            logger.warning(f"Error getting cached prediction: {e}")

        return None

    async def _cache_prediction(
        self,
        cache_key: str,
        result: PredictionResult,
        ttl_seconds: int,
    ):
        """
        Cache prediction result.

        Args:
            cache_key: Cache key
            result: Prediction result
            ttl_seconds: TTL in seconds
        """
        try:
            # Serialize
            cached_data = {
                "model_id": result.model_id,
                "prediction_type": result.prediction_type.value,
                "value": result.value if isinstance(result.value, (int, float, list, np.ndarray)) else None,
                "confidence": result.confidence,
                "timestamp": result.timestamp.isoformat(),
                "inference_time_ms": result.inference_time_ms,
                "metadata": result.metadata,
            }
            await self.cache_manager.set(cache_key, cached_data, ttl_seconds)
        except Exception as e:
            logger.warning(f"Error caching prediction: {e}")

    async def _store_prediction_history(self, result: PredictionResult):
        """
        Store prediction in history.

        Args:
            result: Prediction result
        """
        key = f"{result.model_id}_{result.prediction_type.value}"

        if key not in self._prediction_history:
            self._prediction_history[key] = []

        history = self._prediction_history[key]
        history.append(result)

        # Limit history size
        if len(history) > self.history_size:
            self._prediction_history[key] = history[-self.history_size:]

        # Update accuracy metrics
        await self._update_accuracy_metrics(result)

    async def _update_accuracy_metrics(self, result: PredictionResult):
        """
        Update prediction accuracy metrics.

        Args:
            result: Prediction result
        """
        try:
            # Check if actual value is available
            if "actual" in result.metadata:
                actual = result.metadata["actual"]

                # Calculate accuracy based on prediction type
                if result.prediction_type == PredictionType.DIRECTION:
                    # Binary classification accuracy
                    if isinstance(result.value, (int, float)):
                        predicted = 1 if result.value > 0 else 0
                        accuracy = 1 if predicted == actual else 0
                        PREDICTION_ACCURACY.labels(
                            model_type=result.model_id.split("_")[0] if "_" in result.model_id else "unknown"
                        ).set(accuracy)

                elif result.prediction_type == PredictionType.PRICE:
                    # Price prediction accuracy (relative error)
                    if isinstance(result.value, (int, float)):
                        relative_error = abs(result.value - actual) / (abs(actual) + 1e-8)
                        accuracy = max(0, 1 - relative_error)
                        PREDICTION_ACCURACY.labels(
                            model_type=result.model_id.split("_")[0] if "_" in result.model_id else "unknown"
                        ).set(accuracy)

        except Exception as e:
            logger.debug(f"Error updating accuracy metrics: {e}")

    async def get_prediction_history(
        self,
        model_id: str,
        prediction_type: PredictionType,
        limit: int = 100,
    ) -> List[PredictionResult]:
        """
        Get prediction history.

        Args:
            model_id: Model ID
            prediction_type: Prediction type
            limit: Maximum number of results

        Returns:
            List of prediction results
        """
        key = f"{model_id}_{prediction_type.value}"
        history = self._prediction_history.get(key, [])
        return history[-limit:]

    async def get_statistics(
        self,
        model_id: str,
        prediction_type: PredictionType,
    ) -> Dict[str, Any]:
        """
        Get prediction statistics.

        Args:
            model_id: Model ID
            prediction_type: Prediction type

        Returns:
            Statistics dictionary
        """
        history = await self.get_prediction_history(model_id, prediction_type, limit=1000)

        if not history:
            return {
                "count": 0,
                "avg_confidence": 0,
                "avg_latency": 0,
                "accuracy": 0,
            }

        return {
            "count": len(history),
            "avg_confidence": np.mean([r.confidence for r in history]),
            "avg_latency": np.mean([r.inference_time_ms for r in history]),
            "max_latency": np.max([r.inference_time_ms for r in history]),
            "min_latency": np.min([r.inference_time_ms for r in history]),
            "accuracy": np.mean([1 if r.confidence > 0.5 else 0 for r in history]),
            "recent_accuracy": np.mean([1 if r.confidence > 0.5 else 0 for r in history[-100:]]),
        }

    async def clear_cache(self):
        """Clear prediction cache."""
        if self.cache_manager:
            await self.cache_manager.clear()
        logger.info("Prediction cache cleared")

    async def shutdown(self):
        """Shutdown the predictor."""
        if self._batch_processor_task and not self._batch_processor_task.done():
            self._batch_processor_task.cancel()
            try:
                await self._batch_processor_task
            except asyncio.CancelledError:
                pass

        # Process remaining batch
        if self._batch_queue:
            batch = list(self._batch_queue)
            self._batch_queue.clear()
            await self._execute_batch_predictions(batch)

        logger.info("ModelPredictor shut down")


# Utility functions
def create_prediction_request(
    model_id: str,
    input_data: Union[np.ndarray, torch.Tensor, Dict[str, Any]],
    prediction_type: Union[PredictionType, str],
    **kwargs,
) -> PredictionRequest:
    """
    Create a prediction request.

    Args:
        model_id: Model ID
        input_data: Input data
        prediction_type: Prediction type
        **kwargs: Additional request parameters

    Returns:
        PredictionRequest instance
    """
    if isinstance(prediction_type, str):
        prediction_type = PredictionType(prediction_type)

    return PredictionRequest(
        model_id=model_id,
        input_data=input_data,
        prediction_type=prediction_type,
        **kwargs
    )
