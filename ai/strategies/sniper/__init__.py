
# ai/strategies/sniper/__init__.py
"""
NEXUS AI TRADING SYSTEM - Sniper Strategies Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de stratégies Sniper pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.strategies.sniper.breakout_strategy import (
    BreakoutStrategy,
    BreakoutConfig,
    BreakoutSignal,
    create_breakout_strategy,
)

from ai.strategies.sniper.liquidity_grab import (
    LiquidityGrabStrategy,
    LiquidityGrabConfig,
    LiquidityLevel,
    LiquidityGrabSignal,
    create_liquidity_grab_strategy,
)

from ai.strategies.sniper.stop_hunting import (
    StopHuntingStrategy,
    StopHuntingConfig,
    StopLevel,
    StopHuntingSignal,
    create_stop_hunting_strategy,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Breakout Strategy
    'BreakoutStrategy',
    'BreakoutConfig',
    'BreakoutSignal',
    'create_breakout_strategy',
    
    # Liquidity Grab
    'LiquidityGrabStrategy',
    'LiquidityGrabConfig',
    'LiquidityLevel',
    'LiquidityGrabSignal',
    'create_liquidity_grab_strategy',
    
    # Stop Hunting
    'StopHuntingStrategy',
    'StopHuntingConfig',
    'StopLevel',
    'StopHuntingSignal',
    'create_stop_hunting_strategy',
]


def create_sniper_strategy(
    strategy_type: str = 'breakout',
    **kwargs
) -> Any:
    """
    Factory pour créer des stratégies Sniper.
    
    Args:
        strategy_type: Type de stratégie ('breakout', 'liquidity_grab', 'stop_hunting')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance de la stratégie
    
    Examples:
        ```python
        # Breakout Strategy
        strategy = create_sniper_strategy(
            'breakout',
            symbol='BTC-USD',
            lookback_period=20,
            breakout_threshold=0.02
        )
        
        # Liquidity Grab
        strategy = create_sniper_strategy(
            'liquidity_grab',
            symbol='BTC-USD',
            lookback_period=20,
            liquidity_levels=3
        )
        
        # Stop Hunting
        strategy = create_sniper_strategy(
            'stop_hunting',
            symbol='BTC-USD',
            lookback_period=20,
            stop_level_threshold=0.01
        )
        ```
    """
    strategy_type = strategy_type.lower()
    
    if strategy_type == 'breakout':
        symbol = kwargs.get('symbol', 'BTC-USD')
        lookback_period = kwargs.get('lookback_period', 20)
        breakout_threshold = kwargs.get('breakout_threshold', 0.02)
        
        return create_breakout_strategy(
            symbol=symbol,
            lookback_period=lookback_period,
            breakout_threshold=breakout_threshold,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'lookback_period', 'breakout_threshold']}
        )
    
    elif strategy_type == 'liquidity_grab':
        symbol = kwargs.get('symbol', 'BTC-USD')
        lookback_period = kwargs.get('lookback_period', 20)
        liquidity_levels = kwargs.get('liquidity_levels', 3)
        
        return create_liquidity_grab_strategy(
            symbol=symbol,
            lookback_period=lookback_period,
            liquidity_levels=liquidity_levels,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'lookback_period', 'liquidity_levels']}
        )
    
    elif strategy_type == 'stop_hunting':
        symbol = kwargs.get('symbol', 'BTC-USD')
        lookback_period = kwargs.get('lookback_period', 20)
        stop_level_threshold = kwargs.get('stop_level_threshold', 0.01)
        
        return create_stop_hunting_strategy(
            symbol=symbol,
            lookback_period=lookback_period,
            stop_level_threshold=stop_level_threshold,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'lookback_period', 'stop_level_threshold']}
        )
    
    else:
        raise ValueError(f"Type de stratégie Sniper non supporté: {strategy_type}")


def get_available_sniper_strategies() -> List[str]:
    """
    Retourne la liste des stratégies Sniper disponibles.
    
    Returns:
        List[str]: Liste des types de stratégies
    """
    return ['breakout', 'liquidity_grab', 'stop_hunting']


def get_sniper_strategy_info(strategy_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de stratégie Sniper.
    
    Args:
        strategy_type: Type de stratégie
    
    Returns:
        Dict[str, Any]: Informations sur la stratégie
    """
    info = {
        'breakout': {
            'name': 'Breakout Strategy',
            'description': 'Stratégie de breakout avec confirmation de volume',
            'advantages': [
                'Signaux clairs',
                'Volume confirmation',
                'Gestion de risque ATR'
            ],
            'disadvantages': [
                'Faux breakouts',
                'Nécessite des niveaux clairs',
                'Slipage possible'
            ],
            'use_cases': [
                'Marchés en range',
                'Breakouts significatifs',
                'Trading directionnel'
            ]
        },
        'liquidity_grab': {
            'name': 'Liquidity Grab',
            'description': 'Capture de liquidité sur les niveaux clés',
            'advantages': [
                'Capture des mouvements rapides',
                'Volume confirmation',
                'Niveaux de liquidité'
            ],
            'disadvantages': [
                'Faux signaux',
                'Nécessite des données L2',
                'Risque de contre-tendance'
            ],
            'use_cases': [
                'Marchés liquides',
                'Niveaux de support/résistance',
                'Trading de reversal'
            ]
        },
        'stop_hunting': {
            'name': 'Stop Hunting',
            'description': 'Chasse aux stops avec détection de niveaux',
            'advantages': [
                'Reversals rapides',
                'Volume confirmation',
                'Niveaux Fibonacci'
            ],
            'disadvantages': [
                'Faux signaux',
                'Risque élevé',
                'Nécessite de la précision'
            ],
            'use_cases': [
                'Marchés tendanciels',
                'Liquidations',
                'Trading de reversal'
            ]
        }
    }
    
    return info.get(strategy_type.lower(), {})


