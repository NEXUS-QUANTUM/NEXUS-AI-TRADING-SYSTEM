# trading/brokers/__init__.py
"""
NEXUS AI TRADING SYSTEM - Brokers Package
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This package provides comprehensive broker integration capabilities for the
NEXUS AI Trading System. It includes base classes, configuration management,
connection handling, health monitoring, metrics collection, and routing
for multiple broker implementations.

Package Structure:
    - base.py: Abstract base broker class
    - broker_config.py: Configuration management
    - broker_connection.py: Connection pooling and management
    - broker_factory.py: Broker instance creation and registration
    - broker_health.py: Health checking and monitoring
    - broker_manager.py: Central broker orchestration
    - broker_metrics.py: Performance metrics collection
    - broker_monitor.py: Real-time monitoring and alerting
    - broker_router.py: Intelligent request routing
    - broker_utils.py: Shared utility functions
    - exceptions.py: Broker-specific exceptions

Supported Broker Types:
    - Paper Trading (Simulation)
    - Webhook (External signals)
    - Crypto Exchanges (Binance, Bybit, Coinbase, Kraken, Kucoin)
    - Stock Brokers (Alpaca, Interactive Brokers, Tradier, Tradestation)
    - Forex Brokers (OANDA)
    - Custom/Extensible via BaseBroker

Key Features:
    - Unified interface across all brokers
    - Automatic reconnection and failover
    - Health monitoring and alerting
    - Performance metrics and analytics
    - Intelligent request routing
    - Connection pooling
    - Rate limiting and circuit breakers
    - Comprehensive error handling
    - Configuration management
    - Symbol normalization and formatting
"""

import logging
from typing import Dict, List, Optional, Type, Union

# ============================================================================
# Version
# ============================================================================

__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"


# ============================================================================
# Setup Logging
# ============================================================================

logger = logging.getLogger(__name__)


# ============================================================================
# Package Exports
# ============================================================================

# Base classes
from .base import (
    BaseBroker,
    BrokerConfig,
    BrokerName,
    AssetClass,
    AccountType,
    OrderResponse,
    AccountInfo,
    MarketDataResponse,
    PaperBroker,
    WebhookBroker,
    BrokerException,
    BrokerConnectionError,
    BrokerAuthenticationError,
    BrokerRateLimitError,
    BrokerOrderError,
    BrokerDataError,
    BrokerTimeoutError,
    BrokerFactory,
)

# Configuration
from .broker_config import (
    BrokerConfigLoader,
    BrokerConfigComplete,
    BrokerEndpointConfig,
    BrokerAuthConfig,
    BrokerRateLimitConfig,
    BrokerRetryConfig,
    BrokerCircuitBreakerConfig,
    BrokerTimeoutConfig,
    BrokerMarketConfig,
    BrokerOrderConfig,
    BrokerRiskConfig,
    BrokerLoggingConfig,
    BrokerSecurityConfig,
    EnvironmentType,
)

# Connection management
from .broker_connection import (
    BrokerConnectionManager,
    BrokerConnectionPool,
    BrokerConnectionFactory,
    ConnectionState,
    ConnectionHealth,
    ConnectionInfo,
)

# Health monitoring
from .broker_health import (
    BrokerHealthChecker,
    BrokerHealthMonitor,
    BrokerHealthReport,
    HealthCheckResult,
    HealthStatus,
    HealthCheckType,
    PerformanceMetrics,
)

# Metrics collection
from .broker_metrics import (
    BrokerMetricsCollector,
    BrokerMetricsManager,
    BrokerMetricsSnapshot,
    MetricType,
    MetricAggregation,
    MetricValue,
    MetricAggregationResult,
)

# Monitoring
from .broker_monitor import (
    BrokerMonitor,
    BrokerStatus,
    Alert,
    AlertSeverity,
    AlertCategory,
)

# Routing
from .broker_router import (
    BrokerRouter,
    RoutingStrategy,
    RoutingPreference,
    RoutingDecision,
    BrokerRoute,
    BrokerCapability,
    BrokerCost,
)

# Manager
from .broker_manager import (
    BrokerManager,
    BrokerInstance,
    BrokerSelectionStrategy,
    BrokerOperationMode,
)

# Utils
from .broker_utils import (
    SymbolFormat,
    format_symbol,
    format_symbol_for_exchange,
    parse_symbol,
    normalize_symbol,
    validate_order,
    validate_order_for_exchange,
    normalize_quantity,
    normalize_price,
    calculate_order_value,
    calculate_position_size,
    order_type_to_string,
    string_to_order_type,
    time_in_force_to_string,
    string_to_time_in_force,
    calculate_position_pnl,
    calculate_position_pnl_percentage,
    calculate_position_value,
    calculate_stop_loss_price,
    calculate_take_profit_price,
    calculate_risk_reward_ratio,
    calculate_spread,
    calculate_spread_percentage,
    calculate_mid_price,
    calculate_weighted_average_price,
    calculate_backoff_time,
    mask_sensitive_data,
    truncate_string,
)

