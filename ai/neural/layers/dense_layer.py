
# ai/neural/layers/dense_layer.py
"""
NEXUS AI TRADING SYSTEM - Dense Layer Module
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
class DenseLayerConfig:
    """Configuration pour Dense Layer"""
    in_features: int
    out_features: int
    bias: bool = True
    activation: Optional[str] = None
    dropout: float = 0.0
    use_batch_norm: bool = False
    use_layer_norm: bool = False
    use_weight_norm: bool = False
    weight_init: str = 'xavier_uniform'
    bias_init: str = 'zeros'
    activation_after_norm: bool = True

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        if self.in_features <= 0:
            raise ValueError("in_features doit être > 0")
        if self.out_features <= 0:
            raise ValueError("out_features doit être > 0")
        if self.dropout < 0 or self.dropout > 1:
            raise ValueError("dropout doit être entre 0 et 1")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'in_features': self.in_features,
            'out_features': self.out_features,
            'bias': self.bias,
            'activation': self.activation,
            'dropout': self.dropout,
            'use_batch_norm': self.use_batch_norm,
            'use_layer_norm': self.use_layer_norm,
            'use_weight_norm': self.use_weight_norm,
            'weight_init': self.weight_init,
            'bias_init': self.bias_init,
            'activation_after_norm': self.activation_after_norm,
        }


class DenseLayer(nn.Module):
    """
    Couche dense (fully connected) avec options avancées.

    Features:
    - Linear transformation with bias
    - Activation functions
    - Dropout
    - Batch Normalization
    - Layer Normalization
    - Weight Normalization
    - Various weight initializations
    - Residual connections

    Example:
        ```python
        config = DenseLayerConfig(
            in_features=256,
            out_features=128,
            activation='relu',
            dropout=0.1,
            use_batch_norm=True
        )
        dense = DenseLayer(config)

        # Forward pass
        output = dense(x)
        ```
    """

    def __init__(self, config: Optional[DenseLayerConfig] = None, **kwargs):
        super().__init__()

        if config is None:
            config = DenseLayerConfig(**kwargs)
        elif isinstance(config, dict):
            config = DenseLayerConfig(**config)

        self.config = config
        self.in_features = config.in_features
        self.out_features = config.out_features
        self.bias = config.bias
        self.activation_name = config.activation
        self.dropout_rate = config.dropout
        self.use_batch_norm = config.use_batch_norm
        self.use_layer_norm = config.use_layer_norm
        self.use_weight_norm = config.use_weight_norm
        self.activation_after_norm = config.activation_after_norm

        # Linear layer
        self.linear = nn.Linear(
            self.in_features,
            self.out_features,
            bias=self.bias
        )

        # Weight initialization
        self._initialize_weights()

        # Weight Norm
        if self.use_weight_norm:
            self.linear = nn.utils.weight_norm(self.linear)

        # Normalization
        self.norm = None
        if self.use_batch_norm:
            self.norm = nn.BatchNorm1d(self.out_features)
        elif self.use_layer_norm:
            self.norm = nn.LayerNorm(self.out_features)

        # Activation
        self.activation = None
        if self.activation_name:
            from ai.neural.layers.activation import ActivationFactory
            self.activation = ActivationFactory.create(self.activation_name)

        # Dropout
        self.dropout = nn.Dropout(self.dropout_rate) if self.dropout_rate > 0 else nn.Identity()

        # Residual connection
        self.use_residual = (self.in_features == self.out_features)

    def _initialize_weights(self):
        """Initialise les poids"""
        weight_init = self.config.weight_init
        bias_init = self.config.bias_init

        # Weight initialization
        if weight_init == 'xavier_uniform':
            nn.init.xavier_uniform_(self.linear.weight)
        elif weight_init == 'xavier_normal':
            nn.init.xavier_normal_(self.linear.weight)
        elif weight_init == 'kaiming_uniform':
            nn.init.kaiming_uniform_(self.linear.weight, nonlinearity='relu')
        elif weight_init == 'kaiming_normal':
            nn.init.kaiming_normal_(self.linear.weight, nonlinearity='relu')
        elif weight_init == 'orthogonal':
            nn.init.orthogonal_(self.linear.weight)
        elif weight_init == 'uniform':
            nn.init.uniform_(self.linear.weight, -0.1, 0.1)
        elif weight_init == 'normal':
            nn.init.normal_(self.linear.weight, 0, 0.01)
        elif weight_init == 'zeros':
            nn.init.zeros_(self.linear.weight)
        else:
            logger.warning(f"Initialisation non supportée: {weight_init}, utilisation de xavier_uniform")
            nn.init.xavier_uniform_(self.linear.weight)

        # Bias initialization
        if self.bias:
            if bias_init == 'zeros':
                nn.init.zeros_(self.linear.bias)
            elif bias_init == 'ones':
                nn.init.ones_(self.linear.bias)
            elif bias_init == 'normal':
                nn.init.normal_(self.linear.bias, 0, 0.01)
            elif bias_init == 'uniform':
                nn.init.uniform_(self.linear.bias, -0.1, 0.1)
            else:
                nn.init.zeros_(self.linear.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass de la couche dense.

        Args:
            x: Tensor d'entrée [batch_size, in_features]

        Returns:
            torch.Tensor: Tensor de sortie [batch_size, out_features]
        """
        residual = x

        # Linear
        x = self.linear(x)

        # Normalization (avant activation)
        if self.norm is not None and not self.activation_after_norm:
            x = self.norm(x)

        # Activation
        if self.activation is not None:
            x = self.activation(x)

        # Normalization (après activation)
        if self.norm is not None and self.activation_after_norm:
            x = self.norm(x)

        # Dropout
        x = self.dropout(x)

        # Residual connection
        if self.use_residual:
            x = x + residual

        return x

    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres de la couche"""
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques de la couche"""
        total_params = sum(p.numel() for p in self.parameters())
        trainable_params = sum(p.numel() for p in self.parameters() if p.requires_grad)

        return {
            'in_features': self.in_features,
            'out_features': self.out_features,
            'total_parameters': total_params,
            'trainable_parameters': trainable_params,
            'activation': self.activation_name,
            'dropout': self.dropout_rate,
            'use_batch_norm': self.use_batch_norm,
            'use_layer_norm': self.use_layer_norm,
            'use_weight_norm': self.use_weight_norm,
            'use_residual': self.use_residual,
        }


