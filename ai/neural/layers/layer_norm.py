
# ai/neural/layers/layer_norm.py
"""
NEXUS AI TRADING SYSTEM - Layer Normalization Module
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
class LayerNormConfig:
    """Configuration pour Layer Normalization"""
    normalized_shape: Union[int, List[int], Tuple[int, ...]]
    eps: float = 1e-5
    elementwise_affine: bool = True
    elementwise_scale: bool = True
    use_learnable_scale: bool = False
    use_learnable_bias: bool = False
    use_rms_norm: bool = False
    use_pre_norm: bool = False
    use_post_norm: bool = False

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        if self.eps <= 0:
            raise ValueError("eps doit être > 0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'normalized_shape': self.normalized_shape,
            'eps': self.eps,
            'elementwise_affine': self.elementwise_affine,
            'elementwise_scale': self.elementwise_scale,
            'use_learnable_scale': self.use_learnable_scale,
            'use_learnable_bias': self.use_learnable_bias,
            'use_rms_norm': self.use_rms_norm,
            'use_pre_norm': self.use_pre_norm,
            'use_post_norm': self.use_post_norm,
        }


class LayerNorm(nn.Module):
    """
    Layer Normalization (Ba et al., 2016).

    LayerNorm normalise les activations d'une seule couche
    indépendamment de la taille du batch.

    Features:
    - Standard LayerNorm
    - RMSNorm (Zhang & Sennrich, 2019)
    - Pre-Norm / Post-Norm
    - Learnable scale and bias
    - Configurable normalization shape

    Example:
        ```python
        config = LayerNormConfig(
            normalized_shape=256,
            eps=1e-5,
            elementwise_affine=True
        )
        layer_norm = LayerNorm(config)

        # Forward pass
        output = layer_norm(x)
        ```
    """

    def __init__(self, config: Optional[LayerNormConfig] = None, **kwargs):
        super().__init__()

        if config is None:
            config = LayerNormConfig(**kwargs)
        elif isinstance(config, dict):
            config = LayerNormConfig(**config)

        self.config = config
        self.normalized_shape = config.normalized_shape
        self.eps = config.eps
        self.elementwise_affine = config.elementwise_affine
        self.elementwise_scale = config.elementwise_scale
        self.use_learnable_scale = config.use_learnable_scale
        self.use_learnable_bias = config.use_learnable_bias
        self.use_rms_norm = config.use_rms_norm
        self.use_pre_norm = config.use_pre_norm
        self.use_post_norm = config.use_post_norm

        # Paramètres affines
        if self.elementwise_affine:
            if self.use_learnable_scale:
                self.weight = nn.Parameter(torch.ones(self.normalized_shape))
            else:
                self.register_buffer('weight', torch.ones(self.normalized_shape))

            if self.use_learnable_bias:
                self.bias = nn.Parameter(torch.zeros(self.normalized_shape))
            else:
                self.register_buffer('bias', torch.zeros(self.normalized_shape))

        else:
            self.register_buffer('weight', torch.ones(self.normalized_shape))
            self.register_buffer('bias', torch.zeros(self.normalized_shape))

        # RMSNorm (sans centrage)
        self.use_rms_norm = config.use_rms_norm

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass de Layer Normalization.

        Args:
            x: Tensor d'entrée

        Returns:
            torch.Tensor: Tensor normalisé
        """
        if self.use_rms_norm:
            return self._rms_norm(x)
        else:
            return self._layer_norm(x)

    def _layer_norm(self, x: torch.Tensor) -> torch.Tensor:
        """Layer Normalization standard"""
        # Calcul des statistiques
        mean = x.mean(dim=-1, keepdim=True)
        var = x.var(dim=-1, keepdim=True, unbiased=False)

        # Normalisation
        x_norm = (x - mean) / torch.sqrt(var + self.eps)

        # Affine transformation
        if self.elementwise_affine:
            x_norm = x_norm * self.weight + self.bias

        return x_norm

    def _rms_norm(self, x: torch.Tensor) -> torch.Tensor:
        """RMSNorm (Root Mean Square Normalization)"""
        # Calcul de la norme RMS
        rms = torch.sqrt(torch.mean(x ** 2, dim=-1, keepdim=True) + self.eps)

        # Normalisation
        x_norm = x / rms

        # Scale (sans biais pour RMSNorm)
        if self.elementwise_scale:
            x_norm = x_norm * self.weight

        return x_norm


