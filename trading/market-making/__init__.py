"""
NEXUS AI TRADING SYSTEM - Market Making Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/market-making/__init__.py
Description: Market Making module initialization and exports
"""

import logging
from typing import Dict, List, Optional, Any, Type

# Import all market making components
from trading.market_making.base import (
    BaseMarketMaker,
    MarketMakingStrategy,
    MarketMakingMode,
    QuoteStatus,
    InventoryState,
    OrderPlacementType,
    MarketMakingState,
    QuoteParameters,
    OrderRequest,
    Quote,
    OrderResult,
    InventoryInfo
)

from trading.market_making.order_book import (
    OrderBookManager,
    OrderBookLevel,
    OrderBookState,
    OrderBookStats,
    OrderBookLevelData,
    OrderBookSnapshot,
    OrderBookUpdate,
    OrderBookConfig,
    OrderSide,
    OrderBookStatus,
    OrderBookUpdateType
)

from trading.market_making.analytics import (
    MarketMakingAnalytics,
    AnalyticsPeriod,
    MetricType,
    PerformanceMetric,
    AnalyticsRequest,
    AnalyticsResponse,
    SpreadAnalytics,
    VolumeAnalytics,
    LiquidityAnalytics,
    ProfitabilityAnalytics,
    InventoryAnalytics,
    OrderAnalytics,
    PerformanceAnalytics,
    AnalyticsContext,
    AnalyticsResult
)

from trading.market_making.hedging import (
    HedgingManager,
    HedgingType,
    HedgingMode,
    HedgeStatus,
    HedgeDirection,
    HedgeRequest,
    HedgeResponse,
    HedgeAnalyticsResponse,
    HedgePosition,
    HedgeContext,
    HedgeResult
)

from trading.market_making.inventory_manager import (
    InventoryManager,
    InventoryStrategy,
    InventoryAction,
    InventoryRiskLevel,
    InventoryRequest,
    InventoryResponse,
    InventoryAnalyticsResponse,
    InventoryPosition,
    InventoryContext,
    InventoryDecision
)

from trading.market_making.market_maker import (
    MarketMaker,
    MarketMakerStatus,
    QuoteAdjustmentType,
    MarketMakerRequest,
    MarketMakerResponse,
    QuoteRequest,
    MarketMakerContext,
    QuoteResult
)

from trading.market_making.pricing import (
    PricingManager,
    PricingModel,
    PriceAdjustmentType,
    PricingRequest,
    PricingResponse,
    PricePredictionResponse,
    PricingContext,
    PriceResult,
    VolatilitySurface
)

from trading.market_making.reporter import (
    MarketMakingReporter,
    ReportFormat,
    ReportType,
    ChartType,
    ReportRequest,
    ReportResponse,
    ReportSchedule,
    ReportData,
    ChartData
)

from trading.market_making.risk_manager import (
    MarketMakingRiskManager,
    RiskLimitType,
    RiskLevel,
    RiskAction,
    RiskLimitConfig,
    RiskMetricsRequest,
    RiskMetricsResponse,
    RiskBreachResponse,
    RiskContext,
    RiskLimitState
)

from trading.market_making.spread_manager import (
    SpreadManager,
    SpreadStrategy,
    SpreadAdjustmentType,
    SpreadRequest,
    SpreadResponse,
    SpreadAnalyticsResponse,
    SpreadContext,
    SpreadResult,
    SpreadLimit
)

from trading.market_making.strategy import (
    MarketMakingStrategy as StrategyEngine,
    StrategyType,
    QuoteStyle,
    OrderPlacementStyle,
    StrategyRequest,
    StrategyResponse,
    BacktestRequest,
    BacktestResponse,
    StrategyContext,
    QuoteDecision,
    PerformanceMetrics
)

# Module logger
logger = logging.getLogger(__name__)

# =============================================================================
# Module Metadata
# =============================================================================

__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
__description__ = "Advanced Market Making System for NEXUS AI Trading"

# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Base
    'BaseMarketMaker',
    'MarketMakingStrategy',
    'MarketMakingMode',
    'QuoteStatus',
    'InventoryState',
    'OrderPlacementType',
    'MarketMakingState',
    'QuoteParameters',
    'OrderRequest',
    'Quote',
    'OrderResult',
    'InventoryInfo',
    
    # Order Book
    'OrderBookManager',
    'OrderBookLevel',
    'OrderBookState',
    'OrderBookStats',
    'OrderBookLevelData',
    'OrderBookSnapshot',
    'OrderBookUpdate',
    'OrderBookConfig',
    'OrderSide',
    'OrderBookStatus',
    'OrderBookUpdateType',
    
    # Analytics
    'MarketMakingAnalytics',
    'AnalyticsPeriod',
    'MetricType',
    'PerformanceMetric',
    'AnalyticsRequest',
    'AnalyticsResponse',
    'SpreadAnalytics',
    'VolumeAnalytics',
    'LiquidityAnalytics',
    'ProfitabilityAnalytics',
    'InventoryAnalytics',
    'OrderAnalytics',
    'PerformanceAnalytics',
    'AnalyticsContext',
    'AnalyticsResult',
    
    # Hedging
    'HedgingManager',
    'HedgingType',
    'HedgingMode',
    'HedgeStatus',
    'HedgeDirection',
    'HedgeRequest',
    'HedgeResponse',
    'HedgeAnalyticsResponse',
    'HedgePosition',
    'HedgeContext',
    'HedgeResult',
    
    # Inventory
    'InventoryManager',
    'InventoryStrategy',
    'InventoryAction',
    'InventoryRiskLevel',
    'InventoryRequest',
    'InventoryResponse',
    'InventoryAnalyticsResponse',
    'InventoryPosition',
    'InventoryContext',
    'InventoryDecision',
    
    # Market Maker
    'MarketMaker',
    'MarketMakerStatus',
    'QuoteAdjustmentType',
    'MarketMakerRequest',
    'MarketMakerResponse',
    'QuoteRequest',
    'MarketMakerContext',
    'QuoteResult',
    
    # Pricing
    'PricingManager',
    'PricingModel',
    'PriceAdjustmentType',
    'PricingRequest',
    'PricingResponse',
    'PricePredictionResponse',
    'PricingContext',
    'PriceResult',
    'VolatilitySurface',
    
    # Reporter
    'MarketMakingReporter',
    'ReportFormat',
    'ReportType',
    'ChartType',
    'ReportRequest',
    'ReportResponse',
    'ReportSchedule',
    'ReportData',
    'ChartData',
    
    # Risk Manager
    'MarketMakingRiskManager',
    'RiskLimitType',
    'RiskLevel',
    'RiskAction',
    'RiskLimitConfig',
    'RiskMetricsRequest',
    'RiskMetricsResponse',
    'RiskBreachResponse',
    'RiskContext',
    'RiskLimitState',
    
    # Spread Manager
    'SpreadManager',
    'SpreadStrategy',
    'SpreadAdjustmentType',
    'SpreadRequest',
    'SpreadResponse',
    'SpreadAnalyticsResponse',
    'SpreadContext',
    'SpreadResult',
    'SpreadLimit',
    
    # Strategy
    'StrategyEngine',
    'StrategyType',
    'QuoteStyle',
    'OrderPlacementStyle',
    'StrategyRequest',
    'StrategyResponse',
    'BacktestRequest',
    'BacktestResponse',
    'StrategyContext',
    'QuoteDecision',
    'PerformanceMetrics'
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
        'name': 'trading.market_making',
        'version': __version__,
        'author': __author__,
        'description': __description__,
        'components': [
            'BaseMarketMaker',
            'OrderBookManager',
            'MarketMakingAnalytics',
            'HedgingManager',
            'InventoryManager',
            'MarketMaker',
            'PricingManager',
            'MarketMakingReporter',
            'MarketMakingRiskManager',
            'SpreadManager',
            'StrategyEngine'
        ]
    }


def get_component_dependencies() -> Dict[str, List[str]]:
    """
    Get component dependencies.
    
    Returns:
        Dict[str, List[str]]: Component dependencies
    """
    return {
        'BaseMarketMaker': ['OrderRepository', 'TradeRepository', 'PositionRepository'],
        'OrderBookManager': ['BrokerFactory'],
        'MarketMakingAnalytics': ['OrderRepository', 'TradeRepository', 'PositionRepository', 'OrderBookManager'],
        'HedgingManager': ['PositionRepository', 'OrderRepository', 'TradeRepository', 'RiskLimitsManager'],
        'InventoryManager': ['PositionRepository', 'OrderRepository', 'TradeRepository', 'HedgingManager'],
        'MarketMaker': ['OrderRepository', 'TradeRepository', 'PositionRepository', 'OrderBookManager'],
        'PricingManager': ['TradeRepository', 'PositionRepository', 'BrokerFactory'],
        'MarketMakingReporter': ['OrderRepository', 'TradeRepository', 'PositionRepository', 'Analytics'],
        'MarketMakingRiskManager': ['PositionRepository', 'OrderRepository', 'TradeRepository', 'Analytics'],
        'SpreadManager': ['OrderRepository', 'TradeRepository', 'Analytics', 'PricingManager'],
        'StrategyEngine': ['OrderRepository', 'TradeRepository', 'PositionRepository', 'OrderBookManager']
    }


