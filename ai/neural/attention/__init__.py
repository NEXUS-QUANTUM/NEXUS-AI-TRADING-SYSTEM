
# ai/neural/attention/__init__.py
"""
NEXUS AI TRADING SYSTEM - Attention Mechanisms Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de mécanismes d'attention pour les réseaux de neurones.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.neural.attention.self_attention import (
    SelfAttention,
    SelfAttentionConfig,
    SelfAttentionBlock,
    CausalSelfAttention,
    create_self_attention,
    create_causal_self_attention,
)

from ai.neural.attention.multi_head_attention import (
    MultiHeadAttention,
    MultiHeadAttentionConfig,
    MultiHeadAttentionBlock,
    CausalMultiHeadAttention,
    create_multi_head_attention,
    create_causal_multi_head_attention,
)

from ai.neural.attention.cross_attention import (
    CrossAttention,
    CrossAttentionConfig,
    CrossAttentionBlock,
    MultiCrossAttention,
    create_cross_attention,
    create_cross_attention_block,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Self-Attention
    'SelfAttention',
    'SelfAttentionConfig',
    'SelfAttentionBlock',
    'CausalSelfAttention',
    'create_self_attention',
    'create_causal_self_attention',
    
    # Multi-Head Attention
    'MultiHeadAttention',
    'MultiHeadAttentionConfig',
    'MultiHeadAttentionBlock',
    'CausalMultiHeadAttention',
    'create_multi_head_attention',
    'create_causal_multi_head_attention',
    
    # Cross-Attention
    'CrossAttention',
    'CrossAttentionConfig',
    'CrossAttentionBlock',
    'MultiCrossAttention',
    'create_cross_attention',
    'create_cross_attention_block',
]


def create_attention(
    attention_type: str = 'self',
    **kwargs
) -> Any:
    """
    Factory pour créer des mécanismes d'attention.
    
    Args:
        attention_type: Type d'attention ('self', 'multi_head', 'cross', 'causal_self', 'causal_multi_head')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance du mécanisme d'attention
    
    Examples:
        ```python
        # Self-Attention
        attn = create_attention(
            'self',
            embed_dim=256,
            num_heads=8,
            dropout=0.1
        )
        
        # Multi-Head Attention
        attn = create_attention(
            'multi_head',
            embed_dim=256,
            num_heads=8,
            dropout=0.1
        )
        
        # Cross-Attention
        attn = create_attention(
            'cross',
            embed_dim=256,
            num_heads=8,
            dropout=0.1
        )
        
        # Causal Self-Attention
        attn = create_attention(
            'causal_self',
            embed_dim=256,
            num_heads=8,
            dropout=0.1
        )
        ```
    """
    attention_type = attention_type.lower()
    
    if attention_type == 'self':
        embed_dim = kwargs.get('embed_dim', 256)
        num_heads = kwargs.get('num_heads', 8)
        dropout = kwargs.get('dropout', 0.1)
        
        return create_self_attention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout,
            **{k: v for k, v in kwargs.items() 
               if k not in ['embed_dim', 'num_heads', 'dropout']}
        )
    
    elif attention_type == 'multi_head':
        embed_dim = kwargs.get('embed_dim', 256)
        num_heads = kwargs.get('num_heads', 8)
        dropout = kwargs.get('dropout', 0.1)
        
        return create_multi_head_attention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout,
            **{k: v for k, v in kwargs.items() 
               if k not in ['embed_dim', 'num_heads', 'dropout']}
        )
    
    elif attention_type == 'cross':
        embed_dim = kwargs.get('embed_dim', 256)
        num_heads = kwargs.get('num_heads', 8)
        dropout = kwargs.get('dropout', 0.1)
        
        return create_cross_attention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout,
            **{k: v for k, v in kwargs.items() 
               if k not in ['embed_dim', 'num_heads', 'dropout']}
        )
    
    elif attention_type == 'causal_self':
        embed_dim = kwargs.get('embed_dim', 256)
        num_heads = kwargs.get('num_heads', 8)
        dropout = kwargs.get('dropout', 0.1)
        
        return create_causal_self_attention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout,
            **{k: v for k, v in kwargs.items() 
               if k not in ['embed_dim', 'num_heads', 'dropout']}
        )
    
    elif attention_type == 'causal_multi_head':
        embed_dim = kwargs.get('embed_dim', 256)
        num_heads = kwargs.get('num_heads', 8)
        dropout = kwargs.get('dropout', 0.1)
        
        return create_causal_multi_head_attention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout,
            **{k: v for k, v in kwargs.items() 
               if k not in ['embed_dim', 'num_heads', 'dropout']}
        )
    
    else:
        raise ValueError(f"Type d'attention non supporté: {attention_type}")


def get_available_attentions() -> List[str]:
    """
    Retourne la liste des mécanismes d'attention disponibles.
    
    Returns:
        List[str]: Liste des types d'attention
    """
    attentions = ['self', 'multi_head', 'cross', 'causal_self', 'causal_multi_head']
    
    try:
        import torch
    except ImportError:
        attentions = []
    
    return attentions


def get_attention_info(attention_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un mécanisme d'attention.
    
    Args:
        attention_type: Type d'attention
    
    Returns:
        Dict[str, Any]: Informations sur l'attention
    """
    info = {
        'self': {
            'name': 'Self-Attention',
            'description': 'Attention intra-séquence où chaque position attend toutes les autres',
            'advantages': [
                'Capture les dépendances globales',
                'Simple à utiliser',
                'Efficace pour les séquences'
            ],
            'disadvantages': [
                'Complexité O(n²)',
                'Peut être lourd pour longues séquences',
                'Sensible aux longueurs variables'
            ],
            'use_cases': [
                'Transformers',
                'Encodage de séquences',
                'Modèles de langage'
            ]
        },
        'multi_head': {
            'name': 'Multi-Head Attention',
            'description': 'Attention avec plusieurs têtes pour différents sous-espaces',
            'advantages': [
                'Capture différentes relations',
                'Plus expressif',
                'Standard dans les Transformers'
            ],
            'disadvantages': [
                'Plus de paramètres',
                'Plus lent',
                'Nécessite plus de mémoire'
            ],
            'use_cases': [
                'Transformers',
                'Modèles de langage',
                'Vision Transformers'
            ]
        },
        'cross': {
            'name': 'Cross-Attention',
            'description': 'Attention entre deux séquences différentes',
            'advantages': [
                'Fusion d\'informations',
                'Alignement de séquences',
                'Multimodal'
            ],
            'disadvantages': [
                'Complexe',
                'Nécessite deux séquences',
                'Peut être instable'
            ],
            'use_cases': [
                'Encoder-Decoder',
                'Multimodal learning',
                'Fusion de features'
            ]
        },
        'causal_self': {
            'name': 'Causal Self-Attention',
            'description': 'Self-Attention avec masque causal pour auto-régression',
            'advantages': [
                'Auto-régression',
                'Inférence séquentielle',
                'Modèles génératifs'
            ],
            'disadvantages': [
                'Inférence lente',
                'Parallélisation limitée',
                'Biais causal'
            ],
            'use_cases': [
                'Modèles de langage',
                'Génération de séquences',
                'Prédiction auto-régressive'
            ]
        },
        'causal_multi_head': {
            'name': 'Causal Multi-Head Attention',
            'description': 'Multi-Head Attention avec masque causal',
            'advantages': [
                'Auto-régression avec multi-têtes',
                'Meilleure expressivité',
                'Standard dans GPT'
            ],
            'disadvantages': [
                'Lourd',
                'Inférence lente',
                'Beaucoup de paramètres'
            ],
            'use_cases': [
                'GPT-like models',
                'Génération de texte',
                'Prédiction auto-régressive avancée'
            ]
        }
    }
    
    return info.get(attention_type.lower(), {})


