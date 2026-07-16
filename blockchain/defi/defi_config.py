# blockchain/defi/defi_config.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module DeFi Config - Configuration Centralisée des Protocoles DeFi

Ce module gère la configuration centralisée de tous les protocoles DeFi,
incluant les adresses de contrats, les paramètres de protocole, les mappings
de tokens, et les configurations de sécurité.

Fonctionnalités principales:
- Configuration centralisée des protocoles DeFi
- Gestion des adresses de contrats
- Mappings des tokens par chaîne
- Paramètres de protocole
- Configuration des risques
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
except ImportError:
    from logging import getLogger as get_logger
    from ..core.exceptions import ConfigError, ValidationError
    from ..core.metrics import MetricsCollector

# Configuration du logger
logger = get_logger(__name__)


# ============================================================
# ENUMS ET TYPES
# ============================================================

class DeFiProtocol(Enum):
    """Protocoles DeFi supportés"""
    AAVE_V3 = "aave_v3"
    AAVE_V2 = "aave_v2"
    COMPOUND_V3 = "compound_v3"
    COMPOUND_V2 = "compound_v2"
    CURVE = "curve"
    UNISWAP_V3 = "uniswap_v3"
    UNISWAP_V2 = "uniswap_v2"
    BALANCER = "balancer"
    LIDO = "lido"
    ROCKET_POOL = "rocket_pool"
    MAKER = "maker"
    SPARK = "spark"
    MORPHO = "morpho"


class DeFiChain(Enum):
    """Chaînes supportées"""
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    AVALANCHE = "avalanche"
    BASE = "base"
    BSC = "bsc"
    GNOSIS = "gnosis"


class Environment(Enum):
    """Environnements"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class RiskLevel(Enum):
    """Niveaux de risque"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


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
    is_wrapped: bool = False
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
            "is_wrapped": self.is_wrapped,
            "coingecko_id": self.coingecko_id,
            "metadata": self.metadata,
        }


@dataclass
class ProtocolConfig:
    """Configuration d'un protocole DeFi"""
    protocol: DeFiProtocol
    name: str
    chains: List[str]
    risk_level: RiskLevel
    contracts: Dict[str, ContractConfig]
    supported_tokens: List[str]
    min_amount: Decimal
    max_amount: Decimal
    max_slippage: Decimal
    gas_multiplier: float
    enabled: bool = True
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "protocol": self.protocol.value,
            "name": self.name,
            "chains": self.chains,
            "risk_level": self.risk_level.value,
            "contracts": {k: v.to_dict() for k, v in self.contracts.items()},
            "supported_tokens": self.supported_tokens,
            "min_amount": str(self.min_amount),
            "max_amount": str(self.max_amount),
            "max_slippage": str(self.max_slippage),
            "gas_multiplier": self.gas_multiplier,
            "enabled": self.enabled,
            "priority": self.priority,
            "metadata": self.metadata,
        }


