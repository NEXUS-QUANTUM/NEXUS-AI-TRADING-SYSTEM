# ai/self-learning/incremental_learner.py
"""
NEXUS AI TRADING SYSTEM - Incremental Learner Module
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
import warnings
from collections import deque
import time

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
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
class IncrementalLearnerConfig:
    """Configuration pour Incremental Learner"""
    batch_size: int = 32
    learning_rate: float = 0.001
    momentum: float = 0.9
    weight_decay: float = 1e-5
    max_samples: int = 10000
    warmup_samples: int = 100
    update_frequency: int = 10
    use_gpu: bool = False
    loss_function: str = 'mse'
    optimizer: str = 'adam'
    validation_split: float = 0.2
    early_stopping: bool = True
    patience: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            'batch_size': self.batch_size,
            'learning_rate': self.learning_rate,
            'momentum': self.momentum,
            'weight_decay': self.weight_decay,
            'max_samples': self.max_samples,
            'warmup_samples': self.warmup_samples,
            'update_frequency': self.update_frequency,
            'use_gpu': self.use_gpu,
            'loss_function': self.loss_function,
            'optimizer': self.optimizer,
            'validation_split': self.validation_split,
            'early_stopping': self.early_stopping,
            'patience': self.patience,
        }


@dataclass
class IncrementalState:
    """État de l'apprentissage incrémental"""
    model: Any
    optimizer: Any
    scaler: Any
    training_data: deque
    validation_data: deque
    loss_history: List[float]
    val_loss_history: List[float]
    iterations: int
    best_val_loss: float
    patience_counter: int
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            'iterations': self.iterations,
            'best_val_loss': self.best_val_loss,
            'patience_counter': self.patience_counter,
            'timestamp': self.timestamp.isoformat(),
        }


