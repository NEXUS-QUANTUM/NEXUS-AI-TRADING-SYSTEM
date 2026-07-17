# blockchain/nft/__init__.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module NFT - Gestion des NFTs

Ce module fournit une interface unifiée pour toutes les opérations NFT,
incluant la gestion des collections, le trading sur les marketplaces,
les prêts, le staking, et l'analytique avancée.

Sous-modules:
- base_nft: Classe de base pour les NFTs
- nft_config: Configuration centralisée des NFTs
- nft_manager: Gestionnaire centralisé NFT
- erc721: Gestion des tokens ERC-721
- erc1155: Gestion des tokens ERC-1155
- nft_metadata: Gestion des métadonnées NFT
- nft_marketplace: Gestion des marketplaces
- nft_collection: Gestion des collections
- nft_rarity: Calcul de rareté
- nft_valuation: Évaluation des NFTs
- nft_trading: Trading de NFTs
- nft_lending: Prêts NFT
- nft_staking: Staking NFT
- nft_analytics: Analytique NFT
- nft_whale: Analyse des baleines
- opensea: Intégration OpenSea
- blur: Intégration Blur
- looksrare: Intégration LooksRare
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
from .base_nft import (
    BaseNFT,
    NFTStandard,
    NFTStatus,
    NFTTradeType,
    NFTMetadata,
    NFTData,
    NFTCollection,
    NFTListing,
)

# Configuration
from .nft_config import (
    NFTConfigManager,
    NFTEnvironment,
    NFTMarketplace,
    NFTChain,
    NFTContractConfig,
    NFTCollectionConfig,
    NFTMarketplaceConfig,
    NFTGlobalConfig,
)

# Gestionnaire principal
from .nft_manager import (
    NFTManager,
    NFTManagerStatus,
    NFTManagerState,
    NFTManagerConfig,
)

# Standards
from .erc721 import ERC721Manager
from .erc1155 import ERC1155Manager

# Métadonnées
from .nft_metadata import (
    NFTMetadataManager,
    MetadataStandard,
    StorageProtocol,
    MetadataStatus,
    MetadataSource,
    MetadataTemplate,
)

# Marketplaces
from .nft_marketplace import (
    NFTMarketplaceManager,
    MarketplaceType,
    MarketplaceAction,
    MarketplaceOrder,
)

# Collections
from .nft_collection import (
    NFTCollectionManager,
    CollectionType,
    MintPhase,
    MintStatus,
    CollectionConfig,
    MintPhaseConfig,
    CollectionCreationResult,
)

# Rareté
from .nft_rarity import (
    NFTRarityManager,
    RarityAlgorithm,
    RarityScoreType,
    TraitRarity,
    NFTRarityScore,
    CollectionRarityStats,
)

# Évaluation
from .nft_valuation import (
    NFTValuationManager,
    ValuationMethod,
    ValuationConfidence,
    ComparableSale,
    NFTValuation,
    ValuationFactors,
)

# Trading
from .nft_trading import (
    NFTTradingManager,
    TradingStrategy,
    TradeType,
    TradeStatus,
    TradeOrder,
    TradeResult,
)

# Lending
from .nft_lending import (
    NFTLendingManager,
    NFTLendingProtocol,
    NFTLoanStatus,
    NFTLoanType,
    NFTLoan,
    NFTLendingQuote,
    NFTLendingPosition,
)

# Staking
from .nft_staking import (
    NFTStakingManager,
    NFTStakingProtocol,
    StakingStatus,
    NFTStake,
    StakingPool,
)

# Analytique
from .nft_analytics import (
    NFTAnalytics,
    NFTAnalyticsTimeframe,
    NFTAnalyticsMetric,
    NFTAnalyticsData,
    NFTReport,
    CollectionAnalytics,
    NFTWalletAnalytics,
)

# Baleines
from .nft_whale import (
    NFTWhaleManager,
    WhaleType,
    WhaleActivityType,
    WhaleWallet,
    WhaleActivity,
    WhaleAlert,
)

# Intégrations marketplaces
from .opensea import (
    OpenSeaIntegration,
    OpenSeaAction,
    OpenSeaOrderType,
    OpenSeaStatus,
    OpenSeaOrder,
    OpenSeaBundle,
)

from .blur import (
    BlurIntegration,
    BlurAction,
    BlurOrderType,
    BlurStatus,
    BlurOrder,
    BlurPool,
    BlurLendingPosition,
)

