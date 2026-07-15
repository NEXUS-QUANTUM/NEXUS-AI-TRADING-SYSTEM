# ai/models/base_model.py
"""
NEXUS AI TRADING SYSTEM - Base Model Classes
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import os
import json
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """Métadonnées d'un modèle"""
    name: str
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.now)
    trained_at: Optional[datetime] = None
    model_type: str = ""
    input_shape: Optional[Tuple[int, ...]] = None
    output_shape: Optional[Tuple[int, ...]] = None
    parameters: int = 0
    training_time: float = 0.0
    framework: str = "pytorch"
    description: str = ""
    author: str = "NEXUS QUANTUM LTD"
    license: str = "Proprietary"
    tags: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    hyperparameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'version': self.version,
            'created_at': self.created_at.isoformat(),
            'trained_at': self.trained_at.isoformat() if self.trained_at else None,
            'model_type': self.model_type,
            'input_shape': self.input_shape,
            'output_shape': self.output_shape,
            'parameters': self.parameters,
            'training_time': self.training_time,
            'framework': self.framework,
            'description': self.description,
            'author': self.author,
            'license': self.license,
            'tags': self.tags,
            'metrics': self.metrics,
            'hyperparameters': self.hyperparameters,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelMetadata':
        return cls(
            name=data.get('name', ''),
            version=data.get('version', '1.0.0'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now(),
            trained_at=datetime.fromisoformat(data['trained_at']) if data.get('trained_at') else None,
            model_type=data.get('model_type', ''),
            input_shape=tuple(data['input_shape']) if data.get('input_shape') else None,
            output_shape=tuple(data['output_shape']) if data.get('output_shape') else None,
            parameters=data.get('parameters', 0),
            training_time=data.get('training_time', 0.0),
            framework=data.get('framework', 'pytorch'),
            description=data.get('description', ''),
            author=data.get('author', 'NEXUS QUANTUM LTD'),
            license=data.get('license', 'Proprietary'),
            tags=data.get('tags', []),
            metrics=data.get('metrics', {}),
            hyperparameters=data.get('hyperparameters', {}),
        )


@dataclass
class PredictionResult:
    """Résultat de prédiction"""
    predictions: np.ndarray
    confidence: Optional[np.ndarray] = None
    uncertainty: Optional[np.ndarray] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'confidence': self.confidence.tolist() if isinstance(self.confidence, np.ndarray) else self.confidence,
            'uncertainty': self.uncertainty.tolist() if isinstance(self.uncertainty, np.ndarray) else self.uncertainty,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat(),
        }


