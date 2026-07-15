# ai/models/volatility/__init__.py
"""
NEXUS AI TRADING SYSTEM - Volatility Models Module
Copyright © 2026 NEXUS QUANTUM LTD

Module de modèles de volatilité pour l'IA de trading.
"""

import logging
from typing import Optional, List, Dict, Any

from ai.models.volatility.garch_model import (
    GARCHModel,
    GARCHConfig,
    GARCHResult,
    create_garch_model,
)

from ai.models.volatility.realized_volatility import (
    RealizedVolatility,
    RealizedVolatilityConfig,
    RealizedVolatilityResult,
    create_realized_volatility,
)

from ai.models.volatility.stochastic_volatility import (
    StochasticVolatility,
    StochasticVolatilityConfig,
    StochasticVolatilityResult,
    create_stochastic_volatility,
)

from ai.models.volatility.volatility_forecast import (
    VolatilityForecast,
    VolatilityForecastConfig,
    VolatilityForecastResult,
    create_volatility_forecast,
)

logger = logging.getLogger(__name__)


__all__ = [
    # GARCH
    'GARCHModel',
    'GARCHConfig',
    'GARCHResult',
    'create_garch_model',
    
    # Realized Volatility
    'RealizedVolatility',
    'RealizedVolatilityConfig',
    'RealizedVolatilityResult',
    'create_realized_volatility',
    
    # Stochastic Volatility
    'StochasticVolatility',
    'StochasticVolatilityConfig',
    'StochasticVolatilityResult',
    'create_stochastic_volatility',
    
    # Volatility Forecast
    'VolatilityForecast',
    'VolatilityForecastConfig',
    'VolatilityForecastResult',
    'create_volatility_forecast',
]


def create_volatility_model(
    model_type: str = 'garch',
    **kwargs
) -> Any:
    """
    Factory pour créer des modèles de volatilité.
    
    Args:
        model_type: Type de modèle ('garch', 'realized', 'stochastic', 'forecast')
        **kwargs: Paramètres de configuration
    
    Returns:
        Any: Instance du modèle de volatilité
    
    Examples:
        ```python
        # Modèle GARCH
        model = create_volatility_model(
            'garch',
            p=1,
            q=1,
            vol='GARCH',
            dist='normal'
        )
        
        # Volatilité réalisée
        model = create_volatility_model(
            'realized',
            method='rv',
            window=20,
            annualize=True
        )
        
        # Volatilité stochastique
        model = create_volatility_model(
            'stochastic',
            hidden_size=64,
            distribution='normal',
            use_leverage=True
        )
        
        # Prévision de volatilité
        model = create_volatility_model(
            'forecast',
            model_type='xgboost',
            window=20,
            forecast_horizon=1
        )
        ```
    """
    model_type = model_type.lower()
    
    if model_type == 'garch':
        p = kwargs.get('p', 1)
        q = kwargs.get('q', 1)
        vol = kwargs.get('vol', 'GARCH')
        dist = kwargs.get('dist', 'normal')
        
        return create_garch_model(
            p=p,
            q=q,
            vol=vol,
            dist=dist,
            **{k: v for k, v in kwargs.items() 
               if k not in ['p', 'q', 'vol', 'dist']}
        )
    
    elif model_type == 'realized':
        method = kwargs.get('method', 'rv')
        window = kwargs.get('window', 20)
        annualize = kwargs.get('annualize', True)
        trading_days = kwargs.get('trading_days', 252)
        
        return create_realized_volatility(
            method=method,
            window=window,
            annualize=annualize,
            trading_days=trading_days,
            **{k: v for k, v in kwargs.items() 
               if k not in ['method', 'window', 'annualize', 'trading_days']}
        )
    
    elif model_type == 'stochastic':
        hidden_size = kwargs.get('hidden_size', 64)
        distribution = kwargs.get('distribution', 'normal')
        use_leverage = kwargs.get('use_leverage', False)
        
        return create_stochastic_volatility(
            hidden_size=hidden_size,
            distribution=distribution,
            use_leverage=use_leverage,
            **{k: v for k, v in kwargs.items() 
               if k not in ['hidden_size', 'distribution', 'use_leverage']}
        )
    
    elif model_type == 'forecast':
        model_type_ml = kwargs.get('model_type_ml', 'xgboost')
        window = kwargs.get('window', 20)
        forecast_horizon = kwargs.get('forecast_horizon', 1)
        
        return create_volatility_forecast(
            model_type=model_type_ml,
            window=window,
            forecast_horizon=forecast_horizon,
            **{k: v for k, v in kwargs.items() 
               if k not in ['model_type_ml', 'window', 'forecast_horizon']}
        )
    
    else:
        raise ValueError(f"Type de modèle de volatilité non supporté: {model_type}")


def get_available_volatility_models() -> List[str]:
    """
    Retourne la liste des modèles de volatilité disponibles.
    
    Returns:
        List[str]: Liste des types de modèles
    """
    models = ['garch', 'realized', 'stochastic', 'forecast']
    
    # Vérifier les dépendances
    try:
        import arch
    except ImportError:
        models.remove('garch') if 'garch' in models else None
    
    try:
        import torch
    except ImportError:
        models.remove('stochastic') if 'stochastic' in models else None
    
    try:
        import sklearn
    except ImportError:
        models.remove('forecast') if 'forecast' in models else None
    
    return models