from .looksrare import (
    LooksRareIntegration,
    LooksRareAction,
    LooksRareOrderType,
    LooksRareStatus,
    LooksRareOrder,
    LooksRareStakePosition,
)


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_nft_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Any],
    **kwargs,
) -> NFTManager:
    """
    Crée une instance du gestionnaire NFT

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3 par chaîne
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTManager
    """
    from .nft_manager import NFTManager
    return NFTManager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_erc721_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> ERC721Manager:
    """
    Crée une instance de ERC721Manager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de ERC721Manager
    """
    from .erc721 import ERC721Manager
    return ERC721Manager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_erc1155_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> ERC1155Manager:
    """
    Crée une instance de ERC1155Manager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de ERC1155Manager
    """
    from .erc1155 import ERC1155Manager
    return ERC1155Manager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_nft_metadata_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    **kwargs,
) -> NFTMetadataManager:
    """
    Crée une instance de NFTMetadataManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTMetadataManager
    """
    from .nft_metadata import NFTMetadataManager
    return NFTMetadataManager(
        config=config,
        wallet_manager=wallet_manager,
        **kwargs,
    )


def create_nft_marketplace_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> NFTMarketplaceManager:
    """
    Crée une instance de NFTMarketplaceManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTMarketplaceManager
    """
    from .nft_marketplace import NFTMarketplaceManager
    return NFTMarketplaceManager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_nft_collection_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> NFTCollectionManager:
    """
    Crée une instance de NFTCollectionManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTCollectionManager
    """
    from .nft_collection import NFTCollectionManager
    return NFTCollectionManager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_nft_rarity_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    **kwargs,
) -> NFTRarityManager:
    """
    Crée une instance de NFTRarityManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTRarityManager
    """
    from .nft_rarity import NFTRarityManager
    return NFTRarityManager(
        config=config,
        wallet_manager=wallet_manager,
        **kwargs,
    )


def create_nft_valuation_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    **kwargs,
) -> NFTValuationManager:
    """
    Crée une instance de NFTValuationManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTValuationManager
    """
    from .nft_valuation import NFTValuationManager
    return NFTValuationManager(
        config=config,
        wallet_manager=wallet_manager,
        **kwargs,
    )


def create_nft_trading_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    marketplace_manager: NFTMarketplaceManager,
    **kwargs,
) -> NFTTradingManager:
    """
    Crée une instance de NFTTradingManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        marketplace_manager: Gestionnaire de marketplaces
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTTradingManager
    """
    from .nft_trading import NFTTradingManager
    return NFTTradingManager(
        config=config,
        wallet_manager=wallet_manager,
        marketplace_manager=marketplace_manager,
        **kwargs,
    )


def create_nft_lending_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> NFTLendingManager:
    """
    Crée une instance de NFTLendingManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTLendingManager
    """
    from .nft_lending import NFTLendingManager
    return NFTLendingManager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_nft_staking_manager(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> NFTStakingManager:
    """
    Crée une instance de NFTStakingManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTStakingManager
    """
    from .nft_staking import NFTStakingManager
    return NFTStakingManager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_nft_analytics(
    config: Dict[str, Any],
    nft_instances: Dict[str, Any],
    **kwargs,
) -> NFTAnalytics:
    """
    Crée une instance de NFTAnalytics

    Args:
        config: Configuration
        nft_instances: Instances NFT
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTAnalytics
    """
    from .nft_analytics import NFTAnalytics
    return NFTAnalytics(
        config=config,
        nft_instances=nft_instances,
        **kwargs,
    )


def create_nft_whale_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    **kwargs,
) -> NFTWhaleManager:
    """
    Crée une instance de NFTWhaleManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        **kwargs: Arguments additionnels

    Returns:
        Instance de NFTWhaleManager
    """
    from .nft_whale import NFTWhaleManager
    return NFTWhaleManager(
        config=config,
        wallet_manager=wallet_manager,
        **kwargs,
    )


