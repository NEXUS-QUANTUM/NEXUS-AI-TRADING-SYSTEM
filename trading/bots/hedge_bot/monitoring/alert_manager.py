# trading/bots/hedge_bot/monitoring/alert_manager.py

"""
NEXUS HEDGE BOT - ALERT MANAGER
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced alert management system with multi-channel notification,
escalation policies, and intelligent alert correlation.

Version: 3.0.0
"""

import asyncio
import hashlib
import json
import os
import re
import smtplib
import socket
import sqlite3
import ssl
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum, auto
from pathlib import Path
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, Union,
    AsyncIterator, Coroutine
)
from urllib.parse import urlparse

import aiohttp
import structlog
import yaml
from pydantic import BaseModel, Field, validator, ConfigDict
import redis.asyncio as redis_async
from redis.asyncio import Redis

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertCategory(str, Enum):
    """Alert categories."""
    SYSTEM = "system"
    PERFORMANCE = "performance"
    RISK = "risk"
    TRADING = "trading"
    BROKER = "broker"
    MARKET = "market"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"


class AlertStatus(str, Enum):
    """Alert status."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    ESCALATED = "escalated"


class ChannelType(str, Enum):
    """Notification channel types."""
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


# === DATA MODELS ===

@dataclass
class Alert:
    """Alert data model."""
    alert_id: str = field(default_factory=lambda: hashlib.md5(f"{time.time()}{uuid4()}".encode()).hexdigest()[:16])
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""
    category: AlertCategory = AlertCategory.SYSTEM
    severity: AlertSeverity = AlertSeverity.INFO
    title: str = ""
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    status: AlertStatus = AlertStatus.ACTIVE
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    escalation_level: int = 0
    retry_count: int = 0
    correlation_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    ttl_seconds: int = 3600  # Time to live in seconds
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "category": self.category.value,
            "severity": self.severity.value,
            "status": self.status.value,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Alert":
        data = data.copy()
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if data.get("acknowledged_at"):
            data["acknowledged_at"] = datetime.fromisoformat(data["acknowledged_at"])
        if data.get("resolved_at"):
            data["resolved_at"] = datetime.fromisoformat(data["resolved_at"])
        data["category"] = AlertCategory(data["category"])
        data["severity"] = AlertSeverity(data["severity"])
        data["status"] = AlertStatus(data["status"])
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if the alert has expired."""
        if self.ttl_seconds <= 0:
            return False
        age = (datetime.utcnow() - self.timestamp).total_seconds()
        return age > self.ttl_seconds


@dataclass
class AlertRule:
    """Alert rule definition."""
    rule_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    enabled: bool = True
    condition: str = ""  # Expression to evaluate
    severity: AlertSeverity = AlertSeverity.WARNING
    category: AlertCategory = AlertCategory.SYSTEM
    channels: List[str] = field(default_factory=list)  # Channel names
    cooldown_seconds: int = 300  # Minimum time between alerts
    escalation_policy: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "severity": self.severity.value,
            "category": self.category.value,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlertRule":
        data = data.copy()
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        data["severity"] = AlertSeverity(data["severity"])
        data["category"] = AlertCategory(data["category"])
        return cls(**data)


@dataclass
class Channel:
    """Notification channel configuration."""
    channel_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    type: ChannelType = ChannelType.SLACK
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    rate_limit: int = 60  # Messages per minute
    timeout_seconds: int = 10
    retry_count: int = 3
    retry_delay_seconds: int = 5
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "type": self.type.value,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Channel":
        data = data.copy()
        data["type"] = ChannelType(data["type"])
        return cls(**data)


# === ALERT MANAGER ===

