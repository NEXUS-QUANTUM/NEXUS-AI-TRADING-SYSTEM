# ai/neural/__init__.py
"""
NEXUS AI TRADING SYSTEM - Neural Networks Module
Copyright © 2026 NEXUS QUANTUM LTD

Module central des réseaux de neurones pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

# Sous-modules
from ai.neural import architectures
from ai.neural import attention
from ai.neural import embeddings
from ai.neural import layers
from ai.neural import optimizers

logger = logging.getLogger(__name__)


__all__ = [
    # Sous-modules
    'architectures',
    'attention',
    'embeddings',
    'layers',
    'optimizers',
]


def create_neural_component(
    component_type: str,
    sub_type: str,
    **kwargs
) -> Any:
    """
    Factory unifiée pour créer des composants neuronaux.

    Args:
        component_type: Type de composant ('architecture', 'attention', 'embedding', 'layer', 'optimizer')
        sub_type: Sous-type spécifique
        **kwargs: Paramètres de configuration

    Returns:
        Any: Instance du composant

    Examples:
        ```python
        # Architecture
        model = create_neural_component(
            'architecture',
            'resnet',
            version='resnet50',
            num_classes=10
        )

        # Attention
        attn = create_neural_component(
            'attention',
            'self',
            embed_dim=256,
            num_heads=8
        )

        # Embedding
        emb = create_neural_component(
            'embedding',
            'token',
            vocab_size=10000,
            embed_dim=256
        )

        # Layer
        layer = create_neural_component(
            'layer',
            'dense',
            in_features=256,
            out_features=128
        )

        # Optimizer
        optimizer = create_neural_component(
            'optimizer',
            'adamw',
            lr=1e-3,
            weight_decay=0.01
        )
        ```
    """
    component_type = component_type.lower()
    sub_type = sub_type.lower()

    if component_type == 'architecture':
        return architectures.create_architecture(sub_type, **kwargs)

    elif component_type == 'attention':
        return attention.create_attention(sub_type, **kwargs)

    elif component_type == 'embedding':
        return embeddings.create_embedding(sub_type, **kwargs)

    elif component_type == 'layer':
        return layers.create_layer(sub_type, **kwargs)

    elif component_type == 'optimizer':
        return optimizers.create_optimizer(sub_type, **kwargs)

    else:
        raise ValueError(f"Type de composant non supporté: {component_type}")


def get_available_neural_components() -> Dict[str, List[str]]:
    """
    Retourne la liste des composants neuronaux disponibles.

    Returns:
        Dict[str, List[str]]: Composants par catégorie
    """
    return {
        'architecture': architectures.get_available_architectures(),
        'attention': attention.get_available_attentions(),
        'embedding': embeddings.get_available_embeddings(),
        'layer': layers.get_available_layers(),
        'optimizer': optimizers.get_available_optimizers(),
    }


def get_neural_component_info(component_type: str, sub_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un composant neuronal.

    Args:
        component_type: Type de composant
        sub_type: Sous-type spécifique

    Returns:
        Dict[str, Any]: Informations sur le composant
    """
    component_type = component_type.lower()
    sub_type = sub_type.lower()

    if component_type == 'architecture':
        return architectures.get_architecture_info(sub_type)

    elif component_type == 'attention':
        return attention.get_attention_info(sub_type)

    elif component_type == 'embedding':
        return embeddings.get_embedding_info(sub_type)

    elif component_type == 'layer':
        return layers.get_layer_info(sub_type)

    elif component_type == 'optimizer':
        return optimizers.get_optimizer_info(sub_type)

    else:
        return {
            'name': sub_type.capitalize(),
            'description': f"Composant {sub_type} dans la catégorie {component_type}",
        }


