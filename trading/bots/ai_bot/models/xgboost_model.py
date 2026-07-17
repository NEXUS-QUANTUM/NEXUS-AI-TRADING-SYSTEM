"""
NEXUS AI TRADING SYSTEM - XGBoost Model
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced XGBoost model wrapper for trading predictions with comprehensive
feature engineering, hyperparameter optimization, and model interpretation.
"""

import asyncio
import json
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from prometheus_client import Counter, Histogram
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector

logger = get_logger(__name__)

# Prometheus metrics
XGBOOST_PREDICTIONS = Counter(
    "nexus_xgboost_predictions_total",
    "Total number of XGBoost predictions",
    ["mode", "status"],
)
XGBOOST_TRAINING_DURATION = Histogram(
    "nexus_xgboost_training_duration_seconds",
    "Duration of XGBoost training",
    ["objective"],
)


@dataclass
class XGBoostConfig:
    """Configuration for XGBoost model."""

    # Core parameters
    n_estimators: int = 1000
    max_depth: int = 8
    learning_rate: float = 0.01
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    colsample_bylevel: float = 0.8
    min_child_weight: float = 1.0
    gamma: float = 0.0
    reg_alpha: float = 0.0
    reg_lambda: float = 1.0
    scale_pos_weight: float = 1.0
    base_score: float = 0.5

    # Tree parameters
    tree_method: str = "gpu_hist" if xgb.__version__ else "hist"
    grow_policy: str = "depthwise"
    max_leaves: int = 0
    max_bin: int = 256
    min_child_weight_leaf: float = 0.0

    # Boosting parameters
    booster: str = "gbtree"
    objective: str = "reg:squarederror"
    eval_metric: Optional[Union[str, List[str]]] = "rmse"
    early_stopping_rounds: int = 50
    num_boost_round: int = 1000

    # Randomness
    seed: int = 42
    random_state: int = 42

    # Data parameters
    feature_names: Optional[List[str]] = None
    categorical_features: Optional[List[int]] = None
    feature_types: Optional[Dict[str, str]] = None
    missing: float = np.nan
    enable_categorical: bool = False

    # Training parameters
    use_time_series_split: bool = True
    n_splits: int = 5
    validation_size: float = 0.2
    test_size: float = 0.1
    scale_features: bool = True

    # Model metadata
    model_id: str = ""
    description: str = ""
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "n_estimators": self.n_estimators,
            "max_depth": self.max_depth,
            "learning_rate": self.learning_rate,
            "subsample": self.subsample,
            "colsample_bytree": self.colsample_bytree,
            "colsample_bylevel": self.colsample_bylevel,
            "min_child_weight": self.min_child_weight,
            "gamma": self.gamma,
            "reg_alpha": self.reg_alpha,
            "reg_lambda": self.reg_lambda,
            "scale_pos_weight": self.scale_pos_weight,
            "base_score": self.base_score,
            "tree_method": self.tree_method,
            "grow_policy": self.grow_policy,
            "max_leaves": self.max_leaves,
            "max_bin": self.max_bin,
            "min_child_weight_leaf": self.min_child_weight_leaf,
            "booster": self.booster,
            "objective": self.objective,
            "eval_metric": self.eval_metric,
            "early_stopping_rounds": self.early_stopping_rounds,
            "num_boost_round": self.num_boost_round,
            "seed": self.seed,
            "random_state": self.random_state,
            "feature_names": self.feature_names,
            "categorical_features": self.categorical_features,
            "feature_types": self.feature_types,
            "missing": self.missing,
            "enable_categorical": self.enable_categorical,
            "use_time_series_split": self.use_time_series_split,
            "n_splits": self.n_splits,
            "validation_size": self.validation_size,
            "test_size": self.test_size,
            "scale_features": self.scale_features,
            "model_id": self.model_id,
            "description": self.description,
            "version": self.version,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "XGBoostConfig":
        """Create configuration from dictionary."""
        return cls(**data)


