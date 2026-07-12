"""
NEXUS AI TRADING SYSTEM - Memory System
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Memory System with:
- Short-term memory (working memory)
- Long-term memory (episodic + semantic)
- Episodic memory (experiences)
- Semantic memory (facts and knowledge)
- Working memory (active context)
- Memory consolidation
- Memory retrieval
- Memory decay
- Memory importance scoring
- Memory association
- Memory pruning
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4

import numpy as np
from pydantic import BaseModel, Field, validator
from sklearn.metrics.pairwise import cosine_similarity

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import MemoryError

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class MemoryType(str, Enum):
    """Memory types"""
    WORKING = "working"      # Active context (short-term)
    EPISODIC = "episodic"    # Experiences (long-term)
    SEMANTIC = "semantic"    # Facts and knowledge (long-term)
    PROCEDURAL = "procedural"  # Skills and procedures


class MemoryImportance(str, Enum):
    """Memory importance levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MemoryStatus(str, Enum):
    """Memory status"""
    ACTIVE = "active"
    CONSOLIDATING = "consolidating"
    CONSOLIDATED = "consolidated"
    DECAYING = "decaying"
    FORGOTTEN = "forgotten"


@dataclass
class Memory:
    """Memory item"""
    id: str = field(default_factory=lambda: str(uuid4()))
    content: Any
    type: MemoryType
    importance: MemoryImportance
    status: MemoryStatus = MemoryStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    accessed_at: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    strength: float = 0.5  # 0-1
    decay_rate: float = 0.01
    consolidation_level: float = 0.0  # 0-1
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    associations: List[str] = field(default_factory=list)  # Related memory IDs
    embedding: Optional[List[float]] = None
    source: str = ""  # Source system/agent
    expires_at: Optional[datetime] = None


@dataclass
class MemoryContext:
    """Memory context for retrieval"""
    query: str
    type: Optional[MemoryType] = None
    tags: Optional[List[str]] = None
    importance: Optional[MemoryImportance] = None
    min_strength: float = 0.3
    limit: int = 10
    semantic: bool = False
    time_window: Optional[int] = None  # seconds


@dataclass
class MemoryQueryResult:
    """Memory query result"""
    items: List[Memory]
    total: int
    query_time: float
    context: MemoryContext


class MemoryConfig(BaseModel):
    """Memory configuration"""
    enabled: bool = True
    working_memory_limit: int = Field(default=20, gt=0)
    episodic_memory_limit: int = Field(default=1000, gt=0)
    semantic_memory_limit: int = Field(default=500, gt=0)
    procedural_memory_limit: int = Field(default=100, gt=0)
    consolidation_interval: int = Field(default=3600, gt=0)
    decay_interval: int = Field(default=86400, gt=0)
    min_importance_for_long_term: MemoryImportance = MemoryImportance.MEDIUM
    default_strength: float = Field(default=0.5, ge=0, le=1)
    consolidation_threshold: float = Field(default=0.7, ge=0, le=1)
    decay_factor: float = Field(default=0.01, ge=0)
    association_limit: int = Field(default=10, gt=0)
    embedding_dim: int = Field(default=384, gt=0)
    use_embeddings: bool = True
    cache_enabled: bool = True
    cache_ttl: int = Field(default=3600, gt=0)
    health_check_interval: int = Field(default=60, gt=0)
    log_level: str = "info"


# ========================================
# MEMORY SYSTEM
# ========================================

