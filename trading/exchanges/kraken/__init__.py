# trading/exchanges/kraken/__init__.py
# Nexus AI Trading System - Kraken Exchange Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Kraken Exchange Module - Complete Integration Package

This module provides comprehensive integration with the Kraken cryptocurrency
exchange, offering a unified interface for all trading operations.

Architecture Overview:
    ┌─────────────────────────────────────────────────────────────┐
    │                    Kraken Exchange Module                   │
    ├─────────────────────────────────────────────────────────────┤
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
    │  │    Base     │  │   Market    │  │       Order         │ │
    │  │   (Core)    │  │   (Data)    │  │    (Management)     │ │
    │  └─────────────┘  └─────────────┘  └─────────────────────┘ │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
    │  │   Account   │  │   Spot      │  │     WebSocket       │ │
    │  │  (Manager)  │  │  (Trading)  │  │    (Streaming)      │ │
    │  └─────────────┘  └─────────────┘  └─────────────────────┘ │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
    │  │  Converter  │  │  Exception  │  │      Utils          │ │
    │  │   (Data)    │  │   (Errors)  │  │    (Helpers)        │ │
    │  └─────────────┘  └─────────────┘  └─────────────────────┘ │
    └─────────────────────────────────────────────────────────────┘

Features:
    - Complete REST API integration
    - Real-time WebSocket streaming
    - Advanced order management
    - Multi-currency spot trading
    - Comprehensive error handling
    - Data normalization and conversion
    - Account and balance management
    - Market data analytics
    - Order book management
    - Historical data access
    - Smart order execution
    - Automated reconnection
    - Rate limiting protection
    - Circuit breaker pattern
    - Redis caching
    - PostgreSQL persistence
    - Comprehensive logging
    - Performance monitoring

Submodules:
    - base: Core API client and authentication
    - market: Market data and analytics
    - order: Order management and execution
    - account: Account and balance management
    - spot: Spot trading operations
    - websocket: Real-time data streaming
    - converter: Data normalization
    - exceptions: Error handling hierarchy
    - utils: Utility functions
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union, Type, Tuple
from dataclasses import dataclass, field

# Core exports
from trading.exchanges.kraken.base import (
    KrakenBase,
    KrakenConfig,
    KrakenEnvironment,
    KrakenApiType,
    KrakenOrderType,
    KrakenOrderSide,
    KrakenOrderStatus,
    KrakenTimeInForce,
    KrakenWebSocketEvent,
    KrakenWebSocketChannel,
    KrakenBalance,
    KrakenTicker,
    KrakenOrder,
    KrakenTrade,
    KrakenRateLimiter,
    KrakenError,
    KrakenAuthenticationError,
    KrakenRateLimitError,
    KrakenInvalidSymbolError,
    KrakenOrderError,
    KrakenPositionError,
    KrakenInsufficientFundsError
)

# Market data exports
from trading.exchanges.kraken.market import (
    KrakenMarketData,
    KrakenInterval,
    KrakenIntervalSeconds,
    KrakenOHLC,
    KrakenOrderBookEntry,
    KrakenOrderBook,
    KrakenTrade as MarketTrade,
    KrakenTickerData,
    KrakenAsset,
    KrakenPair,
    MarketStats,
    MarketMetrics
)

# Order management exports
from trading.exchanges.kraken.order import (
    KrakenOrderManager,
    OrderRequest,
    OrderResponse,
    BatchOrderRequest,
    BatchOrderResponse,
    OrderValidationRequest,
    OrderValidationResponse,
    OrderValidationResult,
    OrderCancelRequest,
    OrderModificationRequest,
    OCOOrderRequest,
    BracketOrderRequest,
    OrderExecutionReport,
    OrderExecutionType,
    KrakenOrderStatus as OrderStatus,
    KrakenOrderFlags
)

