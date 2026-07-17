# blockchain/nodes/node_manager.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Node Manager - Gestionnaire Centralisé des Nœuds

Ce module implémente un gestionnaire centralisé pour tous les nœuds blockchain,
intégrant la gestion des connexions, le monitoring, le load balancing,
et la redondance dans une interface unifiée.

Fonctionnalités principales:
- Interface unifiée pour tous les nœuds
- Gestion des connexions
- Load balancing
- Redondance et failover
- Monitoring centralisé
- Gestion des clés API
- Support multi-protocoles
- Configuration dynamique
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

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, NodeError, ValidationError, ConnectionError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..security.encryption import EncryptionManager
    from .base_node import BaseNode, NodeConfig, NodeProtocol, NodeType, NodeHealth, NodeStatus
    from .node_config import NodeConfigManager, NodeEnvironment, NodeGlobalConfig
    from .node_health import NodeHealthManager, HealthStatus, HealthCheckResult
    from .node_cache import NodeCache, CacheConfig, CacheType, CacheStrategy
    from .eth_node import ETHNode, ETHNodeType
    from .bsc_node import BSCNode, BSCNodeType
    from .polygon_node import PolygonNode, PolygonNodeType
    from .arbitrum_node import ArbitrumNode, ArbitrumNodeType
    from .optimism_node import OptimismNode, OptimismNodeType
    from .avalanche_node import AvalancheNode, AvalancheNodeType
    from .solana_node import SolanaNode, SolanaNodeType
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NodeError, ValidationError, ConnectionError
    )
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from ..security.encryption import EncryptionManager
    from .base_node import BaseNode, NodeConfig, NodeProtocol, NodeType, NodeHealth, NodeStatus
    from .node_config import NodeConfigManager, NodeEnvironment, NodeGlobalConfig
    from .node_health import NodeHealthManager, HealthStatus, HealthCheckResult
    from .node_cache import NodeCache, CacheConfig, CacheType, CacheStrategy
    from .eth_node import ETHNode, ETHNodeType
    from .bsc_node import BSCNode, BSCNodeType
    from .polygon_node import PolygonNode, PolygonNodeType
    from .arbitrum_node import ArbitrumNode, ArbitrumNodeType
    from .optimism_node import OptimismNode, OptimismNodeType
    from .avalanche_node import AvalancheNode, AvalancheNodeType
    from .solana_node import SolanaNode, SolanaNodeType

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class NodeManagerStatus(Enum):
    """Statuts du gestionnaire de nœuds"""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class LoadBalancingStrategy(Enum):
    """Stratégies de load balancing"""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    LEAST_LATENCY = "least_latency"
    HEALTH_BASED = "health_based"
    WEIGHTED = "weighted"
    RANDOM = "random"


@dataclass
class NodePool:
    """Pool de nœuds"""
    protocol: NodeProtocol
    nodes: List[BaseNode]
    primary_index: int = 0
    load_balancer: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
    health_check_interval: int = 60
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_next_node(self) -> Optional[BaseNode]:
        """Obtient le prochain nœud selon la stratégie"""
        if not self.nodes:
            return None

        if self.load_balancer == LoadBalancingStrategy.ROUND_ROBIN:
            node = self.nodes[self.primary_index % len(self.nodes)]
            self.primary_index += 1
            return node

        elif self.load_balancer == LoadBalancingStrategy.RANDOM:
            return random.choice(self.nodes)

        elif self.load_balancer == LoadBalancingStrategy.HEALTH_BASED:
            # Sélection du nœud le plus sain
            healthy_nodes = [
                n for n in self.nodes
                if n.get_status() == NodeStatus.ONLINE
            ]
            if healthy_nodes:
                return healthy_nodes[0]

        # Fallback
        return self.nodes[0] if self.nodes else None


