# trading/bots/hedge_bot/monitoring/notification_service.py

"""
NEXUS HEDGE BOT - NOTIFICATION SERVICE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced notification service with multi-channel support, templating,
scheduling, and delivery tracking.

Version: 3.0.0
"""

import asyncio
import base64
import hashlib
import hmac
import json
import smtplib
import socket
import ssl
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from urllib.parse import urlparse

import aiohttp
import aiofiles
import structlog
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field, validator
import redis.asyncio as redis_async
from redis.asyncio import Redis

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class NotificationChannel(str, Enum):
    """Supported notification channels."""
    SLACK = "slack"
    TELEGRAM = "telegram"
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    DISCORD = "discord"
    PAGERDUTY = "pagerduty"
    OPSGENIE = "opsgenie"
    VICTOROPS = "victorops"
    MICROSOFT_TEAMS = "microsoft_teams"


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    URGENT = "urgent"


class NotificationStatus(str, Enum):
    """Notification delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRY = "retry"
    CANCELLED = "cancelled"


class NotificationTemplateType(str, Enum):
    """Types of notification templates."""
    ALERT = "alert"
    REPORT = "report"
    SUMMARY = "summary"
    WARNING = "warning"
    INFO = "info"
    CONFIRMATION = "confirmation"
    CUSTOM = "custom"


# === DATA MODELS ===

@dataclass
class Notification:
    """Notification data model."""
    notification_id: str = field(default_factory=lambda: f"NOT-{datetime.utcnow().strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}")
    title: str = ""
    message: str = ""
    channel: NotificationChannel = NotificationChannel.EMAIL
    priority: NotificationPriority = NotificationPriority.MEDIUM
    status: NotificationStatus = NotificationStatus.PENDING
    recipients: List[str] = field(default_factory=list)
    template_type: Optional[NotificationTemplateType] = None
    template_data: Dict[str, Any] = field(default_factory=dict)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "channel": self.channel.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "template_type": self.template_type.value if self.template_type else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Notification":
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("sent_at"):
            data["sent_at"] = datetime.fromisoformat(data["sent_at"])
        if data.get("delivered_at"):
            data["delivered_at"] = datetime.fromisoformat(data["delivered_at"])
        data["channel"] = NotificationChannel(data["channel"])
        data["priority"] = NotificationPriority(data["priority"])
        data["status"] = NotificationStatus(data["status"])
        if data.get("template_type"):
            data["template_type"] = NotificationTemplateType(data["template_type"])
        return cls(**data)


@dataclass
class NotificationTemplate:
    """Notification template."""
    template_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    template_type: NotificationTemplateType = NotificationTemplateType.CUSTOM
    channel: NotificationChannel = NotificationChannel.EMAIL
    subject: str = ""
    body: str = ""
    html_body: Optional[str] = None
    variables: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "template_type": self.template_type.value,
            "channel": self.channel.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotificationTemplate":
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        data["template_type"] = NotificationTemplateType(data["template_type"])
        data["channel"] = NotificationChannel(data["channel"])
        return cls(**data)


# === NOTIFICATION SERVICE ===

class NotificationService:
    """
    Advanced notification service with multi-channel support, templating,
    scheduling, and delivery tracking.
    """

    def __init__(
        self,
        config: Union[Dict[str, Any], str],
        redis_client: Optional[Redis] = None,
    ):
        """
        Initialize the NotificationService.

        Args:
            config: Configuration dictionary or path to config file
            redis_client: Optional Redis client for distributed operations
        """
        if isinstance(config, str):
            with open(config, "r") as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = config

        self.redis_client = redis_client
        self._lock = threading.RLock()
        self._closed = False

        # Database for persistent storage
        self._db_path = Path(self.config.get("db_path", "notifications.db"))
        self._initialize_db()

        # Templates
        self._templates: Dict[str, NotificationTemplate] = {}
        self._template_env = self._create_template_engine()
        self._load_templates()

        # Channel configurations
        self._channel_configs = self.config.get("channels", {})

        # Rate limiting
        self._rate_limits: Dict[str, List[datetime]] = {}
        self._rate_limit_config = self.config.get("rate_limits", {
            "slack": 60,  # messages per minute
            "telegram": 30,
            "email": 100,
            "sms": 20,
            "webhook": 120,
        })

        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._queue_task: Optional[asyncio.Task] = None
        self._retry_task: Optional[asyncio.Task] = None

        # Notification queue
        self._queue: asyncio.Queue = asyncio.Queue()

        # Start background tasks
        self._start_background_tasks()

        logger.info(
            "notification_service_initialized",
            db_path=str(self._db_path),
            channels=list(self._channel_configs.keys()),
            templates=len(self._templates),
        )

    def _initialize_db(self) -> None:
        """Initialize the SQLite database."""
        self._db = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            isolation_level=None,
        )
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")

        self._db.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                channel TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                recipients TEXT,
                template_type TEXT,
                template_data TEXT,
                attachments TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL,
                sent_at TEXT,
                delivered_at TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                error_message TEXT,
                tags TEXT,
                correlation_id TEXT
            )
        """)

        self._db.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                template_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                template_type TEXT NOT NULL,
                channel TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                html_body TEXT,
                variables TEXT,
                tags TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                enabled INTEGER DEFAULT 1
            )
        """)

        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_channel ON notifications(channel)
        """)

        logger.info("notification_db_initialized", db_path=str(self._db_path))

    def _create_template_engine(self) -> Environment:
        """Create Jinja2 template engine."""
        templates_dir = self.config.get("templates_dir", "templates")
        templates_path = Path(templates_dir)
        templates_path.mkdir(parents=True, exist_ok=True)

        return Environment(
            loader=FileSystemLoader(str(templates_path)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def _load_templates(self) -> None:
        """Load notification templates."""
        # Load from config
        for template_data in self.config.get("templates", []):
            template = NotificationTemplate.from_dict(template_data)
            self._templates[template.name] = template
            self._save_template(template)

        # Load from filesystem
        templates_dir = self.config.get("templates_dir", "templates")
        templates_path = Path(templates_dir)

        for template_file in templates_path.glob("*.yaml"):
            try:
                with open(template_file, "r") as f:
                    data = yaml.safe_load(f)
                    template = NotificationTemplate.from_dict(data)
                    self._templates[template.name] = template
                    self._save_template(template)
            except Exception as e:
                logger.error("template_load_error", file=str(template_file), error=str(e))

        logger.info("templates_loaded", count=len(self._templates))

    def _save_template(self, template: NotificationTemplate) -> None:
        """Save template to database."""
        self._db.execute("""
            INSERT OR REPLACE INTO templates (
                template_id, name, template_type, channel, subject, body,
                html_body, variables, tags, created_at, updated_at, enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            template.template_id,
            template.name,
            template.template_type.value,
            template.channel.value,
            template.subject,
            template.body,
            template.html_body,
            json.dumps(template.variables),
            json.dumps(template.tags),
            template.created_at.isoformat(),
            template.updated_at.isoformat(),
            1 if template.enabled else 0,
        ))

    def _start_background_tasks(self) -> None:
        """Start background tasks."""
        try:
            loop = asyncio.get_event_loop()

            # Queue processing task
            self._queue_task = loop.create_task(self._process_queue())

            # Retry task
            self._retry_task = loop.create_task(self._retry_loop())

            logger.info("background_tasks_started")
        except RuntimeError:
            logger.warning("no_event_loop_available_background_tasks_disabled")

    async def _process_queue(self) -> None:
        """Process notification queue."""
        while not self._closed:
            try:
                notification = await self._queue.get()
                await self._send_notification(notification)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("queue_processing_error", error=str(e))
                await asyncio.sleep(1)

    async def _retry_loop(self) -> None:
        """Retry failed notifications."""
        while not self._closed:
            try:
                await asyncio.sleep(self.config.get("retry_interval", 60))

                # Get failed notifications from database
                cursor = self._db.execute("""
                    SELECT * FROM notifications
                    WHERE status = ? AND retry_count < max_retries
                    ORDER BY created_at ASC
                    LIMIT 100
                """, (NotificationStatus.FAILED.value,))

                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                for row in rows:
                    data = dict(zip(columns, row))
                    data = self._deserialize_notification_data(data)
                    notification = Notification.from_dict(data)

                    # Check if retry is needed
                    if notification.sent_at:
                        retry_after = self.config.get("retry_delay", 300)
                        if (datetime.utcnow() - notification.sent_at).total_seconds() < retry_after:
                            continue

                    notification.retry_count += 1
                    notification.status = NotificationStatus.RETRY
                    self._update_notification(notification)

                    # Re-queue
                    await self._queue.put(notification)

                    logger.info(
                        "notification_retry",
                        notification_id=notification.notification_id,
                        retry_count=notification.retry_count,
                    )

            except Exception as e:
                logger.error("retry_loop_error", error=str(e))
                await asyncio.sleep(5)

    async def send(
        self,
        title: str,
        message: str,
        channel: Union[str, NotificationChannel] = NotificationChannel.EMAIL,
        priority: Union[str, NotificationPriority] = NotificationPriority.MEDIUM,
        recipients: Optional[List[str]] = None,
        template_type: Optional[Union[str, NotificationTemplateType]] = None,
        template_data: Optional[Dict[str, Any]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        correlation_id: Optional[str] = None,
        use_template: Optional[str] = None,
        delay_seconds: int = 0,
    ) -> Notification:
        """
        Send a notification.

        Args:
            title: Notification title
            message: Notification message
            channel: Notification channel
            priority: Notification priority
            recipients: List of recipients
            template_type: Template type
            template_data: Template data
            attachments: Attachments
            metadata: Additional metadata
            tags: Notification tags
            correlation_id: Correlation ID
            use_template: Template name to use
            delay_seconds: Delay before sending

        Returns:
            Notification object
        """
        if isinstance(channel, str):
            channel = NotificationChannel(channel)
        if isinstance(priority, str):
            priority = NotificationPriority(priority)
        if isinstance(template_type, str):
            template_type = NotificationTemplateType(template_type)

        # Use template if specified
        if use_template and use_template in self._templates:
            template = self._templates[use_template]
            rendered = self._render_template(template, template_data or {})
            title = rendered.get("subject", title)
            message = rendered.get("body", message)
            channel = template.channel
            if template_type is None:
                template_type = template.template_type

        notification = Notification(
            title=title,
            message=message,
            channel=channel,
            priority=priority,
            recipients=recipients or [],
            template_type=template_type,
            template_data=template_data or {},
            attachments=attachments or [],
            metadata=metadata or {},
            tags=tags or [],
            correlation_id=correlation_id,
        )

        # Save to database
        self._save_notification(notification)

        # Send immediately if no delay
        if delay_seconds <= 0:
            asyncio.create_task(self._send_notification(notification))
        else:
            # Schedule for later
            asyncio.create_task(self._schedule_delayed(notification, delay_seconds))

        logger.info(
            "notification_queued",
            notification_id=notification.notification_id,
            channel=channel.value,
            priority=priority.value,
            title=title[:50],
        )

        return notification

    async def _schedule_delayed(self, notification: Notification, delay_seconds: int) -> None:
        """Schedule a delayed notification."""
        await asyncio.sleep(delay_seconds)
        await self._queue.put(notification)

    async def _send_notification(self, notification: Notification) -> None:
        """Send a notification through the appropriate channel."""
        notification.status = NotificationStatus.SENDING

        try:
            # Check rate limit
            if not self._check_rate_limit(notification.channel):
                notification.status = NotificationStatus.RETRY
                notification.error_message = "Rate limit exceeded"
                self._update_notification(notification)

                # Re-queue after delay
                await asyncio.sleep(5)
                await self._queue.put(notification)
                return

            # Send through channel
            if notification.channel == NotificationChannel.SLACK:
                await self._send_slack(notification)
            elif notification.channel == NotificationChannel.TELEGRAM:
                await self._send_telegram(notification)
            elif notification.channel == NotificationChannel.EMAIL:
                await self._send_email(notification)
            elif notification.channel == NotificationChannel.WEBHOOK:
                await self._send_webhook(notification)
            elif notification.channel == NotificationChannel.DISCORD:
                await self._send_discord(notification)
            elif notification.channel == NotificationChannel.PAGERDUTY:
                await self._send_pagerduty(notification)
            elif notification.channel == NotificationChannel.OPSGENIE:
                await self._send_opsgenie(notification)
            elif notification.channel == NotificationChannel.MICROSOFT_TEAMS:
                await self._send_teams(notification)
            else:
                raise ValueError(f"Unsupported channel: {notification.channel}")

            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.utcnow()
            notification.delivered_at = datetime.utcnow()
            notification.error_message = None

            logger.info(
                "notification_sent",
                notification_id=notification.notification_id,
                channel=notification.channel.value,
            )

        except Exception as e:
            notification.status = NotificationStatus.FAILED
            notification.error_message = str(e)

            logger.error(
                "notification_failed",
                notification_id=notification.notification_id,
                channel=notification.channel.value,
                error=str(e),
            )

            # Retry if possible
            if notification.retry_count < notification.max_retries:
                notification.status = NotificationStatus.RETRY
                notification.retry_count += 1
                await asyncio.sleep(5)
                await self._queue.put(notification)

        finally:
            self._update_notification(notification)

    def _render_template(
        self,
        template: NotificationTemplate,
        data: Dict[str, Any],
    ) -> Dict[str, str]:
        """Render a template with data."""
        try:
            subject = self._template_env.from_string(template.subject)
            body = self._template_env.from_string(template.body)

            result = {
                "subject": subject.render(**data),
                "body": body.render(**data),
            }

            if template.html_body:
                html = self._template_env.from_string(template.html_body)
                result["html_body"] = html.render(**data)

            return result

        except Exception as e:
            logger.error("template_render_error", template=template.name, error=str(e))
            return {"subject": template.subject, "body": template.body}

    async def _send_slack(self, notification: Notification) -> None:
        """Send notification to Slack."""
        config = self._channel_configs.get("slack", {})
        webhook_url = config.get("webhook_url")

        if not webhook_url:
            raise ValueError("Slack webhook URL not configured")

        # Prepare message
        color = {
            NotificationPriority.LOW: "#36a64f",
            NotificationPriority.MEDIUM: "#36a64f",
            NotificationPriority.HIGH: "#ffaa00",
            NotificationPriority.CRITICAL: "#ff4466",
            NotificationPriority.URGENT: "#ff0000",
        }.get(notification.priority, "#36a64f")

        message = {
            "attachments": [
                {
                    "color": color,
                    "title": notification.title,
                    "text": notification.message,
                    "fields": [
                        {"title": "Priority", "value": notification.priority.value.upper(), "short": True},
                        {"title": "Channel", "value": notification.channel.value, "short": True},
                    ],
                    "footer": f"NEXUS Notification Service v3.0.0 | {notification.notification_id}",
                    "ts": int(notification.created_at.timestamp()),
                }
            ]
        }

        if notification.metadata:
            details = "\n".join([f"• {k}: {v}" for k, v in notification.metadata.items()])
            message["attachments"][0]["fields"].append({
                "title": "Details",
                "value": details[:500],
                "short": False,
            })

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=message, timeout=10) as response:
                if response.status not in (200, 201, 204):
                    error = await response.text()
                    raise Exception(f"Slack returned status {response.status}: {error}")

    async def _send_telegram(self, notification: Notification) -> None:
        """Send notification to Telegram."""
        config = self._channel_configs.get("telegram", {})
        bot_token = config.get("bot_token")
        chat_id = config.get("chat_id")

        if not bot_token or not chat_id:
            raise ValueError("Telegram bot token or chat ID not configured")

        emoji = {
            NotificationPriority.LOW: "ℹ️",
            NotificationPriority.MEDIUM: "ℹ️",
            NotificationPriority.HIGH: "⚠️",
            NotificationPriority.CRITICAL: "🚨",
            NotificationPriority.URGENT: "🔥",
        }.get(notification.priority, "ℹ️")

        message = f"{emoji} *{notification.title}*\n"
        message += f"_Priority:_ {notification.priority.value.upper()}\n"
        message += f"\n{notification.message}\n"

        if notification.metadata:
            message += "\n*Details:*\n"
            for k, v in notification.metadata.items():
                message += f"• {k}: {v}\n"

        message += f"\n`{notification.notification_id}`"

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as response:
                if response.status != 200:
                    error = await response.text()
                    raise Exception(f"Telegram returned status {response.status}: {error}")

    async def _send_email(self, notification: Notification) -> None:
        """Send notification via email."""
        config = self._channel_configs.get("email", {})
        smtp_host = config.get("smtp_host")
        smtp_port = config.get("smtp_port", 587)
        smtp_user = config.get("smtp_user")
        smtp_password = config.get("smtp_password")
        from_email = config.get("from_email")
        to_emails = notification.recipients or config.get("to_emails", [])

        if not all([smtp_host, smtp_user, smtp_password, from_email, to_emails]):
            raise ValueError("Email configuration incomplete")

        if isinstance(to_emails, str):
            to_emails = [to_emails]

        # Create email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{notification.priority.value.upper()}] {notification.title}"
        msg["From"] = from_email
        msg["To"] = ", ".join(to_emails)

        # Plain text version
        text = f"""
        Notification ID: {notification.notification_id}
        Priority: {notification.priority.value.upper()}
        Channel: {notification.channel.value}
        Created: {notification.created_at.isoformat()}

        {notification.title}
        {'=' * len(notification.title)}

        {notification.message}

        Details:
        {json.dumps(notification.metadata, indent=2) if notification.metadata else 'None'}

        NEXUS Hedge Bot Notification Service v3.0.0
        """

        # HTML version
        html = f"""
        <html>
        <body>
        <h2 style="color: {'#ff0000' if notification.priority in (NotificationPriority.CRITICAL, NotificationPriority.URGENT) else '#ffaa00' if notification.priority == NotificationPriority.HIGH else '#36a64f'};">
            {notification.title}
        </h2>
        <table>
            <tr><td><strong>ID:</strong></td><td>{notification.notification_id}</td></tr>
            <tr><td><strong>Priority:</strong></td><td>{notification.priority.value.upper()}</td></tr>
            <tr><td><strong>Channel:</strong></td><td>{notification.channel.value}</td></tr>
            <tr><td><strong>Created:</strong></td><td>{notification.created_at.isoformat()}</td></tr>
        </table>
        <p><strong>Message:</strong></p>
        <p>{notification.message}</p>
        """

        if notification.metadata:
            html += "<p><strong>Details:</strong></p>"
            html += "<ul>"
            for k, v in notification.metadata.items():
                html += f"<li><strong>{k}:</strong> {v}</li>"
            html += "</ul>"

        html += """
        <p style="color: #666; font-size: 12px; margin-top: 20px;">
            NEXUS Hedge Bot Notification Service v3.0.0
        </p>
        </body>
        </html>
        """

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        # Add attachments if any
        for attachment in notification.attachments:
            if "content" in attachment and "filename" in attachment:
                part = MIMEApplication(
                    base64.b64decode(attachment["content"]),
                    Name=attachment["filename"]
                )
                part["Content-Disposition"] = f'attachment; filename="{attachment["filename"]}"'
                msg.attach(part)

        # Send email
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, to_emails, msg.as_string())

    async def _send_webhook(self, notification: Notification) -> None:
        """Send notification via webhook."""
        config = self._channel_configs.get("webhook", {})
        webhook_url = config.get("webhook_url")
        method = config.get("method", "POST")
        headers = config.get("headers", {})

        if not webhook_url:
            raise ValueError("Webhook URL not configured")

        payload = notification.to_dict()

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method,
                url=webhook_url,
                json=payload,
                headers=headers,
                timeout=10,
            ) as response:
                if response.status not in (200, 201, 202, 204):
                    error = await response.text()
                    raise Exception(f"Webhook returned status {response.status}: {error}")

    async def _send_discord(self, notification: Notification) -> None:
        """Send notification to Discord."""
        config = self._channel_configs.get("discord", {})
        webhook_url = config.get("webhook_url")

        if not webhook_url:
            raise ValueError("Discord webhook URL not configured")

        color = {
            NotificationPriority.LOW: 3066993,
            NotificationPriority.MEDIUM: 3066993,
            NotificationPriority.HIGH: 15105570,
            NotificationPriority.CRITICAL: 15158332,
            NotificationPriority.URGENT: 15548997,
        }.get(notification.priority, 3066993)

        message = {
            "embeds": [
                {
                    "title": notification.title,
                    "description": notification.message[:2000],
                    "color": color,
                    "fields": [
                        {"name": "Priority", "value": notification.priority.value.upper(), "inline": True},
                        {"name": "Channel", "value": notification.channel.value, "inline": True},
                    ],
                    "footer": {"text": f"NEXUS Notification v3.0.0 | {notification.notification_id}"},
                    "timestamp": notification.created_at.isoformat(),
                }
            ]
        }

        if notification.metadata:
            details = "\n".join([f"{k}: {v}" for k, v in notification.metadata.items()])
            message["embeds"][0]["fields"].append({
                "name": "Details",
                "value": details[:1000],
                "inline": False,
            })

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=message, timeout=10) as response:
                if response.status not in (200, 201, 204):
                    raise Exception(f"Discord returned status {response.status}")

    async def _send_pagerduty(self, notification: Notification) -> None:
        """Send notification to PagerDuty."""
        config = self._channel_configs.get("pagerduty", {})
        integration_key = config.get("integration_key")

        if not integration_key:
            raise ValueError("PagerDuty integration key not configured")

        severity_map = {
            NotificationPriority.LOW: "info",
            NotificationPriority.MEDIUM: "warning",
            NotificationPriority.HIGH: "error",
            NotificationPriority.CRITICAL: "critical",
            NotificationPriority.URGENT: "critical",
        }

        payload = {
            "routing_key": integration_key,
            "event_action": "trigger",
            "dedup_key": notification.notification_id,
            "payload": {
                "summary": notification.title,
                "source": "nexus_hedge_bot",
                "severity": severity_map.get(notification.priority, "info"),
                "timestamp": notification.created_at.isoformat(),
                "component": "notification_service",
                "group": "alerts",
                "class": "notification",
                "custom_details": notification.metadata,
            },
            "links": [
                {
                    "href": f"https://nexusquantum.com/notifications/{notification.notification_id}",
                    "text": "View in Nexus Dashboard",
                }
            ],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
                timeout=10,
            ) as response:
                if response.status != 202:
                    error = await response.text()
                    raise Exception(f"PagerDuty returned status {response.status}: {error}")

    async def _send_opsgenie(self, notification: Notification) -> None:
        """Send notification to Opsgenie."""
        config = self._channel_configs.get("opsgenie", {})
        api_key = config.get("api_key")

        if not api_key:
            raise ValueError("Opsgenie API key not configured")

        payload = {
            "message": notification.title,
            "alias": notification.notification_id,
            "description": notification.message,
            "source": "nexus_hedge_bot",
            "priority": notification.priority.value.upper(),
            "tags": notification.tags,
            "details": notification.metadata,
        }

        headers = {"Authorization": f"GenieKey {api_key}"}

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.opsgenie.com/v2/alerts",
                json=payload,
                headers=headers,
                timeout=10,
            ) as response:
                if response.status not in (200, 201, 202):
                    error = await response.text()
                    raise Exception(f"Opsgenie returned status {response.status}: {error}")

    async def _send_teams(self, notification: Notification) -> None:
        """Send notification to Microsoft Teams."""
        config = self._channel_configs.get("microsoft_teams", {})
        webhook_url = config.get("webhook_url")

        if not webhook_url:
            raise ValueError("Microsoft Teams webhook URL not configured")

        # Color codes for Teams
        color_map = {
            NotificationPriority.LOW: "00FF00",
            NotificationPriority.MEDIUM: "00FF00",
            NotificationPriority.HIGH: "FFFF00",
            NotificationPriority.CRITICAL: "FF0000",
            NotificationPriority.URGENT: "FF0000",
        }

        message = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "themeColor": color_map.get(notification.priority, "00FF00"),
            "summary": notification.title,
            "sections": [
                {
                    "activityTitle": notification.title,
                    "activitySubtitle": f"Priority: {notification.priority.value.upper()}",
                    "text": notification.message,
                    "facts": [
                        {"name": "Notification ID", "value": notification.notification_id},
                        {"name": "Channel", "value": notification.channel.value},
                        {"name": "Created", "value": notification.created_at.isoformat()},
                    ],
                }
            ],
        }

        if notification.metadata:
            facts = [{"name": k, "value": str(v)} for k, v in notification.metadata.items()]
            message["sections"][0]["facts"].extend(facts)

        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=message, timeout=10) as response:
                if response.status not in (200, 201, 204):
                    raise Exception(f"Teams returned status {response.status}")

    def _check_rate_limit(self, channel: NotificationChannel) -> bool:
        """Check if rate limit is exceeded for a channel."""
        channel_name = channel.value
        limit = self._rate_limit_config.get(channel_name, 60)

        if channel_name not in self._rate_limits:
            self._rate_limits[channel_name] = []

        now = datetime.utcnow()
        window_start = now - timedelta(minutes=1)

        # Clean old entries
        self._rate_limits[channel_name] = [
            ts for ts in self._rate_limits[channel_name]
            if ts > window_start
        ]

        if len(self._rate_limits[channel_name]) >= limit:
            return False

        self._rate_limits[channel_name].append(now)
        return True

    def _save_notification(self, notification: Notification) -> None:
        """Save notification to database."""
        self._db.execute("""
            INSERT OR REPLACE INTO notifications (
                notification_id, title, message, channel, priority, status,
                recipients, template_type, template_data, attachments,
                metadata, created_at, sent_at, delivered_at, retry_count,
                max_retries, error_message, tags, correlation_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            notification.notification_id,
            notification.title,
            notification.message,
            notification.channel.value,
            notification.priority.value,
            notification.status.value,
            json.dumps(notification.recipients),
            notification.template_type.value if notification.template_type else None,
            json.dumps(notification.template_data),
            json.dumps(notification.attachments),
            json.dumps(notification.metadata),
            notification.created_at.isoformat(),
            notification.sent_at.isoformat() if notification.sent_at else None,
            notification.delivered_at.isoformat() if notification.delivered_at else None,
            notification.retry_count,
            notification.max_retries,
            notification.error_message,
            json.dumps(notification.tags),
            notification.correlation_id,
        ))

    def _update_notification(self, notification: Notification) -> None:
        """Update notification in database."""
        self._save_notification(notification)

    def _deserialize_notification_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize JSON fields in notification data."""
        json_fields = [
            "recipients", "template_data", "attachments",
            "metadata", "tags"
        ]

        for field in json_fields:
            if field in data and data[field]:
                try:
                    data[field] = json.loads(data[field])
                except json.JSONDecodeError:
                    data[field] = []

        return data

    def get_notification(self, notification_id: str) -> Optional[Notification]:
        """Get a notification by ID."""
        cursor = self._db.execute(
            "SELECT * FROM notifications WHERE notification_id = ?",
            (notification_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        columns = [desc[0] for desc in cursor.description]
        data = dict(zip(columns, row))
        data = self._deserialize_notification_data(data)
        return Notification.from_dict(data)

    def get_notifications(
        self,
        status: Optional[Union[str, NotificationStatus]] = None,
        channel: Optional[Union[str, NotificationChannel]] = None,
        priority: Optional[Union[str, NotificationPriority]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Notification]:
        """Get notifications with filtering."""
        sql = "SELECT * FROM notifications WHERE 1=1"
        params = []

        if status:
            if isinstance(status, str):
                status = NotificationStatus(status)
            sql += " AND status = ?"
            params.append(status.value)

        if channel:
            if isinstance(channel, str):
                channel = NotificationChannel(channel)
            sql += " AND channel = ?"
            params.append(channel.value)

        if priority:
            if isinstance(priority, str):
                priority = NotificationPriority(priority)
            sql += " AND priority = ?"
            params.append(priority.value)

        if start_date:
            sql += " AND created_at >= ?"
            params.append(start_date.isoformat())

        if end_date:
            sql += " AND created_at <= ?"
            params.append(end_date.isoformat())

        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self._db.execute(sql, params)
        rows = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]
        notifications = []

        for row in rows:
            data = dict(zip(columns, row))
            data = self._deserialize_notification_data(data)
            notifications.append(Notification.from_dict(data))

        return notifications

    def get_template(self, name: str) -> Optional[NotificationTemplate]:
        """Get a template by name."""
        return self._templates.get(name)

    def create_template(self, template: NotificationTemplate) -> None:
        """Create a new template."""
        self._templates[template.name] = template
        self._save_template(template)
        logger.info("template_created", name=template.name, channel=template.channel.value)

    def delete_template(self, name: str) -> bool:
        """Delete a template."""
        if name not in self._templates:
            return False

        del self._templates[name]
        self._db.execute(
            "DELETE FROM templates WHERE name = ?",
            (name,)
        )
        logger.info("template_deleted", name=name)
        return True

    def get_metrics(self) -> Dict[str, Any]:
        """Get notification service metrics."""
        total = self._get_total_notifications()
        by_status = self._get_counts_by_status()
        by_channel = self._get_counts_by_channel()

        return {
            "total_notifications": total,
            "by_status": by_status,
            "by_channel": by_channel,
            "templates": len(self._templates),
            "queue_size": self._queue.qsize(),
            "pending_retries": self._get_pending_retries(),
        }

    def _get_total_notifications(self) -> int:
        cursor = self._db.execute("SELECT COUNT(*) FROM notifications")
        return cursor.fetchone()[0]

    def _get_counts_by_status(self) -> Dict[str, int]:
        cursor = self._db.execute(
            "SELECT status, COUNT(*) FROM notifications GROUP BY status"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def _get_counts_by_channel(self) -> Dict[str, int]:
        cursor = self._db.execute(
            "SELECT channel, COUNT(*) FROM notifications GROUP BY channel"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}

    def _get_pending_retries(self) -> int:
        cursor = self._db.execute(
            "SELECT COUNT(*) FROM notifications WHERE status = ? AND retry_count < max_retries",
            (NotificationStatus.FAILED.value,)
        )
        return cursor.fetchone()[0]

    def close(self) -> None:
        """Close the notification service."""
        if self._closed:
            return

        self._closed = True

        if hasattr(self, "_db") and self._db:
            self._db.close()

        logger.info("notification_service_closed")

    def __enter__(self) -> "NotificationService":
        return self

    def __exit__(self, *args) -> None:
        self.close()


# === MODULE EXPORTS ===

__all__ = [
    "NotificationService",
    "Notification",
    "NotificationTemplate",
    "NotificationChannel",
    "NotificationPriority",
    "NotificationStatus",
    "NotificationTemplateType",
]

logger.info("notification_service_module_loaded", version="3.0.0")
