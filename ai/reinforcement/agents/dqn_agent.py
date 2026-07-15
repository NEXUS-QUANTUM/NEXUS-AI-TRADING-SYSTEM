
# ai/reinforcement/agents/dqn_agent.py
"""
NEXUS AI TRADING SYSTEM - DQN Agent for Reinforcement Learning
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import random
from typing import Optional, List, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import os
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
class DQNConfig:
    """Configuration pour DQN Agent"""
    state_dim: int = 10
    action_dim: int = 3
    hidden_dim: int = 256
    learning_rate: float = 0.001
    gamma: float = 0.99
    epsilon_start: float = 1.0
    epsilon_end: float = 0.01
    epsilon_decay: float = 0.995
    memory_size: int = 10000
    batch_size: int = 64
    target_update: int = 100
    use_gpu: bool = False
    double_dqn: bool = True
    dueling_dqn: bool = True
    prioritized_memory: bool = False
    noisy_net: bool = False
    alpha: float = 0.6
    beta: float = 0.4
    beta_increment: float = 0.001
    tau: float = 0.001

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
            'epsilon_start': self.epsilon_start,
            'epsilon_end': self.epsilon_end,
            'epsilon_decay': self.epsilon_decay,
            'memory_size': self.memory_size,
            'batch_size': self.batch_size,
            'target_update': self.target_update,
            'use_gpu': self.use_gpu,
            'double_dqn': self.double_dqn,
            'dueling_dqn': self.dueling_dqn,
            'prioritized_memory': self.prioritized_memory,
            'noisy_net': self.noisy_net,
            'alpha': self.alpha,
            'beta': self.beta,
            'beta_increment': self.beta_increment,
            'tau': self.tau,
        }


@dataclass
class DQNResult:
    """Résultat d'entraînement DQN"""
    rewards: List[float]
    losses: List[float]
    epsilon_history: List[float]
    q_values: List[float]
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    episodes: int = 0
    average_reward: float = 0.0
    success_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'rewards': self.rewards,
            'losses': self.losses,
            'epsilon_history': self.epsilon_history,
            'q_values': self.q_values,
            'training_time': self.training_time,
            'timestamp': self.timestamp.isoformat(),
            'episodes': self.episodes,
            'average_reward': self.average_reward,
            'success_rate': self.success_rate,
        }


class _DQNNetwork(nn.Module):
    """Réseau Q pour DQN"""

    def __init__(self, config: DQNConfig):
        super().__init__()

        self.config = config
        self.dueling = config.dueling_dqn

        self.fc1 = nn.Linear(config.state_dim, config.hidden_dim)
        self.fc2 = nn.Linear(config.hidden_dim, config.hidden_dim)

        if self.dueling:
            self.value_fc = nn.Linear(config.hidden_dim, 1)
            self.advantage_fc = nn.Linear(config.hidden_dim, config.action_dim)
        else:
            self.output = nn.Linear(config.hidden_dim, config.action_dim)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))

        if self.dueling:
            value = self.value_fc(x)
            advantage = self.advantage_fc(x)
            q_values = value + advantage - advantage.mean(dim=1, keepdim=True)
            return q_values
        else:
            return self.output(x)


class _PrioritizedReplayBuffer:
    """Mémoire de rejeu avec priorisation"""

    def __init__(self, capacity: int, alpha: float = 0.6):
        self.capacity = capacity
        self.alpha = alpha
        self.buffer = []
        self.priorities = []
        self.position = 0

    def push(self, state, action, reward, next_state, done, error=None):
        priority = (abs(error) + 1e-5) ** self.alpha if error is not None else 1.0

        if len(self.buffer) < self.capacity:
            self.buffer.append((state, action, reward, next_state, done))
            self.priorities.append(priority)
        else:
            self.buffer[self.position] = (state, action, reward, next_state, done)
            self.priorities[self.position] = priority

        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size: int, beta: float = 0.4):
        if len(self.buffer) == 0:
            return [], [], []

        priorities = np.array(self.priorities)
        probs = priorities ** self.alpha
        probs = probs / probs.sum()

        indices = np.random.choice(len(self.buffer), batch_size, p=probs)
        samples = [self.buffer[idx] for idx in indices]

        weights = (len(self.buffer) * probs[indices]) ** (-beta)
        weights = weights / weights.max()

        batch = list(zip(*samples))
        return batch, indices, weights

    def update_priorities(self, indices, errors):
        for idx, error in zip(indices, errors):
            self.priorities[idx] = (abs(error) + 1e-5) ** self.alpha

    def __len__(self):
        return len(self.buffer)