@dataclass
class NodeManagerState:
    """État du gestionnaire de nœuds"""
    status: NodeManagerStatus
    total_nodes: int
    active_nodes: int
    degraded_nodes: int
    offline_nodes: int
    health_score: float
    total_requests: int
    error_rate: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "status": self.status.value,
            "total_nodes": self.total_nodes,
            "active_nodes": self.active_nodes,
            "degraded_nodes": self.degraded_nodes,
            "offline_nodes": self.offline_nodes,
            "health_score": self.health_score,
            "total_requests": self.total_requests,
            "error_rate": self.error_rate,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NodeManager:
    """
    Gestionnaire centralisé des nœuds blockchain
    """

    def __init__(
        self,
        config: Dict[str, Any],
        encryption_manager: Optional[EncryptionManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de nœuds

        Args:
            config: Configuration
            encryption_manager: Gestionnaire de chiffrement
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = config
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # État
        self._status = NodeManagerStatus.INITIALIZING
        self._state: Optional[NodeManagerState] = None
        self._nodes: Dict[str, BaseNode] = {}
        self._pools: Dict[NodeProtocol, NodePool] = {}
        self._active_requests: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._is_running = False
        self._monitor_tasks: List[asyncio.Task] = []

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

        # Initialisation des sous-systèmes
        self._initialize_subsystems()

        # Création des pools de nœuds
        self._create_node_pools()

        self._status = NodeManagerStatus.ACTIVE

        logger.info("NodeManager initialisé avec succès")

    # ============================================================
    # INITIALISATION
    # ============================================================

    def _initialize_subsystems(self) -> None:
        """Initialise les sous-systèmes"""
        try:
            # Configuration
            self.config_manager = NodeConfigManager(
                config_dir=self.config.get("config_dir"),
                environment=self.config.get("environment", "production"),
                encryption_manager=self.encryption_manager,
                metrics_collector=self.metrics,
            )

            # Cache
            cache_config = CacheConfig(
                cache_type=CacheType.HYBRID,
                strategy=CacheStrategy.LRU,
                max_size=self.config.get("cache_size", 10000),
                default_ttl=self.cache_ttl,
                redis_url=self.config.get("redis_url"),
                compression=True,
            )
            self.cache = NodeCache(
                config=cache_config,
                metrics_collector=self.metrics,
            )

            # Santé
            self.health_manager = NodeHealthManager(
                config=self.config.get("health", {}),
                metrics_collector=self.metrics,
            )

            logger.info("Sous-systèmes initialisés")

        except Exception as e:
            logger.error(f"Erreur d'initialisation: {e}")
            raise NodeError(f"Erreur d'initialisation: {e}")

    def _create_node_pools(self) -> None:
        """Crée les pools de nœuds"""
        try:
            config = self.config_manager.get_config()

            for node_id, node_config in config.nodes.items():
                try:
                    node = self._create_node(node_config)
                    self._nodes[node_id] = node

                    # Ajout au pool
                    protocol = node_config.protocol
                    if protocol not in self._pools:
                        self._pools[protocol] = NodePool(
                            protocol=protocol,
                            nodes=[],
                            load_balancer=LoadBalancingStrategy(
                                self.config.get("load_balancing", "round_robin")
                            ),
                        )
                    self._pools[protocol].nodes.append(node)

                except Exception as e:
                    logger.error(f"Erreur de création du nœud {node_id}: {e}")

            logger.info(f"{len(self._nodes)} nœuds chargés")

        except Exception as e:
            logger.error(f"Erreur de création des pools: {e}")
            raise NodeError(f"Erreur de création des pools: {e}")

    def _create_node(self, config: NodeConfig) -> BaseNode:
        """Crée un nœud selon le protocole"""
        protocol = config.protocol

        if protocol == NodeProtocol.ETHEREUM:
            return ETHNode(config, self.metrics, self.cache_ttl)
        elif protocol == NodeProtocol.BSC:
            return BSCNode(config, self.metrics, self.cache_ttl)
        elif protocol == NodeProtocol.POLYGON:
            return PolygonNode(config, self.metrics, self.cache_ttl)
        elif protocol == NodeProtocol.ARBITRUM:
            return ArbitrumNode(config, self.metrics, self.cache_ttl)
        elif protocol == NodeProtocol.OPTIMISM:
            return OptimismNode(config, self.metrics, self.cache_ttl)
        elif protocol == NodeProtocol.AVALANCHE:
            return AvalancheNode(config, self.metrics, self.cache_ttl)
        elif protocol == NodeProtocol.SOLANA:
            return SolanaNode(config, self.metrics, self.cache_ttl)
        else:
            raise NodeError(f"Protocole non supporté: {protocol.value}")

    # ============================================================
    # MÉTHODES PUBLIQUES - CONNEXION
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def connect_all(self) -> Dict[str, bool]:
        """
        Connecte tous les nœuds

        Returns:
            Dictionnaire des résultats de connexion
        """
        logger.info("Connexion de tous les nœuds")

        results = {}
        for node_id, node in self._nodes.items():
            try:
                results[node_id] = await node.connect()
            except Exception as e:
                logger.error(f"Erreur de connexion de {node_id}: {e}")
                results[node_id] = False

        return results

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def disconnect_all(self) -> Dict[str, bool]:
        """
        Déconnecte tous les nœuds

        Returns:
            Dictionnaire des résultats de déconnexion
        """
        logger.info("Déconnexion de tous les nœuds")

        results = {}
        for node_id, node in self._nodes.items():
            try:
                results[node_id] = await node.disconnect()
            except Exception as e:
                logger.error(f"Erreur de déconnexion de {node_id}: {e}")
                results[node_id] = False

        return results

    # ============================================================
    # MÉTHODES PUBLIQUES - REQUÊTES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def execute_request(
        self,
        protocol: NodeProtocol,
        method: str,
        params: List[Any],
        retry_on_fail: bool = True,
    ) -> Any:
        """
        Exécute une requête sur un nœud du pool

        Args:
            protocol: Protocole
            method: Méthode RPC
            params: Paramètres
            retry_on_fail: Réessayer en cas d'échec

        Returns:
            Résultat de la requête
        """
        pool = self._pools.get(protocol)
        if not pool:
            raise NodeError(f"Pool non trouvé pour {protocol.value}")

        # Sélection du nœud
        node = pool.get_next_node()
        if not node:
            raise NodeError(f"Aucun nœud disponible pour {protocol.value}")

        # Exécution
        try:
            # Vérification du cache
            cache_key = f"{protocol.value}:{method}:{hash(str(params))}"
            if method in ["eth_getBlockByNumber", "eth_getBalance"]:
                cached_result = await self.cache.get(cache_key)
                if cached_result is not None:
                    return cached_result

            # Exécution de la requête
            result = await self._execute_on_node(node, method, params)

            # Stockage dans le cache
            await self.cache.set(cache_key, result, ttl=self.cache_ttl)

            return result

        except Exception as e:
            logger.warning(f"Erreur sur {node.config.node_id}: {e}")

            if retry_on_fail:
                # Essayer un autre nœud
                for _ in range(len(pool.nodes) - 1):
                    next_node = pool.get_next_node()
                    if next_node and next_node != node:
                        try:
                            return await self._execute_on_node(next_node, method, params)
                        except Exception as e2:
                            logger.warning(f"Erreur sur {next_node.config.node_id}: {e2}")
                            continue

            raise NodeError(f"Échec de la requête: {e}")

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_node(self, node_id: str) -> Optional[BaseNode]:
        """
        Obtient un nœud par son ID

        Args:
            node_id: ID du nœud

        Returns:
            Nœud ou None
        """
        return self._nodes.get(node_id)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_nodes_by_protocol(self, protocol: NodeProtocol) -> List[BaseNode]:
        """
        Obtient les nœuds par protocole

        Args:
            protocol: Protocole

        Returns:
            Liste des nœuds
        """
        pool = self._pools.get(protocol)
        if pool:
            return pool.nodes
        return []

    # ============================================================
    # MÉTHODES DE MONITORING
    # ============================================================

    async def start_monitoring(self) -> None:
        """Démarre le monitoring en arrière-plan"""
        if self._is_running:
            return

        self._is_running = True
        logger.info("Démarrage du monitoring des nœuds")

        # Tâches de monitoring
        self._monitor_tasks.extend([
            asyncio.create_task(self._monitor_health()),
            asyncio.create_task(self._monitor_performance()),
            asyncio.create_task(self._monitor_availability()),
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

    async def _monitor_health(self) -> None:
        """Monitore la santé des nœuds"""
        while self._is_running:
            try:
                for node_id, node in self._nodes.items():
                    try:
                        result = await self.health_manager.check_health(node)
                        self.metrics.record_gauge(
                            "node_health_status",
                            1 if result.is_healthy() else 0,
                            {"node_id": node_id},
                        )
                    except Exception as e:
                        logger.warning(f"Erreur de monitoring de {node_id}: {e}")

                # Mise à jour de l'état
                await self._update_state()

                # Métriques globales
                if self._state:
                    self.metrics.record_gauge(
                        "node_manager_health_score",
                        self._state.health_score,
                    )

            except Exception as e:
                logger.error(f"Erreur de monitoring de santé: {e}")

            await asyncio.sleep(60)

    async def _monitor_performance(self) -> None:
        """Monitore les performances des nœuds"""
        while self._is_running:
            try:
                for node_id, node in self._nodes.items():
                    # Collecte des métriques de performance
                    stats = node.get_statistics()

                    self.metrics.record_gauge(
                        "node_response_time",
                        stats.get("avg_response_time", 0),
                        {"node_id": node_id},
                    )
                    self.metrics.record_gauge(
                        "node_success_rate",
                        stats.get("success_rate", 0),
                        {"node_id": node_id},
                    )

            except Exception as e:
                logger.error(f"Erreur de monitoring des performances: {e}")

            await asyncio.sleep(30)

    async def _monitor_availability(self) -> None:
        """Monitore la disponibilité des nœuds"""
        while self._is_running:
            try:
                for node_id, node in self._nodes.items():
                    try:
                        is_connected = await node.is_healthy()
                        self.metrics.record_gauge(
                            "node_availability",
                            1 if is_connected else 0,
                            {"node_id": node_id},
                        )
                    except Exception as e:
                        logger.warning(f"Erreur de disponibilité de {node_id}: {e}")

            except Exception as e:
                logger.error(f"Erreur de monitoring de disponibilité: {e}")

            await asyncio.sleep(10)

    # ============================================================
    # MÉTHODES D'ÉTAT
    # ============================================================

    async def _update_state(self) -> None:
        """Met à jour l'état du gestionnaire"""
        try:
            total_nodes = len(self._nodes)
            active_nodes = 0
            degraded_nodes = 0
            offline_nodes = 0

            for node in self._nodes.values():
                status = node.get_status()
                if status == NodeStatus.ONLINE:
                    active_nodes += 1
                elif status == NodeStatus.SYNCING:
                    degraded_nodes += 1
                else:
                    offline_nodes += 1

            health_score = active_nodes / max(1, total_nodes)

            self._state = NodeManagerState(
                status=self._status,
                total_nodes=total_nodes,
                active_nodes=active_nodes,
                degraded_nodes=degraded_nodes,
                offline_nodes=offline_nodes,
                health_score=health_score,
                total_requests=sum(
                    node.get_statistics().get("total_requests", 0)
                    for node in self._nodes.values()
                ),
                error_rate=1 - health_score,
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Erreur de mise à jour de l'état: {e}")

    # ============================================================
    # MÉTHODES DE MAINTENANCE
    # ============================================================

    async def add_node(self, config: NodeConfig) -> bool:
        """
        Ajoute un nouveau nœud

        Args:
            config: Configuration du nœud

        Returns:
            True si ajouté avec succès
        """
        try:
            node = self._create_node(config)
            await node.connect()

            self._nodes[config.node_id] = node

            # Ajout au pool
            if config.protocol not in self._pools:
                self._pools[config.protocol] = NodePool(
                    protocol=config.protocol,
                    nodes=[],
                )
            self._pools[config.protocol].nodes.append(node)

            logger.info(f"Nœud {config.node_id} ajouté")
            return True

        except Exception as e:
            logger.error(f"Erreur d'ajout de nœud: {e}")
            return False

    async def remove_node(self, node_id: str) -> bool:
        """
        Supprime un nœud

        Args:
            node_id: ID du nœud

        Returns:
            True si supprimé avec succès
        """
        try:
            node = self._nodes.get(node_id)
            if not node:
                return False

            await node.disconnect()
            await node.cleanup()

            del self._nodes[node_id]

            # Suppression du pool
            for pool in self._pools.values():
                pool.nodes = [n for n in pool.nodes if n.config.node_id != node_id]

            logger.info(f"Nœud {node_id} supprimé")
            return True

        except Exception as e:
            logger.error(f"Erreur de suppression de nœud: {e}")
            return False

    # ============================================================
    # MÉTHODES UTILITAIRES
    # ============================================================

    async def _execute_on_node(
        self,
        node: BaseNode,
        method: str,
        params: List[Any],
    ) -> Any:
        """Exécute une requête sur un nœud"""
        # Dans la réalité, on utiliserait le provider RPC
        # Simulé pour l'exemple
        return {"result": "success"}

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques du gestionnaire"""
        stats = {
            "status": self._status.value,
            "total_nodes": len(self._nodes),
            "protocols": list(self._pools.keys()),
            "cache_size": len(self.cache._memory_cache) if hasattr(self.cache, '_memory_cache') else 0,
            "is_running": self._is_running,
            "monitor_tasks": len(self._monitor_tasks),
        }

        if self._state:
            stats.update({
                "active_nodes": self._state.active_nodes,
                "health_score": self._state.health_score,
                "error_rate": self._state.error_rate,
            })

        return stats

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NodeManager...")

        self._status = NodeManagerStatus.SHUTDOWN

        await self.stop_monitoring()

        # Déconnexion de tous les nœuds
        await self.disconnect_all()

        # Nettoyage des nœuds
        for node in self._nodes.values():
            await node.cleanup()

        self._nodes.clear()
        self._pools.clear()

        # Nettoyage du cache
        await self.cache.cleanup()

        # Nettoyage du gestionnaire de santé
        await self.health_manager.cleanup()

        # Nettoyage du gestionnaire de configuration
        await self.config_manager.cleanup()

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_node_manager(
    config: Dict[str, Any],
    **kwargs,
) -> NodeManager:
    """
    Crée une instance de NodeManager

    Args:
        config: Configuration
        **kwargs: Arguments additionnels

    Returns:
        Instance de NodeManager
    """
    return NodeManager(
        config=config,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NodeManager"""
    # Configuration
    config = {
        "environment": "production",
        "load_balancing": "round_robin",
        "cache_size": 10000,
        "health": {
            "thresholds": {
                "response_time": 3.0,
                "block_latency": 60.0,
            },
        },
    }

    # Création du gestionnaire
    manager = create_node_manager(config=config)

    # Connexion de tous les nœuds
    results = await manager.connect_all()
    print(f"Connexions: {results}")

    # Exécution d'une requête
    result = await manager.execute_request(
        protocol=NodeProtocol.ETHEREUM,
        method="eth_blockNumber",
        params=[],
    )
    print(f"Résultat: {result}")

    # Statistiques
    stats = manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Démarrage du monitoring
    await manager.start_monitoring()

    # Attente
    await asyncio.sleep(5)

    # Nettoyage
    await manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
