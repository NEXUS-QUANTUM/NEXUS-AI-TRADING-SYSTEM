# trading/bots/hedge_bot/hedge_bot_data_redis.py

import asyncio
import logging
import time
import json
import pickle
import zlib
import hashlib
import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict
import threading
import queue

try:
    import redis
    import redis.asyncio as aioredis
    from redis.exceptions import RedisError, ConnectionError, TimeoutError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("redis-py not installed. Please install: pip install redis")

try:
    import redis_lock
    REDIS_LOCK_AVAILABLE = True
except ImportError:
    REDIS_LOCK_AVAILABLE = False

logger = logging.getLogger(__name__)


class RedisDataType(str, Enum):
    STRING = "string"
    HASH = "hash"
    LIST = "list"
    SET = "set"
    ZSET = "zset"
    STREAM = "stream"
    HYPERLOGLOG = "hyperloglog"
    BITMAP = "bitmap"
    GEO = "geo"
    JSON = "json"
    TIMESERIES = "timeseries"


class RedisPersistence(str, Enum):
    RDB = "rdb"
    AOF = "aof"
    BOTH = "both"
    NONE = "none"


class RedisEviction(str, Enum):
    NO_EVICTION = "noeviction"
    ALL_KEYS_LRU = "allkeys_lru"
    VOLATILE_LRU = "volatile_lru"
    ALL_KEYS_RANDOM = "allkeys_random"
    VOLATILE_RANDOM = "volatile_random"
    VOLATILE_TTL = "volatile_ttl"
    ALL_KEYS_LFU = "allkeys_lfu"
    VOLATILE_LFU = "volatile_lfu"


