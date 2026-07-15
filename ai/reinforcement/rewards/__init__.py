# ai/reinforcement/rewards/__init__.py
"""
NEXUS AI TRADING SYSTEM - Reward Functions Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de fonctions de récompense pour l'apprentissage par renforcement.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.reinforcement.rewards.base_reward import (
    BaseReward,
    RewardConfig,
    SparseReward,
    ContinuousReward,
    RewardFactory,
    create_reward,
)

from ai.reinforcement.rewards.consistency_reward import (
    ConsistencyReward,
    ConsistencyRewardConfig,
    ActionConsistencyReward,
    TrendConsistencyReward,
    create_consistency_reward,
)

from ai.reinforcement.rewards.custom_reward import (
    CustomReward,
    CustomRewardConfig,
    CompositeReward,
    AdaptiveReward,
    create_custom_reward,
)

from ai.reinforcement.rewards.drawdown_reward import (
    DrawdownReward,
    DrawdownRewardConfig,
    MaxDrawdownReward,
    RollingDrawdownReward,
    create_drawdown_reward,
)

from ai.reinforcement.rewards.pnl_reward import (
    PnLReward,
    PnLRewardConfig,
    LogPnLReward,
    CumulativePnLReward,
    create_pnl_reward,
)

from ai.reinforcement.rewards.profit_factor_reward import (
    ProfitFactorReward,
    ProfitFactorRewardConfig,
    WinRateReward,
    RiskRewardRatioReward,
    create_profit_factor_reward,
)

from ai.reinforcement.rewards.reward_manager import (
    RewardManager,
    RewardManagerConfig,
    create_reward_manager,
)

from ai.reinforcement.rewards.risk_adjusted_reward import (
    RiskAdjustedReward,
    RiskAdjustedRewardConfig,
    SharpeReward,
    SortinoReward,
    create_risk_adjusted_reward,
)

from ai.reinforcement.rewards.sharpe_reward import (
    SharpeReward as SharpeRewardBase,
    SharpeRewardConfig,
    RollingSharpeReward,
    create_sharpe_reward,
)

from ai.reinforcement.rewards.win_rate_reward import (
    WinRateReward as WinRateRewardBase,
    WinRateRewardConfig,
    ConsecutiveWinReward,
    ConsecutiveLossPenalty,
    create_win_rate_reward,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Base
    'BaseReward',
    'RewardConfig',
    'SparseReward',
    'ContinuousReward',
    'RewardFactory',
    'create_reward',
    
    # Consistency
    'ConsistencyReward',
    'ConsistencyRewardConfig',
    'ActionConsistencyReward',
    'TrendConsistencyReward',
    'create_consistency_reward',
    
    # Custom
    'CustomReward',
    'CustomRewardConfig',
    'CompositeReward',
    'AdaptiveReward',
    'create_custom_reward',
    
    # Drawdown
    'DrawdownReward',
    'DrawdownRewardConfig',
    'MaxDrawdownReward',
    'RollingDrawdownReward',
    'create_drawdown_reward',
    
    # P&L
    'PnLReward',
    'PnLRewardConfig',
    'LogPnLReward',
    'CumulativePnLReward',
    'create_pnl_reward',
    
    # Profit Factor
    'ProfitFactorReward',
    'ProfitFactorRewardConfig',
    'WinRateReward',
    'RiskRewardRatioReward',
    'create_profit_factor_reward',
    
    # Reward Manager
    'RewardManager',
    'RewardManagerConfig',
    'create_reward_manager',
    
    # Risk Adjusted
    'RiskAdjustedReward',
    'RiskAdjustedRewardConfig',
    'SharpeReward',
    'SortinoReward',
    'create_risk_adjusted_reward',
    
    # Sharpe
    'SharpeRewardBase',
    'SharpeRewardConfig',
    'RollingSharpeReward',
    'create_sharpe_reward',
    
    # Win Rate
    'WinRateRewardBase',
    'WinRateRewardConfig',
    'ConsecutiveWinReward',
    'ConsecutiveLossPenalty',
    'create_win_rate_reward',
]


def create_reward_function(
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
    
    Examples:
        ```python
        # P&L Reward
        reward = create_reward_function(
            'pnl',
            use_log_returns=True,
            normalization_scale=1000.0
        )
        
        # Sharpe Reward
        reward = create_reward_function(
            'sharpe',
            risk_free_rate=0.02,
            window_size=20,
            target_sharpe=1.0
        )
        
        # Drawdown Reward
        reward = create_reward_function(
            'drawdown',
            max_drawdown_threshold=0.1,
            reward_negative=-0.5
        )
        
        # Custom Reward
        def my_reward(pnl, **kwargs):
            return pnl / 1000.0
        reward = create_reward_function(
            'custom',
            reward_function=my_reward
        )
        ```
    """
    reward_type = reward_type.lower()
    
    if reward_type == 'continuous':
        return ContinuousReward(**kwargs)
    
    elif reward_type == 'sparse':
        return SparseReward(**kwargs)
    
    elif reward_type == 'pnl':
        return create_pnl_reward(**kwargs)
    
    elif reward_type == 'sharpe':
        return create_sharpe_reward(**kwargs)
    
    elif reward_type == 'drawdown':
        return create_drawdown_reward(**kwargs)
    
    elif reward_type == 'consistency':
        return create_consistency_reward(**kwargs)
    
    elif reward_type == 'profit_factor':
        return create_profit_factor_reward(**kwargs)
    
    elif reward_type == 'risk_adjusted':
        return create_risk_adjusted_reward(**kwargs)
    
    elif reward_type == 'win_rate':
        return create_win_rate_reward(**kwargs)
    
    elif reward_type == 'custom':
        return create_custom_reward(**kwargs)
    
    else:
        raise ValueError(f"Type de récompense non supporté: {reward_type}")


