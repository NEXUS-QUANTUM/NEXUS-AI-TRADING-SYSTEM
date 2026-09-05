"""
Web3 Blockchain Package
========================

This package provides comprehensive Web3 functionality for interacting with
Ethereum and EVM-compatible blockchains. It includes clients for various
providers (Alchemy, Infura, Etherscan), contract interactions, token management,
ENS resolution, event handling, gas optimization, multicall batching, price feeds,
transaction management, and wallet operations.

Key Features:
- Multiple provider support (Alchemy, Infura, Etherscan)
- Smart contract interaction (ERC20, ERC721, ERC1155)
- Token management and portfolio tracking
- ENS name resolution
- Event monitoring and real-time updates
- Gas price optimization (EIP-1559 support)
- Multicall batching for efficient RPC usage
- Price fetching from Chainlink oracles and DEXes
- Transaction management with nonce handling
- Full wallet implementation with key management
- Comprehensive Web3 utilities

Package Structure:
- alchemy_client.py: Alchemy API client
- base_web3.py: Base Web3 client class
- etherscan_client.py: Etherscan API client
- infura_client.py: Infura API client
- web3_client.py: Core Web3 client
- web3_config.py: Configuration management
- web3_contract.py: Smart contract interaction
- web3_ens.py: ENS name resolution
- web3_event.py: Event monitoring
- web3_gas.py: Gas price management
- web3_multicall.py: Multicall batching
- web3_price.py: Price fetching
- web3_provider.py: Provider management
- web3_token.py: Token operations
- web3_transaction.py: Transaction management
- web3_utils.py: Utility functions
- web3_wallet.py: Wallet implementation
"""

import warnings
warnings.filterwarnings('ignore')

# Version information
__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Import all modules for easy access
from .alchemy_client import (
    AlchemyClient,
    create_alchemy_client,
    AlchemyNetwork,
    AlchemyWebSocketClient,
    AlchemyNFTClient,
    AlchemyTokenClient,
    AlchemyTransactClient,
)

from .base_web3 import (
    BaseWeb3Client,
    BaseWeb3Config,
)

from .etherscan_client import (
    EtherscanClient,
    create_etherscan_client,
)

from .infura_client import (
    InfuraClient,
    create_infura_client,
)

from .web3_client import (
    ProviderConfig,
    Web3ClientConfig,
    Web3Client,
    create_web3_client,
)

from .web3_config import (
    Web3ProviderConfig,
    Web3NetworkConfig,
    Web3Config,
    Web3ConfigLoader,
    get_web3_config,
    create_web3_config,
    DEFAULT_NETWORKS,
)

from .web3_contract import (
    ContractEvent,
    ContractCall,
    ContractTransaction,
    Web3Contract,
    create_contract,
    create_erc20_contract,
    create_erc721_contract,
    create_erc1155_contract,
)

from .web3_ens import (
    ENSRecord,
    ENSReverseRecord,
    ENSClient,
    create_ens_client,
    resolve_ens_name,
    reverse_resolve_address,
)

from .web3_event import (
    EventStatus,
    Web3Event,
    EventFilter,
    EventSubscription,
    Web3EventManager,
    create_event_manager,
)

from .web3_gas import (
    GasPriceInfo,
    GasEstimate,
    GasStrategy,
    GasManager,
    create_gas_manager,
)

from .web3_multicall import (
    MulticallRequest,
    MulticallResult,
    Web3Multicall,
    create_multicall,
)

from .web3_price import (
    PriceSource,
    PriceData,
    AggregatedPrice,
    Web3Price,
    create_price_client,
)

from .web3_provider import (
    ProviderType,
    ProviderStatus,
    ProviderConfig as Web3ProviderConfig,
    ProviderStats,
    Web3Provider,
    Web3ProviderPool,
    Web3ProviderManager,
    get_provider_manager,
    create_web3_provider,
    create_provider_pool,
)

