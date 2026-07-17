# blockchain/nodes/node_sync.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Node Sync - Gestion de la Synchronisation des Nœuds

Ce module implémente un système complet de synchronisation pour les
nœuds blockchain, supportant la synchronisation initiale, la synchronisation
continue, la gestion des blocs manquants, et l'optimisation des performances.

Fonctionnalités principales:
- Synchronisation initiale
- Synchronisation continue
- Gestion des blocs manquants
- Optimisation des performances
- Monitoring de la synchronisation
- Gestion des erreurs
- Support multi-protocoles
- États de synchronisation
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
        BlockchainError, NodeError, SyncError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_node import BaseNode, NodeHealth, NodeStatus
    from .node_rpc import NodeRPCClient, RPCMethod
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NodeError, SyncError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_node import BaseNode, NodeHealth, NodeStatus
    from .node_rpc import NodeRPCClient, RPCMethod

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class SyncStatus(Enum):
    """Statuts de synchronisation"""
    NOT_STARTED = "not_started"
    SYNCING = "syncing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class SyncMode(Enum):
    """Modes de synchronisation"""
    FAST = "fast"  # Synchronisation rapide (only headers)
    FULL = "full"  # Synchronisation complète
    SNAP = "snap"  # Snap synchronization
    ARCHIVE = "archive"  # Archive sync
    LIGHT = "light"  # Light sync
    WARP = "warp"  # Warp sync