def create_opensea_integration(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> OpenSeaIntegration:
    """
    Crée une instance de OpenSeaIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de OpenSeaIntegration
    """
    from .opensea import OpenSeaIntegration
    return OpenSeaIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_blur_integration(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> BlurIntegration:
    """
    Crée une instance de BlurIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de BlurIntegration
    """
    from .blur import BlurIntegration
    return BlurIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_looksrare_integration(
    config: Dict[str, Any],
    wallet_manager: MultiChainWallet,
    web3_providers: Dict[str, Web3],
    **kwargs,
) -> LooksRareIntegration:
    """
    Crée une instance de LooksRareIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de LooksRareIntegration
    """
    from .looksrare import LooksRareIntegration
    return LooksRareIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
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
    "BaseNFT",
    "NFTStandard",
    "NFTStatus",
    "NFTTradeType",
    "NFTMetadata",
    "NFTData",
    "NFTCollection",
    "NFTListing",
    
    # Configuration
    "NFTConfigManager",
    "NFTEnvironment",
    "NFTMarketplace",
    "NFTChain",
    "NFTContractConfig",
    "NFTCollectionConfig",
    "NFTMarketplaceConfig",
    "NFTGlobalConfig",
    
    # Gestionnaire principal
    "NFTManager",
    "NFTManagerStatus",
    "NFTManagerState",
    "NFTManagerConfig",
    
    # Standards
    "ERC721Manager",
    "ERC1155Manager",
    
    # Métadonnées
    "NFTMetadataManager",
    "MetadataStandard",
    "StorageProtocol",
    "MetadataStatus",
    "MetadataSource",
    "MetadataTemplate",
    
    # Marketplaces
    "NFTMarketplaceManager",
    "MarketplaceType",
    "MarketplaceAction",
    "MarketplaceOrder",
    
    # Collections
    "NFTCollectionManager",
    "CollectionType",
    "MintPhase",
    "MintStatus",
    "CollectionConfig",
    "MintPhaseConfig",
    "CollectionCreationResult",
    
    # Rareté
    "NFTRarityManager",
    "RarityAlgorithm",
    "RarityScoreType",
    "TraitRarity",
    "NFTRarityScore",
    "CollectionRarityStats",
    
    # Évaluation
    "NFTValuationManager",
    "ValuationMethod",
    "ValuationConfidence",
    "ComparableSale",
    "NFTValuation",
    "ValuationFactors",
    
    # Trading
    "NFTTradingManager",
    "TradingStrategy",
    "TradeType",
    "TradeStatus",
    "TradeOrder",
    "TradeResult",
    
    # Lending
    "NFTLendingManager",
    "NFTLendingProtocol",
    "NFTLoanStatus",
    "NFTLoanType",
    "NFTLoan",
    "NFTLendingQuote",
    "NFTLendingPosition",
    
    # Staking
    "NFTStakingManager",
    "NFTStakingProtocol",
    "StakingStatus",
    "NFTStake",
    "StakingPool",
    
    # Analytique
    "NFTAnalytics",
    "NFTAnalyticsTimeframe",
    "NFTAnalyticsMetric",
    "NFTAnalyticsData",
    "NFTReport",
    "CollectionAnalytics",
    "NFTWalletAnalytics",
    
    # Baleines
    "NFTWhaleManager",
    "WhaleType",
    "WhaleActivityType",
    "WhaleWallet",
    "WhaleActivity",
    "WhaleAlert",
    
    # Intégrations
    "OpenSeaIntegration",
    "OpenSeaAction",
    "OpenSeaOrderType",
    "OpenSeaStatus",
    "OpenSeaOrder",
    "OpenSeaBundle",
    
    "BlurIntegration",
    "BlurAction",
    "BlurOrderType",
    "BlurStatus",
    "BlurOrder",
    "BlurPool",
    "BlurLendingPosition",
    
    "LooksRareIntegration",
    "LooksRareAction",
    "LooksRareOrderType",
    "LooksRareStatus",
    "LooksRareOrder",
    "LooksRareStakePosition",
    
    # Fonctions de création
    "create_nft_manager",
    "create_erc721_manager",
    "create_erc1155_manager",
    "create_nft_metadata_manager",
    "create_nft_marketplace_manager",
    "create_nft_collection_manager",
    "create_nft_rarity_manager",
    "create_nft_valuation_manager",
    "create_nft_trading_manager",
    "create_nft_lending_manager",
    "create_nft_staking_manager",
    "create_nft_analytics",
    "create_nft_whale_manager",
    "create_opensea_integration",
    "create_blur_integration",
    "create_looksrare_integration",
]


# ============================================================
# INITIALISATION DU MODULE
# ============================================================

logger = get_logger(__name__)
logger.info(f"Module NFT chargé (v{__version__})")
