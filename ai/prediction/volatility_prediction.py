
# ai/prediction/volatility_prediction.py
"""
NEXUS AI TRADING SYSTEM - Volatility Prediction Module
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
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    from arch import arch_model
    ARCH_AVAILABLE = True
except ImportError:
    ARCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class VolatilityPredictionConfig:
    """Configuration pour Volatility Prediction"""
    lookback_window: int = 50
    prediction_horizon: int = 1
    model_type: str = 'xgboost'  # 'xgboost', 'random_forest', 'gradient_boosting', 'garch', 'lstm'
    n_estimators: int = 100
    max_depth: int = 6
    learning_rate: float = 0.1
    sequence_length: int = 24
    hidden_size: int = 128
    num_layers: int = 2
    dropout: float = 0.1
    batch_size: int = 64
    epochs: int = 100
    use_gpu: bool = False
    early_stopping: bool = True
    patience: int = 10
    random_state: Optional[int] = 42
    use_ensemble: bool = False
    ensemble_models: List[str] = field(default_factory=lambda: ['xgboost', 'random_forest'])

    def to_dict(self) -> Dict[str, Any]:
        return {
            'lookback_window': self.lookback_window,
            'prediction_horizon': self.prediction_horizon,
            'model_type': self.model_type,
            'n_estimators': self.n_estimators,
            'max_depth': self.max_depth,
            'learning_rate': self.learning_rate,
            'sequence_length': self.sequence_length,
            'hidden_size': self.hidden_size,
            'num_layers': self.num_layers,
            'dropout': self.dropout,
            'batch_size': self.batch_size,
            'epochs': self.epochs,
            'use_gpu': self.use_gpu,
            'early_stopping': self.early_stopping,
            'patience': self.patience,
            'random_state': self.random_state,
            'use_ensemble': self.use_ensemble,
            'ensemble_models': self.ensemble_models,
        }


@dataclass
class VolatilityPredictionResult:
    """Résultat de prédiction de volatilité"""
    symbol: str
    timestamp: datetime
    current_price: float
    predicted_volatility: float  # annualisée
    confidence: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    historical_volatility: Optional[float] = None
    model_version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'current_price': self.current_price,
            'predicted_volatility': self.predicted_volatility,
            'confidence': self.confidence,
            'lower_bound': self.lower_bound,
            'upper_bound': self.upper_bound,
            'historical_volatility': self.historical_volatility,
            'model_version': self.model_version,
        }


class _VolatilityLSTM(nn.Module):
    """Modèle LSTM pour prédiction de volatilité"""

    def __init__(self, config: VolatilityPredictionConfig):
        super().__init__()

        self.lstm = nn.LSTM(
            input_size=1,
            hidden_size=config.hidden_size,
            num_layers=config.num_layers,
            dropout=config.dropout if config.num_layers > 1 else 0,
            batch_first=True
        )

        self.fc = nn.Sequential(
            nn.Linear(config.hidden_size, config.hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_size // 2, 1)
        )

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        return self.fc(lstm_out[:, -1, :])


class VolatilityPredictor:
    """
    Prédicteur de volatilité pour l'IA de trading.

    Features:
    - Multi-model support (XGBoost, GARCH, LSTM)
    - Volatility forecasting
    - Confidence intervals
    - Realized volatility calculation
    - Ensemble predictions

    Example:
        ```python
        config = VolatilityPredictionConfig(
            lookback_window=50,
            prediction_horizon=1,
            model_type='xgboost'
        )
        predictor = VolatilityPredictor(config)

        # Train
        predictor.fit(returns)

        # Predict
        result = predictor.predict(symbol='BTC-USD', data=df)
        ```
    """

    def __init__(self, config: Optional[VolatilityPredictionConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or VolatilityPredictionConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        self.is_fitted = False
        self.feature_importance: Optional[np.ndarray] = None
        self._cache: Dict[str, VolatilityPredictionResult] = {}

        logger.info(f"VolatilityPredictor initialisé sur {self.device}")

    def _calculate_realized_volatility(self, returns: np.ndarray, window: int) -> np.ndarray:
        """Calcule la volatilité réalisée"""
        vol = np.zeros(len(returns))

        for i in range(window, len(returns)):
            vol[i] = np.std(returns[i-window:i]) * np.sqrt(252)

        return vol

    def _create_features(self, returns: np.ndarray) -> np.ndarray:
        """
        Crée les features pour la prédiction de volatilité.

        Args:
            returns: Rendements historiques

        Returns:
            np.ndarray: Features
        """
        features = []

        # Retards des rendements
        for lag in [1, 5, 10, 20]:
            features.append(np.roll(returns, lag))

        # Retards de la volatilité
        vol = self._calculate_realized_volatility(returns, 20)
        for lag in [1, 5, 10]:
            features.append(np.roll(vol, lag))

        # Statistiques sur fenêtre
        for window in [5, 10, 20]:
            mean = pd.Series(returns).rolling(window).mean().values
            std = pd.Series(returns).rolling(window).std().values
            skew = pd.Series(returns).rolling(window).skew().values
            kurt = pd.Series(returns).rolling(window).kurt().values
            features.extend([mean, std, skew, kurt])

        # Rendements absolus
        features.append(np.abs(returns))
        features.append(returns ** 2)

        features = np.array(features).T
        valid_idx = ~np.isnan(features).any(axis=1)
        return features[valid_idx]

    def _create_target(self, returns: np.ndarray) -> np.ndarray:
        """Crée la cible pour la prédiction de volatilité"""
        # Volatilité future
        future_vol = self._calculate_realized_volatility(
            returns,
            self.config.prediction_horizon
        )
        return np.roll(future_vol, -self.config.prediction_horizon)

    def _create_lstm_sequences(self, data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Crée des séquences pour LSTM"""
        sequences = []
        targets = []

        for i in range(self.config.sequence_length, len(data)):
            seq = data[i - self.config.sequence_length:i]
            target = data[i]
            sequences.append(seq)
            targets.append(target)

        return np.array(sequences), np.array(targets)

    def _init_garch_model(self, returns: np.ndarray):
        """Initialise le modèle GARCH"""
        if not ARCH_AVAILABLE:
            logger.warning("Arch n'est pas disponible")
            return None

        try:
            model = arch_model(returns, vol='Garch', p=1, q=1)
            return model
        except Exception as e:
            logger.error(f"Erreur GARCH: {e}")
            return None

    def fit(
        self,
        returns: Union[np.ndarray, pd.Series],
        validation_split: float = 0.2
    ) -> 'VolatilityPredictor':
        """
        Entraîne le prédicteur de volatilité.

        Args:
            returns: Rendements historiques
            validation_split: Ratio de validation

        Returns:
            VolatilityPredictor: Instance entraînée
        """
        if isinstance(returns, pd.Series):
            returns = returns.values

        # Création des features et cibles
        features = self._create_features(returns)
        target = self._create_target(returns)

        # Alignement
        min_len = min(len(features), len(target))
        features = features[:min_len]
        target = target[:min_len]

        # Modèles
        if self.config.use_ensemble:
            self._init_ensemble(features, target, validation_split)
        else:
            self._init_single_model(features, target, validation_split)

        self.is_fitted = True
        logger.info(f"Entraînement terminé")

        return self

    def _init_single_model(self, features: np.ndarray, target: np.ndarray, validation_split: float):
        """Initialise un seul modèle"""
        # Normalisation
        scaler = StandardScaler()
        features = scaler.fit_transform(features)

        # Split
        split_idx = int(len(features) * (1 - validation_split))
        X_train, X_val = features[:split_idx], features[split_idx:]
        y_train, y_val = target[:split_idx], target[split_idx:]

        # Création du modèle
        if self.config.model_type == 'xgboost' and XGB_AVAILABLE:
            model = xgb.XGBRegressor(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                learning_rate=self.config.learning_rate,
                random_state=self.config.random_state
            )
        elif self.config.model_type == 'random_forest' and SKLEARN_AVAILABLE:
            model = RandomForestRegressor(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                random_state=self.config.random_state
            )
        elif self.config.model_type == 'gradient_boosting' and SKLEARN_AVAILABLE:
            model = GradientBoostingRegressor(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                learning_rate=self.config.learning_rate,
                random_state=self.config.random_state
            )
        elif self.config.model_type == 'garch' and ARCH_AVAILABLE:
            model = self._init_garch_model(X_train.flatten())
        elif self.config.model_type == 'lstm' and TORCH_AVAILABLE:
            model = self._fit_lstm(X_train, y_train, X_val, y_val)
        else:
            raise ValueError(f"Modèle non supporté: {self.config.model_type}")

        self.models['primary'] = model
        self.scalers['primary'] = scaler

        # Feature importance
        if hasattr(model, 'feature_importances_'):
            self.feature_importance = model.feature_importances_

    def _fit_lstm(self, X_train, y_train, X_val, y_val):
        """Entraîne le modèle LSTM"""
        model = _VolatilityLSTM(self.config).to(self.device)

        # Séquences
        X_train_seq, y_train_seq = self._create_lstm_sequences(X_train)
        X_val_seq, y_val_seq = self._create_lstm_sequences(X_val)

        X_train = torch.FloatTensor(X_train_seq).unsqueeze(-1).to(self.device)
        y_train = torch.FloatTensor(y_train_seq).to(self.device)
        X_val = torch.FloatTensor(X_val_seq).unsqueeze(-1).to(self.device)
        y_val = torch.FloatTensor(y_val_seq).to(self.device)

        optimizer = torch.optim.Adam(model.parameters(), lr=self.config.learning_rate)
        criterion = nn.MSELoss()

        best_val_loss = float('inf')
        patience_counter = 0

        for epoch in range(self.config.epochs):
            model.train()
            epoch_loss = 0.0

            for i in range(0, len(X_train), self.config.batch_size):
                batch_X = X_train[i:i + self.config.batch_size]
                batch_y = y_train[i:i + self.config.batch_size]

                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y.unsqueeze(1))
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()

            # Validation
            model.eval()
            with torch.no_grad():
                val_outputs = model(X_val)
                val_loss = criterion(val_outputs, y_val.unsqueeze(1)).item()

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
            else:
                patience_counter += 1

            if self.config.early_stopping and patience_counter >= self.config.patience:
                logger.info(f"Arrêt précoce à l'époque {epoch+1}")
                break

        return model

    def _init_ensemble(self, features: np.ndarray, target: np.ndarray, validation_split: float):
        """Initialise les modèles d'ensemble"""
        for model_type in self.config.ensemble_models:
            try:
                # Normalisation
                scaler = StandardScaler()
                features_scaled = scaler.fit_transform(features)

                split_idx = int(len(features_scaled) * (1 - validation_split))
                X_train = features_scaled[:split_idx]
                y_train = target[:split_idx]

                if model_type == 'xgboost' and XGB_AVAILABLE:
                    model = xgb.XGBRegressor(
                        n_estimators=self.config.n_estimators,
                        max_depth=self.config.max_depth,
                        learning_rate=self.config.learning_rate,
                        random_state=self.config.random_state
                    )
                elif model_type == 'random_forest' and SKLEARN_AVAILABLE:
                    model = RandomForestRegressor(
                        n_estimators=self.config.n_estimators,
                        max_depth=self.config.max_depth,
                        random_state=self.config.random_state
                    )
                elif model_type == 'gradient_boosting' and SKLEARN_AVAILABLE:
                    model = GradientBoostingRegressor(
                        n_estimators=self.config.n_estimators,
                        max_depth=self.config.max_depth,
                        learning_rate=self.config.learning_rate,
                        random_state=self.config.random_state
                    )
                else:
                    continue

                model.fit(X_train, y_train)
                self.models[model_type] = model
                self.scalers[model_type] = scaler
                logger.info(f"Modèle {model_type} entraîné")

            except Exception as e:
                logger.error(f"Erreur avec {model_type}: {e}")

    def predict(
        self,
        symbol: str,
        data: Union[np.ndarray, pd.DataFrame, pd.Series],
        return_details: bool = False
    ) -> Union[float, VolatilityPredictionResult]:
        """
        Effectue une prédiction de volatilité.

        Args:
            symbol: Symbole de l'actif
            data: Données historiques
            return_details: Retourner les détails

        Returns:
            float: Volatilité prédite
            VolatilityPredictionResult: Résultat complet
        """
        if not self.is_fitted:
            raise ValueError("Le modèle doit être entraîné")

        if isinstance(data, pd.DataFrame):
            data = data['close'].values if 'close' in data.columns else data.values
        elif isinstance(data, pd.Series):
            data = data.values

        # Cache
        cache_key = f"{symbol}_{len(data)}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if (datetime.now() - cached.timestamp).seconds < 300:
                return cached

        # Calcul des rendements
        returns = np.diff(data) / data[:-1]

        # Features
        features = self._create_features(returns)
        if len(features) == 0:
            raise ValueError("Pas assez de données")

        last_features = features[-1:]

        # Prédiction
        predictions = []

        for name, model in self.models.items():
            try:
                scaler = self.scalers[name]
                features_scaled = scaler.transform(last_features)

                if self.config.model_type == 'garch' and name == 'primary':
                    pred = model.forecast(horizon=1).variance.values[-1, 0] ** 0.5
                elif self.config.model_type == 'lstm' and name == 'primary':
                    model.eval()
                    with torch.no_grad():
                        input_tensor = torch.FloatTensor(features_scaled).unsqueeze(1).to(self.device)
                        pred = model(input_tensor).cpu().numpy()[0, 0]
                else:
                    pred = model.predict(features_scaled)[0]

                predictions.append(max(pred, 0))

            except Exception as e:
                logger.error(f"Erreur avec {name}: {e}")

        if not predictions:
            raise RuntimeError("Aucune prédiction disponible")

        # Agrégation
        if self.config.use_ensemble:
            predicted_vol = np.mean(predictions)
            confidence = 1 - np.std(predictions) / (predicted_vol + 1e-6)
        else:
            predicted_vol = predictions[0]
            confidence = 0.7

        # Annualisation
        predicted_vol = predicted_vol * np.sqrt(252)

        # Volatilité historique
        hist_vol = np.std(returns[-20:]) * np.sqrt(252)

        current_price = data[-1]

        result = VolatilityPredictionResult(
            symbol=symbol,
            timestamp=datetime.now(),
            current_price=current_price,
            predicted_volatility=predicted_vol,
            confidence=min(max(confidence, 0), 1),
            historical_volatility=hist_vol,
            lower_bound=predicted_vol * 0.7,
            upper_bound=predicted_vol * 1.3,
            model_version="1.0.0",
        )

        self._cache[cache_key] = result

        if return_details:
            return result

        return predicted_vol

    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres du prédicteur"""
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques du prédicteur"""
        return {
            'is_fitted': self.is_fitted,
            'device': str(self.device),
            'n_models': len(self.models),
            'models': list(self.models.keys()),
            'use_ensemble': self.config.use_ensemble,
            'cache_size': len(self._cache),
        }

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde le prédicteur.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si la sauvegarde a réussi
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'models': self.models,
                'scalers': self.scalers,
                'feature_importance': self.feature_importance,
                'is_fitted': self.is_fitted,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Prédicteur sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'VolatilityPredictor':
        """
        Charge un prédicteur.

        Args:
            filepath: Chemin du fichier

        Returns:
            VolatilityPredictor: Prédicteur chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = VolatilityPredictionConfig(**data['config'])
            predictor = cls(config)

            predictor.models = data.get('models', {})
            predictor.scalers = data.get('scalers', {})
            predictor.feature_importance = data.get('feature_importance')
            predictor.is_fitted = data.get('is_fitted', False)

            logger.info(f"Prédicteur chargé: {filepath}")
            return predictor

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_volatility_predictor(
    lookback_window: int = 50,
    prediction_horizon: int = 1,
    model_type: str = 'xgboost',
    **kwargs
) -> VolatilityPredictor:
    """
    Factory pour créer un prédicteur de volatilité.

    Args:
        lookback_window: Fenêtre de contexte
        prediction_horizon: Horizon de prédiction
        model_type: Type de modèle
        **kwargs: Arguments supplémentaires

    Returns:
        VolatilityPredictor: Prédicteur de volatilité
    """
    config = VolatilityPredictionConfig(
        lookback_window=lookback_window,
        prediction_horizon=prediction_horizon,
        model_type=model_type,
        **kwargs
    )
    return VolatilityPredictor(config)


__all__ = [
    'VolatilityPredictor',
    'VolatilityPredictionConfig',
    'VolatilityPredictionResult',
    'create_volatility_predictor',
]
