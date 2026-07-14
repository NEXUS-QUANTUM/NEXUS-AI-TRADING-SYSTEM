"""
NEXUS AI TRADING SYSTEM - Memory Module
Copyright © 2026 NEXUS QUANTUM LTD

This module provides comprehensive memory management capabilities for the NEXUS AI Trading System including:
- Episodic memory for trading experiences
- Short-term and working memory for active processing
- Long-term memory for persistent knowledge
- Vector store for semantic search and similarity matching
- Memory consolidation and transfer
- Attention mechanisms
- Memory retrieval and recall
- Memory persistence and backup
- Memory optimization and pruning
- Memory statistics and monitoring
- Integration with cognitive architecture
- Distributed memory operations
- Memory versioning and snapshots
- Memory compression and encoding
- Memory replication and synchronization

The memory module enables the NEXUS AI Trading System to:
- Learn from past trading experiences
- Maintain context and state information
- Build persistent knowledge over time
- Perform semantic search and similarity matching
- Manage attention and focus
- Consolidate and transfer knowledge
- Maintain multiple memory systems
- Scale memory capacity efficiently
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple, Type
from dataclasses import dataclass, field
from enum import Enum

# ============================================
# Module Version and Metadata
# ============================================

__version__ = '3.0.0'
__author__ = 'NEXUS QUANTUM LTD'
__description__ = 'Memory Module for NEXUS AI Trading System'
__license__ = 'Proprietary - Copyright © 2026 NEXUS QUANTUM LTD'

# ============================================
# Module Logger Configuration
# ============================================

logger = logging.getLogger(__name__)

# Create logs directory
LOG_DIR = Path('logs')
LOG_DIR.mkdir(exist_ok=True)

# Configure module logger
if not logger.handlers:
    # File handler
    file_handler = logging.FileHandler(LOG_DIR / 'memory.log')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(console_handler)
    
    logger.setLevel(logging.INFO)

# ============================================
# Module Dependencies
# ============================================

DEPENDENCIES: Dict[str, str] = {
    'numpy': '>=1.24.0',
    'scipy': '>=1.10.0',
    'scikit-learn': '>=1.3.0',
    'torch': '>=2.0.0',
    'faiss-cpu': '>=1.7.4',
    'networkx': '>=3.0.0',
    'tqdm': '>=4.65.0',
}

# Optional dependencies
OPTIONAL_DEPENDENCIES: Dict[str, str] = {
    'faiss-gpu': '>=1.7.4',
}

# ============================================
# Import Submodules
# ============================================

# Import episodic memory
try:
    from .episodic_memory import (
        EpisodicMemory,
        Episode,
        RetrievalStrategy,
        MemoryStatus as EpisodicMemoryStatus,
        MemoryStats as EpisodicMemoryStats,
    )
except ImportError as e:
    logger.warning(f"Failed to import episodic_memory: {e}")
    EpisodicMemory = None
    Episode = None
    RetrievalStrategy = None
    EpisodicMemoryStatus = None
    EpisodicMemoryStats = None

# Import short-term memory
try:
    from .short_term_memory import (
        ShortTermMemory,
        WorkingMemory,
        MemoryItem,
        WorkingMemoryItem,
        MemoryChunk,
        MemoryStatus as ShortTermMemoryStatus,
        RetrievalStrategy as ShortTermRetrievalStrategy,
        AttentionType,
        MemoryStatistics as ShortTermMemoryStats,
    )
except ImportError as e:
    logger.warning(f"Failed to import short_term_memory: {e}")
    ShortTermMemory = None
    WorkingMemory = None
    MemoryItem = None
    WorkingMemoryItem = None
    MemoryChunk = None
    ShortTermMemoryStatus = None
    ShortTermRetrievalStrategy = None
    AttentionType = None
    ShortTermMemoryStats = None

# Import long-term memory
try:
    from .long_term_memory import (
        LongTermMemory,
        KnowledgeItem,
        KnowledgeGraph,
        KnowledgeType,
        MemoryStatus as LongTermMemoryStatus,
        RetrievalMode,
        MemoryStatistics as LongTermMemoryStats,
    )
except ImportError as e:
    logger.warning(f"Failed to import long_term_memory: {e}")
    LongTermMemory = None
    KnowledgeItem = None
    KnowledgeGraph = None
    KnowledgeType = None
    LongTermMemoryStatus = None
    RetrievalMode = None
    LongTermMemoryStats = None

# Import vector store
try:
    from .vector_store import (
        VectorStore,
        VectorMetadata,
        VectorSearchResult,
        IndexStatistics,
        IndexType,
        DistanceMetric,
        IndexStatus,
    )
except ImportError as e:
    logger.warning(f"Failed to import vector_store: {e}")
    VectorStore = None
    VectorMetadata = None
    VectorSearchResult = None
    IndexStatistics = None
    IndexType = None
    DistanceMetric = None
    IndexStatus = None

# Import memory manager
try:
    from .memory_manager import (
        MemoryManager,
        MemoryConfig,
        MemoryType,
        MemoryOperation,
        MemoryPriority,
        MemoryOperationLog,
        MemoryStatistics,
    )
except ImportError as e:
    logger.warning(f"Failed to import memory_manager: {e}")
    MemoryManager = None
    MemoryConfig = None
    MemoryType = None
    MemoryOperation = None
    MemoryPriority = None
    MemoryOperationLog = None
    MemoryStatistics = None

# ============================================
# Module Exports
# ============================================

__all__ = [
    # Episodic Memory
    'EpisodicMemory',
    'Episode',
    'RetrievalStrategy',
    'EpisodicMemoryStatus',
    'EpisodicMemoryStats',
    
    # Short-Term Memory
    'ShortTermMemory',
    'WorkingMemory',
    'MemoryItem',
    'WorkingMemoryItem',
    'MemoryChunk',
    'ShortTermMemoryStatus',
    'ShortTermRetrievalStrategy',
    'AttentionType',
    'ShortTermMemoryStats',
    
    # Long-Term Memory
    'LongTermMemory',
    'KnowledgeItem',
    'KnowledgeGraph',
    'KnowledgeType',
    'LongTermMemoryStatus',
    'RetrievalMode',
    'LongTermMemoryStats',
    
    # Vector Store
    'VectorStore',
    'VectorMetadata',
    'VectorSearchResult',
    'IndexStatistics',
    'IndexType',
    'DistanceMetric',
    'IndexStatus',
    
    # Memory Manager
    'MemoryManager',
    'MemoryConfig',
    'MemoryType',
    'MemoryOperation',
    'MemoryPriority',
    'MemoryOperationLog',
    'MemoryStatistics',
]

# ============================================
# Module Initialization
# ============================================

def check_dependencies() -> Tuple[bool, List[str]]:
    """
    Check if all required dependencies are installed.
    
    Returns:
        Tuple of (all_available, missing_dependencies)
    """
    missing = []
    for package_name, version_spec in DEPENDENCIES.items():
        try:
            import_name = package_name.replace('-', '_').replace('.', '_')
            if package_name == 'scikit-learn':
                import_name = 'sklearn'
            __import__(import_name)
        except ImportError:
            missing.append(f"{package_name}{version_spec}")
    
    if missing:
        logger.warning(f"Missing dependencies: {missing}")
        return False, missing
    
    logger.info("All dependencies are available")
    return True, []

def get_module_info() -> Dict[str, Any]:
    """
    Get comprehensive module information.
    
    Returns:
        Dictionary with module metadata
    """
    return {
        'name': __name__,
        'version': __version__,
        'author': __author__,
        'description': __description__,
        'license': __license__,
        'dependencies': DEPENDENCIES,
        'optional_dependencies': OPTIONAL_DEPENDENCIES,
        'python_version': sys.version,
        'python_executable': sys.executable,
        'platform': sys.platform,
        'available_submodules': {
            'episodic_memory': EpisodicMemory is not None,
            'short_term_memory': ShortTermMemory is not None,
            'long_term_memory': LongTermMemory is not None,
            'vector_store': VectorStore is not None,
            'memory_manager': MemoryManager is not None,
        },
        'log_level': logging.getLevelName(logger.level),
        'log_file': str(LOG_DIR / 'memory.log'),
    }

def setup_environment(
    log_level: str = 'INFO',
    seed: Optional[int] = 42,
    memory_dir: str = './memory',
) -> None:
    """
    Set up the environment for memory operations.
    
    Args:
        log_level: Logging level
        seed: Random seed for reproducibility
        memory_dir: Directory for memory storage
    """
    # Set logging level
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)
    
    # Set random seed
    if seed is not None:
        import random
        import numpy as np
        import torch
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        os.environ['PYTHONHASHSEED'] = str(seed)
        logger.info(f"Random seed set to {seed}")
    
    # Create memory directories
    memory_path = Path(memory_dir)
    memory_path.mkdir(parents=True, exist_ok=True)
    
    subdirs = [
        'episodic',
        'short_term',
        'working',
        'long_term',
        'vector_store',
        'backups',
    ]
    for subdir in subdirs:
        (memory_path / subdir).mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Environment setup complete. Memory directory: {memory_dir}")

# ============================================
# Convenience Functions
# ============================================

def create_memory_manager(
    memory_dir: str = './memory',
    short_term_capacity: int = 100,
    working_memory_capacity: int = 20,
    episodic_max_size: int = 10000,
    long_term_max_items: int = 100000,
    embedding_dim: int = 256,
    enable_backup: bool = True,
    **kwargs
) -> Any:
    """
    Create a memory manager with default configuration.
    
    Args:
        memory_dir: Directory for memory storage
        short_term_capacity: Short-term memory capacity
        working_memory_capacity: Working memory capacity
        episodic_max_size: Episodic memory max size
        long_term_max_items: Long-term memory max items
        embedding_dim: Embedding dimension
        enable_backup: Enable backup
        **kwargs: Additional configuration
        
    Returns:
        MemoryManager instance
    """
    if MemoryManager is None:
        raise ImportError("MemoryManager not available")
    
    config = MemoryConfig(
        memory_dir=memory_dir,
        short_term_capacity=short_term_capacity,
        working_memory_capacity=working_memory_capacity,
        episodic_max_size=episodic_max_size,
        long_term_max_items=long_term_max_items,
        embedding_dim=embedding_dim,
        enable_backup=enable_backup,
        **kwargs
    )
    
    return MemoryManager(config)

def create_vector_store(
    dimension: int = 128,
    index_type: str = 'ivfflat',
    distance_metric: str = 'cosine',
    memory_dir: str = './memory/vector_store',
    **kwargs
) -> Any:
    """
    Create a vector store with default configuration.
    
    Args:
        dimension: Vector dimension
        index_type: Index type
        distance_metric: Distance metric
        memory_dir: Memory directory
        **kwargs: Additional configuration
        
    Returns:
        VectorStore instance
    """
    if VectorStore is None:
        raise ImportError("VectorStore not available")
    
    return VectorStore(
        dimension=dimension,
        index_type=IndexType(index_type),
        distance_metric=DistanceMetric(distance_metric),
        memory_dir=memory_dir,
        **kwargs
    )

def create_memory_system(
    memory_dir: str = './memory',
    dimension: int = 128,
    **kwargs
) -> Dict[str, Any]:
    """
    Create a complete memory system with all components.
    
    Args:
        memory_dir: Directory for memory storage
        dimension: Vector dimension
        **kwargs: Additional configuration
        
    Returns:
        Dictionary of memory components
    """
    memory_system = {
        'manager': create_memory_manager(memory_dir=memory_dir, **kwargs),
        'vector_store': create_vector_store(
            dimension=dimension,
            memory_dir=f"{memory_dir}/vector_store",
            **kwargs
        ),
    }
    
    # Add individual memory systems if available
    if ShortTermMemory is not None:
        memory_system['short_term'] = ShortTermMemory(
            memory_dir=f"{memory_dir}/short_term",
            **kwargs
        )
    
    if WorkingMemory is not None:
        memory_system['working'] = WorkingMemory(
            memory_dir=f"{memory_dir}/working",
            **kwargs
        )
    
    if EpisodicMemory is not None:
        memory_system['episodic'] = EpisodicMemory(
            memory_dir=f"{memory_dir}/episodic",
            **kwargs
        )
    
    if LongTermMemory is not None:
        memory_system['long_term'] = LongTermMemory(
            memory_dir=f"{memory_dir}/long_term",
            **kwargs
        )
    
    return memory_system

# ============================================
# Module Documentation
# ============================================

MODULE_DOCSTRING = """
NEXUS AI Trading System - Memory Module
========================================

