# trading/bots/arbitrage_bot/models/alert.py
# NEXUS AI TRADING SYSTEM - ALERT MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for alerts, notifications, and monitoring
# within the arbitrage bot system. It includes alert types, severities, channels,
# and related data structures for comprehensive alerting and incident management.
# ====================================================================================

"""
NEXUS Arbitrage Bot Alert Models

This module provides comprehensive data models for:
- Alert generation and management
- Notification channels and routing
- Incident tracking and resolution
- Alert severity and priority levels
- Alert aggregation and deduplication
- Escalation policies
- Alert history and analytics
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from uuid import UUID, uuid4
import json
import hashlib
from decimal import Decimal

# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class AlertSeverity(str, Enum):
    """
    Alert severity levels defining the urgency of an alert.
    
    CRITICAL: System is down or severely impacted, immediate action required
    HIGH: Major functionality impacted, action required within minutes
    MEDIUM: Moderate impact, action required within hours
    LOW: Minor impact, action required within days
    INFO: Informational, no action required
    """
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertCategory(str, Enum):
    """Categories for classifying alerts."""
    SYSTEM = "system"
    EXCHANGE = "exchange"
    TRADING = "trading"
    RISK = "risk"
    SECURITY = "security"
    PERFORMANCE = "performance"
    NETWORK = "network"
    DATABASE = "database"
    ORDER = "order"
    OPPORTUNITY = "opportunity"
    STRATEGY = "strategy"
    COMPLIANCE = "compliance"
    CONFIG = "config"
    WEBSOCKET = "websocket"
    API = "api"
    MARKET = "market"
    POSITION = "position"
    PNL = "pnl"
    BACKTEST = "backtest"


class AlertStatus(str, Enum):
    """Status of an alert lifecycle."""
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    CLOSED = "closed"
    SUPPRESSED = "suppressed"
    ESCALATED = "escalated"
    AUTO_RESOLVED = "auto_resolved"
    REOPENED = "reopened"


class AlertPriority(str, Enum):
    """Priority levels for alert handling."""
    P0 = "p0"  # Critical - immediate action, system down
    P1 = "p1"  # High - major impact, action within 15 minutes
    P2 = "p2"  # Medium - moderate impact, action within 1 hour
    P3 = "p3"  # Low - minor impact, action within 4 hours
    P4 = "p4"  # Info - informational, action within 24 hours


class NotificationChannel(str, Enum):
    """Supported notification channels."""
    EMAIL = "email"
    SLACK = "slack"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SMS = "sms"
    PAGERDUTY = "pagerduty"
    OPSGENIE = "opsgenie"
    VICTOROPS = "victorops"
    WEBHOOK = "webhook"
    CONSOLE = "console"
    PUSHOVER = "pushover"
    PUSH_BULLET = "pushbullet"
    TWILIO = "twilio"
    GOTIFY = "gotify"
    MATRIX = "matrix"
    MSTEAMS = "msteams"


class AlertAction(str, Enum):
    """Actions that can be taken on alerts."""
    ACKNOWLEDGE = "acknowledge"
    RESOLVE = "resolve"
    ESCALATE = "escalate"
    SUPPRESS = "suppress"
    REOPEN = "reopen"
    CLOSE = "close"
    COMMENT = "comment"
    ASSIGN = "assign"
    NOTE = "note"


class EscalationLevel(str, Enum):
    """Escalation levels for incident response."""
    LEVEL_1 = "level_1"  # Initial response
    LEVEL_2 = "level_2"  # Primary escalation
    LEVEL_3 = "level_3"  # Secondary escalation
    LEVEL_4 = "level_4"  # Manager escalation
    LEVEL_5 = "level_5"  # Executive escalation


class AlertAggregationType(str, Enum):
    """Types of alert aggregation."""
    NONE = "none"
    DEDUPLICATE = "deduplicate"
    GROUP = "group"
    CORRELATE = "correlate"
    THROTTLE = "throttle"
    WINDOW = "window"


class IncidentSeverity(str, Enum):
    """Incident severity levels."""
    SEV1 = "sev1"  # Critical impact, service down
    SEV2 = "sev2"  # Major impact, significant degradation
    SEV3 = "sev3"  | "Moderate impact, partial degradation"
    SEV4 = "sev4"  # Minor impact, minimal degradation
    SEV5 = "sev5"  # No impact, informational


# ====================================================================================
# ALERT DATA MODELS
# ====================================================================================

@dataclass
class AlertMetadata:
    """Metadata associated with an alert."""
    environment: str = "production"
    service: str = "nexus-arbitrage-bot"
    version: str = "3.0.0"
    region: str = "us-east-1"
    cluster: str = "nexus-prod"
    pod: str = ""
    container: str = ""
    hostname: str = ""
    correlation_id: str = ""
    user_id: str = ""
    session_id: str = ""
    trace_id: str = ""
    span_id: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "environment": self.environment,
            "service": self.service,
            "version": self.version,
            "region": self.region,
            "cluster": self.cluster,
            "pod": self.pod,
            "container": self.container,
            "hostname": self.hostname,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "tags": self.tags,
            "custom_fields": self.custom_fields
        }


@dataclass
class AlertSource:
    """Source information for an alert."""
    name: str = ""
    type: str = ""  # exchange, system, strategy, etc.
    category: str = ""
    module: str = ""
    function: str = ""
    line: int = 0
    file: str = ""
    host: str = ""
    ip: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "category": self.category,
            "module": self.module,
            "function": self.function,
            "line": self.line,
            "file": self.file,
            "host": self.host,
            "ip": self.ip
        }


@dataclass
class AlertContext:
    """Contextual information for an alert."""
    symbol: str = ""
    exchange: str = ""
    market: str = ""
    order_id: str = ""
    trade_id: str = ""
    position_id: str = ""
    strategy: str = ""
    opportunity_id: str = ""
    pair: str = ""
    asset: str = ""
    amount: float = 0.0
    price: float = 0.0
    value: float = 0.0
    expected_value: float = 0.0
    actual_value: float = 0.0
    threshold: float = 0.0
    duration_ms: float = 0.0
    request_id: str = ""
    endpoint: str = ""
    status_code: int = 0
    error_message: str = ""
    stack_trace: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "market": self.market,
            "order_id": self.order_id,
            "trade_id": self.trade_id,
            "position_id": self.position_id,
            "strategy": self.strategy,
            "opportunity_id": self.opportunity_id,
            "pair": self.pair,
            "asset": self.asset,
            "amount": self.amount,
            "price": self.price,
            "value": self.value,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "threshold": self.threshold,
            "duration_ms": self.duration_ms,
            "request_id": self.request_id,
            "endpoint": self.endpoint,
            "status_code": self.status_code,
            "error_message": self.error_message,
            "stack_trace": self.stack_trace,
            "details": self.details,
            "extra": self.extra
        }


@dataclass
class Alert:
    """
    Main alert data model.
    Represents a single alert instance in the system.
    """
    # Core fields
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    description: str = ""
    severity: AlertSeverity = AlertSeverity.MEDIUM
    priority: AlertPriority = AlertPriority.P2
    category: AlertCategory = AlertCategory.SYSTEM
    status: AlertStatus = AlertStatus.PENDING
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    suppressed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    # Sources and context
    source: AlertSource = field(default_factory=AlertSource)
    context: AlertContext = field(default_factory=AlertContext)
    metadata: AlertMetadata = field(default_factory=AlertMetadata)
    
    # Grouping and correlation
    group_id: str = ""
    correlation_id: str = ""
    parent_id: Optional[str] = None
    child_ids: List[str] = field(default_factory=list)
    duplicate_ids: List[str] = field(default_factory=list)
    
    # Assignment
    assigned_to: str = ""
    assigned_team: str = ""
    assignee: str = ""
    
    # Escalation
    escalation_level: EscalationLevel = EscalationLevel.LEVEL_1
    escalation_count: int = 0
    last_escalated_at: Optional[datetime] = None
    
    # Aggregation
    aggregation_type: AlertAggregationType = AlertAggregationType.NONE
    aggregate_count: int = 0
    aggregate_key: str = ""
    
    # Metrics
    occurrence_count: int = 1
    first_occurrence: datetime = field(default_factory=datetime.utcnow)
    last_occurrence: datetime = field(default_factory=datetime.utcnow)
    
    # Actions
    actions: List[Dict[str, Any]] = field(default_factory=list)
    comments: List[Dict[str, Any]] = field(default_factory=list)
    
    # Notifications
    notifications_sent: Dict[str, datetime] = field(default_factory=dict)
    notification_channels: List[NotificationChannel] = field(default_factory=list)
    
    # Auto-resolution
    auto_resolve_enabled: bool = False
    auto_resolve_timeout: int = 300  # seconds
    auto_resolve_conditions: Dict[str, Any] = field(default_factory=dict)
    
    # Custom data
    custom_data: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization processing."""
        if not self.id:
            self.id = str(uuid4())
        if not self.created_at:
            self.created_at = datetime.utcnow()
        if not self.updated_at:
            self.updated_at = datetime.utcnow()
        if not self.first_occurrence:
            self.first_occurrence = datetime.utcnow()
        if not self.last_occurrence:
            self.last_occurrence = datetime.utcnow()
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value if self.severity else None,
            "priority": self.priority.value if self.priority else None,
            "category": self.category.value if self.category else None,
            "status": self.status.value if self.status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "escalated_at": self.escalated_at.isoformat() if self.escalated_at else None,
            "suppressed_at": self.suppressed_at.isoformat() if self.suppressed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "source": self.source.to_dict(),
            "context": self.context.to_dict(),
            "metadata": self.metadata.to_dict(),
            "group_id": self.group_id,
            "correlation_id": self.correlation_id,
            "parent_id": self.parent_id,
            "child_ids": self.child_ids,
            "duplicate_ids": self.duplicate_ids,
            "assigned_to": self.assigned_to,
            "assigned_team": self.assigned_team,
            "assignee": self.assignee,
            "escalation_level": self.escalation_level.value if self.escalation_level else None,
            "escalation_count": self.escalation_count,
            "last_escalated_at": self.last_escalated_at.isoformat() if self.last_escalated_at else None,
            "aggregation_type": self.aggregation_type.value if self.aggregation_type else None,
            "aggregate_count": self.aggregate_count,
            "aggregate_key": self.aggregate_key,
            "occurrence_count": self.occurrence_count,
            "first_occurrence": self.first_occurrence.isoformat() if self.first_occurrence else None,
            "last_occurrence": self.last_occurrence.isoformat() if self.last_occurrence else None,
            "actions": self.actions,
            "comments": self.comments,
            "notifications_sent": {k: v.isoformat() for k, v in self.notifications_sent.items()},
            "notification_channels": [c.value for c in self.notification_channels],
            "auto_resolve_enabled": self.auto_resolve_enabled,
            "auto_resolve_timeout": self.auto_resolve_timeout,
            "auto_resolve_conditions": self.auto_resolve_conditions,
            "custom_data": self.custom_data,
            "labels": self.labels,
            "annotations": self.annotations
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Alert":
        """Create alert from dictionary."""
        alert = cls()
        
        # Core fields
        alert.id = data.get("id", str(uuid4()))
        alert.title = data.get("title", "")
        alert.description = data.get("description", "")
        alert.severity = AlertSeverity(data.get("severity", "medium"))
        alert.priority = AlertPriority(data.get("priority", "p2"))
        alert.category = AlertCategory(data.get("category", "system"))
        alert.status = AlertStatus(data.get("status", "pending"))
        
        # Timestamps
        for field in ["created_at", "updated_at", "resolved_at", "acknowledged_at",
                     "escalated_at", "suppressed_at", "expires_at"]:
            if data.get(field):
                setattr(alert, field, datetime.fromisoformat(data[field]))
                
        # Source
        if data.get("source"):
            alert.source = AlertSource(**data["source"])
            
        # Context
        if data.get("context"):
            alert.context = AlertContext(**data["context"])
            
        # Metadata
        if data.get("metadata"):
            alert.metadata = AlertMetadata(**data["metadata"])
            
        # Grouping
        alert.group_id = data.get("group_id", "")
        alert.correlation_id = data.get("correlation_id", "")
        alert.parent_id = data.get("parent_id")
        alert.child_ids = data.get("child_ids", [])
        alert.duplicate_ids = data.get("duplicate_ids", [])
        
        # Assignment
        alert.assigned_to = data.get("assigned_to", "")
        alert.assigned_team = data.get("assigned_team", "")
        alert.assignee = data.get("assignee", "")
        
        # Escalation
        alert.escalation_level = EscalationLevel(data.get("escalation_level", "level_1"))
        alert.escalation_count = data.get("escalation_count", 0)
        if data.get("last_escalated_at"):
            alert.last_escalated_at = datetime.fromisoformat(data["last_escalated_at"])
            
        # Aggregation
        alert.aggregation_type = AlertAggregationType(data.get("aggregation_type", "none"))
        alert.aggregate_count = data.get("aggregate_count", 0)
        alert.aggregate_key = data.get("aggregate_key", "")
        
        # Occurrences
        alert.occurrence_count = data.get("occurrence_count", 1)
        if data.get("first_occurrence"):
            alert.first_occurrence = datetime.fromisoformat(data["first_occurrence"])
        if data.get("last_occurrence"):
            alert.last_occurrence = datetime.fromisoformat(data["last_occurrence"])
            
        # Actions and comments
        alert.actions = data.get("actions", [])
        alert.comments = data.get("comments", [])
        
        # Notifications
        alert.notifications_sent = {
            k: datetime.fromisoformat(v) for k, v in data.get("notifications_sent", {}).items()
        }
        alert.notification_channels = [
            NotificationChannel(c) for c in data.get("notification_channels", [])
        ]
        
        # Auto-resolution
        alert.auto_resolve_enabled = data.get("auto_resolve_enabled", False)
        alert.auto_resolve_timeout = data.get("auto_resolve_timeout", 300)
        alert.auto_resolve_conditions = data.get("auto_resolve_conditions", {})
        
        # Custom data
        alert.custom_data = data.get("custom_data", {})
        alert.labels = data.get("labels", {})
        alert.annotations = data.get("annotations", {})
        
        return alert
        
    def update(self, **kwargs) -> None:
        """Update alert fields."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()
        
    def acknowledge(self, user: str = "", comment: str = "") -> None:
        """Acknowledge the alert."""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.utcnow()
        self.assigned_to = user
        if comment:
            self.add_comment(user, comment, "acknowledge")
            
    def resolve(self, user: str = "", comment: str = "") -> None:
        """Resolve the alert."""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.utcnow()
        if comment:
            self.add_comment(user, comment, "resolve")
            
    def escalate(self, level: Optional[EscalationLevel] = None) -> None:
        """Escalate the alert."""
        if level:
            self.escalation_level = level
        self.escalation_count += 1
        self.last_escalated_at = datetime.utcnow()
        self.status = AlertStatus.ESCALATED
        
    def suppress(self, duration: int = 3600) -> None:
        """Suppress the alert for a duration."""
        self.status = AlertStatus.SUPPRESSED
        self.suppressed_at = datetime.utcnow()
        self.expires_at = datetime.utcnow() + timedelta(seconds=duration)
        
    def add_comment(self, user: str, comment: str, action: str = "comment") -> None:
        """Add a comment to the alert."""
        self.comments.append({
            "user": user,
            "comment": comment,
            "action": action,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    def increment_occurrence(self) -> None:
        """Increment the occurrence count."""
        self.occurrence_count += 1
        self.last_occurrence = datetime.utcnow()
        
    def is_expired(self) -> bool:
        """Check if the alert has expired."""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False
        
    def get_age(self) -> float:
        """Get the age of the alert in seconds."""
        return (datetime.utcnow() - self.created_at).total_seconds()
        
    def get_duration(self) -> float:
        """Get the duration since alert was created."""
        return self.get_age()
        
    def get_sla_breach_time(self) -> Optional[datetime]:
        """Get the SLA breach time based on priority."""
        sla_times = {
            AlertPriority.P0: timedelta(minutes=5),
            AlertPriority.P1: timedelta(minutes=15),
            AlertPriority.P2: timedelta(hours=1),
            AlertPriority.P3: timedelta(hours=4),
            AlertPriority.P4: timedelta(hours=24)
        }
        if self.priority in sla_times:
            return self.created_at + sla_times[self.priority]
        return None
        
    def is_sla_breached(self) -> bool:
        """Check if SLA has been breached."""
        breach_time = self.get_sla_breach_time()
        if breach_time:
            return datetime.utcnow() > breach_time
        return False


# ====================================================================================
# NOTIFICATION MODELS
# ====================================================================================

@dataclass
class Notification:
    """
    Notification data model.
    Represents a single notification sent for an alert.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    alert_id: str = ""
    channel: NotificationChannel = NotificationChannel.EMAIL
    recipient: str = ""
    subject: str = ""
    message: str = ""
    html_message: str = ""
    status: str = "pending"  # pending, sent, failed, delivered
    sent_at: Optional[datetime] = None
    error: str = ""
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "alert_id": self.alert_id,
            "channel": self.channel.value if self.channel else None,
            "recipient": self.recipient,
            "subject": self.subject,
            "message": self.message,
            "html_message": self.html_message,
            "status": self.status,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "error": self.error,
            "retry_count": self.retry_count,
            "metadata": self.metadata
        }


