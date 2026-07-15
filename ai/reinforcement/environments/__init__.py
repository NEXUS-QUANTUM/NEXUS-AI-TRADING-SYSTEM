
# ai/reinforcement/environments/__init__.py
"""
NEXUS AI TRADING SYSTEM - Reinforcement Learning Environments Module
Copyright © 2026 NEXUS QUANTUM LTD

Module d'environnements pour l'apprentissage par renforcement.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.reinforcement.environments.market_env import (
    MarketEnv,
    MarketEnvConfig,
    DiscreteMarketEnv,
    create_market_env,
)

from ai.reinforcement.environments.multi_agent_env import (
    MultiAgentMarketEnv,
    MultiAgentEnvConfig,
    AgentConfig,
    create_multi_agent_env,
)

from ai.reinforcement.environments.portfolio_env import (
    PortfolioEnv,
    PortfolioEnvConfig,
    create_portfolio_env,
)

from ai.reinforcement.environments.trading_env import (
    TradingEnv,
    TradingEnvConfig,
    create_trading_env,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Market Environment
    'MarketEnv',
    'MarketEnvConfig',
    'DiscreteMarketEnv',
    'create_market_env',
    
    # Multi-Agent Environment
    'MultiAgentMarketEnv',
    'MultiAgentEnvConfig',
    'AgentConfig',
    'create_multi_agent_env',
    
    # Portfolio Environment
    'PortfolioEnv',
    'PortfolioEnvConfig',
    'create_portfolio_env',
    
    # Trading Environment
    'TradingEnv',
    'TradingEnvConfig',
    'create_trading_env',
]


def create_env(
    env_type: str = 'market',
    **kwargs
) -> Any:
    """
    Factory pour créer des environnements RL.
    
    Args:
        env_type: Type d'environnement ('market', 'trading', 'portfolio', 'multi_agent')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance de l'environnement
    
    Examples:
        ```python
        # Market environment
        env = create_env(
            'market',
            symbol='BTC-USD',
            window_size=50,
            initial_balance=10000.0
        )
        
        # Trading environment
        env = create_env(
            'trading',
            symbol='BTC-USD',
            window_size=50,
            initial_balance=10000.0,
            stop_loss=0.05,
            take_profit=0.10
        )
        
        # Portfolio environment
        env = create_env(
            'portfolio',
            symbols=['BTC-USD', 'ETH-USD', 'SOL-USD'],
            initial_balance=10000.0
        )
        
        # Multi-agent environment
        env = create_env(
            'multi_agent',
            symbols=['BTC-USD'],
            agent_configs=[
                {'name': 'Trader_1', 'strategy': 'momentum'},
                {'name': 'Trader_2', 'strategy': 'mean_reversion'},
            ]
        )
        ```
    """
    env_type = env_type.lower()
    
    if env_type == 'market':
        symbol = kwargs.get('symbol', 'BTC-USD')
        window_size = kwargs.get('window_size', 50)
        initial_balance = kwargs.get('initial_balance', 10000.0)
        discrete = kwargs.get('discrete', False)
        
        return create_market_env(
            symbol=symbol,
            window_size=window_size,
            initial_balance=initial_balance,
            discrete=discrete,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'window_size', 'initial_balance', 'discrete']}
        )
    
    elif env_type == 'trading':
        symbol = kwargs.get('symbol', 'BTC-USD')
        window_size = kwargs.get('window_size', 50)
        initial_balance = kwargs.get('initial_balance', 10000.0)
        
        return create_trading_env(
            symbol=symbol,
            window_size=window_size,
            initial_balance=initial_balance,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbol', 'window_size', 'initial_balance']}
        )
    
    elif env_type == 'portfolio':
        symbols = kwargs.get('symbols', ['BTC-USD', 'ETH-USD', 'SOL-USD'])
        initial_balance = kwargs.get('initial_balance', 10000.0)
        
        return create_portfolio_env(
            symbols=symbols,
            initial_balance=initial_balance,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbols', 'initial_balance']}
        )
    
    elif env_type == 'multi_agent':
        symbols = kwargs.get('symbols', ['BTC-USD'])
        agent_configs = kwargs.get('agent_configs', [])
        
        return create_multi_agent_env(
            symbols=symbols,
            agent_configs=agent_configs,
            **{k: v for k, v in kwargs.items() 
               if k not in ['symbols', 'agent_configs']}
        )
    
    else:
        raise ValueError(f"Type d'environnement non supporté: {env_type}")


def get_available_envs() -> List[str]:
    """
    Retourne la liste des environnements disponibles.
    
    Returns:
        List[str]: Liste des types d'environnements
    """
    envs = ['market', 'trading', 'portfolio', 'multi_agent']
    
    try:
        import gymnasium
    except ImportError:
        envs = []
    
    return envs


def get_env_info(env_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type d'environnement.
    
    Args:
        env_type: Type d'environnement
    
    Returns:
        Dict[str, Any]: Informations sur l'environnement
    """
    info = {
        'market': {
            'name': 'Market Environment',
            'description': 'Environnement de trading simple avec un actif',
            'action_space': 'Continuous (position, stop_loss)',
            'observation_space': 'Continuous (price, indicators, position, balance)',
            'features': [
                'Position sizing',
                'Transaction costs',
                'Technical indicators',
                'Random starts'
            ]
        },
        'trading': {
            'name': 'Trading Environment',
            'description': 'Environnement de trading avancé avec stop loss et take profit',
            'action_space': 'Continuous (position, stop_loss, take_profit)',
            'observation_space': 'Continuous (price, indicators, position, balance, pnl)',
            'features': [
                'Long and short positions',
                'Stop loss and take profit',
                'Margin trading',
                'Technical indicators'
            ]
        },
        'portfolio': {
            'name': 'Portfolio Environment',
            'description': 'Environnement de gestion de portefeuille multi-actifs',
            'action_space': 'Continuous (allocations)',
            'observation_space': 'Continuous (prices, indicators, allocations, balance)',
            'features': [
                'Multi-asset allocation',
                'Transaction costs',
                'Portfolio metrics (Sharpe, Sortino)',
                'Risk management'
            ]
        },
        'multi_agent': {
            'name': 'Multi-Agent Environment',
            'description': 'Environnement multi-agents pour le trading',
            'action_space': 'Continuous per agent',
            'observation_space': 'Continuous per agent',
            'features': [
                'Multiple trading agents',
                'Competition and cooperation',
                'Individual portfolio management',
                'Shared market data'
            ]
        }
    }
    
    return info.get(env_type.lower(), {})


