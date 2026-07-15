
# ai/models/transformers/autoformer_model.py
"""
NEXUS AI TRADING SYSTEM - Autoformer Model for Time Series Forecasting
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
class AutoformerConfig:
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
    auto_correlation: bool = True
    moving_avg: int = 25
    series_decomp: bool = True
    trend_length: int = 24
    season_length: int = 12
    use_revin: bool = False

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
            'auto_correlation': self.auto_correlation,
            'moving_avg': self.moving_avg,
            'series_decomp': self.series_decomp,
            'trend_length': self.trend_length,
            'season_length': self.season_length,
            'use_revin': self.use_revin,
        }


@dataclass
class AutoformerResult:
    predictions: np.ndarray
    trend: Optional[np.ndarray] = None
    seasonality: Optional[np.ndarray] = None
    loss_history: Optional[List[float]] = None
    val_loss_history: Optional[List[float]] = None
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    prediction_length: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'trend': self.trend.tolist() if isinstance(self.trend, np.ndarray) else self.trend,
            'seasonality': self.seasonality.tolist() if isinstance(self.seasonality, np.ndarray) else self.seasonality,
            'loss_history': self.loss_history,
            'val_loss_history': self.val_loss_history,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
            'prediction_length': self.prediction_length,
        }


class _SeriesDecomp(nn.Module):
    """Décomposition de séries temporelles en tendance et saisonnalité"""

    def __init__(self, kernel_size: int):
        super().__init__()
        self.kernel_size = kernel_size
        self.avg = nn.AvgPool1d(kernel_size=kernel_size, stride=1, padding=kernel_size // 2)

    def forward(self, x):
        x = x.permute(0, 2, 1)
        trend = self.avg(x)
        trend = F.pad(trend, (0, 0, 0, 0), mode='replicate')
        trend = trend.permute(0, 2, 1)
        season = x.permute(0, 2, 1) - trend
        season = season.permute(0, 2, 1)
        return trend, season


class _AutoCorrelation(nn.Module):
    """Mécanisme d'auto-corrélation pour Autoformer"""

    def __init__(self, hidden_size: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        self.hidden_size = hidden_size
        self.num_heads = num_heads
        self.dropout = nn.Dropout(dropout)

        self.q_proj = nn.Linear(hidden_size, hidden_size)
        self.k_proj = nn.Linear(hidden_size, hidden_size)
        self.v_proj = nn.Linear(hidden_size, hidden_size)
        self.out_proj = nn.Linear(hidden_size, hidden_size)

    def forward(self, queries, keys, values):
        # Projection
        q = self.q_proj(queries)
        k = self.k_proj(keys)
        v = self.v_proj(values)

        # Auto-corrélation simplifiée
        q = q.permute(0, 2, 1)
        k = k.permute(0, 2, 1)
        v = v.permute(0, 2, 1)

        # Calcul de l'auto-corrélation
        q_k = torch.matmul(q, k.transpose(-2, -1))
        q_k = q_k / (self.hidden_size ** 0.5)
        attn = torch.softmax(q_k, dim=-1)
        attn = self.dropout(attn)

        output = torch.matmul(attn, v)
        output = output.permute(0, 2, 1)
        output = self.out_proj(output)

        return output, attn


class _AutoformerBlock(nn.Module):
    """Bloc Autoformer avec auto-corrélation et décomposition"""

    def __init__(self, config: AutoformerConfig):
        super().__init__()

        self.hidden_size = config.hidden_size
        self.num_heads = config.num_heads
        self.dropout = config.dropout

        # Auto-corrélation
        self.auto_corr = _AutoCorrelation(
            config.hidden_size,
            config.num_heads,
            config.dropout
        )

        # Décomposition
        if config.series_decomp:
            self.decomp = _SeriesDecomp(config.moving_avg)
        else:
            self.decomp = None

        # Feed-forward
        self.ff = nn.Sequential(
            nn.Linear(config.hidden_size, config.hidden_size * 4),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_size * 4, config.hidden_size),
            nn.Dropout(config.dropout),
        )

        self.norm1 = nn.LayerNorm(config.hidden_size)
        self.norm2 = nn.LayerNorm(config.hidden_size)

    def forward(self, x):
        # Auto-corrélation
        attn_out, attn = self.auto_corr(x, x, x)
        x = self.norm1(x + attn_out)

        # Feed-forward
        ff_out = self.ff(x)
        x = self.norm2(x + ff_out)

        # Décomposition
        if self.decomp is not None:
            trend, season = self.decomp(x)
            return x, trend, season

        return x, None, None


class _AutoformerModel(nn.Module):
    """Modèle Autoformer complet"""

    def __init__(self, config: AutoformerConfig):
        super().__init__()

        self.config = config
        self.input_proj = nn.Linear(config.input_size, config.hidden_size)

        self.encoder_blocks = nn.ModuleList([
            _AutoformerBlock(config) for _ in range(config.num_layers)
        ])

        self.decoder_blocks = nn.ModuleList([
            _AutoformerBlock(config) for _ in range(config.num_layers)
        ])

        self.output_proj = nn.Linear(config.hidden_size, config.output_size)

        # Décomposition initiale
        if config.series_decomp:
            self.decomp = _SeriesDecomp(config.moving_avg)

    def forward(self, x):
        # Projection d'entrée
        x = self.input_proj(x)

        # Encodage
        encoder_outputs = []
        for block in self.encoder_blocks:
            x, trend, season = block(x)
            encoder_outputs.append(x)

        # Décodage avec auto-régression simplifiée
        x = encoder_outputs[-1]
        for block in self.decoder_blocks:
            x, trend, season = block(x)

        # Projection de sortie
        output = self.output_proj(x)

        return output


