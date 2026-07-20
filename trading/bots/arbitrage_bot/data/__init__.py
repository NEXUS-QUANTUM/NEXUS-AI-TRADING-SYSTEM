"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Data Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Data management module for arbitrage bot with:
- Price management
- Order book management
- Spread management
- Ticker management
- Trade management
- Volume management
- WebSocket management
- Data caching and storage
- Data validation and normalization
- Candle management
- Depth management
- Liquidity management
"""

import asyncio
import logging
from typing import Optional, Any, Dict, List, Union, Tuple, Callable, Awaitable

# Base imports
from .base import (
    BaseDataManager,
    BasePriceManager,
    BaseOrderBookManager,
    BaseSpreadManager,
    BaseTickerManager,
    BaseTradeManager,
    BaseVolumeManager,
    BaseWebSocketManager,
    BaseDataAggregator,
    BaseDataProcessor,
    BaseDataValidator,
    BaseDataNormalizer,
    BaseDataCache,
    BaseDataStorage,
    BaseDataStream,
    BaseCandleManager,
    BaseDepthManager,
    BaseLiquidityManager,
)

# Managers
from .price_manager import (
    PriceManager,
    PriceSource,
    NormalizedPrice,
    PriceSnapshot,
    PriceSourceType,
    PriceConsensusMethod,
    AnomalyDetectionMethod,
    PriceManagerConfig,
    PriceUpdateResult,
    PriceStatistics,
    create_price_manager,
)

from .order_book_manager import (
    OrderBookManager,
    OrderBook,
    OrderBookEntry,
    OrderBookSnapshot,
    OrderBookLevel,
    OrderBookDepth,
    OrderBookStats,
    OrderBookConfig,
    OrderBookUpdate,
    OrderBookSide,
    create_order_book_manager,
)

from .spread_manager import (
    SpreadManager,
    SpreadData,
    CrossExchangeSpread,
    SpreadSnapshot,
    SpreadStatistics,
    SpreadType,
    SpreadDirection,
    SpreadQuality,
    SpreadManagerConfig,
    create_spread_manager,
)

from .ticker_manager import (
    TickerManager,
    TickerData,
    TickerSnapshot,
    TickerStatistics,
    TickerQuality,
    TickerTrend,
    VolumeLevel,
    TickerManagerConfig,
    create_ticker_manager,
)

from .trade_manager import (
    TradeManager,
    Order,
    Trade,
    Position,
    ArbitrageTrade,
    TradeResult,
    OrderType,
    OrderSide,
    OrderStatus,
    TimeInForce,
    TradeType,
    TradeStatus,
    TradeManagerConfig,
    create_trade_manager,
)

from .volume_manager import (
    VolumeManager,
    VolumeData,
    VolumeSnapshot,
    VolumeStatistics,
    VolumeAnomaly,
    VolumeLevel,
    VolumeTrend,
    VolumeQuality,
    VolumeManagerConfig,
    create_volume_manager,
)

from .websocket_manager import (
    WebSocketManager,
    WebSocketMessage,
    WebSocketConnection,
    WebSocketMetrics,
    ConnectionState,
    MessageType,
    ExchangeWebSocketConfig,
    WebSocketManagerConfig,
    create_websocket_manager,
)

# Data utilities
from .data_aggregator import (
    DataAggregator,
    DataAggregatorConfig,
    AggregationMethod,
    AggregationResult,
)

from .data_processor import (
    DataProcessor,
    DataProcessorConfig,
    ProcessingStep,
    ProcessingPipeline,
    ProcessedData,
)

from .data_validator import (
    DataValidator,
    DataValidatorConfig,
    ValidationResult,
    ValidationRule,
    ValidationSeverity,
)

from .data_normalizer import (
    DataNormalizer,
    DataNormalizerConfig,
    NormalizationMethod,
    NormalizedResult,
)

from .data_cache import (
    DataCache,
    DataCacheConfig,
    CacheStrategy,
    CacheEntry,
    CacheStats,
)

from .data_storage import (
    DataStorage,
    DataStorageConfig,
    StorageType,
    StorageResult,
    StorageQuery,
)

from .data_stream import (
    DataStream,
    DataStreamConfig,
    StreamType,
    StreamMessage,
    StreamSubscription,
)

# Additional managers
from .candle_manager import (
    CandleManager,
    CandleData,
    CandleSnapshot,
    CandleInterval,
    CandleType,
    CandleStatistics,
    CandleManagerConfig,
    create_candle_manager,
)

from .depth_manager import (
    DepthManager,
    DepthData,
    DepthSnapshot,
    DepthLevel,
    DepthStats,
    DepthManagerConfig,
    create_depth_manager,
)

from .liquidity_manager import (
    LiquidityManager,
    LiquidityData,
    LiquiditySnapshot,
    LiquidityMetrics,
    LiquidityLevel,
    LiquidityManagerConfig,
    create_liquidity_manager,
)

# Exceptions
from .exceptions import (
    DataManagerError,
    PriceManagerError,
    OrderBookManagerError,
    SpreadManagerError,
    TickerManagerError,
    TradeManagerError,
    VolumeManagerError,
    WebSocketManagerError,
    DataValidationError,
    DataNormalizationError,
    DataCacheError,
    DataStorageError,
    DataStreamError,
    DataAggregationError,
    DataProcessingError,
    CandleManagerError,
    DepthManagerError,
    LiquidityManagerError,
    PriceNotFoundError,
    OrderBookNotFoundError,
    SpreadNotFoundError,
    TickerNotFoundError,
    TradeNotFoundError,
    VolumeNotFoundError,
    PriceTimeoutError,
    OrderBookTimeoutError,
    SpreadTimeoutError,
    TickerTimeoutError,
    TradeTimeoutError,
    VolumeTimeoutError,
    WebSocketTimeoutError,
    WebSocketConnectionError,
    WebSocketSubscriptionError,
    WebSocketMessageError,
    PriceValidationError,
    OrderBookValidationError,
    SpreadValidationError,
    TickerValidationError,
    TradeValidationError,
    VolumeValidationError,
    RateLimitExceededError,
    ExchangeConnectionError,
    SlippageError,
    TradeExecutionError,
)

# Constants
from .constants import (
    DEFAULT_FEE_RATES,
    EXCHANGE_FEE_RATES,
    PRICE_CACHE_TTL,
    ORDER_BOOK_CACHE_TTL,
    TICKER_CACHE_TTL,
    VOLUME_CACHE_TTL,
    SPREAD_CACHE_TTL,
    TRADE_CACHE_TTL,
    CANDLE_CACHE_TTL,
    DEPTH_CACHE_TTL,
    LIQUIDITY_CACHE_TTL,
    WEBSOCKET_RECONNECT_DELAY,
    WEBSOCKET_MAX_RECONNECT_ATTEMPTS,
    WEBSOCKET_HEARTBEAT_INTERVAL,
    WEBSOCKET_MESSAGE_TIMEOUT,
    MAX_PRICE_HISTORY,
    MAX_ORDER_BOOK_HISTORY,
    MAX_TICKER_HISTORY,
    MAX_VOLUME_HISTORY,
    MAX_SPREAD_HISTORY,
    MAX_TRADE_HISTORY,
    MAX_CANDLE_HISTORY,
    MAX_DEPTH_HISTORY,
    DEFAULT_SLIPPAGE_TOLERANCE,
    DEFAULT_MAX_RETRIES,
    VOLUME_WEIGHTING_FACTOR,
    SPREAD_ANOMALY_THRESHOLD,
    TICKER_ANOMALY_THRESHOLD,
    VOLUME_ANOMALY_THRESHOLD,
    PRICE_ANOMALY_THRESHOLD,
    ORDER_BOOK_ANOMALY_THRESHOLD,
    CANDLE_ANOMALY_THRESHOLD,
    DEPTH_ANOMALY_THRESHOLD,
    LIQUIDITY_ANOMALY_THRESHOLD,
    MIN_PRICE_AGE_SECONDS,
    MAX_PRICE_AGE_SECONDS,
    PRICE_UPDATE_TIMEOUT,
    RETRY_ATTEMPTS,
    RETRY_WAIT_SECONDS,
    ORDER_TYPES,
    ORDER_SIDES,
    ORDER_STATUS,
    TRADE_CACHE_TTL,
    MAX_TRADE_HISTORY,
    WEBSOCKET_QUEUE_SIZE,
    DEFAULT_VOLUME_THRESHOLD,
    DEFAULT_CHANGE_THRESHOLD,
)

# Config
from .config import (
    DataManagerConfig,
    PriceManagerConfig,
    OrderBookManagerConfig,
    SpreadManagerConfig,
    TickerManagerConfig,
    TradeManagerConfig,
    VolumeManagerConfig,
    WebSocketManagerConfig,
    DataAggregatorConfig,
    DataProcessorConfig,
    DataValidatorConfig,
    DataNormalizerConfig,
    DataCacheConfig,
    DataStorageConfig,
    DataStreamConfig,
    CandleManagerConfig,
    DepthManagerConfig,
    LiquidityManagerConfig,
)

# Setup logging
logger = logging.getLogger(__name__)

# Version
__version__ = "3.0.0"

# Exports
__all__ = [
    # Base classes
    'BaseDataManager',
    'BasePriceManager',
    'BaseOrderBookManager',
    'BaseSpreadManager',
    'BaseTickerManager',
    'BaseTradeManager',
    'BaseVolumeManager',
    'BaseWebSocketManager',
    'BaseDataAggregator',
    'BaseDataProcessor',
    'BaseDataValidator',
    'BaseDataNormalizer',
    'BaseDataCache',
    'BaseDataStorage',
    'BaseDataStream',
    'BaseCandleManager',
    'BaseDepthManager',
    'BaseLiquidityManager',
    
    # Price Manager
    'PriceManager',
    'PriceSource',
    'NormalizedPrice',
    'PriceSnapshot',
    'PriceSourceType',
    'PriceConsensusMethod',
    'AnomalyDetectionMethod',
    'PriceManagerConfig',
    'PriceUpdateResult',
    'PriceStatistics',
    'create_price_manager',
    
    # Order Book Manager
    'OrderBookManager',
    'OrderBook',
    'OrderBookEntry',
    'OrderBookSnapshot',
    'OrderBookLevel',
    'OrderBookDepth',
    'OrderBookStats',
    'OrderBookConfig',
    'OrderBookUpdate',
    'OrderBookSide',
    'create_order_book_manager',
    
    # Spread Manager
    'SpreadManager',
    'SpreadData',
    'CrossExchangeSpread',
    'SpreadSnapshot',
    'SpreadStatistics',
    'SpreadType',
    'SpreadDirection',
    'SpreadQuality',
    'SpreadManagerConfig',
    'create_spread_manager',
    
    # Ticker Manager
    'TickerManager',
    'TickerData',
    'TickerSnapshot',
    'TickerStatistics',
    'TickerQuality',
    'TickerTrend',
    'VolumeLevel',
    'TickerManagerConfig',
    'create_ticker_manager',
    
    # Trade Manager
    'TradeManager',
    'Order',
    'Trade',
    'Position',
    'ArbitrageTrade',
    'TradeResult',
    'OrderType',
    'OrderSide',
    'OrderStatus',
    'TimeInForce',
    'TradeType',
    'TradeStatus',
    'TradeManagerConfig',
    'create_trade_manager',
    
    # Volume Manager
    'VolumeManager',
    'VolumeData',
    'VolumeSnapshot',
    'VolumeStatistics',
    'VolumeAnomaly',
    'VolumeLevel',
    'VolumeTrend',
    'VolumeQuality',
    'VolumeManagerConfig',
    'create_volume_manager',
    
    # WebSocket Manager
    'WebSocketManager',
    'WebSocketMessage',
    'WebSocketConnection',
    'WebSocketMetrics',
    'ConnectionState',
    'MessageType',
    'ExchangeWebSocketConfig',
    'WebSocketManagerConfig',
    'create_websocket_manager',
    
    # Data utilities
    'DataAggregator',
    'DataAggregatorConfig',
    'AggregationMethod',
    'AggregationResult',
    'DataProcessor',
    'DataProcessorConfig',
    'ProcessingStep',
    'ProcessingPipeline',
    'ProcessedData',
    'DataValidator',
    'DataValidatorConfig',
    'ValidationResult',
    'ValidationRule',
    'ValidationSeverity',
    'DataNormalizer',
    'DataNormalizerConfig',
    'NormalizationMethod',
    'NormalizedResult',
    'DataCache',
    'DataCacheConfig',
    'CacheStrategy',
    'CacheEntry',
    'CacheStats',
    'DataStorage',
    'DataStorageConfig',
    'StorageType',
    'StorageResult',
    'StorageQuery',
    'DataStream',
    'DataStreamConfig',
    'StreamType',
    'StreamMessage',
    'StreamSubscription',
    
    # Additional managers
    'CandleManager',
    'CandleData',
    'CandleSnapshot',
    'CandleInterval',
    'CandleType',
    'CandleStatistics',
    'CandleManagerConfig',
    'create_candle_manager',
    'DepthManager',
    'DepthData',
    'DepthSnapshot',
    'DepthLevel',
    'DepthStats',
    'DepthManagerConfig',
    'create_depth_manager',
    'LiquidityManager',
    'LiquidityData',
    'LiquiditySnapshot',
    'LiquidityMetrics',
    'LiquidityLevel',
    'LiquidityManagerConfig',
    'create_liquidity_manager',
    
    # Exceptions
    'DataManagerError',
    'PriceManagerError',
    'OrderBookManagerError',
    'SpreadManagerError',
    'TickerManagerError',
    'TradeManagerError',
    'VolumeManagerError',
    'WebSocketManagerError',
    'DataValidationError',
    'DataNormalizationError',
    'DataCacheError',
    'DataStorageError',
    'DataStreamError',
    'DataAggregationError',
    'DataProcessingError',
    'CandleManagerError',
    'DepthManagerError',
    'LiquidityManagerError',
    'PriceNotFoundError',
    'OrderBookNotFoundError',
    'SpreadNotFoundError',
    'TickerNotFoundError',
    'TradeNotFoundError',
    'VolumeNotFoundError',
    'PriceTimeoutError',
    'OrderBookTimeoutError',
    'SpreadTimeoutError',
    'TickerTimeoutError',
    'TradeTimeoutError',
    'VolumeTimeoutError',
    'WebSocketTimeoutError',
    'WebSocketConnectionError',
    'WebSocketSubscriptionError',
    'WebSocketMessageError',
    'PriceValidationError',
    'OrderBookValidationError',
    'SpreadValidationError',
    'TickerValidationError',
    'TradeValidationError',
    'VolumeValidationError',
    'RateLimitExceededError',
    'ExchangeConnectionError',
    'SlippageError',
    'TradeExecutionError',
    
    # Constants
    'DEFAULT_FEE_RATES',
    'EXCHANGE_FEE_RATES',
    'PRICE_CACHE_TTL',
    'ORDER_BOOK_CACHE_TTL',
    'TICKER_CACHE_TTL',
    'VOLUME_CACHE_TTL',
    'SPREAD_CACHE_TTL',
    'TRADE_CACHE_TTL',
    'CANDLE_CACHE_TTL',
    'DEPTH_CACHE_TTL',
    'LIQUIDITY_CACHE_TTL',
    'WEBSOCKET_RECONNECT_DELAY',
    'WEBSOCKET_MAX_RECONNECT_ATTEMPTS',
    'WEBSOCKET_HEARTBEAT_INTERVAL',
    'WEBSOCKET_MESSAGE_TIMEOUT',
    'MAX_PRICE_HISTORY',
    'MAX_ORDER_BOOK_HISTORY',
    'MAX_TICKER_HISTORY',
    'MAX_VOLUME_HISTORY',
    'MAX_SPREAD_HISTORY',
    'MAX_TRADE_HISTORY',
    'MAX_CANDLE_HISTORY',
    'MAX_DEPTH_HISTORY',
    'DEFAULT_SLIPPAGE_TOLERANCE',
    'DEFAULT_MAX_RETRIES',
    'VOLUME_WEIGHTING_FACTOR',
    'SPREAD_ANOMALY_THRESHOLD',
    'TICKER_ANOMALY_THRESHOLD',
    'VOLUME_ANOMALY_THRESHOLD',
    'PRICE_ANOMALY_THRESHOLD',
    'ORDER_BOOK_ANOMALY_THRESHOLD',
    'CANDLE_ANOMALY_THRESHOLD',
    'DEPTH_ANOMALY_THRESHOLD',
    'LIQUIDITY_ANOMALY_THRESHOLD',
    'MIN_PRICE_AGE_SECONDS',
    'MAX_PRICE_AGE_SECONDS',
    'PRICE_UPDATE_TIMEOUT',
    'RETRY_ATTEMPTS',
    'RETRY_WAIT_SECONDS',
    'ORDER_TYPES',
    'ORDER_SIDES',
    'ORDER_STATUS',
    'WEBSOCKET_QUEUE_SIZE',
    'DEFAULT_VOLUME_THRESHOLD',
    'DEFAULT_CHANGE_THRESHOLD',
    
    # Config
    'DataManagerConfig',
    'PriceManagerConfig',
    'OrderBookManagerConfig',
    'SpreadManagerConfig',
    'TickerManagerConfig',
    'TradeManagerConfig',
    'VolumeManagerConfig',
    'WebSocketManagerConfig',
    'DataAggregatorConfig',
    'DataProcessorConfig',
    'DataValidatorConfig',
    'DataNormalizerConfig',
    'DataCacheConfig',
    'DataStorageConfig',
    'DataStreamConfig',
    'CandleManagerConfig',
    'DepthManagerConfig',
    'LiquidityManagerConfig',
    
    # Version
    '__version__',
]


# ============================================================
# MODULE INITIALIZATION
# ============================================================

async def initialize_data_module(
    config: Optional[Dict[str, Any]] = None,
    redis_url: Optional[str] = None,
    cache_ttl: int = 5,
    enable_websocket: bool = True,
) -> Dict[str, Any]:
    """
    Initialize the data module with all managers.

    Args:
        config: Configuration dictionary
        redis_url: Redis URL for caching
        cache_ttl: Cache TTL in seconds
        enable_websocket: Enable WebSocket manager

    Returns:
        Dictionary with all manager instances
    """
    from .price_manager import create_price_manager
    from .order_book_manager import create_order_book_manager
    from .spread_manager import create_spread_manager
    from .ticker_manager import create_ticker_manager
    from .trade_manager import create_trade_manager
    from .volume_manager import create_volume_manager
    from .candle_manager import create_candle_manager
    from .depth_manager import create_depth_manager
    from .liquidity_manager import create_liquidity_manager
    from .data_cache import DataCache
    from .data_storage import DataStorage

    # Redis client
    redis_client = None
    if redis_url:
        try:
            import redis.asyncio as redis
            redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        except ImportError:
            logger.warning("Redis not available, using in-memory cache")

    # Cache
    cache = DataCache(redis_client, default_ttl=cache_ttl)

    # Storage
    storage = DataStorage(config)

    # Price Manager
    price_manager = create_price_manager(
        config=config.get('price') if config else None,
        redis_url=redis_url,
        cache_ttl=cache_ttl,
    )

    # Order Book Manager
    order_book_manager = create_order_book_manager(
        config=config.get('order_book') if config else None,
        cache=cache,
    )

    # Spread Manager
    spread_manager = create_spread_manager(
        price_manager=price_manager,
        config=config.get('spread') if config else None,
        redis_client=redis_client,
        cache_ttl=cache_ttl,
    )

    # Ticker Manager
    ticker_manager = create_ticker_manager(
        price_manager=price_manager,
        config=config.get('ticker') if config else None,
        redis_client=redis_client,
        cache_ttl=cache_ttl,
    )

    # Trade Manager
    trade_manager = create_trade_manager(
        price_manager=price_manager,
        config=config.get('trade') if config else None,
        redis_client=redis_client,
        cache_ttl=cache_ttl,
    )

    # Volume Manager
    volume_manager = create_volume_manager(
        price_manager=price_manager,
        ticker_manager=ticker_manager,
        config=config.get('volume') if config else None,
        redis_client=redis_client,
        cache_ttl=cache_ttl,
    )

    # Candle Manager
    candle_manager = create_candle_manager(
        price_manager=price_manager,
        config=config.get('candle') if config else None,
        redis_client=redis_client,
        cache_ttl=cache_ttl,
    )

    # Depth Manager
    depth_manager = create_depth_manager(
        order_book_manager=order_book_manager,
        config=config.get('depth') if config else None,
        redis_client=redis_client,
        cache_ttl=cache_ttl,
    )

    # Liquidity Manager
    liquidity_manager = create_liquidity_manager(
        order_book_manager=order_book_manager,
        volume_manager=volume_manager,
        config=config.get('liquidity') if config else None,
        redis_client=redis_client,
        cache_ttl=cache_ttl,
    )

    # WebSocket Manager
    websocket_manager = None
    if enable_websocket:
        websocket_manager = create_websocket_manager(
            config=config.get('websocket') if config else None,
            redis_client=redis_client,
        )

    managers = {
        'cache': cache,
        'storage': storage,
        'price_manager': price_manager,
        'order_book_manager': order_book_manager,
        'spread_manager': spread_manager,
        'ticker_manager': ticker_manager,
        'trade_manager': trade_manager,
        'volume_manager': volume_manager,
        'candle_manager': candle_manager,
        'depth_manager': depth_manager,
        'liquidity_manager': liquidity_manager,
        'websocket_manager': websocket_manager,
    }

    # Start all managers
    for name, manager in managers.items():
        if manager and hasattr(manager, 'start'):
            try:
                await manager.start()
            except Exception as e:
                logger.warning(f"Error starting {name}: {e}")

    logger.info("Data module initialized with all managers")
    return managers


# ============================================================
# MODULE CLEANUP
# ============================================================

async def cleanup_data_module(managers: Dict[str, Any]) -> None:
    """
    Cleanup the data module.

    Args:
        managers: Dictionary with manager instances
    """
    for name, manager in managers.items():
        if manager and hasattr(manager, 'stop'):
            try:
                await manager.stop()
            except Exception as e:
                logger.warning(f"Error stopping {name}: {e}")
        if manager and hasattr(manager, 'clear'):
            try:
                await manager.clear()
            except Exception as e:
                logger.warning(f"Error clearing {name}: {e}")

    logger.info("Data module cleaned up")


# ============================================================
# DATA MODULE CONTEXT MANAGER
# ============================================================

class DataModule:
    """
    Data module context manager for easy initialization and cleanup.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        redis_url: Optional[str] = None,
        cache_ttl: int = 5,
        enable_websocket: bool = True,
    ):
        """
        Initialize data module.

        Args:
            config: Configuration dictionary
            redis_url: Redis URL for caching
            cache_ttl: Cache TTL in seconds
            enable_websocket: Enable WebSocket manager
        """
        self.config = config
        self.redis_url = redis_url
        self.cache_ttl = cache_ttl
        self.enable_websocket = enable_websocket
        self.managers: Optional[Dict[str, Any]] = None

    async def __aenter__(self) -> Dict[str, Any]:
        """Enter context."""
        self.managers = await initialize_data_module(
            config=self.config,
            redis_url=self.redis_url,
            cache_ttl=self.cache_ttl,
            enable_websocket=self.enable_websocket,
        )
        return self.managers

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context."""
        if self.managers:
            await cleanup_data_module(self.managers)


# ============================================================
# MODULE LOGGING
# ============================================================

def setup_data_logging(level: str = "INFO") -> None:
    """
    Setup logging for the data module.

    Args:
        level: Logging level
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Set specific loggers
    loggers = [
        'price_manager',
        'order_book_manager',
        'spread_manager',
        'ticker_manager',
        'trade_manager',
        'volume_manager',
        'websocket_manager',
        'candle_manager',
        'depth_manager',
        'liquidity_manager',
        'data_aggregator',
        'data_processor',
        'data_validator',
        'data_normalizer',
        'data_cache',
        'data_storage',
        'data_stream',
    ]

    for logger_name in loggers:
        logger = logging.getLogger(f'trading.bots.arbitrage_bot.data.{logger_name}')
        logger.setLevel(getattr(logging, level.upper()))

    logger.info("Data module logging configured")


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    """
    Example usage of the data module.
    """
    import json

    async def main():
        # Setup logging
        setup_data_logging("DEBUG")

        # Initialize data module
        async with DataModule(
            config={
                'price': {'cache_ttl': 5},
                'spread': {'anomaly_threshold': 3.0},
                'volume': {'min_samples': 10},
            },
            redis_url="redis://localhost:6379",
            cache_ttl=5,
            enable_websocket=True,
        ) as managers:
            # Get managers
            price_manager = managers['price_manager']
            spread_manager = managers['spread_manager']
            ticker_manager = managers['ticker_manager']
            trade_manager = managers['trade_manager']
            volume_manager = managers['volume_manager']
            candle_manager = managers['candle_manager']
            depth_manager = managers['depth_manager']
            liquidity_manager = managers['liquidity_manager']
            websocket_manager = managers['websocket_manager']

            # Update prices
            await price_manager.update_price(
                exchange="binance",
                symbol="BTC-USDT",
                price=45000.0,
                bid=44990.0,
                ask=45010.0,
                volume=123.45,
            )

            await price_manager.update_price(
                exchange="bybit",
                symbol="BTC-USDT",
                price=45020.0,
                bid=45010.0,
                ask=45030.0,
                volume=67.89,
            )

            # Get price snapshot
            snapshot = await price_manager.get_snapshot("BTC-USDT")
            print(f"Price Snapshot: {json.dumps(snapshot.to_dict(), indent=2, default=str)}")

            # Get spread
            spread = await spread_manager.calculate_spread("binance", "BTC-USDT")
            print(f"Spread: {spread.spread_pct:.4f}%")

            # Get ticker
            ticker = await ticker_manager.update_ticker(
                exchange="binance",
                symbol="BTC-USDT",
                price=45000.0,
                bid=44990.0,
                ask=45010.0,
                volume=123.45,
                high_24h=46000.0,
                low_24h=44000.0,
            )
            print(f"Ticker: {json.dumps(ticker.to_dict(), indent=2, default=str)}")

            # Get volume snapshot
            volume_snapshot = await volume_manager.get_snapshot("BTC-USDT")
            print(f"Volume Snapshot: {json.dumps(volume_snapshot.to_dict(), indent=2, default=str)}")

            # Get candle data
            candle = await candle_manager.get_candle("binance", "BTC-USDT", "1m")
            if candle:
                print(f"Candle: {candle.to_dict()}")

            # Get depth
            depth = await depth_manager.get_depth("binance", "BTC-USDT", 10)
            print(f"Depth: {json.dumps(depth.to_dict(), indent=2, default=str)}")

            # Get liquidity
            liquidity = await liquidity_manager.get_liquidity("binance", "BTC-USDT")
            print(f"Liquidity: {json.dumps(liquidity.to_dict(), indent=2, default=str)}")

        print("Data module example completed")

    asyncio.run(main())
