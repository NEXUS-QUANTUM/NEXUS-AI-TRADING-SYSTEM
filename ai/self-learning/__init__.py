# ai/self-learning/__init__.py
"""
NEXUS AI TRADING SYSTEM - Self-Learning Module
Copyright © 2026 NEXUS QUANTUM LTD

Module d'auto-apprentissage pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.self-learning.adaptive_learning import (
    AdaptiveLearner,
    AdaptiveLearningConfig,
    AdaptiveState,
    create_adaptive_learner,
)

from ai.self-learning.concept_drift_detector import (
    ConceptDriftDetector,
    ConceptDriftConfig,
    DriftResult,
    create_concept_drift_detector,
)

from ai.self-learning.incremental_learner import (
    IncrementalLearner,
    IncrementalLearnerConfig,
    IncrementalState,
    create_incremental_learner,
)

from ai.self-learning.model_updater import (
    ModelUpdater,
    ModelUpdaterConfig,
    UpdateResult,
    create_model_updater,
)

from ai.self-learning.online_learner import (
    OnlineLearner,
    OnlineLearnerConfig,
    OnlineState,
    create_online_learner,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Adaptive Learning
    'AdaptiveLearner',
    'AdaptiveLearningConfig',
    'AdaptiveState',
    'create_adaptive_learner',
    
    # Concept Drift Detector
    'ConceptDriftDetector',
    'ConceptDriftConfig',
    'DriftResult',
    'create_concept_drift_detector',
    
    # Incremental Learner
    'IncrementalLearner',
    'IncrementalLearnerConfig',
    'IncrementalState',
    'create_incremental_learner',
    
    # Model Updater
    'ModelUpdater',
    'ModelUpdaterConfig',
    'UpdateResult',
    'create_model_updater',
    
    # Online Learner
    'OnlineLearner',
    'OnlineLearnerConfig',
    'OnlineState',
    'create_online_learner',
]


def create_self_learning_system(
    system_type: str = 'incremental',
    **kwargs
) -> Any:
    """
    Factory pour créer des systèmes d'auto-apprentissage.
    
    Args:
        system_type: Type de système ('adaptive', 'incremental', 'online', 'updater', 'drift_detector')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance du système d'auto-apprentissage
    
    Examples:
        ```python
        # Adaptive Learner
        learner = create_self_learning_system(
            'adaptive',
            window_size=100,
            update_frequency=10,
            learning_rate=0.001
        )
        
        # Incremental Learner
        learner = create_self_learning_system(
            'incremental',
            batch_size=32,
            learning_rate=0.001,
            max_samples=10000
        )
        
        # Online Learner
        learner = create_self_learning_system(
            'online',
            learning_rate=0.01,
            forget_factor=0.95
        )
        
        # Model Updater
        updater = create_self_learning_system(
            'updater',
            update_strategy='periodic',
            update_frequency=100
        )
        
        # Concept Drift Detector
        detector = create_self_learning_system(
            'drift_detector',
            method='ddm',
            window_size=100
        )
        ```
    """
    system_type = system_type.lower()
    
    if system_type == 'adaptive':
        window_size = kwargs.get('window_size', 100)
        update_frequency = kwargs.get('update_frequency', 10)
        learning_rate = kwargs.get('learning_rate', 0.001)
        
        return create_adaptive_learner(
            window_size=window_size,
            update_frequency=update_frequency,
            learning_rate=learning_rate,
            **{k: v for k, v in kwargs.items() 
               if k not in ['window_size', 'update_frequency', 'learning_rate']}
        )
    
    elif system_type == 'incremental':
        batch_size = kwargs.get('batch_size', 32)
        learning_rate = kwargs.get('learning_rate', 0.001)
        max_samples = kwargs.get('max_samples', 10000)
        
        return create_incremental_learner(
            batch_size=batch_size,
            learning_rate=learning_rate,
            max_samples=max_samples,
            **{k: v for k, v in kwargs.items() 
               if k not in ['batch_size', 'learning_rate', 'max_samples']}
        )
    
    elif system_type == 'online':
        learning_rate = kwargs.get('learning_rate', 0.01)
        batch_size = kwargs.get('batch_size', 1)
        forget_factor = kwargs.get('forget_factor', 0.95)
        
        return create_online_learner(
            learning_rate=learning_rate,
            batch_size=batch_size,
            forget_factor=forget_factor,
            **{k: v for k, v in kwargs.items() 
               if k not in ['learning_rate', 'batch_size', 'forget_factor']}
        )
    
    elif system_type == 'updater':
        update_strategy = kwargs.get('update_strategy', 'periodic')
        update_frequency = kwargs.get('update_frequency', 100)
        learning_rate = kwargs.get('learning_rate', 0.001)
        
        return create_model_updater(
            update_strategy=update_strategy,
            update_frequency=update_frequency,
            learning_rate=learning_rate,
            **{k: v for k, v in kwargs.items() 
               if k not in ['update_strategy', 'update_frequency', 'learning_rate']}
        )
    
    elif system_type in ['drift_detector', 'drift']:
        method = kwargs.get('method', 'ddm')
        window_size = kwargs.get('window_size', 100)
        detection_threshold = kwargs.get('detection_threshold', 0.05)
        
        return create_concept_drift_detector(
            method=method,
            window_size=window_size,
            detection_threshold=detection_threshold,
            **{k: v for k, v in kwargs.items() 
               if k not in ['method', 'window_size', 'detection_threshold']}
        )
    
    else:
        raise ValueError(f"Type de système d'auto-apprentissage non supporté: {system_type}")


def get_available_self_learning_systems() -> List[str]:
    """
    Retourne la liste des systèmes d'auto-apprentissage disponibles.
    
    Returns:
        List[str]: Liste des types de systèmes
    """
    systems = ['adaptive', 'incremental', 'online', 'updater', 'drift_detector']
    
    try:
        import torch
    except ImportError:
        systems = ['drift_detector']  # Seul le détecteur ne nécessite pas PyTorch
    
    return systems


def get_self_learning_system_info(system_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de système d'auto-apprentissage.
    
    Args:
        system_type: Type de système
    
    Returns:
        Dict[str, Any]: Informations sur le système
    """
    info = {
        'adaptive': {
            'name': 'Adaptive Learner',
            'description': 'Apprentissage adaptatif avec détection de changement',
            'features': [
                'Apprentissage incrémental',
                'Détection de changement de concept',
                'Forgetting adaptatif',
                'Validation en ligne',
                'Early stopping'
            ],
            'use_cases': [
                'Marchés changeants',
                'Données non stationnaires',
                'Systèmes adaptatifs'
            ]
        },
        'incremental': {
            'name': 'Incremental Learner',
            'description': 'Apprentissage incrémental par batch',
            'features': [
                'Apprentissage continu',
                'Mise à jour en ligne',
                'Validation incrémentale',
                'Early stopping',
                'Persistance'
            ],
            'use_cases': [
                'Streaming data',
                'Données en temps réel',
                'Systèmes continus'
            ]
        },
        'online': {
            'name': 'Online Learner',
            'description': 'Apprentissage en temps réel échantillon par échantillon',
            'features': [
                'Apprentissage en temps réel',
                'Mise à jour par échantillon',
                'Forgetting factor',
                'Validation en ligne',
                'Performance tracking'
            ],
            'use_cases': [
                'Trading haute fréquence',
                'Données en streaming',
                'Systèmes temps réel'
            ]
        },
        'updater': {
            'name': 'Model Updater',
            'description': 'Metteur à jour de modèle avec stratégies multiples',
            'features': [
                'Mise à jour incrémentale',
                'Mise à jour périodique',
                'Mise à jour déclenchée',
                'Validation automatique',
                'Historique des versions'
            ],
            'use_cases': [
                'Modèles en production',
                'Maintenance continue',
                'Systèmes évolutifs'
            ]
        },
        'drift_detector': {
            'name': 'Concept Drift Detector',
            'description': 'Détecteur de changement de concept',
            'features': [
                'DDM (Drift Detection Method)',
                'PH (Page-Hinkley)',
                'ADWIN (Adaptive Windowing)',
                'KS Test',
                'Isolation Forest'
            ],
            'use_cases': [
                'Surveillance de modèles',
                'Détection d\'anomalies',
                'Adaptation automatique'
            ]
        }
    }
    
    return info.get(system_type.lower(), {})


