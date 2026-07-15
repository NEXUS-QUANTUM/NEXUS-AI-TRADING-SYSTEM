# ai/neural/embeddings/time_embedding.py
"""
NEXUS AI TRADING SYSTEM - Time Embedding Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class TimeEmbeddingConfig:
    """Configuration pour Time Embedding"""
    embed_dim: int = 64
    num_features: int = 7  # heure, jour, mois, etc.
    include_cyclical: bool = True
    include_weekday: bool = True
    include_month: bool = True
    include_hour: bool = True
    include_minute: bool = True
    include_day_of_year: bool = False
    include_quarter: bool = False
    include_year: bool = False
    normalize: bool = True
    use_positional: bool = False
    max_length: int = 1000

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'embed_dim': self.embed_dim,
            'num_features': self.num_features,
            'include_cyclical': self.include_cyclical,
            'include_weekday': self.include_weekday,
            'include_month': self.include_month,
            'include_hour': self.include_hour,
            'include_minute': self.include_minute,
            'include_day_of_year': self.include_day_of_year,
            'include_quarter': self.include_quarter,
            'include_year': self.include_year,
            'normalize': self.normalize,
            'use_positional': self.use_positional,
            'max_length': self.max_length,
        }


class _TimeFeatures(nn.Module):
    """Extraction des caractéristiques temporelles"""

    def __init__(self, config: TimeEmbeddingConfig):
        super().__init__()

        self.config = config
        self.normalize = config.normalize

        # Dimensions par feature
        self.feature_dims = {
            'hour': 24 if config.include_hour else 0,
            'minute': 60 if config.include_minute else 0,
            'weekday': 7 if config.include_weekday else 0,
            'month': 12 if config.include_month else 0,
            'day_of_year': 366 if config.include_day_of_year else 0,
            'quarter': 4 if config.include_quarter else 0,
            'year': 1 if config.include_year else 0,
        }

        # Compter le nombre total de features
        self.total_features = sum(1 for v in self.feature_dims.values() if v > 0)
        if config.include_cyclical:
            self.total_features *= 2

        # Projection pour la dimension finale
        if self.total_features > 0:
            self.projection = nn.Linear(self.total_features, config.embed_dim)
        else:
            self.projection = nn.Identity()

    def _cyclical_encoding(self, values: torch.Tensor, max_val: float) -> torch.Tensor:
        """Encodage cyclique (sin/cos)"""
        if self.config.normalize:
            values = values / max_val
        sin = torch.sin(2 * np.pi * values)
        cos = torch.cos(2 * np.pi * values)
        return torch.cat([sin, cos], dim=-1)

    def _extract_features_from_timestamps(
        self,
        timestamps: torch.Tensor
    ) -> torch.Tensor:
        """
        Extrait les caractéristiques temporelles des timestamps.

        Args:
            timestamps: Timestamps en secondes [batch_size, seq_len]

        Returns:
            torch.Tensor: Features temporelles
        """
        batch_size, seq_len = timestamps.shape
        features = []

        # Convertir en datetime
        # Pour les timestamps en secondes
        if torch.max(timestamps) > 1e10:  # millisecondes
            timestamps_sec = timestamps / 1000
        else:
            timestamps_sec = timestamps

        # Calculer les composantes temporelles
        # Note: Ces calculs sont simplifiés pour la version tensorielle
        # Pour une version complète, utiliser les datetime Python

        if self.config.include_hour:
            hour = (timestamps_sec % 86400) / 3600
            if self.config.include_cyclical:
                hour_enc = self._cyclical_encoding(hour, 24)
                features.append(hour_enc)
            else:
                features.append(hour.unsqueeze(-1))

        if self.config.include_minute:
            minute = (timestamps_sec % 3600) / 60
            if self.config.include_cyclical:
                minute_enc = self._cyclical_encoding(minute, 60)
                features.append(minute_enc)
            else:
                features.append(minute.unsqueeze(-1))

        if self.config.include_weekday:
            # Jour de la semaine (0-6)
            weekday = (timestamps_sec / 86400 + 4) % 7
            if self.config.include_cyclical:
                weekday_enc = self._cyclical_encoding(weekday, 7)
                features.append(weekday_enc)
            else:
                features.append(weekday.unsqueeze(-1))

        if self.config.include_month:
            # Mois (1-12)
            month = ((timestamps_sec / 86400) % 365) / 30.44
            month = month % 12 + 1
            if self.config.include_cyclical:
                month_enc = self._cyclical_encoding(month, 12)
                features.append(month_enc)
            else:
                features.append(month.unsqueeze(-1))

        if self.config.include_day_of_year:
            day_of_year = (timestamps_sec / 86400) % 365
            if self.config.include_cyclical:
                day_enc = self._cyclical_encoding(day_of_year, 366)
                features.append(day_enc)
            else:
                features.append(day_of_year.unsqueeze(-1))

        if self.config.include_quarter:
            quarter = ((timestamps_sec / 86400) % 365) / 91.25
            quarter = quarter % 4 + 1
            if self.config.include_cyclical:
                quarter_enc = self._cyclical_encoding(quarter, 4)
                features.append(quarter_enc)
            else:
                features.append(quarter.unsqueeze(-1))

        if self.config.include_year:
            year = timestamps_sec / (86400 * 365.25) + 1970
            if self.config.normalize:
                year = (year - 1970) / 100
            features.append(year.unsqueeze(-1))

        if features:
            return torch.cat(features, dim=-1)
        else:
            return torch.zeros(batch_size, seq_len, 0, device=timestamps.device)

    def forward(
        self,
        timestamps: Union[torch.Tensor, List[datetime], np.ndarray, pd.DatetimeIndex]
    ) -> torch.Tensor:
        """
        Extrait et projette les caractéristiques temporelles.

        Args:
            timestamps: Timestamps ou datetimes

        Returns:
            torch.Tensor: Embeddings temporels [batch_size, seq_len, embed_dim]
        """
        # Convertir en tensor
        if isinstance(timestamps, (list, np.ndarray)):
            if isinstance(timestamps[0], datetime):
                timestamps = torch.tensor([int(t.timestamp()) for t in timestamps])
            else:
                timestamps = torch.tensor(timestamps)

        if isinstance(timestamps, pd.DatetimeIndex):
            timestamps = torch.tensor(timestamps.astype('int64') // 10**9)

        if not isinstance(timestamps, torch.Tensor):
            timestamps = torch.tensor(timestamps)

        # S'assurer que c'est un tensor 2D
        if timestamps.dim() == 1:
            timestamps = timestamps.unsqueeze(0)

        features = self._extract_features_from_timestamps(timestamps)
        embeddings = self.projection(features)

        return embeddings


class TimeEmbedding(nn.Module):
    """
    Time Embedding module for time series.

    Converts timestamps into dense embeddings that capture
    temporal patterns and periodicities.

    Features:
    - Multiple temporal features (hour, day, month, etc.)
    - Cyclical encoding (sin/cos)
    - Learnable projections
    - Batch processing
    - Support for various timestamp formats

    Example:
        ```python
        config = TimeEmbeddingConfig(
            embed_dim=64,
            include_cyclical=True,
            include_weekday=True,
            include_hour=True
        )
        time_emb = TimeEmbedding(config)

        # Create embeddings from timestamps
        timestamps = [datetime.now() + timedelta(hours=i) for i in range(24)]
        embeddings = time_emb(timestamps)
        ```
    """

    def __init__(self, config: Optional[TimeEmbeddingConfig] = None):
        super().__init__()

        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or TimeEmbeddingConfig()
        self.embed_dim = self.config.embed_dim

        # Time features extractor
        self.time_features = _TimeFeatures(self.config)

        # Positional encoding (optionnel)
        if self.config.use_positional:
            from ai.neural.embeddings.positional_encoding import PositionalEncoding, PositionalEncodingConfig

            self.positional = PositionalEncoding(
                PositionalEncodingConfig(
                    embed_dim=self.embed_dim,
                    max_length=self.config.max_length,
                    encoding_type='sinusoidal'
                )
            )
        else:
            self.positional = None

        # Layer norm
        self.layer_norm = nn.LayerNorm(self.embed_dim)

    def forward(
        self,
        timestamps: Union[torch.Tensor, List[datetime], np.ndarray, pd.DatetimeIndex]
    ) -> torch.Tensor:
        """
        Crée des embeddings temporels.

        Args:
            timestamps: Timestamps ou datetimes

        Returns:
            torch.Tensor: Embeddings temporels
        """
        embeddings = self.time_features(timestamps)

        # Positional encoding (si activé)
        if self.positional is not None:
            embeddings = self.positional(embeddings)

        # Layer norm
        embeddings = self.layer_norm(embeddings)

        return embeddings

    def get_time_features(
        self,
        timestamps: Union[torch.Tensor, List[datetime], np.ndarray, pd.DatetimeIndex]
    ) -> torch.Tensor:
        """
        Extrait les caractéristiques temporelles brutes.

        Args:
            timestamps: Timestamps ou datetimes

        Returns:
            torch.Tensor: Caractéristiques temporelles
        """
        return self.time_features(timestamps)


class PeriodicTimeEmbedding(TimeEmbedding):
    """
    Time Embedding spécialisé pour les périodicités.

    Utilise des fonctions périodiques (sin/cos) pour capturer
    les patterns cycliques dans les données temporelles.
    """

    def __init__(self, config: Optional[TimeEmbeddingConfig] = None):
        super().__init__(config)

        # S'assurer que l'encodage cyclique est activé
        self.config.include_cyclical = True

        # Fréquences pour différentes périodes
        self.frequencies = {
            'hour': 24,
            'day': 7,
            'week': 52,
            'month': 12,
            'year': 1,
        }

        # Périodes à inclure
        self.periods = {
            'hour': self.config.include_hour,
            'day': self.config.include_weekday,
            'week': False,
            'month': self.config.include_month,
            'year': self.config.include_year,
        }

    def _cyclical_encoding_with_freq(
        self,
        values: torch.Tensor,
        period: float,
        freq: Optional[float] = None
    ) -> torch.Tensor:
        """Encodage cyclique avec fréquence spécifique"""
        if freq is not None:
            values = values * freq
        return self._cyclical_encoding(values, period)


class AdaptiveTimeEmbedding(nn.Module):
    """
    Time Embedding adaptatif avec apprentissage des poids.

    Permet d'apprendre l'importance relative des différentes
    caractéristiques temporelles.
    """

    def __init__(self, config: TimeEmbeddingConfig):
        super().__init__()

        self.config = config
        self.embed_dim = config.embed_dim

        # Time features
        self.time_features = _TimeFeatures(config)

        # Poids appris par feature
        feature_dim = self.time_features.total_features
        if feature_dim > 0:
            self.feature_weights = nn.Parameter(torch.ones(feature_dim))

        # Projection adaptative
        self.projection = nn.Linear(feature_dim, embed_dim)

        self.layer_norm = nn.LayerNorm(embed_dim)

    def forward(
        self,
        timestamps: Union[torch.Tensor, List[datetime], np.ndarray, pd.DatetimeIndex]
    ) -> torch.Tensor:
        features = self.time_features(timestamps)

        # Appliquer les poids appris
        if hasattr(self, 'feature_weights'):
            features = features * F.softmax(self.feature_weights, dim=0)

        embeddings = self.projection(features)
        embeddings = self.layer_norm(embeddings)

        return embeddings


def create_time_embedding(
    embed_dim: int = 64,
    include_cyclical: bool = True,
    include_weekday: bool = True,
    include_hour: bool = True,
    **kwargs
) -> TimeEmbedding:
    """
    Factory pour créer des Time Embeddings.

    Args:
        embed_dim: Dimension d'embedding
        include_cyclical: Utiliser l'encodage cyclique
        include_weekday: Inclure le jour de la semaine
        include_hour: Inclure l'heure
        **kwargs: Arguments supplémentaires

    Returns:
        TimeEmbedding: Instance de TimeEmbedding
    """
    config = TimeEmbeddingConfig(
        embed_dim=embed_dim,
        include_cyclical=include_cyclical,
        include_weekday=include_weekday,
        include_hour=include_hour,
        **kwargs
    )
    return TimeEmbedding(config)


__all__ = [
    'TimeEmbedding',
    'TimeEmbeddingConfig',
    'PeriodicTimeEmbedding',
    'AdaptiveTimeEmbedding',
    'create_time_embedding',
]
