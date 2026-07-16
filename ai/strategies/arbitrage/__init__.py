# ai/strategies/arbitrage/__init__.py
"""
NEXUS AI TRADING SYSTEM - Arbitrage Strategies Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de stratégies d'arbitrage pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.strategies.arbitrage.cross_exchange_arbitrage import (
    CrossExchangeArbitrage,
    CrossExchangeArbitrageConfig,
    ExchangePrice,
    ArbitrageOpportunity,
    create_cross_exchange_arbitrage,
)

from ai.strategies.arbitrage.statistical_arbitrage import (
    StatisticalArbitrage,
    StatisticalArbitrageConfig,
    CointegrationResult,
    create_statistical_arbitrage,
)

from ai.strategies.arbitrage.triangular_arbitrage import (
    TriangularArbitrage,
    TriangularArbitrageConfig,
    CurrencyPair,
    TriangularArbitrageOpportunity,
    create_triangular_arbitrage,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Cross-Exchange Arbitrage
    'CrossExchangeArbitrage',
    'CrossExchangeArbitrageConfig',
    'ExchangePrice',
    'ArbitrageOpportunity',
    'create_cross_exchange_arbitrage',
    
    # Statistical Arbitrage
    'StatisticalArbitrage',
    'StatisticalArbitrageConfig',
    'CointegrationResult',
    'create_statistical_arbitrage',
    
    # Triangular Arbitrage
    'TriangularArbitrage',
    'TriangularArbitrageConfig',
    'CurrencyPair',
    'TriangularArbitrageOpportunity',
    'create_triangular_arbitrage',
]


def create_arbitrage_strategy(
    strategy_type: str = 'cross_exchange',
    **kwargs
) -> Any:
    """
    Factory pour créer des stratégies d'arbitrage.
    
    Args:
        strategy_type: Type de stratégie ('cross_exchange', 'statistical', 'triangular')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance de la stratégie
    
    Examples:
        ```python
        # Cross-Exchange Arbitrage
        strategy = create_arbitrage_strategy(
            'cross_exchange',
            exchanges=['binance', 'coinbase'],
            symbols=['BTC-USD'],
            min_spread_percent=0.1
        )
        
        # Statistical Arbitrage
        strategy = create_arbitrage_strategy(
            'statistical',
            symbols=['BTC-USD', 'ETH-USD', 'SOL-USD'],
            lookback_window=100,
            entry_zscore=2.0
        )
        
        # Triangular Arbitrage
        strategy = create_arbitrage_strategy(
            'triangular',
            currencies=['USD', 'BTC', 'ETH', 'SOL'],
            min_profit_percent=0.1
        )
        ```
    """
    strategy_type = strategy_type.lower()
    
    if strategy_type == 'cross_exchange':
        exchanges = kwargs.get('exchanges', ['binance', 'coinbase', 'kraken', 'bybit'])
        symbols = kwargs.get('symbols', ['BTC-USD', 'ETH-USD', 'SOL-USD'])
        min_spread_percent = kwargs.get('min_spread_percent', 0.1)
        
        return create_cross_exchange_arbitrage(
            exchanges=exchanges,
            symbols=symbols,
            min_spread_percent=min_spread_percent,
            **{k: v for k, v in kwargs.items() 
               if k not in ['exchanges', 'symbols', 'min_spread_percent']}
        )
    
    elif strategy_type == 'statistical':
        symbols = kwargs.get('symbols', ['BTC-USD', 'ETH-USD', 'SOL-USD'])
        lookback_window = kwargs.get('lookback_window', 100)
        entry_zscore = kwargs.get('entry_zscore', 2.0)
        
        return create_statistical_arbitrage(
            symbols=symbols,
            lookback_window=lookback_window,
            entry_zscore=entry_zscore,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbols', 'lookback_window', 'entry_zscore']}
        )
    
    elif strategy_type == 'triangular':
        currencies = kwargs.get('currencies', ['USD', 'BTC', 'ETH', 'SOL'])
        min_profit_percent = kwargs.get('min_profit_percent', 0.1)
        
        return create_triangular_arbitrage(
            currencies=currencies,
            min_profit_percent=min_profit_percent,
            **{k: v for k, v in kwargs.items() 
               if k not in ['currencies', 'min_profit_percent']}
        )
    
    else:
        raise ValueError(f"Type de stratégie d'arbitrage non supporté: {strategy_type}")


def get_available_arbitrage_strategies() -> List[str]:
    """
    Retourne la liste des stratégies d'arbitrage disponibles.
    
    Returns:
        List[str]: Liste des types de stratégies
    """
    return ['cross_exchange', 'statistical', 'triangular']


def get_arbitrage_strategy_info(strategy_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de stratégie d'arbitrage.
    
    Args:
        strategy_type: Type de stratégie
    
    Returns:
        Dict[str, Any]: Informations sur la stratégie
    """
    info = {
        'cross_exchange': {
            'name': 'Cross-Exchange Arbitrage',
            'description': 'Arbitrage entre différentes plateformes d\'échange',
            'advantages': [
                'Profit relativement stable',
                'Risque de marché limité',
                'Opportunités fréquentes'
            ],
            'disadvantages': [
                'Nécessite des comptes sur plusieurs exchanges',
                'Frais de transaction',
                'Temps d\'exécution critique'
            ],
            'use_cases': [
                'Marchés crypto',
                'Marchés fragmentés',
                'Trading haute fréquence'
            ]
        },
        'statistical': {
            'name': 'Statistical Arbitrage',
            'description': 'Arbitrage basé sur la cointégration statistique',
            'advantages': [
                'Basé sur des relations fondamentales',
                'Gestion du risque intégrée',
                'Peut être automatisé'
            ],
            'disadvantages': [
                'Nécessite des données historiques',
                'Périodes de non-cointégration',
                'Complexe à implémenter'
            ],
            'use_cases': [
                'Marchés financiers',
                'Pairs trading',
                'Neutralité de marché'
            ]
        },
        'triangular': {
            'name': 'Triangular Arbitrage',
            'description': 'Arbitrage entre trois devises ou plus',
            'advantages': [
                'Opportunités intra-exchange',
                'Risque de contrepartie limité',
                'Exécution rapide'
            ],
            'disadvantages': [
                'Profits faibles par trade',
                'Nécessite des spreads serrés',
                'Opportunités rares'
            ],
            'use_cases': [
                'Marchés Forex',
                'Marchés crypto',
                'Arbitrage de devises'
            ]
        }
    }
    
    return info.get(strategy_type.lower(), {})


