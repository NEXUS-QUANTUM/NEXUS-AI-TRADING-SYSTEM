# ai/reinforcement/agents/ppo_agent.py
"""
NEXUS AI TRADING SYSTEM - PPO Agent for Reinforcement Learning
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import os
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import torch.optim as optim
    from torch.distributions import Categorical, Normal
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class PPOConfig:
    """Configuration pour PPO Agent"""
    state_dim: int = 10
    action_dim: int = 3
    hidden_dim: int = 256
    learning_rate: float = 0.0003
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    max_grad_norm: float = 0.5
    epochs: int = 10
    batch_size: int = 64
    buffer_size: int = 2048
    use_gpu: bool = False
    continuous_actions: bool = False
    target_kl: Optional[float] = None
    normalize_advantages: bool = True
    use_clipped_value_loss: bool = True

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
            'gae_lambda': self.gae_lambda,
            'clip_epsilon': self.clip_epsilon,
            'value_coef': self.value_coef,
            'entropy_coef': self.entropy_coef,
            'max_grad_norm': self.max_grad_norm,
            'epochs': self.epochs,
            'batch_size': self.batch_size,
            'buffer_size': self.buffer_size,
            'use_gpu': self.use_gpu,
            'continuous_actions': self.continuous_actions,
            'target_kl': self.target_kl,
            'normalize_advantages': self.normalize_advantages,
            'use_clipped_value_loss': self.use_clipped_value_loss,
        }


@dataclass
class PPOResult:
    """Résultat d'entraînement PPO"""
    rewards: List[float]
    losses: List[float]
    policy_losses: List[float]
    value_losses: List[float]
    entropy_losses: List[float]
    kl_divergences: List[float]
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    episodes: int = 0
    average_reward: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'rewards': self.rewards,
            'losses': self.losses,
            'policy_losses': self.policy_losses,
            'value_losses': self.value_losses,
            'entropy_losses': self.entropy_losses,
            'kl_divergences': self.kl_divergences,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
            'episodes': self.episodes,
            'average_reward': self.average_reward,
        }


class _PPONetwork(nn.Module):
    """Réseau PPO avec acteur et critique"""

    def __init__(self, config: PPOConfig):
        super().__init__()

        self.config = config
        self.continuous = config.continuous_actions

        self.fc1 = nn.Linear(config.state_dim, config.hidden_dim)
        self.fc2 = nn.Linear(config.hidden_dim, config.hidden_dim)

        if config.continuous_actions:
            self.mean = nn.Linear(config.hidden_dim, config.action_dim)
            self.log_std = nn.Parameter(torch.zeros(1, config.action_dim))
        else:
            self.actor = nn.Linear(config.hidden_dim, config.action_dim)

        self.critic = nn.Linear(config.hidden_dim, 1)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return x

    def get_action(self, state, deterministic=False):
        hidden = self.forward(state)

        if self.continuous:
            mean = self.mean(hidden)
            std = torch.exp(self.log_std)
            dist = Normal(mean, std)

            if deterministic:
                action = mean
            else:
                action = dist.rsample()

            log_prob = dist.log_prob(action).sum(dim=-1)
            entropy = dist.entropy().sum(dim=-1)
            return action, log_prob, entropy
        else:
            logits = self.actor(hidden)
            dist = Categorical(logits=logits)

            if deterministic:
                action = torch.argmax(logits, dim=-1)
            else:
                action = dist.sample()

            log_prob = dist.log_prob(action)
            entropy = dist.entropy()
            return action, log_prob, entropy

    def evaluate(self, state, action):
        hidden = self.forward(state)
        value = self.critic(hidden)

        if self.continuous:
            mean = self.mean(hidden)
            std = torch.exp(self.log_std)
            dist = Normal(mean, std)
            log_prob = dist.log_prob(action).sum(dim=-1)
            entropy = dist.entropy().sum(dim=-1)
        else:
            logits = self.actor(hidden)
            dist = Categorical(logits=logits)
            log_prob = dist.log_prob(action)
            entropy = dist.entropy()

        return value, log_prob, entropy


