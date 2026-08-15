"""
Swing Bot Alert Manager
=========================

This module provides alert management capabilities for the Swing Bot trading system.
"""

import time
import threading
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, Union, Set
from dataclasses import dataclass, field
from enum import Enum
import logging
import json

from .notification_service import NotificationService
from .metric_collector import MetricCollector
from .incident_manager import IncidentManager, IncidentSeverity, IncidentType


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(Enum):
    """Alert status states."""
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    IGNORED = "ignored"
    ESCALATED = "escalated"


@dataclass
class Alert:
    """Alert data structure."""
    id: str
    name: str
    message: str
    severity: AlertSeverity
    status: AlertStatus
    created_at: datetime
    updated_at: datetime
    source: str
    tags: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution: Optional[str] = None


@dataclass
class AlertRule:
    """Alert rule configuration."""
    name: str
    condition: Callable[[], bool]
    message: str
    severity: AlertSeverity
    source: str
    cooldown: int = 300  # seconds
    enabled: bool = True
    tags: List[str] = field(default_factory=list)
    last_triggered: Optional[datetime] = None


class AlertManager:
    """
    Manage alerts and alert rules.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the alert manager.
        
        Args:
            config: Configuration settings
        """
        self.config = config or {}
        self.alerts: Dict[str, Alert] = {}
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Set[str] = set()
        self.handlers: List[Callable] = []
        self._lock = threading.RLock()
        self._running = False
        self._checker_thread: Optional[threading.Thread] = None
        
        # Initialize services
        self.notification_service = NotificationService(self.config.get('notification', {}))
        self.metric_collector = MetricCollector(self.config.get('metrics', {}))
        self.incident_manager = IncidentManager(self.config.get('incidents', {}))
        
        # Register default rules
        self._register_default_rules()
        
        if self.config.get('auto_start', True):
            self.start()
    
    def _register_default_rules(self) -> None:
        """Register default alert rules."""
        # CPU usage rule
        self.register_rule(
            name="high_cpu_usage",
            condition=self._check_cpu_usage,
            message="CPU usage is above threshold",
            severity=AlertSeverity.HIGH,
            source="system"
        )
        
        # Memory usage rule
        self.register_rule(
            name="high_memory_usage",
            condition=self._check_memory_usage,
            message="Memory usage is above threshold",
            severity=AlertSeverity.HIGH,
            source="system"
        )
        
        # Disk usage rule
        self.register_rule(
            name="high_disk_usage",
            condition=self._check_disk_usage,
            message="Disk usage is above threshold",
            severity=AlertSeverity.MEDIUM,
            source="system"
        )
        
        # Trade error rule
        self.register_rule(
            name="trade_error",
            condition=self._check_trade_errors,
            message="Trade errors detected",
            severity=AlertSeverity.HIGH,
            source="trading"
        )
        
        # Risk breach rule
        self.register_rule(
            name="risk_breach",
            condition=self._check_risk_breach,
            message="Risk limit breach detected",
            severity=AlertSeverity.CRITICAL,
            source="risk"
        )
    
    def register_rule(
        self,
        name: str,
        condition: Callable[[], bool],
        message: str,
        severity: Union[AlertSeverity, str],
        source: str,
        cooldown: int = 300,
        enabled: bool = True,
        tags: Optional[List[str]] = None
    ) -> None:
        """
        Register an alert rule.
        
        Args:
            name: Rule name
            condition: Condition function
            message: Alert message
            severity: Alert severity
            source: Alert source
            cooldown: Cooldown period in seconds
            enabled: Whether the rule is enabled
            tags: Additional tags
        """
        if isinstance(severity, str):
            severity = AlertSeverity(severity.lower())
        
        with self._lock:
            self.rules[name] = AlertRule(
                name=name,
                condition=condition,
                message=message,
                severity=severity,
                source=source,
                cooldown=cooldown,
                enabled=enabled,
                tags=tags or []
            )
    
    def start(self) -> None:
        """Start the alert manager."""
        if self._running:
            return
        
        self._running = True
        self._checker_thread = threading.Thread(target=self._check_loop, daemon=True)
        self._checker_thread.start()
        logging.info("Alert manager started")
    
    def stop(self) -> None:
        """Stop the alert manager."""
        self._running = False
        if self._checker_thread:
            self._checker_thread.join(timeout=5)
        logging.info("Alert manager stopped")
    
    def _check_loop(self) -> None:
        """Main alert checking loop."""
        while self._running:
            try:
                self._check_rules()
                time.sleep(10)
            except Exception as e:
                logging.error(f"Alert check loop error: {e}")
    
    def _check_rules(self) -> None:
        """Check all alert rules."""
        now = datetime.now()
        
        with self._lock:
            for rule_name, rule in self.rules.items():
                if not rule.enabled:
                    continue
                
                # Check cooldown
                if rule.last_triggered:
                    cooldown_seconds = (now - rule.last_triggered).total_seconds()
                    if cooldown_seconds < rule.cooldown:
                        continue
                
                try:
                    if rule.condition():
                        # Trigger alert
                        self._trigger_alert(rule)
                        rule.last_triggered = now
                except Exception as e:
                    logging.error(f"Error checking rule {rule_name}: {e}")
    
    def _trigger_alert(self, rule: AlertRule) -> Alert:
        """
        Trigger an alert from a rule.
        
        Args:
            rule: Alert rule
        
        Returns:
            Created alert
        """
        alert = Alert(
            id=f"alert_{int(time.time())}_{rule.name}",
            name=rule.name,
            message=rule.message,
            severity=rule.severity,
            status=AlertStatus.NEW,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            source=rule.source,
            tags=rule.tags
        )
        
        self.alerts[alert.id] = alert
        self.active_alerts.add(alert.id)
        
        # Send notifications
        self._send_alert_notification(alert)
        
        # Create incident for critical alerts
        if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
            self._create_incident(alert)
        
        # Record metric
        self.metric_collector.record('alerts', 1, {
            'severity': alert.severity.value,
            'source': alert.source
        }, 'count')
        
        # Call handlers
        for handler in self.handlers:
            try:
                handler(alert)
            except Exception as e:
                logging.error(f"Alert handler error: {e}")
        
        return alert
    
    def _send_alert_notification(self, alert: Alert) -> None:
        """Send notification for an alert."""
        severity_icons = {
            AlertSeverity.CRITICAL: '🚨',
            AlertSeverity.HIGH: '⚠️',
            AlertSeverity.MEDIUM: '📢',
            AlertSeverity.LOW: 'ℹ️',
            AlertSeverity.INFO: '📋'
        }
        
        title = f"{severity_icons.get(alert.severity, '📢')} Alert: {alert.name}"
        message = f"""
**Alert:** {alert.name}
**Severity:** {alert.severity.value.upper()}
**Source:** {alert.source}
**Time:** {alert.created_at.strftime('%Y-%m-%d %H:%M:%S')}

**Message:**
{alert.message}

**Tags:** {', '.join(alert.tags) if alert.tags else 'None'}
        """
        
        priority = 'critical' if alert.severity == AlertSeverity.CRITICAL else 'high'
        self.notification_service.send_alert(
            alert_type='alert',
            message=message,
            severity=priority,
            data={'alert_id': alert.id}
        )
    
    def _create_incident(self, alert: Alert) -> None:
        """Create an incident from a critical alert."""
        severity_map = {
            AlertSeverity.CRITICAL: IncidentSeverity.CRITICAL,
            AlertSeverity.HIGH: IncidentSeverity.HIGH,
            AlertSeverity.MEDIUM: IncidentSeverity.MEDIUM,
            AlertSeverity.LOW: IncidentSeverity.LOW,
            AlertSeverity.INFO: IncidentSeverity.INFO
        }
        
        self.incident_manager.create_incident(
            title=alert.name,
            description=alert.message,
            severity=severity_map.get(alert.severity, IncidentSeverity.MEDIUM),
            incident_type=IncidentType.SYSTEM,
            tags=alert.tags
        )
    
    def acknowledge_alert(self, alert_id: str, user: str) -> Optional[Alert]:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: Alert ID
            user: User acknowledging the alert
        
        Returns:
            Updated alert or None
        """
        with self._lock:
            alert = self.alerts.get(alert_id)
            if not alert:
                return None
            
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.updated_at = datetime.now()
            alert.acknowledged_by = user
            
            return alert
    
    def resolve_alert(self, alert_id: str, resolution: str) -> Optional[Alert]:
        """
        Resolve an alert.
        
        Args:
            alert_id: Alert ID
            resolution: Resolution details
        
        Returns:
            Updated alert or None
        """
        with self._lock:
            alert = self.alerts.get(alert_id)
            if not alert:
                return None
            
            alert.status = AlertStatus.RESOLVED
            alert.updated_at = datetime.now()
            alert.resolved_at = datetime.now()
            alert.resolution = resolution
            self.active_alerts.discard(alert_id)
            
            return alert
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """
        Get an alert by ID.
        
        Args:
            alert_id: Alert ID
        
        Returns:
            Alert or None
        """
        return self.alerts.get(alert_id)
    
    def get_active_alerts(self) -> List[Alert]:
        """
        Get all active alerts.
        
        Returns:
            List of active alerts
        """
        return [self.alerts[i] for i in self.active_alerts if i in self.alerts]
    
    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Alert]:
        """
        Get alerts by severity.
        
        Args:
            severity: Alert severity
        
        Returns:
            List of alerts
        """
        return [a for a in self.alerts.values() if a.severity == severity]
    
    def get_alerts_by_status(self, status: AlertStatus) -> List[Alert]:
        """
        Get alerts by status.
        
        Args:
            status: Alert status
        
        Returns:
            List of alerts
        """
        return [a for a in self.alerts.values() if a.status == status]
    
    def get_alerts_by_source(self, source: str) -> List[Alert]:
        """
        Get alerts by source.
        
        Args:
            source: Alert source
        
        Returns:
            List of alerts
        """
        return [a for a in self.alerts.values() if a.source == source]
    
    def get_alerts_by_time_range(
        self,
        start: datetime,
        end: datetime
    ) -> List[Alert]:
        """
        Get alerts within a time range.
        
        Args:
            start: Start time
            end: End time
        
        Returns:
            List of alerts
        """
        return [
            a for a in self.alerts.values()
            if start <= a.created_at <= end
        ]
    
    def register_handler(self, handler: Callable) -> None:
        """
        Register an alert handler.
        
        Args:
            handler: Handler function
        """
        self.handlers.append(handler)
    
    # Default rule check functions
    
    def _check_cpu_usage(self) -> bool:
        """Check CPU usage."""
        import psutil
        threshold = self.config.get('cpu_threshold', 80)
        cpu_usage = psutil.cpu_percent(interval=0.1)
        return cpu_usage > threshold
    
    def _check_memory_usage(self) -> bool:
        """Check memory usage."""
        import psutil
        threshold = self.config.get('memory_threshold', 85)
        memory = psutil.virtual_memory()
        return memory.percent > threshold
    
    def _check_disk_usage(self) -> bool:
        """Check disk usage."""
        import psutil
        threshold = self.config.get('disk_threshold', 85)
        disk = psutil.disk_usage('/')
        return disk.percent > threshold
    
    def _check_trade_errors(self) -> bool:
        """Check for trade errors."""
        # Placeholder - implement actual trade error checking
        return False
    
    def _check_risk_breach(self) -> bool:
        """Check for risk breaches."""
        # Placeholder - implement actual risk breach checking
        return False
    
    def generate_report(self) -> Dict[str, Any]:
        """
        Generate an alert report.
        
        Returns:
            Alert report
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'total_alerts': len(self.alerts),
            'active_alerts': len(self.active_alerts),
            'alerts_by_severity': {
                severity.value: len(self.get_alerts_by_severity(severity))
                for severity in AlertSeverity
            },
            'alerts_by_status': {
                status.value: len(self.get_alerts_by_status(status))
                for status in AlertStatus
            },
            'alerts_by_source': {
                source: len(self.get_alerts_by_source(source))
                for source in set(a.source for a in self.alerts.values())
            },
            'recent_alerts': [
                {
                    'id': a.id,
                    'name': a.name,
                    'severity': a.severity.value,
                    'status': a.status.value,
                    'created_at': a.created_at.isoformat()
                }
                for a in sorted(
                    self.alerts.values(),
                    key=lambda x: x.created_at,
                    reverse=True
                )[:10]
            ]
        }


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get the global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


__all__ = [
    'AlertSeverity',
    'AlertStatus',
    'Alert',
    'AlertRule',
    'AlertManager',
    'get_alert_manager'
]