def get_arbitrage_recommendation(
    market_type: str = 'crypto',
    capital: str = 'medium',
    risk_tolerance: str = 'medium',
    technical_skill: str = 'medium'
) -> Dict[str, Any]:
    """
    Recommande une stratégie d'arbitrage selon les besoins.
    
    Args:
        market_type: Type de marché ('crypto', 'forex', 'stocks')
        capital: Capital disponible ('low', 'medium', 'high')
        risk_tolerance: Tolérance au risque ('low', 'medium', 'high')
        technical_skill: Compétence technique ('low', 'medium', 'high')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    if market_type == 'crypto':
        if capital == 'low':
            return {
                'recommended_strategy': {
                    'type': 'triangular',
                    'description': 'Arbitrage triangulaire pour capital limité'
                },
                'alternative_strategies': ['cross_exchange'],
                'features': ['Opportunités intra-exchange', 'Execution rapide']
            }
        elif capital == 'high':
            return {
                'recommended_strategy': {
                    'type': 'statistical',
                    'description': 'Arbitrage statistique pour capital élevé'
                },
                'alternative_strategies': ['cross_exchange'],
                'features': ['Relations fondamentales', 'Risk management']
            }
        else:
            return {
                'recommended_strategy': {
                    'type': 'cross_exchange',
                    'description': 'Arbitrage cross-exchange pour capital moyen'
                },
                'alternative_strategies': ['triangular', 'statistical'],
                'features': ['Multi-exchange', 'Fréquent']
            }
    
    elif market_type == 'forex':
        return {
            'recommended_strategy': {
                'type': 'triangular',
                'description': 'Arbitrage triangulaire pour Forex'
            },
            'alternative_strategies': ['statistical'],
            'features': ['Devises', 'Spread serrés', '24/7']
        }
    
    elif market_type == 'stocks':
        return {
            'recommended_strategy': {
                'type': 'statistical',
                'description': 'Arbitrage statistique pour actions'
            },
            'alternative_strategies': [],
            'features': ['Pairs trading', 'Neutralité', 'Long terme']
        }
    
    # Par défaut
    return {
        'recommended_strategy': {
            'type': 'cross_exchange',
            'description': 'Arbitrage cross-exchange par défaut'
        },
        'alternative_strategies': ['statistical', 'triangular'],
        'features': ['Flexible', 'Multi-exchange', 'Adaptable']
    }


logger.info("Module de stratégies d'arbitrage initialisé")
