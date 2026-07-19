"""
NEXUS AI TRADING SYSTEM - Binance Exchange Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/binance/__init__.py
Description: Binance Exchange module initialization and exports
"""

import logging
from typing import Dict, List, Optional, Any, Type

# Import all Binance components
from trading.exchanges.binance.base import (
    BinanceBase,
    BinanceEnvironment,
    BinanceInterval,
    BinanceDepthLevel,
    BinanceWebSocketChannel,
    BinanceCandle,
    BinanceTicker,
    BinanceOrderBookLevel,
    BinanceOrderBook,
    BinanceTrade,
    BinanceExchangeInfo,
    BinanceApiLimits,
    BinanceWebSocketMessage,
    BinanceStreamConfig
)

from trading.exchanges.binance.account import (
    BinanceAccount,
    BinanceAccountType,
    BinanceOrderStatus,
    BinanceOrderType,
    BinanceOrderSide,
    BinanceTimeInForce,
    BinanceAccountInfo,
    BinanceBalance,
    BinanceOrderRequest,
    BinanceOrderResponse,
    BinanceCredentials,
    BinanceApiResponse
)

from trading.exchanges.binance.converter import (
    BinanceConverter,
    BinanceToNexusOrderStatus,
    BinanceToNexusOrderType,
    BinanceToNexusTimeFrame,
    NexusCandle,
    NexusOrderBookLevel,
    NexusOrderBook,
    NexusTicker,
    NexusOrder,
    ConversionStats,
    ConversionMapping
)

from trading.exchanges.binance.exceptions import (
    BinanceErrorCode,
    BinanceErrorCategory,
    BinanceErrorSeverity,
    BinanceException,
    BinanceAuthenticationError,
    BinanceOrderError,
    BinanceAccountError,
    BinanceMarketError,
    BinanceRateLimitError,
    BinanceValidationError,
    BinanceNetworkError,
    BinanceErrorHandler
)

from trading.exchanges.binance.futures import (
    BinanceFutures,
    BinanceFuturesType,
    BinanceFuturesOrderType,
    BinanceFuturesOrderSide,
    BinanceFuturesPositionSide,
    BinanceFuturesWorkingType,
    BinanceFuturesTimeInForce,
    BinanceFuturesAccountInfo,
    BinanceFuturesPosition,
    BinanceFuturesOrderRequest,
    BinanceFuturesOrderResponse,
    BinanceFuturesLeverageRequest,
    BinanceFuturesMarginTypeRequest,
    BinanceFuturesStreamConfig
)

from trading.exchanges.binance.margin import (
    BinanceMargin,
    BinanceMarginType,
    BinanceMarginOrderType,
    BinanceMarginOrderSide,
    BinanceMarginTimeInForce,
    BinanceMarginAccountInfo,
    BinanceMarginPosition,
    BinanceMarginOrderRequest,
    BinanceMarginOrderResponse,
    BinanceMarginTransferRequest,
    BinanceMarginLoanRequest,
    BinanceMarginRepayRequest,
    BinanceMarginStreamConfig
)

from trading.exchanges.binance.market import (
    BinanceMarket,
    BinanceMarketType,
    BinanceSymbolStatus,
    BinanceKlineInterval,
    BinanceSymbolInfo,
    BinanceMarketDataRequest,
    BinanceMarketDataResponse,
    BinanceMarketStreamConfig
)

from trading.exchanges.binance.order import (
    BinanceOrder,
    BinanceOrderListStatus,
    BinanceOrderListType,
    BinanceOCOOrderRequest,
    BinanceOCOOrderResponse,
    BinanceOrderHistoryRequest,
    BinanceOrderBookUpdate
)

from trading.exchanges.binance.spot import (
    BinanceSpot,
    BinanceSpotOrderType,
    BinanceSpotOrderSide,
    BinanceSpotTimeInForce,
    BinanceSpotOrderRequest,
    BinanceSpotOrderResponse,
    BinanceSpotAccountInfo,
    BinanceSpotStreamConfig
)

from trading.exchanges.binance.websocket import (
    BinanceWebSocket,
    BinanceStreamType,
    BinanceStreamAction,
    BinanceStreamMessage,
    BinanceStreamSubscription,
    BinanceUserDataStream,
    BinanceWebSocketConnection,
    BinanceStreamEvent
)

