
# ai/models/reinforcement/replay_buffer.py
"""
NEXUS AI TRADING SYSTEM - Replay Buffer for Reinforcement Learning
Copyright © 2026 NEXUS QUANTUM LTD
"""

import logging
import numpy as np
import random
from typing import Optional, List, Dict, Any, Tuple
from collections import deque
from dataclasses import dataclass, field
import warnings
warnings.filterwarnings('ignore')

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ReplayBufferConfig:
    capacity: int = 10000
    batch_size: int = 64
    alpha: float = 0.6
    beta: float = 0.4
    beta_increment: float = 0.001
    epsilon: float = 1e-6
    n_step: int = 1
    gamma: float = 0.99
    use_prioritized: bool = False
    use_n_step: bool = False


class ReplayBuffer:
    """
    Buffer de rejeu pour l'apprentissage par renforcement.

    Supporte:
    - Buffer standard
    - Prioritized Experience Replay (PER)
    - N-step returns
    - GPU compatibility

    Example:
        ```python
        config = ReplayBufferConfig(
            capacity=10000,
            batch_size=64,
            use_prioritized=True,
            use_n_step=True,
            n_step=3
        )
        buffer = ReplayBuffer(config)

        buffer.push(state, action, reward, next_state, done)
        batch, indices, weights = buffer.sample()
        buffer.update_priorities(indices, td_errors)
        ```
    """

    def __init__(self, config: Optional[ReplayBufferConfig] = None):
        self.config = config or ReplayBufferConfig()
        self.capacity = self.config.capacity
        self.batch_size = self.config.batch_size
        self.alpha = self.config.alpha
        self.beta = self.config.beta
        self.beta_increment = self.config.beta_increment
        self.epsilon = self.config.epsilon
        self.n_step = self.config.n_step
        self.gamma = self.config.gamma
        self.use_prioritized = self.config.use_prioritized
        self.use_n_step = self.config.use_n_step

        self.buffer = deque(maxlen=self.capacity)
        self.priorities = deque(maxlen=self.capacity)
        self.position = 0
        self.n_step_buffer = deque(maxlen=self.n_step)
        self.size = 0

        logger.info(f"ReplayBuffer initialisé: capacité={self.capacity}, priorisé={self.use_prioritized}, n-step={self.n_step}")

    def push(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
        td_error: Optional[float] = None
    ):
        """
        Ajoute une transition au buffer.

        Args:
            state: État
            action: Action
            reward: Récompense
            next_state: État suivant
            done: Terminé ou non
            td_error: Erreur TD pour la priorisation
        """
        if self.use_n_step:
            self.n_step_buffer.append((state, action, reward, next_state, done))

            if len(self.n_step_buffer) == self.n_step:
                state, action, reward, next_state, done = self._get_n_step_info()

        if self.use_prioritized:
            priority = (abs(td_error) + self.epsilon) ** self.alpha if td_error is not None else 1.0
            self._push_prioritized(state, action, reward, next_state, done, priority)
        else:
            self._push_standard(state, action, reward, next_state, done)

    def _push_standard(self, state, action, reward, next_state, done):
        """Ajoute une transition standard"""
        if len(self.buffer) < self.capacity:
            self.buffer.append((state, action, reward, next_state, done))
        else:
            self.buffer[self.position] = (state, action, reward, next_state, done)

        self.position = (self.position + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)

    def _push_prioritized(self, state, action, reward, next_state, done, priority):
        """Ajoute une transition priorisée"""
        if len(self.buffer) < self.capacity:
            self.buffer.append((state, action, reward, next_state, done))
            self.priorities.append(priority)
        else:
            self.buffer[self.position] = (state, action, reward, next_state, done)
            self.priorities[self.position] = priority

        self.position = (self.position + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)

    def _get_n_step_info(self) -> Tuple[np.ndarray, int, float, np.ndarray, bool]:
        """
        Calcule la récompense n-step.

        Returns:
            Tuple: (state, action, n_step_reward, next_state, done)
        """
        rewards = []
        for i in range(self.n_step):
            rewards.append(self.n_step_buffer[i][2])

        state, action = self.n_step_buffer[0][0], self.n_step_buffer[0][1]
        next_state, done = self.n_step_buffer[-1][3], self.n_step_buffer[-1][4]

        # Calcul de la récompense n-step
        n_step_reward = 0
        for i in range(self.n_step):
            n_step_reward += (self.gamma ** i) * rewards[i]

        return state, action, n_step_reward, next_state, done

    def sample(self, batch_size: Optional[int] = None) -> Tuple:
        """
        Échantillonne un batch du buffer.

        Args:
            batch_size: Taille du batch

        Returns:
            Tuple: (states, actions, rewards, next_states, dones) ou (..., indices, weights)
        """
        if batch_size is None:
            batch_size = self.batch_size

        if len(self.buffer) < batch_size:
            return None, None, None, None, None

        if self.use_prioritized:
            return self._sample_prioritized(batch_size)
        else:
            return self._sample_standard(batch_size)

    def _sample_standard(self, batch_size: int) -> Tuple:
        """Échantillonnage standard"""
        batch = random.sample(list(self.buffer), batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)

        return np.array(states), np.array(actions), np.array(rewards), np.array(next_states), np.array(dones)

    def _sample_prioritized(self, batch_size: int) -> Tuple:
        """Échantillonnage priorisé"""
        priorities = np.array(self.priorities)
        probs = priorities ** self.alpha
        probs = probs / probs.sum()

        indices = np.random.choice(len(self.buffer), batch_size, p=probs)
        samples = [self.buffer[idx] for idx in indices]

        # Poids d'importance
        weights = (len(self.buffer) * probs[indices]) ** (-self.beta)
        weights = weights / weights.max()

        states, actions, rewards, next_states, dones = zip(*samples)

        return (
            np.array(states),
            np.array(actions),
            np.array(rewards),
            np.array(next_states),
            np.array(dones),
            indices,
            weights
        )

    def update_priorities(self, indices: List[int], td_errors: np.ndarray):
        """
        Met à jour les priorités des transitions.

        Args:
            indices: Indices des transitions
            td_errors: Erreurs TD correspondantes
        """
        if not self.use_prioritized:
            return

        for idx, td_error in zip(indices, td_errors):
            if idx < len(self.priorities):
                self.priorities[idx] = (abs(td_error) + self.epsilon) ** self.alpha

    def update_beta(self):
        """Met à jour beta pour le biais d'importance"""
        if self.use_prioritized:
            self.beta = min(1.0, self.beta + self.beta_increment)

    def clear(self):
        """Vide le buffer"""
        self.buffer.clear()
        self.priorities.clear()
        self.n_step_buffer.clear()
        self.position = 0
        self.size = 0

    def __len__(self) -> int:
        return len(self.buffer)

    def to_tensors(self, batch: Tuple, device: str = 'cpu') -> Tuple:
        """
        Convertit un batch en tenseurs PyTorch.

        Args:
            batch: Batch échantillonné
            device: Périphérique

        Returns:
            Tuple: Tenseurs
        """
        if not TORCH_AVAILABLE:
            return batch

        import torch

        if self.use_prioritized:
            states, actions, rewards, next_states, dones, indices, weights = batch
            return (
                torch.FloatTensor(states).to(device),
                torch.LongTensor(actions).to(device),
                torch.FloatTensor(rewards).to(device),
                torch.FloatTensor(next_states).to(device),
                torch.FloatTensor(dones).to(device),
                indices,
                torch.FloatTensor(weights).to(device),
            )
        else:
            states, actions, rewards, next_states, dones = batch
            return (
                torch.FloatTensor(states).to(device),
                torch.LongTensor(actions).to(device),
                torch.FloatTensor(rewards).to(device),
                torch.FloatTensor(next_states).to(device),
                torch.FloatTensor(dones).to(device),
            )

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du buffer"""
        stats = {
            'size': len(self.buffer),
            'capacity': self.capacity,
            'use_prioritized': self.use_prioritized,
            'use_n_step': self.use_n_step,
            'n_step': self.n_step,
            'beta': self.beta if self.use_prioritized else None,
            'alpha': self.alpha if self.use_prioritized else None,
        }

        if self.use_prioritized and len(self.priorities) > 0:
            stats['max_priority'] = max(self.priorities)
            stats['min_priority'] = min(self.priorities)
            stats['mean_priority'] = np.mean(self.priorities)

        return stats


class HierarchicalReplayBuffer:
    """
    Buffer de rejeu hiérarchique avec plusieurs niveaux.

    Supporte:
    - Multi-level experience storage
    - Different sampling strategies per level
    - Automatic level assignment based on TD error
    """

    def __init__(
        self,
        num_levels: int = 3,
        capacity_per_level: int = 5000,
        batch_size: int = 64,
        **kwargs
    ):
        self.num_levels = num_levels
        self.capacity_per_level = capacity_per_level
        self.batch_size = batch_size

        self.buffers = []
        self.thresholds = []

        for i in range(num_levels):
            config = ReplayBufferConfig(
                capacity=capacity_per_level,
                batch_size=batch_size // num_levels,
                use_prioritized=i > 0,
                **kwargs
            )
            self.buffers.append(ReplayBuffer(config))
            self.thresholds.append(0.1 * (i + 1))

        logger.info(f"HierarchicalReplayBuffer initialisé: {num_levels} niveaux")

    def push(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
        td_error: Optional[float] = None
    ):
        """
        Ajoute une transition au buffer approprié.

        Args:
            state: État
            action: Action
            reward: Récompense
            next_state: État suivant
            done: Terminé ou non
            td_error: Erreur TD
        """
        level = 0

        if td_error is not None:
            for i, threshold in enumerate(self.thresholds):
                if abs(td_error) > threshold:
                    level = min(i + 1, self.num_levels - 1)

        self.buffers[level].push(state, action, reward, next_state, done, td_error)

    def sample(self, batch_size: Optional[int] = None) -> Tuple:
        """
        Échantillonne un batch équilibré des différents niveaux.

        Args:
            batch_size: Taille du batch

        Returns:
            Tuple: Batch échantillonné
        """
        if batch_size is None:
            batch_size = self.batch_size

        all_samples = []
        per_level = batch_size // self.num_levels

        for buffer in self.buffers:
            if len(buffer) > 0:
                samples = buffer.sample(min(per_level, len(buffer)))
                if samples[0] is not None:
                    all_samples.append(samples)

        if not all_samples:
            return None, None, None, None, None

        # Concaténer les samples
        states = np.concatenate([s[0] for s in all_samples])
        actions = np.concatenate([s[1] for s in all_samples])
        rewards = np.concatenate([s[2] for s in all_samples])
        next_states = np.concatenate([s[3] for s in all_samples])
        dones = np.concatenate([s[4] for s in all_samples])

        return states, actions, rewards, next_states, dones

    def update_priorities(self, indices: List[int], td_errors: np.ndarray):
        """Met à jour les priorités dans tous les buffers"""
        for buffer in self.buffers:
            if buffer.use_prioritized:
                buffer.update_priorities(indices, td_errors)

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques des buffers"""
        stats = {
            'num_levels': self.num_levels,
            'total_size': sum(len(b) for b in self.buffers),
            'levels': []
        }

        for i, buffer in enumerate(self.buffers):
            level_stats = buffer.get_stats()
            level_stats['threshold'] = self.thresholds[i]
            stats['levels'].append(level_stats)

        return stats

    def clear(self):
        """Vide tous les buffers"""
        for buffer in self.buffers:
            buffer.clear()


def create_replay_buffer(
    capacity: int = 10000,
    batch_size: int = 64,
    use_prioritized: bool = False,
    use_n_step: bool = False,
    n_step: int = 1,
    **kwargs
) -> ReplayBuffer:
    config = ReplayBufferConfig(
        capacity=capacity,
        batch_size=batch_size,
        use_prioritized=use_prioritized,
        use_n_step=use_n_step,
        n_step=n_step,
        **kwargs
    )
    return ReplayBuffer(config)


def create_hierarchical_replay_buffer(
    num_levels: int = 3,
    capacity_per_level: int = 5000,
    batch_size: int = 64,
    **kwargs
) -> HierarchicalReplayBuffer:
    return HierarchicalReplayBuffer(
        num_levels=num_levels,
        capacity_per_level=capacity_per_level,
        batch_size=batch_size,
        **kwargs
    )


__all__ = [
    'ReplayBuffer',
    'ReplayBufferConfig',
    'HierarchicalReplayBuffer',
    'create_replay_buffer',
    'create_hierarchical_replay_buffer',
]
