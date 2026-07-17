# blockchain/nodes/__init__.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Nodes - Gestion des Nœuds Blockchain

Ce module fournit une interface unifiée pour la gestion des nœuds blockchain,
supportant Ethereum, BSC, Polygon, Solana, et d'autres protocoles majeurs.

Sous-modules:
- base_node: Classe de base pour tous les nœuds
- node_config: Configuration centralisée des nœuds
- node_manager: Gestionnaire centralisé des nœuds
- node_rpc: Client RPC avancé
- node_websocket: Gestion des WebSockets
- node_cache: Système de cache
- node_health: Monitoring de la santé
- node_metrics: Collecte de métriques
- node_monitor: Monitoring avancé
- node_peers: Gestion des pairs
- node_sync: Synchronisation des blocs
- node_backup: Sauvegarde et restauration
- node_recovery: Récupération automatique
- eth_node: Nœud Ethereum
- bsc_node: Nœud BSC
- polygon_node: Nœud Polygon
- solana_node: Nœud Solana
"""

# ============================================================
# VERSION
# ============================================================

__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD. All Rights Reserved."


# ============================================================
# EXPORTS PRINCIPAUX
# ============================================================

# Classe de base
from .base_node import (
    BaseNode,
    NodeType,
    NodeStatus,
    NodeProtocol,
    NodeHealth,
    NodeConfig,
)

# Configuration
from .node_config import (
    NodeConfigManager,
    NodeEnvironment,
    NodeLoadBalancing,
    NodeAPIConfig,
    NodeNetworkConfig,
    NodeSecurityConfig,
    NodeMonitoringConfig,
    NodeGlobalConfig,
)

# Gestionnaire principal
from .node_manager import (
    NodeManager,
    NodeManagerStatus,
    NodePool,
    NodeManagerState,
    LoadBalancingStrategy,
)

# Client RPC
from .node_rpc import (
    NodeRPCClient,
    RPCMethod,
    RPCProtocol,
    RPCRequest,
    RPCResponse,
    RPCBatch,
)

# WebSocket
from .node_websocket import (
    NodeWebSocketManager,
    WebSocketEventType,
    WebSocketSubscription,
    WebSocketConnection,
    WebSocketMessage,
    WebSocketStats,
)

# Cache
from .node_cache import (
    NodeCache,
    CacheType,
    CacheStrategy,
    CachePolicy,
    CacheConfig,
    CacheStats,
    CacheEntry,
)

# Santé
from .node_health import (
    NodeHealthManager,
    HealthStatus,
    HealthMetric,
    HealthCheckResult,
    HealthAlert,
    HealthHistory,
)

# Métriques
from .node_metrics import (
    NodeMetricsCollector,
    MetricType,
    MetricCategory,
    MetricPoint,
    NodeMetric,
    MetricAlert,
    MetricTrend,
)

# Monitoring
from .node_monitor import (
    NodeMonitor,
    MonitorStatus,
    AlertSeverity,
    MonitorEventType,
    MonitorEvent,
    MonitorDashboard,
    MonitorReport,
)

# Pairs
from .node_peers import (
    NodePeerManager,
    PeerStatus,
    PeerScore,
    Peer,
    PeerStats,
    PeerDiscovery,
)

# Synchronisation
from .node_sync import (
    NodeSyncManager,
    SyncStatus,
    SyncMode,
    SyncState,
    SyncCheckpoint,
    SyncReport,
)

# Sauvegarde
from .node_backup import (
    NodeBackupManager,
    BackupType,
    BackupStatus,
    BackupStorage,
    BackupMetadata,
    BackupConfig,
    BackupResult,
)

# Récupération
from .node_recovery import (
    NodeRecoveryManager,
    RecoveryStatus,
    RecoveryStrategy,
    IncidentType,
    Incident,
    RecoveryPlan,
    RecoveryResult,
)

# Implémentations des nœuds
from .eth_node import (
    ETHNode,
    ETHNodeType,
    ETHSyncMode,
    ETHBlock,
    ETHTransaction,
    ETHLog,
)

from .bsc_node import (
    BSCNode,
    BSCNodeType,
    BSCBlock,
    BSCValidator,
)

from .polygon_node import (
    PolygonNode,
    PolygonNodeType,
    PolygonBlock,
    PolygonValidator,
)

from .solana_node import (
    SolanaNode,
    SolanaNodeType,
    SolanaCommitment,
    SolanaBlock,
    SolanaTransaction,
    SolanaValidator,
)


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
    from .node_manager import NodeManager
    return NodeManager(
        config=config,
        **kwargs,
    )


def create_node_rpc_client(
    config: Dict[str, Any],
    **kwargs,
) -> NodeRPCClient:
    """
    Crée une instance de NodeRPCClient

    Args:
        config: Configuration
        **kwargs: Arguments additionnels

    Returns:
        Instance de NodeRPCClient
    """
    from .node_rpc import NodeRPCClient
    return NodeRPCClient(
        config=config,
        **kwargs,
    )


def create_node_websocket_manager(
    config: Dict[str, Any],
    **kwargs,
) -> NodeWebSocketManager:
    """
    Crée une instance de NodeWebSocketManager

    Args:
        config: Configuration
        **kwargs: Arguments additionnels

    Returns:
        Instance de NodeWebSocketManager
    """
    from .node_websocket import NodeWebSocketManager
    return NodeWebSocketManager(
        config=config,
        **kwargs,
    )


def create_node_cache(
    config: Dict[str, Any],
    **kwargs,
) -> NodeCache:
    """
    Crée une instance de NodeCache

    Args:
        config: Configuration
        **kwargs: Arguments additionnels

    Returns:
        Instance de NodeCache
    """
    from .node_cache import NodeCache
    return NodeCache(
        config=config,
        **kwargs,
    )


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
    from .node_health import NodeHealthManager
    return NodeHealthManager(
        config=config,
        **kwargs,
    )


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
    from .node_metrics import NodeMetricsCollector
    return NodeMetricsCollector(
        config=config,
        **kwargs,
    )


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
    from .node_monitor import NodeMonitor
    return NodeMonitor(
        config=config,
        node_manager=node_manager,
        health_manager=health_manager,
        metrics_collector=metrics_collector,
        **kwargs,
    )


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
    from .node_peers import NodePeerManager
    return NodePeerManager(
        config=config,
        **kwargs,
    )


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
    from .node_sync import NodeSyncManager
    return NodeSyncManager(
        config=config,
        rpc_client=rpc_client,
        **kwargs,
    )


def create_node_backup_manager(
    config: Dict[str, Any],
    **kwargs,
) -> NodeBackupManager:
    """
    Crée une instance de NodeBackupManager

    Args:
        config: Configuration
        **kwargs: Arguments additionnels

    Returns:
        Instance de NodeBackupManager
    """
    from .node_backup import NodeBackupManager
    return NodeBackupManager(
        config=config,
        **kwargs,
    )


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
    from .node_recovery import NodeRecoveryManager
    return NodeRecoveryManager(
        config=config,
        node_manager=node_manager,
        health_manager=health_manager,
        **kwargs,
    )


def create_eth_node(
    endpoint: str,
    node_id: Optional[str] = None,
    node_type: str = "mainnet",
    **kwargs,
) -> ETHNode:
    """
    Crée une instance de ETHNode

    Args:
        endpoint: Endpoint RPC
        node_id: ID du nœud (optionnel)
        node_type: Type de nœud
        **kwargs: Arguments additionnels

    Returns:
        Instance de ETHNode
    """
    from .eth_node import create_eth_node
    return create_eth_node(
        endpoint=endpoint,
        node_id=node_id,
        node_type=node_type,
        **kwargs,
    )


def create_bsc_node(
    endpoint: str,
    node_id: Optional[str] = None,
    node_type: str = "mainnet",
    **kwargs,
) -> BSCNode:
    """
    Crée une instance de BSCNode

    Args:
        endpoint: Endpoint RPC
        node_id: ID du nœud (optionnel)
        node_type: Type de nœud
        **kwargs: Arguments additionnels

    Returns:
        Instance de BSCNode
    """
    from .bsc_node import create_bsc_node
    return create_bsc_node(
        endpoint=endpoint,
        node_id=node_id,
        node_type=node_type,
        **kwargs,
    )


def create_polygon_node(
    endpoint: str,
    node_id: Optional[str] = None,
    node_type: str = "mainnet",
    **kwargs,
) -> PolygonNode:
    """
    Crée une instance de PolygonNode

    Args:
        endpoint: Endpoint RPC
        node_id: ID du nœud (optionnel)
        node_type: Type de nœud
        **kwargs: Arguments additionnels

    Returns:
        Instance de PolygonNode
    """
    from .polygon_node import create_polygon_node
    return create_polygon_node(
        endpoint=endpoint,
        node_id=node_id,
        node_type=node_type,
        **kwargs,
    )


def create_solana_node(
    endpoint: str,
    node_id: Optional[str] = None,
    node_type: str = "mainnet",
    **kwargs,
) -> SolanaNode:
    """
    Crée une instance de SolanaNode

    Args:
        endpoint: Endpoint RPC
        node_id: ID du nœud (optionnel)
        node_type: Type de nœud
        **kwargs: Arguments additionnels

    Returns:
        Instance de SolanaNode
    """
    from .solana_node import create_solana_node
    return create_solana_node(
        endpoint=endpoint,
        node_id=node_id,
        node_type=node_type,
        **kwargs,
    )


# ============================================================
# EXPORTS POUR LA DOCUMENTATION
# ============================================================

__all__ = [
    # Versions et métadonnées
    "__version__",
    "__author__",
    "__copyright__",

    # Classe de base
    "BaseNode",
    "NodeType",
    "NodeStatus",
    "NodeProtocol",
    "NodeHealth",
    "NodeConfig",

    # Configuration
    "NodeConfigManager",
    "NodeEnvironment",
    "NodeLoadBalancing",
    "NodeAPIConfig",
    "NodeNetworkConfig",
    "NodeSecurityConfig",
    "NodeMonitoringConfig",
    "NodeGlobalConfig",

    # Gestionnaire principal
    "NodeManager",
    "NodeManagerStatus",
    "NodePool",
    "NodeManagerState",
    "LoadBalancingStrategy",

    # Client RPC
    "NodeRPCClient",
    "RPCMethod",
    "RPCProtocol",
    "RPCRequest",
    "RPCResponse",
    "RPCBatch",

    # WebSocket
    "NodeWebSocketManager",
    "WebSocketEventType",
    "WebSocketSubscription",
    "WebSocketConnection",
    "WebSocketMessage",
    "WebSocketStats",

    # Cache
    "NodeCache",
    "CacheType",
    "CacheStrategy",
    "CachePolicy",
    "CacheConfig",
    "CacheStats",
    "CacheEntry",

    # Santé
    "NodeHealthManager",
    "HealthStatus",
    "HealthMetric",
    "HealthCheckResult",
    "HealthAlert",
    "HealthHistory",

    # Métriques
    "NodeMetricsCollector",
    "MetricType",
    "MetricCategory",
    "MetricPoint",
    "NodeMetric",
    "MetricAlert",
    "MetricTrend",

    # Monitoring
    "NodeMonitor",
    "MonitorStatus",
    "AlertSeverity",
    "MonitorEventType",
    "MonitorEvent",
    "MonitorDashboard",
    "MonitorReport",

    # Pairs
    "NodePeerManager",
    "PeerStatus",
    "PeerScore",
    "Peer",
    "PeerStats",
    "PeerDiscovery",

    # Synchronisation
    "NodeSyncManager",
    "SyncStatus",
    "SyncMode",
    "SyncState",
    "SyncCheckpoint",
    "SyncReport",

    # Sauvegarde
    "NodeBackupManager",
    "BackupType",
    "BackupStatus",
    "BackupStorage",
    "BackupMetadata",
    "BackupConfig",
    "BackupResult",

    # Récupération
    "NodeRecoveryManager",
    "RecoveryStatus",
    "RecoveryStrategy",
    "IncidentType",
    "Incident",
    "RecoveryPlan",
    "RecoveryResult",

    # Implémentations des nœuds
    "ETHNode",
    "ETHNodeType",
    "ETHSyncMode",
    "ETHBlock",
    "ETHTransaction",
    "ETHLog",

    "BSCNode",
    "BSCNodeType",
    "BSCBlock",
    "BSCValidator",

    "PolygonNode",
    "PolygonNodeType",
    "PolygonBlock",
    "PolygonValidator",

    "SolanaNode",
    "SolanaNodeType",
    "SolanaCommitment",
    "SolanaBlock",
    "SolanaTransaction",
    "SolanaValidator",

    # Fonctions de création
    "create_node_manager",
    "create_node_rpc_client",
    "create_node_websocket_manager",
    "create_node_cache",
    "create_node_health_manager",
    "create_node_metrics_collector",
    "create_node_monitor",
    "create_node_peer_manager",
    "create_node_sync_manager",
    "create_node_backup_manager",
    "create_node_recovery_manager",
    "create_eth_node",
    "create_bsc_node",
    "create_polygon_node",
    "create_solana_node",
]


# ============================================================
# INITIALISATION DU MODULE
# ============================================================

logger = get_logger(__name__)
logger.info(f"Module Nodes chargé (v{__version__})")


# ============================================================
# EXEMPLE D'UTILISATION RAPIDE
# ============================================================

async def quick_example():
    """Exemple rapide d'utilisation du module Nodes"""
    # Configuration
    config = {
        "environment": "production",
        "load_balancing": "round_robin",
        "nodes": {
            "eth_main": {
                "node_id": "eth_main",
                "protocol": "ethereum",
                "node_type": "full",
                "endpoint": "https://mainnet.infura.io/v3/YOUR_KEY",
                "chain_id": 1,
            },
            "bsc_main": {
                "node_id": "bsc_main",
                "protocol": "bsc",
                "node_type": "full",
                "endpoint": "https://bsc-dataseed.binance.org",
                "chain_id": 56,
            },
        },
    }

    # Création du gestionnaire
    manager = create_node_manager(config=config)

    # Connexion
    await manager.connect_all()

    # Exécution d'une requête
    result = await manager.execute_request(
        protocol=NodeProtocol.ETHEREUM,
        method="eth_blockNumber",
        params=[],
    )
    print(f"Bloc Ethereum: {result}")

    # Statistiques
    stats = manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(quick_example())
