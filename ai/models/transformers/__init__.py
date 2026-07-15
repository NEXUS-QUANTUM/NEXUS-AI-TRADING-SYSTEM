
# ai/models/transformers/__init__.py
"""
NEXUS AI TRADING SYSTEM - Transformer Models Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de modèles Transformer pour la prévision de séries temporelles.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.models.transformers.time_series_transformer import (
    TimeSeriesTransformer,
    TimeSeriesTransformerConfig,
    TimeSeriesTransformerResult,
    create_time_series_transformer,
)

from ai.models.transformers.informer_model import (
    InformerModel,
    InformerConfig,
    InformerResult,
    create_informer,
)

from ai.models.transformers.autoformer_model import (
    AutoformerModel,
    AutoformerConfig,
    AutoformerResult,
    create_autoformer,
)

from ai.models.transformers.patchtst_model import (
    PatchTSTModel,
    PatchTSTConfig,
    PatchTSTResult,
    create_patchtst,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Time Series Transformer
    'TimeSeriesTransformer',
    'TimeSeriesTransformerConfig',
    'TimeSeriesTransformerResult',
    'create_time_series_transformer',
    
    # Informer
    'InformerModel',
    'InformerConfig',
    'InformerResult',
    'create_informer',
    
    # Autoformer
    'AutoformerModel',
    'AutoformerConfig',
    'AutoformerResult',
    'create_autoformer',
    
    # PatchTST
    'PatchTSTModel',
    'PatchTSTConfig',
    'PatchTSTResult',
    'create_patchtst',
]


def create_transformer_model(
    model_type: str = 'transformer',
    **kwargs
) -> Any:
    """
    Factory pour créer des modèles Transformer.
    
    Args:
        model_type: Type de modèle ('transformer', 'informer', 'autoformer', 'patchtst')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance du modèle Transformer
    
    Examples:
        ```python
        # Time Series Transformer standard
        model = create_transformer_model(
            'transformer',
            input_size=1,
            hidden_size=128,
            context_length=24,
            prediction_length=12,
            num_layers=2,
            num_heads=4
        )
        
        # Informer
        model = create_transformer_model(
            'informer',
            input_size=1,
            hidden_size=128,
            context_length=24,
            prediction_length=12,
            prob_sparse=True,
            distil=True
        )
        
        # Autoformer
        model = create_transformer_model(
            'autoformer',
            input_size=1,
            hidden_size=128,
            context_length=24,
            prediction_length=12,
            auto_correlation=True,
            series_decomp=True
        )
        
        # PatchTST
        model = create_transformer_model(
            'patchtst',
            input_size=1,
            hidden_size=128,
            context_length=24,
            prediction_length=12,
            patch_len=8,
            stride=4
        )
        ```
    """
    model_type = model_type.lower()
    
    if model_type == 'transformer':
        input_size = kwargs.get('input_size', 1)
        hidden_size = kwargs.get('hidden_size', 128)
        context_length = kwargs.get('context_length', 24)
        prediction_length = kwargs.get('prediction_length', 12)
        num_layers = kwargs.get('num_layers', 2)
        num_heads = kwargs.get('num_heads', 4)
        
        return create_time_series_transformer(
            input_size=input_size,
            hidden_size=hidden_size,
            context_length=context_length,
            prediction_length=prediction_length,
            num_layers=num_layers,
            num_heads=num_heads,
            **{k: v for k, v in kwargs.items() 
               if k not in ['input_size', 'hidden_size', 'context_length',
                           'prediction_length', 'num_layers', 'num_heads']}
        )
    
    elif model_type == 'informer':
        input_size = kwargs.get('input_size', 1)
        hidden_size = kwargs.get('hidden_size', 128)
        context_length = kwargs.get('context_length', 24)
        prediction_length = kwargs.get('prediction_length', 12)
        prob_sparse = kwargs.get('prob_sparse', True)
        distil = kwargs.get('distil', True)
        
        return create_informer(
            input_size=input_size,
            hidden_size=hidden_size,
            context_length=context_length,
            prediction_length=prediction_length,
            prob_sparse=prob_sparse,
            distil=distil,
            **{k: v for k, v in kwargs.items() 
               if k not in ['input_size', 'hidden_size', 'context_length',
                           'prediction_length', 'prob_sparse', 'distil']}
        )
    
    elif model_type == 'autoformer':
        input_size = kwargs.get('input_size', 1)
        hidden_size = kwargs.get('hidden_size', 128)
        context_length = kwargs.get('context_length', 24)
        prediction_length = kwargs.get('prediction_length', 12)
        auto_correlation = kwargs.get('auto_correlation', True)
        series_decomp = kwargs.get('series_decomp', True)
        
        return create_autoformer(
            input_size=input_size,
            hidden_size=hidden_size,
            context_length=context_length,
            prediction_length=prediction_length,
            auto_correlation=auto_correlation,
            series_decomp=series_decomp,
            **{k: v for k, v in kwargs.items() 
               if k not in ['input_size', 'hidden_size', 'context_length',
                           'prediction_length', 'auto_correlation', 'series_decomp']}
        )
    
    elif model_type == 'patchtst':
        input_size = kwargs.get('input_size', 1)
        hidden_size = kwargs.get('hidden_size', 128)
        context_length = kwargs.get('context_length', 24)
        prediction_length = kwargs.get('prediction_length', 12)
        patch_len = kwargs.get('patch_len', 8)
        stride = kwargs.get('stride', 4)
        revin = kwargs.get('revin', True)
        
        return create_patchtst(
            input_size=input_size,
            hidden_size=hidden_size,
            context_length=context_length,
            prediction_length=prediction_length,
            patch_len=patch_len,
            stride=stride,
            revin=revin,
            **{k: v for k, v in kwargs.items() 
               if k not in ['input_size', 'hidden_size', 'context_length',
                           'prediction_length', 'patch_len', 'stride', 'revin']}
        )
    
    else:
        raise ValueError(f"Type de modèle Transformer non supporté: {model_type}")


def get_available_transformer_models() -> List[str]:
    """
    Retourne la liste des modèles Transformer disponibles.
    
    Returns:
        List[str]: Liste des types de modèles
    """
    models = ['transformer', 'informer', 'autoformer', 'patchtst']
    
    try:
        import torch
    except ImportError:
        models = []
    
    return models


def get_transformer_model_info(model_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de modèle Transformer.
    
    Args:
        model_type: Type de modèle
    
    Returns:
        Dict[str, Any]: Informations sur le modèle
    """
    info = {
        'transformer': {
            'name': 'Time Series Transformer',
            'description': 'Modèle Transformer standard adapté aux séries temporelles',
            'advantages': [
                'Architecture standard bien comprise',
                'Capture les dépendances longues',
                'Flexible et configurable'
            ],
            'disadvantages': [
                'Peut être lent sur longues séquences',
                'Nécessite beaucoup de données',
                'Sensible aux hyperparamètres'
            ],
            'use_cases': [
                'Séries temporelles de longueur moyenne',
                'Quand l\'interprétabilité est importante',
                'Données avec patterns complexes'
            ]
        },
        'informer': {
            'name': 'Informer',
            'description': 'Modèle Transformer avec attention parcimonieuse',
            'advantages': [
                'Efficace pour les longues séquences',
                'Attention probabiliste',
                'Meilleure performance sur long terme'
            ],
            'disadvantages': [
                'Complexe à implémenter',
                'Nécessite beaucoup de données',
                'Moins interprétable'
            ],
            'use_cases': [
                'Prévisions à long terme',
                'Séries temporelles très longues',
                'Quand l\'efficacité est importante'
            ]
        },
        'autoformer': {
            'name': 'Autoformer',
            'description': 'Modèle Transformer avec auto-corrélation et décomposition',
            'advantages': [
                'Décomposition en tendance/saisonnalité',
                'Mécanisme d\'auto-corrélation',
                'Bon pour les séries saisonnières'
            ],
            'disadvantages': [
                'Complexe à implémenter',
                'Peut être lent',
                'Nécessite beaucoup de données'
            ],
            'use_cases': [
                'Séries avec saisonnalités fortes',
                'Prévisions à moyen/long terme',
                'Données avec patterns récurrents'
            ]
        },
        'patchtst': {
            'name': 'PatchTST',
            'description': 'Modèle Transformer avec patching de séries temporelles',
            'advantages': [
                'Efficace et léger',
                'Bonnes performances',
                'RevIN pour la normalisation'
            ],
            'disadvantages': [
                'Choix de la taille des patches important',
                'Moins interprétable',
                'Nécessite du tuning'
            ],
            'use_cases': [
                'Prévisions à long terme',
                'Quand l\'efficacité est importante',
                'Données avec tendances'
            ]
        }
    }
    
    return info.get(model_type.lower(), {})


