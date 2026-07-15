# ai/reinforcement/rewards/pnl_reward.py
"""
NEXUS AI TRADING SYSTEM - P&L Reward Functions
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
class PnLRewardConfig(RewardConfig):
    """Configuration pour P&L Reward"""
    use_log_returns: bool = False
    use_absolute_pnl: bool = False
    use_cumulative_pnl: bool = False
    use_normalized_pnl: bool = True
    normalization_scale: float = 1000.0
    min_reward: Optional[float] = -10.0
    max_reward: Optional[float] = 10.0
    use_ema_smoothing: bool = False
    ema_alpha: float = 0.1

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'use_log_returns': self.use_log_returns,
            'use_absolute_pnl': self.use_absolute_pnl,
            'use_cumulative_pnl': self.use_cumulative_pnl,
            'use_normalized_pnl': self.use_normalized_pnl,
            'normalization_scale': self.normalization_scale,
            'min_reward': self.min_reward,
            'max_reward': self.max_reward,
            'use_ema_smoothing': self.use_ema_smoothing,
            'ema_alpha': self.ema_alpha,
        })
        return base


class PnLReward(BaseReward):
    """
    Récompense basée sur les P&L (Profits and Losses).

    Features:
    - Log returns
    - Absolute P&L
    - Cumulative P&L
    - Normalized P&L
    - EMA smoothing

    Example:
        ```python
        config = PnLRewardConfig(
            use_log_returns=True,
            normalization_scale=1000.0
        )
        reward_fn = PnLReward(config)

        # Compute reward based on P&L
        reward = reward_fn(pnl=100.0)
        ```
    """

    def __init__(self, config: Optional[PnLRewardConfig] = None):
        super().__init__(config)
        self.config = config or PnLRewardConfig()
        self.cumulative_pnl = 0.0
        self.smooth_pnl = 0.0
        self.pnl_history = deque(maxlen=100)

    def compute(self, pnl: float, **kwargs) -> float:
        """
        Calcule la récompense basée sur le P&L.

        Args:
            pnl: Profit ou perte
            **kwargs: Arguments supplémentaires

        Returns:
            float: Récompense
        """
        self.pnl_history.append(pnl)
        self.cumulative_pnl += pnl

        # Log returns
        if self.config.use_log_returns:
            if self.cumulative_pnl > 0:
                reward = np.log(1 + self.cumulative_pnl / self.config.normalization_scale)
            else:
                reward = -np.log(1 - self.cumulative_pnl / self.config.normalization_scale)
        else:
            reward = pnl

        # Absolute P&L
        if self.config.use_absolute_pnl:
            reward = abs(reward)

        # Cumulative P&L
        if self.config.use_cumulative_pnl:
            reward = self.cumulative_pnl / self.config.normalization_scale

        # Normalization
        if self.config.use_normalized_pnl:
            reward = reward / self.config.normalization_scale

        # EMA smoothing
        if self.config.use_ema_smoothing:
            self.smooth_pnl = self.config.ema_alpha * reward + (1 - self.config.ema_alpha) * self.smooth_pnl
            reward = self.smooth_pnl

        # Clipping
        if self.config.min_reward is not None:
            reward = max(reward, self.config.min_reward)
        if self.config.max_reward is not None:
            reward = min(reward, self.config.max_reward)

        return reward * self.config.scale


class LogPnLReward(BaseReward):
    """
    Récompense basée sur les P&L logarithmiques.

    Utilise le log des rendements pour une meilleure stabilité.
    """

    def __init__(
        self,
        scale: float = 1.0,
        min_reward: float = -5.0,
        max_reward: float = 5.0,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.scale = scale
        self.min_reward = min_reward
        self.max_reward = max_reward

    def compute(self, pnl: float, initial_balance: float = 10000.0, **kwargs) -> float:
        """
        Calcule la récompense logarithmique.

        Args:
            pnl: Profit ou perte
            initial_balance: Solde initial

        Returns:
            float: Récompense
        """
        new_balance = initial_balance + pnl
        if new_balance <= 0:
            return -10.0

        log_return = np.log(new_balance / initial_balance)
        reward = log_return * self.scale
        reward = np.clip(reward, self.min_reward, self.max_reward)

        return reward


class CumulativePnLReward(BaseReward):
    """
    Récompense basée sur le P&L cumulé.

    Encourage la croissance du portefeuille sur le long terme.
    """

    def __init__(
        self,
        scale: float = 0.01,
        min_reward: float = -10.0,
        max_reward: float = 10.0,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.scale = scale
        self.min_reward = min_reward
        self.max_reward = max_reward
        self.cumulative_pnl = 0.0

    def compute(self, pnl: float, **kwargs) -> float:
        """
        Calcule la récompense basée sur le P&L cumulé.

        Args:
            pnl: Profit ou perte

        Returns:
            float: Récompense
        """
        self.cumulative_pnl += pnl
        reward = self.cumulative_pnl * self.scale
        reward = np.clip(reward, self.min_reward, self.max_reward)

        return reward


def create_pnl_reward(
    use_log_returns: bool = False,
    normalization_scale: float = 1000.0,
    **kwargs
) -> PnLReward:
    """
    Factory pour créer une récompense P&L.

    Args:
        use_log_returns: Utiliser les rendements logarithmiques
        normalization_scale: Échelle de normalisation
        **kwargs: Arguments supplémentaires

    Returns:
        PnLReward: Récompense P&L
    """
    config = PnLRewardConfig(
        use_log_returns=use_log_returns,
        normalization_scale=normalization_scale,
        **kwargs
    )
    return PnLReward(config)


__all__ = [
    'PnLReward',
    'PnLRewardConfig',
    'LogPnLReward',
    'CumulativePnLReward',
    'create_pnl_reward',
]
