# blockchain/defi/__init__.py
# NEXUS AI TRADING SYSTEM - Version Avancée
# Copyright © 2026 NEXUS QUANTUM LTD
# Tous droits réservés

"""
Module DeFi - Intégration des Protocoles DeFi

Ce module fournit une interface unifiée pour tous les protocoles DeFi,
permettant l'interaction avec Aave, Compound, Curve, Uniswap, et bien d'autres,
avec des mécanismes de sécurité et d'optimisation avancés.

Sous-modules:
- base_protocol: Classe de base pour tous les protocoles DeFi
- defi_config: Configuration centralisée des protocoles
- defi_manager: Gestionnaire centralisé DeFi
- defi_aggregator: Agrégateur DeFi multi-protocoles
- defi_analytics: Analytique avancée des protocoles
- defi_risk: Gestion des risques DeFi
- aave: Intégration Aave V2/V3
- compound: Intégration Compound V2/V3
- curve: Intégration Curve
- uniswap: Intégration Uniswap V2/V3
- pancake_swap: Intégration PancakeSwap
- lido: Intégration Lido Finance
- maker_dao: Intégration MakerDAO
- lending: Gestion des prêts
- borrowing: Gestion des emprunts
- staking: Gestion du staking
- yield_farming: Gestion du yield farming
- liquidity_pool: Gestion des pools de liquidité
- flash_loan: Gestion des flash loans
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
from .base_protocol import (
    BaseProtocol,
    ProtocolType,
    ProtocolStatus,
    PositionType,
    RiskLevel,
    Position,
    YieldData,
    ProtocolConfig,
)

# Configuration
from .defi_config import (
    DeFiConfigManager,
    DeFiProtocol,
    DeFiChain,
    Environment,
    ContractConfig,
    TokenConfig,
    ProtocolConfig as DeFiProtocolConfig,
)

# Gestionnaire principal
from .defi_manager import (
    DeFiManager,
    DeFiManagerStatus,
    DeFiManagerState,
    DeFiManagerConfig,
)

# Agrégateur
from .defi_aggregator import (
    DeFiAggregator,
    DeFiStrategy,
    AllocationStrategy,
    DeFiStatus,
    DeFiStrategyConfig,
    DeFiPortfolio,
    DeFiPosition,
)

# Analytique
from .defi_analytics import (
    DeFiAnalytics,
    AnalyticsTimeframe,
    AnalyticsMetric,
    DeFiAnalyticsData,
    DeFiReport,
)

# Gestion des risques
from .defi_risk import (
    DeFiRiskManager,
    RiskCategory,
    RiskEventType,
    RiskSeverity,
    RiskMetric,
    RiskEvent,
    RiskProfile,
)

# Protocoles spécifiques
from .aave import (
    AaveIntegration,
    AaveProtocol,
    AaveChain,
    AaveAction,
    AaveInterestRateMode,
    AaveReserveData,
    AaveUserPosition,
)

from .compound import (
    CompoundIntegration,
    CompoundVersion,
    CompoundChain,
    CompoundAction,
    CompoundReserveData,
    CompoundPosition,
)

from .curve import (
    CurveIntegration,
    CurveVersion,
    CurvePoolType,
    CurveAction,
    CurvePoolData,
    CurvePosition,
)

from .uniswap import (
    UniswapIntegration,
    UniswapVersion,
    UniswapChain,
    UniswapAction,
    UniswapPool,
    UniswapPosition,
)

from .pancake_swap import (
    PancakeSwapIntegration,
    PancakeAction,
    PancakePoolType,
    PancakePool,
    PancakePosition,
)

from .lido import (
    LidoIntegration,
    LidoChain,
    LidoAction,
    LidoPosition,
)

from .maker_dao import (
    MakerDAOIntegration,
    MakerAction,
    MakerPositionType,
    MakerVaultData,
    MakerPosition,
)

# Gestion des prêts
from .lending import (
    LendingManager,
    LendingProtocol,
    LendingStatus,
    LendingType,
    LendingPosition,
    LendingQuote,
)

# Gestion des emprunts
from .borrowing import (
    BorrowingManager,
    BorrowProtocol,
    InterestRateMode,
    BorrowStatus,
    BorrowPosition,
    BorrowQuote,
)

# Gestion du staking
from .staking import (
    StakingManager,
    StakingProtocol,
    StakingType,
    StakingPosition,
)

# Gestion du yield farming
from .yield_farming import (
    YieldFarmingManager,
    FarmingProtocol,
    FarmingStrategy,
    FarmingStatus,
    FarmingPosition,
)

# Gestion des pools de liquidité
from .liquidity_pool import (
    LiquidityPoolManager,
    LiquidityPoolProtocol,
    PoolType,
    LiquidityPoolData,
    LiquidityPosition,
)

# Gestion des flash loans
from .flash_loan import (
    FlashLoanManager,
    FlashLoanProtocol,
    FlashLoanAction,
    FlashLoanStatus,
    FlashLoanConfig,
    FlashLoanResult,
)


# ============================================================
# FONCTIONS DE CONVENIENCE
# ============================================================

def create_defi_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    web3_providers: Dict[str, Any],
    **kwargs,
) -> DeFiManager:
    """
    Crée une instance du gestionnaire DeFi

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3 par chaîne
        **kwargs: Arguments additionnels

    Returns:
        Instance de DeFiManager
    """
    from .defi_manager import DeFiManager
    return DeFiManager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_defi_aggregator(
    config: Dict[str, Any],
    wallet_manager: Any,
    **kwargs,
) -> DeFiAggregator:
    """
    Crée une instance de DeFiAggregator

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        **kwargs: Arguments additionnels

    Returns:
        Instance de DeFiAggregator
    """
    from .defi_aggregator import DeFiAggregator
    return DeFiAggregator(
        config=config,
        wallet_manager=wallet_manager,
        **kwargs,
    )


def create_defi_analytics(
    config: Dict[str, Any],
    **kwargs,
) -> DeFiAnalytics:
    """
    Crée une instance de DeFiAnalytics

    Args:
        config: Configuration
        **kwargs: Arguments additionnels

    Returns:
        Instance de DeFiAnalytics
    """
    from .defi_analytics import DeFiAnalytics
    return DeFiAnalytics(
        config=config,
        **kwargs,
    )


def create_defi_risk_manager(
    config: Dict[str, Any],
    **kwargs,
) -> DeFiRiskManager:
    """
    Crée une instance de DeFiRiskManager

    Args:
        config: Configuration
        **kwargs: Arguments additionnels

    Returns:
        Instance de DeFiRiskManager
    """
    from .defi_risk import DeFiRiskManager
    return DeFiRiskManager(
        config=config,
        **kwargs,
    )


def create_aave_integration(
    config: Dict[str, Any],
    wallet_manager: Any,
    web3_providers: Dict[str, Any],
    **kwargs,
) -> AaveIntegration:
    """
    Crée une instance de AaveIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de AaveIntegration
    """
    from .aave import AaveIntegration
    return AaveIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_compound_integration(
    config: Dict[str, Any],
    wallet_manager: Any,
    web3_providers: Dict[str, Any],
    **kwargs,
) -> CompoundIntegration:
    """
    Crée une instance de CompoundIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de CompoundIntegration
    """
    from .compound import CompoundIntegration
    return CompoundIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_curve_integration(
    config: Dict[str, Any],
    wallet_manager: Any,
    web3_providers: Dict[str, Any],
    **kwargs,
) -> CurveIntegration:
    """
    Crée une instance de CurveIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de CurveIntegration
    """
    from .curve import CurveIntegration
    return CurveIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_uniswap_integration(
    config: Dict[str, Any],
    wallet_manager: Any,
    web3_providers: Dict[str, Any],
    **kwargs,
) -> UniswapIntegration:
    """
    Crée une instance de UniswapIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de UniswapIntegration
    """
    from .uniswap import UniswapIntegration
    return UniswapIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_pancake_integration(
    config: Dict[str, Any],
    wallet_manager: Any,
    bsc_provider: Any,
    **kwargs,
) -> PancakeSwapIntegration:
    """
    Crée une instance de PancakeSwapIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        bsc_provider: Provider Web3 BSC
        **kwargs: Arguments additionnels

    Returns:
        Instance de PancakeSwapIntegration
    """
    from .pancake_swap import PancakeSwapIntegration
    return PancakeSwapIntegration(
        config=config,
        wallet_manager=wallet_manager,
        bsc_provider=bsc_provider,
        **kwargs,
    )


def create_lido_integration(
    config: Dict[str, Any],
    wallet_manager: Any,
    web3_providers: Dict[str, Any],
    **kwargs,
) -> LidoIntegration:
    """
    Crée une instance de LidoIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de LidoIntegration
    """
    from .lido import LidoIntegration
    return LidoIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_maker_integration(
    config: Dict[str, Any],
    wallet_manager: Any,
    web3_providers: Dict[str, Any],
    **kwargs,
) -> MakerDAOIntegration:
    """
    Crée une instance de MakerDAOIntegration

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de MakerDAOIntegration
    """
    from .maker_dao import MakerDAOIntegration
    return MakerDAOIntegration(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_lending_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    protocol_instances: Dict[str, Any],
    **kwargs,
) -> LendingManager:
    """
    Crée une instance de LendingManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        protocol_instances: Instances des protocoles
        **kwargs: Arguments additionnels

    Returns:
        Instance de LendingManager
    """
    from .lending import LendingManager
    return LendingManager(
        config=config,
        wallet_manager=wallet_manager,
        protocol_instances=protocol_instances,
        **kwargs,
    )


def create_borrowing_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    protocol_instances: Dict[str, Any],
    **kwargs,
) -> BorrowingManager:
    """
    Crée une instance de BorrowingManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        protocol_instances: Instances des protocoles
        **kwargs: Arguments additionnels

    Returns:
        Instance de BorrowingManager
    """
    from .borrowing import BorrowingManager
    return BorrowingManager(
        config=config,
        wallet_manager=wallet_manager,
        protocol_instances=protocol_instances,
        **kwargs,
    )


def create_staking_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    protocol_instances: Dict[str, Any],
    **kwargs,
) -> StakingManager:
    """
    Crée une instance de StakingManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        protocol_instances: Instances des protocoles
        **kwargs: Arguments additionnels

    Returns:
        Instance de StakingManager
    """
    from .staking import StakingManager
    return StakingManager(
        config=config,
        wallet_manager=wallet_manager,
        protocol_instances=protocol_instances,
        **kwargs,
    )


def create_yield_farming_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    protocol_instances: Dict[str, Any],
    **kwargs,
) -> YieldFarmingManager:
    """
    Crée une instance de YieldFarmingManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        protocol_instances: Instances des protocoles
        **kwargs: Arguments additionnels

    Returns:
        Instance de YieldFarmingManager
    """
    from .yield_farming import YieldFarmingManager
    return YieldFarmingManager(
        config=config,
        wallet_manager=wallet_manager,
        protocol_instances=protocol_instances,
        **kwargs,
    )


def create_liquidity_pool_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    web3_providers: Dict[str, Any],
    **kwargs,
) -> LiquidityPoolManager:
    """
    Crée une instance de LiquidityPoolManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de LiquidityPoolManager
    """
    from .liquidity_pool import LiquidityPoolManager
    return LiquidityPoolManager(
        config=config,
        wallet_manager=wallet_manager,
        web3_providers=web3_providers,
        **kwargs,
    )


def create_flash_loan_manager(
    config: Dict[str, Any],
    wallet_manager: Any,
    web3_providers: Dict[str, Any],
    **kwargs,
) -> FlashLoanManager:
    """
    Crée une instance de FlashLoanManager

    Args:
        config: Configuration
        wallet_manager: Gestionnaire de wallets
        web3_providers: Providers Web3
        **kwargs: Arguments additionnels

    Returns:
        Instance de FlashLoanManager
    """
    from .flash_loan import FlashLoanManager
    return FlashLoanManager(
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
    
    # Classes de base
    "BaseProtocol",
    "ProtocolType",
    "ProtocolStatus",
    "PositionType",
    "RiskLevel",
    "Position",
    "YieldData",
    "ProtocolConfig",
    
    # Configuration
    "DeFiConfigManager",
    "DeFiProtocol",
    "DeFiChain",
    "Environment",
    "ContractConfig",
    "TokenConfig",
    "DeFiProtocolConfig",
    
    # Gestionnaire principal
    "DeFiManager",
    "DeFiManagerStatus",
    "DeFiManagerState",
    "DeFiManagerConfig",
    
    # Agrégateur
    "DeFiAggregator",
    "DeFiStrategy",
    "AllocationStrategy",
    "DeFiStatus",
    "DeFiStrategyConfig",
    "DeFiPortfolio",
    "DeFiPosition",
    
    # Analytique
    "DeFiAnalytics",
    "AnalyticsTimeframe",
    "AnalyticsMetric",
    "DeFiAnalyticsData",
    "DeFiReport",
    
    # Gestion des risques
    "DeFiRiskManager",
    "RiskCategory",
    "RiskEventType",
    "RiskSeverity",
    "RiskMetric",
    "RiskEvent",
    "RiskProfile",
    
    # Aave
    "AaveIntegration",
    "AaveProtocol",
    "AaveChain",
    "AaveAction",
    "AaveInterestRateMode",
    "AaveReserveData",
    "AaveUserPosition",
    
    # Compound
    "CompoundIntegration",
    "CompoundVersion",
    "CompoundChain",
    "CompoundAction",
    "CompoundReserveData",
    "CompoundPosition",
    
    # Curve
    "CurveIntegration",
    "CurveVersion",
    "CurvePoolType",
    "CurveAction",
    "CurvePoolData",
    "CurvePosition",
    
    # Uniswap
    "UniswapIntegration",
    "UniswapVersion",
    "UniswapChain",
    "UniswapAction",
    "UniswapPool",
    "UniswapPosition",
    
    # PancakeSwap
    "PancakeSwapIntegration",
    "PancakeAction",
    "PancakePoolType",
    "PancakePool",
    "PancakePosition",
    
    # Lido
    "LidoIntegration",
    "LidoChain",
    "LidoAction",
    "LidoPosition",
    
    # MakerDAO
    "MakerDAOIntegration",
    "MakerAction",
    "MakerPositionType",
    "MakerVaultData",
    "MakerPosition",
    
    # Lending
    "LendingManager",
    "LendingProtocol",
    "LendingStatus",
    "LendingType",
    "LendingPosition",
    "LendingQuote",
    
    # Borrowing
    "BorrowingManager",
    "BorrowProtocol",
    "InterestRateMode",
    "BorrowStatus",
    "BorrowPosition",
    "BorrowQuote",
    
    # Staking
    "StakingManager",
    "StakingProtocol",
    "StakingType",
    "StakingPosition",
    
    # Yield Farming
    "YieldFarmingManager",
    "FarmingProtocol",
    "FarmingStrategy",
    "FarmingStatus",
    "FarmingPosition",
    
    # Liquidity Pool
    "LiquidityPoolManager",
    "LiquidityPoolProtocol",
    "PoolType",
    "LiquidityPoolData",
    "LiquidityPosition",
    
    # Flash Loan
    "FlashLoanManager",
    "FlashLoanProtocol",
    "FlashLoanAction",
    "FlashLoanStatus",
    "FlashLoanConfig",
    "FlashLoanResult",
    
    # Fonctions de création
    "create_defi_manager",
    "create_defi_aggregator",
    "create_defi_analytics",
    "create_defi_risk_manager",
    "create_aave_integration",
    "create_compound_integration",
    "create_curve_integration",
    "create_uniswap_integration",
    "create_pancake_integration",
    "create_lido_integration",
    "create_maker_integration",
    "create_lending_manager",
    "create_borrowing_manager",
    "create_staking_manager",
    "create_yield_farming_manager",
    "create_liquidity_pool_manager",
    "create_flash_loan_manager",
]


# ============================================================
# INITIALISATION DU MODULE
# ============================================================

logger = get_logger(__name__)
logger.info(f"Module DeFi chargé (v{__version__})")
