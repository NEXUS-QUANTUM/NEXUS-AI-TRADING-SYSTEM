"""
NEXUS AI TRADING SYSTEM - Model Registry
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced model registry with versioning, tagging, lifecycle management,
and distributed coordination support.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import aiofiles
import yaml
from prometheus_client import Counter, Gauge

from shared.utilities.logger import get_logger
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
MODEL_REGISTRY_COUNT = Gauge(
    "nexus_model_registry_count",
    "Number of models in registry",
    ["status"],
)
MODEL_VERSION_COUNT = Gauge(
    "nexus_model_version_count",
    "Number of versions for models",
    ["model_type"],
)


class ModelStatus(Enum):
    """Model lifecycle status."""

    DRAFT = "draft"
    STAGING = "staging"
    PRODUCTION = "production"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
    FAILED = "failed"


class ModelStage(Enum):
    """Deployment stages."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    CANARY = "canary"
    PRODUCTION = "production"
    ROLLBACK = "rollback"


@dataclass
class ModelVersion:
    """Model version information."""

    version: str
    created_at: datetime
    status: ModelStatus
    stage: ModelStage
    model_path: str
    config: Dict[str, Any]
    metrics: Dict[str, float]
    tags: List[str] = field(default_factory=list)
    description: str = ""
    deployed_at: Optional[datetime] = None
    deployment_id: Optional[str] = None
    commit_hash: Optional[str] = None
    parent_version: Optional[str] = None
    checksum: str = ""
    size_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "stage": self.stage.value,
            "model_path": self.model_path,
            "config": self.config,
            "metrics": self.metrics,
            "tags": self.tags,
            "description": self.description,
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
            "deployment_id": self.deployment_id,
            "commit_hash": self.commit_hash,
            "parent_version": self.parent_version,
            "checksum": self.checksum,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelVersion":
        """Create from dictionary."""
        return cls(
            version=data["version"],
            created_at=datetime.fromisoformat(data["created_at"]),
            status=ModelStatus(data["status"]),
            stage=ModelStage(data["stage"]),
            model_path=data["model_path"],
            config=data.get("config", {}),
            metrics=data.get("metrics", {}),
            tags=data.get("tags", []),
            description=data.get("description", ""),
            deployed_at=datetime.fromisoformat(data["deployed_at"]) if data.get("deployed_at") else None,
            deployment_id=data.get("deployment_id"),
            commit_hash=data.get("commit_hash"),
            parent_version=data.get("parent_version"),
            checksum=data.get("checksum", ""),
            size_bytes=data.get("size_bytes", 0),
        )