def get_available_rewards() -> List[str]:
    """
    Retourne la liste des fonctions de récompense disponibles.
    
    Returns:
        List[str]: Liste des types de récompenses
    """
    return [
        'continuous',
        'sparse',
        'pnl',
        'sharpe',
        'drawdown',
        'consistency',
        'profit_factor',
        'risk_adjusted',
        'win_rate',
        'custom',
    ]


def get_reward_info(reward_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de récompense.
    
    Args:
        reward_type: Type de récompense
    
    Returns:
        Dict[str, Any]: Informations sur la récompense
    """
    info = {
        'continuous': {
            'name': 'Continuous Reward',
            'description': 'Récompense continue proportionnelle à la valeur',
            'use_cases': ['P&L simple', 'Rendements', 'Progression linéaire'],
            'parameters': ['scale', 'min_reward', 'max_reward'],
        },
        'sparse': {
            'name': 'Sparse Reward',
            'description': 'Récompense binaire (succès/échec)',
            'use_cases': ['Objectifs binaires', 'Atteinte de seuils', 'Classification'],
            'parameters': ['success_threshold', 'success_reward', 'failure_reward'],
        },
        'pnl': {
            'name': 'P&L Reward',
            'description': 'Récompense basée sur les profits et pertes',
            'use_cases': ['Trading', 'Portfolio management', 'Risk management'],
            'parameters': ['use_log_returns', 'normalization_scale', 'use_ema_smoothing'],
        },
        'sharpe': {
            'name': 'Sharpe Reward',
            'description': 'Récompense basée sur le Sharpe Ratio',
            'use_cases': ['Risk-adjusted returns', 'Portfolio optimization', 'Performance evaluation'],
            'parameters': ['risk_free_rate', 'window_size', 'target_sharpe'],
        },
        'drawdown': {
            'name': 'Drawdown Reward',
            'description': 'Récompense basée sur le drawdown',
            'use_cases': ['Risk management', 'Capital preservation', 'Stop-loss strategies'],
            'parameters': ['window_size', 'max_drawdown_threshold', 'reward_negative'],
        },
        'consistency': {
            'name': 'Consistency Reward',
            'description': 'Récompense basée sur la cohérence des actions',
            'use_cases': ['Stable strategies', 'Reducing churn', 'Trend following'],
            'parameters': ['window_size', 'consistency_threshold', 'reward_positive'],
        },
        'profit_factor': {
            'name': 'Profit Factor Reward',
            'description': 'Récompense basée sur le Profit Factor',
            'use_cases': ['Win rate optimization', 'Risk/reward ratio', 'Trade quality'],
            'parameters': ['window_size', 'target_profit_factor', 'win_rate_weight'],
        },
        'risk_adjusted': {
            'name': 'Risk-Adjusted Reward',
            'description': 'Récompense ajustée au risque',
            'use_cases': ['Sharpe ratio', 'Sortino ratio', 'Calmar ratio'],
            'parameters': ['risk_free_rate', 'window_size', 'use_sharpe_ratio'],
        },
        'win_rate': {
            'name': 'Win Rate Reward',
            'description': 'Récompense basée sur le taux de réussite',
            'use_cases': ['Win rate optimization', 'Streak bonuses', 'Loss penalties'],
            'parameters': ['window_size', 'target_win_rate', 'use_streak_bonus'],
        },
    }
    
    return info.get(reward_type.lower(), {})


def get_reward_recommendation(
    objective: str = 'maximize_pnl',
    risk_tolerance: str = 'medium',
    time_horizon: str = 'long'
) -> Dict[str, Any]:
    """
    Recommande une fonction de récompense selon les besoins.
    
    Args:
        objective: Objectif ('maximize_pnl', 'minimize_risk', 'maximize_sharpe', 'consistency')
        risk_tolerance: Tolérance au risque ('low', 'medium', 'high')
        time_horizon: Horizon temporel ('short', 'medium', 'long')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    if objective == 'maximize_pnl':
        if risk_tolerance == 'low':
            return {
                'recommended_reward': {
                    'type': 'sharpe',
                    'description': 'Sharpe Reward pour maximiser le rendement ajusté au risque'
                },
                'alternative_rewards': ['pnl', 'drawdown'],
                'parameters': {'risk_free_rate': 0.02, 'target_sharpe': 1.0}
            }
        else:
            return {
                'recommended_reward': {
                    'type': 'pnl',
                    'description': 'P&L Reward pour maximiser les profits'
                },
                'alternative_rewards': ['profit_factor'],
                'parameters': {'use_log_returns': True, 'normalization_scale': 1000.0}
            }
    
    elif objective == 'minimize_risk':
        return {
            'recommended_reward': {
                'type': 'drawdown',
                'description': 'Drawdown Reward pour minimiser les pertes'
            },
            'alternative_rewards': ['risk_adjusted'],
            'parameters': {'max_drawdown_threshold': 0.05, 'reward_negative': -0.5}
        }
    
    elif objective == 'maximize_sharpe':
        return {
            'recommended_reward': {
                'type': 'risk_adjusted',
                'description': 'Risk-Adjusted Reward pour optimiser le Sharpe Ratio'
            },
            'alternative_rewards': ['sharpe', 'sortino'],
            'parameters': {'risk_free_rate': 0.02, 'use_sharpe_ratio': True}
        }
    
    elif objective == 'consistency':
        return {
            'recommended_reward': {
                'type': 'consistency',
                'description': 'Consistency Reward pour des performances stables'
            },
            'alternative_rewards': ['win_rate'],
            'parameters': {'window_size': 20, 'consistency_threshold': 0.5}
        }
    
    # Par défaut
    return {
        'recommended_reward': {
            'type': 'continuous',
            'description': 'Récompense continue par défaut'
        },
        'alternative_rewards': ['pnl', 'sharpe'],
        'parameters': {'scale': 1.0}
    }


logger.info("Module de fonctions de récompense initialisé")
