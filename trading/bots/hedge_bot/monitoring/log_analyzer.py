# trading/bots/hedge_bot/monitoring/log_analyzer.py

"""
NEXUS HEDGE BOT - LOG ANALYZER
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced log analysis system with pattern detection, anomaly detection,
log correlation, and real-time log streaming capabilities.

Version: 3.0.0
"""

import asyncio
import json
import re
import sqlite3
import threading
import time
import traceback
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Iterator, Callable
from uuid import uuid4

import aiofiles
import structlog
import yaml
from pydantic import BaseModel, Field, validator
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class LogPatternType(str, Enum):
    """Types of log patterns."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    PERFORMANCE = "performance"
    SECURITY = "security"
    TRADING = "trading"
    SYSTEM = "system"
    NETWORK = "network"
    ANOMALY = "anomaly"
    FREQUENT = "frequent"


class AnomalySeverity(str, Enum):
    """Anomaly severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# === DATA MODELS ===

@dataclass
class LogEntry:
    """Log entry data model."""
    entry_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    level: LogLevel = LogLevel.INFO
    module: str = ""
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    source_file: str = ""
    line_number: int = 0
    thread_id: Optional[str] = None
    process_id: Optional[int] = None
    correlation_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogEntry":
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["level"] = LogLevel(data["level"])
        return cls(**data)


@dataclass
class LogPattern:
    """Detected log pattern."""
    pattern_id: str = field(default_factory=lambda: str(uuid4()))
    pattern_type: LogPatternType = LogPatternType.INFO
    pattern: str = ""
    description: str = ""
    occurrences: int = 0
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    frequency: float = 0.0  # occurrences per hour
    confidence: float = 0.0
    related_entries: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "pattern_type": self.pattern_type.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogPattern":
        data = data.copy()
        data["first_seen"] = datetime.fromisoformat(data["first_seen"])
        data["last_seen"] = datetime.fromisoformat(data["last_seen"])
        data["pattern_type"] = LogPatternType(data["pattern_type"])
        return cls(**data)


@dataclass
class Anomaly:
    """Detected anomaly in logs."""
    anomaly_id: str = field(default_factory=lambda: str(uuid4()))
    severity: AnomalySeverity = AnomalySeverity.MEDIUM
    message: str = ""
    description: str = ""
    detected_at: datetime = field(default_factory=datetime.utcnow)
    related_entries: List[str] = field(default_factory=list)
    pattern_id: Optional[str] = None
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "detected_at": self.detected_at.isoformat(),
            "severity": self.severity.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Anomaly":
        data = data.copy()
        data["detected_at"] = datetime.fromisoformat(data["detected_at"])
        data["severity"] = AnomalySeverity(data["severity"])
        return cls(**data)


# === LOG ANALYZER ===

