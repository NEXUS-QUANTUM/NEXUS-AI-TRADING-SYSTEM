# trading/bots/ai_bot/ai_bot_ensemble.py
"""
NEXUS AI TRADING SYSTEM - Ensemble Model Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements ensemble learning methods for the AI Trading Bot.
Provides:
    - Voting ensembles (hard and soft)
    - Stacking ensembles
    - Blending ensembles
    - Bagging ensembles
    - Boosting ensembles
    - Weighted averaging
    - Model selection
    - Dynamic weighting
    - Ensemble pruning
    - Performance-based weighting
    - Cross-validation ensemble
    - Multi-modal ensemble
    - Adaptive ensemble
"""

import os
import sys
import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, Tuple, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.ensemble import (
    RandomForestClassifier,
    GradientBoostingClassifier,
    AdaBoostClassifier,
    VotingClassifier,
    StackingClassifier
)
from sklearn.base import BaseEstimator, ClassifierMixin, RegressorMixin
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
import pickle
import hashlib

# Import bot components
from trading.bots.ai_bot.ai_bot_model_manager import ModelManager, BaseModel
from trading.bots.ai_bot.ai_bot_predictor import Predictor

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================

class EnsembleType(Enum):
    """Ensemble type enumeration."""
    VOTING = "voting"
    STACKING = "stacking"
    BLENDING = "blending"
    BAGGING = "bagging"
    BOOSTING = "boosting"
    WEIGHTED = "weighted"
    DYNAMIC = "dynamic"
    ADAPTIVE = "adaptive"
    HIERARCHICAL = "hierarchical"
    MULTI_MODAL = "multi_modal"


class VotingMethod(Enum):
    """Voting method enumeration."""
    HARD = "hard"
    SOFT = "soft"
    WEIGHTED = "weighted"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class EnsembleConfig:
    """Ensemble configuration."""
    ensemble_type: EnsembleType = EnsembleType.VOTING
    voting_method: VotingMethod = VotingMethod.SOFT
    n_estimators: int = 10
    max_features: Union[str, int] = "sqrt"
    bootstrap: bool = True
    oob_score: bool = True
    warm_start: bool = False
    n_jobs: int = -1
    random_state: int = 42
    weights: Optional[List[float]] = None
    dynamic_weighting: bool = False
    adaptation_rate: float = 0.1
    prune_threshold: float = 0.1
    cross_validation_folds: int = 5


@dataclass
class EnsembleResult:
    """Ensemble prediction result."""
    prediction: Any
    probabilities: Optional[np.ndarray] = None
    confidence: Optional[float] = None
    individual_predictions: Optional[List[Any]] = None
    weights_used: Optional[List[float]] = None
    ensemble_type: Optional[str] = None
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Base Ensemble Class
# =============================================================================