@dataclass
class ModelInfo:
    """Complete model information."""

    model_id: str
    model_type: str
    name: str
    created_at: datetime
    updated_at: datetime
    versions: Dict[str, ModelVersion]
    current_version: Optional[str] = None
    production_version: Optional[str] = None
    staging_version: Optional[str] = None
    owner: str = ""
    team: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_id": self.model_id,
            "model_type": self.model_type,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "versions": {k: v.to_dict() for k, v in self.versions.items()},
            "current_version": self.current_version,
            "production_version": self.production_version,
            "staging_version": self.staging_version,
            "owner": self.owner,
            "team": self.team,
            "description": self.description,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelInfo":
        """Create from dictionary."""
        return cls(
            model_id=data["model_id"],
            model_type=data["model_type"],
            name=data["name"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            versions={
                k: ModelVersion.from_dict(v)
                for k, v in data.get("versions", {}).items()
            },
            current_version=data.get("current_version"),
            production_version=data.get("production_version"),
            staging_version=data.get("staging_version"),
            owner=data.get("owner", ""),
            team=data.get("team", ""),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


class ModelRegistry:
    """
    Advanced model registry with versioning and lifecycle management.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_manager: Optional[CacheManager] = None,
        storage_path: Optional[Union[str, Path]] = None,
    ):
        """
        Initialize the model registry.

        Args:
            config: Configuration dictionary
            cache_manager: Cache manager instance
            storage_path: Path to persistent storage
        """
        self.config = config or {}
        self.cache_manager = cache_manager or CacheManager()
        self._lock = asyncio.Lock()
        self._registry: Dict[str, ModelInfo] = {}
        self._model_cache: Dict[str, Dict] = {}
        self._storage_path = Path(storage_path) if storage_path else Path("./registry")
        self._initialized = False

        # Load configuration
        self.registry_config = self.config.get("registry", {})
        self.max_versions = self.registry_config.get("max_versions", 10)
        self.auto_archive_days = self.registry_config.get("auto_archive_days", 30)
        self.storage_enabled = self.registry_config.get("storage_enabled", True)

        # Create storage directory
        if self.storage_enabled:
            self._storage_path.mkdir(parents=True, exist_ok=True)

        logger.info("ModelRegistry initialized with config: %s", config)

    async def initialize(self):
        """Initialize the registry with stored data."""
        if self._initialized:
            return

        async with self._lock:
            if self.storage_enabled:
                await self._load_from_storage()

            self._initialized = True
            self._update_metrics()

        logger.info("ModelRegistry initialized")

    async def register_model(
        self,
        model_id: str,
        model_type: str,
        name: str,
        version: str,
        model_path: Union[str, Path],
        config: Dict[str, Any],
        metrics: Dict[str, float],
        description: str = "",
        tags: Optional[List[str]] = None,
        status: Union[ModelStatus, str] = ModelStatus.DRAFT,
        stage: Union[ModelStage, str] = ModelStage.DEVELOPMENT,
        owner: str = "",
        team: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        commit_hash: Optional[str] = None,
        parent_version: Optional[str] = None,
        checksum: Optional[str] = None,
        size_bytes: Optional[int] = None,
    ) -> ModelInfo:
        """
        Register a new model version.

        Args:
            model_id: Model identifier
            model_type: Type of model
            name: Model name
            version: Version string
            model_path: Path to model file
            config: Model configuration
            metrics: Model metrics
            description: Model description
            tags: Model tags
            status: Model status
            stage: Deployment stage
            owner: Model owner
            team: Responsible team
            metadata: Additional metadata
            commit_hash: Git commit hash
            parent_version: Parent version
            checksum: Model checksum
            size_bytes: Model size in bytes

        Returns:
            Registered model info
        """
        if isinstance(status, str):
            status = ModelStatus(status)
        if isinstance(stage, str):
            stage = ModelStage(stage)

        # Parse model path
        model_path = Path(model_path)

        # Create version info
        version_info = ModelVersion(
            version=version,
            created_at=datetime.utcnow(),
            status=status,
            stage=stage,
            model_path=str(model_path),
            config=config,
            metrics=metrics,
            tags=tags or [],
            description=description,
            commit_hash=commit_hash,
            parent_version=parent_version,
            checksum=checksum or "",
            size_bytes=size_bytes or 0,
        )

        async with self._lock:
            # Get existing model or create new
            if model_id in self._registry:
                model_info = self._registry[model_id]
                model_info.updated_at = datetime.utcnow()
                model_info.versions[version] = version_info

                # Check version limit
                if len(model_info.versions) > self.max_versions:
                    await self._archive_old_versions(model_info)

                # Update current version
                if status == ModelStatus.PRODUCTION:
                    model_info.production_version = version
                    model_info.current_version = version

                if stage == ModelStage.STAGING:
                    model_info.staging_version = version

            else:
                model_info = ModelInfo(
                    model_id=model_id,
                    model_type=model_type,
                    name=name,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    versions={version: version_info},
                    current_version=version if status == ModelStatus.PRODUCTION else None,
                    production_version=version if status == ModelStatus.PRODUCTION else None,
                    staging_version=version if stage == ModelStage.STAGING else None,
                    owner=owner,
                    team=team,
                    description=description,
                    tags=tags or [],
                    metadata=metadata or {},
                )

            self._registry[model_id] = model_info

            # Cache model
            self._model_cache[model_id] = {
                "version": version,
                "info": model_info.to_dict(),
            }

            # Persist
            if self.storage_enabled:
                await self._save_to_storage(model_id)

            self._update_metrics()

        logger.info(
            f"Registered model {model_id} version {version} "
            f"(status: {status.value}, stage: {stage.value})"
        )

        return model_info

    async def update_model_status(
        self,
        model_id: str,
        version: str,
        status: Union[ModelStatus, str],
    ) -> ModelInfo:
        """
        Update model status.

        Args:
            model_id: Model identifier
            version: Version to update
            status: New status

        Returns:
            Updated model info
        """
        if isinstance(status, str):
            status = ModelStatus(status)

        async with self._lock:
            model_info = self._get_model_info(model_id)

            if version not in model_info.versions:
                raise ValueError(f"Version {version} not found for model {model_id}")

            version_info = model_info.versions[version]
            version_info.status = status

            # Update production version if promoted
            if status == ModelStatus.PRODUCTION:
                model_info.production_version = version
                model_info.current_version = version

            model_info.updated_at = datetime.utcnow()

            if self.storage_enabled:
                await self._save_to_storage(model_id)

            self._update_metrics()

        logger.info(f"Updated model {model_id} version {version} status to {status.value}")

        return model_info

    async def promote_to_staging(
        self,
        model_id: str,
        version: str,
    ) -> ModelInfo:
        """
        Promote a model version to staging.

        Args:
            model_id: Model identifier
            version: Version to promote

        Returns:
            Updated model info
        """
        return await self.update_model_status(
            model_id, version, ModelStatus.STAGING
        )

    async def promote_to_production(
        self,
        model_id: str,
        version: str,
    ) -> ModelInfo:
        """
        Promote a model version to production.

        Args:
            model_id: Model identifier
            version: Version to promote

        Returns:
            Updated model info
        """
        async with self._lock:
            # First promote to staging if not already
            model_info = self._get_model_info(model_id)

            if version not in model_info.versions:
                raise ValueError(f"Version {version} not found for model {model_id}")

            version_info = model_info.versions[version]

            # If not in staging or production, promote through stages
            if version_info.status not in [ModelStatus.STAGING, ModelStatus.PRODUCTION]:
                await self.promote_to_staging(model_id, version)

            return await self.update_model_status(
                model_id, version, ModelStatus.PRODUCTION
            )

    async def deprecate_version(
        self,
        model_id: str,
        version: str,
        reason: str = "",
    ) -> ModelInfo:
        """
        Deprecate a model version.

        Args:
            model_id: Model identifier
            version: Version to deprecate
            reason: Deprecation reason

        Returns:
            Updated model info
        """
        async with self._lock:
            model_info = self._get_model_info(model_id)

            if version not in model_info.versions:
                raise ValueError(f"Version {version} not found for model {model_id}")

            version_info = model_info.versions[version]
            version_info.status = ModelStatus.DEPRECATED
            version_info.description += f"\nDeprecated: {reason}" if reason else ""

            # If this was production, find next best version
            if model_info.production_version == version:
                # Try to find another production version
                prod_versions = [
                    v for v, info in model_info.versions.items()
                    if info.status == ModelStatus.PRODUCTION and v != version
                ]
                if prod_versions:
                    model_info.production_version = prod_versions[0]
                    model_info.current_version = prod_versions[0]
                else:
                    # Try staging versions
                    staging_versions = [
                        v for v, info in model_info.versions.items()
                        if info.status == ModelStatus.STAGING and v != version
                    ]
                    if staging_versions:
                        model_info.production_version = staging_versions[0]
                        model_info.current_version = staging_versions[0]

            model_info.updated_at = datetime.utcnow()

            if self.storage_enabled:
                await self._save_to_storage(model_id)

            self._update_metrics()

        logger.info(f"Deprecated model {model_id} version {version}: {reason}")

        return model_info

    async def archive_version(
        self,
        model_id: str,
        version: str,
    ) -> ModelInfo:
        """
        Archive a model version.

        Args:
            model_id: Model identifier
            version: Version to archive

        Returns:
            Updated model info
        """
        async with self._lock:
            model_info = self._get_model_info(model_id)

            if version not in model_info.versions:
                raise ValueError(f"Version {version} not found for model {model_id}")

            version_info = model_info.versions[version]
            version_info.status = ModelStatus.ARCHIVED

            model_info.updated_at = datetime.utcnow()

            if self.storage_enabled:
                await self._save_to_storage(model_id)

            self._update_metrics()

        logger.info(f"Archived model {model_id} version {version}")

        return model_info

    async def get_model(
        self,
        model_id: str,
        version: Optional[str] = None,
    ) -> Optional[ModelVersion]:
        """
        Get a specific model version.

        Args:
            model_id: Model identifier
            version: Version to retrieve (latest if None)

        Returns:
            Model version or None
        """
        await self.initialize()

        async with self._lock:
            if model_id not in self._registry:
                return None

            model_info = self._registry[model_id]

            # Determine version
            if version is None:
                version = model_info.current_version or model_info.production_version

            if version is None:
                # Use latest version
                versions = sorted(model_info.versions.keys())
                if not versions:
                    return None
                version = versions[-1]

            return model_info.versions.get(version)

    async def get_model_info(
        self,
        model_id: str,
    ) -> Optional[ModelInfo]:
        """
        Get complete model information.

        Args:
            model_id: Model identifier

        Returns:
            Model info or None
        """
        await self.initialize()

        async with self._lock:
            return self._registry.get(model_id)

    async def get_production_model(
        self,
        model_id: str,
    ) -> Optional[ModelVersion]:
        """
        Get the production version of a model.

        Args:
            model_id: Model identifier

        Returns:
            Production model version or None
        """
        model_info = await self.get_model_info(model_id)

        if not model_info or not model_info.production_version:
            return None

        return model_info.versions.get(model_info.production_version)

    async def get_staging_model(
        self,
        model_id: str,
    ) -> Optional[ModelVersion]:
        """
        Get the staging version of a model.

        Args:
            model_id: Model identifier

        Returns:
            Staging model version or None
        """
        model_info = await self.get_model_info(model_id)

        if not model_info or not model_info.staging_version:
            return None

        return model_info.versions.get(model_info.staging_version)

    async def list_models(
        self,
        model_type: Optional[str] = None,
        status: Optional[Union[ModelStatus, str]] = None,
        stage: Optional[Union[ModelStage, str]] = None,
        team: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ModelInfo]:
        """
        List models with filters.

        Args:
            model_type: Filter by model type
            status: Filter by status
            stage: Filter by stage
            team: Filter by team
            tags: Filter by tags
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            List of model info
        """
        await self.initialize()

        async with self._lock:
            models = list(self._registry.values())

            # Apply filters
            if model_type:
                models = [m for m in models if m.model_type == model_type]

            if status:
                if isinstance(status, str):
                    status = ModelStatus(status)
                models = [
                    m for m in models
                    if any(v.status == status for v in m.versions.values())
                ]

            if stage:
                if isinstance(stage, str):
                    stage = ModelStage(stage)
                models = [
                    m for m in models
                    if any(v.stage == stage for v in m.versions.values())
                ]

            if team:
                models = [m for m in models if m.team == team]

            if tags:
                models = [
                    m for m in models
                    if any(tag in m.tags for tag in tags)
                ]

            # Sort by updated_at
            models.sort(key=lambda x: x.updated_at, reverse=True)

            # Apply pagination
            models = models[offset:offset + limit]

            return models

    async def list_versions(
        self,
        model_id: str,
        limit: int = 10,
        offset: int = 0,
        status: Optional[Union[ModelStatus, str]] = None,
    ) -> List[ModelVersion]:
        """
        List versions of a model.

        Args:
            model_id: Model identifier
            limit: Maximum results
            offset: Offset for pagination
            status: Filter by status

        Returns:
            List of model versions
        """
        model_info = await self.get_model_info(model_id)

        if not model_info:
            return []

        versions = list(model_info.versions.values())

        # Apply filters
        if status:
            if isinstance(status, str):
                status = ModelStatus(status)
            versions = [v for v in versions if v.status == status]

        # Sort by created_at
        versions.sort(key=lambda x: x.created_at, reverse=True)

        # Apply pagination
        versions = versions[offset:offset + limit]

        return versions

    async def delete_model(
        self,
        model_id: str,
        force: bool = False,
    ) -> bool:
        """
        Delete a model from registry.

        Args:
            model_id: Model identifier
            force: Force delete even if in production

        Returns:
            True if deleted
        """
        await self.initialize()

        async with self._lock:
            if model_id not in self._registry:
                return False

            model_info = self._registry[model_id]

            # Check if in production
            if model_info.production_version and not force:
                raise ValueError(
                    f"Model {model_id} has production version. Use force=True to delete."
                )

            del self._registry[model_id]
            self._model_cache.pop(model_id, None)

            # Remove from storage
            if self.storage_enabled:
                model_path = self._storage_path / f"{model_id}.json"
                if model_path.exists():
                    model_path.unlink()

            self._update_metrics()

        logger.info(f"Deleted model {model_id}")

        return True

    async def compare_versions(
        self,
        model_id: str,
        version1: str,
        version2: str,
    ) -> Dict[str, Any]:
        """
        Compare two model versions.

        Args:
            model_id: Model identifier
            version1: First version
            version2: Second version

        Returns:
            Comparison results
        """
        model_info = await self.get_model_info(model_id)

        if not model_info:
            raise ValueError(f"Model {model_id} not found")

        v1 = model_info.versions.get(version1)
        v2 = model_info.versions.get(version2)

        if not v1:
            raise ValueError(f"Version {version1} not found")
        if not v2:
            raise ValueError(f"Version {version2} not found")

        # Compare metrics
        metric_comparison = {}
        all_metrics = set(v1.metrics.keys()) | set(v2.metrics.keys())

        for metric in all_metrics:
            val1 = v1.metrics.get(metric)
            val2 = v2.metrics.get(metric)
            if val1 is not None and val2 is not None and val2 != 0:
                delta = (val1 - val2) / abs(val2) * 100
            else:
                delta = None

            metric_comparison[metric] = {
                "version1": val1,
                "version2": val2,
                "delta_percent": delta,
                "better": val1 > val2 if val1 is not None and val2 is not None else None,
            }

        return {
            "model_id": model_id,
            "version1": {
                "version": version1,
                "created_at": v1.created_at.isoformat(),
                "status": v1.status.value,
                "stage": v1.stage.value,
                "metrics": v1.metrics,
            },
            "version2": {
                "version": version2,
                "created_at": v2.created_at.isoformat(),
                "status": v2.status.value,
                "stage": v2.stage.value,
                "metrics": v2.metrics,
            },
            "metric_comparison": metric_comparison,
            "recommendation": (
                version1 if all(
                    info.get("better") for info in metric_comparison.values()
                    if info.get("better") is not None
                )
                else version2
            ),
        }

    async def get_model_metrics(
        self,
        model_id: str,
        version: Optional[str] = None,
    ) -> Dict[str, float]:
        """
        Get metrics for a model version.

        Args:
            model_id: Model identifier
            version: Version (latest if None)

        Returns:
            Model metrics
        """
        model_version = await self.get_model(model_id, version)

        if not model_version:
            return {}

        return model_version.metrics

    async def update_model_metrics(
        self,
        model_id: str,
        version: str,
        metrics: Dict[str, float],
    ) -> ModelInfo:
        """
        Update metrics for a model version.

        Args:
            model_id: Model identifier
            version: Version to update
            metrics: New metrics

        Returns:
            Updated model info
        """
        async with self._lock:
            model_info = self._get_model_info(model_id)

            if version not in model_info.versions:
                raise ValueError(f"Version {version} not found for model {model_id}")

            model_info.versions[version].metrics.update(metrics)
            model_info.updated_at = datetime.utcnow()

            if self.storage_enabled:
                await self._save_to_storage(model_id)

        logger.info(f"Updated metrics for model {model_id} version {version}")

        return model_info

    async def tag_model(
        self,
        model_id: str,
        version: str,
        tags: List[str],
    ) -> ModelInfo:
        """
        Add tags to a model version.

        Args:
            model_id: Model identifier
            version: Version to tag
            tags: Tags to add

        Returns:
            Updated model info
        """
        async with self._lock:
            model_info = self._get_model_info(model_id)

            if version not in model_info.versions:
                raise ValueError(f"Version {version} not found for model {model_id}")

            version_info = model_info.versions[version]
            version_info.tags.extend(tags)
            version_info.tags = list(set(version_info.tags))

            model_info.updated_at = datetime.utcnow()

            if self.storage_enabled:
                await self._save_to_storage(model_id)

        logger.info(f"Tagged model {model_id} version {version} with {tags}")

        return model_info

    async def _archive_old_versions(self, model_info: ModelInfo):
        """Archive old versions when limit exceeded."""
        versions = sorted(
            model_info.versions.values(),
            key=lambda x: x.created_at,
        )

        # Don't archive production or staging versions
        active_versions = [
            v for v in versions
            if v.status in [ModelStatus.PRODUCTION, ModelStatus.STAGING]
        ]

        # Get old versions to archive
        old_versions = [
            v for v in versions
            if v not in active_versions
        ][:-(self.max_versions - len(active_versions))]

        for version in old_versions:
            version.status = ModelStatus.ARCHIVED

    async def _save_to_storage(self, model_id: str):
        """Save model info to storage."""
        model_info = self._registry[model_id]
        model_path = self._storage_path / f"{model_id}.json"

        data = model_info.to_dict()

        async with aiofiles.open(model_path, "w") as f:
            await f.write(json.dumps(data, indent=2))

    async def _load_from_storage(self):
        """Load model info from storage."""
        for file_path in self._storage_path.glob("*.json"):
            try:
                async with aiofiles.open(file_path, "r") as f:
                    content = await f.read()
                    data = json.loads(content)
                    model_info = ModelInfo.from_dict(data)
                    self._registry[model_info.model_id] = model_info
            except Exception as e:
                logger.error(f"Error loading model from {file_path}: {e}")

    def _get_model_info(self, model_id: str) -> ModelInfo:
        """Get model info or raise error."""
        if model_id not in self._registry:
            raise ValueError(f"Model {model_id} not found")
        return self._registry[model_id]

    def _update_metrics(self):
        """Update Prometheus metrics."""
        # Count models by status
        status_counts = {}
        for model_info in self._registry.values():
            for version in model_info.versions.values():
                status = version.status.value
                status_counts[status] = status_counts.get(status, 0) + 1

        for status, count in status_counts.items():
            MODEL_REGISTRY_COUNT.labels(status=status).set(count)

        # Count versions by model type
        type_counts = {}
        for model_info in self._registry.values():
            type_counts[model_info.model_type] = type_counts.get(model_info.model_type, 0) + 1

        for model_type, count in type_counts.items():
            MODEL_VERSION_COUNT.labels(model_type=model_type).set(count)

    async def export_registry(
        self,
        output_path: Union[str, Path],
        format: str = "json",
    ):
        """
        Export entire registry.

        Args:
            output_path: Output path
            format: Export format ("json" or "yaml")
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            model_id: model_info.to_dict()
            for model_id, model_info in self._registry.items()
        }

        if format == "json":
            async with aiofiles.open(output_path, "w") as f:
                await f.write(json.dumps(data, indent=2))
        elif format == "yaml":
            async with aiofiles.open(output_path, "w") as f:
                await f.write(yaml.dump(data, default_flow_style=False))
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Exported registry to {output_path}")

    async def import_registry(
        self,
        input_path: Union[str, Path],
        format: str = "json",
    ):
        """
        Import registry from file.

        Args:
            input_path: Input path
            format: Import format ("json" or "yaml")
        """
        input_path = Path(input_path)

        if not input_path.exists():
            raise FileNotFoundError(f"File not found: {input_path}")

        async with aiofiles.open(input_path, "r") as f:
            content = await f.read()

        if format == "json":
            data = json.loads(content)
        elif format == "yaml":
            data = yaml.safe_load(content)
        else:
            raise ValueError(f"Unsupported format: {format}")

        async with self._lock:
            for model_id, model_data in data.items():
                model_info = ModelInfo.from_dict(model_data)
                self._registry[model_id] = model_info

                if self.storage_enabled:
                    await self._save_to_storage(model_id)

            self._update_metrics()

        logger.info(f"Imported registry from {input_path}")


# Export singleton
model_registry = ModelRegistry()
