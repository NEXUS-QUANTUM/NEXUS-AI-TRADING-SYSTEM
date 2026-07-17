# blockchain/nft/nft_config.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module NFT Config - Configuration Centralisée des NFTs

Ce module gère la configuration centralisée de tous les composants NFT,
incluant les adresses de contrats, les collections populaires,
les paramètres de marketplace, et les configurations de sécurité.

Fonctionnalités principales:
- Configuration centralisée des collections NFT
- Gestion des adresses de contrats
- Configuration des marketplaces
- Paramètres de royalties
- Configuration des métadonnées
- Gestion des environnements
- Validation des configurations
- Mise à jour dynamique
"""

import json
import logging
import os
import yaml
import time
from dataclasses import dataclass, field
from decimal import Decimal
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
    from .base_nft import NFTStandard
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import ConfigError, ValidationError
    from ..core.metrics import MetricsCollector
    from .base_nft import NFTStandard

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class NFTEnvironment(Enum):
    """Environnements NFT"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class NFTMarketplace(Enum):
    """Marketplaces NFT supportées"""
    OPENSEA = "opensea"
    BLUR = "blur"
    LOOKSRARE = "looksrare"
    RARIBLE = "rarible"
    FOUNDATION = "foundation"
    SUPERRARE = "superrare"
    KNOWN_ORIGIN = "known_origin"


class NFTChain(Enum):
    """Chaînes supportées pour les NFTs"""
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    BASE = "base"
    BSC = "bsc"
    SOLANA = "solana"


@dataclass
class NFTContractConfig:
    """Configuration d'un contrat NFT"""
    address: str
    name: str
    symbol: str
    standard: NFTStandard
    chain: str
    total_supply: Optional[int] = None
    block_deployed: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "address": self.address,
            "name": self.name,
            "symbol": self.symbol,
            "standard": self.standard.value,
            "chain": self.chain,
            "total_supply": self.total_supply,
            "block_deployed": self.block_deployed,
            "metadata": self.metadata,
        }


@dataclass
class NFTCollectionConfig:
    """Configuration d'une collection NFT"""
    collection_id: str
    name: str
    symbol: str
    description: str
    chain: str
    contract_address: str
    standard: NFTStandard
    category: str
    floor_price: Decimal
    total_supply: int
    royalty_percentage: Decimal
    royalty_address: str
    metadata_uri: str
    image: Optional[str] = None
    external_url: Optional[str] = None
    is_verified: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "collection_id": self.collection_id,
            "name": self.name,
            "symbol": self.symbol,
            "description": self.description,
            "chain": self.chain,
            "contract_address": self.contract_address,
            "standard": self.standard.value,
            "category": self.category,
            "floor_price": str(self.floor_price),
            "total_supply": self.total_supply,
            "royalty_percentage": str(self.royalty_percentage),
            "royalty_address": self.royalty_address,
            "metadata_uri": self.metadata_uri,
            "image": self.image,
            "external_url": self.external_url,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class NFTMarketplaceConfig:
    """Configuration d'une marketplace NFT"""
    marketplace: NFTMarketplace
    chain: str
    contract_address: str
    router_address: Optional[str] = None
    execution_delegate: Optional[str] = None
    fee_percentage: Decimal = Decimal("0.025")
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "marketplace": self.marketplace.value,
            "chain": self.chain,
            "contract_address": self.contract_address,
            "router_address": self.router_address,
            "execution_delegate": self.execution_delegate,
            "fee_percentage": str(self.fee_percentage),
            "enabled": self.enabled,
            "metadata": self.metadata,
        }


@dataclass
class NFTGlobalConfig:
    """Configuration globale NFT"""
    version: str
    environment: NFTEnvironment
    collections: Dict[str, NFTCollectionConfig]
    contracts: Dict[str, NFTContractConfig]
    marketplaces: Dict[str, NFTMarketplaceConfig]
    metadata_settings: Dict[str, Any]
    security_settings: Dict[str, Any]
    monitoring_settings: Dict[str, Any]
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "version": self.version,
            "environment": self.environment.value,
            "collections": {k: v.to_dict() for k, v in self.collections.items()},
            "contracts": {k: v.to_dict() for k, v in self.contracts.items()},
            "marketplaces": {k: v.to_dict() for k, v in self.marketplaces.items()},
            "metadata_settings": self.metadata_settings,
            "security_settings": self.security_settings,
            "monitoring_settings": self.monitoring_settings,
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# CONFIGURATIONS PAR DÉFAUT
# ============================================================

