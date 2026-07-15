
# ai/prediction/market_prediction.py
"""
NEXUS AI TRADING SYSTEM - Market Prediction Engine
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import pickle
import os
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class MarketPredictionConfig:
    """Configuration pour Market Prediction"""
    prediction_horizon: int = 24  # Heures
    lookback_window: int = 168  # Heures (7 jours)
    confidence_threshold: float = 0.7
    use_ensemble: bool = True
    ensemble_models: List[str] = field(default_factory=lambda: ['lstm', 'xgboost', 'prophet'])
    use_gpu: bool = False
    batch_size: int = 64
    epochs: int = 100
    random_state: Optional[int] = 42
    save_predictions: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'prediction_horizon': self.prediction_horizon,
            'lookback_window': self.lookback_window,
            'confidence_threshold': self.confidence_threshold,
            'use_ensemble': self.use_ensemble,
            'ensemble_models': self.ensemble_models,
            'use_gpu': self.use_gpu,
            'batch_size': self.batch_size,
            'epochs': self.epochs,
            'random_state': self.random_state,
            'save_predictions': self.save_predictions,
        }


@dataclass
class MarketPrediction:
    """Résultat d'une prédiction de marché"""
    symbol: str
    timestamp: datetime
    current_price: float
    predicted_price: float
    predicted_change: float
    confidence: float
    direction: str  # 'up', 'down', 'neutral'
    timeframe: str  # 'short', 'medium', 'long'
    features: Optional[Dict[str, float]] = None
    model_contributions: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'current_price': self.current_price,
            'predicted_price': self.predicted_price,
            'predicted_change': self.predicted_change,
            'confidence': self.confidence,
            'direction': self.direction,
            'timeframe': self.timeframe,
            'features': self.features,
            'model_contributions': self.model_contributions,
        }


