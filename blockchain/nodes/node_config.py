# blockchain/nodes/node_config.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module Node Config - Configuration Centralisée des Nœuds

Ce module gère la configuration centralisée de tous les nœuds blockchain,
incluant les endpoints RPC, les clés API, les paramètres de connexion,
et les configurations de sécurité.

Fonctionnalités principales:
- Configuration centralisée des nœuds
- Gestion des endpoints RPC/WebSocket
- Gestion des clés API
- Configuration des timeouts
- Gestion des retries
- Support multi-protocoles
- Validation des configurations
- Mise à jour dynamique
"""

import json
import logging
import os
import yaml
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)
from pathlib import Path
from collections import defaultdict
from functools import lru_cache

# Import des modules internes
try:
    from ..core.exceptions import ConfigError, ValidationError
    from ..core.logging import get_logger
    from ..core.metrics import MetricsCollector
    from ..security.encryption import EncryptionManager
    from .base_node import NodeConfig, NodeProtocol, NodeType, NodeHealth, NodeStatus
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import ConfigError, ValidationError
    from ..core.metrics import MetricsCollector
    from ..security.encryption import EncryptionManager
    from .base_node import NodeConfig, NodeProtocol, NodeType, NodeHealth, NodeStatus

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class NodeEnvironment(Enum):
    """Environnements des nœuds"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class NodeLoadBalancing(Enum):
    """Stratégies de load balancing"""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    WEIGHTED = "weighted"
    HEALTH_BASED = "health_based"


@dataclass
class NodeAPIConfig:
    """Configuration API d'un nœud"""
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    api_url: Optional[str] = None
    rate_limit: int = 100  # Requêtes par minute
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "api_key": self.api_key,
            "api_secret": "[REDACTED]" if self.api_secret else None,
            "api_url": self.api_url,
            "rate_limit": self.rate_limit,
            "timeout": self.timeout,
            "retry_attempts": self.retry_attempts,
            "retry_delay": self.retry_delay,
            "metadata": self.metadata,
        }


@dataclass
class NodeNetworkConfig:
    """Configuration réseau d'un nœud"""
    protocol: NodeProtocol
    chain_id: int
    main_endpoint: str
    backup_endpoints: List[str] = field(default_factory=list)
    ws_endpoint: Optional[str] = None
    ws_backup_endpoints: List[str] = field(default_factory=list)
    load_balancing: NodeLoadBalancing = NodeLoadBalancing.ROUND_ROBIN
    health_check_interval: int = 60
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "protocol": self.protocol.value,
            "chain_id": self.chain_id,
            "main_endpoint": self.main_endpoint,
            "backup_endpoints": self.backup_endpoints,
            "ws_endpoint": self.ws_endpoint,
            "ws_backup_endpoints": self.ws_backup_endpoints,
            "load_balancing": self.load_balancing.value,
            "health_check_interval": self.health_check_interval,
            "metadata": self.metadata,
        }


@dataclass
class NodeSecurityConfig:
    """Configuration de sécurité d'un nœud"""
    tls_enabled: bool = True
    verify_ssl: bool = True
    allowed_ips: List[str] = field(default_factory=list)
    whitelist_endpoints: List[str] = field(default_factory=list)
    blacklist_endpoints: List[str] = field(default_factory=list)
    rate_limiting: bool = True
    max_connections: int = 100
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "tls_enabled": self.tls_enabled,
            "verify_ssl": self.verify_ssl,
            "allowed_ips": self.allowed_ips,
            "whitelist_endpoints": self.whitelist_endpoints,
            "blacklist_endpoints": self.blacklist_endpoints,
            "rate_limiting": self.rate_limiting,
            "max_connections": self.max_connections,
            "metadata": self.metadata,
        }


@dataclass
class NodeMonitoringConfig:
    """Configuration de monitoring d'un nœud"""
    enabled: bool = True
    metrics_interval: int = 60
    health_check_enabled: bool = True
    health_check_timeout: int = 5
    alert_thresholds: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "enabled": self.enabled,
            "metrics_interval": self.metrics_interval,
            "health_check_enabled": self.health_check_enabled,
            "health_check_timeout": self.health_check_timeout,
            "alert_thresholds": self.alert_thresholds,
            "metadata": self.metadata,
        }


