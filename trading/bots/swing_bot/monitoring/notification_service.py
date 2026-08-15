"""
Swing Bot Notification Service
================================

This module provides notification capabilities for the Swing Bot trading system.
"""

import json
import smtplib
import logging
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pathlib import Path
import asyncio
import aiohttp


class NotificationService:
    """
    Service for sending notifications through various channels.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the notification service.
        
        Args:
            config: Configuration settings
        """
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)
        self.channels = self.config.get('channels', ['email', 'telegram', 'slack'])
        self.default_priority = self.config.get('default_priority', 'normal')
        
        # Initialize channel handlers
        self.handlers = {}
        self._initialize_handlers()
    
    def _initialize_handlers(self) -> None:
        """Initialize notification channel handlers."""
        if 'email' in self.channels:
            self.handlers['email'] = EmailHandler(self.config.get('email', {}))
        
        if 'telegram' in self.channels:
            self.handlers['telegram'] = TelegramHandler(self.config.get('telegram', {}))
        
        if 'slack' in self.channels:
            self.handlers['slack'] = SlackHandler(self.config.get('slack', {}))
        
        if 'sms' in self.channels:
            self.handlers['sms'] = SMSHandler(self.config.get('sms', {}))
        
        if 'webhook' in self.channels:
            self.handlers['webhook'] = WebhookHandler(self.config.get('webhook', {}))
    
    def send_notification(
        self,
        message: str,
        title: Optional[str] = None,
        priority: str = 'normal',
        channel: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, bool]:
        """
        Send a notification.
        
        Args:
            message: Notification message
            title: Notification title
            priority: Priority level ('low', 'normal', 'high', 'critical')
            channel: Specific channel to use (default: all)
            data: Additional data
        
        Returns:
            Dictionary of channel results
        """
        if not self.enabled:
            return {'status': 'disabled'}
        
        results = {}
        channels = [channel] if channel else self.channels
        
        for ch in channels:
            handler = self.handlers.get(ch)
            if handler:
                try:
                    results[ch] = handler.send(message, title, priority, data)
                except Exception as e:
                    logging.error(f"Notification error on {ch}: {e}")
                    results[ch] = False
            else:
                results[ch] = False
        
        return results
    
    def send_alert(
        self,
        alert_type: str,
        message: str,
        severity: str = 'warning',
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, bool]:
        """
        Send an alert notification.
        
        Args:
            alert_type: Type of alert
            message: Alert message
            severity: Severity level ('info', 'warning', 'error', 'critical')
            data: Additional data
        
        Returns:
            Dictionary of channel results
        """
        priority_map = {
            'info': 'low',
            'warning': 'normal',
            'error': 'high',
            'critical': 'critical'
        }
        
        title = f"{alert_type.upper()} Alert"
        priority = priority_map.get(severity, 'normal')
        
        return self.send_notification(message, title, priority, data=data)
    
    async def send_notification_async(
        self,
        message: str,
        title: Optional[str] = None,
        priority: str = 'normal',
        channel: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, bool]:
        """
        Send a notification asynchronously.
        
        Args:
            message: Notification message
            title: Notification title
            priority: Priority level
            channel: Specific channel to use
            data: Additional data
        
        Returns:
            Dictionary of channel results
        """
        if not self.enabled:
            return {'status': 'disabled'}
        
        results = {}
        channels = [channel] if channel else self.channels
        
        for ch in channels:
            handler = self.handlers.get(ch)
            if handler and hasattr(handler, 'send_async'):
                try:
                    results[ch] = await handler.send_async(message, title, priority, data)
                except Exception as e:
                    logging.error(f"Async notification error on {ch}: {e}")
                    results[ch] = False
            elif handler:
                # Fallback to sync method
                try:
                    results[ch] = handler.send(message, title, priority, data)
                except Exception as e:
                    logging.error(f"Notification error on {ch}: {e}")
                    results[ch] = False
            else:
                results[ch] = False
        
        return results


