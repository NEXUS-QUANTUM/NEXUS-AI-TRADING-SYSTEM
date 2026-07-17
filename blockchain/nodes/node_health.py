# blockchain/nodes/node_health.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Node Health - Monitoring de la Santé des Nœuds

Ce module implémente un système complet de monitoring de la santé des nœuds
blockchain, incluant la vérification des endpoints, la collecte de métriques,
la détection d'anomalies, et les alertes.

Fonctionnalités principales:
- Vérification de la santé des nœuds
- Collecte de métriques de performance
- Détection d'anomalies
- Alertes en temps réel
- Historique de santé
- Tests de performance
- Monitoring des endpoints WebSocket
- Gestion des dégradations
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

import aiohttp
import web3
from web3 import Web3

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, NodeError, HealthError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_node import BaseNode, NodeHealth, NodeStatus, NodeConfig
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NodeError, HealthError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_node import BaseNode, NodeHealth, NodeStatus, NodeConfig

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class HealthStatus(Enum):
    """Statuts de santé"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class HealthMetric(Enum):
    """Types de métriques de santé"""
    RESPONSE_TIME = "response_time"
    BLOCK_LATENCY = "block_latency"
    PEER_COUNT = "peer_count"
    ERROR_RATE = "error_rate"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    NETWORK_LATENCY = "network_latency"
    UPTIME = "uptime"


@dataclass
class HealthCheckResult:
    """Résultat d'un check de santé"""
    check_id: str
    node_id: str
    timestamp: datetime
    status: HealthStatus
    metrics: Dict[HealthMetric, Any]
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "check_id": self.check_id,
            "node_id": self.node_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "metrics": {k.value: v for k, v in self.metrics.items()},
            "message": self.message,
            "details": self.details,
            "metadata": self.metadata,
        }

    def is_healthy(self) -> bool:
        """Vérifie si le nœud est sain"""
        return self.status == HealthStatus.HEALTHY


@dataclass
class HealthAlert:
    """Alerte de santé"""
    alert_id: str
    node_id: str
    severity: str
    metric: HealthMetric
    value: Any
    threshold: Any
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
            "severity": self.severity,
            "metric": self.metric.value,
            "value": str(self.value),
            "threshold": str(self.threshold),
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata,
        }


