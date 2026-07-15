
# ai/prediction/ensemble_predictor.py
"""
NEXUS AI TRADING SYSTEM - Ensemble Predictor
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import os
import warnings
warnings.filterwarnings('ignore')

try:
    from sklearn.ensemble import VotingRegressor, VotingClassifier
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    import lightgbm as lgb
    LGB_AVAILABLE = True
except ImportError:
    LGB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class EnsemblePredictorConfig:
    """Configuration pour Ensemble Predictor"""
    models: Optional[List[Any]] = None
    model_types: Optional[List[str]] = None
    model_configs: Optional[List[Dict[str, Any]]] = None
    weights: Optional[List[float]] = None
    ensemble_type: str = 'weighted'  # 'weighted', 'voting', 'stacking', 'average'
    meta_model_type: str = 'linear'
    meta_model_config: Optional[Dict[str, Any]] = None
    cv_folds: int = 5
    use_proba: bool = False
    n_jobs: int = -1
    random_state: Optional[int] = 42
    verbose: int = 0

    def __post_init__(self):
        if self.models is None and self.model_types is None:
            raise ValueError("models ou model_types doit être fourni")
        if self.weights is not None and self.models is not None and len(self.weights) != len(self.models):
            raise ValueError("weights doit avoir la même longueur que models")
        if self.ensemble_type not in ['weighted', 'voting', 'stacking', 'average']:
            raise ValueError(f"ensemble_type non supporté: {self.ensemble_type}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'ensemble_type': self.ensemble_type,
            'weights': self.weights,
            'meta_model_type': self.meta_model_type,
            'cv_folds': self.cv_folds,
            'use_proba': self.use_proba,
            'n_jobs': self.n_jobs,
            'random_state': self.random_state,
            'verbose': self.verbose,
        }


@dataclass
class EnsemblePredictorResult:
    predictions: np.ndarray
    individual_predictions: List[np.ndarray]
    weights: Optional[np.ndarray] = None
    confidence: Optional[np.ndarray] = None
    variance: Optional[np.ndarray] = None
    model_scores: Optional[List[float]] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'individual_predictions': [p.tolist() if isinstance(p, np.ndarray) else p for p in self.individual_predictions],
            'weights': self.weights.tolist() if isinstance(self.weights, np.ndarray) else self.weights,
            'confidence': self.confidence.tolist() if isinstance(self.confidence, np.ndarray) else self.confidence,
            'variance': self.variance.tolist() if isinstance(self.variance, np.ndarray) else self.variance,
            'model_scores': self.model_scores,
            'timestamp': self.timestamp.isoformat(),
        }


class EnsemblePredictor:
    """
    Ensemble Predictor for combining multiple models.

    Features:
    - Weighted averaging
    - Voting (for classification)
    - Stacking with meta-model
    - Individual model predictions
    - Confidence estimation
    - Feature importance

    Example:
        ```python
        from ai.models.lstm import LSTM
        from ai.models.forecasting import ProphetModel
        from ai.models.ensemble import BaggingEnsemble

        models = [
            LSTM(config1),
            LSTM(config2),
            ProphetModel(config3)
        ]

        config = EnsemblePredictorConfig(
            models=models,
            weights=[0.4, 0.3, 0.3],
            ensemble_type='weighted'
        )
        predictor = EnsemblePredictor(config)
        predictor.fit(X_train, y_train)
        predictions = predictor.predict(X_test)
        ```
    """

    def __init__(self, config: Optional[EnsemblePredictorConfig] = None):
        self.config = config or EnsemblePredictorConfig()
        self.models: List[Any] = []
        self.meta_model: Optional[Any] = None
        self.scaler: Optional[Any] = None
        self.weights: Optional[np.ndarray] = None
        self.model_scores: List[float] = []
        self.is_fitted = False
        self.feature_importance: Optional[np.ndarray] = None

        # Création des modèles
        if self.config.models:
            self.models = self.config.models
        elif self.config.model_types:
            self.models = self._create_models()

        if self.config.weights:
            self.weights = np.array(self.config.weights)

        logger.info(f"EnsemblePredictor initialisé avec {len(self.models)} modèles")

    def _create_models(self) -> List[Any]:
        """Crée les modèles selon les types configurés"""
        models = []
        model_types = self.config.model_types or []
        model_configs = self.config.model_configs or [{}] * len(model_types)

        for i, (model_type, config) in enumerate(zip(model_types, model_configs)):
            seed = self.config.random_state + i if self.config.random_state else None

            if model_type == 'linear':
                models.append(LinearRegression(**config))
            elif model_type == 'logistic':
                models.append(LogisticRegression(**config))
            elif model_type == 'xgboost' and XGB_AVAILABLE:
                models.append(xgb.XGBRegressor(random_state=seed, **config))
            elif model_type == 'lightgbm' and LGB_AVAILABLE:
                models.append(lgb.LGBMRegressor(random_state=seed, **config))
            elif model_type == 'lstm' and TORCH_AVAILABLE:
                models.append(self._create_lstm_model(config))
            else:
                raise ValueError(f"Type de modèle non supporté: {model_type}")

        return models

    def _create_lstm_model(self, config: Dict[str, Any]) -> Any:
        """Crée un modèle LSTM"""
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        class SimpleLSTM(nn.Module):
            def __init__(self, input_size=1, hidden_size=64, num_layers=2, output_size=1):
                super().__init__()
                self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
                self.fc = nn.Linear(hidden_size, output_size)

            def forward(self, x):
                lstm_out, _ = self.lstm(x)
                return self.fc(lstm_out[:, -1, :])

        input_size = config.get('input_size', 1)
        hidden_size = config.get('hidden_size', 64)
        num_layers = config.get('num_layers', 2)
        output_size = config.get('output_size', 1)

        return SimpleLSTM(input_size, hidden_size, num_layers, output_size)

    def _train_model(self, model: Any, X: np.ndarray, y: np.ndarray) -> float:
        """Entraîne un modèle individuel"""
        try:
            if hasattr(model, 'fit'):
                model.fit(X, y)
                return self._score_model(model, X, y)
            elif hasattr(model, 'fit_predict'):
                model.fit_predict(X, y)
                return self._score_model(model, X, y)
            else:
                logger.warning(f"Modèle {type(model).__name__} ne supporte pas fit")
                return 0.0
        except Exception as e:
            logger.error(f"Erreur d'entraînement: {e}")
            return 0.0

    def _score_model(self, model: Any, X: np.ndarray, y: np.ndarray) -> float:
        """Calcule le score d'un modèle"""
        try:
            predictions = model.predict(X)
            return 1 - np.mean((y - predictions) ** 2) / np.var(y)
        except:
            return 0.0

    def _fit_stacking(self, X: np.ndarray, y: np.ndarray):
        """Entraîne un ensemble de stacking"""
        if not SKLEARN_AVAILABLE:
            raise ImportError("Scikit-learn n'est pas installé")

        from sklearn.model_selection import KFold

        # Normalisation
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Prédictions CV
        kf = KFold(n_splits=self.config.cv_folds, shuffle=True, random_state=self.config.random_state)
        cv_predictions = []

        for train_idx, val_idx in kf.split(X_scaled):
            X_train_cv, X_val_cv = X_scaled[train_idx], X_scaled[val_idx]
            y_train_cv, y_val_cv = y[train_idx], y[val_idx]

            fold_preds = []
            for model in self.models:
                model_clone = self._clone_model(model)
                model_clone.fit(X_train_cv, y_train_cv)
                pred = model_clone.predict(X_val_cv)
                fold_preds.append(pred)

            cv_predictions.append(np.column_stack(fold_preds))

        X_meta = np.vstack(cv_predictions)

        # Meta-model
        self.meta_model = self._create_meta_model(X_meta.shape[1])
        self.meta_model.fit(X_meta, y)

    def _clone_model(self, model: Any) -> Any:
        """Clone un modèle"""
        if hasattr(model, '__class__'):
            clone = model.__class__()
            if hasattr(clone, '__dict__'):
                clone.__dict__ = model.__dict__.copy()
            return clone
        return model

    def _create_meta_model(self, n_features: int) -> Any:
        """Crée le méta-modèle"""
        meta_type = self.config.meta_model_type

        if meta_type == 'linear':
            return LinearRegression()
        elif meta_type == 'logistic':
            return LogisticRegression()
        elif meta_type == 'xgboost' and XGB_AVAILABLE:
            config = self.config.meta_model_config or {}
            return xgb.XGBRegressor(**config)
        else:
            return LinearRegression()

    def _compute_weights(self, model_scores: List[float]) -> np.ndarray:
        """Calcule les poids selon les scores"""
        if self.config.weights is not None:
            return np.array(self.config.weights)

        scores = np.array(model_scores)
        scores = np.maximum(scores, 0.01)
        weights = scores / scores.sum()
        return weights

    def _aggregate_predictions(self, predictions: List[np.ndarray]) -> np.ndarray:
        """Agrège les prédictions"""
        if not predictions:
            raise ValueError("Aucune prédiction à agréger")

        if self.weights is None:
            self.weights = np.ones(len(predictions)) / len(predictions)

        weights_norm = self.weights / self.weights.sum()

        if self.config.ensemble_type == 'weighted':
            weighted_preds = np.array(predictions) * weights_norm[:, np.newaxis]
            return np.sum(weighted_preds, axis=0)

        elif self.config.ensemble_type == 'average':
            return np.mean(predictions, axis=0)

        elif self.config.ensemble_type == 'voting':
            rounded_preds = np.round(np.array(predictions))
            return np.apply_along_axis(
                lambda x: np.bincount(x.astype(int)).argmax(),
                axis=0,
                arr=rounded_preds
            )

        elif self.config.ensemble_type == 'stacking':
            if self.meta_model is None:
                return np.mean(predictions, axis=0)

            X_meta = np.column_stack(predictions)
            return self.meta_model.predict(X_meta)

        else:
            return np.mean(predictions, axis=0)

    def _compute_confidence(self, predictions: List[np.ndarray]) -> np.ndarray:
        """Calcule la confiance des prédictions"""
        if len(predictions) < 2:
            return np.ones_like(predictions[0])

        variance = np.var(predictions, axis=0)

        if np.std(predictions) > 0:
            confidence = 1 - np.sqrt(variance) / (np.std(predictions) + 1e-6)
            confidence = np.clip(confidence, 0, 1)
        else:
            confidence = np.ones_like(predictions[0])

        return confidence

    def fit(self, X: Union[np.ndarray, pd.DataFrame], y: Union[np.ndarray, pd.Series]) -> 'EnsemblePredictor':
        """
        Entraîne l'ensemble de modèles.

        Args:
            X: Caractéristiques
            y: Cibles

        Returns:
            EnsemblePredictor: Instance entraînée
        """
        if isinstance(X, pd.DataFrame):
            X = X.values
        if isinstance(y, pd.Series):
            y = y.values

        self.model_scores = []

        # Entraînement des modèles
        for i, model in enumerate(self.models):
            logger.info(f"Entraînement du modèle {i+1}/{len(self.models)}")
            score = self._train_model(model, X, y)
            self.model_scores.append(score)
            logger.info(f"Score: {score:.4f}")

        # Calcul des poids
        self.weights = self._compute_weights(self.model_scores)

        # Stacking
        if self.config.ensemble_type == 'stacking':
            self._fit_stacking(X, y)

        self.is_fitted = True
        logger.info("Ensemble entraîné")

        return self

    def predict(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        return_details: bool = False
    ) -> Union[np.ndarray, EnsemblePredictorResult]:
        """
        Effectue une prédiction avec l'ensemble.

        Args:
            X: Données à prédire
            return_details: Retourner les détails

        Returns:
            np.ndarray: Prédictions
            EnsemblePredictorResult: Résultat complet
        """
        if not self.is_fitted:
            raise ValueError("L'ensemble doit être entraîné")

        if isinstance(X, pd.DataFrame):
            X = X.values

        individual_preds = []

        for model in self.models:
            try:
                pred = model.predict(X)
                individual_preds.append(pred)
            except Exception as e:
                logger.error(f"Erreur de prédiction: {e}")
                continue

        if not individual_preds:
            raise RuntimeError("Aucune prédiction disponible")

        predictions = self._aggregate_predictions(individual_preds)
        confidence = self._compute_confidence(individual_preds)
        variance = np.var(individual_preds, axis=0) if len(individual_preds) > 1 else np.zeros_like(predictions)

        result = EnsemblePredictorResult(
            predictions=predictions,
            individual_predictions=individual_preds,
            weights=self.weights,
            confidence=confidence,
            variance=variance,
            model_scores=self.model_scores,
        )

        if return_details:
            return result
        return predictions

    def predict_proba(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """
        Retourne les probabilités (pour classification).

        Args:
            X: Données à prédire

        Returns:
            np.ndarray: Probabilités
        """
        if self.config.ensemble_type == 'voting':
            probas = []
            for model in self.models:
                if hasattr(model, 'predict_proba'):
                    probas.append(model.predict_proba(X))

            if probas:
                return np.mean(probas, axis=0)

        return self.predict(X)

    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres de l'ensemble"""
        return {
            'n_models': len(self.models),
            'ensemble_type': self.config.ensemble_type,
            'weights': self.weights.tolist() if self.weights is not None else None,
            'model_scores': self.model_scores,
            'is_fitted': self.is_fitted,
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques de l'ensemble"""
        return {
            'n_models': len(self.models),
            'model_scores': self.model_scores,
            'ensemble_type': self.config.ensemble_type,
            'cv_folds': self.config.cv_folds,
            'is_fitted': self.is_fitted,
        }

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde l'ensemble.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si la sauvegarde a réussi
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'models': self.models,
                'meta_model': self.meta_model,
                'scaler': self.scaler,
                'weights': self.weights,
                'model_scores': self.model_scores,
                'is_fitted': self.is_fitted,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Ensemble sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'EnsemblePredictor':
        """
        Charge un ensemble.

        Args:
            filepath: Chemin du fichier

        Returns:
            EnsemblePredictor: Ensemble chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = EnsemblePredictorConfig(**data['config'])
            predictor = cls(config)

            predictor.models = data.get('models', [])
            predictor.meta_model = data.get('meta_model')
            predictor.scaler = data.get('scaler')
            predictor.weights = data.get('weights')
            predictor.model_scores = data.get('model_scores', [])
            predictor.is_fitted = data.get('is_fitted', False)

            logger.info(f"Ensemble chargé: {filepath}")
            return predictor

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_ensemble_predictor(
    models: Optional[List[Any]] = None,
    model_types: Optional[List[str]] = None,
    ensemble_type: str = 'weighted',
    weights: Optional[List[float]] = None,
    **kwargs
) -> EnsemblePredictor:
    """
    Factory pour créer un prédicteur d'ensemble.

    Args:
        models: Liste des modèles
        model_types: Types de modèles
        ensemble_type: Type d'ensemble
        weights: Poids des modèles
        **kwargs: Arguments supplémentaires

    Returns:
        EnsemblePredictor: Prédicteur d'ensemble
    """
    config = EnsemblePredictorConfig(
        models=models,
        model_types=model_types,
        ensemble_type=ensemble_type,
        weights=weights,
        **kwargs
    )
    return EnsemblePredictor(config)


__all__ = [
    'EnsemblePredictor',
    'EnsemblePredictorConfig',
    'EnsemblePredictorResult',
    'create_ensemble_predictor',
]
