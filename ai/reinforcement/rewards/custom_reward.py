# ai/reinforcement/rewards/custom_reward.py
"""
NEXUS AI TRADING SYSTEM - Custom Reward Functions
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Union, Tuple, Callable
from dataclasses import dataclass, field
import warnings
warnings.filterwarnings('ignore')

from ai.reinforcement.rewards.base_reward import BaseReward, RewardConfig

logger = logging.getLogger(__name__)


@dataclass
class CustomRewardConfig(RewardConfig):
    """Configuration pour Custom Reward"""
    reward_function: Optional[Callable] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    use_components: bool = False
    components: List[Dict[str, Any]] = field(default_factory=list)
    weights: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'parameters': self.parameters,
            'use_components': self.use_components,
            'components': self.components,
            'weights': self.weights,
        })
        return base


class CustomReward(BaseReward):
    """
    Fonction de récompense personnalisée.

    Permet de définir des récompenses complexes avec:
    - Fonction personnalisée
    - Combinaison de composants
    - Paramètres configurables
    - Poids ajustables

    Example:
        ```python
        # Avec fonction personnalisée
        def my_reward(state, action, next_state):
            return state['balance'] - next_state['balance']

        config = CustomRewardConfig(
            reward_function=my_reward,
            parameters={'scale': 1.0}
        )
        reward_fn = CustomReward(config)

        # Avec composants multiples
        config = CustomRewardConfig(
            use_components=True,
            components=[
                {'type': 'pnl', 'weight': 0.5},
                {'type': 'sharpe', 'weight': 0.3},
                {'type': 'drawdown', 'weight': 0.2},
            ]
        )
        reward_fn = CustomReward(config)
        ```
    """

    def __init__(self, config: Optional[CustomRewardConfig] = None):
        super().__init__(config)
        self.config = config or CustomRewardConfig()

        if self.config.use_components:
            self.components = self._init_components()

    def _init_components(self) -> List[BaseReward]:
        """Initialise les composants de récompense"""
        components = []
        weights = self.config.weights or [1.0 / len(self.config.components)] * len(self.config.components)

        for i, comp_config in enumerate(self.config.components):
            comp_type = comp_config.get('type', 'continuous')
            comp_weight = weights[i] if i < len(weights) else 1.0

            if comp_type == 'pnl':
                from ai.reinforcement.rewards.pnl_reward import PnLReward
                reward = PnLReward(**comp_config.get('params', {}))
            elif comp_type == 'sharpe':
                from ai.reinforcement.rewards.sharpe_reward import SharpeReward
                reward = SharpeReward(**comp_config.get('params', {}))
            elif comp_type == 'drawdown':
                from ai.reinforcement.rewards.drawdown_reward import DrawdownReward
                reward = DrawdownReward(**comp_config.get('params', {}))
            elif comp_type == 'risk_adjusted':
                from ai.reinforcement.rewards.risk_adjusted_reward import RiskAdjustedReward
                reward = RiskAdjustedReward(**comp_config.get('params', {}))
            elif comp_type == 'consistency':
                from ai.reinforcement.rewards.consistency_reward import ConsistencyReward
                reward = ConsistencyReward(**comp_config.get('params', {}))
            else:
                from ai.reinforcement.rewards.continuous_reward import ContinuousReward
                reward = ContinuousReward(**comp_config.get('params', {}))

            components.append({
                'reward': reward,
                'weight': comp_weight,
            })

        return components

    def compute(self, *args, **kwargs) -> float:
        """
        Calcule la récompense personnalisée.

        Args:
            *args: Arguments variables
            **kwargs: Arguments nommés

        Returns:
            float: Récompense
        """
        if self.config.reward_function is not None:
            # Utilisation de la fonction personnalisée
            return self.config.reward_function(*args, **kwargs)

        elif self.config.use_components and self.components:
            # Combinaison de composants
            total_reward = 0.0
            for comp in self.components:
                reward = comp['reward'](*args, **kwargs)
                total_reward += comp['weight'] * reward
            return total_reward

        else:
            # Par défaut: récompense basée sur le premier argument
            if args:
                return args[0]
            return 0.0


class CompositeReward(BaseReward):
    """
    Récompense composite combinant plusieurs fonctions.

    Permet de combiner des récompenses avec des poids ajustables.
    """

    def __init__(
        self,
        rewards: List[BaseReward],
        weights: Optional[List[float]] = None,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.rewards = rewards
        self.weights = weights or [1.0 / len(rewards)] * len(rewards)

        if len(self.weights) != len(self.rewards):
            raise ValueError("Le nombre de poids doit correspondre au nombre de récompenses")

    def compute(self, *args, **kwargs) -> float:
        """
        Calcule la récompense composite.

        Args:
            *args: Arguments variables
            **kwargs: Arguments nommés

        Returns:
            float: Récompense
        """
        total_reward = 0.0

        for reward, weight in zip(self.rewards, self.weights):
            reward_value = reward(*args, **kwargs)
            total_reward += weight * reward_value

        return total_reward

    def set_weights(self, weights: List[float]):
        """
        Modifie les poids des composants.

        Args:
            weights: Nouveaux poids
        """
        if len(weights) != len(self.rewards):
            raise ValueError("Le nombre de poids doit correspondre au nombre de récompenses")

        self.weights = weights


class AdaptiveReward(BaseReward):
    """
    Récompense adaptative qui s'ajuste pendant l'entraînement.

    Les poids des composants sont appris en fonction des performances.
    """

    def __init__(
        self,
        rewards: List[BaseReward],
        initial_weights: Optional[List[float]] = None,
        learning_rate: float = 0.01,
        window_size: int = 100,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.rewards = rewards
        self.learning_rate = learning_rate
        self.window_size = window_size

        self.weights = initial_weights or [1.0 / len(rewards)] * len(rewards)
        self.history = {i: [] for i in range(len(rewards))}
        self.reward_history = []

    def compute(self, *args, **kwargs) -> float:
        """
        Calcule la récompense adaptative.

        Args:
            *args: Arguments variables
            **kwargs: Arguments nommés

        Returns:
            float: Récompense
        """
        # Calcul des récompenses composantes
        component_rewards = []
        for reward in self.rewards:
            r = reward(*args, **kwargs)
            component_rewards.append(r)

        # Mise à jour de l'historique
        for i, r in enumerate(component_rewards):
            self.history[i].append(r)
            if len(self.history[i]) > self.window_size:
                self.history[i] = self.history[i][-self.window_size:]

        self.reward_history.append(sum(component_rewards))
        if len(self.reward_history) > self.window_size:
            self.reward_history = self.reward_history[-self.window_size:]

        # Adaptation des poids
        self._update_weights()

        # Calcul de la récompense totale
        total_reward = sum(w * r for w, r in zip(self.weights, component_rewards))

        return total_reward

    def _update_weights(self):
        """Met à jour les poids adaptativement"""
        if len(self.reward_history) < self.window_size:
            return

        # Performance de chaque composant
        performances = []
        for i in range(len(self.rewards)):
            rewards = np.array(self.history[i])
            if len(rewards) > 0:
                perf = np.mean(rewards) / (np.std(rewards) + 1e-6)
                performances.append(perf)
            else:
                performances.append(0.0)

        # Mise à jour des poids
        performances = np.array(performances)
        if performances.sum() > 0:
            target_weights = performances / performances.sum()
        else:
            target_weights = np.ones(len(self.rewards)) / len(self.rewards)

        # Mise à jour lissée
        self.weights = self.weights * (1 - self.learning_rate) + target_weights * self.learning_rate
        self.weights = self.weights / self.weights.sum()


def create_custom_reward(
    reward_function: Optional[Callable] = None,
    components: Optional[List[Dict[str, Any]]] = None,
    weights: Optional[List[float]] = None,
    **kwargs
) -> CustomReward:
    """
    Factory pour créer une récompense personnalisée.

    Args:
        reward_function: Fonction de récompense personnalisée
        components: Liste des composants de récompense
        weights: Poids des composants
        **kwargs: Arguments supplémentaires

    Returns:
        CustomReward: Récompense personnalisée
    """
    config = CustomRewardConfig(
        reward_function=reward_function,
        components=components or [],
        weights=weights or [],
        **kwargs
    )
    return CustomReward(config)


__all__ = [
    'CustomReward',
    'CustomRewardConfig',
    'CompositeReward',
    'AdaptiveReward',
    'create_custom_reward',
]
