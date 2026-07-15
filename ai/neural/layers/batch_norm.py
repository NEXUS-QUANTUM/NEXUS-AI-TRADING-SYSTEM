# ai/neural/layers/batch_norm.py
"""
NEXUS AI TRADING SYSTEM - Batch Normalization Module
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
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
class BatchNormConfig:
    """Configuration pour Batch Normalization"""
    num_features: int
    eps: float = 1e-5
    momentum: float = 0.1
    affine: bool = True
    track_running_stats: bool = True
    dim: int = 1  # 1D, 2D, 3D

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        if self.dim not in [1, 2, 3]:
            raise ValueError("dim doit être 1, 2 ou 3")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'num_features': self.num_features,
            'eps': self.eps,
            'momentum': self.momentum,
            'affine': self.affine,
            'track_running_stats': self.track_running_stats,
            'dim': self.dim,
        }


class BatchNormFactory:
    """
    Factory pour créer des Batch Normalization layers.

    Supporte:
    - BatchNorm1d (séquences)
    - BatchNorm2d (images)
    - BatchNorm3d (volumes)
    - Custom configurations
    """

    @staticmethod
    def create(config: Union[BatchNormConfig, int, Dict[str, Any]]) -> nn.Module:
        """
        Crée une couche de Batch Normalization.

        Args:
            config: Configuration ou nombre de features

        Returns:
            nn.Module: Couche BatchNorm
        """
        if isinstance(config, int):
            config = BatchNormConfig(num_features=config)

        elif isinstance(config, dict):
            config = BatchNormConfig(**config)

        if not isinstance(config, BatchNormConfig):
            raise TypeError("config doit être BatchNormConfig, int ou dict")

        if config.dim == 1:
            return nn.BatchNorm1d(
                num_features=config.num_features,
                eps=config.eps,
                momentum=config.momentum,
                affine=config.affine,
                track_running_stats=config.track_running_stats,
            )
        elif config.dim == 2:
            return nn.BatchNorm2d(
                num_features=config.num_features,
                eps=config.eps,
                momentum=config.momentum,
                affine=config.affine,
                track_running_stats=config.track_running_stats,
            )
        elif config.dim == 3:
            return nn.BatchNorm3d(
                num_features=config.num_features,
                eps=config.eps,
                momentum=config.momentum,
                affine=config.affine,
                track_running_stats=config.track_running_stats,
            )
        else:
            raise ValueError(f"dim non supporté: {config.dim}")


class AdaptiveBatchNorm(nn.Module):
    """
    Batch Normalization adaptative avec normalisation par canal.

    Permet une normalisation adaptative pour les données financières
    où les statistiques peuvent varier entre les canaux.
    """

    def __init__(
        self,
        num_features: int,
        eps: float = 1e-5,
        momentum: float = 0.1,
        affine: bool = True,
        adaptive_scale: bool = True,
    ):
        super().__init__()

        self.num_features = num_features
        self.eps = eps
        self.momentum = momentum
        self.affine = affine
        self.adaptive_scale = adaptive_scale

        if affine:
            self.weight = nn.Parameter(torch.ones(num_features))
            self.bias = nn.Parameter(torch.zeros(num_features))
        else:
            self.register_parameter('weight', None)
            self.register_parameter('bias', None)

        if adaptive_scale:
            self.scale = nn.Parameter(torch.ones(num_features))

        self.register_buffer('running_mean', torch.zeros(num_features))
        self.register_buffer('running_var', torch.ones(num_features))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass de BatchNorm adaptative.

        Args:
            x: Tensor d'entrée [batch_size, num_features, ...]

        Returns:
            torch.Tensor: Tensor normalisé
        """
        if self.training:
            # Calcul des statistiques du batch
            batch_mean = x.mean(dim=0, keepdim=True)
            batch_var = x.var(dim=0, keepdim=True, unbiased=False)

            # Mise à jour des statistiques running
            self.running_mean = (1 - self.momentum) * self.running_mean + self.momentum * batch_mean.squeeze()
            self.running_var = (1 - self.momentum) * self.running_var + self.momentum * batch_var.squeeze()

            # Normalisation
            x_norm = (x - batch_mean) / torch.sqrt(batch_var + self.eps)
        else:
            # Utilisation des statistiques running
            x_norm = (x - self.running_mean.unsqueeze(0)) / torch.sqrt(self.running_var.unsqueeze(0) + self.eps)

        # Affine transformation
        if self.affine:
            if self.adaptive_scale:
                x_norm = x_norm * self.weight * self.scale + self.bias
            else:
                x_norm = x_norm * self.weight + self.bias

        return x_norm


