# ai/models/reinforcement/sac_agent.py
"""
NEXUS AI TRADING SYSTEM - SAC (Soft Actor-Critic) Agent
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import os
import random
from collections import deque
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import torch.optim as optim
    from torch.distributions import Normal, TanhTransform, TransformedDistribution
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class SACConfig:
    state_dim: int = 10
    action_dim: int = 3
    hidden_dim: int = 256
    learning_rate: float = 0.0003
    alpha: float = 0.2
    gamma: float = 0.99
    tau: float = 0.005
    memory_size: int = 100000
    batch_size: int = 256
    use_gpu: bool = False
    target_entropy: Optional[float] = None
    learn_alpha: bool = True
    action_scale: float = 1.0
    action_bias: float = 0.0
    use_automatic_entropy_tuning: bool = True

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")
        if self.target_entropy is None:
            self.target_entropy = -self.action_dim

    def to_dict(self) -> Dict[str, Any]:
        return {
            'state_dim': self.state_dim,
            'action_dim': self.action_dim,
            'hidden_dim': self.hidden_dim,
            'learning_rate': self.learning_rate,
            'alpha': self.alpha,
            'gamma': self.gamma,
            'tau': self.tau,
            'memory_size': self.memory_size,
            'batch_size': self.batch_size,
            'use_gpu': self.use_gpu,
            'target_entropy': self.target_entropy,
            'learn_alpha': self.learn_alpha,
            'action_scale': self.action_scale,
            'action_bias': self.action_bias,
            'use_automatic_entropy_tuning': self.use_automatic_entropy_tuning,
        }


@dataclass
class SACResult:
    rewards: List[float]
    losses: List[float]
    alpha_values: List[float]
    q_values: List[float]
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    episodes: int = 0
    average_reward: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'rewards': self.rewards,
            'losses': self.losses,
            'alpha_values': self.alpha_values,
            'q_values': self.q_values,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
            'episodes': self.episodes,
            'average_reward': self.average_reward,
        }


class _SACNetwork(nn.Module):
    """Réseau SAC avec acteur et deux critiques"""

    def __init__(self, config: SACConfig):
        super().__init__()

        self.config = config
        self.action_dim = config.action_dim
        self.action_scale = config.action_scale
        self.action_bias = config.action_bias

        # Acteur
        self.actor_fc1 = nn.Linear(config.state_dim, config.hidden_dim)
        self.actor_fc2 = nn.Linear(config.hidden_dim, config.hidden_dim)
        self.mean = nn.Linear(config.hidden_dim, config.action_dim)
        self.log_std = nn.Linear(config.hidden_dim, config.action_dim)

        # Critiques Q1 et Q2
        self.q1_fc1 = nn.Linear(config.state_dim + config.action_dim, config.hidden_dim)
        self.q1_fc2 = nn.Linear(config.hidden_dim, config.hidden_dim)
        self.q1 = nn.Linear(config.hidden_dim, 1)

        self.q2_fc1 = nn.Linear(config.state_dim + config.action_dim, config.hidden_dim)
        self.q2_fc2 = nn.Linear(config.hidden_dim, config.hidden_dim)
        self.q2 = nn.Linear(config.hidden_dim, 1)

        # Critiques cibles
        self.q1_target = nn.Linear(config.hidden_dim, 1)
        self.q2_target = nn.Linear(config.hidden_dim, 1)

    def forward(self, state, action):
        q1 = F.relu(self.q1_fc1(torch.cat([state, action], dim=1)))
        q1 = F.relu(self.q1_fc2(q1))
        q1 = self.q1(q1)

        q2 = F.relu(self.q2_fc1(torch.cat([state, action], dim=1)))
        q2 = F.relu(self.q2_fc2(q2))
        q2 = self.q2(q2)

        return q1, q2

    def get_action(self, state, deterministic=False):
        x = F.relu(self.actor_fc1(state))
        x = F.relu(self.actor_fc2(x))

        mean = self.mean(x)
        log_std = self.log_std(x)
        log_std = torch.clamp(log_std, -20, 2)

        std = torch.exp(log_std)
        dist = Normal(mean, std)

        if deterministic:
            action = mean
        else:
            action = dist.rsample()

        # Transformation tanh pour limiter l'action à [-1, 1]
        action = torch.tanh(action)
        action = action * self.action_scale + self.action_bias

        # Log probabilité avec correction tanh
        log_prob = dist.log_prob(mean).sum(dim=-1, keepdim=True)
        log_prob -= torch.log(self.action_scale * (1 - action.pow(2)) + 1e-6).sum(dim=-1, keepdim=True)

        return action, log_prob

    def evaluate(self, state, action):
        q1, q2 = self.forward(state, action)
        return q1, q2


class _ReplayBuffer:
    """Mémoire de rejeu standard pour SAC"""

    def __init__(self, capacity: int):
        self.buffer = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int):
        batch = random.sample(self.buffer, batch_size)
        return list(zip(*batch))

    def __len__(self):
        return len(self.buffer)


class SACAgent:
    """
    SAC (Soft Actor-Critic) Agent for reinforcement learning.

    This implementation supports:
    - Continuous action spaces
    - Automatic entropy tuning
    - Double Q-learning
    - Soft target updates
    - GPU acceleration

    Example:
        ```python
        config = SACConfig(
            state_dim=10,
            action_dim=3,
            hidden_dim=256,
            learning_rate=0.0003,
            memory_size=100000
        )
        agent = SACAgent(config)

        # Training loop
        for episode in range(episodes):
            state = env.reset()
            done = False
            while not done:
                action = agent.select_action(state)
                next_state, reward, done = env.step(action)
                agent.store_transition(state, action, reward, next_state, done)
                agent.update()
                state = next_state
        ```
    """

    def __init__(self, config: Optional[SACConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis. Installez avec: pip install torch")

        self.config = config or SACConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')

        # Réseaux
        self.actor = _SACNetwork(self.config).to(self.device)
        self.q1, self.q2 = self.actor.q1, self.actor.q2
        self.q1_target, self.q2_target = self.actor.q1_target, self.actor.q2_target

        # Initialiser les cibles
        self._update_target_networks(tau=1.0)

        # Optimiseurs
        self.actor_optimizer = optim.Adam(
            list(self.actor.actor_fc1.parameters()) +
            list(self.actor.actor_fc2.parameters()) +
            list(self.actor.mean.parameters()) +
            list(self.actor.log_std.parameters()),
            lr=self.config.learning_rate
        )

        self.q1_optimizer = optim.Adam(
            list(self.actor.q1_fc1.parameters()) +
            list(self.actor.q1_fc2.parameters()) +
            list(self.actor.q1.parameters()),
            lr=self.config.learning_rate
        )

        self.q2_optimizer = optim.Adam(
            list(self.actor.q2_fc1.parameters()) +
            list(self.actor.q2_fc2.parameters()) +
            list(self.actor.q2.parameters()),
            lr=self.config.learning_rate
        )

        # Entropie
        if self.config.use_automatic_entropy_tuning:
            self.target_entropy = self.config.target_entropy
            self.log_alpha = torch.zeros(1, requires_grad=True, device=self.device)
            self.alpha_optimizer = optim.Adam([self.log_alpha], lr=self.config.learning_rate)
            self.alpha = self.log_alpha.exp().detach()
        else:
            self.alpha = torch.tensor(self.config.alpha, device=self.device)

        # Mémoire
        self.memory = _ReplayBuffer(self.config.memory_size)

        # Historique
        self.episode_rewards: List[float] = []
        self.losses: List[float] = []
        self.alpha_values: List[float] = []
        self.q_values: List[float] = []

        logger.info(f"SACAgent initialisé sur {self.device}")

    def _update_target_networks(self, tau: Optional[float] = None):
        """Met à jour les réseaux cibles"""
        if tau is None:
            tau = self.config.tau

        for target_param, param in zip(self.q1_target.parameters(), self.q1.parameters()):
            target_param.data.copy_(tau * param.data + (1 - tau) * target_param.data)

        for target_param, param in zip(self.q2_target.parameters(), self.q2.parameters()):
            target_param.data.copy_(tau * param.data + (1 - tau) * target_param.data)

    def select_action(self, state: np.ndarray, deterministic: bool = False) -> np.ndarray:
        """
        Sélectionne une action selon la politique actuelle.

        Args:
            state: État actuel
            deterministic: Action déterministe

        Returns:
            np.ndarray: Action
        """
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            action, _ = self.actor.get_action(state_tensor, deterministic)

        return action.cpu().numpy().flatten()

    def store_transition(self, state: np.ndarray, action: np.ndarray, reward: float, next_state: np.ndarray, done: bool):
        """
        Stocke une transition dans la mémoire.

        Args:
            state: État
            action: Action
            reward: Récompense
            next_state: État suivant
            done: Terminé ou non
        """
        self.memory.push(state, action, reward, next_state, done)

    def update(self) -> Dict[str, float]:
        """
        Met à jour les réseaux SAC.

        Returns:
            Dict[str, float]: Métriques d'entraînement
        """
        if len(self.memory) < self.config.batch_size:
            return {}

        # Échantillonner le batch
        states, actions, rewards, next_states, dones = self.memory.sample(self.config.batch_size)

        states = torch.FloatTensor(np.array(states)).to(self.device)
        actions = torch.FloatTensor(np.array(actions)).to(self.device)
        rewards = torch.FloatTensor(np.array(rewards)).unsqueeze(1).to(self.device)
        next_states = torch.FloatTensor(np.array(next_states)).to(self.device)
        dones = torch.FloatTensor(np.array(dones)).unsqueeze(1).to(self.device)

        # --- Mise à jour des Q-fonctions ---
        with torch.no_grad():
            next_actions, next_log_probs = self.actor.get_action(next_states)
            next_q1, next_q2 = self.q1_target(next_states), self.q2_target(next_states)
            next_q = torch.min(next_q1, next_q2) - self.alpha * next_log_probs
            target_q = rewards + (1 - dones) * self.config.gamma * next_q

        q1, q2 = self.actor.evaluate(states, actions)
        q1_loss = F.mse_loss(q1, target_q)
        q2_loss = F.mse_loss(q2, target_q)

        self.q1_optimizer.zero_grad()
        q1_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.actor.q1.parameters(), 1.0)
        self.q1_optimizer.step()

        self.q2_optimizer.zero_grad()
        q2_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.actor.q2.parameters(), 1.0)
        self.q2_optimizer.step()

        # --- Mise à jour de l'acteur ---
        new_actions, log_probs = self.actor.get_action(states)
        q1_new, q2_new = self.actor.evaluate(states, new_actions)
        q_new = torch.min(q1_new, q2_new)

        actor_loss = (self.alpha * log_probs - q_new).mean()

        self.actor_optimizer.zero_grad()
        actor_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.actor.parameters(), 1.0)
        self.actor_optimizer.step()

        # --- Mise à jour de l'entropie ---
        alpha_loss = None
        if self.config.use_automatic_entropy_tuning:
            alpha_loss = -(self.log_alpha * (log_probs + self.target_entropy).detach()).mean()

            self.alpha_optimizer.zero_grad()
            alpha_loss.backward()
            self.alpha_optimizer.step()

            self.alpha = self.log_alpha.exp().detach()

        # --- Mise à jour des cibles ---
        self._update_target_networks()

        # --- Métriques ---
        total_loss = q1_loss.item() + q2_loss.item() + actor_loss.item()
        if alpha_loss is not None:
            total_loss += alpha_loss.item()

        self.losses.append(total_loss)
        self.alpha_values.append(self.alpha.item())
        self.q_values.append(q_new.mean().item())

        return {
            'q1_loss': q1_loss.item(),
            'q2_loss': q2_loss.item(),
            'actor_loss': actor_loss.item(),
            'alpha_loss': alpha_loss.item() if alpha_loss is not None else 0.0,
            'total_loss': total_loss,
            'alpha': self.alpha.item(),
            'q_value': q_new.mean().item(),
        }

    def get_params(self) -> Dict[str, Any]:
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        metrics = {
            'is_trained': len(self.losses) > 0,
            'episodes': len(self.episode_rewards),
            'alpha': self.alpha.item() if torch.is_tensor(self.alpha) else self.alpha,
            'memory_size': len(self.memory),
            'device': str(self.device),
            'loss_history_length': len(self.losses),
            'reward_history_length': len(self.episode_rewards),
        }

        if self.episode_rewards:
            metrics['average_reward'] = np.mean(self.episode_rewards[-100:])
            metrics['best_reward'] = max(self.episode_rewards)
            metrics['worst_reward'] = min(self.episode_rewards)

        if self.losses:
            metrics['average_loss'] = np.mean(self.losses[-100:])
            metrics['final_loss'] = self.losses[-1]

        return metrics

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde l'agent SAC sur le disque.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si la sauvegarde a réussi
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'actor_state_dict': self.actor.state_dict(),
                'actor_optimizer_state_dict': self.actor_optimizer.state_dict(),
                'q1_optimizer_state_dict': self.q1_optimizer.state_dict(),
                'q2_optimizer_state_dict': self.q2_optimizer.state_dict(),
                'log_alpha': self.log_alpha.detach().cpu().numpy() if hasattr(self, 'log_alpha') else None,
                'alpha': self.alpha.detach().cpu().numpy() if torch.is_tensor(self.alpha) else self.alpha,
                'episode_rewards': self.episode_rewards,
                'losses': self.losses,
                'alpha_values': self.alpha_values,
                'q_values': self.q_values,
                'timestamp': datetime.now().isoformat(),
                'version': '1.0',
            }

            with open(filepath, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

            logger.info(f"Agent sauvegardé: {filepath}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            return False

    @classmethod
    def load(cls, filepath: str) -> 'SACAgent':
        """
        Charge un agent SAC depuis le disque.

        Args:
            filepath: Chemin du fichier

        Returns:
            SACAgent: Agent chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = SACConfig(**data['config'])
            agent = cls(config)

            agent.actor.load_state_dict(data['actor_state_dict'])
            agent.actor_optimizer.load_state_dict(data['actor_optimizer_state_dict'])
            agent.q1_optimizer.load_state_dict(data['q1_optimizer_state_dict'])
            agent.q2_optimizer.load_state_dict(data['q2_optimizer_state_dict'])

            if data.get('log_alpha') is not None:
                agent.log_alpha = torch.tensor(data['log_alpha'], device=agent.device, requires_grad=True)
                agent.alpha = agent.log_alpha.exp().detach()
            else:
                agent.alpha = torch.tensor(data.get('alpha', config.alpha), device=agent.device)

            agent.episode_rewards = data.get('episode_rewards', [])
            agent.losses = data.get('losses', [])
            agent.alpha_values = data.get('alpha_values', [])
            agent.q_values = data.get('q_values', [])

            logger.info(f"Agent chargé: {filepath}")
            return agent

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise


def create_sac_agent(
    state_dim: int = 10,
    action_dim: int = 3,
    hidden_dim: int = 256,
    learning_rate: float = 0.0003,
    memory_size: int = 100000,
    **kwargs
) -> SACAgent:
    config = SACConfig(
        state_dim=state_dim,
        action_dim=action_dim,
        hidden_dim=hidden_dim,
        learning_rate=learning_rate,
        memory_size=memory_size,
        **kwargs
    )
    return SACAgent(config)


__all__ = [
    'SACAgent',
    'SACConfig',
    'SACResult',
    'create_sac_agent',
]
