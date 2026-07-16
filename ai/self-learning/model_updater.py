# ai/self-learning/model_updater.py
"""
NEXUS AI TRADING SYSTEM - Model Updater Module
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
import copy
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
class ModelUpdaterConfig:
    """Configuration pour Model Updater"""
    update_strategy: str = 'incremental'  # 'incremental', 'periodic', 'triggered'
    update_frequency: int = 100
    trigger_threshold: float = 0.05
    min_samples: int = 100
    max_samples: int = 10000
    learning_rate: float = 0.001
    batch_size: int = 32
    use_gpu: bool = False
    validation_split: float = 0.2
    early_stopping: bool = True
    patience: int = 5
    save_history: bool = True
    history_size: int = 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            'update_strategy': self.update_strategy,
            'update_frequency': self.update_frequency,
            'trigger_threshold': self.trigger_threshold,
            'min_samples': self.min_samples,
            'max_samples': self.max_samples,
            'learning_rate': self.learning_rate,
            'batch_size': self.batch_size,
            'use_gpu': self.use_gpu,
            'validation_split': self.validation_split,
            'early_stopping': self.early_stopping,
            'patience': self.patience,
            'save_history': self.save_history,
            'history_size': self.history_size,
        }


@dataclass
class UpdateResult:
    """Résultat de mise à jour du modèle"""
    success: bool
    version: int
    performance_before: Dict[str, float]
    performance_after: Dict[str, float]
    improvement: float
    samples_used: int
    time_taken: float
    timestamp: datetime
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'version': self.version,
            'performance_before': self.performance_before,
            'performance_after': self.performance_after,
            'improvement': self.improvement,
            'samples_used': self.samples_used,
            'time_taken': self.time_taken,
            'timestamp': self.timestamp.isoformat(),
            'details': self.details,
        }


class ModelUpdater:
    """
    Metteur à jour de modèle pour l'IA de trading.

    Features:
    - Mise à jour incrémentale
    - Mise à jour périodique
    - Mise à jour déclenchée par performance
    - Validation automatique
    - Historique des versions

    Example:
        ```python
        config = ModelUpdaterConfig(
            update_strategy='periodic',
            update_frequency=100,
            trigger_threshold=0.05
        )
        updater = ModelUpdater(config)

        # Initialisation
        updater.initialize(model, optimizer)

        # Mise à jour
        for batch in data_stream:
            updater.update(batch)
            if updater.should_update():
                updater.perform_update()
        ```
    """

    def __init__(self, config: Optional[ModelUpdaterConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or ModelUpdaterConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.model: Optional[nn.Module] = None
        self.optimizer: Optional[optim.Optimizer] = None
        self.loss_fn: Optional[nn.Module] = None
        self.data_buffer: deque = deque(maxlen=self.config.max_samples)
        self.version: int = 0
        self.update_history: List[UpdateResult] = []
        self.performance_history: List[Dict[str, float]] = []
        self.best_performance: Dict[str, float] = {}

        logger.info(f"ModelUpdater initialisé sur {self.device}")

    def initialize(
        self,
        model: nn.Module,
        optimizer: Optional[optim.Optimizer] = None,
        loss_fn: Optional[nn.Module] = None
    ) -> None:
        """
        Initialise le metteur à jour.

        Args:
            model: Modèle à mettre à jour
            optimizer: Optimiseur (optionnel)
            loss_fn: Fonction de perte (optionnel)
        """
        self.model = model.to(self.device)
        self.optimizer = optimizer or optim.Adam(
            self.model.parameters(),
            lr=self.config.learning_rate
        )
        self.loss_fn = loss_fn or nn.MSELoss()
        self.version = 1

        logger.info(f"ModelUpdater initialisé (version {self.version})")

    def update(self, X: np.ndarray, y: np.ndarray) -> float:
        """
        Met à jour le buffer avec de nouvelles données.

        Args:
            X: Caractéristiques
            y: Cibles

        Returns:
            float: Perte actuelle
        """
        if self.model is None:
            raise ValueError("ModelUpdater non initialisé")

        self.data_buffer.append((X, y))

        # Mise à jour incrémentale
        if self.config.update_strategy == 'incremental':
            return self._incremental_update(X, y)

        return 0.0

    def _incremental_update(self, X: np.ndarray, y: np.ndarray) -> float:
        """
        Mise à jour incrémentale du modèle.

        Args:
            X: Caractéristiques
            y: Cibles

        Returns:
            float: Perte
        """
        X_tensor = torch.FloatTensor(X).to(self.device)
        y_tensor = torch.FloatTensor(y).reshape(-1, 1).to(self.device)

        self.model.train()
        self.optimizer.zero_grad()

        predictions = self.model(X_tensor)
        loss = self.loss_fn(predictions, y_tensor)

        loss.backward()
        self.optimizer.step()

        return loss.item()

    def should_update(self) -> bool:
        """
        Vérifie si une mise à jour est nécessaire.

        Returns:
            bool: True si mise à jour nécessaire
        """
        if len(self.data_buffer) < self.config.min_samples:
            return False

        if self.config.update_strategy == 'periodic':
            return len(self.data_buffer) % self.config.update_frequency == 0

        elif self.config.update_strategy == 'triggered':
            return self._check_trigger_condition()

        elif self.config.update_strategy == 'incremental':
            return True

        return False

    def _check_trigger_condition(self) -> bool:
        """
        Vérifie la condition de déclenchement.

        Returns:
            bool: True si condition remplie
        """
        if len(self.performance_history) < 2:
            return False

        current_perf = self.performance_history[-1]
        previous_perf = self.performance_history[-2]

        if 'loss' in current_perf and 'loss' in previous_perf:
            loss_change = abs(current_perf['loss'] - previous_perf['loss']) / (previous_perf['loss'] + 1e-6)
            return loss_change > self.config.trigger_threshold

        return False

    def perform_update(self) -> UpdateResult:
        """
        Effectue une mise à jour complète du modèle.

        Returns:
            UpdateResult: Résultat de la mise à jour
        """
        if self.model is None:
            raise ValueError("ModelUpdater non initialisé")

        if len(self.data_buffer) < self.config.min_samples:
            return UpdateResult(
                success=False,
                version=self.version,
                performance_before=self._get_performance(),
                performance_after={},
                improvement=0.0,
                samples_used=len(self.data_buffer),
                time_taken=0.0,
                timestamp=datetime.now(),
                details={'error': 'insufficient_samples'}
            )

        start_time = time.time()

        # Performance avant
        perf_before = self._get_performance()

        # Préparation des données
        data = list(self.data_buffer)
        np.random.shuffle(data)

        X = np.array([d[0] for d in data])
        y = np.array([d[1] for d in data])

        # Validation split
        split_idx = int(len(X) * (1 - self.config.validation_split))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]

        # Entraînement
        X_train_tensor = torch.FloatTensor(X_train).to(self.device)
        y_train_tensor = torch.FloatTensor(y_train).reshape(-1, 1).to(self.device)

        self.model.train()
        self.optimizer.zero_grad()

        predictions = self.model(X_train_tensor)
        train_loss = self.loss_fn(predictions, y_train_tensor)

        train_loss.backward()
        self.optimizer.step()

        # Validation
        X_val_tensor = torch.FloatTensor(X_val).to(self.device)
        y_val_tensor = torch.FloatTensor(y_val).reshape(-1, 1).to(self.device)

        self.model.eval()
        with torch.no_grad():
            val_predictions = self.model(X_val_tensor)
            val_loss = self.loss_fn(val_predictions, y_val_tensor)

        # Performance après
        perf_after = {'train_loss': train_loss.item(), 'val_loss': val_loss.item()}

        # Mise à jour de l'historique
        self.version += 1
        self.performance_history.append(perf_after)

        # Meilleure performance
        if not self.best_performance or val_loss.item() < self.best_performance.get('val_loss', float('inf')):
            self.best_performance = perf_after

        result = UpdateResult(
            success=True,
            version=self.version,
            performance_before=perf_before,
            performance_after=perf_after,
            improvement=perf_before.get('val_loss', 0) - perf_after.get('val_loss', 0),
            samples_used=len(data),
            time_taken=time.time() - start_time,
            timestamp=datetime.now(),
            details={
                'train_samples': len(X_train),
                'val_samples': len(X_val),
            }
        )

        if self.config.save_history:
            self.update_history.append(result)

        logger.info(f"Mise à jour terminée (version {self.version}): val_loss={val_loss.item():.4f}")

        return result

    def _get_performance(self) -> Dict[str, float]:
        """
        Calcule la performance actuelle du modèle.

        Returns:
            Dict[str, float]: Métriques de performance
        """
        if not self.data_buffer or self.model is None:
            return {'loss': 0.0}

        # Utilisation des données récentes
        data = list(self.data_buffer)[-100:]
        X = np.array([d[0] for d in data])
        y = np.array([d[1] for d in data])

        X_tensor = torch.FloatTensor(X).to(self.device)
        y_tensor = torch.FloatTensor(y).reshape(-1, 1).to(self.device)

        self.model.eval()
        with torch.no_grad():
            predictions = self.model(X_tensor)
            loss = self.loss_fn(predictions, y_tensor)

        return {'loss': loss.item()}

    def get_latest_update(self) -> Optional[UpdateResult]:
        """
        Retourne la dernière mise à jour.

        Returns:
            Optional[UpdateResult]: Dernier résultat
        """
        if self.update_history:
            return self.update_history[-1]
        return None

    def get_best_performance(self) -> Dict[str, float]:
        """
        Retourne la meilleure performance.

        Returns:
            Dict[str, float]: Meilleure performance
        """
        return self.best_performance

    def get_history(self) -> List[Dict[str, Any]]:
        """
        Retourne l'historique des mises à jour.

        Returns:
            List[Dict[str, Any]]: Historique
        """
        return [r.to_dict() for r in self.update_history]

    def reset(self) -> None:
        """Réinitialise le metteur à jour"""
        self.data_buffer.clear()
        self.version = 0
        self.update_history = []
        self.performance_history = []
        self.best_performance = {}

        logger.info("ModelUpdater réinitialisé")

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde le metteur à jour.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si sauvegardé
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'version': self.version,
                'update_history': [r.to_dict() for r in self.update_history],
                'performance_history': self.performance_history,
                'best_performance': self.best_performance,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"ModelUpdater sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'ModelUpdater':
        """
        Charge un metteur à jour.

        Args:
            filepath: Chemin du fichier

        Returns:
            ModelUpdater: Metteur à jour chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = ModelUpdaterConfig(**data['config'])
            updater = cls(config)

            updater.version = data.get('version', 0)
            updater.best_performance = data.get('best_performance', {})

            # Restaurer l'historique
            for r in data.get('update_history', []):
                updater.update_history.append(UpdateResult(
                    success=r['success'],
                    version=r['version'],
                    performance_before=r['performance_before'],
                    performance_after=r['performance_after'],
                    improvement=r['improvement'],
                    samples_used=r['samples_used'],
                    time_taken=r['time_taken'],
                    timestamp=datetime.fromisoformat(r['timestamp']),
                    details=r['details'],
                ))

            updater.performance_history = data.get('performance_history', [])

            logger.info(f"ModelUpdater chargé: {filepath}")
            return updater

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_model_updater(
    update_strategy: str = 'periodic',
    update_frequency: int = 100,
    learning_rate: float = 0.001,
    **kwargs
) -> ModelUpdater:
    """
    Factory pour créer un metteur à jour de modèle.

    Args:
        update_strategy: Stratégie de mise à jour
        update_frequency: Fréquence de mise à jour
        learning_rate: Taux d'apprentissage
        **kwargs: Arguments supplémentaires

    Returns:
        ModelUpdater: Metteur à jour de modèle
    """
    config = ModelUpdaterConfig(
        update_strategy=update_strategy,
        update_frequency=update_frequency,
        learning_rate=learning_rate,
        **kwargs
    )
    return ModelUpdater(config)


__all__ = [
    'ModelUpdater',
    'ModelUpdaterConfig',
    'UpdateResult',
    'create_model_updater',
]
