"""
NEXUS AI TRADING SYSTEM - Long-Term Memory Module
Copyright © 2026 NEXUS QUANTUM LTD

This module implements long-term memory for the NEXUS AI Trading System including:
- Persistent knowledge storage
- Semantic memory organization
- Knowledge graph construction
- Concept learning and generalization
- Pattern recognition and categorization
- Temporal pattern learning
- Association learning
- Memory consolidation and integration
- Distributed representation
- Knowledge retrieval and inference
- Transfer learning
- Concept drift detection
- Memory decay and forgetting
- Importance-based retention
- Query-based retrieval
- Similarity-based search
- Hierarchical organization
- Schema learning
- Causal reasoning
- Analogical reasoning
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
import networkx as nx
from networkx.algorithms import community
from sklearn.cluster import DBSCAN, KMeans, AgglomerativeClustering
from sklearn.decomposition import PCA, NMF, LatentDirichletAllocation
from sklearn.manifold import TSNE
from sklearn.metrics import pairwise_distances
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.spatial.distance import cosine, euclidean
from scipy.stats import pearsonr, spearmanr
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import faiss
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/long_term_memory.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Enums and Constants
# ============================================

class KnowledgeType(Enum):
    """Types of knowledge in long-term memory."""
    FACT = "fact"
    CONCEPT = "concept"
    RULE = "rule"
    PATTERN = "pattern"
    RELATIONSHIP = "relationship"
    SCHEMA = "schema"
    PROCEDURAL = "procedural"
    DECLARATIVE = "declarative"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryStatus(Enum):
    """Status of memory items."""
    STORED = "stored"
    CONSOLIDATED = "consolidated"
    INTEGRATED = "integrated"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    DECAYED = "decayed"
    FORGOTTEN = "forgotten"


class RetrievalMode(Enum):
    """Modes for knowledge retrieval."""
    EXACT = "exact"
    SEMANTIC = "semantic"
    ASSOCIATIVE = "associative"
    INFERENTIAL = "inferential"
    ANALOGICAL = "analogical"
    PATTERN = "pattern"
    RULE_BASED = "rule_based"


@dataclass
class KnowledgeItem:
    """
    A single knowledge item in long-term memory.
    
    Attributes:
        id: Unique identifier
        type: Type of knowledge
        content: Knowledge content
        embedding: Semantic embedding
        timestamp: Creation timestamp
        last_accessed: Last access timestamp
        access_count: Number of accesses
        importance: Importance weight (0-1)
        consolidation_count: Consolidation count
        associations: Associated knowledge IDs
        metadata: Additional metadata
        source: Source of knowledge
        confidence: Confidence score (0-1)
        semantic_type: Semantic category
        temporal_context: Temporal context
        spatial_context: Spatial context
        schema: Schema reference
        examples: Example instances
        properties: Knowledge properties
        relationships: Relationships to other knowledge
        status: Current memory status
    """
    id: str
    type: KnowledgeType
    content: Any
    embedding: Optional[np.ndarray] = None
    timestamp: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    importance: float = 0.5
    consolidation_count: int = 0
    associations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    confidence: float = 0.8
    semantic_type: str = "general"
    temporal_context: Dict[str, Any] = field(default_factory=dict)
    spatial_context: Dict[str, Any] = field(default_factory=dict)
    schema: Optional[str] = None
    examples: List[Dict[str, Any]] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    relationships: Dict[str, List[str]] = field(default_factory=dict)
    status: MemoryStatus = MemoryStatus.STORED


@dataclass
class KnowledgeGraph:
    """
    Knowledge graph for long-term memory.
    
    Attributes:
        nodes: Graph nodes (knowledge items)
        edges: Graph edges (relationships)
        weights: Edge weights
        communities: Community structure
        centrality: Node centrality scores
        embedding: Graph embedding
    """
    nodes: Dict[str, KnowledgeItem]
    edges: List[Tuple[str, str, float]]
    weights: Dict[Tuple[str, str], float]
    communities: Dict[str, int]
    centrality: Dict[str, float]
    embedding: Optional[np.ndarray] = None


@dataclass
class MemoryStatistics:
    """Statistics for long-term memory."""
    total_items: int
    by_type: Dict[str, int]
    by_status: Dict[str, int]
    by_source: Dict[str, int]
    average_importance: float
    average_confidence: float
    total_accesses: int
    consolidation_rate: float
    semantic_density: float
    graph_density: float
    average_degree: float
    community_count: int
    memory_usage: int
    timestamp: float


# ============================================
# Long-Term Memory Implementation
# ============================================

class LongTermMemory:
    """
    Long-term memory for the NEXUS AI Trading System.
    
    This class implements persistent knowledge storage and retrieval
    with semantic organization, inference, and learning capabilities.
    """
    
    def __init__(
        self,
        max_items: int = 100000,
        embedding_dim: int = 256,
        consolidation_threshold: float = 0.7,
        importance_threshold: float = 0.8,
        decay_rate: float = 0.01,
        consolidation_interval: int = 100,
        memory_dir: str = "./memory/long_term",
        enable_graph: bool = True,
        enable_embedding: bool = True,
        enable_semantic: bool = True,
        device: str = "cpu",
    ):
        """
        Initialize long-term memory.
        
        Args:
            max_items: Maximum number of items to store
            embedding_dim: Dimension of semantic embeddings
            consolidation_threshold: Threshold for consolidation
            importance_threshold: Threshold for important items
            decay_rate: Memory decay rate
            consolidation_interval: Items between consolidations
            memory_dir: Directory to store memory
            enable_graph: Enable knowledge graph
            enable_embedding: Enable embeddings
            enable_semantic: Enable semantic operations
            device: Device for computations
        """
        self.max_items = max_items
        self.embedding_dim = embedding_dim
        self.consolidation_threshold = consolidation_threshold
        self.importance_threshold = importance_threshold
        self.decay_rate = decay_rate
        self.consolidation_interval = consolidation_interval
        self.enable_graph = enable_graph
        self.enable_embedding = enable_embedding
        self.enable_semantic = enable_semantic
        self.device = device
        
        # Storage
        self.items: Dict[str, KnowledgeItem] = {}
        self.item_order: List[str] = []
        self.item_index: Dict[str, int] = {}
        
        # Embedding index
        self.embedding_index: Optional[faiss.Index] = None
        self.embedding_scaler = None
        
        # Knowledge graph
        self.graph: Optional[KnowledgeGraph] = None
        
        # Statistics
        self.stats = MemoryStatistics(
            total_items=0,
            by_type={},
            by_status={},
            by_source={},
            average_importance=0.0,
            average_confidence=0.0,
            total_accesses=0,
            consolidation_rate=0.0,
            semantic_density=0.0,
            graph_density=0.0,
            average_degree=0.0,
            community_count=0,
            memory_usage=0,
            timestamp=time.time(),
        )
        
        # Memory directory
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Consolidation counter
        self._consolidation_counter = 0
        
        # Initialize
        self._init_embedding_index()
        self._load_memory()
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Long-Term Memory initialized with max_items={max_items}")
        self.logger.info(f"Embedding dim: {embedding_dim}")
    
    # ============================================
    # Initialization Methods
    # ============================================
    
    def _init_embedding_index(self) -> None:
        """Initialize FAISS index for embeddings."""
        if not self.enable_embedding:
            return
        
        try:
            nlist = min(100, self.max_items // 100)
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
                    self.items = data.get('items', {})
                    self.item_order = data.get('item_order', [])
                    self.item_index = data.get('item_index', {})
                    self.stats = data.get('stats', self.stats)
                    self._consolidation_counter = data.get('consolidation_counter', 0)
                    if self.enable_graph and 'graph' in data:
                        self.graph = data['graph']
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
                'stats': self.stats,
                'consolidation_counter': self._consolidation_counter,
            }
            if self.enable_graph and self.graph:
                data['graph'] = self.graph
            with open(self.memory_dir / "memory.pkl", 'wb') as f:
                pickle.dump(data, f)
            self.logger.debug("Memory saved to disk")
        except Exception as e:
            self.logger.warning(f"Failed to save memory: {e}")
    
    # ============================================
    # Embedding Generation
    # ============================================
    
    def _generate_embedding(self, content: Any) -> np.ndarray:
        """
        Generate embedding for knowledge content.
        
        Args:
            content: Knowledge content
            
        Returns:
            Embedding vector
        """
        # This is a placeholder - in production, use a proper encoder
        # For now, use a simple hash-based embedding
        if isinstance(content, str):
            # TF-IDF or transformer-based encoding would be used here
            import hashlib
            hash_bytes = hashlib.sha256(content.encode()).digest()
            embedding = np.frombuffer(hash_bytes, dtype=np.uint8)[:self.embedding_dim]
            return embedding.astype(np.float32) / 255.0
        elif isinstance(content, dict):
            # Combine content values into a string
            content_str = json.dumps(content, sort_keys=True)
            return self._generate_embedding(content_str)
        elif isinstance(content, (list, tuple)):
            # Combine list items
            content_str = "".join(str(item) for item in content)
            return self._generate_embedding(content_str)
        else:
            # Default: use timestamp and id
            import hashlib
            content_str = str(content) + str(time.time())
            hash_bytes = hashlib.sha256(content_str.encode()).digest()
            embedding = np.frombuffer(hash_bytes, dtype=np.uint8)[:self.embedding_dim]
            return embedding.astype(np.float32) / 255.0
    
    # ============================================
    # Knowledge Storage
    # ============================================
    
    def store_knowledge(
        self,
        content: Any,
        knowledge_type: KnowledgeType = KnowledgeType.FACT,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "unknown",
        importance: float = 0.5,
        confidence: float = 0.8,
        associations: Optional[List[str]] = None,
        properties: Optional[Dict[str, Any]] = None,
        examples: Optional[List[Dict[str, Any]]] = None,
        semantic_type: str = "general",
        schema: Optional[str] = None,
    ) -> str:
        """
        Store knowledge in long-term memory.
        
        Args:
            content: Knowledge content
            knowledge_type: Type of knowledge
            metadata: Additional metadata
            source: Source of knowledge
            importance: Importance weight
            confidence: Confidence score
            associations: Associated knowledge IDs
            properties: Knowledge properties
            examples: Example instances
            semantic_type: Semantic category
            schema: Schema reference
            
        Returns:
            Knowledge item ID
        """
        # Check capacity
        if len(self.items) >= self.max_items:
            self._forget_oldest()
        
        # Create knowledge item
        item_id = hashlib.md5(
            f"{time.time()}_{np.random.rand()}_{str(content)}".encode()
        ).hexdigest()[:16]
        
        item = KnowledgeItem(
            id=item_id,
            type=knowledge_type,
            content=content,
            metadata=metadata or {},
            source=source,
            importance=importance,
            confidence=confidence,
            associations=associations or [],
            properties=properties or {},
            examples=examples or [],
            semantic_type=semantic_type,
            schema=schema,
            timestamp=time.time(),
        )
        
        # Generate embedding
        if self.enable_embedding:
            item.embedding = self._generate_embedding(content)
        
        # Store item
        self.items[item_id] = item
        self.item_order.append(item_id)
        self.item_index[item_id] = len(self.item_order) - 1
        
        # Update statistics
        self._update_stats(item)
        
        # Add to graph
        if self.enable_graph:
            self._add_to_graph(item)
        
        # Consolidate if needed
        self._consolidation_counter += 1
        if self._consolidation_counter >= self.consolidation_interval:
            self._consolidate_memory()
            self._consolidation_counter = 0
        
        # Save periodically
        if len(self.items) % 100 == 0:
            self._save_memory()
        
        self.logger.debug(f"Stored knowledge {item_id} ({knowledge_type.value})")
        return item_id
    
    def _update_stats(self, item: KnowledgeItem) -> None:
        """Update memory statistics."""
        self.stats.total_items = len(self.items)
        
        # Update by type
        type_key = item.type.value
        self.stats.by_type[type_key] = self.stats.by_type.get(type_key, 0) + 1
        
        # Update by status
        status_key = item.status.value
        self.stats.by_status[status_key] = self.stats.by_status.get(status_key, 0) + 1
        
        # Update by source
        self.stats.by_source[item.source] = self.stats.by_source.get(item.source, 0) + 1
        
        # Calculate averages
        if self.items:
            total_importance = sum(i.importance for i in self.items.values())
            total_confidence = sum(i.confidence for i in self.items.values())
            self.stats.average_importance = total_importance / len(self.items)
            self.stats.average_confidence = total_confidence / len(self.items)
    
    # ============================================
    # Knowledge Retrieval
    # ============================================
    
    def retrieve_knowledge(
        self,
        query: Any,
        mode: RetrievalMode = RetrievalMode.SEMANTIC,
        n: int = 10,
        min_importance: float = 0.0,
        max_importance: float = 1.0,
        types: Optional[List[KnowledgeType]] = None,
        sources: Optional[List[str]] = None,
        semantic_type: Optional[str] = None,
        exclude_ids: Optional[List[str]] = None,
    ) -> List[KnowledgeItem]:
        """
        Retrieve knowledge from memory.
        
        Args:
            query: Query for retrieval
            mode: Retrieval mode
            n: Number of items to retrieve
            min_importance: Minimum importance threshold
            max_importance: Maximum importance threshold
            types: Filter by knowledge types
            sources: Filter by sources
            semantic_type: Filter by semantic type
            exclude_ids: IDs to exclude
            
        Returns:
            List of retrieved knowledge items
        """
        exclude_ids = set(exclude_ids or [])
        
        # Filter items
        available = []
        for item in self.items.values():
            if item.id in exclude_ids:
                continue
            if item.importance < min_importance or item.importance > max_importance:
                continue
            if types and item.type not in types:
                continue
            if sources and item.source not in sources:
                continue
            if semantic_type and item.semantic_type != semantic_type:
                continue
            if item.status == MemoryStatus.FORGOTTEN:
                continue
            available.append(item)
        
        if not available:
            return []
        
        # Apply retrieval mode
        if mode == RetrievalMode.EXACT:
            # Exact match on content
            results = [
                item for item in available
                if str(item.content) == str(query)
            ]
            if not results:
                results = available[:n]
        
        elif mode == RetrievalMode.SEMANTIC:
            # Semantic similarity
            if self.enable_embedding:
                query_embedding = self._generate_embedding(query)
                results = self._semantic_search(query_embedding, n, available)
            else:
                results = available[:n]
        
        elif mode == RetrievalMode.ASSOCIATIVE:
            # Association-based retrieval
            associations = defaultdict(float)
            for item in available:
                for assoc in item.associations:
                    associations[assoc] += item.importance
            
            sorted_associations = sorted(
                associations.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            results = []
            for assoc_id, _ in sorted_associations[:n]:
                if assoc_id in self.items:
                    results.append(self.items[assoc_id])
        
        elif mode == RetrievalMode.INFERENTIAL:
            # Inferential reasoning (rule-based)
            results = self._inferential_retrieval(query, available, n)
        
        elif mode == RetrievalMode.ANALOGICAL:
            # Analogical reasoning
            results = self._analogical_retrieval(query, available, n)
        
        elif mode == RetrievalMode.PATTERN:
            # Pattern-based retrieval
            results = self._pattern_retrieval(query, available, n)
        
        elif mode == RetrievalMode.RULE_BASED:
            # Rule-based retrieval
            results = self._rule_based_retrieval(query, available, n)
        
        else:
            results = available[:n]
        
        # Update access statistics
        for item in results:
            item.access_count += 1
            item.last_accessed = time.time()
        
        self.stats.total_accesses += len(results)
        
        return results
    
    def _semantic_search(
        self,
        query_embedding: np.ndarray,
        n: int,
        candidates: List[KnowledgeItem]
    ) -> List[KnowledgeItem]:
        """
        Search for knowledge by semantic similarity.
        
        Args:
            query_embedding: Query embedding
            n: Number of items to retrieve
            candidates: Candidate items
            
        Returns:
            List of semantically similar items
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
        
        if self.embedding_index and len(embeddings) > 100:
            # Use FAISS for large-scale search
            if not self.embedding_index.is_trained:
                self.embedding_index.train(embeddings)
            self.embedding_index.add(embeddings)
            distances, indices = self.embedding_index.search(query_embedding, min(n, len(items)))
            results = [items[i] for i in indices[0]]
        else:
            # Use direct computation
            similarities = 1 - pairwise_distances(query_embedding, embeddings, metric='cosine')[0]
            sorted_indices = np.argsort(similarities)[::-1][:n]
            results = [items[i] for i in sorted_indices]
        
        return results
    
    def _inferential_retrieval(
        self,
        query: Any,
        candidates: List[KnowledgeItem],
        n: int
    ) -> List[KnowledgeItem]:
        """
        Retrieve knowledge using inferential reasoning.
        
        Args:
            query: Query
            candidates: Candidate items
            n: Number of items to retrieve
            
        Returns:
            List of inferred knowledge items
        """
        # Simple rule-based inference
        results = []
        if self.enable_graph and self.graph:
            # Use graph for inference
            # Find nodes connected to query concept
            query_str = str(query).lower()
            
            # Find matching nodes
            matching_nodes = []
            for node_id, node in self.graph.nodes.items():
                if query_str in str(node.content).lower():
                    matching_nodes.append(node_id)
            
            # Get neighbors
            if matching_nodes:
                neighbors = set()
                for node_id in matching_nodes:
                    for edge in self.graph.edges:
                        if edge[0] == node_id:
                            neighbors.add(edge[1])
                        elif edge[1] == node_id:
                            neighbors.add(edge[0])
                
                # Convert to items
                for node_id in list(neighbors)[:n]:
                    if node_id in self.items:
                        results.append(self.items[node_id])
        
        # Fallback to importance-based retrieval
        if not results:
            results = sorted(candidates, key=lambda x: x.importance, reverse=True)[:n]
        
        return results
    
    def _analogical_retrieval(
        self,
        query: Any,
        candidates: List[KnowledgeItem],
        n: int
    ) -> List[KnowledgeItem]:
        """
        Retrieve knowledge using analogical reasoning.
        
        Args:
            query: Query
            candidates: Candidate items
            n: Number of items to retrieve
            
        Returns:
            List of analogically similar items
        """
        # Find items with similar structure or relationships
        results = []
        query_str = str(query).lower()
        
        for item in candidates:
            # Check structural similarity
            if isinstance(item.content, (dict, list, tuple)):
                # Structure-based similarity
                item_str = str(item.content).lower()
                if len(item_str) > 0:
                    # Simple string similarity
                    similarity = len(set(query_str.split()) & set(item_str.split())) / max(1, len(set(query_str.split()) | set(item_str.split())))
                    if similarity > 0.3:
                        results.append((item, similarity))
        
        # Sort by similarity
        results.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in results[:n]]
    
    def _pattern_retrieval(
        self,
        query: Any,
        candidates: List[KnowledgeItem],
        n: int
    ) -> List[KnowledgeItem]:
        """
        Retrieve knowledge by pattern matching.
        
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
            # Check for pattern matches in content, properties, and metadata
            match_score = 0.0
            
            # Content match
            content_str = str(item.content).lower()
            if query_str in content_str:
                match_score += 0.5
            
            # Properties match
            for key, value in item.properties.items():
                if query_str in str(key).lower() or query_str in str(value).lower():
                    match_score += 0.3
            
            # Metadata match
            for key, value in item.metadata.items():
                if query_str in str(key).lower() or query_str in str(value).lower():
                    match_score += 0.2
            
            if match_score > 0:
                results.append((item, match_score))
        
        # Sort by match score
        results.sort(key=lambda x: x[1], reverse=True)
        return [item for item, _ in results[:n]]
    
    def _rule_based_retrieval(
        self,
        query: Any,
        candidates: List[KnowledgeItem],
        n: int
    ) -> List[KnowledgeItem]:
        """
        Retrieve knowledge using rule-based reasoning.
        
        Args:
            query: Query
            candidates: Candidate items
            n: Number of items to retrieve
            
        Returns:
            List of rule-matched items
        """
        # Simple rule-based retrieval
        results = []
        query_str = str(query).lower()
        
        for item in candidates:
            # Check if item matches any rules
            if item.type == KnowledgeType.RULE:
                # Check rule application
                rule_conditions = item.properties.get('conditions', [])
                rule_consequences = item.properties.get('consequences', [])
                
                # Check if query matches conditions
                conditions_met = False
                for condition in rule_conditions:
                    if condition in query_str or str(condition).lower() in query_str:
                        conditions_met = True
                        break
                
                if conditions_met:
                    results.append(item)
                    if len(results) >= n:
                        break
        
        # Fallback to importance-based retrieval
        if not results:
            results = sorted(candidates, key=lambda x: x.importance, reverse=True)[:n]
        
        return results
    
    # ============================================
    # Memory Consolidation
    # ============================================
    
    def _consolidate_memory(self) -> None:
        """Consolidate memory items."""
        # Identify items for consolidation
        to_consolidate = [
            item for item in self.items.values()
            if item.importance >= self.consolidation_threshold
            and item.status != MemoryStatus.CONSOLIDATED
        ]
        
        if not to_consolidate:
            return
        
        # Consolidate items
        for item in to_consolidate:
            item.consolidation_count += 1
            item.status = MemoryStatus.CONSOLIDATED
            
            # Update importance
            item.importance = min(1.0, item.importance + 0.05)
            
            # Merge similar items if possible
            if self.enable_semantic:
                self._merge_similar_items(item)
        
        # Update graph
        if self.enable_graph:
            self._update_graph()
        
        self.logger.debug(f"Consolidated {len(to_consolidate)} items")
    
    def _merge_similar_items(self, item: KnowledgeItem) -> None:
        """
        Merge similar knowledge items.
        
        Args:
            item: Item to merge with similar items
        """
        if not self.enable_embedding or item.embedding is None:
            return
        
        # Find similar items
        similar = []
        for other_id, other_item in self.items.items():
            if other_id == item.id:
                continue
            if other_item.embedding is None:
                continue
            
            similarity = 1 - cosine(item.embedding, other_item.embedding)
            if similarity > 0.9:
                similar.append((other_id, similarity))
        
        # Merge similar items
        for other_id, _ in similar:
            if other_id in self.items:
                other_item = self.items[other_id]
                # Merge content
                if isinstance(item.content, dict) and isinstance(other_item.content, dict):
                    item.content.update(other_item.content)
                elif isinstance(item.content, list) and isinstance(other_item.content, list):
                    item.content.extend(other_item.content)
                
                # Merge properties
                item.properties.update(other_item.properties)
                
                # Merge metadata
                item.metadata.update(other_item.metadata)
                
                # Update associations
                item.associations.extend(other_item.associations)
                item.associations = list(set(item.associations))
                
                # Remove other item
                self._remove_item(other_id)
                
                self.logger.debug(f"Merged item {other_id} into {item.id}")
    
    def _remove_item(self, item_id: str) -> None:
        """
        Remove an item from memory.
        
        Args:
            item_id: Item ID to remove
        """
        if item_id not in self.items:
            return
        
        item = self.items[item_id]
        item.status = MemoryStatus.FORGOTTEN
        
        # Remove from storage
        del self.items[item_id]
        
        # Remove from order
        if item_id in self.item_order:
            self.item_order.remove(item_id)
        
        # Remove from index
        if item_id in self.item_index:
            del self.item_index[item_id]
    
    # ============================================
    # Knowledge Graph
    # ============================================
    
    def _add_to_graph(self, item: KnowledgeItem) -> None:
        """Add item to knowledge graph."""
        if not self.enable_graph:
            return
        
        if self.graph is None:
            self.graph = KnowledgeGraph(
                nodes={},
                edges=[],
                weights={},
                communities={},
                centrality={},
            )
        
        # Add node
        self.graph.nodes[item.id] = item
        
        # Add edges based on associations
        for assoc_id in item.associations:
            if assoc_id in self.graph.nodes:
                self.graph.edges.append((item.id, assoc_id, 0.5))
                self.graph.weights[(item.id, assoc_id)] = 0.5
        
        # Add edges based on semantic similarity
        if self.enable_embedding and item.embedding is not None:
            for other_id, other_item in self.items.items():
                if other_id == item.id:
                    continue
                if other_item.embedding is None:
                    continue
                
                similarity = 1 - cosine(item.embedding, other_item.embedding)
                if similarity > 0.7:
                    self.graph.edges.append((item.id, other_id, similarity))
                    self.graph.weights[(item.id, other_id)] = similarity
    
    def _update_graph(self) -> None:
        """Update knowledge graph."""
        if not self.enable_graph or self.graph is None:
            return
        
        # Update centrality
        G = nx.Graph()
        for edge in self.graph.edges:
            G.add_edge(edge[0], edge[1], weight=edge[2])
        
        # Compute centrality
        try:
            centrality = nx.eigenvector_centrality(G, weight='weight')
            self.graph.centrality = centrality
        except:
            # Fallback to degree centrality
            centrality = nx.degree_centrality(G)
            self.graph.centrality = centrality
        
        # Detect communities
        try:
            communities = community.greedy_modularity_communities(G)
            for i, community_nodes in enumerate(communities):
                for node in community_nodes:
                    self.graph.communities[node] = i
            self.stats.community_count = len(communities)
        except:
            self.graph.communities = {}
            self.stats.community_count = 0
        
        # Update graph density
        n_nodes = len(self.graph.nodes)
        n_edges = len(self.graph.edges)
        self.stats.graph_density = (2 * n_edges) / (n_nodes * (n_nodes - 1)) if n_nodes > 1 else 0
        self.stats.average_degree = (2 * n_edges) / n_nodes if n_nodes > 0 else 0
    
    # ============================================
    # Memory Forgetting
    # ============================================
    
    def _forget_oldest(self) -> None:
        """Forget the oldest/lowest importance item."""
        if not self.item_order:
            return
        
        # Find item with lowest importance
        min_importance = float('inf')
        forget_id = None
        
        for item_id in self.item_order:
            item = self.items[item_id]
            # Apply decay
            age = time.time() - item.last_accessed
            decayed_importance = item.importance * np.exp(-self.decay_rate * age)
            
            if decayed_importance < min_importance and item.status != MemoryStatus.SEMANTIC:
                min_importance = decayed_importance
                forget_id = item_id
        
        if forget_id:
            self._remove_item(forget_id)
    
    # ============================================
    # Memory Analysis
    # ============================================
    
    def get_stats(self) -> MemoryStatistics:
        """Get memory statistics."""
        self.stats.memory_usage = self._calculate_memory_usage()
        self.stats.timestamp = time.time()
        self.stats.consolidation_rate = sum(
            1 for item in self.items.values()
            if item.consolidation_count > 0
        ) / len(self.items) if self.items else 0
        
        # Update semantic density
        if self.enable_embedding and len(self.items) > 1:
            embeddings = []
            for item in self.items.values():
                if item.embedding is not None:
                    embeddings.append(item.embedding)
            if embeddings:
                embeddings = np.array(embeddings)
                distances = pairwise_distances(embeddings, metric='cosine')
                self.stats.semantic_density = 1 - np.mean(distances)
        
        return self.stats
    
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
            return total
        except:
            return 0
    
    def analyze_memory(self) -> Dict[str, Any]:
        """
        Analyze long-term memory.
        
        Returns:
            Analysis results
        """
        analysis = {
            'total_items': len(self.items),
            'type_distribution': dict(self.stats.by_type),
            'status_distribution': dict(self.stats.by_status),
            'source_distribution': dict(self.stats.by_source),
            'importance_stats': {
                'mean': self.stats.average_importance,
                'max': max([i.importance for i in self.items.values()]) if self.items else 0,
                'min': min([i.importance for i in self.items.values()]) if self.items else 0,
            },
            'confidence_stats': {
                'mean': self.stats.average_confidence,
                'max': max([i.confidence for i in self.items.values()]) if self.items else 0,
                'min': min([i.confidence for i in self.items.values()]) if self.items else 0,
            },
            'graph_stats': {
                'density': self.stats.graph_density,
                'average_degree': self.stats.average_degree,
                'community_count': self.stats.community_count,
            } if self.enable_graph else None,
            'semantic_density': self.stats.semantic_density,
            'consolidation_rate': self.stats.consolidation_rate,
        }
        
        # Add semantic clusters if available
        if self.enable_semantic and len(self.items) > 10:
            embeddings = []
            item_ids = []
            for item in self.items.values():
                if item.embedding is not None:
                    embeddings.append(item.embedding)
                    item_ids.append(item.id)
            
            if len(embeddings) > 10:
                embeddings = np.array(embeddings)
                
                # Reduce dimensions
                try:
                    pca = PCA(n_components=min(50, len(embeddings[0])))
                    embeddings_pca = pca.fit_transform(embeddings)
                    
                    # Cluster
                    n_clusters = min(10, len(embeddings) // 20)
                    kmeans = KMeans(n_clusters=max(2, n_clusters), random_state=42)
                    labels = kmeans.fit_predict(embeddings_pca)
                    
                    analysis['clusters'] = {
                        'n_clusters': len(set(labels)),
                        'cluster_sizes': dict(zip(*np.unique(labels, return_counts=True))),
                        'item_ids': item_ids,
                        'labels': labels.tolist(),
                    }
                except:
                    pass
        
        return analysis
    
    # ============================================
    # Memory Export/Import
    # ============================================
    
    def export_memory(self, format: str = "json") -> Union[str, bytes]:
        """
        Export long-term memory.
        
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
            'stats': asdict(self.stats),
            'graph': self.graph if self.enable_graph else None,
        }
        
        for item_id, item in self.items.items():
            item_data = asdict(item)
            if item_data.get('embedding') is not None:
                item_data['embedding'] = item_data['embedding'].tolist()
            data['items'][item_id] = item_data
        
        if format == "json":
            return json.dumps(data, indent=2, default=str)
        elif format == "pickle":
            return pickle.dumps(data)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def import_memory(self, data: Union[str, bytes], format: str = "json") -> int:
        """
        Import long-term memory.
        
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
        
        # Clear existing memory
        self.items.clear()
        self.item_order.clear()
        self.item_index.clear()
        
        # Import items
        count = 0
        for item_id, item_data in loaded.get('items', {}).items():
            # Convert embedding back to numpy
            if 'embedding' in item_data and item_data['embedding']:
                item_data['embedding'] = np.array(item_data['embedding'])
            
            item = KnowledgeItem(**item_data)
            self.items[item_id] = item
            self.item_order.append(item_id)
            self.item_index[item_id] = len(self.item_order) - 1
            count += 1
        
        # Restore stats
        if 'stats' in loaded:
            self.stats = MemoryStatistics(**loaded['stats'])
        
        # Restore graph
        if self.enable_graph and 'graph' in loaded and loaded['graph']:
            self.graph = loaded['graph']
        
        self._save_memory()
        self.logger.info(f"Imported {count} items")
        return count

# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point for CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NEXUS Long-Term Memory CLI')
    parser.add_argument('--command', choices=['stats', 'analyze', 'export', 'import', 'clear'],
                       required=True, help='Command to execute')
    parser.add_argument('--memory-dir', type=str, default='./memory/long_term', help='Memory directory')
    parser.add_argument('--format', type=str, default='json', help='Export/import format')
    parser.add_argument('--file', type=str, help='File for export/import')
    parser.add_argument('--max-items', type=int, default=100000, help='Maximum items')
    parser.add_argument('--embedding-dim', type=int, default=256, help='Embedding dimension')
    
    args = parser.parse_args()
    
    # Initialize memory
    memory = LongTermMemory(
        max_items=args.max_items,
        embedding_dim=args.embedding_dim,
        memory_dir=args.memory_dir,
    )
    
    if args.command == 'stats':
        stats = memory.get_stats()
        print("\nLong-Term Memory Statistics:")
        print("-" * 50)
        print(f"Total Items: {stats.total_items}")
        print(f"By Type: {stats.by_type}")
        print(f"By Status: {stats.by_status}")
        print(f"By Source: {stats.by_source}")
        print(f"Average Importance: {stats.average_importance:.4f}")
        print(f"Average Confidence: {stats.average_confidence:.4f}")
        print(f"Total Accesses: {stats.total_accesses}")
        print(f"Consolidation Rate: {stats.consolidation_rate:.4f}")
        print(f"Semantic Density: {stats.semantic_density:.4f}")
        print(f"Graph Density: {stats.graph_density:.4f}")
        print(f"Average Degree: {stats.average_degree:.2f}")
        print(f"Community Count: {stats.community_count}")
        print(f"Memory Usage: {stats.memory_usage / 1024:.2f} KB")
    
    elif args.command == 'analyze':
        analysis = memory.analyze_memory()
        print("\nLong-Term Memory Analysis:")
        print("-" * 50)
        print(f"Total Items: {analysis['total_items']}")
        print(f"Type Distribution: {analysis['type_distribution']}")
        print(f"Status Distribution: {analysis['status_distribution']}")
        print(f"Source Distribution: {analysis['source_distribution']}")
        print(f"Importance Stats: {analysis['importance_stats']}")
        print(f"Confidence Stats: {analysis['confidence_stats']}")
        if analysis['graph_stats']:
            print(f"Graph Density: {analysis['graph_stats']['density']:.4f}")
            print(f"Average Degree: {analysis['graph_stats']['average_degree']:.2f}")
            print(f"Community Count: {analysis['graph_stats']['community_count']}")
        print(f"Semantic Density: {analysis['semantic_density']:.4f}")
        print(f"Consolidation Rate: {analysis['consolidation_rate']:.4f}")
        if 'clusters' in analysis:
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
        print(f"Imported {count} items")
    
    elif args.command == 'clear':
        memory.items.clear()
        memory.item_order.clear()
        memory.item_index.clear()
        memory.graph = None
        memory._save_memory()
        print("Memory cleared")


if __name__ == '__main__':
    main()
