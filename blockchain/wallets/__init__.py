"""
NEXUS AI TRADING SYSTEM - WALLETS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de gestion des wallets multi-blockchain pour la plateforme NEXUS.
Support complet des wallets sur Ethereum, BSC, Polygon, Solana, Tron, Avalanche, etc.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

# Version du module
__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"


# ============================================================================
# IMPORTS DES MODULES PRINCIPAUX
# ============================================================================

from .base_wallet import (
    BaseWallet,
    WalletConfig,
    WalletBalance,
    Transaction,
    TransactionType,
    TransactionStatus,
    BlockchainNetwork,
    WalletStatus,
    WalletType,
    WalletError,
    WalletNotFoundError,
    WalletLockedError,
    InsufficientBalanceError,
    InvalidAddressError,
    TransactionError,
    NetworkError
)

from .wallet_config import (
    WalletConfigService,
    NetworkConfig,
    TokenConfig,
    WalletPreferences,
    SecurityConfig,
    create_wallet_config_service,
    DEFAULT_NETWORKS,
    DEFAULT_TOKENS
)

from .wallet_manager import (
    WalletManager,
    WalletManagerStatus,
    WalletOperation,
    WalletOperationResult,
    WalletHealthCheck,
    create_wallet_manager
)

from .wallet_balance import (
    WalletBalanceService,
    BalanceType,
    PriceSource,
    TokenPrice,
    BalanceSnapshot,
    BalanceAlert,
    create_wallet_balance_service
)

from .wallet_history import (
    WalletHistoryService,
    HistoryFilter,
    HistorySort,
    TransactionSummary,
    TransactionGroup,
    HistoryStats,
    create_wallet_history_service
)

from .wallet_security import (
    WalletSecurity,
    SecurityLevel,
    SecurityEventType,
    TwoFactorMethod,
    SecurityEvent,
    APIKey,
    Session,
    create_wallet_security
)

from .wallet_signer import (
    WalletSigner,
    SignatureType,
    SigningStatus,
    SigningRequest,
    SignedTransaction,
    create_wallet_signer
)

from .wallet_transaction import (
    WalletTransactionService,
    TransactionPriority,
    TransactionCategory,
    TransactionBuilder,
    TransactionReceipt,
    TransactionBatch,
    create_wallet_transaction_service
)

from .wallet_monitor import (
    WalletMonitor,
    MonitorEventType,
    MonitorSeverity,
    MonitorEvent,
    MonitorAlert,
    MonitorMetrics,
    create_wallet_monitor
)

from .wallet_backup import (
    WalletBackupService,
    BackupType,
    BackupStatus,
    RecoveryMethod,
    BackupMetadata,
    BackupData,
    BackupRecovery,
    create_wallet_backup_service
)

from .wallet_analytics import (
    WalletAnalyticsService,
    AnalyticsPeriod,
    RiskMetric,
    PerformanceMetric,
    PortfolioSnapshot,
    PortfolioPerformance,
    WalletInsight,
    WalletAnalytics,
    create_wallet_analytics_service
)

from .wallet_hd import (
    HDWallet,
    HDWalletFactory,
    HDStandard,
    HDCoinType,
    HDWalletPath,
    HDWalletInfo,
    HDAddress,
    COIN_TYPE_MAP,
    create_hd_wallet
)

from .multi_chain_wallet import (
    MultiChainWalletManager,
    MultiChainWallet,
    CrossChainTransaction,
    ChainType,
    CHAIN_NETWORKS,
    CHAIN_TOKENS,
    BRIDGE_CONFIG,
    create_multi_chain_manager
)

# ============================================================================
# IMPORTS DES WALLETS SPÉCIFIQUES PAR BLOCKCHAIN
# ============================================================================

from .ethereum_wallet import (
    EthereumWallet,
    ERC20_TOKENS,
    UNISWAP_V2_ROUTER,
    UNISWAP_V2_FACTORY,
    UNISWAP_V3_ROUTER,
    UNISWAP_V3_FACTORY,
    create_ethereum_wallet
)

from .bsc_wallet import (
    BSCWallet,
    BEP20_TOKENS,
    PANCAKESWAP_ROUTER,
    PANCAKESWAP_FACTORY,
    create_bsc_wallet
)

from .polygon_wallet import (
    PolygonWallet,
    POLYGON_TOKENS,
    QUICKSWAP_ROUTER,
    QUICKSWAP_FACTORY,
    create_polygon_wallet
)

from .solana_wallet import (
    SolanaWallet,
    SPL_TOKENS,
    SOLANA_PROGRAMS,
    create_solana_wallet
)

from .tron_wallet import (
    TronWallet,
    TRC20_TOKENS,
    TRC10_TOKENS,
    TRON_CONTRACTS,
    create_tron_wallet
)

from .avalanche_wallet import (
    AvalancheWallet,
    AVAX_TOKENS,
    TRADERJOE_ROUTER,
    create_avalanche_wallet
)

from .arbitrum_wallet import (
    ArbitrumWallet,
    ARBITRUM_TOKENS,
    create_arbitrum_wallet
)

from .optimism_wallet import (
    OptimismWallet,
    OPTIMISM_TOKENS,
    create_optimism_wallet
)


# ============================================================================
# CONSTANTES GLOBALES
# ============================================================================

# Blockchains supportées
SUPPORTED_BLOCKCHAINS = [
    "ethereum",
    "bsc",
    "polygon",
    "solana",
    "tron",
    "avalanche",
    "arbitrum",
    "optimism"
]

# Réseaux supportés par blockchain
SUPPORTED_NETWORKS = {
    "ethereum": ["mainnet", "goerli", "sepolia", "holesky"],
    "bsc": ["mainnet", "testnet"],
    "polygon": ["mainnet", "mumbai"],
    "solana": ["mainnet", "devnet", "testnet"],
    "tron": ["mainnet", "shasta", "nile"],
    "avalanche": ["mainnet", "fuji"],
    "arbitrum": ["mainnet", "goerli"],
    "optimism": ["mainnet", "goerli"]
}

# Tokens natifs par blockchain
NATIVE_TOKENS = {
    "ethereum": "ETH",
    "bsc": "BNB",
    "polygon": "MATIC",
    "solana": "SOL",
    "tron": "TRX",
    "avalanche": "AVAX",
    "arbitrum": "ETH",
    "optimism": "ETH"
}

# Decimals des tokens natifs
NATIVE_DECIMALS = {
    "ethereum": 18,
    "bsc": 18,
    "polygon": 18,
    "solana": 9,
    "tron": 6,
    "avalanche": 18,
    "arbitrum": 18,
    "optimism": 18
}

# URLs des explorateurs par blockchain
EXPLORER_URLS = {
    "ethereum": "https://etherscan.io",
    "bsc": "https://bscscan.com",
    "polygon": "https://polygonscan.com",
    "solana": "https://solscan.io",
    "tron": "https://tronscan.org",
    "avalanche": "https://snowtrace.io",
    "arbitrum": "https://arbiscan.io",
    "optimism": "https://optimistic.etherscan.io"
}

# URLs des RPC par défaut
DEFAULT_RPC_URLS = {
    "ethereum": {
        "mainnet": "https://eth.llamarpc.com",
        "goerli": "https://goerli.gateway.tenderly.co",
        "sepolia": "https://sepolia.gateway.tenderly.co"
    },
    "bsc": {
        "mainnet": "https://bsc-dataseed.binance.org",
        "testnet": "https://data-seed-prebsc-1-s1.binance.org:8545"
    },
    "polygon": {
        "mainnet": "https://polygon-rpc.com",
        "mumbai": "https://rpc-mumbai.maticvigil.com"
    },
    "solana": {
        "mainnet": "https://api.mainnet-beta.solana.com",
        "devnet": "https://api.devnet.solana.com",
        "testnet": "https://api.testnet.solana.com"
    },
    "tron": {
        "mainnet": "https://api.trongrid.io",
        "shasta": "https://api.shasta.trongrid.io",
        "nile": "https://api.nile.trongrid.io"
    },
    "avalanche": {
        "mainnet": "https://api.avax.network/ext/bc/C/rpc",
        "fuji": "https://api.avax-test.network/ext/bc/C/rpc"
    },
    "arbitrum": {
        "mainnet": "https://arb1.arbitrum.io/rpc",
        "goerli": "https://goerli-rollup.arbitrum.io/rpc"
    },
    "optimism": {
        "mainnet": "https://mainnet.optimism.io",
        "goerli": "https://goerli.optimism.io"
    }
}


# ============================================================================
# FACTORY PRINCIPALE
# ============================================================================

class WalletFactory:
    """
    Factory pour créer des instances de wallets et services associés.
    """

    @staticmethod
    def create_wallet(
        blockchain: str,
        user_id: UUID,
        name: str,
        network: BlockchainNetwork,
        private_key: Optional[str] = None,
        mnemonic: Optional[str] = None,
        api_keys: Optional[Dict[str, str]] = None
    ) -> BaseWallet:
        """
        Crée un wallet pour une blockchain spécifique.

        Args:
            blockchain: Blockchain cible
            user_id: ID de l'utilisateur
            name: Nom du wallet
            network: Réseau
            private_key: Clé privée (optionnel)
            mnemonic: Phrase mnémonique (optionnel)
            api_keys: Clés API

        Returns:
            Instance du wallet

        Raises:
            ValueError: Si la blockchain n'est pas supportée
        """
        blockchain_lower = blockchain.lower()

        if blockchain_lower == "ethereum":
            return create_ethereum_wallet(
                user_id=user_id,
                name=name,
                network=network,
                private_key=private_key,
                mnemonic=mnemonic,
                api_keys=api_keys
            )
        elif blockchain_lower == "bsc":
            return create_bsc_wallet(
                user_id=user_id,
                name=name,
                network=network,
                private_key=private_key,
                mnemonic=mnemonic,
                api_keys=api_keys
            )
        elif blockchain_lower == "polygon":
            return create_polygon_wallet(
                user_id=user_id,
                name=name,
                network=network,
                private_key=private_key,
                mnemonic=mnemonic,
                api_keys=api_keys
            )
        elif blockchain_lower == "solana":
            return create_solana_wallet(
                user_id=user_id,
                name=name,
                network=network,
                private_key=private_key,
                mnemonic=mnemonic,
                api_keys=api_keys
            )
        elif blockchain_lower == "tron":
            return create_tron_wallet(
                user_id=user_id,
                name=name,
                network=network,
                private_key=private_key,
                mnemonic=mnemonic,
                api_keys=api_keys
            )
        elif blockchain_lower == "avalanche":
            return create_avalanche_wallet(
                user_id=user_id,
                name=name,
                network=network,
                private_key=private_key,
                mnemonic=mnemonic,
                api_keys=api_keys
            )
        elif blockchain_lower == "arbitrum":
            return create_arbitrum_wallet(
                user_id=user_id,
                name=name,
                network=network,
                private_key=private_key,
                mnemonic=mnemonic,
                api_keys=api_keys
            )
        elif blockchain_lower == "optimism":
            return create_optimism_wallet(
                user_id=user_id,
                name=name,
                network=network,
                private_key=private_key,
                mnemonic=mnemonic,
                api_keys=api_keys
            )
        else:
            raise ValueError(
                f"Blockchain '{blockchain}' non supportée. "
                f"Blockchains supportées: {SUPPORTED_BLOCKCHAINS}"
            )

    @staticmethod
    def create_hd_wallet(
        user_id: UUID,
        name: str,
        blockchain: str,
        network: BlockchainNetwork,
        mnemonic: Optional[str] = None,
        passphrase: str = "",
        standard: HDStandard = HDStandard.BIP44,
        account_index: int = 0,
        strength: int = 256,
        language: str = "english"
    ) -> HDWallet:
        """
        Crée un wallet HD.

        Args:
            user_id: ID de l'utilisateur
            name: Nom du wallet
            blockchain: Blockchain
            network: Réseau
            mnemonic: Phrase mnémonique (optionnel)
            passphrase: Passphrase
            standard: Standard HD
            account_index: Index du compte
            strength: Force de la mnémonique
            language: Langue

        Returns:
            Wallet HD créé
        """
        return HDWalletFactory.create_wallet(
            user_id=user_id,
            name=name,
            blockchain=blockchain,
            network=network,
            mnemonic=mnemonic,
            passphrase=passphrase,
            standard=standard,
            account_index=account_index,
            strength=strength,
            language=language
        )

    @staticmethod
    def create_multi_chain_manager(
        redis_url: str = "redis://localhost:6379/0",
        api_keys: Optional[Dict[str, str]] = None
    ) -> MultiChainWalletManager:
        """
        Crée un gestionnaire multi-chain.

        Args:
            redis_url: URL de connexion Redis
            api_keys: Clés API

        Returns:
            Gestionnaire multi-chain
        """
        return create_multi_chain_manager(
            redis_url=redis_url,
            api_keys=api_keys
        )

    @staticmethod
    def create_manager(
        redis_url: str = "redis://localhost:6379/0",
        api_keys: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> WalletManager:
        """
        Crée un gestionnaire de wallets.

        Args:
            redis_url: URL de connexion Redis
            api_keys: Clés API
            config: Configuration

        Returns:
            Gestionnaire de wallets
        """
        return create_wallet_manager(
            redis_url=redis_url,
            api_keys=api_keys,
            config=config
        )

    @staticmethod
    def create_balance_service(
        redis_url: str = "redis://localhost:6379/0",
        api_keys: Optional[Dict[str, str]] = None
    ) -> WalletBalanceService:
        """
        Crée un service de gestion des soldes.

        Args:
            redis_url: URL de connexion Redis
            api_keys: Clés API

        Returns:
            Service de gestion des soldes
        """
        return create_wallet_balance_service(
            redis_url=redis_url,
            api_keys=api_keys
        )

    @staticmethod
    def create_history_service(
        redis_url: str = "redis://localhost:6379/0",
        api_keys: Optional[Dict[str, str]] = None
    ) -> WalletHistoryService:
        """
        Crée un service d'historique.

        Args:
            redis_url: URL de connexion Redis
            api_keys: Clés API

        Returns:
            Service d'historique
        """
        return create_wallet_history_service(
            redis_url=redis_url,
            api_keys=api_keys
        )

    @staticmethod
    def create_security_service(
        redis_url: str = "redis://localhost:6379/0",
        jwt_secret: Optional[str] = None,
        api_keys: Optional[Dict[str, str]] = None
    ) -> WalletSecurity:
        """
        Crée un service de sécurité.

        Args:
            redis_url: URL de connexion Redis
            jwt_secret: Secret JWT
            api_keys: Clés API

        Returns:
            Service de sécurité
        """
        return create_wallet_security(
            redis_url=redis_url,
            jwt_secret=jwt_secret,
            api_keys=api_keys
        )

    @staticmethod
    def create_signer_service(
        redis_url: str = "redis://localhost:6379/0",
        api_keys: Optional[Dict[str, str]] = None
    ) -> WalletSigner:
        """
        Crée un service de signature.

        Args:
            redis_url: URL de connexion Redis
            api_keys: Clés API

        Returns:
            Service de signature
        """
        return create_wallet_signer(
            redis_url=redis_url,
            api_keys=api_keys
        )

    @staticmethod
    def create_transaction_service(
        redis_url: str = "redis://localhost:6379/0",
        api_keys: Optional[Dict[str, str]] = None
    ) -> WalletTransactionService:
        """
        Crée un service de transactions.

        Args:
            redis_url: URL de connexion Redis
            api_keys: Clés API

        Returns:
            Service de transactions
        """
        return create_wallet_transaction_service(
            redis_url=redis_url,
            api_keys=api_keys
        )

    @staticmethod
    def create_monitor_service(
        redis_url: str = "redis://localhost:6379/0",
        webhook_urls: Optional[Dict[str, str]] = None,
        api_keys: Optional[Dict[str, str]] = None
    ) -> WalletMonitor:
        """
        Crée un service de monitoring.

        Args:
            redis_url: URL de connexion Redis
            webhook_urls: URLs des webhooks
            api_keys: Clés API

        Returns:
            Service de monitoring
        """
        return create_wallet_monitor(
            redis_url=redis_url,
            webhook_urls=webhook_urls,
            api_keys=api_keys
        )

    @staticmethod
    def create_backup_service(
        storage_path: str = "./backups",
        encryption_key: Optional[str] = None,
        redis_url: str = "redis://localhost:6379/0",
        api_keys: Optional[Dict[str, str]] = None
    ) -> WalletBackupService:
        """
        Crée un service de sauvegarde.

        Args:
            storage_path: Chemin de stockage
            encryption_key: Clé de chiffrement
            redis_url: URL de connexion Redis
            api_keys: Clés API

        Returns:
            Service de sauvegarde
        """
        return create_wallet_backup_service(
            storage_path=storage_path,
            encryption_key=encryption_key,
            redis_url=redis_url,
            api_keys=api_keys
        )

    @staticmethod
    def create_analytics_service(
        redis_url: str = "redis://localhost:6379/0",
        api_keys: Optional[Dict[str, str]] = None
    ) -> WalletAnalyticsService:
        """
        Crée un service d'analytics.

        Args:
            redis_url: URL de connexion Redis
            api_keys: Clés API

        Returns:
            Service d'analytics
        """
        return create_wallet_analytics_service(
            redis_url=redis_url,
            api_keys=api_keys
        )


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def get_supported_blockchains() -> List[str]:
    """
    Récupère la liste des blockchains supportées.

    Returns:
        Liste des blockchains
    """
    return SUPPORTED_BLOCKCHAINS.copy()


def get_supported_networks(blockchain: Optional[str] = None) -> Dict[str, List[str]]:
    """
    Récupère les réseaux supportés.

    Args:
        blockchain: Filtrer par blockchain

    Returns:
        Dictionnaire des réseaux par blockchain
    """
    if blockchain:
        return {blockchain: SUPPORTED_NETWORKS.get(blockchain.lower(), [])}
    return SUPPORTED_NETWORKS.copy()


def get_native_token(blockchain: str) -> str:
    """
    Récupère le token natif d'une blockchain.

    Args:
        blockchain: Blockchain

    Returns:
        Symbole du token natif
    """
    return NATIVE_TOKENS.get(blockchain.lower(), "UNKNOWN")


def get_native_decimals(blockchain: str) -> int:
    """
    Récupère les decimals du token natif.

    Args:
        blockchain: Blockchain

    Returns:
        Nombre de decimals
    """
    return NATIVE_DECIMALS.get(blockchain.lower(), 18)


def get_explorer_url(blockchain: str, tx_hash: Optional[str] = None) -> str:
    """
    Récupère l'URL de l'explorateur.

    Args:
        blockchain: Blockchain
        tx_hash: Hash de transaction (optionnel)

    Returns:
        URL de l'explorateur
    """
    base_url = EXPLORER_URLS.get(blockchain.lower(), "https://etherscan.io")
    if tx_hash:
        return f"{base_url}/tx/{tx_hash}"
    return base_url


def get_default_rpc(blockchain: str, network: str) -> str:
    """
    Récupère l'URL RPC par défaut.

    Args:
        blockchain: Blockchain
        network: Réseau

    Returns:
        URL RPC
    """
    rpcs = DEFAULT_RPC_URLS.get(blockchain.lower(), {})
    return rpcs.get(network.lower(), "")


async def check_wallet_health(
    wallet: BaseWallet
) -> Dict[str, Any]:
    """
    Vérifie la santé d'un wallet.

    Args:
        wallet: Wallet à vérifier

    Returns:
        État de santé du wallet
    """
    try:
        return await wallet.get_health()
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def get_wallet_balance_summary(
    wallet: BaseWallet,
    include_tokens: bool = True
) -> Dict[str, Any]:
    """
    Récupère un résumé du solde d'un wallet.

    Args:
        wallet: Wallet
        include_tokens: Inclure les tokens

    Returns:
        Résumé du solde
    """
    try:
        balance = await wallet.get_balance()
        
        result = {
            "wallet_id": str(wallet.config.wallet_id),
            "address": wallet.config.address,
            "blockchain": wallet.config.blockchain,
            "network": wallet.config.network.value if hasattr(wallet.config.network, 'value') else str(wallet.config.network),
            "native": {
                "symbol": NATIVE_TOKENS.get(wallet.config.blockchain, "ETH"),
                "balance": float(balance.native_balance),
                "usd": float(balance.native_balance_usd)
            },
            "total_usd": float(balance.total_balance_usd),
            "timestamp": datetime.now().isoformat()
        }

        if include_tokens:
            result["tokens"] = {
                addr: {
                    "symbol": await wallet.get_token_info(addr) and (await wallet.get_token_info(addr)).symbol or "UNKNOWN",
                    "balance": float(bal),
                    "usd": float(balance.token_balances_usd.get(addr, Decimal("0")))
                }
                for addr, bal in balance.token_balances.items()
            }

        return result

    except Exception as e:
        logger.error(f"Erreur lors de la récupération du résumé du solde: {e}")
        return {"error": str(e)}


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Version
    "__version__",
    "__author__",
    "__copyright__",
    
    # Constantes
    "SUPPORTED_BLOCKCHAINS",
    "SUPPORTED_NETWORKS",
    "NATIVE_TOKENS",
    "NATIVE_DECIMALS",
    "EXPLORER_URLS",
    "DEFAULT_RPC_URLS",
    
    # Enums
    "BlockchainNetwork",
    "WalletStatus",
    "WalletType",
    "TransactionType",
    "TransactionStatus",
    "ChainType",
    "HDStandard",
    "HDCoinType",
    "SecurityLevel",
    "SecurityEventType",
    "TwoFactorMethod",
    "SignatureType",
    "SigningStatus",
    "MonitorEventType",
    "MonitorSeverity",
    "BackupType",
    "BackupStatus",
    "RecoveryMethod",
    "AnalyticsPeriod",
    "RiskMetric",
    "PerformanceMetric",
    "HistoryFilter",
    "HistorySort",
    "BalanceType",
    "PriceSource",
    "TransactionPriority",
    "TransactionCategory",
    
    # Classes de base
    "BaseWallet",
    "WalletConfig",
    "WalletBalance",
    "Transaction",
    "WalletError",
    "WalletNotFoundError",
    "WalletLockedError",
    "InsufficientBalanceError",
    "InvalidAddressError",
    "TransactionError",
    "NetworkError",
    
    # Wallets spécifiques
    "EthereumWallet",
    "BSCWallet",
    "PolygonWallet",
    "SolanaWallet",
    "TronWallet",
    "AvalancheWallet",
    "ArbitrumWallet",
    "OptimismWallet",
    
    # Tokens par blockchain
    "ERC20_TOKENS",
    "BEP20_TOKENS",
    "POLYGON_TOKENS",
    "SPL_TOKENS",
    "TRC20_TOKENS",
    "TRC10_TOKENS",
    "TRON_CONTRACTS",
    "AVAX_TOKENS",
    "ARBITRUM_TOKENS",
    "OPTIMISM_TOKENS",
    
    # DEX Routers
    "UNISWAP_V2_ROUTER",
    "UNISWAP_V2_FACTORY",
    "UNISWAP_V3_ROUTER",
    "UNISWAP_V3_FACTORY",
    "PANCAKESWAP_ROUTER",
    "PANCAKESWAP_FACTORY",
    "QUICKSWAP_ROUTER",
    "QUICKSWAP_FACTORY",
    "TRADERJOE_ROUTER",
    "SOLANA_PROGRAMS",
    
    # Services
    "WalletConfigService",
    "NetworkConfig",
    "TokenConfig",
    "WalletPreferences",
    "SecurityConfig",
    
    "WalletManager",
    "WalletManagerStatus",
    "WalletOperation",
    "WalletOperationResult",
    "WalletHealthCheck",
    
    "WalletBalanceService",
    "TokenPrice",
    "BalanceSnapshot",
    "BalanceAlert",
    
    "WalletHistoryService",
    "TransactionSummary",
    "TransactionGroup",
    "HistoryStats",
    
    "WalletSecurity",
    "SecurityEvent",
    "APIKey",
    "Session",
    
    "WalletSigner",
    "SigningRequest",
    "SignedTransaction",
    
    "WalletTransactionService",
    "TransactionBuilder",
    "TransactionReceipt",
    "TransactionBatch",
    
    "WalletMonitor",
    "MonitorEvent",
    "MonitorAlert",
    "MonitorMetrics",
    
    "WalletBackupService",
    "BackupMetadata",
    "BackupData",
    "BackupRecovery",
    
    "WalletAnalyticsService",
    "PortfolioSnapshot",
    "PortfolioPerformance",
    "WalletInsight",
    "WalletAnalytics",
    
    "HDWallet",
    "HDWalletFactory",
    "HDWalletPath",
    "HDWalletInfo",
    "HDAddress",
    "COIN_TYPE_MAP",
    
    "MultiChainWalletManager",
    "MultiChainWallet",
    "CrossChainTransaction",
    "CHAIN_NETWORKS",
    "CHAIN_TOKENS",
    "BRIDGE_CONFIG",
    
    # Factory
    "WalletFactory",
    
    # Fonctions de création
    "create_ethereum_wallet",
    "create_bsc_wallet",
    "create_polygon_wallet",
    "create_solana_wallet",
    "create_tron_wallet",
    "create_avalanche_wallet",
    "create_arbitrum_wallet",
    "create_optimism_wallet",
    "create_multi_chain_manager",
    "create_wallet_manager",
    "create_wallet_balance_service",
    "create_wallet_history_service",
    "create_wallet_security",
    "create_wallet_signer",
    "create_wallet_transaction_service",
    "create_wallet_monitor",
    "create_wallet_backup_service",
    "create_wallet_analytics_service",
    "create_wallet_config_service",
    
    # Fonctions utilitaires
    "get_supported_blockchains",
    "get_supported_networks",
    "get_native_token",
    "get_native_decimals",
    "get_explorer_url",
    "get_default_rpc",
    "check_wallet_health",
    "get_wallet_balance_summary"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du module wallets."""
    print("=" * 60)
    print("NEXUS AI TRADING - WALLETS MODULE")
    print(f"Version: {__version__}")
    print(f"Copyright: {__copyright__}")
    print("=" * 60)

    print("\n📋 Blockchains supportées:")
    for chain in SUPPORTED_BLOCKCHAINS:
        print(f"   - {chain.upper()}")
        networks = SUPPORTED_NETWORKS.get(chain, [])
        print(f"     Réseaux: {', '.join(networks)}")
        print(f"     Token natif: {NATIVE_TOKENS.get(chain, 'UNKNOWN')}")

    print("\n🔧 URLs des explorateurs:")
    for chain, url in EXPLORER_URLS.items():
        print(f"   - {chain.upper()}: {url}")

    print("\n" + "=" * 60)
    print("Module wallets NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
