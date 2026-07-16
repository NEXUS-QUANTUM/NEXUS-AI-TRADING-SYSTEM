# ai/self-learning/online_learner.py
"""
NEXUS AI TRADING SYSTEM - Online Learner Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import os
import time
import random
from collections import deque
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from sklearn.linear_model import SGDRegressor, SGDClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class OnlineLearnerConfig:
    """Configuration pour Online Learner"""
    learning_rate: float = 0.01
    batch_size: int = 1
    max_samples: int = 10000
    warmup_samples: int = 50
    update_frequency: int = 1
    loss_function: str = 'mse'
    optimizer: str = 'sgd'
    use_gpu: bool = False
    forget_factor: float = 0.95
    use_validation: bool = True
    validation_frequency: int = 10
    early_stopping: bool = False
    patience: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return {
            'learning_rate': self.learning_rate,
            'batch_size': self.batch_size,
            'max_samples': self.max_samples,
            'warmup_samples': self.warmup_samples,
            'update_frequency': self.update_frequency,
            'loss_function': self.loss_function,
            'optimizer': self.optimizer,
            'use_gpu': self.use_gpu,
            'forget_factor': self.forget_factor,
            'use_validation': self.use_validation,
            'validation_frequency': self.validation_frequency,
            'early_stopping': self.early_stopping,
            'patience': self.patience,
        }


@dataclass
class OnlineState:
    """État de l'apprentissage en ligne"""
    model: Any
    optimizer: Any
    scaler: Any
    samples_seen: int
    loss_history: List[float]
    val_loss_history: List[float]
    performance_history: List[float]
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'samples_seen': self.samples_seen,
            'timestamp': self.timestamp.isoformat(),
        }


