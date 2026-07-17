# blockchain/nodes/node_metrics.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Node Metrics - Collecte et Analyse des Métriques des Nœuds

Ce module implémente un système complet de collecte, d'analyse et de
visualisation des métriques pour les nœuds blockchain, supportant
la collecte en temps réel, le stockage historique, et les alertes.

Fonctionnalités principales:
- Collecte de métriques en temps réel
- Stockage historique
- Analyse des tendances
- Détection d'anomalies
- Visualisation des métriques
- Alertes basées sur les métriques
- Support multi-protocoles
- Export des métriques
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict, deque
from functools import lru_cache, wraps
import statistics
import math

import aiohttp
import numpy as np
from scipy import stats as scipy_stats

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, NodeError, MetricsError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_node import BaseNode, NodeHealth, NodeStatus
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NodeError, MetricsError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_node import BaseNode, NodeHealth, NodeStatus

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class MetricType(Enum):
    """Types de métriques"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    TIMING = "timing"


class MetricCategory(Enum):
    """Catégories de métriques"""
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    THROUGHPUT = "throughput"
    LATENCY = "latency"
    RESOURCE = "resource"
    NETWORK = "network"
    BLOCKCHAIN = "blockchain"
    CUSTOM = "custom"


@dataclass
class MetricPoint:
    """Point de métrique"""
    timestamp: datetime
    value: Union[int, float, Decimal]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": str(self.value) if isinstance(self.value, Decimal) else self.value,
            "metadata": self.metadata,
        }


@dataclass
class NodeMetric:
    """Métrique de nœud"""
    metric_id: str
    node_id: str
    name: str
    category: MetricCategory
    metric_type: MetricType
    points: List[MetricPoint]
    unit: str = ""
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "metric_id": self.metric_id,
            "node_id": self.node_id,
            "name": self.name,
            "category": self.category.value,
            "metric_type": self.metric_type.value,
            "points": [p.to_dict() for p in self.points],
            "unit": self.unit,
            "description": self.description,
            "metadata": self.metadata,
        }

    def get_current_value(self) -> Optional[Union[int, float, Decimal]]:
        """Obtient la valeur actuelle"""
        if self.points:
            return self.points[-1].value
        return None

    def get_average(self, window: Optional[int] = None) -> Optional[float]:
        """Obtient la moyenne"""
        points = self.points[-window:] if window else self.points
        if not points:
            return None

        values = [float(p.value) for p in points]
        return statistics.mean(values)


@dataclass
class MetricAlert:
    """Alerte de métrique"""
    alert_id: str
    node_id: str
    metric_name: str
    condition: str
    threshold: float
    current_value: float
    severity: str
    message: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "alert_id": self.alert_id,
            "node_id": self.node_id,
            "metric_name": self.metric_name,
            "condition": self.condition,
            "threshold": self.threshold,
            "current_value": self.current_value,
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata,
        }


@dataclass
class MetricTrend:
    """Tendance de métrique"""
    metric_name: str
    node_id: str
    trend_direction: str  # "up", "down", "stable"
    slope: float
    correlation: float
    forecast: float
    confidence: float
    period: int  # secondes
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "metric_name": self.metric_name,
            "node_id": self.node_id,
            "trend_direction": self.trend_direction,
            "slope": self.slope,
            "correlation": self.correlation,
            "forecast": self.forecast,
            "confidence": self.confidence,
            "period": self.period,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NodeMetricsCollector:
    """
    Collecteur de métriques pour les nœuds blockchain
    """

    def __init__(
        self,
        config: Dict[str, Any],
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le collecteur de métriques

        Args:
            config: Configuration
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._metrics: Dict[str, NodeMetric] = {}
        self._alerts: List[MetricAlert] = []
        self._active_alerts: Dict[str, MetricAlert] = {}
        self._trends: Dict[str, MetricTrend] = {}
        self._history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=10.0,
            backoff=2.0,
        )

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Alertes
        self._alert_callbacks: List[Callable] = []

        # Stockage
        self._storage: Optional[Any] = None
        self._init_storage()

        logger.info("NodeMetricsCollector initialisé avec succès")

    def _init_storage(self) -> None:
        """Initialise le stockage des métriques"""
        storage_type = self.config.get("storage_type", "memory")

        if storage_type == "memory":
            self._storage = {}
        elif storage_type == "redis":
            # Implémentation Redis
            pass
        elif storage_type == "influxdb":
            # Implémentation InfluxDB
            pass
        else:
            self._storage = {}

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def collect_metrics(self, node: BaseNode) -> Dict[str, Any]:
        """
        Collecte les métriques d'un nœud

        Args:
            node: Nœud à collecter

        Returns:
            Métriques collectées
        """
        logger.info(f"Collecte des métriques de {node.config.node_id}")

        try:
            # Récupération de la santé
            health = await node.get_health()

            # Métriques de base
            metrics = {
                "block_height": health.block_height,
                "peer_count": health.peer_count,
                "response_time": health.response_time,
                "block_latency": time.time() - health.last_block_time.timestamp(),
                "memory_usage": health.memory_usage,
                "cpu_usage": health.cpu_usage,
                "network_latency": health.network_latency,
                "uptime": health.uptime,
            }

            # Métriques supplémentaires
            stats = node.get_statistics()
            metrics.update({
                "success_rate": stats.get("success_rate", 0),
                "total_requests": stats.get("total_requests", 0),
                "error_rate": stats.get("error_rate", 0),
                "active_requests": stats.get("active_requests", 0),
            })

            # Métriques spécifiques au protocole
            if hasattr(node, 'get_protocol_metrics'):
                protocol_metrics = await node.get_protocol_metrics()
                metrics.update(protocol_metrics)

            # Stockage des métriques
            await self._store_metrics(node.config.node_id, metrics)

            # Vérification des alertes
            await self._check_alert_conditions(node.config.node_id, metrics)

            # Analyse des tendances
            await self._analyze_trends(node.config.node_id, metrics)

            return metrics

        except Exception as e:
            logger.error(f"Erreur de collecte des métriques: {e}")
            raise MetricsError(f"Erreur de collecte des métriques: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_metric(
        self,
        node_id: str,
        metric_name: str,
        window: Optional[int] = None,
    ) -> Optional[NodeMetric]:
        """
        Obtient une métrique

        Args:
            node_id: ID du nœud
            metric_name: Nom de la métrique
            window: Fenêtre de points

        Returns:
            Métrique ou None
        """
        key = f"{node_id}:{metric_name}"
        metric = self._metrics.get(key)

        if metric and window is not None:
            metric.points = metric.points[-window:]

        return metric

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_metrics(
        self,
        node_id: str,
        category: Optional[MetricCategory] = None,
        limit: int = 100,
    ) -> List[NodeMetric]:
        """
        Obtient les métriques d'un nœud

        Args:
            node_id: ID du nœud
            category: Catégorie de métriques
            limit: Nombre maximum

        Returns:
            Liste des métriques
        """
        metrics = [
            m for m in self._metrics.values()
            if m.node_id == node_id
        ]

        if category:
            metrics = [m for m in metrics if m.category == category]

        return metrics[:limit]

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_alerts(
        self,
        node_id: Optional[str] = None,
        severity: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 100,
    ) -> List[MetricAlert]:
        """
        Obtient les alertes

        Args:
            node_id: ID du nœud (optionnel)
            severity: Sévérité (optionnel)
            resolved: Résolu (optionnel)
            limit: Nombre maximum

        Returns:
            Liste des alertes
        """
        alerts = self._alerts

        if node_id:
            alerts = [a for a in alerts if a.node_id == node_id]

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]

        return alerts[-limit:]

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_trends(
        self,
        node_id: Optional[str] = None,
        metric_name: Optional[str] = None,
    ) -> List[MetricTrend]:
        """
        Obtient les tendances

        Args:
            node_id: ID du nœud (optionnel)
            metric_name: Nom de la métrique (optionnel)

        Returns:
            Liste des tendances
        """
        trends = list(self._trends.values())

        if node_id:
            trends = [t for t in trends if t.node_id == node_id]

        if metric_name:
            trends = [t for t in trends if t.metric_name == metric_name]

        return trends

    # ============================================================
    # MÉTHODES DE STOCKAGE
    # ============================================================

    async def _store_metrics(self, node_id: str, metrics: Dict[str, Any]) -> None:
        """Stocke les métriques"""
        timestamp = datetime.now()

        for name, value in metrics.items():
            key = f"{node_id}:{name}"

            async with self._locks[key]:
                # Création ou mise à jour de la métrique
                if key not in self._metrics:
                    self._metrics[key] = NodeMetric(
                        metric_id=f"m_{uuid.uuid4().hex[:12]}",
                        node_id=node_id,
                        name=name,
                        category=self._get_metric_category(name),
                        metric_type=self._get_metric_type(name),
                        points=[],
                    )

                metric = self._metrics[key]
                point = MetricPoint(
                    timestamp=timestamp,
                    value=value,
                )
                metric.points.append(point)

                # Limitation de l'historique
                if len(metric.points) > 1000:
                    metric.points = metric.points[-500:]

                # Stockage externe
                if self._storage is not None:
                    await self._store_external(node_id, name, value, timestamp)

    async def _store_external(
        self,
        node_id: str,
        metric_name: str,
        value: Any,
        timestamp: datetime,
    ) -> None:
        """Stocke les métriques dans un système externe"""
        # Implémentation pour InfluxDB, Redis, etc.
        pass

    # ============================================================
    # MÉTHODES D'ALERTE
    # ============================================================

    async def _check_alert_conditions(
        self,
        node_id: str,
        metrics: Dict[str, Any],
    ) -> None:
        """Vérifie les conditions d'alerte"""
        alert_configs = self.config.get("alerts", {})

        for metric_name, value in metrics.items():
            if metric_name in alert_configs:
                config = alert_configs[metric_name]

                # Vérification des seuils
                if "threshold" in config:
                    threshold = config["threshold"]
                    condition = config.get("condition", "gt")

                    triggered = False
                    if condition == "gt" and value > threshold:
                        triggered = True
                    elif condition == "lt" and value < threshold:
                        triggered = True
                    elif condition == "gte" and value >= threshold:
                        triggered = True
                    elif condition == "lte" and value <= threshold:
                        triggered = True

                    if triggered:
                        alert = MetricAlert(
                            alert_id=f"al_{uuid.uuid4().hex[:12]}",
                            node_id=node_id,
                            metric_name=metric_name,
                            condition=condition,
                            threshold=threshold,
                            current_value=float(value),
                            severity=config.get("severity", "warning"),
                            message=config.get("message", f"{metric_name} dépasse le seuil"),
                            timestamp=datetime.now(),
                        )

                        self._alerts.append(alert)
                        self._active_alerts[alert.alert_id] = alert

                        # Envoi de l'alerte
                        await self._send_alert(alert)

    async def _send_alert(self, alert: MetricAlert) -> None:
        """Envoie une alerte"""
        alert_data = alert.to_dict()

        logger.warning(f"ALERTE MÉTRIQUE: {alert.message}")

        self.metrics.record_increment(
            "node_metric_alert",
            1,
            {
                "node_id": alert.node_id,
                "metric": alert.metric_name,
                "severity": alert.severity,
            },
        )

        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert_data)
                else:
                    callback(alert_data)
            except Exception as e:
                logger.warning(f"Erreur de callback d'alerte: {e}")

    # ============================================================
    # MÉTHODES D'ANALYSE
    # ============================================================

    async def _analyze_trends(self, node_id: str, metrics: Dict[str, Any]) -> None:
        """Analyse les tendances des métriques"""
        for name, value in metrics.items():
            key = f"{node_id}:{name}"

            # Récupération de l'historique
            history = [p.value for p in self._metrics[key].points[-30:]] if key in self._metrics else []

            if len(history) >= 10:
                # Analyse de tendance
                x = list(range(len(history)))
                slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x, [float(v) for v in history])

                # Prédiction
                forecast = slope * (len(history) + 1) + intercept

                self._trends[f"{node_id}:{name}"] = MetricTrend(
                    metric_name=name,
                    node_id=node_id,
                    trend_direction="up" if slope > 0 else "down" if slope < 0 else "stable",
                    slope=slope,
                    correlation=r_value,
                    forecast=forecast,
                    confidence=1 - p_value,
                    period=len(history),
                    timestamp=datetime.now(),
                )

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    def _get_metric_category(self, name: str) -> MetricCategory:
        """Détermine la catégorie d'une métrique"""
        if name in ["block_height", "peer_count"]:
            return MetricCategory.BLOCKCHAIN
        elif name in ["response_time", "block_latency", "network_latency"]:
            return MetricCategory.LATENCY
        elif name in ["cpu_usage", "memory_usage"]:
            return MetricCategory.RESOURCE
        elif name in ["success_rate", "error_rate"]:
            return MetricCategory.PERFORMANCE
        elif name in ["total_requests", "active_requests"]:
            return MetricCategory.THROUGHPUT
        else:
            return MetricCategory.CUSTOM

    def _get_metric_type(self, name: str) -> MetricType:
        """Détermine le type d'une métrique"""
        if name in ["total_requests", "active_requests"]:
            return MetricType.COUNTER
        elif name in ["block_height", "peer_count"]:
            return MetricType.GAUGE
        else:
            return MetricType.GAUGE

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques du collecteur"""
        return {
            "total_metrics": len(self._metrics),
            "total_alerts": len(self._alerts),
            "active_alerts": len(self._active_alerts),
            "total_trends": len(self._trends),
            "storage_type": self.config.get("storage_type", "memory"),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NodeMetricsCollector...")

        self._metrics.clear()
        self._alerts.clear()
        self._active_alerts.clear()
        self._trends.clear()
        self._history.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_node_metrics_collector(
    config: Dict[str, Any],
    **kwargs,
) -> NodeMetricsCollector:
    """
    Crée une instance de NodeMetricsCollector

    Args:
        config: Configuration
        **kwargs: Arguments additionnels

    Returns:
        Instance de NodeMetricsCollector
    """
    return NodeMetricsCollector(
        config=config,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NodeMetricsCollector"""
    # Configuration
    config = {
        "storage_type": "memory",
        "alerts": {
            "response_time": {
                "threshold": 2.0,
                "condition": "gt",
                "severity": "warning",
                "message": "Temps de réponse élevé",
            },
            "error_rate": {
                "threshold": 0.05,
                "condition": "gt",
                "severity": "critical",
                "message": "Taux d'erreur élevé",
            },
        },
    }

    # Création du collecteur
    collector = create_node_metrics_collector(config=config)

    # Création d'un nœud de test
    class TestNode:
        def __init__(self):
            self.config = NodeConfig(
                node_id="test_node",
                protocol=NodeProtocol.ETHEREUM,
                node_type=NodeType.FULL,
                endpoint="https://mainnet.infura.io/v3/YOUR_KEY",
            )

        async def get_health(self):
            return NodeHealth(
                node_id="test_node",
                status=NodeStatus.ONLINE,
                block_height=10000000,
                peer_count=50,
                response_time=0.1,
                last_block_time=datetime.now(),
                uptime=3600.0,
                memory_usage=0.5,
                cpu_usage=0.3,
                network_latency=0.05,
            )

        def get_statistics(self):
            return {
                "total_requests": 1000,
                "success_rate": 0.98,
                "error_rate": 0.02,
                "active_requests": 10,
            }

    node = TestNode()

    # Ajout d'un callback d'alerte
    async def alert_callback(alert):
        print(f"ALERTE: {alert}")

    collector.add_alert_callback(alert_callback)

    # Collecte des métriques
    metrics = await collector.collect_metrics(node)
    print(f"Métriques collectées: {metrics}")

    # Récupération des métriques
    metric = await collector.get_metric("test_node", "response_time")
    if metric:
        print(f"Métrique response_time:")
        print(f"  Actuel: {metric.get_current_value()}")
        print(f"  Moyenne: {metric.get_average(10)}")

    # Récupération des alertes
    alerts = await collector.get_alerts()
    print(f"Alertes: {len(alerts)}")

    # Récupération des tendances
    trends = await collector.get_trends()
    print(f"Tendances: {len(trends)}")

    # Statistiques
    stats = collector.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await collector.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