@dataclass
class NotificationTemplate:
    """
    Notification template for different alert types and channels.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    channel: NotificationChannel = NotificationChannel.EMAIL
    subject_template: str = ""
    body_template: str = ""
    html_template: str = ""
    variables: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def render(self, context: Dict[str, Any]) -> Dict[str, str]:
        """
        Render the template with the given context.
        
        Args:
            context: Template variables
            
        Returns:
            Rendered subject, body, and html
        """
        rendered = {}
        
        # Render subject
        rendered["subject"] = self._render_template(self.subject_template, context)
        
        # Render body
        rendered["body"] = self._render_template(self.body_template, context)
        
        # Render HTML
        if self.html_template:
            rendered["html"] = self._render_template(self.html_template, context)
        else:
            rendered["html"] = rendered["body"]
            
        return rendered
        
    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        """Render a template string with context."""
        result = template
        for key, value in context.items():
            placeholder = f"{{{{ {key} }}}}"
            result = result.replace(placeholder, str(value))
        return result


# ====================================================================================
# ESCALATION MODELS
# ====================================================================================

@dataclass
class EscalationRule:
    """
    Escalation rule for alert handling.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    conditions: Dict[str, Any] = field(default_factory=dict)
    escalation_level: EscalationLevel = EscalationLevel.LEVEL_1
    delay_minutes: int = 5
    max_escalations: int = 3
    notify_on_escalation: bool = True
    channels: List[NotificationChannel] = field(default_factory=list)
    recipients: List[str] = field(default_factory=list)
    
    def matches(self, alert: Alert) -> bool:
        """
        Check if this rule matches the given alert.
        
        Args:
            alert: Alert to check
            
        Returns:
            True if rule matches
        """
        for key, value in self.conditions.items():
            if key == "severity":
                if alert.severity != AlertSeverity(value):
                    return False
            elif key == "category":
                if alert.category != AlertCategory(value):
                    return False
            elif key == "priority":
                if alert.priority != AlertPriority(value):
                    return False
            elif hasattr(alert, key):
                if getattr(alert, key) != value:
                    return False
        return True


