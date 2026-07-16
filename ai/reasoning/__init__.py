# ai/reasoning/__init__.py
"""
NEXUS AI TRADING SYSTEM - Reasoning Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de raisonnement pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.reasoning.inference_engine import (
    InferenceEngine,
    InferenceRule,
    InferenceResult,
    create_inference_engine,
)

from ai.reasoning.logic_engine import (
    LogicEngine,
    LogicalExpression,
    LogicalRule,
    LogicResult,
    create_logic_engine,
)

from ai.reasoning.probabilistic_reasoning import (
    ProbabilisticReasoning,
    ProbabilisticNode,
    BayesianNetwork,
    InferenceResult as ProbabilisticInferenceResult,
    create_probabilistic_engine,
)

from ai.reasoning.rule_based_system import (
    RuleBasedSystem,
    Rule,
    RuleResult,
    create_rule_system,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Inference Engine
    'InferenceEngine',
    'InferenceRule',
    'InferenceResult',
    'create_inference_engine',
    
    # Logic Engine
    'LogicEngine',
    'LogicalExpression',
    'LogicalRule',
    'LogicResult',
    'create_logic_engine',
    
    # Probabilistic Reasoning
    'ProbabilisticReasoning',
    'ProbabilisticNode',
    'BayesianNetwork',
    'ProbabilisticInferenceResult',
    'create_probabilistic_engine',
    
    # Rule-Based System
    'RuleBasedSystem',
    'Rule',
    'RuleResult',
    'create_rule_system',
]


def create_reasoning_system(
    system_type: str = 'rule_based',
    **kwargs
) -> Any:
    """
    Factory pour créer des systèmes de raisonnement.
    
    Args:
        system_type: Type de système ('inference', 'logic', 'probabilistic', 'rule_based')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance du système de raisonnement
    
    Examples:
        ```python
        # Inference Engine
        engine = create_reasoning_system(
            'inference',
            confidence_threshold=0.5,
            max_rules=100
        )
        
        # Logic Engine
        engine = create_reasoning_system(
            'logic',
            confidence_threshold=0.5
        )
        
        # Probabilistic Reasoning
        engine = create_reasoning_system(
            'probabilistic',
            sampling_method='rejection',
            n_samples=10000
        )
        
        # Rule-Based System
        system = create_reasoning_system(
            'rule_based',
            conflict_resolution='priority',
            confidence_threshold=0.5
        )
        ```
    """
    system_type = system_type.lower()
    
    if system_type == 'inference':
        confidence_threshold = kwargs.get('confidence_threshold', 0.5)
        max_rules = kwargs.get('max_rules', 100)
        
        return create_inference_engine(
            confidence_threshold=confidence_threshold,
            max_rules=max_rules,
            **{k: v for k, v in kwargs.items() 
               if k not in ['confidence_threshold', 'max_rules']}
        )
    
    elif system_type == 'logic':
        confidence_threshold = kwargs.get('confidence_threshold', 0.5)
        max_rules = kwargs.get('max_rules', 100)
        
        return create_logic_engine(
            confidence_threshold=confidence_threshold,
            max_rules=max_rules,
            **{k: v for k, v in kwargs.items() 
               if k not in ['confidence_threshold', 'max_rules']}
        )
    
    elif system_type == 'probabilistic':
        sampling_method = kwargs.get('sampling_method', 'rejection')
        n_samples = kwargs.get('n_samples', 10000)
        
        return create_probabilistic_engine(
            sampling_method=sampling_method,
            n_samples=n_samples,
            **{k: v for k, v in kwargs.items() 
               if k not in ['sampling_method', 'n_samples']}
        )
    
    elif system_type == 'rule_based':
        conflict_resolution = kwargs.get('conflict_resolution', 'priority')
        confidence_threshold = kwargs.get('confidence_threshold', 0.5)
        
        return create_rule_system(
            conflict_resolution=conflict_resolution,
            confidence_threshold=confidence_threshold,
            **{k: v for k, v in kwargs.items() 
               if k not in ['conflict_resolution', 'confidence_threshold']}
        )
    
    else:
        raise ValueError(f"Type de système de raisonnement non supporté: {system_type}")


def get_available_reasoning_systems() -> List[str]:
    """
    Retourne la liste des systèmes de raisonnement disponibles.
    
    Returns:
        List[str]: Liste des types de systèmes
    """
    return ['inference', 'logic', 'probabilistic', 'rule_based']


def get_reasoning_system_info(system_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de système de raisonnement.
    
    Args:
        system_type: Type de système
    
    Returns:
        Dict[str, Any]: Informations sur le système
    """
    info = {
        'inference': {
            'name': 'Inference Engine',
            'description': 'Moteur d\'inférence basé sur des règles',
            'features': [
                'Rule-based reasoning',
                'Forward chaining',
                'Backward chaining',
                'Uncertainty handling',
                'Explanation generation'
            ],
            'use_cases': [
                'Diagnostic',
                'Decision support',
                'Expert systems'
            ]
        },
        'logic': {
            'name': 'Logic Engine',
            'description': 'Moteur logique pour le raisonnement déductif',
            'features': [
                'Logical expressions',
                'Conditional rules',
                'Logical deduction',
                'Uncertainty management',
                'Explanations'
            ],
            'use_cases': [
                'Deductive reasoning',
                'Logical inference',
                'Knowledge validation'
            ]
        },
        'probabilistic': {
            'name': 'Probabilistic Reasoning',
            'description': 'Raisonnement probabiliste avec réseaux bayésiens',
            'features': [
                'Bayesian networks',
                'Belief propagation',
                'Variable elimination',
                'Monte Carlo sampling',
                'Evidence integration'
            ],
            'use_cases': [
                'Uncertainty modeling',
                'Risk assessment',
                'Prediction under uncertainty'
            ]
        },
        'rule_based': {
            'name': 'Rule-Based System',
            'description': 'Système basé sur des règles conditionnelles',
            'features': [
                'Conditional rules',
                'Forward/backward chaining',
                'Conflict resolution',
                'Uncertainty management',
                'Explanations'
            ],
            'use_cases': [
                'Expert systems',
                'Decision support',
                'Automated reasoning'
            ]
        }
    }
    
    return info.get(system_type.lower(), {})


