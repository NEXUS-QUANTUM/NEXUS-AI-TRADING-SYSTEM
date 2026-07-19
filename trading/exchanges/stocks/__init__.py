#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NEXUS AI TRADING SYSTEM - Stocks Exchange Module
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Advanced stocks exchange module with multi-broker support,
real-time data streaming, order management, and portfolio tracking.
Supports: Alpaca, Interactive Brokers, Tradier, TradeStation,
Schwab, Fidelity, and E*TRADE.

Author: Dr X...
Version: 3.0.0
"""

# ============================================================================
# VERSION & METADATA
# ============================================================================

__version__ = "3.0.0"
__author__ = "Dr X..."
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"
__license__ = "Proprietary"
__status__ = "Production"

# ============================================================================
# IMPORTS - BASE CLASSES
# ============================================================================

from .base import (
    # Enums
    StockOrderType,
    StockOrderSide,
    StockTimeInForce,
    StockOrderStatus,
    StockPositionSide,
    StockOrderClass,
    StockOrderType as StockOrderTypeAlias,
    
    # Data Classes
    StockOrder,
    StockPosition,
    StockAccountInfo,
    StockMarketData,
    StockOrderBook,
    StockTrade,
    StockQuote,
    StockBar,
    StockWatchlist,
    StockAccountActivity,
    StockDividend,
    StockSplit,
    StockEarnings,
    
    # Base Class
    StockExchangeBase,
)

# ============================================================================
# IMPORTS - EXCEPTIONS
# ============================================================================

from .exceptions import (
    StockExchangeError,
    AuthenticationError,
    AuthorizationError,
    ConnectionError,
    RateLimitError,
    OrderError,
    InvalidOrderError,
    InsufficientBalanceError,
    MarketDataError,
    PositionError,
    AccountError,
    WatchlistError,
    StreamError,
    WebhookError,
    ValidationError,
    SymbolError,
    BrokerError,
)

# ============================================================================
# IMPORTS - BROKERS
# ============================================================================

# Alpaca
from .alpaca import (
    AlpacaBroker,
    AlpacaConfig,
    AlpacaAccount,
    AlpacaOrder,
    AlpacaPosition,
    AlpacaMarketData,
    AlpacaWebSocket,
    AlpacaException,
)

# Interactive Brokers
from .ibkr import (
    InteractiveBrokersBroker,
    IBKRConfig,
    IBKRConnection,
    IBKRContract,
    IBKROrder,
    IBKRPosition,
    IBKRMarketData,
    IBKRWebSocket,
    IBRKException,
)

# Tradier
from .tradier import (
    TradierBroker,
    TradierConfig,
    TradierAccount,
    TradierOrder,
    TradierPosition,
    TradierMarketData,
    TradierWebSocket,
    TradierException,
)

# TradeStation
from .tradestation import (
    TradeStationBroker,
    TradeStationConfig,
    TradeStationAccount,
    TradeStationOrder,
    TradeStationPosition,
    TradeStationMarketData,
    TradeStationWebSocket,
    TradeStationException,
)

# Schwab
from .schwab import (
    SchwabBroker,
    SchwabConfig,
    SchwabAccount,
    SchwabOrder,
    SchwabPosition,
    SchwabMarketData,
    SchwabException,
)

# Fidelity
from .fidelity import (
    FidelityBroker,
    FidelityConfig,
    FidelityAccount,
    FidelityOrder,
    FidelityPosition,
    FidelityMarketData,
    FidelityException,
)

# E*TRADE
from .etrade import (
    ETRADEBroker,
    ETRADEConfig,
    ETRADEAccount,
    ETRADEOrder,
    ETRADEPosition,
    ETRADEMarketData,
    ETRADEException,
)

# ============================================================================
# IMPORTS - CONVERTERS
# ============================================================================

from .converter import (
    StockDataConverter,
    OrderConverter,
    MarketDataConverter,
    PositionConverter,
    QuoteConverter,
    BarConverter,
    TradeConverter,
    AccountConverter,
    WatchlistConverter,
    OHLCVConverter,
    OrderBookConverter,
)

# ============================================================================
# IMPORTS - UTILITIES
# ============================================================================

from .utils import (
    StockUtils,
    SymbolValidator,
    MarketHours,
    HolidayCalendar,
    StockScreener,
    PositionCalculator,
    RiskMetrics,
    PerformanceMetrics,
    TechnicalIndicators,
    FundamentalAnalyzer,
    OptionPricer,
    StockFilter,
    MarketTiming,
    SectorAnalyzer,
    VolatilityCalculator,
    CorrelationAnalyzer,
)

# ============================================================================
# IMPORTS - WEBHOOK
# ============================================================================

from .webhook import (
    WebhookHandler,
    WebhookConfig,
    WebhookPayload,
    WebhookResponse,
    WebhookProvider,
    WebhookEventType,
    WebhookStatus,
    WebhookFormat,
    WebhookAuthType,
    WebhookCompression,
    SignatureAlgorithm,
    StockTradeData,
    StockQuoteData,
    StockAggregateData,
    StockBarData,
    StockOrderData,
    StockPositionData,
    StockAccountData,
    create_webhook_handler,
)

# ============================================================================
# BROKER REGISTRY
# ============================================================================

BROKER_REGISTRY = {
    # Stock Brokers
    "alpaca": AlpacaBroker,
    "ibkr": InteractiveBrokersBroker,
    "tradier": TradierBroker,
    "tradestation": TradeStationBroker,
    "schwab": SchwabBroker,
    "fidelity": FidelityBroker,
    "etrade": ETRADEBroker,
}

SUPPORTED_BROKERS = list(BROKER_REGISTRY.keys())

# ============================================================================
# BROKER CONFIGURATIONS
# ============================================================================

BROKER_CONFIGS = {
    "alpaca": {
        "name": "Alpaca",
        "website": "https://alpaca.markets",
        "docs": "https://docs.alpaca.markets",
        "paper_trading": True,
        "fractional_shares": True,
        "crypto": True,
        "options": False,
        "margin": True,
        "webhooks": True,
        "websocket": True,
        "rate_limit": {"requests": 200, "period": 60},
        "fee_structure": {"maker": 0.0, "taker": 0.0},
        "api_version": "v2",
    },
    "ibkr": {
        "name": "Interactive Brokers",
        "website": "https://www.interactivebrokers.com",
        "docs": "https://interactivebrokers.github.io/tws-api",
        "paper_trading": True,
        "fractional_shares": True,
        "crypto": True,
        "options": True,
        "margin": True,
        "webhooks": False,
        "websocket": True,
        "rate_limit": {"requests": 50, "period": 60},
        "fee_structure": {"maker": 0.0, "taker": 0.0},
        "api_version": "v1",
    },
    "tradier": {
        "name": "Tradier",
        "website": "https://tradier.com",
        "docs": "https://documentation.tradier.com",
        "paper_trading": True,
        "fractional_shares": False,
        "crypto": False,
        "options": True,
        "margin": True,
        "webhooks": True,
        "websocket": True,
        "rate_limit": {"requests": 60, "period": 60},
        "fee_structure": {"maker": 0.0, "taker": 0.0},
        "api_version": "v1",
    },
    "tradestation": {
        "name": "TradeStation",
        "website": "https://www.tradestation.com",
        "docs": "https://docs.tradestation.com",
        "paper_trading": True,
        "fractional_shares": True,
        "crypto": False,
        "options": True,
        "margin": True,
        "webhooks": False,
        "websocket": True,
        "rate_limit": {"requests": 100, "period": 60},
        "fee_structure": {"maker": 0.0, "taker": 0.0},
        "api_version": "v3",
    },
    "schwab": {
        "name": "Schwab",
        "website": "https://www.schwab.com",
        "docs": "https://developer.schwab.com",
        "paper_trading": True,
        "fractional_shares": True,
        "crypto": False,
        "options": True,
        "margin": True,
        "webhooks": False,
        "websocket": False,
        "rate_limit": {"requests": 50, "period": 60},
        "fee_structure": {"maker": 0.0, "taker": 0.0},
        "api_version": "v1",
    },
    "fidelity": {
        "name": "Fidelity",
        "website": "https://www.fidelity.com",
        "docs": "https://developer.fidelity.com",
        "paper_trading": False,
        "fractional_shares": True,
        "crypto": False,
        "options": True,
        "margin": True,
        "webhooks": False,
        "websocket": False,
        "rate_limit": {"requests": 50, "period": 60},
        "fee_structure": {"maker": 0.0, "taker": 0.0},
        "api_version": "v1",
    },
    "etrade": {
        "name": "E*TRADE",
        "website": "https://www.etrade.com",
        "docs": "https://developer.etrade.com",
        "paper_trading": True,
        "fractional_shares": False,
        "crypto": False,
        "options": True,
        "margin": True,
        "webhooks": True,
        "websocket": False,
        "rate_limit": {"requests": 100, "period": 60},
        "fee_structure": {"maker": 0.0, "taker": 0.0},
        "api_version": "v1",
    },
}

# ============================================================================
# API ENDPOINTS
# ============================================================================

BROKER_ENDPOINTS = {
    "alpaca": {
        "rest": "https://api.alpaca.markets/v2",
        "rest_paper": "https://paper-api.alpaca.markets/v2",
        "websocket": "wss://stream.data.alpaca.markets/v2/iex",
        "websocket_paper": "wss://stream.data.alpaca.markets/v2/iex",
        "data": "https://data.alpaca.markets/v2",
    },
    "ibkr": {
        "rest": "https://api.ibkr.com/v1",
        "rest_paper": "https://api.ibkr.com/v1",
        "websocket": "wss://api.ibkr.com/ws",
    },
    "tradier": {
        "rest": "https://api.tradier.com/v1",
        "rest_paper": "https://api.tradier.com/v1",
        "websocket": "wss://ws.tradier.com/v1",
    },
    "tradestation": {
        "rest": "https://api.tradestation.com/v3",
        "rest_paper": "https://api.tradestation.com/v3",
        "websocket": "wss://api.tradestation.com/stream",
    },
    "schwab": {
        "rest": "https://api.schwab.com/v1",
        "rest_paper": "https://api.schwab.com/v1",
    },
    "fidelity": {
        "rest": "https://api.fidelity.com/v1",
        "rest_paper": "https://api.fidelity.com/v1",
    },
    "etrade": {
        "rest": "https://api.etrade.com/v1",
        "rest_paper": "https://api.etrade.com/v1",
    },
}

# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def create_broker(
    broker_type: str,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    api_passphrase: Optional[str] = None,
    paper_trading: bool = False,
    testnet: bool = False,
    sandbox: bool = False,
    timeout: int = 30,
    max_retries: int = 3,
    **kwargs
) -> StockExchangeBase:
    """
    Create a stock broker instance by type.
    
    Args:
        broker_type: Broker type ('alpaca', 'ibkr', 'tradier', etc.)
        api_key: API key (optional)
        api_secret: API secret (optional)
        api_passphrase: API passphrase (optional)
        paper_trading: Enable paper trading mode (optional)
        testnet: Use testnet endpoints (optional)
        sandbox: Use sandbox environment (optional)
        timeout: Request timeout in seconds (optional)
        max_retries: Maximum number of retries (optional)
        **kwargs: Additional broker-specific configuration
    
    Returns:
        StockExchangeBase: Broker instance
    
    Raises:
        ValueError: If broker type is not supported
    """
    broker_type = broker_type.lower()
    
    if broker_type not in BROKER_REGISTRY:
        raise ValueError(
            f"Unsupported broker type: {broker_type}. "
            f"Supported brokers: {', '.join(SUPPORTED_BROKERS)}"
        )
    
    broker_class = BROKER_REGISTRY[broker_type]
    
    # Get configuration
    config = BROKER_CONFIGS.get(broker_type, {})
    endpoints = BROKER_ENDPOINTS.get(broker_type, {})
    
    # Prepare configuration
    broker_config = {
        "api_key": api_key,
        "api_secret": api_secret,
        "api_passphrase": api_passphrase,
        "paper_trading": paper_trading,
        "testnet": testnet,
        "sandbox": sandbox,
        "timeout": timeout,
        "max_retries": max_retries,
        "config": config,
        "endpoints": endpoints,
        **kwargs,
    }
    
    # Remove None values
    broker_config = {k: v for k, v in broker_config.items() if v is not None}
    
    return broker_class(**broker_config)


def get_broker_info(broker_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Get information about supported brokers.
    
    Args:
        broker_type: Specific broker type (optional)
    
    Returns:
        dict: Broker information
    """
    info = {
        "supported_brokers": SUPPORTED_BROKERS,
        "count": len(SUPPORTED_BROKERS),
        "configs": BROKER_CONFIGS,
        "endpoints": BROKER_ENDPOINTS,
        "versions": {
            broker: getattr(BROKER_REGISTRY[broker], "__version__", "unknown")
            for broker in SUPPORTED_BROKERS
        },
    }
    
    if broker_type:
        broker_type = broker_type.lower()
        if broker_type in BROKER_REGISTRY:
            broker_class = BROKER_REGISTRY[broker_type]
            info["broker_details"] = {
                "name": broker_type,
                "class": broker_class.__name__,
                "module": broker_class.__module__,
                "version": getattr(broker_class, "__version__", "unknown"),
                "description": getattr(broker_class, "__doc__", "").strip(),
                "config": BROKER_CONFIGS.get(broker_type, {}),
                "endpoints": BROKER_ENDPOINTS.get(broker_type, {}),
            }
        else:
            info["broker_details"] = {"error": f"Broker {broker_type} not found"}
    
    return info


