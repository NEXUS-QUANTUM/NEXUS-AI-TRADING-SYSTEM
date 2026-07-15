
# ai/models/volatility/stochastic_volatility.py
"""
NEXUS AI TRADING SYSTEM - Stochastic Volatility Models
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
    from torch.distributions import Normal, Laplace, StudentT
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from scipy import stats
    from scipy.optimize import minimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class StochasticVolatilityConfig:
    hidden_size: int = 64
    num_layers: int = 1
    dropout: float = 0.1
    learning_rate: float = 0.001
    batch_size: int = 64
    epochs: int = 100
    use_gpu: bool = False
    early_stopping: bool = True
    patience: int = 10
    clip_gradient: float = 1.0
    weight_decay: float = 1e-5
    distribution: str = 'normal'
    use_volatility_scale: bool = True
    use_leverage: bool = False
    prior_mean: float = 0.0
    prior_std: float = 1.0
    volatility_prior_mean: float = -1.0
    volatility_prior_std: float = 0.5

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        if self.distribution not in ['normal', 'laplace', 'student_t']:
            raise ValueError(f"Distribution non supportée: {self.distribution}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'hidden_size': self.hidden_size,
            'num_layers': self.num_layers,
            'dropout': self.dropout,
            'learning_rate': self.learning_rate,
            'batch_size': self.batch_size,
            'epochs': self.epochs,
            'use_gpu': self.use_gpu,
            'early_stopping': self.early_stopping,
            'patience': self.patience,
            'clip_gradient': self.clip_gradient,
            'weight_decay': self.weight_decay,
            'distribution': self.distribution,
            'use_volatility_scale': self.use_volatility_scale,
            'use_leverage': self.use_leverage,
            'prior_mean': self.prior_mean,
            'prior_std': self.prior_std,
            'volatility_prior_mean': self.volatility_prior_mean,
            'volatility_prior_std': self.volatility_prior_std,
        }


@dataclass
class StochasticVolatilityResult:
    volatility: np.ndarray
    latent_volatility: np.ndarray
    predictions: Optional[np.ndarray] = None
    losses: Optional[List[float]] = None
    val_losses: Optional[List[float]] = None
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    forecast_steps: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'volatility': self.volatility.tolist() if isinstance(self.volatility, np.ndarray) else self.volatility,
            'latent_volatility': self.latent_volatility.tolist() if isinstance(self.latent_volatility, np.ndarray) else self.latent_volatility,
            'predictions': self.predictions.tolist() if isinstance(self.predictions, np.ndarray) else self.predictions,
            'losses': self.losses,
            'val_losses': self.val_losses,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
            'forecast_steps': self.forecast_steps,
        }


class _StochasticVolatilityLSTM(nn.Module):
    """Modèle LSTM pour volatilité stochastique"""

    def __init__(self, config: StochasticVolatilityConfig):
        super().__init__()

        self.config = config
        self.hidden_size = config.hidden_size
        self.num_layers = config.num_layers
        self.use_leverage = config.use_leverage
        self.use_volatility_scale = config.use_volatility_scale

        # LSTM pour la volatilité latente
        self.lstm = nn.LSTM(
            input_size=1 + (1 if config.use_leverage else 0),
            hidden_size=config.hidden_size,
            num_layers=config.num_layers,
            dropout=config.dropout if config.num_layers > 1 else 0,
            batch_first=True
        )

        # Projection pour la volatilité
        self.volatility_proj = nn.Sequential(
            nn.Linear(config.hidden_size, config.hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_size // 2, 1)
        )

        # Projection pour l'échelle (optionnel)
        if config.use_volatility_scale:
            self.scale_proj = nn.Sequential(
                nn.Linear(config.hidden_size, config.hidden_size // 2),
                nn.ReLU(),
                nn.Dropout(config.dropout),
                nn.Linear(config.hidden_size // 2, 1),
                nn.Softplus()
            )

    def forward(self, x, returns=None, hidden=None):
        # Construire l'entrée
        if self.use_leverage and returns is not None:
            leverage = returns.unsqueeze(-1)
            x = torch.cat([x, leverage], dim=-1)

        # LSTM
        output, hidden = self.lstm(x, hidden)

        # Volatilité latente
        latent_vol = self.volatility_proj(output)

        # Échelle (optionnel)
        if self.use_volatility_scale:
            scale = self.scale_proj(output)
            latent_vol = latent_vol * scale

        return latent_vol, hidden


class StochasticVolatility:
    """
    Stochastic Volatility model using deep learning.

    This implementation uses LSTM networks to model latent volatility
    dynamics with support for multiple return distributions.

    Features:
    - LSTM-based latent volatility estimation
    - Support for Normal, Laplace, and Student-t distributions
    - Leverage effect modeling
    - Volatility scaling
    - GPU acceleration
    - Early stopping
    - Model checkpointing

    Example:
        ```python
        config = StochasticVolatilityConfig(
            hidden_size=64,
            distribution='normal',
            use_leverage=True,
            epochs=100
        )
        model = StochasticVolatility(config)

        # Fit model
        model.fit(returns)

        # Predict volatility
        vol, latent = model.predict(steps=10)
        ```
    """

    def __init__(self, config: Optional[StochasticVolatilityConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis. Installez avec: pip install torch")

        self.config = config or StochasticVolatilityConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.model: Optional[_StochasticVolatilityLSTM] = None
        self.is_fitted = False
        self.data: Optional[np.ndarray] = None
        self._prediction_cache: Dict[str, Any] = {}
        self.losses: List[float] = []
        self.val_losses: List[float] = []
        self.scaler = None
        self.mean = None
        self.std = None

        logger.info(f"StochasticVolatility initialisé sur {self.device}")

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

    def _prepare_data(
        self,
        data: np.ndarray,
        sequence_length: int,
        batch_size: int,
        shuffle: bool = True
    ) -> torch.utils.data.DataLoader:
        """Prépare les données pour l'entraînement"""
        sequences = []
        targets = []

        for i in range(sequence_length, len(data)):
            seq = data[i - sequence_length:i]
            target = data[i]
            sequences.append(seq)
            targets.append(target)

        if len(sequences) == 0:
            raise ValueError("Pas assez de données pour créer des séquences")

        dataset = torch.utils.data.TensorDataset(
            torch.FloatTensor(np.array(sequences)).unsqueeze(-1),
            torch.FloatTensor(np.array(targets))
        )

        return torch.utils.data.DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            drop_last=True
        )

    def _get_distribution(self):
        """Retourne la distribution pour les rendements"""
        if self.config.distribution == 'normal':
            return Normal
        elif self.config.distribution == 'laplace':
            return Laplace
        elif self.config.distribution == 'student_t':
            return StudentT
        else:
            return Normal

    def _compute_loss(
        self,
        returns: torch.Tensor,
        latent_vol: torch.Tensor,
        scale: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """Calcule la perte négative de vraisemblance"""
        if self.config.distribution == 'student_t':
            df = torch.ones(1, device=returns.device) * 3
            dist = StudentT(df, loc=0, scale=torch.exp(latent_vol))
        else:
            scale_val = scale if scale is not None else torch.exp(latent_vol)
            if self.config.distribution == 'normal':
                dist = Normal(0, scale_val)
            elif self.config.distribution == 'laplace':
                dist = Laplace(0, scale_val)
            else:
                dist = Normal(0, scale_val)

        # Log-likelihood
        log_prob = dist.log_prob(returns)

        # Prior sur la volatilité
        prior = Normal(
            self.config.volatility_prior_mean,
            self.config.volatility_prior_std
        )
        log_prior = prior.log_prob(latent_vol)

        # Perte négative
        loss = -(log_prob + log_prior).mean()

        return loss

    def fit(
        self,
        data: Union[np.ndarray, pd.Series, List[float]],
        validation_data: Optional[Union[np.ndarray, pd.Series, List[float]]] = None,
        **kwargs
    ) -> 'StochasticVolatility':
        """
        Entraîne le modèle de volatilité stochastique.

        Args:
            data: Données de rendements
            validation_data: Données de validation (optionnel)
            **kwargs: Arguments supplémentaires

        Returns:
            StochasticVolatility: Instance entraînée
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

        self.data = data

        # Normalisation
        normalized_data = self._normalize_data(data)
        normalized_val = None
        if validation_data is not None:
            normalized_val = self._normalize_data(validation_data)

        config = self.config
        sequence_length = kwargs.get('sequence_length', 20)
        batch_size = kwargs.get('batch_size', config.batch_size)
        epochs = kwargs.get('epochs', config.epochs)
        learning_rate = kwargs.get('learning_rate', config.learning_rate)

        # Préparation des données
        train_loader = self._prepare_data(
            normalized_data,
            sequence_length,
            batch_size,
            shuffle=True
        )

        val_loader = None
        if normalized_val is not None:
            val_loader = self._prepare_data(
                normalized_val,
                sequence_length,
                batch_size,
                shuffle=False
            )

        # Création du modèle
        self.model = _StochasticVolatilityLSTM(config).to(self.device)

        optimizer = optim.Adam(
            self.model.parameters(),
            lr=learning_rate,
            weight_decay=config.weight_decay
        )

        scheduler = None
        if config.scheduler:
            scheduler = optim.lr_scheduler.ReduceLROnPlateau(
                optimizer, patience=5, factor=0.5
            )

        self.losses = []
        self.val_losses = []
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

                # Prédiction de la volatilité
                latent_vol, _ = self.model(batch_X, batch_y)

                # Calcul de la perte
                loss = self._compute_loss(batch_y, latent_vol)
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
            self.losses.append(avg_loss)

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

                        latent_vol, _ = self.model(batch_X, batch_y)
                        loss = self._compute_loss(batch_y, latent_vol)

                        val_loss += loss.item()
                        val_batches += 1

                val_loss = val_loss / val_batches
                self.val_losses.append(val_loss)

                if scheduler is not None:
                    scheduler.step(val_loss)

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
        data: Optional[Union[np.ndarray, pd.Series, List[float]]] = None,
        steps: int = 1,
        return_details: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, np.ndarray], StochasticVolatilityResult]:
        """
        Prédit la volatilité future.

        Args:
            data: Données de rendements (optionnel)
            steps: Nombre d'étapes à prédire
            return_details: Retourner tous les détails

        Returns:
            np.ndarray: Volatilité prédite
            Tuple: (Volatilité, Volatilité latente)
            StochasticVolatilityResult: Résultat complet
        """
        if not self.is_fitted:
            raise ValueError("Le modèle doit être entraîné avant de prédire")

        if data is None:
            data = self.data

        if isinstance(data, pd.Series):
            data = data.values
        elif isinstance(data, list):
            data = np.array(data)

        if len(data) < 20:
            raise ValueError("Pas assez de données pour la prédiction")

        normalized_data = self._normalize_data(data)

        # Dernière séquence
        sequence = normalized_data[-20:]
        sequence_tensor = torch.FloatTensor(sequence).unsqueeze(0).unsqueeze(-1).to(self.device)

        self.model.eval()

        latent_vols = []
        with torch.no_grad():
            current_seq = sequence_tensor
            hidden = None

            for _ in range(steps):
                latent_vol, hidden = self.model(current_seq, None, hidden)
                latent_vols.append(latent_vol.squeeze().item())

                # Mise à jour de la séquence
                # Simuler un rendement (moyenne 0)
                simulated_return = torch.zeros(1, 1, 1).to(self.device)
                current_seq = torch.cat([
                    current_seq[:, 1:, :],
                    simulated_return
                ], dim=1)

            latent_vols = np.array(latent_vols)

        # Volatilité
        volatility = np.exp(latent_vols)

        # Dénormalisation
        volatility = self._denormalize_data(volatility)

        result = StochasticVolatilityResult(
            volatility=volatility,
            latent_volatility=latent_vols,
            losses=self.losses,
            val_losses=self.val_losses,
            forecast_steps=steps,
        )

        if return_details:
            return result
        else:
            return volatility

    def get_params(self) -> Dict[str, Any]:
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        metrics = {
            'is_fitted': self.is_fitted,
            'losses_length': len(self.losses),
            'val_losses_length': len(self.val_losses),
            'device': str(self.device),
            'distribution': self.config.distribution,
            'use_leverage': self.config.use_leverage,
        }

        if self.losses:
            metrics['final_loss'] = self.losses[-1]
            metrics['min_loss'] = min(self.losses)

        if self.val_losses:
            metrics['final_val_loss'] = self.val_losses[-1]
            metrics['min_val_loss'] = min(self.val_losses)

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
                'losses': self.losses,
                'val_losses': self.val_losses,
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
    def load(cls, filepath: str) -> 'StochasticVolatility':
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = StochasticVolatilityConfig(**data['config'])
            model = cls(config)

            if data.get('model_state_dict'):
                model.model = _StochasticVolatilityLSTM(config).to(model.device)
                model.model.load_state_dict(data['model_state_dict'])

            model.mean = data.get('mean')
            model.std = data.get('std')
            model.is_fitted = data.get('is_fitted', False)
            model.losses = data.get('losses', [])
            model.val_losses = data.get('val_losses', [])

            logger.info(f"Modèle chargé: {filepath}")
            return model

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise


def create_stochastic_volatility(
    hidden_size: int = 64,
    distribution: str = 'normal',
    use_leverage: bool = False,
    **kwargs
) -> StochasticVolatility:
    config = StochasticVolatilityConfig(
        hidden_size=hidden_size,
        distribution=distribution,
        use_leverage=use_leverage,
        **kwargs
    )
    return StochasticVolatility(config)


__all__ = [
    'StochasticVolatility',
    'StochasticVolatilityConfig',
    'StochasticVolatilityResult',
    'create_stochastic_volatility',
]
