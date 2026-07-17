"""
NEXUS AI TRADING SYSTEM - Monitoring Package
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Comprehensive monitoring package for AI trading bots.
Provides advanced monitoring, alerting, logging, and incident management.
"""

# Alert Manager
from trading.bots.ai_bot.monitoring.alert_manager import (
    AlertManager,
    Alert,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    AlertCategory,
    ChannelType,
    NotificationConfig,
    alert_manager,
)

# Dashboard API
from trading.bots.ai_bot.monitoring.dashboard_api import (
    DashboardAPI,
    router as dashboard_router,
)

# Health Checker
from trading.bots.ai_bot.monitoring.health_checker import (
    HealthChecker,
    HealthCheckResult,
    HealthStatus,
    ComponentType,
    health_checker,
)

# Incident Manager
from trading.bots.ai_bot.monitoring.incident_manager import (
    IncidentManager,
    Incident,
    IncidentReport,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
    SLAConfig,
    incident_manager,
)

# Log Analyzer
from trading.bots.ai_bot.monitoring.log_analyzer import (
    LogAnalyzer,
    LogEntry,
    LogPattern,
    LogLevel,
    AnalysisType,
    AnalysisResult,
    log_analyzer,
)

# Metric Collector
from trading.bots.ai_bot.monitoring.metric_collector import (
    MetricCollector,
    MetricDefinition,
    MetricPoint,
    MetricSeries,
    MetricType,
    AggregationType,
    metric_collector,
)

# Notification Service
from trading.bots.ai_bot.monitoring.notification_service import (
    NotificationService,
    Notification,
    NotificationTemplate,
    NotificationPriority,
    NotificationChannel,
    ChannelConfig,
    notification_service,
)

__all__ = [
    # Alert Manager
    "AlertManager",
    "Alert",
    "AlertRule",
    "AlertSeverity",
    "AlertStatus",
    "AlertCategory",
    "ChannelType",
    "NotificationConfig",
    "alert_manager",
    # Dashboard API
    "DashboardAPI",
    "dashboard_router",
    # Health Checker
    "HealthChecker",
    "HealthCheckResult",
    "HealthStatus",
    "ComponentType",
    "health_checker",
    # Incident Manager
    "IncidentManager",
    "Incident",
    "IncidentReport",
    "IncidentSeverity",
    "IncidentStatus",
    "IncidentType",
    "SLAConfig",
    "incident_manager",
    # Log Analyzer
    "LogAnalyzer",
    "LogEntry",
    "LogPattern",
    "LogLevel",
    "AnalysisType",
    "AnalysisResult",
    "log_analyzer",
    # Metric Collector
    "MetricCollector",
    "MetricDefinition",
    "MetricPoint",
    "MetricSeries",
    "MetricType",
    "AggregationType",
    "metric_collector",
    # Notification Service
    "NotificationService",
    "Notification",
    "NotificationTemplate",
    "NotificationPriority",
    "NotificationChannel",
    "ChannelConfig",
    "notification_service",
]

__version__ = "3.0.0"
__author__ = "Dr X..."
__copyright__ = "Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved"


# Utility functions for monitoring

async def get_monitoring_status() -> Dict[str, Any]:
    """
    Get overall monitoring system status.

    Returns:
        Monitoring status dictionary
    """
    status = {
        "timestamp": datetime.utcnow().isoformat(),
        "components": {},
        "overall": "healthy",
    }

    # Health Checker status
    try:
        health_status = await health_checker.get_status()
        status["components"]["health_checker"] = health_status
        if health_status.get("overall") != "healthy":
            status["overall"] = "degraded"
    except Exception as e:
        status["components"]["health_checker"] = {"status": "unhealthy", "error": str(e)}
        status["overall"] = "unhealthy"

    # Alert Manager status
    try:
        alert_stats = await alert_manager.get_alert_stats()
        status["components"]["alert_manager"] = alert_stats
        if alert_stats.get("active_alerts", 0) > 0:
            status["overall"] = "degraded" if status["overall"] == "healthy" else "unhealthy"
    except Exception as e:
        status["components"]["alert_manager"] = {"status": "unhealthy", "error": str(e)}
        status["overall"] = "unhealthy"

    # Incident Manager status
    try:
        incident_stats = await incident_manager.get_incident_stats()
        status["components"]["incident_manager"] = incident_stats
        if incident_stats.get("active_incidents", 0) > 0:
            status["overall"] = "degraded" if status["overall"] == "healthy" else "unhealthy"
    except Exception as e:
        status["components"]["incident_manager"] = {"status": "unhealthy", "error": str(e)}
        status["overall"] = "unhealthy"

    # Metric Collector status
    try:
        metric_count = len(metric_collector._metrics)
        status["components"]["metric_collector"] = {
            "status": "healthy",
            "metrics_count": metric_count,
            "buffer_size": len(metric_collector._buffer),
        }
    except Exception as e:
        status["components"]["metric_collector"] = {"status": "unhealthy", "error": str(e)}
        status["overall"] = "unhealthy"

    # Notification Service status
    try:
        queue_status = await notification_service.get_queue_status()
        status["components"]["notification_service"] = queue_status
        if queue_status.get("failed", 0) > 0:
            status["overall"] = "degraded" if status["overall"] == "healthy" else "unhealthy"
    except Exception as e:
        status["components"]["notification_service"] = {"status": "unhealthy", "error": str(e)}
        status["overall"] = "unhealthy"

    # Log Analyzer status
    try:
        pattern_count = len(log_analyzer._patterns)
        buffer_size = len(log_analyzer._log_buffer)
        status["components"]["log_analyzer"] = {
            "status": "healthy",
            "patterns": pattern_count,
            "buffer_size": buffer_size,
        }
    except Exception as e:
        status["components"]["log_analyzer"] = {"status": "unhealthy", "error": str(e)}
        status["overall"] = "unhealthy"

    return status


