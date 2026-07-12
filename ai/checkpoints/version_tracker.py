"""
NEXUS AI TRADING SYSTEM - Version Tracker
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Version Tracker system with:
- Version management
- Version history tracking
- Version comparison
- Version rollback
- Version tagging
- Version metadata
- Version lifecycle management
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4

from pydantic import BaseModel, Field, validator

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import VersionTrackerError

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class VersionStatus(str, Enum):
    """Version status"""
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
    DELETED = "deleted"


class VersionType(str, Enum):
    """Version types"""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    HOTFIX = "hotfix"
    RELEASE = "release"
    CANDIDATE = "candidate"
    SNAPSHOT = "snapshot"


@dataclass
class Version:
    """Version data"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str
    number: str
    type: VersionType
    status: VersionStatus = VersionStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None
    deprecated_at: Optional[datetime] = None
    description: str = ""
    changelog: str = ""
    author: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)  # version IDs
    previous_version: Optional[str] = None
    next_version: Optional[str] = None


@dataclass
class VersionInfo:
    """Version information"""
    id: str
    name: str
    number: str
    type: VersionType
    status: VersionStatus
    created_at: datetime
    description: str
    tags: List[str]
    dependencies: List[str]


@dataclass
class VersionDiff:
    """Version difference"""
    version_from: str
    version_to: str
    changes: List[Dict[str, Any]]
    additions: List[str]
    removals: List[str]
    modifications: List[str]


class VersionConfig(BaseModel):
    """Version configuration"""
    enabled: bool = True
    max_versions: int = Field(default=1000, gt=0)
    keep_versions_days: int = Field(default=365, gt=0)
    auto_cleanup: bool = True
    cleanup_interval: int = Field(default=86400, gt=0)  # seconds
    health_check_interval: int = Field(default=60, gt=0)
    log_level: str = "info"


# ========================================
# VERSION TRACKER
# ========================================

