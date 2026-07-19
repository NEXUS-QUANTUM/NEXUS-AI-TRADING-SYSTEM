# trading/exchanges/okx/__init__.py
# Nexus AI Trading System - OKX Exchange Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
OKX Exchange Module - Complete Integration Package

This module provides comprehensive integration with the OKX cryptocurrency
exchange, offering a unified interface for all trading operations across
spot, futures, options, and perpetual swaps.

Architecture Overview:
    ┌─────────────────────────────────────────────────────────────────┐
    │                      OKX Exchange Module                       │
    ├─────────────────────────────────────────────────────────────────┤
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
    │  │    Base     │  │   Market    │  │         Order           │ │
    │  │   (Core)    │  │   (Data)    │  │      (Management)       │ │
    │  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
    │  │   Account   │  │    Spot     │  │        Futures          │ │
    │  │  (Manager)  │  │  (Trading)  │  │      (Trading)          │ │
    │  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
    │  │   Options   │  │    Swap     │  │       WebSocket         │ │
    │  │  (Trading)  │  │  (Trading)  │  │      (Streaming)        │ │
    │  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
    │  │  Converter  │  │  Exception  │  │         Utils           │ │
    │  │   (Data)    │  │   (Errors)  │  │       (Helpers)         │ │
    │  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
    └─────────────────────────────────────────────────────────────────┘

Features:
    - Complete REST API integration
    - Real-time WebSocket streaming
    - Advanced order management
    - Multi-currency spot trading
    - Futures and perpetual swap trading
    - Options trading with Greeks
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
    - futures: Futures trading operations
    - swap: Perpetual swap trading operations
    - option: Options trading with Greeks
    - websocket: Real-time data streaming
    - converter: Data normalization
    - exceptions: Error handling hierarchy
    - utils: Utility functions
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union, Type, Tuple
from dataclasses import dataclass, field

# =============================================================================
# CORE EXPORTS
# =============================================================================

from trading.exchanges.okx.base import (
    OKXBase,
    OKXConfig,
    OKXEnvironment,
    OKXApiType,
    OKXOrderType,
    OKXOrderSide,
    OKXOrderStatus,
    OKXTimeInForce,
    OKXWebSocketEvent,
    OKXWebSocketChannel,
    OKXTicker,
    OKXOHLC,
    OKXOrder,
    OKXRateLimiter,
    OKXError,
    OKXAuthenticationError,
    OKXRateLimitError,
    OKXInvalidSymbolError,
    OKXOrderError,
    OKXPositionError,
    OKXInsufficientFundsError
)

# =============================================================================
# MARKET DATA EXPORTS
# =============================================================================

from trading.exchanges.okx.market import (
    OKXMarketData,
    OKXInterval,
    OKXIntervalSeconds,
    OKXInstrumentType as MarketInstrumentType,
    OKXMarketStatus,
    OKXOHLC as MarketOHLC,
    OKXOrderBookEntry,
    OKXOrderBook,
    OKXTicker as MarketTicker,
    OKXInstrument,
    MarketStats,
    MarketMetrics
)

# =============================================================================
# ORDER MANAGEMENT EXPORTS
# =============================================================================

from trading.exchanges.okx.order import (
    OKXOrderManager,
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
    OKXOrderStatusExtended
)

# =============================================================================
# SPOT TRADING EXPORTS
# =============================================================================

from trading.exchanges.okx.spot import (
    OKXSpotTrading,
    SpotOrderType,
    SpotOrderSide,
    SpotOrderStatus,
    SpotTimeInForce,
    SpotExecutionType,
    SpotPrice,
    SpotOrder,
    SpotPosition,
    SpotTrade,
    SpotBalance,
    SpotExecutionParams
)

# =============================================================================
# FUTURES TRADING EXPORTS
# =============================================================================

