
# ai/prediction/price_prediction.py
"""
NEXUS AI TRADING SYSTEM - Price Prediction Module
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
class PricePredictionConfig:
    """Configuration pour Price Prediction"""
    input_size: int = 20
    hidden_size: int = 128
    num_layers: int = 2
    output_size: int = 1
    dropout: float = 0.1
    learning_rate: float = 0.001
    batch_size: int = 64
    epochs: int = 100
    sequence_length: int = 24
    prediction_length: int = 1
    use_gpu: bool = False
    early_stopping: bool = True
    patience: int = 10
    clip_gradient: float = 1.0
    weight_decay: float = 1e-5
    random_state: Optional[int] = 42
    save_best: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'input_size': self.input_size,
            'hidden_size': self.hidden_size,
            'num_layers': self.num_layers,
            'output_size': self.output_size,
            'dropout': self.dropout,
            'learning_rate': self.learning_rate,
            'batch_size': self.batch_size,
            'epochs': self.epochs,
            'sequence_length': self.sequence_length,
            'prediction_length': self.prediction_length,
            'use_gpu': self.use_gpu,
            'early_stopping': self.early_stopping,
            'patience': self.patience,
            'clip_gradient': self.clip_gradient,
            'weight_decay': self.weight_decay,
            'random_state': self.random_state,
            'save_best': self.save_best,
        }


@dataclass
class PricePredictionResult:
    """Résultat de prédiction de prix"""
    symbol: str
    timestamp: datetime
    current_price: float
    predicted_price: float
    confidence: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    model_version: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'current_price': self.current_price,
            'predicted_price': self.predicted_price,
            'confidence': self.confidence,
            'lower_bound': self.lower_bound,
            'upper_bound': self.upper_bound,
            'model_version': self.model_version,
            'metadata': self.metadata,
        }


class _PriceLSTM(nn.Module):
    """Modèle LSTM pour prédiction de prix"""

    def __init__(self, config: PricePredictionConfig):
        super().__init__()

        self.lstm = nn.LSTM(
            input_size=config.input_size,
            hidden_size=config.hidden_size,
            num_layers=config.num_layers,
            dropout=config.dropout if config.num_layers > 1 else 0,
            batch_first=True
        )

        self.fc = nn.Sequential(
            nn.Linear(config.hidden_size, config.hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_size // 2, config.output_size)
        )

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        return self.fc(lstm_out[:, -1, :])


class PricePredictor:
    """
    Prédicteur de prix pour l'IA de trading.

    Features:
    - LSTM-based price prediction
    - Multi-step forecasting
    - Confidence estimation
    - Feature engineering
    - Model persistence

    Example:
        ```python
        config = PricePredictionConfig(
            sequence_length=24,
            prediction_length=1,
            hidden_size=128
        )
        predictor = PricePredictor(config)

        # Train
        predictor.fit(X_train, y_train)

        # Predict
        result = predictor.predict(symbol='BTC-USD', data=df)
        ```
    """

    def __init__(self, config: Optional[PricePredictionConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or PricePredictionConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.model: Optional[_PriceLSTM] = None
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self.is_fitted = False
        self.best_loss = float('inf')
        self._version = "1.0.0"

        logger.info(f"PricePredictor initialisé sur {self.device}")

    def _create_sequences(
        self,
        data: np.ndarray,
        sequence_length: int,
        prediction_length: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Crée des séquences pour l'entraînement"""
        sequences = []
        targets = []

        for i in range(len(data) - sequence_length - prediction_length + 1):
            seq = data[i:i + sequence_length]
            target = data[i + sequence_length:i + sequence_length + prediction_length]
            sequences.append(seq)
            targets.append(target)

        return np.array(sequences), np.array(targets)

    def _prepare_data(
        self,
        data: np.ndarray,
        sequence_length: Optional[int] = None,
        prediction_length: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Prépare les données pour l'entraînement"""
        seq_len = sequence_length or self.config.sequence_length
        pred_len = prediction_length or self.config.prediction_length

        # Normalisation
        if self.scaler is not None:
            data = self.scaler.fit_transform(data.reshape(-1, 1)).flatten()

        sequences, targets = self._create_sequences(data, seq_len, pred_len)

        return sequences, targets

    def fit(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Optional[Union[np.ndarray, pd.Series]] = None,
        validation_split: float = 0.2,
        **kwargs
    ) -> 'PricePredictor':
        """
        Entraîne le modèle de prédiction de prix.

        Args:
            X: Données d'entrée (prix historiques)
            y: Cibles (optionnel, si None utilise X décalé)
            validation_split: Ratio de validation
            **kwargs: Arguments supplémentaires

        Returns:
            PricePredictor: Instance entraînée
        """
        if isinstance(X, pd.DataFrame):
            X = X['close'].values if 'close' in X.columns else X.values
        elif isinstance(X, pd.Series):
            X = X.values

        # Préparation des données
        if y is None:
            sequences, targets = self._prepare_data(X)
        else:
            if isinstance(y, pd.Series):
                y = y.values
            sequences, targets = self._prepare_data(np.concatenate([X, y]))

        # Split
        split_idx = int(len(sequences) * (1 - validation_split))
        X_train, X_val = sequences[:split_idx], sequences[split_idx:]
        y_train, y_val = targets[:split_idx], targets[split_idx:]

        # Tensor conversion
        X_train = torch.FloatTensor(X_train).to(self.device)
        y_train = torch.FloatTensor(y_train).to(self.device)
        X_val = torch.FloatTensor(X_val).to(self.device)
        y_val = torch.FloatTensor(y_val).to(self.device)

        # Modèle
        self.model = _PriceLSTM(self.config).to(self.device)
        optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay
        )
        criterion = nn.MSELoss()

        # Entraînement
        best_val_loss = float('inf')
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

                if self.config.clip_gradient > 0:
                    torch.nn.utils.clip_grad_norm_(
                        self.model.parameters(),
                        self.config.clip_gradient
                    )

                optimizer.step()
                epoch_loss += loss.item()

            # Validation
            self.model.eval()
            with torch.no_grad():
                val_outputs = self.model(X_val)
                val_loss = criterion(val_outputs, y_val).item()

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                self.best_loss = best_val_loss

                if self.config.save_best:
                    self._save_checkpoint()
            else:
                patience_counter += 1

            if epoch % 10 == 0:
                logger.debug(f"Epoch {epoch+1}/{self.config.epochs}, Loss: {epoch_loss/len(X_train):.6f}, Val Loss: {val_loss:.6f}")

            if self.config.early_stopping and patience_counter >= self.config.patience:
                logger.info(f"Arrêt précoce à l'époque {epoch+1}")
                break

        self.is_fitted = True
        logger.info(f"Entraînement terminé - Best Loss: {self.best_loss:.6f}")

        return self

    def _save_checkpoint(self):
        """Sauvegarde le checkpoint du modèle"""
        if self.model is not None:
            self._checkpoint = {
                'model_state_dict': self.model.state_dict(),
                'config': self.config,
                'scaler': self.scaler,
                'best_loss': self.best_loss,
                'version': self._version,
            }

    def predict(
        self,
        symbol: str,
        data: Union[np.ndarray, pd.DataFrame, pd.Series],
        return_details: bool = False
    ) -> Union[float, PricePredictionResult]:
        """
        Effectue une prédiction de prix.

        Args:
            symbol: Symbole de l'actif
            data: Données historiques
            return_details: Retourner les détails

        Returns:
            float: Prix prédit
            PricePredictionResult: Résultat complet
        """
        if not self.is_fitted:
            raise ValueError("Le modèle doit être entraîné")

        if isinstance(data, pd.DataFrame):
            data = data['close'].values if 'close' in data.columns else data.values
        elif isinstance(data, pd.Series):
            data = data.values

        # Préparation
        if len(data) < self.config.sequence_length:
            raise ValueError(f"Données insuffisantes. Besoin de {self.config.sequence_length} points")

        last_sequence = data[-self.config.sequence_length:]

        if self.scaler is not None:
            last_sequence = self.scaler.transform(last_sequence.reshape(-1, 1)).flatten()

        # Prédiction
        self.model.eval()
        with torch.no_grad():
            input_tensor = torch.FloatTensor(last_sequence).unsqueeze(0).unsqueeze(-1).to(self.device)
            prediction = self.model(input_tensor).cpu().numpy().flatten()[0]

        # Dénormalisation
        if self.scaler is not None:
            prediction = self.scaler.inverse_transform([[prediction]])[0][0]

        current_price = data[-1]
        confidence = 1 - (self.best_loss / (current_price + 1e-6))

        if return_details:
            return PricePredictionResult(
                symbol=symbol,
                timestamp=datetime.now(),
                current_price=current_price,
                predicted_price=prediction,
                confidence=confidence,
                model_version=self._version,
            )

        return prediction

    def predict_batch(
        self,
        symbols: List[str],
        data_dict: Dict[str, pd.DataFrame]
    ) -> Dict[str, float]:
        """
        Effectue des prédictions batch.

        Args:
            symbols: Liste des symboles
            data_dict: Dictionnaire des données par symbole

        Returns:
            Dict[str, float]: Prédictions par symbole
        """
        results = {}

        for symbol in symbols:
            if symbol in data_dict:
                results[symbol] = self.predict(symbol, data_dict[symbol])

        return results

    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres du prédicteur"""
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques du prédicteur"""
        return {
            'is_fitted': self.is_fitted,
            'device': str(self.device),
            'best_loss': self.best_loss,
            'version': self._version,
            'sequence_length': self.config.sequence_length,
            'prediction_length': self.config.prediction_length,
            'hidden_size': self.config.hidden_size,
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
                'model_state_dict': self.model.state_dict() if self.model else None,
                'scaler': self.scaler,
                'best_loss': self.best_loss,
                'is_fitted': self.is_fitted,
                'version': self._version,
                'timestamp': datetime.now().isoformat(),
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Prédicteur sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'PricePredictor':
        """
        Charge un prédicteur.

        Args:
            filepath: Chemin du fichier

        Returns:
            PricePredictor: Prédicteur chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = PricePredictionConfig(**data['config'])
            predictor = cls(config)

            if data.get('model_state_dict'):
                predictor.model = _PriceLSTM(config).to(predictor.device)
                predictor.model.load_state_dict(data['model_state_dict'])

            predictor.scaler = data.get('scaler')
            predictor.best_loss = data.get('best_loss', float('inf'))
            predictor.is_fitted = data.get('is_fitted', False)
            predictor._version = data.get('version', '1.0.0')

            logger.info(f"Prédicteur chargé: {filepath}")
            return predictor

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_price_predictor(
    sequence_length: int = 24,
    prediction_length: int = 1,
    hidden_size: int = 128,
    **kwargs
) -> PricePredictor:
    """
    Factory pour créer un prédicteur de prix.

    Args:
        sequence_length: Longueur de la séquence
        prediction_length: Longueur de prédiction
        hidden_size: Taille du cache
        **kwargs: Arguments supplémentaires

    Returns:
        PricePredictor: Prédicteur de prix
    """
    config = PricePredictionConfig(
        sequence_length=sequence_length,
        prediction_length=prediction_length,
        hidden_size=hidden_size,
        **kwargs
    )
    return PricePredictor(config)


__all__ = [
    'PricePredictor',
    'PricePredictionConfig',
    'PricePredictionResult',
    'create_price_predictor',
]
