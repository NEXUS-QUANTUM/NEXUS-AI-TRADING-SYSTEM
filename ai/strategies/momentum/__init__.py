# ai/strategies/momentum/__init__.py
"""
NEXUS AI TRADING SYSTEM - Momentum Strategies Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de stratégies de momentum pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.strategies.momentum.macd_strategy import (
    MACDStrategy,
    MACDConfig,
    MACDSignal,
    Divergence,
    create_macd_strategy,
)

from ai.strategies.momentum.moving_average_crossover import (
    MovingAverageCrossoverStrategy,
    MovingAverageCrossoverConfig,
    CrossSignal,
    create_moving_average_crossover,
)

from ai.strategies.momentum.trend_following import (
    TrendFollowingStrategy,
    TrendFollowingConfig,
    TrendSignal,
    create_trend_following_strategy,
)

logger = logging.getLogger(__name__)


__all__ = [
    # MACD Strategy
    'MACDStrategy',
    'MACDConfig',
    'MACDSignal',
    'Divergence',
    'create_macd_strategy',
    
    # Moving Average Crossover
    'MovingAverageCrossoverStrategy',
    'MovingAverageCrossoverConfig',
    'CrossSignal',
    'create_moving_average_crossover',
    
    # Trend Following
    'TrendFollowingStrategy',
    'TrendFollowingConfig',
    'TrendSignal',
    'create_trend_following_strategy',
]


def create_momentum_strategy(
    strategy_type: str = 'macd',
    **kwargs
) -> Any:
    """
    Factory pour créer des stratégies de momentum.
    
    Args:
        strategy_type: Type de stratégie ('macd', 'ma_crossover', 'trend_following')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance de la stratégie
    
    Examples:
        ```python
        # MACD Strategy
        strategy = create_momentum_strategy(
            'macd',
            symbol='BTC-USD',
            fast_period=12,
            slow_period=26,
            signal_period=9
        )
        
        # Moving Average Crossover
        strategy = create_momentum_strategy(
            'ma_crossover',
            symbol='BTC-USD',
            fast_period=50,
            slow_period=200
        )
        
        # Trend Following
        strategy = create_momentum_strategy(
            'trend_following',
            symbol='BTC-USD',
            adx_period=14,
            adx_threshold=25.0
        )
        ```
    """
    strategy_type = strategy_type.lower()
    
    if strategy_type == 'macd':
        symbol = kwargs.get('symbol', 'BTC-USD')
        fast_period = kwargs.get('fast_period', 12)
        slow_period = kwargs.get('slow_period', 26)
        signal_period = kwargs.get('signal_period', 9)
        
        return create_macd_strategy(
            symbol=symbol,
            fast_period=fast_period,
            slow_period=slow_period,
            signal_period=signal_period,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'fast_period', 'slow_period', 'signal_period']}
        )
    
    elif strategy_type == 'ma_crossover':
        symbol = kwargs.get('symbol', 'BTC-USD')
        fast_period = kwargs.get('fast_period', 50)
        slow_period = kwargs.get('slow_period', 200)
        
        return create_moving_average_crossover(
            symbol=symbol,
            fast_period=fast_period,
            slow_period=slow_period,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'fast_period', 'slow_period']}
        )
    
    elif strategy_type == 'trend_following':
        symbol = kwargs.get('symbol', 'BTC-USD')
        adx_period = kwargs.get('adx_period', 14)
        adx_threshold = kwargs.get('adx_threshold', 25.0)
        
        return create_trend_following_strategy(
            symbol=symbol,
            adx_period=adx_period,
            adx_threshold=adx_threshold,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'adx_period', 'adx_threshold']}
        )
    
    else:
        raise ValueError(f"Type de stratégie de momentum non supporté: {strategy_type}")


def get_available_momentum_strategies() -> List[str]:
    """
    Retourne la liste des stratégies de momentum disponibles.
    
    Returns:
        List[str]: Liste des types de stratégies
    """
    return ['macd', 'ma_crossover', 'trend_following']


def get_momentum_strategy_info(strategy_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de stratégie de momentum.
    
    Args:
        strategy_type: Type de stratégie
    
    Returns:
        Dict[str, Any]: Informations sur la stratégie
    """
    info = {
        'macd': {
            'name': 'MACD Strategy',
            'description': 'Stratégie basée sur la divergence de la moyenne mobile',
            'advantages': [
                'Signaux clairs',
                'Bien adapté aux tendances',
                'Multiple confirmations'
            ],
            'disadvantages': [
                'Faux signaux en range',
                'Lagging indicator',
                'Paramètres à optimiser'
            ],
            'use_cases': [
                'Marchés tendanciels',
                'Entrée/sortie',
                'Confirmation de tendance'
            ]
        },
        'ma_crossover': {
            'name': 'Moving Average Crossover',
            'description': 'Stratégie basée sur le croisement de moyennes mobiles',
            'advantages': [
                'Simple à implémenter',
                'Robuste',
                'Bien compris'
            ],
            'disadvantages': [
                'Lagging',
                'Faux signaux',
                'Performance variable'
            ],
            'use_cases': [
                'Suivi de tendance',
                'Entrée/sortie',
                'Filtrage de bruit'
            ]
        },
        'trend_following': {
            'name': 'Trend Following',
            'description': 'Stratégie de suivi de tendance avec ADX',
            'advantages': [
                'Mesure de force de tendance',
                'Filtrage des ranges',
                'Gestion de risque intégrée'
            ],
            'disadvantages': [
                'Complexe',
                'Nécessite des paramètres',
                'Retard dans les signaux'
            ],
            'use_cases': [
                'Tendances fortes',
                'Suivi de tendance',
                'Risk management'
            ]
        }
    }
    
    return info.get(strategy_type.lower(), {})


def get_momentum_recommendation(
    market_type: str = 'crypto',
    time_frame: str = 'medium',
    risk_tolerance: str = 'medium',
    experience: str = 'medium'
) -> Dict[str, Any]:
    """
    Recommande une stratégie de momentum selon les besoins.
    
    Args:
        market_type: Type de marché ('crypto', 'forex', 'stocks')
        time_frame: Horizon temporel ('short', 'medium', 'long')
        risk_tolerance: Tolérance au risque ('low', 'medium', 'high')
        experience: Niveau d'expérience ('low', 'medium', 'high')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    if experience == 'low':
        return {
            'recommended_strategy': {
                'type': 'ma_crossover',
                'description': 'Moving Average Crossover pour débutants'
            },
            'alternative_strategies': ['macd'],
            'features': ['Simple', 'Robuste', 'Facile à comprendre']
        }
    
    if market_type == 'crypto':
        return {
            'recommended_strategy': {
                'type': 'trend_following',
                'description': 'Trend Following pour crypto'
            },
            'alternative_strategies': ['macd'],
            'features': ['ADX filter', 'Gestion de risque', 'Trailing stop']
        }
    
    if time_frame == 'short':
        return {
            'recommended_strategy': {
                'type': 'macd',
                'description': 'MACD pour court terme'
            },
            'alternative_strategies': ['ma_crossover'],
            'features': ['Réactif', 'Signaux fréquents']
        }
    
    # Par défaut
    return {
        'recommended_strategy': {
            'type': 'ma_crossover',
            'description': 'Moving Average Crossover pour approche générale'
        },
        'alternative_strategies': ['macd', 'trend_following'],
        'features': ['Simple', 'Robuste', 'Standard']
    }


logger.info("Module de stratégies de momentum initialisé")
