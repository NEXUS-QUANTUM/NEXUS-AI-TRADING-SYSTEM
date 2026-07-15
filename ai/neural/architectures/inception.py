
# ai/neural/architectures/inception.py
"""
NEXUS AI TRADING SYSTEM - Inception Architecture for Financial Data
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
class InceptionConfig:
    """Configuration pour Inception"""
    num_classes: int = 1000
    input_channels: int = 3
    dropout_rate: float = 0.4
    aux_logits: bool = True
    version: str = 'v3'  # v1, v2, v3, v4
    use_batch_norm: bool = True
    use_label_smoothing: bool = False
    label_smoothing: float = 0.1
    input_size: int = 299

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        # Configurations par version
        if self.version == 'v1':
            self.input_size = 224
        elif self.version in ['v2', 'v3', 'v4']:
            self.input_size = 299
        else:
            self.input_size = 299

    def to_dict(self) -> Dict[str, Any]:
        return {
            'num_classes': self.num_classes,
            'input_channels': self.input_channels,
            'dropout_rate': self.dropout_rate,
            'aux_logits': self.aux_logits,
            'version': self.version,
            'use_batch_norm': self.use_batch_norm,
            'use_label_smoothing': self.use_label_smoothing,
            'label_smoothing': self.label_smoothing,
            'input_size': self.input_size,
        }


class _InceptionA(nn.Module):
    """Module Inception-A (version 3)"""

    def __init__(
        self,
        in_channels: int,
        pool_features: int,
        use_batch_norm: bool = True
    ):
        super().__init__()

        self.branch1 = nn.Sequential(
            nn.Conv2d(in_channels, 64, 1, bias=False),
            nn.BatchNorm2d(64) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )

        self.branch2 = nn.Sequential(
            nn.Conv2d(in_channels, 48, 1, bias=False),
            nn.BatchNorm2d(48) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
            nn.Conv2d(48, 64, 5, padding=2, bias=False),
            nn.BatchNorm2d(64) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )

        self.branch3 = nn.Sequential(
            nn.Conv2d(in_channels, 64, 1, bias=False),
            nn.BatchNorm2d(64) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 96, 3, padding=1, bias=False),
            nn.BatchNorm2d(96) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
            nn.Conv2d(96, 96, 3, padding=1, bias=False),
            nn.BatchNorm2d(96) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )

        self.branch4 = nn.Sequential(
            nn.AvgPool2d(3, stride=1, padding=1),
            nn.Conv2d(in_channels, pool_features, 1, bias=False),
            nn.BatchNorm2d(pool_features) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        out1 = self.branch1(x)
        out2 = self.branch2(x)
        out3 = self.branch3(x)
        out4 = self.branch4(x)
        return torch.cat([out1, out2, out3, out4], dim=1)


class _InceptionB(nn.Module):
    """Module Inception-B (version 3)"""

    def __init__(self, in_channels: int, use_batch_norm: bool = True):
        super().__init__()

        self.branch1 = nn.Sequential(
            nn.Conv2d(in_channels, 384, 3, stride=2, bias=False),
            nn.BatchNorm2d(384) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )

        self.branch2 = nn.Sequential(
            nn.Conv2d(in_channels, 64, 1, bias=False),
            nn.BatchNorm2d(64) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 96, 3, padding=1, bias=False),
            nn.BatchNorm2d(96) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
            nn.Conv2d(96, 96, 3, stride=2, bias=False),
            nn.BatchNorm2d(96) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )

        self.branch3 = nn.Sequential(
            nn.MaxPool2d(3, stride=2),
        )

    def forward(self, x):
        out1 = self.branch1(x)
        out2 = self.branch2(x)
        out3 = self.branch3(x)
        return torch.cat([out1, out2, out3], dim=1)


class _InceptionC(nn.Module):
    """Module Inception-C (version 3)"""

    def __init__(self, in_channels: int, use_batch_norm: bool = True):
        super().__init__()

        self.branch1 = nn.Sequential(
            nn.Conv2d(in_channels, 192, 1, bias=False),
            nn.BatchNorm2d(192) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )

        self.branch2 = nn.Sequential(
            nn.Conv2d(in_channels, 128, 1, bias=False),
            nn.BatchNorm2d(128) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 128, 1, padding=1, bias=False),
            nn.BatchNorm2d(128) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 192, 1, padding=1, bias=False),
            nn.BatchNorm2d(192) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )

        self.branch3 = nn.Sequential(
            nn.Conv2d(in_channels, 128, 1, bias=False),
            nn.BatchNorm2d(128) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 128, 1, padding=1, bias=False),
            nn.BatchNorm2d(128) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
            nn.Conv2d(128, 128, 1, padding=1, bias=False),
            nn.BatchNorm2d(128) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )

        self.branch4 = nn.Sequential(
            nn.AvgPool2d(3, stride=1, padding=1),
            nn.Conv2d(in_channels, 128, 1, bias=False),
            nn.BatchNorm2d(128) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        out1 = self.branch1(x)
        out2 = self.branch2(x)
        out3 = self.branch3(x)
        out4 = self.branch4(x)
        return torch.cat([out1, out2, out3, out4], dim=1)


class _InceptionD(nn.Module):
    """Module Inception-D (version 3)"""

    def __init__(self, in_channels: int, use_batch_norm: bool = True):
        super().__init__()

        self.branch1 = nn.Sequential(
            nn.Conv2d(in_channels, 192, 1, bias=False),
            nn.BatchNorm2d(192) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
            nn.Conv2d(192, 320, 3, stride=2, bias=False),
            nn.BatchNorm2d(320) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )

        self.branch2 = nn.Sequential(
            nn.Conv2d(in_channels, 192, 1, bias=False),
            nn.BatchNorm2d(192) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
            nn.Conv2d(192, 192, 3, padding=1, bias=False),
            nn.BatchNorm2d(192) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
            nn.Conv2d(192, 192, 3, stride=2, bias=False),
            nn.BatchNorm2d(192) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )

        self.branch3 = nn.Sequential(
            nn.MaxPool2d(3, stride=2),
        )

    def forward(self, x):
        out1 = self.branch1(x)
        out2 = self.branch2(x)
        out3 = self.branch3(x)
        return torch.cat([out1, out2, out3], dim=1)


class _InceptionE(nn.Module):
    """Module Inception-E (version 3)"""

    def __init__(self, in_channels: int, use_batch_norm: bool = True):
        super().__init__()

        self.branch1 = nn.Sequential(
            nn.Conv2d(in_channels, 320, 1, bias=False),
            nn.BatchNorm2d(320) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )

        self.branch2 = nn.Sequential(
            nn.Conv2d(in_channels, 384, 1, bias=False),
            nn.BatchNorm2d(384) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )
        self.branch2a = nn.Sequential(
            nn.Conv2d(384, 384, 1, padding=1, bias=False),
            nn.BatchNorm2d(384) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )
        self.branch2b = nn.Sequential(
            nn.Conv2d(384, 384, 1, padding=1, bias=False),
            nn.BatchNorm2d(384) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )

        self.branch3 = nn.Sequential(
            nn.Conv2d(in_channels, 448, 1, bias=False),
            nn.BatchNorm2d(448) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
            nn.Conv2d(448, 384, 3, padding=1, bias=False),
            nn.BatchNorm2d(384) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )
        self.branch3a = nn.Sequential(
            nn.Conv2d(384, 384, 1, padding=1, bias=False),
            nn.BatchNorm2d(384) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )
        self.branch3b = nn.Sequential(
            nn.Conv2d(384, 384, 1, padding=1, bias=False),
            nn.BatchNorm2d(384) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )

        self.branch4 = nn.Sequential(
            nn.AvgPool2d(3, stride=1, padding=1),
            nn.Conv2d(in_channels, 192, 1, bias=False),
            nn.BatchNorm2d(192) if use_batch_norm else nn.Identity(),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        out1 = self.branch1(x)

        out2 = self.branch2(x)
        out2 = torch.cat([self.branch2a(out2), self.branch2b(out2)], dim=1)

        out3 = self.branch3(x)
        out3 = torch.cat([self.branch3a(out3), self.branch3b(out3)], dim=1)

        out4 = self.branch4(x)

        return torch.cat([out1, out2, out3, out4], dim=1)


class _AuxLogits(nn.Module):
    """Logits auxiliaires pour Inception"""

    def __init__(self, in_channels: int, num_classes: int, use_batch_norm: bool = True):
        super().__init__()

        self.avg_pool = nn.AvgPool2d(5, stride=3)
        self.conv = nn.Conv2d(in_channels, 128, 1, bias=False)
        self.bn = nn.BatchNorm2d(128) if use_batch_norm else nn.Identity()
        self.relu = nn.ReLU(inplace=True)
        self.fc1 = nn.Linear(128 * 4 * 4, 768)
        self.fc2 = nn.Linear(768, num_classes)

    def forward(self, x):
        x = self.avg_pool(x)
        x = self.conv(x)
        x = self.bn(x)
        x = self.relu(x)
        x = x.view(x.size(0), -1)
        x = self.fc1(x)
        x = self.relu(x)
        x = self.fc2(x)
        return x


class Inception(nn.Module):
    """
    Inception architecture for financial data processing.

    Inception is a convolutional neural network architecture that uses
    multiple filter sizes in parallel to capture features at different scales.

    This implementation supports:
    - Inception V3 architecture
    - Auxiliary classifiers
    - Batch normalization
    - Multiple input sizes

    Adapted for financial data (charts, patterns, technical indicators).

    Example:
        ```python
        config = InceptionConfig(
            version='v3',
            num_classes=10,
            input_channels=3
        )
        model = Inception(config)

        # Forward pass
        output, aux_output = model(torch.randn(32, 3, 299, 299))
        ```
    """

    def __init__(self, config: Optional[InceptionConfig] = None):
        super().__init__()

        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

        self.config = config or InceptionConfig()
        self.num_classes = self.config.num_classes
        self.aux_logits = self.config.aux_logits
        self.use_batch_norm = self.config.use_batch_norm
        self.dropout_rate = self.config.dropout_rate

        in_channels = self.config.input_channels

        # Stem
        self.conv1 = nn.Conv2d(in_channels, 32, 3, stride=2, bias=False)
        self.bn1 = nn.BatchNorm2d(32) if self.use_batch_norm else nn.Identity()
        self.relu1 = nn.ReLU(inplace=True)

        self.conv2 = nn.Conv2d(32, 32, 3, bias=False)
        self.bn2 = nn.BatchNorm2d(32) if self.use_batch_norm else nn.Identity()
        self.relu2 = nn.ReLU(inplace=True)

        self.conv3 = nn.Conv2d(32, 64, 3, padding=1, bias=False)
        self.bn3 = nn.BatchNorm2d(64) if self.use_batch_norm else nn.Identity()
        self.relu3 = nn.ReLU(inplace=True)

        self.pool1 = nn.MaxPool2d(3, stride=2)

        self.conv4 = nn.Conv2d(64, 80, 1, bias=False)
        self.bn4 = nn.BatchNorm2d(80) if self.use_batch_norm else nn.Identity()
        self.relu4 = nn.ReLU(inplace=True)

        self.conv5 = nn.Conv2d(80, 192, 3, bias=False)
        self.bn5 = nn.BatchNorm2d(192) if self.use_batch_norm else nn.Identity()
        self.relu5 = nn.ReLU(inplace=True)

        self.pool2 = nn.MaxPool2d(3, stride=2)

        # Modules Inception
        self.inception_a1 = _InceptionA(192, 32, self.use_batch_norm)
        self.inception_a2 = _InceptionA(256, 64, self.use_batch_norm)
        self.inception_a3 = _InceptionA(288, 64, self.use_batch_norm)
        self.inception_b1 = _InceptionB(288, self.use_batch_norm)
        self.inception_c1 = _InceptionC(768, self.use_batch_norm)
        self.inception_c2 = _InceptionC(768, self.use_batch_norm)
        self.inception_c3 = _InceptionC(768, self.use_batch_norm)
        self.inception_c4 = _InceptionC(768, self.use_batch_norm)
        self.inception_d1 = _InceptionD(768, self.use_batch_norm)
        self.inception_e1 = _InceptionE(1280, self.use_batch_norm)
        self.inception_e2 = _InceptionE(2048, self.use_batch_norm)

        # Auxiliary logits
        if self.aux_logits:
            self.aux_logits_layer = _AuxLogits(768, self.num_classes, self.use_batch_norm)

        # Classifier
        self.pool3 = nn.AdaptiveAvgPool2d(1)
        self.dropout = nn.Dropout(self.dropout_rate)
        self.fc = nn.Linear(2048, self.num_classes)

        # Initialisation
        self._initialize_weights()

    def _initialize_weights(self):
        """Initialise les poids du modèle"""
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.xavier_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, 0, 0.01)
                nn.init.zeros_(m.bias)

    def forward(self, x):
        # Stem
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu1(x)

        x = self.conv2(x)
        x = self.bn2(x)
        x = self.relu2(x)

        x = self.conv3(x)
        x = self.bn3(x)
        x = self.relu3(x)

        x = self.pool1(x)

        x = self.conv4(x)
        x = self.bn4(x)
        x = self.relu4(x)

        x = self.conv5(x)
        x = self.bn5(x)
        x = self.relu5(x)

        x = self.pool2(x)

        # Inception modules
        x = self.inception_a1(x)
        x = self.inception_a2(x)
        x = self.inception_a3(x)

        aux_output = None
        if self.aux_logits and self.training:
            aux_output = self.aux_logits_layer(x)

        x = self.inception_b1(x)
        x = self.inception_c1(x)
        x = self.inception_c2(x)
        x = self.inception_c3(x)
        x = self.inception_c4(x)

        x = self.inception_d1(x)
        x = self.inception_e1(x)
        x = self.inception_e2(x)

        # Classifier
        x = self.pool3(x)
        x = x.view(x.size(0), -1)
        x = self.dropout(x)
        x = self.fc(x)

        if self.aux_logits and self.training:
            return x, aux_output
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
        x = self.relu1(x)
        features.append(x)

        x = self.conv2(x)
        x = self.bn2(x)
        x = self.relu2(x)
        features.append(x)

        x = self.conv3(x)
        x = self.bn3(x)
        x = self.relu3(x)
        features.append(x)

        x = self.pool1(x)
        x = self.conv4(x)
        x = self.bn4(x)
        x = self.relu4(x)
        features.append(x)

        x = self.conv5(x)
        x = self.bn5(x)
        x = self.relu5(x)
        features.append(x)

        x = self.pool2(x)
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
            'aux_logits': self.aux_logits,
            'version': self.config.version,
            'input_size': self.config.input_size,
            'input_channels': self.config.input_channels,
            'num_classes': self.config.num_classes,
        }


def create_inception(
    version: str = 'v3',
    num_classes: int = 1000,
    input_channels: int = 3,
    aux_logits: bool = True,
    **kwargs
) -> Inception:
    """
    Factory pour créer des modèles Inception.

    Args:
        version: Version ('v1', 'v2', 'v3', 'v4')
        num_classes: Nombre de classes
        input_channels: Canaux d'entrée
        aux_logits: Utiliser les logits auxiliaires
        **kwargs: Arguments supplémentaires

    Returns:
        Inception: Instance du modèle

    Example:
        ```python
        # Inception V3 pour classification financière
        model = create_inception(
            version='v3',
            num_classes=10,
            input_channels=3
        )

        # Inception V4 sans aux logits
        model = create_inception(
            version='v4',
            num_classes=5,
            input_channels=1,
            aux_logits=False
        )
        ```
    """
    config = InceptionConfig(
        version=version,
        num_classes=num_classes,
        input_channels=input_channels,
        aux_logits=aux_logits,
        **kwargs
    )
    return Inception(config)


__all__ = [
    'Inception',
    'InceptionConfig',
    'create_inception',
]