@dataclass
class NodeGlobalConfig:
    """Configuration globale des nœuds"""
    version: str
    environment: NodeEnvironment
    nodes: Dict[str, NodeConfig]
    network_configs: Dict[str, NodeNetworkConfig]
    security_configs: Dict[str, NodeSecurityConfig]
    monitoring_configs: Dict[str, NodeMonitoringConfig]
    default_timeout: int = 30
    default_retries: int = 3
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "version": self.version,
            "environment": self.environment.value,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "network_configs": {k: v.to_dict() for k, v in self.network_configs.items()},
            "security_configs": {k: v.to_dict() for k, v in self.security_configs.items()},
            "monitoring_configs": {k: v.to_dict() for k, v in self.monitoring_configs.items()},
            "default_timeout": self.default_timeout,
            "default_retries": self.default_retries,
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# CONFIGURATIONS PAR DÉFAUT
# ============================================================

DEFAULT_NODES = {
    "ethereum_mainnet": {
        "protocol": "ethereum",
        "node_type": "full",
        "endpoint": "https://mainnet.infura.io/v3/YOUR_KEY",
        "backup_endpoints": [
            "https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY",
            "https://rpc.ankr.com/eth",
        ],
        "ws_endpoint": "wss://mainnet.infura.io/ws/v3/YOUR_KEY",
        "chain_id": 1,
        "timeout": 30,
        "max_retries": 3,
        "retry_delay": 1.0,
    },
    "bsc_mainnet": {
        "protocol": "bsc",
        "node_type": "full",
        "endpoint": "https://bsc-dataseed.binance.org",
        "backup_endpoints": [
            "https://bsc-dataseed1.defibit.io",
            "https://bsc-dataseed1.ninicoin.io",
        ],
        "ws_endpoint": "wss://bsc-ws-node.nariox.org",
        "chain_id": 56,
        "timeout": 30,
        "max_retries": 3,
        "retry_delay": 1.0,
    },
    "polygon_mainnet": {
        "protocol": "polygon",
        "node_type": "full",
        "endpoint": "https://polygon-rpc.com",
        "backup_endpoints": [
            "https://rpc-mainnet.maticvigil.com",
            "https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY",
        ],
        "ws_endpoint": "wss://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY",
        "chain_id": 137,
        "timeout": 30,
        "max_retries": 3,
        "retry_delay": 1.0,
    },
    "arbitrum_mainnet": {
        "protocol": "arbitrum",
        "node_type": "full",
        "endpoint": "https://arb1.arbitrum.io/rpc",
        "backup_endpoints": [
            "https://arbitrum-mainnet.infura.io/v3/YOUR_KEY",
            "https://rpc.ankr.com/arbitrum",
        ],
        "ws_endpoint": "wss://arb1.arbitrum.io/ws",
        "chain_id": 42161,
        "timeout": 30,
        "max_retries": 3,
        "retry_delay": 1.0,
    },
    "optimism_mainnet": {
        "protocol": "optimism",
        "node_type": "full",
        "endpoint": "https://mainnet.optimism.io",
        "backup_endpoints": [
            "https://optimism-mainnet.infura.io/v3/YOUR_KEY",
            "https://rpc.ankr.com/optimism",
        ],
        "ws_endpoint": "wss://mainnet.optimism.io/ws",
        "chain_id": 10,
        "timeout": 30,
        "max_retries": 3,
        "retry_delay": 1.0,
    },
    "avalanche_mainnet": {
        "protocol": "avalanche",
        "node_type": "full",
        "endpoint": "https://api.avax.network/ext/bc/C/rpc",
        "backup_endpoints": [
            "https://avalanche-mainnet.infura.io/v3/YOUR_KEY",
            "https://rpc.ankr.com/avalanche",
        ],
        "ws_endpoint": "wss://api.avax.network/ext/bc/C/ws",
        "chain_id": 43114,
        "timeout": 30,
        "max_retries": 3,
        "retry_delay": 1.0,
    },
    "solana_mainnet": {
        "protocol": "solana",
        "node_type": "full",
        "endpoint": "https://api.mainnet-beta.solana.com",
        "backup_endpoints": [
            "https://solana-api.projectserum.com",
            "https://rpc.ankr.com/solana",
        ],
        "ws_endpoint": "wss://api.mainnet-beta.solana.com",
        "chain_id": 101,
        "timeout": 30,
        "max_retries": 3,
        "retry_delay": 1.0,
    },
}

