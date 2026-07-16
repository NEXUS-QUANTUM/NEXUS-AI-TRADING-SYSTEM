# ai/strategies/mean_reversion/__init__.py
"""
NEXUS AI TRADING SYSTEM - Mean Reversion Strategies Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de stratégies de mean reversion pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.strategies.mean_reversion.bollinger_bands import (
    BollingerBandsStrategy,
    BollingerBandsConfig,
    BollingerSignal,
    create_bollinger_bands_strategy,
)

from ai.strategies.mean_reversion.kalman_filter import (
    KalmanFilterStrategy,
    KalmanFilterConfig,
    KalmanFilterState,
    KalmanSignal,
    create_kalman_filter_strategy,
)

from ai.strategies.mean_reversion.pairs_trading import (
    PairsTradingStrategy,
    PairsTradingConfig,
    Pair,
    PairsSignal,
    create_pairs_trading_strategy,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Bollinger Bands
    'BollingerBandsStrategy',
    'BollingerBandsConfig',
    'BollingerSignal',
    'create_bollinger_bands_strategy',
    
    # Kalman Filter
    'KalmanFilterStrategy',
    'KalmanFilterConfig',
    'KalmanFilterState',
    'KalmanSignal',
    'create_kalman_filter_strategy',
    
    # Pairs Trading
    'PairsTradingStrategy',
    'PairsTradingConfig',
    'Pair',
    'PairsSignal',
    'create_pairs_trading_strategy',
]


def create_mean_reversion_strategy(
    strategy_type: str = 'bollinger_bands',
    **kwargs
) -> Any:
    """
    Factory pour créer des stratégies de mean reversion.
    
    Args:
        strategy_type: Type de stratégie ('bollinger_bands', 'kalman_filter', 'pairs_trading')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance de la stratégie
    
    Examples:
        ```python
        # Bollinger Bands Strategy
        strategy = create_mean_reversion_strategy(
            'bollinger_bands',
            symbol='BTC-USD',
            window=20,
            num_std=2.0,
            entry_threshold=2.0
        )
        
        # Kalman Filter Strategy
        strategy = create_mean_reversion_strategy(
            'kalman_filter',
            symbol='BTC-USD',
            observation_noise=0.1,
            process_noise=0.01,
            entry_threshold=2.0
        )
        
        # Pairs Trading Strategy
        strategy = create_mean_reversion_strategy(
            'pairs_trading',
            symbols=['BTC-USD', 'ETH-USD'],
            lookback_window=100,
            entry_zscore=2.0
        )
        ```
    """
    strategy_type = strategy_type.lower()
    
    if strategy_type == 'bollinger_bands':
        symbol = kwargs.get('symbol', 'BTC-USD')
        window = kwargs.get('window', 20)
        num_std = kwargs.get('num_std', 2.0)
        entry_threshold = kwargs.get('entry_threshold', 2.0)
        
        return create_bollinger_bands_strategy(
            symbol=symbol,
            window=window,
            num_std=num_std,
            entry_threshold=entry_threshold,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'window', 'num_std', 'entry_threshold']}
        )
    
    elif strategy_type == 'kalman_filter':
        symbol = kwargs.get('symbol', 'BTC-USD')
        observation_noise = kwargs.get('observation_noise', 0.1)
        process_noise = kwargs.get('process_noise', 0.01)
        entry_threshold = kwargs.get('entry_threshold', 2.0)
        
        return create_kalman_filter_strategy(
            symbol=symbol,
            observation_noise=observation_noise,
            process_noise=process_noise,
            entry_threshold=entry_threshold,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'observation_noise', 'process_noise', 'entry_threshold']}
        )
    
    elif strategy_type == 'pairs_trading':
        symbols = kwargs.get('symbols', ['BTC-USD', 'ETH-USD', 'SOL-USD'])
        lookback_window = kwargs.get('lookback_window', 100)
        entry_zscore = kwargs.get('entry_zscore', 2.0)
        
        return create_pairs_trading_strategy(
            symbols=symbols,
            lookback_window=lookback_window,
            entry_zscore=entry_zscore,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbols', 'lookback_window', 'entry_zscore']}
        )
    
    else:
        raise ValueError(f"Type de stratégie de mean reversion non supporté: {strategy_type}")


def get_available_mean_reversion_strategies() -> List[str]:
    """
    Retourne la liste des stratégies de mean reversion disponibles.
    
    Returns:
        List[str]: Liste des types de stratégies
    """
    return ['bollinger_bands', 'kalman_filter', 'pairs_trading']


def get_mean_reversion_strategy_info(strategy_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de stratégie de mean reversion.
    
    Args:
        strategy_type: Type de stratégie
    
    Returns:
        Dict[str, Any]: Informations sur la stratégie
    """
    info = {
        'bollinger_bands': {
            'name': 'Bollinger Bands',
            'description': 'Stratégie de mean reversion basée sur les bandes de Bollinger',
            'advantages': [
                'Simple à implémenter',
                'Visuel et interprétable',
                'Signaux clairs'
            ],
            'disadvantages': [
                'Faux signaux en tendance',
                'Paramètres à optimiser',
                'Performance variable'
            ],
            'use_cases': [
                'Marchés latéraux',
                'Range trading',
                'Entrée/sortie de positions'
            ]
        },
        'kalman_filter': {
            'name': 'Kalman Filter',
            'description': 'Stratégie de mean reversion avec filtre de Kalman',
            'advantages': [
                'Adaptatif',
                'Bruit réduit',
                'Estimations en temps réel'
            ],
            'disadvantages': [
                'Complexe à implémenter',
                'Paramètres sensibles',
                'Nécessite des données continues'
            ],
            'use_cases': [
                'Suivi de tendance',
                'Estimation d\'état',
                'Filtrage de bruit'
            ]
        },
        'pairs_trading': {
            'name': 'Pairs Trading',
            'description': 'Stratégie de mean reversion sur paires d\'actifs corrélés',
            'advantages': [
                'Neutralité de marché',
                'Diversification',
                'Risque réduit'
            ],
            'disadvantages': [
                'Nécessite des paires cointégrées',
                'Complexe à identifier',
                'Capital requis'
            ],
            'use_cases': [
                'Arbitrage statistique',
                'Couverture',
                'Market neutral'
            ]
        }
    }
    
    return info.get(strategy_type.lower(), {})