@dataclass
class EscalationPolicy:
    """
    Escalation policy for incident response.
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    rules: List[EscalationRule] = field(default_factory=list)
    default_escalation_level: EscalationLevel = EscalationLevel.LEVEL_1
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def get_escalation_rule(self, alert: Alert) -> Optional[EscalationRule]:
        """
        Get the matching escalation rule for an alert.
        
        Args:
            alert: Alert to check
            
        Returns:
            Matching rule or None
        """
        for rule in self.rules:
            if rule.matches(alert):
                return rule
        return None


# ====================================================================================
# ALERT AGGREGATION MODELS
# ====================================================================================

@dataclass
class AlertAggregationConfig:
    """Configuration for alert aggregation."""
    enabled: bool = True
    aggregation_type: AlertAggregationType = AlertAggregationType.DEDUPLICATE
    window_seconds: int = 60
    max_alerts_per_window: int = 10
    group_by_fields: List[str] = field(default_factory=list)
    deduplicate_fields: List[str] = field(default_factory=list)
    throttle_seconds: int = 30
    max_aggregate_count: int = 100


@dataclass
class AlertGroup:
    """Group of related alerts."""
    id: str = field(default_factory=lambda: str(uuid4()))
    group_key: str = ""
    alerts: List[Alert] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    status: AlertStatus = AlertStatus.PENDING
    severity: AlertSeverity = AlertSeverity.MEDIUM
    count: int = 0
    
    def add_alert(self, alert: Alert) -> None:
        """Add an alert to the group."""
        self.alerts.append(alert)
        self.count = len(self.alerts)
        self.updated_at = datetime.utcnow()
        
        # Update severity based on highest in group
        severities = [AlertSeverity(a.severity) for a in self.alerts if a.severity]
        severity_order = [AlertSeverity.CRITICAL, AlertSeverity.HIGH, 
                         AlertSeverity.MEDIUM, AlertSeverity.LOW, AlertSeverity.INFO]
        for sev in severity_order:
            if sev in severities:
                self.severity = sev
                break
                
    def resolve(self) -> None:
        """Resolve the entire group."""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.utcnow()
        for alert in self.alerts:
            if alert.status not in [AlertStatus.RESOLVED, AlertStatus.CLOSED]:
                alert.resolve()


# ====================================================================================
# ALERT REPORTING MODELS
# ====================================================================================

@dataclass
class AlertStats:
    """Statistics about alerts."""
    total: int = 0
    by_severity: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    by_status: Dict[str, int] = field(default_factory=dict)
    by_priority: Dict[str, int] = field(default_factory=dict)
    average_resolution_time: float = 0.0
    sla_breach_count: int = 0
    escalation_count: int = 0
    resolution_rate: float = 0.0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total": self.total,
            "by_severity": self.by_severity,
            "by_category": self.by_category,
            "by_status": self.by_status,
            "by_priority": self.by_priority,
            "average_resolution_time": self.average_resolution_time,
            "sla_breach_count": self.sla_breach_count,
            "escalation_count": self.escalation_count,
            "resolution_rate": self.resolution_rate,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None
        }


@dataclass
class AlertReport:
    """Comprehensive alert report."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    generated_at: datetime = field(default_factory=datetime.utcnow)
    stats: AlertStats = field(default_factory=AlertStats)
    top_alerts: List[Alert] = field(default_factory=list)
    trends: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "stats": self.stats.to_dict(),
            "top_alerts": [a.to_dict() for a in self.top_alerts[:10]],
            "trends": self.trends,
            "recommendations": self.recommendations
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def create_alert(
    title: str,
    description: str,
    severity: AlertSeverity = AlertSeverity.MEDIUM,
    category: AlertCategory = AlertCategory.SYSTEM,
    source: Optional[AlertSource] = None,
    context: Optional[AlertContext] = None,
    **kwargs
) -> Alert:
    """
    Create a new alert with the given parameters.
    
    Args:
        title: Alert title
        description: Alert description
        severity: Alert severity
        category: Alert category
        source: Alert source
        context: Alert context
        **kwargs: Additional alert fields
        
    Returns:
        New Alert instance
    """
    alert = Alert(
        title=title,
        description=description,
        severity=severity,
        category=category,
        source=source or AlertSource(),
        context=context or AlertContext()
    )
    
    # Set additional fields
    for key, value in kwargs.items():
        if hasattr(alert, key):
            setattr(alert, key, value)
            
    return alert