def get_self_learning_recommendation(
    data_frequency: str = 'medium',
    concept_drift_probability: str = 'medium',
    adaptation_speed: str = 'medium',
    resources: str = 'medium'
) -> Dict[str, Any]:
    """
    Recommande un système d'auto-apprentissage selon les besoins.
    
    Args:
        data_frequency: Fréquence des données ('low', 'medium', 'high')
        concept_drift_probability: Probabilité de changement ('low', 'medium', 'high')
        adaptation_speed: Vitesse d'adaptation ('slow', 'medium', 'fast')
        resources: Ressources disponibles ('low', 'medium', 'high')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    if concept_drift_probability == 'high':
        return {
            'recommended_system': {
                'type': 'adaptive',
                'description': 'Apprentissage adaptatif pour changements fréquents'
            },
            'alternative_systems': ['drift_detector', 'online'],
            'features': ['Détection de changement', 'Forgetting adaptatif', 'Early stopping']
        }
    
    if data_frequency == 'high':
        return {
            'recommended_system': {
                'type': 'online',
                'description': 'Apprentissage en ligne pour données haute fréquence'
            },
            'alternative_systems': ['incremental', 'adaptive'],
            'features': ['Temps réel', 'Forgetting factor', 'Performance tracking']
        }
    
    if resources == 'low':
        return {
            'recommended_system': {
                'type': 'drift_detector',
                'description': 'Détecteur de drift léger pour ressources limitées'
            },
            'alternative_systems': ['online'],
            'features': ['Léger', 'Efficace', 'Surveillance continue']
        }
    
    if adaptation_speed == 'fast':
        return {
            'recommended_system': {
                'type': 'online',
                'description': 'Apprentissage en ligne pour adaptation rapide'
            },
            'alternative_systems': ['incremental'],
            'features': ['Mise à jour instantanée', 'Réponse rapide']
        }
    
    # Par défaut
    return {
        'recommended_system': {
            'type': 'incremental',
            'description': 'Apprentissage incrémental pour approche équilibrée'
        },
        'alternative_systems': ['adaptive', 'online', 'updater'],
        'features': ['Équilibré', 'Robuste', 'Flexible']
    }


logger.info("Module d'auto-apprentissage initialisé")