# Spot trading exports
from trading.exchanges.kraken.spot import (
    KrakenSpotTrading,
    SpotOrderType,
    SpotOrderStatus,
    SpotOrderSide,
    SpotOrderTimeInForce,
    SpotExecutionType,
    SpotRiskLevel,
    SpotPrice,
    SpotOrder,
    SpotPosition,
    SpotTrade,
    SpotBalance,
    SpotExecutionParams
)

# Account management exports
from trading.exchanges.kraken.account import (
    KrakenAccountManager,
    AccountTier,
    AccountStatus,
    TransactionType,
    TransactionStatus,
    DepositMethod,
    WithdrawalMethod,
    Balance as AccountBalance,
    Transaction,
    DepositAddress,
    WithdrawalRequest,
    AccountSummary
)

# WebSocket exports
from trading.exchanges.kraken.websocket import (
    KrakenWebSocket,
    KrakenWebSocketFactory,
    KrakenWSChannel,
    KrakenWSEvent,
    KrakenWSConnectionStatus,
    KrakenWSMessageType,
    WSSubscription,
    WSMessage,
    WSConnectionState,
    WSStatistics
)

# Converter exports
from trading.exchanges.kraken.converter import (
    KrakenConverter,
    StandardOrder,
    StandardTicker,
    StandardBalance,
    StandardTrade,
    StandardPosition,
    get_converter,
    KRAKEN_CURRENCY_MAP,
    STANDARD_CURRENCY_MAP,
    KRAKEN_PAIR_MAP,
    STANDARD_PAIR_MAP,
    ORDER_TYPE_MAP,
    ORDER_STATUS_MAP,
    TIME_IN_FORCE_MAP
)

# Exception exports
from trading.exchanges.kraken.exceptions import (
    KrakenError as KrakenException,
    KrakenAuthenticationError as KrakenAuthError,
    KrakenRateLimitError as KrakenRateError,
    KrakenInvalidSymbolError as KrakenSymbolError,
    KrakenOrderError as KrakenOrderException,
    KrakenPositionError as KrakenPositionException,
    KrakenInsufficientFundsError as KrakenFundsError,
    KrakenPermissionError,
    KrakenTwoFactorError,
    KrakenOrderNotFoundError,
    KrakenOrderCancelledError,
    KrakenPositionNotFoundError,
    KrakenLiquidationError,
    KrakenAccountError,
    KrakenVerificationError,
    KrakenAccountSuspendedError,
    KrakenDataError,
    KrakenWebSocketError,
    KrakenWebSocketConnectionError,
    KrakenWebSocketSubscriptionError,
    KrakenWithdrawalError,
    KrakenInvalidAddressError,
    KrakenDepositError,
    KrakenValidationError,
    KrakenParameterError,
    KrakenSystemError,
    KrakenConnectionError,
    KrakenTimeoutError,
    create_kraken_exception,
    handle_kraken_response,
    retry_on_kraken_error
)

# Utility exports
from trading.exchanges.kraken.utils import (
    normalize_currency_pair,
    validate_currency_pair,
    calculate_pip_value,
    calculate_position_size,
    calculate_risk_reward_ratio,
    format_kraken_price,
    parse_kraken_price,
    get_kraken_pair_info,
    validate_kraken_symbol,
    calculate_kraken_fee,
    get_kraken_trading_hours,
    is_kraken_market_open,
    get_kraken_asset_info,
    get_kraken_trading_fees,
    calculate_kraken_min_order_size,
    validate_kraken_order_params,
    generate_kraken_client_id,
    parse_kraken_timestamp,
    format_kraken_timestamp,
    KRAKEN_ORDER_TYPES,
    KRAKEN_ORDER_SIDES,
    KRAKEN_TIME_IN_FORCE,
    KRAKEN_INTERVALS,
    KRAKEN_FIAT_CURRENCIES,
    KRAKEN_CRYPTO_CURRENCIES
)

# =============================================================================
# MODULE CONFIGURATION
# =============================================================================

# Module version
__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# EXCHANGE FACTORY
# =============================================================================

