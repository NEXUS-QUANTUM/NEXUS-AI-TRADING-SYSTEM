# ai/simulation/__init__.py
"""
NEXUS AI TRADING SYSTEM - Simulation Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de simulation pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.simulation.broker_simulator import (
    BrokerSimulator,
    BrokerSimulatorConfig,
    Order,
    Position,
    Account,
    create_broker_simulator,
)

from ai.simulation.market_simulator import (
    MarketSimulator,
    MarketSimulatorConfig,
    MarketData,
    create_market_simulator,
)

from ai.simulation.order_book_simulator import (
    OrderBookSimulator,
    OrderBookSimulatorConfig,
    OrderBookLevel,
    OrderBookSnapshot,
    create_order_book_simulator,
)

from ai.simulation.scenario_generator import (
    ScenarioGenerator,
    ScenarioConfig,
    ScenarioResult,
    create_scenario_generator,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Broker Simulator
    'BrokerSimulator',
    'BrokerSimulatorConfig',
    'Order',
    'Position',
    'Account',
    'create_broker_simulator',
    
    # Market Simulator
    'MarketSimulator',
    'MarketSimulatorConfig',
    'MarketData',
    'create_market_simulator',
    
    # Order Book Simulator
    'OrderBookSimulator',
    'OrderBookSimulatorConfig',
    'OrderBookLevel',
    'OrderBookSnapshot',
    'create_order_book_simulator',
    
    # Scenario Generator
    'ScenarioGenerator',
    'ScenarioConfig',
    'ScenarioResult',
    'create_scenario_generator',
]


def create_simulation_component(
    component_type: str,
    **kwargs
) -> Any:
    """
    Factory pour créer des composants de simulation.
    
    Args:
        component_type: Type de composant ('broker', 'market', 'order_book', 'scenario')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance du composant
    
    Examples:
        ```python
        # Broker Simulator
        broker = create_simulation_component(
            'broker',
            initial_balance=10000.0,
            commission=0.001,
            slippage=0.0005
        )
        
        # Market Simulator
        market = create_simulation_component(
            'market',
            symbols=['BTC-USD', 'ETH-USD'],
            start_date='2024-01-01',
            end_date='2024-12-31',
            frequency='1h'
        )
        
        # Order Book Simulator
        order_book = create_simulation_component(
            'order_book',
            symbol='BTC-USD',
            initial_price=50000.0,
            depth=20
        )
        
        # Scenario Generator
        scenario = create_simulation_component(
            'scenario',
            name='bear_market',
            market_condition='bear',
            duration_days=30
        )
        ```
    """
    component_type = component_type.lower()
    
    if component_type == 'broker':
        initial_balance = kwargs.get('initial_balance', 10000.0)
        commission = kwargs.get('commission', 0.001)
        slippage = kwargs.get('slippage', 0.0005)
        
        return create_broker_simulator(
            initial_balance=initial_balance,
            commission=commission,
            slippage=slippage,
            **{k: v for k, v in kwargs.items() 
               if k not in ['initial_balance', 'commission', 'slippage']}
        )
    
    elif component_type == 'market':
        symbols = kwargs.get('symbols', ['BTC-USD', 'ETH-USD', 'SOL-USD'])
        start_date = kwargs.get('start_date', '2024-01-01')
        end_date = kwargs.get('end_date', '2024-12-31')
        frequency = kwargs.get('frequency', '1h')
        
        return create_market_simulator(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbols', 'start_date', 'end_date', 'frequency']}
        )
    
    elif component_type == 'order_book':
        symbol = kwargs.get('symbol', 'BTC-USD')
        initial_price = kwargs.get('initial_price', 50000.0)
        depth = kwargs.get('depth', 20)
        
        return create_order_book_simulator(
            symbol=symbol,
            initial_price=initial_price,
            depth=depth,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'initial_price', 'depth']}
        )
    
    elif component_type == 'scenario':
        name = kwargs.get('name', 'default_scenario')
        market_condition = kwargs.get('market_condition', 'normal')
        duration_days = kwargs.get('duration_days', 30)
        
        return create_scenario_generator(
            name=name,
            market_condition=market_condition,
            duration_days=duration_days,
            **{k: v for k, v in kwargs.items() 
               if k not in ['name', 'market_condition', 'duration_days']}
        )
    
    else:
        raise ValueError(f"Type de composant de simulation non supporté: {component_type}")


def get_available_simulation_components() -> List[str]:
    """
    Retourne la liste des composants de simulation disponibles.
    
    Returns:
        List[str]: Liste des types de composants
    """
    return ['broker', 'market', 'order_book', 'scenario']


def get_simulation_component_info(component_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de composant de simulation.
    
    Args:
        component_type: Type de composant
    
    Returns:
        Dict[str, Any]: Informations sur le composant
    """
    info = {
        'broker': {
            'name': 'Broker Simulator',
            'description': 'Simulateur de broker pour l\'exécution d\'ordres',
            'features': [
                'Exécution d\'ordres',
                'Gestion des positions',
                'Gestion du compte',
                'Slippage et commissions',
                'Marge et levier'
            ],
            'use_cases': [
                'Backtesting',
                'Simulation de stratégies',
                'Test d\'exécution'
            ]
        },
        'market': {
            'name': 'Market Simulator',
            'description': 'Simulateur de marché multi-symboles',
            'features': [
                'Multi-symbol simulation',
                'Correlated price movements',
                'Volume simulation',
                'Price spikes',
                'Technical indicators'
            ],
            'use_cases': [
                'Génération de données',
                'Test de stratégies',
                'Analyse de marché'
            ]
        },
        'order_book': {
            'name': 'Order Book Simulator',
            'description': 'Simulateur de carnet d\'ordres Level 2',
            'features': [
                'Bid-ask spread',
                'Order arrival and cancellation',
                'Price updates',
                'Volume simulation',
                'Level 2 data'
            ],
            'use_cases': [
                'Simulation d\'exécution',
                'Analyse de liquidité',
                'Test d\'impact de marché'
            ]
        },
        'scenario': {
            'name': 'Scenario Generator',
            'description': 'Générateur de scénarios de marché',
            'features': [
                'Multiples conditions de marché',
                'Chocs de marché',
                'Corrélation entre actifs',
                'Scénarios personnalisables',
                'Export/Import JSON'
            ],
            'use_cases': [
                'Stress testing',
                'Analyse de scénarios',
                'Planification stratégique'
            ]
        }
    }
    
    return info.get(component_type.lower(), {})