class EmailHandler:
    """Email notification handler."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.smtp_host = config.get('smtp_host', 'smtp.gmail.com')
        self.smtp_port = config.get('smtp_port', 587)
        self.smtp_user = config.get('smtp_user', '')
        self.smtp_password = config.get('smtp_password', '')
        self.from_email = config.get('from_email', self.smtp_user)
        self.to_emails = config.get('to_emails', [])
        self.use_tls = config.get('use_tls', True)
    
    def send(
        self,
        message: str,
        title: Optional[str] = None,
        priority: str = 'normal',
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send an email notification.
        
        Args:
            message: Email body
            title: Email subject
            priority: Priority level
            data: Additional data
        
        Returns:
            True if successful, False otherwise
        """
        if not self.to_emails:
            logging.warning("No email recipients configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ', '.join(self.to_emails)
            msg['Subject'] = title or 'NEXUS Trading Notification'
            
            # Add priority header
            priority_headers = {
                'low': '5',
                'normal': '3',
                'high': '1',
                'critical': '1'
            }
            msg['X-Priority'] = priority_headers.get(priority, '3')
            
            # Add body
            body = self._format_message(message, priority, data)
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logging.info(f"Email notification sent to {len(self.to_emails)} recipients")
            return True
            
        except Exception as e:
            logging.error(f"Email send error: {e}")
            return False
    
    def _format_message(
        self,
        message: str,
        priority: str,
        data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format the email message."""
        lines = [
            f"Priority: {priority.upper()}",
            f"Timestamp: {datetime.now().isoformat()}",
            "",
            message
        ]
        
        if data:
            lines.extend([
                "",
                "Additional Data:",
                json.dumps(data, indent=2)
            ])
        
        return "\n".join(lines)


class TelegramHandler:
    """Telegram notification handler."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.bot_token = config.get('bot_token', '')
        self.chat_ids = config.get('chat_ids', [])
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
    
    def send(
        self,
        message: str,
        title: Optional[str] = None,
        priority: str = 'normal',
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a Telegram notification.
        
        Args:
            message: Message content
            title: Message title
            priority: Priority level
            data: Additional data
        
        Returns:
            True if successful, False otherwise
        """
        if not self.bot_token or not self.chat_ids:
            logging.warning("Telegram not configured")
            return False
        
        formatted_message = self._format_message(message, title, priority, data)
        
        success = True
        for chat_id in self.chat_ids:
            try:
                response = requests.post(
                    self.api_url,
                    json={
                        'chat_id': chat_id,
                        'text': formatted_message,
                        'parse_mode': 'HTML'
                    },
                    timeout=10
                )
                
                if response.status_code != 200:
                    logging.error(f"Telegram error: {response.text}")
                    success = False
                    
            except Exception as e:
                logging.error(f"Telegram send error: {e}")
                success = False
        
        return success
    
    def _format_message(
        self,
        message: str,
        title: Optional[str],
        priority: str,
        data: Optional[Dict[str, Any]]
    ) -> str:
        """Format the Telegram message."""
        lines = []
        
        if title:
            lines.append(f"<b>{title}</b>")
        
        priority_icons = {
            'low': 'ℹ️',
            'normal': '📢',
            'high': '⚠️',
            'critical': '🚨'
        }
        icon = priority_icons.get(priority, '📢')
        lines.append(f"{icon} Priority: {priority.upper()}")
        lines.append(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append(message)
        
        if data:
            lines.append("")
            lines.append("<b>Additional Data:</b>")
            lines.append(f"<pre>{json.dumps(data, indent=2)}</pre>")
        
        return "\n".join(lines)
    
    async def send_async(
        self,
        message: str,
        title: Optional[str] = None,
        priority: str = 'normal',
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send Telegram notification asynchronously."""
        if not self.bot_token or not self.chat_ids:
            logging.warning("Telegram not configured")
            return False
        
        formatted_message = self._format_message(message, title, priority, data)
        
        success = True
        async with aiohttp.ClientSession() as session:
            for chat_id in self.chat_ids:
                try:
                    async with session.post(
                        self.api_url,
                        json={
                            'chat_id': chat_id,
                            'text': formatted_message,
                            'parse_mode': 'HTML'
                        },
                        timeout=10
                    ) as response:
                        if response.status != 200:
                            logging.error(f"Telegram error: {await response.text()}")
                            success = False
                except Exception as e:
                    logging.error(f"Telegram send error: {e}")
                    success = False
        
        return success


class SlackHandler:
    """Slack notification handler."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.webhook_url = config.get('webhook_url', '')
        self.channel = config.get('channel', '')
        self.username = config.get('username', 'NEXUS Trading Bot')
    
    def send(
        self,
        message: str,
        title: Optional[str] = None,
        priority: str = 'normal',
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a Slack notification.
        
        Args:
            message: Message content
            title: Message title
            priority: Priority level
            data: Additional data
        
        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url:
            logging.warning("Slack webhook not configured")
            return False
        
        try:
            payload = self._format_payload(message, title, priority, data)
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            
            if response.status_code != 200:
                logging.error(f"Slack error: {response.text}")
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Slack send error: {e}")
            return False
    
    def _format_payload(
        self,
        message: str,
        title: Optional[str],
        priority: str,
        data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Format the Slack payload."""
        color_map = {
            'low': '#808080',
            'normal': '#3498db',
            'high': '#f1c40f',
            'critical': '#e74c3c'
        }
        
        payload = {
            'channel': self.channel if self.channel else None,
            'username': self.username,
            'attachments': [{
                'color': color_map.get(priority, '#3498db'),
                'title': title or 'NEXUS Trading Notification',
                'text': message,
                'fields': [
                    {
                        'title': 'Priority',
                        'value': priority.upper(),
                        'short': True
                    },
                    {
                        'title': 'Timestamp',
                        'value': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'short': True
                    }
                ],
                'footer': 'NEXUS Trading Bot',
                'ts': int(datetime.now().timestamp())
            }]
        }
        
        if data:
            payload['attachments'][0]['fields'].append({
                'title': 'Additional Data',
                'value': f"```{json.dumps(data, indent=2)}```",
                'short': False
            })
        
        return payload


class SMSHandler:
    """SMS notification handler."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider = config.get('provider', 'twilio')
        self.phone_numbers = config.get('phone_numbers', [])
        
        if self.provider == 'twilio':
            self.account_sid = config.get('account_sid', '')
            self.auth_token = config.get('auth_token', '')
            self.from_number = config.get('from_number', '')
    
    def send(
        self,
        message: str,
        title: Optional[str] = None,
        priority: str = 'normal',
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send an SMS notification.
        
        Args:
            message: Message content
            title: Message title
            priority: Priority level
            data: Additional data
        
        Returns:
            True if successful, False otherwise
        """
        if not self.phone_numbers:
            logging.warning("No phone numbers configured")
            return False
        
        formatted_message = self._format_message(message, title, priority)
        
        success = True
        for phone_number in self.phone_numbers:
            try:
                if self.provider == 'twilio':
                    success &= self._send_twilio(formatted_message, phone_number)
                else:
                    logging.warning(f"Unsupported SMS provider: {self.provider}")
                    success = False
            except Exception as e:
                logging.error(f"SMS send error: {e}")
                success = False
        
        return success
    
    def _send_twilio(self, message: str, to_number: str) -> bool:
        """Send SMS via Twilio."""
        try:
            from twilio.rest import Client
            
            client = Client(self.account_sid, self.auth_token)
            client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            return True
        except ImportError:
            logging.error("Twilio library not installed")
            return False
        except Exception as e:
            logging.error(f"Twilio send error: {e}")
            return False
    
    def _format_message(self, message: str, title: Optional[str], priority: str) -> str:
        """Format the SMS message."""
        parts = []
        if title:
            parts.append(f"[{title}]")
        parts.append(f"{priority.upper()} - {message}")
        return " ".join(parts)


class WebhookHandler:
    """Webhook notification handler."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.webhook_url = config.get('webhook_url', '')
        self.method = config.get('method', 'POST')
        self.headers = config.get('headers', {})
    
    def send(
        self,
        message: str,
        title: Optional[str] = None,
        priority: str = 'normal',
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a webhook notification.
        
        Args:
            message: Message content
            title: Message title
            priority: Priority level
            data: Additional data
        
        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url:
            logging.warning("Webhook URL not configured")
            return False
        
        try:
            payload = {
                'message': message,
                'title': title,
                'priority': priority,
                'timestamp': datetime.now().isoformat(),
                'data': data or {}
            }
            
            response = requests.request(
                method=self.method,
                url=self.webhook_url,
                headers=self.headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code not in [200, 201, 202, 204]:
                logging.error(f"Webhook error: {response.status_code}")
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Webhook send error: {e}")
            return False
    
    async def send_async(
        self,
        message: str,
        title: Optional[str] = None,
        priority: str = 'normal',
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send webhook notification asynchronously."""
        if not self.webhook_url:
            logging.warning("Webhook URL not configured")
            return False
        
        try:
            payload = {
                'message': message,
                'title': title,
                'priority': priority,
                'timestamp': datetime.now().isoformat(),
                'data': data or {}
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=self.method,
                    url=self.webhook_url,
                    headers=self.headers,
                    json=payload,
                    timeout=10
                ) as response:
                    if response.status not in [200, 201, 202, 204]:
                        logging.error(f"Webhook error: {response.status}")
                        return False
                    return True
            
        except Exception as e:
            logging.error(f"Webhook send error: {e}")
            return False


# Global notification service instance
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get the global notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


def send_notification(
    message: str,
    title: Optional[str] = None,
    priority: str = 'normal',
    channel: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, bool]:
    """
    Send a notification using the global service.
    
    Args:
        message: Notification message
        title: Notification title
        priority: Priority level
        channel: Specific channel to use
        data: Additional data
    
    Returns:
        Dictionary of channel results
    """
    return get_notification_service().send_notification(message, title, priority, channel, data)


async def send_notification_async(
    message: str,
    title: Optional[str] = None,
    priority: str = 'normal',
    channel: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, bool]:
    """
    Send a notification asynchronously using the global service.
    
    Args:
        message: Notification message
        title: Notification title
        priority: Priority level
        channel: Specific channel to use
        data: Additional data
    
    Returns:
        Dictionary of channel results
    """
    return await get_notification_service().send_notification_async(message, title, priority, channel, data)


def send_alert(
    alert_type: str,
    message: str,
    severity: str = 'warning',
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, bool]:
    """
    Send an alert using the global service.
    
    Args:
        alert_type: Type of alert
        message: Alert message
        severity: Severity level
        data: Additional data
    
    Returns:
        Dictionary of channel results
    """
    return get_notification_service().send_alert(alert_type, message, severity, data)


__all__ = [
    'NotificationService',
    'EmailHandler',
    'TelegramHandler',
    'SlackHandler',
    'SMSHandler',
    'WebhookHandler',
    'get_notification_service',
    'send_notification',
    'send_notification_async',
    'send_alert'
]
