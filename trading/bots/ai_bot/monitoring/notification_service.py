"""
NEXUS AI TRADING SYSTEM - Notification Service
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced notification service with multi-channel delivery, template management,
batch processing, and intelligent routing for trading system alerts and updates.
"""

import asyncio
import json
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import aiofiles
import aiohttp
import yaml
from jinja2 import Environment, FileSystemLoader
from prometheus_client import Counter, Histogram, Gauge

from shared.utilities.logger import get_logger
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
NOTIFICATION_COUNTER = Counter(
    "nexus_notifications_total",
    "Total number of notifications sent",
    ["channel", "status", "template"],
)
NOTIFICATION_DURATION = Histogram(
    "nexus_notification_duration_seconds",
    "Duration of notification delivery",
    ["channel"],
)
NOTIFICATION_QUEUE_SIZE = Gauge(
    "nexus_notification_queue_size",
    "Size of notification queue",
)


class NotificationPriority(Enum):
    """Notification priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


class NotificationChannel(Enum):
    """Supported notification channels."""

    EMAIL = "email"
    SLACK = "slack"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    PUSHOVER = "pushover"
    SMS = "sms"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"
    OPSGENIE = "opsgenie"
    PUSH_NOTIFICATION = "push"
    IN_APP = "in_app"


@dataclass
class Notification:
    """Notification message."""

    id: str
    title: str
    message: str
    template_name: Optional[str] = None
    template_data: Dict[str, Any] = field(default_factory=dict)
    priority: NotificationPriority = NotificationPriority.NORMAL
    channels: List[NotificationChannel] = field(default_factory=list)
    recipients: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    status: str = "pending"
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "template_name": self.template_name,
            "template_data": self.template_data,
            "priority": self.priority.value,
            "channels": [c.value for c in self.channels],
            "recipients": self.recipients,
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "status": self.status,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "metadata": self.metadata,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Notification":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            title=data["title"],
            message=data["message"],
            template_name=data.get("template_name"),
            template_data=data.get("template_data", {}),
            priority=NotificationPriority(data["priority"]),
            channels=[NotificationChannel(c) for c in data.get("channels", [])],
            recipients=data.get("recipients", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            sent_at=datetime.fromisoformat(data["sent_at"]) if data.get("sent_at") else None,
            status=data.get("status", "pending"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
        )


@dataclass
class NotificationTemplate:
    """Notification template."""

    name: str
    subject: str
    body: str
    channels: List[NotificationChannel]
    priority: NotificationPriority = NotificationPriority.NORMAL
    enabled: bool = True
    description: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "subject": self.subject,
            "body": self.body,
            "channels": [c.value for c in self.channels],
            "priority": self.priority.value,
            "enabled": self.enabled,
            "description": self.description,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotificationTemplate":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            subject=data["subject"],
            body=data["body"],
            channels=[NotificationChannel(c) for c in data["channels"]],
            priority=NotificationPriority(data.get("priority", "normal")),
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            tags=data.get("tags", []),
        )


@dataclass
class ChannelConfig:
    """Channel configuration."""

    channel: NotificationChannel
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    rate_limit_per_minute: int = 60
    retry_delay_seconds: int = 5
    max_retries: int = 3


class NotificationService:
    """
    Advanced notification service with multi-channel delivery and templating.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_manager: Optional[CacheManager] = None,
    ):
        """
        Initialize the notification service.

        Args:
            config: Configuration dictionary
            cache_manager: Cache manager instance
        """
        self.config = config or {}
        self.cache_manager = cache_manager or CacheManager()
        self._lock = asyncio.Lock()
        self._queue: List[Notification] = []
        self._processing_task: Optional[asyncio.Task] = None
        self._retry_task: Optional[asyncio.Task] = None
        self._templates: Dict[str, NotificationTemplate] = {}
        self._channel_configs: Dict[NotificationChannel, ChannelConfig] = {}
        self._rate_limits: Dict[str, List[datetime]] = defaultdict(list)
        self._handler_registry: Dict[NotificationChannel, Callable] = {}

        # Load configuration
        self.notification_config = self.config.get("notification_service", {})
        self.templates_path = Path(self.notification_config.get("templates_path", "./configs/notifications/templates"))
        self.channels_file = Path(self.notification_config.get("channels_file", "./configs/notifications/channels.yaml"))
        self.batch_size = self.notification_config.get("batch_size", 50)
        self.process_interval = self.notification_config.get("process_interval", 5)
        self.retry_interval = self.notification_config.get("retry_interval", 60)
        self.max_queue_size = self.notification_config.get("max_queue_size", 1000)

        # Load templates
        self._load_templates()

        # Load channel configs
        self._load_channel_configs()

        # Register default handlers
        self._register_default_handlers()

        # Start background tasks
        self._start_background_tasks()

        logger.info(f"NotificationService initialized with {len(self._templates)} templates")

    def _load_templates(self):
        """Load notification templates."""
        try:
            if self.templates_path.exists():
                # Load from template files
                env = Environment(loader=FileSystemLoader(str(self.templates_path)))
                
                for template_file in self.templates_path.glob("*.yaml"):
                    try:
                        with open(template_file, "r") as f:
                            data = yaml.safe_load(f)
                            for template_data in data.get("templates", []):
                                template = NotificationTemplate.from_dict(template_data)
                                # Load HTML/plain text template content
                                if "body_file" in template_data:
                                    body_file = self.templates_path / template_data["body_file"]
                                    if body_file.exists():
                                        with open(body_file, "r") as bf:
                                            template.body = bf.read()
                                self._templates[template.name] = template
                    except Exception as e:
                        logger.error(f"Error loading template {template_file}: {e}")
                logger.info(f"Loaded {len(self._templates)} templates from files")
            else:
                self._load_default_templates()
        except Exception as e:
            logger.error(f"Error loading templates: {e}")
            self._load_default_templates()

    def _load_default_templates(self):
        """Load default notification templates."""
        default_templates = [
            NotificationTemplate(
                name="alert_critical",
                subject="[CRITICAL] {{ title }}",
                body="""**CRITICAL ALERT**

{{ title }}

{{ message }}

Severity: {{ severity }}
Time: {{ timestamp }}
Source: {{ source }}

---
Nexus AI Trading System
""",
                channels=[NotificationChannel.SLACK, NotificationChannel.TELEGRAM, NotificationChannel.PAGERDUTY],
                priority=NotificationPriority.CRITICAL,
                description="Critical alert notification",
            ),
            NotificationTemplate(
                name="alert_error",
                subject="[ERROR] {{ title }}",
                body="""**ERROR ALERT**

{{ title }}

{{ message }}

Severity: {{ severity }}
Time: {{ timestamp }}
Source: {{ source }}

---
Nexus AI Trading System
""",
                channels=[NotificationChannel.SLACK, NotificationChannel.TELEGRAM],
                priority=NotificationPriority.HIGH,
                description="Error alert notification",
            ),
            NotificationTemplate(
                name="alert_warning",
                subject="[WARNING] {{ title }}",
                body="""**WARNING**

{{ title }}

{{ message }}

Time: {{ timestamp }}
Source: {{ source }}

---
Nexus AI Trading System
""",
                channels=[NotificationChannel.SLACK],
                priority=NotificationPriority.NORMAL,
                description="Warning notification",
            ),
            NotificationTemplate(
                name="trading_summary",
                subject="Trading Summary - {{ date }}",
                body="""**Trading Summary**

Date: {{ date }}
Total Trades: {{ total_trades }}
Win Rate: {{ win_rate }}%
Total PnL: ${{ total_pnl }}
Best Trade: ${{ best_trade }}
Worst Trade: ${{ worst_trade }}

---
Nexus AI Trading System
""",
                channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK],
                priority=NotificationPriority.NORMAL,
                description="Daily trading summary",
            ),
            NotificationTemplate(
                name="model_update",
                subject="Model Update - {{ model_id }}",
                body="""**Model Update**

Model: {{ model_id }}
Version: {{ version }}
Status: {{ status }}
Accuracy: {{ accuracy }}%
Loss: {{ loss }}

Deployment: {{ deployment }}

---
Nexus AI Trading System
""",
                channels=[NotificationChannel.SLACK, NotificationChannel.TELEGRAM],
                priority=NotificationPriority.NORMAL,
                description="Model update notification",
            ),
            NotificationTemplate(
                name="system_health",
                subject="System Health - {{ status }}",
                body="""**System Health Report**

Status: {{ status }}
CPU Usage: {{ cpu_usage }}%
Memory Usage: {{ memory_usage }}%
Disk Usage: {{ disk_usage }}%
Uptime: {{ uptime }}

Issues: {{ issues }}

---
Nexus AI Trading System
""",
                channels=[NotificationChannel.SLACK, NotificationChannel.EMAIL],
                priority=NotificationPriority.NORMAL,
                description="System health report",
            ),
            NotificationTemplate(
                name="trade_execution",
                subject="Trade Executed - {{ symbol }}",
                body="""**Trade Executed**

Symbol: {{ symbol }}
Side: {{ side }}
Quantity: {{ quantity }}
Price: ${{ price }}
Total: ${{ total }}
Status: {{ status }}

---
Nexus AI Trading System
""",
                channels=[NotificationChannel.SLACK, NotificationChannel.TELEGRAM],
                priority=NotificationPriority.HIGH,
                description="Trade execution notification",
            ),
        ]

        for template in default_templates:
            self._templates[template.name] = template

        logger.info(f"Loaded {len(self._templates)} default templates")

    def _load_channel_configs(self):
        """Load channel configurations."""
        try:
            if self.channels_file.exists():
                with open(self.channels_file, "r") as f:
                    data = yaml.safe_load(f)
                    for channel_data in data.get("channels", []):
                        channel = NotificationChannel(channel_data["channel"])
                        config = ChannelConfig(
                            channel=channel,
                            enabled=channel_data.get("enabled", True),
                            config=channel_data.get("config", {}),
                            rate_limit_per_minute=channel_data.get("rate_limit_per_minute", 60),
                            retry_delay_seconds=channel_data.get("retry_delay_seconds", 5),
                            max_retries=channel_data.get("max_retries", 3),
                        )
                        self._channel_configs[channel] = config
                logger.info(f"Loaded {len(self._channel_configs)} channel configs")
            else:
                self._load_default_channel_configs()
        except Exception as e:
            logger.error(f"Error loading channel configs: {e}")
            self._load_default_channel_configs()

    def _load_default_channel_configs(self):
        """Load default channel configurations."""
        default_configs = [
            ChannelConfig(
                channel=NotificationChannel.EMAIL,
                enabled=True,
                config={
                    "smtp_server": "smtp.gmail.com",
                    "smtp_port": 587,
                    "username": "",
                    "password": "",
                    "from_email": "",
                    "to_emails": [],
                },
                rate_limit_per_minute=60,
            ),
            ChannelConfig(
                channel=NotificationChannel.SLACK,
                enabled=True,
                config={
                    "webhook_url": "",
                    "channel": "",
                },
                rate_limit_per_minute=100,
            ),
            ChannelConfig(
                channel=NotificationChannel.TELEGRAM,
                enabled=True,
                config={
                    "bot_token": "",
                    "chat_id": "",
                },
                rate_limit_per_minute=30,
            ),
            ChannelConfig(
                channel=NotificationChannel.DISCORD,
                enabled=True,
                config={
                    "webhook_url": "",
                    "username": "Nexus Alerts",
                },
                rate_limit_per_minute=30,
            ),
        ]

        for config in default_configs:
            self._channel_configs[config.channel] = config

        logger.info(f"Loaded {len(self._channel_configs)} default channel configs")

    def _register_default_handlers(self):
        """Register default notification handlers."""
        self.register_handler(NotificationChannel.EMAIL, self._send_email)
        self.register_handler(NotificationChannel.SLACK, self._send_slack)
        self.register_handler(NotificationChannel.TELEGRAM, self._send_telegram)
        self.register_handler(NotificationChannel.DISCORD, self._send_discord)
        self.register_handler(NotificationChannel.PUSHOVER, self._send_pushover)
        self.register_handler(NotificationChannel.WEBHOOK, self._send_webhook)
        self.register_handler(NotificationChannel.PAGERDUTY, self._send_pagerduty)
        self.register_handler(NotificationChannel.OPSGENIE, self._send_opsgenie)

    def _start_background_tasks(self):
        """Start background tasks."""
        if self._processing_task is None:
            self._processing_task = asyncio.create_task(self._process_loop())

        if self._retry_task is None:
            self._retry_task = asyncio.create_task(self._retry_loop())

    async def _process_loop(self):
        """Background loop for processing notifications."""
        while True:
            try:
                await self._process_queue()
                await asyncio.sleep(self.process_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in process loop: {e}")
                await asyncio.sleep(5)

    async def _retry_loop(self):
        """Background loop for retrying failed notifications."""
        while True:
            try:
                await self._retry_failed()
                await asyncio.sleep(self.retry_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in retry loop: {e}")
                await asyncio.sleep(10)

    async def send_notification(
        self,
        title: str,
        message: str,
        template_name: Optional[str] = None,
        template_data: Optional[Dict[str, Any]] = None,
        priority: Optional[Union[NotificationPriority, str]] = None,
        channels: Optional[List[Union[NotificationChannel, str]]] = None,
        recipients: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Send a notification.

        Args:
            title: Notification title
            message: Notification message
            template_name: Optional template name
            template_data: Template data
            priority: Notification priority
            channels: Target channels
            recipients: Recipients
            metadata: Additional metadata
            tags: Notification tags

        Returns:
            Notification ID if sent, None otherwise
        """
        # Parse priority
        if priority:
            if isinstance(priority, str):
                priority = NotificationPriority(priority)
        else:
            priority = NotificationPriority.NORMAL

        # Parse channels
        if channels:
            parsed_channels = []
            for channel in channels:
                if isinstance(channel, str):
                    parsed_channels.append(NotificationChannel(channel))
                else:
                    parsed_channels.append(channel)
        else:
            parsed_channels = [NotificationChannel.SLACK, NotificationChannel.EMAIL]

        # Use template if specified
        if template_name and template_name in self._templates:
            template = self._templates[template_name]
            if template.priority.value in ["critical", "urgent"]:
                priority = template.priority

            # Merge channels
            if channels is None:
                parsed_channels = template.channels.copy()

            # Render template
            if template_data:
                rendered = await self._render_template(template_name, template_data)
                title = rendered.get("subject", title)
                message = rendered.get("body", message)

        # Create notification
        notification_id = f"notif_{int(datetime.utcnow().timestamp())}_{len(self._queue)}"
        notification = Notification(
            id=notification_id,
            title=title,
            message=message,
            template_name=template_name,
            template_data=template_data or {},
            priority=priority,
            channels=parsed_channels,
            recipients=recipients or [],
            metadata=metadata or {},
            tags=tags or [],
        )

        # Add to queue
        async with self._lock:
            if len(self._queue) >= self.max_queue_size:
                logger.warning(f"Notification queue full, dropping notification {notification_id}")
                return None

            self._queue.append(notification)
            NOTIFICATION_QUEUE_SIZE.set(len(self._queue))

        logger.info(f"Notification {notification_id} queued with priority {priority.value}")

        return notification_id

    async def send_notification_now(
        self,
        title: str,
        message: str,
        **kwargs,
    ) -> bool:
        """
        Send notification immediately without queuing.

        Args:
            title: Notification title
            message: Notification message
            **kwargs: Additional notification parameters

        Returns:
            True if sent successfully
        """
        notification_id = await self.send_notification(title, message, **kwargs)

        if notification_id:
            # Process immediately
            async with self._lock:
                for i, notif in enumerate(self._queue):
                    if notif.id == notification_id:
                        await self._process_single(notif)
                        self._queue.pop(i)
                        break

            return True

        return False

    async def _process_queue(self):
        """Process queued notifications."""
        if not self._queue:
            return

        async with self._lock:
            # Get batch
            batch = self._queue[:self.batch_size]

            # Process each notification
            for notification in batch:
                try:
                    await self._process_single(notification)
                    self._queue.remove(notification)
                except Exception as e:
                    logger.error(f"Error processing notification {notification.id}: {e}")
                    notification.status = "failed"
                    notification.retry_count += 1

            NOTIFICATION_QUEUE_SIZE.set(len(self._queue))

    async def _process_single(self, notification: Notification):
        """
        Process a single notification.

        Args:
            notification: Notification to process
        """
        if notification.status in ["sent", "failed"]:
            return

        # Determine channels to use
        channels = notification.channels or [NotificationChannel.SLACK, NotificationChannel.EMAIL]

        # Filter enabled channels
        enabled_channels = []
        for channel in channels:
            config = self._channel_configs.get(channel)
            if config and config.enabled:
                enabled_channels.append(channel)

        if not enabled_channels:
            logger.warning(f"No enabled channels for notification {notification.id}")
            return

        # Send to each channel
        success_count = 0
        for channel in enabled_channels:
            try:
                # Check rate limit
                if not await self._check_rate_limit(channel):
                    logger.warning(f"Rate limit exceeded for channel {channel.value}")
                    continue

                # Send notification
                handler = self._handler_registry.get(channel)
                if not handler:
                    logger.warning(f"No handler for channel {channel.value}")
                    continue

                if asyncio.iscoroutinefunction(handler):
                    await handler(notification, channel)
                else:
                    handler(notification, channel)

                success_count += 1

                NOTIFICATION_COUNTER.labels(
                    channel=channel.value,
                    status="success",
                    template=notification.template_name or "custom",
                ).inc()

            except Exception as e:
                logger.error(f"Error sending to channel {channel.value}: {e}")
                NOTIFICATION_COUNTER.labels(
                    channel=channel.value,
                    status="error",
                    template=notification.template_name or "custom",
                ).inc()

        # Update notification status
        if success_count > 0:
            notification.status = "sent"
            notification.sent_at = datetime.utcnow()
        elif notification.retry_count >= notification.max_retries:
            notification.status = "failed"
        else:
            notification.status = "pending"

    async def _retry_failed(self):
        """Retry failed notifications."""
        failed_notifications = []

        async with self._lock:
            for notification in self._queue:
                if notification.status == "failed" and notification.retry_count < notification.max_retries:
                    notification.status = "pending"
                    failed_notifications.append(notification)

            if failed_notifications:
                logger.info(f"Retrying {len(failed_notifications)} failed notifications")

    async def _render_template(
        self,
        template_name: str,
        data: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Render a template with data.

        Args:
            template_name: Template name
            data: Template data

        Returns:
            Rendered template
        """
        template = self._templates.get(template_name)

        if not template:
            return {"subject": "", "body": ""}

        try:
            # Use Jinja2 for rendering
            env = Environment(
                loader=FileSystemLoader(str(self.templates_path)),
                autoescape=True,
            )

            # Add default data
            template_data = {
                "timestamp": datetime.utcnow().isoformat(),
                **data,
            }

            # Render subject
            subject_template = env.from_string(template.subject)
            subject = subject_template.render(**template_data)

            # Render body
            body_template = env.from_string(template.body)
            body = body_template.render(**template_data)

            return {"subject": subject, "body": body}

        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {e}")
            return {"subject": template.subject, "body": template.body}

    async def _check_rate_limit(self, channel: NotificationChannel) -> bool:
        """
        Check if channel rate limit is exceeded.

        Args:
            channel: Channel to check

        Returns:
            True if not exceeded
        """
        config = self._channel_configs.get(channel)
        if not config:
            return True

        # Clean old timestamps
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)

        self._rate_limits[channel.value] = [
            ts for ts in self._rate_limits[channel.value]
            if ts > cutoff
        ]

        # Check limit
        if len(self._rate_limits[channel.value]) >= config.rate_limit_per_minute:
            return False

        # Add timestamp
        self._rate_limits[channel.value].append(now)

        return True

    def register_handler(self, channel: NotificationChannel, handler: Callable):
        """
        Register a notification handler.

        Args:
            channel: Channel for handler
            handler: Handler function
        """
        self._handler_registry[channel] = handler
        logger.info(f"Registered handler for channel {channel.value}")

    # Channel Handlers

    async def _send_email(self, notification: Notification, channel: NotificationChannel):
        """Send email notification."""
        config = self._channel_configs.get(channel)

        if not config:
            return

        smtp_config = config.config
        recipients = notification.recipients or smtp_config.get("to_emails", [])

        if not recipients:
            logger.warning(f"No recipients for email notification {notification.id}")
            return

        msg = MIMEMultipart()
        msg["From"] = smtp_config.get("from_email")
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = notification.title

        # Use HTML template if available
        body = notification.message
        if notification.template_name:
            try:
                template_file = self.templates_path / f"{notification.template_name}.html"
                if template_file.exists():
                    with open(template_file, "r") as f:
                        html_template = f.read()
                        env = Environment(loader=FileSystemLoader(str(self.templates_path.parent)))
                        template = env.from_string(html_template)
                        body = template.render(**notification.template_data)
            except Exception as e:
                logger.warning(f"Error loading HTML template: {e}")

        msg.attach(MIMEText(body, "html" if "<html" in body else "plain"))

        try:
            with smtplib.SMTP(smtp_config.get("smtp_server"), smtp_config.get("smtp_port", 587)) as server:
                server.starttls()
                server.login(
                    smtp_config.get("username"),
                    smtp_config.get("password"),
                )
                server.send_message(msg)

            logger.debug(f"Email sent to {recipients}")

        except Exception as e:
            logger.error(f"Error sending email: {e}")
            raise

    async def _send_slack(self, notification: Notification, channel: NotificationChannel):
        """Send Slack notification."""
        config = self._channel_configs.get(channel)

        if not config:
            return

        slack_config = config.config
        webhook_url = slack_config.get("webhook_url")

        if not webhook_url:
            logger.warning(f"No webhook URL for Slack notification {notification.id}")
            return

        # Determine color based on priority
        color_map = {
            NotificationPriority.LOW: "#36a64f",
            NotificationPriority.NORMAL: "#36a64f",
            NotificationPriority.HIGH: "#ffcc00",
            NotificationPriority.URGENT: "#ff6600",
            NotificationPriority.CRITICAL: "#ff0000",
        }

        color = color_map.get(notification.priority, "#36a64f")

        payload = {
            "channel": slack_config.get("channel"),
            "username": slack_config.get("username", "Nexus AI Trading"),
            "attachments": [
                {
                    "color": color,
                    "title": notification.title,
                    "text": notification.message,
                    "fields": [
                        {
                            "title": "Priority",
                            "value": notification.priority.value.upper(),
                            "short": True,
                        },
                        {
                            "title": "ID",
                            "value": notification.id,
                            "short": True,
                        },
                        {
                            "title": "Time",
                            "value": notification.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                            "short": True,
                        },
                    ],
                    "footer": "Nexus AI Trading System",
                    "ts": int(notification.created_at.timestamp()),
                }
            ],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status not in [200, 204]:
                    logger.error(f"Slack webhook returned {response.status}")

    async def _send_telegram(self, notification: Notification, channel: NotificationChannel):
        """Send Telegram notification."""
        config = self._channel_configs.get(channel)

        if not config:
            return

        telegram_config = config.config
        bot_token = telegram_config.get("bot_token")
        chat_id = telegram_config.get("chat_id")

        if not bot_token or not chat_id:
            logger.warning(f"Missing bot_token or chat_id for Telegram notification {notification.id}")
            return

        # Format message
        priority_emoji = {
            NotificationPriority.LOW: "ℹ️",
            NotificationPriority.NORMAL: "ℹ️",
            NotificationPriority.HIGH: "⚠️",
            NotificationPriority.URGENT: "🚨",
            NotificationPriority.CRITICAL: "🔥",
        }

        emoji = priority_emoji.get(notification.priority, "ℹ️")

        message = f"""
{emoji} *{notification.title}*

{notification.message}

🆔 *ID:* {notification.id}
⏰ *Time:* {notification.created_at.strftime("%Y-%m-%d %H:%M:%S")}
🎯 *Priority:* {notification.priority.value.upper()}
"""

        if notification.tags:
            message += f"🏷️ *Tags:* {', '.join(notification.tags)}\n"

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

    async def _send_discord(self, notification: Notification, channel: NotificationChannel):
        """Send Discord notification."""
        config = self._channel_configs.get(channel)

        if not config:
            return

        discord_config = config.config
        webhook_url = discord_config.get("webhook_url")

        if not webhook_url:
            logger.warning(f"No webhook URL for Discord notification {notification.id}")
            return

        # Determine color based on priority
        color_map = {
            NotificationPriority.LOW: 3066993,
            NotificationPriority.NORMAL: 3066993,
            NotificationPriority.HIGH: 16776960,
            NotificationPriority.URGENT: 15105570,
            NotificationPriority.CRITICAL: 15158332,
        }

        color = color_map.get(notification.priority, 3066993)

        payload = {
            "username": discord_config.get("username", "Nexus AI Trading"),
            "embeds": [
                {
                    "title": notification.title,
                    "description": notification.message[:2000],
                    "color": color,
                    "fields": [
                        {
                            "name": "Priority",
                            "value": notification.priority.value.upper(),
                            "inline": True,
                        },
                        {
                            "name": "ID",
                            "value": notification.id,
                            "inline": True,
                        },
                        {
                            "name": "Time",
                            "value": notification.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                            "inline": True,
                        },
                    ],
                    "footer": {"text": "Nexus AI Trading System"},
                    "timestamp": notification.created_at.isoformat(),
                }
            ],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status != 204:
                    logger.error(f"Discord webhook returned {response.status}")

    async def _send_pushover(self, notification: Notification, channel: NotificationChannel):
        """Send Pushover notification."""
        config = self._channel_configs.get(channel)

        if not config:
            return

        pushover_config = config.config
        api_token = pushover_config.get("api_token")
        user_key = pushover_config.get("user_key")

        if not api_token or not user_key:
            logger.warning(f"Missing api_token or user_key for Pushover notification {notification.id}")
            return

        # Determine priority based on notification priority
        priority_map = {
            NotificationPriority.LOW: -1,
            NotificationPriority.NORMAL: 0,
            NotificationPriority.HIGH: 0,
            NotificationPriority.URGENT: 1,
            NotificationPriority.CRITICAL: 2,
        }

        priority = priority_map.get(notification.priority, 0)

        payload = {
            "token": api_token,
            "user": user_key,
            "title": notification.title,
            "message": notification.message[:500],
            "priority": priority,
            "timestamp": int(notification.created_at.timestamp()),
        }

        url = "https://api.pushover.net/1/messages.json"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload) as response:
                if response.status != 200:
                    logger.error(f"Pushover API returned {response.status}")

    async def _send_webhook(self, notification: Notification, channel: NotificationChannel):
        """Send webhook notification."""
        config = self._channel_configs.get(channel)

        if not config:
            return

        webhook_config = config.config
        webhook_url = webhook_config.get("webhook_url")
        method = webhook_config.get("method", "POST")
        headers = webhook_config.get("headers", {})

        if not webhook_url:
            logger.warning(f"No webhook URL for webhook notification {notification.id}")
            return

        payload = {
            "id": notification.id,
            "title": notification.title,
            "message": notification.message,
            "priority": notification.priority.value,
            "created_at": notification.created_at.isoformat(),
            "tags": notification.tags,
            "metadata": notification.metadata,
        }

        async with aiohttp.ClientSession() as session:
            async with session.request(method, webhook_url, json=payload, headers=headers) as response:
                if response.status >= 400:
                    logger.error(f"Webhook returned {response.status}")

    async def _send_pagerduty(self, notification: Notification, channel: NotificationChannel):
        """Send PagerDuty notification."""
        config = self._channel_configs.get(channel)

        if not config:
            return

        pd_config = config.config
        integration_key = pd_config.get("integration_key")

        if not integration_key:
            logger.warning(f"No integration_key for PagerDuty notification {notification.id}")
            return

        # Determine urgency
        urgency = "high" if notification.priority in [NotificationPriority.URGENT, NotificationPriority.CRITICAL] else "low"

        payload = {
            "payload": {
                "summary": notification.title,
                "source": "Nexus AI Trading System",
                "severity": notification.priority.value,
                "timestamp": notification.created_at.isoformat(),
                "component": "trading",
                "group": "notifications",
                "custom_details": {
                    "notification_id": notification.id,
                    "message": notification.message,
                    "tags": notification.tags,
                    "metadata": notification.metadata,
                },
            },
            "routing_key": integration_key,
            "event_action": "trigger",
            "dedup_key": f"nexus_{notification.id}",
        }

        url = "https://events.pagerduty.com/v2/enqueue"
        headers = {"Content-Type": "application/json"}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status != 202:
                    logger.error(f"PagerDuty API returned {response.status}")

    async def _send_opsgenie(self, notification: Notification, channel: NotificationChannel):
        """Send OpsGenie notification."""
        config = self._channel_configs.get(channel)

        if not config:
            return

        og_config = config.config
        api_key = og_config.get("api_key")
        integration_key = og_config.get("integration_key")

        if not api_key and not integration_key:
            logger.warning(f"Missing api_key for OpsGenie notification {notification.id}")
            return

        # Determine priority
        priority_map = {
            NotificationPriority.LOW: "P4",
            NotificationPriority.NORMAL: "P3",
            NotificationPriority.HIGH: "P3",
            NotificationPriority.URGENT: "P2",
            NotificationPriority.CRITICAL: "P1",
        }

        priority = priority_map.get(notification.priority, "P3")

        payload = {
            "message": notification.title,
            "alias": f"nexus_{notification.id}",
            "description": notification.message,
            "priority": priority,
            "source": "Nexus AI Trading System",
            "tags": notification.tags or [],
            "details": {
                "notification_id": notification.id,
                "metadata": notification.metadata,
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

    async def get_queue_status(self) -> Dict[str, Any]:
        """
        Get notification queue status.

        Returns:
            Queue status
        """
        async with self._lock:
            total = len(self._queue)
            pending = sum(1 for n in self._queue if n.status == "pending")
            failed = sum(1 for n in self._queue if n.status == "failed")

            return {
                "total": total,
                "pending": pending,
                "failed": failed,
                "max_size": self.max_queue_size,
                "utilization": (total / self.max_queue_size) * 100 if self.max_queue_size > 0 else 0,
            }

    async def get_templates(self) -> List[Dict[str, Any]]:
        """
        Get all notification templates.

        Returns:
            List of templates
        """
        return [t.to_dict() for t in self._templates.values()]

    async def add_template(self, template: NotificationTemplate) -> bool:
        """
        Add a new template.

        Args:
            template: Template to add

        Returns:
            True if added
        """
        async with self._lock:
            if template.name in self._templates:
                return False

            self._templates[template.name] = template
            await self._save_templates()
            logger.info(f"Added template: {template.name}")
            return True

    async def update_template(self, name: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing template.

        Args:
            name: Template name
            updates: Updates to apply

        Returns:
            True if updated
        """
        async with self._lock:
            if name not in self._templates:
                return False

            template = self._templates[name]

            for key, value in updates.items():
                if key == "channels":
                    value = [NotificationChannel(c) for c in value]
                elif key == "priority":
                    value = NotificationPriority(value)
                setattr(template, key, value)

            await self._save_templates()
            logger.info(f"Updated template: {name}")
            return True

    async def _save_templates(self):
        """Save templates to file."""
        try:
            data = {
                "templates": [
                    {
                        "name": t.name,
                        "subject": t.subject,
                        "body": t.body,
                        "channels": [c.value for c in t.channels],
                        "priority": t.priority.value,
                        "enabled": t.enabled,
                        "description": t.description,
                        "tags": t.tags,
                    }
                    for t in self._templates.values()
                ]
            }

            self.templates_path.mkdir(parents=True, exist_ok=True)
            with open(self.templates_path / "templates.yaml", "w") as f:
                yaml.dump(data, f, default_flow_style=False)

        except Exception as e:
            logger.error(f"Error saving templates: {e}")

    async def shutdown(self):
        """Shutdown the notification service."""
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass

        # Process remaining queue
        if self._queue:
            await self._process_queue()

        logger.info("NotificationService shut down")


# Export singleton
notification_service = NotificationService()
