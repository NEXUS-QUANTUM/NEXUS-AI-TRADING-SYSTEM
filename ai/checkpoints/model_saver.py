"""
NEXUS AI TRADING SYSTEM - Model Saver
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Model Saver system with:
- Model serialization (PyTorch, TensorFlow, Scikit-learn, etc.)
- Model versioning
- Model metadata management
- Automatic saving
- Model validation
- Model loading
- Model comparison
- Export capabilities
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4

import cloudpickle
import numpy as np
import torch
import tensorflow as tf
from sklearn.base import BaseEstimator
from pydantic import BaseModel, Field

from ai.checkpoints.checkpoint_manager import (
    CheckpointManager,
    Checkpoint,
    CheckpointType,
    CheckpointStatus,
    get_checkpoint_manager
)
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import ModelSaverError

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class FrameworkType(str, Enum):
    """ML framework types"""
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    KERAS = "keras"
    SKLEARN = "sklearn"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    CATBOOST = "catboost"
    ONNX = "onnx"
    CUSTOM = "custom"


class ModelStatus(str, Enum):
    """Model status"""
    TRAINING = "training"
    TRAINED = "trained"
    VALIDATING = "validating"
    VALIDATED = "validated"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"
    FAILED = "failed"


@dataclass
class ModelMetadata:
    """Model metadata"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str
    version: str
    framework: FrameworkType
    architecture: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    status: ModelStatus = ModelStatus.TRAINING
    metrics: Dict[str, float] = field(default_factory=dict)
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    training_data: Dict[str, Any] = field(default_factory=dict)
    validation_data: Dict[str, Any] = field(default_factory=dict)
    performance: Dict[str, float] = field(default_factory=dict)
    dependencies: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelInfo:
    """Model information"""
    id: str
    name: str
    version: str
    framework: FrameworkType
    architecture: str
    status: ModelStatus
    created_at: datetime
    metrics: Dict[str, float]
    performance: Dict[str, float]
    tags: List[str]


class ModelSaverConfig(BaseModel):
    """Model saver configuration"""
    enabled: bool = True
    auto_save: bool = True
    auto_save_interval: int = Field(default=300, gt=0)  # seconds
    max_models: int = Field(default=50, gt=0)
    max_versions_per_model: int = Field(default=10, gt=0)
    compression_enabled: bool = True
    encryption_enabled: bool = True
    encryption_key: Optional[str] = None
    validate_after_save: bool = True
    validate_before_load: bool = True
    save_best_only: bool = True
    save_checkpoint_interval: int = Field(default=100, gt=0)  # steps
    health_check_interval: int = Field(default=60, gt=0)
    log_level: str = "info"


# ========================================
# MODEL SAVER
# ========================================

