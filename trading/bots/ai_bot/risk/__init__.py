"""
NEXUS AI TRADING SYSTEM - Risk Management Package
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Comprehensive risk management package for AI trading bots.
Provides advanced risk analysis, position sizing, stop loss management,
and portfolio risk control.
"""

# Drawdown Controller
from trading.bots.ai_bot.risk.drawdown_controller import (
    DrawdownController,
    DrawdownConfig,
    DrawdownState,
    DrawdownLevel,
    ActionType,
    drawdown_controller,
)

# Position Sizer
from trading.bots.ai_bot.risk.position_sizer import (
    PositionSizer,
    PositionSizingConfig,
    PositionSizeResult,
    Position,
    SizingStrategy,
    position_sizer,
)

# Risk Analyzer
from trading.bots.ai_bot.risk.risk_analyzer import (
    RiskAnalyzer,
    RiskAnalysisConfig,
    RiskMetrics,
    RiskLevel,
    ScenarioType,
    StressTestResult,
    ScenarioResult,
    risk_analyzer,
)

# Risk Calculator
from trading.bots.ai_bot.risk.risk_calculator import (
    RiskCalculator,
    RiskResult,
    RiskContribution,
    VaRMethod,
    RiskMeasure,
    risk_calculator,
)

# Risk Limits
from trading.bots.ai_bot.risk.risk_limits import (
    RiskLimitsManager,
    RiskLimit,
    LimitViolation,
    LimitType,
    LimitSeverity,
    LimitAction,
    risk_limits_manager,
)

# Risk Monitor
from trading.bots.ai_bot.risk.risk_monitor import (
    RiskMonitor,
    RiskEvent,
    RiskEventType,
    RiskEventSeverity,
    RiskEventStatus,
    RiskSummary,
    risk_monitor,
)

# Stop Loss Manager
from trading.bots.ai_bot.risk.stop_loss_manager import (
    StopLossManager,
    StopLoss,
    StopLossConfig,
    StopLossType,
    StopLossStatus,
    StopLossEvent,
    stop_loss_manager,
)

# Take Profit Manager
from trading.bots.ai_bot.risk.take_profit_manager import (
    TakeProfitManager,
    TakeProfit,
    TakeProfitConfig,
    TakeProfitType,
    TakeProfitStatus,
    TakeProfitEvent,
    take_profit_manager,
)

# VaR Calculator
from trading.bots.ai_bot.risk.var_calculator import (
    VaRCalculator,
    VaRResult,
    VaRConfig,
    VaRMethod,
    VaRType,
    var_calculator,
)

__all__ = [
    # Drawdown Controller
    "DrawdownController",
    "DrawdownConfig",
    "DrawdownState",
    "DrawdownLevel",
    "ActionType",
    "drawdown_controller",
    
    # Position Sizer
    "PositionSizer",
    "PositionSizingConfig",
    "PositionSizeResult",
    "Position",
    "SizingStrategy",
    "position_sizer",
    
    # Risk Analyzer
    "RiskAnalyzer",
    "RiskAnalysisConfig",
    "RiskMetrics",
    "RiskLevel",
    "ScenarioType",
    "StressTestResult",
    "ScenarioResult",
    "risk_analyzer",
    
    # Risk Calculator
    "RiskCalculator",
    "RiskResult",
    "RiskContribution",
    "VaRMethod",
    "RiskMeasure",
    "risk_calculator",
    
    # Risk Limits
    "RiskLimitsManager",
    "RiskLimit",
    "LimitViolation",
    "LimitType",
    "LimitSeverity",
    "LimitAction",
    "risk_limits_manager",
    
    # Risk Monitor
    "RiskMonitor",
    "RiskEvent",
    "RiskEventType",
    "RiskEventSeverity",
    "RiskEventStatus",
    "RiskSummary",
    "risk_monitor",
    
    # Stop Loss Manager
    "StopLossManager",
    "StopLoss",
    "StopLossConfig",
    "StopLossType",
    "StopLossStatus",
    "StopLossEvent",
    "stop_loss_manager",
    
    # Take Profit Manager
    "TakeProfitManager",
    "TakeProfit",
    "TakeProfitConfig",
    "TakeProfitType",
    "TakeProfitStatus",
    "TakeProfitEvent",
    "take_profit_manager",
    
    # VaR Calculator
    "VaRCalculator",
    "VaRResult",
    "VaRConfig",
    "VaRMethod",
    "VaRType",
    "var_calculator",
]

__version__ = "3.0.0"
__author__ = "Dr X..."
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"


