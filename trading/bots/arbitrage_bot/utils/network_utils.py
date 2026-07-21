"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Network Utilities
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Utilitaires réseau pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import socket
import ipaddress
import json
import aiohttp
import requests
import urllib.parse
import time
import hashlib
import ssl
import certifi
import dns.resolver
import netifaces
import ping3
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    Tuple,
    Callable,
    TypeVar,
    Generic,
    AsyncIterator,
    Iterator,
    BinaryIO,
    TextIO
)
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import os
import re
import threading
import queue
import subprocess
from contextlib import contextmanager, asynccontextmanager
import zlib
import base64

# ============================================================
# LOGGING
# ============================================================
import logging
logger = logging.getLogger(__name__)

# ============================================================
# TYPE VARIABLES
# ============================================================
T = TypeVar('T')
R = TypeVar('R')

# ============================================================
# CONSTANTS
# ============================================================

DEFAULT_TIMEOUT = 30
DEFAULT_USER_AGENT = "NEXUS-Arbitrage-Bot/2.0.0"
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 1.0
DEFAULT_CHUNK_SIZE = 8192

# ============================================================
# ENUMS
# ============================================================

class HTTPMethod(Enum):
    """Méthodes HTTP"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"

class NetworkProtocol(Enum):
    """Protocoles réseau"""
    TCP = "TCP"
    UDP = "UDP"
    HTTP = "HTTP"
    HTTPS = "HTTPS"
    WS = "WS"
    WSS = "WSS"

# ============================================================
# HTTP CLIENT
# ============================================================

class HTTPClient:
    """Client HTTP avec fonctionnalités avancées"""
    
    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        user_agent: str = DEFAULT_USER_AGENT,
        proxy: Optional[str] = None,
        verify_ssl: bool = True,
        headers: Optional[Dict[str, str]] = None,
        session: Optional[aiohttp.ClientSession] = None
    ):
        """
        Initialise le client HTTP
        
        Args:
            timeout: Timeout en secondes
            max_retries: Nombre maximum de tentatives
            user_agent: User-Agent
            proxy: Proxy URL
            verify_ssl: Vérifier SSL
            headers: En-têtes additionnels
            session: Session aiohttp existante
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        self.proxy = proxy
        self.verify_ssl = verify_ssl
        self.headers = headers or {}
        self._session = session
        self._owns_session = session is None
        self._stats = {
            'requests': 0,
            'successes': 0,
            'failures': 0,
            'retries': 0,
            'total_time': 0,
            'avg_time': 0,
        }
        self._lock = threading.Lock()
        
        logger.info(f"HTTPClient initialized (timeout={timeout}s, max_retries={max_retries})")
    
    @property
    def session(self) -> aiohttp.ClientSession:
        """Récupère la session aiohttp"""
        if self._session is None:
            connector = aiohttp.TCPConnector(
                ssl=ssl.create_default_context(cafile=certifi.where()) if self.verify_ssl else False
            )
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session
    
    async def request(
        self,
        method: Union[str, HTTPMethod],
        url: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        retries: Optional[int] = None,
        stream: bool = False
    ) -> aiohttp.ClientResponse:
        """
        Effectue une requête HTTP
        
        Args:
            method: Méthode HTTP
            url: URL
            params: Paramètres de requête
            data: Données à envoyer
            json_data: Données JSON à envoyer
            headers: En-têtes additionnels
            timeout: Timeout spécifique
            retries: Nombre de tentatives spécifique
            stream: Mode streaming
            
        Returns:
            aiohttp.ClientResponse: Réponse
        """
        if isinstance(method, HTTPMethod):
            method = method.value
        
        headers = headers or {}
        headers.update(self.headers)
        headers.setdefault('User-Agent', self.user_agent)
        
        if json_data is not None:
            headers.setdefault('Content-Type', 'application/json')
        
        timeout = timeout or self.timeout
        retries = retries or self.max_retries
        
        start_time = time.perf_counter()
        
        for attempt in range(retries):
            try:
                async with self.session as session:
                    async with session.request(
                        method=method,
                        url=url,
                        params=params,
                        data=data,
                        json=json_data,
                        headers=headers,
                        proxy=self.proxy,
                        timeout=aiohttp.ClientTimeout(total=timeout),
                        ssl=ssl.create_default_context(cafile=certifi.where()) if self.verify_ssl else False
                    ) as response:
                        elapsed = time.perf_counter() - start_time
                        
                        with self._lock:
                            self._stats['requests'] += 1
                            self._stats['successes'] += 1
                            self._stats['total_time'] += elapsed
                            self._stats['avg_time'] = self._stats['total_time'] / self._stats['successes']
                        
                        logger.debug(f"{method} {url} - Status: {response.status} - Time: {elapsed:.3f}s")
                        
                        if stream:
                            return response
                        
                        await response.read()
                        return response
            
            except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
                elapsed = time.perf_counter() - start_time
                
                if attempt < retries - 1:
                    wait_time = DEFAULT_BACKOFF_FACTOR * (2 ** attempt)
                    logger.warning(f"Request failed (attempt {attempt + 1}/{retries}): {e}. Retrying in {wait_time:.2f}s")
                    with self._lock:
                        self._stats['retries'] += 1
                    await asyncio.sleep(wait_time)
                else:
                    with self._lock:
                        self._stats['requests'] += 1
                        self._stats['failures'] += 1
                    
                    logger.error(f"Request failed after {retries} attempts: {e}")
                    raise
    
    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """Requête GET"""
        return await self.request(HTTPMethod.GET, url, params=params, headers=headers, **kwargs)
    
    async def post(
        self,
        url: str,
        data: Optional[Any] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """Requête POST"""
        return await self.request(
            HTTPMethod.POST, url,
            data=data, json_data=json_data, headers=headers, **kwargs
        )
    
    async def put(
        self,
        url: str,
        data: Optional[Any] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """Requête PUT"""
        return await self.request(
            HTTPMethod.PUT, url,
            data=data, json_data=json_data, headers=headers, **kwargs
        )
    
    async def delete(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """Requête DELETE"""
        return await self.request(HTTPMethod.DELETE, url, headers=headers, **kwargs)
    
    async def patch(
        self,
        url: str,
        data: Optional[Any] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """Requête PATCH"""
        return await self.request(
            HTTPMethod.PATCH, url,
            data=data, json_data=json_data, headers=headers, **kwargs
        )
    
    async def close(self):
        """Ferme le client"""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        with self._lock:
            return {
                **self._stats,
                'success_rate': self._stats['successes'] / self._stats['requests'] if self._stats['requests'] > 0 else 0,
                'failure_rate': self._stats['failures'] / self._stats['requests'] if self._stats['requests'] > 0 else 0,
            }
    
    def __repr__(self) -> str:
        return f"<HTTPClient requests={self._stats['requests']} successes={self._stats['successes']} failures={self._stats['failures']}>"

# ============================================================
# WEBSOCKET CLIENT
# ============================================================

class WebSocketClient:
    """Client WebSocket avec reconnexion automatique"""
    
    def __init__(
        self,
        url: str,
        reconnect_attempts: int = 5,
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 30.0,
        heartbeat_interval: float = 30.0,
        timeout: int = DEFAULT_TIMEOUT,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialise le client WebSocket
        
        Args:
            url: URL WebSocket
            reconnect_attempts: Nombre de tentatives de reconnexion
            reconnect_delay: Délai initial de reconnexion
            max_reconnect_delay: Délai maximum de reconnexion
            heartbeat_interval: Intervalle de heartbeat
            timeout: Timeout
            headers: En-têtes additionnels
        """
        self.url = url
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self.heartbeat_interval = heartbeat_interval
        self.timeout = timeout
        self.headers = headers or {}
        
        self._ws = None
        self._connected = False
        self._running = False
        self._reconnect_task = None
        self._heartbeat_task = None
        self._message_queue = asyncio.Queue()
        self._listeners = []
        self._stats = {
            'messages_received': 0,
            'messages_sent': 0,
            'reconnections': 0,
            'errors': 0,
        }
        self._lock = asyncio.Lock()
    
    async def connect(self):
        """Connecte le client WebSocket"""
        if self._connected:
            return
        
        self._running = True
        
        await self._do_connect()
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        logger.info(f"WebSocket connected to {self.url}")
    
    async def _do_connect(self):
        """Établit la connexion WebSocket"""
        try:
            self._ws = await aiohttp.ClientSession().ws_connect(
                self.url,
                headers=self.headers,
                timeout=self.timeout,
                heartbeat=self.heartbeat_interval,
                receive_timeout=self.timeout,
                max_msg_size=0,
                autoclose=True,
                autoheartbeat=True
            )
            self._connected = True
            self._stats['reconnections'] += 1
            
            asyncio.create_task(self._message_listener())
            
        except Exception as e:
            self._stats['errors'] += 1
            logger.error(f"WebSocket connection error: {e}")
            raise
    
    async def _reconnect_loop(self):
        """Boucle de reconnexion"""
        delay = self.reconnect_delay
        attempt = 0
        
        while self._running and attempt < self.reconnect_attempts:
            await asyncio.sleep(delay)
            
            if not self._connected:
                try:
                    await self._do_connect()
                    delay = self.reconnect_delay
                    attempt = 0
                    logger.info("WebSocket reconnected successfully")
                except Exception as e:
                    delay = min(delay * 2, self.max_reconnect_delay)
                    attempt += 1
                    logger.warning(f"Reconnection attempt {attempt} failed: {e}. Retrying in {delay}s")
    
    async def _heartbeat_loop(self):
        """Boucle de heartbeat"""
        while self._running and self._connected:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self.send("ping")
            except Exception as e:
                logger.warning(f"Heartbeat error: {e}")
                break
    
    async def _message_listener(self):
        """Écoute les messages WebSocket"""
        while self._connected and self._running:
            try:
                msg = await self._ws.receive()
                self._stats['messages_received'] += 1
                
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_message(msg.data)
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    await self._handle_message(msg.data, binary=True)
                elif msg.type == aiohttp.WSMsgType.PING:
                    await self._ws.pong()
                elif msg.type == aiohttp.WSMsgType.PONG:
                    pass
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    self._connected = False
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self._stats['errors'] += 1
                    logger.error(f"WebSocket error: {self._ws.exception()}")
                    break
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._stats['errors'] += 1
                logger.error(f"WebSocket listener error: {e}")
                self._connected = False
                break
    
    async def _handle_message(self, data: Union[str, bytes], binary: bool = False):
        """Traite un message reçu"""
        try:
            if not binary and isinstance(data, str):
                try:
                    parsed = json.loads(data)
                    message = {'type': 'json', 'data': parsed, 'raw': data}
                except json.JSONDecodeError:
                    message = {'type': 'text', 'data': data, 'raw': data}
            else:
                message = {'type': 'binary', 'data': data, 'raw': data}
            
            # Notifier les listeners
            for listener in self._listeners:
                try:
                    await listener(message)
                except Exception as e:
                    logger.error(f"Listener error: {e}")
        
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    async def send(self, data: Union[str, dict, bytes]) -> bool:
        """
        Envoie un message WebSocket
        
        Args:
            data: Données à envoyer
            
        Returns:
            bool: True si envoyé
        """
        if not self._connected:
            return False
        
        try:
            if isinstance(data, dict):
                data = json.dumps(data)
                await self._ws.send_str(data)
            elif isinstance(data, str):
                await self._ws.send_str(data)
            else:
                await self._ws.send_bytes(data)
            
            self._stats['messages_sent'] += 1
            return True
            
        except Exception as e:
            self._stats['errors'] += 1
            logger.error(f"Send error: {e}")
            return False
    
    async def send_json(self, data: dict) -> bool:
        """
        Envoie un message JSON
        
        Args:
            data: Données JSON à envoyer
            
        Returns:
            bool: True si envoyé
        """
        return await self.send(data)
    
    def add_listener(self, listener: Callable[[dict], Awaitable[None]]):
        """
        Ajoute un listener
        
        Args:
            listener: Fonction de callback
        """
        self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[dict], Awaitable[None]]):
        """
        Supprime un listener
        
        Args:
            listener: Fonction de callback
        """
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    async def close(self):
        """Ferme la connexion WebSocket"""
        self._running = False
        self._connected = False
        
        if self._reconnect_task:
            self._reconnect_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        
        if self._ws:
            await self._ws.close()
        
        logger.info("WebSocket closed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques"""
        return {
            **self._stats,
            'connected': self._connected,
            'running': self._running,
            'queue_size': self._message_queue.qsize(),
            'listeners': len(self._listeners),
        }

# ============================================================
# NETWORK UTILITIES
# ============================================================

class NetworkUtils:
    """Utilitaires réseau"""
    
    @staticmethod
    def get_local_ip() -> str:
        """
        Récupère l'adresse IP locale
        
        Returns:
            str: Adresse IP locale
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return '127.0.0.1'
    
    @staticmethod
    def get_public_ip() -> str:
        """
        Récupère l'adresse IP publique
        
        Returns:
            str: Adresse IP publique
        """
        try:
            response = requests.get('https://api.ipify.org', timeout=5)
            return response.text.strip()
        except Exception:
            try:
                response = requests.get('https://api.ipinfo.io/ip', timeout=5)
                return response.text.strip()
            except Exception:
                return 'unknown'
    
    @staticmethod
    def ping(host: str, count: int = 4) -> Dict[str, Any]:
        """
        Ping un hôte
        
        Args:
            host: Hôte à pinger
            count: Nombre de pings
            
        Returns:
            Dict[str, Any]: Résultats du ping
        """
        results = []
        successful = 0
        
        for _ in range(count):
            try:
                rtt = ping3.ping(host, timeout=2)
                if rtt is not None:
                    results.append(rtt)
                    successful += 1
            except Exception:
                pass
        
        if results:
            return {
                'success': True,
                'min': min(results),
                'max': max(results),
                'avg': sum(results) / len(results),
                'loss': (count - successful) / count * 100,
                'count': len(results),
            }
        else:
            return {
                'success': False,
                'loss': 100,
                'count': 0,
            }
    
    @staticmethod
    def dns_lookup(hostname: str) -> List[str]:
        """
        Résout un nom de domaine en adresse IP
        
        Args:
            hostname: Nom de domaine
            
        Returns:
            List[str]: Adresses IP
        """
        try:
            return [str(ip) for ip in socket.gethostbyname_ex(hostname)[2]]
        except Exception:
            return []
    
    @staticmethod
    def port_scan(host: str, ports: List[int], timeout: float = 1.0) -> Dict[int, bool]:
        """
        Scanne les ports d'un hôte
        
        Args:
            host: Hôte à scanner
            ports: Ports à scanner
            timeout: Timeout par port
            
        Returns:
            Dict[int, bool]: Résultats du scan
        """
        results = {}
        
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                result = sock.connect_ex((host, port))
                sock.close()
                results[port] = result == 0
            except Exception:
                results[port] = False
        
        return results
    
    @staticmethod
    def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
        """
        Vérifie si un port est ouvert
        
        Args:
            host: Hôte
            port: Port
            timeout: Timeout
            
        Returns:
            bool: True si le port est ouvert
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    @staticmethod
    def get_mac_address(interface: Optional[str] = None) -> str:
        """
        Récupère l'adresse MAC
        
        Args:
            interface: Interface réseau
            
        Returns:
            str: Adresse MAC
        """
        try:
            if interface:
                return netifaces.ifaddresses(interface)[netifaces.AF_LINK][0]['addr']
            else:
                for iface in netifaces.interfaces():
                    if iface != 'lo':
                        return netifaces.ifaddresses(iface)[netifaces.AF_LINK][0]['addr']
        except Exception:
            pass
        return '00:00:00:00:00:00'
    
    @staticmethod
    def get_network_interfaces() -> List[Dict[str, Any]]:
        """
        Récupère les interfaces réseau
        
        Returns:
            List[Dict[str, Any]]: Interfaces réseau
        """
        interfaces = []
        
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            
            interface_info = {
                'name': iface,
                'ipv4': [],
                'ipv6': [],
                'mac': None,
            }
            
            if netifaces.AF_LINK in addrs:
                interface_info['mac'] = addrs[netifaces.AF_LINK][0]['addr']
            
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    interface_info['ipv4'].append({
                        'address': addr['addr'],
                        'netmask': addr.get('netmask', ''),
                        'broadcast': addr.get('broadcast', ''),
                    })
            
            if netifaces.AF_INET6 in addrs:
                for addr in addrs[netifaces.AF_INET6]:
                    interface_info['ipv6'].append({
                        'address': addr['addr'],
                        'netmask': addr.get('netmask', ''),
                    })
            
            interfaces.append(interface_info)
        
        return interfaces

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Enums
    'HTTPMethod',
    'NetworkProtocol',
    
    # Classes
    'HTTPClient',
    'WebSocketClient',
    'NetworkUtils',
]

# ============================================================
# INITIALIZATION
# ============================================================

logger.info("Network utilities module initialized")
