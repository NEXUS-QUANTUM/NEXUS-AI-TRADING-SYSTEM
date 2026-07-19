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
# EXPOSE PUBLIC API
# ============================================================================

from .base import (
    StockExchangeBase,
    StockOrderType,
    StockOrderSide,
    StockTimeInForce,
    StockOrderStatus,
    StockOrder,
    StockPosition,
    StockAccountInfo,
    StockMarketData,
    StockOrderBook,
    StockTrade,
    StockQuote,
    StockBar,
    StockWatchlist,
)

from .alpaca import AlpacaBroker
from .ibkr import InteractiveBrokersBroker
from .tradier import TradierBroker
from .tradestation import TradeStationBroker
from .schwab import SchwabBroker
from .fidelity import FidelityBroker
from .etrade import ETRADEBroker

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
)

from .converter import (
    StockDataConverter,
    OrderConverter,
    MarketDataConverter,
    PositionConverter,
    QuoteConverter,
    BarConverter,
    TradeConverter,
)

from .utils import (
    StockUtils,
    SymbolValidator,
    MarketHours,
    HolidayCalendar,
    StockScreener,
    PositionCalculator,
    RiskMetrics,
    PerformanceMetrics,
)

from .webhook import (
    WebhookHandler,
    WebhookConfig,
    WebhookPayload,
    WebhookResponse,
    WebhookProvider,
    WebhookEventType,
    WebhookStatus,
    StockTradeData,
    StockQuoteData,
    StockAggregateData,
    create_webhook_handler,
)

# ============================================================================
# BROKER REGISTRY
# ============================================================================