def get_env_recommendation(
    task: str = 'single_asset',
    num_agents: int = 1,
    num_assets: int = 1,
    complexity: str = 'medium'
) -> Dict[str, Any]:
    """
    Recommande un environnement selon les besoins.
    
    Args:
        task: Tâche ('single_asset', 'multi_asset', 'multi_agent')
        num_agents: Nombre d'agents
        num_assets: Nombre d'actifs
        complexity: Complexité ('simple', 'medium', 'complex')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    if num_agents > 1:
        return {
            'recommended_env': {
                'type': 'multi_agent',
                'description': 'Environnement multi-agents pour plusieurs traders'
            },
            'alternative_envs': ['trading', 'market'],
            'features': ['Competition mode', 'Cooperative rewards', 'Individual portfolios']
        }
    
    if num_assets > 1:
        return {
            'recommended_env': {
                'type': 'portfolio',
                'description': 'Environnement de portefeuille pour allocation multi-actifs'
            },
            'alternative_envs': ['market', 'trading'],
            'features': ['Multi-asset allocation', 'Portfolio metrics', 'Risk management']
        }
    
    if complexity == 'complex':
        return {
            'recommended_env': {
                'type': 'trading',
                'description': 'Environnement de trading avancé avec stop loss et take profit'
            },
            'alternative_envs': ['market'],
            'features': ['Stop loss', 'Take profit', 'Margin trading']
        }
    
    return {
        'recommended_env': {
            'type': 'market',
            'description': 'Environnement de marché simple pour débuter'
        },
        'alternative_envs': ['trading'],
        'features': ['Position sizing', 'Transaction costs', 'Technical indicators']
    }


logger.info("Module d'environnements RL initialisé")
