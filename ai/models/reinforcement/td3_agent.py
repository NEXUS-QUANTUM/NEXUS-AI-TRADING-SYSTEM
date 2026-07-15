
# ai/models/reinforcement/td3_agent.py
"""
NEXUS AI TRADING SYSTEM - TD3 (Twin Delayed Deep Deterministic Policy Gradient) Agent
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
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class TD3Config:
    state_dim: int = 10
    action_dim: int = 3
    hidden_dim: int = 256
    learning_rate: float = 0.0003
    gamma: float = 0.99
    tau: float = 0.005
    policy_noise: float = 0.2
    noise_clip: float = 0.5
    policy_freq: int = 2
    memory_size: int = 100000
    batch_size: int = 256
    use_gpu: bool = False
    action_scale: float = 1.0
    action_bias: float = 0.0
    max_grad_norm: float = 1.0

    def __post_init__(self):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch n'est pas installé")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'state_dim': self.state_dim,
            'action_dim': self.action_dim,
            'hidden_dim': self.hidden_dim,
            'learning_rate': self.learning_rate,
            'gamma': self.gamma,
            'tau': self.tau,
            'policy_noise': self.policy_noise,
            'noise_clip': self.noise_clip,
            'policy_freq': self.policy_freq,
            'memory_size': self.memory_size,
            'batch_size': self.batch_size,
            'use_gpu': self.use_gpu,
            'action_scale': self.action_scale,
            'action_bias': self.action_bias,
            'max_grad_norm': self.max_grad_norm,
        }


@dataclass
class TD3Result:
    rewards: List[float]
    losses: List[float]
    q_values: List[float]
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    episodes: int = 0
    average_reward: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'rewards': self.rewards,
            'losses': self.losses,
            'q_values': self.q_values,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
            'episodes': self.episodes,
            'average_reward': self.average_reward,
        }


class _TD3Actor(nn.Module):
    """Acteur pour TD3"""

    def __init__(self, config: TD3Config):
        super().__init__()

        self.config = config
        self.action_scale = config.action_scale
        self.action_bias = config.action_bias

        self.fc1 = nn.Linear(config.state_dim, config.hidden_dim)
        self.fc2 = nn.Linear(config.hidden_dim, config.hidden_dim)
        self.mean = nn.Linear(config.hidden_dim, config.action_dim)

    def forward(self, state):
        x = F.relu(self.fc1(state))
        x = F.relu(self.fc2(x))
        action = torch.tanh(self.mean(x))
        action = action * self.action_scale + self.action_bias
        return action


class _TD3Critic(nn.Module):
    """Critique pour TD3 (deux Q-fonctions)"""

    def __init__(self, config: TD3Config):
        super().__init__()

        # Q1
        self.q1_fc1 = nn.Linear(config.state_dim + config.action_dim, config.hidden_dim)
        self.q1_fc2 = nn.Linear(config.hidden_dim, config.hidden_dim)
        self.q1 = nn.Linear(config.hidden_dim, 1)

        # Q2
        self.q2_fc1 = nn.Linear(config.state_dim + config.action_dim, config.hidden_dim)
        self.q2_fc2 = nn.Linear(config.hidden_dim, config.hidden_dim)
        self.q2 = nn.Linear(config.hidden_dim, 1)

    def forward(self, state, action):
        sa = torch.cat([state, action], dim=1)

        q1 = F.relu(self.q1_fc1(sa))
        q1 = F.relu(self.q1_fc2(q1))
        q1 = self.q1(q1)

        q2 = F.relu(self.q2_fc1(sa))
        q2 = F.relu(self.q2_fc2(q2))
        q2 = self.q2(q2)

        return q1, q2

    def get_q1(self, state, action):
        sa = torch.cat([state, action], dim=1)
        q1 = F.relu(self.q1_fc1(sa))
        q1 = F.relu(self.q1_fc2(q1))
        q1 = self.q1(q1)
        return q1


class _ReplayBuffer:
    """Mémoire de rejeu standard pour TD3"""

    def __init__(self, capacity: int):
        self.buffer = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int):
        batch = random.sample(self.buffer, batch_size)
        return list(zip(*batch))

    def __len__(self):
        return len(self.buffer)


class TD3Agent:
    """
    TD3 (Twin Delayed Deep Deterministic Policy Gradient) Agent.

    TD3 improves upon DDPG with:
    - Clipped Double-Q Learning
    - Target Policy Smoothing
    - Delayed Policy Updates

    This implementation supports:
    - Continuous action spaces
    - Double Q-learning with min target
    - Target policy smoothing with noise
    - Delayed actor updates
    - GPU acceleration

    Example:
        ```python
        config = TD3Config(
            state_dim=10,
            action_dim=3,
            hidden_dim=256,
            learning_rate=0.0003,
            memory_size=100000
        )
        agent = TD3Agent(config)

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

    def __init__(self, config: Optional[TD3Config] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis. Installez avec: pip install torch")

        self.config = config or TD3Config()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')

        # Acteur
        self.actor = _TD3Actor(self.config).to(self.device)
        self.actor_target = _TD3Actor(self.config).to(self.device)
        self.actor_target.load_state_dict(self.actor.state_dict())

        # Critiques
        self.critic = _TD3Critic(self.config).to(self.device)
        self.critic_target = _TD3Critic(self.config).to(self.device)
        self.critic_target.load_state_dict(self.critic.state_dict())

        # Optimiseurs
        self.actor_optimizer = optim.Adam(
            self.actor.parameters(),
            lr=self.config.learning_rate
        )

        self.critic_optimizer = optim.Adam(
            self.critic.parameters(),
            lr=self.config.learning_rate
        )

        # Mémoire
        self.memory = _ReplayBuffer(self.config.memory_size)

        # Compteur pour delayed policy update
        self.total_it = 0

        # Historique
        self.episode_rewards: List[float] = []
        self.losses: List[float] = []
        self.q_values: List[float] = []

        logger.info(f"TD3Agent initialisé sur {self.device}")

    def select_action(self, state: np.ndarray, add_noise: bool = False, noise_scale: float = 0.1) -> np.ndarray:
        """
        Sélectionne une action selon la politique actuelle.

        Args:
            state: État actuel
            add_noise: Ajouter du bruit à l'action
            noise_scale: Échelle du bruit

        Returns:
            np.ndarray: Action
        """
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            action = self.actor(state_tensor)
            action = action.cpu().numpy().flatten()

        if add_noise:
            noise = np.random.normal(0, noise_scale, size=self.config.action_dim)
            action = np.clip(action + noise, -self.config.action_scale, self.config.action_scale)

        return action

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
        Met à jour les réseaux TD3.

        Returns:
            Dict[str, float]: Métriques d'entraînement
        """
        if len(self.memory) < self.config.batch_size:
            return {}

        self.total_it += 1

        # Échantillonner le batch
        states, actions, rewards, next_states, dones = self.memory.sample(self.config.batch_size)

        states = torch.FloatTensor(np.array(states)).to(self.device)
        actions = torch.FloatTensor(np.array(actions)).to(self.device)
        rewards = torch.FloatTensor(np.array(rewards)).unsqueeze(1).to(self.device)
        next_states = torch.FloatTensor(np.array(next_states)).to(self.device)
        dones = torch.FloatTensor(np.array(dones)).unsqueeze(1).to(self.device)

        # --- Mise à jour des Q-fonctions ---
        with torch.no_grad():
            # Target policy smoothing
            noise = torch.randn_like(actions) * self.config.policy_noise
            noise = torch.clamp(noise, -self.config.noise_clip, self.config.noise_clip)

            next_actions = self.actor_target(next_states) + noise
            next_actions = torch.clamp(next_actions, -self.config.action_scale, self.config.action_scale)

            # Min target Q
            target_q1, target_q2 = self.critic_target(next_states, next_actions)
            target_q = torch.min(target_q1, target_q2)
            target_q = rewards + (1 - dones) * self.config.gamma * target_q

        # Current Q
        q1, q2 = self.critic(states, actions)

        # Critic loss
        q1_loss = F.mse_loss(q1, target_q)
        q2_loss = F.mse_loss(q2, target_q)
        critic_loss = q1_loss + q2_loss

        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.critic.parameters(), self.config.max_grad_norm)
        self.critic_optimizer.step()

        # --- Mise à jour de l'acteur (retardée) ---
        actor_loss = torch.tensor(0.0, device=self.device)

        if self.total_it % self.config.policy_freq == 0:
            # Actor loss
            new_actions = self.actor(states)
            q1_new = self.critic.get_q1(states, new_actions)
            actor_loss = -q1_new.mean()

            self.actor_optimizer.zero_grad()
            actor_loss.backward()
            torch.nn.utils.clip_grad_norm_(self.actor.parameters(), self.config.max_grad_norm)
            self.actor_optimizer.step()

            # Mise à jour des cibles
            self._update_target_networks()

        # --- Métriques ---
        total_loss = critic_loss.item() + (actor_loss.item() if torch.is_tensor(actor_loss) else 0)

        self.losses.append(total_loss)
        self.q_values.append(q1.mean().item())

        return {
            'q1_loss': q1_loss.item(),
            'q2_loss': q2_loss.item(),
            'critic_loss': critic_loss.item(),
            'actor_loss': actor_loss.item() if torch.is_tensor(actor_loss) else 0,
            'total_loss': total_loss,
            'q_value': q1.mean().item(),
        }

    def _update_target_networks(self):
        """Met à jour les réseaux cibles avec soft update"""
        for target_param, param in zip(self.actor_target.parameters(), self.actor.parameters()):
            target_param.data.copy_(self.config.tau * param.data + (1 - self.config.tau) * target_param.data)

        for target_param, param in zip(self.critic_target.parameters(), self.critic.parameters()):
            target_param.data.copy_(self.config.tau * param.data + (1 - self.config.tau) * target_param.data)

    def get_params(self) -> Dict[str, Any]:
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        metrics = {
            'is_trained': len(self.losses) > 0,
            'episodes': len(self.episode_rewards),
            'total_updates': self.total_it,
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
        Sauvegarde l'agent TD3 sur le disque.

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
                'actor_target_state_dict': self.actor_target.state_dict(),
                'critic_state_dict': self.critic.state_dict(),
                'critic_target_state_dict': self.critic_target.state_dict(),
                'actor_optimizer_state_dict': self.actor_optimizer.state_dict(),
                'critic_optimizer_state_dict': self.critic_optimizer.state_dict(),
                'total_it': self.total_it,
                'episode_rewards': self.episode_rewards,
                'losses': self.losses,
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
    def load(cls, filepath: str) -> 'TD3Agent':
        """
        Charge un agent TD3 depuis le disque.

        Args:
            filepath: Chemin du fichier

        Returns:
            TD3Agent: Agent chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = TD3Config(**data['config'])
            agent = cls(config)

            agent.actor.load_state_dict(data['actor_state_dict'])
            agent.actor_target.load_state_dict(data['actor_target_state_dict'])
            agent.critic.load_state_dict(data['critic_state_dict'])
            agent.critic_target.load_state_dict(data['critic_target_state_dict'])
            agent.actor_optimizer.load_state_dict(data['actor_optimizer_state_dict'])
            agent.critic_optimizer.load_state_dict(data['critic_optimizer_state_dict'])

            agent.total_it = data.get('total_it', 0)
            agent.episode_rewards = data.get('episode_rewards', [])
            agent.losses = data.get('losses', [])
            agent.q_values = data.get('q_values', [])

            logger.info(f"Agent chargé: {filepath}")
            return agent

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise


def create_td3_agent(
    state_dim: int = 10,
    action_dim: int = 3,
    hidden_dim: int = 256,
    learning_rate: float = 0.0003,
    memory_size: int = 100000,
    **kwargs
) -> TD3Agent:
    config = TD3Config(
        state_dim=state_dim,
        action_dim=action_dim,
        hidden_dim=hidden_dim,
        learning_rate=learning_rate,
        memory_size=memory_size,
        **kwargs
    )
    return TD3Agent(config)


__all__ = [
    'TD3Agent',
    'TD3Config',
    'TD3Result',
    'create_td3_agent',
]
