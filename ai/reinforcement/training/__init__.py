# ai/reinforcement/training/__init__.py
"""
NEXUS AI TRADING SYSTEM - Reinforcement Learning Training Module
Copyright © 2026 NEXUS QUANTUM LTD

Module d'entraînement pour l'apprentissage par renforcement.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.reinforcement.training.checkpoint import (
    CheckpointManager,
    CheckpointConfig,
    Checkpoint,
    create_checkpoint_manager,
)

from ai.reinforcement.training.evaluator import (
    Evaluator,
    EvaluatorConfig,
    EvaluationResult,
    create_evaluator,
)

from ai.reinforcement.training.logger import (
    TrainingLogger,
    LoggerConfig,
    create_training_logger,
)

from ai.reinforcement.training.trainer import (
    Trainer,
    TrainerConfig,
    create_trainer,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Checkpoint
    'CheckpointManager',
    'CheckpointConfig',
    'Checkpoint',
    'create_checkpoint_manager',
    
    # Evaluator
    'Evaluator',
    'EvaluatorConfig',
    'EvaluationResult',
    'create_evaluator',
    
    # Logger
    'TrainingLogger',
    'LoggerConfig',
    'create_training_logger',
    
    # Trainer
    'Trainer',
    'TrainerConfig',
    'create_trainer',
]


def create_training_pipeline(
    agent: Any,
    train_env: Any,
    eval_env: Optional[Any] = None,
    n_episodes: int = 1000,
    eval_frequency: int = 50,
    save_frequency: int = 100,
    **kwargs
) -> Trainer:
    """
    Factory pour créer un pipeline d'entraînement complet.
    
    Args:
        agent: Agent à entraîner
        train_env: Environnement d'entraînement
        eval_env: Environnement d'évaluation (optionnel)
        n_episodes: Nombre d'épisodes
        eval_frequency: Fréquence d'évaluation
        save_frequency: Fréquence de sauvegarde
        **kwargs: Arguments supplémentaires
    
    Returns:
        Trainer: Entraîneur configuré
    
    Examples:
        ```python
        # Création du pipeline
        trainer = create_training_pipeline(
            agent=agent,
            train_env=env,
            eval_env=eval_env,
            n_episodes=1000,
            eval_frequency=50,
            save_frequency=100
        )
        
        # Entraînement
        history = trainer.train()
        
        # Visualisation
        trainer.plot_results()
        ```
    """
    config = TrainerConfig(
        n_episodes=n_episodes,
        eval_frequency=eval_frequency,
        save_frequency=save_frequency,
        **kwargs
    )
    
    trainer = Trainer(config)
    trainer.agent = agent
    trainer.train_env = train_env
    trainer.eval_env = eval_env
    
    return trainer


def get_available_training_components() -> Dict[str, List[str]]:
    """
    Retourne la liste des composants d'entraînement disponibles.
    
    Returns:
        Dict[str, List[str]]: Composants par catégorie
    """
    return {
        'checkpoint': ['CheckpointManager', 'CheckpointConfig', 'Checkpoint'],
        'evaluator': ['Evaluator', 'EvaluatorConfig', 'EvaluationResult'],
        'logger': ['TrainingLogger', 'LoggerConfig'],
        'trainer': ['Trainer', 'TrainerConfig'],
    }


def get_training_component_info(component_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un composant d'entraînement.
    
    Args:
        component_type: Type de composant
    
    Returns:
        Dict[str, Any]: Informations sur le composant
    """
    info = {
        'checkpoint': {
            'name': 'Checkpoint Manager',
            'description': 'Gestionnaire de checkpoints pour sauvegarde et reprise',
            'features': [
                'Sauvegarde automatique',
                'Conservation des meilleurs modèles',
                'Rotation des checkpoints',
                'Chargement automatique'
            ],
            'parameters': ['checkpoint_dir', 'max_checkpoints', 'save_best_only', 'save_frequency']
        },
        'evaluator': {
            'name': 'Evaluator',
            'description': 'Évaluateur de performance des agents',
            'features': [
                'Évaluation périodique',
                'Métriques de performance',
                'Visualisation',
                'Sauvegarde des résultats'
            ],
            'parameters': ['evaluation_episodes', 'evaluation_frequency', 'render_eval', 'save_results']
        },
        'logger': {
            'name': 'Training Logger',
            'description': 'Logger pour l\'entraînement',
            'features': [
                'Logging des métriques',
                'Sauvegarde des graphiques',
                'Support TensorBoard',
                'Support Weights & Biases'
            ],
            'parameters': ['log_dir', 'save_metrics', 'save_plots', 'log_frequency']
        },
        'trainer': {
            'name': 'Trainer',
            'description': 'Entraîneur complet pour RL',
            'features': [
                'Boucle d\'entraînement',
                'Évaluation périodique',
                'Checkpoints',
                'Logging',
                'Visualisation'
            ],
            'parameters': ['n_episodes', 'eval_frequency', 'save_frequency', 'log_frequency']
        }
    }
    
    return info.get(component_type.lower(), {})


logger.info("Module d'entraînement RL initialisé")
