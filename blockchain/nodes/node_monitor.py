# blockchain/nodes/node_monitor.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Node Monitor - Monitoring Avancé des Nœuds

Ce module implémente un système complet de monitoring pour les nœuds
blockchain, incluant la surveillance en temps réel, les alertes,
les dashboards, et l'analyse des performances.

Fonctionnalités principales:
- Surveillance en temps réel
- Dashboards de monitoring
- Alertes configurables
- Analyse des performances
- Historique des événements
- Rapports automatisés
- Support multi-protocoles
- Intégration avec les outils de monitoring
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

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, NodeError, MonitoringError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_node import BaseNode, NodeHealth, NodeStatus
    from .node_manager import NodeManager
    from .node_health import NodeHealthManager
    from .node_metrics import NodeMetricsCollector
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NodeError, MonitoringError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_node import BaseNode, NodeHealth, NodeStatus
    from .node_manager import NodeManager
    from .node_health import NodeHealthManager
    from .node_metrics import NodeMetricsCollector

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class MonitorStatus(Enum):
    """Statuts de monitoring"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class AlertSeverity(Enum):
    """Sévérité des alertes"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class MonitorEventType(Enum):
    """Types d'événements de monitoring"""
    NODE_CONNECTED = "node_connected"
    NODE_DISCONNECTED = "node_disconnected"
    NODE_SYNCING = "node_syncing"
    NODE_ERROR = "node_error"
    NODE_RECOVERED = "node_recovered"
    BLOCK_PRODUCED = "block_produced"
    TRANSACTION_PENDING = "transaction_pending"
    TRANSACTION_CONFIRMED = "transaction_confirmed"
    PEER_ADDED = "peer_added"
    PEER_REMOVED = "peer_removed"


@dataclass
class MonitorEvent:
    """Événement de monitoring"""
    event_id: str
    event_type: MonitorEventType
    node_id: str
    severity: AlertSeverity
    message: str
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "node_id": self.node_id,
            "severity": self.severity.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "metadata": self.metadata,
        }


