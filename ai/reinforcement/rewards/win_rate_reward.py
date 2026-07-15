# ai/reinforcement/rewards/win_rate_reward.py
"""
NEXUS AI TRADING SYSTEM - Win Rate Reward Functions
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
class WinRateRewardConfig(RewardConfig):
    """Configuration pour Win Rate Reward"""
    window_size: int = 20
    min_trades: int = 5
    target_win_rate: float = 0.5
    reward_positive: float = 0.1
    reward_negative: float = -0.05
    use_rolling_win_rate: bool = True
    use_streak_bonus: bool = False
    streak_bonus: float = 0.05
    use_consecutive_loss_penalty: bool = False
    consecutive_loss_penalty: float = 0.1

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'window_size': self.window_size,
            'min_trades': self.min_trades,
            'target_win_rate': self.target_win_rate,
            'reward_positive': self.reward_positive,
            'reward_negative': self.reward_negative,
            'use_rolling_win_rate': self.use_rolling_win_rate,
            'use_streak_bonus': self.use_streak_bonus,
            'streak_bonus': self.streak_bonus,
            'use_consecutive_loss_penalty': self.use_consecutive_loss_penalty,
            'consecutive_loss_penalty': self.consecutive_loss_penalty,
        })
        return base


class WinRateReward(BaseReward):
    """
    Récompense basée sur le taux de réussite.

    Encourage les stratégies avec un bon taux de réussite
    et pénalise les séries de pertes.

    Features:
    - Rolling win rate
    - Win/loss streak bonuses
    - Consecutive loss penalties
    - Minimum trade requirement

    Example:
        ```python
        config = WinRateRewardConfig(
            window_size=20,
            target_win_rate=0.5,
            use_streak_bonus=True
        )
        reward_fn = WinRateReward(config)

        # Compute reward based on trade result
        reward = reward_fn(pnl=10.0)
        ```
    """

    def __init__(self, config: Optional[WinRateRewardConfig] = None):
        super().__init__(config)
        self.config = config or WinRateRewardConfig()
        self.trade_history = deque(maxlen=self.config.window_size)
        self.win_streak = 0
        self.loss_streak = 0

    def compute(self, pnl: float, **kwargs) -> float:
        """
        Calcule la récompense basée sur le taux de réussite.

        Args:
            pnl: P&L du trade
            **kwargs: Arguments supplémentaires

        Returns:
            float: Récompense
        """
        is_win = pnl >= 0
        self.trade_history.append(1 if is_win else 0)

        if is_win:
            self.win_streak += 1
            self.loss_streak = 0
        else:
            self.loss_streak += 1
            self.win_streak = 0

        if len(self.trade_history) < self.config.min_trades:
            return 0.0

        reward = 0.0

        # 1. Taux de réussite
        if self.config.use_rolling_win_rate:
            win_rate = sum(self.trade_history) / len(self.trade_history)

            if win_rate >= self.config.target_win_rate:
                reward += self.config.reward_positive * (win_rate / self.config.target_win_rate)
            else:
                reward += self.config.reward_negative * (1 - win_rate / self.config.target_win_rate)

        # 2. Bonus pour série de gains
        if self.config.use_streak_bonus and self.win_streak >= 3:
            reward += self.config.streak_bonus * (self.win_streak / 3)

        # 3. Pénalité pour série de pertes
        if self.config.use_consecutive_loss_penalty and self.loss_streak >= 2:
            reward -= self.config.consecutive_loss_penalty * (self.loss_streak / 2)

        return reward * self.config.scale


class ConsecutiveWinReward(BaseReward):
    """
    Récompense basée sur les séries de gains consécutifs.

    Encourage la constance des performances.
    """

    def __init__(
        self,
        win_streak_bonus: float = 0.1,
        max_bonus: float = 1.0,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.win_streak_bonus = win_streak_bonus
        self.max_bonus = max_bonus
        self.win_streak = 0

    def compute(self, pnl: float, **kwargs) -> float:
        """
        Calcule la récompense basée sur les séries de gains.

        Args:
            pnl: P&L du trade

        Returns:
            float: Récompense
        """
        if pnl >= 0:
            self.win_streak += 1
            bonus = min(self.win_streak * self.win_streak_bonus, self.max_bonus)
            return bonus
        else:
            self.win_streak = 0
            return 0.0


class ConsecutiveLossPenalty(BaseReward):
    """
    Pénalité pour les séries de pertes consécutives.

    Décourage les séries de trades perdants.
    """

    def __init__(
        self,
        loss_penalty: float = 0.1,
        max_penalty: float = 1.0,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.loss_penalty = loss_penalty
        self.max_penalty = max_penalty
        self.loss_streak = 0

    def compute(self, pnl: float, **kwargs) -> float:
        """
        Calcule la pénalité pour séries de pertes.

        Args:
            pnl: P&L du trade

        Returns:
            float: Pénalité
        """
        if pnl < 0:
            self.loss_streak += 1
            penalty = min(self.loss_streak * self.loss_penalty, self.max_penalty)
            return -penalty
        else:
            self.loss_streak = 0
            return 0.0


def create_win_rate_reward(
    window_size: int = 20,
    target_win_rate: float = 0.5,
    **kwargs
) -> WinRateReward:
    """
    Factory pour créer une récompense de taux de réussite.

    Args:
        window_size: Taille de la fenêtre
        target_win_rate: Taux de réussite cible
        **kwargs: Arguments supplémentaires

    Returns:
        WinRateReward: Récompense de taux de réussite
    """
    config = WinRateRewardConfig(
        window_size=window_size,
        target_win_rate=target_win_rate,
        **kwargs
    )
    return WinRateReward(config)


__all__ = [
    'WinRateReward',
    'WinRateRewardConfig',
    'ConsecutiveWinReward',
    'ConsecutiveLossPenalty',
    'create_win_rate_reward',
]