class MarketPredictionEngine:
    """
    Moteur de prédiction de marché pour l'IA de trading.

    Features:
    - Support multi-modèles (LSTM, XGBoost, Prophet)
    - Ensemble predictions
    - Confidence estimation
    - Feature engineering
    - Prediction caching
    - Historical tracking

    Example:
        ```python
        config = MarketPredictionConfig(
            prediction_horizon=24,
            lookback_window=168,
            use_ensemble=True
        )
        engine = MarketPredictionEngine(config)

        # Train on historical data
        engine.fit(historical_data)

        # Predict
        prediction = engine.predict(symbol='BTC-USD')
        ```
    """

    def __init__(self, config: Optional[MarketPredictionConfig] = None):
        self.config = config or MarketPredictionConfig()
        self.models: Dict[str, Any] = {}
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self.is_fitted = False
        self._cache: Dict[str, MarketPrediction] = {}
        self._feature_importance: Dict[str, float] = {}

        logger.info(f"MarketPredictionEngine initialisé")

    def _create_models(self) -> Dict[str, Any]:
        """Crée les modèles de prédiction"""
        models = {}

        for model_type in self.config.ensemble_models:
            if model_type == 'lstm' and TORCH_AVAILABLE:
                from ai.models.lstm import create_lstm
                models['lstm'] = create_lstm(
                    input_size=20,
                    hidden_size=128,
                    sequence_length=self.config.lookback_window,
                    prediction_length=self.config.prediction_horizon,
                    use_gpu=self.config.use_gpu,
                    random_state=self.config.random_state
                )

            elif model_type == 'xgboost' and XGB_AVAILABLE:
                import xgboost as xgb
                models['xgboost'] = xgb.XGBRegressor(
                    n_estimators=100,
                    max_depth=6,
                    learning_rate=0.1,
                    random_state=self.config.random_state
                )

            elif model_type == 'prophet' and PROPHET_AVAILABLE:
                from prophet import Prophet
                models['prophet'] = Prophet(
                    yearly_seasonality=True,
                    weekly_seasonality=True,
                    daily_seasonality=True
                )

            elif model_type == 'linear' and SKLEARN_AVAILABLE:
                from sklearn.linear_model import LinearRegression
                models['linear'] = LinearRegression()

            else:
                logger.warning(f"Modèle {model_type} non disponible")

        return models

    def _extract_features(self, data: pd.DataFrame) -> np.ndarray:
        """Extrait les features des données"""
        features = []

        # Prix
        features.append(data['close'].values)

        # Retards
        for lag in [1, 5, 10, 20, 50]:
            if len(data) > lag:
                features.append(data['close'].shift(lag).values)

        # Volatilité
        for window in [5, 10, 20, 50]:
            if len(data) > window:
                features.append(data['close'].pct_change().rolling(window).std().values)

        # Moyennes mobiles
        for window in [5, 10, 20, 50]:
            if len(data) > window:
                features.append(data['close'].rolling(window).mean().values)

        # RSI
        if 'close' in data.columns:
            delta = data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            features.append(rsi.values)

        # Volume
        if 'volume' in data.columns:
            features.append(data['volume'].values)

        # Supprimer les NaN
        features = np.array(features).T
        valid_idx = ~np.isnan(features).any(axis=1)
        return features[valid_idx]

    def fit(self, data: pd.DataFrame, target: Optional[np.ndarray] = None):
        """
        Entraîne les modèles de prédiction.

        Args:
            data: Données historiques
            target: Cibles (optionnel)
        """
        logger.info("Début de l'entraînement des modèles")

        # Extraction des features
        features = self._extract_features(data)

        if target is None:
            # Target: prix futur
            target = data['close'].shift(-self.config.prediction_horizon).values
            target = target[:len(features)]

        # Normalisation
        if self.scaler is not None:
            features = self.scaler.fit_transform(features)

        # Création des modèles
        self.models = self._create_models()

        # Entraînement
        for name, model in self.models.items():
            try:
                if name == 'prophet':
                    # Format Prophet
                    df_prophet = data.copy()
                    df_prophet = df_prophet.reset_index()
                    df_prophet.columns = ['ds', 'y']
                    model.fit(df_prophet)
                else:
                    model.fit(features[:-self.config.prediction_horizon], target[:-self.config.prediction_horizon])
                logger.info(f"Modèle {name} entraîné")
            except Exception as e:
                logger.error(f"Erreur d'entraînement pour {name}: {e}")

        self.is_fitted = True
        logger.info("Entraînement terminé")

    def predict(
        self,
        symbol: str,
        data: pd.DataFrame,
        use_cache: bool = True
    ) -> MarketPrediction:
        """
        Effectue une prédiction de marché.

        Args:
            symbol: Symbole de l'actif
            data: Données récentes
            use_cache: Utiliser le cache

        Returns:
            MarketPrediction: Résultat de la prédiction
        """
        if not self.is_fitted:
            raise ValueError("Le moteur doit être entraîné")

        # Vérification du cache
        cache_key = f"{symbol}_{data.index[-1]}"
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            if (datetime.now() - cached.timestamp).seconds < 300:
                logger.debug(f"Prédiction trouvée dans le cache pour {symbol}")
                return cached

        # Extraction des features
        features = self._extract_features(data)

        if self.scaler is not None:
            features = self.scaler.transform(features)

        # Prédictions par modèle
        predictions = []
        model_contributions = {}

        for name, model in self.models.items():
            try:
                if name == 'prophet':
                    future = model.make_future_dataframe(periods=self.config.prediction_horizon, freq='H')
                    forecast = model.predict(future)
                    pred = forecast['yhat'].values[-1]
                else:
                    pred = model.predict(features[-1:])[0]
                predictions.append(pred)
                model_contributions[name] = pred
            except Exception as e:
                logger.error(f"Erreur de prédiction pour {name}: {e}")

        if not predictions:
            raise RuntimeError("Aucune prédiction disponible")

        # Agrégation des prédictions
        if self.config.use_ensemble:
            predicted_price = np.mean(predictions)
            confidence = 1 - np.std(predictions) / np.mean(predictions)
        else:
            predicted_price = predictions[0]
            confidence = self.config.confidence_threshold

        current_price = data['close'].iloc[-1]
        predicted_change = (predicted_price - current_price) / current_price

        # Direction
        if predicted_change > 0.01:
            direction = 'up'
        elif predicted_change < -0.01:
            direction = 'down'
        else:
            direction = 'neutral'

        # Timeframe
        if self.config.prediction_horizon <= 24:
            timeframe = 'short'
        elif self.config.prediction_horizon <= 168:
            timeframe = 'medium'
        else:
            timeframe = 'long'

        result = MarketPrediction(
            symbol=symbol,
            timestamp=datetime.now(),
            current_price=current_price,
            predicted_price=predicted_price,
            predicted_change=predicted_change,
            confidence=confidence,
            direction=direction,
            timeframe=timeframe,
            model_contributions=model_contributions,
        )

        # Cache
        if self.config.save_predictions:
            self._cache[cache_key] = result

        return result

    def predict_batch(
        self,
        symbols: List[str],
        data_dict: Dict[str, pd.DataFrame],
        use_cache: bool = True
    ) -> Dict[str, MarketPrediction]:
        """
        Effectue des prédictions batch.

        Args:
            symbols: Liste des symboles
            data_dict: Dictionnaire des données par symbole
            use_cache: Utiliser le cache

        Returns:
            Dict[str, MarketPrediction]: Prédictions par symbole
        """
        results = {}

        for symbol in symbols:
            if symbol in data_dict:
                results[symbol] = self.predict(symbol, data_dict[symbol], use_cache)

        return results

    def get_signal(
        self,
        prediction: MarketPrediction,
        threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Génère un signal de trading à partir d'une prédiction.

        Args:
            prediction: Prédiction de marché
            threshold: Seuil de confiance

        Returns:
            Dict[str, Any]: Signal de trading
        """
        threshold = threshold or self.config.confidence_threshold

        signal = {
            'symbol': prediction.symbol,
            'timestamp': datetime.now(),
            'action': 'hold',
            'confidence': prediction.confidence,
            'strength': 0,
        }

        if prediction.confidence >= threshold:
            if prediction.direction == 'up':
                signal['action'] = 'buy'
                signal['strength'] = prediction.confidence * abs(prediction.predicted_change)
            elif prediction.direction == 'down':
                signal['action'] = 'sell'
                signal['strength'] = prediction.confidence * abs(prediction.predicted_change)

        return signal

    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres du moteur"""
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques du moteur"""
        return {
            'is_fitted': self.is_fitted,
            'n_models': len(self.models),
            'models': list(self.models.keys()),
            'cache_size': len(self._cache),
            'prediction_horizon': self.config.prediction_horizon,
            'lookback_window': self.config.lookback_window,
        }

    def save(self, filepath: str) -> bool:
        """Sauvegarde le moteur"""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'models': self.models,
                'scaler': self.scaler,
                'is_fitted': self.is_fitted,
                'feature_importance': self._feature_importance,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Moteur sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'MarketPredictionEngine':
        """Charge un moteur"""
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = MarketPredictionConfig(**data['config'])
            engine = cls(config)

            engine.models = data.get('models', {})
            engine.scaler = data.get('scaler')
            engine.is_fitted = data.get('is_fitted', False)
            engine._feature_importance = data.get('feature_importance', {})

            logger.info(f"Moteur chargé: {filepath}")
            return engine

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_market_prediction(
    prediction_horizon: int = 24,
    lookback_window: int = 168,
    use_ensemble: bool = True,
    **kwargs
) -> MarketPredictionEngine:
    """
    Factory pour créer un moteur de prédiction de marché.

    Args:
        prediction_horizon: Horizon de prédiction (heures)
        lookback_window: Fenêtre de contexte (heures)
        use_ensemble: Utiliser l'ensemble
        **kwargs: Arguments supplémentaires

    Returns:
        MarketPredictionEngine: Moteur de prédiction
    """
    config = MarketPredictionConfig(
        prediction_horizon=prediction_horizon,
        lookback_window=lookback_window,
        use_ensemble=use_ensemble,
        **kwargs
    )
    return MarketPredictionEngine(config)


__all__ = [
    'MarketPredictionEngine',
    'MarketPredictionConfig',
    'MarketPrediction',
    'create_market_prediction',
]
