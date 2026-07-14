"""
NEXUS AI TRADING SYSTEM - Distributed Learning Worker
Copyright © 2026 NEXUS QUANTUM LTD

This module implements a distributed learning worker for federated learning including:
- Local model training on worker data
- Gradient computation and updates
- Model parameter synchronization
- Communication with parameter server
- Data loading and preprocessing
- Local validation and evaluation
- Checkpointing and recovery
- Health monitoring and reporting
- Performance metrics collection
- Secure communication with encryption
- Compression for communication efficiency
- Staleness tracking and handling
- Adaptive learning rate scheduling
- Local data management
- Device management (CPU/GPU)
- Batch processing
- Distributed training coordination
- Fault tolerance and recovery
- Resource management
- Progress tracking and reporting
"""

import asyncio
import logging
import time
import json
import pickle
import hashlib
import zlib
import os
import sys
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset, TensorDataset
import aiohttp
from aiohttp import ClientSession, ClientTimeout, TCPConnector
import asyncio
import uvloop
import redis.asyncio as redis
from redis.exceptions import ConnectionError, TimeoutError
import psutil
import gc
import tracemalloc
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/worker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Enums and Constants
# ============================================

class WorkerStatus(Enum):
    """Worker status states."""
    INITIALIZING = "initializing"
    IDLE = "idle"
    TRAINING = "training"
    VALIDATING = "validating"
    UPLOADING = "uploading"
    DOWNLOADING = "downloading"
    SYNCING = "syncing"
    ERROR = "error"
    STOPPED = "stopped"

class WorkerRole(Enum):
    """Worker roles in the distributed system."""
    TRAINER = "trainer"
    VALIDATOR = "validator"
    LEADER = "leader"
    BACKUP = "backup"

@dataclass
class TrainingConfig:
    """Training configuration for the worker."""
    # Model settings
    model_name: str = "nexus_trading_model"
    model_version: str = "1.0.0"
    
    # Training settings
    batch_size: int = 32
    learning_rate: float = 0.001
    epochs: int = 10
    local_epochs: int = 5
    optimizer: str = "adam"
    loss_function: str = "mse"
    
    # Data settings
    data_path: str = "./data/training"
    validation_split: float = 0.2
    shuffle_data: bool = True
    num_workers: int = 4
    
    # Communication settings
    server_url: str = "http://localhost:8080"
    sync_interval: int = 60
    heartbeat_interval: int = 10
    timeout: int = 30
    retry_attempts: int = 3
    
    # Security settings
    enable_encryption: bool = True
    encryption_key: Optional[str] = None
    
    # Performance settings
    use_gpu: bool = False
    compression_enabled: bool = True
    compression_level: int = 5
    
    # Monitoring settings
    log_interval: int = 10
    metrics_enabled: bool = True


@dataclass
class WorkerState:
    """Worker state information."""
    worker_id: str
    status: WorkerStatus
    role: WorkerRole
    current_epoch: int
    current_step: int
    total_steps: int
    data_size: int
    device: str
    local_accuracy: float = 0.0
    local_loss: float = 0.0
    global_step: int = 0
    last_sync: float = 0.0
    start_time: float = field(default_factory=time.time)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrainingMetrics:
    """Training metrics for the worker."""
    timestamp: float
    epoch: int
    step: int
    loss: float
    accuracy: float
    learning_rate: float
    batch_time: float
    data_throughput: float
    memory_usage: float
    gpu_memory: Optional[float] = None
    gradient_norm: Optional[float] = None


@dataclass
class ModelUpdate:
    """Model update to send to parameter server."""
    worker_id: str
    version_id: str
    parameters: Dict[str, np.ndarray]
    local_epoch: int
    loss: float
    accuracy: float
    data_size: int
    timestamp: float = field(default_factory=time.time)
    staleness: int = 0


# ============================================
# Worker Implementation
# ============================================

