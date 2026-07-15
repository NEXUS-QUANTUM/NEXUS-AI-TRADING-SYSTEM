
# ai/neural/embeddings/__init__.py
"""
NEXUS AI TRADING SYSTEM - Embeddings Module
Copyright © 2026 NEXUS QUANTUM LTD

Module d'embeddings pour les réseaux de neurones.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.neural.embeddings.positional_encoding import (
    PositionalEncoding,
    PositionalEncodingConfig,
    LearnablePositionalEncoding,
    RelativePositionalEncoding,
    RotaryPositionalEmbedding,
    create_positional_encoding,
)

from ai.neural.embeddings.time_embedding import (
    TimeEmbedding,
    TimeEmbeddingConfig,
    PeriodicTimeEmbedding,
    AdaptiveTimeEmbedding,
    create_time_embedding,
)

from ai.neural.embeddings.token_embedding import (
    TokenEmbedding,
    TokenEmbeddingConfig,
    MultiTokenEmbedding,
    AdaptiveTokenEmbedding,
    PositionalTokenEmbedding,
    create_token_embedding,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Positional Encoding
    'PositionalEncoding',
    'PositionalEncodingConfig',
    'LearnablePositionalEncoding',
    'RelativePositionalEncoding',
    'RotaryPositionalEmbedding',
    'create_positional_encoding',
    
    # Time Embedding
    'TimeEmbedding',
    'TimeEmbeddingConfig',
    'PeriodicTimeEmbedding',
    'AdaptiveTimeEmbedding',
    'create_time_embedding',
    
    # Token Embedding
    'TokenEmbedding',
    'TokenEmbeddingConfig',
    'MultiTokenEmbedding',
    'AdaptiveTokenEmbedding',
    'PositionalTokenEmbedding',
    'create_token_embedding',
]


def create_embedding(
    embedding_type: str = 'token',
    **kwargs
) -> Any:
    """
    Factory pour créer des embeddings.
    
    Args:
        embedding_type: Type d'embedding ('token', 'positional', 'time')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance de l'embedding
    
    Examples:
        ```python
        # Token Embedding
        embedding = create_embedding(
            'token',
            vocab_size=10000,
            embed_dim=256,
            padding_idx=0
        )
        
        # Positional Encoding
        embedding = create_embedding(
            'positional',
            embed_dim=256,
            max_length=512,
            encoding_type='sinusoidal'
        )
        
        # Time Embedding
        embedding = create_embedding(
            'time',
            embed_dim=64,
            include_cyclical=True,
            include_hour=True
        )
        ```
    """
    embedding_type = embedding_type.lower()
    
    if embedding_type == 'token':
        vocab_size = kwargs.get('vocab_size', 10000)
        embed_dim = kwargs.get('embed_dim', 256)
        padding_idx = kwargs.get('padding_idx', None)
        dropout = kwargs.get('dropout', 0.0)
        
        return create_token_embedding(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            padding_idx=padding_idx,
            dropout=dropout,
            **{k: v for k, v in kwargs.items() 
               if k not in ['vocab_size', 'embed_dim', 'padding_idx', 'dropout']}
        )
    
    elif embedding_type == 'positional':
        embed_dim = kwargs.get('embed_dim', 256)
        max_length = kwargs.get('max_length', 1000)
        encoding_type = kwargs.get('encoding_type', 'sinusoidal')
        dropout = kwargs.get('dropout', 0.1)
        
        return create_positional_encoding(
            embed_dim=embed_dim,
            max_length=max_length,
            encoding_type=encoding_type,
            dropout=dropout,
            **{k: v for k, v in kwargs.items() 
               if k not in ['embed_dim', 'max_length', 'encoding_type', 'dropout']}
        )
    
    elif embedding_type == 'time':
        embed_dim = kwargs.get('embed_dim', 64)
        include_cyclical = kwargs.get('include_cyclical', True)
        include_weekday = kwargs.get('include_weekday', True)
        include_hour = kwargs.get('include_hour', True)
        
        return create_time_embedding(
            embed_dim=embed_dim,
            include_cyclical=include_cyclical,
            include_weekday=include_weekday,
            include_hour=include_hour,
            **{k: v for k, v in kwargs.items() 
               if k not in ['embed_dim', 'include_cyclical', 'include_weekday', 'include_hour']}
        )
    
    else:
        raise ValueError(f"Type d'embedding non supporté: {embedding_type}")


def get_available_embeddings() -> List[str]:
    """
    Retourne la liste des embeddings disponibles.
    
    Returns:
        List[str]: Liste des types d'embeddings
    """
    embeddings = ['token', 'positional', 'time']
    
    try:
        import torch
    except ImportError:
        embeddings = []
    
    return embeddings


def get_embedding_info(embedding_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type d'embedding.
    
    Args:
        embedding_type: Type d'embedding
    
    Returns:
        Dict[str, Any]: Informations sur l'embedding
    """
    info = {
        'token': {
            'name': 'Token Embedding',
            'description': 'Embedding de tokens en vecteurs denses',
            'advantages': [
                'Standard et bien compris',
                'Support des tokens OOV',
                'Apprentissage de représentations'
            ],
            'disadvantages': [
                'Nécessite un vocabulaire fixe',
                'Pas de contexte',
                'Ne capture pas les relations sémantiques complexes'
            ],
            'use_cases': [
                'Modèles NLP',
                'Recherche d'information',
                'Classification de textes'
            ]
        },
        'positional': {
            'name': 'Positional Encoding',
            'description': 'Encodage de la position dans les séquences',
            'advantages': [
                'Ajoute l\'information de position',
                'Plusieurs types disponibles',
                'Support des longues séquences'
            ],
            'disadvantages': [
                'Peut être sensible à la longueur',
                'Poids fixes pour sinusoidal',
                'Nécessite une max_length'
            ],
            'use_cases': [
                'Transformers',
                'Modèles de langage',
                'Séquences temporelles'
            ]
        },
        'time': {
            'name': 'Time Embedding',
            'description': 'Embedding des informations temporelles',
            'advantages': [
                'Capture les patterns temporels',
                'Cyclical encoding',
                'Features riches (heure, jour, etc.)'
            ],
            'disadvantages': [
                'Plus complexe',
                'Nécessite des timestamps',
                'Peut être sur-spécifique'
            ],
            'use_cases': [
                'Séries temporelles',
                'Prévision',
                'Analyse de patterns temporels'
            ]
        }
    }
    
    return info.get(embedding_type.lower(), {})


