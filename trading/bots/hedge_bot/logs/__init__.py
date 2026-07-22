# trading/bots/hedge_bot/logs/__init__.py

"""
NEXUS HEDGE BOT - LOGS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Comprehensive logging system for the hedge bot with structured logging,
log rotation, archiving, and real-time monitoring capabilities.

Version: 3.0.0
"""

import json
import logging
import logging.handlers
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union
from uuid import uuid4

import structlog
from structlog.processors import JSONRenderer, TimeStamper, StackInfoRenderer, format_exc_info
from structlog.stdlib import LoggerFactory, BoundLogger, add_log_level

from .archive import ArchiveManager, create_archive_manager
from .reports import ReportManager, ReportConfig

# === LOGGING CONFIGURATION ===

class LoggingConfig:
    """Configuration for the logging system."""
    
    def __init__(
        self,
        log_dir: str = "logs",
        log_level: str = "INFO",
        json_logging: bool = True,
        console_logging: bool = True,
        file_logging: bool = True,
        max_file_size_mb: int = 100,
        backup_count: int = 10,
        archive_enabled: bool = True,
        archive_retention_days: int = 90,
        report_enabled: bool = True,
        log_format: str = "detailed",
    ):
        self.log_dir = Path(log_dir)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.json_logging = json_logging
        self.console_logging = console_logging
        self.file_logging = file_logging
        self.max_file_size_mb = max_file_size_mb
        self.backup_count = backup_count
        self.archive_enabled = archive_enabled
        self.archive_retention_days = archive_retention_days
        self.report_enabled = report_enabled
        self.log_format = log_format
        
        # Create log directories
        self._create_directories()
    
    def _create_directories(self) -> None:
        """Create all necessary log directories."""
        directories = [
            self.log_dir,
            self.log_dir / "archive",
            self.log_dir / "reports",
            self.log_dir / "templates",
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


# === STRUCTURED LOGGING SETUP ===

def setup_structlog(config: LoggingConfig) -> BoundLogger:
    """
    Set up structured logging with structlog.
    
    Args:
        config: Logging configuration
        
    Returns:
        Configured structlog logger
    """
    # Remove existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Configure logging
    logging.basicConfig(
        level=config.log_level,
        format="%(message)s",
        handlers=[],
    )
    
    # Set up processors
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if config.json_logging:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Set up handlers
    handlers = []
    
    if config.console_logging:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(config.log_level)
        handlers.append(console_handler)
    
    if config.file_logging:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=config.log_dir / "nexus_hedge_bot.log",
            maxBytes=config.max_file_size_mb * 1024 * 1024,
            backupCount=config.backup_count,
        )
        file_handler.setLevel(config.log_level)
        handlers.append(file_handler)
        
        # Error handler
        error_handler = logging.handlers.RotatingFileHandler(
            filename=config.log_dir / "errors.log",
            maxBytes=config.max_file_size_mb * 1024 * 1024,
            backupCount=config.backup_count,
        )
        error_handler.setLevel(logging.ERROR)
        handlers.append(error_handler)
    
    # Add handlers to root logger
    for handler in handlers:
        if config.json_logging:
            handler.setFormatter(logging.Formatter(json.dumps({
                "timestamp": "%(asctime)s",
                "level": "%(levelname)s",
                "module": "%(name)s",
                "message": "%(message)s",
            })))
        else:
            handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S.%f",
            ))
        logging.root.addHandler(handler)
    
    return structlog.get_logger()


# === LOGGING UTILITIES ===

class LoggerMixin:
    """Mixin class for adding logging capabilities."""
    
    @property
    def logger(self) -> BoundLogger:
        """Get a logger for the current class."""
        if not hasattr(self, "_logger"):
            self._logger = structlog.get_logger(self.__class__.__name__)
        return self._logger
    
    def log_info(self, message: str, **kwargs) -> None:
        """Log an info message."""
        self.logger.info(message, **kwargs)
    
    def log_warning(self, message: str, **kwargs) -> None:
        """Log a warning message."""
        self.logger.warning(message, **kwargs)
    
    def log_error(self, message: str, exc_info: bool = True, **kwargs) -> None:
        """Log an error message."""
        self.logger.error(message, exc_info=exc_info, **kwargs)
    
    def log_debug(self, message: str, **kwargs) -> None:
        """Log a debug message."""
        self.logger.debug(message, **kwargs)
    
    def log_exception(self, message: str, exception: Exception, **kwargs) -> None:
        """Log an exception with full traceback."""
        self.logger.error(
            message,
            exception=str(exception),
            traceback=traceback.format_exc(),
            **kwargs
        )