BROKER_REGISTRY = {
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
# FACTORY FUNCTIONS
# ============================================================================

def create_broker(
    broker_type: str,
    api_key: str = None,
    api_secret: str = None,
    paper_trading: bool = False,
    **kwargs
) -> StockExchangeBase:
    """
    Create a stock broker instance by type.
    
    Args:
        broker_type: Broker type ('alpaca', 'ibkr', 'tradier', etc.)
        api_key: API key (optional)
        api_secret: API secret (optional)
        paper_trading: Use paper trading environment (optional)
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
    
    # Prepare configuration
    config = {
        "api_key": api_key,
        "api_secret": api_secret,
        "paper_trading": paper_trading,
        **kwargs,
    }
    
    # Remove None values
    config = {k: v for k, v in config.items() if v is not None}
    
    return broker_class(**config)


def get_broker_info(broker_type: str = None) -> dict:
    """
    Get information about supported brokers.
    
    Args:
        broker_type: Specific broker type (optional)
    
    Returns:
        dict: Broker information
    """
    info = {
        "supported_brokers": SUPPORTED_BROKERS,
        "versions": {
            broker: getattr(BROKER_REGISTRY[broker], "__version__", "unknown")
            for broker in SUPPORTED_BROKERS
        },
        "features": {
            broker: _get_broker_features(broker)
            for broker in SUPPORTED_BROKERS
        },
    }
    
    if broker_type:
        broker_type = broker_type.lower()
        if broker_type in BROKER_REGISTRY:
            broker_class = BROKER_REGISTRY[broker_type]
            info["broker_info"] = {
                "name": broker_type,
                "class": broker_class.__name__,
                "module": broker_class.__module__,
                "version": getattr(broker_class, "__version__", "unknown"),
                "description": getattr(broker_class, "__doc__", "").strip(),
                "features": _get_broker_features(broker_type),
            }
        else:
            info["broker_info"] = {"error": f"Broker {broker_type} not found"}
    
    return info


def _get_broker_features(broker_type: str) -> Dict[str, bool]:
    """Get features for a specific broker."""
    features = {
        "alpaca": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": True,
            "crypto": True,
            "options": False,
            "margin": True,
            "webhooks": True,
            "websocket_stream": True,
        },
        "ibkr": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": True,
            "crypto": True,
            "options": True,
            "margin": True,
            "webhooks": False,
            "websocket_stream": True,
        },
        "tradier": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": False,
            "options": True,
            "margin": True,
            "webhooks": True,
            "websocket_stream": True,
        },
        "tradestation": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": True,
            "crypto": False,
            "options": True,
            "margin": True,
            "webhooks": False,
            "websocket_stream": True,
        },
        "schwab": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": True,
            "crypto": False,
            "options": True,
            "margin": True,
            "webhooks": False,
            "websocket_stream": False,
        },
        "fidelity": {
            "paper_trading": False,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": True,
            "crypto": False,
            "options": True,
            "margin": True,
            "webhooks": False,
            "websocket_stream": False,
        },
        "etrade": {
            "paper_trading": True,
            "real_time_data": True,
            "historical_data": True,
            "fractional_shares": False,
            "crypto": False,
            "options": True,
            "margin": True,
            "webhooks": True,
            "websocket_stream": False,
        },
    }
    return features.get(broker_type, {})


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
    return SymbolValidator.is_valid(symbol)


def normalize_symbol(symbol: str) -> str:
    """
    Normalize a stock symbol.
    
    Args:
        symbol: Stock symbol to normalize
    
    Returns:
        str: Normalized symbol
    """
    return SymbolValidator.normalize(symbol)


def is_market_open(exchange: str = "NYSE", date: datetime = None) -> bool:
    """
    Check if the market is open.
    
    Args:
        exchange: Exchange name
        date: Date to check (default: now)
    
    Returns:
        bool: True if market is open
    """
    return MarketHours.is_open(exchange, date)


def get_next_market_open(exchange: str = "NYSE", date: datetime = None) -> datetime:
    """
    Get the next market open time.
    
    Args:
        exchange: Exchange name
        date: Date to check (default: now)
    
    Returns:
        datetime: Next market open time
    """
    return MarketHours.next_open(exchange, date)


def get_next_market_close(exchange: str = "NYSE", date: datetime = None) -> datetime:
    """
    Get the next market close time.
    
    Args:
        exchange: Exchange name
        date: Date to check (default: now)
    
    Returns:
        datetime: Next market close time
    """
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
    return PerformanceMetrics.sharpe_ratio(returns, risk_free_rate)


def calculate_max_drawdown(values: List[float]) -> float:
    """
    Calculate maximum drawdown.
    
    Args:
        values: List of values (e.g., portfolio values)
    
    Returns:
        float: Maximum drawdown percentage
    """
    return PerformanceMetrics.max_drawdown(values)


# ============================================================================
# MODULE DOCUMENTATION
# ============================================================================

__all__ = [
    # Classes
    "StockExchangeBase",
    "StockOrderType",
    "StockOrderSide",
    "StockTimeInForce",
    "StockOrderStatus",
    "StockOrder",
    "StockPosition",
    "StockAccountInfo",
    "StockMarketData",
    "StockOrderBook",
    "StockTrade",
    "StockQuote",
    "StockBar",
    "StockWatchlist",
    
    "AlpacaBroker",
    "InteractiveBrokersBroker",
    "TradierBroker",
    "TradeStationBroker",
    "SchwabBroker",
    "FidelityBroker",
    "ETRADEBroker",
    
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
    
    "StockDataConverter",
    "OrderConverter",
    "MarketDataConverter",
    "PositionConverter",
    "QuoteConverter",
    "BarConverter",
    "TradeConverter",
    
    "StockUtils",
    "SymbolValidator",
    "MarketHours",
    "HolidayCalendar",
    "StockScreener",
    "PositionCalculator",
    "RiskMetrics",
    "PerformanceMetrics",
    
    "WebhookHandler",
    "WebhookConfig",
    "WebhookPayload",
    "WebhookResponse",
    "WebhookProvider",
    "WebhookEventType",
    "WebhookStatus",
    "StockTradeData",
    "StockQuoteData",
    "StockAggregateData",
    "create_webhook_handler",
    
    # Constants
    "BROKER_REGISTRY",
    "SUPPORTED_BROKERS",
    
    # Functions
    "create_broker",
    "get_broker_info",
    "validate_symbol",
    "normalize_symbol",
    "is_market_open",
    "get_next_market_open",
    "get_next_market_close",
    "calculate_position_size",
    "calculate_sharpe_ratio",
    "calculate_max_drawdown",
]

# ============================================================================
# MODULE INITIALIZATION
# ============================================================================

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

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
        
        # Configure market hours
        market_hours_config = config.get("market_hours", {})
        if market_hours_config:
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
# UNIT TESTS
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Run basic tests
    print("=" * 70)
    print("NEXUS AI TRADING SYSTEM - Stocks Module Test")
    print("=" * 70)
    print(f"Version: {__version__}")
    print(f"Copyright: {__copyright__}")
    print(f"Status: {__status__}")
    print("=" * 70)
    
    # Test broker registry
    print("\n[1] Testing Broker Registry:")
    print(f"Supported brokers: {SUPPORTED_BROKERS}")
    for broker in SUPPORTED_BROKERS:
        features = _get_broker_features(broker)
        print(f"  {broker:12} - {len(features)} features")
    
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
    for broker_name in SUPPORTED_BROKERS[:4]:
        try:
            broker = create_broker(broker_name, paper_trading=True)
            print(f"  {broker_name:15} -> ✓ Created")
        except Exception as e:
            print(f"  {broker_name:15} -> ✗ Failed - {e}")
    
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
    
    # Test webhook handler
    print("\n[7] Testing Webhook Handler:")
    try:
        handler = create_webhook_handler(
            provider="custom",
            path="/webhook",
            port=8080,
            secret_key="test-key-123",
            rate_limit_requests=10,
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
    print("\n[8] Broker Information:")
    info = get_broker_info()
    print(f"  Supported brokers: {len(info['supported_brokers'])}")
    for broker, version in info['versions'].items():
        print(f"    {broker:12} - v{version}")
    
    print("\n" + "=" * 70)
    print("✅ All tests completed successfully!")
    print("=" * 70)
