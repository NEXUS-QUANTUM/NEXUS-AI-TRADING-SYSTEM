"""
NEXUS AI TRADING SYSTEM - Performance Package
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Comprehensive performance package for AI trading bots.
Provides advanced performance analysis, optimization, reporting, and tracking.
"""

# Performance Analyzer
from trading.bots.ai_bot.performance.performance_analyzer import (
    PerformanceAnalyzer,
    PerformancePoint,
    PerformanceReport,
    PerformanceMetric,
    AnalysisType,
    performance_analyzer,
)

# Performance Metrics
from trading.bots.ai_bot.performance.performance_metrics import (
    PerformanceMetrics,
    PerformanceMetricsCalculator,
    PerformanceVisualizer,
    rolling_sharpe_ratio,
)

# Performance Optimizer
from trading.bots.ai_bot.performance.performance_optimizer import (
    PerformanceOptimizer,
    OptimizationConfig,
    OptimizationResult,
    ParameterSpace,
    OptimizerType,
    OptimizationObjective,
    performance_optimizer,
)

# Performance Report
from trading.bots.ai_bot.performance.performance_report import (
    PerformanceReportGenerator,
    ReportConfig,
    ReportData,
    ReportType,
    ReportFormat,
    performance_report_generator,
)

# Performance Tracker
from trading.bots.ai_bot.performance.performance_tracker import (
    PerformanceTracker,
    PerformanceEntry,
    AggregatedData,
    TrackerConfig,
    TrackerType,
    AggregationWindow,
    performance_tracker,
)

__all__ = [
    # Performance Analyzer
    "PerformanceAnalyzer",
    "PerformancePoint",
    "PerformanceReport",
    "PerformanceMetric",
    "AnalysisType",
    "performance_analyzer",
    
    # Performance Metrics
    "PerformanceMetrics",
    "PerformanceMetricsCalculator",
    "PerformanceVisualizer",
    "rolling_sharpe_ratio",
    
    # Performance Optimizer
    "PerformanceOptimizer",
    "OptimizationConfig",
    "OptimizationResult",
    "ParameterSpace",
    "OptimizerType",
    "OptimizationObjective",
    "performance_optimizer",
    
    # Performance Report
    "PerformanceReportGenerator",
    "ReportConfig",
    "ReportData",
    "ReportType",
    "ReportFormat",
    "performance_report_generator",
    
    # Performance Tracker
    "PerformanceTracker",
    "PerformanceEntry",
    "AggregatedData",
    "TrackerConfig",
    "TrackerType",
    "AggregationWindow",
    "performance_tracker",
]

__version__ = "3.0.0"
__author__ = "Dr X..."
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"


# Utility functions for performance management

async def get_performance_status() -> Dict[str, Any]:
    """
    Get overall performance system status.

    Returns:
        Performance status dictionary
    """
    status = {
        "timestamp": datetime.utcnow().isoformat(),
        "components": {},
        "overall": "healthy",
    }

    # Performance Tracker status
    try:
        tracker_stats = await performance_tracker.get_tracker_stats()
        status["components"]["tracker"] = tracker_stats
        if tracker_stats.get("buffer_size", 0) > 5000:
            status["overall"] = "degraded"
    except Exception as e:
        status["components"]["tracker"] = {"status": "unhealthy", "error": str(e)}
        status["overall"] = "unhealthy"

    # Performance Optimizer status
    try:
        results = await performance_optimizer.get_results(limit=1)
        status["components"]["optimizer"] = {
            "status": "healthy",
            "last_optimization": results[0].created_at.isoformat() if results else None,
        }
    except Exception as e:
        status["components"]["optimizer"] = {"status": "unhealthy", "error": str(e)}
        status["overall"] = "unhealthy"

    # Performance Report Generator status
    try:
        configs = await performance_report_generator.get_report_configs()
        status["components"]["report_generator"] = {
            "status": "healthy",
            "configs": len(configs),
        }
    except Exception as e:
        status["components"]["report_generator"] = {"status": "unhealthy", "error": str(e)}
        status["overall"] = "unhealthy"

    return status


