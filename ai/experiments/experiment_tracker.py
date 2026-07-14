"""
NEXUS AI TRADING SYSTEM - Experiment Tracker Module
Copyright © 2026 NEXUS QUANTUM LTD

This module provides comprehensive experiment tracking capabilities including:
- Experiment lifecycle management
- Hyperparameter tracking
- Metric logging and visualization
- Model checkpointing
- Experiment comparison
- Run management
- Version control integration
- Artifact management
- Parameter sweeps
- Multi-run analysis
- Statistical significance testing
- Experiment reproducibility
- Result visualization
- Dashboard generation
- Export capabilities
- Integration with MLflow, Weights & Biases, and TensorBoard
- Parallel experiment execution
- Experiment scheduling
- Notification system
- Resource monitoring
- Experiment templates
- Metadata management
"""

import os
import sys
import json
import yaml
import time
import logging
import hashlib
import pickle
import copy
import uuid
import threading
import queue
from typing import Dict, List, Optional, Tuple, Any, Union, Callable, Type, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, OrderedDict, Counter
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import torch
import torch.nn as nn
from torch.utils.tensorboard import SummaryWriter
import mlflow
import mlflow.pytorch
from mlflow.tracking import MlflowClient
import wandb
from tqdm import tqdm
import git
import psutil
import GPUtil
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import threading
import warnings
import traceback
import gc
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/experiment_tracker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Enums and Constants
# ============================================

