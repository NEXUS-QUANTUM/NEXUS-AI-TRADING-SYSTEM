"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Notifier
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Système de notifications avancé pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import json
import time
import threading
import queue
import smtplib
import requests
import telegram
import slack_sdk
import discord_webhook
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional, Union, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from pathlib import Path
import hmac
import hashlib
import base64

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# ENUMS
# ============================================================

class NotificationType(Enum):
    """Types de notifications"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    TRADE = "trade"
    OPPORTUNITY = "opportunity"
    RISK = "risk"
    SYSTEM = "system"
    REPORT = "report"

class NotificationChannel(Enum):
    """Canaux de notification"""
    TELEGRAM = "telegram"
    SLACK = "slack"
    DISCORD = "discord"
    EMAIL = "email"
    WEBHOOK = "webhook"
    PUSHOVER = "pushover"
    PAGERDUTY = "pagerduty"
    SMS = "sms"
    CONSOLE = "console"

class NotificationPriority(Enum):
    """Priorités de notification"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class Notification:
    """Notification"""
    type: NotificationType
    channel: NotificationChannel
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    recipient: Optional[str] = None
    status: str = "pending"

@dataclass
class NotificationTemplate:
    """Template de notification"""
    name: str
    type: NotificationType
    channel: NotificationChannel
    template: str
    subject_template: Optional[str] = None

# ============================================================
# NOTIFIER
# ============================================================

class ArbitrageBotNotifier:
    """
    Système de notifications avancé pour le bot d'arbitrage
    
    Supporte multiples canaux, templates, gestion des files d'attente,
    et retry automatique
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        queue_size: int = 1000,
        retry_attempts: int = 3,
        retry_delay: float = 5.0,
        workers: int = 2,
        enable_telegram: bool = False,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        enable_slack: bool = False,
        slack_webhook: Optional[str] = None,
        enable_discord: bool = False,
        discord_webhook: Optional[str] = None,
        enable_email: bool = False,
        email_config: Optional[Dict[str, Any]] = None,
        enable_webhook: bool = False,
        webhook_url: Optional[str] = None,
    ):
        """
        Initialise le système de notifications
        
        Args:
            config: Configuration
            queue_size: Taille de la file d'attente
            retry_attempts: Nombre de tentatives
            retry_delay: Délai entre les tentatives
            workers: Nombre de workers
            enable_telegram: Activer Telegram
            telegram_token: Token Telegram
            telegram_chat_id: Chat ID Telegram
            enable_slack: Activer Slack
            slack_webhook: Webhook Slack
            enable_discord: Activer Discord
            discord_webhook: Webhook Discord
            enable_email: Activer Email
            email_config: Configuration Email
            enable_webhook: Activer Webhook
            webhook_url: URL Webhook
        """
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.config = config or {}
        self.queue_size = queue_size
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.workers = workers
        
        # Canaux
        self.channels: Dict[NotificationChannel, Any] = {}
        
        # Telegram
        if enable_telegram and telegram_token and telegram_chat_id:
            self._setup_telegram(telegram_token, telegram_chat_id)
        
        # Slack
        if enable_slack and slack_webhook:
            self._setup_slack(slack_webhook)
        
        # Discord
        if enable_discord and discord_webhook:
            self._setup_discord(discord_webhook)
        
        # Email
        if enable_email and email_config:
            self._setup_email(email_config)
        
        # Webhook
        if enable_webhook and webhook_url:
            self._setup_webhook(webhook_url)
        
        # File d'attente
        self.queue = queue.Queue(maxsize=queue_size)
        
        # Workers
        self._workers = []
        self._running = False
        
        # Templates
        self.templates: Dict[str, NotificationTemplate] = {}
        self._load_default_templates()
        
        # Statistiques
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'by_channel': {},
            'by_type': {},
            'errors': 0,
        }
        
        self._initialized = True
        
        # Démarrer
        self.start()
        
        logger.info("Notifier initialized")
    
    def _setup_telegram(self, token: str, chat_id: str):
        """Configure Telegram"""
        try:
            bot = telegram.Bot(token=token)
            self.channels[NotificationChannel.TELEGRAM] = {
                'bot': bot,
                'chat_id': chat_id,
            }
            logger.info("Telegram configured")
        except Exception as e:
            logger.error(f"Telegram setup error: {e}")
    
    def _setup_slack(self, webhook: str):
        """Configure Slack"""
        try:
            client = slack_sdk.WebhookClient(webhook)
            self.channels[NotificationChannel.SLACK] = {
                'client': client,
            }
            logger.info("Slack configured")
        except Exception as e:
            logger.error(f"Slack setup error: {e}")
    
    def _setup_discord(self, webhook: str):
        """Configure Discord"""
        try:
            webhook = discord_webhook.DiscordWebhook(url=webhook)
            self.channels[NotificationChannel.DISCORD] = {
                'webhook': webhook,
            }
            logger.info("Discord configured")
        except Exception as e:
            logger.error(f"Discord setup error: {e}")
    
    def _setup_email(self, config: Dict[str, Any]):
        """Configure Email"""
        try:
            self.channels[NotificationChannel.EMAIL] = {
                'smtp_host': config.get('smtp_host', 'smtp.gmail.com'),
                'smtp_port': config.get('smtp_port', 587),
                'smtp_user': config.get('smtp_user'),
                'smtp_password': config.get('smtp_password'),
                'from_email': config.get('from_email'),
                'to_emails': config.get('to_emails', []),
            }
            logger.info("Email configured")
        except Exception as e:
            logger.error(f"Email setup error: {e}")
    
    def _setup_webhook(self, url: str):
        """Configure Webhook"""
        try:
            self.channels[NotificationChannel.WEBHOOK] = {
                'url': url,
                'headers': self.config.get('webhook_headers', {}),
            }
            logger.info("Webhook configured")
        except Exception as e:
            logger.error(f"Webhook setup error: {e}")
    
    def _load_default_templates(self):
        """Charge les templates par défaut"""
        templates = {
            'trade': NotificationTemplate(
                name='trade',
                type=NotificationType.TRADE,
                channel=NotificationChannel.TELEGRAM,
                template="""📊 *Trade Executed*
                
