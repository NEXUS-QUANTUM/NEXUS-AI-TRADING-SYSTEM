# trading/bots/hedge_bot/hedge_bot_metrics.py
# Advanced Metrics & Performance Analytics Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Metrics Module - Module avancé de métriques et d'analyse de performance pour le Hedge Bot.
Gère la collecte, l'analyse, la visualisation et le reporting des métriques de performance,
de risque, de trading et de système pour l'ensemble du système de hedging.
"""

import asyncio
import json
import math
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
import pickle
import zlib

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_metrics")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionResult, DecisionType
)
from trading.bots.hedge_bot.hedge_bot_data_execution import (
    Order, ExecutionResult
)


# ============== ENUMS & TYPES ==============

class MetricType(Enum):
    """Types de métriques."""
    PERFORMANCE = "performance"
    RISK = "risk"
    TRADING = "trading"
    SYSTEM = "system"
    BUSINESS = "business"
    QUALITY = "quality"
    OPERATIONAL = "operational"


class MetricCategory(Enum):
    """Catégories de métriques."""
    SHARPE = "sharpe"
    DRAWDOWN = "drawdown"
    VOLATILITY = "volatility"
    PNL = "pnl"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    AVAILABILITY = "availability"


class AggregationMethod(Enum):
    """Méthodes d'agrégation."""
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    STD = "std"
    PERCENTILE = "percentile"
    MEDIAN = "median"


# ============== DATA MODELS ==============

@dataclass
class Metric:
    """Modèle de métrique."""
    metric_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    metric_type: MetricType = MetricType.PERFORMANCE
    category: MetricCategory = MetricCategory.SHARPE
    value: float = 0.0
    unit: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    dimensions: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    aggregation: AggregationMethod = AggregationMethod.AVG


@dataclass
class MetricSeries:
    """Série de métriques."""
    series_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    metric_type: MetricType = MetricType.PERFORMANCE
    values: List[float] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)
    dimensions: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    interval: str = "1m"
    count: int = 0
    min_value: float = 0.0
    max_value: float = 0.0
    avg_value: float = 0.0
    last_value: float = 0.0


@dataclass
class MetricReport:
    """Rapport de métriques."""
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc) - timedelta(days=30))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metrics: List[Metric] = field(default_factory=list)
    series: List[MetricSeries] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    analysis: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricThreshold:
    """Seuil de métrique."""
    threshold_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = ""
    warning_threshold: float = 0.0
    critical_threshold: float = 0.0
    operator: str = "gt"  # gt, lt, eq, ne, gte, lte
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


# ============== INTERFACES ==============

class MetricsEngineInterface(ABC):
    """Interface abstraite pour le moteur de métriques."""
    
    @abstractmethod
    async def record_metric(self, metric: Metric) -> str:
        """Enregistre une métrique."""
        pass
    
    @abstractmethod
    async def get_metrics(self, name: str, limit: int = 100) -> List[Metric]:
        """Récupère les métriques."""
        pass
    
    @abstractmethod
    async def get_series(self, name: str, interval: str = "1m") -> Optional[MetricSeries]:
        """Récupère une série de métriques."""
        pass
    
    @abstractmethod
    async def generate_report(self, period: Tuple[datetime, datetime]) -> MetricReport:
        """Génère un rapport de métriques."""
        pass


# ============== IMPLÉMENTATION ==============