def get_broker_class(broker_type: str) -> Optional[type]:
    """
    Get the broker class for a given type.
    
    Args:
        broker_type: Broker type
    
    Returns:
        Optional[type]: Broker class or None
    """
    broker_type = broker_type.lower()
    return BROKER_REGISTRY.get(broker_type)


def is_broker_supported(broker_type: str) -> bool:
    """
    Check if a broker is supported.
    
    Args:
        broker_type: Broker type
    
    Returns:
        bool: True if supported
    """
    return broker_type.lower() in BROKER_REGISTRY


def get_broker_features(broker_type: str) -> Dict[str, Any]:
    """
    Get features for a specific broker.
    
    Args:
        broker_type: Broker type
    
    Returns:
        Dict[str, Any]: Broker features
    """
    broker_type = broker_type.lower()
    return BROKER_CONFIGS.get(broker_type, {})


def get_broker_endpoints(broker_type: str) -> Dict[str, str]:
    """
    Get API endpoints for a specific broker.
    
    Args:
        broker_type: Broker type
    
    Returns:
        Dict[str, str]: API endpoints
    """
    broker_type = broker_type.lower()
    return BROKER_ENDPOINTS.get(broker_type, {})


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def validate_symbol(symbol: str) -> bool:
    """
    Validate a stock symbol.
    
    Args:
        symbol: Stock symbol to validate
    
    Returns:
        bool: True if valid
    """
    from .utils import SymbolValidator
    return SymbolValidator.is_valid(symbol)