DEFAULT_COLLECTIONS = {
    "bored_ape_yacht_club": {
        "name": "Bored Ape Yacht Club",
        "symbol": "BAYC",
        "description": "Bored Ape Yacht Club is a collection of 10,000 unique Bored Ape NFTs",
        "chain": "ethereum",
        "contract_address": "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D",
        "standard": "erc721",
        "category": "profile_picture",
        "floor_price": "30",
        "total_supply": 10000,
        "royalty_percentage": "2.5",
        "royalty_address": "0x...",
        "metadata_uri": "https://api.boredapeyachtclub.com/metadata/",
        "image": "https://ipfs.io/ipfs/Qm...",
        "is_verified": True,
    },
    "mutant_ape_yacht_club": {
        "name": "Mutant Ape Yacht Club",
        "symbol": "MAYC",
        "description": "Mutant Ape Yacht Club is a collection of 20,000 Mutant Ape NFTs",
        "chain": "ethereum",
        "contract_address": "0x60E4d786628Fea6478F785A6d7e704777c86a7c6",
        "standard": "erc721",
        "category": "profile_picture",
        "floor_price": "6",
        "total_supply": 20000,
        "royalty_percentage": "2.5",
        "royalty_address": "0x...",
        "metadata_uri": "https://api.mutantapeyachtclub.com/metadata/",
        "is_verified": True,
    },
    "azuki": {
        "name": "Azuki",
        "symbol": "AZUKI",
        "description": "Azuki is a collection of 10,000 anime-inspired NFTs",
        "chain": "ethereum",
        "contract_address": "0xED5AF388653567Af2F388E6224dC7C4b3241C544",
        "standard": "erc721",
        "category": "profile_picture",
        "floor_price": "7",
        "total_supply": 10000,
        "royalty_percentage": "2.5",
        "royalty_address": "0x...",
        "metadata_uri": "https://api.azuki.com/metadata/",
        "is_verified": True,
    },
    "doodles": {
        "name": "Doodles",
        "symbol": "DOODLE",
        "description": "Doodles is a collection of 10,000 NFTs featuring unique doodles",
        "chain": "ethereum",
        "contract_address": "0x8a90CAb2b38dba80c64b7734e58Ee1dB38B8992e",
        "standard": "erc721",
        "category": "art",
        "floor_price": "2",
        "total_supply": 10000,
        "royalty_percentage": "2.5",
        "royalty_address": "0x...",
        "metadata_uri": "https://api.doodles.app/metadata/",
        "is_verified": True,
    },
    "clonex": {
        "name": "Clone X",
        "symbol": "CLONEX",
        "description": "Clone X is a collection of 20,000 avatars by RTFKT",
        "chain": "ethereum",
        "contract_address": "0x49cF6f5d44E70224e2E23fDcDd2C053F30aDA28B",
        "standard": "erc721",
        "category": "profile_picture",
        "floor_price": "1.5",
        "total_supply": 20000,
        "royalty_percentage": "5",
        "royalty_address": "0x...",
        "metadata_uri": "https://api.clonex.com/metadata/",
        "is_verified": True,
    },
}

DEFAULT_MARKETPLACES = {
    "opensea": {
        "chain": "ethereum",
        "contract_address": "0x0000000000000000000000000000000000000000",
        "fee_percentage": "0.025",
        "enabled": True,
    },
    "blur": {
        "chain": "ethereum",
        "contract_address": "0x0000000000000000000000000000000000000000",
        "fee_percentage": "0.005",
        "enabled": True,
    },
    "looksrare": {
        "chain": "ethereum",
        "contract_address": "0x0000000000000000000000000000000000000000",
        "fee_percentage": "0.02",
        "enabled": True,
    },
}

