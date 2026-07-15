
# ai/reinforcement/policies/__init__.py
"""
NEXUS AI TRADING SYSTEM - Reinforcement Learning Policies Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de politiques pour l'apprentissage par renforcement.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.reinforcement.policies.categorical_policy import (
    CategoricalPolicy,
    CategoricalPolicyConfig,
    create_categorical_policy,
)

from ai.reinforcement.policies.deterministic_policy import (
    DeterministicPolicy,
    DeterministicPolicyConfig,
    create_deterministic_policy,
)

from ai.reinforcement.policies.gaussian_policy import (
    GaussianPolicy,
    GaussianPolicyConfig,
    create_gaussian_policy,
)

from ai.reinforcement.policies.stochastic_policy import (
    StochasticPolicy,
    StochasticPolicyConfig,
    create_stochastic_policy,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Categorical Policy
    'CategoricalPolicy',
    'CategoricalPolicyConfig',
    'create_categorical_policy',
    
    # Deterministic Policy
    'DeterministicPolicy',
    'DeterministicPolicyConfig',
    'create_deterministic_policy',
    
    # Gaussian Policy
    'GaussianPolicy',
    'GaussianPolicyConfig',
    'create_gaussian_policy',
    
    # Stochastic Policy
    'StochasticPolicy',
    'StochasticPolicyConfig',
    'create_stochastic_policy',
]


def create_policy(
    policy_type: str = 'categorical',
    **kwargs
) -> Any:
    """
    Factory pour créer des politiques RL.
    
    Args:
        policy_type: Type de politique ('categorical', 'deterministic', 'gaussian', 'stochastic')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance de la politique
    
    Examples:
        ```python
        # Categorical Policy (discrete actions)
        policy = create_policy(
            'categorical',
            state_dim=10,
            action_dim=3,
            temperature=1.0
        )
        
        # Deterministic Policy (continuous actions)
        policy = create_policy(
            'deterministic',
            state_dim=10,
            action_dim=3,
            max_action=1.0
        )
        
        # Gaussian Policy (continuous actions with stochasticity)
        policy = create_policy(
            'gaussian',
            state_dim=10,
            action_dim=3,
            use_state_dependent_std=True
        )
        
        # Stochastic Policy (discrete or continuous)
        policy = create_policy(
            'stochastic',
            state_dim=10,
            action_dim=3,
            policy_type='gaussian'
        )
        ```
    """
    policy_type = policy_type.lower()
    
    if policy_type == 'categorical':
        state_dim = kwargs.get('state_dim', 10)
        action_dim = kwargs.get('action_dim', 3)
        hidden_dim = kwargs.get('hidden_dim', 256)
        temperature = kwargs.get('temperature', 1.0)
        
        return create_categorical_policy(
            state_dim=state_dim,
            action_dim=action_dim,
            hidden_dim=hidden_dim,
            temperature=temperature,
            **{k: v for k, v in kwargs.items() 
               if k not in ['state_dim', 'action_dim', 'hidden_dim', 'temperature']}
        )
    
    elif policy_type == 'deterministic':
        state_dim = kwargs.get('state_dim', 10)
        action_dim = kwargs.get('action_dim', 3)
        hidden_dim = kwargs.get('hidden_dim', 256)
        max_action = kwargs.get('max_action', 1.0)
        
        return create_deterministic_policy(
            state_dim=state_dim,
            action_dim=action_dim,
            hidden_dim=hidden_dim,
            max_action=max_action,
            **{k: v for k, v in kwargs.items() 
               if k not in ['state_dim', 'action_dim', 'hidden_dim', 'max_action']}
        )
    
    elif policy_type == 'gaussian':
        state_dim = kwargs.get('state_dim', 10)
        action_dim = kwargs.get('action_dim', 3)
        hidden_dim = kwargs.get('hidden_dim', 256)
        max_action = kwargs.get('max_action', 1.0)
        
        return create_gaussian_policy(
            state_dim=state_dim,
            action_dim=action_dim,
            hidden_dim=hidden_dim,
            max_action=max_action,
            **{k: v for k, v in kwargs.items() 
               if k not in ['state_dim', 'action_dim', 'hidden_dim', 'max_action']}
        )
    
    elif policy_type == 'stochastic':
        state_dim = kwargs.get('state_dim', 10)
        action_dim = kwargs.get('action_dim', 3)
        hidden_dim = kwargs.get('hidden_dim', 256)
        policy_subtype = kwargs.get('policy_subtype', 'categorical')
        temperature = kwargs.get('temperature', 1.0)
        
        return create_stochastic_policy(
            state_dim=state_dim,
            action_dim=action_dim,
            policy_type=policy_subtype,
            temperature=temperature,
            **{k: v for k, v in kwargs.items() 
               if k not in ['state_dim', 'action_dim', 'hidden_dim', 'policy_subtype', 'temperature']}
        )
    
    else:
        raise ValueError(f"Type de politique non supporté: {policy_type}")


def get_available_policies() -> List[str]:
    """
    Retourne la liste des politiques disponibles.
    
    Returns:
        List[str]: Liste des types de politiques
    """
    policies = ['categorical', 'deterministic', 'gaussian', 'stochastic']
    
    try:
        import torch
    except ImportError:
        policies = []
    
    return policies


def get_policy_info(policy_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de politique.
    
    Args:
        policy_type: Type de politique
    
    Returns:
        Dict[str, Any]: Informations sur la politique
    """
    info = {
        'categorical': {
            'name': 'Categorical Policy',
            'description': 'Politique catégorielle pour actions discrètes',
            'action_space': 'Discrete',
            'features': [
                'Softmax distribution',
                'Temperature scaling',
                'Entropy bonus',
                'Exploration control'
            ],
            'use_cases': ['Espaces d\'actions discrets', 'Classification', 'MCTS']
        },
        'deterministic': {
            'name': 'Deterministic Policy',
            'description': 'Politique déterministe pour actions continues',
            'action_space': 'Continuous',
            'features': [
                'Action scaling',
                'Layer normalization',
                'Batch normalization',
                'Multiple activations'
            ],
            'use_cases': ['Espaces d\'actions continus', 'DDPG', 'TD3']
        },
        'gaussian': {
            'name': 'Gaussian Policy',
            'description': 'Politique gaussienne avec écart-type appris',
            'action_space': 'Continuous',
            'features': [
                'Gaussian distribution',
                'State-dependent std',
                'Tanh action scaling',
                'Log-prob correction'
            ],
            'use_cases': ['Espaces d\'actions continus', 'SAC', 'PPO']
        },
        'stochastic': {
            'name': 'Stochastic Policy',
            'description': 'Politique stochastique polyvalente',
            'action_space': 'Discrete ou Continuous',
            'features': [
                'Multiple policy types',
                'Stochastic sampling',
                'Entropy computation',
                'Temperature scaling'
            ],
            'use_cases': ['Espaces d\'actions mixtes', 'A2C', 'PPO']
        }
    }
    
    return info.get(policy_type.lower(), {})


