# trading/bots/hedge_bot/hedge_bot_data_monitoring.py
# Advanced Data Monitoring & Performance Tracking Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Monitoring Module - Module avancé de monitoring des données et de suivi des performances
pour le Hedge Bot. Assure la surveillance en temps réel des opérations, le tracking des performances,
la détection des goulots d'étranglement et l'optimisation continue du système de hedging.
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
import hashlib

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_monitoring")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionResult
)


# ============== ENUMS & TYPES ==============

class MonitoringMetricType(Enum):
    """Types de métriques de monitoring."""
    PERFORMANCE = "performance"
    RESOURCE = "resource"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR = "error"
    AVAILABILITY = "availability"
    QUALITY = "quality"
    BUSINESS = "business"


class MonitoringAlertLevel(Enum):
    """Niveaux d'alerte."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MonitoringPeriod(Enum):
    """Périodes de monitoring."""
    REAL_TIME = "real_time"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# ============== DATA MODELS ==============

@dataclass
class MonitoringMetric:
    """Métrique de monitoring."""
    metric_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    metric_type: MonitoringMetricType = MonitoringMetricType.PERFORMANCE
    value: float = 0.0
    unit: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    dimensions: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "metric_type": self.metric_type.value,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp.isoformat(),
            "dimensions": self.dimensions,
            "tags": self.tags,
            "metadata": self.metadata
        }


@dataclass
class MonitoringAlert:
    """Alerte de monitoring."""
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    level: MonitoringAlertLevel = MonitoringAlertLevel.WARNING
    message: str = ""
    metric: str = ""
    threshold: float = 0.0
    current_value: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged: bool = False
    resolved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class MonitoringReport:
    """Rapport de monitoring."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    period: MonitoringPeriod = MonitoringPeriod.DAILY
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc) - timedelta(days=1))
    end_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metrics: List[MonitoringMetric] = field(default_factory=list)
    alerts: List[MonitoringAlert] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitoringDashboard:
    """Dashboard de monitoring."""
    dashboard_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    widgets: List[Dict[str, Any]] = field(default_factory=list)
    refresh_interval: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============== INTERFACES ==============

class MonitoringEngineInterface(ABC):
    """Interface abstraite pour le moteur de monitoring."""
    
    @abstractmethod
    async def record_metric(self, metric: MonitoringMetric) -> str:
        """Enregistre une métrique."""
        pass
    
    @abstractmethod
    async def create_alert(self, alert: MonitoringAlert) -> str:
        """Crée une alerte."""
        pass
    
    @abstractmethod
    async def generate_report(self, period: MonitoringPeriod) -> MonitoringReport:
        """Génère un rapport de monitoring."""
        pass


# ============== IMPLÉMENTATION ==============

