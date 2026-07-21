"""
NEXUS AI TRADING SYSTEM - HEDGE BOT NETWORK UTILS MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module d'utilitaires réseau pour le Hedge Bot.
Support des requêtes HTTP, WebSocket, proxy, et monitoring réseau.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import hashlib
import ipaddress
import json
import logging
import socket
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse, parse_qs, urlencode, urljoin

import aiohttp
import aiohttp.client_exceptions
import dns.asyncresolver
import dns.resolver
import ping3
import requests
from aiohttp_socks import ProxyConnector, ProxyType

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class NetworkProtocol(Enum):
    """Protocoles réseau."""
    HTTP = "http"
    HTTPS = "https"
    WS = "ws"
    WSS = "wss"
    TCP = "tcp"
    UDP = "udp"
    DNS = "dns"
    ICMP = "icmp"


class ProxyType(Enum):
    """Types de proxy."""
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class NetworkStatus(Enum):
    """Statuts réseau."""
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class NetworkEndpoint:
    """Point d'extrémité réseau."""
    url: str
    protocol: NetworkProtocol
    host: str
    port: int
    path: str
    query: Dict[str, str]
    scheme: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "url": self.url,
            "protocol": self.protocol.value,
            "host": self.host,
            "port": self.port,
            "path": self.path,
            "query": self.query,
            "scheme": self.scheme,
            "metadata": self.metadata
        }


@dataclass
class NetworkResponse:
    """Réponse réseau."""
    url: str
    status_code: int
    headers: Dict[str, str]
    body: Any
    elapsed: float
    size_bytes: int
    timestamp: datetime
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "url": self.url,
            "status_code": self.status_code,
            "headers": self.headers,
            "body": self.body,
            "elapsed": self.elapsed,
            "size_bytes": self.size_bytes,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata
        }


