# ai/strategies/swing/__init__.py
"""
NEXUS AI TRADING SYSTEM - Swing Strategies Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de stratégies Swing pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.strategies.swing.fibonacci_strategy import (
    FibonacciStrategy,
    FibonacciConfig,
    FibonacciLevel,
    FibonacciSignal,
    create_fibonacci_strategy,
)

from ai.strategies.swing.harmonic_patterns import (
    HarmonicPatternsStrategy,
    HarmonicPatternConfig,
    HarmonicPoint,
    HarmonicPattern,
    HarmonicSignal,
    create_harmonic_patterns_strategy,
)

from ai.strategies.swing.support_resistance import (
    SupportResistanceStrategy,
    SupportResistanceConfig,
    SupportResistanceLevel,
    SupportResistanceSignal,
    create_support_resistance_strategy,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Fibonacci Strategy
    'FibonacciStrategy',
    'FibonacciConfig',
    'FibonacciLevel',
    'FibonacciSignal',
    'create_fibonacci_strategy',
    
    # Harmonic Patterns
    'HarmonicPatternsStrategy',
    'HarmonicPatternConfig',
    'HarmonicPoint',
    'HarmonicPattern',
    'HarmonicSignal',
    'create_harmonic_patterns_strategy',
    
    # Support & Resistance
    'SupportResistanceStrategy',
    'SupportResistanceConfig',
    'SupportResistanceLevel',
    'SupportResistanceSignal',
    'create_support_resistance_strategy',
]


def create_swing_strategy(
    strategy_type: str = 'fibonacci',
    **kwargs
) -> Any:
    """
    Factory pour créer des stratégies Swing.
    
    Args:
        strategy_type: Type de stratégie ('fibonacci', 'harmonic', 'support_resistance')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance de la stratégie
    
    Examples:
        ```python
        # Fibonacci Strategy
        strategy = create_swing_strategy(
            'fibonacci',
            symbol='BTC-USD',
            lookback_period=50,
            fib_levels=[0.382, 0.5, 0.618]
        )
        
        # Harmonic Patterns
        strategy = create_swing_strategy(
            'harmonic',
            symbol='BTC-USD',
            lookback_period=100,
            min_pattern_quality=0.7
        )
        
        # Support & Resistance
        strategy = create_swing_strategy(
            'support_resistance',
            symbol='BTC-USD',
            lookback_period=50,
            consolidation_threshold=0.02
        )
        ```
    """
    strategy_type = strategy_type.lower()
    
    if strategy_type == 'fibonacci':
        symbol = kwargs.get('symbol', 'BTC-USD')
        lookback_period = kwargs.get('lookback_period', 50)
        
        return create_fibonacci_strategy(
            symbol=symbol,
            lookback_period=lookback_period,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'lookback_period']}
        )
    
    elif strategy_type == 'harmonic':
        symbol = kwargs.get('symbol', 'BTC-USD')
        lookback_period = kwargs.get('lookback_period', 100)
        min_pattern_quality = kwargs.get('min_pattern_quality', 0.7)
        
        return create_harmonic_patterns_strategy(
            symbol=symbol,
            lookback_period=lookback_period,
            min_pattern_quality=min_pattern_quality,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'lookback_period', 'min_pattern_quality']}
        )
    
    elif strategy_type == 'support_resistance':
        symbol = kwargs.get('symbol', 'BTC-USD')
        lookback_period = kwargs.get('lookback_period', 50)
        consolidation_threshold = kwargs.get('consolidation_threshold', 0.02)
        
        return create_support_resistance_strategy(
            symbol=symbol,
            lookback_period=lookback_period,
            consolidation_threshold=consolidation_threshold,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'lookback_period', 'consolidation_threshold']}
        )
    
    else:
        raise ValueError(f"Type de stratégie Swing non supporté: {strategy_type}")


def get_available_swing_strategies() -> List[str]:
    """
    Retourne la liste des stratégies Swing disponibles.
    
    Returns:
        List[str]: Liste des types de stratégies
    """
    return ['fibonacci', 'harmonic', 'support_resistance']


def get_swing_strategy_info(strategy_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de stratégie Swing.
    
    Args:
        strategy_type: Type de stratégie
    
    Returns:
        Dict[str, Any]: Informations sur la stratégie
    """
    info = {
        'fibonacci': {
            'name': 'Fibonacci Strategy',
            'description': 'Stratégie basée sur les niveaux de Fibonacci',
            'advantages': [
                'Niveaux bien définis',
                'Points d\'entrée clairs',
                'Gestion de risque intégrée'
            ],
            'disadvantages': [
                'Nécessite une tendance claire',
                'Faux signaux possibles',
                'Peut être subjectif'
            ],
            'use_cases': [
                'Marchés tendanciels',
                'Retracements',
                'Extensions de prix'
            ]
        },
        'harmonic': {
            'name': 'Harmonic Patterns',
            'description': 'Stratégie basée sur les motifs harmoniques',
            'advantages': [
                'Rapports de Fibonacci précis',
                'Points d\'inversion clairs',
                'Structure définie'
            ],
            'disadvantages': [
                'Complexe à identifier',
                'Rare',
                'Nécessite de l\'expérience'
            ],
            'use_cases': [
                'Reversals',
                'Points d\'inversion',
                'Trading de continuation'
            ]
        },
        'support_resistance': {
            'name': 'Support & Resistance',
            'description': 'Stratégie basée sur les niveaux de support/résistance',
            'advantages': [
                'Niveaux clairs',
                'Multiples points de contact',
                'Volume confirmation'
            ],
            'disadvantages': [
                'Faux breakouts',
                'Niveaux subjectifs',
                'Nécessite de l\'expérience'
            ],
            'use_cases': [
                'Breakouts',
                'Bounces',
                'Consolidations'
            ]
        }
    }
    
    return info.get(strategy_type.lower(), {})


def get_swing_recommendation(
    market_type: str = 'crypto',
    time_frame: str = 'medium',
    risk_tolerance: str = 'medium',
    experience: str = 'medium'
) -> Dict[str, Any]:
    """
    Recommande une stratégie Swing selon les besoins.
    
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
                'type': 'support_resistance',
                'description': 'Support & Resistance pour débutants'
            },
            'alternative_strategies': ['fibonacci'],
            'features': ['Niveaux clairs', 'Volume confirmation', 'Simple']
        }
    
    if market_type == 'crypto':
        return {
            'recommended_strategy': {
                'type': 'support_resistance',
                'description': 'Support & Resistance pour crypto'
            },
            'alternative_strategies': ['fibonacci'],
            'features': ['Niveaux clairs', 'Volume', 'Breakouts']
        }
    
    if time_frame == 'long':
        return {
            'recommended_strategy': {
                'type': 'fibonacci',
                'description': 'Fibonacci pour long terme'
            },
            'alternative_strategies': ['harmonic'],
            'features': ['Retracements', 'Extensions', 'Tendance']
        }
    
    # Par défaut
    return {
        'recommended_strategy': {
            'type': 'support_resistance',
            'description': 'Support & Resistance pour approche générale'
        },
        'alternative_strategies': ['fibonacci', 'harmonic'],
        'features': ['Niveaux', 'Volume', 'Structure']
    }


logger.info("Module de stratégies Swing initialisé")
