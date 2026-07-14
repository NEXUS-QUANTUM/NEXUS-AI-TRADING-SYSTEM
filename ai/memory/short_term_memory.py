"""
NEXUS AI TRADING SYSTEM - Short-Term Memory Module
Copyright © 2026 NEXUS QUANTUM LTD

This module implements short-term and working memory for the NEXUS AI Trading System including:
- Short-term memory storage and retrieval
- Working memory with attention mechanisms
- Memory decay and forgetting
- Importance-based retention
- Temporal context tracking
- Memory consolidation preparation
- Chunking and grouping
- Pattern recognition
- Associative memory
- Priming and activation
- Interference management
- Capacity management
- Memory rehearsal
- Attention-based retrieval
- Context-dependent memory
- State-dependent memory
- Memory updating
- Memory inhibition
- Memory segmentation
- Temporal coding
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
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
import numpy as np
from scipy.spatial.distance import cosine
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import torch
import torch.nn as nn
import torch.nn.functional as F
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/short_term_memory.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Enums and Constants
# ============================================

class MemoryStatus(Enum):
    """Status of memory items."""
    ACTIVE = "active"
    DECAYING = "decaying"
    CONSOLIDATING = "consolidating"
    FORGOTTEN = "forgotten"
    PRIMED = "primed"
    INHIBITED = "inhibited"


class RetrievalStrategy(Enum):
    """Strategies for memory retrieval."""
    RECENCY = "recency"
    RELEVANCE = "relevance"
    IMPORTANCE = "importance"
    PRIMING = "priming"
    ASSOCIATION = "association"
    PATTERN = "pattern"
    CONTEXT = "context"
    RANDOM = "random"
    HYBRID = "hybrid"


class AttentionType(Enum):
    """Types of attention mechanisms."""
    FOCUSED = "focused"
    SUSTAINED = "sustained"
    SELECTIVE = "selective"
    ALTERNATING = "alternating"
    DIVIDED = "divided"
    EXECUTIVE = "executive"


@dataclass
class MemoryItem:
    """
    A single item in short-term/working memory.
    
    Attributes:
        id: Unique identifier
        content: Memory content
        timestamp: Creation timestamp
        last_accessed: Last access timestamp
        access_count: Number of accesses
        importance: Importance weight (0-1)
        decay_rate: Decay rate multiplier
        activation: Current activation level
        chunk_id: Chunk/group identifier
        associations: Associated item IDs
        context: Context vector
        embedding: Semantic embedding
        metadata: Additional metadata
        status: Current memory status
        attention_weight: Attention weight
        priming_level: Priming activation level
        inhibition_level: Inhibition level
    """
    id: str
    content: Any
    timestamp: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    importance: float = 0.5
    decay_rate: float = 1.0
    activation: float = 1.0
    chunk_id: Optional[str] = None
    associations: List[str] = field(default_factory=list)
    context: Optional[np.ndarray] = None
    embedding: Optional[np.ndarray] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: MemoryStatus = MemoryStatus.ACTIVE
    attention_weight: float = 1.0
    priming_level: float = 0.0
    inhibition_level: float = 0.0


@dataclass
class WorkingMemoryItem:
    """
    A specialized item for working memory with attention tracking.
    
    Attributes:
        id: Unique identifier
        content: Content
        timestamp: Creation timestamp
        last_accessed: Last access timestamp
        attention: Attention weight
        status: Memory status
        metadata: Additional metadata
    """
    id: str
    content: Any
    timestamp: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    attention: float = 1.0
    status: MemoryStatus = MemoryStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryChunk:
    """Chunk of grouped memory items."""
    id: str
    items: List[str]
    centroid: Optional[np.ndarray] = None
    importance: float = 0.5
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryStatistics:
    """Statistics for short-term memory."""
    total_items: int
    active_items: int
    decaying_items: int
    forgotten_items: int
    primed_items: int
    inhibited_items: int
    average_activation: float
    average_importance: float
    chunk_count: int
    memory_usage: int
    total_accesses: int
    timestamp: float


# ============================================
# Short-Term Memory Implementation
# ============================================

class ShortTermMemory:
    """
    Short-term memory for the NEXUS AI Trading System.
    
    This class implements short-term memory with decay, consolidation,
    and retrieval mechanisms for temporary storage and processing.
    """
    
    def __init__(
        self,
        max_size: int = 100,
        default_decay_rate: float = 0.1,
        consolidation_threshold: float = 0.7,
        importance_threshold: float = 0.5,
        embedding_dim: int = 128,
        memory_dir: str = "./memory/short_term",
        device: str = "cpu",
    ):
        """
        Initialize short-term memory.
        
        Args:
            max_size: Maximum number of items
            default_decay_rate: Default decay rate for items
            consolidation_threshold: Threshold for consolidation
            importance_threshold: Threshold for importance
            embedding_dim: Dimension of embeddings
            memory_dir: Directory to store memory
            device: Device for computations
        """
        self.max_size = max_size
        self.default_decay_rate = default_decay_rate
        self.consolidation_threshold = consolidation_threshold
        self.importance_threshold = importance_threshold
        self.embedding_dim = embedding_dim
        self.device = device
        
        # Storage
        self.items: Dict[str, MemoryItem] = {}
        self.item_order: List[str] = []
        self.item_index: Dict[str, int] = {}
        self.chunks: Dict[str, MemoryChunk] = {}
        
        # Statistics
        self.stats = MemoryStatistics(
            total_items=0,
            active_items=0,
            decaying_items=0,
            forgotten_items=0,
            primed_items=0,
            inhibited_items=0,
            average_activation=0.0,
            average_importance=0.0,
            chunk_count=0,
            memory_usage=0,
            total_accesses=0,
            timestamp=time.time(),
        )
        
        # Memory directory
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Tfidf for text encoding (if no embeddings)
        self.vectorizer = TfidfVectorizer(max_features=embedding_dim)
        self._fitted = False
        
        # Load existing memory
        self._load_memory()
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Short-Term Memory initialized with max_size={max_size}")
    
    # ============================================
    # Initialization Methods
    # ============================================
    
    def _generate_embedding(self, content: Any) -> Optional[np.ndarray]:
        """
        Generate embedding for content.
        
        Args:
            content: Content to embed
            
        Returns:
            Embedding vector or None
        """
        try:
            if isinstance(content, str):
                # Use TF-IDF for text
                if not self._fitted:
                    self.vectorizer.fit([content])
                    self._fitted = True
                return self.vectorizer.transform([content]).toarray()[0]
            elif isinstance(content, (list, tuple)):
                # Average embeddings of items
                embeddings = []
                for item in content:
                    emb = self._generate_embedding(item)
                    if emb is not None:
                        embeddings.append(emb)
                if embeddings:
                    return np.mean(embeddings, axis=0)
            elif isinstance(content, dict):
                # Combine string representations
                content_str = json.dumps(content, sort_keys=True)
                return self._generate_embedding(content_str)
            elif isinstance(content, np.ndarray):
                return content[:self.embedding_dim]
            elif isinstance(content, torch.Tensor):
                return content.cpu().numpy()[:self.embedding_dim]
            
            return None
        except:
            return None
    
    def _load_memory(self) -> None:
        """Load memory from disk."""
        memory_file = self.memory_dir / "memory.pkl"
        if memory_file.exists():
            try:
                with open(memory_file, 'rb') as f:
                    data = pickle.load(f)
                    self.items = data.get('items', {})
                    self.item_order = data.get('item_order', [])
                    self.item_index = data.get('item_index', {})
                    self.chunks = data.get('chunks', {})
                    self.stats = data.get('stats', self.stats)
                self.logger.info(f"Loaded {len(self.items)} items from memory")
            except Exception as e:
                self.logger.warning(f"Failed to load memory: {e}")
    
    def _save_memory(self) -> None:
        """Save memory to disk."""
        try:
            data = {
                'items': self.items,
                'item_order': self.item_order,
                'item_index': self.item_index,
                'chunks': self.chunks,
                'stats': self.stats,
            }
            with open(self.memory_dir / "memory.pkl", 'wb') as f:
                pickle.dump(data, f)
            self.logger.debug("Memory saved to disk")
        except Exception as e:
            self.logger.warning(f"Failed to save memory: {e}")
    
    # ============================================
    # Memory Storage
    # ============================================
    
    def store_memory(
        self,
        content: Any,
        importance: float = 0.5,
        decay_rate: Optional[float] = None,
        chunk_id: Optional[str] = None,
        associations: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[np.ndarray] = None,
        generate_embedding: bool = True,
    ) -> str:
        """
        Store an item in short-term memory.
        
        Args:
            content: Content to store
            importance: Importance weight
            decay_rate: Decay rate (default: default_decay_rate)
            chunk_id: Chunk/group identifier
            associations: Associated item IDs
            metadata: Additional metadata
            context: Context vector
            generate_embedding: Whether to generate embedding
            
        Returns:
            Item ID
        """
        # Check capacity
        if len(self.items) >= self.max_size:
            self._forget_oldest()
        
        # Create item
        item_id = hashlib.md5(
            f"{time.time()}_{np.random.rand()}_{str(content)}".encode()
        ).hexdigest()[:16]
        
        item = MemoryItem(
            id=item_id,
            content=content,
            importance=importance,
            decay_rate=decay_rate or self.default_decay_rate,
            chunk_id=chunk_id,
            associations=associations or [],
            metadata=metadata or {},
            context=context,
            timestamp=time.time(),
            last_accessed=time.time(),
        )
        
        # Generate embedding
        if generate_embedding:
            item.embedding = self._generate_embedding(content)
        
        # Store item
        self.items[item_id] = item
        self.item_order.append(item_id)
        self.item_index[item_id] = len(self.item_order) - 1
        
        # Update chunk if specified
        if chunk_id and chunk_id in self.chunks:
            self.chunks[chunk_id].items.append(item_id)
            self._update_chunk_centroid(chunk_id)
        
        # Update statistics
        self._update_stats()
        
        # Save periodically
        if len(self.items) % 10 == 0:
            self._save_memory()
        
        self.logger.debug(f"Stored memory item {item_id}")
        return item_id
    
    def update_memory(
        self,
        item_id: str,
        content: Optional[Any] = None,
        importance: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        associations: Optional[List[str]] = None,
    ) -> bool:
        """
        Update an existing memory item.
        
        Args:
            item_id: Item ID to update
            content: New content
            importance: New importance
            metadata: New metadata
            associations: New associations
            
        Returns:
            True if updated
        """
        if item_id not in self.items:
            return False
        
        item = self.items[item_id]
        if content is not None:
            item.content = content
            item.embedding = self._generate_embedding(content)
        if importance is not None:
            item.importance = importance
        if metadata is not None:
            item.metadata.update(metadata)
        if associations is not None:
            item.associations.extend(associations)
            item.associations = list(set(item.associations))
        
        item.last_accessed = time.time()
        item.access_count += 1
        
        self._update_stats()
        return True
    
    # ============================================
    # Memory Retrieval
    # ============================================
    
    def retrieve_memory(
        self,
        query: Any,
        n: int = 5,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
        min_importance: float = 0.0,
        max_importance: float = 1.0,
        include_decaying: bool = False,
        context: Optional[np.ndarray] = None,
    ) -> List[MemoryItem]:
        """
        Retrieve items from memory.
        
        Args:
            query: Query for retrieval
            n: Number of items to retrieve
            strategy: Retrieval strategy
            min_importance: Minimum importance threshold
            max_importance: Maximum importance threshold
            include_decaying: Include decaying items
            context: Context for retrieval
            
        Returns:
            List of retrieved items
        """
        # Filter items
        available = []
        for item in self.items.values():
            if item.importance < min_importance or item.importance > max_importance:
                continue
            if not include_decaying and item.status == MemoryStatus.DECAYING:
                continue
            if item.status == MemoryStatus.FORGOTTEN:
                continue
            available.append(item)
        
        if not available:
            return []
        
        # Apply retrieval strategy
        if strategy == RetrievalStrategy.RECENCY:
            # Retrieve most recent
            items = sorted(available, key=lambda x: x.timestamp, reverse=True)[:n]
            
        elif strategy == RetrievalStrategy.RELEVANCE:
            # Retrieve by relevance (requires embedding)
            if query is not None:
                query_embedding = self._generate_embedding(query)
                if query_embedding is not None:
                    items = self._relevance_search(query_embedding, n, available)
                else:
                    items = available[:n]
            else:
                items = available[:n]
        
        elif strategy == RetrievalStrategy.IMPORTANCE:
            # Retrieve by importance
            items = sorted(available, key=lambda x: x.importance, reverse=True)[:n]
        
        elif strategy == RetrievalStrategy.PRIMING:
            # Retrieve by priming level
            items = sorted(available, key=lambda x: x.priming_level, reverse=True)[:n]
        
        elif strategy == RetrievalStrategy.ASSOCIATION:
            # Retrieve by associations
            if isinstance(query, str) and query in self.items:
                source = self.items[query]
                associated = []
                for assoc_id in source.associations:
                    if assoc_id in self.items:
                        associated.append(self.items[assoc_id])
                items = associated[:n]
            else:
                items = available[:n]
        
        elif strategy == RetrievalStrategy.PATTERN:
            # Pattern-based retrieval
            items = self._pattern_retrieval(query, available, n)
        
        elif strategy == RetrievalStrategy.CONTEXT:
            # Context-based retrieval
            if context is not None:
                items = self._context_retrieval(context, n, available)
            else:
                items = available[:n]
        
        elif strategy == RetrievalStrategy.RANDOM:
            # Random retrieval
            indices = np.random.choice(len(available), min(n, len(available)), replace=False)
            items = [available[i] for i in indices]
        
        else:  # HYBRID - combine multiple strategies
            items = self._hybrid_retrieval(query, n, available, context)
        
        # Update access statistics
        for item in items:
            item.last_accessed = time.time()
            item.access_count += 1
            item.activation = min(1.0, item.activation + 0.1)
            item.priming_level = min(1.0, item.priming_level + 0.2)
        
        self.stats.total_accesses += len(items)
        self._update_stats()
        
        return items
    
    def _relevance_search(
        self,
        query_embedding: np.ndarray,
        n: int,
        candidates: List[MemoryItem]
    ) -> List[MemoryItem]:
        """
        Search by relevance using embeddings.
        
        Args:
            query_embedding: Query embedding
            n: Number of items to retrieve
            candidates: Candidate items
            
        Returns:
            List of relevant items
        """
        if not candidates:
            return []
        
        # Get embeddings for candidates
        embeddings = []
        items = []
        for item in candidates:
            if item.embedding is not None:
                embeddings.append(item.embedding)
                items.append(item)
        
        if not embeddings:
            return candidates[:n]
        
        # Compute similarities
        embeddings = np.array(embeddings)
        query_embedding = query_embedding.reshape(1, -1)
        
        similarities = cosine_similarity(query_embedding, embeddings)[0]
        sorted_indices = np.argsort(similarities)[::-1][:n]
        
        return [items[i] for i in sorted_indices]
    
    def _pattern_retrieval(
        self,
        query: Any,
        candidates: List[MemoryItem],
        n: int
    ) -> List[MemoryItem]:
        """
        Pattern-based retrieval.
        
        Args:
            query: Query
            candidates: Candidate items
            n: Number of items to retrieve
            
        Returns:
            List of pattern-matched items
        """
        results = []
        query_str = str(query).lower()
        
        for item in candidates:
            content_str = str(item.content).lower()
            # Simple pattern matching
            if query_str in content_str:
                results.append(item)
                if len(results) >= n:
                    break
        
        # Fallback to recency
        if not results:
            results = candidates[:n]
        
        return results
    
    def _context_retrieval(
        self,
        query_context: np.ndarray,
        n: int,
        candidates: List[MemoryItem]
    ) -> List[MemoryItem]:
        """
        Context-based retrieval.
        
        Args:
            query_context: Context vector
            n: Number of items to retrieve
            candidates: Candidate items
            
        Returns:
            List of context-matched items
        """
        if not candidates:
            return []
        
        # Get contexts for candidates
        contexts = []
        items = []
        for item in candidates:
            if item.context is not None:
                contexts.append(item.context)
                items.append(item)
        
        if not contexts:
            return candidates[:n]
        
        # Compute context similarities
        contexts = np.array(contexts)
        query_context = query_context.reshape(1, -1)
        
        similarities = cosine_similarity(query_context, contexts)[0]
        sorted_indices = np.argsort(similarities)[::-1][:n]
        
        return [items[i] for i in sorted_indices]
    
    def _hybrid_retrieval(
        self,
        query: Any,
        n: int,
        candidates: List[MemoryItem],
        context: Optional[np.ndarray] = None
    ) -> List[MemoryItem]:
        """
        Hybrid retrieval combining multiple strategies.
        
        Args:
            query: Query
            n: Number of items to retrieve
            candidates: Candidate items
            context: Context vector
            
        Returns:
            List of retrieved items
        """
        if not candidates:
            return []
        
        # Compute scores for each strategy
        recency_scores = self._compute_recency_scores(candidates)
        importance_scores = self._compute_importance_scores(candidates)
        activation_scores = self._compute_activation_scores(candidates)
        relevance_scores = self._compute_relevance_scores(candidates, query)
        context_scores = self._compute_context_scores(candidates, context) if context is not None else np.ones(len(candidates))
        
        # Normalize scores
        recency_norm = self._normalize_scores(recency_scores)
        importance_norm = self._normalize_scores(importance_scores)
        activation_norm = self._normalize_scores(activation_scores)
        relevance_norm = self._normalize_scores(relevance_scores)
        context_norm = self._normalize_scores(context_scores)
        
        # Weighted combination
        weights = [0.25, 0.25, 0.15, 0.2, 0.15]  # recency, importance, activation, relevance, context
        combined = (
            weights[0] * recency_norm +
            weights[1] * importance_norm +
            weights[2] * activation_norm +
            weights[3] * relevance_norm +
            weights[4] * context_norm
        )
        
        # Sort by combined score
        sorted_indices = np.argsort(combined)[::-1][:n]
        return [candidates[i] for i in sorted_indices]
    
    def _compute_recency_scores(self, items: List[MemoryItem]) -> np.ndarray:
        """Compute recency scores."""
        if not items:
            return np.array([])
        
        timestamps = np.array([item.timestamp for item in items])
        max_time = np.max(timestamps)
        min_time = np.min(timestamps)
        
        if max_time == min_time:
            return np.ones(len(items))
        
        return (timestamps - min_time) / (max_time - min_time)
    
    def _compute_importance_scores(self, items: List[MemoryItem]) -> np.ndarray:
        """Compute importance scores."""
        if not items:
            return np.array([])
        
        return np.array([item.importance for item in items])
    
    def _compute_activation_scores(self, items: List[MemoryItem]) -> np.ndarray:
        """Compute activation scores."""
        if not items:
            return np.array([])
        
        return np.array([item.activation for item in items])
    
    def _compute_relevance_scores(self, items: List[MemoryItem], query: Any) -> np.ndarray:
        """Compute relevance scores."""
        if not items or query is None:
            return np.ones(len(items)) if items else np.array([])
        
        query_embedding = self._generate_embedding(query)
        if query_embedding is None:
            return np.ones(len(items))
        
        scores = []
        for item in items:
            if item.embedding is not None:
                similarity = 1 - cosine(item.embedding, query_embedding)
                scores.append(similarity)
            else:
                scores.append(0.5)
        
        return np.array(scores)
    
    def _compute_context_scores(self, items: List[MemoryItem], context: np.ndarray) -> np.ndarray:
        """Compute context similarity scores."""
        if not items or context is None:
            return np.ones(len(items)) if items else np.array([])
        
        scores = []
        for item in items:
            if item.context is not None:
                similarity = 1 - cosine(item.context, context)
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
    # Memory Decay and Forgetting
    # ============================================
    
    def decay_memory(self, time_passed: float = 1.0) -> int:
        """
        Apply memory decay to all items.
        
        Args:
            time_passed: Time passed since last decay
            
        Returns:
            Number of items decayed
        """
        decayed = 0
        
        for item_id, item in list(self.items.items()):
            # Calculate decay
            age = time.time() - item.last_accessed
            decay_amount = item.decay_rate * self.default_decay_rate * time_passed
            
            # Apply decay to activation
            item.activation = max(0, item.activation - decay_amount)
            
            # Apply decay to importance
            if item.importance > 0.1:
                item.importance = max(0, item.importance - decay_amount * 0.5)
            
            # Update status based on activation
            if item.activation < 0.1:
                if item.importance > self.consolidation_threshold:
                    item.status = MemoryStatus.CONSOLIDATING
                else:
                    item.status = MemoryStatus.DECAYING
            
            if item.activation < 0.05 and item.importance < 0.1:
                item.status = MemoryStatus.FORGOTTEN
                self._forget_item(item_id)
                decayed += 1
        
        self._update_stats()
        return decayed
    
    def _forget_item(self, item_id: str) -> None:
        """
        Forget an item.
        
        Args:
            item_id: Item ID to forget
        """
        if item_id not in self.items:
            return
        
        item = self.items[item_id]
        item.status = MemoryStatus.FORGOTTEN
        
        # Remove from chunk
        if item.chunk_id and item.chunk_id in self.chunks:
            chunk = self.chunks[item.chunk_id]
            if item_id in chunk.items:
                chunk.items.remove(item_id)
        
        # Remove from storage
        del self.items[item_id]
        
        # Remove from order
        if item_id in self.item_order:
            self.item_order.remove(item_id)
        
        # Remove from index
        if item_id in self.item_index:
            del self.item_index[item_id]
    
    def _forget_oldest(self) -> None:
        """Forget the oldest/lowest importance item."""
        if not self.item_order:
            return
        
        # Find item with lowest importance and highest age
        forget_id = None
        min_score = float('inf')
        
        for item_id in self.item_order:
            item = self.items[item_id]
            if item.status == MemoryStatus.CONSOLIDATING:
                continue
            
            # Score: low importance + high age + low activation
            age = time.time() - item.last_accessed
            score = (1 - item.importance) + (age / 3600) + (1 - item.activation)
            
            if score < min_score:
                min_score = score
                forget_id = item_id
        
        if forget_id:
            self._forget_item(forget_id)
    
    # ============================================
    # Priming and Inhibition
    # ============================================
    
    def prime_memory(self, item_ids: List[str], intensity: float = 0.5) -> None:
        """
        Prime memory items.
        
        Args:
            item_ids: Items to prime
            intensity: Priming intensity
        """
        for item_id in item_ids:
            if item_id in self.items:
                item = self.items[item_id]
                item.priming_level = min(1.0, item.priming_level + intensity)
                item.activation = min(1.0, item.activation + intensity * 0.5)
                item.status = MemoryStatus.PRIMED
    
    def inhibit_memory(self, item_ids: List[str], intensity: float = 0.5) -> None:
        """
        Inhibit memory items.
        
        Args:
            item_ids: Items to inhibit
            intensity: Inhibition intensity
        """
        for item_id in item_ids:
            if item_id in self.items:
                item = self.items[item_id]
                item.inhibition_level = min(1.0, item.inhibition_level + intensity)
                item.activation = max(0, item.activation - intensity * 0.5)
                if item.activation < 0.1:
                    item.status = MemoryStatus.INHIBITED
    
    # ============================================
    # Chunking and Grouping
    # ============================================
    
    def create_chunk(
        self,
        item_ids: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a chunk from existing items.
        
        Args:
            item_ids: Items to include in chunk
            metadata: Additional metadata
            
        Returns:
            Chunk ID
        """
        chunk_id = hashlib.md5(
            f"{time.time()}_{np.random.rand()}_{str(item_ids)}".encode()
        ).hexdigest()[:16]
        
        chunk = MemoryChunk(
            id=chunk_id,
            items=item_ids.copy(),
            timestamp=time.time(),
            metadata=metadata or {},
        )
        
        # Calculate centroid
        embeddings = []
        for item_id in item_ids:
            if item_id in self.items and self.items[item_id].embedding is not None:
                embeddings.append(self.items[item_id].embedding)
        
        if embeddings:
            chunk.centroid = np.mean(embeddings, axis=0)
        
        # Calculate chunk importance
        if item_ids:
            chunk.importance = np.mean([
                self.items[item_id].importance for item_id in item_ids
                if item_id in self.items
            ])
        
        # Update items with chunk ID
        for item_id in item_ids:
            if item_id in self.items:
                self.items[item_id].chunk_id = chunk_id
        
        self.chunks[chunk_id] = chunk
        self._update_stats()
        
        return chunk_id
    
    def _update_chunk_centroid(self, chunk_id: str) -> None:
        """Update chunk centroid."""
        if chunk_id not in self.chunks:
            return
        
        chunk = self.chunks[chunk_id]
        embeddings = []
        for item_id in chunk.items:
            if item_id in self.items and self.items[item_id].embedding is not None:
                embeddings.append(self.items[item_id].embedding)
        
        if embeddings:
            chunk.centroid = np.mean(embeddings, axis=0)
    
    # ============================================
    # Memory Analysis
    # ============================================
    
    def _update_stats(self) -> None:
        """Update memory statistics."""
        self.stats.total_items = len(self.items)
        self.stats.active_items = sum(1 for item in self.items.values() if item.status == MemoryStatus.ACTIVE)
        self.stats.decaying_items = sum(1 for item in self.items.values() if item.status == MemoryStatus.DECAYING)
        self.stats.forgotten_items = sum(1 for item in self.items.values() if item.status == MemoryStatus.FORGOTTEN)
        self.stats.primed_items = sum(1 for item in self.items.values() if item.status == MemoryStatus.PRIMED)
        self.stats.inhibited_items = sum(1 for item in self.items.values() if item.status == MemoryStatus.INHIBITED)
        self.stats.chunk_count = len(self.chunks)
        self.stats.memory_usage = self._calculate_memory_usage()
        self.stats.timestamp = time.time()
        
        if self.items:
            self.stats.average_activation = np.mean([item.activation for item in self.items.values()])
            self.stats.average_importance = np.mean([item.importance for item in self.items.values()])
    
    def _calculate_memory_usage(self) -> int:
        """Calculate memory usage in bytes."""
        try:
            import sys
            total = 0
            for item in self.items.values():
                total += sys.getsizeof(item)
                total += sys.getsizeof(item.content)
                if item.embedding is not None:
                    total += item.embedding.nbytes
                if item.context is not None:
                    total += item.context.nbytes
            return total
        except:
            return 0
    
    def get_statistics(self) -> MemoryStatistics:
        """Get memory statistics."""
        self._update_stats()
        return self.stats
    
    def get_all_items(self) -> List[MemoryItem]:
        """Get all items."""
        return list(self.items.values())
    
    def clear(self) -> None:
        """Clear all memory."""
        self.items.clear()
        self.item_order.clear()
        self.item_index.clear()
        self.chunks.clear()
        self._update_stats()
        self._save_memory()
        self.logger.info("Memory cleared")
    
    # ============================================
    # Memory Export/Import
    # ============================================
    
    def export_memory(self, format: str = "json") -> Union[str, bytes]:
        """
        Export short-term memory.
        
        Args:
            format: Export format ('json', 'pickle')
            
        Returns:
            Exported memory data
        """
        data = {
            'metadata': {
                'version': '1.0',
                'timestamp': time.time(),
                'total_items': len(self.items),
                'embedding_dim': self.embedding_dim,
            },
            'items': {},
            'chunks': {},
            'stats': asdict(self.stats),
        }
        
        for item_id, item in self.items.items():
            item_data = asdict(item)
            if item_data.get('embedding') is not None:
                item_data['embedding'] = item_data['embedding'].tolist()
            if item_data.get('context') is not None:
                item_data['context'] = item_data['context'].tolist()
            data['items'][item_id] = item_data
        
        for chunk_id, chunk in self.chunks.items():
            data['chunks'][chunk_id] = asdict(chunk)
        
        if format == "json":
            return json.dumps(data, indent=2, default=str)
        elif format == "pickle":
            return pickle.dumps(data)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def import_memory(self, data: Union[str, bytes], format: str = "json") -> int:
        """
        Import short-term memory.
        
        Args:
            data: Memory data
            format: Data format ('json', 'pickle')
            
        Returns:
            Number of items imported
        """
        if format == "json":
            if isinstance(data, (bytes, bytearray)):
                data = data.decode('utf-8')
            loaded = json.loads(data)
        elif format == "pickle":
            loaded = pickle.loads(data)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        # Clear existing memory        self.items.clear()
        self.item_order.clear()
        self.item_index.clear()
        self.chunks.clear()
        
        # Import items
        count = 0
        for item_id, item_data in loaded.get('items', {}).items():
            # Convert embeddings back to numpy
            if 'embedding' in item_data and item_data['embedding']:
                item_data['embedding'] = np.array(item_data['embedding'])
            if 'context' in item_data and item_data['context']:
                item_data['context'] = np.array(item_data['context'])
            
            item = MemoryItem(**item_data)
            self.items[item_id] = item
            self.item_order.append(item_id)
            self.item_index[item_id] = len(self.item_order) - 1
            count += 1
        
        # Import chunks
        for chunk_id, chunk_data in loaded.get('chunks', {}).items():
            chunk = MemoryChunk(**chunk_data)
            self.chunks[chunk_id] = chunk
        
        # Restore stats
        if 'stats' in loaded:
            self.stats = MemoryStatistics(**loaded['stats'])
        
        self._update_stats()
        self._save_memory()
        self.logger.info(f"Imported {count} items")
        return count


