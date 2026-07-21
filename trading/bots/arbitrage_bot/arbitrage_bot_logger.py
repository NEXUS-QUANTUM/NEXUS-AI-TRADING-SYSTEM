"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Logger
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Système de logging avancé pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import logging
import logging.handlers
import sys
import os
import json
import time
import uuid
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple, Callable
from enum import Enum
from dataclasses import dataclass, field
import threading
import queue
import socket
import requests
import re
import colorama
from colorama import Fore, Back, Style, init as colorama_init

# ============================================================
# LOGGING CONFIGURATION
# ============================================================
colorama_init()

# ============================================================
# ENUMS
# ============================================================

class LogLevel(Enum):
    """Niveaux de log"""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    TRACE = 5
    SUCCESS = 25

class LogFormat(Enum):
    """Formats de log"""
    TEXT = "text"
    JSON = "json"
    COLOR = "color"
    MINIMAL = "minimal"
    VERBOSE = "verbose"

class LogCategory(Enum):
    """Catégories de log"""
    SYSTEM = "system"
    TRADING = "trading"
    RISK = "risk"
    EXCHANGE = "exchange"
    STRATEGY = "strategy"
    EXECUTION = "execution"
    MARKET_DATA = "market_data"
    NOTIFICATION = "notification"
    API = "api"
    WEBSOCKET = "websocket"
    DATABASE = "database"
    CACHE = "cache"
    PERFORMANCE = "performance"
    SECURITY = "security"
    COMPLIANCE = "compliance"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class LogEntry:
    """Entrée de log"""
    timestamp: datetime
    level: LogLevel
    category: LogCategory
    message: str
    module: str
    function: str
    line: int
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    exception: Optional[Exception] = None
    stack_trace: Optional[str] = None

@dataclass
class LogConfig:
    """Configuration de logging"""
    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.TEXT
    console_enabled: bool = True
    console_color: bool = True
    file_enabled: bool = True
    file_path: Path = Path("logs/arbitrage.log")
    file_max_size: int = 10485760  # 10MB
    file_backup_count: int = 10
    json_enabled: bool = False
    json_path: Path = Path("logs/arbitrage.json")
    syslog_enabled: bool = False
    syslog_host: str = "localhost"
    syslog_port: int = 514
    elasticsearch_enabled: bool = False
    elasticsearch_host: str = "localhost"
    elasticsearch_port: int = 9200
    elasticsearch_index: str = "nexus-arbitrage"
    buffer_size: int = 100
    flush_interval: int = 5
    propagate: bool = False

# ============================================================
# LOGGER
# ============================================================