This module provides a complete memory system for the NEXUS AI Trading System,
enabling sophisticated memory management for trading agents.

Key Components:
---------------
1. Episodic Memory (episodic_memory.py)
   - Storage of trading episodes and experiences
   - Temporal sequence learning
   - Experience replay
   - Pattern recognition

2. Short-Term Memory (short_term_memory.py)
   - Active processing and storage
   - Attention mechanisms
   - Memory decay and forgetting
   - Chunking and grouping

3. Long-Term Memory (long_term_memory.py)
   - Persistent knowledge storage
   - Semantic organization
   - Knowledge graph
   - Inference and reasoning

4. Vector Store (vector_store.py)
   - High-performance vector search
   - Multiple index types
   - Similarity matching
   - Clustering and analysis

5. Memory Manager (memory_manager.py)
   - Integration of all memory systems
   - Consolidation and transfer
   - Backup and recovery
   - Statistics and monitoring

Quick Start:
------------
1. Create a memory manager:
   >>> from ai.memory import create_memory_manager
   >>> manager = create_memory_manager()

2. Store a memory:
   >>> manager.store(
   ...     content={'price': 100, 'action': 'buy'},
   ...     memory_type='episodic',
   ...     importance=0.8
   ... )

3. Retrieve from memory:
   >>> results = manager.retrieve(
   ...     query={'price': 100},
   ...     memory_type='episodic',
   ...     n=5
   ... )