METADATA_SETTINGS = {
    "base_uri": "https://api.example.com/metadata/",
    "ipfs_gateway": "https://ipfs.io/ipfs/",
    "arweave_gateway": "https://arweave.net/",
    "cache_ttl": 300,
    "max_retries": 3,
}

SECURITY_SETTINGS = {
    "min_confirmations": 12,
    "max_slippage": 0.01,
    "rate_limit": 10,
    "circuit_breaker": {
        "failure_threshold": 5,
        "recovery_timeout": 60,
        "half_open_attempts": 3,
    },
}

MONITORING_SETTINGS = {
    "enabled": True,
    "metrics_interval": 60,
    "alert_thresholds": {
        "floor_price_drop": 0.2,
        "volume_drop": 0.3,
        "rare_items": 0.01,
    },
}


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class NFTConfigManager:
    """
    Gestionnaire centralisé de configuration NFT
    """

    def __init__(
        self,
        config_dir: Optional[str] = None,
        environment: NFTEnvironment = NFTEnvironment.PRODUCTION,
        metrics_collector: Optional[MetricsCollector] = None,
        cache_ttl: int = 300,
    ):
        """
        Initialise le gestionnaire de configuration

        Args:
            config_dir: Répertoire des configurations
            environment: Environnement
            metrics_collector: Collecteur de métriques
            cache_ttl: Durée de vie du cache en secondes
        """
        self.config_dir = config_dir or os.path.join(
            os.path.dirname(__file__), "configs"
        )
        self.environment = environment
        self.metrics = metrics_collector or MetricsCollector()
        self.cache_ttl = cache_ttl

        # Configuration
        self._config: Optional[NFTGlobalConfig] = None
        self._config_cache: Dict[str, Tuple[float, Any]] = {}

        # Création du répertoire
        os.makedirs(self.config_dir, exist_ok=True)

        # Chargement de la configuration
        self._load_config()

        logger.info(f"NFTConfigManager initialisé (environnement: {environment.value})")

    # ============================================================
    # MÉTHODES DE CHARGEMENT
    # ============================================================

    def _load_config(self) -> None:
        """Charge la configuration complète"""
        try:
            # Chargement des configurations
            collections = self._load_collections()
            contracts = self._load_contracts()
            marketplaces = self._load_marketplaces()

            # Chargement des paramètres
            metadata_settings = self._load_metadata_settings()
            security_settings = self._load_security_settings()
            monitoring_settings = self._load_monitoring_settings()

            # Création de la configuration
            self._config = NFTGlobalConfig(
                version="1.0.0",
                environment=self.environment,
                collections=collections,
                contracts=contracts,
                marketplaces=marketplaces,
                metadata_settings=metadata_settings,
                security_settings=security_settings,
                monitoring_settings=monitoring_settings,
                updated_at=datetime.now(),
                metadata={},
            )

            # Validation
            self._validate_config()

            logger.info(
                f"Configuration NFT chargée: "
                f"{len(collections)} collections, "
                f"{len(contracts)} contrats, "
                f"{len(marketplaces)} marketplaces"
            )

        except Exception as e:
            logger.error(f"Erreur de chargement de la configuration: {e}")
            # Utiliser la configuration par défaut
            self._config = self._create_default_config()
            raise ConfigError(f"Erreur de chargement de la configuration: {e}")

    def _load_collections(self) -> Dict[str, NFTCollectionConfig]:
        """Charge les configurations des collections"""
        collections = {}

        # Chargement depuis les fichiers
        collections_dir = os.path.join(self.config_dir, "collections")
        if os.path.exists(collections_dir):
            for file in os.listdir(collections_dir):
                if file.endswith((".yaml", ".yml")):
                    collection_data = self._load_yaml_file(os.path.join(collections_dir, file))
                    if collection_data and "collection_id" in collection_data:
                        collection_id = collection_data["collection_id"]
                        collections[collection_id] = self._create_collection_config(collection_data)

        # Ajout des collections par défaut
        for collection_id, default_data in DEFAULT_COLLECTIONS.items():
            if collection_id not in collections:
                collections[collection_id] = self._create_collection_config({
                    "collection_id": collection_id,
                    **default_data,
                })

        return collections

    def _load_contracts(self) -> Dict[str, NFTContractConfig]:
        """Charge les configurations des contrats"""
        contracts = {}

        # Chargement depuis les fichiers
        contracts_dir = os.path.join(self.config_dir, "contracts")
        if os.path.exists(contracts_dir):
            for file in os.listdir(contracts_dir):
                if file.endswith((".yaml", ".yml")):
                    contract_data = self._load_yaml_file(os.path.join(contracts_dir, file))
                    if contract_data and "address" in contract_data:
                        address = contract_data["address"]
                        contracts[address] = self._create_contract_config(contract_data)

        return contracts

    def _load_marketplaces(self) -> Dict[str, NFTMarketplaceConfig]:
        """Charge les configurations des marketplaces"""
        marketplaces = {}

        # Chargement depuis les fichiers
        marketplaces_dir = os.path.join(self.config_dir, "marketplaces")
        if os.path.exists(marketplaces_dir):
            for file in os.listdir(marketplaces_dir):
                if file.endswith((".yaml", ".yml")):
                    marketplace_data = self._load_yaml_file(os.path.join(marketplaces_dir, file))
                    if marketplace_data and "marketplace" in marketplace_data:
                        name = marketplace_data["marketplace"]
                        marketplaces[name] = self._create_marketplace_config(marketplace_data)

        # Ajout des marketplaces par défaut
        for name, default_data in DEFAULT_MARKETPLACES.items():
            if name not in marketplaces:
                marketplaces[name] = self._create_marketplace_config({
                    "marketplace": name,
                    **default_data,
                })

        return marketplaces

    def _load_metadata_settings(self) -> Dict[str, Any]:
        """Charge les paramètres des métadonnées"""
        metadata_path = os.path.join(self.config_dir, "metadata.yaml")
        if os.path.exists(metadata_path):
            return self._load_yaml_file(metadata_path)
        return METADATA_SETTINGS.copy()

    def _load_security_settings(self) -> Dict[str, Any]:
        """Charge les paramètres de sécurité"""
        security_path = os.path.join(self.config_dir, "security.yaml")
        if os.path.exists(security_path):
            return self._load_yaml_file(security_path)
        return SECURITY_SETTINGS.copy()

    def _load_monitoring_settings(self) -> Dict[str, Any]:
        """Charge les paramètres de monitoring"""
        monitoring_path = os.path.join(self.config_dir, "monitoring.yaml")
        if os.path.exists(monitoring_path):
            return self._load_yaml_file(monitoring_path)
        return MONITORING_SETTINGS.copy()

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

    def _create_collection_config(self, data: Dict[str, Any]) -> NFTCollectionConfig:
        """Crée une configuration de collection"""
        return NFTCollectionConfig(
            collection_id=data.get("collection_id", f"col_{uuid.uuid4().hex[:8]}"),
            name=data.get("name", ""),
            symbol=data.get("symbol", ""),
            description=data.get("description", ""),
            chain=data.get("chain", "ethereum"),
            contract_address=data.get("contract_address", ""),
            standard=NFTStandard(data.get("standard", "erc721")),
            category=data.get("category", "other"),
            floor_price=Decimal(str(data.get("floor_price", "0"))),
            total_supply=data.get("total_supply", 0),
            royalty_percentage=Decimal(str(data.get("royalty_percentage", "0"))),
            royalty_address=data.get("royalty_address", ""),
            metadata_uri=data.get("metadata_uri", ""),
            image=data.get("image"),
            external_url=data.get("external_url"),
            is_verified=data.get("is_verified", False),
            created_at=data.get("created_at", datetime.now()),
            updated_at=data.get("updated_at", datetime.now()),
            metadata=data.get("metadata", {}),
        )

    def _create_contract_config(self, data: Dict[str, Any]) -> NFTContractConfig:
        """Crée une configuration de contrat"""
        return NFTContractConfig(
            address=data.get("address", ""),
            name=data.get("name", ""),
            symbol=data.get("symbol", ""),
            standard=NFTStandard(data.get("standard", "erc721")),
            chain=data.get("chain", "ethereum"),
            total_supply=data.get("total_supply"),
            block_deployed=data.get("block_deployed"),
            metadata=data.get("metadata", {}),
        )

    def _create_marketplace_config(self, data: Dict[str, Any]) -> NFTMarketplaceConfig:
        """Crée une configuration de marketplace"""
        return NFTMarketplaceConfig(
            marketplace=NFTMarketplace(data.get("marketplace", "opensea")),
            chain=data.get("chain", "ethereum"),
            contract_address=data.get("contract_address", ""),
            router_address=data.get("router_address"),
            execution_delegate=data.get("execution_delegate"),
            fee_percentage=Decimal(str(data.get("fee_percentage", "0.025"))),
            enabled=data.get("enabled", True),
            metadata=data.get("metadata", {}),
        )

    def _create_default_config(self) -> NFTGlobalConfig:
        """Crée une configuration par défaut"""
        collections = {}
        for collection_id, default_data in DEFAULT_COLLECTIONS.items():
            collections[collection_id] = self._create_collection_config({
                "collection_id": collection_id,
                **default_data,
            })

        marketplaces = {}
        for name, default_data in DEFAULT_MARKETPLACES.items():
            marketplaces[name] = self._create_marketplace_config({
                "marketplace": name,
                **default_data,
            })

        return NFTGlobalConfig(
            version="1.0.0",
            environment=self.environment,
            collections=collections,
            contracts={},
            marketplaces=marketplaces,
            metadata_settings=METADATA_SETTINGS.copy(),
            security_settings=SECURITY_SETTINGS.copy(),
            monitoring_settings=MONITORING_SETTINGS.copy(),
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

        # Validation des collections
        for collection_id, collection in self._config.collections.items():
            if not collection.contract_address:
                raise ConfigError(f"Adresse manquante pour la collection {collection_id}")

            if collection.total_supply <= 0:
                raise ConfigError(f"Total supply invalide pour {collection_id}")

            if collection.royalty_percentage < 0 or collection.royalty_percentage > 100:
                raise ConfigError(f"Royalty invalide pour {collection_id}")

        # Validation des marketplaces
        for name, marketplace in self._config.marketplaces.items():
            if marketplace.enabled and not marketplace.contract_address:
                raise ConfigError(f"Adresse manquante pour la marketplace {name}")

            if marketplace.fee_percentage < 0 or marketplace.fee_percentage > 100:
                raise ConfigError(f"Fee invalide pour {name}")

        logger.info("Configuration validée avec succès")

    # ============================================================
    # MÉTHODES D'ACCÈS
    # ============================================================

    def get_config(self) -> NFTGlobalConfig:
        """Obtient la configuration complète"""
        if not self._config:
            self._load_config()
        return self._config

    def get_collection(self, collection_id: str) -> Optional[NFTCollectionConfig]:
        """Obtient la configuration d'une collection"""
        return self._config.collections.get(collection_id)

    def get_collection_by_address(self, address: str) -> Optional[NFTCollectionConfig]:
        """Obtient une collection par son adresse"""
        for collection in self._config.collections.values():
            if collection.contract_address.lower() == address.lower():
                return collection
        return None

    def get_contract(self, address: str) -> Optional[NFTContractConfig]:
        """Obtient la configuration d'un contrat"""
        return self._config.contracts.get(address)

    def get_marketplace(self, name: str) -> Optional[NFTMarketplaceConfig]:
        """Obtient la configuration d'une marketplace"""
        return self._config.marketplaces.get(name)

    def get_enabled_marketplaces(self) -> List[NFTMarketplaceConfig]:
        """Obtient les marketplaces activées"""
        return [
            m for m in self._config.marketplaces.values()
            if m.enabled
        ]

    def get_collections_by_chain(self, chain: str) -> List[NFTCollectionConfig]:
        """Obtient les collections par chaîne"""
        return [
            c for c in self._config.collections.values()
            if c.chain == chain
        ]

    def get_collections_by_category(self, category: str) -> List[NFTCollectionConfig]:
        """Obtient les collections par catégorie"""
        return [
            c for c in self._config.collections.values()
            if c.category == category
        ]

    def get_metadata_settings(self) -> Dict[str, Any]:
        """Obtient les paramètres des métadonnées"""
        return self._config.metadata_settings

    def get_security_settings(self) -> Dict[str, Any]:
        """Obtient les paramètres de sécurité"""
        return self._config.security_settings

    def get_monitoring_settings(self) -> Dict[str, Any]:
        """Obtient les paramètres de monitoring"""
        return self._config.monitoring_settings

    # ============================================================
    # MÉTHODES DE MISE À JOUR
    # ============================================================

    def update_config(self, new_config: NFTGlobalConfig) -> None:
        """Met à jour la configuration"""
        self._config = new_config
        self._validate_config()
        self._config.updated_at = datetime.now()
        self._config_cache.clear()
        logger.info("Configuration NFT mise à jour")

    def reload_config(self) -> None:
        """Recharge la configuration"""
        self._load_config()
        logger.info("Configuration NFT rechargée")

    def save_config(self, path: Optional[str] = None) -> None:
        """Sauvegarde la configuration"""
        if not self._config:
            return

        save_path = path or os.path.join(self.config_dir, "nft_config.yaml")

        try:
            with open(save_path, 'w') as f:
                yaml.dump(self._config.to_dict(), f, default_flow_style=False)
            logger.info(f"Configuration NFT sauvegardée: {save_path}")
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
            "collections": len(self._config.collections),
            "contracts": len(self._config.contracts),
            "marketplaces": len(self._config.marketplaces),
            "enabled_marketplaces": len(self.get_enabled_marketplaces()),
            "environment": self.environment.value,
            "version": self._config.version,
            "updated_at": self._config.updated_at.isoformat(),
            "chains_supported": self._get_supported_chains(),
        }

    def _get_supported_chains(self) -> List[str]:
        """Obtient la liste des chaînes supportées"""
        chains = set()
        for collection in self._config.collections.values():
            chains.add(collection.chain)
        for marketplace in self._config.marketplaces.values():
            chains.add(marketplace.chain)
        return sorted(list(chains))

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources NFTConfigManager...")
        self._config_cache.clear()
        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_nft_config_manager(
    config_dir: Optional[str] = None,
    environment: str = "production",
    **kwargs,
) -> NFTConfigManager:
    """
    Crée une instance de NFTConfigManager

    Args:
        config_dir: Répertoire des configurations
        environment: Environnement
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTConfigManager
    """
    env = NFTEnvironment(environment.lower())
    return NFTConfigManager(
        config_dir=config_dir,
        environment=env,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de NFTConfigManager"""
    # Création du gestionnaire
    config_manager = create_nft_config_manager(
        config_dir="./nft_configs",
        environment="production",
    )

    # Obtention de la configuration
    config = config_manager.get_config()
    print(f"Version: {config.version}")
    print(f"Environnement: {config.environment.value}")

    # Obtention d'une collection
    collection = config_manager.get_collection("bored_ape_yacht_club")
    if collection:
        print(f"\nCollection BAYC:")
        print(f"  Name: {collection.name}")
        print(f"  Symbol: {collection.symbol}")
        print(f"  Floor price: {collection.floor_price} ETH")
        print(f"  Total supply: {collection.total_supply}")

    # Obtention des marketplaces activées
    marketplaces = config_manager.get_enabled_marketplaces()
    print(f"\nMarketplaces activées:")
    for m in marketplaces:
        print(f"  {m.marketplace.value} (fee: {m.fee_percentage}%)")

    # Obtention des collections par chaîne
    eth_collections = config_manager.get_collections_by_chain("ethereum")
    print(f"\nCollections sur Ethereum: {len(eth_collections)}")

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
