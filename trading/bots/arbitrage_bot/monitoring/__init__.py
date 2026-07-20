# trading/bots/arbitrage_bot/monitoring/__init__.py
# NEXUS AI TRADING SYSTEM - MONITORING PACKAGE
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This package provides comprehensive monitoring capabilities for the arbitrage bot,
# including alerting, metrics collection, health checking, incident management,
# and performance monitoring.
# ====================================================================================

"""
NEXUS Arbitrage Bot Monitoring Package

This package provides comprehensive monitoring for:
- Alert management and notification
- Incident tracking and resolution
- Health checking and status monitoring
- Performance monitoring and optimization
- Metric collection and analysis
- Log analysis and pattern detection
- Report generation and delivery
- Dashboard API for visualization
- Real-time monitoring and alerting
- SLA tracking and compliance
- Root cause analysis
- Performance optimization recommendations
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Set, Tuple

# ====================================================================================
# ALERT MANAGER
# ====================================================================================

from .alert_manager import (
    AlertManager,
    NotificationStatus,
    EscalationStatus,
    EmailConfig,
    SlackConfig,
    TelegramConfig,
    DiscordConfig,
    PagerDutyConfig,
    WebhookConfig,
    NotificationProvider,
    EmailProvider,
    SlackProvider,
    TelegramProvider,
    DiscordProvider,
    PagerDutyProvider,
    WebhookProvider,
    get_alert_manager,
    reset_alert_manager,
)

# ====================================================================================
# DASHBOARD API
# ====================================================================================

from .dashboard_api import (
    DashboardAPI,
    get_dashboard_api,
)

# ====================================================================================
# HEALTH CHECKER
# ====================================================================================

from .health_checker import (
    HealthChecker,
    HealthStatus,
    ComponentType,
    CheckSeverity,
    HealthCheckConfig,
    HealthCheckResult,
    ComponentHealth,
    SystemHealth,
    create_exchange_health_check,
    create_service_health_check,
    create_database_health_check,
    create_websocket_health_check,
    get_health_checker,
    reset_health_checker,
)

# ====================================================================================
# INCIDENT MANAGER
# ====================================================================================

from .incident_manager import (
    IncidentManager,
    IncidentSeverity,
    IncidentStatus,
    IncidentCategory,
    IncidentPriority,
    ResolutionStatus,
    Incident,
    IncidentTimeline,
    IncidentMetrics,
    IncidentReport,
    get_incident_manager,
    reset_incident_manager,
)

# ====================================================================================
# LOG ANALYZER
# ====================================================================================

from .log_analyzer import (
    LogAnalyzer,
    LogLevel,
    LogPatternType,
    LogAnalysisPeriod,
    LogEntry,
    LogPattern,
    LogAnomaly,
    LogAnalysisResult,
    get_log_analyzer,
    reset_log_analyzer,
)

# ====================================================================================
# METRIC COLLECTOR
# ====================================================================================

from .metric_collector import (
    MetricCollector,
    MetricType,
    MetricCategory,
    AggregationMethod,
    Metric,
    MetricAggregation,
    MetricQuery,
    get_metric_collector,
    reset_metric_collector,
)

# ====================================================================================
# NOTIFICATION SERVICE
# ====================================================================================

from .notification_service import (
    NotificationService,
    NotificationStatus as NotificationServiceStatus,
    NotificationPriority,
    NotificationType,
    Notification,
    NotificationTemplate,
    NotificationPreference,
    NotificationStats,
    NotificationProvider as NotificationServiceProvider,
    EmailProvider as NotificationEmailProvider,
    SlackProvider as NotificationSlackProvider,
    TelegramProvider as NotificationTelegramProvider,
    ConsoleProvider,
    get_notification_service,
    reset_notification_service,
)

# ====================================================================================
# PERFORMANCE MONITOR
# ====================================================================================

from .performance_monitor import (
    PerformanceMonitor,
    PerformanceMetric,
    PerformanceSeverity,
    PerformanceStatus,
    PerformanceDataPoint,
    PerformanceThreshold,
    PerformanceIssue,
    PerformanceReport,
    get_performance_monitor,
    reset_performance_monitor,
)

# ====================================================================================
# REPORT GENERATOR
# ====================================================================================

from .report_generator import (
    ReportGenerator,
    ReportType,
    ReportFormat,
    ReportStatus,
    ReportSchedule,
    Report,
    ReportConfig,
    ReportTemplate,
    get_report_generator,
    reset_report_generator,
)

# ====================================================================================
# PACKAGE METADATA
# ====================================================================================

__version__ = "3.0.0"
__author__ = "Dr X..."
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"
__description__ = "NEXUS AI Trading System - Arbitrage Bot Monitoring"
__status__ = "Production Ready"

# ====================================================================================
# PACKAGE INITIALIZATION
# ====================================================================================

# Initialize package logger
logger = logging.getLogger(__name__)
logger.debug(f"Monitoring package v{__version__} initialized")

# Global instances
_global_alert_manager: Optional[AlertManager] = None
_global_dashboard_api: Optional[DashboardAPI] = None
_global_health_checker: Optional[HealthChecker] = None
_global_incident_manager: Optional[IncidentManager] = None
_global_log_analyzer: Optional[LogAnalyzer] = None
_global_metric_collector: Optional[MetricCollector] = None
_global_notification_service: Optional[NotificationService] = None
_global_performance_monitor: Optional[PerformanceMonitor] = None
_global_report_generator: Optional[ReportGenerator] = None

# ====================================================================================
# CONVENIENCE FUNCTIONS
# ====================================================================================

async def initialize_monitoring(
    config: Optional[Dict[str, Any]] = None
) -> None:
    """
    Initialize all monitoring components.
    
    Args:
        config: Configuration dictionary
    """
    config = config or {}
    
    # Initialize alert manager
    alert_manager = get_alert_manager()
    await alert_manager.initialize()
    
    # Initialize health checker
    health_checker = get_health_checker()
    await health_checker.initialize()
    
    # Initialize incident manager
    incident_manager = get_incident_manager()
    await incident_manager.initialize()
    
    # Initialize log analyzer
    log_analyzer = get_log_analyzer()
    await log_analyzer.initialize()
    
    # Initialize metric collector
    metric_collector = get_metric_collector()
    await metric_collector.initialize()
    
    # Initialize notification service
    notification_service = get_notification_service()
    await notification_service.initialize()
    
    # Initialize performance monitor
    performance_monitor = get_performance_monitor()
    await performance_monitor.initialize()
    
    # Initialize report generator
    report_generator = get_report_generator()
    await report_generator.initialize()
    
    # Initialize dashboard API
    dashboard_api = get_dashboard_api()
    await dashboard_api.start()
    
    logger.info("All monitoring components initialized")


async def shutdown_monitoring() -> None:
    """Shutdown all monitoring components gracefully."""
    global _global_alert_manager, _global_dashboard_api, _global_health_checker
    global _global_incident_manager, _global_log_analyzer, _global_metric_collector
    global _global_notification_service, _global_performance_monitor, _global_report_generator
    
    try:
        # Shutdown in reverse order
        if _global_report_generator:
            await _global_report_generator.close()
            _global_report_generator = None
            
        if _global_performance_monitor:
            await _global_performance_monitor.close()
            _global_performance_monitor = None
            
        if _global_notification_service:
            await _global_notification_service.close()
            _global_notification_service = None
            
        if _global_metric_collector:
            await _global_metric_collector.close()
            _global_metric_collector = None
            
        if _global_log_analyzer:
            await _global_log_analyzer.close()
            _global_log_analyzer = None
            
        if _global_incident_manager:
            await _global_incident_manager.close()
            _global_incident_manager = None
            
        if _global_health_checker:
            await _global_health_checker.close()
            _global_health_checker = None
            
        if _global_dashboard_api:
            await _global_dashboard_api.stop()
            _global_dashboard_api = None
            
        if _global_alert_manager:
            await _global_alert_manager.close()
            _global_alert_manager = None
            
        logger.info("All monitoring components shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during monitoring shutdown: {e}")


def get_monitoring_status() -> Dict[str, bool]:
    """
    Get status of all monitoring components.
    
    Returns:
        Dict of component name -> initialized status
    """
    return {
        "alert_manager": _global_alert_manager is not None and _global_alert_manager._initialized,
        "dashboard_api": _global_dashboard_api is not None and _global_dashboard_api._running,
        "health_checker": _global_health_checker is not None and _global_health_checker._initialized,
        "incident_manager": _global_incident_manager is not None and _global_incident_manager._initialized,
        "log_analyzer": _global_log_analyzer is not None and _global_log_analyzer._initialized,
        "metric_collector": _global_metric_collector is not None and _global_metric_collector._initialized,
        "notification_service": _global_notification_service is not None and _global_notification_service._initialized,
        "performance_monitor": _global_performance_monitor is not None and _global_performance_monitor._initialized,
        "report_generator": _global_report_generator is not None and _global_report_generator._initialized,
    }


def reset_all_monitoring() -> None:
    """Reset all monitoring components."""
    reset_alert_manager()
    reset_health_checker()
    reset_incident_manager()
    reset_log_analyzer()
    reset_metric_collector()
    reset_notification_service()
    reset_performance_monitor()
    reset_report_generator()
    
    global _global_dashboard_api
    if _global_dashboard_api:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_global_dashboard_api.stop())
            else:
                asyncio.run(_global_dashboard_api.stop())
        except Exception:
            pass
        _global_dashboard_api = None
        
    logger.info("All monitoring components reset")


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Alert Manager
    'AlertManager',
    'NotificationStatus',
    'EscalationStatus',
    'EmailConfig',
    'SlackConfig',
    'TelegramConfig',
    'DiscordConfig',
    'PagerDutyConfig',
    'WebhookConfig',
    'NotificationProvider',
    'EmailProvider',
    'SlackProvider',
    'TelegramProvider',
    'DiscordProvider',
    'PagerDutyProvider',
    'WebhookProvider',
    'get_alert_manager',
    'reset_alert_manager',
    
    # Dashboard API
    'DashboardAPI',
    'get_dashboard_api',
    
    # Health Checker
    'HealthChecker',
    'HealthStatus',
    'ComponentType',
    'CheckSeverity',
    'HealthCheckConfig',
    'HealthCheckResult',
    'ComponentHealth',
    'SystemHealth',
    'create_exchange_health_check',
    'create_service_health_check',
    'create_database_health_check',
    'create_websocket_health_check',
    'get_health_checker',
    'reset_health_checker',
    
    # Incident Manager
    'IncidentManager',
    'IncidentSeverity',
    'IncidentStatus',
    'IncidentCategory',
    'IncidentPriority',
    'ResolutionStatus',
    'Incident',
    'IncidentTimeline',
    'IncidentMetrics',
    'IncidentReport',
    'get_incident_manager',
    'reset_incident_manager',
    
    # Log Analyzer
    'LogAnalyzer',
    'LogLevel',
    'LogPatternType',
    'LogAnalysisPeriod',
    'LogEntry',
    'LogPattern',
    'LogAnomaly',
    'LogAnalysisResult',
    'get_log_analyzer',
    'reset_log_analyzer',
    
    # Metric Collector
    'MetricCollector',
    'MetricType',
    'MetricCategory',
    'AggregationMethod',
    'Metric',
    'MetricAggregation',
    'MetricQuery',
    'get_metric_collector',
    'reset_metric_collector',
    
    # Notification Service
    'NotificationService',
    'NotificationServiceStatus',
    'NotificationPriority',
    'NotificationType',
    'Notification',
    'NotificationTemplate',
    'NotificationPreference',
    'NotificationStats',
    'NotificationServiceProvider',
    'NotificationEmailProvider',
    'NotificationSlackProvider',
    'NotificationTelegramProvider',
    'ConsoleProvider',
    'get_notification_service',
    'reset_notification_service',
    
    # Performance Monitor
    'PerformanceMonitor',
    'PerformanceMetric',
    'PerformanceSeverity',
    'PerformanceStatus',
    'PerformanceDataPoint',
    'PerformanceThreshold',
    'PerformanceIssue',
    'PerformanceReport',
    'get_performance_monitor',
    'reset_performance_monitor',
    
    # Report Generator
    'ReportGenerator',
    'ReportType',
    'ReportFormat',
    'ReportStatus',
    'ReportSchedule',
    'Report',
    'ReportConfig',
    'ReportTemplate',
    'get_report_generator',
    'reset_report_generator',
    
    # Package functions
    'initialize_monitoring',
    'shutdown_monitoring',
    'get_monitoring_status',
    'reset_all_monitoring',
]

# ====================================================================================
# END OF MONITORING PACKAGE
# ====================================================================================
