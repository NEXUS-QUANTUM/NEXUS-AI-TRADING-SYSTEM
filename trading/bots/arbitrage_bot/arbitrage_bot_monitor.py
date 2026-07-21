"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Monitor
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Système de monitoring avancé pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import json
import threading
import subprocess
import psutil
import platform
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Callable
from pathlib import Path
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum

# Imports internes
from .arbitrage_bot_health import ArbitrageBotHealth, HealthCheckResult
from .arbitrage_bot_metrics import ArbitrageBotMetrics, get_metrics
from .arbitrage_bot_logger import get_logger, LogCategory

# ============================================================
# LOGGING
# ============================================================
logger = get_logger()

# ============================================================
# ENUMS
# ============================================================

class MonitorStatus(Enum):
    """Statuts de monitoring"""
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"

class AlertSeverity(Enum):
    """Sévérités d'alerte"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class MonitorEventType(Enum):
    """Types d'événements de monitoring"""
    SYSTEM = "system"
    PERFORMANCE = "performance"
    ERROR = "error"
    WARNING = "warning"
    RECOVERY = "recovery"
    STATUS_CHANGE = "status_change"
    METRIC_THRESHOLD = "metric_threshold"
    RESOURCE_USAGE = "resource_usage"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class MonitorEvent:
    """Événement de monitoring"""
    type: MonitorEventType
    severity: AlertSeverity
    message: str
    timestamp: float = field(default_factory=time.time)
    details: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None

@dataclass
class ResourceUsage:
    """Utilisation des ressources"""
    cpu_percent: float
    memory_percent: float
    memory_used: float
    memory_total: float
    disk_usage_percent: float
    network_bytes_sent: float
    network_bytes_recv: float
    process_count: int
    thread_count: int
    open_files: int
    connections: int

@dataclass
class PerformanceMetrics:
    """Métriques de performance"""
    throughput: float
    latency_avg: float
    latency_p95: float
    latency_p99: float
    error_rate: float
    success_rate: float
    request_rate: float
    response_time: float

# ============================================================
# MONITOR
# ============================================================

