"""
NEXUS AI TRADING SYSTEM - Coinbase Exchange Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/coinbase/__init__.py
Description: Coinbase Exchange module initialization and exports
"""

import logging
from typing import Dict, List, Optional, Any, Type

# Import all Coinbase components
from trading.exchanges.coinbase.base import (
    CoinbaseBase,
    CoinbaseEnvironment,
    CoinbaseProductType,
    CoinbaseGranularity,
    CoinbaseWebSocketChannel,
    CoinbaseCandle,
    CoinbaseTicker,
    CoinbaseOrderBookLevel,
    CoinbaseOrderBook,
    CoinbaseTrade,
    CoinbaseProductInfo,
    CoinbaseApiLimits,
    CoinbaseWebSocketMessage,
    CoinbaseStreamConfig
)

from trading.exchanges.coinbase.account import (
    CoinbaseAccount,
    CoinbaseAccountType,
    CoinbaseOrderStatus,
    CoinbaseOrderType,
    CoinbaseOrderSide,
    CoinbaseTimeInForce,
    CoinbaseAccountInfo,
    CoinbaseBalance,
    CoinbaseOrderRequest,
    CoinbaseOrderResponse,
    CoinbaseCredentials,
    CoinbaseApiResponse
)

from trading.exchanges.coinbase.converter import (
    CoinbaseConverter,
    CoinbaseToNexusOrderStatus,
    CoinbaseToNexusOrderType,
    CoinbaseToNexusTimeFrame,
    NexusCandle,
    NexusOrderBookLevel,
    NexusOrderBook,
    NexusTicker,
    NexusTrade,
    NexusOrder,
    ConversionStats,
    ConversionMapping
)

from trading.exchanges.coinbase.exceptions import (
    CoinbaseErrorCode,
    CoinbaseErrorCategory,
    CoinbaseErrorSeverity,
    CoinbaseException,
    CoinbaseAuthenticationError,
    CoinbaseOrderError,
    CoinbaseAccountError,
    CoinbaseProductError,
    CoinbaseRateLimitError,
    CoinbaseValidationError,
    CoinbaseNetworkError,
    CoinbaseErrorHandler
)

from trading.exchanges.coinbase.market import (
    CoinbaseMarket,
    CoinbaseMarketType,
    CoinbaseProductStatus,
    CoinbaseMarketDataRequest,
    CoinbaseMarketDataResponse,
    CoinbaseMarketStreamConfig
)

from trading.exchanges.coinbase.order import (
    CoinbaseOrder,
    CoinbaseOrderListStatus,
    CoinbaseOrderListType,
    CoinbaseStopDirection,
    CoinbaseOCOOrderRequest,
    CoinbaseOCOOrderResponse,
    CoinbaseBracketOrderRequest,
    CoinbaseOrderHistoryRequest,
    CoinbaseOrderBookUpdate
)

from trading.exchanges.coinbase.spot import (
    CoinbaseSpot,
    CoinbaseSpotOrderType,
    CoinbaseSpotOrderSide,
    CoinbaseSpotTimeInForce,
    CoinbaseSpotOrderRequest,
    CoinbaseSpotOrderResponse,
    CoinbaseSpotAccountInfo,
    CoinbaseSpotStreamConfig
)

from trading.exchanges.coinbase.websocket import (
    CoinbaseWebSocket,
    CoinbaseStreamType,
    CoinbaseStreamAction,
    CoinbaseStreamMessage,
    CoinbaseStreamSubscription,
    CoinbaseWebSocketConnection,
    CoinbaseStreamEvent
)

# Module logger
logger = logging.getLogger(__name__)

# =============================================================================
# Module Metadata
# =============================================================================

__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
__description__ = "Coinbase Exchange Integration for NEXUS AI Trading"

# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Base
    'CoinbaseBase',
    'CoinbaseEnvironment',
    'CoinbaseProductType',
    'CoinbaseGranularity',
    'CoinbaseWebSocketChannel',
    'CoinbaseCandle',
    'CoinbaseTicker',
    'CoinbaseOrderBookLevel',
    'CoinbaseOrderBook',
    'CoinbaseTrade',
    'CoinbaseProductInfo',
    'CoinbaseApiLimits',
    'CoinbaseWebSocketMessage',
    'CoinbaseStreamConfig',
    
    # Account
    'CoinbaseAccount',
    'CoinbaseAccountType',
    'CoinbaseOrderStatus',
    'CoinbaseOrderType',
    'CoinbaseOrderSide',
    'CoinbaseTimeInForce',
    'CoinbaseAccountInfo',
    'CoinbaseBalance',
    'CoinbaseOrderRequest',
    'CoinbaseOrderResponse',
    'CoinbaseCredentials',
    'CoinbaseApiResponse',
    
    # Converter
    'CoinbaseConverter',
    'CoinbaseToNexusOrderStatus',
    'CoinbaseToNexusOrderType',
    'CoinbaseToNexusTimeFrame',
    'NexusCandle',
    'NexusOrderBookLevel',
    'NexusOrderBook',
    'NexusTicker',
    'NexusTrade',
    'NexusOrder',
    'ConversionStats',
    'ConversionMapping',
    
    # Exceptions
    'CoinbaseErrorCode',
    'CoinbaseErrorCategory',
    'CoinbaseErrorSeverity',
    'CoinbaseException',
    'CoinbaseAuthenticationError',
    'CoinbaseOrderError',
    'CoinbaseAccountError',
    'CoinbaseProductError',
    'CoinbaseRateLimitError',
    'CoinbaseValidationError',
    'CoinbaseNetworkError',
    'CoinbaseErrorHandler',
    
    # Market
    'CoinbaseMarket',
    'CoinbaseMarketType',
    'CoinbaseProductStatus',
    'CoinbaseMarketDataRequest',
    'CoinbaseMarketDataResponse',
    'CoinbaseMarketStreamConfig',
    
    # Order
    'CoinbaseOrder',
    'CoinbaseOrderListStatus',
    'CoinbaseOrderListType',
    'CoinbaseStopDirection',
    'CoinbaseOCOOrderRequest',
    'CoinbaseOCOOrderResponse',
    'CoinbaseBracketOrderRequest',
    'CoinbaseOrderHistoryRequest',
    'CoinbaseOrderBookUpdate',
    
    # Spot
    'CoinbaseSpot',
    'CoinbaseSpotOrderType',
    'CoinbaseSpotOrderSide',
    'CoinbaseSpotTimeInForce',
    'CoinbaseSpotOrderRequest',
    'CoinbaseSpotOrderResponse',
    'CoinbaseSpotAccountInfo',
    'CoinbaseSpotStreamConfig',
    
    # WebSocket
    'CoinbaseWebSocket',
    'CoinbaseStreamType',
    'CoinbaseStreamAction',
    'CoinbaseStreamMessage',
    'CoinbaseStreamSubscription',
    'CoinbaseWebSocketConnection',
    'CoinbaseStreamEvent'
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
        'name': 'trading.exchanges.coinbase',
        'version': __version__,
        'author': __author__,
        'description': __description__,
        'components': [
            'CoinbaseBase',
            'CoinbaseAccount',
            'CoinbaseConverter',
            'CoinbaseMarket',
            'CoinbaseOrder',
            'CoinbaseSpot',
            'CoinbaseWebSocket'
        ]
    }


