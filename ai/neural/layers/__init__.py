```python
# ai/neural/layers/__init__.py
"""
NEXUS AI TRADING SYSTEM - Neural Network Layers Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de couches pour les réseaux de neurones.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.neural.layers.activation import (
    ActivationFactory,
    ActivationConfig,
    Swish,
    Mish,
    LogSigmoid,
    ParametricSwish,
    ParametricMish,
    ActivationBlock,
    create_activation,
)

from ai.neural.layers.batch_norm import (
    BatchNormConfig,
    BatchNormFactory,
    AdaptiveBatchNorm,
    LayerNorm,
    InstanceNorm,
    WeightNorm,
    create_batch_norm,
)

from ai.neural.layers.dense_layer import (
    DenseLayer,
    DenseLayerConfig,
    ResidualDenseBlock,
    AdaptiveDenseLayer,
    create_dense_layer,
)

from ai.neural.layers.dropout_layer import (
    DropoutConfig,
    DropoutFactory,
    VariationalDropout,
    ConcreteDropout,
    DropoutBlock,
    ScheduledDropout,
    AdaptiveDropout,
    create_dropout,
)

from ai.neural.layers.layer_norm import (
    LayerNorm as LayerNormLayer,
    LayerNormConfig,
    PreLayerNorm,
    PostLayerNorm,
    RMSNorm,
    AdaptiveLayerNorm,
    LayerNormBlock,
    create_layer_norm,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Activation
    'ActivationFactory',
    'ActivationConfig',
    'Swish',
    'Mish',
    'LogSigmoid',
    'ParametricSwish',
    'ParametricMish',
    'ActivationBlock',
    'create_activation',
    
    # Batch Normalization
    'BatchNormConfig',
    'BatchNormFactory',
    'AdaptiveBatchNorm',
    'LayerNorm',
    'InstanceNorm',
    'WeightNorm',
    'create_batch_norm',
    
    # Dense Layer
    'DenseLayer',
    'DenseLayerConfig',
    'ResidualDenseBlock',
    'AdaptiveDenseLayer',
    'create_dense_layer',
    
    # Dropout
    'DropoutConfig',
    'DropoutFactory',
    'VariationalDropout',
    'ConcreteDropout',
    'DropoutBlock',
    'ScheduledDropout',
    'AdaptiveDropout',
    'create_dropout',
    
    # Layer Normalization
    'LayerNormLayer',
    'LayerNormConfig',
    'PreLayerNorm',
    'PostLayerNorm',
    'RMSNorm',
    'AdaptiveLayerNorm',
    'LayerNormBlock',
    'create_layer_norm',
]


def create_layer(
    layer_type: str = 'dense',
    **kwargs
) -> Any:
    """
    Factory pour créer des couches neurales.
    
    Args:
        layer_type: Type de couche ('dense', 'activation', 'batch_norm', 'dropout', 'layer_norm')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance de la couche
    
    Examples:
        ```python
        # Couche dense
        layer = create_layer(
            'dense',
            in_features=256,
            out_features=128,
            activation='relu',
            dropout=0.1
        )
        
        # Activation
        layer = create_layer(
            'activation',
            activation_type='swish'
        )
        
        # Batch Normalization
        layer = create_layer(
            'batch_norm',
            num_features=256,
            dim=1
        )
        
        # Dropout
        layer = create_layer(
            'dropout',
            p=0.5,
            use_variational=True
        )
        
        # Layer Normalization
        layer = create_layer(
            'layer_norm',
            normalized_shape=256,
            use_rms_norm=True
        )
        ```
    """
    layer_type = layer_type.lower()
    
    if layer_type == 'dense':
        in_features = kwargs.get('in_features')
        out_features = kwargs.get('out_features')
        if in_features is None or out_features is None:
            raise ValueError("in_features et out_features sont requis")
        
        activation = kwargs.get('activation')
        dropout = kwargs.get('dropout', 0.0)
        use_batch_norm = kwargs.get('use_batch_norm', False)
        use_layer_norm = kwargs.get('use_layer_norm', False)
        
        return create_dense_layer(
            in_features=in_features,
            out_features=out_features,
            activation=activation,
            dropout=dropout,
            use_batch_norm=use_batch_norm,
            use_layer_norm=use_layer_norm,
            **{k: v for k, v in kwargs.items() 
               if k not in ['in_features', 'out_features', 'activation', 
                           'dropout', 'use_batch_norm', 'use_layer_norm']}
        )
    
    elif layer_type == 'activation':
        activation_type = kwargs.get('activation_type', 'relu')
        negative_slope = kwargs.get('negative_slope', 0.01)
        threshold = kwargs.get('threshold', 1.0)
        learnable = kwargs.get('learnable', False)
        inplace = kwargs.get('inplace', False)
        
        return create_activation(
            activation_type=activation_type,
            negative_slope=negative_slope,
            threshold=threshold,
            learnable=learnable,
            inplace=inplace,
            **{k: v for k, v in kwargs.items() 
               if k not in ['activation_type', 'negative_slope', 
                           'threshold', 'learnable', 'inplace']}
        )
    
    elif layer_type == 'batch_norm':
        num_features = kwargs.get('num_features')
        if num_features is None:
            raise ValueError("num_features est requis")
        
        dim = kwargs.get('dim', 1)
        eps = kwargs.get('eps', 1e-5)
        momentum = kwargs.get('momentum', 0.1)
        affine = kwargs.get('affine', True)
        track_running_stats = kwargs.get('track_running_stats', True)
        
        return create_batch_norm(
            num_features=num_features,
            dim=dim,
            eps=eps,
            momentum=momentum,
            affine=affine,
            track_running_stats=track_running_stats,
            **{k: v for k, v in kwargs.items() 
               if k not in ['num_features', 'dim', 'eps', 
                           'momentum', 'affine', 'track_running_stats']}
        )
    
    elif layer_type == 'dropout':
        p = kwargs.get('p', 0.5)
        use_alpha = kwargs.get('use_alpha', False)
        use_feature = kwargs.get('use_feature', False)
        use_spatial = kwargs.get('use_spatial', False)
        use_variational = kwargs.get('use_variational', False)
        dim = kwargs.get('dim', None)
        
        return create_dropout(
            p=p,
            use_alpha=use_alpha,
            use_feature=use_feature,
            use_spatial=use_spatial,
            use_variational=use_variational,
            dim=dim,
            **{k: v for k, v in kwargs.items() 
               if k not in ['p', 'use_alpha', 'use_feature', 
                           'use_spatial', 'use_variational', 'dim']}
        )
    
    elif layer_type == 'layer_norm':
        normalized_shape = kwargs.get('normalized_shape')
        if normalized_shape is None:
            raise ValueError("normalized_shape est requis")
        
        eps = kwargs.get('eps', 1e-5)
        elementwise_affine = kwargs.get('elementwise_affine', True)
        use_rms_norm = kwargs.get('use_rms_norm', False)
        use_pre_norm = kwargs.get('use_pre_norm', False)
        use_post_norm = kwargs.get('use_post_norm', False)
        
        if use_rms_norm:
            return RMSNorm(
                normalized_shape=normalized_shape,
                eps=eps,
                elementwise_scale=elementwise_affine,
            )
        elif use_pre_norm:
            return PreLayerNorm(
                normalized_shape=normalized_shape,
                eps=eps,
                elementwise_affine=elementwise_affine,
            )
        elif use_post_norm:
            return PostLayerNorm(
                normalized_shape=normalized_shape,
                eps=eps,
                elementwise_affine=elementwise_affine,
            )
        else:
            return create_layer_norm(
                normalized_shape=normalized_shape,
                eps=eps,
                elementwise_affine=elementwise_affine,
                **{k: v for k, v in kwargs.items() 
                   if k not in ['normalized_shape', 'eps', 
                               'elementwise_affine', 'use_rms_norm',
                               'use_pre_norm', 'use_post_norm']}
            )
    
    else:
        raise ValueError(f"Type de couche non supporté: {layer_type}")


def get_available_layers() -> List[str]:
    """
    Retourne la liste des couches disponibles.
    
    Returns:
        List[str]: Liste des types de couches
    """
    layers = ['dense', 'activation', 'batch_norm', 'dropout', 'layer_norm']
    
    try:
        import torch
    except ImportError:
        layers = []
    
    return layers


def get_layer_info(layer_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de couche.
    
    Args:
        layer_type: Type de couche
    
    Returns:
        Dict[str, Any]: Informations sur la couche
    """
    info = {
        'dense': {
            'name': 'Dense Layer',
            'description': 'Couche fully connected avec options avancées',
            'parameters': ['in_features', 'out_features', 'activation', 'dropout', 'use_batch_norm'],
            'use_cases': ['Modèles fully connected', 'Couches de sortie', 'Projeteurs'],
        },
        'activation': {
            'name': 'Activation Layer',
            'description': 'Fonctions d\'activation avec options paramétriques',
            'parameters': ['activation_type', 'negative_slope', 'learnable'],
            'use_cases': ['Non-linéarité', 'Normalisation', 'Activation des couches'],
        },
        'batch_norm': {
            'name': 'Batch Normalization',
            'description': 'Normalisation par batch pour stabiliser l\'entraînement',
            'parameters': ['num_features', 'dim', 'momentum', 'affine'],
            'use_cases': ['CNNs', 'MLPs', 'Stabilisation'],
        },
        'dropout': {
            'name': 'Dropout Layer',
            'description': 'Régularisation par dropout avec variantes',
            'parameters': ['p', 'use_alpha', 'use_spatial', 'use_variational'],
            'use_cases': ['Régularisation', 'Prévention overfitting', 'Incertitude'],
        },
        'layer_norm': {
            'name': 'Layer Normalization',
            'description': 'Normalisation par couche avec RMSNorm',
            'parameters': ['normalized_shape', 'eps', 'use_rms_norm', 'use_pre_norm'],
            'use_cases': ['Transformers', 'RNNs', 'Séquences'],
        }
    }
    
    return info.get(layer_type.lower(), {})


logger.info("Module de couches neurales initialisé")
```
