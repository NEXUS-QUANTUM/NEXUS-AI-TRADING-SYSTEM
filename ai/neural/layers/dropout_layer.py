# ai/neural/layers/dropout_layer.py
"""
NEXUS AI TRADING SYSTEM - Dropout Layer Module
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
class DropoutConfig:
    """Configuration pour Dropout"""
    p: float = 0.5
    inplace: bool = False
    dim: Optional[int] = None  # Pour AlphaDropout, FeatureAlphaDropout
    use_alpha: bool = False
    use_feature: bool = False
    use_spatial: bool = False
    use_variational: bool = False
    use_concrete: bool = False

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        if self.p < 0 or self.p > 1:
            raise ValueError("p doit être entre 0 et 1")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'p': self.p,
            'inplace': self.inplace,
            'dim': self.dim,
            'use_alpha': self.use_alpha,
            'use_feature': self.use_feature,
            'use_spatial': self.use_spatial,
            'use_variational': self.use_variational,
            'use_concrete': self.use_concrete,
        }


class DropoutFactory:
    """
    Factory pour créer des Dropout layers.

    Supporte:
    - Standard Dropout
    - AlphaDropout
    - FeatureAlphaDropout
    - Dropout2d (SpatialDropout)
    - Dropout3d (SpatialDropout)
    - VariationalDropout
    - ConcreteDropout
    """

    @staticmethod
    def create(config: Union[DropoutConfig, float]) -> nn.Module:
        """
        Crée une couche de Dropout.

        Args:
            config: Configuration ou probabilité

        Returns:
            nn.Module: Couche Dropout
        """
        if isinstance(config, float):
            config = DropoutConfig(p=config)

        if isinstance(config, dict):
            config = DropoutConfig(**config)

        if not isinstance(config, DropoutConfig):
            raise TypeError("config doit être DropoutConfig, float ou dict")

        p = config.p
        inplace = config.inplace
        dim = config.dim
        use_alpha = config.use_alpha
        use_feature = config.use_feature
        use_spatial = config.use_spatial
        use_variational = config.use_variational
        use_concrete = config.use_concrete

        # AlphaDropout
        if use_alpha and use_feature:
            return nn.FeatureAlphaDropout(p=p, inplace=inplace)
        elif use_alpha:
            return nn.AlphaDropout(p=p, inplace=inplace)

        # Spatial Dropout
        if use_spatial:
            if dim is None:
                dim = 2
            if dim == 2:
                return nn.Dropout2d(p=p, inplace=inplace)
            elif dim == 3:
                return nn.Dropout3d(p=p, inplace=inplace)
            else:
                raise ValueError(f"dim doit être 2 ou 3 pour Spatial Dropout, reçu {dim}")

        # Variational Dropout
        if use_variational:
            return VariationalDropout(p=p)

        # Concrete Dropout
        if use_concrete:
            return ConcreteDropout(p=p, dim=dim)

        # Standard Dropout
        return nn.Dropout(p=p, inplace=inplace)


class VariationalDropout(nn.Module):
    """
    Variational Dropout (Gal & Ghahramani, 2016).

    Utilise un même masque de dropout pour toutes les passes
    afin d'approcher l'inférence bayésienne.
    """

    def __init__(self, p: float = 0.5, dim: Optional[int] = None):
        super().__init__()

        self.p = p
        self.dim = dim
        self.mask = None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass de Variational Dropout.

        Args:
            x: Tensor d'entrée

        Returns:
            torch.Tensor: Tensor avec dropout
        """
        if not self.training or self.p == 0:
            return x

        if self.mask is None or self.mask.size() != x.size():
            if self.dim is not None:
                size = list(x.size())
                size[self.dim] = 1
                self.mask = torch.bernoulli(torch.ones(size) * (1 - self.p)).to(x.device)
            else:
                self.mask = torch.bernoulli(torch.ones_like(x) * (1 - self.p))

        # Mise à l'échelle pour conserver la moyenne
        scale = 1.0 / (1.0 - self.p)

        return x * self.mask * scale


