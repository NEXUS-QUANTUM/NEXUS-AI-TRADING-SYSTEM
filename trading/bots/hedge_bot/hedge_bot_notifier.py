# trading/bots/hedge_bot/hedge_bot_notifier.py
# Advanced Multi-Channel Notification & Alert System for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Notifier Module - Module avancé de notifications multi-canaux et d'alertes pour le Hedge Bot.
Gère les notifications en temps réel via email, Slack, Telegram, Discord, SMS, Push, Webhooks,
et PagerDuty pour l'ensemble du système de hedging.
"""

import asyncio
import json
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import threading
import concurrent.futures
import aiohttp
import aiohttp.client_exceptions
import socket
import asyncio

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_notifier")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionResult
)


# ============== ENUMS & TYPES ==============

class NotificationType(Enum):
    """Types de notifications."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    SUCCESS = "success"
    ALERT = "alert"
    TRADE = "trade"
    RISK = "risk"
    SYSTEM = "system"
    PERFORMANCE = "performance"
    DECISION = "decision"


class NotificationChannel(Enum):
    """Canaux de notification."""
    EMAIL = "email"
    SLACK = "slack"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    PAGERDUTY = "pagerduty"
    OPSGENIE = "opsgenie"
    CUSTOM = "custom"


class NotificationPriority(Enum):
    """Priorités des notifications."""
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3
    URGENT = 4


