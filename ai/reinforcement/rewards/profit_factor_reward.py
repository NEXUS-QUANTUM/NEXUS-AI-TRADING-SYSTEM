# ai/reinforcement/rewards/profit_factor_reward.py
"""
NEXUS AI TRADING SYSTEM - Profit Factor Reward Functions
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
class ProfitFactorRewardConfig(RewardConfig):
    """Configuration pour Profit Factor Reward"""
    window_size: int = 20
    min_trades: int = 5
    target_profit_factor: float = 1.5
    reward_positive: float = 0.1
    reward_negative: float = -0.1
    use_rolling_factor: bool = True
    use_win_rate_component: bool = True
    use_avg_win_loss_ratio: bool = True
    win_rate_weight: float = 0.3
    avg_win_loss_weight: float = 0.3

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'window_size': self.window_size,
            'min_trades': self.min_trades,
            'target_profit_factor': self.target_profit_factor,
            'reward_positive': self.reward_positive,
            'reward_negative': self.reward_negative,
            'use_rolling_factor': self.use_rolling_factor,
            'use_win_rate_component': self.use_win_rate_component,
            'use_avg_win_loss_ratio': self.use_avg_win_loss_ratio,
            'win_rate_weight': self.win_rate_weight,
            'avg_win_loss_weight': self.avg_win_loss_weight,
        })
        return base


class ProfitFactorReward(BaseReward):
    """
    Récompense basée sur le Profit Factor.

    Encourage les stratégies avec un bon ratio gain/perte
    et une bonne rentabilité globale.

    Features:
    - Rolling profit factor calculation
    - Win rate component
    - Average win/loss ratio
    - Trade count consideration
    - Adaptive thresholds

    Example:
        ```python
        config = ProfitFactorRewardConfig(
            window_size=20,
            target_profit_factor=1.5
        )
        reward_fn = ProfitFactorReward(config)

        # Compute reward based on trades
        reward = reward_fn(
            trades=trade_history,
            pnl=current_pnl
        )
        ```
    """

    def __init__(self, config: Optional[ProfitFactorRewardConfig] = None):
        super().__init__(config)
        self.config = config or ProfitFactorRewardConfig()
        self.trade_history = deque(maxlen=self.config.window_size)
        self.wins = deque(maxlen=self.config.window_size)
        self.losses = deque(maxlen=self.config.window_size)
        self.pnl_history = deque(maxlen=self.config.window_size)

    def compute(self, pnl: float, **kwargs) -> float:
        """
        Calcule la récompense basée sur le Profit Factor.

        Args:
            pnl: P&L du trade
            **kwargs: Arguments supplémentaires

        Returns:
            float: Récompense
        """
        self.trade_history.append(pnl)
        self.pnl_history.append(pnl)

        if pnl >= 0:
            self.wins.append(pnl)
        else:
            self.losses.append(-pnl)  # En valeur absolue

        if len(self.trade_history) < self.config.min_trades:
            return 0.0

        reward = 0.0

        # 1. Profit Factor
        if self.config.use_rolling_factor:
            total_wins = sum(self.wins)
            total_losses = sum(self.losses)

            if total_losses > 0:
                profit_factor = total_wins / total_losses
            else:
                profit_factor = float('inf')

            if profit_factor >= self.config.target_profit_factor:
                reward += self.config.reward_positive
            else:
                reward += self.config.reward_negative * (1 - profit_factor / self.config.target_profit_factor)

        # 2. Win Rate
        if self.config.use_win_rate_component:
            win_rate = len(self.wins) / len(self.trade_history)
            reward += self.config.win_rate_weight * (win_rate - 0.5) * 2

        # 3. Average Win/Loss Ratio
        if self.config.use_avg_win_loss_ratio:
            avg_win = np.mean(self.wins) if self.wins else 0
            avg_loss = np.mean(self.losses) if self.losses else 1

            if avg_loss > 0:
                ratio = avg_win / avg_loss
                reward += self.config.avg_win_loss_weight * (ratio - 1) / 1.5

        return reward * self.config.scale


class WinRateReward(BaseReward):
    """
    Récompense basée uniquement sur le taux de réussite.

    Encourage les stratégies avec un bon taux de réussite.
    """

    def __init__(
        self,
        window_size: int = 20,
        target_win_rate: float = 0.5,
        reward_positive: float = 0.1,
        reward_negative: float = -0.05,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.window_size = window_size
        self.target_win_rate = target_win_rate
        self.reward_positive = reward_positive
        self.reward_negative = reward_negative
        self.trade_history = deque(maxlen=window_size)

    def compute(self, pnl: float, **kwargs) -> float:
        """
        Calcule la récompense basée sur le taux de réussite.

        Args:
            pnl: P&L du trade

        Returns:
            float: Récompense
        """
        self.trade_history.append(1 if pnl >= 0 else 0)

        if len(self.trade_history) < self.window_size:
            return 0.0

        win_rate = sum(self.trade_history) / len(self.trade_history)

        if win_rate >= self.target_win_rate:
            return self.reward_positive * (win_rate / self.target_win_rate)
        return self.reward_negative * (1 - win_rate / self.target_win_rate)


class RiskRewardRatioReward(BaseReward):
    """
    Récompense basée sur le ratio risque/récompense.

    Encourage les trades avec un bon ratio gain/perte.
    """

    def __init__(
        self,
        target_ratio: float = 2.0,
        reward_scale: float = 0.1,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.target_ratio = target_ratio
        self.reward_scale = reward_scale

    def compute(self, risk: float, reward: float, **kwargs) -> float:
        """
        Calcule la récompense basée sur le ratio risque/récompense.

        Args:
            risk: Risque du trade
            reward: Récompense potentielle

        Returns:
            float: Récompense
        """
        if risk <= 0:
            return 0.0

        ratio = reward / risk
        score = min(ratio / self.target_ratio, 2.0) - 1.0
        return score * self.reward_scale


def create_profit_factor_reward(
    window_size: int = 20,
    target_profit_factor: float = 1.5,
    **kwargs
) -> ProfitFactorReward:
    """
    Factory pour créer une récompense de Profit Factor.

    Args:
        window_size: Taille de la fenêtre
        target_profit_factor: Profit Factor cible
        **kwargs: Arguments supplémentaires

    Returns:
        ProfitFactorReward: Récompense de Profit Factor
    """
    config = ProfitFactorRewardConfig(
        window_size=window_size,
        target_profit_factor=target_profit_factor,
        **kwargs
    )
    return ProfitFactorReward(config)


__all__ = [
    'ProfitFactorReward',
    'ProfitFactorRewardConfig',
    'WinRateReward',
    'RiskRewardRatioReward',
    'create_profit_factor_reward',
]