# Exceptions
from .exceptions import (
    BrokerError,
    BrokerConnectionError as BrokerConnError,
    BrokerDisconnectionError,
    BrokerTimeoutError as BrokerTimeout,
    BrokerConnectionPoolError,
    BrokerWebSocketError,
    BrokerReconnectionError,
    BrokerAuthenticationError as BrokerAuthError,
    BrokerAuthorizationError,
    BrokerAPIKeyError,
    BrokerTokenExpiredError,
    BrokerTwoFactorRequiredError,
    BrokerOrderError as BrokerOrderErr,
    BrokerOrderNotFoundError,
    BrokerOrderRejectedError,
    BrokerOrderCancellationError,
    BrokerOrderModificationError,
    BrokerOrderValidationError,
    BrokerInsufficientBalanceError,
    BrokerMarginError,
    BrokerPositionError,
    BrokerPositionNotFoundError,
    BrokerPositionCloseError,
    BrokerDataError as BrokerDataErr,
    BrokerSymbolNotFoundError,
    BrokerMarketDataUnavailableError,
    BrokerHistoricalDataError,
    BrokerRateLimitError as BrokerRateLimit,
    BrokerWebSocketDataError,
    BrokerConfigError,
    BrokerConfigNotFoundError,
    BrokerConfigValidationError,
    BrokerEndpointError,
    BrokerAccountError,
    BrokerAccountNotFoundError,
    BrokerAccountLockedError,
    BrokerAccountSuspendedError,
    BrokerHealthCheckError,
    BrokerUnhealthyError,
    BrokerDegradedError,
    BrokerOfflineError,
    BrokerRateLimitExceededError,
    BrokerRateLimitConfigError,
    BrokerFactoryError,
    BrokerNotFoundError,
    BrokerRegistrationError,
    BrokerDiscoveryError,
    BrokerRoutingError,
    BrokerNoAvailableError,
    BrokerSelectionError,
    BrokerExchangeError,
    BinanceError,
    CoinbaseError,
    KrakenError,
    BybitError,
    AlpacaError,
    OandaError,
    map_exchange_error,
    exception_to_dict,
    is_retryable_error,
)


# ============================================================================
# Package Initialization
# ============================================================================

def initialize(
    config_dir: Optional[str] = None,
    auto_discover: bool = True,
    auto_connect: bool = True,
) -> BrokerManager:
    """
    Initialize the broker system.
    
    This is the main entry point for initializing the broker subsystem.
    It sets up configuration loading, broker discovery, and creates
    the central broker manager.
    
    Args:
        config_dir: Directory containing broker configurations
        auto_discover: Whether to auto-discover broker implementations
        auto_connect: Whether to auto-connect brokers on initialization
        
    Returns:
        BrokerManager: Initialized broker manager instance
    """
    from pathlib import Path
    
    # Initialize factory
    from .broker_factory import BrokerFactory
    
    if config_dir:
        BrokerFactory.initialize(Path(config_dir), auto_discover)
    else:
        BrokerFactory.initialize(auto_discover=auto_discover)
    
    # Create manager
    manager = BrokerManager(
        config_loader=BrokerFactory.get_config_loader(),
        auto_connect=auto_connect,
    )
    
    logger.info("Broker system initialized successfully")
    return manager


def get_available_brokers() -> List[Dict[str, any]]:
    """
    Get list of all available brokers.
    
    Returns:
        List[Dict[str, any]]: List of broker information
    """
    from .broker_factory import BrokerFactory
    BrokerFactory.initialize()
    return BrokerFactory.list_available_brokers()


def create_broker(
    config: Union[BrokerConfig, BrokerConfigComplete, Dict[str, any], str],
    **kwargs,
) -> BaseBroker:
    """
    Create a single broker instance.
    
    Args:
        config: Broker configuration
        **kwargs: Additional arguments for broker creation
        
    Returns:
        BaseBroker: Broker instance
    """
    from .broker_factory import create_broker
    return create_broker(config, **kwargs)


async def create_broker_async(
    config: Union[BrokerConfig, BrokerConfigComplete, Dict[str, any], str],
    **kwargs,
) -> BaseBroker:
    """
    Create a single broker instance asynchronously.
    
    Args:
        config: Broker configuration
        **kwargs: Additional arguments for broker creation
        
    Returns:
        BaseBroker: Broker instance
    """
    from .broker_factory import create_broker_async
    return await create_broker_async(config, **kwargs)


