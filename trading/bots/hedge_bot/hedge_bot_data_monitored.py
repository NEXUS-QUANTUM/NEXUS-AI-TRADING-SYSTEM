# trading/bots/hedge_bot/hedge_bot_data_monitored.py
# Advanced Data Monitoring & Observability Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Monitored Module - Module avancé de monitoring et d'observabilité des données
pour le Hedge Bot. Assure la surveillance en temps réel des données, la détection d'anomalies,
la qualité des données, les métriques de performance et les alertes pour l'ensemble du système.
"""

import asyncio
import json
import time
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
import hashlib
import statistics

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_monitored")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_encryption import (
    EncryptionEngine, SecurityContext
)


# ============== ENUMS & TYPES ==============

class MonitorMetricType(Enum):
    """Types de métriques de monitoring."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    RATE = "rate"
    PERCENTILE = "percentile"
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    SUM = "sum"


class MonitorAlertSeverity(Enum):
    """Sévérité des alertes de monitoring."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    FATAL = "fatal"


class MonitorStatus(Enum):
    """Statuts de monitoring."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    MAINTENANCE = "maintenance"


# ============== DATA MODELS ==============

@dataclass
class MonitorMetric:
    """Métrique de monitoring."""
    metric_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    metric_type: MonitorMetricType = MonitorMetricType.GAUGE
    value: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    dimensions: Dict[str, str] = field(default_factory=dict)
    unit: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitorAlert:
    """Alerte de monitoring."""
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    severity: MonitorAlertSeverity = MonitorAlertSeverity.WARNING
    message: str = ""
    condition: str = ""
    metric: str = ""
    threshold: float = 0.0
    current_value: float = 0.0
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    status: str = "active"  # active, resolved, acknowledged
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitorCheck:
    """Check de monitoring."""
    check_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    interval: int = 60  # seconds
    last_run: Optional[datetime] = None
    status: MonitorStatus = MonitorStatus.UNKNOWN
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    active: bool = True


@dataclass
class MonitorDashboard:
    """Dashboard de monitoring."""
    dashboard_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    metrics: List[str] = field(default_factory=list)
    layout: Dict[str, Any] = field(default_factory=dict)
    refresh_interval: int = 30
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True


# ============== INTERFACES ==============

class MonitoredEngineInterface(ABC):
    """Interface abstraite pour le moteur de monitoring."""
    
    @abstractmethod
    async def record_metric(self, metric: MonitorMetric) -> str:
        """Enregistre une métrique."""
        pass
    
    @abstractmethod
    async def create_alert(self, alert: MonitorAlert) -> str:
        """Crée une alerte."""
        pass
    
    @abstractmethod
    async def run_check(self, check: MonitorCheck) -> MonitorCheck:
        """Exécute un check de monitoring."""
        pass
    
    @abstractmethod
    async def get_metrics(self, name: str, limit: int = 100) -> List[MonitorMetric]:
        """Récupère les métriques."""
        pass


# ============== IMPLÉMENTATION ==============