class MetricsEngine(MetricsEngineInterface):
    """
    Moteur de métriques avancé pour le Hedge Bot.
    Gère la collecte, l'analyse et le reporting des métriques.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des métriques
        self._metrics: Dict[str, List[Metric]] = defaultdict(list)
        self._metrics_lock = threading.RLock()
        
        # Gestion des séries
        self._series: Dict[str, MetricSeries] = {}
        self._series_lock = threading.RLock()
        
        # Gestion des seuils
        self._thresholds: Dict[str, MetricThreshold] = {}
        self._thresholds_lock = threading.RLock()
        
        # Gestion des rapports
        self._reports: Dict[str, MetricReport] = {}
        self._reports_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "metrics_recorded": 0,
            "series_created": 0,
            "reports_generated": 0,
            "alerts_triggered": 0,
            "avg_metric_time_ms": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("MetricsEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "metric_history_size": 10000,
            "series_interval": "1m",
            "series_retention": 1000,
            "report_retention": 100,
            "enable_aggregation": True,
            "enable_alerting": True,
            "alert_check_interval": 60,
            "cache_size": 1000,
            "cache_ttl": 3600,
            "enable_caching": True,
            "max_metrics_per_second": 1000
        }
    
    async def start(self) -> None:
        """Démarre le moteur de métriques."""
        logger.info("MetricsEngine starting...")
        self._is_running = True
        
        # Chargement des métriques
        await self._load_metrics()
        
        # Chargement des séries
        await self._load_series()
        
        # Chargement des seuils
        await self._load_thresholds()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._aggregation_loop())
        asyncio.create_task(self._alert_checker())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("MetricsEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de métriques."""
        logger.info("MetricsEngine stopping...")
        self._is_running = False
        
        # Sauvegarde des métriques
        await self._save_metrics()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("MetricsEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def record_metric(self, metric: Metric) -> str:
        """Enregistre une métrique."""
        start_time = time.time()
        self._stats["metrics_recorded"] += 1
        
        with self._metrics_lock:
            self._metrics[metric.name].append(metric)
            
            # Limitation de l'historique
            if len(self._metrics[metric.name]) > self.config["metric_history_size"]:
                self._metrics[metric.name] = self._metrics[metric.name][-self.config["metric_history_size"]:]
        
        # Mise à jour de la série
        await self._update_series(metric)
        
        # Vérification des seuils
        if self.config["enable_alerting"]:
            await self._check_thresholds(metric)
        
        # Métriques de temps
        elapsed = (time.time() - start_time) * 1000
        self._stats["avg_metric_time_ms"] = (
            self._stats["avg_metric_time_ms"] * 0.9 + elapsed * 0.1
        )
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"metrics:{metric.metric_id}",
                metric.to_dict(),
                DataType.METRICS
            )
        
        return metric.metric_id
    
    async def get_metrics(self, name: str, limit: int = 100) -> List[Metric]:
        """Récupère les métriques."""
        with self._metrics_lock:
            metrics = self._metrics.get(name, [])
            return metrics[-limit:]
    
    async def get_series(self, name: str, interval: str = "1m") -> Optional[MetricSeries]:
        """Récupère une série de métriques."""
        with self._series_lock:
            series = self._series.get(name)
            if series:
                return series
        
        # Création de la série si elle n'existe pas
        series = MetricSeries(
            name=name,
            interval=interval,
            dimensions={},
            tags=[]
        )
        
        with self._series_lock:
            self._series[name] = series
        
        return series
    
    async def generate_report(self, period: Tuple[datetime, datetime]) -> MetricReport:
        """Génère un rapport de métriques."""
        self._stats["reports_generated"] += 1
        
        start_time, end_time = period
        
        # Récupération des métriques de la période
        metrics = []
        with self._metrics_lock:
            for metric_list in self._metrics.values():
                for metric in metric_list:
                    if start_time <= metric.timestamp <= end_time:
                        metrics.append(metric)
        
        # Récupération des séries
        series = []
        with self._series_lock:
            series = list(self._series.values())
        
        # Analyse des métriques
        analysis = await self._analyze_metrics(metrics)
        
        # Génération des recommandations
        recommendations = await self._generate_recommendations(analysis)
        
        # Création du rapport
        report = MetricReport(
            name=f"Metrics Report {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}",
            period_start=start_time,
            period_end=end_time,
            metrics=metrics,
            series=series,
            summary={
                "total_metrics": len(metrics),
                "unique_metrics": len(set(m.name for m in metrics)),
                "period_days": (end_time - start_time).days
            },
            analysis=analysis,
            recommendations=recommendations,
            metadata={"generated_by": "metrics_engine"}
        )
        
        with self._reports_lock:
            self._reports[report.report_id] = report
            if len(self._reports) > self.config["report_retention"]:
                oldest = min(self._reports.keys())
                del self._reports[oldest]
        
        logger.info(f"Metrics report generated: {report.name}")
        return report
    
    # ========== MÉTHODES PRIVÉES - SÉRIES ==========
    
    async def _update_series(self, metric: Metric) -> None:
        """Met à jour une série de métriques."""
        with self._series_lock:
            series = self._series.get(metric.name)
            if not series:
                series = MetricSeries(
                    name=metric.name,
                    metric_type=metric.metric_type,
                    dimensions=metric.dimensions,
                    tags=metric.tags,
                    interval=self.config["series_interval"]
                )
                self._series[metric.name] = series
            
            # Ajout de la valeur
            series.values.append(metric.value)
            series.timestamps.append(metric.timestamp)
            series.count += 1
            
            # Mise à jour des statistiques
            series.last_value = metric.value
            if series.count == 1:
                series.min_value = metric.value
                series.max_value = metric.value
                series.avg_value = metric.value
            else:
                series.min_value = min(series.min_value, metric.value)
                series.max_value = max(series.max_value, metric.value)
                series.avg_value = (series.avg_value * (series.count - 1) + metric.value) / series.count
            
            # Limitation de la série
            if len(series.values) > self.config["series_retention"]:
                series.values = series.values[-self.config["series_retention"]:]
                series.timestamps = series.timestamps[-self.config["series_retention"]:]
    
    # ========== MÉTHODES PRIVÉES - SEUILS ==========
    
    async def _check_thresholds(self, metric: Metric) -> None:
        """Vérifie les seuils pour une métrique."""
        with self._thresholds_lock:
            for threshold in self._thresholds.values():
                if threshold.metric_name != metric.name:
                    continue
                
                if not threshold.active:
                    continue
                
                # Vérification du seuil
                triggered = False
                if threshold.operator == "gt" and metric.value > threshold.critical_threshold:
                    triggered = True
                elif threshold.operator == "lt" and metric.value < threshold.critical_threshold:
                    triggered = True
                elif threshold.operator == "gte" and metric.value >= threshold.critical_threshold:
                    triggered = True
                elif threshold.operator == "lte" and metric.value <= threshold.critical_threshold:
                    triggered = True
                elif threshold.operator == "eq" and metric.value == threshold.critical_threshold:
                    triggered = True
                elif threshold.operator == "ne" and metric.value != threshold.critical_threshold:
                    triggered = True
                
                if triggered:
                    self._stats["alerts_triggered"] += 1
                    logger.warning(f"Threshold triggered: {metric.name} = {metric.value} "
                                 f"threshold={threshold.critical_threshold}")
                    
                    # Création d'une alerte
                    if self.data_manager:
                        await self.data_manager.store(
                            f"metrics:alert:{metric.metric_id}",
                            {
                                "metric": metric.to_dict(),
                                "threshold": threshold.to_dict(),
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            },
                            DataType.ALERT
                        )
    
    # ========== MÉTHODES PRIVÉES - ANALYSE ==========
    
    async def _analyze_metrics(self, metrics: List[Metric]) -> Dict[str, Any]:
        """Analyse les métriques."""
        if not metrics:
            return {"status": "no_data"}
        
        analysis = {
            "by_type": defaultdict(int),
            "by_category": defaultdict(int),
            "statistics": {},
            "trends": {},
            "anomalies": []
        }
        
        # Analyse par type
        for metric in metrics:
            analysis["by_type"][metric.metric_type.value] += 1
            analysis["by_category"][metric.category.value] += 1
        
        # Statistiques par métrique
        metric_names = set(m.name for m in metrics)
        for name in metric_names:
            values = [m.value for m in metrics if m.name == name]
            analysis["statistics"][name] = {
                "count": len(values),
                "min": np.min(values),
                "max": np.max(values),
                "mean": np.mean(values),
                "median": np.median(values),
                "std": np.std(values),
                "p95": np.percentile(values, 95),
                "p99": np.percentile(values, 99)
            }
            
            # Détection d'anomalies
            if len(values) > 10:
                mean = np.mean(values)
                std = np.std(values)
                for v in values:
                    if abs(v - mean) > 3 * std:
                        analysis["anomalies"].append({
                            "metric": name,
                            "value": v,
                            "expected": mean,
                            "deviation": abs(v - mean) / std
                        })
        
        return analysis
    
    async def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Génère des recommandations basées sur l'analyse."""
        recommendations = []
        
        if not analysis or analysis.get("status") == "no_data":
            return ["No data available for recommendations"]
        
        # Recommandations basées sur les statistiques
        for name, stats in analysis.get("statistics", {}).items():
            if stats.get("std", 0) > stats.get("mean", 1) * 0.5:
                recommendations.append(f"High variance detected in {name}. Consider stabilization.")
            
            if stats.get("p95", 0) > stats.get("mean", 0) * 1.5:
                recommendations.append(f"High percentiles detected in {name}. Check for outliers.")
        
        # Recommandations basées sur les anomalies
        if analysis.get("anomalies"):
            recommendations.append(f"Anomalies detected in {len(analysis['anomalies'])} metrics. Investigate.")
        
        return recommendations
    
    # ========== MÉTHODES PRIVÉES - AGRÉGATION ==========
    
    async def _aggregation_loop(self) -> None:
        """Boucle d'agrégation des métriques."""
        while self._is_running:
            await asyncio.sleep(self.config["alert_check_interval"])
            
            try:
                if not self.config["enable_aggregation"]:
                    continue
                
                # Agrégation des métriques
                with self._metrics_lock:
                    for name, metrics in self._metrics.items():
                        if len(metrics) < 2:
                            continue
                        
                        # Agrégation par intervalle
                        # Dans un système réel, on agrégerait les métriques
                        pass
                
            except Exception as e:
                logger.error(f"Aggregation loop error: {e}")
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _alert_checker(self) -> None:
        """Vérifie les alertes périodiquement."""
        while self._is_running:
            await asyncio.sleep(self.config["alert_check_interval"])
            
            try:
                # Vérification des métriques récentes
                with self._metrics_lock:
                    for metrics in self._metrics.values():
                        if metrics:
                            await self._check_thresholds(metrics[-1])
                
            except Exception as e:
                logger.error(f"Alert checker error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._metrics_lock:
                    # Nettoyage des métriques anciennes
                    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
                    for name in list(self._metrics.keys()):
                        metrics = self._metrics[name]
                        self._metrics[name] = [m for m in metrics if m.timestamp > cutoff]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques système."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Métriques système
                import psutil
                
                cpu_percent = psutil.cpu_percent()
                memory_percent = psutil.virtual_memory().percent
                disk_percent = psutil.disk_usage('/').percent
                
                # Enregistrement des métriques système
                for name, value in [
                    ("system.cpu.usage", cpu_percent),
                    ("system.memory.usage", memory_percent),
                    ("system.disk.usage", disk_percent)
                ]:
                    metric = Metric(
                        name=name,
                        metric_type=MetricType.SYSTEM,
                        category=MetricCategory.AVAILABILITY,
                        value=value,
                        unit="%",
                        dimensions={"host": socket.gethostname()},
                        source="system"
                    )
                    await self.record_metric(metric)
                
                # Mise à jour des statistiques
                with self._metrics_lock:
                    self._stats["total_metrics"] = sum(len(m) for m in self._metrics.values())
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "metrics:stats",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_metrics(self) -> None:
        """Charge les métriques existantes."""
        try:
            if self.data_manager:
                metrics_data = await self.data_manager.retrieve(
                    "metrics:all",
                    DataType.METRICS
                )
                
                if metrics_data:
                    for m_dict in metrics_data:
                        metric = self._deserialize_metric(m_dict)
                        if metric:
                            with self._metrics_lock:
                                self._metrics[metric.name].append(metric)
            
            logger.info(f"Loaded {self._stats['metrics_recorded']} metrics")
            
        except Exception as e:
            logger.error(f"Load metrics error: {e}")
    
    async def _load_series(self) -> None:
        """Charge les séries existantes."""
        try:
            if self.data_manager:
                series_data = await self.data_manager.retrieve(
                    "metrics:series",
                    DataType.SERIES
                )
                
                if series_data:
                    for s_dict in series_data:
                        series = self._deserialize_series(s_dict)
                        if series:
                            with self._series_lock:
                                self._series[series.name] = series
            
            logger.info(f"Loaded {len(self._series)} series")
            
        except Exception as e:
            logger.error(f"Load series error: {e}")
    
    async def _load_thresholds(self) -> None:
        """Charge les seuils existants."""
        try:
            if self.data_manager:
                thresholds_data = await self.data_manager.retrieve(
                    "metrics:thresholds",
                    DataType.CONFIG
                )
                
                if thresholds_data:
                    for t_dict in thresholds_data:
                        threshold = self._deserialize_threshold(t_dict)
                        if threshold:
                            with self._thresholds_lock:
                                self._thresholds[threshold.threshold_id] = threshold
            
            logger.info(f"Loaded {len(self._thresholds)} thresholds")
            
        except Exception as e:
            logger.error(f"Load thresholds error: {e}")
    
    def _deserialize_metric(self, data: Dict) -> Optional[Metric]:
        """Désérialise une métrique."""
        try:
            return Metric(
                metric_id=data.get("metric_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                metric_type=MetricType(data.get("metric_type", "performance")),
                category=MetricCategory(data.get("category", "sharpe")),
                value=data.get("value", 0.0),
                unit=data.get("unit", ""),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
                dimensions=data.get("dimensions", {}),
                tags=data.get("tags", []),
                metadata=data.get("metadata", {}),
                source=data.get("source", ""),
                aggregation=AggregationMethod(data.get("aggregation", "avg"))
            )
        except Exception as e:
            logger.error(f"Error deserializing metric: {e}")
            return None
    
    def _deserialize_series(self, data: Dict) -> Optional[MetricSeries]:
        """Désérialise une série."""
        try:
            return MetricSeries(
                series_id=data.get("series_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                metric_type=MetricType(data.get("metric_type", "performance")),
                values=data.get("values", []),
                timestamps=[datetime.fromisoformat(ts) for ts in data.get("timestamps", [])],
                dimensions=data.get("dimensions", {}),
                tags=data.get("tags", []),
                metadata=data.get("metadata", {}),
                interval=data.get("interval", "1m"),
                count=data.get("count", 0),
                min_value=data.get("min_value", 0.0),
                max_value=data.get("max_value", 0.0),
                avg_value=data.get("avg_value", 0.0),
                last_value=data.get("last_value", 0.0)
            )
        except Exception as e:
            logger.error(f"Error deserializing series: {e}")
            return None
    
    def _deserialize_threshold(self, data: Dict) -> Optional[MetricThreshold]:
        """Désérialise un seuil."""
        try:
            return MetricThreshold(
                threshold_id=data.get("threshold_id", str(uuid.uuid4())),
                metric_name=data.get("metric_name", ""),
                warning_threshold=data.get("warning_threshold", 0.0),
                critical_threshold=data.get("critical_threshold", 0.0),
                operator=data.get("operator", "gt"),
                active=data.get("active", True),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", [])
            )
        except Exception as e:
            logger.error(f"Error deserializing threshold: {e}")
            return None
    
    async def _save_metrics(self) -> None:
        """Sauvegarde les métriques."""
        try:
            if self.data_manager:
                with self._metrics_lock:
                    for metrics in self._metrics.values():
                        for metric in metrics:
                            await self.data_manager.store(
                                f"metrics:{metric.metric_id}",
                                metric.to_dict(),
                                DataType.METRICS
                            )
            
            logger.info("Metrics saved")
            
        except Exception as e:
            logger.error(f"Save metrics error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_report(self, report_id: str) -> Optional[MetricReport]:
        """Récupère un rapport."""
        with self._reports_lock:
            return self._reports.get(report_id)
    
    async def get_reports(self, limit: int = 10) -> List[MetricReport]:
        """Récupère les rapports."""
        with self._reports_lock:
            reports = list(self._reports.values())
            return sorted(reports, key=lambda r: r.period_end, reverse=True)[:limit]
    
    async def create_threshold(self, threshold: MetricThreshold) -> str:
        """Crée un seuil de métrique."""
        with self._thresholds_lock:
            self._thresholds[threshold.threshold_id] = threshold
        
        if self.data_manager:
            await self.data_manager.store(
                f"metrics:threshold:{threshold.threshold_id}",
                threshold.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Metric threshold created: {threshold.metric_name}")
        return threshold.threshold_id
    
    async def get_threshold(self, threshold_id: str) -> Optional[MetricThreshold]:
        """Récupère un seuil."""
        with self._thresholds_lock:
            return self._thresholds.get(threshold_id)
    
    async def get_thresholds(self) -> List[MetricThreshold]:
        """Récupère les seuils."""
        with self._thresholds_lock:
            return list(self._thresholds.values())
    
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
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._metrics_lock:
            self._stats["total_metrics"] = sum(len(m) for m in self._metrics.values())
        
        return self._stats.copy()


# ============== METRICS VISUALIZER ==============

class MetricsVisualizer:
    """
    Visualiseur de métriques.
    Génère des visualisations pour les métriques.
    """
    
    def __init__(self, engine: MetricsEngine):
        self.engine = engine
    
    async def plot_metric(self, name: str, period: Tuple[datetime, datetime]) -> str:
        """Génère un graphique de métrique."""
        import matplotlib.pyplot as plt
        
        metrics = await self.engine.get_metrics(name)
        filtered = [m for m in metrics if period[0] <= m.timestamp <= period[1]]
        
        if not filtered:
            return ""
        
        values = [m.value for m in filtered]
        timestamps = [m.timestamp for m in filtered]
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(timestamps, values, linewidth=2)
        ax.set_title(f"Metric: {name}")
        ax.set_xlabel("Time")
        ax.set_ylabel("Value")
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        path = f"metric_{name}_{int(time.time())}.png"
        plt.savefig(path, dpi=100)
        plt.close()
        
        return path


# ============== FACTORY ==============

class MetricsFactory:
    """Factory pour créer des composants de métriques."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> MetricsEngine:
        """Crée un moteur de métriques."""
        engine = MetricsEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_visualizer(engine: MetricsEngine) -> MetricsVisualizer:
        """Crée un visualiseur de métriques."""
        return MetricsVisualizer(engine)


# ============== EXPORT ==============

__all__ = [
    "MetricType",
    "MetricCategory",
    "AggregationMethod",
    "Metric",
    "MetricSeries",
    "MetricReport",
    "MetricThreshold",
    "MetricsEngineInterface",
    "MetricsEngine",
    "MetricsVisualizer",
    "MetricsFactory"
]
