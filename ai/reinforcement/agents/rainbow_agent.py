
# ai/reinforcement/agents/rainbow_agent.py
"""
NEXUS AI TRADING SYSTEM - Rainbow DQN Agent
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
class RainbowConfig:
    """Configuration pour Rainbow DQN Agent"""
    state_dim: int = 10
    action_dim: int = 3
    hidden_dim: int = 256
    num_atoms: int = 51
    v_min: float = -10.0
    v_max: float = 10.0
    learning_rate: float = 0.0001
    gamma: float = 0.99
    epsilon_start: float = 1.0
    epsilon_end: float = 0.01
    epsilon_decay: float = 0.995
    memory_size: int = 100000
    batch_size: int = 32
    target_update: int = 100
    use_gpu: bool = False
    double_dqn: bool = True
    dueling_dqn: bool = True
    prioritized_memory: bool = True
    noisy_net: bool = True
    n_step: int = 3
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
            'num_atoms': self.num_atoms,
            'v_min': self.v_min,
            'v_max': self.v_max,
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
            'n_step': self.n_step,
            'alpha': self.alpha,
            'beta': self.beta,
            'beta_increment': self.beta_increment,
            'tau': self.tau,
        }


@dataclass
class RainbowResult:
    """Résultat d'entraînement Rainbow"""
    rewards: List[float]
    losses: List[float]
    epsilon_history: List[float]
    q_values: List[float]
    training_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    episodes: int = 0
    average_reward: float = 0.0

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
        }


class _NoisyLinear(nn.Module):
    """Couche linéaire avec bruit NoisyNet"""

    def __init__(self, in_features: int, out_features: int, sigma_init: float = 0.5):
        super().__init__()

        self.in_features = in_features
        self.out_features = out_features
        self.sigma_init = sigma_init

        self.weight_mu = nn.Parameter(torch.empty(out_features, in_features))
        self.weight_sigma = nn.Parameter(torch.empty(out_features, in_features))
        self.bias_mu = nn.Parameter(torch.empty(out_features))
        self.bias_sigma = nn.Parameter(torch.empty(out_features))

        self.register_buffer('weight_epsilon', torch.empty(out_features, in_features))
        self.register_buffer('bias_epsilon', torch.empty(out_features))

        self.reset_parameters()
        self.reset_noise()

    def reset_parameters(self):
        mu_range = 1 / np.sqrt(self.in_features)
        self.weight_mu.data.uniform_(-mu_range, mu_range)
        self.weight_sigma.data.fill_(self.sigma_init / np.sqrt(self.in_features))
        self.bias_mu.data.uniform_(-mu_range, mu_range)
        self.bias_sigma.data.fill_(self.sigma_init / np.sqrt(self.out_features))

    def reset_noise(self):
        epsilon_in = self._scale_noise(self.in_features)
        epsilon_out = self._scale_noise(self.out_features)
        self.weight_epsilon.copy_(epsilon_out.outer(epsilon_in))
        self.bias_epsilon.copy_(epsilon_out)

    def _scale_noise(self, size: int) -> torch.Tensor:
        x = torch.randn(size)
        return x.sign().mul_(x.abs().sqrt_())

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.training:
            weight = self.weight_mu + self.weight_sigma * self.weight_epsilon
            bias = self.bias_mu + self.bias_sigma * self.bias_epsilon
        else:
            weight = self.weight_mu
            bias = self.bias_mu

        return F.linear(x, weight, bias)


class _RainbowNetwork(nn.Module):
    """Réseau Rainbow avec Distributional, Dueling et NoisyNet"""

    def __init__(self, config: RainbowConfig):
        super().__init__()

        self.config = config
        self.num_atoms = config.num_atoms
        self.v_min = config.v_min
        self.v_max = config.v_max
        self.dueling = config.dueling_dqn
        self.noisy = config.noisy_net

        if self.noisy:
            self.fc1 = _NoisyLinear(config.state_dim, config.hidden_dim)
            self.fc2 = _NoisyLinear(config.hidden_dim, config.hidden_dim)
        else:
            self.fc1 = nn.Linear(config.state_dim, config.hidden_dim)
            self.fc2 = nn.Linear(config.hidden_dim, config.hidden_dim)

        if self.dueling:
            self.value_fc = nn.Linear(config.hidden_dim, self.num_atoms)
            self.advantage_fc = nn.Linear(config.hidden_dim, config.action_dim * self.num_atoms)
        else:
            self.output = nn.Linear(config.hidden_dim, config.action_dim * self.num_atoms)

        # Support pour la distribution
        self.register_buffer('support', torch.linspace(
            config.v_min, config.v_max, config.num_atoms
        ))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))

        if self.dueling:
            value = self.value_fc(x).view(-1, 1, self.num_atoms)
            advantage = self.advantage_fc(x).view(-1, self.config.action_dim, self.num_atoms)
            advantage_mean = advantage.mean(dim=1, keepdim=True)
            logits = value + advantage - advantage_mean
        else:
            logits = self.output(x).view(-1, self.config.action_dim, self.num_atoms)

        return F.softmax(logits, dim=-1)

    def reset_noise(self):
        if self.noisy:
            for module in self.modules():
                if hasattr(module, 'reset_noise'):
                    module.reset_noise()


