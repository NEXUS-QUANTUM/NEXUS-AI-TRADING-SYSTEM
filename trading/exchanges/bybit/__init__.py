"""
NEXUS AI TRADING SYSTEM - Bybit Exchange Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/bybit/__init__.py
Description: Bybit Exchange module initialization and exports
"""

import logging
from typing import Dict, List, Optional, Any, Type

# Import all Bybit components
from trading.exchanges.bybit.base import (
    BybitBase,
    BybitEnvironment,
    BybitInterval,
    BybitCategory,
    BybitDepthLevel,
    BybitWebSocketChannel,
    BybitCandle,
    BybitTicker,
    BybitOrderBookLevel,
    BybitOrderBook,
    BybitTrade,
    BybitInstrumentInfo,
    BybitApiLimits,
    BybitWebSocketMessage,
    BybitStreamConfig
)

from trading.exchanges.bybit.account import (
    BybitAccount,
    BybitAccountType,
    BybitOrderStatus,
    BybitOrderType,
    BybitOrderSide,
    BybitTimeInForce,
    BybitMarginMode,
    BybitAccountInfo,
    BybitBalance,
    BybitOrderRequest,
    BybitOrderResponse,
    BybitCredentials,
    BybitApiResponse
)

from trading.exchanges.bybit.converter import (
    BybitConverter,
    BybitToNexusOrderStatus,
    BybitToNexusOrderType,
    BybitToNexusTimeFrame,
    NexusCandle,
    NexusOrderBookLevel,
    NexusOrderBook,
    NexusTicker,
    NexusTrade,
    NexusOrder,
    ConversionStats,
    ConversionMapping
)

from trading.exchanges.bybit.exceptions import (
    BybitErrorCode,
    BybitErrorCategory,
    BybitErrorSeverity,
    BybitException,
    BybitAuthenticationError,
    BybitOrderError,
    BybitAccountError,
    BybitPositionError,
    BybitMarketError,
    BybitRateLimitError,
    BybitValidationError,
    BybitNetworkError,
    BybitErrorHandler
)

from trading.exchanges.bybit.futures import (
    BybitFutures,
    BybitFuturesType,
    BybitFuturesOrderType,
    BybitFuturesOrderSide,
    BybitFuturesPositionSide,
    BybitFuturesTimeInForce,
    BybitFuturesMarginMode,
    BybitFuturesAccountInfo,
    BybitFuturesPosition,
    BybitFuturesOrderRequest,
    BybitFuturesOrderResponse,
    BybitFuturesLeverageRequest,
    BybitFuturesStreamConfig
)

from trading.exchanges.bybit.inverse import (
    BybitInverse,
    BybitInverseOrderType,
    BybitInverseOrderSide,
    BybitInversePositionSide,
    BybitInverseTimeInForce,
    BybitInverseAccountInfo,
    BybitInversePosition,
    BybitInverseOrderRequest,
    BybitInverseOrderResponse,
    BybitInverseLeverageRequest,
    BybitInverseStreamConfig
)

from trading.exchanges.bybit.market import (
    BybitMarket,
    BybitMarketType,
    BybitSymbolStatus,
    BybitKlineInterval,
    BybitSymbolInfo,
    BybitMarketDataRequest,
    BybitMarketDataResponse,
    BybitMarketStreamConfig
)

from trading.exchanges.bybit.option import (
    BybitOption,
    BybitOptionType,
    BybitOptionOrderType,
    BybitOptionOrderSide,
    BybitOptionTimeInForce,
    BybitOptionOrderStatus,
    BybitOptionAccountInfo,
    BybitOptionPosition,
    BybitOptionOrderRequest,
    BybitOptionOrderResponse,
    BybitOptionStreamConfig
)

from trading.exchanges.bybit.order import (
    BybitOrder,
    BybitOrderListStatus,
    BybitOrderListType,
    BybitTriggerBy,
    BybitOCOOrderRequest,
    BybitOCOOrderResponse,
    BybitBracketOrderRequest,
    BybitOrderHistoryRequest,
    BybitOrderBookUpdate
)

from trading.exchanges.bybit.spot import (
    BybitSpot,
    BybitSpotOrderType,
    BybitSpotOrderSide,
    BybitSpotTimeInForce,
    BybitSpotOrderRequest,
    BybitSpotOrderResponse,
    BybitSpotAccountInfo,
    BybitSpotStreamConfig
)

from trading.exchanges.bybit.websocket import (
    BybitWebSocket,
    BybitStreamType,
    BybitStreamAction,
    BybitStreamMessage,
    BybitStreamSubscription,
    BybitWebSocketConnection,
    BybitStreamEvent
)

# Module logger
logger = logging.getLogger(__name__)

# =============================================================================
# Module Metadata
# =============================================================================

__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
__description__ = "Bybit Exchange Integration for NEXUS AI Trading"

# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Base
    'BybitBase',
    'BybitEnvironment',
    'BybitInterval',
    'BybitCategory',
    'BybitDepthLevel',
    'BybitWebSocketChannel',
    'BybitCandle',
    'BybitTicker',
    'BybitOrderBookLevel',
    'BybitOrderBook',
    'BybitTrade',
    'BybitInstrumentInfo',
    'BybitApiLimits',
    'BybitWebSocketMessage',
    'BybitStreamConfig',
    
    # Account
    'BybitAccount',
    'BybitAccountType',
    'BybitOrderStatus',
    'BybitOrderType',
    'BybitOrderSide',
    'BybitTimeInForce',
    'BybitMarginMode',
    'BybitAccountInfo',
    'BybitBalance',
    'BybitOrderRequest',
    'BybitOrderResponse',
    'BybitCredentials',
    'BybitApiResponse',
    
    # Converter
    'BybitConverter',
    'BybitToNexusOrderStatus',
    'BybitToNexusOrderType',
    'BybitToNexusTimeFrame',
    'NexusCandle',
    'NexusOrderBookLevel',
    'NexusOrderBook',
    'NexusTicker',
    'NexusTrade',
    'NexusOrder',
    'ConversionStats',
    'ConversionMapping',
    
    # Exceptions
    'BybitErrorCode',
    'BybitErrorCategory',
    'BybitErrorSeverity',
    'BybitException',
    'BybitAuthenticationError',
    'BybitOrderError',
    'BybitAccountError',
    'BybitPositionError',
    'BybitMarketError',
    'BybitRateLimitError',
    'BybitValidationError',
    'BybitNetworkError',
    'BybitErrorHandler',
    
    # Futures
    'BybitFutures',
    'BybitFuturesType',
    'BybitFuturesOrderType',
    'BybitFuturesOrderSide',
    'BybitFuturesPositionSide',
    'BybitFuturesTimeInForce',
    'BybitFuturesMarginMode',
    'BybitFuturesAccountInfo',
    'BybitFuturesPosition',
    'BybitFuturesOrderRequest',
    'BybitFuturesOrderResponse',
    'BybitFuturesLeverageRequest',
    'BybitFuturesStreamConfig',
    
    # Inverse
    'BybitInverse',
    'BybitInverseOrderType',
    'BybitInverseOrderSide',
    'BybitInversePositionSide',
    'BybitInverseTimeInForce',
    'BybitInverseAccountInfo',
    'BybitInversePosition',
    'BybitInverseOrderRequest',
    'BybitInverseOrderResponse',
    'BybitInverseLeverageRequest',
    'BybitInverseStreamConfig',
    
    # Market
    'BybitMarket',
    'BybitMarketType',
    'BybitSymbolStatus',
    'BybitKlineInterval',
    'BybitSymbolInfo',
    'BybitMarketDataRequest',
    'BybitMarketDataResponse',
    'BybitMarketStreamConfig',
    
    # Option
    'BybitOption',
    'BybitOptionType',
    'BybitOptionOrderType',
    'BybitOptionOrderSide',
    'BybitOptionTimeInForce',
    'BybitOptionOrderStatus',
    'BybitOptionAccountInfo',
    'BybitOptionPosition',
    'BybitOptionOrderRequest',
    'BybitOptionOrderResponse',
    'BybitOptionStreamConfig',
    
    # Order
    'BybitOrder',
    'BybitOrderListStatus',
    'BybitOrderListType',
    'BybitTriggerBy',
    'BybitOCOOrderRequest',
    'BybitOCOOrderResponse',
    'BybitBracketOrderRequest',
    'BybitOrderHistoryRequest',
    'BybitOrderBookUpdate',
    
    # Spot
    'BybitSpot',
    'BybitSpotOrderType',
    'BybitSpotOrderSide',
    'BybitSpotTimeInForce',
    'BybitSpotOrderRequest',
    'BybitSpotOrderResponse',
    'BybitSpotAccountInfo',
    'BybitSpotStreamConfig',
    
    # WebSocket
    'BybitWebSocket',
    'BybitStreamType',
    'BybitStreamAction',
    'BybitStreamMessage',
    'BybitStreamSubscription',
    'BybitWebSocketConnection',
    'BybitStreamEvent'
]

# =============================================================================
# Module Documentation
# =============================================================================

def get_module_info() -> Dict[str, Any]:
    """
    Get module information.
    
    Returns:
        Dict[str, Any]: Module metadata
    """
    return {
        'name': 'trading.exchanges.bybit',
        'version': __version__,
        'author': __author__,
        'description': __description__,
        'components': [
            'BybitBase',
            'BybitAccount',
            'BybitConverter',
            'BybitFutures',
            'BybitInverse',
            'BybitMarket',
            'BybitOption',
            'BybitOrder',
            'BybitSpot',
            'BybitWebSocket'
        ]
    }


