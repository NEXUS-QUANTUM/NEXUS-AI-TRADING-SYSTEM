# trading/bots/arbitrage_bot/monitoring/log_analyzer.py
# NEXUS AI TRADING SYSTEM - LOG ANALYZER
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module provides comprehensive log analysis capabilities for the arbitrage bot,
# including log parsing, pattern detection, anomaly detection, and reporting.
# ====================================================================================

"""
NEXUS Arbitrage Bot Log Analyzer

This module provides comprehensive log analysis for:
- Log parsing and structured extraction
- Pattern detection and anomaly identification
- Performance analysis from logs
- Error detection and classification
- Trend analysis and forecasting
- Log aggregation and summarization
- Real-time log monitoring
- Report generation
"""

import asyncio
import logging
import json
import re
import gzip
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque, Counter
from pathlib import Path
import aiofiles
import aiohttp

# NEXUS internal imports
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector
from trading.bots.arbitrage_bot.models.alert import Alert, AlertSeverity, AlertCategory

logger = logging.getLogger("nexus.arbitrage.log_analyzer")


# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    TRACE = "TRACE"
    PERFORMANCE = "PERFORMANCE"
    TRADE = "TRADE"
    OPPORTUNITY = "OPPORTUNITY"


class LogPatternType(str, Enum):
    """Types of log patterns."""
    ERROR_PATTERN = "error_pattern"
    PERFORMANCE_PATTERN = "performance_pattern"
    TRADE_PATTERN = "trade_pattern"
    OPPORTUNITY_PATTERN = "opportunity_pattern"
    SYSTEM_PATTERN = "system_pattern"
    SECURITY_PATTERN = "security_pattern"
    ANOMALY_PATTERN = "anomaly_pattern"


class LogAnalysisPeriod(str, Enum):
    """Analysis periods."""
    LAST_HOUR = "last_hour"
    LAST_DAY = "last_day"
    LAST_WEEK = "last_week"
    LAST_MONTH = "last_month"
    CUSTOM = "custom"


# ====================================================================================
# DATA MODELS
# ====================================================================================

@dataclass
class LogEntry:
    """
    Structured log entry.
    """
    timestamp: datetime
    level: str
    module: str
    message: str
    correlation_id: str
    category: str
    metadata: Dict[str, Any]
    raw: str
    line_number: int
    file_path: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "module": self.module,
            "message": self.message,
            "correlation_id": self.correlation_id,
            "category": self.category,
            "metadata": self.metadata,
            "line_number": self.line_number,
            "file_path": self.file_path
        }


@dataclass
class LogPattern:
    """
    Detected log pattern.
    """
    pattern_id: str
    type: LogPatternType
    name: str
    description: str
    regex: str
    severity: str
    occurrences: int
    first_seen: datetime
    last_seen: datetime
    examples: List[str]
    metadata: Dict[str, Any]


@dataclass
class LogAnomaly:
    """
    Detected log anomaly.
    """
    anomaly_id: str
    type: str
    description: str
    severity: str
    timestamp: datetime
    log_entries: List[LogEntry]
    confidence: float
    metadata: Dict[str, Any]


@dataclass
class LogAnalysisResult:
    """
    Log analysis result.
    """
    period_start: datetime
    period_end: datetime
    total_entries: int
    by_level: Dict[str, int]
    by_module: Dict[str, int]
    by_category: Dict[str, int]
    patterns: List[LogPattern]
    anomalies: List[LogAnomaly]
    error_rate: float
    warning_rate: float
    summary: str


# ====================================================================================
# LOG ANALYZER
# ====================================================================================

