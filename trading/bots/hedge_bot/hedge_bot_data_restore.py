# trading/bots/hedge_bot/hedge_bot_data_restore.py

import asyncio
import logging
import time
import json
import hashlib
import pickle
import zlib
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable, BinaryIO
from decimal import Decimal
from collections import defaultdict
import aiofiles
import aiohttp

logger = logging.getLogger(__name__)


class RestoreType(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"
    POINT_IN_TIME = "point_in_time"
    SELECTIVE = "selective"
    SCHEMA_ONLY = "schema_only"
    DATA_ONLY = "data_only"


class RestoreStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    VALIDATING = "validating"
    EXTRACTING = "extracting"
    LOADING = "loading"


class RestoreSource(str, Enum):
    LOCAL = "local"
    REMOTE = "remote"
    CLOUD = "cloud"
    DATABASE = "database"
    SNAPSHOT = "snapshot"
    BACKUP = "backup"
    ARCHIVE = "archive"


@dataclass
class RestoreConfig:
    type: RestoreType
    source: RestoreSource
    source_path: str
    destination_path: str
    timestamp: Optional[float] = None
    include_tables: Optional[List[str]] = None
    exclude_tables: Optional[List[str]] = None
    include_data: bool = True
    include_schema: bool = True
    validate: bool = True
    overwrite: bool = False
    max_parallel: int = 4
    batch_size: int = 1000
    compression: bool = True
    encryption: bool = True
    timeout: int = 3600
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RestoreResult:
    id: str
    type: RestoreType
    source: RestoreSource
    status: RestoreStatus
    start_time: float
    end_time: Optional[float] = None
    total_size: int = 0
    restored_size: int = 0
    total_objects: int = 0
    restored_objects: int = 0
    failed_objects: int = 0
    skipped_objects: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    checksum: Optional[str] = None
    validation_status: Optional[str] = None


@dataclass
class RestorePoint:
    id: str
    timestamp: float
    type: RestoreType
    source: str
    size: int
    objects: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    checksum: Optional[str] = None


@dataclass
class RestoreJob:
    id: str
    config: RestoreConfig
    status: RestoreStatus
    progress: float
    current_stage: str
    start_time: float
    updated_time: float
    result: Optional[RestoreResult] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataRestoreManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._jobs: Dict[str, RestoreJob] = {}
        self._results: Dict[str, RestoreResult] = {}
        self._restore_points: Dict[str, RestorePoint] = {}
        self._handlers: Dict[RestoreSource, Callable] = {}
        self._validators: List[Callable] = []
        self._observers: List[Callable] = []
        self._running = False
        self._temp_dir: Optional[str] = None
        
        self._initialize_handlers()
        self._initialize_restore_points()

    def _initialize_handlers(self) -> None:
        self.register_handler(RestoreSource.LOCAL, self._restore_local)
        self.register_handler(RestoreSource.REMOTE, self._restore_remote)
        self.register_handler(RestoreSource.CLOUD, self._restore_cloud)
        self.register_handler(RestoreSource.DATABASE, self._restore_database)
        self.register_handler(RestoreSource.SNAPSHOT, self._restore_snapshot)
        self.register_handler(RestoreSource.BACKUP, self._restore_backup)
        self.register_handler(RestoreSource.ARCHIVE, self._restore_archive)

    def _initialize_restore_points(self) -> None:
        pass

    def register_handler(self, source_type: RestoreSource, handler: Callable) -> None:
        self._handlers[source_type] = handler

    def register_validator(self, validator: Callable) -> None:
        self._validators.append(validator)

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def restore(
        self,
        config: RestoreConfig,
        job_id: Optional[str] = None,
        dry_run: bool = False
    ) -> RestoreResult:
        async with self._lock:
            if job_id is None:
                job_id = hashlib.md5(f"{config.source_path}_{time.time()}".encode()).hexdigest()
            
            job = RestoreJob(
                id=job_id,
                config=config,
                status=RestoreStatus.PENDING,
                progress=0.0,
                current_stage="initializing",
                start_time=time.time(),
                updated_time=time.time()
            )
            
            self._jobs[job_id] = job
            
            result = RestoreResult(
                id=hashlib.md5(f"{job_id}_{time.time()}".encode()).hexdigest(),
                type=config.type,
                source=config.source,
                status=RestoreStatus.PENDING,
                start_time=time.time()
            )
            
            try:
                await self._notify_observers("restore_started", job)
                
                job.status = RestoreStatus.RUNNING
                job.current_stage = "validating"
                
                if not await self._validate_restore(config):
                    raise ValueError("Restore validation failed")
                
                job.current_stage = "extracting"
                job.progress = 10.0
                
                if config.source not in self._handlers:
                    raise ValueError(f"No handler for source: {config.source}")
                
                handler = self._handlers[config.source]
                
                if dry_run:
                    job.current_stage = "dry_run"
                    job.progress = 50.0
                    await asyncio.sleep(0.5)
                else:
                    await self._prepare_restore(config)
                    
                    job.current_stage = "loading"
                    job.progress = 30.0
                    
                    result = await handler(config, job)
                    
                    await self._post_restore(result, config)
                
                job.status = RestoreStatus.COMPLETED
                job.progress = 100.0
                result.status = RestoreStatus.COMPLETED
                result.end_time = time.time()
                
                self._results[result.id] = result
                job.result = result
                
                await self._notify_observers("restore_completed", job, result)
                
            except Exception as e:
                logger.error(f"Restore failed: {e}")
                job.status = RestoreStatus.FAILED
                result.status = RestoreStatus.FAILED
                result.errors.append({"error": str(e), "timestamp": time.time()})
                result.end_time = time.time()
                
                await self._notify_observers("restore_failed", job, result)
            
            return result

    async def _validate_restore(self, config: RestoreConfig) -> bool:
        if not os.path.exists(config.source_path):
            if config.source == RestoreSource.LOCAL:
                logger.error(f"Source path does not exist: {config.source_path}")
                return False
        
        if config.destination_path:
            os.makedirs(os.path.dirname(config.destination_path), exist_ok=True)
        
        for validator in self._validators:
            try:
                if asyncio.iscoroutinefunction(validator):
                    if not await validator(config):
                        return False
                else:
                    if not validator(config):
                        return False
            except Exception as e:
                logger.error(f"Validator error: {e}")
                return False
        
        return True

    async def _prepare_restore(self, config: RestoreConfig) -> None:
        self._temp_dir = tempfile.mkdtemp()
        
        if not config.overwrite and os.path.exists(config.destination_path):
            backup_path = f"{config.destination_path}.backup_{int(time.time())}"
            shutil.copytree(config.destination_path, backup_path)
            logger.info(f"Created backup at: {backup_path}")

    async def _post_restore(self, result: RestoreResult, config: RestoreConfig) -> None:
        if config.validate and result.status == RestoreStatus.COMPLETED:
            await self._validate_restored_data(result, config)

    async def _validate_restored_data(self, result: RestoreResult, config: RestoreConfig) -> None:
        try:
            result.validation_status = "validating"
            
            if os.path.exists(config.destination_path):
                await self._validate_files(config.destination_path, result)
                result.validation_status = "validated"
            else:
                result.validation_status = "failed"
                result.errors.append({
                    "error": "Destination path does not exist after restore",
                    "timestamp": time.time()
                })
                
        except Exception as e:
            logger.error(f"Validation error: {e}")
            result.validation_status = "failed"
            result.errors.append({"error": str(e), "timestamp": time.time()})

    async def _validate_files(self, path: str, result: RestoreResult) -> None:
        if os.path.isfile(path):
            try:
                with open(path, 'rb') as f:
                    data = f.read()
                    checksum = hashlib.sha256(data).hexdigest()
                    
                    if result.checksum and result.checksum != checksum:
                        result.warnings.append(f"Checksum mismatch for {path}")
                        
            except Exception as e:
                result.warnings.append(f"Could not validate {path}: {e}")
                
        elif os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    await self._validate_files(os.path.join(root, file), result)

    async def _restore_local(self, config: RestoreConfig, job: RestoreJob) -> RestoreResult:
        result = await self._create_empty_result(config)
        
        source_path = config.source_path
        dest_path = config.destination_path
        
        if os.path.isfile(source_path):
            await self._restore_file(source_path, dest_path, result, job)
        elif os.path.isdir(source_path):
            await self._restore_directory(source_path, dest_path, result, job)
        else:
            raise ValueError(f"Invalid source path: {source_path}")
        
        return result

    async def _restore_remote(self, config: RestoreConfig, job: RestoreJob) -> RestoreResult:
        result = await self._create_empty_result(config)
        
        url = config.source_path
        dest_path = config.destination_path
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP error: {response.status}")
                
                content = await response.read()
                result.total_size = len(content)
                
                if os.path.isdir(dest_path) or dest_path.endswith('/'):
                    file_name = os.path.basename(url)
                    dest_file = os.path.join(dest_path, file_name)
                else:
                    dest_file = dest_path
                
                async with aiofiles.open(dest_file, 'wb') as f:
                    await f.write(content)
                
                result.restored_size = len(content)
                result.restored_objects = 1
                result.total_objects = 1
        
        return result

    async def _restore_cloud(self, config: RestoreConfig, job: RestoreJob) -> RestoreResult:
        result = await self._create_empty_result(config)
        
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 not installed")
        
        bucket = config.metadata.get("bucket")
        key = config.metadata.get("key")
        region = config.metadata.get("region", "us-east-1")
        
        if not bucket or not key:
            raise ValueError("Bucket and key required for S3 restore")
        
        s3 = boto3.client('s3', region_name=region)
        response = s3.get_object(Bucket=bucket, Key=key)
        
        content = response['Body'].read()
        result.total_size = len(content)
        
        dest_file = config.destination_path
        if os.path.isdir(dest_file):
            dest_file = os.path.join(dest_file, os.path.basename(key))
        
        async with aiofiles.open(dest_file, 'wb') as f:
            await f.write(content)
        
        result.restored_size = len(content)
        result.restored_objects = 1
        result.total_objects = 1
        
        return result

    async def _restore_database(self, config: RestoreConfig, job: RestoreJob) -> RestoreResult:
        result = await self._create_empty_result(config)
        
        import sqlalchemy
        
        connection_string = config.source_path
        dest_connection = config.destination_path
        
        engine = sqlalchemy.create_engine(connection_string)
        dest_engine = sqlalchemy.create_engine(dest_connection)
        
        inspector = sqlalchemy.inspect(engine)
        tables = inspector.get_table_names()
        
        if config.include_tables:
            tables = [t for t in tables if t in config.include_tables]
        if config.exclude_tables:
            tables = [t for t in tables if t not in config.exclude_tables]
        
        result.total_objects = len(tables)
        
        for table in tables:
            try:
                if config.include_schema:
                    metadata = sqlalchemy.MetaData()
                    table_obj = sqlalchemy.Table(table, metadata, autoload_with=engine)
                    table_obj.create(dest_engine, checkfirst=True)
                
                if config.include_data:
                    df = pd.read_sql_table(table, engine)
                    
                    if config.overwrite:
                        df.to_sql(table, dest_engine, if_exists='replace', index=False)
                    else:
                        df.to_sql(table, dest_engine, if_exists='append', index=False)
                    
                    result.restored_objects += 1
                    
            except Exception as e:
                logger.error(f"Error restoring table {table}: {e}")
                result.failed_objects += 1
                result.errors.append({
                    "table": table,
                    "error": str(e),
                    "timestamp": time.time()
                })
        
        return result

    async def _restore_snapshot(self, config: RestoreConfig, job: RestoreJob) -> RestoreResult:
        result = await self._create_empty_result(config)
        
        snapshot_path = config.source_path
        dest_path = config.destination_path
        
        if not os.path.exists(snapshot_path):
            raise ValueError(f"Snapshot not found: {snapshot_path}")
        
        with open(snapshot_path, 'rb') as f:
            data = f.read()
            result.total_size = len(data)
            
            if config.compression:
                data = zlib.decompress(data)
            
            snapshot_data = pickle.loads(data)
            
            if 'objects' in snapshot_data:
                result.total_objects = len(snapshot_data['objects'])
                
                for obj in snapshot_data['objects']:
                    obj_path = os.path.join(dest_path, obj.get('path', ''))
                    os.makedirs(os.path.dirname(obj_path), exist_ok=True)
                    
                    with open(obj_path, 'wb') as obj_file:
                        obj_file.write(obj.get('data', b''))
                    
                    result.restored_objects += 1
                    result.restored_size += len(obj.get('data', b''))
        
        return result

    async def _restore_backup(self, config: RestoreConfig, job: RestoreJob) -> RestoreResult:
        result = await self._create_empty_result(config)
        
        backup_path = config.source_path
        dest_path = config.destination_path
        
        if backup_path.endswith('.tar.gz') or backup_path.endswith('.tgz'):
            import tarfile
            with tarfile.open(backup_path, 'r:gz') as tar:
                result.total_objects = len(tar.getmembers())
                tar.extractall(path=dest_path)
                result.restored_objects = result.total_objects
                
                for member in tar.getmembers():
                    result.restored_size += member.size
                    
        elif backup_path.endswith('.zip'):
            import zipfile
            with zipfile.ZipFile(backup_path, 'r') as zip_ref:
                result.total_objects = len(zip_ref.namelist())
                zip_ref.extractall(dest_path)
                result.restored_objects = result.total_objects
                
                for info in zip_ref.infolist():
                    result.restored_size += info.file_size
        else:
            raise ValueError(f"Unsupported backup format: {backup_path}")
        
        return result

    async def _restore_archive(self, config: RestoreConfig, job: RestoreJob) -> RestoreResult:
        result = await self._create_empty_result(config)
        
        archive_path = config.source_path
        dest_path = config.destination_path
        
        if archive_path.endswith('.tar'):
            import tarfile
            with tarfile.open(archive_path, 'r') as tar:
                result.total_objects = len(tar.getmembers())
                tar.extractall(path=dest_path)
                result.restored_objects = result.total_objects
                
        elif archive_path.endswith('.tar.gz') or archive_path.endswith('.tgz'):
            import tarfile
            with tarfile.open(archive_path, 'r:gz') as tar:
                result.total_objects = len(tar.getmembers())
                tar.extractall(path=dest_path)
                result.restored_objects = result.total_objects
                
        elif archive_path.endswith('.zip'):
            import zipfile
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                result.total_objects = len(zip_ref.namelist())
                zip_ref.extractall(dest_path)
                result.restored_objects = result.total_objects
                
        else:
            raise ValueError(f"Unsupported archive format: {archive_path}")
        
        return result

    async def _restore_file(
        self,
        source: str,
        dest: str,
        result: RestoreResult,
        job: RestoreJob
    ) -> None:
        result.total_objects = 1
        
        if os.path.isdir(dest):
            dest = os.path.join(dest, os.path.basename(source))
        
        async with aiofiles.open(source, 'rb') as f:
            data = await f.read()
            result.total_size = len(data)
        
        async with aiofiles.open(dest, 'wb') as f:
            await f.write(data)
        
        result.restored_size = len(data)
        result.restored_objects = 1

    async def _restore_directory(
        self,
        source: str,
        dest: str,
        result: RestoreResult,
        job: RestoreJob
    ) -> None:
        total_files = 0
        total_size = 0
        
        for root, dirs, files in os.walk(source):
            for file in files:
                total_files += 1
                src_file = os.path.join(root, file)
                rel_path = os.path.relpath(src_file, source)
                dest_file = os.path.join(dest, rel_path)
                
                os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                
                file_size = os.path.getsize(src_file)
                total_size += file_size
                
                if not config.include_data:
                    continue
                
                shutil.copy2(src_file, dest_file)
                result.restored_objects += 1
                result.restored_size += file_size
                
                job.progress = (result.restored_objects / total_files) * 100
        
        result.total_objects = total_files
        result.total_size = total_size

    async def _create_empty_result(self, config: RestoreConfig) -> RestoreResult:
        return RestoreResult(
            id=hashlib.md5(f"{config.source_path}_{time.time()}".encode()).hexdigest(),
            type=config.type,
            source=config.source,
            status=RestoreStatus.RUNNING,
            start_time=time.time()
        )

    async def get_restore_job(self, job_id: str) -> Optional[RestoreJob]:
        return self._jobs.get(job_id)

    async def get_restore_result(self, result_id: str) -> Optional[RestoreResult]:
        return self._results.get(result_id)

    async def get_restore_points(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[RestorePoint]:
        points = list(self._restore_points.values())
        points.sort(key=lambda p: p.timestamp, reverse=True)
        return points[offset:offset + limit]

    async def create_restore_point(
        self,
        source: str,
        type: RestoreType = RestoreType.SNAPSHOT,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RestorePoint:
        point_id = hashlib.md5(f"{source}_{time.time()}".encode()).hexdigest()
        
        objects = []
        total_size = 0
        
        if os.path.isfile(source):
            size = os.path.getsize(source)
            total_size = size
            objects.append(source)
            
        elif os.path.isdir(source):
            for root, dirs, files in os.walk(source):
                for file in files:
                    file_path = os.path.join(root, file)
                    objects.append(file_path)
                    total_size += os.path.getsize(file_path)
        
        point = RestorePoint(
            id=point_id,
            timestamp=time.time(),
            type=type,
            source=source,
            size=total_size,
            objects=objects,
            metadata=metadata or {}
        )
        
        self._restore_points[point_id] = point
        return point

    async def cancel_restore(self, job_id: str) -> bool:
        if job_id not in self._jobs:
            return False
        
        job = self._jobs[job_id]
        if job.status in [RestoreStatus.COMPLETED, RestoreStatus.FAILED]:
            return False
        
        job.status = RestoreStatus.CANCELLED
        await self._notify_observers("restore_cancelled", job)
        return True

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
        total_jobs = len(self._jobs)
        completed = len([j for j in self._jobs.values() if j.status == RestoreStatus.COMPLETED])
        failed = len([j for j in self._jobs.values() if j.status == RestoreStatus.FAILED])
        running = len([j for j in self._jobs.values() if j.status == RestoreStatus.RUNNING])
        
        total_restored = sum(r.restored_size for r in self._results.values())
        total_objects = sum(r.restored_objects for r in self._results.values())
        
        return {
            "total_jobs": total_jobs,
            "completed": completed,
            "failed": failed,
            "running": running,
            "restore_points": len(self._restore_points),
            "total_restored_size": total_restored,
            "total_restored_objects": total_objects,
            "handlers": len(self._handlers),
            "validators": len(self._validators),
            "running": self._running
        }


__all__ = [
    "RestoreType",
    "RestoreStatus",
    "RestoreSource",
    "RestoreConfig",
    "RestoreResult",
    "RestorePoint",
    "RestoreJob",
    "DataRestoreManager"
]
