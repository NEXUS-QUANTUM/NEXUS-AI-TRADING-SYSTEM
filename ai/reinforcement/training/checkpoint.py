# ai/reinforcement/training/checkpoint.py
"""
NEXUS AI TRADING SYSTEM - Training Checkpoint Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import os
import pickle
import json
import shutil
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


@dataclass
class CheckpointConfig:
    """Configuration pour les checkpoints"""
    checkpoint_dir: str = "./checkpoints"
    max_checkpoints: int = 10
    save_best_only: bool = True
    save_frequency: int = 10  # Épisodes
    save_on_exit: bool = True
    auto_load_best: bool = True
    metric: str = "reward"  # 'reward', 'loss', 'sharpe'
    metric_mode: str = "max"  # 'max' ou 'min'
    save_optimizer: bool = True
    save_config: bool = True
    save_metadata: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'checkpoint_dir': self.checkpoint_dir,
            'max_checkpoints': self.max_checkpoints,
            'save_best_only': self.save_best_only,
            'save_frequency': self.save_frequency,
            'save_on_exit': self.save_on_exit,
            'auto_load_best': self.auto_load_best,
            'metric': self.metric,
            'metric_mode': self.metric_mode,
            'save_optimizer': self.save_optimizer,
            'save_config': self.save_config,
            'save_metadata': self.save_metadata,
        }


@dataclass
class Checkpoint:
    """Point de contrôle"""
    episode: int
    step: int
    state: Dict[str, Any]
    metrics: Dict[str, float]
    timestamp: datetime
    filepath: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'episode': self.episode,
            'step': self.step,
            'metrics': self.metrics,
            'timestamp': self.timestamp.isoformat(),
            'filepath': self.filepath,
        }


class CheckpointManager:
    """
    Gestionnaire de checkpoints pour l'entraînement RL.

    Features:
    - Sauvegarde automatique des checkpoints
    - Conservation des meilleurs modèles
    - Chargement automatique
    - Métriques de performance
    - Rotation des checkpoints

    Example:
        ```python
        config = CheckpointConfig(
            checkpoint_dir="./runs/exp1/checkpoints",
            max_checkpoints=5,
            save_best_only=True,
            save_frequency=10
        )
        manager = CheckpointManager(config)

        # Sauvegarde
        manager.save(agent, episode, step, metrics)

        # Chargement
        checkpoint = manager.load(agent)
        ```
    """

    def __init__(self, config: Optional[CheckpointConfig] = None):
        self.config = config or CheckpointConfig()
        self.checkpoints: List[Checkpoint] = []
        self.best_checkpoint: Optional[Checkpoint] = None
        self.best_metric_value = float('-inf') if self.config.metric_mode == 'max' else float('inf')

        # Création du répertoire
        os.makedirs(self.config.checkpoint_dir, exist_ok=True)

        # Chargement des checkpoints existants
        self._load_checkpoint_index()

        logger.info(f"CheckpointManager initialisé: {self.config.checkpoint_dir}")

    def _load_checkpoint_index(self):
        """Charge l'index des checkpoints existants"""
        index_file = os.path.join(self.config.checkpoint_dir, "index.json")

        if os.path.exists(index_file):
            try:
                with open(index_file, 'r') as f:
                    data = json.load(f)
                    self.checkpoints = []
                    for cp_data in data.get('checkpoints', []):
                        cp = Checkpoint(
                            episode=cp_data['episode'],
                            step=cp_data['step'],
                            state={},
                            metrics=cp_data['metrics'],
                            timestamp=datetime.fromisoformat(cp_data['timestamp']),
                            filepath=cp_data['filepath']
                        )
                        self.checkpoints.append(cp)
                        self._update_best(cp)
            except Exception as e:
                logger.warning(f"Erreur de chargement de l'index: {e}")

    def _update_best(self, checkpoint: Checkpoint):
        """Met à jour le meilleur checkpoint"""
        if self.config.metric not in checkpoint.metrics:
            return

        value = checkpoint.metrics[self.config.metric]

        if self.config.metric_mode == 'max':
            if value > self.best_metric_value:
                self.best_metric_value = value
                self.best_checkpoint = checkpoint
        else:
            if value < self.best_metric_value:
                self.best_metric_value = value
                self.best_checkpoint = checkpoint

    def _save_index(self):
        """Sauvegarde l'index des checkpoints"""
        index_file = os.path.join(self.config.checkpoint_dir, "index.json")

        data = {
            'checkpoints': [cp.to_dict() for cp in self.checkpoints],
            'best_checkpoint': self.best_checkpoint.to_dict() if self.best_checkpoint else None,
            'best_metric_value': self.best_metric_value,
            'updated_at': datetime.now().isoformat(),
        }

        try:
            with open(index_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Erreur de sauvegarde de l'index: {e}")

    def _cleanup_old_checkpoints(self):
        """Supprime les checkpoints les plus anciens"""
        if len(self.checkpoints) <= self.config.max_checkpoints:
            return

        # Trier par épisode
        sorted_cps = sorted(self.checkpoints, key=lambda x: x.episode)

        # Supprimer les plus anciens
        to_remove = sorted_cps[:-self.config.max_checkpoints]

        for cp in to_remove:
            if os.path.exists(cp.filepath):
                os.remove(cp.filepath)
            self.checkpoints.remove(cp)

        # Mise à jour du meilleur
        self.best_checkpoint = None
        self.best_metric_value = float('-inf') if self.config.metric_mode == 'max' else float('inf')
        for cp in self.checkpoints:
            self._update_best(cp)

    def save(
        self,
        agent: Any,
        episode: int,
        step: int,
        metrics: Dict[str, float],
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Optional[Checkpoint]:
        """
        Sauvegarde un checkpoint.

        Args:
            agent: Agent à sauvegarder
            episode: Épisode actuel
            step: Étape actuelle
            metrics: Métriques
            additional_data: Données supplémentaires

        Returns:
            Optional[Checkpoint]: Checkpoint sauvegardé ou None
        """
        # Vérification de la fréquence
        if self.config.save_best_only:
            # Vérifier si c'est le meilleur
            if self.config.metric not in metrics:
                return None

            value = metrics[self.config.metric]
            is_best = False

            if self.config.metric_mode == 'max':
                is_best = value > self.best_metric_value
            else:
                is_best = value < self.best_metric_value

            if not is_best:
                return None

        elif episode % self.config.save_frequency != 0:
            return None

        # Création du checkpoint
        timestamp = datetime.now()
        filename = f"checkpoint_{episode:06d}_{timestamp.strftime('%Y%m%d_%H%M%S')}.pkl"
        filepath = os.path.join(self.config.checkpoint_dir, filename)

        # Données à sauvegarder
        data = {
            'episode': episode,
            'step': step,
            'metrics': metrics,
            'timestamp': timestamp.isoformat(),
            'config': self.config.to_dict(),
        }

        # Sauvegarde de l'agent
        if hasattr(agent, 'save'):
            agent_data = agent.save_to_dict() if hasattr(agent, 'save_to_dict') else agent
            data['agent'] = agent_data
        else:
            data['agent'] = agent

        # Sauvegarde de l'optimiseur
        if self.config.save_optimizer and hasattr(agent, 'optimizer'):
            data['optimizer_state'] = agent.optimizer.state_dict()

        # Sauvegarde de la configuration
        if self.config.save_config and hasattr(agent, 'config'):
            data['agent_config'] = agent.config.to_dict() if hasattr(agent.config, 'to_dict') else agent.config

        # Données supplémentaires
        if additional_data:
            data['additional'] = additional_data

        # Sauvegarde
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            # Création du checkpoint
            checkpoint = Checkpoint(
                episode=episode,
                step=step,
                state=data,
                metrics=metrics,
                timestamp=timestamp,
                filepath=filepath
            )

            self.checkpoints.append(checkpoint)
            self._update_best(checkpoint)
            self._cleanup_old_checkpoints()
            self._save_index()

            logger.info(f"Checkpoint sauvegardé: {filepath}")
            return checkpoint

        except Exception as e:
            logger.error(f"Erreur de sauvegarde du checkpoint: {e}")
            return None

    def load(
        self,
        agent: Any,
        checkpoint: Optional[Checkpoint] = None
    ) -> Optional[Checkpoint]:
        """
        Charge un checkpoint.

        Args:
            agent: Agent à charger
            checkpoint: Checkpoint spécifique (None pour le meilleur)

        Returns:
            Optional[Checkpoint]: Checkpoint chargé
        """
        if checkpoint is None:
            if self.config.auto_load_best:
                checkpoint = self.best_checkpoint
            else:
                checkpoint = self.checkpoints[-1] if self.checkpoints else None

        if checkpoint is None:
            logger.warning("Aucun checkpoint disponible")
            return None

        try:
            with open(checkpoint.filepath, 'rb') as f:
                data = pickle.load(f)

            # Chargement de l'agent
            if hasattr(agent, 'load_from_dict'):
                agent.load_from_dict(data['agent'])
            elif hasattr(agent, 'load_state_dict'):
                agent.load_state_dict(data['agent'])
            else:
                # Copie des attributs
                for key, value in data['agent'].items():
                    if hasattr(agent, key):
                        setattr(agent, key, value)

            # Chargement de l'optimiseur
            if self.config.save_optimizer and 'optimizer_state' in data and hasattr(agent, 'optimizer'):
                agent.optimizer.load_state_dict(data['optimizer_state'])

            logger.info(f"Checkpoint chargé: {checkpoint.filepath} (épisode {checkpoint.episode})")
            return checkpoint

        except Exception as e:
            logger.error(f"Erreur de chargement du checkpoint: {e}")
            return None

    def get_best_checkpoint(self) -> Optional[Checkpoint]:
        """Retourne le meilleur checkpoint"""
        return self.best_checkpoint

    def get_latest_checkpoint(self) -> Optional[Checkpoint]:
        """Retourne le checkpoint le plus récent"""
        if self.checkpoints:
            return max(self.checkpoints, key=lambda x: x.episode)
        return None

    def get_checkpoints(self) -> List[Dict[str, Any]]:
        """Retourne la liste des checkpoints"""
        return [cp.to_dict() for cp in self.checkpoints]

    def delete_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """
        Supprime un checkpoint.

        Args:
            checkpoint: Checkpoint à supprimer

        Returns:
            bool: True si supprimé
        """
        try:
            if os.path.exists(checkpoint.filepath):
                os.remove(checkpoint.filepath)

            self.checkpoints.remove(checkpoint)

            if self.best_checkpoint == checkpoint:
                self.best_checkpoint = None
                self.best_metric_value = float('-inf') if self.config.metric_mode == 'max' else float('inf')
                for cp in self.checkpoints:
                    self._update_best(cp)

            self._save_index()
            logger.info(f"Checkpoint supprimé: {checkpoint.filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de suppression: {e}")
            return False

    def clear(self) -> bool:
        """
        Supprime tous les checkpoints.

        Returns:
            bool: True si réussi
        """
        try:
            for cp in self.checkpoints:
                if os.path.exists(cp.filepath):
                    os.remove(cp.filepath)

            self.checkpoints.clear()
            self.best_checkpoint = None
            self.best_metric_value = float('-inf') if self.config.metric_mode == 'max' else float('inf')

            # Suppression de l'index
            index_file = os.path.join(self.config.checkpoint_dir, "index.json")
            if os.path.exists(index_file):
                os.remove(index_file)

            logger.info("Tous les checkpoints supprimés")
            return True

        except Exception as e:
            logger.error(f"Erreur de suppression: {e}")
            return False


def create_checkpoint_manager(
    checkpoint_dir: str = "./checkpoints",
    max_checkpoints: int = 10,
    save_best_only: bool = True,
    **kwargs
) -> CheckpointManager:
    """
    Factory pour créer un gestionnaire de checkpoints.

    Args:
        checkpoint_dir: Répertoire des checkpoints
        max_checkpoints: Nombre maximum de checkpoints
        save_best_only: Sauvegarder uniquement les meilleurs
        **kwargs: Arguments supplémentaires

    Returns:
        CheckpointManager: Gestionnaire de checkpoints
    """
    config = CheckpointConfig(
        checkpoint_dir=checkpoint_dir,
        max_checkpoints=max_checkpoints,
        save_best_only=save_best_only,
        **kwargs
    )
    return CheckpointManager(config)


__all__ = [
    'CheckpointManager',
    'CheckpointConfig',
    'Checkpoint',
    'create_checkpoint_manager',
]