def normalize_symbol(symbol: str) -> str:
    """
    Normalize a stock symbol.
    
    Args:
        symbol: Stock symbol to normalize
    
    Returns:
        str: Normalized symbol
    """
    from .utils import SymbolValidator
    return SymbolValidator.normalize(symbol)


def is_market_open(exchange: str = "NYSE", date: Optional[datetime] = None) -> bool:
    """
    Check if the market is open.
    
    Args:
        exchange: Exchange name
        date: Date to check (default: now)
    
    Returns:
        bool: True if market is open
    """
    from .utils import MarketHours
    return MarketHours.is_open(exchange, date)


def get_next_market_open(exchange: str = "NYSE", date: Optional[datetime] = None) -> datetime:
    """
    Get the next market open time.
    
    Args:
        exchange: Exchange name
        date: Date to check (default: now)
    
    Returns:
        datetime: Next market open time
    """
    from .utils import MarketHours
    return MarketHours.next_open(exchange, date)


def get_next_market_close(exchange: str = "NYSE", date: Optional[datetime] = None) -> datetime:
    """
    Get the next market close time.
    
    Args:
        exchange: Exchange name
        date: Date to check (default: now)
    
    Returns:
        datetime: Next market close time
    """
    from .utils import MarketHours
    return MarketHours.next_close(exchange, date)