def get_transformer_recommendation(
    sequence_length: int,
    forecast_horizon: int,
    seasonality: Optional[str] = None,
    performance: str = 'balanced'
) -> Dict[str, Any]:
    """
    Recommande un modèle Transformer selon les besoins.
    
    Args:
        sequence_length: Longueur de la séquence historique
        forecast_horizon: Horizon de prévision
        seasonality: Type de saisonnalité ('daily', 'weekly', 'yearly', None)
        performance: Priorité ('speed', 'balanced', 'accuracy')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    recommendations = {
        'short': {
            'speed': {'model': 'transformer', 'description': 'Time Series Transformer pour séquences courtes'},
            'balanced': {'model': 'transformer', 'description': 'Time Series Transformer pour séquences courtes'},
            'accuracy': {'model': 'autoformer', 'description': 'Autoformer pour meilleure précision'},
        },
        'medium': {
            'speed': {'model': 'patchtst', 'description': 'PatchTST pour séquences moyennes efficace'},
            'balanced': {'model': 'informer', 'description': 'Informer pour séquences moyennes'},
            'accuracy': {'model': 'autoformer', 'description': 'Autoformer pour meilleure précision'},
        },
        'long': {
            'speed': {'model': 'patchtst', 'description': 'PatchTST efficace pour longues séquences'},
            'balanced': {'model': 'informer', 'description': 'Informer pour longues séquences'},
            'accuracy': {'model': 'informer', 'description': 'Informer pour meilleure précision'},
        }
    }
    
    # Déterminer la catégorie de longueur
    if sequence_length < 50:
        length_category = 'short'
    elif sequence_length < 200:
        length_category = 'medium'
    else:
        length_category = 'long'
    
    # Ajuster selon l'horizon de prévision
    if forecast_horizon > sequence_length // 2 and length_category != 'long':
        length_category = 'medium' if length_category == 'short' else 'long'
    
    # Ajuster selon la saisonnalité
    if seasonality is not None and length_category != 'short':
        if seasonality in ['daily', 'weekly']:
            return {
                'length_category': length_category,
                'forecast_horizon': forecast_horizon,
                'seasonality': seasonality,
                'performance': performance,
                'recommended_model': {
                    'model': 'autoformer',
                    'description': 'Autoformer recommandé pour les séries saisonnières'
                },
                'alternative_models': ['informer', 'patchtst', 'transformer'],
            }
    
    recommendation = recommendations[length_category][performance]
    
    return {
        'length_category': length_category,
        'forecast_horizon': forecast_horizon,
        'seasonality': seasonality,
        'performance': performance,
        'recommended_model': recommendation,
        'alternative_models': ['transformer', 'informer', 'autoformer', 'patchtst'],
    }


logger.info("Module de modèles Transformer initialisé")