def get_component_dependencies() -> Dict[str, List[str]]:
    """
    Get component dependencies.
    
    Returns:
        Dict[str, List[str]]: Component dependencies
    """
    return {
        'CoinbaseBase': ['aiohttp', 'websockets'],
        'CoinbaseAccount': ['CoinbaseBase'],
        'CoinbaseConverter': [],
        'CoinbaseMarket': ['CoinbaseBase'],
        'CoinbaseOrder': ['CoinbaseBase', 'CoinbaseAccount'],
        'CoinbaseSpot': ['CoinbaseBase', 'CoinbaseAccount', 'CoinbaseMarket', 'CoinbaseOrder'],
        'CoinbaseWebSocket': ['CoinbaseBase', 'CoinbaseConverter']
    }


def get_default_config() -> Dict[str, Any]:
    """
    Get default configuration for Coinbase components.
    
    Returns:
        Dict[str, Any]: Default configuration
    """
    return {
        'environment': 'sandbox',
        'base': {
            'timeout': 30,
            'max_retries': 3,
            'retry_delay': 0.5,
            'rate_limit': 10
        },
        'account': {
            'cache_ttl': 60,
            'include_balances': True
        },
        'market': {
            'default_granularity': 'ONE_HOUR',
            'max_candles': 1000,
            'default_order_book_level': 2
        },
        'order': {
            'default_time_in_force': 'GTC',
            'max_orders': 100,
            'order_timeout': 30
        },
        'spot': {
            'min_order_size': 0.000001,
            'max_order_size': 1000000,
            'price_precision': 8,
            'size_precision': 8
        },
        'websocket': {
            'ping_interval': 20,
            'ping_timeout': 10,
            'reconnect_attempts': 5,
            'reconnect_delay': 1
        }
    }


def initialize_coinbase(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Initialize all Coinbase components.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Dict[str, Any]: Initialized components
    """
    from trading.exchanges.coinbase.account import CoinbaseAccount
    from trading.exchanges.coinbase.converter import CoinbaseConverter
    from trading.exchanges.coinbase.market import CoinbaseMarket
    from trading.exchanges.coinbase.order import CoinbaseOrder
    from trading.exchanges.coinbase.spot import CoinbaseSpot
    from trading.exchanges.coinbase.websocket import CoinbaseWebSocket
    
    config = config or get_default_config()
    env = config.get('environment', 'sandbox')
    
    components = {
        'converter': CoinbaseConverter(),
        'market': CoinbaseMarket(environment=env),
        'websocket': CoinbaseWebSocket(environment=env)
    }
    
    logger.info("Coinbase components initialized successfully")
    return components


def get_router() -> Any:
    """
    Get FastAPI router for Coinbase endpoints.
    
    Returns:
        Any: FastAPI router
    """
    from fastapi import APIRouter
    
    router = APIRouter(prefix="/api/v1/exchanges/coinbase", tags=["Coinbase"])
    
    # Import all routers
    from trading.exchanges.coinbase.account import router as account_router
    from trading.exchanges.coinbase.converter import router as converter_router
    from trading.exchanges.coinbase.exceptions import router as exceptions_router
    from trading.exchanges.coinbase.market import router as market_router
    from trading.exchanges.coinbase.order import router as order_router
    from trading.exchanges.coinbase.spot import router as spot_router
    from trading.exchanges.coinbase.websocket import router as websocket_router
    
    # Include routers
    router.include_router(account_router)
    router.include_router(converter_router)
    router.include_router(exceptions_router)
    router.include_router(market_router)
    router.include_router(order_router)
    router.include_router(spot_router)
    router.include_router(websocket_router)
    
    return router


# =============================================================================
# Module Initialization
# =============================================================================

logger.info(f"Coinbase Module v{__version__} loaded successfully")

# Export FastAPI router
coinbase_router = get_router()