def calculate_position_size(
    capital: float,
    risk_per_trade: float,
    stop_loss_pct: float,
    entry_price: float
) -> float:
    """
    Calculate position size based on risk.
    
    Args:
        capital: Total capital
        risk_per_trade: Risk percentage (0-1)
        stop_loss_pct: Stop loss percentage (0-1)
        entry_price: Entry price
    
    Returns:
        float: Position size in shares
    """
    from .utils import PositionCalculator
    return PositionCalculator.calculate_size(capital, risk_per_trade, stop_loss_pct, entry_price)


def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.02) -> float:
    """
    Calculate Sharpe ratio.
    
    Args:
        returns: List of returns
        risk_free_rate: Risk-free rate (annualized)
    
    Returns:
        float: Sharpe ratio
    """
    from .utils import PerformanceMetrics
    return PerformanceMetrics.sharpe_ratio(returns, risk_free_rate)


def calculate_max_drawdown(values: List[float]) -> float:
    """
    Calculate maximum drawdown.
    
    Args:
        values: List of values (e.g., portfolio values)
    
    Returns:
        float: Maximum drawdown percentage
    """
    from .utils import PerformanceMetrics
    return PerformanceMetrics.max_drawdown(values)


def calculate_technical_indicator(
    data: List[float],
    indicator: str,
    **kwargs
) -> List[float]:
    """
    Calculate a technical indicator.
    
    Args:
        data: Price data
        indicator: Indicator name
        **kwargs: Indicator parameters
    
    Returns:
        List[float]: Indicator values
    """
    from .utils import TechnicalIndicators
    indicator_func = getattr(TechnicalIndicators, indicator, None)
    if indicator_func:
        return indicator_func(data, **kwargs)
    raise ValueError(f"Unknown indicator: {indicator}")