class _PPOBuffer:
    """Buffer pour PPO"""

    def __init__(self, buffer_size: int):
        self.buffer_size = buffer_size
        self.states = []
        self.actions = []
        self.rewards = []
        self.dones = []
        self.log_probs = []
        self.values = []
        self.advantages = []
        self.returns = []

    def push(self, state, action, reward, done, log_prob, value):
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.dones.append(done)
        self.log_probs.append(log_prob)
        self.values.append(value)

    def compute_gae(self, gamma: float, gae_lambda: float, last_value: float):
        """Calcule l'advantage avec GAE"""
        advantages = []
        gae = 0

        for t in reversed(range(len(self.rewards))):
            if t == len(self.rewards) - 1:
                next_value = last_value
            else:
                next_value = self.values[t + 1]

            delta = self.rewards[t] + gamma * next_value * (1 - self.dones[t]) - self.values[t]
            gae = delta + gamma * gae_lambda * (1 - self.dones[t]) * gae
            advantages.insert(0, gae)

        returns = [adv + val for adv, val in zip(advantages, self.values)]

        self.advantages = advantages
        self.returns = returns

    def get_batches(self, batch_size: int):
        """Génère des batches d'entraînement"""
        n = len(self.states)
        indices = np.random.permutation(n)

        for i in range(0, n, batch_size):
            batch_indices = indices[i:i + batch_size]
            yield {
                'states': torch.FloatTensor(np.array([self.states[i] for i in batch_indices])),
                'actions': torch.LongTensor(np.array([self.actions[i] for i in batch_indices])),
                'log_probs': torch.FloatTensor(np.array([self.log_probs[i] for i in batch_indices])),
                'advantages': torch.FloatTensor(np.array([self.advantages[i] for i in batch_indices])),
                'returns': torch.FloatTensor(np.array([self.returns[i] for i in batch_indices])),
                'values': torch.FloatTensor(np.array([self.values[i] for i in batch_indices])),
            }

    def clear(self):
        self.states = []
        self.actions = []
        self.rewards = []
        self.dones = []
        self.log_probs = []
        self.values = []
        self.advantages = []
        self.returns = []

    def __len__(self):
        return len(self.states)


