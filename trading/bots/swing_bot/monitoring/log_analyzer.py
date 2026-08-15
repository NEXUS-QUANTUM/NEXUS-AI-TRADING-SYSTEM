"""
Swing Bot Log Analyzer
========================

This module provides log analysis capabilities for the Swing Bot trading system.
"""

import re
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import defaultdict, Counter
from pathlib import Path
import gzip
import shutil
import logging
import pandas as pd
from dataclasses import dataclass, field


@dataclass
class LogEntry:
    """Log entry data structure."""
    timestamp: datetime
    level: str
    message: str
    source: str
    data: Dict[str, Any] = field(default_factory=dict)
    raw: str = ""


@dataclass
class LogAnalysis:
    """Log analysis results."""
    total_entries: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    debug_count: int = 0
    unique_sources: Set[str] = field(default_factory=set)
    time_range: Tuple[Optional[datetime], Optional[datetime]] = (None, None)
    level_distribution: Dict[str, int] = field(default_factory=dict)
    source_distribution: Dict[str, int] = field(default_factory=dict)
    error_patterns: Dict[str, int] = field(default_factory=dict)
    frequent_messages: List[Tuple[str, int]] = field(default_factory=list)


class LogAnalyzer:
    """
    Analyze log files and extract meaningful patterns.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the log analyzer.
        
        Args:
            config: Configuration settings
        """
        self.config = config or {}
        self.log_dir = Path(self.config.get('log_dir', 'logs'))
        self.patterns = self._load_patterns()
        self.entries: List[LogEntry] = []
        self.analysis: Optional[LogAnalysis] = None
    
    def _load_patterns(self) -> Dict[str, Any]:
        """Load log patterns."""
        return {
            'timestamp': [
                r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)',
                r'(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})',
                r'(\d{2}:\d{2}:\d{2}(?:\.\d+)?)',
            ],
            'level': [
                r'\[(ERROR|WARNING|INFO|DEBUG|CRITICAL)\]',
                r'\s(ERROR|WARNING|INFO|DEBUG|CRITICAL)\s',
                r'^\s*(ERROR|WARNING|INFO|DEBUG|CRITICAL):'
            ],
            'source': [
                r'\[([A-Za-z0-9_\-\.]+)\]',
                r'\(([A-Za-z0-9_\-\.]+)\)',
            ]
        }
    
    def parse_log_file(self, file_path: Union[str, Path]) -> List[LogEntry]:
        """
        Parse a log file.
        
        Args:
            file_path: Path to the log file
        
        Returns:
            List of parsed log entries
        """
        file_path = Path(file_path)
        entries = []
        
        if not file_path.exists():
            logging.warning(f"Log file not found: {file_path}")
            return entries
        
        # Handle compressed files
        if file_path.suffix == '.gz':
            import gzip
            open_func = gzip.open
            mode = 'rt'
        else:
            open_func = open
            mode = 'r'
        
        try:
            with open_func(file_path, mode, encoding='utf-8') as f:
                for line in f:
                    entry = self._parse_line(line.strip())
                    if entry:
                        entries.append(entry)
        except Exception as e:
            logging.error(f"Error parsing log file {file_path}: {e}")
        
        return entries
    
    def parse_log_directory(self, directory: Union[str, Path]) -> List[LogEntry]:
        """
        Parse all log files in a directory.
        
        Args:
            directory: Directory containing log files
        
        Returns:
            List of parsed log entries
        """
        directory = Path(directory)
        all_entries = []
        
        if not directory.exists():
            logging.warning(f"Log directory not found: {directory}")
            return all_entries
        
        for file_path in directory.iterdir():
            if file_path.is_file():
                entries = self.parse_log_file(file_path)
                all_entries.extend(entries)
        
        return all_entries
    
    def _parse_line(self, line: str) -> Optional[LogEntry]:
        """
        Parse a single log line.
        
        Args:
            line: Log line to parse
        
        Returns:
            Parsed log entry or None
        """
        if not line:
            return None
        
        entry = LogEntry(raw=line)
        
        # Parse timestamp
        for pattern in self.patterns['timestamp']:
            match = re.search(pattern, line)
            if match:
                timestamp_str = match.group(1)
                try:
                    entry.timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f')
                except ValueError:
                    try:
                        entry.timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        try:
                            entry.timestamp = datetime.strptime(timestamp_str, '%Y/%m/%d %H:%M:%S')
                        except ValueError:
                            try:
                                entry.timestamp = datetime.strptime(timestamp_str, '%H:%M:%S.%f')
                            except ValueError:
                                entry.timestamp = datetime.now()
                break
        
        if not entry.timestamp:
            entry.timestamp = datetime.now()
        
        # Parse level
        for pattern in self.patterns['level']:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                entry.level = match.group(1).upper()
                break
        
        if not entry.level:
            entry.level = 'INFO'
        
        # Parse source
        for pattern in self.patterns['source']:
            match = re.search(pattern, line)
            if match:
                entry.source = match.group(1)
                break
        
        if not entry.source:
            entry.source = 'unknown'
        
        # Extract data from JSON
        json_match = re.search(r'\{.*\}', line)
        if json_match:
            try:
                entry.data = json.loads(json_match.group())
                # Clean up message
                entry.message = line.replace(json_match.group(), '').strip()
            except json.JSONDecodeError:
                entry.message = line
        else:
            entry.message = line
        
        return entry
    
    def analyze(self, entries: Optional[List[LogEntry]] = None) -> LogAnalysis:
        """
        Analyze log entries.
        
        Args:
            entries: List of log entries to analyze
        
        Returns:
            Log analysis results
        """
        if entries is None:
            entries = self.entries
        
        if not entries:
            return LogAnalysis()
        
        analysis = LogAnalysis()
        analysis.total_entries = len(entries)
        
        # Count levels
        level_counts = Counter()
        source_counts = Counter()
        error_messages = []
        
        timestamps = []
        
        for entry in entries:
            # Count levels
            level_counts[entry.level] += 1
            analysis.unique_sources.add(entry.source)
            source_counts[entry.source] += 1
            
            if entry.timestamp:
                timestamps.append(entry.timestamp)
            
            # Collect error messages
            if entry.level in ['ERROR', 'CRITICAL']:
                error_messages.append(entry.message)
        
        analysis.level_distribution = dict(level_counts)
        analysis.error_count = level_counts.get('ERROR', 0) + level_counts.get('CRITICAL', 0)
        analysis.warning_count = level_counts.get('WARNING', 0)
        analysis.info_count = level_counts.get('INFO', 0)
        analysis.debug_count = level_counts.get('DEBUG', 0)
        analysis.source_distribution = dict(source_counts)
        
        if timestamps:
            analysis.time_range = (min(timestamps), max(timestamps))
        
        # Find error patterns
        analysis.error_patterns = self._analyze_error_patterns(error_messages)
        
        # Find frequent messages
        message_counts = Counter([e.message[:100] for e in entries])
        analysis.frequent_messages = message_counts.most_common(10)
        
        self.analysis = analysis
        return analysis
    
    def _analyze_error_patterns(self, error_messages: List[str]) -> Dict[str, int]:
        """Analyze error message patterns."""
        patterns = Counter()
        
        for msg in error_messages:
            # Extract error type
            error_type_match = re.search(r'([A-Za-z]+Error):', msg)
            if error_type_match:
                patterns[error_type_match.group(1)] += 1
            else:
                # Look for common patterns
                if 'timeout' in msg.lower():
                    patterns['Timeout'] += 1
                elif 'connection' in msg.lower():
                    patterns['Connection'] += 1
                elif 'validation' in msg.lower():
                    patterns['Validation'] += 1
                elif 'permission' in msg.lower() or 'access' in msg.lower():
                    patterns['Permission'] += 1
                elif 'not found' in msg.lower():
                    patterns['NotFound'] += 1
        
        return dict(patterns)
    
    def find_errors(self, entries: Optional[List[LogEntry]] = None) -> List[LogEntry]:
        """
        Find error log entries.
        
        Args:
            entries: List of log entries
        
        Returns:
            List of error entries
        """
        if entries is None:
            entries = self.entries
        
        return [e for e in entries if e.level in ['ERROR', 'CRITICAL']]
    
    def find_by_level(self, level: str, entries: Optional[List[LogEntry]] = None) -> List[LogEntry]:
        """
        Find log entries by level.
        
        Args:
            level: Log level
            entries: List of log entries
        
        Returns:
            List of matching entries
        """
        if entries is None:
            entries = self.entries
        
        return [e for e in entries if e.level == level.upper()]
    
    def find_by_source(self, source: str, entries: Optional[List[LogEntry]] = None) -> List[LogEntry]:
        """
        Find log entries by source.
        
        Args:
            source: Log source
            entries: List of log entries
        
        Returns:
            List of matching entries
        """
        if entries is None:
            entries = self.entries
        
        return [e for e in entries if e.source == source]
    
    def find_by_time_range(
        self,
        start: datetime,
        end: datetime,
        entries: Optional[List[LogEntry]] = None
    ) -> List[LogEntry]:
        """
        Find log entries within a time range.
        
        Args:
            start: Start time
            end: End time
            entries: List of log entries
        
        Returns:
            List of matching entries
        """
        if entries is None:
            entries = self.entries
        
        return [e for e in entries if start <= e.timestamp <= end]
    
    def find_by_message_pattern(
        self,
        pattern: str,
        entries: Optional[List[LogEntry]] = None
    ) -> List[LogEntry]:
        """
        Find log entries matching a message pattern.
        
        Args:
            pattern: Regex pattern to search
            entries: List of log entries
        
        Returns:
            List of matching entries
        """
        if entries is None:
            entries = self.entries
        
        regex = re.compile(pattern, re.IGNORECASE)
        return [e for e in entries if regex.search(e.message)]
    
    def generate_report(self, entries: Optional[List[LogEntry]] = None) -> Dict[str, Any]:
        """
        Generate a log analysis report.
        
        Args:
            entries: List of log entries
        
        Returns:
            Report dictionary
        """
        if entries is None:
            entries = self.entries
        
        analysis = self.analyze(entries)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_entries': analysis.total_entries,
            'error_count': analysis.error_count,
            'warning_count': analysis.warning_count,
            'info_count': analysis.info_count,
            'debug_count': analysis.debug_count,
            'time_range': {
                'start': analysis.time_range[0].isoformat() if analysis.time_range[0] else None,
                'end': analysis.time_range[1].isoformat() if analysis.time_range[1] else None
            },
            'level_distribution': analysis.level_distribution,
            'source_distribution': analysis.source_distribution,
            'error_patterns': analysis.error_patterns,
            'frequent_messages': analysis.frequent_messages,
            'unique_sources': list(analysis.unique_sources)
        }
    
    def export_report(self, report: Dict[str, Any], output_file: Union[str, Path]) -> None:
        """
        Export report to file.
        
        Args:
            report: Report dictionary
            output_file: Output file path
        """
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
    
    def get_trend_analysis(self, entries: Optional[List[LogEntry]] = None) -> pd.DataFrame:
        """
        Get trend analysis of log entries.
        
        Args:
            entries: List of log entries
        
        Returns:
            DataFrame with trend data
        """
        if entries is None:
            entries = self.entries
        
        if not entries:
            return pd.DataFrame()
        
        # Create DataFrame
        data = []
        for entry in entries:
            data.append({
                'timestamp': entry.timestamp,
                'level': entry.level,
                'source': entry.source
            })
        
        df = pd.DataFrame(data)
        
        # Create time-based aggregations
        df['hour'] = df['timestamp'].dt.floor('H')
        df['day'] = df['timestamp'].dt.floor('D')
        
        # Count by hour and level
        hourly = df.groupby(['hour', 'level']).size().unstack(fill_value=0)
        
        # Count by day and level
        daily = df.groupby(['day', 'level']).size().unstack(fill_value=0)
        
        return {
            'hourly': hourly,
            'daily': daily
        }


