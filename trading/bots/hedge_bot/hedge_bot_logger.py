# trading/bots/hedge_bot/hedge_bot_logger.py
# Advanced Logging & Audit Trail Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Logger Module - Module avancé de logging et de traçabilité d'audit pour le Hedge Bot.
Gère les logs système, les traces d'audit, la rotation des logs, la journalisation structurée,
et l'intégration avec les systèmes de logging centralisés.
"""

import asyncio
import json
import logging
import logging.handlers
import time
import traceback
import sys
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import threading
import concurrent.futures
import hashlib
import pickle
import zlib
from pathlib import Path
import socket
import platform

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_logger")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class LogLevel(Enum):
    """Niveaux de log."""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    TRACE = 5
    AUDIT = 15


class LogCategory(Enum):
    """Catégories de logs."""
    SYSTEM = "system"
    TRADING = "trading"
    RISK = "risk"
    SECURITY = "security"
    AUDIT = "audit"
    PERFORMANCE = "performance"
    DATA = "data"
    USER = "user"
    INTEGRATION = "integration"


class LogFormat(Enum):
    """Formats de logs."""
    JSON = "json"
    TEXT = "text"
    CSV = "csv"
    SYSLOG = "syslog"
    CUSTOM = "custom"


class LogOutput(Enum):
    """Sorties de logs."""
    FILE = "file"
    CONSOLE = "console"
    SYSLOG = "syslog"
    KAFKA = "kafka"
    ELASTICSEARCH = "elasticsearch"
    DATABASE = "database"
    S3 = "s3"


# ============== DATA MODELS ==============

@dataclass
class LogEntry:
    """Entrée de log."""
    log_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    level: LogLevel = LogLevel.INFO
    category: LogCategory = LogCategory.SYSTEM
    message: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""
    module: str = ""
    function: str = ""
    line: int = 0
    traceback: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: int = 1
    
    def to_dict(self) -> Dict:
        return {
            "log_id": self.log_id,
            "level": self.level.value,
            "level_name": self.level.name,
            "category": self.category.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "module": self.module,
            "function": self.function,
            "line": self.line,
            "traceback": self.traceback,
            "context": self.context,
            "tags": self.tags,
            "correlation_id": self.correlation_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "metadata": self.metadata,
            "version": self.version
        }


@dataclass
class AuditTrail:
    """Traçabilité d'audit."""
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user: str = ""
    action: str = ""
    resource: str = ""
    resource_id: str = ""
    changes: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "success"
    source_ip: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class LogConfig:
    """Configuration de logging."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    level: LogLevel = LogLevel.INFO
    format: LogFormat = LogFormat.JSON
    output: LogOutput = LogOutput.FILE
    file_path: str = "./logs/nexus.log"
    max_size_mb: int = 100
    backup_count: int = 5
    rotation_interval: str = "1d"
    enable_compression: bool = True
    enable_encryption: bool = False
    enable_audit: bool = True
    retention_days: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True


# ============== INTERFACES ==============

class LoggerEngineInterface(ABC):
    """Interface abstraite pour le moteur de logging."""
    
    @abstractmethod
    async def log(self, entry: LogEntry) -> str:
        """Enregistre un log."""
        pass
    
    @abstractmethod
    async def audit(self, trail: AuditTrail) -> str:
        """Enregistre une trace d'audit."""
        pass
    
    @abstractmethod
    async def get_logs(self, filter: Dict[str, Any], limit: int = 100) -> List[LogEntry]:
        """Récupère les logs."""
        pass


# ============== IMPLÉMENTATION ==============