4. Consolidate memory:
   >>> manager.consolidate('short_term', 'episodic')

5. Get statistics:
   >>> stats = manager.get_statistics()
   >>> print(stats)

Memory Types:
-------------
- EPISODIC: Trading experiences and episodes
- SHORT_TERM: Active information and processing
- WORKING: Current focus and attention
- LONG_TERM: Persistent knowledge and facts

Integration with AI Systems:
---------------------------
- Trading agents can store and retrieve experiences
- Reinforcement learning can use experience replay
- Pattern recognition can use episodic memories
- Decision making can use long-term knowledge
- Semantic search can use vector store
"""

# ============================================
# Module Initialization Logging
# ============================================

logger.info(f"Memory Module v{__version__} initialized")
logger.info(f"Python version: {sys.version}")

available = []
for name, available_sub in get_module_info()['available_submodules'].items():
    if available_sub:
        available.append(name)
logger.info(f"Available submodules: {', '.join(available)}")

# Check dependencies
available, missing = check_dependencies()
if not available:
    logger.warning(f"Missing dependencies: {missing}")
    logger.warning("Please install missing dependencies to use all features")
    logger.warning("Install with: pip install faiss-cpu scikit-learn numpy scipy torch")

# Log FAISS availability
try:
    import faiss
    logger.info(f"FAISS available: {faiss.__version__}")
except ImportError:
    logger.warning("FAISS not available. Vector store functionality will be limited.")
    logger.warning("Install with: pip install faiss-cpu or faiss-gpu")

# ============================================
# Module Ready
# ============================================

logger.info("Module ready for use")

# ============================================
# Export Module
# ============================================

# Only export what's available
__all__ = __all__

# ============================================
# End of Module
# ============================================
