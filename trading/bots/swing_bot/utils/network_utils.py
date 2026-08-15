"""
Swing Bot Network Utilities Module
===================================

This module provides network utilities for the Swing Bot trading system.
Includes HTTP clients, WebSocket utilities, and network-related helpers.
"""

import socket
import ipaddress
import urllib.parse
import requests
import aiohttp
import asyncio
import json
import ssl
import time
from typing import Any, Dict, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import re
import dns.resolver
import ping3


class NetworkProtocol(Enum):
    """Network protocols."""
    HTTP = "http"
    HTTPS = "https"
    WS = "ws"
    WSS = "wss"
    TCP = "tcp"
    UDP = "udp"


class RequestMethod(Enum):
    """HTTP request methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


@dataclass
class NetworkStats:
    """Network statistics."""
    requests_sent: int = 0
    requests_received: int = 0
    total_bytes_sent: int = 0
    total_bytes_received: int = 0
    avg_response_time: float = 0.0
    max_response_time: float = 0.0
    min_response_time: float = float('inf')
    errors: int = 0
    last_error: Optional[str] = None


class NetworkClient:
    """
    Network client for making HTTP/HTTPS requests.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        headers: Optional[Dict[str, str]] = None,
        verify_ssl: bool = True,
        proxy: Optional[str] = None,
        user_agent: str = "SwingBot/3.0"
    ):
        """
        Initialize the network client.
        
        Args:
            base_url: Base URL for requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            headers: Default headers
            verify_ssl: Verify SSL certificates
            proxy: Proxy URL
            user_agent: User agent string
        """
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = headers or {}
        self.headers["User-Agent"] = user_agent
        self.verify_ssl = verify_ssl
        self.proxy = proxy
        self.session = requests.Session()
        self._stats = NetworkStats()
        
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
    
    def _build_url(self, endpoint: str) -> str:
        """Build the full URL."""
        if endpoint.startswith(("http://", "https://")):
            return endpoint
        if self.base_url:
            return urllib.parse.urljoin(self.base_url, endpoint)
        return endpoint
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> requests.Response:
        """Make an HTTP request with retries."""
        url = self._build_url(endpoint)
        headers = {**self.headers, **(headers or {})}
        timeout = timeout or self.timeout
        
        attempts = 0
        last_error = None
        
        while attempts < self.max_retries:
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=headers,
                    timeout=timeout,
                    verify=self.verify_ssl
                )
                self._stats.requests_sent += 1
                self._stats.total_bytes_sent += len(data or "") + len(json_data or "")
                self._stats.total_bytes_received += len(response.content or "")
                return response
            except requests.RequestException as e:
                last_error = e
                self._stats.errors += 1
                attempts += 1
                if attempts < self.max_retries:
                    time.sleep(2 ** attempts)
        
        raise last_error
    
    def get(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> requests.Response:
        """Make a GET request."""
        return self._make_request("GET", endpoint, params=params, headers=headers, timeout=timeout)
    
    def post(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> requests.Response:
        """Make a POST request."""
        return self._make_request("POST", endpoint, data=data, json_data=json_data, params=params, headers=headers, timeout=timeout)
    
    def put(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> requests.Response:
        """Make a PUT request."""
        return self._make_request("PUT", endpoint, data=data, json_data=json_data, params=params, headers=headers, timeout=timeout)
    
    def delete(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> requests.Response:
        """Make a DELETE request."""
        return self._make_request("DELETE", endpoint, params=params, headers=headers, timeout=timeout)
    
    def patch(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> requests.Response:
        """Make a PATCH request."""
        return self._make_request("PATCH", endpoint, data=data, json_data=json_data, params=params, headers=headers, timeout=timeout)
    
    def get_json(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> Dict:
        """Make a GET request and return JSON response."""
        response = self.get(endpoint, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    
    def post_json(
        self,
        endpoint: str,
        json_data: Dict,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> Dict:
        """Make a POST request and return JSON response."""
        response = self.post(endpoint, json_data=json_data, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    
    def get_stats(self) -> NetworkStats:
        """Get network statistics."""
        return self._stats


class AsyncNetworkClient:
    """
    Async network client for making HTTP/HTTPS requests.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        headers: Optional[Dict[str, str]] = None,
        verify_ssl: bool = True,
        proxy: Optional[str] = None,
        user_agent: str = "SwingBot/3.0"
    ):
        """
        Initialize the async network client.
        
        Args:
            base_url: Base URL for requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            headers: Default headers
            verify_ssl: Verify SSL certificates
            proxy: Proxy URL
            user_agent: User agent string
        """
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = headers or {}
        self.headers["User-Agent"] = user_agent
        self.verify_ssl = verify_ssl
        self.proxy = proxy
        self.session: Optional[aiohttp.ClientSession] = None
        self._stats = NetworkStats()
        self._lock = asyncio.Lock()
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the session."""
        async with self._lock:
            if self.session is None or self.session.closed:
                connector = aiohttp.TCPConnector(ssl=self.verify_ssl)
                self.session = aiohttp.ClientSession(
                    connector=connector,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                )
        return self.session
    
    def _build_url(self, endpoint: str) -> str:
        """Build the full URL."""
        if endpoint.startswith(("http://", "https://")):
            return endpoint
        if self.base_url:
            return urllib.parse.urljoin(self.base_url, endpoint)
        return endpoint
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> aiohttp.ClientResponse:
        """Make an HTTP request with retries."""
        url = self._build_url(endpoint)
        headers = {**self.headers, **(headers or {})}
        timeout = timeout or self.timeout
        
        attempts = 0
        last_error = None
        
        while attempts < self.max_retries:
            try:
                session = await self._get_session()
                async with session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=headers,
                    timeout=timeout
                ) as response:
                    self._stats.requests_sent += 1
                    self._stats.total_bytes_sent += len(data or "") + len(json_data or "")
                    # Read response to get size
                    content = await response.read()
                    self._stats.total_bytes_received += len(content)
                    return response, content
            except aiohttp.ClientError as e:
                last_error = e
                self._stats.errors += 1
                attempts += 1
                if attempts < self.max_retries:
                    await asyncio.sleep(2 ** attempts)
        
        raise last_error
    
    async def get(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> Tuple[aiohttp.ClientResponse, bytes]:
        """Make a GET request."""
        return await self._make_request("GET", endpoint, params=params, headers=headers, timeout=timeout)
    
    async def post(
        self,
        endpoint: str,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> Tuple[aiohttp.ClientResponse, bytes]:
        """Make a POST request."""
        return await self._make_request("POST", endpoint, data=data, json_data=json_data, params=params, headers=headers, timeout=timeout)
    
    async def get_json(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> Dict:
        """Make a GET request and return JSON response."""
        response, content = await self.get(endpoint, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return json.loads(content)
    
    async def post_json(
        self,
        endpoint: str,
        json_data: Dict,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> Dict:
        """Make a POST request and return JSON response."""
        response, content = await self.post(endpoint, json_data=json_data, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return json.loads(content)
    
    async def close(self) -> None:
        """Close the session."""
        async with self._lock:
            if self.session and not self.session.closed:
                await self.session.close()
    
    def get_stats(self) -> NetworkStats:
        """Get network statistics."""
        return self._stats


class WebSocketManager:
    """
    WebSocket connection manager.
    """
    
    def __init__(
        self,
        url: str,
        on_message: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        reconnect: bool = True,
        max_reconnect_attempts: int = 5,
        reconnect_delay: float = 1.0
    ):
        """
        Initialize the WebSocket manager.
        
        Args:
            url: WebSocket URL
            on_message: Callback for messages
            on_error: Callback for errors
            on_close: Callback for connection close
            reconnect: Enable auto-reconnect
            max_reconnect_attempts: Maximum reconnect attempts
            reconnect_delay: Delay between reconnect attempts
        """
        self.url = url
        self.on_message = on_message
        self.on_error = on_error
        self.on_close = on_close
        self.reconnect = reconnect
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay
        
        self._ws = None
        self._running = False
        self._reconnect_attempts = 0
        self._lock = asyncio.Lock()
    
    async def connect(self) -> None:
        """Connect to the WebSocket."""
        self._running = True
        self._reconnect_attempts = 0
        
        while self._running and self._reconnect_attempts < self.max_reconnect_attempts:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(self.url) as ws:
                        self._ws = ws
                        self._reconnect_attempts = 0
                        
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                if self.on_message:
                                    self.on_message(msg.data)
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                if self.on_error:
                                    self.on_error(ws.exception())
                                break
                            elif msg.type == aiohttp.WSMsgType.CLOSE:
                                if self.on_close:
                                    self.on_close()
                                break
            except Exception as e:
                if self.on_error:
                    self.on_error(e)
                
                if self.reconnect and self._running:
                    self._reconnect_attempts += 1
                    await asyncio.sleep(self.reconnect_delay * self._reconnect_attempts)
                else:
                    break
    
    async def send(self, data: str) -> None:
        """Send data over the WebSocket."""
        if self._ws and not self._ws.closed:
            await self._ws.send_str(data)
    
    async def send_json(self, data: Dict) -> None:
        """Send JSON data over the WebSocket."""
        if self._ws and not self._ws.closed:
            await self._ws.send_json(data)
    
    async def close(self) -> None:
        """Close the WebSocket connection."""
        self._running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()


def is_valid_ip(ip: str) -> bool:
    """Check if a string is a valid IP address."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def is_valid_port(port: int) -> bool:
    """Check if a port is valid."""
    return 1 <= port <= 65535


def is_valid_url(url: str) -> bool:
    """Check if a string is a valid URL."""
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def resolve_dns(hostname: str) -> List[str]:
    """Resolve a hostname to IP addresses."""
    try:
        return [str(ip) for ip in dns.resolver.resolve(hostname, 'A')]
    except Exception:
        return []


def ping_host(host: str, count: int = 4) -> Optional[float]:
    """Ping a host and return average latency."""
    try:
        results = ping3.ping(host, count=count)
        if results:
            return sum(results) / len(results)
    except Exception:
        pass
    return None


def get_local_ip() -> str:
    """Get the local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_public_ip() -> Optional[str]:
    """Get the public IP address."""
    try:
        response = requests.get("https://api.ipify.org", timeout=5)
        if response.status_code == 200:
            return response.text.strip()
    except Exception:
        pass
    return None


def check_port(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a port is open on a host."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def get_service_status(host: str, port: int, timeout: float = 5.0) -> bool:
    """Check if a service is running on a host and port."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except Exception:
        return False


__all__ = [
    # Enums
    'NetworkProtocol',
    'RequestMethod',
    
    # Classes
    'NetworkStats',
    'NetworkClient',
    'AsyncNetworkClient',
    'WebSocketManager',
    
    # Functions
    'is_valid_ip',
    'is_valid_port',
    'is_valid_url',
    'resolve_dns',
    'ping_host',
    'get_local_ip',
    'get_public_ip',
    'check_port',
    'get_service_status',
]
