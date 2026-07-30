# trading/bots/hedge_bot/hedge_bot_data_archive.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Data Archive Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Data Archive Module

This module provides comprehensive data archiving capabilities for the
NEXUS Hedge Bot system. It manages data lifecycle, archiving strategies,
and data retrieval from archives.

The module covers:
- Data Archiving
- Data Lifecycle Management
- Archive Strategies
- Archive Compression
- Archive Encryption
- Archive Verification
- Data Retrieval from Archives
- Archive Cleanup
- Archive Reporting
"""

import os
import sys
import json
import logging
import shutil
import gzip
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
import pandas as pd
import pickle
import tempfile

logger = logging.getLogger(__name__)


# ============================================================
# DATA ARCHIVE ENUMS
# ============================================================

class ArchiveMethod(Enum):
    """Archive methods"""
    TIMESTAMP = "timestamp"
    SIZE_BASED = "size_based"
    MANUAL = "manual"
    HYBRID = "hybrid"


class ArchiveType(Enum):
    """Archive types"""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"


class ArchiveStatus(Enum):
    """Archive status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


@dataclass
class ArchiveConfig:
    """Archive configuration"""
    id: str
    name: str
    source_path: str
    archive_path: str
    method: ArchiveMethod
    type: ArchiveType
    max_age_days: int = 30
    max_size_gb: float = 10.0
    compression: bool = True
    encryption: bool = False
    verify_after_archive: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "source_path": self.source_path,
            "archive_path": self.archive_path,
            "method": self.method.value,
            "type": self.type.value,
            "max_age_days": self.max_age_days,
            "max_size_gb": self.max_size_gb,
            "compression": self.compression,
            "encryption": self.encryption,
            "verify_after_archive": self.verify_after_archive,
        }


@dataclass
class ArchiveResult:
    """Archive result"""
    archive_id: str
    source_path: str
    archive_path: str
    original_size: int
    archived_size: int
    compression_ratio: float
    file_count: int
    status: ArchiveStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    checksum: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "archive_id": self.archive_id,
            "source_path": self.source_path,
            "archive_path": self.archive_path,
            "original_size": self.original_size,
            "archived_size": self.archived_size,
            "compression_ratio": self.compression_ratio,
            "file_count": self.file_count,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "checksum": self.checksum,
            "error": self.error,
        }


# ============================================================
# DATA ARCHIVE ENGINE
# ============================================================

