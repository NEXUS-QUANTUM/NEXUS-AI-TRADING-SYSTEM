```python
"""
Blockchain Package
====================

This package provides comprehensive blockchain functionality for the Nexus Trading System.
It includes modules for Web3 interactions, DeFi protocols, NFT operations, staking,
bridge protocols, on-chain analytics, smart contract management, and wallet operations.

Package Structure:
- bridges/: Cross-chain bridge protocols and swap functionality
- defi/: DeFi protocol integrations (Aave, Compound, Uniswap, Curve, etc.)
- nft/: NFT operations (ERC721, ERC1155, marketplaces, analytics)
- nodes/: Blockchain node management (Ethereum, BSC, Polygon, Solana)
- onchain-analysis/: On-chain data analysis and metrics
- smart-contracts/: Smart contract management and deployment
- staking/: Staking protocol integrations
- wallets/: Wallet management (multi-chain support)
- web3/: Core Web3 client and utilities
"""

import warnings
warnings.filterwarnings('ignore')

# Version information
__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Import Web3 subpackage
from .web3 import (
    # Alchemy
    AlchemyClient,
    create_alchemy_client,
    AlchemyNetwork,
    AlchemyWebSocketClient,
    AlchemyNFTClient,
    AlchemyTokenClient,
    AlchemyTransactClient,
    
    # Base Web3
    BaseWeb3Client,
    BaseWeb3Config,
    
    # Etherscan
    EtherscanClient,
    create_etherscan_client,
    
    # Infura
    InfuraClient,
    create_infura_client,
    
    # Web3 Client
    ProviderConfig,
    Web3ClientConfig,
    Web3Client,
    create_web3_client,
    create_web3_client_from_config,
    create_web3_client_from_env,
    get_default_web3_client,
    
    # Web3 Config
    Web3ProviderConfig,
    Web3NetworkConfig,
    Web3Config,
    Web3ConfigLoader,
    get_web3_config,
    create_web3_config,
    DEFAULT_NETWORKS,
    
    # Web3 Contract
    ContractEvent,
    ContractCall,
    ContractTransaction,
    Web3Contract,
    create_contract,
    create_erc20_contract,
    create_erc721_contract,
    create_erc1155_contract,
    
    # Web3 ENS
    ENSRecord,
    ENSReverseRecord,
    ENSClient,
    create_ens_client,
    resolve_ens_name,
    reverse_resolve_address,
    
    # Web3 Event
    EventStatus,
    Web3Event,
    EventFilter,
    EventSubscription,
    Web3EventManager,
    create_event_manager,
    
    # Web3 Gas
    GasPriceInfo,
    GasEstimate,
    GasStrategy,
    GasManager,
    create_gas_manager,
    
    # Web3 Multicall
    MulticallRequest,
    MulticallResult,
    Web3Multicall,
    create_multicall,
    
    # Web3 Price
    PriceSource,
    PriceData,
    AggregatedPrice,
    Web3Price,
    create_price_client,
    
    # Web3 Provider
    ProviderType,
    ProviderStatus,
    Web3ProviderConfig,
    ProviderStats,
    Web3Provider,
    Web3ProviderPool,
    Web3ProviderManager,
    get_provider_manager,
    create_web3_provider,
    create_provider_pool,
    
    # Web3 Token
    TokenInfo,
    TokenBalance,
    TokenAllowance,
    TokenTransfer,
    TokenManager,
    create_token_manager,
    
    # Web3 Transaction
    TransactionStatus,
    TransactionType,
    Transaction,
    TransactionOptions,
    Web3TransactionManager,
    create_transaction_manager,
    
    # Web3 Utils
    Web3Utils,
    get_web3_utils,
    create_web3_utils,
    get_web3_utils_singleton,
    
    # Web3 Wallet
    WalletInfo,
    TransactionInfo,
    Web3Wallet,
    create_wallet,
    create_random_wallet,
    
    # Convenience functions
    get_eth_balance,
    get_token_balance,
    send_eth,
    resolve_ens,
    reverse_resolve,
)

# Import Bridges
try:
    from .bridges import (
        ArbitrumBridge,
        AvalancheBridge,
        BaseBridge,
        BinanceBridge,
        BridgeAnalytics,
        BridgeConfig,
        BridgeEvents,
        BridgeFees,
        BridgeManager,
        BridgeMonitor,
        BridgeSecurity,
        BridgeTransaction,
        BridgeValidator,
        CrossChainSwap,
        EthereumBridge,
        OptimismBridge,
        PolygonBridge,
        SolanaBridge,
        create_bridge_manager,
        get_bridge_manager,
    )
except ImportError as e:
    warnings.warn(f"Bridges module import error: {e}")
    ArbitrumBridge = AvalancheBridge = BaseBridge = BinanceBridge = None
    BridgeAnalytics = BridgeConfig = BridgeEvents = BridgeFees = None
    BridgeManager = BridgeMonitor = BridgeSecurity = BridgeTransaction = None
    BridgeValidator = CrossChainSwap = EthereumBridge = None
    OptimismBridge = PolygonBridge = SolanaBridge = None
    create_bridge_manager = get_bridge_manager = None

# Import DeFi
try:
    from .defi import (
        AaveProtocol,
        BaseProtocol,
        BorrowingManager,
        CompoundProtocol,
        CurveProtocol,
        DeFiAggregator,
        DeFiAnalytics,
        DeFiConfig,
        DeFiManager,
        DeFiRisk,
        FlashLoanManager,
        LendingManager,
        LidoProtocol,
        LiquidityPool,
        MakerDAO,
        PancakeSwap,
        StakingManager,
        UniswapProtocol,
        YieldFarming,
        create_defi_manager,
        get_defi_manager,
    )
except ImportError as e:
    warnings.warn(f"DeFi module import error: {e}")
    AaveProtocol = BaseProtocol = BorrowingManager = None
    CompoundProtocol = CurveProtocol = DeFiAggregator = None
    DeFiAnalytics = DeFiConfig = DeFiManager = DeFiRisk = None
    FlashLoanManager = LendingManager = LidoProtocol = None
    LiquidityPool = MakerDAO = PancakeSwap = None
    StakingManager = UniswapProtocol = YieldFarming = None
    create_defi_manager = get_defi_manager = None

# Import NFT
try:
    from .nft import (
        BaseNFT,
        BlurMarketplace,
        ERC1155Contract,
        ERC721Contract,
        LooksRareMarketplace,
        NFTAnalytics,
        NFTCollection,
        NFTConfig,
        NFTLending,
        NFTManager,
        NFTMarketplace,
        NFTMetadata,
        NFTRarity,
        NFTStaking,
        NFTTrading,
        NFTValuation,
        NFTWhaleTracker,
        OpenSeaMarketplace,
        create_nft_manager,
        get_nft_manager,
    )
except ImportError as e:
    warnings.warn(f"NFT module import error: {e}")
    BaseNFT = BlurMarketplace = ERC1155Contract = None
    ERC721Contract = LooksRareMarketplace = NFTAnalytics = None
    NFTCollection = NFTConfig = NFTLending = NFTManager = None
    NFTMarketplace = NFTMetadata = NFTRarity = NFTStaking = None
    NFTTrading = NFTValuation = NFTWhaleTracker = None
    OpenSeaMarketplace = create_nft_manager = get_nft_manager = None

# Import Nodes
try:
    from .nodes import (
        BaseNode,
        BSCNode,
        EthNode,
        NodeBackup,
        NodeCache,
        NodeConfig,
        NodeHealth,
        NodeManager,
        NodeMetrics,
        NodeMonitor,
        NodePeers,
        NodeRecovery,
        NodeRPC,
        NodeSync,
        NodeWebSocket,
        PolygonNode,
        SolanaNode,
        create_node_manager,
        get_node_manager,
    )
except ImportError as e:
    warnings.warn(f"Nodes module import error: {e}")
    BaseNode = BSCNode = EthNode = None
    NodeBackup = NodeCache = NodeConfig = NodeHealth = None
    NodeManager = NodeMetrics = NodeMonitor = NodePeers = None
    NodeRecovery = NodeRPC = NodeSync = NodeWebSocket = None
    PolygonNode = SolanaNode = None
    create_node_manager = get_node_manager = None

# Import On-Chain Analysis
try:
    from .onchain_analysis import (
        AnalysisConfig,
        BaseAnalyzer,
        DeFiAnalyzer,
        ExchangeFlowAnalyzer,
        GasAnalyzer,
        HolderAnalyzer,
        MempoolAnalyzer,
        NFTAnalyzer,
        OnChainAlerts,
        OnChainAnalyzer,
        OnChainMetrics,
        OnChainSignals,
        SmartMoneyTracker,
        TokenAnalyzer,
        VolumeAnalyzer,
        WhaleTracker,
        create_onchain_analyzer,
        get_onchain_analyzer,
    )
except ImportError as e:
    warnings.warn(f"On-Chain Analysis module import error: {e}")
    AnalysisConfig = BaseAnalyzer = DeFiAnalyzer = None
    ExchangeFlowAnalyzer = GasAnalyzer = HolderAnalyzer = None
    MempoolAnalyzer = NFTAnalyzer = OnChainAlerts = None
    OnChainAnalyzer = OnChainMetrics = OnChainSignals = None
    SmartMoneyTracker = TokenAnalyzer = VolumeAnalyzer = None
    WhaleTracker = create_onchain_analyzer = get_onchain_analyzer = None

# Import Smart Contracts
try:
    from .smart_contracts import (
        AaveContract,
        BaseContract,
        CompoundContract,
        ContractABI,
        ContractAudit,
        ContractBytecode,
        ContractCompiler,
        ContractConfig,
        ContractDeployer,
        ContractInterceptor,
        ContractManager,
        ContractUpgrade,
        ContractVerifier,
        ERC1155Contract as SmartERC1155Contract,
        ERC20Contract,
        ERC721Contract as SmartERC721Contract,
        PancakeContract,
        UniswapContract,
        create_contract_manager,
        get_contract_manager,
    )
except ImportError as e:
    warnings.warn(f"Smart Contracts module import error: {e}")
    AaveContract = BaseContract = CompoundContract = None
    ContractABI = ContractAudit = ContractBytecode = None
    ContractCompiler = ContractConfig = ContractDeployer = None
    ContractInterceptor = ContractManager = ContractUpgrade = None
    ContractVerifier = SmartERC1155Contract = ERC20Contract = None
    SmartERC721Contract = PancakeContract = UniswapContract = None
    create_contract_manager = get_contract_manager = None

# Import Staking
try:
    from .staking import (
        AtomStaking,
        BaseStaking,
        BNBStaking,
        DOTStaking,
        ETHStaking,
        LiquidStaking,
        SOLStaking,
        StakingAnalytics,
        StakingAPY,
        StakingConfig,
        StakingManager,
        StakingPool,
        StakingRewards,
        StakingRisk,
        StakingValidator,
        create_staking_manager,
        get_staking_manager,
    )
except ImportError as e:
    warnings.warn(f"Staking module import error: {e}")
    AtomStaking = BaseStaking = BNBStaking = None
    DOTStaking = ETHStaking = LiquidStaking = None
    SOLStaking = StakingAnalytics = StakingAPY = None
    StakingConfig = StakingManager = StakingPool = None
    StakingRewards = StakingRisk = StakingValidator = None
    create_staking_manager = get_staking_manager = None

# Import Wallets
try:
    from .wallets import (
        BaseWallet,
        BSCWallet,
        EthereumWallet,
        MultiChainWallet,
        PolygonWallet,
        SolanaWallet,
        TronWallet,
        WalletAnalytics,
        WalletBackup,
        WalletBalance,
        WalletConfig,
        WalletHD,
        WalletHistory,
        WalletManager,
        WalletMonitor,
        WalletSecurity,
        WalletSigner,
        WalletTransaction,
        create_wallet_manager,
        get_wallet_manager,
    )
except ImportError as e:
    warnings.warn(f"Wallets module import error: {e}")
    BaseWallet = BSCWallet = EthereumWallet = None
    MultiChainWallet = PolygonWallet = SolanaWallet = None
    TronWallet = WalletAnalytics = WalletBackup = None
    WalletBalance = WalletConfig = WalletHD = WalletHistory = None
    WalletManager = WalletMonitor = WalletSecurity = None
    WalletSigner = WalletTransaction = None
    create_wallet_manager = get_wallet_manager = None


# Convenience functions for blockchain operations
def get_blockchain_manager(chain: str = "ethereum") -> Optional[Any]:
    """
    Get the appropriate blockchain manager for a chain.
    
    Args:
        chain: Chain name ('ethereum', 'bsc', 'polygon', etc.)
        
    Returns:
        Blockchain manager instance or None.
    """
    if chain == "ethereum":
        return get_default_web3_client()
    elif chain == "bsc":
        try:
            from .nodes import get_node_manager
            return get_node_manager().get_node("bsc")
        except:
            return None
    elif chain == "polygon":
        try:
            from .nodes import get_node_manager
            return get_node_manager().get_node("polygon")
        except:
            return None
    elif chain == "solana":
        try:
            from .nodes import get_node_manager
            return get_node_manager().get_node("solana")
        except:
            return None
    else:
        return None


def get_chain_id(chain: str) -> int:
    """
    Get the chain ID for a chain name.
    
    Args:
        chain: Chain name.
        
    Returns:
        Chain ID.
    """
    chain_ids = {
        'ethereum': 1,
        'goerli': 5,
        'sepolia': 11155111,
        'polygon': 137,
        'bsc': 56,
        'arbitrum': 42161,
        'optimism': 10,
        'avalanche': 43114,
        'fantom': 250,
        'solana': 0,  # Solana uses different ID system
    }
    return chain_ids.get(chain.lower(), 1)


def is_supported_chain(chain: str) -> bool:
    """
    Check if a chain is supported.
    
    Args:
        chain: Chain name.
        
    Returns:
        True if supported, False otherwise.
    """
    supported = ['ethereum', 'goerli', 'sepolia', 'polygon', 'bsc', 
                 'arbitrum', 'optimism', 'avalanche', 'fantom', 'solana']
    return chain.lower() in supported


def get_supported_chains() -> List[str]:
    """
    Get list of supported chains.
    
    Returns:
        List of chain names.
    """
    return ['ethereum', 'goerli', 'sepolia', 'polygon', 'bsc', 
            'arbitrum', 'optimism', 'avalanche', 'fantom', 'solana']


# Blockchain utility singleton
_blockchain_utils = None


def get_blockchain_utils(chain: str = "ethereum") -> Web3Utils:
    """
    Get blockchain utilities for a specific chain.
    
    Args:
        chain: Chain name.
        
    Returns:
        Web3Utils instance.
    """
    global _blockchain_utils
    if _blockchain_utils is None:
        client = get_blockchain_manager(chain)
        if client:
            _blockchain_utils = create_web3_utils(client)
    return _blockchain_utils


# Export all public classes and functions
__all__ = [
    # Version info
    '__version__',
    '__author__',
    '__copyright__',
    
    # Web3 (all exports from web3 package)
    'AlchemyClient',
    'create_alchemy_client',
    'AlchemyNetwork',
    'AlchemyWebSocketClient',
    'AlchemyNFTClient',
    'AlchemyTokenClient',
    'AlchemyTransactClient',
    'BaseWeb3Client',
    'BaseWeb3Config',
    'EtherscanClient',
    'create_etherscan_client',
    'InfuraClient',
    'create_infura_client',
    'ProviderConfig',
    'Web3ClientConfig',
    'Web3Client',
    'create_web3_client',
    'create_web3_client_from_config',
    'create_web3_client_from_env',
    'get_default_web3_client',
    'Web3ProviderConfig',
    'Web3NetworkConfig',
    'Web3Config',
    'Web3ConfigLoader',
    'get_web3_config',
    'create_web3_config',
    'DEFAULT_NETWORKS',
    'ContractEvent',
    'ContractCall',
    'ContractTransaction',
    'Web3Contract',
    'create_contract',
    'create_erc20_contract',
    'create_erc721_contract',
    'create_erc1155_contract',
    'ENSRecord',
    'ENSReverseRecord',
    'ENSClient',
    'create_ens_client',
    'resolve_ens_name',
    'reverse_resolve_address',
    'EventStatus',
    'Web3Event',
    'EventFilter',
    'EventSubscription',
    'Web3EventManager',
    'create_event_manager',
    'GasPriceInfo',
    'GasEstimate',
    'GasStrategy',
    'GasManager',
    'create_gas_manager',
    'MulticallRequest',
    'MulticallResult',
    'Web3Multicall',
    'create_multicall',
    'PriceSource',
    'PriceData',
    'AggregatedPrice',
    'Web3Price',
    'create_price_client',
    'ProviderType',
    'ProviderStatus',
    'Web3ProviderConfig',
    'ProviderStats',
    'Web3Provider',
    'Web3ProviderPool',
    'Web3ProviderManager',
    'get_provider_manager',
    'create_web3_provider',
    'create_provider_pool',
    'TokenInfo',
    'TokenBalance',
    'TokenAllowance',
    'TokenTransfer',
    'TokenManager',
    'create_token_manager',
    'TransactionStatus',
    'TransactionType',
    'Transaction',
    'TransactionOptions',
    'Web3TransactionManager',
    'create_transaction_manager',
    'Web3Utils',
    'get_web3_utils',
    'create_web3_utils',
    'get_web3_utils_singleton',
    'WalletInfo',
    'TransactionInfo',
    'Web3Wallet',
    'create_wallet',
    'create_random_wallet',
    'get_eth_balance',
    'get_token_balance',
    'send_eth',
    'resolve_ens',
    'reverse_resolve',
    
    # Bridges (if available)
    'ArbitrumBridge',
    'AvalancheBridge',
    'BaseBridge',
    'BinanceBridge',
    'BridgeAnalytics',
    'BridgeConfig',
    'BridgeEvents',
    'BridgeFees',
    'BridgeManager',
    'BridgeMonitor',
    'BridgeSecurity',
    'BridgeTransaction',
    'BridgeValidator',
    'CrossChainSwap',
    'EthereumBridge',
    'OptimismBridge',
    'PolygonBridge',
    'SolanaBridge',
    'create_bridge_manager',
    'get_bridge_manager',
    
    # DeFi (if available)
    'AaveProtocol',
    'BaseProtocol',
    'BorrowingManager',
    'CompoundProtocol',
    'CurveProtocol',
    'DeFiAggregator',
    'DeFiAnalytics',
    'DeFiConfig',
    'DeFiManager',
    'DeFiRisk',
    'FlashLoanManager',
    'LendingManager',
    'LidoProtocol',
    'LiquidityPool',
    'MakerDAO',
    'PancakeSwap',
    'StakingManager',
    'UniswapProtocol',
    'YieldFarming',
    'create_defi_manager',
    'get_defi_manager',
    
    # NFT (if available)
    'BaseNFT',
    'BlurMarketplace',
    'ERC1155Contract',
    'ERC721Contract',
    'LooksRareMarketplace',
    'NFTAnalytics',
    'NFTCollection',
    'NFTConfig',
    'NFTLending',
    'NFTManager',
    'NFTMarketplace',
    'NFTMetadata',
    'NFTRarity',
    'NFTStaking',
    'NFTTrading',
    'NFTValuation',
    'NFTWhaleTracker',
    'OpenSeaMarketplace',
    'create_nft_manager',
    'get_nft_manager',
    
    # Nodes (if available)
    'BaseNode',
    'BSCNode',
    'EthNode',
    'NodeBackup',
    'NodeCache',
    'NodeConfig',
    'NodeHealth',
    'NodeManager',
    'NodeMetrics',
    'NodeMonitor',
    'NodePeers',
    'NodeRecovery',
    'NodeRPC',
    'NodeSync',
    'NodeWebSocket',
    'PolygonNode',
    'SolanaNode',
    'create_node_manager',
    'get_node_manager',
    
    # On-Chain Analysis (if available)
    'AnalysisConfig',
    'BaseAnalyzer',
    'DeFiAnalyzer',
    'ExchangeFlowAnalyzer',
    'GasAnalyzer',
    'HolderAnalyzer',
    'MempoolAnalyzer',
    'NFTAnalyzer',
    'OnChainAlerts',
    'OnChainAnalyzer',
    'OnChainMetrics',
    'OnChainSignals',
    'SmartMoneyTracker',
    'TokenAnalyzer',
    'VolumeAnalyzer',
    'WhaleTracker',
    'create_onchain_analyzer',
    'get_onchain_analyzer',
    
    # Smart Contracts (if available)
    'AaveContract',
    'BaseContract',
    'CompoundContract',
    'ContractABI',
    'ContractAudit',
    'ContractBytecode',
    'ContractCompiler',
    'ContractConfig',
    'ContractDeployer',
    'ContractInterceptor',
    'ContractManager',
    'ContractUpgrade',
    'ContractVerifier',
    'SmartERC1155Contract',
    'ERC20Contract',
    'SmartERC721Contract',
    'PancakeContract',
    'UniswapContract',
    'create_contract_manager',
    'get_contract_manager',
    
    # Staking (if available)
    'AtomStaking',
    'BaseStaking',
    'BNBStaking',
    'DOTStaking',
    'ETHStaking',
    'LiquidStaking',
    'SOLStaking',
    'StakingAnalytics',
    'StakingAPY',
    'StakingConfig',
    'StakingManager',
    'StakingPool',
    'StakingRewards',
    'StakingRisk',
    'StakingValidator',
    'create_staking_manager',
    'get_staking_manager',
    
    # Wallets (if available)
    'BaseWallet',
    'BSCWallet',
    'EthereumWallet',
    'MultiChainWallet',
    'PolygonWallet',
    'SolanaWallet',
    'TronWallet',
    'WalletAnalytics',
    'WalletBackup',
    'WalletBalance',
    'WalletConfig',
    'WalletHD',
    'WalletHistory',
    'WalletManager',
    'WalletMonitor',
    'WalletSecurity',
    'WalletSigner',
    'WalletTransaction',
    'create_wallet_manager',
    'get_wallet_manager',
    
    # Convenience functions
    'get_blockchain_manager',
    'get_chain_id',
    'is_supported_chain',
    'get_supported_chains',
    'get_blockchain_utils',
]

# Setup logging
import logging
logger = logging.getLogger(__name__)
logger.info(f"Blockchain package version {__version__} initialized")
```
