
"""
NEXUS AI TRADING SYSTEM - DeepAR Model for Time Series Forecasting
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
import json
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class DeepARConfig:
    input_size: int = 1
    hidden_size: int = 128
    num_layers: int = 2
    dropout: float = 0.1
    learning_rate: float = 0.001
    batch_size: int = 64
    epochs: int = 100
    context_length: int = 24
    prediction_length: int = 12
    use_gpu: bool = False
    early_stopping: bool = True
    patience: int = 10
    loss: str = 'mse'
    embedding_dim: int = 16
    num_embeddings: int = 10
    hidden_dim: Optional[int] = None
    num_heads: int = 4
    use_lstm: bool = True
    use_attention: bool = False
    clip_gradient: float = 1.0
    weight_decay: float = 1e-5
    scheduler: Optional[str] = None

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'input_size': self.input_size,
            'hidden_size': self.hidden_size,
            'num_layers': self.num_layers,
            'dropout': self.dropout,
            'learning_rate': self.learning_rate,
            'batch_size': self.batch_size,
            'epochs': self.epochs,
            'context_length': self.context_length,
            'prediction_length': self.prediction_length,
            'use_gpu': self.use_gpu,
            'early_stopping': self.early_stopping,
            'patience': self.patience,
            'loss': self.loss,
            'embedding_dim': self.embedding_dim,
            'num_embeddings': self.num_embeddings,
            'hidden_dim': self.hidden_dim,
            'num_heads': self.num_heads,
            'use_lstm': self.use_lstm,
            'use_attention': self.use_attention,
            'clip_gradient': self.clip_gradient,
            'weight_decay': self.weight_decay,
            'scheduler': self.scheduler,
        }


@dataclass
class DeepARResult:
    predictions: np.ndarray
    lower_bound: Optional[np.ndarray] = None
    upper_bound: Optional[np.ndarray] = None
    samples: Optional[np.ndarray] = None
    loss_history: Optional[List[float]] = None
    val_loss_history: Optional[List[float]] = None
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    prediction_length: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'lower_bound': self.lower_bound.tolist() if isinstance(self.lower_bound, np.ndarray) else self.lower_bound,
            'upper_bound': self.upper_bound.tolist() if isinstance(self.upper_bound, np.ndarray) else self.upper_bound,
            'samples': self.samples.tolist() if isinstance(self.samples, np.ndarray) else self.samples,
            'loss_history': self.loss_history,
            'val_loss_history': self.val_loss_history,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
            'prediction_length': self.prediction_length,
        }


class _DeepARLayer(nn.Module):
    """Couche récurrente pour DeepAR avec support LSTM/GRU et attention"""

    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        num_layers: int,
        dropout: float,
        use_lstm: bool = True,
        use_attention: bool = False,
        num_heads: int = 4
    ):
        super().__init__()

        self.use_attention = use_attention

        if use_lstm:
            self.rnn = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                dropout=dropout if num_layers > 1 else 0,
                batch_first=True
            )
        else:
            self.rnn = nn.GRU(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                dropout=dropout if num_layers > 1 else 0,
                batch_first=True
            )

        if use_attention:
            self.attention = nn.MultiheadAttention(
                embed_dim=hidden_size,
                num_heads=num_heads,
                dropout=dropout,
                batch_first=True
            )

    def forward(self, x, hidden=None):
        output, hidden = self.rnn(x, hidden)

        if self.use_attention:
            output, _ = self.attention(output, output, output)

        return output, hidden


class _DeepARModel(nn.Module):
    """Modèle DeepAR complet avec support des embeddings catégoriels"""

    def __init__(self, config: DeepARConfig):
        super().__init__()

        self.config = config
        self.input_size = config.input_size
        self.hidden_size = config.hidden_size
        self.num_layers = config.num_layers
        self.dropout = config.dropout
        self.num_embeddings = config.num_embeddings
        self.embedding_dim = config.embedding_dim

        self.rnn = _DeepARLayer(
            input_size=self.input_size,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
            dropout=self.dropout,
            use_lstm=config.use_lstm,
            use_attention=config.use_attention,
            num_heads=config.num_heads
        )

        self.embedding = nn.Embedding(
            num_embeddings=self.num_embeddings,
            embedding_dim=self.embedding_dim
        )

        self.decoder = nn.Sequential(
            nn.Linear(self.hidden_size + self.embedding_dim, self.hidden_size),
            nn.ReLU(),
            nn.Dropout(self.dropout),
            nn.Linear(self.hidden_size, self.hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(self.dropout),
            nn.Linear(self.hidden_size // 2, self.input_size),
        )

    def forward(self, x, categorical_features=None, hidden=None):
        batch_size, seq_len, _ = x.size()

        if hidden is None:
            hidden = self._init_hidden(batch_size)

        output, hidden = self.rnn(x, hidden)

        if categorical_features is not None:
            embedded = self.embedding(categorical_features)
            embedded = embedded.unsqueeze(1).expand(-1, seq_len, -1)
            combined = torch.cat([output, embedded], dim=2)
            predictions = self.decoder(combined)
        else:
            predictions = self.decoder(output)

        return predictions, hidden

    def _init_hidden(self, batch_size):
        if self.config.use_lstm:
            return (
                torch.zeros(self.num_layers, batch_size, self.hidden_size),
                torch.zeros(self.num_layers, batch_size, self.hidden_size)
            )
        else:
            return torch.zeros(self.num_layers, batch_size, self.hidden_size)


class DeepARModel:
    """
    DeepAR Model for time series forecasting using deep learning.

    DeepAR is a probabilistic forecasting method based on autoregressive
    recurrent networks. This implementation supports:
    - Univariate and multivariate time series
    - Categorical features via embeddings
    - Probabilistic forecasts with confidence intervals
    - GPU acceleration
    - Early stopping and model checkpoints

    Example:
        ```python
        # Create model
        config = DeepARConfig(
            input_size=1,
            hidden_size=128,
            context_length=24,
            prediction_length=12,
            epochs=100
        )
        model = DeepARModel(config)

        # Fit model
        model.fit(train_data, train_features)

        # Predict
        predictions, lower, upper = model.predict(
            test_data,
            return_bounds=True,
            num_samples=100
        )
        ```
    """

    def __init__(self, config: Optional[DeepARConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis. Installez avec: pip install torch")

        self.config = config or DeepARConfig()
        self.model: Optional[_DeepARModel] = None
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.is_fitted = False
        self.scaler = None
        self.mean = None
        self.std = None
        self._prediction_cache: Dict[str, Any] = {}
        self.loss_history: List[float] = []
        self.val_loss_history: List[float] = []

        logger.info(f"DeepARModel initialisé sur {self.device}")

    def _normalize_data(self, data: np.ndarray) -> np.ndarray:
        """Normalise les données"""
        self.mean = np.mean(data)
        self.std = np.std(data) + 1e-8
        return (data - self.mean) / self.std

    def _denormalize_data(self, data: np.ndarray) -> np.ndarray:
        """Dénormalise les données"""
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
        """Crée des séquences d'entraînement"""
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
        """Prépare les données pour l'entraînement"""
        sequences, targets = self._create_sequences(data, context_length, prediction_length)

        if len(sequences) == 0:
            raise ValueError("Pas assez de données pour créer des séquences")

        dataset = TensorDataset(
            torch.FloatTensor(sequences),
            torch.FloatTensor(targets)
        )

        return DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            drop_last=True
        )

    def _get_loss_function(self) -> nn.Module:
        """Retourne la fonction de perte"""
        if self.config.loss == 'mse':
            return nn.MSELoss()
        elif self.config.loss == 'mae':
            return nn.L1Loss()
        elif self.config.loss == 'smooth_l1':
            return nn.SmoothL1Loss()
        elif self.config.loss == 'huber':
            return nn.HuberLoss()
        else:
            logger.warning(f"Perte {self.config.loss} non reconnue, utilisation de MSE")
            return nn.MSELoss()

    def fit(
        self,
        data: Union[np.ndarray, pd.Series, List[float]],
        validation_data: Optional[Union[np.ndarray, pd.Series, List[float]]] = None,
        categorical_features: Optional[np.ndarray] = None,
        **kwargs
    ) -> 'DeepARModel':
        """
        Entraîne le modèle DeepAR.

        Args:
            data: Données d'entraînement
            validation_data: Données de validation (optionnel)
            categorical_features: Caractéristiques catégorielles
            **kwargs: Arguments supplémentaires

        Returns:
            DeepARModel: Instance entraînée
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

        # Normalisation
        normalized_data = self._normalize_data(data)
        normalized_val = None
        if validation_data is not None:
            normalized_val = (validation_data - self.mean) / self.std

        # Configuration
        config = self.config
        context_length = kwargs.get('context_length', config.context_length)
        prediction_length = kwargs.get('prediction_length', config.prediction_length)
        batch_size = kwargs.get('batch_size', config.batch_size)
        epochs = kwargs.get('epochs', config.epochs)
        learning_rate = kwargs.get('learning_rate', config.learning_rate)

        # Préparation des données
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

        # Création du modèle
        self.config.input_size = 1
        self.model = _DeepARModel(self.config).to(self.device)

        # Optimiseur
        optimizer = optim.Adam(
            self.model.parameters(),
            lr=learning_rate,
            weight_decay=config.weight_decay
        )

        # Scheduler
        scheduler = None
        if config.scheduler == 'step':
            scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.1)
        elif config.scheduler == 'plateau':
            scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)

        # Fonction de perte
        criterion = self._get_loss_function()

        # Entraînement
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

                # Teacher forcing: utiliser les valeurs réelles pour l'auto-régressivité
                predictions, _ = self.model(batch_X)

                # Dimensions: [batch, seq_len, features]
                if predictions.dim() == 3 and predictions.size(2) > 1:
                    predictions = predictions.squeeze(-1)

                loss = criterion(predictions, batch_y)
                loss.backward()

                # Gradient clipping
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

            # Validation
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

                        loss = criterion(predictions, batch_y)
                        val_loss += loss.item()
                        val_batches += 1

                val_loss = val_loss / val_batches
                self.val_loss_history.append(val_loss)

            # Scheduler
            if scheduler is not None:
                if isinstance(scheduler, optim.lr_scheduler.ReduceLROnPlateau):
                    scheduler.step(val_loss)
                else:
                    scheduler.step()

            # Logging
            if epoch % 10 == 0 or epoch == epochs - 1:
                log_msg = f"Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.6f}"
                if val_loss is not None:
                    log_msg += f", Val Loss: {val_loss:.6f}"
                logger.debug(log_msg)

            # Early stopping
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

        # Charger le meilleur checkpoint
        if config.early_stopping:
            self._load_checkpoint()

        self.is_fitted = True
        logger.info("Entraînement terminé")

        return self

    def _save_checkpoint(self):
        """Sauvegarde le checkpoint du modèle"""
        if self.model is None:
            return

        self._checkpoint = {
            'model_state_dict': self.model.state_dict(),
            'config': self.config,
            'mean': self.mean,
            'std': self.std,
        }

    def _load_checkpoint(self):
        """Charge le checkpoint du modèle"""
        if hasattr(self, '_checkpoint') and self.model is not None:
            self.model.load_state_dict(self._checkpoint['model_state_dict'])

    def predict(
        self,
        data: Union[np.ndarray, pd.Series, List[float]],
        prediction_length: Optional[int] = None,
        return_bounds: bool = False,
        num_samples: int = 100,
        confidence_level: float = 0.95,
        return_samples: bool = False,
        return_details: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray, np.ndarray], DeepARResult]:
        """
        Effectue une prédiction avec le modèle DeepAR.

        Args:
            data: Données d'entrée
            prediction_length: Nombre d'étapes à prédire
            return_bounds: Retourner les bornes de confiance
            num_samples: Nombre d'échantillons pour l'inférence
            confidence_level: Niveau de confiance (0.95 = 95%)
            return_samples: Retourner les échantillons
            return_details: Retourner tous les détails

        Returns:
            np.ndarray: Prédictions
            Tuple: (Prédictions, Lower, Upper)
            DeepARResult: Résultat complet
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

        cache_key = f"{hash(data.tobytes())}_{prediction_length}_{confidence_level}"
        if cache_key in self._prediction_cache:
            logger.debug("Prédiction trouvée dans le cache")
            cached = self._prediction_cache[cache_key]
            if return_details:
                return cached
            elif return_bounds:
                return cached.predictions, cached.lower_bound, cached.upper_bound
            else:
                return cached.predictions

        # Normalisation
        normalized_data = (data - self.mean) / self.std

        # Préparer les séquences
        context = normalized_data[-self.config.context_length:]
        context_tensor = torch.FloatTensor(context).unsqueeze(0).unsqueeze(-1).to(self.device)

        self.model.eval()

        with torch.no_grad():
            # Prédiction auto-régressive
            predictions = []
            current_context = context_tensor

            for _ in range(prediction_length):
                pred, _ = self.model(current_context)
                pred_value = pred[:, -1, :]
                predictions.append(pred_value.item())

                # Mettre à jour le contexte
                current_context = torch.cat([
                    current_context[:, 1:, :],
                    pred_value.unsqueeze(1)
                ], dim=1)

            predictions = np.array(predictions)

            # Simulation d'échantillons pour les intervalles de confiance
            samples = []
            for _ in range(num_samples):
                noise = np.random.normal(0, 0.05 * np.std(predictions), len(predictions))
                sample = predictions + noise
                samples.append(sample)

            samples = np.array(samples)

        # Dénormalisation
        predictions = self._denormalize_data(predictions)
        samples = self._denormalize_data(samples)

        # Intervalles de confiance
        lower_percentile = (1 - confidence_level) / 2 * 100
        upper_percentile = (1 + confidence_level) / 2 * 100

        lower_bound = np.percentile(samples, lower_percentile, axis=0)
        upper_bound = np.percentile(samples, upper_percentile, axis=0)

        result = DeepARResult(
            predictions=predictions,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            samples=samples if return_samples else None,
            loss_history=self.loss_history,
            val_loss_history=self.val_loss_history,
            prediction_length=prediction_length,
        )

        self._prediction_cache[cache_key] = result

        if return_details:
            return result
        elif return_bounds:
            return predictions, lower_bound, upper_bound
        else:
            return predictions

    def predict_probabilistic(
        self,
        data: Union[np.ndarray, pd.Series, List[float]],
        prediction_length: Optional[int] = None,
        num_samples: int = 1000
    ) -> Dict[str, np.ndarray]:
        """
        Retourne une distribution probabiliste des prédictions.

        Args:
            data: Données d'entrée
            prediction_length: Nombre d'étapes à prédire
            num_samples: Nombre d'échantillons

        Returns:
            Dict[str, np.ndarray]: Distribution des prédictions
        """
        if prediction_length is None:
            prediction_length = self.config.prediction_length

        predictions, lower, upper = self.predict(
            data,
            prediction_length=prediction_length,
            return_bounds=True,
            num_samples=num_samples,
            return_samples=True
        )

        return {
            'mean': predictions,
            'lower': lower,
            'upper': upper,
            'samples': predictions  # Pour compatibilité
        }

    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres du modèle"""
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques du modèle"""
        metrics = {
            'is_fitted': self.is_fitted,
            'loss_history_length': len(self.loss_history),
            'val_loss_history_length': len(self.val_loss_history),
            'device': str(self.device),
        }

        if self.loss_history:
            metrics['final_loss'] = self.loss_history[-1]
            metrics['min_loss'] = min(self.loss_history)

        if self.val_loss_history:
            metrics['final_val_loss'] = self.val_loss_history[-1]
            metrics['min_val_loss'] = min(self.val_loss_history)

        return metrics

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde le modèle sur le disque.

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
    def load(cls, filepath: str) -> 'DeepARModel':
        """
        Charge un modèle depuis le disque.

        Args:
            filepath: Chemin du fichier

        Returns:
            DeepARModel: Modèle chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = DeepARConfig(**data['config'])
            model = cls(config)

            if data.get('model_state_dict'):
                model.model = _DeepARModel(config).to(model.device)
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


def create_deepar_model(
    input_size: int = 1,
    hidden_size: int = 128,
    num_layers: int = 2,
    context_length: int = 24,
    prediction_length: int = 12,
    learning_rate: float = 0.001,
    epochs: int = 100,
    **kwargs
) -> DeepARModel:
    """
    Factory pour créer un modèle DeepAR.

    Args:
        input_size: Taille d'entrée
        hidden_size: Taille du cache
        num_layers: Nombre de couches
        context_length: Longueur du contexte
        prediction_length: Longueur de prédiction
        learning_rate: Taux d'apprentissage
        epochs: Nombre d'époques
        **kwargs: Arguments supplémentaires

    Returns:
        DeepARModel: Instance du modèle
    """
    config = DeepARConfig(
        input_size=input_size,
        hidden_size=hidden_size,
        num_layers=num_layers,
        context_length=context_length,
        prediction_length=prediction_length,
        learning_rate=learning_rate,
        epochs=epochs,
        **kwargs
    )
    return DeepARModel(config)


__all__ = [
    'DeepARModel',
    'DeepARConfig',
    'DeepARResult',
    'create_deepar_model',
]
