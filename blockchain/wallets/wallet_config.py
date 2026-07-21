"""
NEXUS AI TRADING SYSTEM - WALLET CONFIG MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de configuration pour wallets multi-blockchain.
Gestion des paramètres, réseaux, tokens, et préférences utilisateur.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import yaml
from pathlib import Path

from .base_wallet import (
    BaseWallet,
    WalletConfig,
    WalletBalance,
    Transaction,
    TransactionType,
    TransactionStatus,
    BlockchainNetwork,
    WalletStatus,
    WalletType
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class ConfigVersion(Enum):
    """Versions de configuration."""
    V1 = "1.0.0"
    V2 = "2.0.0"
    V3 = "3.0.0"
    LATEST = "3.0.0"


class ConfigSource(Enum):
    """Sources de configuration."""
    FILE = "file"
    ENVIRONMENT = "environment"
    DATABASE = "database"
    REDIS = "redis"
    API = "api"
    DEFAULT = "default"
    USER = "user"


@dataclass
class NetworkConfig:
    """Configuration d'un réseau blockchain."""
    name: str
    chain_id: int
    rpc_urls: List[str]
    api_urls: List[str]
    explorer_url: str
    native_currency: str
    native_decimals: int
    gas_price_multiplier: float = 1.0
    max_gas_price: float = 0
    min_gas_price: float = 0
    is_testnet: bool = False
    is_mainnet: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "name": self.name,
            "chain_id": self.chain_id,
            "rpc_urls": self.rpc_urls,
            "api_urls": self.api_urls,
            "explorer_url": self.explorer_url,
            "native_currency": self.native_currency,
            "native_decimals": self.native_decimals,
            "gas_price_multiplier": self.gas_price_multiplier,
            "max_gas_price": self.max_gas_price,
            "min_gas_price": self.min_gas_price,
            "is_testnet": self.is_testnet,
            "is_mainnet": self.is_mainnet,
            "metadata": self.metadata
        }


@dataclass
class TokenConfig:
    """Configuration d'un token."""
    address: str
    symbol: str
    name: str
    decimals: int
    chain: str
    network: str
    is_native: bool = False
    is_stable: bool = False
    is_verified: bool = False
    price_source: Optional[str] = None
    price_oracle: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "address": self.address,
            "symbol": self.symbol,
            "name": self.name,
            "decimals": self.decimals,
            "chain": self.chain,
            "network": self.network,
            "is_native": self.is_native,
            "is_stable": self.is_stable,
            "is_verified": self.is_verified,
            "price_source": self.price_source,
            "price_oracle": self.price_oracle,
            "metadata": self.metadata
        }


@dataclass
class WalletPreferences:
    """Préférences utilisateur pour un wallet."""
    wallet_id: UUID
    user_id: UUID
    default_chain: str
    default_network: str
    default_gas_price: float = 0
    default_slippage: float = 0.5
    auto_compound: bool = True
    auto_claim: bool = False
    max_position_size: Decimal = Decimal("10000")
    min_position_size: Decimal = Decimal("10")
    risk_tolerance: str = "medium"  # low, medium, high
    preferred_dex: Optional[str] = None
    preferred_bridge: Optional[str] = None
    notification_enabled: bool = True
    notification_channels: List[str] = field(default_factory=lambda: ["email", "push"])
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "default_chain": self.default_chain,
            "default_network": self.default_network,
            "default_gas_price": self.default_gas_price,
            "default_slippage": self.default_slippage,
            "auto_compound": self.auto_compound,
            "auto_claim": self.auto_claim,
            "max_position_size": str(self.max_position_size),
            "min_position_size": str(self.min_position_size),
            "risk_tolerance": self.risk_tolerance,
            "preferred_dex": self.preferred_dex,
            "preferred_bridge": self.preferred_bridge,
            "notification_enabled": self.notification_enabled,
            "notification_channels": self.notification_channels,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class SecurityConfig:
    """Configuration de sécurité."""
    wallet_id: UUID
    user_id: UUID
    encryption_enabled: bool = True
    encryption_algorithm: str = "AES-256-GCM"
    two_factor_enabled: bool = False
    two_factor_method: Optional[str] = None
    whitelist_enabled: bool = False
    whitelist_addresses: List[str] = field(default_factory=list)
    max_transaction_amount: Decimal = Decimal("10000")
    daily_transaction_limit: Decimal = Decimal("50000")
    weekly_transaction_limit: Decimal = Decimal("200000")
    monthly_transaction_limit: Decimal = Decimal("500000")
    require_confirmation: bool = True
    confirmation_threshold: int = 2
    suspicious_activity_alert: bool = True
    ip_restriction_enabled: bool = False
    allowed_ips: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "wallet_id": str(self.wallet_id),
            "user_id": str(self.user_id),
            "encryption_enabled": self.encryption_enabled,
            "encryption_algorithm": self.encryption_algorithm,
            "two_factor_enabled": self.two_factor_enabled,
            "two_factor_method": self.two_factor_method,
            "whitelist_enabled": self.whitelist_enabled,
            "whitelist_addresses": self.whitelist_addresses,
            "max_transaction_amount": str(self.max_transaction_amount),
            "daily_transaction_limit": str(self.daily_transaction_limit),
            "weekly_transaction_limit": str(self.weekly_transaction_limit),
            "monthly_transaction_limit": str(self.monthly_transaction_limit),
            "require_confirmation": self.require_confirmation,
            "confirmation_threshold": self.confirmation_threshold,
            "suspicious_activity_alert": self.suspicious_activity_alert,
            "ip_restriction_enabled": self.ip_restriction_enabled,
            "allowed_ips": self.allowed_ips,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


