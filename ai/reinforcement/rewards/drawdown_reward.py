# ai/reinforcement/rewards/drawdown_reward.py
"""
NEXUS AI TRADING SYSTEM - Drawdown Reward Functions
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
class DrawdownRewardConfig(RewardConfig):
    """Configuration pour Drawdown Reward"""
    window_size: int = 20
    max_drawdown_threshold: float = 0.1
    reward_positive: float = 0.1
    reward_negative: float = -0.5
    use_rolling_drawdown: bool = True
    use_peak_drawdown: bool = True
    use_recovery_reward: bool = True
    recovery_reward: float = 0.2

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'window_size': self.window_size,
            'max_drawdown_threshold': self.max_drawdown_threshold,
            'reward_positive': self.reward_positive,
            'reward_negative': self.reward_negative,
            'use_rolling_drawdown': self.use_rolling_drawdown,
            'use_peak_drawdown': self.use_peak_drawdown,
            'use_recovery_reward': self.use_recovery_reward,
            'recovery_reward': self.recovery_reward,
        })
        return base


class DrawdownReward(BaseReward):
    """
    Récompense basée sur le drawdown.

    Encourage la gestion du risque en pénalisant les drawdowns
    et en récompensant les recoveries.

    Features:
    - Rolling drawdown calculation
    - Peak drawdown tracking
    - Recovery bonuses
    - Drawdown penalties
    - Adaptive thresholds

    Example:
        ```python
        config = DrawdownRewardConfig(
            window_size=20,
            max_drawdown_threshold=0.1,
            reward_negative=-0.5
        )
        reward_fn = DrawdownReward(config)

        # Compute reward based on portfolio values
        reward = reward_fn(portfolio_values)
        ```
    """

    def __init__(self, config: Optional[DrawdownRewardConfig] = None):
        super().__init__(config)
        self.config = config or DrawdownRewardConfig()
        self.peak = None
        self.portfolio_history = deque(maxlen=self.config.window_size)
        self.drawdown_history = deque(maxlen=self.config.window_size)
        self.max_drawdown_seen = 0.0
        self.recovery_mode = False
        self.recovery_start = None

    def compute(self, portfolio_value: float, **kwargs) -> float:
        """
        Calcule la récompense basée sur le drawdown.

        Args:
            portfolio_value: Valeur actuelle du portefeuille
            **kwargs: Arguments supplémentaires

        Returns:
            float: Récompense
        """
        self.portfolio_history.append(portfolio_value)

        if self.peak is None:
            self.peak = portfolio_value
            return 0.0

        # Mise à jour du pic
        if portfolio_value > self.peak:
            self.peak = portfolio_value

        # Drawdown actuel
        current_drawdown = (self.peak - portfolio_value) / (self.peak + 1e-6)

        # Historique des drawdowns
        self.drawdown_history.append(current_drawdown)
        self.max_drawdown_seen = max(self.max_drawdown_seen, current_drawdown)

        reward = 0.0

        # 1. Pénalité pour drawdown
        if self.config.use_rolling_drawdown:
            if current_drawdown > self.config.max_drawdown_threshold:
                reward += self.config.reward_negative * (current_drawdown / self.config.max_drawdown_threshold)
            else:
                reward += self.config.reward_positive * (1 - current_drawdown / self.config.max_drawdown_threshold)

        # 2. Pénalité pour drawdown max (historique)
        if self.config.use_peak_drawdown:
            if self.max_drawdown_seen > self.config.max_drawdown_threshold:
                reward += self.config.reward_negative * 0.5

        # 3. Récompense pour récupération
        if self.config.use_recovery_reward:
            if current_drawdown < self.config.max_drawdown_threshold * 0.5:
                if self.recovery_mode:
                    # Sortie de recovery
                    reward += self.config.recovery_reward
                    self.recovery_mode = False
            else:
                self.recovery_mode = True

        return reward * self.config.scale


class MaxDrawdownReward(BaseReward):
    """
    Récompense basée sur le drawdown maximum global.

    Pénalise les drawdowns sévères et encourage la stabilité.
    """

    def __init__(
        self,
        max_drawdown_limit: float = 0.2,
        penalty_scale: float = 2.0,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.max_drawdown_limit = max_drawdown_limit
        self.penalty_scale = penalty_scale
        self.peak = None
        self.max_drawdown = 0.0

    def compute(self, portfolio_value: float, **kwargs) -> float:
        """
        Calcule la récompense basée sur le drawdown maximum.

        Args:
            portfolio_value: Valeur actuelle du portefeuille

        Returns:
            float: Récompense
        """
        if self.peak is None:
            self.peak = portfolio_value
            return 0.0

        if portfolio_value > self.peak:
            self.peak = portfolio_value

        current_drawdown = (self.peak - portfolio_value) / (self.peak + 1e-6)
        self.max_drawdown = max(self.max_drawdown, current_drawdown)

        if self.max_drawdown > self.max_drawdown_limit:
            penalty = (self.max_drawdown - self.max_drawdown_limit) * self.penalty_scale
            return -penalty

        return 0.0


class RollingDrawdownReward(BaseReward):
    """
    Récompense basée sur le drawdown glissant.

    Calcule le drawdown sur une fenêtre glissante
    pour une pénalité plus réactive.
    """

    def __init__(
        self,
        window_size: int = 20,
        max_drawdown: float = 0.1,
        penalty_scale: float = 1.0,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.window_size = window_size
        self.max_drawdown = max_drawdown
        self.penalty_scale = penalty_scale
        self.values = deque(maxlen=window_size)

    def compute(self, portfolio_value: float, **kwargs) -> float:
        """
        Calcule la récompense basée sur le drawdown glissant.

        Args:
            portfolio_value: Valeur actuelle du portefeuille

        Returns:
            float: Récompense
        """
        self.values.append(portfolio_value)

        if len(self.values) < self.window_size:
            return 0.0

        # Drawdown sur la fenêtre
        values = np.array(self.values)
        peak = np.max(values)
        current_drawdown = (peak - values[-1]) / (peak + 1e-6)

        if current_drawdown > self.max_drawdown:
            return -self.penalty_scale * (current_drawdown / self.max_drawdown)

        return 0.0


def create_drawdown_reward(
    window_size: int = 20,
    max_drawdown_threshold: float = 0.1,
    **kwargs
) -> DrawdownReward:
    """
    Factory pour créer une récompense de drawdown.

    Args:
        window_size: Taille de la fenêtre
        max_drawdown_threshold: Seuil de drawdown maximum
        **kwargs: Arguments supplémentaires

    Returns:
        DrawdownReward: Récompense de drawdown
    """
    config = DrawdownRewardConfig(
        window_size=window_size,
        max_drawdown_threshold=max_drawdown_threshold,
        **kwargs
    )
    return DrawdownReward(config)


__all__ = [
    'DrawdownReward',
    'DrawdownRewardConfig',
    'MaxDrawdownReward',
    'RollingDrawdownReward',
    'create_drawdown_reward',
]
