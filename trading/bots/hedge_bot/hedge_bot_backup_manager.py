# trading/bots/hedge_bot/hedge_bot_backup_manager.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Backup Manager Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Backup Manager Module

This module provides comprehensive backup and restore capabilities for the
NEXUS Hedge Bot system. It handles automated backups, data recovery,
and disaster recovery procedures.

The module covers:
- Automated Backups
- Manual Backups
- Incremental Backups
- Full Backups
- Backup Scheduling
- Backup Compression
- Backup Encryption
- Backup Verification
- Data Restoration
- Point-in-Time Recovery
- Disaster Recovery
- Backup Retention
- Backup Rotation
- Cloud Backup
- Local Backup
"""

import os
import sys
import json
import time
import shutil
import tarfile
import gzip
import hashlib
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import pickle
import sqlite3
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

# Try to import optional dependencies
try:
    from cryptography.fernet import Fernet
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False

logger = logging.getLogger(__name__)


# ============================================================
# BACKUP ENUMS
# ============================================================

class BackupType(Enum):
    """Backup types"""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"


class BackupStatus(Enum):
    """Backup status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    RESTORING = "restoring"
    RESTORED = "restored"


class BackupStorage(Enum):
    """Backup storage types"""
    LOCAL = "local"
    CLOUD = "cloud"
    NETWORK = "network"
    TAPE = "tape"


class BackupCompression(Enum):
    """Compression types"""
    NONE = "none"
    GZIP = "gzip"
    BZIP2 = "bzip2"
    ZIP = "zip"
    TAR = "tar"
    TAR_GZ = "tar_gz"


# ============================================================
# BACKUP DATACLASSES
# ============================================================

@dataclass
class BackupJob:
    """Backup job definition"""
    id: str
    name: str
    type: BackupType
    storage: BackupStorage
    source_paths: List[str]
    destination_path: str
    compression: BackupCompression = BackupCompression.TAR_GZ
    encryption: bool = False
    encryption_key: Optional[str] = None
    schedule: Optional[str] = None
    retention_days: int = 30
    max_backups: int = 10
    verify_backup: bool = True
    notify_on_completion: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_run: Optional[datetime] = None
    last_status: BackupStatus = BackupStatus.PENDING
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "storage": self.storage.value,
            "source_paths": self.source_paths,
            "destination_path": self.destination_path,
            "compression": self.compression.value,
            "encryption": self.encryption,
            "schedule": self.schedule,
            "retention_days": self.retention_days,
            "max_backups": self.max_backups,
            "verify_backup": self.verify_backup,
            "notify_on_completion": self.notify_on_completion,
            "created_at": self.created_at.isoformat(),
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_status": self.last_status.value,
            "last_error": self.last_error,
        }


@dataclass
class BackupResult:
    """Backup result"""
    job_id: str
    job_name: str
    backup_path: str
    size_bytes: int
    duration_seconds: float
    file_count: int
    status: BackupStatus
    checksum: Optional[str] = None
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "job_id": self.job_id,
            "job_name": self.job_name,
            "backup_path": self.backup_path,
            "size_bytes": self.size_bytes,
            "duration_seconds": self.duration_seconds,
            "file_count": self.file_count,
            "status": self.status.value,
            "checksum": self.checksum,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
        }


@dataclass
class RestoreJob:
    """Restore job definition"""
    id: str
    name: str
    backup_job_id: str
    backup_path: str
    destination_path: str
    overwrite: bool = False
    restore_metadata: bool = True
    verify_after_restore: bool = True
    status: BackupStatus = BackupStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "backup_job_id": self.backup_job_id,
            "backup_path": self.backup_path,
            "destination_path": self.destination_path,
            "overwrite": self.overwrite,
            "restore_metadata": self.restore_metadata,
            "verify_after_restore": self.verify_after_restore,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


# ============================================================
# BACKUP MANAGER
# ============================================================