# Utility functions for risk management

from datetime import datetime
from typing import Any, Dict, Optional


async def get_risk_status() -> Dict[str, Any]:
    """
    Get overall risk management system status.

    Returns:
        Risk status dictionary
    """
    status = {
        "timestamp": datetime.utcnow().isoformat(),
        "components": {},
        "overall": "healthy",
    }

    # Risk Monitor status
    try:
        monitor_status = await risk_monitor.get_risk_summary()
        if monitor_status:
            status["components"]["monitor"] = monitor_status.to_dict()
            if monitor_status.active_events > 0:
                status["overall"] = "degraded" if monitor_status.active_events < 5 else "unhealthy"
    except Exception as e:
        status["components"]["monitor"] = {"status": "unhealthy", "error": str(e)}
        status["overall"] = "unhealthy"

    # Risk Limits status
    try:
        limits_summary = await risk_limits_manager.get_limits_summary()
        status["components"]["limits"] = limits_summary
        if limits_summary.get("active_violations", 0) > 0:
            status["overall"] = "degraded" if limits_summary["active_violations"] < 3 else "unhealthy"
    except Exception as e:
        status["components"]["limits"] = {"status": "unhealthy", "error": str(e)}
        status["overall"] = "unhealthy"

    # Stop Loss status
    try:
        sl_stats = await stop_loss_manager.get_stats()
        status["components"]["stop_loss"] = sl_stats
    except Exception as e:
        status["components"]["stop_loss"] = {"status": "unhealthy", "error": str(e)}
        status["overall"] = "unhealthy"

    # Take Profit status
    try:
        tp_stats = await take_profit_manager.get_stats()
        status["components"]["take_profit"] = tp_stats
    except Exception as e:
        status["components"]["take_profit"] = {"status": "unhealthy", "error": str(e)}
        status["overall"] = "unhealthy"

    # Drawdown status
    try:
        dd_state = await drawdown_controller.get_drawdown_state()
        if dd_state:
            status["components"]["drawdown"] = dd_state.to_dict()
    except Exception as e:
        status["components"]["drawdown"] = {"status": "unhealthy", "error": str(e)}
        status["overall"] = "unhealthy"

    return status