from .web3_token import (
    TokenInfo,
    TokenBalance,
    TokenAllowance,
    TokenTransfer,
    TokenManager,
    create_token_manager,
)

from .web3_transaction import (
    TransactionStatus,
    TransactionType,
    Transaction,
    TransactionOptions,
    Web3TransactionManager,
    create_transaction_manager,
)

from .web3_utils import (
    Web3Utils,
    get_web3_utils,
    create_web3_utils,
)

from .web3_wallet import (
    WalletInfo,
    TransactionInfo,
    Web3Wallet,
    create_wallet,
    create_random_wallet,
)


# Web3 factory functions
def create_web3_client_from_config(config: dict) -> Web3Client:
    """
    Create a Web3 client from configuration dictionary.
    
    Args:
        config: Configuration dictionary.
        
    Returns:
        Web3Client instance.
    """
    return create_web3_client(config)


def create_web3_client_from_env() -> Web3Client:
    """
    Create a Web3 client from environment variables.
    
    Returns:
        Web3Client instance.
    """
    from .web3_config import get_web3_config
    config = get_web3_config()
    return Web3Client(config)


def get_default_web3_client() -> Web3Client:
    """
    Get the default Web3 client instance.
    
    Returns:
        Web3Client instance.
    """
    from .web3_client import _default_web3_client
    if _default_web3_client is None:
        return create_web3_client_from_env()
    return _default_web3_client


# Convenience functions for common operations
def get_eth_balance(address: str, web3_client: Optional[Web3Client] = None) -> float:
    """
    Get ETH balance for an address.
    
    Args:
        address: Ethereum address.
        web3_client: Web3 client (uses default if None).
        
    Returns:
        Balance in ETH.
    """
    if web3_client is None:
        web3_client = get_default_web3_client()
    return web3_client.get_balance(address)


def get_token_balance(
    token_address: str,
    owner_address: str,
    web3_client: Optional[Web3Client] = None,
    decimals: Optional[int] = None
) -> float:
    """
    Get ERC20 token balance.
    
    Args:
        token_address: Token contract address.
        owner_address: Owner address.
        web3_client: Web3 client (uses default if None).
        decimals: Token decimals (auto-fetched if None).
        
    Returns:
        Token balance.
    """
    if web3_client is None:
        web3_client = get_default_web3_client()
    return web3_client.get_token_balance(token_address, owner_address, decimals)


def send_eth(
    to: str,
    amount: float,
    private_key: str,
    web3_client: Optional[Web3Client] = None,
    gas_strategy: str = "standard"
) -> str:
    """
    Send ETH to an address.
    
    Args:
        to: Recipient address.
        amount: Amount in ETH.
        private_key: Sender private key.
        web3_client: Web3 client (uses default if None).
        gas_strategy: Gas strategy.
        
    Returns:
        Transaction hash.
    """
    if web3_client is None:
        web3_client = get_default_web3_client()
    
    # Set private key
    web3_client.set_private_key(private_key)
    
    # Build and send transaction
    tx = web3_client.build_transaction(to=to, value=amount, gas_strategy=gas_strategy)
    signed = web3_client._account.sign_transaction(tx)
    tx_hash = web3_client.send_raw_transaction(signed.raw_transaction)
    return tx_hash.hex()


def resolve_ens(name: str, web3_client: Optional[Web3Client] = None) -> Optional[str]:
    """
    Resolve an ENS name to an address.
    
    Args:
        name: ENS name.
        web3_client: Web3 client (uses default if None).
        
    Returns:
        Address or None.
    """
    if web3_client is None:
        web3_client = get_default_web3_client()
    return web3_client.resolve_ens(name)


def reverse_resolve(address: str, web3_client: Optional[Web3Client] = None) -> Optional[str]:
    """
    Reverse resolve an address to an ENS name.
    
    Args:
        address: Ethereum address.
        web3_client: Web3 client (uses default if None).
        
    Returns:
        ENS name or None.
    """
    if web3_client is None:
        web3_client = get_default_web3_client()
    return web3_client.reverse_resolve_ens(address)