# ============================================================================
# CONFIGURATIONS PAR DÉFAUT
# ============================================================================

DEFAULT_NETWORKS = {
    "ethereum": {
        "mainnet": NetworkConfig(
            name="mainnet",
            chain_id=1,
            rpc_urls=[
                "https://eth.llamarpc.com",
                "https://rpc.ankr.com/eth",
                "https://eth-mainnet.public.blastapi.io"
            ],
            api_urls=["https://api.etherscan.io/api"],
            explorer_url="https://etherscan.io",
            native_currency="ETH",
            native_decimals=18,
            is_mainnet=True
        ),
        "goerli": NetworkConfig(
            name="goerli",
            chain_id=5,
            rpc_urls=["https://goerli.gateway.tenderly.co"],
            api_urls=["https://api-goerli.etherscan.io/api"],
            explorer_url="https://goerli.etherscan.io",
            native_currency="ETH",
            native_decimals=18,
            is_testnet=True,
            is_mainnet=False
        ),
        "sepolia": NetworkConfig(
            name="sepolia",
            chain_id=11155111,
            rpc_urls=["https://sepolia.gateway.tenderly.co"],
            api_urls=["https://api-sepolia.etherscan.io/api"],
            explorer_url="https://sepolia.etherscan.io",
            native_currency="ETH",
            native_decimals=18,
            is_testnet=True,
            is_mainnet=False
        )
    },
    "bsc": {
        "mainnet": NetworkConfig(
            name="mainnet",
            chain_id=56,
            rpc_urls=[
                "https://bsc-dataseed.binance.org",
                "https://bsc-dataseed1.binance.org"
            ],
            api_urls=["https://api.bscscan.com/api"],
            explorer_url="https://bscscan.com",
            native_currency="BNB",
            native_decimals=18,
            is_mainnet=True
        ),
        "testnet": NetworkConfig(
            name="testnet",
            chain_id=97,
            rpc_urls=["https://data-seed-prebsc-1-s1.binance.org:8545"],
            api_urls=["https://api-testnet.bscscan.com/api"],
            explorer_url="https://testnet.bscscan.com",
            native_currency="BNB",
            native_decimals=18,
            is_testnet=True,
            is_mainnet=False
        )
    },
    "polygon": {
        "mainnet": NetworkConfig(
            name="mainnet",
            chain_id=137,
            rpc_urls=[
                "https://polygon-rpc.com",
                "https://rpc-mainnet.maticvigil.com"
            ],
            api_urls=["https://api.polygonscan.com/api"],
            explorer_url="https://polygonscan.com",
            native_currency="MATIC",
            native_decimals=18,
            is_mainnet=True
        ),
        "mumbai": NetworkConfig(
            name="mumbai",
            chain_id=80001,
            rpc_urls=["https://rpc-mumbai.maticvigil.com"],
            api_urls=["https://api-mumbai.polygonscan.com/api"],
            explorer_url="https://mumbai.polygonscan.com",
            native_currency="MATIC",
            native_decimals=18,
            is_testnet=True,
            is_mainnet=False
        )
    },
    "solana": {
        "mainnet": NetworkConfig(
            name="mainnet",
            chain_id=1,
            rpc_urls=[
                "https://api.mainnet-beta.solana.com",
                "https://solana-api.projectserum.com"
            ],
            api_urls=["https://api.solscan.io/v1"],
            explorer_url="https://solscan.io",
            native_currency="SOL",
            native_decimals=9,
            is_mainnet=True
        ),
        "devnet": NetworkConfig(
            name="devnet",
            chain_id=2,
            rpc_urls=["https://api.devnet.solana.com"],
            api_urls=["https://api.solscan.io/v1"],
            explorer_url="https://solscan.io?cluster=devnet",
            native_currency="SOL",
            native_decimals=9,
            is_testnet=True,
            is_mainnet=False
        )
    },
    "tron": {
        "mainnet": NetworkConfig(
            name="mainnet",
            chain_id=1,
            rpc_urls=[
                "https://api.trongrid.io",
                "https://api.trongrid.net"
            ],
            api_urls=["https://api.tronscan.org/api"],
            explorer_url="https://tronscan.org",
            native_currency="TRX",
            native_decimals=6,
            is_mainnet=True
        ),
        "shasta": NetworkConfig(
            name="shasta",
            chain_id=2,
            rpc_urls=["https://api.shasta.trongrid.io"],
            api_urls=["https://api.shasta.tronscan.org/api"],
            explorer_url="https://shasta.tronscan.org",
            native_currency="TRX",
            native_decimals=6,
            is_testnet=True,
            is_mainnet=False
        )
    }
}

