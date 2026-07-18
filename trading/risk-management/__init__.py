"""
NEXUS AI TRADING SYSTEM - Risk Management Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/risk-management/__init__.py
Description: Risk Management module initialization and exports
"""

import logging
from typing import Dict, List, Optional, Any, Type

# Import all risk management components
from trading.risk_management.base import BaseRiskManager
from trading.risk_management.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerState
from trading.risk_management.drawdown_controller import DrawdownController, DrawdownConfig, DrawdownStatus
from trading.risk_management.portfolio_risk import (
    PortfolioRiskManager,
    PortfolioRiskRequest,
    PortfolioRiskResponse,
    RiskLevel,
    RiskStatus,
    RiskMetricType,
    RiskLimitConfig,
    RiskExposure,
    RiskRecommendation
)
from trading.risk_management.position_sizer import (
    PositionSizer,
    PositionSizingRequest,
    PositionSizingResponse,
    SizingMethod,
    RiskTolerance,
    MarketCondition,
    SizingContext,
    SizingResult,
    SizingHistory
)
from trading.risk_management.risk_limits import (
    RiskLimitsManager,
    LimitType,
    LimitSeverity,
    LimitAction,
    LimitScope,
    RiskLimitConfig as RiskLimitConfigModel,
    RiskLimitBreachRequest,
    RiskLimitStatusResponse,
    RiskLimitsSummaryResponse,
    LimitBreachHistory,
    LimitValidationResult
)
from trading.risk_management.risk_monitor import (
    RiskMonitor,
    MonitorStatus,
    AlertSeverity,
    AlertCategory,
    RiskEventType,
    RiskMonitorConfig,
    RiskAlertCreate,
    RiskAlertResponse,
    RiskMonitorStatusResponse,
    RiskMonitorSummaryResponse,
    MonitorCheck,
    RiskSnapshot,
    PerformanceMetric
)
from trading.risk_management.risk_reporter import (
    RiskReporter,
    ReportRequest,
    ReportResponse,
    ReportSchedule,
    ReportFormat,
    ReportType,
    ReportFrequency,
    ChartType,
    ReportData,
    ChartData
)
from trading.risk_management.stop_loss import (
    StopLossManager,
    StopLossType,
    StopLossStatus,
    StopLossTrigger,
    StopLossRequest,
    StopLossResponse,
    StopLossHistoryResponse,
    BatchStopLossRequest,
    StopLossAnalyticsResponse,
    StopLossContext,
    StopLossResult,
    TrailingStopState
)
from trading.risk_management.stress_tester import (
    StressTester,
    StressScenarioType,
    StressTestStatus,
    StressSeverity,
    StressTestRequest,
    StressTestResponse,
    HistoricalScenario,
    ScenarioDefinition,
    StressTestContext,
    ScenarioResult,
    MonteCarloResult
)
from trading.risk_management.take_profit import (
    TakeProfitManager,
    TakeProfitType,
    TakeProfitStatus,
    TakeProfitTrigger,
    TakeProfitRequest,
    TakeProfitResponse,
    TakeProfitHistoryResponse,
    BatchTakeProfitRequest,
    TakeProfitAnalyticsResponse,
    TakeProfitContext,
    TakeProfitResult,
    TrailingTPState
)
from trading.risk_management.var_calculator import (
    VaRCalculator,
    VarMethod,
    DistributionType,
    ConfidenceLevel,
    TimeHorizon,
    VarRequest,
    VarResponse,
    VaRAnalyticsResponse,
    VarContext,
    VarDecomposition,
    DistributionFit
)

# Module logger
logger = logging.getLogger(__name__)

# =============================================================================
# Module Metadata
# =============================================================================

__version__ = "1.0.0"
__author__ = "NEXUS QUANTUM LTD"
__description__ = "Advanced Risk Management System for NEXUS AI Trading"

# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Base
    'BaseRiskManager',
    
    # Circuit Breaker
    'CircuitBreaker',
    'CircuitBreakerConfig',
    'CircuitBreakerState',
    
    # Drawdown Controller
    'DrawdownController',
    'DrawdownConfig',
    'DrawdownStatus',
    
    # Portfolio Risk
    'PortfolioRiskManager',
    'PortfolioRiskRequest',
    'PortfolioRiskResponse',
    'RiskLevel',
    'RiskStatus',
    'RiskMetricType',
    'RiskLimitConfig',
    'RiskExposure',
    'RiskRecommendation',
    
    # Position Sizer
    'PositionSizer',
    'PositionSizingRequest',
    'PositionSizingResponse',
    'SizingMethod',
    'RiskTolerance',
    'MarketCondition',
    'SizingContext',
    'SizingResult',
    'SizingHistory',
    
    # Risk Limits
    'RiskLimitsManager',
    'LimitType',
    'LimitSeverity',
    'LimitAction',
    'LimitScope',
    'RiskLimitConfigModel',
    'RiskLimitBreachRequest',
    'RiskLimitStatusResponse',
    'RiskLimitsSummaryResponse',
    'LimitBreachHistory',
    'LimitValidationResult',
    
    # Risk Monitor
    'RiskMonitor',
    'MonitorStatus',
    'AlertSeverity',
    'AlertCategory',
    'RiskEventType',
    'RiskMonitorConfig',
    'RiskAlertCreate',
    'RiskAlertResponse',
    'RiskMonitorStatusResponse',
    'RiskMonitorSummaryResponse',
    'MonitorCheck',
    'RiskSnapshot',
    'PerformanceMetric',
    
    # Risk Reporter
    'RiskReporter',
    'ReportRequest',
    'ReportResponse',
    'ReportSchedule',
    'ReportFormat',
    'ReportType',
    'ReportFrequency',
    'ChartType',
    'ReportData',
    'ChartData',
    
    # Stop Loss
    'StopLossManager',
    'StopLossType',
    'StopLossStatus',
    'StopLossTrigger',
    'StopLossRequest',
    'StopLossResponse',
    'StopLossHistoryResponse',
    'BatchStopLossRequest',
    'StopLossAnalyticsResponse',
    'StopLossContext',
    'StopLossResult',
    'TrailingStopState',
    
    # Stress Tester
    'StressTester',
    'StressScenarioType',
    'StressTestStatus',
    'StressSeverity',
    'StressTestRequest',
    'StressTestResponse',
    'HistoricalScenario',
    'ScenarioDefinition',
    'StressTestContext',
    'ScenarioResult',
    'MonteCarloResult',
    
    # Take Profit
    'TakeProfitManager',
    'TakeProfitType',
    'TakeProfitStatus',
    'TakeProfitTrigger',
    'TakeProfitRequest',
    'TakeProfitResponse',
    'TakeProfitHistoryResponse',
    'BatchTakeProfitRequest',
    'TakeProfitAnalyticsResponse',
    'TakeProfitContext',
    'TakeProfitResult',
    'TrailingTPState',
    
    # VaR Calculator
    'VaRCalculator',
    'VarMethod',
    'DistributionType',
    'ConfidenceLevel',
    'TimeHorizon',
    'VarRequest',
    'VarResponse',
    'VaRAnalyticsResponse',
    'VarContext',
    'VarDecomposition',
    'DistributionFit'
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
        'name': 'trading.risk_management',
        'version': __version__,
        'author': __author__,
        'description': __description__,
        'components': [
            'BaseRiskManager',
            'CircuitBreaker',
            'DrawdownController',
            'PortfolioRiskManager',
            'PositionSizer',
            'RiskLimitsManager',
            'RiskMonitor',
            'RiskReporter',
            'StopLossManager',
            'StressTester',
            'TakeProfitManager',
            'VaRCalculator'
        ]
    }


def get_component_dependencies() -> Dict[str, List[str]]:
    """
    Get component dependencies.
    
    Returns:
        Dict[str, List[str]]: Component dependencies
    """
    return {
        'PortfolioRiskManager': ['PositionRepository', 'TradeRepository', 'PortfolioRepository'],
        'PositionSizer': ['PositionRepository', 'TradeRepository', 'PortfolioRepository', 'RiskManager'],
        'RiskLimitsManager': ['RiskRepository', 'PositionRepository', 'TradeRepository', 'PortfolioRepository'],
        'RiskMonitor': ['RiskRepository', 'PositionRepository', 'TradeRepository', 'PortfolioRepository'],
        'RiskReporter': ['PositionRepository', 'TradeRepository', 'PortfolioRepository', 'RiskRepository'],
        'StopLossManager': ['PositionRepository', 'TradeRepository', 'PortfolioRepository'],
        'StressTester': ['PositionRepository', 'TradeRepository', 'PortfolioRepository', 'RiskRepository'],
        'TakeProfitManager': ['PositionRepository', 'TradeRepository', 'PortfolioRepository'],
        'VaRCalculator': ['PositionRepository', 'TradeRepository', 'PortfolioRepository']
    }