def get_mean_reversion_recommendation(
    market_type: str = 'crypto',
    risk_tolerance: str = 'medium',
    capital: str = 'medium',
    technical_skill: str = 'medium'
) -> Dict[str, Any]:
    """
    Recommande une stratégie de mean reversion selon les besoins.
    
    Args:
        market_type: Type de marché ('crypto', 'forex', 'stocks')
        risk_tolerance: Tolérance au risque ('low', 'medium', 'high')
        capital: Capital disponible ('low', 'medium', 'high')
        technical_skill: Compétence technique ('low', 'medium', 'high')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    if technical_skill == 'low':
        return {
            'recommended_strategy': {
                'type': 'bollinger_bands',
                'description': 'Bollinger Bands pour débutants'
            },
            'alternative_strategies': ['kalman_filter'],
            'features': ['Simple', 'Visuel', 'Interprétable']
        }
    
    if market_type == 'crypto':
        return {
            'recommended_strategy': {
                'type': 'pairs_trading',
                'description': 'Pairs Trading pour crypto'
            },
            'alternative_strategies': ['bollinger_bands'],
            'features': ['Corrélation crypto', 'Neutralité', 'Diversification']
        }
    
    if risk_tolerance == 'low':
        return {
            'recommended_strategy': {
                'type': 'kalman_filter',
                'description': 'Kalman Filter pour risque contrôlé'
            },
            'alternative_strategies': ['pairs_trading'],
            'features': ['Adaptatif', 'Filtrage', 'Précis']
        }
    
    # Par défaut
    return {
        'recommended_strategy': {
            'type': 'bollinger_bands',
            'description': 'Bollinger Bands pour approche générale'
        },
        'alternative_strategies': ['kalman_filter', 'pairs_trading'],
        'features': ['Simple', 'Efficace', 'Standard']
    }


logger.info("Module de stratégies de mean reversion initialisé")