# ============================================================================
# ASYNC CONTEXT MANAGER
# ============================================================================

async def create_broker_context(
    broker_type: str,
    **kwargs
) -> StockExchangeBase:
    """
    Create a broker instance with async context manager support.
    
    Args:
        broker_type: Broker type
        **kwargs: Broker configuration
    
    Returns:
        StockExchangeBase: Broker instance
    
    Example:
        async with create_broker_context('alpaca', api_key='...') as broker:
            await broker.get_market_data('AAPL')
    """
    broker = create_broker(broker_type, **kwargs)
    await broker.connect()
    return broker


# ============================================================================
# MODULE INITIALIZATION
# ============================================================================

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Type

logger = logging.getLogger(__name__)


def init_stocks_module(config: Optional[Dict[str, Any]] = None) -> None:
    """
    Initialize the stocks module with configuration.
    
    Args:
        config: Configuration dictionary (optional)
    """
    if config:
        # Configure logging
        log_level = config.get("log_level", "INFO")
        logger.setLevel(log_level)
        
        # Configure default broker
        default_broker = config.get("default_broker")
        if default_broker:
            logger.info(f"Default broker set to: {default_broker}")
        
        # Configure broker-specific settings
        broker_configs = config.get("brokers", {})
        for broker_name, broker_config in broker_configs.items():
            logger.info(f"Configured broker: {broker_name}")
        
        # Configure market hours
        market_hours_config = config.get("market_hours", {})
        if market_hours_config:
            from .utils import MarketHours
            MarketHours.configure(market_hours_config)
        
        # Configure webhook settings
        webhook_config = config.get("webhook", {})
        if webhook_config:
            logger.info("Webhook configuration loaded")
        
        logger.info("Stocks module initialized successfully")
    else:
        logger.info("Stocks module initialized with default configuration")