def get_default_config() -> Dict[str, Any]:
    """
    Get default configuration for risk management components.
    
    Returns:
        Dict[str, Any]: Default configuration
    """
    return {
        'circuit_breaker': {
            'failure_threshold': 5,
            'timeout_seconds': 60,
            'half_open_max_calls': 3,
            'success_threshold': 2
        },
        'drawdown_controller': {
            'max_drawdown': 0.20,
            'warning_threshold': 0.15,
            'stop_trading_threshold': 0.25,
            'recovery_threshold': 0.10
        },
        'position_sizer': {
            'default_method': 'risk_based',
            'risk_per_trade': 0.02,
            'max_position_pct': 0.10,
            'min_position_pct': 0.001
        },
        'risk_limits': {
            'max_portfolio_risk': 0.05,
            'max_drawdown': 0.20,
            'max_concentration': 0.40,
            'max_position_size': 0.10,
            'max_leverage': 2.0,
            'max_daily_loss': 1000,
            'max_weekly_loss': 3000
        },
        'risk_monitor': {
            'check_interval_seconds': 5,
            'alert_cooldown_seconds': 60,
            'max_alerts_per_minute': 10,
            'enable_websocket': True,
            'enable_dashboard': True
        },
        'stop_loss': {
            'default_type': 'percentage',
            'default_percentage': 0.02,
            'max_stop_distance': 0.10,
            'min_stop_distance': 0.005,
            'trailing_activation': 0.02
        },
        'take_profit': {
            'default_type': 'risk_reward',
            'default_risk_reward': 2.0,
            'max_tp_distance': 0.50,
            'min_tp_distance': 0.01
        },
        'var_calculator': {
            'default_method': 'historical',
            'default_confidence': 0.95,
            'default_lookback': 252,
            'default_horizon': '1d',
            'monte_carlo_simulations': 10000
        }
    }


def initialize_risk_management(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Initialize all risk management components.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        Dict[str, Any]: Initialized components
    """
    from trading.risk_management.portfolio_risk import PortfolioRiskManager
    from trading.risk_management.position_sizer import PositionSizer
    from trading.risk_management.risk_limits import RiskLimitsManager
    from trading.risk_management.risk_monitor import RiskMonitor
    from trading.risk_management.risk_reporter import RiskReporter
    from trading.risk_management.stop_loss import StopLossManager
    from trading.risk_management.stress_tester import StressTester
    from trading.risk_management.take_profit import TakeProfitManager
    from trading.risk_management.var_calculator import VaRCalculator
    
    config = config or get_default_config()
    
    components = {
        'portfolio_risk': PortfolioRiskManager(config.get('portfolio_risk', {})),
        'position_sizer': PositionSizer(config.get('position_sizer', {})),
        'risk_limits': RiskLimitsManager(config.get('risk_limits', {})),
        'risk_monitor': RiskMonitor(config.get('risk_monitor', {})),
        'risk_reporter': RiskReporter(config.get('risk_reporter', {})),
        'stop_loss': StopLossManager(config.get('stop_loss', {})),
        'stress_tester': StressTester(config.get('stress_tester', {})),
        'take_profit': TakeProfitManager(config.get('take_profit', {})),
        'var_calculator': VaRCalculator(config.get('var_calculator', {}))
    }
    
    logger.info("Risk management components initialized successfully")
    return components


def get_router() -> Any:
    """
    Get FastAPI router for risk management endpoints.
    
    Returns:
        Any: FastAPI router
    """
    from fastapi import APIRouter
    
    router = APIRouter(prefix="/api/v1/risk", tags=["Risk Management"])
    
    # Import all routers
    from trading.risk_management.portfolio_risk import router as portfolio_risk_router
    from trading.risk_management.position_sizer import router as position_sizer_router
    from trading.risk_management.risk_limits import router as risk_limits_router
    from trading.risk_management.risk_monitor import router as risk_monitor_router
    from trading.risk_management.risk_reporter import router as risk_reporter_router
    from trading.risk_management.stop_loss import router as stop_loss_router
    from trading.risk_management.stress_tester import router as stress_tester_router
    from trading.risk_management.take_profit import router as take_profit_router
    from trading.risk_management.var_calculator import router as var_calculator_router
    
    # Include routers
    router.include_router(portfolio_risk_router)
    router.include_router(position_sizer_router)
    router.include_router(risk_limits_router)
    router.include_router(risk_monitor_router)
    router.include_router(risk_reporter_router)
    router.include_router(stop_loss_router)
    router.include_router(stress_tester_router)
    router.include_router(take_profit_router)
    router.include_router(var_calculator_router)
    
    return router


# =============================================================================
# Module Initialization
# =============================================================================

logger.info(f"Risk Management Module v{__version__} loaded successfully")

# Export FastAPI router
risk_router = get_router()
