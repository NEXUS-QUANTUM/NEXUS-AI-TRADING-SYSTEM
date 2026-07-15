# ai/reinforcement/rewards/sharpe_reward.py
"""
NEXUS AI TRADING SYSTEM - Sharpe Ratio Reward
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
class SharpeRewardConfig(RewardConfig):
    """Configuration pour Sharpe Reward"""
    risk_free_rate: float = 0.02
    window_size: int = 20
    target_sharpe: float = 1.0
    reward_scale: float = 1.0
    use_rolling_sharpe: bool = True
    use_annualized: bool = True
    trading_days: int = 252

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'risk_free_rate': self.risk_free_rate,
            'window_size': self.window_size,
            'target_sharpe': self.target_sharpe,
            'reward_scale': self.reward_scale,
            'use_rolling_sharpe': self.use_rolling_sharpe,
            'use_annualized': self.use_annualized,
            'trading_days': self.trading_days,
        })
        return base


class SharpeReward(BaseReward):
    """
    Récompense basée sur le Sharpe Ratio.

    Encourage les stratégies avec un bon ratio risque/rendement.

    Features:
    - Rolling Sharpe calculation
    - Annualized Sharpe
    - Target Sharpe threshold
    - Risk-free rate adjustment

    Example:
        ```python
        config = SharpeRewardConfig(
            risk_free_rate=0.02,
            window_size=20,
            target_sharpe=1.0
        )
        reward_fn = SharpeReward(config)

        # Compute reward based on returns
        reward = reward_fn(returns=returns)
        ```
    """

    def __init__(self, config: Optional[SharpeRewardConfig] = None):
        super().__init__(config)
        self.config = config or SharpeRewardConfig()
        self.returns_history = deque(maxlen=self.config.window_size)

    def compute(self, returns: Union[float, List[float], np.ndarray], **kwargs) -> float:
        """
        Calcule la récompense basée sur le Sharpe Ratio.

        Args:
            returns: Rendements ou liste de rendements
            **kwargs: Arguments supplémentaires

        Returns:
            float: Récompense
        """
        if isinstance(returns, (int, float)):
            self.returns_history.append(returns)
        else:
            for r in returns:
                self.returns_history.append(r)

        if len(self.returns_history) < 2:
            return 0.0

        returns_arr = np.array(self.returns_history)

        # Calcul du Sharpe Ratio
        excess_returns = returns_arr - self.config.risk_free_rate / self.config.trading_days

        mean_return = np.mean(excess_returns)
        std_return = np.std(excess_returns) + 1e-6

        sharpe = mean_return / std_return

        if self.config.use_annualized:
            sharpe = sharpe * np.sqrt(self.config.trading_days)

        # Normalisation
        normalized_sharpe = sharpe / self.config.target_sharpe
        reward = np.clip(normalized_sharpe, -1.0, 2.0)

        return reward * self.config.reward_scale


class RollingSharpeReward(BaseReward):
    """
    Récompense basée sur le Sharpe Ratio glissant.

    Calcule le Sharpe sur une fenêtre glissante.
    """

    def __init__(
        self,
        window_size: int = 20,
        target_sharpe: float = 1.0,
        risk_free_rate: float = 0.02,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.window_size = window_size
        self.target_sharpe = target_sharpe
        self.risk_free_rate = risk_free_rate
        self.returns_history = deque(maxlen=window_size * 2)

    def compute(self, returns: Union[float, List[float], np.ndarray], **kwargs) -> float:
        """
        Calcule la récompense basée sur le Sharpe glissant.

        Args:
            returns: Rendements

        Returns:
            float: Récompense
        """
        if isinstance(returns, (int, float)):
            self.returns_history.append(returns)
        else:
            for r in returns:
                self.returns_history.append(r)

        if len(self.returns_history) < self.window_size + 1:
            return 0.0

        # Calcul du Sharpe glissant
        rewards = []
        for i in range(len(self.returns_history) - self.window_size):
            window = list(self.returns_history)[i:i + self.window_size]
            window_arr = np.array(window)

            excess = window_arr - self.risk_free_rate / 252
            mean_return = np.mean(excess)
            std_return = np.std(excess) + 1e-6

            sharpe = mean_return / std_return * np.sqrt(252)
            rewards.append(sharpe)

        if not rewards:
            return 0.0

        # Moyenne des Sharpe glissants
        avg_sharpe = np.mean(rewards)
        normalized = avg_sharpe / self.target_sharpe

        return np.clip(normalized, -1.0, 2.0)


def create_sharpe_reward(
    risk_free_rate: float = 0.02,
    window_size: int = 20,
    target_sharpe: float = 1.0,
    **kwargs
) -> SharpeReward:
    """
    Factory pour créer une récompense Sharpe.

    Args:
        risk_free_rate: Taux sans risque
        window_size: Taille de la fenêtre
        target_sharpe: Sharpe Ratio cible
        **kwargs: Arguments supplémentaires

    Returns:
        SharpeReward: Récompense Sharpe
    """
    config = SharpeRewardConfig(
        risk_free_rate=risk_free_rate,
        window_size=window_size,
        target_sharpe=target_sharpe,
        **kwargs
    )
    return SharpeReward(config)


__all__ = [
    'SharpeReward',
    'SharpeRewardConfig',
    'RollingSharpeReward',
    'create_sharpe_reward',
]