def create_critical_alert(
    title: str,
    description: str,
    category: AlertCategory = AlertCategory.SYSTEM,
    **kwargs
) -> Alert:
    """Create a critical alert."""
    return create_alert(
        title=title,
        description=description,
        severity=AlertSeverity.CRITICAL,
        priority=AlertPriority.P0,
        category=category,
        **kwargs
    )


def create_high_alert(
    title: str,
    description: str,
    category: AlertCategory = AlertCategory.SYSTEM,
    **kwargs
) -> Alert:
    """Create a high priority alert."""
    return create_alert(
        title=title,
        description=description,
        severity=AlertSeverity.HIGH,
        priority=AlertPriority.P1,
        category=category,
        **kwargs
    )


def create_info_alert(
    title: str,
    description: str,
    category: AlertCategory = AlertCategory.SYSTEM,
    **kwargs
) -> Alert:
    """Create an informational alert."""
    return create_alert(
        title=title,
        description=description,
        severity=AlertSeverity.INFO,
        priority=AlertPriority.P4,
        category=category,
        **kwargs
    )


def create_trading_alert(
    title: str,
    description: str,
    severity: AlertSeverity = AlertSeverity.HIGH,
    symbol: str = "",
    exchange: str = "",
    order_id: str = "",
    **kwargs
) -> Alert:
    """Create a trading-related alert."""
    context = AlertContext(
        symbol=symbol,
        exchange=exchange,
        order_id=order_id,
        **kwargs.pop("context", {})
    )
    return create_alert(
        title=title,
        description=description,
        severity=severity,
        category=AlertCategory.TRADING,
        context=context,
        **kwargs
    )