from trading.exchanges.okx.futures import (
    OKXFuturesTrading,
    FuturesInstrumentType,
    FuturesOrderType,
    FuturesOrderSide,
    FuturesPositionSide,
    FuturesMarginMode,
    FuturesOrderStatus,
    FuturesPositionStatus,
    FuturesTimeInForce,
    FuturesOrder,
    FuturesPosition,
    FuturesFundingRate,
    FuturesRiskInfo,
    FuturesTrade,
    FuturesBalance,
    FuturesInstrument
)

# =============================================================================
# PERPETUAL SWAP EXPORTS
# =============================================================================

from trading.exchanges.okx.swap import (
    OKXSwapTrading,
    SwapOrderType,
    SwapOrderSide,
    SwapPositionSide,
    SwapMarginMode,
    SwapOrderStatus,
    SwapPositionStatus,
    SwapTimeInForce,
    SwapInstrumentType,
    SwapOrder,
    SwapPosition,
    SwapFundingRate,
    SwapRiskInfo,
    SwapTrade,
    SwapBalance,
    SwapInstrument
)

# =============================================================================
# OPTIONS TRADING EXPORTS
# =============================================================================

from trading.exchanges.okx.option import (
    OKXOptionsTrading,
    OptionType,
    OptionStyle,
    OptionOrderType,
    OptionOrderSide,
    OptionPositionSide,
    OptionExerciseType,
    OptionMarginMode,
    OptionStatus,
    OptionGreeks,
    OptionContract,
    OptionOrder,
    OptionPosition,
    OptionStrategy,
    VolatilitySurface,
    OptionPricingEngine
)

# =============================================================================
# ACCOUNT MANAGEMENT EXPORTS
# =============================================================================

from trading.exchanges.okx.account import (
    OKXAccountManager,
    AccountType,
    AccountTier,
    AccountStatus,
    TransactionType,
    TransactionStatus,
    DepositStatus,
    WithdrawalStatus,
    TransferType,
    FeeTier,
    Balance,
    Transaction,
    DepositAddress,
    WithdrawalRequest,
    DepositRequest,
    TransferRequest,
    AccountSummary,
    FeeInfo
)

# =============================================================================
# WEBSOCKET EXPORTS
# =============================================================================

from trading.exchanges.okx.websocket import (
    OKXWebSocket,
    OKXWebSocketFactory,
    OKXWSChannel,
    OKXWSEvent,
    OKXWSConnectionStatus,
    OKXWSMessageType,
    WSSubscription,
    WSMessage,
    WSConnectionState,
    WSStatistics
)

# =============================================================================
# CONVERTER EXPORTS
# =============================================================================

from trading.exchanges.okx.converter import (
    OKXConverter,
    StandardOrder,
    StandardTicker,
    StandardBalance,
    StandardTrade,
    StandardOHLC,
    StandardInstrument,
    get_converter,
    OKX_CURRENCY_MAP,
    STANDARD_CURRENCY_MAP,
    OKX_INSTRUMENT_TYPE,
    ORDER_TYPE_MAP,
    ORDER_STATUS_MAP,
    TIME_IN_FORCE_MAP,
    OKX_BAR_MAP
)

# =============================================================================
# EXCEPTION EXPORTS
# =============================================================================

