# trading/bots/hedge_bot/monitoring/__init__.py

"""
NEXUS HEDGE BOT - MONITORING MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Comprehensive monitoring system with real-time metrics, alerting,
incident management, health checks, performance monitoring, and reporting.

Version: 3.0.0
"""

import logging
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import structlog
from structlog import BoundLogger

# Import submodules
from .alert_manager import (
    AlertManager,
    Alert,
    AlertRule,
    Channel,
    AlertSeverity,
    AlertCategory,
    AlertStatus,
    ChannelType,
)

from .dashboard_api import (
    DashboardAPI,
    DashboardConfig,
    DashboardData,
    DashboardMetric,
    SystemStatus,
    create_dashboard_api,
)

from .health_checker import (
    HealthMonitor,
    HealthMonitorConfig,
    HealthCheckConfig,
    HealthCheckResult,
    HealthStatus,
    HealthCheckType,
    ResourceType,
    BaseHealthChecker,
    SystemHealthChecker,
    NetworkHealthChecker,
    DatabaseHealthChecker,
    CacheHealthChecker,
    BrokerHealthChecker,
)

from .incident_manager import (
    IncidentManager,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    IncidentCategory,
    IncidentType,
)

from .log_analyzer import (
    LogAnalyzer,
    LogEntry,
    LogPattern,
    LogPatternType,
    Anomaly,
    AnomalySeverity,
    LogLevel,
)

from .metric_collector import (
    MetricCollector,
    Metric,
    MetricHistogram,
    MetricType,
    MetricCategory,
)

from .notification_service import (
    NotificationService,
    Notification,
    NotificationTemplate,
    NotificationChannel,
    NotificationPriority,
    NotificationStatus,
    NotificationTemplateType,
)

from .performance_monitor import (
    PerformanceMonitor,
    PerformanceSample,
    PerformanceAlert,
    PerformanceMetricType,
    PerformanceAlertLevel,
)

from .report_generator import (
    ReportGenerator,
    Report,
    ReportSchedule,
    ReportType,
    ReportFormat,
    ReportStatus,
    ReportDistributionChannel,
)

# Setup default logger
logger = structlog.get_logger(__name__)

# === MODULE CONFIGURATION ===