def get_default_config() -> Dict[str, Any]:
    """
    Get default configuration for market making components.
    
    Returns:
        Dict[str, Any]: Default configuration
    """
    return {
        'market_maker': {
            'base_spread': 0.01,
            'min_spread': 0.001,
            'max_spread': 0.05,
            'bid_size': 10.0,
            'ask_size': 10.0,
            'max_position': 100.0,
            'inventory_target': 0.0,
            'order_lifetime': 60,
            'rebalance_threshold': 0.10
        },
        'order_book': {
            'max_depth': 10,
            'update_frequency': 100,
            'max_history': 10000,
            'enable_websocket': True,
            'enable_analytics': True
        },
        'analytics': {
            'default_period': '1d',
            'granularity': '1h',
            'include_charts': True,
            'include_details': True
        },
        'hedging': {
            'default_type': 'delta',
            'hedge_ratio': 1.0,
            'rebalance_frequency': 60,
            'target_delta': 0.0,
            'threshold': 0.05
        },
        'inventory': {
            'default_strategy': 'target',
            'max_inventory': 100.0,
            'min_inventory': -100.0,
            'rebalance_threshold': 0.10,
            'max_daily_turnover': 1000.0
        },
        'pricing': {
            'default_model': 'mid_price',
            'lookback_period': 100,
            'confidence_level': 0.95,
            'include_indicators': True,
            'risk_adjustment': True
        },
        'risk_manager': {
            'max_position': 100.0,
            'max_drawdown': 0.10,
            'max_daily_loss': 1000.0,
            'var_limit': 0.02,
            'leverage_limit': 2.0
        },
        'spread': {
            'default_strategy': 'volatility',
            'min_spread': 0.001,
            'max_spread': 0.05,
            'target_spread': 0.01,
            'adjustment_factor': 1.0
        },
        'strategy': {
            'default_type': 'dynamic',
            'quote_style': 'symmetric',
            'order_style': 'post_only',
            'lookback_period': 100,
            'risk_adjustment': True
        }
    }


def initialize_market_making(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Initialize all market making components.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Dict[str, Any]: Initialized components
    """
    from trading.market_making.analytics import MarketMakingAnalytics
    from trading.market_making.hedging import HedgingManager
    from trading.market_making.inventory_manager import InventoryManager
    from trading.market_making.market_maker import MarketMaker
    from trading.market_making.order_book import OrderBookManager
    from trading.market_making.pricing import PricingManager
    from trading.market_making.reporter import MarketMakingReporter
    from trading.market_making.risk_manager import MarketMakingRiskManager
    from trading.market_making.spread_manager import SpreadManager
    from trading.market_making.strategy import MarketMakingStrategy
    
    config = config or get_default_config()
    
    components = {
        'order_book': OrderBookManager(config.get('order_book', {})),
        'analytics': MarketMakingAnalytics(config.get('analytics', {})),
        'hedging': HedgingManager(config.get('hedging', {})),
        'inventory': InventoryManager(config.get('inventory', {})),
        'market_maker': MarketMaker(config.get('market_maker', {})),
        'pricing': PricingManager(config.get('pricing', {})),
        'reporter': MarketMakingReporter(config.get('reporter', {})),
        'risk_manager': MarketMakingRiskManager(config.get('risk_manager', {})),
        'spread_manager': SpreadManager(config.get('spread', {})),
        'strategy': MarketMakingStrategy(config.get('strategy', {}))
    }
    
    logger.info("Market making components initialized successfully")
    return components


def get_router() -> Any:
    """
    Get FastAPI router for market making endpoints.
    
    Returns:
        Any: FastAPI router
    """
    from fastapi import APIRouter
    
    router = APIRouter(prefix="/api/v1/market-making", tags=["Market Making"])
    
    # Import all routers
    from trading.market_making.analytics import router as analytics_router
    from trading.market_making.hedging import router as hedging_router
    from trading.market_making.inventory_manager import router as inventory_router
    from trading.market_making.market_maker import router as market_maker_router
    from trading.market_making.order_book import router as order_book_router
    from trading.market_making.pricing import router as pricing_router
    from trading.market_making.reporter import router as reporter_router
    from trading.market_making.risk_manager import router as risk_router
    from trading.market_making.spread_manager import router as spread_router
    from trading.market_making.strategy import router as strategy_router
    
    # Include routers
    router.include_router(analytics_router)
    router.include_router(hedging_router)
    router.include_router(inventory_router)
    router.include_router(market_maker_router)
    router.include_router(order_book_router)
    router.include_router(pricing_router)
    router.include_router(reporter_router)
    router.include_router(risk_router)
    router.include_router(spread_router)
    router.include_router(strategy_router)
    
    return router


# =============================================================================
# Module Initialization
# =============================================================================

logger.info(f"Market Making Module v{__version__} loaded successfully")

# Export FastAPI router
market_making_router = get_router()
