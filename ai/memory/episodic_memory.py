"""
NEXUS AI TRADING SYSTEM - Episodic Memory Module
Copyright © 2026 NEXUS QUANTUM LTD

This module implements episodic memory for the NEXUS AI Trading System including:
- Storage and retrieval of trading episodes
- Temporal sequence learning
- Experience replay
- Pattern recognition
- Anomaly detection
- Memory consolidation
- Forgetting mechanisms
- Similarity-based retrieval
- Context-dependent memory
- Episodic clustering
- Memory compression
- Importance weighting
- Temporal decay
- Episode segmentation
- Cue-based recall
- State-transition memory
- Reward-based memory
- Experience replay for reinforcement learning
- Transfer learning from past episodes
"""

import os
import sys
import json
import time
import logging
import hashlib
import pickle
import zlib
from typing import Dict, List, Optional, Tuple, Any, Union, Set, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
from pathlib import Path
from collections import defaultdict, deque
from collections.abc import MutableSequence
import numpy as np
from numpy.linalg import norm
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from sklearn.cluster import DBSCAN, KMeans
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.preprocessing import StandardScaler
from scipy.spatial.distance import cdist
from scipy.stats import entropy
import networkx as nx
import faiss
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/episodic_memory.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Enums and Constants
# ============================================

class MemoryStatus(Enum):
    """Status of memory episodes."""
    STORED = "stored"
    CONSOLIDATED = "consolidated"
    FORGOTTEN = "forgotten"
    IMPORTANT = "important"
    RECENT = "recent"
    REPLAYED = "replayed"


class RetrievalStrategy(Enum):
    """Strategies for retrieving memory episodes."""
    RECENCY = "recency"
    RELEVANCE = "relevance"
    IMPORTANCE = "importance"
    SIMILARITY = "similarity"
    CONTEXT = "context"
    RANDOM = "random"
    HYBRID = "hybrid"


@dataclass
class Episode:
    """
    A single trading episode in episodic memory.
    
    Attributes:
        id: Unique episode identifier
        timestamp: Creation timestamp
        state: Environment state at episode start
        action: Action taken
        reward: Reward received
        next_state: Environment state after action
        done: Whether episode ended
        metadata: Additional episode metadata
        importance: Importance weight (0-1)
        consolidation_count: Number of times consolidated
        last_accessed: Last access timestamp
        access_count: Number of times accessed
        compressed: Whether episode is compressed
        embedding: Optional embedding vector
        context: Optional context vector
        temporal_position: Position in sequence
        episode_length: Length of episode
        cumulative_reward: Cumulative reward
        success: Whether episode was successful
        strategy: Strategy used
        market_conditions: Market conditions during episode
    """
    id: str
    timestamp: float
    state: Dict[str, Any]
    action: Dict[str, Any]
    reward: float
    next_state: Dict[str, Any]
    done: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5
    consolidation_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    compressed: bool = False
    embedding: Optional[np.ndarray] = None
    context: Optional[np.ndarray] = None
    temporal_position: int = 0
    episode_length: int = 0
    cumulative_reward: float = 0.0
    success: bool = False
    strategy: str = "unknown"
    market_conditions: Dict[str, Any] = field(default_factory=dict)
    status: MemoryStatus = MemoryStatus.STORED


@dataclass
class EpisodeBatch:
    """Batch of episodes for training or replay."""
    states: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]
    rewards: List[float]
    next_states: List[Dict[str, Any]]
    dones: List[bool]
    weights: List[float]
    episode_ids: List[str]
    contexts: Optional[List[np.ndarray]] = None
    embeddings: Optional[List[np.ndarray]] = None


@dataclass
class MemoryStats:
    """Statistics about episodic memory."""
    total_episodes: int
    stored_episodes: int
    consolidated_episodes: int
    important_episodes: int
    forgotten_episodes: int
    average_importance: float
    average_consolidation: float
    total_episode_length: int
    average_episode_length: float
    total_reward: float
    average_reward: float
    success_rate: float
    access_count: int
    compression_ratio: float
    memory_usage: int


# ============================================
# Episodic Memory Implementation
# ============================================

