"""
NEXUS AI TRADING SYSTEM - Log Analyzer
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced log analysis system with real-time monitoring, pattern detection,
anomaly detection, and intelligent alerting for trading system logs.
"""

import asyncio
import gzip
import json
import mmap
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import aiofiles
import yaml
from prometheus_client import Counter, Gauge, Histogram

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
LOG_ENTRY_COUNTER = Counter(
    "nexus_log_entries_total",
    "Total number of log entries processed",
    ["level", "source"],
)
LOG_ERROR_COUNTER = Counter(
    "nexus_log_errors_total",
    "Total number of error logs",
    ["error_type", "source"],
)
LOG_PATTERN_MATCHES = Counter(
    "nexus_log_pattern_matches_total",
    "Total number of pattern matches",
    ["pattern_id", "severity"],
)
LOG_ANALYSIS_DURATION = Histogram(
    "nexus_log_analysis_duration_seconds",
    "Duration of log analysis",
    ["analysis_type"],
)


class LogLevel(Enum):
    """Log severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AnalysisType(Enum):
    """Types of log analysis."""

    PATTERN = "pattern"
    ANOMALY = "anomaly"
    FREQUENCY = "frequency"
    SEQUENCE = "sequence"
    CORRELATION = "correlation"
    TREND = "trend"


@dataclass
class LogEntry:
    """Parsed log entry."""

    timestamp: datetime
    level: LogLevel
    source: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    raw: str = ""
    line_number: int = 0
    file_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "source": self.source,
            "message": self.message,
            "context": self.context,
            "raw": self.raw,
            "line_number": self.line_number,
            "file_path": self.file_path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogEntry":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            level=LogLevel(data["level"]),
            source=data["source"],
            message=data["message"],
            context=data.get("context", {}),
            raw=data.get("raw", ""),
            line_number=data.get("line_number", 0),
            file_path=data.get("file_path"),
        )


@dataclass
class LogPattern:
    """Log pattern definition."""

    id: str
    name: str
    pattern: str
    regex: re.Pattern
    severity: LogLevel
    description: str
    enabled: bool = True
    cooldown_seconds: int = 300
    tags: List[str] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "pattern": self.pattern,
            "severity": self.severity.value,
            "description": self.description,
            "enabled": self.enabled,
            "cooldown_seconds": self.cooldown_seconds,
            "tags": self.tags,
            "actions": self.actions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogPattern":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            pattern=data["pattern"],
            regex=re.compile(data["pattern"], re.IGNORECASE),
            severity=LogLevel(data["severity"]),
            description=data["description"],
            enabled=data.get("enabled", True),
            cooldown_seconds=data.get("cooldown_seconds", 300),
            tags=data.get("tags", []),
            actions=data.get("actions", []),
        )


@dataclass
class AnalysisResult:
    """Result of log analysis."""

    analysis_type: AnalysisType
    pattern_id: Optional[str] = None
    severity: LogLevel = LogLevel.INFO
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    matched_entries: List[LogEntry] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class LogAnalyzer:
    """
    Advanced log analysis system with real-time monitoring and pattern detection.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        alert_manager: Optional[Any] = None,
    ):
        """
        Initialize the log analyzer.

        Args:
            config: Configuration dictionary
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
            alert_manager: Alert manager instance
        """
        self.config = config or {}
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.alert_manager = alert_manager
        self._lock = asyncio.Lock()
        self._patterns: Dict[str, LogPattern] = {}
        self._log_buffer: deque = deque(maxlen=10000)
        self._error_history: Dict[str, List[LogEntry]] = defaultdict(list)
        self._pattern_matches: Dict[str, List[datetime]] = defaultdict(list)
        self._analysis_handlers: Dict[AnalysisType, List[Callable]] = defaultdict(list)
        self._monitor_task: Optional[asyncio.Task] = None
        self._analysis_task: Optional[asyncio.Task] = None

        # Load configuration
        self.log_config = self.config.get("log_analyzer", {})
        self.log_dirs = self.log_config.get("log_dirs", ["./logs"])
        self.patterns_file = Path(self.log_config.get("patterns_file", "./configs/log_patterns.yaml"))
        self.buffer_size = self.log_config.get("buffer_size", 10000)
        self.analysis_interval = self.log_config.get("analysis_interval", 60)
        self.max_error_age_days = self.log_config.get("max_error_age_days", 7)

        # Load patterns
        self._load_patterns()

        # Start background tasks
        self._start_background_tasks()

        logger.info(f"LogAnalyzer initialized with {len(self._patterns)} patterns")

    def _load_patterns(self):
        """Load log patterns from configuration."""
        try:
            if self.patterns_file.exists():
                with open(self.patterns_file, "r") as f:
                    data = yaml.safe_load(f)
                    for pattern_data in data.get("patterns", []):
                        pattern = LogPattern.from_dict(pattern_data)
                        self._patterns[pattern.id] = pattern
                logger.info(f"Loaded {len(self._patterns)} patterns from {self.patterns_file}")
            else:
                # Load default patterns
                self._load_default_patterns()
        except Exception as e:
            logger.error(f"Error loading patterns: {e}")
            self._load_default_patterns()

    def _load_default_patterns(self):
        """Load default log patterns."""
        default_patterns = [
            LogPattern(
                id="error_exception",
                name="Exception Detected",
                pattern=r"(?i)(exception|error|failed|crash|timeout|connection refused)",
                severity=LogLevel.ERROR,
                description="Detects exceptions and errors in logs",
                actions=[{"type": "alert", "severity": "error"}],
            ),
            LogPattern(
                id="trade_failure",
                name="Trade Failure",
                pattern=r"(?i)trade (failed|rejected|invalid|cancelled|order failed)",
                severity=LogLevel.ERROR,
                description="Detects trade execution failures",
                actions=[{"type": "alert", "severity": "critical"}],
            ),
            LogPattern(
                id="api_error",
                name="API Error",
                pattern=r"(?i)api (error|failed|timeout|rate limit|429|503)",
                severity=LogLevel.WARNING,
                description="Detects API errors and failures",
                actions=[{"type": "alert", "severity": "warning"}],
            ),
            LogPattern(
                id="model_failure",
                name="Model Failure",
                pattern=r"(?i)model (failed|error|crash|inference failed|prediction failed)",
                severity=LogLevel.ERROR,
                description="Detects model inference failures",
                actions=[{"type": "alert", "severity": "error"}],
            ),
            LogPattern(
                id="security_breach",
                name="Security Breach",
                pattern=r"(?i)(unauthorized|forbidden|hack|breach|intrusion|attack|suspicious)",
                severity=LogLevel.CRITICAL,
                description="Detects potential security breaches",
                actions=[{"type": "alert", "severity": "critical"}],
            ),
            LogPattern(
                id="performance_degradation",
                name="Performance Degradation",
                pattern=r"(?i)(slow|latency|timeout|high (cpu|memory|load)|performance degraded)",
                severity=LogLevel.WARNING,
                description="Detects performance degradation",
                actions=[{"type": "alert", "severity": "warning"}],
            ),
            LogPattern(
                id="broker_connection",
                name="Broker Connection Issue",
                pattern=r"(?i)(broker connection|websocket (disconnected|reconnect)|stream (stopped|error))",
                severity=LogLevel.ERROR,
                description="Detects broker connection issues",
                actions=[{"type": "alert", "severity": "error"}],
            ),
            LogPattern(
                id="data_integrity",
                name="Data Integrity Issue",
                pattern=r"(?i)(data (corrupt|missing|inconsistent|integrity)|validation failed)",
                severity=LogLevel.ERROR,
                description="Detects data integrity issues",
                actions=[{"type": "alert", "severity": "error"}],
            ),
        ]

        for pattern in default_patterns:
            self._patterns[pattern.id] = pattern

        logger.info(f"Loaded {len(self._patterns)} default patterns")

    def _start_background_tasks(self):
        """Start background tasks."""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._monitor_loop())

        if self._analysis_task is None:
            self._analysis_task = asyncio.create_task(self._analysis_loop())

    async def _monitor_loop(self):
        """Background loop for log monitoring."""
        while True:
            try:
                await self._tail_log_files()
                await asyncio.sleep(5)  # Check every 5 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(10)

    async def _analysis_loop(self):
        """Background loop for log analysis."""
        while True:
            try:
                await self.run_analysis()
                await asyncio.sleep(self.analysis_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in analysis loop: {e}")
                await asyncio.sleep(30)

    async def _tail_log_files(self):
        """Tail log files for new entries."""
        for log_dir in self.log_dirs:
            dir_path = Path(log_dir)
            if not dir_path.exists():
                continue

            # Get all log files
            log_files = list(dir_path.glob("*.log")) + list(dir_path.glob("*.log.*"))

            for log_file in log_files:
                await self._process_log_file(log_file)

    async def _process_log_file(self, log_file: Path):
        """Process a log file for new entries."""
        try:
            # Check if file has been modified
            last_position = await self.cache_manager.get(f"log_pos_{log_file}")
            last_position = int(last_position) if last_position else 0

            # Get current file size
            current_size = log_file.stat().st_size

            if current_size == last_position:
                return

            # Read new lines
            async with aiofiles.open(log_file, "r") as f:
                await f.seek(last_position)
                lines = await f.readlines()

            # Update position
            await self.cache_manager.set(f"log_pos_{log_file}", str(current_size), 86400)

            # Process lines
            for line_num, line in enumerate(lines, start=1):
                # Handle compressed files (if needed)
                if log_file.suffix == ".gz":
                    line = gzip.decompress(line.encode()).decode()

                # Parse log entry
                entry = await self._parse_log_entry(line, log_file, line_num)

                if entry:
                    await self._process_log_entry(entry)

        except Exception as e:
            logger.error(f"Error processing log file {log_file}: {e}")

    async def _parse_log_entry(
        self,
        line: str,
        file_path: Path,
        line_number: int,
    ) -> Optional[LogEntry]:
        """
        Parse a log line into a LogEntry.

        Args:
            line: Log line
            file_path: File path
            line_number: Line number

        Returns:
            Parsed LogEntry or None
        """
        try:
            # Try JSON format first
            if line.strip().startswith("{"):
                try:
                    data = json.loads(line)
                    return LogEntry(
                        timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat())),
                        level=LogLevel(data.get("level", "info").lower()),
                        source=data.get("source", "unknown"),
                        message=data.get("message", ""),
                        context=data.get("context", {}),
                        raw=line.strip(),
                        line_number=line_number,
                        file_path=str(file_path),
                    )
                except json.JSONDecodeError:
                    pass

            # Try standard log format
            # [2024-01-01 12:00:00] [INFO] [source] message
            pattern = r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?)\] \[(\w+)\] \[(\w+)\] (.*)"
            match = re.match(pattern, line)

            if match:
                timestamp_str, level_str, source, message = match.groups()
                return LogEntry(
                    timestamp=datetime.fromisoformat(timestamp_str),
                    level=LogLevel(level_str.lower()),
                    source=source,
                    message=message.strip(),
                    raw=line.strip(),
                    line_number=line_number,
                    file_path=str(file_path),
                )

            # Fallback: extract timestamp and level
            # 2024-01-01 12:00:00 INFO: message
            pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?) (\w+): (.*)"
            match = re.match(pattern, line)

            if match:
                timestamp_str, level_str, message = match.groups()
                return LogEntry(
                    timestamp=datetime.fromisoformat(timestamp_str),
                    level=LogLevel(level_str.lower()),
                    source="unknown",
                    message=message.strip(),
                    raw=line.strip(),
                    line_number=line_number,
                    file_path=str(file_path),
                )

            # Basic fallback
            return LogEntry(
                timestamp=datetime.utcnow(),
                level=LogLevel.INFO,
                source="unknown",
                message=line.strip(),
                raw=line.strip(),
                line_number=line_number,
                file_path=str(file_path),
            )

        except Exception as e:
            logger.debug(f"Error parsing log entry: {e}")
            return None

    async def _process_log_entry(self, entry: LogEntry):
        """Process a log entry."""
        # Add to buffer
        async with self._lock:
            self._log_buffer.append(entry)

        # Update metrics
        LOG_ENTRY_COUNTER.labels(
            level=entry.level.value,
            source=entry.source,
        ).inc()

        # Store errors
        if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
            self._error_history[entry.source].append(entry)
            LOG_ERROR_COUNTER.labels(
                error_type=entry.source,
                source=entry.source,
            ).inc()

            # Clean old errors
            cutoff = datetime.utcnow() - timedelta(days=self.max_error_age_days)
            self._error_history[entry.source] = [
                e for e in self._error_history[entry.source]
                if e.timestamp > cutoff
            ]

        # Check patterns
        await self._check_patterns(entry)

    async def _check_patterns(self, entry: LogEntry):
        """Check log entry against patterns."""
        for pattern in self._patterns.values():
            if not pattern.enabled:
                continue

            # Check cooldown
            matches = self._pattern_matches.get(pattern.id, [])
            if matches:
                last_match = max(matches)
                if (datetime.utcnow() - last_match).total_seconds() < pattern.cooldown_seconds:
                    continue

            # Check pattern
            if pattern.regex.search(entry.message):
                matches.append(datetime.utcnow())
                self._pattern_matches[pattern.id] = matches[-100:]  # Keep last 100

                # Record match
                LOG_PATTERN_MATCHES.labels(
                    pattern_id=pattern.id,
                    severity=pattern.severity.value,
                ).inc()

                # Execute actions
                await self._execute_pattern_actions(pattern, entry)

                # Update metrics
                if entry.level.value in ["error", "critical"]:
                    LOG_ERROR_COUNTER.labels(
                        error_type=pattern.id,
                        source=entry.source,
                    ).inc()

                logger.info(f"Pattern match: {pattern.name} in {entry.source}")

    async def _execute_pattern_actions(self, pattern: LogPattern, entry: LogEntry):
        """
        Execute actions for a pattern match.

        Args:
            pattern: Matched pattern
            entry: Log entry
        """
        for action in pattern.actions:
            action_type = action.get("type")

            if action_type == "alert" and self.alert_manager:
                severity = action.get("severity", pattern.severity.value)
                await self.alert_manager.evaluate_rules({
                    "log_pattern": pattern.id,
                    "log_severity": severity,
                    "log_source": entry.source,
                    "log_message": entry.message,
                }, source="log_analyzer")

            elif action_type == "email":
                # TODO: Implement email action
                pass

            elif action_type == "slack":
                # TODO: Implement Slack action
                pass

            elif action_type == "webhook":
                # TODO: Implement webhook action
                pass

    async def analyze_logs(
        self,
        analysis_type: Union[AnalysisType, str],
        **kwargs,
    ) -> List[AnalysisResult]:
        """
        Analyze logs with specified analysis type.

        Args:
            analysis_type: Type of analysis
            **kwargs: Analysis parameters

        Returns:
            List of analysis results
        """
        if isinstance(analysis_type, str):
            analysis_type = AnalysisType(analysis_type)

        start_time = time.time()
        results = []

        async with self._lock:
            entries = list(self._log_buffer)

        if analysis_type == AnalysisType.PATTERN:
            results = await self._analyze_patterns(entries, **kwargs)
        elif analysis_type == AnalysisType.ANOMALY:
            results = await self._analyze_anomalies(entries, **kwargs)
        elif analysis_type == AnalysisType.FREQUENCY:
            results = await self._analyze_frequency(entries, **kwargs)
        elif analysis_type == AnalysisType.SEQUENCE:
            results = await self._analyze_sequence(entries, **kwargs)
        elif analysis_type == AnalysisType.CORRELATION:
            results = await self._analyze_correlation(entries, **kwargs)
        elif analysis_type == AnalysisType.TREND:
            results = await self._analyze_trend(entries, **kwargs)

        LOG_ANALYSIS_DURATION.labels(
            analysis_type=analysis_type.value
        ).observe(time.time() - start_time)

        # Call handlers
        for handler in self._analysis_handlers[analysis_type]:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(results)
                else:
                    handler(results)
            except Exception as e:
                logger.error(f"Error in analysis handler: {e}")

        return results

    async def _analyze_patterns(
        self,
        entries: List[LogEntry],
        **kwargs,
    ) -> List[AnalysisResult]:
        """Analyze patterns in logs."""
        results = []
        pattern = kwargs.get("pattern")
        severity = kwargs.get("severity")

        for entry in entries:
            if pattern and not re.search(pattern, entry.message, re.IGNORECASE):
                continue

            if severity:
                if isinstance(severity, str):
                    severity = LogLevel(severity)
                if entry.level != severity:
                    continue

            # Check against registered patterns
            for p in self._patterns.values():
                if p.regex.search(entry.message):
                    results.append(AnalysisResult(
                        analysis_type=AnalysisType.PATTERN,
                        pattern_id=p.id,
                        severity=entry.level,
                        message=f"Pattern match: {p.name}",
                        details={"pattern": p.pattern, "match": entry.message},
                        matched_entries=[entry],
                    ))

        return results

    async def _analyze_anomalies(
        self,
        entries: List[LogEntry],
        **kwargs,
    ) -> List[AnalysisResult]:
        """Detect anomalies in logs."""
        results = []
        threshold = kwargs.get("threshold", 3.0)

        # Group by source and count
        counts = defaultdict(int)
        for entry in entries:
            counts[entry.source] += 1

        # Calculate mean and std
        if counts:
            values = list(counts.values())
            mean = sum(values) / len(values)
            std = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5

            # Detect anomalies
            for source, count in counts.items():
                if count > mean + threshold * std:
                    results.append(AnalysisResult(
                        analysis_type=AnalysisType.ANOMALY,
                        severity=LogLevel.WARNING,
                        message=f"Anomaly detected: {source} has {count} entries",
                        details={
                            "source": source,
                            "count": count,
                            "mean": mean,
                            "std": std,
                            "threshold": threshold,
                        },
                        matched_entries=[e for e in entries if e.source == source],
                    ))

        return results

    async def _analyze_frequency(
        self,
        entries: List[LogEntry],
        **kwargs,
    ) -> List[AnalysisResult]:
        """Analyze log frequency."""
        results = []
        window_seconds = kwargs.get("window_seconds", 60)

        # Group by time window
        windows = defaultdict(int)
        for entry in entries:
            window_key = int(entry.timestamp.timestamp() / window_seconds)
            windows[window_key] += 1

        # Detect frequency changes
        if windows:
            window_counts = list(windows.values())
            mean = sum(window_counts) / len(window_counts)
            std = (sum((v - mean) ** 2 for v in window_counts) / len(window_counts)) ** 0.5

            for window_key, count in windows.items():
                if count > mean + 2 * std:
                    window_time = datetime.fromtimestamp(window_key * window_seconds)
                    results.append(AnalysisResult(
                        analysis_type=AnalysisType.FREQUENCY,
                        severity=LogLevel.WARNING,
                        message=f"Frequency spike detected: {count} entries in window",
                        details={
                            "window_start": window_time.isoformat(),
                            "count": count,
                            "mean": mean,
                            "std": std,
                        },
                    ))

        return results

    async def _analyze_sequence(
        self,
        entries: List[LogEntry],
        **kwargs,
    ) -> List[AnalysisResult]:
        """Analyze log sequences."""
        results = []
        sequence = kwargs.get("sequence", [])
        window_seconds = kwargs.get("window_seconds", 300)

        if not sequence:
            return results

        # Look for sequences
        for i, entry in enumerate(entries):
            if i + len(sequence) >= len(entries):
                break

            # Check if sequence matches
            match = True
            for j, pattern in enumerate(sequence):
                if not re.search(pattern, entries[i + j].message, re.IGNORECASE):
                    match = False
                    break

            if match:
                # Check time window
                if (entries[i + len(sequence) - 1].timestamp - entries[i].timestamp).total_seconds() <= window_seconds:
                    results.append(AnalysisResult(
                        analysis_type=AnalysisType.SEQUENCE,
                        severity=LogLevel.WARNING,
                        message="Sequence detected",
                        details={"sequence": sequence},
                        matched_entries=entries[i:i + len(sequence)],
                    ))

        return results

    async def _analyze_correlation(
        self,
        entries: List[LogEntry],
        **kwargs,
    ) -> List[AnalysisResult]:
        """Analyze correlations in logs."""
        results = []
        min_correlation = kwargs.get("min_correlation", 0.7)
        window_seconds = kwargs.get("window_seconds", 300)

        # Group by source
        sources = {}
        for entry in entries:
            if entry.source not in sources:
                sources[entry.source] = []
            sources[entry.source].append(entry)

        # Check correlations between sources
        source_names = list(sources.keys())
        for i in range(len(source_names)):
            for j in range(i + 1, len(source_names)):
                source1 = source_names[i]
                source2 = source_names[j]

                # Check if sources appear together
                entries1 = sources[source1]
                entries2 = sources[source2]

                # Count co-occurrences
                co_occurrences = 0
                for e1 in entries1:
                    for e2 in entries2:
                        if abs((e1.timestamp - e2.timestamp).total_seconds()) <= window_seconds:
                            co_occurrences += 1
                            break

                correlation = co_occurrences / min(len(entries1), len(entries2))

                if correlation >= min_correlation:
                    results.append(AnalysisResult(
                        analysis_type=AnalysisType.CORRELATION,
                        severity=LogLevel.INFO,
                        message=f"Correlation detected between {source1} and {source2}",
                        details={
                            "source1": source1,
                            "source2": source2,
                            "correlation": correlation,
                            "co_occurrences": co_occurrences,
                        },
                    ))

        return results

    async def _analyze_trend(
        self,
        entries: List[LogEntry],
        **kwargs,
    ) -> List[AnalysisResult]:
        """Analyze log trends."""
        results = []
        window_seconds = kwargs.get("window_seconds", 3600)

        # Group by source and time
        trends = defaultdict(list)
        for entry in entries:
            window_key = int(entry.timestamp.timestamp() / window_seconds)
            trends[entry.source].append(window_key)

        # Check for increasing trends
        for source, windows in trends.items():
            if len(windows) < 3:
                continue

            # Count unique windows
            unique_windows = sorted(set(windows))

            if len(unique_windows) < 3:
                continue

            # Check if count is increasing
            counts = []
            for window in unique_windows:
                count = windows.count(window)
                counts.append(count)

            # Simple trend detection
            increasing = all(counts[i] <= counts[i + 1] for i in range(len(counts) - 1))

            if increasing and counts[-1] > counts[0] * 2:
                results.append(AnalysisResult(
                    analysis_type=AnalysisType.TREND,
                    severity=LogLevel.WARNING,
                    message=f"Increasing trend detected for {source}",
                    details={
                        "source": source,
                        "counts": counts,
                        "windows": unique_windows,
                    },
                ))

        return results

    async def run_analysis(self) -> List[AnalysisResult]:
        """
        Run all analyses.

        Returns:
            List of analysis results
        """
        results = []

        # Run pattern analysis
        pattern_results = await self.analyze_logs(AnalysisType.PATTERN)
        results.extend(pattern_results)

        # Run anomaly detection
        anomaly_results = await self.analyze_logs(AnalysisType.ANOMALY)
        results.extend(anomaly_results)

        # Run frequency analysis
        frequency_results = await self.analyze_logs(AnalysisType.FREQUENCY)
        results.extend(frequency_results)

        # Run trend analysis
        trend_results = await self.analyze_logs(AnalysisType.TREND)
        results.extend(trend_results)

        return results

    async def get_errors(
        self,
        source: Optional[str] = None,
        level: Optional[Union[LogLevel, str]] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[LogEntry]:
        """
        Get error logs.

        Args:
            source: Filter by source
            level: Filter by level
            since: Filter since date
            limit: Maximum results

        Returns:
            List of error logs
        """
        if level and isinstance(level, str):
            level = LogLevel(level)

        errors = []
        for s, entries in self._error_history.items():
            if source and s != source:
                continue

            for entry in entries:
                if level and entry.level != level:
                    continue
                if since and entry.timestamp < since:
                    continue
                errors.append(entry)

        errors.sort(key=lambda x: x.timestamp, reverse=True)
        return errors[:limit]

    async def get_pattern_matches(
        self,
        pattern_id: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> Dict[str, List[datetime]]:
        """
        Get pattern match history.

        Args:
            pattern_id: Filter by pattern ID
            since: Filter since date

        Returns:
            Pattern match history
        """
        matches = {}

        for pid, timestamps in self._pattern_matches.items():
            if pattern_id and pid != pattern_id:
                continue

            if since:
                timestamps = [t for t in timestamps if t >= since]

            if timestamps:
                matches[pid] = timestamps

        return matches

    async def add_pattern(self, pattern: LogPattern) -> bool:
        """
        Add a new log pattern.

        Args:
            pattern: Pattern to add

        Returns:
            True if added
        """
        async with self._lock:
            if pattern.id in self._patterns:
                return False

            self._patterns[pattern.id] = pattern
            await self._save_patterns()
            logger.info(f"Added pattern: {pattern.id} - {pattern.name}")
            return True

    async def update_pattern(
        self,
        pattern_id: str,
        updates: Dict[str, Any],
    ) -> bool:
        """
        Update an existing pattern.

        Args:
            pattern_id: Pattern to update
            updates: Updates to apply

        Returns:
            True if updated
        """
        async with self._lock:
            if pattern_id not in self._patterns:
                return False

            pattern = self._patterns[pattern_id]

            for key, value in updates.items():
                if key == "severity":
                    value = LogLevel(value)
                elif key == "enabled":
                    value = bool(value)
                setattr(pattern, key, value)

            # Update regex if pattern changed
            if "pattern" in updates:
                pattern.regex = re.compile(pattern.pattern, re.IGNORECASE)

            await self._save_patterns()
            logger.info(f"Updated pattern: {pattern_id}")
            return True

    async def delete_pattern(self, pattern_id: str) -> bool:
        """
        Delete a pattern.

        Args:
            pattern_id: Pattern to delete

        Returns:
            True if deleted
        """
        async with self._lock:
            if pattern_id not in self._patterns:
                return False

            del self._patterns[pattern_id]
            await self._save_patterns()
            logger.info(f"Deleted pattern: {pattern_id}")
            return True

    async def _save_patterns(self):
        """Save patterns to file."""
        try:
            data = {
                "patterns": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "pattern": p.pattern,
                        "severity": p.severity.value,
                        "description": p.description,
                        "enabled": p.enabled,
                        "cooldown_seconds": p.cooldown_seconds,
                        "tags": p.tags,
                        "actions": p.actions,
                    }
                    for p in self._patterns.values()
                ]
            }

            with open(self.patterns_file, "w") as f:
                yaml.dump(data, f, default_flow_style=False)

        except Exception as e:
            logger.error(f"Error saving patterns: {e}")

    def register_analysis_handler(
        self,
        analysis_type: Union[AnalysisType, str],
        handler: Callable,
    ):
        """
        Register an analysis handler.

        Args:
            analysis_type: Type of analysis
            handler: Callback function
        """
        if isinstance(analysis_type, str):
            analysis_type = AnalysisType(analysis_type)

        self._analysis_handlers[analysis_type].append(handler)
        logger.info(f"Registered analysis handler for {analysis_type.value}")

    async def shutdown(self):
        """Shutdown the log analyzer."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        if self._analysis_task:
            self._analysis_task.cancel()
            try:
                await self._analysis_task
            except asyncio.CancelledError:
                pass

        logger.info("LogAnalyzer shut down")


# Export singleton
log_analyzer = LogAnalyzer()
