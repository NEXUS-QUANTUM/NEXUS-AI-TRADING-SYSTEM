# ai/reinforcement/rewards/risk_adjusted_reward.py
"""
NEXUS AI TRADING SYSTEM - Risk-Adjusted Reward Functions
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
class RiskAdjustedRewardConfig(RewardConfig):
    """Configuration pour Risk Adjusted Reward"""
    risk_free_rate: float = 0.02
    window_size: int = 20
    use_sharpe_ratio: bool = True
    use_sortino_ratio: bool = False
    use_calmar_ratio: bool = False
    use_omega_ratio: bool = False
    target_sharpe: float = 1.0
    target_sortino: float = 1.5
    target_calmar: float = 1.0
    reward_scale: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'risk_free_rate': self.risk_free_rate,
            'window_size': self.window_size,
            'use_sharpe_ratio': self.use_sharpe_ratio,
            'use_sortino_ratio': self.use_sortino_ratio,
            'use_calmar_ratio': self.use_calmar_ratio,
            'use_omega_ratio': self.use_omega_ratio,
            'target_sharpe': self.target_sharpe,
            'target_sortino': self.target_sortino,
            'target_calmar': self.target_calmar,
            'reward_scale': self.reward_scale,
        })
        return base


class RiskAdjustedReward(BaseReward):
    """
    Récompense basée sur les ratios ajustés au risque.

    Encourage les stratégies avec un bon ratio risque/rendement.

    Features:
    - Sharpe Ratio
    - Sortino Ratio
    - Calmar Ratio
    - Omega Ratio
    - Rolling calculation

    Example:
        ```python
        config = RiskAdjustedRewardConfig(
            risk_free_rate=0.02,
            window_size=20,
            use_sharpe_ratio=True,
            target_sharpe=1.0
        )
        reward_fn = RiskAdjustedReward(config)

        # Compute reward based on returns
        reward = reward_fn(returns=returns)
        ```
    """

    def __init__(self, config: Optional[RiskAdjustedRewardConfig] = None):
        super().__init__(config)
        self.config = config or RiskAdjustedRewardConfig()
        self.returns_history = deque(maxlen=self.config.window_size)

    def compute(self, returns: Union[float, List[float], np.ndarray], **kwargs) -> float:
        """
        Calcule la récompense ajustée au risque.

        Args:
            returns: Rendements ou liste de rendements
            **kwargs: Arguments supplémentaires

        Returns:
            float: Récompense ajustée au risque
        """
        if isinstance(returns, (int, float)):
            self.returns_history.append(returns)
        else:
            for r in returns:
                self.returns_history.append(r)

        if len(self.returns_history) < 2:
            return 0.0

        returns_arr = np.array(self.returns_history)
        excess_returns = returns_arr - self.config.risk_free_rate / 252

        reward = 0.0
        n_components = 0

        # 1. Sharpe Ratio
        if self.config.use_sharpe_ratio:
            sharpe = self._compute_sharpe(excess_returns)
            reward += self._normalize_ratio(sharpe, self.config.target_sharpe)
            n_components += 1

        # 2. Sortino Ratio
        if self.config.use_sortino_ratio:
            sortino = self._compute_sortino(excess_returns)
            reward += self._normalize_ratio(sortino, self.config.target_sortino)
            n_components += 1

        # 3. Calmar Ratio
        if self.config.use_calmar_ratio:
            calmar = self._compute_calmar(returns_arr)
            reward += self._normalize_ratio(calmar, self.config.target_calmar)
            n_components += 1

        # 4. Omega Ratio
        if self.config.use_omega_ratio:
            omega = self._compute_omega(returns_arr)
            reward += self._normalize_ratio(omega, 1.0)
            n_components += 1

        if n_components > 0:
            reward = reward / n_components

        return reward * self.config.reward_scale

    def _compute_sharpe(self, excess_returns: np.ndarray) -> float:
        """Calcule le Sharpe Ratio"""
        if len(excess_returns) < 2:
            return 0.0

        mean_return = np.mean(excess_returns)
        std_return = np.std(excess_returns) + 1e-6

        return mean_return / std_return * np.sqrt(252)

    def _compute_sortino(self, excess_returns: np.ndarray) -> float:
        """Calcule le Sortino Ratio"""
        if len(excess_returns) < 2:
            return 0.0

        negative_returns = excess_returns[excess_returns < 0]
        if len(negative_returns) == 0:
            return float('inf')

        downside_std = np.std(negative_returns) + 1e-6
        mean_return = np.mean(excess_returns)

        return mean_return / downside_std * np.sqrt(252)

    def _compute_calmar(self, returns: np.ndarray) -> float:
        """Calcule le Calmar Ratio"""
        if len(returns) < 2:
            return 0.0

        annualized_return = np.mean(returns) * 252

        # Maximum drawdown
        cumulative = np.cumprod(1 + returns)
        peak = np.maximum.accumulate(cumulative)
        drawdown = (peak - cumulative) / peak
        max_drawdown = np.max(drawdown) + 1e-6

        return annualized_return / max_drawdown

    def _compute_omega(self, returns: np.ndarray) -> float:
        """Calcule le Omega Ratio"""
        threshold = self.config.risk_free_rate / 252

        gains = returns[returns > threshold] - threshold
        losses = threshold - returns[returns < threshold]

        if len(gains) == 0:
            return 0.0
        if len(losses) == 0:
            return float('inf')

        total_gains = np.sum(gains)
        total_losses = np.sum(losses) + 1e-6

        return total_gains / total_losses

    def _normalize_ratio(self, ratio: float, target: float) -> float:
        """Normalise le ratio par rapport à la cible"""
        if ratio == float('inf'):
            return 2.0

        normalized = ratio / (target + 1e-6)
        return np.clip(normalized, -1.0, 2.0)


class SharpeReward(BaseReward):
    """
    Récompense basée uniquement sur le Sharpe Ratio.
    """

    def __init__(
        self,
        risk_free_rate: float = 0.02,
        window_size: int = 20,
        target_sharpe: float = 1.0,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.risk_free_rate = risk_free_rate
        self.window_size = window_size
        self.target_sharpe = target_sharpe
        self.returns_history = deque(maxlen=window_size)

    def compute(self, returns: Union[float, List[float], np.ndarray], **kwargs) -> float:
        """
        Calcule la récompense basée sur le Sharpe Ratio.

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

        if len(self.returns_history) < 2:
            return 0.0

        returns_arr = np.array(self.returns_history)
        excess_returns = returns_arr - self.risk_free_rate / 252

        mean_return = np.mean(excess_returns)
        std_return = np.std(excess_returns) + 1e-6

        sharpe = mean_return / std_return * np.sqrt(252)
        normalized = sharpe / self.target_sharpe

        return np.clip(normalized, -1.0, 2.0)