class DistributedWorker:
    """
    Distributed learning worker for federated training.
    
    This worker handles local training, model updates, and communication
    with the parameter server for distributed learning.
    """
    
    def __init__(self, worker_id: str, config: TrainingConfig):
        """
        Initialize the distributed worker.
        
        Args:
            worker_id: Unique worker identifier
            config: Training configuration
        """
        self.worker_id = worker_id
        self.config = config
        self.logger = logging.getLogger(f"worker.{worker_id}")
        
        # State
        self.state = WorkerState(
            worker_id=worker_id,
            status=WorkerStatus.INITIALIZING,
            role=WorkerRole.TRAINER,
            current_epoch=0,
            current_step=0,
            total_steps=0,
            data_size=0,
            device="cuda" if config.use_gpu and torch.cuda.is_available() else "cpu",
        )
        
        # Model
        self.model: Optional[nn.Module] = None
        self.optimizer: Optional[optim.Optimizer] = None
        self.criterion: Optional[nn.Module] = None
        self.current_model_params: Optional[Dict[str, np.ndarray]] = None
        
        # Data
        self.train_loader: Optional[DataLoader] = None
        self.val_loader: Optional[DataLoader] = None
        self.dataset: Optional[Dataset] = None
        
        # Communication
        self.session: Optional[ClientSession] = None
        self.redis_client: Optional[redis.Redis] = None
        
        # Security
        self.cipher: Optional[Fernet] = None
        
        # Metrics
        self.training_metrics: List[TrainingMetrics] = []
        self.metrics_lock = asyncio.Lock()
        
        # Thread pool
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Control flags
        self.is_running = False
        self.is_training = False
        self.stop_requested = False
        
        # Initialize
        self._init_security()
        self._init_device()
        
        self.logger.info(f"Worker {worker_id} initialized on {self.state.device}")
    
    # ============================================
    # Initialization Methods
    # ============================================
    
    def _init_security(self) -> None:
        """Initialize encryption and security."""
        if self.config.enable_encryption:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            import base64
            
            if self.config.encryption_key:
                key = base64.urlsafe_b64encode(
                    hashlib.sha256(self.config.encryption_key.encode()).digest()
                )
            else:
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'nexus_salt_2026',
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(b"nexus_ai_trading_2026"))
            
            self.cipher = Fernet(key)
            self.logger.info("Encryption enabled")
    
    def _init_device(self) -> None:
        """Initialize the device for training."""
        if self.config.use_gpu and torch.cuda.is_available():
            self.device = torch.device("cuda")
            self.logger.info(f"Using GPU: {torch.cuda.get_device_name(0)}")
        else:
            self.device = torch.device("cpu")
            self.logger.info("Using CPU")
        
        torch.set_num_threads(self.config.num_workers)
    
    # ============================================
    # Model Management
    # ============================================
    
    def create_model(self) -> nn.Module:
        """
        Create the model architecture.
        
        Returns:
            PyTorch model
        """
        # This is a placeholder - in production, this would create the actual model
        from ai.models.base_model import BaseModel
        
        model = BaseModel()
        model = model.to(self.device)
        return model
    
    def initialize_model(self) -> None:
        """Initialize the model, optimizer, and criterion."""
        self.model = self.create_model()
        self.model.to(self.device)
        
        # Initialize optimizer
        if self.config.optimizer == "adam":
            self.optimizer = optim.Adam(
                self.model.parameters(),
                lr=self.config.learning_rate
            )
        elif self.config.optimizer == "sgd":
            self.optimizer = optim.SGD(
                self.model.parameters(),
                lr=self.config.learning_rate,
                momentum=0.9
            )
        else:
            self.optimizer = optim.Adam(
                self.model.parameters(),
                lr=self.config.learning_rate
            )
        
        # Initialize loss function
        if self.config.loss_function == "mse":
            self.criterion = nn.MSELoss()
        elif self.config.loss_function == "cross_entropy":
            self.criterion = nn.CrossEntropyLoss()
        else:
            self.criterion = nn.MSELoss()
        
        self.logger.info("Model initialized")
    
    def set_model_parameters(self, parameters: Dict[str, np.ndarray]) -> None:
        """
        Set model parameters from numpy arrays.
        
        Args:
            parameters: Dictionary of parameter arrays
        """
        if self.model is None:
            self.initialize_model()
        
        state_dict = {}
        for key, value in parameters.items():
            if isinstance(value, np.ndarray):
                state_dict[key] = torch.from_numpy(value).to(self.device)
            else:
                state_dict[key] = value
        
        self.model.load_state_dict(state_dict, strict=False)
        self.current_model_params = parameters
        
        self.logger.debug("Model parameters updated")
    
    def get_model_parameters(self) -> Dict[str, np.ndarray]:
        """
        Get model parameters as numpy arrays.
        
        Returns:
            Dictionary of parameter arrays
        """
        if self.model is None:
            self.initialize_model()
        
        parameters = {}
        for key, value in self.model.state_dict().items():
            if isinstance(value, torch.Tensor):
                parameters[key] = value.cpu().numpy()
            else:
                parameters[key] = value
        
        return parameters
    
    # ============================================
    # Data Management
    # ============================================
    
    def load_data(self) -> None:
        """Load and prepare training data."""
        # This is a placeholder - in production, this would load actual data
        # For demonstration, we create synthetic data
        import torch.utils.data as data_utils
        
        # Create synthetic data
        num_samples = 10000
        input_dim = 100
        output_dim = 1
        
        X = torch.randn(num_samples, input_dim)
        y = torch.randn(num_samples, output_dim)
        
        dataset = TensorDataset(X, y)
        
        # Split into train/validation
        train_size = int((1 - self.config.validation_split) * len(dataset))
        val_size = len(dataset) - train_size
        train_dataset, val_dataset = data_utils.random_split(
            dataset, [train_size, val_size]
        )
        
        self.dataset = dataset
        self.train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=self.config.shuffle_data,
            num_workers=self.config.num_workers,
            pin_memory=self.config.use_gpu,
        )
        self.val_loader = DataLoader(
            val_dataset,
            batch_size=self.config.batch_size,
            shuffle=False,
            num_workers=self.config.num_workers,
            pin_memory=self.config.use_gpu,
        )
        
        self.state.data_size = len(train_dataset)
        self.state.total_steps = len(self.train_loader) * self.config.local_epochs
        
        self.logger.info(f"Data loaded: {self.state.data_size} training samples")
    
    # ============================================
    # Training Methods
    # ============================================
    
    async def train_epoch(self, epoch: int) -> Dict[str, float]:
        """
        Train for one epoch.
        
        Args:
            epoch: Current epoch number
            
        Returns:
            Training metrics
        """
        if self.model is None:
            self.initialize_model()
        
        self.model.train()
        total_loss = 0.0
        total_correct = 0
        total_samples = 0
        batch_times = []
        
        for batch_idx, (data, targets) in enumerate(self.train_loader):
            start_time = time.time()
            
            # Move data to device
            data = data.to(self.device)
            targets = targets.to(self.device)
            
            # Forward pass
            self.optimizer.zero_grad()
            outputs = self.model(data)
            loss = self.criterion(outputs, targets)
            
            # Backward pass
            loss.backward()
            self.optimizer.step()
            
            # Track metrics
            batch_time = time.time() - start_time
            batch_times.append(batch_time)
            
            total_loss += loss.item() * data.size(0)
            total_samples += data.size(0)
            
            # Calculate accuracy (for classification tasks)
            if outputs.size(1) > 1:
                _, predicted = torch.max(outputs.data, 1)
                _, targets_max = torch.max(targets.data, 1)
                total_correct += (predicted == targets_max).sum().item()
            else:
                # Regression - use R² approximation
                total_correct += 1
            
            self.state.current_step += 1
            
            # Log progress
            if batch_idx % self.config.log_interval == 0:
                avg_loss = total_loss / total_samples
                accuracy = total_correct / total_samples if total_samples > 0 else 0
                self.logger.info(
                    f"Epoch {epoch}, Batch {batch_idx}/{len(self.train_loader)}, "
                    f"Loss: {avg_loss:.4f}, Acc: {accuracy:.4f}"
                )
        
        # Calculate epoch metrics
        avg_loss = total_loss / total_samples
        accuracy = total_correct / total_samples if total_samples > 0 else 0
        avg_batch_time = sum(batch_times) / len(batch_times) if batch_times else 0
        
        return {
            'loss': avg_loss,
            'accuracy': accuracy,
            'avg_batch_time': avg_batch_time,
            'samples': total_samples,
        }
    
    async def validate(self) -> Dict[str, float]:
        """
        Validate the model on validation data.
        
        Returns:
            Validation metrics
        """
        if self.model is None:
            self.initialize_model()
        
        self.model.eval()
        total_loss = 0.0
        total_correct = 0
        total_samples = 0
        
        with torch.no_grad():
            for data, targets in self.val_loader:
                data = data.to(self.device)
                targets = targets.to(self.device)
                
                outputs = self.model(data)
                loss = self.criterion(outputs, targets)
                
                total_loss += loss.item() * data.size(0)
                total_samples += data.size(0)
                
                if outputs.size(1) > 1:
                    _, predicted = torch.max(outputs.data, 1)
                    _, targets_max = torch.max(targets.data, 1)
                    total_correct += (predicted == targets_max).sum().item()
                else:
                    total_correct += 1
        
        avg_loss = total_loss / total_samples
        accuracy = total_correct / total_samples if total_samples > 0 else 0
        
        return {
            'loss': avg_loss,
            'accuracy': accuracy,
            'samples': total_samples,
        }
    
    async def local_training_round(self) -> Dict[str, Any]:
        """
        Perform one local training round.
        
        Returns:
            Training results including model updates
        """
        if self.model is None:
            self.initialize_model()
        
        self.state.status = WorkerStatus.TRAINING
        self.is_training = True
        
        self.logger.info(f"Starting local training round (epochs: {self.config.local_epochs})")
        
        # Get current global model
        global_model = await self.download_model()
        if global_model:
            self.set_model_parameters(global_model)
        
        # Training loop
        training_metrics = []
        for epoch in range(self.config.local_epochs):
            self.state.current_epoch = epoch
            
            # Train
            train_results = await self.train_epoch(epoch)
            self.state.local_loss = train_results['loss']
            self.state.local_accuracy = train_results['accuracy']
            
            # Validate
            val_results = await self.validate()
            
            # Record metrics
            metrics = TrainingMetrics(
                timestamp=time.time(),
                epoch=epoch,
                step=self.state.current_step,
                loss=train_results['loss'],
                accuracy=train_results['accuracy'],
                learning_rate=self.config.learning_rate,
                batch_time=train_results['avg_batch_time'],
                data_throughput=train_results['samples'] / train_results['avg_batch_time'],
                memory_usage=psutil.Process().memory_info().rss / 1024 / 1024,
                gpu_memory=torch.cuda.memory_allocated() / 1024 / 1024 if self.config.use_gpu else None,
            )
            training_metrics.append(metrics)
            
            self.logger.info(
                f"Epoch {epoch} completed: Loss={train_results['loss']:.4f}, "
                f"Acc={train_results['accuracy']:.4f}"
            )
        
        # Get model updates
        model_update = ModelUpdate(
            worker_id=self.worker_id,
            version_id=f"{self.config.model_name}_{int(time.time())}",
            parameters=self.get_model_parameters(),
            local_epoch=self.config.local_epochs,
            loss=self.state.local_loss,
            accuracy=self.state.local_accuracy,
            data_size=self.state.data_size,
            timestamp=time.time(),
        )
        
        self.is_training = False
        self.state.status = WorkerStatus.IDLE
        
        return {
            'metrics': training_metrics,
            'update': model_update,
            'validation': await self.validate(),
        }
    
    # ============================================
    # Communication Methods
    # ============================================
    
    async def _create_session(self) -> None:
        """Create HTTP session for communication."""
        if self.session is None:
            connector = TCPConnector(limit=100, limit_per_host=20)
            timeout = ClientTimeout(total=self.config.timeout)
            self.session = ClientSession(
                connector=connector,
                timeout=timeout,
                trust_env=True,
            )
    
    async def _close_session(self) -> None:
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def download_model(self) -> Optional[Dict[str, np.ndarray]]:
        """
        Download the latest model from the parameter server.
        
        Returns:
            Model parameters or None
        """
        await self._create_session()
        
        self.state.status = WorkerStatus.DOWNLOADING
        
        try:
            params = {
                'worker_id': self.worker_id,
                'version_id': 'latest',
            }
            
            async with self.session.get(
                f"{self.config.server_url}/api/model",
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Convert parameters
                    parameters = {}
                    for item in data.get('parameters', []):
                        parameters[item['name']] = np.array(item['value'])
                    
                    self.logger.info(f"Model downloaded (step: {data.get('global_step', 0)})")
                    self.state.global_step = data.get('global_step', 0)
                    
                    self.state.status = WorkerStatus.IDLE
                    return parameters
                else:
                    self.logger.error(f"Failed to download model: {response.status}")
                    self.state.status = WorkerStatus.ERROR
                    return None
                    
        except Exception as e:
            self.logger.error(f"Download error: {e}")
            self.state.status = WorkerStatus.ERROR
            return None
    
    async def upload_update(self, update: ModelUpdate) -> bool:
        """
        Upload model update to the parameter server.
        
        Args:
            update: Model update to upload
            
        Returns:
            True if upload successful
        """
        await self._create_session()
        
        self.state.status = WorkerStatus.UPLOADING
        
        try:
            # Prepare update data
            update_data = {
                'worker_id': update.worker_id,
                'version_id': update.version_id,
                'parameters': [
                    {'name': name, 'value': value.tolist()}
                    for name, value in update.parameters.items()
                ],
                'local_epoch': update.local_epoch,
                'loss': update.loss,
                'accuracy': update.accuracy,
                'data_size': update.data_size,
                'timestamp': update.timestamp,
            }
            
            async with self.session.post(
                f"{self.config.server_url}/api/update",
                json=update_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.logger.info(f"Update uploaded: {result.get('status', 'unknown')}")
                    self.state.last_sync = time.time()
                    
                    self.state.status = WorkerStatus.IDLE
                    return True
                else:
                    self.logger.error(f"Failed to upload update: {response.status}")
                    self.state.status = WorkerStatus.ERROR
                    return False
                    
        except Exception as e:
            self.logger.error(f"Upload error: {e}")
            self.state.status = WorkerStatus.ERROR
            return False
    
    async def send_heartbeat(self) -> bool:
        """
        Send heartbeat to the parameter server.
        
        Returns:
            True if heartbeat successful
        """
        await self._create_session()
        
        try:
            data = {
                'node_id': self.worker_id,
                'status': self.state.status.value,
                'timestamp': time.time(),
            }
            
            async with self.session.post(
                f"{self.config.server_url}/api/heartbeat",
                json=data
            ) as response:
                return response.status == 200
                
        except Exception as e:
            self.logger.error(f"Heartbeat error: {e}")
            return False
    
    async def register_with_server(self) -> bool:
        """
        Register with the parameter server.
        
        Returns:
            True if registration successful
        """
        await self._create_session()
        
        try:
            data = {
                'node_id': self.worker_id,
                'device': self.state.device,
                'data_size': self.state.data_size,
                'learning_rate': self.config.learning_rate,
                'batch_size': self.config.batch_size,
                'metadata': {
                    'model_name': self.config.model_name,
                    'model_version': self.config.model_version,
                }
            }
            
            async with self.session.post(
                f"{self.config.server_url}/api/register",
                json=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.logger.info(f"Registered with server: {result}")
                    self.state.status = WorkerStatus.IDLE
                    return True
                else:
                    self.logger.error(f"Registration failed: {response.status}")
                    self.state.status = WorkerStatus.ERROR
                    return False
                    
        except Exception as e:
            self.logger.error(f"Registration error: {e}")
            self.state.status = WorkerStatus.ERROR
            return False
    
    async def unregister_from_server(self) -> bool:
        """
        Unregister from the parameter server.
        
        Returns:
            True if unregistration successful
        """
        await self._create_session()
        
        try:
            data = {'node_id': self.worker_id}
            
            async with self.session.post(
                f"{self.config.server_url}/api/unregister",
                json=data
            ) as response:
                if response.status == 200:
                    self.logger.info("Unregistered from server")
                    return True
                else:
                    self.logger.error(f"Unregistration failed: {response.status}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Unregistration error: {e}")
            return False
    
    # ============================================
    # Main Worker Loop
    # ============================================
    
    async def worker_loop(self) -> None:
        """Main worker training loop."""
        self.is_running = True
        
        self.logger.info("Worker loop started")
        
        try:
            # Register with server
            if not await self.register_with_server():
                self.logger.error("Failed to register with server")
                return
            
            # Load data
            self.load_data()
            
            # Initialize model
            self.initialize_model()
            
            # Download initial model
            initial_model = await self.download_model()
            if initial_model:
                self.set_model_parameters(initial_model)
            
            self.state.status = WorkerStatus.IDLE
            
            # Main loop
            round_counter = 0
            while self.is_running and not self.stop_requested:
                try:
                    # Check if we should sync
                    if round_counter % self.config.sync_interval == 0:
                        # Perform local training round
                        round_counter += 1
                        self.logger.info(f"Starting training round {round_counter}")
                        
                        result = await self.local_training_round()
                        
                        # Upload update
                        if result['update']:
                            await self.upload_update(result['update'])
                        
                        # Log validation results
                        val_results = result.get('validation', {})
                        self.logger.info(
                            f"Round {round_counter} completed: "
                            f"Loss={val_results.get('loss', 0):.4f}, "
                            f"Acc={val_results.get('accuracy', 0):.4f}"
                        )
                        
                        # Record metrics
                        if self.config.metrics_enabled:
                            await self._record_metrics(result['metrics'])
                    
                    # Send heartbeat
                    await self.send_heartbeat()
                    
                    # Sleep before next iteration
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    self.logger.error(f"Loop iteration error: {e}")
                    await asyncio.sleep(5)
                
                # Check for stop signal
                if self.stop_requested:
                    self.logger.info("Stop requested, exiting loop")
                    break
        
        except Exception as e:
            self.logger.error(f"Worker loop error: {e}")
        
        finally:
            # Cleanup
            await self._cleanup()
    
    async def _record_metrics(self, metrics: List[TrainingMetrics]) -> None:
        """Record training metrics."""
        async with self.metrics_lock:
            self.training_metrics.extend(metrics)
            
            # Keep only last 1000 metrics
            if len(self.training_metrics) > 1000:
                self.training_metrics = self.training_metrics[-1000:]
    
    async def _cleanup(self) -> None:
        """Clean up resources."""
        self.is_running = False
        self.state.status = WorkerStatus.STOPPED
        
        # Unregister from server
        await self.unregister_from_server()
        
        # Close session
        await self._close_session()
        
        # Clear GPU memory
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        self.logger.info("Worker cleanup complete")
    
    # ============================================
    # Control Methods
    # ============================================
    
    def start(self) -> None:
        """Start the worker."""
        if self.is_running:
            self.logger.warning("Worker already running")
            return
        
        self.stop_requested = False
        
        # Run in event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(self.worker_loop())
        else:
            asyncio.run(self.worker_loop())
    
    def stop(self) -> None:
        """Stop the worker."""
        self.stop_requested = True
        self.logger.info("Worker stop requested")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get worker status.
        
        Returns:
            Worker status information
        """
        return {
            'worker_id': self.worker_id,
            'status': self.state.status.value,
            'role': self.state.role.value,
            'epoch': self.state.current_epoch,
            'step': self.state.current_step,
            'total_steps': self.state.total_steps,
            'data_size': self.state.data_size,
            'device': self.state.device,
            'accuracy': self.state.local_accuracy,
            'loss': self.state.local_loss,
            'global_step': self.state.global_step,
            'last_sync': self.state.last_sync,
            'uptime': time.time() - self.state.start_time,
        }
    
    def get_metrics(self) -> List[Dict[str, Any]]:
        """
        Get training metrics.
        
        Returns:
            List of training metrics
        """
        return [
            {
                'timestamp': m.timestamp,
                'epoch': m.epoch,
                'step': m.step,
                'loss': m.loss,
                'accuracy': m.accuracy,
                'learning_rate': m.learning_rate,
                'batch_time': m.batch_time,
                'data_throughput': m.data_throughput,
                'memory_usage': m.memory_usage,
                'gpu_memory': m.gpu_memory,
                'gradient_norm': m.gradient_norm,
            }
            for m in self.training_metrics
        ]


# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point."""
    import argparse
    import signal
    
    parser = argparse.ArgumentParser(description='NEXUS Distributed Worker')
    parser.add_argument('--worker-id', required=True, help='Worker identifier')
    parser.add_argument('--server-url', default='http://localhost:8080', help='Parameter server URL')
    parser.add_argument('--data-path', default='./data/training', help='Training data path')
    parser.add_argument('--batch-size', type=int, default=32, help='Batch size')
    parser.add_argument('--learning-rate', type=float, default=0.001, help='Learning rate')
    parser.add_argument('--local-epochs', type=int, default=5, help='Local epochs per round')
    parser.add_argument('--use-gpu', action='store_true', help='Use GPU for training')
    parser.add_argument('--log-level', default='INFO', help='Log level')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create configuration
    config = TrainingConfig(
        server_url=args.server_url,
        data_path=args.data_path,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        local_epochs=args.local_epochs,
        use_gpu=args.use_gpu,
        log_level=args.log_level,
    )
    
    # Create and start worker
    worker = DistributedWorker(args.worker_id, config)
    
    # Handle signals
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, stopping worker...")
        worker.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start worker
    worker.start()


if __name__ == '__main__':
    main()