class ArbitrageBotLogger:
    """
    Système de logging avancé pour le bot d'arbitrage
    
    Supporte plusieurs sorties, formats, niveaux de log,
    et enrichissement des logs avec contexte
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        config: Optional[Union[LogConfig, Dict[str, Any]]] = None,
        name: str = "arbitrage_bot"
    ):
        """
        Initialise le logger
        
        Args:
            config: Configuration de logging
            name: Nom du logger
        """
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.name = name
        self.config = self._parse_config(config)
        self._initialized = True
        
        # Logger
        self._logger = logging.getLogger(name)
        self._logger.setLevel(self.config.level.value)
        self._logger.propagate = self.config.propagate
        
        # Handlers
        self._handlers: List[logging.Handler] = []
        self._setup_handlers()
        
        # Buffer
        self._buffer: List[LogEntry] = []
        self._buffer_lock = threading.Lock()
        self._flush_thread = None
        self._flush_event = threading.Event()
        self._running = True
        
        # Start flush thread
        self._start_flush_thread()
        
        # Context
        self._context: Dict[str, Any] = {}
        self._context_lock = threading.Lock()
        
        # Stats
        self.stats = {
            'total_logs': 0,
            'by_level': {},
            'by_category': {},
            'errors': 0,
            'warnings': 0,
        }
        
        # Initialize
        self.info("Logger initialized", category=LogCategory.SYSTEM)
        
        # Set as global logger
        logging.setLoggerClass(ArbitrageBotLogger)
    
    def _parse_config(self, config: Optional[Union[LogConfig, Dict[str, Any]]]) -> LogConfig:
        """Parse la configuration"""
        if config is None:
            return LogConfig()
        
        if isinstance(config, LogConfig):
            return config
        
        if isinstance(config, dict):
            return LogConfig(**config)
        
        return LogConfig()
    
    def _setup_handlers(self):
        """Configure les handlers"""
        # Console handler
        if self.config.console_enabled:
            console_handler = self._create_console_handler()
            self._logger.addHandler(console_handler)
            self._handlers.append(console_handler)
        
        # File handler
        if self.config.file_enabled:
            file_handler = self._create_file_handler()
            self._logger.addHandler(file_handler)
            self._handlers.append(file_handler)
        
        # JSON file handler
        if self.config.json_enabled:
            json_handler = self._create_json_handler()
            self._logger.addHandler(json_handler)
            self._handlers.append(json_handler)
        
        # Syslog handler
        if self.config.syslog_enabled:
            syslog_handler = self._create_syslog_handler()
            self._logger.addHandler(syslog_handler)
            self._handlers.append(syslog_handler)
        
        # Elasticsearch handler
        if self.config.elasticsearch_enabled:
            es_handler = self._create_elasticsearch_handler()
            self._logger.addHandler(es_handler)
            self._handlers.append(es_handler)
    
    def _create_console_handler(self) -> logging.Handler:
        """Crée un handler console"""
        handler = logging.StreamHandler(sys.stdout)
        
        if self.config.console_color:
            formatter = self._create_color_formatter()
        else:
            formatter = self._create_formatter()
        
        handler.setFormatter(formatter)
        handler.setLevel(self.config.level.value)
        return handler
    
    def _create_file_handler(self) -> logging.Handler:
        """Crée un handler fichier"""
        # Créer le répertoire
        self.config.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        handler = logging.handlers.RotatingFileHandler(
            filename=self.config.file_path,
            maxBytes=self.config.file_max_size,
            backupCount=self.config.file_backup_count,
            encoding='utf-8'
        )
        
        formatter = self._create_formatter()
        handler.setFormatter(formatter)
        handler.setLevel(self.config.level.value)
        return handler
    
    def _create_json_handler(self) -> logging.Handler:
        """Crée un handler JSON"""
        self.config.json_path.parent.mkdir(parents=True, exist_ok=True)
        
        handler = logging.handlers.RotatingFileHandler(
            filename=self.config.json_path,
            maxBytes=self.config.file_max_size,
            backupCount=self.config.file_backup_count,
            encoding='utf-8'
        )
        
        formatter = self._create_json_formatter()
        handler.setFormatter(formatter)
        handler.setLevel(self.config.level.value)
        return handler
    
    def _create_syslog_handler(self) -> logging.Handler:
        """Crée un handler syslog"""
        handler = logging.handlers.SysLogHandler(
            address=(self.config.syslog_host, self.config.syslog_port)
        )
        
        formatter = self._create_formatter()
        handler.setFormatter(formatter)
        handler.setLevel(self.config.level.value)
        return handler
    
    def _create_elasticsearch_handler(self) -> logging.Handler:
        """Crée un handler Elasticsearch"""
        # Implémentation simplifiée
        # En production, utiliser la librairie elasticsearch
        class ElasticsearchHandler(logging.Handler):
            def __init__(self, host, port, index):
                super().__init__()
                self.host = host
                self.port = port
                self.index = index
            
            def emit(self, record):
                try:
                    # Envoyer à Elasticsearch
                    pass
                except Exception:
                    pass
        
        handler = ElasticsearchHandler(
            self.config.elasticsearch_host,
            self.config.elasticsearch_port,
            self.config.elasticsearch_index
        )
        
        formatter = self._create_json_formatter()
        handler.setFormatter(formatter)
        handler.setLevel(self.config.level.value)
        return handler
    
    def _create_formatter(self) -> logging.Formatter:
        """Crée un formatter"""
        format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        return logging.Formatter(format_str)
    
    def _create_color_formatter(self) -> logging.Formatter:
        """Crée un formatter coloré"""
        class ColorFormatter(logging.Formatter):
            COLORS = {
                'TRACE': Fore.CYAN,
                'DEBUG': Fore.BLUE,
                'INFO': Fore.GREEN,
                'SUCCESS': Fore.GREEN + Style.BRIGHT,
                'WARNING': Fore.YELLOW,
                'ERROR': Fore.RED,
                'CRITICAL': Fore.RED + Style.BRIGHT,
            }
            
            def format(self, record):
                levelname = record.levelname
                color = self.COLORS.get(levelname, Fore.WHITE)
                
                record.levelname = f"{color}{levelname}{Style.RESET_ALL}"
                record.asctime = f"{Fore.MAGENTA}{record.asctime}{Style.RESET_ALL}"
                record.name = f"{Fore.CYAN}{record.name}{Style.RESET_ALL}"
                
                return super().format(record)
        
        format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        return ColorFormatter(format_str)
    
    def _create_json_formatter(self) -> logging.Formatter:
        """Crée un formatter JSON"""
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                    'level': record.levelname,
                    'name': record.name,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno,
                    'thread': record.threadName,
                    'process': record.processName,
                }
                
                if hasattr(record, 'trace_id'):
                    log_data['trace_id'] = record.trace_id
                
                if hasattr(record, 'category'):
                    log_data['category'] = record.category
                
                if record.exc_info:
                    log_data['exception'] = {
                        'type': record.exc_info[0].__name__,
                        'message': str(record.exc_info[1]),
                        'traceback': traceback.format_exc(),
                    }
                
                if hasattr(record, 'details'):
                    log_data['details'] = record.details
                
                return json.dumps(log_data)
        
        return JSONFormatter()
    
    # ============================================================
    # FLUSH THREAD
    # ============================================================
    
    def _start_flush_thread(self):
        """Démarre le thread de vidage"""
        def flush_loop():
            while self._running:
                self._flush_event.wait(self.config.flush_interval)
                self._flush()
        
        self._flush_thread = threading.Thread(target=flush_loop, daemon=True)
        self._flush_thread.start()
    
    def _flush(self):
        """Vide le buffer"""
        with self._buffer_lock:
            if not self._buffer:
                return
            
            entries = self._buffer
            self._buffer = []
        
        for entry in entries:
            self._log_entry(entry)
    
    def _log_entry(self, entry: LogEntry):
        """
        Log une entrée
        
        Args:
            entry: Entrée à logger
        """
        record = logging.LogRecord(
            name=self.name,
            level=entry.level.value,
            pathname='',
            lineno=entry.line,
            msg=entry.message,
            args=(),
            exc_info=None
        )
        
        record.category = entry.category.value
        record.trace_id = entry.trace_id
        record.span_id = entry.span_id
        record.user_id = entry.user_id
        record.session_id = entry.session_id
        record.request_id = entry.request_id
        record.details = entry.details
        
        if entry.exception:
            record.exc_info = (type(entry.exception), entry.exception, entry.exception.__traceback__)
        
        self._logger.handle(record)
        
        # Mettre à jour les stats
        self.stats['total_logs'] += 1
        level_name = entry.level.name
        self.stats['by_level'][level_name] = self.stats['by_level'].get(level_name, 0) + 1
        
        category_name = entry.category.value
        self.stats['by_category'][category_name] = self.stats['by_category'].get(category_name, 0) + 1
        
        if entry.level == LogLevel.ERROR or entry.level == LogLevel.CRITICAL:
            self.stats['errors'] += 1
        elif entry.level == LogLevel.WARNING:
            self.stats['warnings'] += 1
    
    # ============================================================
    # LOGGING METHODS
    # ============================================================
    
    def _log(
        self,
        level: LogLevel,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        module: Optional[str] = None,
        function: Optional[str] = None,
        line: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
        **kwargs
    ):
        """
        Log un message
        
        Args:
            level: Niveau de log
            message: Message
            category: Catégorie
            module: Module
            function: Fonction
            line: Ligne
            details: Détails supplémentaires
            exception: Exception
            **kwargs: Arguments supplémentaires
        """
        # Récupérer le contexte d'appel
        if module is None or function is None or line is None:
            frame = sys._getframe(2)
            module = module or frame.f_globals.get('__name__', '')
            function = function or frame.f_code.co_name
            line = line or frame.f_lineno
        
        # Créer l'entrée
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            category=category,
            message=message,
            module=module,
            function=function,
            line=line,
            trace_id=kwargs.get('trace_id', self._context.get('trace_id')),
            span_id=kwargs.get('span_id', self._context.get('span_id')),
            user_id=kwargs.get('user_id', self._context.get('user_id')),
            session_id=kwargs.get('session_id', self._context.get('session_id')),
            request_id=kwargs.get('request_id', self._context.get('request_id')),
            details=details or kwargs.get('details', {}),
            exception=exception,
            stack_trace=traceback.format_exc() if exception else None,
        )
        
        # Ajouter au buffer
        with self._buffer_lock:
            self._buffer.append(entry)
            if len(self._buffer) >= self.config.buffer_size:
                self._flush_event.set()
    
    def trace(self, message: str, category: LogCategory = LogCategory.SYSTEM, **kwargs):
        """Log un message de trace"""
        self._log(LogLevel.TRACE, message, category, **kwargs)
    
    def debug(self, message: str, category: LogCategory = LogCategory.SYSTEM, **kwargs):
        """Log un message de debug"""
        self._log(LogLevel.DEBUG, message, category, **kwargs)
    
    def info(self, message: str, category: LogCategory = LogCategory.SYSTEM, **kwargs):
        """Log un message d'information"""
        self._log(LogLevel.INFO, message, category, **kwargs)
    
    def success(self, message: str, category: LogCategory = LogCategory.SYSTEM, **kwargs):
        """Log un message de succès"""
        self._log(LogLevel.SUCCESS, message, category, **kwargs)
    
    def warning(self, message: str, category: LogCategory = LogCategory.SYSTEM, **kwargs):
        """Log un message d'avertissement"""
        self._log(LogLevel.WARNING, message, category, **kwargs)
    
    def error(self, message: str, category: LogCategory = LogCategory.SYSTEM, **kwargs):
        """Log un message d'erreur"""
        self._log(LogLevel.ERROR, message, category, **kwargs)
    
    def critical(self, message: str, category: LogCategory = LogCategory.SYSTEM, **kwargs):
        """Log un message critique"""
        self._log(LogLevel.CRITICAL, message, category, **kwargs)
    
    def exception(self, message: str, exception: Exception, category: LogCategory = LogCategory.SYSTEM, **kwargs):
        """Log une exception"""
        self._log(LogLevel.ERROR, message, category, exception=exception, **kwargs)
    
    # ============================================================
    # CONTEXT MANAGEMENT
    # ============================================================
    
    def set_context(self, **kwargs):
        """
        Définit le contexte
        
        Args:
            **kwargs: Contexte à définir
        """
        with self._context_lock:
            self._context.update(kwargs)
    
    def clear_context(self):
        """Efface le contexte"""
        with self._context_lock:
            self._context.clear()
    
    def get_context(self) -> Dict[str, Any]:
        """
        Récupère le contexte
        
        Returns:
            Dict[str, Any]: Contexte
        """
        with self._context_lock:
            return self._context.copy()
    
    def context(self, **kwargs):
        """
        Context manager pour le contexte
        
        Args:
            **kwargs: Contexte à ajouter
        
        Yields:
            None
        """
        old_context = self.get_context()
        self.set_context(**kwargs)
        try:
            yield
        finally:
            with self._context_lock:
                self._context.clear()
                self._context.update(old_context)
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        return {
            'total_logs': self.stats['total_logs'],
            'by_level': self.stats['by_level'],
            'by_category': self.stats['by_category'],
            'errors': self.stats['errors'],
            'warnings': self.stats['warnings'],
            'buffer_size': len(self._buffer),
            'handlers': len(self._handlers),
        }
    
    # ============================================================
    # CLEANUP
    # ============================================================
    
    def close(self):
        """Ferme le logger"""
        self._running = False
        self._flush_event.set()
        
        if self._flush_thread:
            self._flush_thread.join(timeout=5)
        
        self._flush()
        
        for handler in self._handlers:
            handler.close()
        
        self._handlers.clear()
        self._logger.handlers.clear()
        
        logging.shutdown()

