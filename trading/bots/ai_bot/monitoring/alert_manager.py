"""
NEXUS AI TRADING SYSTEM - Alert Manager
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced alert management system for monitoring trading bots, models,
and system health with multi-channel notifications, escalation policies,
and intelligent alert correlation.
"""

import asyncio
import json
import smtplib
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import aiohttp
import yaml
from prometheus_client import Counter, Gauge, Histogram
from pydantic import BaseModel, Field, validator

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
ALERT_COUNTER = Counter(
    "nexus_alerts_total",
    "Total number of alerts generated",
    ["severity", "status", "type"],
)
ALERT_RESOLUTION_TIME = Histogram(
    "nexus_alert_resolution_time_seconds",
    "Time taken to resolve alerts",
    ["severity"],
)
ALERT_ESCALATION_COUNTER = Counter(
    "nexus_alert_escalations_total",
    "Total number of alert escalations",
    ["severity"],
)
ACTIVE_ALERTS = Gauge(
    "nexus_active_alerts",
    "Number of currently active alerts",
    ["severity"],
)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(Enum):
    """Alert status states."""

    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"
    ESCALATED = "escalated"


class AlertCategory(Enum):
    """Alert categories."""

    SYSTEM = "system"
    TRADING = "trading"
    MODEL = "model"
    DATA = "data"
    BROKER = "broker"
    RISK = "risk"
    PERFORMANCE = "performance"
    SECURITY = "security"
    BOT = "bot"


class ChannelType(Enum):
    """Notification channel types."""

    EMAIL = "email"
    SLACK = "slack"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SMS = "sms"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"
    OPSGENIE = "opsgenie"
    PUSHOVER = "pushover"
    TWILIO = "twilio"


@dataclass
class AlertRule:
    """Alert rule definition."""

    id: str
    name: str
    description: str
    severity: AlertSeverity
    category: AlertCategory
    condition: Dict[str, Any]
    enabled: bool = True
    cooldown_seconds: int = 300
    escalation_after_seconds: int = 600
    auto_resolve_seconds: int = 3600
    channels: List[ChannelType] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "category": self.category.value,
            "condition": self.condition,
            "enabled": self.enabled,
            "cooldown_seconds": self.cooldown_seconds,
            "escalation_after_seconds": self.escalation_after_seconds,
            "auto_resolve_seconds": self.auto_resolve_seconds,
            "channels": [c.value for c in self.channels],
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlertRule":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            severity=AlertSeverity(data["severity"]),
            category=AlertCategory(data["category"]),
            condition=data["condition"],
            enabled=data.get("enabled", True),
            cooldown_seconds=data.get("cooldown_seconds", 300),
            escalation_after_seconds=data.get("escalation_after_seconds", 600),
            auto_resolve_seconds=data.get("auto_resolve_seconds", 3600),
            channels=[ChannelType(c) for c in data.get("channels", [])],
            tags=data.get("tags", []),
        )


@dataclass
class Alert:
    """Alert instance."""

    id: str
    rule_id: str
    severity: AlertSeverity
    category: AlertCategory
    title: str
    message: str
    status: AlertStatus = AlertStatus.NEW
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    escalation_count: int = 0
    notification_count: int = 0
    related_alerts: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    source: str = ""
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "category": self.category.value,
            "title": self.title,
            "message": self.message,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "escalated_at": self.escalated_at.isoformat() if self.escalated_at else None,
            "escalation_count": self.escalation_count,
            "notification_count": self.notification_count,
            "related_alerts": self.related_alerts,
            "data": self.data,
            "tags": self.tags,
            "source": self.source,
            "resolved_by": self.resolved_by,
            "resolution_note": self.resolution_note,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Alert":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            rule_id=data["rule_id"],
            severity=AlertSeverity(data["severity"]),
            category=AlertCategory(data["category"]),
            title=data["title"],
            message=data["message"],
            status=AlertStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            acknowledged_at=datetime.fromisoformat(data["acknowledged_at"]) if data.get("acknowledged_at") else None,
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            escalated_at=datetime.fromisoformat(data["escalated_at"]) if data.get("escalated_at") else None,
            escalation_count=data.get("escalation_count", 0),
            notification_count=data.get("notification_count", 0),
            related_alerts=data.get("related_alerts", []),
            data=data.get("data", {}),
            tags=data.get("tags", []),
            source=data.get("source", ""),
            resolved_by=data.get("resolved_by"),
            resolution_note=data.get("resolution_note"),
        )


