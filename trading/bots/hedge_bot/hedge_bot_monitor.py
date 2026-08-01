# trading/bots/hedge_bot/hedge_bot_monitor.py
# Advanced System Monitoring & Health Management Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Monitor Module - Module avancé de monitoring système et de gestion de la santé
pour le Hedge Bot. Assure la surveillance en temps réel des composants, la détection
des anomalies, les alertes, et la gestion de la santé du système de hedging.
"""

import asyncio
import json
import time
import psutil
import platform
import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import threading
import concurrent.futures
import subprocess

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_monitor")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)


# ============== ENUMS & TYPES ==============

class ComponentType(Enum):
    """Types de composants."""
    SYSTEM = "system"
    DATABASE = "database"
    NETWORK = "network"
    API = "api"
    TRADING = "trading"
    RISK = "risk"
    STORAGE = "storage"
    MEMORY = "memory"
    CPU = "cpu"
    PROCESS = "process"
    SERVICE = "service"
    EXTERNAL = "external"


class HealthStatus(Enum):
    """Statuts de santé."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    UNKNOWN = "unknown"
    MAINTENANCE = "maintenance"


class AlertSeverity(Enum):
    """Sévérité des alertes."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"


# ============== DATA MODELS ==============

@dataclass
class ComponentHealth:
    """Santé d'un composant."""
    health_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    component: ComponentType = ComponentType.SYSTEM
    name: str = ""
    status: HealthStatus = HealthStatus.UNKNOWN
    metrics: Dict[str, float] = field(default_factory=dict)
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uptime: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class SystemAlert:
    """Alerte système."""
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    severity: AlertSeverity = AlertSeverity.WARNING
    component: ComponentType = ComponentType.SYSTEM
    message: str = ""
    value: float = 0.0
    threshold: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    resolved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class SystemSnapshot:
    """Snapshot système."""
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_percent: float = 0.0
    network_in: float = 0.0
    network_out: float = 0.0
    process_count: int = 0
    thread_count: int = 0
    open_files: int = 0
    components: List[ComponentHealth] = field(default_factory=list)
    alerts: List[SystemAlert] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class MonitorEngineInterface(ABC):
    """Interface abstraite pour le moteur de monitoring."""
    
    @abstractmethod
    async def check_health(self) -> List[ComponentHealth]:
        """Vérifie la santé du système."""
        pass
    
    @abstractmethod
    async def get_snapshot(self) -> SystemSnapshot:
        """Récupère un snapshot du système."""
        pass
    
    @abstractmethod
    async def create_alert(self, alert: SystemAlert) -> str:
        """Crée une alerte."""
        pass


# ============== IMPLÉMENTATION ==============

