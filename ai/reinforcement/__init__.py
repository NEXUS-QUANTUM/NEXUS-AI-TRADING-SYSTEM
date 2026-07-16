# ai/reinforcement/__init__.py
"""
NEXUS AI TRADING SYSTEM - Reinforcement Learning Module
Copyright © 2026 NEXUS QUANTUM LTD

Module central d'apprentissage par renforcement pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

# Sous-modules
from ai.reinforcement import agents
from ai.reinforcement import environments
from ai.reinforcement import policies
from ai.reinforcement import rewards
from ai.reinforcement import training

logger = logging.getLogger(__name__)


__all__ = [
    # Sous-modules
    'agents',
    'environments',
    'policies',
    'rewards',
    'training',
]


def create_rl_component(
    component_type: str,
    sub_type: str,
    **kwargs
) -> Any:
    """
    Factory unifiée pour créer des composants RL.
    
    Args:
        component_type: Type de composant ('agent', 'environment', 'policy', 'reward', 'trainer')
        sub_type: Sous-type spécifique
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance du composant
    
    Examples:
        ```python
        # Agent
        agent = create_rl_component(
            'agent',
            'dqn',
            state_dim=10,
            action_dim=3,
            hidden_dim=256
        )
        
        # Environment
        env = create_rl_component(
            'environment',
            'market',
            symbol='BTC-USD',
            window_size=50
        )
        
        # Policy
        policy = create_rl_component(
            'policy',
            'categorical',
            state_dim=10,
            action_dim=3
        )
        
        # Reward
        reward = create_rl_component(
            'reward',
            'sharpe',
            risk_free_rate=0.02,
            target_sharpe=1.0
        )
        
        # Trainer
        trainer = create_rl_component(
            'trainer',
            'default',
            n_episodes=1000,
            eval_frequency=50
        )
        ```
    """
    component_type = component_type.lower()
    sub_type = sub_type.lower()
    
    if component_type == 'agent':
        return agents.create_rl_agent(sub_type, **kwargs)
    
    elif component_type == 'environment':
        return environments.create_env(sub_type, **kwargs)
    
    elif component_type == 'policy':
        return policies.create_policy(sub_type, **kwargs)
    
    elif component_type == 'reward':
        return rewards.create_reward_function(sub_type, **kwargs)
    
    elif component_type == 'trainer':
        if sub_type == 'default':
            return training.create_trainer(**kwargs)
        else:
            raise ValueError(f"Sous-type de trainer non supporté: {sub_type}")
    
    else:
        raise ValueError(f"Type de composant RL non supporté: {component_type}")


def get_available_rl_components() -> Dict[str, List[str]]:
    """
    Retourne la liste des composants RL disponibles.
    
    Returns:
        Dict[str, List[str]]: Composants par catégorie
    """
    return {
        'agent': agents.get_available_rl_agents(),
        'environment': environments.get_available_envs(),
        'policy': policies.get_available_policies(),
        'reward': rewards.get_available_rewards(),
        'trainer': ['default'],
    }


def get_rl_component_info(component_type: str, sub_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un composant RL.
    
    Args:
        component_type: Type de composant
        sub_type: Sous-type spécifique
    
    Returns:
        Dict[str, Any]: Informations sur le composant
    """
    component_type = component_type.lower()
    sub_type = sub_type.lower()
    
    if component_type == 'agent':
        return agents.get_rl_agent_info(sub_type)
    
    elif component_type == 'environment':
        return environments.get_env_info(sub_type)
    
    elif component_type == 'policy':
        return policies.get_policy_info(sub_type)
    
    elif component_type == 'reward':
        return rewards.get_reward_info(sub_type)
    
    elif component_type == 'trainer':
        return {
            'name': 'Trainer',
            'description': 'Entraîneur complet pour RL',
            'features': [
                'Boucle d\'entraînement',
                'Évaluation périodique',
                'Checkpoints',
                'Logging',
                'Visualisation'
            ],
        }
    
    else:
        return {
            'name': sub_type.capitalize(),
            'description': f"Composant {sub_type} dans la catégorie {component_type}",
        }