from trading.exchanges.okx.exceptions import (
    OKXError as OKXException,
    OKXAuthenticationError as OKXAuthError,
    OKXRateLimitError as OKXRateError,
    OKXInvalidSymbolError as OKXSymbolError,
    OKXOrderError as OKXOrderException,
    OKXPositionError as OKXPositionException,
    OKXInsufficientFundsError as OKXFundsError,
    OKXPermissionError,
    OKXTwoFactorError,
    OKXVerificationError,
    OKXAccountError,
    OKXAccountFrozenError,
    OKXOrderNotFoundError,
    OKXOrderCancelledError,
    OKXOrderFilledError,
    OKXOrderTypeError,
    OKXSideError,
    OKXTimeInForceError,
    OKXPriceOutOfRangeError,
    OKXVolumeOutOfRangeError,
    OKXPositionNotFoundError,
    OKXPositionLimitError,
    OKXLiquidationError,
    OKXMarketDataError,
    OKXMarketClosedError,
    OKXWithdrawalError,
    OKXInvalidAddressError,
    OKXDepositError,
    OKXTransferError,
    OKXWebSocketError,
    OKXWebSocketConnectionError,
    OKXWebSocketSubscriptionError,
    OKXWebSocketRateLimitError,
    OKXValidationError,
    OKXParameterError,
    OKXSystemError,
    OKXConnectionError,
    OKXTimeoutError,
    create_okx_exception,
    handle_okx_response,
    handle_okx_error_response,
    retry_on_okx_error,
    handle_okx_errors,
    OKXErrorCode,
    OKX_ERROR_MAP,
    OKX_ERROR_MESSAGES,
    RETRYABLE_ERROR_CODES,
    RECOVERY_ACTIONS
)

# =============================================================================
# UTILITY EXPORTS
# =============================================================================