@dataclass
class RedisConfig:
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = None
    db: int = 0
    ssl: bool = False
    ssl_certfile: Optional[str] = None
    ssl_keyfile: Optional[str] = None
    ssl_ca_certs: Optional[str] = None
    max_connections: int = 50
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    retry_on_timeout: bool = True
    health_check_interval: int = 30
    decode_responses: bool = False
    encoding: str = "utf-8"
    cluster_mode: bool = False
    cluster_nodes: List[str] = field(default_factory=list)
    sentinel_mode: bool = False
    sentinel_hosts: List[str] = field(default_factory=list)
    sentinel_master_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RedisKeyInfo:
    key: str
    type: str
    ttl: int
    size: int
    last_access: float
    created_at: float
    expires_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RedisStreamMessage:
    id: str
    data: Dict[str, Any]
    timestamp: float
    stream: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RedisGeoLocation:
    longitude: float
    latitude: float
    name: str
    distance: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class RedisDataManager:
    
    def __init__(self, config: Optional[RedisConfig] = None):
        self.config = config or RedisConfig()
        self._lock = asyncio.Lock()
        self._client: Optional[aioredis.Redis] = None
        self._cluster_client: Optional[aioredis.RedisCluster] = None
        self._sentinel_client: Optional[aioredis.Sentinel] = None
        self._connected = False
        self._running = False
        self._pipeline = None
        self._pubsub: Optional[aioredis.PubSub] = None
        self._subscriptions: Dict[str, List[Callable]] = defaultdict(list)
        self._pubsub_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._stats = defaultdict(int)
        self._key_cache: Dict[str, Any] = {}
        self._cache_ttl = 60
        self._last_cache_cleanup = time.time()
        
        self._initialize_connection()

    def _initialize_connection(self) -> None:
        if not REDIS_AVAILABLE:
            raise ImportError("redis-py not available")

    async def connect(self) -> None:
        async with self._lock:
            if self._connected:
                return
            
            logger.info(f"Connecting to Redis at {self.config.host}:{self.config.port}")
            
            try:
                if self.config.cluster_mode:
                    await self._connect_cluster()
                elif self.config.sentinel_mode:
                    await self._connect_sentinel()
                else:
                    await self._connect_single()
                
                self._connected = True
                self._running = True
                
                self._pubsub = self._client.pubsub()
                self._pubsub_task = asyncio.create_task(self._pubsub_loop())
                self._health_check_task = asyncio.create_task(self._health_check_loop())
                
                logger.info("Redis connected successfully")
                
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise

    async def _connect_single(self) -> None:
        connection_kwargs = {
            "host": self.config.host,
            "port": self.config.port,
            "db": self.config.db,
            "password": self.config.password,
            "ssl": self.config.ssl,
            "decode_responses": self.config.decode_responses,
            "encoding": self.config.encoding,
            "socket_timeout": self.config.socket_timeout,
            "socket_connect_timeout": self.config.socket_connect_timeout,
            "retry_on_timeout": self.config.retry_on_timeout,
            "health_check_interval": self.config.health_check_interval,
            "max_connections": self.config.max_connections
        }
        
        if self.config.ssl:
            if self.config.ssl_certfile:
                connection_kwargs["ssl_certfile"] = self.config.ssl_certfile
            if self.config.ssl_keyfile:
                connection_kwargs["ssl_keyfile"] = self.config.ssl_keyfile
            if self.config.ssl_ca_certs:
                connection_kwargs["ssl_ca_certs"] = self.config.ssl_ca_certs
        
        self._client = aioredis.Redis(**connection_kwargs)
        await self._client.ping()

    async def _connect_cluster(self) -> None:
        from aioredis import RedisCluster
        
        cluster_kwargs = {
            "startup_nodes": self.config.cluster_nodes,
            "password": self.config.password,
            "decode_responses": self.config.decode_responses,
            "encoding": self.config.encoding,
            "socket_timeout": self.config.socket_timeout,
            "socket_connect_timeout": self.config.socket_connect_timeout,
            "retry_on_timeout": self.config.retry_on_timeout,
            "max_connections": self.config.max_connections
        }
        
        self._cluster_client = RedisCluster(**cluster_kwargs)
        await self._cluster_client.ping()
        self._client = self._cluster_client

    async def _connect_sentinel(self) -> None:
        sentinel_kwargs = {
            "sentinels": self.config.sentinel_hosts,
            "password": self.config.password,
            "db": self.config.db,
            "socket_timeout": self.config.socket_timeout,
            "decode_responses": self.config.decode_responses
        }
        
        self._sentinel_client = aioredis.Sentinel(**sentinel_kwargs)
        self._client = self._sentinel_client.master_for(
            self.config.sentinel_master_name,
            password=self.config.password,
            db=self.config.db
        )
        await self._client.ping()

    async def disconnect(self) -> None:
        async with self._lock:
            self._running = False
            self._connected = False
            
            if self._pubsub_task:
                self._pubsub_task.cancel()
                try:
                    await self._pubsub_task
                except asyncio.CancelledError:
                    pass
                self._pubsub_task = None
            
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
                self._health_check_task = None
            
            if self._pubsub:
                try:
                    await self._pubsub.close()
                except:
                    pass
                self._pubsub = None
            
            if self._client:
                try:
                    await self._client.close()
                except:
                    pass
                self._client = None
            
            if self._cluster_client:
                try:
                    await self._cluster_client.close()
                except:
                    pass
                self._cluster_client = None
            
            if self._sentinel_client:
                try:
                    await self._sentinel_client.close()
                except:
                    pass
                self._sentinel_client = None
            
            logger.info("Redis disconnected")

    async def reconnect(self) -> None:
        retries = 0
        max_retries = self.config.socket_connect_timeout
        
        while retries < max_retries and self._running:
            try:
                await self.disconnect()
                await asyncio.sleep(1 * (2 ** retries))
                await self.connect()
                return
            except Exception as e:
                retries += 1
                logger.error(f"Reconnection attempt {retries} failed: {e}")
        
        raise ConnectionError("Failed to reconnect to Redis")

    async def ensure_connection(self) -> None:
        if not self._connected:
            await self.connect()
        
        try:
            await self._client.ping()
        except Exception:
            await self.reconnect()

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        nx: bool = False,
        xx: bool = False,
        serialize: bool = True
    ) -> bool:
        await self.ensure_connection()
        
        try:
            if serialize:
                value = self._serialize(value)
            
            if ttl:
                result = await self._client.set(key, value, ex=ttl, nx=nx, xx=xx)
            else:
                result = await self._client.set(key, value, nx=nx, xx=xx)
            
            self._stats['sets'] += 1
            
            if key in self._key_cache:
                del self._key_cache[key]
            
            return result
            
        except Exception as e:
            logger.error(f"Error setting key {key}: {e}")
            self._stats['errors'] += 1
            return False

    async def get(
        self,
        key: str,
        deserialize: bool = True,
        use_cache: bool = False
    ) -> Optional[Any]:
        await self.ensure_connection()
        
        try:
            if use_cache and key in self._key_cache:
                cache_entry = self._key_cache[key]
                if time.time() - cache_entry["timestamp"] < self._cache_ttl:
                    return cache_entry["value"]
            
            value = await self._client.get(key)
            
            if value is None:
                return None
            
            if deserialize:
                value = self._deserialize(value)
            
            if use_cache:
                self._key_cache[key] = {
                    "value": value,
                    "timestamp": time.time()
                }
            
            self._stats['gets'] += 1
            return value
            
        except Exception as e:
            logger.error(f"Error getting key {key}: {e}")
            self._stats['errors'] += 1
            return None

    async def delete(self, *keys: str) -> int:
        await self.ensure_connection()
        
        try:
            result = await self._client.delete(*keys)
            
            for key in keys:
                if key in self._key_cache:
                    del self._key_cache[key]
            
            self._stats['deletes'] += 1
            return result
            
        except Exception as e:
            logger.error(f"Error deleting keys: {e}")
            self._stats['errors'] += 1
            return 0

    async def exists(self, *keys: str) -> int:
        await self.ensure_connection()
        
        try:
            result = await self._client.exists(*keys)
            self._stats['exists'] += 1
            return result
            
        except Exception as e:
            logger.error(f"Error checking existence: {e}")
            self._stats['errors'] += 1
            return 0

    async def expire(self, key: str, ttl: int) -> bool:
        await self.ensure_connection()
        
        try:
            result = await self._client.expire(key, ttl)
            self._stats['expires'] += 1
            return result
            
        except Exception as e:
            logger.error(f"Error setting expiry for {key}: {e}")
            self._stats['errors'] += 1
            return False

    async def ttl(self, key: str) -> int:
        await self.ensure_connection()
        
        try:
            result = await self._client.ttl(key)
            self._stats['ttl'] += 1
            return result
            
        except Exception as e:
            logger.error(f"Error getting TTL for {key}: {e}")
            self._stats['errors'] += 1
            return -2

    async def hset(
        self,
        key: str,
        field: str,
        value: Any,
        serialize: bool = True
    ) -> int:
        await self.ensure_connection()
        
        try:
            if serialize:
                value = self._serialize(value)
            
            result = await self._client.hset(key, field, value)
            self._stats['hsets'] += 1
            
            if key in self._key_cache:
                del self._key_cache[key]
            
            return result
            
        except Exception as e:
            logger.error(f"Error setting hash field {key}:{field}: {e}")
            self._stats['errors'] += 1
            return 0

    async def hget(
        self,
        key: str,
        field: str,
        deserialize: bool = True
    ) -> Optional[Any]:
        await self.ensure_connection()
        
        try:
            value = await self._client.hget(key, field)
            
            if value is None:
                return None
            
            if deserialize:
                value = self._deserialize(value)
            
            self._stats['hgets'] += 1
            return value
            
        except Exception as e:
            logger.error(f"Error getting hash field {key}:{field}: {e}")
            self._stats['errors'] += 1
            return None

    async def hgetall(
        self,
        key: str,
        deserialize: bool = True
    ) -> Dict[str, Any]:
        await self.ensure_connection()
        
        try:
            result = await self._client.hgetall(key)
            
            if deserialize and result:
                result = {k: self._deserialize(v) for k, v in result.items()}
            
            self._stats['hgetalls'] += 1
            return result
            
        except Exception as e:
            logger.error(f"Error getting hash {key}: {e}")
            self._stats['errors'] += 1
            return {}

    async def hdel(self, key: str, *fields: str) -> int:
        await self.ensure_connection()
        
        try:
            result = await self._client.hdel(key, *fields)
            self._stats['hdels'] += 1
            
            if key in self._key_cache:
                del self._key_cache[key]
            
            return result
            
        except Exception as e:
            logger.error(f"Error deleting hash fields {key}: {e}")
            self._stats['errors'] += 1
            return 0

    async def lpush(self, key: str, *values: Any, serialize: bool = True) -> int:
        await self.ensure_connection()
        
        try:
            if serialize:
                values = [self._serialize(v) for v in values]
            
            result = await self._client.lpush(key, *values)
            self._stats['lpushs'] += 1
            
            if key in self._key_cache:
                del self._key_cache[key]
            
            return result
            
        except Exception as e:
            logger.error(f"Error pushing to list {key}: {e}")
            self._stats['errors'] += 1
            return 0

    async def rpush(self, key: str, *values: Any, serialize: bool = True) -> int:
        await self.ensure_connection()
        
        try:
            if serialize:
                values = [self._serialize(v) for v in values]
            
            result = await self._client.rpush(key, *values)
            self._stats['rpushs'] += 1
            
            if key in self._key_cache:
                del self._key_cache[key]
            
            return result
            
        except Exception as e:
            logger.error(f"Error pushing to list {key}: {e}")
            self._stats['errors'] += 1
            return 0

    async def lpop(self, key: str, deserialize: bool = True) -> Optional[Any]:
        await self.ensure_connection()
        
        try:
            value = await self._client.lpop(key)
            
            if value is None:
                return None
            
            if deserialize:
                value = self._deserialize(value)
            
            self._stats['lpops'] += 1
            return value
            
        except Exception as e:
            logger.error(f"Error popping from list {key}: {e}")
            self._stats['errors'] += 1
            return None

    async def rpop(self, key: str, deserialize: bool = True) -> Optional[Any]:
        await self.ensure_connection()
        
        try:
            value = await self._client.rpop(key)
            
            if value is None:
                return None
            
            if deserialize:
                value = self._deserialize(value)
            
            self._stats['rpops'] += 1
            return value
            
        except Exception as e:
            logger.error(f"Error popping from list {key}: {e}")
            self._stats['errors'] += 1
            return None

    async def lrange(
        self,
        key: str,
        start: int = 0,
        end: int = -1,
        deserialize: bool = True
    ) -> List[Any]:
        await self.ensure_connection()
        
        try:
            values = await self._client.lrange(key, start, end)
            
            if deserialize and values:
                values = [self._deserialize(v) for v in values]
            
            self._stats['lranges'] += 1
            return values
            
        except Exception as e:
            logger.error(f"Error getting range from list {key}: {e}")
            self._stats['errors'] += 1
            return []

    async def sadd(self, key: str, *values: Any, serialize: bool = True) -> int:
        await self.ensure_connection()
        
        try:
            if serialize:
                values = [self._serialize(v) for v in values]
            
            result = await self._client.sadd(key, *values)
            self._stats['sadds'] += 1
            
            if key in self._key_cache:
                del self._key_cache[key]
            
            return result
            
        except Exception as e:
            logger.error(f"Error adding to set {key}: {e}")
            self._stats['errors'] += 1
            return 0

    async def srem(self, key: str, *values: Any, serialize: bool = True) -> int:
        await self.ensure_connection()
        
        try:
            if serialize:
                values = [self._serialize(v) for v in values]
            
            result = await self._client.srem(key, *values)
            self._stats['srems'] += 1
            
            if key in self._key_cache:
                del self._key_cache[key]
            
            return result
            
        except Exception as e:
            logger.error(f"Error removing from set {key}: {e}")
            self._stats['errors'] += 1
            return 0

    async def smembers(self, key: str, deserialize: bool = True) -> Set[Any]:
        await self.ensure_connection()
        
        try:
            members = await self._client.smembers(key)
            
            if deserialize and members:
                members = {self._deserialize(v) for v in members}
            
            self._stats['smembers'] += 1
            return members
            
        except Exception as e:
            logger.error(f"Error getting set members {key}: {e}")
            self._stats['errors'] += 1
            return set()

    async def zadd(
        self,
        key: str,
        mapping: Dict[Any, float],
        serialize: bool = True,
        nx: bool = False,
        xx: bool = False,
        ch: bool = False,
        incr: bool = False
    ) -> int:
        await self.ensure_connection()
        
        try:
            if serialize:
                mapping = {self._serialize(k): v for k, v in mapping.items()}
            
            result = await self._client.zadd(key, mapping, nx=nx, xx=xx, ch=ch, incr=incr)
            self._stats['zadds'] += 1
            
            if key in self._key_cache:
                del self._key_cache[key]
            
            return result
            
        except Exception as e:
            logger.error(f"Error adding to sorted set {key}: {e}")
            self._stats['errors'] += 1
            return 0

    async def zrange(
        self,
        key: str,
        start: int = 0,
        end: int = -1,
        withscores: bool = False,
        deserialize: bool = True
    ) -> Union[List[Any], List[Tuple[Any, float]]]:
        await self.ensure_connection()
        
        try:
            result = await self._client.zrange(key, start, end, withscores=withscores)
            
            if deserialize and result:
                if withscores:
                    result = [(self._deserialize(k), v) for k, v in result]
                else:
                    result = [self._deserialize(v) for v in result]
            
            self._stats['zranges'] += 1
            return result
            
        except Exception as e:
            logger.error(f"Error getting range from sorted set {key}: {e}")
            self._stats['errors'] += 1
            return [] if not withscores else []

    async def zrem(self, key: str, *values: Any, serialize: bool = True) -> int:
        await self.ensure_connection()
        
        try:
            if serialize:
                values = [self._serialize(v) for v in values]
            
            result = await self._client.zrem(key, *values)
            self._stats['zrems'] += 1
            
            if key in self._key_cache:
                del self._key_cache[key]
            
            return result
            
        except Exception as e:
            logger.error(f"Error removing from sorted set {key}: {e}")
            self._stats['errors'] += 1
            return 0

    async def publish(self, channel: str, message: Any, serialize: bool = True) -> int:
        await self.ensure_connection()
        
        try:
            if serialize:
                message = self._serialize(message)
            
            result = await self._client.publish(channel, message)
            self._stats['publishes'] += 1
            return result
            
        except Exception as e:
            logger.error(f"Error publishing to channel {channel}: {e}")
            self._stats['errors'] += 1
            return 0

    async def subscribe(self, channel: str, callback: Callable) -> None:
        await self.ensure_connection()
        
        self._subscriptions[channel].append(callback)
        
        if self._pubsub:
            await self._pubsub.subscribe(channel)
            logger.info(f"Subscribed to channel: {channel}")

    async def unsubscribe(self, channel: str) -> None:
        if channel in self._subscriptions:
            del self._subscriptions[channel]
        
        if self._pubsub:
            await self._pubsub.unsubscribe(channel)
            logger.info(f"Unsubscribed from channel: {channel}")

    async def _pubsub_loop(self) -> None:
        while self._running:
            try:
                message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                
                if message and message.get("type") == "message":
                    channel = message["channel"].decode() if isinstance(message["channel"], bytes) else message["channel"]
                    data = message["data"]
                    
                    if channel in self._subscriptions:
                        try:
                            deserialized = self._deserialize(data)
                            for callback in self._subscriptions[channel]:
                                try:
                                    if asyncio.iscoroutinefunction(callback):
                                        await callback(deserialized)
                                    else:
                                        callback(deserialized)
                                except Exception as e:
                                    logger.error(f"Error in callback for {channel}: {e}")
                        except Exception as e:
                            logger.error(f"Error processing pubsub message: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Pubsub loop error: {e}")
                await asyncio.sleep(1)

    async def _health_check_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                
                try:
                    await self._client.ping()
                    self._stats['health_checks'] += 1
                except Exception:
                    logger.warning("Health check failed, attempting reconnect")
                    await self.reconnect()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")

    async def get_key_info(self, key: str) -> Optional[RedisKeyInfo]:
        await self.ensure_connection()
        
        try:
            key_type = await self._client.type(key)
            key_type = key_type.decode() if isinstance(key_type, bytes) else key_type
            
            ttl = await self._client.ttl(key)
            
            if key_type == "string":
                size = len(await self._client.get(key) or b"")
            elif key_type == "hash":
                size = await self._client.hlen(key)
            elif key_type == "list":
                size = await self._client.llen(key)
            elif key_type == "set":
                size = await self._client.scard(key)
            elif key_type == "zset":
                size = await self._client.zcard(key)
            else:
                size = 0
            
            return RedisKeyInfo(
                key=key,
                type=key_type,
                ttl=ttl,
                size=size,
                last_access=time.time(),
                created_at=time.time(),
                expires_at=time.time() + ttl if ttl > 0 else None
            )
            
        except Exception as e:
            logger.error(f"Error getting key info for {key}: {e}")
            return None

    async def get_keys(self, pattern: str = "*", count: int = 1000) -> List[str]:
        await self.ensure_connection()
        
        try:
            keys = []
            cursor = 0
            
            while True:
                cursor, results = await self._client.scan(cursor, match=pattern, count=count)
                keys.extend(results)
                if cursor == 0:
                    break
            
            self._stats['scan'] += 1
            return keys
            
        except Exception as e:
            logger.error(f"Error scanning keys: {e}")
            self._stats['errors'] += 1
            return []

    async def get_keys_info(self, pattern: str = "*", limit: int = 1000) -> List[RedisKeyInfo]:
        keys = await self.get_keys(pattern, limit)
        
        key_infos = []
        for key in keys[:limit]:
            info = await self.get_key_info(key)
            if info:
                key_infos.append(info)
        
        return key_infos

    async def get_memory_usage(self, key: str) -> int:
        await self.ensure_connection()
        
        try:
            result = await self._client.memory_usage(key)
            self._stats['memory_usage'] += 1
            return result or 0
            
        except Exception as e:
            logger.error(f"Error getting memory usage for {key}: {e}")
            return 0

    async def get_info(self) -> Dict[str, Any]:
        await self.ensure_connection()
        
        try:
            info = await self._client.info()
            self._stats['info'] += 1
            return info
            
        except Exception as e:
            logger.error(f"Error getting Redis info: {e}")
            return {}

    async def get_stats(self) -> Dict[str, Any]:
        info = await self.get_info()
        
        return {
            "connected": self._connected,
            "running": self._running,
            "stats": dict(self._stats),
            "cache_size": len(self._key_cache),
            "subscriptions": len(self._subscriptions),
            "info": {
                "redis_version": info.get("redis_version"),
                "uptime": info.get("uptime_in_seconds"),
                "connected_clients": info.get("connected_clients"),
                "used_memory": info.get("used_memory"),
                "used_memory_rss": info.get("used_memory_rss"),
                "total_connections_received": info.get("total_connections_received"),
                "total_commands_processed": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits"),
                "keyspace_misses": info.get("keyspace_misses")
            }
        }

    async def flush_db(self) -> bool:
        await self.ensure_connection()
        
        try:
            await self._client.flushdb()
            self._key_cache.clear()
            self._stats['flush'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Error flushing database: {e}")
            return False

    async def flush_all(self) -> bool:
        await self.ensure_connection()
        
        try:
            await self._client.flushall()
            self._key_cache.clear()
            self._stats['flush_all'] += 1
            return True
            
        except Exception as e:
            logger.error(f"Error flushing all databases: {e}")
            return False

    async def acquire_lock(
        self,
        lock_name: str,
        timeout: float = 10.0,
        blocking: bool = True,
        blocking_timeout: float = 5.0
    ) -> Optional[Any]:
        if not REDIS_LOCK_AVAILABLE:
            raise ImportError("redis_lock not available")
        
        await self.ensure_connection()
        
        try:
            lock = redis_lock.Lock(
                self._client,
                lock_name,
                timeout=timeout,
                blocking=blocking,
                blocking_timeout=blocking_timeout
            )
            acquired = await lock.acquire()
            
            if acquired:
                self._stats['locks_acquired'] += 1
                return lock
            return None
            
        except Exception as e:
            logger.error(f"Error acquiring lock {lock_name}: {e}")
            return None

    async def release_lock(self, lock: Any) -> bool:
        try:
            result = await lock.release()
            self._stats['locks_released'] += 1
            return result
            
        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
            return False

    def _serialize(self, value: Any) -> Union[str, bytes]:
        if isinstance(value, str):
            return value
        elif isinstance(value, (int, float, bool, Decimal)):
            return str(value)
        elif isinstance(value, (dict, list, set, tuple)):
            return json.dumps(value, default=self._json_default)
        else:
            return pickle.dumps(value)

    def _deserialize(self, value: Union[str, bytes]) -> Any:
        if isinstance(value, bytes):
            try:
                return pickle.loads(value)
            except:
                try:
                    return json.loads(value.decode('utf-8'))
                except:
                    return value.decode('utf-8')
        elif isinstance(value, str):
            try:
                return json.loads(value)
            except:
                return value
        else:
            return value

    def _json_default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        return str(obj)

    async def pipeline_start(self) -> None:
        self._pipeline = self._client.pipeline()

    async def pipeline_execute(self) -> List[Any]:
        if self._pipeline:
            try:
                result = await self._pipeline.execute()
                self._pipeline = None
                return result
            except Exception as e:
                self._pipeline = None
                logger.error(f"Pipeline execution error: {e}")
                raise

    async def pipeline_reset(self) -> None:
        if self._pipeline:
            await self._pipeline.reset()
            self._pipeline = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        asyncio.run(self.disconnect())

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


__all__ = [
    "RedisDataType",
    "RedisPersistence",
    "RedisEviction",
    "RedisConfig",
    "RedisKeyInfo",
    "RedisStreamMessage",
    "RedisGeoLocation",
    "RedisDataManager"
]
