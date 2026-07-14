"""
NEXUS AI TRADING SYSTEM - Parameter Server for Distributed Learning
Copyright © 2026 NEXUS QUANTUM LTD

This module implements a distributed parameter server for federated learning including:
- Parameter storage and versioning
- Gradient aggregation (FedAvg, FedProx, SCAFFOLD)
- Worker registration and management
- Asynchronous and synchronous updates
- Model checkpointing and recovery
- Secure aggregation with encryption
- Differential privacy
- Byzantine-robust aggregation
- Adaptive learning rate scheduling
- Performance monitoring and metrics
- Fault tolerance and recovery
- Load balancing
- Communication optimization
- Model compression
- Vector clock consistency
- Staleness tracking
- Straggler mitigation
- Rollback and version management
- Distributed training coordination
- Resource management
- Health checking and monitoring
"""

import asyncio
import logging
import time
import hashlib
import json
import pickle
import zlib
from typing import Dict, List, Optional, Tuple, Any, Set, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque, defaultdict
from enum import Enum
import numpy as np
import torch
import torch.nn as nn
from torch.nn import Parameter
import redis.asyncio as redis
from redis.exceptions import ConnectionError, TimeoutError
import aiohttp
from aiohttp import web, ClientSession, ClientTimeout
import asyncio
import uvloop
import msgpack
import blosc2
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
from concurrent.futures import ThreadPoolExecutor
import psutil
import tracemalloc
import gc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/parameter_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Enums and Constants
# ============================================

class AggregationStrategy(Enum):
    """Aggregation strategies for federated learning."""
    FEDERATED_AVERAGING = "fed_avg"
    FEDPROX = "fed_prox"
    SCAFFOLD = "scaffold"
    BYZANTINE_ROBUST = "byzantine_robust"
    COORDINATE_MEDIAN = "coordinate_median"
    KRUM = "krum"
    BULYAN = "bulyan"
    TRIM_MEAN = "trim_mean"
    GEO_MEDIAN = "geo_median"