@dataclass
class DnsRecord:
    """Enregistrement DNS."""
    name: str
    type: str
    ttl: int
    value: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "name": self.name,
            "type": self.type,
            "ttl": self.ttl,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class NetworkStats:
    """Statistiques réseau."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    average_latency: float = 0.0
    max_latency: float = 0.0
    min_latency: float = float('inf')
    uptime_percentage: float = 100.0
    last_check: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "total_bytes_sent": self.total_bytes_sent,
            "total_bytes_received": self.total_bytes_received,
            "average_latency": self.average_latency,
            "max_latency": self.max_latency,
            "min_latency": self.min_latency,
            "uptime_percentage": self.uptime_percentage,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE NETWORK UTILS
# ============================================================================

class NetworkUtils:
    """
    Utilitaires réseau avancés.
    """

    # Timeouts par défaut
    DEFAULT_TIMEOUT = 30
    DEFAULT_CONNECT_TIMEOUT = 10
    DEFAULT_READ_TIMEOUT = 20

    # User agent par défaut
    DEFAULT_USER_AGENT = "NEXUS-AI-TRADING/3.0.0"

    # Ports communs
    COMMON_PORTS = {
        "http": 80,
        "https": 443,
        "ws": 80,
        "wss": 443,
        "ssh": 22,
        "ftp": 21,
        "smtp": 25,
        "pop3": 110,
        "imap": 143,
        "mysql": 3306,
        "postgresql": 5432,
        "redis": 6379,
        "mongodb": 27017,
        "elasticsearch": 9200
    }

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        user_agent: str = DEFAULT_USER_AGENT,
        proxy_config: Optional[Dict[str, str]] = None,
        retry_count: int = 3,
        retry_delay: float = 1.0,
        max_connections: int = 100
    ):
        """
        Initialise les utilitaires réseau.

        Args:
            timeout: Timeout par défaut
            user_agent: User agent
            proxy_config: Configuration du proxy
            retry_count: Nombre de tentatives
            retry_delay: Délai entre les tentatives
            max_connections: Nombre maximum de connexions
        """
        self.timeout = timeout
        self.user_agent = user_agent
        self.proxy_config = proxy_config
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.max_connections = max_connections
        
        # Session HTTP
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws_sessions: Dict[str, aiohttp.ClientWebSocketResponse] = {}
        
        # Cache DNS
        self._dns_cache: Dict[str, List[DnsRecord]] = {}
        self._dns_cache_ttl = 300  # 5 minutes
        
        # Statistiques
        self._stats: NetworkStats = NetworkStats()
        
        # Métriques
        self._metrics = {
            "total_requests": 0,
            "active_connections": 0,
            "by_method": {},
            "by_status": {},
            "last_request": None
        }

        logger.info("NetworkUtils initialisé avec succès")

    # ========================================================================
    # SESSION HTTP
    # ========================================================================

    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Récupère ou crée une session HTTP.

        Returns:
            Session HTTP
        """
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.max_connections,
                limit_per_host=10,
                ttl_dns_cache=300,
                ssl=False
            )
            
            # Configuration du proxy
            proxy = None
            if self.proxy_config:
                proxy_type = self.proxy_config.get("type", "http")
                proxy_host = self.proxy_config.get("host")
                proxy_port = self.proxy_config.get("port")
                proxy_auth = self.proxy_config.get("auth")
                
                if proxy_type == "socks5":
                    connector = ProxyConnector(
                        proxy_type=ProxyType.SOCKS5,
                        host=proxy_host,
                        port=proxy_port,
                        username=proxy_auth.get("username") if proxy_auth else None,
                        password=proxy_auth.get("password") if proxy_auth else None
                    )
                elif proxy_type == "socks4":
                    connector = ProxyConnector(
                        proxy_type=ProxyType.SOCKS4,
                        host=proxy_host,
                        port=proxy_port
                    )
                else:
                    proxy = f"{proxy_type}://{proxy_host}:{proxy_port}"
                    if proxy_auth:
                        proxy = f"{proxy_type}://{proxy_auth.get('username')}:{proxy_auth.get('password')}@{proxy_host}:{proxy_port}"

            timeout = aiohttp.ClientTimeout(
                total=self.timeout,
                connect=self.DEFAULT_CONNECT_TIMEOUT,
                sock_read=self.DEFAULT_READ_TIMEOUT
            )

            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={"User-Agent": self.user_agent},
                proxy=proxy
            )

        return self._session

    async def close(self) -> None:
        """Ferme la session HTTP."""
        if self._session and not self._session.closed:
            await self._session.close()
        
        # Fermeture des WebSockets
        for ws in self._ws_sessions.values():
            if not ws.closed:
                await ws.close()
        self._ws_sessions.clear()

    # ========================================================================
    # REQUÊTES HTTP
    # ========================================================================

    async def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        data: Optional[Any] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[int] = None,
        retry: Optional[int] = None,
        retry_delay: Optional[float] = None,
        **kwargs
    ) -> NetworkResponse:
        """
        Effectue une requête HTTP.

        Args:
            method: Méthode HTTP
            url: URL
            params: Paramètres de requête
            data: Données
            json_data: Données JSON
            headers: En-têtes
            timeout: Timeout
            retry: Nombre de tentatives
            retry_delay: Délai entre les tentatives
            **kwargs: Arguments supplémentaires

        Returns:
            Réponse réseau
        """
        session = await self._get_session()
        
        retry = retry or self.retry_count
        retry_delay = retry_delay or self.retry_delay
        timeout = timeout or self.timeout
        
        start_time = time.time()
        last_error = None
        
        for attempt in range(retry):
            try:
                async with session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=headers,
                    timeout=timeout,
                    **kwargs
                ) as response:
                    elapsed = time.time() - start_time
                    
                    # Lecture du corps
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type:
                        body = await response.json()
                    else:
                        body = await response.text()
                    
                    # Mise à jour des statistiques
                    self._update_stats(
                        success=True,
                        size=len(str(body)),
                        latency=elapsed
                    )
                    
                    return NetworkResponse(
                        url=url,
                        status_code=response.status,
                        headers=dict(response.headers),
                        body=body,
                        elapsed=elapsed,
                        size_bytes=len(str(body)),
                        timestamp=datetime.now(),
                        success=True
                    )

            except Exception as e:
                last_error = e
                elapsed = time.time() - start_time
                
                if attempt < retry - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                
                self._update_stats(success=False)
                
                return NetworkResponse(
                    url=url,
                    status_code=0,
                    headers={},
                    body=None,
                    elapsed=elapsed,
                    size_bytes=0,
                    timestamp=datetime.now(),
                    success=False,
                    error=str(e)
                )

    async def get(
        self,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> NetworkResponse:
        """
        Effectue une requête GET.

        Args:
            url: URL
            params: Paramètres
            headers: En-têtes
            **kwargs: Arguments supplémentaires

        Returns:
            Réponse réseau
        """
        return await self.request("GET", url, params=params, headers=headers, **kwargs)

    async def post(
        self,
        url: str,
        data: Optional[Any] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> NetworkResponse:
        """
        Effectue une requête POST.

        Args:
            url: URL
            data: Données
            json_data: Données JSON
            headers: En-têtes
            **kwargs: Arguments supplémentaires

        Returns:
            Réponse réseau
        """
        return await self.request(
            "POST", url,
            data=data,
            json_data=json_data,
            headers=headers,
            **kwargs
        )

    async def put(
        self,
        url: str,
        data: Optional[Any] = None,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> NetworkResponse:
        """
        Effectue une requête PUT.

        Args:
            url: URL
            data: Données
            json_data: Données JSON
            headers: En-têtes
            **kwargs: Arguments supplémentaires

        Returns:
            Réponse réseau
        """
        return await self.request(
            "PUT", url,
            data=data,
            json_data=json_data,
            headers=headers,
            **kwargs
        )

    async def delete(
        self,
        url: str,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> NetworkResponse:
        """
        Effectue une requête DELETE.

        Args:
            url: URL
            headers: En-têtes
            **kwargs: Arguments supplémentaires

        Returns:
            Réponse réseau
        """
        return await self.request("DELETE", url, headers=headers, **kwargs)

    async def head(
        self,
        url: str,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> NetworkResponse:
        """
        Effectue une requête HEAD.

        Args:
            url: URL
            headers: En-têtes
            **kwargs: Arguments supplémentaires

        Returns:
            Réponse réseau
        """
        return await self.request("HEAD", url, headers=headers, **kwargs)

    async def options(
        self,
        url: str,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> NetworkResponse:
        """
        Effectue une requête OPTIONS.

        Args:
            url: URL
            headers: En-têtes
            **kwargs: Arguments supplémentaires

        Returns:
            Réponse réseau
        """
        return await self.request("OPTIONS", url, headers=headers, **kwargs)

    # ========================================================================
    # WEBSOCKET
    # ========================================================================

    async def connect_websocket(
        self,
        url: str,
        headers: Optional[Dict] = None,
        protocols: Optional[List[str]] = None,
        **kwargs
    ) -> Optional[aiohttp.ClientWebSocketResponse]:
        """
        Connecte un WebSocket.

        Args:
            url: URL
            headers: En-têtes
            protocols: Protocoles
            **kwargs: Arguments supplémentaires

        Returns:
            Connexion WebSocket
        """
        try:
            session = await self._get_session()
            
            ws = await session.ws_connect(
                url,
                headers=headers,
                protocols=protocols,
                **kwargs
            )
            
            self._ws_sessions[url] = ws
            self._metrics["active_connections"] += 1
            
            logger.info(f"WebSocket connecté: {url}")
            return ws

        except Exception as e:
            logger.error(f"Erreur de connexion WebSocket: {e}")
            return None

    async def disconnect_websocket(self, url: str) -> bool:
        """
        Déconnecte un WebSocket.

        Args:
            url: URL

        Returns:
            True si déconnecté
        """
        try:
            ws = self._ws_sessions.get(url)
            if ws and not ws.closed:
                await ws.close()
                del self._ws_sessions[url]
                self._metrics["active_connections"] -= 1
                return True
            return False

        except Exception as e:
            logger.error(f"Erreur de déconnexion WebSocket: {e}")
            return False

    async def send_websocket(
        self,
        url: str,
        data: Any,
        type: int = aiohttp.WSMsgType.TEXT
    ) -> bool:
        """
        Envoie un message via WebSocket.

        Args:
            url: URL
            data: Données
            type: Type de message

        Returns:
            True si envoyé
        """
        try:
            ws = self._ws_sessions.get(url)
            if ws and not ws.closed:
                await ws.send(data, type)
                return True
            return False

        except Exception as e:
            logger.error(f"Erreur d'envoi WebSocket: {e}")
            return False

    async def receive_websocket(
        self,
        url: str,
        timeout: Optional[float] = None
    ) -> Optional[aiohttp.WSMessage]:
        """
        Reçoit un message via WebSocket.

        Args:
            url: URL
            timeout: Timeout

        Returns:
            Message WebSocket
        """
        try:
            ws = self._ws_sessions.get(url)
            if ws and not ws.closed:
                return await ws.receive(timeout=timeout)
            return None

        except Exception as e:
            logger.error(f"Erreur de réception WebSocket: {e}")
            return None

    # ========================================================================
    # DNS
    # ========================================================================

    async def resolve_dns(
        self,
        hostname: str,
        record_type: str = "A",
        use_cache: bool = True
    ) -> List[DnsRecord]:
        """
        Résout un nom de domaine.

        Args:
            hostname: Nom de domaine
            record_type: Type d'enregistrement
            use_cache: Utiliser le cache

        Returns:
            Enregistrements DNS
        """
        try:
            cache_key = f"{hostname}:{record_type}"
            
            if use_cache and cache_key in self._dns_cache:
                records = self._dns_cache[cache_key]
                if records:
                    age = (datetime.now() - records[0].timestamp).seconds
                    if age < self._dns_cache_ttl:
                        return records

            resolver = dns.asyncresolver.Resolver()
            answers = await resolver.resolve(hostname, record_type)
            
            records = []
            for answer in answers:
                record = DnsRecord(
                    name=hostname,
                    type=record_type,
                    ttl=answer.ttl,
                    value=str(answer),
                    timestamp=datetime.now()
                )
                records.append(record)
            
            self._dns_cache[cache_key] = records
            return records

        except Exception as e:
            logger.error(f"Erreur de résolution DNS: {e}")
            return []

    async def reverse_dns(self, ip: str) -> Optional[str]:
        """
        Résout une adresse IP en nom de domaine.

        Args:
            ip: Adresse IP

        Returns:
            Nom de domaine
        """
        try:
            resolver = dns.asyncresolver.Resolver()
            answers = await resolver.resolve(ip, "PTR")
            return str(answers[0]) if answers else None

        except Exception as e:
            logger.error(f"Erreur de résolution DNS inverse: {e}")
            return None

    # ========================================================================
    # PING ET PORT SCAN
    # ========================================================================

    async def ping(
        self,
        host: str,
        timeout: float = 2.0,
        count: int = 1
    ) -> Optional[float]:
        """
        Ping un hôte.

        Args:
            host: Hôte
            timeout: Timeout
            count: Nombre de pings

        Returns:
            Latence en ms ou None
        """
        try:
            latencies = []
            for _ in range(count):
                latency = ping3.ping(host, timeout=timeout)
                if latency is not None:
                    latencies.append(latency)
                await asyncio.sleep(0.1)
            
            if latencies:
                return sum(latencies) / len(latencies)
            return None

        except Exception as e:
            logger.error(f"Erreur de ping: {e}")
            return None

    async def port_scan(
        self,
        host: str,
        ports: Optional[List[int]] = None,
        timeout: float = 2.0
    ) -> Dict[int, bool]:
        """
        Scanne des ports.

        Args:
            host: Hôte
            ports: Liste des ports
            timeout: Timeout

        Returns:
            Résultats du scan
        """
        if ports is None:
            ports = list(self.COMMON_PORTS.values())
        
        results = {}
        
        for port in ports:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=timeout
                )
                writer.close()
                await writer.wait_closed()
                results[port] = True
            except:
                results[port] = False
        
        return results

    # ========================================================================
    # PARSING ET UTILITAIRES
    # ========================================================================

    def parse_url(self, url: str) -> NetworkEndpoint:
        """
        Parse une URL.

        Args:
            url: URL

        Returns:
            Point d'extrémité réseau
        """
        parsed = urlparse(url)
        
        protocol = NetworkProtocol.HTTP
        if parsed.scheme in ["https", "wss"]:
            protocol = NetworkProtocol.HTTPS if parsed.scheme != "wss" else NetworkProtocol.WSS
        elif parsed.scheme in ["ws"]:
            protocol = NetworkProtocol.WS
        
        port = parsed.port or self.COMMON_PORTS.get(parsed.scheme, 80)
        
        return NetworkEndpoint(
            url=url,
            protocol=protocol,
            host=parsed.hostname or "",
            port=port,
            path=parsed.path or "/",
            query={k: v[0] if v else "" for k, v in parse_qs(parsed.query).items()},
            scheme=parsed.scheme
        )

    def join_url(self, base: str, path: str) -> str:
        """
        Joint une URL.

        Args:
            base: URL de base
            path: Chemin

        Returns:
            URL complète
        """
        return urljoin(base, path)

    def add_query_params(self, url: str, params: Dict[str, str]) -> str:
        """
        Ajoute des paramètres de requête.

        Args:
            url: URL
            params: Paramètres

        Returns:
            URL avec paramètres
        """
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        query.update(params)
        new_query = urlencode(query, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    def is_valid_ip(self, ip: str) -> bool:
        """
        Vérifie si une adresse IP est valide.

        Args:
            ip: Adresse IP

        Returns:
            True si valide
        """
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    def is_valid_url(self, url: str) -> bool:
        """
        Vérifie si une URL est valide.

        Args:
            url: URL

        Returns:
            True si valide
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    def get_public_ip(self) -> Optional[str]:
        """
        Récupère l'IP publique.

        Returns:
            Adresse IP
        """
        try:
            response = requests.get("https://api.ipify.org", timeout=5)
            return response.text.strip() if response.status_code == 200 else None
        except:
            return None

    # ========================================================================
    # STATISTIQUES
    # ========================================================================

    def _update_stats(
        self,
        success: bool,
        size: int = 0,
        latency: float = 0
    ) -> None:
        """
        Met à jour les statistiques.

        Args:
            success: Succès
            size: Taille en bytes
            latency: Latence
        """
        self._stats.total_requests += 1
        
        if success:
            self._stats.successful_requests += 1
            self._stats.total_bytes_received += size
            
            if latency > self._stats.max_latency:
                self._stats.max_latency = latency
            if latency < self._stats.min_latency:
                self._stats.min_latency = latency
            
            total = self._stats.successful_requests
            self._stats.average_latency = (
                (self._stats.average_latency * (total - 1) + latency) / total
            )
        else:
            self._stats.failed_requests += 1
        
        self._stats.last_check = datetime.now()
        self._stats.uptime_percentage = (
            self._stats.successful_requests / self._stats.total_requests * 100
            if self._stats.total_requests > 0 else 100
        )

    def get_stats(self) -> NetworkStats:
        """
        Récupère les statistiques.

        Returns:
            Statistiques réseau
        """
        return self._stats

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            # Test de connexion
            public_ip = self.get_public_ip()
            
            return {
                "status": "healthy" if public_ip else "degraded",
                "public_ip": public_ip,
                "total_requests": self._stats.total_requests,
                "success_rate": (
                    self._stats.successful_requests / self._stats.total_requests * 100
                    if self._stats.total_requests > 0 else 100
                ),
                "average_latency": self._stats.average_latency,
                "active_websockets": len(self._ws_sessions),
                "dns_cache_size": len(self._dns_cache),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_network_utils(
    timeout: int = 30,
    user_agent: str = "NEXUS-AI-TRADING/3.0.0",
    proxy_config: Optional[Dict[str, str]] = None,
    retry_count: int = 3
) -> NetworkUtils:
    """
    Crée une instance de NetworkUtils.

    Args:
        timeout: Timeout par défaut
        user_agent: User agent
        proxy_config: Configuration du proxy
        retry_count: Nombre de tentatives

    Returns:
        Instance de NetworkUtils
    """
    return NetworkUtils(
        timeout=timeout,
        user_agent=user_agent,
        proxy_config=proxy_config,
        retry_count=retry_count
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "NetworkProtocol",
    "ProxyType",
    "NetworkStatus",
    "NetworkEndpoint",
    "NetworkResponse",
    "DnsRecord",
    "NetworkStats",
    "NetworkUtils",
    "create_network_utils"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation de NetworkUtils."""
    print("=" * 60)
    print("NEXUS AI TRADING - HEDGE BOT NETWORK UTILS")
    print("=" * 60)

    # Création de l'instance
    network = create_network_utils()

    print(f"\n✅ NetworkUtils initialisé")

    # Requête HTTP GET
    print(f"\n🌐 Requête HTTP GET...")
    response = await network.get("https://api.github.com/zen")
    if response.success:
        print(f"   Statut: {response.status_code}")
        print(f"   Body: {response.body[:100]}...")
        print(f"   Latence: {response.elapsed:.3f}s")

    # Requête POST
    print(f"\n📤 Requête HTTP POST...")
    response = await network.post(
        "https://httpbin.org/post",
        json_data={"test": "value"}
    )
    if response.success:
        print(f"   Statut: {response.status_code}")
        print(f"   Body: {response.body.get('json', {})}")

    # Résolution DNS
    print(f"\n🔍 Résolution DNS...")
    records = await network.resolve_dns("google.com")
    for record in records[:3]:
        print(f"   {record.type}: {record.value}")

    # Ping
    print(f"\n🏓 Ping...")
    latency = await network.ping("google.com")
    if latency:
        print(f"   Latence: {latency:.2f}ms")

    # Port scan
    print(f"\n🔎 Port scan...")
    results = await network.port_scan("google.com", [80, 443, 22])
    for port, open_status in results.items():
        print(f"   Port {port}: {'Ouvert' if open_status else 'Fermé'}")

    # Statistiques
    stats = network.get_stats()
    print(f"\n📊 Statistiques:")
    print(f"   Requêtes: {stats.total_requests}")
    print(f"   Succès: {stats.successful_requests}")
    print(f"   Latence moyenne: {stats.average_latency:.3f}s")

    # Santé du service
    health = await network.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Statut: {health['status']}")
    print(f"   IP publique: {health['public_ip']}")
    print(f"   WebSockets actifs: {health['active_websockets']}")

    # Fermeture
    await network.close()

    print("\n" + "=" * 60)
    print("NetworkUtils NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    from urllib.parse import urlunparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