# ============================================
# Working Memory Implementation
# ============================================

class WorkingMemory:
    """
    Working memory with attention mechanisms.
    
    This class implements working memory with attention tracking
    for active processing and manipulation of information.
    """
    
    def __init__(
        self,
        max_size: int = 20,
        memory_dir: str = "./memory/working",
    ):
        """
        Initialize working memory.
        
        Args:
            max_size: Maximum number of items
            memory_dir: Directory to store memory
        """
        self.max_size = max_size
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Storage
        self.items: Dict[str, WorkingMemoryItem] = {}
        self.item_order: List[str] = []
        self.attention_focus: Optional[str] = None
        
        # Statistics
        self.attention_distribution: Dict[str, float] = {}
        self.total_accesses = 0
        
        # Load existing memory
        self._load_memory()
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Working Memory initialized with max_size={max_size}")
    
    def _load_memory(self) -> None:
        """Load memory from disk."""
        memory_file = self.memory_dir / "memory.pkl"
        if memory_file.exists():
            try:
                with open(memory_file, 'rb') as f:
                    data = pickle.load(f)
                    self.items = data.get('items', {})
                    self.item_order = data.get('item_order', [])
                    self.attention_focus = data.get('attention_focus')
                    self.attention_distribution = data.get('attention_distribution', {})
                    self.total_accesses = data.get('total_accesses', 0)
                self.logger.info(f"Loaded {len(self.items)} items from working memory")
            except Exception as e:
                self.logger.warning(f"Failed to load working memory: {e}")
    
    def _save_memory(self) -> None:
        """Save memory to disk."""
        try:
            data = {
                'items': self.items,
                'item_order': self.item_order,
                'attention_focus': self.attention_focus,
                'attention_distribution': self.attention_distribution,
                'total_accesses': self.total_accesses,
            }
            with open(self.memory_dir / "memory.pkl", 'wb') as f:
                pickle.dump(data, f)
            self.logger.debug("Working memory saved to disk")
        except Exception as e:
            self.logger.warning(f"Failed to save working memory: {e}")
    
    def store_item(
        self,
        content: Any,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Store an item in working memory.
        
        Args:
            content: Content to store
            importance: Importance weight
            metadata: Additional metadata
            
        Returns:
            Item ID
        """
        # Check capacity
        if len(self.items) >= self.max_size:
            self._forget_oldest()
        
        item_id = hashlib.md5(
            f"{time.time()}_{np.random.rand()}_{str(content)}".encode()
        ).hexdigest()[:16]
        
        item = WorkingMemoryItem(
            id=item_id,
            content=content,
            metadata=metadata or {},
            timestamp=time.time(),
            last_accessed=time.time(),
        )
        
        # Apply attention based on importance
        item.attention = min(1.0, 0.5 + importance * 0.5)
        
        self.items[item_id] = item
        self.item_order.append(item_id)
        self.attention_distribution[item_id] = item.attention
        
        # Update focus
        if len(self.items) == 1:
            self.attention_focus = item_id
        
        self._update_attention()
        self._save_memory()
        
        self.logger.debug(f"Stored working memory item {item_id}")
        return item_id
    
    def retrieve(self, query: Any, n: int = 3) -> List[WorkingMemoryItem]:
        """
        Retrieve items from working memory.
        
        Args:
            query: Query for retrieval
            n: Number of items to retrieve
            
        Returns:
            List of retrieved items
        """
        if not self.items:
            return []
        
        # Simple relevance-based retrieval
        items = list(self.items.values())
        
        # Sort by attention and recency
        items.sort(key=lambda x: (x.attention, x.timestamp), reverse=True)
        
        # Update access
        for item in items[:n]:
            item.last_accessed = time.time()
            item.attention = min(1.0, item.attention + 0.1)
        
        self.total_accesses += n
        self._update_attention()
        self._save_memory()
        
        return items[:n]
    
    def focus_attention(self, item_id: str) -> bool:
        """
        Focus attention on a specific item.
        
        Args:
            item_id: Item to focus on
            
        Returns:
            True if focused
        """
        if item_id not in self.items:
            return False
        
        self.attention_focus = item_id
        
        # Boost attention for focused item
        self.items[item_id].attention = min(1.0, self.items[item_id].attention + 0.3)
        
        # Slightly decrease others
        for other_id in self.items:
            if other_id != item_id:
                self.items[other_id].attention = max(0, self.items[other_id].attention - 0.05)
        
        self._update_attention()
        self._save_memory()
        return True
    
    def shift_attention(self, direction: str = "next") -> Optional[str]:
        """
        Shift attention to another item.
        
        Args:
            direction: Direction to shift ('next', 'prev', 'random')
            
        Returns:
            New focus item ID or None
        """
        if len(self.items) < 2:
            return None
        
        items = list(self.items.keys())
        if self.attention_focus not in items:
            self.attention_focus = items[0]
        
        current_idx = items.index(self.attention_focus)
        
        if direction == "next":
            new_idx = (current_idx + 1) % len(items)
        elif direction == "prev":
            new_idx = (current_idx - 1) % len(items)
        else:  # random
            new_idx = np.random.randint(0, len(items))
        
        new_focus = items[new_idx]
        self.focus_attention(new_focus)
        return new_focus
    
    def _update_attention(self) -> None:
        """Update attention distribution."""
        for item_id in self.items:
            self.attention_distribution[item_id] = self.items[item_id].attention
    
    def _forget_oldest(self) -> None:
        """Forget the oldest item."""
        if not self.item_order:
            return
        
        # Find item with lowest attention
        forget_id = min(self.items.keys(), key=lambda x: self.items[x].attention)
        self.forget(forget_id)
    
    def forget(self, item_id: str) -> bool:
        """
        Forget an item.
        
        Args:
            item_id: Item ID to forget
            
        Returns:
            True if forgotten
        """
        if item_id not in self.items:
            return False
        
        del self.items[item_id]
        if item_id in self.item_order:
            self.item_order.remove(item_id)
        if item_id in self.attention_distribution:
            del self.attention_distribution[item_id]
        if self.attention_focus == item_id:
            self.attention_focus = self.item_order[0] if self.item_order else None
        
        self._update_attention()
        self._save_memory()
        return True
    
    def clear(self) -> None:
        """Clear working memory."""
        self.items.clear()
        self.item_order.clear()
        self.attention_distribution.clear()
        self.attention_focus = None
        self.total_accesses = 0
        self._save_memory()
        self.logger.info("Working memory cleared")
    
    def get_all_items(self) -> List[WorkingMemoryItem]:
        """Get all items."""
        return list(self.items.values())
    
    def get_attention_focus(self) -> Optional[WorkingMemoryItem]:
        """Get the currently focused item."""
        if self.attention_focus and self.attention_focus in self.items:
            return self.items[self.attention_focus]
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get working memory statistics."""
        return {
            'total_items': len(self.items),
            'attention_focus': self.attention_focus,
            'attention_distribution': self.attention_distribution,
            'total_accesses': self.total_accesses,
            'average_attention': np.mean([item.attention for item in self.items.values()]) if self.items else 0,
        }
    
    def _calculate_memory_usage(self) -> int:
        """Calculate memory usage in bytes."""
        try:
            import sys
            total = 0
            for item in self.items.values():
                total += sys.getsizeof(item)
                total += sys.getsizeof(item.content)
            return total
        except:
            return 0
    
    def export_memory(self, format: str = "json") -> Union[str, bytes]:
        """Export working memory."""
        data = {
            'metadata': {
                'version': '1.0',
                'timestamp': time.time(),
                'total_items': len(self.items),
            },
            'items': {},
            'attention_focus': self.attention_focus,
            'attention_distribution': self.attention_distribution,
            'total_accesses': self.total_accesses,
        }
        
        for item_id, item in self.items.items():
            data['items'][item_id] = asdict(item)
        
        if format == "json":
            return json.dumps(data, indent=2, default=str)
        elif format == "pickle":
            return pickle.dumps(data)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def import_memory(self, data: Union[str, bytes], format: str = "json") -> int:
        """Import working memory."""
        if format == "json":
            if isinstance(data, (bytes, bytearray)):
                data = data.decode('utf-8')
            loaded = json.loads(data)
        elif format == "pickle":
            loaded = pickle.loads(data)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        self.items.clear()
        self.item_order.clear()
        self.attention_distribution.clear()
        
        for item_id, item_data in loaded.get('items', {}).items():
            item = WorkingMemoryItem(**item_data)
            self.items[item_id] = item
            self.item_order.append(item_id)
            self.attention_distribution[item_id] = item.attention
        
        self.attention_focus = loaded.get('attention_focus')
        self.total_accesses = loaded.get('total_accesses', 0)
        
        self._save_memory()
        return len(self.items)


# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point for CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NEXUS Short-Term Memory CLI')
    parser.add_argument('--command', choices=['stats', 'clear', 'export', 'import'],
                       required=True, help='Command to execute')
    parser.add_argument('--memory-dir', type=str, default='./memory/short_term', help='Memory directory')
    parser.add_argument('--format', type=str, default='json', help='Export/import format')
    parser.add_argument('--file', type=str, help='File for export/import')
    parser.add_argument('--max-size', type=int, default=100, help='Maximum size')
    parser.add_argument('--embedding-dim', type=int, default=128, help='Embedding dimension')
    
    args = parser.parse_args()
    
    # Initialize memory
    memory = ShortTermMemory(
        max_size=args.max_size,
        embedding_dim=args.embedding_dim,
        memory_dir=args.memory_dir,
    )
    
    # Also initialize working memory
    working = WorkingMemory(
        max_size=20,
        memory_dir=args.memory_dir.replace('short_term', 'working'),
    )
    
    if args.command == 'stats':
        stats = memory.get_statistics()
        print("\nShort-Term Memory Statistics:")
        print("-" * 40)
        print(f"Total Items: {stats.total_items}")
        print(f"Active Items: {stats.active_items}")
        print(f"Decaying Items: {stats.decaying_items}")
        print(f"Forgotten Items: {stats.forgotten_items}")
        print(f"Primed Items: {stats.primed_items}")
        print(f"Inhibited Items: {stats.inhibited_items}")
        print(f"Average Activation: {stats.average_activation:.4f}")
        print(f"Average Importance: {stats.average_importance:.4f}")
        print(f"Chunk Count: {stats.chunk_count}")
        print(f"Memory Usage: {stats.memory_usage / 1024:.2f} KB")
        
        print("\nWorking Memory Statistics:")
        w_stats = working.get_statistics()
        print(f"Total Items: {w_stats['total_items']}")
        print(f"Attention Focus: {w_stats['attention_focus']}")
        print(f"Average Attention: {w_stats['average_attention']:.4f}")
    
    elif args.command == 'clear':
        memory.clear()
        working.clear()
        print("Memory cleared")
    
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
        print(f"Imported {count} items")


if __name__ == '__main__':
    main()