async def initialize_risk_management(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Initialize all risk management components.

    Args:
        config: Configuration dictionary

    Returns:
        Initialization status
    """
    results = {
        "components": {},
        "success": True,
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        # Initialize Drawdown Controller
        if config and "drawdown_controller" in config:
            await drawdown_controller.update_config(config["drawdown_controller"])
        results["components"]["drawdown_controller"] = {"status": "initialized"}

        # Initialize Position Sizer
        if config and "position_sizer" in config:
            await position_sizer.update_config(config["position_sizer"])
        results["components"]["position_sizer"] = {"status": "initialized"}

        # Initialize Risk Analyzer
        if config and "risk_analyzer" in config:
            risk_analyzer.config.update(config["risk_analyzer"])
        results["components"]["risk_analyzer"] = {"status": "initialized"}

        # Initialize Risk Calculator
        if config and "risk_calculator" in config:
            risk_calculator.config.update(config["risk_calculator"])
        results["components"]["risk_calculator"] = {"status": "initialized"}

        # Initialize Risk Limits
        if config and "risk_limits" in config:
            risk_limits_manager.config.update(config["risk_limits"])
        results["components"]["risk_limits"] = {"status": "initialized"}

        # Initialize Risk Monitor
        if config and "risk_monitor" in config:
            risk_monitor.config.update(config["risk_monitor"])
        results["components"]["risk_monitor"] = {"status": "initialized"}

        # Initialize Stop Loss
        if config and "stop_loss" in config:
            stop_loss_manager.config.update(config["stop_loss"])
        results["components"]["stop_loss"] = {"status": "initialized"}

        # Initialize Take Profit
        if config and "take_profit" in config:
            take_profit_manager.config.update(config["take_profit"])
        results["components"]["take_profit"] = {"status": "initialized"}

        # Initialize VaR Calculator
        if config and "var_calculator" in config:
            var_calculator.config.update(config["var_calculator"])
        results["components"]["var_calculator"] = {"status": "initialized"}

        logger.info("All risk management components initialized successfully")

    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        logger.error(f"Error initializing risk management components: {e}")

    return results


async def shutdown_risk_management() -> Dict[str, Any]:
    """
    Shutdown all risk management components.

    Returns:
        Shutdown status
    """
    results = {
        "components": {},
        "success": True,
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        # Shutdown Drawdown Controller
        await drawdown_controller.shutdown()
        results["components"]["drawdown_controller"] = {"status": "shutdown"}

        # Shutdown Risk Analyzer
        await risk_analyzer.shutdown()
        results["components"]["risk_analyzer"] = {"status": "shutdown"}

        # Shutdown Risk Calculator
        await risk_calculator.shutdown()
        results["components"]["risk_calculator"] = {"status": "shutdown"}

        # Shutdown Risk Limits
        await risk_limits_manager.shutdown()
        results["components"]["risk_limits"] = {"status": "shutdown"}

        # Shutdown Risk Monitor
        await risk_monitor.shutdown()
        results["components"]["risk_monitor"] = {"status": "shutdown"}

        # Shutdown Stop Loss
        await stop_loss_manager.shutdown()
        results["components"]["stop_loss"] = {"status": "shutdown"}

        # Shutdown Take Profit
        await take_profit_manager.shutdown()
        results["components"]["take_profit"] = {"status": "shutdown"}

        # Shutdown VaR Calculator
        await var_calculator.shutdown()
        results["components"]["var_calculator"] = {"status": "shutdown"}

        logger.info("All risk management components shutdown successfully")

    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        logger.error(f"Error shutting down risk management components: {e}")

    return results


# Risk management component registry
risk_components = {
    "drawdown_controller": drawdown_controller,
    "position_sizer": position_sizer,
    "risk_analyzer": risk_analyzer,
    "risk_calculator": risk_calculator,
    "risk_limits_manager": risk_limits_manager,
    "risk_monitor": risk_monitor,
    "stop_loss_manager": stop_loss_manager,
    "take_profit_manager": take_profit_manager,
    "var_calculator": var_calculator,
}


# FastAPI integration utilities
def register_risk_routes(app):
    """
    Register risk management routes with a FastAPI app.

    Args:
        app: FastAPI application instance
    """
    from fastapi import FastAPI, Query

    if isinstance(app, FastAPI):
        # Risk status endpoint
        @app.get("/risk/status")
        async def risk_status():
            return await get_risk_status()

        # Risk summary endpoint
        @app.get("/risk/summary")
        async def risk_summary():
            summary = await risk_monitor.get_risk_summary()
            if summary:
                return {
                    "status": "success",
                    "data": summary.to_dict(),
                }
            return {
                "status": "warning",
                "message": "No risk summary available",
            }

        # Risk events endpoint
        @app.get("/risk/events")
        async def risk_events(
            severity: Optional[str] = Query(None, description="Filter by severity"),
            limit: int = Query(100, description="Maximum events"),
        ):
            events = await risk_monitor.get_events(
                severity=severity,
                limit=limit,
            )
            return {
                "status": "success",
                "data": [e.to_dict() for e in events],
                "count": len(events),
            }

        # Risk limits endpoint
        @app.get("/risk/limits")
        async def risk_limits():
            limits = await risk_limits_manager.get_limits()
            return {
                "status": "success",
                "data": [l.to_dict() for l in limits],
                "count": len(limits),
            }

        # Stop losses endpoint
        @app.get("/risk/stop-losses")
        async def stop_losses(
            symbol: Optional[str] = Query(None, description="Filter by symbol"),
        ):
            sls = await stop_loss_manager.get_active_stop_losses(symbol=symbol)
            return {
                "status": "success",
                "data": [sl.to_dict() for sl in sls],
                "count": len(sls),
            }

        # Take profits endpoint
        @app.get("/risk/take-profits")
        async def take_profits(
            symbol: Optional[str] = Query(None, description="Filter by symbol"),
        ):
            tps = await take_profit_manager.get_active_take_profits(symbol=symbol)
            return {
                "status": "success",
                "data": [tp.to_dict() for tp in tps],
                "count": len(tps),
            }

        # Drawdown status endpoint
        @app.get("/risk/drawdown")
        async def drawdown_status(
            portfolio_id: str = Query("default", description="Portfolio ID"),
        ):
            state = await drawdown_controller.get_drawdown_state(portfolio_id)
            if state:
                return {
                    "status": "success",
                    "data": state.to_dict(),
                }
            return {
                "status": "warning",
                "message": f"No drawdown data for portfolio {portfolio_id}",
            }

        logger.info("Risk management routes registered")


# NEXUS placeholder - All risk management components are complete
__all__ += [
    "get_risk_status",
    "initialize_risk_management",
    "shutdown_risk_management",
    "risk_components",
    "register_risk_routes",
]
