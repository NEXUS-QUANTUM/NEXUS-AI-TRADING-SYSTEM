"""
NEXUS AI TRADING SYSTEM - Portfolio Management Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/portfolio/__init__.py
Description: Portfolio Management module initialization and exports
"""

import logging
from typing import Dict, List, Optional, Any, Type

# Import all portfolio components
from trading.portfolio.base import (
    BasePortfolioManager,
    PortfolioStatus,
    PortfolioType,
    PortfolioRiskLevel,
    PortfolioCreateRequest,
    PortfolioResponse,
    PortfolioUpdateRequest,
    PortfolioState,
    PortfolioMetrics,
    PositionInfo
)

from trading.portfolio.allocation import (
    PortfolioAllocation,
    AllocationMethod,
    RiskParityMethod,
    RebalanceFrequency,
    AllocationRequest,
    AllocationResponse,
    OptimizationRequest,
    AllocationContext,
    AllocationResult
)

from trading.portfolio.balance_tracker import (
    BalanceTracker,
    BalanceStatus,
    BalanceMetricType,
    TimeFrame,
    BalanceRequest,
    BalanceResponse,
    BalanceHistoryResponse,
    BalanceAlertRequest,
    BalanceAlertResponse,
    BalanceContext,
    BalanceSnapshot
)

from trading.portfolio.history import (
    PortfolioHistory,
    HistoryPeriod,
    HistoryGranularity,
    ExportFormat,
    HistoryRequest,
    HistoryResponse,
    TradeHistoryResponse,
    PositionHistoryResponse,
    ExportRequest,
    HistoryContext,
    PerformanceSummary
)

from trading.portfolio.performance import (
    PortfolioPerformance,
    PerformanceMetric,
    ComparisonType,
    AttributionType,
    PerformanceRequest,
    PerformanceResponse,
    PerformanceHistoryResponse,
    ComparisonResponse,
    PerformanceContext,
    PerformanceResult,
    AttributionResult
)

from trading.portfolio.pnl_calculator import (
    PnLCalculator,
    PnLType,
    PnLCalculationMethod,
    PnLPeriod,
    PnLRequest,
    PnLResponse,
    PnLAnalyticsResponse,
    PnLContext,
    TradePnL,
    PositionPnL,
    PnLResult
)

from trading.portfolio.portfolio_manager import (
    PortfolioManager,
    PortfolioManagerStatus,
    OrderExecutionStyle,
    PortfolioManagerRequest,
    PortfolioManagerResponse,
    OrderRequest,
    OrderResponse,
    PortfolioManagerContext,
    ExecutionResult
)

from trading.portfolio.position_manager import (
    PositionManager,
    PositionStatus,
    PositionType,
    PositionRiskLevel,
    PositionRequest,
    PositionResponse,
    PositionUpdateRequest,
    PositionCloseRequest,
    PositionBatchRequest,
    PositionContext,
    PositionAnalytics
)

from trading.portfolio.rebalancer import (
    PortfolioRebalancer,
    RebalanceTrigger,
    RebalanceType,
    RebalanceStatus,
    RebalanceRequest,
    RebalanceResponse,
    RebalanceSchedule,
    RebalanceContext,
    RebalanceTrade
)

from trading.portfolio.reporting import (
    PortfolioReporter,
    ReportFormat,
    ReportType,
    ChartType,
    ReportRequest,
    ReportResponse,
    ReportSchedule,
    ReportData,
    ChartData
)

from trading.portfolio.risk_metrics import (
    PortfolioRiskMetrics,
    RiskMetricType,
    RiskLevel,
    RiskMetricsRequest,
    RiskMetricsResponse,
    RiskMetricsHistoryResponse,
    RiskMetricsContext,
    RiskMetricsResult
)

# Module logger
logger = logging.getLogger(__name__)

# =============================================================================
# Module Metadata
# =============================================================================

__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
__description__ = "Advanced Portfolio Management System for NEXUS AI Trading"

# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Base
    'BasePortfolioManager',
    'PortfolioStatus',
    'PortfolioType',
    'PortfolioRiskLevel',
    'PortfolioCreateRequest',
    'PortfolioResponse',
    'PortfolioUpdateRequest',
    'PortfolioState',
    'PortfolioMetrics',
    'PositionInfo',
    
    # Allocation
    'PortfolioAllocation',
    'AllocationMethod',
    'RiskParityMethod',
    'RebalanceFrequency',
    'AllocationRequest',
    'AllocationResponse',
    'OptimizationRequest',
    'AllocationContext',
    'AllocationResult',
    
    # Balance Tracker
    'BalanceTracker',
    'BalanceStatus',
    'BalanceMetricType',
    'TimeFrame',
    'BalanceRequest',
    'BalanceResponse',
    'BalanceHistoryResponse',
    'BalanceAlertRequest',
    'BalanceAlertResponse',
    'BalanceContext',
    'BalanceSnapshot',
    
    # History
    'PortfolioHistory',
    'HistoryPeriod',
    'HistoryGranularity',
    'ExportFormat',
    'HistoryRequest',
    'HistoryResponse',
    'TradeHistoryResponse',
    'PositionHistoryResponse',
    'ExportRequest',
    'HistoryContext',
    'PerformanceSummary',
    
    # Performance
    'PortfolioPerformance',
    'PerformanceMetric',
    'ComparisonType',
    'AttributionType',
    'PerformanceRequest',
    'PerformanceResponse',
    'PerformanceHistoryResponse',
    'ComparisonResponse',
    'PerformanceContext',
    'PerformanceResult',
    'AttributionResult',
    
    # PnL Calculator
    'PnLCalculator',
    'PnLType',
    'PnLCalculationMethod',
    'PnLPeriod',
    'PnLRequest',
    'PnLResponse',
    'PnLAnalyticsResponse',
    'PnLContext',
    'TradePnL',
    'PositionPnL',
    'PnLResult',
    
    # Portfolio Manager
    'PortfolioManager',
    'PortfolioManagerStatus',
    'OrderExecutionStyle',
    'PortfolioManagerRequest',
    'PortfolioManagerResponse',
    'OrderRequest',
    'OrderResponse',
    'PortfolioManagerContext',
    'ExecutionResult',
    
    # Position Manager
    'PositionManager',
    'PositionStatus',
    'PositionType',
    'PositionRiskLevel',
    'PositionRequest',
    'PositionResponse',
    'PositionUpdateRequest',
    'PositionCloseRequest',
    'PositionBatchRequest',
    'PositionContext',
    'PositionAnalytics',
    
    # Rebalancer
    'PortfolioRebalancer',
    'RebalanceTrigger',
    'RebalanceType',
    'RebalanceStatus',
    'RebalanceRequest',
    'RebalanceResponse',
    'RebalanceSchedule',
    'RebalanceContext',
    'RebalanceTrade',
    
    # Reporting
    'PortfolioReporter',
    'ReportFormat',
    'ReportType',
    'ChartType',
    'ReportRequest',
    'ReportResponse',
    'ReportSchedule',
    'ReportData',
    'ChartData',
    
    # Risk Metrics
    'PortfolioRiskMetrics',
    'RiskMetricType',
    'RiskLevel',
    'RiskMetricsRequest',
    'RiskMetricsResponse',
    'RiskMetricsHistoryResponse',
    'RiskMetricsContext',
    'RiskMetricsResult'
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
        'name': 'trading.portfolio',
        'version': __version__,
        'author': __author__,
        'description': __description__,
        'components': [
            'BasePortfolioManager',
            'PortfolioAllocation',
            'BalanceTracker',
            'PortfolioHistory',
            'PortfolioPerformance',
            'PnLCalculator',
            'PortfolioManager',
            'PositionManager',
            'PortfolioRebalancer',
            'PortfolioReporter',
            'PortfolioRiskMetrics'
        ]
    }


def get_component_dependencies() -> Dict[str, List[str]]:
    """
    Get component dependencies.
    
    Returns:
        Dict[str, List[str]]: Component dependencies
    """
    return {
        'BasePortfolioManager': ['PositionRepository', 'OrderRepository', 'TradeRepository', 'PortfolioRepository'],
        'PortfolioAllocation': ['PositionRepository', 'TradeRepository', 'PortfolioRepository'],
        'BalanceTracker': ['PositionRepository', 'TradeRepository', 'PortfolioRepository'],
        'PortfolioHistory': ['PositionRepository', 'TradeRepository', 'PortfolioRepository'],
        'PortfolioPerformance': ['PositionRepository', 'TradeRepository', 'PortfolioRepository'],
        'PnLCalculator': ['PositionRepository', 'TradeRepository', 'PortfolioRepository'],
        'PortfolioManager': ['PositionRepository', 'OrderRepository', 'TradeRepository', 'PortfolioRepository'],
        'PositionManager': ['PositionRepository', 'OrderRepository', 'TradeRepository'],
        'PortfolioRebalancer': ['PositionRepository', 'TradeRepository', 'PortfolioRepository'],
        'PortfolioReporter': ['PositionRepository', 'TradeRepository', 'PortfolioRepository'],
        'PortfolioRiskMetrics': ['PositionRepository', 'TradeRepository', 'PortfolioRepository']
    }


