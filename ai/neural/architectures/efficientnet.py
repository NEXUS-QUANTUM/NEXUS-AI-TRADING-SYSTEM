
# ai/neural/architectures/efficientnet.py
"""
NEXUS AI TRADING SYSTEM - EfficientNet Architecture for Financial Data
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
class EfficientNetConfig:
    """Configuration pour EfficientNet"""
    width_multiplier: float = 1.0
    depth_multiplier: float = 1.0
    resolution: int = 224
    num_classes: int = 1000
    dropout_rate: float = 0.2
    stochastic_depth_rate: float = 0.2
    use_se: bool = True  # Squeeze-and-Excitation
    se_ratio: float = 0.25
    use_swish: bool = True
    input_channels: int = 3
    version: str = 'b0'  # b0, b1, b2, b3, b4, b5, b6, b7

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        # Configurations par version
        configs = {
            'b0': (1.0, 1.0, 224),
            'b1': (1.0, 1.1, 240),
            'b2': (1.1, 1.2, 260),
            'b3': (1.2, 1.4, 300),
            'b4': (1.4, 1.8, 380),
            'b5': (1.6, 2.2, 456),
            'b6': (1.8, 2.6, 528),
            'b7': (2.0, 3.1, 600),
        }

        if self.version in configs:
            w, d, r = configs[self.version]
            self.width_multiplier = w
            self.depth_multiplier = d
            self.resolution = r

    def to_dict(self) -> Dict[str, Any]:
        return {
            'width_multiplier': self.width_multiplier,
            'depth_multiplier': self.depth_multiplier,
            'resolution': self.resolution,
            'num_classes': self.num_classes,
            'dropout_rate': self.dropout_rate,
            'stochastic_depth_rate': self.stochastic_depth_rate,
            'use_se': self.use_se,
            'se_ratio': self.se_ratio,
            'use_swish': self.use_swish,
            'input_channels': self.input_channels,
            'version': self.version,
        }


class _SqueezeExcitation(nn.Module):
    """Bloc Squeeze-and-Excitation"""

    def __init__(self, in_channels: int, se_ratio: float = 0.25):
        super().__init__()
        reduced_channels = max(1, int(in_channels * se_ratio))

        self.fc1 = nn.Linear(in_channels, reduced_channels)
        self.fc2 = nn.Linear(reduced_channels, in_channels)

    def forward(self, x):
        batch_size, channels, height, width = x.size()
        se = F.adaptive_avg_pool2d(x, 1).view(batch_size, channels)
        se = F.relu(self.fc1(se))
        se = torch.sigmoid(self.fc2(se))
        se = se.view(batch_size, channels, 1, 1)
        return x * se


class _MBConvBlock(nn.Module):
    """Bloc Mobile Inverted Bottleneck avec Squeeze-and-Excitation"""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        stride: int,
        expand_ratio: int,
        se_ratio: float = 0.25,
        dropout_rate: float = 0.0,
        use_swish: bool = True
    ):
        super().__init__()

        self.use_residual = (stride == 1 and in_channels == out_channels)
        self.dropout_rate = dropout_rate

        expanded_channels = in_channels * expand_ratio
        self.expand = expand_ratio > 1

        # Pointwise expansion
        if self.expand:
            self.expand_conv = nn.Conv2d(in_channels, expanded_channels, 1, bias=False)
            self.expand_bn = nn.BatchNorm2d(expanded_channels)

        # Depthwise convolution
        self.dw_conv = nn.Conv2d(
            expanded_channels,
            expanded_channels,
            kernel_size,
            stride,
            padding=kernel_size // 2,
            groups=expanded_channels,
            bias=False
        )
        self.dw_bn = nn.BatchNorm2d(expanded_channels)

        # Squeeze-and-Excitation
        self.se = _SqueezeExcitation(expanded_channels, se_ratio)

        # Pointwise projection
        self.proj_conv = nn.Conv2d(expanded_channels, out_channels, 1, bias=False)
        self.proj_bn = nn.BatchNorm2d(out_channels)

        # Activation
        self.activation = nn.SiLU() if use_swish else nn.ReLU()

    def forward(self, x):
        residual = x

        if self.expand:
            x = self.expand_conv(x)
            x = self.expand_bn(x)
            x = self.activation(x)

        x = self.dw_conv(x)
        x = self.dw_bn(x)
        x = self.activation(x)

        x = self.se(x)

        x = self.proj_conv(x)
        x = self.proj_bn(x)

        if self.use_residual:
            if self.dropout_rate > 0:
                x = F.dropout(x, p=self.dropout_rate, training=self.training)
            x = x + residual

        return x


class EfficientNet(nn.Module):
    """
    EfficientNet architecture for financial data processing.

    EfficientNet is a family of convolutional neural networks that achieve
    state-of-the-art accuracy while being computationally efficient.

    This implementation supports:
    - EfficientNet B0 to B7 variants
    - Squeeze-and-Excitation blocks
    - Stochastic depth
    - Swish activation
    - Flexible input sizes

    Adapted for financial data (charts, patterns, technical indicators).

    Example:
        ```python
        config = EfficientNetConfig(
            version='b0',
            num_classes=10,
            input_channels=3
        )
        model = EfficientNet(config)

        # Forward pass
        output = model(torch.randn(32, 3, 224, 224))
        ```
    """

    def __init__(self, config: Optional[EfficientNetConfig] = None):
        super().__init__()

        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or EfficientNetConfig()
        self.num_classes = self.config.num_classes
        self.dropout_rate = self.config.dropout_rate
        self.stochastic_depth_rate = self.config.stochastic_depth_rate

        # Configuration des blocs
        # (in_channels, out_channels, kernel_size, stride, expand_ratio, repeats)
        block_configs = [
            (32, 16, 3, 1, 1, 1),
            (16, 24, 3, 2, 6, 2),
            (24, 40, 5, 2, 6, 2),
            (40, 80, 3, 2, 6, 3),
            (80, 112, 5, 1, 6, 3),
            (112, 192, 5, 2, 6, 4),
            (192, 320, 3, 1, 6, 1),
        ]

        # Ajustement des canaux selon le width_multiplier
        def _round_channels(channels: int) -> int:
            return int(self.config.width_multiplier * channels)

        # Calcul du nombre de répétitions selon le depth_multiplier
        def _round_repeats(repeats: int) -> int:
            return int(np.ceil(self.config.depth_multiplier * repeats))

        # Stage 1: Conv2D initial
        in_channels = _round_channels(32)
        self.stem = nn.Sequential(
            nn.Conv2d(
                self.config.input_channels,
                in_channels,
                kernel_size=3,
                stride=2,
                padding=1,
                bias=False
            ),
            nn.BatchNorm2d(in_channels),
            nn.SiLU() if self.config.use_swish else nn.ReLU(),
        )

        # Stages MBConv
        self.blocks = nn.ModuleList()
        total_blocks = sum(_round_repeats(conf[5]) for conf in block_configs)
        block_idx = 0

        for in_channels, out_channels, kernel_size, stride, expand_ratio, repeats in block_configs:
            in_channels = _round_channels(in_channels)
            out_channels = _round_channels(out_channels)

            for i in range(_round_repeats(repeats)):
                stride = stride if i == 0 else 1
                dropout = self.stochastic_depth_rate * (block_idx / total_blocks)

                block = _MBConvBlock(
                    in_channels=in_channels if i == 0 else out_channels,
                    out_channels=out_channels,
                    kernel_size=kernel_size,
                    stride=stride,
                    expand_ratio=expand_ratio,
                    se_ratio=self.config.se_ratio if self.config.use_se else 0.0,
                    dropout_rate=dropout,
                    use_swish=self.config.use_swish,
                )
                self.blocks.append(block)
                block_idx += 1

        # Stage final
        out_channels = _round_channels(1280)
        self.head = nn.Sequential(
            nn.Conv2d(_round_channels(320), out_channels, 1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.SiLU() if self.config.use_swish else nn.ReLU(),
        )

        # Classificateur
        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Dropout(self.dropout_rate) if self.dropout_rate > 0 else nn.Identity(),
            nn.Linear(out_channels, self.num_classes),
        )

        # Initialisation
        self._initialize_weights()

    def _initialize_weights(self):
        """Initialise les poids du modèle"""
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, 0, 0.01)
                nn.init.zeros_(m.bias)

    def forward(self, x):
        x = self.stem(x)

        for block in self.blocks:
            x = block(x)

        x = self.head(x)
        x = self.classifier(x)

        return x

    def extract_features(self, x):
        """
        Extrait les caractéristiques intermédiaires.

        Args:
            x: Tensor d'entrée

        Returns:
            List[Tensor]: Caractéristiques à chaque niveau
        """
        features = []

        x = self.stem(x)
        features.append(x)

        for block in self.blocks:
            x = block(x)
            if isinstance(block, _MBConvBlock) and block.use_residual:
                features.append(x)

        x = self.head(x)
        features.append(x)

        return features

    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres du modèle"""
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques du modèle"""
        total_params = sum(p.numel() for p in self.parameters())
        trainable_params = sum(p.numel() for p in self.parameters() if p.requires_grad)

        return {
            'total_parameters': total_params,
            'trainable_parameters': trainable_params,
            'num_layers': len(self.blocks) + 2,
            'version': self.config.version,
            'resolution': self.config.resolution,
            'input_channels': self.config.input_channels,
            'num_classes': self.config.num_classes,
        }


def create_efficientnet(
    version: str = 'b0',
    num_classes: int = 1000,
    input_channels: int = 3,
    **kwargs
) -> EfficientNet:
    """
    Factory pour créer des modèles EfficientNet.

    Args:
        version: Version ('b0' à 'b7')
        num_classes: Nombre de classes
        input_channels: Canaux d'entrée
        **kwargs: Arguments supplémentaires

    Returns:
        EfficientNet: Instance du modèle

    Example:
        ```python
        # EfficientNet B0 pour classification financière
        model = create_efficientnet(
            version='b0',
            num_classes=10,
            input_channels=3
        )

        # EfficientNet B4 pour analyse de patterns
        model = create_efficientnet(
            version='b4',
            num_classes=5,
            input_channels=1
        )
        ```
    """
    config = EfficientNetConfig(
        version=version,
        num_classes=num_classes,
        input_channels=input_channels,
        **kwargs
    )
    return EfficientNet(config)


__all__ = [
    'EfficientNet',
    'EfficientNetConfig',
    'create_efficientnet',
]