class SortinoReward(BaseReward):
    """
    Récompense basée sur le Sortino Ratio.
    """

    def __init__(
        self,
        risk_free_rate: float = 0.02,
        window_size: int = 20,
        target_sortino: float = 1.5,
        config: Optional[RewardConfig] = None
    ):
        super().__init__(config)
        self.risk_free_rate = risk_free_rate
        self.window_size = window_size
        self.target_sortino = target_sortino
        self.returns_history = deque(maxlen=window_size)

    def compute(self, returns: Union[float, List[float], np.ndarray], **kwargs) -> float:
        """
        Calcule la récompense basée sur le Sortino Ratio.

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

        if len(self.returns_history) < 2:
            return 0.0

        returns_arr = np.array(self.returns_history)
        excess_returns = returns_arr - self.risk_free_rate / 252

        negative_returns = excess_returns[excess_returns < 0]
        if len(negative_returns) == 0:
            return 2.0

        downside_std = np.std(negative_returns) + 1e-6
        mean_return = np.mean(excess_returns)

        sortino = mean_return / downside_std * np.sqrt(252)
        normalized = sortino / self.target_sortino

        return np.clip(normalized, -1.0, 2.0)


def create_risk_adjusted_reward(
    use_sharpe_ratio: bool = True,
    target_sharpe: float = 1.0,
    **kwargs
) -> RiskAdjustedReward:
    """
    Factory pour créer une récompense ajustée au risque.

    Args:
        use_sharpe_ratio: Utiliser le Sharpe Ratio
        target_sharpe: Sharpe Ratio cible
        **kwargs: Arguments supplémentaires

    Returns:
        RiskAdjustedReward: Récompense ajustée au risque
    """
    config = RiskAdjustedRewardConfig(
        use_sharpe_ratio=use_sharpe_ratio,
        target_sharpe=target_sharpe,
        **kwargs
    )
    return RiskAdjustedReward(config)


__all__ = [
    'RiskAdjustedReward',
    'RiskAdjustedRewardConfig',
    'SharpeReward',
    'SortinoReward',
    'create_risk_adjusted_reward',
]
