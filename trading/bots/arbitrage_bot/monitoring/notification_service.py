# trading/bots/arbitrage_bot/monitoring/notification_service.py
# NEXUS AI TRADING SYSTEM - NOTIFICATION SERVICE
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module provides comprehensive notification services for the arbitrage bot,
# including multi-channel delivery, templating, scheduling, and management.
# ====================================================================================

"""
NEXUS Arbitrage Bot Notification Service

This module provides comprehensive notification services for:
- Multi-channel notification delivery (Email, Slack, Telegram, Discord, etc.)
- Template-based message generation
- Notification scheduling and queuing
- Delivery tracking and retry
- User preference management
- Notification history and analytics
- Integration with alerting systems
"""

import asyncio
import logging
import json
import smtplib
import ssl
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import aiohttp
import aiofiles

# NEXUS internal imports
from trading.bots.arbitrage_bot.models.alert import NotificationChannel
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector
from trading.bots.arbitrage_bot.core.retry_handler import RetryHandler, RetryConfig
from trading.bots.arbitrage_bot.core.circuit_breaker import CircuitBreaker

logger = logging.getLogger("nexus.arbitrage.notification_service")


# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class NotificationStatus(str, Enum):
    """Status of notification delivery."""
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    EXPIRED = "expired"


class NotificationPriority(str, Enum):
    """Priority levels for notifications."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BACKGROUND = "background"


class NotificationType(str, Enum):
    """Types of notifications."""
    ALERT = "alert"
    TRADE = "trade"
    OPPORTUNITY = "opportunity"
    SYSTEM = "system"
    REPORT = "report"
    MAINTENANCE = "maintenance"
    SECURITY = "security"
    CUSTOM = "custom"


# ====================================================================================
# DATA MODELS
# ====================================================================================

@dataclass
class Notification:
    """
    Notification data model.
    """
    id: str
    type: NotificationType
    channel: NotificationChannel
    priority: NotificationPriority
    recipients: List[str]
    subject: str
    message: str
    html_message: str
    template_name: str
    template_data: Dict[str, Any]
    status: NotificationStatus
    created_at: datetime
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    error: Optional[str]
    retry_count: int
    max_retries: int
    metadata: Dict[str, Any]


@dataclass
class NotificationTemplate:
    """
    Notification template.
    """
    name: str
    channel: NotificationChannel
    subject_template: str
    body_template: str
    html_template: str
    variables: List[str]
    version: str
    created_at: datetime
    updated_at: datetime


@dataclass
class NotificationPreference:
    """
    User notification preferences.
    """
    user_id: str
    channels: List[NotificationChannel]
    types: List[NotificationType]
    min_priority: NotificationPriority
    quiet_hours: Dict[str, str]  # {"start": "22:00", "end": "06:00"}
    enabled: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class NotificationStats:
    """
    Notification statistics.
    """
    total_sent: int
    total_delivered: int
    total_failed: int
    by_channel: Dict[str, int]
    by_type: Dict[str, int]
    success_rate: float
    avg_delivery_time: float
    period_start: datetime
    period_end: datetime


# ====================================================================================
# NOTIFICATION PROVIDERS
# ====================================================================================

class NotificationProvider:
    """Base notification provider."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60.0,
            half_open_attempts=2
        )
        
    async def initialize(self) -> None:
        """Initialize provider."""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        
    async def close(self) -> None:
        """Close provider."""
        if self._session:
            await self._session.close()
            
    async def send(self, notification: Notification) -> Dict[str, Any]:
        """
        Send notification.
        
        Args:
            notification: Notification to send
            
        Returns:
            Delivery result
        """
        if self._circuit_breaker.is_open():
            return {
                "status": "failed",
                "error": f"Circuit breaker open - retry after {self._circuit_breaker.get_retry_after():.0f}s"
            }
            
        try:
            result = await self._send(notification)
            self._circuit_breaker.record_success()
            return result
        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(f"Provider send failed: {e}")
            return {"status": "failed", "error": str(e)}
            
    async def _send(self, notification: Notification) -> Dict[str, Any]:
        """Implement in subclass."""
        raise NotImplementedError


