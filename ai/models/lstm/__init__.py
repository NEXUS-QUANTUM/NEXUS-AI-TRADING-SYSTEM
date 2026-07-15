
# ai/models/lstm/__init__.py
"""
NEXUS AI TRADING SYSTEM - LSTM Models Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de modèles LSTM pour la prévision de séries temporelles.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.models.lstm.lstm_model import (
    LSTM,
    LSTMConfig,
    LSTMResult,
    create_lstm,
)

from ai.models.lstm.bilstm_model import (
    BiLSTM,
    BiLSTMConfig,
    BiLSTMResult,
    create_bilstm,
)

from ai.models.lstm.attention_lstm import (
    AttentionLSTM,
    AttentionLSTMConfig,
    AttentionLSTMResult,
    create_attention_lstm,
)

from ai.models.lstm.stacked_lstm import (
    StackedLSTM,
    StackedLSTMConfig,
    StackedLSTMResult,
    create_stacked_lstm,
)

logger = logging.getLogger(__name__)


__all__ = [
    # LSTM Standard
    'LSTM',
    'LSTMConfig',
    'LSTMResult',
    'create_lstm',
    
    # BiLSTM
    'BiLSTM',
    'BiLSTMConfig',
    'BiLSTMResult',
    'create_bilstm',
    
    # Attention LSTM
    'AttentionLSTM',
    'AttentionLSTMConfig',
    'AttentionLSTMResult',
    'create_attention_lstm',
    
    # Stacked LSTM
    'StackedLSTM',
    'StackedLSTMConfig',
    'StackedLSTMResult',
    'create_stacked_lstm',
]


def create_lstm_model(
    model_type: str = 'lstm',
    **kwargs
) -> Any:
    """
    Factory pour créer des modèles LSTM.
    
    Args:
        model_type: Type de modèle ('lstm', 'bilstm', 'attention_lstm', 'stacked_lstm')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance du modèle LSTM
    
    Examples:
        ```python
        # LSTM standard
        model = create_lstm_model(
            'lstm',
            input_size=1,
            hidden_size=128,
            sequence_length=24,
            prediction_length=12
        )
        
        # BiLSTM
        model = create_lstm_model(
            'bilstm',
            input_size=1,
            hidden_size=128,
            bidirectional=True,
            sequence_length=24,
            prediction_length=12
        )
        
        # Attention LSTM
        model = create_lstm_model(
            'attention_lstm',
            input_size=1,
            hidden_size=128,
            attention_type='bahdanau',
            sequence_length=24,
            prediction_length=12
        )
        
        # Stacked LSTM
        model = create_lstm_model(
            'stacked_lstm',
            input_size=1,
            hidden_sizes=[128, 64, 32],
            use_residual=True,
            sequence_length=24,
            prediction_length=12
        )
        ```
    """
    model_type = model_type.lower()
    
    if model_type == 'lstm':
        input_size = kwargs.get('input_size', 1)
        hidden_size = kwargs.get('hidden_size', 128)
        num_layers = kwargs.get('num_layers', 2)
        sequence_length = kwargs.get('sequence_length', 24)
        prediction_length = kwargs.get('prediction_length', 12)
        use_encoder_decoder = kwargs.get('use_encoder_decoder', False)
        
        return create_lstm(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            sequence_length=sequence_length,
            prediction_length=prediction_length,
            use_encoder_decoder=use_encoder_decoder,
            **{k: v for k, v in kwargs.items() 
               if k not in ['input_size', 'hidden_size', 'num_layers',
                           'sequence_length', 'prediction_length', 'use_encoder_decoder']}
        )
    
    elif model_type == 'bilstm':
        input_size = kwargs.get('input_size', 1)
        hidden_size = kwargs.get('hidden_size', 128)
        num_layers = kwargs.get('num_layers', 2)
        sequence_length = kwargs.get('sequence_length', 24)
        prediction_length = kwargs.get('prediction_length', 12)
        bidirectional = kwargs.get('bidirectional', True)
        use_stacked = kwargs.get('use_stacked', False)
        
        return create_bilstm(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            sequence_length=sequence_length,
            prediction_length=prediction_length,
            bidirectional=bidirectional,
            use_stacked=use_stacked,
            **{k: v for k, v in kwargs.items() 
               if k not in ['input_size', 'hidden_size', 'num_layers',
                           'sequence_length', 'prediction_length', 'bidirectional', 'use_stacked']}
        )
    
    elif model_type in ['attention_lstm', 'attention']:
        input_size = kwargs.get('input_size', 1)
        hidden_size = kwargs.get('hidden_size', 128)
        sequence_length = kwargs.get('sequence_length', 24)
        prediction_length = kwargs.get('prediction_length', 12)
        attention_type = kwargs.get('attention_type', 'bahdanau')
        bidirectional = kwargs.get('bidirectional', False)
        
        return create_attention_lstm(
            input_size=input_size,
            hidden_size=hidden_size,
            sequence_length=sequence_length,
            prediction_length=prediction_length,
            attention_type=attention_type,
            bidirectional=bidirectional,
            **{k: v for k, v in kwargs.items() 
               if k not in ['input_size', 'hidden_size', 'sequence_length',
                           'prediction_length', 'attention_type', 'bidirectional']}
        )
    
    elif model_type in ['stacked_lstm', 'stacked']:
        input_size = kwargs.get('input_size', 1)
        hidden_sizes = kwargs.get('hidden_sizes', [128, 64, 32])
        sequence_length = kwargs.get('sequence_length', 24)
        prediction_length = kwargs.get('prediction_length', 12)
        use_encoder_decoder = kwargs.get('use_encoder_decoder', False)
        use_residual = kwargs.get('use_residual', False)
        
        return create_stacked_lstm(
            input_size=input_size,
            hidden_sizes=hidden_sizes,
            sequence_length=sequence_length,
            prediction_length=prediction_length,
            use_encoder_decoder=use_encoder_decoder,
            use_residual=use_residual,
            **{k: v for k, v in kwargs.items() 
               if k not in ['input_size', 'hidden_sizes', 'sequence_length',
                           'prediction_length', 'use_encoder_decoder', 'use_residual']}
        )
    
    else:
        raise ValueError(f"Type de modèle LSTM non supporté: {model_type}")


def get_available_lstm_models() -> List[str]:
    """
    Retourne la liste des modèles LSTM disponibles.
    
    Returns:
        List[str]: Liste des types de modèles
    """
    models = ['lstm', 'bilstm', 'attention_lstm', 'stacked_lstm']
    
    # Vérifier les dépendances
    try:
        import torch
    except ImportError:
        models = []
    
    return models


def get_lstm_model_info(model_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de modèle LSTM.
    
    Args:
        model_type: Type de modèle
    
    Returns:
        Dict[str, Any]: Informations sur le modèle
    """
    info = {
        'lstm': {
            'name': 'LSTM Standard',
            'description': 'Long Short-Term Memory network',
            'advantages': [
                'Simple et efficace',
                'Capte les dépendances à long terme',
                'Bon pour les séries temporelles'
            ],
            'disadvantages': [
                'Peut souffrir de sur-apprentissage',
                'Sensible aux hyperparamètres',
                'Temps d\'entraînement conséquent'
            ],
            'use_cases': [
                'Séries temporelles simples',
                'Prévisions à court terme',
                'Données avec patterns récurrents'
            ]
        },
        'bilstm': {
            'name': 'BiLSTM (Bidirectionnel)',
            'description': 'LSTM bidirectionnel capturant les contextes passé et futur',
            'advantages': [
                'Capture les dépendances bidirectionnelles',
                'Meilleur contexte pour les séquences',
                'Plus riche en informations'
            ],
            'disadvantages': [
                'Plus lent que LSTM standard',
                'Plus de paramètres',
                'Nécessite plus de données'
            ],
            'use_cases': [
                'Séquences où le contexte futur est important',
                'Analyse de séries temporelles complexes',
                'Trading haute fréquence'
            ]
        },
        'attention_lstm': {
            'name': 'Attention LSTM',
            'description': 'LSTM avec mécanisme d\'attention',
            'advantages': [
                'Interprétable (visualisation de l\'attention)',
                'Se concentre sur les parties importantes',
                'Meilleure performance sur les longues séquences'
            ],
            'disadvantages': [
                'Plus complexe',
                'Plus lent',
                'Nécessite plus de données'
            ],
            'use_cases': [
                'Longues séquences temporelles',
                'Quand l\'interprétabilité est importante',
                'Patterns complexes avec moments clés'
            ]
        },
        'stacked_lstm': {
            'name': 'Stacked LSTM',
            'description': 'LSTM avec plusieurs couches empilées',
            'advantages': [
                'Extraction hiérarchique des features',
                'Capacité de représentation élevée',
                'Meilleure généralisation avec résidus'
            ],
            'disadvantages': [
                'Très lent à l\'entraînement',
                'Beaucoup de paramètres',
                'Risque de sur-apprentissage élevé'
            ],
            'use_cases': [
                'Données très complexes',
                'Grandes séries temporelles',
                'Quand la profondeur est nécessaire'
            ]
        }
    }
    
    return info.get(model_type.lower(), {})


def get_lstm_recommendation(
    data_length: int,
    complexity: str = 'medium',
    interpretability: bool = False,
    speed: str = 'balanced'
) -> str:
    """
    Recommande un modèle LSTM selon les besoins.
    
    Args:
        data_length: Nombre de points de données
        complexity: Complexité des données ('simple', 'medium', 'complex')
        interpretability: Nécessité d'interprétabilité
        speed: Priorité ('fast', 'balanced', 'accurate')
    
    Returns:
        str: Type de modèle recommandé
    """
    if data_length < 100:
        return 'lstm'
    
    if interpretability:
        return 'attention_lstm'
    
    if speed == 'fast':
        return 'lstm'
    
    if complexity == 'simple':
        return 'lstm'
    
    if complexity == 'complex':
        if data_length > 1000:
            return 'stacked_lstm'
        else:
            return 'bilstm'
    
    if speed == 'accurate':
        if data_length > 500:
            return 'stacked_lstm'
        else:
            return 'bilstm'
    
    # Par défaut
    if data_length > 500:
        return 'bilstm'
    return 'lstm'


logger.info("Module LSTM initialisé")
