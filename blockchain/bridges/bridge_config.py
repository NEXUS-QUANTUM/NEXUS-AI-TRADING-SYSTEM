# blockchain/bridges/bridge_config.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module de Configuration des Bridges

Ce module implémente un système complet de gestion de configuration pour les
bridges cross-chain, incluant le chargement, la validation, la mise à jour
dynamique, et la gestion des versions des configurations.

Fonctionnalités principales:
- Chargement des configurations depuis fichiers YAML/JSON
- Validation des configurations
- Mise à jour dynamique des configurations
- Gestion des versions
- Configuration multi-environnements
- Configuration des protocoles
- Configuration des tokens
- Configuration des adresses de contrats
- Configuration des frais
- Configuration des limites
"""

import json
import logging
import os
import yaml
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
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
    from .base_bridge import BaseBridge
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import ConfigError, ValidationError
    from ..core.metrics import MetricsCollector
    from .base_bridge import BaseBridge

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class Environment(Enum):
    """Environnements de déploiement"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class ProtocolStatus(Enum):
    """Statuts des protocoles"""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    MAINTENANCE = "maintenance"
    DISABLED = "disabled"


@dataclass
class ContractConfig:
    """Configuration d'un contrat"""
    address: str
    abi_path: Optional[str] = None
    version: str = "1.0.0"
    block_deployed: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "address": self.address,
            "abi_path": self.abi_path,
            "version": self.version,
            "block_deployed": self.block_deployed,
            "metadata": self.metadata,
        }


@dataclass
class TokenConfig:
    """Configuration d'un token"""
    symbol: str
    name: str
    address: str
    decimals: int
    chain: str
    is_native: bool = False
    is_stable: bool = False
    coingecko_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "symbol": self.symbol,
            "name": self.name,
            "address": self.address,
            "decimals": self.decimals,
            "chain": self.chain,
            "is_native": self.is_native,
            "is_stable": self.is_stable,
            "coingecko_id": self.coingecko_id,
            "metadata": self.metadata,
        }


@dataclass
class ProtocolConfig:
    """Configuration d'un protocole de bridge"""
    protocol: str
    name: str
    status: ProtocolStatus
    chain: str
    type: str  # "lock_and_mint", "burn_and_mint", "swap", etc.
    contracts: Dict[str, ContractConfig]
    supported_tokens: List[str]
    min_amount: Decimal
    max_amount: Decimal
    default_gas_limit: int
    confirmations_required: int
    priority: int
    enabled: bool = True
    fee_percentage: Decimal = Decimal("0.001")
    estimated_time: int = 120  # secondes
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "protocol": self.protocol,
            "name": self.name,
            "status": self.status.value,
            "chain": self.chain,
            "type": self.type,
            "contracts": {k: v.to_dict() for k, v in self.contracts.items()},
            "supported_tokens": self.supported_tokens,
            "min_amount": str(self.min_amount),
            "max_amount": str(self.max_amount),
            "default_gas_limit": self.default_gas_limit,
            "confirmations_required": self.confirmations_required,
            "priority": self.priority,
            "enabled": self.enabled,
            "fee_percentage": str(self.fee_percentage),
            "estimated_time": self.estimated_time,
            "metadata": self.metadata,
        }


@dataclass
class ChainConfig:
    """Configuration d'une blockchain"""
    chain: str
    name: str
    chain_id: int
    rpc_url: str
    ws_url: Optional[str] = None
    explorer_url: Optional[str] = None
    native_currency: str
    gas_limit_multiplier: float = 1.0
    max_gas_price: Optional[int] = None
    min_gas_price: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "chain": self.chain,
            "name": self.name,
            "chain_id": self.chain_id,
            "rpc_url": self.rpc_url,
            "ws_url": self.ws_url,
            "explorer_url": self.explorer_url,
            "native_currency": self.native_currency,
            "gas_limit_multiplier": self.gas_limit_multiplier,
            "max_gas_price": self.max_gas_price,
            "min_gas_price": self.min_gas_price,
            "metadata": self.metadata,
        }


