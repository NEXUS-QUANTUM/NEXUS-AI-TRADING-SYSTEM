
# ai/models/forecasting/__init__.py
"""
NEXUS AI TRADING SYSTEM - Forecasting Models Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de modèles de prévision pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.models.forecasting.arima_model import (
    ARIMAModel,
    ARIMAConfig,
    ARIMAResult,
    create_arima_model,
)

from ai.models.forecasting.prophet_model import (
    ProphetModel,
    ProphetConfig,
    ProphetResult,
    create_prophet_model,
)

from ai.models.forecasting.deepar_model import (
    DeepARModel,
    DeepARConfig,
    DeepARResult,
    create_deepar_model,
)

from ai.models.forecasting.temporal_fusion import (
    TemporalFusionModel,
    TemporalFusionConfig,
    TemporalFusionResult,
    create_temporal_fusion_model,
)

logger = logging.getLogger(__name__)


__all__ = [
    # ARIMA
    'ARIMAModel',
    'ARIMAConfig',
    'ARIMAResult',
    'create_arima_model',
    
    # Prophet
    'ProphetModel',
    'ProphetConfig',
    'ProphetResult',
    'create_prophet_model',
    
    # DeepAR
    'DeepARModel',
    'DeepARConfig',
    'DeepARResult',
    'create_deepar_model',
    
    # Temporal Fusion Transformer
    'TemporalFusionModel',
    'TemporalFusionConfig',
    'TemporalFusionResult',
    'create_temporal_fusion_model',
]


def create_forecasting_model(
    model_type: str = 'arima',
    **kwargs
) -> Any:
    """
    Factory pour créer des modèles de prévision.
    
    Args:
        model_type: Type de modèle ('arima', 'prophet', 'deepar', 'temporal_fusion')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance du modèle de prévision
    
    Examples:
        ```python
        # Création d'un modèle ARIMA
        model = create_forecasting_model(
            'arima',
            order=(1, 1, 1),
            seasonal_order=(0, 0, 0, 0)
        )
        
        # Création d'un modèle Prophet
        model = create_forecasting_model(
            'prophet',
            growth='linear',
            weekly_seasonality=True,
            yearly_seasonality=True
        )
        
        # Création d'un modèle DeepAR
        model = create_forecasting_model(
            'deepar',
            hidden_size=128,
            context_length=24,
            prediction_length=12,
            epochs=100
        )
        
        # Création d'un modèle Temporal Fusion Transformer
        model = create_forecasting_model(
            'temporal_fusion',
            hidden_size=128,
            num_heads=4,
            context_length=24,
            prediction_length=12,
            quantiles=[0.1, 0.5, 0.9]
        )
        ```
    """
    model_type = model_type.lower()
    
    if model_type == 'arima':
        order = kwargs.get('order', (1, 1, 1))
        seasonal_order = kwargs.get('seasonal_order', (0, 0, 0, 0))
        trend = kwargs.get('trend', None)
        
        return create_arima_model(
            order=order,
            seasonal_order=seasonal_order,
            trend=trend,
            **{k: v for k, v in kwargs.items() 
               if k not in ['order', 'seasonal_order', 'trend']}
        )
    
    elif model_type == 'prophet':
        growth = kwargs.get('growth', 'linear')
        seasonality_mode = kwargs.get('seasonality_mode', 'additive')
        weekly_seasonality = kwargs.get('weekly_seasonality', True)
        yearly_seasonality = kwargs.get('yearly_seasonality', True)
        changepoint_prior_scale = kwargs.get('changepoint_prior_scale', 0.05)
        interval_width = kwargs.get('interval_width', 0.95)
        
        return create_prophet_model(
            growth=growth,
            seasonality_mode=seasonality_mode,
            weekly_seasonality=weekly_seasonality,
            yearly_seasonality=yearly_seasonality,
            changepoint_prior_scale=changepoint_prior_scale,
            interval_width=interval_width,
            **{k: v for k, v in kwargs.items() 
               if k not in ['growth', 'seasonality_mode', 'weekly_seasonality',
                           'yearly_seasonality', 'changepoint_prior_scale', 'interval_width']}
        )
    
    elif model_type == 'deepar':
        input_size = kwargs.get('input_size', 1)
        hidden_size = kwargs.get('hidden_size', 128)
        num_layers = kwargs.get('num_layers', 2)
        context_length = kwargs.get('context_length', 24)
        prediction_length = kwargs.get('prediction_length', 12)
        learning_rate = kwargs.get('learning_rate', 0.001)
        epochs = kwargs.get('epochs', 100)
        
        return create_deepar_model(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            context_length=context_length,
            prediction_length=prediction_length,
            learning_rate=learning_rate,
            epochs=epochs,
            **{k: v for k, v in kwargs.items() 
               if k not in ['input_size', 'hidden_size', 'num_layers',
                           'context_length', 'prediction_length', 'learning_rate', 'epochs']}
        )
    
    elif model_type in ['temporal_fusion', 'temporal_fusion_transformer', 'tft']:
        input_size = kwargs.get('input_size', 1)
        hidden_size = kwargs.get('hidden_size', 128)
        num_heads = kwargs.get('num_heads', 4)
        context_length = kwargs.get('context_length', 24)
        prediction_length = kwargs.get('prediction_length', 12)
        quantiles = kwargs.get('quantiles', [0.1, 0.5, 0.9])
        learning_rate = kwargs.get('learning_rate', 0.001)
        epochs = kwargs.get('epochs', 100)
        
        return create_temporal_fusion_model(
            input_size=input_size,
            hidden_size=hidden_size,
            num_heads=num_heads,
            context_length=context_length,
            prediction_length=prediction_length,
            quantiles=quantiles,
            learning_rate=learning_rate,
            epochs=epochs,
            **{k: v for k, v in kwargs.items() 
               if k not in ['input_size', 'hidden_size', 'num_heads',
                           'context_length', 'prediction_length', 'quantiles',
                           'learning_rate', 'epochs']}
        )
    
    else:
        raise ValueError(f"Type de modèle de prévision non supporté: {model_type}")


def get_available_forecasting_models() -> List[str]:
    """
    Retourne la liste des modèles de prévision disponibles.
    
    Returns:
        List[str]: Liste des types de modèles
    """
    models = ['arima', 'prophet', 'deepar', 'temporal_fusion']
    
    # Vérifier les dépendances
    try:
        import statsmodels
    except ImportError:
        models.remove('arima') if 'arima' in models else None
    
    try:
        import prophet
    except ImportError:
        models.remove('prophet') if 'prophet' in models else None
    
    try:
        import torch
    except ImportError:
        models.remove('deepar') if 'deepar' in models else None
        models.remove('temporal_fusion') if 'temporal_fusion' in models else None
    
    return models


def get_forecasting_model_info(model_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de modèle de prévision.
    
    Args:
        model_type: Type de modèle
    
    Returns:
        Dict[str, Any]: Informations sur le modèle
    """
    info = {
        'arima': {
            'name': 'ARIMA',
            'description': 'AutoRegressive Integrated Moving Average',
            'advantages': [
                'Simple et interprétable',
                'Bon pour les séries stationnaires',
                'Peu de données nécessaires'
            ],
            'disadvantages': [
                'Nécessite des données stationnaires',
                'Paramètres à choisir manuellement',
                'Pas de support des saisonnalités complexes'
            ],
            'use_cases': [
                'Séries temporelles courtes',
                'Données financières stationnaires',
                'Prévisions à court terme'
            ]
        },
        'prophet': {
            'name': 'Prophet (Facebook)',
            'description': 'Modèle de prévision avec saisonnalités et jours fériés',
            'advantages': [
                'Gère les saisonnalités automatiquement',
                'Robuste aux données manquantes',
                'Intègre les jours fériés'
            ],
            'disadvantages': [
                'Nécessite des données journalières',
                'Moins précis sur les séries non-saisonnières',
                'Peut être lent sur de grandes données'
            ],
            'use_cases': [
                'Séries avec saisonnalités quotidiennes/hebdomadaires',
                'Données avec jours fériés',
                'Prévisions à moyen terme'
            ]
        },
        'deepar': {
            'name': 'DeepAR (Amazon)',
            'description': 'Modèle probabiliste basé sur LSTM',
            'advantages': [
                'Prévisions probabilistes',
                'Support des séries multiples',
                'Apprentissage des corrélations'
            ],
            'disadvantages': [
                'Nécessite beaucoup de données',
                'Complexe à entraîner',
                'Black-box'
            ],
            'use_cases': [
                'Séries temporelles longues',
                'Prévisions probabilistes',
                'Données avec patterns complexes'
            ]
        },
        'temporal_fusion': {
            'name': 'Temporal Fusion Transformer',
            'description': 'Modèle de prévision avec attention multi-têtes',
            'advantages': [
                'Capte les dépendances longues',
                'Prévisions probabilistes avec quantiles',
                'Attention interprétable'
            ],
            'disadvantages': [
                'Nécessite beaucoup de données',
                'Complexe et lourd',
                'Temps d\'entraînement long'
            ],
            'use_cases': [
                'Séries temporelles très longues',
                'Prévisions probabilistes avancées',
                'Données avec patterns complexes'
            ]
        }
    }
    
    return info.get(model_type.lower(), {})


def get_forecasting_recommendation(
    data_length: int,
    seasonality: Optional[str] = None,
    probabilistic: bool = False,
    performance: str = 'balanced'
) -> str:
    """
    Recommande un modèle de prévision selon les besoins.
    
    Args:
        data_length: Nombre de points de données
        seasonality: Type de saisonnalité ('daily', 'weekly', 'yearly', None)
        probabilistic: Nécessité de prévisions probabilistes
        performance: Priorité ('speed', 'accuracy', 'balanced')
    
    Returns:
        str: Type de modèle recommandé
    """
    if data_length < 50:
        return 'arima'
    
    if data_length < 200 and seasonality:
        return 'prophet'
    
    if probabilistic:
        if data_length > 500:
            return 'temporal_fusion'
        else:
            return 'deepar'
    
    if seasonality == 'daily' or seasonality == 'weekly':
        return 'prophet'
    
    if data_length > 1000:
        return 'temporal_fusion'
    
    if performance == 'speed':
        return 'arima'
    elif performance == 'accuracy':
        if data_length > 300:
            return 'deepar'
        return 'prophet'
    else:
        if seasonality:
            return 'prophet'
        return 'arima'


logger.info("Module de modèles de prévision initialisé")