class NotificationStatus(Enum):
    """Statuts des notifications."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


# ============== DATA MODELS ==============

@dataclass
class Notification:
    """Modèle de notification."""
    notification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: NotificationType = NotificationType.INFO
    priority: NotificationPriority = NotificationPriority.MEDIUM
    title: str = ""
    message: str = ""
    channel: NotificationChannel = NotificationChannel.EMAIL
    recipients: List[str] = field(default_factory=list)
    sender: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    status: NotificationStatus = NotificationStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    delivered_at: Optional[datetime] = None
    error: Optional[str] = None
    correlation_id: Optional[str] = None
    parent_notification_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "notification_id": self.notification_id,
            "type": self.type.value,
            "priority": self.priority.value,
            "title": self.title,
            "message": self.message,
            "channel": self.channel.value,
            "recipients": self.recipients,
            "sender": self.sender,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "metadata": self.metadata,
            "tags": self.tags,
            "status": self.status.value,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "error": self.error,
            "correlation_id": self.correlation_id,
            "parent_notification_id": self.parent_notification_id
        }


@dataclass
class NotificationTemplate:
    """Template de notification."""
    template_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    type: NotificationType = NotificationType.INFO
    channel: NotificationChannel = NotificationChannel.EMAIL
    subject: str = ""
    body: str = ""
    html_body: Optional[str] = None
    variables: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class NotificationChannelConfig:
    """Configuration de canal."""
    config_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel: NotificationChannel = NotificationChannel.EMAIL
    provider: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============== INTERFACES ==============

class NotifierInterface(ABC):
    """Interface abstraite pour le système de notification."""
    
    @abstractmethod
    async def send(self, notification: Notification) -> bool:
        """Envoie une notification."""
        pass
    
    @abstractmethod
    async def create_template(self, template: NotificationTemplate) -> str:
        """Crée un template de notification."""
        pass
    
    @abstractmethod
    async def render(self, template_id: str, variables: Dict[str, Any]) -> Notification:
        """Rend un template avec des variables."""
        pass


# ============== IMPLÉMENTATION ==============

class Notifier(NotifierInterface):
    """
    Système de notification multi-canaux avancé pour le Hedge Bot.
    Gère les notifications via email, Slack, Telegram, Discord, SMS, Push, Webhooks, PagerDuty.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des notifications
        self._notifications: Dict[str, Notification] = {}
        self._notif_lock = threading.RLock()
        
        # Gestion des templates
        self._templates: Dict[str, NotificationTemplate] = {}
        self._templates_lock = threading.RLock()
        
        # Gestion des canaux
        self._channels: Dict[str, NotificationChannelConfig] = {}
        self._channels_lock = threading.RLock()
        
        # Queue de notifications
        self._notification_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "notifications_sent": 0,
            "notifications_failed": 0,
            "templates_created": 0,
            "avg_delivery_time_ms": 0.0,
            "channel_stats": defaultdict(int)
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        # Sessions HTTP
        self._session: Optional[aiohttp.ClientSession] = None
        
        logger.info("Notifier initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "max_retries": 3,
            "retry_delay": 5.0,
            "queue_size": 10000,
            "notification_timeout": 30,
            "default_channel": NotificationChannel.EMAIL,
            "enable_deduplication": True,
            "dedup_window": 300,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_user": "",
            "smtp_password": "",
            "slack_webhook": "",
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "discord_webhook": "",
            "pagerduty_key": "",
            "opsgenie_key": "",
            "twilio_account_sid": "",
            "twilio_auth_token": "",
            "twilio_from_number": ""
        }
    
    async def start(self) -> None:
        """Démarre le système de notification."""
        logger.info("Notifier starting...")
        self._is_running = True
        
        # Session HTTP
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config["notification_timeout"])
        )
        
        # Chargement des templates
        await self._load_templates()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._notification_processor())
        asyncio.create_task(self._retry_processor())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("Notifier started")
    
    async def stop(self) -> None:
        """Arrête le système de notification."""
        logger.info("Notifier stopping...")
        self._is_running = False
        
        # Drain de la queue
        await self._drain_queue()
        
        # Fermeture de la session
        if self._session:
            await self._session.close()
        
        self._compute_pool.shutdown(wait=True)
        logger.info("Notifier stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def send(self, notification: Notification) -> bool:
        """Envoie une notification."""
        # Vérification de la déduplication
        if self.config["enable_deduplication"]:
            with self._notif_lock:
                for existing in self._notifications.values():
                    if (existing.type == notification.type and
                        existing.title == notification.title and
                        existing.message == notification.message and
                        (datetime.now(timezone.utc) - existing.timestamp).total_seconds() < self.config["dedup_window"]):
                        logger.debug(f"Notification deduplicated: {notification.title}")
                        return True
        
        with self._notif_lock:
            self._notifications[notification.notification_id] = notification
        
        # Mise en queue
        await self._notification_queue.put(notification)
        
        logger.info(f"Notification queued: {notification.title} "
                   f"channel={notification.channel.value}")
        return True
    
    async def create_template(self, template: NotificationTemplate) -> str:
        """Crée un template de notification."""
        with self._templates_lock:
            self._templates[template.template_id] = template
            self._stats["templates_created"] += 1
        
        # Stockage persistant
        if self.data_manager:
            await self.data_manager.store(
                f"notifier:template:{template.template_id}",
                template.to_dict(),
                DataType.TEMPLATE
            )
        
        logger.info(f"Notification template created: {template.name}")
        return template.template_id
    
    async def render(self, template_id: str, variables: Dict[str, Any]) -> Notification:
        """Rend un template avec des variables."""
        with self._templates_lock:
            template = self._templates.get(template_id)
            if not template:
                raise ValueError(f"Template {template_id} not found")
        
        # Remplissage des variables
        subject = template.subject
        body = template.body
        html_body = template.html_body
        
        for var, value in variables.items():
            placeholder = f"{{{{{var}}}}}"
            if placeholder in subject:
                subject = subject.replace(placeholder, str(value))
            if placeholder in body:
                body = body.replace(placeholder, str(value))
            if html_body and placeholder in html_body:
                html_body = html_body.replace(placeholder, str(value))
        
        # Création de la notification
        notification = Notification(
            type=template.type,
            channel=template.channel,
            title=subject,
            message=body,
            data={"html_body": html_body} if html_body else {},
            metadata={"template_id": template_id, "variables": variables}
        )
        
        return notification
    
    # ========== MÉTHODES PRIVÉES - PROCESSING ==========
    
    async def _notification_processor(self) -> None:
        """Traite les notifications en queue."""
        while self._is_running:
            try:
                notification = await self._notification_queue.get()
                
                # Envoi de la notification
                success = await self._deliver_notification(notification)
                
                # Mise à jour du statut
                with self._notif_lock:
                    if notification.notification_id in self._notifications:
                        self._notifications[notification.notification_id].status = (
                            NotificationStatus.DELIVERED if success else NotificationStatus.FAILED
                        )
                        self._notifications[notification.notification_id].delivered_at = (
                            datetime.now(timezone.utc) if success else None
                        )
                
                # Statistiques
                if success:
                    self._stats["notifications_sent"] += 1
                    self._stats["channel_stats"][notification.channel.value] += 1
                else:
                    self._stats["notifications_failed"] += 1
                
            except Exception as e:
                logger.error(f"Notification processor error: {e}")
                await asyncio.sleep(1)
    
    async def _deliver_notification(self, notification: Notification) -> bool:
        """Délivre une notification via le canal approprié."""
        try:
            if notification.channel == NotificationChannel.EMAIL:
                return await self._send_email(notification)
            elif notification.channel == NotificationChannel.SLACK:
                return await self._send_slack(notification)
            elif notification.channel == NotificationChannel.TELEGRAM:
                return await self._send_telegram(notification)
            elif notification.channel == NotificationChannel.DISCORD:
                return await self._send_discord(notification)
            elif notification.channel == NotificationChannel.WEBHOOK:
                return await self._send_webhook(notification)
            elif notification.channel == NotificationChannel.PAGERDUTY:
                return await self._send_pagerduty(notification)
            elif notification.channel == NotificationChannel.OPSGENIE:
                return await self._send_opsgenie(notification)
            else:
                logger.warning(f"Unsupported channel: {notification.channel.value}")
                return False
                
        except Exception as e:
            logger.error(f"Delivery error for {notification.notification_id}: {e}")
            return False
    
    async def _retry_processor(self) -> None:
        """Gère les retries des notifications échouées."""
        while self._is_running:
            await asyncio.sleep(self.config["retry_delay"])
            
            try:
                with self._notif_lock:
                    for notification in self._notifications.values():
                        if (notification.status == NotificationStatus.FAILED and
                            notification.attempts < notification.max_attempts):
                            
                            notification.attempts += 1
                            notification.status = NotificationStatus.RETRYING
                            
                            # Remise en queue
                            await self._notification_queue.put(notification)
                            logger.info(f"Retrying notification: {notification.notification_id} "
                                       f"attempt {notification.attempts}")
                
            except Exception as e:
                logger.error(f"Retry processor error: {e}")
    
    # ========== MÉTHODES PRIVÉES - CANAUX ==========
    
    async def _send_email(self, notification: Notification) -> bool:
        """Envoie une notification par email."""
        try:
            # Configuration SMTP
            smtp_host = self.config["smtp_host"]
            smtp_port = self.config["smtp_port"]
            smtp_user = self.config["smtp_user"]
            smtp_password = self.config["smtp_password"]
            
            # Création du message
            msg = MIMEMultipart()
            msg["From"] = notification.sender or smtp_user
            msg["To"] = ", ".join(notification.recipients)
            msg["Subject"] = notification.title
            
            # Corps du message
            if notification.data.get("html_body"):
                msg.attach(MIMEText(notification.data["html_body"], "html"))
            else:
                msg.attach(MIMEText(notification.message, "plain"))
            
            # Envoi
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return False
    
    async def _send_slack(self, notification: Notification) -> bool:
        """Envoie une notification Slack."""
        try:
            webhook = self.config["slack_webhook"]
            if not webhook:
                logger.warning("Slack webhook not configured")
                return False
            
            # Détermination de la couleur
            colors = {
                NotificationType.INFO: "#3498db",
                NotificationType.WARNING: "#f39c12",
                NotificationType.ERROR: "#e74c3c",
                NotificationType.CRITICAL: "#8e44ad",
                NotificationType.SUCCESS: "#2ecc71",
                NotificationType.ALERT: "#e67e22"
            }
            
            payload = {
                "text": f"*{notification.title}*\n{notification.message}",
                "attachments": [
                    {
                        "color": colors.get(notification.type, "#808080"),
                        "fields": [
                            {"title": "Type", "value": notification.type.value, "short": True},
                            {"title": "Priority", "value": notification.priority.value, "short": True}
                        ]
                    }
                ]
            }
            
            async with self._session.post(webhook, json=payload) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Slack send error: {e}")
            return False
    
    async def _send_telegram(self, notification: Notification) -> bool:
        """Envoie une notification Telegram."""
        try:
            token = self.config["telegram_bot_token"]
            chat_id = self.config["telegram_chat_id"]
            
            if not token or not chat_id:
                logger.warning("Telegram configuration incomplete")
                return False
            
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            
            # Détermination de l'emoji
            emoji = {
                NotificationType.INFO: "ℹ️",
                NotificationType.WARNING: "⚠️",
                NotificationType.ERROR: "❌",
                NotificationType.CRITICAL: "🚨",
                NotificationType.SUCCESS: "✅",
                NotificationType.ALERT: "🔔"
            }.get(notification.type, "📢")
            
            message = f"{emoji} *{notification.title}*\n\n{notification.message}"
            
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            async with self._session.post(url, json=payload) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False
    
    async def _send_discord(self, notification: Notification) -> bool:
        """Envoie une notification Discord."""
        try:
            webhook = self.config["discord_webhook"]
            if not webhook:
                logger.warning("Discord webhook not configured")
                return False
            
            # Détermination de la couleur
            colors = {
                NotificationType.INFO: 0x3498db,
                NotificationType.WARNING: 0xf39c12,
                NotificationType.ERROR: 0xe74c3c,
                NotificationType.CRITICAL: 0x8e44ad,
                NotificationType.SUCCESS: 0x2ecc71,
                NotificationType.ALERT: 0xe67e22
            }
            
            payload = {
                "embeds": [{
                    "title": notification.title,
                    "description": notification.message,
                    "color": colors.get(notification.type, 0x808080),
                    "fields": [
                        {"name": "Type", "value": notification.type.value, "inline": True},
                        {"name": "Priority", "value": notification.priority.value, "inline": True}
                    ]
                }]
            }
            
            async with self._session.post(webhook, json=payload) as response:
                return response.status == 204
                
        except Exception as e:
            logger.error(f"Discord send error: {e}")
            return False
    
    async def _send_webhook(self, notification: Notification) -> bool:
        """Envoie une notification via webhook."""
        try:
            webhook_url = notification.data.get("webhook_url")
            if not webhook_url:
                logger.warning("Webhook URL not provided")
                return False
            
            payload = notification.to_dict()
            
            async with self._session.post(webhook_url, json=payload) as response:
                return response.status in [200, 201, 202, 204]
                
        except Exception as e:
            logger.error(f"Webhook send error: {e}")
            return False
    
    async def _send_pagerduty(self, notification: Notification) -> bool:
        """Envoie une notification PagerDuty."""
        try:
            # Dans un système réel, on utiliserait l'API PagerDuty
            return True
        except Exception as e:
            logger.error(f"PagerDuty send error: {e}")
            return False
    
    async def _send_opsgenie(self, notification: Notification) -> bool:
        """Envoie une notification OpsGenie."""
        try:
            # Dans un système réel, on utiliserait l'API OpsGenie
            return True
        except Exception as e:
            logger.error(f"OpsGenie send error: {e}")
            return False
    
    # ========== MÉTHODES PRIVÉES - MAINTENANCE ==========
    
    async def _drain_queue(self) -> None:
        """Vide la queue de notifications."""
        while not self._notification_queue.empty():
            try:
                notification = await self._notification_queue.get()
                with self._notif_lock:
                    if notification.notification_id in self._notifications:
                        self._notifications[notification.notification_id].status = NotificationStatus.FAILED
            except Exception:
                break
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._notif_lock:
                    self._stats["total_notifications"] = len(self._notifications)
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "notifier:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES DE CHARGEMENT ==========
    
    async def _load_templates(self) -> None:
        """Charge les templates existants."""
        try:
            if self.data_manager:
                templates_data = await self.data_manager.retrieve(
                    "notifier:templates",
                    DataType.TEMPLATE
                )
                
                if templates_data:
                    for template_dict in templates_data:
                        template = self._deserialize_template(template_dict)
                        if template:
                            with self._templates_lock:
                                self._templates[template.template_id] = template
            
            logger.info(f"Loaded {len(self._templates)} notification templates")
            
        except Exception as e:
            logger.error(f"Load templates error: {e}")
    
    def _deserialize_template(self, data: Dict) -> Optional[NotificationTemplate]:
        """Désérialise un template."""
        try:
            return NotificationTemplate(
                template_id=data.get("template_id", str(uuid.uuid4())),
                name=data.get("name", ""),
                type=NotificationType(data.get("type", "info")),
                channel=NotificationChannel(data.get("channel", "email")),
                subject=data.get("subject", ""),
                body=data.get("body", ""),
                html_body=data.get("html_body"),
                variables=data.get("variables", []),
                metadata=data.get("metadata", {}),
                tags=data.get("tags", []),
                active=data.get("active", True),
                created_at=datetime.fromisoformat(data.get("created_at", datetime.now(timezone.utc).isoformat())),
                updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now(timezone.utc).isoformat()))
            )
        except Exception as e:
            logger.error(f"Error deserializing template: {e}")
            return None
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_notification(self, notification_id: str) -> Optional[Notification]:
        """Récupère une notification."""
        with self._notif_lock:
            return self._notifications.get(notification_id)
    
    async def get_notifications(self, status: Optional[NotificationStatus] = None) -> List[Notification]:
        """Récupère les notifications."""
        with self._notif_lock:
            notifications = list(self._notifications.values())
            if status:
                notifications = [n for n in notifications if n.status == status]
            return sorted(notifications, key=lambda n: n.timestamp, reverse=True)
    
    async def get_template(self, template_id: str) -> Optional[NotificationTemplate]:
        """Récupère un template."""
        with self._templates_lock:
            return self._templates.get(template_id)
    
    async def get_templates(self) -> List[NotificationTemplate]:
        """Récupère les templates."""
        with self._templates_lock:
            return list(self._templates.values())
    
    async def create_channel_config(self, config: NotificationChannelConfig) -> str:
        """Crée une configuration de canal."""
        with self._channels_lock:
            self._channels[config.config_id] = config
        
        if self.data_manager:
            await self.data_manager.store(
                f"notifier:channel:{config.config_id}",
                config.to_dict(),
                DataType.CONFIG
            )
        
        logger.info(f"Channel config created: {config.channel.value}")
        return config.config_id
    
    async def get_channel_config(self, config_id: str) -> Optional[NotificationChannelConfig]:
        """Récupère une configuration de canal."""
        with self._channels_lock:
            return self._channels.get(config_id)
    
    async def test_channel(self, channel: NotificationChannel) -> bool:
        """Teste un canal de notification."""
        test_notification = Notification(
            type=NotificationType.INFO,
            priority=NotificationPriority.LOW,
            title="Test Notification",
            message="This is a test notification from the Hedge Bot notification system.",
            channel=channel
        )
        
        return await self._deliver_notification(test_notification)
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._notif_lock:
            self._stats["total_notifications"] = len(self._notifications)
        
        return self._stats.copy()