class _RainbowReplayBuffer:
    """Mémoire de rejeu avec priorisation et N-step"""

    def __init__(
        self,
        capacity: int,
        alpha: float = 0.6,
        n_step: int = 3,
        gamma: float = 0.99
    ):
        self.capacity = capacity
        self.alpha = alpha
        self.n_step = n_step
        self.gamma = gamma

        self.buffer = []
        self.priorities = []
        self.position = 0
        self.n_step_buffer = deque(maxlen=n_step)

    def push(self, state, action, reward, next_state, done, error=None):
        self.n_step_buffer.append((state, action, reward, next_state, done))

        if len(self.n_step_buffer) == self.n_step:
            state, action, reward, next_state, done = self._get_n_step_info()
            self._push_transition(state, action, reward, next_state, done, error)

    def _get_n_step_info(self):
        rewards = []
        for i in range(self.n_step):
            rewards.append(self.n_step_buffer[i][2])

        state, action = self.n_step_buffer[0][0], self.n_step_buffer[0][1]
        next_state, done = self.n_step_buffer[-1][3], self.n_step_buffer[-1][4]

        n_step_reward = sum((self.gamma ** i) * rewards[i] for i in range(self.n_step))

        return state, action, n_step_reward, next_state, done

    def _push_transition(self, state, action, reward, next_state, done, error):
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