class PreLayerNorm(nn.Module):
    """
    Pre-Layer Normalization.

    Applique LayerNorm avant les couches principales.
    Utilisé dans les Transformers modernes.
    """

    def __init__(
        self,
        normalized_shape: Union[int, List[int], Tuple[int, ...]],
        eps: float = 1e-5,
        elementwise_affine: bool = True,
    ):
        super().__init__()

        self.norm = LayerNorm(
            LayerNormConfig(
                normalized_shape=normalized_shape,
                eps=eps,
                elementwise_affine=elementwise_affine,
                use_pre_norm=True,
            )
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass de Pre-LayerNorm.

        Args:
            x: Tensor d'entrée

        Returns:
            torch.Tensor: Tensor normalisé
        """
        return self.norm(x)


class PostLayerNorm(nn.Module):
    """
    Post-Layer Normalization.

    Applique LayerNorm après les couches principales.
    Utilisé dans le Transformer original.
    """

    def __init__(
        self,
        normalized_shape: Union[int, List[int], Tuple[int, ...]],
        eps: float = 1e-5,
        elementwise_affine: bool = True,
    ):
        super().__init__()

        self.norm = LayerNorm(
            LayerNormConfig(
                normalized_shape=normalized_shape,
                eps=eps,
                elementwise_affine=elementwise_affine,
                use_post_norm=True,
            )
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass de Post-LayerNorm.

        Args:
            x: Tensor d'entrée

        Returns:
            torch.Tensor: Tensor normalisé
        """
        return self.norm(x)


class RMSNorm(nn.Module):
    """
    RMSNorm - Root Mean Square Layer Normalization.

    Plus rapide que LayerNorm car il ne calcule pas la moyenne.
    Utilisé dans LLaMA, Mistral, etc.
    """

    def __init__(
        self,
        normalized_shape: Union[int, List[int], Tuple[int, ...]],
        eps: float = 1e-5,
        elementwise_scale: bool = True,
    ):
        super().__init__()

        self.normalized_shape = normalized_shape
        self.eps = eps
        self.elementwise_scale = elementwise_scale

        if elementwise_scale:
            self.weight = nn.Parameter(torch.ones(normalized_shape))
        else:
            self.register_buffer('weight', torch.ones(normalized_shape))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass de RMSNorm.

        Args:
            x: Tensor d'entrée

        Returns:
            torch.Tensor: Tensor normalisé
        """
        # Calcul de la norme RMS
        rms = torch.sqrt(torch.mean(x ** 2, dim=-1, keepdim=True) + self.eps)

        # Normalisation
        x_norm = x / rms

        # Scale
        if self.elementwise_scale:
            x_norm = x_norm * self.weight

        return x_norm


class AdaptiveLayerNorm(nn.Module):
    """
    Layer Normalization adaptative avec poids appris.

    Permet d'apprendre l'importance relative des dimensions
    normalisées.
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

        # Poids d'importance appris
        self.importance = nn.Parameter(torch.ones(normalized_shape))

        if elementwise_affine:
            self.weight = nn.Parameter(torch.ones(normalized_shape))
            self.bias = nn.Parameter(torch.zeros(normalized_shape))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass d'Adaptive LayerNorm.

        Args:
            x: Tensor d'entrée

        Returns:
            torch.Tensor: Tensor normalisé
        """
        # Normalisation standard
        mean = x.mean(dim=-1, keepdim=True)
        var = x.var(dim=-1, keepdim=True, unbiased=False)
        x_norm = (x - mean) / torch.sqrt(var + self.eps)

        # Application des poids d'importance
        importance = F.softmax(self.importance, dim=0)
        x_norm = x_norm * importance

        # Affine transformation
        x_norm = x_norm * self.weight + self.bias

        return x_norm


class LayerNormBlock(nn.Module):
    """
    Bloc Layer Normalization avec activation intégrée.

    Combine LayerNorm avec activation pour une architecture
    simplifiée.
    """

    def __init__(
        self,
        normalized_shape: Union[int, List[int], Tuple[int, ...]],
        activation: str = 'gelu',
        eps: float = 1e-5,
        elementwise_affine: bool = True,
        use_pre_norm: bool = True,
    ):
        super().__init__()

        self.use_pre_norm = use_pre_norm

        # LayerNorm
        if use_pre_norm:
            self.norm = PreLayerNorm(
                normalized_shape=normalized_shape,
                eps=eps,
                elementwise_affine=elementwise_affine,
            )
        else:
            self.norm = PostLayerNorm(
                normalized_shape=normalized_shape,
                eps=eps,
                elementwise_affine=elementwise_affine,
            )

        # Activation
        from ai.neural.layers.activation import ActivationFactory
        self.activation = ActivationFactory.create(activation)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass du bloc LayerNorm.

        Args:
            x: Tensor d'entrée

        Returns:
            torch.Tensor: Tensor normalisé et activé
        """
        x = self.norm(x)
        x = self.activation(x)
        return x


def create_layer_norm(
    normalized_shape: Union[int, List[int], Tuple[int, ...]],
    eps: float = 1e-5,
    elementwise_affine: bool = True,
    use_rms_norm: bool = False,
    **kwargs
) -> nn.Module:
    """
    Factory pour créer des Layer Normalization.

    Args:
        normalized_shape: Forme à normaliser
        eps: Epsilon pour la stabilité
        elementwise_affine: Utiliser les paramètres affines
        use_rms_norm: Utiliser RMSNorm
        **kwargs: Arguments supplémentaires

    Returns:
        nn.Module: Couche de normalisation

    Example:
        ```python
        # LayerNorm standard
        norm = create_layer_norm(256)

        # RMSNorm (plus rapide)
        norm = create_layer_norm(256, use_rms_norm=True)

        # Pre-LayerNorm pour Transformers
        norm = create_layer_norm(256, use_pre_norm=True)
        ```
    """
    if use_rms_norm:
        return RMSNorm(
            normalized_shape=normalized_shape,
            eps=eps,
            elementwise_scale=elementwise_affine,
        )

    config = LayerNormConfig(
        normalized_shape=normalized_shape,
        eps=eps,
        elementwise_affine=elementwise_affine,
        **kwargs
    )
    return LayerNorm(config)


__all__ = [
    'LayerNorm',
    'LayerNormConfig',
    'PreLayerNorm',
    'PostLayerNorm',
    'RMSNorm',
    'AdaptiveLayerNorm',
    'LayerNormBlock',
    'create_layer_norm',
]
