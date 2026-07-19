"""
NEXUS AI TRADING SYSTEM - Paper Trading Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/paper-trading/__init__.py
Description: Paper Trading module initialization and exports
"""

import logging
from typing import Dict, List, Optional, Any, Type

# Import all paper trading components
from trading.paper_trading.paper_account import (
    PaperTradingAccount,
    AccountStatus,
    AccountType,
    OrderStatus,
    OrderType,
    OrderSide,
    TimeInForce,
    AccountCreateRequest,
    AccountResponse,
    OrderRequest,
    OrderResponse,
    PositionResponse,
    AccountState,
    TradeResult
)

from trading.paper_trading.paper_analytics import (
    PaperTradingAnalytics,
    AnalyticsPeriod,
    AnalyticsMetric,
    AnalyticsRequest,
    AnalyticsResponse,
    TradeAnalyticsResponse,
    AnalyticsContext,
    PerformanceSummary
)

from trading.paper_trading.paper_engine import (
    PaperTradingEngine,
    EngineStatus,
    ExecutionMode,
    EngineRequest,
    EngineResponse,
    ExecutionRequest,
    ExecutionResponse,
    EngineState,
    ExecutionResult
)

from trading.paper_trading.paper_fees import (
    PaperTradingFees,
    FeeType,
    FeeStructure,
    FeeSchedule,
    FeeConfig,
    FeeRequest,
    FeeResponse,
    FeeAnalyticsResponse,
    FeeContext,
    FeeResult,
    FeeTier
)

from trading.paper_trading.paper_market import (
    PaperTradingMarket,
    MarketStatus,
    MarketCondition,
    OrderBookDepth,
    MarketDataRequest,
    MarketDataResponse,
    OrderBookResponse,
    TradeDataResponse,
    MarketContext,
    PriceBar,
    OrderBookLevel
)

from trading.paper_trading.paper_orders import (
    PaperTradingOrders,
    OrderStatus as OrdersOrderStatus,
    OrderType as OrdersOrderType,
    OrderSide as OrdersOrderSide,
    TimeInForce as OrdersTimeInForce,
    OrderRequest as OrdersOrderRequest,
    OrderResponse as OrdersOrderResponse,
    OrderUpdateRequest,
    OrderCancelRequest,
    OrderHistoryResponse,
    OrderContext,
    OrderFill
)

from trading.paper_trading.paper_portfolio import (
    PaperTradingPortfolio,
    PortfolioStatus,
    PositionSide,
    PositionStatus,
    PortfolioRequest,
    PortfolioResponse,
    PositionRequest,
    PositionResponse,
    PortfolioMetricsResponse,
    PortfolioState,
    PositionContext
)

from trading.paper_trading.paper_replay import (
    PaperTradingReplay,
    ReplayStatus,
    ReplaySpeed,
    DataSource,
    ReplayRequest,
    ReplayResponse,
    ReplayBarData,
    ReplaySummaryResponse,
    ReplayState,
    ReplayBar
)

from trading.paper_trading.paper_reporter import (
    PaperTradingReporter,
    ReportFormat,
    ReportType,
    ChartType,
    ReportRequest,
    ReportResponse,
    ReportSchedule,
    ReportData,
    ChartData
)

from trading.paper_trading.paper_slippage import (
    PaperTradingSlippage,
    SlippageModel,
    SlippageSeverity,
    SlippageConfig,
    SlippageRequest,
    SlippageResponse,
    SlippageAnalyticsResponse,
    SlippageContext,
    SlippageResult,
    SlippageRecord
)

from trading.paper_trading.paper_validator import (
    PaperTradingValidator,
    ValidationLevel,
    ValidationResult,
    ValidationRule,
    ValidationRequest,
    ValidationResponse,
    ValidationRuleConfig,
    ValidationContext,
    ValidationCheck
)

# Module logger
logger = logging.getLogger(__name__)

# =============================================================================
# Module Metadata
# =============================================================================

__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
__description__ = "Advanced Paper Trading System for NEXUS AI Trading"

# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Paper Account
    'PaperTradingAccount',
    'AccountStatus',
    'AccountType',
    'OrderStatus',
    'OrderType',
    'OrderSide',
    'TimeInForce',
    'AccountCreateRequest',
    'AccountResponse',
    'OrderRequest',
    'OrderResponse',
    'PositionResponse',
    'AccountState',
    'TradeResult',
    
    # Paper Analytics
    'PaperTradingAnalytics',
    'AnalyticsPeriod',
    'AnalyticsMetric',
    'AnalyticsRequest',
    'AnalyticsResponse',
    'TradeAnalyticsResponse',
    'AnalyticsContext',
    'PerformanceSummary',
    
    # Paper Engine
    'PaperTradingEngine',
    'EngineStatus',
    'ExecutionMode',
    'EngineRequest',
    'EngineResponse',
    'ExecutionRequest',
    'ExecutionResponse',
    'EngineState',
    'ExecutionResult',
    
    # Paper Fees
    'PaperTradingFees',
    'FeeType',
    'FeeStructure',
    'FeeSchedule',
    'FeeConfig',
    'FeeRequest',
    'FeeResponse',
    'FeeAnalyticsResponse',
    'FeeContext',
    'FeeResult',
    'FeeTier',
    
    # Paper Market
    'PaperTradingMarket',
    'MarketStatus',
    'MarketCondition',
    'OrderBookDepth',
    'MarketDataRequest',
    'MarketDataResponse',
    'OrderBookResponse',
    'TradeDataResponse',
    'MarketContext',
    'PriceBar',
    'OrderBookLevel',
    
    # Paper Orders
    'PaperTradingOrders',
    'OrdersOrderStatus',
    'OrdersOrderType',
    'OrdersOrderSide',
    'OrdersTimeInForce',
    'OrdersOrderRequest',
    'OrdersOrderResponse',
    'OrderUpdateRequest',
    'OrderCancelRequest',
    'OrderHistoryResponse',
    'OrderContext',
    'OrderFill',
    
    # Paper Portfolio
    'PaperTradingPortfolio',
    'PortfolioStatus',
    'PositionSide',
    'PositionStatus',
    'PortfolioRequest',
    'PortfolioResponse',
    'PositionRequest',
    'PositionResponse',
    'PortfolioMetricsResponse',
    'PortfolioState',
    'PositionContext',
    
    # Paper Replay
    'PaperTradingReplay',
    'ReplayStatus',
    'ReplaySpeed',
    'DataSource',
    'ReplayRequest',
    'ReplayResponse',
    'ReplayBarData',
    'ReplaySummaryResponse',
    'ReplayState',
    'ReplayBar',
    
    # Paper Reporter
    'PaperTradingReporter',
    'ReportFormat',
    'ReportType',
    'ChartType',
    'ReportRequest',
    'ReportResponse',
    'ReportSchedule',
    'ReportData',
    'ChartData',
    
    # Paper Slippage
    'PaperTradingSlippage',
    'SlippageModel',
    'SlippageSeverity',
    'SlippageConfig',
    'SlippageRequest',
    'SlippageResponse',
    'SlippageAnalyticsResponse',
    'SlippageContext',
    'SlippageResult',
    'SlippageRecord',
    
    # Paper Validator
    'PaperTradingValidator',
    'ValidationLevel',
    'ValidationResult',
    'ValidationRule',
    'ValidationRequest',
    'ValidationResponse',
    'ValidationRuleConfig',
    'ValidationContext',
    'ValidationCheck'
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
        'name': 'trading.paper_trading',
        'version': __version__,
        'author': __author__,
        'description': __description__,
        'components': [
            'PaperTradingAccount',
            'PaperTradingAnalytics',
            'PaperTradingEngine',
            'PaperTradingFees',
            'PaperTradingMarket',
            'PaperTradingOrders',
            'PaperTradingPortfolio',
            'PaperTradingReplay',
            'PaperTradingReporter',
            'PaperTradingSlippage',
            'PaperTradingValidator'
        ]
    }


def get_component_dependencies() -> Dict[str, List[str]]:
    """
    Get component dependencies.
    
    Returns:
        Dict[str, List[str]]: Component dependencies
    """
    return {
        'PaperTradingAccount': ['PositionRepository', 'OrderRepository', 'TradeRepository'],
        'PaperTradingAnalytics': ['TradeRepository', 'OrderRepository', 'PositionRepository'],
        'PaperTradingEngine': ['TradeRepository', 'OrderRepository', 'PositionRepository'],
        'PaperTradingFees': ['TradeRepository', 'OrderRepository'],
        'PaperTradingMarket': ['BrokerFactory'],
        'PaperTradingOrders': ['OrderRepository', 'TradeRepository'],
        'PaperTradingPortfolio': ['PositionRepository', 'TradeRepository'],
        'PaperTradingReplay': ['TradeRepository', 'OrderRepository', 'PositionRepository'],
        'PaperTradingReporter': ['TradeRepository', 'OrderRepository', 'PositionRepository'],
        'PaperTradingSlippage': ['TradeRepository', 'OrderRepository'],
        'PaperTradingValidator': ['TradeRepository', 'OrderRepository', 'PositionRepository']
    }