class ResidualDenseBlock(nn.Module):
    """
    Bloc dense avec connections résiduelles et normalisation.

    Architecture:
    - Dense Layer 1
    - Normalization
    - Activation
    - Dense Layer 2
    - Normalization
    - Residual connection
    - Activation
    """

    def __init__(
        self,
        in_features: int,
        hidden_features: Optional[int] = None,
        out_features: Optional[int] = None,
        activation: str = 'relu',
        dropout: float = 0.0,
        use_batch_norm: bool = True,
        use_layer_norm: bool = False,
    ):
        super().__init__()

        hidden_features = hidden_features or in_features * 2
        out_features = out_features or in_features

        self.fc1 = DenseLayer(
            DenseLayerConfig(
                in_features=in_features,
                out_features=hidden_features,
                activation=None,
                dropout=dropout,
                use_batch_norm=use_batch_norm,
                use_layer_norm=use_layer_norm,
            )
        )

        self.activation = create_activation(activation)

        self.fc2 = DenseLayer(
            DenseLayerConfig(
                in_features=hidden_features,
                out_features=out_features,
                activation=None,
                dropout=dropout,
                use_batch_norm=use_batch_norm,
                use_layer_norm=use_layer_norm,
            )
        )

        self.final_activation = create_activation(activation)

        self.use_residual = (in_features == out_features)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x

        x = self.fc1(x)
        x = self.activation(x)
        x = self.fc2(x)

        if self.use_residual:
            x = x + residual

        x = self.final_activation(x)

        return x


class AdaptiveDenseLayer(nn.Module):
    """
    Couche dense adaptative avec paramètres appris.

    Permet d'apprendre la dimension de sortie optimale.
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        max_out_features: Optional[int] = None,
        activation: str = 'relu',
        dropout: float = 0.0,
    ):
        super().__init__()

        self.in_features = in_features
        self.out_features = out_features
        self.max_out_features = max_out_features or out_features

        # Paramètres appris pour la sélection de features
        self.feature_weights = nn.Parameter(torch.ones(out_features))

        self.linear = nn.Linear(in_features, self.max_out_features)
        self.activation = create_activation(activation)
        self.dropout = nn.Dropout(dropout) if dropout > 0 else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Projection
        x = self.linear(x)

        # Sélection adaptative des features
        weights = F.softmax(self.feature_weights, dim=0)
        x = x * weights[:self.out_features]

        x = self.activation(x)
        x = self.dropout(x)

        return x


def create_dense_layer(
    in_features: int,
    out_features: int,
    activation: Optional[str] = None,
    dropout: float = 0.0,
    use_batch_norm: bool = False,
    use_layer_norm: bool = False,
    **kwargs
) -> DenseLayer:
    """
    Factory pour créer des couches denses.

    Args:
        in_features: Nombre de features d'entrée
        out_features: Nombre de features de sortie
        activation: Fonction d'activation
        dropout: Taux de dropout
        use_batch_norm: Utiliser BatchNorm
        use_layer_norm: Utiliser LayerNorm
        **kwargs: Arguments supplémentaires

    Returns:
        DenseLayer: Couche dense

    Example:
        ```python
        dense = create_dense_layer(
            in_features=256,
            out_features=128,
            activation='relu',
            dropout=0.1,
            use_batch_norm=True
        )
        ```
    """
    config = DenseLayerConfig(
        in_features=in_features,
        out_features=out_features,
        activation=activation,
        dropout=dropout,
        use_batch_norm=use_batch_norm,
        use_layer_norm=use_layer_norm,
        **kwargs
    )
    return DenseLayer(config)


__all__ = [
    'DenseLayer',
    'DenseLayerConfig',
    'ResidualDenseBlock',
    'AdaptiveDenseLayer',
    'create_dense_layer',
]
