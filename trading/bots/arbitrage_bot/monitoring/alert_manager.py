# trading/bots/arbitrage_bot/monitoring/alert_manager.py
# NEXUS AI TRADING SYSTEM - ALERT MANAGER
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module provides comprehensive alert management for the arbitrage bot,
# including alert generation, notification, escalation, and resolution.
# ====================================================================================

"""
NEXUS Arbitrage Bot Alert Manager

This module provides comprehensive alert management for:
- Alert generation and detection
- Multi-channel notification delivery
- Escalation and incident management
- Alert aggregation and deduplication
- Alert history and analytics
- Integration with external monitoring systems
"""

import asyncio
import logging
import json
import time
import smtplib
import ssl
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import uuid
import aiohttp
import aiofiles

# NEXUS internal imports
from trading.bots.arbitrage_bot.models.alert import (
    Alert, AlertSeverity, AlertCategory, AlertStatus, AlertPriority,
    AlertSource, AlertContext, AlertMetadata, NotificationChannel,
    AlertAction, EscalationLevel, EscalationRule, EscalationPolicy,
    AlertAggregationConfig, AlertGroup, create_alert
)
from trading.bots.arbitrage_bot.models.alert import AlertStats, AlertReport
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector
from trading.bots.arbitrage_bot.core.retry_handler import RetryHandler, RetryConfig
from trading.bots.arbitrage_bot.core.circuit_breaker import CircuitBreaker

logger = logging.getLogger("nexus.arbitrage.alert_manager")


# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class NotificationStatus(str, Enum):
    """Status of notification delivery."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class EscalationStatus(str, Enum):
    """Status of escalation process."""
    IDLE = "idle"
    IN_PROGRESS = "in_progress"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    FAILED = "failed"


# ====================================================================================
# NOTIFICATION PROVIDER CONFIGURATIONS
# ====================================================================================

@dataclass
class EmailConfig:
    """Email notification configuration."""
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    from_email: str = ""
    use_tls: bool = True
    use_ssl: bool = False
    timeout: int = 30


@dataclass
class SlackConfig:
    """Slack notification configuration."""
    webhook_url: str = ""
    bot_token: str = ""
    default_channel: str = "#alerts"
    username: str = "NEXUS Alert Bot"
    icon_emoji: str = ":robot_face:"
    icon_url: str = ""


@dataclass
class TelegramConfig:
    """Telegram notification configuration."""
    bot_token: str = ""
    chat_id: str = ""
    parse_mode: str = "HTML"
    disable_notification: bool = False


@dataclass
class DiscordConfig:
    """Discord notification configuration."""
    webhook_url: str = ""
    bot_token: str = ""
    default_channel: str = "alerts"
    username: str = "NEXUS Alert Bot"
    avatar_url: str = ""


@dataclass
class PagerDutyConfig:
    """PagerDuty notification configuration."""
    integration_key: str = ""
    routing_key: str = ""
    service_id: str = ""
    api_token: str = ""


@dataclass
class WebhookConfig:
    """Generic webhook notification configuration."""
    url: str = ""
    method: str = "POST"
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30


# ====================================================================================
# NOTIFICATION PROVIDER INTERFACE
# ====================================================================================

class NotificationProvider:
    """Base class for notification providers."""
    
    def __init__(self, config: Any):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60.0,
            half_open_attempts=2
        )
        
    async def initialize(self) -> None:
        """Initialize the provider."""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        
    async def close(self) -> None:
        """Close the provider."""
        if self._session:
            await self._session.close()
            
    async def send(self, alert: Alert, recipient: str = "") -> Dict[str, Any]:
        """
        Send notification.
        
        Args:
            alert: Alert to send
            recipient: Recipient identifier
            
        Returns:
            Notification result
        """
        try:
            if self._circuit_breaker.is_open():
                return {
                    "status": "failed",
                    "error": "Circuit breaker is open",
                    "retry_after": self._circuit_breaker.get_retry_after()
                }
                
            result = await self._send(alert, recipient)
            self._circuit_breaker.record_success()
            return result
            
        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(f"Notification send failed: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
            
    async def _send(self, alert: Alert, recipient: str) -> Dict[str, Any]:
        """Implement in subclass."""
        raise NotImplementedError


# ====================================================================================
# EMAIL PROVIDER
# ====================================================================================

class EmailProvider(NotificationProvider):
    """Email notification provider."""
    
    def __init__(self, config: EmailConfig):
        super().__init__(config)
        self._template = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; }
                .alert { padding: 15px; margin: 10px 0; border-radius: 5px; }
                .critical { background: #ffebee; border-left: 4px solid #c62828; }
                .high { background: #fff3e0; border-left: 4px solid #e65100; }
                .medium { background: #fff8e1; border-left: 4px solid #f9a825; }
                .low { background: #e8f5e9; border-left: 4px solid #2e7d32; }
                .info { background: #e3f2fd; border-left: 4px solid #0d47a1; }
                .header { color: #1a237e; margin-bottom: 10px; }
                .field { margin: 5px 0; }
                .label { font-weight: bold; color: #37474f; }
                .value { color: #263238; }
                .footer { margin-top: 20px; padding-top: 10px; border-top: 1px solid #e0e0e0; 
                         font-size: 12px; color: #78909c; }
            </style>
        </head>
        <body>
            <div class="alert {severity_class}">
                <h2 class="header">🚨 {title}</h2>
                <div class="field"><span class="label">Severity:</span> <span class="value">{severity}</span></div>
                <div class="field"><span class="label">Priority:</span> <span class="value">{priority}</span></div>
                <div class="field"><span class="label">Category:</span> <span class="value">{category}</span></div>
                <div class="field"><span class="label">Description:</span></div>
                <div class="value">{description}</div>
                <hr>
                <div class="field"><span class="label">Exchange:</span> <span class="value">{exchange}</span></div>
                <div class="field"><span class="label">Symbol:</span> <span class="value">{symbol}</span></div>
                <div class="field"><span class="label">Source:</span> <span class="value">{source}</span></div>
                <div class="field"><span class="label">Time:</span> <span class="value">{timestamp}</span></div>
                <div class="field"><span class="label">Alert ID:</span> <span class="value">{alert_id}</span></div>
                {extra}
                <div class="footer">
                    NEXUS AI Trading System - Automated Alert
                    <br>© 2026 NEXUS QUANTUM LTD
                </div>
            </div>
        </body>
        </html>
        """
        
    async def _send(self, alert: Alert, recipient: str) -> Dict[str, Any]:
        """Send email notification."""
        if not self.config.username or not self.config.password:
            return {"status": "failed", "error": "Email credentials not configured"}
            
        try:
            # Build email
            subject = f"[{alert.severity.value.upper()}] NEXUS Alert: {alert.title}"
            body = self._format_html(alert)
            
            # Create message
            msg = f"Subject: {subject}\n"
            msg += "MIME-Version: 1.0\n"
            msg += "Content-Type: text/html; charset=utf-8\n"
            msg += f"From: {self.config.from_email}\n"
            msg += f"To: {recipient}\n\n"
            msg += body
            
            # Send email
            if self.config.use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    self.config.smtp_server,
                    self.config.smtp_port,
                    context=context,
                    timeout=self.config.timeout
                ) as server:
                    server.login(self.config.username, self.config.password)
                    server.sendmail(self.config.from_email, recipient, msg.encode('utf-8'))
            else:
                with smtplib.SMTP(
                    self.config.smtp_server,
                    self.config.smtp_port,
                    timeout=self.config.timeout
                ) as server:
                    if self.config.use_tls:
                        server.starttls()
                    server.login(self.config.username, self.config.password)
                    server.sendmail(self.config.from_email, recipient, msg.encode('utf-8'))
                    
            return {"status": "sent", "recipient": recipient}
            
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return {"status": "failed", "error": str(e)}
            
    def _format_html(self, alert: Alert) -> str:
        """Format alert as HTML."""
        severity_class = {
            AlertSeverity.CRITICAL: "critical",
            AlertSeverity.HIGH: "high",
            AlertSeverity.MEDIUM: "medium",
            AlertSeverity.LOW: "low",
            AlertSeverity.INFO: "info"
        }.get(alert.severity, "info")
        
        extra = ""
        if alert.context.details:
            extra = "<div class='field'><span class='label'>Details:</span></div>"
            for key, value in alert.context.details.items():
                extra += f"<div class='field'><span class='label'>{key}:</span> <span class='value'>{value}</span></div>"
                
        return self._template.format(
            severity_class=severity_class,
            title=alert.title,
            severity=alert.severity.value.upper(),
            priority=alert.priority.value.upper(),
            category=alert.category.value.upper(),
            description=alert.description,
            exchange=alert.context.exchange or "N/A",
            symbol=alert.context.symbol or "N/A",
            source=alert.source.name or "N/A",
            timestamp=alert.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            alert_id=alert.id,
            extra=extra
        )


# ====================================================================================
# SLACK PROVIDER
# ====================================================================================