class AlertManager:
    """
    Advanced alert management system with multi-channel notification,
    escalation policies, and intelligent alert correlation.
    """
    
    def __init__(
        self,
        config: Union[Dict[str, Any], str],
        redis_client: Optional[Redis] = None,
    ):
        """
        Initialize the AlertManager.
        
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
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self._closed = False
        
        # Database for persistent storage
        self._db_path = Path(self.config.get("db_path", "alerts.db"))
        self._initialize_db()
        
        # Load rules and channels
        self.rules: Dict[str, AlertRule] = {}
        self.channels: Dict[str, Channel] = {}
        self._load_configuration()
        
        # Alert cache
        self._alert_cache: Dict[str, Alert] = {}
        self._active_alerts: Dict[str, Alert] = {}
        self._last_alert_times: Dict[str, datetime] = {}
        
        # Rate limiting
        self._rate_limits: Dict[str, List[datetime]] = {}
        
        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._escalation_task: Optional[asyncio.Task] = None
        
        # Start background tasks
        self._start_background_tasks()
        
        logger.info(
            "alert_manager_initialized",
            rules_count=len(self.rules),
            channels_count=len(self.channels),
            db_path=str(self._db_path),
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
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT,
                status TEXT NOT NULL,
                acknowledged_at TEXT,
                resolved_at TEXT,
                acknowledged_by TEXT,
                escalation_level INTEGER DEFAULT 0,
                retry_count INTEGER DEFAULT 0,
                correlation_id TEXT,
                tags TEXT,
                ttl_seconds INTEGER DEFAULT 3600
            )
        """)
        
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS alert_rules (
                rule_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                enabled INTEGER DEFAULT 1,
                condition TEXT NOT NULL,
                severity TEXT NOT NULL,
                category TEXT NOT NULL,
                channels TEXT,
                cooldown_seconds INTEGER DEFAULT 300,
                escalation_policy TEXT,
                tags TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                channel_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                config TEXT,
                rate_limit INTEGER DEFAULT 60,
                timeout_seconds INTEGER DEFAULT 10,
                retry_count INTEGER DEFAULT 3,
                retry_delay_seconds INTEGER DEFAULT 5,
                tags TEXT
            )
        """)
        
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity)
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_category ON alerts(category)
        """)
        
        logger.info("alert_db_initialized", db_path=str(self._db_path))
    
    def _load_configuration(self) -> None:
        """Load rules and channels from configuration."""
        # Load rules
        for rule_data in self.config.get("rules", []):
            rule = AlertRule.from_dict(rule_data)
            self.rules[rule.rule_id] = rule
        
        # Load channels
        for channel_data in self.config.get("channels", []):
            channel = Channel.from_dict(channel_data)
            self.channels[channel.channel_id] = channel
    
    def _start_background_tasks(self) -> None:
        """Start background tasks."""
        try:
            loop = asyncio.get_event_loop()
            
            # Cleanup task
            self._cleanup_task = loop.create_task(self._cleanup_loop())
            
            # Escalation task
            self._escalation_task = loop.create_task(self._escalation_loop())
            
            logger.info("background_tasks_started")
        except RuntimeError:
            logger.warning("no_event_loop_available_background_tasks_disabled")
    
    async def _cleanup_loop(self) -> None:
        """Background task for cleaning up expired alerts."""
        while not self._closed:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._cleanup_expired_alerts()
            except Exception as e:
                logger.error("cleanup_loop_error", error=str(e))
    
    async def _escalation_loop(self) -> None:
        """Background task for handling alert escalations."""
        while not self._closed:
            try:
                await asyncio.sleep(30)  # Run every 30 seconds
                await self._process_escalations()
            except Exception as e:
                logger.error("escalation_loop_error", error=str(e))
    
    async def _cleanup_expired_alerts(self) -> None:
        """Clean up expired alerts."""
        with self._lock:
            now = datetime.utcnow()
            expired_ids = []
            
            for alert_id, alert in list(self._active_alerts.items()):
                if alert.is_expired():
                    expired_ids.append(alert_id)
                    alert.status = AlertStatus.RESOLVED
                    alert.resolved_at = now
                    self._save_alert(alert)
            
            for alert_id in expired_ids:
                del self._active_alerts[alert_id]
            
            if expired_ids:
                logger.info("cleaned_expired_alerts", count=len(expired_ids))
    
    async def _process_escalations(self) -> None:
        """Process alert escalations."""
        with self._lock:
            now = datetime.utcnow()
            escalated_ids = []
            
            for alert_id, alert in self._active_alerts.items():
                if alert.status != AlertStatus.ACTIVE:
                    continue
                
                # Check if escalation is needed
                age = (now - alert.timestamp).total_seconds()
                rule = self.rules.get(alert_id)  # This needs mapping
                
                if rule and rule.escalation_policy:
                    for escalation in rule.escalation_policy:
                        if age > escalation.get("after_seconds", 300):
                            if alert.escalation_level < len(rule.escalation_policy):
                                alert.escalation_level += 1
                                alert.status = AlertStatus.ESCALATED
                                escalated_ids.append(alert_id)
                                
                                # Send escalation notification
                                await self._send_alert(
                                    alert,
                                    channels=escalation.get("channels", []),
                                    is_escalation=True,
                                )
                                
                                logger.info(
                                    "alert_escalated",
                                    alert_id=alert_id,
                                    escalation_level=alert.escalation_level,
                                    escalation_data=escalation,
                                )
            
            # Update escalated alerts
            for alert_id in escalated_ids:
                self._save_alert(self._active_alerts[alert_id])
    
    def create_alert(
        self,
        source: str,
        title: str,
        message: str,
        severity: Union[str, AlertSeverity] = AlertSeverity.INFO,
        category: Union[str, AlertCategory] = AlertCategory.SYSTEM,
        details: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        correlation_id: Optional[str] = None,
        ttl_seconds: int = 3600,
    ) -> Alert:
        """
        Create a new alert.
        
        Args:
            source: Source of the alert
            title: Alert title
            message: Alert message
            severity: Alert severity
            category: Alert category
            details: Additional details
            tags: Alert tags
            correlation_id: Correlation ID for grouping
            ttl_seconds: Time to live in seconds
            
        Returns:
            Created Alert object
        """
        if isinstance(severity, str):
            severity = AlertSeverity(severity.lower())
        if isinstance(category, str):
            category = AlertCategory(category.lower())
        
        alert = Alert(
            source=source,
            severity=severity,
            category=category,
            title=title,
            message=message,
            details=details or {},
            tags=tags or [],
            correlation_id=correlation_id,
            ttl_seconds=ttl_seconds,
        )
        
        with self._lock:
            self._alert_cache[alert.alert_id] = alert
            self._active_alerts[alert.alert_id] = alert
            self._save_alert(alert)
        
        # Check if alert should be auto-acknowledged (low severity)
        if severity in (AlertSeverity.INFO, AlertSeverity.WARNING):
            self.acknowledge_alert(alert.alert_id, "system")
        
        logger.info(
            "alert_created",
            alert_id=alert.alert_id,
            severity=severity.value,
            category=category.value,
            title=title,
        )
        
        # Send alert immediately for high severity
        if severity in (AlertSeverity.ERROR, AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY):
            asyncio.create_task(self._send_alert(alert))
        
        return alert
    
    def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: Optional[str] = None,
    ) -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: ID of the alert
            acknowledged_by: Who acknowledged the alert
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            alert = self._active_alerts.get(alert_id)
            if not alert:
                return False
            
            if alert.status == AlertStatus.RESOLVED:
                return False
            
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = acknowledged_by
            
            self._save_alert(alert)
        
        logger.info(
            "alert_acknowledged",
            alert_id=alert_id,
            acknowledged_by=acknowledged_by or "unknown",
        )
        return True
    
    def resolve_alert(
        self,
        alert_id: str,
        resolved_by: Optional[str] = None,
    ) -> bool:
        """
        Resolve an alert.
        
        Args:
            alert_id: ID of the alert
            resolved_by: Who resolved the alert
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            alert = self._active_alerts.get(alert_id)
            if not alert:
                return False
            
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.utcnow()
            
            self._save_alert(alert)
            
            # Remove from active alerts
            del self._active_alerts[alert_id]
        
        logger.info(
            "alert_resolved",
            alert_id=alert_id,
            resolved_by=resolved_by or "unknown",
        )
        return True
    
    async def _send_alert(
        self,
        alert: Alert,
        channels: Optional[List[str]] = None,
        is_escalation: bool = False,
    ) -> None:
        """
        Send an alert through configured channels.
        
        Args:
            alert: Alert to send
            channels: List of channel IDs to use (if None, use all enabled channels)
            is_escalation: Whether this is an escalation
        """
        if channels is None:
            # Use channels from config
            channels = self.config.get("default_channels", [])
        
        # Find matching channel configurations
        channel_objs = []
        for channel_id in channels:
            channel = self.channels.get(channel_id)
            if channel and channel.enabled:
                # Check rate limit
                if not self._check_rate_limit(channel_id):
                    logger.warning(
                        "rate_limit_exceeded",
                        channel_id=channel_id,
                        alert_id=alert.alert_id,
                    )
                    continue
                channel_objs.append(channel)
        
        if not channel_objs:
            logger.warning(
                "no_channels_available",
                alert_id=alert.alert_id,
                requested_channels=channels,
            )
            return
        
        # Send through each channel
        tasks = []
        for channel in channel_objs:
            task = self._send_to_channel(channel, alert, is_escalation)
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_to_channel(
        self,
        channel: Channel,
        alert: Alert,
        is_escalation: bool,
    ) -> None:
        """
        Send an alert through a specific channel with retries.
        
        Args:
            channel: Channel configuration
            alert: Alert to send
            is_escalation: Whether this is an escalation
        """
        for attempt in range(channel.retry_count):
            try:
                if channel.type == ChannelType.SLACK:
                    await self._send_slack(channel, alert, is_escalation)
                elif channel.type == ChannelType.TELEGRAM:
                    await self._send_telegram(channel, alert, is_escalation)
                elif channel.type == ChannelType.EMAIL:
                    await self._send_email(channel, alert, is_escalation)
                elif channel.type == ChannelType.WEBHOOK:
                    await self._send_webhook(channel, alert, is_escalation)
                elif channel.type == ChannelType.PAGERDUTY:
                    await self._send_pagerduty(channel, alert, is_escalation)
                elif channel.type == ChannelType.OPSGENIE:
                    await self._send_opsgenie(channel, alert, is_escalation)
                elif channel.type == ChannelType.DISCORD:
                    await self._send_discord(channel, alert, is_escalation)
                else:
                    logger.warning(
                        "unsupported_channel_type",
                        type=channel.type.value,
                        channel_id=channel.channel_id,
                    )
                
                logger.info(
                    "alert_sent",
                    alert_id=alert.alert_id,
                    channel=channel.name,
                    attempt=attempt + 1,
                )
                return
                
            except Exception as e:
                logger.error(
                    "alert_send_failed",
                    alert_id=alert.alert_id,
                    channel=channel.name,
                    attempt=attempt + 1,
                    error=str(e),
                )
                if attempt < channel.retry_count - 1:
                    await asyncio.sleep(channel.retry_delay_seconds)
        
        logger.error(
            "alert_send_failed_all_retries",
            alert_id=alert.alert_id,
            channel=channel.name,
            retry_count=channel.retry_count,
        )
        
        # Increment retry count
        alert.retry_count += 1
        self._save_alert(alert)
    
    async def _send_slack(
        self,
        channel: Channel,
        alert: Alert,
        is_escalation: bool,
    ) -> None:
        """Send alert to Slack."""
        webhook_url = channel.config.get("webhook_url")
        if not webhook_url:
            raise ValueError("Slack webhook URL not configured")
        
        # Prepare message
        color = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ffaa00",
            AlertSeverity.ERROR: "#ff4466",
            AlertSeverity.CRITICAL: "#ff0000",
            AlertSeverity.EMERGENCY: "#cc0000",
        }.get(alert.severity, "#36a64f")
        
        message = {
            "attachments": [
                {
                    "color": color,
                    "title": f"{'🚨 ' if is_escalation else ''}{alert.title}",
                    "text": alert.message,
                    "fields": [
                        {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                        {"title": "Category", "value": alert.category.value, "short": True},
                        {"title": "Source", "value": alert.source, "short": True},
                        {"title": "Status", "value": alert.status.value, "short": True},
                    ],
                    "footer": f"NEXUS Alert Manager v3.0.0 | {alert.alert_id}",
                    "ts": int(alert.timestamp.timestamp()),
                }
            ]
        }
        
        # Add details if present
        if alert.details:
            details_text = "\n".join([f"• {k}: {v}" for k, v in alert.details.items()])
            message["attachments"][0]["fields"].append({
                "title": "Details",
                "value": details_text[:500],
                "short": False,
            })
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=message, timeout=channel.timeout_seconds) as response:
                if response.status not in (200, 201, 204):
                    raise Exception(f"Slack returned status {response.status}")
    
    async def _send_telegram(
        self,
        channel: Channel,
        alert: Alert,
        is_escalation: bool,
    ) -> None:
        """Send alert to Telegram."""
        bot_token = channel.config.get("bot_token")
        chat_id = channel.config.get("chat_id")
        
        if not bot_token or not chat_id:
            raise ValueError("Telegram bot token or chat ID not configured")
        
        # Prepare message
        emoji = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.ERROR: "❌",
            AlertSeverity.CRITICAL: "🚨",
            AlertSeverity.EMERGENCY: "🔥",
        }.get(alert.severity, "ℹ️")
        
        message = f"{emoji} *{alert.title}*\n"
        message += f"_Severity:_ {alert.severity.value.upper()}\n"
        message += f"_Category:_ {alert.category.value}\n"
        message += f"_Source:_ {alert.source}\n"
        message += f"_Status:_ {alert.status.value}\n"
        message += f"\n{alert.message}\n"
        
        if alert.details:
            message += "\n*Details:*\n"
            for k, v in alert.details.items():
                message += f"• {k}: {v}\n"
        
        if is_escalation:
            message += "\n⚠️ *This is an escalation!* ⚠️\n"
        
        message += f"\n`{alert.alert_id}`"
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=channel.timeout_seconds) as response:
                if response.status != 200:
                    error = await response.text()
                    raise Exception(f"Telegram returned status {response.status}: {error}")
    
    async def _send_email(
        self,
        channel: Channel,
        alert: Alert,
        is_escalation: bool,
    ) -> None:
        """Send alert via email."""
        smtp_host = channel.config.get("smtp_host")
        smtp_port = channel.config.get("smtp_port", 587)
        smtp_user = channel.config.get("smtp_user")
        smtp_password = channel.config.get("smtp_password")
        from_email = channel.config.get("from_email")
        to_emails = channel.config.get("to_emails", [])
        
        if not all([smtp_host, smtp_user, smtp_password, from_email, to_emails]):
            raise ValueError("Email configuration incomplete")
        
        if isinstance(to_emails, str):
            to_emails = [to_emails]
        
        # Create email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{alert.severity.value.upper()}] {alert.title}"
        msg["From"] = from_email
        msg["To"] = ", ".join(to_emails)
        
        # Plain text version
        text = f"""
        Alert ID: {alert.alert_id}
        Severity: {alert.severity.value.upper()}
        Category: {alert.category.value}
        Source: {alert.source}
        Status: {alert.status.value}
        Timestamp: {alert.timestamp.isoformat()}
        
        {alert.title}
        {'=' * len(alert.title)}
        
        {alert.message}
        
        Details:
        {json.dumps(alert.details, indent=2) if alert.details else 'None'}
        
        {'* ESCALATED *' if is_escalation else ''}
        
        NEXUS Hedge Bot Alert Manager v3.0.0
        """
        
        # HTML version
        html = f"""
        <html>
        <body>
        <h2 style="color: {'#ff0000' if alert.severity in (AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY) else '#ffaa00' if alert.severity == AlertSeverity.ERROR else '#36a64f'};">
            {alert.title}
        </h2>
        <table>
            <tr><td><strong>Alert ID:</strong></td><td>{alert.alert_id}</td></tr>
            <tr><td><strong>Severity:</strong></td><td>{alert.severity.value.upper()}</td></tr>
            <tr><td><strong>Category:</strong></td><td>{alert.category.value}</td></tr>
            <tr><td><strong>Source:</strong></td><td>{alert.source}</td></tr>
            <tr><td><strong>Status:</strong></td><td>{alert.status.value}</td></tr>
            <tr><td><strong>Timestamp:</strong></td><td>{alert.timestamp.isoformat()}</td></tr>
        </table>
        <p><strong>Message:</strong></p>
        <p>{alert.message}</p>
        """
        
        if alert.details:
            html += "<p><strong>Details:</strong></p>"
            html += "<ul>"
            for k, v in alert.details.items():
                html += f"<li><strong>{k}:</strong> {v}</li>"
            html += "</ul>"
        
        if is_escalation:
            html += '<p style="color: #ff0000; font-weight: bold;">⚠️ ESCALATED ⚠️</p>'
        
        html += """
        <p style="color: #666; font-size: 12px; margin-top: 20px;">
            NEXUS Hedge Bot Alert Manager v3.0.0
        </p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))
        
        # Send email
        with smtplib.SMTP(smtp_host, smtp_port, timeout=channel.timeout_seconds) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, to_emails, msg.as_string())
    
    async def _send_webhook(
        self,
        channel: Channel,
        alert: Alert,
        is_escalation: bool,
    ) -> None:
        """Send alert via webhook."""
        webhook_url = channel.config.get("webhook_url")
        method = channel.config.get("method", "POST")
        headers = channel.config.get("headers", {})
        
        if not webhook_url:
            raise ValueError("Webhook URL not configured")
        
        payload = alert.to_dict()
        payload["is_escalation"] = is_escalation
        
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method,
                url=webhook_url,
                json=payload,
                headers=headers,
                timeout=channel.timeout_seconds,
            ) as response:
                if response.status not in (200, 201, 202, 204):
                    error = await response.text()
                    raise Exception(f"Webhook returned status {response.status}: {error}")
    
    async def _send_pagerduty(
        self,
        channel: Channel,
        alert: Alert,
        is_escalation: bool,
    ) -> None:
        """Send alert to PagerDuty."""
        integration_key = channel.config.get("integration_key")
        if not integration_key:
            raise ValueError("PagerDuty integration key not configured")
        
        severity_map = {
            AlertSeverity.INFO: "info",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.ERROR: "error",
            AlertSeverity.CRITICAL: "critical",
            AlertSeverity.EMERGENCY: "critical",
        }
        
        payload = {
            "routing_key": integration_key,
            "event_action": "trigger",
            "dedup_key": alert.alert_id,
            "payload": {
                "summary": alert.title,
                "source": alert.source,
                "severity": severity_map.get(alert.severity, "info"),
                "timestamp": alert.timestamp.isoformat(),
                "component": alert.category.value,
                "group": "hedge_bot",
                "class": "trading_alert",
                "custom_details": alert.details,
            },
            "links": [
                {
                    "href": f"https://nexusquantum.com/alerts/{alert.alert_id}",
                    "text": "View in Nexus Dashboard",
                }
            ],
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
                timeout=channel.timeout_seconds,
            ) as response:
                if response.status != 202:
                    error = await response.text()
                    raise Exception(f"PagerDuty returned status {response.status}: {error}")
    
    async def _send_opsgenie(
        self,
        channel: Channel,
        alert: Alert,
        is_escalation: bool,
    ) -> None:
        """Send alert to Opsgenie."""
        api_key = channel.config.get("api_key")
        if not api_key:
            raise ValueError("Opsgenie API key not configured")
        
        payload = {
            "message": alert.title,
            "alias": alert.alert_id,
            "description": alert.message,
            "source": alert.source,
            "priority": alert.severity.value.upper(),
            "tags": alert.tags,
            "details": alert.details,
        }
        
        headers = {"Authorization": f"GenieKey {api_key}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.opsgenie.com/v2/alerts",
                json=payload,
                headers=headers,
                timeout=channel.timeout_seconds,
            ) as response:
                if response.status not in (200, 201, 202):
                    error = await response.text()
                    raise Exception(f"Opsgenie returned status {response.status}: {error}")
    
    async def _send_discord(
        self,
        channel: Channel,
        alert: Alert,
        is_escalation: bool,
    ) -> None:
        """Send alert to Discord."""
        webhook_url = channel.config.get("webhook_url")
        if not webhook_url:
            raise ValueError("Discord webhook URL not configured")
        
        color = {
            AlertSeverity.INFO: 3066993,   # Green
            AlertSeverity.WARNING: 15105570,  # Yellow
            AlertSeverity.ERROR: 15158332,    # Red
            AlertSeverity.CRITICAL: 15548997, # Dark Red
            AlertSeverity.EMERGENCY: 15548997, # Dark Red
        }.get(alert.severity, 3066993)
        
        message = {
            "embeds": [
                {
                    "title": f"{'🚨 ' if is_escalation else ''}{alert.title}",
                    "description": alert.message[:2000],
                    "color": color,
                    "fields": [
                        {"name": "Severity", "value": alert.severity.value.upper(), "inline": True},
                        {"name": "Category", "value": alert.category.value, "inline": True},
                        {"name": "Source", "value": alert.source, "inline": True},
                        {"name": "Status", "value": alert.status.value, "inline": True},
                    ],
                    "footer": {"text": f"NEXUS Alert Manager v3.0.0 | {alert.alert_id}"},
                    "timestamp": alert.timestamp.isoformat(),
                }
            ]
        }
        
        if alert.details:
            details_text = "\n".join([f"{k}: {v}" for k, v in alert.details.items()])
            message["embeds"][0]["fields"].append({
                "name": "Details",
                "value": details_text[:1000],
                "inline": False,
            })
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=message, timeout=channel.timeout_seconds) as response:
                if response.status not in (200, 201, 204):
                    raise Exception(f"Discord returned status {response.status}")
    
    def _check_rate_limit(self, channel_id: str) -> bool:
        """
        Check if a channel's rate limit has been exceeded.
        
        Args:
            channel_id: ID of the channel
            
        Returns:
            True if rate limit not exceeded, False otherwise
        """
        if channel_id not in self._rate_limits:
            self._rate_limits[channel_id] = []
        
        channel = self.channels.get(channel_id)
        if not channel:
            return False
        
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=1)
        
        # Clean old entries
        self._rate_limits[channel_id] = [
            ts for ts in self._rate_limits[channel_id]
            if ts > window_start
        ]
        
        if len(self._rate_limits[channel_id]) >= channel.rate_limit:
            return False
        
        self._rate_limits[channel_id].append(now)
        return True
    
    def _save_alert(self, alert: Alert) -> None:
        """Save alert to database."""
        try:
            self._db.execute("""
                INSERT OR REPLACE INTO alerts (
                    alert_id, timestamp, source, category, severity, title, message,
                    details, status, acknowledged_at, resolved_at, acknowledged_by,
                    escalation_level, retry_count, correlation_id, tags, ttl_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id,
                alert.timestamp.isoformat(),
                alert.source,
                alert.category.value,
                alert.severity.value,
                alert.title,
                alert.message,
                json.dumps(alert.details),
                alert.status.value,
                alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                alert.resolved_at.isoformat() if alert.resolved_at else None,
                alert.acknowledged_by,
                alert.escalation_level,
                alert.retry_count,
                alert.correlation_id,
                json.dumps(alert.tags),
                alert.ttl_seconds,
            ))
        except Exception as e:
            logger.error("failed_to_save_alert", alert_id=alert.alert_id, error=str(e))
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """
        Get an alert by ID.
        
        Args:
            alert_id: ID of the alert
            
        Returns:
            Alert object or None if not found
        """
        # Check cache first
        if alert_id in self._alert_cache:
            return self._alert_cache[alert_id]
        
        # Query database
        cursor = self._db.execute(
            "SELECT * FROM alerts WHERE alert_id = ?",
            (alert_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        
        columns = [desc[0] for desc in cursor.description]
        data = dict(zip(columns, row))
        data["details"] = json.loads(data["details"]) if data.get("details") else {}
        data["tags"] = json.loads(data["tags"]) if data.get("tags") else []
        
        alert = Alert.from_dict(data)
        self._alert_cache[alert_id] = alert
        return alert
    
    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
        category: Optional[AlertCategory] = None,
    ) -> List[Alert]:
        """
        Get all active alerts.
        
        Args:
            severity: Filter by severity
            category: Filter by category
            
        Returns:
            List of active alerts
        """
        alerts = list(self._active_alerts.values())
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if category:
            alerts = [a for a in alerts if a.category == category]
        
        return alerts
    
    def get_alert_history(
        self,
        limit: int = 100,
        offset: int = 0,
        severity: Optional[AlertSeverity] = None,
        category: Optional[AlertCategory] = None,
        status: Optional[AlertStatus] = None,
    ) -> List[Alert]:
        """
        Get alert history.
        
        Args:
            limit: Maximum number of alerts to return
            offset: Pagination offset
            severity: Filter by severity
            category: Filter by category
            status: Filter by status
            
        Returns:
            List of alerts
        """
        sql = "SELECT * FROM alerts WHERE 1=1"
        params = []
        
        if severity:
            sql += " AND severity = ?"
            params.append(severity.value)
        
        if category:
            sql += " AND category = ?"
            params.append(category.value)
        
        if status:
            sql += " AND status = ?"
            params.append(status.value)
        
        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = self._db.execute(sql, params)
        rows = cursor.fetchall()
        
        columns = [desc[0] for desc in cursor.description]
        alerts = []
        
        for row in rows:
            data = dict(zip(columns, row))
            data["details"] = json.loads(data["details"]) if data.get("details") else {}
            data["tags"] = json.loads(data["tags"]) if data.get("tags") else []
            alerts.append(Alert.from_dict(data))
        
        return alerts
    
    def add_rule(self, rule: AlertRule) -> None:
        """
        Add an alert rule.
        
        Args:
            rule: Alert rule to add
        """
        with self._lock:
            self.rules[rule.rule_id] = rule
            self._db.execute("""
                INSERT OR REPLACE INTO alert_rules (
                    rule_id, name, description, enabled, condition, severity,
                    category, channels, cooldown_seconds, escalation_policy,
                    tags, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rule.rule_id,
                rule.name,
                rule.description,
                1 if rule.enabled else 0,
                rule.condition,
                rule.severity.value,
                rule.category.value,
                json.dumps(rule.channels),
                rule.cooldown_seconds,
                json.dumps(rule.escalation_policy),
                json.dumps(rule.tags),
                rule.created_at.isoformat(),
                rule.updated_at.isoformat(),
            ))
        
        logger.info("alert_rule_added", rule_id=rule.rule_id, name=rule.name)
    
    def evaluate_rules(self, event_data: Dict[str, Any]) -> List[Alert]:
        """
        Evaluate alert rules against event data.
        
        Args:
            event_data: Event data to evaluate
            
        Returns:
            List of created alerts
        """
        alerts = []
        
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            # Check cooldown
            if rule.rule_id in self._last_alert_times:
                last = self._last_alert_times[rule.rule_id]
                if (datetime.utcnow() - last).total_seconds() < rule.cooldown_seconds:
                    continue
            
            # Evaluate condition
            try:
                # Simple condition evaluation
                # This should be replaced with a proper expression evaluator
                if self._evaluate_condition(rule.condition, event_data):
                    alert = self.create_alert(
                        source="rule_engine",
                        title=f"Rule triggered: {rule.name}",
                        message=f"Alert rule '{rule.name}' was triggered",
                        severity=rule.severity,
                        category=rule.category,
                        details={"rule_id": rule.rule_id, "event_data": event_data},
                        tags=rule.tags,
                    )
                    alerts.append(alert)
                    self._last_alert_times[rule.rule_id] = datetime.utcnow()
            except Exception as e:
                logger.error(
                    "rule_evaluation_failed",
                    rule_id=rule.rule_id,
                    error=str(e),
                )
        
        return alerts
    
    def _evaluate_condition(self, condition: str, event_data: Dict[str, Any]) -> bool:
        """
        Evaluate a condition expression.
        
        Args:
            condition: Condition expression
            event_data: Event data
            
        Returns:
            True if condition is met, False otherwise
        """
        # This is a simple implementation - should use a proper expression evaluator
        if not condition:
            return False
        
        # Simple key exists check
        if condition.startswith("exists:"):
            key = condition[7:]
            parts = key.split(".")
            value = event_data
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                    if value is None:
                        return False
                else:
                    return False
            return True
        
        # Simple value comparison
        if ">" in condition:
            parts = condition.split(">")
            key = parts[0].strip()
            threshold = float(parts[1].strip())
            value = self._get_nested_value(event_data, key)
            if value is None:
                return False
            return float(value) > threshold
        
        if "<" in condition:
            parts = condition.split("<")
            key = parts[0].strip()
            threshold = float(parts[1].strip())
            value = self._get_nested_value(event_data, key)
            if value is None:
                return False
            return float(value) < threshold
        
        if "==" in condition:
            parts = condition.split("==")
            key = parts[0].strip()
            expected = parts[1].strip()
            value = self._get_nested_value(event_data, key)
            return str(value) == expected
        
        return False
    
    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Any:
        """Get a nested value from a dictionary."""
        parts = key.split(".")
        value = data
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
                if value is None:
                    return None
            else:
                return None
        return value
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get alert manager metrics.
        
        Returns:
            Dictionary of metrics
        """
        return {
            "active_alerts": len(self._active_alerts),
            "total_alerts": self._get_total_alerts(),
            "rules_count": len(self.rules),
            "channels_count": len(self.channels),
            "alert_by_severity": self._get_alert_counts_by_severity(),
            "alert_by_category": self._get_alert_counts_by_category(),
            "alert_by_status": self._get_alert_counts_by_status(),
        }
    
    def _get_total_alerts(self) -> int:
        """Get total number of alerts in database."""
        cursor = self._db.execute("SELECT COUNT(*) FROM alerts")
        return cursor.fetchone()[0]
    
    def _get_alert_counts_by_severity(self) -> Dict[str, int]:
        """Get alert counts grouped by severity."""
        cursor = self._db.execute(
            "SELECT severity, COUNT(*) FROM alerts GROUP BY severity"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}
    
    def _get_alert_counts_by_category(self) -> Dict[str, int]:
        """Get alert counts grouped by category."""
        cursor = self._db.execute(
            "SELECT category, COUNT(*) FROM alerts GROUP BY category"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}
    
    def _get_alert_counts_by_status(self) -> Dict[str, int]:
        """Get alert counts grouped by status."""
        cursor = self._db.execute(
            "SELECT status, COUNT(*) FROM alerts GROUP BY status"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}
    
    def close(self) -> None:
        """Close the alert manager."""
        if self._closed:
            return
        
        self._closed = True
        
        if hasattr(self, "_db") and self._db:
            self._db.close()
        
        self._executor.shutdown(wait=True)
        
        logger.info("alert_manager_closed")
    
    def __enter__(self) -> "AlertManager":
        return self
    
    def __exit__(self, *args) -> None:
        self.close()


# === MODULE EXPORTS ===

__all__ = [
    "AlertManager",
    "Alert",
    "AlertRule",
    "Channel",
    "AlertSeverity",
    "AlertCategory",
    "AlertStatus",
    "ChannelType",
]

logger.info("alert_manager_module_loaded", version="3.0.0")