*Symbol:* {symbol}
*Side:* {side}
*Quantity:* {quantity}
*Price:* {price}
*PNL:* {pnl}
*Strategy:* {strategy}
*Time:* {time}""",
                subject_template="Trade Executed: {symbol}"
            ),
            'opportunity': NotificationTemplate(
                name='opportunity',
                type=NotificationType.OPPORTUNITY,
                channel=NotificationChannel.TELEGRAM,
                template="""🎯 *Arbitrage Opportunity*
                
*Symbol:* {symbol}
*Spread:* {spread}
*Profit:* {profit}
*Exchange A:* {exchange_a}
*Exchange B:* {exchange_b}
*Time:* {time}""",
                subject_template="Arbitrage Opportunity: {symbol}"
            ),
            'risk': NotificationTemplate(
                name='risk',
                type=NotificationType.RISK,
                channel=NotificationChannel.TELEGRAM,
                template="""⚠️ *Risk Alert*
                
*Type:* {risk_type}
*Level:* {level}
*Message:* {message}
*Time:* {time}""",
                subject_template="Risk Alert: {risk_type}"
            ),
            'system': NotificationTemplate(
                name='system',
                type=NotificationType.SYSTEM,
                channel=NotificationChannel.TELEGRAM,
                template="""🖥️ *System Notification*
                
*Event:* {event}
*Status:* {status}
*Message:* {message}
*Time:* {time}""",
                subject_template="System: {event}"
            ),
            'report': NotificationTemplate(
                name='report',
                type=NotificationType.REPORT,
                channel=NotificationChannel.EMAIL,
                template="""📊 *Performance Report*
                