class LogRotator:
    """
    Manage log file rotation.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the log rotator.
        
        Args:
            config: Configuration settings
        """
        self.config = config or {}
        self.log_dir = Path(self.config.get('log_dir', 'logs'))
        self.max_size = self.config.get('max_size', 100 * 1024 * 1024)  # 100 MB
        self.max_age_days = self.config.get('max_age_days', 30)
        self.compress = self.config.get('compress', True)
    
    def rotate(self, log_file: Union[str, Path]) -> None:
        """
        Rotate a log file.
        
        Args:
            log_file: Path to the log file
        """
        log_file = Path(log_file)
        
        if not log_file.exists():
            return
        
        # Check file size
        if log_file.stat().st_size < self.max_size:
            return
        
        # Create backup
        backup_name = f"{log_file.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        backup_path = self.log_dir / 'archive' / backup_name
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.move(log_file, backup_path)
        
        # Compress if enabled
        if self.compress:
            with open(backup_path, 'rb') as f_in:
                with gzip.open(f"{backup_path}.gz", 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            backup_path.unlink()
        
        # Create new log file
        log_file.touch()
    
    def cleanup_old_logs(self) -> None:
        """Clean up old log files."""
        archive_dir = self.log_dir / 'archive'
        if not archive_dir.exists():
            return
        
        cutoff = datetime.now() - timedelta(days=self.max_age_days)
        
        for file_path in archive_dir.iterdir():
            if file_path.is_file():
                # Check file modification time
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < cutoff:
                    file_path.unlink()


# Global log analyzer instance
_log_analyzer: Optional[LogAnalyzer] = None


def get_log_analyzer() -> LogAnalyzer:
    """Get the global log analyzer instance."""
    global _log_analyzer
    if _log_analyzer is None:
        _log_analyzer = LogAnalyzer()
    return _log_analyzer


def analyze_logs(log_dir: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Analyze logs from a directory.
    
    Args:
        log_dir: Directory containing log files
    
    Returns:
        Analysis report
    """
    analyzer = LogAnalyzer()
    if log_dir:
        analyzer.log_dir = Path(log_dir)
    
    entries = analyzer.parse_log_directory(analyzer.log_dir)
    analyzer.entries = entries
    
    return analyzer.generate_report()


__all__ = [
    'LogEntry',
    'LogAnalysis',
    'LogAnalyzer',
    'LogRotator',
    'get_log_analyzer',
    'analyze_logs'
]