class KrakenExchangeFactory:
    """
    Factory for creating Kraken exchange components.
    
    Provides a unified interface for creating and managing
    all Kraken exchange components.
    """
    
    @staticmethod
    async def create_exchange(
        api_key: str,
        api_secret: str,
        environment: KrakenEnvironment = KrakenEnvironment.PRODUCTION,
        config_override: Optional[Dict[str, Any]] = None,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Create a complete Kraken exchange instance with all components.
        
        Args:
            api_key: Kraken API key
            api_secret: Kraken API secret
            environment: API environment
            config_override: Configuration overrides
            redis: Redis client for caching
            pool: PostgreSQL connection pool
            
        Returns:
            Dict containing all exchange components
        """
        # Create configuration
        config = KrakenConfig(
            api_key=api_key,
            api_secret=api_secret,
            environment=environment,
            **(config_override or {})
        )
        
        # Create converter
        converter = get_converter()
        
        # Create base client
        base = KrakenBase(config, redis)
        await base.connect()
        
        # Create market data
        market_data = KrakenMarketData(base, config, converter, redis, pool)
        await market_data.initialize()
        
        # Create account manager
        account_manager = KrakenAccountManager(config, base, redis, pool)
        await account_manager.initialize()
        
        # Create order manager
        order_manager = KrakenOrderManager(base, config, market_data, converter, redis, pool)
        await order_manager.initialize()
        
        # Create spot trading
        spot_trading = KrakenSpotTrading(base, config, market_data, order_manager, converter, redis, pool)
        await spot_trading.initialize()
        
        # Create WebSocket
        websocket = KrakenWebSocket(base, config, converter, redis, pool)
        await websocket.initialize()
        
        return {
            "config": config,
            "base": base,
            "converter": converter,
            "market_data": market_data,
            "account_manager": account_manager,
            "order_manager": order_manager,
            "spot_trading": spot_trading,
            "websocket": websocket
        }
    
    @staticmethod
    async def create_base_client(
        api_key: str,
        api_secret: str,
        environment: KrakenEnvironment = KrakenEnvironment.PRODUCTION,
        config_override: Optional[Dict[str, Any]] = None,
        redis: Optional[Any] = None
    ) -> KrakenBase:
        """
        Create only the base client.
        
        Args:
            api_key: Kraken API key
            api_secret: Kraken API secret
            environment: API environment
            config_override: Configuration overrides
            redis: Redis client for caching
            
        Returns:
            KrakenBase instance
        """
        config = KrakenConfig(
            api_key=api_key,
            api_secret=api_secret,
            environment=environment,
            **(config_override or {})
        )
        
        base = KrakenBase(config, redis)
        await base.connect()
        return base
    
    @staticmethod
    async def create_market_data(
        base: KrakenBase,
        config: KrakenConfig,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None
    ) -> KrakenMarketData:
        """
        Create market data component.
        
        Args:
            base: Kraken base client
            config: Kraken configuration
            redis: Redis client for caching
            pool: PostgreSQL connection pool
            
        Returns:
            KrakenMarketData instance
        """
        market_data = KrakenMarketData(base, config, None, redis, pool)
        await market_data.initialize()
        return market_data
    
    @staticmethod
    async def create_account_manager(
        base: KrakenBase,
        config: KrakenConfig,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None
    ) -> KrakenAccountManager:
        """
        Create account manager component.
        
        Args:
            base: Kraken base client
            config: Kraken configuration
            redis: Redis client for caching
            pool: PostgreSQL connection pool
            
        Returns:
            KrakenAccountManager instance
        """
        account_manager = KrakenAccountManager(config, base, redis, pool)
        await account_manager.initialize()
        return account_manager
    
    @staticmethod
    async def create_order_manager(
        base: KrakenBase,
        config: KrakenConfig,
        market_data: Optional[KrakenMarketData] = None,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None
    ) -> KrakenOrderManager:
        """
        Create order manager component.
        
        Args:
            base: Kraken base client
            config: Kraken configuration
            market_data: Market data component
            redis: Redis client for caching
            pool: PostgreSQL connection pool
            
        Returns:
            KrakenOrderManager instance
        """
        order_manager = KrakenOrderManager(base, config, market_data, None, redis, pool)
        await order_manager.initialize()
        return order_manager
    
    @staticmethod
    async def create_websocket(
        base: KrakenBase,
        config: KrakenConfig,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None
    ) -> KrakenWebSocket:
        """
        Create WebSocket component.
        
        Args:
            base: Kraken base client
            config: Kraken configuration
            redis: Redis client for caching
            pool: PostgreSQL connection pool
            
        Returns:
            KrakenWebSocket instance
        """
        websocket = KrakenWebSocket(base, config, None, redis, pool)
        await websocket.initialize()
        return websocket


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def create_kraken_client(
    api_key: str,
    api_secret: str,
    environment: str = "production",
    **kwargs
) -> Dict[str, Any]:
    """
    Create a complete Kraken client with all components.
    
    Args:
        api_key: Kraken API key
        api_secret: Kraken API secret
        environment: Environment (production, sandbox, development)
        **kwargs: Additional configuration
        
    Returns:
        Dict with all components
    """
    env_map = {
        "production": KrakenEnvironment.PRODUCTION,
        "sandbox": KrakenEnvironment.SANDBOX,
        "development": KrakenEnvironment.DEVELOPMENT
    }
    
    env = env_map.get(environment.lower(), KrakenEnvironment.PRODUCTION)
    
    return await KrakenExchangeFactory.create_exchange(
        api_key=api_key,
        api_secret=api_secret,
        environment=env,
        config_override=kwargs
    )


async def create_simple_client(
    api_key: str,
    api_secret: str,
    environment: str = "production"
) -> KrakenBase:
    """
    Create a simple base client.
    
    Args:
        api_key: Kraken API key
        api_secret: Kraken API secret
        environment: Environment
        
    Returns:
        KrakenBase instance
    """
    env_map = {
        "production": KrakenEnvironment.PRODUCTION,
        "sandbox": KrakenEnvironment.SANDBOX,
        "development": KrakenEnvironment.DEVELOPMENT
    }
    
    env = env_map.get(environment.lower(), KrakenEnvironment.PRODUCTION)
    
    return await KrakenExchangeFactory.create_base_client(
        api_key=api_key,
        api_secret=api_secret,
        environment=env
    )


# =============================================================================
# MODULE INITIALIZATION
# =============================================================================

# Initialize module on first import
logger.info(f"Kraken exchange module v{__version__} initialized")
logger.info(f"Supported by NEXUS QUANTUM LTD - {__copyright__}")

# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Core
    'KrakenBase',
    'KrakenConfig',
    'KrakenEnvironment',
    'KrakenApiType',
    'KrakenOrderType',
    'KrakenOrderSide',
    'KrakenOrderStatus',
    'KrakenTimeInForce',
    'KrakenWebSocketEvent',
    'KrakenWebSocketChannel',
    'KrakenBalance',
    'KrakenTicker',
    'KrakenOrder',
    'KrakenTrade',
    'KrakenRateLimiter',
    
    # Market Data
    'KrakenMarketData',
    'KrakenInterval',
    'KrakenIntervalSeconds',
    'KrakenOHLC',
    'KrakenOrderBookEntry',
    'KrakenOrderBook',
    'MarketTrade',
    'KrakenTickerData',
    'KrakenAsset',
    'KrakenPair',
    'MarketStats',
    'MarketMetrics',
    
    # Order Management
    'KrakenOrderManager',
    'OrderRequest',
    'OrderResponse',
    'BatchOrderRequest',
    'BatchOrderResponse',
    'OrderValidationRequest',
    'OrderValidationResponse',
    'OrderValidationResult',
    'OrderCancelRequest',
    'OrderModificationRequest',
    'OCOOrderRequest',
    'BracketOrderRequest',
    'OrderExecutionReport',
    'OrderExecutionType',
    'OrderStatus',
    'KrakenOrderFlags',
    
    # Spot Trading
    'KrakenSpotTrading',
    'SpotOrderType',
    'SpotOrderStatus',
    'SpotOrderSide',
    'SpotOrderTimeInForce',
    'SpotExecutionType',
    'SpotRiskLevel',
    'SpotPrice',
    'SpotOrder',
    'SpotPosition',
    'SpotTrade',
    'SpotBalance',
    'SpotExecutionParams',
    
    # Account Management
    'KrakenAccountManager',
    'AccountTier',
    'AccountStatus',
    'TransactionType',
    'TransactionStatus',
    'DepositMethod',
    'WithdrawalMethod',
    'AccountBalance',
    'Transaction',
    'DepositAddress',
    'WithdrawalRequest',
    'AccountSummary',
    
    # WebSocket
    'KrakenWebSocket',
    'KrakenWebSocketFactory',
    'KrakenWSChannel',
    'KrakenWSEvent',
    'KrakenWSConnectionStatus',
    'KrakenWSMessageType',
    'WSSubscription',
    'WSMessage',
    'WSConnectionState',
    'WSStatistics',
    
    # Converter
    'KrakenConverter',
    'StandardOrder',
    'StandardTicker',
    'StandardBalance',
    'StandardTrade',
    'StandardPosition',
    'get_converter',
    'KRAKEN_CURRENCY_MAP',
    'STANDARD_CURRENCY_MAP',
    'KRAKEN_PAIR_MAP',
    'STANDARD_PAIR_MAP',
    'ORDER_TYPE_MAP',
    'ORDER_STATUS_MAP',
    'TIME_IN_FORCE_MAP',
    
    # Exceptions
    'KrakenException',
    'KrakenAuthError',
    'KrakenRateError',
    'KrakenSymbolError',
    'KrakenOrderException',
    'KrakenPositionException',
    'KrakenFundsError',
    'KrakenPermissionError',
    'KrakenTwoFactorError',
    'KrakenOrderNotFoundError',
    'KrakenOrderCancelledError',
    'KrakenPositionNotFoundError',
    'KrakenLiquidationError',
    'KrakenAccountError',
    'KrakenVerificationError',
    'KrakenAccountSuspendedError',
    'KrakenDataError',
    'KrakenWebSocketError',
    'KrakenWebSocketConnectionError',
    'KrakenWebSocketSubscriptionError',
    'KrakenWithdrawalError',
    'KrakenInvalidAddressError',
    'KrakenDepositError',
    'KrakenValidationError',
    'KrakenParameterError',
    'KrakenSystemError',
    'KrakenConnectionError',
    'KrakenTimeoutError',
    'create_kraken_exception',
    'handle_kraken_response',
    'retry_on_kraken_error',
    
    # Utilities
    'normalize_currency_pair',
    'validate_currency_pair',
    'calculate_pip_value',
    'calculate_position_size',
    'calculate_risk_reward_ratio',
    'format_kraken_price',
    'parse_kraken_price',
    'get_kraken_pair_info',
    'validate_kraken_symbol',
    'calculate_kraken_fee',
    'get_kraken_trading_hours',
    'is_kraken_market_open',
    'get_kraken_asset_info',
    'get_kraken_trading_fees',
    'calculate_kraken_min_order_size',
    'validate_kraken_order_params',
    'generate_kraken_client_id',
    'parse_kraken_timestamp',
    'format_kraken_timestamp',
    'KRAKEN_ORDER_TYPES',
    'KRAKEN_ORDER_SIDES',
    'KRAKEN_TIME_IN_FORCE',
    'KRAKEN_INTERVALS',
    'KRAKEN_FIAT_CURRENCIES',
    'KRAKEN_CRYPTO_CURRENCIES',
    
    # Factory
    'KrakenExchangeFactory',
    'create_kraken_client',
    'create_simple_client',
    
    # Module info
    '__version__',
    '__author__',
    '__copyright__'
]
