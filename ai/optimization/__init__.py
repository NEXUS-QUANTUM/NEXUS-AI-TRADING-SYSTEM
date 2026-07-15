
# ai/optimization/__init__.py
"""
NEXUS AI TRADING SYSTEM - Optimization Module
Copyright © 2026 NEXUS QUANTUM LTD

Module d'optimisation pour les hyperparamètres et les modèles.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.optimization.bayesian_optimization import (
    BayesianOptimization,
    BayesianOptimizationConfig,
    create_bayesian_optimization,
)

from ai.optimization.genetic_algorithm import (
    GeneticAlgorithm,
    GeneticAlgorithmConfig,
    Individual,
    create_genetic_algorithm,
)

from ai.optimization.grid_search import (
    GridSearch,
    GridSearchConfig,
    GridSearchResult,
    create_grid_search,
)

from ai.optimization.hyperopt import (
    HyperoptOptimizer,
    HyperoptConfig,
    HyperoptResult,
    create_hyperopt_optimizer,
)

from ai.optimization.optuna_optimizer import (
    OptunaOptimizer,
    OptunaConfig,
    OptunaResult,
    create_optuna_optimizer,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Bayesian Optimization
    'BayesianOptimization',
    'BayesianOptimizationConfig',
    'create_bayesian_optimization',
    
    # Genetic Algorithm
    'GeneticAlgorithm',
    'GeneticAlgorithmConfig',
    'Individual',
    'create_genetic_algorithm',
    
    # Grid Search
    'GridSearch',
    'GridSearchConfig',
    'GridSearchResult',
    'create_grid_search',
    
    # Hyperopt
    'HyperoptOptimizer',
    'HyperoptConfig',
    'HyperoptResult',
    'create_hyperopt_optimizer',
    
    # Optuna
    'OptunaOptimizer',
    'OptunaConfig',
    'OptunaResult',
    'create_optuna_optimizer',
]


def create_optimizer(
    optimizer_type: str = 'optuna',
    **kwargs
) -> Any:
    """
    Factory pour créer des optimiseurs d'hyperparamètres.
    
    Args:
        optimizer_type: Type d'optimiseur ('optuna', 'hyperopt', 'bayesian', 'genetic', 'grid')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance de l'optimiseur
    
    Examples:
        ```python
        # Optuna
        optimizer = create_optimizer(
            'optuna',
            n_trials=100,
            direction='minimize',
            sampler='tpe'
        )
        
        # Hyperopt
        optimizer = create_optimizer(
            'hyperopt',
            max_evals=100,
            algorithm='tpe'
        )
        
        # Bayesian Optimization
        optimizer = create_optimizer(
            'bayesian',
            n_iterations=50,
            acquisition_function='ei'
        )
        
        # Genetic Algorithm
        optimizer = create_optimizer(
            'genetic',
            population_size=50,
            n_generations=100
        )
        
        # Grid Search
        optimizer = create_optimizer(
            'grid',
            param_grid={'x1': [1, 2, 3], 'x2': [4, 5, 6]},
            cv=5
        )
        ```
    """
    optimizer_type = optimizer_type.lower()
    
    if optimizer_type == 'optuna':
        n_trials = kwargs.get('n_trials', 100)
        direction = kwargs.get('direction', 'minimize')
        sampler = kwargs.get('sampler', 'tpe')
        pruner = kwargs.get('pruner', 'median')
        
        return create_optuna_optimizer(
            n_trials=n_trials,
            direction=direction,
            sampler=sampler,
            pruner=pruner,
            **{k: v for k, v in kwargs.items() 
               if k not in ['n_trials', 'direction', 'sampler', 'pruner']}
        )
    
    elif optimizer_type == 'hyperopt':
        max_evals = kwargs.get('max_evals', 100)
        algorithm = kwargs.get('algorithm', 'tpe')
        early_stopping = kwargs.get('early_stopping', True)
        patience = kwargs.get('patience', 20)
        
        return create_hyperopt_optimizer(
            max_evals=max_evals,
            algorithm=algorithm,
            early_stopping=early_stopping,
            patience=patience,
            **{k: v for k, v in kwargs.items() 
               if k not in ['max_evals', 'algorithm', 'early_stopping', 'patience']}
        )
    
    elif optimizer_type == 'bayesian':
        n_iterations = kwargs.get('n_iterations', 50)
        n_initial_points = kwargs.get('n_initial_points', 10)
        acquisition_function = kwargs.get('acquisition_function', 'ei')
        
        return create_bayesian_optimization(
            n_iterations=n_iterations,
            n_initial_points=n_initial_points,
            acquisition_function=acquisition_function,
            **{k: v for k, v in kwargs.items() 
               if k not in ['n_iterations', 'n_initial_points', 'acquisition_function']}
        )
    
    elif optimizer_type == 'genetic':
        population_size = kwargs.get('population_size', 50)
        n_generations = kwargs.get('n_generations', 100)
        mutation_rate = kwargs.get('mutation_rate', 0.1)
        crossover_rate = kwargs.get('crossover_rate', 0.8)
        
        return create_genetic_algorithm(
            population_size=population_size,
            n_generations=n_generations,
            mutation_rate=mutation_rate,
            crossover_rate=crossover_rate,
            **{k: v for k, v in kwargs.items() 
               if k not in ['population_size', 'n_generations', 'mutation_rate', 'crossover_rate']}
        )
    
    elif optimizer_type == 'grid':
        param_grid = kwargs.get('param_grid')
        if param_grid is None:
            raise ValueError("param_grid est requis pour grid search")
        
        scoring = kwargs.get('scoring', 'neg_mean_squared_error')
        cv = kwargs.get('cv', 5)
        n_jobs = kwargs.get('n_jobs', -1)
        
        return create_grid_search(
            param_grid=param_grid,
            scoring=scoring,
            cv=cv,
            n_jobs=n_jobs,
            **{k: v for k, v in kwargs.items() 
               if k not in ['param_grid', 'scoring', 'cv', 'n_jobs']}
        )
    
    else:
        raise ValueError(f"Type d'optimiseur non supporté: {optimizer_type}")


def get_available_optimizers() -> List[str]:
    """
    Retourne la liste des optimiseurs disponibles.
    
    Returns:
        List[str]: Liste des types d'optimiseurs
    """
    optimizers = ['optuna', 'hyperopt', 'bayesian', 'genetic', 'grid']
    
    try:
        import optuna
    except ImportError:
        optimizers.remove('optuna') if 'optuna' in optimizers else None
    
    try:
        from hyperopt import fmin
    except ImportError:
        optimizers.remove('hyperopt') if 'hyperopt' in optimizers else None
    
    try:
        import torch
    except ImportError:
        optimizers.remove('bayesian') if 'bayesian' in optimizers else None
    
    return optimizers


def get_optimizer_info(optimizer_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type d'optimiseur.
    
    Args:
        optimizer_type: Type d'optimiseur
    
    Returns:
        Dict[str, Any]: Informations sur l'optimiseur
    """
    info = {
        'optuna': {
            'name': 'Optuna',
            'description': 'Framework d'optimisation avec pruning et visualisation',
            'advantages': [
                'Très complet',
                'Multiples samplers',
                'Pruning intégré',
                'Visualisation avancée'
            ],
            'disadvantages': [
                'Installation lourde',
                'Courbe d\'apprentissage',
                'Peut être lent'
            ],
            'use_cases': [
                'Optimisation de modèles complexes',
                'Grands espaces de recherche',
                'Quand la visualisation est importante'
            ]
        },
        'hyperopt': {
            'name': 'Hyperopt',
            'description': 'Optimisation avec TPE et algorithmes avancés',
            'advantages': [
                'Léger et rapide',
                'TPE efficace',
                'Support des espaces complexes'
            ],
            'disadvantages': [
                'Moins de fonctionnalités',
                'Pas de pruning intégré',
                'Visualisation limitée'
            ],
            'use_cases': [
                'Optimisation rapide',
                'Espaces de recherche simples',
                'Quand la légèreté est importante'
            ]
        },
        'bayesian': {
            'name': 'Bayesian Optimization',
            'description': 'Optimisation avec processus gaussien',
            'advantages': [
                'Efficace pour peu d\'évaluations',
                'Modélisation de l\'incertitude',
                'Bonne exploration/exploitation'
            ],
            'disadvantages': [
                'Nécessite beaucoup de calculs',
                'Scalabilité limitée',
                'Moins adapté aux espaces complexes'
            ],
            'use_cases': [
                'Fonctions coûteuses à évaluer',
                'Petits espaces de recherche',
                'Quand l\'incertitude est importante'
            ]
        },
        'genetic': {
            'name': 'Genetic Algorithm',
            'description': 'Algorithmes génétiques pour l\'optimisation',
            'advantages': [
                'Robuste',
                'Support des contraintes',
                'Bonne exploration'
            ],
            'disadvantages': [
                'Lent',
                'Paramètres à régler',
                'Pas de garantie de convergence'
            ],
            'use_cases': [
                'Espaces de recherche complexes',
                'Optimisation multi-objectifs',
                'Quand la robustesse est importante'
            ]
        },
        'grid': {
            'name': 'Grid Search',
            'description': 'Recherche exhaustive sur une grille',
            'advantages': [
                'Simple et robuste',
                'Répétable',
                'Exhaustif'
            ],
            'disadvantages': [
                'Coûteux en temps',
                'Maudit de la dimensionnalité',
                'Pas adaptatif'
            ],
            'use_cases': [
                'Petits espaces de recherche',
                'Validation de modèles',
                'Quand la reproductibilité est importante'
            ]
        }
    }
    
    return info.get(optimizer_type.lower(), {})


