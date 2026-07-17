# blockchain/nodes/node_peers.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Node Peers - Gestion des Pairs des Nœuds

Ce module implémente un système complet de gestion des pairs pour les
nœuds blockchain, incluant la découverte, la connexion, le monitoring,
et l'optimisation des connexions entre pairs.

Fonctionnalités principales:
- Découverte de pairs
- Connexion aux pairs
- Monitoring des pairs
- Gestion des connexions
- Optimisation des pairs
- Filtrage des pairs
- Statistiques des pairs
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
import web3
from web3 import Web3

# Import des modules internes
try:
    from ..core.exceptions import (
        BlockchainError, NodeError, PeerError
    )
    from ..core.logging import get_logger
    from ..core.retry import async_retry, RetryConfig
    from ..core.circuit_breaker import CircuitBreaker
    from ..core.metrics import MetricsCollector
    from .base_node import BaseNode, NodeHealth, NodeStatus
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import (
        BlockchainError, NodeError, PeerError
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

class PeerStatus(Enum):
    """Statuts des pairs"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    FAILED = "failed"
    BANNED = "banned"
    UNKNOWN = "unknown"


class PeerScore(Enum):
    """Scores des pairs"""
    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    BAD = "bad"


@dataclass
class Peer:
    """Pair réseau"""
    peer_id: str
    address: str
    port: int
    protocol: str
    status: PeerStatus
    score: PeerScore
    latency: float
    last_seen: datetime
    first_seen: datetime
    connected_since: Optional[datetime] = None
    message_count: int = 0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "peer_id": self.peer_id,
            "address": self.address,
            "port": self.port,
            "protocol": self.protocol,
            "status": self.status.value,
            "score": self.score.value,
            "latency": self.latency,
            "last_seen": self.last_seen.isoformat(),
            "first_seen": self.first_seen.isoformat(),
            "connected_since": self.connected_since.isoformat() if self.connected_since else None,
            "message_count": self.message_count,
            "error_count": self.error_count,
            "metadata": self.metadata,
        }


@dataclass
class PeerStats:
    """Statistiques des pairs"""
    total_peers: int
    connected_peers: int
    connecting_peers: int
    failed_peers: int
    banned_peers: int
    average_latency: float
    best_peer: Optional[Peer] = None
    worst_peer: Optional[Peer] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "total_peers": self.total_peers,
            "connected_peers": self.connected_peers,
            "connecting_peers": self.connecting_peers,
            "failed_peers": self.failed_peers,
            "banned_peers": self.banned_peers,
            "average_latency": self.average_latency,
            "best_peer": self.best_peer.to_dict() if self.best_peer else None,
            "worst_peer": self.worst_peer.to_dict() if self.worst_peer else None,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class PeerDiscovery:
    """Découverte de pairs"""
    discovery_id: str
    node_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    found_peers: List[Peer] = field(default_factory=list)
    total_found: int = 0
    successful_connections: int = 0
    failed_connections: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "discovery_id": self.discovery_id,
            "node_id": self.node_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "found_peers": [p.to_dict() for p in self.found_peers],
            "total_found": self.total_found,
            "successful_connections": self.successful_connections,
            "failed_connections": self.failed_connections,
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NodePeerManager:
    """
    Gestionnaire de pairs pour les nœuds blockchain
    """

    # Configuration par défaut
    DEFAULT_CONFIG = {
        "max_peers": 50,
        "min_peers": 10,
        "connect_timeout": 10,
        "ping_interval": 30,
        "ban_threshold": 5,
        "score_threshold": 0.5,
    }

    def __init__(
        self,
        config: Dict[str, Any],
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de pairs

        Args:
            config: Configuration
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config = self.DEFAULT_CONFIG.copy()
        self.config.update(config)
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # États internes
        self._peers: Dict[str, Peer] = {}
        self._banned_peers: Set[str] = set()
        self._discoveries: List[PeerDiscovery] = []
        self._active_discoveries: Dict[str, PeerDiscovery] = {}
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
                failure_threshold=5,
                recovery_timeout=60.0,
                half_open_attempts=3,
            )
        )

        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=10)

        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None
        self._init_session()

        logger.info("NodePeerManager initialisé avec succès")

    def _init_session(self) -> None:
        """Initialise la session HTTP"""
        if not self._session:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    "User-Agent": "NEXUS-AI-TRADING/1.0",
                    "Accept": "application/json",
                },
            )

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def discover_peers(self, node: BaseNode) -> PeerDiscovery:
        """
        Découvre de nouveaux pairs

        Args:
            node: Nœud pour la découverte

        Returns:
            Résultat de la découverte
        """
        discovery_id = f"disc_{uuid.uuid4().hex[:12]}"
        logger.info(f"Découverte de pairs {discovery_id} pour {node.config.node_id}")

        discovery = PeerDiscovery(
            discovery_id=discovery_id,
            node_id=node.config.node_id,
            started_at=datetime.now(),
        )

        self._active_discoveries[discovery_id] = discovery

        try:
            # Récupération des pairs via le protocole
            if hasattr(node, 'get_peers'):
                peers_data = await node.get_peers()
                for peer_data in peers_data:
                    peer = await self._create_peer(node.config.node_id, peer_data)
                    if peer:
                        discovery.found_peers.append(peer)
                        await self.add_peer(peer)

            discovery.total_found = len(discovery.found_peers)

            # Tentative de connexion
            for peer in discovery.found_peers[:10]:
                try:
                    if await self._connect_peer(node, peer):
                        discovery.successful_connections += 1
                    else:
                        discovery.failed_connections += 1
                except Exception as e:
                    logger.warning(f"Erreur de connexion à {peer.address}: {e}")
                    discovery.failed_connections += 1

            discovery.completed_at = datetime.now()

            self._discoveries.append(discovery)
            del self._active_discoveries[discovery_id]

            self.metrics.record_gauge(
                "node_peers_discovered",
                discovery.total_found,
                {"node_id": node.config.node_id},
            )

            logger.info(f"Découverte {discovery_id} terminée: {discovery.total_found} pairs trouvés")
            return discovery

        except Exception as e:
            logger.error(f"Erreur de découverte: {e}")
            discovery.completed_at = datetime.now()
            self._discoveries.append(discovery)
            del self._active_discoveries[discovery_id]
            raise PeerError(f"Erreur de découverte: {e}")

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def add_peer(self, peer: Peer) -> bool:
        """
        Ajoute un pair

        Args:
            peer: Pair à ajouter

        Returns:
            True si ajouté avec succès
        """
        async with self._locks[peer.peer_id]:
            # Vérification du ban
            if peer.peer_id in self._banned_peers:
                logger.warning(f"Pair {peer.peer_id} banni")
                return False

            # Limite de pairs
            if len(self._peers) >= self.config["max_peers"]:
                # Remplacer le pire pair
                worst_peer = await self._get_worst_peer()
                if worst_peer and worst_peer.score.value < peer.score.value:
                    del self._peers[worst_peer.peer_id]
                else:
                    return False

            self._peers[peer.peer_id] = peer

            self.metrics.record_increment(
                "node_peer_added",
                1,
                {"protocol": peer.protocol},
            )

            return True

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def remove_peer(self, peer_id: str) -> bool:
        """
        Supprime un pair

        Args:
            peer_id: ID du pair

        Returns:
            True si supprimé avec succès
        """
        if peer_id in self._peers:
            del self._peers[peer_id]

            self.metrics.record_increment(
                "node_peer_removed",
                1,
                {},
            )

            return True

        return False

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def ban_peer(self, peer_id: str, reason: str = "") -> bool:
        """
        Bannit un pair

        Args:
            peer_id: ID du pair
            reason: Raison du ban

        Returns:
            True si banni avec succès
        """
        self._banned_peers.add(peer_id)

        if peer_id in self._peers:
            self._peers[peer_id].status = PeerStatus.BANNED

        logger.info(f"Pair {peer_id} banni: {reason}")

        self.metrics.record_increment(
            "node_peer_banned",
            1,
            {},
        )

        return True

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_peer(self, peer_id: str) -> Optional[Peer]:
        """
        Obtient un pair

        Args:
            peer_id: ID du pair

        Returns:
            Pair ou None
        """
        return self._peers.get(peer_id)

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_peers(
        self,
        status: Optional[PeerStatus] = None,
        score: Optional[PeerScore] = None,
    ) -> List[Peer]:
        """
        Obtient les pairs filtrés

        Args:
            status: Statut (optionnel)
            score: Score (optionnel)

        Returns:
            Liste des pairs
        """
        peers = list(self._peers.values())

        if status:
            peers = [p for p in peers if p.status == status]

        if score:
            peers = [p for p in peers if p.score == score]

        return peers

    @async_retry(max_attempts=3, initial_delay=0.5)
    async def get_stats(self) -> PeerStats:
        """
        Obtient les statistiques des pairs

        Returns:
            Statistiques des pairs
        """
        total_peers = len(self._peers)
        connected_peers = sum(1 for p in self._peers.values() if p.status == PeerStatus.CONNECTED)
        connecting_peers = sum(1 for p in self._peers.values() if p.status == PeerStatus.CONNECTING)
        failed_peers = sum(1 for p in self._peers.values() if p.status == PeerStatus.FAILED)
        banned_peers = len(self._banned_peers)

        # Latence moyenne
        latencies = [p.latency for p in self._peers.values() if p.latency > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        # Meilleur et pire pair
        best_peer = None
        worst_peer = None

        if self._peers:
            best_peer = min(self._peers.values(), key=lambda p: p.latency if p.latency > 0 else float('inf'))
            worst_peer = max(self._peers.values(), key=lambda p: p.latency if p.latency > 0 else 0)

        return PeerStats(
            total_peers=total_peers,
            connected_peers=connected_peers,
            connecting_peers=connecting_peers,
            failed_peers=failed_peers,
            banned_peers=banned_peers,
            average_latency=avg_latency,
            best_peer=best_peer,
            worst_peer=worst_peer,
        )

    # ============================================================
    # MÉTHODES DE MAINTENANCE
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def maintain_connections(self, node: BaseNode) -> None:
        """
        Maintient les connexions optimales

        Args:
            node: Nœud à maintenir
        """
        logger.info(f"Maintenance des connexions pour {node.config.node_id}")

        try:
            # Récupération des statistiques
            stats = await self.get_stats()

            # Vérification du nombre de connexions
            if stats.connected_peers < self.config["min_peers"]:
                # Découverte de nouveaux pairs
                await self.discover_peers(node)

            # Nettoyage des pairs inactifs
            await self._cleanup_inactive_peers()

            # Mise à jour des scores
            await self._update_peer_scores()

            # Gestion des bans
            await self._manage_bans()

        except Exception as e:
            logger.error(f"Erreur de maintenance: {e}")

    # ============================================================
    # MÉTHODES DE COMMUNICATION
    # ============================================================

    @async_retry(max_attempts=3, initial_delay=1.0)
    async def ping_peer(self, peer: Peer) -> float:
        """
        Ping un pair

        Args:
            peer: Pair à pinger

        Returns:
            Latence en secondes
        """
        try:
            start_time = time.time()

            # Simulation de ping
            await asyncio.sleep(0.1)

            latency = time.time() - start_time

            # Mise à jour de la latence
            peer.latency = latency
            peer.last_seen = datetime.now()

            self.metrics.record_timing(
                "node_peer_ping",
                latency,
                {"peer_id": peer.peer_id[:8]},
            )

            return latency

        except Exception as e:
            logger.warning(f"Erreur de ping {peer.peer_id}: {e}")
            peer.error_count += 1
            return float('inf')

    # ============================================================
    # MÉTHODES INTERNES
    # ============================================================

    async def _create_peer(self, node_id: str, data: Dict[str, Any]) -> Optional[Peer]:
        """Crée un pair à partir de données"""
        try:
            return Peer(
                peer_id=f"peer_{uuid.uuid4().hex[:12]}",
                address=data.get("address", ""),
                port=data.get("port", 0),
                protocol=data.get("protocol", "unknown"),
                status=PeerStatus.UNKNOWN,
                score=PeerScore.AVERAGE,
                latency=data.get("latency", 0),
                last_seen=datetime.now(),
                first_seen=datetime.now(),
                metadata=data.get("metadata", {}),
            )

        except Exception as e:
            logger.warning(f"Erreur de création de pair: {e}")
            return None

    async def _connect_peer(self, node: BaseNode, peer: Peer) -> bool:
        """Tente de se connecter à un pair"""
        try:
            # Simulation de connexion
            await asyncio.sleep(0.5)

            peer.status = PeerStatus.CONNECTED
            peer.connected_since = datetime.now()
            peer.last_seen = datetime.now()

            return True

        except Exception as e:
            peer.status = PeerStatus.FAILED
            peer.error_count += 1
            return False

    async def _cleanup_inactive_peers(self) -> None:
        """Nettoie les pairs inactifs"""
        cutoff = datetime.now() - timedelta(minutes=10)

        to_remove = []
        for peer_id, peer in self._peers.items():
            if peer.status == PeerStatus.DISCONNECTED and peer.last_seen < cutoff:
                to_remove.append(peer_id)

        for peer_id in to_remove:
            await self.remove_peer(peer_id)

    async def _update_peer_scores(self) -> None:
        """Met à jour les scores des pairs"""
        for peer in self._peers.values():
            # Calcul du score basé sur la latence et les erreurs
            score = 1.0

            # Latence
            if peer.latency > 0:
                if peer.latency < 0.1:
                    score *= 1.5
                elif peer.latency < 0.5:
                    score *= 1.2
                elif peer.latency < 1.0:
                    score *= 1.0
                else:
                    score *= 0.8

            # Erreurs
            if peer.error_count > 0:
                score *= max(0.5, 1 - (peer.error_count / 10))

            # Détermination du score
            if score >= 0.9:
                peer.score = PeerScore.EXCELLENT
            elif score >= 0.7:
                peer.score = PeerScore.GOOD
            elif score >= 0.5:
                peer.score = PeerScore.AVERAGE
            elif score >= 0.3:
                peer.score = PeerScore.POOR
            else:
                peer.score = PeerScore.BAD

    async def _manage_bans(self) -> None:
        """Gère les bans"""
        for peer in self._peers.values():
            # Ban si trop d'erreurs
            if peer.error_count >= self.config["ban_threshold"]:
                await self.ban_peer(peer.peer_id, "Trop d'erreurs")

            # Ban si score trop faible
            if peer.score == PeerScore.BAD:
                await self.ban_peer(peer.peer_id, "Score trop faible")

    async def _get_worst_peer(self) -> Optional[Peer]:
        """Obtient le pire pair"""
        if not self._peers:
            return None

        return max(self._peers.values(), key=lambda p: p.latency if p.latency > 0 else float('inf'))

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques du gestionnaire"""
        return {
            "total_peers": len(self._peers),
            "banned_peers": len(self._banned_peers),
            "active_discoveries": len(self._active_discoveries),
            "total_discoveries": len(self._discoveries),
            "config": self.config,
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NodePeerManager...")

        self._peers.clear()
        self._banned_peers.clear()
        self._discoveries.clear()
        self._active_discoveries.clear()

        if self._session:
            await self._session.close()
            self._session = None

        self._executor.shutdown(wait=True)

        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_node_peer_manager(
    config: Dict[str, Any],
    **kwargs,
) -> NodePeerManager:
    """
    Crée une instance de NodePeerManager

    Args:
        config: Configuration
        **kwargs: Arguments additionnels

    Returns:
        Instance de NodePeerManager
    """
    return NodePeerManager(
        config=config,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NodePeerManager"""
    # Configuration
    config = {
        "max_peers": 50,
        "min_peers": 10,
        "connect_timeout": 10,
        "ping_interval": 30,
        "ban_threshold": 5,
    }

    # Création du gestionnaire
    peer_manager = create_node_peer_manager(config=config)

    # Création d'un nœud de test
    class TestNode:
        def __init__(self):
            self.config = NodeConfig(
                node_id="test_node",
                protocol=NodeProtocol.ETHEREUM,
                node_type=NodeType.FULL,
                endpoint="https://mainnet.infura.io/v3/YOUR_KEY",
            )

        async def get_peers(self):
            return [
                {"address": "192.168.1.1", "port": 30303, "protocol": "eth"},
                {"address": "192.168.1.2", "port": 30303, "protocol": "eth"},
                {"address": "192.168.1.3", "port": 30303, "protocol": "eth"},
            ]

    node = TestNode()

    # Découverte de pairs
    discovery = await peer_manager.discover_peers(node)
    print(f"Découverte: {discovery.to_dict()}")

    # Récupération des pairs
    peers = await peer_manager.get_peers()
    print(f"Pairs trouvés: {len(peers)}")

    for peer in peers[:3]:
        print(f"  {peer.address}:{peer.port} - {peer.status.value}")

    # Statistiques
    stats = await peer_manager.get_stats()
    print(f"Statistiques: {stats.to_dict()}")

    # Maintenance
    await peer_manager.maintain_connections(node)

    # Statistiques du gestionnaire
    manager_stats = peer_manager.get_statistics()
    print(f"Statistiques du gestionnaire: {manager_stats}")

    # Nettoyage
    await peer_manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
