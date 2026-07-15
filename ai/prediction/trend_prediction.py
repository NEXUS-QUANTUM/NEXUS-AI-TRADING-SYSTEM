
# ai/prediction/trend_prediction.py
"""
NEXUS AI TRADING SYSTEM - Trend Prediction Module
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
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class TrendPredictionConfig:
    """Configuration pour Trend Prediction"""
    lookback_window: int = 50
    prediction_horizon: int = 1
    n_estimators: int = 100
    max_depth: int = 6
    learning_rate: float = 0.1
    model_type: str = 'xgboost'  # 'xgboost', 'random_forest', 'gradient_boosting', 'lstm'
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
    confidence_threshold: float = 0.6

    def to_dict(self) -> Dict[str, Any]:
        return {
            'lookback_window': self.lookback_window,
            'prediction_horizon': self.prediction_horizon,
            'n_estimators': self.n_estimators,
            'max_depth': self.max_depth,
            'learning_rate': self.learning_rate,
            'model_type': self.model_type,
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
            'confidence_threshold': self.confidence_threshold,
        }


@dataclass
class TrendPredictionResult:
    """Résultat de prédiction de tendance"""
    symbol: str
    timestamp: datetime
    current_price: float
    predicted_trend: str  # 'up', 'down', 'sideways'
    confidence: float
    probability_up: float
    probability_down: float
    probability_sideways: float
    strength: float  # 0-1
    horizon: str  # 'short', 'medium', 'long'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'current_price': self.current_price,
            'predicted_trend': self.predicted_trend,
            'confidence': self.confidence,
            'probability_up': self.probability_up,
            'probability_down': self.probability_down,
            'probability_sideways': self.probability_sideways,
            'strength': self.strength,
            'horizon': self.horizon,
        }


class _TrendLSTM(nn.Module):
    """Modèle LSTM pour prédiction de tendance"""

    def __init__(self, config: TrendPredictionConfig):
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
            nn.Linear(config.hidden_size // 2, 3)  # up, down, sideways
        )

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        return self.fc(lstm_out[:, -1, :])


class TrendPredictor:
    """
    Prédicteur de tendance pour l'IA de trading.

    Features:
    - Multi-model support (XGBoost, Random Forest, LSTM)
    - Trend classification (up/down/sideways)
    - Confidence scoring
    - Feature engineering
    - Backtesting support

    Example:
        ```python
        config = TrendPredictionConfig(
            lookback_window=50,
            prediction_horizon=1,
            model_type='xgboost'
        )
        predictor = TrendPredictor(config)

        # Train
        predictor.fit(X_train, y_train)

        # Predict
        result = predictor.predict(symbol='BTC-USD', data=df)
        ```
    """

    def __init__(self, config: Optional[TrendPredictionConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or TrendPredictionConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.model: Optional[Any] = None
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self.is_fitted = False
        self.feature_importance: Optional[np.ndarray] = None
        self._cache: Dict[str, TrendPredictionResult] = {}

        logger.info(f"TrendPredictor initialisé sur {self.device}")

    def _create_features(self, data: pd.DataFrame) -> np.ndarray:
        """
        Crée les features pour la prédiction de tendance.

        Args:
            data: DataFrame avec colonnes 'close', 'volume', etc.

        Returns:
            np.ndarray: Features
        """
        features = []

        # Prix et retards
        close = data['close'].values
        for lag in [1, 5, 10, 20]:
            if len(close) > lag:
                features.append(np.roll(close, lag))

        # Rendements
        returns = np.diff(close, prepend=close[0])
        for lag in [1, 5, 10]:
            features.append(np.roll(returns, lag))

        # Moyennes mobiles
        for window in [5, 10, 20, 50]:
            if len(close) > window:
                ma = np.convolve(close, np.ones(window)/window, mode='same')
                features.append(ma)

        # Volatilité
        for window in [5, 10, 20]:
            if len(returns) > window:
                vol = pd.Series(returns).rolling(window).std().values
                features.append(vol)

        # RSI
        if len(close) > 14:
            delta = np.diff(close, prepend=close[0])
            gain = np.where(delta > 0, delta, 0)
            loss = np.where(delta < 0, -delta, 0)
            avg_gain = pd.Series(gain).rolling(14).mean().values
            avg_loss = pd.Series(loss).rolling(14).mean().values
            rs = avg_gain / (avg_loss + 1e-6)
            rsi = 100 - (100 / (1 + rs))
            features.append(rsi)

        # Volume
        if 'volume' in data.columns:
            volume = data['volume'].values
            features.append(volume)
            for window in [5, 10]:
                features.append(pd.Series(volume).rolling(window).mean().values)

        features = np.array(features).T
        valid_idx = ~np.isnan(features).any(axis=1)
        return features[valid_idx]

    def _create_target(self, data: pd.DataFrame) -> np.ndarray:
        """
        Crée la cible pour la prédiction de tendance.

        Args:
            data: DataFrame avec colonne 'close'

        Returns:
            np.ndarray: Labels (0: down, 1: sideways, 2: up)
        """
        close = data['close'].values
        future_returns = np.diff(close, n=self.config.prediction_horizon, prepend=close[0])

        # Classification
        threshold = 0.01  # 1%
        labels = np.zeros_like(future_returns, dtype=int)
        labels[future_returns > threshold] = 2  # up
        labels[future_returns < -threshold] = 0  # down
        labels[(future_returns >= -threshold) & (future_returns <= threshold)] = 1  # sideways

        return labels

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

    def fit(
        self,
        X: pd.DataFrame,
        y: Optional[np.ndarray] = None,
        validation_split: float = 0.2
    ) -> 'TrendPredictor':
        """
        Entraîne le prédicteur de tendance.

        Args:
            X: Données historiques
            y: Labels (optionnel)
            validation_split: Ratio de validation

        Returns:
            TrendPredictor: Instance entraînée
        """
        # Création des features
        features = self._create_features(X)

        if y is None:
            y = self._create_target(X)

        # Alignement
        min_len = min(len(features), len(y))
        features = features[:min_len]
        y = y[:min_len]

        # Normalisation
        if self.scaler is not None:
            features = self.scaler.fit_transform(features)

        # Split
        split_idx = int(len(features) * (1 - validation_split))
        X_train, X_val = features[:split_idx], features[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]

        # Création du modèle
        if self.config.model_type == 'xgboost' and XGB_AVAILABLE:
            self.model = xgb.XGBClassifier(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                learning_rate=self.config.learning_rate,
                random_state=self.config.random_state
            )
        elif self.config.model_type == 'random_forest' and SKLEARN_AVAILABLE:
            self.model = RandomForestClassifier(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                random_state=self.config.random_state
            )
        elif self.config.model_type == 'gradient_boosting' and SKLEARN_AVAILABLE:
            self.model = GradientBoostingClassifier(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.max_depth,
                learning_rate=self.config.learning_rate,
                random_state=self.config.random_state
            )
        elif self.config.model_type == 'lstm' and TORCH_AVAILABLE:
            self.model = _TrendLSTM(self.config).to(self.device)
        else:
            raise ValueError(f"Modèle non supporté: {self.config.model_type}")

        # Entraînement
        if self.config.model_type == 'lstm':
            self._fit_lstm(X_train, y_train, X_val, y_val)
        else:
            self.model.fit(X_train, y_train)

            # Importance des features
            if hasattr(self.model, 'feature_importances_'):
                self.feature_importance = self.model.feature_importances_

        self.is_fitted = True
        logger.info(f"Entraînement terminé")

        return self

    def _fit_lstm(self, X_train, y_train, X_val, y_val):
        """Entraîne le modèle LSTM"""
        # Préparation des séquences
        X_train_seq, y_train_seq = self._create_lstm_sequences(X_train)
        X_val_seq, y_val_seq = self._create_lstm_sequences(X_val)

        # Conversion en tenseurs
        X_train = torch.FloatTensor(X_train_seq).unsqueeze(-1).to(self.device)
        y_train = torch.LongTensor(y_train_seq).to(self.device)
        X_val = torch.FloatTensor(X_val_seq).unsqueeze(-1).to(self.device)
        y_val = torch.LongTensor(y_val_seq).to(self.device)

        # Optimiseur
        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.config.learning_rate)
        criterion = nn.CrossEntropyLoss()

        # Entraînement
        best_val_acc = 0
        patience_counter = 0

        for epoch in range(self.config.epochs):
            self.model.train()
            epoch_loss = 0.0

            for i in range(0, len(X_train), self.config.batch_size):
                batch_X = X_train[i:i + self.config.batch_size]
                batch_y = y_train[i:i + self.config.batch_size]

                optimizer.zero_grad()
                outputs = self.model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()

            # Validation
            self.model.eval()
            with torch.no_grad():
                val_outputs = self.model(X_val)
                val_preds = torch.argmax(val_outputs, dim=1)
                val_acc = (val_preds == y_val).float().mean().item()

            if val_acc > best_val_acc:
                best_val_acc = val_acc
                patience_counter = 0
            else:
                patience_counter += 1

            if self.config.early_stopping and patience_counter >= self.config.patience:
                logger.info(f"Arrêt précoce à l'époque {epoch+1}")
                break

    def predict(
        self,
        symbol: str,
        data: pd.DataFrame,
        return_details: bool = False
    ) -> Union[Dict[str, Any], TrendPredictionResult]:
        """
        Effectue une prédiction de tendance.

        Args:
            symbol: Symbole de l'actif
            data: Données historiques
            return_details: Retourner les détails

        Returns:
            Dict[str, Any]: Prédiction
            TrendPredictionResult: Résultat complet
        """
        if not self.is_fitted:
            raise ValueError("Le modèle doit être entraîné")

        # Cache
        cache_key = f"{symbol}_{data.index[-1]}" if hasattr(data, 'index') else symbol
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if (datetime.now() - cached.timestamp).seconds < 300:
                return cached

        # Features
        features = self._create_features(data)
        if len(features) == 0:
            raise ValueError("Pas assez de données")

        last_features = features[-1:]

        if self.scaler is not None:
            last_features = self.scaler.transform(last_features)

        # Prédiction
        if self.config.model_type == 'lstm':
            self.model.eval()
            with torch.no_grad():
                input_tensor = torch.FloatTensor(last_features).unsqueeze(1).to(self.device)
                output = self.model(input_tensor)
                probs = torch.softmax(output, dim=1).cpu().numpy()[0]
                pred_class = int(np.argmax(probs))
        else:
            probs = self.model.predict_proba(last_features)[0]
            pred_class = int(self.model.predict(last_features)[0])

        # Interprétation
        trend_map = {0: 'down', 1: 'sideways', 2: 'up'}
        predicted_trend = trend_map[pred_class]

        confidence = probs[pred_class]

        # Force de la tendance
        strength = np.max(probs) * (1 - np.std(probs))

        current_price = data['close'].iloc[-1]

        result = TrendPredictionResult(
            symbol=symbol,
            timestamp=datetime.now(),
            current_price=current_price,
            predicted_trend=predicted_trend,
            confidence=confidence,
            probability_up=probs[2],
            probability_down=probs[0],
            probability_sideways=probs[1],
            strength=strength,
            horizon='short' if self.config.prediction_horizon <= 1 else 'medium' if self.config.prediction_horizon <= 5 else 'long',
        )

        self._cache[cache_key] = result

        if return_details:
            return result

        return {
            'symbol': symbol,
            'trend': predicted_trend,
            'confidence': confidence,
            'strength': strength,
            'probabilities': {
                'up': probs[2],
                'down': probs[0],
                'sideways': probs[1],
            }
        }

    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres du prédicteur"""
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques du prédicteur"""
        return {
            'is_fitted': self.is_fitted,
            'device': str(self.device),
            'model_type': self.config.model_type,
            'feature_importance': self.feature_importance.tolist() if self.feature_importance is not None else None,
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
                'model': self.model,
                'scaler': self.scaler,
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
    def load(cls, filepath: str) -> 'TrendPredictor':
        """
        Charge un prédicteur.

        Args:
            filepath: Chemin du fichier

        Returns:
            TrendPredictor: Prédicteur chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = TrendPredictionConfig(**data['config'])
            predictor = cls(config)

            predictor.model = data.get('model')
            predictor.scaler = data.get('scaler')
            predictor.feature_importance = data.get('feature_importance')
            predictor.is_fitted = data.get('is_fitted', False)

            logger.info(f"Prédicteur chargé: {filepath}")
            return predictor

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_trend_predictor(
    lookback_window: int = 50,
    prediction_horizon: int = 1,
    model_type: str = 'xgboost',
    **kwargs
) -> TrendPredictor:
    """
    Factory pour créer un prédicteur de tendance.

    Args:
        lookback_window: Fenêtre de contexte
        prediction_horizon: Horizon de prédiction
        model_type: Type de modèle
        **kwargs: Arguments supplémentaires

    Returns:
        TrendPredictor: Prédicteur de tendance
    """
    config = TrendPredictionConfig(
        lookback_window=lookback_window,
        prediction_horizon=prediction_horizon,
        model_type=model_type,
        **kwargs
    )
    return TrendPredictor(config)


__all__ = [
    'TrendPredictor',
    'TrendPredictionConfig',
    'TrendPredictionResult',
    'create_trend_predictor',
]
