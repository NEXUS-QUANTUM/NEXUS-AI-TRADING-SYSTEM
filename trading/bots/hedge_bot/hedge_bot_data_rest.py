# trading/bots/hedge_bot/hedge_bot_data_rest.py

import asyncio
import logging
import time
import json
import hashlib
import base64
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable, BinaryIO
from decimal import Decimal
from collections import defaultdict
import aiohttp
import aiofiles
import ssl
import certifi

logger = logging.getLogger(__name__)


class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ContentType(str, Enum):
    JSON = "application/json"
    FORM = "application/x-www-form-urlencoded"
    MULTIPART = "multipart/form-data"
    XML = "application/xml"
    TEXT = "text/plain"
    HTML = "text/html"
    BINARY = "application/octet-stream"
    CSV = "text/csv"
    PROTOBUF = "application/protobuf"
    MSGPACK = "application/msgpack"
    YAML = "application/yaml"


class AuthType(str, Enum):
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    JWT = "jwt"
    DIGEST = "digest"
    AWS_SIGV4 = "aws_sigv4"
    CUSTOM = "custom"


class ResponseFormat(str, Enum):
    JSON = "json"
    TEXT = "text"
    BINARY = "binary"
    STREAM = "stream"
    XML = "xml"
    CSV = "csv"
    YAML = "yaml"