class MonitoringConfig:
    """Configuration for the monitoring module."""
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize monitoring configuration.
        
        Args:
            config_path: Path to configuration file
            **kwargs: Additional configuration parameters
        """
        self.config = kwargs.copy()
        
        if config_path:
            import yaml
            with open(config_path, "r") as f:
                yaml_config = yaml.safe_load(f)
                self.config.update(yaml_config)
        
        # Set defaults
        self.config.setdefault("db_path", "monitoring.db")
        self.config.setdefault("log_dir", "logs")
        self.config.setdefault("report_dir", "reports")
        self.config.setdefault("alert_config", {})
        self.config.setdefault("health_config", {})
        self.config.setdefault("incident_config", {})
        self.config.setdefault("performance_config", {})
        self.config.setdefault("notification_config", {})
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)


# === MONITORING SERVICE ===

class MonitoringService:
    """
    Centralized monitoring service for the hedge bot.
    """
    
    def __init__(
        self,
        config: Optional[Union[Dict[str, Any], MonitoringConfig, str]] = None
    ):
        """
        Initialize the monitoring service.
        
        Args:
            config: Configuration object, dict, or path to config file
        """
        if isinstance(config, str):
            self.config = MonitoringConfig(config_path=config)
        elif isinstance(config, dict):
            self.config = MonitoringConfig(**config)
        elif isinstance(config, MonitoringConfig):
            self.config = config
        else:
            self.config = MonitoringConfig()
        
        self._initialized = False
        self._closed = False
        self._lock = threading.RLock()
        
        # Component instances
        self.alert_manager: Optional[AlertManager] = None
        self.health_monitor: Optional[HealthMonitor] = None
        self.incident_manager: Optional[IncidentManager] = None
        self.log_analyzer: Optional[LogAnalyzer] = None
        self.metric_collector: Optional[MetricCollector] = None
        self.notification_service: Optional[NotificationService] = None
        self.performance_monitor: Optional[PerformanceMonitor] = None
        self.report_generator: Optional[ReportGenerator] = None
        self.dashboard_api: Optional[DashboardAPI] = None
        
        # Background tasks
        self._background_tasks = []
        self._running = False
        
        # Initialize components
        self._initialize_components()
        
        logger.info(
            "monitoring_service_initialized",
            version="3.0.0",
            components=self._get_component_status(),
        )
    
    def _initialize_components(self) -> None:
        """Initialize all monitoring components."""
        try:
            # Alert Manager
            self.alert_manager = AlertManager(
                config=self.config.get("alert_config", {}),
            )
            
            # Health Monitor
            self.health_monitor = HealthMonitor(
                config=self.config.get("health_config", {}),
            )
            
            # Incident Manager
            self.incident_manager = IncidentManager(
                config=self.config.get("incident_config", {}),
            )
            
            # Log Analyzer
            self.log_analyzer = LogAnalyzer(
                config=self.config.get("log_analyzer_config", {}),
                log_files=self.config.get("log_files", []),
            )
            
            # Metric Collector
            self.metric_collector = MetricCollector(
                config=self.config.get("metric_config", {}),
            )
            
            # Notification Service
            self.notification_service = NotificationService(
                config=self.config.get("notification_config", {}),
            )
            
            # Performance Monitor
            self.performance_monitor = PerformanceMonitor(
                config=self.config.get("performance_config", {}),
            )
            
            # Report Generator
            self.report_generator = ReportGenerator(
                config=self.config.get("report_config", {}),
            )
            
            # Dashboard API
            if self.config.get("dashboard_enabled", True):
                self.dashboard_api = DashboardAPI(
                    config=self.config.get("dashboard_config", {}),
                    alert_manager=self.alert_manager,
                    health_checker=self.health_monitor,
                    incident_manager=self.incident_manager,
                    log_analyzer=self.log_analyzer,
                    metric_collector=self.metric_collector,
                )
            
            self._initialized = True
            
        except Exception as e:
            logger.error(
                "monitoring_component_initialization_failed",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            raise
    
    def start(self) -> None:
        """Start all monitoring components."""
        if self._running:
            return
        
        self._running = True
        
        try:
            # Start components
            if self.health_monitor:
                asyncio.create_task(self.health_monitor.start())
            
            if self.dashboard_api:
                asyncio.create_task(self.dashboard_api.start())
            
            logger.info("monitoring_service_started")
            
        except Exception as e:
            logger.error("monitoring_service_start_failed", error=str(e))
            raise
    
    async def start_async(self) -> None:
        """Start all monitoring components asynchronously."""
        if self._running:
            return
        
        self._running = True
        
        try:
            # Start components
            if self.health_monitor:
                await self.health_monitor.start()
            
            if self.dashboard_api:
                await self.dashboard_api.start()
            
            logger.info("monitoring_service_started")
            
        except Exception as e:
            logger.error("monitoring_service_start_failed", error=str(e))
            raise
    
    def stop(self) -> None:
        """Stop all monitoring components."""
        if not self._running:
            return
        
        self._running = False
        
        try:
            # Stop components
            if self.dashboard_api:
                asyncio.create_task(self.dashboard_api.stop())
            
            if self.health_monitor:
                asyncio.create_task(self.health_monitor.stop())
            
            logger.info("monitoring_service_stopped")
            
        except Exception as e:
            logger.error("monitoring_service_stop_failed", error=str(e))
    
    async def stop_async(self) -> None:
        """Stop all monitoring components asynchronously."""
        if not self._running:
            return
        
        self._running = False
        
        try:
            # Stop components
            if self.dashboard_api:
                await self.dashboard_api.stop()
            
            if self.health_monitor:
                await self.health_monitor.stop()
            
            logger.info("monitoring_service_stopped")
            
        except Exception as e:
            logger.error("monitoring_service_stop_failed", error=str(e))
    
    def close(self) -> None:
        """Close all monitoring components."""
        if self._closed:
            return
        
        self._closed = True
        
        try:
            # Close components
            if self.alert_manager:
                self.alert_manager.close()
            
            if self.incident_manager:
                self.incident_manager.close()
            
            if self.log_analyzer:
                self.log_analyzer.close()
            
            if self.metric_collector:
                self.metric_collector.close()
            
            if self.notification_service:
                self.notification_service.close()
            
            if self.performance_monitor:
                self.performance_monitor.close()
            
            if self.report_generator:
                self.report_generator.close()
            
            if self.dashboard_api:
                self.dashboard_api.close()
            
            logger.info("monitoring_service_closed")
            
        except Exception as e:
            logger.error("monitoring_service_close_failed", error=str(e))
    
    def get_component(self, name: str) -> Optional[Any]:
        """
        Get a monitoring component by name.
        
        Args:
            name: Component name (alert_manager, health_monitor, etc.)
            
        Returns:
            Component instance or None
        """
        component_map = {
            "alert_manager": self.alert_manager,
            "health_monitor": self.health_monitor,
            "incident_manager": self.incident_manager,
            "log_analyzer": self.log_analyzer,
            "metric_collector": self.metric_collector,
            "notification_service": self.notification_service,
            "performance_monitor": self.performance_monitor,
            "report_generator": self.report_generator,
            "dashboard_api": self.dashboard_api,
        }
        
        return component_map.get(name)
    
    def _get_component_status(self) -> Dict[str, bool]:
        """Get status of all monitoring components."""
        return {
            "alert_manager": self.alert_manager is not None,
            "health_monitor": self.health_monitor is not None,
            "incident_manager": self.incident_manager is not None,
            "log_analyzer": self.log_analyzer is not None,
            "metric_collector": self.metric_collector is not None,
            "notification_service": self.notification_service is not None,
            "performance_monitor": self.performance_monitor is not None,
            "report_generator": self.report_generator is not None,
            "dashboard_api": self.dashboard_api is not None,
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get monitoring service status.
        
        Returns:
            Dictionary with service status
        """
        return {
            "initialized": self._initialized,
            "running": self._running,
            "closed": self._closed,
            "components": self._get_component_status(),
            "metrics": self.get_metrics(),
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get metrics from all monitoring components.
        
        Returns:
            Dictionary with metrics
        """
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "components": {},
        }
        
        if self.alert_manager:
            metrics["components"]["alert_manager"] = self.alert_manager.get_metrics()
        
        if self.health_monitor:
            metrics["components"]["health_monitor"] = self.health_monitor.get_metrics()
        
        if self.incident_manager:
            metrics["components"]["incident_manager"] = self.incident_manager.get_metrics()
        
        if self.metric_collector:
            metrics["components"]["metric_collector"] = self.metric_collector.get_metrics_summary()
        
        if self.performance_monitor:
            metrics["components"]["performance_monitor"] = self.performance_monitor.get_metrics()
        
        if self.report_generator:
            metrics["components"]["report_generator"] = self.report_generator.get_metrics()
        
        return metrics


# === MODULE EXPORTS ===

__all__ = [
    # Main service
    "MonitoringService",
    "MonitoringConfig",
    
    # Alert Manager
    "AlertManager",
    "Alert",
    "AlertRule",
    "Channel",
    "AlertSeverity",
    "AlertCategory",
    "AlertStatus",
    "ChannelType",
    
    # Dashboard API
    "DashboardAPI",
    "DashboardConfig",
    "DashboardData",
    "DashboardMetric",
    "SystemStatus",
    "create_dashboard_api",
    
    # Health Checker
    "HealthMonitor",
    "HealthMonitorConfig",
    "HealthCheckConfig",
    "HealthCheckResult",
    "HealthStatus",
    "HealthCheckType",
    "ResourceType",
    "BaseHealthChecker",
    "SystemHealthChecker",
    "NetworkHealthChecker",
    "DatabaseHealthChecker",
    "CacheHealthChecker",
    "BrokerHealthChecker",
    
    # Incident Manager
    "IncidentManager",
    "Incident",
    "IncidentSeverity",
    "IncidentStatus",
    "IncidentCategory",
    "IncidentType",
    
    # Log Analyzer
    "LogAnalyzer",
    "LogEntry",
    "LogPattern",
    "LogPatternType",
    "Anomaly",
    "AnomalySeverity",
    "LogLevel",
    
    # Metric Collector
    "MetricCollector",
    "Metric",
    "MetricHistogram",
    "MetricType",
    "MetricCategory",
    
    # Notification Service
    "NotificationService",
    "Notification",
    "NotificationTemplate",
    "NotificationChannel",
    "NotificationPriority",
    "NotificationStatus",
    "NotificationTemplateType",
    
    # Performance Monitor
    "PerformanceMonitor",
    "PerformanceSample",
    "PerformanceAlert",
    "PerformanceMetricType",
    "PerformanceAlertLevel",
    
    # Report Generator
    "ReportGenerator",
    "Report",
    "ReportSchedule",
    "ReportType",
    "ReportFormat",
    "ReportStatus",
    "ReportDistributionChannel",
]

# === MODULE INITIALIZATION ===

logger.info(
    "monitoring_module_initialized",
    version="3.0.0",
    module="trading.bots.hedge_bot.monitoring",
    copyright="© 2026 NEXUS QUANTUM LTD",
)

# === SAMPLE MONITORING CONFIGURATION ===

SAMPLE_MONITORING_CONFIG = {
    "db_path": "monitoring.db",
    "log_dir": "logs",
    "report_dir": "reports",
    "dashboard_enabled": True,
    "dashboard_config": {
        "host": "0.0.0.0",
        "port": 8000,
        "update_interval_seconds": 5,
    },
    "alert_config": {
        "default_channels": ["slack", "email"],
        "rules": [
            {
                "name": "High CPU Alert",
                "condition": "system.cpu_usage > 80",
                "severity": "warning",
                "category": "system",
                "channels": ["slack", "email"],
            },
            {
                "name": "High Drawdown Alert",
                "condition": "drawdown > 5",
                "severity": "warning",
                "category": "risk",
                "channels": ["slack", "email"],
            },
        ],
        "channels": [
            {
                "name": "slack",
                "type": "slack",
                "config": {
                    "webhook_url": "https://hooks.slack.com/...",
                },
            },
            {
                "name": "email",
                "type": "email",
                "config": {
                    "smtp_host": "smtp.gmail.com",
                    "smtp_port": 587,
                    "smtp_user": "alerts@nexusquantum.com",
                    "smtp_password": "****",
                    "from_email": "alerts@nexusquantum.com",
                    "to_emails": ["admin@nexusquantum.com"],
                },
            },
        ],
    },
    "health_config": {
        "check_interval_seconds": 10,
        "checks": [
            {
                "name": "System Health",
                "type": "system",
                "threshold_warning": 70.0,
                "threshold_critical": 85.0,
            },
            {
                "name": "Network Health",
                "type": "network",
                "config": {
                    "targets": [
                        {"host": "8.8.8.8", "port": 53},
                        {"host": "api.binance.com", "port": 443},
                    ],
                },
            },
        ],
    },
    "performance_config": {
        "collect_interval": 5.0,
        "profiling_enabled": True,
        "memory_tracking_enabled": True,
        "thresholds": {
            "cpu_warning": 70.0,
            "cpu_critical": 85.0,
            "memory_warning": 80.0,
            "memory_critical": 90.0,
            "latency_warning": 100.0,
            "latency_critical": 500.0,
        },
    },
    "log_analyzer_config": {
        "log_files": ["logs/hedge.log", "logs/errors.log"],
        "monitor_interval": 1.0,
        "analysis_interval": 60.0,
        "retention_days": 30,
    },
    "notification_config": {
        "retry_interval": 60,
        "retry_delay": 300,
        "channels": {
            "slack": {
                "webhook_url": "https://hooks.slack.com/...",
            },
            "telegram": {
                "bot_token": "****",
                "chat_id": "****",
            },
            "email": {
                "smtp_host": "smtp.gmail.com",
                "smtp_port": 587,
                "smtp_user": "notifications@nexusquantum.com",
                "smtp_password": "****",
                "from_email": "notifications@nexusquantum.com",
            },
        },
        "rate_limits": {
            "slack": 60,
            "telegram": 30,
            "email": 100,
            "webhook": 120,
        },
    },
    "report_config": {
        "output_dir": "reports",
        "template_dir": "templates",
        "charts": {
            "width": 1200,
            "height": 600,
            "dpi": 150,
            "theme": "dark",
        },
    },
}