DEFAULT_SECURITY = {
    "tls_enabled": True,
    "verify_ssl": True,
    "rate_limiting": True,
    "max_connections": 100,
}

DEFAULT_MONITORING = {
    "enabled": True,
    "metrics_interval": 60,
    "health_check_enabled": True,
    "health_check_timeout": 5,
    "alert_thresholds": {
        "response_time": 5.0,
        "error_rate": 0.05,
        "block_latency": 30.0,
    },
}


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NodeConfigManager:
    """
    Gestionnaire centralisé de configuration des nœuds
    """

    def __init__(
        self,
        config_dir: Optional[str] = None,
        environment: NodeEnvironment = NodeEnvironment.PRODUCTION,
        encryption_manager: Optional[EncryptionManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de configuration

        Args:
            config_dir: Répertoire des configurations
            environment: Environnement
            encryption_manager: Gestionnaire de chiffrement
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config_dir = config_dir or os.path.join(
            os.path.dirname(__file__), "configs"
        )
        self.environment = environment
        self.encryption_manager = encryption_manager or EncryptionManager()
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # Configuration
        self._config: Optional[NodeGlobalConfig] = None
        self._config_cache: Dict[str, Tuple[float, Any]] = {}

        # Création du répertoire
        os.makedirs(self.config_dir, exist_ok=True)

        # Chargement de la configuration
        self._load_config()

        logger.info(f"NodeConfigManager initialisé (environnement: {environment.value})")

    # ============================================================
    # MÉTHODES DE CHARGEMENT
    # ============================================================

    def _load_config(self) -> None:
        """Charge la configuration complète"""
        try:
            # Chargement des configurations
            nodes = self._load_nodes()
            network_configs = self._load_network_configs()
            security_configs = self._load_security_configs()
            monitoring_configs = self._load_monitoring_configs()

            # Création de la configuration
            self._config = NodeGlobalConfig(
                version="1.0.0",
                environment=self.environment,
                nodes=nodes,
                network_configs=network_configs,
                security_configs=security_configs,
                monitoring_configs=monitoring_configs,
                default_timeout=self.config.get("default_timeout", 30),
                default_retries=self.config.get("default_retries", 3),
                updated_at=datetime.now(),
                metadata={},
            )

            # Validation
            self._validate_config()

            logger.info(
                f"Configuration des nœuds chargée: {len(nodes)} nœuds"
            )

        except Exception as e:
            logger.error(f"Erreur de chargement de la configuration: {e}")
            # Utiliser la configuration par défaut
            self._config = self._create_default_config()
            raise ConfigError(f"Erreur de chargement de la configuration: {e}")

    def _load_nodes(self) -> Dict[str, NodeConfig]:
        """Charge les configurations des nœuds"""
        nodes = {}

        # Chargement depuis les fichiers
        nodes_dir = os.path.join(self.config_dir, "nodes")
        if os.path.exists(nodes_dir):
            for file in os.listdir(nodes_dir):
                if file.endswith((".yaml", ".yml")):
                    node_data = self._load_yaml_file(os.path.join(nodes_dir, file))
                    if node_data and "node_id" in node_data:
                        node_id = node_data["node_id"]
                        nodes[node_id] = self._create_node_config(node_data)

        # Ajout des nœuds par défaut
        for node_id, default_data in DEFAULT_NODES.items():
            if node_id not in nodes:
                nodes[node_id] = self._create_node_config({
                    "node_id": node_id,
                    **default_data,
                })

        return nodes

    def _load_network_configs(self) -> Dict[str, NodeNetworkConfig]:
        """Charge les configurations réseau"""
        network_configs = {}

        # Chargement depuis les fichiers
        network_dir = os.path.join(self.config_dir, "networks")
        if os.path.exists(network_dir):
            for file in os.listdir(network_dir):
                if file.endswith((".yaml", ".yml")):
                    network_data = self._load_yaml_file(os.path.join(network_dir, file))
                    if network_data and "protocol" in network_data:
                        protocol = network_data["protocol"]
                        network_configs[protocol] = self._create_network_config(network_data)

        return network_configs

    def _load_security_configs(self) -> Dict[str, NodeSecurityConfig]:
        """Charge les configurations de sécurité"""
        security_configs = {}

        # Chargement depuis les fichiers
        security_dir = os.path.join(self.config_dir, "security")
        if os.path.exists(security_dir):
            for file in os.listdir(security_dir):
                if file.endswith((".yaml", ".yml")):
                    security_data = self._load_yaml_file(os.path.join(security_dir, file))
                    if security_data and "node_id" in security_data:
                        node_id = security_data["node_id"]
                        security_configs[node_id] = self._create_security_config(security_data)

        return security_configs

    def _load_monitoring_configs(self) -> Dict[str, NodeMonitoringConfig]:
        """Charge les configurations de monitoring"""
        monitoring_configs = {}

        # Chargement depuis les fichiers
        monitoring_dir = os.path.join(self.config_dir, "monitoring")
        if os.path.exists(monitoring_dir):
            for file in os.listdir(monitoring_dir):
                if file.endswith((".yaml", ".yml")):
                    monitoring_data = self._load_yaml_file(os.path.join(monitoring_dir, file))
                    if monitoring_data and "node_id" in monitoring_data:
                        node_id = monitoring_data["node_id"]
                        monitoring_configs[node_id] = self._create_monitoring_config(monitoring_data)

        return monitoring_configs

    def _load_yaml_file(self, path: str) -> Dict[str, Any]:
        """Charge un fichier YAML"""
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Erreur de chargement de {path}: {e}")
            return {}

    # ============================================================
    # MÉTHODES DE CRÉATION
    # ============================================================

    def _create_node_config(self, data: Dict[str, Any]) -> NodeConfig:
        """Crée une configuration de nœud"""
        return NodeConfig(
            node_id=data.get("node_id", f"node_{uuid.uuid4().hex[:8]}"),
            protocol=NodeProtocol(data.get("protocol", "ethereum")),
            node_type=NodeType(data.get("node_type", "full")),
            endpoint=data.get("endpoint", ""),
            backup_endpoints=data.get("backup_endpoints", []),
            ws_endpoint=data.get("ws_endpoint"),
            chain_id=data.get("chain_id"),
            timeout=data.get("timeout", 30),
            max_retries=data.get("max_retries", 3),
            retry_delay=data.get("retry_delay", 1.0),
            metadata=data.get("metadata", {}),
        )

    def _create_network_config(self, data: Dict[str, Any]) -> NodeNetworkConfig:
        """Crée une configuration réseau"""
        return NodeNetworkConfig(
            protocol=NodeProtocol(data.get("protocol", "ethereum")),
            chain_id=data.get("chain_id", 1),
            main_endpoint=data.get("main_endpoint", ""),
            backup_endpoints=data.get("backup_endpoints", []),
            ws_endpoint=data.get("ws_endpoint"),
            ws_backup_endpoints=data.get("ws_backup_endpoints", []),
            load_balancing=NodeLoadBalancing(data.get("load_balancing", "round_robin")),
            health_check_interval=data.get("health_check_interval", 60),
            metadata=data.get("metadata", {}),
        )

    def _create_security_config(self, data: Dict[str, Any]) -> NodeSecurityConfig:
        """Crée une configuration de sécurité"""
        return NodeSecurityConfig(
            tls_enabled=data.get("tls_enabled", True),
            verify_ssl=data.get("verify_ssl", True),
            allowed_ips=data.get("allowed_ips", []),
            whitelist_endpoints=data.get("whitelist_endpoints", []),
            blacklist_endpoints=data.get("blacklist_endpoints", []),
            rate_limiting=data.get("rate_limiting", True),
            max_connections=data.get("max_connections", 100),
            metadata=data.get("metadata", {}),
        )

    def _create_monitoring_config(self, data: Dict[str, Any]) -> NodeMonitoringConfig:
        """Crée une configuration de monitoring"""
        return NodeMonitoringConfig(
            enabled=data.get("enabled", True),
            metrics_interval=data.get("metrics_interval", 60),
            health_check_enabled=data.get("health_check_enabled", True),
            health_check_timeout=data.get("health_check_timeout", 5),
            alert_thresholds=data.get("alert_thresholds", {}),
            metadata=data.get("metadata", {}),
        )

    def _create_default_config(self) -> NodeGlobalConfig:
        """Crée une configuration par défaut"""
        nodes = {}
        for node_id, default_data in DEFAULT_NODES.items():
            nodes[node_id] = self._create_node_config({
                "node_id": node_id,
                **default_data,
            })

        network_configs = {}
        security_configs = {}
        monitoring_configs = {}

        return NodeGlobalConfig(
            version="1.0.0",
            environment=self.environment,
            nodes=nodes,
            network_configs=network_configs,
            security_configs=security_configs,
            monitoring_configs=monitoring_configs,
            default_timeout=30,
            default_retries=3,
            updated_at=datetime.now(),
            metadata={},
        )

    # ============================================================
    # MÉTHODES DE VALIDATION
    # ============================================================

    def _validate_config(self) -> None:
        """Valide la configuration"""
        if not self._config:
            raise ConfigError("Configuration non chargée")

        # Validation des nœuds
        for node_id, node in self._config.nodes.items():
            if not node.endpoint:
                raise ConfigError(f"Endpoint manquant pour le nœud {node_id}")

            if node.timeout <= 0:
                raise ConfigError(f"Timeout invalide pour {node_id}")

            if node.max_retries < 0:
                raise ConfigError(f"Max retries invalide pour {node_id}")

        # Validation des configurations réseau
        for protocol, network in self._config.network_configs.items():
            if not network.main_endpoint:
                raise ConfigError(f"Endpoint principal manquant pour {protocol}")

        # Validation des configurations de sécurité
        for node_id, security in self._config.security_configs.items():
            if security.max_connections <= 0:
                raise ConfigError(f"Max connections invalide pour {node_id}")

        logger.info("Configuration validée avec succès")

    # ============================================================
    # MÉTHODES D'ACCÈS
    # ============================================================

    def get_config(self) -> NodeGlobalConfig:
        """Obtient la configuration complète"""
        if not self._config:
            self._load_config()
        return self._config

    def get_node_config(self, node_id: str) -> Optional[NodeConfig]:
        """Obtient la configuration d'un nœud"""
        return self._config.nodes.get(node_id)

    def get_node_by_protocol(self, protocol: str) -> Optional[NodeConfig]:
        """Obtient un nœud par protocole"""
        for node in self._config.nodes.values():
            if node.protocol.value == protocol:
                return node
        return None

    def get_network_config(self, protocol: str) -> Optional[NodeNetworkConfig]:
        """Obtient la configuration réseau d'un protocole"""
        return self._config.network_configs.get(protocol)

    def get_security_config(self, node_id: str) -> Optional[NodeSecurityConfig]:
        """Obtient la configuration de sécurité d'un nœud"""
        return self._config.security_configs.get(node_id)

    def get_monitoring_config(self, node_id: str) -> Optional[NodeMonitoringConfig]:
        """Obtient la configuration de monitoring d'un nœud"""
        return self._config.monitoring_configs.get(node_id)

    def get_all_nodes(self) -> List[NodeConfig]:
        """Obtient tous les nœuds"""
        return list(self._config.nodes.values())

    def get_enabled_nodes(self) -> List[NodeConfig]:
        """Obtient les nœuds actifs"""
        return [
            node for node in self._config.nodes.values()
            if node.enabled
        ]

    def get_endpoints(self, node_id: str) -> List[str]:
        """
        Obtient tous les endpoints d'un nœud

        Args:
            node_id: ID du nœud

        Returns:
            Liste des endpoints
        """
        node = self.get_node_config(node_id)
        if not node:
            return []

        endpoints = [node.endpoint]
        endpoints.extend(node.backup_endpoints)

        return endpoints

    def get_ws_endpoints(self, node_id: str) -> List[str]:
        """
        Obtient tous les endpoints WebSocket d'un nœud

        Args:
            node_id: ID du nœud

        Returns:
            Liste des endpoints WebSocket
        """
        node = self.get_node_config(node_id)
        if not node:
            return []

        endpoints = []
        if node.ws_endpoint:
            endpoints.append(node.ws_endpoint)

        return endpoints

    # ============================================================
    # MÉTHODES DE MISE À JOUR
    # ============================================================

    def update_config(self, new_config: NodeGlobalConfig) -> None:
        """Met à jour la configuration"""
        self._config = new_config
        self._validate_config()
        self._config.updated_at = datetime.now()
        self._config_cache.clear()
        logger.info("Configuration des nœuds mise à jour")

    def reload_config(self) -> None:
        """Recharge la configuration"""
        self._load_config()
        logger.info("Configuration des nœuds rechargée")

    def save_config(self, path: Optional[str] = None) -> None:
        """Sauvegarde la configuration"""
        if not self._config:
            return

        save_path = path or os.path.join(self.config_dir, "node_config.yaml")

        try:
            with open(save_path, 'w') as f:
                yaml.dump(self._config.to_dict(), f, default_flow_style=False)
            logger.info(f"Configuration des nœuds sauvegardée: {save_path}")
        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {e}")
            raise ConfigError(f"Erreur de sauvegarde: {e}")

    # ============================================================
    # MÉTHODES DE STATISTIQUES
    # ============================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Obtient les statistiques de configuration"""
        if not self._config:
            return {}

        return {
            "total_nodes": len(self._config.nodes),
            "enabled_nodes": len([n for n in self._config.nodes.values() if n.enabled]),
            "protocols": list(set(n.protocol.value for n in self._config.nodes.values())),
            "environment": self.environment.value,
            "version": self._config.version,
            "updated_at": self._config.updated_at.isoformat(),
            "network_configs": len(self._config.network_configs),
            "security_configs": len(self._config.security_configs),
            "monitoring_configs": len(self._config.monitoring_configs),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NodeConfigManager...")
        self._config_cache.clear()
        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_node_config_manager(
    config_dir: Optional[str] = None,
    environment: str = "production",
    **kwargs,
) -> NodeConfigManager:
    """
    Crée une instance de NodeConfigManager

    Args:
        config_dir: Répertoire des configurations
        environment: Environnement
        **kwargs: Arguments additionnels

    Returns:
        Instance de NodeConfigManager
    """
    env = NodeEnvironment(environment.lower())
    return NodeConfigManager(
        config_dir=config_dir,
        environment=env,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NodeConfigManager"""
    # Création du gestionnaire
    config_manager = create_node_config_manager(
        config_dir="./node_configs",
        environment="production",
    )

    # Obtention de la configuration
    config = config_manager.get_config()
    print(f"Version: {config.version}")
    print(f"Environnement: {config.environment.value}")

    # Obtention d'un nœud
    node = config_manager.get_node_config("ethereum_mainnet")
    if node:
        print(f"\nNœud Ethereum:")
        print(f"  Endpoint: {node.endpoint}")
        print(f"  Chain ID: {node.chain_id}")
        print(f"  Timeout: {node.timeout}s")

    # Obtention des endpoints
    endpoints = config_manager.get_endpoints("ethereum_mainnet")
    print(f"\nEndpoints Ethereum:")
    for endpoint in endpoints:
        print(f"  {endpoint}")

    # Obtention de la configuration réseau
    network = config_manager.get_network_config("ethereum")
    if network:
        print(f"\nConfiguration réseau Ethereum:")
        print(f"  Load balancing: {network.load_balancing.value}")
        print(f"  Health check interval: {network.health_check_interval}s")

    # Statistiques
    stats = config_manager.get_statistics()
    print(f"\nStatistiques: {stats}")

    # Sauvegarde
    config_manager.save_config()

    # Nettoyage
    await config_manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