# Web3 utility singleton
_web3_utils_singleton: Optional[Web3Utils] = None


def get_web3_utils_singleton(web3_client: Optional[Web3Client] = None) -> Web3Utils:
    """
    Get the singleton Web3 utilities instance.
    
    Args:
        web3_client: Web3 client (uses default if None).
        
    Returns:
        Web3Utils instance.
    """
    global _web3_utils_singleton
    if _web3_utils_singleton is None:
        if web3_client is None:
            web3_client = get_default_web3_client()
        _web3_utils_singleton = Web3Utils(web3_client)
    return _web3_utils_singleton


# Export all public classes and functions
__all__ = [
    # Alchemy
    'AlchemyClient',
    'create_alchemy_client',
    'AlchemyNetwork',
    'AlchemyWebSocketClient',
    'AlchemyNFTClient',
    'AlchemyTokenClient',
    'AlchemyTransactClient',
    
    # Base Web3
    'BaseWeb3Client',
    'BaseWeb3Config',
    
    # Etherscan
    'EtherscanClient',
    'create_etherscan_client',
    
    # Infura
    'InfuraClient',
    'create_infura_client',
    
    # Web3 Client
    'ProviderConfig',
    'Web3ClientConfig',
    'Web3Client',
    'create_web3_client',
    'create_web3_client_from_config',
    'create_web3_client_from_env',
    'get_default_web3_client',
    
    # Web3 Config
    'Web3ProviderConfig',
    'Web3NetworkConfig',
    'Web3Config',
    'Web3ConfigLoader',
    'get_web3_config',
    'create_web3_config',
    'DEFAULT_NETWORKS',
    
    # Web3 Contract
    'ContractEvent',
    'ContractCall',
    'ContractTransaction',
    'Web3Contract',
    'create_contract',
    'create_erc20_contract',
    'create_erc721_contract',
    'create_erc1155_contract',
    
    # Web3 ENS
    'ENSRecord',
    'ENSReverseRecord',
    'ENSClient',
    'create_ens_client',
    'resolve_ens_name',
    'reverse_resolve_address',
    
    # Web3 Event
    'EventStatus',
    'Web3Event',
    'EventFilter',
    'EventSubscription',
    'Web3EventManager',
    'create_event_manager',
    
    # Web3 Gas
    'GasPriceInfo',
    'GasEstimate',
    'GasStrategy',
    'GasManager',
    'create_gas_manager',
    
    # Web3 Multicall
    'MulticallRequest',
    'MulticallResult',
    'Web3Multicall',
    'create_multicall',
    
    # Web3 Price
    'PriceSource',
    'PriceData',
    'AggregatedPrice',
    'Web3Price',
    'create_price_client',
    
    # Web3 Provider
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
    
    # Web3 Token
    'TokenInfo',
    'TokenBalance',
    'TokenAllowance',
    'TokenTransfer',
    'TokenManager',
    'create_token_manager',
    
    # Web3 Transaction
    'TransactionStatus',
    'TransactionType',
    'Transaction',
    'TransactionOptions',
    'Web3TransactionManager',
    'create_transaction_manager',
    
    # Web3 Utils
    'Web3Utils',
    'get_web3_utils',
    'create_web3_utils',
    'get_web3_utils_singleton',
    
    # Web3 Wallet
    'WalletInfo',
    'TransactionInfo',
    'Web3Wallet',
    'create_wallet',
    'create_random_wallet',
    
    # Convenience functions
    'get_eth_balance',
    'get_token_balance',
    'send_eth',
    'resolve_ens',
    'reverse_resolve',
    
    # Version info
    '__version__',
    '__author__',
    '__copyright__',
]

# Setup logging
import logging
logger = logging.getLogger(__name__)
logger.info(f"Web3 package version {__version__} initialized")
