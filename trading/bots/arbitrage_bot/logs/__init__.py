# trading/bots/arbitrage_bot/logs/__init__.py
# NEXUS AI TRADING SYSTEM - COMPLETE LOGGING MODULE
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module provides enterprise-grade logging infrastructure for the arbitrage bot
# with support for structured logging, log rotation, compression, archiving,
# monitoring, and distributed tracing.
# ====================================================================================

"""
NEXUS Arbitrage Bot Logging Module

A comprehensive logging system designed for high-frequency trading bots with:
- Structured JSON logging for log aggregation (ELK, Loki, Datadog)
- Asynchronous logging with zero-impact on trading performance
- Automatic log rotation with compression and archiving
- Sensitive data redaction (API keys, passwords, tokens)
- Distributed tracing with correlation IDs
- Performance metrics logging with Prometheus integration
- Trade and opportunity tracking with structured formats
- Multi-level logging with category filtering
- Cloud archive support (S3, GCS, Azure Blob)
- Compliance-ready audit logging
- Real-time log monitoring and alerting
- Contextual logging with request/user tracking
"""

import os
import sys
import json
import time
import gzip
import shutil
import logging
import logging.handlers
import traceback
import asyncio
import threading
import queue
import socket
import hashlib
import re
import uuid
from typing import Dict, List, Optional, Any, Union, Callable, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from contextvars import ContextVar
from functools import wraps
from collections import deque, defaultdict

# Third-party imports with graceful fallback
try:
    import colorlog
    HAS_COLORLOG = True
except ImportError:
    HAS_COLORLOG = False

try:
    from pythonjsonlogger import jsonlogger
    HAS_JSONLOGGER = True
except ImportError:
    HAS_JSONLOGGER = False

try:
    import sentry_sdk
    from sentry_sdk.integrations.logging import SentryHandler
    HAS_SENTRY = True
except ImportError:
    HAS_SENTRY = False

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

try:
    from google.cloud import storage
    HAS_GCS = True
except ImportError:
    HAS_GCS = False

try:
    from azure.storage.blob import BlobServiceClient
    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False

# NEXUS internal imports
try:
    from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector
except ImportError:
    MetricsCollector = None

logger = logging.getLogger(__name__)


# ======================== ENUMS AND CONSTANTS ========================

class LogLevel(str, Enum):
    """Standard and custom log levels."""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    NOTICE = "NOTICE"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    PERFORMANCE = "PERFORMANCE"
    TRADE = "TRADE"
    OPPORTUNITY = "OPPORTUNITY"
    EXECUTION = "EXECUTION"
    SYSTEM = "SYSTEM"
    SECURITY = "SECURITY"
    AUDIT = "AUDIT"
    COMPLIANCE = "COMPLIANCE"


class LogCategory(str, Enum):
    """Log categories for filtering and routing."""
    # Core categories
    SYSTEM = "system"
    EXCHANGE = "exchange"
    ORDER = "order"
    TRADE = "trade"
    OPPORTUNITY = "opportunity"
    EXECUTION = "execution"
    STRATEGY = "strategy"
    RISK = "risk"
    
    # Infrastructure categories
    PERFORMANCE = "performance"
    SECURITY = "security"
    AUDIT = "audit"
    COMPLIANCE = "compliance"
    WEBSOCKET = "websocket"
    DATABASE = "database"
    NETWORK = "network"
    CONFIG = "config"
    API = "api"
    
    # Business categories
    PNL = "pnl"
    PORTFOLIO = "portfolio"
    POSITION = "position"
    SIGNAL = "signal"
    BACKTEST = "backtest"
    PAPER_TRADING = "paper_trading"


class LogFormat(str, Enum):
    """Log output formats."""
    TEXT = "text"
    JSON = "json"
    COLOR = "color"
    CSV = "csv"
    SYSLOG = "syslog"
    GELF = "gelf"  # Graylog Extended Log Format
    CEF = "cef"    # Common Event Format


class LogStorage(str, Enum):
    """Log storage destinations."""
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"
    ELASTICSEARCH = "elasticsearch"
    LOGSTASH = "logstash"
    DATADOG = "datadog"
    GRAYLOG = "graylog"


# ======================== CONFIGURATION ========================

@dataclass
class CloudStorageConfig:
    """Cloud storage configuration for log archiving."""
    provider: str = "s3"  # s3, gcs, azure
    bucket: str = ""
    prefix: str = "logs/"
    region: str = "us-east-1"
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    endpoint_url: Optional[str] = None
    use_ssl: bool = True
    timeout: int = 30
    max_retries: int = 3


@dataclass
class LoggerConfig:
    """
    Comprehensive logging configuration.
    
    Attributes:
        level: Global log level
        format: Output format
        categories: Enabled/disabled categories
        handlers: Handler configurations
        storage: Storage configurations
        monitoring: Monitoring configurations
        security: Security configurations
    """
    # Basic settings
    level: str = "INFO"
    format: LogFormat = LogFormat.TEXT
    enable_colors: bool = True
    enable_json: bool = True
    enable_timestamp: bool = True
    
    # File settings
    log_dir: str = "logs"
    max_file_size: int = 100 * 1024 * 1024  # 100 MB
    backup_count: int = 10
    compression: bool = True
    compression_delay_days: int = 7
    rotation_schedule: str = "daily"  # daily, hourly, size-based
    
    # Archive settings
    archive_enabled: bool = True
    archive_path: str = "logs/archive"
    archive_retention_days: int = 30
    archive_cloud: Optional[CloudStorageConfig] = None
    archive_local_compression: bool = True
    
    # Categories
    enabled_categories: List[LogCategory] = field(default_factory=lambda: list(LogCategory))
    disabled_categories: List[LogCategory] = field(default_factory=list)
    category_levels: Dict[str, str] = field(default_factory=dict)
    
    # Handlers
    console_enabled: bool = True
    console_level: Optional[str] = None
    file_enabled: bool = True
    file_level: Optional[str] = None
    syslog_enabled: bool = False
    syslog_level: Optional[str] = None
    syslog_address: str = "/dev/log"
    syslog_facility: str = "local0"
    sentry_enabled: bool = False
    sentry_level: str = "ERROR"
    sentry_dsn: Optional[str] = None
    sentry_environment: str = "production"
    
    # Performance
    async_logging: bool = True
    queue_size: int = 10000
    flush_interval: float = 1.0
    batch_size: int = 100
    drop_on_overflow: bool = True
    worker_threads: int = 2
    
    # Context
    include_hostname: bool = True
    include_pid: bool = True
    include_thread: bool = True
    include_correlation_id: bool = True
    include_user_id: bool = False
    include_request_id: bool = True
    include_session_id: bool = False
    include_environment: bool = True
    include_version: bool = True
    include_extra_fields: bool = True
    
    # Security
    redact_sensitive: bool = True
    sensitive_patterns: List[str] = field(default_factory=lambda: [
        r'api[_-]?key["\s:=]+([a-zA-Z0-9_\-]+)',
        r'secret["\s:=]+([a-zA-Z0-9_\-]+)',
        r'passphrase["\s:=]+([a-zA-Z0-9_\-]+)',
        r'token["\s:=]+([a-zA-Z0-9_\-]+)',
        r'password["\s:=]+([a-zA-Z0-9_\-]+)',
        r'private[_-]?key["\s:=]+([a-zA-Z0-9_\-]+)',
        r'signature["\s:=]+([a-zA-Z0-9_\-]+)',
        r'bearer["\s:=]+([a-zA-Z0-9_\-]+)',
        r'authorization["\s:=]+([a-zA-Z0-9_\-]+)',
        r'credential["\s:=]+([a-zA-Z0-9_\-]+)',
    ])
    redact_replacement: str = "***REDACTED***"
    redact_emails: bool = True
    redact_ips: bool = True
    redact_personal_data: bool = True
    
    # Monitoring
    metrics_enabled: bool = True
    metrics_prefix: str = "nexus_arbitrage_logs"
    metrics_labels: Dict[str, str] = field(default_factory=dict)
    alert_on_error: bool = True
    alert_on_critical: bool = True
    
    # Audit
    audit_enabled: bool = True
    audit_log_path: str = "logs/audit.log"
    audit_retention_days: int = 365
    audit_fields: List[str] = field(default_factory=lambda: [
        "timestamp", "user", "action", "resource", "ip", "user_agent"
    ])
    
    # Environment
    environment: str = "production"
    service_name: str = "nexus-arbitrage-bot"
    service_version: str = "3.0.0"
    
    def __post_init__(self):
        """Validate and configure after initialization."""
        # Create log directories
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        if self.archive_enabled:
            Path(self.archive_path).mkdir(parents=True, exist_ok=True)
        if self.audit_enabled:
            Path(self.audit_log_path).parent.mkdir(parents=True, exist_ok=True)
            
        # Convert level to uppercase
        self.level = self.level.upper()
        
        # Validate level
        valid_levels = [l.value for l in LogLevel] + list(logging._nameToLevel.keys())
        if self.level not in valid_levels:
            raise ValueError(f"Invalid log level: {self.level}")
            
        # Convert string categories to enum
        self.enabled_categories = [
            LogCategory(c) if isinstance(c, str) else c 
            for c in self.enabled_categories
        ]
        self.disabled_categories = [
            LogCategory(c) if isinstance(c, str) else c 
            for c in self.disabled_categories
        ]
        
        # Set category levels
        if not self.category_levels:
            self.category_levels = {
                "trade": "INFO",
                "opportunity": "INFO",
                "execution": "INFO",
                "performance": "INFO",
                "system": "INFO",
                "security": "WARNING",
                "audit": "INFO",
                "compliance": "INFO"
            }