def get_rl_recommendation(
    task: str = 'trading',
    action_space: str = 'continuous',
    complexity: str = 'medium',
    **kwargs
) -> Dict[str, Any]:
    """
    Recommande des composants RL selon les besoins.
    
    Args:
        task: Tâche ('trading', 'portfolio', 'market_making')
        action_space: Espace d'actions ('discrete', 'continuous')
        complexity: Complexité ('simple', 'medium', 'complex')
        **kwargs: Arguments supplémentaires
    
    Returns:
        Dict[str, Any]: Recommandations de composants
    """
    recommendations = {
        'trading': {
            'discrete': {
                'simple': {
                    'agent': {'type': 'dqn', 'config': {'hidden_dim': 128}},
                    'environment': {'type': 'market', 'config': {'window_size': 30}},
                    'policy': {'type': 'categorical', 'config': {}},
                    'reward': {'type': 'pnl', 'config': {}},
                },
                'medium': {
                    'agent': {'type': 'rainbow', 'config': {'hidden_dim': 256}},
                    'environment': {'type': 'trading', 'config': {'window_size': 50}},
                    'policy': {'type': 'categorical', 'config': {'temperature': 0.5}},
                    'reward': {'type': 'sharpe', 'config': {'target_sharpe': 1.0}},
                },
                'complex': {
                    'agent': {'type': 'ppo', 'config': {'hidden_dim': 256}},
                    'environment': {'type': 'trading', 'config': {'window_size': 100}},
                    'policy': {'type': 'stochastic', 'config': {'policy_type': 'categorical'}},
                    'reward': {'type': 'risk_adjusted', 'config': {'use_sharpe_ratio': True}},
                },
            },
            'continuous': {
                'simple': {
                    'agent': {'type': 'sac', 'config': {'hidden_dim': 128}},
                    'environment': {'type': 'market', 'config': {'window_size': 30}},
                    'policy': {'type': 'gaussian', 'config': {}},
                    'reward': {'type': 'pnl', 'config': {}},
                },
                'medium': {
                    'agent': {'type': 'td3', 'config': {'hidden_dim': 256}},
                    'environment': {'type': 'trading', 'config': {'window_size': 50}},
                    'policy': {'type': 'gaussian', 'config': {'use_state_dependent_std': True}},
                    'reward': {'type': 'sharpe', 'config': {'target_sharpe': 1.0}},
                },
                'complex': {
                    'agent': {'type': 'ppo', 'config': {'hidden_dim': 256, 'continuous_actions': True}},
                    'environment': {'type': 'trading', 'config': {'window_size': 100}},
                    'policy': {'type': 'stochastic', 'config': {'policy_type': 'gaussian'}},
                    'reward': {'type': 'risk_adjusted', 'config': {'use_sharpe_ratio': True}},
                },
            },
        },
        'portfolio': {
            'continuous': {
                'simple': {
                    'agent': {'type': 'sac', 'config': {'hidden_dim': 128}},
                    'environment': {'type': 'portfolio', 'config': {'symbols': ['BTC-USD']}},
                    'policy': {'type': 'deterministic', 'config': {}},
                    'reward': {'type': 'sharpe', 'config': {'target_sharpe': 0.5}},
                },
                'medium': {
                    'agent': {'type': 'td3', 'config': {'hidden_dim': 256}},
                    'environment': {'type': 'portfolio', 'config': {'symbols': ['BTC-USD', 'ETH-USD']}},
                    'policy': {'type': 'gaussian', 'config': {}},
                    'reward': {'type': 'risk_adjusted', 'config': {'use_sharpe_ratio': True}},
                },
                'complex': {
                    'agent': {'type': 'ppo', 'config': {'hidden_dim': 256, 'continuous_actions': True}},
                    'environment': {'type': 'portfolio', 'config': {'symbols': ['BTC-USD', 'ETH-USD', 'SOL-USD']}},
                    'policy': {'type': 'stochastic', 'config': {'policy_type': 'gaussian'}},
                    'reward': {'type': 'custom', 'config': {'use_components': True}},
                },
            },
        },
    }
    
    task_lower = task.lower()
    if task_lower not in recommendations:
        task_lower = 'trading'
    
    action_space_lower = action_space.lower()
    if action_space_lower not in ['discrete', 'continuous']:
        action_space_lower = 'continuous'
    
    complexity_lower = complexity.lower()
    if complexity_lower not in ['simple', 'medium', 'complex']:
        complexity_lower = 'medium'
    
    recommendation = recommendations[task_lower][action_space_lower][complexity_lower]
    
    return {
        'task': task_lower,
        'action_space': action_space_lower,
        'complexity': complexity_lower,
        'recommended_components': recommendation,
        'training': {
            'n_episodes': 500 if complexity_lower == 'simple' else 1000 if complexity_lower == 'medium' else 2000,
            'eval_frequency': 50,
            'save_frequency': 100,
        }
    }


logger.info("Module d'apprentissage par renforcement initialisé")