DEFAULT_TOKENS = {
    "ethereum": {
        "mainnet": {
            "0xdAC17F958D2ee523a2206206994597C13D831ec7": TokenConfig(
                address="0xdAC17F958D2ee523a2206206994597C13D831ec7",
                symbol="USDT",
                name="Tether USD",
                decimals=18,
                chain="ethereum",
                network="mainnet",
                is_stable=True,
                is_verified=True,
                price_source="coingecko"
            ),
            "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": TokenConfig(
                address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                symbol="USDC",
                name="USD Coin",
                decimals=18,
                chain="ethereum",
                network="mainnet",
                is_stable=True,
                is_verified=True,
                price_source="coingecko"
            ),
            "0x6B175474E89094C44Da98b954EedeAC495271d0F": TokenConfig(
                address="0x6B175474E89094C44Da98b954EedeAC495271d0F",
                symbol="DAI",
                name="Dai Stablecoin",
                decimals=18,
                chain="ethereum",
                network="mainnet",
                is_stable=True,
                is_verified=True,
                price_source="coingecko"
            ),
            "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599": TokenConfig(
                address="0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                symbol="WBTC",
                name="Wrapped Bitcoin",
                decimals=8,
                chain="ethereum",
                network="mainnet",
                is_verified=True,
                price_source="coingecko"
            ),
            "0x514910771AF9Ca656af840dff83E8264EcF986CA": TokenConfig(
                address="0x514910771AF9Ca656af840dff83E8264EcF986CA",
                symbol="LINK",
                name="Chainlink",
                decimals=18,
                chain="ethereum",
                network="mainnet",
                is_verified=True,
                price_source="coingecko"
            )
        }
    },
    "bsc": {
        "mainnet": {
            "0x55d398326f99059fF775485246999027B3197955": TokenConfig(
                address="0x55d398326f99059fF775485246999027B3197955",
                symbol="USDT",
                name="Tether USD",
                decimals=18,
                chain="bsc",
                network="mainnet",
                is_stable=True,
                is_verified=True,
                price_source="coingecko"
            ),
            "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d": TokenConfig(
                address="0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
                symbol="USDC",
                name="USD Coin",
                decimals=18,
                chain="bsc",
                network="mainnet",
                is_stable=True,
                is_verified=True,
                price_source="coingecko"
            ),
            "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56": TokenConfig(
                address="0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56",
                symbol="BUSD",
                name="Binance USD",
                decimals=18,
                chain="bsc",
                network="mainnet",
                is_stable=True,
                is_verified=True,
                price_source="coingecko"
            )
        }
    }
}


# ============================================================================
# CLASSE WALLET CONFIG SERVICE
# ============================================================================