def get_reasoning_recommendation(
    problem_type: str = 'decision_support',
    uncertainty_level: str = 'medium',
    interpretability: bool = True,
    complexity: str = 'medium'
) -> Dict[str, Any]:
    """
    Recommande un système de raisonnement selon les besoins.
    
    Args:
        problem_type: Type de problème ('decision_support', 'diagnostic', 'prediction', 'validation')
        uncertainty_level: Niveau d'incertitude ('low', 'medium', 'high')
        interpretability: Nécessité d'interprétabilité
        complexity: Complexité ('simple', 'medium', 'complex')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    if uncertainty_level == 'high':
        return {
            'recommended_system': {
                'type': 'probabilistic',
                'description': 'Raisonnement probabiliste pour gérer l\'incertitude élevée'
            },
            'alternative_systems': ['inference', 'logic'],
            'features': ['Bayesian networks', 'Monte Carlo sampling', 'Evidence integration']
        }
    
    if interpretability and problem_type == 'decision_support':
        return {
            'recommended_system': {
                'type': 'rule_based',
                'description': 'Système de règles pour des décisions interprétables'
            },
            'alternative_systems': ['logic', 'inference'],
            'features': ['Explicit rules', 'Explanations', 'Conflict resolution']
        }
    
    if problem_type == 'diagnostic':
        return {
            'recommended_system': {
                'type': 'inference',
                'description': 'Moteur d\'inférence pour le diagnostic'
            },
            'alternative_systems': ['rule_based', 'logic'],
            'features': ['Forward chaining', 'Backward chaining', 'Rule-based reasoning']
        }
    
    if problem_type == 'validation':
        return {
            'recommended_system': {
                'type': 'logic',
                'description': 'Moteur logique pour la validation'
            },
            'alternative_systems': ['inference'],
            'features': ['Logical expressions', 'Deduction', 'Consistency checking']
        }
    
    # Par défaut
    if complexity == 'simple':
        return {
            'recommended_system': {
                'type': 'rule_based',
                'description': 'Système de règles simple pour des cas faciles'
            },
            'alternative_systems': ['logic', 'inference'],
            'features': ['Simple rules', 'Fast execution', 'Easy to understand']
        }
    
    return {
        'recommended_system': {
            'type': 'inference',
            'description': 'Moteur d\'inférence pour une approche équilibrée'
        },
        'alternative_systems': ['rule_based', 'logic', 'probabilistic'],
        'features': ['Flexible reasoning', 'Multiple strategies', 'Explanation support']
    }


logger.info("Module de raisonnement initialisé")