def get_neural_recommendation(
    task: str = 'classification',
    model_type: str = 'transformer',
    data_type: str = 'tabular',
    **kwargs
) -> Dict[str, Any]:
    """
    Recommande des composants neuronaux selon les besoins.

    Args:
        task: Tâche ('classification', 'forecasting', 'embedding')
        model_type: Type de modèle ('transformer', 'cnn', 'rnn', 'mlp')
        data_type: Type de données ('tabular', 'time_series', 'text', 'image')
        **kwargs: Arguments supplémentaires

    Returns:
        Dict[str, Any]: Recommandations de composants
    """
    recommendations = {
        'classification': {
            'tabular': {
                'architecture': {'name': 'resnet', 'version': 'resnet18'},
                'attention': {'name': 'self', 'config': {'embed_dim': 128, 'num_heads': 4}},
                'embedding': {'name': 'token', 'config': {'embed_dim': 128}},
                'layer': {'name': 'dense', 'config': {'activation': 'relu', 'dropout': 0.1}},
                'optimizer': {'name': 'adamw', 'config': {'lr': 1e-3, 'weight_decay': 0.01}},
            },
            'time_series': {
                'architecture': {'name': 'resnet', 'version': 'resnet18'},
                'attention': {'name': 'multi_head', 'config': {'embed_dim': 256, 'num_heads': 8}},
                'embedding': {'name': 'time', 'config': {'embed_dim': 64, 'include_cyclical': True}},
                'layer': {'name': 'layer_norm', 'config': {'normalized_shape': 256}},
                'optimizer': {'name': 'adamw', 'config': {'lr': 1e-3}},
            },
            'text': {
                'architecture': {'name': 'resnet', 'version': 'resnet18'},
                'attention': {'name': 'multi_head', 'config': {'embed_dim': 256, 'num_heads': 8}},
                'embedding': {'name': 'token', 'config': {'vocab_size': 10000, 'embed_dim': 256}},
                'layer': {'name': 'layer_norm', 'config': {'normalized_shape': 256}},
                'optimizer': {'name': 'adamw', 'config': {'lr': 1e-3, 'weight_decay': 0.01}},
            },
        },
        'forecasting': {
            'tabular': {
                'architecture': {'name': 'resnet', 'version': 'resnet18'},
                'attention': {'name': 'causal_self', 'config': {'embed_dim': 256, 'num_heads': 8}},
                'embedding': {'name': 'time', 'config': {'embed_dim': 64, 'include_cyclical': True}},
                'layer': {'name': 'layer_norm', 'config': {'normalized_shape': 256}},
                'optimizer': {'name': 'adamw', 'config': {'lr': 1e-3}},
            },
            'time_series': {
                'architecture': {'name': 'resnet', 'version': 'resnet18'},
                'attention': {'name': 'causal_multi_head', 'config': {'embed_dim': 256, 'num_heads': 8}},
                'embedding': {'name': 'time', 'config': {'embed_dim': 64, 'include_hour': True, 'include_weekday': True}},
                'layer': {'name': 'layer_norm', 'config': {'normalized_shape': 256, 'use_rms_norm': True}},
                'optimizer': {'name': 'adamw', 'config': {'lr': 1e-3}},
            },
        },
        'embedding': {
            'tabular': {
                'architecture': {'name': 'efficientnet', 'version': 'b0'},
                'attention': {'name': 'self', 'config': {'embed_dim': 128, 'num_heads': 4}},
                'embedding': {'name': 'token', 'config': {'embed_dim': 128}},
                'layer': {'name': 'dense', 'config': {'activation': 'relu'}},
                'optimizer': {'name': 'adamw', 'config': {'lr': 1e-3}},
            },
            'text': {
                'architecture': {'name': 'efficientnet', 'version': 'b0'},
                'attention': {'name': 'multi_head', 'config': {'embed_dim': 256, 'num_heads': 8}},
                'embedding': {'name': 'token', 'config': {'vocab_size': 10000, 'embed_dim': 256}},
                'layer': {'name': 'layer_norm', 'config': {'normalized_shape': 256}},
                'optimizer': {'name': 'adamw', 'config': {'lr': 1e-3}},
            },
        }
    }

    task_lower = task.lower()
    if task_lower not in recommendations:
        task_lower = 'classification'

    data_type_lower = data_type.lower()
    if data_type_lower not in recommendations[task_lower]:
        data_type_lower = 'tabular'

    recommendation = recommendations[task_lower][data_type_lower]

    return {
        'task': task_lower,
        'model_type': model_type,
        'data_type': data_type_lower,
        'recommended_components': recommendation,
        'alternative_components': {
            'architecture': ['resnet', 'inception', 'efficientnet'],
            'attention': ['self', 'multi_head', 'cross'],
            'embedding': ['token', 'positional', 'time'],
            'layer': ['dense', 'layer_norm', 'batch_norm'],
            'optimizer': ['adamw', 'sgd', 'rmsprop'],
        },
    }


logger.info("Module neuronal initialisé")