class PPOAgent:
    """
    PPO (Proximal Policy Optimization) Agent for reinforcement learning.

    This implementation supports:
    - Continuous and discrete action spaces
    - GAE (Generalized Advantage Estimation)
    - Clipped surrogate objective
    - Value function clipping
    - Entropy bonus for exploration
    - KL divergence monitoring

    Example:
        ```python
        config = PPOConfig(
            state_dim=10,
            action_dim=3,
            hidden_dim=256,
            buffer_size=2048
        )
        agent = PPOAgent(config)

        # Training loop
        for episode in range(episodes):
            state = env.reset()
            done = False
            while not done:
                action, log_prob, value = agent.select_action(state)
                next_state, reward, done = env.step(action)
                agent.store_transition(state, action, reward, done, log_prob, value)
                state = next_state

                if agent.is_buffer_ready():
                    agent.update()
        ```
    """

    def __init__(self, config: Optional[PPOConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis")

        self.config = config or PPOConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')

        self.network = _PPONetwork(self.config).to(self.device)
        self.optimizer = optim.Adam(
            self.network.parameters(),
            lr=self.config.learning_rate
        )

        self.buffer = _PPOBuffer(self.config.buffer_size)
        self.episode_rewards: List[float] = []
        self.losses: List[float] = []
        self.policy_losses: List[float] = []
        self.value_losses: List[float] = []
        self.entropy_losses: List[float] = []
        self.kl_divergences: List[float] = []

        self._last_value = None
        self._episode_reward = 0.0

        logger.info(f"PPOAgent initialisé sur {self.device}")

    def select_action(self, state: np.ndarray, deterministic: bool = False) -> Tuple[Any, float, float]:
        """
        Sélectionne une action selon la politique actuelle.

        Args:
            state: État actuel
            deterministic: Action déterministe

        Returns:
            Tuple: (action, log_prob, value)
        """
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)

        with torch.no_grad():
            action, log_prob, _ = self.network.get_action(state_tensor, deterministic)

        action = action.cpu().numpy()
        if not self.config.continuous_actions:
            action = int(action)

        return action, log_prob.item(), self._get_value(state)

    def _get_value(self, state: np.ndarray) -> float:
        """Calcule la valeur d'un état"""
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            hidden = self.network.forward(state_tensor)
            value = self.network.critic(hidden)
        return value.item()

    def store_transition(
        self,
        state: np.ndarray,
        action: Any,
        reward: float,
        done: bool,
        log_prob: float,
        value: float
    ):
        """
        Stocke une transition dans le buffer.

        Args:
            state: État
            action: Action
            reward: Récompense
            done: Terminé ou non
            log_prob: Log probabilité de l'action
            value: Valeur de l'état
        """
        self.buffer.push(state, action, reward, done, log_prob, value)
        self._episode_reward += reward

        if done:
            self.episode_rewards.append(self._episode_reward)
            self._episode_reward = 0.0

    def is_buffer_ready(self) -> bool:
        """Vérifie si le buffer est prêt pour l'entraînement"""
        return len(self.buffer) >= self.config.buffer_size

    def update(self, last_value: Optional[float] = None) -> Dict[str, float]:
        """
        Met à jour la politique avec les données du buffer.

        Args:
            last_value: Dernière valeur (optionnel)

        Returns:
            Dict[str, float]: Métriques d'entraînement
        """
        if last_value is None:
            last_value = 0.0

        self.buffer.compute_gae(
            self.config.gamma,
            self.config.gae_lambda,
            last_value
        )

        if self.config.normalize_advantages:
            advantages = np.array(self.buffer.advantages)
            if len(advantages) > 1:
                advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
                self.buffer.advantages = advantages.tolist()

        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy_loss = 0.0
        total_kl = 0.0
        n_batches = 0

        for epoch in range(self.config.epochs):
            batch_generator = self.buffer.get_batches(self.config.batch_size)

            for batch in batch_generator:
                states = batch['states'].to(self.device)
                actions = batch['actions'].to(self.device)
                old_log_probs = batch['log_probs'].to(self.device)
                advantages = batch['advantages'].to(self.device)
                returns = batch['returns'].to(self.device)
                old_values = batch['values'].to(self.device)

                values, log_probs, entropy = self.network.evaluate(states, actions)

                ratio = torch.exp(log_probs - old_log_probs)

                surr1 = ratio * advantages
                surr2 = torch.clamp(ratio, 1 - self.config.clip_epsilon, 1 + self.config.clip_epsilon) * advantages
                policy_loss = -torch.min(surr1, surr2).mean()

                if self.config.use_clipped_value_loss:
                    value_clipped = old_values + torch.clamp(
                        values - old_values,
                        -self.config.clip_epsilon,
                        self.config.clip_epsilon
                    )
                    value_loss1 = F.mse_loss(values, returns)
                    value_loss2 = F.mse_loss(value_clipped, returns)
                    value_loss = torch.max(value_loss1, value_loss2)
                else:
                    value_loss = F.mse_loss(values, returns)

                entropy_loss = -entropy.mean()

                loss = (
                    policy_loss +
                    self.config.value_coef * value_loss +
                    self.config.entropy_coef * entropy_loss
                )

                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.network.parameters(), self.config.max_grad_norm)
                self.optimizer.step()

                with torch.no_grad():
                    kl = (old_log_probs - log_probs).mean().item()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy_loss += entropy_loss.item()
                total_kl += kl
                n_batches += 1

                if self.config.target_kl is not None and kl > self.config.target_kl:
                    logger.debug(f"KL divergence {kl:.4f} > target {self.config.target_kl}")
                    break

        avg_policy_loss = total_policy_loss / n_batches if n_batches > 0 else 0
        avg_value_loss = total_value_loss / n_batches if n_batches > 0 else 0
        avg_entropy_loss = total_entropy_loss / n_batches if n_batches > 0 else 0
        avg_kl = total_kl / n_batches if n_batches > 0 else 0
        avg_loss = avg_policy_loss + self.config.value_coef * avg_value_loss + self.config.entropy_coef * avg_entropy_loss

        self.losses.append(avg_loss)
        self.policy_losses.append(avg_policy_loss)
        self.value_losses.append(avg_value_loss)
        self.entropy_losses.append(avg_entropy_loss)
        self.kl_divergences.append(avg_kl)

        self.buffer.clear()

        return {
            'loss': avg_loss,
            'policy_loss': avg_policy_loss,
            'value_loss': avg_value_loss,
            'entropy_loss': avg_entropy_loss,
            'kl_divergence': avg_kl,
        }

    def get_action(self, state: np.ndarray, deterministic: bool = False) -> Any:
        """
        Sélectionne une action (interface simplifiée).

        Args:
            state: État
            deterministic: Action déterministe

        Returns:
            Any: Action
        """
        action, _, _ = self.select_action(state, deterministic)
        return action

    def get_params(self) -> Dict[str, Any]:
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        metrics = {
            'is_trained': len(self.losses) > 0,
            'episodes': len(self.episode_rewards),
            'buffer_size': len(self.buffer),
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

        if self.kl_divergences:
            metrics['average_kl'] = np.mean(self.kl_divergences[-100:])

        return metrics

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde l'agent PPO sur le disque.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si la sauvegarde a réussi
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'network_state_dict': self.network.state_dict(),
                'optimizer_state_dict': self.optimizer.state_dict(),
                'episode_rewards': self.episode_rewards,
                'losses': self.losses,
                'policy_losses': self.policy_losses,
                'value_losses': self.value_losses,
                'entropy_losses': self.entropy_losses,
                'kl_divergences': self.kl_divergences,
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
    def load(cls, filepath: str) -> 'PPOAgent':
        """
        Charge un agent PPO depuis le disque.

        Args:
            filepath: Chemin du fichier

        Returns:
            PPOAgent: Agent chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = PPOConfig(**data['config'])
            agent = cls(config)

            agent.network.load_state_dict(data['network_state_dict'])
            agent.optimizer.load_state_dict(data['optimizer_state_dict'])

            agent.episode_rewards = data.get('episode_rewards', [])
            agent.losses = data.get('losses', [])
            agent.policy_losses = data.get('policy_losses', [])
            agent.value_losses = data.get('value_losses', [])
            agent.entropy_losses = data.get('entropy_losses', [])
            agent.kl_divergences = data.get('kl_divergences', [])

            logger.info(f"Agent chargé: {filepath}")
            return agent

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise


def create_ppo_agent(
    state_dim: int = 10,
    action_dim: int = 3,
    hidden_dim: int = 256,
    learning_rate: float = 0.0003,
    buffer_size: int = 2048,
    **kwargs
) -> PPOAgent:
    """
    Factory pour créer un agent PPO.

    Args:
        state_dim: Dimension de l'état
        action_dim: Dimension de l'action
        hidden_dim: Dimension cachée
        learning_rate: Taux d'apprentissage
        buffer_size: Taille du buffer
        **kwargs: Arguments supplémentaires

    Returns:
        PPOAgent: Agent PPO
    """
    config = PPOConfig(
        state_dim=state_dim,
        action_dim=action_dim,
        hidden_dim=hidden_dim,
        learning_rate=learning_rate,
        buffer_size=buffer_size,
        **kwargs
    )
    return PPOAgent(config)


__all__ = [
    'PPOAgent',
    'PPOConfig',
    'PPOResult',
    'create_ppo_agent',
]
