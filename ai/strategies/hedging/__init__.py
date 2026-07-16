# ai/strategies/hedging/__init__.py
"""
NEXUS AI TRADING SYSTEM - Hedging Strategies Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de stratégies de couverture pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.strategies.hedging.cross_hedging import (
    CrossHedging,
    CrossHedgingConfig,
    HedgeInstrument,
    HedgePosition,
    create_cross_hedging,
)

from ai.strategies.hedging.delta_hedging import (
    DeltaHedging,
    DeltaHedgingConfig,
    Option,
    DeltaHedgePosition,
    create_delta_hedging,
)

from ai.strategies.hedging.gamma_hedging import (
    GammaHedging,
    GammaHedgingConfig,
    GammaHedgePosition,
    OptionGreeks,
    create_gamma_hedging,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Cross Hedging
    'CrossHedging',
    'CrossHedgingConfig',
    'HedgeInstrument',
    'HedgePosition',
    'create_cross_hedging',
    
    # Delta Hedging
    'DeltaHedging',
    'DeltaHedgingConfig',
    'Option',
    'DeltaHedgePosition',
    'create_delta_hedging',
    
    # Gamma Hedging
    'GammaHedging',
    'GammaHedgingConfig',
    'GammaHedgePosition',
    'OptionGreeks',
    'create_gamma_hedging',
]


def create_hedging_strategy(
    strategy_type: str = 'delta',
    **kwargs
) -> Any:
    """
    Factory pour créer des stratégies de couverture.
    
    Args:
        strategy_type: Type de stratégie ('delta', 'gamma', 'cross')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance de la stratégie
    
    Examples:
        ```python
        # Delta Hedging
        strategy = create_hedging_strategy(
            'delta',
            options=[{'strike': 50000, 'expiry': '2024-12-31', 'option_type': 'call'}],
            underlying_symbol='BTC-USD'
        )
        
        # Gamma Hedging
        strategy = create_hedging_strategy(
            'gamma',
            underlying_symbol='BTC-USD',
            gamma_tolerance=0.01
        )
        
        # Cross Hedging
        strategy = create_hedging_strategy(
            'cross',
            assets=['BTC-USD'],
            hedge_instruments=['ETH-USD', 'SOL-USD'],
            lookback_window=100
        )
        ```
    """
    strategy_type = strategy_type.lower()
    
    if strategy_type == 'delta':
        options = kwargs.get('options', [])
        underlying_symbol = kwargs.get('underlying_symbol', 'BTC-USD')
        risk_free_rate = kwargs.get('risk_free_rate', 0.02)
        
        return create_delta_hedging(
            options=options,
            underlying_symbol=underlying_symbol,
            risk_free_rate=risk_free_rate,
            **{k: v for k, v in kwargs.items() 
               if k not in ['options', 'underlying_symbol', 'risk_free_rate']}
        )
    
    elif strategy_type == 'gamma':
        underlying_symbol = kwargs.get('underlying_symbol', 'BTC-USD')
        gamma_tolerance = kwargs.get('gamma_tolerance', 0.01)
        
        return create_gamma_hedging(
            underlying_symbol=underlying_symbol,
            gamma_tolerance=gamma_tolerance,
            **{k: v for k, v in kwargs.items() 
               if k not in ['underlying_symbol', 'gamma_tolerance']}
        )
    
    elif strategy_type == 'cross':
        assets = kwargs.get('assets', ['BTC-USD'])
        hedge_instruments = kwargs.get('hedge_instruments', ['ETH-USD', 'SOL-USD'])
        lookback_window = kwargs.get('lookback_window', 100)
        min_correlation = kwargs.get('min_correlation', 0.5)
        
        return create_cross_hedging(
            assets=assets,
            hedge_instruments=hedge_instruments,
            lookback_window=lookback_window,
            min_correlation=min_correlation,
            **{k: v for k, v in kwargs.items() 
               if k not in ['assets', 'hedge_instruments', 'lookback_window', 'min_correlation']}
        )
    
    else:
        raise ValueError(f"Type de stratégie de couverture non supporté: {strategy_type}")


def get_available_hedging_strategies() -> List[str]:
    """
    Retourne la liste des stratégies de couverture disponibles.
    
    Returns:
        List[str]: Liste des types de stratégies
    """
    return ['delta', 'gamma', 'cross']


def get_hedging_strategy_info(strategy_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de stratégie de couverture.
    
    Args:
        strategy_type: Type de stratégie
    
    Returns:
        Dict[str, Any]: Informations sur la stratégie
    """
    info = {
        'delta': {
            'name': 'Delta Hedging',
            'description': 'Couverture du risque de direction avec options',
            'advantages': [
                'Réduction du risque de direction',
                'Protection contre les mouvements défavorables',
                'Flexibilité'
            ],
            'disadvantages': [
                'Coût de la couverture',
                'Rebalancing fréquent',
                'Risque de base'
            ],
            'use_cases': [
                'Options trading',
                'Portfolio protection',
                'Risk management'
            ]
        },
        'gamma': {
            'name': 'Gamma Hedging',
            'description': 'Couverture du risque de convexité',
            'advantages': [
                'Protection contre les grands mouvements',
                'Gestion du risque de convexité',
                'Réduction de la volatilité du portefeuille'
            ],
            'disadvantages': [
                'Coût élevé',
                'Complexité',
                'Nécessite des instruments spécifiques'
            ],
            'use_cases': [
                'Options trading avancé',
                'Gestion de portefeuille complexe',
                'Trading de volatilité'
            ]
        },
        'cross': {
            'name': 'Cross Hedging',
            'description': 'Couverture avec instruments corrélés',
            'advantages': [
                'Flexibilité des instruments',
                'Réduction des coûts',
                'Diversification'
            ],
            'disadvantages': [
                'Risque de base',
                'Corrélation variable',
                'Efficacité limitée'
            ],
            'use_cases': [
                'Couverture d\'actifs non liquides',
                'Optimisation des coûts',
                'Diversification des risques'
            ]
        }
    }
    
    return info.get(strategy_type.lower(), {})


