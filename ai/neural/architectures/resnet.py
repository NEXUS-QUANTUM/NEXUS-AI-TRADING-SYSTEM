
# ai/neural/architectures/resnet.py
"""
NEXUS AI TRADING SYSTEM - ResNet Architecture for Financial Data
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
class ResNetConfig:
    """Configuration pour ResNet"""
    num_classes: int = 1000
    input_channels: int = 3
    dropout_rate: float = 0.0
    version: str = 'resnet50'  # resnet18, resnet34, resnet50, resnet101, resnet152
    use_batch_norm: bool = True
    use_pretrained: bool = False
    input_size: int = 224
    activation: str = 'relu'  # relu, swish, gelu

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'num_classes': self.num_classes,
            'input_channels': self.input_channels,
            'dropout_rate': self.dropout_rate,
            'version': self.version,
            'use_batch_norm': self.use_batch_norm,
            'use_pretrained': self.use_pretrained,
            'input_size': self.input_size,
            'activation': self.activation,
        }


class _BasicBlock(nn.Module):
    """Bloc ResNet de base (18, 34)"""

    expansion = 1

    def __init__(
        self,
        in_planes: int,
        planes: int,
        stride: int = 1,
        downsample: Optional[nn.Module] = None,
        use_batch_norm: bool = True,
        activation: str = 'relu'
    ):
        super().__init__()

        self.activation = self._get_activation(activation)

        self.conv1 = nn.Conv2d(in_planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes) if use_batch_norm else nn.Identity()

        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes) if use_batch_norm else nn.Identity()

        self.downsample = downsample

    def _get_activation(self, name: str) -> nn.Module:
        if name == 'relu':
            return nn.ReLU(inplace=True)
        elif name == 'swish':
            return nn.SiLU(inplace=True)
        elif name == 'gelu':
            return nn.GELU()
        else:
            return nn.ReLU(inplace=True)

    def forward(self, x):
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.activation(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out += identity
        out = self.activation(out)

        return out


class _Bottleneck(nn.Module):
    """Bloc ResNet Bottleneck (50, 101, 152)"""

    expansion = 4

    def __init__(
        self,
        in_planes: int,
        planes: int,
        stride: int = 1,
        downsample: Optional[nn.Module] = None,
        use_batch_norm: bool = True,
        activation: str = 'relu'
    ):
        super().__init__()

        self.activation = self._get_activation(activation)

        self.conv1 = nn.Conv2d(in_planes, planes, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes) if use_batch_norm else nn.Identity()

        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes) if use_batch_norm else nn.Identity()

        self.conv3 = nn.Conv2d(planes, planes * self.expansion, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm2d(planes * self.expansion) if use_batch_norm else nn.Identity()

        self.downsample = downsample

    def _get_activation(self, name: str) -> nn.Module:
        if name == 'relu':
            return nn.ReLU(inplace=True)
        elif name == 'swish':
            return nn.SiLU(inplace=True)
        elif name == 'gelu':
            return nn.GELU()
        else:
            return nn.ReLU(inplace=True)

    def forward(self, x):
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.activation(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.activation(out)

        out = self.conv3(out)
        out = self.bn3(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out += identity
        out = self.activation(out)

        return out


class ResNet(nn.Module):
    """
    ResNet architecture for financial data processing.

    ResNet (Residual Network) uses skip connections to enable training
    of very deep networks by addressing the vanishing gradient problem.

    This implementation supports:
    - ResNet18, ResNet34, ResNet50, ResNet101, ResNet152
    - Batch normalization
    - Multiple activation functions (ReLU, Swish, GELU)
    - Flexible input sizes

    Adapted for financial data (charts, patterns, technical indicators).

    Example:
        ```python
        config = ResNetConfig(
            version='resnet50',
            num_classes=10,
            input_channels=3
        )
        model = ResNet(config)

        # Forward pass
        output = model(torch.randn(32, 3, 224, 224))
        ```
    """

    def __init__(self, config: Optional[ResNetConfig] = None):
        super().__init__()

        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or ResNetConfig()
        self.num_classes = self.config.num_classes
        self.in_planes = 64

        # Configurations par version
        configs = {
            'resnet18': (_BasicBlock, [2, 2, 2, 2]),
            'resnet34': (_BasicBlock, [3, 4, 6, 3]),
            'resnet50': (_Bottleneck, [3, 4, 6, 3]),
            'resnet101': (_Bottleneck, [3, 4, 23, 3]),
            'resnet152': (_Bottleneck, [3, 8, 36, 3]),
        }

        if self.config.version not in configs:
            raise ValueError(f"Version non supportée: {self.config.version}")

        block, layers = configs[self.config.version]
        self.block = block
        self.layers = layers

        self.activation = self._get_activation(self.config.activation)
        self.use_batch_norm = self.config.use_batch_norm

        # Stem
        self.conv1 = nn.Conv2d(
            self.config.input_channels,
            64,
            kernel_size=7,
            stride=2,
            padding=3,
            bias=False
        )
        self.bn1 = nn.BatchNorm2d(64) if self.use_batch_norm else nn.Identity()
        self.activation = self._get_activation(self.config.activation)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)

        # Layers
        self.layer1 = self._make_layer(block, 64, layers[0])
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2)
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2)

        # Classifier
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))
        self.dropout = nn.Dropout(self.config.dropout_rate) if self.config.dropout_rate > 0 else nn.Identity()
        self.fc = nn.Linear(512 * block.expansion, self.num_classes)

        # Initialisation
        self._initialize_weights()

    def _get_activation(self, name: str) -> nn.Module:
        if name == 'relu':
            return nn.ReLU(inplace=True)
        elif name == 'swish':
            return nn.SiLU(inplace=True)
        elif name == 'gelu':
            return nn.GELU()
        else:
            return nn.ReLU(inplace=True)

    def _make_layer(
        self,
        block: nn.Module,
        planes: int,
        blocks: int,
        stride: int = 1
    ) -> nn.Sequential:
        downsample = None

        if stride != 1 or self.in_planes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(
                    self.in_planes,
                    planes * block.expansion,
                    kernel_size=1,
                    stride=stride,
                    bias=False
                ),
                nn.BatchNorm2d(planes * block.expansion) if self.use_batch_norm else nn.Identity(),
            )

        layers = []
        layers.append(
            block(
                self.in_planes,
                planes,
                stride,
                downsample,
                self.use_batch_norm,
                self.config.activation
            )
        )
        self.in_planes = planes * block.expansion

        for _ in range(1, blocks):
            layers.append(
                block(
                    self.in_planes,
                    planes,
                    1,
                    None,
                    self.use_batch_norm,
                    self.config.activation
                )
            )

        return nn.Sequential(*layers)

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
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.activation(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        x = self.dropout(x)
        x = self.fc(x)

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

        x = self.conv1(x)
        x = self.bn1(x)
        x = self.activation(x)
        x = self.maxpool(x)
        features.append(x)

        x = self.layer1(x)
        features.append(x)

        x = self.layer2(x)
        features.append(x)

        x = self.layer3(x)
        features.append(x)

        x = self.layer4(x)
        features.append(x)

        return features

    def get_layer_outputs(self, x):
        """
        Retourne les sorties de chaque couche.

        Args:
            x: Tensor d'entrée

        Returns:
            Dict[str, Tensor]: Sorties par couche
        """
        outputs = {}

        x = self.conv1(x)
        x = self.bn1(x)
        x = self.activation(x)
        outputs['stem'] = x

        x = self.maxpool(x)
        outputs['maxpool'] = x

        x = self.layer1(x)
        outputs['layer1'] = x

        x = self.layer2(x)
        outputs['layer2'] = x

        x = self.layer3(x)
        outputs['layer3'] = x

        x = self.layer4(x)
        outputs['layer4'] = x

        return outputs

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
            'version': self.config.version,
            'input_size': self.config.input_size,
            'input_channels': self.config.input_channels,
            'num_classes': self.config.num_classes,
            'activation': self.config.activation,
            'use_batch_norm': self.config.use_batch_norm,
        }


def create_resnet(
    version: str = 'resnet50',
    num_classes: int = 1000,
    input_channels: int = 3,
    **kwargs
) -> ResNet:
    """
    Factory pour créer des modèles ResNet.

    Args:
        version: Version ('resnet18', 'resnet34', 'resnet50', 'resnet101', 'resnet152')
        num_classes: Nombre de classes
        input_channels: Canaux d'entrée
        **kwargs: Arguments supplémentaires

    Returns:
        ResNet: Instance du modèle

    Example:
        ```python
        # ResNet50 pour classification financière
        model = create_resnet(
            version='resnet50',
            num_classes=10,
            input_channels=3
        )

        # ResNet18 pour analyse de patterns
        model = create_resnet(
            version='resnet18',
            num_classes=5,
            input_channels=1,
            activation='swish'
        )
        ```
    """
    config = ResNetConfig(
        version=version,
        num_classes=num_classes,
        input_channels=input_channels,
        **kwargs
    )
    return ResNet(config)


__all__ = [
    'ResNet',
    'ResNetConfig',
    'create_resnet',
]
