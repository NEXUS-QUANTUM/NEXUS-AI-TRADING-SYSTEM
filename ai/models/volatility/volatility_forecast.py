
# ai/models/volatility/volatility_forecast.py
"""
NEXUS AI TRADING SYSTEM - Volatility Forecast Model
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import os
import warnings
warnings.filterwarnings('ignore')

try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.linear_model import LinearRegression, Ridge, Lasso
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class VolatilityForecastConfig:
    model_type: str = 'xgboost'  # 'linear', 'ridge', 'lasso', 'random_forest', 'gradient_boosting', 'xgboost', 'lstm'
    window: int = 20
    forecast_horizon: int = 1
    test_size: float = 0.2
    n_estimators: int = 100
    max_depth: int = 5
    learning_rate: float = 0.1
    hidden_size: int = 64
    num_layers: int = 2
    dropout: float = 0.1
    batch_size: int = 64
    epochs: int = 100
    use_gpu: bool = False
    early_stopping: bool = True
    patience: int = 10
    clip_gradient: float = 1.0
    weight_decay: float = 1e-5
    random_state: int = 42

    def __post_init__(self):
        valid_models = ['linear', 'ridge', 'lasso', 'random_forest', 'gradient_boosting', 'xgboost', 'lstm']
        if self.model_type not in valid_models:
            raise ValueError(f"Type de modèle non supporté: {self.model_type}")


@dataclass
class VolatilityForecastResult:
    predictions: np.ndarray
    actual: Optional[np.ndarray] = None
    mse: Optional[float] = None
    mae: Optional[float] = None
    r2: Optional[float] = None
    feature_importance: Optional[Dict[str, float]] = None
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    forecast_horizon: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'actual': self.actual.tolist() if isinstance(self.actual, np.ndarray) else self.actual,
            'mse': self.mse,
            'mae': self.mae,
            'r2': self.r2,
            'feature_importance': self.feature_importance,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
            'forecast_horizon': self.forecast_horizon,
        }


class _VolatilityLSTM(nn.Module):
    """Modèle LSTM pour prévision de volatilité"""

    def __init__(self, input_size: int, hidden_size: int, num_layers: int, dropout: float):
        super().__init__()

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True
        )

        self.fc = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, 1)
        )

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        return self.fc(lstm_out[:, -1, :])


class VolatilityForecast:
    """
    Volatility Forecasting model using machine learning.

    This implementation provides multiple models for forecasting volatility:
    - Linear models (Linear, Ridge, Lasso)
    - Tree-based models (Random Forest, Gradient Boosting, XGBoost)
    - Deep learning (LSTM)

    Features:
    - Feature engineering for volatility prediction
    - Multiple model types
    - Feature importance analysis
    - GPU acceleration (for LSTM)
    - Model persistence

    Example:
        ```python
        config = VolatilityForecastConfig(
            model_type='xgboost',
            window=20,
            forecast_horizon=1,
            n_estimators=100
        )
        model = VolatilityForecast(config)

        # Fit model
        model.fit(returns, volatility)

        # Predict
        predictions = model.predict(features)
        ```
    """

    def __init__(self, config: Optional[VolatilityForecastConfig] = None):
        if not SKLEARN_AVAILABLE:
            raise ImportError("Scikit-learn est requis. Installez avec: pip install scikit-learn")

        self.config = config or VolatilityForecastConfig()
        self.model: Optional[Any] = None
        self.scaler = StandardScaler()
        self.is_fitted = False
        self.feature_names: List[str] = []
        self.feature_importance: Optional[Dict[str, float]] = None
        self._prediction_cache: Dict[str, Any] = {}

        logger.info(f"VolatilityForecast initialisé avec {self.config.model_type}")

    def _create_features(
        self,
        returns: np.ndarray,
        volatility: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """Crée les features pour la prévision de volatilité"""
        n = len(returns)
        features = []

        # Retards des rendements
        for lag in range(1, min(5, n)):
            features.append(np.roll(returns, lag))

        # Retards de la volatilité
        if volatility is not None:
            for lag in range(1, min(5, len(volatility))):
                features.append(np.roll(volatility, lag))

        # Statistiques sur fenêtre glissante
        for window in [5, 10, 20]:
            if n >= window:
                rolling_mean = np.convolve(returns, np.ones(window)/window, mode='same')
                rolling_std = np.array([np.std(returns[max(0, i-window):i]) for i in range(len(returns))])
                features.append(rolling_mean)
                features.append(rolling_std)

                if volatility is not None:
                    vol_mean = np.convolve(volatility, np.ones(window)/window, mode='same')
                    features.append(vol_mean)

        # Rendements absolus
        features.append(np.abs(returns))

        # Rendements au carré
        features.append(returns ** 2)

        # Maximum/minimum sur fenêtre
        for window in [5, 10]:
            if n >= window:
                max_return = np.array([np.max(returns[max(0, i-window):i]) for i in range(len(returns))])
                min_return = np.array([np.min(returns[max(0, i-window):i]) for i in range(len(returns))])
                features.append(max_return)
                features.append(min_return)

        # Skewness et kurtosis sur fenêtre
        for window in [10, 20]:
            if n >= window:
                skew = np.array([stats.skew(returns[max(0, i-window):i]) for i in range(len(returns))])
                kurt = np.array([stats.kurtosis(returns[max(0, i-window):i]) for i in range(len(returns))])
                features.append(skew)
                features.append(kurt)

        # Feature names
        self.feature_names = []
        for lag in range(1, 5):
            self.feature_names.append(f'return_lag_{lag}')
        if volatility is not None:
            for lag in range(1, 5):
                self.feature_names.append(f'volatility_lag_{lag}')
        for window in [5, 10, 20]:
            self.feature_names.append(f'return_mean_{window}')
            self.feature_names.append(f'return_std_{window}')
            if volatility is not None:
                self.feature_names.append(f'volatility_mean_{window}')
        self.feature_names.append('abs_return')
        self.feature_names.append('squared_return')
        for window in [5, 10]:
            self.feature_names.append(f'max_return_{window}')
            self.feature_names.append(f'min_return_{window}')
        for window in [10, 20]:
            self.feature_names.append(f'skew_{window}')
            self.feature_names.append(f'kurt_{window}')

        features = np.array(features).T
        return features

    def _prepare_data(
        self,
        returns: np.ndarray,
        volatility: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Prépare les données pour l'entraînement"""
        features = self._create_features(returns, volatility)

        # Cible: volatilité future
        if volatility is not None:
            target = np.roll(volatility, -self.config.forecast_horizon)
        else:
            target = np.roll(returns ** 2, -self.config.forecast_horizon)

        # Supprimer les NaN
        valid_idx = ~(np.isnan(features).any(axis=1) | np.isnan(target))
        features = features[valid_idx]
        target = target[valid_idx]

        # Split train/test
        split_idx = int(len(features) * (1 - self.config.test_size))
        X_train = features[:split_idx]
        X_test = features[split_idx:]
        y_train = target[:split_idx]
        y_test = target[split_idx:]

        return X_train, X_test, y_train, y_test

    def _create_model(self, input_size: int) -> Any:
        """Crée le modèle selon la configuration"""
        if self.config.model_type == 'linear':
            return LinearRegression()
        elif self.config.model_type == 'ridge':
            return Ridge(alpha=1.0)
        elif self.config.model_type == 'lasso':
            return Lasso(alpha=0.01)
        elif self.config.model_type == 'random_forest':
            return RandomForestRegressor(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                random_state=self.config.random_state
            )
        elif self.config.model_type == 'gradient_boosting':
            return GradientBoostingRegressor(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                learning_rate=self.config.learning_rate,
                random_state=self.config.random_state
            )
        elif self.config.model_type == 'xgboost' and XGB_AVAILABLE:
            return xgb.XGBRegressor(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                learning_rate=self.config.learning_rate,
                random_state=self.config.random_state
            )
        elif self.config.model_type == 'lstm' and TORCH_AVAILABLE:
            return _VolatilityLSTM(
                input_size=input_size,
                hidden_size=self.config.hidden_size,
                num_layers=self.config.num_layers,
                dropout=self.config.dropout
            )
        else:
            raise ValueError(f"Modèle non supporté: {self.config.model_type}")

    def _train_lstm(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray
    ) -> Any:
        """Entraîne le modèle LSTM"""
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        model = self._create_model(X_train.shape[1]).to(device)

        # Reshape pour LSTM
        X_train_lstm = X_train.reshape(X_train.shape[0], 1, X_train.shape[1])
        X_val_lstm = X_val.reshape(X_val.shape[0], 1, X_val.shape[1])

        train_dataset = TensorDataset(
            torch.FloatTensor(X_train_lstm).to(device),
            torch.FloatTensor(y_train).reshape(-1, 1).to(device)
        )
        val_dataset = TensorDataset(
            torch.FloatTensor(X_val_lstm).to(device),
            torch.FloatTensor(y_val).reshape(-1, 1).to(device)
        )

        train_loader = DataLoader(train_dataset, batch_size=self.config.batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=self.config.batch_size, shuffle=False)

        optimizer = optim.Adam(model.parameters(), lr=self.config.learning_rate)
        criterion = nn.MSELoss()

        best_val_loss = float('inf')
        patience_counter = 0

        for epoch in range(self.config.epochs):
            model.train()
            epoch_loss = 0.0
            for batch_X, batch_y in train_loader:
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), self.config.clip_gradient)
                optimizer.step()
                epoch_loss += loss.item()

            # Validation
            model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for batch_X, batch_y in val_loader:
                    outputs = model(batch_X)
                    loss = criterion(outputs, batch_y)
                    val_loss += loss.item()

            val_loss /= len(val_loader)

            if self.config.early_stopping:
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                    self._checkpoint = {'model_state_dict': model.state_dict()}
                else:
                    patience_counter += 1
                    if patience_counter >= self.config.patience:
                        logger.info(f"Arrêt précoce à l'époque {epoch+1}")
                        break

            if epoch % 10 == 0:
                logger.debug(f"Epoch {epoch+1}, Loss: {epoch_loss/len(train_loader):.6f}, Val Loss: {val_loss:.6f}")

        # Charger le meilleur modèle
        if hasattr(self, '_checkpoint'):
            model.load_state_dict(self._checkpoint['model_state_dict'])

        return model

    def fit(
        self,
        returns: Union[np.ndarray, pd.Series, List[float]],
        volatility: Optional[Union[np.ndarray, pd.Series, List[float]]] = None
    ) -> 'VolatilityForecast':
        """
        Entraîne le modèle de prévision de volatilité.

        Args:
            returns: Données de rendements
            volatility: Volatilité historique (optionnel)

        Returns:
            VolatilityForecast: Instance entraînée
        """
        if isinstance(returns, pd.Series):
            returns = returns.values
        elif isinstance(returns, list):
            returns = np.array(returns)

        if volatility is not None:
            if isinstance(volatility, pd.Series):
                volatility = volatility.values
            elif isinstance(volatility, list):
                volatility = np.array(volatility)
            if len(volatility) != len(returns):
                raise ValueError("returns et volatility doivent avoir la même longueur")

        X_train, X_test, y_train, y_test = self._prepare_data(returns, volatility)

        # Normalisation
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Création et entraînement du modèle
        if self.config.model_type == 'lstm' and TORCH_AVAILABLE:
            self.model = self._train_lstm(X_train_scaled, y_train, X_test_scaled, y_test)
        else:
            self.model = self._create_model(X_train.shape[1])
            self.model.fit(X_train_scaled, y_train)

        self.is_fitted = True

        # Métriques
        y_pred = self.predict(X_test)
        self.metrics = {
            'mse': mean_squared_error(y_test, y_pred),
            'mae': mean_absolute_error(y_test, y_pred),
            'r2': r2_score(y_test, y_pred),
        }

        # Importance des features
        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
            self.feature_importance = dict(zip(self.feature_names, importances))

        logger.info(f"Entraînement terminé - R2: {self.metrics['r2']:.4f}")
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Effectue une prédiction de volatilité.

        Args:
            X: Features (format: [n_samples, n_features])

        Returns:
            np.ndarray: Prédictions
        """
        if not self.is_fitted:
            raise ValueError("Le modèle doit être entraîné avant de prédire")

        X_scaled = self.scaler.transform(X)

        if self.config.model_type == 'lstm' and TORCH_AVAILABLE:
            device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
            self.model.eval()
            X_lstm = X_scaled.reshape(X_scaled.shape[0], 1, X_scaled.shape[1])
            X_tensor = torch.FloatTensor(X_lstm).to(device)
            with torch.no_grad():
                predictions = self.model(X_tensor).cpu().numpy().flatten()
        else:
            predictions = self.model.predict(X_scaled)

        return predictions

    def forecast(
        self,
        returns: Union[np.ndarray, pd.Series, List[float]],
        volatility: Optional[Union[np.ndarray, pd.Series, List[float]]] = None,
        steps: int = 1
    ) -> np.ndarray:
        """
        Prédit la volatilité future.

        Args:
            returns: Données de rendements
            volatility: Volatilité historique
            steps: Nombre d'étapes

        Returns:
            np.ndarray: Prédictions de volatilité
        """
        if not self.is_fitted:
            raise ValueError("Le modèle doit être entraîné")

        if isinstance(returns, pd.Series):
            returns = returns.values
        elif isinstance(returns, list):
            returns = np.array(returns)

        if volatility is not None:
            if isinstance(volatility, pd.Series):
                volatility = volatility.values
            elif isinstance(volatility, list):
                volatility = np.array(volatility)

        predictions = []
        current_returns = returns.copy()
        current_volatility = volatility.copy() if volatility is not None else None

        for _ in range(steps):
            features = self._create_features(current_returns, current_volatility)
            pred = self.predict(features[-1:])[0]
            predictions.append(pred)

            # Mise à jour des données
            current_returns = np.append(current_returns, np.mean(current_returns[-5:]))
            if current_volatility is not None:
                current_volatility = np.append(current_volatility, pred)

        return np.array(predictions)

    def get_params(self) -> Dict[str, Any]:
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        if not self.is_fitted:
            return {'is_fitted': False}
        return {
            'is_fitted': True,
            'model_type': self.config.model_type,
            'mse': self.metrics['mse'],
            'mae': self.metrics['mae'],
            'r2': self.metrics['r2'],
        }

    def get_feature_importance(self) -> Optional[Dict[str, float]]:
        return self.feature_importance

    def save(self, filepath: str) -> bool:
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'model': self.model,
                'scaler': self.scaler,
                'feature_names': self.feature_names,
                'feature_importance': self.feature_importance,
                'is_fitted': self.is_fitted,
                'metrics': self.metrics if hasattr(self, 'metrics') else {},
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Modèle sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'VolatilityForecast':
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = VolatilityForecastConfig(**data['config'])
            model = cls(config)

            model.model = data['model']
            model.scaler = data['scaler']
            model.feature_names = data.get('feature_names', [])
            model.feature_importance = data.get('feature_importance')
            model.is_fitted = data.get('is_fitted', False)
            model.metrics = data.get('metrics', {})

            logger.info(f"Modèle chargé: {filepath}")
            return model

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise


def create_volatility_forecast(
    model_type: str = 'xgboost',
    window: int = 20,
    forecast_horizon: int = 1,
    **kwargs
) -> VolatilityForecast:
    config = VolatilityForecastConfig(
        model_type=model_type,
        window=window,
        forecast_horizon=forecast_horizon,
        **kwargs
    )
    return VolatilityForecast(config)


__all__ = [
    'VolatilityForecast',
    'VolatilityForecastConfig',
    'VolatilityForecastResult',
    'create_volatility_forecast',
]