def get_simulation_recommendation(
    purpose: str = 'backtesting',
    complexity: str = 'medium',
    data_availability: str = 'low'
) -> Dict[str, Any]:
    """
    Recommande un composant de simulation selon les besoins.
    
    Args:
        purpose: Objectif ('backtesting', 'strategy_testing', 'market_analysis', 'stress_testing')
        complexity: Complexité ('simple', 'medium', 'complex')
        data_availability: Disponibilité des données ('low', 'medium', 'high')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    if purpose == 'backtesting':
        if data_availability == 'low':
            return {
                'recommended_component': {
                    'type': 'broker',
                    'description': 'Broker Simulator pour backtesting avec données limitées'
                },
                'alternative_components': ['market'],
                'features': ['Exécution d\'ordres', 'Gestion de compte', 'Simulation de marché']
            }
        else:
            return {
                'recommended_component': {
                    'type': 'broker',
                    'description': 'Broker Simulator pour backtesting complet'
                },
                'alternative_components': ['order_book', 'market'],
                'features': ['Exécution réaliste', 'Slippage', 'Commissions']
            }
    
    if purpose == 'strategy_testing':
        return {
            'recommended_component': {
                'type': 'market',
                'description': 'Market Simulator pour test de stratégies'
            },
            'alternative_components': ['broker', 'scenario'],
            'features': ['Données multi-symboles', 'Indicateurs techniques', 'Conditions variées']
        }
    
    if purpose == 'market_analysis':
        return {
            'recommended_component': {
                'type': 'order_book',
                'description': 'Order Book Simulator pour analyse de liquidité'
            },
            'alternative_components': ['market'],
            'features': ['Level 2 données', 'Impact de marché', 'Profondeur']
        }
    
    if purpose == 'stress_testing':
        return {
            'recommended_component': {
                'type': 'scenario',
                'description': 'Scenario Generator pour stress testing'
            },
            'alternative_components': ['market'],
            'features': ['Chocs de marché', 'Conditions extrêmes', 'Scénarios personnalisables']
        }
    
    # Par défaut
    return {
        'recommended_component': {
            'type': 'market',
            'description': 'Market Simulator pour approche générale'
        },
        'alternative_components': ['broker', 'scenario'],
        'features': ['Génération de données', 'Multi-symboles', 'Flexibilité']
    }


logger.info("Module de simulation initialisé")