@dataclass
class RestEndpoint:
    id: str
    name: str
    base_url: str
    path: str
    method: HTTPMethod
    auth_type: AuthType
    timeout: int = 30
    retry_count: int = 3
    retry_delay: float = 1.0
    rate_limit: Optional[float] = None
    headers: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RestRequest:
    id: str
    endpoint_id: str
    method: HTTPMethod
    url: str
    headers: Dict[str, str]
    params: Dict[str, Any]
    body: Any
    timeout: int
    retry_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class RestResponse:
    id: str
    request_id: str
    status_code: int
    headers: Dict[str, str]
    body: Any
    content_type: str
    encoding: str
    size: int
    elapsed_time: float
    retry_count: int
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RestClient:
    id: str
    name: str
    base_url: str
    auth_type: AuthType
    auth_config: Dict[str, Any]
    timeout: int = 30
    max_retries: int = 3
    rate_limit: Optional[float] = None
    headers: Dict[str, str] = field(default_factory=dict)
    session: Optional[aiohttp.ClientSession] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class RestDataManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._clients: Dict[str, RestClient] = {}
        self._endpoints: Dict[str, RestEndpoint] = {}
        self._requests: Dict[str, RestRequest] = {}
        self._responses: Dict[str, RestResponse] = {}
        self._sessions: Dict[str, aiohttp.ClientSession] = {}
        self._rate_limits: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._handlers: Dict[int, Callable] = {}
        self._interceptors: List[Callable] = []
        self._observers: List[Callable] = []
        self._running = False
        self._ssl_context = None
        
        self._initialize_ssl_context()

    def _initialize_ssl_context(self) -> None:
        try:
            self._ssl_context = ssl.create_default_context(cafile=certifi.where())
        except:
            self._ssl_context = ssl.create_default_context()

    async def create_client(
        self,
        name: str,
        base_url: str,
        auth_type: AuthType = AuthType.NONE,
        auth_config: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        max_retries: int = 3,
        rate_limit: Optional[float] = None,
        headers: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RestClient:
        async with self._lock:
            client_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            client = RestClient(
                id=client_id,
                name=name,
                base_url=base_url.rstrip('/'),
                auth_type=auth_type,
                auth_config=auth_config or {},
                timeout=timeout,
                max_retries=max_retries,
                rate_limit=rate_limit,
                headers=headers or {},
                metadata=metadata or {}
            )
            
            self._clients[client_id] = client
            await self._create_session(client)
            
            logger.info(f"Created REST client: {name}")
            return client

    async def _create_session(self, client: RestClient) -> None:
        connector = aiohttp.TCPConnector(ssl=self._ssl_context, limit=100)
        
        session = aiohttp.ClientSession(
            connector=connector,
            base_url=client.base_url,
            headers=client.headers,
            timeout=aiohttp.ClientTimeout(total=client.timeout)
        )
        
        self._sessions[client.id] = session

    async def create_endpoint(
        self,
        client_id: str,
        name: str,
        path: str,
        method: HTTPMethod = HTTPMethod.GET,
        auth_type: Optional[AuthType] = None,
        timeout: Optional[int] = None,
        retry_count: Optional[int] = None,
        rate_limit: Optional[float] = None,
        headers: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[RestEndpoint]:
        async with self._lock:
            if client_id not in self._clients:
                return None
            
            client = self._clients[client_id]
            
            endpoint_id = hashlib.md5(f"{client_id}_{name}_{time.time()}".encode()).hexdigest()
            
            endpoint = RestEndpoint(
                id=endpoint_id,
                name=name,
                base_url=client.base_url,
                path=path.lstrip('/'),
                method=method,
                auth_type=auth_type or client.auth_type,
                timeout=timeout or client.timeout,
                retry_count=retry_count or client.max_retries,
                rate_limit=rate_limit or client.rate_limit,
                headers=headers or {},
                metadata=metadata or {}
            )
            
            self._endpoints[endpoint_id] = endpoint
            return endpoint

    async def execute(
        self,
        endpoint_id: str,
        params: Optional[Dict[str, Any]] = None,
        body: Any = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        retry_count: Optional[int] = None,
        response_format: ResponseFormat = ResponseFormat.JSON
    ) -> RestResponse:
        async with self._lock:
            if endpoint_id not in self._endpoints:
                raise ValueError(f"Endpoint not found: {endpoint_id}")
            
            endpoint = self._endpoints[endpoint_id]
            client = self._clients.get(endpoint.auth_type.value, None)
            
            if not client and endpoint.auth_type != AuthType.NONE:
                for c in self._clients.values():
                    if c.auth_type == endpoint.auth_type:
                        client = c
                        break
            
            request_id = hashlib.md5(f"{endpoint_id}_{time.time()}".encode()).hexdigest()
            
            full_headers = endpoint.headers.copy()
            if headers:
                full_headers.update(headers)
            
            auth_headers = await self._get_auth_headers(client, endpoint, params)
            if auth_headers:
                full_headers.update(auth_headers)
            
            await self._check_rate_limit(endpoint)
            
            url = self._build_url(endpoint, params)
            
            request = RestRequest(
                id=request_id,
                endpoint_id=endpoint_id,
                method=endpoint.method,
                url=url,
                headers=full_headers,
                params=params or {},
                body=body,
                timeout=timeout or endpoint.timeout,
                retry_count=0,
                metadata={
                    "endpoint_name": endpoint.name,
                    "client_id": client.id if client else None
                }
            )
            
            self._requests[request_id] = request
            
            for interceptor in self._interceptors:
                try:
                    if asyncio.iscoroutinefunction(interceptor):
                        request = await interceptor(request)
                    else:
                        request = interceptor(request)
                except Exception as e:
                    logger.error(f"Interceptor error: {e}")
            
            return await self._execute_request(request, endpoint, response_format)

    async def _execute_request(
        self,
        request: RestRequest,
        endpoint: RestEndpoint,
        response_format: ResponseFormat
    ) -> RestResponse:
        start_time = time.time()
        retry_count = 0
        max_retries = request.retry_count or endpoint.retry_count
        
        while retry_count <= max_retries:
            try:
                session = await self._get_session(endpoint)
                
                async with session.request(
                    method=request.method.value,
                    url=request.url,
                    headers=request.headers,
                    params=request.params,
                    json=request.body if isinstance(request.body, dict) else None,
                    data=request.body if not isinstance(request.body, dict) else None,
                    timeout=aiohttp.ClientTimeout(total=request.timeout)
                ) as response:
                    
                    raw_body = await response.read()
                    elapsed_time = time.time() - start_time
                    
                    body = await self._parse_response(raw_body, response.headers.get('content-type', ''), response_format)
                    
                    resp = RestResponse(
                        id=hashlib.md5(f"{request.id}_{time.time()}".encode()).hexdigest(),
                        request_id=request.id,
                        status_code=response.status,
                        headers=dict(response.headers),
                        body=body,
                        content_type=response.headers.get('content-type', ''),
                        encoding=response.get_encoding(),
                        size=len(raw_body),
                        elapsed_time=elapsed_time,
                        retry_count=retry_count,
                        success=200 <= response.status < 300
                    )
                    
                    self._responses[resp.id] = resp
                    await self._notify_observers("response_received", resp)
                    
                    if resp.status_code in self._handlers:
                        await self._handlers[resp.status_code](resp)
                    
                    return resp
                    
            except asyncio.TimeoutError:
                retry_count += 1
                if retry_count > max_retries:
                    return self._create_error_response(request, "Request timeout", retry_count, time.time() - start_time)
                await asyncio.sleep(endpoint.retry_delay * retry_count)
                
            except aiohttp.ClientError as e:
                retry_count += 1
                if retry_count > max_retries:
                    return self._create_error_response(request, str(e), retry_count, time.time() - start_time)
                await asyncio.sleep(endpoint.retry_delay * retry_count)
                
            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    return self._create_error_response(request, str(e), retry_count, time.time() - start_time)
                await asyncio.sleep(endpoint.retry_delay * retry_count)
        
        return self._create_error_response(request, "Max retries exceeded", retry_count, time.time() - start_time)

    async def _get_session(self, endpoint: RestEndpoint) -> aiohttp.ClientSession:
        auth_type = endpoint.auth_type
        
        for client in self._clients.values():
            if client.auth_type == auth_type:
                if client.id in self._sessions:
                    return self._sessions[client.id]
        
        return self._sessions.get("default")

    async def _get_auth_headers(
        self,
        client: Optional[RestClient],
        endpoint: RestEndpoint,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, str]]:
        auth_type = endpoint.auth_type
        
        if auth_type == AuthType.NONE:
            return None
        
        if auth_type == AuthType.BASIC:
            username = endpoint.metadata.get("username") or (client.auth_config.get("username") if client else None)
            password = endpoint.metadata.get("password") or (client.auth_config.get("password") if client else None)
            if username and password:
                auth = base64.b64encode(f"{username}:{password}".encode()).decode()
                return {"Authorization": f"Basic {auth}"}
        
        elif auth_type == AuthType.BEARER:
            token = endpoint.metadata.get("token") or (client.auth_config.get("token") if client else None)
            if token:
                return {"Authorization": f"Bearer {token}"}
        
        elif auth_type == AuthType.API_KEY:
            key = endpoint.metadata.get("api_key") or (client.auth_config.get("api_key") if client else None)
            key_name = endpoint.metadata.get("api_key_name") or (client.auth_config.get("api_key_name", "api_key") if client else "api_key")
            key_location = endpoint.metadata.get("api_key_location") or (client.auth_config.get("api_key_location", "header") if client else "header")
            
            if key:
                if key_location == "header":
                    return {key_name: key}
                elif key_location == "query":
                    if params is None:
                        params = {}
                    params[key_name] = key
                    return None
        
        elif auth_type == AuthType.JWT:
            token = endpoint.metadata.get("jwt_token") or (client.auth_config.get("jwt_token") if client else None)
            if token:
                return {"Authorization": f"Bearer {token}"}
        
        elif auth_type == AuthType.AWS_SIGV4:
            # Simplified AWS Signature V4 - full implementation would be more complex
            region = endpoint.metadata.get("aws_region") or (client.auth_config.get("region") if client else "us-east-1")
            service = endpoint.metadata.get("aws_service") or (client.auth_config.get("service") if client else "execute-api")
            # In production, use aws-requests-auth or similar
            return {}
        
        return None

    async def _check_rate_limit(self, endpoint: RestEndpoint) -> None:
        if not endpoint.rate_limit:
            return
        
        now = time.time()
        key = f"rate_limit_{endpoint.id}"
        
        if key in self._rate_limits:
            if now - self._rate_limits[key].get("last_request", 0) < (1.0 / endpoint.rate_limit):
                wait_time = (1.0 / endpoint.rate_limit) - (now - self._rate_limits[key]["last_request"])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
        
        self._rate_limits[key]["last_request"] = time.time()

    def _build_url(self, endpoint: RestEndpoint, params: Optional[Dict[str, Any]] = None) -> str:
        path = endpoint.path
        if path.startswith('/'):
            path = path[1:]
        
        if params:
            query_params = {}
            for key, value in params.items():
                if key not in endpoint.path and not key.startswith('_'):
                    query_params[key] = value
            
            if query_params:
                return f"{endpoint.base_url}/{path}?{urllib.parse.urlencode(query_params)}"
        
        return f"{endpoint.base_url}/{path}"

    async def _parse_response(
        self,
        data: bytes,
        content_type: str,
        response_format: ResponseFormat
    ) -> Any:
        if not data:
            return None
        
        content_type = content_type.lower()
        
        if response_format == ResponseFormat.JSON or 'json' in content_type:
            try:
                return json.loads(data.decode('utf-8'))
            except:
                return data
        
        elif response_format == ResponseFormat.TEXT or 'text' in content_type:
            try:
                return data.decode('utf-8')
            except:
                return data
        
        elif response_format == ResponseFormat.XML or 'xml' in content_type:
            return data
        
        elif response_format == ResponseFormat.CSV or 'csv' in content_type:
            return data
        
        elif response_format == ResponseFormat.YAML or 'yaml' in content_type:
            try:
                import yaml
                return yaml.safe_load(data)
            except:
                return data
        
        elif response_format == ResponseFormat.BINARY:
            return data
        
        elif response_format == ResponseFormat.STREAM:
            return data
        
        return data

    def _create_error_response(
        self,
        request: RestRequest,
        error: str,
        retry_count: int,
        elapsed_time: float
    ) -> RestResponse:
        return RestResponse(
            id=hashlib.md5(f"{request.id}_{time.time()}".encode()).hexdigest(),
            request_id=request.id,
            status_code=0,
            headers={},
            body=None,
            content_type="",
            encoding="",
            size=0,
            elapsed_time=elapsed_time,
            retry_count=retry_count,
            success=False,
            error=error
        )

    def register_status_handler(self, status_code: int, handler: Callable) -> None:
        self._handlers[status_code] = handler

    def register_interceptor(self, interceptor: Callable) -> None:
        self._interceptors.append(interceptor)

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    async def get_client(self, client_id: str) -> Optional[RestClient]:
        return self._clients.get(client_id)

    async def get_endpoint(self, endpoint_id: str) -> Optional[RestEndpoint]:
        return self._endpoints.get(endpoint_id)

    async def get_request(self, request_id: str) -> Optional[RestRequest]:
        return self._requests.get(request_id)

    async def get_response(self, response_id: str) -> Optional[RestResponse]:
        return self._responses.get(response_id)

    async def close(self) -> None:
        for session in self._sessions.values():
            await session.close()
        self._sessions.clear()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "clients": len(self._clients),
            "endpoints": len(self._endpoints),
            "requests": len(self._requests),
            "responses": len(self._responses),
            "sessions": len(self._sessions),
            "handlers": len(self._handlers),
            "interceptors": len(self._interceptors),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "HTTPMethod",
    "ContentType",
    "AuthType",
    "ResponseFormat",
    "RestEndpoint",
    "RestRequest",
    "RestResponse",
    "RestClient",
    "RestDataManager"
]
