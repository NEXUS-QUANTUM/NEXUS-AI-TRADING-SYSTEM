
# ai/models/transformers/time_series_transformer.py
"""
NEXUS AI TRADING SYSTEM - Time Series Transformer Model
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
class TimeSeriesTransformerConfig:
    input_size: int = 1
    output_size: int = 1
    hidden_size: int = 128
    num_layers: int = 2
    num_heads: int = 4
    dropout: float = 0.1
    learning_rate: float = 0.001
    batch_size: int = 64
    epochs: int = 100
    context_length: int = 24
    prediction_length: int = 12
    use_gpu: bool = False
    early_stopping: bool = True
    patience: int = 10
    clip_gradient: float = 1.0
    weight_decay: float = 1e-5
    scheduler: Optional[str] = None
    use_positional_encoding: bool = True
    activation: str = 'gelu'
    norm_first: bool = False
    bias: bool = True
    use_causal_mask: bool = False

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'input_size': self.input_size,
            'output_size': self.output_size,
            'hidden_size': self.hidden_size,
            'num_layers': self.num_layers,
            'num_heads': self.num_heads,
            'dropout': self.dropout,
            'learning_rate': self.learning_rate,
            'batch_size': self.batch_size,
            'epochs': self.epochs,
            'context_length': self.context_length,
            'prediction_length': self.prediction_length,
            'use_gpu': self.use_gpu,
            'early_stopping': self.early_stopping,
            'patience': self.patience,
            'clip_gradient': self.clip_gradient,
            'weight_decay': self.weight_decay,
            'scheduler': self.scheduler,
            'use_positional_encoding': self.use_positional_encoding,
            'activation': self.activation,
            'norm_first': self.norm_first,
            'bias': self.bias,
            'use_causal_mask': self.use_causal_mask,
        }


@dataclass
class TimeSeriesTransformerResult:
    predictions: np.ndarray
    attention_weights: Optional[np.ndarray] = None
    loss_history: Optional[List[float]] = None
    val_loss_history: Optional[List[float]] = None
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    prediction_length: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'attention_weights': self.attention_weights.tolist() if isinstance(self.attention_weights, np.ndarray) else self.attention_weights,
            'loss_history': self.loss_history,
            'val_loss_history': self.val_loss_history,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
            'prediction_length': self.prediction_length,
        }


class _PositionalEncoding(nn.Module):
    """Encodage positionnel pour Transformer"""

    def __init__(self, hidden_size: int, max_len: int = 1000):
        super().__init__()

        pe = torch.zeros(max_len, hidden_size)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, hidden_size, 2).float() * (-np.log(10000.0) / hidden_size))

        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)

        self.register_buffer('pe', pe)

    def forward(self, x):
        return x + self.pe[:, :x.size(1), :]


class _TimeSeriesTransformerModel(nn.Module):
    """Modèle Transformer pour séries temporelles"""

    def __init__(self, config: TimeSeriesTransformerConfig):
        super().__init__()

        self.config = config
        self.hidden_size = config.hidden_size

        # Projection d'entrée
        self.input_proj = nn.Linear(config.input_size, config.hidden_size, bias=config.bias)

        # Positional encoding
        if config.use_positional_encoding:
            self.pos_encoder = _PositionalEncoding(config.hidden_size)

        # Encoder Transformer
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.hidden_size,
            nhead=config.num_heads,
            dim_feedforward=config.hidden_size * 4,
            dropout=config.dropout,
            activation=config.activation,
            batch_first=True,
            norm_first=config.norm_first,
            bias=config.bias,
        )

        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=config.num_layers)

        # Decoder Transformer
        decoder_layer = nn.TransformerDecoderLayer(
            d_model=config.hidden_size,
            nhead=config.num_heads,
            dim_feedforward=config.hidden_size * 4,
            dropout=config.dropout,
            activation=config.activation,
            batch_first=True,
            norm_first=config.norm_first,
            bias=config.bias,
        )

        self.decoder = nn.TransformerDecoder(decoder_layer, num_layers=config.num_layers)

        # Projection de sortie
        self.output_proj = nn.Linear(config.hidden_size, config.output_size, bias=config.bias)

        # Masque causal
        if config.use_causal_mask:
            self.register_buffer(
                'causal_mask',
                torch.triu(torch.ones(1, 1, config.prediction_length, config.prediction_length), diagonal=1).bool()
            )
        else:
            self.causal_mask = None

    def forward(self, x):
        batch_size = x.size(0)

        # Projection d'entrée
        x = self.input_proj(x)

        # Positional encoding
        if self.config.use_positional_encoding:
            x = self.pos_encoder(x)

        # Encodage
        memory = self.encoder(x)

        # Décodage (auto-régressif simplifié)
        # Utiliser la dernière position comme première entrée du décodeur
        tgt = x[:, -1:, :]

        # Répéter pour la longueur de prédiction
        tgt = tgt.repeat(1, self.config.prediction_length, 1)

        # Décodage
        if self.causal_mask is not None:
            output = self.decoder(tgt, memory, tgt_mask=self.causal_mask)
        else:
            output = self.decoder(tgt, memory)

        # Projection de sortie
        output = self.output_proj(output)

        return output


class TimeSeriesTransformer:
    """
    Time Series Transformer model for forecasting.

    This implementation provides a standard Transformer architecture
    adapted for time series forecasting with encoder-decoder structure.

    Features:
    - Full Transformer encoder-decoder architecture
    - Positional encoding for sequence order
    - Causal masking for autoregressive decoding
    - GPU acceleration
    - Early stopping
    - Model checkpointing

    Example:
        ```python
        config = TimeSeriesTransformerConfig(
            input_size=1,
            hidden_size=128,
            context_length=24,
            prediction_length=12,
            num_layers=2,
            num_heads=4,
            epochs=100
        )
        model = TimeSeriesTransformer(config)
        model.fit(train_data)
        predictions = model.predict(test_data)
        ```
    """

    def __init__(self, config: Optional[TimeSeriesTransformerConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis. Installez avec: pip install torch")

        self.config = config or TimeSeriesTransformerConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.model: Optional[_TimeSeriesTransformerModel] = None
        self.is_fitted = False
        self.scaler = None
        self.mean = None
        self.std = None
        self._prediction_cache: Dict[str, Any] = {}
        self.loss_history: List[float] = []
        self.val_loss_history: List[float] = []

        logger.info(f"TimeSeriesTransformer initialisé sur {self.device}")

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
        context_length: int,
        prediction_length: int,
        step: int = 1
    ) -> Tuple[np.ndarray, np.ndarray]:
        sequences = []
        targets = []

        for i in range(0, len(data) - context_length - prediction_length + 1, step):
            seq = data[i:i + context_length]
            target = data[i + context_length:i + context_length + prediction_length]
            sequences.append(seq)
            targets.append(target)

        return np.array(sequences), np.array(targets)

    def _prepare_data(
        self,
        data: np.ndarray,
        context_length: int,
        prediction_length: int,
        batch_size: int,
        shuffle: bool = True
    ) -> DataLoader:
        sequences, targets = self._create_sequences(data, context_length, prediction_length)

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

    def fit(
        self,
        data: Union[np.ndarray, pd.Series, List[float]],
        validation_data: Optional[Union[np.ndarray, pd.Series, List[float]]] = None,
        **kwargs
    ) -> 'TimeSeriesTransformer':
        """
        Entraîne le modèle Time Series Transformer.

        Args:
            data: Données d'entraînement
            validation_data: Données de validation (optionnel)
            **kwargs: Arguments supplémentaires

        Returns:
            TimeSeriesTransformer: Instance entraînée
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
        context_length = kwargs.get('context_length', config.context_length)
        prediction_length = kwargs.get('prediction_length', config.prediction_length)
        batch_size = kwargs.get('batch_size', config.batch_size)
        epochs = kwargs.get('epochs', config.epochs)
        learning_rate = kwargs.get('learning_rate', config.learning_rate)

        train_loader = self._prepare_data(
            normalized_data,
            context_length,
            prediction_length,
            batch_size,
            shuffle=True
        )

        val_loader = None
        if normalized_val is not None:
            val_loader = self._prepare_data(
                normalized_val,
                context_length,
                prediction_length,
                batch_size,
                shuffle=False
            )

        self.model = _TimeSeriesTransformerModel(self.config).to(self.device)

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

                predictions = self.model(batch_X)

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

                        predictions = self.model(batch_X)

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
        return_attention: bool = False,
        return_details: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray], TimeSeriesTransformerResult]:
        """
        Effectue une prédiction avec le modèle Transformer.

        Args:
            data: Données d'entrée
            prediction_length: Nombre d'étapes à prédire
            return_attention: Retourner les poids d'attention
            return_details: Retourner tous les détails

        Returns:
            np.ndarray: Prédictions
            Tuple: (Prédictions, Poids d'attention)
            TimeSeriesTransformerResult: Résultat complet
        """
        if not self.is_fitted:
            raise ValueError("Le modèle doit être entraîné avant de prédire")

        if isinstance(data, pd.Series):
            data = data.values
        elif isinstance(data, list):
            data = np.array(data)

        if prediction_length is None:
            prediction_length = self.config.prediction_length

        if len(data) < self.config.context_length:
            raise ValueError(f"Données insuffisantes. Besoin de {self.config.context_length} points")

        cache_key = f"{hash(data.tobytes())}_{prediction_length}_{return_attention}"
        if cache_key in self._prediction_cache:
            logger.debug("Prédiction trouvée dans le cache")
            cached = self._prediction_cache[cache_key]
            if return_details:
                return cached
            elif return_attention:
                return cached.predictions, cached.attention_weights
            else:
                return cached.predictions

        normalized_data = (data - self.mean) / self.std

        context = normalized_data[-self.config.context_length:]
        context_tensor = torch.FloatTensor(context).unsqueeze(0).unsqueeze(-1).to(self.device)

        self.model.eval()

        predictions_list = []
        attention_weights_list = []

        with torch.no_grad():
            current_context = context_tensor

            for step in range(prediction_length):
                pred = self.model(current_context)
                pred_value = pred[0, -1, 0].item()

                predictions_list.append(pred_value)

                pred_tensor = torch.FloatTensor([[[pred_value]]]).to(self.device)
                current_context = torch.cat([
                    current_context[:, 1:, :],
                    pred_tensor
                ], dim=1)

            predictions = np.array(predictions_list)

        # Dénormalisation
        predictions = self._denormalize_data(predictions)

        result = TimeSeriesTransformerResult(
            predictions=predictions,
            attention_weights=None,
            loss_history=self.loss_history,
            val_loss_history=self.val_loss_history,
            prediction_length=prediction_length,
        )

        self._prediction_cache[cache_key] = result

        if return_details:
            return result
        elif return_attention:
            return predictions, result.attention_weights
        else:
            return predictions

    def get_params(self) -> Dict[str, Any]:
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        metrics = {
            'is_fitted': self.is_fitted,
            'loss_history_length': len(self.loss_history),
            'val_loss_history_length': len(self.val_loss_history),
            'device': str(self.device),
            'context_length': self.config.context_length,
            'prediction_length': self.config.prediction_length,
            'hidden_size': self.config.hidden_size,
            'num_heads': self.config.num_heads,
            'num_layers': self.config.num_layers,
            'use_positional_encoding': self.config.use_positional_encoding,
            'use_causal_mask': self.config.use_causal_mask,
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
    def load(cls, filepath: str) -> 'TimeSeriesTransformer':
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = TimeSeriesTransformerConfig(**data['config'])
            model = cls(config)

            if data.get('model_state_dict'):
                model.model = _TimeSeriesTransformerModel(config).to(model.device)
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


def create_time_series_transformer(
    input_size: int = 1,
    hidden_size: int = 128,
    context_length: int = 24,
    prediction_length: int = 12,
    num_layers: int = 2,
    num_heads: int = 4,
    **kwargs
) -> TimeSeriesTransformer:
    config = TimeSeriesTransformerConfig(
        input_size=input_size,
        hidden_size=hidden_size,
        context_length=context_length,
        prediction_length=prediction_length,
        num_layers=num_layers,
        num_heads=num_heads,
        **kwargs
    )
    return TimeSeriesTransformer(config)


__all__ = [
    'TimeSeriesTransformer',
    'TimeSeriesTransformerConfig',
    'TimeSeriesTransformerResult',
    'create_time_series_transformer',
]
