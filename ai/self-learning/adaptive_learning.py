# ai/self-learning/adaptive_learning.py
"""
NEXUS AI TRADING SYSTEM - Adaptive Learning Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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

logger = logging.getLogger(__name__)


@dataclass
class AdaptiveLearningConfig:
    """Configuration pour Adaptive Learning"""
    window_size: int = 100
    update_frequency: int = 10
    learning_rate: float = 0.001
    forgetting_rate: float = 0.01
    exploration_rate: float = 0.1
    min_samples: int = 50
    max_samples: int = 1000
    adaptation_strategy: str = 'incremental'  # 'incremental', 'batch', 'online'
    use_validation: bool = True
    validation_split: float = 0.2
    early_stopping: bool = True
    patience: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return {
            'window_size': self.window_size,
            'update_frequency': self.update_frequency,
            'learning_rate': self.learning_rate,
            'forgetting_rate': self.forgetting_rate,
            'exploration_rate': self.exploration_rate,
            'min_samples': self.min_samples,
            'max_samples': self.max_samples,
            'adaptation_strategy': self.adaptation_strategy,
            'use_validation': self.use_validation,
            'validation_split': self.validation_split,
            'early_stopping': self.early_stopping,
            'patience': self.patience,
        }


@dataclass
class AdaptiveState:
    """État d'apprentissage adaptatif"""
    model: Any
    optimizer: Optional[Any]
    training_data: deque
    validation_data: deque
    performance_history: List[float]
    adaptation_count: int
    last_update: datetime
    best_performance: float
    patience_counter: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'adaptation_count': self.adaptation_count,
            'last_update': self.last_update.isoformat(),
            'best_performance': self.best_performance,
            'patience_counter': self.patience_counter,
        }


