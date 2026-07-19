# trading/bots/arbitrage_bot/core/__init__.py
# Nexus AI Trading System - Arbitrage Bot Core Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with all implementations

"""
Arbitrage Bot - Core Module

This module provides the core infrastructure for the arbitrage bot system,
including all essential components for arbitrage detection, execution,
and risk management.

Module Structure:
    core/
    ├── __init__.py                 # Module initialization and exports
    ├── arbitrage_engine.py         # Main arbitrage detection and execution engine
    ├── arbitrage_types.py          # Type definitions for arbitrage operations
    ├── balance_manager.py          # Multi-exchange balance management
    ├── base_arbitrage.py           # Base arbitrage engine class
    ├── circuit_breaker.py          # Circuit breaker pattern implementation
    ├── exchange_connector.py       # Unified exchange connection interface
    ├── execution_timer.py          # Execution timing and latency monitoring
    ├── fee_calculator.py           # Multi-exchange fee calculation
    ├── gas_calculator.py           # Blockchain gas cost calculation
    ├── latency_monitor.py          # Latency monitoring and analytics
    ├── market_data.py              # Market data aggregation and management
    ├── order_router.py             # Smart order routing across exchanges
    ├── order_scheduler.py          # Order scheduling and timing optimization
    ├── order_splitter.py           # Order splitting and size optimization
    ├── order_validator.py          # Order validation and verification
    ├── portfolio_manager.py        # Portfolio management and analytics
    ├── position_tracker.py         # Position tracking and monitoring
    ├── profit_calculator.py        # Profit calculation and optimization
    ├── rate_limiter.py             # Rate limiting and request management
    ├── risk_calculator.py          # Risk calculation and management
    └── slippage_calculator.py      # Slippage calculation and optimization

Features:
    - Multi-exchange arbitrage detection
    - Smart order routing and execution
    - Real-time market data aggregation
    - Comprehensive risk management
    - Advanced fee and slippage optimization
    - Position and portfolio tracking
    - Performance analytics and reporting
    - Circuit breaker protection
    - Rate limiting and request management
    - Distributed architecture support
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union, Type, Tuple
from dataclasses import dataclass, field

# =============================================================================
# CORE COMPONENT EXPORTS
# =============================================================================

# Arbitrage Types
from trading.bots.arbitrage_bot.core.arbitrage_types import (
    ArbitrageType,
    ArbitrageStatus,
    ArbitrageExecutionType,
    ArbitrageRiskLevel,
    ExchangeType,
    OrderStatus,
    ArbitrageOpportunity,
    ArbitrageExecution,
    ExchangeConfig,
    ArbitrageStrategyConfig,
    ArbitrageStatisticalData,
    ArbitrageRiskMetrics,
    ArbitragePerformanceMetrics,
    StatisticalArbitrageModel,
    calculate_arbitrage_profit,
    calculate_risk_score
)

# Balance Manager
from trading.bots.arbitrage_bot.core.balance_manager import (
    BalanceManager,
    BalanceStatus,
    BalanceUpdateType,
    BalanceAllocationStrategy,
    CurrencyType,
    Balance,
    BalanceSnapshot,
    BalanceAlert,
    BalanceAllocation,
    ExchangeBalanceAdapter,
    OKXBalanceAdapter,
    KrakenBalanceAdapter,
    BinanceBalanceAdapter,
    BalanceError,
    BalanceNotFoundError,
    BalanceInsufficientError,
    BalanceAllocationError
)

# Base Arbitrage
from trading.bots.arbitrage_bot.core.base_arbitrage import (
    BaseArbitrageEngine,
    EngineStatus,
    EngineEventType,
    EngineState,
    EngineConfig,
    EnginePerformance,
    ArbitrageEngineFactory
)

# Circuit Breaker
from trading.bots.arbitrage_bot.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerGroup,
    CircuitBreakerState,
    CircuitBreakerEvent,
    FailureType,
    CircuitBreakerConfig,
    CircuitBreakerStateData,
    CircuitBreakerMetrics,
    CircuitBreakerOpenError,
    CircuitBreakerTimeoutError,
    CircuitBreakerRateLimitError
)

# Exchange Connector
from trading.bots.arbitrage_bot.core.exchange_connector import (
    ExchangeConnector,
    ExchangeStatus,
    ExchangeOrderType,
    ExchangeOrderSide,
    ExchangeOrderStatus,
    ExchangeTimeInForce,
    ExchangeConnectionConfig,
    ExchangeBalance,
    ExchangePrice,
    ExchangeOrder,
    ExchangeOrderBook,
    ExchangeTrade,
    ExchangeConnectorFactory,
    ExchangeRateLimiter,
    ExchangeConnectionError,
    ExchangeAuthenticationError,
    ExchangeRateLimitError,
    ExchangeInvalidSymbolError,
    ExchangeInsufficientFundsError,
    ExchangeOrderError,
    ExchangeOrderNotFoundError,
    ExchangeWebSocketError,
    CircuitBreakerOpenError as ExchangeCircuitBreakerOpenError
)

# Execution Timer
from trading.bots.arbitrage_bot.core.execution_timer import (
    ExecutionTimer,
    TimerStatus,
    TimerMetricType,
    TimerSeverity,
    ExecutionTimerConfig,
    TimerMetric,
    TimerStatistics,
    ExecutionTimerSnapshot,
    timed,
    get_timer
)

# Fee Calculator
from trading.bots.arbitrage_bot.core.fee_calculator import (
    FeeCalculator,
    FeeType,
    FeeTier,
    FeeDiscountType,
    FeeCurrency,
    FeeConfig,
    FeeCalculation,
    GasCost,
    FeeHistory
)

# Gas Calculator
from trading.bots.arbitrage_bot.core.gas_calculator import (
    GasCalculator,
    Chain,
    GasPricePriority,
    TransactionType,
    GasToken,
    GasPrice,
    GasEstimate,
    GasHistory,
    GasOptimization,
    GasPriceUnavailableError,
    GasEstimateError
)

# Latency Monitor
from trading.bots.arbitrage_bot.core.latency_monitor import (
    LatencyMonitor,
    LatencySource,
    LatencySeverity,
    LatencyStatus,
    LatencyConfig,
    LatencyMetric,
    LatencyStatistics,
    LatencyAlert,
    LatencySnapshot,
    measure_latency,
    get_latency_monitor
)

# Market Data
from trading.bots.arbitrage_bot.core.market_data import (
    MarketDataManager,
    MarketDataSource,
    MarketDataStatus,
    SpreadType,
    MarketDataConfig,
    MarketPrice,
    MarketDepth,
    MarketTrade,
    MarketSpread,
    MarketSummary
)

# Order Router
from trading.bots.arbitrage_bot.core.order_router import (
    OrderRouter,
    OrderRouterType,
    OrderExecutionStrategy,
    ExecutionQuality,
    OrderRoutingStatus,
    OrderRoute,
    RoutingRequest,
    RoutingResponse,
    ExecutionReport,
    CircuitBreakerOpenError as OrderRouterCircuitBreakerOpenError,
    RoutingError,
    ExecutionError
)

# Order Scheduler
from trading.bots.arbitrage_bot.core.order_scheduler import (
    OrderScheduler,
    SchedulePriority,
    ScheduleStatus,
    ScheduleType,
    ExecutionWindow,
    ScheduleConfig,
    ScheduledOrder,
    ScheduleExecution,
    ScheduleQueueStatus
)

# Order Splitter
from trading.bots.arbitrage_bot.core.order_splitter import (
    OrderSplitter,
    SplitStrategy,
    SplitStatus,
    SplitType,
    SplitConfig,
    SplitRequest,
    SplitChunk,
    SplitResponse,
    CircuitBreakerOpenError as SplitterCircuitBreakerOpenError,
    SplitError
)

# Order Validator
from trading.bots.arbitrage_bot.core.order_validator import (
    OrderValidator,
    ValidationSeverity,
    ValidationResult,
    ValidationType,
    ValidationConfig,
    ValidationRequest,
    ValidationResultItem,
    ValidationResponse,
    OrderValidationMetrics,
    validate_order,
    ValidationFailedError
)

# Portfolio Manager
from trading.bots.arbitrage_bot.core.portfolio_manager import (
    PortfolioManager,
    PortfolioStatus,
    PositionType,
    RiskLevel as PortfolioRiskLevel,
    AllocationStrategy,
    PortfolioConfig,
    PortfolioPosition,
    PortfolioSnapshot,
    PortfolioMetrics,
    PortfolioAllocation,
    CircuitBreakerOpenError as PortfolioCircuitBreakerOpenError
)

# Position Tracker
from trading.bots.arbitrage_bot.core.position_tracker import (
    PositionTracker,
    PositionStatus,
    PositionLegStatus,
    PositionSide,
    PositionType as TrackerPositionType,
    PositionExitReason,
    PositionLeg,
    Position,
    PositionAlert,
    PositionSummary,
    CircuitBreakerOpenError as TrackerCircuitBreakerOpenError
)

# Profit Calculator
from trading.bots.arbitrage_bot.core.profit_calculator import (
    ProfitCalculator,
    ProfitType,
    ProfitMetric,
    ProfitStatus,
    ProfitCalculation,
    ProfitMetrics,
    ProfitHistory,
    ProfitForecast
)

# Rate Limiter
from trading.bots.arbitrage_bot.core.rate_limiter import (
    RateLimiter,
    RateLimiterFactory,
    RateLimitType,
    RateLimitStatus,
    RateLimitPriority,
    RequestType,
    RateLimitConfig,
    RateLimitRequest,
    RateLimitResponse,
    RateLimitStats,
    rate_limited,
    RateLimitExceededError
)

# Risk Calculator
from trading.bots.arbitrage_bot.core.risk_calculator import (
    RiskCalculator,
    RiskMetricType,
    RiskLevel,
    RiskCategory,
    RiskStatus,
    RiskConfig,
    RiskMetric,
    PositionRisk,
    PortfolioRisk,
    StressTestResult,
    RiskAlert
)

# Slippage Calculator
from trading.bots.arbitrage_bot.core.slippage_calculator import (
    SlippageCalculator,
    SlippageType,
    SlippageLevel,
    SlippageStatus,
    SlippageConfig,
    SlippageEstimate,
    SlippageHistory,
    SlippageStatistics,
    SlippageOptimization,
    CircuitBreakerOpenError as SlippageCircuitBreakerOpenError
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
# ARBITRAGE BOT CORE FACTORY
# =============================================================================

class ArbitrageBotCoreFactory:
    """
    Factory for creating arbitrage bot core components.
    
    This factory provides a unified interface for creating and managing
    all core arbitrage bot components.
    """
    
    @staticmethod
    async def create_balance_manager(
        redis: Optional[Any] = None,
        pool: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> BalanceManager:
        """Create a balance manager instance."""
        manager = BalanceManager(redis, pool, config)
        await manager.initialize()
        return manager
    
    @staticmethod
    async def create_circuit_breaker(
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None
    ) -> CircuitBreaker:
        """Create a circuit breaker instance."""
        breaker = CircuitBreaker(name, config, redis, pool)
        await breaker.initialize()
        return breaker
    
    @staticmethod
    async def create_exchange_connector(
        config: ExchangeConnectionConfig,
        circuit_breaker: Optional[CircuitBreaker] = None,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None
    ) -> ExchangeConnector:
        """Create an exchange connector instance."""
        return ExchangeConnectorFactory.create_connector(
            config, circuit_breaker, redis, pool
        )
    
    @staticmethod
    async def create_execution_timer(
        name: str,
        config: Optional[ExecutionTimerConfig] = None,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None
    ) -> ExecutionTimer:
        """Create an execution timer instance."""
        timer = ExecutionTimer(name, config, redis, pool)
        await timer.initialize()
        return timer
    
    @staticmethod
    async def create_fee_calculator(
        redis: Optional[Any] = None,
        pool: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> FeeCalculator:
        """Create a fee calculator instance."""
        calculator = FeeCalculator(redis, pool, config)
        await calculator.initialize()
        return calculator
    
    @staticmethod
    async def create_gas_calculator(
        redis: Optional[Any] = None,
        pool: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> GasCalculator:
        """Create a gas calculator instance."""
        calculator = GasCalculator(redis, pool, config)
        await calculator.initialize()
        return calculator
    
    @staticmethod
    async def create_latency_monitor(
        redis: Optional[Any] = None,
        pool: Optional[Any] = None,
        config: Optional[LatencyConfig] = None
    ) -> LatencyMonitor:
        """Create a latency monitor instance."""
        monitor = LatencyMonitor(redis, pool, config)
        await monitor.initialize()
        return monitor
    
    @staticmethod
    async def create_market_data_manager(
        redis: Optional[Any] = None,
        pool: Optional[Any] = None,
        config: Optional[MarketDataConfig] = None
    ) -> MarketDataManager:
        """Create a market data manager instance."""
        manager = MarketDataManager(redis, pool, config)
        await manager.initialize()
        return manager
    
    @staticmethod
    async def create_order_router(
        market_data: MarketDataManager,
        fee_calculator: FeeCalculator,
        latency_monitor: Optional[LatencyMonitor] = None,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> OrderRouter:
        """Create an order router instance."""
        router = OrderRouter(market_data, fee_calculator, latency_monitor, redis, pool, config)
        await router.initialize()
        return router
    
    @staticmethod
    async def create_order_scheduler(
        order_router: OrderRouter,
        market_data: MarketDataManager,
        latency_monitor: Optional[LatencyMonitor] = None,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None,
        config: Optional[ScheduleConfig] = None
    ) -> OrderScheduler:
        """Create an order scheduler instance."""
        scheduler = OrderScheduler(order_router, market_data, latency_monitor, redis, pool, config)
        await scheduler.initialize()
        return scheduler
    
    @staticmethod
    async def create_order_splitter(
        market_data: MarketDataManager,
        fee_calculator: FeeCalculator,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None,
        config: Optional[SplitConfig] = None
    ) -> OrderSplitter:
        """Create an order splitter instance."""
        splitter = OrderSplitter(market_data, fee_calculator, redis, pool, config)
        await splitter.initialize()
        return splitter
    
    @staticmethod
    async def create_order_validator(
        market_data: MarketDataManager,
        balance_manager: BalanceManager,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None,
        config: Optional[ValidationConfig] = None
    ) -> OrderValidator:
        """Create an order validator instance."""
        validator = OrderValidator(market_data, balance_manager, redis, pool, config)
        await validator.initialize()
        return validator
    
    @staticmethod
    async def create_portfolio_manager(
        balance_manager: BalanceManager,
        market_data: MarketDataManager,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None,
        config: Optional[PortfolioConfig] = None
    ) -> PortfolioManager:
        """Create a portfolio manager instance."""
        manager = PortfolioManager(balance_manager, market_data, redis, pool, config)
        await manager.initialize()
        return manager
    
    @staticmethod
    async def create_position_tracker(
        market_data: MarketDataManager,
        balance_manager: BalanceManager,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> PositionTracker:
        """Create a position tracker instance."""
        tracker = PositionTracker(market_data, balance_manager, redis, pool, config)
        await tracker.initialize()
        return tracker
    
    @staticmethod
    async def create_profit_calculator(
        fee_calculator: Optional[FeeCalculator] = None,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> ProfitCalculator:
        """Create a profit calculator instance."""
        calculator = ProfitCalculator(fee_calculator, redis, pool, config)
        await calculator.initialize()
        return calculator
    
    @staticmethod
    async def create_rate_limiter(
        name: str,
        config: Optional[RateLimitConfig] = None,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None
    ) -> RateLimiter:
        """Create a rate limiter instance."""
        return RateLimiterFactory.get_limiter(name, config, redis, pool)
    
    @staticmethod
    async def create_risk_calculator(
        market_data: MarketDataManager,
        balance_manager: BalanceManager,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None,
        config: Optional[RiskConfig] = None
    ) -> RiskCalculator:
        """Create a risk calculator instance."""
        calculator = RiskCalculator(market_data, balance_manager, redis, pool, config)
        await calculator.initialize()
        return calculator
    
    @staticmethod
    async def create_slippage_calculator(
        market_data: MarketDataManager,
        redis: Optional[Any] = None,
        pool: Optional[Any] = None,
        config: Optional[SlippageConfig] = None
    ) -> SlippageCalculator:
        """Create a slippage calculator instance."""
        calculator = SlippageCalculator(market_data, redis, pool, config)
        await calculator.initialize()
        return calculator


# =============================================================================
# COMPLETE CORE INITIALIZATION
# =============================================================================

async def initialize_arbitrage_core(
    redis: Optional[Any] = None,
    pool: Optional[Any] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Initialize the complete arbitrage bot core.
    
    Args:
        redis: Redis client for caching and distributed operations
        pool: PostgreSQL connection pool for persistence
        config: Global configuration
        
    Returns:
        Dict containing all core components
    """
    # Create all components
    components = {}
    
    # Balance Manager
    balance_manager = await ArbitrageBotCoreFactory.create_balance_manager(
        redis, pool, config.get('balance_manager') if config else None
    )
    components['balance_manager'] = balance_manager
    
    # Fee Calculator
    fee_calculator = await ArbitrageBotCoreFactory.create_fee_calculator(
        redis, pool, config.get('fee_calculator') if config else None
    )
    components['fee_calculator'] = fee_calculator
    
    # Market Data Manager
    market_data = await ArbitrageBotCoreFactory.create_market_data_manager(
        redis, pool, config.get('market_data') if config else None
    )
    components['market_data'] = market_data
    
    # Latency Monitor
    latency_monitor = await ArbitrageBotCoreFactory.create_latency_monitor(
        redis, pool, config.get('latency_monitor') if config else None
    )
    components['latency_monitor'] = latency_monitor
    
    # Order Router
    order_router = await ArbitrageBotCoreFactory.create_order_router(
        market_data, fee_calculator, latency_monitor, redis, pool,
        config.get('order_router') if config else None
    )
    components['order_router'] = order_router
    
    # Order Validator
    order_validator = await ArbitrageBotCoreFactory.create_order_validator(
        market_data, balance_manager, redis, pool,
        config.get('order_validator') if config else None
    )
    components['order_validator'] = order_validator
    
    # Order Splitter
    order_splitter = await ArbitrageBotCoreFactory.create_order_splitter(
        market_data, fee_calculator, redis, pool,
        config.get('order_splitter') if config else None
    )
    components['order_splitter'] = order_splitter
    
    # Order Scheduler
    order_scheduler = await ArbitrageBotCoreFactory.create_order_scheduler(
        order_router, market_data, latency_monitor, redis, pool,
        config.get('order_scheduler') if config else None
    )
    components['order_scheduler'] = order_scheduler
    
    # Position Tracker
    position_tracker = await ArbitrageBotCoreFactory.create_position_tracker(
        market_data, balance_manager, redis, pool,
        config.get('position_tracker') if config else None
    )
    components['position_tracker'] = position_tracker
    
    # Portfolio Manager
    portfolio_manager = await ArbitrageBotCoreFactory.create_portfolio_manager(
        balance_manager, market_data, redis, pool,
        config.get('portfolio_manager') if config else None
    )
    components['portfolio_manager'] = portfolio_manager
    
    # Profit Calculator
    profit_calculator = await ArbitrageBotCoreFactory.create_profit_calculator(
        fee_calculator, redis, pool,
        config.get('profit_calculator') if config else None
    )
    components['profit_calculator'] = profit_calculator
    
    # Risk Calculator
    risk_calculator = await ArbitrageBotCoreFactory.create_risk_calculator(
        market_data, balance_manager, redis, pool,
        config.get('risk_calculator') if config else None
    )
    components['risk_calculator'] = risk_calculator
    
    # Slippage Calculator
    slippage_calculator = await ArbitrageBotCoreFactory.create_slippage_calculator(
        market_data, redis, pool,
        config.get('slippage_calculator') if config else None
    )
    components['slippage_calculator'] = slippage_calculator
    
    # Gas Calculator
    gas_calculator = await ArbitrageBotCoreFactory.create_gas_calculator(
        redis, pool, config.get('gas_calculator') if config else None
    )
    components['gas_calculator'] = gas_calculator
    
    # Rate Limiters
    components['rate_limiters'] = {}
    
    logger.info("Arbitrage bot core initialized with all components")
    return components


