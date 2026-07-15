
# ai/prediction/__init__.py
"""
NEXUS AI TRADING SYSTEM - Prediction Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de prédiction pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.prediction.ensemble_predictor import (
    EnsemblePredictor,
    EnsemblePredictorConfig,
    EnsemblePredictorResult,
    create_ensemble_predictor,
)

from ai.prediction.market_prediction import (
    MarketPredictionEngine,
    MarketPredictionConfig,
    MarketPrediction,
    create_market_prediction,
)

from ai.prediction.prediction_cache import (
    PredictionCache,
    PredictionCacheConfig,
    CacheEntry,
    CachedPredictor,
    create_prediction_cache,
)

from ai.prediction.prediction_pipeline import (
    PredictionPipeline,
    PredictionPipelineConfig,
    PredictionTask,
    PredictionResult,
    create_prediction_pipeline,
)

from ai.prediction.price_prediction import (
    PricePredictor,
    PricePredictionConfig,
    PricePredictionResult,
    create_price_predictor,
)

from ai.prediction.sentiment_prediction import (
    SentimentPredictor,
    SentimentPredictionConfig,
    SentimentResult,
    create_sentiment_predictor,
)

from ai.prediction.trend_prediction import (
    TrendPredictor,
    TrendPredictionConfig,
    TrendPredictionResult,
    create_trend_predictor,
)

from ai.prediction.volatility_prediction import (
    VolatilityPredictor,
    VolatilityPredictionConfig,
    VolatilityPredictionResult,
    create_volatility_predictor,
)

logger = logging.getLogger(__name__)


__all__ = [
    # Ensemble Predictor
    'EnsemblePredictor',
    'EnsemblePredictorConfig',
    'EnsemblePredictorResult',
    'create_ensemble_predictor',
    
    # Market Prediction
    'MarketPredictionEngine',
    'MarketPredictionConfig',
    'MarketPrediction',
    'create_market_prediction',
    
    # Prediction Cache
    'PredictionCache',
    'PredictionCacheConfig',
    'CacheEntry',
    'CachedPredictor',
    'create_prediction_cache',
    
    # Prediction Pipeline
    'PredictionPipeline',
    'PredictionPipelineConfig',
    'PredictionTask',
    'PredictionResult',
    'create_prediction_pipeline',
    
    # Price Prediction
    'PricePredictor',
    'PricePredictionConfig',
    'PricePredictionResult',
    'create_price_predictor',
    
    # Sentiment Prediction
    'SentimentPredictor',
    'SentimentPredictionConfig',
    'SentimentResult',
    'create_sentiment_predictor',
    
    # Trend Prediction
    'TrendPredictor',
    'TrendPredictionConfig',
    'TrendPredictionResult',
    'create_trend_predictor',
    
    # Volatility Prediction
    'VolatilityPredictor',
    'VolatilityPredictionConfig',
    'VolatilityPredictionResult',
    'create_volatility_predictor',
]


def create_predictor(
    predictor_type: str = 'price',
    **kwargs
) -> Any:
    """
    Factory pour créer des prédicteurs.
    
    Args:
        predictor_type: Type de prédicteur ('price', 'trend', 'volatility', 'sentiment', 'market', 'ensemble')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance du prédicteur
    
    Examples:
        ```python
        # Price predictor
        predictor = create_predictor(
            'price',
            sequence_length=24,
            prediction_length=1,
            hidden_size=128
        )
        
        # Trend predictor
        predictor = create_predictor(
            'trend',
            lookback_window=50,
            model_type='xgboost'
        )
        
        # Volatility predictor
        predictor = create_predictor(
            'volatility',
            lookback_window=50,
            model_type='xgboost'
        )
        
        # Sentiment predictor
        predictor = create_predictor(
            'sentiment',
            model_type='finbert',
            use_ensemble=True
        )
        
        # Market predictor
        predictor = create_predictor(
            'market',
            prediction_horizon=24,
            use_ensemble=True
        )
        
        # Ensemble predictor
        predictor = create_predictor(
            'ensemble',
            model_types=['xgboost', 'random_forest'],
            ensemble_type='weighted'
        )
        ```
    """
    predictor_type = predictor_type.lower()
    
    if predictor_type == 'price':
        sequence_length = kwargs.get('sequence_length', 24)
        prediction_length = kwargs.get('prediction_length', 1)
        hidden_size = kwargs.get('hidden_size', 128)
        
        return create_price_predictor(
            sequence_length=sequence_length,
            prediction_length=prediction_length,
            hidden_size=hidden_size,
            **{k: v for k, v in kwargs.items() 
               if k not in ['sequence_length', 'prediction_length', 'hidden_size']}
        )
    
    elif predictor_type == 'trend':
        lookback_window = kwargs.get('lookback_window', 50)
        prediction_horizon = kwargs.get('prediction_horizon', 1)
        model_type = kwargs.get('model_type', 'xgboost')
        
        return create_trend_predictor(
            lookback_window=lookback_window,
            prediction_horizon=prediction_horizon,
            model_type=model_type,
            **{k: v for k, v in kwargs.items() 
               if k not in ['lookback_window', 'prediction_horizon', 'model_type']}
        )
    
    elif predictor_type == 'volatility':
        lookback_window = kwargs.get('lookback_window', 50)
        prediction_horizon = kwargs.get('prediction_horizon', 1)
        model_type = kwargs.get('model_type', 'xgboost')
        
        return create_volatility_predictor(
            lookback_window=lookback_window,
            prediction_horizon=prediction_horizon,
            model_type=model_type,
            **{k: v for k, v in kwargs.items() 
               if k not in ['lookback_window', 'prediction_horizon', 'model_type']}
        )
    
    elif predictor_type == 'sentiment':
        model_type = kwargs.get('model_type', 'finbert')
        use_ensemble = kwargs.get('use_ensemble', False)
        
        return create_sentiment_predictor(
            model_type=model_type,
            use_ensemble=use_ensemble,
            **{k: v for k, v in kwargs.items() 
               if k not in ['model_type', 'use_ensemble']}
        )
    
    elif predictor_type == 'market':
        prediction_horizon = kwargs.get('prediction_horizon', 24)
        lookback_window = kwargs.get('lookback_window', 168)
        use_ensemble = kwargs.get('use_ensemble', True)
        
        return create_market_prediction(
            prediction_horizon=prediction_horizon,
            lookback_window=lookback_window,
            use_ensemble=use_ensemble,
            **{k: v for k, v in kwargs.items() 
               if k not in ['prediction_horizon', 'lookback_window', 'use_ensemble']}
        )
    
    elif predictor_type == 'ensemble':
        models = kwargs.get('models', None)
        model_types = kwargs.get('model_types', None)
        ensemble_type = kwargs.get('ensemble_type', 'weighted')
        weights = kwargs.get('weights', None)
        
        return create_ensemble_predictor(
            models=models,
            model_types=model_types,
            ensemble_type=ensemble_type,
            weights=weights,
            **{k: v for k, v in kwargs.items() 
               if k not in ['models', 'model_types', 'ensemble_type', 'weights']}
        )
    
    else:
        raise ValueError(f"Type de prédicteur non supporté: {predictor_type}")


def get_available_predictors() -> List[str]:
    """
    Retourne la liste des prédicteurs disponibles.
    
    Returns:
        List[str]: Liste des types de prédicteurs
    """
    predictors = ['price', 'trend', 'volatility', 'sentiment', 'market', 'ensemble']
    
    try:
        import torch
    except ImportError:
        predictors.remove('price') if 'price' in predictors else None
        predictors.remove('sentiment') if 'sentiment' in predictors else None
    
    try:
        import xgboost
    except ImportError:
        # Les prédicteurs basés sur XGBoost seront limités
        pass
    
    return predictors


def get_predictor_info(predictor_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de prédicteur.
    
    Args:
        predictor_type: Type de prédicteur
    
    Returns:
        Dict[str, Any]: Informations sur le prédicteur
    """
    info = {
        'price': {
            'name': 'Price Predictor',
            'description': 'Prédiction des prix futurs avec LSTM',
            'output': 'Prix prédit',
            'use_cases': ['Prédiction de prix', 'Trading directionnel', 'Market timing'],
            'requires': ['PyTorch', 'Données historiques'],
        },
        'trend': {
            'name': 'Trend Predictor',
            'description': 'Prédiction de la tendance du marché',
            'output': 'Direction (up/down/sideways)',
            'use_cases': ['Analyse de tendance', 'Stratégies de suivi de tendance', 'Market sentiment'],
            'requires': ['XGBoost', 'Données historiques'],
        },
        'volatility': {
            'name': 'Volatility Predictor',
            'description': 'Prédiction de la volatilité future',
            'output': 'Volatilité annualisée',
            'use_cases': ['Risk management', 'Option pricing', 'Position sizing'],
            'requires': ['XGBoost/GARCH', 'Données historiques'],
        },
        'sentiment': {
            'name': 'Sentiment Predictor',
            'description': 'Analyse de sentiment des textes financiers',
            'output': 'Sentiment (positive/negative/neutral)',
            'use_cases': ['Analyse de news', 'Market sentiment', 'Social media analysis'],
            'requires': ['Transformers', 'Modèle FinBERT'],
        },
        'market': {
            'name': 'Market Predictor',
            'description': 'Prédiction de marché multi-modèles',
            'output': 'Prédiction de marché complète',
            'use_cases': ['Prédiction multi-actifs', 'Analyse globale', 'Système de trading'],
            'requires': ['PyTorch', 'XGBoost', 'Données historiques'],
        },
        'ensemble': {
            'name': 'Ensemble Predictor',
            'description': 'Combinaison de multiples prédicteurs',
            'output': 'Prédiction agrégée',
            'use_cases': ['Amélioration de précision', 'Réduction de variance', 'Robustesse'],
            'requires': ['Multiples modèles'],
        }
    }
    
    return info.get(predictor_type.lower(), {})


