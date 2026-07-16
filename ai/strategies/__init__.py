# ai/strategies/__init__.py
"""
NEXUS AI TRADING SYSTEM - Trading Strategies Module
Copyright © 2026 NEXUS QUANTUM LTD

Module central des stratégies de trading pour l'IA.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.strategies.base_strategy import (
    BaseStrategy,
    StrategyConfig,
    Signal,
    Position,
    Trade,
    BacktestResult,
    create_strategy,
)

# Sous-modules
from ai.strategies import arbitrage
from ai.strategies import hedging
from ai.strategies import mean_reversion
from ai.strategies import momentum
from ai.strategies import scalping
from ai.strategies import sniper
from ai.strategies import swing

logger = logging.getLogger(__name__)


__all__ = [
    # Base
    'BaseStrategy',
    'StrategyConfig',
    'Signal',
    'Position',
    'Trade',
    'BacktestResult',
    'create_strategy',
    
    # Sous-modules
    'arbitrage',
    'hedging',
    'mean_reversion',
    'momentum',
    'scalping',
    'sniper',
    'swing',
]


def get_available_strategies() -> Dict[str, List[str]]:
    """
    Retourne la liste des stratégies disponibles par catégorie.
    
    Returns:
        Dict[str, List[str]]: Stratégies par catégorie
    """
    return {
        'arbitrage': arbitrage.get_available_arbitrage_strategies(),
        'hedging': hedging.get_available_hedging_strategies(),
        'mean_reversion': mean_reversion.get_available_mean_reversion_strategies(),
        'momentum': momentum.get_available_momentum_strategies(),
        'scalping': scalping.get_available_scalping_strategies(),
        'sniper': sniper.get_available_sniper_strategies(),
        'swing': swing.get_available_swing_strategies(),
    }


def get_strategy_info(category: str, strategy_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur une stratégie spécifique.
    
    Args:
        category: Catégorie de stratégie
        strategy_type: Type de stratégie
    
    Returns:
        Dict[str, Any]: Informations sur la stratégie
    """
    category_info = {
        'arbitrage': arbitrage.get_arbitrage_strategy_info,
        'hedging': hedging.get_hedging_strategy_info,
        'mean_reversion': mean_reversion.get_mean_reversion_strategy_info,
        'momentum': momentum.get_momentum_strategy_info,
        'scalping': scalping.get_scalping_strategy_info,
        'sniper': sniper.get_sniper_strategy_info,
        'swing': swing.get_swing_strategy_info,
    }
    
    if category in category_info:
        try:
            return category_info[category](strategy_type)
        except:
            pass
    
    return {
        'name': strategy_type.capitalize(),
        'description': f"Stratégie {strategy_type} dans la catégorie {category}",
        'advantages': ['À documenter'],
        'disadvantages': ['À documenter'],
        'use_cases': ['À documenter'],
    }


def get_strategy_recommendation(
    trading_style: str = 'swing',
    risk_tolerance: str = 'medium',
    time_horizon: str = 'medium',
    capital: str = 'medium'
) -> Dict[str, Any]:
    """
    Recommande une stratégie selon les besoins.
    
    Args:
        trading_style: Style de trading ('scalping', 'day', 'swing', 'position')
        risk_tolerance: Tolérance au risque ('low', 'medium', 'high')
        time_horizon: Horizon temporel ('short', 'medium', 'long')
        capital: Capital disponible ('low', 'medium', 'high')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    recommendations = {
        'scalping': {
            'category': 'scalping',
            'strategy': 'order_book',
            'description': 'Scalping sur carnet d\'ordres pour trading rapide'
        },
        'day': {
            'category': 'momentum',
            'strategy': 'macd',
            'description': 'MACD pour trading journalier'
        },
        'swing': {
            'category': 'swing',
            'strategy': 'support_resistance',
            'description': 'Support/Résistance pour swing trading'
        },
        'position': {
            'category': 'momentum',
            'strategy': 'trend_following',
            'description': 'Suivi de tendance pour position trading'
        }
    }
    
    if risk_tolerance == 'low':
        return {
            'recommended_strategy': {
                'category': 'hedging',
                'strategy': 'delta',
                'description': 'Delta Hedging pour risque faible'
            },
            'alternative_strategies': [
                {'category': 'mean_reversion', 'strategy': 'bollinger_bands'},
                {'category': 'arbitrage', 'strategy': 'statistical'}
            ]
        }
    
    if capital == 'low':
        return {
            'recommended_strategy': {
                'category': 'scalping',
                'strategy': 'spread',
                'description': 'Spread Scalping pour capital limité'
            },
            'alternative_strategies': [
                {'category': 'momentum', 'strategy': 'ma_crossover'},
                {'category': 'swing', 'strategy': 'fibonacci'}
            ]
        }
    
    if trading_style in recommendations:
        rec = recommendations[trading_style]
        return {
            'recommended_strategy': rec,
            'alternative_strategies': [
                {'category': 'mean_reversion', 'strategy': 'pairs_trading'},
                {'category': 'momentum', 'strategy': 'trend_following'},
                {'category': 'sniper', 'strategy': 'breakout'}
            ]
        }
    
    # Par défaut
    return {
        'recommended_strategy': {
            'category': 'swing',
            'strategy': 'support_resistance',
            'description': 'Support/Résistance pour approche générale'
        },
        'alternative_strategies': [
            {'category': 'momentum', 'strategy': 'macd'},
            {'category': 'mean_reversion', 'strategy': 'bollinger_bands'},
            {'category': 'arbitrage', 'strategy': 'statistical'}
        ]
    }


def get_strategy_categories() -> List[str]:
    """
    Retourne la liste des catégories de stratégies disponibles.
    
    Returns:
        List[str]: Liste des catégories
    """
    return ['arbitrage', 'hedging', 'mean_reversion', 'momentum', 'scalping', 'sniper', 'swing']


logger.info("Module de stratégies initialisé")
