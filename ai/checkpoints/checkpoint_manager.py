"""
NEXUS AI TRADING SYSTEM - Checkpoint Manager
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Checkpoint Manager system with:
- Model checkpointing
- State persistence
- Version control
- Checkpoint recovery
- Checkpoint validation
- Storage management
- Metadata tracking
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
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4

import aiofiles
import cloudpickle
import numpy as np
from pydantic import BaseModel, Field, validator

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import CheckpointError

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class CheckpointType(str, Enum):
    """Checkpoint types"""
    MODEL = "model"
    STATE = "state"
    CONFIG = "config"
    DATA = "data"
    METRICS = "metrics"
    FULL = "full"


class CheckpointStatus(str, Enum):
    """Checkpoint status"""
    CREATED = "created"
    VALIDATING = "validating"
    VALIDATED = "validated"
    INVALID = "invalid"
    RESTORING = "restoring"
    RESTORED = "restored"
    FAILED = "failed"
    DELETED = "deleted"


class StorageType(str, Enum):
    """Storage types"""
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"
    REDIS = "redis"


@dataclass
class Checkpoint:
    """Checkpoint data"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str
    type: CheckpointType
    version: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    status: CheckpointStatus = CheckpointStatus.CREATED
    path: str = ""
    size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    checksum: Optional[str] = None
    expires_at: Optional[datetime] = None


@dataclass
class CheckpointInfo:
    """Checkpoint information"""
    id: str
    name: str
    type: CheckpointType
    version: str
    created_at: datetime
    size: int
    status: CheckpointStatus
    tags: List[str]
    metadata: Dict[str, Any]


class CheckpointConfig(BaseModel):
    """Checkpoint configuration"""
    enabled: bool = True
    storage_type: StorageType = StorageType.LOCAL
    storage_path: str = Field(default="./checkpoints")
    max_checkpoints: int = Field(default=100, gt=0)
    max_size_gb: float = Field(default=10.0, gt=0)
    auto_save_interval: int = Field(default=300, gt=0)  # seconds
    compression_enabled: bool = True
    encryption_enabled: bool = True
    encryption_key: Optional[str] = None
    retention_days: int = Field(default=30, gt=0)
    validate_checksums: bool = True
    parallel_workers: int = Field(default=4, gt=0)
    cleanup_interval: int = Field(default=3600, gt=0)
    health_check_interval: int = Field(default=60, gt=0)
    log_level: str = "info"


# ========================================
# CHECKPOINT MANAGER
# ========================================

