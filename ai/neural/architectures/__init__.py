
# ai/neural/architectures/__init__.py
"""
NEXUS AI TRADING SYSTEM - Neural Network Architectures Module
Copyright © 2026 NEXUS QUANTUM LTD

Module d'architectures de réseaux de neurones pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.neural.architectures.resnet import (
    ResNet,
    ResNetConfig,
    create_resnet,
)

from ai.neural.architectures.inception import (
    Inception,
    InceptionConfig,
    create_inception,
)

from ai.neural.architectures.efficientnet import (
    EfficientNet,
    EfficientNetConfig,
    create_efficientnet,
)

logger = logging.getLogger(__name__)


__all__ = [
    # ResNet
    'ResNet',
    'ResNetConfig',
    'create_resnet',
    
    # Inception
    'Inception',
    'InceptionConfig',
    'create_inception',
    
    # EfficientNet
    'EfficientNet',
    'EfficientNetConfig',
    'create_efficientnet',
]


def create_architecture(
    architecture: str = 'resnet',
    **kwargs
) -> Any:
    """
    Factory pour créer des architectures de réseaux de neurones.
    
    Args:
        architecture: Type d'architecture ('resnet', 'inception', 'efficientnet')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance de l'architecture
    
    Examples:
        ```python
        # ResNet50
        model = create_architecture(
            'resnet',
            version='resnet50',
            num_classes=10,
            input_channels=3
        )
        
        # Inception V3
        model = create_architecture(
            'inception',
            version='v3',
            num_classes=10,
            input_channels=3
        )
        
        # EfficientNet B0
        model = create_architecture(
            'efficientnet',
            version='b0',
            num_classes=10,
            input_channels=3
        )
        ```
    """
    architecture = architecture.lower()
    
    if architecture == 'resnet':
        version = kwargs.get('version', 'resnet50')
        num_classes = kwargs.get('num_classes', 1000)
        input_channels = kwargs.get('input_channels', 3)
        
        return create_resnet(
            version=version,
            num_classes=num_classes,
            input_channels=input_channels,
            **{k: v for k, v in kwargs.items() 
               if k not in ['version', 'num_classes', 'input_channels']}
        )
    
    elif architecture == 'inception':
        version = kwargs.get('version', 'v3')
        num_classes = kwargs.get('num_classes', 1000)
        input_channels = kwargs.get('input_channels', 3)
        aux_logits = kwargs.get('aux_logits', True)
        
        return create_inception(
            version=version,
            num_classes=num_classes,
            input_channels=input_channels,
            aux_logits=aux_logits,
            **{k: v for k, v in kwargs.items() 
               if k not in ['version', 'num_classes', 'input_channels', 'aux_logits']}
        )
    
    elif architecture == 'efficientnet':
        version = kwargs.get('version', 'b0')
        num_classes = kwargs.get('num_classes', 1000)
        input_channels = kwargs.get('input_channels', 3)
        
        return create_efficientnet(
            version=version,
            num_classes=num_classes,
            input_channels=input_channels,
            **{k: v for k, v in kwargs.items() 
               if k not in ['version', 'num_classes', 'input_channels']}
        )
    
    else:
        raise ValueError(f"Architecture non supportée: {architecture}")


def get_available_architectures() -> List[str]:
    """
    Retourne la liste des architectures disponibles.
    
    Returns:
        List[str]: Liste des types d'architectures
    """
    architectures = ['resnet', 'inception', 'efficientnet']
    
    try:
        import torch
    except ImportError:
        architectures = []
    
    return architectures


def get_architecture_info(architecture: str) -> Dict[str, Any]:
    """
    Retourne des informations sur une architecture.
    
    Args:
        architecture: Type d'architecture
    
    Returns:
        Dict[str, Any]: Informations sur l'architecture
    """
    info = {
        'resnet': {
            'name': 'ResNet',
            'description': 'Residual Network avec connections de saut',
            'versions': ['resnet18', 'resnet34', 'resnet50', 'resnet101', 'resnet152'],
            'advantages': [
                'Très profond',
                'Facile à entraîner',
                'Bien adapté aux images'
            ],
            'disadvantages': [
                'Beaucoup de paramètres',
                'Lourd en mémoire',
                'Temps d\'inférence élevé'
            ],
            'use_cases': [
                'Classification d\'images',
                'Extraction de features',
                'Transfer learning'
            ]
        },
        'inception': {
            'name': 'Inception',
            'description': 'Architecture avec convolutions multi-échelles',
            'versions': ['v1', 'v2', 'v3', 'v4'],
            'advantages': [
                'Capture différentes échelles',
                'Efficace',
                'Performant'
            ],
            'disadvantages': [
                'Complexe',
                'Difficile à optimiser',
                'Beaucoup de branches'
            ],
            'use_cases': [
                'Classification d\'images',
                'Détection d\'objets',
                'Analyse de patterns'
            ]
        },
        'efficientnet': {
            'name': 'EfficientNet',
            'description': 'Architecture optimisée pour l\'efficacité',
            'versions': ['b0', 'b1', 'b2', 'b3', 'b4', 'b5', 'b6', 'b7'],
            'advantages': [
                'Très efficace',
                'Bon rapport performance/poids',
                'Scaling automatique'
            ],
            'disadvantages': [
                'Complexe à comprendre',
                'Nécessite des réglages',
                'Moins interprétable'
            ],
            'use_cases': [
                'Classification d\'images',
                'Embeddings',
                'Applications mobiles'
            ]
        }
    }
    
    return info.get(architecture.lower(), {})


def get_architecture_recommendation(
    task: str = 'classification',
    dataset_size: str = 'medium',
    performance: str = 'balanced',
    memory: str = 'medium'
) -> Dict[str, Any]:
    """
    Recommande une architecture selon les besoins.
    
    Args:
        task: Tâche ('classification', 'feature_extraction', 'embedding')
        dataset_size: Taille du dataset ('small', 'medium', 'large')
        performance: Priorité ('speed', 'balanced', 'accuracy')
        memory: Contrainte mémoire ('low', 'medium', 'high')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    recommendations = {
        'classification': {
            'small': {
                'speed': {'architecture': 'resnet', 'version': 'resnet18'},
                'balanced': {'architecture': 'resnet', 'version': 'resnet50'},
                'accuracy': {'architecture': 'efficientnet', 'version': 'b4'},
            },
            'medium': {
                'speed': {'architecture': 'efficientnet', 'version': 'b0'},
                'balanced': {'architecture': 'resnet', 'version': 'resnet50'},
                'accuracy': {'architecture': 'inception', 'version': 'v3'},
            },
            'large': {
                'speed': {'architecture': 'efficientnet', 'version': 'b1'},
                'balanced': {'architecture': 'inception', 'version': 'v3'},
                'accuracy': {'architecture': 'resnet', 'version': 'resnet152'},
            }
        },
        'feature_extraction': {
            'small': {
                'speed': {'architecture': 'resnet', 'version': 'resnet18'},
                'balanced': {'architecture': 'resnet', 'version': 'resnet50'},
                'accuracy': {'architecture': 'inception', 'version': 'v3'},
            },
            'medium': {
                'speed': {'architecture': 'efficientnet', 'version': 'b0'},
                'balanced': {'architecture': 'inception', 'version': 'v3'},
                'accuracy': {'architecture': 'resnet', 'version': 'resnet101'},
            },
            'large': {
                'speed': {'architecture': 'efficientnet', 'version': 'b2'},
                'balanced': {'architecture': 'resnet', 'version': 'resnet50'},
                'accuracy': {'architecture': 'inception', 'version': 'v4'},
            }
        },
        'embedding': {
            'small': {
                'speed': {'architecture': 'efficientnet', 'version': 'b0'},
                'balanced': {'architecture': 'efficientnet', 'version': 'b1'},
                'accuracy': {'architecture': 'efficientnet', 'version': 'b3'},
            },
            'medium': {
                'speed': {'architecture': 'efficientnet', 'version': 'b1'},
                'balanced': {'architecture': 'efficientnet', 'version': 'b2'},
                'accuracy': {'architecture': 'efficientnet', 'version': 'b4'},
            },
            'large': {
                'speed': {'architecture': 'efficientnet', 'version': 'b2'},
                'balanced': {'architecture': 'efficientnet', 'version': 'b3'},
                'accuracy': {'architecture': 'efficientnet', 'version': 'b5'},
            }
        }
    }
    
    task_lower = task.lower()
    if task_lower not in recommendations:
        task_lower = 'classification'
    
    dataset_size_lower = dataset_size.lower()
    if dataset_size_lower not in ['small', 'medium', 'large']:
        dataset_size_lower = 'medium'
    
    performance_lower = performance.lower()
    if performance_lower not in ['speed', 'balanced', 'accuracy']:
        performance_lower = 'balanced'
    
    recommendation = recommendations[task_lower][dataset_size_lower][performance_lower]
    
    return {
        'task': task_lower,
        'dataset_size': dataset_size_lower,
        'performance': performance_lower,
        'memory': memory,
        'recommended_architecture': recommendation,
        'alternative_architectures': [
            {'architecture': 'resnet', 'version': 'resnet50'},
            {'architecture': 'inception', 'version': 'v3'},
            {'architecture': 'efficientnet', 'version': 'b0'},
        ],
    }


logger.info("Module d'architectures neurales initialisé")
