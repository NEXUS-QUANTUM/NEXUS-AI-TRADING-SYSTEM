# trading/bots/hedge_bot/hedge_bot_data_sync.py

import asyncio
import logging
import time
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict

logger = logging.getLogger(__name__)


class SyncType(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    BIDIRECTIONAL = "bidirectional"
    ONE_WAY = "one_way"
    REAL_TIME = "realtime"
    SCHEDULED = "scheduled"
    EVENT_DRIVEN = "event_driven"
    BATCH = "batch"


class SyncStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    CONFLICT = "conflict"
    RESOLVING = "resolving"


class SyncDirection(str, Enum):
    PUSH = "push"
    PULL = "pull"
    BOTH = "both"


@dataclass
class SyncConfig:
    id: str
    name: str
    type: SyncType
    direction: SyncDirection
    source: str
    destination: str
    source_config: Dict[str, Any]
    destination_config: Dict[str, Any]
    schedule: Optional[str] = None
    batch_size: int = 1000
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: int = 300
    conflict_resolution: str = "source_wins"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    enabled: bool = True


@dataclass
class SyncJob:
    id: str
    config_id: str
    status: SyncStatus
    total_records: int = 0
    synced_records: int = 0
    failed_records: int = 0
    conflicts: int = 0
    start_time: float
    end_time: Optional[float] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncConflict:
    id: str
    job_id: str
    source_value: Any
    destination_value: Any
    resolved_value: Any
    resolution: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncMetrics:
    total_syncs: int
    successful_syncs: int
    failed_syncs: int
    total_records: int
    total_failures: int
    total_conflicts: int
    avg_sync_time: float
    last_sync_time: float
    last_sync_status: SyncStatus


class DataSyncManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._configs: Dict[str, SyncConfig] = {}
        self._jobs: Dict[str, SyncJob] = {}
        self._conflicts: Dict[str, SyncConflict] = {}
        self._connectors: Dict[str, Callable] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_default_connectors()

    def _initialize_default_connectors(self) -> None:
        pass

    def register_connector(self, name: str, connector: Callable) -> None:
        self._connectors[name] = connector

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def create_config(
        self,
        name: str,
        type: SyncType,
        direction: SyncDirection,
        source: str,
        destination: str,
        source_config: Dict[str, Any],
        destination_config: Dict[str, Any],
        schedule: Optional[str] = None,
        batch_size: int = 1000,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: int = 300,
        conflict_resolution: str = "source_wins",
        metadata: Optional[Dict[str, Any]] = None
    ) -> SyncConfig:
        async with self._lock:
            config_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            config = SyncConfig(
                id=config_id,
                name=name,
                type=type,
                direction=direction,
                source=source,
                destination=destination,
                source_config=source_config,
                destination_config=destination_config,
                schedule=schedule,
                batch_size=batch_size,
                max_retries=max_retries,
                retry_delay=retry_delay,
                timeout=timeout,
                conflict_resolution=conflict_resolution,
                metadata=metadata or {}
            )
            
            self._configs[config_id] = config
            await self._notify_observers("config_created", config)
            return config

    async def sync(self, config_id: str) -> Optional[SyncJob]:
        async with self._lock:
            if config_id not in self._configs:
                return None
            
            config = self._configs[config_id]
            
            if not config.enabled:
                return None
            
            job = SyncJob(
                id=hashlib.md5(f"{config_id}_{time.time()}".encode()).hexdigest(),
                config_id=config_id,
                status=SyncStatus.RUNNING,
                start_time=time.time()
            )
            
            self._jobs[job.id] = job
            await self._notify_observers("sync_started", job)
            
            try:
                if config.source not in self._connectors:
                    raise ValueError(f"Connector not found: {config.source}")
                
                if config.destination not in self._connectors:
                    raise ValueError(f"Connector not found: {config.destination}")
                
                source_connector = self._connectors[config.source]
                dest_connector = self._connectors[config.destination]
                
                # Get data from source
                data = await source_connector("read", config.source_config)
                job.total_records = len(data) if isinstance(data, list) else 1
                
                # Process data
                processed_data = await self._process_data(data, config)
                
                # Write to destination
                result = await dest_connector("write", config.destination_config, processed_data)
                
                job.synced_records = len(processed_data) if isinstance(processed_data, list) else 1
                job.status = SyncStatus.COMPLETED
                job.end_time = time.time()
                
                await self._notify_observers("sync_completed", job)
                return job
                
            except Exception as e:
                logger.error(f"Sync failed: {e}")
                job.status = SyncStatus.FAILED
                job.error = str(e)
                job.end_time = time.time()
                await self._notify_observers("sync_failed", job)
                return job

    async def _process_data(self, data: Any, config: SyncConfig) -> Any:
        if config.type == SyncType.FULL:
            return data
        elif config.type == SyncType.INCREMENTAL:
            return await self._process_incremental(data, config)
        elif config.type == SyncType.DIFFERENTIAL:
            return await self._process_differential(data, config)
        elif config.type == SyncType.BIDIRECTIONAL:
            return await self._process_bidirectional(data, config)
        else:
            return data

    async def _process_incremental(self, data: Any, config: SyncConfig) -> Any:
        # Incremental sync: only sync new/changed data
        if isinstance(data, list):
            return data[-config.batch_size:] if len(data) > config.batch_size else data
        return data

    async def _process_differential(self, data: Any, config: SyncConfig) -> Any:
        # Differential sync: sync only differences
        if isinstance(data, list):
            # Simulate differential processing
            return data
        return data

    async def _process_bidirectional(self, data: Any, config: SyncConfig) -> Any:
        # Bidirectional sync: sync both ways
        if isinstance(data, list):
            return data
        return data

    async def resolve_conflict(
        self,
        conflict_id: str,
        resolution: str,
        resolved_value: Any
    ) -> Optional[SyncConflict]:
        async with self._lock:
            if conflict_id not in self._conflicts:
                return None
            
            conflict = self._conflicts[conflict_id]
            conflict.resolved_value = resolved_value
            conflict.resolution = resolution
            
            await self._notify_observers("conflict_resolved", conflict)
            return conflict

    async def get_config(self, config_id: str) -> Optional[SyncConfig]:
        return self._configs.get(config_id)

    async def get_configs(self) -> List[SyncConfig]:
        return list(self._configs.values())

    async def get_job(self, job_id: str) -> Optional[SyncJob]:
        return self._jobs.get(job_id)

    async def get_jobs(
        self,
        status: Optional[SyncStatus] = None,
        config_id: Optional[str] = None,
        limit: int = 100
    ) -> List[SyncJob]:
        jobs = list(self._jobs.values())
        
        if status:
            jobs = [j for j in jobs if j.status == status]
        if config_id:
            jobs = [j for j in jobs if j.config_id == config_id]
        
        jobs.sort(key=lambda j: j.start_time, reverse=True)
        return jobs[:limit]

    async def get_conflict(self, conflict_id: str) -> Optional[SyncConflict]:
        return self._conflicts.get(conflict_id)

    async def get_conflicts(
        self,
        job_id: Optional[str] = None,
        resolved: bool = False,
        limit: int = 100
    ) -> List[SyncConflict]:
        conflicts = list(self._conflicts.values())
        
        if job_id:
            conflicts = [c for c in conflicts if c.job_id == job_id]
        if resolved:
            conflicts = [c for c in conflicts if c.resolution != "pending"]
        
        conflicts.sort(key=lambda c: c.timestamp, reverse=True)
        return conflicts[:limit]

    async def enable_config(self, config_id: str) -> bool:
        if config_id in self._configs:
            self._configs[config_id].enabled = True
            return True
        return False

    async def disable_config(self, config_id: str) -> bool:
        if config_id in self._configs:
            self._configs[config_id].enabled = False
            return True
        return False

    async def delete_config(self, config_id: str) -> bool:
        if config_id in self._configs:
            del self._configs[config_id]
            return True
        return False

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "configs": len(self._configs),
            "jobs": len(self._jobs),
            "conflicts": len(self._conflicts),
            "connectors": len(self._connectors),
            "running": self._running
        }


__all__ = [
    "SyncType",
    "SyncStatus",
    "SyncDirection",
    "SyncConfig",
    "SyncJob",
    "SyncConflict",
    "SyncMetrics",
    "DataSyncManager"
]