class OnlineLearner:
    """
    Apprentissage en ligne pour l'IA de trading.

    Features:
    - Apprentissage en temps réel
    - Mise à jour par échantillon
    - Forgetting factor
    - Validation en ligne
    - Performance tracking

    Example:
        ```python
        config = OnlineLearnerConfig(
            learning_rate=0.01,
            batch_size=1,
            forget_factor=0.95
        )
        learner = OnlineLearner(config)

        # Initialisation
        learner.initialize(model)

        # Apprentissage en ligne
        for sample in data_stream:
            learner.update(sample)
        ```
    """

    def __init__(self, config: Optional[OnlineLearnerConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or OnlineLearnerConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.state: Optional[OnlineState] = None
        self.total_updates = 0
        self._loss_ema = None

        logger.info(f"OnlineLearner initialisé sur {self.device}")

    def initialize(
        self,
        model: Any,
        input_dim: Optional[int] = None,
        output_dim: Optional[int] = None,
        use_sklearn: bool = False
    ) -> None:
        """
        Initialise l'apprentissage en ligne.

        Args:
            model: Modèle à entraîner
            input_dim: Dimension d'entrée (optionnel)
            output_dim: Dimension de sortie (optionnel)
            use_sklearn: Utiliser scikit-learn
        """
        if model is not None:
            self.model = model
        elif use_sklearn and SKLEARN_AVAILABLE and input_dim is not None and output_dim is not None:
            # Modèle scikit-learn
            if output_dim == 1:
                self.model = SGDRegressor(
                    learning_rate='adaptive',
                    eta0=self.config.learning_rate,
                    max_iter=1,
                    tol=None,
                    warm_start=True
                )
            else:
                self.model = SGDClassifier(
                    learning_rate='adaptive',
                    eta0=self.config.learning_rate,
                    max_iter=1,
                    tol=None,
                    warm_start=True
                )
            self.model.partial_fit(np.zeros((1, input_dim)), np.zeros(1) if output_dim == 1 else np.zeros(output_dim))
        elif input_dim is not None and output_dim is not None:
            # Modèle PyTorch simple
            self.model = nn.Sequential(
                nn.Linear(input_dim, 64),
                nn.ReLU(),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.Linear(32, output_dim)
            ).to(self.device)
        else:
            raise ValueError("Modèle ou dimensions d'entrée/sortie requis")

        # Optimiseur PyTorch
        self.optimizer = None
        if hasattr(self.model, 'parameters'):
            if self.config.optimizer == 'sgd':
                self.optimizer = optim.SGD(
                    self.model.parameters(),
                    lr=self.config.learning_rate
                )
            elif self.config.optimizer == 'adam':
                self.optimizer = optim.Adam(
                    self.model.parameters(),
                    lr=self.config.learning_rate
                )
            elif self.config.optimizer == 'rmsprop':
                self.optimizer = optim.RMSprop(
                    self.model.parameters(),
                    lr=self.config.learning_rate
                )
            else:
                self.optimizer = optim.Adam(
                    self.model.parameters(),
                    lr=self.config.learning_rate
                )

        # Scaler
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None

        # État
        self.state = OnlineState(
            model=self.model,
            optimizer=self.optimizer,
            scaler=self.scaler,
            samples_seen=0,
            loss_history=[],
            val_loss_history=[],
            performance_history=[],
            timestamp=datetime.now(),
        )

        logger.info(f"OnlineLearner initialisé")

    def update(
        self,
        X: Union[np.ndarray, torch.Tensor],
        y: Union[np.ndarray, torch.Tensor],
        is_validation: bool = False
    ) -> float:
        """
        Met à jour le modèle avec un nouvel échantillon.

        Args:
            X: Caractéristiques
            y: Cibles
            is_validation: Échantillon de validation

        Returns:
            float: Perte
        """
        if self.state is None:
            raise ValueError("Learner non initialisé")

        self.total_updates += 1
        self.state.samples_seen += 1

        # Conversion en numpy
        if isinstance(X, torch.Tensor):
            X = X.cpu().numpy()
        if isinstance(y, torch.Tensor):
            y = y.cpu().numpy()

        # Normalisation
        if self.state.scaler is not None:
            if self.state.samples_seen <= self.config.warmup_samples:
                self.state.scaler.partial_fit(X.reshape(1, -1))
            X = self.state.scaler.transform(X.reshape(1, -1)).flatten()

        # Modèle scikit-learn
        if hasattr(self.model, 'partial_fit'):
            return self._update_sklearn(X, y)

        # Modèle PyTorch
        return self._update_pytorch(X, y)

    def _update_sklearn(self, X: np.ndarray, y: np.ndarray) -> float:
        """Mise à jour du modèle scikit-learn"""
        try:
            X_reshaped = X.reshape(1, -1)
            y_reshaped = np.array([y])

            self.model.partial_fit(X_reshaped, y_reshaped)

            # Prédiction pour évaluation
            pred = self.model.predict(X_reshaped)
            loss = (pred[0] - y) ** 2

            self.state.loss_history.append(loss)
            self.state.performance_history.append(loss)

            return loss

        except Exception as e:
            logger.error(f"Erreur de mise à jour sklearn: {e}")
            return 0.0

    def _update_pytorch(self, X: np.ndarray, y: np.ndarray) -> float:
        """Mise à jour du modèle PyTorch"""
        if self.state.optimizer is None:
            return 0.0

        X_tensor = torch.FloatTensor(X).unsqueeze(0).to(self.device)
        y_tensor = torch.FloatTensor([y]).to(self.device)

        self.model.train()
        self.state.optimizer.zero_grad()

        predictions = self.model(X_tensor)

        if self.config.loss_function == 'mse':
            loss_fn = nn.MSELoss()
        elif self.config.loss_function == 'mae':
            loss_fn = nn.L1Loss()
        elif self.config.loss_function == 'smooth_l1':
            loss_fn = nn.SmoothL1Loss()
        else:
            loss_fn = nn.MSELoss()

        loss = loss_fn(predictions, y_tensor)

        # EMA de la perte
        if self._loss_ema is None:
            self._loss_ema = loss.item()
        else:
            self._loss_ema = self.config.forget_factor * self._loss_ema + (1 - self.config.forget_factor) * loss.item()

        loss.backward()
        self.state.optimizer.step()

        # Historique
        self.state.loss_history.append(loss.item())
        self.state.performance_history.append(self._loss_ema)

        return loss.item()

    def predict(self, X: Union[np.ndarray, torch.Tensor]) -> np.ndarray:
        """
        Effectue une prédiction.

        Args:
            X: Caractéristiques

        Returns:
            np.ndarray: Prédictions
        """
        if self.state is None:
            raise ValueError("Learner non initialisé")

        if isinstance(X, torch.Tensor):
            X = X.cpu().numpy()

        # Normalisation
        if self.state.scaler is not None:
            X = self.state.scaler.transform(X.reshape(1, -1)).flatten()

        # Modèle scikit-learn
        if hasattr(self.model, 'predict'):
            return self.model.predict(X.reshape(1, -1))

        # Modèle PyTorch
        X_tensor = torch.FloatTensor(X).unsqueeze(0).to(self.device)

        self.model.eval()
        with torch.no_grad():
            predictions = self.model(X_tensor)

        return predictions.cpu().numpy().flatten()

    def get_performance(self) -> Dict[str, Any]:
        """
        Retourne les performances du modèle.

        Returns:
            Dict[str, Any]: Métriques de performance
        """
        if self.state is None:
            return {'status': 'not_initialized'}

        metrics = {
            'samples_seen': self.state.samples_seen,
            'total_updates': self.total_updates,
            'current_loss': self._loss_ema or 0.0,
        }

        if self.state.loss_history:
            metrics['avg_loss'] = np.mean(self.state.loss_history[-100:])
            metrics['last_loss'] = self.state.loss_history[-1]
            metrics['min_loss'] = min(self.state.loss_history[-100:]) if self.state.loss_history else 0

        if self.state.performance_history:
            metrics['performance'] = self.state.performance_history[-1] if self.state.performance_history else 0
            metrics['avg_performance'] = np.mean(self.state.performance_history[-100:])

        return metrics

    def get_state(self) -> Dict[str, Any]:
        """
        Retourne l'état actuel.

        Returns:
            Dict[str, Any]: État
        """
        if self.state is None:
            return {}

        return {
            'samples_seen': self.state.samples_seen,
            'loss_history_len': len(self.state.loss_history),
            'val_loss_history_len': len(self.state.val_loss_history),
            'timestamp': self.state.timestamp.isoformat(),
        }

    def reset(self) -> None:
        """Réinitialise l'apprentissage en ligne"""
        self.state = None
        self.total_updates = 0
        self._loss_ema = None
        logger.info("OnlineLearner réinitialisé")

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde l'apprentissage en ligne.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si sauvegardé
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'state': self.state.to_dict() if self.state else None,
                'total_updates': self.total_updates,
                'loss_ema': self._loss_ema,
                'loss_history': self.state.loss_history if self.state else [],
                'performance_history': self.state.performance_history if self.state else [],
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"OnlineLearner sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'OnlineLearner':
        """
        Charge un apprentissage en ligne.

        Args:
            filepath: Chemin du fichier

        Returns:
            OnlineLearner: Apprentissage chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = OnlineLearnerConfig(**data['config'])
            learner = cls(config)

            # Restaurer l'état
            state_data = data.get('state')
            if state_data:
                learner.state = OnlineState(
                    model=None,  # À restaurer séparément
                    optimizer=None,
                    scaler=None,
                    samples_seen=state_data.get('samples_seen', 0),
                    loss_history=data.get('loss_history', []),
                    val_loss_history=[],
                    performance_history=data.get('performance_history', []),
                    timestamp=datetime.fromisoformat(state_data.get('timestamp', datetime.now().isoformat())),
                )

            learner.total_updates = data.get('total_updates', 0)
            learner._loss_ema = data.get('loss_ema')

            logger.info(f"OnlineLearner chargé: {filepath}")
            return learner

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_online_learner(
    learning_rate: float = 0.01,
    batch_size: int = 1,
    forget_factor: float = 0.95,
    **kwargs
) -> OnlineLearner:
    """
    Factory pour créer un apprentissage en ligne.

    Args:
        learning_rate: Taux d'apprentissage
        batch_size: Taille du batch
        forget_factor: Facteur d'oubli
        **kwargs: Arguments supplémentaires

    Returns:
        OnlineLearner: Apprentissage en ligne
    """
    config = OnlineLearnerConfig(
        learning_rate=learning_rate,
        batch_size=batch_size,
        forget_factor=forget_factor,
        **kwargs
    )
    return OnlineLearner(config)


__all__ = [
    'OnlineLearner',
    'OnlineLearnerConfig',
    'OnlineState',
    'create_online_learner',
]