def get_component_dependencies() -> Dict[str, List[str]]:
    """
    Get component dependencies.
    
    Returns:
        Dict[str, List[str]]: Component dependencies
    """
    return {
        'BybitBase': ['aiohttp', 'websockets'],
        'BybitAccount': ['BybitBase'],
        'BybitConverter': [],
        'BybitFutures': ['BybitBase', 'BybitAccount'],
        'BybitInverse': ['BybitBase', 'BybitAccount', 'BybitFutures'],
        'BybitMarket': ['BybitBase'],
        'BybitOption': ['BybitBase', 'BybitAccount'],
        'BybitOrder': ['BybitBase', 'BybitAccount'],
        'BybitSpot': ['BybitBase', 'BybitAccount', 'BybitMarket', 'BybitOrder'],
        'BybitWebSocket': ['BybitBase', 'BybitConverter']
    }


def get_default_config() -> Dict[str, Any]:
    """
    Get default configuration for Bybit components.
    
    Returns:
        Dict[str, Any]: Default configuration
    """
    return {
        'environment': 'testnet',
        'category': 'linear',
        'base': {
            'timeout': 30,
            'max_retries': 3,
            'retry_delay': 0.5,
            'rate_limit': 50
        },
        'account': {
            'cache_ttl': 60,
            'include_balances': True,
            'include_positions': True
        },
        'futures': {
            'default_leverage': 1,
            'default_margin_mode': 'ISOLATED',
            'max_leverage': 100
        },
        'inverse': {
            'default_leverage': 1,
            'default_margin_mode': 'ISOLATED',
            'max_leverage': 100
        },
        'market': {
            'default_depth': 'LEVEL_10',
            'default_interval': 'ONE_HOUR',
            'max_candles': 1000
        },
        'option': {
            'default_time_in_force': 'GTC',
            'max_orders': 100
        },
        'order': {
            'default_time_in_force': 'GTC',
            'max_orders': 100,
            'order_timeout': 30
        },
        'spot': {
            'min_order_qty': 0.000001,
            'max_order_qty': 1000000,
            'price_precision': 8,
            'qty_precision': 8
        },
        'websocket': {
            'ping_interval': 20,
            'ping_timeout': 10,
            'reconnect_attempts': 5,
            'reconnect_delay': 1
        }
    }


def initialize_bybit(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Initialize all Bybit components.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Dict[str, Any]: Initialized components
    """
    from trading.exchanges.bybit.account import BybitAccount
    from trading.exchanges.bybit.converter import BybitConverter
    from trading.exchanges.bybit.futures import BybitFutures
    from trading.exchanges.bybit.inverse import BybitInverse
    from trading.exchanges.bybit.market import BybitMarket
    from trading.exchanges.bybit.option import BybitOption
    from trading.exchanges.bybit.order import BybitOrder
    from trading.exchanges.bybit.spot import BybitSpot
    from trading.exchanges.bybit.websocket import BybitWebSocket
    
    config = config or get_default_config()
    env = config.get('environment', 'testnet')
    cat = config.get('category', 'linear')
    
    components = {
        'converter': BybitConverter(),
        'market': BybitMarket(environment=env),
        'websocket': BybitWebSocket(environment=env, category=cat)
    }
    
    logger.info("Bybit components initialized successfully")
    return components


def get_router() -> Any:
    """
    Get FastAPI router for Bybit endpoints.
    
    Returns:
        Any: FastAPI router
    """
    from fastapi import APIRouter
    
    router = APIRouter(prefix="/api/v1/exchanges/bybit", tags=["Bybit"])
    
    # Import all routers
    from trading.exchanges.bybit.account import router as account_router
    from trading.exchanges.bybit.converter import router as converter_router
    from trading.exchanges.bybit.exceptions import router as exceptions_router
    from trading.exchanges.bybit.futures import router as futures_router
    from trading.exchanges.bybit.inverse import router as inverse_router
    from trading.exchanges.bybit.market import router as market_router
    from trading.exchanges.bybit.option import router as option_router
    from trading.exchanges.bybit.order import router as order_router
    from trading.exchanges.bybit.spot import router as spot_router
    from trading.exchanges.bybit.websocket import router as websocket_router
    
    # Include routers
    router.include_router(account_router)
    router.include_router(converter_router)
    router.include_router(exceptions_router)
    router.include_router(futures_router)
    router.include_router(inverse_router)
    router.include_router(market_router)
    router.include_router(option_router)
    router.include_router(order_router)
    router.include_router(spot_router)
    router.include_router(websocket_router)
    
    return router


# =============================================================================
# Module Initialization
# =============================================================================

logger.info(f"Bybit Module v{__version__} loaded successfully")

# Export FastAPI router
bybit_router = get_router()
