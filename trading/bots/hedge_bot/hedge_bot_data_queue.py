# trading/bots/hedge_bot/hedge_bot_data_queue.py

import asyncio
import logging
import time
import json
import uuid
import heapq
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable, Generic, TypeVar
from decimal import Decimal
from collections import defaultdict, deque
import pickle
import zlib
import hashlib

try:
    import redis
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import aio_pika
    RABBITMQ_AVAILABLE = True
except ImportError:
    RABBITMQ_AVAILABLE = False

try:
    import aiokafka
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

logger = logging.getLogger(__name__)

T = TypeVar('T')


class QueueType(str, Enum):
    FIFO = "fifo"
    LIFO = "lifo"
    PRIORITY = "priority"
    DELAYED = "delayed"
    SCHEDULED = "scheduled"
    CIRCULAR = "circular"
    BATCH = "batch"
    DEDUPLICATED = "deduplicated"
    PERSISTENT = "persistent"
    TRANSIENT = "transient"
    RELIABLE = "reliable"
    ORDERED = "ordered"
    PARTITIONED = "partitioned"


class QueuePriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BACKGROUND = "background"


class QueueMode(str, Enum):
    MEMORY = "memory"
    REDIS = "redis"
    RABBITMQ = "rabbitmq"
    KAFKA = "kafka"
    HYBRID = "hybrid"


@dataclass
class QueueItem(Generic[T]):
    id: str
    data: T
    priority: QueuePriority = QueuePriority.MEDIUM
    timestamp: float = field(default_factory=time.time)
    scheduled_time: Optional[float] = None
    expires_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    retry_delay: float = 5.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "pending"


@dataclass
class QueueStats:
    name: str
    size: int
    pending: int
    processing: int
    completed: int
    failed: int
    delayed: int
    scheduled: int
    total_processed: int
    total_failed: int
    avg_processing_time: float
    max_processing_time: float
    min_processing_time: float
    throughput: float
    created_at: float
    updated_at: float


class DataQueueManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._queues: Dict[str, Any] = {}
        self._queue_stats: Dict[str, QueueStats] = {}
        self._queue_items: Dict[str, Dict[str, QueueItem]] = {}
        self._priority_queues: Dict[str, List[Tuple[int, str, QueueItem]]] = defaultdict(list)
        self._delayed_queues: Dict[str, List[QueueItem]] = defaultdict(list)
        self._scheduled_queues: Dict[str, List[Tuple[float, str, QueueItem]]] = defaultdict(list)
        self._processing_items: Dict[str, Set[str]] = defaultdict(set)
        self._completed_items: Dict[str, Set[str]] = defaultdict(set)
        self._failed_items: Dict[str, Set[str]] = defaultdict(set)
        self._handlers: Dict[str, Callable] = {}
        self._error_handlers: Dict[str, Callable] = {}
        self._middleware: List[Callable] = []
        self._listeners: List[Callable] = []
        self._worker_tasks: Dict[str, asyncio.Task] = {}
        self._monitor_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._mode = QueueMode.MEMORY
        self._redis_client: Optional[Any] = None
        self._rabbitmq_client: Optional[Any] = None
        self._kafka_client: Optional[Any] = None
        
        self._initialize_backends()
        self._initialize_default_handlers()

    def _initialize_backends(self) -> None:
        if self.config.get("mode") == QueueMode.REDIS and REDIS_AVAILABLE:
            self._mode = QueueMode.REDIS
            self._init_redis()
        elif self.config.get("mode") == QueueMode.RABBITMQ and RABBITMQ_AVAILABLE:
            self._mode = QueueMode.RABBITMQ
            self._init_rabbitmq()
        elif self.config.get("mode") == QueueMode.KAFKA and KAFKA_AVAILABLE:
            self._mode = QueueMode.KAFKA
            self._init_kafka()
        elif self.config.get("mode") == QueueMode.HYBRID:
            self._mode = QueueMode.HYBRID
            if REDIS_AVAILABLE:
                self._init_redis()
            if RABBITMQ_AVAILABLE:
                self._init_rabbitmq()
            if KAFKA_AVAILABLE:
                self._init_kafka()

    def _init_redis(self) -> None:
        try:
            redis_config = self.config.get("redis", {})
            self._redis_client = aioredis.from_url(
                redis_config.get("url", "redis://localhost:6379/0"),
                decode_responses=True,
                max_connections=redis_config.get("max_connections", 50)
            )
            logger.info("Redis backend initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            self._mode = QueueMode.MEMORY

    def _init_rabbitmq(self) -> None:
        try:
            rabbitmq_config = self.config.get("rabbitmq", {})
            self._rabbitmq_client = aio_pika.connect_robust(
                rabbitmq_config.get("url", "amqp://guest:guest@localhost:5672/")
            )
            logger.info("RabbitMQ backend initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RabbitMQ: {e}")
            self._mode = QueueMode.MEMORY

    def _init_kafka(self) -> None:
        try:
            kafka_config = self.config.get("kafka", {})
            self._kafka_client = aiokafka.AIOKafkaProducer(
                bootstrap_servers=kafka_config.get("servers", "localhost:9092"),
                enable_idempotence=True
            )
            logger.info("Kafka backend initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka: {e}")
            self._mode = QueueMode.MEMORY

    def _initialize_default_handlers(self) -> None:
        self.register_handler("default", self._default_handler)

    def register_handler(self, queue_name: str, handler: Callable) -> None:
        self._handlers[queue_name] = handler
        logger.info(f"Registered handler for queue: {queue_name}")

    def register_error_handler(self, queue_name: str, handler: Callable) -> None:
        self._error_handlers[queue_name] = handler
        logger.info(f"Registered error handler for queue: {queue_name}")

    def register_middleware(self, middleware: Callable) -> None:
        self._middleware.append(middleware)

    def register_listener(self, listener: Callable) -> None:
        self._listeners.append(listener)

    async def create_queue(
        self,
        name: str,
        queue_type: QueueType = QueueType.FIFO,
        max_size: int = 10000,
        ttl: int = 3600,
        mode: Optional[QueueMode] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        async with self._lock:
            if name in self._queues:
                raise ValueError(f"Queue already exists: {name}")
            
            if mode is None:
                mode = self._mode
            
            queue_config = {
                "type": queue_type,
                "max_size": max_size,
                "ttl": ttl,
                "mode": mode,
                "metadata": metadata or {},
                "created_at": time.time()
            }
            
            self._queues[name] = queue_config
            self._queue_items[name] = {}
            self._queue_stats[name] = QueueStats(
                name=name,
                size=0,
                pending=0,
                processing=0,
                completed=0,
                failed=0,
                delayed=0,
                scheduled=0,
                total_processed=0,
                total_failed=0,
                avg_processing_time=0,
                max_processing_time=0,
                min_processing_time=0,
                throughput=0,
                created_at=time.time(),
                updated_at=time.time()
            )
            
            if mode != QueueMode.MEMORY:
                await self._create_remote_queue(name, queue_config)
            
            logger.info(f"Queue created: {name}")

    async def _create_remote_queue(self, name: str, config: Dict[str, Any]) -> None:
        if self._mode in [QueueMode.REDIS, QueueMode.HYBRID] and self._redis_client:
            await self._redis_client.sadd("queues", name)
            await self._redis_client.hset(f"queue:{name}:config", mapping=config)
        
        if self._mode in [QueueMode.RABBITMQ, QueueMode.HYBRID] and self._rabbitmq_client:
            connection = await self._rabbitmq_client
            channel = await connection.channel()
            await channel.declare_queue(name, durable=True)
            await channel.close()

        if self._mode in [QueueMode.KAFKA, QueueMode.HYBRID] and self._kafka_client:
            # Kafka topic creation is typically automatic
            pass

    async def push(
        self,
        queue_name: str,
        data: Any,
        priority: QueuePriority = QueuePriority.MEDIUM,
        scheduled_time: Optional[float] = None,
        expires_at: Optional[float] = None,
        max_retries: int = 3,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        async with self._lock:
            if queue_name not in self._queues:
                raise ValueError(f"Queue not found: {queue_name}")
            
            queue = self._queues[queue_name]
            
            if queue["max_size"] > 0 and len(self._queue_items[queue_name]) >= queue["max_size"]:
                raise ValueError(f"Queue {queue_name} is full")
            
            item_id = str(uuid.uuid4())
            
            item = QueueItem(
                id=item_id,
                data=data,
                priority=priority,
                scheduled_time=scheduled_time,
                expires_at=expires_at,
                max_retries=max_retries,
                metadata=metadata or {},
                timestamp=time.time()
            )
            
            self._queue_items[queue_name][item_id] = item
            self._queue_stats[queue_name].size += 1
            
            if scheduled_time and scheduled_time > time.time():
                self._scheduled_queues[queue_name].append((scheduled_time, item_id, item))
                self._queue_stats[queue_name].scheduled += 1
            elif expires_at and expires_at <= time.time():
                self._failed_items[queue_name].add(item_id)
                self._queue_stats[queue_name].failed += 1
                logger.warning(f"Item {item_id} expired before processing")
            else:
                await self._add_to_queue(queue_name, item)
            
            if queue["mode"] != QueueMode.MEMORY:
                await self._push_remote(queue_name, item)
            
            await self._notify_listeners("push", queue_name, item)
            
            return item_id

    async def _add_to_queue(self, queue_name: str, item: QueueItem) -> None:
        queue_type = self._queues[queue_name]["type"]
        
        if queue_type == QueueType.FIFO:
            # Already in queue_items dict
            pass
        elif queue_type == QueueType.LIFO:
            # Will be handled in pop
            pass
        elif queue_type == QueueType.PRIORITY:
            priority_order = {
                QueuePriority.CRITICAL: 0,
                QueuePriority.HIGH: 1,
                QueuePriority.MEDIUM: 2,
                QueuePriority.LOW: 3,
                QueuePriority.BACKGROUND: 4
            }
            heapq.heappush(
                self._priority_queues[queue_name],
                (priority_order[item.priority], item.timestamp, item.id, item)
            )
        elif queue_type == QueueType.DELAYED:
            if item.scheduled_time:
                self._delayed_queues[queue_name].append(item)
        elif queue_type == QueueType.SCHEDULED:
            if item.scheduled_time:
                heapq.heappush(
                    self._scheduled_queues[queue_name],
                    (item.scheduled_time, item.id, item)
                )
        
        self._queue_stats[queue_name].pending += 1

    async def _push_remote(self, queue_name: str, item: QueueItem) -> None:
        try:
            data = pickle.dumps(item)
            compressed = zlib.compress(data)
            encoded = base64.b64encode(compressed).decode('utf-8')
            
            if self._mode in [QueueMode.REDIS, QueueMode.HYBRID] and self._redis_client:
                await self._redis_client.rpush(f"queue:{queue_name}:items", encoded)
                await self._redis_client.sadd(f"queue:{queue_name}:pending", item.id)
            
            if self._mode in [QueueMode.RABBITMQ, QueueMode.HYBRID] and self._rabbitmq_client:
                connection = await self._rabbitmq_client
                channel = await connection.channel()
                await channel.default_exchange.publish(
                    aio_pika.Message(
                        body=encoded.encode(),
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                    ),
                    routing_key=queue_name
                )
                await channel.close()
            
            if self._mode in [QueueMode.KAFKA, QueueMode.HYBRID] and self._kafka_client:
                await self._kafka_client.send_and_wait(
                    queue_name,
                    value=encoded.encode()
                )
                
        except Exception as e:
            logger.error(f"Failed to push to remote queue: {e}")

    async def pop(
        self,
        queue_name: str,
        timeout: float = 0,
        batch_size: int = 1
    ) -> Optional[Union[QueueItem, List[QueueItem]]]:
        async with self._lock:
            if queue_name not in self._queues:
                raise ValueError(f"Queue not found: {queue_name}")
            
            if self._mode != QueueMode.MEMORY:
                remote_items = await self._pop_remote(queue_name, batch_size)
                if remote_items:
                    return remote_items if batch_size > 1 else remote_items[0]
            
            queue_type = self._queues[queue_name]["type"]
            items = []
            
            if queue_type == QueueType.FIFO:
                items = await self._pop_fifo(queue_name, batch_size)
            elif queue_type == QueueType.LIFO:
                items = await self._pop_lifo(queue_name, batch_size)
            elif queue_type == QueueType.PRIORITY:
                items = await self._pop_priority(queue_name, batch_size)
            elif queue_type == QueueType.DELAYED:
                items = await self._pop_delayed(queue_name, batch_size)
            elif queue_type == QueueType.SCHEDULED:
                items = await self._pop_scheduled(queue_name, batch_size)
            elif queue_type == QueueType.CIRCULAR:
                items = await self._pop_circular(queue_name, batch_size)
            elif queue_type == QueueType.BATCH:
                items = await self._pop_batch(queue_name, batch_size)
            elif queue_type == QueueType.DEDUPLICATED:
                items = await self._pop_deduplicated(queue_name, batch_size)
            else:
                items = await self._pop_fifo(queue_name, batch_size)
            
            if items:
                for item in items:
                    item.retry_count += 1
                    self._processing_items[queue_name].add(item.id)
                    self._queue_stats[queue_name].pending -= 1
                    self._queue_stats[queue_name].processing += 1
                
                await self._notify_listeners("pop", queue_name, items)
                
                if self._mode != QueueMode.MEMORY:
                    await self._ack_remote(queue_name, items)
                
                return items if batch_size > 1 else items[0]
            
            if timeout > 0:
                await asyncio.sleep(timeout)
                return await self.pop(queue_name, 0, batch_size)
            
            return None

    async def _pop_fifo(self, queue_name: str, batch_size: int) -> List[QueueItem]:
        items = []
        for item_id in list(self._queue_items[queue_name].keys()):
            if len(items) >= batch_size:
                break
            item = self._queue_items[queue_name].get(item_id)
            if item and item_id not in self._processing_items[queue_name]:
                items.append(item)
                del self._queue_items[queue_name][item_id]
        return items

    async def _pop_lifo(self, queue_name: str, batch_size: int) -> List[QueueItem]:
        items = []
        for item_id in reversed(list(self._queue_items[queue_name].keys())):
            if len(items) >= batch_size:
                break
            item = self._queue_items[queue_name].get(item_id)
            if item and item_id not in self._processing_items[queue_name]:
                items.append(item)
                del self._queue_items[queue_name][item_id]
        return items

    async def _pop_priority(self, queue_name: str, batch_size: int) -> List[QueueItem]:
        items = []
        queue = self._priority_queues[queue_name]
        while queue and len(items) < batch_size:
            priority, timestamp, item_id, item = heapq.heappop(queue)
            if item_id not in self._processing_items[queue_name]:
                items.append(item)
                del self._queue_items[queue_name][item_id]
        return items

    async def _pop_delayed(self, queue_name: str, batch_size: int) -> List[QueueItem]:
        items = []
        now = time.time()
        delayed = self._delayed_queues[queue_name]
        
        for item in delayed[:]:
            if len(items) >= batch_size:
                break
            if item.scheduled_time and item.scheduled_time <= now:
                items.append(item)
                delayed.remove(item)
                del self._queue_items[queue_name][item.id]
        
        return items

    async def _pop_scheduled(self, queue_name: str, batch_size: int) -> List[QueueItem]:
        items = []
        now = time.time()
        queue = self._scheduled_queues[queue_name]
        
        while queue and len(items) < batch_size:
            scheduled_time, item_id, item = heapq.heappop(queue)
            if scheduled_time <= now:
                if item_id not in self._processing_items[queue_name]:
                    items.append(item)
                    del self._queue_items[queue_name][item_id]
            else:
                heapq.heappush(queue, (scheduled_time, item_id, item))
                break
        
        return items

    async def _pop_circular(self, queue_name: str, batch_size: int) -> List[QueueItem]:
        items = []
        item_ids = list(self._queue_items[queue_name].keys())
        
        if not item_ids:
            return items
        
        start_idx = self._queues[queue_name].get("circular_index", 0)
        
        for i in range(batch_size):
            idx = (start_idx + i) % len(item_ids)
            item_id = item_ids[idx]
            item = self._queue_items[queue_name].get(item_id)
            if item and item_id not in self._processing_items[queue_name]:
                items.append(item)
        
        self._queues[queue_name]["circular_index"] = (start_idx + batch_size) % len(item_ids)
        return items

    async def _pop_batch(self, queue_name: str, batch_size: int) -> List[QueueItem]:
        return await self._pop_fifo(queue_name, batch_size)

    async def _pop_deduplicated(self, queue_name: str, batch_size: int) -> List[QueueItem]:
        items = []
        seen_hashes = set()
        
        for item_id in list(self._queue_items[queue_name].keys()):
            if len(items) >= batch_size:
                break
            
            item = self._queue_items[queue_name].get(item_id)
            if not item or item_id in self._processing_items[queue_name]:
                continue
            
            item_hash = hashlib.md5(pickle.dumps(item.data)).hexdigest()
            if item_hash in seen_hashes:
                continue
            
            seen_hashes.add(item_hash)
            items.append(item)
            del self._queue_items[queue_name][item_id]
        
        return items

    async def _pop_remote(self, queue_name: str, batch_size: int) -> List[QueueItem]:
        items = []
        
        try:
            if self._mode in [QueueMode.REDIS, QueueMode.HYBRID] and self._redis_client:
                encoded_items = await self._redis_client.lpop(f"queue:{queue_name}:items", count=batch_size)
                if encoded_items:
                    for encoded in encoded_items:
                        compressed = base64.b64decode(encoded.encode('utf-8'))
                        data = zlib.decompress(compressed)
                        item = pickle.loads(data)
                        items.append(item)
                        await self._redis_client.srem(f"queue:{queue_name}:pending", item.id)
            
            if self._mode in [QueueMode.RABBITMQ, QueueMode.HYBRID] and self._rabbitmq_client:
                connection = await self._rabbitmq_client
                channel = await connection.channel()
                for _ in range(batch_size):
                    message = await channel.basic_get(queue_name)
                    if message:
                        compressed = base64.b64decode(message.body.decode('utf-8'))
                        data = zlib.decompress(compressed)
                        item = pickle.loads(data)
                        items.append(item)
                        await message.ack()
                await channel.close()
            
            if self._mode in [QueueMode.KAFKA, QueueMode.HYBRID] and self._kafka_client:
                # Kafka consumer would be needed for this
                pass
                
        except Exception as e:
            logger.error(f"Failed to pop from remote queue: {e}")
        
        return items

    async def _ack_remote(self, queue_name: str, items: List[QueueItem]) -> None:
        try:
            if self._mode in [QueueMode.REDIS, QueueMode.HYBRID] and self._redis_client:
                for item in items:
                    await self._redis_client.srem(f"queue:{queue_name}:processing", item.id)
            
            if self._mode in [QueueMode.RABBITMQ, QueueMode.HYBRID] and self._rabbitmq_client:
                # ACK handled during pop
                pass
                
        except Exception as e:
            logger.error(f"Failed to ack remote items: {e}")

    async def complete(self, queue_name: str, item_id: str) -> bool:
        async with self._lock:
            if queue_name not in self._queues:
                return False
            
            if item_id in self._processing_items[queue_name]:
                self._processing_items[queue_name].remove(item_id)
                self._completed_items[queue_name].add(item_id)
                self._queue_stats[queue_name].processing -= 1
                self._queue_stats[queue_name].completed += 1
                self._queue_stats[queue_name].total_processed += 1
                
                if self._mode != QueueMode.MEMORY:
                    await self._complete_remote(queue_name, item_id)
                
                await self._notify_listeners("complete", queue_name, item_id)
                return True
            
            return False

    async def _complete_remote(self, queue_name: str, item_id: str) -> None:
        try:
            if self._mode in [QueueMode.REDIS, QueueMode.HYBRID] and self._redis_client:
                await self._redis_client.srem(f"queue:{queue_name}:processing", item_id)
                await self._redis_client.sadd(f"queue:{queue_name}:completed", item_id)
                
        except Exception as e:
            logger.error(f"Failed to complete remote item: {e}")

    async def fail(self, queue_name: str, item_id: str, error: Optional[Exception] = None) -> bool:
        async with self._lock:
            if queue_name not in self._queues:
                return False
            
            if item_id in self._processing_items[queue_name]:
                self._processing_items[queue_name].remove(item_id)
                self._queue_stats[queue_name].processing -= 1
                
                item = self._queue_items[queue_name].get(item_id)
                
                if item and item.retry_count < item.max_retries:
                    if item.retry_delay > 0:
                        item.scheduled_time = time.time() + item.retry_delay
                        self._delayed_queues[queue_name].append(item)
                        self._queue_stats[queue_name].delayed += 1
                    else:
                        self._queue_items[queue_name][item_id] = item
                        self._queue_stats[queue_name].pending += 1
                        await self._add_to_queue(queue_name, item)
                else:
                    self._failed_items[queue_name].add(item_id)
                    self._queue_stats[queue_name].failed += 1
                    self._queue_stats[queue_name].total_failed += 1
                    
                    if error and queue_name in self._error_handlers:
                        await self._error_handlers[queue_name](item, error)
                
                await self._notify_listeners("fail", queue_name, item_id, error)
                return True
            
            return False

    async def retry(self, queue_name: str, item_id: str) -> bool:
        async with self._lock:
            if queue_name not in self._queues:
                return False
            
            if item_id in self._failed_items[queue_name]:
                self._failed_items[queue_name].remove(item_id)
                item = self._queue_items[queue_name].get(item_id)
                
                if item:
                    item.retry_count = 0
                    self._queue_items[queue_name][item_id] = item
                    self._queue_stats[queue_name].pending += 1
                    await self._add_to_queue(queue_name, item)
                    
                    if self._mode != QueueMode.MEMORY:
                        await self._retry_remote(queue_name, item)
                    
                    return True
            
            return False

    async def _retry_remote(self, queue_name: str, item: QueueItem) -> None:
        try:
            if self._mode in [QueueMode.REDIS, QueueMode.HYBRID] and self._redis_client:
                await self._redis_client.srem(f"queue:{queue_name}:failed", item.id)
                
        except Exception as e:
            logger.error(f"Failed to retry remote item: {e}")

    async def process_queue(
        self,
        queue_name: str,
        concurrency: int = 1,
        continuous: bool = True
    ) -> None:
        if queue_name not in self._queues:
            raise ValueError(f"Queue not found: {queue_name}")
        
        if queue_name in self._worker_tasks:
            logger.warning(f"Queue {queue_name} already being processed")
            return
        
        if queue_name not in self._handlers:
            logger.warning(f"No handler registered for queue: {queue_name}")
            return
        
        handler = self._handlers[queue_name]
        
        async def worker(worker_id: int):
            logger.info(f"Worker {worker_id} started for queue: {queue_name}")
            
            while self._running:
                try:
                    items = await self.pop(queue_name, timeout=1, batch_size=concurrency)
                    
                    if not items:
                        if not continuous:
                            break
                        await asyncio.sleep(0.1)
                        continue
                    
                    if not isinstance(items, list):
                        items = [items]
                    
                    for item in items:
                        try:
                            for middleware in self._middleware:
                                await middleware("before", queue_name, item)
                            
                            await handler(item)
                            
                            for middleware in self._middleware:
                                await middleware("after", queue_name, item)
                            
                            await self.complete(queue_name, item.id)
                            
                        except Exception as e:
                            logger.error(f"Error processing item {item.id}: {e}")
                            await self.fail(queue_name, item.id, e)
                            
                except Exception as e:
                    logger.error(f"Worker {worker_id} error: {e}")
                    await asyncio.sleep(1)
            
            logger.info(f"Worker {worker_id} stopped for queue: {queue_name}")
        
        self._worker_tasks[queue_name] = asyncio.gather(
            *[worker(i) for i in range(concurrency)]
        )
        
        self._monitor_tasks[queue_name] = asyncio.create_task(
            self._monitor_queue(queue_name)
        )

    async def _monitor_queue(self, queue_name: str) -> None:
        while self._running:
            try:
                await asyncio.sleep(60)
                await self._update_queue_stats(queue_name)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error for {queue_name}: {e}")

    async def _update_queue_stats(self, queue_name: str) -> None:
        stats = self._queue_stats.get(queue_name)
        if not stats:
            return
        
        stats.updated_at = time.time()
        
        if stats.total_processed > 0:
            stats.avg_processing_time = (stats.avg_processing_time * (stats.total_processed - 1) + 
                                        stats.avg_processing_time) / stats.total_processed
        
        if self._mode != QueueMode.MEMORY:
            await self._update_remote_stats(queue_name)

    async def _update_remote_stats(self, queue_name: str) -> None:
        try:
            if self._mode in [QueueMode.REDIS, QueueMode.HYBRID] and self._redis_client:
                stats = self._queue_stats[queue_name]
                await self._redis_client.hset(f"queue:{queue_name}:stats", {
                    "size": stats.size,
                    "pending": stats.pending,
                    "processing": stats.processing,
                    "completed": stats.completed,
                    "failed": stats.failed,
                    "delayed": stats.delayed,
                    "scheduled": stats.scheduled,
                    "total_processed": stats.total_processed,
                    "total_failed": stats.total_failed,
                    "updated_at": stats.updated_at
                })
                
        except Exception as e:
            logger.error(f"Failed to update remote stats: {e}")

    async def stop_processing(self, queue_name: str) -> None:
        if queue_name in self._worker_tasks:
            self._worker_tasks[queue_name].cancel()
            try:
                await self._worker_tasks[queue_name]
            except asyncio.CancelledError:
                pass
            del self._worker_tasks[queue_name]
        
        if queue_name in self._monitor_tasks:
            self._monitor_tasks[queue_name].cancel()
            try:
                await self._monitor_tasks[queue_name]
            except asyncio.CancelledError:
                pass
            del self._monitor_tasks[queue_name]

    async def delete_queue(self, queue_name: str, force: bool = False) -> bool:
        async with self._lock:
            if queue_name not in self._queues:
                return False
            
            if not force and self._queue_stats[queue_name].processing > 0:
                raise ValueError(f"Queue {queue_name} has items in processing")
            
            await self.stop_processing(queue_name)
            
            del self._queues[queue_name]
            del self._queue_items[queue_name]
            del self._queue_stats[queue_name]
            
            self._priority_queues.pop(queue_name, None)
            self._delayed_queues.pop(queue_name, None)
            self._scheduled_queues.pop(queue_name, None)
            self._processing_items.pop(queue_name, None)
            self._completed_items.pop(queue_name, None)
            self._failed_items.pop(queue_name, None)
            
            if self._mode != QueueMode.MEMORY:
                await self._delete_remote_queue(queue_name)
            
            logger.info(f"Queue deleted: {queue_name}")
            return True

    async def _delete_remote_queue(self, queue_name: str) -> None:
        try:
            if self._mode in [QueueMode.REDIS, QueueMode.HYBRID] and self._redis_client:
                await self._redis_client.srem("queues", queue_name)
                await self._redis_client.delete(f"queue:{queue_name}:config")
                await self._redis_client.delete(f"queue:{queue_name}:items")
                await self._redis_client.delete(f"queue:{queue_name}:pending")
                await self._redis_client.delete(f"queue:{queue_name}:processing")
                await self._redis_client.delete(f"queue:{queue_name}:completed")
                await self._redis_client.delete(f"queue:{queue_name}:failed")
                await self._redis_client.delete(f"queue:{queue_name}:stats")
                
            if self._mode in [QueueMode.RABBITMQ, QueueMode.HYBRID] and self._rabbitmq_client:
                connection = await self._rabbitmq_client
                channel = await connection.channel()
                await channel.queue_delete(queue_name)
                await channel.close()
                
        except Exception as e:
            logger.error(f"Failed to delete remote queue: {e}")

    async def get_queue_stats(self, queue_name: str) -> Optional[QueueStats]:
        if queue_name not in self._queues:
            return None
        
        stats = self._queue_stats[queue_name]
        await self._update_queue_stats(queue_name)
        return stats

    async def get_all_queue_stats(self) -> Dict[str, QueueStats]:
        stats = {}
        for queue_name in self._queues:
            stats[queue_name] = await self.get_queue_stats(queue_name)
        return stats

    async def get_queue_items(
        self,
        queue_name: str,
        status: str = "all",
        limit: int = 100
    ) -> List[QueueItem]:
        if queue_name not in self._queues:
            return []
        
        items = []
        
        if status == "all" or status == "pending":
            items.extend(list(self._queue_items[queue_name].values())[:limit])
        
        if status == "all" or status == "processing":
            for item_id in list(self._processing_items[queue_name])[:limit]:
                item = self._queue_items[queue_name].get(item_id)
                if item:
                    items.append(item)
        
        if status == "all" or status == "completed":
            for item_id in list(self._completed_items[queue_name])[:limit]:
                item = self._queue_items[queue_name].get(item_id)
                if item:
                    items.append(item)
        
        if status == "all" or status == "failed":
            for item_id in list(self._failed_items[queue_name])[:limit]:
                item = self._queue_items[queue_name].get(item_id)
                if item:
                    items.append(item)
        
        return items[:limit]

    async def clear_queue(self, queue_name: str) -> int:
        async with self._lock:
            if queue_name not in self._queues:
                return 0
            
            count = len(self._queue_items[queue_name])
            
            self._queue_items[queue_name].clear()
            self._priority_queues[queue_name].clear()
            self._delayed_queues[queue_name].clear()
            self._scheduled_queues[queue_name].clear()
            
            self._queue_stats[queue_name].size = 0
            self._queue_stats[queue_name].pending = 0
            
            if self._mode != QueueMode.MEMORY:
                await self._clear_remote_queue(queue_name)
            
            return count

    async def _clear_remote_queue(self, queue_name: str) -> None:
        try:
            if self._mode in [QueueMode.REDIS, QueueMode.HYBRID] and self._redis_client:
                await self._redis_client.delete(f"queue:{queue_name}:items")
                await self._redis_client.delete(f"queue:{queue_name}:pending")
                
        except Exception as e:
            logger.error(f"Failed to clear remote queue: {e}")

    async def _notify_listeners(self, event: str, queue_name: str, *args) -> None:
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, queue_name, *args)
                else:
                    listener(event, queue_name, *args)
            except Exception as e:
                logger.error(f"Error in listener: {e}")

    async def _default_handler(self, item: QueueItem) -> None:
        logger.info(f"Processing item: {item.id}")

    async def start(self) -> None:
        self._running = True
        logger.info("Data queue manager started")

    async def shutdown(self) -> None:
        self._running = False
        
        for queue_name in list(self._worker_tasks.keys()):
            await self.stop_processing(queue_name)
        
        if self._redis_client:
            await self._redis_client.close()
        
        if self._rabbitmq_client:
            await self._rabbitmq_client.close()
        
        if self._kafka_client:
            await self._kafka_client.close()
        
        logger.info("Data queue manager shutdown")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "mode": self._mode.value,
            "queues": len(self._queues),
            "total_items": sum(len(items) for items in self._queue_items.values()),
            "processing_items": sum(len(items) for items in self._processing_items.values()),
            "completed_items": sum(len(items) for items in self._completed_items.values()),
            "failed_items": sum(len(items) for items in self._failed_items.values()),
            "workers": len(self._worker_tasks),
            "monitors": len(self._monitor_tasks),
            "handlers": len(self._handlers),
            "middleware": len(self._middleware),
            "listeners": len(self._listeners),
            "running": self._running
        }


__all__ = [
    "QueueType",
    "QueuePriority",
    "QueueMode",
    "QueueItem",
    "QueueStats",
    "DataQueueManager"
]