def create_exchange_alert(
    title: str,
    description: str,
    severity: AlertSeverity = AlertSeverity.HIGH,
    exchange: str = "",
    endpoint: str = "",
    status_code: int = 0,
    **kwargs
) -> Alert:
    """Create an exchange-related alert."""
    context = AlertContext(
        exchange=exchange,
        endpoint=endpoint,
        status_code=status_code,
        **kwargs.pop("context", {})
    )
    return create_alert(
        title=title,
        description=description,
        severity=severity,
        category=AlertCategory.EXCHANGE,
        context=context,
        **kwargs
    )


def create_opportunity_alert(
    title: str,
    description: str,
    severity: AlertSeverity = AlertSeverity.INFO,
    symbol: str = "",
    exchange: str = "",
    profit_percent: float = 0.0,
    **kwargs
) -> Alert:
    """Create an opportunity-related alert."""
    context = AlertContext(
        symbol=symbol,
        exchange=exchange,
        **kwargs.pop("context", {})
    )
    return create_alert(
        title=title,
        description=description,
        severity=severity,
        category=AlertCategory.OPPORTUNITY,
        context=context,
        **kwargs
    )


def create_security_alert(
    title: str,
    description: str,
    severity: AlertSeverity = AlertSeverity.CRITICAL,
    **kwargs
) -> Alert:
    """Create a security-related alert."""
    return create_alert(
        title=title,
        description=description,
        severity=severity,
        priority=AlertPriority.P0,
        category=AlertCategory.SECURITY,
        **kwargs
    )


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'AlertSeverity',
    'AlertCategory',
    'AlertStatus',
    'AlertPriority',
    'NotificationChannel',
    'AlertAction',
    'EscalationLevel',
    'AlertAggregationType',
    'IncidentSeverity',
    
    # Core Models
    'Alert',
    'AlertMetadata',
    'AlertSource',
    'AlertContext',
    'AlertStats',
    'AlertReport',
    
    # Notification Models
    'Notification',
    'NotificationTemplate',
    
    # Escalation Models
    'EscalationRule',
    'EscalationPolicy',
    
    # Aggregation Models
    'AlertAggregationConfig',
    'AlertGroup',
    
    # Helper Functions
    'create_alert',
    'create_critical_alert',
    'create_high_alert',
    'create_info_alert',
    'create_trading_alert',
    'create_exchange_alert',
    'create_opportunity_alert',
    'create_security_alert',
]