class SlackProvider(NotificationProvider):
    """Slack notification provider."""
    
    def __init__(self, config: SlackConfig):
        super().__init__(config)
        
    async def _send(self, alert: Alert, recipient: str) -> Dict[str, Any]:
        """Send Slack notification."""
        if not self.config.webhook_url and not self.config.bot_token:
            return {"status": "failed", "error": "Slack credentials not configured"}
            
        try:
            # Build message
            color_map = {
                AlertSeverity.CRITICAL: "#c62828",
                AlertSeverity.HIGH: "#e65100",
                AlertSeverity.MEDIUM: "#f9a825",
                AlertSeverity.LOW: "#2e7d32",
                AlertSeverity.INFO: "#0d47a1"
            }
            
            channel = recipient or self.config.default_channel
            
            payload = {
                "channel": channel,
                "username": self.config.username,
                "icon_emoji": self.config.icon_emoji,
                "attachments": [{
                    "color": color_map.get(alert.severity, "#607d8b"),
                    "title": f"🚨 {alert.title}",
                    "fields": [
                        {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                        {"title": "Priority", "value": alert.priority.value.upper(), "short": True},
                        {"title": "Category", "value": alert.category.value.upper(), "short": True},
                        {"title": "Status", "value": alert.status.value.upper(), "short": True},
                        {"title": "Exchange", "value": alert.context.exchange or "N/A", "short": True},
                        {"title": "Symbol", "value": alert.context.symbol or "N/A", "short": True},
                        {"title": "Source", "value": alert.source.name or "N/A", "short": True},
                    ],
                    "text": alert.description[:500],
                    "footer": f"NEXUS Trading Alert • {alert.id}",
                    "ts": int(alert.created_at.timestamp()),
                    "mrkdwn_in": ["text", "fields"]
                }]
            }
            
            # Add extra fields from context
            if alert.context.details:
                for key, value in list(alert.context.details.items())[:5]:
                    payload["attachments"][0]["fields"].append({
                        "title": key,
                        "value": str(value),
                        "short": True
                    })
                    
            # Send
            url = self.config.webhook_url or "https://slack.com/api/chat.postMessage"
            headers = {"Content-Type": "application/json"}
            
            if not self.config.webhook_url and self.config.bot_token:
                headers["Authorization"] = f"Bearer {self.config.bot_token}"
                
            async with self._session.post(url, json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok"):
                        return {"status": "sent", "channel": channel}
                    else:
                        return {"status": "failed", "error": result.get("error", "Unknown error")}
                else:
                    return {"status": "failed", "error": f"HTTP {response.status}"}
                    
        except Exception as e:
            logger.error(f"Slack send failed: {e}")
            return {"status": "failed", "error": str(e)}


# ====================================================================================
# TELEGRAM PROVIDER
# ====================================================================================

class TelegramProvider(NotificationProvider):
    """Telegram notification provider."""
    
    def __init__(self, config: TelegramConfig):
        super().__init__(config)
        
    async def _send(self, alert: Alert, recipient: str) -> Dict[str, Any]:
        """Send Telegram notification."""
        if not self.config.bot_token:
            return {"status": "failed", "error": "Telegram bot token not configured"}
            
        try:
            # Build message
            emoji_map = {
                AlertSeverity.CRITICAL: "🔴",
                AlertSeverity.HIGH: "🟠",
                AlertSeverity.MEDIUM: "🟡",
                AlertSeverity.LOW: "🟢",
                AlertSeverity.INFO: "🔵"
            }
            
            emoji = emoji_map.get(alert.severity, "⚪")
            
            message = f"""
<b>{emoji} NEXUS Alert: {alert.title}</b>

<b>Severity:</b> <code>{alert.severity.value.upper()}</code>
<b>Priority:</b> <code>{alert.priority.value.upper()}</code>
<b>Category:</b> <code>{alert.category.value.upper()}</code>
<b>Status:</b> <code>{alert.status.value.upper()}</code>

<b>Description:</b>
{alert.description}

<b>Exchange:</b> {alert.context.exchange or 'N/A'}
<b>Symbol:</b> {alert.context.symbol or 'N/A'}
<b>Source:</b> {alert.source.name or 'N/A'}

<b>Alert ID:</b> <code>{alert.id}</code>
<b>Time:</b> {alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
            
            chat_id = recipient or self.config.chat_id
            
            # Send
            url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_notification": self.config.disable_notification
            }
            
            async with self._session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok"):
                        return {"status": "sent", "chat_id": chat_id}
                    else:
                        return {"status": "failed", "error": result.get("description", "Unknown error")}
                else:
                    return {"status": "failed", "error": f"HTTP {response.status}"}
                    
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return {"status": "failed", "error": str(e)}


# ====================================================================================
# DISCORD PROVIDER
# ====================================================================================

class DiscordProvider(NotificationProvider):
    """Discord notification provider."""
    
    def __init__(self, config: DiscordConfig):
        super().__init__(config)
        
    async def _send(self, alert: Alert, recipient: str) -> Dict[str, Any]:
        """Send Discord notification."""
        if not self.config.webhook_url and not self.config.bot_token:
            return {"status": "failed", "error": "Discord credentials not configured"}
            
        try:
            color_map = {
                AlertSeverity.CRITICAL: 0xc62828,
                AlertSeverity.HIGH: 0xe65100,
                AlertSeverity.MEDIUM: 0xf9a825,
                AlertSeverity.LOW: 0x2e7d32,
                AlertSeverity.INFO: 0x0d47a1
            }
            
            payload = {
                "content": f"🚨 **{alert.title}**",
                "username": self.config.username,
                "avatar_url": self.config.avatar_url,
                "embeds": [{
                    "color": color_map.get(alert.severity, 0x607d8b),
                    "fields": [
                        {"name": "Severity", "value": alert.severity.value.upper(), "inline": True},
                        {"name": "Priority", "value": alert.priority.value.upper(), "inline": True},
                        {"name": "Category", "value": alert.category.value.upper(), "inline": True},
                        {"name": "Exchange", "value": alert.context.exchange or "N/A", "inline": True},
                        {"name": "Symbol", "value": alert.context.symbol or "N/A", "inline": True},
                        {"name": "Status", "value": alert.status.value.upper(), "inline": True},
                    ],
                    "description": alert.description[:2000],
                    "footer": {"text": f"NEXUS Trading Alert • {alert.id}"},
                    "timestamp": alert.created_at.isoformat()
                }]
            }
            
            # Add extra details
            if alert.context.details:
                detail_text = "\n".join([f"{k}: {v}" for k, v in alert.context.details.items()][:5])
                payload["embeds"][0]["fields"].append({
                    "name": "Details",
                    "value": detail_text[:1000],
                    "inline": False
                })
                
            # Send
            url = self.config.webhook_url
            async with self._session.post(url, json=payload) as response:
                if response.status in [200, 204]:
                    return {"status": "sent"}
                else:
                    return {"status": "failed", "error": f"HTTP {response.status}"}
                    
        except Exception as e:
            logger.error(f"Discord send failed: {e}")
            return {"status": "failed", "error": str(e)}


# ====================================================================================
# PAGERDUTY PROVIDER
# ====================================================================================

class PagerDutyProvider(NotificationProvider):
    """PagerDuty notification provider."""
    
    def __init__(self, config: PagerDutyConfig):
        super().__init__(config)
        
    async def _send(self, alert: Alert, recipient: str) -> Dict[str, Any]:
        """Send PagerDuty notification."""
        if not self.config.integration_key:
            return {"status": "failed", "error": "PagerDuty integration key not configured"}
            
        try:
            severity_map = {
                AlertSeverity.CRITICAL: "critical",
                AlertSeverity.HIGH: "error",
                AlertSeverity.MEDIUM: "warning",
                AlertSeverity.LOW: "info",
                AlertSeverity.INFO: "info"
            }
            
            payload = {
                "payload": {
                    "summary": alert.title,
                    "source": alert.source.name or "nexus-arbitrage-bot",
                    "severity": severity_map.get(alert.severity, "warning"),
                    "timestamp": alert.created_at.isoformat(),
                    "component": alert.category.value,
                    "group": "arbitrage",
                    "class": alert.type.value if hasattr(alert, 'type') else "alert",
                    "custom_details": {
                        "alert_id": alert.id,
                        "priority": alert.priority.value,
                        "description": alert.description,
                        "exchange": alert.context.exchange,
                        "symbol": alert.context.symbol,
                        "source_module": alert.source.module,
                        "source_function": alert.source.function
                    }
                },
                "routing_key": self.config.routing_key or self.config.integration_key,
                "event_action": "trigger"
            }
            
            # Add details from context
            if alert.context.details:
                for key, value in alert.context.details.items():
                    payload["payload"]["custom_details"][key] = value
                    
            # Send
            url = "https://events.pagerduty.com/v2/enqueue"
            headers = {"Content-Type": "application/json"}
            
            if self.config.api_token:
                headers["Authorization"] = f"Token token={self.config.api_token}"
                
            async with self._session.post(url, json=payload, headers=headers) as response:
                if response.status == 202:
                    return {"status": "sent", "dedup_key": (await response.json()).get("dedup_key")}
                else:
                    return {"status": "failed", "error": f"HTTP {response.status}"}
                    
        except Exception as e:
            logger.error(f"PagerDuty send failed: {e}")
            return {"status": "failed", "error": str(e)}


# ====================================================================================
# WEBHOOK PROVIDER
# ====================================================================================

class WebhookProvider(NotificationProvider):
    """Webhook notification provider."""
    
    def __init__(self, config: WebhookConfig):
        super().__init__(config)
        
    async def _send(self, alert: Alert, recipient: str) -> Dict[str, Any]:
        """Send webhook notification."""
        if not self.config.url:
            return {"status": "failed", "error": "Webhook URL not configured"}
            
        try:
            payload = {
                "alert_id": alert.id,
                "title": alert.title,
                "description": alert.description,
                "severity": alert.severity.value,
                "priority": alert.priority.value,
                "category": alert.category.value,
                "status": alert.status.value,
                "timestamp": alert.created_at.isoformat(),
                "source": {
                    "name": alert.source.name,
                    "type": alert.source.type,
                    "module": alert.source.module,
                    "function": alert.source.function,
                    "host": alert.source.host
                },
                "context": {
                    "symbol": alert.context.symbol,
                    "exchange": alert.context.exchange,
                    "value": alert.context.value,
                    "threshold": alert.context.threshold,
                    "duration_ms": alert.context.duration_ms
                },
                "metadata": alert.metadata.to_dict(),
                "details": alert.context.details
            }
            
            headers = self.config.headers or {}
            headers["Content-Type"] = "application/json"
            
            async with self._session.request(
                method=self.config.method,
                url=self.config.url,
                json=payload,
                headers=headers,
                timeout=self.config.timeout
            ) as response:
                if 200 <= response.status < 300:
                    return {"status": "sent", "status_code": response.status}
                else:
                    return {"status": "failed", "error": f"HTTP {response.status}"}
                    
        except Exception as e:
            logger.error(f"Webhook send failed: {e}")
            return {"status": "failed", "error": str(e)}


# ====================================================================================
# ALERT MANAGER
# ====================================================================================

class AlertManager:
    """
    Comprehensive alert management system.
    
    Features:
    - Multi-channel notification delivery
    - Alert aggregation and deduplication
    - Escalation and incident management
    - Alert history and analytics
    - Integration with external monitoring
    - Circuit breaker and retry logic
    - Health monitoring and metrics
    """
    
    def __init__(self):
        # Alert storage
        self._alerts: Dict[str, Alert] = {}
        self._alert_groups: Dict[str, AlertGroup] = {}
        self._alert_history: deque = deque(maxlen=10000)
        
        # Notification providers
        self._providers: Dict[NotificationChannel, NotificationProvider] = {}
        self._provider_configs: Dict[NotificationChannel, Any] = {}
        
        # Escalation
        self._escalation_policies: Dict[str, EscalationPolicy] = {}
        self._escalation_status: Dict[str, EscalationStatus] = {}
        self._escalation_tasks: Dict[str, asyncio.Task] = {}
        
        # Aggregation
        self._aggregation_configs: Dict[str, AlertAggregationConfig] = {}
        self._aggregation_windows: Dict[str, List[Alert]] = defaultdict(list)
        self._aggregation_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Metrics
        self._metrics = MetricsCollector(
            name="nexus_alert_manager",
            labels={"service": "arbitrage_bot"}
        )
        self._setup_metrics()
        
        # State
        self._initialized = False
        self._running = False
        self._background_tasks: Set[asyncio.Task] = set()
        
        # Configuration
        self._default_aggregation_config = AlertAggregationConfig(
            enabled=True,
            aggregation_type="deduplicate",
            window_seconds=60,
            max_alerts_per_window=10,
            deduplicate_fields=["title", "severity", "category", "symbol", "exchange"]
        )
        
        logger.info("AlertManager initialized (version=3.0.0)")
        
    def _setup_metrics(self) -> None:
        """Setup metrics collection."""
        self._metrics.register_counter("alerts_total", "Total alerts generated")
        self._metrics.register_counter("alerts_by_severity", "Alerts by severity")
        self._metrics.register_counter("alerts_by_category", "Alerts by category")
        self._metrics.register_counter("notifications_sent", "Notifications sent")
        self._metrics.register_counter("notifications_failed", "Notifications failed")
        self._metrics.register_gauge("alerts_active", "Active alerts")
        self._metrics.register_gauge("alerts_open", "Open alerts")
        self._metrics.register_histogram("alert_resolution_time", "Alert resolution time in seconds")
        
    def configure_provider(
        self,
        channel: NotificationChannel,
        config: Union[
            EmailConfig, SlackConfig, TelegramConfig,
            DiscordConfig, PagerDutyConfig, WebhookConfig
        ]
    ) -> None:
        """
        Configure a notification provider.
        
        Args:
            channel: Notification channel
            config: Provider configuration
        """
        self._provider_configs[channel] = config
        
        # Create provider instance
        if channel == NotificationChannel.EMAIL:
            self._providers[channel] = EmailProvider(config)
        elif channel == NotificationChannel.SLACK:
            self._providers[channel] = SlackProvider(config)
        elif channel == NotificationChannel.TELEGRAM:
            self._providers[channel] = TelegramProvider(config)
        elif channel == NotificationChannel.DISCORD:
            self._providers[channel] = DiscordProvider(config)
        elif channel == NotificationChannel.PAGERDUTY:
            self._providers[channel] = PagerDutyProvider(config)
        elif channel == NotificationChannel.WEBHOOK:
            self._providers[channel] = WebhookProvider(config)
        else:
            logger.warning(f"Unsupported channel: {channel}")
            
        logger.info(f"Configured provider for channel: {channel.value}")
        
    def add_escalation_policy(self, policy: EscalationPolicy) -> None:
        """
        Add an escalation policy.
        
        Args:
            policy: Escalation policy
        """
        self._escalation_policies[policy.id] = policy
        logger.info(f"Added escalation policy: {policy.name}")
        
    def set_aggregation_config(
        self,
        config: AlertAggregationConfig,
        key: str = "default"
    ) -> None:
        """
        Set aggregation configuration.
        
        Args:
            config: Aggregation configuration
            key: Configuration key
        """
        self._aggregation_configs[key] = config
        logger.info(f"Set aggregation config: {key}")
        
    async def initialize(self) -> None:
        """Initialize the alert manager."""
        if self._initialized:
            return
            
        # Initialize providers
        for provider in self._providers.values():
            await provider.initialize()
            
        # Start background tasks
        await self._start_background_tasks()
        
        self._initialized = True
        self._running = True
        logger.info("AlertManager initialized")
        
    async def _start_background_tasks(self) -> None:
        """Start background maintenance tasks."""
        # Aggregation cleanup
        task = asyncio.create_task(self._aggregation_cleanup_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        # Escalation monitor
        task = asyncio.create_task(self._escalation_monitor_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        # Metrics update
        task = asyncio.create_task(self._metrics_update_loop())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
    async def _aggregation_cleanup_loop(self) -> None:
        """Clean up old aggregation windows."""
        while self._running:
            try:
                await asyncio.sleep(60)
                now = datetime.utcnow()
                
                for key, windows in self._aggregation_windows.items():
                    config = self._aggregation_configs.get(key, self._default_aggregation_config)
                    cutoff = now - timedelta(seconds=config.window_seconds)
                    
                    # Remove old alerts
                    self._aggregation_windows[key] = [
                        a for a in windows
                        if a.created_at > cutoff
                    ]
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Aggregation cleanup error: {e}")
                
    async def _escalation_monitor_loop(self) -> None:
        """Monitor and process escalations."""
        while self._running:
            try:
                await asyncio.sleep(30)
                for alert_id, alert in self._alerts.items():
                    if alert.status in [AlertStatus.PENDING, AlertStatus.ACKNOWLEDGED]:
                        await self._check_escalation(alert)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Escalation monitor error: {e}")
                
    async def _metrics_update_loop(self) -> None:
        """Update metrics periodically."""
        while self._running:
            try:
                await asyncio.sleep(60)
                active = sum(1 for a in self._alerts.values() 
                            if a.status in [AlertStatus.PENDING, AlertStatus.ACKNOWLEDGED])
                open_alerts = sum(1 for a in self._alerts.values() 
                                 if a.status not in [AlertStatus.RESOLVED, AlertStatus.CLOSED])
                
                self._metrics.set_gauge("alerts_active", active)
                self._metrics.set_gauge("alerts_open", open_alerts)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics update error: {e}")
                
    async def close(self) -> None:
        """Close the alert manager."""
        self._running = False
        self._initialized = False
        
        # Cancel background tasks
        for task in list(self._background_tasks):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        # Close providers
        for provider in self._providers.values():
            await provider.close()
            
        logger.info("AlertManager closed")
        
    # ====================================================================
    # ALERT GENERATION
    # ====================================================================
    
    async def create_alert(
        self,
        title: str,
        description: str,
        severity: AlertSeverity = AlertSeverity.MEDIUM,
        category: AlertCategory = AlertCategory.SYSTEM,
        source: Optional[AlertSource] = None,
        context: Optional[AlertContext] = None,
        send_notifications: bool = True,
        **kwargs
    ) -> Alert:
        """
        Create and process a new alert.
        
        Args:
            title: Alert title
            description: Alert description
            severity: Alert severity
            category: Alert category
            source: Alert source
            context: Alert context
            send_notifications: Whether to send notifications
            **kwargs: Additional alert fields
            
        Returns:
            Created Alert
        """
        # Check for aggregation/deduplication
        alert = await self._process_aggregation(
            title, description, severity, category, source, context, **kwargs
        )
        
        if alert is None:
            # Alert was aggregated/suppressed
            return None
            
        # Store alert
        self._alerts[alert.id] = alert
        self._alert_history.append(alert)
        
        # Update metrics
        self._metrics.increment_counter("alerts_total")
        self._metrics.increment_counter("alerts_by_severity", labels={"severity": severity.value})
        self._metrics.increment_counter("alerts_by_category", labels={"category": category.value})
        
        # Send notifications
        if send_notifications:
            await self._send_notifications(alert)
            
        # Check escalation
        await self._check_escalation(alert)
        
        logger.info(f"Alert created: {alert.id} - {alert.title}")
        return alert
        
    async def _process_aggregation(
        self,
        title: str,
        description: str,
        severity: AlertSeverity,
        category: AlertCategory,
        source: Optional[AlertSource],
        context: Optional[AlertContext],
        **kwargs
    ) -> Optional[Alert]:
        """
        Process alert through aggregation/deduplication.
        
        Returns:
            Alert if should be created, None if suppressed
        """
        # Get aggregation config
        config = self._aggregation_configs.get(
            f"{category.value}_{severity.value}",
            self._aggregation_configs.get("default", self._default_aggregation_config)
        )
        
        if not config.enabled:
            # Create new alert
            return self._create_alert_object(
                title, description, severity, category, source, context, **kwargs
            )
            
        # Check for duplicates
        dedup_key = self._generate_dedup_key(
            title, severity, category, source, context,
            config.deduplicate_fields
        )
        
        async with self._aggregation_locks[dedup_key]:
            # Check existing alerts in window
            window_alerts = [
                a for a in self._aggregation_windows[dedup_key]
                if a.created_at > datetime.utcnow() - timedelta(seconds=config.window_seconds)
            ]
            
            if window_alerts and config.aggregation_type == "deduplicate":
                # Update existing alert
                existing = window_alerts[0]
                existing.occurrence_count += 1
                existing.last_occurrence = datetime.utcnow()
                existing.updated_at = datetime.utcnow()
                return None
                
            if len(window_alerts) >= config.max_alerts_per_window:
                # Throttle
                return None
                
            # Create new alert
            alert = self._create_alert_object(
                title, description, severity, category, source, context, **kwargs
            )
            
            # Add to window
            self._aggregation_windows[dedup_key].append(alert)
            
            # Set aggregation info
            alert.aggregation_type = config.aggregation_type.value
            alert.aggregate_key = dedup_key
            alert.aggregate_count = len(window_alerts) + 1
            
            return alert
            
    def _generate_dedup_key(
        self,
        title: str,
        severity: AlertSeverity,
        category: AlertCategory,
        source: Optional[AlertSource],
        context: Optional[AlertContext],
        fields: List[str]
    ) -> str:
        """Generate deduplication key."""
        parts = []
        for field in fields:
            if field == "title":
                parts.append(title.lower())
            elif field == "severity":
                parts.append(severity.value)
            elif field == "category":
                parts.append(category.value)
            elif field == "symbol" and context:
                parts.append(context.symbol or "")
            elif field == "exchange" and context:
                parts.append(context.exchange or "")
            elif field == "source" and source:
                parts.append(source.name or "")
        return "_".join(parts)
        
    def _create_alert_object(
        self,
        title: str,
        description: str,
        severity: AlertSeverity,
        category: AlertCategory,
        source: Optional[AlertSource],
        context: Optional[AlertContext],
        **kwargs
    ) -> Alert:
        """Create alert object."""
        return create_alert(
            title=title,
            description=description,
            severity=severity,
            category=category,
            source=source or AlertSource(),
            context=context or AlertContext(),
            **kwargs
        )
        
    # ====================================================================
    # NOTIFICATION
    # ====================================================================
    
    async def _send_notifications(self, alert: Alert) -> None:
        """
        Send notifications for an alert.
        
        Args:
            alert: Alert to send notifications for
        """
        channels = alert.notification_channels or [NotificationChannel.CONSOLE]
        
        results = []
        for channel in channels:
            if channel in self._providers:
                result = await self._send_notification(alert, channel)
                results.append(result)
            else:
                logger.warning(f"No provider configured for channel: {channel.value}")
                
        # Log results
        successful = sum(1 for r in results if r.get("status") == "sent")
        failed = len(results) - successful
        
        self._metrics.increment_counter("notifications_sent", value=successful)
        self._metrics.increment_counter("notifications_failed", value=failed)
        
    async def _send_notification(
        self,
        alert: Alert,
        channel: NotificationChannel
    ) -> Dict[str, Any]:
        """
        Send notification via a specific channel.
        
        Args:
            alert: Alert to send
            channel: Notification channel
            
        Returns:
            Notification result
        """
        provider = self._providers.get(channel)
        if not provider:
            return {"status": "failed", "error": f"No provider for channel: {channel.value}"}
            
        try:
            # Determine recipient
            recipient = alert.assignee or ""
            
            # Send
            result = await provider.send(alert, recipient)
            
            # Update alert
            if result.get("status") == "sent":
                alert.notifications_sent[channel.value] = datetime.utcnow()
                
            return result
            
        except Exception as e:
            logger.error(f"Notification error on {channel.value}: {e}")
            return {"status": "failed", "error": str(e)}
            
    def add_notification_channel(
        self,
        alert_id: str,
        channel: NotificationChannel
    ) -> bool:
        """
        Add a notification channel to an alert.
        
        Args:
            alert_id: Alert ID
            channel: Notification channel
            
        Returns:
            True if added successfully
        """
        alert = self._alerts.get(alert_id)
        if not alert:
            return False
            
        if channel not in alert.notification_channels:
            alert.notification_channels.append(channel)
            alert.updated_at = datetime.utcnow()
            return True
            
        return False
        
    # ====================================================================
    # ESCALATION
    # ====================================================================
    
    async def _check_escalation(self, alert: Alert) -> None:
        """
        Check and process escalation for an alert.
        
        Args:
            alert: Alert to check
        """
        # Find matching escalation policy
        policy = None
        for p in self._escalation_policies.values():
            rule = p.get_escalation_rule(alert)
            if rule:
                policy = p
                break
                
        if not policy:
            return
            
        # Check if escalation is needed
        if alert.status in [AlertStatus.PENDING, AlertStatus.ACKNOWLEDGED]:
            time_open = (datetime.utcnow() - alert.created_at).total_seconds()
            
            for rule in policy.rules:
                if rule.matches(alert):
                    if time_open > rule.delay_minutes * 60:
                        if alert.escalation_count < rule.max_escalations:
                            await self._escalate_alert(alert, rule)
                            break
                            
    async def _escalate_alert(
        self,
        alert: Alert,
        rule: EscalationRule
    ) -> None:
        """
        Escalate an alert.
        
        Args:
            alert: Alert to escalate
            rule: Escalation rule
        """
        alert.escalate(rule.escalation_level)
        alert.assigned_team = rule.recipients[0] if rule.recipients else ""
        alert.updated_at = datetime.utcnow()
        
        # Send escalation notification
        if rule.notify_on_escalation:
            await self._send_escalation_notification(alert, rule)
            
        logger.info(f"Alert escalated: {alert.id} to {rule.escalation_level.value}")
        
    async def _send_escalation_notification(
        self,
        alert: Alert,
        rule: EscalationRule
    ) -> None:
        """
        Send escalation notification.
        
        Args:
            alert: Alert being escalated
            rule: Escalation rule
        """
        channels = rule.channels or [NotificationChannel.CONSOLE]
        
        for channel in channels:
            if channel in self._providers:
                # Add escalation context
                alert.metadata.custom_fields["escalation_level"] = rule.escalation_level.value
                alert.metadata.custom_fields["escalation_rule"] = rule.name
                
                await self._send_notification(alert, channel)
                
    # ====================================================================
    # ALERT MANAGEMENT
    # ====================================================================
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID."""
        return self._alerts.get(alert_id)
        
    def get_all_alerts(
        self,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        category: Optional[AlertCategory] = None,
        limit: int = 100
    ) -> List[Alert]:
        """
        Get alerts with filters.
        
        Args:
            status: Filter by status
            severity: Filter by severity
            category: Filter by category
            limit: Maximum number of alerts
            
        Returns:
            List of alerts
        """
        alerts = list(self._alerts.values())
        
        if status:
            alerts = [a for a in alerts if a.status == status]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if category:
            alerts = [a for a in alerts if a.category == category]
            
        # Sort by created_at descending
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        
        return alerts[:limit]
        
    async def acknowledge_alert(
        self,
        alert_id: str,
        user: str = "",
        comment: str = ""
    ) -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: Alert ID
            user: User acknowledging
            comment: Comment
            
        Returns:
            True if acknowledged
        """
        alert = self._alerts.get(alert_id)
        if not alert:
            return False
            
        alert.acknowledge(user, comment)
        alert.updated_at = datetime.utcnow()
        
        logger.info(f"Alert acknowledged: {alert_id} by {user}")
        return True
        
    async def resolve_alert(
        self,
        alert_id: str,
        user: str = "",
        comment: str = ""
    ) -> bool:
        """
        Resolve an alert.
        
        Args:
            alert_id: Alert ID
            user: User resolving
            comment: Comment
            
        Returns:
            True if resolved
        """
        alert = self._alerts.get(alert_id)
        if not alert:
            return False
            
        alert.resolve(user, comment)
        alert.updated_at = datetime.utcnow()
        
        # Record resolution time
        resolution_time = (alert.resolved_at - alert.created_at).total_seconds()
        self._metrics.record_histogram("alert_resolution_time", resolution_time)
        
        logger.info(f"Alert resolved: {alert_id} by {user}")
        return True
        
    # ====================================================================
    # STATISTICS AND REPORTING
    # ====================================================================
    
    def get_stats(self, period_days: int = 1) -> AlertStats:
        """
        Get alert statistics.
        
        Args:
            period_days: Analysis period in days
            
        Returns:
            Alert statistics
        """
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        alerts = [a for a in self._alert_history if a.created_at > cutoff]
        
        stats = AlertStats(
            total=len(alerts),
            period_start=cutoff,
            period_end=datetime.utcnow()
        )
        
        # By severity
        for sev in AlertSeverity:
            stats.by_severity[sev.value] = sum(1 for a in alerts if a.severity == sev)
            
        # By category
        for cat in AlertCategory:
            stats.by_category[cat.value] = sum(1 for a in alerts if a.category == cat)
            
        # By status
        for status in AlertStatus:
            stats.by_status[status.value] = sum(1 for a in alerts if a.status == status)
            
        # Resolution metrics
        resolved = [a for a in alerts if a.status == AlertStatus.RESOLVED]
        if resolved:
            resolution_times = [(a.resolved_at - a.created_at).total_seconds() for a in resolved]
            stats.average_resolution_time = sum(resolution_times) / len(resolution_times)
            
        stats.resolution_rate = len(resolved) / len(alerts) if alerts else 0
        
        return stats
        
    def generate_report(self, period_days: int = 1) -> AlertReport:
        """
        Generate alert report.
        
        Args:
            period_days: Analysis period in days
            
        Returns:
            Alert report
        """
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        alerts = [a for a in self._alert_history if a.created_at > cutoff]
        
        stats = self.get_stats(period_days)
        
        return AlertReport(
            name=f"Alert Report - {datetime.utcnow().strftime('%Y-%m-%d')}",
            description=f"Alert summary for the last {period_days} days",
            period_start=cutoff,
            period_end=datetime.utcnow(),
            stats=stats,
            top_alerts=sorted(alerts, key=lambda a: a.occurrence_count, reverse=True)[:10],
            recommendations=self._generate_recommendations(stats)
        )
        
    def _generate_recommendations(self, stats: AlertStats) -> List[str]:
        """Generate recommendations based on stats."""
        recommendations = []
        
        if stats.by_severity.get("critical", 0) > 10:
            recommendations.append("High number of critical alerts. Review system stability.")
            
        if stats.by_category.get("exchange", 0) > 20:
            recommendations.append("Many exchange-related alerts. Check exchange connections.")
            
        if stats.resolution_rate < 0.5:
            recommendations.append("Low resolution rate. Improve alert response process.")
            
        if stats.average_resolution_time > 3600:
            recommendations.append("Slow resolution time. Consider faster response procedures.")
            
        return recommendations


# ====================================================================================
# GLOBAL INSTANCE
# ====================================================================================

_global_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """
    Get the global alert manager instance.
    
    Returns:
        AlertManager instance
    """
    global _global_alert_manager
    if _global_alert_manager is None:
        _global_alert_manager = AlertManager()
    return _global_alert_manager


def reset_alert_manager() -> None:
    """Reset the global alert manager instance."""
    global _global_alert_manager
    if _global_alert_manager:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_global_alert_manager.close())
            else:
                asyncio.run(_global_alert_manager.close())
        except Exception:
            pass
    _global_alert_manager = None


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'NotificationStatus',
    'EscalationStatus',
    
    # Configurations
    'EmailConfig',
    'SlackConfig',
    'TelegramConfig',
    'DiscordConfig',
    'PagerDutyConfig',
    'WebhookConfig',
    
    # Providers
    'NotificationProvider',
    'EmailProvider',
    'SlackProvider',
    'TelegramProvider',
    'DiscordProvider',
    'PagerDutyProvider',
    'WebhookProvider',
    
    # Manager
    'AlertManager',
    'get_alert_manager',
    'reset_alert_manager',
]
