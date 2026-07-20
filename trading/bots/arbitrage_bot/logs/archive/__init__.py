# trading/bots/arbitrage_bot/logs/archive/__init__.py
# NEXUS AI TRADING SYSTEM
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 4.2.0 - Log Archive Package

"""
Log Archive Package - Log File Archiving and Management

This package provides comprehensive log archiving capabilities for the
NEXUS AI Trading System, including compression, rotation, and management
of historical log files.

Architecture:
    - ArchiveManager: Main archive management
    - CompressionHandler: Compression utilities
    - RotationHandler: Log rotation
    - RetentionManager: Retention policy management
    - ArchiveIndex: Indexing and searching

Features:
    - Log file compression (gzip)
    - Automatic log rotation
    - Retention policy enforcement
    - Archive indexing
    - Search capabilities
    - Archive restoration
    - Storage management
"""

import logging
import os
import gzip
import shutil
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum

# Logger setup
logger = logging.getLogger(__name__)

# Version information
__version__ = "4.2.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Package metadata
PACKAGE_METADATA = {
    "name": "archive",
    "version": __version__,
    "description": "Log Archive Management Package",
    "author": __author__,
    "copyright": __copyright__,
    "supported_formats": ["gz", "zip", "bz2"],
    "retention_policies": ["daily", "weekly", "monthly", "custom"],
}


class ArchiveFormat(Enum):
    """Archive format enumeration."""
    GZIP = "gz"
    ZIP = "zip"
    BZ2 = "bz2"