# Module logger
logger = logging.getLogger(__name__)

# =============================================================================
# Module Metadata
# =============================================================================

__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
__description__ = "Binance Exchange Integration for NEXUS AI Trading"

# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Base
    'BinanceBase',
    'BinanceEnvironment',
    'BinanceInterval',
    'BinanceDepthLevel',
    'BinanceWebSocketChannel',
    'BinanceCandle',
    'BinanceTicker',
    'BinanceOrderBookLevel',
    'BinanceOrderBook',
    'BinanceTrade',
    'BinanceExchangeInfo',
    'BinanceApiLimits',
    'BinanceWebSocketMessage',
    'BinanceStreamConfig',
    
    # Account
    'BinanceAccount',
    'BinanceAccountType',
    'BinanceOrderStatus',
    'BinanceOrderType',
    'BinanceOrderSide',
    'BinanceTimeInForce',
    'BinanceAccountInfo',
    'BinanceBalance',
    'BinanceOrderRequest',
    'BinanceOrderResponse',
    'BinanceCredentials',
    'BinanceApiResponse',
    
    # Converter
    'BinanceConverter',
    'BinanceToNexusOrderStatus',
    'BinanceToNexusOrderType',
    'BinanceToNexusTimeFrame',
    'NexusCandle',
    'NexusOrderBookLevel',
    'NexusOrderBook',
    'NexusTicker',
    'NexusOrder',
    'ConversionStats',
    'ConversionMapping',
    
    # Exceptions
    'BinanceErrorCode',
    'BinanceErrorCategory',
    'BinanceErrorSeverity',
    'BinanceException',
    'BinanceAuthenticationError',
    'BinanceOrderError',
    'BinanceAccountError',
    'BinanceMarketError',
    'BinanceRateLimitError',
    'BinanceValidationError',
    'BinanceNetworkError',
    'BinanceErrorHandler',
    
    # Futures
    'BinanceFutures',
    'BinanceFuturesType',
    'BinanceFuturesOrderType',
    'BinanceFuturesOrderSide',
    'BinanceFuturesPositionSide',
    'BinanceFuturesWorkingType',
    'BinanceFuturesTimeInForce',
    'BinanceFuturesAccountInfo',
    'BinanceFuturesPosition',
    'BinanceFuturesOrderRequest',
    'BinanceFuturesOrderResponse',
    'BinanceFuturesLeverageRequest',
    'BinanceFuturesMarginTypeRequest',
    'BinanceFuturesStreamConfig',
    
    # Margin
    'BinanceMargin',
    'BinanceMarginType',
    'BinanceMarginOrderType',
    'BinanceMarginOrderSide',
    'BinanceMarginTimeInForce',
    'BinanceMarginAccountInfo',
    'BinanceMarginPosition',
    'BinanceMarginOrderRequest',
    'BinanceMarginOrderResponse',
    'BinanceMarginTransferRequest',
    'BinanceMarginLoanRequest',
    'BinanceMarginRepayRequest',
    'BinanceMarginStreamConfig',
    
    # Market
    'BinanceMarket',
    'BinanceMarketType',
    'BinanceSymbolStatus',
    'BinanceKlineInterval',
    'BinanceSymbolInfo',
    'BinanceMarketDataRequest',
    'BinanceMarketDataResponse',
    'BinanceMarketStreamConfig',
    
    # Order
    'BinanceOrder',
    'BinanceOrderListStatus',
    'BinanceOrderListType',
    'BinanceOCOOrderRequest',
    'BinanceOCOOrderResponse',
    'BinanceOrderHistoryRequest',
    'BinanceOrderBookUpdate',
    
    # Spot
    'BinanceSpot',
    'BinanceSpotOrderType',
    'BinanceSpotOrderSide',
    'BinanceSpotTimeInForce',
    'BinanceSpotOrderRequest',
    'BinanceSpotOrderResponse',
    'BinanceSpotAccountInfo',
    'BinanceSpotStreamConfig',
    
    # WebSocket
    'BinanceWebSocket',
    'BinanceStreamType',
    'BinanceStreamAction',
    'BinanceStreamMessage',
    'BinanceStreamSubscription',
    'BinanceUserDataStream',
    'BinanceWebSocketConnection',
    'BinanceStreamEvent'
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
        'name': 'trading.exchanges.binance',
        'version': __version__,
        'author': __author__,
        'description': __description__,
        'components': [
            'BinanceBase',
            'BinanceAccount',
            'BinanceConverter',
            'BinanceFutures',
            'BinanceMargin',
            'BinanceMarket',
            'BinanceOrder',
            'BinanceSpot',
            'BinanceWebSocket'
        ]
    }


