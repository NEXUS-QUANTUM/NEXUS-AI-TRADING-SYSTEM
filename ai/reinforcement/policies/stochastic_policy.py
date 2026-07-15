
# ai/reinforcement/policies/stochastic_policy.py
"""
NEXUS AI TRADING SYSTEM - Stochastic Policy for Reinforcement Learning
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
    from torch.distributions import Categorical, Normal, Bernoulli
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class StochasticPolicyConfig:
    """Configuration pour Stochastic Policy"""
    state_dim: int = 10
    action_dim: int = 3
    hidden_dim: int = 256
    dropout: float = 0.1
    policy_type: str = 'categorical'  # 'categorical', 'gaussian', 'bernoulli'
    temperature: float = 1.0
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
            'policy_type': self.policy_type,
            'temperature': self.temperature,
            'log_std_min': self.log_std_min,
            'log_std_max': self.log_std_max,
            'use_state_dependent_std': self.use_state_dependent_std,
            'use_action_scaling': self.use_action_scaling,
            'max_action': self.max_action,
            'min_action': self.min_action,
            'use_gpu': self.use_gpu,
        }


class _StochasticPolicyNetwork(nn.Module):
    """Réseau de politique stochastique"""

    def __init__(self, config: StochasticPolicyConfig):
        super().__init__()

        self.config = config
        self.policy_type = config.policy_type
        self.action_dim = config.action_dim
        self.temperature = config.temperature
        self.log_std_min = config.log_std_min
        self.log_std_max = config.log_std_max

        # Couches partagées
        self.fc1 = nn.Linear(config.state_dim, config.hidden_dim)
        self.fc2 = nn.Linear(config.hidden_dim, config.hidden_dim)
        self.dropout = nn.Dropout(config.dropout)

        if policy_type == 'categorical':
            self.output = nn.Linear(config.hidden_dim, config.action_dim)
        elif policy_type == 'gaussian':
            self.mean = nn.Linear(config.hidden_dim, config.action_dim)
            if config.use_state_dependent_std:
                self.log_std = nn.Linear(config.hidden_dim, config.action_dim)
            else:
                self.log_std = nn.Parameter(torch.zeros(1, config.action_dim))
        elif policy_type == 'bernoulli':
            self.output = nn.Linear(config.hidden_dim, config.action_dim)
        else:
            raise ValueError(f"Type de politique non supporté: {policy_type}")

    def forward(self, x: torch.Tensor) -> Any:
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = F.relu(self.fc2(x))
        x = self.dropout(x)

        if self.policy_type == 'categorical':
            logits = self.output(x)
            if self.temperature != 1.0:
                logits = logits / self.temperature
            return Categorical(logits=logits)

        elif self.policy_type == 'gaussian':
            mean = self.mean(x)
            if self.config.use_state_dependent_std:
                log_std = self.log_std(x)
            else:
                log_std = self.log_std.expand_as(mean)
            log_std = torch.clamp(log_std, self.log_std_min, self.log_std_max)
            std = torch.exp(log_std)
            return Normal(mean, std)

        elif self.policy_type == 'bernoulli':
            logits = self.output(x)
            return Bernoulli(logits=logits)

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
        dist = self.forward(state)

        if deterministic:
            if self.policy_type == 'categorical':
                action = torch.argmax(dist.logits, dim=-1)
            elif self.policy_type == 'gaussian':
                action = dist.mean
            else:  # bernoulli
                action = (dist.probs > 0.5).int()
        else:
            action = dist.sample()

        log_prob = dist.log_prob(action)
        if self.policy_type == 'gaussian':
            log_prob = log_prob.sum(dim=-1, keepdim=True)
        elif self.policy_type == 'bernoulli':
            log_prob = log_prob.sum(dim=-1, keepdim=True)

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
        dist = self.forward(state)

        log_prob = dist.log_prob(action)
        if self.policy_type == 'gaussian':
            log_prob = log_prob.sum(dim=-1, keepdim=True)
        elif self.policy_type == 'bernoulli':
            log_prob = log_prob.sum(dim=-1, keepdim=True)

        entropy = dist.entropy()
        if self.policy_type == 'gaussian':
            entropy = entropy.sum(dim=-1, keepdim=True)
        elif self.policy_type == 'bernoulli':
            entropy = entropy.sum(dim=-1, keepdim=True)

        return log_prob, entropy


class StochasticPolicy:
    """
    Politique stochastique pour les espaces d'actions discrets et continus.

    Features:
    - Multiple policy types (categorical, gaussian, bernoulli)
    - Stochastic sampling
    - Entropy computation
    - Temperature scaling
    - Deterministic option

    Example:
        ```python
        config = StochasticPolicyConfig(
            state_dim=10,
            action_dim=3,
            policy_type='categorical',
            temperature=1.0
        )
        policy = StochasticPolicy(config)

        # Select action
        state = env.reset()
        action, log_prob = policy.select_action(state)

        # Evaluate action
        log_prob, entropy = policy.evaluate(state, action)
        ```
    """

    def __init__(self, config: Optional[StochasticPolicyConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis")

        self.config = config or StochasticPolicyConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.network = _StochasticPolicyNetwork(self.config).to(self.device)

        logger.info(f"StochasticPolicy initialisé sur {self.device}")

    def select_action(
        self,
        state: Union[np.ndarray, torch.Tensor],
        deterministic: bool = False,
        return_log_prob: bool = True
    ) -> Union[Any, Tuple[Any, float]]:
        """
        Sélectionne une action selon la politique.

        Args:
            state: État actuel
            deterministic: Action déterministe
            return_log_prob: Retourner la log-probabilité

        Returns:
            Union[Any, Tuple[Any, float]]: Action et optionnellement log-probabilité
        """
        if isinstance(state, np.ndarray):
            state = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            action, log_prob = self.network.get_action(state, deterministic)

        action = action.cpu().numpy()
        if self.config.policy_type == 'categorical' or self.config.policy_type == 'bernoulli':
            action = int(action)

        if return_log_prob:
            return action, log_prob.item()

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

        if isinstance(action, (int, np.integer)):
            action = torch.tensor([action]).to(self.device)
        elif isinstance(action, np.ndarray):
            action = torch.FloatTensor(action).to(self.device)

        if state.dim() == 1:
            state = state.unsqueeze(0)
        if action.dim() == 1 and self.config.policy_type != 'categorical':
            action = action.unsqueeze(0)

        with torch.no_grad():
            log_prob, entropy = self.network.evaluate(state, action)

        return log_prob.mean().item(), entropy.mean().item()

    def get_action_probs(
        self,
        state: Union[np.ndarray, torch.Tensor]
    ) -> np.ndarray:
        """
        Retourne les probabilités des actions (pour catégorielle).

        Args:
            state: État

        Returns:
            np.ndarray: Probabilités des actions
        """
        if self.config.policy_type != 'categorical':
            raise ValueError("get_action_probs n'est disponible que pour categorical")

        if isinstance(state, np.ndarray):
            state = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            dist = self.network.forward(state)
            probs = F.softmax(dist.logits, dim=-1)

        return probs.cpu().numpy().flatten()

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
            'policy_type': self.config.policy_type,
            'temperature': self.config.temperature,
            'action_dim': self.config.action_dim,
            'use_state_dependent_std': self.config.use_state_dependent_std,
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
    def load(cls, filepath: str) -> 'StochasticPolicy':
        """
        Charge une politique.

        Args:
            filepath: Chemin du fichier

        Returns:
            StochasticPolicy: Politique chargée
        """
        try:
            import pickle

            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = StochasticPolicyConfig(**data['config'])
            policy = cls(config)

            policy.network.load_state_dict(data['network_state_dict'])

            logger.info(f"Politique chargée: {filepath}")
            return policy

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_stochastic_policy(
    state_dim: int = 10,
    action_dim: int = 3,
    policy_type: str = 'categorical',
    temperature: float = 1.0,
    **kwargs
) -> StochasticPolicy:
    """
    Factory pour créer une politique stochastique.

    Args:
        state_dim: Dimension de l'état
        action_dim: Dimension de l'action
        policy_type: Type de politique ('categorical', 'gaussian', 'bernoulli')
        temperature: Température pour catégorielle
        **kwargs: Arguments supplémentaires

    Returns:
        StochasticPolicy: Politique stochastique
    """
    config = StochasticPolicyConfig(
        state_dim=state_dim,
        action_dim=action_dim,
        policy_type=policy_type,
        temperature=temperature,
        **kwargs
    )
    return StochasticPolicy(config)


__all__ = [
    'StochasticPolicy',
    'StochasticPolicyConfig',
    'create_stochastic_policy',
]