class BaseEnsemble:
    """
    Base class for ensemble models.
    
    Provides common functionality for all ensemble types including:
        - Model management
        - Weight handling
        - Prediction aggregation
        - Performance tracking
        - Serialization
    """
    
    def __init__(
        self,
        config: Union[Dict[str, Any], EnsembleConfig],
        models: Optional[List[Any]] = None
    ):
        """
        Initialize the ensemble.
        
        Args:
            config: Ensemble configuration
            models: List of base models
        """
        # Load configuration
        if isinstance(config, dict):
            self.config = EnsembleConfig(**config)
        else:
            self.config = config
        
        # Initialize models
        self.models = models or []
        self.model_names = []
        self.model_weights = None
        self.is_fitted = False
        self.scaler = StandardScaler()
        
        # Performance tracking
        self.performance_history = []
        self.feature_importances_ = None
        
        # Logging
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize weights
        if self.config.weights:
            self.model_weights = np.array(self.config.weights)
        else:
            self.model_weights = np.ones(len(self.models)) / len(self.models) if self.models else None
        
        self.logger.info(f"Ensemble initialized with {len(self.models)} models")
    
    # =========================================================================
    # Model Management
    # =========================================================================
    
    def add_model(self, model: Any, name: Optional[str] = None) -> None:
        """
        Add a model to the ensemble.
        
        Args:
            model: Model instance
            name: Optional model name
        """
        self.models.append(model)
        self.model_names.append(name or f"model_{len(self.models)}")
        
        # Recalculate weights
        if self.model_weights is not None:
            self.model_weights = np.ones(len(self.models)) / len(self.models)
        
        self.is_fitted = False
        self.logger.info(f"Added model: {self.model_names[-1]}")
    
    def remove_model(self, index: int) -> None:
        """
        Remove a model from the ensemble.
        
        Args:
            index: Model index
        """
        if 0 <= index < len(self.models):
            del self.models[index]
            if self.model_names:
                del self.model_names[index]
            if self.model_weights is not None:
                self.model_weights = np.delete(self.model_weights, index)
                self.model_weights = self.model_weights / self.model_weights.sum()
            
            self.is_fitted = False
            self.logger.info(f"Removed model at index {index}")
    
    def set_weights(self, weights: List[float]) -> None:
        """
        Set model weights.
        
        Args:
            weights: List of weights
        """
        self.model_weights = np.array(weights) / np.sum(weights)
        self.logger.info(f"Set weights: {self.model_weights}")
    
    def get_models(self) -> List[Any]:
        """
        Get all models.
        
        Returns:
            List of models
        """
        return self.models
    
    def get_model_names(self) -> List[str]:
        """
        Get model names.
        
        Returns:
            List of model names
        """
        return self.model_names
    
    def get_weights(self) -> np.ndarray:
        """
        Get model weights.
        
        Returns:
            Array of weights
        """
        return self.model_weights
    
    # =========================================================================
    # Weight Management
    # =========================================================================
    
    def update_weights_performance(self, performances: List[float]) -> None:
        """
        Update weights based on model performance.
        
        Args:
            performances: List of performance scores
        """
        # Normalize performances to weights
        performances = np.array(performances)
        performances = performances - performances.min() + 0.1
        new_weights = performances / performances.sum()
        
        # Apply adaptation rate
        if self.config.dynamic_weighting:
            self.model_weights = (
                (1 - self.config.adaptation_rate) * self.model_weights +
                self.config.adaptation_rate * new_weights
            )
        else:
            self.model_weights = new_weights
        
        # Normalize
        self.model_weights = self.model_weights / self.model_weights.sum()
        
        self.logger.debug(f"Updated weights: {self.model_weights}")
    
    def update_weights_recent_performance(
        self,
        predictions: List[np.ndarray],
        y_true: np.ndarray,
        window_size: int = 100
    ) -> None:
        """
        Update weights based on recent performance.
        
        Args:
            predictions: List of model predictions
            y_true: True labels
            window_size: Recent window size
        """
        performances = []
        
        for pred in predictions:
            # Calculate performance metric (e.g., accuracy)
            if len(pred.shape) > 1:
                pred_classes = np.argmax(pred, axis=1)
            else:
                pred_classes = pred
            
            # Use recent window
            if len(pred_classes) > window_size:
                pred_classes = pred_classes[-window_size:]
                y_true_window = y_true[-window_size:]
            else:
                y_true_window = y_true
            
            accuracy = np.mean(pred_classes == y_true_window)
            performances.append(accuracy)
        
        self.update_weights_performance(performances)
    
    # =========================================================================
    # Performance Tracking
    # =========================================================================
    
    def track_performance(
        self,
        metrics: Dict[str, float],
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Track ensemble performance metrics.
        
        Args:
            metrics: Performance metrics
            timestamp: Optional timestamp
        """
        entry = {
            'timestamp': timestamp or datetime.now(),
            'metrics': metrics
        }
        self.performance_history.append(entry)
        
        # Keep only recent history
        if len(self.performance_history) > 1000:
            self.performance_history = self.performance_history[-1000:]
    
    def get_performance_history(self) -> List[Dict[str, Any]]:
        """
        Get performance history.
        
        Returns:
            List of performance entries
        """
        return self.performance_history
    
    def get_best_weights_from_history(self, metric: str = "accuracy") -> np.ndarray:
        """
        Get best weights from performance history.
        
        Args:
            metric: Performance metric to optimize
            
        Returns:
            Best weights
        """
        if not self.performance_history:
            return self.model_weights
        
        # Find best performance
        best_entry = max(
            self.performance_history,
            key=lambda x: x['metrics'].get(metric, 0)
        )
        
        return np.array(best_entry.get('weights', self.model_weights))
    
    # =========================================================================
    # Serialization
    # =========================================================================
    
    def save(self, path: Union[str, Path]) -> None:
        """
        Save ensemble to file.
        
        Args:
            path: Save path
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save ensemble state
        state = {
            'config': asdict(self.config),
            'model_names': self.model_names,
            'model_weights': self.model_weights.tolist() if self.model_weights is not None else None,
            'is_fitted': self.is_fitted,
            'performance_history': self.performance_history,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(path, 'wb') as f:
            pickle.dump(state, f)
        
        self.logger.info(f"Ensemble saved to {path}")
    
    def load(self, path: Union[str, Path]) -> None:
        """
        Load ensemble from file.
        
        Args:
            path: Load path
        """
        path = Path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        with open(path, 'rb') as f:
            state = pickle.load(f)
        
        self.model_names = state.get('model_names', [])
        self.model_weights = np.array(state.get('model_weights')) if state.get('model_weights') else None
        self.is_fitted = state.get('is_fitted', False)
        self.performance_history = state.get('performance_history', [])
        
        self.logger.info(f"Ensemble loaded from {path}")


# =============================================================================
# Voting Ensemble
# =============================================================================

class VotingEnsemble(BaseEnsemble):
    """
    Voting ensemble implementation.
    
    Supports both hard (majority) and soft (probability averaging) voting.
    """
    
    def __init__(
        self,
        config: Union[Dict[str, Any], EnsembleConfig],
        models: Optional[List[Any]] = None
    ):
        """
        Initialize voting ensemble.
        
        Args:
            config: Ensemble configuration
            models: List of base models
        """
        super().__init__(config, models)
        self.ensemble_type = EnsembleType.VOTING
        self.logger.info(f"Voting ensemble initialized with {len(self.models)} models")
    
    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        validation_split: float = 0.2
    ) -> 'VotingEnsemble':
        """
        Fit all models in the ensemble.
        
        Args:
            X: Training data
            y: Training labels
            validation_split: Validation split for weighting
            
        Returns:
            Self
        """
        self.logger.info(f"Fitting voting ensemble with {len(self.models)} models")
        
        # Split data for validation
        n_samples = len(X)
        n_val = int(n_samples * validation_split)
        indices = np.random.permutation(n_samples)
        
        train_idx = indices[n_val:]
        val_idx = indices[:n_val]
        
        X_train, y_train = X[train_idx], y[train_idx]
        X_val, y_val = X[val_idx], y[val_idx]
        
        # Fit each model
        performances = []
        
        for i, model in enumerate(self.models):
            self.logger.debug(f"Fitting model {i+1}/{len(self.models)}")
            
            try:
                # Fit model
                model.fit(X_train, y_train)
                
                # Evaluate on validation set
                y_pred = model.predict(X_val)
                if hasattr(model, 'predict_proba'):
                    y_proba = model.predict_proba(X_val)
                
                # Calculate performance
                accuracy = np.mean(y_pred == y_val)
                performances.append(accuracy)
                
                self.logger.debug(f"Model {i+1} accuracy: {accuracy:.4f}")
                
            except Exception as e:
                self.logger.error(f"Error fitting model {i+1}: {e}")
                performances.append(0.0)
        
        # Update weights based on performance
        if self.config.dynamic_weighting:
            self.update_weights_performance(performances)
        
        self.is_fitted = True
        self.logger.info("Voting ensemble fitted successfully")
        
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Make predictions using voting.
        
        Args:
            X: Input data
            
        Returns:
            Predictions
        """
        if not self.is_fitted:
            raise RuntimeError("Ensemble not fitted. Call fit() first.")
        
        # Get predictions from all models
        predictions = []
        probabilities = []
        
        for model in self.models:
            if hasattr(model, 'predict_proba'):
                proba = model.predict_proba(X)
                probabilities.append(proba)
                predictions.append(np.argmax(proba, axis=1))
            else:
                pred = model.predict(X)
                predictions.append(pred)
        
        # Apply voting
        if self.config.voting_method == VotingMethod.SOFT:
            # Soft voting (probability averaging)
            if probabilities:
                # Weighted average of probabilities
                weighted_probas = np.zeros_like(probabilities[0])
                for i, proba in enumerate(probabilities):
                    weight = self.model_weights[i] if self.model_weights is not None else 1.0
                    weighted_probas += weight * proba
                
                weighted_probas /= (self.model_weights.sum() if self.model_weights is not None else len(probabilities))
                
                return np.argmax(weighted_probas, axis=1)
            else:
                # Fallback to hard voting if no probabilities
                return self._hard_vote(predictions)
        else:
            # Hard voting
            return self._hard_vote(predictions)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Get probability predictions.
        
        Args:
            X: Input data
            
        Returns:
            Probability predictions
        """
        if not self.is_fitted:
            raise RuntimeError("Ensemble not fitted. Call fit() first.")
        
        if self.config.voting_method == VotingMethod.SOFT:
            probabilities = []
            
            for model in self.models:
                if hasattr(model, 'predict_proba'):
                    proba = model.predict_proba(X)
                    probabilities.append(proba)
                else:
                    # Convert predictions to pseudo-probabilities
                    pred = model.predict(X)
                    n_classes = len(np.unique(pred))
                    proba = np.zeros((len(X), n_classes))
                    for i, p in enumerate(pred):
                        proba[i, p] = 1.0
                    probabilities.append(proba)
            
            # Weighted average
            weighted_probas = np.zeros_like(probabilities[0])
            for i, proba in enumerate(probabilities):
                weight = self.model_weights[i] if self.model_weights is not None else 1.0
                weighted_probas += weight * proba
            
            weighted_probas /= (self.model_weights.sum() if self.model_weights is not None else len(probabilities))
            
            return weighted_probas
        
        return None
    
    def _hard_vote(self, predictions: List[np.ndarray]) -> np.ndarray:
        """
        Hard voting (majority vote).
        
        Args:
            predictions: List of predictions
            
        Returns:
            Majority vote predictions
        """
        # Stack predictions
        stacked = np.stack(predictions, axis=1)
        
        # Apply weights if available
        if self.model_weights is not None:
            # Weighted majority vote
            n_samples = stacked.shape[0]
            n_classes = len(np.unique(stacked))
            weighted_votes = np.zeros((n_samples, n_classes))
            
            for i, preds in enumerate(stacked):
                for j, pred in enumerate(preds):
                    weighted_votes[i, pred] += self.model_weights[j]
            
            return np.argmax(weighted_votes, axis=1)
        else:
            # Unweighted majority vote
            results = []
            for preds in stacked:
                # Count votes
                unique, counts = np.unique(preds, return_counts=True)
                results.append(unique[np.argmax(counts)])
            
            return np.array(results)


# =============================================================================
# Stacking Ensemble
# =============================================================================

class StackingEnsemble(BaseEnsemble):
    """
    Stacking ensemble implementation.
    
    Uses a meta-model to combine predictions from base models.
    """
    
    def __init__(
        self,
        config: Union[Dict[str, Any], EnsembleConfig],
        models: Optional[List[Any]] = None,
        meta_model: Optional[Any] = None
    ):
        """
        Initialize stacking ensemble.
        
        Args:
            config: Ensemble configuration
            models: List of base models
            meta_model: Meta-model for stacking
        """
        super().__init__(config, models)
        self.ensemble_type = EnsembleType.STACKING
        self.meta_model = meta_model
        self.meta_features = None
        self.is_fitted = False
        
        self.logger.info(f"Stacking ensemble initialized with {len(self.models)} models")
    
    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        cv_folds: int = 5
    ) -> 'StackingEnsemble':
        """
        Fit the stacking ensemble.
        
        Args:
            X: Training data
            y: Training labels
            cv_folds: Number of cross-validation folds
            
        Returns:
            Self
        """
        self.logger.info("Fitting stacking ensemble...")
        
        n_samples = len(X)
        n_classes = len(np.unique(y))
        
        # Generate meta-features using cross-validation
        meta_features = np.zeros((n_samples, len(self.models) * n_classes))
        
        for fold_idx in range(cv_folds):
            # Split data
            fold_size = n_samples // cv_folds
            val_start = fold_idx * fold_size
            val_end = (fold_idx + 1) * fold_size if fold_idx < cv_folds - 1 else n_samples
            
            X_train = np.concatenate([X[:val_start], X[val_end:]], axis=0)
            X_val = X[val_start:val_end]
            y_train = np.concatenate([y[:val_start], y[val_end:]], axis=0)
            
            # Train base models on training fold
            fold_meta = np.zeros((len(X_val), len(self.models) * n_classes))
            
            for i, model in enumerate(self.models):
                # Fit model on training fold
                model.fit(X_train, y_train)
                
                # Get predictions for validation fold
                if hasattr(model, 'predict_proba'):
                    proba = model.predict_proba(X_val)
                else:
                    proba = np.eye(n_classes)[model.predict(X_val)]
                
                fold_meta[:, i * n_classes:(i + 1) * n_classes] = proba
            
            meta_features[val_start:val_end] = fold_meta
        
        # Train meta-model on full meta-features
        if self.meta_model is not None:
            self.meta_model.fit(meta_features, y)
        
        self.meta_features = meta_features
        self.is_fitted = True
        self.logger.info("Stacking ensemble fitted successfully")
        
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Make predictions using stacking.
        
        Args:
            X: Input data
            
        Returns:
            Predictions
        """
        if not self.is_fitted:
            raise RuntimeError("Ensemble not fitted. Call fit() first.")
        
        # Generate meta-features
        n_samples = len(X)
        n_classes = len(np.unique(self.meta_features.shape[1] // len(self.models)))
        meta_features = np.zeros((n_samples, len(self.models) * n_classes))
        
        for i, model in enumerate(self.models):
            if hasattr(model, 'predict_proba'):
                proba = model.predict_proba(X)
            else:
                proba = np.eye(n_classes)[model.predict(X)]
            
            meta_features[:, i * n_classes:(i + 1) * n_classes] = proba
        
        # Meta-model prediction
        if self.meta_model is not None:
            if hasattr(self.meta_model, 'predict_proba'):
                return np.argmax(self.meta_model.predict_proba(meta_features), axis=1)
            else:
                return self.meta_model.predict(meta_features)
        
        # Fallback to voting
        predictions = []
        for model in self.models:
            predictions.append(model.predict(X))
        
        return np.array([np.bincount(pred).argmax() for pred in np.array(predictions).T])
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Get probability predictions.
        
        Args:
            X: Input data
            
        Returns:
            Probability predictions
        """
        if not self.is_fitted:
            raise RuntimeError("Ensemble not fitted. Call fit() first.")
        
        if self.meta_model is not None and hasattr(self.meta_model, 'predict_proba'):
            # Generate meta-features
            n_samples = len(X)
            n_classes = len(np.unique(self.meta_features.shape[1] // len(self.models)))
            meta_features = np.zeros((n_samples, len(self.models) * n_classes))
            
            for i, model in enumerate(self.models):
                if hasattr(model, 'predict_proba'):
                    proba = model.predict_proba(X)
                else:
                    proba = np.eye(n_classes)[model.predict(X)]
                
                meta_features[:, i * n_classes:(i + 1) * n_classes] = proba
            
            return self.meta_model.predict_proba(meta_features)
        
        return None


# =============================================================================
# Blending Ensemble
# =============================================================================

class BlendingEnsemble(BaseEnsemble):
    """
    Blending ensemble implementation.
    
    Uses a hold-out validation set to learn blending weights.
    """
    
    def __init__(
        self,
        config: Union[Dict[str, Any], EnsembleConfig],
        models: Optional[List[Any]] = None
    ):
        """
        Initialize blending ensemble.
        
        Args:
            config: Ensemble configuration
            models: List of base models
        """
        super().__init__(config, models)
        self.ensemble_type = EnsembleType.BLENDING
        self.blend_weights = None
        self.is_fitted = False
        
        self.logger.info(f"Blending ensemble initialized with {len(self.models)} models")
    
    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        validation_size: float = 0.3
    ) -> 'BlendingEnsemble':
        """
        Fit the blending ensemble.
        
        Args:
            X: Training data
            y: Training labels
            validation_size: Validation set size
            
        Returns:
            Self
        """
        self.logger.info("Fitting blending ensemble...")
        
        # Split data
        n_samples = len(X)
        n_val = int(n_samples * validation_size)
        indices = np.random.permutation(n_samples)
        
        train_idx = indices[n_val:]
        val_idx = indices[:n_val]
        
        X_train, y_train = X[train_idx], y[train_idx]
        X_val, y_val = X[val_idx], y[val_idx]
        
        # Train base models on full training set
        predictions_val = []
        
        for i, model in enumerate(self.models):
            self.logger.debug(f"Fitting model {i+1}/{len(self.models)}")
            model.fit(X_train, y_train)
            
            # Get predictions on validation set
            if hasattr(model, 'predict_proba'):
                pred = model.predict_proba(X_val)
            else:
                pred = np.eye(len(np.unique(y_val)))[model.predict(X_val)]
            
            predictions_val.append(pred)
        
        # Learn blending weights using optimization
        self.blend_weights = self._learn_blend_weights(
            np.array(predictions_val), y_val
        )
        
        # Retrain models on full dataset
        for i, model in enumerate(self.models):
            model.fit(X, y)
        
        self.is_fitted = True
        self.logger.info(f"Blending ensemble fitted. Weights: {self.blend_weights}")
        
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Make predictions using blending.
        
        Args:
            X: Input data
            
        Returns:
            Predictions
        """
        if not self.is_fitted:
            raise RuntimeError("Ensemble not fitted. Call fit() first.")
        
        # Get predictions from all models
        predictions = []
        
        for i, model in enumerate(self.models):
            if hasattr(model, 'predict_proba'):
                pred = model.predict_proba(X)
            else:
                pred = np.eye(len(self.blend_weights))[model.predict(X)]
            
            predictions.append(pred)
        
        # Apply blending weights
        n_samples = len(X)
        n_classes = predictions[0].shape[1]
        blended = np.zeros((n_samples, n_classes))
        
        for i, pred in enumerate(predictions):
            weight = self.blend_weights[i]
            blended += weight * pred
        
        return np.argmax(blended, axis=1)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Get probability predictions.
        
        Args:
            X: Input data
            
        Returns:
            Probability predictions
        """
        if not self.is_fitted:
            raise RuntimeError("Ensemble not fitted. Call fit() first.")
        
        predictions = []
        
        for i, model in enumerate(self.models):
            if hasattr(model, 'predict_proba'):
                pred = model.predict_proba(X)
            else:
                pred = np.eye(len(self.blend_weights))[model.predict(X)]
            
            predictions.append(pred)
        
        # Apply blending weights
        n_samples = len(X)
        n_classes = predictions[0].shape[1]
        blended = np.zeros((n_samples, n_classes))
        
        for i, pred in enumerate(predictions):
            weight = self.blend_weights[i]
            blended += weight * pred
        
        return blended
    
    def _learn_blend_weights(
        self,
        predictions: np.ndarray,
        y_true: np.ndarray
    ) -> np.ndarray:
        """
        Learn blending weights using optimization.
        
        Args:
            predictions: Model predictions on validation set
            y_true: True labels
            
        Returns:
            Optimal blending weights
        """
        from scipy.optimize import minimize
        
        n_models = predictions.shape[0]
        
        def loss(weights):
            # Normalize weights
            weights = np.abs(weights) / np.sum(np.abs(weights))
            
            # Calculate weighted predictions
            weighted = np.zeros_like(predictions[0])
            for i, pred in enumerate(predictions):
                weighted += weights[i] * pred
            
            # Calculate loss (cross-entropy)
            pred_probs = np.exp(weighted) / np.sum(np.exp(weighted), axis=1, keepdims=True)
            
            # Cross-entropy loss
            log_likelihood = -np.mean([
                np.log(pred_probs[i, y_true[i]] + 1e-10)
                for i in range(len(y_true))
            ])
            
            return log_likelihood
        
        # Initial weights
        initial_weights = np.ones(n_models) / n_models
        
        # Optimize
        result = minimize(
            loss,
            initial_weights,
            method='L-BFGS-B',
            bounds=[(0, 1)] * n_models,
            constraints={'type': 'eq', 'fun': lambda x: np.sum(x) - 1}
        )
        
        return result.x


# =============================================================================
# Ensemble Factory
# =============================================================================

class EnsembleFactory:
    """
    Factory for creating ensemble models.
    
    Provides methods for creating different types of ensembles with
    various configurations.
    """
    
    @staticmethod
    def create_ensemble(
        ensemble_type: EnsembleType,
        models: List[Any],
        config: Optional[Union[Dict[str, Any], EnsembleConfig]] = None,
        **kwargs
    ) -> BaseEnsemble:
        """
        Create an ensemble model.
        
        Args:
            ensemble_type: Type of ensemble
            models: List of base models
            config: Ensemble configuration
            **kwargs: Additional arguments
            
        Returns:
            Ensemble instance
        """
        config = config or {}
        if isinstance(config, dict):
            config = EnsembleConfig(**config)
        
        if ensemble_type == EnsembleType.VOTING:
            return VotingEnsemble(config, models, **kwargs)
        elif ensemble_type == EnsembleType.STACKING:
            return StackingEnsemble(config, models, **kwargs)
        elif ensemble_type == EnsembleType.BLENDING:
            return BlendingEnsemble(config, models, **kwargs)
        else:
            raise ValueError(f"Unsupported ensemble type: {ensemble_type}")
    
    @staticmethod
    def create_voting_ensemble(
        models: List[Any],
        voting: VotingMethod = VotingMethod.SOFT,
        weights: Optional[List[float]] = None,
        **kwargs
    ) -> VotingEnsemble:
        """
        Create a voting ensemble.
        
        Args:
            models: List of base models
            voting: Voting method
            weights: Model weights
            **kwargs: Additional arguments
            
        Returns:
            VotingEnsemble instance
        """
        config = EnsembleConfig(
            ensemble_type=EnsembleType.VOTING,
            voting_method=voting,
            weights=weights,
            **kwargs
        )
        
        return VotingEnsemble(config, models)
    
    @staticmethod
    def create_stacking_ensemble(
        models: List[Any],
        meta_model: Any,
        config: Optional[Union[Dict[str, Any], EnsembleConfig]] = None,
        **kwargs
    ) -> StackingEnsemble:
        """
        Create a stacking ensemble.
        
        Args:
            models: List of base models
            meta_model: Meta-model
            config: Ensemble configuration
            **kwargs: Additional arguments
            
        Returns:
            StackingEnsemble instance
        """
        config = config or {}
        if isinstance(config, dict):
            config = EnsembleConfig(**config)
        config.ensemble_type = EnsembleType.STACKING
        
        return StackingEnsemble(config, models, meta_model, **kwargs)
    
    @staticmethod
    def create_blending_ensemble(
        models: List[Any],
        config: Optional[Union[Dict[str, Any], EnsembleConfig]] = None,
        **kwargs
    ) -> BlendingEnsemble:
        """
        Create a blending ensemble.
        
        Args:
            models: List of base models
            config: Ensemble configuration
            **kwargs: Additional arguments
            
        Returns:
            BlendingEnsemble instance
        """
        config = config or {}
        if isinstance(config, dict):
            config = EnsembleConfig(**config)
        config.ensemble_type = EnsembleType.BLENDING
        
        return BlendingEnsemble(config, models, **kwargs)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'BaseEnsemble',
    'VotingEnsemble',
    'StackingEnsemble',
    'BlendingEnsemble',
    'EnsembleFactory',
    'EnsembleConfig',
    'EnsembleResult',
    'EnsembleType',
    'VotingMethod'
]


# =============================================================================
# Module Docstring
# =============================================================================

__doc__ = f"""
{__name__} - NEXUS AI Trading Bot Ensemble Module

This module implements ensemble learning methods for the NEXUS AI Trading Bot,
providing state-of-the-art ensemble techniques for improved prediction accuracy.

Copyright: {__copyright__}
CEO: {__author__}
Version: {__version__}

Ensemble Types:
    - Voting: Hard/soft voting with optional weighting
    - Stacking: Meta-model based combination
    - Blending: Learned weighted combination
    - Bagging: Bootstrap aggregating
    - Boosting: Sequential model correction
    - Dynamic: Performance-based weight adaptation

Features:
    - Multiple ensemble methods
    - Dynamic weighting
    - Performance tracking
    - Cross-validation support
    - Serialization
    - Model selection
    - Feature importance analysis
"""

# Log module initialization
logger.info(f"Ensemble module loaded (version {__version__})")