@dataclass
class MonitorDashboard:
    """Tableau de bord de monitoring"""
    dashboard_id: str
    node_id: str
    status: MonitorStatus
    uptime: float
    block_height: int
    peer_count: int
    response_time: float
    error_rate: float
    active_connections: int
    pending_transactions: int
    last_event: Optional[MonitorEvent] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "dashboard_id": self.dashboard_id,
            "node_id": self.node_id,
            "status": self.status.value,
            "uptime": self.uptime,
            "block_height": self.block_height,
            "peer_count": self.peer_count,
            "response_time": self.response_time,
            "error_rate": self.error_rate,
            "active_connections": self.active_connections,
            "pending_transactions": self.pending_transactions,
            "last_event": self.last_event.to_dict() if self.last_event else None,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class MonitorReport:
    """Rapport de monitoring"""
    report_id: str
    node_id: str
    period: str
    start_time: datetime
    end_time: datetime
    summary: Dict[str, Any]
    events: List[MonitorEvent]
    metrics: Dict[str, List[Dict[str, Any]]]
    recommendations: List[str]
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "report_id": self.report_id,
            "node_id": self.node_id,
            "period": self.period,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "summary": self.summary,
            "events": [e.to_dict() for e in self.events],
            "metrics": self.metrics,
            "recommendations": self.recommendations,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NodeMonitor:
    """
    Moniteur avancé pour les nœuds blockchain
    """

    def __init__(
        self,
        config: Dict[str, Any],
        node_manager: NodeManager,
        health_manager: NodeHealthManager,
        metrics_collector: NodeMetricsCollector,
        metrics: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le moniteur de nœuds

        Args:
            config: Configuration
            node_manager: Gestionnaire de nœuds
            health_manager: Gestionnaire de santé
            metrics_collector: Collecteur de métriques
            metrics: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.node_manager = node_manager
        self.health_manager = health_manager
        self.metrics_collector = metrics_collector
        self.metrics = metrics or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._dashboards: Dict[str, MonitorDashboard] = {}
        self._events: List[MonitorEvent] = []
        self._reports: Dict[str, MonitorReport] = {}
        self._active_alerts: Dict[str, Dict[str, Any]] = {}
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

        # Monitoring
        self._is_running = False
        self._monitor_tasks: List[asyncio.Task] = []

        logger.info("NodeMonitor initialisé avec succès")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    async def start_monitoring(self) -> None:
        """Démarre le monitoring en arrière-plan"""
        if self._is_running:
            return

        self._is_running = True
        logger.info("Démarrage du monitoring des nœuds")

        # Tâches de monitoring
        self._monitor_tasks.extend([
            asyncio.create_task(self._monitor_nodes()),
            asyncio.create_task(self._monitor_events()),
            asyncio.create_task(self._monitor_alerts()),
            asyncio.create_task(self._monitor_dashboards()),
        ])

    async def stop_monitoring(self) -> None:
        """Arrête le monitoring"""
        self._is_running = False

        for task in self._monitor_tasks:
            task.cancel()

        try:
            await asyncio.gather(*self._monitor_tasks, return_exceptions=True)
        except Exception:
            pass

        self._monitor_tasks.clear()
        logger.info("Monitoring des nœuds arrêté")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_dashboard(self, node_id: str) -> Optional[MonitorDashboard]:
        """
        Obtient le tableau de bord d'un nœud

        Args:
            node_id: ID du nœud

        Returns:
            Tableau de bord ou None
        """
        return self._dashboards.get(node_id)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_events(
        self,
        node_id: Optional[str] = None,
        severity: Optional[AlertSeverity] = None,
        limit: int = 100,
    ) -> List[MonitorEvent]:
        """
        Obtient les événements

        Args:
            node_id: ID du nœud (optionnel)
            severity: Sévérité (optionnel)
            limit: Nombre maximum

        Returns:
            Liste des événements
        """
        events = self._events

        if node_id:
            events = [e for e in events if e.node_id == node_id]

        if severity:
            events = [e for e in events if e.severity == severity]

        return events[-limit:]

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def generate_report(
        self,
        node_id: str,
        period: str = "hour",
    ) -> MonitorReport:
        """
        Génère un rapport de monitoring

        Args:
            node_id: ID du nœud
            period: Période (hour, day, week, month)

        Returns:
            Rapport de monitoring
        """
        report_id = f"mr_{uuid.uuid4().hex[:12]}"
        logger.info(f"Génération du rapport {report_id} pour {node_id}")

        try:
            # Détermination des dates
            end_time = datetime.now()
            if period == "hour":
                start_time = end_time - timedelta(hours=1)
            elif period == "day":
                start_time = end_time - timedelta(days=1)
            elif period == "week":
                start_time = end_time - timedelta(weeks=1)
            elif period == "month":
                start_time = end_time - timedelta(days=30)
            else:
                start_time = end_time - timedelta(hours=1)

            # Récupération des événements
            events = [
                e for e in self._events
                if e.node_id == node_id and start_time <= e.timestamp <= end_time
            ]

            # Récupération des métriques
            metrics = await self.metrics_collector.get_metrics(node_id)

            # Résumé
            summary = {
                "total_events": len(events),
                "errors": len([e for e in events if e.severity == AlertSeverity.CRITICAL]),
                "warnings": len([e for e in events if e.severity == AlertSeverity.WARNING]),
                "uptime": self._calculate_uptime(node_id, start_time, end_time),
                "average_response_time": self._calculate_average_response_time(node_id),
            }

            # Recommandations
            recommendations = await self._generate_recommendations(node_id, events, metrics)

            report = MonitorReport(
                report_id=report_id,
                node_id=node_id,
                period=period,
                start_time=start_time,
                end_time=end_time,
                summary=summary,
                events=events[-100:],
                metrics={m.name: [p.to_dict() for p in m.points[-100:]] for m in metrics},
                recommendations=recommendations,
                created_at=datetime.now(),
            )

            self._reports[report_id] = report

            return report

        except Exception as e:
            logger.error(f"Erreur de génération de rapport: {e}")
            raise MonitoringError(f"Erreur de génération de rapport: {e}")

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def _monitor_nodes(self) -> None:
        """Monitore les nœuds en continu"""
        while self._is_running:
            try:
                for node_id in self.node_manager._nodes.keys():
                    try:
                        # Récupération du nœud
                        node = await self.node_manager.get_node(node_id)
                        if not node:
                            continue

                        # Vérification de la santé
                        health = await node.get_health()

                        # Mise à jour du tableau de bord
                        await self._update_dashboard(node_id, health)

                        # Vérification des alertes
                        await self._check_alerts(node_id, health)

                    except Exception as e:
                        logger.warning(f"Erreur de monitoring de {node_id}: {e}")
                        await self._create_event(
                            node_id=node_id,
                            event_type=MonitorEventType.NODE_ERROR,
                            severity=AlertSeverity.WARNING,
                            message=f"Erreur de monitoring: {str(e)}",
                            details={"error": str(e)},
                        )

                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Erreur de monitoring des nœuds: {e}")
                await asyncio.sleep(30)

    async def _monitor_events(self) -> None:
        """Monitore les événements en continu"""
        while self._is_running:
            try:
                # Vérification des événements récents
                recent_events = self._events[-100:]
                critical_events = [e for e in recent_events if e.severity == AlertSeverity.CRITICAL]

                if critical_events:
                    for event in critical_events:
                        if event.event_id not in self._active_alerts:
                            self._active_alerts[event.event_id] = event.to_dict()
                            await self._send_alert(event)

            except Exception as e:
                logger.error(f"Erreur de monitoring des événements: {e}")

            await asyncio.sleep(5)

    async def _monitor_alerts(self) -> None:
        """Monitore les alertes en continu"""
        while self._is_running:
            try:
                # Vérification des alertes actives
                for alert_id, alert in list(self._active_alerts.items()):
                    # Résolution automatique après 1 heure
                    if (datetime.now() - alert["timestamp"]).seconds > 3600:
                        del self._active_alerts[alert_id]
                        await self._create_event(
                            node_id=alert["node_id"],
                            event_type=MonitorEventType.NODE_RECOVERED,
                            severity=AlertSeverity.INFO,
                            message=f"Alerte {alert_id} résolue automatiquement",
                            details={"alert": alert},
                        )

            except Exception as e:
                logger.error(f"Erreur de monitoring des alertes: {e}")

            await asyncio.sleep(60)

    async def _monitor_dashboards(self) -> None:
        """Monitore les tableaux de bord en continu"""
        while self._is_running:
            try:
                for node_id, dashboard in self._dashboards.items():
                    # Mise à jour des métriques
                    dashboard.timestamp = datetime.now()

                    # Métriques
                    self.metrics.record_gauge(
                        "node_monitor_status",
                        1 if dashboard.status == MonitorStatus.HEALTHY else 0,
                        {"node_id": node_id},
                    )
                    self.metrics.record_gauge(
                        "node_monitor_block_height",
                        dashboard.block_height,
                        {"node_id": node_id},
                    )
                    self.metrics.record_gauge(
                        "node_monitor_response_time",
                        dashboard.response_time,
                        {"node_id": node_id},
                    )

            except Exception as e:
                logger.error(f"Erreur de monitoring des tableaux de bord: {e}")

            await asyncio.sleep(5)

    # ============================================================
    # MÉTHODES DE MISE À JOUR
    # ============================================================

    async def _update_dashboard(self, node_id: str, health: NodeHealth) -> None:
        """Met à jour le tableau de bord"""
        status = self._map_status(health.status)

        if node_id not in self._dashboards:
            self._dashboards[node_id] = MonitorDashboard(
                dashboard_id=f"db_{uuid.uuid4().hex[:12]}",
                node_id=node_id,
                status=status,
                uptime=0,
                block_height=0,
                peer_count=0,
                response_time=0,
                error_rate=0,
                active_connections=0,
                pending_transactions=0,
            )

        dashboard = self._dashboards[node_id]
        dashboard.status = status
        dashboard.uptime = health.uptime
        dashboard.block_height = health.block_height
        dashboard.peer_count = health.peer_count
        dashboard.response_time = health.response_time

        # Calcul du taux d'erreur
        stats = self.node_manager.get_statistics()
        dashboard.error_rate = stats.get("error_rate", 0)

        # Dernier événement
        if self._events:
            dashboard.last_event = self._events[-1]

        dashboard.timestamp = datetime.now()

    # ============================================================
    # MÉTHODES D'ALERTE
    # ============================================================

    async def _check_alerts(self, node_id: str, health: NodeHealth) -> None:
        """Vérifie les conditions d'alerte"""
        # Vérification du statut
        if health.status == NodeStatus.OFFLINE:
            await self._create_event(
                node_id=node_id,
                event_type=MonitorEventType.NODE_DISCONNECTED,
                severity=AlertSeverity.CRITICAL,
                message=f"Nœud {node_id} hors ligne",
                details={"health": health.to_dict()},
            )

        elif health.status == NodeStatus.SYNCING:
            await self._create_event(
                node_id=node_id,
                event_type=MonitorEventType.NODE_SYNCING,
                severity=AlertSeverity.WARNING,
                message=f"Nœud {node_id} en synchronisation",
                details={"health": health.to_dict()},
            )

        # Vérification du temps de réponse
        if health.response_time > 5.0:
            await self._create_event(
                node_id=node_id,
                event_type=MonitorEventType.NODE_ERROR,
                severity=AlertSeverity.WARNING,
                message=f"Temps de réponse élevé: {health.response_time:.2f}s",
                details={"response_time": health.response_time},
            )

        # Vérification du nombre de pairs
        if health.peer_count < 5:
            await self._create_event(
                node_id=node_id,
                event_type=MonitorEventType.PEER_REMOVED,
                severity=AlertSeverity.WARNING,
                message=f"Nombre de pairs faible: {health.peer_count}",
                details={"peer_count": health.peer_count},
            )

    async def _create_event(
        self,
        node_id: str,
        event_type: MonitorEventType,
        severity: AlertSeverity,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Crée un événement"""
        event = MonitorEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            node_id=node_id,
            severity=severity,
            message=message,
            timestamp=datetime.now(),
            details=details or {},
        )

        self._events.append(event)

        # Métriques
        self.metrics.record_increment(
            "node_monitor_event",
            1,
            {
                "node_id": node_id,
                "event_type": event_type.value,
                "severity": severity.value,
            },
        )

        # Alerte si critique
        if severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]:
            await self._send_alert(event)

    async def _send_alert(self, event: MonitorEvent) -> None:
        """Envoie une alerte"""
        alert_data = event.to_dict()

        logger.warning(f"ALERTE MONITORING: {event.message}")

        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert_data)
                else:
                    callback(alert_data)
            except Exception as e:
                logger.warning(f"Erreur de callback d'alerte: {e}")

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    def _map_status(self, status: NodeStatus) -> MonitorStatus:
        """Mappe le statut du nœud"""
        mapping = {
            NodeStatus.ONLINE: MonitorStatus.HEALTHY,
            NodeStatus.SYNCING: MonitorStatus.DEGRADED,
            NodeStatus.OFFLINE: MonitorStatus.OFFLINE,
            NodeStatus.ERROR: MonitorStatus.UNHEALTHY,
            NodeStatus.MAINTENANCE: MonitorStatus.MAINTENANCE,
            NodeStatus.UNKNOWN: MonitorStatus.DEGRADED,
        }
        return mapping.get(status, MonitorStatus.DEGRADED)

    def _calculate_uptime(
        self,
        node_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> float:
        """Calcule l'uptime"""
        events = [
            e for e in self._events
            if e.node_id == node_id and start_time <= e.timestamp <= end_time
        ]

        # Simulé - dans la réalité, on calculerait à partir des événements
        return 99.9

    def _calculate_average_response_time(self, node_id: str) -> float:
        """Calcule le temps de réponse moyen"""
        # Simulé
        return 0.1

    async def _generate_recommendations(
        self,
        node_id: str,
        events: List[MonitorEvent],
        metrics: List[Any],
    ) -> List[str]:
        """Génère des recommandations"""
        recommendations = []

        # Vérification des erreurs
        error_count = len([e for e in events if e.severity == AlertSeverity.CRITICAL])
        if error_count > 5:
            recommendations.append("Nombre élevé d'erreurs. Vérifier les logs du nœud.")

        # Vérification du temps de réponse
        response_time = self._calculate_average_response_time(node_id)
        if response_time > 2.0:
            recommendations.append("Temps de réponse élevé. Considérer l'utilisation d'un nœud plus proche.")

        # Vérification des pairs
        dashboard = self._dashboards.get(node_id)
        if dashboard and dashboard.peer_count < 10:
            recommendations.append("Nombre de pairs faible. Vérifier la configuration réseau.")

        if not recommendations:
            recommendations.append("Aucune recommandation spécifique. Le nœud semble en bonne santé.")

        return recommendations

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques du moniteur"""
        total_dashboards = len(self._dashboards)
        healthy_nodes = sum(
            1 for d in self._dashboards.values()
            if d.status == MonitorStatus.HEALTHY
        )

        return {
            "total_nodes": total_dashboards,
            "healthy_nodes": healthy_nodes,
            "degraded_nodes": total_dashboards - healthy_nodes,
            "total_events": len(self._events),
            "active_alerts": len(self._active_alerts),
            "total_reports": len(self._reports),
            "is_running": self._is_running,
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NodeMonitor...")

        await self.stop_monitoring()

        self._dashboards.clear()
        self._events.clear()
        self._reports.clear()
        self._active_alerts.clear()
        self._alert_callbacks.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_node_monitor(
    config: Dict[str, Any],
    node_manager: NodeManager,
    health_manager: NodeHealthManager,
    metrics_collector: NodeMetricsCollector,
    **kwargs,
) -> NodeMonitor:
    """
    Crée une instance de NodeMonitor

    Args:
        config: Configuration
        node_manager: Gestionnaire de nœuds
        health_manager: Gestionnaire de santé
        metrics_collector: Collecteur de métriques
        **kwargs: Arguments additionnels

    Returns:
        Instance de NodeMonitor
    """
    return NodeMonitor(
        config=config,
        node_manager=node_manager,
        health_manager=health_manager,
        metrics_collector=metrics_collector,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NodeMonitor"""
    # Configuration
    config = {
        "alert_thresholds": {
            "response_time": 5.0,
            "peer_count": 5,
            "error_rate": 0.05,
        },
    }

    # Création des dépendances (simplifiées)
    class SimpleNodeManager:
        def __init__(self):
            self._nodes = {"test_node": None}

        def get_statistics(self):
            return {"error_rate": 0.02}

        async def get_node(self, node_id):
            return None

    class SimpleHealthManager:
        pass

    class SimpleMetricsCollector:
        async def get_metrics(self, node_id):
            return []

    node_manager = SimpleNodeManager()
    health_manager = SimpleHealthManager()
    metrics_collector = SimpleMetricsCollector()

    # Création du moniteur
    monitor = create_node_monitor(
        config=config,
        node_manager=node_manager,
        health_manager=health_manager,
        metrics_collector=metrics_collector,
    )

    # Ajout d'un callback d'alerte
    async def alert_callback(alert):
        print(f"ALERTE: {alert}")

    monitor.add_alert_callback(alert_callback)

    # Démarrage du monitoring
    await monitor.start_monitoring()

    # Attente
    await asyncio.sleep(5)

    # Obtention d'un tableau de bord
    dashboard = await monitor.get_dashboard("test_node")
    print(f"Tableau de bord: {dashboard.to_dict() if dashboard else 'Non trouvé'}")

    # Génération d'un rapport
    report = await monitor.generate_report("test_node", "hour")
    print(f"Rapport: {report.to_dict()}")

    # Statistiques
    stats = monitor.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await monitor.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