def get_default_config() -> Dict[str, Any]:
    """
    Get default configuration for paper trading components.
    
    Returns:
        Dict[str, Any]: Default configuration
    """
    return {
        'account': {
            'initial_balance': 100000.0,
            'currency': 'USD',
            'leverage': 1.0
        },
        'analytics': {
            'default_period': 'month',
            'include_history': True,
            'include_charts': False
        },
        'engine': {
            'execution_mode': 'real_time',
            'check_interval': 1,
            'max_orders_per_second': 10
        },
        'fees': {
            'default_model': 'percentage',
            'maker_rate': 0.001,
            'taker_rate': 0.002,
            'min_fee': 0.01
        },
        'market': {
            'default_depth': 'level_1',
            'update_interval': 0.1,
            'volatility': 0.02
        },
        'orders': {
            'max_orders': 100,
            'order_timeout': 300,
            'default_time_in_force': 'gtc'
        },
        'portfolio': {
            'max_positions': 50,
            'max_position_size': 1000,
            'min_position_size': 0.01
        },
        'replay': {
            'default_speed': 'real_time',
            'default_data_source': 'historical',
            'bars_per_second': 1
        },
        'reporter': {
            'default_format': 'pdf',
            'include_charts': True,
            'include_tables': True
        },
        'slippage': {
            'default_model': 'hybrid',
            'fixed_rate': 0.001,
            'max_slippage': 0.05,
            'min_slippage': 0.0
        },
        'validator': {
            'default_level': 'standard',
            'min_order_size': 0.001,
            'max_order_size': 1000000,
            'max_leverage': 2.0,
            'risk_limit': 0.05,
            'daily_loss_limit': 10000
        }
    }


def initialize_paper_trading(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Initialize all paper trading components.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Dict[str, Any]: Initialized components
    """
    from trading.paper_trading.paper_account import PaperTradingAccount
    from trading.paper_trading.paper_analytics import PaperTradingAnalytics
    from trading.paper_trading.paper_engine import PaperTradingEngine
    from trading.paper_trading.paper_fees import PaperTradingFees
    from trading.paper_trading.paper_market import PaperTradingMarket
    from trading.paper_trading.paper_orders import PaperTradingOrders
    from trading.paper_trading.paper_portfolio import PaperTradingPortfolio
    from trading.paper_trading.paper_replay import PaperTradingReplay
    from trading.paper_trading.paper_reporter import PaperTradingReporter
    from trading.paper_trading.paper_slippage import PaperTradingSlippage
    from trading.paper_trading.paper_validator import PaperTradingValidator
    
    config = config or get_default_config()
    
    components = {
        'account': PaperTradingAccount(config.get('account', {})),
        'analytics': PaperTradingAnalytics(config.get('analytics', {})),
        'engine': PaperTradingEngine(config.get('engine', {})),
        'fees': PaperTradingFees(config.get('fees', {})),
        'market': PaperTradingMarket(config.get('market', {})),
        'orders': PaperTradingOrders(config.get('orders', {})),
        'portfolio': PaperTradingPortfolio(config.get('portfolio', {})),
        'replay': PaperTradingReplay(config.get('replay', {})),
        'reporter': PaperTradingReporter(config.get('reporter', {})),
        'slippage': PaperTradingSlippage(config.get('slippage', {})),
        'validator': PaperTradingValidator(config.get('validator', {}))
    }
    
    logger.info("Paper trading components initialized successfully")
    return components


def get_router() -> Any:
    """
    Get FastAPI router for paper trading endpoints.
    
    Returns:
        Any: FastAPI router
    """
    from fastapi import APIRouter
    
    router = APIRouter(prefix="/api/v1/paper-trading", tags=["Paper Trading"])
    
    # Import all routers
    from trading.paper_trading.paper_account import router as account_router
    from trading.paper_trading.paper_analytics import router as analytics_router
    from trading.paper_trading.paper_engine import router as engine_router
    from trading.paper_trading.paper_fees import router as fees_router
    from trading.paper_trading.paper_market import router as market_router
    from trading.paper_trading.paper_orders import router as orders_router
    from trading.paper_trading.paper_portfolio import router as portfolio_router
    from trading.paper_trading.paper_replay import router as replay_router
    from trading.paper_trading.paper_reporter import router as reporter_router
    from trading.paper_trading.paper_slippage import router as slippage_router
    from trading.paper_trading.paper_validator import router as validator_router
    
    # Include routers
    router.include_router(account_router)
    router.include_router(analytics_router)
    router.include_router(engine_router)
    router.include_router(fees_router)
    router.include_router(market_router)
    router.include_router(orders_router)
    router.include_router(portfolio_router)
    router.include_router(replay_router)
    router.include_router(reporter_router)
    router.include_router(slippage_router)
    router.include_router(validator_router)
    
    return router


# =============================================================================
# Module Initialization
# =============================================================================

logger.info(f"Paper Trading Module v{__version__} loaded successfully")

# Export FastAPI router
paper_trading_router = get_router()