async def initialize_monitoring(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Initialize all monitoring components.

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
        # Initialize Alert Manager
        if config and "alert_manager" in config:
            alert_manager.config.update(config["alert_manager"])
        await alert_manager._load_rules()
        results["components"]["alert_manager"] = {"status": "initialized"}

        # Initialize Health Checker
        if config and "health_checker" in config:
            health_checker.config.update(config["health_checker"])
        results["components"]["health_checker"] = {"status": "initialized"}

        # Initialize Incident Manager
        if config and "incident_manager" in config:
            incident_manager.config.update(config["incident_manager"])
        results["components"]["incident_manager"] = {"status": "initialized"}

        # Initialize Metric Collector
        if config and "metric_collector" in config:
            metric_collector.config.update(config["metric_collector"])
        results["components"]["metric_collector"] = {"status": "initialized"}

        # Initialize Notification Service
        if config and "notification_service" in config:
            notification_service.config.update(config["notification_service"])
        results["components"]["notification_service"] = {"status": "initialized"}

        # Initialize Log Analyzer
        if config and "log_analyzer" in config:
            log_analyzer.config.update(config["log_analyzer"])
        results["components"]["log_analyzer"] = {"status": "initialized"}

        logger.info("All monitoring components initialized successfully")

    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        logger.error(f"Error initializing monitoring components: {e}")

    return results


async def shutdown_monitoring() -> Dict[str, Any]:
    """
    Shutdown all monitoring components.

    Returns:
        Shutdown status
    """
    results = {
        "components": {},
        "success": True,
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        # Shutdown Alert Manager
        await alert_manager.shutdown()
        results["components"]["alert_manager"] = {"status": "shutdown"}

        # Shutdown Health Checker
        await health_checker.shutdown()
        results["components"]["health_checker"] = {"status": "shutdown"}

        # Shutdown Incident Manager
        await incident_manager.shutdown()
        results["components"]["incident_manager"] = {"status": "shutdown"}

        # Shutdown Metric Collector
        await metric_collector.shutdown()
        results["components"]["metric_collector"] = {"status": "shutdown"}

        # Shutdown Notification Service
        await notification_service.shutdown()
        results["components"]["notification_service"] = {"status": "shutdown"}

        # Shutdown Log Analyzer
        await log_analyzer.shutdown()
        results["components"]["log_analyzer"] = {"status": "shutdown"}

        logger.info("All monitoring components shutdown successfully")

    except Exception as e:
        results["success"] = False
        results["error"] = str(e)
        logger.error(f"Error shutting down monitoring components: {e}")

    return results


# Register default monitoring routes for FastAPI
def register_monitoring_routes(app):
    """
    Register monitoring routes with a FastAPI app.

    Args:
        app: FastAPI application instance
    """
    from fastapi import FastAPI

    if isinstance(app, FastAPI):
        app.include_router(dashboard_router)

        # Health check endpoint
        @app.get("/health")
        async def health_check():
            return await health_checker.get_status()

        # Metrics endpoint
        @app.get("/metrics")
        async def get_metrics():
            from prometheus_client import generate_latest
            return Response(generate_latest(), media_type="text/plain")

        # Monitoring status endpoint
        @app.get("/monitoring/status")
        async def monitoring_status():
            return await get_monitoring_status()

        logger.info("Monitoring routes registered")


# Export monitoring components with default configurations
monitoring_components = {
    "alert_manager": alert_manager,
    "health_checker": health_checker,
    "incident_manager": incident_manager,
    "metric_collector": metric_collector,
    "notification_service": notification_service,
    "log_analyzer": log_analyzer,
}


# NEXUS placeholder - All monitoring components are complete
__all__ += [
    "get_monitoring_status",
    "initialize_monitoring",
    "shutdown_monitoring",
    "register_monitoring_routes",
    "monitoring_components",
]