# ============================================================================
# Convenience Variables
# ============================================================================

# Commonly used broker names
BINANCE = BrokerName.BINANCE
BYBIT = BrokerName.BYBIT
COINBASE = BrokerName.COINBASE
KRAKEN = BrokerName.KRAKEN
KUCOIN = BrokerName.KUCOIN
ALPACA = BrokerName.ALPACA
OANDA = BrokerName.OANDA
IBKR = BrokerName.IBKR
PAPER = BrokerName.PAPER
WEBHOOK = BrokerName.WEBHOOK

# Common asset classes
CRYPTO = AssetClass.CRYPTO
FOREX = AssetClass.FOREX
STOCK = AssetClass.STOCK
ETF = AssetClass.ETF
FUTURES = AssetClass.FUTURES
OPTIONS = AssetClass.OPTIONS

# Health status aliases
HEALTHY = HealthStatus.HEALTHY
DEGRADED = HealthStatus.DEGRADED
UNHEALTHY = HealthStatus.UNHEALTHY
OFFLINE = HealthStatus.OFFLINE
UNKNOWN = HealthStatus.UNKNOWN

# Alert severity aliases
INFO = AlertSeverity.INFO
WARNING = AlertSeverity.WARNING
ERROR = AlertSeverity.ERROR
CRITICAL = AlertSeverity.CRITICAL

# Routing strategy aliases
ROUND_ROBIN = RoutingStrategy.ROUND_ROBIN
LEAST_LOADED = RoutingStrategy.LEAST_LOADED
FASTEST = RoutingStrategy.FASTEST_LATENCY
LOWEST_COST = RoutingStrategy.LOWEST_COST
SYMBOL_PINNED = RoutingStrategy.SYMBOL_PINNED
SMART = RoutingStrategy.SMART
FAILOVER = RoutingStrategy.FAILOVER
RANDOM = RoutingStrategy.RANDOM


# ============================================================================
# Package Documentation
# ============================================================================

__doc__ = """
NEXUS AI Trading System - Brokers Package
=========================================

A comprehensive broker integration framework for algorithmic trading.

Quick Start:
------------
    from trading.brokers import initialize, BINANCE, PAPER
    
    # Initialize the broker system
    manager = initialize()
    
    # Add a broker
    config = {
        "name": BINANCE,
        "sandbox_mode": True,
        "auth": {
            "api_key": "your_api_key",
            "api_secret": "your_api_secret",
        }
    }
    broker_id = await manager.add_broker(config)
    
    # Place an order
    order = Order(
        symbol="BTC/USD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=0.001,
    )
    result = await manager.place_order(order)

For more information, see the documentation in each module.
"""


# ============================================================================
# Cleanup
# ============================================================================

def cleanup() -> None:
    """Clean up all broker resources."""
    import asyncio
    from .broker_factory import BrokerFactory
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(BrokerFactory.close_all())
        else:
            loop.run_until_complete(BrokerFactory.close_all())
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


# ============================================================================
# Register cleanup on interpreter exit
# ============================================================================

import atexit
atexit.register(cleanup)


# ============================================================================
# Re-export for convenience
# ============================================================================

