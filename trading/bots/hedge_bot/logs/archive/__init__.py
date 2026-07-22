# trading/bots/hedge_bot/logs/archive/__init__.py

"""
NEXUS HEDGE BOT - LOGS ARCHIVE MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced log archival system with compression, encryption, rotation,
indexing, search, and retention policies.

Version: 3.0.0
"""

import asyncio
import bz2
import concurrent.futures
import gzip
import hashlib
import json
import lzma
import os
import pickle
import re
import shutil
import sqlite3
import stat
import sys
import threading
import time
import traceback
import zlib
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import (
    Any, Callable, Dict, Iterator, List, Optional, Set, Tuple, Union, 
    TypeVar, Generic, AsyncIterator, Coroutine, Protocol, runtime_checkable
)
from uuid import UUID, uuid4

import aiofiles
import psutil
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pydantic import BaseModel, Field, validator, root_validator, ConfigDict
import redis.asyncio as redis_async
from redis.asyncio import Redis
import structlog
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
import yaml

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class CompressionAlgorithm(str, Enum):
    """Supported compression algorithms."""
    NONE = "none"
    GZIP = "gzip"
    BZ2 = "bz2"
    LZMA = "lzma"
    ZSTD = "zstd"
    ZLIB = "zlib"
    DEFLATE = "deflate"


class EncryptionAlgorithm(str, Enum):
    """Supported encryption algorithms."""
    NONE = "none"
    FERNET = "fernet"
    AES256 = "aes256"
    RSA = "rsa"


class ArchiveFormat(str, Enum):
    """Archive file formats."""
    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    PICKLE = "pickle"
    PARQUET = "parquet"
    PROTOBUF = "protobuf"
    TEXT = "text"
    BINARY = "binary"
    LOG = "log"


class RetentionPolicy(str, Enum):
    """Retention policies for archive management."""
    TIME_BASED = "time_based"
    SIZE_BASED = "size_based"
    HYBRID = "hybrid"
    INTELLIGENT = "intelligent"
    NONE = "none"


class ArchiveEventType(str, Enum):
    """Types of archive events."""
    CREATED = "created"
    ROTATED = "rotated"
    DELETED = "deleted"
    COMPRESSED = "compressed"
    DECOMPRESSED = "decompressed"
    ENCRYPTED = "encrypted"
    DECRYPTED = "decrypted"
    INDEXED = "indexed"
    SEARCHED = "searched"
    EXPIRED = "expired"
    CORRUPTED = "corrupted"
    REPAIRED = "repaired"
    MIGRATED = "migrated"
    BACKUP_CREATED = "backup_created"
    BACKUP_RESTORED = "backup_restored"
    VERIFICATION_FAILED = "verification_failed"
    VERIFICATION_PASSED = "verification_passed"


# === DATA MODELS ===

@dataclass
class ArchiveMetadata:
    """Metadata for an archived log file."""
    archive_id: str = field(default_factory=lambda: str(uuid4()))
    original_path: str = ""
    archive_path: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    modified_at: datetime = field(default_factory=datetime.utcnow)
    size_bytes: int = 0
    compressed_size_bytes: int = 0
    compression_algorithm: CompressionAlgorithm = CompressionAlgorithm.NONE
    encryption_algorithm: EncryptionAlgorithm = EncryptionAlgorithm.NONE
    archive_format: ArchiveFormat = ArchiveFormat.LOG
    checksum: str = ""
    checksum_algorithm: str = "sha256"
    retention_days: int = 90
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    corrupted: bool = False
    verified: bool = False
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "compression_algorithm": self.compression_algorithm.value,
            "encryption_algorithm": self.encryption_algorithm.value,
            "archive_format": self.archive_format.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArchiveMetadata":
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["modified_at"] = datetime.fromisoformat(data["modified_at"])
        data["compression_algorithm"] = CompressionAlgorithm(data["compression_algorithm"])
        data["encryption_algorithm"] = EncryptionAlgorithm(data["encryption_algorithm"])
        data["archive_format"] = ArchiveFormat(data["archive_format"])
        return cls(**data)