def get_embedding_recommendation(
    task: str = 'sequence_modeling',
    data_type: str = 'text',
    sequence_length: str = 'medium'
) -> Dict[str, Any]:
    """
    Recommande un type d'embedding selon les besoins.
    
    Args:
        task: Tâche ('sequence_modeling', 'time_series', 'classification')
        data_type: Type de données ('text', 'time', 'token')
        sequence_length: Longueur des séquences ('short', 'medium', 'long')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    if data_type == 'text':
        return {
            'recommended_embedding': {
                'type': 'token',
                'description': 'Token Embedding pour les données textuelles'
            },
            'alternative_embeddings': ['positional'],
            'additional_info': 'Ajouter un Positional Encoding pour les Transformers'
        }
    
    elif data_type == 'time':
        return {
            'recommended_embedding': {
                'type': 'time',
                'description': 'Time Embedding pour les données temporelles'
            },
            'alternative_embeddings': ['positional'],
            'additional_info': 'Utiliser l\'encodage cyclique pour les périodicités'
        }
    
    elif data_type == 'token':
        if task == 'sequence_modeling':
            return {
                'recommended_embedding': {
                    'type': 'positional',
                    'description': 'Positional Encoding pour la modélisation de séquences'
                },
                'alternative_embeddings': ['token'],
                'additional_info': 'Combiner avec Token Embedding pour de meilleurs résultats'
            }
        else:
            return {
                'recommended_embedding': {
                    'type': 'token',
                    'description': 'Token Embedding pour la classification'
                },
                'alternative_embeddings': ['positional', 'time'],
                'additional_info': 'Ajuster la dimension selon la complexité de la tâche'
            }
    
    # Par défaut
    return {
        'recommended_embedding': {
            'type': 'token',
            'description': 'Token Embedding par défaut'
        },
        'alternative_embeddings': ['positional', 'time'],
        'additional_info': 'Adapter selon le type de données et la tâche',
    }


logger.info("Module d'embeddings initialisé")