class LoggerEngine(LoggerEngineInterface):
    """
    Moteur de logging avancé pour le Hedge Bot.
    Gère les logs, l'audit et la traçabilité.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.encryption_engine = encryption_engine
        self.config = config or self._default_config()
        
        # Gestion des logs
        self._logs: Dict[str, LogEntry] = {}
        self._logs_lock = threading.RLock()
        
        # Gestion des audits
        self._audits: Dict[str, AuditTrail] = {}
        self._audits_lock = threading.RLock()
        
        # Gestion des configurations
        self._configs: Dict[str, LogConfig] = {}
        self._configs_lock = threading.RLock()
        
        # Handlers de logging
        self._handlers: Dict[str, logging.Handler] = {}
        self._handlers_lock = threading.RLock()
        
        # Logger Python
        self._logger = logging.getLogger("nexus_hedge_bot")
        
        # Queue de logs
        self._log_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "logs_recorded": 0,
            "audits_recorded": 0,
            "logs_flushed": 0,
            "errors": 0,
            "queue_size": 0,
            "avg_log_time_ms": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        # Host info
        self._hostname = socket.gethostname()
        self._process_id = os.getpid()
        
        # Initialize logging
        self._setup_logging()
        
        logger.info("LoggerEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "default_level": LogLevel.INFO,
            "default_format": LogFormat.JSON,
            "default_output": LogOutput.FILE,
            "log_file": "./logs/nexus.log",
            "max_log_size_mb": 100,
            "backup_count": 5,
            "enable_audit": True,
            "audit_retention_days": 365,
            "log_retention_days": 30,
            "flush_interval": 5,
            "batch_size": 1000,
            "enable_compression": True,
            "enable_encryption": False,
            "enable_structured_logging": True,
            "enable_trace_id": True
        }
    
    async def start(self) -> None:
        """Démarre le moteur de logging."""
        logger.info("LoggerEngine starting...")
        self._is_running = True
        
        # Chargement des configurations
        await self._load_configs()
        
        # Chargement des logs
        await self._load_logs()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._log_processor())
        asyncio.create_task(self._log_rotator())
        asyncio.create_task(self._metrics_collector())
        asyncio.create_task(self._cache_cleaner())
        
        logger.info("LoggerEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de logging."""
        logger.info("LoggerEngine stopping...")
        self._is_running = False
        
        # Drain de la queue
        await self._drain_queue()
        
        # Fermeture des handlers
        for handler in self._handlers.values():
            handler.close()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("LoggerEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def log(self, entry: LogEntry) -> str:
        """Enregistre un log."""
        start_time = time.time()
        self._stats["logs_recorded"] += 1
        
        # Enrichissement du log
        await self._enrich_log_entry(entry)
        
        # Mise en queue
        await self._log_queue.put(entry)
        
        # Stockage en mémoire
        with self._logs_lock:
            self._logs[entry.log_id] = entry
        
        # Métriques de temps
        elapsed = (time.time() - start_time) * 1000
        self._stats["avg_log_time_ms"] = (
            self._stats["avg_log_time_ms"] * 0.9 + elapsed * 0.1
        )
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"log:{entry.log_id}",
                entry.to_dict(),
                DataType.LOG
            )
        
        return entry.log_id
    
    async def audit(self, trail: AuditTrail) -> str:
        """Enregistre une trace d'audit."""
        self._stats["audits_recorded"] += 1
        
        # Enrichissement
        trail.source_ip = trail.source_ip or self._get_client_ip()
        trail.session_id = trail.session_id or str(uuid.uuid4())
        
        with self._audits_lock:
            self._audits[trail.audit_id] = trail
        
        # Enregistrement comme log
        log_entry = LogEntry(
            level=LogLevel.AUDIT,
            category=LogCategory.AUDIT,
            message=f"Audit: {trail.action} on {trail.resource} by {trail.user}",
            context=trail.to_dict(),
            user_id=trail.user,
            tags=["audit", trail.action],
            correlation_id=trail.session_id
        )
        await self.log(log_entry)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"audit:{trail.audit_id}",
                trail.to_dict(),
                DataType.AUDIT
            )
        
        logger.info(f"Audit recorded: {trail.action} by {trail.user}")
        return trail.audit_id
    
    async def get_logs(self, filter: Dict[str, Any], limit: int = 100) -> List[LogEntry]:
        """Récupère les logs."""
        logs = []
        
        with self._logs_lock:
            for log in self._logs.values():
                # Filtrage
                match = True
                for key, value in filter.items():
                    if key == "level" and log.level.value != value:
                        match = False
                        break
                    elif key == "category" and log.category.value != value:
                        match = False
                        break
                    elif key == "user_id" and log.user_id != value:
                        match = False
                        break
                    elif key == "correlation_id" and log.correlation_id != value:
                        match = False
                        break
                    elif key == "start_time" and log.timestamp < value:
                        match = False
                        break
                    elif key == "end_time" and log.timestamp > value:
                        match = False
                        break
                
                if match:
                    logs.append(log)
        
        # Tri par timestamp
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        return logs[:limit]
    
    # ========== MÉTHODES PRIVÉES - LOGGING ==========
    
    def _setup_logging(self) -> None:
        """Configure le système de logging."""
        # Configuration de base
        self._logger.setLevel(logging.DEBUG)
        
        # Handler console
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_format)
        self._logger.addHandler(console_handler)
        
        # Handler fichier
        log_dir = Path(self.config["log_file"]).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            self.config["log_file"],
            maxBytes=self.config["max_log_size_mb"] * 1024 * 1024,
            backupCount=self.config["backup_count"]
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_format)
        self._logger.addHandler(file_handler)
        
        logger.info("Logging system initialized")
    
    async def _enrich_log_entry(self, entry: LogEntry) -> None:
        """Enrichit une entrée de log."""
        entry.source = self._hostname
        entry.module = entry.module or self._get_caller_module()
        entry.function = entry.function or self._get_caller_function()
        
        # Ajout du trace_id
        if self.config["enable_trace_id"]:
            entry.context["trace_id"] = str(uuid.uuid4())
        
        # Ajout des métadonnées système
        entry.context.update({
            "hostname": self._hostname,
            "process_id": self._process_id,
            "python_version": platform.python_version(),
            "platform": platform.platform()
        })
    
    def _get_caller_module(self) -> str:
        """Récupère le module appelant."""
        frame = sys._getframe(2)
        return frame.f_globals.get("__name__", "unknown")
    
    def _get_caller_function(self) -> str:
        """Récupère la fonction appelante."""
        frame = sys._getframe(2)
        return frame.f_code.co_name
    
    def _get_client_ip(self) -> str:
        """Récupère l'IP du client."""
        # Dans un système réel, on récupérerait l'IP de la requête
        return "0.0.0.0"
    
    # ========== MÉTHODES PRIVÉES - PROCESSING ==========
    
    async def _log_processor(self) -> None:
        """Traite les logs en queue."""
        batch = []
        last_flush = time.time()
        
        while self._is_running:
            try:
                # Collecte des logs
                try:
                    entry = await asyncio.wait_for(
                        self._log_queue.get(),
                        timeout=self.config["flush_interval"]
                    )
                    batch.append(entry)
                except asyncio.TimeoutError:
                    pass
                
                # Flush du batch
                if len(batch) >= self.config["batch_size"] or \
                   (time.time() - last_flush) >= self.config["flush_interval"]:
                    
                    if batch:
                        await self._flush_logs(batch)
                        batch = []
                        last_flush = time.time()
                
            except Exception as e:
                logger.error(f"Log processor error: {e}")
                await asyncio.sleep(0.1)
    
    async def _flush_logs(self, logs: List[LogEntry]) -> None:
        """Flush les logs."""
        for entry in logs:
            try:
                # Formatage du log
                formatted = self._format_log(entry)
                
                # Écriture dans les handlers
                await self._write_log(entry, formatted)
                
                self._stats["logs_flushed"] += 1
                
            except Exception as e:
                self._stats["errors"] += 1
                logger.error(f"Flush log error: {e}")
    
    def _format_log(self, entry: LogEntry) -> Union[str, Dict]:
        """Formate un log."""
        if self.config["enable_structured_logging"]:
            return entry.to_dict()
        else:
            return f"{entry.timestamp.isoformat()} - {entry.level.name} - {entry.category.value} - {entry.message}"
    
    async def _write_log(self, entry: LogEntry, formatted: Union[str, Dict]) -> None:
        """Écrit un log."""
        # Écriture dans le logger Python
        if isinstance(formatted, dict):
            log_message = json.dumps(formatted)
        else:
            log_message = str(formatted)
        
        # Utilisation du logger Python
        self._logger.log(entry.level.value, log_message)
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _log_rotator(self) -> None:
        """Gère la rotation des logs."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                # Vérification de la taille du fichier de log
                log_file = Path(self.config["log_file"])
                if log_file.exists():
                    size_mb = log_file.stat().st_size / (1024 * 1024)
                    if size_mb > self.config["max_log_size_mb"]:
                        # Rotation du fichier
                        backup_file = log_file.parent / f"{log_file.stem}.{int(time.time())}{log_file.suffix}"
                        log_file.rename(backup_file)
                        
                        # Compression
                        if self.config["enable_compression"]:
                            import gzip
                            with open(backup_file, 'rb') as f:
                                with gzip.open(f"{backup_file}.gz", 'wb') as gz:
                                    gz.write(f.read())
                            backup_file.unlink()
                
            except Exception as e:
                logger.error(f"Log rotator error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(days=self.config["log_retention_days"])
                
                with self._logs_lock:
                    old_logs = [
                        lid for lid, log in self._logs.items()
                        if log.timestamp < cutoff
                    ]
                    for lid in old_logs:
                        del self._logs[lid]
                
                with self._audits_lock:
                    cutoff_audit = datetime.now(timezone.utc) - timedelta(days=self.config["audit_retention_days"])
                    old_audits = [
                        aid for aid, audit in self._audits.items()
                        if audit.timestamp < cutoff_audit
                    ]
                    for aid in old_audits:
                        del self._audits[aid]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _drain_queue(self) -> None:
        """Vide la queue de logs."""
        logs = []
        while not self._log_queue.empty():
            try:
                entry = await self._log_queue.get()
                logs.append(entry)
            except Exception:
                break
        
        if logs:
            await self._flush_logs(logs)
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._logs_lock:
                    self._stats["total_logs"] = len(self._logs)
                with self._audits_lock:
                    self._stats["total_audits"] = len(self._audits)
                
                self._stats["queue_size"] = self._log_queue.qsize()
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "logger:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_configs(self) -> None:
        """Charge les configurations."""
        try:
            if self.data_manager:
                configs_data = await self.data_manager.retrieve(
                    "logger:configs",
                    DataType.CONFIG
                )
                
                if configs_data:
                    for c_dict in configs_data:
                        config = self._deserialize_config(c_dict)
                        if config:
                            with self._configs_lock:
                                self._configs[config.config_id] = config
            
            logger.info(f"Loaded {len(self._configs)} log configs")
            
        except Exception as e:
            logger.error(f"Load configs error: {e}")
    
    async def _load_logs(self) -> None:
        """Charge les logs existants."""
        try:
            if self.data_manager:
                logs_data = await self.data_manager.retrieve(
                    "logs:recent",
                    DataType.LOG
                )
                
                if logs_data:
                    for l_dict in logs_data:
                        log = self._deserialize_log(l_dict)
                        if log:
                            with self._logs_lock:
                                self._logs[log.log_id] = log
            
            logger.info(f"Loaded {len(self._logs)} recent logs")
            
        except Exception as e:
            logger.error(f"Load logs error: {e}")
    
    def _deserialize_log(self, data: Dict) -> Optional[LogEntry]:
        """Désérialise un log."""
        try:
            return LogEntry(
                log_id=data.get("log_id", str(uuid.uuid4())),
                level=LogLevel(data.get("level", 20)),
                category=LogCategory(data.get("category", "system")),
                message=data.get("message", ""),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                source=data.get("source", ""),
                module=data.get("module", ""),
                function=data.get("function", ""),
                line=data.get("line", 0),
                traceback=data.get("traceback"),
                context=data.get("context", {}),
                tags=data.get("tags", []),
                correlation_id=data.get("correlation_id"),
                session_id=data.get("session_id"),
                user_id=data.get("user_id"),
                ip_address=data.get("ip_address"),
                metadata=data.get("metadata", {}),
                version=data.get("version", 1)
            )
        except Exception as e:
            logger.error(f"Error deserializing log: {e}")
            return None
    
    def _deserialize_config(self, data: Dict) -> Optional[LogConfig]:
        """Désérialise une configuration."""
        try:
            return LogConfig(
                config_id=data.get("config_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                level=LogLevel(data.get("level", 20)),
                format=LogFormat(data.get("format", "json")),
                output=LogOutput(data.get("output", "file")),
                file_path=data.get("file_path", "./logs/nexus.log"),
                max_size_mb=data.get("max_size_mb", 100),
                backup_count=data.get("backup_count", 5),
                rotation_interval=data.get("rotation_interval", "1d"),
                enable_compression=data.get("enable_compression", True),
                enable_encryption=data.get("enable_encryption", False),
                enable_audit=data.get("enable_audit", True),
                retention_days=data.get("retention_days", 30),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True)
            )
        except Exception as e:
            logger.error(f"Error deserializing config: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def create_config(self, config: LogConfig) -> str:
        """Crée une configuration de logging."""
        with self._configs_lock:
            self._configs[config.config_id] = config
        
        if self.data_manager:
            await self.data_manager.store(
                f"logger:config:{config.config_id}",
                config.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Log config created: {config.name}")
        return config.config_id
    
    async def get_config(self, config_id: str) -> Optional[LogConfig]:
        """Récupère une configuration."""
        with self._configs_lock:
            return self._configs.get(config_id)
    
    async def get_configs(self) -> List[LogConfig]:
        """Récupère les configurations."""
        with self._configs_lock:
            return list(self._configs.values())
    
    async def get_audits(self, user: Optional[str] = None) -> List[AuditTrail]:
        """Récupère les audits."""
        with self._audits_lock:
            audits = list(self._audits.values())
            if user:
                audits = [a for a in audits if a.user == user]
            return sorted(auds, key=lambda a: a.timestamp, reverse=True)
    
    async def search_logs(self, query: str, limit: int = 100) -> List[LogEntry]:
        """Recherche dans les logs."""
        results = []
        
        with self._logs_lock:
            for log in self._logs.values():
                if query.lower() in log.message.lower():
                    results.append(log)
        
        return results[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._logs_lock:
            self._stats["total_logs"] = len(self._logs)
        with self._audits_lock:
            self._stats["total_audits"] = len(self._audits)
        
        return self._stats.copy()


# ============== LOG HELPER ==============

class LogHelper:
    """
    Helper pour la création de logs.
    Facilite la création de logs structurés.
    """
    
    def __init__(self, engine: LoggerEngine):
        self.engine = engine
    
    async def info(self, message: str, **kwargs) -> str:
        """Log INFO."""
        entry = LogEntry(
            level=LogLevel.INFO,
            message=message,
            context=kwargs.get("context", {}),
            tags=kwargs.get("tags", []),
            correlation_id=kwargs.get("correlation_id"),
            user_id=kwargs.get("user_id")
        )
        return await self.engine.log(entry)
    
    async def warning(self, message: str, **kwargs) -> str:
        """Log WARNING."""
        entry = LogEntry(
            level=LogLevel.WARNING,
            message=message,
            context=kwargs.get("context", {}),
            tags=kwargs.get("tags", []),
            correlation_id=kwargs.get("correlation_id"),
            user_id=kwargs.get("user_id")
        )
        return await self.engine.log(entry)
    
    async def error(self, message: str, **kwargs) -> str:
        """Log ERROR."""
        entry = LogEntry(
            level=LogLevel.ERROR,
            message=message,
            context=kwargs.get("context", {}),
            tags=kwargs.get("tags", []),
            correlation_id=kwargs.get("correlation_id"),
            user_id=kwargs.get("user_id"),
            traceback=kwargs.get("traceback")
        )
        return await self.engine.log(entry)
    
    async def critical(self, message: str, **kwargs) -> str:
        """Log CRITICAL."""
        entry = LogEntry(
            level=LogLevel.CRITICAL,
            message=message,
            context=kwargs.get("context", {}),
            tags=kwargs.get("tags", []),
            correlation_id=kwargs.get("correlation_id"),
            user_id=kwargs.get("user_id"),
            traceback=kwargs.get("traceback")
        )
        return await self.engine.log(entry)
    
    async def audit(self, action: str, resource: str, user: str, **kwargs) -> str:
        """Log AUDIT."""
        trail = AuditTrail(
            user=user,
            action=action,
            resource=resource,
            resource_id=kwargs.get("resource_id"),
            changes=kwargs.get("changes", {}),
            status=kwargs.get("status", "success"),
            source_ip=kwargs.get("source_ip"),
            session_id=kwargs.get("session_id"),
            tags=kwargs.get("tags", [])
        )
        return await self.engine.audit(trail)


# ============== FACTORY ==============

class LoggerFactory:
    """Factory pour créer des composants de logging."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> LoggerEngine:
        """Crée un moteur de logging."""
        engine = LoggerEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_helper(engine: LoggerEngine) -> LogHelper:
        """Crée un helper de logging."""
        return LogHelper(engine)


# ============== EXPORT ==============

__all__ = [
    "LogLevel",
    "LogCategory",
    "LogFormat",
    "LogOutput",
    "LogEntry",
    "AuditTrail",
    "LogConfig",
    "LoggerEngineInterface",
    "LoggerEngine",
    "LogHelper",
    "LoggerFactory"
]
