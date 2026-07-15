
# ai/models/__init__.py
"""
NEXUS AI TRADING SYSTEM - Models Module
Copyright © 2026 NEXUS QUANTUM LTD

Module central des modèles d'IA pour le trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.models.base_model import (
    BaseModel,
    BaseRegressor,
    BaseClassifier,
    BaseForecaster,
    BaseEnsemble,
    ModelMetadata,
    PredictionResult,
)

# Sous-modules
from ai.models import ensemble
from ai.models import forecasting
from ai.models import lstm
from ai.models import pretrained
from ai.models import reinforcement
from ai.models import transformers
from ai.models import volatility

logger = logging.getLogger(__name__)


__all__ = [
    # Classes de base
    'BaseModel',
    'BaseRegressor',
    'BaseClassifier',
    'BaseForecaster',
    'BaseEnsemble',
    'ModelMetadata',
    'PredictionResult',
    
    # Sous-modules
    'ensemble',
    'forecasting',
    'lstm',
    'pretrained',
    'reinforcement',
    'transformers',
    'volatility',
]


def get_available_model_types() -> Dict[str, List[str]]:
    """
    Retourne la liste des types de modèles disponibles par catégorie.
    
    Returns:
        Dict[str, List[str]]: Types de modèles par catégorie
    """
    return {
        'ensemble': ['bagging', 'voting', 'stacking'],
        'forecasting': ['arima', 'prophet', 'deepar', 'temporal_fusion'],
        'lstm': ['lstm', 'bilstm', 'attention_lstm', 'stacked_lstm'],
        'pretrained': ['finbert', 'bloomberg_bert', 'sentence_transformer'],
        'reinforcement': ['dqn', 'ppo', 'sac', 'td3'],
        'transformers': ['transformer', 'informer', 'autoformer', 'patchtst'],
        'volatility': ['garch', 'realized', 'stochastic', 'forecast'],
    }


def get_model_info(model_category: str, model_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un modèle spécifique.
    
    Args:
        model_category: Catégorie du modèle
        model_type: Type de modèle
    
    Returns:
        Dict[str, Any]: Informations sur le modèle
    """
    category_info = {
        'ensemble': ensemble.get_ensemble_info,
        'forecasting': forecasting.get_forecasting_model_info,
        'lstm': lstm.get_lstm_model_info,
        'pretrained': pretrained.get_pretrained_model_info,
        'reinforcement': reinforcement.get_rl_agent_info,
        'transformers': transformers.get_transformer_model_info,
        'volatility': volatility.get_volatility_model_info,
    }
    
    if model_category in category_info:
        try:
            return category_info[model_category](model_type)
        except:
            pass
    
    return {
        'name': model_type.capitalize(),
        'description': f"Modèle {model_type} dans la catégorie {model_category}",
        'advantages': ['À documenter'],
        'disadvantages': ['À documenter'],
        'use_cases': ['À documenter'],
    }


def create_model(
    model_category: str,
    model_type: str,
    **kwargs
) -> Any:
    """
    Factory unifiée pour créer des modèles d'IA.
    
    Args:
        model_category: Catégorie du modèle ('ensemble', 'forecasting', 'lstm', 'pretrained', 'reinforcement', 'transformers', 'volatility')
        model_type: Type de modèle spécifique
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance du modèle
    
    Examples:
        ```python
        # Créer un modèle LSTM
        model = create_model('lstm', 'lstm', input_size=1, hidden_size=128)
        
        # Créer un modèle Prophet
        model = create_model('forecasting', 'prophet', weekly_seasonality=True)
        
        # Créer un agent DQN
        agent = create_model('reinforcement', 'dqn', state_dim=10, action_dim=3)
        
        # Créer un modèle Transformer
        model = create_model('transformers', 'transformer', input_size=1, hidden_size=128)
        ```
    """
    model_category = model_category.lower()
    model_type = model_type.lower()
    
    if model_category == 'ensemble':
        return ensemble.create_ensemble(model_type, **kwargs)
    
    elif model_category == 'forecasting':
        return forecasting.create_forecasting_model(model_type, **kwargs)
    
    elif model_category == 'lstm':
        return lstm.create_lstm_model(model_type, **kwargs)
    
    elif model_category == 'pretrained':
        return pretrained.load_pretrained_model(model_type, **kwargs)
    
    elif model_category == 'reinforcement':
        return reinforcement.create_rl_agent(model_type, **kwargs)
    
    elif model_category == 'transformers':
        return transformers.create_transformer_model(model_type, **kwargs)
    
    elif model_category == 'volatility':
        return volatility.create_volatility_model(model_type, **kwargs)
    
    else:
        raise ValueError(f"Catégorie de modèle non supportée: {model_category}")


