"""
NEXUS AI TRADING SYSTEM - Distributed Learning Module
Copyright © 2026 NEXUS QUANTUM LTD

This module provides distributed learning capabilities for the NEXUS AI Trading System including:
- Federated Learning with multiple aggregation strategies
- Distributed parameter server for model coordination
- Worker nodes for local training
- Gradient aggregation and synchronization
- Model versioning and checkpointing
- Secure communication with encryption
- Compression for communication efficiency
- Fault tolerance and recovery
- Performance monitoring and metrics
- Scalable architecture for multiple workers
- Asynchronous and synchronous training modes
- Adaptive learning rate scheduling
- Resource management and load balancing

The distributed learning system enables:
- Training on distributed data without centralizing sensitive information
- Leveraging multiple compute nodes for faster training
- Privacy-preserving machine learning
- Robust model aggregation with Byzantine-robust strategies
- Cross-device federated learning
- Secure aggregation with differential privacy
- Model distillation and knowledge transfer
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple, Callable, Type, TypeVar

# ============================================
# Module Version and Metadata
# ============================================

__version__ = '3.0.0'
__author__ = 'NEXUS QUANTUM LTD'
__description__ = 'Distributed Learning Module for NEXUS AI Trading System'
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
    file_handler = logging.FileHandler(LOG_DIR / 'distributed_learning.log')
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
    'torch': '>=2.0.0',
    'numpy': '>=1.24.0',
    'redis': '>=4.5.0',
    'aiohttp': '>=3.8.0',
    'cryptography': '>=39.0.0',
    'uvloop': '>=0.17.0',
    'msgpack': '>=1.0.0',
    'blosc2': '>=2.0.0',
    'psutil': '>=5.9.0',
}

# ============================================
# Import Submodules
# ============================================

# Import from parameter_server
from .parameter_server import (
    ParameterServer,
    ParameterServerConfig,
    AggregationStrategy,
    UpdateStatus,
    WorkerStatus,
    ModelVersion,
    WorkerInfo,
    UpdateRequest,
    AggregationResult,
    TrainingMetrics,
)

# Import from sync_manager
from .sync_manager import (
    SyncManager,
    SyncManagerConfig,
    SyncMode,
    SyncStatus,
    OperationType,
    SyncOperation,
    DistributedLock,
    DistributedCounter,
    VectorClock,
    SyncMetrics,
)

# Import from worker
from .worker import (
    DistributedWorker,
    WorkerRole,
    WorkerState,
    TrainingConfig,
    TrainingMetrics as WorkerTrainingMetrics,
    ModelUpdate,
)

# Import from gradient_aggregator
try:
    from .gradient_aggregator import (
        GradientAggregator,
        AggregationMethod,
        GradientAggregationResult,
        ByzantineRobustAggregator,
    )
except ImportError:
    GradientAggregator = None
    AggregationMethod = None
    GradientAggregationResult = None
    ByzantineRobustAggregator = None
    logger.warning("gradient_aggregator module not found. Some features may be unavailable.")

# Import from federated_learning
try:
    from .federated_learning import (
        FederatedLearningCoordinator,
        FederatedLearningConfig,
        FederatedRound,
        FederatedResult,
        ClientInfo,
        ClientUpdate,
        AggregationMethod as FLAggregationMethod,
    )
except ImportError:
    FederatedLearningCoordinator = None
    FederatedLearningConfig = None
    FederatedRound = None
    FederatedResult = None
    ClientInfo = None
    ClientUpdate = None
    FLAggregationMethod = None
    logger.warning("federated_learning module not found. Some features may be unavailable.")

# Import from distributed_training
try:
    from .distributed_training import (
        DistributedTrainer,
        DistributedTrainingConfig,
        TrainingMode,
        NodeRole,
        TrainingStatus,
        NodeInfo,
        TrainingProgress,
    )
except ImportError:
    DistributedTrainer = None
    DistributedTrainingConfig = None
    TrainingMode = None
    NodeRole = None
    TrainingStatus = None
    NodeInfo = None
    TrainingProgress = None
    logger.warning("distributed_training module not found. Some features may be unavailable.")

# ============================================
# Module Exports
# ============================================

__all__ = [
    # Parameter Server
    'ParameterServer',
    'ParameterServerConfig',
    'AggregationStrategy',
    'UpdateStatus',
    'WorkerStatus',
    'ModelVersion',
    'WorkerInfo',
    'UpdateRequest',
    'AggregationResult',
    'TrainingMetrics',
    
    # Sync Manager
    'SyncManager',
    'SyncManagerConfig',
    'SyncMode',
    'SyncStatus',
    'OperationType',
    'SyncOperation',
    'DistributedLock',
    'DistributedCounter',
    'VectorClock',
    'SyncMetrics',
    
    # Worker
    'DistributedWorker',
    'WorkerRole',
    'WorkerState',
    'TrainingConfig',
    'WorkerTrainingMetrics',
    'ModelUpdate',
    
    # Gradient Aggregator
    'GradientAggregator',
    'AggregationMethod',
    'GradientAggregationResult',
    'ByzantineRobustAggregator',
    
    # Federated Learning
    'FederatedLearningCoordinator',
    'FederatedLearningConfig',
    'FederatedRound',
    'FederatedResult',
    'ClientInfo',
    'ClientUpdate',
    'FLAggregationMethod',
    
    # Distributed Training
    'DistributedTrainer',
    'DistributedTrainingConfig',
    'TrainingMode',
    'NodeRole',
    'TrainingStatus',
    'NodeInfo',
    'TrainingProgress',
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
            __import__(package_name.replace('-', '_').replace('.', '_'))
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
        'python_version': sys.version,
        'python_executable': sys.executable,
        'platform': sys.platform,
        'available_submodules': {
            'parameter_server': True,
            'sync_manager': True,
            'worker': True,
            'gradient_aggregator': GradientAggregator is not None,
            'federated_learning': FederatedLearningCoordinator is not None,
            'distributed_training': DistributedTrainer is not None,
        },
        'log_level': logging.getLevelName(logger.level),
        'log_file': str(LOG_DIR / 'distributed_learning.log'),
    }

def setup_environment(
    log_level: str = 'INFO',
    seed: Optional[int] = 42,
    use_uvloop: bool = True,
) -> None:
    """
    Set up the environment for distributed learning.
    
    Args:
        log_level: Logging level
        seed: Random seed for reproducibility
        use_uvloop: Whether to use uvloop for async operations
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
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
        os.environ['PYTHONHASHSEED'] = str(seed)
        logger.info(f"Random seed set to {seed}")
    
    # Use uvloop for async operations
    if use_uvloop:
        try:
            import uvloop
            uvloop.install()
            logger.info("uvloop installed for async operations")
        except ImportError:
            logger.warning("uvloop not available, using default event loop")
    
    # Set environment variables
    os.environ.setdefault('OMP_NUM_THREADS', str(os.cpu_count() or 4))
    os.environ.setdefault('MKL_NUM_THREADS', str(os.cpu_count() or 4))
    os.environ.setdefault('OPENBLAS_NUM_THREADS', str(os.cpu_count() or 4))
    
    # Create necessary directories
    directories = [
        'checkpoints',
        'logs',
        'data/training',
        'data/validation',
        'data/test',
        'models',
        'metrics',
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created directory: {directory}")
    
    # Check dependencies
    available, missing = check_dependencies()
    if not available:
        logger.warning(f"Missing dependencies: {missing}")
        logger.warning("Please install missing dependencies to use all features")
    else:
        logger.info("Environment setup complete")

# ============================================
# Convenience Functions
# ============================================

def create_parameter_server(
    host: str = '0.0.0.0',
    port: int = 8080,
    redis_url: str = 'redis://localhost:6379',
    model_name: str = 'nexus_trading_model',
    strategy: str = 'fed_avg',
    **kwargs
) -> ParameterServer:
    """
    Create a parameter server with the specified configuration.
    
    Args:
        host: Server host
        port: Server port
        redis_url: Redis URL for storage
        model_name: Name of the model
        strategy: Aggregation strategy
        **kwargs: Additional configuration options
    
    Returns:
        Configured ParameterServer instance
    """
    config = ParameterServerConfig(
        host=host,
        port=port,
        redis_url=redis_url,
        model_name=model_name,
        aggregation_strategy=strategy,
        **kwargs
    )
    return ParameterServer(config)

def create_worker(
    worker_id: str,
    server_url: str = 'http://localhost:8080',
    data_path: str = './data/training',
    batch_size: int = 32,
    learning_rate: float = 0.001,
    local_epochs: int = 5,
    use_gpu: bool = False,
    **kwargs
) -> DistributedWorker:
    """
    Create a distributed worker with the specified configuration.
    
    Args:
        worker_id: Unique worker identifier
        server_url: Parameter server URL
        data_path: Training data path
        batch_size: Batch size for training
        learning_rate: Learning rate
        local_epochs: Number of local epochs per round
        use_gpu: Whether to use GPU
        **kwargs: Additional configuration options
    
    Returns:
        Configured DistributedWorker instance
    """
    config = TrainingConfig(
        server_url=server_url,
        data_path=data_path,
        batch_size=batch_size,
        learning_rate=learning_rate,
        local_epochs=local_epochs,
        use_gpu=use_gpu,
        **kwargs
    )
    return DistributedWorker(worker_id, config)

def create_sync_manager(
    host: str = '0.0.0.0',
    port: int = 8081,
    redis_url: str = 'redis://localhost:6379',
    sync_mode: str = 'synchronous',
    **kwargs
) -> SyncManager:
    """
    Create a synchronization manager with the specified configuration.
    
    Args:
        host: Server host
        port: Server port
        redis_url: Redis URL for storage
        sync_mode: Synchronization mode
        **kwargs: Additional configuration options
    
    Returns:
        Configured SyncManager instance
    """
    config = SyncManagerConfig(
        host=host,
        port=port,
        redis_url=redis_url,
        sync_mode=sync_mode,
        **kwargs
    )
    return SyncManager(config)

# ============================================
# Module Documentation
# ============================================

MODULE_DOCSTRING = """
NEXUS AI Trading System - Distributed Learning Module
======================================================

This module provides a complete distributed learning framework for the NEXUS AI Trading System.

Components:
-----------
1. Parameter Server (parameter_server.py)
   - Centralized model storage and coordination
   - Multiple aggregation strategies (FedAvg, FedProx, Byzantine-robust)
   - Model versioning and checkpointing
   - Worker registration and management

2. Sync Manager (sync_manager.py)
   - Distributed synchronization primitives
   - All-reduce, broadcast, scatter, gather operations
   - Vector clocks for event ordering
   - Distributed locks and counters

3. Worker (worker.py)
   - Local training with configurable epochs
   - Model download and upload
   - Data loading and preprocessing
   - Validation and evaluation

4. Gradient Aggregator (gradient_aggregator.py)
   - Various aggregation methods
   - Byzantine-robust aggregation
   - Secure aggregation with differential privacy

5. Federated Learning (federated_learning.py)
   - End-to-end federated learning coordination
   - Client selection and management
   - Round-based training
   - Secure aggregation protocols

6. Distributed Training (distributed_training.py)
   - Scalable distributed training coordination
   - Multiple training modes (synchronous, asynchronous)
   - Resource management and load balancing
   - Fault tolerance and recovery

Quick Start:
------------
1. Start a parameter server:
   >>> from ai.distributed_learning import create_parameter_server
   >>> server = create_parameter_server()
   >>> server.run()

2. Start workers:
   >>> from ai.distributed_learning import create_worker
   >>> worker = create_worker('worker-1')
   >>> worker.start()

3. Start sync manager (optional):
   >>> from ai.distributed_learning import create_sync_manager
   >>> sync_manager = create_sync_manager()
   >>> sync_manager.run()

For more details, see the documentation for each submodule.
"""

# ============================================
# Module Initialization Logging
# ============================================

logger.info(f"Distributed Learning Module v{__version__} initialized")
logger.info(f"Python version: {sys.version}")
logger.info(f"Available submodules: {list(get_module_info()['available_submodules'].keys())}")

# ============================================
# Export Module
# ============================================

# Only export what's available
__all__ = __all__

# ============================================
# Module Ready
# ============================================

logger.info("Module ready for use")