class MonitorEngine(MonitorEngineInterface):
    """
    Moteur de monitoring avancé pour le Hedge Bot.
    Surveille la santé du système et génère des alertes.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion de la santé
        self._health: Dict[str, ComponentHealth] = {}
        self._health_lock = threading.RLock()
        
        # Gestion des alertes
        self._alerts: Dict[str, SystemAlert] = {}
        self._alerts_lock = threading.RLock()
        
        # Gestion des snapshots
        self._snapshots: List[SystemSnapshot] = []
        self._snapshots_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "health_checks": 0,
            "alerts_created": 0,
            "alerts_resolved": 0,
            "critical_alerts": 0,
            "warning_alerts": 0,
            "system_uptime": 0.0,
            "avg_cpu": 0.0,
            "avg_memory": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        # Process start time
        self._start_time = time.time()
        
        logger.info("MonitorEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "check_interval": 60,
            "health_threshold_cpu": 80,
            "health_threshold_memory": 80,
            "health_threshold_disk": 85,
            "alert_retention_days": 30,
            "snapshot_retention": 1000,
            "enable_alerts": True,
            "enable_auto_resolve": True,
            "auto_resolve_delay": 300,
            "critical_threshold_cpu": 95,
            "critical_threshold_memory": 95,
            "warning_threshold_cpu": 70,
            "warning_threshold_memory": 70
        }
    
    async def start(self) -> None:
        """Démarre le moteur de monitoring."""
        logger.info("MonitorEngine starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._alert_processor())
        asyncio.create_task(self._cleanup_loop())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("MonitorEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de monitoring."""
        logger.info("MonitorEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("MonitorEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def check_health(self) -> List[ComponentHealth]:
        """Vérifie la santé du système."""
        self._stats["health_checks"] += 1
        
        health_checks = []
        
        # Vérification CPU
        cpu_health = await self._check_cpu()
        health_checks.append(cpu_health)
        
        # Vérification mémoire
        memory_health = await self._check_memory()
        health_checks.append(memory_health)
        
        # Vérification disque
        disk_health = await self._check_disk()
        health_checks.append(disk_health)
        
        # Vérification réseau
        network_health = await self._check_network()
        health_checks.append(network_health)
        
        # Vérification processus
        process_health = await self._check_processes()
        health_checks.append(process_health)
        
        # Vérification des services
        services_health = await self._check_services()
        health_checks.extend(services_health)
        
        # Stockage de la santé
        with self._health_lock:
            for health in health_checks:
                self._health[health.health_id] = health
        
        # Génération d'alertes
        if self.config["enable_alerts"]:
            await self._generate_alerts(health_checks)
        
        return health_checks
    
    async def get_snapshot(self) -> SystemSnapshot:
        """Récupère un snapshot du système."""
        # Récupération des métriques
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net = psutil.net_io_counters()
        
        # Récupération de la santé
        with self._health_lock:
            components = list(self._health.values())
        
        with self._alerts_lock:
            alerts = list(self._alerts.values())
        
        snapshot = SystemSnapshot(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_percent=disk.percent,
            network_in=net.bytes_recv / (1024 ** 2),
            network_out=net.bytes_sent / (1024 ** 2),
            process_count=len(psutil.pids()),
            thread_count=sum(p.num_threads() for p in psutil.process_iter()),
            open_files=0,
            components=components,
            alerts=alerts
        )
        
        with self._snapshots_lock:
            self._snapshots.append(snapshot)
            if len(self._snapshots) > self.config["snapshot_retention"]:
                self._snapshots = self._snapshots[-self.config["snapshot_retention"]:]
        
        return snapshot
    
    async def create_alert(self, alert: SystemAlert) -> str:
        """Crée une alerte."""
        self._stats["alerts_created"] += 1
        
        if alert.severity == AlertSeverity.CRITICAL:
            self._stats["critical_alerts"] += 1
        elif alert.severity == AlertSeverity.WARNING:
            self._stats["warning_alerts"] += 1
        
        with self._alerts_lock:
            self._alerts[alert.alert_id] = alert
        
        # Notification
        await self._notify_alert(alert)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"monitor:alert:{alert.alert_id}",
                alert.to_dict(),
                DataType.ALERT
            )
        
        logger.info(f"Alert created: {alert.message} severity={alert.severity.value}")
        return alert.alert_id
    
    # ========== MÉTHODES PRIVÉES - VÉRIFICATIONS ==========
    
    async def _check_cpu(self) -> ComponentHealth:
        """Vérifie l'utilisation CPU."""
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        health = ComponentHealth(
            component=ComponentType.CPU,
            name="CPU Usage",
            metrics={"percent": cpu_percent, "count": cpu_count},
            uptime=time.time() - self._start_time
        )
        
        if cpu_percent > self.config["critical_threshold_cpu"]:
            health.status = HealthStatus.CRITICAL
            health.error = f"CPU usage at {cpu_percent:.1f}%"
        elif cpu_percent > self.config["health_threshold_cpu"]:
            health.status = HealthStatus.DEGRADED
            health.error = f"CPU usage at {cpu_percent:.1f}%"
        else:
            health.status = HealthStatus.HEALTHY
        
        return health
    
    async def _check_memory(self) -> ComponentHealth:
        """Vérifie l'utilisation mémoire."""
        memory = psutil.virtual_memory()
        
        health = ComponentHealth(
            component=ComponentType.MEMORY,
            name="Memory Usage",
            metrics={
                "percent": memory.percent,
                "available_mb": memory.available / (1024 ** 2),
                "used_mb": memory.used / (1024 ** 2),
                "total_mb": memory.total / (1024 ** 2)
            },
            uptime=time.time() - self._start_time
        )
        
        if memory.percent > self.config["critical_threshold_memory"]:
            health.status = HealthStatus.CRITICAL
            health.error = f"Memory usage at {memory.percent:.1f}%"
        elif memory.percent > self.config["health_threshold_memory"]:
            health.status = HealthStatus.DEGRADED
            health.error = f"Memory usage at {memory.percent:.1f}%"
        else:
            health.status = HealthStatus.HEALTHY
        
        return health
    
    async def _check_disk(self) -> ComponentHealth:
        """Vérifie l'utilisation disque."""
        disk = psutil.disk_usage('/')
        
        health = ComponentHealth(
            component=ComponentType.STORAGE,
            name="Disk Usage",
            metrics={
                "percent": disk.percent,
                "free_gb": disk.free / (1024 ** 3),
                "used_gb": disk.used / (1024 ** 3),
                "total_gb": disk.total / (1024 ** 3)
            },
            uptime=time.time() - self._start_time
        )
        
        if disk.percent > self.config["health_threshold_disk"]:
            health.status = HealthStatus.DEGRADED
            health.error = f"Disk usage at {disk.percent:.1f}%"
        else:
            health.status = HealthStatus.HEALTHY
        
        return health
    
    async def _check_network(self) -> ComponentHealth:
        """Vérifie le réseau."""
        net = psutil.net_io_counters()
        
        health = ComponentHealth(
            component=ComponentType.NETWORK,
            name="Network",
            metrics={
                "bytes_sent_mb": net.bytes_sent / (1024 ** 2),
                "bytes_recv_mb": net.bytes_recv / (1024 ** 2),
                "packets_sent": net.packets_sent,
                "packets_recv": net.packets_recv
            },
            uptime=time.time() - self._start_time
        )
        
        health.status = HealthStatus.HEALTHY
        return health
    
    async def _check_processes(self) -> ComponentHealth:
        """Vérifie les processus."""
        processes = list(psutil.process_iter())
        
        health = ComponentHealth(
            component=ComponentType.PROCESS,
            name="Processes",
            metrics={
                "count": len(processes),
                "threads": sum(p.num_threads() for p in processes)
            },
            uptime=time.time() - self._start_time
        )
        
        health.status = HealthStatus.HEALTHY
        return health
    
    async def _check_services(self) -> List[ComponentHealth]:
        """Vérifie les services."""
        services = []
        
        # Vérification du data manager
        if self.data_manager:
            try:
                # Ici on vérifierait la santé du data manager
                services.append(ComponentHealth(
                    component=ComponentType.SERVICE,
                    name="Data Manager",
                    status=HealthStatus.HEALTHY
                ))
            except:
                services.append(ComponentHealth(
                    component=ComponentType.SERVICE,
                    name="Data Manager",
                    status=HealthStatus.UNHEALTHY,
                    error="Data manager unreachable"
                ))
        
        return services
    
    # ========== MÉTHODES PRIVÉES - ALERTES ==========
    
    async def _generate_alerts(self, health_checks: List[ComponentHealth]) -> None:
        """Génère des alertes basées sur la santé."""
        for health in health_checks:
            if health.status in [HealthStatus.CRITICAL, HealthStatus.UNHEALTHY]:
                alert = SystemAlert(
                    severity=AlertSeverity.CRITICAL if health.status == HealthStatus.CRITICAL else AlertSeverity.ERROR,
                    component=health.component,
                    message=health.error or f"{health.name} is {health.status.value}",
                    value=health.metrics.get("percent", 0),
                    threshold=self.config.get(f"health_threshold_{health.component.value}", 80),
                    tags=[health.component.value, health.status.value]
                )
                await self.create_alert(alert)
            
            elif health.status == HealthStatus.DEGRADED:
                alert = SystemAlert(
                    severity=AlertSeverity.WARNING,
                    component=health.component,
                    message=health.error or f"{health.name} is degraded",
                    value=health.metrics.get("percent", 0),
                    threshold=self.config.get(f"health_threshold_{health.component.value}", 80),
                    tags=[health.component.value, health.status.value]
                )
                await self.create_alert(alert)
    
    async def _notify_alert(self, alert: SystemAlert) -> None:
        """Notifie une alerte."""
        # Dans un système réel, on enverrait des notifications
        if alert.severity == AlertSeverity.CRITICAL:
            logger.critical(f"CRITICAL: {alert.message}")
        elif alert.severity == AlertSeverity.ERROR:
            logger.error(f"ERROR: {alert.message}")
        elif alert.severity == AlertSeverity.WARNING:
            logger.warning(f"WARNING: {alert.message}")
        else:
            logger.info(f"INFO: {alert.message}")
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _health_check_loop(self) -> None:
        """Boucle de vérification de santé."""
        while self._is_running:
            await asyncio.sleep(self.config["check_interval"])
            
            try:
                await self.check_health()
                
                # Snapshot périodique
                if self._stats["health_checks"] % 10 == 0:
                    await self.get_snapshot()
                
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
    
    async def _alert_processor(self) -> None:
        """Traite les alertes."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                if self.config["enable_auto_resolve"]:
                    with self._alerts_lock:
                        now = datetime.now(timezone.utc)
                        for alert_id, alert in list(self._alerts.items()):
                            if not alert.resolved:
                                age = (now - alert.timestamp).total_seconds()
                                if age > self.config["auto_resolve_delay"]:
                                    alert.resolved = True
                                    self._stats["alerts_resolved"] += 1
                
            except Exception as e:
                logger.error(f"Alert processor error: {e}")
    
    async def _cleanup_loop(self) -> None:
        """Nettoie les données anciennes."""
        while self._is_running:
            await asyncio.sleep(86400)  # 1 jour
            
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(days=self.config["alert_retention_days"])
                
                with self._alerts_lock:
                    old_alerts = [
                        aid for aid, alert in self._alerts.items()
                        if alert.timestamp < cutoff
                    ]
                    for aid in old_alerts:
                        del self._alerts[aid]
                
                if old_alerts:
                    logger.debug(f"Cleaned up {len(old_alerts)} old alerts")
                
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._health_lock:
                    self._stats["total_health"] = len(self._health)
                with self._alerts_lock:
                    self._stats["total_alerts"] = len(self._alerts)
                    active_alerts = len([a for a in self._alerts.values() if not a.resolved])
                    self._stats["active_alerts"] = active_alerts
                
                # Métriques système
                self._stats["system_uptime"] = time.time() - self._start_time
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "monitor:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}"
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_health(self, health_id: str) -> Optional[ComponentHealth]:
        """Récupère un état de santé."""
        with self._health_lock:
            return self._health.get(health_id)
    
    async def get_health_checks(self) -> List[ComponentHealth]:
        """Récupère les états de santé."""
        with self._health_lock:
            return list(self._health.values())
    
    async def get_alert(self, alert_id: str) -> Optional[SystemAlert]:
        """Récupère une alerte."""
        with self._alerts_lock:
            return self._alerts.get(alert_id)
    
    async def get_alerts(self, resolved: bool = False) -> List[SystemAlert]:
        """Récupère les alertes."""
        with self._alerts_lock:
            alerts = list(self._alerts.values())
            if not resolved:
                alerts = [a for a in alerts if not a.resolved]
            return sorted(alerts, key=lambda a: a.timestamp, reverse=True)
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Résout une alerte."""
        with self._alerts_lock:
            alert = self._alerts.get(alert_id)
            if not alert or alert.resolved:
                return False
            
            alert.resolved = True
            self._stats["alerts_resolved"] += 1
            return True
    
    async def get_snapshots(self, limit: int = 100) -> List[SystemSnapshot]:
        """Récupère les snapshots."""
        with self._snapshots_lock:
            return self._snapshots[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._health_lock:
            self._stats["total_health"] = len(self._health)
        with self._alerts_lock:
            self._stats["total_alerts"] = len(self._alerts)
        
        return self._stats.copy()


# ============== HEALTH DASHBOARD ==============

class HealthDashboard:
    """
    Dashboard de santé.
    Visualise la santé du système.
    """
    
    def __init__(self, engine: MonitorEngine):
        self.engine = engine
    
    async def generate_report(self) -> Dict[str, Any]:
        """Génère un rapport de santé."""
        health_checks = await self.engine.get_health_checks()
        alerts = await self.engine.get_alerts()
        
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_components": len(health_checks),
                "healthy": len([h for h in health_checks if h.status == HealthStatus.HEALTHY]),
                "degraded": len([h for h in health_checks if h.status == HealthStatus.DEGRADED]),
                "unhealthy": len([h for h in health_checks if h.status == HealthStatus.UNHEALTHY]),
                "critical": len([h for h in health_checks if h.status == HealthStatus.CRITICAL]),
                "active_alerts": len([a for a in alerts if not a.resolved]),
                "critical_alerts": len([a for a in alerts if a.severity == AlertSeverity.CRITICAL and not a.resolved])
            },
            "components": [h.to_dict() for h in health_checks],
            "alerts": [a.to_dict() for a in alerts if not a.resolved],
            "system_uptime": time.time() - self.engine._start_time
        }
        
        return report


# ============== FACTORY ==============

class MonitorFactory:
    """Factory pour créer des composants de monitoring."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> MonitorEngine:
        """Crée un moteur de monitoring."""
        engine = MonitorEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_dashboard(engine: MonitorEngine) -> HealthDashboard:
        """Crée un dashboard de santé."""
        return HealthDashboard(engine)


# ============== EXPORT ==============

__all__ = [
    "ComponentType",
    "HealthStatus",
    "AlertSeverity",
    "ComponentHealth",
    "SystemAlert",
    "SystemSnapshot",
    "MonitorEngineInterface",
    "MonitorEngine",
    "HealthDashboard",
    "MonitorFactory"
]