# Auto-initialize on import
init_stocks_module()


# ============================================================================
# MODULE DOCUMENTATION
# ============================================================================

__all__ = [
    # Version
    "__version__",
    
    # Enums (Base)
    "StockOrderType",
    "StockOrderSide",
    "StockTimeInForce",
    "StockOrderStatus",
    "StockPositionSide",
    "StockOrderClass",
    
    # Data Classes (Base)
    "StockOrder",
    "StockPosition",
    "StockAccountInfo",
    "StockMarketData",
    "StockOrderBook",
    "StockTrade",
    "StockQuote",
    "StockBar",
    "StockWatchlist",
    "StockAccountActivity",
    "StockDividend",
    "StockSplit",
    "StockEarnings",
    
    # Base Class
    "StockExchangeBase",
    
    # Exceptions
    "StockExchangeError",
    "AuthenticationError",
    "AuthorizationError",
    "ConnectionError",
    "RateLimitError",
    "OrderError",
    "InvalidOrderError",
    "InsufficientBalanceError",
    "MarketDataError",
    "PositionError",
    "AccountError",
    "WatchlistError",
    "StreamError",
    "WebhookError",
    "ValidationError",
    "SymbolError",
    "BrokerError",
    
    # Brokers
    "AlpacaBroker",
    "AlpacaConfig",
    "AlpacaAccount",
    "AlpacaOrder",
    "AlpacaPosition",
    "AlpacaMarketData",
    "AlpacaWebSocket",
    "AlpacaException",
    
    "InteractiveBrokersBroker",
    "IBKRConfig",
    "IBKRConnection",
    "IBKRContract",
    "IBKROrder",
    "IBKRPosition",
    "IBKRMarketData",
    "IBKRWebSocket",
    "IBRKException",
    
    "TradierBroker",
    "TradierConfig",
    "TradierAccount",
    "TradierOrder",
    "TradierPosition",
    "TradierMarketData",
    "TradierWebSocket",
    "TradierException",
    
    "TradeStationBroker",
    "TradeStationConfig",
    "TradeStationAccount",
    "TradeStationOrder",
    "TradeStationPosition",
    "TradeStationMarketData",
    "TradeStationWebSocket",
    "TradeStationException",
    
    "SchwabBroker",
    "SchwabConfig",
    "SchwabAccount",
    "SchwabOrder",
    "SchwabPosition",
    "SchwabMarketData",
    "SchwabException",
    
    "FidelityBroker",
    "FidelityConfig",
    "FidelityAccount",
    "FidelityOrder",
    "FidelityPosition",
    "FidelityMarketData",
    "FidelityException",
    
    "ETRADEBroker",
    "ETRADEConfig",
    "ETRADEAccount",
    "ETRADEOrder",
    "ETRADEPosition",
    "ETRADEMarketData",
    "ETRADEException",
    
    # Converters
    "StockDataConverter",
    "OrderConverter",
    "MarketDataConverter",
    "PositionConverter",
    "QuoteConverter",
    "BarConverter",
    "TradeConverter",
    "AccountConverter",
    "WatchlistConverter",
    "OHLCVConverter",
    "OrderBookConverter",
    
    # Utilities
    "StockUtils",
    "SymbolValidator",
    "MarketHours",
    "HolidayCalendar",
    "StockScreener",
    "PositionCalculator",
    "RiskMetrics",
    "PerformanceMetrics",
    "TechnicalIndicators",
    "FundamentalAnalyzer",
    "OptionPricer",
    "StockFilter",
    "MarketTiming",
    "SectorAnalyzer",
    "VolatilityCalculator",
    "CorrelationAnalyzer",
    
    # Webhook
    "WebhookHandler",
    "WebhookConfig",
    "WebhookPayload",
    "WebhookResponse",
    "WebhookProvider",
    "WebhookEventType",
    "WebhookStatus",
    "WebhookFormat",
    "WebhookAuthType",
    "WebhookCompression",
    "SignatureAlgorithm",
    "StockTradeData",
    "StockQuoteData",
    "StockAggregateData",
    "StockBarData",
    "StockOrderData",
    "StockPositionData",
    "StockAccountData",
    "create_webhook_handler",
    
    # Registry
    "BROKER_REGISTRY",
    "SUPPORTED_BROKERS",
    "BROKER_CONFIGS",
    "BROKER_ENDPOINTS",
    
    # Factory Functions
    "create_broker",
    "get_broker_info",
    "get_broker_class",
    "is_broker_supported",
    "get_broker_features",
    "get_broker_endpoints",
    "create_broker_context",
    
    # Convenience Functions
    "validate_symbol",
    "normalize_symbol",
    "is_market_open",
    "get_next_market_open",
    "get_next_market_close",
    "calculate_position_size",
    "calculate_sharpe_ratio",
    "calculate_max_drawdown",
    "calculate_technical_indicator",
    
    # Init
    "init_stocks_module",
]