class DataArchiveEngine:
    """
    Comprehensive data archive engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data archive engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.archive_base_path = Path(self.config.get("archive_base_path", "archives"))
        self.temp_path = Path(self.config.get("temp_path", "temp"))
        
        # Create directories
        self.archive_base_path.mkdir(parents=True, exist_ok=True)
        self.temp_path.mkdir(parents=True, exist_ok=True)
        
        # State
        self.configs: Dict[str, ArchiveConfig] = {}
        self.results: Dict[str, ArchiveResult] = {}
        
        # Register default archives
        self._register_default_archives()
        
        logger.info("Data archive engine initialized")
    
    # ============================================================
    # DEFAULT ARCHIVES
    # ============================================================
    
    def _register_default_archives(self) -> None:
        """Register default archive configurations"""
        default_configs = [
            ArchiveConfig(
                id="archive_trades",
                name="Trades Archive",
                source_path="data/trades",
                archive_path="archives/trades",
                method=ArchiveMethod.TIMESTAMP,
                type=ArchiveType.FULL,
                max_age_days=90,
                max_size_gb=5.0,
            ),
            ArchiveConfig(
                id="archive_positions",
                name="Positions Archive",
                source_path="data/positions",
                archive_path="archives/positions",
                method=ArchiveMethod.TIMESTAMP,
                type=ArchiveType.FULL,
                max_age_days=60,
                max_size_gb=2.0,
            ),
            ArchiveConfig(
                id="archive_market_data",
                name="Market Data Archive",
                source_path="data/market_data",
                archive_path="archives/market_data",
                method=ArchiveMethod.SIZE_BASED,
                type=ArchiveType.INCREMENTAL,
                max_age_days=30,
                max_size_gb=10.0,
            ),
        ]
        
        for config in default_configs:
            self.configs[config.id] = config
        
        logger.info(f"Registered {len(default_configs)} default archives")
    
    # ============================================================
    # ARCHIVE MANAGEMENT
    # ============================================================
    
    def create_archive_config(
        self,
        name: str,
        source_path: str,
        archive_path: str,
        method: ArchiveMethod = ArchiveMethod.TIMESTAMP,
        type: ArchiveType = ArchiveType.FULL,
        max_age_days: int = 30,
        max_size_gb: float = 10.0,
        compression: bool = True,
        encryption: bool = False,
        verify: bool = True
    ) -> ArchiveConfig:
        """
        Create an archive configuration
        
        Args:
            name: Archive name
            source_path: Source path
            archive_path: Archive path
            method: Archive method
            type: Archive type
            max_age_days: Maximum age in days
            max_size_gb: Maximum size in GB
            compression: Enable compression
            encryption: Enable encryption
            verify: Verify after archive
            
        Returns:
            ArchiveConfig
        """
        config = ArchiveConfig(
            id=f"archive_{int(time.time())}_{len(self.configs)}",
            name=name,
            source_path=source_path,
            archive_path=archive_path,
            method=method,
            type=type,
            max_age_days=max_age_days,
            max_size_gb=max_size_gb,
            compression=compression,
            encryption=encryption,
            verify_after_archive=verify,
        )
        
        self.configs[config.id] = config
        logger.info(f"Created archive config: {name}")
        return config
    
    def update_archive_config(
        self,
        config_id: str,
        updates: Dict[str, Any]
    ) -> Optional[ArchiveConfig]:
        """
        Update archive configuration
        
        Args:
            config_id: Configuration ID
            updates: Updates to apply
            
        Returns:
            Updated config or None
        """
        config = self.configs.get(config_id)
        if not config:
            return None
        
        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        logger.info(f"Updated archive config: {config.name}")
        return config
    
    def delete_archive_config(self, config_id: str) -> bool:
        """
        Delete archive configuration
        
        Args:
            config_id: Configuration ID
            
        Returns:
            True if deleted
        """
        if config_id in self.configs:
            del self.configs[config_id]
            logger.info(f"Deleted archive config: {config_id}")
            return True
        return False
    
    def get_archive_config(self, config_id: str) -> Optional[ArchiveConfig]:
        """
        Get archive configuration
        
        Args:
            config_id: Configuration ID
            
        Returns:
            ArchiveConfig or None
        """
        return self.configs.get(config_id)
    
    def get_archive_configs(self) -> List[ArchiveConfig]:
        """
        Get all archive configurations
        
        Returns:
            List of archive configs
        """
        return list(self.configs.values())
    
    # ============================================================
    # ARCHIVE EXECUTION
    # ============================================================
    
    def run_archive(self, config_id: str) -> ArchiveResult:
        """
        Run archive process
        
        Args:
            config_id: Configuration ID
            
        Returns:
            ArchiveResult
        """
        config = self.configs.get(config_id)
        if not config:
            raise ValueError(f"Archive config not found: {config_id}")
        
        source_path = Path(config.source_path)
        archive_path = Path(config.archive_path)
        
        if not source_path.exists():
            raise ValueError(f"Source path not found: {source_path}")
        
        # Create archive path
        archive_path.mkdir(parents=True, exist_ok=True)
        
        # Start archiving
        result = ArchiveResult(
            archive_id=config.id,
            source_path=str(source_path),
            archive_path=str(archive_path),
            original_size=0,
            archived_size=0,
            compression_ratio=0.0,
            file_count=0,
            status=ArchiveStatus.RUNNING,
            started_at=datetime.now(),
        )
        
        try:
            if config.method == ArchiveMethod.TIMESTAMP:
                result = self._archive_by_timestamp(config, result)
            elif config.method == ArchiveMethod.SIZE_BASED:
                result = self._archive_by_size(config, result)
            elif config.method == ArchiveMethod.MANUAL:
                result = self._archive_manual(config, result)
            elif config.method == ArchiveMethod.HYBRID:
                result = self._archive_hybrid(config, result)
            else:
                result = self._archive_timestamp(config, result)
            
            # Verify archive
            if config.verify_after_archive:
                self._verify_archive(config, result)
            
            result.status = ArchiveStatus.COMPLETED
            result.completed_at = datetime.now()
            
        except Exception as e:
            result.status = ArchiveStatus.FAILED
            result.error = str(e)
            logger.error(f"Archive failed: {e}")
        
        self.results[result.archive_id] = result
        return result
    
    def _archive_by_timestamp(
        self,
        config: ArchiveConfig,
        result: ArchiveResult
    ) -> ArchiveResult:
        """
        Archive by timestamp
        
        Args:
            config: Archive config
            result: Archive result
            
        Returns:
            Updated result
        """
        source_path = Path(config.source_path)
        archive_path = Path(config.archive_path)
        
        # Create timestamp-based archive
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{config.name}_{timestamp}.tar.gz"
        archive_file = archive_path / archive_name
        
        # Create tar archive
        import tarfile
        with tarfile.open(archive_file, "w:gz") as tar:
            for file_path in source_path.glob("*"):
                if file_path.is_file():
                    tar.add(file_path, arcname=file_path.name)
                    result.file_count += 1
        
        # Update sizes
        result.original_size = sum(f.stat().st_size for f in source_path.glob("*") if f.is_file())
        result.archived_size = archive_file.stat().st_size
        result.compression_ratio = result.archived_size / result.original_size if result.original_size > 0 else 0
        
        return result
    
    def _archive_by_size(
        self,
        config: ArchiveConfig,
        result: ArchiveResult
    ) -> ArchiveResult:
        """
        Archive by size
        
        Args:
            config: Archive config
            result: Archive result
            
        Returns:
            Updated result
        """
        source_path = Path(config.source_path)
        archive_path = Path(config.archive_path)
        
        # Check if source exceeds size limit
        total_size = sum(f.stat().st_size for f in source_path.glob("*") if f.is_file())
        max_size_bytes = config.max_size_gb * 1024 * 1024 * 1024
        
        if total_size <= max_size_bytes:
            return self._archive_by_timestamp(config, result)
        
        # Split into multiple archives
        files = list(source_path.glob("*"))
        files.sort(key=lambda f: f.stat().st_mtime)
        
        current_size = 0
        archive_index = 1
        current_files = []
        
        for file_path in files:
            file_size = file_path.stat().st_size
            if current_size + file_size > max_size_bytes:
                # Create archive for current batch
                self._create_archive_batch(
                    config, archive_path, current_files, archive_index, result
                )
                archive_index += 1
                current_files = []
                current_size = 0
            
            current_files.append(file_path)
            current_size += file_size
        
        # Create final archive
        if current_files:
            self._create_archive_batch(
                config, archive_path, current_files, archive_index, result
            )
        
        return result
    
    def _create_archive_batch(
        self,
        config: ArchiveConfig,
        archive_path: Path,
        files: List[Path],
        index: int,
        result: ArchiveResult
    ) -> None:
        """
        Create a batch archive
        
        Args:
            config: Archive config
            archive_path: Archive path
            files: List of files
            index: Archive index
            result: Archive result
        """
        import tarfile
        
        archive_name = f"{config.name}_part_{index:03d}_{datetime.now().strftime('%Y%m%d')}.tar.gz"
        archive_file = archive_path / archive_name
        
        with tarfile.open(archive_file, "w:gz") as tar:
            for file_path in files:
                tar.add(file_path, arcname=file_path.name)
                result.file_count += 1
        
        # Update sizes
        result.original_size += sum(f.stat().st_size for f in files)
        result.archived_size += archive_file.stat().st_size
        result.compression_ratio = result.archived_size / result.original_size if result.original_size > 0 else 0
    
    def _archive_manual(
        self,
        config: ArchiveConfig,
        result: ArchiveResult
    ) -> ArchiveResult:
        """
        Manual archiving
        
        Args:
            config: Archive config
            result: Archive result
            
        Returns:
            Updated result
        """
        # For manual archiving, we just copy the files
        source_path = Path(config.source_path)
        archive_path = Path(config.archive_path)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_dir = archive_path / f"{config.name}_{timestamp}"
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        for file_path in source_path.glob("*"):
            if file_path.is_file():
                shutil.copy2(file_path, archive_dir / file_path.name)
                result.file_count += 1
        
        # Update sizes
        result.original_size = sum(f.stat().st_size for f in source_path.glob("*") if f.is_file())
        result.archived_size = sum(f.stat().st_size for f in archive_dir.glob("*") if f.is_file())
        result.compression_ratio = 1.0
        
        return result
    
    def _archive_hybrid(
        self,
        config: ArchiveConfig,
        result: ArchiveResult
    ) -> ArchiveResult:
        """
        Hybrid archiving
        
        Args:
            config: Archive config
            result: Archive result
            
        Returns:
            Updated result
        """
        # Check both age and size
        source_path = Path(config.source_path)
        
        # Get old files
        cutoff_date = datetime.now() - timedelta(days=config.max_age_days)
        old_files = []
        for file_path in source_path.glob("*"):
            if file_path.is_file():
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < cutoff_date:
                    old_files.append(file_path)
        
        if old_files:
            # Archive old files
            archive_path = Path(config.archive_path)
            archive_name = f"{config.name}_old_{datetime.now().strftime('%Y%m%d')}.tar.gz"
            archive_file = archive_path / archive_name
            
            import tarfile
            with tarfile.open(archive_file, "w:gz") as tar:
                for file_path in old_files:
                    tar.add(file_path, arcname=file_path.name)
                    result.file_count += 1
            
            # Update sizes
            result.original_size = sum(f.stat().st_size for f in old_files)
            result.archived_size = archive_file.stat().st_size
            result.compression_ratio = result.archived_size / result.original_size if result.original_size > 0 else 0
            
            # Remove old files
            for file_path in old_files:
                file_path.unlink()
        
        return result
    
    def _verify_archive(
        self,
        config: ArchiveConfig,
        result: ArchiveResult
    ) -> bool:
        """
        Verify archive
        
        Args:
            config: Archive config
            result: Archive result
            
        Returns:
            True if verified
        """
        try:
            archive_path = Path(result.archive_path)
            if not archive_path.exists():
                return False
            
            # Calculate checksum
            sha256 = hashlib.sha256()
            with open(archive_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            
            result.checksum = sha256.hexdigest()
            result.status = ArchiveStatus.VERIFIED
            
            logger.info(f"Archive verified: {result.archive_id}")
            return True
            
        except Exception as e:
            logger.error(f"Archive verification failed: {e}")
            return False
    
    # ============================================================
    # DATA RETRIEVAL
    # ============================================================
    
    def retrieve_archive(
        self,
        archive_id: str,
        destination_path: str
    ) -> bool:
        """
        Retrieve data from archive
        
        Args:
            archive_id: Archive ID
            destination_path: Destination path
            
        Returns:
            True if retrieved
        """
        result = self.results.get(archive_id)
        if not result:
            return False
        
        archive_path = Path(result.archive_path)
        if not archive_path.exists():
            return False
        
        dest_path = Path(destination_path)
        dest_path.mkdir(parents=True, exist_ok=True)
        
        try:
            if archive_path.suffix == ".tar.gz":
                import tarfile
                with tarfile.open(archive_path, "r:gz") as tar:
                    tar.extractall(dest_path)
            else:
                # Copy files
                for file_path in archive_path.glob("*"):
                    if file_path.is_file():
                        shutil.copy2(file_path, dest_path / file_path.name)
            
            logger.info(f"Archive retrieved: {archive_id}")
            return True
            
        except Exception as e:
            logger.error(f"Archive retrieval failed: {e}")
            return False
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get archive statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_archives": len(self.configs),
            "completed_archives": len([r for r in self.results.values() if r.status == ArchiveStatus.COMPLETED]),
            "failed_archives": len([r for r in self.results.values() if r.status == ArchiveStatus.FAILED]),
            "verified_archives": len([r for r in self.results.values() if r.status == ArchiveStatus.VERIFIED]),
            "total_original_size": sum(r.original_size for r in self.results.values()),
            "total_archived_size": sum(r.archived_size for r in self.results.values()),
            "overall_compression_ratio": sum(r.archived_size for r in self.results.values()) / sum(r.original_size for r in self.results.values()) if sum(r.original_size for r in self.results.values()) > 0 else 1,
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "ArchiveMethod",
    "ArchiveType",
    "ArchiveStatus",
    
    # Dataclasses
    "ArchiveConfig",
    "ArchiveResult",
    
    # Classes
    "DataArchiveEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
