
# ai/models/lstm/lstm_model.py
"""
NEXUS AI TRADING SYSTEM - LSTM Model for Time Series Forecasting
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
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class LSTMConfig:
    input_size: int = 1
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
    scheduler: Optional[str] = None
    teacher_forcing_ratio: float = 0.5
    use_peephole: bool = False
    use_layer_norm: bool = False

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

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
            'scheduler': self.scheduler,
            'teacher_forcing_ratio': self.teacher_forcing_ratio,
            'use_peephole': self.use_peephole,
            'use_layer_norm': self.use_layer_norm,
        }


@dataclass
class LSTMResult:
    predictions: np.ndarray
    hidden_states: Optional[List[np.ndarray]] = None
    loss_history: Optional[List[float]] = None
    val_loss_history: Optional[List[float]] = None
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    prediction_length: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'hidden_states': [h.tolist() if isinstance(h, np.ndarray) else h for h in (self.hidden_states or [])],
            'loss_history': self.loss_history,
            'val_loss_history': self.val_loss_history,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
            'prediction_length': self.prediction_length,
        }


class _LSTM(nn.Module):
    """Modèle LSTM de base"""

    def __init__(self, config: LSTMConfig):
        super().__init__()

        self.config = config
        self.hidden_size = config.hidden_size
        self.num_layers = config.num_layers
        self.teacher_forcing_ratio = config.teacher_forcing_ratio

        # LSTM Layer
        self.lstm = nn.LSTM(
            input_size=config.input_size,
            hidden_size=config.hidden_size,
            num_layers=config.num_layers,
            dropout=config.dropout if config.num_layers > 1 else 0,
            batch_first=True
        )

        # Layer Normalization (optionnelle)
        self.use_layer_norm = config.use_layer_norm
        if self.use_layer_norm:
            self.layer_norm = nn.LayerNorm(config.hidden_size)

        # Decoder
        self.decoder = nn.Sequential(
            nn.Linear(config.hidden_size, config.hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_size // 2, config.output_size)
        )

    def forward(self, x, hidden=None):
        lstm_output, hidden = self.lstm(x, hidden)

        if self.use_layer_norm:
            lstm_output = self.layer_norm(lstm_output)

        # Utiliser la dernière sortie pour la prédiction
        last_output = lstm_output[:, -1, :]
        output = self.decoder(last_output)

        return output, hidden


class _LSTMEncoderDecoder(nn.Module):
    """Modèle LSTM Encoder-Decoder pour séquence à séquence"""

    def __init__(self, config: LSTMConfig):
        super().__init__()

        self.config = config
        self.hidden_size = config.hidden_size
        self.num_layers = config.num_layers
        self.teacher_forcing_ratio = config.teacher_forcing_ratio

        # Encoder
        self.encoder = nn.LSTM(
            input_size=config.input_size,
            hidden_size=config.hidden_size,
            num_layers=config.num_layers,
            dropout=config.dropout if config.num_layers > 1 else 0,
            batch_first=True
        )

        # Decoder
        self.decoder = nn.LSTM(
            input_size=config.input_size,
            hidden_size=config.hidden_size,
            num_layers=config.num_layers,
            dropout=config.dropout if config.num_layers > 1 else 0,
            batch_first=True
        )

        # Output layer
        self.output_layer = nn.Sequential(
            nn.Linear(config.hidden_size, config.hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_size // 2, config.output_size)
        )

    def forward(self, x, hidden=None):
        # Encodage
        encoder_output, hidden = self.encoder(x, hidden)

        # Décodage
        decoder_input = encoder_output[:, -1:, :]
        decoder_output, hidden = self.decoder(decoder_input, hidden)

        output = self.output_layer(decoder_output)

        return output, hidden


class LSTM:
    """
    LSTM (Long Short-Term Memory) for time series forecasting.

    This implementation supports:
    - Standard LSTM
    - Encoder-Decoder architecture
    - Teacher forcing
    - Layer normalization
    - GPU acceleration
    - Early stopping
    - Model checkpointing
    - Multi-step predictions

    Example:
        ```python
        config = LSTMConfig(
            input_size=1,
            hidden_size=128,
            sequence_length=24,
            prediction_length=12,
            epochs=100
        )
        model = LSTM(config, use_encoder_decoder=True)
        model.fit(train_data)
        predictions = model.predict(test_data)
        ```
    """

    def __init__(self, config: Optional[LSTMConfig] = None, use_encoder_decoder: bool = False):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis. Installez avec: pip install torch")

        self.config = config or LSTMConfig()
        self.use_encoder_decoder = use_encoder_decoder
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.model: Optional[nn.Module] = None
        self.is_fitted = False
        self.scaler = None
        self.mean = None
        self.std = None
        self._prediction_cache: Dict[str, Any] = {}
        self.loss_history: List[float] = []
        self.val_loss_history: List[float] = []

        logger.info(f"LSTM initialisé sur {self.device}")

    def _normalize_data(self, data: np.ndarray) -> np.ndarray:
        self.mean = np.mean(data)
        self.std = np.std(data) + 1e-8
        return (data - self.mean) / self.std

    def _denormalize_data(self, data: np.ndarray) -> np.ndarray:
        if self.mean is None or self.std is None:
            return data
        return data * self.std + self.mean

    def _create_sequences(
        self,
        data: np.ndarray,
        sequence_length: int,
        prediction_length: int,
        step: int = 1
    ) -> Tuple[np.ndarray, np.ndarray]:
        sequences = []
        targets = []

        for i in range(0, len(data) - sequence_length - prediction_length + 1, step):
            seq = data[i:i + sequence_length]
            target = data[i + sequence_length:i + sequence_length + prediction_length]
            sequences.append(seq)
            targets.append(target)

        return np.array(sequences), np.array(targets)

    def _prepare_data(
        self,
        data: np.ndarray,
        sequence_length: int,
        prediction_length: int,
        batch_size: int,
        shuffle: bool = True
    ) -> DataLoader:
        sequences, targets = self._create_sequences(data, sequence_length, prediction_length)

        if len(sequences) == 0:
            raise ValueError("Pas assez de données pour créer des séquences")

        dataset = TensorDataset(
            torch.FloatTensor(sequences).unsqueeze(-1),
            torch.FloatTensor(targets).unsqueeze(-1)
        )

        return DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            drop_last=True
        )

    def _create_model(self) -> nn.Module:
        """Crée le modèle LSTM"""
        if self.use_encoder_decoder:
            return _LSTMEncoderDecoder(self.config)
        return _LSTM(self.config)

    def fit(
        self,
        data: Union[np.ndarray, pd.Series, List[float]],
        validation_data: Optional[Union[np.ndarray, pd.Series, List[float]]] = None,
        **kwargs
    ) -> 'LSTM':
        """
        Entraîne le modèle LSTM.

        Args:
            data: Données d'entraînement
            validation_data: Données de validation (optionnel)
            **kwargs: Arguments supplémentaires

        Returns:
            LSTM: Instance entraînée
        """
        if isinstance(data, pd.Series):
            data = data.values
        elif isinstance(data, list):
            data = np.array(data)

        if validation_data is not None:
            if isinstance(validation_data, pd.Series):
                validation_data = validation_data.values
            elif isinstance(validation_data, list):
                validation_data = np.array(validation_data)

        normalized_data = self._normalize_data(data)
        normalized_val = None
        if validation_data is not None:
            normalized_val = (validation_data - self.mean) / self.std

        config = self.config
        sequence_length = kwargs.get('sequence_length', config.sequence_length)
        prediction_length = kwargs.get('prediction_length', config.prediction_length)
        batch_size = kwargs.get('batch_size', config.batch_size)
        epochs = kwargs.get('epochs', config.epochs)
        learning_rate = kwargs.get('learning_rate', config.learning_rate)

        train_loader = self._prepare_data(
            normalized_data,
            sequence_length,
            prediction_length,
            batch_size,
            shuffle=True
        )

        val_loader = None
        if normalized_val is not None:
            val_loader = self._prepare_data(
                normalized_val,
                sequence_length,
                prediction_length,
                batch_size,
                shuffle=False
            )

        self.model = self._create_model().to(self.device)

        optimizer = optim.Adam(
            self.model.parameters(),
            lr=learning_rate,
            weight_decay=config.weight_decay
        )

        scheduler = None
        if config.scheduler == 'step':
            scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.1)
        elif config.scheduler == 'plateau':
            scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

        criterion = nn.MSELoss()

        self.loss_history = []
        self.val_loss_history = []
        best_val_loss = float('inf')
        patience_counter = 0

        logger.info(f"Début de l'entraînement pour {epochs} époques")

        for epoch in range(epochs):
            self.model.train()
            epoch_loss = 0.0
            num_batches = 0

            for batch_X, batch_y in train_loader:
                batch_X = batch_X.to(self.device)
                batch_y = batch_y.to(self.device)

                optimizer.zero_grad()

                predictions, _ = self.model(batch_X)

                if predictions.dim() == 3 and predictions.size(2) > 1:
                    predictions = predictions.squeeze(-1)

                if batch_y.dim() == 3 and batch_y.size(2) > 1:
                    batch_y = batch_y.squeeze(-1)

                loss = criterion(predictions, batch_y)
                loss.backward()

                if config.clip_gradient > 0:
                    torch.nn.utils.clip_grad_norm_(
                        self.model.parameters(),
                        config.clip_gradient
                    )

                optimizer.step()

                epoch_loss += loss.item()
                num_batches += 1

            avg_loss = epoch_loss / num_batches
            self.loss_history.append(avg_loss)

            val_loss = None
            if val_loader is not None:
                self.model.eval()
                val_loss = 0.0
                val_batches = 0

                with torch.no_grad():
                    for batch_X, batch_y in val_loader:
                        batch_X = batch_X.to(self.device)
                        batch_y = batch_y.to(self.device)

                        predictions, _ = self.model(batch_X)

                        if predictions.dim() == 3 and predictions.size(2) > 1:
                            predictions = predictions.squeeze(-1)

                        if batch_y.dim() == 3 and batch_y.size(2) > 1:
                            batch_y = batch_y.squeeze(-1)

                        loss = criterion(predictions, batch_y)
                        val_loss += loss.item()
                        val_batches += 1

                val_loss = val_loss / val_batches
                self.val_loss_history.append(val_loss)

            if scheduler is not None:
                if isinstance(scheduler, optim.lr_scheduler.ReduceLROnPlateau):
                    scheduler.step(val_loss)
                else:
                    scheduler.step()

            if epoch % 10 == 0 or epoch == epochs - 1:
                log_msg = f"Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.6f}"
                if val_loss is not None:
                    log_msg += f", Val Loss: {val_loss:.6f}"
                logger.debug(log_msg)

            if config.early_stopping and val_loss is not None:
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                    self._save_checkpoint()
                else:
                    patience_counter += 1
                    if patience_counter >= config.patience:
                        logger.info(f"Arrêt précoce à l'époque {epoch+1}")
                        break

        if config.early_stopping:
            self._load_checkpoint()

        self.is_fitted = True
        logger.info("Entraînement terminé")

        return self

    def _save_checkpoint(self):
        if self.model is None:
            return

        self._checkpoint = {
            'model_state_dict': self.model.state_dict(),
            'config': self.config,
            'mean': self.mean,
            'std': self.std,
        }

    def _load_checkpoint(self):
        if hasattr(self, '_checkpoint') and self.model is not None:
            self.model.load_state_dict(self._checkpoint['model_state_dict'])

    def predict(
        self,
        data: Union[np.ndarray, pd.Series, List[float]],
        prediction_length: Optional[int] = None,
        return_hidden: bool = False,
        return_details: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, List[np.ndarray]], LSTMResult]:
        """
        Effectue une prédiction avec le modèle LSTM.

        Args:
            data: Données d'entrée
            prediction_length: Nombre d'étapes à prédire
            return_hidden: Retourner les états cachés
            return_details: Retourner tous les détails

        Returns:
            np.ndarray: Prédictions
            Tuple: (Prédictions, États cachés)
            LSTMResult: Résultat complet
        """
        if not self.is_fitted:
            raise ValueError("Le modèle doit être entraîné avant de prédire")

        if isinstance(data, pd.Series):
            data = data.values
        elif isinstance(data, list):
            data = np.array(data)

        if prediction_length is None:
            prediction_length = self.config.prediction_length

        if len(data) < self.config.sequence_length:
            raise ValueError(f"Données insuffisantes. Besoin de {self.config.sequence_length} points")

        cache_key = f"{hash(data.tobytes())}_{prediction_length}"
        if cache_key in self._prediction_cache:
            logger.debug("Prédiction trouvée dans le cache")
            cached = self._prediction_cache[cache_key]
            if return_details:
                return cached
            elif return_hidden:
                return cached.predictions, cached.hidden_states
            else:
                return cached.predictions

        normalized_data = (data - self.mean) / self.std

        context = normalized_data[-self.config.sequence_length:]
        context_tensor = torch.FloatTensor(context).unsqueeze(0).unsqueeze(-1).to(self.device)

        self.model.eval()

        hidden_states_list = []
        predictions_list = []

        with torch.no_grad():
            current_context = context_tensor
            hidden = None

            for step in range(prediction_length):
                pred, hidden = self.model(current_context, hidden)

                pred_value = pred[0, 0].item()
                predictions_list.append(pred_value)

                if return_hidden:
                    if isinstance(hidden, tuple):
                        hidden_states_list.append(hidden[0].cpu().numpy())
                    else:
                        hidden_states_list.append(hidden.cpu().numpy())

                pred_tensor = torch.FloatTensor([[[pred_value]]]).to(self.device)
                current_context = torch.cat([
                    current_context[:, 1:, :],
                    pred_tensor
                ], dim=1)

            predictions = np.array(predictions_list)

        # Dénormalisation
        predictions = self._denormalize_data(predictions)

        result = LSTMResult(
            predictions=predictions,
            hidden_states=hidden_states_list if return_hidden else None,
            loss_history=self.loss_history,
            val_loss_history=self.val_loss_history,
            prediction_length=prediction_length,
        )

        self._prediction_cache[cache_key] = result

        if return_details:
            return result
        elif return_hidden:
            return predictions, hidden_states_list
        else:
            return predictions

    def get_hidden_states(self, data: Union[np.ndarray, pd.Series, List[float]]) -> np.ndarray:
        """
        Extrait les états cachés du modèle.

        Args:
            data: Données d'entrée

        Returns:
            np.ndarray: États cachés
        """
        _, hidden_states = self.predict(data, return_hidden=True)
        return np.array(hidden_states)

    def get_params(self) -> Dict[str, Any]:
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        metrics = {
            'is_fitted': self.is_fitted,
            'loss_history_length': len(self.loss_history),
            'val_loss_history_length': len(self.val_loss_history),
            'device': str(self.device),
            'use_encoder_decoder': self.use_encoder_decoder,
            'num_layers': self.config.num_layers,
            'sequence_length': self.config.sequence_length,
            'prediction_length': self.config.prediction_length,
            'hidden_size': self.config.hidden_size,
            'use_layer_norm': self.config.use_layer_norm,
            'use_peephole': self.config.use_peephole,
        }

        if self.loss_history:
            metrics['final_loss'] = self.loss_history[-1]
            metrics['min_loss'] = min(self.loss_history)

        if self.val_loss_history:
            metrics['final_val_loss'] = self.val_loss_history[-1]
            metrics['min_val_loss'] = min(self.val_loss_history)

        return metrics

    def save(self, filepath: str) -> bool:
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'model_state_dict': self.model.state_dict() if self.model else None,
                'mean': self.mean,
                'std': self.std,
                'is_fitted': self.is_fitted,
                'loss_history': self.loss_history,
                'val_loss_history': self.val_loss_history,
                'use_encoder_decoder': self.use_encoder_decoder,
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
    def load(cls, filepath: str) -> 'LSTM':
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = LSTMConfig(**data['config'])
            use_encoder_decoder = data.get('use_encoder_decoder', False)
            model = cls(config, use_encoder_decoder=use_encoder_decoder)

            if data.get('model_state_dict'):
                model.model = model._create_model().to(model.device)
                model.model.load_state_dict(data['model_state_dict'])

            model.mean = data.get('mean')
            model.std = data.get('std')
            model.is_fitted = data.get('is_fitted', False)
            model.loss_history = data.get('loss_history', [])
            model.val_loss_history = data.get('val_loss_history', [])

            logger.info(f"Modèle chargé: {filepath}")
            return model

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise


def create_lstm(
    input_size: int = 1,
    hidden_size: int = 128,
    num_layers: int = 2,
    sequence_length: int = 24,
    prediction_length: int = 12,
    use_encoder_decoder: bool = False,
    **kwargs
) -> LSTM:
    config = LSTMConfig(
        input_size=input_size,
        hidden_size=hidden_size,
        num_layers=num_layers,
        sequence_length=sequence_length,
        prediction_length=prediction_length,
        **kwargs
    )
    return LSTM(config, use_encoder_decoder=use_encoder_decoder)


__all__ = [
    'LSTM',
    'LSTMConfig',
    'LSTMResult',
    'create_lstm',
]