class BaseModel(ABC):
    """
    Classe de base abstraite pour tous les modèles de l'IA de trading.
    
    Cette classe définit l'interface commune pour tous les modèles :
    - Entraînement (fit)
    - Prédiction (predict)
    - Sauvegarde/Chargement (save/load)
    - Métadonnées (get_metadata)
    - Métriques (get_metrics)
    
    Tous les modèles du système héritent de cette classe.
    """

    def __init__(self, name: str = "BaseModel", **kwargs):
        self.name = name
        self.metadata = ModelMetadata(
            name=name,
            model_type=self.__class__.__name__,
            hyperparameters=kwargs,
            tags=['base']
        )
        self.is_fitted = False
        self._version = kwargs.get('version', '1.0.0')
        self._framework = kwargs.get('framework', 'pytorch')
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def fit(self, X: Union[np.ndarray, pd.DataFrame], y: Union[np.ndarray, pd.Series], **kwargs) -> 'BaseModel':
        """
        Entraîne le modèle sur les données.
        
        Args:
            X: Caractéristiques d'entraînement
            y: Cibles d'entraînement
            **kwargs: Arguments supplémentaires
        
        Returns:
            BaseModel: Instance entraînée
        """
        pass

    @abstractmethod
    def predict(self, X: Union[np.ndarray, pd.DataFrame], **kwargs) -> np.ndarray:
        """
        Effectue une prédiction.
        
        Args:
            X: Données à prédire
            **kwargs: Arguments supplémentaires
        
        Returns:
            np.ndarray: Prédictions
        """
        pass

    @abstractmethod
    def predict_proba(self, X: Union[np.ndarray, pd.DataFrame], **kwargs) -> np.ndarray:
        """
        Retourne les probabilités de prédiction (pour classification).
        
        Args:
            X: Données à prédire
            **kwargs: Arguments supplémentaires
        
        Returns:
            np.ndarray: Probabilités
        """
        pass

    @abstractmethod
    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres du modèle"""
        pass

    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques du modèle"""
        pass

    def fit_predict(self, X: Union[np.ndarray, pd.DataFrame], y: Union[np.ndarray, pd.Series], **kwargs) -> np.ndarray:
        """
        Entraîne le modèle et effectue une prédiction.
        
        Args:
            X: Caractéristiques
            y: Cibles
            **kwargs: Arguments supplémentaires
        
        Returns:
            np.ndarray: Prédictions
        """
        self.fit(X, y, **kwargs)
        return self.predict(X, **kwargs)

    def score(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        metric: str = 'r2'
    ) -> float:
        """
        Calcule le score du modèle sur des données de test.
        
        Args:
            X: Caractéristiques
            y: Cibles
            metric: Métrique ('r2', 'mse', 'mae', 'accuracy')
        
        Returns:
            float: Score
        """
        predictions = self.predict(X)

        if metric == 'r2':
            try:
                from sklearn.metrics import r2_score
                return r2_score(y, predictions)
            except ImportError:
                return 1 - np.mean((y - predictions) ** 2) / np.var(y)

        elif metric == 'mse':
            try:
                from sklearn.metrics import mean_squared_error
                return mean_squared_error(y, predictions)
            except ImportError:
                return np.mean((y - predictions) ** 2)

        elif metric == 'mae':
            try:
                from sklearn.metrics import mean_absolute_error
                return mean_absolute_error(y, predictions)
            except ImportError:
                return np.mean(np.abs(y - predictions))

        elif metric == 'accuracy':
            return np.mean(np.round(predictions) == y)

        else:
            raise ValueError(f"Métrique non supportée: {metric}")

    def _validate_data(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Optional[Union[np.ndarray, pd.Series]] = None
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Valide et convertit les données"""
        if isinstance(X, pd.DataFrame):
            X = X.values
        elif isinstance(X, list):
            X = np.array(X)

        if not isinstance(X, np.ndarray):
            raise TypeError("X doit être un tableau numpy, pandas DataFrame ou liste")

        if X.ndim == 1:
            X = X.reshape(-1, 1)

        if y is not None:
            if isinstance(y, pd.Series):
                y = y.values
            elif isinstance(y, list):
                y = np.array(y)

            if not isinstance(y, np.ndarray):
                raise TypeError("y doit être un tableau numpy, pandas Series ou liste")

            if len(X) != len(y):
                raise ValueError("X et y doivent avoir la même longueur")

            return X, y

        return X, None

    def _normalize_data(self, data: np.ndarray) -> np.ndarray:
        """Normalise les données"""
        mean = np.mean(data)
        std = np.std(data) + 1e-8
        return (data - mean) / std

    def _denormalize_data(self, data: np.ndarray, mean: float, std: float) -> np.ndarray:
        """Dénormalise les données"""
        return data * std + mean

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde le modèle sur le disque.
        
        Args:
            filepath: Chemin du fichier
        
        Returns:
            bool: True si la sauvegarde a réussi
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'metadata': self.metadata.to_dict(),
                'is_fitted': self.is_fitted,
                'params': self.get_params(),
                'metrics': self.get_metrics(),
                'version': self._version,
                'framework': self._framework,
                'timestamp': datetime.now().isoformat(),
            }

            # Sauvegarde du modèle spécifique
            model_data = self._save_model()
            if model_data:
                data['model_data'] = model_data

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            self._logger.info(f"Modèle sauvegardé: {filepath}")
            return True

        except Exception as e:
            self._logger.error(f"Erreur lors de la sauvegarde: {e}")
            return False

    def _save_model(self) -> Dict[str, Any]:
        """
        Sauvegarde les données spécifiques du modèle.
        À surcharger par les sous-classes.
        """
        return {}

    @classmethod
    def load(cls, filepath: str) -> 'BaseModel':
        """
        Charge un modèle depuis le disque.
        
        Args:
            filepath: Chemin du fichier
        
        Returns:
            BaseModel: Modèle chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            # Créer une instance
            model = cls()

            # Restaurer les métadonnées
            model.metadata = ModelMetadata.from_dict(data['metadata'])
            model.is_fitted = data.get('is_fitted', False)
            model._version = data.get('version', '1.0.0')
            model._framework = data.get('framework', 'pytorch')

            # Charger les données spécifiques du modèle
            model_data = data.get('model_data', {})
            model._load_model(model_data)

            model._logger.info(f"Modèle chargé: {filepath}")
            return model

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise

    def _load_model(self, data: Dict[str, Any]):
        """
        Charge les données spécifiques du modèle.
        À surcharger par les sous-classes.
        """
        pass

    def update_metadata(self, **kwargs):
        """Met à jour les métadonnées du modèle"""
        for key, value in kwargs.items():
            if hasattr(self.metadata, key):
                setattr(self.metadata, key, value)

        if 'metrics' in kwargs:
            self.metadata.metrics.update(kwargs['metrics'])

        if 'hyperparameters' in kwargs:
            self.metadata.hyperparameters.update(kwargs['hyperparameters'])

    def get_metadata(self) -> Dict[str, Any]:
        """Retourne les métadonnées du modèle"""
        return self.metadata.to_dict()

    def get_summary(self) -> str:
        """Retourne un résumé du modèle"""
        summary = f"""
        {self.__class__.__name__}
        ========================
        Nom: {self.metadata.name}
        Version: {self.metadata.version}
        Type: {self.metadata.model_type}
        Framework: {self._framework}
        Entraîné: {self.is_fitted}
        Paramètres: {self.metadata.parameters}
        Temps d'entraînement: {self.metadata.training_time:.2f}s
        
        Métriques:
        {json.dumps(self.metadata.metrics, indent=2)}
        
        Hyperparamètres:
        {json.dumps(self.metadata.hyperparameters, indent=2)}
        """
        return summary

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', fitted={self.is_fitted})"


class BaseRegressor(BaseModel):
    """Classe de base pour les modèles de régression"""

    def __init__(self, name: str = "BaseRegressor", **kwargs):
        super().__init__(name, **kwargs)
        self.metadata.tags.append('regressor')

    def predict_proba(self, X: Union[np.ndarray, pd.DataFrame], **kwargs) -> np.ndarray:
        """
        Pour la régression, retourne les prédictions avec intervalle de confiance.
        """
        predictions = self.predict(X, **kwargs)
        return np.array([predictions, predictions, predictions]).T

    def score(self, X: Union[np.ndarray, pd.DataFrame], y: Union[np.ndarray, pd.Series], metric: str = 'r2') -> float:
        return super().score(X, y, metric)


class BaseClassifier(BaseModel):
    """Classe de base pour les modèles de classification"""

    def __init__(self, name: str = "BaseClassifier", **kwargs):
        super().__init__(name, **kwargs)
        self.metadata.tags.append('classifier')

    def score(self, X: Union[np.ndarray, pd.DataFrame], y: Union[np.ndarray, pd.Series], metric: str = 'accuracy') -> float:
        return super().score(X, y, metric)


class BaseForecaster(BaseModel):
    """Classe de base pour les modèles de prévision"""

    def __init__(self, name: str = "BaseForecaster", **kwargs):
        super().__init__(name, **kwargs)
        self.metadata.tags.append('forecaster')
        self.context_length = kwargs.get('context_length', 24)
        self.prediction_length = kwargs.get('prediction_length', 12)

    @abstractmethod
    def forecast(self, steps: int = 1, **kwargs) -> np.ndarray:
        """
        Effectue une prévision future.
        
        Args:
            steps: Nombre d'étapes
            **kwargs: Arguments supplémentaires
        
        Returns:
            np.ndarray: Prévisions
        """
        pass

    def predict(self, X: Union[np.ndarray, pd.DataFrame], **kwargs) -> np.ndarray:
        """Alias pour forecast pour compatibilité"""
        return self.forecast(**kwargs)


class BaseEnsemble(BaseModel):
    """Classe de base pour les modèles d'ensemble"""

    def __init__(self, name: str = "BaseEnsemble", **kwargs):
        super().__init__(name, **kwargs)
        self.metadata.tags.append('ensemble')
        self.models: List[BaseModel] = []
        self.weights: Optional[np.ndarray] = None

    def add_model(self, model: BaseModel, weight: float = 1.0) -> 'BaseEnsemble':
        """
        Ajoute un modèle à l'ensemble.
        
        Args:
            model: Modèle à ajouter
            weight: Poids du modèle
        
        Returns:
            BaseEnsemble: Instance
        """
        self.models.append(model)
        if self.weights is None:
            self.weights = np.array([weight])
        else:
            self.weights = np.append(self.weights, weight)

        self.metadata.parameters += model.metadata.parameters
        return self

    def get_models(self) -> List[BaseModel]:
        """Retourne les modèles de l'ensemble"""
        return self.models

    def get_weights(self) -> Optional[np.ndarray]:
        """Retourne les poids des modèles"""
        return self.weights


__all__ = [
    'BaseModel',
    'BaseRegressor',
    'BaseClassifier',
    'BaseForecaster',
    'BaseEnsemble',
    'ModelMetadata',
    'PredictionResult',
]
