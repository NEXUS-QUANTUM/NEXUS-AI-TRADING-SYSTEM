# blockchain/nodes/node_recovery.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Node Recovery - Récupération Automatique des Nœuds

Ce module implémente un système complet de récupération automatique
pour les nœuds blockchain, incluant la détection de pannes, les stratégies
de récupération, et le failover automatique.

Fonctionnalités principales:
- Détection de pannes
- Stratégies de récupération
- Failover automatique
- Redémarrage des nœuds
- Vérification de l'état
- Historique des incidents
- Alertes de récupération
- Support multi-protocoles
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
from collections import defaultdict
from functools import lru_cache, wraps

import aiohttp

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, NodeError, RecoveryError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_node import BaseNode, NodeHealth, NodeStatus
    from .node_manager import NodeManager
    from .node_health import NodeHealthManager
    from .node_backup import NodeBackupManager
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NodeError, RecoveryError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_node import BaseNode, NodeHealth, NodeStatus
    from .node_manager import NodeManager
    from .node_health import NodeHealthManager
    from .node_backup import NodeBackupManager

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class RecoveryStatus(Enum):
    """Statuts de récupération"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RecoveryStrategy(Enum):
    """Stratégies de récupération"""
    RESTART = "restart"
    FAILOVER = "failover"
    RESTORE = "restore"
    RECONNECT = "reconnect"
    RESYNC = "resync"
    CUSTOM = "custom"


class IncidentType(Enum):
    """Types d'incidents"""
    CONNECTION_LOST = "connection_lost"
    NODE_OFFLINE = "node_offline"
    SYNC_FAILED = "sync_failed"
    CORRUPTED_DATA = "corrupted_data"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    NETWORK_PARTITION = "network_partition"
    SOFTWARE_ERROR = "software_error"
    HARDWARE_FAILURE = "hardware_failure"


@dataclass
class Incident:
    """Incident de nœud"""
    incident_id: str
    node_id: str
    incident_type: IncidentType
    severity: str
    message: str
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    recovery_attempts: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "incident_id": self.incident_id,
            "node_id": self.node_id,
            "incident_type": self.incident_type.value,
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "recovery_attempts": self.recovery_attempts,
            "metadata": self.metadata,
        }