# ======================== CONTEXT MANAGEMENT ========================

# Context variables for distributed tracing
_correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')
_user_id_var: ContextVar[str] = ContextVar('user_id', default='')
_request_id_var: ContextVar[str] = ContextVar('request_id', default='')
_session_id_var: ContextVar[str] = ContextVar('session_id', default='')
_trace_id_var: ContextVar[str] = ContextVar('trace_id', default='')
_span_id_var: ContextVar[str] = ContextVar('span_id', default='')
_environment_var: ContextVar[str] = ContextVar('environment', default='production')


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current context."""
    _correlation_id_var.set(correlation_id)


def get_correlation_id() -> str:
    """Get current correlation ID."""
    return _correlation_id_var.get()


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())


def set_user_id(user_id: str) -> None:
    """Set user ID for current context."""
    _user_id_var.set(user_id)


def get_user_id() -> str:
    """Get current user ID."""
    return _user_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set request ID for current context."""
    _request_id_var.set(request_id)


def get_request_id() -> str:
    """Get current request ID."""
    return _request_id_var.get()


def set_session_id(session_id: str) -> None:
    """Set session ID for current context."""
    _session_id_var.set(session_id)


def get_session_id() -> str:
    """Get current session ID."""
    return _session_id_var.get()


def set_trace_id(trace_id: str) -> None:
    """Set trace ID for current context."""
    _trace_id_var.set(trace_id)


def get_trace_id() -> str:
    """Get current trace ID."""
    return _trace_id_var.get()


def set_span_id(span_id: str) -> None:
    """Set span ID for current context."""
    _span_id_var.set(span_id)


def get_span_id() -> str:
    """Get current span ID."""
    return _span_id_var.get()


def set_environment(environment: str) -> None:
    """Set environment for current context."""
    _environment_var.set(environment)


def get_environment() -> str:
    """Get current environment."""
    return _environment_var.get()


class LogContext:
    """Context manager for setting log context."""
    
    def __init__(
        self,
        correlation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        **kwargs
    ):
        self._context = kwargs
        self._previous_context = {}
        
        if correlation_id:
            self._context['correlation_id'] = correlation_id
        if user_id:
            self._context['user_id'] = user_id
        if request_id:
            self._context['request_id'] = request_id
        if session_id:
            self._context['session_id'] = session_id
        if trace_id:
            self._context['trace_id'] = trace_id
            
    def __enter__(self):
        """Enter context, saving previous values."""
        for key, value in self._context.items():
            var_name = f"_{key}_var"
            if hasattr(sys.modules[__name__], var_name):
                var = getattr(sys.modules[__name__], var_name)
                self._previous_context[key] = var.get()
                var.set(value)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context, restoring previous values."""
        for key, value in self._previous_context.items():
            var_name = f"_{key}_var"
            if hasattr(sys.modules[__name__], var_name):
                var = getattr(sys.modules[__name__], var_name)
                var.set(value)
                
    @classmethod
    def create(cls, **kwargs):
        """Create a new context with given values."""
        return cls(**kwargs)


# ======================== LOG FILTERS ========================

class ContextFilter(logging.Filter):
    """Adds context information to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _correlation_id_var.get()
        record.user_id = _user_id_var.get()
        record.request_id = _request_id_var.get()
        record.session_id = _session_id_var.get()
        record.trace_id = _trace_id_var.get()
        record.span_id = _span_id_var.get()
        record.environment = _environment_var.get()
        record.hostname = socket.gethostname()
        record.pid = os.getpid()
        record.thread_name = threading.current_thread().name
        return True