class IncrementalLearner:
    """
    Apprentissage incrémental pour l'IA de trading.

    Features:
    - Apprentissage continu
    - Mise à jour en ligne
    - Validation incrémentale
    - Early stopping
    - Persistance

    Example:
        ```python
        config = IncrementalLearnerConfig(
            batch_size=32,
            learning_rate=0.001,
            max_samples=10000
        )
        learner = IncrementalLearner(config)

        # Initialisation
        learner.initialize(model)

        # Entraînement incrémental
        for batch in data_stream:
            learner.update(batch)
        ```
    """

    def __init__(self, config: Optional[IncrementalLearnerConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or IncrementalLearnerConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.state: Optional[IncrementalState] = None
        self.total_samples = 0

        logger.info(f"IncrementalLearner initialisé sur {self.device}")

    def initialize(
        self,
        model: Any,
        input_dim: Optional[int] = None,
        output_dim: Optional[int] = None
    ) -> None:
        """
        Initialise l'apprentissage incrémental.

        Args:
            model: Modèle à entraîner
            input_dim: Dimension d'entrée (optionnel)
            output_dim: Dimension de sortie (optionnel)
        """
        # Initialisation du modèle si fourni
        if model is not None:
            self.model = model.to(self.device)
        elif input_dim is not None and output_dim is not None:
            # Création d'un modèle simple
            self.model = nn.Sequential(
                nn.Linear(input_dim, 64),
                nn.ReLU(),
                nn.Linear(64, 32),
                nn.ReLU(),
                nn.Linear(32, output_dim)
            ).to(self.device)
        else:
            raise ValueError("Modèle ou dimensions d'entrée/sortie requis")

        # Optimiseur
        if self.config.optimizer == 'adam':
            optimizer = optim.Adam(
                self.model.parameters(),
                lr=self.config.learning_rate,
                weight_decay=self.config.weight_decay
            )
        elif self.config.optimizer == 'sgd':
            optimizer = optim.SGD(
                self.model.parameters(),
                lr=self.config.learning_rate,
                momentum=self.config.momentum,
                weight_decay=self.config.weight_decay
            )
        else:
            raise ValueError(f"Optimiseur non supporté: {self.config.optimizer}")

        # Scaler
        scaler = StandardScaler() if SKLEARN_AVAILABLE else None

        # État
        self.state = IncrementalState(
            model=self.model,
            optimizer=optimizer,
            scaler=scaler,
            training_data=deque(maxlen=self.config.max_samples),
            validation_data=deque(maxlen=int(self.config.max_samples * self.config.validation_split)),
            loss_history=[],
            val_loss_history=[],
            iterations=0,
            best_val_loss=float('inf'),
            patience_counter=0,
            timestamp=datetime.now(),
        )

        logger.info(f"IncrementalLearner initialisé")

    def update(self, X: Union[np.ndarray, torch.Tensor], y: Union[np.ndarray, torch.Tensor]) -> float:
        """
        Met à jour le modèle avec un nouvel échantillon.

        Args:
            X: Caractéristiques
            y: Cibles

        Returns:
            float: Perte
        """
        if self.state is None:
            raise ValueError("Learner non initialisé")

        self.total_samples += 1

        # Conversion en numpy
        if isinstance(X, torch.Tensor):
            X = X.cpu().numpy()
        if isinstance(y, torch.Tensor):
            y = y.cpu().numpy()

        # Normalisation
        if self.state.scaler is not None:
            X = self.state.scaler.transform(X.reshape(1, -1)).flatten()

        # Ajout aux données d'entraînement
        self.state.training_data.append((X, y))

        # Validation
        val_loss = None
        if len(self.state.training_data) > self.config.warmup_samples and self.config.validation_split > 0:
            val_loss = self._validate()

        # Mise à jour du modèle
        loss = None
        if self.total_samples % self.config.update_frequency == 0:
            loss = self._train_batch()

        # Enregistrement
        if loss is not None:
            self.state.loss_history.append(loss)
            if val_loss is not None:
                self.state.val_loss_history.append(val_loss)

            # Early stopping
            if self.config.early_stopping and val_loss is not None:
                self._check_early_stopping(val_loss)

            self.state.iterations += 1
            self.state.timestamp = datetime.now()

        return loss or 0.0

    def _train_batch(self) -> float:
        """Entraîne le modèle sur un batch"""
        if len(self.state.training_data) < self.config.warmup_samples:
            return 0.0

        # Préparation du batch
        batch_size = min(self.config.batch_size, len(self.state.training_data))
        indices = np.random.choice(len(self.state.training_data), batch_size, replace=False)

        X_batch = np.array([self.state.training_data[i][0] for i in indices])
        y_batch = np.array([self.state.training_data[i][1] for i in indices])

        X_tensor = torch.FloatTensor(X_batch).to(self.device)
        y_tensor = torch.FloatTensor(y_batch).reshape(-1, 1).to(self.device)

        # Entraînement
        self.state.model.train()
        self.state.optimizer.zero_grad()

        predictions = self.state.model(X_tensor)

        if self.config.loss_function == 'mse':
            loss_fn = nn.MSELoss()
        elif self.config.loss_function == 'mae':
            loss_fn = nn.L1Loss()
        elif self.config.loss_function == 'smooth_l1':
            loss_fn = nn.SmoothL1Loss()
        else:
            loss_fn = nn.MSELoss()

        loss = loss_fn(predictions, y_tensor)

        loss.backward()
        self.state.optimizer.step()

        return loss.item()

    def _validate(self) -> float:
        """Valide le modèle"""
        if len(self.state.training_data) < self.config.warmup_samples:
            return 0.0

        # Préparation des données de validation
        val_size = min(
            int(len(self.state.training_data) * self.config.validation_split),
            self.config.max_samples // 2
        )

        if val_size < 1:
            return 0.0

        # Échantillonnage
        val_indices = np.random.choice(
            len(self.state.training_data),
            min(val_size, len(self.state.training_data) // 2),
            replace=False
        )

        X_val = np.array([self.state.training_data[i][0] for i in val_indices])
        y_val = np.array([self.state.training_data[i][1] for i in val_indices])

        X_tensor = torch.FloatTensor(X_val).to(self.device)
        y_tensor = torch.FloatTensor(y_val).reshape(-1, 1).to(self.device)

        # Évaluation
        self.state.model.eval()
        with torch.no_grad():
            predictions = self.state.model(X_tensor)

            if self.config.loss_function == 'mse':
                loss_fn = nn.MSELoss()
            elif self.config.loss_function == 'mae':
                loss_fn = nn.L1Loss()
            else:
                loss_fn = nn.MSELoss()

            loss = loss_fn(predictions, y_tensor)

        return loss.item()

    def _check_early_stopping(self, val_loss: float) -> None:
        """
        Vérifie les conditions d'early stopping.

        Args:
            val_loss: Perte de validation
        """
        if val_loss < self.state.best_val_loss:
            self.state.best_val_loss = val_loss
            self.state.patience_counter = 0
            logger.debug(f"Nouveau meilleur score: {val_loss:.4f}")
        else:
            self.state.patience_counter += 1
            if self.state.patience_counter >= self.config.patience:
                logger.info(f"Early stopping activé après {self.state.patience_counter} itérations")

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

        X_tensor = torch.FloatTensor(X).unsqueeze(0).to(self.device)

        self.state.model.eval()
        with torch.no_grad():
            predictions = self.state.model(X_tensor)

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
            'iterations': self.state.iterations,
            'total_samples': self.total_samples,
            'best_val_loss': self.state.best_val_loss,
            'patience_counter': self.state.patience_counter,
            'training_samples': len(self.state.training_data),
        }

        if self.state.loss_history:
            metrics['avg_loss'] = np.mean(self.state.loss_history[-100:])
            metrics['last_loss'] = self.state.loss_history[-1]

        if self.state.val_loss_history:
            metrics['avg_val_loss'] = np.mean(self.state.val_loss_history[-100:])
            metrics['last_val_loss'] = self.state.val_loss_history[-1]

        return metrics

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde l'apprentissage incrémental.

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
                'total_samples': self.total_samples,
                'model_state_dict': self.state.model.state_dict() if self.state else None,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"IncrementalLearner sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'IncrementalLearner':
        """
        Charge un apprentissage incrémental.

        Args:
            filepath: Chemin du fichier

        Returns:
            IncrementalLearner: Apprentissage chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = IncrementalLearnerConfig(**data['config'])
            learner = cls(config)

            # Restaurer l'état
            state_data = data.get('state')
            if state_data:
                learner.state = IncrementalState(
                    model=None,  # À restaurer séparément
                    optimizer=None,
                    scaler=None,
                    training_data=deque(maxlen=config.max_samples),
                    validation_data=deque(maxlen=int(config.max_samples * config.validation_split)),
                    loss_history=[],
                    val_loss_history=[],
                    iterations=state_data.get('iterations', 0),
                    best_val_loss=state_data.get('best_val_loss', float('inf')),
                    patience_counter=state_data.get('patience_counter', 0),
                    timestamp=datetime.fromisoformat(state_data.get('timestamp', datetime.now().isoformat())),
                )

            learner.total_samples = data.get('total_samples', 0)

            logger.info(f"IncrementalLearner chargé: {filepath}")
            return learner

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_incremental_learner(
    batch_size: int = 32,
    learning_rate: float = 0.001,
    max_samples: int = 10000,
    **kwargs
) -> IncrementalLearner:
    """
    Factory pour créer un apprentissage incrémental.

    Args:
        batch_size: Taille du batch
        learning_rate: Taux d'apprentissage
        max_samples: Nombre maximum d'échantillons
        **kwargs: Arguments supplémentaires

    Returns:
        IncrementalLearner: Apprentissage incrémental
    """
    config = IncrementalLearnerConfig(
        batch_size=batch_size,
        learning_rate=learning_rate,
        max_samples=max_samples,
        **kwargs
    )
    return IncrementalLearner(config)


__all__ = [
    'IncrementalLearner',
    'IncrementalLearnerConfig',
    'IncrementalState',
    'create_incremental_learner',
]