from trading.exchanges.okx.utils import (
    normalize_okx_symbol,
    validate_okx_symbol,
    calculate_pip_value,
    calculate_position_size,
    calculate_risk_reward_ratio,
    format_okx_price,
    parse_okx_price,
    get_okx_instrument_info,
    validate_okx_instrument,
    calculate_okx_fee,
    get_okx_trading_hours,
    is_okx_market_open,
    get_okx_asset_info,
    get_okx_trading_fees,
    calculate_okx_min_order_size,
    validate_okx_order_params,
    generate_okx_client_id,
    parse_okx_timestamp,
    format_okx_timestamp,
    OKX_ORDER_TYPES,
    OKX_ORDER_SIDES,
    OKX_TIME_IN_FORCE,
    OKX_INTERVALS,
    OKX_FIAT_CURRENCIES,
    OKX_CRYPTO_CURRENCIES
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

class OKXExchangeFactory:
    """
    Factory for creating OKX exchange components.
    
    Provides a unified interface for creating and managing
    all OKX exchange components across all product types.
    """
    
    @staticmethod
    async def create_exchange(
        api_key: str,
        api_secret: str,
        api_passphrase: str,
        environment: OKXEnvironment = OKXEnvironment.PRODUCTION,
        config_override: Optional[Dict[str, Any]] = None,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Create a complete OKX exchange instance with all components.
        
        Args:
            api_key: OKX API key
            api_secret: OKX API secret
            api_passphrase: OKX API passphrase
            environment: API environment
            config_override: Configuration overrides
            redis: Redis client for caching
            pool: PostgreSQL connection pool
            
        Returns:
            Dict containing all exchange components
        """
        # Create configuration
        config = OKXConfig(
            api_key=api_key,
            api_secret=api_secret,
            api_passphrase=api_passphrase,
            environment=environment,
            **(config_override or {})
        )
        
        # Create converter
        converter = get_converter()
        
        # Create base client
        base = OKXBase(config, redis)
        await base.connect()
        
        # Create market data
        market_data = OKXMarketData(base, config, converter, redis, pool)
        await market_data.initialize()
        
        # Create account manager
        account_manager = OKXAccountManager(config, base, redis, pool)
        await account_manager.initialize()
        
        # Create order manager
        order_manager = OKXOrderManager(base, config, market_data, converter, redis, pool)
        await order_manager.initialize()
        
        # Create spot trading
        spot_trading = OKXSpotTrading(base, config, market_data, order_manager, converter, redis, pool)
        await spot_trading.initialize()
        
        # Create futures trading
        futures_trading = OKXFuturesTrading(base, config, market_data, converter, redis, pool)
        await futures_trading.initialize()
        
        # Create swap trading
        swap_trading = OKXSwapTrading(base, config, market_data, converter, redis, pool)
        await swap_trading.initialize()
        
        # Create options trading
        options_trading = OKXOptionsTrading(base, config, market_data, converter, redis, pool)
        await options_trading.initialize()
        
        # Create WebSocket
        websocket = OKXWebSocket(base, config, converter, redis, pool)
        await websocket.initialize()
        
        return {
            "config": config,
            "base": base,
            "converter": converter,
            "market_data": market_data,
            "account_manager": account_manager,
            "order_manager": order_manager,
            "spot_trading": spot_trading,
            "futures_trading": futures_trading,
            "swap_trading": swap_trading,
            "options_trading": options_trading,
            "websocket": websocket
        }
    
    @staticmethod
    async def create_base_client(
        api_key: str,
        api_secret: str,
        api_passphrase: str,
        environment: OKXEnvironment = OKXEnvironment.PRODUCTION,
        config_override: Optional[Dict[str, Any]] = None,
        redis: Optional[Any] = None
    ) -> OKXBase:
        """Create only the base client."""
        config = OKXConfig(
            api_key=api_key,
            api_secret=api_secret,
            api_passphrase=api_passphrase,
            environment=environment,
            **(config_override or {})
        )
        
        base = OKXBase(config, redis)
        await base.connect()
        return base
    
    @staticmethod
    async def create_trading_module(
        base: OKXBase,
        config: OKXConfig,
        module_type: str,
        market_data: Optional[OKXMarketData] = None,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None
    ) -> Any:
        """
        Create a specific trading module.
        
        Args:
            base: OKX base client
            config: OKX configuration
            module_type: 'spot', 'futures', 'swap', or 'options'
            market_data: Market data component
            redis: Redis client
            pool: PostgreSQL connection pool
            
        Returns:
            Trading module instance
        """
        converter = get_converter()
        
        if module_type == 'spot':
            order_manager = OKXOrderManager(base, config, market_data, converter, redis, pool)
            await order_manager.initialize()
            spot = OKXSpotTrading(base, config, market_data, order_manager, converter, redis, pool)
            await spot.initialize()
            return spot
        
        elif module_type == 'futures':
            futures = OKXFuturesTrading(base, config, market_data, converter, redis, pool)
            await futures.initialize()
            return futures
        
        elif module_type == 'swap':
            swap = OKXSwapTrading(base, config, market_data, converter, redis, pool)
            await swap.initialize()
            return swap
        
        elif module_type == 'options':
            options = OKXOptionsTrading(base, config, market_data, converter, redis, pool)
            await options.initialize()
            return options
        
        else:
            raise ValueError(f"Unknown module type: {module_type}")

# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

async def create_okx_client(
    api_key: str,
    api_secret: str,
    api_passphrase: str,
    environment: str = "production",
    **kwargs
) -> Dict[str, Any]:
    """
    Create a complete OKX client with all components.
    
    Args:
        api_key: OKX API key
        api_secret: OKX API secret
        api_passphrase: OKX API passphrase
        environment: Environment (production, demo, sandbox)
        **kwargs: Additional configuration
        
    Returns:
        Dict with all components
    """
    env_map = {
        "production": OKXEnvironment.PRODUCTION,
        "demo": OKXEnvironment.DEMO,
        "sandbox": OKXEnvironment.SANDBOX
    }
    
    env = env_map.get(environment.lower(), OKXEnvironment.PRODUCTION)
    
    return await OKXExchangeFactory.create_exchange(
        api_key=api_key,
        api_secret=api_secret,
        api_passphrase=api_passphrase,
        environment=env,
        config_override=kwargs
    )


async def create_simple_client(
    api_key: str,
    api_secret: str,
    api_passphrase: str,
    environment: str = "production"
) -> OKXBase:
    """
    Create a simple base client.
    
    Args:
        api_key: OKX API key
        api_secret: OKX API secret
        api_passphrase: OKX API passphrase
        environment: Environment
        
    Returns:
        OKXBase instance
    """
    env_map = {
        "production": OKXEnvironment.PRODUCTION,
        "demo": OKXEnvironment.DEMO,
        "sandbox": OKXEnvironment.SANDBOX
    }
    
    env = env_map.get(environment.lower(), OKXEnvironment.PRODUCTION)
    
    return await OKXExchangeFactory.create_base_client(
        api_key=api_key,
        api_secret=api_secret,
        api_passphrase=api_passphrase,
        environment=env
    )


def get_converter_instance(precision: int = 8) -> OKXConverter:
    """Get the default converter instance."""
    return get_converter(precision)

# =============================================================================
# MODULE INITIALIZATION
# =============================================================================

# Initialize module on first import
logger.info(f"OKX exchange module v{__version__} initialized")
logger.info(f"Supported by NEXUS QUANTUM LTD - {__copyright__}")

# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Core
    'OKXBase',
    'OKXConfig',
    'OKXEnvironment',
    'OKXApiType',
    'OKXOrderType',
    'OKXOrderSide',
    'OKXOrderStatus',
    'OKXTimeInForce',
    'OKXWebSocketEvent',
    'OKXWebSocketChannel',
    'OKXTicker',
    'OKXOHLC',
    'OKXOrder',
    'OKXRateLimiter',
    
    # Market Data
    'OKXMarketData',
    'OKXInterval',
    'OKXIntervalSeconds',
    'MarketInstrumentType',
    'OKXMarketStatus',
    'MarketOHLC',
    'OKXOrderBookEntry',
    'OKXOrderBook',
    'MarketTicker',
    'OKXInstrument',
    'MarketStats',
    'MarketMetrics',
    
    # Order Management
    'OKXOrderManager',
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
    'OKXOrderStatusExtended',
    
    # Spot Trading
    'OKXSpotTrading',
    'SpotOrderType',
    'SpotOrderSide',
    'SpotOrderStatus',
    'SpotTimeInForce',
    'SpotExecutionType',
    'SpotPrice',
    'SpotOrder',
    'SpotPosition',
    'SpotTrade',
    'SpotBalance',
    'SpotExecutionParams',
    
    # Futures Trading
    'OKXFuturesTrading',
    'FuturesInstrumentType',
    'FuturesOrderType',
    'FuturesOrderSide',
    'FuturesPositionSide',
    'FuturesMarginMode',
    'FuturesOrderStatus',
    'FuturesPositionStatus',
    'FuturesTimeInForce',
    'FuturesOrder',
    'FuturesPosition',
    'FuturesFundingRate',
    'FuturesRiskInfo',
    'FuturesTrade',
    'FuturesBalance',
    'FuturesInstrument',
    
    # Swap Trading
    'OKXSwapTrading',
    'SwapOrderType',
    'SwapOrderSide',
    'SwapPositionSide',
    'SwapMarginMode',
    'SwapOrderStatus',
    'SwapPositionStatus',
    'SwapTimeInForce',
    'SwapInstrumentType',
    'SwapOrder',
    'SwapPosition',
    'SwapFundingRate',
    'SwapRiskInfo',
    'SwapTrade',
    'SwapBalance',
    'SwapInstrument',
    
    # Options Trading
    'OKXOptionsTrading',
    'OptionType',
    'OptionStyle',
    'OptionOrderType',
    'OptionOrderSide',
    'OptionPositionSide',
    'OptionExerciseType',
    'OptionMarginMode',
    'OptionStatus',
    'OptionGreeks',
    'OptionContract',
    'OptionOrder',
    'OptionPosition',
    'OptionStrategy',
    'VolatilitySurface',
    'OptionPricingEngine',
    
    # Account Management
    'OKXAccountManager',
    'AccountType',
    'AccountTier',
    'AccountStatus',
    'TransactionType',
    'TransactionStatus',
    'DepositStatus',
    'WithdrawalStatus',
    'TransferType',
    'FeeTier',
    'Balance',
    'Transaction',
    'DepositAddress',
    'WithdrawalRequest',
    'DepositRequest',
    'TransferRequest',
    'AccountSummary',
    'FeeInfo',
    
    # WebSocket
    'OKXWebSocket',
    'OKXWebSocketFactory',
    'OKXWSChannel',
    'OKXWSEvent',
    'OKXWSConnectionStatus',
    'OKXWSMessageType',
    'WSSubscription',
    'WSMessage',
    'WSConnectionState',
    'WSStatistics',
    
    # Converter
    'OKXConverter',
    'StandardOrder',
    'StandardTicker',
    'StandardBalance',
    'StandardTrade',
    'StandardOHLC',
    'StandardInstrument',
    'get_converter',
    'OKX_CURRENCY_MAP',
    'STANDARD_CURRENCY_MAP',
    'OKX_INSTRUMENT_TYPE',
    'ORDER_TYPE_MAP',
    'ORDER_STATUS_MAP',
    'TIME_IN_FORCE_MAP',
    'OKX_BAR_MAP',
    
    # Exceptions
    'OKXException',
    'OKXAuthError',
    'OKXRateError',
    'OKXSymbolError',
    'OKXOrderException',
    'OKXPositionException',
    'OKXFundsError',
    'OKXPermissionError',
    'OKXTwoFactorError',
    'OKXVerificationError',
    'OKXAccountError',
    'OKXAccountFrozenError',
    'OKXOrderNotFoundError',
    'OKXOrderCancelledError',
    'OKXOrderFilledError',
    'OKXOrderTypeError',
    'OKXSideError',
    'OKXTimeInForceError',
    'OKXPriceOutOfRangeError',
    'OKXVolumeOutOfRangeError',
    'OKXPositionNotFoundError',
    'OKXPositionLimitError',
    'OKXLiquidationError',
    'OKXMarketDataError',
    'OKXMarketClosedError',
    'OKXWithdrawalError',
    'OKXInvalidAddressError',
    'OKXDepositError',
    'OKXTransferError',
    'OKXWebSocketError',
    'OKXWebSocketConnectionError',
    'OKXWebSocketSubscriptionError',
    'OKXWebSocketRateLimitError',
    'OKXValidationError',
    'OKXParameterError',
    'OKXSystemError',
    'OKXConnectionError',
    'OKXTimeoutError',
    'create_okx_exception',
    'handle_okx_response',
    'handle_okx_error_response',
    'retry_on_okx_error',
    'handle_okx_errors',
    'OKXErrorCode',
    'OKX_ERROR_MAP',
    'OKX_ERROR_MESSAGES',
    'RETRYABLE_ERROR_CODES',
    'RECOVERY_ACTIONS',
    
    # Utilities
    'normalize_okx_symbol',
    'validate_okx_symbol',
    'calculate_pip_value',
    'calculate_position_size',
    'calculate_risk_reward_ratio',
    'format_okx_price',
    'parse_okx_price',
    'get_okx_instrument_info',
    'validate_okx_instrument',
    'calculate_okx_fee',
    'get_okx_trading_hours',
    'is_okx_market_open',
    'get_okx_asset_info',
    'get_okx_trading_fees',
    'calculate_okx_min_order_size',
    'validate_okx_order_params',
    'generate_okx_client_id',
    'parse_okx_timestamp',
    'format_okx_timestamp',
    'OKX_ORDER_TYPES',
    'OKX_ORDER_SIDES',
    'OKX_TIME_IN_FORCE',
    'OKX_INTERVALS',
    'OKX_FIAT_CURRENCIES',
    'OKX_CRYPTO_CURRENCIES',
    
    # Factory
    'OKXExchangeFactory',
    'create_okx_client',
    'create_simple_client',
    'get_converter_instance',
    
    # Module info
    '__version__',
    '__author__',
    '__copyright__'
]