__all__ = [
    # Version
    "__version__",
    "__author__",
    "__copyright__",
    
    # Initialization
    "initialize",
    "cleanup",
    "get_available_brokers",
    "create_broker",
    "create_broker_async",
    
    # Base
    "BaseBroker",
    "BrokerConfig",
    "BrokerName",
    "AssetClass",
    "AccountType",
    "OrderResponse",
    "AccountInfo",
    "MarketDataResponse",
    "PaperBroker",
    "WebhookBroker",
    "BrokerException",
    "BrokerConnectionError",
    "BrokerAuthenticationError",
    "BrokerRateLimitError",
    "BrokerOrderError",
    "BrokerDataError",
    "BrokerTimeoutError",
    "BrokerFactory",
    
    # Configuration
    "BrokerConfigLoader",
    "BrokerConfigComplete",
    "BrokerEndpointConfig",
    "BrokerAuthConfig",
    "BrokerRateLimitConfig",
    "BrokerRetryConfig",
    "BrokerCircuitBreakerConfig",
    "BrokerTimeoutConfig",
    "BrokerMarketConfig",
    "BrokerOrderConfig",
    "BrokerRiskConfig",
    "BrokerLoggingConfig",
    "BrokerSecurityConfig",
    "EnvironmentType",
    
    # Connection
    "BrokerConnectionManager",
    "BrokerConnectionPool",
    "BrokerConnectionFactory",
    "ConnectionState",
    "ConnectionHealth",
    "ConnectionInfo",
    
    # Health
    "BrokerHealthChecker",
    "BrokerHealthMonitor",
    "BrokerHealthReport",
    "HealthCheckResult",
    "HealthStatus",
    "HealthCheckType",
    "PerformanceMetrics",
    
    # Metrics
    "BrokerMetricsCollector",
    "BrokerMetricsManager",
    "BrokerMetricsSnapshot",
    "MetricType",
    "MetricAggregation",
    "MetricValue",
    "MetricAggregationResult",
    
    # Monitor
    "BrokerMonitor",
    "BrokerStatus",
    "Alert",
    "AlertSeverity",
    "AlertCategory",
    
    # Router
    "BrokerRouter",
    "RoutingStrategy",
    "RoutingPreference",
    "RoutingDecision",
    "BrokerRoute",
    "BrokerCapability",
    "BrokerCost",
    
    # Manager
    "BrokerManager",
    "BrokerInstance",
    "BrokerSelectionStrategy",
    "BrokerOperationMode",
    
    # Utils
    "SymbolFormat",
    "format_symbol",
    "format_symbol_for_exchange",
    "parse_symbol",
    "normalize_symbol",
    "validate_order",
    "validate_order_for_exchange",
    "normalize_quantity",
    "normalize_price",
    "calculate_order_value",
    "calculate_position_size",
    "order_type_to_string",
    "string_to_order_type",
    "time_in_force_to_string",
    "string_to_time_in_force",
    "calculate_position_pnl",
    "calculate_position_pnl_percentage",
    "calculate_position_value",
    "calculate_stop_loss_price",
    "calculate_take_profit_price",
    "calculate_risk_reward_ratio",
    "calculate_spread",
    "calculate_spread_percentage",
    "calculate_mid_price",
    "calculate_weighted_average_price",
    "calculate_backoff_time",
    "mask_sensitive_data",
    "truncate_string",
    
    # Exceptions
    "BrokerError",
    "BrokerConnError",
    "BrokerDisconnectionError",
    "BrokerTimeout",
    "BrokerConnectionPoolError",
    "BrokerWebSocketError",
    "BrokerReconnectionError",
    "BrokerAuthError",
    "BrokerAuthorizationError",
    "BrokerAPIKeyError",
    "BrokerTokenExpiredError",
    "BrokerTwoFactorRequiredError",
    "BrokerOrderErr",
    "BrokerOrderNotFoundError",
    "BrokerOrderRejectedError",
    "BrokerOrderCancellationError",
    "BrokerOrderModificationError",
    "BrokerOrderValidationError",
    "BrokerInsufficientBalanceError",
    "BrokerMarginError",
    "BrokerPositionError",
    "BrokerPositionNotFoundError",
    "BrokerPositionCloseError",
    "BrokerDataErr",
    "BrokerSymbolNotFoundError",
    "BrokerMarketDataUnavailableError",
    "BrokerHistoricalDataError",
    "BrokerRateLimit",
    "BrokerWebSocketDataError",
    "BrokerConfigError",
    "BrokerConfigNotFoundError",
    "BrokerConfigValidationError",
    "BrokerEndpointError",
    "BrokerAccountError",
    "BrokerAccountNotFoundError",
    "BrokerAccountLockedError",
    "BrokerAccountSuspendedError",
    "BrokerHealthCheckError",
    "BrokerUnhealthyError",
    "BrokerDegradedError",
    "BrokerOfflineError",
    "BrokerRateLimitExceededError",
    "BrokerRateLimitConfigError",
    "BrokerFactoryError",
    "BrokerNotFoundError",
    "BrokerRegistrationError",
    "BrokerDiscoveryError",
    "BrokerRoutingError",
    "BrokerNoAvailableError",
    "BrokerSelectionError",
    "BrokerExchangeError",
    "BinanceError",
    "CoinbaseError",
    "KrakenError",
    "BybitError",
    "AlpacaError",
    "OandaError",
    "map_exchange_error",
    "exception_to_dict",
    "is_retryable_error",
    
    # Convenience aliases
    "BINANCE",
    "BYBIT",
    "COINBASE",
    "KRAKEN",
    "KUCOIN",
    "ALPACA",
    "OANDA",
    "IBKR",
    "PAPER",
    "WEBHOOK",
    "CRYPTO",
    "FOREX",
    "STOCK",
    "ETF",
    "FUTURES",
    "OPTIONS",
    "HEALTHY",
    "DEGRADED",
    "UNHEALTHY",
    "OFFLINE",
    "UNKNOWN",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
    "ROUND_ROBIN",
    "LEAST_LOADED",
    "FASTEST",
    "LOWEST_COST",
    "SYMBOL_PINNED",
    "SMART",
    "FAILOVER",
    "RANDOM",
]