async def initialize_performance(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Initialize all performance components.

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
        # Initialize Performance Tracker
        if config and "performance_tracker" in config:
            performance_tracker.config.update(config["performance_tracker"])
        results["components"]["tracker"] = {"status": "initialized"}

        # Initialize Performance Analyzer
        if config and "performance_analyzer" in config:
            performance_analyzer.config.update(config["performance_analyzer"])
        results["components"]["analyzer"] = {"status": "initialized"}

        # Initialize Performance Optimizer
        if config and "performance_optimizer" in config:
            performance_optimizer.config.update(config["performance_optimizer"])
        results["components"]["optimizer"] = {"status": "initialized"}

        # Initialize Performance Report Generator
        if config and "performance_report" in config:
            performance_report_generator.config.update(config["performance_report"])
        results["components"]["report_generator"] = {"status": "initialized"}

        logger.info("All performance components initialized successfully")

    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        logger.error(f"Error initializing performance components: {e}")

    return results


async def shutdown_performance() -> Dict[str, Any]:
    """
    Shutdown all performance components.

    Returns:
        Shutdown status
    """
    results = {
        "components": {},
        "success": True,
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        # Shutdown Performance Tracker
        await performance_tracker.shutdown()
        results["components"]["tracker"] = {"status": "shutdown"}

        # Shutdown Performance Analyzer
        await performance_analyzer.shutdown()
        results["components"]["analyzer"] = {"status": "shutdown"}

        # Shutdown Performance Optimizer
        await performance_optimizer.shutdown()
        results["components"]["optimizer"] = {"status": "shutdown"}

        # Shutdown Performance Report Generator
        await performance_report_generator.shutdown()
        results["components"]["report_generator"] = {"status": "shutdown"}

        logger.info("All performance components shutdown successfully")

    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        logger.error(f"Error shutting down performance components: {e}")

    return results


# Performance component registry
performance_components = {
    "tracker": performance_tracker,
    "analyzer": performance_analyzer,
    "optimizer": performance_optimizer,
    "report_generator": performance_report_generator,
}


# FastAPI integration utilities
def register_performance_routes(app):
    """
    Register performance routes with a FastAPI app.

    Args:
        app: FastAPI application instance
    """
    from fastapi import FastAPI, Query

    if isinstance(app, FastAPI):
        # Performance status endpoint
        @app.get("/performance/status")
        async def performance_status():
            return await get_performance_status()

        # Performance tracker endpoints
        @app.get("/performance/tracker/metrics")
        async def get_tracker_metrics(
            component: str = Query(..., description="Component name"),
            metric: Optional[str] = Query(None, description="Metric name"),
            since: Optional[datetime] = Query(None, description="Time since"),
            limit: int = Query(1000, description="Maximum entries"),
        ):
            if since:
                entries = await performance_tracker.get_entries(
                    component=component,
                    metric_name=metric,
                    start_time=since,
                    limit=limit,
                )
            else:
                entries = await performance_tracker.get_entries(
                    component=component,
                    metric_name=metric,
                    limit=limit,
                )
            return {
                "status": "success",
                "data": [e.to_dict() for e in entries],
                "count": len(entries),
            }

        # Performance analyzer endpoints
        @app.get("/performance/analyzer/report")
        async def get_analyzer_report(
            component: str = Query(..., description="Component name"),
        ):
            report = await performance_analyzer.get_latest_report(component)
            if report:
                return {
                    "status": "success",
                    "data": report.to_dict(),
                }
            return {
                "status": "warning",
                "message": f"No report found for component: {component}",
            }

        # Performance optimizer endpoints
        @app.get("/performance/optimizer/results")
        async def get_optimizer_results(
            limit: int = Query(10, description="Maximum results"),
        ):
            results = await performance_optimizer.get_results(limit=limit)
            return {
                "status": "success",
                "data": [r.to_dict() for r in results],
                "count": len(results),
            }

        # Performance report endpoints
        @app.get("/performance/report/configs")
        async def get_report_configs():
            configs = await performance_report_generator.get_report_configs()
            return {
                "status": "success",
                "data": configs,
                "count": len(configs),
            }

        @app.post("/performance/report/generate")
        async def generate_report(
            config_name: str = Query(..., description="Report configuration name"),
        ):
            try:
                results = await performance_report_generator.generate_report(config_name)
                return {
                    "status": "success",
                    "data": results,
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": str(e),
                }

        logger.info("Performance routes registered")


# NEXUS placeholder - All performance components are complete
__all__ += [
    "get_performance_status",
    "initialize_performance",
    "shutdown_performance",
    "performance_components",
    "register_performance_routes",
]