class AdaptiveLearner:
    """
    Apprentissage adaptatif pour l'IA de trading.

    Features:
    - Apprentissage incrémental
    - Détection de changement de concept
    - Forgetting adaptatif
    - Validation en ligne
    - Early stopping

    Example:
        ```python
        config = AdaptiveLearningConfig(
            window_size=100,
            update_frequency=10,
            learning_rate=0.001
        )
        learner = AdaptiveLearner(config)

        # Initialisation
        learner.initialize(model)

        # Adaptation
        for sample in data_stream:
            learner.update(sample)
            if learner.should_adapt():
                learner.adapt()
        ```
    """

    def __init__(self, config: Optional[AdaptiveLearningConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or AdaptiveLearningConfig()
        self.state: Optional[AdaptiveState] = None
        self.sample_count = 0
        self.adaptation_history: List[Dict[str, Any]] = []

        logger.info(f"AdaptiveLearner initialisé")

    def initialize(self, model: Any, optimizer: Optional[Any] = None) -> None:
        """
        Initialise l'apprentissage adaptatif.

        Args:
            model: Modèle à adapter
            optimizer: Optimiseur (optionnel)
        """
        self.state = AdaptiveState(
            model=model,
            optimizer=optimizer,
            training_data=deque(maxlen=self.config.max_samples),
            validation_data=deque(maxlen=int(self.config.max_samples * self.config.validation_split)),
            performance_history=[],
            adaptation_count=0,
            last_update=datetime.now(),
            best_performance=float('-inf'),
            patience_counter=0,
        )

        logger.info("AdaptiveLearner initialisé")

    def update(self, x: np.ndarray, y: np.ndarray, validate: bool = True) -> float:
        """
        Met à jour l'état d'apprentissage avec un nouvel échantillon.

        Args:
            x: Caractéristiques
            y: Cible
            validate: Effectuer la validation

        Returns:
            float: Perte ou erreur
        """
        if self.state is None:
            raise ValueError("Learner non initialisé")

        self.sample_count += 1

        # Ajout aux données d'entraînement
        self.state.training_data.append((x, y))

        # Validation
        loss = 0.0
        if validate and len(self.state.training_data) > self.config.min_samples:
            loss = self._validate()

        # Mise à jour de la performance
        if loss > 0:
            self.state.performance_history.append(loss)

        return loss

    def _validate(self) -> float:
        """Valide le modèle sur les données de validation"""
        if len(self.state.training_data) < self.config.min_samples:
            return 0.0

        # Création du lot de validation
        val_size = min(
            int(len(self.state.training_data) * self.config.validation_split),
            self.config.max_samples // 2
        )

        if val_size < 1:
            return 0.0

        # Échantillonnage aléatoire
        val_indices = random.sample(
            range(len(self.state.training_data)),
            min(val_size, len(self.state.training_data) // 2)
        )

        val_data = [self.state.training_data[i] for i in val_indices]
        val_X = np.array([d[0] for d in val_data])
        val_y = np.array([d[1] for d in val_data])

        # Évaluation
        if hasattr(self.state.model, 'evaluate'):
            loss = self.state.model.evaluate(val_X, val_y)
        elif hasattr(self.state.model, 'score'):
            loss = 1 - self.state.model.score(val_X, val_y)
        else:
            predictions = self._predict(val_X)
            loss = np.mean((predictions - val_y) ** 2)

        return loss

    def _predict(self, X: np.ndarray) -> np.ndarray:
        """Effectue une prédiction avec le modèle"""
        if hasattr(self.state.model, 'predict'):
            return self.state.model.predict(X)
        elif hasattr(self.state.model, 'forward'):
            with torch.no_grad():
                return self.state.model(torch.FloatTensor(X)).numpy()
        else:
            raise ValueError("Modèle ne supporte pas la prédiction")

    def should_adapt(self) -> bool:
        """
        Vérifie si une adaptation est nécessaire.

        Returns:
            bool: True si adaptation nécessaire
        """
        if self.state is None:
            return False

        return (
            self.sample_count % self.config.update_frequency == 0
            and len(self.state.training_data) >= self.config.min_samples
        )

    def adapt(self) -> Dict[str, Any]:
        """
        Effectue une adaptation du modèle.

        Returns:
            Dict[str, Any]: Résultats de l'adaptation
        """
        if self.state is None:
            raise ValueError("Learner non initialisé")

        if len(self.state.training_data) < self.config.min_samples:
            return {'status': 'insufficient_data', 'samples': len(self.state.training_data)}

        start_time = time.time()

        # Préparation des données
        train_data = list(self.state.training_data)
        random.shuffle(train_data)

        train_X = np.array([d[0] for d in train_data])
        train_y = np.array([d[1] for d in train_data])

        # Adaptation selon la stratégie
        if self.config.adaptation_strategy == 'incremental':
            loss = self._incremental_adaptation(train_X, train_y)
        elif self.config.adaptation_strategy == 'batch':
            loss = self._batch_adaptation(train_X, train_y)
        elif self.config.adaptation_strategy == 'online':
            loss = self._online_adaptation(train_X, train_y)
        else:
            raise ValueError(f"Stratégie non supportée: {self.config.adaptation_strategy}")

        # Mise à jour de l'état
        self.state.adaptation_count += 1
        self.state.last_update = datetime.now()

        # Early stopping
        if self.config.early_stopping and self.config.use_validation:
            self._check_early_stopping(loss)

        # Historique
        result = {
            'iteration': self.state.adaptation_count,
            'loss': loss,
            'samples': len(train_data),
            'time': time.time() - start_time,
        }
        self.adaptation_history.append(result)

        logger.info(f"Adaptation {self.state.adaptation_count}: loss={loss:.4f}")

        return result

    def _incremental_adaptation(self, X: np.ndarray, y: np.ndarray) -> float:
        """Adaptation incrémentale"""
        if self.state.optimizer is None:
            import torch.optim as optim
            self.state.optimizer = optim.Adam(
                self.state.model.parameters(),
                lr=self.config.learning_rate
            )

        # Petit batch pour adaptation incrémentale
        batch_size = min(32, len(X))
        indices = np.random.choice(len(X), batch_size, replace=False)

        X_batch = torch.FloatTensor(X[indices])
        y_batch = torch.FloatTensor(y[indices]).reshape(-1, 1)

        self.state.model.train()
        self.state.optimizer.zero_grad()

        predictions = self.state.model(X_batch)
        loss = nn.MSELoss()(predictions, y_batch)

        loss.backward()
        self.state.optimizer.step()

        return loss.item()

    def _batch_adaptation(self, X: np.ndarray, y: np.ndarray) -> float:
        """Adaptation par batch"""
        if self.state.optimizer is None:
            import torch.optim as optim
            self.state.optimizer = optim.Adam(
                self.state.model.parameters(),
                lr=self.config.learning_rate
            )

        X_tensor = torch.FloatTensor(X)
        y_tensor = torch.FloatTensor(y).reshape(-1, 1)

        self.state.model.train()
        self.state.optimizer.zero_grad()

        predictions = self.state.model(X_tensor)
        loss = nn.MSELoss()(predictions, y_tensor)

        loss.backward()
        self.state.optimizer.step()

        return loss.item()

    def _online_adaptation(self, X: np.ndarray, y: np.ndarray) -> float:
        """Adaptation en ligne"""
        if self.state.optimizer is None:
            import torch.optim as optim
            self.state.optimizer = optim.Adam(
                self.state.model.parameters(),
                lr=self.config.learning_rate
            )

        total_loss = 0.0

        for i in range(len(X)):
            X_sample = torch.FloatTensor(X[i:i+1])
            y_sample = torch.FloatTensor(y[i:i+1]).reshape(-1, 1)

            self.state.model.train()
            self.state.optimizer.zero_grad()

            predictions = self.state.model(X_sample)
            loss = nn.MSELoss()(predictions, y_sample)

            loss.backward()
            self.state.optimizer.step()

            total_loss += loss.item()

        return total_loss / len(X)

    def _check_early_stopping(self, loss: float) -> bool:
        """
        Vérifie les conditions d'early stopping.

        Args:
            loss: Perte actuelle

        Returns:
            bool: True si arrêt précoce
        """
        if not self.config.early_stopping:
            return False

        if loss < self.state.best_performance:
            self.state.best_performance = loss
            self.state.patience_counter = 0
            return False
        else:
            self.state.patience_counter += 1
            if self.state.patience_counter >= self.config.patience:
                logger.info(f"Early stopping activé après {self.state.patience_counter} itérations")
                return True

        return False

    def get_performance(self) -> Dict[str, Any]:
        """
        Retourne les performances de l'apprentissage.

        Returns:
            Dict[str, Any]: Métriques de performance
        """
        if not self.state or not self.state.performance_history:
            return {'status': 'no_data'}

        history = self.state.performance_history

        return {
            'mean': np.mean(history[-100:]) if history else 0,
            'std': np.std(history[-100:]) if history else 0,
            'min': np.min(history[-100:]) if history else 0,
            'max': np.max(history[-100:]) if history else 0,
            'trend': self._calculate_trend(history),
            'samples': len(history),
            'adaptations': self.state.adaptation_count,
        }

    def _calculate_trend(self, history: List[float]) -> str:
        """
        Calcule la tendance des performances.

        Args:
            history: Historique des performances

        Returns:
            str: Tendance ('improving', 'stable', 'degrading')
        """
        if len(history) < 10:
            return 'stable'

        recent = np.mean(history[-10:])
        older = np.mean(history[-20:-10]) if len(history) >= 20 else recent

        if recent < older * 0.95:
            return 'improving'
        elif recent > older * 1.05:
            return 'degrading'
        else:
            return 'stable'

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde l'apprentissage adaptatif.

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
                'sample_count': self.sample_count,
                'adaptation_history': self.adaptation_history,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"AdaptiveLearner sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'AdaptiveLearner':
        """
        Charge un apprentissage adaptatif.

        Args:
            filepath: Chemin du fichier

        Returns:
            AdaptiveLearner: Apprentissage chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = AdaptiveLearningConfig(**data['config'])
            learner = cls(config)

            # Restaurer l'état
            state_data = data.get('state')
            if state_data:
                learner.state = AdaptiveState(
                    model=None,  # À restaurer séparément
                    optimizer=None,
                    training_data=deque(maxlen=learner.config.max_samples),
                    validation_data=deque(maxlen=int(learner.config.max_samples * learner.config.validation_split)),
                    performance_history=state_data.get('performance_history', []),
                    adaptation_count=state_data.get('adaptation_count', 0),
                    last_update=datetime.fromisoformat(state_data.get('last_update', datetime.now().isoformat())),
                    best_performance=state_data.get('best_performance', float('-inf')),
                    patience_counter=state_data.get('patience_counter', 0),
                )

            learner.sample_count = data.get('sample_count', 0)
            learner.adaptation_history = data.get('adaptation_history', [])

            logger.info(f"AdaptiveLearner chargé: {filepath}")
            return learner

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_adaptive_learner(
    window_size: int = 100,
    update_frequency: int = 10,
    learning_rate: float = 0.001,
    **kwargs
) -> AdaptiveLearner:
    """
    Factory pour créer un apprentissage adaptatif.

    Args:
        window_size: Taille de la fenêtre
        update_frequency: Fréquence de mise à jour
        learning_rate: Taux d'apprentissage
        **kwargs: Arguments supplémentaires

    Returns:
        AdaptiveLearner: Apprentissage adaptatif
    """
    config = AdaptiveLearningConfig(
        window_size=window_size,
        update_frequency=update_frequency,
        learning_rate=learning_rate,
        **kwargs
    )
    return AdaptiveLearner(config)


__all__ = [
    'AdaptiveLearner',
    'AdaptiveLearningConfig',
    'AdaptiveState',
    'create_adaptive_learner',
]