class RetentionPolicy(Enum):
    """Retention policy enumeration."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


@dataclass
class ArchiveInfo:
    """Archive information."""
    filename: str
    date: datetime
    size: int
    compressed_size: int
    format: ArchiveFormat
    entries: int
    checksum: str
    retention_days: int
    expires_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ArchiveConfig:
    """Archive configuration."""
    archive_dir: str
    retention_days: int = 90
    max_size_mb: int = 1024  # 1GB
    compress_level: int = 6  # 1-9
    format: ArchiveFormat = ArchiveFormat.GZIP
    auto_rotate: bool = True
    rotate_interval_days: int = 1
    retention_policy: RetentionPolicy = RetentionPolicy.DAILY
    max_archives: int = 100


class ArchiveManager:
    """
    Log Archive Manager.
    
    This class provides comprehensive log archiving capabilities:
    1. Log compression
    2. Archive rotation
    3. Retention management
    4. Archive indexing
    5. Archive restoration
    6. Storage management
    
    Features:
    - Multi-format support (gzip, zip, bz2)
    - Automatic rotation
    - Retention policy enforcement
    - Archive indexing and searching
    - Storage management
    - Integrity checking
    """
    
    def __init__(self, config: ArchiveConfig):
        """
        Initialize the Archive Manager.
        
        Args:
            config: Archive configuration
        """
        self.config = config
        self.archive_dir = Path(config.archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        self.archives: Dict[str, ArchiveInfo] = {}
        self.index_file = self.archive_dir / "index.json"
        
        # Load index if exists
        self._load_index()
        
        self.logger = logging.getLogger(f"{__name__}.ArchiveManager")
        self.logger.info(f"ArchiveManager initialized: {self.archive_dir}")
    
    def _load_index(self) -> None:
        """Load archive index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        value['date'] = datetime.fromisoformat(value['date'])
                        value['expires_at'] = datetime.fromisoformat(value['expires_at'])
                        self.archives[key] = ArchiveInfo(**value)
                self.logger.info(f"Loaded {len(self.archives)} archives from index")
            except Exception as e:
                self.logger.error(f"Failed to load index: {e}")
    
    def _save_index(self) -> None:
        """Save archive index to disk."""
        try:
            data = {}
            for key, info in self.archives.items():
                data[key] = {
                    'filename': info.filename,
                    'date': info.date.isoformat(),
                    'size': info.size,
                    'compressed_size': info.compressed_size,
                    'format': info.format.value,
                    'entries': info.entries,
                    'checksum': info.checksum,
                    'retention_days': info.retention_days,
                    'expires_at': info.expires_at.isoformat(),
                    'metadata': info.metadata,
                }
            with open(self.index_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save index: {e}")
    
    def archive_file(
        self,
        file_path: Union[str, Path],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[ArchiveInfo]:
        """
        Archive a log file.
        
        Args:
            file_path: Path to the file to archive
            metadata: Optional metadata
            
        Returns:
            ArchiveInfo or None
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            self.logger.error(f"File not found: {file_path}")
            return None
        
        try:
            # Generate archive filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            archive_name = f"{file_path.stem}_{timestamp}.{self.config.format.value}"
            archive_path = self.archive_dir / archive_name
            
            # Get original file size
            original_size = file_path.stat().st_size
            
            # Compress the file
            if self.config.format == ArchiveFormat.GZIP:
                compressed_size = self._compress_gzip(file_path, archive_path)
            elif self.config.format == ArchiveFormat.ZIP:
                compressed_size = self._compress_zip(file_path, archive_path)
            elif self.config.format == ArchiveFormat.BZ2:
                compressed_size = self._compress_bz2(file_path, archive_path)
            else:
                self.logger.error(f"Unsupported format: {self.config.format}")
                return None
            
            # Calculate checksum
            checksum = self._calculate_checksum(archive_path)
            
            # Count entries
            entries = self._count_entries(archive_path)
            
            # Create archive info
            archive_info = ArchiveInfo(
                filename=archive_name,
                date=datetime.utcnow(),
                size=original_size,
                compressed_size=compressed_size,
                format=self.config.format,
                entries=entries,
                checksum=checksum,
                retention_days=self.config.retention_days,
                expires_at=datetime.utcnow() + timedelta(days=self.config.retention_days),
                metadata=metadata or {},
            )
            
            # Store in index
            self.archives[archive_name] = archive_info
            self._save_index()
            
            # Delete original file
            file_path.unlink()
            
            self.logger.info(f"Archived: {archive_name} ({compressed_size} bytes)")
            
            # Cleanup old archives
            self._cleanup_archives()
            
            return archive_info
            
        except Exception as e:
            self.logger.error(f"Failed to archive file: {e}")
            return None
    
    def _compress_gzip(self, source: Path, target: Path) -> int:
        """Compress file using gzip."""
        with open(source, 'rb') as f_in:
            with gzip.open(target, 'wb', compresslevel=self.config.compress_level) as f_out:
                shutil.copyfileobj(f_in, f_out)
        return target.stat().st_size
    
    def _compress_zip(self, source: Path, target: Path) -> int:
        """Compress file using zip."""
        import zipfile
        with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(source, source.name)
        return target.stat().st_size
    
    def _compress_bz2(self, source: Path, target: Path) -> int:
        """Compress file using bzip2."""
        import bz2
        with open(source, 'rb') as f_in:
            with bz2.open(target, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return target.stat().st_size
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        import hashlib
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for block in iter(lambda: f.read(4096), b''):
                sha256.update(block)
        return sha256.hexdigest()
    
    def _count_entries(self, file_path: Path) -> int:
        """Count entries in an archive."""
        # For gzip and bz2, count lines
        if self.config.format in [ArchiveFormat.GZIP, ArchiveFormat.BZ2]:
            count = 0
            with open(file_path, 'rb') as f:
                for _ in f:
                    count += 1
            return count
        # For zip, count files
        elif self.config.format == ArchiveFormat.ZIP:
            import zipfile
            with zipfile.ZipFile(file_path, 'r') as zf:
                return len(zf.namelist())
        return 0
    
    def _cleanup_archives(self) -> None:
        """Clean up expired archives."""
        now = datetime.utcnow()
        to_remove = []
        
        for key, info in self.archives.items():
            if info.expires_at <= now:
                to_remove.append(key)
        
        for key in to_remove:
            self._remove_archive(key)
    
    def _remove_archive(self, archive_name: str) -> bool:
        """
        Remove an archive.
        
        Args:
            archive_name: Archive filename
            
        Returns:
            True if removed successfully
        """
        archive_path = self.archive_dir / archive_name
        
        try:
            if archive_path.exists():
                archive_path.unlink()
            
            del self.archives[archive_name]
            self._save_index()
            
            self.logger.info(f"Removed expired archive: {archive_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to remove archive: {e}")
            return False
    
    def restore_archive(
        self,
        archive_name: str,
        target_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        Restore an archive.
        
        Args:
            archive_name: Archive filename
            target_dir: Target directory (default: current working dir)
            
        Returns:
            Path to restored file or None
        """
        if archive_name not in self.archives:
            self.logger.error(f"Archive not found: {archive_name}")
            return None
        
        archive_path = self.archive_dir / archive_name
        
        if not archive_path.exists():
            self.logger.error(f"Archive file not found: {archive_path}")
            return None
        
        target_dir = target_dir or Path.cwd()
        target_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Determine restored filename
            restored_name = archive_name.rsplit('.', 1)[0]
            restored_path = target_dir / restored_name
            
            # Extract based on format
            if self.config.format == ArchiveFormat.GZIP:
                with gzip.open(archive_path, 'rb') as f_in:
                    with open(restored_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            elif self.config.format == ArchiveFormat.ZIP:
                import zipfile
                with zipfile.ZipFile(archive_path, 'r') as zf:
                    zf.extractall(target_dir)
                restored_path = target_dir / zf.namelist()[0]
            elif self.config.format == ArchiveFormat.BZ2:
                import bz2
                with bz2.open(archive_path, 'rb') as f_in:
                    with open(restored_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                self.logger.error(f"Unsupported format: {self.config.format}")
                return None
            
            self.logger.info(f"Restored: {archive_name} -> {restored_path}")
            return restored_path
            
        except Exception as e:
            self.logger.error(f"Failed to restore archive: {e}")
            return None
    
    def list_archives(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[ArchiveInfo]:
        """
        List archives.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            List of ArchiveInfo
        """
        archives = list(self.archives.values())
        
        if start_date:
            archives = [a for a in archives if a.date >= start_date]
        if end_date:
            archives = [a for a in archives if a.date <= end_date]
        
        return sorted(archives, key=lambda x: x.date, reverse=True)
    
    def get_archive_info(self, archive_name: str) -> Optional[ArchiveInfo]:
        """
        Get archive information.
        
        Args:
            archive_name: Archive filename
            
        Returns:
            ArchiveInfo or None
        """
        return self.archives.get(archive_name)
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Storage statistics
        """
        total_size = sum(a.size for a in self.archives.values())
        total_compressed = sum(a.compressed_size for a in self.archives.values())
        
        return {
            "total_archives": len(self.archives),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "total_compressed_bytes": total_compressed,
            "total_compressed_mb": total_compressed / (1024 * 1024),
            "compression_ratio": total_compressed / total_size if total_size > 0 else 0,
            "archive_dir": str(self.archive_dir),
            "retention_days": self.config.retention_days,
            "format": self.config.format.value,
        }
    
    def verify_archive(self, archive_name: str) -> bool:
        """
        Verify archive integrity.
        
        Args:
            archive_name: Archive filename
            
        Returns:
            True if valid
        """
        if archive_name not in self.archives:
            return False
        
        archive_path = self.archive_dir / archive_name
        
        if not archive_path.exists():
            return False
        
        # Verify checksum
        actual_checksum = self._calculate_checksum(archive_path)
        expected_checksum = self.archives[archive_name].checksum
        
        return actual_checksum == expected_checksum
    
    def rotate_logs(self, log_dir: Path, pattern: str = "*.log") -> int:
        """
        Rotate logs in a directory.
        
        Args:
            log_dir: Directory containing logs
            pattern: File pattern
            
        Returns:
            Number of files archived
        """
        log_dir = Path(log_dir)
        if not log_dir.exists():
            return 0
        
        files = list(log_dir.glob(pattern))
        archived = 0
        
        for file_path in files:
            if self.archive_file(file_path):
                archived += 1
        
        return archived


# Utility functions
def create_archive_manager(config: Dict[str, Any]) -> ArchiveManager:
    """
    Create an archive manager instance.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        ArchiveManager instance
    """
    archive_config = ArchiveConfig(
        archive_dir=config.get('archive_dir', './archives'),
        retention_days=config.get('retention_days', 90),
        max_size_mb=config.get('max_size_mb', 1024),
        compress_level=config.get('compress_level', 6),
        format=ArchiveFormat(config.get('format', 'gz')),
        auto_rotate=config.get('auto_rotate', True),
        rotate_interval_days=config.get('rotate_interval_days', 1),
        retention_policy=RetentionPolicy(config.get('retention_policy', 'daily')),
        max_archives=config.get('max_archives', 100),
    )
    return ArchiveManager(archive_config)


def get_default_config() -> Dict[str, Any]:
    """
    Get default archive configuration.
    
    Returns:
        Default configuration dictionary
    """
    return {
        'archive_dir': './logs/archive',
        'retention_days': 90,
        'max_size_mb': 1024,
        'compress_level': 6,
        'format': 'gz',
        'auto_rotate': True,
        'rotate_interval_days': 1,
        'retention_policy': 'daily',
        'max_archives': 100,
    }


# Module exports
__all__ = [
    'ArchiveManager',
    'ArchiveConfig',
    'ArchiveInfo',
    'ArchiveFormat',
    'RetentionPolicy',
    'create_archive_manager',
    'get_default_config',
]


# Package initialization
logger.info(f"Initializing Archive Package v{__version__}")


# Lazy imports for circular dependency resolution
def __getattr__(name: str) -> Any:
    """
    Lazy import for submodules.
    
    This allows for clean imports while avoiding circular dependencies.
    """
    raise AttributeError(f"module {__name__} has no attribute {name}")