class ConcreteDropout(nn.Module):
    """
    Concrete Dropout (Gal et al., 2017).

    Dropout avec paramètre appris pour l'incertitude.
    """

    def __init__(
        self,
        p: float = 0.5,
        dim: Optional[int] = None,
        init_scale: float = 1.0,
        regularizer: float = 1e-4,
    ):
        super().__init__()

        self.p = p
        self.dim = dim
        self.init_scale = init_scale
        self.regularizer = regularizer

        # Paramètre de température appris
        self.log_alpha = nn.Parameter(torch.tensor(init_scale).log())

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass de Concrete Dropout.

        Args:
            x: Tensor d'entrée

        Returns:
            torch.Tensor: Tensor avec dropout
        """
        if not self.training or self.p == 0:
            return x

        alpha = torch.exp(self.log_alpha)
        p = alpha / (1 + alpha)

        # Masque avec bruit concret
        noise = torch.rand_like(x)
        if self.dim is not None:
            # Pour les dimensions spécifiques
            noise = noise.mean(dim=self.dim, keepdim=True)

        z = torch.sigmoid((noise.log() - (1 - noise).log() + self.log_alpha) / 1.0)
        z = z * (1 - p) + p

        return x * z

    def get_regularization(self) -> torch.Tensor:
        """
        Calcule la régularisation pour Concrete Dropout.

        Returns:
            torch.Tensor: Perte de régularisation
        """
        alpha = torch.exp(self.log_alpha)
        p = alpha / (1 + alpha)
        return self.regularizer * (p * (1 - p))


class DropoutBlock(nn.Module):
    """
    Bloc de Dropout avec normalisation adaptative.

    Combine plusieurs stratégies de dropout.
    """

    def __init__(
        self,
        p: float = 0.5,
        use_alpha: bool = False,
        use_feature: bool = False,
        use_spatial: bool = False,
        use_variational: bool = False,
        dim: Optional[int] = None,
        adaptive: bool = True,
    ):
        super().__init__()

        self.p = p
        self.use_alpha = use_alpha
        self.use_feature = use_feature
        self.use_spatial = use_spatial
        self.use_variational = use_variational
        self.dim = dim
        self.adaptive = adaptive

        # Dropout principal
        config = DropoutConfig(
            p=p,
            use_alpha=use_alpha,
            use_feature=use_feature,
            use_spatial=use_spatial,
            use_variational=use_variational,
            dim=dim,
        )
        self.dropout = DropoutFactory.create(config)

        # Dropout supplémentaire pour les features importantes
        if adaptive:
            self.feature_weights = nn.Parameter(torch.ones(1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass du bloc Dropout.

        Args:
            x: Tensor d'entrée

        Returns:
            torch.Tensor: Tensor avec dropout
        """
        x = self.dropout(x)

        # Dropout adaptatif sur les features importantes
        if self.adaptive and self.training:
            if self.feature_weights.dim() == 1:
                weight = torch.sigmoid(self.feature_weights)
                scale = weight / (1 - self.p + self.p * weight)
                x = x * scale

        return x


