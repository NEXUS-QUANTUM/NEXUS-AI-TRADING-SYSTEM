"""
NEXUS AI TRADING SYSTEM - Memory Manager Module
Copyright © 2026 NEXUS QUANTUM LTD

This module implements a comprehensive memory management system for the NEXUS AI Trading System including:
- Integration of episodic, short-term, and long-term memory
- Memory consolidation and transfer
- Memory retrieval and recall
- Attention mechanisms
- Working memory management
- Memory optimization
- Cognitive architecture integration
- Memory persistence
- Memory synchronization
- Memory pruning
- Memory compression
- Memory allocation
- Memory monitoring
- Memory diagnostics
- Memory backup and recovery
- Memory versioning
- Memory replication
- Memory distribution
- Memory performance optimization
"""

import os
import sys
import json
import time
import logging
import hashlib
import pickle
import zlib
import threading
import queue
from typing import Dict, List, Optional, Tuple, Any, Union, Set, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Import memory modules
from .episodic_memory import EpisodicMemory, Episode, RetrievalStrategy, MemoryStatus as EpisodicStatus
from .short_term_memory import ShortTermMemory, WorkingMemory, MemoryItem, RetrievalStrategy as STMRetrievalStrategy
from .long_term_memory import LongTermMemory, KnowledgeItem, RetrievalMode, KnowledgeType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/memory_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Enums and Constants
# ============================================

class MemoryType(Enum):
    """Types of memory."""
    EPISODIC = "episodic"
    SHORT_TERM = "short_term"
    WORKING = "working"
    LONG_TERM = "long_term"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    DECLARATIVE = "declarative"
    IMPLICIT = "implicit"
    EXPLICIT = "explicit"


class MemoryOperation(Enum):
    """Memory operations."""
    STORE = "store"
    RETRIEVE = "retrieve"
    CONSOLIDATE = "consolidate"
    TRANSFER = "transfer"
    FORGET = "forget"
    UPDATE = "update"
    MERGE = "merge"
    COMPRESS = "compress"
    EXPAND = "expand"
    PRUNE = "prune"
    BACKUP = "backup"
    RESTORE = "restore"


class MemoryPriority(Enum):
    """Memory priorities."""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


@dataclass
class MemoryConfig:
    """Configuration for memory manager."""
    # Memory capacities
    short_term_capacity: int = 100
    working_memory_capacity: int = 20
    episodic_max_size: int = 10000
    long_term_max_items: int = 100000
    
    # Memory parameters
    embedding_dim: int = 256
    consolidation_threshold: float = 0.7
    importance_threshold: float = 0.8
    decay_rate: float = 0.01
    transfer_interval: int = 100
    
    # Performance settings
    enable_parallel: bool = True
    enable_compression: bool = True
    enable_backup: bool = True
    backup_interval: int = 1000
    
    # Memory directories
    memory_dir: str = "./memory"
    backup_dir: str = "./memory/backups"
    
    # Device settings
    device: str = "cpu"
    
    # Logging
    log_level: str = "INFO"


@dataclass
class MemoryOperationLog:
    """Log of memory operations."""
    operation: MemoryOperation
    memory_type: MemoryType
    item_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    duration: float = 0.0
    success: bool = True
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryStatistics:
    """Comprehensive memory statistics."""
    timestamp: float
    total_items: int
    by_type: Dict[str, int]
    memory_usage: int
    operation_count: int
    operation_success_rate: float
    average_retrieval_time: float
    average_consolidation_time: float
    transfer_count: int
    prune_count: int
    backup_count: int
    last_backup: Optional[float] = None
    health_score: float = 1.0
    warnings: List[str] = field(default_factory=list)


# ============================================
# Memory Manager Implementation
# ============================================

