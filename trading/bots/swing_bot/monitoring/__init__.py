"""
Swing Bot Monitoring Package
==============================

This package provides monitoring capabilities for the Swing Bot trading system.
Includes alerting, metrics collection, health checking, incident management,
and notification services.
"""

from .alert_manager import (
    AlertSeverity,
    AlertStatus,
    Alert,
    AlertRule,
    AlertManager,
    get_alert_manager
)

from .metric_collector import (
    Metric,
    MetricSummary,
    MetricCollector,
    AsyncMetricCollector,
    get_metric_collector,
    record_metric
)

from .health_checker import (
    HealthStatus,
    HealthCheck,
    HealthReport,
    HealthChecker,
    AsyncHealthChecker,
    get_health_checker,
    check_health
)

from .incident_manager import (
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
    Incident,
    IncidentManager,
    get_incident_manager,
    create_incident
)

from .notification_service import (
    NotificationService,
    EmailHandler,
    TelegramHandler,
    SlackHandler,
    SMSHandler,
    WebhookHandler,
    get_notification_service,
    send_notification,
    send_notification_async,
    send_alert
)

from .performance_monitor import (
    PerformanceMetric,
    PerformanceStats,
    PerformanceMonitor,
    AsyncPerformanceMonitor,
    get_performance_monitor,
    record_metric as record_performance_metric,
    record_time,
    get_metric_stats
)

from .log_analyzer import (
    LogEntry,
    LogAnalysis,
    LogAnalyzer,
    LogRotator,
    get_log_analyzer,
    analyze_logs
)

from .report_generator import (
    ReportGenerator,
    generate_report
)

from .dashboard_api import (
    DashboardAPI,
    create_dashboard_app
)

# Version information
__version__ = "3.0.0"
__author__ = "NEXUS QUANTUM LTD"
__copyright__ = "© 2026 NEXUS QUANTUM LTD - All Rights Reserved"


def setup_monitoring(config: dict) -> None:
    """
    Setup the monitoring system with configuration.
    
    Args:
        config: Monitoring configuration
    """
    # Initialize metric collector
    metric_config = config.get('metrics', {})
    if metric_config.get('enabled', True):
        collector = get_metric_collector()
        if metric_config.get('start_immediately', True):
            collector.start()
    
    # Initialize health checker
    health_config = config.get('health', {})
    if health_config.get('enabled', True):
        checker = get_health_checker()
        if health_config.get('start_immediately', True):
            checker.start()
    
    # Initialize alert manager
    alert_config = config.get('alerts', {})
    if alert_config.get('enabled', True):
        manager = get_alert_manager()
        if alert_config.get('start_immediately', True):
            manager.start()
    
    # Initialize notification service
    notification_config = config.get('notification', {})
    if notification_config.get('enabled', True):
        service = get_notification_service()
        service.config = notification_config


def stop_monitoring() -> None:
    """Stop all monitoring services."""
    # Stop metric collector
    collector = get_metric_collector()
    collector.stop()
    
    # Stop health checker
    checker = get_health_checker()
    checker.stop()
    
    # Stop alert manager
    manager = get_alert_manager()
    manager.stop()


def get_monitoring_status() -> dict:
    """
    Get the status of all monitoring services.
    
    Returns:
        Status information
    """
    return {
        'timestamp': datetime.now().isoformat(),
        'metric_collector': {
            'running': get_metric_collector()._running,
            'metrics_count': len(get_metric_collector().metrics)
        },
        'health_checker': {
            'running': get_health_checker()._running,
            'checks': len(get_health_checker().checks)
        },
        'alert_manager': {
            'running': get_alert_manager()._running,
            'rules': len(get_alert_manager().rules),
            'active_alerts': len(get_alert_manager().active_alerts)
        }
    }


__all__ = [
    # Alert Manager
    'AlertSeverity',
    'AlertStatus',
    'Alert',
    'AlertRule',
    'AlertManager',
    'get_alert_manager',
    
    # Metric Collector
    'Metric',
    'MetricSummary',
    'MetricCollector',
    'AsyncMetricCollector',
    'get_metric_collector',
    'record_metric',
    
    # Health Checker
    'HealthStatus',
    'HealthCheck',
    'HealthReport',
    'HealthChecker',
    'AsyncHealthChecker',
    'get_health_checker',
    'check_health',
    
    # Incident Manager
    'IncidentSeverity',
    'IncidentStatus',
    'IncidentType',
    'Incident',
    'IncidentManager',
    'get_incident_manager',
    'create_incident',
    
    # Notification Service
    'NotificationService',
    'EmailHandler',
    'TelegramHandler',
    'SlackHandler',
    'SMSHandler',
    'WebhookHandler',
    'get_notification_service',
    'send_notification',
    'send_notification_async',
    'send_alert',
    
    # Performance Monitor
    'PerformanceMetric',
    'PerformanceStats',
    'PerformanceMonitor',
    'AsyncPerformanceMonitor',
    'get_performance_monitor',
    'record_performance_metric',
    'record_time',
    'get_metric_stats',
    
    # Log Analyzer
    'LogEntry',
    'LogAnalysis',
    'LogAnalyzer',
    'LogRotator',
    'get_log_analyzer',
    'analyze_logs',
    
    # Report Generator
    'ReportGenerator',
    'generate_report',
    
    # Dashboard API
    'DashboardAPI',
    'create_dashboard_app',
    
    # Setup functions
    'setup_monitoring',
    'stop_monitoring',
    'get_monitoring_status',
    
    # Version
    '__version__',
    '__author__',
    '__copyright__',
]