def get_optimizer_recommendation(
    search_space_size: str = 'medium',
    eval_cost: str = 'medium',
    time_budget: str = 'medium',
    reproducibility: bool = False
) -> Dict[str, Any]:
    """
    Recommande un optimiseur selon les besoins.
    
    Args:
        search_space_size: Taille de l'espace ('small', 'medium', 'large')
        eval_cost: Coût de l'évaluation ('low', 'medium', 'high')
        time_budget: Budget temps ('short', 'medium', 'long')
        reproducibility: Importance de la reproductibilité
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    recommendations = {
        'small': {
            'low': {
                'short': {'optimizer': 'grid', 'description': 'Grid Search rapide pour petits espaces'},
                'medium': {'optimizer': 'bayesian', 'description': 'Bayesian pour équilibre'},
                'long': {'optimizer': 'optuna', 'description': 'Optuna pour optimisation complète'},
            },
            'medium': {
                'short': {'optimizer': 'hyperopt', 'description': 'Hyperopt rapide pour espaces moyens'},
                'medium': {'optimizer': 'bayesian', 'description': 'Bayesian pour équilibre'},
                'long': {'optimizer': 'optuna', 'description': 'Optuna pour optimisation complète'},
            },
            'high': {
                'short': {'optimizer': 'bayesian', 'description': 'Bayesian efficace pour évaluations coûteuses'},
                'medium': {'optimizer': 'bayesian', 'description': 'Bayesian pour équilibre'},
                'long': {'optimizer': 'genetic', 'description': 'Genetic pour exploration profonde'},
            }
        },
        'medium': {
            'low': {
                'short': {'optimizer': 'hyperopt', 'description': 'Hyperopt rapide pour espaces moyens'},
                'medium': {'optimizer': 'optuna', 'description': 'Optuna pour équilibre'},
                'long': {'optimizer': 'optuna', 'description': 'Optuna pour optimisation complète'},
            },
            'medium': {
                'short': {'optimizer': 'hyperopt', 'description': 'Hyperopt pour équilibre'},
                'medium': {'optimizer': 'optuna', 'description': 'Optuna pour équilibre'},
                'long': {'optimizer': 'optuna', 'description': 'Optuna pour optimisation complète'},
            },
            'high': {
                'short': {'optimizer': 'bayesian', 'description': 'Bayesian efficace pour évaluations coûteuses'},
                'medium': {'optimizer': 'genetic', 'description': 'Genetic pour exploration'},
                'long': {'optimizer': 'genetic', 'description': 'Genetic pour optimisation profonde'},
            }
        },
        'large': {
            'low': {
                'short': {'optimizer': 'hyperopt', 'description': 'Hyperopt rapide pour grands espaces'},
                'medium': {'optimizer': 'optuna', 'description': 'Optuna pour équilibre'},
                'long': {'optimizer': 'optuna', 'description': 'Optuna pour optimisation complète'},
            },
            'medium': {
                'short': {'optimizer': 'hyperopt', 'description': 'Hyperopt pour équilibre'},
                'medium': {'optimizer': 'optuna', 'description': 'Optuna pour équilibre'},
                'long': {'optimizer': 'optuna', 'description': 'Optuna pour optimisation complète'},
            },
            'high': {
                'short': {'optimizer': 'genetic', 'description': 'Genetic pour grands espaces'},
                'medium': {'optimizer': 'genetic', 'description': 'Genetic pour exploration'},
                'long': {'optimizer': 'genetic', 'description': 'Genetic pour optimisation profonde'},
            }
        }
    }
    
    space_size = search_space_size.lower()
    if space_size not in ['small', 'medium', 'large']:
        space_size = 'medium'
    
    eval_cost_lower = eval_cost.lower()
    if eval_cost_lower not in ['low', 'medium', 'high']:
        eval_cost_lower = 'medium'
    
    time_budget_lower = time_budget.lower()
    if time_budget_lower not in ['short', 'medium', 'long']:
        time_budget_lower = 'medium'
    
    recommendation = recommendations[space_size][eval_cost_lower][time_budget_lower]
    
    # Ajustement pour la reproductibilité
    if reproducibility and recommendation['optimizer'] != 'grid':
        if recommendation['optimizer'] in ['bayesian', 'genetic']:
            recommendation['optimizer'] = 'grid'
            recommendation['description'] = 'Grid Search pour reproductibilité'
    
    return {
        'search_space_size': space_size,
        'eval_cost': eval_cost_lower,
        'time_budget': time_budget_lower,
        'reproducibility': reproducibility,
        'recommended_optimizer': recommendation,
        'alternative_optimizers': ['optuna', 'hyperopt', 'bayesian', 'genetic', 'grid'],
    }


logger.info("Module d'optimisation initialisé")