def get_attention_recommendation(
    task: str = 'encoding',
    sequence_length: str = 'medium',
    performance: str = 'balanced'
) -> Dict[str, Any]:
    """
    Recommande un mécanisme d'attention selon les besoins.
    
    Args:
        task: Tâche ('encoding', 'decoding', 'fusion', 'generation')
        sequence_length: Longueur des séquences ('short', 'medium', 'long')
        performance: Priorité ('speed', 'balanced', 'accuracy')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    recommendations = {
        'encoding': {
            'short': {
                'speed': {'attention': 'self', 'description': 'Self-Attention pour encodage rapide'},
                'balanced': {'attention': 'multi_head', 'description': 'Multi-Head pour encodage équilibré'},
                'accuracy': {'attention': 'multi_head', 'description': 'Multi-Head pour meilleure précision'},
            },
            'medium': {
                'speed': {'attention': 'self', 'description': 'Self-Attention pour encodage efficace'},
                'balanced': {'attention': 'multi_head', 'description': 'Multi-Head pour encodage équilibré'},
                'accuracy': {'attention': 'multi_head', 'description': 'Multi-Head pour meilleure précision'},
            },
            'long': {
                'speed': {'attention': 'self', 'description': 'Self-Attention pour longues séquences'},
                'balanced': {'attention': 'self', 'description': 'Self-Attention pour équilibre'},
                'accuracy': {'attention': 'multi_head', 'description': 'Multi-Head pour longues séquences'},
            }
        },
        'decoding': {
            'short': {
                'speed': {'attention': 'causal_self', 'description': 'Causal Self pour décodage rapide'},
                'balanced': {'attention': 'causal_multi_head', 'description': 'Causal Multi-Head pour équilibre'},
                'accuracy': {'attention': 'causal_multi_head', 'description': 'Causal Multi-Head pour précision'},
            },
            'medium': {
                'speed': {'attention': 'causal_self', 'description': 'Causal Self pour décodage efficace'},
                'balanced': {'attention': 'causal_multi_head', 'description': 'Causal Multi-Head pour équilibre'},
                'accuracy': {'attention': 'causal_multi_head', 'description': 'Causal Multi-Head pour précision'},
            },
            'long': {
                'speed': {'attention': 'causal_self', 'description': 'Causal Self pour longues séquences'},
                'balanced': {'attention': 'causal_self', 'description': 'Causal Self pour équilibre'},
                'accuracy': {'attention': 'causal_multi_head', 'description': 'Causal Multi-Head pour longues séquences'},
            }
        },
        'fusion': {
            'short': {
                'speed': {'attention': 'cross', 'description': 'Cross-Attention pour fusion rapide'},
                'balanced': {'attention': 'cross', 'description': 'Cross-Attention pour fusion équilibrée'},
                'accuracy': {'attention': 'cross', 'description': 'Cross-Attention pour meilleure fusion'},
            },
            'medium': {
                'speed': {'attention': 'cross', 'description': 'Cross-Attention pour fusion efficace'},
                'balanced': {'attention': 'cross', 'description': 'Cross-Attention pour fusion équilibrée'},
                'accuracy': {'attention': 'cross', 'description': 'Cross-Attention pour meilleure fusion'},
            },
            'long': {
                'speed': {'attention': 'cross', 'description': 'Cross-Attention pour longues séquences'},
                'balanced': {'attention': 'cross', 'description': 'Cross-Attention pour équilibre'},
                'accuracy': {'attention': 'cross', 'description': 'Cross-Attention pour longues séquences'},
            }
        },
        'generation': {
            'short': {
                'speed': {'attention': 'causal_self', 'description': 'Causal Self pour génération rapide'},
                'balanced': {'attention': 'causal_multi_head', 'description': 'Causal Multi-Head pour équilibre'},
                'accuracy': {'attention': 'causal_multi_head', 'description': 'Causal Multi-Head pour précision'},
            },
            'medium': {
                'speed': {'attention': 'causal_self', 'description': 'Causal Self pour génération efficace'},
                'balanced': {'attention': 'causal_multi_head', 'description': 'Causal Multi-Head pour équilibre'},
                'accuracy': {'attention': 'causal_multi_head', 'description': 'Causal Multi-Head pour précision'},
            },
            'long': {
                'speed': {'attention': 'causal_self', 'description': 'Causal Self pour longues séquences'},
                'balanced': {'attention': 'causal_self', 'description': 'Causal Self pour équilibre'},
                'accuracy': {'attention': 'causal_multi_head', 'description': 'Causal Multi-Head pour longues séquences'},
            }
        }
    }
    
    task_lower = task.lower()
    if task_lower not in recommendations:
        task_lower = 'encoding'
    
    seq_len = sequence_length.lower()
    if seq_len not in ['short', 'medium', 'long']:
        seq_len = 'medium'
    
    perf = performance.lower()
    if perf not in ['speed', 'balanced', 'accuracy']:
        perf = 'balanced'
    
    recommendation = recommendations[task_lower][seq_len][perf]
    
    return {
        'task': task_lower,
        'sequence_length': seq_len,
        'performance': perf,
        'recommended_attention': recommendation,
        'alternative_attentions': ['self', 'multi_head', 'cross', 'causal_self', 'causal_multi_head'],
    }


logger.info("Module d'attention initialisé")
