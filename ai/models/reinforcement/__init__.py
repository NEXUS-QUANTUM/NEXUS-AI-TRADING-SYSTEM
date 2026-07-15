
# ai/models/reinforcement/__init__.py
"""
NEXUS AI TRADING SYSTEM - Reinforcement Learning Models Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de modèles d'apprentissage par renforcement pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.models.reinforcement.dqn_agent import (
    DQNAgent,
    DQNConfig,
    DQNResult,
    create_dqn_agent,
)

from ai.models.reinforcement.ppo_agent import (
    PPOAgent,
    PPOConfig,
    PPOResult,
    create_ppo_agent,
)

from ai.models.reinforcement.sac_agent import (
    SACAgent,
    SACConfig,
    SACResult,
    create_sac_agent,
)

from ai.models.reinforcement.td3_agent import (
    TD3Agent,
    TD3Config,
    TD3Result,
    create_td3_agent,
)

from ai.models.reinforcement.replay_buffer import (
    ReplayBuffer,
    ReplayBufferConfig,
    HierarchicalReplayBuffer,
    create_replay_buffer,
    create_hierarchical_replay_buffer,
)

logger = logging.getLogger(__name__)


__all__ = [
    # DQN
    'DQNAgent',
    'DQNConfig',
    'DQNResult',
    'create_dqn_agent',
    
    # PPO
    'PPOAgent',
    'PPOConfig',
    'PPOResult',
    'create_ppo_agent',
    
    # SAC
    'SACAgent',
    'SACConfig',
    'SACResult',
    'create_sac_agent',
    
    # TD3
    'TD3Agent',
    'TD3Config',
    'TD3Result',
    'create_td3_agent',
    
    # Replay Buffer
    'ReplayBuffer',
    'ReplayBufferConfig',
    'HierarchicalReplayBuffer',
    'create_replay_buffer',
    'create_hierarchical_replay_buffer',
]


def create_rl_agent(
    agent_type: str = 'dqn',
    **kwargs
) -> Any:
    """
    Factory pour créer des agents d'apprentissage par renforcement.
    
    Args:
        agent_type: Type d'agent ('dqn', 'ppo', 'sac', 'td3')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance de l'agent
    
    Examples:
        ```python
        # Création d'un agent DQN
        agent = create_rl_agent(
            'dqn',
            state_dim=10,
            action_dim=3,
            hidden_dim=256,
            memory_size=10000
        )
        
        # Création d'un agent PPO
        agent = create_rl_agent(
            'ppo',
            state_dim=10,
            action_dim=3,
            hidden_dim=256,
            buffer_size=2048
        )
        
        # Création d'un agent SAC
        agent = create_rl_agent(
            'sac',
            state_dim=10,
            action_dim=3,
            hidden_dim=256,
            memory_size=100000
        )
        
        # Création d'un agent TD3
        agent = create_rl_agent(
            'td3',
            state_dim=10,
            action_dim=3,
            hidden_dim=256,
            memory_size=100000
        )
        ```
    """
    agent_type = agent_type.lower()
    
    if agent_type == 'dqn':
        state_dim = kwargs.get('state_dim', 10)
        action_dim = kwargs.get('action_dim', 3)
        hidden_dim = kwargs.get('hidden_dim', 256)
        learning_rate = kwargs.get('learning_rate', 0.001)
        memory_size = kwargs.get('memory_size', 10000)
        
        return create_dqn_agent(
            state_dim=state_dim,
            action_dim=action_dim,
            hidden_dim=hidden_dim,
            learning_rate=learning_rate,
            memory_size=memory_size,
            **{k: v for k, v in kwargs.items() 
               if k not in ['state_dim', 'action_dim', 'hidden_dim', 
                           'learning_rate', 'memory_size']}
        )
    
    elif agent_type == 'ppo':
        state_dim = kwargs.get('state_dim', 10)
        action_dim = kwargs.get('action_dim', 3)
        hidden_dim = kwargs.get('hidden_dim', 256)
        learning_rate = kwargs.get('learning_rate', 0.0003)
        buffer_size = kwargs.get('buffer_size', 2048)
        
        return create_ppo_agent(
            state_dim=state_dim,
            action_dim=action_dim,
            hidden_dim=hidden_dim,
            learning_rate=learning_rate,
            buffer_size=buffer_size,
            **{k: v for k, v in kwargs.items() 
               if k not in ['state_dim', 'action_dim', 'hidden_dim', 
                           'learning_rate', 'buffer_size']}
        )
    
    elif agent_type == 'sac':
        state_dim = kwargs.get('state_dim', 10)
        action_dim = kwargs.get('action_dim', 3)
        hidden_dim = kwargs.get('hidden_dim', 256)
        learning_rate = kwargs.get('learning_rate', 0.0003)
        memory_size = kwargs.get('memory_size', 100000)
        
        return create_sac_agent(
            state_dim=state_dim,
            action_dim=action_dim,
            hidden_dim=hidden_dim,
            learning_rate=learning_rate,
            memory_size=memory_size,
            **{k: v for k, v in kwargs.items() 
               if k not in ['state_dim', 'action_dim', 'hidden_dim', 
                           'learning_rate', 'memory_size']}
        )
    
    elif agent_type == 'td3':
        state_dim = kwargs.get('state_dim', 10)
        action_dim = kwargs.get('action_dim', 3)
        hidden_dim = kwargs.get('hidden_dim', 256)
        learning_rate = kwargs.get('learning_rate', 0.0003)
        memory_size = kwargs.get('memory_size', 100000)
        
        return create_td3_agent(
            state_dim=state_dim,
            action_dim=action_dim,
            hidden_dim=hidden_dim,
            learning_rate=learning_rate,
            memory_size=memory_size,
            **{k: v for k, v in kwargs.items() 
               if k not in ['state_dim', 'action_dim', 'hidden_dim', 
                           'learning_rate', 'memory_size']}
        )
    
    else:
        raise ValueError(f"Type d'agent RL non supporté: {agent_type}")


def get_available_rl_agents() -> List[str]:
    """
    Retourne la liste des agents RL disponibles.
    
    Returns:
        List[str]: Liste des types d'agents
    """
    agents = ['dqn', 'ppo', 'sac', 'td3']
    
    # Vérifier les dépendances
    try:
        import torch
    except ImportError:
        agents = []
    
    return agents


def get_rl_agent_info(agent_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type d'agent RL.
    
    Args:
        agent_type: Type d'agent
    
    Returns:
        Dict[str, Any]: Informations sur l'agent
    """
    info = {
        'dqn': {
            'name': 'DQN (Deep Q-Network)',
            'description': 'Agent Q-learning avec réseau de neurones',
            'advantages': [
                'Simple à implémenter',
                'Fonctionne bien avec des espaces discrets',
                'Support des mémoires priorisées'
            ],
            'disadvantages': [
                'Ne supporte que les actions discrètes',
                'Peut être instable',
                'Sensible aux hyperparamètres'
            ],
            'use_cases': [
                'Espaces d\'actions discrets',
                'Environnements simples à moyens',
                'Quand l\'exploration est importante'
            ],
            'action_space': 'discrete',
        },
        'ppo': {
            'name': 'PPO (Proximal Policy Optimization)',
            'description': 'Agent politique avec optimisation proximal',
            'advantages': [
                'Robuste et stable',
                'Support des actions continues et discrètes',
                'Bonnes performances générales'
            ],
            'disadvantages': [
                'Plus complexe à implémenter',
                'Nécessite plus de données',
                'Sensible au learning rate'
            ],
            'use_cases': [
                'Environnements complexes',
                'Actions continues',
                'Quand la stabilité est importante'
            ],
            'action_space': 'both',
        },
        'sac': {
            'name': 'SAC (Soft Actor-Critic)',
            'description': 'Agent hors-politique avec entropie maximale',
            'advantages': [
                'Support des actions continues',
                'Exploration efficace',
                'Bonne performance échantillonnage'
            ],
            'disadvantages': [
                'Complexe à implémenter',
                'Nécessite beaucoup de mémoire',
                'Sensible au réglage de l\'entropie'
            ],
            'use_cases': [
                'Environnements continus',
                'Quand l\'exploration est critique',
                'Données complexes'
            ],
            'action_space': 'continuous',
        },
        'td3': {
            'name': 'TD3 (Twin Delayed DDPG)',
            'description': 'Agent hors-politique avec double Q-learning et politique retardée',
            'advantages': [
                'Robuste contre le surapprentissage',
                'Support des actions continues',
                'Meilleur que DDPG'
            ],
            'disadvantages': [
                'Complexe à implémenter',
                'Nécessite beaucoup de données',
                'Sensible au bruit de politique'
            ],
            'use_cases': [
                'Environnements continus',
                'Quand la stabilité est nécessaire',
                'Robustesse contre les erreurs'
            ],
            'action_space': 'continuous',
        }
    }
    
    return info.get(agent_type.lower(), {})


