"""
NEXUS AI TRADING SYSTEM - Model Evaluator
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced model evaluation module for AI trading bots.
Provides comprehensive model assessment, validation, and performance analysis.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from prometheus_client import Counter, Gauge, Histogram
from sklearn.metrics import (
    accuracy_score,
    auc,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import TimeSeriesSplit

from shared.helpers.trading_helpers import TradingHelpers
from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector

logger = get_logger(__name__)

# Prometheus metrics
MODEL_EVALUATION_COUNTER = Counter(
    "nexus_model_evaluations_total",
    "Total number of model evaluations",
    ["model_type", "status"],
)
MODEL_EVALUATION_DURATION = Histogram(
    "nexus_model_evaluation_duration_seconds",
    "Duration of model evaluations",
    ["model_type"],
)
MODEL_PERFORMANCE_GAUGE = Gauge(
    "nexus_model_performance",
    "Model performance metrics",
    ["model_type", "metric"],
)


class EvaluationMode(Enum):
    """Evaluation modes for different use cases."""

    QUICK = "quick"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"
    CROSS_VALIDATION = "cross_validation"
    WALK_FORWARD = "walk_forward"


class ValidationType(Enum):
    """Types of validation to perform."""

    IN_SAMPLE = "in_sample"
    OUT_OF_SAMPLE = "out_of_sample"
    WALK_FORWARD = "walk_forward"
    CROSS_VALIDATION = "cross_validation"
    MONTE_CARLO = "monte_carlo"


@dataclass
class PerformanceMetrics:
    """Container for model performance metrics."""

    # Regression metrics
    mse: float = 0.0
    rmse: float = 0.0
    mae: float = 0.0
    r2: float = 0.0
    mape: float = 0.0
    smape: float = 0.0

    # Classification metrics
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    auc_roc: float = 0.0
    auc_pr: float = 0.0

    # Trading metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_return: float = 0.0
    volatility: float = 0.0

    # Model metrics
    inference_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    model_size_mb: float = 0.0
    feature_importance: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "regression": {
                "mse": self.mse,
                "rmse": self.rmse,
                "mae": self.mae,
                "r2": self.r2,
                "mape": self.mape,
                "smape": self.smape,
            },
            "classification": {
                "accuracy": self.accuracy,
                "precision": self.precision,
                "recall": self.recall,
                "f1": self.f1,
                "auc_roc": self.auc_roc,
                "auc_pr": self.auc_pr,
            },
            "trading": {
                "sharpe_ratio": self.sharpe_ratio,
                "sortino_ratio": self.sortino_ratio,
                "calmar_ratio": self.calmar_ratio,
                "max_drawdown": self.max_drawdown,
                "win_rate": self.win_rate,
                "profit_factor": self.profit_factor,
                "avg_return": self.avg_return,
                "volatility": self.volatility,
            },
            "model": {
                "inference_time_ms": self.inference_time_ms,
                "memory_usage_mb": self.memory_usage_mb,
                "model_size_mb": self.model_size_mb,
                "feature_importance": self.feature_importance,
            },
        }


@dataclass
class EvaluationResult:
    """Complete evaluation result for a model."""

    model_id: str
    model_type: str
    version: str
    timestamp: datetime
    evaluation_mode: EvaluationMode
    validation_type: ValidationType
    metrics: PerformanceMetrics
    confidence_intervals: Dict[str, Tuple[float, float]]
    predictions: Optional[np.ndarray] = None
    actuals: Optional[np.ndarray] = None
    residuals: Optional[np.ndarray] = None
    confusion_matrix: Optional[np.ndarray] = None
    feature_importance: Optional[Dict[str, float]] = None
    error_analysis: Optional[Dict[str, Any]] = None
    recommendation: Optional[str] = None
    grade: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "model_id": self.model_id,
            "model_type": self.model_type,
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "evaluation_mode": self.evaluation_mode.value,
            "validation_type": self.validation_type.value,
            "metrics": self.metrics.to_dict(),
            "confidence_intervals": self.confidence_intervals,
            "recommendation": self.recommendation,
            "grade": self.grade,
        }


class ModelEvaluator:
    """
    Advanced model evaluator with comprehensive validation and analysis.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        model_registry: Optional[Any] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the model evaluator.

        Args:
            config: Configuration dictionary
            model_registry: Optional model registry for persisting results
            metrics_collector: Optional metrics collector for monitoring
        """
        self.config = config
        self.model_registry = model_registry
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.evaluation_history: List[EvaluationResult] = []
        self._lock = asyncio.Lock()

        # Load evaluation configuration
        self.eval_config = config.get("evaluation", {})
        self.default_mode = EvaluationMode(
            self.eval_config.get("default_mode", "standard")
        )
        self.min_validation_samples = self.eval_config.get(
            "min_validation_samples", 100
        )
        self.confidence_level = self.eval_config.get("confidence_level", 0.95)
        self.walk_forward_windows = self.eval_config.get(
            "walk_forward_windows", 5
        )
        self.cv_folds = self.eval_config.get("cv_folds", 5)

        # Set up grading thresholds
        self.grading_thresholds = self.eval_config.get(
            "grading_thresholds",
            {
                "A": {"sharpe": 2.0, "accuracy": 0.85, "r2": 0.90},
                "B": {"sharpe": 1.5, "accuracy": 0.75, "r2": 0.80},
                "C": {"sharpe": 1.0, "accuracy": 0.60, "r2": 0.60},
                "D": {"sharpe": 0.5, "accuracy": 0.50, "r2": 0.40},
            },
        )

        logger.info("ModelEvaluator initialized with config: %s", config)

    async def evaluate_model(
        self,
        model: nn.Module,
        model_id: str,
        model_type: str,
        version: str,
        X_test: Union[np.ndarray, torch.Tensor],
        y_test: Union[np.ndarray, torch.Tensor],
        X_train: Optional[Union[np.ndarray, torch.Tensor]] = None,
        y_train: Optional[Union[np.ndarray, torch.Tensor]] = None,
        mode: Union[EvaluationMode, str] = EvaluationMode.STANDARD,
        task_type: str = "regression",
        feature_names: Optional[List[str]] = None,
        verbose: bool = True,
    ) -> EvaluationResult:
        """
        Evaluate a model with comprehensive metrics and analysis.

        Args:
            model: PyTorch model to evaluate
            model_id: Unique identifier for the model
            model_type: Type of model (e.g., "lstm", "transformer")
            version: Model version
            X_test: Test features
            y_test: Test targets
            X_train: Optional training features for validation
            y_train: Optional training targets for validation
            mode: Evaluation mode
            task_type: "regression" or "classification"
            feature_names: Names of features for importance analysis
            verbose: Whether to log progress

        Returns:
            EvaluationResult object
        """
        mode = (
            EvaluationMode(mode)
            if isinstance(mode, str)
            else mode
        )

        start_time = time.time()
        logger.info(
            f"Starting {mode.value} evaluation for model {model_id} (v{version})"
        )

        try:
            # Prepare data
            X_test = self._prepare_data(X_test)
            y_test = self._prepare_data(y_test)

            if X_train is not None:
                X_train = self._prepare_data(X_train)
            if y_train is not None:
                y_train = self._prepare_data(y_train)

            # Perform model inference
            predictions = await self._predict_with_timing(model, X_test)

            # Calculate base metrics
            metrics = PerformanceMetrics()

            if task_type == "regression":
                metrics = self._calculate_regression_metrics(y_test, predictions)
            else:
                metrics = self._calculate_classification_metrics(
                    y_test, predictions
                )

            # Additional trading metrics
            metrics = self._calculate_trading_metrics(y_test, predictions, metrics)

            # Model performance metrics
            metrics = await self._calculate_model_metrics(
                model, predictions, metrics
            )

            # Feature importance
            if feature_names and X_test is not None:
                metrics.feature_importance = await self._calculate_feature_importance(
                    model, X_test, y_test, feature_names
                )

            # Calculate confidence intervals
            confidence_intervals = self._calculate_confidence_intervals(
                predictions, y_test
            )

            # Calculate residuals
            residuals = predictions - y_test

            # Calculate confusion matrix for classification
            confusion_matrix_result = None
            if task_type == "classification":
                confusion_matrix_result = confusion_matrix(
                    y_test.round().astype(int),
                    predictions.round().astype(int),
                )

            # Error analysis
            error_analysis = await self._analyze_errors(
                y_test, predictions, residuals
            )

            # Grade the model
            grade = self._calculate_grade(metrics, task_type)

            # Generate recommendation
            recommendation = self._generate_recommendation(metrics, grade)

            result = EvaluationResult(
                model_id=model_id,
                model_type=model_type,
                version=version,
                timestamp=datetime.utcnow(),
                evaluation_mode=mode,
                validation_type=ValidationType.OUT_OF_SAMPLE,
                metrics=metrics,
                confidence_intervals=confidence_intervals,
                predictions=predictions,
                actuals=y_test,
                residuals=residuals,
                confusion_matrix=confusion_matrix_result,
                feature_importance=metrics.feature_importance,
                error_analysis=error_analysis,
                recommendation=recommendation,
                grade=grade,
            )

            # Store result
            async with self._lock:
                self.evaluation_history.append(result)

            # Record metrics
            self._record_metrics(result)

            # Log results
            if verbose:
                self._log_evaluation_result(result)

            duration = time.time() - start_time
            MODEL_EVALUATION_DURATION.labels(model_type=model_type).observe(
                duration
            )
            MODEL_EVALUATION_COUNTER.labels(
                model_type=model_type, status="success"
            ).inc()

            # Save to registry if available
            if self.model_registry:
                await self._save_to_registry(result)

            return result

        except Exception as e:
            MODEL_EVALUATION_COUNTER.labels(
                model_type=model_type, status="error"
            ).inc()
            logger.error(f"Error evaluating model {model_id}: {e}")
            raise

    def _prepare_data(
        self,
        data: Union[np.ndarray, torch.Tensor, pd.DataFrame],
    ) -> np.ndarray:
        """Prepare data for evaluation."""
        if isinstance(data, torch.Tensor):
            return data.cpu().numpy()
        elif isinstance(data, pd.DataFrame):
            return data.values
        return data

    async def _predict_with_timing(
        self,
        model: nn.Module,
        X: np.ndarray,
    ) -> np.ndarray:
        """Perform model prediction with timing."""
        model.eval()
        start_time = time.perf_counter()

        with torch.no_grad():
            if isinstance(X, np.ndarray):
                X_tensor = torch.tensor(X, dtype=torch.float32)

            # Handle different input shapes
            if len(X_tensor.shape) == 2:
                # 2D input (batch, features)
                predictions = model(X_tensor).cpu().numpy()
            else:
                # 3D input (batch, sequence, features) for sequence models
                predictions = model(X_tensor).cpu().numpy()

        self._inference_time = (time.perf_counter() - start_time) * 1000  # ms
        return predictions.flatten()

    def _calculate_regression_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> PerformanceMetrics:
        """Calculate regression metrics."""
        metrics = PerformanceMetrics()

        # Handle NaN values
        mask = ~(np.isnan(y_true) | np.isnan(y_pred))
        y_true_clean = y_true[mask]
        y_pred_clean = y_pred[mask]

        if len(y_true_clean) < self.min_validation_samples:
            logger.warning(
                f"Only {len(y_true_clean)} valid samples for evaluation"
            )
            return metrics

        # Standard regression metrics
        metrics.mse = mean_squared_error(y_true_clean, y_pred_clean)
        metrics.rmse = np.sqrt(metrics.mse)
        metrics.mae = mean_absolute_error(y_true_clean, y_pred_clean)
        metrics.r2 = r2_score(y_true_clean, y_pred_clean)

        # MAPE (Mean Absolute Percentage Error)
        with np.errstate(divide="ignore", invalid="ignore"):
            mape = np.mean(
                np.abs((y_true_clean - y_pred_clean) / y_true_clean)
            ) * 100
            metrics.mape = np.nan_to_num(mape, nan=0.0, posinf=0.0)

        # SMAPE (Symmetric Mean Absolute Percentage Error)
        denominator = (np.abs(y_true_clean) + np.abs(y_pred_clean)) / 2
        with np.errstate(divide="ignore", invalid="ignore"):
            smape = np.mean(
                np.abs(y_true_clean - y_pred_clean) / denominator
            ) * 100
            metrics.smape = np.nan_to_num(smape, nan=0.0, posinf=0.0)

        return metrics

    def _calculate_classification_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> PerformanceMetrics:
        """Calculate classification metrics."""
        metrics = PerformanceMetrics()

        # Handle NaN values
        mask = ~(np.isnan(y_true) | np.isnan(y_pred))
        y_true_clean = y_true[mask]
        y_pred_clean = y_pred[mask]

        if len(y_true_clean) < self.min_validation_samples:
            return metrics

        # Convert to binary predictions if needed
        y_pred_binary = np.round(y_pred_clean).astype(int)

        # Standard classification metrics
        metrics.accuracy = accuracy_score(y_true_clean, y_pred_binary)
        metrics.precision = precision_score(
            y_true_clean, y_pred_binary, average="weighted", zero_division=0
        )
        metrics.recall = recall_score(
            y_true_clean, y_pred_binary, average="weighted", zero_division=0
        )
        metrics.f1 = f1_score(
            y_true_clean, y_pred_binary, average="weighted", zero_division=0
        )

        # AUC-ROC
        try:
            metrics.auc_roc = roc_auc_score(
                y_true_clean,
                y_pred_clean,
                average="weighted",
                multi_class="ovr",
            )
        except Exception:
            metrics.auc_roc = 0.5

        # AUC-PR
        try:
            precision_curve, recall_curve, _ = precision_recall_curve(
                y_true_clean, y_pred_clean
            )
            metrics.auc_pr = auc(recall_curve, precision_curve)
        except Exception:
            metrics.auc_pr = 0.0

        return metrics

    def _calculate_trading_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        metrics: PerformanceMetrics,
    ) -> PerformanceMetrics:
        """Calculate trading-specific metrics."""
        try:
            # Calculate returns
            actual_returns = np.diff(y_true) / y_true[:-1]
            predicted_returns = np.diff(y_pred) / y_pred[:-1]

            # Win rate (direction prediction accuracy)
            direction_correct = np.mean(
                (np.sign(actual_returns) == np.sign(predicted_returns))
            )
            metrics.win_rate = direction_correct

            # Profit factor
            gains = actual_returns[actual_returns > 0]
            losses = np.abs(actual_returns[actual_returns < 0])
            metrics.profit_factor = (
                np.sum(gains) / np.sum(losses) if np.sum(losses) > 0 else 0.0
            )

            # Sharpe ratio
            if len(actual_returns) > 1:
                metrics.sharpe_ratio = (
                    np.mean(actual_returns) / (np.std(actual_returns) + 1e-8)
                ) * np.sqrt(252)

            # Sortino ratio
            downside_returns = actual_returns[actual_returns < 0]
            if len(downside_returns) > 0:
                downside_std = np.std(downside_returns)
                metrics.sortino_ratio = (
                    np.mean(actual_returns) / (downside_std + 1e-8)
                ) * np.sqrt(252)

            # Maximum drawdown
            cumulative_returns = np.cumprod(1 + actual_returns)
            running_max = np.maximum.accumulate(cumulative_returns)
            drawdown = (running_max - cumulative_returns) / running_max
            metrics.max_drawdown = np.max(drawdown)

            # Calmar ratio
            if metrics.max_drawdown > 0:
                metrics.calmar_ratio = metrics.sharpe_ratio / metrics.max_drawdown

            # Volatility
            metrics.volatility = np.std(actual_returns) * np.sqrt(252)

            # Average return
            metrics.avg_return = np.mean(actual_returns)

        except Exception as e:
            logger.warning(f"Error calculating trading metrics: {e}")

        return metrics

    async def _calculate_model_metrics(
        self,
        model: nn.Module,
        predictions: np.ndarray,
        metrics: PerformanceMetrics,
    ) -> PerformanceMetrics:
        """Calculate model-specific metrics."""
        try:
            # Model size
            model_bytes = sum(
                p.numel() * p.element_size() for p in model.parameters()
            )
            metrics.model_size_mb = model_bytes / (1024 * 1024)

            # Memory usage (approximate)
            metrics.memory_usage_mb = torch.cuda.memory_allocated() / (1024 * 1024)

            # Inference time
            metrics.inference_time_ms = getattr(self, "_inference_time", 0.0)

        except Exception as e:
            logger.warning(f"Error calculating model metrics: {e}")

        return metrics

    async def _calculate_feature_importance(
        self,
        model: nn.Module,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
    ) -> Dict[str, float]:
        """Calculate feature importance using permutation importance."""
        importance = {}

        try:
            # Get base performance
            base_pred = await self._predict_with_timing(model, X)
            base_mse = mean_squared_error(y, base_pred)

            # For each feature, permute and measure impact
            X_permuted = X.copy()
            for i, feature_name in enumerate(feature_names):
                if i >= X.shape[1]:
                    break

                # Shuffle feature
                np.random.shuffle(X_permuted[:, i])

                # Calculate performance with permuted feature
                permuted_pred = await self._predict_with_timing(
                    model, X_permuted
                )
                permuted_mse = mean_squared_error(y, permuted_pred)

                # Importance is the increase in MSE
                importance[feature_name] = max(0, permuted_mse - base_mse)

                # Reset feature
                X_permuted[:, i] = X[:, i]

            # Normalize importance
            total = sum(importance.values())
            if total > 0:
                importance = {
                    k: v / total for k, v in importance.items()
                }

        except Exception as e:
            logger.warning(f"Error calculating feature importance: {e}")

        return importance

    def _calculate_confidence_intervals(
        self,
        y_pred: np.ndarray,
        y_true: np.ndarray,
    ) -> Dict[str, Tuple[float, float]]:
        """Calculate confidence intervals for predictions."""
        residuals = y_true - y_pred
        n = len(residuals)

        if n < 30:
            # Use t-distribution for small samples
            from scipy.stats import t

            se = np.std(residuals) / np.sqrt(n)
            t_value = t.ppf((1 + self.confidence_level) / 2, n - 1)
            margin = t_value * se
        else:
            # Use normal distribution for large samples
            from scipy.stats import norm

            se = np.std(residuals) / np.sqrt(n)
            z_value = norm.ppf((1 + self.confidence_level) / 2)
            margin = z_value * se

        mean_pred = np.mean(y_pred)
        return {
            "mean": (mean_pred - margin, mean_pred + margin),
            "individual": (
                np.percentile(y_pred, (1 - self.confidence_level) / 2 * 100),
                np.percentile(y_pred, (1 + self.confidence_level) / 2 * 100),
            ),
        }

    async def _analyze_errors(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        residuals: np.ndarray,
    ) -> Dict[str, Any]:
        """Analyze prediction errors."""
        error_analysis = {
            "residual_stats": {
                "mean": float(np.mean(residuals)),
                "std": float(np.std(residuals)),
                "skew": float(
                    np.mean((residuals - np.mean(residuals)) ** 3)
                    / (np.std(residuals) ** 3 + 1e-8)
                ),
                "kurtosis": float(
                    np.mean((residuals - np.mean(residuals)) ** 4)
                    / (np.std(residuals) ** 4 + 1e-8)
                    - 3
                ),
            },
            "outliers": {
                "count": int(np.sum(np.abs(residuals) > 3 * np.std(residuals))),
                "percentage": float(
                    np.mean(np.abs(residuals) > 3 * np.std(residuals)) * 100
                ),
            },
            "error_distribution": {
                "quartiles": [
                    float(np.percentile(residuals, q))
                    for q in [25, 50, 75]
                ],
                "min": float(np.min(residuals)),
                "max": float(np.max(residuals)),
            },
        }

        # Check for bias
        error_analysis["bias"] = {
            "positive_bias": float(np.mean(y_pred > y_true)),
            "negative_bias": float(np.mean(y_pred < y_true)),
            "systematic_bias": float(np.mean(residuals)),
        }

        return error_analysis

    def _calculate_grade(
        self,
        metrics: PerformanceMetrics,
        task_type: str,
    ) -> str:
        """Calculate model grade based on performance."""
        thresholds = self.grading_thresholds

        if task_type == "regression":
            score = metrics.r2
            # Combine with trading metrics
            if metrics.sharpe_ratio > 0:
                score = (score + min(metrics.sharpe_ratio / 2, 0.5)) / 1.5
        else:
            score = metrics.accuracy
            # Combine with F1
            score = (score + metrics.f1) / 2

        # Determine grade
        if score >= thresholds["A"]["accuracy"]:
            return "A"
        elif score >= thresholds["B"]["accuracy"]:
            return "B"
        elif score >= thresholds["C"]["accuracy"]:
            return "C"
        elif score >= thresholds["D"]["accuracy"]:
            return "D"
        else:
            return "F"

    def _generate_recommendation(
        self,
        metrics: PerformanceMetrics,
        grade: str,
    ) -> str:
        """Generate recommendation based on evaluation results."""
        if grade in ["A", "B"]:
            return (
                "Model performs well across all metrics. "
                "Recommended for deployment with monitoring."
            )
        elif grade == "C":
            return (
                "Model shows acceptable performance but has room for improvement. "
                "Consider additional training or feature engineering."
            )
        elif grade == "D":
            return (
                "Model performance is below expectations. "
                "Consider hyperparameter tuning, increasing data, or trying "
                "different architectures."
            )
        else:
            return (
                "Model needs significant improvement. "
                "Consider revisiting the model architecture and training process."
            )

    def _log_evaluation_result(self, result: EvaluationResult):
        """Log evaluation results."""
        logger.info("=" * 80)
        logger.info(f"MODEL EVALUATION RESULTS - {result.model_id} v{result.version}")
        logger.info("=" * 80)
        logger.info(f"Grade: {result.grade} | Recommendation: {result.recommendation}")
        logger.info("-" * 40)
        logger.info("REGRESSION METRICS:")
        logger.info(f"  MSE: {result.metrics.mse:.6f}")
        logger.info(f"  RMSE: {result.metrics.rmse:.6f}")
        logger.info(f"  MAE: {result.metrics.mae:.6f}")
        logger.info(f"  R²: {result.metrics.r2:.4f}")
        logger.info(f"  MAPE: {result.metrics.mape:.2f}%")
        logger.info(f"  SMAPE: {result.metrics.smape:.2f}%")
        logger.info("-" * 40)
        logger.info("TRADING METRICS:")
        logger.info(f"  Sharpe Ratio: {result.metrics.sharpe_ratio:.4f}")
        logger.info(f"  Sortino Ratio: {result.metrics.sortino_ratio:.4f}")
        logger.info(f"  Calmar Ratio: {result.metrics.calmar_ratio:.4f}")
        logger.info(f"  Max Drawdown: {result.metrics.max_drawdown:.4f}")
        logger.info(f"  Win Rate: {result.metrics.win_rate:.4f}")
        logger.info(f"  Profit Factor: {result.metrics.profit_factor:.4f}")
        logger.info("-" * 40)
        logger.info("MODEL METRICS:")
        logger.info(f"  Inference Time: {result.metrics.inference_time_ms:.2f} ms")
        logger.info(f"  Model Size: {result.metrics.model_size_mb:.2f} MB")
        logger.info("=" * 80)

    def _record_metrics(self, result: EvaluationResult):
        """Record evaluation metrics for monitoring."""
        try:
            # Recording trading metrics
            MODEL_PERFORMANCE_GAUGE.labels(
                model_type=result.model_type, metric="sharpe_ratio"
            ).set(result.metrics.sharpe_ratio)
            MODEL_PERFORMANCE_GAUGE.labels(
                model_type=result.model_type, metric="max_drawdown"
            ).set(result.metrics.max_drawdown)
            MODEL_PERFORMANCE_GAUGE.labels(
                model_type=result.model_type, metric="r2"
            ).set(result.metrics.r2)

            if result.metrics.accuracy > 0:
                MODEL_PERFORMANCE_GAUGE.labels(
                    model_type=result.model_type, metric="accuracy"
                ).set(result.metrics.accuracy)

        except Exception as e:
            logger.warning(f"Error recording metrics: {e}")

    async def _save_to_registry(self, result: EvaluationResult):
        """Save evaluation result to registry."""
        try:
            if self.model_registry:
                await self.model_registry.save_evaluation(result)
                logger.info(f"Saved evaluation result to registry for {result.model_id}")
        except Exception as e:
            logger.error(f"Error saving to registry: {e}")

    async def perform_walk_forward_validation(
        self,
        model_factory: callable,
        X: np.ndarray,
        y: np.ndarray,
        window_size: int,
        step_size: int,
        **kwargs,
    ) -> List[EvaluationResult]:
        """
        Perform walk-forward validation.

        Args:
            model_factory: Function to create a new model instance
            X: Features
            y: Targets
            window_size: Size of each validation window
            step_size: Step size between windows
            **kwargs: Additional arguments for evaluation

        Returns:
            List of evaluation results for each window
        """
        results = []
        n = len(X)
        num_windows = min(
            self.walk_forward_windows, (n - window_size) // step_size
        )

        logger.info(
            f"Starting walk-forward validation with {num_windows} windows"
        )

        for i in range(num_windows):
            # Split data
            start_idx = i * step_size
            end_idx = start_idx + window_size

            X_window = X[start_idx:end_idx]
            y_window = y[start_idx:end_idx]

            # Train model on this window
            model = model_factory()
            # Assume model has a train method
            if hasattr(model, "train"):
                await model.train(X_window, y_window)

            # Evaluate on next window
            next_start = end_idx
            next_end = min(next_start + step_size, n)

            if next_start >= n:
                break

            X_test = X[next_start:next_end]
            y_test = y[next_start:next_end]

            # Evaluate
            result = await self.evaluate_model(
                model,
                model_id=f"walk_{i}",
                model_type=kwargs.get("model_type", "unknown"),
                version=f"walk_{i}",
                X_test=X_test,
                y_test=y_test,
                mode=EvaluationMode.WALK_FORWARD,
                **kwargs,
            )
            results.append(result)

        # Aggregate results
        if results:
            self._log_walk_forward_summary(results)

        return results

    def _log_walk_forward_summary(self, results: List[EvaluationResult]):
        """Log summary of walk-forward validation."""
        logger.info("=" * 80)
        logger.info("WALK-FORWARD VALIDATION SUMMARY")
        logger.info("=" * 80)

        avg_sharpe = np.mean([r.metrics.sharpe_ratio for r in results])
        avg_r2 = np.mean([r.metrics.r2 for r in results])
        avg_drawdown = np.mean([r.metrics.max_drawdown for r in results])

        logger.info(f"Average Sharpe Ratio: {avg_sharpe:.4f}")
        logger.info(f"Average R²: {avg_r2:.4f}")
        logger.info(f"Average Max Drawdown: {avg_drawdown:.4f}")
        logger.info(f"Number of Windows: {len(results)}")
        logger.info("=" * 80)

    async def get_evaluation_history(
        self,
        model_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[EvaluationResult]:
        """Get evaluation history."""
        async with self._lock:
            if model_id:
                history = [
                    r for r in self.evaluation_history
                    if r.model_id == model_id
                ]
            else:
                history = self.evaluation_history.copy()

            return history[-limit:]

    async def compare_models(
        self,
        model_results: List[EvaluationResult],
    ) -> Dict[str, Any]:
        """
        Compare multiple model evaluation results.

        Args:
            model_results: List of evaluation results to compare

        Returns:
            Comparison dictionary
        """
        if not model_results:
            return {}

        comparison = {
            "models": [],
            "rankings": {},
            "best_performing": {},
            "recommendation": "",
        }

        # Gather metrics by model
        metrics_by_model = {}
        for result in model_results:
            model_key = f"{result.model_id}_v{result.version}"
            metrics_by_model[model_key] = result.metrics

        # Rankings for key metrics
        metrics_to_rank = ["sharpe_ratio", "r2", "accuracy", "win_rate"]

        for metric in metrics_to_rank:
            # Sort models by metric
            sorted_models = sorted(
                metrics_by_model.items(),
                key=lambda x: getattr(x[1], metric, 0),
                reverse=True,
            )
            comparison["rankings"][metric] = [
                (model, getattr(metrics, metric))
                for model, metrics in sorted_models[:5]
            ]

        # Best performing model
        best_model = max(
            metrics_by_model.items(),
            key=lambda x: (
                x[1].sharpe_ratio + x[1].r2 + (x[1].accuracy or 0)
            ),
        )
        comparison["best_performing"] = {
            "model": best_model[0],
            "metrics": best_model[1].to_dict(),
        }

        # Generate recommendation
        comparison["recommendation"] = (
            f"Best model is {best_model[0]} with Sharpe ratio of "
            f"{best_model[1].sharpe_ratio:.4f} and R² of {best_model[1].r2:.4f}"
        )

        return comparison

    async def export_evaluation_report(
        self,
        result: EvaluationResult,
        output_path: Union[str, Path],
        format: str = "json",
    ):
        """Export evaluation report to file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            with open(output_path, "w") as f:
                json.dump(result.to_dict(), f, indent=2)
        elif format == "yaml":
            import yaml

            with open(output_path, "w") as f:
                yaml.dump(result.to_dict(), f, default_flow_style=False)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Evaluation report exported to {output_path}")


# Utility function for precision-recall curve
def precision_recall_curve(y_true, y_pred, pos_label=1):
    """Calculate precision-recall curve."""
    from sklearn.metrics import precision_recall_curve as sk_curve

    if isinstance(y_true, np.ndarray) and len(y_true.shape) > 1:
        # Multi-label case
        precision = []
        recall = []
        for i in range(y_true.shape[1]):
            p, r, _ = sk_curve(y_true[:, i], y_pred[:, i], pos_label=pos_label)
            precision.append(p)
            recall.append(r)
        return np.mean(precision, axis=0), np.mean(recall, axis=0), None
    else:
        return sk_curve(y_true, y_pred, pos_label=pos_label)