class EmailProvider(NotificationProvider):
    """Email notification provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._smtp_server = config.get("smtp_server", "smtp.gmail.com")
        self._smtp_port = config.get("smtp_port", 587)
        self._username = config.get("username", "")
        self._password = config.get("password", "")
        self._from_email = config.get("from_email", "")
        self._use_tls = config.get("use_tls", True)
        
    async def _send(self, notification: Notification) -> Dict[str, Any]:
        """Send email."""
        if not self._username or not self._password:
            return {"status": "failed", "error": "Email credentials not configured"}
            
        try:
            # Build email
            subject = notification.subject
            body = notification.html_message or notification.message
            
            msg = f"Subject: {subject}\n"
            msg += "MIME-Version: 1.0\n"
            msg += "Content-Type: text/html; charset=utf-8\n"
            msg += f"From: {self._from_email}\n"
            msg += f"To: {', '.join(notification.recipients)}\n\n"
            msg += body
            
            # Send in thread to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._send_sync,
                msg,
                notification.recipients
            )
            
            return {"status": "sent", "recipients": notification.recipients}
            
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return {"status": "failed", "error": str(e)}
            
    def _send_sync(self, msg: str, recipients: List[str]) -> None:
        """Synchronous email send."""
        if self._use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(self._smtp_server, self._smtp_port) as server:
                server.starttls(context=context)
                server.login(self._username, self._password)
                server.sendmail(self._from_email, recipients, msg.encode('utf-8'))
        else:
            with smtplib.SMTP(self._smtp_server, self._smtp_port) as server:
                server.login(self._username, self._password)
                server.sendmail(self._from_email, recipients, msg.encode('utf-8'))


class SlackProvider(NotificationProvider):
    """Slack notification provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._webhook_url = config.get("webhook_url", "")
        self._bot_token = config.get("bot_token", "")
        self._default_channel = config.get("default_channel", "#alerts")
        self._username = config.get("username", "NEXUS Alert Bot")
        
    async def _send(self, notification: Notification) -> Dict[str, Any]:
        """Send Slack message."""
        if not self._webhook_url and not self._bot_token:
            return {"status": "failed", "error": "Slack credentials not configured"}
            
        try:
            channel = notification.recipients[0] if notification.recipients else self._default_channel
            
            payload = {
                "channel": channel,
                "username": self._username,
                "text": notification.message,
                "attachments": [
                    {
                        "color": self._get_color(notification),
                        "title": notification.subject,
                        "text": notification.message[:2000],
                        "footer": f"NEXUS Trading Bot • {notification.type.value}",
                        "ts": int(notification.created_at.timestamp())
                    }
                ]
            }
            
            # Add fields from template data
            if notification.template_data:
                fields = []
                for key, value in notification.template_data.items():
                    if isinstance(value, (str, int, float, bool)):
                        fields.append({"title": key, "value": str(value), "short": True})
                    if len(fields) >= 10:
                        break
                if fields:
                    payload["attachments"][0]["fields"] = fields
                    
            # Send
            if self._webhook_url:
                async with self._session.post(self._webhook_url, json=payload) as response:
                    if response.status == 200:
                        return {"status": "sent", "channel": channel}
                    return {"status": "failed", "error": f"HTTP {response.status}"}
            else:
                headers = {"Authorization": f"Bearer {self._bot_token}"}
                url = "https://slack.com/api/chat.postMessage"
                async with self._session.post(url, json=payload, headers=headers) as response:
                    result = await response.json()
                    if result.get("ok"):
                        return {"status": "sent", "channel": channel}
                    return {"status": "failed", "error": result.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Slack send failed: {e}")
            return {"status": "failed", "error": str(e)}
            
    def _get_color(self, notification: Notification) -> str:
        """Get color based on notification type."""
        colors = {
            NotificationType.ALERT: "#c62828",
            NotificationType.TRADE: "#2e7d32",
            NotificationType.OPPORTUNITY: "#f9a825",
            NotificationType.SYSTEM: "#0d47a1",
            NotificationType.SECURITY: "#d32f2f",
            NotificationType.MAINTENANCE: "#e65100"
        }
        return colors.get(notification.type, "#607d8b")


class TelegramProvider(NotificationProvider):
    """Telegram notification provider."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._bot_token = config.get("bot_token", "")
        self._chat_id = config.get("chat_id", "")
        self._parse_mode = config.get("parse_mode", "HTML")
        
    async def _send(self, notification: Notification) -> Dict[str, Any]:
        """Send Telegram message."""
        if not self._bot_token:
            return {"status": "failed", "error": "Telegram bot token not configured"}
            
        try:
            chat_id = notification.recipients[0] if notification.recipients else self._chat_id
            
            # Build message
            emoji_map = {
                NotificationType.ALERT: "🔴",
                NotificationType.TRADE: "✅",
                NotificationType.OPPORTUNITY: "💰",
                NotificationType.SYSTEM: "⚙️",
                NotificationType.SECURITY: "🛡️",
                NotificationType.MAINTENANCE: "🔧"
            }
            
            emoji = emoji_map.get(notification.type, "ℹ️")
            
            message = f"""
<b>{emoji} {notification.subject}</b>

{notification.message}

<b>Type:</b> <code>{notification.type.value}</code>
<b>Priority:</b> <code>{notification.priority.value}</code>
<b>Time:</b> {notification.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
"""
            
            # Add template data
            if notification.template_data:
                for key, value in notification.template_data.items():
                    if isinstance(value, (str, int, float)):
                        message += f"\n<b>{key}:</b> <code>{value}</code>"
                        
            # Send
            url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": self._parse_mode
            }
            
            async with self._session.post(url, json=payload) as response:
                result = await response.json()
                if result.get("ok"):
                    return {"status": "sent", "chat_id": chat_id}
                return {"status": "failed", "error": result.get("description", "Unknown error")}
                
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return {"status": "failed", "error": str(e)}


class ConsoleProvider(NotificationProvider):
    """Console notification provider (for debugging)."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
    async def _send(self, notification: Notification) -> Dict[str, Any]:
        """Print to console."""
        print("=" * 80)
        print(f"[{notification.created_at}] {notification.type.value.upper()}")
        print(f"Subject: {notification.subject}")
        print(f"Channel: {notification.channel.value}")
        print(f"Priority: {notification.priority.value}")
        print(f"Recipients: {', '.join(notification.recipients)}")
        print("-" * 40)
        print(notification.message)
        if notification.html_message:
            print("[HTML message available]")
        print("=" * 80)
        return {"status": "sent"}


# ====================================================================================
# NOTIFICATION SERVICE
# ====================================================================================

class NotificationService:
    """
    Comprehensive notification service.
    
    Features:
    - Multi-channel delivery
    - Template-based messaging
    - Notification queuing and scheduling
    - Delivery tracking and retry
    - User preference management
    - Notification history
    - Integration with alerting
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the notification service.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        # Providers
        self._providers: Dict[NotificationChannel, NotificationProvider] = {}
        self._provider_configs: Dict[NotificationChannel, Dict[str, Any]] = {}
        
        # Templates
        self._templates: Dict[str, NotificationTemplate] = {}
        
        # Queues
        self._notification_queue: asyncio.Queue = asyncio.Queue()
        self._pending_notifications: Dict[str, Notification] = {}
        
        # Preferences
        self._preferences: Dict[str, NotificationPreference] = {}
        
        # History
        self._notification_history: deque = deque(maxlen=10000)
        
        # Metrics
        self._metrics = MetricsCollector(
            name="nexus_notification_service",
            labels={"service": "arbitrage_bot"}
        )
        self._setup_metrics()
        
        # State
        self._running = False
        self._initialized = False
        self._background_tasks: Set[asyncio.Task] = set()
        
        # Retry handler
        self._retry_handler = RetryHandler(
            RetryConfig(
                max_retries=3,
                backoff=2.0,
                backoff_max=30.0
            )
        )
        
        logger.info("NotificationService initialized (version=3.0.0)")
        
    def _setup_metrics(self) -> None:
        """Setup metrics collection."""
        self._metrics.register_counter("notifications_sent", "Notifications sent")
        self._metrics.register_counter("notifications_delivered", "Notifications delivered")
        self._metrics.register_counter("notifications_failed", "Notifications failed")
        self._metrics.register_counter("notifications_retried", "Notifications retried")
        self._metrics.register_gauge("notifications_queued", "Notifications in queue")
        self._metrics.register_histogram("notification_delivery_time", "Notification delivery time in seconds")
        
    def configure_provider(
        self,
        channel: NotificationChannel,
        config: Dict[str, Any]
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
        elif channel == NotificationChannel.CONSOLE:
            self._providers[channel] = ConsoleProvider(config)
        else:
            logger.warning(f"Unsupported channel: {channel.value}")
            
        logger.info(f"Configured provider for channel: {channel.value}")
        
    def register_template(
        self,
        template: NotificationTemplate
    ) -> None:
        """
        Register a notification template.
        
        Args:
            template: Notification template
        """
        self._templates[template.name] = template
        logger.info(f"Registered template: {template.name}")
        
    def set_preference(
        self,
        preference: NotificationPreference
    ) -> None:
        """
        Set user notification preferences.
        
        Args:
            preference: Notification preference
        """
        self._preferences[preference.user_id] = preference
        logger.info(f"Set preferences for user: {preference.user_id}")
        
    async def initialize(self) -> None:
        """Initialize the notification service."""
        if self._initialized:
            return
            
        # Initialize providers
        for provider in self._providers.values():
            await provider.initialize()
            
        self._initialized = True
        self._running = True
        
        # Start background tasks
        await self._start_background_tasks()
        
        logger.info("NotificationService initialized")
        
    async def _start_background_tasks(self) -> None:
        """Start background tasks."""
        # Notification processor
        task = asyncio.create_task(self._notification_processor())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        # Retry processor
        task = asyncio.create_task(self._retry_processor())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        # Metrics updater
        task = asyncio.create_task(self._metrics_updater())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
    async def _notification_processor(self) -> None:
        """Process queued notifications."""
        while self._running:
            try:
                notification = await self._notification_queue.get()
                await self._process_notification(notification)
                self._notification_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Notification processor error: {e}")
                
    async def _retry_processor(self) -> None:
        """Retry failed notifications."""
        while self._running:
            try:
                await asyncio.sleep(30)
                
                now = datetime.utcnow()
                for notification_id, notification in list(self._pending_notifications.items()):
                    if notification.status == NotificationStatus.FAILED:
                        age = (now - notification.created_at).total_seconds()
                        if age > 300:  # 5 minutes
                            if notification.retry_count < notification.max_retries:
                                await self.retry_notification(notification_id)
                            else:
                                notification.status = NotificationStatus.EXPIRED
                                del self._pending_notifications[notification_id]
                                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Retry processor error: {e}")
                
    async def _metrics_updater(self) -> None:
        """Update metrics periodically."""
        while self._running:
            try:
                await asyncio.sleep(30)
                
                queued_count = self._notification_queue.qsize()
                self._metrics.set_gauge("notifications_queued", queued_count)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics updater error: {e}")
                
    async def _process_notification(self, notification: Notification) -> None:
        """
        Process a single notification.
        
        Args:
            notification: Notification to process
        """
        try:
            start_time = time.time()
            
            # Check user preferences
            if not self._should_send(notification):
                notification.status = NotificationStatus.FAILED
                notification.error = "Blocked by user preferences"
                return
                
            # Get provider
            provider = self._providers.get(notification.channel)
            if not provider:
                notification.status = NotificationStatus.FAILED
                notification.error = f"No provider for channel: {notification.channel.value}"
                return
                
            # Apply template
            await self._apply_template(notification)
            
            # Send
            result = await provider.send(notification)
            
            if result.get("status") == "sent":
                notification.status = NotificationStatus.SENT
                notification.sent_at = datetime.utcnow()
                
                # Record delivery time
                delivery_time = (datetime.utcnow() - notification.created_at).total_seconds()
                self._metrics.record_histogram("notification_delivery_time", delivery_time)
                self._metrics.increment_counter("notifications_sent")
                
                # Track delivery
                self._notification_history.append(notification)
                
            else:
                notification.status = NotificationStatus.FAILED
                notification.error = result.get("error", "Unknown error")
                self._metrics.increment_counter("notifications_failed")
                
        except Exception as e:
            notification.status = NotificationStatus.FAILED
            notification.error = str(e)
            self._metrics.increment_counter("notifications_failed")
            logger.error(f"Notification processing error: {e}")
            
    def _should_send(self, notification: Notification) -> bool:
        """
        Check if notification should be sent based on preferences.
        
        Args:
            notification: Notification
            
        Returns:
            True if should send
        """
        # Check for each recipient
        for recipient in notification.recipients:
            if recipient in self._preferences:
                pref = self._preferences[recipient]
                
                # Check enabled
                if not pref.enabled:
                    return False
                    
                # Check channel
                if notification.channel not in pref.channels:
                    return False
                    
                # Check type
                if notification.type not in pref.types:
                    return False
                    
                # Check priority
                priority_order = [NotificationPriority.CRITICAL, NotificationPriority.HIGH,
                                 NotificationPriority.MEDIUM, NotificationPriority.LOW,
                                 NotificationPriority.BACKGROUND]
                if priority_order.index(notification.priority) < priority_order.index(pref.min_priority):
                    return False
                    
                # Check quiet hours
                if "start" in pref.quiet_hours and "end" in pref.quiet_hours:
                    now = datetime.utcnow()
                    current_time = now.strftime("%H:%M")
                    if pref.quiet_hours["start"] <= current_time <= pref.quiet_hours["end"]:
                        return False
                        
        return True
        
    async def _apply_template(self, notification: Notification) -> None:
        """
        Apply template to notification.
        
        Args:
            notification: Notification
        """
        if not notification.template_name:
            return
            
        template = self._templates.get(notification.template_name)
        if not template:
            return
            
        # Apply template
        if not notification.subject:
            notification.subject = self._render_template(
                template.subject_template,
                notification.template_data
            )
            
        if not notification.message:
            notification.message = self._render_template(
                template.body_template,
                notification.template_data
            )
            
        if not notification.html_message and template.html_template:
            notification.html_message = self._render_template(
                template.html_template,
                notification.template_data
            )
            
    def _render_template(self, template: str, data: Dict[str, Any]) -> str:
        """
        Render template with data.
        
        Args:
            template: Template string
            data: Template data
            
        Returns:
            Rendered string
        """
        result = template
        for key, value in data.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, str(value))
        return result
        
    async def send_notification(
        self,
        type: NotificationType,
        channel: NotificationChannel,
        recipients: List[str],
        subject: str = "",
        message: str = "",
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        template_name: str = "",
        template_data: Optional[Dict[str, Any]] = None,
        max_retries: int = 3
    ) -> str:
        """
        Send a notification.
        
        Args:
            type: Notification type
            channel: Notification channel
            recipients: List of recipients
            subject: Notification subject
            message: Notification message
            priority: Notification priority
            template_name: Template name
            template_data: Template data
            max_retries: Maximum retries
            
        Returns:
            Notification ID
        """
        notification_id = f"NOT-{datetime.utcnow().strftime('%Y%m%d')}-{len(self._notification_history)+1:06d}"
        
        notification = Notification(
            id=notification_id,
            type=type,
            channel=channel,
            priority=priority,
            recipients=recipients,
            subject=subject,
            message=message,
            html_message="",
            template_name=template_name,
            template_data=template_data or {},
            status=NotificationStatus.PENDING,
            created_at=datetime.utcnow(),
            sent_at=None,
            delivered_at=None,
            error=None,
            retry_count=0,
            max_retries=max_retries,
            metadata={}
        )
        
        # Queue for processing
        await self._notification_queue.put(notification)
        self._pending_notifications[notification_id] = notification
        
        logger.info(f"Notification queued: {notification_id}")
        return notification_id
        
    async def retry_notification(self, notification_id: str) -> bool:
        """
        Retry a failed notification.
        
        Args:
            notification_id: Notification ID
            
        Returns:
            True if retried
        """
        notification = self._pending_notifications.get(notification_id)
        if not notification:
            return False
            
        if notification.retry_count >= notification.max_retries:
            return False
            
        notification.retry_count += 1
        notification.status = NotificationStatus.RETRYING
        notification.error = None
        
        # Re-queue
        await self._notification_queue.put(notification)
        self._metrics.increment_counter("notifications_retried")
        
        logger.info(f"Notification retried: {notification_id} (attempt {notification.retry_count})")
        return True
        
    def get_notification(self, notification_id: str) -> Optional[Notification]:
        """
        Get notification by ID.
        
        Args:
            notification_id: Notification ID
            
        Returns:
            Notification or None
        """
        return self._pending_notifications.get(notification_id)
        
    def get_history(
        self,
        limit: int = 100,
        type: Optional[NotificationType] = None,
        channel: Optional[NotificationChannel] = None,
        status: Optional[NotificationStatus] = None
    ) -> List[Notification]:
        """
        Get notification history.
        
        Args:
            limit: Maximum results
            type: Filter by type
            channel: Filter by channel
            status: Filter by status
            
        Returns:
            List of notifications
        """
        history = list(self._notification_history)
        
        if type:
            history = [n for n in history if n.type == type]
        if channel:
            history = [n for n in history if n.channel == channel]
        if status:
            history = [n for n in history if n.status == status]
            
        return history[-limit:]
        
    def get_stats(self, period_days: int = 1) -> NotificationStats:
        """
        Get notification statistics.
        
        Args:
            period_days: Analysis period in days
            
        Returns:
            Notification statistics
        """
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        history = [n for n in self._notification_history if n.created_at > cutoff]
        
        by_channel = defaultdict(int)
        by_type = defaultdict(int)
        delivery_times = []
        
        for notification in history:
            by_channel[notification.channel.value] += 1
            by_type[notification.type.value] += 1
            if notification.sent_at and notification.created_at:
                delivery_time = (notification.sent_at - notification.created_at).total_seconds()
                delivery_times.append(delivery_time)
                
        total = len(history)
        delivered = sum(1 for n in history if n.status == NotificationStatus.DELIVERED)
        failed = sum(1 for n in history if n.status == NotificationStatus.FAILED)
        
        return NotificationStats(
            total_sent=total,
            total_delivered=delivered,
            total_failed=failed,
            by_channel=dict(by_channel),
            by_type=dict(by_type),
            success_rate=delivered / total if total > 0 else 0,
            avg_delivery_time=sum(delivery_times) / len(delivery_times) if delivery_times else 0,
            period_start=cutoff,
            period_end=datetime.utcnow()
        )
        
    async def close(self) -> None:
        """Close the notification service."""
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
            
        logger.info("NotificationService closed")


# ====================================================================================
# GLOBAL INSTANCE
# ====================================================================================

_global_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """
    Get the global notification service instance.
    
    Returns:
        NotificationService instance
    """
    global _global_notification_service
    if _global_notification_service is None:
        _global_notification_service = NotificationService()
    return _global_notification_service


def reset_notification_service() -> None:
    """Reset the global notification service instance."""
    global _global_notification_service
    if _global_notification_service:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_global_notification_service.close())
            else:
                asyncio.run(_global_notification_service.close())
        except Exception:
            pass
    _global_notification_service = None


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'NotificationStatus',
    'NotificationPriority',
    'NotificationType',
    
    # Data Models
    'Notification',
    'NotificationTemplate',
    'NotificationPreference',
    'NotificationStats',
    
    # Providers
    'NotificationProvider',
    'EmailProvider',
    'SlackProvider',
    'TelegramProvider',
    'ConsoleProvider',
    
    # Main Class
    'NotificationService',
    'get_notification_service',
    'reset_notification_service',
]