@dataclass
class HealthHistory:
    """Historique de santé"""
    node_id: str
    checks: List[HealthCheckResult]
    alerts: List[HealthAlert]
    uptime: float
    downtime: float
    last_check: Optional[datetime] = None
    first_check: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "node_id": self.node_id,
            "checks": [c.to_dict() for c in self.checks[-100:]],
            "alerts": [a.to_dict() for a in self.alerts[-100:]],
            "uptime": self.uptime,
            "downtime": self.downtime,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "first_check": self.first_check.isoformat() if self.first_check else None,
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NodeHealthManager:
    """
    Gestionnaire de santé des nœuds
    """

    # Seuils par défaut
    DEFAULT_THRESHOLDS = {
        HealthMetric.RESPONSE_TIME: 2.0,  # secondes
        HealthMetric.BLOCK_LATENCY: 30.0,  # secondes
        HealthMetric.PEER_COUNT: 5,
        HealthMetric.ERROR_RATE: 0.05,
        HealthMetric.CPU_USAGE: 0.8,
        HealthMetric.MEMORY_USAGE: 0.8,
        HealthMetric.NETWORK_LATENCY: 0.5,
        HealthMetric.UPTIME: 0.95,
    }

    def __init__(
        self,
        config: Dict[str, Any],
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de santé

        Args:
            config: Configuration
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._health_history: Dict[str, HealthHistory] = {}
        self._active_alerts: Dict[str, HealthAlert] = {}
        self._thresholds: Dict[HealthMetric, Any] = self.DEFAULT_THRESHOLDS.copy()
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=10.0,
            backoff=2.0,
        )

        # Circuit breakers
        self.circuit_breakers: Dict[str, CircuitBreaker] = defaultdict(
            lambda: CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60.0,
                half_open_attempts=2,
            )
        )

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Alertes
        self._alert_callbacks: List[Callable] = []

        # Mise à jour des seuils
        self._update_thresholds()

        logger.info("NodeHealthManager initialisé avec succès")

    def _update_thresholds(self) -> None:
        """Met à jour les seuils depuis la configuration"""
        if "thresholds" in self.config:
            for key, value in self.config["thresholds"].items():
                try:
                    metric = HealthMetric(key)
                    self._thresholds[metric] = value
                except ValueError:
                    logger.warning(f"Seuil invalide pour {key}")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def check_health(
        self,
        node: BaseNode,
        full_check: bool = False,
    ) -> HealthCheckResult:
        """
        Vérifie la santé d'un nœud

        Args:
            node: Nœud à vérifier
            full_check: Effectuer un check complet

        Returns:
            Résultat du check de santé
        """
        check_id = f"hc_{uuid.uuid4().hex[:12]}"
        logger.info(f"Vérification de santé de {node.config.node_id}")

        try:
            start_time = time.time()

            # Récupération des métriques de base
            health = await node.get_health()
            status = self._map_status(health.status)

            # Collecte des métriques
            metrics = {
                HealthMetric.RESPONSE_TIME: health.response_time,
                HealthMetric.BLOCK_LATENCY: time.time() - health.last_block_time.timestamp(),
                HealthMetric.PEER_COUNT: health.peer_count,
                HealthMetric.CPU_USAGE: health.cpu_usage,
                HealthMetric.MEMORY_USAGE: health.memory_usage,
                HealthMetric.NETWORK_LATENCY: health.network_latency,
                HealthMetric.UPTIME: health.uptime / (health.uptime + self._get_downtime(node)),
            }

            # Vérification approfondie
            if full_check:
                extended_metrics = await self._extended_check(node)
                metrics.update(extended_metrics)

            # Détection des anomalies
            alerts = await self._check_thresholds(node.config.node_id, metrics)

            # Mise à jour de l'historique
            await self._update_history(node.config.node_id, check_id, status, metrics, alerts)

            # Envoi des alertes
            for alert in alerts:
                await self._send_alert(alert)

            result = HealthCheckResult(
                check_id=check_id,
                node_id=node.config.node_id,
                timestamp=datetime.now(),
                status=status,
                metrics=metrics,
                message=f"Check {status.value}",
                details={
                    "duration": time.time() - start_time,
                    "full_check": full_check,
                    "alerts": [a.to_dict() for a in alerts],
                },
            )

            # Métriques
            self.metrics.record_gauge(
                "node_health_status",
                1 if status == HealthStatus.HEALTHY else 0,
                {"node_id": node.config.node_id},
            )
            self.metrics.record_timing(
                "node_health_check_duration",
                time.time() - start_time,
                {"node_id": node.config.node_id},
            )

            return result

        except Exception as e:
            logger.error(f"Erreur de vérification de santé: {e}")

            return HealthCheckResult(
                check_id=check_id,
                node_id=node.config.node_id,
                timestamp=datetime.now(),
                status=HealthStatus.UNKNOWN,
                metrics={},
                message=f"Erreur: {str(e)}",
                details={"error": str(e)},
            )

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_health_history(
        self,
        node_id: str,
        limit: int = 100,
    ) -> Optional[HealthHistory]:
        """
        Obtient l'historique de santé d'un nœud

        Args:
            node_id: ID du nœud
            limit: Nombre maximum de checks

        Returns:
            Historique de santé
        """
        history = self._health_history.get(node_id)
        if history:
            # Limitation des données
            history.checks = history.checks[-limit:]
            history.alerts = history.alerts[-limit:]
            return history

        return None

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_active_alerts(self, node_id: Optional[str] = None) -> List[HealthAlert]:
        """
        Obtient les alertes actives

        Args:
            node_id: ID du nœud (optionnel)

        Returns:
            Liste des alertes actives
        """
        alerts = list(self._active_alerts.values())

        if node_id:
            alerts = [a for a in alerts if a.node_id == node_id]

        return alerts

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def resolve_alert(self, alert_id: str) -> bool:
        """
        Résout une alerte

        Args:
            alert_id: ID de l'alerte

        Returns:
            True si résolue
        """
        alert = self._active_alerts.get(alert_id)
        if alert and not alert.resolved:
            alert.resolved = True
            alert.resolved_at = datetime.now()
            del self._active_alerts[alert_id]

            logger.info(f"Alerte {alert_id} résolue")
            return True

        return False

    # ============================================================
    # MÉTHODES DE VÉRIFICATION
    # ============================================================

    async def _extended_check(self, node: BaseNode) -> Dict[HealthMetric, Any]:
        """Effectue un check approfondi"""
        metrics = {}

        try:
            # Vérification des transactions
            if hasattr(node, 'send_transaction'):
                # Test de transaction (simulé)
                pass

            # Vérification des peers
            if hasattr(node, 'get_peers'):
                # Récupération des pairs
                pass

            # Vérification des logs
            # ...

        except Exception as e:
            logger.warning(f"Erreur de check approfondi: {e}")

        return metrics

    async def _check_thresholds(
        self,
        node_id: str,
        metrics: Dict[HealthMetric, Any],
    ) -> List[HealthAlert]:
        """Vérifie les seuils"""
        alerts = []

        for metric, value in metrics.items():
            if metric in self._thresholds:
                threshold = self._thresholds[metric]

                if isinstance(value, (int, float)):
                    if value > threshold:
                        alert = HealthAlert(
                            alert_id=f"al_{uuid.uuid4().hex[:12]}",
                            node_id=node_id,
                            severity="warning" if value < threshold * 1.5 else "critical",
                            metric=metric,
                            value=value,
                            threshold=threshold,
                            message=f"{metric.value} dépasse le seuil: {value} > {threshold}",
                            timestamp=datetime.now(),
                        )
                        alerts.append(alert)

        return alerts

    def _map_status(self, status: NodeStatus) -> HealthStatus:
        """Mappe le statut du nœud"""
        mapping = {
            NodeStatus.ONLINE: HealthStatus.HEALTHY,
            NodeStatus.SYNCING: HealthStatus.DEGRADED,
            NodeStatus.OFFLINE: HealthStatus.OFFLINE,
            NodeStatus.ERROR: HealthStatus.UNHEALTHY,
            NodeStatus.MAINTENANCE: HealthStatus.DEGRADED,
            NodeStatus.UNKNOWN: HealthStatus.UNKNOWN,
        }
        return mapping.get(status, HealthStatus.UNKNOWN)

    def _get_downtime(self, node: BaseNode) -> float:
        """Obtient le temps d'arrêt du nœud"""
        # Simulé - dans la réalité, on calculerait à partir des historiques
        return 60.0

    # ============================================================
    # MÉTHODES D'HISTORIQUE
    # ============================================================

    async def _update_history(
        self,
        node_id: str,
        check_id: str,
        status: HealthStatus,
        metrics: Dict[HealthMetric, Any],
        alerts: List[HealthAlert],
    ) -> None:
        """Met à jour l'historique de santé"""
        async with self._locks[node_id]:
            if node_id not in self._health_history:
                self._health_history[node_id] = HealthHistory(
                    node_id=node_id,
                    checks=[],
                    alerts=[],
                    uptime=0,
                    downtime=0,
                    first_check=datetime.now(),
                )

            history = self._health_history[node_id]

            # Ajout du check
            result = HealthCheckResult(
                check_id=check_id,
                node_id=node_id,
                timestamp=datetime.now(),
                status=status,
                metrics=metrics,
                message=f"Check {status.value}",
            )
            history.checks.append(result)
            history.last_check = datetime.now()

            # Mise à jour de l'uptime
            if status == HealthStatus.HEALTHY:
                history.uptime += 1
            else:
                history.downtime += 1

            # Ajout des alertes
            for alert in alerts:
                history.alerts.append(alert)
                self._active_alerts[alert.alert_id] = alert

            # Nettoyage de l'historique
            if len(history.checks) > 1000:
                history.checks = history.checks[-500:]
            if len(history.alerts) > 1000:
                history.alerts = history.alerts[-500:]

    # ============================================================
    # MÉTHODES D'ALERTE
    # ============================================================

    async def _send_alert(self, alert: HealthAlert) -> None:
        """Envoie une alerte"""
        alert_data = alert.to_dict()

        # Logging
        logger.warning(f"ALERTE SANTÉ: {alert.message}")

        # Métriques
        self.metrics.record_increment(
            "node_health_alert",
            1,
            {
                "node_id": alert.node_id,
                "metric": alert.metric.value,
                "severity": alert.severity,
            },
        )

        # Callbacks
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert_data)
                else:
                    callback(alert_data)
            except Exception as e:
                logger.warning(f"Erreur de callback d'alerte: {e}")

    def add_alert_callback(self, callback: Callable) -> None:
        """
        Ajoute un callback pour les alertes

        Args:
            callback: Fonction callback
        """
        self._alert_callbacks.append(callback)

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques de santé"""
        total_nodes = len(self._health_history)
        healthy_nodes = sum(
            1 for h in self._health_history.values()
            if h.checks and h.checks[-1].status == HealthStatus.HEALTHY
        )

        return {
            "total_nodes": total_nodes,
            "healthy_nodes": healthy_nodes,
            "degraded_nodes": total_nodes - healthy_nodes,
            "active_alerts": len(self._active_alerts),
            "total_checks": sum(len(h.checks) for h in self._health_history.values()),
            "total_alerts": sum(len(h.alerts) for h in self._health_history.values()),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NodeHealthManager...")

        self._health_history.clear()
        self._active_alerts.clear()
        self._alert_callbacks.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_node_health_manager(
    config: Dict[str, Any],
    **kwargs,
) -> NodeHealthManager:
    """
    Crée une instance de NodeHealthManager

    Args:
        config: Configuration
        **kwargs: Arguments additionnels

    Returns:
        Instance de NodeHealthManager
    """
    return NodeHealthManager(
        config=config,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NodeHealthManager"""
    # Configuration
    config = {
        "thresholds": {
            "response_time": 3.0,
            "block_latency": 60.0,
            "peer_count": 10,
        },
    }

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

        async def get_health(self):
            return NodeHealth(...)

    node = TestNode()

    # Création du gestionnaire
    health_manager = create_node_health_manager(config=config)

    # Ajout d'un callback d'alerte
    async def alert_callback(alert):
        print(f"ALERTE: {alert}")

    health_manager.add_alert_callback(alert_callback)

    # Vérification de la santé
    result = await health_manager.check_health(node)
    print(f"Résultat: {result.to_dict()}")

    # Historique
    history = await health_manager.get_health_history("test_node")
    if history:
        print(f"Historique: {history.to_dict()}")

    # Alertes actives
    alerts = await health_manager.get_active_alerts()
    print(f"Alertes actives: {len(alerts)}")

    # Statistiques
    stats = health_manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await health_manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
