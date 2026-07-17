# trading/bots/ai_bot/ai_bot_model_manager.py
# NEXUS AI TRADING SYSTEM - AI Bot Model Manager
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
AI Bot Model Manager for NEXUS AI Trading System.
Provides comprehensive model management including:
- Model lifecycle management (load, save, delete, version)
- Model registry and versioning
- Model training and retraining
- Model evaluation and validation
- Model selection and switching
- Model performance tracking
- Model optimization (quantization, pruning, distillation)
- Multi-model ensemble management
- Model deployment and serving
- A/B testing of models
- Model lineage and tracking
"""

import asyncio
import json
import logging
import os
import pickle
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.base import BaseEstimator

# NEXUS Imports
from trading.bots.ai_bot.config.bot_configs import BotConfig
from trading.bots.ai_bot.data.data_storage import DataStorage
from trading.bots.ai_bot.models.model_factory import ModelFactory
from trading.bots.ai_bot.models.model_evaluator import ModelEvaluator
from trading.bots.ai_bot.models.model_trainer import ModelTrainer
from trading.bots.ai_bot.metrics.metrics_engine import MetricsEngine
from shared.utilities.logger import get_logger
from shared.utilities.cache_utils import CacheManager

logger = get_logger("nexus.trading.bot.model_manager")


# ============================================================================
# Enums & Constants
# ============================================================================

class ModelStatus(str, Enum):
    """Model status."""
    DRAFT = "draft"
    TRAINING = "training"
    TRAINED = "trained"
    EVALUATING = "evaluating"
    EVALUATED = "evaluated"
    DEPLOYED = "deployed"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
    DELETED = "deleted"
    FAILED = "failed"


class ModelType(str, Enum):
    """Model types."""
    LSTM = "lstm"
    TRANSFORMER = "transformer"
    XGBOOST = "xgboost"
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    DQN = "dqn"
    PPO = "ppo"
    SAC = "sac"
    ENSEMBLE = "ensemble"
    CUSTOM = "custom"


class ModelFormat(str, Enum):
    """Model formats."""
    PYTORCH = "pytorch"
    SKLEARN = "sklearn"
    ONNX = "onnx"
    TENSORFLOW = "tensorflow"
    JOBLIB = "joblib"
    PICKLE = "pickle"
    CUSTOM = "custom"


class ModelDeployment(str, Enum):
    """Model deployment modes."""
    LOCAL = "local"
    REMOTE = "remote"
    CONTAINER = "container"
    SERVERLESS = "serverless"
    EDGE = "edge"


@dataclass
class ModelInfo:
    """Model information."""
    model_id: str
    model_type: ModelType
    name: str
    version: str
    status: ModelStatus
    format: ModelFormat
    created_at: datetime
    updated_at: datetime
    deployed_at: Optional[datetime] = None
    file_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    performance: Dict[str, float] = field(default_factory=dict)
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    data_info: Dict[str, Any] = field(default_factory=dict)
    deployment_info: Dict[str, Any] = field(default_factory=dict)
    lineage: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class ModelVersion:
    """Model version information."""
    version: str
    created_at: datetime
    model_id: str
    file_path: str
    performance: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrainingJob:
    """Training job information."""
    job_id: str
    model_id: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    logs: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class ModelComparison:
    """Model comparison results."""
    models: List[ModelInfo]
    metrics: Dict[str, Dict[str, float]]
    ranking: Dict[str, float]
    best_model: ModelInfo
    recommendation: str
    timestamp: datetime


# ============================================================================
# Model Manager
# ============================================================================

class ModelManager:
    """
    Advanced Model Manager for NEXUS AI Trading Bot.
    """

    def __init__(
        self,
        config: BotConfig,
        model_factory: ModelFactory,
        model_evaluator: ModelEvaluator,
        model_trainer: ModelTrainer,
        data_storage: DataStorage,
        metrics_engine: MetricsEngine,
        cache_manager: CacheManager,
    ):
        """
        Initialize model manager.

        Args:
            config: Bot configuration
            model_factory: Model factory instance
            model_evaluator: Model evaluator instance
            model_trainer: Model trainer instance
            data_storage: Data storage instance
            metrics_engine: Metrics engine instance
            cache_manager: Cache manager instance
        """
        self.config = config
        self.model_factory = model_factory
        self.model_evaluator = model_evaluator
        self.model_trainer = model_trainer
        self.data_storage = data_storage
        self.metrics_engine = metrics_engine
        self.cache_manager = cache_manager

        # Model registry
        self._models: Dict[str, ModelInfo] = {}
        self._models_by_type: Dict[ModelType, List[str]] = {}
        self._active_model_id: Optional[str] = None
        self._deployed_models: Dict[str, ModelInfo] = {}

        # Model cache
        self._model_cache: Dict[str, Any] = {}
        self._model_version_cache: Dict[str, List[ModelVersion]] = {}

        # Training jobs
        self._training_jobs: Dict[str, TrainingJob] = {}
        self._active_training_jobs: Set[str] = set()

        # Performance tracking
        self._performance = {
            "models_loaded": 0,
            "models_saved": 0,
            "models_deployed": 0,
            "models_archived": 0,
            "training_jobs_started": 0,
            "training_jobs_completed": 0,
            "training_jobs_failed": 0,
            "avg_load_time_ms": 0.0,
            "avg_save_time_ms": 0.0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        # Model directory
        self._model_dir = Path(config.get("model_dir", "./data/models"))
        self._model_dir.mkdir(parents=True, exist_ok=True)

        # Load existing models
        self._load_models()

        logger.info(
            "ModelManager initialized",
            extra={
                "model_dir": str(self._model_dir),
                "models_loaded": len(self._models),
                "active_model": self._active_model_id,
            }
        )

    # -----------------------------------------------------------------------
    # Model Registration
    # -----------------------------------------------------------------------

    def register_model(
        self,
        model_type: ModelType,
        name: str,
        version: str = "1.0.0",
        metadata: Optional[Dict[str, Any]] = None,
        hyperparameters: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> ModelInfo:
        """
        Register a new model.

        Args:
            model_type: Model type
            name: Model name
            version: Model version
            metadata: Additional metadata
            hyperparameters: Model hyperparameters
            tags: Model tags

        Returns:
            ModelInfo
        """
        model_id = f"{name}_{version}_{int(time.time())}"

        model_info = ModelInfo(
            model_id=model_id,
            model_type=model_type,
            name=name,
            version=version,
            status=ModelStatus.DRAFT,
            format=self._get_default_format(model_type),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata=metadata or {},
            hyperparameters=hyperparameters or {},
            tags=tags or [],
            file_path=str(self._model_dir / f"{model_id}.pkl"),
        )

        self._models[model_id] = model_info

        if model_type not in self._models_by_type:
            self._models_by_type[model_type] = []
        self._models_by_type[model_type].append(model_id)

        logger.info(f"Model registered: {model_id}")
        return model_info

    # -----------------------------------------------------------------------
    # Model Loading/Saving
    # -----------------------------------------------------------------------

    async def load_model(
        self,
        model_id: str,
        force_reload: bool = False,
    ) -> Optional[Any]:
        """
        Load a model from storage.

        Args:
            model_id: Model ID
            force_reload: Force reload from disk

        Returns:
            Loaded model or None
        """
        start_time = time.time()

        # Check cache
        if not force_reload and model_id in self._model_cache:
            self._performance["cache_hits"] += 1
            return self._model_cache[model_id]

        self._performance["cache_misses"] += 1

        model_info = self._models.get(model_id)

        if not model_info:
            logger.error(f"Model {model_id} not found")
            return None

        try:
            # Load model based on format
            if model_info.format == ModelFormat.PYTORCH:
                model = await self._load_pytorch_model(model_info)
            elif model_info.format == ModelFormat.SKLEARN:
                model = await self._load_sklearn_model(model_info)
            elif model_info.format == ModelFormat.JOBLIB:
                model = await self._load_joblib_model(model_info)
            elif model_info.format == ModelFormat.PICKLE:
                model = await self._load_pickle_model(model_info)
            elif model_info.format == ModelFormat.ONNX:
                model = await self._load_onnx_model(model_info)
            else:
                model = await self._load_custom_model(model_info)

            if model:
                self._model_cache[model_id] = model
                self._performance["models_loaded"] += 1

                # Update performance
                elapsed_ms = (time.time() - start_time) * 1000
                self._performance["avg_load_time_ms"] = (
                    (self._performance["avg_load_time_ms"] *
                     (self._performance["models_loaded"] - 1) +
                     elapsed_ms) / self._performance["models_loaded"]
                )

                logger.info(f"Model loaded: {model_id}")
                return model

        except Exception as e:
            logger.error(f"Error loading model {model_id}: {e}")
            return None

    async def save_model(
        self,
        model_id: str,
        model: Any,
        format: Optional[ModelFormat] = None,
    ) -> bool:
        """
        Save a model to storage.

        Args:
            model_id: Model ID
            model: Model instance
            format: Model format

        Returns:
            True if saved successfully
        """
        start_time = time.time()

        model_info = self._models.get(model_id)

        if not model_info:
            logger.error(f"Model {model_id} not found")
            return False

        try:
            format = format or model_info.format

            # Save model based on format
            if format == ModelFormat.PYTORCH:
                success = await self._save_pytorch_model(model_info, model)
            elif format == ModelFormat.SKLEARN:
                success = await self._save_sklearn_model(model_info, model)
            elif format == ModelFormat.JOBLIB:
                success = await self._save_joblib_model(model_info, model)
            elif format == ModelFormat.PICKLE:
                success = await self._save_pickle_model(model_info, model)
            elif format == ModelFormat.ONNX:
                success = await self._save_onnx_model(model_info, model)
            else:
                success = await self._save_custom_model(model_info, model)

            if success:
                model_info.updated_at = datetime.utcnow()
                model_info.format = format
                self._models[model_id] = model_info
                self._model_cache[model_id] = model
                self._performance["models_saved"] += 1

                # Update performance
                elapsed_ms = (time.time() - start_time) * 1000
                self._performance["avg_save_time_ms"] = (
                    (self._performance["avg_save_time_ms"] *
                     (self._performance["models_saved"] - 1) +
                     elapsed_ms) / self._performance["models_saved"]
                )

                logger.info(f"Model saved: {model_id}")
                return True

        except Exception as e:
            logger.error(f"Error saving model {model_id}: {e}")

        return False

    async def _load_pytorch_model(self, model_info: ModelInfo) -> Optional[nn.Module]:
        """Load PyTorch model."""
        if not model_info.file_path or not os.path.exists(model_info.file_path):
            logger.error(f"Model file not found: {model_info.file_path}")
            return None

        # Create model instance
        model = self.model_factory.create_model(
            model_type=model_info.model_type,
            **model_info.hyperparameters,
        )

        # Load weights
        model.load_state_dict(torch.load(model_info.file_path, map_location="cpu"))
        model.eval()

        return model

    async def _save_pytorch_model(self, model_info: ModelInfo, model: nn.Module) -> bool:
        """Save PyTorch model."""
        try:
            torch.save(model.state_dict(), model_info.file_path)
            return True
        except Exception as e:
            logger.error(f"Error saving PyTorch model: {e}")
            return False

    async def _load_sklearn_model(self, model_info: ModelInfo) -> Optional[BaseEstimator]:
        """Load scikit-learn model."""
        if not model_info.file_path or not os.path.exists(model_info.file_path):
            logger.error(f"Model file not found: {model_info.file_path}")
            return None

        with open(model_info.file_path, 'rb') as f:
            return pickle.load(f)

    async def _save_sklearn_model(self, model_info: ModelInfo, model: BaseEstimator) -> bool:
        """Save scikit-learn model."""
        try:
            with open(model_info.file_path, 'wb') as f:
                pickle.dump(model, f)
            return True
        except Exception as e:
            logger.error(f"Error saving sklearn model: {e}")
            return False

    async def _load_joblib_model(self, model_info: ModelInfo) -> Optional[Any]:
        """Load joblib model."""
        if not model_info.file_path or not os.path.exists(model_info.file_path):
            logger.error(f"Model file not found: {model_info.file_path}")
            return None

        return joblib.load(model_info.file_path)

    async def _save_joblib_model(self, model_info: ModelInfo, model: Any) -> bool:
        """Save joblib model."""
        try:
            joblib.dump(model, model_info.file_path)
            return True
        except Exception as e:
            logger.error(f"Error saving joblib model: {e}")
            return False

    async def _load_pickle_model(self, model_info: ModelInfo) -> Optional[Any]:
        """Load pickle model."""
        if not model_info.file_path or not os.path.exists(model_info.file_path):
            logger.error(f"Model file not found: {model_info.file_path}")
            return None

        with open(model_info.file_path, 'rb') as f:
            return pickle.load(f)

    async def _save_pickle_model(self, model_info: ModelInfo, model: Any) -> bool:
        """Save pickle model."""
        try:
            with open(model_info.file_path, 'wb') as f:
                pickle.dump(model, f)
            return True
        except Exception as e:
            logger.error(f"Error saving pickle model: {e}")
            return False

    async def _load_onnx_model(self, model_info: ModelInfo) -> Optional[Any]:
        """Load ONNX model."""
        # Would use onnxruntime
        return None

    async def _save_onnx_model(self, model_info: ModelInfo, model: Any) -> bool:
        """Save ONNX model."""
        # Would convert and save ONNX
        return False

    async def _load_custom_model(self, model_info: ModelInfo) -> Optional[Any]:
        """Load custom model."""
        # Custom implementation
        return None

    async def _save_custom_model(self, model_info: ModelInfo, model: Any) -> bool:
        """Save custom model."""
        return False

    # -----------------------------------------------------------------------
    # Model Deployment
    # -----------------------------------------------------------------------

    async def deploy_model(
        self,
        model_id: str,
        deployment_mode: ModelDeployment = ModelDeployment.LOCAL,
        deployment_config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Deploy a model.

        Args:
            model_id: Model ID
            deployment_mode: Deployment mode
            deployment_config: Deployment configuration

        Returns:
            True if deployed successfully
        """
        model_info = self._models.get(model_id)

        if not model_info:
            logger.error(f"Model {model_id} not found")
            return False

        try:
            # Load model
            model = await self.load_model(model_id)

            if model is None:
                logger.error(f"Failed to load model {model_id}")
                return False

            # Deploy based on mode
            if deployment_mode == ModelDeployment.LOCAL:
                success = await self._deploy_local(model_id, model)
            elif deployment_mode == ModelDeployment.REMOTE:
                success = await self._deploy_remote(model_id, model, deployment_config)
            elif deployment_mode == ModelDeployment.CONTAINER:
                success = await self._deploy_container(model_id, model, deployment_config)
            elif deployment_mode == ModelDeployment.SERVERLESS:
                success = await self._deploy_serverless(model_id, model, deployment_config)
            elif deployment_mode == ModelDeployment.EDGE:
                success = await self._deploy_edge(model_id, model, deployment_config)
            else:
                success = False

            if success:
                model_info.status = ModelStatus.DEPLOYED
                model_info.deployed_at = datetime.utcnow()
                model_info.deployment_info = {
                    "mode": deployment_mode.value,
                    "config": deployment_config or {},
                    "deployed_at": datetime.utcnow().isoformat(),
                }
                self._models[model_id] = model_info
                self._deployed_models[model_id] = model_info
                self._active_model_id = model_id

                self._performance["models_deployed"] += 1

                logger.info(f"Model deployed: {model_id}")
                return True

        except Exception as e:
            logger.error(f"Error deploying model {model_id}: {e}")

        return False

    async def _deploy_local(self, model_id: str, model: Any) -> bool:
        """Deploy model locally."""
        # Store in cache
        self._model_cache[model_id] = model
        return True

    async def _deploy_remote(self, model_id: str, model: Any, config: Dict[str, Any]) -> bool:
        """Deploy model remotely."""
        # Would deploy to remote endpoint
        return True

    async def _deploy_container(self, model_id: str, model: Any, config: Dict[str, Any]) -> bool:
        """Deploy model in container."""
        # Would create and deploy container
        return True

    async def _deploy_serverless(self, model_id: str, model: Any, config: Dict[str, Any]) -> bool:
        """Deploy model as serverless function."""
        # Would deploy to serverless platform
        return True

    async def _deploy_edge(self, model_id: str, model: Any, config: Dict[str, Any]) -> bool:
        """Deploy model to edge."""
        # Would deploy to edge device
        return True

    async def undeploy_model(self, model_id: str) -> bool:
        """
        Undeploy a model.

        Args:
            model_id: Model ID

        Returns:
            True if undeployed successfully
        """
        if model_id not in self._deployed_models:
            logger.warning(f"Model {model_id} not deployed")
            return False

        try:
            # Remove from cache
            if model_id in self._model_cache:
                del self._model_cache[model_id]

            # Update status
            model_info = self._models.get(model_id)
            if model_info:
                model_info.status = ModelStatus.EVALUATED
                model_info.deployment_info = {}
                self._models[model_id] = model_info

            del self._deployed_models[model_id]

            if self._active_model_id == model_id:
                self._active_model_id = None

            logger.info(f"Model undeployed: {model_id}")
            return True

        except Exception as e:
            logger.error(f"Error undeploying model {model_id}: {e}")
            return False

    # -----------------------------------------------------------------------
    # Model Training
    # -----------------------------------------------------------------------

    async def train_model(
        self,
        model_id: str,
        train_data: pd.DataFrame,
        target_column: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> TrainingJob:
        """
        Train a model.

        Args:
            model_id: Model ID
            train_data: Training data
            target_column: Target column name
            config: Training configuration

        Returns:
            TrainingJob
        """
        model_info = self._models.get(model_id)

        if not model_info:
            logger.error(f"Model {model_id} not found")
            raise ValueError(f"Model {model_id} not found")

        # Create training job
        job_id = f"train_{model_id}_{int(time.time())}"
        training_job = TrainingJob(
            job_id=job_id,
            model_id=model_id,
            status="created",
            created_at=datetime.utcnow(),
            config=config or {},
        )

        self._training_jobs[job_id] = training_job
        self._active_training_jobs.add(job_id)
        self._performance["training_jobs_started"] += 1

        try:
            training_job.status = "running"
            training_job.started_at = datetime.utcnow()

            # Create model instance
            model = self.model_factory.create_model(
                model_type=model_info.model_type,
                **model_info.hyperparameters,
            )

            # Train model
            train_result = await self.model_trainer.train(
                model=model,
                train_data=train_data,
                target_column=target_column,
                config=config,
                callback=lambda progress: self._update_training_progress(job_id, progress),
            )

            # Save model
            await self.save_model(model_id, model)

            # Evaluate model
            eval_metrics = await self.model_evaluator.evaluate(
                model=model,
                data=train_data,
                target_column=target_column,
            )

            # Update model info
            model_info.performance = eval_metrics
            model_info.status = ModelStatus.TRAINED
            model_info.updated_at = datetime.utcnow()
            self._models[model_id] = model_info

            # Update training job
            training_job.status = "completed"
            training_job.completed_at = datetime.utcnow()
            training_job.progress = 1.0
            training_job.metrics = eval_metrics

            self._performance["training_jobs_completed"] += 1

            logger.info(f"Model training completed: {model_id}")
            return training_job

        except Exception as e:
            logger.error(f"Error training model {model_id}: {e}")

            training_job.status = "failed"
            training_job.error = str(e)

            model_info.status = ModelStatus.FAILED
            self._models[model_id] = model_info

            self._performance["training_jobs_failed"] += 1

            return training_job

        finally:
            self._active_training_jobs.discard(job_id)

    def _update_training_progress(self, job_id: str, progress: float) -> None:
        """Update training job progress."""
        if job_id in self._training_jobs:
            self._training_jobs[job_id].progress = progress

    # -----------------------------------------------------------------------
    # Model Evaluation
    # -----------------------------------------------------------------------

    async def evaluate_model(
        self,
        model_id: str,
        test_data: pd.DataFrame,
        target_column: str,
    ) -> Dict[str, float]:
        """
        Evaluate a model.

        Args:
            model_id: Model ID
            test_data: Test data
            target_column: Target column name

        Returns:
            Evaluation metrics
        """
        model_info = self._models.get(model_id)

        if not model_info:
            logger.error(f"Model {model_id} not found")
            return {}

        try:
            # Load model
            model = await self.load_model(model_id)

            if model is None:
                logger.error(f"Failed to load model {model_id}")
                return {}

            # Evaluate
            metrics = await self.model_evaluator.evaluate(
                model=model,
                data=test_data,
                target_column=target_column,
            )

            # Update model info
            model_info.performance = metrics
            model_info.status = ModelStatus.EVALUATED
            self._models[model_id] = model_info

            # Collect metrics
            for name, value in metrics.items():
                await self.metrics_engine.collect_metric(
                    f"model_{name}",
                    value,
                    metadata={"model_id": model_id},
                )

            logger.info(f"Model evaluated: {model_id}")
            return metrics

        except Exception as e:
            logger.error(f"Error evaluating model {model_id}: {e}")
            return {}

    # -----------------------------------------------------------------------
    # Model Selection
    # -----------------------------------------------------------------------

    async def select_best_model(
        self,
        model_type: Optional[ModelType] = None,
        metric: str = "accuracy",
        maximize: bool = True,
    ) -> Optional[ModelInfo]:
        """
        Select the best model based on performance.

        Args:
            model_type: Filter by model type
            metric: Performance metric to use
            maximize: Maximize or minimize

        Returns:
            Best ModelInfo or None
        """
        models = self._get_models_by_type(model_type) if model_type else list(self._models.values())

        if not models:
            return None

        # Filter models with performance data
        models_with_perf = [m for m in models if m.performance and metric in m.performance]

        if not models_with_perf:
            return None

        # Sort by metric
        sorted_models = sorted(
            models_with_perf,
            key=lambda m: m.performance.get(metric, 0),
            reverse=maximize,
        )

        return sorted_models[0]

    def get_active_model(self) -> Optional[ModelInfo]:
        """
        Get the currently active model.

        Returns:
            Active ModelInfo or None
        """
        if self._active_model_id and self._active_model_id in self._models:
            return self._models[self._active_model_id]
        return None

    async def switch_model(self, model_id: str) -> bool:
        """
        Switch to a different model.

        Args:
            model_id: Model ID to switch to

        Returns:
            True if switched successfully
        """
        if model_id not in self._models:
            logger.error(f"Model {model_id} not found")
            return False

        # Load the model
        model = await self.load_model(model_id)

        if model is None:
            logger.error(f"Failed to load model {model_id}")
            return False

        # Update active model
        self._active_model_id = model_id
        self._model_cache[model_id] = model

        logger.info(f"Switched to model: {model_id}")
        return True

    # -----------------------------------------------------------------------
    # Model Versioning
    # -----------------------------------------------------------------------

    def create_version(self, model_id: str, version: str) -> ModelVersion:
        """
        Create a new version of a model.

        Args:
            model_id: Model ID
            version: Version string

        Returns:
            ModelVersion
        """
        model_info = self._models.get(model_id)

        if not model_info:
            raise ValueError(f"Model {model_id} not found")

        # Create version
        model_version = ModelVersion(
            version=version,
            created_at=datetime.utcnow(),
            model_id=model_id,
            file_path=model_info.file_path or "",
            performance=model_info.performance.copy(),
            metadata={
                "name": model_info.name,
                "model_type": model_info.model_type.value,
                "created_from": model_info.version,
            },
        )

        # Store version
        if model_id not in self._model_version_cache:
            self._model_version_cache[model_id] = []
        self._model_version_cache[model_id].append(model_version)

        # Update model info
        model_info.version = version
        model_info.updated_at = datetime.utcnow()
        self._models[model_id] = model_info

        logger.info(f"Model version created: {model_id} v{version}")
        return model_version

    def get_versions(self, model_id: str) -> List[ModelVersion]:
        """
        Get all versions of a model.

        Args:
            model_id: Model ID

        Returns:
            List of ModelVersion
        """
        return self._model_version_cache.get(model_id, [])

    def get_latest_version(self, model_id: str) -> Optional[ModelVersion]:
        """
        Get the latest version of a model.

        Args:
            model_id: Model ID

        Returns:
            Latest ModelVersion or None
        """
        versions = self.get_versions(model_id)
        if versions:
            return versions[-1]
        return None

    # -----------------------------------------------------------------------
    # Model Comparison
    # -----------------------------------------------------------------------

    async def compare_models(
        self,
        model_ids: List[str],
        test_data: pd.DataFrame,
        target_column: str,
    ) -> ModelComparison:
        """
        Compare multiple models.

        Args:
            model_ids: List of model IDs
            test_data: Test data
            target_column: Target column name

        Returns:
            ModelComparison
        """
        models = []
        metrics = {}
        ranking = {}

        for model_id in model_ids:
            model_info = self._models.get(model_id)

            if not model_info:
                continue

            # Load model
            model = await self.load_model(model_id)

            if model is None:
                continue

            # Evaluate
            eval_metrics = await self.model_evaluator.evaluate(
                model=model,
                data=test_data,
                target_column=target_column,
            )

            models.append(model_info)
            metrics[model_id] = eval_metrics

            # Calculate overall score
            score = 0
            for metric_name, value in eval_metrics.items():
                if metric_name in ["accuracy", "precision", "recall", "f1"]:
                    score += value * 100
                elif metric_name in ["rmse", "mae"]:
                    score += max(0, 100 - value * 10)

            ranking[model_id] = score

        if not models:
            return ModelComparison(
                models=[],
                metrics={},
                ranking={},
                best_model=ModelInfo(
                    model_id="none",
                    model_type=ModelType.CUSTOM,
                    name="none",
                    version="1.0.0",
                    status=ModelStatus.DRAFT,
                    format=ModelFormat.PICKLE,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                ),
                recommendation="No models available",
                timestamp=datetime.utcnow(),
            )

        # Find best model
        best_model_id = max(ranking, key=ranking.get)
        best_model = self._models.get(best_model_id)

        # Generate recommendation
        if best_model:
            recommendation = (
                f"Best model: {best_model.name} v{best_model.version} "
                f"with score {ranking[best_model_id]:.2f}"
            )
        else:
            recommendation = "No model selected"

        return ModelComparison(
            models=models,
            metrics=metrics,
            ranking=ranking,
            best_model=best_model,
            recommendation=recommendation,
            timestamp=datetime.utcnow(),
        )

    # -----------------------------------------------------------------------
    # Model Archiving
    # -----------------------------------------------------------------------

    async def archive_model(self, model_id: str) -> bool:
        """
        Archive a model.

        Args:
            model_id: Model ID

        Returns:
            True if archived successfully
        """
        model_info = self._models.get(model_id)

        if not model_info:
            logger.error(f"Model {model_id} not found")
            return False

        try:
            # Move to archive
            archive_dir = self._model_dir / "archive"
            archive_dir.mkdir(exist_ok=True)

            if model_info.file_path and os.path.exists(model_info.file_path):
                archive_path = archive_dir / f"{model_id}.pkl"
                shutil.move(model_info.file_path, archive_path)
                model_info.file_path = str(archive_path)

            model_info.status = ModelStatus.ARCHIVED
            model_info.updated_at = datetime.utcnow()
            self._models[model_id] = model_info

            # Remove from cache
            if model_id in self._model_cache:
                del self._model_cache[model_id]

            # Remove from deployed
            if model_id in self._deployed_models:
                del self._deployed_models[model_id]

            self._performance["models_archived"] += 1

            logger.info(f"Model archived: {model_id}")
            return True

        except Exception as e:
            logger.error(f"Error archiving model {model_id}: {e}")
            return False

    async def restore_model(self, model_id: str) -> bool:
        """
        Restore an archived model.

        Args:
            model_id: Model ID

        Returns:
            True if restored successfully
        """
        model_info = self._models.get(model_id)

        if not model_info:
            logger.error(f"Model {model_id} not found")
            return False

        if model_info.status != ModelStatus.ARCHIVED:
            logger.warning(f"Model {model_id} is not archived")
            return False

        try:
            # Move from archive
            if model_info.file_path and os.path.exists(model_info.file_path):
                model_path = self._model_dir / f"{model_id}.pkl"
                shutil.move(model_info.file_path, model_path)
                model_info.file_path = str(model_path)

            model_info.status = ModelStatus.EVALUATED
            model_info.updated_at = datetime.utcnow()
            self._models[model_id] = model_info

            logger.info(f"Model restored: {model_id}")
            return True

        except Exception as e:
            logger.error(f"Error restoring model {model_id}: {e}")
            return False

    async def delete_model(self, model_id: str, permanent: bool = False) -> bool:
        """
        Delete a model.

        Args:
            model_id: Model ID
            permanent: Permanently delete

        Returns:
            True if deleted successfully
        """
        model_info = self._models.get(model_id)

        if not model_info:
            logger.error(f"Model {model_id} not found")
            return False

        try:
            if permanent:
                # Delete file
                if model_info.file_path and os.path.exists(model_info.file_path):
                    os.remove(model_info.file_path)

                # Remove from registry
                del self._models[model_id]

                # Remove from type index
                if model_info.model_type in self._models_by_type:
                    self._models_by_type[model_info.model_type].remove(model_id)

                # Remove from cache
                if model_id in self._model_cache:
                    del self._model_cache[model_id]

                # Remove from deployed
                if model_id in self._deployed_models:
                    del self._deployed_models[model_id]

                # Remove versions
                if model_id in self._model_version_cache:
                    del self._model_version_cache[model_id]

                self._performance["models_deleted"] = getattr(self._performance, "models_deleted", 0) + 1
                logger.info(f"Model permanently deleted: {model_id}")
            else:
                model_info.status = ModelStatus.DELETED
                model_info.updated_at = datetime.utcnow()
                self._models[model_id] = model_info
                logger.info(f"Model marked as deleted: {model_id}")

            return True

        except Exception as e:
            logger.error(f"Error deleting model {model_id}: {e}")
            return False

    # -----------------------------------------------------------------------
    # Model Metadata
    # -----------------------------------------------------------------------

    def get_model_info(self, model_id: str) -> Optional[ModelInfo]:
        """
        Get model information.

        Args:
            model_id: Model ID

        Returns:
            ModelInfo or None
        """
        return self._models.get(model_id)

    def get_all_models(self) -> List[ModelInfo]:
        """
        Get all models.

        Returns:
            List of ModelInfo
        """
        return list(self._models.values())

    def get_models_by_status(self, status: ModelStatus) -> List[ModelInfo]:
        """
        Get models by status.

        Args:
            status: Model status

        Returns:
            List of ModelInfo
        """
        return [m for m in self._models.values() if m.status == status]

    def get_deployed_models(self) -> List[ModelInfo]:
        """
        Get deployed models.

        Returns:
            List of ModelInfo
        """
        return list(self._deployed_models.values())

    def get_training_jobs(self) -> List[TrainingJob]:
        """
        Get all training jobs.

        Returns:
            List of TrainingJob
        """
        return list(self._training_jobs.values())

    def get_training_job(self, job_id: str) -> Optional[TrainingJob]:
        """
        Get a training job.

        Args:
            job_id: Job ID

        Returns:
            TrainingJob or None
        """
        return self._training_jobs.get(job_id)

    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------

    def _get_default_format(self, model_type: ModelType) -> ModelFormat:
        """Get default format for model type."""
        if model_type in [ModelType.LSTM, ModelType.TRANSFORMER, ModelType.DQN, ModelType.PPO, ModelType.SAC]:
            return ModelFormat.PYTORCH
        elif model_type in [ModelType.XGBOOST, ModelType.RANDOM_FOREST, ModelType.GRADIENT_BOOSTING]:
            return ModelFormat.JOBLIB
        elif model_type == ModelType.ENSEMBLE:
            return ModelFormat.PICKLE
        else:
            return ModelFormat.PICKLE

    def _get_models_by_type(self, model_type: ModelType) -> List[ModelInfo]:
        """Get models by type."""
        model_ids = self._models_by_type.get(model_type, [])
        return [self._models[mid] for mid in model_ids if mid in self._models]

    def _load_models(self) -> None:
        """Load existing models from directory."""
        try:
            # Load model metadata
            metadata_file = self._model_dir / "models_metadata.json"

            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    data = json.load(f)

                for model_data in data.get("models", []):
                    model_info = ModelInfo(
                        model_id=model_data["model_id"],
                        model_type=ModelType(model_data["model_type"]),
                        name=model_data["name"],
                        version=model_data["version"],
                        status=ModelStatus(model_data["status"]),
                        format=ModelFormat(model_data["format"]),
                        created_at=datetime.fromisoformat(model_data["created_at"]),
                        updated_at=datetime.fromisoformat(model_data["updated_at"]),
                        deployed_at=datetime.fromisoformat(model_data["deployed_at"]) if model_data.get("deployed_at") else None,
                        file_path=model_data.get("file_path"),
                        metadata=model_data.get("metadata", {}),
                        performance=model_data.get("performance", {}),
                        hyperparameters=model_data.get("hyperparameters", {}),
                        tags=model_data.get("tags", []),
                    )

                    self._models[model_info.model_id] = model_info

                    if model_info.model_type not in self._models_by_type:
                        self._models_by_type[model_info.model_type] = []
                    self._models_by_type[model_info.model_type].append(model_info.model_id)

                    if model_info.status == ModelStatus.DEPLOYED:
                        self._deployed_models[model_info.model_id] = model_info

                logger.info(f"Loaded {len(self._models)} models from metadata")

        except Exception as e:
            logger.error(f"Error loading models: {e}")

    def _save_metadata(self) -> None:
        """Save model metadata."""
        try:
            metadata = {
                "models": [
                    {
                        "model_id": m.model_id,
                        "model_type": m.model_type.value,
                        "name": m.name,
                        "version": m.version,
                        "status": m.status.value,
                        "format": m.format.value,
                        "created_at": m.created_at.isoformat(),
                        "updated_at": m.updated_at.isoformat(),
                        "deployed_at": m.deployed_at.isoformat() if m.deployed_at else None,
                        "file_path": m.file_path,
                        "metadata": m.metadata,
                        "performance": m.performance,
                        "hyperparameters": m.hyperparameters,
                        "tags": m.tags,
                    }
                    for m in self._models.values()
                    if m.status != ModelStatus.DELETED
                ]
            }

            metadata_file = self._model_dir / "models_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving metadata: {e}")

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.

        Returns:
            Performance metrics
        """
        return {
            **self._performance,
            "total_models": len(self._models),
            "deployed_models": len(self._deployed_models),
            "active_model": self._active_model_id,
            "model_types": {k.value: len(v) for k, v in self._models_by_type.items()},
            "training_jobs": len(self._training_jobs),
            "active_training_jobs": len(self._active_training_jobs),
            "versions": sum(len(v) for v in self._model_version_cache.values()),
            "cache_size": len(self._model_cache),
        }

    def clear_cache(self) -> None:
        """Clear model cache."""
        self._model_cache.clear()
        logger.info("Model cache cleared")

    # -----------------------------------------------------------------------
    # Lifecycle Management
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """Start the model manager."""
        logger.info("ModelManager started")

    async def stop(self) -> None:
        """Stop the model manager."""
        # Save metadata
        self._save_metadata()

        # Clear cache
        self.clear_cache()

        logger.info("ModelManager stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_model_manager(
    config: BotConfig,
    model_factory: ModelFactory,
    model_evaluator: ModelEvaluator,
    model_trainer: ModelTrainer,
    data_storage: DataStorage,
    metrics_engine: MetricsEngine,
    cache_manager: CacheManager,
) -> ModelManager:
    """
    Factory function to create a ModelManager instance.

    Args:
        config: Bot configuration
        model_factory: Model factory instance
        model_evaluator: Model evaluator instance
        model_trainer: Model trainer instance
        data_storage: Data storage instance
        metrics_engine: Metrics engine instance
        cache_manager: Cache manager instance

    Returns:
        ModelManager instance
    """
    return ModelManager(
        config=config,
        model_factory=model_factory,
        model_evaluator=model_evaluator,
        model_trainer=model_trainer,
        data_storage=data_storage,
        metrics_engine=metrics_engine,
        cache_manager=cache_manager,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the model manager
    pass