class VersionTracker:
    """
    Complete version tracker for AI models and system components.
    
    Features:
    - Version management
    - Version history tracking
    - Version comparison
    - Version rollback
    - Version tagging
    - Version metadata
    - Version lifecycle management
    - Health monitoring
    - Configuration management
    - Event handling
    - Logging
    - Metrics collection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = VersionConfig(**(config or {}))
        self.redis = get_redis()
        
        # State
        self._versions: Dict[str, Version] = {}
        self._version_lists: Dict[str, List[str]] = {}  # name -> version IDs
        self._current_versions: Dict[str, str] = {}  # name -> current version ID
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        self._tasks: List[asyncio.Task] = []
        
        # Metrics
        self._metrics = {
            "total_versions": 0,
            "active_versions": 0,
            "published_versions": 0,
            "deprecated_versions": 0,
            "archived_versions": 0,
            "snapshots_created": 0,
            "releases_created": 0,
            "rollbacks_performed": 0,
            "avg_creation_time": 0.0
        }
        
        self.logger = get_logger(f"{__name__}.VersionTracker")
        self.logger.info("VersionTracker initialized")
    
    # ========================================
    # VERSION CREATION
    # ========================================
    
    async def create_version(
        self,
        name: str,
        number: str,
        type: VersionType,
        description: str = "",
        changelog: str = "",
        author: str = "",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None
    ) -> Version:
        """
        Create a new version.
        
        Args:
            name: Version name
            number: Version number (semantic)
            type: Version type
            description: Version description
            changelog: Changelog
            author: Author name
            tags: Tags
            metadata: Additional metadata
            dependencies: Dependencies IDs
            
        Returns:
            Version: Created version
            
        Raises:
            VersionTrackerError: If version already exists
        """
        start_time = time.time()
        
        try:
            # Validate version number
            if not self._validate_version_number(number):
                raise VersionTrackerError(f"Invalid version number: {number}")
            
            # Check if version already exists
            existing = await self.get_version_by_name_number(name, number)
            if existing:
                raise VersionTrackerError(f"Version {name} v{number} already exists")
            
            # Create version
            version_id = str(uuid4())
            
            version = Version(
                id=version_id,
                name=name,
                number=number,
                type=type,
                description=description,
                changelog=changelog,
                author=author,
                tags=tags or [],
                metadata=metadata or {},
                dependencies=dependencies or []
            )
            
            # Get previous version
            current = await self.get_current_version(name)
            if current:
                version.previous_version = current.id
            
            # Update state
            self._versions[version_id] = version
            
            if name not in self._version_lists:
                self._version_lists[name] = []
            self._version_lists[name].append(version_id)
            
            # Update metrics
            self._metrics["total_versions"] += 1
            self._metrics["active_versions"] += 1
            
            if type == VersionType.RELEASE:
                self._metrics["releases_created"] += 1
            elif type == VersionType.SNAPSHOT:
                self._metrics["snapshots_created"] += 1
            
            elapsed = time.time() - start_time
            self._metrics["avg_creation_time"] = (
                self._metrics["avg_creation_time"] * 0.9 + elapsed * 0.1
            )
            
            self.logger.info(f"Version created: {name} v{number} ({type.value})")
            
            return version
            
        except Exception as e:
            self.logger.error(f"Failed to create version: {e}")
            raise
    
    # ========================================
    # VERSION PUBLISHING
    # ========================================
    
    async def publish_version(self, version_id: str) -> Version:
        """
        Publish a version.
        
        Args:
            version_id: Version ID
            
        Returns:
            Version: Published version
            
        Raises:
            VersionTrackerError: If version not found
        """
        version = self._get_version(version_id)
        
        if version.status == VersionStatus.PUBLISHED:
            raise VersionTrackerError(f"Version {version.name} v{version.number} is already published")
        
        # Update status
        version.status = VersionStatus.PUBLISHED
        version.published_at = datetime.utcnow()
        version.updated_at = datetime.utcnow()
        
        # Update current version
        self._current_versions[version.name] = version_id
        
        # Update next version of previous
        if version.previous_version and version.previous_version in self._versions:
            prev = self._versions[version.previous_version]
            prev.next_version = version_id
        
        self._metrics["published_versions"] += 1
        
        self.logger.info(f"Version published: {version.name} v{version.number}")
        return version
    
    async def deprecate_version(self, version_id: str) -> Version:
        """
        Deprecate a version.
        
        Args:
            version_id: Version ID
            
        Returns:
            Version: Deprecated version
        """
        version = self._get_version(version_id)
        
        version.status = VersionStatus.DEPRECATED
        version.deprecated_at = datetime.utcnow()
        version.updated_at = datetime.utcnow()
        
        self._metrics["deprecated_versions"] += 1
        self._metrics["active_versions"] -= 1
        
        self.logger.info(f"Version deprecated: {version.name} v{version.number}")
        return version
    
    async def archive_version(self, version_id: str) -> Version:
        """
        Archive a version.
        
        Args:
            version_id: Version ID
            
        Returns:
            Version: Archived version
        """
        version = self._get_version(version_id)
        
        version.status = VersionStatus.ARCHIVED
        version.updated_at = datetime.utcnow()
        
        self._metrics["archived_versions"] += 1
        self._metrics["active_versions"] -= 1
        
        self.logger.info(f"Version archived: {version.name} v{version.number}")
        return version
    
    # ========================================
    # VERSION ROLLBACK
    # ========================================
    
    async def rollback_version(
        self,
        name: str,
        target_version: str
    ) -> Version:
        """
        Rollback to a specific version.
        
        Args:
            name: Version name
            target_version: Target version number
            
        Returns:
            Version: Rolled back version
        """
        try:
            # Get target version
            target = await self.get_version_by_name_number(name, target_version)
            if not target:
                raise VersionTrackerError(f"Version {name} v{target_version} not found")
            
            # Create rollback version
            rollback = await self.create_version(
                name=name,
                number=f"{target_version}-rollback-{int(time.time())}",
                type=VersionType.HOTFIX,
                description=f"Rollback to version {target_version}",
                changelog=f"Rollback from {target.number} to {target_version}",
                tags=["rollback"],
                metadata={
                    'rollback_from': target.id,
                    'rollback_at': datetime.utcnow().isoformat()
                }
            )
            
            # Publish rollback
            await self.publish_version(rollback.id)
            
            self._metrics["rollbacks_performed"] += 1
            
            self.logger.info(f"Rollback performed: {name} to {target_version}")
            return rollback
            
        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            raise
    
    # ========================================
    # VERSION QUERY
    # ========================================
    
    def _get_version(self, version_id: str) -> Version:
        """Get version by ID"""
        version = self._versions.get(version_id)
        if not version:
            raise VersionTrackerError(f"Version {version_id} not found")
        return version
    
    async def get_version_by_name_number(
        self,
        name: str,
        number: str
    ) -> Optional[Version]:
        """Get version by name and number"""
        if name not in self._version_lists:
            return None
        
        for version_id in self._version_lists[name]:
            version = self._versions.get(version_id)
            if version and version.number == number:
                return version
        
        return None
    
    async def get_current_version(self, name: str) -> Optional[Version]:
        """Get current version"""
        version_id = self._current_versions.get(name)
        if version_id and version_id in self._versions:
            return self._versions[version_id]
        return None
    
    async def get_version_info(self, version_id: str) -> Optional[VersionInfo]:
        """Get version information"""
        version = self._versions.get(version_id)
        if not version:
            return None
        
        return VersionInfo(
            id=version.id,
            name=version.name,
            number=version.number,
            type=version.type,
            status=version.status,
            created_at=version.created_at,
            description=version.description,
            tags=version.tags,
            dependencies=version.dependencies
        )
    
    async def list_versions(
        self,
        name: Optional[str] = None,
        status: Optional[VersionStatus] = None,
        type: Optional[VersionType] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[VersionInfo]:
        """List versions with filters"""
        versions = list(self._versions.values())
        
        # Apply filters
        if name:
            versions = [v for v in versions if v.name == name]
        
        if status:
            versions = [v for v in versions if v.status == status]
        
        if type:
            versions = [v for v in versions if v.type == type]
        
        if tags:
            versions = [
                v for v in versions
                if any(tag in v.tags for tag in tags)
            ]
        
        # Sort by creation date
        versions.sort(key=lambda v: v.created_at, reverse=True)
        
        # Apply pagination
        versions = versions[offset:offset + limit]
        
        return [
            VersionInfo(
                id=v.id,
                name=v.name,
                number=v.number,
                type=v.type,
                status=v.status,
                created_at=v.created_at,
                description=v.description,
                tags=v.tags,
                dependencies=v.dependencies
            )
            for v in versions
        ]
    
    async def get_version_history(self, name: str) -> List[VersionInfo]:
        """Get full version history"""
        if name not in self._version_lists:
            return []
        
        versions = []
        for version_id in self._version_lists[name]:
            version = self._versions.get(version_id)
            if version:
                versions.append(version)
        
        versions.sort(key=lambda v: v.created_at)
        
        return [
            VersionInfo(
                id=v.id,
                name=v.name,
                number=v.number,
                type=v.type,
                status=v.status,
                created_at=v.created_at,
                description=v.description,
                tags=v.tags,
                dependencies=v.dependencies
            )
            for v in versions
        ]
    
    # ========================================
    # VERSION COMPARISON
    # ========================================
    
    async def compare_versions(
        self,
        version_id1: str,
        version_id2: str
    ) -> VersionDiff:
        """
        Compare two versions.
        
        Args:
            version_id1: First version ID
            version_id2: Second version ID
            
        Returns:
            VersionDiff: Version differences
        """
        version1 = self._get_version(version_id1)
        version2 = self._get_version(version_id2)
        
        # Compare metadata
        changes = []
        additions = []
        removals = []
        modifications = []
        
        # Compare metadata
        for key in set(version1.metadata.keys()) | set(version2.metadata.keys()):
            if key not in version1.metadata:
                additions.append(f"Added metadata: {key}")
            elif key not in version2.metadata:
                removals.append(f"Removed metadata: {key}")
            elif version1.metadata[key] != version2.metadata[key]:
                modifications.append(f"Changed metadata: {key} from {version1.metadata[key]} to {version2.metadata[key]}")
        
        # Compare tags
        tags1 = set(version1.tags)
        tags2 = set(version2.tags)
        
        for tag in tags2 - tags1:
            additions.append(f"Added tag: {tag}")
        for tag in tags1 - tags2:
            removals.append(f"Removed tag: {tag}")
        
        # Compare dependencies
        deps1 = set(version1.dependencies)
        deps2 = set(version2.dependencies)
        
        for dep in deps2 - deps1:
            additions.append(f"Added dependency: {dep}")
        for dep in deps1 - deps2:
            removals.append(f"Removed dependency: {dep}")
        
        # Build changes list
        changes = [
            {'type': 'addition', 'description': desc}
            for desc in additions
        ] + [
            {'type': 'removal', 'description': desc}
            for desc in removals
        ] + [
            {'type': 'modification', 'description': desc}
            for desc in modifications
        ]
        
        return VersionDiff(
            version_from=version1.number,
            version_to=version2.number,
            changes=changes,
            additions=additions,
            removals=removals,
            modifications=modifications
        )
    
    # ========================================
    # HELPER FUNCTIONS
    # ========================================
    
    def _validate_version_number(self, version: str) -> bool:
        """Validate semantic version number"""
        import re
        pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9-]+))?(?:\+([a-zA-Z0-9-]+))?$'
        return bool(re.match(pattern, version))
    
    # ========================================
    # CLEANUP
    # ========================================
    
    async def _cleanup_old_versions(self) -> None:
        """Clean up old versions"""
        if not self.config.auto_cleanup:
            return
        
        cutoff = datetime.utcnow() - timedelta(days=self.config.keep_versions_days)
        
        for version in list(self._versions.values()):
            if version.status in [VersionStatus.ARCHIVED, VersionStatus.DELETED]:
                if version.created_at < cutoff:
                    await self._delete_version(version.id)
        
        # Check max versions
        if len(self._versions) > self.config.max_versions:
            # Delete oldest archived versions
            archived = [
                v for v in self._versions.values()
                if v.status == VersionStatus.ARCHIVED
            ]
            archived.sort(key=lambda v: v.created_at)
            
            to_delete = len(self._versions) - self.config.max_versions
            for version in archived[:to_delete]:
                await self._delete_version(version.id)
    
    async def _delete_version(self, version_id: str) -> None:
        """Delete a version"""
        if version_id not in self._versions:
            return
        
        version = self._versions[version_id]
        
        # Remove from lists
        if version.name in self._version_lists:
            self._version_lists[version.name] = [
                vid for vid in self._version_lists[version.name]
                if vid != version_id
            ]
        
        # Remove from current
        if self._current_versions.get(version.name) == version_id:
            # Find previous version
            if version.previous_version and version.previous_version in self._versions:
                self._current_versions[version.name] = version.previous_version
            else:
                del self._current_versions[version.name]
        
        # Update metrics
        if version.status != VersionStatus.DELETED:
            self._metrics["active_versions"] -= 1
        
        # Delete
        version.status = VersionStatus.DELETED
        
        self.logger.info(f"Version deleted: {version.name} v{version.number}")
    
    # ========================================
    # BACKGROUND TASKS
    # ========================================
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop"""
        while self._running:
            try:
                await self._cleanup_old_versions()
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
        """Get tracker metrics"""
        return {
            **self._metrics,
            "total_versions": len(self._versions),
            "version_names": len(self._version_lists),
            "current_versions": len(self._current_versions)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check tracker health"""
        health = {
            'status': 'healthy',
            'versions': {
                'total': len(self._versions),
                'active': self._metrics["active_versions"],
                'published': self._metrics["published_versions"],
                'deprecated': self._metrics["deprecated_versions"],
                'archived': self._metrics["archived_versions"]
            }
        }
        
        if len(self._versions) > self.config.max_versions * 0.9:
            health['status'] = 'degraded'
            health['warning'] = 'Approaching max versions limit'
        
        return health
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the version tracker"""
        self._running = True
        
        # Start background tasks
        self._tasks.append(asyncio.create_task(self._cleanup_loop()))
        self._tasks.append(asyncio.create_task(self._health_loop()))
        
        self.logger.info("VersionTracker started")
    
    async def stop(self) -> None:
        """Stop the version tracker"""
        self._running = False
        
        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self.logger.info("VersionTracker stopped")


# ========================================
# DEPENDENCY INJECTION
# ========================================

_version_tracker: Optional[VersionTracker] = None


def get_version_tracker() -> VersionTracker:
    """Get singleton instance of VersionTracker"""
    global _version_tracker
    if _version_tracker is None:
        _version_tracker = VersionTracker()
    return _version_tracker


def reset_version_tracker() -> None:
    """Reset the version tracker (for testing)"""
    global _version_tracker
    if _version_tracker:
        asyncio.create_task(_version_tracker.stop())
    _version_tracker = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'VersionTracker',
    'VersionConfig',
    'Version',
    'VersionInfo',
    'VersionDiff',
    'VersionStatus',
    'VersionType',
    'get_version_tracker',
    'reset_version_tracker'
]