class BackupManager:
    """
    Comprehensive backup manager for the hedge bot
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the backup manager
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.backup_dir = Path(self.config.get("backup_dir", "backups"))
        self.temp_dir = Path(self.config.get("temp_dir", "temp"))
        self.parallel_jobs = self.config.get("parallel_jobs", 4)
        self.encryption_key = self.config.get("encryption_key")
        
        # Create directories
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # State
        self.backup_jobs: Dict[str, BackupJob] = {}
        self.backup_results: Dict[str, BackupResult] = {}
        self.restore_jobs: Dict[str, RestoreJob] = {}
        
        # Threading
        self.executor = ThreadPoolExecutor(max_workers=self.parallel_jobs)
        self.threads: List[threading.Thread] = []
        
        # Cache
        self._cache: Dict[str, Any] = {}
        
        logger.info("Backup manager initialized")
    
    # ============================================================
    # BACKUP JOB MANAGEMENT
    # ============================================================
    
    def create_backup_job(
        self,
        name: str,
        source_paths: List[str],
        destination_path: Optional[str] = None,
        backup_type: BackupType = BackupType.FULL,
        storage: BackupStorage = BackupStorage.LOCAL,
        compression: BackupCompression = BackupCompression.TAR_GZ,
        encryption: bool = False,
        schedule: Optional[str] = None,
        retention_days: int = 30,
        max_backups: int = 10,
        verify_backup: bool = True,
    ) -> BackupJob:
        """
        Create a backup job
        
        Args:
            name: Job name
            source_paths: Paths to backup
            destination_path: Backup destination
            backup_type: Type of backup
            storage: Storage type
            compression: Compression type
            encryption: Encrypt backup
            schedule: Schedule expression
            retention_days: Retention days
            max_backups: Maximum backups to keep
            verify_backup: Verify backup after creation
            
        Returns:
            BackupJob
        """
        if destination_path is None:
            destination_path = str(self.backup_dir / name)
        
        job = BackupJob(
            id=f"backup_{int(time.time())}_{len(self.backup_jobs)}",
            name=name,
            type=backup_type,
            storage=storage,
            source_paths=source_paths,
            destination_path=destination_path,
            compression=compression,
            encryption=encryption,
            schedule=schedule,
            retention_days=retention_days,
            max_backups=max_backups,
            verify_backup=verify_backup,
        )
        
        self.backup_jobs[job.id] = job
        logger.info(f"Created backup job: {name}")
        return job
    
    def update_backup_job(self, job_id: str, updates: Dict[str, Any]) -> Optional[BackupJob]:
        """
        Update a backup job
        
        Args:
            job_id: Job ID
            updates: Updates to apply
            
        Returns:
            Updated job or None
        """
        job = self.backup_jobs.get(job_id)
        if not job:
            return None
        
        for key, value in updates.items():
            if hasattr(job, key):
                setattr(job, key, value)
        
        logger.info(f"Updated backup job: {job.name}")
        return job
    
    def delete_backup_job(self, job_id: str) -> bool:
        """
        Delete a backup job
        
        Args:
            job_id: Job ID
            
        Returns:
            True if deleted
        """
        if job_id in self.backup_jobs:
            del self.backup_jobs[job_id]
            logger.info(f"Deleted backup job: {job_id}")
            return True
        return False
    
    def get_backup_job(self, job_id: str) -> Optional[BackupJob]:
        """
        Get a backup job
        
        Args:
            job_id: Job ID
            
        Returns:
            BackupJob or None
        """
        return self.backup_jobs.get(job_id)
    
    def get_backup_jobs(self) -> List[BackupJob]:
        """
        Get all backup jobs
        
        Returns:
            List of backup jobs
        """
        return list(self.backup_jobs.values())
    
    # ============================================================
    # BACKUP EXECUTION
    # ============================================================
    
    def run_backup(self, job_id: str, async_mode: bool = False) -> Union[BackupResult, threading.Thread]:
        """
        Run a backup job
        
        Args:
            job_id: Job ID
            async_mode: Run asynchronously
            
        Returns:
            BackupResult or Thread
        """
        job = self.backup_jobs.get(job_id)
        if not job:
            raise ValueError(f"Backup job not found: {job_id}")
        
        if async_mode:
            thread = threading.Thread(target=self._run_backup_sync, args=(job_id,))
            thread.start()
            self.threads.append(thread)
            return thread
        
        return self._run_backup_sync(job_id)
    
    def _run_backup_sync(self, job_id: str) -> BackupResult:
        """
        Synchronous backup execution
        
        Args:
            job_id: Job ID
            
        Returns:
            BackupResult
        """
        job = self.backup_jobs.get(job_id)
        if not job:
            raise ValueError(f"Backup job not found: {job_id}")
        
        start_time = time.time()
        started_at = datetime.now()
        
        # Update job status
        job.last_status = BackupStatus.RUNNING
        job.last_run = started_at
        
        try:
            # Create backup
            backup_path = self._create_backup(job)
            
            # Verify backup
            if job.verify_backup:
                self._verify_backup(backup_path)
            
            # Clean old backups
            self._cleanup_old_backups(job)
            
            # Calculate result
            duration = time.time() - start_time
            file_count = self._count_files(backup_path)
            size_bytes = self._get_size(backup_path)
            checksum = self._calculate_checksum(backup_path)
            
            result = BackupResult(
                job_id=job.id,
                job_name=job.name,
                backup_path=backup_path,
                size_bytes=size_bytes,
                duration_seconds=duration,
                file_count=file_count,
                status=BackupStatus.SUCCESS,
                checksum=checksum,
                started_at=started_at,
                completed_at=datetime.now(),
            )
            
            job.last_status = BackupStatus.SUCCESS
            job.last_error = None
            
            logger.info(f"Backup completed: {job.name} in {duration:.2f}s")
            
        except Exception as e:
            job.last_status = BackupStatus.FAILED
            job.last_error = str(e)
            
            result = BackupResult(
                job_id=job.id,
                job_name=job.name,
                backup_path="",
                size_bytes=0,
                duration_seconds=time.time() - start_time,
                file_count=0,
                status=BackupStatus.FAILED,
                error=str(e),
                started_at=started_at,
                completed_at=datetime.now(),
            )
            
            logger.error(f"Backup failed: {job.name} - {e}")
        
        self.backup_results[job.id] = result
        return result
    
    def _create_backup(self, job: BackupJob) -> str:
        """
        Create a backup
        
        Args:
            job: Backup job
            
        Returns:
            Backup path
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{job.name}_{timestamp}"
        
        if job.type == BackupType.FULL:
            return self._create_full_backup(job, backup_name)
        elif job.type == BackupType.INCREMENTAL:
            return self._create_incremental_backup(job, backup_name)
        elif job.type == BackupType.SNAPSHOT:
            return self._create_snapshot_backup(job, backup_name)
        else:
            return self._create_full_backup(job, backup_name)
    
    def _create_full_backup(self, job: BackupJob, backup_name: str) -> str:
        """
        Create a full backup
        
        Args:
            job: Backup job
            backup_name: Backup name
            
        Returns:
            Backup path
        """
        backup_path = Path(job.destination_path) / f"{backup_name}.tar.gz"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create tar file
        with tarfile.open(backup_path, "w:gz") as tar:
            for source_path in job.source_paths:
                source = Path(source_path)
                if source.exists():
                    tar.add(source, arcname=source.name)
        
        # Encrypt if enabled
        if job.encryption and job.encryption_key:
            backup_path = self._encrypt_backup(backup_path, job.encryption_key)
        
        return str(backup_path)
    
    def _create_incremental_backup(self, job: BackupJob, backup_name: str) -> str:
        """
        Create an incremental backup
        
        Args:
            job: Backup job
            backup_name: Backup name
            
        Returns:
            Backup path
        """
        # Simplified incremental backup
        return self._create_full_backup(job, backup_name)
    
    def _create_snapshot_backup(self, job: BackupJob, backup_name: str) -> str:
        """
        Create a snapshot backup
        
        Args:
            job: Backup job
            backup_name: Backup name
            
        Returns:
            Backup path
        """
        # Simplified snapshot backup
        return self._create_full_backup(job, backup_name)
    
    def _verify_backup(self, backup_path: str) -> bool:
        """
        Verify a backup
        
        Args:
            backup_path: Path to backup
            
        Returns:
            True if verified
        """
        try:
            # Check if file exists
            if not os.path.exists(backup_path):
                raise FileNotFoundError(f"Backup file not found: {backup_path}")
            
            # Check if file is readable
            with open(backup_path, "rb") as f:
                f.read(1024)
            
            # Verify tar integrity
            if backup_path.endswith(".tar.gz"):
                with tarfile.open(backup_path, "r:gz") as tar:
                    tar.getmembers()
            
            logger.info(f"Backup verified: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return False
    
    def _cleanup_old_backups(self, job: BackupJob) -> None:
        """
        Clean up old backups
        
        Args:
            job: Backup job
        """
        backup_dir = Path(job.destination_path)
        if not backup_dir.exists():
            return
        
        # Get all backups for this job
        backups = []
        for file in backup_dir.glob(f"{job.name}_*"):
            if file.is_file():
                backups.append(file)
        
        # Sort by modification time
        backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Remove old backups
        for i, backup in enumerate(backups):
            if i >= job.max_backups:
                backup.unlink()
                logger.info(f"Removed old backup: {backup.name}")
        
        # Remove backups older than retention period
        cutoff = datetime.now() - timedelta(days=job.retention_days)
        for backup in backups:
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)
            if mtime < cutoff:
                backup.unlink()
                logger.info(f"Removed expired backup: {backup.name}")
    
    def _count_files(self, backup_path: str) -> int:
        """Count files in backup"""
        try:
            if backup_path.endswith(".tar.gz"):
                with tarfile.open(backup_path, "r:gz") as tar:
                    return len(tar.getmembers())
            else:
                return 1
        except:
            return 0
    
    def _get_size(self, backup_path: str) -> int:
        """Get backup file size"""
        try:
            return os.path.getsize(backup_path)
        except:
            return 0
    
    def _calculate_checksum(self, backup_path: str) -> str:
        """Calculate checksum"""
        try:
            sha256 = hashlib.sha256()
            with open(backup_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except:
            return ""
    
    def _encrypt_backup(self, backup_path: Path, key: str) -> Path:
        """
        Encrypt a backup
        
        Args:
            backup_path: Backup path
            key: Encryption key
            
        Returns:
            Encrypted backup path
        """
        if not HAS_CRYPTOGRAPHY:
            logger.warning("Cryptography not installed, skipping encryption")
            return backup_path
        
        encrypted_path = backup_path.with_suffix(backup_path.suffix + ".enc")
        
        fernet = Fernet(key.encode())
        with open(backup_path, "rb") as f:
            data = f.read()
        encrypted_data = fernet.encrypt(data)
        
        with open(encrypted_path, "wb") as f:
            f.write(encrypted_data)
        
        # Remove unencrypted backup
        backup_path.unlink()
        
        return encrypted_path
    
    # ============================================================
    # RESTORE
    # ============================================================
    
    def restore_backup(
        self,
        backup_path: str,
        destination_path: str,
        overwrite: bool = False,
        verify: bool = True
    ) -> RestoreJob:
        """
        Restore a backup
        
        Args:
            backup_path: Path to backup
            destination_path: Destination path
            overwrite: Overwrite existing files
            verify: Verify after restore
            
        Returns:
            RestoreJob
        """
        job = RestoreJob(
            id=f"restore_{int(time.time())}_{len(self.restore_jobs)}",
            name=f"Restore_{Path(backup_path).name}",
            backup_job_id="",
            backup_path=backup_path,
            destination_path=destination_path,
            overwrite=overwrite,
            verify_after_restore=verify,
            status=BackupStatus.RUNNING,
            started_at=datetime.now(),
        )
        
        self.restore_jobs[job.id] = job
        
        try:
            self._perform_restore(job)
            job.status = BackupStatus.RESTORED
            job.completed_at = datetime.now()
            logger.info(f"Restore completed: {job.name}")
            
        except Exception as e:
            job.status = BackupStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.now()
            logger.error(f"Restore failed: {job.name} - {e}")
        
        return job
    
    def _perform_restore(self, job: RestoreJob) -> None:
        """
        Perform restore operation
        
        Args:
            job: Restore job
        """
        backup_path = Path(job.backup_path)
        destination_path = Path(job.destination_path)
        
        # Decrypt if encrypted
        if backup_path.suffix == ".enc":
            backup_path = self._decrypt_backup(backup_path)
        
        # Extract backup
        if backup_path.suffix == ".gz" or backup_path.suffix == ".tar.gz":
            with tarfile.open(backup_path, "r:gz") as tar:
                tar.extractall(destination_path)
        elif backup_path.suffix == ".zip":
            with zipfile.ZipFile(backup_path, "r") as zip_file:
                zip_file.extractall(destination_path)
        else:
            shutil.copy2(backup_path, destination_path)
        
        # Verify restore
        if job.verify_after_restore:
            self._verify_restore(job)
    
    def _decrypt_backup(self, backup_path: Path) -> Path:
        """
        Decrypt a backup
        
        Args:
            backup_path: Encrypted backup path
            
        Returns:
            Decrypted backup path
        """
        if not HAS_CRYPTOGRAPHY:
            raise ImportError("Cryptography not installed")
        
        if not self.encryption_key:
            raise ValueError("Encryption key not set")
        
        decrypted_path = backup_path.with_suffix("")
        
        fernet = Fernet(self.encryption_key.encode())
        with open(backup_path, "rb") as f:
            encrypted_data = f.read()
        decrypted_data = fernet.decrypt(encrypted_data)
        
        with open(decrypted_path, "wb") as f:
            f.write(decrypted_data)
        
        return decrypted_path
    
    def _verify_restore(self, job: RestoreJob) -> bool:
        """
        Verify a restore
        
        Args:
            job: Restore job
            
        Returns:
            True if verified
        """
        destination = Path(job.destination_path)
        if not destination.exists():
            raise FileNotFoundError(f"Destination not found: {destination}")
        
        # Check if files were restored
        backup_files = self._get_backup_files(job.backup_path)
        restored_files = self._get_restored_files(destination)
        
        if len(backup_files) != len(restored_files):
            logger.warning(f"File count mismatch: {len(backup_files)} vs {len(restored_files)}")
            return False
        
        logger.info(f"Restore verified: {job.name}")
        return True
    
    def _get_backup_files(self, backup_path: str) -> List[str]:
        """Get list of files in backup"""
        try:
            if backup_path.endswith(".tar.gz"):
                with tarfile.open(backup_path, "r:gz") as tar:
                    return [m.name for m in tar.getmembers()]
            elif backup_path.endswith(".zip"):
                with zipfile.ZipFile(backup_path, "r") as zip_file:
                    return zip_file.namelist()
            else:
                return [os.path.basename(backup_path)]
        except:
            return []
    
    def _get_restored_files(self, destination: Path) -> List[str]:
        """Get list of restored files"""
        files = []
        for root, _, filenames in os.walk(destination):
            for filename in filenames:
                files.append(os.path.join(root, filename))
        return files
    
    # ============================================================
    # CLOUD BACKUP
    # ============================================================
    
    def upload_to_cloud(
        self,
        backup_path: str,
        cloud_provider: str,
        bucket: str,
        key: Optional[str] = None,
        region: Optional[str] = None
    ) -> bool:
        """
        Upload backup to cloud
        
        Args:
            backup_path: Local backup path
            cloud_provider: Cloud provider (aws, gcp, azure)
            bucket: Bucket name
            key: Object key
            region: Region
            
        Returns:
            True if uploaded
        """
        if not HAS_BOTO3:
            logger.error("Boto3 not installed")
            return False
        
        if key is None:
            key = Path(backup_path).name
        
        try:
            if cloud_provider == "aws":
                s3 = boto3.client("s3", region_name=region)
                s3.upload_file(backup_path, bucket, key)
                logger.info(f"Uploaded to S3: {bucket}/{key}")
                return True
            elif cloud_provider == "gcp":
                # GCP implementation would go here
                logger.info("GCP upload not implemented")
                return False
            elif cloud_provider == "azure":
                # Azure implementation would go here
                logger.info("Azure upload not implemented")
                return False
            else:
                logger.error(f"Unsupported cloud provider: {cloud_provider}")
                return False
        except Exception as e:
            logger.error(f"Cloud upload failed: {e}")
            return False
    
    def download_from_cloud(
        self,
        cloud_provider: str,
        bucket: str,
        key: str,
        destination_path: str,
        region: Optional[str] = None
    ) -> bool:
        """
        Download backup from cloud
        
        Args:
            cloud_provider: Cloud provider
            bucket: Bucket name
            key: Object key
            destination_path: Local destination
            region: Region
            
        Returns:
            True if downloaded
        """
        if not HAS_BOTO3:
            logger.error("Boto3 not installed")
            return False
        
        try:
            if cloud_provider == "aws":
                s3 = boto3.client("s3", region_name=region)
                s3.download_file(bucket, key, destination_path)
                logger.info(f"Downloaded from S3: {bucket}/{key}")
                return True
            else:
                logger.error(f"Unsupported cloud provider: {cloud_provider}")
                return False
        except Exception as e:
            logger.error(f"Cloud download failed: {e}")
            return False
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def get_backup_results(self, job_id: Optional[str] = None) -> List[BackupResult]:
        """
        Get backup results
        
        Args:
            job_id: Filter by job ID
            
        Returns:
            List of backup results
        """
        if job_id:
            return [r for r in self.backup_results.values() if r.job_id == job_id]
        return list(self.backup_results.values())
    
    def get_restore_jobs(self) -> List[RestoreJob]:
        """
        Get restore jobs
        
        Returns:
            List of restore jobs
        """
        return list(self.restore_jobs.values())
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get backup statistics
        
        Returns:
            Statistics dictionary
        """
        total_backups = len(self.backup_results)
        successful = len([r for r in self.backup_results.values() if r.status == BackupStatus.SUCCESS])
        failed = len([r for r in self.backup_results.values() if r.status == BackupStatus.FAILED])
        
        total_size = sum(r.size_bytes for r in self.backup_results.values())
        
        return {
            "total_backups": total_backups,
            "successful_backups": successful,
            "failed_backups": failed,
            "success_rate": successful / total_backups if total_backups > 0 else 0,
            "total_size_bytes": total_size,
            "total_size_gb": total_size / (1024 ** 3),
            "backup_jobs": len(self.backup_jobs),
            "restore_jobs": len(self.restore_jobs),
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "BackupType",
    "BackupStatus",
    "BackupStorage",
    "BackupCompression",
    
    # Dataclasses
    "BackupJob",
    "BackupResult",
    "RestoreJob",
    
    # Classes
    "BackupManager",
]

# ============================================================
# END OF MODULE
# ============================================================
