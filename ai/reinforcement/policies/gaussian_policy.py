
# ai/reinforcement/policies/gaussian_policy.py
"""
NEXUS AI TRADING SYSTEM - Gaussian Policy for Reinforcement Learning
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
    from torch.distributions import Normal
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class GaussianPolicyConfig:
    """Configuration pour Gaussian Policy"""
    state_dim: int = 10
    action_dim: int = 3
    hidden_dim: int = 256
    dropout: float = 0.1
    log_std_min: float = -20.0
    log_std_max: float = 2.0
    use_state_dependent_std: bool = True
    use_action_scaling: bool = True
    max_action: float = 1.0
    min_action: float = -1.0
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
            'log_std_min': self.log_std_min,
            'log_std_max': self.log_std_max,
            'use_state_dependent_std': self.use_state_dependent_std,
            'use_action_scaling': self.use_action_scaling,
            'max_action': self.max_action,
            'min_action': self.min_action,
            'use_gpu': self.use_gpu,
        }


class _GaussianPolicyNetwork(nn.Module):
    """Réseau de politique gaussienne"""

    def __init__(self, config: GaussianPolicyConfig):
        super().__init__()

        self.config = config
        self.action_dim = config.action_dim
        self.log_std_min = config.log_std_min
        self.log_std_max = config.log_std_max
        self.use_state_dependent_std = config.use_state_dependent_std
        self.use_action_scaling = config.use_action_scaling
        self.max_action = config.max_action
        self.min_action = config.min_action

        # Couches partagées
        self.fc1 = nn.Linear(config.state_dim, config.hidden_dim)
        self.fc2 = nn.Linear(config.hidden_dim, config.hidden_dim)
        self.dropout = nn.Dropout(config.dropout)

        # Moyenne
        self.mean = nn.Linear(config.hidden_dim, config.action_dim)

        # Log-écart-type
        if config.use_state_dependent_std:
            self.log_std = nn.Linear(config.hidden_dim, config.action_dim)
        else:
            self.log_std = nn.Parameter(torch.zeros(1, config.action_dim))

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = F.relu(self.fc2(x))
        x = self.dropout(x)

        mean = self.mean(x)

        if self.use_state_dependent_std:
            log_std = self.log_std(x)
        else:
            log_std = self.log_std.expand_as(mean)

        log_std = torch.clamp(log_std, self.log_std_min, self.log_std_max)
        std = torch.exp(log_std)

        return mean, std

    def get_action(
        self,
        state: torch.Tensor,
        deterministic: bool = False
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Sélectionne une action selon la politique.

        Args:
            state: État
            deterministic: Action déterministe

        Returns:
            Tuple[torch.Tensor, torch.Tensor]: (Action, Log-probabilité)
        """
        mean, std = self.forward(state)
        dist = Normal(mean, std)

        if deterministic:
            action = mean
        else:
            action = dist.rsample()

        if self.use_action_scaling:
            # Tanh pour contraindre l'action dans [-1, 1]
            action = torch.tanh(action)
            action = action * (self.max_action - self.min_action) / 2 + (self.max_action + self.min_action) / 2
            action = torch.clamp(action, self.min_action, self.max_action)

            # Correction du log-prob (jacobian du tanh)
            log_prob = dist.log_prob(mean).sum(dim=-1, keepdim=True)
            log_prob -= torch.log(self.max_action - self.min_action + 1e-6).sum(dim=-1, keepdim=True)
            log_prob -= torch.log(1 - (2 * (action - self.min_action) / (self.max_action - self.min_action) - 1).pow(2) + 1e-6).sum(dim=-1, keepdim=True)
        else:
            log_prob = dist.log_prob(action).sum(dim=-1, keepdim=True)

        return action, log_prob

    def evaluate(
        self,
        state: torch.Tensor,
        action: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Évalue une action selon la politique.

        Args:
            state: État
            action: Action

        Returns:
            Tuple[torch.Tensor, torch.Tensor]: (Log-probabilité, Entropie)
        """
        mean, std = self.forward(state)
        dist = Normal(mean, std)

        log_prob = dist.log_prob(action).sum(dim=-1, keepdim=True)
        entropy = dist.entropy().sum(dim=-1, keepdim=True)

        return log_prob, entropy


class GaussianPolicy:
    """
    Politique gaussienne pour les espaces d'actions continus.

    Features:
    - Gaussian distribution over actions
    - State-dependent or fixed std
    - Action scaling with tanh
    - Entropy computation
    - Log-probability correction

    Example:
        ```python
        config = GaussianPolicyConfig(
            state_dim=10,
            action_dim=3,
            hidden_dim=256,
            use_state_dependent_std=True
        )
        policy = GaussianPolicy(config)

        # Select action
        state = env.reset()
        action, log_prob = policy.select_action(state)

        # Evaluate action
        log_prob, entropy = policy.evaluate(state, action)
        ```
    """

    def __init__(self, config: Optional[GaussianPolicyConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis")

        self.config = config or GaussianPolicyConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.network = _GaussianPolicyNetwork(self.config).to(self.device)

        logger.info(f"GaussianPolicy initialisé sur {self.device}")

    def select_action(
        self,
        state: Union[np.ndarray, torch.Tensor],
        deterministic: bool = False,
        return_log_prob: bool = True
    ) -> Union[np.ndarray, Tuple[np.ndarray, float]]:
        """
        Sélectionne une action selon la politique.

        Args:
            state: État actuel
            deterministic: Action déterministe
            return_log_prob: Retourner la log-probabilité

        Returns:
            Union[np.ndarray, Tuple[np.ndarray, float]]: Action et optionnellement log-probabilité
        """
        if isinstance(state, np.ndarray):
            state = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            action, log_prob = self.network.get_action(state, deterministic)

        action = action.cpu().numpy().flatten()
        log_prob = log_prob.item() if return_log_prob else 0.0

        if return_log_prob:
            return action, log_prob
        return action

    def evaluate(
        self,
        state: Union[np.ndarray, torch.Tensor],
        action: Union[np.ndarray, torch.Tensor]
    ) -> Tuple[float, float]:
        """
        Évalue une action selon la politique.

        Args:
            state: État
            action: Action

        Returns:
            Tuple[float, float]: (Log-probabilité, Entropie)
        """
        if isinstance(state, np.ndarray):
            state = torch.FloatTensor(state).to(self.device)

        if isinstance(action, np.ndarray):
            action = torch.FloatTensor(action).to(self.device)

        if state.dim() == 1:
            state = state.unsqueeze(0)
        if action.dim() == 1:
            action = action.unsqueeze(0)

        with torch.no_grad():
            log_prob, entropy = self.network.evaluate(state, action)

        return log_prob.mean().item(), entropy.mean().item()

    def get_mean_std(
        self,
        state: Union[np.ndarray, torch.Tensor]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Retourne la moyenne et l'écart-type de la distribution.

        Args:
            state: État

        Returns:
            Tuple[np.ndarray, np.ndarray]: (Moyenne, Écart-type)
        """
        if isinstance(state, np.ndarray):
            state = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            mean, std = self.network.forward(state)

        return mean.cpu().numpy().flatten(), std.cpu().numpy().flatten()

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
            'use_state_dependent_std': self.config.use_state_dependent_std,
            'log_std_min': self.config.log_std_min,
            'log_std_max': self.config.log_std_max,
            'use_action_scaling': self.config.use_action_scaling,
            'max_action': self.config.max_action,
            'min_action': self.config.min_action,
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
    def load(cls, filepath: str) -> 'GaussianPolicy':
        """
        Charge une politique.

        Args:
            filepath: Chemin du fichier

        Returns:
            GaussianPolicy: Politique chargée
        """
        try:
            import pickle

            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = GaussianPolicyConfig(**data['config'])
            policy = cls(config)

            policy.network.load_state_dict(data['network_state_dict'])

            logger.info(f"Politique chargée: {filepath}")
            return policy

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_gaussian_policy(
    state_dim: int = 10,
    action_dim: int = 3,
    hidden_dim: int = 256,
    max_action: float = 1.0,
    **kwargs
) -> GaussianPolicy:
    """
    Factory pour créer une politique gaussienne.

    Args:
        state_dim: Dimension de l'état
        action_dim: Dimension de l'action
        hidden_dim: Dimension cachée
        max_action: Action maximale
        **kwargs: Arguments supplémentaires

    Returns:
        GaussianPolicy: Politique gaussienne
    """
    config = GaussianPolicyConfig(
        state_dim=state_dim,
        action_dim=action_dim,
        hidden_dim=hidden_dim,
        max_action=max_action,
        **kwargs
    )
    return GaussianPolicy(config)


__all__ = [
    'GaussianPolicy',
    'GaussianPolicyConfig',
    'create_gaussian_policy',
]
