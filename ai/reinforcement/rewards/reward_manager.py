# ai/reinforcement/rewards/reward_manager.py
"""
NEXUS AI TRADING SYSTEM - Reward Manager
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from collections import deque
import warnings
warnings.filterwarnings('ignore')

from ai.reinforcement.rewards.base_reward import BaseReward, RewardConfig

logger = logging.getLogger(__name__)


@dataclass
class RewardManagerConfig:
    """Configuration pour Reward Manager"""
    reward_functions: List[Dict[str, Any]] = field(default_factory=list)
    weights: Optional[List[float]] = None
    normalize_rewards: bool = True
    clip_rewards: bool = True
    clip_min: float = -10.0
    clip_max: float = 10.0
    use_adaptive_weights: bool = False
    adaptation_rate: float = 0.01
    history_size: int = 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            'reward_functions': self.reward_functions,
            'weights': self.weights,
            'normalize_rewards': self.normalize_rewards,
            'clip_rewards': self.clip_rewards,
            'clip_min': self.clip_min,
            'clip_max': self.clip_max,
            'use_adaptive_weights': self.use_adaptive_weights,
            'adaptation_rate': self.adaptation_rate,
            'history_size': self.history_size,
        }


class RewardManager:
    """
    Gestionnaire de récompenses pour l'apprentissage par renforcement.

    Features:
    - Multiples fonctions de récompense
    - Pondération adaptative
    - Normalisation
    - Clipping
    - Historique
    - Statistiques

    Example:
        ```python
        config = RewardManagerConfig(
            reward_functions=[
                {'type': 'pnl', 'params': {'use_log_returns': True}},
                {'type': 'sharpe', 'params': {'window_size': 20}},
                {'type': 'drawdown', 'params': {'max_drawdown_threshold': 0.1}},
            ],
            weights=[0.5, 0.3, 0.2]
        )
        manager = RewardManager(config)

        # Compute reward
        reward = manager.compute(pnl=100.0, portfolio_values=values)
        ```
    """

    def __init__(self, config: Optional[RewardManagerConfig] = None):
        self.config = config or RewardManagerConfig()
        self.reward_functions: List[BaseReward] = []
        self.weights = self.config.weights or []
        self.history: List[float] = []
        self.component_history: List[List[float]] = []
        self.stats = {
            'mean': 0.0,
            'std': 0.0,
            'min': float('inf'),
            'max': -float('inf'),
        }

        self._init_rewards()
        self._validate_weights()

        logger.info(f"RewardManager initialisé avec {len(self.reward_functions)} fonctions")

    def _init_rewards(self):
        """Initialise les fonctions de récompense"""
        from ai.reinforcement.rewards import RewardFactory

        for reward_config in self.config.reward_functions:
            reward_type = reward_config.get('type', 'continuous')
            params = reward_config.get('params', {})
            reward = RewardFactory.create(reward_type, **params)
            self.reward_functions.append(reward)

    def _validate_weights(self):
        """Valide et normalise les poids"""
        if not self.weights:
            self.weights = [1.0 / len(self.reward_functions)] * len(self.reward_functions)
        elif len(self.weights) != len(self.reward_functions):
            logger.warning("Nombre de poids différent du nombre de fonctions, réinitialisation")
            self.weights = [1.0 / len(self.reward_functions)] * len(self.reward_functions)

        # Normalisation
        total = sum(self.weights)
        if total > 0:
            self.weights = [w / total for w in self.weights]

    def compute(self, *args, **kwargs) -> float:
        """
        Calcule la récompense totale.

        Args:
            *args: Arguments variables
            **kwargs: Arguments nommés

        Returns:
            float: Récompense totale
        """
        # Calcul des récompenses composantes
        component_rewards = []
        for reward_fn in self.reward_functions:
            reward = reward_fn(*args, **kwargs)
            component_rewards.append(reward)

        # Stockage de l'historique
        self.component_history.append(component_rewards)
        if len(self.component_history) > self.config.history_size:
            self.component_history = self.component_history[-self.config.history_size:]

        # Calcul de la récompense totale
        total_reward = sum(w * r for w, r in zip(self.weights, component_rewards))

        # Normalisation
        if self.config.normalize_rewards:
            if self.history:
                mean = np.mean(self.history)
                std = np.std(self.history) + 1e-6
                total_reward = (total_reward - mean) / std

        # Clipping
        if self.config.clip_rewards:
            total_reward = np.clip(total_reward, self.config.clip_min, self.config.clip_max)

        # Historique et statistiques
        self.history.append(total_reward)
        if len(self.history) > self.config.history_size:
            self.history = self.history[-self.config.history_size:]

        self._update_stats(total_reward)

        # Adaptation des poids
        if self.config.use_adaptive_weights:
            self._update_weights(component_rewards)

        return total_reward

    def _update_stats(self, reward: float):
        """Met à jour les statistiques"""
        self.stats['min'] = min(self.stats['min'], reward)
        self.stats['max'] = max(self.stats['max'], reward)

        if self.history:
            self.stats['mean'] = np.mean(self.history)
            self.stats['std'] = np.std(self.history)

    def _update_weights(self, component_rewards: List[float]):
        """Met à jour les poids adaptativement"""
        # Performance basée sur la variance des composants
        variances = []
        if len(self.component_history) > 10:
            for i in range(len(self.reward_functions)):
                values = [comp[i] for comp in self.component_history[-20:]]
                var = np.var(values)
                variances.append(var)

            if sum(variances) > 0:
                # Les composants avec moins de variance reçoivent plus de poids
                new_weights = [1 / (var + 1e-6) for var in variances]
                total = sum(new_weights)
                if total > 0:
                    new_weights = [w / total for w in new_weights]

                    # Mise à jour lissée
                    lr = self.config.adaptation_rate
                    self.weights = [
                        (1 - lr) * w + lr * nw
                        for w, nw in zip(self.weights, new_weights)
                    ]

    def reset(self):
        """Réinitialise le gestionnaire"""
        self.history = []
        self.component_history = []
        self.stats = {
            'mean': 0.0,
            'std': 0.0,
            'min': float('inf'),
            'max': -float('inf'),
        }

        for reward_fn in self.reward_functions:
            if hasattr(reward_fn, 'reset'):
                reward_fn.reset()

    def get_stats(self) -> Dict[str, float]:
        """Retourne les statistiques"""
        return self.stats

    def get_component_stats(self) -> List[Dict[str, float]]:
        """Retourne les statistiques des composants"""
        stats = []
        for i, reward_fn in enumerate(self.reward_functions):
            reward_stats = reward_fn.get_stats()
            reward_stats['weight'] = self.weights[i]
            stats.append(reward_stats)
        return stats

    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres du gestionnaire"""
        return {
            'n_functions': len(self.reward_functions),
            'weights': self.weights,
            'functions': [r.get_params() for r in self.reward_functions],
            'stats': self.stats,
        }

    def set_weights(self, weights: List[float]):
        """
        Modifie les poids des composants.

        Args:
            weights: Nouveaux poids
        """
        if len(weights) != len(self.reward_functions):
            raise ValueError("Le nombre de poids doit correspondre au nombre de fonctions")

        total = sum(weights)
        if total > 0:
            self.weights = [w / total for w in weights]

    def add_reward(self, reward_fn: BaseReward, weight: float = 1.0):
        """
        Ajoute une fonction de récompense.

        Args:
            reward_fn: Fonction de récompense
            weight: Poids associé
        """
        self.reward_functions.append(reward_fn)
        self.weights.append(weight)

        # Normalisation
        total = sum(self.weights)
        if total > 0:
            self.weights = [w / total for w in self.weights]

    def remove_reward(self, index: int):
        """
        Supprime une fonction de récompense.

        Args:
            index: Index de la fonction
        """
        if 0 <= index < len(self.reward_functions):
            self.reward_functions.pop(index)
            self.weights.pop(index)

            # Normalisation
            total = sum(self.weights)
            if total > 0:
                self.weights = [w / total for w in self.weights]


def create_reward_manager(
    reward_functions: List[Dict[str, Any]],
    weights: Optional[List[float]] = None,
    **kwargs
) -> RewardManager:
    """
    Factory pour créer un gestionnaire de récompenses.

    Args:
        reward_functions: Liste des fonctions de récompense
        weights: Poids des fonctions
        **kwargs: Arguments supplémentaires

    Returns:
        RewardManager: Gestionnaire de récompenses
    """
    config = RewardManagerConfig(
        reward_functions=reward_functions,
        weights=weights,
        **kwargs
    )
    return RewardManager(config)


__all__ = [
    'RewardManager',
    'RewardManagerConfig',
    'create_reward_manager',
]