class WalletConfigService:
    """
    Service de configuration pour wallets multi-blockchain.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le service de configuration.

        Args:
            config_path: Chemin du fichier de configuration
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
        """
        self.config_path = Path(config_path) if config_path else Path("./config")
        self.redis = redis_client
        self.api_keys = api_keys or {}
        
        # Configuration des réseaux et tokens
        self.networks = DEFAULT_NETWORKS.copy()
        self.tokens = DEFAULT_TOKENS.copy()
        
        # Cache
        self._wallet_config_cache: Dict[UUID, WalletConfig] = {}
        self._preferences_cache: Dict[UUID, WalletPreferences] = {}
        self._security_cache: Dict[UUID, SecurityConfig] = {}
        
        # Métriques
        self._metrics = {
            "total_configs_loaded": 0,
            "total_configs_saved": 0,
            "last_load": None,
            "last_save": None
        }

        # Chargement de la configuration
        self._load_default_configs()
        
        logger.info("WalletConfigService initialisé avec succès")

    def _load_default_configs(self) -> None:
        """Charge les configurations par défaut."""
        try:
            # Chargement des réseaux
            for chain, networks in DEFAULT_NETWORKS.items():
                if chain not in self.networks:
                    self.networks[chain] = {}
                for network, config in networks.items():
                    self.networks[chain][network] = config

            # Chargement des tokens
            for chain, networks in DEFAULT_TOKENS.items():
                if chain not in self.tokens:
                    self.tokens[chain] = {}
                for network, tokens in networks.items():
                    if network not in self.tokens[chain]:
                        self.tokens[chain][network] = {}
                    for address, token in tokens.items():
                        self.tokens[chain][network][address] = token

            logger.info("Configurations par défaut chargées")

        except Exception as e:
            logger.error(f"Erreur lors du chargement des configs par défaut: {e}")

    # ========================================================================
    # GESTION DES RÉSEAUX
    # ========================================================================

    def get_network_config(
        self,
        chain: str,
        network: str
    ) -> Optional[NetworkConfig]:
        """
        Récupère la configuration d'un réseau.

        Args:
            chain: Blockchain
            network: Réseau

        Returns:
            Configuration du réseau
        """
        try:
            return self.networks.get(chain, {}).get(network)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du réseau: {e}")
            return None

    def get_all_networks(
        self,
        chain: Optional[str] = None
    ) -> Dict[str, Dict[str, NetworkConfig]]:
        """
        Récupère toutes les configurations de réseaux.

        Args:
            chain: Filtrer par blockchain

        Returns:
            Configurations des réseaux
        """
        try:
            if chain:
                return {chain: self.networks.get(chain, {})}
            return self.networks.copy()
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des réseaux: {e}")
            return {}

    async def add_network(
        self,
        chain: str,
        network: str,
        config: NetworkConfig
    ) -> bool:
        """
        Ajoute une configuration de réseau.

        Args:
            chain: Blockchain
            network: Réseau
            config: Configuration du réseau

        Returns:
            True si l'ajout a réussi
        """
        try:
            if chain not in self.networks:
                self.networks[chain] = {}
            
            self.networks[chain][network] = config
            
            # Sauvegarde dans Redis
            if self.redis:
                key = f"config:network:{chain}:{network}"
                await self.redis.setex(
                    key,
                    86400 * 30,  # 30 jours
                    json.dumps(config.to_dict())
                )
            
            logger.info(f"Réseau ajouté: {chain}:{network}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'ajout du réseau: {e}")
            return False

    async def remove_network(
        self,
        chain: str,
        network: str
    ) -> bool:
        """
        Supprime une configuration de réseau.

        Args:
            chain: Blockchain
            network: Réseau

        Returns:
            True si la suppression a réussi
        """
        try:
            if chain in self.networks and network in self.networks[chain]:
                del self.networks[chain][network]
                
                # Suppression de Redis
                if self.redis:
                    key = f"config:network:{chain}:{network}"
                    await self.redis.delete(key)
                
                logger.info(f"Réseau supprimé: {chain}:{network}")
                return True
            
            return False

        except Exception as e:
            logger.error(f"Erreur lors de la suppression du réseau: {e}")
            return False

    # ========================================================================
    # GESTION DES TOKENS
    # ========================================================================

    def get_token_config(
        self,
        chain: str,
        network: str,
        address: str
    ) -> Optional[TokenConfig]:
        """
        Récupère la configuration d'un token.

        Args:
            chain: Blockchain
            network: Réseau
            address: Adresse du token

        Returns:
            Configuration du token
        """
        try:
            return self.tokens.get(chain, {}).get(network, {}).get(address)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du token: {e}")
            return None

    def get_all_tokens(
        self,
        chain: Optional[str] = None,
        network: Optional[str] = None
    ) -> Dict[str, Dict[str, Dict[str, TokenConfig]]]:
        """
        Récupère toutes les configurations de tokens.

        Args:
            chain: Filtrer par blockchain
            network: Filtrer par réseau

        Returns:
            Configurations des tokens
        """
        try:
            if chain and network:
                return {chain: {network: self.tokens.get(chain, {}).get(network, {})}}
            elif chain:
                return {chain: self.tokens.get(chain, {})}
            return self.tokens.copy()
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des tokens: {e}")
            return {}

    async def add_token(
        self,
        chain: str,
        network: str,
        address: str,
        config: TokenConfig
    ) -> bool:
        """
        Ajoute une configuration de token.

        Args:
            chain: Blockchain
            network: Réseau
            address: Adresse du token
            config: Configuration du token

        Returns:
            True si l'ajout a réussi
        """
        try:
            if chain not in self.tokens:
                self.tokens[chain] = {}
            if network not in self.tokens[chain]:
                self.tokens[chain][network] = {}
            
            self.tokens[chain][network][address] = config
            
            # Sauvegarde dans Redis
            if self.redis:
                key = f"config:token:{chain}:{network}:{address}"
                await self.redis.setex(
                    key,
                    86400 * 30,
                    json.dumps(config.to_dict())
                )
            
            logger.info(f"Token ajouté: {chain}:{network}:{address}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'ajout du token: {e}")
            return False

    async def remove_token(
        self,
        chain: str,
        network: str,
        address: str
    ) -> bool:
        """
        Supprime une configuration de token.

        Args:
            chain: Blockchain
            network: Réseau
            address: Adresse du token

        Returns:
            True si la suppression a réussi
        """
        try:
            if (chain in self.tokens and 
                network in self.tokens[chain] and 
                address in self.tokens[chain][network]):
                
                del self.tokens[chain][network][address]
                
                # Suppression de Redis
                if self.redis:
                    key = f"config:token:{chain}:{network}:{address}"
                    await self.redis.delete(key)
                
                logger.info(f"Token supprimé: {chain}:{network}:{address}")
                return True
            
            return False

        except Exception as e:
            logger.error(f"Erreur lors de la suppression du token: {e}")
            return False

    # ========================================================================
    # GESTION DES PRÉFÉRENCES
    # ========================================================================

    async def get_preferences(
        self,
        wallet_id: UUID,
        user_id: UUID
    ) -> WalletPreferences:
        """
        Récupère les préférences d'un wallet.

        Args:
            wallet_id: ID du wallet
            user_id: ID de l'utilisateur

        Returns:
            Préférences du wallet
        """
        try:
            # Vérification du cache
            if wallet_id in self._preferences_cache:
                return self._preferences_cache[wallet_id]

            # Récupération depuis Redis
            if self.redis:
                key = f"config:preferences:{wallet_id}"
                data = await self.redis.get(key)
                if data:
                    pref_dict = json.loads(data)
                    preferences = WalletPreferences(
                        wallet_id=UUID(pref_dict["wallet_id"]),
                        user_id=UUID(pref_dict["user_id"]),
                        default_chain=pref_dict["default_chain"],
                        default_network=pref_dict["default_network"],
                        default_gas_price=float(pref_dict.get("default_gas_price", 0)),
                        default_slippage=float(pref_dict.get("default_slippage", 0.5)),
                        auto_compound=pref_dict.get("auto_compound", True),
                        auto_claim=pref_dict.get("auto_claim", False),
                        max_position_size=Decimal(pref_dict.get("max_position_size", "10000")),
                        min_position_size=Decimal(pref_dict.get("min_position_size", "10")),
                        risk_tolerance=pref_dict.get("risk_tolerance", "medium"),
                        preferred_dex=pref_dict.get("preferred_dex"),
                        preferred_bridge=pref_dict.get("preferred_bridge"),
                        notification_enabled=pref_dict.get("notification_enabled", True),
                        notification_channels=pref_dict.get("notification_channels", ["email", "push"]),
                        metadata=pref_dict.get("metadata", {}),
                        created_at=datetime.fromisoformat(pref_dict["created_at"]),
                        updated_at=datetime.fromisoformat(pref_dict["updated_at"])
                    )
                    self._preferences_cache[wallet_id] = preferences
                    return preferences

            # Préférences par défaut
            preferences = WalletPreferences(
                wallet_id=wallet_id,
                user_id=user_id,
                default_chain="ethereum",
                default_network="mainnet"
            )
            
            self._preferences_cache[wallet_id] = preferences
            return preferences

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des préférences: {e}")
            return WalletPreferences(
                wallet_id=wallet_id,
                user_id=user_id,
                default_chain="ethereum",
                default_network="mainnet"
            )

    async def save_preferences(
        self,
        preferences: WalletPreferences
    ) -> bool:
        """
        Sauvegarde les préférences d'un wallet.

        Args:
            preferences: Préférences à sauvegarder

        Returns:
            True si la sauvegarde a réussi
        """
        try:
            preferences.updated_at = datetime.now()
            
            # Mise en cache
            self._preferences_cache[preferences.wallet_id] = preferences
            
            # Sauvegarde dans Redis
            if self.redis:
                key = f"config:preferences:{preferences.wallet_id}"
                await self.redis.setex(
                    key,
                    86400 * 30,
                    json.dumps(preferences.to_dict())
                )
            
            self._metrics["total_configs_saved"] += 1
            self._metrics["last_save"] = datetime.now().isoformat()
            
            logger.info(f"Préférences sauvegardées pour {preferences.wallet_id}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des préférences: {e}")
            return False

    # ========================================================================
    # GESTION DE LA SÉCURITÉ
    # ========================================================================

    async def get_security_config(
        self,
        wallet_id: UUID,
        user_id: UUID
    ) -> SecurityConfig:
        """
        Récupère la configuration de sécurité d'un wallet.

        Args:
            wallet_id: ID du wallet
            user_id: ID de l'utilisateur

        Returns:
            Configuration de sécurité
        """
        try:
            # Vérification du cache
            if wallet_id in self._security_cache:
                return self._security_cache[wallet_id]

            # Récupération depuis Redis
            if self.redis:
                key = f"config:security:{wallet_id}"
                data = await self.redis.get(key)
                if data:
                    sec_dict = json.loads(data)
                    security = SecurityConfig(
                        wallet_id=UUID(sec_dict["wallet_id"]),
                        user_id=UUID(sec_dict["user_id"]),
                        encryption_enabled=sec_dict.get("encryption_enabled", True),
                        encryption_algorithm=sec_dict.get("encryption_algorithm", "AES-256-GCM"),
                        two_factor_enabled=sec_dict.get("two_factor_enabled", False),
                        two_factor_method=sec_dict.get("two_factor_method"),
                        whitelist_enabled=sec_dict.get("whitelist_enabled", False),
                        whitelist_addresses=sec_dict.get("whitelist_addresses", []),
                        max_transaction_amount=Decimal(sec_dict.get("max_transaction_amount", "10000")),
                        daily_transaction_limit=Decimal(sec_dict.get("daily_transaction_limit", "50000")),
                        weekly_transaction_limit=Decimal(sec_dict.get("weekly_transaction_limit", "200000")),
                        monthly_transaction_limit=Decimal(sec_dict.get("monthly_transaction_limit", "500000")),
                        require_confirmation=sec_dict.get("require_confirmation", True),
                        confirmation_threshold=int(sec_dict.get("confirmation_threshold", 2)),
                        suspicious_activity_alert=sec_dict.get("suspicious_activity_alert", True),
                        ip_restriction_enabled=sec_dict.get("ip_restriction_enabled", False),
                        allowed_ips=sec_dict.get("allowed_ips", []),
                        metadata=sec_dict.get("metadata", {}),
                        created_at=datetime.fromisoformat(sec_dict["created_at"]),
                        updated_at=datetime.fromisoformat(sec_dict["updated_at"])
                    )
                    self._security_cache[wallet_id] = security
                    return security

            # Configuration par défaut
            security = SecurityConfig(
                wallet_id=wallet_id,
                user_id=user_id
            )
            
            self._security_cache[wallet_id] = security
            return security

        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la config de sécurité: {e}")
            return SecurityConfig(wallet_id=wallet_id, user_id=user_id)

    async def save_security_config(
        self,
        security: SecurityConfig
    ) -> bool:
        """
        Sauvegarde la configuration de sécurité.

        Args:
            security: Configuration de sécurité

        Returns:
            True si la sauvegarde a réussi
        """
        try:
            security.updated_at = datetime.now()
            
            # Mise en cache
            self._security_cache[security.wallet_id] = security
            
            # Sauvegarde dans Redis
            if self.redis:
                key = f"config:security:{security.wallet_id}"
                await self.redis.setex(
                    key,
                    86400 * 30,
                    json.dumps(security.to_dict())
                )
            
            logger.info(f"Configuration de sécurité sauvegardée pour {security.wallet_id}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de la config de sécurité: {e}")
            return False

    # ========================================================================
    # VALIDATION DE CONFIGURATION
    # ========================================================================

    async def validate_config(
        self,
        config: WalletConfig
    ) -> Tuple[bool, List[str]]:
        """
        Valide une configuration de wallet.

        Args:
            config: Configuration à valider

        Returns:
            (valide, liste des erreurs)
        """
        errors = []

        try:
            # Validation de l'adresse
            if not config.address or len(config.address) < 10:
                errors.append("Adresse invalide")

            # Validation de la blockchain
            if config.blockchain not in self.networks:
                errors.append(f"Blockchain non supportée: {config.blockchain}")

            # Validation du réseau
            if config.blockchain in self.networks:
                network_name = config.network.value if hasattr(config.network, 'value') else str(config.network)
                if network_name not in self.networks[config.blockchain]:
                    errors.append(f"Réseau non supporté: {network_name}")

            # Validation du type
            if not hasattr(config.type, 'value') or config.type.value not in [t.value for t in WalletType]:
                errors.append("Type de wallet invalide")

            # Validation du statut
            if not hasattr(config.status, 'value') or config.status.value not in [s.value for s in WalletStatus]:
                errors.append("Statut de wallet invalide")

            return len(errors) == 0, errors

        except Exception as e:
            logger.error(f"Erreur lors de la validation: {e}")
            return False, [str(e)]

    # ========================================================================
    # CHARGEMENT ET SAUVEGARDE DE FICHIERS
    # ========================================================================

    async def load_config_file(
        self,
        file_path: str
    ) -> Dict[str, Any]:
        """
        Charge une configuration depuis un fichier.

        Args:
            file_path: Chemin du fichier

        Returns:
            Configuration chargée
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                logger.warning(f"Fichier de configuration non trouvé: {file_path}")
                return {}

            if path.suffix == '.json':
                async with aiofiles.open(path, 'r') as f:
                    data = await f.read()
                    return json.loads(data)
            elif path.suffix in ['.yaml', '.yml']:
                async with aiofiles.open(path, 'r') as f:
                    data = await f.read()
                    return yaml.safe_load(data)
            else:
                logger.error(f"Format de fichier non supporté: {path.suffix}")
                return {}

        except Exception as e:
            logger.error(f"Erreur lors du chargement du fichier: {e}")
            return {}

    async def save_config_file(
        self,
        file_path: str,
        config: Dict[str, Any],
        format: str = 'json'
    ) -> bool:
        """
        Sauvegarde une configuration dans un fichier.

        Args:
            file_path: Chemin du fichier
            config: Configuration à sauvegarder
            format: Format de fichier ('json' ou 'yaml')

        Returns:
            True si la sauvegarde a réussi
        """
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            if format == 'json':
                content = json.dumps(config, indent=2)
            elif format in ['yaml', 'yml']:
                content = yaml.dump(config, default_flow_style=False)
            else:
                logger.error(f"Format non supporté: {format}")
                return False

            async with aiofiles.open(path, 'w') as f:
                await f.write(content)

            logger.info(f"Configuration sauvegardée: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du fichier: {e}")
            return False

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_configs_loaded": self._metrics["total_configs_loaded"],
                "total_configs_saved": self._metrics["total_configs_saved"],
                "last_load": self._metrics["last_load"],
                "last_save": self._metrics["last_save"],
                "networks_loaded": sum(len(n) for n in self.networks.values()),
                "tokens_loaded": sum(len(t) for chains in self.tokens.values() for t in chains.values()),
                "cached_preferences": len(self._preferences_cache),
                "cached_security": len(self._security_cache),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de WalletConfigService...")
        self._wallet_config_cache.clear()
        self._preferences_cache.clear()
        self._security_cache.clear()
        logger.info("WalletConfigService fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_wallet_config_service(
    config_path: Optional[str] = None,
    api_keys: Optional[Dict[str, str]] = None,
    redis_url: str = "redis://localhost:6379/0"
) -> WalletConfigService:
    """
    Crée une instance du service de configuration.

    Args:
        config_path: Chemin du fichier de configuration
        api_keys: Clés API pour les services externes
        redis_url: URL de connexion Redis

    Returns:
        Instance du service
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return WalletConfigService(
        config_path=config_path,
        redis_client=redis_client,
        api_keys=api_keys
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "ConfigVersion",
    "ConfigSource",
    "NetworkConfig",
    "TokenConfig",
    "WalletPreferences",
    "SecurityConfig",
    "WalletConfigService",
    "create_wallet_config_service",
    "DEFAULT_NETWORKS",
    "DEFAULT_TOKENS"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du service de configuration."""
    print("=" * 60)
    print("NEXUS AI TRADING - WALLET CONFIG MODULE")
    print("=" * 60)

    # Création du service
    config_service = create_wallet_config_service(
        config_path="./config",
        api_keys={}
    )

    # Récupération des réseaux
    print("\n🌐 Réseaux disponibles:")
    for chain, networks in config_service.get_all_networks().items():
        print(f"   {chain.upper()}:")
        for network, config in networks.items():
            print(f"      - {network}: {config.native_currency} (chain_id: {config.chain_id})")

    # Récupération des tokens
    print("\n💰 Tokens disponibles:")
    for chain, networks in config_service.get_all_tokens().items():
        print(f"   {chain.upper()}:")
        for network, tokens in networks.items():
            print(f"      {network}:")
            for address, token in list(tokens.items())[:3]:
                print(f"         - {token.symbol}: {token.name}")

    # Création d'un wallet exemple
    from uuid import UUID
    from .base_wallet import WalletConfig, BlockchainNetwork, WalletType, WalletStatus
    
    user_id = UUID("12345678-1234-5678-1234-567812345678")
    wallet_id = UUID("87654321-4321-5678-8765-432187654321")
    
    config = WalletConfig(
        wallet_id=wallet_id,
        user_id=user_id,
        name="Example Wallet",
        type=WalletType.EOA,
        blockchain="ethereum",
        network=BlockchainNetwork.ETHEREUM_MAINNET,
        address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        private_key_encrypted="encrypted_private_key",
        public_key="public_key",
        is_created=True,
        is_imported=False,
        is_hardware=False,
        status=WalletStatus.ACTIVE,
        metadata={"source": "example"}
    )

    # Validation de la configuration
    valid, errors = await config_service.validate_config(config)
    print(f"\n✅ Configuration valide: {valid}")
    if errors:
        print(f"   Erreurs: {errors}")

    # Sauvegarde des préférences
    preferences = WalletPreferences(
        wallet_id=wallet_id,
        user_id=user_id,
        default_chain="ethereum",
        default_network="mainnet",
        auto_compound=True,
        risk_tolerance="medium"
    )
    
    saved = await config_service.save_preferences(preferences)
    print(f"\n💾 Préférences sauvegardées: {saved}")

    # Récupération des préférences
    retrieved = await config_service.get_preferences(wallet_id, user_id)
    print(f"\n📋 Préférences récupérées:")
    print(f"   Wallet: {retrieved.wallet_id}")
    print(f"   Chaîne par défaut: {retrieved.default_chain}")
    print(f"   Auto-compound: {retrieved.auto_compound}")
    print(f"   Tolérance au risque: {retrieved.risk_tolerance}")

    # Santé du service
    health = await config_service.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Réseaux chargés: {health['networks_loaded']}")
    print(f"   Tokens chargés: {health['tokens_loaded']}")
    print(f"   Préférences en cache: {health['cached_preferences']}")

    # Fermeture
    await config_service.close()

    print("\n" + "=" * 60)
    print("WalletConfigService NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import aiofiles
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