def get_policy_recommendation(
    action_space: str = 'discrete',
    stochastic: bool = True,
    deterministic_eval: bool = True,
    complexity: str = 'medium'
) -> Dict[str, Any]:
    """
    Recommande une politique selon les besoins.
    
    Args:
        action_space: Espace d'actions ('discrete', 'continuous')
        stochastic: Politique stochastique
        deterministic_eval: Évaluation déterministe
        complexity: Complexité ('simple', 'medium', 'complex')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    if action_space == 'discrete':
        if stochastic:
            return {
                'recommended_policy': {
                    'type': 'categorical',
                    'description': 'Politique catégorielle pour actions discrètes stochastiques'
                },
                'alternative_policies': ['stochastic'],
                'features': ['Softmax', 'Temperature', 'Entropy']
            }
        else:
            return {
                'recommended_policy': {
                    'type': 'categorical',
                    'description': 'Politique catégorielle pour actions discrètes déterministes'
                },
                'alternative_policies': [],
                'features': ['Softmax', 'Deterministic evaluation']
            }
    
    if action_space == 'continuous':
        if complexity == 'simple':
            return {
                'recommended_policy': {
                    'type': 'deterministic',
                    'description': 'Politique déterministe pour actions continues simples'
                },
                'alternative_policies': ['gaussian'],
                'features': ['Deterministic', 'Action scaling']
            }
        elif complexity == 'medium':
            return {
                'recommended_policy': {
                    'type': 'gaussian',
                    'description': 'Politique gaussienne pour actions continues moyennes'
                },
                'alternative_policies': ['stochastic', 'deterministic'],
                'features': ['Gaussian distribution', 'State-dependent std']
            }
        else:  # complex
            return {
                'recommended_policy': {
                    'type': 'gaussian',
                    'description': 'Politique gaussienne avancée pour actions continues complexes'
                },
                'alternative_policies': ['stochastic'],
                'features': ['Tanh scaling', 'Log-prob correction', 'Entropy']
            }
    
    # Par défaut
    return {
        'recommended_policy': {
            'type': 'categorical',
            'description': 'Politique catégorielle par défaut'
        },
        'alternative_policies': ['stochastic', 'gaussian'],
        'features': ['Softmax', 'Temperature', 'Entropy']
    }


logger.info("Module de politiques RL initialisé")