def get_component_dependencies() -> Dict[str, List[str]]:
    """
    Get component dependencies.
    
    Returns:
        Dict[str, List[str]]: Component dependencies
    """
    return {
        'BinanceBase': ['aiohttp', 'websockets'],
        'BinanceAccount': ['BinanceBase'],
        'BinanceConverter': [],
        'BinanceFutures': ['BinanceBase', 'BinanceAccount'],
        'BinanceMargin': ['BinanceBase', 'BinanceAccount'],
        'BinanceMarket': ['BinanceBase'],
        'BinanceOrder': ['BinanceBase', 'BinanceAccount'],
        'BinanceSpot': ['BinanceBase', 'BinanceAccount', 'BinanceMarket', 'BinanceOrder'],
        'BinanceWebSocket': ['BinanceBase', 'BinanceConverter']
    }


def get_default_config() -> Dict[str, Any]:
    """
    Get default configuration for Binance components.
    
    Returns:
        Dict[str, Any]: Default configuration
    """
    return {
        'environment': 'testnet',
        'base': {
            'timeout': 30,
            'max_retries': 3,
            'retry_delay': 1.0,
            'rate_limit': 1200
        },
        'account': {
            'cache_ttl': 60,
            'include_balances': True,
            'include_positions': True
        },
        'futures': {
            'default_leverage': 1,
            'default_margin_type': 'ISOLATED',
            'max_leverage': 125
        },
        'margin': {
            'default_margin_type': 'CROSS',
            'transfer_timeout': 30
        },
        'market': {
            'default_depth': 'LEVEL_10',
            'default_interval': 'ONE_HOUR',
            'max_candles': 1000
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
            'ping_interval': 30,
            'ping_timeout': 10,
            'reconnect_attempts': 5,
            'reconnect_delay': 1
        }
    }


def initialize_binance(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Initialize all Binance components.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Dict[str, Any]: Initialized components
    """
    from trading.exchanges.binance.account import BinanceAccount
    from trading.exchanges.binance.converter import BinanceConverter
    from trading.exchanges.binance.futures import BinanceFutures
    from trading.exchanges.binance.margin import BinanceMargin
    from trading.exchanges.binance.market import BinanceMarket
    from trading.exchanges.binance.order import BinanceOrder
    from trading.exchanges.binance.spot import BinanceSpot
    from trading.exchanges.binance.websocket import BinanceWebSocket
    
    config = config or get_default_config()
    env = config.get('environment', 'testnet')
    
    components = {
        'converter': BinanceConverter(),
        'market': BinanceMarket(environment=env),
        'websocket': BinanceWebSocket(environment=env)
    }
    
    logger.info("Binance components initialized successfully")
    return components


def get_router() -> Any:
    """
    Get FastAPI router for Binance endpoints.
    
    Returns:
        Any: FastAPI router
    """
    from fastapi import APIRouter
    
    router = APIRouter(prefix="/api/v1/exchanges/binance", tags=["Binance"])
    
    # Import all routers
    from trading.exchanges.binance.account import router as account_router
    from trading.exchanges.binance.converter import router as converter_router
    from trading.exchanges.binance.exceptions import router as exceptions_router
    from trading.exchanges.binance.futures import router as futures_router
    from trading.exchanges.binance.margin import router as margin_router
    from trading.exchanges.binance.market import router as market_router
    from trading.exchanges.binance.order import router as order_router
    from trading.exchanges.binance.spot import router as spot_router
    from trading.exchanges.binance.websocket import router as websocket_router
    
    # Include routers
    router.include_router(account_router)
    router.include_router(converter_router)
    router.include_router(exceptions_router)
    router.include_router(futures_router)
    router.include_router(margin_router)
    router.include_router(market_router)
    router.include_router(order_router)
    router.include_router(spot_router)
    router.include_router(websocket_router)
    
    return router


# =============================================================================
# Module Initialization
# =============================================================================

logger.info(f"Binance Module v{__version__} loaded successfully")

# Export FastAPI router
binance_router = get_router()
