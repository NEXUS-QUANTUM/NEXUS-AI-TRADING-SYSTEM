
# ai/reinforcement/rewards/base_reward.py
"""
NEXUS AI TRADING SYSTEM - Base Reward Functions
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


@dataclass
class RewardConfig:
    """Configuration de base pour les fonctions de récompense"""
    name: str = "base_reward"
    scale: float = 1.0
    clip_min: Optional[float] = None
    clip_max: Optional[float] = None
    use_shaping: bool = False
    shaping_weight: float = 0.1

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'scale': self.scale,
            'clip_min': self.clip_min,
            'clip_max': self.clip_max,
            'use_shaping': self.use_shaping,
            'shaping_weight': self.shaping_weight,
        }


class BaseReward(ABC):
    """
    Classe de base pour les fonctions de récompense.

    Features:
    - Reward scaling
    - Clipping
    - Reward shaping
    - History tracking
    - Statistics

    Example:
        ```python
        class CustomReward(BaseReward):
            def compute(self, state, action, next_state):
                return state['balance'] - next_state['balance']

        reward_fn = CustomReward(config)
        reward = reward_fn.compute(state, action, next_state)
        ```
    """

    def __init__(self, config: Optional[RewardConfig] = None):
        self.config = config or RewardConfig()
        self.history: List[float] = []
        self.stats = {
            'mean': 0.0,
            'std': 0.0,
            'min': float('inf'),
            'max': -float('inf'),
        }

    @abstractmethod
    def compute(self, *args, **kwargs) -> float:
        """
        Calcule la récompense.

        Args:
            *args: Arguments variables
            **kwargs: Arguments nommés

        Returns:
            float: Récompense
        """
        pass

    def __call__(self, *args, **kwargs) -> float:
        """
        Calcule et traite la récompense.

        Args:
            *args: Arguments variables
            **kwargs: Arguments nommés

        Returns:
            float: Récompense traitée
        """
        reward = self.compute(*args, **kwargs)

        # Scaling
        reward = reward * self.config.scale

        # Clipping
        if self.config.clip_min is not None:
            reward = max(reward, self.config.clip_min)
        if self.config.clip_max is not None:
            reward = min(reward, self.config.clip_max)

        # Historique
        self.history.append(reward)
        self._update_stats(reward)

        return reward

    def _update_stats(self, reward: float):
        """Met à jour les statistiques"""
        self.stats['min'] = min(self.stats['min'], reward)
        self.stats['max'] = max(self.stats['max'], reward)

        if len(self.history) > 0:
            self.stats['mean'] = np.mean(self.history)
            self.stats['std'] = np.std(self.history)

    def reset(self):
        """Réinitialise l'historique et les statistiques"""
        self.history = []
        self.stats = {
            'mean': 0.0,
            'std': 0.0,
            'min': float('inf'),
            'max': -float('inf'),
        }

    def get_stats(self) -> Dict[str, float]:
        """Retourne les statistiques"""
        return self.stats

    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres de la fonction de récompense"""
        return self.config.to_dict()


class SparseReward(BaseReward):
    """
    Récompense sparse: positive seulement en cas de succès.

    Example:
        ```python
        reward_fn = SparseReward(
            success_threshold=0.1,
            success_reward=1.0,
            failure_reward=-1.0
        )
        reward = reward_fn(profit)  # 1.0 si profit > 0.1, -1.0 sinon
        ```
    """

    def __init__(
        self,
        success_threshold: float = 0.0,
        success_reward: float = 1.0,
        failure_reward: float = -1.0,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.success_threshold = success_threshold
        self.success_reward = success_reward
        self.failure_reward = failure_reward

    def compute(self, value: float, **kwargs) -> float:
        """
        Calcule la récompense sparse.

        Args:
            value: Valeur à évaluer

        Returns:
            float: Récompense
        """
        if value >= self.success_threshold:
            return self.success_reward
        return self.failure_reward


class ContinuousReward(BaseReward):
    """
    Récompense continue proportionnelle à la valeur.

    Example:
        ```python
        reward_fn = ContinuousReward(
            scale=1.0,
            min_reward=-10.0,
            max_reward=10.0
        )
        reward = reward_fn(profit)  # profit * scale, clampé à [-10, 10]
        ```
    """

    def __init__(
        self,
        scale: float = 1.0,
        min_reward: Optional[float] = None,
        max_reward: Optional[float] = None,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.scale = scale
        self.min_reward = min_reward
        self.max_reward = max_reward

    def compute(self, value: float, **kwargs) -> float:
        """
        Calcule la récompense continue.

        Args:
            value: Valeur à évaluer

        Returns:
            float: Récompense
        """
        reward = value * self.scale

        if self.min_reward is not None:
            reward = max(reward, self.min_reward)
        if self.max_reward is not None:
            reward = min(reward, self.max_reward)

        return reward


class RewardFactory:
    """Factory pour créer des fonctions de récompense"""

    @staticmethod
    def create(
        reward_type: str = 'continuous',
        **kwargs
    ) -> BaseReward:
        """
        Crée une fonction de récompense.

        Args:
            reward_type: Type de récompense ('continuous', 'sparse', 'custom')
            **kwargs: Arguments de configuration

        Returns:
            BaseReward: Fonction de récompense

        Example:
            ```python
            reward_fn = RewardFactory.create(
                'sparse',
                success_threshold=0.1,
                success_reward=1.0
            )
            ```
        """
        if reward_type == 'continuous':
            return ContinuousReward(**kwargs)

        elif reward_type == 'sparse':
            return SparseReward(**kwargs)

        elif reward_type == 'custom':
            from ai.reinforcement.rewards.custom_reward import CustomReward
            return CustomReward(**kwargs)

        else:
            raise ValueError(f"Type de récompense non supporté: {reward_type}")


def create_reward(
    reward_type: str = 'continuous',
    **kwargs
) -> BaseReward:
    """
    Factory pour créer des fonctions de récompense.

    Args:
        reward_type: Type de récompense
        **kwargs: Arguments de configuration

    Returns:
        BaseReward: Fonction de récompense
    """
    return RewardFactory.create(reward_type, **kwargs)


__all__ = [
    'BaseReward',
    'RewardConfig',
    'SparseReward',
    'ContinuousReward',
    'RewardFactory',
    'create_reward',
]