def get_default_config() -> Dict[str, Any]:
    """
    Get default configuration for portfolio components.
    
    Returns:
        Dict[str, Any]: Default configuration
    """
    return {
        'portfolio': {
            'initial_capital': 10000.0,
            'currency': 'USD',
            'risk_per_trade': 0.02,
            'max_drawdown': 0.20,
            'max_position_pct': 0.10,
            'max_leverage': 2.0
        },
        'allocation': {
            'default_method': 'risk_parity',
            'max_weight': 0.40,
            'min_weight': 0.01,
            'lookback_period': 252
        },
        'balance_tracker': {
            'include_unrealized': True,
            'include_margin': True,
            'history_days': 30,
            'alert_cooldown': 300
        },
        'performance': {
            'risk_free_rate': 0.03,
            'confidence_level': 0.95,
            'default_period': '1y'
        },
        'pnl': {
            'default_method': 'mark_to_market',
            'default_period': 'month'
        },
        'position_manager': {
            'max_positions': 50,
            'max_position_size': 1000,
            'min_position_size': 0.01
        },
        'rebalancer': {
            'drift_threshold': 0.05,
            'min_trade_size': 0.01,
            'max_trade_size': 1000.0,
            'tax_aware': False
        },
        'reporter': {
            'default_format': 'pdf',
            'include_charts': True,
            'include_tables': True,
            'include_summary': True
        },
        'risk_metrics': {
            'lookback_period': 252,
            'confidence_level': 0.95,
            'risk_free_rate': 0.03
        }
    }


def initialize_portfolio(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Initialize all portfolio components.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Dict[str, Any]: Initialized components
    """
    from trading.portfolio.allocation import PortfolioAllocation
    from trading.portfolio.balance_tracker import BalanceTracker
    from trading.portfolio.history import PortfolioHistory
    from trading.portfolio.performance import PortfolioPerformance
    from trading.portfolio.pnl_calculator import PnLCalculator
    from trading.portfolio.portfolio_manager import PortfolioManager
    from trading.portfolio.position_manager import PositionManager
    from trading.portfolio.rebalancer import PortfolioRebalancer
    from trading.portfolio.reporting import PortfolioReporter
    from trading.portfolio.risk_metrics import PortfolioRiskMetrics
    
    config = config or get_default_config()
    
    components = {
        'allocation': PortfolioAllocation(config.get('allocation', {})),
        'balance_tracker': BalanceTracker(config.get('balance_tracker', {})),
        'history': PortfolioHistory(config.get('history', {})),
        'performance': PortfolioPerformance(config.get('performance', {})),
        'pnl': PnLCalculator(config.get('pnl', {})),
        'portfolio_manager': PortfolioManager(config.get('portfolio', {})),
        'position_manager': PositionManager(config.get('position_manager', {})),
        'rebalancer': PortfolioRebalancer(config.get('rebalancer', {})),
        'reporter': PortfolioReporter(config.get('reporter', {})),
        'risk_metrics': PortfolioRiskMetrics(config.get('risk_metrics', {}))
    }
    
    logger.info("Portfolio components initialized successfully")
    return components


def get_router() -> Any:
    """
    Get FastAPI router for portfolio endpoints.
    
    Returns:
        Any: FastAPI router
    """
    from fastapi import APIRouter
    
    router = APIRouter(prefix="/api/v1/portfolio", tags=["Portfolio"])
    
    # Import all routers
    from trading.portfolio.allocation import router as allocation_router
    from trading.portfolio.balance_tracker import router as balance_router
    from trading.portfolio.history import router as history_router
    from trading.portfolio.performance import router as performance_router
    from trading.portfolio.pnl_calculator import router as pnl_router
    from trading.portfolio.portfolio_manager import router as portfolio_router
    from trading.portfolio.position_manager import router as position_router
    from trading.portfolio.rebalancer import router as rebalancer_router
    from trading.portfolio.reporting import router as reporting_router
    from trading.portfolio.risk_metrics import router as risk_metrics_router
    
    # Include routers
    router.include_router(allocation_router)
    router.include_router(balance_router)
    router.include_router(history_router)
    router.include_router(performance_router)
    router.include_router(pnl_router)
    router.include_router(portfolio_router)
    router.include_router(position_router)
    router.include_router(rebalancer_router)
    router.include_router(reporting_router)
    router.include_router(risk_metrics_router)
    
    return router


# =============================================================================
# Module Initialization
# =============================================================================

logger.info(f"Portfolio Module v{__version__} loaded successfully")

# Export FastAPI router
portfolio_router = get_router()