def get_recommendation(
    problem_type: str,
    data_type: str = 'timeseries',
    data_size: str = 'medium',
    interpretability: bool = False,
    performance: str = 'balanced'
) -> Dict[str, Any]:
    """
    Recommande un modèle selon les besoins.
    
    Args:
        problem_type: Type de problème ('regression', 'classification', 'forecasting', 'rl', 'volatility')
        data_type: Type de données ('timeseries', 'tabular', 'text')
        data_size: Taille des données ('small', 'medium', 'large')
        interpretability: Nécessité d'interprétabilité
        performance: Priorité ('speed', 'balanced', 'accuracy')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    recommendations = {
        'forecasting': {
            'small': {
                'speed': {'category': 'forecasting', 'model': 'arima', 'description': 'ARIMA pour petites données'},
                'balanced': {'category': 'forecasting', 'model': 'prophet', 'description': 'Prophet pour équilibre'},
                'accuracy': {'category': 'forecasting', 'model': 'prophet', 'description': 'Prophet pour précision'},
            },
            'medium': {
                'speed': {'category': 'forecasting', 'model': 'lstm', 'description': 'LSTM pour données moyennes'},
                'balanced': {'category': 'forecasting', 'model': 'deepar', 'description': 'DeepAR pour équilibre'},
                'accuracy': {'category': 'transformers', 'model': 'transformer', 'description': 'Transformer pour précision'},
            },
            'large': {
                'speed': {'category': 'transformers', 'model': 'patchtst', 'description': 'PatchTST pour grandes données'},
                'balanced': {'category': 'transformers', 'model': 'informer', 'description': 'Informer pour équilibre'},
                'accuracy': {'category': 'transformers', 'model': 'autoformer', 'description': 'Autoformer pour précision'},
            }
        },
        'volatility': {
            'small': {
                'speed': {'category': 'volatility', 'model': 'garch', 'description': 'GARCH pour petite volatilité'},
                'balanced': {'category': 'volatility', 'model': 'garch', 'description': 'GARCH pour équilibre'},
                'accuracy': {'category': 'volatility', 'model': 'realized', 'description': 'Realized pour précision'},
            },
            'medium': {
                'speed': {'category': 'volatility', 'model': 'realized', 'description': 'Realized pour données moyennes'},
                'balanced': {'category': 'volatility', 'model': 'garch', 'description': 'GARCH pour équilibre'},
                'accuracy': {'category': 'volatility', 'model': 'stochastic', 'description': 'Stochastic pour précision'},
            },
            'large': {
                'speed': {'category': 'volatility', 'model': 'forecast', 'description': 'ML Forecast pour grandes données'},
                'balanced': {'category': 'volatility', 'model': 'forecast', 'description': 'ML Forecast pour équilibre'},
                'accuracy': {'category': 'volatility', 'model': 'stochastic', 'description': 'Stochastic pour précision'},
            }
        },
        'reinforcement': {
            'discrete': {
                'speed': {'category': 'reinforcement', 'model': 'dqn', 'description': 'DQN pour actions discrètes'},
                'balanced': {'category': 'reinforcement', 'model': 'dqn', 'description': 'DQN pour équilibre'},
                'accuracy': {'category': 'reinforcement', 'model': 'ppo', 'description': 'PPO pour précision'},
            },
            'continuous': {
                'speed': {'category': 'reinforcement', 'model': 'sac', 'description': 'SAC pour actions continues'},
                'balanced': {'category': 'reinforcement', 'model': 'sac', 'description': 'SAC pour équilibre'},
                'accuracy': {'category': 'reinforcement', 'model': 'td3', 'description': 'TD3 pour précision'},
            }
        },
        'nlp': {
            'small': {
                'speed': {'category': 'pretrained', 'model': 'finbert', 'description': 'FinBERT pour NLP finance'},
                'balanced': {'category': 'pretrained', 'model': 'finbert', 'description': 'FinBERT pour équilibre'},
                'accuracy': {'category': 'pretrained', 'model': 'bloomberg_bert', 'description': 'Bloomberg BERT pour précision'},
            },
            'large': {
                'speed': {'category': 'pretrained', 'model': 'finbert', 'description': 'FinBERT pour grandes données'},
                'balanced': {'category': 'pretrained', 'model': 'bloomberg_bert', 'description': 'Bloomberg BERT pour équilibre'},
                'accuracy': {'category': 'pretrained', 'model': 'bloomberg_bert', 'description': 'Bloomberg BERT pour précision'},
            }
        }
    }
    
    # Sélectionner la recommandation appropriée
    if problem_type in recommendations:
        problem_rec = recommendations[problem_type]
        
        if problem_type == 'reinforcement':
            action_space = kwargs.get('action_space', 'discrete')
            if action_space in problem_rec:
                return problem_rec[action_space][performance]
        
        elif problem_type == 'volatility':
            if data_size in problem_rec:
                return problem_rec[data_size][performance]
        
        else:
            if data_size in problem_rec:
                return problem_rec[data_size][performance]
    
    # Recommandation par défaut
    return {
        'category': 'forecasting',
        'model': 'prophet',
        'description': 'Prophet pour approche par défaut'
    }


logger.info("Module de modèles initialisé")