def get_predictor_recommendation(
    task: str = 'price_prediction',
    data_type: str = 'historical',
    accuracy: str = 'balanced',
    speed: str = 'balanced'
) -> Dict[str, Any]:
    """
    Recommande un prédicteur selon les besoins.
    
    Args:
        task: Tâche ('price_prediction', 'trend_analysis', 'volatility_forecast', 'sentiment_analysis', 'market_analysis')
        data_type: Type de données ('historical', 'text', 'mixed')
        accuracy: Priorité ('speed', 'balanced', 'accuracy')
        speed: Priorité de vitesse ('fast', 'balanced', 'slow')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    recommendations = {
        'price_prediction': {
            'historical': {
                'speed': {'predictor': 'price', 'description': 'Price predictor pour prédiction rapide'},
                'balanced': {'predictor': 'price', 'description': 'Price predictor équilibré'},
                'accuracy': {'predictor': 'ensemble', 'description': 'Ensemble pour meilleure précision'},
            },
            'mixed': {
                'speed': {'predictor': 'price', 'description': 'Price predictor pour données mixtes'},
                'balanced': {'predictor': 'market', 'description': 'Market predictor pour données mixtes'},
                'accuracy': {'predictor': 'ensemble', 'description': 'Ensemble pour précision'},
            }
        },
        'trend_analysis': {
            'historical': {
                'speed': {'predictor': 'trend', 'description': 'Trend predictor rapide'},
                'balanced': {'predictor': 'trend', 'description': 'Trend predictor équilibré'},
                'accuracy': {'predictor': 'ensemble', 'description': 'Ensemble pour tendance'},
            },
            'mixed': {
                'speed': {'predictor': 'trend', 'description': 'Trend predictor rapide'},
                'balanced': {'predictor': 'market', 'description': 'Market predictor complet'},
                'accuracy': {'predictor': 'ensemble', 'description': 'Ensemble pour précision'},
            }
        },
        'volatility_forecast': {
            'historical': {
                'speed': {'predictor': 'volatility', 'description': 'Volatility predictor rapide'},
                'balanced': {'predictor': 'volatility', 'description': 'Volatility predictor équilibré'},
                'accuracy': {'predictor': 'ensemble', 'description': 'Ensemble pour volatilité'},
            }
        },
        'sentiment_analysis': {
            'text': {
                'speed': {'predictor': 'sentiment', 'description': 'Sentiment predictor rapide'},
                'balanced': {'predictor': 'sentiment', 'description': 'Sentiment predictor équilibré'},
                'accuracy': {'predictor': 'sentiment', 'description': 'Sentiment predictor précis'},
            },
            'mixed': {
                'speed': {'predictor': 'sentiment', 'description': 'Sentiment predictor rapide'},
                'balanced': {'predictor': 'market', 'description': 'Market predictor complet'},
                'accuracy': {'predictor': 'ensemble', 'description': 'Ensemble pour précision'},
            }
        }
    }
    
    task_lower = task.lower()
    if task_lower not in recommendations:
        task_lower = 'price_prediction'
    
    data_type_lower = data_type.lower()
    if data_type_lower not in recommendations[task_lower]:
        data_type_lower = 'historical'
    
    accuracy_lower = accuracy.lower()
    if accuracy_lower not in ['speed', 'balanced', 'accuracy']:
        accuracy_lower = 'balanced'
    
    recommendation = recommendations[task_lower][data_type_lower][accuracy_lower]
    
    # Ajustement pour la vitesse
    if speed == 'fast' and recommendation['predictor'] == 'ensemble':
        recommendation['predictor'] = 'price'
        recommendation['description'] = 'Price predictor pour vitesse maximale'
    
    return {
        'task': task_lower,
        'data_type': data_type_lower,
        'accuracy': accuracy_lower,
        'speed': speed,
        'recommended_predictor': recommendation,
        'alternative_predictors': ['price', 'trend', 'volatility', 'sentiment', 'market', 'ensemble'],
    }


logger.info("Module de prédiction initialisé")