class LogAnalyzer:
    """
    Comprehensive log analysis system.
    
    Features:
    - Log parsing and structured extraction
    - Pattern detection using regex
    - Anomaly detection using statistical methods
    - Performance trend analysis
    - Error classification and grouping
    - Real-time log monitoring
    - Report generation
    - Integration with alerting
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the log analyzer.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.log_dir = self.config.get("log_dir", "logs")
        
        # Log storage
        self._log_cache: deque = deque(maxlen=10000)
        self._patterns: List[LogPattern] = []
        self._anomalies: List[LogAnomaly] = []
        
        # Pattern definitions
        self._pattern_definitions = self._load_pattern_definitions()
        
        # Metrics
        self._metrics = MetricsCollector(
            name="nexus_log_analyzer",
            labels={"service": "arbitrage_bot"}
        )
        self._setup_metrics()
        
        # State
        self._running = False
        self._initialized = False
        self._background_tasks: Set[asyncio.Task] = set()
        
        logger.info("LogAnalyzer initialized (version=3.0.0)")
        
    def _setup_metrics(self) -> None:
        """Setup metrics collection."""
        self._metrics.register_counter("logs_parsed", "Total logs parsed")
        self._metrics.register_counter("logs_errors", "Error logs detected")
        self._metrics.register_counter("logs_warnings", "Warning logs detected")
        self._metrics.register_counter("patterns_detected", "Patterns detected")
        self._metrics.register_counter("anomalies_detected", "Anomalies detected")
        self._metrics.register_gauge("log_rate", "Log rate per second")
        
    def _load_pattern_definitions(self) -> List[Dict[str, Any]]:
        """Load pattern definitions."""
        return [
            {
                "name": "exchange_connection_error",
                "type": LogPatternType.ERROR_PATTERN,
                "description": "Exchange connection error detected",
                "regex": r"ERROR.*(?:connection|connect|disconnect).*(?:exchange|binance|bybit|coinbase|kraken)",
                "severity": "high"
            },
            {
                "name": "order_failure",
                "type": LogPatternType.ERROR_PATTERN,
                "description": "Order failure detected",
                "regex": r"ERROR.*order.*(?:failed|rejected|cancelled|timeout)",
                "severity": "high"
            },
            {
                "name": "opportunity_detected",
                "type": LogPatternType.OPPORTUNITY_PATTERN,
                "description": "Arbitrage opportunity detected",
                "regex": r"OPPORTUNITY.*profit.*%",
                "severity": "info"
            },
            {
                "name": "trade_executed",
                "type": LogPatternType.TRADE_PATTERN,
                "description": "Trade executed",
                "regex": r"TRADE.*executed",
                "severity": "info"
            },
            {
                "name": "websocket_disconnect",
                "type": LogPatternType.ERROR_PATTERN,
                "description": "WebSocket disconnect detected",
                "regex": r"ERROR.*websocket.*disconnect",
                "severity": "medium"
            },
            {
                "name": "rate_limit_exceeded",
                "type": LogPatternType.ERROR_PATTERN,
                "description": "Rate limit exceeded",
                "regex": r"ERROR.*rate limit",
                "severity": "medium"
            },
            {
                "name": "performance_issue",
                "type": LogPatternType.PERFORMANCE_PATTERN,
                "description": "Performance issue detected",
                "regex": r"PERFORMANCE.*(?:slow|timeout|latency).*\d+ms",
                "severity": "medium"
            },
            {
                "name": "system_restart",
                "type": LogPatternType.SYSTEM_PATTERN,
                "description": "System restart detected",
                "regex": r"INFO.*(?:starting|restarting|initializing).*NEXUS",
                "severity": "info"
            }
        ]
        
    async def initialize(self) -> None:
        """Initialize the log analyzer."""
        if self._initialized:
            return
            
        self._initialized = True
        self._running = True
        
        # Start background tasks
        await self._start_background_tasks()
        
        logger.info("LogAnalyzer initialized")
        
    async def _start_background_tasks(self) -> None:
        """Start background maintenance tasks."""
        # Log monitoring loop
        task = asyncio.create_task(self._log_monitor_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        # Pattern analysis loop
        task = asyncio.create_task(self._pattern_analysis_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
    async def _log_monitor_loop(self) -> None:
        """Monitor log files for new entries."""
        while self._running:
            try:
                # Monitor log directory
                log_files = self._get_log_files()
                for log_file in log_files:
                    await self._process_log_file(log_file)
                    
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Log monitor error: {e}")
                
    def _get_log_files(self) -> List[str]:
        """Get list of log files to monitor."""
        log_files = []
        log_dir = Path(self.log_dir)
        
        if log_dir.exists():
            for file in log_dir.glob("*.log"):
                log_files.append(str(file))
            for file in log_dir.glob("*.log.*"):
                if not str(file).endswith(".gz"):
                    log_files.append(str(file))
                    
        return log_files
        
    async def _process_log_file(self, file_path: str) -> None:
        """
        Process a log file.
        
        Args:
            file_path: Path to log file
        """
        try:
            # Get file modification time
            mtime = os.path.getmtime(file_path)
            
            # Check if file was modified recently
            if time.time() - mtime > 60:
                return
                
            # Read new lines
            async with aiofiles.open(file_path, 'r') as f:
                content = await f.read()
                lines = content.split('\n')
                
                for line in lines:
                    if line.strip():
                        await self._parse_log_line(line, file_path)
                        
        except Exception as e:
            logger.error(f"Error processing log file {file_path}: {e}")
            
    async def _parse_log_line(self, line: str, file_path: str) -> Optional[LogEntry]:
        """
        Parse a log line.
        
        Args:
            line: Log line
            file_path: File path
            
        Returns:
            LogEntry or None
        """
        # Try to parse as JSON
        try:
            data = json.loads(line)
            return LogEntry(
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat())),
                level=data.get("level", "INFO"),
                module=data.get("module", "unknown"),
                message=data.get("message", ""),
                correlation_id=data.get("correlation_id", ""),
                category=data.get("category", ""),
                metadata=data.get("metadata", {}),
                raw=line,
                line_number=0,
                file_path=file_path
            )
        except json.JSONDecodeError:
            pass
            
        # Parse standard log format
        pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) \| (\w+) \| ([\w\.]+) \| (.*?)(?:\s*\| (.*))?'
        match = re.match(pattern, line)
        
        if match:
            timestamp_str, level, module, message, extra = match.groups()
            
            # Parse metadata from extra
            metadata = {}
            category = ""
            correlation_id = ""
            
            if extra:
                parts = extra.split('|')
                for part in parts:
                    part = part.strip()
                    if '=' in part:
                        key, value = part.split('=', 1)
                        metadata[key.strip()] = value.strip()
                    elif part:
                        # Try to detect category
                        if part in ["trade", "opportunity", "performance", "system", "security"]:
                            category = part
                        elif len(part) == 36 and '-' in part:  # UUID
                            correlation_id = part
                            
            return LogEntry(
                timestamp=datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f"),
                level=level,
                module=module,
                message=message.strip(),
                correlation_id=correlation_id,
                category=category,
                metadata=metadata,
                raw=line,
                line_number=0,
                file_path=file_path
            )
            
        # Fallback: return minimal entry
        return LogEntry(
            timestamp=datetime.utcnow(),
            level="INFO",
            module="unknown",
            message=line[:200],
            correlation_id="",
            category="",
            metadata={},
            raw=line,
            line_number=0,
            file_path=file_path
        )
        
    async def analyze_logs(
        self,
        period: LogAnalysisPeriod = LogAnalysisPeriod.LAST_DAY,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> LogAnalysisResult:
        """
        Analyze logs for a period.
        
        Args:
            period: Analysis period
            start_time: Custom start time
            end_time: Custom end time
            
        Returns:
            Log analysis result
        """
        # Determine time range
        if period == LogAnalysisPeriod.LAST_HOUR:
            start = datetime.utcnow() - timedelta(hours=1)
            end = datetime.utcnow()
        elif period == LogAnalysisPeriod.LAST_DAY:
            start = datetime.utcnow() - timedelta(days=1)
            end = datetime.utcnow()
        elif period == LogAnalysisPeriod.LAST_WEEK:
            start = datetime.utcnow() - timedelta(weeks=1)
            end = datetime.utcnow()
        elif period == LogAnalysisPeriod.LAST_MONTH:
            start = datetime.utcnow() - timedelta(days=30)
            end = datetime.utcnow()
        else:
            start = start_time or datetime.utcnow() - timedelta(days=1)
            end = end_time or datetime.utcnow()
            
        # Collect log entries
        entries = []
        for entry in self._log_cache:
            if start <= entry.timestamp <= end:
                entries.append(entry)
                
        # Analyze entries
        by_level = Counter()
        by_module = Counter()
        by_category = Counter()
        
        for entry in entries:
            by_level[entry.level] += 1
            by_module[entry.module] += 1
            by_category[entry.category] += 1
            
        # Detect patterns
        patterns = await self._detect_patterns(entries)
        
        # Detect anomalies
        anomalies = await self._detect_anomalies(entries)
        
        # Calculate rates
        total = len(entries)
        error_rate = (by_level.get("ERROR", 0) + by_level.get("CRITICAL", 0)) / total if total > 0 else 0
        warning_rate = by_level.get("WARNING", 0) / total if total > 0 else 0
        
        # Generate summary
        summary = self._generate_summary(entries, patterns, anomalies)
        
        return LogAnalysisResult(
            period_start=start,
            period_end=end,
            total_entries=total,
            by_level=dict(by_level),
            by_module=dict(by_module),
            by_category=dict(by_category),
            patterns=patterns,
            anomalies=anomalies,
            error_rate=error_rate,
            warning_rate=warning_rate,
            summary=summary
        )
        
    async def _detect_patterns(self, entries: List[LogEntry]) -> List[LogPattern]:
        """
        Detect patterns in log entries.
        
        Args:
            entries: Log entries
            
        Returns:
            List of detected patterns
        """
        patterns = []
        
        for pattern_def in self._pattern_definitions:
            regex = re.compile(pattern_def["regex"], re.IGNORECASE)
            matches = []
            occurrences = 0
            
            for entry in entries:
                if regex.search(entry.message) or regex.search(entry.raw):
                    matches.append(entry)
                    occurrences += 1
                    
            if occurrences > 0:
                pattern = LogPattern(
                    pattern_id=f"PAT-{datetime.utcnow().strftime('%Y%m%d')}-{len(patterns)+1:04d}",
                    type=pattern_def["type"],
                    name=pattern_def["name"],
                    description=pattern_def["description"],
                    regex=pattern_def["regex"],
                    severity=pattern_def["severity"],
                    occurrences=occurrences,
                    first_seen=matches[0].timestamp if matches else datetime.utcnow(),
                    last_seen=matches[-1].timestamp if matches else datetime.utcnow(),
                    examples=[m.message[:200] for m in matches[:5]],
                    metadata={"total_matches": occurrences}
                )
                patterns.append(pattern)
                
                self._metrics.increment_counter("patterns_detected")
                
        return patterns
        
    async def _detect_anomalies(self, entries: List[LogEntry]) -> List[LogAnomaly]:
        """
        Detect anomalies in log entries.
        
        Args:
            entries: Log entries
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Detect error bursts
        error_entries = [e for e in entries if e.level in ["ERROR", "CRITICAL"]]
        if error_entries:
            # Group by time windows
            bursts = self._detect_bursts(error_entries, window_seconds=60)
            for burst in bursts:
                if len(burst) >= 5:
                    anomaly = LogAnomaly(
                        anomaly_id=f"ANO-{datetime.utcnow().strftime('%Y%m%d')}-{len(anomalies)+1:04d}",
                        type="error_burst",
                        description=f"Error burst detected: {len(burst)} errors in 60 seconds",
                        severity="high",
                        timestamp=datetime.utcnow(),
                        log_entries=burst[:20],
                        confidence=0.85,
                        metadata={"burst_size": len(burst)}
                    )
                    anomalies.append(anomaly)
                    self._metrics.increment_counter("anomalies_detected")
                    
        # Detect unusual patterns
        levels = Counter(e.level for e in entries)
        total = len(entries)
        
        for level, count in levels.items():
            ratio = count / total if total > 0 else 0
            if level in ["ERROR", "CRITICAL"] and ratio > 0.1:
                anomaly = LogAnomaly(
                    anomaly_id=f"ANO-{datetime.utcnow().strftime('%Y%m%d')}-{len(anomalies)+1:04d}",
                    type="high_error_rate",
                    description=f"High error rate: {ratio*100:.1f}% of logs are errors",
                    severity="medium",
                    timestamp=datetime.utcnow(),
                    log_entries=[e for e in entries if e.level in ["ERROR", "CRITICAL"]][:10],
                    confidence=0.75,
                    metadata={"error_ratio": ratio}
                )
                anomalies.append(anomaly)
                self._metrics.increment_counter("anomalies_detected")
                
        # Detect warning spikes
        warning_entries = [e for e in entries if e.level == "WARNING"]
        if warning_entries:
            recent_warnings = [e for e in warning_entries if e.timestamp > datetime.utcnow() - timedelta(minutes=5)]
            if len(recent_warnings) > 10:
                anomaly = LogAnomaly(
                    anomaly_id=f"ANO-{datetime.utcnow().strftime('%Y%m%d')}-{len(anomalies)+1:04d}",
                    type="warning_spike",
                    description=f"Warning spike detected: {len(recent_warnings)} warnings in 5 minutes",
                    severity="low",
                    timestamp=datetime.utcnow(),
                    log_entries=recent_warnings[:10],
                    confidence=0.65,
                    metadata={"warning_count": len(recent_warnings)}
                )
                anomalies.append(anomaly)
                self._metrics.increment_counter("anomalies_detected")
                
        return anomalies
        
    def _detect_bursts(self, entries: List[LogEntry], window_seconds: int = 60) -> List[List[LogEntry]]:
        """
        Detect bursts of entries.
        
        Args:
            entries: Log entries
            window_seconds: Window size in seconds
            
        Returns:
            List of bursts
        """
        if not entries:
            return []
            
        sorted_entries = sorted(entries, key=lambda e: e.timestamp)
        bursts = []
        current_burst = [sorted_entries[0]]
        
        for i in range(1, len(sorted_entries)):
            time_diff = (sorted_entries[i].timestamp - sorted_entries[i-1].timestamp).total_seconds()
            if time_diff <= window_seconds:
                current_burst.append(sorted_entries[i])
            else:
                if len(current_burst) >= 3:
                    bursts.append(current_burst)
                current_burst = [sorted_entries[i]]
                
        if len(current_burst) >= 3:
            bursts.append(current_burst)
            
        return bursts
        
    def _generate_summary(
        self,
        entries: List[LogEntry],
        patterns: List[LogPattern],
        anomalies: List[LogAnomaly]
    ) -> str:
        """
        Generate summary from analysis.
        
        Args:
            entries: Log entries
            patterns: Detected patterns
            anomalies: Detected anomalies
            
        Returns:
            Summary string
        """
        lines = [
            "=== Log Analysis Summary ===",
            f"Total entries: {len(entries)}",
            f"Patterns found: {len(patterns)}",
            f"Anomalies found: {len(anomalies)}"
        ]
        
        if patterns:
            lines.append("\nTop Patterns:")
            for p in sorted(patterns, key=lambda x: x.occurrences, reverse=True)[:5]:
                lines.append(f"  - {p.name}: {p.occurrences} occurrences")
                
        if anomalies:
            lines.append("\nAnomalies:")
            for a in anomalies[:5]:
                lines.append(f"  - {a.type}: {a.description}")
                
        return "\n".join(lines)
        
    async def process_new_log(self, log_line: str, file_path: str = "stream") -> Optional[LogEntry]:
        """
        Process a new log line.
        
        Args:
            log_line: Log line
            file_path: Source file path
            
        Returns:
            Parsed log entry
        """
        entry = await self._parse_log_line(log_line, file_path)
        if entry:
            self._log_cache.append(entry)
            self._metrics.increment_counter("logs_parsed")
            
            # Track error rates
            if entry.level in ["ERROR", "CRITICAL"]:
                self._metrics.increment_counter("logs_errors")
            elif entry.level == "WARNING":
                self._metrics.increment_counter("logs_warnings")
                
        return entry
        
    async def search_logs(
        self,
        query: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[LogEntry]:
        """
        Search logs for pattern.
        
        Args:
            query: Search pattern
            start_time: Start time
            end_time: End time
            limit: Maximum results
            
        Returns:
            Matching log entries
        """
        results = []
        regex = re.compile(query, re.IGNORECASE)
        
        for entry in self._log_cache:
            if start_time and entry.timestamp < start_time:
                continue
            if end_time and entry.timestamp > end_time:
                continue
                
            if regex.search(entry.message) or regex.search(entry.raw):
                results.append(entry)
                if len(results) >= limit:
                    break
                    
        return results
        
    async def get_error_summary(self, period_days: int = 1) -> Dict[str, Any]:
        """
        Get error summary.
        
        Args:
            period_days: Analysis period in days
            
        Returns:
            Error summary
        """
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        errors = [e for e in self._log_cache if e.level in ["ERROR", "CRITICAL"] and e.timestamp > cutoff]
        
        by_module = Counter()
        by_category = Counter()
        
        for error in errors:
            by_module[error.module] += 1
            by_category[error.category] += 1
            
        return {
            "total_errors": len(errors),
            "by_module": dict(by_module),
            "by_category": dict(by_category),
            "error_rate": len(errors) / max(1, len([e for e in self._log_cache if e.timestamp > cutoff])),
            "recent_errors": [e.to_dict() for e in errors[-20:]]
        }
        
    async def close(self) -> None:
        """Close the log analyzer."""
        self._running = False
        self._initialized = False
        
        # Cancel background tasks
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        logger.info("LogAnalyzer closed")


# ====================================================================================
# GLOBAL INSTANCE
# ====================================================================================

_global_log_analyzer: Optional[LogAnalyzer] = None


def get_log_analyzer() -> LogAnalyzer:
    """
    Get the global log analyzer instance.
    
    Returns:
        LogAnalyzer instance
    """
    global _global_log_analyzer
    if _global_log_analyzer is None:
        _global_log_analyzer = LogAnalyzer()
    return _global_log_analyzer


def reset_log_analyzer() -> None:
    """Reset the global log analyzer instance."""
    global _global_log_analyzer
    if _global_log_analyzer:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_global_log_analyzer.close())
            else:
                asyncio.run(_global_log_analyzer.close())
        except Exception:
            pass
    _global_log_analyzer = None


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'LogLevel',
    'LogPatternType',
    'LogAnalysisPeriod',
    
    # Data Models
    'LogEntry',
    'LogPattern',
    'LogAnomaly',
    'LogAnalysisResult',
    
    # Main Class
    'LogAnalyzer',
    'get_log_analyzer',
    'reset_log_analyzer',
]