class SensitiveDataFilter(logging.Filter):
    """
    Filter that redacts sensitive data from log records.
    Uses regex patterns to find and replace sensitive information.
    """
    
    def __init__(
        self,
        patterns: List[str],
        replacement: str = "***REDACTED***",
        redact_emails: bool = True,
        redact_ips: bool = True,
        redact_personal: bool = True
    ):
        self.patterns = [re.compile(p, re.IGNORECASE) for p in patterns]
        self.replacement = replacement
        self.redact_emails = redact_emails
        self.redact_ips = redact_ips
        self.redact_personal = redact_personal
        
        # Additional patterns
        if redact_emails:
            self.patterns.append(re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'))
        if redact_ips:
            self.patterns.append(re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'))
        if redact_personal:
            self.patterns.append(re.compile(r'phone["\s:=]+([0-9+\-() ]{10,})'))
            self.patterns.append(re.compile(r'address["\s:=]+([a-zA-Z0-9 ,.\-]+)'))
            self.patterns.append(re.compile(r'dob["\s:=]+([0-9/\-]+)'))
            
    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive data from log record."""
        if hasattr(record, 'msg') and record.msg:
            msg = record.msg
            for pattern in self.patterns:
                msg = pattern.sub(self.replacement, msg)
            record.msg = msg
            
        if hasattr(record, 'args') and record.args:
            args = list(record.args)
            for i, arg in enumerate(args):
                if isinstance(arg, str):
                    for pattern in self.patterns:
                        arg = pattern.sub(self.replacement, arg)
                    args[i] = arg
                elif isinstance(arg, dict):
                    args[i] = self._redact_dict(arg)
                elif isinstance(arg, list):
                    args[i] = self._redact_list(arg)
            record.args = tuple(args)
            
        return True
        
    def _redact_dict(self, data: dict) -> dict:
        """Recursively redact sensitive data in a dictionary."""
        result = {}
        sensitive_keys = {'api_key', 'api_secret', 'secret', 'password', 'passphrase', 
                         'token', 'private_key', 'signature', 'authorization', 'bearer'}
        
        for key, value in data.items():
            if key.lower() in sensitive_keys:
                result[key] = self.replacement
            elif isinstance(value, dict):
                result[key] = self._redact_dict(value)
            elif isinstance(value, list):
                result[key] = self._redact_list(value)
            elif isinstance(value, str):
                for pattern in self.patterns:
                    value = pattern.sub(self.replacement, value)
                result[key] = value
            else:
                result[key] = value
                
        return result
        
    def _redact_list(self, data: list) -> list:
        """Recursively redact sensitive data in a list."""
        result = []
        for item in data:
            if isinstance(item, dict):
                result.append(self._redact_dict(item))
            elif isinstance(item, list):
                result.append(self._redact_list(item))
            elif isinstance(item, str):
                for pattern in self.patterns:
                    item = pattern.sub(self.replacement, item)
                result.append(item)
            else:
                result.append(item)
        return result


class CategoryFilter(logging.Filter):
    """Filter logs by category with configurable levels."""
    
    def __init__(
        self,
        enabled_categories: List[LogCategory],
        disabled_categories: List[LogCategory],
        category_levels: Dict[str, str]
    ):
        self.enabled = [c.value for c in enabled_categories]
        self.disabled = [c.value for c in disabled_categories]
        self.category_levels = category_levels
        
    def filter(self, record: logging.LogRecord) -> bool:
        """Check if record passes category filter."""
        category = getattr(record, 'category', '')
        
        # Check if category is disabled
        if category in self.disabled:
            return False
            
        # Check if category is enabled
        if self.enabled and category not in self.enabled:
            return False
            
        # Check category-specific level
        if category in self.category_levels:
            min_level = getattr(logging, self.category_levels[category].upper(), logging.INFO)
            if record.levelno < min_level:
                return False
                
        return True


class LevelFilter(logging.Filter):
    """Filter logs by level for specific handlers."""
    
    def __init__(self, min_level: str, max_level: Optional[str] = None):
        self.min_level = getattr(logging, min_level.upper(), logging.INFO)
        self.max_level = getattr(logging, max_level.upper(), logging.CRITICAL) if max_level else None
        
    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < self.min_level:
            return False
        if self.max_level and record.levelno > self.max_level:
            return False
        return True


# ======================== LOG FORMATTERS ========================

class BaseFormatter(logging.Formatter):
    """Base formatter with common functionality."""
    
    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        style: str = '%'
    ):
        if fmt is None:
            fmt = '%(asctime)s | %(levelname)-8s | %(correlation_id)-8s | %(category)-12s | %(message)s'
        if datefmt is None:
            datefmt = '%Y-%m-%d %H:%M:%S.%f'
        super().__init__(fmt, datefmt, style)


class TextFormatter(BaseFormatter):
    """Plain text formatter."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as text."""
        return super().format(record)


class ColorFormatter(BaseFormatter):
    """
    Colorized console formatter.
    Uses ANSI color codes for better readability.
    """
    
    COLORS = {
        'TRACE': '\033[37m',       # White
        'DEBUG': '\033[36m',       # Cyan
        'INFO': '\033[32m',        # Green
        'NOTICE': '\033[34m',      # Blue
        'WARNING': '\033[33m',     # Yellow
        'ERROR': '\033[31m',       # Red
        'CRITICAL': '\033[41m',    # Red background
        'PERFORMANCE': '\033[35m', # Magenta
        'TRADE': '\033[34m',       # Blue
        'OPPORTUNITY': '\033[32m', # Green
        'EXECUTION': '\033[33m',   # Yellow
        'SYSTEM': '\033[36m',      # Cyan
        'SECURITY': '\033[31m',    # Red
        'AUDIT': '\033[35m',       # Magenta
        'RESET': '\033[0m'
    }
    
    LEVEL_COLORS = {
        'TRACE': '\033[37m',
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'NOTICE': '\033[34m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[41m\033[37m',
        'PERFORMANCE': '\033[35m',
        'TRADE': '\033[34m',
        'OPPORTUNITY': '\033[32m',
        'EXECUTION': '\033[33m',
        'SYSTEM': '\033[36m',
        'SECURITY': '\033[31m',
        'AUDIT': '\033[35m',
    }
    
    CATEGORY_COLORS = {
        'trade': '\033[34m',
        'opportunity': '\033[32m',
        'execution': '\033[33m',
        'performance': '\033[35m',
        'system': '\033[36m',
        'security': '\033[31m',
        'audit': '\033[35m',
        'default': '\033[37m'
    }
    
    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        super().__init__(fmt, datefmt)
        if HAS_COLORLOG:
            self._color_formatter = colorlog.ColoredFormatter(
                fmt or '%(log_color)s%(levelname)-8s%(reset)s | %(asctime)s | %(message)s',
                datefmt=datefmt
            )
        else:
            self._color_formatter = None
            
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        if self._color_formatter:
            return self._color_formatter.format(record)
            
        # Manual colorization
        levelname = record.levelname
        category = getattr(record, 'category', '')
        
        level_color = self.LEVEL_COLORS.get(levelname, self.COLORS.get(levelname, '\033[37m'))
        category_color = self.CATEGORY_COLORS.get(category, self.CATEGORY_COLORS['default'])
        reset = self.COLORS['RESET']
        
        # Format message
        formatted = super().format(record)
        
        # Apply colors to components
        parts = formatted.split('|')
        if len(parts) >= 4:
            # Color level
            parts[1] = f"{level_color}{parts[1].strip()}{reset}"
            # Color category
            parts[3] = f"{category_color}{parts[3].strip()}{reset}"
            formatted = '|'.join(parts)
            
        return formatted


class JsonFormatter(BaseFormatter):
    """
    JSON formatter for structured logging.
    Compatible with ELK, Loki, and other log aggregation systems.
    """
    
    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        style: str = '%',
        validate: bool = True
    ):
        super().__init__(fmt, datefmt, style)
        self.validate = validate
        
        if HAS_JSONLOGGER:
            self._json_formatter = jsonlogger.JsonFormatter(
                fmt=fmt,
                datefmt=datefmt,
                style=style
            )
        else:
            self._json_formatter = None
            
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        if self._json_formatter:
            return self._json_formatter.format(record)
            
        # Fallback JSON formatter
        log_data = self._build_log_data(record)
        
        try:
            return json.dumps(log_data, default=str, ensure_ascii=False)
        except Exception:
            return super().format(record)
            
    def _build_log_data(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Build log data dictionary."""
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.threadName,
            "process": record.process,
            "host": getattr(record, 'hostname', socket.gethostname()),
            "environment": getattr(record, 'environment', 'production'),
            "service": 'nexus-arbitrage-bot',
            "version": '3.0.0'
        }
        
        # Add context
        context_fields = [
            'correlation_id', 'user_id', 'request_id', 'session_id',
            'trace_id', 'span_id', 'category'
        ]
        for field in context_fields:
            value = getattr(record, field, None)
            if value:
                log_data[field] = value
                
        # Add duration if present
        if hasattr(record, 'duration_ms'):
            log_data["duration_ms"] = record.duration_ms
            
        # Add value if present
        if hasattr(record, 'value'):
            log_data["value"] = record.value
            
        # Add metric if present
        if hasattr(record, 'metric'):
            log_data["metric"] = record.metric
            
        # Add exception if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
            
        # Add extra fields
        if hasattr(record, 'extra'):
            extra = getattr(record, 'extra', {})
            if isinstance(extra, dict):
                log_data.update(extra)
                
        return log_data


class GELFFormatter(BaseFormatter):
    """Graylog Extended Log Format (GELF) formatter."""
    
    def __init__(self, facility: str = "nexus-arbitrage-bot"):
        super().__init__()
        self.facility = facility
        
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as GELF."""
        gelf_message = {
            "version": "1.1",
            "host": socket.gethostname(),
            "short_message": record.getMessage(),
            "timestamp": record.created,
            "level": self._gelf_level(record.levelno),
            "facility": self.facility,
            "_correlation_id": getattr(record, 'correlation_id', ''),
            "_user_id": getattr(record, 'user_id', ''),
            "_request_id": getattr(record, 'request_id', ''),
            "_category": getattr(record, 'category', ''),
            "_logger": record.name,
            "_module": record.module,
            "_function": record.funcName,
            "_line": record.lineno,
            "_thread": record.threadName,
            "_process": record.process,
            "_environment": getattr(record, 'environment', 'production')
        }
        
        # Add duration if present
        if hasattr(record, 'duration_ms'):
            gelf_message["_duration_ms"] = record.duration_ms
            
        # Add exception if present
        if record.exc_info:
            gelf_message["_exception"] = traceback.format_exception(*record.exc_info)
            
        return json.dumps(gelf_message)
        
    def _gelf_level(self, level: int) -> int:
        """Convert logging level to GELF level."""
        if level >= logging.CRITICAL:
            return 2
        elif level >= logging.ERROR:
            return 3
        elif level >= logging.WARNING:
            return 4
        elif level >= logging.INFO:
            return 6
        else:
            return 7


class CSVFormatter(BaseFormatter):
    """CSV formatter for structured data export."""
    
    def __init__(
        self,
        fields: List[str] = None,
        delimiter: str = ','
    ):
        super().__init__()
        self.fields = fields or [
            'timestamp', 'level', 'category', 'correlation_id',
            'message', 'module', 'function', 'line'
        ]
        self.delimiter = delimiter
        
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as CSV."""
        row = []
        for field in self.fields:
            value = getattr(record, field, '')
            if field == 'timestamp':
                value = self.formatTime(record, self.datefmt)
            elif field == 'message':
                value = record.getMessage()
            # Escape commas and quotes
            value = str(value).replace('"', '""')
            if self.delimiter in value:
                value = f'"{value}"'
            row.append(value)
        return self.delimiter.join(row)


# ======================== LOG HANDLERS ========================

class AsyncQueueHandler(logging.Handler):
    """
    Asynchronous logging handler using a queue.
    Prevents logging from blocking the main trading thread.
    """
    
    def __init__(
        self,
        handler: logging.Handler,
        maxsize: int = 10000,
        drop_on_overflow: bool = True,
        worker_threads: int = 2
    ):
        super().__init__()
        self.handler = handler
        self.queue = queue.Queue(maxsize=maxsize)
        self.drop_on_overflow = drop_on_overflow
        self.running = True
        self.workers = []
        
        # Start worker threads
        for i in range(worker_threads):
            thread = threading.Thread(
                target=self._worker,
                daemon=True,
                name=f"log-worker-{i}"
            )
            thread.start()
            self.workers.append(thread)
            
    def _worker(self) -> None:
        """Worker thread to process log records asynchronously."""
        while self.running:
            try:
                record = self.queue.get(timeout=0.1)
                if record is None:
                    break
                try:
                    self.handler.handle(record)
                except Exception as e:
                    sys.stderr.write(f"Async log handler error: {e}\n")
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                sys.stderr.write(f"Async worker error: {e}\n")
                
    def emit(self, record: logging.LogRecord) -> None:
        """Add log record to queue."""
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            if self.drop_on_overflow:
                self.handleError(record)
            else:
                # Block until space available
                try:
                    self.queue.put(record, timeout=5.0)
                except queue.Full:
                    self.handleError(record)
                    
    def flush(self) -> None:
        """Flush all pending log records."""
        self.queue.join()
        
    def close(self) -> None:
        """Close handler and stop worker threads."""
        self.running = False
        
        # Send sentinel to stop workers
        for _ in self.workers:
            self.queue.put(None)
            
        # Wait for workers to finish
        for thread in self.workers:
            thread.join(timeout=5.0)
            
        self.handler.close()
        super().close()


class RotatingFileHandlerWithCompression(logging.handlers.RotatingFileHandler):
    """
    Rotating file handler with automatic compression.
    Compresses rotated log files after a delay.
    """
    
    def __init__(
        self,
        filename: str,
        mode: str = 'a',
        maxBytes: int = 0,
        backupCount: int = 0,
        encoding: Optional[str] = None,
        delay: bool = False,
        compress: bool = True,
        compression_delay_days: int = 7
    ):
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
        self.compress = compress
        self.compression_delay_days = compression_delay_days
        self._compression_running = True
        self._compression_thread = threading.Thread(
            target=self._compress_old_files,
            daemon=True
        )
        self._compression_thread.start()
        
    def _compress_old_files(self) -> None:
        """Compress old log files after delay."""
        while self._compression_running:
            try:
                time.sleep(3600)  # Check every hour
                if not self.compress:
                    continue
                    
                base = self.baseFilename
                if base.endswith('.log'):
                    base = base[:-4]
                    
                cutoff = time.time() - (self.compression_delay_days * 24 * 3600)
                for i in range(1, self.backupCount + 1):
                    log_file = f"{base}.log.{i}"
                    if os.path.exists(log_file):
                        mtime = os.path.getmtime(log_file)
                        if mtime < cutoff:
                            gz_file = f"{log_file}.gz"
                            if not os.path.exists(gz_file):
                                self._compress_file(log_file)
                                
            except Exception as e:
                sys.stderr.write(f"Compression error: {e}\n")
                
    def _compress_file(self, file_path: str) -> None:
        """Compress a file using gzip."""
        try:
            with open(file_path, 'rb') as f_in:
                with gzip.open(f"{file_path}.gz", 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            os.remove(file_path)
        except Exception as e:
            sys.stderr.write(f"Failed to compress {file_path}: {e}\n")
            
    def close(self) -> None:
        """Close handler and stop compression thread."""
        self._compression_running = False
        self._compression_thread.join(timeout=5.0)
        super().close()


class TimedRotatingFileHandlerWithCompression(
    logging.handlers.TimedRotatingFileHandler
):
    """Timed rotating file handler with compression."""
    
    def __init__(
        self,
        filename: str,
        when: str = 'midnight',
        interval: int = 1,
        backupCount: int = 30,
        encoding: Optional[str] = None,
        delay: bool = False,
        utc: bool = False,
        compress: bool = True,
        compression_delay_days: int = 7
    ):
        super().__init__(filename, when, interval, backupCount, encoding, delay, utc)
        self.compress = compress
        self.compression_delay_days = compression_delay_days
        self._compression_running = True
        self._compression_thread = threading.Thread(
            target=self._compress_old_files,
            daemon=True
        )
        self._compression_thread.start()
        
    def _compress_old_files(self) -> None:
        """Compress old log files after delay."""
        while self._compression_running:
            try:
                time.sleep(3600)
                if not self.compress:
                    continue
                    
                base = self.baseFilename
                if base.endswith('.log'):
                    base = base[:-4]
                    
                # Find all rotated files
                pattern = re.compile(rf'{re.escape(base)}\.log\.(\d{{4}}-\d{{2}}-\d{{2}})$')
                cutoff = time.time() - (self.compression_delay_days * 24 * 3600)
                
                for file in os.listdir(os.path.dirname(base)):
                    match = pattern.match(file)
                    if match:
                        file_path = os.path.join(os.path.dirname(base), file)
                        if os.path.getmtime(file_path) < cutoff:
                            gz_file = f"{file_path}.gz"
                            if not os.path.exists(gz_file):
                                self._compress_file(file_path)
                                
            except Exception as e:
                sys.stderr.write(f"Compression error: {e}\n")
                
    def _compress_file(self, file_path: str) -> None:
        """Compress a file using gzip."""
        try:
            with open(file_path, 'rb') as f_in:
                with gzip.open(f"{file_path}.gz", 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            os.remove(file_path)
        except Exception as e:
            sys.stderr.write(f"Failed to compress {file_path}: {e}\n")
            
    def close(self) -> None:
        """Close handler and stop compression thread."""
        self._compression_running = False
        self._compression_thread.join(timeout=5.0)
        super().close()


class CloudArchiveHandler(logging.Handler):
    """
    Cloud archive handler for sending logs to cloud storage.
    Supports S3, GCS, and Azure Blob Storage.
    """
    
    def __init__(
        self,
        config: CloudStorageConfig,
        buffer_size: int = 100,
        flush_interval: float = 60.0
    ):
        super().__init__()
        self.config = config
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.buffer: List[str] = []
        self.last_flush = time.time()
        self._client = None
        
        # Initialize cloud client
        self._init_client()
        
        # Start flush timer
        self._flush_timer = threading.Timer(flush_interval, self._flush)
        self._flush_timer.daemon = True
        self._flush_timer.start()
        
    def _init_client(self) -> None:
        """Initialize cloud storage client."""
        provider = self.config.provider.lower()
        
        if provider == "s3":
            if HAS_BOTO3:
                kwargs = {
                    'region_name': self.config.region,
                    'use_ssl': self.config.use_ssl
                }
                if self.config.access_key and self.config.secret_key:
                    kwargs['aws_access_key_id'] = self.config.access_key
                    kwargs['aws_secret_access_key'] = self.config.secret_key
                if self.config.endpoint_url:
                    kwargs['endpoint_url'] = self.config.endpoint_url
                self._client = boto3.client('s3', **kwargs)
                
        elif provider == "gcs":
            if HAS_GCS:
                self._client = storage.Client()
                
        elif provider == "azure":
            if HAS_AZURE:
                if self.config.access_key:
                    self._client = BlobServiceClient.from_connection_string(
                        self.config.access_key
                    )
                    
    def emit(self, record: logging.LogRecord) -> None:
        """Add log record to buffer."""
        try:
            message = self.format(record)
            self.buffer.append(message)
            
            if len(self.buffer) >= self.buffer_size:
                self._flush()
        except Exception as e:
            self.handleError(record)
            
    def _flush(self) -> None:
        """Flush buffer to cloud storage."""
        if not self.buffer:
            return
            
        try:
            data = '\n'.join(self.buffer)
            timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H")
            key = f"{self.config.prefix}logs-{timestamp}.log"
            
            if self.config.provider.lower() == "s3":
                self._client.put_object(
                    Bucket=self.config.bucket,
                    Key=key,
                    Body=data.encode('utf-8'),
                    ContentType='text/plain'
                )
            elif self.config.provider.lower() == "gcs":
                bucket = self._client.bucket(self.config.bucket)
                blob = bucket.blob(key)
                blob.upload_from_string(data, content_type='text/plain')
            elif self.config.provider.lower() == "azure":
                container = self._client.get_container_client(self.config.bucket)
                container.upload_blob(key, data, overwrite=True)
                
            self.buffer.clear()
            self.last_flush = time.time()
            
        except Exception as e:
            sys.stderr.write(f"Cloud archive error: {e}\n")
            
    def close(self) -> None:
        """Close handler."""
        self._flush()
        if self._flush_timer:
            self._flush_timer.cancel()
        super().close()


# ======================== LOGGER FACTORY ========================

class LoggerFactory:
    """
    Factory class for creating and managing loggers.
    Implements singleton pattern for global logging configuration.
    """
    
    _instance = None
    _initialized = False
    _config: Optional[LoggerConfig] = None
    _loggers: Dict[str, logging.Logger] = {}
    _handlers: Dict[str, logging.Handler] = {}
    _metrics: Optional[Any] = None
    _lock = threading.Lock()
    _startup_time = datetime.utcnow()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(LoggerFactory, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._config = LoggerConfig()
            self._setup_handlers()
            self._setup_metrics()
            self._initialized = True
            
    def configure(self, config: Union[LoggerConfig, Dict[str, Any]]) -> None:
        """
        Configure the logging system.
        
        Args:
            config: LoggerConfig instance or configuration dict
        """
        with self._lock:
            if isinstance(config, dict):
                config = LoggerConfig(**config)
                
            self._config = config
            self._setup_handlers()
            self._setup_metrics()
            
    def _setup_handlers(self) -> None:
        """Setup log handlers based on configuration."""
        # Remove existing handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
            
        # Clear handler cache
        self._handlers.clear()
        
        # Set root level
        log_level = getattr(logging, self._config.level.upper(), logging.INFO)
        logging.root.setLevel(log_level)
        
        # Console handler
        if self._config.console_enabled:
            handler = self._create_console_handler()
            self._handlers['console'] = handler
            logging.root.addHandler(handler)
            
        # File handler
        if self._config.file_enabled:
            handler = self._create_file_handler()
            self._handlers['file'] = handler
            logging.root.addHandler(handler)
            
        # Syslog handler
        if self._config.syslog_enabled:
            handler = self._create_syslog_handler()
            self._handlers['syslog'] = handler
            logging.root.addHandler(handler)
            
        # Sentry handler
        if self._config.sentry_enabled and HAS_SENTRY:
            handler = self._create_sentry_handler()
            self._handlers['sentry'] = handler
            logging.root.addHandler(handler)
            
        # Cloud archive handler
        if self._config.archive_enabled and self._config.archive_cloud:
            handler = self._create_cloud_handler()
            self._handlers['cloud'] = handler
            logging.root.addHandler(handler)
            
        # Add filters
        context_filter = ContextFilter()
        logging.root.addFilter(context_filter)
        
        if self._config.redact_sensitive:
            sensitive_filter = SensitiveDataFilter(
                self._config.sensitive_patterns,
                self._config.redact_replacement,
                self._config.redact_emails,
                self._config.redact_ips,
                self._config.redact_personal_data
            )
            logging.root.addFilter(sensitive_filter)
            
        category_filter = CategoryFilter(
            self._config.enabled_categories,
            self._config.disabled_categories,
            self._config.category_levels
        )
        logging.root.addFilter(category_filter)
        
    def _create_console_handler(self) -> logging.Handler:
        """Create console log handler."""
        handler = logging.StreamHandler(sys.stdout)
        
        # Set level
        level = self._config.console_level or self._config.level
        handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        
        # Set formatter
        if self._config.format == LogFormat.JSON:
            formatter = JsonFormatter()
        elif self._config.format == LogFormat.COLOR or self._config.enable_colors:
            formatter = ColorFormatter()
        else:
            formatter = TextFormatter()
            
        handler.setFormatter(formatter)
        
        if self._config.async_logging:
            handler = AsyncQueueHandler(
                handler,
                self._config.queue_size,
                self._config.drop_on_overflow,
                self._config.worker_threads
            )
            
        return handler
        
    def _create_file_handler(self) -> logging.Handler:
        """Create file log handler with rotation and compression."""
        log_file = Path(self._config.log_dir) / "arbitrage.log"
        
        # Use TimedRotatingFileHandler if rotation_schedule is daily/hourly
        if self._config.rotation_schedule in ['daily', 'hourly']:
            when = 'midnight' if self._config.rotation_schedule == 'daily' else 'H'
            handler = TimedRotatingFileHandlerWithCompression(
                filename=str(log_file),
                when=when,
                interval=1,
                backupCount=self._config.backup_count,
                compress=self._config.compression,
                compression_delay_days=self._config.compression_delay_days
            )
        else:
            handler = RotatingFileHandlerWithCompression(
                filename=str(log_file),
                maxBytes=self._config.max_file_size,
                backupCount=self._config.backup_count,
                compress=self._config.compression,
                compression_delay_days=self._config.compression_delay_days
            )
            
        # Set level
        level = self._config.file_level or self._config.level
        handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        
        # Set formatter
        if self._config.format == LogFormat.JSON:
            formatter = JsonFormatter()
        elif self._config.format == LogFormat.CSV:
            formatter = CSVFormatter()
        else:
            formatter = TextFormatter()
            
        handler.setFormatter(formatter)
        
        if self._config.async_logging:
            handler = AsyncQueueHandler(
                handler,
                self._config.queue_size,
                self._config.drop_on_overflow,
                self._config.worker_threads
            )
            
        return handler
        
    def _create_syslog_handler(self) -> logging.Handler:
        """Create syslog handler."""
        facility = getattr(
            logging.handlers.SysLogHandler,
            self._config.syslog_facility.upper(),
            logging.handlers.SysLogHandler.LOG_LOCAL0
        )
        
        handler = logging.handlers.SysLogHandler(
            address=self._config.syslog_address,
            facility=facility
        )
        
        level = self._config.syslog_level or self._config.level
        handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        
        if self._config.format == LogFormat.SYSLOG:
            formatter = logging.Formatter(
                'nexus-arbitrage[%(process)d]: %(levelname)s | %(category)s | %(message)s'
            )
        else:
            formatter = TextFormatter()
            
        handler.setFormatter(formatter)
        return handler
        
    def _create_sentry_handler(self) -> logging.Handler:
        """Create Sentry handler."""
        if not HAS_SENTRY:
            return logging.NullHandler()
            
        if self._config.sentry_dsn:
            sentry_sdk.init(
                dsn=self._config.sentry_dsn,
                environment=self._config.environment,
                release=self._config.service_version,
                traces_sample_rate=0.1
            )
            
        handler = SentryHandler(level=self._config.sentry_level)
        return handler
        
    def _create_cloud_handler(self) -> logging.Handler:
        """Create cloud archive handler."""
        if not self._config.archive_cloud:
            return logging.NullHandler()
            
        handler = CloudArchiveHandler(self._config.archive_cloud)
        handler.setLevel(logging.INFO)
        
        if self._config.format == LogFormat.JSON:
            formatter = JsonFormatter()
        else:
            formatter = TextFormatter()
            
        handler.setFormatter(formatter)
        return handler
        
    def _setup_metrics(self) -> None:
        """Setup metrics collection for logging."""
        if not self._config.metrics_enabled:
            return
            
        if MetricsCollector:
            labels = {'service': 'nexus-arbitrage-bot', **self._config.metrics_labels}
            self._metrics = MetricsCollector(
                name="nexus_arbitrage_logs",
                labels=labels
            )
            
            # Register metrics
            self._metrics.register_counter("logs_total", "Total log messages")
            self._metrics.register_counter("logs_errors", "Error log messages")
            self._metrics.register_counter("logs_warnings", "Warning log messages")
            self._metrics.register_counter("logs_trade", "Trade log messages")
            self._metrics.register_counter("logs_opportunity", "Opportunity log messages")
            self._metrics.register_counter("logs_performance", "Performance log messages")
            self._metrics.register_counter("logs_security", "Security log messages")
            self._metrics.register_histogram("log_size_bytes", "Log message size in bytes")
            
    def get_logger(
        self,
        name: Optional[str] = None,
        category: Optional[LogCategory] = None,
        **kwargs
    ) -> logging.Logger:
        """
        Get a logger instance with context.
        
        Args:
            name: Logger name
            category: Log category
            **kwargs: Extra context to attach to logger
            
        Returns:
            logging.Logger instance
        """
        if name is None:
            name = self._get_caller_module()
            
        # Check if logger already exists
        if name in self._loggers:
            logger = self._loggers[name]
        else:
            logger = logging.getLogger(name)
            self._loggers[name] = logger
            
        # Set category
        if category:
            logger.category = category.value
            
        # Set extra attributes
        for key, value in kwargs.items():
            setattr(logger, key, value)
            
        return logger
        
    def get_logger_with_context(
        self,
        name: Optional[str] = None,
        category: Optional[LogCategory] = None,
        **context
    ) -> logging.Logger:
        """
        Get a logger with context variables set.
        
        Args:
            name: Logger name
            category: Log category
            **context: Context variables (correlation_id, user_id, request_id, etc.)
            
        Returns:
            logging.Logger instance with context applied
        """
        # Set context variables
        if 'correlation_id' in context:
            set_correlation_id(context['correlation_id'])
        if 'user_id' in context:
            set_user_id(context['user_id'])
        if 'request_id' in context:
            set_request_id(context['request_id'])
        if 'session_id' in context:
            set_session_id(context['session_id'])
        if 'trace_id' in context:
            set_trace_id(context['trace_id'])
        if 'environment' in context:
            set_environment(context['environment'])
            
        return self.get_logger(name, category)
        
    def _get_caller_module(self) -> str:
        """Get the caller's module name."""
        frame = sys._getframe(2)
        return frame.f_globals.get('__name__', 'root')
        
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        if self._metrics:
            return self._metrics.get_metrics()
        return {}
        
    def flush(self) -> None:
        """Flush all async log handlers."""
        for handler in self._handlers.values():
            if hasattr(handler, 'flush'):
                handler.flush()
                
    def close(self) -> None:
        """Close all log handlers."""
        for handler in self._handlers.values():
            if hasattr(handler, 'close'):
                handler.close()
        self._handlers.clear()
        self._loggers.clear()
        
    def get_config(self) -> LoggerConfig:
        """Get current configuration."""
        return self._config


# ======================== LOG DECORATORS ========================

def log_entry_exit(
    logger_name: Optional[str] = None,
    level: str = "DEBUG",
    category: Optional[LogCategory] = None
):
    """
    Decorator to log function entry and exit.
    
    Args:
        logger_name: Name of logger to use
        level: Log level for entry/exit messages
        category: Log category
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            log = get_logger(logger_name or func.__module__, category)
            log_level = getattr(logging, level.upper(), logging.DEBUG)
            
            # Log entry
            log.log(log_level, f"Entering {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                log.log(log_level, f"Exiting {func.__name__} (success)")
                return result
            except Exception as e:
                log.log(log_level, f"Exiting {func.__name__} (error: {e})")
                raise
                
        return wrapper
    return decorator


def log_performance(
    logger_name: Optional[str] = None,
    category: LogCategory = LogCategory.PERFORMANCE
):
    """
    Decorator to log function performance metrics.
    
    Args:
        logger_name: Name of logger to use
        category: Log category
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            log = get_logger(logger_name or func.__module__, category)
            start_time = time.perf_counter()
            
            try:
                result = func(*args, **kwargs)
                duration = (time.perf_counter() - start_time) * 1000
                
                log.info(
                    f"{func.__name__} took {duration:.2f}ms",
                    extra={
                        'duration_ms': duration,
                        'function': func.__name__
                    }
                )
                return result
            except Exception as e:
                duration = (time.perf_counter() - start_time) * 1000
                log.error(
                    f"{func.__name__} failed after {duration:.2f}ms: {e}",
                    extra={
                        'duration_ms': duration,
                        'function': func.__name__,
                        'error': str(e)
                    }
                )
                raise
                
        return wrapper
    return decorator


def log_error(logger_name: Optional[str] = None, category: Optional[LogCategory] = None):
    """
    Decorator to log and wrap exceptions.
    
    Args:
        logger_name: Name of logger to use
        category: Log category
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            log = get_logger(logger_name or func.__module__, category)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log.error(f"Error in {func.__name__}: {e}", exc_info=True)
                raise
        return wrapper
    return decorator


def log_async(logger_name: Optional[str] = None, category: Optional[LogCategory] = None):
    """
    Decorator for async functions to log execution.
    
    Args:
        logger_name: Name of logger to use
        category: Log category
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            log = get_logger(logger_name or func.__module__, category)
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                log.error(f"Error in {func.__name__}: {e}", exc_info=True)
                raise
        return wrapper
    return decorator


# ======================== ASYNC LOGGER ========================

class AsyncLogger:
    """
    Async logger for use in async contexts.
    Provides non-blocking logging for async applications.
    """
    
    def __init__(self, logger: logging.Logger):
        self._logger = logger
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._running = False
        
    async def start(self) -> None:
        """Start the async logger worker."""
        if self._task is None:
            self._running = True
            self._task = asyncio.create_task(self._worker())
            
    async def stop(self) -> None:
        """Stop the async logger worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            
    async def _worker(self) -> None:
        """Worker to process log records asynchronously."""
        while self._running:
            try:
                record = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                if record is None:
                    break
                self._logger.handle(record)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                sys.stderr.write(f"Async logger error: {e}\n")
                
    def _log(self, level: int, msg: str, *args, **kwargs) -> None:
        """Queue a log record."""
        extra = kwargs.get('extra', {})
        record = self._logger.makeRecord(
            self._logger.name,
            level,
            "(unknown)",
            0,
            msg,
            args,
            None,
            func="",
            extra=extra
        )
        asyncio.create_task(self._queue.put(record))
        
    def debug(self, msg: str, *args, **kwargs) -> None:
        self._log(logging.DEBUG, msg, *args, **kwargs)
        
    def info(self, msg: str, *args, **kwargs) -> None:
        self._log(logging.INFO, msg, *args, **kwargs)
        
    def warning(self, msg: str, *args, **kwargs) -> None:
        self._log(logging.WARNING, msg, *args, **kwargs)
        
    def error(self, msg: str, *args, **kwargs) -> None:
        self._log(logging.ERROR, msg, *args, **kwargs)
        
    def critical(self, msg: str, *args, **kwargs) -> None:
        self._log(logging.CRITICAL, msg, *args, **kwargs)
        
    def trade(self, msg: str, *args, **kwargs) -> None:
        """Log trade message."""
        kwargs['extra'] = kwargs.get('extra', {})
        kwargs['extra']['category'] = 'trade'
        self._log(logging.INFO, msg, *args, **kwargs)
        
    def opportunity(self, msg: str, *args, **kwargs) -> None:
        """Log opportunity message."""
        kwargs['extra'] = kwargs.get('extra', {})
        kwargs['extra']['category'] = 'opportunity'
        self._log(logging.INFO, msg, *args, **kwargs)
        
    def performance(self, msg: str, *args, **kwargs) -> None:
        """Log performance message."""
        kwargs['extra'] = kwargs.get('extra', {})
        kwargs['extra']['category'] = 'performance'
        self._log(logging.INFO, msg, *args, **kwargs)


# ======================== TRADE LOGGING ========================

@dataclass
class TradeLog:
    """Structure for trade log entries."""
    trade_id: str
    strategy: str
    exchange_buy: str
    exchange_sell: str
    symbol: str
    side: str
    quantity: float
    price: float
    value: float
    fee: float
    profit: float
    pnl: float
    status: str
    duration: float
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
        
    def to_log(self) -> str:
        """Convert to log string."""
        return (
            f"TRADE: {self.trade_id} | {self.strategy} | {self.exchange_buy}->{self.exchange_sell} | "
            f"{self.symbol} | {self.side} | {self.quantity:.6f} | {self.price:.6f} | "
            f"{self.pnl:.2f} | {self.status} | {self.duration:.2f}s"
        )


@dataclass
class OpportunityLog:
    """Structure for opportunity log entries."""
    opportunity_id: str
    strategy: str
    exchange_buy: str
    exchange_sell: str
    symbol: str
    bid_price: float
    ask_price: float
    spread: float
    profit_percent: float
    volume: float
    estimated_profit: float
    confidence: float
    status: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
        
    def to_log(self) -> str:
        """Convert to log string."""
        return (
            f"OPPORTUNITY: {self.opportunity_id} | {self.strategy} | "
            f"{self.exchange_buy}->{self.exchange_sell} | {self.symbol} | "
            f"Profit: {self.profit_percent:.2f}% | Confidence: {self.confidence:.1f}%"
        )


@dataclass
class PerformanceLog:
    """Structure for performance log entries."""
    metric_category: str
    metric_name: str
    value: float
    unit: str
    details: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
        
    def to_log(self) -> str:
        """Convert to log string."""
        return (
            f"PERFORMANCE: {self.metric_category} | {self.metric_name} | "
            f"{self.value:.2f} {self.unit} | {self.details}"
        )


@dataclass
class AuditLog:
    """Structure for audit log entries."""
    user: str
    action: str
    resource: str
    ip: str = ""
    user_agent: str = ""
    changes: Dict[str, Any] = field(default_factory=dict)
    status: str = "success"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
        
    def to_log(self) -> str:
        """Convert to log string."""
        return (
            f"AUDIT: {self.user} | {self.action} | {self.resource} | "
            f"{self.status} | {self.ip} | {self.user_agent}"
        )


# ======================== CONVENIENCE FUNCTIONS ========================

# Global logger factory
_logger_factory: Optional[LoggerFactory] = None
_async_loggers: Dict[str, AsyncLogger] = {}
_audit_logger: Optional[logging.Logger] = None


def get_logger(
    name: Optional[str] = None,
    category: Optional[LogCategory] = None,
    **kwargs
) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Logger name (defaults to caller's module)
        category: Log category
        **kwargs: Extra context to attach
        
    Returns:
        logging.Logger instance
    """
    global _logger_factory
    
    if _logger_factory is None:
        _logger_factory = LoggerFactory()
        
    if name is None:
        name = _get_caller_module()
        
    return _logger_factory.get_logger(name, category, **kwargs)


def get_async_logger(
    name: Optional[str] = None,
    category: Optional[LogCategory] = None
) -> AsyncLogger:
    """
    Get an async logger instance.
    
    Args:
        name: Logger name
        category: Log category
        
    Returns:
        AsyncLogger instance
    """
    global _async_loggers, _logger_factory
    
    if _logger_factory is None:
        _logger_factory = LoggerFactory()
        
    logger = get_logger(name, category)
    logger_key = logger.name
    
    if logger_key not in _async_loggers:
        _async_loggers[logger_key] = AsyncLogger(logger)
        
    return _async_loggers[logger_key]


def get_audit_logger() -> logging.Logger:
    """Get the audit logger."""
    global _audit_logger, _logger_factory
    
    if _logger_factory is None:
        _logger_factory = LoggerFactory()
        
    if _audit_logger is None:
        _audit_logger = _logger_factory.get_logger(
            "nexus.arbitrage.audit",
            LogCategory.AUDIT
        )
        
    return _audit_logger


def _get_caller_module() -> str:
    """Get the caller's module name."""
    frame = sys._getframe(2)
    return frame.f_globals.get('__name__', 'root')


def configure_logging(config: Union[LoggerConfig, Dict[str, Any]]) -> None:
    """
    Configure the global logging system.
    
    Args:
        config: LoggerConfig instance or configuration dict
    """
    global _logger_factory
    
    if _logger_factory is None:
        _logger_factory = LoggerFactory()
        
    _logger_factory.configure(config)


def init_logging(config: Optional[Union[LoggerConfig, Dict[str, Any]]] = None) -> None:
    """
    Initialize the logging system.
    
    Args:
        config: Optional configuration
    """
    if config is None:
        config = LoggerConfig()
        
    configure_logging(config)
    
    # Log initialization
    logger = get_logger()
    logger.info("=" * 80)
    logger.info(f"NEXUS ARBITRAGE BOT LOGGING SYSTEM v{config.service_version}")
    logger.info(f"Started at: {datetime.utcnow().isoformat()}")
    logger.info(f"Environment: {config.environment}")
    logger.info(f"Log directory: {config.log_dir}")
    logger.info(f"Log level: {config.level}")
    logger.info(f"Log format: {config.format.value}")
    logger.info("=" * 80)
    
    # Start async loggers
    if config.async_logging:
        for logger_key in _async_loggers:
            asyncio.create_task(_async_loggers[logger_key].start())


async def shutdown_logging() -> None:
    """Shutdown the logging system gracefully."""
    global _async_loggers
    
    logger = get_logger()
    logger.info("Shutting down logging system...")
    
    # Stop async loggers
    for logger_key, async_logger in list(_async_loggers.items()):
        await async_logger.stop()
    _async_loggers.clear()
    
    # Flush and close handlers
    if _logger_factory:
        _logger_factory.flush()
        _logger_factory.close()
        
    logger.info("Logging system shutdown complete")


def log_trade(trade: TradeLog) -> None:
    """
    Log a trade with structured format.
    
    Args:
        trade: TradeLog instance
    """
    logger = get_logger(category=LogCategory.TRADE)
    logger.info(
        trade.to_log(),
        extra={
            'category': 'trade',
            'trade_data': trade.to_dict(),
            'value': trade.pnl
        }
    )
    
    # Also log to audit if needed
    if _logger_factory and _logger_factory._config.audit_enabled:
        audit_logger = get_audit_logger()
        audit_logger.info(
            f"TRADE: {trade.trade_id} | {trade.strategy} | "
            f"{trade.symbol} | {trade.pnl:.2f} | {trade.status}"
        )


def log_opportunity(opportunity: OpportunityLog) -> None:
    """
    Log an arbitrage opportunity.
    
    Args:
        opportunity: OpportunityLog instance
    """
    logger = get_logger(category=LogCategory.OPPORTUNITY)
    logger.info(
        opportunity.to_log(),
        extra={
            'category': 'opportunity',
            'opportunity_data': opportunity.to_dict(),
            'value': opportunity.estimated_profit
        }
    )


def log_performance_metric(metric: PerformanceLog) -> None:
    """
    Log a performance metric.
    
    Args:
        metric: PerformanceLog instance
    """
    logger = get_logger(category=LogCategory.PERFORMANCE)
    logger.info(
        metric.to_log(),
        extra={
            'category': 'performance',
            'metric_data': metric.to_dict()
        }
    )


def log_system_event(event: str, level: str = "INFO", **kwargs) -> None:
    """
    Log a system event.
    
    Args:
        event: Event description
        level: Log level
        **kwargs: Additional key-value pairs to log
    """
    logger = get_logger(category=LogCategory.SYSTEM)
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    extra = {'category': 'system'}
    extra.update(kwargs)
    
    logger.log(log_level, f"SYSTEM: {event}", extra=extra)


def log_security_event(event: str, level: str = "WARNING", **kwargs) -> None:
    """
    Log a security event.
    
    Args:
        event: Event description
        level: Log level
        **kwargs: Additional key-value pairs to log
    """
    logger = get_logger(category=LogCategory.SECURITY)
    log_level = getattr(logging, level.upper(), logging.WARNING)
    
    extra = {'category': 'security'}
    extra.update(kwargs)
    
    logger.log(log_level, f"SECURITY: {event}", extra=extra)


def log_audit_event(audit: AuditLog) -> None:
    """
    Log an audit event.
    
    Args:
        audit: AuditLog instance
    """
    logger = get_audit_logger()
    logger.info(
        audit.to_log(),
        extra={
            'category': 'audit',
            'audit_data': audit.to_dict()
        }
    )


def log_compliance_event(event: str, **kwargs) -> None:
    """
    Log a compliance event.
    
    Args:
        event: Event description
        **kwargs: Additional key-value pairs
    """
    logger = get_logger(category=LogCategory.COMPLIANCE)
    extra = {'category': 'compliance'}
    extra.update(kwargs)
    logger.info(f"COMPLIANCE: {event}", extra=extra)


# ======================== EXPORTS ========================

__all__ = [
    # Enums
    'LogLevel',
    'LogCategory',
    'LogFormat',
    'LogStorage',
    
    # Configuration
    'LoggerConfig',
    'CloudStorageConfig',
    
    # Context
    'LogContext',
    'set_correlation_id',
    'get_correlation_id',
    'generate_correlation_id',
    'set_user_id',
    'get_user_id',
    'set_request_id',
    'get_request_id',
    'set_session_id',
    'get_session_id',
    'set_trace_id',
    'get_trace_id',
    'set_span_id',
    'get_span_id',
    'set_environment',
    'get_environment',
    
    # Formatters
    'TextFormatter',
    'ColorFormatter',
    'JsonFormatter',
    'GELFFormatter',
    'CSVFormatter',
    
    # Handlers
    'AsyncQueueHandler',
    'RotatingFileHandlerWithCompression',
    'TimedRotatingFileHandlerWithCompression',
    'CloudArchiveHandler',
    
    # Filters
    'ContextFilter',
    'SensitiveDataFilter',
    'CategoryFilter',
    'LevelFilter',
    
    # Factory
    'LoggerFactory',
    
    # Async
    'AsyncLogger',
    
    # Data structures
    'TradeLog',
    'OpportunityLog',
    'PerformanceLog',
    'AuditLog',
    
    # Main functions
    'get_logger',
    'get_async_logger',
    'get_audit_logger',
    'configure_logging',
    'init_logging',
    'shutdown_logging',
    
    # Logging functions
    'log_trade',
    'log_opportunity',
    'log_performance_metric',
    'log_system_event',
    'log_security_event',
    'log_audit_event',
    'log_compliance_event',
    
    # Decorators
    'log_entry_exit',
    'log_performance',
    'log_error',
    'log_async',
]

# ======================== INITIALIZATION ========================

# Initialize default logging if not already configured
if _logger_factory is None:
    _logger_factory = LoggerFactory()

# Create default logger for this module
logger = get_logger(__name__)
logger.debug("Logging module initialized")

# ====================================================================================
# END OF LOGGING MODULE
# ====================================================================================