@dataclass
class NotificationConfig:
    """Notification channel configuration."""

    channel: ChannelType
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)


class AlertManager:
    """
    Advanced alert management system with multi-channel notifications.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the alert manager.

        Args:
            config: Configuration dictionary
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
        """
        self.config = config or {}
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._lock = asyncio.Lock()
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: Dict[str, Alert] = {}
        self._last_notifications: Dict[str, datetime] = {}
        self._notification_tasks: Set[asyncio.Task] = set()
        self._escalation_task: Optional[asyncio.Task] = None
        self._auto_resolve_task: Optional[asyncio.Task] = None
        self._handlers: Dict[ChannelType, Callable] = {}

        # Load configuration
        self.alert_config = self.config.get("alert_manager", {})
        self.rules_file = Path(self.alert_config.get("rules_file", "./configs/alerts/rules.yaml"))
        self.enable_auto_escalation = self.alert_config.get("enable_auto_escalation", True)
        self.enable_auto_resolve = self.alert_config.get("enable_auto_resolve", True)
        self.max_alert_age_days = self.alert_config.get("max_alert_age_days", 7)
        self.max_alerts_per_rule = self.alert_config.get("max_alerts_per_rule", 100)

        # Load notification configs
        self.notifications = self._load_notification_configs()

        # Load rules
        self._load_rules()

        # Start background tasks
        self._start_background_tasks()

        logger.info("AlertManager initialized with %d rules", len(self._rules))

    def _start_background_tasks(self):
        """Start background tasks."""
        if self.enable_auto_escalation and self._escalation_task is None:
            self._escalation_task = asyncio.create_task(
                self._escalation_loop()
            )

        if self.enable_auto_resolve and self._auto_resolve_task is None:
            self._auto_resolve_task = asyncio.create_task(
                self._auto_resolve_loop()
            )

    def _load_rules(self):
        """Load alert rules from configuration."""
        try:
            if self.rules_file.exists():
                with open(self.rules_file, "r") as f:
                    data = yaml.safe_load(f)
                    for rule_data in data.get("rules", []):
                        rule = AlertRule.from_dict(rule_data)
                        self._rules[rule.id] = rule
                logger.info(f"Loaded {len(self._rules)} alert rules from {self.rules_file}")
            else:
                # Load default rules
                self._load_default_rules()
        except Exception as e:
            logger.error(f"Error loading alert rules: {e}")
            self._load_default_rules()

    def _load_default_rules(self):
        """Load default alert rules."""
        default_rules = [
            AlertRule(
                id="system_cpu_high",
                name="High CPU Usage",
                description="CPU usage exceeds threshold",
                severity=AlertSeverity.WARNING,
                category=AlertCategory.SYSTEM,
                condition={"metric": "cpu_usage", "operator": ">", "threshold": 80},
                channels=[ChannelType.EMAIL, ChannelType.SLACK],
            ),
            AlertRule(
                id="system_memory_high",
                name="High Memory Usage",
                description="Memory usage exceeds threshold",
                severity=AlertSeverity.WARNING,
                category=AlertCategory.SYSTEM,
                condition={"metric": "memory_usage", "operator": ">", "threshold": 85},
                channels=[ChannelType.EMAIL, ChannelType.SLACK],
            ),
            AlertRule(
                id="trading_position_loss",
                name="Position Loss Exceeded",
                description="Trading position loss exceeds configured limit",
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.TRADING,
                condition={"metric": "position_pnl", "operator": "<", "threshold": -1000},
                channels=[ChannelType.EMAIL, ChannelType.SLACK, ChannelType.PAGERDUTY],
            ),
            AlertRule(
                id="model_accuracy_drop",
                name="Model Accuracy Drop",
                description="Model prediction accuracy has dropped significantly",
                severity=AlertSeverity.WARNING,
                category=AlertCategory.MODEL,
                condition={"metric": "model_accuracy", "operator": "<", "threshold": 0.6},
                channels=[ChannelType.EMAIL, ChannelType.SLACK],
            ),
            AlertRule(
                id="broker_connection_failed",
                name="Broker Connection Failed",
                description="Failed to connect to broker API",
                severity=AlertSeverity.ERROR,
                category=AlertCategory.BROKER,
                condition={"metric": "broker_connected", "operator": "==", "threshold": False},
                channels=[ChannelType.EMAIL, ChannelType.SLACK, ChannelType.TELEGRAM],
            ),
            AlertRule(
                id="risk_limit_breached",
                name="Risk Limit Breached",
                description="Portfolio risk limit has been breached",
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.RISK,
                condition={"metric": "risk_exposure", "operator": ">", "threshold": 0.2},
                channels=[ChannelType.EMAIL, ChannelType.PAGERDUTY, ChannelType.OPSGENIE],
            ),
        ]

        for rule in default_rules:
            self._rules[rule.id] = rule

        logger.info(f"Loaded {len(self._rules)} default alert rules")

    def _load_notification_configs(self) -> Dict[ChannelType, NotificationConfig]:
        """Load notification channel configurations."""
        configs = {}
        notification_config = self.alert_config.get("notifications", {})

        for channel in ChannelType:
            channel_config = notification_config.get(channel.value, {})
            if channel_config.get("enabled", False):
                configs[channel] = NotificationConfig(
                    channel=channel,
                    enabled=True,
                    config=channel_config.get("config", {}),
                )

        return configs

    async def evaluate_rule(
        self,
        rule_id: str,
        metrics: Dict[str, Any],
        source: str = "",
    ) -> Optional[Alert]:
        """
        Evaluate a single alert rule.

        Args:
            rule_id: Rule to evaluate
            metrics: Metrics to evaluate against
            source: Source of the metrics

        Returns:
            Alert if triggered, None otherwise
        """
        rule = self._rules.get(rule_id)

        if not rule or not rule.enabled:
            return None

        # Check cooldown
        if rule_id in self._last_notifications:
            cooldown_remaining = (
                self._last_notifications[rule_id]
                + timedelta(seconds=rule.cooldown_seconds)
                - datetime.utcnow()
            )
            if cooldown_remaining.total_seconds() > 0:
                return None

        # Check if rule condition is met
        if not self._check_condition(rule.condition, metrics):
            return None

        # Create alert
        alert = Alert(
            id=f"{rule_id}_{int(time.time())}",
            rule_id=rule.id,
            severity=rule.severity,
            category=rule.category,
            title=rule.name,
            message=self._format_alert_message(rule, metrics),
            tags=rule.tags,
            source=source,
            data=metrics,
        )

        # Store alert
        async with self._lock:
            self._alerts[alert.id] = alert

        # Send notifications
        await self._send_notifications(alert)

        # Update metrics
        ACTIVE_ALERTS.labels(severity=rule.severity.value).inc()
        ALERT_COUNTER.labels(
            severity=rule.severity.value,
            status=AlertStatus.NEW.value,
            type=rule.category.value,
        ).inc()

        # Update last notification time
        self._last_notifications[rule_id] = datetime.utcnow()

        logger.info(f"Alert triggered: {alert.title} ({alert.severity.value})")

        return alert

    async def evaluate_rules(
        self,
        metrics: Dict[str, Any],
        source: str = "",
    ) -> List[Alert]:
        """
        Evaluate all alert rules.

        Args:
            metrics: Metrics to evaluate against
            source: Source of the metrics

        Returns:
            List of triggered alerts
        """
        triggered_alerts = []

        for rule_id in self._rules:
            alert = await self.evaluate_rule(rule_id, metrics, source)
            if alert:
                triggered_alerts.append(alert)

        return triggered_alerts

    def _check_condition(
        self,
        condition: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> bool:
        """
        Check if condition is met.

        Args:
            condition: Condition to check
            metrics: Metrics to evaluate

        Returns:
            True if condition is met
        """
        metric_name = condition.get("metric")
        operator = condition.get("operator")
        threshold = condition.get("threshold")

        if metric_name not in metrics:
            return False

        value = metrics[metric_name]

        if operator == ">":
            return value > threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<":
            return value < threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return value == threshold
        elif operator == "!=":
            return value != threshold
        elif operator == "in":
            return value in threshold
        elif operator == "not_in":
            return value not in threshold
        elif operator == "contains":
            return threshold in value
        else:
            return False

    def _format_alert_message(
        self,
        rule: AlertRule,
        metrics: Dict[str, Any],
    ) -> str:
        """Format alert message."""
        message = f"Rule: {rule.name}\n"
        message += f"Description: {rule.description}\n"
        message += f"Severity: {rule.severity.value}\n"
        message += f"Condition: {rule.condition}\n\n"

        message += "Current Metrics:\n"
        for key, value in metrics.items():
            message += f"  {key}: {value}\n"

        return message

    async def _send_notifications(self, alert: Alert):
        """
        Send notifications for an alert.

        Args:
            alert: Alert to notify about
        """
        # Determine channels
        rule = self._rules.get(alert.rule_id)
        if not rule:
            return

        channels = rule.channels

        # Add severity-based overrides
        if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]:
            if ChannelType.PAGERDUTY not in channels:
                channels.append(ChannelType.PAGERDUTY)

        # Send to each channel
        for channel in channels:
            if channel not in self.notifications or not self.notifications[channel].enabled:
                continue

            try:
                task = asyncio.create_task(
                    self._send_notification(channel, alert)
                )
                self._notification_tasks.add(task)
                task.add_done_callback(self._notification_tasks.discard)
                alert.notification_count += 1
            except Exception as e:
                logger.error(f"Error sending notification to {channel.value}: {e}")

    async def _send_notification(self, channel: ChannelType, alert: Alert):
        """
        Send notification to a specific channel.

        Args:
            channel: Channel to send to
            alert: Alert to send
        """
        config = self.notifications.get(channel)

        if not config:
            return

        if channel == ChannelType.EMAIL:
            await self._send_email(alert, config.config)
        elif channel == ChannelType.SLACK:
            await self._send_slack(alert, config.config)
        elif channel == ChannelType.TELEGRAM:
            await self._send_telegram(alert, config.config)
        elif channel == ChannelType.DISCORD:
            await self._send_discord(alert, config.config)
        elif channel == ChannelType.PAGERDUTY:
            await self._send_pagerduty(alert, config.config)
        elif channel == ChannelType.OPSGENIE:
            await self._send_opsgenie(alert, config.config)
        elif channel == ChannelType.WEBHOOK:
            await self._send_webhook(alert, config.config)
        elif channel == ChannelType.SMS:
            await self._send_sms(alert, config.config)
        elif channel == ChannelType.PUSHOVER:
            await self._send_pushover(alert, config.config)

    async def _send_email(self, alert: Alert, config: Dict[str, Any]):
        """Send email notification."""
        try:
            smtp_server = config.get("smtp_server")
            smtp_port = config.get("smtp_port", 587)
            username = config.get("username")
            password = config.get("password")
            from_email = config.get("from_email")
            to_emails = config.get("to_emails", [])

            msg = MIMEMultipart()
            msg["From"] = from_email
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = f"[{alert.severity.value.upper()}] {alert.title}"

            body = f"""
            Alert Details:
            =============
            ID: {alert.id}
            Title: {alert.title}
            Severity: {alert.severity.value}
            Category: {alert.category.value}
            Time: {alert.created_at}
            Source: {alert.source}

            Message:
            {alert.message}

            Data:
            {json.dumps(alert.data, indent=2)}
            """

            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(username, password)
                server.send_message(msg)

            logger.debug(f"Email notification sent for alert {alert.id}")

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")

    async def _send_slack(self, alert: Alert, config: Dict[str, Any]):
        """Send Slack notification."""
        try:
            webhook_url = config.get("webhook_url")
            channel = config.get("channel")

            # Determine color based on severity
            color_map = {
                AlertSeverity.INFO: "#36a64f",
                AlertSeverity.WARNING: "#ffcc00",
                AlertSeverity.ERROR: "#ff6600",
                AlertSeverity.CRITICAL: "#ff0000",
                AlertSeverity.EMERGENCY: "#990000",
            }

            color = color_map.get(alert.severity, "#36a64f")

            payload = {
                "channel": channel,
                "attachments": [
                    {
                        "color": color,
                        "title": f"[{alert.severity.value.upper()}] {alert.title}",
                        "text": alert.message,
                        "fields": [
                            {
                                "title": "Category",
                                "value": alert.category.value,
                                "short": True,
                            },
                            {
                                "title": "Source",
                                "value": alert.source or "Unknown",
                                "short": True,
                            },
                            {
                                "title": "Time",
                                "value": alert.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                                "short": True,
                            },
                            {
                                "title": "ID",
                                "value": alert.id,
                                "short": True,
                            },
                        ],
                        "footer": "Nexus AI Trading System",
                        "ts": int(time.time()),
                    }
                ],
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"Slack webhook returned {response.status}")

            logger.debug(f"Slack notification sent for alert {alert.id}")

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")

    async def _send_telegram(self, alert: Alert, config: Dict[str, Any]):
        """Send Telegram notification."""
        try:
            bot_token = config.get("bot_token")
            chat_id = config.get("chat_id")

            message = f"""
⚠️ *[{alert.severity.value.upper()}] {alert.title}*

📋 *Message:*
{alert.message}

📂 *Category:* {alert.category.value}
🆔 *ID:* {alert.id}
⏰ *Time:* {alert.created_at.strftime("%Y-%m-%d %H:%M:%S")}
🔗 *Source:* {alert.source or "Unknown"}

📊 *Data:*
```json
{json.dumps(alert.data, indent=2)[:500]}
```
"""

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"Telegram API returned {response.status}")

            logger.debug(f"Telegram notification sent for alert {alert.id}")

        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")

    async def _send_discord(self, alert: Alert, config: Dict[str, Any]):
        """Send Discord notification."""
        try:
            webhook_url = config.get("webhook_url")
            username = config.get("username", "Nexus Alerts")

            # Determine color based on severity
            color_map = {
                AlertSeverity.INFO: 3066993,
                AlertSeverity.WARNING: 16776960,
                AlertSeverity.ERROR: 15105570,
                AlertSeverity.CRITICAL: 15158332,
                AlertSeverity.EMERGENCY: 10038562,
            }

            color = color_map.get(alert.severity, 3066993)

            payload = {
                "username": username,
                "embeds": [
                    {
                        "title": f"[{alert.severity.value.upper()}] {alert.title}",
                        "description": alert.message[:2000],
                        "color": color,
                        "fields": [
                            {
                                "name": "Category",
                                "value": alert.category.value,
                                "inline": True,
                            },
                            {
                                "name": "Source",
                                "value": alert.source or "Unknown",
                                "inline": True,
                            },
                            {
                                "name": "Time",
                                "value": alert.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                                "inline": True,
                            },
                        ],
                        "footer": {"text": f"Alert ID: {alert.id}"},
                        "timestamp": alert.created_at.isoformat(),
                    }
                ],
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status != 204:
                        logger.error(f"Discord webhook returned {response.status}")

            logger.debug(f"Discord notification sent for alert {alert.id}")

        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")

    async def _send_pagerduty(self, alert: Alert, config: Dict[str, Any]):
        """Send PagerDuty notification."""
        try:
            integration_key = config.get("integration_key")
            service_key = config.get("service_key")

            # Determine urgency based on severity
            urgency = "high" if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY] else "low"

            payload = {
                "payload": {
                    "summary": f"[{alert.severity.value.upper()}] {alert.title}",
                    "source": alert.source or "Nexus AI Trading System",
                    "severity": alert.severity.value,
                    "timestamp": alert.created_at.isoformat(),
                    "component": alert.category.value,
                    "group": "trading",
                    "class": "alert",
                    "custom_details": {
                        "alert_id": alert.id,
                        "rule_id": alert.rule_id,
                        "message": alert.message,
                        "data": alert.data,
                    },
                },
                "routing_key": integration_key or service_key,
                "event_action": "trigger",
                "dedup_key": f"nexus_{alert.id}",
            }

            url = "https://events.pagerduty.com/v2/enqueue"
            headers = {"Content-Type": "application/json"}

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status != 202:
                        logger.error(f"PagerDuty API returned {response.status}")

            logger.debug(f"PagerDuty notification sent for alert {alert.id}")

        except Exception as e:
            logger.error(f"Failed to send PagerDuty notification: {e}")

    async def _send_opsgenie(self, alert: Alert, config: Dict[str, Any]):
        """Send OpsGenie notification."""
        try:
            api_key = config.get("api_key")
            integration_key = config.get("integration_key")

            # Determine priority based on severity
            priority_map = {
                AlertSeverity.INFO: "P4",
                AlertSeverity.WARNING: "P3",
                AlertSeverity.ERROR: "P2",
                AlertSeverity.CRITICAL: "P1",
                AlertSeverity.EMERGENCY: "P1",
            }

            priority = priority_map.get(alert.severity, "P3")

            payload = {
                "message": f"[{alert.severity.value.upper()}] {alert.title}",
                "alias": f"nexus_{alert.id}",
                "description": alert.message,
                "priority": priority,
                "source": alert.source or "Nexus AI Trading System",
                "tags": [alert.category.value] + alert.tags,
                "details": {
                    "alert_id": alert.id,
                    "rule_id": alert.rule_id,
                    "data": alert.data,
                },
            }

            url = "https://api.opsgenie.com/v2/alerts"
            headers = {
                "Authorization": f"GenieKey {api_key or integration_key}",
                "Content-Type": "application/json",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status not in [202, 201]:
                        logger.error(f"OpsGenie API returned {response.status}")

            logger.debug(f"OpsGenie notification sent for alert {alert.id}")

        except Exception as e:
            logger.error(f"Failed to send OpsGenie notification: {e}")

    async def _send_webhook(self, alert: Alert, config: Dict[str, Any]):
        """Send webhook notification."""
        try:
            webhook_url = config.get("webhook_url")
            method = config.get("method", "POST")
            headers = config.get("headers", {})

            payload = alert.to_dict()

            async with aiohttp.ClientSession() as session:
                async with session.request(method, webhook_url, json=payload, headers=headers) as response:
                    if response.status >= 400:
                        logger.error(f"Webhook returned {response.status}")

            logger.debug(f"Webhook notification sent for alert {alert.id}")

        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")

    async def _send_sms(self, alert: Alert, config: Dict[str, Any]):
        """Send SMS notification via Twilio."""
        try:
            account_sid = config.get("account_sid")
            auth_token = config.get("auth_token")
            from_number = config.get("from_number")
            to_numbers = config.get("to_numbers", [])

            if not to_numbers:
                return

            message = f"[{alert.severity.value.upper()}] {alert.title}: {alert.message[:140]}"

            # This is a simplified implementation
            # In production, use Twilio's async client
            logger.info(f"SMS notification would be sent to {to_numbers}: {message}")

        except Exception as e:
            logger.error(f"Failed to send SMS notification: {e}")

    async def _send_pushover(self, alert: Alert, config: Dict[str, Any]):
        """Send Pushover notification."""
        try:
            api_token = config.get("api_token")
            user_key = config.get("user_key")

            # Determine priority based on severity
            priority_map = {
                AlertSeverity.INFO: -1,
                AlertSeverity.WARNING: 0,
                AlertSeverity.ERROR: 1,
                AlertSeverity.CRITICAL: 2,
                AlertSeverity.EMERGENCY: 2,
            }

            priority = priority_map.get(alert.severity, 0)

            payload = {
                "token": api_token,
                "user": user_key,
                "title": f"[{alert.severity.value.upper()}] {alert.title}",
                "message": alert.message[:500],
                "priority": priority,
                "timestamp": int(time.time()),
            }

            url = "https://api.pushover.net/1/messages.json"

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload) as response:
                    if response.status != 200:
                        logger.error(f"Pushover API returned {response.status}")

            logger.debug(f"Pushover notification sent for alert {alert.id}")

        except Exception as e:
            logger.error(f"Failed to send Pushover notification: {e}")

    async def acknowledge_alert(
        self,
        alert_id: str,
        user: str = "",
        note: str = "",
    ) -> bool:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert ID
            user: User acknowledging the alert
            note: Acknowledgment note

        Returns:
            True if acknowledged
        """
        async with self._lock:
            if alert_id not in self._alerts:
                return False

            alert = self._alerts[alert_id]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.utcnow()
            alert.updated_at = datetime.utcnow()
            alert.data["acknowledged_by"] = user
            alert.data["acknowledgment_note"] = note

            ACTIVE_ALERTS.labels(severity=alert.severity.value).dec()
            ALERT_COUNTER.labels(
                severity=alert.severity.value,
                status=AlertStatus.ACKNOWLEDGED.value,
                type=alert.category.value,
            ).inc()

            logger.info(f"Alert {alert_id} acknowledged by {user}")

            return True

    async def resolve_alert(
        self,
        alert_id: str,
        user: str = "",
        note: str = "",
    ) -> bool:
        """
        Resolve an alert.

        Args:
            alert_id: Alert ID
            user: User resolving the alert
            note: Resolution note

        Returns:
            True if resolved
        """
        async with self._lock:
            if alert_id not in self._alerts:
                return False

            alert = self._alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.utcnow()
            alert.updated_at = datetime.utcnow()
            alert.resolved_by = user
            alert.resolution_note = note

            # Track resolution time
            resolution_time = (
                alert.resolved_at - alert.created_at
            ).total_seconds()
            ALERT_RESOLUTION_TIME.labels(
                severity=alert.severity.value
            ).observe(resolution_time)

            ACTIVE_ALERTS.labels(severity=alert.severity.value).dec()
            ALERT_COUNTER.labels(
                severity=alert.severity.value,
                status=AlertStatus.RESOLVED.value,
                type=alert.category.value,
            ).inc()

            logger.info(f"Alert {alert_id} resolved by {user}: {note}")

            return True

    async def _escalation_loop(self):
        """Background task for alert escalation."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                async with self._lock:
                    for alert in self._alerts.values():
                        if alert.status in [AlertStatus.NEW, AlertStatus.ACKNOWLEDGED]:
                            rule = self._rules.get(alert.rule_id)

                            if not rule:
                                continue

                            # Check if escalation is needed
                            elapsed = (
                                datetime.utcnow() - alert.created_at
                            ).total_seconds()

                            if elapsed > rule.escalation_after_seconds:
                                alert.escalation_count += 1
                                alert.status = AlertStatus.ESCALATED
                                alert.escalated_at = datetime.utcnow()

                                # Resend notifications with escalation flag
                                alert.data["escalated"] = True
                                alert.data["escalation_count"] = alert.escalation_count

                                await self._send_notifications(alert)

                                ALERT_ESCALATION_COUNTER.labels(
                                    severity=alert.severity.value
                                ).inc()

                                logger.info(
                                    f"Alert {alert.id} escalated "
                                    f"(count: {alert.escalation_count})"
                                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in escalation loop: {e}")
                await asyncio.sleep(10)

    async def _auto_resolve_loop(self):
        """Background task for auto-resolution."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes

                async with self._lock:
                    for alert in list(self._alerts.values()):
                        if alert.status in [AlertStatus.NEW, AlertStatus.ACKNOWLEDGED, AlertStatus.INVESTIGATING]:
                            rule = self._rules.get(alert.rule_id)

                            if not rule or rule.auto_resolve_seconds == 0:
                                continue

                            # Check if auto-resolution should trigger
                            elapsed = (
                                datetime.utcnow() - alert.created_at
                            ).total_seconds()

                            if elapsed > rule.auto_resolve_seconds:
                                await self.resolve_alert(
                                    alert.id,
                                    user="System",
                                    note="Auto-resolved after timeout",
                                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in auto-resolve loop: {e}")
                await asyncio.sleep(30)

    async def get_active_alerts(
        self,
        severity: Optional[Union[AlertSeverity, str]] = None,
        category: Optional[Union[AlertCategory, str]] = None,
    ) -> List[Alert]:
        """
        Get active alerts.

        Args:
            severity: Filter by severity
            category: Filter by category

        Returns:
            List of active alerts
        """
        async with self._lock:
            alerts = list(self._alerts.values())

            # Filter active statuses
            active_statuses = [
                AlertStatus.NEW,
                AlertStatus.ACKNOWLEDGED,
                AlertStatus.INVESTIGATING,
                AlertStatus.ESCALATED,
            ]
            alerts = [a for a in alerts if a.status in active_statuses]

            if severity:
                if isinstance(severity, str):
                    severity = AlertSeverity(severity)
                alerts = [a for a in alerts if a.severity == severity]

            if category:
                if isinstance(category, str):
                    category = AlertCategory(category)
                alerts = [a for a in alerts if a.category == category]

            return sorted(alerts, key=lambda x: x.created_at, reverse=True)

    async def get_alert_history(
        self,
        limit: int = 100,
        offset: int = 0,
        severity: Optional[Union[AlertSeverity, str]] = None,
        category: Optional[Union[AlertCategory, str]] = None,
        status: Optional[Union[AlertStatus, str]] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[Alert]:
        """
        Get alert history.

        Args:
            limit: Maximum number of alerts
            offset: Offset for pagination
            severity: Filter by severity
            category: Filter by category
            status: Filter by status
            from_date: Filter from date
            to_date: Filter to date

        Returns:
            List of alerts
        """
        async with self._lock:
            alerts = list(self._alerts.values())

            if severity:
                if isinstance(severity, str):
                    severity = AlertSeverity(severity)
                alerts = [a for a in alerts if a.severity == severity]

            if category:
                if isinstance(category, str):
                    category = AlertCategory(category)
                alerts = [a for a in alerts if a.category == category]

            if status:
                if isinstance(status, str):
                    status = AlertStatus(status)
                alerts = [a for a in alerts if a.status == status]

            if from_date:
                alerts = [a for a in alerts if a.created_at >= from_date]

            if to_date:
                alerts = [a for a in alerts if a.created_at <= to_date]

            alerts.sort(key=lambda x: x.created_at, reverse=True)
            return alerts[offset:offset + limit]

    async def get_alert_stats(self) -> Dict[str, Any]:
        """
        Get alert statistics.

        Returns:
            Alert statistics
        """
        async with self._lock:
            total = len(self._alerts)

            by_status = {}
            by_severity = {}
            by_category = {}

            for alert in self._alerts.values():
                by_status[alert.status.value] = by_status.get(alert.status.value, 0) + 1
                by_severity[alert.severity.value] = by_severity.get(alert.severity.value, 0) + 1
                by_category[alert.category.value] = by_category.get(alert.category.value, 0) + 1

            # Calculate average resolution time
            resolved_alerts = [
                a for a in self._alerts.values()
                if a.resolved_at and a.created_at
            ]

            if resolved_alerts:
                avg_resolution_time = np.mean([
                    (a.resolved_at - a.created_at).total_seconds()
                    for a in resolved_alerts
                ])
            else:
                avg_resolution_time = 0

            return {
                "total_alerts": total,
                "active_alerts": sum(by_status.get(s.value, 0) for s in [
                    AlertStatus.NEW,
                    AlertStatus.ACKNOWLEDGED,
                    AlertStatus.INVESTIGATING,
                    AlertStatus.ESCALATED,
                ]),
                "by_status": by_status,
                "by_severity": by_severity,
                "by_category": by_category,
                "avg_resolution_time_seconds": avg_resolution_time,
            }

    async def add_rule(self, rule: AlertRule) -> bool:
        """
        Add a new alert rule.

        Args:
            rule: Rule to add

        Returns:
            True if added
        """
        async with self._lock:
            if rule.id in self._rules:
                return False

            self._rules[rule.id] = rule
            await self._save_rules()
            logger.info(f"Added alert rule: {rule.id} - {rule.name}")
            return True

    async def update_rule(self, rule_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing rule.

        Args:
            rule_id: Rule to update
            updates: Updates to apply

        Returns:
            True if updated
        """
        async with self._lock:
            if rule_id not in self._rules:
                return False

            rule = self._rules[rule_id]

            for key, value in updates.items():
                if hasattr(rule, key):
                    if key == "severity":
                        value = AlertSeverity(value)
                    elif key == "category":
                        value = AlertCategory(value)
                    elif key == "channels":
                        value = [ChannelType(c) for c in value]
                    setattr(rule, key, value)

            rule.updated_at = datetime.utcnow()
            await self._save_rules()
            logger.info(f"Updated alert rule: {rule_id}")
            return True

    async def delete_rule(self, rule_id: str) -> bool:
        """
        Delete an alert rule.

        Args:
            rule_id: Rule to delete

        Returns:
            True if deleted
        """
        async with self._lock:
            if rule_id not in self._rules:
                return False

            del self._rules[rule_id]
            await self._save_rules()
            logger.info(f"Deleted alert rule: {rule_id}")
            return True

    async def _save_rules(self):
        """Save rules to file."""
        try:
            data = {
                "rules": [
                    {
                        "id": rule.id,
                        "name": rule.name,
                        "description": rule.description,
                        "severity": rule.severity.value,
                        "category": rule.category.value,
                        "condition": rule.condition,
                        "enabled": rule.enabled,
                        "cooldown_seconds": rule.cooldown_seconds,
                        "escalation_after_seconds": rule.escalation_after_seconds,
                        "auto_resolve_seconds": rule.auto_resolve_seconds,
                        "channels": [c.value for c in rule.channels],
                        "tags": rule.tags,
                    }
                    for rule in self._rules.values()
                ]
            }

            with open(self.rules_file, "w") as f:
                yaml.dump(data, f, default_flow_style=False)

        except Exception as e:
            logger.error(f"Error saving rules: {e}")

    async def shutdown(self):
        """Shutdown the alert manager."""
        if self._escalation_task:
            self._escalation_task.cancel()
            try:
                await self._escalation_task
            except asyncio.CancelledError:
                pass

        if self._auto_resolve_task:
            self._auto_resolve_task.cancel()
            try:
                await self._auto_resolve_task
            except asyncio.CancelledError:
                pass

        # Wait for notifications to complete
        if self._notification_tasks:
            await asyncio.gather(*self._notification_tasks, return_exceptions=True)

        logger.info("AlertManager shut down")


# Export singleton
alert_manager = AlertManager()