class LayerNorm(nn.Module):
    """
    Layer Normalization alternative à BatchNorm pour séries temporelles.

    LayerNorm normalise les activations d'une seule couche,
    indépendamment de la taille du batch.
    """

    def __init__(
        self,
        normalized_shape: Union[int, List[int], Tuple[int, ...]],
        eps: float = 1e-5,
        elementwise_affine: bool = True,
    ):
        super().__init__()

        self.normalized_shape = normalized_shape
        self.eps = eps
        self.elementwise_affine = elementwise_affine

        if elementwise_affine:
            self.weight = nn.Parameter(torch.ones(normalized_shape))
            self.bias = nn.Parameter(torch.zeros(normalized_shape))
        else:
            self.register_parameter('weight', None)
            self.register_parameter('bias', None)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass de LayerNorm.

        Args:
            x: Tensor d'entrée

        Returns:
            torch.Tensor: Tensor normalisé
        """
        # Calcul des statistiques
        mean = x.mean(dim=-1, keepdim=True)
        var = x.var(dim=-1, keepdim=True, unbiased=False)

        # Normalisation
        x_norm = (x - mean) / torch.sqrt(var + self.eps)

        # Affine transformation
        if self.elementwise_affine:
            x_norm = x_norm * self.weight + self.bias

        return x_norm


class InstanceNorm(nn.Module):
    """
    Instance Normalization.

    Normalise chaque instance (sample) indépendamment.
    Utile pour les données où chaque instance a sa propre distribution.
    """

    def __init__(
        self,
        num_features: int,
        eps: float = 1e-5,
        momentum: float = 0.1,
        affine: bool = True,
        track_running_stats: bool = False,
    ):
        super().__init__()

        self.num_features = num_features
        self.eps = eps
        self.momentum = momentum
        self.affine = affine
        self.track_running_stats = track_running_stats

        if affine:
            self.weight = nn.Parameter(torch.ones(num_features))
            self.bias = nn.Parameter(torch.zeros(num_features))
        else:
            self.register_parameter('weight', None)
            self.register_parameter('bias', None)

        if track_running_stats:
            self.register_buffer('running_mean', torch.zeros(num_features))
            self.register_buffer('running_var', torch.ones(num_features))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass de InstanceNorm.

        Args:
            x: Tensor d'entrée

        Returns:
            torch.Tensor: Tensor normalisé
        """
        if self.training or not self.track_running_stats:
            # Calcul des statistiques par instance
            mean = x.mean(dim=(2, 3), keepdim=True)
            var = x.var(dim=(2, 3), keepdim=True, unbiased=False)

            if self.track_running_stats:
                # Mise à jour des statistiques running
                batch_mean = mean.mean(dim=0).squeeze()
                batch_var = var.mean(dim=0).squeeze()
                self.running_mean = (1 - self.momentum) * self.running_mean + self.momentum * batch_mean
                self.running_var = (1 - self.momentum) * self.running_var + self.momentum * batch_var
        else:
            # Utilisation des statistiques running
            mean = self.running_mean.view(1, -1, 1, 1)
            var = self.running_var.view(1, -1, 1, 1)

        x_norm = (x - mean) / torch.sqrt(var + self.eps)

        if self.affine:
            weight = self.weight.view(1, -1, 1, 1)
            bias = self.bias.view(1, -1, 1, 1)
            x_norm = x_norm * weight + bias

        return x_norm


class WeightNorm(nn.Module):
    """
    Weight Normalization.

    Normalise les poids des couches pour améliorer la convergence.
    """

    def __init__(self, weight: torch.Tensor, dim: int = 0, eps: float = 1e-5):
        super().__init__()

        self.dim = dim
        self.eps = eps

        # Paramètres de poids normalisé
        self.weight_g = nn.Parameter(torch.ones(weight.size(dim)))
        self.weight_v = nn.Parameter(weight)

    def forward(self) -> torch.Tensor:
        """
        Retourne les poids normalisés.

        Returns:
            torch.Tensor: Poids normalisés
        """
        # Normalisation
        norm = torch.norm(self.weight_v, dim=self.dim, keepdim=True) + self.eps
        weight = self.weight_g * (self.weight_v / norm)

        return weight


def create_batch_norm(
    num_features: int,
    dim: int = 1,
    eps: float = 1e-5,
    momentum: float = 0.1,
    affine: bool = True,
    track_running_stats: bool = True,
    **kwargs
) -> nn.Module:
    """
    Factory pour créer des Batch Normalization layers.

    Args:
        num_features: Nombre de features
        dim: Dimension (1, 2, 3)
        eps: Epsilon pour la stabilité
        momentum: Momentum pour les statistiques running
        affine: Utiliser les paramètres affines
        track_running_stats: Suivre les statistiques running
        **kwargs: Arguments supplémentaires

    Returns:
        nn.Module: Couche BatchNorm
    """
    config = BatchNormConfig(
        num_features=num_features,
        dim=dim,
        eps=eps,
        momentum=momentum,
        affine=affine,
        track_running_stats=track_running_stats,
        **kwargs
    )
    return BatchNormFactory.create(config)


__all__ = [
    'BatchNormConfig',
    'BatchNormFactory',
    'AdaptiveBatchNorm',
    'LayerNorm',
    'InstanceNorm',
    'WeightNorm',
    'create_batch_norm',
]