*Period:* {period}
*Total Trades:* {total_trades}
*Win Rate:* {win_rate}
*Total PNL:* {total_pnl}
*Best Trade:* {best_trade}
*Worst Trade:* {worst_trade}
*Sharpe Ratio:* {sharpe_ratio}
*Max Drawdown:* {max_drawdown}""",
                subject_template="Performance Report: {period}"
            ),
        }
        
        for template in templates.values():
            self.templates[template.name] = template
    
    # ============================================================
    # WORKER MANAGEMENT
    # ============================================================
    
    def start(self):
        """Démarre les workers"""
        if self._running:
            return
        
        self._running = True
        
        for i in range(self.workers):
            worker = threading.Thread(target=self._worker_loop, daemon=True)
            worker.start()
            self._workers.append(worker)
        
        logger.info(f"Notifier workers started: {self.workers}")
    
    def stop(self):
        """Arrête les workers"""
        if not self._running:
            return
        
        self._running = False
        
        # Attendre la fin des workers
        for worker in self._workers:
            worker.join(timeout=2)
        
        self._workers.clear()
        logger.info("Notifier workers stopped")
    
    def _worker_loop(self):
        """Boucle du worker"""
        while self._running:
            try:
                notification = self.queue.get(timeout=1)
                self._process_notification(notification)
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")
    
    # ============================================================
    # NOTIFICATION PROCESSING
    # ============================================================
    
    def _process_notification(self, notification: Notification):
        """
        Traite une notification
        
        Args:
            notification: Notification à traiter
        """
        for attempt in range(self.retry_attempts):
            try:
                if notification.channel == NotificationChannel.TELEGRAM:
                    self._send_telegram(notification)
                elif notification.channel == NotificationChannel.SLACK:
                    self._send_slack(notification)
                elif notification.channel == NotificationChannel.DISCORD:
                    self._send_discord(notification)
                elif notification.channel == NotificationChannel.EMAIL:
                    self._send_email(notification)
                elif notification.channel == NotificationChannel.WEBHOOK:
                    self._send_webhook(notification)
                elif notification.channel == NotificationChannel.CONSOLE:
                    self._send_console(notification)
                else:
                    logger.warning(f"Unsupported channel: {notification.channel}")
                    return
                
                notification.status = "sent"
                self.stats['success'] += 1
                self._update_stats(notification)
                return
                
            except Exception as e:
                logger.error(f"Notification error (attempt {attempt+1}): {e}")
                
                if attempt < self.retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    notification.status = "failed"
                    self.stats['failed'] += 1
                    self.stats['errors'] += 1
    
    def _update_stats(self, notification: Notification):
        """Met à jour les statistiques"""
        self.stats['total'] += 1
        
        channel_key = notification.channel.value
        if channel_key not in self.stats['by_channel']:
            self.stats['by_channel'][channel_key] = 0
        self.stats['by_channel'][channel_key] += 1
        
        type_key = notification.type.value
        if type_key not in self.stats['by_type']:
            self.stats['by_type'][type_key] = 0
        self.stats['by_type'][type_key] += 1
    
    # ============================================================
    # SEND METHODS
    # ============================================================
    
    def _send_telegram(self, notification: Notification):
        """Envoie une notification Telegram"""
        channel = self.channels.get(NotificationChannel.TELEGRAM)
        if not channel:
            raise Exception("Telegram not configured")
        
        bot = channel['bot']
        chat_id = channel['chat_id']
        
        # Formater le message
        message = self._format_message(notification)
        
        # Envoyer
        bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode='HTML'
        )
    
    def _send_slack(self, notification: Notification):
        """Envoie une notification Slack"""
        channel = self.channels.get(NotificationChannel.SLACK)
        if not channel:
            raise Exception("Slack not configured")
        
        client = channel['client']
        
        # Formater le message
        message = self._format_message(notification)
        
        # Envoyer
        client.send(text=message)
    
    def _send_discord(self, notification: Notification):
        """Envoie une notification Discord"""
        channel = self.channels.get(NotificationChannel.DISCORD)
        if not channel:
            raise Exception("Discord not configured")
        
        webhook = channel['webhook']
        
        # Formater le message
        message = self._format_message(notification)
        
        # Envoyer
        webhook.content = message
        webhook.execute()
    
    def _send_email(self, notification: Notification):
        """Envoie une notification Email"""
        channel = self.channels.get(NotificationChannel.EMAIL)
        if not channel:
            raise Exception("Email not configured")
        
        # Créer le message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = notification.title
        msg['From'] = channel['from_email']
        msg['To'] = ', '.join(channel['to_emails'])
        
        # Corps du message
        text = self._format_message(notification)
        part = MIMEText(text, 'plain')
        msg.attach(part)
        
        # Envoyer
        with smtplib.SMTP(channel['smtp_host'], channel['smtp_port']) as server:
            server.starttls()
            server.login(channel['smtp_user'], channel['smtp_password'])
            server.send_message(msg)
    
    def _send_webhook(self, notification: Notification):
        """Envoie une notification Webhook"""
        channel = self.channels.get(NotificationChannel.WEBHOOK)
        if not channel:
            raise Exception("Webhook not configured")
        
        # Préparer les données
        data = {
            'type': notification.type.value,
            'title': notification.title,
            'message': notification.message,
            'priority': notification.priority.value,
            'timestamp': notification.timestamp,
            'data': notification.data,
        }
        
        # Envoyer
        response = requests.post(
            channel['url'],
            json=data,
            headers=channel['headers'],
            timeout=10
        )
        response.raise_for_status()
    
    def _send_console(self, notification: Notification):
        """Envoie une notification Console"""
        message = self._format_message(notification)
        print(f"[{notification.type.value.upper()}] {notification.title}")
        print(message)
        print("-" * 40)
    
    # ============================================================
    # MESSAGE FORMATTING
    # ============================================================
    
    def _format_message(self, notification: Notification) -> str:
        """
        Formate un message
        
        Args:
            notification: Notification
            
        Returns:
            str: Message formaté
        """
        # Utiliser un template si disponible
        template = self.templates.get(notification.type.value)
        
        if template:
            try:
                return template.template.format(
                    **notification.data,
                    title=notification.title,
                    message=notification.message,
                    time=datetime.fromtimestamp(notification.timestamp).isoformat()
                )
            except KeyError:
                pass
        
        # Message par défaut
        return f"{notification.title}\n\n{notification.message}"
    
    # ============================================================
    # NOTIFICATION METHODS
    # ============================================================
    
    def send(
        self,
        type: NotificationType,
        title: str,
        message: str,
        channel: Optional[NotificationChannel] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        data: Optional[Dict[str, Any]] = None,
        recipient: Optional[str] = None
    ):
        """
        Envoie une notification
        
        Args:
            type: Type de notification
            title: Titre
            message: Message
            channel: Canal de notification
            priority: Priorité
            data: Données supplémentaires
            recipient: Destinataire
        """
        # Déterminer le canal
        if channel is None:
            # Utiliser le canal par défaut en fonction du type
            if type in [NotificationType.CRITICAL, NotificationType.ERROR]:
                channel = NotificationChannel.TELEGRAM
            elif type == NotificationType.REPORT:
                channel = NotificationChannel.EMAIL
            else:
                channel = NotificationChannel.CONSOLE
        
        # Créer la notification
        notification = Notification(
            type=type,
            channel=channel,
            title=title,
            message=message,
            priority=priority,
            data=data or {},
            recipient=recipient,
        )
        
        # Ajouter à la file d'attente
        try:
            self.queue.put_nowait(notification)
        except queue.Full:
            logger.warning(f"Notification queue full, dropping: {title}")
    
    def info(self, title: str, message: str, **kwargs):
        """Envoie une notification d'information"""
        self.send(NotificationType.INFO, title, message, **kwargs)
    
    def success(self, title: str, message: str, **kwargs):
        """Envoie une notification de succès"""
        self.send(NotificationType.SUCCESS, title, message, **kwargs)
    
    def warning(self, title: str, message: str, **kwargs):
        """Envoie une notification d'avertissement"""
        self.send(NotificationType.WARNING, title, message, **kwargs)
    
    def error(self, title: str, message: str, **kwargs):
        """Envoie une notification d'erreur"""
        self.send(NotificationType.ERROR, title, message, **kwargs)
    
    def critical(self, title: str, message: str, **kwargs):
        """Envoie une notification critique"""
        self.send(
            NotificationType.CRITICAL,
            title,
            message,
            priority=NotificationPriority.CRITICAL,
            **kwargs
        )
    
    def trade(self, title: str, message: str, data: Dict[str, Any]):
        """Envoie une notification de trade"""
        self.send(
            NotificationType.TRADE,
            title,
            message,
            data=data,
            channel=NotificationChannel.TELEGRAM
        )
    
    def opportunity(self, title: str, message: str, data: Dict[str, Any]):
        """Envoie une notification d'opportunité"""
        self.send(
            NotificationType.OPPORTUNITY,
            title,
            message,
            data=data,
            channel=NotificationChannel.TELEGRAM
        )
    
    def risk(self, title: str, message: str, data: Dict[str, Any]):
        """Envoie une notification de risque"""
        self.send(
            NotificationType.RISK,
            title,
            message,
            data=data,
            channel=NotificationChannel.TELEGRAM
        )
    
    def system(self, title: str, message: str, data: Dict[str, Any]):
        """Envoie une notification système"""
        self.send(
            NotificationType.SYSTEM,
            title,
            message,
            data=data,
            channel=NotificationChannel.CONSOLE
        )
    
    def report(self, title: str, message: str, data: Dict[str, Any]):
        """Envoie une notification de rapport"""
        self.send(
            NotificationType.REPORT,
            title,
            message,
            data=data,
            channel=NotificationChannel.EMAIL
        )
    
    # ============================================================
    # TEMPLATE MANAGEMENT
    # ============================================================
    
    def add_template(self, template: NotificationTemplate):
        """
        Ajoute un template
        
        Args:
            template: Template à ajouter
        """
        self.templates[template.name] = template
    
    def remove_template(self, name: str):
        """
        Supprime un template
        
        Args:
            name: Nom du template
        """
        if name in self.templates:
            del self.templates[name]
    
    def get_template(self, name: str) -> Optional[NotificationTemplate]:
        """
        Récupère un template
        
        Args:
            name: Nom du template
            
        Returns:
            Optional[NotificationTemplate]: Template
        """
        return self.templates.get(name)
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques
        
        Returns:
            Dict[str, Any]: Statistiques
        """
        return {
            **self.stats,
            'queue_size': self.queue.qsize(),
            'workers': len(self._workers),
            'channels': list(self.channels.keys()),
            'templates': len(self.templates),
        }

# ============================================================
# GLOBAL NOTIFIER INSTANCE
# ============================================================

_notifier: Optional[ArbitrageBotNotifier] = None

def get_notifier(
    **kwargs
) -> ArbitrageBotNotifier:
    """
    Récupère le système de notifications global
    
    Args:
        **kwargs: Arguments supplémentaires
        
    Returns:
        ArbitrageBotNotifier: Système de notifications
    """
    global _notifier
    if _notifier is None:
        _notifier = ArbitrageBotNotifier(**kwargs)
    return _notifier

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'NotificationType',
    'NotificationChannel',
    'NotificationPriority',
    'Notification',
    'NotificationTemplate',
    'ArbitrageBotNotifier',
    'get_notifier',
]

# ============================================================
# INITIALIZATION
# ============================================================

# Créer l'instance par défaut
notifier = get_notifier()

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    # Test du notifier
    notifier = get_notifier()
    
    print("Sending test notifications...")
    
    # Tester différents types
    notifier.info("Test Info", "This is an info notification")
    notifier.success("Test Success", "This is a success notification")
    notifier.warning("Test Warning", "This is a warning notification")
    notifier.error("Test Error", "This is an error notification")
    
    # Tester avec des données
    notifier.trade(
        "Trade Executed",
        "BTC/USDT BUY 0.5 @ 45000",
        data={
            'symbol': 'BTC/USDT',
            'side': 'BUY',
            'quantity': 0.5,
            'price': 45000,
            'pnl': 500,
        }
    )
    
    # Attendre l'envoi
    time.sleep(2)
    
    print("\nStatistics:")
    print(json.dumps(notifier.get_stats(), indent=2))
    
    notifier.stop()