class LogContext:
    """Context manager for adding context to logs."""
    
    def __init__(self, **kwargs):
        self.context = kwargs
        self._previous_context = None
    
    def __enter__(self):
        self._previous_context = structlog.contextvars.get_contextvars()
        for key, value in self.context.items():
            structlog.contextvars.bind_contextvars(**{key: value})
        return self
    
    def __exit__(self, *args):
        structlog.contextvars.reset_contextvars(self._previous_context)


def log_execution_time(func):
    """Decorator to log function execution time."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = (time.time() - start_time) * 1000
            logger = structlog.get_logger(func.__module__)
            logger.info(
                f"{func.__name__} completed",
                duration_ms=round(duration, 2),
                success=True,
            )
            return result
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger = structlog.get_logger(func.__module__)
            logger.error(
                f"{func.__name__} failed",
                duration_ms=round(duration, 2),
                exception=str(e),
                exc_info=True,
            )
            raise
    return wrapper


def log_async_execution_time(func):
    """Decorator to log async function execution time."""
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = (time.time() - start_time) * 1000
            logger = structlog.get_logger(func.__module__)
            logger.info(
                f"{func.__name__} completed",
                duration_ms=round(duration, 2),
                success=True,
            )
            return result
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger = structlog.get_logger(func.__module__)
            logger.error(
                f"{func.__name__} failed",
                duration_ms=round(duration, 2),
                exception=str(e),
                exc_info=True,
            )
            raise
    return wrapper


# === LOG ROTATION AND ARCHIVAL ===

class LogManager:
    """
    Centralized log manager for the hedge bot.
    """
    
    def __init__(
        self,
        config: Optional[LoggingConfig] = None,
    ):
        """
        Initialize the log manager.
        
        Args:
            config: Logging configuration
        """
        self.config = config or LoggingConfig()
        self.logger = setup_structlog(self.config)
        
        # Initialize archive manager
        self.archive_manager = None
        if self.config.archive_enabled:
            self.archive_manager = create_archive_manager(
                root_dir=str(self.config.log_dir / "archive"),
                compression="gzip",
                encryption="none",
                retention_days=self.config.archive_retention_days,
                max_size_gb=10.0,
            )
        
        # Initialize report manager
        self.report_manager = None
        if self.config.report_enabled:
            report_config = ReportConfig(
                reports_dir=str(self.config.log_dir / "reports"),
                default_format="html",
                retention_days=self.config.archive_retention_days,
            )
            self.report_manager = ReportManager(report_config)
        
        self._initialized = True
        self.logger.info(
            "log_manager_initialized",
            log_dir=str(self.config.log_dir),
            log_level=logging.getLevelName(self.config.log_level),
            json_logging=self.config.json_logging,
            archive_enabled=self.config.archive_enabled,
            report_enabled=self.config.report_enabled,
        )
    
    def get_logger(self, name: Optional[str] = None) -> BoundLogger:
        """Get a logger instance."""
        if name:
            return structlog.get_logger(name)
        return self.logger
    
    def archive_logs(self) -> Dict[str, Any]:
        """Archive current logs."""
        if not self.archive_manager:
            self.logger.warning("archive_manager_not_enabled")
            return {"status": "disabled"}
        
        try:
            # Archive each log file
            results = {}
            for log_file in self.config.log_dir.glob("*.log"):
                if log_file.name in ["errors.log", "nexus_hedge_bot.log"]:
                    try:
                        metadata = self.archive_manager.archive_file(
                            log_file,
                            tags=["hedge_bot", "logs", "archive"],
                            extra_metadata={"source": "LogManager"},
                        )
                        results[log_file.name] = {
                            "status": "archived",
                            "archive_id": metadata.archive_id,
                            "size_bytes": metadata.size_bytes,
                        }
                    except Exception as e:
                        results[log_file.name] = {"status": "failed", "error": str(e)}
            
            self.logger.info("log_archival_complete", results=results)
            return results
        except Exception as e:
            self.logger.error("log_archival_failed", exception=str(e))
            return {"status": "failed", "error": str(e)}
    
    def generate_report(
        self,
        report_type: str = "daily",
        output_format: str = "html",
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a log report.
        
        Args:
            report_type: Type of report to generate
            output_format: Output format
            period_start: Start of reporting period
            period_end: End of reporting period
            
        Returns:
            Report metadata or None if report manager not enabled
        """
        if not self.report_manager:
            self.logger.warning("report_manager_not_enabled")
            return None
        
        try:
            # Collect log data
            log_data = self._collect_log_data(period_start, period_end)
            
            # Generate report
            metadata = self.report_manager.generate_performance_report(
                trades=log_data.get("trades", []),
                period_start=period_start,
                period_end=period_end,
                title=f"Hedge Bot {report_type.capitalize()} Report",
                tags=["logs", report_type],
            )
            
            return metadata.to_dict() if metadata else None
        except Exception as e:
            self.logger.error("report_generation_failed", exception=str(e))
            return None
    
    def _collect_log_data(
        self,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Collect log data for reporting."""
        # This would parse log files and extract structured data
        # For now, return sample data
        return {
            "trades": [],
            "positions": [],
            "risks": [],
            "performance": {},
        }
    
    def cleanup(self) -> None:
        """Clean up old logs and archives."""
        if self.archive_manager:
            self.archive_manager.apply_retention_policy()
        
        if self.report_manager:
            self.report_manager._apply_retention_policy()
        
        self.logger.info("log_cleanup_complete")
    
    def close(self) -> None:
        """Close the log manager."""
        if self.archive_manager:
            self.archive_manager.close()
        
        if self.report_manager:
            self.report_manager.close()
        
        logging.shutdown()
        self._initialized = False
        self.logger.info("log_manager_closed")


# === MODULE EXPORTS ===

__all__ = [
    # Configuration
    "LoggingConfig",
    "LogManager",
    
    # Logging utilities
    "LoggerMixin",
    "LogContext",
    "log_execution_time",
    "log_async_execution_time",
    
    # Setup
    "setup_structlog",
    "get_logger",
    
    # Archive and reports
    "ArchiveManager",
    "ReportManager",
    "ReportConfig",
    
    # Constants
    "LOG_LEVELS",
]

# === DEFAULT LOGGER ===

_default_logger = None

def get_logger(name: Optional[str] = None) -> BoundLogger:
    """
    Get the default logger or create a new one.
    
    Args:
        name: Optional logger name
        
    Returns:
        BoundLogger instance
    """
    global _default_logger
    if _default_logger is None:
        config = LoggingConfig()
        _default_logger = setup_structlog(config)
    return _default_logger.bind(name=name) if name else _default_logger


# === LOG LEVEL CONSTANTS ===

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# === MODULE INITIALIZATION ===

logger = get_logger(__name__)
logger.info(
    "logs_module_initialized",
    version="3.0.0",
    module="trading.bots.hedge_bot.logs",
    copyright="© 2026 NEXUS QUANTUM LTD",
)

# === SAMPLE LOG FILES ===
# The following log files are created by this module:
# - hedge.log: Main hedge operations
# - hedge.log.1: Rotated hedge log
# - errors.log: Error events
# - performance.log: Performance metrics
# - positions.log: Position changes
# - risk.log: Risk management
# - trades.log: Trade executions
# 
# Directory structure:
# logs/
# ├── archive/           # Compressed log archives
# │   ├── archive.log.*.gz
# │   └── index.db
# ├── reports/           # Generated reports
# │   ├── daily_*.html
# │   ├── weekly_*.html
# │   └── reports.db
# └── templates/         # Report templates