class ExperimentStatus(Enum):
    """Status of an experiment."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    SCHEDULED = "scheduled"


class ExperimentType(Enum):
    """Types of experiments."""
    TRAINING = "training"
    EVALUATION = "evaluation"
    HYPERPARAMETER_TUNING = "hyperparameter_tuning"
    ABLATION = "ablation"
    BENCHMARK = "benchmark"
    INFERENCE = "inference"
    DATA_PROCESSING = "data_processing"
    MODEL_ANALYSIS = "model_analysis"


class MetricType(Enum):
    """Types of metrics."""
    SCALAR = "scalar"
    IMAGE = "image"
    TEXT = "text"
    TABLE = "table"
    HISTOGRAM = "histogram"
    AUDIO = "audio"
    VIDEO = "video"
    CURVE = "curve"
    FIGURE = "figure"
    EMBEDDING = "embedding"


@dataclass
class ExperimentConfig:
    """Configuration for an experiment."""
    experiment_id: str
    name: str
    description: str
    experiment_type: ExperimentType
    parameters: Dict[str, Any]
    environment: Dict[str, Any]
    resources: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class ExperimentRun:
    """Single run of an experiment."""
    run_id: str
    experiment_id: str
    status: ExperimentStatus
    start_time: float
    end_time: Optional[float] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, List[Tuple[float, float]]] = field(default_factory=dict)
    artifacts: Dict[str, str] = field(default_factory=dict)
    logs: List[Tuple[float, str, str]] = field(default_factory=list)
    system_metrics: Dict[str, List[Tuple[float, float]]] = field(default_factory=dict)
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None


@dataclass
class ExperimentSummary:
    """Summary of experiment results."""
    experiment_id: str
    name: str
    total_runs: int
    completed_runs: int
    failed_runs: int
    best_run: Optional[str] = None
    best_metrics: Dict[str, float] = field(default_factory=dict)
    parameter_importance: Dict[str, float] = field(default_factory=dict)
    statistics: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# ============================================
# Experiment Tracker Implementation
# ============================================

class ExperimentTracker:
    """
    Comprehensive experiment tracking system.
    
    This class manages the entire experiment lifecycle including creation,
    execution, tracking, and analysis of machine learning experiments.
    """
    
    def __init__(
        self,
        experiment_dir: str = "./experiments",
        enable_mlflow: bool = True,
        enable_wandb: bool = False,
        enable_tensorboard: bool = True,
        enable_git: bool = True,
        mlflow_tracking_uri: Optional[str] = None,
        wandb_project: Optional[str] = None,
        wandb_entity: Optional[str] = None,
        experiment_name: str = "nexus_ai_trading",
        tags: List[str] = None,
    ):
        """
        Initialize the experiment tracker.
        
        Args:
            experiment_dir: Directory to store experiment data
            enable_mlflow: Enable MLflow tracking
            enable_wandb: Enable Weights & Biases tracking
            enable_tensorboard: Enable TensorBoard logging
            enable_git: Enable Git integration
            mlflow_tracking_uri: MLflow tracking URI
            wandb_project: W&B project name
            wandb_entity: W&B entity name
            experiment_name: Name of the experiment
            tags: Tags for the experiment
        """
        self.experiment_dir = Path(experiment_dir)
        self.experiment_dir.mkdir(parents=True, exist_ok=True)
        
        self.enable_mlflow = enable_mlflow
        self.enable_wandb = enable_wandb
        self.enable_tensorboard = enable_tensorboard
        self.enable_git = enable_git
        
        self.experiment_name = experiment_name
        self.tags = tags or []
        
        # Initialize tracking systems
        self._init_mlflow(mlflow_tracking_uri)
        self._init_wandb(wandb_project, wandb_entity)
        self._init_tensorboard()
        self._init_git()
        
        # State
        self.experiments: Dict[str, ExperimentConfig] = {}
        self.runs: Dict[str, ExperimentRun] = {}
        self.current_run: Optional[str] = None
        self.lock = threading.Lock()
        
        # Resource monitoring
        self.resource_monitor: Optional[threading.Thread] = None
        self.resource_monitor_stop = threading.Event()
        
        # Queue for async logging
        self.log_queue = queue.Queue()
        self.log_worker: Optional[threading.Thread] = None
        
        # Load existing experiments
        self._load_experiments()
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Experiment Tracker initialized at {self.experiment_dir}")
        self.logger.info(f"MLflow: {'enabled' if enable_mlflow else 'disabled'}")
        self.logger.info(f"W&B: {'enabled' if enable_wandb else 'disabled'}")
        self.logger.info(f"TensorBoard: {'enabled' if enable_tensorboard else 'disabled'}")
    
    # ============================================
    # Initialization Methods
    # ============================================
    
    def _init_mlflow(self, tracking_uri: Optional[str] = None) -> None:
        """Initialize MLflow tracking."""
        if not self.enable_mlflow:
            return
        
        try:
            if tracking_uri:
                mlflow.set_tracking_uri(tracking_uri)
            
            # Set experiment
            mlflow.set_experiment(self.experiment_name)
            
            # Start a run if not already started
            if mlflow.active_run() is None:
                mlflow.start_run(run_name=self.experiment_name)
            
            self.logger.info("MLflow initialized successfully")
        except Exception as e:
            self.logger.warning(f"Failed to initialize MLflow: {e}")
            self.enable_mlflow = False
    
    def _init_wandb(self, project: Optional[str] = None, entity: Optional[str] = None) -> None:
        """Initialize Weights & Biases tracking."""
        if not self.enable_wandb:
            return
        
        try:
            wandb.init(
                project=project or self.experiment_name,
                entity=entity,
                config={},
                tags=self.tags,
                reinit=True,
            )
            self.logger.info("W&B initialized successfully")
        except Exception as e:
            self.logger.warning(f"Failed to initialize W&B: {e}")
            self.enable_wandb = False
    
    def _init_tensorboard(self) -> None:
        """Initialize TensorBoard logging."""
        if not self.enable_tensorboard:
            return
        
        try:
            self.tb_dir = self.experiment_dir / "tensorboard"
            self.tb_dir.mkdir(parents=True, exist_ok=True)
            self.writer = SummaryWriter(str(self.tb_dir))
            self.logger.info("TensorBoard initialized successfully")
        except Exception as e:
            self.logger.warning(f"Failed to initialize TensorBoard: {e}")
            self.enable_tensorboard = False
    
    def _init_git(self) -> None:
        """Initialize Git integration."""
        if not self.enable_git:
            return
        
        try:
            self.repo = git.Repo(search_parent_directories=True)
            self.git_commit = self.repo.head.commit.hexsha[:8]
            self.git_branch = self.repo.active_branch.name
            self.logger.info(f"Git integration: branch={self.git_branch}, commit={self.git_commit}")
        except Exception as e:
            self.logger.warning(f"Failed to initialize Git: {e}")
            self.enable_git = False
    
    def _load_experiments(self) -> None:
        """Load existing experiments from disk."""
        experiments_file = self.experiment_dir / "experiments.json"
        if experiments_file.exists():
            try:
                with open(experiments_file, 'r') as f:
                    data = json.load(f)
                    for exp_data in data.get('experiments', []):
                        exp = ExperimentConfig(
                            experiment_id=exp_data['experiment_id'],
                            name=exp_data['name'],
                            description=exp_data['description'],
                            experiment_type=ExperimentType(exp_data['experiment_type']),
                            parameters=exp_data['parameters'],
                            environment=exp_data['environment'],
                            resources=exp_data['resources'],
                            metadata=exp_data.get('metadata', {}),
                            tags=exp_data.get('tags', []),
                            parent_id=exp_data.get('parent_id'),
                            created_at=exp_data['created_at'],
                        )
                        self.experiments[exp.experiment_id] = exp
                    self.logger.info(f"Loaded {len(self.experiments)} experiments")
            except Exception as e:
                self.logger.warning(f"Failed to load experiments: {e}")
    
    # ============================================
    # Experiment Management
    # ============================================
    
    def create_experiment(
        self,
        name: str,
        description: str,
        experiment_type: ExperimentType,
        parameters: Dict[str, Any],
        tags: List[str] = None,
        parent_id: Optional[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """
        Create a new experiment.
        
        Args:
            name: Experiment name
            description: Experiment description
            experiment_type: Type of experiment
            parameters: Experiment parameters
            tags: Experiment tags
            parent_id: Parent experiment ID
            metadata: Additional metadata
            
        Returns:
            Experiment ID
        """
        experiment_id = f"exp_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Get environment info
        environment = {
            'python_version': sys.version,
            'platform': sys.platform,
            'hostname': os.uname().nodename if hasattr(os, 'uname') else 'unknown',
            'gpu_available': torch.cuda.is_available(),
            'gpu_count': torch.cuda.device_count() if torch.cuda.is_available() else 0,
            'cpu_count': os.cpu_count(),
            'memory_total': psutil.virtual_memory().total / (1024**3),  # GB
        }
        
        if torch.cuda.is_available():
            environment['gpu_name'] = torch.cuda.get_device_name(0)
            environment['cuda_version'] = torch.version.cuda
        
        # Get resources
        resources = {
            'experiment_dir': str(self.experiment_dir / experiment_id),
        }
        
        config = ExperimentConfig(
            experiment_id=experiment_id,
            name=name,
            description=description,
            experiment_type=experiment_type,
            parameters=parameters,
            environment=environment,
            resources=resources,
            metadata=metadata or {},
            tags=tags or [],
            parent_id=parent_id,
            created_at=time.time(),
        )
        
        # Create experiment directory
        exp_dir = self.experiment_dir / experiment_id
        exp_dir.mkdir(parents=True, exist_ok=True)
        
        # Save configuration
        config_file = exp_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(asdict(config), f, indent=2, default=str)
        
        # Store in memory
        with self.lock:
            self.experiments[experiment_id] = config
        
        # Save to index
        self._save_experiments_index()
        
        self.logger.info(f"Created experiment: {name} ({experiment_id})")
        return experiment_id
    
    def _save_experiments_index(self) -> None:
        """Save experiments index to disk."""
        experiments_file = self.experiment_dir / "experiments.json"
        data = {
            'timestamp': time.time(),
            'experiments': [asdict(exp) for exp in self.experiments.values()],
        }
        with open(experiments_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    # ============================================
    # Run Management
    # ============================================
    
    def start_run(
        self,
        experiment_id: str,
        parameters: Optional[Dict[str, Any]] = None,
        resume_from: Optional[str] = None,
        tags: List[str] = None,
    ) -> str:
        """
        Start a new run for an experiment.
        
        Args:
            experiment_id: Experiment ID
            parameters: Run parameters (overrides experiment params)
            resume_from: Run ID to resume from
            tags: Run tags
            
        Returns:
            Run ID
        """
        if experiment_id not in self.experiments:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        experiment = self.experiments[experiment_id]
        
        # Merge parameters
        run_params = {**experiment.parameters}
        if parameters:
            run_params.update(parameters)
        
        # Resume from previous run
        if resume_from and resume_from in self.runs:
            prev_run = self.runs[resume_from]
            run_params = {**prev_run.parameters, **run_params}
        
        run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        run = ExperimentRun(
            run_id=run_id,
            experiment_id=experiment_id,
            status=ExperimentStatus.RUNNING,
            start_time=time.time(),
            parameters=run_params,
            git_commit=self.git_commit if self.enable_git else None,
            git_branch=self.git_branch if self.enable_git else None,
            metadata={'tags': tags or []},
        )
        
        # Create run directory
        run_dir = self.experiment_dir / experiment_id / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Save run config
        run_file = run_dir / "run_config.json"
        with open(run_file, 'w') as f:
            json.dump(asdict(run), f, indent=2, default=str)
        
        # Store in memory
        with self.lock:
            self.runs[run_id] = run
            self.current_run = run_id
        
        # Start resource monitoring
        self._start_resource_monitoring(run_id)
        
        # Log to tracking systems
        self._log_run_start(run)
        
        self.logger.info(f"Started run: {run_id} for experiment {experiment_id}")
        return run_id
    
    def end_run(self, run_id: str, status: ExperimentStatus = ExperimentStatus.COMPLETED) -> None:
        """
        End a run.
        
        Args:
            run_id: Run ID
            status: Final status
        """
        if run_id not in self.runs:
            raise ValueError(f"Run {run_id} not found")
        
        run = self.runs[run_id]
        run.status = status
        run.end_time = time.time()
        
        # Stop resource monitoring
        self._stop_resource_monitoring()
        
        # Save run data
        run_dir = self.experiment_dir / run.experiment_id / run_id
        run_file = run_dir / "run_config.json"
        with open(run_file, 'w') as f:
            json.dump(asdict(run), f, indent=2, default=str)
        
        # Log to tracking systems
        self._log_run_end(run)
        
        # Update current run
        if self.current_run == run_id:
            self.current_run = None
        
        self.logger.info(f"Ended run: {run_id} with status {status.value}")
    
    # ============================================
    # Metric Logging
    # ============================================
    
    def log_metric(
        self,
        run_id: str,
        key: str,
        value: float,
        step: Optional[int] = None,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Log a metric for a run.
        
        Args:
            run_id: Run ID
            key: Metric key
            value: Metric value
            step: Step number (auto-increments if None)
            timestamp: Timestamp (defaults to now)
        """
        if run_id not in self.runs:
            raise ValueError(f"Run {run_id} not found")
        
        run = self.runs[run_id]
        ts = timestamp or time.time()
        
        # Determine step
        if step is None:
            if key in run.metrics:
                step = len(run.metrics[key])
            else:
                step = 0
        
        # Store metric
        if key not in run.metrics:
            run.metrics[key] = []
        run.metrics[key].append((ts, value))
        
        # Log to tracking systems
        self._log_metric_external(run_id, key, value, step)
        
        # Queue for async saving
        self.log_queue.put(('metric', run_id, key, value, step, ts))
    
    def log_metrics(
        self,
        run_id: str,
        metrics: Dict[str, float],
        step: Optional[int] = None,
    ) -> None:
        """
        Log multiple metrics for a run.
        
        Args:
            run_id: Run ID
            metrics: Dictionary of metrics
            step: Step number
        """
        for key, value in metrics.items():
            self.log_metric(run_id, key, value, step)
    
    def log_artifact(
        self,
        run_id: str,
        name: str,
        data: Any,
        artifact_type: str = "file",
    ) -> str:
        """
        Log an artifact for a run.
        
        Args:
            run_id: Run ID
            name: Artifact name
            data: Artifact data
            artifact_type: Type of artifact
            
        Returns:
            Artifact path
        """
        if run_id not in self.runs:
            raise ValueError(f"Run {run_id} not found")
        
        run = self.runs[run_id]
        run_dir = self.experiment_dir / run.experiment_id / run_id
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Save artifact
        artifact_path = artifacts_dir / f"{name}_{int(time.time())}"
        
        if artifact_type in ["json", "dict"]:
            with open(artifact_path.with_suffix('.json'), 'w') as f:
                json.dump(data, f, indent=2, default=str)
            artifact_path = artifact_path.with_suffix('.json')
        elif artifact_type in ["pickle", "model"]:
            with open(artifact_path.with_suffix('.pkl'), 'wb') as f:
                pickle.dump(data, f)
            artifact_path = artifact_path.with_suffix('.pkl')
        elif artifact_type == "text":
            with open(artifact_path.with_suffix('.txt'), 'w') as f:
                f.write(str(data))
            artifact_path = artifact_path.with_suffix('.txt')
        elif artifact_type == "image":
            if hasattr(data, 'save'):
                data.save(artifact_path.with_suffix('.png'))
                artifact_path = artifact_path.with_suffix('.png')
            else:
                import matplotlib.pyplot as plt
                plt.figure()
                plt.imshow(data)
                plt.savefig(artifact_path.with_suffix('.png'))
                plt.close()
                artifact_path = artifact_path.with_suffix('.png')
        elif artifact_type == "figure":
            data.savefig(artifact_path.with_suffix('.png'), dpi=300, bbox_inches='tight')
            artifact_path = artifact_path.with_suffix('.png')
        else:
            with open(artifact_path, 'wb') as f:
                f.write(data)
        
        # Store artifact reference
        run.artifacts[name] = str(artifact_path)
        
        # Log to tracking systems
        self._log_artifact_external(run_id, name, str(artifact_path))
        
        self.logger.debug(f"Logged artifact: {name} -> {artifact_path}")
        return str(artifact_path)
    
    def log_model(
        self,
        run_id: str,
        model: nn.Module,
        model_name: str = "model",
        metrics: Optional[Dict[str, float]] = None,
    ) -> str:
        """
        Log a model as an artifact.
        
        Args:
            run_id: Run ID
            model: PyTorch model
            model_name: Name of the model
            metrics: Model metrics
            
        Returns:
            Model artifact path
        """
        # Save model
        model_path = self.log_artifact(
            run_id=run_id,
            name=model_name,
            data=model.state_dict(),
            artifact_type="pickle",
        )
        
        # Log metrics if provided
        if metrics:
            self.log_metrics(run_id, metrics)
        
        # Log to tracking systems
        if self.enable_mlflow:
            mlflow.pytorch.log_model(model, model_name)
        
        if self.enable_wandb and wandb.run is not None:
            wandb.save(model_path)
        
        self.logger.info(f"Logged model: {model_name} -> {model_path}")
        return model_path
    
    # ============================================
    # System Monitoring
    # ============================================
    
    def _start_resource_monitoring(self, run_id: str) -> None:
        """Start resource monitoring thread."""
        if self.resource_monitor is not None:
            return
        
        self.resource_monitor_stop.clear()
        self.resource_monitor = threading.Thread(
            target=self._monitor_resources,
            args=(run_id,),
            daemon=True,
        )
        self.resource_monitor.start()
    
    def _stop_resource_monitoring(self) -> None:
        """Stop resource monitoring thread."""
        if self.resource_monitor is None:
            return
        
        self.resource_monitor_stop.set()
        self.resource_monitor.join(timeout=2)
        self.resource_monitor = None
    
    def _monitor_resources(self, run_id: str) -> None:
        """
        Monitor system resources.
        
        Args:
            run_id: Run ID to log metrics for
        """
        while not self.resource_monitor_stop.is_set():
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self.log_metric(run_id, "system/cpu_usage", cpu_percent / 100)
                
                # Memory usage
                memory = psutil.virtual_memory()
                self.log_metric(run_id, "system/memory_usage", memory.percent / 100)
                
                # GPU usage
                if torch.cuda.is_available():
                    gpu_util = torch.cuda.utilization()
                    if gpu_util is not None:
                        self.log_metric(run_id, "system/gpu_usage", gpu_util / 100)
                    
                    gpu_memory = torch.cuda.memory_allocated() / (1024**3)
                    self.log_metric(run_id, "system/gpu_memory_used", gpu_memory)
                
                # Disk usage
                disk = psutil.disk_usage('/')
                self.log_metric(run_id, "system/disk_usage", disk.percent / 100)
                
                time.sleep(5)
            except Exception as e:
                self.logger.warning(f"Resource monitoring error: {e}")
                time.sleep(10)
    
    # ============================================
    # Log Worker
    # ============================================
    
    def _start_log_worker(self) -> None:
        """Start log worker thread."""
        if self.log_worker is not None:
            return
        
        self.log_worker = threading.Thread(
            target=self._process_log_queue,
            daemon=True,
        )
        self.log_worker.start()
    
    def _process_log_queue(self) -> None:
        """Process log queue items."""
        while True:
            try:
                item = self.log_queue.get(timeout=1)
                if item is None:
                    break
                
                # Process based on type
                if item[0] == 'metric':
                    _, run_id, key, value, step, ts = item
                    self._save_metric_to_disk(run_id, key, value, step, ts)
                elif item[0] == 'artifact':
                    _, run_id, name, path = item
                    self._save_artifact_to_disk(run_id, name, path)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.warning(f"Log worker error: {e}")
    
    def _save_metric_to_disk(self, run_id: str, key: str, value: float, step: int, ts: float) -> None:
        """
        Save metric to disk.
        
        Args:
            run_id: Run ID
            key: Metric key
            value: Metric value
            step: Step number
            ts: Timestamp
        """
        if run_id not in self.runs:
            return
        
        run = self.runs[run_id]
        run_dir = self.experiment_dir / run.experiment_id / run_id
        metrics_file = run_dir / "metrics.json"
        
        # Load existing metrics
        metrics_data = {}
        if metrics_file.exists():
            with open(metrics_file, 'r') as f:
                metrics_data = json.load(f)
        
        # Add metric
        if key not in metrics_data:
            metrics_data[key] = []
        metrics_data[key].append({'step': step, 'value': value, 'timestamp': ts})
        
        # Save
        with open(metrics_file, 'w') as f:
            json.dump(metrics_data, f, indent=2, default=str)
    
    def _save_artifact_to_disk(self, run_id: str, name: str, path: str) -> None:
        """
        Save artifact reference to disk.
        
        Args:
            run_id: Run ID
            name: Artifact name
            path: Artifact path
        """
        if run_id not in self.runs:
            return
        
        run = self.runs[run_id]
        run_dir = self.experiment_dir / run.experiment_id / run_id
        artifacts_file = run_dir / "artifacts.json"
        
        # Load existing artifacts
        artifacts_data = {}
        if artifacts_file.exists():
            with open(artifacts_file, 'r') as f:
                artifacts_data = json.load(f)
        
        # Add artifact
        artifacts_data[name] = path
        
        # Save
        with open(artifacts_file, 'w') as f:
            json.dump(artifacts_data, f, indent=2, default=str)
    
    # ============================================
    # External Tracking Systems
    # ============================================
    
    def _log_run_start(self, run: ExperimentRun) -> None:
        """Log run start to external tracking systems."""
        if self.enable_mlflow:
            try:
                mlflow.start_run(run_name=run.run_id)
                mlflow.log_params(run.parameters)
                if run.git_commit:
                    mlflow.log_param('git_commit', run.git_commit)
                if run.git_branch:
                    mlflow.log_param('git_branch', run.git_branch)
            except Exception as e:
                self.logger.warning(f"MLflow run start error: {e}")
        
        if self.enable_wandb and wandb.run is not None:
            try:
                wandb.config.update(run.parameters)
                if run.git_commit:
                    wandb.config.update({'git_commit': run.git_commit})
                if run.git_branch:
                    wandb.config.update({'git_branch': run.git_branch})
            except Exception as e:
                self.logger.warning(f"W&B run start error: {e}")
    
    def _log_run_end(self, run: ExperimentRun) -> None:
        """Log run end to external tracking systems."""
        if self.enable_mlflow:
            try:
                mlflow.end_run()
            except Exception as e:
                self.logger.warning(f"MLflow run end error: {e}")
        
        if self.enable_wandb and wandb.run is not None:
            try:
                wandb.finish()
            except Exception as e:
                self.logger.warning(f"W&B run end error: {e}")
    
    def _log_metric_external(self, run_id: str, key: str, value: float, step: int) -> None:
        """Log metric to external tracking systems."""
        if self.enable_mlflow:
            try:
                mlflow.log_metric(key, value, step=step)
            except Exception as e:
                self.logger.warning(f"MLflow metric error: {e}")
        
        if self.enable_wandb and wandb.run is not None:
            try:
                wandb.log({key: value}, step=step)
            except Exception as e:
                self.logger.warning(f"W&B metric error: {e}")
        
        if self.enable_tensorboard:
            try:
                self.writer.add_scalar(key, value, step)
            except Exception as e:
                self.logger.warning(f"TensorBoard metric error: {e}")
    
    def _log_artifact_external(self, run_id: str, name: str, path: str) -> None:
        """Log artifact to external tracking systems."""
        if self.enable_mlflow:
            try:
                mlflow.log_artifact(path, artifact_path=name)
            except Exception as e:
                self.logger.warning(f"MLflow artifact error: {e}")
        
        if self.enable_wandb and wandb.run is not None:
            try:
                wandb.save(path, base_path=str(self.experiment_dir))
            except Exception as e:
                self.logger.warning(f"W&B artifact error: {e}")
    
    # ============================================
    # Query and Analysis
    # ============================================
    
    def get_experiment(self, experiment_id: str) -> Optional[ExperimentConfig]:
        """
        Get experiment configuration.
        
        Args:
            experiment_id: Experiment ID
            
        Returns:
            Experiment configuration or None
        """
        return self.experiments.get(experiment_id)
    
    def get_run(self, run_id: str) -> Optional[ExperimentRun]:
        """
        Get run data.
        
        Args:
            run_id: Run ID
            
        Returns:
            Run data or None
        """
        return self.runs.get(run_id)
    
    def get_experiment_runs(self, experiment_id: str) -> List[ExperimentRun]:
        """
        Get all runs for an experiment.
        
        Args:
            experiment_id: Experiment ID
            
        Returns:
            List of runs
        """
        return [run for run in self.runs.values() if run.experiment_id == experiment_id]
    
    def get_best_runs(self, experiment_id: str, metric: str = "accuracy", n: int = 5) -> List[ExperimentRun]:
        """
        Get the best runs for an experiment.
        
        Args:
            experiment_id: Experiment ID
            metric: Metric to optimize
            n: Number of runs to return
            
        Returns:
            List of best runs
        """
        runs = self.get_experiment_runs(experiment_id)
        completed = [r for r in runs if r.status == ExperimentStatus.COMPLETED]
        
        # Extract metric values
        scored = []
        for run in completed:
            if metric in run.metrics and run.metrics[metric]:
                final_value = run.metrics[metric][-1][1]
                scored.append((run, final_value))
        
        # Sort by metric (descending for accuracy, ascending for loss)
        scored.sort(key=lambda x: x[1], reverse=True)
        return [run for run, _ in scored[:n]]
    
    def compare_runs(self, run_ids: List[str]) -> pd.DataFrame:
        """
        Compare multiple runs.
        
        Args:
            run_ids: List of run IDs
            
        Returns:
            DataFrame with comparison data
        """
        runs = [self.runs[run_id] for run_id in run_ids if run_id in self.runs]
        if not runs:
            return pd.DataFrame()
        
        data = []
        for run in runs:
            row = {
                'run_id': run.run_id,
                'status': run.status.value,
                'duration': run.end_time - run.start_time if run.end_time else None,
            }
            
            # Add parameters
            for key, value in run.parameters.items():
                row[f'param_{key}'] = value
            
            # Add metrics (last value)
            for key, values in run.metrics.items():
                if values:
                    row[f'metric_{key}_final'] = values[-1][1]
                    row[f'metric_{key}_last'] = values[-1][1]
                    row[f'metric_{key}_best'] = max(v[1] for v in values)
            
            data.append(row)
        
        return pd.DataFrame(data)
    
    # ============================================
    # Visualization
    # ============================================
    
    def plot_metrics(
        self,
        run_ids: List[str],
        metrics: List[str],
        title: Optional[str] = None,
        figsize: Tuple[int, int] = (12, 8),
        save_path: Optional[str] = None,
    ) -> None:
        """
        Plot metrics for multiple runs.
        
        Args:
            run_ids: List of run IDs
            metrics: List of metrics to plot
            title: Plot title
            figsize: Figure size
            save_path: Path to save figure
        """
        n_metrics = len(metrics)
        fig, axes = plt.subplots(n_metrics, 1, figsize=figsize)
        if n_metrics == 1:
            axes = [axes]
        
        for i, metric in enumerate(metrics):
            ax = axes[i]
            for run_id in run_ids:
                run = self.runs.get(run_id)
                if not run or metric not in run.metrics:
                    continue
                
                values = run.metrics[metric]
                if not values:
                    continue
                
                steps = [v[0] for v in values]
                vals = [v[1] for v in values]
                ax.plot(steps, vals, label=f"{run_id[:8]}")
            
            ax.set_title(f"{metric}")
            ax.set_xlabel("Step")
            ax.set_ylabel(metric)
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        if title:
            fig.suptitle(title, fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Saved plot to {save_path}")
        
        plt.show()
    
    def generate_report(
        self,
        experiment_id: str,
        output_format: str = "html",
        output_dir: Optional[str] = None,
    ) -> str:
        """
        Generate a report for an experiment.
        
        Args:
            experiment_id: Experiment ID
            output_format: Report format (html, md, pdf)
            output_dir: Output directory
            
        Returns:
            Path to the generated report
        """
        experiment = self.experiments.get(experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")
        
        runs = self.get_experiment_runs(experiment_id)
        completed = [r for r in runs if r.status == ExperimentStatus.COMPLETED]
        
        # Create report directory
        report_dir = Path(output_dir) if output_dir else self.experiment_dir / experiment_id / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        if output_format == "html":
            report_path = report_dir / "report.html"
            self._generate_html_report(experiment, completed, report_path)
        elif output_format == "md":
            report_path = report_dir / "report.md"
            self._generate_markdown_report(experiment, completed, report_path)
        elif output_format == "pdf":
            report_path = report_dir / "report.pdf"
            self._generate_pdf_report(experiment, completed, report_path)
        else:
            raise ValueError(f"Unsupported format: {output_format}")
        
        self.logger.info(f"Generated report: {report_path}")
        return str(report_path)
    
    def _generate_html_report(
        self,
        experiment: ExperimentConfig,
        runs: List[ExperimentRun],
        output_path: Path,
    ) -> None:
        """Generate HTML report."""
        import jinja2
        
        # Prepare data
        best_run = max(runs, key=lambda r: max((v[-1][1] for v in r.metrics.values() if v), default=0))
        
        template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Experiment Report: {{ experiment.name }}</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
                .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                h1 { color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }
                h2 { color: #555; margin-top: 30px; }
                table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
                th { background-color: #4CAF50; color: white; }
                tr:hover { background-color: #f5f5f5; }
                .metric-card { display: inline-block; margin: 10px; padding: 20px; background: #f9f9f9; border-radius: 8px; min-width: 150px; }
                .metric-value { font-size: 24px; font-weight: bold; color: #4CAF50; }
                .metric-label { color: #666; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Experiment Report: {{ experiment.name }}</h1>
                <p><strong>ID:</strong> {{ experiment.experiment_id }}</p>
                <p><strong>Description:</strong> {{ experiment.description }}</p>
                <p><strong>Type:</strong> {{ experiment.experiment_type.value }}</p>
                <p><strong>Created:</strong> {{ experiment.created_at | datetime }}</p>
                
                <h2>Summary</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Total Runs</td><td>{{ runs|length }}</td></tr>
                    <tr><td>Completed Runs</td><td>{{ completed_count }}</td></tr>
                    <tr><td>Failed Runs</td><td>{{ failed_count }}</td></tr>
                    <tr><td>Best Run</td><td>{{ best_run.run_id[:8] }}</td></tr>
                </table>
                
                <h2>Best Run Metrics</h2>
                <div>
                    {% for key, values in best_run.metrics.items() %}
                        {% if values %}
                        <div class="metric-card">
                            <div class="metric-label">{{ key }}</div>
                            <div class="metric-value">{{ values[-1][1] | round(4) }}</div>
                        </div>
                        {% endif %}
                    {% endfor %}
                </div>
                
                <h2>All Runs</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Run ID</th>
                            <th>Status</th>
                            <th>Duration (s)</th>
                            {% for key in best_run.metrics.keys() %}
                                <th>{{ key }}</th>
                            {% endfor %}
                        </tr>
                    </thead>
                    <tbody>
                        {% for run in runs %}
                        <tr>
                            <td>{{ run.run_id[:8] }}</td>
                            <td>{{ run.status.value }}</td>
                            <td>{{ (run.end_time - run.start_time) | round(2) if run.end_time else 'N/A' }}</td>
                            {% for key in best_run.metrics.keys() %}
                                <td>{{ run.metrics[key][-1][1] | round(4) if run.metrics.get(key) else 'N/A' }}</td>
                            {% endfor %}
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                
                <p><em>Generated: {{ now() }}</em></p>
            </div>
        </body>
        </html>
        """
        
        # Simple rendering without jinja2 to avoid dependency
        html = template.replace('{{ experiment.name }}', experiment.name)
        html = html.replace('{{ experiment.experiment_id }}', experiment.experiment_id)
        html = html.replace('{{ experiment.description }}', experiment.description)
        html = html.replace('{{ experiment.experiment_type.value }}', experiment.experiment_type.value)
        html = html.replace('{{ experiment.created_at | datetime }}', datetime.fromtimestamp(experiment.created_at).isoformat())
        html = html.replace('{{ runs|length }}', str(len(runs)))
        html = html.replace('{{ completed_count }}', str(len([r for r in runs if r.status == ExperimentStatus.COMPLETED])))
        html = html.replace('{{ failed_count }}', str(len([r for r in runs if r.status == ExperimentStatus.FAILED])))
        html = html.replace('{{ best_run.run_id[:8] }}', best_run.run_id[:8] if best_run else 'N/A')
        html = html.replace('{{ now() }}', datetime.now().isoformat())
        
        with open(output_path, 'w') as f:
            f.write(html)
    
    def _generate_markdown_report(
        self,
        experiment: ExperimentConfig,
        runs: List[ExperimentRun],
        output_path: Path,
    ) -> None:
        """Generate Markdown report."""
        lines = [
            f"# Experiment Report: {experiment.name}",
            "",
            f"**ID:** {experiment.experiment_id}",
            f"**Description:** {experiment.description}",
            f"**Type:** {experiment.experiment_type.value}",
            f"**Created:** {datetime.fromtimestamp(experiment.created_at).isoformat()}",
            "",
            "## Summary",
            "",
            f"- Total Runs: {len(runs)}",
            f"- Completed Runs: {len([r for r in runs if r.status == ExperimentStatus.COMPLETED])}",
            f"- Failed Runs: {len([r for r in runs if r.status == ExperimentStatus.FAILED])}",
            "",
            "## All Runs",
            "",
            "| Run ID | Status | Duration (s) |",
            "|--------|--------|--------------|",
        ]
        
        for run in runs:
            duration = run.end_time - run.start_time if run.end_time else 0
            lines.append(f"| {run.run_id[:8]} | {run.status.value} | {duration:.2f} |")
        
        lines.append("")
        lines.append("---")
        lines.append("*Generated by NEXUS Experiment Tracker*")
        
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))
    
    def _generate_pdf_report(
        self,
        experiment: ExperimentConfig,
        runs: List[ExperimentRun],
        output_path: Path,
    ) -> None:
        """Generate PDF report."""
        # Use matplotlib to create a simple PDF report
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle(f"Experiment Report: {experiment.name}", fontsize=16, fontweight='bold')
        
        # Plot 1: Run status distribution
        ax1 = axes[0, 0]
        statuses = [r.status.value for r in runs]
        status_counts = Counter(statuses)
        ax1.bar(status_counts.keys(), status_counts.values(), color=['green', 'red', 'orange'])
        ax1.set_title('Run Status Distribution')
        ax1.set_xlabel('Status')
        ax1.set_ylabel('Count')
        
        # Plot 2: Duration distribution
        ax2 = axes[0, 1]
        durations = [r.end_time - r.start_time for r in runs if r.end_time]
        if durations:
            ax2.hist(durations, bins=20, color='blue', alpha=0.7)
            ax2.set_title('Run Duration Distribution')
            ax2.set_xlabel('Duration (s)')
            ax2.set_ylabel('Frequency')
        
        # Plot 3: Metrics comparison
        ax3 = axes[1, 0]
        if runs and runs[0].metrics:
            metric_keys = list(runs[0].metrics.keys())
            metric_values = []
            for run in runs:
                values = []
                for key in metric_keys:
                    if key in run.metrics and run.metrics[key]:
                        values.append(run.metrics[key][-1][1])
                    else:
                        values.append(0)
                metric_values.append(values)
            
            if metric_values:
                ax3.boxplot(metric_values, labels=metric_keys)
                ax3.set_title('Metrics Distribution')
                ax3.set_xlabel('Metric')
                ax3.set_ylabel('Value')
                ax3.tick_params(axis='x', rotation=45)
        
        # Plot 4: Parameter importance (placeholder)
        ax4 = axes[1, 1]
        ax4.text(0.5, 0.5, 'Parameter Importance\n(Coming Soon)', 
                ha='center', va='center', fontsize=12, transform=ax4.transAxes)
        ax4.set_title('Parameter Importance')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        self.logger.info(f"Generated PDF report: {output_path}")

# ============================================
# Command Line Interface
# ============================================

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='NEXUS Experiment Tracker')
    parser.add_argument('--command', choices=['list', 'create', 'run', 'summary', 'compare', 'export'],
                       required=True, help='Command to execute')
    parser.add_argument('--experiment-id', type=str, help='Experiment ID')
    parser.add_argument('--name', type=str, help='Experiment name')
    parser.add_argument('--description', type=str, help='Experiment description')
    parser.add_argument('--config', type=str, help='Configuration file')
    parser.add_argument('--output', type=str, help='Output file')
    parser.add_argument('--format', type=str, default='html', help='Report format')
    parser.add_argument('--runs', type=str, help='Run IDs (comma-separated)')
    parser.add_argument('--metric', type=str, default='accuracy', help='Metric to optimize')
    parser.add_argument('--n', type=int, default=5, help='Number of runs to show')
    parser.add_argument('--experiment-dir', type=str, default='./experiments', help='Experiment directory')
    parser.add_argument('--log-level', type=str, default='INFO', help='Logging level')
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize tracker
    tracker = ExperimentTracker(
        experiment_dir=args.experiment_dir,
        enable_mlflow=False,
        enable_wandb=False,
        enable_tensorboard=True,
        enable_git=False,
    )
    
    if args.command == 'list':
        # List all experiments
        print("Experiments:")
        print("-" * 60)
        for exp_id, exp in tracker.experiments.items():
            runs = tracker.get_experiment_runs(exp_id)
            print(f"ID: {exp_id}")
            print(f"  Name: {exp.name}")
            print(f"  Type: {exp.experiment_type.value}")
            print(f"  Runs: {len(runs)}")
            print(f"  Created: {datetime.fromtimestamp(exp.created_at).isoformat()}")
            print()
    
    elif args.command == 'create':
        # Create new experiment
        if not args.name or not args.config:
            print("Error: --name and --config are required")
            return
        
        with open(args.config, 'r') as f:
            config = json.load(f)
        
        exp_id = tracker.create_experiment(
            name=args.name,
            description=config.get('description', ''),
            experiment_type=ExperimentType(config.get('experiment_type', 'training')),
            parameters=config.get('parameters', {}),
            tags=config.get('tags', []),
        )
        print(f"Created experiment: {exp_id}")
    
    elif args.command == 'run':
        # Run an experiment
        if not args.experiment_id:
            print("Error: --experiment-id is required")
            return
        
        # Load config if provided
        parameters = {}
        if args.config:
            with open(args.config, 'r') as f:
                parameters = json.load(f)
        
        run_id = tracker.start_run(
            experiment_id=args.experiment_id,
            parameters=parameters,
        )
        print(f"Started run: {run_id}")
        
        # Simulate training
        print("Running training...")
        import time
        for step in range(100):
            time.sleep(0.05)
            tracker.log_metric(
                run_id=run_id,
                key='accuracy',
                value=0.5 + 0.4 * (1 - np.exp(-step / 20)) + np.random.normal(0, 0.02),
                step=step
            )
            tracker.log_metric(
                run_id=run_id,
                key='loss',
                value=0.5 * np.exp(-step / 15) + np.random.exponential(0.02),
                step=step
            )
            if step % 10 == 0:
                print(f"Step {step}: accuracy={tracker.runs[run_id].metrics['accuracy'][-1][1]:.4f}")
        
        tracker.end_run(run_id)
        print(f"Run completed: {run_id}")
    
    elif args.command == 'summary':
        # Show experiment summary
        if not args.experiment_id:
            print("Error: --experiment-id is required")
            return
        
        exp = tracker.get_experiment(args.experiment_id)
        if not exp:
            print(f"Experiment {args.experiment_id} not found")
            return
        
        runs = tracker.get_experiment_runs(args.experiment_id)
        completed = [r for r in runs if r.status == ExperimentStatus.COMPLETED]
        
        print(f"Experiment: {exp.name} ({exp.experiment_id})")
        print(f"Description: {exp.description}")
        print(f"Type: {exp.experiment_type.value}")
        print(f"Total Runs: {len(runs)}")
        print(f"Completed: {len(completed)}")
        print(f"Failed: {len([r for r in runs if r.status == ExperimentStatus.FAILED])}")
        
        if completed:
            best = max(completed, key=lambda r: max((v[-1][1] for v in r.metrics.values() if v), default=0))
            print(f"\nBest Run: {best.run_id}")
            for key, values in best.metrics.items():
                if values:
                    print(f"  {key}: {values[-1][1]:.4f}")
    
    elif args.command == 'compare':
        # Compare runs
        if not args.runs:
            print("Error: --runs is required")
            return
        
        run_ids = [r.strip() for r in args.runs.split(',')]
        df = tracker.compare_runs(run_ids)
        print(df.to_string())
        
        if args.output:
            df.to_csv(args.output)
            print(f"Saved comparison to {args.output}")
    
    elif args.command == 'export':
        # Export report
        if not args.experiment_id:
            print("Error: --experiment-id is required")
            return
        
        report_path = tracker.generate_report(
            experiment_id=args.experiment_id,
            output_format=args.format,
            output_dir=args.output,
        )
        print(f"Report generated: {report_path}")


if __name__ == '__main__':
    main()