class ArbitrageBotMonitor:
    """
    Système de monitoring avancé pour le bot d'arbitrage
    
    Surveille les performances, les ressources, génère des alertes
    et fournit des tableaux de bord en temps réel
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
        enabled: bool = True,
        collect_interval: int = 10,
        alert_interval: int = 60,
        retention_days: int = 7,
        resource_thresholds: Optional[Dict[str, float]] = None,
        performance_thresholds: Optional[Dict[str, float]] = None,
        enable_dashboard: bool = True,
        dashboard_port: int = 8500
    ):
        """
        Initialise le système de monitoring
        
        Args:
            enabled: Activer le monitoring
            collect_interval: Intervalle de collecte en secondes
            alert_interval: Intervalle d'alertes en secondes
            retention_days: Jours de rétention des données
            resource_thresholds: Seuils de ressources
            performance_thresholds: Seuils de performance
            enable_dashboard: Activer le tableau de bord
            dashboard_port: Port du tableau de bord
        """
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.enabled = enabled
        self.collect_interval = collect_interval
        self.alert_interval = alert_interval
        self.retention_days = retention_days
        self.resource_thresholds = resource_thresholds or {
            'cpu': 80.0,
            'memory': 80.0,
            'disk': 80.0,
        }
        self.performance_thresholds = performance_thresholds or {
            'latency': 100.0,
            'error_rate': 5.0,
            'throughput': 1000,
        }
        self.enable_dashboard = enable_dashboard
        self.dashboard_port = dashboard_port
        
        self._initialized = True
        
        # État
        self.status = MonitorStatus.STOPPED
        self.events: List[MonitorEvent] = []
        self.resource_history: List[ResourceUsage] = []
        self.performance_history: List[PerformanceMetrics] = []
        self.alerts: List[Dict[str, Any]] = []
        
        # Composants
        self.health_checker = ArbitrageBotHealth()
        self.metrics_system = get_metrics()
        
        # Threads
        self._collect_thread = None
        self._alert_thread = None
        self._dashboard_thread = None
        self._running = False
        
        # Statistiques
        self.stats = {
            'total_events': 0,
            'by_type': {},
            'by_severity': {},
            'alerts': 0,
            'errors': 0,
            'last_collection': None,
            'last_alert': None,
        }
        
        if self.enabled:
            self.start()
        
        logger.info("Monitor initialized", category=LogCategory.SYSTEM)
    
    def start(self):
        """Démarre le monitoring"""
        if self._running:
            logger.warning("Monitor already running")
            return
        
        self._running = True
        self.status = MonitorStatus.RUNNING
        
        # Démarrer les threads
        self._collect_thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._collect_thread.start()
        
        self._alert_thread = threading.Thread(target=self._alert_loop, daemon=True)
        self._alert_thread.start()
        
        if self.enable_dashboard:
            self._dashboard_thread = threading.Thread(target=self._start_dashboard, daemon=True)
            self._dashboard_thread.start()
        
        logger.info("Monitor started", category=LogCategory.SYSTEM)
    
    def stop(self):
        """Arrête le monitoring"""
        if not self._running:
            logger.warning("Monitor not running")
            return
        
        self._running = False
        self.status = MonitorStatus.STOPPED
        
        # Arrêter les threads
        if self._collect_thread:
            self._collect_thread.join(timeout=2)
        if self._alert_thread:
            self._alert_thread.join(timeout=2)
        if self._dashboard_thread:
            self._dashboard_thread.join(timeout=2)
        
        logger.info("Monitor stopped", category=LogCategory.SYSTEM)
    
    def pause(self):
        """Met en pause le monitoring"""
        self.status = MonitorStatus.PAUSED
        logger.info("Monitor paused", category=LogCategory.SYSTEM)
    
    def resume(self):
        """Reprend le monitoring"""
        self.status = MonitorStatus.RUNNING
        logger.info("Monitor resumed", category=LogCategory.SYSTEM)
    
    # ============================================================
    # COLLECTION LOOPS
    # ============================================================
    
    def _collect_loop(self):
        """Boucle de collecte"""
        while self._running:
            if self.status == MonitorStatus.RUNNING:
                try:
                    self._collect()
                except Exception as e:
                    logger.error(f"Collection error: {e}", category=LogCategory.SYSTEM)
            
            time.sleep(self.collect_interval)
    
    def _alert_loop(self):
        """Boucle d'alertes"""
        while self._running:
            if self.status == MonitorStatus.RUNNING:
                try:
                    self._check_alerts()
                except Exception as e:
                    logger.error(f"Alert check error: {e}", category=LogCategory.SYSTEM)
            
            time.sleep(self.alert_interval)
    
    def _collect(self):
        """Collecte les données"""
        # Ressources système
        resource_usage = self._collect_resources()
        self.resource_history.append(resource_usage)
        
        # Métriques de performance
        performance = self._collect_performance()
        self.performance_history.append(performance)
        
        # Nettoyer l'historique
        self._clean_history()
        
        self.stats['last_collection'] = datetime.now().isoformat()
        
        # Ajouter un événement
        self._add_event(
            type=MonitorEventType.SYSTEM,
            severity=AlertSeverity.INFO,
            message="Data collection completed",
            details={
                'resources': resource_usage.__dict__,
                'performance': performance.__dict__,
            }
        )
        
        logger.debug("Data collected", category=LogCategory.SYSTEM)
    
    def _collect_resources(self) -> ResourceUsage:
        """Collecte l'utilisation des ressources"""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.5)
        
        # Mémoire
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used = memory.used / (1024 * 1024)  # MB
        memory_total = memory.total / (1024 * 1024)  # MB
        
        # Disque
        disk = psutil.disk_usage('/')
        disk_usage_percent = disk.percent
        
        # Réseau
        network = psutil.net_io_counters()
        network_bytes_sent = network.bytes_sent / (1024 * 1024)  # MB
        network_bytes_recv = network.bytes_recv / (1024 * 1024)  # MB
        
        # Processus
        process = psutil.Process()
        process_count = len(psutil.pids())
        thread_count = process.num_threads()
        open_files = len(process.open_files())
        connections = len(process.connections())
        
        return ResourceUsage(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used=memory_used,
            memory_total=memory_total,
            disk_usage_percent=disk_usage_percent,
            network_bytes_sent=network_bytes_sent,
            network_bytes_recv=network_bytes_recv,
            process_count=process_count,
            thread_count=thread_count,
            open_files=open_files,
            connections=connections
        )
    
    def _collect_performance(self) -> PerformanceMetrics:
        """Collecte les métriques de performance"""
        # Récupérer les métriques
        metrics = self.metrics_system.get_all_metrics()
        
        # Calculer les métriques
        throughput = self._calculate_throughput(metrics)
        latency = self._calculate_latency(metrics)
        error_rate = self._calculate_error_rate(metrics)
        success_rate = 1 - error_rate
        request_rate = self._calculate_request_rate(metrics)
        response_time = self._calculate_response_time(metrics)
        
        return PerformanceMetrics(
            throughput=throughput,
            latency_avg=latency.get('avg', 0),
            latency_p95=latency.get('p95', 0),
            latency_p99=latency.get('p99', 0),
            error_rate=error_rate,
            success_rate=success_rate,
            request_rate=request_rate,
            response_time=response_time
        )
    
    def _calculate_throughput(self, metrics: Dict[str, Any]) -> float:
        """Calcule le débit"""
        # Utiliser les métriques de volume de trades
        trade_count = metrics.get('trades.total', {}).get('value', 0)
        return trade_count / self.collect_interval
    
    def _calculate_latency(self, metrics: Dict[str, Any]) -> Dict[str, float]:
        """Calcule la latence"""
        # Utiliser les métriques de latence
        latencies = []
        
        for key, metric in metrics.items():
            if 'latency' in key.lower():
                if isinstance(metric, dict):
                    value = metric.get('value', 0)
                    if value > 0:
                        latencies.append(value)
        
        if not latencies:
            return {'avg': 0, 'p95': 0, 'p99': 0}
        
        sorted_latencies = sorted(latencies)
        
        return {
            'avg': sum(latencies) / len(latencies),
            'p95': sorted_latencies[int(len(sorted_latencies) * 0.95)],
            'p99': sorted_latencies[int(len(sorted_latencies) * 0.99)],
        }
    
    def _calculate_error_rate(self, metrics: Dict[str, Any]) -> float:
        """Calcule le taux d'erreur"""
        total = metrics.get('requests.total', {}).get('value', 1)
        errors = metrics.get('requests.errors', {}).get('value', 0)
        return errors / total if total > 0 else 0
    
    def _calculate_request_rate(self, metrics: Dict[str, Any]) -> float:
        """Calcule le taux de requêtes"""
        total = metrics.get('requests.total', {}).get('value', 0)
        return total / self.collect_interval
    
    def _calculate_response_time(self, metrics: Dict[str, Any]) -> float:
        """Calcule le temps de réponse"""
        # Utiliser les métriques de temps de réponse
        response_times = []
        
        for key, metric in metrics.items():
            if 'response_time' in key.lower():
                if isinstance(metric, dict):
                    value = metric.get('value', 0)
                    if value > 0:
                        response_times.append(value)
        
        if not response_times:
            return 0
        
        return sum(response_times) / len(response_times)
    
    # ============================================================
    # ALERT CHECKING
    # ============================================================
    
    def _check_alerts(self):
        """Vérifie les alertes"""
        # Vérifier les seuils de ressources
        if self.resource_history:
            latest = self.resource_history[-1]
            
            # CPU
            if latest.cpu_percent > self.resource_thresholds['cpu']:
                self._trigger_alert(
                    severity=AlertSeverity.WARNING,
                    message=f"CPU usage high: {latest.cpu_percent:.1f}%",
                    details={'resource': 'cpu', 'value': latest.cpu_percent}
                )
            
            # Mémoire
            if latest.memory_percent > self.resource_thresholds['memory']:
                self._trigger_alert(
                    severity=AlertSeverity.WARNING,
                    message=f"Memory usage high: {latest.memory_percent:.1f}%",
                    details={'resource': 'memory', 'value': latest.memory_percent}
                )
            
            # Disque
            if latest.disk_usage_percent > self.resource_thresholds['disk']:
                self._trigger_alert(
                    severity=AlertSeverity.WARNING,
                    message=f"Disk usage high: {latest.disk_usage_percent:.1f}%",
                    details={'resource': 'disk', 'value': latest.disk_usage_percent}
                )
        
        # Vérifier les seuils de performance
        if self.performance_history:
            latest = self.performance_history[-1]
            
            # Latence
            if latest.latency_avg > self.performance_thresholds['latency']:
                self._trigger_alert(
                    severity=AlertSeverity.WARNING,
                    message=f"High latency: {latest.latency_avg:.1f}ms",
                    details={'performance': 'latency', 'value': latest.latency_avg}
                )
            
            # Taux d'erreur
            if latest.error_rate * 100 > self.performance_thresholds['error_rate']:
                self._trigger_alert(
                    severity=AlertSeverity.CRITICAL,
                    message=f"High error rate: {latest.error_rate*100:.1f}%",
                    details={'performance': 'error_rate', 'value': latest.error_rate}
                )
            
            # Débit
            if latest.throughput < self.performance_thresholds['throughput']:
                self._trigger_alert(
                    severity=AlertSeverity.WARNING,
                    message=f"Low throughput: {latest.throughput:.1f}",
                    details={'performance': 'throughput', 'value': latest.throughput}
                )
        
        self.stats['last_alert'] = datetime.now().isoformat()
    
    def _trigger_alert(
        self,
        severity: AlertSeverity,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Déclenche une alerte"""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'severity': severity.value,
            'message': message,
            'details': details or {},
        }
        
        self.alerts.append(alert)
        self.stats['alerts'] += 1
        
        # Ajouter un événement
        self._add_event(
            type=MonitorEventType.METRIC_THRESHOLD,
            severity=severity,
            message=message,
            details=details or {}
        )
        
        # Log
        if severity == AlertSeverity.CRITICAL or severity == AlertSeverity.EMERGENCY:
            logger.critical(message, category=LogCategory.SYSTEM, details=details)
        elif severity == AlertSeverity.WARNING:
            logger.warning(message, category=LogCategory.SYSTEM, details=details)
        else:
            logger.info(message, category=LogCategory.SYSTEM, details=details)
    
    def _add_event(
        self,
        type: MonitorEventType,
        severity: AlertSeverity,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None
    ):
        """Ajoute un événement"""
        event = MonitorEvent(
            type=type,
            severity=severity,
            message=message,
            details=details or {},
            source=source or 'monitor'
        )
        
        self.events.append(event)
        self.stats['total_events'] += 1
        
        # Mettre à jour les statistiques
        type_key = type.value
        self.stats['by_type'][type_key] = self.stats['by_type'].get(type_key, 0) + 1
        
        severity_key = severity.value
        self.stats['by_severity'][severity_key] = self.stats['by_severity'].get(severity_key, 0) + 1
    
    # ============================================================
    # HISTORY MANAGEMENT
    # ============================================================
    
    def _clean_history(self):
        """Nettoie l'historique"""
        retention_seconds = self.retention_days * 24 * 3600
        current_time = time.time()
        
        # Nettoyer les événements
        self.events = [
            e for e in self.events
            if current_time - e.timestamp <= retention_seconds
        ]
        
        # Nettoyer les alertes
        self.alerts = [
            a for a in self.alerts
            if current_time - self._parse_timestamp(a['timestamp']) <= retention_seconds
        ]
    
    def _parse_timestamp(self, timestamp_str: str) -> float:
        """Parse un timestamp"""
        try:
            dt = datetime.fromisoformat(timestamp_str)
            return dt.timestamp()
        except:
            return 0
    
    # ============================================================
    # DASHBOARD
    # ============================================================
    
    def _start_dashboard(self):
        """Démarre le tableau de bord"""
        try:
            from .arbitrage_bot_dashboard import ArbitrageBotDashboard
            dashboard = ArbitrageBotDashboard(
                bot=None,
                port=self.dashboard_port
            )
            dashboard.run(open_browser=False)
        except ImportError:
            logger.warning("Dashboard not available", category=LogCategory.SYSTEM)
        except Exception as e:
            logger.error(f"Dashboard error: {e}", category=LogCategory.SYSTEM)
    
    # ============================================================
    # QUERY METHODS
    # ============================================================
    
    def get_events(
        self,
        limit: int = 100,
        since: Optional[datetime] = None,
        severity: Optional[str] = None,
        type: Optional[str] = None
    ) -> List[MonitorEvent]:
        """
        Récupère les événements
        
        Args:
            limit: Nombre maximum d'événements
            since: Depuis quand
            severity: Sévérité
            type: Type
            
        Returns:
            List[MonitorEvent]: Événements
        """
        events = self.events
        
        if since:
            since_ts = since.timestamp()
            events = [e for e in events if e.timestamp >= since_ts]
        
        if severity:
            events = [e for e in events if e.severity.value == severity]
        
        if type:
            events = [e for e in events if e.type.value == type]
        
        return events[-limit:]
    
    def get_alerts(
        self,
        limit: int = 100,
        since: Optional[datetime] = None,
        severity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Récupère les alertes
        
        Args:
            limit: Nombre maximum d'alertes
            since: Depuis quand
            severity: Sévérité
            
        Returns:
            List[Dict[str, Any]]: Alertes
        """
        alerts = self.alerts
        
        if since:
            since_ts = since.timestamp()
            alerts = [
                a for a in alerts
                if self._parse_timestamp(a['timestamp']) >= since_ts
            ]
        
        if severity:
            alerts = [a for a in alerts if a.get('severity') == severity]
        
        return alerts[-limit:]
    
    def get_resources(
        self,
        limit: int = 100
    ) -> List[ResourceUsage]:
        """
        Récupère l'historique des ressources
        
        Args:
            limit: Nombre maximum d'entrées
            
        Returns:
            List[ResourceUsage]: Historique des ressources
        """
        return self.resource_history[-limit:]
    
    def get_performance(
        self,
        limit: int = 100
    ) -> List[PerformanceMetrics]:
        """
        Récupère l'historique des performances
        
        Args:
            limit: Nombre maximum d'entrées
            
        Returns:
            List[PerformanceMetrics]: Historique des performances
        """
        return self.performance_history[-limit:]
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Récupère un résumé
        
        Returns:
            Dict[str, Any]: Résumé
        """
        # Dernières métriques
        latest_resources = self.resource_history[-1] if self.resource_history else None
        latest_performance = self.performance_history[-1] if self.performance_history else None
        
        # Dernières alertes
        latest_alerts = self.alerts[-5:] if self.alerts else []
        
        # Statut général
        status = 'healthy'
        if any(a.get('severity') == 'critical' for a in latest_alerts):
            status = 'critical'
        elif any(a.get('severity') == 'warning' for a in latest_alerts):
            status = 'warning'
        
        return {
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'resources': latest_resources.__dict__ if latest_resources else None,
            'performance': latest_performance.__dict__ if latest_performance else None,
            'alerts': latest_alerts,
            'stats': self.stats,
            'events_today': len([
                e for e in self.events
                if datetime.fromtimestamp(e.timestamp).date() == datetime.now().date()
            ]),
        }

# ============================================================
# GLOBAL MONITOR INSTANCE
# ============================================================

_monitor: Optional[ArbitrageBotMonitor] = None

def get_monitor(
    enabled: bool = True,
    **kwargs
) -> ArbitrageBotMonitor:
    """
    Récupère le système de monitoring global
    
    Args:
        enabled: Activer le monitoring
        **kwargs: Arguments supplémentaires
        
    Returns:
        ArbitrageBotMonitor: Système de monitoring
    """
    global _monitor
    if _monitor is None:
        _monitor = ArbitrageBotMonitor(enabled=enabled, **kwargs)
    return _monitor

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'MonitorStatus',
    'AlertSeverity',
    'MonitorEventType',
    'MonitorEvent',
    'ResourceUsage',
    'PerformanceMetrics',
    'ArbitrageBotMonitor',
    'get_monitor',
]

# ============================================================
# INITIALIZATION
# ============================================================

# Créer l'instance par défaut
monitor = get_monitor()

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    # Test du monitor
    monitor = get_monitor()
    
    print("Starting monitor...")
    monitor.start()
    
    # Simuler une activité
    print("Simulating activity...")
    for i in range(5):
        time.sleep(5)
        summary = monitor.get_summary()
        print(f"Status: {summary['status']}")
    
    monitor.stop()
    print("Monitor stopped")
