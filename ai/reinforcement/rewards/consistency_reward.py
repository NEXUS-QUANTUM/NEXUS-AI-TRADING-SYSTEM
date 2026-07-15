# ai/reinforcement/rewards/consistency_reward.py
"""
NEXUS AI TRADING SYSTEM - Consistency Reward Functions
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
class ConsistencyRewardConfig(RewardConfig):
    """Configuration pour Consistency Reward"""
    window_size: int = 10
    consistency_threshold: float = 0.5
    reward_positive: float = 0.1
    reward_negative: float = -0.1
    use_rolling_std: bool = True
    use_correlation: bool = False
    use_trend_consistency: bool = True

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'window_size': self.window_size,
            'consistency_threshold': self.consistency_threshold,
            'reward_positive': self.reward_positive,
            'reward_negative': self.reward_negative,
            'use_rolling_std': self.use_rolling_std,
            'use_correlation': self.use_correlation,
            'use_trend_consistency': self.use_trend_consistency,
        })
        return base


class ConsistencyReward(BaseReward):
    """
    Récompense basée sur la cohérence des actions.

    Encourage les actions cohérentes avec les tendances passées.

    Features:
    - Rolling consistency
    - Trend following
    - Volatility-adjusted
    - Action sequence analysis

    Example:
        ```python
        config = ConsistencyRewardConfig(
            window_size=10,
            consistency_threshold=0.5
        )
        reward_fn = ConsistencyReward(config)

        # Compute reward based on action sequence
        reward = reward_fn(
            actions=action_history,
            prices=price_history
        )
        ```
    """

    def __init__(self, config: Optional[ConsistencyRewardConfig] = None):
        super().__init__(config)
        self.config = config or ConsistencyRewardConfig()
        self.action_history = deque(maxlen=self.config.window_size)
        self.value_history = deque(maxlen=self.config.window_size)

    def compute(self, action: float, value: float, **kwargs) -> float:
        """
        Calcule la récompense de cohérence.

        Args:
            action: Action actuelle
            value: Valeur associée (prix, P&L, etc.)
            **kwargs: Arguments supplémentaires

        Returns:
            float: Récompense de cohérence
        """
        self.action_history.append(action)
        self.value_history.append(value)

        if len(self.action_history) < self.config.window_size:
            return 0.0

        actions = np.array(self.action_history)
        values = np.array(self.value_history)

        reward = 0.0

        # 1. Cohérence des actions (peu de changements brusques)
        if self.config.use_rolling_std:
            action_std = np.std(actions[-5:])
            if action_std < self.config.consistency_threshold:
                reward += self.config.reward_positive
            else:
                reward += self.config.reward_negative

        # 2. Cohérence avec la tendance
        if self.config.use_trend_consistency:
            trend = np.polyfit(np.arange(len(values)), values, 1)[0]
            action_trend = np.mean(actions[-3:])
            if (trend > 0 and action_trend > 0) or (trend < 0 and action_trend < 0):
                reward += self.config.reward_positive
            else:
                reward += self.config.reward_negative

        # 3. Corrélation action-valeur
        if self.config.use_correlation and len(actions) > 2:
            corr = np.corrcoef(actions, values)[0, 1]
            if not np.isnan(corr):
                if abs(corr) > 0.5:
                    reward += self.config.reward_positive * abs(corr)
                else:
                    reward += self.config.reward_negative * (1 - abs(corr))

        return reward * self.config.scale


class ActionConsistencyReward(BaseReward):
    """
    Récompense basée sur la cohérence des actions uniquement.

    Encourage la stabilité des actions et la réduction des churn.
    """

    def __init__(
        self,
        window_size: int = 10,
        max_change: float = 0.3,
        reward_positive: float = 0.1,
        reward_negative: float = -0.1,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.window_size = window_size
        self.max_change = max_change
        self.reward_positive = reward_positive
        self.reward_negative = reward_negative
        self.action_history = deque(maxlen=window_size)

    def compute(self, action: float, **kwargs) -> float:
        """
        Calcule la récompense de cohérence des actions.

        Args:
            action: Action actuelle

        Returns:
            float: Récompense
        """
        self.action_history.append(action)

        if len(self.action_history) < 2:
            return 0.0

        # Changement moyen
        changes = np.abs(np.diff(self.action_history))
        avg_change = np.mean(changes)

        if avg_change < self.max_change:
            return self.reward_positive
        return self.reward_negative


class TrendConsistencyReward(BaseReward):
    """
    Récompense basée sur la cohérence avec la tendance du marché.
    """

    def __init__(
        self,
        window_size: int = 20,
        reward_correct: float = 0.1,
        reward_incorrect: float = -0.1,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.window_size = window_size
        self.reward_correct = reward_correct
        self.reward_incorrect = reward_incorrect
        self.price_history = deque(maxlen=window_size)

    def compute(self, action: float, price: float, **kwargs) -> float:
        """
        Calcule la récompense de cohérence avec la tendance.

        Args:
            action: Action (1=buy, -1=sell, 0=hold)
            price: Prix actuel

        Returns:
            float: Récompense
        """
        self.price_history.append(price)

        if len(self.price_history) < self.window_size:
            return 0.0

        # Tendance
        prices = np.array(self.price_history)
        trend = np.polyfit(np.arange(len(prices)), prices, 1)[0]

        # Vérification de la cohérence
        if (trend > 0 and action > 0) or (trend < 0 and action < 0):
            return self.reward_correct
        elif action == 0:
            return 0.0
        return self.reward_incorrect


def create_consistency_reward(
    window_size: int = 10,
    consistency_threshold: float = 0.5,
    **kwargs
) -> ConsistencyReward:
    """
    Factory pour créer une récompense de cohérence.

    Args:
        window_size: Taille de la fenêtre
        consistency_threshold: Seuil de cohérence
        **kwargs: Arguments supplémentaires

    Returns:
        ConsistencyReward: Récompense de cohérence
    """
    config = ConsistencyRewardConfig(
        window_size=window_size,
        consistency_threshold=consistency_threshold,
        **kwargs
    )
    return ConsistencyReward(config)


__all__ = [
    'ConsistencyReward',
    'ConsistencyRewardConfig',
    'ActionConsistencyReward',
    'TrendConsistencyReward',
    'create_consistency_reward',
]