def get_hedging_recommendation(
    portfolio_type: str = 'options',
    risk_tolerance: str = 'medium',
    budget: str = 'medium',
    complexity_tolerance: str = 'medium'
) -> Dict[str, Any]:
    """
    Recommande une stratégie de couverture selon les besoins.
    
    Args:
        portfolio_type: Type de portefeuille ('options', 'stocks', 'crypto', 'mixed')
        risk_tolerance: Tolérance au risque ('low', 'medium', 'high')
        budget: Budget ('low', 'medium', 'high')
        complexity_tolerance: Tolérance à la complexité ('low', 'medium', 'high')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    if portfolio_type == 'options':
        if risk_tolerance == 'low':
            return {
                'recommended_strategy': {
                    'type': 'delta',
                    'description': 'Delta Hedging pour options avec faible tolérance au risque'
                },
                'alternative_strategies': ['gamma'],
                'features': ['Protection directionnelle', 'Rebalancing fréquent']
            }
        else:
            return {
                'recommended_strategy': {
                    'type': 'gamma',
                    'description': 'Gamma Hedging pour options avancées'
                },
                'alternative_strategies': ['delta'],
                'features': ['Protection de convexité', 'Gestion de volatilité']
            }
    
    elif portfolio_type == 'stocks':
        return {
            'recommended_strategy': {
                'type': 'cross',
                'description': 'Cross Hedging pour actions avec instruments corrélés'
            },
            'alternative_strategies': ['delta'],
            'features': ['Flexibilité', 'Réduction des coûts', 'Diversification']
        }
    
    elif portfolio_type == 'crypto':
        return {
            'recommended_strategy': {
                'type': 'cross',
                'description': 'Cross Hedging pour crypto avec instruments corrélés'
            },
            'alternative_strategies': ['delta'],
            'features': ['Corrélation entre cryptos', 'Réduction des risques', 'Flexibilité']
        }
    
    # Par défaut
    return {
        'recommended_strategy': {
            'type': 'delta',
            'description': 'Delta Hedging pour approche générale'
        },
        'alternative_strategies': ['cross', 'gamma'],
        'features': ['Protection directionnelle', 'Flexibilité', 'Standard']
    }


logger.info("Module de stratégies de couverture initialisé")
