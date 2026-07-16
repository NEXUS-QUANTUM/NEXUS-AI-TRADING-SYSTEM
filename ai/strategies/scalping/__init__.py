# ai/strategies/scalping/__init__.py
"""
NEXUS AI TRADING SYSTEM - Scalping Strategies Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de stratégies de scalping pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.strategies.scalping.order_book_scalping import (
    OrderBookScalpingStrategy,
    OrderBookScalpingConfig,
    OrderBookData,
    OrderBookLevel,
    ScalpingSignal,
    create_order_book_scalping,
)

from ai.strategies.scalping.spread_scalping import (
    SpreadScalpingStrategy,
    SpreadScalpingConfig,
    SpreadData,
    SpreadSignal,
    create_spread_scalping,
)

from ai.strategies.scalping.tick_scalping import (
    TickScalpingStrategy,
    TickScalpingConfig,
    TickData,
    TickSignal,
    create_tick_scalping,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Order Book Scalping
    'OrderBookScalpingStrategy',
    'OrderBookScalpingConfig',
    'OrderBookData',
    'OrderBookLevel',
    'ScalpingSignal',
    'create_order_book_scalping',
    
    # Spread Scalping
    'SpreadScalpingStrategy',
    'SpreadScalpingConfig',
    'SpreadData',
    'SpreadSignal',
    'create_spread_scalping',
    
    # Tick Scalping
    'TickScalpingStrategy',
    'TickScalpingConfig',
    'TickData',
    'TickSignal',
    'create_tick_scalping',
]


def create_scalping_strategy(
    strategy_type: str = 'order_book',
    **kwargs
) -> Any:
    """
    Factory pour créer des stratégies de scalping.
    
    Args:
        strategy_type: Type de stratégie ('order_book', 'spread', 'tick')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance de la stratégie
    
    Examples:
        ```python
        # Order Book Scalping
        strategy = create_scalping_strategy(
            'order_book',
            symbol='BTC-USD',
            depth=10,
            imbalance_threshold=0.3
        )
        
        # Spread Scalping
        strategy = create_scalping_strategy(
            'spread',
            symbol='BTC-USD',
            min_spread=0.001,
            max_spread=0.01,
            entry_zscore=2.0
        )
        
        # Tick Scalping
        strategy = create_scalping_strategy(
            'tick',
            symbol='BTC-USD',
            tick_window=100,
            volume_threshold=100.0
        )
        ```
    """
    strategy_type = strategy_type.lower()
    
    if strategy_type == 'order_book':
        symbol = kwargs.get('symbol', 'BTC-USD')
        depth = kwargs.get('depth', 10)
        imbalance_threshold = kwargs.get('imbalance_threshold', 0.3)
        
        return create_order_book_scalping(
            symbol=symbol,
            depth=depth,
            imbalance_threshold=imbalance_threshold,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'depth', 'imbalance_threshold']}
        )
    
    elif strategy_type == 'spread':
        symbol = kwargs.get('symbol', 'BTC-USD')
        min_spread = kwargs.get('min_spread', 0.001)
        max_spread = kwargs.get('max_spread', 0.01)
        entry_zscore = kwargs.get('entry_zscore', 2.0)
        
        return create_spread_scalping(
            symbol=symbol,
            min_spread=min_spread,
            max_spread=max_spread,
            entry_zscore=entry_zscore,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'min_spread', 'max_spread', 'entry_zscore']}
        )
    
    elif strategy_type == 'tick':
        symbol = kwargs.get('symbol', 'BTC-USD')
        tick_window = kwargs.get('tick_window', 100)
        volume_threshold = kwargs.get('volume_threshold', 100.0)
        
        return create_tick_scalping(
            symbol=symbol,
            tick_window=tick_window,
            volume_threshold=volume_threshold,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'tick_window', 'volume_threshold']}
        )
    
    else:
        raise ValueError(f"Type de stratégie de scalping non supporté: {strategy_type}")


def get_available_scalping_strategies() -> List[str]:
    """
    Retourne la liste des stratégies de scalping disponibles.
    
    Returns:
        List[str]: Liste des types de stratégies
    """
    return ['order_book', 'spread', 'tick']


def get_scalping_strategy_info(strategy_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de stratégie de scalping.
    
    Args:
        strategy_type: Type de stratégie
    
    Returns:
        Dict[str, Any]: Informations sur la stratégie
    """
    info = {
        'order_book': {
            'name': 'Order Book Scalping',
            'description': 'Scalping basé sur l\'analyse du carnet d\'ordres',
            'advantages': [
                'Réactif',
                'Basé sur la liquidité réelle',
                'Signaux précoces'
            ],
            'disadvantages': [
                'Nécessite des données L2',
                'Volume de données important',
                'Complexe à implémenter'
            ],
            'use_cases': [
                'Marchés liquides',
                'Trading haute fréquence',
                'Analyse de microstructure'
            ]
        },
        'spread': {
            'name': 'Spread Scalping',
            'description': 'Scalping basé sur l\'évolution du spread',
            'advantages': [
                'Simple à comprendre',
                'Bonne gestion du risque',
                'Rentable en range'
            ],
            'disadvantages': [
                'Nécessite un spread stable',
                'Opportunités limitées',
                'Sensible au bruit'
            ],
            'use_cases': [
                'Marchés avec spread variable',
                'Market making',
                'Arbitrage de spread'
            ]
        },
        'tick': {
            'name': 'Tick Scalping',
            'description': 'Scalping sur données tick par tick',
            'advantages': [
                'Très réactif',
                'Capture des micro-mouvements',
                'Haute fréquence'
            ],
            'disadvantages': [
                'Nécessite beaucoup de données',
                'Sensible au bruit de tick',
                'Frais de transaction élevés'
            ],
            'use_cases': [
                'Trading haute fréquence',
                'Marchés très liquides',
                'Micro-trading'
            ]
        }
    }
    
    return info.get(strategy_type.lower(), {})


def get_scalping_recommendation(
    market_type: str = 'crypto',
    latency: str = 'medium',
    capital: str = 'medium',
    technical_skill: str = 'medium'
) -> Dict[str, Any]:
    """
    Recommande une stratégie de scalping selon les besoins.
    
    Args:
        market_type: Type de marché ('crypto', 'forex', 'stocks')
        latency: Latence ('low', 'medium', 'high')
        capital: Capital disponible ('low', 'medium', 'high')
        technical_skill: Compétence technique ('low', 'medium', 'high')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    if technical_skill == 'low':
        return {
            'recommended_strategy': {
                'type': 'spread',
                'description': 'Spread Scalping pour débutants'
            },
            'alternative_strategies': ['order_book'],
            'features': ['Simple', 'Gestion de risque', 'Interprétable']
        }
    
    if latency == 'low':
        return {
            'recommended_strategy': {
                'type': 'tick',
                'description': 'Tick Scalping pour faible latence'
            },
            'alternative_strategies': ['order_book'],
            'features': ['Très réactif', 'Micro-trading', 'Haute fréquence']
        }
    
    if market_type == 'crypto':
        return {
            'recommended_strategy': {
                'type': 'order_book',
                'description': 'Order Book Scalping pour crypto'
            },
            'alternative_strategies': ['tick'],
            'features': ['Liquidité', 'Profondeur', 'Réactif']
        }
    
    # Par défaut
    return {
        'recommended_strategy': {
            'type': 'order_book',
            'description': 'Order Book Scalping pour approche générale'
        },
        'alternative_strategies': ['spread', 'tick'],
        'features': ['Basé sur la liquidité', 'Précis', 'Efficace']
    }


logger.info("Module de stratégies de scalping initialisé")