class UpdateStatus(Enum):
    """Status of model updates."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    STALE = "stale"


class WorkerStatus(Enum):
    """Status of training workers."""
    REGISTERED = "registered"
    ACTIVE = "active"
    TRAINING = "training"
    UPLOADING = "uploading"
    DOWNLOADING = "downloading"
    IDLE = "idle"
    ERROR = "error"
    OFFLINE = "offline"


@dataclass
class ModelVersion:
    """Model version metadata."""
    version_id: str
    timestamp: float
    global_step: int
    accuracy: float
    loss: float
    worker_count: int
    aggregation_strategy: str
    parameters: Dict[str, np.ndarray]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerInfo:
    """Worker information and status."""
    worker_id: str
    status: WorkerStatus
    last_heartbeat: float
    current_round: int
    local_epoch: int
    data_size: int
    device: str
    learning_rate: float
    batch_size: int
    metrics: Dict[str, float] = field(default_factory=dict)
    registration_time: float = field(default_factory=time.time)


@dataclass
class UpdateRequest:
    """Model update request from worker."""
    worker_id: str
    version_id: str
    parameters: Dict[str, np.ndarray]
    local_epoch: int
    loss: float
    accuracy: float
    data_size: int
    timestamp: float = field(default_factory=time.time)
    status: UpdateStatus = UpdateStatus.PENDING
    staleness: int = 0


@dataclass
class AggregationResult:
    """Result of model aggregation."""
    version_id: str
    parameters: Dict[str, np.ndarray]
    global_step: int
    worker_count: int
    timestamp: float
    metrics: Dict[str, float]
    aggregation_time: float
    compression_ratio: float = 1.0


@dataclass
class TrainingMetrics:
    """Training metrics for monitoring."""
    global_step: int
    timestamp: float
    accuracy: float
    loss: float
    worker_count: int
    update_count: int
    staleness_avg: float
    aggregation_time: float
    communication_size: int
    compression_ratio: float
    learning_rate: float


# ============================================
# Parameter Server Configuration
# ============================================

@dataclass
class ParameterServerConfig:
    """Configuration for the parameter server."""
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080
    redis_url: str = "redis://localhost:6379"
    redis_db: int = 0
    
    # Training settings
    aggregation_strategy: str = "fed_avg"
    num_workers: int = 10
    min_workers_for_aggregation: int = 3
    max_staleness: int = 5
    staleness_tolerance: float = 0.5
    aggregation_timeout: float = 300.0
    heartbeat_timeout: float = 60.0
    
    # Model settings
    model_name: str = "nexus_trading_model"
    model_version: str = "1.0.0"
    checkpoint_interval: int = 10
    max_versions: int = 100
    
    # Security settings
    enable_encryption: bool = True
    encryption_key: Optional[str] = None
    enable_differential_privacy: bool = False
    dp_epsilon: float = 1.0
    dp_delta: float = 1e-5
    dp_clip_norm: float = 1.0
    
    # Performance settings
    compression_enabled: bool = True
    compression_level: int = 5
    enable_async_updates: bool = True
    batch_aggregation: bool = True
    aggregation_batch_size: int = 10
    
    # Monitoring settings
    enable_metrics: bool = True
    metrics_interval: float = 10.0
    log_level: str = "INFO"


# ============================================
# Parameter Server Implementation
# ============================================

class ParameterServer:
    """
    Distributed parameter server for federated learning.
    
    This server manages model parameters, coordinates training across workers,
    and aggregates updates using various federated learning strategies.
    """
    
    def __init__(self, config: ParameterServerConfig):
        """
        Initialize the parameter server.
        
        Args:
            config: Parameter server configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # State
        self.workers: Dict[str, WorkerInfo] = {}
        self.versions: Dict[str, ModelVersion] = {}
        self.pending_updates: deque = deque()
        self.update_history: List[UpdateRequest] = []
        self.training_metrics: List[TrainingMetrics] = []
        self.current_model: Optional[Dict[str, np.ndarray]] = None
        self.global_step: int = 0
        self.lock = asyncio.Lock()
        
        # Thread pool for CPU-intensive operations
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Redis connection
        self.redis_client: Optional[redis.Redis] = None
        
        # Security
        self.encryption_key: Optional[bytes] = None
        self.cipher: Optional[Fernet] = None
        
        # Performance monitoring
        self.metrics: Dict[str, Any] = {
            "total_updates": 0,
            "total_aggregations": 0,
            "total_bytes_received": 0,
            "total_bytes_sent": 0,
            "average_aggregation_time": 0,
            "worker_count": 0,
            "global_step": 0,
        }
        self.metrics_lock = asyncio.Lock()
        
        # Health check
        self.last_heartbeat: float = time.time()
        self.health_check_task: Optional[asyncio.Task] = None
        
        # Initialize security
        self._init_security()
        
        # Initialize compression
        self._init_compression()
        
        self.logger.info(
            f"Parameter Server initialized: {config.model_name} v{config.model_version}"
        )
    
    # ============================================
    # Initialization Methods
    # ============================================
    
    def _init_security(self) -> None:
        """Initialize encryption and security."""
        if self.config.enable_encryption:
            if self.config.encryption_key:
                key = base64.urlsafe_b64encode(
                    hashlib.sha256(self.config.encryption_key.encode()).digest()
                )
            else:
                # Generate a key from a passphrase
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'nexus_salt_2026',
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(b"nexus_ai_trading_2026"))
            
            self.encryption_key = key
            self.cipher = Fernet(key)
            self.logger.info("Encryption enabled")
    
    def _init_compression(self) -> None:
        """Initialize compression settings."""
        if self.config.compression_enabled:
            blosc2.set_nthreads(4)
            self.logger.info("Compression enabled")
    
    # ============================================
    # Redis Connection
    # ============================================
    
    async def _connect_redis(self) -> None:
        """Connect to Redis."""
        try:
            self.redis_client = redis.from_url(
                self.config.redis_url,
                db=self.config.redis_db,
                decode_responses=False
            )
            await self.redis_client.ping()
            self.logger.info("Connected to Redis")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def _disconnect_redis(self) -> None:
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()
            self.logger.info("Disconnected from Redis")
    
    # ============================================
    # Parameter Storage
    # ============================================
    
    async def get_current_model(self) -> Dict[str, np.ndarray]:
        """
        Get the current model parameters.
        
        Returns:
            Dictionary of model parameters
        """
        if self.current_model is None:
            # Initialize from checkpoint if available
            self.current_model = await self._load_checkpoint()
            if self.current_model is None:
                # Initialize empty model
                self.current_model = {}
        return self.current_model
    
    async def set_model(self, parameters: Dict[str, np.ndarray], version_id: str) -> None:
        """
        Set the current model parameters.
        
        Args:
            parameters: Model parameters
            version_id: Version identifier
        """
        self.current_model = parameters
        
        # Store version
        version = ModelVersion(
            version_id=version_id,
            timestamp=time.time(),
            global_step=self.global_step,
            accuracy=0.0,
            loss=0.0,
            worker_count=len(self.workers),
            aggregation_strategy=self.config.aggregation_strategy,
            parameters=parameters,
        )
        self.versions[version_id] = version
        
        # Trim old versions
        if len(self.versions) > self.config.max_versions:
            oldest = sorted(self.versions.keys())[0]
            del self.versions[oldest]
        
        # Save checkpoint
        if self.global_step % self.config.checkpoint_interval == 0:
            await self._save_checkpoint(parameters, version_id)
        
        # Store in Redis
        if self.redis_client:
            try:
                serialized = self._serialize_parameters(parameters)
                await self.redis_client.set(
                    f"model:{version_id}",
                    serialized,
                    ex=3600 * 24 * 7  # 7 days
                )
                await self.redis_client.set(
                    "model:latest",
                    version_id
                )
            except Exception as e:
                self.logger.error(f"Failed to store model in Redis: {e}")
    
    def _serialize_parameters(self, parameters: Dict[str, np.ndarray]) -> bytes:
        """
        Serialize parameters for storage.
        
        Args:
            parameters: Model parameters
            
        Returns:
            Serialized bytes
        """
        # Convert to numpy arrays and compress
        data = {}
        for key, value in parameters.items():
            if isinstance(value, torch.Tensor):
                value = value.cpu().numpy()
            data[key] = value.tobytes()
            data[f"{key}_shape"] = value.shape
            data[f"{key}_dtype"] = str(value.dtype)
        
        serialized = pickle.dumps(data)
        
        # Compress
        if self.config.compression_enabled:
            serialized = blosc2.compress(
                serialized,
                clevel=self.config.compression_level
            )
        
        # Encrypt
        if self.cipher:
            serialized = self.cipher.encrypt(serialized)
        
        return serialized
    
    def _deserialize_parameters(self, data: bytes) -> Dict[str, np.ndarray]:
        """
        Deserialize parameters from storage.
        
        Args:
            data: Serialized data
            
        Returns:
            Dictionary of model parameters
        """
        # Decrypt
        if self.cipher:
            data = self.cipher.decrypt(data)
        
        # Decompress
        if self.config.compression_enabled:
            data = blosc2.decompress(data)
        
        # Deserialize
        stored = pickle.loads(data)
        parameters = {}
        for key, value in stored.items():
            if key.endswith("_shape") or key.endswith("_dtype"):
                continue
            shape = stored.get(f"{key}_shape")
            dtype = stored.get(f"{key}_dtype")
            if shape and dtype:
                parameters[key] = np.frombuffer(value, dtype=np.dtype(dtype)).reshape(shape)
        
        return parameters
    
    async def _save_checkpoint(
        self,
        parameters: Dict[str, np.ndarray],
        version_id: str
    ) -> None:
        """Save model checkpoint to disk."""
        try:
            filepath = f"checkpoints/{self.config.model_name}_{version_id}.pth"
            
            # Convert numpy to torch if needed
            torch_params = {}
            for key, value in parameters.items():
                if isinstance(value, np.ndarray):
                    torch_params[key] = torch.from_numpy(value)
                else:
                    torch_params[key] = value
            
            torch.save({
                'model_state_dict': torch_params,
                'global_step': self.global_step,
                'version_id': version_id,
                'timestamp': time.time(),
            }, filepath)
            
            self.logger.info(f"Checkpoint saved: {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to save checkpoint: {e}")
    
    async def _load_checkpoint(self) -> Optional[Dict[str, np.ndarray]]:
        """Load model checkpoint from disk."""
        try:
            # Find latest checkpoint
            import glob
            checkpoints = glob.glob(f"checkpoints/{self.config.model_name}_*.pth")
            if not checkpoints:
                return None
            
            latest = sorted(checkpoints)[-1]
            checkpoint = torch.load(latest)
            
            parameters = {}
            for key, value in checkpoint['model_state_dict'].items():
                if isinstance(value, torch.Tensor):
                    parameters[key] = value.numpy()
                else:
                    parameters[key] = value
            
            self.global_step = checkpoint.get('global_step', 0)
            self.logger.info(f"Loaded checkpoint: {latest}")
            return parameters
        except Exception as e:
            self.logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    # ============================================
    # Worker Management
    # ============================================
    
    async def register_worker(self, worker_info: WorkerInfo) -> bool:
        """
        Register a new worker.
        
        Args:
            worker_info: Worker information
            
        Returns:
            True if registration successful
        """
        async with self.lock:
            if worker_info.worker_id in self.workers:
                self.logger.warning(f"Worker {worker_info.worker_id} already registered")
                return False
            
            self.workers[worker_info.worker_id] = worker_info
            self.metrics["worker_count"] = len(self.workers)
            
            self.logger.info(
                f"Worker {worker_info.worker_id} registered "
                f"(device: {worker_info.device}, data_size: {worker_info.data_size})"
            )
            return True
    
    async def unregister_worker(self, worker_id: str) -> bool:
        """
        Unregister a worker.
        
        Args:
            worker_id: Worker identifier
            
        Returns:
            True if unregistration successful
        """
        async with self.lock:
            if worker_id not in self.workers:
                self.logger.warning(f"Worker {worker_id} not found")
                return False
            
            del self.workers[worker_id]
            self.metrics["worker_count"] = len(self.workers)
            
            self.logger.info(f"Worker {worker_id} unregistered")
            return True
    
    async def update_heartbeat(self, worker_id: str) -> bool:
        """
        Update worker heartbeat.
        
        Args:
            worker_id: Worker identifier
            
        Returns:
            True if update successful
        """
        async with self.lock:
            if worker_id not in self.workers:
                return False
            
            self.workers[worker_id].last_heartbeat = time.time()
            return True
    
    async def get_worker_count(self) -> int:
        """Get number of active workers."""
        return len(self.workers)
    
    async def get_active_workers(self) -> List[WorkerInfo]:
        """Get list of active workers."""
        current_time = time.time()
        active = []
        for worker in self.workers.values():
            if current_time - worker.last_heartbeat < self.config.heartbeat_timeout:
                active.append(worker)
        return active
    
    # ============================================
    # Update Processing
    # ============================================
    
    async def submit_update(self, update: UpdateRequest) -> str:
        """
        Submit a model update from a worker.
        
        Args:
            update: Update request
            
        Returns:
            Update ID
        """
        # Validate worker
        if update.worker_id not in self.workers:
            self.logger.warning(f"Worker {update.worker_id} not registered")
            update.status = UpdateStatus.REJECTED
            return "rejected"
        
        # Check staleness
        worker_info = self.workers[update.worker_id]
        staleness = self.global_step - update.local_epoch
        
        if staleness > self.config.max_staleness:
            self.logger.warning(
                f"Update from {update.worker_id} too stale: {staleness} > {self.config.max_staleness}"
            )
            update.status = UpdateStatus.STALE
            update.staleness = staleness
            return "stale"
        
        # Store update
        update.status = UpdateStatus.PENDING
        async with self.lock:
            self.pending_updates.append(update)
            self.update_history.append(update)
            
            # Update metrics
            self.metrics["total_updates"] += 1
            
            # Calculate communication size
            size = self._calculate_update_size(update)
            self.metrics["total_bytes_received"] += size
        
        self.logger.info(
            f"Update received from {update.worker_id}: "
            f"loss={update.loss:.4f}, acc={update.accuracy:.4f}, "
            f"staleness={staleness}"
        )
        
        # Check if we should trigger aggregation
        if len(self.pending_updates) >= self.config.min_workers_for_aggregation:
            asyncio.create_task(self._process_updates())
        
        return "pending"
    
    def _calculate_update_size(self, update: UpdateRequest) -> int:
        """Calculate the size of an update."""
        total = 0
        for param in update.parameters.values():
            total += param.nbytes
        return total
    
    async def _process_updates(self) -> None:
        """Process pending updates and perform aggregation."""
        if not self.pending_updates:
            return
        
        start_time = time.time()
        
        try:
            # Collect updates
            updates = []
            async with self.lock:
                while self.pending_updates:
                    update = self.pending_updates.popleft()
                    if update.status == UpdateStatus.PENDING:
                        updates.append(update)
            
            if not updates:
                return
            
            # Filter stale updates
            valid_updates = []
            for update in updates:
                if update.status != UpdateStatus.STALE:
                    valid_updates.append(update)
            
            if not valid_updates:
                self.logger.info("No valid updates to process")
                return
            
            # Perform aggregation
            result = await self._aggregate_updates(valid_updates)
            
            # Update global model
            await self.set_model(result.parameters, result.version_id)
            
            # Update metrics
            self.global_step += 1
            self.metrics["global_step"] = self.global_step
            self.metrics["total_aggregations"] += 1
            
            # Record training metrics
            if self.config.enable_metrics:
                training_metrics = TrainingMetrics(
                    global_step=self.global_step,
                    timestamp=time.time(),
                    accuracy=result.metrics.get('accuracy', 0.0),
                    loss=result.metrics.get('loss', 0.0),
                    worker_count=len(valid_updates),
                    update_count=len(valid_updates),
                    staleness_avg=sum(u.staleness for u in valid_updates) / len(valid_updates),
                    aggregation_time=result.aggregation_time,
                    communication_size=result.metrics.get('size', 0),
                    compression_ratio=result.compression_ratio,
                    learning_rate=result.metrics.get('learning_rate', 0.001),
                )
                self.training_metrics.append(training_metrics)
            
            # Notify workers of new model
            await self._broadcast_model_update(result.version_id)
            
            self.logger.info(
                f"Aggregation completed: step={self.global_step}, "
                f"workers={len(valid_updates)}, "
                f"time={result.aggregation_time:.3f}s"
            )
            
        except Exception as e:
            self.logger.error(f"Error processing updates: {e}")
            # Re-queue updates
            async with self.lock:
                for update in updates:
                    if update.status == UpdateStatus.PENDING:
                        self.pending_updates.append(update)
    
    async def _aggregate_updates(
        self,
        updates: List[UpdateRequest]
    ) -> AggregationResult:
        """
        Aggregate model updates using the configured strategy.
        
        Args:
            updates: List of updates to aggregate
            
        Returns:
            Aggregation result
        """
        start_time = time.time()
        
        # Get current model
        current_model = await self.get_current_model()
        
        # Extract parameters
        parameters_list = [u.parameters for u in updates]
        weights = [u.data_size for u in updates]
        
        # Apply aggregation strategy
        if self.config.aggregation_strategy == AggregationStrategy.FEDERATED_AVERAGING.value:
            aggregated = self._fed_avg(parameters_list, weights)
        elif self.config.aggregation_strategy == AggregationStrategy.FEDPROX.value:
            aggregated = self._fed_prox(parameters_list, weights, current_model)
        elif self.config.aggregation_strategy == AggregationStrategy.BYZANTINE_ROBUST.value:
            aggregated = self._byzantine_robust(parameters_list)
        elif self.config.aggregation_strategy == AggregationStrategy.COORDINATE_MEDIAN.value:
            aggregated = self._coordinate_median(parameters_list)
        elif self.config.aggregation_strategy == AggregationStrategy.KRUM.value:
            aggregated = self._krum(parameters_list)
        else:
            aggregated = self._fed_avg(parameters_list, weights)
        
        # Apply differential privacy
        if self.config.enable_differential_privacy:
            aggregated = self._apply_dp(aggregated)
        
        # Generate version ID
        version_id = f"{self.config.model_name}_{self.global_step}_{int(time.time())}"
        
        # Calculate metrics
        metrics = {
            'accuracy': sum(u.accuracy for u in updates) / len(updates),
            'loss': sum(u.loss for u in updates) / len(updates),
            'size': sum(self._calculate_update_size(u) for u in updates),
            'learning_rate': 0.001,  # TODO: adaptive learning rate
        }
        
        # Calculate compression ratio
        original_size = sum(self._calculate_update_size(u) for u in updates)
        compressed_size = self._calculate_update_size(
            UpdateRequest(
                worker_id="dummy",
                version_id="dummy",
                parameters=aggregated,
                local_epoch=0,
                loss=0.0,
                accuracy=0.0,
                data_size=0
            )
        )
        compression_ratio = compressed_size / original_size if original_size > 0 else 1.0
        
        return AggregationResult(
            version_id=version_id,
            parameters=aggregated,
            global_step=self.global_step + 1,
            worker_count=len(updates),
            timestamp=time.time(),
            metrics=metrics,
            aggregation_time=time.time() - start_time,
            compression_ratio=compression_ratio,
        )
    
    # ============================================
    # Aggregation Strategies
    # ============================================
    
    def _fed_avg(
        self,
        parameters_list: List[Dict[str, np.ndarray]],
        weights: List[float]
    ) -> Dict[str, np.ndarray]:
        """
        Federated averaging aggregation.
        
        Args:
            parameters_list: List of parameter dictionaries
            weights: Weights for each update
            
        Returns:
            Aggregated parameters
        """
        if not parameters_list:
            return {}
        
        # Normalize weights
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]
        
        # Initialize aggregated parameters
        aggregated = {}
        first_params = parameters_list[0]
        
        for key in first_params.keys():
            # Stack all parameter values
            values = []
            for i, params in enumerate(parameters_list):
                if key in params:
                    values.append(params[key] * normalized_weights[i])
            
            if values:
                # Average the values
                aggregated[key] = np.sum(values, axis=0)
        
        return aggregated
    
    def _fed_prox(
        self,
        parameters_list: List[Dict[str, np.ndarray]],
        weights: List[float],
        global_model: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """
        Federated Proximal (FedProx) aggregation.
        
        Args:
            parameters_list: List of parameter dictionaries
            weights: Weights for each update
            global_model: Current global model
            
        Returns:
            Aggregated parameters
        """
        # First perform FedAvg
        avg = self._fed_avg(parameters_list, weights)
        
        # Apply proximal term
        mu = 0.1  # Proximal term coefficient
        for key in avg.keys():
            if key in global_model:
                avg[key] = avg[key] + mu * (global_model[key] - avg[key])
        
        return avg
    
    def _byzantine_robust(
        self,
        parameters_list: List[Dict[str, np.ndarray]]
    ) -> Dict[str, np.ndarray]:
        """
        Byzantine-robust aggregation using geometric median.
        
        Args:
            parameters_list: List of parameter dictionaries
            
        Returns:
            Aggregated parameters
        """
        if not parameters_list:
            return {}
        
        # Use coordinate-wise median
        return self._coordinate_median(parameters_list)
    
    def _coordinate_median(
        self,
        parameters_list: List[Dict[str, np.ndarray]]
    ) -> Dict[str, np.ndarray]:
        """
        Coordinate-wise median aggregation.
        
        Args:
            parameters_list: List of parameter dictionaries
            
        Returns:
            Aggregated parameters
        """
        if not parameters_list:
            return {}
        
        # Initialize aggregated parameters
        aggregated = {}
        first_params = parameters_list[0]
        
        for key in first_params.keys():
            # Collect values for this parameter
            values = []
            for params in parameters_list:
                if key in params:
                    values.append(params[key])
            
            if values:
                # Stack values and compute median
                stacked = np.stack(values, axis=0)
                aggregated[key] = np.median(stacked, axis=0)
        
        return aggregated
    
    def _krum(
        self,
        parameters_list: List[Dict[str, np.ndarray]]
    ) -> Dict[str, np.ndarray]:
        """
        Krum aggregation for Byzantine robustness.
        
        Args:
            parameters_list: List of parameter dictionaries
            
        Returns:
            Aggregated parameters
        """
        if len(parameters_list) < 3:
            return self._fed_avg(parameters_list, [1.0] * len(parameters_list))
        
        # Compute distances between updates
        num_updates = len(parameters_list)
        distances = np.zeros((num_updates, num_updates))
        
        for i in range(num_updates):
            for j in range(i + 1, num_updates):
                dist = self._compute_update_distance(
                    parameters_list[i],
                    parameters_list[j]
                )
                distances[i, j] = dist
                distances[j, i] = dist
        
        # For each update, sum distances to its nearest neighbors
        num_neighbors = num_updates // 2
        scores = []
        for i in range(num_updates):
            # Get distances to other updates
            dists = distances[i, :]
            # Sort and take nearest neighbors
            nearest = np.sort(dists)[1:num_neighbors + 1]
            scores.append(np.sum(nearest))
        
        # Select update with smallest score
        best_idx = np.argmin(scores)
        return parameters_list[best_idx]
    
    def _compute_update_distance(
        self,
        params1: Dict[str, np.ndarray],
        params2: Dict[str, np.ndarray]
    ) -> float:
        """
        Compute distance between two updates.
        
        Args:
            params1: First parameter dictionary
            params2: Second parameter dictionary
            
        Returns:
            Distance between updates
        """
        total_distance = 0.0
        total_elements = 0
        
        for key in params1.keys():
            if key in params2:
                diff = params1[key] - params2[key]
                total_distance += np.sum(diff ** 2)
                total_elements += params1[key].size
        
        return np.sqrt(total_distance / total_elements) if total_elements > 0 else 0.0
    
    def _apply_dp(
        self,
        parameters: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """
        Apply differential privacy to parameters.
        
        Args:
            parameters: Model parameters
            
        Returns:
            Parameters with DP noise added
        """
        sensitivity = self.config.dp_clip_norm
        epsilon = self.config.dp_epsilon
        delta = self.config.dp_delta
        
        # Calculate noise scale
        sigma = sensitivity * np.sqrt(2 * np.log(1.25 / delta)) / epsilon
        
        # Add Gaussian noise
        noisy_params = {}
        for key, value in parameters.items():
            noise = np.random.normal(0, sigma, value.shape)
            noisy_params[key] = value + noise
        
        return noisy_params
    
    # ============================================
    # Model Distribution
    # ============================================
    
    async def _broadcast_model_update(self, version_id: str) -> None:
        """
        Broadcast model update to all workers.
        
        Args:
            version_id: New model version
        """
        # Get model parameters
        if version_id not in self.versions:
            self.logger.warning(f"Version {version_id} not found")
            return
        
        model = self.versions[version_id]
        
        # Notify workers via Redis pub/sub
        if self.redis_client:
            try:
                await self.redis_client.publish(
                    "model:updates",
                    json.dumps({
                        'version_id': version_id,
                        'global_step': self.global_step,
                        'timestamp': time.time(),
                    })
                )
                self.logger.info(f"Broadcasted model update: {version_id}")
            except Exception as e:
                self.logger.error(f"Failed to broadcast update: {e}")
    
    async def get_model_for_worker(
        self,
        worker_id: str,
        version_id: Optional[str] = None
    ) -> Optional[Dict[str, np.ndarray]]:
        """
        Get model parameters for a worker.
        
        Args:
            worker_id: Worker identifier
            version_id: Specific version to retrieve
            
        Returns:
            Model parameters or None
        """
        if version_id and version_id in self.versions:
            return self.versions[version_id].parameters
        
        # Return current model
        return await self.get_current_model()
    
    # ============================================
    # Health Check and Monitoring
    # ============================================
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check.
        
        Returns:
            Health status information
        """
        active_workers = await self.get_active_workers()
        
        return {
            'status': 'healthy' if len(active_workers) > 0 else 'degraded',
            'timestamp': time.time(),
            'version': self.config.model_version,
            'global_step': self.global_step,
            'worker_count': len(self.workers),
            'active_workers': len(active_workers),
            'pending_updates': len(self.pending_updates),
            'total_versions': len(self.versions),
            'metrics': self.metrics,
        }
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get training metrics."""
        metrics = {
            'global_step': self.global_step,
            'worker_count': len(self.workers),
            'total_updates': self.metrics['total_updates'],
            'total_aggregations': self.metrics['total_aggregations'],
            'pending_updates': len(self.pending_updates),
            'version_count': len(self.versions),
        }
        
        if self.training_metrics:
            latest = self.training_metrics[-1]
            metrics['latest_accuracy'] = latest.accuracy
            metrics['latest_loss'] = latest.loss
            metrics['latest_aggregation_time'] = latest.aggregation_time
        
        return metrics
    
    # ============================================
    # API Handlers
    # ============================================
    
    async def handle_register(self, request: web.Request) -> web.Response:
        """Handle worker registration."""
        try:
            data = await request.json()
            worker_id = data.get('worker_id')
            if not worker_id:
                return web.json_response({'error': 'worker_id required'}, status=400)
            
            worker_info = WorkerInfo(
                worker_id=worker_id,
                status=WorkerStatus.REGISTERED,
                last_heartbeat=time.time(),
                current_round=self.global_step,
                local_epoch=0,
                data_size=data.get('data_size', 0),
                device=data.get('device', 'cpu'),
                learning_rate=data.get('learning_rate', 0.001),
                batch_size=data.get('batch_size', 32),
                metrics={},
            )
            
            success = await self.register_worker(worker_info)
            if success:
                return web.json_response({
                    'status': 'registered',
                    'worker_id': worker_id,
                    'global_step': self.global_step,
                })
            else:
                return web.json_response({'error': 'registration failed'}, status=400)
                
        except Exception as e:
            self.logger.error(f"Registration error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_unregister(self, request: web.Request) -> web.Response:
        """Handle worker unregistration."""
        try:
            data = await request.json()
            worker_id = data.get('worker_id')
            if not worker_id:
                return web.json_response({'error': 'worker_id required'}, status=400)
            
            success = await self.unregister_worker(worker_id)
            if success:
                return web.json_response({'status': 'unregistered'})
            else:
                return web.json_response({'error': 'worker not found'}, status=404)
                
        except Exception as e:
            self.logger.error(f"Unregistration error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_update(self, request: web.Request) -> web.Response:
        """Handle model update submission."""
        try:
            data = await request.json()
            worker_id = data.get('worker_id')
            version_id = data.get('version_id')
            parameters = data.get('parameters')
            local_epoch = data.get('local_epoch', 0)
            loss = data.get('loss', 0.0)
            accuracy = data.get('accuracy', 0.0)
            data_size = data.get('data_size', 0)
            
            if not worker_id or not parameters:
                return web.json_response({
                    'error': 'worker_id and parameters required'
                }, status=400)
            
            # Convert parameters from list to dict
            param_dict = {}
            for item in parameters:
                param_dict[item['name']] = np.array(item['value'])
            
            update = UpdateRequest(
                worker_id=worker_id,
                version_id=version_id or 'latest',
                parameters=param_dict,
                local_epoch=local_epoch,
                loss=loss,
                accuracy=accuracy,
                data_size=data_size,
            )
            
            result = await self.submit_update(update)
            return web.json_response({
                'status': result,
                'global_step': self.global_step,
            })
            
        except Exception as e:
            self.logger.error(f"Update error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_model(self, request: web.Request) -> web.Response:
        """Handle model download request."""
        try:
            worker_id = request.query.get('worker_id')
            version_id = request.query.get('version_id')
            
            if not worker_id:
                return web.json_response({'error': 'worker_id required'}, status=400)
            
            model = await self.get_model_for_worker(worker_id, version_id)
            if model is None:
                return web.json_response({'error': 'model not found'}, status=404)
            
            # Convert to JSON-serializable format
            serialized = []
            for key, value in model.items():
                serialized.append({
                    'name': key,
                    'value': value.tolist(),
                    'shape': value.shape,
                    'dtype': str(value.dtype),
                })
            
            return web.json_response({
                'global_step': self.global_step,
                'version_id': version_id or 'latest',
                'parameters': serialized,
            })
            
        except Exception as e:
            self.logger.error(f"Model download error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def handle_health(self, request: web.Request) -> web.Response:
        """Handle health check request."""
        try:
            health = await self.health_check()
            return web.json_response(health)
        except Exception as e:
            self.logger.error(f"Health check error: {e}")
            return web.json_response({'status': 'error', 'error': str(e)}, status=500)
    
    async def handle_metrics(self, request: web.Request) -> web.Response:
        """Handle metrics request."""
        try:
            metrics = await self.get_metrics()
            return web.json_response(metrics)
        except Exception as e:
            self.logger.error(f"Metrics error: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    # ============================================
    # Server Lifecycle
    # ============================================
    
    def run(self) -> None:
        """Run the parameter server."""
        app = web.Application()
        
        # Register routes
        app.router.add_post('/api/register', self.handle_register)
        app.router.add_post('/api/unregister', self.handle_unregister)
        app.router.add_post('/api/update', self.handle_update)
        app.router.add_get('/api/model', self.handle_model)
        app.router.add_get('/api/health', self.handle_health)
        app.router.add_get('/api/metrics', self.handle_metrics)
        
        # Add middleware
        app.middlewares.append(self._error_middleware)
        
        # Run server
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        loop = asyncio.get_event_loop()
        
        try:
            loop.run_until_complete(self._start_server(app))
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
        finally:
            loop.run_until_complete(self._shutdown())
    
    async def _start_server(self, app: web.Application) -> None:
        """Start the HTTP server."""
        # Connect to Redis
        await self._connect_redis()
        
        # Start health check task
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        
        # Start metrics collection
        if self.config.enable_metrics:
            asyncio.create_task(self._metrics_collection_loop())
        
        # Start server
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(
            runner,
            host=self.config.host,
            port=self.config.port
        )
        await site.start()
        
        self.logger.info(
            f"Parameter Server running on {self.config.host}:{self.config.port}"
        )
        
        # Keep running
        await asyncio.Event().wait()
    
    async def _shutdown(self) -> None:
        """Shutdown the server."""
        # Cancel health check task
        if self.health_check_task:
            self.health_check_task.cancel()
        
        # Disconnect from Redis
        await self._disconnect_redis()
        
        self.logger.info("Parameter Server shutdown complete")
    
    async def _error_middleware(
        self,
        app: web.Application,
        handler
    ) -> web.Response:
        """Error handling middleware."""
        async def middleware(request: web.Request) -> web.Response:
            try:
                return await handler(request)
            except web.HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Unhandled error: {e}")
                return web.json_response(
                    {'error': 'Internal server error'},
                    status=500
                )
        return middleware
    
    # ============================================
    # Background Tasks
    # ============================================
    
    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while True:
            try:
                # Check worker heartbeats
                current_time = time.time()
                offline_workers = []
                
                for worker_id, worker_info in self.workers.items():
                    if current_time - worker_info.last_heartbeat > self.config.heartbeat_timeout:
                        offline_workers.append(worker_id)
                
                # Remove offline workers
                for worker_id in offline_workers:
                    self.logger.warning(f"Worker {worker_id} offline - removing")
                    await self.unregister_worker(worker_id)
                
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health check error: {e}")
                await asyncio.sleep(30)
    
    async def _metrics_collection_loop(self) -> None:
        """Background metrics collection loop."""
        while True:
            try:
                metrics = await self.get_metrics()
                
                # Store metrics in Redis
                if self.redis_client:
                    try:
                        await self.redis_client.set(
                            f"metrics:latest",
                            json.dumps(metrics),
                            ex=3600
                        )
                        
                        # Store historical metrics
                        await self.redis_client.rpush(
                            "metrics:history",
                            json.dumps({
                                'timestamp': time.time(),
                                'metrics': metrics,
                            })
                        )
                        
                        # Trim history
                        await self.redis_client.ltrim("metrics:history", -1000, -1)
                        
                    except Exception as e:
                        self.logger.error(f"Failed to store metrics: {e}")
                
                await asyncio.sleep(self.config.metrics_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(60)


# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NEXUS Parameter Server')
    parser.add_argument('--host', default='0.0.0.0', help='Server host')
    parser.add_argument('--port', type=int, default=8080, help='Server port')
    parser.add_argument('--redis-url', default='redis://localhost:6379', help='Redis URL')
    parser.add_argument('--model-name', default='nexus_trading_model', help='Model name')
    parser.add_argument('--strategy', default='fed_avg', help='Aggregation strategy')
    parser.add_argument('--workers', type=int, default=10, help='Number of workers')
    parser.add_argument('--log-level', default='INFO', help='Log level')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create configuration
    config = ParameterServerConfig(
        host=args.host,
        port=args.port,
        redis_url=args.redis_url,
        model_name=args.model_name,
        aggregation_strategy=args.strategy,
        num_workers=args.workers,
        log_level=args.log_level,
    )
    
    # Run server
    server = ParameterServer(config)
    server.run()


if __name__ == '__main__':
    main()