# =============================================================================
# MODULE INITIALIZATION
# =============================================================================

logger.info(f"Arbitrage bot core module v{__version__} initialized")
logger.info(f"Supported by {__copyright__}")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Arbitrage Types
    'ArbitrageType',
    'ArbitrageStatus',
    'ArbitrageExecutionType',
    'ArbitrageRiskLevel',
    'ExchangeType',
    'OrderStatus',
    'ArbitrageOpportunity',
    'ArbitrageExecution',
    'ExchangeConfig',
    'ArbitrageStrategyConfig',
    'ArbitrageStatisticalData',
    'ArbitrageRiskMetrics',
    'ArbitragePerformanceMetrics',
    'StatisticalArbitrageModel',
    'calculate_arbitrage_profit',
    'calculate_risk_score',
    
    # Balance Manager
    'BalanceManager',
    'BalanceStatus',
    'BalanceUpdateType',
    'BalanceAllocationStrategy',
    'CurrencyType',
    'Balance',
    'BalanceSnapshot',
    'BalanceAlert',
    'BalanceAllocation',
    'ExchangeBalanceAdapter',
    'OKXBalanceAdapter',
    'KrakenBalanceAdapter',
    'BinanceBalanceAdapter',
    'BalanceError',
    'BalanceNotFoundError',
    'BalanceInsufficientError',
    'BalanceAllocationError',
    
    # Base Arbitrage
    'BaseArbitrageEngine',
    'EngineStatus',
    'EngineEventType',
    'EngineState',
    'EngineConfig',
    'EnginePerformance',
    'ArbitrageEngineFactory',
    
    # Circuit Breaker
    'CircuitBreaker',
    'CircuitBreakerGroup',
    'CircuitBreakerState',
    'CircuitBreakerEvent',
    'FailureType',
    'CircuitBreakerConfig',
    'CircuitBreakerStateData',
    'CircuitBreakerMetrics',
    'CircuitBreakerOpenError',
    'CircuitBreakerTimeoutError',
    'CircuitBreakerRateLimitError',
    
    # Exchange Connector
    'ExchangeConnector',
    'ExchangeStatus',
    'ExchangeOrderType',
    'ExchangeOrderSide',
    'ExchangeOrderStatus',
    'ExchangeTimeInForce',
    'ExchangeConnectionConfig',
    'ExchangeBalance',
    'ExchangePrice',
    'ExchangeOrder',
    'ExchangeOrderBook',
    'ExchangeTrade',
    'ExchangeConnectorFactory',
    'ExchangeRateLimiter',
    'ExchangeConnectionError',
    'ExchangeAuthenticationError',
    'ExchangeRateLimitError',
    'ExchangeInvalidSymbolError',
    'ExchangeInsufficientFundsError',
    'ExchangeOrderError',
    'ExchangeOrderNotFoundError',
    'ExchangeWebSocketError',
    
    # Execution Timer
    'ExecutionTimer',
    'TimerStatus',
    'TimerMetricType',
    'TimerSeverity',
    'ExecutionTimerConfig',
    'TimerMetric',
    'TimerStatistics',
    'ExecutionTimerSnapshot',
    'timed',
    'get_timer',
    
    # Fee Calculator
    'FeeCalculator',
    'FeeType',
    'FeeTier',
    'FeeDiscountType',
    'FeeCurrency',
    'FeeConfig',
    'FeeCalculation',
    'GasCost',
    'FeeHistory',
    
    # Gas Calculator
    'GasCalculator',
    'Chain',
    'GasPricePriority',
    'TransactionType',
    'GasToken',
    'GasPrice',
    'GasEstimate',
    'GasHistory',
    'GasOptimization',
    'GasPriceUnavailableError',
    'GasEstimateError',
    
    # Latency Monitor
    'LatencyMonitor',
    'LatencySource',
    'LatencySeverity',
    'LatencyStatus',
    'LatencyConfig',
    'LatencyMetric',
    'LatencyStatistics',
    'LatencyAlert',
    'LatencySnapshot',
    'measure_latency',
    'get_latency_monitor',
    
    # Market Data
    'MarketDataManager',
    'MarketDataSource',
    'MarketDataStatus',
    'SpreadType',
    'MarketDataConfig',
    'MarketPrice',
    'MarketDepth',
    'MarketTrade',
    'MarketSpread',
    'MarketSummary',
    
    # Order Router
    'OrderRouter',
    'OrderRouterType',
    'OrderExecutionStrategy',
    'ExecutionQuality',
    'OrderRoutingStatus',
    'OrderRoute',
    'RoutingRequest',
    'RoutingResponse',
    'ExecutionReport',
    'RoutingError',
    'ExecutionError',
    
    # Order Scheduler
    'OrderScheduler',
    'SchedulePriority',
    'ScheduleStatus',
    'ScheduleType',
    'ExecutionWindow',
    'ScheduleConfig',
    'ScheduledOrder',
    'ScheduleExecution',
    'ScheduleQueueStatus',
    
    # Order Splitter
    'OrderSplitter',
    'SplitStrategy',
    'SplitStatus',
    'SplitType',
    'SplitConfig',
    'SplitRequest',
    'SplitChunk',
    'SplitResponse',
    'SplitError',
    
    # Order Validator
    'OrderValidator',
    'ValidationSeverity',
    'ValidationResult',
    'ValidationType',
    'ValidationConfig',
    'ValidationRequest',
    'ValidationResultItem',
    'ValidationResponse',
    'OrderValidationMetrics',
    'validate_order',
    'ValidationFailedError',
    
    # Portfolio Manager
    'PortfolioManager',
    'PortfolioStatus',
    'PositionType',
    'AllocationStrategy',
    'PortfolioConfig',
    'PortfolioPosition',
    'PortfolioSnapshot',
    'PortfolioMetrics',
    'PortfolioAllocation',
    
    # Position Tracker
    'PositionTracker',
    'PositionStatus',
    'PositionLegStatus',
    'PositionSide',
    'PositionExitReason',
    'PositionLeg',
    'Position',
    'PositionAlert',
    'PositionSummary',
    
    # Profit Calculator
    'ProfitCalculator',
    'ProfitType',
    'ProfitMetric',
    'ProfitStatus',
    'ProfitCalculation',
    'ProfitMetrics',
    'ProfitHistory',
    'ProfitForecast',
    
    # Rate Limiter
    'RateLimiter',
    'RateLimiterFactory',
    'RateLimitType',
    'RateLimitStatus',
    'RateLimitPriority',
    'RequestType',
    'RateLimitConfig',
    'RateLimitRequest',
    'RateLimitResponse',
    'RateLimitStats',
    'rate_limited',
    'RateLimitExceededError',
    
    # Risk Calculator
    'RiskCalculator',
    'RiskMetricType',
    'RiskLevel',
    'RiskCategory',
    'RiskStatus',
    'RiskConfig',
    'RiskMetric',
    'PositionRisk',
    'PortfolioRisk',
    'StressTestResult',
    'RiskAlert',
    
    # Slippage Calculator
    'SlippageCalculator',
    'SlippageType',
    'SlippageLevel',
    'SlippageStatus',
    'SlippageConfig',
    'SlippageEstimate',
    'SlippageHistory',
    'SlippageStatistics',
    'SlippageOptimization',
    
    # Factory
    'ArbitrageBotCoreFactory',
    'initialize_arbitrage_core',
    
    # Module info
    '__version__',
    '__author__',
    '__copyright__'
]