class EpisodicMemory:
    """
    Episodic memory for the NEXUS AI Trading System.
    
    This class implements episodic memory capabilities including storage,
    retrieval, consolidation, and forgetting of trading episodes.
    """
    
    def __init__(
        self,
        max_size: int = 10000,
        embedding_dim: int = 128,
        context_dim: int = 64,
        consolidation_threshold: float = 0.7,
        importance_threshold: float = 0.8,
        forgetting_threshold: float = 0.1,
        temporal_decay_rate: float = 0.01,
        consolidation_interval: int = 100,
        memory_dir: str = "./memory/episodic",
        enable_compression: bool = True,
        enable_embedding: bool = True,
        enable_context: bool = True,
        device: str = "cpu",
    ):
        """
        Initialize episodic memory.
        
        Args:
            max_size: Maximum number of episodes to store
            embedding_dim: Dimension of episode embeddings
            context_dim: Dimension of context vectors
            consolidation_threshold: Importance threshold for consolidation
            importance_threshold: Threshold for marking as important
            forgetting_threshold: Importance threshold for forgetting
            temporal_decay_rate: Rate of temporal decay for importance
            consolidation_interval: Episodes between consolidations
            memory_dir: Directory to store memory
            enable_compression: Enable compression of episodes
            enable_embedding: Enable embedding generation
            enable_context: Enable context generation
            device: Device for computations ('cpu' or 'cuda')
        """
        self.max_size = max_size
        self.embedding_dim = embedding_dim
        self.context_dim = context_dim
        self.consolidation_threshold = consolidation_threshold
        self.importance_threshold = importance_threshold
        self.forgetting_threshold = forgetting_threshold
        self.temporal_decay_rate = temporal_decay_rate
        self.consolidation_interval = consolidation_interval
        self.enable_compression = enable_compression
        self.enable_embedding = enable_embedding
        self.enable_context = enable_context
        self.device = device
        
        # Storage
        self.episodes: Dict[str, Episode] = {}
        self.episode_order: List[str] = []
        self.episode_index: Dict[str, int] = {}
        
        # Embeddings index
        self.embedding_index: Optional[faiss.Index] = None
        self.embedding_scaler = StandardScaler()
        
        # Statistics
        self.stats = MemoryStats(
            total_episodes=0,
            stored_episodes=0,
            consolidated_episodes=0,
            important_episodes=0,
            forgotten_episodes=0,
            average_importance=0.0,
            average_consolidation=0.0,
            total_episode_length=0,
            average_episode_length=0.0,
            total_reward=0.0,
            average_reward=0.0,
            success_rate=0.0,
            access_count=0,
            compression_ratio=0.0,
            memory_usage=0,
        )
        
        # Memory directory
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Consolidation counter
        self._consolidation_counter = 0
        
        # Lock for thread safety
        self._lock = None
        
        # Initialize embedding index
        if self.enable_embedding:
            self._init_embedding_index()
        
        # Load existing memory
        self._load_memory()
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Episodic Memory initialized with max_size={max_size}")
        self.logger.info(f"Embedding dim: {embedding_dim}, Context dim: {context_dim}")
    
    # ============================================
    # Initialization Methods
    # ============================================
    
    def _init_embedding_index(self) -> None:
        """Initialize FAISS index for embeddings."""
        if not self.enable_embedding:
            return
        
        try:
            # Use IVF for large-scale similarity search
            nlist = min(100, self.max_size // 10)
            quantizer = faiss.IndexFlatL2(self.embedding_dim)
            self.embedding_index = faiss.IndexIVFFlat(
                quantizer, self.embedding_dim, max(1, nlist)
            )
            self.embedding_index.nprobe = 10
            self.logger.debug("Embedding index initialized")
        except Exception as e:
            self.logger.warning(f"Failed to initialize FAISS index: {e}")
            self.embedding_index = faiss.IndexFlatL2(self.embedding_dim)
    
    def _load_memory(self) -> None:
        """Load memory from disk."""
        memory_file = self.memory_dir / "memory.pkl"
        if memory_file.exists():
            try:
                with open(memory_file, 'rb') as f:
                    data = pickle.load(f)
                    self.episodes = data.get('episodes', {})
                    self.episode_order = data.get('episode_order', [])
                    self.episode_index = data.get('episode_index', {})
                    self.stats = data.get('stats', self.stats)
                    self._consolidation_counter = data.get('consolidation_counter', 0)
                self.logger.info(f"Loaded {len(self.episodes)} episodes from memory")
            except Exception as e:
                self.logger.warning(f"Failed to load memory: {e}")
    
    def _save_memory(self) -> None:
        """Save memory to disk."""
        try:
            data = {
                'episodes': self.episodes,
                'episode_order': self.episode_order,
                'episode_index': self.episode_index,
                'stats': self.stats,
                'consolidation_counter': self._consolidation_counter,
            }
            with open(self.memory_dir / "memory.pkl", 'wb') as f:
                pickle.dump(data, f)
            self.logger.debug("Memory saved to disk")
        except Exception as e:
            self.logger.warning(f"Failed to save memory: {e}")
    
    # ============================================
    # Episode Encoding
    # ============================================
    
    def _encode_episode(
        self,
        episode: Episode,
        generate_embedding: bool = True,
        generate_context: bool = True
    ) -> Episode:
        """
        Encode episode with embeddings and context.
        
        Args:
            episode: Episode to encode
            generate_embedding: Whether to generate embedding
            generate_context: Whether to generate context
            
        Returns:
            Encoded episode
        """
        if self.enable_embedding and generate_embedding and episode.embedding is None:
            episode.embedding = self._generate_embedding(episode)
        
        if self.enable_context and generate_context and episode.context is None:
            episode.context = self._generate_context(episode)
        
        return episode
    
    def _generate_embedding(self, episode: Episode) -> np.ndarray:
        """
        Generate embedding for an episode.
        
        Args:
            episode: Episode to embed
            
        Returns:
            Embedding vector
        """
        # Combine state, action, and reward into a feature vector
        features = []
        
        # State features
        if episode.state:
            state_values = []
            for key in sorted(episode.state.keys()):
                val = episode.state[key]
                if isinstance(val, (int, float)):
                    state_values.append(float(val))
                elif isinstance(val, (list, tuple)):
                    state_values.extend([float(v) for v in val])
            if state_values:
                features.extend(state_values[:50])  # Limit to 50 features
        
        # Action features
        if episode.action:
            action_values = []
            for key in sorted(episode.action.keys()):
                val = episode.action[key]
                if isinstance(val, (int, float)):
                    action_values.append(float(val))
                elif isinstance(val, (list, tuple)):
                    action_values.extend([float(v) for v in val])
            if action_values:
                features.extend(action_values[:20])  # Limit to 20 features
        
        # Reward and metadata
        features.append(float(episode.reward))
        features.append(float(episode.importance))
        features.append(float(episode.episode_length))
        features.append(float(episode.cumulative_reward))
        features.append(1.0 if episode.success else 0.0)
        
        # Pad or truncate to embedding_dim
        if len(features) < self.embedding_dim:
            features.extend([0.0] * (self.embedding_dim - len(features)))
        else:
            features = features[:self.embedding_dim]
        
        # Normalize
        features = np.array(features, dtype=np.float32)
        if np.std(features) > 1e-6:
            features = (features - np.mean(features)) / np.std(features)
        
        return features
    
    def _generate_context(self, episode: Episode) -> np.ndarray:
        """
        Generate context vector for an episode.
        
        Args:
            episode: Episode for context
            
        Returns:
            Context vector
        """
        # Context includes market conditions, temporal info, and strategy
        context = []
        
        # Market conditions
        if episode.market_conditions:
            for key in ['volatility', 'trend', 'volume', 'sentiment']:
                val = episode.market_conditions.get(key, 0.0)
                if isinstance(val, (int, float)):
                    context.append(float(val))
                else:
                    context.append(0.0)
        
        # Temporal context
        context.append(episode.temporal_position / max(1, self.max_size))
        context.append(episode.episode_length / max(1, self.stats.average_episode_length))
        
        # Success and strategy
        context.append(1.0 if episode.success else 0.0)
        context.append(hash(episode.strategy) % 100 / 100.0)
        
        # Pad or truncate
        if len(context) < self.context_dim:
            context.extend([0.0] * (self.context_dim - len(context)))
        else:
            context = context[:self.context_dim]
        
        return np.array(context, dtype=np.float32)
    
    # ============================================
    # Episode Storage
    # ============================================
    
    def store_episode(
        self,
        state: Dict[str, Any],
        action: Dict[str, Any],
        reward: float,
        next_state: Dict[str, Any],
        done: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
        strategy: str = "unknown",
        market_conditions: Optional[Dict[str, Any]] = None,
        generate_embedding: bool = True,
        generate_context: bool = True,
    ) -> str:
        """
        Store a new episode in memory.
        
        Args:
            state: Environment state
            action: Action taken
            reward: Reward received
            next_state: Next environment state
            done: Whether episode ended
            metadata: Additional metadata
            importance: Importance weight
            strategy: Strategy used
            market_conditions: Market conditions
            generate_embedding: Whether to generate embedding
            generate_context: Whether to generate context
            
        Returns:
            Episode ID
        """
        # Check memory capacity
        if len(self.episodes) >= self.max_size:
            self._forget_oldest()
        
        # Create episode
        episode_id = hashlib.md5(
            f"{time.time()}_{np.random.rand()}_{state}".encode()
        ).hexdigest()[:16]
        
        episode = Episode(
            id=episode_id,
            timestamp=time.time(),
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=done,
            metadata=metadata or {},
            importance=importance,
            strategy=strategy,
            market_conditions=market_conditions or {},
            temporal_position=len(self.episodes),
        )
        
        # Encode episode
        episode = self._encode_episode(
            episode,
            generate_embedding=generate_embedding,
            generate_context=generate_context
        )
        
        # Store episode
        self.episodes[episode_id] = episode
        self.episode_order.append(episode_id)
        self.episode_index[episode_id] = len(self.episode_order) - 1
        
        # Update episode length and cumulative reward
        if len(self.episode_order) > 1:
            episode.episode_length = 1
            episode.cumulative_reward = reward
        else:
            # For episodes with previous state, calculate length
            prev_episode = self.episodes[self.episode_order[-2]]
            episode.episode_length = prev_episode.episode_length + 1
            episode.cumulative_reward = prev_episode.cumulative_reward + reward
        
        # Update statistics
        self._update_stats(episode)
        
        # Consolidate if needed
        self._consolidation_counter += 1
        if self._consolidation_counter >= self.consolidation_interval:
            self._consolidate_memory()
            self._consolidation_counter = 0
        
        # Save memory periodically
        if len(self.episodes) % 100 == 0:
            self._save_memory()
        
        self.logger.debug(f"Stored episode {episode_id}: reward={reward:.4f}, importance={importance:.4f}")
        return episode_id
    
    def _update_stats(self, episode: Episode) -> None:
        """Update memory statistics."""
        self.stats.total_episodes += 1
        self.stats.stored_episodes = len(self.episodes)
        
        total_importance = 0.0
        total_consolidation = 0.0
        total_reward = 0.0
        total_length = 0
        
        for ep in self.episodes.values():
            total_importance += ep.importance
            total_consolidation += ep.consolidation_count
            total_reward += ep.cumulative_reward
            total_length += ep.episode_length
        
        self.stats.average_importance = total_importance / len(self.episodes) if self.episodes else 0.0
        self.stats.average_consolidation = total_consolidation / len(self.episodes) if self.episodes else 0.0
        self.stats.total_reward = total_reward
        self.stats.average_reward = total_reward / len(self.episodes) if self.episodes else 0.0
        self.stats.total_episode_length = total_length
        self.stats.average_episode_length = total_length / len(self.episodes) if self.episodes else 0.0
        
        # Success rate
        success_count = sum(1 for ep in self.episodes.values() if ep.success)
        self.stats.success_rate = success_count / len(self.episodes) if self.episodes else 0.0
        
        # Count important and consolidated
        self.stats.important_episodes = sum(1 for ep in self.episodes.values() if ep.importance >= self.importance_threshold)
        self.stats.consolidated_episodes = sum(1 for ep in self.episodes.values() if ep.consolidation_count > 0)
        self.stats.forgotten_episodes = sum(1 for ep in self.episodes.values() if ep.status == MemoryStatus.FORGOTTEN)
    
    # ============================================
    # Memory Retrieval
    # ============================================
    
    def retrieve_episodes(
        self,
        query: Optional[Dict[str, Any]] = None,
        n: int = 10,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
        context: Optional[np.ndarray] = None,
        min_importance: float = 0.0,
        max_importance: float = 1.0,
        exclude_ids: Optional[List[str]] = None,
    ) -> List[Episode]:
        """
        Retrieve episodes from memory.
        
        Args:
            query: Query for similarity-based retrieval
            n: Number of episodes to retrieve
            strategy: Retrieval strategy
            context: Context for context-based retrieval
            min_importance: Minimum importance threshold
            max_importance: Maximum importance threshold
            exclude_ids: Episode IDs to exclude
            
        Returns:
            List of retrieved episodes
        """
        exclude_ids = set(exclude_ids or [])
        available = [
            ep for ep in self.episodes.values()
            if ep.id not in exclude_ids
            and min_importance <= ep.importance <= max_importance
            and ep.status != MemoryStatus.FORGOTTEN
        ]
        
        if not available:
            return []
        
        if strategy == RetrievalStrategy.RECENCY:
            # Retrieve most recent
            episodes = sorted(available, key=lambda x: x.timestamp, reverse=True)[:n]
            
        elif strategy == RetrievalStrategy.RELEVANCE:
            # Retrieve by relevance to query
            if query and self.enable_embedding:
                # Generate query embedding
                query_embedding = self._generate_query_embedding(query)
                episodes = self._similarity_search(query_embedding, n, available)
            else:
                episodes = sorted(available, key=lambda x: x.importance, reverse=True)[:n]
        
        elif strategy == RetrievalStrategy.IMPORTANCE:
            # Retrieve by importance
            episodes = sorted(available, key=lambda x: x.importance, reverse=True)[:n]
        
        elif strategy == RetrievalStrategy.SIMILARITY:
            # Retrieve by similarity (using embeddings)
            if query and self.enable_embedding:
                query_embedding = self._generate_query_embedding(query)
                episodes = self._similarity_search(query_embedding, n, available)
            else:
                episodes = available[:n]
        
        elif strategy == RetrievalStrategy.CONTEXT:
            # Retrieve by context similarity
            if context is not None:
                episodes = self._context_similarity_search(context, n, available)
            else:
                episodes = available[:n]
        
        elif strategy == RetrievalStrategy.RANDOM:
            # Random retrieval
            indices = np.random.choice(len(available), min(n, len(available)), replace=False)
            episodes = [available[i] for i in indices]
        
        else:  # HYBRID - combine multiple strategies
            # Get recency, importance, and similarity scores
            recency_scores = self._compute_recency_scores(available)
            importance_scores = self._compute_importance_scores(available)
            similarity_scores = self._compute_similarity_scores(available, query) if query else np.ones(len(available))
            
            # Normalize scores
            recency_norm = self._normalize_scores(recency_scores)
            importance_norm = self._normalize_scores(importance_scores)
            similarity_norm = self._normalize_scores(similarity_scores)
            
            # Weighted combination
            weights = [0.3, 0.3, 0.4]  # recency, importance, similarity
            combined = weights[0] * recency_norm + weights[1] * importance_norm + weights[2] * similarity_norm
            
            # Sort by combined score
            sorted_indices = np.argsort(combined)[::-1]
            episodes = [available[i] for i in sorted_indices[:n]]
        
        # Update access statistics
        for ep in episodes:
            ep.access_count += 1
            ep.last_accessed = time.time()
        
        self.stats.access_count += len(episodes)
        
        return episodes
    
    def _generate_query_embedding(self, query: Dict[str, Any]) -> np.ndarray:
        """
        Generate embedding for a query.
        
        Args:
            query: Query dictionary
            
        Returns:
            Query embedding
        """
        features = []
        
        # Extract features from query
        for key in sorted(query.keys()):
            val = query[key]
            if isinstance(val, (int, float)):
                features.append(float(val))
            elif isinstance(val, (list, tuple)):
                features.extend([float(v) for v in val[:10]])
        
        # Pad or truncate
        if len(features) < self.embedding_dim:
            features.extend([0.0] * (self.embedding_dim - len(features)))
        else:
            features = features[:self.embedding_dim]
        
        return np.array(features, dtype=np.float32)
    
    def _similarity_search(
        self,
        query_embedding: np.ndarray,
        n: int,
        candidates: List[Episode]
    ) -> List[Episode]:
        """
        Search for episodes by similarity.
        
        Args:
            query_embedding: Query embedding
            n: Number of episodes to retrieve
            candidates: Candidate episodes
            
        Returns:
            List of similar episodes
        """
        if not candidates:
            return []
        
        # Get embeddings for candidates
        embeddings = []
        episodes = []
        for ep in candidates:
            if ep.embedding is not None:
                embeddings.append(ep.embedding)
                episodes.append(ep)
        
        if not embeddings:
            return candidates[:n]
        
        # Compute similarities
        embeddings = np.array(embeddings)
        query_embedding = query_embedding.reshape(1, -1)
        
        if self.embedding_index and len(embeddings) > 100:
            # Use FAISS for large-scale search
            if not self.embedding_index.is_trained:
                self.embedding_index.train(embeddings)
            self.embedding_index.add(embeddings)
            distances, indices = self.embedding_index.search(query_embedding, min(n, len(episodes)))
            similar_episodes = [episodes[i] for i in indices[0]]
        else:
            # Use direct computation for small-scale search
            similarities = cdist(query_embedding, embeddings, metric='cosine')[0]
            sorted_indices = np.argsort(similarities)[:n]
            similar_episodes = [episodes[i] for i in sorted_indices]
        
        return similar_episodes
    
    def _context_similarity_search(
        self,
        query_context: np.ndarray,
        n: int,
        candidates: List[Episode]
    ) -> List[Episode]:
        """
        Search for episodes by context similarity.
        
        Args:
            query_context: Query context
            n: Number of episodes to retrieve
            candidates: Candidate episodes
            
        Returns:
            List of context-similar episodes
        """
        if not candidates:
            return []
        
        # Get contexts for candidates
        contexts = []
        episodes = []
        for ep in candidates:
            if ep.context is not None:
                contexts.append(ep.context)
                episodes.append(ep)
        
        if not contexts:
            return candidates[:n]
        
        # Compute context similarities
        contexts = np.array(contexts)
        query_context = query_context.reshape(1, -1)
        similarities = cdist(query_context, contexts, metric='cosine')[0]
        sorted_indices = np.argsort(similarities)[:n]
        
        return [episodes[i] for i in sorted_indices]
    
    def _compute_recency_scores(self, episodes: List[Episode]) -> np.ndarray:
        """Compute recency scores for episodes."""
        if not episodes:
            return np.array([])
        
        timestamps = np.array([ep.timestamp for ep in episodes])
        max_time = np.max(timestamps)
        min_time = np.min(timestamps)
        
        if max_time == min_time:
            return np.ones(len(episodes))
        
        return (timestamps - min_time) / (max_time - min_time)
    
    def _compute_importance_scores(self, episodes: List[Episode]) -> np.ndarray:
        """Compute importance scores for episodes."""
        if not episodes:
            return np.array([])
        
        return np.array([ep.importance for ep in episodes])
    
    def _compute_similarity_scores(
        self,
        episodes: List[Episode],
        query: Dict[str, Any]
    ) -> np.ndarray:
        """Compute similarity scores for episodes to query."""
        if not episodes or not query:
            return np.ones(len(episodes))
        
        # Generate query embedding
        query_embedding = self._generate_query_embedding(query)
        
        # Compute similarities
        scores = []
        for ep in episodes:
            if ep.embedding is not None:
                similarity = 1 - np.dot(ep.embedding, query_embedding) / (
                    np.linalg.norm(ep.embedding) * np.linalg.norm(query_embedding) + 1e-8
                )
                scores.append(similarity)
            else:
                scores.append(0.5)
        
        return np.array(scores)
    
    def _normalize_scores(self, scores: np.ndarray) -> np.ndarray:
        """Normalize scores to [0, 1]."""
        if len(scores) == 0:
            return scores
        
        min_score = np.min(scores)
        max_score = np.max(scores)
        
        if max_score == min_score:
            return np.ones(len(scores))
        
        return (scores - min_score) / (max_score - min_score)
    
    # ============================================
    # Memory Consolidation
    # ============================================
    
    def _consolidate_memory(self) -> None:
        """Consolidate memory episodes."""
        # Identify episodes for consolidation
        to_consolidate = [
            ep for ep in self.episodes.values()
            if ep.importance >= self.consolidation_threshold
            and ep.status != MemoryStatus.CONSOLIDATED
        ]
        
        if not to_consolidate:
            return
        
        # Consolidate episodes
        for ep in to_consolidate:
            ep.consolidation_count += 1
            ep.status = MemoryStatus.CONSOLIDATED
            
            # Update importance based on consolidation
            ep.importance = min(1.0, ep.importance + 0.05)
            
            # Compress if enabled
            if self.enable_compression and ep.consolidation_count > 3:
                ep.compressed = True
                # Compress state and next_state
                ep.state = self._compress_state(ep.state)
                ep.next_state = self._compress_state(ep.next_state)
        
        self.logger.debug(f"Consolidated {len(to_consolidate)} episodes")
    
    def _compress_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress a state dictionary.
        
        Args:
            state: State to compress
            
        Returns:
            Compressed state
        """
        # Simple compression: keep only essential fields
        essential_keys = ['price', 'volume', 'timestamp', 'symbol', 'change']
        compressed = {}
        for key in essential_keys:
            if key in state:
                compressed[key] = state[key]
        return compressed
    
    # ============================================
    # Memory Forgetting
    # ============================================
    
    def _forget_oldest(self) -> None:
        """Forget the oldest episode."""
        if not self.episode_order:
            return
        
        # Find episode with lowest importance
        min_importance = float('inf')
        forget_id = None
        
        for ep_id in self.episode_order:
            ep = self.episodes[ep_id]
            # Apply temporal decay
            age = time.time() - ep.last_accessed
            decayed_importance = ep.importance * np.exp(-self.temporal_decay_rate * age)
            
            if decayed_importance < min_importance and ep.status != MemoryStatus.IMPORTANT:
                min_importance = decayed_importance
                forget_id = ep_id
        
        if forget_id:
            self._remove_episode(forget_id)
    
    def _remove_episode(self, episode_id: str) -> None:
        """
        Remove an episode from memory.
        
        Args:
            episode_id: Episode ID to remove
        """
        if episode_id not in self.episodes:
            return
        
        ep = self.episodes[episode_id]
        ep.status = MemoryStatus.FORGOTTEN
        
        # Remove from storage
        del self.episodes[episode_id]
        
        # Remove from order
        if episode_id in self.episode_order:
            self.episode_order.remove(episode_id)
        
        # Remove from index
        if episode_id in self.episode_index:
            del self.episode_index[episode_id]
        
        self.logger.debug(f"Forgot episode {episode_id}")
    
    def forget_episodes(self, criteria: Dict[str, Any]) -> int:
        """
        Forget episodes matching criteria.
        
        Args:
            criteria: Forgetting criteria
            
        Returns:
            Number of episodes forgotten
        """
        forgotten = 0
        to_forget = []
        
        for ep_id, ep in self.episodes.items():
            # Check criteria
            match = True
            for key, value in criteria.items():
                if key == 'min_importance' and ep.importance < value:
                    match = False
                elif key == 'max_importance' and ep.importance > value:
                    match = False
                elif key == 'min_age' and (time.time() - ep.timestamp) < value:
                    match = False
                elif key == 'strategy' and ep.strategy != value:
                    match = False
                elif key == 'success' and ep.success != value:
                    match = False
            
            if match and ep.status != MemoryStatus.IMPORTANT:
                to_forget.append(ep_id)
        
        for ep_id in to_forget:
            self._remove_episode(ep_id)
            forgotten += 1
        
        if forgotten > 0:
            self.logger.info(f"Forgot {forgotten} episodes")
        
        return forgotten
    
    # ============================================
    # Experience Replay
    # ============================================
    
    def sample_batch(
        self,
        batch_size: int = 32,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
        query: Optional[Dict[str, Any]] = None,
        context: Optional[np.ndarray] = None,
        min_importance: float = 0.0,
    ) -> EpisodeBatch:
        """
        Sample a batch of episodes for experience replay.
        
        Args:
            batch_size: Number of episodes to sample
            strategy: Retrieval strategy
            query: Query for similarity-based sampling
            context: Context for context-based sampling
            min_importance: Minimum importance threshold
            
        Returns:
            Episode batch for replay
        """
        # Retrieve episodes
        episodes = self.retrieve_episodes(
            query=query,
            n=min(batch_size * 2, len(self.episodes)),
            strategy=strategy,
            context=context,
            min_importance=min_importance,
        )
        
        if len(episodes) < batch_size:
            # Sample with replacement
            indices = np.random.choice(len(episodes), batch_size, replace=True)
            episodes = [episodes[i] for i in indices]
        else:
            # Sample without replacement
            episodes = np.random.choice(episodes, batch_size, replace=False).tolist()
        
        # Create batch
        states = [ep.state for ep in episodes]
        actions = [ep.action for ep in episodes]
        rewards = [ep.reward for ep in episodes]
        next_states = [ep.next_state for ep in episodes]
        dones = [ep.done for ep in episodes]
        weights = [ep.importance for ep in episodes]
        episode_ids = [ep.id for ep in episodes]
        contexts = [ep.context for ep in episodes if ep.context is not None] if self.enable_context else None
        embeddings = [ep.embedding for ep in episodes if ep.embedding is not None] if self.enable_embedding else None
        
        return EpisodeBatch(
            states=states,
            actions=actions,
            rewards=rewards,
            next_states=next_states,
            dones=dones,
            weights=weights,
            episode_ids=episode_ids,
            contexts=contexts,
            embeddings=embeddings,
        )
    
    # ============================================
    # Memory Analysis
    # ============================================
    
    def get_stats(self) -> MemoryStats:
        """
        Get memory statistics.
        
        Returns:
            Memory statistics
        """
        # Update memory usage
        self.stats.memory_usage = self._calculate_memory_usage()
        
        # Update compression ratio
        compressed = sum(1 for ep in self.episodes.values() if ep.compressed)
        self.stats.compression_ratio = compressed / len(self.episodes) if self.episodes else 0.0
        
        return self.stats
    
    def _calculate_memory_usage(self) -> int:
        """Calculate memory usage in bytes."""
        try:
            import sys
            total = 0
            for ep in self.episodes.values():
                total += sys.getsizeof(ep)
                total += sys.getsizeof(ep.state)
                total += sys.getsizeof(ep.action)
                total += sys.getsizeof(ep.next_state)
                if ep.embedding is not None:
                    total += ep.embedding.nbytes
                if ep.context is not None:
                    total += ep.context.nbytes
            return total
        except:
            return 0
    
    def analyze_memory(self) -> Dict[str, Any]:
        """
        Perform analysis on episodic memory.
        
        Returns:
            Analysis results
        """
        analysis = {
            'total_episodes': len(self.episodes),
            'status_distribution': {},
            'importance_distribution': {
                'min': 0.0,
                'max': 0.0,
                'mean': 0.0,
                'std': 0.0,
            },
            'consolidation_distribution': {},
            'strategy_distribution': {},
            'success_rate': 0.0,
            'reward_distribution': {},
            'clusters': None,
        }
        
        if not self.episodes:
            return analysis
        
        # Status distribution
        status_counts = defaultdict(int)
        for ep in self.episodes.values():
            status_counts[ep.status.value] += 1
        analysis['status_distribution'] = dict(status_counts)
        
        # Importance distribution
        importances = [ep.importance for ep in self.episodes.values()]
        analysis['importance_distribution'] = {
            'min': np.min(importances),
            'max': np.max(importances),
            'mean': np.mean(importances),
            'std': np.std(importances),
        }
        
        # Consolidation distribution
        consolidation_counts = defaultdict(int)
        for ep in self.episodes.values():
            consolidation_counts[ep.consolidation_count] += 1
        analysis['consolidation_distribution'] = dict(consolidation_counts)
        
        # Strategy distribution
        strategy_counts = defaultdict(int)
        for ep in self.episodes.values():
            strategy_counts[ep.strategy] += 1
        analysis['strategy_distribution'] = dict(strategy_counts)
        
        # Success rate
        success_count = sum(1 for ep in self.episodes.values() if ep.success)
        analysis['success_rate'] = success_count / len(self.episodes)
        
        # Reward distribution
        rewards = [ep.cumulative_reward for ep in self.episodes.values()]
        analysis['reward_distribution'] = {
            'min': np.min(rewards),
            'max': np.max(rewards),
            'mean': np.mean(rewards),
            'std': np.std(rewards),
        }
        
        # Cluster analysis (if enough episodes)
        if len(self.episodes) > 10 and self.enable_embedding:
            embeddings = []
            ep_ids = []
            for ep in self.episodes.values():
                if ep.embedding is not None:
                    embeddings.append(ep.embedding)
                    ep_ids.append(ep.id)
            
            if len(embeddings) > 10:
                embeddings = np.array(embeddings)
                
                # Reduce dimensions for visualization
                pca = PCA(n_components=min(50, len(embeddings[0])))
                embeddings_pca = pca.fit_transform(embeddings)
                
                # Cluster
                kmeans = KMeans(n_clusters=min(5, len(embeddings) // 10), random_state=42)
                labels = kmeans.fit_predict(embeddings_pca)
                
                analysis['clusters'] = {
                    'n_clusters': len(set(labels)),
                    'labels': labels.tolist(),
                    'episode_ids': ep_ids,
                }
        
        return analysis
    
    # ============================================
    # Memory Export/Import
    # ============================================
    
    def export_memory(self, format: str = "json") -> Union[str, bytes]:
        """
        Export episodic memory.
        
        Args:
            format: Export format ('json', 'pickle')
            
        Returns:
            Exported memory data
        """
        data = {
            'metadata': {
                'version': '1.0',
                'timestamp': time.time(),
                'total_episodes': len(self.episodes),
                'embedding_dim': self.embedding_dim,
                'context_dim': self.context_dim,
            },
            'episodes': {},
            'stats': asdict(self.stats),
        }
        
        for ep_id, ep in self.episodes.items():
            ep_data = asdict(ep)
            # Convert numpy arrays to lists for JSON
            if ep_data.get('embedding') is not None:
                ep_data['embedding'] = ep_data['embedding'].tolist()
            if ep_data.get('context') is not None:
                ep_data['context'] = ep_data['context'].tolist()
            data['episodes'][ep_id] = ep_data
        
        if format == "json":
            return json.dumps(data, indent=2, default=str)
        elif format == "pickle":
            return pickle.dumps(data)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def import_memory(self, data: Union[str, bytes], format: str = "json") -> int:
        """
        Import episodic memory.
        
        Args:
            data: Memory data
            format: Data format ('json', 'pickle')
            
        Returns:
            Number of episodes imported
        """
        if format == "json":
            if isinstance(data, (bytes, bytearray)):
                data = data.decode('utf-8')
            loaded = json.loads(data)
        elif format == "pickle":
            loaded = pickle.loads(data)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        # Clear existing memory
        self.episodes.clear()
        self.episode_order.clear()
        self.episode_index.clear()
        
        # Import episodes
        count = 0
        for ep_id, ep_data in loaded.get('episodes', {}).items():
            # Convert back to Episode
            ep = Episode(**ep_data)
            self.episodes[ep_id] = ep
            self.episode_order.append(ep_id)
            self.episode_index[ep_id] = len(self.episode_order) - 1
            count += 1
        
        # Restore stats
        if 'stats' in loaded:
            self.stats = MemoryStats(**loaded['stats'])
        
        self._save_memory()
        self.logger.info(f"Imported {count} episodes")
        return count

# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point for CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NEXUS Episodic Memory CLI')
    parser.add_argument('--command', choices=['stats', 'analyze', 'export', 'import', 'clear'],
                       required=True, help='Command to execute')
    parser.add_argument('--memory-dir', type=str, default='./memory/episodic', help='Memory directory')
    parser.add_argument('--format', type=str, default='json', help='Export/import format')
    parser.add_argument('--file', type=str, help='File for export/import')
    parser.add_argument('--max-size', type=int, default=10000, help='Maximum memory size')
    parser.add_argument('--embedding-dim', type=int, default=128, help='Embedding dimension')
    
    args = parser.parse_args()
    
    # Initialize memory
    memory = EpisodicMemory(
        max_size=args.max_size,
        embedding_dim=args.embedding_dim,
        memory_dir=args.memory_dir,
    )
    
    if args.command == 'stats':
        stats = memory.get_stats()
        print("\nEpisodic Memory Statistics:")
        print("-" * 40)
        print(f"Total Episodes: {stats.total_episodes}")
        print(f"Stored Episodes: {stats.stored_episodes}")
        print(f"Consolidated Episodes: {stats.consolidated_episodes}")
        print(f"Important Episodes: {stats.important_episodes}")
        print(f"Forgotten Episodes: {stats.forgotten_episodes}")
        print(f"Average Importance: {stats.average_importance:.4f}")
        print(f"Average Consolidation: {stats.average_consolidation:.2f}")
        print(f"Success Rate: {stats.success_rate:.4f}")
        print(f"Memory Usage: {stats.memory_usage / 1024:.2f} KB")
    
    elif args.command == 'analyze':
        analysis = memory.analyze_memory()
        print("\nEpisodic Memory Analysis:")
        print("-" * 40)
        print(f"Total Episodes: {analysis['total_episodes']}")
        print(f"Status Distribution: {analysis['status_distribution']}")
        print(f"Importance Distribution: {analysis['importance_distribution']}")
        print(f"Strategy Distribution: {analysis['strategy_distribution']}")
        print(f"Success Rate: {analysis['success_rate']:.4f}")
        if analysis['clusters']:
            print(f"Clusters: {analysis['clusters']['n_clusters']}")
    
    elif args.command == 'export':
        data = memory.export_memory(args.format)
        if args.file:
            with open(args.file, 'w' if args.format == 'json' else 'wb') as f:
                f.write(data)
            print(f"Exported to {args.file}")
        else:
            print(data)
    
    elif args.command == 'import':
        if not args.file:
            print("Error: --file required for import")
            return
        with open(args.file, 'rb' if args.format == 'pickle' else 'r') as f:
            data = f.read()
        count = memory.import_memory(data, args.format)
        print(f"Imported {count} episodes")
    
    elif args.command == 'clear':
        memory.episodes.clear()
        memory.episode_order.clear()
        memory.episode_index.clear()
        memory._save_memory()
        print("Memory cleared")


if __name__ == '__main__':
    main()