class MonitoringEngine(MonitoringEngineInterface):
    """
    Moteur de monitoring avancé pour le Hedge Bot.
    Assure la surveillance en temps réel, le tracking des performances et les alertes.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des métriques
        self._metrics: Dict[str, List[MonitoringMetric]] = defaultdict(list)
        self._metrics_lock = threading.RLock()
        
        # Gestion des alertes
        self._alerts: Dict[str, MonitoringAlert] = {}
        self._alerts_lock = threading.RLock()
        
        # Gestion des rapports
        self._reports: Dict[str, MonitoringReport] = {}
        self._reports_lock = threading.RLock()
        
        # Gestion des dashboards
        self._dashboards: Dict[str, MonitoringDashboard] = {}
        self._dashboards_lock = threading.RLock()
        
        # Cache des métriques
        self._metric_cache: Dict[str, List[float]] = defaultdict(list)
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "metrics_recorded": 0,
            "alerts_created": 0,
            "reports_generated": 0,
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
        
        logger.info("MonitoringEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "metric_history_size": 10000,
            "alert_retention_days": 30,
            "report_retention_days": 90,
            "dashboard_refresh_default": 30,
            "metric_cache_ttl": 60,
            "enable_auto_alerts": True,
            "critical_threshold": 0.9,
            "warning_threshold": 0.7,
            "anomaly_detection_enabled": True,
            "anomaly_window": 60,
            "performance_tracking_interval": 60,
            "resource_monitoring_interval": 60,
            "health_check_interval": 60
        }
    
    async def start(self) -> None:
        """Démarre le moteur de monitoring."""
        logger.info("MonitoringEngine starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._performance_tracker())
        asyncio.create_task(self._resource_monitor())
        asyncio.create_task(self._anomaly_detector())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        asyncio.create_task(self._health_checker())
        
        logger.info("MonitoringEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de monitoring."""
        logger.info("MonitoringEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("MonitoringEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def record_metric(self, metric: MonitoringMetric) -> str:
        """Enregistre une métrique."""
        start_time = time.time()
        self._stats["metrics_recorded"] += 1
        
        with self._metrics_lock:
            self._metrics[metric.name].append(metric)
            
            # Limitation de l'historique
            if len(self._metrics[metric.name]) > self.config["metric_history_size"]:
                self._metrics[metric.name] = self._metrics[metric.name][-self.config["metric_history_size"]:]
        
        # Mise à jour du cache
        with self._cache_lock:
            self._metric_cache[metric.name].append(metric.value)
            if len(self._metric_cache[metric.name]) > 100:
                self._metric_cache[metric.name] = self._metric_cache[metric.name][-100:]
        
        # Détection d'anomalies
        if self.config["anomaly_detection_enabled"]:
            await self._check_anomaly(metric)
        
        # Vérification des seuils
        if self.config["enable_auto_alerts"]:
            await self._check_thresholds(metric)
        
        # Métriques de temps
        elapsed = (time.time() - start_time) * 1000
        self._stats["avg_metric_time_ms"] = (
            self._stats["avg_metric_time_ms"] * 0.9 + elapsed * 0.1
        )
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"monitoring:metric:{metric.metric_id}",
                metric.to_dict(),
                DataType.METRICS
            )
        
        return metric.metric_id
    
    async def create_alert(self, alert: MonitoringAlert) -> str:
        """Crée une alerte."""
        self._stats["alerts_created"] += 1
        
        # Mise à jour des statistiques
        if alert.level == MonitoringAlertLevel.CRITICAL:
            self._stats["critical_alerts"] += 1
        elif alert.level == MonitoringAlertLevel.WARNING:
            self._stats["warning_alerts"] += 1
        
        with self._alerts_lock:
            self._alerts[alert.alert_id] = alert
        
        # Notification
        await self._notify_alert(alert)
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"monitoring:alert:{alert.alert_id}",
                alert.to_dict(),
                DataType.ALERT
            )
        
        logger.info(f"Alert created: {alert.name} (level={alert.level.value})")
        return alert.alert_id
    
    async def generate_report(self, period: MonitoringPeriod) -> MonitoringReport:
        """Génère un rapport de monitoring."""
        self._stats["reports_generated"] += 1
        
        start_time = self._get_period_start(period)
        end_time = datetime.now(timezone.utc)
        
        # Récupération des métriques
        metrics = []
        with self._metrics_lock:
            for metric_list in self._metrics.values():
                for metric in metric_list:
                    if start_time <= metric.timestamp <= end_time:
                        metrics.append(metric)
        
        # Récupération des alertes
        alerts = []
        with self._alerts_lock:
            for alert in self._alerts.values():
                if start_time <= alert.timestamp <= end_time:
                    alerts.append(alert)
        
        # Génération du résumé
        summary = await self._generate_summary(metrics, alerts)
        
        # Génération des recommandations
        recommendations = await self._generate_recommendations(summary)
        
        # Création du rapport
        report = MonitoringReport(
            name=f"Monitoring Report - {period.value}",
            period=period,
            start_time=start_time,
            end_time=end_time,
            metrics=metrics,
            alerts=alerts,
            summary=summary,
            recommendations=recommendations,
            metadata={"generated_by": "monitoring_engine"}
        )
        
        with self._reports_lock:
            self._reports[report.report_id] = report
        
        logger.info(f"Monitoring report generated: {report.name}")
        return report
    
    # ========== MÉTHODES PRIVÉES - PERFORMANCE ==========
    
    async def _performance_tracker(self) -> None:
        """Track les performances du système."""
        while self._is_running:
            await asyncio.sleep(self.config["performance_tracking_interval"])
            
            try:
                # Métriques de performance
                if self.data_manager:
                    # Temps de réponse moyen
                    query_time = await self.data_manager.get_avg_query_time()
                    
                    metric = MonitoringMetric(
                        name="system.performance.avg_query_time",
                        metric_type=MonitoringMetricType.PERFORMANCE,
                        value=query_time,
                        unit="ms",
                        tags=["performance", "system"]
                    )
                    await self.record_metric(metric)
                
                # Métriques de latence
                if hasattr(self, "_latency_metrics"):
                    latency = np.mean(list(self._latency_metrics.values())) if self._latency_metrics else 0
                    
                    metric = MonitoringMetric(
                        name="system.latency.avg",
                        metric_type=MonitoringMetricType.LATENCY,
                        value=latency,
                        unit="ms",
                        tags=["latency", "system"]
                    )
                    await self.record_metric(metric)
                
            except Exception as e:
                logger.error(f"Performance tracker error: {e}")
    
    async def _resource_monitor(self) -> None:
        """Monitor les ressources système."""
        while self._is_running:
            await asyncio.sleep(self.config["resource_monitoring_interval"])
            
            try:
                # CPU
                cpu_usage = psutil.cpu_percent()
                metric = MonitoringMetric(
                    name="system.resource.cpu_usage",
                    metric_type=MonitoringMetricType.RESOURCE,
                    value=cpu_usage,
                    unit="%",
                    tags=["resource", "cpu"]
                )
                await self.record_metric(metric)
                
                # Mémoire
                memory = psutil.virtual_memory()
                metric = MonitoringMetric(
                    name="system.resource.memory_usage",
                    metric_type=MonitoringMetricType.RESOURCE,
                    value=memory.percent,
                    unit="%",
                    tags=["resource", "memory"]
                )
                await self.record_metric(metric)
                
                # Disque
                disk = psutil.disk_usage('/')
                metric = MonitoringMetric(
                    name="system.resource.disk_usage",
                    metric_type=MonitoringMetricType.RESOURCE,
                    value=disk.percent,
                    unit="%",
                    tags=["resource", "disk"]
                )
                await self.record_metric(metric)
                
                # Réseau
                net = psutil.net_io_counters()
                metric = MonitoringMetric(
                    name="system.resource.network_bandwidth",
                    metric_type=MonitoringMetricType.RESOURCE,
                    value=net.bytes_sent + net.bytes_recv,
                    unit="bytes",
                    tags=["resource", "network"]
                )
                await self.record_metric(metric)
                
            except Exception as e:
                logger.error(f"Resource monitor error: {e}")
    
    # ========== MÉTHODES PRIVÉES - ANOMALIES ==========
    
    async def _anomaly_detector(self) -> None:
        """Détecte les anomalies dans les métriques."""
        while self._is_running:
            await asyncio.sleep(self.config["anomaly_window"])
            
            try:
                with self._cache_lock:
                    for metric_name, values in self._metric_cache.items():
                        if len(values) < 10:
                            continue
                        
                        recent = values[-self.config["anomaly_window"]:]
                        mean = np.mean(recent)
                        std = np.std(recent)
                        
                        if std > 0:
                            current = recent[-1]
                            z_score = (current - mean) / std
                            
                            if abs(z_score) > 3:
                                # Anomalie détectée
                                alert = MonitoringAlert(
                                    name=f"Anomaly detected: {metric_name}",
                                    level=MonitoringAlertLevel.WARNING,
                                    message=f"Z-score anomaly: {z_score:.2f}",
                                    metric=metric_name,
                                    threshold=3.0,
                                    current_value=current,
                                    tags=["anomaly", "z-score"]
                                )
                                await self.create_alert(alert)
                
            except Exception as e:
                logger.error(f"Anomaly detector error: {e}")
    
    async def _check_thresholds(self, metric: MonitoringMetric) -> None:
        """Vérifie les seuils d'une métrique."""
        # Seuils configurés
        thresholds = self.config.get("thresholds", {})
        
        if metric.name in thresholds:
            threshold = thresholds[metric.name]
            
            if metric.value > threshold["critical"]:
                alert = MonitoringAlert(
                    name=f"Critical threshold exceeded: {metric.name}",
                    level=MonitoringAlertLevel.CRITICAL,
                    message=f"Value {metric.value:.2f} exceeds critical threshold {threshold['critical']:.2f}",
                    metric=metric.name,
                    threshold=threshold["critical"],
                    current_value=metric.value,
                    tags=["threshold", "critical"]
                )
                await self.create_alert(alert)
            
            elif metric.value > threshold["warning"]:
                alert = MonitoringAlert(
                    name=f"Warning threshold exceeded: {metric.name}",
                    level=MonitoringAlertLevel.WARNING,
                    message=f"Value {metric.value:.2f} exceeds warning threshold {threshold['warning']:.2f}",
                    metric=metric.name,
                    threshold=threshold["warning"],
                    current_value=metric.value,
                    tags=["threshold", "warning"]
                )
                await self.create_alert(alert)
    
    # ========== MÉTHODES PRIVÉES - RAPPORTS ==========
    
    async def _generate_summary(self, metrics: List[MonitoringMetric], alerts: List[MonitoringAlert]) -> Dict[str, Any]:
        """Génère un résumé des métriques et alertes."""
        summary = {
            "total_metrics": len(metrics),
            "total_alerts": len(alerts),
            "critical_alerts": len([a for a in alerts if a.level == MonitoringAlertLevel.CRITICAL]),
            "warning_alerts": len([a for a in alerts if a.level == MonitoringAlertLevel.WARNING]),
            "metrics_by_type": defaultdict(int),
            "alerts_by_type": defaultdict(int),
            "performance_metrics": {},
            "resource_metrics": {},
            "availability": 100.0
        }
        
        # Métriques par type
        for metric in metrics:
            summary["metrics_by_type"][metric.metric_type.value] += 1
        
        # Alertes par type
        for alert in alerts:
            summary["alerts_by_type"][alert.level.value] += 1
        
        # Métriques de performance
        perf_metrics = [m for m in metrics if m.metric_type == MonitoringMetricType.PERFORMANCE]
        if perf_metrics:
            summary["performance_metrics"] = {
                "avg": np.mean([m.value for m in perf_metrics]),
                "max": np.max([m.value for m in perf_metrics]),
                "min": np.min([m.value for m in perf_metrics]),
                "p95": np.percentile([m.value for m in perf_metrics], 95)
            }
        
        # Métriques de ressources
        res_metrics = [m for m in metrics if m.metric_type == MonitoringMetricType.RESOURCE]
        if res_metrics:
            summary["resource_metrics"] = {
                "cpu_avg": np.mean([m.value for m in res_metrics if "cpu" in m.name.lower()]) if any("cpu" in m.name.lower() for m in res_metrics) else 0,
                "memory_avg": np.mean([m.value for m in res_metrics if "memory" in m.name.lower()]) if any("memory" in m.name.lower() for m in res_metrics) else 0,
                "disk_avg": np.mean([m.value for m in res_metrics if "disk" in m.name.lower()]) if any("disk" in m.name.lower() for m in res_metrics) else 0
            }
        
        # Disponibilité
        if alerts:
            downtime = len([a for a in alerts if a.level == MonitoringAlertLevel.CRITICAL])
            total_periods = len(metrics) + len(alerts)
            summary["availability"] = max(0, 100 - (downtime / max(1, total_periods) * 100))
        
        return summary
    
    async def _generate_recommendations(self, summary: Dict[str, Any]) -> List[str]:
        """Génère des recommandations basées sur le résumé."""
        recommendations = []
        
        # Recommandations basées sur les alertes
        if summary["critical_alerts"] > 0:
            recommendations.append(f"Critical alerts detected: {summary['critical_alerts']}. Immediate action required.")
        
        if summary["warning_alerts"] > 0:
            recommendations.append(f"Warning alerts detected: {summary['warning_alerts']}. Monitor closely.")
        
        # Recommandations basées sur les performances
        perf = summary.get("performance_metrics", {})
        if perf.get("p95", 0) > 100:
            recommendations.append("High latency detected (P95 > 100ms). Consider optimization.")
        
        # Recommandations basées sur les ressources
        res = summary.get("resource_metrics", {})
        if res.get("cpu_avg", 0) > 80:
            recommendations.append("High CPU usage detected (>80%). Consider scaling.")
        
        if res.get("memory_avg", 0) > 80:
            recommendations.append("High memory usage detected (>80%). Consider increasing resources.")
        
        if res.get("disk_avg", 0) > 80:
            recommendations.append("High disk usage detected (>80%). Consider cleaning up or expanding storage.")
        
        # Recommandations générales
        if summary["availability"] < 99:
            recommendations.append(f"System availability is {summary['availability']:.2f}%. Investigate causes of downtime.")
        
        return recommendations
    
    # ========== MÉTHODES PRIVÉES - NOTIFICATIONS ==========
    
    async def _notify_alert(self, alert: MonitoringAlert) -> None:
        """Notifie une alerte."""
        if alert.level == MonitoringAlertLevel.CRITICAL:
            logger.critical(f"CRITICAL: {alert.name} - {alert.message}")
        elif alert.level == MonitoringAlertLevel.ERROR:
            logger.error(f"ERROR: {alert.name} - {alert.message}")
        elif alert.level == MonitoringAlertLevel.WARNING:
            logger.warning(f"WARNING: {alert.name} - {alert.message}")
        else:
            logger.info(f"INFO: {alert.name} - {alert.message}")
    
    def _get_period_start(self, period: MonitoringPeriod) -> datetime:
        """Calcule le début de période."""
        now = datetime.now(timezone.utc)
        
        if period == MonitoringPeriod.REAL_TIME:
            return now - timedelta(minutes=5)
        elif period == MonitoringPeriod.HOURLY:
            return now - timedelta(hours=1)
        elif period == MonitoringPeriod.DAILY:
            return now - timedelta(days=1)
        elif period == MonitoringPeriod.WEEKLY:
            return now - timedelta(weeks=1)
        elif period == MonitoringPeriod.MONTHLY:
            return now - timedelta(days=30)
        else:
            return now - timedelta(days=1)
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    for name, values in self._metric_cache.items():
                        if len(values) > 1000:
                            self._metric_cache[name] = values[-1000:]
                
                # Nettoyage des alertes résolues
                with self._alerts_lock:
                    cutoff = datetime.now(timezone.utc) - timedelta(days=self.config["alert_retention_days"])
                    resolved = [
                        aid for aid, alert in self._alerts.items()
                        if alert.resolved and alert.timestamp < cutoff
                    ]
                    for aid in resolved:
                        del self._alerts[aid]
                
                # Nettoyage des rapports
                with self._reports_lock:
                    cutoff = datetime.now(timezone.utc) - timedelta(days=self.config["report_retention_days"])
                    old_reports = [
                        rid for rid, report in self._reports.items()
                        if report.end_time < cutoff
                    ]
                    for rid in old_reports:
                        del self._reports[rid]
                
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
                    active_alerts = len([a for a in self._alerts.values() if not a.resolved])
                    self._stats["active_alerts"] = active_alerts
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "monitoring:stats",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    async def _health_checker(self) -> None:
        """Vérifie la santé du système."""
        while self._is_running:
            await asyncio.sleep(self.config["health_check_interval"])
            
            try:
                # Vérification des services
                health_status = {}
                
                # Vérification du data manager
                if self.data_manager:
                    try:
                        health = await self.data_manager.health_check()
                        health_status["data_manager"] = health
                    except:
                        health_status["data_manager"] = False
                
                # Vérification du système
                health_status["system"] = True
                
                # Enregistrement de la métrique de santé
                metric = MonitoringMetric(
                    name="system.health_status",
                    metric_type=MonitoringMetricType.AVAILABILITY,
                    value=100 if all(health_status.values()) else 0,
                    unit="%",
                    tags=["health", "system"],
                    metadata=health_status
                )
                await self.record_metric(metric)
                
                # Alerte si problème
                if not all(health_status.values()):
                    alert = MonitoringAlert(
                        name="System health degraded",
                        level=MonitoringAlertLevel.ERROR,
                        message="One or more services are unhealthy",
                        metric="system.health_status",
                        threshold=100,
                        current_value=0,
                        tags=["health", "system"],
                        metadata=health_status
                    )
                    await self.create_alert(alert)
                
            except Exception as e:
                logger.error(f"Health checker error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Résout une alerte."""
        with self._alerts_lock:
            alert = self._alerts.get(alert_id)
            if not alert or alert.resolved:
                return False
            
            alert.resolved = True
            self._stats["alerts_resolved"] += 1
            return True
    
    async def get_metric_stats(self, name: str) -> Dict[str, float]:
        """Récupère les statistiques d'une métrique."""
        with self._metrics_lock:
            metrics = self._metrics.get(name, [])
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
    
    async def create_dashboard(self, dashboard: MonitoringDashboard) -> str:
        """Crée un dashboard de monitoring."""
        with self._dashboards_lock:
            self._dashboards[dashboard.dashboard_id] = dashboard
        
        logger.info(f"Monitoring dashboard created: {dashboard.name}")
        return dashboard.dashboard_id
    
    async def get_dashboard(self, dashboard_id: str) -> Optional[MonitoringDashboard]:
        """Récupère un dashboard."""
        with self._dashboards_lock:
            return self._dashboards.get(dashboard_id)
    
    async def get_dashboards(self) -> List[MonitoringDashboard]:
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


# ============== MONITORING DASHBOARD BUILDER ==============

class MonitoringDashboardBuilder:
    """
    Constructeur de dashboards de monitoring.
    Facilite la création de dashboards pour le monitoring.
    """
    
    def __init__(self):
        self._dashboard = MonitoringDashboard()
        self._widgets = []
    
    def name(self, name: str) -> 'MonitoringDashboardBuilder':
        """Définit le nom du dashboard."""
        self._dashboard.name = name
        return self
    
    def add_widget(self, widget_type: str, config: Dict[str, Any]) -> 'MonitoringDashboardBuilder':
        """Ajoute un widget."""
        self._widgets.append({
            "type": widget_type,
            "config": config
        })
        return self
    
    def refresh_interval(self, interval: int) -> 'MonitoringDashboardBuilder':
        """Définit l'intervalle de rafraîchissement."""
        self._dashboard.refresh_interval = interval
        return self
    
    def tags(self, tags: List[str]) -> 'MonitoringDashboardBuilder':
        """Définit les tags."""
        self._dashboard.tags = tags
        return self
    
    def metadata(self, metadata: Dict[str, Any]) -> 'MonitoringDashboardBuilder':
        """Définit les métadonnées."""
        self._dashboard.metadata = metadata
        return self
    
    def build(self) -> MonitoringDashboard:
        """Construit le dashboard."""
        self._dashboard.widgets = self._widgets
        return self._dashboard


# ============== FACTORY ==============

class MonitoringFactory:
    """Factory pour créer des composants de monitoring."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> MonitoringEngine:
        """Crée un moteur de monitoring."""
        engine = MonitoringEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_dashboard_builder() -> MonitoringDashboardBuilder:
        """Crée un constructeur de dashboards."""
        return MonitoringDashboardBuilder()


# ============== EXPORT ==============

__all__ = [
    "MonitoringMetricType",
    "MonitoringAlertLevel",
    "MonitoringPeriod",
    "MonitoringMetric",
    "MonitoringAlert",
    "MonitoringReport",
    "MonitoringDashboard",
    "MonitoringEngineInterface",
    "MonitoringEngine",
    "MonitoringDashboardBuilder",
    "MonitoringFactory"
]
