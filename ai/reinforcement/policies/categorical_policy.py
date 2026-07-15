# ai/reinforcement/policies/categorical_policy.py 
"""
NEXUS AI TRADING SYSTEM - Categorical Policy for Reinforcement Learning
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
    from torch.distributions import Categorical
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class CategoricalPolicyConfig:
    """Configuration pour Categorical Policy"""
    state_dim: int = 10
    action_dim: int = 3
    hidden_dim: int = 256
    dropout: float = 0.1
    use_softmax: bool = True
    temperature: float = 1.0
    use_entropy_bonus: bool = True
    entropy_coef: float = 0.01
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
            'use_softmax': self.use_softmax,
            'temperature': self.temperature,
            'use_entropy_bonus': self.use_entropy_bonus,
            'entropy_coef': self.entropy_coef,
            'use_gpu': self.use_gpu,
        }


class _CategoricalPolicyNetwork(nn.Module):
    """Réseau de politique catégorielle"""

    def __init__(self, config: CategoricalPolicyConfig):
        super().__init__()

        self.config = config
        self.action_dim = config.action_dim
        self.temperature = config.temperature

        self.fc1 = nn.Linear(config.state_dim, config.hidden_dim)
        self.fc2 = nn.Linear(config.hidden_dim, config.hidden_dim)
        self.dropout = nn.Dropout(config.dropout)
        self.output = nn.Linear(config.hidden_dim, config.action_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = F.relu(self.fc2(x))
        x = self.dropout(x)
        logits = self.output(x)

        if self.temperature != 1.0:
            logits = logits / self.temperature

        return logits


class CategoricalPolicy:
    """
    Politique catégorielle pour les espaces d'actions discrets.

    Features:
    - Softmax distribution over actions
    - Temperature scaling
    - Entropy bonus
    - Exploration control
    - Batch processing

    Example:
        ```python
        config = CategoricalPolicyConfig(
            state_dim=10,
            action_dim=3,
            hidden_dim=256,
            temperature=1.0
        )
        policy = CategoricalPolicy(config)

        # Select action
        state = env.reset()
        action, log_prob = policy.select_action(state)

        # Evaluate action
        log_prob, entropy = policy.evaluate(state, action)
        ```
    """

    def __init__(self, config: Optional[CategoricalPolicyConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis")

        self.config = config or CategoricalPolicyConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')
        self.network = _CategoricalPolicyNetwork(self.config).to(self.device)

        logger.info(f"CategoricalPolicy initialisé sur {self.device}")

    def _get_distribution(self, state: torch.Tensor) -> Categorical:
        """Retourne la distribution catégorielle"""
        logits = self.network(state)

        if not self.config.use_softmax:
            # Logits directs
            return Categorical(logits=logits)

        # Avec softmax
        probs = F.softmax(logits, dim=-1)
        return Categorical(probs=probs)

    def select_action(
        self,
        state: Union[np.ndarray, torch.Tensor],
        deterministic: bool = False,
        return_log_prob: bool = True
    ) -> Union[int, Tuple[int, float]]:
        """
        Sélectionne une action selon la politique.

        Args:
            state: État actuel
            deterministic: Action déterministe
            return_log_prob: Retourner la log-probabilité

        Returns:
            Union[int, Tuple[int, float]]: Action et optionnellement log-probabilité
        """
        if isinstance(state, np.ndarray):
            state = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            if deterministic:
                logits = self.network(state)
                action = torch.argmax(logits, dim=-1).item()
                if return_log_prob:
                    return action, 0.0
                return action

            dist = self._get_distribution(state)
            action = dist.sample()

            if return_log_prob:
                log_prob = dist.log_prob(action).item()
                return action.item(), log_prob

            return action.item()

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
        dist = self._get_distribution(state)
        log_prob = dist.log_prob(action)

        if self.config.use_entropy_bonus:
            entropy = dist.entropy()
        else:
            entropy = torch.zeros_like(log_prob)

        return log_prob, entropy

    def get_action_probs(
        self,
        state: Union[np.ndarray, torch.Tensor]
    ) -> np.ndarray:
        """
        Retourne les probabilités des actions.

        Args:
            state: État

        Returns:
            np.ndarray: Probabilités des actions
        """
        if isinstance(state, np.ndarray):
            state = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.network(state)
            probs = F.softmax(logits, dim=-1)

        return probs.cpu().numpy().flatten()

    def get_logits(
        self,
        state: Union[np.ndarray, torch.Tensor]
    ) -> np.ndarray:
        """
        Retourne les logits des actions.

        Args:
            state: État

        Returns:
            np.ndarray: Logits des actions
        """
        if isinstance(state, np.ndarray):
            state = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.network(state)

        return logits.cpu().numpy().flatten()

    def set_temperature(self, temperature: float):
        """
        Modifie la température de la politique.

        Args:
            temperature: Nouvelle température
        """
        self.config.temperature = temperature
        self.network.temperature = temperature
        logger.info(f"Temperature modifiée: {temperature}")

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
            'temperature': self.config.temperature,
            'action_dim': self.config.action_dim,
            'use_entropy_bonus': self.config.use_entropy_bonus,
            'entropy_coef': self.config.entropy_coef,
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
    def load(cls, filepath: str) -> 'CategoricalPolicy':
        """
        Charge une politique.

        Args:
            filepath: Chemin du fichier

        Returns:
            CategoricalPolicy: Politique chargée
        """
        try:
            import pickle

            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = CategoricalPolicyConfig(**data['config'])
            policy = cls(config)

            policy.network.load_state_dict(data['network_state_dict'])

            logger.info(f"Politique chargée: {filepath}")
            return policy

        except Exception as e:
            logger.error(f"Erreur de chargement: {e}")
            raise


def create_categorical_policy(
    state_dim: int = 10,
    action_dim: int = 3,
    hidden_dim: int = 256,
    temperature: float = 1.0,
    **kwargs
) -> CategoricalPolicy:
    """
    Factory pour créer une politique catégorielle.

    Args:
        state_dim: Dimension de l'état
        action_dim: Dimension de l'action
        hidden_dim: Dimension cachée
        temperature: Température de la politique
        **kwargs: Arguments supplémentaires

    Returns:
        CategoricalPolicy: Politique catégorielle
    """
    config = CategoricalPolicyConfig(
        state_dim=state_dim,
        action_dim=action_dim,
        hidden_dim=hidden_dim,
        temperature=temperature,
        **kwargs
    )
    return CategoricalPolicy(config)


__all__ = [
    'CategoricalPolicy',
    'CategoricalPolicyConfig',
    'create_categorical_policy',
]