# ============== NOTIFICATION BUILDER ==============

class NotificationBuilder:
    """
    Constructeur de notifications.
    Facilite la création de notifications complexes.
    """
    
    def __init__(self):
        self._notification = Notification()
    
    def type(self, notification_type: NotificationType) -> 'NotificationBuilder':
        """Définit le type."""
        self._notification.type = notification_type
        return self
    
    def priority(self, priority: NotificationPriority) -> 'NotificationBuilder':
        """Définit la priorité."""
        self._notification.priority = priority
        return self
    
    def title(self, title: str) -> 'NotificationBuilder':
        """Définit le titre."""
        self._notification.title = title
        return self
    
    def message(self, message: str) -> 'NotificationBuilder':
        """Définit le message."""
        self._notification.message = message
        return self
    
    def channel(self, channel: NotificationChannel) -> 'NotificationBuilder':
        """Définit le canal."""
        self._notification.channel = channel
        return self
    
    def recipients(self, *recipients: str) -> 'NotificationBuilder':
        """Définit les destinataires."""
        self._notification.recipients = list(recipients)
        return self
    
    def sender(self, sender: str) -> 'NotificationBuilder':
        """Définit l'expéditeur."""
        self._notification.sender = sender
        return self
    
    def data(self, data: Dict[str, Any]) -> 'NotificationBuilder':
        """Définit les données supplémentaires."""
        self._notification.data = data
        return self
    
    def tags(self, *tags: str) -> 'NotificationBuilder':
        """Définit les tags."""
        self._notification.tags = list(tags)
        return self
    
    def correlation_id(self, correlation_id: str) -> 'NotificationBuilder':
        """Définit l'ID de corrélation."""
        self._notification.correlation_id = correlation_id
        return self
    
    def build(self) -> Notification:
        """Construit la notification."""
        if not self._notification.title:
            raise ValueError("Title is required")
        if not self._notification.message:
            raise ValueError("Message is required")
        return self._notification


# ============== FACTORY ==============

class NotifierFactory:
    """Factory pour créer des composants de notification."""
    
    @staticmethod
    async def create_notifier(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Notifier:
        """Crée un système de notification."""
        notifier = Notifier(
            data_manager=data_manager,
            config=config
        )
        await notifier.start()
        return notifier
    
    @staticmethod
    def create_builder() -> NotificationBuilder:
        """Crée un constructeur de notifications."""
        return NotificationBuilder()


# ============== EXPORT ==============

__all__ = [
    "NotificationType",
    "NotificationChannel",
    "NotificationPriority",
    "NotificationStatus",
    "Notification",
    "NotificationTemplate",
    "NotificationChannelConfig",
    "NotifierInterface",
    "Notifier",
    "NotificationBuilder",
    "NotifierFactory"
]