@dataclass
class DeFiGlobalConfig:
    """Configuration globale DeFi"""
    version: str
    environment: Environment
    protocols: Dict[str, ProtocolConfig]
    tokens: Dict[str, TokenConfig]
    risk_parameters: Dict[str, Any]
    gas_settings: Dict[str, Any]
    monitoring: Dict[str, Any]
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire"""
        return {
            "version": self.version,
            "environment": self.environment.value,
            "protocols": {k: v.to_dict() for k, v in self.protocols.items()},
            "tokens": {k: v.to_dict() for k, v in self.tokens.items()},
            "risk_parameters": self.risk_parameters,
            "gas_settings": self.gas_settings,
            "monitoring": self.monitoring,
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


# ============================================================
# CONFIGURATIONS PAR DÉFAUT
# ============================================================

DEFAULT_PROTOCOLS = {
    "aave_v3": {
        "name": "Aave V3",
        "risk_level": "low",
        "supported_tokens": ["USDC", "USDT", "DAI", "WETH", "WBTC", "MATIC", "AVAX"],
        "min_amount": "0.001",
        "max_amount": "1000000",
        "max_slippage": "0.01",
        "gas_multiplier": 1.1,
    },
    "compound_v3": {
        "name": "Compound V3",
        "risk_level": "low",
        "supported_tokens": ["USDC", "USDT", "WETH", "WBTC"],
        "min_amount": "0.01",
        "max_amount": "500000",
        "max_slippage": "0.01",
        "gas_multiplier": 1.0,
    },
    "curve": {
        "name": "Curve",
        "risk_level": "medium",
        "supported_tokens": ["USDC", "USDT", "DAI", "WETH", "stETH"],
        "min_amount": "0.001",
        "max_amount": "1000000",
        "max_slippage": "0.015",
        "gas_multiplier": 1.2,
    },
    "uniswap_v3": {
        "name": "Uniswap V3",
        "risk_level": "medium",
        "supported_tokens": ["USDC", "USDT", "DAI", "WETH", "WBTC", "UNI"],
        "min_amount": "0.001",
        "max_amount": "1000000",
        "max_slippage": "0.01",
        "gas_multiplier": 1.0,
    },
}

DEFAULT_TOKENS = {
    "USDC": {
        "name": "USD Coin",
        "decimals": 6,
        "is_stable": True,
        "coingecko_id": "usd-coin",
    },
    "USDT": {
        "name": "Tether USD",
        "decimals": 6,
        "is_stable": True,
        "coingecko_id": "tether",
    },
    "DAI": {
        "name": "Dai",
        "decimals": 18,
        "is_stable": True,
        "coingecko_id": "dai",
    },
    "WETH": {
        "name": "Wrapped Ether",
        "decimals": 18,
        "is_wrapped": True,
        "coingecko_id": "ethereum",
    },
    "WBTC": {
        "name": "Wrapped Bitcoin",
        "decimals": 8,
        "is_wrapped": True,
        "coingecko_id": "wrapped-bitcoin",
    },
    "MATIC": {
        "name": "Polygon",
        "decimals": 18,
        "is_native": True,
        "coingecko_id": "polygon",
    },
    "AVAX": {
        "name": "Avalanche",
        "decimals": 18,
        "is_native": True,
        "coingecko_id": "avalanche-2",
    },
    "UNI": {
        "name": "Uniswap",
        "decimals": 18,
        "coingecko_id": "uniswap",
    },
}

CONTRACT_ADDRESSES = {
    "aave_v3": {
        "ethereum": {
            "pool": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
            "pool_addresses_provider": "0x2f39d218133AFaB8F2B819B1066c7E434Ad94E9e",
        },
        "polygon": {
            "pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
            "pool_addresses_provider": "0xa97684ead0e402dC232d5A977023DF7Edb90cA1A",
        },
        "arbitrum": {
            "pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
            "pool_addresses_provider": "0xa97684ead0e402dC232d5A977023DF7Edb90cA1A",
        },
        "optimism": {
            "pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
            "pool_addresses_provider": "0xa97684ead0e402dC232d5A977023DF7Edb90cA1A",
        },
        "avalanche": {
            "pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
            "pool_addresses_provider": "0xa97684ead0e402dC232d5A977023DF7Edb90cA1A",
        },
        "base": {
            "pool": "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5",
            "pool_addresses_provider": "0xe20fCBdBfFC4Dd1382e8E2c6f5A51c289C81b1B3",
        },
    },
    "compound_v3": {
        "ethereum": {
            "comet_usdc": "0xc3d688B66703497DAA19211EEdff47f25384cdc3",
        },
        "polygon": {
            "comet_usdc": "0xE0D5Ded89342e0BC151eE63D6603139dfCFaDB0c",
        },
        "arbitrum": {
            "comet_usdc": "0xA5EDBDD9646f8dFF606d7448e414884C7d905dA1",
        },
        "base": {
            "comet_usdc": "0xb125E6687d4313864e53df431d5425969c15Eb2F",
        },
    },
    "curve": {
        "ethereum": {
            "3pool": "0xbEbc44782C7dB0a1A60Cb6fe97d0b483032FF1C7",
            "factory": "0x0959158b6040D32d04c301A72CBFD6b39E21c9AE",
        },
        "polygon": {
            "3pool": "0xE7a24EF0C5e95Ffb0f6684b813A78F2a3AD6D24C",
            "factory": "0x0959158b6040D32d04c301A72CBFD6b39E21c9AE",
        },
    },
}

# Mapping des tokens par chaîne
TOKEN_ADDRESSES = {
    "ethereum": {
        "USDC": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "UNI": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
    },
    "polygon": {
        "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
        "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        "DAI": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
        "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
        "MATIC": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
    },
    "arbitrum": {
        "USDC": "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8",
        "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
        "DAI": "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1",
        "WETH": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "WBTC": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",
    },
    "optimism": {
        "USDC": "0x7F5c764cBc14f9669B88837ca1490cCa17c31607",
        "USDT": "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",
        "DAI": "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1",
        "WETH": "0x4200000000000000000000000000000000000006",
    },
    "avalanche": {
        "USDC": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
        "USDT": "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7",
        "DAI": "0xd586E7F844cEa2F87f50152665BCbc2C279D8d70",
        "WETH": "0x49D5c2BdFfAC6AE2BFdb6640F4F80f226db10eAB",
        "AVAX": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
    },
    "base": {
        "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "WETH": "0x4200000000000000000000000000000000000006",
    },
}


# ============================================================
# CLASSE PRINCIPALE
# ============================================================

class DeFiConfigManager:
    """
    Gestionnaire centralisé de configuration DeFi
    """

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
        self._config: Optional[DeFiGlobalConfig] = None
        self._config_cache: Dict[str, Tuple[float, Any]] = {}

        # Création du répertoire
        os.makedirs(self.config_dir, exist_ok=True)

        # Chargement de la configuration
        self._load_config()

        logger.info(f"DeFiConfigManager initialisé (environnement: {environment.value})")

    # ============================================================
    # MÉTHODES DE CHARGEMENT
    # ============================================================

    def _load_config(self) -> None:
        """Charge la configuration complète"""
        try:
            # Chargement des configurations
            protocols = self._load_protocols()
            tokens = self._load_tokens()
            contracts = self._load_contracts()

            # Mise à jour des contrats dans les protocoles
            for protocol_name, protocol in protocols.items():
                if protocol_name in contracts:
                    for chain, chain_contracts in contracts[protocol_name].items():
                        if chain in protocol.chains:
                            for contract_name, address in chain_contracts.items():
                                if contract_name not in protocol.contracts:
                                    protocol.contracts[contract_name] = ContractConfig(
                                        address=address,
                                        version="1.0.0",
                                    )

            # Chargement des paramètres
            risk_parameters = self._load_risk_parameters()
            gas_settings = self._load_gas_settings()
            monitoring = self._load_monitoring_config()

            # Création de la configuration
            self._config = DeFiGlobalConfig(
                version="1.0.0",
                environment=self.environment,
                protocols=protocols,
                tokens=tokens,
                risk_parameters=risk_parameters,
                gas_settings=gas_settings,
                monitoring=monitoring,
                updated_at=datetime.now(),
                metadata={},
            )

            # Validation
            self._validate_config()

            logger.info(
                f"Configuration DeFi chargée: "
                f"{len(protocols)} protocoles, "
                f"{len(tokens)} tokens"
            )

        except Exception as e:
            logger.error(f"Erreur de chargement de la configuration: {e}")
            # Utiliser la configuration par défaut
            self._config = self._create_default_config()
            raise ConfigError(f"Erreur de chargement de la configuration: {e}")

    def _load_protocols(self) -> Dict[str, ProtocolConfig]:
        """Charge les configurations des protocoles"""
        protocols = {}

        # Chargement depuis les fichiers
        protocols_dir = os.path.join(self.config_dir, "protocols")
        if os.path.exists(protocols_dir):
            for file in os.listdir(protocols_dir):
                if file.endswith((".yaml", ".yml")):
                    protocol_data = self._load_yaml_file(os.path.join(protocols_dir, file))
                    if protocol_data and "protocol" in protocol_data:
                        protocol_name = protocol_data["protocol"]
                        protocols[protocol_name] = self._create_protocol_config(protocol_data)

        # Ajout des protocoles par défaut
        for protocol_name, default_data in DEFAULT_PROTOCOLS.items():
            if protocol_name not in protocols:
                protocols[protocol_name] = self._create_protocol_config({
                    "protocol": protocol_name,
                    **default_data,
                })

        return protocols

    def _load_tokens(self) -> Dict[str, TokenConfig]:
        """Charge les configurations des tokens"""
        tokens = {}

        # Chargement depuis les fichiers
        tokens_dir = os.path.join(self.config_dir, "tokens")
        if os.path.exists(tokens_dir):
            for file in os.listdir(tokens_dir):
                if file.endswith((".yaml", ".yml")):
                    token_data = self._load_yaml_file(os.path.join(tokens_dir, file))
                    if token_data and "symbol" in token_data:
                        symbol = token_data["symbol"]
                        tokens[symbol] = self._create_token_config(token_data)

        # Ajout des tokens par défaut
        for symbol, default_data in DEFAULT_TOKENS.items():
            if symbol not in tokens:
                token_data = {
                    "symbol": symbol,
                    **default_data,
                    "address": self._get_token_address(symbol),
                }
                tokens[symbol] = self._create_token_config(token_data)

        return tokens

    def _load_contracts(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """Charge les adresses des contrats"""
        contracts = {}

        for protocol_name, chain_addresses in CONTRACT_ADDRESSES.items():
            contracts[protocol_name] = {}
            for chain, addresses in chain_addresses.items():
                contracts[protocol_name][chain] = addresses

        return contracts

    def _load_risk_parameters(self) -> Dict[str, Any]:
        """Charge les paramètres de risque"""
        risk_path = os.path.join(self.config_dir, "risk.yaml")
        if os.path.exists(risk_path):
            return self._load_yaml_file(risk_path)

        return {
            "max_leverage": 3.0,
            "min_health_factor": 1.2,
            "liquidation_buffer": 0.1,
            "max_concentration": 0.3,
            "risk_tolerance": {
                "very_low": 0.1,
                "low": 0.2,
                "medium": 0.4,
                "high": 0.6,
                "very_high": 0.8,
            },
        }

    def _load_gas_settings(self) -> Dict[str, Any]:
        """Charge les paramètres de gaz"""
        gas_path = os.path.join(self.config_dir, "gas.yaml")
        if os.path.exists(gas_path):
            return self._load_yaml_file(gas_path)

        return {
            "max_gas_price": 500,
            "priority_fee": 2,
            "gas_multiplier": 1.1,
            "max_gas_limit": 2000000,
            "min_gas_limit": 100000,
        }

    def _load_monitoring_config(self) -> Dict[str, Any]:
        """Charge la configuration de monitoring"""
        monitoring_path = os.path.join(self.config_dir, "monitoring.yaml")
        if os.path.exists(monitoring_path):
            return self._load_yaml_file(monitoring_path)

        return {
            "enabled": True,
            "interval": 60,
            "alert_thresholds": {
                "apy_drop": 0.5,
                "tvl_drop": 0.2,
                "health_factor_drop": 0.1,
            },
            "slack_webhook": "",
            "email_recipients": [],
        }

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

    def _create_protocol_config(self, data: Dict[str, Any]) -> ProtocolConfig:
        """Crée une configuration de protocole"""
        return ProtocolConfig(
            protocol=DeFiProtocol(data.get("protocol", "aave_v3")),
            name=data.get("name", data.get("protocol", "Unknown")),
            chains=data.get("chains", ["ethereum"]),
            risk_level=RiskLevel(data.get("risk_level", "medium")),
            contracts={},
            supported_tokens=data.get("supported_tokens", []),
            min_amount=Decimal(str(data.get("min_amount", "0.001"))),
            max_amount=Decimal(str(data.get("max_amount", "1000000"))),
            max_slippage=Decimal(str(data.get("max_slippage", "0.01"))),
            gas_multiplier=data.get("gas_multiplier", 1.0),
            enabled=data.get("enabled", True),
            priority=data.get("priority", 0),
            metadata=data.get("metadata", {}),
        )

    def _create_token_config(self, data: Dict[str, Any]) -> TokenConfig:
        """Crée une configuration de token"""
        return TokenConfig(
            symbol=data.get("symbol", ""),
            name=data.get("name", data.get("symbol", "")),
            address=data.get("address", ""),
            decimals=data.get("decimals", 18),
            chain=data.get("chain", "ethereum"),
            is_native=data.get("is_native", False),
            is_stable=data.get("is_stable", False),
            is_wrapped=data.get("is_wrapped", False),
            coingecko_id=data.get("coingecko_id"),
            metadata=data.get("metadata", {}),
        )

    def _create_default_config(self) -> DeFiGlobalConfig:
        """Crée une configuration par défaut"""
        protocols = {}
        for protocol_name, default_data in DEFAULT_PROTOCOLS.items():
            protocols[protocol_name] = self._create_protocol_config({
                "protocol": protocol_name,
                **default_data,
                "chains": ["ethereum"],
            })

        tokens = {}
        for symbol, default_data in DEFAULT_TOKENS.items():
            tokens[symbol] = self._create_token_config({
                "symbol": symbol,
                **default_data,
                "address": self._get_token_address(symbol),
                "chain": "ethereum",
            })

        return DeFiGlobalConfig(
            version="1.0.0",
            environment=self.environment,
            protocols=protocols,
            tokens=tokens,
            risk_parameters=self._load_risk_parameters(),
            gas_settings=self._load_gas_settings(),
            monitoring=self._load_monitoring_config(),
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

        # Validation des protocoles
        for protocol_name, protocol in self._config.protocols.items():
            if protocol.enabled and not protocol.contracts:
                raise ConfigError(f"Contrats manquants pour {protocol_name}")

            # Validation des tokens supportés
            for token in protocol.supported_tokens:
                if token not in self._config.tokens:
                    raise ConfigError(f"Token {token} non configuré pour {protocol_name}")

        # Validation des tokens
        for symbol, token in self._config.tokens.items():
            if not token.address:
                raise ConfigError(f"Adresse manquante pour {symbol}")

            if token.decimals <= 0 or token.decimals > 18:
                raise ConfigError(f"Décimales invalides pour {symbol}")

        # Validation des paramètres
        risk_params = self._config.risk_parameters
        if risk_params.get("max_leverage", 0) <= 0:
            raise ConfigError("max_leverage doit être positif")

        logger.info("Configuration validée avec succès")

    # ============================================================
    # MÉTHODES D'ACCÈS
    # ============================================================

    def get_config(self) -> DeFiGlobalConfig:
        """Obtient la configuration complète"""
        if not self._config:
            self._load_config()
        return self._config

    def get_protocol_config(self, protocol: str) -> Optional[ProtocolConfig]:
        """Obtient la configuration d'un protocole"""
        return self._config.protocols.get(protocol)

    def get_token_config(self, symbol: str) -> Optional[TokenConfig]:
        """Obtient la configuration d'un token"""
        return self._config.tokens.get(symbol)

    def get_token_address(self, symbol: str, chain: str) -> Optional[str]:
        """Obtient l'adresse d'un token sur une chaîne"""
        if chain in TOKEN_ADDRESSES:
            return TOKEN_ADDRESSES[chain].get(symbol)
        return None

    def get_contract_address(
        self,
        protocol: str,
        chain: str,
        contract: str,
    ) -> Optional[str]:
        """Obtient l'adresse d'un contrat"""
        if protocol in CONTRACT_ADDRESSES:
            chain_addresses = CONTRACT_ADDRESSES[protocol].get(chain, {})
            return chain_addresses.get(contract)
        return None

    def get_supported_protocols(
        self,
        chain: Optional[str] = None,
        token: Optional[str] = None,
    ) -> List[str]:
        """Obtient la liste des protocoles supportés"""
        protocols = []

        for protocol_name, protocol in self._config.protocols.items():
            if not protocol.enabled:
                continue

            if chain and chain not in protocol.chains:
                continue

            if token and token not in protocol.supported_tokens:
                continue

            protocols.append(protocol_name)

        return protocols

    def get_supported_tokens(
        self,
        chain: Optional[str] = None,
        protocol: Optional[str] = None,
    ) -> List[str]:
        """Obtient la liste des tokens supportés"""
        tokens = set()

        if protocol:
            protocol_config = self.get_protocol_config(protocol)
            if protocol_config:
                tokens.update(protocol_config.supported_tokens)
        else:
            for protocol_config in self._config.protocols.values():
                if protocol_config.enabled:
                    if chain is None or chain in protocol_config.chains:
                        tokens.update(protocol_config.supported_tokens)

        return sorted(list(tokens))

    def get_risk_parameters(self) -> Dict[str, Any]:
        """Obtient les paramètres de risque"""
        return self._config.risk_parameters

    def get_gas_settings(self) -> Dict[str, Any]:
        """Obtient les paramètres de gaz"""
        return self._config.gas_settings

    def get_monitoring_config(self) -> Dict[str, Any]:
        """Obtient la configuration de monitoring"""
        return self._config.monitoring

    # ============================================================
    # MÉTHODES DE MISE À JOUR
    # ============================================================

    def update_config(self, new_config: DeFiGlobalConfig) -> None:
        """Met à jour la configuration"""
        self._config = new_config
        self._validate_config()
        self._config.updated_at = datetime.now()
        self._config_cache.clear()
        logger.info("Configuration DeFi mise à jour")

    def reload_config(self) -> None:
        """Recharge la configuration"""
        self._load_config()
        logger.info("Configuration DeFi rechargée")

    def save_config(self, path: Optional[str] = None) -> None:
        """Sauvegarde la configuration"""
        if not self._config:
            return

        save_path = path or os.path.join(self.config_dir, "defi_config.yaml")

        try:
            with open(save_path, 'w') as f:
                yaml.dump(self._config.to_dict(), f, default_flow_style=False)
            logger.info(f"Configuration DeFi sauvegardée: {save_path}")
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
        active_tokens = len(self._config.tokens)

        return {
            "protocols": len(self._config.protocols),
            "active_protocols": active_protocols,
            "tokens": active_tokens,
            "environment": self.environment.value,
            "version": self._config.version,
            "updated_at": self._config.updated_at.isoformat(),
            "chains_supported": self._get_supported_chains(),
        }

    def _get_supported_chains(self) -> List[str]:
        """Obtient la liste des chaînes supportées"""
        chains = set()
        for protocol in self._config.protocols.values():
            if protocol.enabled:
                chains.update(protocol.chains)
        return sorted(list(chains))

    # ============================================================
    # MÉTHODES DE NETTOYAGE
    # ============================================================

    async def cleanup(self) -> None:
        """Nettoie les ressources"""
        logger.info("Nettoyage des ressources DeFiConfigManager...")
        self._config_cache.clear()
        logger.info("Nettoyage terminé")


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_defi_config_manager(
    config_dir: Optional[str] = None,
    environment: str = "production",
    **kwargs,
) -> DeFiConfigManager:
    """
    Crée une instance de DeFiConfigManager

    Args:
        config_dir: Répertoire des configurations
        environment: Environnement
        **kwargs: Arguments additionnels

    Returns:
        Instance de DeFiConfigManager
    """
    env = Environment(environment.lower())
    return DeFiConfigManager(
        config_dir=config_dir,
        environment=env,
        **kwargs,
    )


