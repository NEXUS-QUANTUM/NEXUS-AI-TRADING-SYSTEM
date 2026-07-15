# ai/neural/layers/activation.py
"""
NEXUS AI TRADING SYSTEM - Activation Functions Module
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
class ActivationConfig:
    """Configuration pour les fonctions d'activation"""
    activation_type: str = 'relu'
    negative_slope: float = 0.01
    threshold: float = 1.0
    learnable: bool = False
    inplace: bool = False

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'activation_type': self.activation_type,
            'negative_slope': self.negative_slope,
            'threshold': self.threshold,
            'learnable': self.learnable,
            'inplace': self.inplace,
        }


class ActivationFactory:
    """
    Factory pour créer des fonctions d'activation.

    Supporte les activations standards et avancées:
    - ReLU, LeakyReLU, PReLU, ELU, SELU, GELU, Swish, Mish
    - Sigmoid, Tanh, Softplus, Softsign
    - Parametric activations
    """

    @staticmethod
    def create(config: Union[str, ActivationConfig]) -> nn.Module:
        """
        Crée une fonction d'activation.

        Args:
            config: Type d'activation ou configuration

        Returns:
            nn.Module: Fonction d'activation
        """
        if isinstance(config, str):
            config = ActivationConfig(activation_type=config)

        activation_type = config.activation_type.lower()
        negative_slope = config.negative_slope
        threshold = config.threshold
        learnable = config.learnable
        inplace = config.inplace

        # Activations standards
        if activation_type == 'relu':
            return nn.ReLU(inplace=inplace)

        elif activation_type == 'leaky_relu':
            return nn.LeakyReLU(negative_slope=negative_slope, inplace=inplace)

        elif activation_type == 'prelu':
            if learnable:
                return nn.PReLU()
            else:
                return nn.PReLU(init=negative_slope)

        elif activation_type == 'elu':
            return nn.ELU(alpha=negative_slope, inplace=inplace)

        elif activation_type == 'selu':
            return nn.SELU(inplace=inplace)

        elif activation_type == 'gelu':
            return nn.GELU()

        elif activation_type == 'swish':
            return Swish()

        elif activation_type == 'mish':
            return Mish()

        elif activation_type == 'sigmoid':
            return nn.Sigmoid()

        elif activation_type == 'tanh':
            return nn.Tanh()

        elif activation_type == 'softplus':
            return nn.Softplus()

        elif activation_type == 'softsign':
            return nn.Softsign()

        elif activation_type == 'hardtanh':
            return nn.Hardtanh(min_val=-threshold, max_val=threshold, inplace=inplace)

        elif activation_type == 'hardswish':
            return nn.Hardswish(inplace=inplace)

        elif activation_type == 'rrelu':
            return nn.RReLU(lower=negative_slope / 10, upper=negative_slope, inplace=inplace)

        elif activation_type == 'celu':
            return nn.CELU(alpha=negative_slope, inplace=inplace)

        elif activation_type == 'relu6':
            return nn.ReLU6(inplace=inplace)

        elif activation_type == 'threshold':
            return nn.Threshold(threshold=threshold, value=0.0, inplace=inplace)

        elif activation_type == 'logsigmoid':
            return LogSigmoid()

        elif activation_type == 'softshrink':
            return nn.Softshrink(lambd=threshold)

        elif activation_type == 'hardshrink':
            return nn.Hardshrink(lambd=threshold)

        else:
            raise ValueError(f"Activation non supportée: {activation_type}")


class Swish(nn.Module):
    """
    Swish activation function: x * sigmoid(x)

    Swish is a smooth, non-monotonic activation function that
    often outperforms ReLU in deep networks.
    """

    def __init__(self):
        super().__init__()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.sigmoid(x)


class Mish(nn.Module):
    """
    Mish activation function: x * tanh(softplus(x))

    Mish is a smooth, non-monotonic activation function that
    preserves information flow through the network.
    """

    def __init__(self):
        super().__init__()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.tanh(F.softplus(x))


class LogSigmoid(nn.Module):
    """
    LogSigmoid activation function: log(sigmoid(x))

    Useful for when you need the log of the sigmoid probability.
    """

    def __init__(self):
        super().__init__()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.logsigmoid(x)


class ParametricSwish(nn.Module):
    """
    Parametric Swish: x * sigmoid(beta * x)

    Learnable parameter beta controls the shape of the activation.
    """

    def __init__(self, beta: float = 1.0, learnable: bool = True):
        super().__init__()

        if learnable:
            self.beta = nn.Parameter(torch.tensor(beta))
        else:
            self.register_buffer('beta', torch.tensor(beta))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.sigmoid(self.beta * x)


class ParametricMish(nn.Module):
    """
    Parametric Mish: x * tanh(softplus(beta * x))

    Learnable parameter beta controls the sharpness of the activation.
    """

    def __init__(self, beta: float = 1.0, learnable: bool = True):
        super().__init__()

        if learnable:
            self.beta = nn.Parameter(torch.tensor(beta))
        else:
            self.register_buffer('beta', torch.tensor(beta))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.tanh(F.softplus(self.beta * x))


class ActivationBlock(nn.Module):
    """
    Bloc d'activation avec normalisation optionnelle.

    Combine activation avec BatchNorm ou LayerNorm pour
    améliorer la stabilité de l'entraînement.
    """

    def __init__(
        self,
        activation: Union[str, nn.Module],
        norm_type: Optional[str] = None,
        num_features: Optional[int] = None,
        eps: float = 1e-5,
        momentum: float = 0.1,
        affine: bool = True,
    ):
        super().__init__()

        # Activation
        if isinstance(activation, str):
            self.activation = ActivationFactory.create(activation)
        else:
            self.activation = activation

        # Normalisation
        self.norm = None
        if norm_type is not None:
            if norm_type.lower() == 'batch':
                if num_features is None:
                    raise ValueError("num_features requis pour BatchNorm")
                self.norm = nn.BatchNorm1d(num_features, eps=eps, momentum=momentum, affine=affine)
            elif norm_type.lower() == 'layer':
                if num_features is None:
                    raise ValueError("num_features requis pour LayerNorm")
                self.norm = nn.LayerNorm(num_features, eps=eps, elementwise_affine=affine)
            else:
                raise ValueError(f"Type de normalisation non supporté: {norm_type}")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.norm is not None:
            x = self.norm(x)
        return self.activation(x)


def create_activation(
    activation_type: str = 'relu',
    negative_slope: float = 0.01,
    threshold: float = 1.0,
    learnable: bool = False,
    inplace: bool = False,
    **kwargs
) -> nn.Module:
    """
    Factory pour créer des fonctions d'activation.

    Args:
        activation_type: Type d'activation
        negative_slope: Pente négative (pour LeakyReLU, ELU, etc.)
        threshold: Seuil (pour Threshold, Hardtanh, etc.)
        learnable: Paramètres appris (pour PReLU, etc.)
        inplace: Opération in-place
        **kwargs: Arguments supplémentaires

    Returns:
        nn.Module: Fonction d'activation
    """
    config = ActivationConfig(
        activation_type=activation_type,
        negative_slope=negative_slope,
        threshold=threshold,
        learnable=learnable,
        inplace=inplace,
        **kwargs
    )
    return ActivationFactory.create(config)


__all__ = [
    'ActivationFactory',
    'ActivationConfig',
    'Swish',
    'Mish',
    'LogSigmoid',
    'ParametricSwish',
    'ParametricMish',
    'ActivationBlock',
    'create_activation',
]