class RainbowAgent:
    """
    Rainbow DQN Agent combining multiple improvements:
    - Double DQN
    - Dueling Network
    - Prioritized Experience Replay
    - Noisy Networks
    - Distributional RL (C51)
    - N-step returns

    Example:
        ```python
        config = RainbowConfig(
            state_dim=10,
            action_dim=3,
            hidden_dim=256,
            num_atoms=51,
            memory_size=100000
        )
        agent = RainbowAgent(config)

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

    def __init__(self, config: Optional[RainbowConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch est requis")

        self.config = config or RainbowConfig()
        self.device = torch.device('cuda' if self.config.use_gpu and torch.cuda.is_available() else 'cpu')

        self.policy_net = _RainbowNetwork(self.config).to(self.device)
        self.target_net = _RainbowNetwork(self.config).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())

        self.optimizer = optim.Adam(
            self.policy_net.parameters(),
            lr=self.config.learning_rate
        )

        self.memory = _RainbowReplayBuffer(
            self.config.memory_size,
            self.config.alpha,
            self.config.n_step,
            self.config.gamma
        )

        self.epsilon = self.config.epsilon_start
        self.steps = 0
        self.loss_history: List[float] = []
        self.reward_history: List[float] = []
        self.epsilon_history: List[float] = []
        self.q_value_history: List[float] = []

        logger.info(f"RainbowAgent initialisé sur {self.device}")

    def select_action(self, state: np.ndarray, epsilon: Optional[float] = None) -> int:
        if epsilon is None:
            epsilon = self.epsilon

        if random.random() < epsilon:
            return random.randrange(self.config.action_dim)

        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            dist = self.policy_net(state_tensor)
            q_values = (dist * self.policy_net.support).sum(dim=-1)
            action = q_values.argmax().item()

        return action

    def store_transition(self, state, action, reward, next_state, done, td_error=None):
        self.memory.push(state, action, reward, next_state, done, td_error)

    def update(self) -> Tuple[Optional[float], Optional[float]]:
        if len(self.memory) < self.config.batch_size:
            return None, None

        batch, indices, weights = self.memory.sample(
            self.config.batch_size,
            self.config.beta
        )
        states, actions, rewards, next_states, dones = batch

        states = torch.FloatTensor(np.array(states)).to(self.device)
        actions = torch.LongTensor(np.array(actions)).to(self.device)
        rewards = torch.FloatTensor(np.array(rewards)).to(self.device)
        next_states = torch.FloatTensor(np.array(next_states)).to(self.device)
        dones = torch.FloatTensor(np.array(dones)).to(self.device)
        weights = torch.FloatTensor(weights).to(self.device)

        # Distributional Q-learning
        dist = self.policy_net(states)
        next_dist = self.target_net(next_states)

        # Double DQN pour la distribution
        if self.config.double_dqn:
            next_actions = self.policy_net(next_states).sum(dim=-1).argmax(dim=-1)
            next_dist = next_dist[range(self.config.batch_size), next_actions]
        else:
            next_dist = next_dist.sum(dim=-1).argmax(dim=-1)

        # Projection de la distribution
        support = self.policy_net.support
        delta_z = support[1] - support[0]

        with torch.no_grad():
            Tz = rewards.unsqueeze(1) + (1 - dones).unsqueeze(1) * self.config.gamma * support.unsqueeze(0)
            Tz = Tz.clamp(self.config.v_min, self.config.v_max)

            b = (Tz - self.config.v_min) / delta_z
            l = b.floor().long()
            u = b.ceil().long()
            l = l.clamp(0, self.config.num_atoms - 1)
            u = u.clamp(0, self.config.num_atoms - 1)

            target_dist = torch.zeros_like(next_dist)
            for i in range(self.config.batch_size):
                target_dist[i, l[i]] += next_dist[i] * (u - b)[i]
                target_dist[i, u[i]] += next_dist[i] * (b - l)[i]

        # Perte
        log_dist = dist.log()
        target_dist = target_dist.detach()
        loss = -(weights.unsqueeze(1) * target_dist * log_dist[range(self.config.batch_size), actions]).sum(dim=-1).mean()

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 1.0)
        self.optimizer.step()

        self.steps += 1

        # Mise à jour des priorités
        td_errors = (target_dist - dist[range(self.config.batch_size), actions]).detach().cpu().numpy()
        td_errors = td_errors.max(axis=1)
        self.memory.update_priorities(indices, td_errors)

        if self.steps % self.config.target_update == 0:
            self._update_target_network()

        # Reset NoisyNet
        self.policy_net.reset_noise()
        self.target_net.reset_noise()

        self._decay_epsilon()

        self.loss_history.append(loss.item())
        q_value = (dist * support).sum(dim=-1).mean().item()
        self.q_value_history.append(q_value)

        return loss.item(), q_value

    def _update_target_network(self):
        if self.config.tau < 1:
            for target_param, policy_param in zip(
                self.target_net.parameters(),
                self.policy_net.parameters()
            ):
                target_param.data.copy_(
                    self.config.tau * policy_param.data +
                    (1 - self.config.tau) * target_param.data
                )
        else:
            self.target_net.load_state_dict(self.policy_net.state_dict())

    def _decay_epsilon(self):
        self.epsilon = max(
            self.config.epsilon_end,
            self.epsilon * self.config.epsilon_decay
        )
        self.epsilon_history.append(self.epsilon)

    def get_q_values(self, state: np.ndarray) -> np.ndarray:
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            dist = self.policy_net(state_tensor)
            q_values = (dist * self.policy_net.support).sum(dim=-1)
        return q_values.cpu().numpy().flatten()

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
            'num_atoms': self.config.num_atoms,
            'n_step': self.config.n_step,
        }

        if self.reward_history:
            metrics['average_reward'] = np.mean(self.reward_history[-100:])
            metrics['best_reward'] = max(self.reward_history)

        if self.loss_history:
            metrics['average_loss'] = np.mean(self.loss_history[-100:])
            metrics['final_loss'] = self.loss_history[-1]

        return metrics

    def save(self, filepath: str) -> bool:
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
    def load(cls, filepath: str) -> 'RainbowAgent':
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)

            config = RainbowConfig(**data['config'])
            agent = cls(config)

            agent.policy_net.load_state_dict(data['policy_net_state_dict'])
            agent.target_net.load_state_dict(data['target_net_state_dict'])

            agent.epsilon = data.get('epsilon', config.epsilon_start)
            agent.steps = data.get('steps', 0)
            agent.loss_history = data.get('loss_history', [])
            agent.reward_history = data.get('reward_history', [])
            agent.epsilon_history = data.get('epsilon_history', [])
            agent.q_value_history = data.get('q_value_history', [])

            logger.info(f"Agent chargé: {filepath}")
            return agent

        except Exception as e:
            logger.error(f"Erreur lors du chargement: {e}")
            raise


def create_rainbow_agent(
    state_dim: int = 10,
    action_dim: int = 3,
    hidden_dim: int = 256,
    num_atoms: int = 51,
    memory_size: int = 100000,
    **kwargs
) -> RainbowAgent:
    config = RainbowConfig(
        state_dim=state_dim,
        action_dim=action_dim,
        hidden_dim=hidden_dim,
        num_atoms=num_atoms,
        memory_size=memory_size,
        **kwargs
    )
    return RainbowAgent(config)


__all__ = [
    'RainbowAgent',
    'RainbowConfig',
    'RainbowResult',
    'create_rainbow_agent',
]