def get_volatility_model_info(model_type: str) -> Dict[str, Any]:
    """
    Retourne des informations sur un type de modèle de volatilité.
    
    Args:
        model_type: Type de modèle
    
    Returns:
        Dict[str, Any]: Informations sur le modèle
    """
    info = {
        'garch': {
            'name': 'GARCH',
            'description': 'Modèle autorégressif de volatilité conditionnelle',
            'advantages': [
                'Classique et bien compris',
                'Multiple variantes (EGARCH, GJR-GARCH)',
                'Interprétable'
            ],
            'disadvantages': [
                'Paramètres à estimer',
                'Hypothèses fortes',
                'Peut ne pas capturer les longues dépendances'
            ],
            'use_cases': [
                'Prévisions de volatilité court terme',
                'Risk management',
                'Option pricing'
            ]
        },
        'realized': {
            'name': 'Realized Volatility',
            'description': 'Volatilité calculée à partir des données historiques',
            'advantages': [
                'Simple à calculer',
                'Sans paramètres',
                'Multiple méthodes (RV, Parkinson, etc.)'
            ],
            'disadvantages': [
                'Nécessite des données haute fréquence',
                'Sensible au bruit de microstructure',
                'Pas de prévision'
            ],
            'use_cases': [
                'Mesure de volatilité historique',
                'Analyse de la volatilité réalisée',
                'Backtesting'
            ]
        },
        'stochastic': {
            'name': 'Stochastic Volatility',
            'description': 'Volatilité avec dynamique latente',
            'advantages': [
                'Capture les non-linéarités',
                'Flexible',
                'Support des distributions complexes'
            ],
            'disadvantages': [
                'Complexe à estimer',
                'Nécessite beaucoup de données',
                'Moins interprétable'
            ],
            'use_cases': [
                'Prévisions de volatilité long terme',
                'Marchés avec changements de régime',
                'Données complexes'
            ]
        },
        'forecast': {
            'name': 'Volatility Forecast',
            'description': 'Prévision de volatilité avec ML',
            'advantages': [
                'Utilise de nombreuses features',
                'Peu d\'hypothèses',
                'Bonnes performances'
            ],
            'disadvantages': [
                'Black-box',
                'Nécessite beaucoup de données',
                'Sensible aux features'
            ],
            'use_cases': [
                'Prévisions de volatilité',
                'Modélisation de la volatilité future',
                'Feature engineering'
            ]
        }
    }
    
    return info.get(model_type.lower(), {})


def get_volatility_recommendation(
    data_frequency: str = 'daily',
    forecast_horizon: str = 'short',
    interpretability: bool = True,
    data_available: str = 'medium'
) -> Dict[str, Any]:
    """
    Recommande un modèle de volatilité selon les besoins.
    
    Args:
        data_frequency: Fréquence des données ('high', 'daily', 'weekly')
        forecast_horizon: Horizon de prévision ('short', 'medium', 'long')
        interpretability: Nécessité d'interprétabilité
        data_available: Quantité de données ('low', 'medium', 'high')
    
    Returns:
        Dict[str, Any]: Recommandation
    """
    if data_frequency == 'high':
        if data_available == 'high':
            return {
                'recommended_model': {
                    'model': 'realized',
                    'description': 'Volatilité réalisée pour données haute fréquence'
                },
                'alternative_models': ['stochastic', 'garch']
            }
        else:
            return {
                'recommended_model': {
                    'model': 'garch',
                    'description': 'GARCH pour données haute fréquence limitées'
                },
                'alternative_models': ['realized', 'forecast']
            }
    
    if forecast_horizon == 'short':
        if interpretability:
            return {
                'recommended_model': {
                    'model': 'garch',
                    'description': 'GARCH pour prévisions court terme interprétables'
                },
                'alternative_models': ['realized', 'forecast']
            }
        else:
            return {
                'recommended_model': {
                    'model': 'forecast',
                    'description': 'Forecast ML pour meilleure précision court terme'
                },
                'alternative_models': ['garch', 'stochastic']
            }
    
    if forecast_horizon == 'long':
        if data_available == 'high':
            return {
                'recommended_model': {
                    'model': 'stochastic',
                    'description': 'Volatilité stochastique pour long terme'
                },
                'alternative_models': ['forecast', 'garch']
            }
        else:
            return {
                'recommended_model': {
                    'model': 'garch',
                    'description': 'GARCH pour long terme avec données limitées'
                },
                'alternative_models': ['forecast', 'stochastic']
            }
    
    # Par défaut
    return {
        'recommended_model': {
            'model': 'garch',
            'description': 'GARCH pour approche équilibrée'
        },
        'alternative_models': ['realized', 'stochastic', 'forecast']
    }


logger.info("Module de modèles de volatilité initialisé")