@dataclass
class BridgeConfig:
    """Configuration principale des bridges"""
    version: str
    environment: Environment
    chains: Dict[str, ChainConfig]
    protocols: Dict[str, ProtocolConfig]
    tokens: Dict[str, TokenConfig]
    global_settings: Dict[str, Any]
    security: Dict[str, Any]
    monitoring: Dict[str, Any]
    fees: Dict[str, Any]
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "version": self.version,
            "environment": self.environment.value,
            "chains": {k: v.to_dict() for k, v in self.chains.items()},
            "protocols": {k: v.to_dict() for k, v in self.protocols.items()},
            "tokens": {k: v.to_dict() for k, v in self.tokens.items()},
            "global_settings": self.global_settings,
            "security": self.security,
            "monitoring": self.monitoring,
            "fees": self.fees,
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class BridgeConfigManager:
    """
    Gestionnaire de configuration des bridges
    """

    # Configuration par défaut
    DEFAULT_CONFIG = {
        "version": "1.0.0",
        "environment": "production",
        "global_settings": {
            "max_transactions_per_second": 10,
            "max_pending_transactions": 100,
            "retry_attempts": 3,
            "retry_delay": 5,
            "timeout": 300,
            "gas_multiplier": 1.1,
        },
        "security": {
            "min_confirmations": 12,
            "max_slippage": 0.01,
            "blacklist_check": True,
            "whitelist_check": False,
            "rate_limit": 10,
            "circuit_breaker": {
                "failure_threshold": 5,
                "recovery_timeout": 60,
                "half_open_attempts": 3,
            },
        },
        "monitoring": {
            "enabled": True,
            "metrics_interval": 60,
            "alert_thresholds": {
                "success_rate": 0.95,
                "response_time": 10,
                "pending_transactions": 50,
            },
        },
        "fees": {
            "default_percentage": 0.001,
            "min_fee": 0.01,
            "max_fee": 1000,
            "gas_price_multiplier": 1.0,
        },
    }

    def __init__(
        self,
        config_dir: Optional[str] = None,
        environment: Environment = Environment.PRODUCTION,
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
        self._config: Optional[BridgeConfig] = None
        self._config_cache: Dict[str, Tuple[float, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Configuration des chemins
        self._config_paths = {
            "chains": os.path.join(self.config_dir, "chains"),
            "protocols": os.path.join(self.config_dir, "protocols"),
            "tokens": os.path.join(self.config_dir, "tokens"),
            "global": os.path.join(self.config_dir, "global.yaml"),
            "security": os.path.join(self.config_dir, "security.yaml"),
            "monitoring": os.path.join(self.config_dir, "monitoring.yaml"),
            "fees": os.path.join(self.config_dir, "fees.yaml"),
        }

        # Chargement initial
        self._load_config()

        logger.info(f"BridgeConfigManager initialisé (environnement: {environment.value})")

    # ============================================================
    # MÉTHODES DE CHARGEMENT
    # ============================================================

    def _load_config(self) -> None:
        """Charge la configuration complète"""
        try:
            # Création du répertoire si inexistant
            os.makedirs(self.config_dir, exist_ok=True)

            # Chargement des configurations
            chains = self._load_chains()
            protocols = self._load_protocols()
            tokens = self._load_tokens()

            # Chargement des configurations globales
            global_settings = self._load_global_settings()
            security = self._load_security_config()
            monitoring = self._load_monitoring_config()
            fees = self._load_fees_config()

            # Création de la configuration
            self._config = BridgeConfig(
                version=self.DEFAULT_CONFIG["version"],
                environment=self.environment,
                chains=chains,
                protocols=protocols,
                tokens=tokens,
                global_settings=global_settings,
                security=security,
                monitoring=monitoring,
                fees=fees,
                updated_at=datetime.now(),
                metadata={},
            )

            # Validation
            self._validate_config()

            logger.info(
                f"Configuration chargée: "
                f"{len(chains)} chaînes, "
                f"{len(protocols)} protocoles, "
                f"{len(tokens)} tokens"
            )

        except Exception as e:
            logger.error(f"Erreur de chargement de la configuration: {e}")
            # Utiliser la configuration par défaut
            self._config = self._create_default_config()
            raise ConfigError(f"Erreur de chargement de la configuration: {e}")

    def _load_chains(self) -> Dict[str, ChainConfig]:
        """Charge les configurations des chaînes"""
        chains = {}
        chains_dir = self._config_paths["chains"]

        if os.path.exists(chains_dir):
            for file in os.listdir(chains_dir):
                if file.endswith((".yaml", ".yml")):
                    chain_config = self._load_yaml_file(os.path.join(chains_dir, file))
                    if chain_config:
                        chain = chain_config.get("chain")
                        if chain:
                            chains[chain] = ChainConfig(
                                chain=chain,
                                name=chain_config.get("name", chain),
                                chain_id=chain_config.get("chain_id", 0),
                                rpc_url=chain_config.get("rpc_url", ""),
                                ws_url=chain_config.get("ws_url"),
                                explorer_url=chain_config.get("explorer_url"),
                                native_currency=chain_config.get("native_currency", "ETH"),
                                gas_limit_multiplier=chain_config.get("gas_limit_multiplier", 1.0),
                                max_gas_price=chain_config.get("max_gas_price"),
                                min_gas_price=chain_config.get("min_gas_price"),
                                metadata=chain_config.get("metadata", {}),
                            )

        # Chaînes par défaut
        default_chains = {
            "ethereum": ChainConfig(
                chain="ethereum",
                name="Ethereum",
                chain_id=1,
                rpc_url="https://mainnet.infura.io/v3/YOUR_KEY",
                explorer_url="https://etherscan.io",
                native_currency="ETH",
            ),
            "polygon": ChainConfig(
                chain="polygon",
                name="Polygon",
                chain_id=137,
                rpc_url="https://polygon-rpc.com",
                explorer_url="https://polygonscan.com",
                native_currency="MATIC",
            ),
            "arbitrum": ChainConfig(
                chain="arbitrum",
                name="Arbitrum",
                chain_id=42161,
                rpc_url="https://arb1.arbitrum.io/rpc",
                explorer_url="https://arbiscan.io",
                native_currency="ETH",
            ),
            "optimism": ChainConfig(
                chain="optimism",
                name="Optimism",
                chain_id=10,
                rpc_url="https://mainnet.optimism.io",
                explorer_url="https://optimistic.etherscan.io",
                native_currency="ETH",
            ),
            "base": ChainConfig(
                chain="base",
                name="Base",
                chain_id=8453,
                rpc_url="https://mainnet.base.org",
                explorer_url="https://basescan.org",
                native_currency="ETH",
            ),
            "solana": ChainConfig(
                chain="solana",
                name="Solana",
                chain_id=101,
                rpc_url="https://api.mainnet-beta.solana.com",
                explorer_url="https://solscan.io",
                native_currency="SOL",
            ),
            "bsc": ChainConfig(
                chain="bsc",
                name="Binance Smart Chain",
                chain_id=56,
                rpc_url="https://bsc-dataseed.binance.org",
                explorer_url="https://bscscan.com",
                native_currency="BNB",
            ),
            "avalanche": ChainConfig(
                chain="avalanche",
                name="Avalanche",
                chain_id=43114,
                rpc_url="https://api.avax.network/ext/bc/C/rpc",
                explorer_url="https://snowtrace.io",
                native_currency="AVAX",
            ),
        }

        # Fusion avec les chaînes chargées
        for chain_id, default_chain in default_chains.items():
            if chain_id not in chains:
                chains[chain_id] = default_chain

        return chains

    def _load_protocols(self) -> Dict[str, ProtocolConfig]:
        """Charge les configurations des protocoles"""
        protocols = {}
        protocols_dir = self._config_paths["protocols"]

        if os.path.exists(protocols_dir):
            for file in os.listdir(protocols_dir):
                if file.endswith((".yaml", ".yml")):
                    protocol_config = self._load_yaml_file(os.path.join(protocols_dir, file))
                    if protocol_config:
                        protocol = protocol_config.get("protocol")
                        if protocol:
                            protocols[protocol] = self._create_protocol_config(protocol_config)

        # Protocoles par défaut
        default_protocols = self._get_default_protocols()

        for protocol_id, default_config in default_protocols.items():
            if protocol_id not in protocols:
                protocols[protocol_id] = default_config

        return protocols

    def _load_tokens(self) -> Dict[str, TokenConfig]:
        """Charge les configurations des tokens"""
        tokens = {}
        tokens_dir = self._config_paths["tokens"]

        if os.path.exists(tokens_dir):
            for file in os.listdir(tokens_dir):
                if file.endswith((".yaml", ".yml")):
                    token_config = self._load_yaml_file(os.path.join(tokens_dir, file))
                    if token_config:
                        symbol = token_config.get("symbol")
                        if symbol:
                            tokens[symbol] = TokenConfig(
                                symbol=symbol,
                                name=token_config.get("name", symbol),
                                address=token_config.get("address", ""),
                                decimals=token_config.get("decimals", 18),
                                chain=token_config.get("chain", "ethereum"),
                                is_native=token_config.get("is_native", False),
                                is_stable=token_config.get("is_stable", False),
                                coingecko_id=token_config.get("coingecko_id"),
                                metadata=token_config.get("metadata", {}),
                            )

        # Tokens par défaut
        default_tokens = self._get_default_tokens()

        for symbol, default_config in default_tokens.items():
            if symbol not in tokens:
                tokens[symbol] = default_config

        return tokens

    def _load_global_settings(self) -> Dict[str, Any]:
        """Charge les paramètres globaux"""
        global_path = self._config_paths["global"]
        settings = self.DEFAULT_CONFIG["global_settings"].copy()

        if os.path.exists(global_path):
            loaded = self._load_yaml_file(global_path)
            if loaded:
                settings.update(loaded)

        return settings

    def _load_security_config(self) -> Dict[str, Any]:
        """Charge la configuration de sécurité"""
        security_path = self._config_paths["security"]
        config = self.DEFAULT_CONFIG["security"].copy()

        if os.path.exists(security_path):
            loaded = self._load_yaml_file(security_path)
            if loaded:
                config.update(loaded)

        return config

    def _load_monitoring_config(self) -> Dict[str, Any]:
        """Charge la configuration de monitoring"""
        monitoring_path = self._config_paths["monitoring"]
        config = self.DEFAULT_CONFIG["monitoring"].copy()

        if os.path.exists(monitoring_path):
            loaded = self._load_yaml_file(monitoring_path)
            if loaded:
                config.update(loaded)

        return config

    def _load_fees_config(self) -> Dict[str, Any]:
        """Charge la configuration des frais"""
        fees_path = self._config_paths["fees"]
        config = self.DEFAULT_CONFIG["fees"].copy()

        if os.path.exists(fees_path):
            loaded = self._load_yaml_file(fees_path)
            if loaded:
                config.update(loaded)

        return config

    def _load_yaml_file(self, path: str) -> Dict[str, Any]:
        """Charge un fichier YAML"""
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Erreur de chargement de {path}: {e}")
            return {}

    def _load_json_file(self, path: str) -> Dict[str, Any]:
        """Charge un fichier JSON"""
        try:
            with open(path, 'r') as f:
                return json.load(f) or {}
        except Exception as e:
            logger.warning(f"Erreur de chargement de {path}: {e}")
            return {}

    # ============================================================
    # MÉTHODES DE CRÉATION DE CONFIGURATION
    # ============================================================

    def _create_protocol_config(self, data: Dict[str, Any]) -> ProtocolConfig:
        """Crée une configuration de protocole"""
        contracts = {}
        for name, contract_data in data.get("contracts", {}).items():
            contracts[name] = ContractConfig(
                address=contract_data.get("address", ""),
                abi_path=contract_data.get("abi_path"),
                version=contract_data.get("version", "1.0.0"),
                block_deployed=contract_data.get("block_deployed"),
                metadata=contract_data.get("metadata", {}),
            )

        return ProtocolConfig(
            protocol=data.get("protocol", ""),
            name=data.get("name", ""),
            status=ProtocolStatus(data.get("status", "active")),
            chain=data.get("chain", "ethereum"),
            type=data.get("type", "lock_and_mint"),
            contracts=contracts,
            supported_tokens=data.get("supported_tokens", []),
            min_amount=Decimal(str(data.get("min_amount", "0.001"))),
            max_amount=Decimal(str(data.get("max_amount", "1000000"))),
            default_gas_limit=data.get("default_gas_limit", 200000),
            confirmations_required=data.get("confirmations_required", 12),
            priority=data.get("priority", 0),
            enabled=data.get("enabled", True),
            fee_percentage=Decimal(str(data.get("fee_percentage", "0.001"))),
            estimated_time=data.get("estimated_time", 120),
            metadata=data.get("metadata", {}),
        )

    def _get_default_protocols(self) -> Dict[str, ProtocolConfig]:
        """Obtient les protocoles par défaut"""
        return {
            "wormhole": ProtocolConfig(
                protocol="wormhole",
                name="Wormhole",
                status=ProtocolStatus.ACTIVE,
                chain="ethereum",
                type="lock_and_mint",
                contracts={
                    "core": ContractConfig(
                        address="0x98f3c9e6E3fAce36bAAd05FE09d375Ef1464288B",
                        version="2.0.0",
                    ),
                    "token": ContractConfig(
                        address="0x3ee18B2214AFF97000D974cf647E7C347E8fa585",
                        version="2.0.0",
                    ),
                },
                supported_tokens=["USDC", "USDT", "ETH", "WBTC", "DAI"],
                min_amount=Decimal("0.001"),
                max_amount=Decimal("200000"),
                default_gas_limit=250000,
                confirmations_required=12,
                priority=10,
                fee_percentage=Decimal("0.0003"),
                estimated_time=90,
            ),
            "layerzero": ProtocolConfig(
                protocol="layerzero",
                name="LayerZero",
                status=ProtocolStatus.ACTIVE,
                chain="ethereum",
                type="lock_and_mint",
                contracts={
                    "endpoint": ContractConfig(
                        address="0x66A71Dcef29A0fFBDBE3c6a460a3B5BC225Cd675",
                        version="2.0.0",
                    ),
                },
                supported_tokens=["USDC", "USDT", "ETH", "DAI"],
                min_amount=Decimal("0.001"),
                max_amount=Decimal("100000"),
                default_gas_limit=300000,
                confirmations_required=12,
                priority=20,
                fee_percentage=Decimal("0.0005"),
                estimated_time=120,
            ),
            "cctp": ProtocolConfig(
                protocol="cctp",
                name="Circle CCTP",
                status=ProtocolStatus.ACTIVE,
                chain="ethereum",
                type="cctp",
                contracts={
                    "token_messenger": ContractConfig(
                        address="0x354222B555b952382a5762d4c342E7FBeA0B5b3C",
                        version="1.0.0",
                    ),
                },
                supported_tokens=["USDC"],
                min_amount=Decimal("1"),
                max_amount=Decimal("100000"),
                default_gas_limit=200000,
                confirmations_required=12,
                priority=30,
                fee_percentage=Decimal("0.0001"),
                estimated_time=60,
            ),
            "optimism_native": ProtocolConfig(
                protocol="optimism_native",
                name="Optimism Native Bridge",
                status=ProtocolStatus.ACTIVE,
                chain="optimism",
                type="native",
                contracts={
                    "l1_bridge": ContractConfig(
                        address="0x99C9fc46f92E8a1c0deC1b1747d010903E884bE1",
                        version="1.0.0",
                    ),
                },
                supported_tokens=["ETH", "USDC", "USDT", "DAI"],
                min_amount=Decimal("0.001"),
                max_amount=Decimal("100000"),
                default_gas_limit=300000,
                confirmations_required=12,
                priority=40,
                fee_percentage=Decimal("0.0002"),
                estimated_time=120,
            ),
            "polygon_pos": ProtocolConfig(
                protocol="polygon_pos",
                name="Polygon PoS Bridge",
                status=ProtocolStatus.ACTIVE,
                chain="polygon",
                type="lock_and_mint",
                contracts={
                    "root_chain": ContractConfig(
                        address="0xA0c68C638235ee32657e8f720a23ceC1bFc77C77",
                        version="1.0.0",
                    ),
                },
                supported_tokens=["MATIC", "USDC", "USDT", "ETH", "DAI"],
                min_amount=Decimal("0.001"),
                max_amount=Decimal("100000"),
                default_gas_limit=300000,
                confirmations_required=12,
                priority=50,
                fee_percentage=Decimal("0.0002"),
                estimated_time=120,
            ),
            "solana_wormhole": ProtocolConfig(
                protocol="solana_wormhole",
                name="Solana Wormhole",
                status=ProtocolStatus.ACTIVE,
                chain="solana",
                type="lock_and_mint",
                contracts={
                    "core_bridge": ContractConfig(
                        address="worm2ZoG2kUd4vFXhvjh93UUH596ayRfgQ2MgjNMTth",
                        version="2.0.0",
                    ),
                },
                supported_tokens=["SOL", "USDC", "USDT", "WETH", "WBTC"],
                min_amount=Decimal("0.001"),
                max_amount=Decimal("100000"),
                default_gas_limit=200000,
                confirmations_required=32,
                priority=60,
                fee_percentage=Decimal("0.0003"),
                estimated_time=30,
            ),
        }

    def _get_default_tokens(self) -> Dict[str, TokenConfig]:
        """Obtient les tokens par défaut"""
        return {
            "ETH": TokenConfig(
                symbol="ETH",
                name="Ethereum",
                address="0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                decimals=18,
                chain="ethereum",
                is_native=True,
                coingecko_id="ethereum",
            ),
            "MATIC": TokenConfig(
                symbol="MATIC",
                name="Polygon",
                address="0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0",
                decimals=18,
                chain="polygon",
                is_native=True,
                coingecko_id="polygon",
            ),
            "USDC": TokenConfig(
                symbol="USDC",
                name="USD Coin",
                address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                decimals=6,
                chain="ethereum",
                is_stable=True,
                coingecko_id="usd-coin",
            ),
            "USDT": TokenConfig(
                symbol="USDT",
                name="Tether USD",
                address="0xdAC17F958D2ee523a2206206994597C13D831ec7",
                decimals=6,
                chain="ethereum",
                is_stable=True,
                coingecko_id="tether",
            ),
            "DAI": TokenConfig(
                symbol="DAI",
                name="Dai",
                address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
                decimals=18,
                chain="ethereum",
                is_stable=True,
                coingecko_id="dai",
            ),
            "WBTC": TokenConfig(
                symbol="WBTC",
                name="Wrapped Bitcoin",
                address="0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                decimals=8,
                chain="ethereum",
                coingecko_id="wrapped-bitcoin",
            ),
            "SOL": TokenConfig(
                symbol="SOL",
                name="Solana",
                address="So11111111111111111111111111111111111111112",
                decimals=9,
                chain="solana",
                is_native=True,
                coingecko_id="solana",
            ),
            "BNB": TokenConfig(
                symbol="BNB",
                name="BNB",
                address="0x0000000000000000000000000000000000000000",
                decimals=18,
                chain="bsc",
                is_native=True,
                coingecko_id="bnb",
            ),
            "AVAX": TokenConfig(
                symbol="AVAX",
                name="Avalanche",
                address="0x0000000000000000000000000000000000000000",
                decimals=18,
                chain="avalanche",
                is_native=True,
                coingecko_id="avalanche-2",
            ),
        }

    def _create_default_config(self) -> BridgeConfig:
        """Crée une configuration par défaut"""
        chains = self._load_chains()
        protocols = self._get_default_protocols()
        tokens = self._get_default_tokens()

        return BridgeConfig(
            version=self.DEFAULT_CONFIG["version"],
            environment=self.environment,
            chains=chains,
            protocols=protocols,
            tokens=tokens,
            global_settings=self.DEFAULT_CONFIG["global_settings"],
            security=self.DEFAULT_CONFIG["security"],
            monitoring=self.DEFAULT_CONFIG["monitoring"],
            fees=self.DEFAULT_CONFIG["fees"],
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

        # Validation des chaînes
        for chain_id, chain in self._config.chains.items():
            if not chain.rpc_url:
                raise ConfigError(f"RPC URL manquant pour {chain_id}")

        # Validation des protocoles
        for protocol_id, protocol in self._config.protocols.items():
            if protocol.enabled and not protocol.contracts:
                raise ConfigError(f"Contrats manquants pour {protocol_id}")

        # Validation des tokens
        for symbol, token in self._config.tokens.items():
            if not token.address:
                raise ConfigError(f"Adresse manquante pour {symbol}")

        # Validation des montants
        for protocol in self._config.protocols.values():
            if protocol.min_amount >= protocol.max_amount:
                raise ConfigError(
                    f"Montant minimum > maximum pour {protocol.protocol}"
                )

        logger.info("Configuration validée avec succès")

    # ============================================================
    # MÉTHODES PUBLIQUES
    # ============================================================

    def get_config(self) -> BridgeConfig:
        """
        Obtient la configuration complète

        Returns:
            Configuration des bridges
        """
        if not self._config:
            self._load_config()
        return self._config

    def get_chain_config(self, chain: str) -> Optional[ChainConfig]:
        """
        Obtient la configuration d'une chaîne

        Args:
            chain: Nom de la chaîne

        Returns:
            Configuration de la chaîne
        """
        return self._config.chains.get(chain)

    def get_protocol_config(self, protocol: str) -> Optional[ProtocolConfig]:
        """
        Obtient la configuration d'un protocole

        Args:
            protocol: Nom du protocole

        Returns:
            Configuration du protocole
        """
        return self._config.protocols.get(protocol)

    def get_token_config(self, symbol: str) -> Optional[TokenConfig]:
        """
        Obtient la configuration d'un token

        Args:
            symbol: Symbole du token

        Returns:
            Configuration du token
        """
        return self._config.tokens.get(symbol)

    def get_token_by_address(
        self,
        address: str,
        chain: Optional[str] = None,
    ) -> Optional[TokenConfig]:
        """
        Obtient un token par son adresse

        Args:
            address: Adresse du token
            chain: Chaîne (optionnel)

        Returns:
            Configuration du token
        """
        for token in self._config.tokens.values():
            if token.address.lower() == address.lower():
                if chain is None or token.chain == chain:
                    return token
        return None

    def get_protocols_for_chain(self, chain: str) -> List[ProtocolConfig]:
        """
        Obtient les protocoles pour une chaîne

        Args:
            chain: Nom de la chaîne

        Returns:
            Liste des protocoles
        """
        return [
            protocol for protocol in self._config.protocols.values()
            if protocol.chain == chain and protocol.enabled
        ]

    def get_protocols_for_token(
        self,
        token: str,
        chain: Optional[str] = None,
    ) -> List[ProtocolConfig]:
        """
        Obtient les protocoles supportant un token

        Args:
            token: Symbole du token
            chain: Chaîne (optionnel)

        Returns:
            Liste des protocoles
        """
        protocols = []
        for protocol in self._config.protocols.values():
            if token in protocol.supported_tokens:
                if chain is None or protocol.chain == chain:
                    protocols.append(protocol)
        return protocols

    @lru_cache(maxsize=128)
    def get_contract_address(
        self,
        protocol: str,
        contract_name: str,
    ) -> Optional[str]:
        """
        Obtient l'adresse d'un contrat

        Args:
            protocol: Nom du protocole
            contract_name: Nom du contrat

        Returns:
            Adresse du contrat
        """
        protocol_config = self.get_protocol_config(protocol)
        if protocol_config and contract_name in protocol_config.contracts:
            return protocol_config.contracts[contract_name].address
        return None

    @lru_cache(maxsize=128)
    def get_chain_id(self, chain: str) -> Optional[int]:
        """
        Obtient l'ID d'une chaîne

        Args:
            chain: Nom de la chaîne

        Returns:
            ID de la chaîne
        """
        chain_config = self.get_chain_config(chain)
        return chain_config.chain_id if chain_config else None

    def update_config(self, new_config: BridgeConfig) -> None:
        """
        Met à jour la configuration

        Args:
            new_config: Nouvelle configuration
        """
        self._config = new_config
        self._validate_config()
        self._config.updated_at = datetime.now()
        self._config_cache.clear()
        logger.info("Configuration mise à jour")

    def reload_config(self) -> None:
        """Recharge la configuration"""
        self._load_config()
        logger.info("Configuration rechargée")

    def get_environment(self) -> Environment:
        """
        Obtient l'environnement actuel

        Returns:
            Environnement
        """
        return self.environment

    def to_dict(self) -> Dict[str, Any]:
        """
        Convertit la configuration en dictionnaire

        Returns:
            Dictionnaire de configuration
        """
        return self._config.to_dict() if self._config else {}

    def to_json(self, indent: int = 2) -> str:
        """
        Convertit la configuration en JSON

        Args:
            indent: Indentation

        Returns:
            Configuration en JSON
        """
        return json.dumps(self.to_dict(), indent=indent)

    def save_config(self, path: Optional[str] = None) -> None:
        """
        Sauvegarde la configuration

        Args:
            path: Chemin de sauvegarde (optionnel)
        """
        if not self._config:
            return

        save_path = path or os.path.join(self.config_dir, "bridge_config.yaml")

        try:
            with open(save_path, 'w') as f:
                yaml.dump(self.to_dict(), f, default_flow_style=False)
            logger.info(f"Configuration sauvegardée: {save_path}")
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

        active_protocols = sum(1 for p in self._config.protocols.values() if p.enabled)
        active_tokens = sum(1 for t in self._config.tokens.values() if t.address)

        return {
            "chains": len(self._config.chains),
            "protocols": len(self._config.protocols),
            "active_protocols": active_protocols,
            "tokens": len(self._config.tokens),
            "active_tokens": active_tokens,
            "environment": self.environment.value,
            "version": self._config.version,
            "updated_at": self._config.updated_at.isoformat(),
        }

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources BridgeConfigManager...")
        self._config_cache.clear()
        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_bridge_config_manager(
    config_dir: Optional[str] = None,
    environment: str = "production",
    **kwargs,
) -> BridgeConfigManager:
    """
    Crée une instance de BridgeConfigManager

    Args:
        config_dir: Répertoire des configurations
        environment: Environnement
        **kwargs: Arguments additionnels

    Returns:
        Instance de BridgeConfigManager
    """
    env = Environment(environment.lower())
    return BridgeConfigManager(
        config_dir=config_dir,
        environment=env,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation du BridgeConfigManager"""
    # Création du gestionnaire de configuration
    config_manager = create_bridge_config_manager(
        config_dir="./configs",
        environment="production",
    )

    # Obtention de la configuration complète
    config = config_manager.get_config()
    print(f"Configuration version: {config.version}")
    print(f"Environnement: {config.environment.value}")

    # Obtention d'une chaîne
    eth_config = config_manager.get_chain_config("ethereum")
    print(f"Ethereum RPC: {eth_config.rpc_url}")

    # Obtention d'un protocole
    wormhole_config = config_manager.get_protocol_config("wormhole")
    print(f"Wormhole: {wormhole_config.name} (min: {wormhole_config.min_amount})")

    # Obtention d'un token
    usdc_config = config_manager.get_token_config("USDC")
    print(f"USDC: {usdc_config.name} ({usdc_config.decimals} decimals)")

    # Obtention des protocoles pour une chaîne
    protocols = config_manager.get_protocols_for_chain("ethereum")
    print(f"Protocoles sur Ethereum: {len(protocols)}")

    # Obtention des protocoles pour un token
    token_protocols = config_manager.get_protocols_for_token("USDC")
    print(f"Protocoles supportant USDC: {len(token_protocols)}")

    # Sauvegarde de la configuration
    config_manager.save_config()

    # Statistiques
    stats = config_manager.get_statistics()
    print(f"Statistiques: {stats}")

    # Nettoyage
    await config_manager.cleanup()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main_example())