class _ReplayBuffer:
    """Mémoire de rejeu standard"""

    def __init__(self, capacity: int):
        self.buffer = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int):
        batch = random.sample(self.buffer, batch_size)
        return list(zip(*batch))

    def __len__(self):
        return len(self.buffer)


class DQNAgent:
    """
    DQN (Deep Q-Network) Agent for reinforcement learning.

    This implementation supports:
    - Standard DQN
    - Double DQN
    - Dueling DQN
    - Prioritized Experience Replay
    - Soft target updates

    Example:
        ```python
        config = DQNConfig(
            state_dim=10,
            action_dim=3,
            hidden_dim=256,
            memory_size=10000
        )
        agent = DQNAgent(config)

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

    def __init__(self, config: Optional[DQNConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis")

        self.config = config or DQNConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')

        self.policy_net = _DQNNetwork(self.config).to(self.device)
        self.target_net = _DQNNetwork(self.config).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())

        self.optimizer = optim.Adam(
            self.policy_net.parameters(),
            lr=self.config.learning_rate
        )

        if self.config.prioritized_memory:
            self.memory = _PrioritizedReplayBuffer(
                self.config.memory_size,
                self.config.alpha
            )
        else:
            self.memory = _ReplayBuffer(self.config.memory_size)

        self.epsilon = self.config.epsilon_start
        self.steps = 0
        self.loss_history: List[float] = []
        self.reward_history: List[float] = []
        self.epsilon_history: List[float] = []
        self.q_value_history: List[float] = []

        logger.info(f"DQNAgent initialisé sur {self.device}")

    def select_action(self, state: np.ndarray, epsilon: Optional[float] = None) -> int:
        """
        Sélectionne une action selon la politique epsilon-greedy.

        Args:
            state: État actuel
            epsilon: Valeur d'epsilon (optionnel)

        Returns:
            int: Action sélectionnée
        """
        if epsilon is None:
            epsilon = self.epsilon

        if random.random() < epsilon:
            return random.randrange(self.config.action_dim)

        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            q_values = self.policy_net(state_tensor)
            action = q_values.argmax().item()

        return action

    def store_transition(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
        td_error: Optional[float] = None
    ):
        """
        Stocke une transition dans la mémoire.

        Args:
            state: État
            action: Action
            reward: Récompense
            next_state: État suivant
            done: Terminé ou non
            td_error: Erreur TD pour la mémoire priorisée
        """
        if self.config.prioritized_memory:
            self.memory.push(state, action, reward, next_state, done, td_error)
        else:
            self.memory.push(state, action, reward, next_state, done)

    def update(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Met à jour le réseau Q.

        Returns:
            Tuple[Optional[float], Optional[float]]: (Perte, Q-Valeur moyenne)
        """
        if len(self.memory) < self.config.batch_size:
            return None, None

        if self.config.prioritized_memory:
            batch, indices, weights = self.memory.sample(
                self.config.batch_size,
                self.config.beta
            )
            states, actions, rewards, next_states, dones = batch
            weights = torch.FloatTensor(weights).to(self.device)
        else:
            states, actions, rewards, next_states, dones = self.memory.sample(
                self.config.batch_size
            )
            indices = None
            weights = None

        states = torch.FloatTensor(np.array(states)).to(self.device)
        actions = torch.LongTensor(np.array(actions)).to(self.device)
        rewards = torch.FloatTensor(np.array(rewards)).to(self.device)
        next_states = torch.FloatTensor(np.array(next_states)).to(self.device)
        dones = torch.FloatTensor(np.array(dones)).to(self.device)

        current_q = self.policy_net(states).gather(1, actions.unsqueeze(1)).squeeze()

        if self.config.double_dqn:
            next_actions = self.policy_net(next_states).argmax(1, keepdim=True)
            next_q = self.target_net(next_states).gather(1, next_actions).squeeze()
        else:
            next_q = self.target_net(next_states).max(1)[0]

        target_q = rewards + (1 - dones) * self.config.gamma * next_q.detach()

        if weights is not None:
            loss = (weights * (current_q - target_q) ** 2).mean()
        else:
            loss = F.mse_loss(current_q, target_q)

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 1.0)
        self.optimizer.step()

        self.steps += 1

        if self.config.prioritized_memory and indices is not None:
            td_errors = (current_q - target_q).detach().cpu().numpy()
            self.memory.update_priorities(indices, td_errors)

        if self.steps % self.config.target_update == 0:
            self._update_target_network()

        self._decay_epsilon()

        q_value = current_q.mean().item()
        self.loss_history.append(loss.item())
        self.q_value_history.append(q_value)

        return loss.item(), q_value

    def _update_target_network(self):
        """Met à jour le réseau cible"""
        if self.config.tau < 1:
            # Soft update
            for target_param, policy_param in zip(
                self.target_net.parameters(),
                self.policy_net.parameters()
            ):
                target_param.data.copy_(
                    self.config.tau * policy_param.data +
                    (1 - self.config.tau) * target_param.data
                )
        else:
            # Hard update
            self.target_net.load_state_dict(self.policy_net.state_dict())

    def _decay_epsilon(self):
        """Décroît epsilon"""
        self.epsilon = max(
            self.config.epsilon_end,
            self.epsilon * self.config.epsilon_decay
        )
        self.epsilon_history.append(self.epsilon)

    def get_q_values(self, state: np.ndarray) -> np.ndarray:
        """
        Retourne les Q-values pour un état donné.

        Args:
            state: État

        Returns:
            np.ndarray: Q-values
        """
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            q_values = self.policy_net(state_tensor).cpu().numpy().flatten()
        return q_values

    def get_params(self) -> Dict[str, Any]:
        return self.config.to_dict()

    def get_metrics(self) -> Dict[str, Any]:
        metrics = {
            'is_trained': len(self.loss_history) > 0,
            'episodes': len(self.reward_history),
            'epsilon': self.epsilon,
            'steps': self.steps,
            'memory_size': len(self.memory),
            'device': str(self.device),
            'loss_history_length': len(self.loss_history),
            'reward_history_length': len(self.reward_history),
        }

        if self.reward_history:
            metrics['average_reward'] = np.mean(self.reward_history[-100:])
            metrics['best_reward'] = max(self.reward_history)
            metrics['worst_reward'] = min(self.reward_history)

        if self.loss_history:
            metrics['average_loss'] = np.mean(self.loss_history[-100:])
            metrics['final_loss'] = self.loss_history[-1]

        return metrics

    def save(self, filepath: str) -> bool:
        """
        Sauvegarde l'agent DQN sur le disque.

        Args:
            filepath: Chemin du fichier

        Returns:
            bool: True si la sauvegarde a réussi
        """
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            data = {
                'config': self.config.to_dict(),
                'policy_net_state_dict': self.policy_net.state_dict(),
                'target_net_state_dict': self.target_net.state_dict(),
                'epsilon': self.epsilon,
                'steps': self.steps,
                'loss_history': self.loss_history,
                'reward_history': self.reward_history,
                'epsilon_history': self.epsilon_history,
                'q_value_history': self.q_value_history,
                'memory': list(self.memory.buffer) if hasattr(self.memory, 'buffer') else [],
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
    def load(cls, filepath: str) -> 'DQNAgent':
        """
        Charge un agent DQN depuis le disque.

        Args:
            filepath: Chemin du fichier

        Returns:
            DQNAgent: Agent chargé
        """
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = DQNConfig(**data['config'])
            agent = cls(config)

            agent.policy_net.load_state_dict(data['policy_net_state_dict'])
            agent.target_net.load_state_dict(data['target_net_state_dict'])

            agent.epsilon = data.get('epsilon', config.epsilon_start)
            agent.steps = data.get('steps', 0)
            agent.loss_history = data.get('loss_history', [])
            agent.reward_history = data.get('reward_history', [])
            agent.epsilon_history = data.get('epsilon_history', [])
            agent.q_value_history = data.get('q_value_history', [])

            if data.get('memory'):
                if agent.config.prioritized_memory:
                    for item in data['memory']:
                        agent.memory.push(*item)
                else:
                    agent.memory.buffer = deque(data['memory'], maxlen=agent.config.memory_size)

            logger.info(f"Agent chargé: {filepath}")
            return agent

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise


def create_dqn_agent(
    state_dim: int = 10,
    action_dim: int = 3,
    hidden_dim: int = 256,
    learning_rate: float = 0.001,
    memory_size: int = 10000,
    **kwargs
) -> DQNAgent:
    """
    Factory pour créer un agent DQN.

    Args:
        state_dim: Dimension de l'état
        action_dim: Dimension de l'action
        hidden_dim: Dimension cachée
        learning_rate: Taux d'apprentissage
        memory_size: Taille de la mémoire
        **kwargs: Arguments supplémentaires

    Returns:
        DQNAgent: Agent DQN
    """
    config = DQNConfig(
        state_dim=state_dim,
        action_dim=action_dim,
        hidden_dim=hidden_dim,
        learning_rate=learning_rate,
        memory_size=memory_size,
        **kwargs
    )
    return DQNAgent(config)


__all__ = [
    'DQNAgent',
    'DQNConfig',
    'DQNResult',
    'create_dqn_agent',
]