class MonitoredEngine(MonitoredEngineInterface):
    """
    Moteur de monitoring avancé pour le Hedge Bot.
    Assure la surveillance en temps réel, la détection d'anomalies et les alertes.
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
        
        # Gestion des métriques
        self._metrics: Dict[str, List[MonitorMetric]] = defaultdict(list)
        self._metrics_lock = threading.RLock()
        
        # Gestion des alertes
        self._alerts: Dict[str, MonitorAlert] = {}
        self._alerts_lock = threading.RLock()
        
        # Gestion des checks
        self._checks: Dict[str, MonitorCheck] = {}
        self._checks_lock = threading.RLock()
        
        # Gestion des dashboards
        self._dashboards: Dict[str, MonitorDashboard] = {}
        self._dashboards_lock = threading.RLock()
        
        # Cache des métriques
        self._metric_cache: Dict[str, List[MonitorMetric]] = {}
        self._cache_lock = threading.RLock()
        
        # Queue d'alertes
        self._alert_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "metrics_recorded": 0,
            "alerts_created": 0,
            "checks_run": 0,
            "alerts_resolved": 0,
            "critical_alerts": 0,
            "warning_alerts": 0,
            "avg_metric_time_ms": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("MonitoredEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "metric_history_size": 10000,
            "alert_retention_days": 30,
            "check_timeout": 30,
            "metric_cache_ttl": 60,
            "enable_metric_aggregation": True,
            "enable_alert_deduplication": True,
            "alert_dedup_window": 300,
            "default_alert_severity": MonitorAlertSeverity.WARNING,
            "max_metrics_per_second": 1000,
            "dashboard_refresh_default": 30,
            "health_check_interval": 60,
            "anomaly_detection_enabled": True,
            "anomaly_window": 60
        }
    
    async def start(self) -> None:
        """Démarre le moteur de monitoring."""
        logger.info("MonitoredEngine starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._alert_processor())
        asyncio.create_task(self._check_scheduler())
        asyncio.create_task(self._anomaly_detector())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("MonitoredEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de monitoring."""
        logger.info("MonitoredEngine stopping...")
        self._is_running = False
        
        # Vidage de la queue
        await self._drain_queue()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("MonitoredEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def record_metric(self, metric: MonitorMetric) -> str:
        """Enregistre une métrique."""
        self._stats["metrics_recorded"] += 1
        
        with self._metrics_lock:
            self._metrics[metric.name].append(metric)
            
            # Limitation de l'historique
            if len(self._metrics[metric.name]) > self.config["metric_history_size"]:
                self._metrics[metric.name] = self._metrics[metric.name][-self.config["metric_history_size"]:]
        
        # Mise à jour du cache
        with self._cache_lock:
            if metric.name in self._metric_cache:
                self._metric_cache[metric.name].append(metric)
                if len(self._metric_cache[metric.name]) > 100:
                    self._metric_cache[metric.name] = self._metric_cache[metric.name][-100:]
            else:
                self._metric_cache[metric.name] = [metric]
        
        # Détection d'anomalies
        if self.config["anomaly_detection_enabled"]:
            await self._detect_anomaly(metric)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"monitor:metric:{metric.metric_id}",
                metric.to_dict(),
                DataType.METRICS
            )
        
        return metric.metric_id
    
    async def create_alert(self, alert: MonitorAlert) -> str:
        """Crée une alerte."""
        self._stats["alerts_created"] += 1
        
        # Déduplication
        if self.config["enable_alert_deduplication"]:
            with self._alerts_lock:
                for existing in self._alerts.values():
                    if (existing.name == alert.name and 
                        existing.status == "active" and
                        (datetime.now(timezone.utc) - existing.triggered_at).total_seconds() < self.config["alert_dedup_window"]):
                        logger.debug(f"Alert deduplicated: {alert.name}")
                        return existing.alert_id
        
        # Mise à jour des statistiques
        if alert.severity == MonitorAlertSeverity.CRITICAL:
            self._stats["critical_alerts"] += 1
        elif alert.severity == MonitorAlertSeverity.WARNING:
            self._stats["warning_alerts"] += 1
        
        with self._alerts_lock:
            self._alerts[alert.alert_id] = alert
        
        # Mise en queue pour traitement
        await self._alert_queue.put(alert)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"monitor:alert:{alert.alert_id}",
                alert.to_dict(),
                DataType.ALERT
            )
        
        logger.info(f"Alert created: {alert.name} (severity={alert.severity.value})")
        return alert.alert_id
    
    async def run_check(self, check: MonitorCheck) -> MonitorCheck:
        """Exécute un check de monitoring."""
        self._stats["checks_run"] += 1
        
        check.last_run = datetime.now(timezone.utc)
        
        try:
            # Exécution du check
            result = await self._execute_check(check)
            check.result = result
            check.status = MonitorStatus.HEALTHY
            
            # Vérification des seuils
            if result and "value" in result:
                threshold = check.metadata.get("threshold", 0)
                if result["value"] > threshold * 1.5:
                    check.status = MonitorStatus.UNHEALTHY
                    check.error = f"Value {result['value']} exceeds threshold {threshold}"
                elif result["value"] > threshold:
                    check.status = MonitorStatus.DEGRADED
                    check.error = f"Value {result['value']} near threshold {threshold}"
            
        except Exception as e:
            check.status = MonitorStatus.UNHEALTHY
            check.error = str(e)
            logger.error(f"Check failed: {check.name} - {e}")
        
        # Stockage du check
        with self._checks_lock:
            self._checks[check.check_id] = check
        
        return check
    
    async def get_metrics(self, name: str, limit: int = 100) -> List[MonitorMetric]:
        """Récupère les métriques."""
        with self._metrics_lock:
            metrics = self._metrics.get(name, [])
            return metrics[-limit:]
    
    # ========== MÉTHODES PRIVÉES - ALERTES ==========
    
    async def _alert_processor(self) -> None:
        """Traite les alertes en queue."""
        while self._is_running:
            try:
                alert = await self._alert_queue.get()
                
                # Traitement de l'alerte
                await self._process_alert(alert)
                
            except Exception as e:
                logger.error(f"Alert processor error: {e}")
                await asyncio.sleep(1)
    
    async def _process_alert(self, alert: MonitorAlert) -> None:
        """Traite une alerte."""
        # Notification
        await self._notify_alert(alert)
        
        # Enregistrement dans l'historique
        if self.data_manager:
            await self.data_manager.store(
                f"monitor:alert_history:{alert.alert_id}",
                alert.to_dict(),
                DataType.ALERT
            )
    
    async def _notify_alert(self, alert: MonitorAlert) -> None:
        """Notifie une alerte."""
        # Dans un système réel, on enverrait des notifications
        # via email, Slack, PagerDuty, etc.
        if alert.severity in [MonitorAlertSeverity.CRITICAL, MonitorAlertSeverity.FATAL]:
            logger.warning(f"CRITICAL ALERT: {alert.name} - {alert.message}")
        elif alert.severity == MonitorAlertSeverity.ERROR:
            logger.error(f"ERROR ALERT: {alert.name} - {alert.message}")
        else:
            logger.info(f"ALERT: {alert.name} - {alert.message}")
    
    # ========== MÉTHODES PRIVÉES - CHECKS ==========
    
    async def _check_scheduler(self) -> None:
        """Planifie les checks périodiques."""
        while self._is_running:
            await asyncio.sleep(self.config["health_check_interval"])
            
            try:
                with self._checks_lock:
                    for check in self._checks.values():
                        if not check.active:
                            continue
                        
                        # Vérification de l'intervalle
                        if check.last_run:
                            elapsed = (datetime.now(timezone.utc) - check.last_run).total_seconds()
                            if elapsed < check.interval:
                                continue
                        
                        # Exécution du check
                        asyncio.create_task(self.run_check(check))
                
            except Exception as e:
                logger.error(f"Check scheduler error: {e}")
    
    async def _execute_check(self, check: MonitorCheck) -> Dict[str, Any]:
        """Exécute un check."""
        # Simulation de check
        # Dans un système réel, on vérifierait l'état du système
        
        if check.name == "data_quality":
            return await self._check_data_quality()
        elif check.name == "system_health":
            return await self._check_system_health()
        elif check.name == "performance":
            return await self._check_performance()
        else:
            return {"value": 1.0, "status": "ok"}
    
    async def _check_data_quality(self) -> Dict[str, Any]:
        """Vérifie la qualité des données."""
        missing_count = 0
        total_count = 0
        
        if self.data_manager:
            for data_type in DataType:
                records = await self.data_manager.retrieve_all(data_type)
                for record in records:
                    total_count += 1
                    if not record.value:
                        missing_count += 1
        
        quality_score = 1 - (missing_count / (total_count + 1))
        
        return {
            "value": quality_score,
            "missing_count": missing_count,
            "total_count": total_count,
            "status": "ok" if quality_score > 0.95 else "degraded"
        }
    
    async def _check_system_health(self) -> Dict[str, Any]:
        """Vérifie la santé du système."""
        # Simulation de santé système
        import psutil
        
        cpu_usage = psutil.cpu_percent()
        memory_usage = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('/').percent
        
        health_score = 1 - ((cpu_usage + memory_usage + disk_usage) / 300)
        
        return {
            "value": health_score,
            "cpu_usage": cpu_usage,
            "memory_usage": memory_usage,
            "disk_usage": disk_usage,
            "status": "ok" if health_score > 0.7 else "degraded"
        }
    
    async def _check_performance(self) -> Dict[str, Any]:
        """Vérifie les performances."""
        # Simulation de performances
        avg_latency = self._stats.get("avg_metric_time_ms", 0)
        throughput = self._stats.get("metrics_recorded", 0) / 60
        
        performance_score = 1 - (avg_latency / 1000)
        
        return {
            "value": performance_score,
            "avg_latency_ms": avg_latency,
            "throughput": throughput,
            "status": "ok" if performance_score > 0.7 else "degraded"
        }
    
    # ========== MÉTHODES PRIVÉES - ANOMALIES ==========
    
    async def _anomaly_detector(self) -> None:
        """Détecte les anomalies dans les métriques."""
        while self._is_running:
            await asyncio.sleep(self.config["anomaly_window"])
            
            try:
                with self._metrics_lock:
                    for metric_name, metrics in self._metrics.items():
                        if len(metrics) < 10:
                            continue
                        
                        recent = metrics[-self.config["anomaly_window"]:]
                        values = [m.value for m in recent]
                        
                        # Détection d'anomalies par Z-score
                        mean = np.mean(values)
                        std = np.std(values)
                        
                        if std > 0:
                            for metric in recent[-5:]:
                                z_score = (metric.value - mean) / std
                                if abs(z_score) > 3:
                                    # Anomalie détectée
                                    alert = MonitorAlert(
                                        name=f"Anomaly detected: {metric_name}",
                                        severity=MonitorAlertSeverity.WARNING,
                                        message=f"Z-score anomaly detected: {z_score:.2f}",
                                        condition=f"abs(z_score) > 3",
                                        metric=metric_name,
                                        threshold=3.0,
                                        current_value=metric.value,
                                        tags=["anomaly", "z-score"]
                                    )
                                    await self.create_alert(alert)
                
            except Exception as e:
                logger.error(f"Anomaly detector error: {e}")
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    # Nettoyage du cache des métriques
                    for name, metrics in list(self._metric_cache.items()):
                        if len(metrics) > 100:
                            self._metric_cache[name] = metrics[-100:]
                
                # Nettoyage des alertes résolues
                with self._alerts_lock:
                    cutoff = datetime.now(timezone.utc) - timedelta(days=self.config["alert_retention_days"])
                    resolved = [
                        aid for aid, alert in self._alerts.items()
                        if alert.status == "resolved" and alert.resolved_at and alert.resolved_at < cutoff
                    ]
                    for aid in resolved:
                        del self._alerts[aid]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._metrics_lock:
                    self._stats["total_metrics"] = sum(len(m) for m in self._metrics.values())
                with self._alerts_lock:
                    self._stats["total_alerts"] = len(self._alerts)
                    active_alerts = len([a for a in self._alerts.values() if a.status == "active"])
                    self._stats["active_alerts"] = active_alerts
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "monitor:stats",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    async def _drain_queue(self) -> None:
        """Vide la queue d'alertes."""
        while not self._alert_queue.empty():
            try:
                alert = await self._alert_queue.get()
                await self._process_alert(alert)
            except Exception:
                break
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_metric_stats(self, name: str) -> Dict[str, float]:
        """Récupère les statistiques d'une métrique."""
        metrics = await self.get_metrics(name)
        if not metrics:
            return {}
        
        values = [m.value for m in metrics]
        return {
            "count": len(values),
            "mean": np.mean(values),
            "std": np.std(values),
            "min": np.min(values),
            "max": np.max(values),
            "p50": np.percentile(values, 50),
            "p90": np.percentile(values, 90),
            "p95": np.percentile(values, 95),
            "p99": np.percentile(values, 99)
        }
    
    async def get_alert(self, alert_id: str) -> Optional[MonitorAlert]:
        """Récupère une alerte."""
        with self._alerts_lock:
            return self._alerts.get(alert_id)
    
    async def get_alerts(self, status: Optional[str] = None) -> List[MonitorAlert]:
        """Récupère les alertes."""
        with self._alerts_lock:
            alerts = list(self._alerts.values())
            if status:
                alerts = [a for a in alerts if a.status == status]
            return sorted(alerts, key=lambda a: a.triggered_at, reverse=True)
    
    async def resolve_alert(self, alert_id: str, resolution: str = "") -> bool:
        """Résout une alerte."""
        with self._alerts_lock:
            alert = self._alerts.get(alert_id)
            if not alert or alert.status != "active":
                return False
            
            alert.status = "resolved"
            alert.resolved_at = datetime.now(timezone.utc)
            alert.metadata["resolution"] = resolution
            self._stats["alerts_resolved"] += 1
            
            logger.info(f"Alert resolved: {alert.name}")
            return True
    
    async def create_check(self, check: MonitorCheck) -> str:
        """Crée un check de monitoring."""
        with self._checks_lock:
            self._checks[check.check_id] = check
        
        logger.info(f"Monitor check created: {check.name}")
        return check.check_id
    
    async def get_check(self, check_id: str) -> Optional[MonitorCheck]:
        """Récupère un check."""
        with self._checks_lock:
            return self._checks.get(check_id)
    
    async def get_checks(self) -> List[MonitorCheck]:
        """Récupère les checks."""
        with self._checks_lock:
            return list(self._checks.values())
    
    async def create_dashboard(self, dashboard: MonitorDashboard) -> str:
        """Crée un dashboard de monitoring."""
        with self._dashboards_lock:
            self._dashboards[dashboard.dashboard_id] = dashboard
        
        logger.info(f"Monitor dashboard created: {dashboard.name}")
        return dashboard.dashboard_id
    
    async def get_dashboard(self, dashboard_id: str) -> Optional[MonitorDashboard]:
        """Récupère un dashboard."""
        with self._dashboards_lock:
            return self._dashboards.get(dashboard_id)
    
    async def get_dashboards(self) -> List[MonitorDashboard]:
        """Récupère les dashboards."""
        with self._dashboards_lock:
            return list(self._dashboards.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._metrics_lock:
            self._stats["total_metrics"] = sum(len(m) for m in self._metrics.values())
        with self._alerts_lock:
            self._stats["total_alerts"] = len(self._alerts)
        
        return self._stats.copy()


# ============== MONITOR DASHBOARD BUILDER ==============

class MonitorDashboardBuilder:
    """
    Constructeur de dashboards de monitoring.
    Facilite la création de dashboards pour le monitoring.
    """
    
    def __init__(self):
        self._dashboard = MonitorDashboard()
        self._widgets = []
    
    def name(self, name: str) -> 'MonitorDashboardBuilder':
        """Définit le nom du dashboard."""
        self._dashboard.name = name
        return self
    
    def description(self, description: str) -> 'MonitorDashboardBuilder':
        """Définit la description."""
        self._dashboard.description = description
        return self
    
    def add_metric(self, metric: str) -> 'MonitorDashboardBuilder':
        """Ajoute une métrique."""
        self._dashboard.metrics.append(metric)
        return self
    
    def add_widget(self, widget_type: str, config: Dict[str, Any]) -> 'MonitorDashboardBuilder':
        """Ajoute un widget."""
        self._widgets.append({
            "type": widget_type,
            "config": config
        })
        return self
    
    def refresh_interval(self, interval: int) -> 'MonitorDashboardBuilder':
        """Définit l'intervalle de rafraîchissement."""
        self._dashboard.refresh_interval = interval
        return self
    
    def tags(self, tags: List[str]) -> 'MonitorDashboardBuilder':
        """Définit les tags."""
        self._dashboard.tags = tags
        return self
    
    def metadata(self, metadata: Dict[str, Any]) -> 'MonitorDashboardBuilder':
        """Définit les métadonnées."""
        self._dashboard.metadata = metadata
        return self
    
    def build(self) -> MonitorDashboard:
        """Construit le dashboard."""
        self._dashboard.layout = {
            "widgets": self._widgets
        }
        return self._dashboard


# ============== FACTORY ==============

class MonitoredFactory:
    """Factory pour créer des composants de monitoring."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        encryption_engine: Optional[EncryptionEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> MonitoredEngine:
        """Crée un moteur de monitoring."""
        engine = MonitoredEngine(
            data_manager=data_manager,
            encryption_engine=encryption_engine,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_dashboard_builder() -> MonitorDashboardBuilder:
        """Crée un constructeur de dashboards."""
        return MonitorDashboardBuilder()


# ============== EXPORT ==============

__all__ = [
    "MonitorMetricType",
    "MonitorAlertSeverity",
    "MonitorStatus",
    "MonitorMetric",
    "MonitorAlert",
    "MonitorCheck",
    "MonitorDashboard",
    "MonitoredEngineInterface",
    "MonitoredEngine",
    "MonitorDashboardBuilder",
    "MonitoredFactory"
]