# ============================================================
# EXEMPLE D'UTILISATION
# ============================================================

async def main_example():
    """Exemple d'utilisation de DeFiConfigManager"""
    # Création du gestionnaire
    config_manager = create_defi_config_manager(
        config_dir="./defi_configs",
        environment="production",
    )

    # Obtention de la configuration
    config = config_manager.get_config()
    print(f"Version: {config.version}")
    print(f"Environnement: {config.environment.value}")

    # Obtention d'un protocole
    aave_config = config_manager.get_protocol_config("aave_v3")
    print(f"\nAave V3:")
    print(f"  Risk level: {aave_config.risk_level.value}")
    print(f"  Supported tokens: {aave_config.supported_tokens}")
    print(f"  Min amount: {aave_config.min_amount}")

    # Obtention d'un token
    usdc_config = config_manager.get_token_config("USDC")
    print(f"\nUSDC:")
    print(f"  Name: {usdc_config.name}")
    print(f"  Decimals: {usdc_config.decimals}")
    print(f"  Stable: {usdc_config.is_stable}")

    # Obtention des protocoles supportés
    protocols = config_manager.get_supported_protocols(
        chain="ethereum",
        token="USDC",
    )
    print(f"\nProtocoles supportant USDC sur Ethereum: {protocols}")

    # Obtention des tokens supportés
    tokens = config_manager.get_supported_tokens(protocol="aave_v3")
    print(f"\nTokens supportés par Aave V3: {tokens}")

    # Paramètres de risque
    risk_params = config_manager.get_risk_parameters()
    print(f"\nParamètres de risque:")
    for key, value in risk_params.items():
        print(f"  {key}: {value}")

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