# ============================================================
# GLOBAL LOGGER INSTANCE
# ============================================================

_default_logger: Optional[ArbitrageBotLogger] = None

def get_logger(
    config: Optional[Union[LogConfig, Dict[str, Any]]] = None,
    name: str = "arbitrage_bot"
) -> ArbitrageBotLogger:
    """
    Récupère le logger global
    
    Args:
        config: Configuration de logging
        name: Nom du logger
        
    Returns:
        ArbitrageBotLogger: Logger global
    """
    global _default_logger
    if _default_logger is None:
        _default_logger = ArbitrageBotLogger(config, name)
    return _default_logger

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'LogLevel',
    'LogFormat',
    'LogCategory',
    'LogEntry',
    'LogConfig',
    'ArbitrageBotLogger',
    'get_logger',
]

# ============================================================
# INITIALIZATION
# ============================================================

# Créer le logger par défaut
logger = get_logger()

# Ajouter les fonctions de logging au niveau du module
def trace(msg, *args, **kwargs):
    logger.trace(msg, *args, **kwargs)

def debug(msg, *args, **kwargs):
    logger.debug(msg, *args, **kwargs)

def info(msg, *args, **kwargs):
    logger.info(msg, *args, **kwargs)

def success(msg, *args, **kwargs):
    logger.success(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    logger.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    logger.error(msg, *args, **kwargs)

def critical(msg, *args, **kwargs):
    logger.critical(msg, *args, **kwargs)

def exception(msg, exc, *args, **kwargs):
    logger.exception(msg, exc, *args, **kwargs)

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    # Test du logger
    logger = get_logger()
    
    logger.info("This is an info message")
    logger.success("This is a success message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    try:
        raise ValueError("Test exception")
    except Exception as e:
        logger.exception("Exception caught", e)
    
    with logger.context(user_id="user123", session_id="session456"):
        logger.info("Contextualized log message")
    
    print("\nLogger statistics:")
    print(json.dumps(logger.get_stats(), indent=2))
    
    logger.close()
