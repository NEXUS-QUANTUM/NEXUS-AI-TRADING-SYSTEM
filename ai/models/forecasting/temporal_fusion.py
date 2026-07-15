
# ai/models/forecasting/temporal_fusion.py
"""
NEXUS AI TRADING SYSTEM - Temporal Fusion Transformer for Time Series Forecasting
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
class TemporalFusionConfig:
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
    quantiles: List[float] = field(default_factory=lambda: [0.1, 0.5, 0.9])
    static_features: Optional[List[str]] = None
    time_features: Optional[List[str]] = None

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
            'quantiles': self.quantiles,
            'static_features': self.static_features,
            'time_features': self.time_features,
        }


@dataclass
class TemporalFusionResult:
    predictions: np.ndarray
    quantiles: Optional[Dict[float, np.ndarray]] = None
    lower_bound: Optional[np.ndarray] = None
    upper_bound: Optional[np.ndarray] = None
    attention_weights: Optional[np.ndarray] = None
    loss_history: Optional[List[float]] = None
    val_loss_history: Optional[List[float]] = None
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    prediction_length: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'quantiles': {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in (self.quantiles or {}).items()},
            'lower_bound': self.lower_bound.tolist() if isinstance(self.lower_bound, np.ndarray) else self.lower_bound,
            'upper_bound': self.upper_bound.tolist() if isinstance(self.upper_bound, np.ndarray) else self.upper_bound,
            'attention_weights': self.attention_weights.tolist() if isinstance(self.attention_weights, np.ndarray) else self.attention_weights,
            'loss_history': self.loss_history,
            'val_loss_history': self.val_loss_history,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
            'prediction_length': self.prediction_length,
        }


class _TemporalFusionBlock(nn.Module):
    """Bloc Temporal Fusion avec attention multi-têtes"""

    def __init__(
        self,
        hidden_size: int,
        num_heads: int,
        dropout: float
    ):
        super().__init__()

        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_size,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True
        )

        self.norm1 = nn.LayerNorm(hidden_size)
        self.norm2 = nn.LayerNorm(hidden_size)

        self.ffn = nn.Sequential(
            nn.Linear(hidden_size, hidden_size * 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size * 4, hidden_size),
            nn.Dropout(dropout),
        )

        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        attn_output, attn_weights = self.attention(x, x, x)
        x = self.norm1(x + self.dropout(attn_output))
        ffn_output = self.ffn(x)
        x = self.norm2(x + self.dropout(ffn_output))
        return x, attn_weights


class _TemporalFusionDecoder(nn.Module):
    """Décodeur Temporal Fusion avec LSTM et attention"""

    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        output_size: int,
        num_layers: int,
        dropout: float,
        num_heads: int
    ):
        super().__init__()

        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True
        )

        self.fusion_blocks = nn.ModuleList([
            _TemporalFusionBlock(hidden_size, num_heads, dropout)
            for _ in range(2)
        ])

        self.output_projection = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, output_size)
        )

    def forward(self, x, hidden=None, return_attention=False):
        lstm_output, hidden = self.lstm(x, hidden)

        attn_weights = []
        for block in self.fusion_blocks:
            lstm_output, attn = block(lstm_output)
            if return_attention:
                attn_weights.append(attn)

        outputs = self.output_projection(lstm_output)

        if return_attention:
            return outputs, hidden, attn_weights
        return outputs, hidden


class _TemporalFusionModel(nn.Module):
    """Modèle Temporal Fusion Transformer complet"""

    def __init__(self, config: TemporalFusionConfig):
        super().__init__()

        self.config = config
        self.quantiles = config.quantiles

        self.encoder = nn.LSTM(
            input_size=config.input_size,
            hidden_size=config.hidden_size,
            num_layers=config.num_layers,
            dropout=config.dropout if config.num_layers > 1 else 0,
            batch_first=True
        )

        self.decoder = _TemporalFusionDecoder(
            input_size=config.hidden_size,
            hidden_size=config.hidden_size,
            output_size=len(config.quantiles) * config.output_size,
            num_layers=config.num_layers,
            dropout=config.dropout,
            num_heads=config.num_heads
        )

        self.static_encoder = nn.Sequential(
            nn.Linear(config.input_size, config.hidden_size),
            nn.ReLU(),
            nn.Dropout(config.dropout)
        )

    def forward(self, x, hidden=None, return_attention=False):
        # Encodage
        encoder_output, hidden = self.encoder(x, hidden)

        # Décodage avec fusion temporelle
        outputs, hidden, attn_weights = self.decoder(
            encoder_output,
            hidden,
            return_attention=True
        )

        # Redimensionnement pour les quantiles
        batch_size, seq_len, _ = outputs.size()
        outputs = outputs.view(
            batch_size,
            seq_len,
            len(self.quantiles),
            self.config.output_size
        )

        if return_attention:
            return outputs, hidden, attn_weights
        return outputs, hidden


class TemporalFusionModel:
    """
    Temporal Fusion Transformer for time series forecasting.

    This implementation combines LSTM with multi-head attention for
    probabilistic forecasting with quantile predictions.

    Features:
    - Probabilistic forecasts with quantile predictions
    - Attention-based temporal fusion
    - Support for static and time-varying features
    - Multi-horizon forecasting
    - GPU acceleration

    Example:
        ```python
        config = TemporalFusionConfig(
            input_size=1,
            hidden_size=128,
            context_length=24,
            prediction_length=12,
            quantiles=[0.1, 0.5, 0.9],
            epochs=100
        )
        model = TemporalFusionModel(config)
        model.fit(train_data)
        predictions, quantiles = model.predict(test_data, return_quantiles=True)
        ```
    """

    def __init__(self, config: Optional[TemporalFusionConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis. Installez avec: pip install torch")

        self.config = config or TemporalFusionConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.model: Optional[_TemporalFusionModel] = None
        self.is_fitted = False
        self.scaler = None
        self.mean = None
        self.std = None
        self._prediction_cache: Dict[str, Any] = {}
        self.loss_history: List[float] = []
        self.val_loss_history: List[float] = []

        logger.info(f"TemporalFusionModel initialisé sur {self.device}")

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

    def _quantile_loss(self, predictions: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Perte quantile pour les prévisions probabilistes"""
        quantiles = torch.tensor(self.config.quantiles, device=predictions.device)
        errors = targets - predictions

        quantile_losses = []
        for i, q in enumerate(quantiles):
            q_pred = predictions[:, :, i, :]
            error = targets - q_pred
            loss = torch.max(q * error, (q - 1) * error)
            quantile_losses.append(loss.mean())

        return sum(quantile_losses) / len(quantile_losses)

    def _get_loss_function(self) -> nn.Module:
        """Retourne la fonction de perte"""
        class QuantileLoss(nn.Module):
            def __init__(self, quantiles):
                super().__init__()
                self.quantiles = quantiles

            def forward(self, predictions, targets):
                losses = []
                for i, q in enumerate(self.quantiles):
                    q_pred = predictions[:, :, i, :]
                    error = targets - q_pred
                    loss = torch.max(q * error, (q - 1) * error)
                    losses.append(loss.mean())
                return sum(losses) / len(losses)

        return QuantileLoss(self.config.quantiles)

    def fit(
        self,
        data: Union[np.ndarray, pd.Series, List[float]],
        validation_data: Optional[Union[np.ndarray, pd.Series, List[float]]] = None,
        **kwargs
    ) -> 'TemporalFusionModel':
        """
        Entraîne le modèle Temporal Fusion.

        Args:
            data: Données d'entraînement
            validation_data: Données de validation (optionnel)
            **kwargs: Arguments supplémentaires

        Returns:
            TemporalFusionModel: Instance entraînée
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

        self.model = _TemporalFusionModel(self.config).to(self.device)

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

        criterion = self._get_loss_function()

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
        return_quantiles: bool = False,
        return_attention: bool = False,
        return_details: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, Dict[float, np.ndarray]], TemporalFusionResult]:
        """
        Effectue une prédiction avec le modèle Temporal Fusion.

        Args:
            data: Données d'entrée
            prediction_length: Nombre d'étapes à prédire
            return_quantiles: Retourner les prédictions par quantile
            return_attention: Retourner les poids d'attention
            return_details: Retourner tous les détails

        Returns:
            np.ndarray: Prédictions (médiane)
            Tuple: (Médiane, Quantiles)
            TemporalFusionResult: Résultat complet
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

        cache_key = f"{hash(data.tobytes())}_{prediction_length}_{return_quantiles}"
        if cache_key in self._prediction_cache:
            logger.debug("Prédiction trouvée dans le cache")
            cached = self._prediction_cache[cache_key]
            if return_details:
                return cached
            elif return_quantiles:
                return cached.predictions, cached.quantiles
            else:
                return cached.predictions

        normalized_data = (data - self.mean) / self.std

        context = normalized_data[-self.config.context_length:]
        context_tensor = torch.FloatTensor(context).unsqueeze(0).unsqueeze(-1).to(self.device)

        self.model.eval()

        with torch.no_grad():
            predictions_list = []
            current_context = context_tensor
            attn_weights_all = []

            for _ in range(prediction_length):
                if return_attention:
                    pred, _, attn_weights = self.model(current_context, return_attention=True)
                    attn_weights_all.append(attn_weights)
                else:
                    pred, _ = self.model(current_context, return_attention=False)

                # Prendre la médiane (quantile 0.5)
                median_idx = self.config.quantiles.index(0.5) if 0.5 in self.config.quantiles else len(self.config.quantiles) // 2
                pred_value = pred[0, -1, median_idx, 0].item()

                predictions_list.append(pred_value)

                pred_tensor = torch.FloatTensor([[[pred_value]]]).to(self.device)
                current_context = torch.cat([
                    current_context[:, 1:, :],
                    pred_tensor
                ], dim=1)

            predictions = np.array(predictions_list)

            # Prédictions par quantile
            quantiles = None
            if return_quantiles:
                quantiles = {}
                for i, q in enumerate(self.config.quantiles):
                    q_preds = []
                    current_context = context_tensor
                    for _ in range(prediction_length):
                        pred, _ = self.model(current_context, return_attention=False)
                        pred_value = pred[0, -1, i, 0].item()
                        q_preds.append(pred_value)
                        pred_tensor = torch.FloatTensor([[[pred_value]]]).to(self.device)
                        current_context = torch.cat([
                            current_context[:, 1:, :],
                            pred_tensor
                        ], dim=1)
                    quantiles[q] = np.array(q_preds)

            # Attention weights
            attention_weights = None
            if return_attention and attn_weights_all:
                attention_weights = torch.stack(attn_weights_all).cpu().numpy()

        # Dénormalisation
        predictions = self._denormalize_data(predictions)
        if quantiles:
            quantiles = {q: self._denormalize_data(v) for q, v in quantiles.items()}

        lower_bound = None
        upper_bound = None
        if quantiles:
            q_values = sorted(quantiles.keys())
            if len(q_values) >= 2:
                lower_bound = quantiles[q_values[0]]
                upper_bound = quantiles[q_values[-1]]

        result = TemporalFusionResult(
            predictions=predictions,
            quantiles=quantiles,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            attention_weights=attention_weights,
            loss_history=self.loss_history,
            val_loss_history=self.val_loss_history,
            prediction_length=prediction_length,
        )

        self._prediction_cache[cache_key] = result

        if return_details:
            return result
        elif return_quantiles:
            return predictions, quantiles
        else:
            return predictions

    def predict_probabilistic(
        self,
        data: Union[np.ndarray, pd.Series, List[float]],
        prediction_length: Optional[int] = None
    ) -> Dict[float, np.ndarray]:
        """
        Retourne les prédictions probabilistes par quantile.

        Args:
            data: Données d'entrée
            prediction_length: Nombre d'étapes à prédire

        Returns:
            Dict[float, np.ndarray]: Prédictions par quantile
        """
        _, quantiles = self.predict(
            data,
            prediction_length=prediction_length,
            return_quantiles=True
        )
        return quantiles

    def get_params(self) -> Dict[str, Any]:
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        metrics = {
            'is_fitted': self.is_fitted,
            'loss_history_length': len(self.loss_history),
            'val_loss_history_length': len(self.val_loss_history),
            'device': str(self.device),
            'quantiles': self.config.quantiles,
            'context_length': self.config.context_length,
            'prediction_length': self.config.prediction_length,
            'hidden_size': self.config.hidden_size,
            'num_heads': self.config.num_heads,
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
    def load(cls, filepath: str) -> 'TemporalFusionModel':
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = TemporalFusionConfig(**data['config'])
            model = cls(config)

            if data.get('model_state_dict'):
                model.model = _TemporalFusionModel(config).to(model.device)
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


def create_temporal_fusion_model(
    input_size: int = 1,
    hidden_size: int = 128,
    context_length: int = 24,
    prediction_length: int = 12,
    quantiles: Optional[List[float]] = None,
    **kwargs
) -> TemporalFusionModel:
    if quantiles is None:
        quantiles = [0.1, 0.5, 0.9]

    config = TemporalFusionConfig(
        input_size=input_size,
        hidden_size=hidden_size,
        context_length=context_length,
        prediction_length=prediction_length,
        quantiles=quantiles,
        **kwargs
    )
    return TemporalFusionModel(config)


__all__ = [
    'TemporalFusionModel',
    'TemporalFusionConfig',
    'TemporalFusionResult',
    'create_temporal_fusion_model',
]