@dataclass
class ArchiveIndexEntry:
    """Entry in the archive search index."""
    entry_id: str = field(default_factory=lambda: str(uuid4()))
    archive_id: str = ""
    line_number: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    level: str = "INFO"
    module: str = ""
    function: str = ""
    message: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    raw_line: str = ""
    checksum: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArchiveIndexEntry":
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class ArchiveConfig(BaseModel):
    """Configuration for the archive system."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    root_dir: str = "logs/archive"
    compression: CompressionAlgorithm = CompressionAlgorithm.GZIP
    encryption: EncryptionAlgorithm = EncryptionAlgorithm.NONE
    archive_format: ArchiveFormat = ArchiveFormat.JSONL
    retention_policy: RetentionPolicy = RetentionPolicy.HYBRID
    retention_days: int = 90
    max_size_gb: float = 10.0
    max_files: int = 1000
    enable_indexing: bool = True
    enable_encryption: bool = False
    enable_compression: bool = True
    enable_deduplication: bool = True
    enable_corruption_check: bool = True
    enable_backup: bool = True
    enable_remote_sync: bool = False
    encryption_key_path: Optional[str] = None
    redis_url: Optional[str] = None
    parallel_workers: int = 4
    chunk_size_mb: int = 10
    use_temp_files: bool = True
    log_rotation_interval_hours: int = 24
    max_archive_versions: int = 5
    
    @validator("retention_days")
    def validate_retention_days(cls, v: int) -> int:
        if v < 1:
            raise ValueError("retention_days must be at least 1")
        return v
    
    @validator("max_size_gb")
    def validate_max_size(cls, v: float) -> float:
        if v < 0.1:
            raise ValueError("max_size_gb must be at least 0.1")
        return v
    
    @validator("parallel_workers")
    def validate_workers(cls, v: int) -> int:
        if v < 1:
            raise ValueError("parallel_workers must be at least 1")
        return v
    
    @classmethod
    def from_file(cls, path: str) -> "ArchiveConfig":
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)


# === EXCEPTIONS ===

class ArchiveError(Exception):
    """Base exception for archive errors."""
    pass


class ArchiveCorruptionError(ArchiveError):
    """Raised when archive corruption is detected."""
    pass


class ArchiveEncryptionError(ArchiveError):
    """Raised when encryption/decryption fails."""
    pass


class ArchiveNotFoundError(ArchiveError):
    """Raised when an archive is not found."""
    pass


class ArchiveIndexError(ArchiveError):
    """Raised when index operations fail."""
    pass


# === ARCHIVE MANAGER ===

class ArchiveManager:
    """
    Advanced log archive manager with compression, encryption, indexing,
    and retention management.
    """

    def __init__(
        self,
        config: Union[ArchiveConfig, Dict[str, Any], str],
        redis_client: Optional[Redis] = None,
    ):
        """
        Initialize the ArchiveManager.

        Args:
            config: Configuration object, dict, or path to config file
            redis_client: Optional Redis client for distributed operations
        """
        if isinstance(config, str):
            self.config = ArchiveConfig.from_file(config)
        elif isinstance(config, dict):
            self.config = ArchiveConfig(**config)
        else:
            self.config = config
        
        self.root_dir = Path(self.config.root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        
        self.redis_client = redis_client
        self._lock = threading.RLock()
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.parallel_workers
        )
        
        self._encryption_key: Optional[Fernet] = None
        if self.config.enable_encryption and self.config.encryption_key_path:
            self._load_encryption_key()
        
        self._file_watcher: Optional[Observer] = None
        self._index_db: Optional[sqlite3.Connection] = None
        self._closed = False
        
        self._initialize_index_db()
        self._start_watcher()
        
        # Metrics
        self._metrics = {
            "archives_created": 0,
            "archives_deleted": 0,
            "archives_compressed": 0,
            "archives_encrypted": 0,
            "archives_restored": 0,
            "corruption_detected": 0,
            "corruption_repaired": 0,
            "total_bytes_saved": 0,
            "errors": 0,
        }
        
        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        
        logger.info(
            "archive_manager_initialized",
            root_dir=str(self.root_dir),
            compression=self.config.compression.value,
            encryption=self.config.encryption.value,
            retention_days=self.config.retention_days,
            max_size_gb=self.config.max_size_gb,
        )

    def _load_encryption_key(self) -> None:
        """Load the encryption key from the specified path."""
        try:
            key_path = Path(self.config.encryption_key_path)
            if not key_path.exists():
                raise ArchiveEncryptionError(f"Encryption key not found: {key_path}")
            
            with open(key_path, "rb") as f:
                key = f.read().strip()
            
            # If key is a password, derive a Fernet key using PBKDF2
            if len(key) < 32:
                salt = b"NEXUS_SALT_2026"
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(key))
            elif len(key) != 44:
                # Try base64 decode if it's not a valid Fernet key length
                try:
                    key = base64.urlsafe_b64encode(base64.urlsafe_b64decode(key))
                except Exception:
                    # Use as-is, but warn
                    logger.warning("invalid_fernet_key_format", key_length=len(key))
            
            self._encryption_key = Fernet(key)
            logger.info("encryption_key_loaded")
        except Exception as e:
            logger.error("failed_to_load_encryption_key", error=str(e))
            raise ArchiveEncryptionError(f"Failed to load encryption key: {e}")

    def _initialize_index_db(self) -> None:
        """Initialize the SQLite index database."""
        index_path = self.root_dir / "index.db"
        self._index_db = sqlite3.connect(
            str(index_path),
            check_same_thread=False,
            isolation_level=None,
        )
        self._index_db.execute("PRAGMA journal_mode=WAL")
        self._index_db.execute("PRAGMA synchronous=NORMAL")
        self._index_db.execute("PRAGMA cache_size=-10000")  # 10MB cache
        
        self._index_db.execute("""
            CREATE TABLE IF NOT EXISTS archive_metadata (
                archive_id TEXT PRIMARY KEY,
                original_path TEXT NOT NULL,
                archive_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                modified_at TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                compressed_size_bytes INTEGER NOT NULL,
                compression_algorithm TEXT NOT NULL,
                encryption_algorithm TEXT NOT NULL,
                archive_format TEXT NOT NULL,
                checksum TEXT NOT NULL,
                checksum_algorithm TEXT NOT NULL,
                retention_days INTEGER NOT NULL,
                tags TEXT,
                metadata TEXT,
                corrupted INTEGER DEFAULT 0,
                verified INTEGER DEFAULT 0,
                version INTEGER DEFAULT 1
            )
        """)
        
        self._index_db.execute("""
            CREATE TABLE IF NOT EXISTS archive_entries (
                entry_id TEXT PRIMARY KEY,
                archive_id TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                module TEXT,
                function TEXT,
                message TEXT,
                context TEXT,
                raw_line TEXT,
                checksum TEXT,
                FOREIGN KEY (archive_id) REFERENCES archive_metadata(archive_id) ON DELETE CASCADE
            )
        """)
        
        self._index_db.execute("""
            CREATE TABLE IF NOT EXISTS archive_tags (
                tag TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        """)
        
        self._index_db.execute("""
            CREATE INDEX IF NOT EXISTS idx_entries_archive_id ON archive_entries(archive_id)
        """)
        self._index_db.execute("""
            CREATE INDEX IF NOT EXISTS idx_entries_timestamp ON archive_entries(timestamp)
        """)
        self._index_db.execute("""
            CREATE INDEX IF NOT EXISTS idx_entries_level ON archive_entries(level)
        """)
        self._index_db.execute("""
            CREATE INDEX IF NOT EXISTS idx_entries_message ON archive_entries(message)
        """)
        self._index_db.execute("""
            CREATE INDEX IF NOT EXISTS idx_metadata_created_at ON archive_metadata(created_at)
        """)
        self._index_db.execute("""
            CREATE INDEX IF NOT EXISTS idx_metadata_tags ON archive_metadata(tags)
        """)
        
        logger.info("index_db_initialized", path=str(index_path))

    def _start_watcher(self) -> None:
        """Start the file watcher for automatic archive processing."""
        if self.config.log_rotation_interval_hours > 0:
            self._file_watcher = Observer()
            handler = ArchiveWatcherHandler(self)
            self._file_watcher.schedule(handler, str(self.root_dir), recursive=True)
            self._file_watcher.start()
            logger.info("file_watcher_started", root_dir=str(self.root_dir))

    def _get_encryption_key(self) -> Optional[Fernet]:
        """Get the encryption key."""
        return self._encryption_key

    @contextmanager
    def _archive_lock(self) -> Iterator[None]:
        """Context manager for archive-level locking."""
        with self._lock:
            yield

    def _calculate_checksum(self, data: bytes, algorithm: str = "sha256") -> str:
        """
        Calculate checksum of data.

        Args:
            data: Bytes to checksum
            algorithm: Hash algorithm to use

        Returns:
            Hex digest of the checksum
        """
        if algorithm == "sha256":
            return hashlib.sha256(data).hexdigest()
        elif algorithm == "md5":
            return hashlib.md5(data).hexdigest()
        elif algorithm == "sha1":
            return hashlib.sha1(data).hexdigest()
        else:
            raise ValueError(f"Unsupported checksum algorithm: {algorithm}")

    def _compress_data(self, data: bytes, algorithm: CompressionAlgorithm) -> Tuple[bytes, str]:
        """
        Compress data using the specified algorithm.

        Args:
            data: Raw bytes to compress
            algorithm: Compression algorithm to use

        Returns:
            Tuple of (compressed_data, file_extension)
        """
        if algorithm == CompressionAlgorithm.NONE:
            return data, ""
        elif algorithm == CompressionAlgorithm.GZIP:
            return gzip.compress(data, compresslevel=9), ".gz"
        elif algorithm == CompressionAlgorithm.BZ2:
            return bz2.compress(data, compresslevel=9), ".bz2"
        elif algorithm == CompressionAlgorithm.LZMA:
            return lzma.compress(data, preset=9), ".xz"
        elif algorithm == CompressionAlgorithm.ZLIB:
            return zlib.compress(data, level=9), ".zlib"
        elif algorithm == CompressionAlgorithm.DEFLATE:
            # Use zlib with no header
            compressor = zlib.compressobj(level=9, wbits=-15)
            compressed = compressor.compress(data) + compressor.flush()
            return compressed, ".deflate"
        elif algorithm == CompressionAlgorithm.ZSTD:
            try:
                import zstandard as zstd
                compressor = zstd.ZstdCompressor(level=9)
                return compressor.compress(data), ".zst"
            except ImportError:
                logger.warning("zstd_not_available_falling_back_to_gzip")
                return gzip.compress(data, compresslevel=9), ".gz"
        else:
            raise ValueError(f"Unsupported compression algorithm: {algorithm}")

    def _decompress_data(self, data: bytes, algorithm: CompressionAlgorithm) -> bytes:
        """
        Decompress data using the specified algorithm.

        Args:
            data: Compressed bytes
            algorithm: Compression algorithm used

        Returns:
            Decompressed bytes
        """
        if algorithm == CompressionAlgorithm.NONE:
            return data
        elif algorithm == CompressionAlgorithm.GZIP:
            return gzip.decompress(data)
        elif algorithm == CompressionAlgorithm.BZ2:
            return bz2.decompress(data)
        elif algorithm == CompressionAlgorithm.LZMA:
            return lzma.decompress(data)
        elif algorithm == CompressionAlgorithm.ZLIB:
            return zlib.decompress(data)
        elif algorithm == CompressionAlgorithm.DEFLATE:
            decompressor = zlib.decompressobj(wbits=-15)
            return decompressor.decompress(data) + decompressor.flush()
        elif algorithm == CompressionAlgorithm.ZSTD:
            try:
                import zstandard as zstd
                decompressor = zstd.ZstdDecompressor()
                return decompressor.decompress(data)
            except ImportError:
                raise ArchiveError("Zstandard not available")
        else:
            raise ValueError(f"Unsupported decompression algorithm: {algorithm}")

    def _encrypt_data(self, data: bytes) -> bytes:
        """
        Encrypt data using the configured encryption.

        Args:
            data: Raw bytes to encrypt

        Returns:
            Encrypted bytes
        """
        if not self._encryption_key:
            raise ArchiveEncryptionError("Encryption key not configured")
        return self._encryption_key.encrypt(data)

    def _decrypt_data(self, data: bytes) -> bytes:
        """
        Decrypt data using the configured encryption.

        Args:
            data: Encrypted bytes

        Returns:
            Decrypted bytes
        """
        if not self._encryption_key:
            raise ArchiveEncryptionError("Encryption key not configured")
        try:
            return self._encryption_key.decrypt(data)
        except Exception as e:
            raise ArchiveEncryptionError(f"Decryption failed: {e}")

    def _get_archive_path(
        self,
        base_name: str,
        compression: CompressionAlgorithm,
        archive_format: ArchiveFormat,
    ) -> Path:
        """
        Generate the archive file path.

        Args:
            base_name: Base name of the archive
            compression: Compression algorithm
            archive_format: Archive format

        Returns:
            Full path to the archive file
        """
        extension_map = {
            ArchiveFormat.JSON: ".json",
            ArchiveFormat.JSONL: ".jsonl",
            ArchiveFormat.CSV: ".csv",
            ArchiveFormat.PICKLE: ".pkl",
            ArchiveFormat.PARQUET: ".parquet",
            ArchiveFormat.PROTOBUF: ".pb",
            ArchiveFormat.TEXT: ".txt",
            ArchiveFormat.BINARY: ".bin",
            ArchiveFormat.LOG: ".log",
        }
        
        extension = extension_map.get(archive_format, ".log")
        
        # Add compression extension
        compression_ext_map = {
            CompressionAlgorithm.GZIP: ".gz",
            CompressionAlgorithm.BZ2: ".bz2",
            CompressionAlgorithm.LZMA: ".xz",
            CompressionAlgorithm.ZLIB: ".zlib",
            CompressionAlgorithm.DEFLATE: ".deflate",
            CompressionAlgorithm.ZSTD: ".zst",
            CompressionAlgorithm.NONE: "",
        }
        comp_ext = compression_ext_map.get(compression, "")
        
        return self.root_dir / f"{base_name}{extension}{comp_ext}"

    def _read_log_file(self, file_path: Path) -> List[str]:
        """
        Read lines from a log file.

        Args:
            file_path: Path to the log file

        Returns:
            List of lines from the file
        """
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.readlines()
        except Exception as e:
            logger.error("failed_to_read_log_file", path=str(file_path), error=str(e))
            raise ArchiveError(f"Failed to read log file: {e}")

    def _parse_log_line(self, line: str) -> Optional[ArchiveIndexEntry]:
        """
        Parse a single log line for indexing.

        Args:
            line: Raw log line

        Returns:
            ArchiveIndexEntry or None if line is not parseable
        """
        # Try to parse as structured log (JSON)
        try:
            data = json.loads(line.strip())
            if isinstance(data, dict):
                timestamp = data.get("timestamp") or data.get("time") or data.get("date")
                if timestamp:
                    try:
                        if isinstance(timestamp, str):
                            ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        else:
                            ts = datetime.utcnow()
                    except ValueError:
                        ts = datetime.utcnow()
                else:
                    ts = datetime.utcnow()
                
                return ArchiveIndexEntry(
                    timestamp=ts,
                    level=data.get("level", "INFO").upper(),
                    module=data.get("module", ""),
                    function=data.get("function", ""),
                    message=data.get("message", "") or data.get("msg", ""),
                    context={k: v for k, v in data.items() if k not in ("timestamp", "level", "module", "function", "message", "msg")},
                    raw_line=line.strip(),
                    checksum=self._calculate_checksum(line.encode(), "md5")[:16],
                )
        except json.JSONDecodeError:
            pass
        
        # Try to parse syslog-like format
        syslog_pattern = re.compile(
            r'^(?P<timestamp>\w+\s+\d+\s+\d+:\d+:\d+)\s+(?P<host>\S+)\s+(?P<module>\S+):\s+(?P<message>.*)$'
        )
        match = syslog_pattern.match(line.strip())
        if match:
            try:
                ts = datetime.strptime(match.group("timestamp"), "%b %d %H:%M:%S")
                ts = ts.replace(year=datetime.utcnow().year)
            except ValueError:
                ts = datetime.utcnow()
            
            return ArchiveIndexEntry(
                timestamp=ts,
                level="INFO",
                module=match.group("module"),
                message=match.group("message"),
                raw_line=line.strip(),
                checksum=self._calculate_checksum(line.encode(), "md5")[:16],
            )
        
        # Try to parse NEXUS log format
        nexus_pattern = re.compile(
            r'^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+\|\s+(?P<level>[A-Z]+)\s+\|\s+(?P<module>[^\|]+)\s+\|\s+(?P<message>.*)$'
        )
        match = nexus_pattern.match(line.strip())
        if match:
            try:
                ts = datetime.fromisoformat(match.group("timestamp"))
            except ValueError:
                ts = datetime.utcnow()
            
            return ArchiveIndexEntry(
                timestamp=ts,
                level=match.group("level"),
                module=match.group("module").strip(),
                message=match.group("message").strip(),
                raw_line=line.strip(),
                checksum=self._calculate_checksum(line.encode(), "md5")[:16],
            )
        
        # Fallback: create entry with just the raw line
        return ArchiveIndexEntry(
            timestamp=datetime.utcnow(),
            level="UNKNOWN",
            message=line.strip()[:500],
            raw_line=line.strip(),
            checksum=self._calculate_checksum(line.encode(), "md5")[:16],
        )

    def _serialize_archive(
        self,
        lines: List[str],
        archive_format: ArchiveFormat,
        metadata: ArchiveMetadata,
    ) -> bytes:
        """
        Serialize the log lines into the specified format.

        Args:
            lines: List of log lines
            archive_format: Desired archive format
            metadata: Archive metadata

        Returns:
            Serialized bytes
        """
        if archive_format == ArchiveFormat.JSON:
            data = []
            for line in lines:
                entry = self._parse_log_line(line)
                if entry:
                    data.append(entry.to_dict())
                else:
                    data.append({"raw": line.strip(), "timestamp": datetime.utcnow().isoformat()})
            return json.dumps(data, indent=2, default=str).encode("utf-8")
        
        elif archive_format == ArchiveFormat.JSONL:
            data = []
            for line in lines:
                entry = self._parse_log_line(line)
                if entry:
                    data.append(json.dumps(entry.to_dict(), default=str))
                else:
                    data.append(json.dumps({"raw": line.strip(), "timestamp": datetime.utcnow().isoformat()}))
            return "\n".join(data).encode("utf-8")
        
        elif archive_format == ArchiveFormat.CSV:
            import csv
            from io import StringIO
            
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(["timestamp", "level", "module", "function", "message", "raw"])
            
            for line in lines:
                entry = self._parse_log_line(line)
                if entry:
                    writer.writerow([
                        entry.timestamp.isoformat(),
                        entry.level,
                        entry.module,
                        entry.function,
                        entry.message,
                        entry.raw_line,
                    ])
                else:
                    writer.writerow([
                        datetime.utcnow().isoformat(),
                        "UNKNOWN",
                        "",
                        "",
                        line.strip()[:500],
                        line.strip(),
                    ])
            
            return output.getvalue().encode("utf-8")
        
        elif archive_format == ArchiveFormat.PICKLE:
            entries = []
            for line in lines:
                entry = self._parse_log_line(line)
                if entry:
                    entries.append(entry)
            return pickle.dumps(entries, protocol=pickle.HIGHEST_PROTOCOL)
        
        elif archive_format == ArchiveFormat.TEXT:
            return "".join(lines).encode("utf-8")
        
        elif archive_format == ArchiveFormat.LOG:
            return "".join(lines).encode("utf-8")
        
        elif archive_format == ArchiveFormat.BINARY:
            return b"\n".join(line.encode("utf-8", errors="replace") for line in lines)
        
        else:
            raise ValueError(f"Unsupported archive format: {archive_format}")

    def _deserialize_archive(
        self,
        data: bytes,
        archive_format: ArchiveFormat,
    ) -> List[str]:
        """
        Deserialize the archive data back to lines.

        Args:
            data: Serialized archive data
            archive_format: Archive format used

        Returns:
            List of log lines
        """
        if archive_format == ArchiveFormat.JSON:
            parsed = json.loads(data.decode("utf-8"))
            lines = []
            for item in parsed:
                if "raw" in item:
                    lines.append(item["raw"])
                elif "message" in item:
                    lines.append(item["message"])
                else:
                    lines.append(json.dumps(item, default=str))
            return lines
        
        elif archive_format == ArchiveFormat.JSONL:
            lines = []
            for line in data.decode("utf-8").splitlines():
                if line.strip():
                    try:
                        item = json.loads(line)
                        if "raw" in item:
                            lines.append(item["raw"])
                        else:
                            lines.append(line)
                    except json.JSONDecodeError:
                        lines.append(line)
            return lines
        
        elif archive_format == ArchiveFormat.CSV:
            import csv
            from io import StringIO
            
            lines = []
            content = data.decode("utf-8")
            reader = csv.DictReader(StringIO(content))
            for row in reader:
                if "raw" in row and row["raw"]:
                    lines.append(row["raw"])
                else:
                    # Reconstruct from fields
                    parts = []
                    if row.get("timestamp"):
                        parts.append(row["timestamp"])
                    if row.get("level"):
                        parts.append(f"[{row['level']}]")
                    if row.get("module"):
                        parts.append(f"({row['module']})")
                    if row.get("message"):
                        parts.append(row["message"])
                    lines.append(" ".join(parts))
            return lines
        
        elif archive_format == ArchiveFormat.PICKLE:
            entries = pickle.loads(data)
            return [entry.raw_line for entry in entries]
        
        elif archive_format in (ArchiveFormat.TEXT, ArchiveFormat.LOG):
            return data.decode("utf-8", errors="replace").splitlines(keepends=True)
        
        elif archive_format == ArchiveFormat.BINARY:
            return data.decode("utf-8", errors="replace").splitlines(keepends=True)
        
        else:
            raise ValueError(f"Unsupported archive format: {archive_format}")

    def _create_archive_metadata(
        self,
        original_path: str,
        archive_path: str,
        size_bytes: int,
        compressed_size_bytes: int,
        compression: CompressionAlgorithm,
        encryption: EncryptionAlgorithm,
        archive_format: ArchiveFormat,
        checksum: str,
        retention_days: int,
        tags: Optional[List[str]] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> ArchiveMetadata:
        """Create archive metadata object."""
        return ArchiveMetadata(
            archive_id=str(uuid4()),
            original_path=original_path,
            archive_path=archive_path,
            created_at=datetime.utcnow(),
            modified_at=datetime.utcnow(),
            size_bytes=size_bytes,
            compressed_size_bytes=compressed_size_bytes,
            compression_algorithm=compression,
            encryption_algorithm=encryption,
            archive_format=archive_format,
            checksum=checksum,
            retention_days=retention_days,
            tags=tags or [],
            metadata=extra_metadata or {},
            verified=True,
        )

    def archive_file(
        self,
        file_path: Union[str, Path],
        tags: Optional[List[str]] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> ArchiveMetadata:
        """
        Archive a log file.

        Args:
            file_path: Path to the log file to archive
            tags: Tags to associate with the archive
            extra_metadata: Extra metadata to include

        Returns:
            ArchiveMetadata of the created archive
        """
        with self._archive_lock():
            file_path = Path(file_path)
            if not file_path.exists():
                raise ArchiveNotFoundError(f"File not found: {file_path}")
            
            # Read and process the file
            lines = self._read_log_file(file_path)
            raw_data = "".join(lines).encode("utf-8", errors="replace")
            
            # Check for deduplication
            if self.config.enable_deduplication:
                checksum = self._calculate_checksum(raw_data)
                existing = self.find_archive_by_checksum(checksum)
                if existing:
                    logger.info(
                        "duplicate_archive_found",
                        archive_id=existing.archive_id,
                        file_path=str(file_path),
                    )
                    return existing
            
            # Serialize
            serialized = self._serialize_archive(
                lines,
                self.config.archive_format,
                None,
            )
            
            # Compress
            if self.config.enable_compression:
                compressed, comp_ext = self._compress_data(serialized, self.config.compression)
            else:
                compressed = serialized
                comp_ext = ""
            
            # Encrypt
            if self.config.enable_encryption:
                encrypted = self._encrypt_data(compressed)
                encryption_algorithm = self.config.encryption
            else:
                encrypted = compressed
                encryption_algorithm = EncryptionAlgorithm.NONE
            
            # Calculate checksum
            archive_checksum = self._calculate_checksum(encrypted)
            
            # Generate archive path
            base_name = f"{file_path.stem}_{int(datetime.utcnow().timestamp())}"
            archive_path = self._get_archive_path(
                base_name,
                self.config.compression,
                self.config.archive_format,
            )
            
            # Write the archive
            with open(archive_path, "wb") as f:
                f.write(encrypted)
            
            # Create metadata
            metadata = self._create_archive_metadata(
                original_path=str(file_path),
                archive_path=str(archive_path),
                size_bytes=len(raw_data),
                compressed_size_bytes=len(encrypted),
                compression=self.config.compression,
                encryption=encryption_algorithm,
                archive_format=self.config.archive_format,
                checksum=archive_checksum,
                retention_days=self.config.retention_days,
                tags=tags,
                extra_metadata=extra_metadata,
            )
            
            # Index the archive
            if self.config.enable_indexing:
                self._index_archive(metadata, lines)
            
            self._metrics["archives_created"] += 1
            self._metrics["total_bytes_saved"] += len(raw_data) - len(encrypted)
            
            logger.info(
                "archive_created",
                archive_id=metadata.archive_id,
                archive_path=str(archive_path),
                original_size=len(raw_data),
                compressed_size=len(encrypted),
                ratio=f"{(len(encrypted) / len(raw_data) * 100):.1f}%",
            )
            
            return metadata

    def _index_archive(self, metadata: ArchiveMetadata, lines: List[str]) -> None:
        """
        Index an archive for searching.

        Args:
            metadata: Archive metadata
            lines: Lines from the archive
        """
        if not self._index_db:
            return
        
        try:
            # Insert metadata
            self._index_db.execute("""
                INSERT OR REPLACE INTO archive_metadata (
                    archive_id, original_path, archive_path, created_at, modified_at,
                    size_bytes, compressed_size_bytes, compression_algorithm,
                    encryption_algorithm, archive_format, checksum,
                    checksum_algorithm, retention_days, tags, metadata,
                    corrupted, verified, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.archive_id,
                metadata.original_path,
                metadata.archive_path,
                metadata.created_at.isoformat(),
                metadata.modified_at.isoformat(),
                metadata.size_bytes,
                metadata.compressed_size_bytes,
                metadata.compression_algorithm.value,
                metadata.encryption_algorithm.value,
                metadata.archive_format.value,
                metadata.checksum,
                metadata.checksum_algorithm,
                metadata.retention_days,
                json.dumps(metadata.tags),
                json.dumps(metadata.metadata),
                1 if metadata.corrupted else 0,
                1 if metadata.verified else 0,
                metadata.version,
            ))
            
            # Insert entries
            for idx, line in enumerate(lines):
                entry = self._parse_log_line(line)
                if entry:
                    entry.archive_id = metadata.archive_id
                    entry.line_number = idx + 1
                    self._index_db.execute("""
                        INSERT INTO archive_entries (
                            entry_id, archive_id, line_number, timestamp, level,
                            module, function, message, context, raw_line, checksum
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        entry.entry_id,
                        entry.archive_id,
                        entry.line_number,
                        entry.timestamp.isoformat(),
                        entry.level,
                        entry.module,
                        entry.function,
                        entry.message,
                        json.dumps(entry.context, default=str),
                        entry.raw_line,
                        entry.checksum,
                    ))
            
            self._metrics["archives_indexed"] += 1
            
        except Exception as e:
            logger.error("failed_to_index_archive", archive_id=metadata.archive_id, error=str(e))
            raise ArchiveIndexError(f"Failed to index archive: {e}")

    def restore_archive(self, archive_id: str, output_path: Optional[Union[str, Path]] = None) -> str:
        """
        Restore an archive to its original format.

        Args:
            archive_id: ID of the archive to restore
            output_path: Optional path for the restored file

        Returns:
            Path to the restored file
        """
        with self._archive_lock():
            metadata = self.get_archive_metadata(archive_id)
            if not metadata:
                raise ArchiveNotFoundError(f"Archive not found: {archive_id}")
            
            archive_path = Path(metadata.archive_path)
            if not archive_path.exists():
                raise ArchiveNotFoundError(f"Archive file not found: {archive_path}")
            
            # Read the archive
            with open(archive_path, "rb") as f:
                data = f.read()
            
            # Decrypt if needed
            if metadata.encryption_algorithm != EncryptionAlgorithm.NONE:
                data = self._decrypt_data(data)
            
            # Decompress if needed
            if metadata.compression_algorithm != CompressionAlgorithm.NONE:
                data = self._decompress_data(data, metadata.compression_algorithm)
            
            # Verify checksum
            if self.config.enable_corruption_check:
                checksum = self._calculate_checksum(data)
                if checksum != metadata.checksum:
                    logger.error(
                        "corruption_detected",
                        archive_id=archive_id,
                        expected=metadata.checksum,
                        actual=checksum,
                    )
                    metadata.corrupted = True
                    self._update_metadata(metadata)
                    self._metrics["corruption_detected"] += 1
                    raise ArchiveCorruptionError(f"Archive corrupted: {archive_id}")
            
            # Deserialize
            lines = self._deserialize_archive(data, metadata.archive_format)
            
            # Write output
            if output_path is None:
                output_path = Path(metadata.original_path)
            else:
                output_path = Path(output_path)
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8", errors="replace") as f:
                f.writelines(lines)
            
            self._metrics["archives_restored"] += 1
            
            logger.info(
                "archive_restored",
                archive_id=archive_id,
                output_path=str(output_path),
            )
            
            return str(output_path)

    def get_archive_metadata(self, archive_id: str) -> Optional[ArchiveMetadata]:
        """Get metadata for an archive."""
        if not self._index_db:
            return None
        
        cursor = self._index_db.execute(
            "SELECT * FROM archive_metadata WHERE archive_id = ?",
            (archive_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        
        columns = [desc[0] for desc in cursor.description]
        data = dict(zip(columns, row))
        return ArchiveMetadata.from_dict(data)

    def find_archive_by_checksum(self, checksum: str) -> Optional[ArchiveMetadata]:
        """Find an archive by its checksum."""
        if not self._index_db:
            return None
        
        cursor = self._index_db.execute(
            "SELECT * FROM archive_metadata WHERE checksum = ?",
            (checksum,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        
        columns = [desc[0] for desc in cursor.description]
        data = dict(zip(columns, row))
        return ArchiveMetadata.from_dict(data)

    def _update_metadata(self, metadata: ArchiveMetadata) -> None:
        """Update metadata in the index."""
        if not self._index_db:
            return
        
        self._index_db.execute("""
            UPDATE archive_metadata SET
                modified_at = ?, size_bytes = ?, compressed_size_bytes = ?,
                corrupted = ?, verified = ?, metadata = ?
            WHERE archive_id = ?
        """, (
            datetime.utcnow().isoformat(),
            metadata.size_bytes,
            metadata.compressed_size_bytes,
            1 if metadata.corrupted else 0,
            1 if metadata.verified else 0,
            json.dumps(metadata.metadata),
            metadata.archive_id,
        ))

    def search_archives(
        self,
        query: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        module: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ArchiveIndexEntry]:
        """
        Search archived logs.

        Args:
            query: Search query (SQL LIKE pattern)
            start_time: Filter entries after this time
            end_time: Filter entries before this time
            level: Filter by log level
            module: Filter by module name
            tags: Filter by archive tags
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of matching ArchiveIndexEntry objects
        """
        if not self._index_db:
            return []
        
        sql = "SELECT * FROM archive_entries WHERE 1=1"
        params = []
        
        if query:
            sql += " AND (message LIKE ? OR raw_line LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])
        
        if start_time:
            sql += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        
        if end_time:
            sql += " AND timestamp <= ?"
            params.append(end_time.isoformat())
        
        if level:
            sql += " AND level = ?"
            params.append(level.upper())
        
        if module:
            sql += " AND module LIKE ?"
            params.append(f"%{module}%")
        
        if tags:
            # Join with archive_metadata to filter by tags
            sql = """
                SELECT ae.* FROM archive_entries ae
                INNER JOIN archive_metadata am ON ae.archive_id = am.archive_id
                WHERE 1=1
            """
            params = []
            if query:
                sql += " AND (ae.message LIKE ? OR ae.raw_line LIKE ?)"
                params.extend([f"%{query}%", f"%{query}%"])
            if start_time:
                sql += " AND ae.timestamp >= ?"
                params.append(start_time.isoformat())
            if end_time:
                sql += " AND ae.timestamp <= ?"
                params.append(end_time.isoformat())
            if level:
                sql += " AND ae.level = ?"
                params.append(level.upper())
            if module:
                sql += " AND ae.module LIKE ?"
                params.append(f"%{module}%")
            
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("am.tags LIKE ?")
                params.append(f'%"{tag}"%')
            if tag_conditions:
                sql += " AND (" + " OR ".join(tag_conditions) + ")"
        
        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = self._index_db.execute(sql, params)
        rows = cursor.fetchall()
        
        columns = [desc[0] for desc in cursor.description]
        results = []
        for row in rows:
            data = dict(zip(columns, row))
            results.append(ArchiveIndexEntry.from_dict(data))
        
        return results

    def search_archives_realtime(
        self,
        query: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        module: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ArchiveIndexEntry]:
        """Alias for search_archives."""
        return self.search_archives(
            query=query,
            start_time=start_time,
            end_time=end_time,
            level=level,
            module=module,
            tags=tags,
            limit=limit,
            offset=offset,
        )

    def search_archives_async(
        self,
        query: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        module: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Coroutine[Any, Any, List[ArchiveIndexEntry]]:
        """Async wrapper for search_archives."""
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(
            self._executor,
            self.search_archives,
            query,
            start_time,
            end_time,
            level,
            module,
            tags,
            limit,
            offset,
        )

    def apply_retention_policy(self) -> Dict[str, int]:
        """
        Apply the retention policy to delete old archives.

        Returns:
            Dictionary with deletion statistics
        """
        with self._archive_lock():
            deleted_count = 0
            deleted_size = 0
            expired_archives = []
            
            # Get all archives
            cursor = self._index_db.execute(
                "SELECT * FROM archive_metadata WHERE retention_days > 0"
            )
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            
            now = datetime.utcnow()
            
            for row in rows:
                data = dict(zip(columns, row))
                metadata = ArchiveMetadata.from_dict(data)
                
                # Check if expired
                age = (now - metadata.created_at).days
                if age >= metadata.retention_days:
                    expired_archives.append(metadata)
            
            # Delete expired archives
            for metadata in expired_archives:
                try:
                    archive_path = Path(metadata.archive_path)
                    if archive_path.exists():
                        deleted_size += archive_path.stat().st_size
                        archive_path.unlink()
                    
                    self._index_db.execute(
                        "DELETE FROM archive_metadata WHERE archive_id = ?",
                        (metadata.archive_id,)
                    )
                    self._index_db.execute(
                        "DELETE FROM archive_entries WHERE archive_id = ?",
                        (metadata.archive_id,)
                    )
                    deleted_count += 1
                    self._metrics["archives_deleted"] += 1
                    
                    logger.info(
                        "archive_expired",
                        archive_id=metadata.archive_id,
                        age_days=age,
                        retention_days=metadata.retention_days,
                    )
                except Exception as e:
                    logger.error(
                        "failed_to_delete_expired_archive",
                        archive_id=metadata.archive_id,
                        error=str(e),
                    )
            
            # Also check size-based retention
            if self.config.retention_policy in (RetentionPolicy.SIZE_BASED, RetentionPolicy.HYBRID):
                total_size = self.get_archive_size()
                max_bytes = self.config.max_size_gb * 1024 * 1024 * 1024
                
                if total_size > max_bytes:
                    # Get archives sorted by creation time (oldest first)
                    cursor = self._index_db.execute(
                        "SELECT * FROM archive_metadata ORDER BY created_at ASC"
                    )
                    rows = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    
                    for row in rows:
                        if total_size <= max_bytes * 0.8:  # Reduce to 80% of max
                            break
                        
                        data = dict(zip(columns, row))
                        metadata = ArchiveMetadata.from_dict(data)
                        
                        # Skip if this archive is protected (e.g., has certain tags)
                        if "protected" in metadata.tags:
                            continue
                        
                        try:
                            archive_path = Path(metadata.archive_path)
                            if archive_path.exists():
                                file_size = archive_path.stat().st_size
                                total_size -= file_size
                                deleted_size += file_size
                                archive_path.unlink()
                            
                            self._index_db.execute(
                                "DELETE FROM archive_metadata WHERE archive_id = ?",
                                (metadata.archive_id,)
                            )
                            self._index_db.execute(
                                "DELETE FROM archive_entries WHERE archive_id = ?",
                                (metadata.archive_id,)
                            )
                            deleted_count += 1
                            self._metrics["archives_deleted"] += 1
                            
                            logger.info(
                                "archive_deleted_by_size_policy",
                                archive_id=metadata.archive_id,
                                size_mb=file_size / (1024 * 1024),
                            )
                        except Exception as e:
                            logger.error(
                                "failed_to_delete_archive_by_size",
                                archive_id=metadata.archive_id,
                                error=str(e),
                            )
            
            logger.info(
                "retention_policy_applied",
                deleted_count=deleted_count,
                deleted_size_mb=deleted_size / (1024 * 1024),
                remaining_size_mb=self.get_archive_size() / (1024 * 1024),
            )
            
            return {
                "deleted_count": deleted_count,
                "deleted_size_bytes": deleted_size,
                "remaining_size_bytes": self.get_archive_size(),
            }

    def get_archive_size(self) -> int:
        """Get the total size of all archives."""
        total = 0
        for root, dirs, files in os.walk(self.root_dir):
            for file in files:
                if file == "index.db" or file.endswith(".db-journal"):
                    continue
                file_path = Path(root) / file
                try:
                    total += file_path.stat().st_size
                except OSError:
                    pass
        return total

    def verify_archive_integrity(self, archive_id: str) -> bool:
        """
        Verify the integrity of an archive.

        Args:
            archive_id: ID of the archive to verify

        Returns:
            True if the archive is valid, False otherwise
        """
        metadata = self.get_archive_metadata(archive_id)
        if not metadata:
            return False
        
        archive_path = Path(metadata.archive_path)
        if not archive_path.exists():
            return False
        
        try:
            with open(archive_path, "rb") as f:
                data = f.read()
            
            # Decrypt if needed
            if metadata.encryption_algorithm != EncryptionAlgorithm.NONE:
                data = self._decrypt_data(data)
            
            # Decompress if needed
            if metadata.compression_algorithm != CompressionAlgorithm.NONE:
                data = self._decompress_data(data, metadata.compression_algorithm)
            
            # Verify checksum
            checksum = self._calculate_checksum(data)
            if checksum != metadata.checksum:
                metadata.corrupted = True
                self._update_metadata(metadata)
                self._metrics["corruption_detected"] += 1
                return False
            
            # Verify serialization
            try:
                lines = self._deserialize_archive(data, metadata.archive_format)
                if not lines:
                    metadata.corrupted = True
                    self._update_metadata(metadata)
                    self._metrics["corruption_detected"] += 1
                    return False
            except Exception:
                metadata.corrupted = True
                self._update_metadata(metadata)
                self._metrics["corruption_detected"] += 1
                return False
            
            metadata.verified = True
            self._update_metadata(metadata)
            self._metrics["verification_passed"] += 1
            return True
            
        except Exception as e:
            logger.error(
                "verification_failed",
                archive_id=archive_id,
                error=str(e),
            )
            metadata.corrupted = True
            self._update_metadata(metadata)
            self._metrics["corruption_detected"] += 1
            return False

    def verify_all_archives(self) -> Dict[str, bool]:
        """
        Verify integrity of all archives.

        Returns:
            Dictionary mapping archive_id to verification status
        """
        results = {}
        cursor = self._index_db.execute("SELECT archive_id FROM archive_metadata")
        rows = cursor.fetchall()
        
        for row in rows:
            archive_id = row[0]
            results[archive_id] = self.verify_archive_integrity(archive_id)
        
        return results

    def get_metrics(self) -> Dict[str, Any]:
        """Get archive system metrics."""
        return {
            **self._metrics,
            "total_size_bytes": self.get_archive_size(),
            "total_archives": self.get_archive_count(),
            "total_entries": self.get_entry_count(),
        }

    def get_archive_count(self) -> int:
        """Get the total number of archives."""
        if not self._index_db:
            return 0
        cursor = self._index_db.execute("SELECT COUNT(*) FROM archive_metadata")
        return cursor.fetchone()[0]

    def get_entry_count(self) -> int:
        """Get the total number of indexed entries."""
        if not self._index_db:
            return 0
        cursor = self._index_db.execute("SELECT COUNT(*) FROM archive_entries")
        return cursor.fetchone()[0]

    def close(self) -> None:
        """Close the archive manager."""
        if self._closed:
            return
        
        self._closed = True
        
        if self._file_watcher:
            self._file_watcher.stop()
            self._file_watcher.join()
        
        if self._index_db:
            self._index_db.close()
        
        self._executor.shutdown(wait=True)
        
        logger.info("archive_manager_closed")

    def __enter__(self) -> "ArchiveManager":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    async def __aenter__(self) -> "ArchiveManager":
        return self

    async def __aexit__(self, *args) -> None:
        self.close()


# === FILE WATCHER ===

class ArchiveWatcherHandler(FileSystemEventHandler):
    """Watchdog handler for automatic archive processing."""

    def __init__(self, manager: ArchiveManager):
        self.manager = manager
        self._logger = structlog.get_logger(__name__)

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".log"):
            try:
                self.manager.archive_file(event.src_path)
                self._logger.info(
                    "auto_archive_created",
                    path=event.src_path,
                )
            except Exception as e:
                self._logger.error(
                    "auto_archive_failed",
                    path=event.src_path,
                    error=str(e),
                )

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".log"):
            # Check if file is stable (hasn't been modified in 5 seconds)
            try:
                time.sleep(5)
                self.manager.archive_file(event.src_path)
                self._logger.info(
                    "auto_archive_modified",
                    path=event.src_path,
                )
            except Exception as e:
                self._logger.error(
                    "auto_archive_failed",
                    path=event.src_path,
                    error=str(e),
                )


# === FACTORY FUNCTIONS ===

def create_archive_manager(
    root_dir: str = "logs/archive",
    compression: str = "gzip",
    encryption: str = "none",
    retention_days: int = 90,
    max_size_gb: float = 10.0,
    **kwargs,
) -> ArchiveManager:
    """
    Create an ArchiveManager with sensible defaults.

    Args:
        root_dir: Root directory for archives
        compression: Compression algorithm ('none', 'gzip', 'bz2', 'lzma', 'zstd')
        encryption: Encryption algorithm ('none', 'fernet')
        retention_days: Number of days to keep archives
        max_size_gb: Maximum total archive size in GB
        **kwargs: Additional configuration options

    Returns:
        Configured ArchiveManager instance
    """
    config = {
        "root_dir": root_dir,
        "compression": CompressionAlgorithm(compression),
        "encryption": EncryptionAlgorithm(encryption),
        "retention_days": retention_days,
        "max_size_gb": max_size_gb,
        **kwargs,
    }
    return ArchiveManager(config)


# === MODULE EXPORTS ===

__all__ = [
    # Main classes
    "ArchiveManager",
    "ArchiveConfig",
    "ArchiveMetadata",
    "ArchiveIndexEntry",
    
    # Enums
    "CompressionAlgorithm",
    "EncryptionAlgorithm",
    "ArchiveFormat",
    "RetentionPolicy",
    "ArchiveEventType",
    
    # Exceptions
    "ArchiveError",
    "ArchiveCorruptionError",
    "ArchiveEncryptionError",
    "ArchiveNotFoundError",
    "ArchiveIndexError",
    
    # Factory functions
    "create_archive_manager",
]

logger.info("archive_module_loaded", version="3.0.0")