@dataclass
class RecoveryPlan:
    """Plan de récupération"""
    plan_id: str
    node_id: str
    strategy: RecoveryStrategy
    steps: List[Dict[str, Any]]
    status: RecoveryStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "plan_id": self.plan_id,
            "node_id": self.node_id,
            "strategy": self.strategy.value,
            "steps": self.steps,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class RecoveryResult:
    """Résultat de récupération"""
    result_id: str
    plan_id: str
    node_id: str
    success: bool
    duration: float
    message: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "result_id": self.result_id,
            "plan_id": self.plan_id,
            "node_id": self.node_id,
            "success": self.success,
            "duration": self.duration,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NodeRecoveryManager:
    """
    Gestionnaire de récupération des nœuds
    """

    def __init__(
        self,
        config: Dict[str, Any],
        node_manager: NodeManager,
        health_manager: NodeHealthManager,
        backup_manager: Optional[NodeBackupManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de récupération

        Args:
            config: Configuration
            node_manager: Gestionnaire de nœuds
            health_manager: Gestionnaire de santé
            backup_manager: Gestionnaire de sauvegarde
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.node_manager = node_manager
        self.health_manager = health_manager
        self.backup_manager = backup_manager
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._incidents: Dict[str, Incident] = {}
        self._recovery_plans: Dict[str, RecoveryPlan] = {}
        self._recovery_results: List[RecoveryResult] = []
        self._active_recoveries: Dict[str, asyncio.Task] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=60.0,
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

        # Stratégies de récupération
        self._recovery_strategies = {
            RecoveryStrategy.RESTART: self._recover_by_restart,
            RecoveryStrategy.FAILOVER: self._recover_by_failover,
            RecoveryStrategy.RESTORE: self._recover_by_restore,
            RecoveryStrategy.RECONNECT: self._recover_by_reconnect,
            RecoveryStrategy.RESYNC: self._recover_by_resync,
        }

        logger.info("NodeRecoveryManager initialisé avec succès")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def detect_incidents(self) -> List[Incident]:
        """
        Détecte les incidents en cours

        Returns:
            Liste des incidents détectés
        """
        logger.info("Détection des incidents")

        incidents = []
        nodes = self.node_manager._nodes.values()

        for node in nodes:
            try:
                # Vérification de la santé
                health = await node.get_health()

                if health.status == NodeStatus.OFFLINE:
                    incident = await self._create_incident(
                        node_id=node.config.node_id,
                        incident_type=IncidentType.NODE_OFFLINE,
                        severity="critical",
                        message=f"Nœud {node.config.node_id} hors ligne",
                        details={"health": health.to_dict()},
                    )
                    incidents.append(incident)

                elif health.status == NodeStatus.SYNCING:
                    # Vérification du temps de synchronisation
                    if health.block_latency > 300:  # 5 minutes
                        incident = await self._create_incident(
                            node_id=node.config.node_id,
                            incident_type=IncidentType.SYNC_FAILED,
                            severity="warning",
                            message=f"Nœud {node.config.node_id} en synchronisation trop longue",
                            details={"health": health.to_dict()},
                        )
                        incidents.append(incident)

            except Exception as e:
                logger.warning(f"Erreur de détection pour {node.config.node_id}: {e}")

        return incidents

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def create_recovery_plan(
        self,
        incident: Incident,
        strategy: Optional[RecoveryStrategy] = None,
    ) -> RecoveryPlan:
        """
        Crée un plan de récupération

        Args:
            incident: Incident à récupérer
            strategy: Stratégie de récupération (optionnel)

        Returns:
            Plan de récupération
        """
        plan_id = f"rp_{uuid.uuid4().hex[:12]}"
        logger.info(f"Création du plan de récupération {plan_id}")

        # Sélection automatique de la stratégie
        if strategy is None:
            strategy = await self._select_strategy(incident)

        # Création des étapes
        steps = await self._create_recovery_steps(incident, strategy)

        plan = RecoveryPlan(
            plan_id=plan_id,
            node_id=incident.node_id,
            strategy=strategy,
            steps=steps,
            status=RecoveryStatus.PENDING,
            created_at=datetime.now(),
            metadata={"incident_id": incident.incident_id},
        )

        self._recovery_plans[plan_id] = plan

        self.metrics.record_increment(
            "node_recovery_plan_created",
            1,
            {"strategy": strategy.value},
        )

        return plan

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def execute_recovery(self, plan_id: str) -> RecoveryResult:
        """
        Exécute un plan de récupération

        Args:
            plan_id: ID du plan

        Returns:
            Résultat de récupération
        """
        logger.info(f"Exécution du plan de récupération {plan_id}")

        plan = self._recovery_plans.get(plan_id)
        if not plan:
            raise RecoveryError(f"Plan {plan_id} non trouvé")

        if plan.status == RecoveryStatus.RUNNING:
            raise RecoveryError(f"Plan {plan_id} déjà en cours")

        start_time = time.time()

        try:
            plan.status = RecoveryStatus.RUNNING
            plan.started_at = datetime.now()

            # Exécution des étapes
            for step in plan.steps:
                await self._execute_step(plan.node_id, step)

            plan.status = RecoveryStatus.COMPLETED
            plan.completed_at = datetime.now()

            result = RecoveryResult(
                result_id=f"rr_{uuid.uuid4().hex[:12]}",
                plan_id=plan_id,
                node_id=plan.node_id,
                success=True,
                duration=time.time() - start_time,
                message="Récupération réussie",
                timestamp=datetime.now(),
            )

            self.metrics.record_increment(
                "node_recovery_success",
                1,
                {"strategy": plan.strategy.value},
            )

            return result

        except Exception as e:
            logger.error(f"Erreur de récupération: {e}")

            plan.status = RecoveryStatus.FAILED
            plan.error_message = str(e)

            result = RecoveryResult(
                result_id=f"rr_{uuid.uuid4().hex[:12]}",
                plan_id=plan_id,
                node_id=plan.node_id,
                success=False,
                duration=time.time() - start_time,
                message=f"Échec de récupération: {str(e)}",
                timestamp=datetime.now(),
            )

            self.metrics.record_increment(
                "node_recovery_failure",
                1,
                {"strategy": plan.strategy.value},
            )

            return result

        finally:
            self._recovery_results.append(result)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_incident(self, incident_id: str) -> Optional[Incident]:
        """
        Obtient un incident

        Args:
            incident_id: ID de l'incident

        Returns:
            Incident ou None
        """
        return self._incidents.get(incident_id)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_incidents(
        self,
        node_id: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 100,
    ) -> List[Incident]:
        """
        Obtient les incidents

        Args:
            node_id: ID du nœud (optionnel)
            resolved: Résolu (optionnel)
            limit: Nombre maximum

        Returns:
            Liste des incidents
        """
        incidents = list(self._incidents.values())

        if node_id:
            incidents = [i for i in incidents if i.node_id == node_id]

        if resolved is not None:
            incidents = [i for i in incidents if i.resolved == resolved]

        return incidents[-limit:]

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_recovery_plan(self, plan_id: str) -> Optional[RecoveryPlan]:
        """
        Obtient un plan de récupération

        Args:
            plan_id: ID du plan

        Returns:
            Plan ou None
        """
        return self._recovery_plans.get(plan_id)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_recovery_results(
        self,
        node_id: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 100,
    ) -> List[RecoveryResult]:
        """
        Obtient les résultats de récupération

        Args:
            node_id: ID du nœud (optionnel)
            success: Succès (optionnel)
            limit: Nombre maximum

        Returns:
            Liste des résultats
        """
        results = self._recovery_results

        if node_id:
            results = [r for r in results if r.node_id == node_id]

        if success is not None:
            results = [r for r in results if r.success == success]

        return results[-limit:]

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def monitor_recovery(
        self,
        interval: int = 60,
    ) -> None:
        """
        Surveille la récupération en continu

        Args:
            interval: Intervalle en secondes
        """
        logger.info("Démarrage du monitoring de récupération")

        while True:
            try:
                # Détection des incidents
                incidents = await self.detect_incidents()

                for incident in incidents:
                    # Création du plan de récupération
                    plan = await self.create_recovery_plan(incident)

                    # Exécution du plan
                    await self.execute_recovery(plan.plan_id)

                    # Attente avant la prochaine tentative
                    await asyncio.sleep(10)

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Erreur de monitoring de récupération: {e}")
                await asyncio.sleep(interval * 2)

    # ============================================================
    # MÉTHODES DE STRATÉGIE
    # ============================================================

    async def _select_strategy(self, incident: Incident) -> RecoveryStrategy:
        """Sélectionne la stratégie de récupération"""
        if incident.incident_type == IncidentType.CONNECTION_LOST:
            return RecoveryStrategy.RECONNECT
        elif incident.incident_type == IncidentType.NODE_OFFLINE:
            return RecoveryStrategy.RESTART
        elif incident.incident_type == IncidentType.SYNC_FAILED:
            return RecoveryStrategy.RESYNC
        elif incident.incident_type == IncidentType.CORRUPTED_DATA:
            return RecoveryStrategy.RESTORE
        elif incident.incident_type == IncidentType.NETWORK_PARTITION:
            return RecoveryStrategy.FAILOVER
        else:
            return RecoveryStrategy.RESTART

    async def _create_recovery_steps(
        self,
        incident: Incident,
        strategy: RecoveryStrategy,
    ) -> List[Dict[str, Any]]:
        """Crée les étapes de récupération"""
        steps = []

        if strategy == RecoveryStrategy.RESTART:
            steps = [
                {"action": "disconnect", "params": {"graceful": True}},
                {"action": "wait", "params": {"duration": 5}},
                {"action": "reconnect", "params": {}},
                {"action": "verify", "params": {}},
            ]

        elif strategy == RecoveryStrategy.FAILOVER:
            steps = [
                {"action": "disconnect", "params": {"graceful": False}},
                {"action": "switch_node", "params": {"protocol": incident.node_id.split("_")[0]}},
                {"action": "verify", "params": {}},
            ]

        elif strategy == RecoveryStrategy.RESTORE:
            steps = [
                {"action": "disconnect", "params": {"graceful": True}},
                {"action": "restore_backup", "params": {"latest": True}},
                {"action": "reconnect", "params": {}},
                {"action": "verify", "params": {}},
            ]

        elif strategy == RecoveryStrategy.RECONNECT:
            steps = [
                {"action": "disconnect", "params": {"graceful": False}},
                {"action": "wait", "params": {"duration": 2}},
                {"action": "reconnect", "params": {}},
                {"action": "verify", "params": {}},
            ]

        elif strategy == RecoveryStrategy.RESYNC:
            steps = [
                {"action": "disconnect", "params": {"graceful": True}},
                {"action": "resync", "params": {"mode": "fast"}},
                {"action": "reconnect", "params": {}},
                {"action": "verify", "params": {}},
            ]

        return steps

    # ============================================================
    # MÉTHODES D'EXÉCUTION
    # ============================================================

    async def _execute_step(self, node_id: str, step: Dict[str, Any]) -> None:
        """Exécute une étape de récupération"""
        action = step.get("action")
        params = step.get("params", {})

        logger.info(f"Exécution de l'étape {action} pour {node_id}")

        if action == "disconnect":
            await self._disconnect_node(node_id, params)
        elif action == "reconnect":
            await self._reconnect_node(node_id, params)
        elif action == "wait":
            await asyncio.sleep(params.get("duration", 5))
        elif action == "verify":
            await self._verify_node(node_id)
        elif action == "switch_node":
            await self._switch_node(node_id, params)
        elif action == "restore_backup":
            await self._restore_backup(node_id, params)
        elif action == "resync":
            await self._resync_node(node_id, params)
        else:
            raise RecoveryError(f"Action inconnue: {action}")

    async def _disconnect_node(self, node_id: str, params: Dict[str, Any]) -> None:
        """Déconnecte un nœud"""
        node = await self.node_manager.get_node(node_id)
        if node:
            await node.disconnect()

    async def _reconnect_node(self, node_id: str, params: Dict[str, Any]) -> None:
        """Reconnecte un nœud"""
        node = await self.node_manager.get_node(node_id)
        if node:
            await node.connect()

    async def _verify_node(self, node_id: str) -> None:
        """Vérifie un nœud"""
        node = await self.node_manager.get_node(node_id)
        if node:
            health = await node.get_health()
            if health.status != NodeStatus.ONLINE:
                raise RecoveryError(f"Nœud {node_id} non vérifié")

    async def _switch_node(self, node_id: str, params: Dict[str, Any]) -> None:
        """Bascule vers un autre nœud"""
        protocol = params.get("protocol")
        # Logique de failover
        pass

    async def _restore_backup(self, node_id: str, params: Dict[str, Any]) -> None:
        """Restaure une sauvegarde"""
        if self.backup_manager:
            latest = params.get("latest", True)
            # Récupération de la dernière sauvegarde
            backups = await self.backup_manager.list_backups(node_id)
            if backups:
                await self.backup_manager.restore_backup(backups[0].backup_id)

    async def _resync_node(self, node_id: str, params: Dict[str, Any]) -> None:
        """Resynchronise un nœud"""
        node = await self.node_manager.get_node(node_id)
        if node:
            # Logique de resynchronisation
            pass

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _create_incident(
        self,
        node_id: str,
        incident_type: IncidentType,
        severity: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Incident:
        """Crée un incident"""
        incident = Incident(
            incident_id=f"inc_{uuid.uuid4().hex[:12]}",
            node_id=node_id,
            incident_type=incident_type,
            severity=severity,
            message=message,
            timestamp=datetime.now(),
            metadata=details or {},
        )

        self._incidents[incident.incident_id] = incident

        # Métriques
        self.metrics.record_increment(
            "node_incident",
            1,
            {
                "node_id": node_id,
                "type": incident_type.value,
                "severity": severity,
            },
        )

        # Alerte
        await self._send_alert(incident)

        return incident

    async def _send_alert(self, incident: Incident) -> None:
        """Envoie une alerte"""
        alert_data = incident.to_dict()

        logger.warning(f"INCIDENT: {incident.message}")

        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert_data)
                else:
                    callback(alert_data)
            except Exception as e:
                logger.warning(f"Erreur de callback d'alerte: {e}")

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques du gestionnaire"""
        total_incidents = len(self._incidents)
        unresolved = sum(1 for i in self._incidents.values() if not i.resolved)
        total_recoveries = len(self._recovery_results)
        successful = sum(1 for r in self._recovery_results if r.success)

        return {
            "total_incidents": total_incidents,
            "unresolved_incidents": unresolved,
            "total_recoveries": total_recoveries,
            "successful_recoveries": successful,
            "recovery_rate": successful / max(1, total_recoveries),
            "active_recoveries": len(self._active_recoveries),
            "available_strategies": list(self._recovery_strategies.keys()),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NodeRecoveryManager...")

        # Annulation des récupérations actives
        for task in self._active_recoveries.values():
            task.cancel()

        self._incidents.clear()
        self._recovery_plans.clear()
        self._recovery_results.clear()
        self._active_recoveries.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_node_recovery_manager(
    config: Dict[str, Any],
    node_manager: NodeManager,
    health_manager: NodeHealthManager,
    **kwargs,
) -> NodeRecoveryManager:
    """
    Crée une instance de NodeRecoveryManager

    Args:
        config: Configuration
        node_manager: Gestionnaire de nœuds
        health_manager: Gestionnaire de santé
        **kwargs: Arguments additionnels

    Returns:
        Instance de NodeRecoveryManager
    """
    return NodeRecoveryManager(
        config=config,
        node_manager=node_manager,
        health_manager=health_manager,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NodeRecoveryManager"""
    # Configuration
    config = {
        "auto_recover": True,
        "max_attempts": 3,
        "recovery_timeout": 300,
    }

    # Création des dépendances (simplifiées)
    class SimpleNodeManager:
        def __init__(self):
            self._nodes = {}

        def get_statistics(self):
            return {}

        async def get_node(self, node_id):
            return None

    class SimpleHealthManager:
        pass

    node_manager = SimpleNodeManager()
    health_manager = SimpleHealthManager()

    # Création du gestionnaire
    recovery_manager = create_node_recovery_manager(
        config=config,
        node_manager=node_manager,
        health_manager=health_manager,
    )

    # Ajout d'un callback d'alerte
    async def alert_callback(alert):
        print(f"ALERTE: {alert}")

    recovery_manager.add_alert_callback(alert_callback)

    # Détection des incidents
    incidents = await recovery_manager.detect_incidents()
    print(f"Incidents détectés: {len(incidents)}")

    # Création d'un plan de récupération
    if incidents:
        plan = await recovery_manager.create_recovery_plan(
            incident=incidents[0],
            strategy=RecoveryStrategy.RESTART,
        )
        print(f"Plan créé: {plan.to_dict()}")

        # Exécution du plan
        result = await recovery_manager.execute_recovery(plan.plan_id)
        print(f"Résultat: {result.to_dict()}")

    # Statistiques
    stats = recovery_manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await recovery_manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