# ============================================================================
# UNIT TESTS
# ============================================================================

if __name__ == "__main__":
    import sys
    import asyncio
    from datetime import datetime
    
    print("=" * 70)
    print("NEXUS AI TRADING SYSTEM - Stocks Module Test")
    print("=" * 70)
    print(f"Version: {__version__}")
    print(f"Copyright: {__copyright__}")
    print(f"Status: {__status__}")
    print("=" * 70)
    
    # Test registry
    print("\n[1] Testing Broker Registry:")
    print(f"Total brokers: {len(BROKER_REGISTRY)}")
    print(f"Supported brokers: {', '.join(SUPPORTED_BROKERS)}")
    
    for broker_name, config in BROKER_CONFIGS.items():
        print(f"\n  {config['name']} ({broker_name}):")
        print(f"    Paper trading: {config.get('paper_trading', False)}")
        print(f"    Fractional shares: {config.get('fractional_shares', False)}")
        print(f"    Options: {config.get('options', False)}")
        print(f"    WebSocket: {config.get('websocket', False)}")
    
    # Test symbol validation
    print("\n[2] Testing Symbol Validation:")
    test_symbols = [
        "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
        "BRK.A", "BRK.B", "VTI", "SPY", "QQQ",
        "INVALID$", "123ABC", "AAPL20260101C00100000"
    ]
    for symbol in test_symbols:
        valid = validate_symbol(symbol)
        normalized = normalize_symbol(symbol) if valid else "N/A"
        print(f"  {symbol:20} -> {'✓ Valid' if valid else '✗ Invalid'} -> {normalized}")
    
    # Test market hours
    print("\n[3] Testing Market Hours:")
    now = datetime.now()
    exchanges = ["NYSE", "NASDAQ", "AMEX", "LSE", "TSX"]
    for exchange in exchanges:
        is_open = is_market_open(exchange)
        status = "Open" if is_open else "Closed"
        print(f"  {exchange:10} - {status}")
        if not is_open:
            next_open = get_next_market_open(exchange)
            next_close = get_next_market_close(exchange)
            print(f"    Next open:  {next_open.strftime('%Y-%m-%d %H:%M %Z')}")
            print(f"    Next close: {next_close.strftime('%Y-%m-%d %H:%M %Z')}")
    
    # Test broker creation
    print("\n[4] Testing Broker Creation:")
    test_brokers = ["alpaca", "ibkr", "tradier", "tradestation"]
    for broker_name in test_brokers:
        try:
            broker = create_broker(broker_name, paper_trading=True)
            print(f"  ✓ {broker_name:15} - Created successfully")
            print(f"      Class: {broker.__class__.__name__}")
        except Exception as e:
            print(f"  ✗ {broker_name:15} - Failed: {e}")
    
    # Test position calculation
    print("\n[5] Testing Position Calculator:")
    capital = 100000
    risk_per_trade = 0.02  # 2% risk
    stop_loss_pct = 0.05   # 5% stop loss
    entry_price = 100.0
    
    position_size = calculate_position_size(capital, risk_per_trade, stop_loss_pct, entry_price)
    print(f"  Capital: ${capital:,.0f}")
    print(f"  Risk per trade: {risk_per_trade * 100:.1f}%")
    print(f"  Stop loss: {stop_loss_pct * 100:.1f}%")
    print(f"  Position size: {position_size:,.2f} shares")
    print(f"  Position value: ${position_size * entry_price:,.2f}")
    
    # Test performance metrics
    print("\n[6] Testing Performance Metrics:")
    sample_returns = [0.01, -0.005, 0.02, -0.01, 0.015, -0.008, 0.025, -0.012, 0.018, 0.005]
    sharpe = calculate_sharpe_ratio(sample_returns)
    print(f"  Sharpe ratio: {sharpe:.3f}")
    
    sample_values = [100000, 102000, 101000, 103000, 99000, 98000, 105000, 108000, 106000, 110000]
    max_dd = calculate_max_drawdown(sample_values)
    print(f"  Max drawdown: {max_dd * 100:.2f}%")
    
    # Test technical indicators
    print("\n[7] Testing Technical Indicators:")
    sample_prices = [100, 101, 102, 101, 103, 104, 103, 105, 106, 107]
    sma = calculate_technical_indicator(sample_prices, "sma", period=3)
    print(f"  SMA(3): {[round(x, 2) for x in sma]}")
    
    # Test webhook handler
    print("\n[8] Testing Webhook Handler:")
    try:
        handler = create_webhook_handler(
            provider="custom",
            path="/webhook",
            port=8080,
            secret_key="test-key-123456",
            rate_limit_requests=100,
            rate_limit_period=60,
        )
        print(f"  Webhook handler: ✓ Created")
        print(f"    Provider: {handler.config.provider.value}")
        print(f"    Path: {handler.config.path}")
        print(f"    Port: {handler.config.port}")
        print(f"    Rate limit: {handler.config.rate_limit_requests} req/{handler.config.rate_limit_period}s")
    except Exception as e:
        print(f"  Webhook handler: ✗ Failed - {e}")
    
    # Test broker info
    print("\n[9] Broker Information:")
    info = get_broker_info()
    print(f"  Supported brokers: {info['count']}")
    for broker, version in info['versions'].items():
        config = info['configs'].get(broker, {})
        print(f"    {broker:15} - v{version} - {config.get('name', broker)}")
    
    # Test broker features
    print("\n[10] Broker Features:")
    features_to_check = ["paper_trading", "fractional_shares", "options", "websocket", "webhooks"]
    for broker in ["alpaca", "ibkr", "tradier"]:
        features = get_broker_features(broker)
        print(f"\n  {broker.upper()}:")
        for feature in features_to_check:
            print(f"    {feature:20} - {features.get(feature, False)}")
    
    print("\n" + "=" * 70)
    print("✅ All tests completed successfully!")
    print("=" * 70)
