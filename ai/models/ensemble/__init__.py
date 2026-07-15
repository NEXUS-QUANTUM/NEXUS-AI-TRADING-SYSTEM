```python
# ai/models/ensemble/__init__.py
"""
NEXUS AI TRADING SYSTEM - Ensemble Models Module
Copyright © 2026 NEXUS QUANTUM LTD

Module d'ensembles de modèles pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.models.ensemble.bagging_ensemble import (
    BaggingEnsemble,
    BaggingConfig,
    BaggingResult,
    create_ensemble_from_config,
    create_ensemble_from_args,
)

from ai.models.ensemble.voting_ensemble import (
    VotingEnsemble,
    VotingConfig,
    VotingResult,
    create_voting_ensemble,
)

from ai.models.ensemble.stacking_ensemble import (
    StackingEnsemble,
    StackingConfig,
    StackingResult,
    create_stacking_ensemble,
)

from ai.models.ensemble.weighting_strategies import (
    WeightingStrategy,
    EqualWeighting,
    PerformanceWeighting,
    RankWeighting,
    ErrorWeighting,
    CorrelationWeighting,
    SharpeWeighting,
    BayesianWeighting,
    DiversityWeighting,
    OnlineWeighting,
    EnsembleWeightingOptimizer,
    WeightingResult,
    create_weighting_strategy,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Bagging
    'BaggingEnsemble',
    'BaggingConfig',
    'BaggingResult',
    'create_ensemble_from_config',
    'create_ensemble_from_args',
    
    # Voting
    'VotingEnsemble',
    'VotingConfig',
    'VotingResult',
    'create_voting_ensemble',
    
    # Stacking
    'StackingEnsemble',
    'StackingConfig',
    'StackingResult',
    'create_stacking_ensemble',
    
    # Weighting Strategies
    'WeightingStrategy',
    'EqualWeighting',
    'PerformanceWeighting',
    'RankWeighting',
    'ErrorWeighting',
    'CorrelationWeighting',
    'SharpeWeighting',
    'BayesianWeighting',
    'DiversityWeighting',
    'OnlineWeighting',
    'EnsembleWeightingOptimizer',
    'WeightingResult',
    'create_weighting_strategy',
]


def create_ensemble(
    ensemble_type: str = 'bagging',
    **kwargs
) -> Any:
    """
    Factory pour créer des ensembles de modèles.
    
    Args:
        ensemble_type: Type d'ensemble ('bagging', 'voting', 'stacking')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance de l'ensemble
    
    Examples:
        ```python
        # Création d'un ensemble Bagging
        ensemble = create_ensemble(
            'bagging',
            n_estimators=50,
            base_model='xgboost',
            aggregation='weighted'
        )
        
        # Création d'un ensemble Voting
        ensemble = create_ensemble(
            'voting',
            model_types=['xgboost', 'lightgbm', 'random_forest'],
            voting='weighted'
        )
        
        # Création d'un ensemble Stacking
        ensemble = create_ensemble(
            'stacking',
            base_model_types=['decision_tree', 'random_forest', 'xgboost'],
            meta_model_type='linear',
            cv_folds=5
        )
        ```
    """
    ensemble_type = ensemble_type.lower()
    
    if ensemble_type == 'bagging':
        n_estimators = kwargs.get('n_estimators', 10)
        base_model = kwargs.get('base_model', 'decision_tree')
        aggregation = kwargs.get('aggregation', 'mean')
        max_samples = kwargs.get('max_samples', 0.8)
        max_features = kwargs.get('max_features', 0.7)
        bootstrap = kwargs.get('bootstrap', True)
        n_jobs = kwargs.get('n_jobs', -1)
        random_state = kwargs.get('random_state', 42)
        
        return create_ensemble_from_args(
            n_estimators=n_estimators,
            base_model=base_model,
            aggregation=aggregation,
            max_samples=max_samples,
            max_features=max_features,
            bootstrap=bootstrap,
            n_jobs=n_jobs,
            random_state=random_state,
            **{k: v for k, v in kwargs.items() 
               if k not in ['n_estimators', 'base_model', 'aggregation', 
                           'max_samples', 'max_features', 'bootstrap', 
                           'n_jobs', 'random_state']}
        )
    
    elif ensemble_type == 'voting':
        model_types = kwargs.get('model_types', ['decision_tree', 'xgboost'])
        voting = kwargs.get('voting', 'hard')
        weights = kwargs.get('weights', None)
        use_proba = kwargs.get('use_proba', False)
        n_jobs = kwargs.get('n_jobs', -1)
        random_state = kwargs.get('random_state', 42)
        
        return create_voting_ensemble(
            model_types=model_types,
            voting=voting,
            weights=weights,
            use_proba=use_proba,
            n_jobs=n_jobs,
            random_state=random_state,
            **{k: v for k, v in kwargs.items() 
               if k not in ['model_types', 'voting', 'weights', 
                           'use_proba', 'n_jobs', 'random_state']}
        )
    
    elif ensemble_type == 'stacking':
        base_model_types = kwargs.get('base_model_types', ['decision_tree', 'random_forest'])
        meta_model_type = kwargs.get('meta_model_type', 'linear')
        cv_folds = kwargs.get('cv_folds', 5)
        use_proba = kwargs.get('use_proba', False)
        n_jobs = kwargs.get('n_jobs', -1)
        random_state = kwargs.get('random_state', 42)
        
        return create_stacking_ensemble(
            base_model_types=base_model_types,
            meta_model_type=meta_model_type,
            cv_folds=cv_folds,
            use_proba=use_proba,
            n_jobs=n_jobs,
            random_state=random_state,
            **{k: v for k, v in kwargs.items() 
               if k not in ['base_model_types', 'meta_model_type', 'cv_folds',
                           'use_proba', 'n_jobs', 'random_state']}
        )
    
    else:
        raise ValueError(f"Type d'ensemble non supporté: {ensemble_type}")


def get_available_ensembles() -> List[str]:
    """
    Retourne la liste des types d'ensembles disponibles.
    
    Returns:
        List[str]: Liste des types d'ensembles
    """
    return ['bagging', 'voting', 'stacking']


def get_available_weighting_strategies() -> List[str]:
    """
    Retourne la liste des stratégies de pondération disponibles.
    
    Returns:
        List[str]: Liste des stratégies de pondération
    """
    return [
        'equal',
        'performance',
        'rank',
        'error',
        'correlation',
        'sharpe',
        'bayesian',
        'diversity',
        'online'
    ]


def get_available_base_models() -> List[str]:
    """
    Retourne la liste des modèles de base disponibles.
    
    Returns:
        List[str]: Liste des modèles de base
    """
    models = ['linear', 'decision_tree', 'random_forest', 'svm', 'knn']
    
    try:
        import xgboost
        models.append('xgboost')
    except ImportError:
        pass
    
    try:
        import lightgbm
        models.append('lightgbm')
    except ImportError:
        pass
    
    try:
        import torch
        models.append('torch')
    except ImportError:
        pass
    
    return models


def get_ensemble_info(ensemble_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type d'ensemble.
    
    Args:
        ensemble_type: Type d'ensemble
    
    Returns:
        Dict[str, Any]: Informations sur l'ensemble
    """
    info = {
        'bagging': {
            'name': 'Bagging Ensemble',
            'description': 'Bootstrap Aggregating pour réduire la variance',
            'advantages': [
                'Réduit le surapprentissage',
                'Robuste aux outliers',
                'Parallélisable'
            ],
            'disadvantages': [
                'Peut être coûteux en mémoire',
                'Moins interprétable'
            ],
            'use_cases': [
                'Données bruitées',
                'Petits jeux de données',
                'Quand la variance est élevée'
            ]
        },
        'voting': {
            'name': 'Voting Ensemble',
            'description': 'Combine les prédictions par vote (hard/soft)',
            'advantages': [
                'Simple à implémenter',
                'Fonctionne bien avec des modèles diversifiés',
                'Interprétable'
            ],
            'disadvantages': [
                'Nécessite des modèles diversifiés',
                'Peut être moins performant que stacking'
            ],
            'use_cases': [
                'Classification',
                'Quand les modèles sont complémentaires',
                'Pour des prédictions rapides'
            ]
        },
        'stacking': {
            'name': 'Stacking Ensemble',
            'description': 'Empilement de modèles avec un méta-modèle',
            'advantages': [
                'Peut capturer des relations complexes',
                'Souvent le plus performant',
                'Flexible'
            ],
            'disadvantages': [
                'Plus complexe à entraîner',
                'Risque de surapprentissage',
                'Plus long à entraîner'
            ],
            'use_cases': [
                'Données complexes',
                'Quand la performance est prioritaire',
                'Données de grande taille'
            ]
        }
    }
    
    return info.get(ensemble_type.lower(), {})


logger.info("Module d'ensembles de modèles initialisé")