class ScheduledDropout(nn.Module):
    """
    Dropout avec programme de décroissance.

    Le taux de dropout diminue progressivement pendant l'entraînement.
    """

    def __init__(
        self,
        p_start: float = 0.5,
        p_end: float = 0.1,
        total_steps: int = 1000,
        schedule: str = 'linear',
    ):
        super().__init__()

        self.p_start = p_start
        self.p_end = p_end
        self.total_steps = total_steps
        self.schedule = schedule

        self.step_counter = 0
        self.current_p = p_start

        # Dropout dynamique
        self.dropout = nn.Dropout(p=self.current_p)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass de Scheduled Dropout.

        Args:
            x: Tensor d'entrée

        Returns:
            torch.Tensor: Tensor avec dropout
        """
        if not self.training:
            return x

        # Mise à jour du taux de dropout
        progress = min(self.step_counter / self.total_steps, 1.0)

        if self.schedule == 'linear':
            p = self.p_start - (self.p_start - self.p_end) * progress
        elif self.schedule == 'exponential':
            p = self.p_start * (self.p_end / self.p_start) ** progress
        elif self.schedule == 'cosine':
            p = self.p_end + (self.p_start - self.p_end) * (1 + np.cos(np.pi * progress)) / 2
        else:
            p = self.p_start

        self.current_p = p
        self.dropout.p = p
        self.step_counter += 1

        return self.dropout(x)

    def reset(self):
        """Réinitialise le compteur de pas"""
        self.step_counter = 0
        self.current_p = self.p_start


class AdaptiveDropout(nn.Module):
    """
    Dropout adaptatif basé sur la variance des activations.

    Ajuste le taux de dropout en fonction de la variance des activations
    pour réguler automatiquement le surapprentissage.
    """

    def __init__(
        self,
        p_min: float = 0.1,
        p_max: float = 0.5,
        target_variance: float = 0.5,
        learning_rate: float = 0.01,
        momentum: float = 0.9,
    ):
        super().__init__()

        self.p_min = p_min
        self.p_max = p_max
        self.target_variance = target_variance
        self.learning_rate = learning_rate
        self.momentum = momentum

        self.current_p = (p_min + p_max) / 2
        self.running_variance = None

        self.dropout = nn.Dropout(p=self.current_p)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass d'Adaptive Dropout.

        Args:
            x: Tensor d'entrée

        Returns:
            torch.Tensor: Tensor avec dropout
        """
        if not self.training:
            return x

        # Mise à jour du taux de dropout basé sur la variance
        with torch.no_grad():
            var = x.var().item()

            if self.running_variance is None:
                self.running_variance = var
            else:
                self.running_variance = self.momentum * self.running_variance + (1 - self.momentum) * var

            # Ajustement de p
            if self.running_variance > self.target_variance:
                self.current_p = min(self.p_max, self.current_p + self.learning_rate)
            else:
                self.current_p = max(self.p_min, self.current_p - self.learning_rate)

        self.dropout.p = self.current_p

        return self.dropout(x)


def create_dropout(
    p: float = 0.5,
    use_alpha: bool = False,
    use_feature: bool = False,
    use_spatial: bool = False,
    use_variational: bool = False,
    dim: Optional[int] = None,
    **kwargs
) -> nn.Module:
    """
    Factory pour créer des Dropout layers.

    Args:
        p: Probabilité de dropout
        use_alpha: Utiliser AlphaDropout
        use_feature: Utiliser FeatureAlphaDropout
        use_spatial: Utiliser Spatial Dropout
        use_variational: Utiliser Variational Dropout
        dim: Dimension (pour Spatial Dropout)
        **kwargs: Arguments supplémentaires

    Returns:
        nn.Module: Couche Dropout

    Example:
        ```python
        # Standard Dropout
        dropout = create_dropout(p=0.5)

        # Spatial Dropout pour CNN
        dropout = create_dropout(p=0.3, use_spatial=True, dim=2)

        # Variational Dropout
        dropout = create_dropout(p=0.4, use_variational=True)
        ```
    """
    config = DropoutConfig(
        p=p,
        use_alpha=use_alpha,
        use_feature=use_feature,
        use_spatial=use_spatial,
        use_variational=use_variational,
        dim=dim,
        **kwargs
    )
    return DropoutFactory.create(config)


__all__ = [
    'DropoutConfig',
    'DropoutFactory',
    'VariationalDropout',
    'ConcreteDropout',
    'DropoutBlock',
    'ScheduledDropout',
    'AdaptiveDropout',
    'create_dropout',
]