def get_sniper_recommendation(
    market_type: str = 'crypto',
    risk_tolerance: str = 'medium',
    time_available: str = 'medium',
    experience: str = 'medium'
) -> Dict[str, Any]:
    """
    Recommande une stratégie Sniper selon les besoins.
    
    Args:
        market_type: Type de marché ('crypto', 'forex', 'stocks')
        risk_tolerance: Tolérance au risque ('low', 'medium', 'high')
        time_available: Temps disponible ('low', 'medium', 'high')
        experience: Niveau d'expérience ('low', 'medium', 'high')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    if experience == 'low':
        return {
            'recommended_strategy': {
                'type': 'breakout',
                'description': 'Breakout Strategy pour débutants'
            },
            'alternative_strategies': ['liquidity_grab'],
            'features': ['Simple', 'Volume confirmation', 'Gestion de risque']
        }
    
    if risk_tolerance == 'high' and time_available == 'high':
        return {
            'recommended_strategy': {
                'type': 'stop_hunting',
                'description': 'Stop Hunting pour traders expérimentés'
            },
            'alternative_strategies': ['liquidity_grab'],
            'features': ['Chasse aux stops', 'Niveaux Fibonacci', 'Reversals']
        }
    
    if market_type == 'crypto':
        return {
            'recommended_strategy': {
                'type': 'liquidity_grab',
                'description': 'Liquidity Grab pour crypto'
            },
            'alternative_strategies': ['breakout'],
            'features': ['Liquidité', 'Volume', 'Réactif']
        }
    
    # Par défaut
    return {
        'recommended_strategy': {
            'type': 'breakout',
            'description': 'Breakout Strategy pour approche générale'
        },
        'alternative_strategies': ['liquidity_grab', 'stop_hunting'],
        'features': ['Niveaux clés', 'Volume', 'Gestion de risque']
    }


logger.info("Module de stratégies Sniper initialisé")