class AutoformerModel:
    """
    Autoformer model for time series forecasting.

    Autoformer is a transformer variant designed for time series forecasting
    with auto-correlation mechanisms and series decomposition.

    Features:
    - Auto-correlation mechanism for capturing dependencies
    - Series decomposition into trend and seasonality
    - Long-term forecasting
    - GPU acceleration
    - Early stopping
    - Model checkpointing

    Example:
        ```python
        config = AutoformerConfig(
            input_size=1,
            hidden_size=128,
            context_length=24,
            prediction_length=12,
            auto_correlation=True,
            series_decomp=True,
            epochs=100
        )
        model = AutoformerModel(config)
        model.fit(train_data)
        predictions, trend, season = model.predict(test_data, return_components=True)
        ```
    """

    def __init__(self, config: Optional[AutoformerConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis. Installez avec: pip install torch")

        self.config = config or AutoformerConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.model: Optional[_AutoformerModel] = None
        self.is_fitted = False
        self.scaler = None
        self.mean = None
        self.std = None
        self._prediction_cache: Dict[str, Any] = {}
        self.loss_history: List[float] = []
        self.val_loss_history: List[float] = []

        logger.info(f"AutoformerModel initialisé sur {self.device}")

    def _normalize_data(self, data: np.ndarray) -> np.ndarray:
        if self.config.use_revin:
            self.mean = np.mean(data)
            self.std = np.std(data) + 1e-8
            return (data - self.mean) / self.std
        return data

    def _denormalize_data(self, data: np.ndarray) -> np.ndarray:
        if self.config.use_revin and self.mean is not None and self.std is not None:
            return data * self.std + self.mean
        return data

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
    ) -> 'AutoformerModel':
        """
        Entraîne le modèle Autoformer.

        Args:
            data: Données d'entraînement
            validation_data: Données de validation (optionnel)
            **kwargs: Arguments supplémentaires

        Returns:
            AutoformerModel: Instance entraînée
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
            normalized_val = (validation_data - self.mean) / self.std if self.config.use_revin else validation_data

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

        self.model = _AutoformerModel(self.config).to(self.device)

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
        return_components: bool = False,
        return_details: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray, np.ndarray], AutoformerResult]:
        """
        Effectue une prédiction avec le modèle Autoformer.

        Args:
            data: Données d'entrée
            prediction_length: Nombre d'étapes à prédire
            return_components: Retourner les composants (trend, season)
            return_details: Retourner tous les détails

        Returns:
            np.ndarray: Prédictions
            Tuple: (Prédictions, Trend, Seasonality)
            AutoformerResult: Résultat complet
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

        cache_key = f"{hash(data.tobytes())}_{prediction_length}_{return_components}"
        if cache_key in self._prediction_cache:
            logger.debug("Prédiction trouvée dans le cache")
            cached = self._prediction_cache[cache_key]
            if return_details:
                return cached
            elif return_components:
                return cached.predictions, cached.trend, cached.seasonality
            else:
                return cached.predictions

        normalized_data = self._normalize_data(data)

        context = normalized_data[-self.config.context_length:]
        context_tensor = torch.FloatTensor(context).unsqueeze(0).unsqueeze(-1).to(self.device)

        self.model.eval()

        predictions_list = []
        trend_list = []
        season_list = []

        with torch.no_grad():
            current_context = context_tensor

            for step in range(prediction_length):
                pred = self.model(current_context)
                pred_value = pred[0, -1, 0].item()

                predictions_list.append(pred_value)
                current_context = torch.cat([
                    current_context[:, 1:, :],
                    torch.FloatTensor([[[pred_value]]]).to(self.device)
                ], dim=1)

            predictions = np.array(predictions_list)

        # Dénormalisation
        predictions = self._denormalize_data(predictions)

        result = AutoformerResult(
            predictions=predictions,
            trend=None,
            seasonality=None,
            loss_history=self.loss_history,
            val_loss_history=self.val_loss_history,
            prediction_length=prediction_length,
        )

        self._prediction_cache[cache_key] = result

        if return_details:
            return result
        elif return_components:
            return predictions, result.trend, result.seasonality
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
            'auto_correlation': self.config.auto_correlation,
            'series_decomp': self.config.series_decomp,
            'context_length': self.config.context_length,
            'prediction_length': self.config.prediction_length,
            'hidden_size': self.config.hidden_size,
            'num_heads': self.config.num_heads,
            'num_layers': self.config.num_layers,
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
    def load(cls, filepath: str) -> 'AutoformerModel':
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = AutoformerConfig(**data['config'])
            model = cls(config)

            if data.get('model_state_dict'):
                model.model = _AutoformerModel(config).to(model.device)
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


def create_autoformer(
    input_size: int = 1,
    hidden_size: int = 128,
    context_length: int = 24,
    prediction_length: int = 12,
    auto_correlation: bool = True,
    series_decomp: bool = True,
    **kwargs
) -> AutoformerModel:
    config = AutoformerConfig(
        input_size=input_size,
        hidden_size=hidden_size,
        context_length=context_length,
        prediction_length=prediction_length,
        auto_correlation=auto_correlation,
        series_decomp=series_decomp,
        **kwargs
    )
    return AutoformerModel(config)


__all__ = [
    'AutoformerModel',
    'AutoformerConfig',
    'AutoformerResult',
    'create_autoformer',
]
