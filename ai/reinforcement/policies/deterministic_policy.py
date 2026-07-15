
# ai/reinforcement/policies/deterministic_policy.py
"""
NEXUS AI TRADING SYSTEM - Deterministic Policy for Reinforcement Learning
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
class DeterministicPolicyConfig:
    """Configuration pour Deterministic Policy"""
    state_dim: int = 10
    action_dim: int = 3
    hidden_dim: int = 256
    dropout: float = 0.1
    max_action: float = 1.0
    min_action: float = -1.0
    use_action_scaling: bool = True
    use_layer_norm: bool = False
    use_batch_norm: bool = False
    activation: str = 'relu'
    use_gpu: bool = False

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'state_dim': self.state_dim,
            'action_dim': self.action_dim,
            'hidden_dim': self.hidden_dim,
            'dropout': self.dropout,
            'max_action': self.max_action,
            'min_action': self.min_action,
            'use_action_scaling': self.use_action_scaling,
            'use_layer_norm': self.use_layer_norm,
            'use_batch_norm': self.use_batch_norm,
            'activation': self.activation,
            'use_gpu': self.use_gpu,
        }


class _DeterministicPolicyNetwork(nn.Module):
    """Réseau de politique déterministe"""

    def __init__(self, config: DeterministicPolicyConfig):
        super().__init__()

        self.config = config
        self.action_dim = config.action_dim
        self.max_action = config.max_action
        self.min_action = config.min_action
        self.use_action_scaling = config.use_action_scaling

        # Couches
        self.fc1 = nn.Linear(config.state_dim, config.hidden_dim)

        if config.use_layer_norm:
            self.ln1 = nn.LayerNorm(config.hidden_dim)
        else:
            self.ln1 = nn.Identity()

        if config.use_batch_norm:
            self.bn1 = nn.BatchNorm1d(config.hidden_dim)
        else:
            self.bn1 = nn.Identity()

        self.fc2 = nn.Linear(config.hidden_dim, config.hidden_dim)

        if config.use_layer_norm:
            self.ln2 = nn.LayerNorm(config.hidden_dim)
        else:
            self.ln2 = nn.Identity()

        if config.use_batch_norm:
            self.bn2 = nn.BatchNorm1d(config.hidden_dim)
        else:
            self.bn2 = nn.Identity()

        self.dropout = nn.Dropout(config.dropout)
        self.output = nn.Linear(config.hidden_dim, config.action_dim)

        # Activation
        if config.activation == 'relu':
            self.activation = nn.ReLU()
        elif config.activation == 'swish':
            self.activation = nn.SiLU()
        elif config.activation == 'gelu':
            self.activation = nn.GELU()
        else:
            self.activation = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.fc1(x)
        x = self.ln1(x)
        x = self.bn1(x)
        x = self.activation(x)
        x = self.dropout(x)

        x = self.fc2(x)
        x = self.ln2(x)
        x = self.bn2(x)
        x = self.activation(x)
        x = self.dropout(x)

        action = self.output(x)

        if self.use_action_scaling:
            action = torch.tanh(action)
            action = action * (self.max_action - self.min_action) / 2 + (self.max_action + self.min_action) / 2
            action = torch.clamp(action, self.min_action, self.max_action)

        return action


class DeterministicPolicy:
    """
    Politique déterministe pour les espaces d'actions continus.

    Features:
    - Deterministic policy output
    - Action scaling
    - Layer and batch normalization
    - Multiple activation functions
    - Batch processing

    Example:
        ```python
        config = DeterministicPolicyConfig(
            state_dim=10,
            action_dim=3,
            hidden_dim=256,
            max_action=1.0
        )
        policy = DeterministicPolicy(config)

        # Select action
        state = env.reset()
        action = policy.select_action(state)

        # With exploration noise
        action = policy.select_action(state, noise_scale=0.1)
        ```
    """

    def __init__(self, config: Optional[DeterministicPolicyConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis")

        self.config = config or DeterministicPolicyConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.network = _DeterministicPolicyNetwork(self.config).to(self.device)

        logger.info(f"DeterministicPolicy initialisé sur {self.device}")

    def select_action(
        self,
        state: Union[np.ndarray, torch.Tensor],
        noise_scale: float = 0.0,
        noise_clip: Optional[float] = None
    ) -> np.ndarray:
        """
        Sélectionne une action selon la politique.

        Args:
            state: État actuel
            noise_scale: Échelle du bruit d'exploration
            noise_clip: Limite du bruit

        Returns:
            np.ndarray: Action
        """
        if isinstance(state, np.ndarray):
            state = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            action = self.network(state).cpu().numpy().flatten()

        if noise_scale > 0:
            noise = np.random.normal(0, noise_scale, size=action.shape)
            if noise_clip is not None:
                noise = np.clip(noise, -noise_clip, noise_clip)
            action = action + noise
            action = np.clip(action, self.config.min_action, self.config.max_action)

        return action

    def get_action_batch(
        self,
        states: Union[np.ndarray, torch.Tensor]
    ) -> np.ndarray:
        """
        Sélectionne des actions pour un batch d'états.

        Args:
            states: Batch d'états

        Returns:
            np.ndarray: Actions
        """
        if isinstance(states, np.ndarray):
            states = torch.FloatTensor(states).to(self.device)

        with torch.no_grad():
            actions = self.network(states).cpu().numpy()

        return actions

    def get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres de la politique"""
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        """Retourne les métriques de la politique"""
        total_params = sum(p.numel() for p in self.network.parameters())
        trainable_params = sum(p.numel() for p in self.network.parameters() if p.requires_grad)

        return {
            'total_parameters': total_params,
            'trainable_parameters': trainable_params,
            'device': str(self.device),
            'action_dim': self.config.action_dim,
            'max_action': self.config.max_action,
            'min_action': self.config.min_action,
            'use_action_scaling': self.config.use_action_scaling,
            'use_layer_norm': self.config.use_layer_norm,
            'use_batch_norm': self.config.use_batch_norm,
            'activation': self.config.activation,
        }

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde la politique.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si la sauvegarde a réussi
        """
        try:
            import os
            import pickle
            from datetime import datetime

            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'network_state_dict': self.network.state_dict(),
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Politique sauvegardée: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'DeterministicPolicy':
        """
        Charge une politique.

        Args:
            filepath: Chemin du fichier

        Returns:
            DeterministicPolicy: Politique chargée
        """
        try:
            import pickle

            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = DeterministicPolicyConfig(**data['config'])
            policy = cls(config)

            policy.network.load_state_dict(data['network_state_dict'])

            logger.info(f"Politique chargée: {filepath}")
            return policy

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_deterministic_policy(
    state_dim: int = 10,
    action_dim: int = 3,
    hidden_dim: int = 256,
    max_action: float = 1.0,
    **kwargs
) -> DeterministicPolicy:
    """
    Factory pour créer une politique déterministe.

    Args:
        state_dim: Dimension de l'état
        action_dim: Dimension de l'action
        hidden_dim: Dimension cachée
        max_action: Action maximale
        **kwargs: Arguments supplémentaires

    Returns:
        DeterministicPolicy: Politique déterministe
    """
    config = DeterministicPolicyConfig(
        state_dim=state_dim,
        action_dim=action_dim,
        hidden_dim=hidden_dim,
        max_action=max_action,
        **kwargs
    )
    return DeterministicPolicy(config)


__all__ = [
    'DeterministicPolicy',
    'DeterministicPolicyConfig',
    'create_deterministic_policy',
]