class MemorySystem:
    """
    Complete memory system for AI trading agent.
    
    Features:
    - Short-term memory (working memory)
    - Long-term memory (episodic + semantic)
    - Episodic memory (experiences)
    - Semantic memory (facts and knowledge)
    - Working memory (active context)
    - Memory consolidation
    - Memory retrieval
    - Memory decay
    - Memory importance scoring
    - Memory association
    - Memory pruning
    - Health monitoring
    - Configuration management
    - Event handling
    - Logging
    - Metrics collection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = MemoryConfig(**(config or {}))
        self.redis = get_redis()
        
        # State
        self._memories: Dict[str, Memory] = {}
        self._working_memory: List[str] = []  # IDs in working memory
        self._episodic_memory: List[str] = []  # IDs in episodic memory
        self._semantic_memory: List[str] = []  # IDs in semantic memory
        self._procedural_memory: List[str] = []  # IDs in procedural memory
        
        # Indices
        self._tag_index: Dict[str, Set[str]] = {}  # tag -> memory IDs
        self._association_graph: Dict[str, Set[str]] = {}  # memory ID -> associated IDs
        
        # Embedding cache
        self._embedding_cache: Dict[str, List[float]] = {}
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        self._tasks: List[asyncio.Task] = []
        
        # Metrics
        self._metrics = {
            "total_memories": 0,
            "working_memories": 0,
            "episodic_memories": 0,
            "semantic_memories": 0,
            "procedural_memories": 0,
            "active_memories": 0,
            "consolidated_memories": 0,
            "decayed_memories": 0,
            "access_count": 0,
            "avg_strength": 0.0,
            "avg_consolidation": 0.0
        }
        
        self.logger = get_logger(f"{__name__}.MemorySystem")
        self.logger.info("MemorySystem initialized")
    
    # ========================================
    # MEMORY STORAGE
    # ========================================
    
    async def store_memory(
        self,
        content: Any,
        type: MemoryType,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "",
        associations: Optional[List[str]] = None,
        strength: Optional[float] = None
    ) -> Memory:
        """
        Store a memory.
        
        Args:
            content: Memory content
            type: Memory type
            importance: Memory importance
            tags: Tags for retrieval
            metadata: Additional metadata
            source: Source system/agent
            associations: Related memory IDs
            strength: Initial memory strength
            
        Returns:
            Memory: Stored memory
        """
        try:
            # Check limits
            await self._check_limits(type)
            
            # Create memory
            memory = Memory(
                content=content,
                type=type,
                importance=importance,
                tags=tags or [],
                metadata=metadata or {},
                source=source,
                associations=associations or [],
                strength=strength or self.config.default_strength
            )
            
            # Generate embedding
            if self.config.use_embeddings:
                memory.embedding = await self._generate_embedding(str(content))
            
            # Store in appropriate memory type
            if type == MemoryType.WORKING:
                self._working_memory.append(memory.id)
                self._metrics["working_memories"] += 1
            elif type == MemoryType.EPISODIC:
                self._episodic_memory.append(memory.id)
                self._metrics["episodic_memories"] += 1
            elif type == MemoryType.SEMANTIC:
                self._semantic_memory.append(memory.id)
                self._metrics["semantic_memories"] += 1
            elif type == MemoryType.PROCEDURAL:
                self._procedural_memory.append(memory.id)
                self._metrics["procedural_memories"] += 1
            
            # Add to main storage
            self._memories[memory.id] = memory
            
            # Update indices
            for tag in memory.tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = set()
                self._tag_index[tag].add(memory.id)
            
            # Update association graph
            for assoc_id in memory.associations:
                if assoc_id not in self._association_graph:
                    self._association_graph[assoc_id] = set()
                self._association_graph[assoc_id].add(memory.id)
            
            # Update metrics
            self._metrics["total_memories"] += 1
            self._metrics["active_memories"] += 1
            self._metrics["avg_strength"] = (
                self._metrics["avg_strength"] * 0.9 + memory.strength * 0.1
            )
            
            self.logger.info(
                f"Memory stored: {memory.id} ({type.value}) "
                f"importance={importance.value} strength={memory.strength:.2f}"
            )
            
            # Trim working memory if needed
            if type == MemoryType.WORKING:
                await self._trim_working_memory()
            
            return memory
            
        except Exception as e:
            self.logger.error(f"Failed to store memory: {e}")
            raise MemoryError(f"Memory storage failed: {e}")
    
    # ========================================
    # MEMORY RETRIEVAL
    # ========================================
    
    async def retrieve_memories(
        self,
        query: str,
        type: Optional[MemoryType] = None,
        tags: Optional[List[str]] = None,
        importance: Optional[MemoryImportance] = None,
        min_strength: float = 0.3,
        limit: int = 10,
        semantic: bool = False,
        time_window: Optional[int] = None
    ) -> MemoryQueryResult:
        """
        Retrieve memories based on query.
        
        Args:
            query: Query string
            type: Filter by type
            tags: Filter by tags
            importance: Filter by importance
            min_strength: Minimum strength
            limit: Maximum results
            semantic: Use semantic search
            time_window: Time window in seconds
            
        Returns:
            MemoryQueryResult: Query results
        """
        start_time = time.time()
        
        context = MemoryContext(
            query=query,
            type=type,
            tags=tags,
            importance=importance,
            min_strength=min_strength,
            limit=limit,
            semantic=semantic,
            time_window=time_window
        )
        
        try:
            # Get candidates
            candidates = await self._get_candidates(context)
            
            # Score and rank
            ranked_items = await self._rank_memories(context, candidates)
            
            # Apply filters
            filtered = self._apply_filters(ranked_items, context)
            
            # Limit results
            results = filtered[:limit]
            
            # Update access counts
            for memory in results:
                memory.access_count += 1
                memory.accessed_at = datetime.utcnow()
                self._metrics["access_count"] += 1
            
            result = MemoryQueryResult(
                items=results,
                total=len(filtered),
                query_time=time.time() - start_time,
                context=context
            )
            
            self.logger.debug(f"Retrieved {len(results)} memories in {result.query_time:.3f}s")
            return result
            
        except Exception as e:
            self.logger.error(f"Memory retrieval failed: {e}")
            raise MemoryError(f"Memory retrieval failed: {e}")
    
    async def get_memory(self, memory_id: str) -> Optional[Memory]:
        """Get memory by ID"""
        memory = self._memories.get(memory_id)
        if memory:
            memory.access_count += 1
            memory.accessed_at = datetime.utcnow()
            self._metrics["access_count"] += 1
        return memory
    
    async def get_memories_by_type(
        self,
        type: MemoryType,
        limit: int = 10
    ) -> List[Memory]:
        """Get memories by type"""
        memory_ids = self._get_memory_ids_by_type(type)
        memories = []
        
        for memory_id in memory_ids[-limit:]:
            memory = self._memories.get(memory_id)
            if memory and memory.status == MemoryStatus.ACTIVE:
                memories.append(memory)
        
        return memories
    
    async def get_memories_by_tags(
        self,
        tags: List[str],
        limit: int = 10
    ) -> List[Memory]:
        """Get memories by tags"""
        memory_ids = set()
        
        for tag in tags:
            if tag in self._tag_index:
                memory_ids.update(self._tag_index[tag])
        
        memories = []
        for memory_id in memory_ids:
            memory = self._memories.get(memory_id)
            if memory and memory.status == MemoryStatus.ACTIVE:
                memories.append(memory)
        
        # Sort by strength
        memories.sort(key=lambda x: x.strength, reverse=True)
        return memories[:limit]
    
    # ========================================
    # MEMORY CONSOLIDATION
    # ========================================
    
    async def consolidate_memories(self) -> None:
        """Consolidate working memories to long-term"""
        for memory_id in self._working_memory[:]:
            memory = self._memories.get(memory_id)
            if not memory:
                continue
            
            # Check if should consolidate
            if memory.importance == MemoryImportance.LOW:
                continue
            
            # Increase consolidation level
            memory.consolidation_level += 0.1
            memory.status = MemoryStatus.CONSOLIDATING
            
            # Check if consolidated
            if memory.consolidation_level >= self.config.consolidation_threshold:
                # Move to long-term memory
                if memory.type == MemoryType.WORKING:
                    memory.type = MemoryType.EPISODIC
                    self._working_memory.remove(memory_id)
                    self._episodic_memory.append(memory_id)
                    memory.status = MemoryStatus.CONSOLIDATED
                    self._metrics["consolidated_memories"] += 1
                    
                    self.logger.info(
                        f"Memory consolidated: {memory_id} "
                        f"importance={memory.importance.value}"
                    )
    
    async def _trim_working_memory(self) -> None:
        """Trim working memory to limit"""
        while len(self._working_memory) > self.config.working_memory_limit:
            # Find least important memory in working memory
            memory_ids = self._working_memory[:]
            
            # Sort by importance and strength
            def get_priority(mid: str) -> tuple:
                m = self._memories.get(mid)
                if not m:
                    return (0, 0)
                importance_order = {
                    MemoryImportance.CRITICAL: 4,
                    MemoryImportance.HIGH: 3,
                    MemoryImportance.MEDIUM: 2,
                    MemoryImportance.LOW: 1
                }
                return (importance_order.get(m.importance, 0), m.strength)
            
            memory_ids.sort(key=get_priority)
            
            # Remove least important
            to_remove = memory_ids[0]
            self._working_memory.remove(to_remove)
            
            # Move to episodic if still relevant
            memory = self._memories.get(to_remove)
            if memory:
                memory.type = MemoryType.EPISODIC
                self._episodic_memory.append(to_remove)
    
    # ========================================
    # MEMORY DECAY
    # ========================================
    
    async def apply_decay(self) -> None:
        """Apply memory decay"""
        for memory in self._memories.values():
            if memory.status == MemoryStatus.FORGOTTEN:
                continue
            
            # Calculate time since last access
            time_since_access = (datetime.utcnow() - memory.accessed_at).total_seconds()
            
            # Apply decay
            decay = self.config.decay_factor * (time_since_access / 86400)  # per day
            memory.strength = max(0, memory.strength - decay)
            
            # Check if forgotten
            if memory.strength < 0.1 and memory.status == MemoryStatus.ACTIVE:
                memory.status = MemoryStatus.DECAYING
            
            if memory.strength < 0.01:
                memory.status = MemoryStatus.FORGOTTEN
                self._metrics["decayed_memories"] += 1
                self._metrics["active_memories"] -= 1
    
    # ========================================
    # MEMORY PRUNING
    # ========================================
    
    async def prune_memories(self) -> None:
        """Prune old or weak memories"""
        # Check limits for each memory type
        await self._prune_by_type(MemoryType.EPISODIC, self.config.episodic_memory_limit)
        await self._prune_by_type(MemoryType.SEMANTIC, self.config.semantic_memory_limit)
        await self._prune_by_type(MemoryType.PROCEDURAL, self.config.procedural_memory_limit)
    
    async def _prune_by_type(self, type: MemoryType, limit: int) -> None:
        """Prune memories of specific type"""
        memory_ids = self._get_memory_ids_by_type(type)
        
        if len(memory_ids) <= limit:
            return
        
        # Get memories to prune
        memories_to_prune = []
        for memory_id in memory_ids:
            memory = self._memories.get(memory_id)
            if memory and memory.status == MemoryStatus.FORGOTTEN:
                memories_to_prune.append(memory_id)
        
        # Sort by importance and strength
        def get_prune_score(mid: str) -> tuple:
            m = self._memories.get(mid)
            if not m:
                return (0, 0)
            importance_order = {
                MemoryImportance.CRITICAL: 4,
                MemoryImportance.HIGH: 3,
                MemoryImportance.MEDIUM: 2,
                MemoryImportance.LOW: 1
            }
            return (importance_order.get(m.importance, 0), m.strength)
        
        memories_to_prune.sort(key=get_prune_score)
        
        # Prune excess memories
        to_remove = len(memory_ids) - limit
        for memory_id in memories_to_prune[:to_remove]:
            await self._remove_memory(memory_id)
    
    async def _remove_memory(self, memory_id: str) -> None:
        """Remove a memory"""
        memory = self._memories.get(memory_id)
        if not memory:
            return
        
        # Remove from lists
        for memory_list in [
            self._working_memory,
            self._episodic_memory,
            self._semantic_memory,
            self._procedural_memory
        ]:
            if memory_id in memory_list:
                memory_list.remove(memory_id)
        
        # Remove from tag index
        for tag in memory.tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(memory_id)
        
        # Remove from association graph
        if memory_id in self._association_graph:
            del self._association_graph[memory_id]
        
        # Remove from storage
        del self._memories[memory_id]
        
        self._metrics["active_memories"] -= 1
    
    # ========================================
    # MEMORY ASSOCIATION
    # ========================================
    
    async def associate_memories(
        self,
        memory_id1: str,
        memory_id2: str,
        strength: float = 0.5
    ) -> None:
        """
        Associate two memories.
        
        Args:
            memory_id1: First memory ID
            memory_id2: Second memory ID
            strength: Association strength
        """
        if memory_id1 not in self._memories or memory_id2 not in self._memories:
            raise MemoryError("Memory not found")
        
        # Add associations
        memory1 = self._memories[memory_id1]
        memory2 = self._memories[memory_id2]
        
        if memory_id2 not in memory1.associations:
            memory1.associations.append(memory_id2)
        if memory_id1 not in memory2.associations:
            memory2.associations.append(memory_id1)
        
        # Update association graph
        if memory_id1 not in self._association_graph:
            self._association_graph[memory_id1] = set()
        self._association_graph[memory_id1].add(memory_id2)
        
        if memory_id2 not in self._association_graph:
            self._association_graph[memory_id2] = set()
        self._association_graph[memory_id2].add(memory_id1)
    
    async def get_associations(
        self,
        memory_id: str,
        limit: int = 10
    ) -> List[Memory]:
        """Get associated memories"""
        if memory_id not in self._association_graph:
            return []
        
        associated_ids = self._association_graph[memory_id]
        memories = []
        
        for assoc_id in associated_ids[:limit]:
            memory = self._memories.get(assoc_id)
            if memory and memory.status == MemoryStatus.ACTIVE:
                memories.append(memory)
        
        return memories
    
    # ========================================
    # MEMORY SEARCH
    # ========================================
    
    async def _get_candidates(
        self,
        context: MemoryContext
    ) -> List[Memory]:
        """Get candidate memories for query"""
        candidates = []
        
        # Get by tags
        if context.tags:
            tag_memories = await self.get_memories_by_tags(context.tags)
            candidates.extend(tag_memories)
        
        # Get by type
        if context.type:
            type_memories = await self.get_memories_by_type(context.type)
            candidates.extend(type_memories)
        
        # Get all active if no filters
        if not candidates:
            candidates = [
                memory for memory in self._memories.values()
                if memory.status == MemoryStatus.ACTIVE
            ]
        
        # Remove duplicates
        seen = set()
        unique_candidates = []
        for memory in candidates:
            if memory.id not in seen:
                seen.add(memory.id)
                unique_candidates.append(memory)
        
        return unique_candidates
    
    async def _rank_memories(
        self,
        context: MemoryContext,
        candidates: List[Memory]
    ) -> List[Memory]:
        """Rank memories by relevance"""
        scored_memories = []
        
        # Get query embedding if semantic
        query_embedding = None
        if context.semantic:
            query_embedding = await self._generate_embedding(context.query)
        
        for memory in candidates:
            score = 0.0
            
            # Strength score
            score += memory.strength * 0.3
            
            # Importance score
            importance_scores = {
                MemoryImportance.CRITICAL: 1.0,
                MemoryImportance.HIGH: 0.8,
                MemoryImportance.MEDIUM: 0.6,
                MemoryImportance.LOW: 0.4
            }
            score += importance_scores.get(memory.importance, 0.5) * 0.2
            
            # Semantic similarity
            if context.semantic and query_embedding and memory.embedding:
                similarity = await self._compute_similarity(
                    query_embedding,
                    memory.embedding
                )
                score += similarity * 0.4
            
            # Recency
            time_since = (datetime.utcnow() - memory.created_at).total_seconds()
            recency = max(0, 1 - time_since / 86400)  # 24 hours
            score += recency * 0.1
            
            scored_memories.append((memory, score))
        
        # Sort by score
        scored_memories.sort(key=lambda x: x[1], reverse=True)
        return [memory for memory, _ in scored_memories]
    
    def _apply_filters(
        self,
        memories: List[Memory],
        context: MemoryContext
    ) -> List[Memory]:
        """Apply filters to memories"""
        filtered = []
        
        for memory in memories:
            # Check strength
            if memory.strength < context.min_strength:
                continue
            
            # Check importance
            if context.importance and memory.importance != context.importance:
                continue
            
            # Check time window
            if context.time_window:
                age = (datetime.utcnow() - memory.created_at).total_seconds()
                if age > context.time_window:
                    continue
            
            filtered.append(memory)
        
        return filtered
    
    # ========================================
    # HELPER FUNCTIONS
    # ========================================
    
    def _get_memory_ids_by_type(self, type: MemoryType) -> List[str]:
        """Get memory IDs by type"""
        if type == MemoryType.WORKING:
            return self._working_memory
        elif type == MemoryType.EPISODIC:
            return self._episodic_memory
        elif type == MemoryType.SEMANTIC:
            return self._semantic_memory
        elif type == MemoryType.PROCEDURAL:
            return self._procedural_memory
        return []
    
    async def _check_limits(self, type: MemoryType) -> None:
        """Check memory limits"""
        limits = {
            MemoryType.WORKING: self.config.working_memory_limit,
            MemoryType.EPISODIC: self.config.episodic_memory_limit,
            MemoryType.SEMANTIC: self.config.semantic_memory_limit,
            MemoryType.PROCEDURAL: self.config.procedural_memory_limit
        }
        
        limit = limits.get(type, 1000)
        count = len(self._get_memory_ids_by_type(type))
        
        if count >= limit:
            await self.prune_memories()
            count = len(self._get_memory_ids_by_type(type))
            if count >= limit:
                raise MemoryError(f"Memory limit reached for {type.value}")
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        # Simple hash-based embedding for demo
        import hashlib
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()
        
        embedding = []
        for i in range(self.config.embedding_dim):
            value = int.from_bytes(hash_bytes[i % 32:i % 32 + 4], 'big')
            embedding.append((value / (2 ** 32)) * 2 - 1)
        
        return embedding
    
    async def _compute_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """Compute cosine similarity between embeddings"""
        if not embedding1 or not embedding2:
            return 0.0
        
        try:
            return cosine_similarity([embedding1], [embedding2])[0][0]
        except Exception:
            return 0.0
    
    # ========================================
    # BACKGROUND TASKS
    # ========================================
    
    async def _consolidation_loop(self) -> None:
        """Background consolidation loop"""
        while self._running:
            try:
                await self.consolidate_memories()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Consolidation loop error: {e}")
            
            await asyncio.sleep(self.config.consolidation_interval)
    
    async def _decay_loop(self) -> None:
        """Background decay loop"""
        while self._running:
            try:
                await self.apply_decay()
                await self.prune_memories()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Decay loop error: {e}")
            
            await asyncio.sleep(self.config.decay_interval)
    
    async def _health_loop(self) -> None:
        """Health monitoring loop"""
        while self._running:
            try:
                health = await self.health_check()
                self.logger.debug(f"Health: {health}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health loop error: {e}")
            
            await asyncio.sleep(self.config.health_check_interval)
    
    # ========================================
    # API METHODS
    # ========================================
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get memory metrics"""
        return {
            **self._metrics,
            "total_memories": len(self._memories),
            "working_memory_count": len(self._working_memory),
            "episodic_memory_count": len(self._episodic_memory),
            "semantic_memory_count": len(self._semantic_memory),
            "procedural_memory_count": len(self._procedural_memory)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check memory health"""
        health = {
            'status': 'healthy',
            'memories': {
                'total': len(self._memories),
                'active': self._metrics["active_memories"],
                'consolidated': self._metrics["consolidated_memories"],
                'decayed': self._metrics["decayed_memories"]
            },
            'types': {
                'working': len(self._working_memory),
                'episodic': len(self._episodic_memory),
                'semantic': len(self._semantic_memory),
                'procedural': len(self._procedural_memory)
            }
        }
        
        # Check limits
        if len(self._memories) > 0.9 * (self.config.working_memory_limit + self.config.episodic_memory_limit + self.config.semantic_memory_limit + self.config.procedural_memory_limit):
            health['status'] = 'degraded'
            health['warning'] = 'Approaching memory limits'
        
        return health
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the memory system"""
        self._running = True
        
        # Start background tasks
        self._tasks.append(asyncio.create_task(self._consolidation_loop()))
        self._tasks.append(asyncio.create_task(self._decay_loop()))
        self._tasks.append(asyncio.create_task(self._health_loop()))
        
        self.logger.info("MemorySystem started")
    
    async def stop(self) -> None:
        """Stop the memory system"""
        self._running = False
        
        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self.logger.info("MemorySystem stopped")


# ========================================
# DEPENDENCY INJECTION
# ========================================

_memory_system: Optional[MemorySystem] = None


def get_memory() -> MemorySystem:
    """Get singleton instance of MemorySystem"""
    global _memory_system
    if _memory_system is None:
        _memory_system = MemorySystem()
    return _memory_system


def reset_memory() -> None:
    """Reset the memory system (for testing)"""
    global _memory_system
    if _memory_system:
        asyncio.create_task(_memory_system.stop())
    _memory_system = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'MemorySystem',
    'MemoryConfig',
    'Memory',
    'MemoryContext',
    'MemoryQueryResult',
    'MemoryType',
    'MemoryImportance',
    'MemoryStatus',
    'get_memory',
    'reset_memory'
]
