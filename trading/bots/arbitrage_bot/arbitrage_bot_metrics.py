"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Metrics
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Système de métriques avancé pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import time
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Callable
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import statistics

# Imports internes
from .utils import (
    StatisticsUtils,
    NumberFormatter,
    DateTimeFormatter,
)

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class MetricType(Enum):
    """Types de métriques"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    TIMER = "timer"

class MetricUnit(Enum):
    """Unités de métriques"""
    COUNT = "count"
    PERCENT = "percent"
    MILLISECONDS = "ms"
    SECONDS = "s"
    BYTES = "bytes"
    RATE = "rate"
    RATIO = "ratio"
    CURRENCY = "currency"

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class Metric:
    """Métrique"""
    name: str
    type: MetricType
    value: Any
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)
    unit: Optional[MetricUnit] = None
    description: Optional[str] = None

@dataclass
class MetricSnapshot:
    """Snapshot de métrique"""
    name: str
    type: MetricType
    value: Any
    timestamp: float
    labels: Dict[str, str]
    unit: Optional[MetricUnit]
    description: Optional[str]
    count: Optional[int] = None
    sum: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    p50: Optional[float] = None
    p95: Optional[float] = None
    p99: Optional[float] = None

# ============================================================
# METRICS COLLECTOR
# ============================================================

class ArbitrageBotMetrics:
    """
    Système de métriques pour le bot d'arbitrage
    
    Collecte, agrège et expose les métriques de performance
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
        retention_period: int = 3600,
        flush_interval: int = 60,
        max_metrics: int = 10000,
        enable_export: bool = True,
        export_format: str = "json",
        export_path: Optional[str] = None
    ):
        """
        Initialise le système de métriques
        
        Args:
            enabled: Activer les métriques
            retention_period: Période de rétention en secondes
            flush_interval: Intervalle de vidage en secondes
            max_metrics: Nombre maximum de métriques
            enable_export: Activer l'export
            export_format: Format d'export
            export_path: Chemin d'export
        """
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.enabled = enabled
        self.retention_period = retention_period
        self.flush_interval = flush_interval
        self.max_metrics = max_metrics
        self.enable_export = enable_export
        self.export_format = export_format
        self.export_path = export_path or "metrics/arbitrage_metrics"
        
        self._initialized = True
        
        # Métriques
        self._metrics: Dict[str, Metric] = {}
        self._history: Dict[str, List[Metric]] = defaultdict(list)
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self _timers: Dict[str, List[float]] = defaultdict(list)
        
        # Verrous
        self._lock = threading.RLock()
        self._flush_thread = None
        self._running = False
        
        # Statistiques
        self.stats = {
            'total_metrics': 0,
            'collected_metrics': 0,
            'exported_metrics': 0,
            'errors': 0,
            'last_flush': None,
        }
        
        if self.enabled:
            self._start()
        
        logger.info("Metrics system initialized")
    
    def _start(self):
        """Démarre le système de métriques"""
        self._running = True
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()
        logger.info("Metrics collection started")
    
    def _stop(self):
        """Arrête le système de métriques"""
        self._running = False
        if self._flush_thread:
            self._flush_thread.join(timeout=2)
        self._flush()
        logger.info("Metrics collection stopped")
    
    def _flush_loop(self):
        """Boucle de vidage"""
        while self._running:
            try:
                time.sleep(self.flush_interval)
                self._flush()
            except Exception as e:
                logger.error(f"Flush loop error: {e}")
    
    def _flush(self):
        """Vide les métriques"""
        if not self.enabled:
            return
        
        with self._lock:
            # Supprimer les métriques expirées
            now = time.time()
            for name, metrics in list(self._history.items()):
                self._history[name] = [
                    m for m in metrics
                    if now - m.timestamp <= self.retention_period
                ]
                if not self._history[name]:
                    del self._history[name]
            
            # Limiter la taille
            total_metrics = sum(len(m) for m in self._history.values())
            if total_metrics > self.max_metrics:
                # Supprimer les plus anciennes
                for name in list(self._history.keys()):
                    if total_metrics <= self.max_metrics:
                        break
                    remove_count = min(
                        len(self._history[name]),
                        total_metrics - self.max_metrics
                    )
                    self._history[name] = self._history[name][remove_count:]
                    total_metrics -= remove_count
            
            self.stats['last_flush'] = datetime.now().isoformat()
            
            # Exporter
            if self.enable_export:
                self._export()
    
    def _export(self):
        """Exporte les métriques"""
        try:
            snapshot = self.get_snapshot()
            
            # Créer le répertoire
            export_dir = Path(self.export_path).parent
            export_dir.mkdir(parents=True, exist_ok=True)
            
            # Formater la date
            date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if self.export_format == "json":
                file_path = f"{self.export_path}_{date_str}.json"
                with open(file_path, 'w') as f:
                    json.dump(snapshot, f, indent=2, default=str)
            elif self.export_format == "csv":
                file_path = f"{self.export_path}_{date_str}.csv"
                import csv
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['name', 'type', 'value', 'timestamp', 'unit'])
                    for metric in snapshot:
                        writer.writerow([
                            metric['name'],
                            metric['type'],
                            metric['value'],
                            metric['timestamp'],
                            metric.get('unit', '')
                        ])
            
            self.stats['exported_metrics'] += len(snapshot)
            
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Export error: {e}")
    
    # ============================================================
    # METRIC COLLECTION
    # ============================================================
    
    def counter(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None) -> int:
        """
        Incrémente un compteur
        
        Args:
            name: Nom de la métrique
            value: Valeur à ajouter
            labels: Labels
            
        Returns:
            int: Nouvelle valeur
        """
        if not self.enabled:
            return 0
        
        with self._lock:
            self._counters[name] += value
            current_value = self._counters[name]
            
            metric = Metric(
                name=name,
                type=MetricType.COUNTER,
                value=current_value,
                labels=labels or {},
                unit=MetricUnit.COUNT
            )
            self._add_metric(name, metric)
            
            return current_value
    
    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> float:
        """
        Définit un gauge
        
        Args:
            name: Nom de la métrique
            value: Valeur
            labels: Labels
            
        Returns:
            float: Valeur définie
        """
        if not self.enabled:
            return 0
        
        with self._lock:
            self._gauges[name] = value
            
            metric = Metric(
                name=name,
                type=MetricType.GAUGE,
                value=value,
                labels=labels or {},
                unit=MetricUnit.COUNT
            )
            self._add_metric(name, metric)
            
            return value
    
    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> List[float]:
        """
        Ajoute une valeur à un histogramme
        
        Args:
            name: Nom de la métrique
            value: Valeur
            labels: Labels
            
        Returns:
            List[float]: Historique
        """
        if not self.enabled:
            return []
        
        with self._lock:
            self._histograms[name].append(value)
            
            # Limiter la taille
            if len(self._histograms[name]) > 1000:
                self._histograms[name] = self._histograms[name][-1000:]
            
            metric = Metric(
                name=name,
                type=MetricType.HISTOGRAM,
                value=value,
                labels=labels or {}
            )
            self._add_metric(name, metric)
            
            return self._histograms[name]
    
    def timer(self, name: str, duration: float, labels: Optional[Dict[str, str]] = None) -> float:
        """
        Enregistre une durée
        
        Args:
            name: Nom de la métrique
            duration: Durée en secondes
            labels: Labels
            
        Returns:
            float: Durée enregistrée
        """
        if not self.enabled:
            return 0
        
        with self._lock:
            self._timers[name].append(duration)
            
            # Limiter la taille
            if len(self._timers[name]) > 1000:
                self._timers[name] = self._timers[name][-1000:]
            
            metric = Metric(
                name=name,
                type=MetricType.TIMER,
                value=duration * 1000,  # Convertir en ms
                labels=labels or {},
                unit=MetricUnit.MILLISECONDS
            )
            self._add_metric(name, metric)
            
            return duration
    
    def _add_metric(self, name: str, metric: Metric):
        """Ajoute une métrique"""
        self._metrics[name] = metric
        self._history[name].append(metric)
        self.stats['collected_metrics'] += 1
        self.stats['total_metrics'] = len(self._metrics)
    
    # ============================================================
    # METRIC QUERYING
    # ============================================================
    
    def get_metric(self, name: str) -> Optional[Metric]:
        """
        Récupère une métrique
        
        Args:
            name: Nom de la métrique
            
        Returns:
            Optional[Metric]: Métrique
        """
        with self._lock:
            return self._metrics.get(name)
    
    def get_history(self, name: str, limit: int = 100) -> List[Metric]:
        """
        Récupère l'historique d'une métrique
        
        Args:
            name: Nom de la métrique
            limit: Nombre d'entrées
            
        Returns:
            List[Metric]: Historique
        """
        with self._lock:
            history = self._history.get(name, [])
            return history[-limit:]
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Récupère toutes les métriques
        
        Returns:
            Dict[str, Any]: Métriques
        """
        with self._lock:
            return {
                name: {
                    'type': metric.type.value,
                    'value': metric.value,
                    'timestamp': metric.timestamp,
                    'labels': metric.labels,
                    'unit': metric.unit.value if metric.unit else None,
                }
                for name, metric in self._metrics.items()
            }
    
    def get_snapshot(self) -> List[Dict[str, Any]]:
        """
        Récupère un snapshot des métriques
        
        Returns:
            List[Dict[str, Any]]: Snapshot
        """
        snapshot = []
        
        with self._lock:
            for name, metric in self._metrics.items():
                entry = {
                    'name': name,
                    'type': metric.type.value,
                    'value': metric.value,
                    'timestamp': metric.timestamp,
                    'labels': metric.labels,
                }
                
                if metric.unit:
                    entry['unit'] = metric.unit.value
                
                if metric.description:
                    entry['description'] = metric.description
                
                # Ajouter des statistiques pour les histogrammes
                if metric.type == MetricType.HISTOGRAM and name in self._histograms:
                    values = self._histograms[name]
                    if values:
                        entry['count'] = len(values)
                        entry['sum'] = sum(values)
                        entry['mean'] = statistics.mean(values)
                        entry['median'] = statistics.median(values)
                        entry['min'] = min(values)
                        entry['max'] = max(values)
                        
                        sorted_values = sorted(values)
                        entry['p50'] = sorted_values[int(len(sorted_values) * 0.50)]
                        entry['p95'] = sorted_values[int(len(sorted_values) * 0.95)]
                        entry['p99'] = sorted_values[int(len(sorted_values) * 0.99)]
                
                # Ajouter des statistiques pour les timers
                if metric.type == MetricType.TIMER and name in self._timers:
                    values = self._timers[name]
                    if values:
                        entry['count'] = len(values)
                        entry['sum'] = sum(values)
                        entry['mean'] = statistics.mean(values)
                        entry['median'] = statistics.median(values)
                        entry['min'] = min(values)
                        entry['max'] = max(values)
                        
                        sorted_values = sorted(values)
                        entry['p50'] = sorted_values[int(len(sorted_values) * 0.50)]
                        entry['p95'] = sorted_values[int(len(sorted_values) * 0.95)]
                        entry['p99'] = sorted_values[int(len(sorted_values) * 0.99)]
                
                snapshot.append(entry)
        
        return snapshot
    
    def get_metrics_by_prefix(self, prefix: str) -> Dict[str, Any]:
        """
        Récupère les métriques par préfixe
        
        Args:
            prefix: Préfixe
            
        Returns:
            Dict[str, Any]: Métriques
        """
        with self._lock:
            return {
                name: metric
                for name, metric in self._metrics.items()
                if name.startswith(prefix)
            }
    
    def get_metrics_by_type(self, metric_type: MetricType) -> Dict[str, Any]:
        """
        Récupère les métriques par type
        
        Args:
            metric_type: Type de métrique
            
        Returns:
            Dict[str, Any]: Métriques
        """
        with self._lock:
            return {
                name: metric
                for name, metric in self._metrics.items()
                if metric.type == metric_type
            }
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        with self._lock:
            return {
                **self.stats,
                'metrics_count': len(self._metrics),
                'history_size': sum(len(h) for h in self._history.values()),
                'counters': dict(self._counters),
                'gauges': dict(self._gauges),
                'histograms': {
                    name: {
                        'size': len(values),
                        'mean': statistics.mean(values) if values else 0,
                        'max': max(values) if values else 0,
                        'min': min(values) if values else 0,
                    }
                    for name, values in self._histograms.items()
                },
                'timers': {
                    name: {
                        'size': len(values),
                        'mean': statistics.mean(values) if values else 0,
                        'max': max(values) if values else 0,
                        'min': min(values) if values else 0,
                    }
                    for name, values in self._timers.items()
                },
            }

# ============================================================
# GLOBAL METRICS INSTANCE
# ============================================================

_metrics: Optional[ArbitrageBotMetrics] = None

def get_metrics(
    enabled: bool = True,
    **kwargs
) -> ArbitrageBotMetrics:
    """
    Récupère le système de métriques global
    
    Args:
        enabled: Activer les métriques
        **kwargs: Arguments supplémentaires
        
    Returns:
        ArbitrageBotMetrics: Système de métriques
    """
    global _metrics
    if _metrics is None:
        _metrics = ArbitrageBotMetrics(enabled=enabled, **kwargs)
    return _metrics

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'MetricType',
    'MetricUnit',
    'Metric',
    'MetricSnapshot',
    'ArbitrageBotMetrics',
    'get_metrics',
]

# ============================================================
# INITIALIZATION
# ============================================================

# Créer l'instance par défaut
metrics = get_metrics()

# Fonctions de commodité pour les métriques
def counter(name: str, value: int = 1, labels: Optional[Dict[str, str]] = None) -> int:
    return metrics.counter(name, value, labels)

def gauge(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> float:
    return metrics.gauge(name, value, labels)

def histogram(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> List[float]:
    return metrics.histogram(name, value, labels)

def timer(name: str, duration: float, labels: Optional[Dict[str, str]] = None) -> float:
    return metrics.timer(name, duration, labels)

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    # Test du système de métriques
    metrics = get_metrics()
    
    # Simuler des métriques
    print("Simulating metrics...")
    
    for i in range(100):
        metrics.counter("test.counter", 1, {"env": "test"})
        metrics.gauge("test.gauge", i * 0.1, {"env": "test"})
        metrics.histogram("test.histogram", np.random.normal(10, 2), {"env": "test"})
        metrics.timer("test.timer", np.random.uniform(0.1, 1.0), {"env": "test"})
        
        if i % 10 == 0:
            print(f"Collected {i+1} samples...")
    
    print("\nMetrics snapshot:")
    snapshot = metrics.get_snapshot()
    print(json.dumps(snapshot[:5], indent=2, default=str))
    
    print("\nMetrics statistics:")
    print(json.dumps(metrics.get_stats(), indent=2, default=str))
    
    metrics._stop()