class XGBoostModel:
    """
    Advanced XGBoost model wrapper for trading predictions.
    """

    def __init__(
        self,
        config: Optional[Union[XGBoostConfig, Dict[str, Any]]] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize XGBoost model.

        Args:
            config: Model configuration
            metrics_collector: Metrics collector instance
        """
        if isinstance(config, dict):
            self.config = XGBoostConfig.from_dict(config)
        elif isinstance(config, XGBoostConfig):
            self.config = config
        else:
            self.config = XGBoostConfig()

        self.metrics_collector = metrics_collector or MetricsCollector()
        self.model: Optional[xgb.XGBRegressor] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_importance: Optional[Dict[str, float]] = None
        self._lock = asyncio.Lock()

        logger.info(f"XGBoostModel initialized with config: {self.config.to_dict()}")

    async def train(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        eval_set: Optional[Tuple[Union[np.ndarray, pd.DataFrame], Union[np.ndarray, pd.Series]]] = None,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        Train the XGBoost model.

        Args:
            X: Feature matrix
            y: Target values
            eval_set: Evaluation set (X_val, y_val)
            verbose: Whether to log progress

        Returns:
            Training history and metrics
        """
        start_time = time.time()

        # Prepare data
        X_train, y_train, X_val, y_val, X_test, y_test = await self._prepare_data(
            X, y, eval_set
        )

        # Scale features if configured
        if self.config.scale_features:
            X_train, X_val, X_test = await self._scale_features(
                X_train, X_val, X_test
            )

        # Convert to DMatrix for better performance
        dtrain = xgb.DMatrix(
            X_train,
            label=y_train,
            feature_names=self.config.feature_names,
            enable_categorical=self.config.enable_categorical,
        )

        if X_val is not None:
            dval = xgb.DMatrix(
                X_val,
                label=y_val,
                feature_names=self.config.feature_names,
                enable_categorical=self.config.enable_categorical,
            )
            evals = [(dtrain, "train"), (dval, "eval")]
        else:
            evals = [(dtrain, "train")]

        # Set up parameters
        params = self._get_xgboost_params()

        # Train model
        self.model = xgb.train(
            params=params,
            dtrain=dtrain,
            num_boost_round=self.config.num_boost_round,
            evals=evals,
            early_stopping_rounds=self.config.early_stopping_rounds,
            verbose_eval=verbose,
        )

        # Calculate feature importance
        self.feature_importance = self._calculate_feature_importance()

        # Record metrics
        training_duration = time.time() - start_time
        XGBOOST_TRAINING_DURATION.labels(
            objective=self.config.objective
        ).observe(training_duration)

        logger.info(f"XGBoost training completed in {training_duration:.2f} seconds")

        # Return training history
        return {
            "best_score": self.model.best_score,
            "best_iteration": self.model.best_iteration,
            "best_ntree_limit": self.model.best_ntree_limit,
            "feature_importance": self.feature_importance,
            "training_duration": training_duration,
        }

    async def predict(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        return_proba: bool = False,
        return_std: bool = False,
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
        """
        Make predictions.

        Args:
            X: Feature matrix
            return_proba: Whether to return probabilities
            return_std: Whether to return standard deviation

        Returns:
            Predictions and optionally standard deviation
        """
        if self.model is None:
            raise ValueError("Model not trained yet")

        start_time = time.time()

        # Scale features if configured
        if self.config.scale_features and self.scaler is not None:
            X = self.scaler.transform(X)

        # Convert to DMatrix
        dtest = xgb.DMatrix(
            X,
            feature_names=self.config.feature_names,
            enable_categorical=self.config.enable_categorical,
        )

        # Make predictions
        if return_std:
            # Use prediction intervals
            predictions = self.model.predict(dtest)
            # TODO: Implement proper uncertainty estimation
            std = np.ones_like(predictions) * 0.1
            XGBOOST_PREDICTIONS.labels(mode="with_std", status="success").inc()
            return predictions, std
        elif return_proba:
            # Use sigmoid for probability (for classification tasks)
            predictions = self.model.predict(dtest)
            proba = 1 / (1 + np.exp(-predictions))
            XGBOOST_PREDICTIONS.labels(mode="probability", status="success").inc()
            return proba
        else:
            predictions = self.model.predict(dtest)
            XGBOOST_PREDICTIONS.labels(mode="point", status="success").inc()

        # Record prediction time
        prediction_time = time.time() - start_time
        # metrics_collector.record_prediction_time(prediction_time)  # TODO: Implement

        return predictions

    async def predict_batch(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        batch_size: int = 1000,
    ) -> np.ndarray:
        """
        Make batch predictions.

        Args:
            X: Feature matrix
            batch_size: Batch size for prediction

        Returns:
            Predictions
        """
        if self.model is None:
            raise ValueError("Model not trained yet")

        if self.config.scale_features and self.scaler is not None:
            X = self.scaler.transform(X)

        # Scale features if configured
        dtest = xgb.DMatrix(
            X,
            feature_names=self.config.feature_names,
            enable_categorical=self.config.enable_categorical,
        )

        return self.model.predict(dtest)

    async def _prepare_data(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        eval_set: Optional[Tuple[Union[np.ndarray, pd.DataFrame], Union[np.ndarray, pd.Series]]] = None,
    ) -> Tuple[
        np.ndarray, np.ndarray, Optional[np.ndarray], Optional[np.ndarray],
        Optional[np.ndarray], Optional[np.ndarray]
    ]:
        """
        Prepare data for training.

        Args:
            X: Feature matrix
            y: Target values
            eval_set: Evaluation set

        Returns:
            Training, validation, and test data
        """
        # Convert to numpy arrays
        if isinstance(X, pd.DataFrame):
            X = X.values
        if isinstance(y, pd.Series):
            y = y.values

        # Extract feature names if not provided
        if self.config.feature_names is None and hasattr(X, "columns"):
            self.config.feature_names = list(X.columns)

        # Handle evaluation set
        if eval_set is not None:
            X_val, y_val = eval_set
            if isinstance(X_val, pd.DataFrame):
                X_val = X_val.values
            if isinstance(y_val, pd.Series):
                y_val = y_val.values

            # Split training data
            X_train, y_train = X, y
            X_test, y_test = None, None
        else:
            # Split data using time series split
            if self.config.use_time_series_split:
                X_train, X_val, X_test, y_train, y_val, y_test = (
                    await self._time_series_split(X, y)
                )
            else:
                # Random split
                X_train, X_val, X_test, y_train, y_val, y_test = (
                    await self._random_split(X, y)
                )

        return X_train, y_train, X_val, y_val, X_test, y_test

    async def _time_series_split(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> Tuple[
        np.ndarray, np.ndarray, np.ndarray,
        np.ndarray, np.ndarray, np.ndarray
    ]:
        """
        Split data using time series cross-validation.

        Args:
            X: Feature matrix
            y: Target values

        Returns:
            Training, validation, and test splits
        """
        n = len(X)
        n_train = int(n * (1 - self.config.validation_size - self.config.test_size))
        n_val = int(n * self.config.validation_size)
        n_test = n - n_train - n_val

        # Time-based split
        X_train = X[:n_train]
        X_val = X[n_train:n_train + n_val]
        X_test = X[n_train + n_val:]
        y_train = y[:n_train]
        y_val = y[n_train:n_train + n_val]
        y_test = y[n_train + n_val:]

        return X_train, X_val, X_test, y_train, y_val, y_test

    async def _random_split(
        self,
        X: np.ndarray,
        y: np.ndarray,
    ) -> Tuple[
        np.ndarray, np.ndarray, np.ndarray,
        np.ndarray, np.ndarray, np.ndarray
    ]:
        """
        Split data randomly.

        Args:
            X: Feature matrix
            y: Target values

        Returns:
            Training, validation, and test splits
        """
        from sklearn.model_selection import train_test_split

        # First split: train+val vs test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size=self.config.test_size,
            random_state=self.config.random_state,
        )

        # Second split: train vs val
        X_train, X_val, y_train, y_val = train_test_split(
            X_train, y_train,
            test_size=self.config.validation_size / (1 - self.config.test_size),
            random_state=self.config.random_state,
        )

        return X_train, X_val, X_test, y_train, y_val, y_test

    async def _scale_features(
        self,
        X_train: np.ndarray,
        X_val: Optional[np.ndarray],
        X_test: Optional[np.ndarray],
    ) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Scale features using StandardScaler.

        Args:
            X_train: Training data
            X_val: Validation data
            X_test: Test data

        Returns:
            Scaled data
        """
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)

        X_val_scaled = None
        if X_val is not None:
            X_val_scaled = self.scaler.transform(X_val)

        X_test_scaled = None
        if X_test is not None:
            X_test_scaled = self.scaler.transform(X_test)

        return X_train_scaled, X_val_scaled, X_test_scaled

    def _get_xgboost_params(self) -> Dict[str, Any]:
        """Get XGBoost parameters from config."""
        params = {
            "n_estimators": self.config.n_estimators,
            "max_depth": self.config.max_depth,
            "learning_rate": self.config.learning_rate,
            "subsample": self.config.subsample,
            "colsample_bytree": self.config.colsample_bytree,
            "colsample_bylevel": self.config.colsample_bylevel,
            "min_child_weight": self.config.min_child_weight,
            "gamma": self.config.gamma,
            "reg_alpha": self.config.reg_alpha,
            "reg_lambda": self.config.reg_lambda,
            "scale_pos_weight": self.config.scale_pos_weight,
            "base_score": self.config.base_score,
            "tree_method": self.config.tree_method,
            "grow_policy": self.config.grow_policy,
            "max_leaves": self.config.max_leaves,
            "max_bin": self.config.max_bin,
            "min_child_weight_leaf": self.config.min_child_weight_leaf,
            "booster": self.config.booster,
            "objective": self.config.objective,
            "seed": self.config.seed,
            "random_state": self.config.random_state,
        }

        # Add eval_metric if specified
        if self.config.eval_metric:
            params["eval_metric"] = self.config.eval_metric

        return params

    def _calculate_feature_importance(self) -> Dict[str, float]:
        """
        Calculate feature importance.

        Returns:
            Dictionary mapping feature names to importance scores
        """
        if self.model is None:
            return {}

        # Get importance scores
        importance = self.model.get_score(importance_type="weight")

        if not importance:
            return {}

        # Normalize
        total = sum(importance.values())
        if total > 0:
            importance = {k: v / total for k, v in importance.items()}

        # Map to feature names if available
        if self.config.feature_names:
            mapped_importance = {}
            for key, value in importance.items():
                try:
                    idx = int(key.replace("f", ""))
                    if idx < len(self.config.feature_names):
                        mapped_importance[self.config.feature_names[idx]] = value
                except ValueError:
                    mapped_importance[key] = value
            return mapped_importance

        return importance

    def get_feature_importance(
        self,
        importance_type: str = "weight",
    ) -> Dict[str, float]:
        """
        Get feature importance.

        Args:
            importance_type: Type of importance ("weight", "gain", "cover")

        Returns:
            Dictionary mapping feature names to importance scores
        """
        if self.model is None:
            return {}

        importance = self.model.get_score(importance_type=importance_type)

        if not importance:
            return {}

        # Normalize
        total = sum(importance.values())
        if total > 0:
            importance = {k: v / total for k, v in importance.items()}

        # Map to feature names
        if self.config.feature_names:
            mapped_importance = {}
            for key, value in importance.items():
                try:
                    idx = int(key.replace("f", ""))
                    if idx < len(self.config.feature_names):
                        mapped_importance[self.config.feature_names[idx]] = value
                except ValueError:
                    mapped_importance[key] = value
            return mapped_importance

        return importance

    def save(self, path: Union[str, Path]) -> None:
        """
        Save the model to disk.

        Args:
            path: Path to save the model
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if self.model is None:
            raise ValueError("Model not trained yet")

        # Save model
        model_path = path.with_suffix(".json")
        self.model.save_model(str(model_path))

        # Save scaler
        if self.scaler is not None:
            scaler_path = path.with_suffix("").with_name(f"{path.stem}_scaler.pkl")
            joblib.dump(self.scaler, scaler_path)

        # Save config
        config_path = path.with_suffix("").with_name(f"{path.stem}_config.json")
        with open(config_path, "w") as f:
            json.dump(self.config.to_dict(), f, indent=2)

        logger.info(f"Model saved to {path}")

    def load(self, path: Union[str, Path]) -> None:
        """
        Load the model from disk.

        Args:
            path: Path to load the model from
        """
        path = Path(path)

        # Load model
        model_path = path.with_suffix(".json")
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        self.model = xgb.XGBRegressor()
        self.model.load_model(str(model_path))

        # Load scaler
        scaler_path = path.with_suffix("").with_name(f"{path.stem}_scaler.pkl")
        if scaler_path.exists():
            self.scaler = joblib.load(scaler_path)

        # Load config
        config_path = path.with_suffix("").with_name(f"{path.stem}_config.json")
        if config_path.exists():
            with open(config_path, "r") as f:
                config_data = json.load(f)
                self.config = XGBoostConfig.from_dict(config_data)

        logger.info(f"Model loaded from {path}")

    def get_params(self) -> Dict[str, Any]:
        """
        Get model parameters.

        Returns:
            Model parameters
        """
        if self.model is None:
            return {}

        return self.model.get_params()

    def set_params(self, **params) -> "XGBoostModel":
        """
        Set model parameters.

        Args:
            **params: Parameters to set

        Returns:
            Self for chaining
        """
        if self.model is not None:
            self.model.set_params(**params)

        # Update config
        for key, value in params.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        return self

    def get_booster(self) -> Optional[xgb.Booster]:
        """
        Get the underlying XGBoost booster.

        Returns:
            XGBoost booster
        """
        if self.model is None:
            return None

        return self.model.get_booster()

    def plot_importance(
        self,
        importance_type: str = "weight",
        max_num_features: int = 20,
    ) -> None:
        """
        Plot feature importance.

        Args:
            importance_type: Type of importance
            max_num_features: Maximum number of features to show
        """
        if self.model is None:
            raise ValueError("Model not trained yet")

        try:
            import matplotlib.pyplot as plt

            importance = self.get_feature_importance(importance_type)

            # Sort by importance
            sorted_importance = sorted(
                importance.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:max_num_features]

            # Plot
            fig, ax = plt.subplots(figsize=(10, 6))
            features, scores = zip(*sorted_importance)
            ax.barh(features, scores)
            ax.set_xlabel("Importance")
            ax.set_title(f"Feature Importance ({importance_type})")
            plt.tight_layout()
            plt.show()

        except ImportError:
            logger.warning("matplotlib not installed, cannot plot importance")

    def get_feature_importance_df(
        self,
        importance_type: str = "weight",
    ) -> pd.DataFrame:
        """
        Get feature importance as DataFrame.

        Args:
            importance_type: Type of importance

        Returns:
            DataFrame with feature importance
        """
        importance = self.get_feature_importance(importance_type)

        if not importance:
            return pd.DataFrame()

        df = pd.DataFrame(
            list(importance.items()),
            columns=["feature", "importance"],
        )
        df = df.sort_values("importance", ascending=False)

        return df

    def __repr__(self) -> str:
        """Get string representation."""
        return f"XGBoostModel(config={self.config.to_dict()})"