class MemoryManager:
    """
    Central memory manager for the NEXUS AI Trading System.
    
    This class integrates and manages all memory systems including
    episodic, short-term, working, and long-term memory.
    """
    
    def __init__(self, config: MemoryConfig):
        """
        Initialize the memory manager.
        
        Args:
            config: Memory configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Memory systems
        self.short_term = ShortTermMemory(
            max_size=config.short_term_capacity,
            embedding_dim=config.embedding_dim,
            decay_rate=config.decay_rate,
            memory_dir=config.memory_dir + "/short_term",
            device=config.device,
        )
        
        self.working_memory = WorkingMemory(
            max_size=config.working_memory_capacity,
            embedding_dim=config.embedding_dim,
            memory_dir=config.memory_dir + "/working",
            device=config.device,
        )
        
        self.episodic = EpisodicMemory(
            max_size=config.episodic_max_size,
            embedding_dim=config.embedding_dim,
            consolidation_threshold=config.consolidation_threshold,
            importance_threshold=config.importance_threshold,
            forgetting_threshold=0.1,
            temporal_decay_rate=config.decay_rate,
            consolidation_interval=config.transfer_interval,
            memory_dir=config.memory_dir + "/episodic",
            enable_compression=config.enable_compression,
            enable_embedding=True,
            enable_context=True,
            device=config.device,
        )
        
        self.long_term = LongTermMemory(
            max_items=config.long_term_max_items,
            embedding_dim=config.embedding_dim,
            consolidation_threshold=config.consolidation_threshold,
            importance_threshold=config.importance_threshold,
            decay_rate=config.decay_rate,
            consolidation_interval=config.transfer_interval,
            memory_dir=config.memory_dir + "/long_term",
            enable_graph=True,
            enable_embedding=True,
            enable_semantic=True,
            device=config.device,
        )
        
        # Operation tracking
        self.operation_logs: List[MemoryOperationLog] = []
        self.operation_queue = queue.Queue()
        
        # Statistics
        self.stats = MemoryStatistics(
            timestamp=time.time(),
            total_items=0,
            by_type={},
            memory_usage=0,
            operation_count=0,
            operation_success_rate=1.0,
            average_retrieval_time=0.0,
            average_consolidation_time=0.0,
            transfer_count=0,
            prune_count=0,
            backup_count=0,
        )
        
        # Threading
        self._lock = threading.Lock()
        self._running = True
        self._worker_thread: Optional[threading.Thread] = None
        
        # Backup
        self.backup_dir = Path(config.backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize
        self._init_backup()
        self._start_worker()
        
        self.logger.info("Memory Manager initialized")
        self.logger.info(f"Short-term capacity: {config.short_term_capacity}")
        self.logger.info(f"Working memory capacity: {config.working_memory_capacity}")
        self.logger.info(f"Episodic max size: {config.episodic_max_size}")
        self.logger.info(f"Long-term max items: {config.long_term_max_items}")
    
    # ============================================
    # Initialization Methods
    # ============================================
    
    def _init_backup(self) -> None:
        """Initialize backup system."""
        if not self.config.enable_backup:
            return
        
        # Load latest backup if available
        backup_files = sorted(self.backup_dir.glob("memory_backup_*.pkl"))
        if backup_files:
            latest = backup_files[-1]
            try:
                with open(latest, 'rb') as f:
                    data = pickle.load(f)
                    self._restore_from_backup(data)
                self.logger.info(f"Restored from backup: {latest.name}")
            except Exception as e:
                self.logger.warning(f"Failed to restore backup: {e}")
    
    def _start_worker(self) -> None:
        """Start background worker thread."""
        if self._worker_thread is not None:
            return
        
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="MemoryWorker"
        )
        self._worker_thread.start()
        self.logger.debug("Worker thread started")
    
    def _stop_worker(self) -> None:
        """Stop background worker thread."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
            self._worker_thread = None
        self.logger.debug("Worker thread stopped")
    
    # ============================================
    # Worker Loop
    # ============================================
    
    def _worker_loop(self) -> None:
        """Background worker loop for async operations."""
        while self._running:
            try:
                # Process operation queue
                if not self.operation_queue.empty():
                    operation = self.operation_queue.get(timeout=1)
                    self._process_operation(operation)
                
                # Periodic consolidation
                if self._should_consolidate():
                    self._consolidate_memory()
                
                # Periodic backup
                if self.config.enable_backup and self._should_backup():
                    self._create_backup()
                
                # Periodic pruning
                if self._should_prune():
                    self._prune_memory()
                
                time.sleep(1)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Worker error: {e}")
                time.sleep(5)
    
    # ============================================
    # Memory Operations
    # ============================================
    
    def store(
        self,
        content: Any,
        memory_type: MemoryType = MemoryType.SHORT_TERM,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        priority: MemoryPriority = MemoryPriority.MEDIUM,
    ) -> Optional[str]:
        """
        Store content in memory.
        
        Args:
            content: Content to store
            memory_type: Target memory type
            importance: Importance weight
            metadata: Additional metadata
            priority: Operation priority
            
        Returns:
            Item ID if stored, None otherwise
        """
        start_time = time.time()
        item_id = None
        
        try:
            if memory_type == MemoryType.EPISODIC:
                # Store as episode
                item_id = self.episodic.store_episode(
                    state=content.get('state', {}),
                    action=content.get('action', {}),
                    reward=content.get('reward', 0.0),
                    next_state=content.get('next_state', {}),
                    done=content.get('done', False),
                    metadata=metadata,
                    importance=importance,
                    strategy=content.get('strategy', 'unknown'),
                    market_conditions=content.get('market_conditions', {}),
                )
            
            elif memory_type == MemoryType.SHORT_TERM:
                # Store in short-term memory
                item_id = self.short_term.store_memory(
                    content=content,
                    importance=importance,
                    metadata=metadata,
                )
            
            elif memory_type == MemoryType.WORKING:
                # Store in working memory
                item_id = self.working_memory.store_item(
                    content=content,
                    importance=importance,
                    metadata=metadata,
                )
            
            elif memory_type == MemoryType.LONG_TERM:
                # Store in long-term memory
                item_id = self.long_term.store_knowledge(
                    content=content,
                    knowledge_type=KnowledgeType.FACT,
                    metadata=metadata,
                    importance=importance,
                )
            
            else:
                self.logger.warning(f"Unsupported memory type: {memory_type}")
                return None
            
            # Log operation
            self._log_operation(
                operation=MemoryOperation.STORE,
                memory_type=memory_type,
                item_id=item_id,
                duration=time.time() - start_time,
                success=True,
            )
            
            # Update statistics
            self._update_stats()
            
            return item_id
            
        except Exception as e:
            self.logger.error(f"Store failed: {e}")
            self._log_operation(
                operation=MemoryOperation.STORE,
                memory_type=memory_type,
                duration=time.time() - start_time,
                success=False,
                details={'error': str(e)},
            )
            return None
    
    def retrieve(
        self,
        query: Any,
        memory_type: MemoryType = MemoryType.SHORT_TERM,
        n: int = 10,
        **kwargs
    ) -> List[Any]:
        """
        Retrieve from memory.
        
        Args:
            query: Query for retrieval
            memory_type: Target memory type
            n: Number of items to retrieve
            **kwargs: Additional retrieval parameters
            
        Returns:
            List of retrieved items
        """
        start_time = time.time()
        results = []
        
        try:
            if memory_type == MemoryType.EPISODIC:
                # Retrieve episodes
                strategy = kwargs.get('strategy', RetrievalStrategy.HYBRID)
                episodes = self.episodic.retrieve_episodes(
                    query=query,
                    n=n,
                    strategy=strategy,
                    min_importance=kwargs.get('min_importance', 0.0),
                    max_importance=kwargs.get('max_importance', 1.0),
                )
                results = [ep.content for ep in episodes]
            
            elif memory_type == MemoryType.SHORT_TERM:
                # Retrieve from short-term
                strategy = kwargs.get('strategy', STMRetrievalStrategy.HYBRID)
                items = self.short_term.retrieve_memory(
                    query=query,
                    n=n,
                    strategy=strategy,
                    min_importance=kwargs.get('min_importance', 0.0),
                )
                results = [item.content for item in items]
            
            elif memory_type == MemoryType.WORKING:
                # Retrieve from working memory
                items = self.working_memory.retrieve(
                    query=query,
                    n=n,
                )
                results = [item.content for item in items]
            
            elif memory_type == MemoryType.LONG_TERM:
                # Retrieve from long-term
                mode = kwargs.get('mode', RetrievalMode.SEMANTIC)
                items = self.long_term.retrieve_knowledge(
                    query=query,
                    mode=mode,
                    n=n,
                    min_importance=kwargs.get('min_importance', 0.0),
                    max_importance=kwargs.get('max_importance', 1.0),
                )
                results = [item.content for item in items]
            
            else:
                self.logger.warning(f"Unsupported memory type: {memory_type}")
                return []
            
            # Log operation
            self._log_operation(
                operation=MemoryOperation.RETRIEVE,
                memory_type=memory_type,
                duration=time.time() - start_time,
                success=True,
                details={'results_count': len(results)},
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Retrieval failed: {e}")
            self._log_operation(
                operation=MemoryOperation.RETRIEVE,
                memory_type=memory_type,
                duration=time.time() - start_time,
                success=False,
                details={'error': str(e)},
            )
            return []
    
    # ============================================
    # Memory Consolidation
    # ============================================
    
    def consolidate(self, source: MemoryType, target: MemoryType) -> int:
        """
        Consolidate memory from source to target.
        
        Args:
            source: Source memory type
            target: Target memory type
            
        Returns:
            Number of items consolidated
        """
        start_time = time.time()
        count = 0
        
        try:
            if source == MemoryType.SHORT_TERM and target == MemoryType.EPISODIC:
                # Consolidate from short-term to episodic
                items = self.short_term.get_all_items()
                for item in items[:100]:  # Limit per consolidation
                    if item.importance >= self.config.consolidation_threshold:
                        # Convert to episode
                        self.episodic.store_episode(
                            state=item.content.get('state', {}),
                            action=item.content.get('action', {}),
                            reward=item.content.get('reward', 0.0),
                            next_state=item.content.get('next_state', {}),
                            done=item.content.get('done', False),
                            metadata=item.metadata,
                            importance=item.importance,
                        )
                        count += 1
                        # Remove from short-term
                        self.short_term.forget_memory(item.id)
            
            elif source == MemoryType.EPISODIC and target == MemoryType.LONG_TERM:
                # Consolidate from episodic to long-term
                episodes = self.episodic.retrieve_episodes(
                    query=None,
                    n=50,
                    strategy=RetrievalStrategy.IMPORTANCE,
                )
                for ep in episodes:
                    if ep.importance >= self.config.consolidation_threshold:
                        # Convert to knowledge
                        self.long_term.store_knowledge(
                            content=ep.state,
                            knowledge_type=KnowledgeType.EPISODIC,
                            metadata=ep.metadata,
                            importance=ep.importance,
                            source="episodic_consolidation",
                        )
                        count += 1
            
            elif source == MemoryType.WORKING and target == MemoryType.SHORT_TERM:
                # Consolidate from working to short-term
                items = self.working_memory.get_all_items()
                for item in items:
                    self.short_term.store_memory(
                        content=item.content,
                        importance=item.importance,
                        metadata=item.metadata,
                    )
                    count += 1
                    self.working_memory.forget(item.id)
            
            else:
                self.logger.warning(f"Unsupported consolidation: {source} -> {target}")
                return 0
            
            # Log operation
            self._log_operation(
                operation=MemoryOperation.CONSOLIDATE,
                memory_type=source,
                duration=time.time() - start_time,
                success=True,
                details={'source': source.value, 'target': target.value, 'count': count},
            )
            
            self.stats.transfer_count += count
            self._update_stats()
            
            return count
            
        except Exception as e:
            self.logger.error(f"Consolidation failed: {e}")
            self._log_operation(
                operation=MemoryOperation.CONSOLIDATE,
                memory_type=source,
                duration=time.time() - start_time,
                success=False,
                details={'error': str(e)},
            )
            return 0
    
    def _consolidate_memory(self) -> None:
        """Periodic memory consolidation."""
        self.logger.debug("Running periodic consolidation")
        
        # Consolidate working -> short-term
        self.consolidate(MemoryType.WORKING, MemoryType.SHORT_TERM)
        
        # Consolidate short-term -> episodic
        self.consolidate(MemoryType.SHORT_TERM, MemoryType.EPISODIC)
        
        # Consolidate episodic -> long-term
        self.consolidate(MemoryType.EPISODIC, MemoryType.LONG_TERM)
    
    # ============================================
    # Memory Pruning
    # ============================================
    
    def prune(self, memory_type: MemoryType, threshold: float = 0.1) -> int:
        """
        Prune memory by removing low-importance items.
        
        Args:
            memory_type: Target memory type
            threshold: Importance threshold
            
        Returns:
            Number of items pruned
        """
        start_time = time.time()
        count = 0
        
        try:
            if memory_type == MemoryType.SHORT_TERM:
                # Prune short-term memory
                items = self.short_term.get_all_items()
                for item in items:
                    if item.importance < threshold:
                        self.short_term.forget_memory(item.id)
                        count += 1
            
            elif memory_type == MemoryType.EPISODIC:
                # Prune episodic memory
                self.episodic.forget_episodes({'max_importance': threshold})
                count = len([ep for ep in self.episodic.episodes.values() if ep.status == EpisodicStatus.FORGOTTEN])
            
            elif memory_type == MemoryType.LONG_TERM:
                # Prune long-term memory
                # Use long-term's forgetting mechanism
                items = self.long_term.items.values()
                for item in items:
                    if item.importance < threshold:
                        self.long_term._remove_item(item.id)
                        count += 1
            
            else:
                self.logger.warning(f"Unsupported prune type: {memory_type}")
                return 0
            
            # Log operation
            self._log_operation(
                operation=MemoryOperation.PRUNE,
                memory_type=memory_type,
                duration=time.time() - start_time,
                success=True,
                details={'count': count},
            )
            
            self.stats.prune_count += count
            self._update_stats()
            
            return count
            
        except Exception as e:
            self.logger.error(f"Prune failed: {e}")
            self._log_operation(
                operation=MemoryOperation.PRUNE,
                memory_type=memory_type,
                duration=time.time() - start_time,
                success=False,
                details={'error': str(e)},
            )
            return 0
    
    def _prune_memory(self) -> None:
        """Periodic memory pruning."""
        self.logger.debug("Running periodic pruning")
        
        # Prune low-importance items
        self.prune(MemoryType.SHORT_TERM, threshold=0.1)
        self.prune(MemoryType.EPISODIC, threshold=0.05)
        self.prune(MemoryType.LONG_TERM, threshold=0.05)
    
    # ============================================
    # Memory Backup and Recovery
    # ============================================
    
    def backup(self) -> str:
        """
        Create a full memory backup.
        
        Returns:
            Backup file path
        """
        start_time = time.time()
        
        try:
            backup_data = {
                'timestamp': time.time(),
                'version': '1.0',
                'short_term': self.short_term.export_memory('pickle'),
                'working': self.working_memory.export_memory('pickle'),
                'episodic': self.episodic.export_memory('pickle'),
                'long_term': self.long_term.export_memory('pickle'),
                'stats': asdict(self.stats),
            }
            
            # Compress and save
            backup_path = self.backup_dir / f"memory_backup_{int(time.time())}.pkl"
            with open(backup_path, 'wb') as f:
                pickle.dump(backup_data, f)
            
            # Log operation
            self._log_operation(
                operation=MemoryOperation.BACKUP,
                memory_type=MemoryType.EPISODIC,
                duration=time.time() - start_time,
                success=True,
                details={'path': str(backup_path)},
            )
            
            self.stats.backup_count += 1
            self.stats.last_backup = time.time()
            
            # Keep only latest 10 backups
            backups = sorted(self.backup_dir.glob("memory_backup_*.pkl"))
            for old_backup in backups[:-10]:
                old_backup.unlink()
            
            self.logger.info(f"Backup created: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            self.logger.error(f"Backup failed: {e}")
            self._log_operation(
                operation=MemoryOperation.BACKUP,
                memory_type=MemoryType.EPISODIC,
                duration=time.time() - start_time,
                success=False,
                details={'error': str(e)},
            )
            return ""
    
    def restore(self, backup_path: Optional[str] = None) -> bool:
        """
        Restore from backup.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if restore successful
        """
        try:
            if backup_path is None:
                # Use latest backup
                backups = sorted(self.backup_dir.glob("memory_backup_*.pkl"))
                if not backups:
                    self.logger.warning("No backups found")
                    return False
                backup_path = str(backups[-1])
            
            with open(backup_path, 'rb') as f:
                data = pickle.load(f)
            
            self._restore_from_backup(data)
            
            self._log_operation(
                operation=MemoryOperation.RESTORE,
                memory_type=MemoryType.EPISODIC,
                duration=0,
                success=True,
                details={'path': backup_path},
            )
            
            self.logger.info(f"Restored from backup: {backup_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Restore failed: {e}")
            return False
    
    def _restore_from_backup(self, data: Dict[str, Any]) -> None:
        """Restore memory from backup data."""
        if 'short_term' in data:
            self.short_term.import_memory(data['short_term'], 'pickle')
        if 'working' in data:
            self.working_memory.import_memory(data['working'], 'pickle')
        if 'episodic' in data:
            self.episodic.import_memory(data['episodic'], 'pickle')
        if 'long_term' in data:
            self.long_term.import_memory(data['long_term'], 'pickle')
        if 'stats' in data:
            self.stats = MemoryStatistics(**data['stats'])
        
        self._update_stats()
    
    # ============================================
    # Memory Query and Analysis
    # ============================================
    
    def query(
        self,
        query: Any,
        memory_types: Optional[List[MemoryType]] = None,
        n: int = 10,
        **kwargs
    ) -> Dict[MemoryType, List[Any]]:
        """
        Query multiple memory systems.
        
        Args:
            query: Query
            memory_types: Memory types to query
            n: Number of results per type
            **kwargs: Additional parameters
            
        Returns:
            Dictionary of results by memory type
        """
        if memory_types is None:
            memory_types = [
                MemoryType.WORKING,
                MemoryType.SHORT_TERM,
                MemoryType.EPISODIC,
                MemoryType.LONG_TERM,
            ]
        
        results = {}
        for mt in memory_types:
            try:
                results[mt] = self.retrieve(query, mt, n, **kwargs)
            except Exception as e:
                self.logger.warning(f"Query failed for {mt.value}: {e}")
                results[mt] = []
        
        return results
    
    def get_statistics(self) -> MemoryStatistics:
        """
        Get comprehensive memory statistics.
        
        Returns:
            Memory statistics
        """
        # Update statistics
        self._update_stats()
        
        # Calculate health score
        health = 1.0
        warnings = []
        
        # Check memory capacities
        if len(self.short_term.items) > self.config.short_term_capacity * 0.9:
            health -= 0.1
            warnings.append("Short-term memory near capacity")
        
        if len(self.episodic.episodes) > self.config.episodic_max_size * 0.9:
            health -= 0.1
            warnings.append("Episodic memory near capacity")
        
        if len(self.long_term.items) > self.config.long_term_max_items * 0.9:
            health -= 0.1
            warnings.append("Long-term memory near capacity")
        
        # Check operation success rate
        if self.stats.operation_success_rate < 0.8:
            health -= 0.2
            warnings.append("Low operation success rate")
        
        # Check backup status
        if self.config.enable_backup:
            if self.stats.last_backup is None or time.time() - self.stats.last_backup > 86400 * 7:
                health -= 0.1
                warnings.append("No recent backup")
        
        self.stats.health_score = max(0, health)
        self.stats.warnings = warnings
        self.stats.timestamp = time.time()
        
        return self.stats
    
    def _update_stats(self) -> None:
        """Update memory statistics."""
        self.stats.total_items = (
            len(self.short_term.items) +
            len(self.working_memory.items) +
            len(self.episodic.episodes) +
            len(self.long_term.items)
        )
        
        self.stats.by_type = {
            'short_term': len(self.short_term.items),
            'working': len(self.working_memory.items),
            'episodic': len(self.episodic.episodes),
            'long_term': len(self.long_term.items),
        }
        
        # Calculate memory usage (approximate)
        self.stats.memory_usage = (
            self.short_term._calculate_memory_usage() +
            self.working_memory._calculate_memory_usage() +
            self.episodic._calculate_memory_usage() +
            self.long_term._calculate_memory_usage()
        )
    
    # ============================================
    # Operation Logging
    # ============================================
    
    def _log_operation(
        self,
        operation: MemoryOperation,
        memory_type: MemoryType,
        item_id: Optional[str] = None,
        duration: float = 0.0,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log a memory operation.
        
        Args:
            operation: Operation type
            memory_type: Memory type
            item_id: Item ID
            duration: Operation duration
            success: Operation success
            details: Additional details
        """
        log = MemoryOperationLog(
            operation=operation,
            memory_type=memory_type,
            item_id=item_id,
            timestamp=time.time(),
            duration=duration,
            success=success,
            details=details or {},
        )
        
        with self._lock:
            self.operation_logs.append(log)
            if len(self.operation_logs) > 1000:
                self.operation_logs = self.operation_logs[-1000:]
            
            self.stats.operation_count += 1
            success_count = sum(1 for l in self.operation_logs if l.success)
            self.stats.operation_success_rate = success_count / len(self.operation_logs) if self.operation_logs else 1.0
            
            # Update average times
            retrieve_logs = [l for l in self.operation_logs if l.operation == MemoryOperation.RETRIEVE]
            if retrieve_logs:
                self.stats.average_retrieval_time = sum(l.duration for l in retrieve_logs) / len(retrieve_logs)
            
            consolidate_logs = [l for l in self.operation_logs if l.operation == MemoryOperation.CONSOLIDATE]
            if consolidate_logs:
                self.stats.average_consolidation_time = sum(l.duration for l in consolidate_logs) / len(consolidate_logs)
    
    def get_operation_logs(
        self,
        limit: int = 100,
        operation: Optional[MemoryOperation] = None,
        memory_type: Optional[MemoryType] = None,
        success_only: bool = False,
    ) -> List[MemoryOperationLog]:
        """
        Get operation logs.
        
        Args:
            limit: Maximum number of logs
            operation: Filter by operation
            memory_type: Filter by memory type
            success_only: Only successful operations
            
        Returns:
            List of operation logs
        """
        logs = self.operation_logs[-limit:] if limit > 0 else self.operation_logs
        
        if operation:
            logs = [l for l in logs if l.operation == operation]
        
        if memory_type:
            logs = [l for l in logs if l.memory_type == memory_type]
        
        if success_only:
            logs = [l for l in logs if l.success]
        
        return logs
    
    # ============================================
    # Memory Control
    # ============================================
    
    def clear(self, memory_type: Optional[MemoryType] = None) -> None:
        """
        Clear memory.
        
        Args:
            memory_type: Memory type to clear (None for all)
        """
        if memory_type is None or memory_type == MemoryType.SHORT_TERM:
            self.short_term.clear()
        
        if memory_type is None or memory_type == MemoryType.WORKING:
            self.working_memory.clear()
        
        if memory_type is None or memory_type == MemoryType.EPISODIC:
            self.episodic.episodes.clear()
            self.episodic.episode_order.clear()
            self.episodic.episode_index.clear()
        
        if memory_type is None or memory_type == MemoryType.LONG_TERM:
            self.long_term.items.clear()
            self.long_term.item_order.clear()
            self.long_term.item_index.clear()
        
        self.logger.info(f"Cleared memory: {memory_type.value if memory_type else 'all'}")
        self._update_stats()
    
    def _should_consolidate(self) -> bool:
        """Check if consolidation is needed."""
        return time.time() % self.config.transfer_interval < 1
    
    def _should_backup(self) -> bool:
        """Check if backup is needed."""
        if not self.config.enable_backup:
            return False
        
        if self.stats.last_backup is None:
            return True
        
        return time.time() - self.stats.last_backup > self.config.backup_interval
    
    def _should_prune(self) -> bool:
        """Check if pruning is needed."""
        # Prune when memory is near capacity
        short_term_usage = len(self.short_term.items) / self.config.short_term_capacity
        episodic_usage = len(self.episodic.episodes) / self.config.episodic_max_size
        long_term_usage = len(self.long_term.items) / self.config.long_term_max_items
        
        return (short_term_usage > 0.8 or episodic_usage > 0.8 or long_term_usage > 0.8)
    
    def _process_operation(self, operation: Any) -> None:
        """
        Process an operation from the queue.
        
        Args:
            operation: Operation to process
        """
        # This is a placeholder for async operations
        pass
    
    # ============================================
    # Shutdown
    # ============================================
    
    def shutdown(self) -> None:
        """Shutdown the memory manager."""
        self.logger.info("Shutting down memory manager...")
        
        # Stop worker
        self._stop_worker()
        
        # Save all memory
        self.short_term._save_memory()
        self.working_memory._save_memory()
        self.episodic._save_memory()
        self.long_term._save_memory()
        
        # Create final backup
        if self.config.enable_backup:
            self.backup()
        
        self.logger.info("Memory manager shutdown complete")

# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point for CLI."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NEXUS Memory Manager CLI')
    parser.add_argument('--command', choices=['stats', 'backup', 'restore', 'clear', 'prune', 'consolidate'],
                       required=True, help='Command to execute')
    parser.add_argument('--memory-dir', type=str, default='./memory', help='Memory directory')
    parser.add_argument('--backup-dir', type=str, default='./memory/backups', help='Backup directory')
    parser.add_argument('--backup-file', type=str, help='Backup file for restore')
    parser.add_argument('--memory-type', type=str, default='all', help='Memory type')
    parser.add_argument('--threshold', type=float, default=0.1, help='Prune threshold')
    parser.add_argument('--short-term-capacity', type=int, default=100, help='Short-term capacity')
    parser.add_argument('--working-capacity', type=int, default=20, help='Working memory capacity')
    parser.add_argument('--episodic-max', type=int, default=10000, help='Episodic max size')
    parser.add_argument('--long-term-max', type=int, default=100000, help='Long-term max items')
    
    args = parser.parse_args()
    
    # Create config
    config = MemoryConfig(
        memory_dir=args.memory_dir,
        backup_dir=args.backup_dir,
        short_term_capacity=args.short_term_capacity,
        working_memory_capacity=args.working_capacity,
        episodic_max_size=args.episodic_max,
        long_term_max_items=args.long_term_max,
    )
    
    # Initialize manager
    manager = MemoryManager(config)
    
    if args.command == 'stats':
        stats = manager.get_statistics()
        print("\nMemory Statistics:")
        print("-" * 50)
        print(f"Total Items: {stats.total_items}")
        print(f"By Type: {stats.by_type}")
        print(f"Memory Usage: {stats.memory_usage / 1024:.2f} KB")
        print(f"Operation Count: {stats.operation_count}")
        print(f"Success Rate: {stats.operation_success_rate:.2%}")
        print(f"Avg Retrieval Time: {stats.average_retrieval_time:.3f}s")
        print(f"Avg Consolidation Time: {stats.average_consolidation_time:.3f}s")
        print(f"Transfer Count: {stats.transfer_count}")
        print(f"Prune Count: {stats.prune_count}")
        print(f"Backup Count: {stats.backup_count}")
        print(f"Health Score: {stats.health_score:.2f}")
        if stats.warnings:
            print("\nWarnings:")
            for warning in stats.warnings:
                print(f"  - {warning}")
    
    elif args.command == 'backup':
        path = manager.backup()
        if path:
            print(f"Backup created: {path}")
        else:
            print("Backup failed")
    
    elif args.command == 'restore':
        success = manager.restore(args.backup_file)
        if success:
            print("Restore successful")
        else:
            print("Restore failed")
    
    elif args.command == 'clear':
        memory_type = None if args.memory_type == 'all' else MemoryType(args.memory_type)
        manager.clear(memory_type)
        print(f"Cleared memory: {args.memory_type}")
    
    elif args.command == 'prune':
        memory_type = MemoryType(args.memory_type) if args.memory_type != 'all' else MemoryType.EPISODIC
        count = manager.prune(memory_type, args.threshold)
        print(f"Pruned {count} items from {args.memory_type}")
    
    elif args.command == 'consolidate':
        source = MemoryType(args.memory_type) if args.memory_type != 'all' else MemoryType.SHORT_TERM
        target = MemoryType.LONG_TERM if source == MemoryType.EPISODIC else MemoryType.EPISODIC
        count = manager.consolidate(source, target)
        print(f"Consolidated {count} items from {source.value} to {target.value}")
    
    # Shutdown
    manager.shutdown()


if __name__ == '__main__':
    main()