def get_rl_recommendation(
    action_space: str = 'discrete',
    complexity: str = 'medium',
    sample_efficiency: bool = True,
    stability: str = 'balanced'
) -> Dict[str, Any]:
    """
    Recommande un agent RL selon les besoins.
    
    Args:
        action_space: Espace d'actions ('discrete', 'continuous', 'both')
        complexity: Complexité de l'environnement ('simple', 'medium', 'complex')
        sample_efficiency: Priorité de l'efficacité échantillonnage
        stability: Priorité de stabilité ('fast', 'balanced', 'high')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    recommendations = {
        'discrete': {
            'simple': {'agent': 'dqn', 'description': 'DQN pour environnements discrets simples'},
            'medium': {'agent': 'dqn', 'description': 'DQN avec mémoire priorisée'},
            'complex': {'agent': 'ppo', 'description': 'PPO pour environnements complexes discrets'},
        },
        'continuous': {
            'simple': {'agent': 'sac', 'description': 'SAC pour environnements continus simples'},
            'medium': {'agent': 'sac', 'description': 'SAC pour environnements continus moyens'},
            'complex': {'agent': 'td3', 'description': 'TD3 pour environnements continus complexes'},
        },
        'both': {
            'simple': {'agent': 'ppo', 'description': 'PPO pour environnements mixtes'},
            'medium': {'agent': 'ppo', 'description': 'PPO pour environnements mixtes moyens'},
            'complex': {'agent': 'ppo', 'description': 'PPO pour environnements mixtes complexes'},
        }
    }
    
    action_space_lower = action_space.lower()
    if action_space_lower not in recommendations:
        action_space_lower = 'discrete'
    
    complexity_lower = complexity.lower()
    if complexity_lower not in ['simple', 'medium', 'complex']:
        complexity_lower = 'medium'
    
    recommendation = recommendations[action_space_lower][complexity_lower]
    
    # Ajustements selon les priorités
    if sample_efficiency and recommendation['agent'] != 'sac':
        if action_space_lower == 'continuous':
            recommendation['agent'] = 'sac'
            recommendation['description'] = 'SAC pour meilleure efficacité échantillonnage'
    
    if stability == 'high' and recommendation['agent'] == 'dqn':
        recommendation['agent'] = 'ppo'
        recommendation['description'] = 'PPO pour meilleure stabilité'
    
    return {
        'action_space': action_space_lower,
        'complexity': complexity_lower,
        'sample_efficiency': sample_efficiency,
        'stability': stability,
        'recommended_agent': recommendation,
        'alternative_agents': {
            'discrete': ['dqn', 'ppo'],
            'continuous': ['sac', 'td3', 'ppo'],
            'both': ['ppo'],
        }.get(action_space_lower, ['dqn', 'ppo']),
    }


logger.info("Module d'apprentissage par renforcement initialisé")