@dataclass
class SyncState:
    """État de synchronisation"""
    node_id: str
    status: SyncStatus
    mode: SyncMode
    current_block: int
    target_block: int
    progress: float
    speed: float  # blocs par seconde
    start_time: datetime
    last_update: datetime
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "mode": self.mode.value,
            "current_block": self.current_block,
            "target_block": self.target_block,
            "progress": self.progress,
            "speed": self.speed,
            "start_time": self.start_time.isoformat(),
            "last_update": self.last_update.isoformat(),
            "estimated_completion": self.estimated_completion.isoformat() if self.estimated_completion else None,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class SyncCheckpoint:
    """Point de contrôle de synchronisation"""
    checkpoint_id: str
    node_id: str
    block_number: int
    block_hash: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "checkpoint_id": self.checkpoint_id,
            "node_id": self.node_id,
            "block_number": self.block_number,
            "block_hash": self.block_hash,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class SyncReport:
    """Rapport de synchronisation"""
    report_id: str
    node_id: str
    sync_state: SyncState
    total_blocks: int
    blocks_synced: int
    average_speed: float
    duration: float
    errors: List[str]
    checkpoints: List[SyncCheckpoint]
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "report_id": self.report_id,
            "node_id": self.node_id,
            "sync_state": self.sync_state.to_dict(),
            "total_blocks": self.total_blocks,
            "blocks_synced": self.blocks_synced,
            "average_speed": self.average_speed,
            "duration": self.duration,
            "errors": self.errors,
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NodeSyncManager:
    """
    Gestionnaire de synchronisation des nœuds
    """

    def __init__(
        self,
        config: Dict[str, Any],
        rpc_client: NodeRPCClient,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de synchronisation

        Args:
            config: Configuration
            rpc_client: Client RPC
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.rpc_client = rpc_client
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._sync_states: Dict[str, SyncState] = {}
        self._checkpoints: Dict[str, List[SyncCheckpoint]] = defaultdict(list)
        self._active_syncs: Dict[str, asyncio.Task] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des retries
        self.retry_config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=30.0,
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

        logger.info("NodeSyncManager initialisé avec succès")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def start_sync(
        self,
        node_id: str,
        endpoint: str,
        mode: SyncMode = SyncMode.FAST,
        target_block: Optional[int] = None,
    ) -> SyncState:
        """
        Démarre la synchronisation d'un nœud

        Args:
            node_id: ID du nœud
            endpoint: Endpoint RPC
            mode: Mode de synchronisation
            target_block: Bloc cible (optionnel)

        Returns:
            État de synchronisation
        """
        logger.info(f"Démarrage de la synchronisation pour {node_id}")

        async with self._locks[node_id]:
            if node_id in self._active_syncs:
                raise SyncError(f"Synchronisation déjà en cours pour {node_id}")

            # Récupération du bloc cible
            if target_block is None:
                target_block = await self._get_latest_block(endpoint)

            # Création de l'état
            state = SyncState(
                node_id=node_id,
                status=SyncStatus.SYNCING,
                mode=mode,
                current_block=0,
                target_block=target_block,
                progress=0.0,
                speed=0.0,
                start_time=datetime.now(),
                last_update=datetime.now(),
            )

            self._sync_states[node_id] = state

            # Démarrage de la tâche de synchronisation
            task = asyncio.create_task(
                self._sync_task(node_id, endpoint, state)
            )
            self._active_syncs[node_id] = task

            self.metrics.record_increment(
                "node_sync_started",
                1,
                {"node_id": node_id, "mode": mode.value},
            )

            return state

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_sync_state(self, node_id: str) -> Optional[SyncState]:
        """
        Obtient l'état de synchronisation

        Args:
            node_id: ID du nœud

        Returns:
            État de synchronisation ou None
        """
        return self._sync_states.get(node_id)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def pause_sync(self, node_id: str) -> bool:
        """
        Met en pause la synchronisation

        Args:
            node_id: ID du nœud

        Returns:
            True si mis en pause
        """
        state = self._sync_states.get(node_id)
        if state and state.status == SyncStatus.SYNCING:
            state.status = SyncStatus.PAUSED
            logger.info(f"Synchronisation de {node_id} mise en pause")
            return True
        return False

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def resume_sync(self, node_id: str) -> bool:
        """
        Reprend la synchronisation

        Args:
            node_id: ID du nœud

        Returns:
            True si repris
        """
        state = self._sync_states.get(node_id)
        if state and state.status == SyncStatus.PAUSED:
            state.status = SyncStatus.SYNCING
            logger.info(f"Synchronisation de {node_id} reprise")
            return True
        return False

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def cancel_sync(self, node_id: str) -> bool:
        """
        Annule la synchronisation

        Args:
            node_id: ID du nœud

        Returns:
            True si annulé
        """
        state = self._sync_states.get(node_id)
        if state and state.status in [SyncStatus.SYNCING, SyncStatus.PAUSED]:
            state.status = SyncStatus.CANCELLED
            logger.info(f"Synchronisation de {node_id} annulée")

            # Annulation de la tâche
            if node_id in self._active_syncs:
                self._active_syncs[node_id].cancel()
                del self._active_syncs[node_id]

            return True
        return False

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def generate_report(self, node_id: str) -> SyncReport:
        """
        Génère un rapport de synchronisation

        Args:
            node_id: ID du nœud

        Returns:
            Rapport de synchronisation
        """
        state = self._sync_states.get(node_id)
        if not state:
            raise SyncError(f"Aucune synchronisation pour {node_id}")

        total_blocks = state.target_block - state.current_block
        duration = (datetime.now() - state.start_time).total_seconds()

        return SyncReport(
            report_id=f"sr_{uuid.uuid4().hex[:12]}",
            node_id=node_id,
            sync_state=state,
            total_blocks=total_blocks,
            blocks_synced=state.current_block,
            average_speed=state.speed,
            duration=duration,
            errors=[],
            checkpoints=self._checkpoints.get(node_id, [])[-10:],
            created_at=datetime.now(),
        )

    # ============================================================
    # MÉTHODES DE SYNCHRONISATION
    # ============================================================

    async def _sync_task(
        self,
        node_id: str,
        endpoint: str,
        state: SyncState,
    ) -> None:
        """Tâche de synchronisation"""
        logger.info(f"Tâche de synchronisation pour {node_id}")

        try:
            # Mode fast: synchronisation des headers uniquement
            if state.mode == SyncMode.FAST:
                await self._sync_fast(node_id, endpoint, state)
            elif state.mode == SyncMode.SNAP:
                await self._sync_snap(node_id, endpoint, state)
            elif state.mode == SyncMode.WARP:
                await self._sync_warp(node_id, endpoint, state)
            else:
                await self._sync_full(node_id, endpoint, state)

            # Vérification
            state.status = SyncStatus.VERIFYING
            await self._verify_sync(node_id, endpoint, state)

            state.status = SyncStatus.COMPLETED

            self.metrics.record_increment(
                "node_sync_completed",
                1,
                {"node_id": node_id, "mode": state.mode.value},
            )

            logger.info(f"Synchronisation de {node_id} terminée")

        except asyncio.CancelledError:
            logger.info(f"Synchronisation de {node_id} annulée")
            state.status = SyncStatus.CANCELLED

        except Exception as e:
            logger.error(f"Erreur de synchronisation pour {node_id}: {e}")
            state.status = SyncStatus.FAILED
            state.error_message = str(e)

            self.metrics.record_increment(
                "node_sync_failed",
                1,
                {"node_id": node_id, "error": type(e).__name__},
            )

            await self._send_alert({
                "type": "sync_failed",
                "node_id": node_id,
                "error": str(e),
            })

        finally:
            if node_id in self._active_syncs:
                del self._active_syncs[node_id]

    async def _sync_fast(
        self,
        node_id: str,
        endpoint: str,
        state: SyncState,
    ) -> None:
        """Synchronisation rapide"""
        batch_size = self.config.get("fast_batch_size", 100)
        checkpoint_interval = self.config.get("checkpoint_interval", 1000)

        while state.status == SyncStatus.SYNCING:
            try:
                # Récupération des blocs en batch
                start_block = state.current_block + 1
                end_block = min(start_block + batch_size - 1, state.target_block)

                if start_block > state.target_block:
                    break

                # Récupération des headers
                blocks = await self._fetch_blocks_batch(
                    endpoint, start_block, end_block
                )

                # Traitement des blocs
                for block in blocks:
                    # Vérification du header
                    if not await self._verify_block_header(block):
                        raise SyncError("Header de bloc invalide")

                    state.current_block = block.get("number", 0)

                    # Mise à jour de la progression
                    state.progress = state.current_block / state.target_block
                    state.last_update = datetime.now()

                    # Point de contrôle
                    if state.current_block % checkpoint_interval == 0:
                        await self._create_checkpoint(node_id, block)

                # Métriques
                self.metrics.record_timing(
                    "node_sync_batch_duration",
                    (datetime.now() - state.last_update).total_seconds(),
                    {"node_id": node_id, "mode": "fast"},
                )

            except Exception as e:
                logger.warning(f"Erreur de batch fast: {e}")
                await asyncio.sleep(5)

    async def _sync_full(
        self,
        node_id: str,
        endpoint: str,
        state: SyncState,
    ) -> None:
        """Synchronisation complète"""
        batch_size = self.config.get("full_batch_size", 50)
        checkpoint_interval = self.config.get("checkpoint_interval", 500)

        while state.status == SyncStatus.SYNCING:
            try:
                start_block = state.current_block + 1
                end_block = min(start_block + batch_size - 1, state.target_block)

                if start_block > state.target_block:
                    break

                # Récupération des blocs complets
                blocks = await self._fetch_blocks_batch(
                    endpoint, start_block, end_block, full=True
                )

                for block in blocks:
                    # Vérification complète
                    if not await self._verify_full_block(block):
                        raise SyncError("Bloc invalide")

                    state.current_block = block.get("number", 0)
                    state.progress = state.current_block / state.target_block
                    state.last_update = datetime.now()

                    if state.current_block % checkpoint_interval == 0:
                        await self._create_checkpoint(node_id, block)

                self.metrics.record_timing(
                    "node_sync_batch_duration",
                    (datetime.now() - state.last_update).total_seconds(),
                    {"node_id": node_id, "mode": "full"},
                )

            except Exception as e:
                logger.warning(f"Erreur de batch full: {e}")
                await asyncio.sleep(5)

    async def _sync_snap(
        self,
        node_id: str,
        endpoint: str,
        state: SyncState,
    ) -> None:
        """Synchronisation snap"""
        # Récupération du snap
        snap_data = await self._fetch_snap(endpoint)

        # Validation du snap
        if not await self._verify_snap(snap_data):
            raise SyncError("Snap invalide")

        # Application du snap
        state.current_block = snap_data.get("block_number", 0)
        state.progress = state.current_block / state.target_block
        state.last_update = datetime.now()

        # Puis synchronisation normale
        await self._sync_fast(node_id, endpoint, state)

    async def _sync_warp(
        self,
        node_id: str,
        endpoint: str,
        state: SyncState,
    ) -> None:
        """Synchronisation warp"""
        # Récupération des points de warp
        warp_data = await self._fetch_warp_data(endpoint)

        # Application des warp points
        for warp_point in warp_data:
            # Vérification du point de warp
            if await self._verify_warp_point(warp_point):
                state.current_block = warp_point.get("block_number", 0)
                state.progress = state.current_block / state.target_block
                state.last_update = datetime.now()

        # Puis synchronisation rapide
        await self._sync_fast(node_id, endpoint, state)

    # ============================================================
    # MÉTHODES DE VÉRIFICATION
    # ============================================================

    async def _verify_sync(
        self,
        node_id: str,
        endpoint: str,
        state: SyncState,
    ) -> bool:
        """Vérifie la synchronisation"""
        latest_block = await self._get_latest_block(endpoint)

        if latest_block == state.target_block:
            logger.info(f"Synchronisation de {node_id} vérifiée")
            return True

        raise SyncError(f"Vérification échouée: {latest_block} != {state.target_block}")

    async def _verify_block_header(self, block: Dict[str, Any]) -> bool:
        """Vérifie un header de bloc"""
        try:
            # Vérification de base
            required_fields = ["number", "hash", "parentHash", "timestamp"]
            for field in required_fields:
                if field not in block:
                    return False

            # Vérification du format
            if not isinstance(block.get("number"), int):
                return False

            return True

        except Exception:
            return False

    async def _verify_full_block(self, block: Dict[str, Any]) -> bool:
        """Vérifie un bloc complet"""
        try:
            # Vérification du header
            if not await self._verify_block_header(block):
                return False

            # Vérification des transactions
            transactions = block.get("transactions", [])
            if not isinstance(transactions, list):
                return False

            # Vérification des logs
            if "logs" in block:
                if not isinstance(block.get("logs"), list):
                    return False

            return True

        except Exception:
            return False

    async def _verify_snap(self, snap_data: Dict[str, Any]) -> bool:
        """Vérifie un snap"""
        required_fields = ["block_number", "block_hash", "state_root"]
        for field in required_fields:
            if field not in snap_data:
                return False
        return True

    async def _verify_warp_point(self, warp_point: Dict[str, Any]) -> bool:
        """Vérifie un point de warp"""
        required_fields = ["block_number", "block_hash", "state_root"]
        for field in required_fields:
            if field not in warp_point:
                return False
        return True

    # ============================================================
    # MÉTHODES DE RÉCUPÉRATION DE DONNÉES
    # ============================================================

    async def _get_latest_block(self, endpoint: str) -> int:
        """Obtient le dernier bloc"""
        response = await self.rpc_client.call(
            method=RPCMethod.ETH_BLOCK_NUMBER,
            params=[],
            endpoint=endpoint,
        )

        if response.is_success():
            return int(response.result, 16)

        raise SyncError("Échec de la récupération du dernier bloc")

    async def _fetch_blocks_batch(
        self,
        endpoint: str,
        start_block: int,
        end_block: int,
        full: bool = False,
    ) -> List[Dict[str, Any]]:
        """Récupère un batch de blocs"""
        blocks = []

        for block_number in range(start_block, end_block + 1):
            hex_block = hex(block_number)
            response = await self.rpc_client.call(
                method=RPCMethod.ETH_GET_BLOCK_BY_NUMBER,
                params=[hex_block, full],
                endpoint=endpoint,
            )

            if response.is_success():
                blocks.append(response.result)

        return blocks

    async def _fetch_snap(self, endpoint: str) -> Dict[str, Any]:
        """Récupère un snap"""
        # Simulé - dans la réalité, on utiliserait une API de snap
        return {
            "block_number": 1000000,
            "block_hash": "0x...",
            "state_root": "0x...",
        }

    async def _fetch_warp_data(self, endpoint: str) -> List[Dict[str, Any]]:
        """Récupère les données warp"""
        # Simulé
        return [
            {"block_number": 100000, "block_hash": "0x...", "state_root": "0x..."},
            {"block_number": 200000, "block_hash": "0x...", "state_root": "0x..."},
        ]

    # ============================================================
    # MÉTHODES DE CHECKPOINT
    # ============================================================

    async def _create_checkpoint(
        self,
        node_id: str,
        block: Dict[str, Any],
    ) -> None:
        """Crée un point de contrôle"""
        checkpoint = SyncCheckpoint(
            checkpoint_id=f"cp_{uuid.uuid4().hex[:12]}",
            node_id=node_id,
            block_number=block.get("number", 0),
            block_hash=block.get("hash", ""),
            timestamp=datetime.now(),
        )

        self._checkpoints[node_id].append(checkpoint)

        # Limitation de l'historique
        if len(self._checkpoints[node_id]) > 100:
            self._checkpoints[node_id] = self._checkpoints[node_id][-100:]

    # ============================================================
    # MÉTHODES D'ALERTE
    # ============================================================

    async def _send_alert(self, alert: Dict[str, Any]) -> None:
        """Envoie une alerte"""
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
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
        """Obtient les statistiques du gestionnaire"""
        total_syncs = len(self._sync_states)
        active_syncs = len(self._active_syncs)
        completed = sum(1 for s in self._sync_states.values() if s.status == SyncStatus.COMPLETED)
        failed = sum(1 for s in self._sync_states.values() if s.status == SyncStatus.FAILED)

        return {
            "total_syncs": total_syncs,
            "active_syncs": active_syncs,
            "completed_syncs": completed,
            "failed_syncs": failed,
            "total_checkpoints": sum(len(c) for c in self._checkpoints.values()),
            "average_speed": self._calculate_average_speed(),
        }

    def _calculate_average_speed(self) -> float:
        """Calcule la vitesse moyenne"""
        speeds = [s.speed for s in self._sync_states.values() if s.speed > 0]
        if speeds:
            return sum(speeds) / len(speeds)
        return 0.0

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NodeSyncManager...")

        # Annulation des synchronisations actives
        for task in self._active_syncs.values():
            task.cancel()

        # Attente de la fin des tâches
        if self._active_syncs:
            await asyncio.gather(*self._active_syncs.values(), return_exceptions=True)

        self._sync_states.clear()
        self._checkpoints.clear()
        self._active_syncs.clear()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_node_sync_manager(
    config: Dict[str, Any],
    rpc_client: NodeRPCClient,
    **kwargs,
) -> NodeSyncManager:
    """
    Crée une instance de NodeSyncManager

    Args:
        config: Configuration
        rpc_client: Client RPC
        **kwargs: Arguments additionnels

    Returns:
        Instance de NodeSyncManager
    """
    return NodeSyncManager(
        config=config,
        rpc_client=rpc_client,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NodeSyncManager"""
    # Configuration
    config = {
        "fast_batch_size": 100,
        "full_batch_size": 50,
        "checkpoint_interval": 1000,
        "sync_timeout": 3600,
    }

    # Client RPC
    rpc_client = NodeRPCClient({})

    # Création du gestionnaire
    sync_manager = create_node_sync_manager(
        config=config,
        rpc_client=rpc_client,
    )

    # Ajout d'un callback d'alerte
    async def alert_callback(alert):
        print(f"ALERTE: {alert}")

    sync_manager.add_alert_callback(alert_callback)

    # Démarrage de la synchronisation
    state = await sync_manager.start_sync(
        node_id="test_node",
        endpoint="https://mainnet.infura.io/v3/YOUR_KEY",
        mode=SyncMode.FAST,
        target_block=10000000,
    )

    print(f"État de synchronisation: {state.to_dict()}")

    # Attente de la synchronisation
    while state.status == SyncStatus.SYNCING:
        await asyncio.sleep(5)
        print(f"Progression: {state.progress:.2%}")

    # Génération d'un rapport
    report = await sync_manager.generate_report("test_node")
    print(f"Rapport: {report.to_dict()}")

    # Statistiques
    stats = sync_manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await sync_manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