class LogAnalyzer:
    """
    Advanced log analysis system with pattern detection, anomaly detection,
    log correlation, and real-time log streaming capabilities.
    """

    def __init__(
        self,
        config: Union[Dict[str, Any], str],
        log_files: Optional[List[str]] = None,
    ):
        """
        Initialize the LogAnalyzer.

        Args:
            config: Configuration dictionary or path to config file
            log_files: List of log file paths to monitor
        """
        if isinstance(config, str):
            with open(config, "r") as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = config

        self.log_files = log_files or self.config.get("log_files", [])
        self._lock = threading.RLock()
        self._closed = False

        # Database for persistent storage
        self._db_path = Path(self.config.get("db_path", "log_analysis.db"))
        self._initialize_db()

        # In-memory storage
        self._log_entries: List[LogEntry] = []
        self._patterns: List[LogPattern] = []
        self._anomalies: List[Anomaly] = []
        self._entry_stream: deque = deque(maxlen=10000)

        # Pattern detection
        self._pattern_cache: Dict[str, LogPattern] = {}
        self._frequent_patterns: Dict[str, int] = defaultdict(int)

        # Anomaly detection
        self._anomaly_threshold = self.config.get("anomaly_threshold", 3.0)
        self._baseline_stats: Dict[str, Dict[str, float]] = {}

        # File monitoring
        self._file_positions: Dict[str, int] = {}
        self._file_mtimes: Dict[str, float] = {}

        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._monitor_task: Optional[asyncio.Task] = None
        self._analysis_task: Optional[asyncio.Task] = None

        # Initialize
        self._initialize_file_positions()
        self._start_background_tasks()

        logger.info(
            "log_analyzer_initialized",
            db_path=str(self._db_path),
            log_files=len(self.log_files),
        )

    def _initialize_db(self) -> None:
        """Initialize the SQLite database."""
        self._db = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            isolation_level=None,
        )
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")

        self._db.execute("""
            CREATE TABLE IF NOT EXISTS log_entries (
                entry_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                module TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT,
                source_file TEXT,
                line_number INTEGER,
                thread_id TEXT,
                process_id INTEGER,
                correlation_id TEXT,
                tags TEXT
            )
        """)

        self._db.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                pattern_id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                pattern TEXT NOT NULL,
                description TEXT,
                occurrences INTEGER DEFAULT 0,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                frequency REAL DEFAULT 0,
                confidence REAL DEFAULT 0,
                related_entries TEXT,
                tags TEXT,
                metadata TEXT
            )
        """)

        self._db.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                anomaly_id TEXT PRIMARY KEY,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                description TEXT,
                detected_at TEXT NOT NULL,
                related_entries TEXT,
                pattern_id TEXT,
                score REAL DEFAULT 0,
                metadata TEXT,
                acknowledged INTEGER DEFAULT 0,
                resolved INTEGER DEFAULT 0
            )
        """)

        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_entries_timestamp ON log_entries(timestamp)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_entries_level ON log_entries(level)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_entries_module ON log_entries(module)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON anomalies(severity)
        """)

        logger.info("log_analyzer_db_initialized", db_path=str(self._db_path))

    def _initialize_file_positions(self) -> None:
        """Initialize file positions for monitoring."""
        for log_file in self.log_files:
            file_path = Path(log_file)
            if file_path.exists():
                self._file_positions[log_file] = file_path.stat().st_size
                self._file_mtimes[log_file] = file_path.stat().st_mtime

    def _start_background_tasks(self) -> None:
        """Start background tasks."""
        try:
            loop = asyncio.get_event_loop()

            # File monitoring task
            self._monitor_task = loop.create_task(self._monitor_loop())

            # Analysis task
            self._analysis_task = loop.create_task(self._analysis_loop())

            logger.info("background_tasks_started")
        except RuntimeError:
            logger.warning("no_event_loop_available_background_tasks_disabled")

    async def _monitor_loop(self) -> None:
        """Background task for monitoring log files."""
        while not self._closed:
            try:
                await self._check_log_files()
                await asyncio.sleep(self.config.get("monitor_interval", 1.0))
            except Exception as e:
                logger.error("monitor_loop_error", error=str(e))
                await asyncio.sleep(5)

    async def _analysis_loop(self) -> None:
        """Background task for analyzing logs."""
        while not self._closed:
            try:
                await self._run_analysis()
                await asyncio.sleep(self.config.get("analysis_interval", 60.0))
            except Exception as e:
                logger.error("analysis_loop_error", error=str(e))
                await asyncio.sleep(30)

    async def _check_log_files(self) -> None:
        """Check log files for new entries."""
        for log_file in self.log_files:
            try:
                await self._process_log_file(log_file)
            except Exception as e:
                logger.error(
                    "log_file_processing_error",
                    file=log_file,
                    error=str(e),
                )

    async def _process_log_file(self, log_file: str) -> None:
        """Process a single log file for new entries."""
        file_path = Path(log_file)

        if not file_path.exists():
            return

        # Check if file was rotated
        current_size = file_path.stat().st_size
        current_mtime = file_path.stat().st_mtime

        if log_file in self._file_positions:
            if current_size < self._file_positions[log_file]:
                # File was rotated, reset position
                self._file_positions[log_file] = 0

        # Read new entries
        try:
            async with aiofiles.open(log_file, "r") as f:
                await f.seek(self._file_positions[log_file])
                async for line in f:
                    line = line.strip()
                    if line:
                        entry = self._parse_log_line(line, log_file)
                        if entry:
                            await self._add_entry(entry)

                self._file_positions[log_file] = await f.tell()

        except Exception as e:
            logger.error(
                "log_file_read_error",
                file=log_file,
                error=str(e),
            )

    def _parse_log_line(self, line: str, source_file: str) -> Optional[LogEntry]:
        """
        Parse a log line into a LogEntry.

        Args:
            line: Raw log line
            source_file: Source file path

        Returns:
            Parsed LogEntry or None if parsing fails
        """
        # Try structured JSON format
        try:
            data = json.loads(line)
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

                return LogEntry(
                    timestamp=ts,
                    level=LogLevel(data.get("level", "info").lower()),
                    module=data.get("module", ""),
                    message=data.get("message", "") or data.get("msg", ""),
                    details={k: v for k, v in data.items() if k not in ("timestamp", "level", "module", "message", "msg")},
                    source_file=source_file,
                    correlation_id=data.get("correlation_id") or data.get("correlationId"),
                    tags=data.get("tags", []),
                )
        except json.JSONDecodeError:
            pass

        # Try to parse NEXUS log format
        nexus_pattern = re.compile(
            r'^\[(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]\s+\|\s+(?P<level>[A-Z]+)\s+\|\s+(?P<module>[^\|]+)\s+\|\s+(?P<message>.*)$'
        )
        match = nexus_pattern.match(line.strip())
        if match:
            try:
                ts = datetime.fromisoformat(match.group("timestamp"))
            except ValueError:
                ts = datetime.utcnow()

            return LogEntry(
                timestamp=ts,
                level=LogLevel(match.group("level").lower()),
                module=match.group("module").strip(),
                message=match.group("message").strip(),
                source_file=source_file,
            )

        # Try syslog-like format
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

            return LogEntry(
                timestamp=ts,
                level=LogLevel.INFO,
                module=match.group("module"),
                message=match.group("message"),
                source_file=source_file,
            )

        # Fallback: create entry with raw line
        return LogEntry(
            level=LogLevel.INFO,
            message=line.strip()[:500],
            details={"raw": line.strip()},
            source_file=source_file,
        )

    async def _add_entry(self, entry: LogEntry) -> None:
        """
        Add a log entry to the system.

        Args:
            entry: LogEntry to add
        """
        with self._lock:
            self._log_entries.append(entry)
            self._entry_stream.append(entry)

            # Save to database
            self._db.execute("""
                INSERT INTO log_entries (
                    entry_id, timestamp, level, module, message, details,
                    source_file, line_number, thread_id, process_id,
                    correlation_id, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.entry_id,
                entry.timestamp.isoformat(),
                entry.level.value,
                entry.module,
                entry.message,
                json.dumps(entry.details),
                entry.source_file,
                entry.line_number,
                entry.thread_id,
                entry.process_id,
                entry.correlation_id,
                json.dumps(entry.tags),
            ))

            # Update pattern cache
            self._update_patterns(entry)

            # Check for anomalies
            self._check_anomaly(entry)

            # Limit memory usage
            if len(self._log_entries) > 10000:
                self._log_entries = self._log_entries[-10000:]

    def _update_patterns(self, entry: LogEntry) -> None:
        """Update pattern detection with a new entry."""
        # Extract key parts for pattern matching
        pattern_key = f"{entry.module}:{entry.message[:50]}"

        # Update frequent patterns
        self._frequent_patterns[pattern_key] += 1

        # Check for error patterns
        if entry.level in (LogLevel.ERROR, LogLevel.CRITICAL):
            self._detect_error_pattern(entry)

        # Check for warning patterns
        if entry.level == LogLevel.WARNING:
            self._detect_warning_pattern(entry)

    def _detect_error_pattern(self, entry: LogEntry) -> None:
        """Detect patterns in error logs."""
        pattern_type = LogPatternType.ERROR

        # Extract error type
        error_patterns = [
            (r'TimeoutError', 'timeout_error'),
            (r'ConnectionError', 'connection_error'),
            (r'RateLimitError', 'rate_limit'),
            (r'AuthenticationError', 'auth_error'),
            (r'ValueError', 'value_error'),
            (r'KeyError', 'key_error'),
            (r'AttributeError', 'attribute_error'),
            (r'TypeError', 'type_error'),
        ]

        for pattern, name in error_patterns:
            if re.search(pattern, entry.message, re.IGNORECASE):
                self._add_pattern(
                    pattern_type=pattern_type,
                    pattern=name,
                    description=f"{name} error detected",
                    entry=entry,
                )
                break

    def _detect_warning_pattern(self, entry: LogEntry) -> None:
        """Detect patterns in warning logs."""
        pattern_type = LogPatternType.WARNING

        warning_patterns = [
            (r'Drawdown', 'drawdown_warning'),
            (r'Risk limit', 'risk_limit_warning'),
            (r'performance degradation', 'performance_warning'),
            (r'api latency', 'latency_warning'),
            (r'connection lost', 'connection_warning'),
        ]

        for pattern, name in warning_patterns:
            if re.search(pattern, entry.message, re.IGNORECASE):
                self._add_pattern(
                    pattern_type=pattern_type,
                    pattern=name,
                    description=f"{name} warning detected",
                    entry=entry,
                )
                break

    def _add_pattern(
        self,
        pattern_type: LogPatternType,
        pattern: str,
        description: str,
        entry: LogEntry,
    ) -> None:
        """Add or update a pattern."""
        key = f"{pattern_type.value}:{pattern}"

        if key in self._pattern_cache:
            cached = self._pattern_cache[key]
            cached.occurrences += 1
            cached.last_seen = entry.timestamp
            cached.frequency = cached.occurrences / max(1, (cached.last_seen - cached.first_seen).total_seconds() / 3600)
            cached.related_entries.append(entry.entry_id)
            if len(cached.related_entries) > 100:
                cached.related_entries = cached.related_entries[-100:]
        else:
            new_pattern = LogPattern(
                pattern_type=pattern_type,
                pattern=pattern,
                description=description,
                occurrences=1,
                first_seen=entry.timestamp,
                last_seen=entry.timestamp,
                frequency=1.0,
                confidence=0.5,
                related_entries=[entry.entry_id],
            )
            self._pattern_cache[key] = new_pattern
            self._patterns.append(new_pattern)

    def _check_anomaly(self, entry: LogEntry) -> None:
        """Check if an entry is anomalous."""
        # Check for critical errors
        if entry.level == LogLevel.CRITICAL:
            self._create_anomaly(
                severity=AnomalySeverity.CRITICAL,
                message=f"Critical error: {entry.message[:100]}",
                description="Critical error detected",
                entry=entry,
                score=5.0,
            )
            return

        # Check for error frequency
        if entry.level == LogLevel.ERROR:
            error_count = sum(1 for e in self._log_entries[-100:] if e.level == LogLevel.ERROR)
            if error_count > 10:
                self._create_anomaly(
                    severity=AnomalySeverity.HIGH,
                    message=f"High error rate: {error_count} errors in last 100 entries",
                    description="Unusual error frequency detected",
                    entry=entry,
                    score=3.0,
                )

        # Check for unusual patterns in message
        if self._is_unusual_message(entry):
            self._create_anomaly(
                severity=AnomalySeverity.MEDIUM,
                message=f"Unusual message: {entry.message[:100]}",
                description="Unusual log message pattern detected",
                entry=entry,
                score=2.0,
            )

    def _is_unusual_message(self, entry: LogEntry) -> bool:
        """Check if a message is unusual."""
        # Simple heuristic: check for messages that don't match common patterns
        common_patterns = [
            r'Starting.*cycle',
            r'Completed.*cycle',
            r'Order.*placed',
            r'Order.*filled',
            r'Position.*updated',
            r'Position.*created',
            r'Market snapshot',
            r'Health check',
            r'System health',
        ]

        message = entry.message.lower()

        # Check if message matches any common pattern
        for pattern in common_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return False

        # Check if message contains unusual keywords
        unusual_keywords = [
            'failed',
            'error',
            'exception',
            'timeout',
            'unexpected',
            'invalid',
            'corrupt',
            'crash',
        ]

        for keyword in unusual_keywords:
            if keyword in message:
                return True

        return False

    def _create_anomaly(
        self,
        severity: AnomalySeverity,
        message: str,
        description: str,
        entry: LogEntry,
        score: float = 0.0,
    ) -> None:
        """Create a new anomaly."""
        anomaly = Anomaly(
            severity=severity,
            message=message,
            description=description,
            detected_at=datetime.utcnow(),
            related_entries=[entry.entry_id],
            score=score,
        )

        self._anomalies.append(anomaly)

        # Save to database
        self._db.execute("""
            INSERT INTO anomalies (
                anomaly_id, severity, message, description, detected_at,
                related_entries, score, metadata, acknowledged, resolved
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            anomaly.anomaly_id,
            anomaly.severity.value,
            anomaly.message,
            anomaly.description,
            anomaly.detected_at.isoformat(),
            json.dumps(anomaly.related_entries),
            anomaly.score,
            json.dumps(anomaly.metadata),
            1 if anomaly.acknowledged else 0,
            1 if anomaly.resolved else 0,
        ))

        logger.warning(
            "anomaly_detected",
            anomaly_id=anomaly.anomaly_id,
            severity=severity.value,
            message=message[:100],
        )

    async def _run_analysis(self) -> None:
        """Run periodic log analysis."""
        try:
            # Analyze recent logs for patterns
            recent_entries = self._get_recent_entries(hours=1)
            if recent_entries:
                self._analyze_frequent_patterns(recent_entries)

            # Update baselines
            self._update_baselines()

            # Clean up old data
            self._cleanup_old_data()

        except Exception as e:
            logger.error("analysis_error", error=str(e))

    def _get_recent_entries(self, hours: int = 1) -> List[LogEntry]:
        """Get entries from the last N hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [e for e in self._log_entries if e.timestamp > cutoff]

    def _analyze_frequent_patterns(self, entries: List[LogEntry]) -> None:
        """Analyze frequent patterns in log entries."""
        if len(entries) < 10:
            return

        # Group by module and message type
        pattern_counts = defaultdict(int)
        for entry in entries:
            key = f"{entry.module}:{entry.level.value}"
            pattern_counts[key] += 1

        # Detect frequent patterns
        threshold = len(entries) * 0.1  # 10% of entries
        for key, count in pattern_counts.items():
            if count > threshold:
                module, level = key.split(":")
                if level == "error":
                    pattern_type = LogPatternType.ERROR
                elif level == "warning":
                    pattern_type = LogPatternType.WARNING
                else:
                    pattern_type = LogPatternType.FREQUENT

                self._add_pattern(
                    pattern_type=pattern_type,
                    pattern=f"frequent_{module}_{level}",
                    description=f"Frequent {level} logs from {module}",
                    entry=entries[0],
                )

    def _update_baselines(self) -> None:
        """Update baseline statistics for anomaly detection."""
        # Calculate error rate baseline
        recent = self._get_recent_entries(hours=24)
        if recent:
            error_count = sum(1 for e in recent if e.level in (LogLevel.ERROR, LogLevel.CRITICAL))
            self._baseline_stats["error_rate"] = {
                "count": error_count,
                "total": len(recent),
                "rate": error_count / max(1, len(recent)) * 100,
            }

    def _cleanup_old_data(self) -> None:
        """Clean up old data from database."""
        retention_days = self.config.get("retention_days", 30)
        cutoff = datetime.utcnow() - timedelta(days=retention_days)

        self._db.execute(
            "DELETE FROM log_entries WHERE timestamp < ?",
            (cutoff.isoformat(),)
        )
        self._db.execute(
            "DELETE FROM patterns WHERE last_seen < ?",
            (cutoff.isoformat(),)
        )
        self._db.execute(
            "DELETE FROM anomalies WHERE detected_at < ? AND resolved = 1",
            (cutoff.isoformat(),)
        )

        # Vacuum database periodically
        if self._db.execute("SELECT COUNT(*) FROM log_entries").fetchone()[0] % 1000 == 0:
            self._db.execute("VACUUM")

    def get_entries(
        self,
        level: Optional[Union[str, LogLevel]] = None,
        module: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[LogEntry]:
        """
        Get log entries with filtering.

        Args:
            level: Filter by log level
            module: Filter by module
            start_time: Start time
            end_time: End time
            limit: Maximum number of entries
            offset: Pagination offset

        Returns:
            List of LogEntry objects
        """
        sql = "SELECT * FROM log_entries WHERE 1=1"
        params = []

        if level:
            if isinstance(level, str):
                level = LogLevel(level)
            sql += " AND level = ?"
            params.append(level.value)

        if module:
            sql += " AND module LIKE ?"
            params.append(f"%{module}%")

        if start_time:
            sql += " AND timestamp >= ?"
            params.append(start_time.isoformat())

        if end_time:
            sql += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self._db.execute(sql, params)
        rows = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]
        entries = []

        for row in rows:
            data = dict(zip(columns, row))
            data["details"] = json.loads(data["details"]) if data.get("details") else {}
            data["tags"] = json.loads(data["tags"]) if data.get("tags") else []
            entries.append(LogEntry.from_dict(data))

        return entries

    def get_patterns(
        self,
        pattern_type: Optional[Union[str, LogPatternType]] = None,
        min_occurrences: int = 1,
    ) -> List[LogPattern]:
        """
        Get detected log patterns.

        Args:
            pattern_type: Filter by pattern type
            min_occurrences: Minimum occurrences

        Returns:
            List of LogPattern objects
        """
        if pattern_type:
            if isinstance(pattern_type, str):
                pattern_type = LogPatternType(pattern_type)

        patterns = []
        for pattern in self._patterns:
            if pattern_type and pattern.pattern_type != pattern_type:
                continue
            if pattern.occurrences < min_occurrences:
                continue
            patterns.append(pattern)

        return sorted(patterns, key=lambda p: p.occurrences, reverse=True)

    def get_anomalies(
        self,
        severity: Optional[Union[str, AnomalySeverity]] = None,
        resolved: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Anomaly]:
        """
        Get detected anomalies.

        Args:
            severity: Filter by severity
            resolved: Filter by resolved status
            limit: Maximum number of anomalies
            offset: Pagination offset

        Returns:
            List of Anomaly objects
        """
        sql = "SELECT * FROM anomalies WHERE 1=1"
        params = []

        if severity:
            if isinstance(severity, str):
                severity = AnomalySeverity(severity)
            sql += " AND severity = ?"
            params.append(severity.value)

        if resolved is not None:
            sql += " AND resolved = ?"
            params.append(1 if resolved else 0)

        sql += " ORDER BY detected_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self._db.execute(sql, params)
        rows = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]
        anomalies = []

        for row in rows:
            data = dict(zip(columns, row))
            data["related_entries"] = json.loads(data["related_entries"]) if data.get("related_entries") else []
            data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
            anomalies.append(Anomaly.from_dict(data))

        return anomalies

    def acknowledge_anomaly(self, anomaly_id: str) -> bool:
        """
        Acknowledge an anomaly.

        Args:
            anomaly_id: ID of the anomaly

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            self._db.execute(
                "UPDATE anomalies SET acknowledged = 1 WHERE anomaly_id = ?",
                (anomaly_id,)
            )

            for anomaly in self._anomalies:
                if anomaly.anomaly_id == anomaly_id:
                    anomaly.acknowledged = True
                    return True

            return False

    def resolve_anomaly(self, anomaly_id: str) -> bool:
        """
        Resolve an anomaly.

        Args:
            anomaly_id: ID of the anomaly

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            self._db.execute(
                "UPDATE anomalies SET resolved = 1 WHERE anomaly_id = ?",
                (anomaly_id,)
            )

            for anomaly in self._anomalies:
                if anomaly.anomaly_id == anomaly_id:
                    anomaly.resolved = True
                    return True

            return False

    def get_log_stats(self) -> Dict[str, Any]:
        """
        Get log analysis statistics.

        Returns:
            Dictionary of statistics
        """
        total = self._get_total_entries()
        by_level = self._get_counts_by_level()
        by_module = self._get_counts_by_module()

        return {
            "total_entries": total,
            "entries_by_level": by_level,
            "entries_by_module": by_module,
            "patterns_count": len(self._patterns),
            "anomalies_count": len(self._anomalies),
            "anomalies_active": len([a for a in self._anomalies if not a.resolved]),
            "error_rate": self._baseline_stats.get("error_rate", {}).get("rate", 0),
            "analyzed_since": self._log_entries[0].timestamp.isoformat() if self._log_entries else None,
        }

    def _get_total_entries(self) -> int:
        """Get total number of entries in database."""
        cursor = self._db.execute("SELECT COUNT(*) FROM log_entries")
        return cursor.fetchone()[0]

    def _get_counts_by_level(self) -> Dict[str, int]:
        """Get entry counts by log level."""
        cursor = self._db.execute(
            "SELECT level, COUNT(*) FROM log_entries GROUP BY level"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def _get_counts_by_module(self) -> Dict[str, int]:
        """Get entry counts by module."""
        cursor = self._db.execute(
            "SELECT module, COUNT(*) FROM log_entries GROUP BY module ORDER BY COUNT(*) DESC LIMIT 20"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def stream_entries(self) -> Iterator[LogEntry]:
        """Stream log entries in real-time."""
        while not self._closed:
            if self._entry_stream:
                yield self._entry_stream.popleft()
            else:
                time.sleep(0.1)

    async def stream_entries_async(self) -> AsyncIterator[LogEntry]:
        """Stream log entries asynchronously in real-time."""
        while not self._closed:
            if self._entry_stream:
                yield self._entry_stream.popleft()
            else:
                await asyncio.sleep(0.1)

    def close(self) -> None:
        """Close the log analyzer."""
        if self._closed:
            return

        self._closed = True

        if hasattr(self, "_db") and self._db:
            self._db.close()

        logger.info("log_analyzer_closed")

    def __enter__(self) -> "LogAnalyzer":
        return self

    def __exit__(self, *args) -> None:
        self.close()


# === MODULE EXPORTS ===

__all__ = [
    "LogAnalyzer",
    "LogEntry",
    "LogPattern",
    "LogPatternType",
    "Anomaly",
    "AnomalySeverity",
    "LogLevel",
]

logger.info("log_analyzer_module_loaded", version="3.0.0")