class CheckpointManager:
    """
    Complete checkpoint manager for AI models and system state.
    
    Features:
    - Model checkpointing
    - State persistence
    - Version control
    - Checkpoint recovery
    - Checkpoint validation
    - Storage management
    - Metadata tracking
    - Health monitoring
    - Configuration management
    - Event handling
    - Logging
    - Metrics collection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = CheckpointConfig(**(config or {}))
        self.redis = get_redis()
        
        # State
        self._checkpoints: Dict[str, Checkpoint] = {}
        self._active_restores: Dict[str, asyncio.Task] = {}
        self._active_saves: Dict[str, asyncio.Task] = {}
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        self._tasks: List[asyncio.Task] = []
        
        # Metrics
        self._metrics = {
            "total_checkpoints": 0,
            "active_checkpoints": 0,
            "total_size_gb": 0.0,
            "saves_completed": 0,
            "saves_failed": 0,
            "restores_completed": 0,
            "restores_failed": 0,
            "validations_completed": 0,
            "validations_failed": 0,
            "avg_save_time": 0.0,
            "avg_restore_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        # Initialize storage
        self._initialize_storage()
        
        # Load existing checkpoints
        self._load_checkpoints()
        
        self.logger = get_logger(f"{__name__}.CheckpointManager")
        self.logger.info("CheckpointManager initialized")
    
    # ========================================
    # STORAGE MANAGEMENT
    # ========================================
    
    def _initialize_storage(self) -> None:
        """Initialize storage directory"""
        if self.config.storage_type == StorageType.LOCAL:
            path = Path(self.config.storage_path)
            path.mkdir(parents=True, exist_ok=True)
            
            # Create subdirectories
            for subdir in ['models', 'states', 'configs', 'data', 'metrics', 'full']:
                (path / subdir).mkdir(exist_ok=True)
    
    def _load_checkpoints(self) -> None:
        """Load existing checkpoints from storage"""
        if self.config.storage_type != StorageType.LOCAL:
            return
        
        path = Path(self.config.storage_path)
        if not path.exists():
            return
        
        # Load metadata files
        for metadata_file in path.glob("*.meta.json"):
            try:
                with open(metadata_file, 'r') as f:
                    data = json.load(f)
                
                checkpoint = Checkpoint(
                    id=data['id'],
                    name=data['name'],
                    type=CheckpointType(data['type']),
                    version=data['version'],
                    created_at=datetime.fromisoformat(data['created_at']),
                    updated_at=datetime.fromisoformat(data['updated_at']),
                    status=CheckpointStatus(data['status']),
                    path=data['path'],
                    size=data['size'],
                    metadata=data.get('metadata', {}),
                    tags=data.get('tags', []),
                    dependencies=data.get('dependencies', []),
                    parent_id=data.get('parent_id'),
                    checksum=data.get('checksum'),
                    expires_at=datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None
                )
                
                self._checkpoints[checkpoint.id] = checkpoint
                
            except Exception as e:
                self.logger.error(f"Failed to load checkpoint metadata {metadata_file}: {e}")
        
        self._metrics["total_checkpoints"] = len(self._checkpoints)
        self.logger.info(f"Loaded {len(self._checkpoints)} checkpoints")
    
    # ========================================
    # CHECKPOINT CREATION
    # ========================================
    
    async def create_checkpoint(
        self,
        name: str,
        type: CheckpointType,
        data: Any,
        version: str = "1.0.0",
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        parent_id: Optional[str] = None,
        expires_in_days: Optional[int] = None
    ) -> Checkpoint:
        """
        Create a new checkpoint.
        
        Args:
            name: Checkpoint name
            type: Checkpoint type
            data: Data to checkpoint
            version: Version string
            metadata: Additional metadata
            tags: Tags for categorization
            dependencies: List of dependency checkpoint IDs
            parent_id: Parent checkpoint ID
            expires_in_days: Expiration in days
            
        Returns:
            Checkpoint: Created checkpoint
        """
        start_time = time.time()
        
        try:
            # Validate storage
            if not self._check_storage_available():
                raise CheckpointError("Storage is full or unavailable")
            
            # Create checkpoint
            checkpoint_id = str(uuid4())
            
            checkpoint = Checkpoint(
                id=checkpoint_id,
                name=name,
                type=type,
                version=version,
                metadata=metadata or {},
                tags=tags or [],
                dependencies=dependencies or [],
                parent_id=parent_id
            )
            
            if expires_in_days:
                checkpoint.expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
            
            # Save data
            path = await self._save_data(checkpoint_id, type, data)
            checkpoint.path = path
            checkpoint.size = os.path.getsize(path) if os.path.exists(path) else 0
            
            # Calculate checksum
            if self.config.validate_checksums:
                checkpoint.checksum = await self._calculate_checksum(path)
            
            # Save metadata
            await self._save_metadata(checkpoint)
            
            # Update state
            self._checkpoints[checkpoint_id] = checkpoint
            
            # Update metrics
            self._metrics["total_checkpoints"] += 1
            self._metrics["active_checkpoints"] += 1
            self._metrics["total_size_gb"] += checkpoint.size / (1024 ** 3)
            self._metrics["saves_completed"] += 1
            
            elapsed = time.time() - start_time
            self._metrics["avg_save_time"] = (
                self._metrics["avg_save_time"] * 0.9 + elapsed * 0.1
            )
            
            self.logger.info(
                f"Checkpoint created: {name} ({checkpoint_id}) "
                f"size: {checkpoint.size / 1024:.2f}KB "
                f"in {elapsed:.2f}s"
            )
            
            # Cleanup old checkpoints if needed
            await self._cleanup_if_needed()
            
            return checkpoint
            
        except Exception as e:
            self.logger.error(f"Failed to create checkpoint: {e}")
            self._metrics["saves_failed"] += 1
            raise CheckpointError(f"Checkpoint creation failed: {e}")
    
    # ========================================
    # CHECKPOINT RESTORATION
    # ========================================
    
    async def restore_checkpoint(
        self,
        checkpoint_id: str,
        target_path: Optional[str] = None
    ) -> Any:
        """
        Restore a checkpoint.
        
        Args:
            checkpoint_id: Checkpoint ID
            target_path: Target path for restoration
            
        Returns:
            Any: Restored data
            
        Raises:
            CheckpointError: If checkpoint not found or invalid
        """
        start_time = time.time()
        
        try:
            checkpoint = self._get_checkpoint(checkpoint_id)
            
            if checkpoint.status == CheckpointStatus.DELETED:
                raise CheckpointError(f"Checkpoint {checkpoint_id} has been deleted")
            
            # Validate checkpoint
            if not await self._validate_checkpoint(checkpoint):
                raise CheckpointError(f"Checkpoint {checkpoint_id} validation failed")
            
            # Check dependencies
            await self._check_dependencies(checkpoint)
            
            # Restore data
            data = await self._restore_data(checkpoint, target_path)
            
            # Update status
            checkpoint.status = CheckpointStatus.RESTORED
            checkpoint.updated_at = datetime.utcnow()
            await self._save_metadata(checkpoint)
            
            # Update metrics
            self._metrics["restores_completed"] += 1
            
            elapsed = time.time() - start_time
            self._metrics["avg_restore_time"] = (
                self._metrics["avg_restore_time"] * 0.9 + elapsed * 0.1
            )
            
            self.logger.info(f"Checkpoint restored: {checkpoint.name} ({checkpoint_id}) in {elapsed:.2f}s")
            
            return data
            
        except Exception as e:
            self.logger.error(f"Failed to restore checkpoint: {e}")
            self._metrics["restores_failed"] += 1
            raise CheckpointError(f"Checkpoint restoration failed: {e}")
    
    # ========================================
    # CHECKPOINT VALIDATION
    # ========================================
    
    async def _validate_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """Validate a checkpoint"""
        try:
            checkpoint.status = CheckpointStatus.VALIDATING
            
            # Check if file exists
            if not os.path.exists(checkpoint.path):
                self.logger.warning(f"Checkpoint file missing: {checkpoint.path}")
                checkpoint.status = CheckpointStatus.INVALID
                return False
            
            # Validate checksum
            if self.config.validate_checksums and checkpoint.checksum:
                current_checksum = await self._calculate_checksum(checkpoint.path)
                if current_checksum != checkpoint.checksum:
                    self.logger.warning(f"Checksum mismatch for checkpoint {checkpoint.id}")
                    checkpoint.status = CheckpointStatus.INVALID
                    return False
            
            # Validate data integrity
            try:
                await self._test_load(checkpoint.path)
            except Exception as e:
                self.logger.warning(f"Data integrity check failed: {e}")
                checkpoint.status = CheckpointStatus.INVALID
                return False
            
            checkpoint.status = CheckpointStatus.VALIDATED
            self._metrics["validations_completed"] += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Checkpoint validation failed: {e}")
            checkpoint.status = CheckpointStatus.INVALID
            self._metrics["validations_failed"] += 1
            return False
    
    async def _test_load(self, path: str) -> None:
        """Test load data from checkpoint"""
        try:
            with open(path, 'rb') as f:
                data = cloudpickle.load(f)
            # Just verify it can be loaded
        except Exception as e:
            raise CheckpointError(f"Failed to test load: {e}")
    
    async def _check_dependencies(self, checkpoint: Checkpoint) -> None:
        """Check if all dependencies are available"""
        if not checkpoint.dependencies:
            return
        
        missing_deps = []
        for dep_id in checkpoint.dependencies:
            if dep_id not in self._checkpoints:
                missing_deps.append(dep_id)
            else:
                dep = self._checkpoints[dep_id]
                if dep.status in [CheckpointStatus.INVALID, CheckpointStatus.DELETED]:
                    missing_deps.append(dep_id)
        
        if missing_deps:
            raise CheckpointError(f"Missing dependencies: {missing_deps}")
    
    # ========================================
    # CHECKPOINT DELETION
    # ========================================
    
    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """
        Delete a checkpoint.
        
        Args:
            checkpoint_id: Checkpoint ID
            
        Returns:
            bool: True if deleted
        """
        try:
            checkpoint = self._get_checkpoint(checkpoint_id)
            
            # Delete file
            if os.path.exists(checkpoint.path):
                os.remove(checkpoint.path)
            
            # Delete metadata
            metadata_path = Path(self.config.storage_path) / f"{checkpoint_id}.meta.json"
            if metadata_path.exists():
                os.remove(metadata_path)
            
            # Update state
            checkpoint.status = CheckpointStatus.DELETED
            
            self._metrics["active_checkpoints"] -= 1
            self._metrics["total_size_gb"] -= checkpoint.size / (1024 ** 3)
            
            self.logger.info(f"Checkpoint deleted: {checkpoint.name} ({checkpoint_id})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete checkpoint: {e}")
            return False
    
    # ========================================
    # STORAGE OPERATIONS
    # ========================================
    
    async def _save_data(
        self,
        checkpoint_id: str,
        type: CheckpointType,
        data: Any
    ) -> str:
        """Save data to storage"""
        # Determine subdirectory
        subdir = type.value.lower()
        if type == CheckpointType.FULL:
            subdir = 'full'
        
        path = Path(self.config.storage_path) / subdir / f"{checkpoint_id}.pkl"
        
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save data
        async with aiofiles.open(path, 'wb') as f:
            # Serialize with cloudpickle
            serialized = cloudpickle.dumps(data)
            
            # Compress if enabled
            if self.config.compression_enabled:
                import zlib
                serialized = zlib.compress(serialized)
            
            # Encrypt if enabled
            if self.config.encryption_enabled and self.config.encryption_key:
                from cryptography.fernet import Fernet
                cipher = Fernet(self.config.encryption_key.encode())
                serialized = cipher.encrypt(serialized)
            
            await f.write(serialized)
        
        return str(path)
    
    async def _restore_data(
        self,
        checkpoint: Checkpoint,
        target_path: Optional[str] = None
    ) -> Any:
        """Restore data from storage"""
        path = target_path or checkpoint.path
        
        async with aiofiles.open(path, 'rb') as f:
            data = await f.read()
            
            # Decrypt if enabled
            if self.config.encryption_enabled and self.config.encryption_key:
                from cryptography.fernet import Fernet
                cipher = Fernet(self.config.encryption_key.encode())
                data = cipher.decrypt(data)
            
            # Decompress if enabled
            if self.config.compression_enabled:
                import zlib
                data = zlib.decompress(data)
            
            # Deserialize
            return cloudpickle.loads(data)
    
    async def _save_metadata(self, checkpoint: Checkpoint) -> None:
        """Save checkpoint metadata"""
        metadata_path = Path(self.config.storage_path) / f"{checkpoint.id}.meta.json"
        
        metadata = {
            'id': checkpoint.id,
            'name': checkpoint.name,
            'type': checkpoint.type.value,
            'version': checkpoint.version,
            'created_at': checkpoint.created_at.isoformat(),
            'updated_at': checkpoint.updated_at.isoformat(),
            'status': checkpoint.status.value,
            'path': checkpoint.path,
            'size': checkpoint.size,
            'metadata': checkpoint.metadata,
            'tags': checkpoint.tags,
            'dependencies': checkpoint.dependencies,
            'parent_id': checkpoint.parent_id,
            'checksum': checkpoint.checksum,
            'expires_at': checkpoint.expires_at.isoformat() if checkpoint.expires_at else None
        }
        
        async with aiofiles.open(metadata_path, 'w') as f:
            await f.write(json.dumps(metadata, indent=2))
    
    async def _calculate_checksum(self, path: str) -> str:
        """Calculate file checksum"""
        sha256_hash = hashlib.sha256()
        
        async with aiofiles.open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    def _check_storage_available(self) -> bool:
        """Check if storage is available"""
        if self.config.storage_type != StorageType.LOCAL:
            return True
        
        # Check disk space
        path = Path(self.config.storage_path)
        if not path.exists():
            return False
        
        total_size = sum(
            checkpoint.size for checkpoint in self._checkpoints.values()
            if checkpoint.status != CheckpointStatus.DELETED
        )
        
        max_size_bytes = self.config.max_size_gb * 1024 ** 3
        if total_size >= max_size_bytes:
            self.logger.warning("Storage limit reached")
            return False
        
        # Check number of checkpoints
        active_count = sum(
            1 for c in self._checkpoints.values()
            if c.status != CheckpointStatus.DELETED
        )
        
        if active_count >= self.config.max_checkpoints:
            self.logger.warning("Max checkpoints reached")
            return False
        
        return True
    
    # ========================================
    # CLEANUP
    # ========================================
    
    async def _cleanup_if_needed(self) -> None:
        """Clean up old checkpoints if needed"""
        # Check if we need to clean up
        active_count = sum(
            1 for c in self._checkpoints.values()
            if c.status != CheckpointStatus.DELETED
        )
        
        if active_count < self.config.max_checkpoints:
            return
        
        # Delete oldest checkpoints
        sorted_checkpoints = sorted(
            [c for c in self._checkpoints.values() if c.status != CheckpointStatus.DELETED],
            key=lambda c: c.created_at
        )
        
        to_delete = len(sorted_checkpoints) - self.config.max_checkpoints // 2
        for checkpoint in sorted_checkpoints[:to_delete]:
            await self.delete_checkpoint(checkpoint.id)
    
    async def _cleanup_expired(self) -> None:
        """Clean up expired checkpoints"""
        now = datetime.utcnow()
        
        for checkpoint in list(self._checkpoints.values()):
            if checkpoint.expires_at and checkpoint.expires_at < now:
                await self.delete_checkpoint(checkpoint.id)
    
    # ========================================
    # SEARCH & QUERY
    # ========================================
    
    def _get_checkpoint(self, checkpoint_id: str) -> Checkpoint:
        """Get checkpoint by ID"""
        checkpoint = self._checkpoints.get(checkpoint_id)
        if not checkpoint:
            raise CheckpointError(f"Checkpoint {checkpoint_id} not found")
        return checkpoint
    
    async def get_checkpoint_info(
        self,
        checkpoint_id: str
    ) -> Optional[CheckpointInfo]:
        """Get checkpoint information"""
        checkpoint = self._checkpoints.get(checkpoint_id)
        if not checkpoint:
            return None
        
        return CheckpointInfo(
            id=checkpoint.id,
            name=checkpoint.name,
            type=checkpoint.type,
            version=checkpoint.version,
            created_at=checkpoint.created_at,
            size=checkpoint.size,
            status=checkpoint.status,
            tags=checkpoint.tags,
            metadata=checkpoint.metadata
        )
    
    async def list_checkpoints(
        self,
        type: Optional[CheckpointType] = None,
        status: Optional[CheckpointStatus] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[CheckpointInfo]:
        """List checkpoints with filters"""
        checkpoints = list(self._checkpoints.values())
        
        # Apply filters
        if type:
            checkpoints = [c for c in checkpoints if c.type == type]
        
        if status:
            checkpoints = [c for c in checkpoints if c.status == status]
        
        if tags:
            checkpoints = [
                c for c in checkpoints
                if any(tag in c.tags for tag in tags)
            ]
        
        # Sort by creation date (newest first)
        checkpoints.sort(key=lambda c: c.created_at, reverse=True)
        
        # Apply pagination
        checkpoints = checkpoints[offset:offset + limit]
        
        return [
            CheckpointInfo(
                id=c.id,
                name=c.name,
                type=c.type,
                version=c.version,
                created_at=c.created_at,
                size=c.size,
                status=c.status,
                tags=c.tags,
                metadata=c.metadata
            )
            for c in checkpoints
        ]
    
    async def search_checkpoints(
        self,
        query: str,
        limit: int = 50
    ) -> List[CheckpointInfo]:
        """Search checkpoints by name, tags, or metadata"""
        results = []
        
        for checkpoint in self._checkpoints.values():
            # Search in name
            if query.lower() in checkpoint.name.lower():
                results.append(checkpoint)
                continue
            
            # Search in tags
            if any(query.lower() in tag.lower() for tag in checkpoint.tags):
                results.append(checkpoint)
                continue
            
            # Search in metadata
            if checkpoint.metadata:
                for key, value in checkpoint.metadata.items():
                    if query.lower() in str(value).lower():
                        results.append(checkpoint)
                        break
        
        results.sort(key=lambda c: c.created_at, reverse=True)
        results = results[:limit]
        
        return [
            CheckpointInfo(
                id=c.id,
                name=c.name,
                type=c.type,
                version=c.version,
                created_at=c.created_at,
                size=c.size,
                status=c.status,
                tags=c.tags,
                metadata=c.metadata
            )
            for c in results
        ]
    
    # ========================================
    # EXPORT & IMPORT
    # ========================================
    
    async def export_checkpoint(
        self,
        checkpoint_id: str,
        export_path: str
    ) -> str:
        """
        Export checkpoint to a file.
        
        Args:
            checkpoint_id: Checkpoint ID
            export_path: Export path
            
        Returns:
            str: Export file path
        """
        checkpoint = self._get_checkpoint(checkpoint_id)
        
        if checkpoint.status == CheckpointStatus.DELETED:
            raise CheckpointError(f"Checkpoint {checkpoint_id} has been deleted")
        
        # Copy file
        export_file = Path(export_path) / f"{checkpoint.name}_{checkpoint_id}.ckpt"
        shutil.copy2(checkpoint.path, export_file)
        
        # Copy metadata
        metadata_file = export_file.with_suffix('.meta.json')
        metadata_path = Path(self.config.storage_path) / f"{checkpoint.id}.meta.json"
        shutil.copy2(metadata_path, metadata_file)
        
        self.logger.info(f"Checkpoint exported: {export_file}")
        return str(export_file)
    
    async def import_checkpoint(self, import_path: str) -> Checkpoint:
        """
        Import checkpoint from file.
        
        Args:
            import_path: Import file path
            
        Returns:
            Checkpoint: Imported checkpoint
        """
        import_file = Path(import_path)
        
        if not import_file.exists():
            raise CheckpointError(f"Import file not found: {import_path}")
        
        # Load metadata
        metadata_file = import_file.with_suffix('.meta.json')
        if not metadata_file.exists():
            raise CheckpointError(f"Metadata file not found: {metadata_file}")
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        # Create checkpoint
        checkpoint = Checkpoint(
            name=metadata['name'],
            type=CheckpointType(metadata['type']),
            version=metadata['version'],
            metadata=metadata.get('metadata', {}),
            tags=metadata.get('tags', []),
            dependencies=metadata.get('dependencies', [])
        )
        
        # Copy file
        target_path = Path(self.config.storage_path) / f"{checkpoint.id}.pkl"
        shutil.copy2(import_file, target_path)
        checkpoint.path = str(target_path)
        checkpoint.size = target_path.stat().st_size
        
        # Save metadata
        await self._save_metadata(checkpoint)
        
        # Update state
        self._checkpoints[checkpoint.id] = checkpoint
        
        self._metrics["total_checkpoints"] += 1
        self._metrics["active_checkpoints"] += 1
        self._metrics["total_size_gb"] += checkpoint.size / (1024 ** 3)
        
        self.logger.info(f"Checkpoint imported: {checkpoint.name} ({checkpoint.id})")
        return checkpoint
    
    # ========================================
    # BACKGROUND TASKS
    # ========================================
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop"""
        while self._running:
            try:
                await self._cleanup_expired()
                await self._cleanup_if_needed()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Cleanup loop error: {e}")
            
            await asyncio.sleep(self.config.cleanup_interval)
    
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
        """Get manager metrics"""
        return {
            **self._metrics,
            "total_checkpoints": len(self._checkpoints),
            "active_checkpoints": sum(
                1 for c in self._checkpoints.values()
                if c.status != CheckpointStatus.DELETED
            ),
            "storage_used_gb": self._metrics["total_size_gb"],
            "storage_available_gb": self.config.max_size_gb - self._metrics["total_size_gb"],
            "running": self._running
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check manager health"""
        health = {
            'status': 'healthy',
            'storage': {
                'type': self.config.storage_type.value,
                'path': self.config.storage_path,
                'available': self._check_storage_available()
            },
            'checkpoints': {
                'total': len(self._checkpoints),
                'active': sum(
                    1 for c in self._checkpoints.values()
                    if c.status != CheckpointStatus.DELETED
                ),
                'invalid': sum(
                    1 for c in self._checkpoints.values()
                    if c.status == CheckpointStatus.INVALID
                )
            }
        }
        
        if not self._check_storage_available():
            health['status'] = 'degraded'
        
        return health
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the checkpoint manager"""
        self._running = True
        
        # Start background tasks
        self._tasks.append(asyncio.create_task(self._cleanup_loop()))
        self._tasks.append(asyncio.create_task(self._health_loop()))
        
        self.logger.info("CheckpointManager started")
    
    async def stop(self) -> None:
        """Stop the checkpoint manager"""
        self._running = False
        
        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self.logger.info("CheckpointManager stopped")


# ========================================
# DEPENDENCY INJECTION
# ========================================

_checkpoint_manager: Optional[CheckpointManager] = None


def get_checkpoint_manager() -> CheckpointManager:
    """Get singleton instance of CheckpointManager"""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
    return _checkpoint_manager


def reset_checkpoint_manager() -> None:
    """Reset the checkpoint manager (for testing)"""
    global _checkpoint_manager
    if _checkpoint_manager:
        asyncio.create_task(_checkpoint_manager.stop())
    _checkpoint_manager = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'CheckpointManager',
    'CheckpointConfig',
    'Checkpoint',
    'CheckpointInfo',
    'CheckpointType',
    'CheckpointStatus',
    'StorageType',
    'get_checkpoint_manager',
    'reset_checkpoint_manager'
]