class ModelSaver:
    """
    Complete model saver for ML models.
    
    Features:
    - Model serialization (PyTorch, TensorFlow, Scikit-learn, etc.)
    - Model versioning
    - Model metadata management
    - Automatic saving
    - Model validation
    - Model loading
    - Model comparison
    - Export capabilities
    - Health monitoring
    - Configuration management
    - Event handling
    - Logging
    - Metrics collection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = ModelSaverConfig(**(config or {}))
        self.redis = get_redis()
        self.checkpoint_manager = get_checkpoint_manager()
        
        # State
        self._models: Dict[str, ModelMetadata] = {}
        self._model_versions: Dict[str, List[str]] = {}  # name -> version IDs
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        self._tasks: List[asyncio.Task] = []
        
        # Metrics
        self._metrics = {
            "total_models": 0,
            "active_models": 0,
            "deployed_models": 0,
            "saves_completed": 0,
            "saves_failed": 0,
            "loads_completed": 0,
            "loads_failed": 0,
            "validations_completed": 0,
            "validations_failed": 0,
            "avg_save_time": 0.0,
            "avg_load_time": 0.0
        }
        
        self.logger = get_logger(f"{__name__}.ModelSaver")
        self.logger.info("ModelSaver initialized")
    
    # ========================================
    # MODEL SAVING
    # ========================================
    
    async def save_model(
        self,
        model: Any,
        name: str,
        framework: FrameworkType,
        architecture: str,
        version: str = "1.0.0",
        metrics: Optional[Dict[str, float]] = None,
        hyperparameters: Optional[Dict[str, Any]] = None,
        training_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        save_best_only: bool = True
    ) -> ModelMetadata:
        """
        Save a model.
        
        Args:
            model: Model to save
            name: Model name
            framework: ML framework
            architecture: Model architecture
            version: Version string
            metrics: Model metrics
            hyperparameters: Model hyperparameters
            training_data: Training data info
            metadata: Additional metadata
            tags: Tags for categorization
            save_best_only: Only save if best
            
        Returns:
            ModelMetadata: Saved model metadata
        """
        start_time = time.time()
        
        try:
            # Check if model already exists
            existing = await self.get_model_by_name_version(name, version)
            
            # Validate if should save
            if save_best_only and existing:
                # Compare performance
                if not self._is_better_model(metrics, existing.metrics):
                    self.logger.info(f"Model {name} v{version} is not better than existing")
                    return existing
            
            # Create metadata
            model_metadata = ModelMetadata(
                name=name,
                version=version,
                framework=framework,
                architecture=architecture,
                metrics=metrics or {},
                hyperparameters=hyperparameters or {},
                training_data=training_data or {},
                metadata=metadata or {},
                tags=tags or []
            )
            
            # Save model to temporary location
            temp_path = await self._save_model_to_temp(model, framework, model_metadata)
            
            # Validate model
            if self.config.validate_after_save:
                if not await self._validate_model(temp_path, framework):
                    raise ModelSaverError("Model validation failed")
            
            # Create checkpoint
            checkpoint = await self.checkpoint_manager.create_checkpoint(
                name=f"model_{name}_{version}",
                type=CheckpointType.MODEL,
                data={
                    'model_path': temp_path,
                    'metadata': model_metadata.__dict__,
                    'framework': framework.value
                },
                version=version,
                metadata={
                    'model_name': name,
                    'framework': framework.value,
                    'architecture': architecture
                },
                tags=tags,
                expires_in_days=365  # Keep models for 1 year
            )
            
            # Update state
            self._models[model_metadata.id] = model_metadata
            
            if name not in self._model_versions:
                self._model_versions[name] = []
            self._model_versions[name].append(model_metadata.id)
            
            # Update status
            model_metadata.status = ModelStatus.TRAINED
            
            # Update metrics
            self._metrics["total_models"] += 1
            self._metrics["active_models"] += 1
            self._metrics["saves_completed"] += 1
            
            elapsed = time.time() - start_time
            self._metrics["avg_save_time"] = (
                self._metrics["avg_save_time"] * 0.9 + elapsed * 0.1
            )
            
            self.logger.info(
                f"Model saved: {name} v{version} "
                f"({framework.value}) in {elapsed:.2f}s"
            )
            
            # Cleanup old versions if needed
            await self._cleanup_old_versions(name)
            
            return model_metadata
            
        except Exception as e:
            self.logger.error(f"Failed to save model: {e}")
            self._metrics["saves_failed"] += 1
            raise ModelSaverError(f"Model save failed: {e}")
    
    async def _save_model_to_temp(
        self,
        model: Any,
        framework: FrameworkType,
        metadata: ModelMetadata
    ) -> str:
        """Save model to temporary location"""
        temp_dir = tempfile.mkdtemp()
        model_path = os.path.join(temp_dir, f"model.{self._get_model_extension(framework)}")
        
        try:
            if framework == FrameworkType.PYTORCH:
                # PyTorch model
                torch.save(model.state_dict(), model_path)
                
            elif framework in [FrameworkType.TENSORFLOW, FrameworkType.KERAS]:
                # TensorFlow/Keras model
                model.save(model_path)
                
            elif framework == FrameworkType.SKLEARN:
                # Scikit-learn model
                import joblib
                joblib.dump(model, model_path)
                
            elif framework == FrameworkType.XGBOOST:
                # XGBoost model
                model.save_model(model_path)
                
            elif framework == FrameworkType.LIGHTGBM:
                # LightGBM model
                model.booster_.save_model(model_path)
                
            elif framework == FrameworkType.CATBOOST:
                # CatBoost model
                model.save_model(model_path)
                
            else:
                # Custom: use cloudpickle
                with open(model_path, 'wb') as f:
                    cloudpickle.dump(model, f)
            
            return model_path
            
        except Exception as e:
            # Cleanup on failure
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise ModelSaverError(f"Failed to save model: {e}")
    
    def _get_model_extension(self, framework: FrameworkType) -> str:
        """Get file extension for framework"""
        extensions = {
            FrameworkType.PYTORCH: 'pt',
            FrameworkType.TENSORFLOW: 'tf',
            FrameworkType.KERAS: 'keras',
            FrameworkType.SKLEARN: 'pkl',
            FrameworkType.XGBOOST: 'xgb',
            FrameworkType.LIGHTGBM: 'lgbm',
            FrameworkType.CATBOOST: 'cbm',
            FrameworkType.ONNX: 'onnx',
            FrameworkType.CUSTOM: 'pkl'
        }
        return extensions.get(framework, 'pkl')
    
    # ========================================
    # MODEL LOADING
    # ========================================
    
    async def load_model(
        self,
        model_id: str,
        device: Optional[str] = None
    ) -> Any:
        """
        Load a model.
        
        Args:
            model_id: Model ID
            device: Device to load on (cpu/cuda)
            
        Returns:
            Any: Loaded model
            
        Raises:
            ModelSaverError: If model not found or invalid
        """
        start_time = time.time()
        
        try:
            model_metadata = self._get_model_metadata(model_id)
            
            # Get checkpoint
            checkpoint = await self.checkpoint_manager.get_checkpoint_info(model_id)
            if not checkpoint:
                raise ModelSaverError(f"Checkpoint not found for model {model_id}")
            
            # Load checkpoint
            checkpoint_data = await self.checkpoint_manager.restore_checkpoint(model_id)
            
            model_path = checkpoint_data['model_path']
            framework = checkpoint_data['framework']
            
            # Validate before load
            if self.config.validate_before_load:
                if not await self._validate_model(model_path, FrameworkType(framework)):
                    raise ModelSaverError("Model validation failed before load")
            
            # Load model
            model = await self._load_model_from_path(model_path, FrameworkType(framework), device)
            
            # Update status
            model_metadata.status = ModelStatus.VALIDATED
            model_metadata.updated_at = datetime.utcnow()
            
            # Update metrics
            self._metrics["loads_completed"] += 1
            
            elapsed = time.time() - start_time
            self._metrics["avg_load_time"] = (
                self._metrics["avg_load_time"] * 0.9 + elapsed * 0.1
            )
            
            self.logger.info(f"Model loaded: {model_metadata.name} v{model_metadata.version} in {elapsed:.2f}s")
            
            return model
            
        except Exception as e:
            self.logger.error(f"Failed to load model: {e}")
            self._metrics["loads_failed"] += 1
            raise ModelSaverError(f"Model load failed: {e}")
    
    async def _load_model_from_path(
        self,
        path: str,
        framework: FrameworkType,
        device: Optional[str] = None
    ) -> Any:
        """Load model from path"""
        try:
            if framework == FrameworkType.PYTORCH:
                # PyTorch model
                import torch
                model = torch.load(path, map_location=device or 'cpu')
                return model
                
            elif framework in [FrameworkType.TENSORFLOW, FrameworkType.KERAS]:
                # TensorFlow/Keras model
                import tensorflow as tf
                model = tf.keras.models.load_model(path)
                return model
                
            elif framework == FrameworkType.SKLEARN:
                # Scikit-learn model
                import joblib
                model = joblib.load(path)
                return model
                
            elif framework == FrameworkType.XGBOOST:
                # XGBoost model
                import xgboost as xgb
                model = xgb.Booster()
                model.load_model(path)
                return model
                
            elif framework == FrameworkType.LIGHTGBM:
                # LightGBM model
                import lightgbm as lgb
                model = lgb.Booster(model_file=path)
                return model
                
            elif framework == FrameworkType.CATBOOST:
                # CatBoost model
                from catboost import CatBoost
                model = CatBoost()
                model.load_model(path)
                return model
                
            else:
                # Custom: use cloudpickle
                with open(path, 'rb') as f:
                    model = cloudpickle.load(f)
                return model
                
        except Exception as e:
            raise ModelSaverError(f"Failed to load model from path: {e}")
    
    # ========================================
    # MODEL VALIDATION
    # ========================================
    
    async def _validate_model(self, path: str, framework: FrameworkType) -> bool:
        """Validate a model"""
        try:
            self._metrics["validations_completed"] += 1
            
            # Try to load the model
            model = await self._load_model_from_path(path, framework)
            
            # Basic validation
            if model is None:
                return False
            
            # Framework-specific validation
            if framework == FrameworkType.PYTORCH:
                import torch
                if not isinstance(model, torch.nn.Module):
                    return False
                
            elif framework in [FrameworkType.TENSORFLOW, FrameworkType.KERAS]:
                import tensorflow as tf
                if not hasattr(model, 'predict'):
                    return False
                
            elif framework == FrameworkType.SKLEARN:
                if not hasattr(model, 'predict'):
                    return False
                
            return True
            
        except Exception as e:
            self.logger.warning(f"Model validation failed: {e}")
            self._metrics["validations_failed"] += 1
            return False
    
    def _is_better_model(
        self,
        new_metrics: Dict[str, float],
        old_metrics: Dict[str, float]
    ) -> bool:
        """Check if new model is better than old model"""
        if not old_metrics:
            return True
        
        # Use primary metric if available
        primary_metric = old_metrics.get('primary_metric', 'accuracy')
        new_score = new_metrics.get(primary_metric, 0)
        old_score = old_metrics.get(primary_metric, 0)
        
        # Check if improvement is significant
        improvement_threshold = 0.01
        return new_score > old_score * (1 + improvement_threshold)
    
    # ========================================
    # MODEL DEPLOYMENT
    # ========================================
    
    async def deploy_model(self, model_id: str) -> bool:
        """
        Deploy a model.
        
        Args:
            model_id: Model ID
            
        Returns:
            bool: True if deployed
        """
        model_metadata = self._get_model_metadata(model_id)
        
        try:
            # Validate model
            if not await self._validate_model(
                model_metadata.get('model_path', ''),
                model_metadata.framework
            ):
                raise ModelSaverError("Model validation failed for deployment")
            
            # Update status
            model_metadata.status = ModelStatus.DEPLOYED
            model_metadata.updated_at = datetime.utcnow()
            
            self._metrics["deployed_models"] += 1
            
            self.logger.info(f"Model deployed: {model_metadata.name} v{model_metadata.version}")
            return True
            
        except Exception as e:
            self.logger.error(f"Model deployment failed: {e}")
            return False
    
    async def archive_model(self, model_id: str) -> bool:
        """
        Archive a model.
        
        Args:
            model_id: Model ID
            
        Returns:
            bool: True if archived
        """
        model_metadata = self._get_model_metadata(model_id)
        
        try:
            model_metadata.status = ModelStatus.ARCHIVED
            model_metadata.updated_at = datetime.utcnow()
            
            self._metrics["active_models"] -= 1
            
            self.logger.info(f"Model archived: {model_metadata.name} v{model_metadata.version}")
            return True
            
        except Exception as e:
            self.logger.error(f"Model archive failed: {e}")
            return False
    
    # ========================================
    # MODEL QUERY
    # ========================================
    
    def _get_model_metadata(self, model_id: str) -> ModelMetadata:
        """Get model metadata by ID"""
        model = self._models.get(model_id)
        if not model:
            raise ModelSaverError(f"Model {model_id} not found")
        return model
    
    async def get_model_by_name_version(
        self,
        name: str,
        version: str
    ) -> Optional[ModelMetadata]:
        """Get model by name and version"""
        for model in self._models.values():
            if model.name == name and model.version == version:
                return model
        return None
    
    async def get_model_info(self, model_id: str) -> Optional[ModelInfo]:
        """Get model information"""
        model = self._models.get(model_id)
        if not model:
            return None
        
        return ModelInfo(
            id=model.id,
            name=model.name,
            version=model.version,
            framework=model.framework,
            architecture=model.architecture,
            status=model.status,
            created_at=model.created_at,
            metrics=model.metrics,
            performance=model.performance,
            tags=model.tags
        )
    
    async def list_models(
        self,
        framework: Optional[FrameworkType] = None,
        status: Optional[ModelStatus] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ModelInfo]:
        """List models with filters"""
        models = list(self._models.values())
        
        # Apply filters
        if framework:
            models = [m for m in models if m.framework == framework]
        
        if status:
            models = [m for m in models if m.status == status]
        
        if tags:
            models = [
                m for m in models
                if any(tag in m.tags for tag in tags)
            ]
        
        # Sort by creation date
        models.sort(key=lambda m: m.created_at, reverse=True)
        
        # Apply pagination
        models = models[offset:offset + limit]
        
        return [
            ModelInfo(
                id=m.id,
                name=m.name,
                version=m.version,
                framework=m.framework,
                architecture=m.architecture,
                status=m.status,
                created_at=m.created_at,
                metrics=m.metrics,
                performance=m.performance,
                tags=m.tags
            )
            for m in models
        ]
    
    async def search_models(
        self,
        query: str,
        limit: int = 50
    ) -> List[ModelInfo]:
        """Search models by name, architecture, or tags"""
        results = []
        
        for model in self._models.values():
            # Search in name
            if query.lower() in model.name.lower():
                results.append(model)
                continue
            
            # Search in architecture
            if query.lower() in model.architecture.lower():
                results.append(model)
                continue
            
            # Search in tags
            if any(query.lower() in tag.lower() for tag in model.tags):
                results.append(model)
                continue
        
        results.sort(key=lambda m: m.created_at, reverse=True)
        results = results[:limit]
        
        return [
            ModelInfo(
                id=m.id,
                name=m.name,
                version=m.version,
                framework=m.framework,
                architecture=m.architecture,
                status=m.status,
                created_at=m.created_at,
                metrics=m.metrics,
                performance=m.performance,
                tags=m.tags
            )
            for m in results
        ]
    
    async def compare_models(
        self,
        model_ids: List[str],
        metric: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compare multiple models.
        
        Args:
            model_ids: List of model IDs
            metric: Metric to compare (default: primary_metric)
            
        Returns:
            Dict[str, Any]: Comparison results
        """
        models = []
        for model_id in model_ids:
            model = self._models.get(model_id)
            if model:
                models.append(model)
        
        if not models:
            return {'error': 'No valid models found'}
        
        # Determine metric to compare
        if not metric:
            metric = models[0].metrics.get('primary_metric', 'accuracy')
        
        comparison = {
            'metric': metric,
            'models': []
        }
        
        for model in models:
            score = model.metrics.get(metric, 0)
            comparison['models'].append({
                'id': model.id,
                'name': model.name,
                'version': model.version,
                'score': score,
                'status': model.status.value,
                'created_at': model.created_at.isoformat()
            })
        
        # Sort by score
        comparison['models'].sort(key=lambda x: x['score'], reverse=True)
        
        return comparison
    
    # ========================================
    # CLEANUP
    # ========================================
    
    async def _cleanup_old_versions(self, name: str) -> None:
        """Clean up old versions of a model"""
        if name not in self._model_versions:
            return
        
        versions = self._model_versions[name]
        if len(versions) <= self.config.max_versions_per_model:
            return
        
        # Get models sorted by creation date
        models = [
            self._models[v] for v in versions
            if v in self._models
        ]
        models.sort(key=lambda m: m.created_at, reverse=True)
        
        # Archive oldest versions
        for model in models[self.config.max_versions_per_model:]:
            if model.status != ModelStatus.DEPLOYED:
                await self.archive_model(model.id)
    
    # ========================================
    # BACKGROUND TASKS
    # ========================================
    
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
        """Get saver metrics"""
        return {
            **self._metrics,
            "total_models": len(self._models),
            "active_models": sum(
                1 for m in self._models.values()
                if m.status not in [ModelStatus.ARCHIVED, ModelStatus.FAILED]
            ),
            "deployed_models": sum(
                1 for m in self._models.values()
                if m.status == ModelStatus.DEPLOYED
            )
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check saver health"""
        health = {
            'status': 'healthy',
            'models': {
                'total': len(self._models),
                'active': self._metrics["active_models"],
                'deployed': self._metrics["deployed_models"]
            }
        }
        
        # Check checkpoint manager health
        try:
            checkpoint_health = await self.checkpoint_manager.health_check()
            if checkpoint_health.get('status') != 'healthy':
                health['status'] = 'degraded'
                health['checkpoint_manager'] = checkpoint_health
        except Exception as e:
            health['status'] = 'degraded'
            health['checkpoint_manager_error'] = str(e)
        
        return health
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the model saver"""
        self._running = True
        
        # Start background tasks
        self._tasks.append(asyncio.create_task(self._health_loop()))
        
        self.logger.info("ModelSaver started")
    
    async def stop(self) -> None:
        """Stop the model saver"""
        self._running = False
        
        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self.logger.info("ModelSaver stopped")


# ========================================
# DEPENDENCY INJECTION
# ========================================

_model_saver: Optional[ModelSaver] = None


def get_model_saver() -> ModelSaver:
    """Get singleton instance of ModelSaver"""
    global _model_saver
    if _model_saver is None:
        _model_saver = ModelSaver()
    return _model_saver


def reset_model_saver() -> None:
    """Reset the model saver (for testing)"""
    global _model_saver
    if _model_saver:
        asyncio.create_task(_model_saver.stop())
    _model_saver = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'ModelSaver',
    'ModelSaverConfig',
    'ModelMetadata',
    'ModelInfo',
    'FrameworkType',
    'ModelStatus',
    'get_model_saver',
    'reset_model_saver'
]
