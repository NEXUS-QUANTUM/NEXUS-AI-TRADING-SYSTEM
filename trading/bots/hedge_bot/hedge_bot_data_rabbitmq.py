# trading/bots/hedge_bot/hedge_bot_data_rabbitmq.py

import asyncio
import logging
import time
import json
import uuid
import pickle
import zlib
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
    import aio_pika
    from aio_pika import (
        Connection, Channel, Exchange, Queue, Message,
        DeliveryMode, ExchangeType, MessageAck, MessageReject,
        connect_robust, connect
    )
    from aio_pika.abc import (
        AbstractConnection, AbstractChannel, AbstractExchange,
        AbstractQueue, AbstractMessage, AbstractIncomingMessage
    )
    RABBITMQ_AVAILABLE = True
except ImportError:
    RABBITMQ_AVAILABLE = False
    print("aio-pika not installed. Please install: pip install aio-pika")

try:
    import pika
    from pika import BlockingConnection, ConnectionParameters
    from pika.adapters.asyncio_connection import AsyncioConnection
    PIKA_AVAILABLE = True
except ImportError:
    PIKA_AVAILABLE = False

logger = logging.getLogger(__name__)


class ExchangeType(str, Enum):
    DIRECT = "direct"
    FANOUT = "fanout"
    TOPIC = "topic"
    HEADERS = "headers"
    DELAYED = "x-delayed-message"


class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MessageStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    RETRY = "retry"


class DeadLetterPolicy(str, Enum):
    NONE = "none"
    REJECT = "reject"
    RETRY = "retry"
    DLX = "dlx"
    REQUEUE = "requeue"
    DISCARD = "discard"


@dataclass
class RabbitMQConfig:
    host: str = "localhost"
    port: int = 5672
    username: str = "guest"
    password: str = "guest"
    vhost: str = "/"
    ssl: bool = False
    heartbeat: int = 60
    connection_timeout: int = 30
    max_retries: int = 5
    retry_delay: float = 1.0
    prefetch_count: int = 10
    consumer_timeout: int = 300
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExchangeConfig:
    name: str
    exchange_type: ExchangeType = ExchangeType.DIRECT
    durable: bool = True
    auto_delete: bool = False
    internal: bool = False
    arguments: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueueConfig:
    name: str
    durable: bool = True
    exclusive: bool = False
    auto_delete: bool = False
    arguments: Dict[str, Any] = field(default_factory=dict)
    dead_letter_exchange: Optional[str] = None
    dead_letter_routing_key: Optional[str] = None
    max_length: Optional[int] = None
    max_length_bytes: Optional[int] = None
    message_ttl: Optional[int] = None
    expires: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BindingConfig:
    queue_name: str
    exchange_name: str
    routing_key: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Message:
    id: str
    body: Any
    priority: MessagePriority = MessagePriority.NORMAL
    delivery_mode: int = 2
    headers: Dict[str, str] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    expiration: Optional[int] = None
    user_id: Optional[str] = None
    app_id: Optional[str] = None
    content_type: str = "application/json"
    content_encoding: str = "utf-8"
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    status: MessageStatus = MessageStatus.PENDING


@dataclass
class MessageResult:
    message_id: str
    success: bool
    error: Optional[str] = None
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class RabbitMQManager:
    
    def __init__(self, config: Optional[RabbitMQConfig] = None):
        self.config = config or RabbitMQConfig()
        self._lock = asyncio.Lock()
        self._connection: Optional[AbstractConnection] = None
        self._channel: Optional[AbstractChannel] = None
        self._exchanges: Dict[str, AbstractExchange] = {}
        self._queues: Dict[str, AbstractQueue] = {}
        self._bindings: Dict[str, List[BindingConfig]] = defaultdict(list)
        self._consumers: Dict[str, Callable] = {}
        self._consumer_tags: Dict[str, str] = {}
        self._pending_messages: Dict[str, Dict[str, Any]] = {}
        self._message_handlers: Dict[str, Callable] = {}
        self._error_handlers: Dict[str, Callable] = {}
        self._middleware: List[Callable] = []
        self._listeners: List[Callable] = []
        self._running = False
        self._connected = False
        self._reconnecting = False
        self._connection_task: Optional[asyncio.Task] = None
        self._consumer_tasks: Dict[str, asyncio.Task] = {}
        self._stats = defaultdict(int)
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._processor_task: Optional[asyncio.Task] = None
        
        self._initialize_default_handlers()

    def _initialize_default_handlers(self) -> None:
        self.register_handler("default", self._default_message_handler)
        self.register_error_handler("default", self._default_error_handler)

    async def connect(self) -> None:
        async with self._lock:
            if self._connected:
                return
            
            logger.info(f"Connecting to RabbitMQ at {self.config.host}:{self.config.port}")
            
            try:
                connection_url = self._build_connection_url()
                
                self._connection = await connect_robust(
                    connection_url,
                    heartbeat=self.config.heartbeat,
                    timeout=self.config.connection_timeout
                )
                
                self._channel = await self._connection.channel()
                await self._channel.set_qos(prefetch_count=self.config.prefetch_count)
                
                self._connected = True
                self._running = True
                
                self._processor_task = asyncio.create_task(self._processor_loop())
                
                logger.info("RabbitMQ connected successfully")
                
            except Exception as e:
                logger.error(f"Failed to connect to RabbitMQ: {e}")
                raise

    def _build_connection_url(self) -> str:
        auth = f"{self.config.username}:{self.config.password}"
        host = f"{self.config.host}:{self.config.port}"
        vhost = self.config.vhost
        ssl = "?ssl=True" if self.config.ssl else ""
        
        return f"amqp://{auth}@{host}/{vhost}{ssl}"

    async def disconnect(self) -> None:
        async with self._lock:
            self._running = False
            
            if self._processor_task:
                self._processor_task.cancel()
                try:
                    await self._processor_task
                except asyncio.CancelledError:
                    pass
                self._processor_task = None
            
            for consumer_task in self._consumer_tasks.values():
                consumer_task.cancel()
                try:
                    await consumer_task
                except asyncio.CancelledError:
                    pass
            self._consumer_tasks.clear()
            
            if self._connection:
                try:
                    await self._connection.close()
                except:
                    pass
                self._connection = None
                self._channel = None
            
            self._connected = False
            logger.info("RabbitMQ disconnected")

    async def reconnect(self) -> None:
        if self._reconnecting:
            return
        
        self._reconnecting = True
        logger.info("Attempting to reconnect to RabbitMQ")
        
        retries = 0
        max_retries = self.config.max_retries
        
        while retries < max_retries and self._running:
            try:
                await self.disconnect()
                await asyncio.sleep(self.config.retry_delay * (2 ** retries))
                await self.connect()
                self._reconnecting = False
                return
            except Exception as e:
                retries += 1
                logger.error(f"Reconnection attempt {retries} failed: {e}")
        
        self._reconnecting = False
        raise ConnectionError("Failed to reconnect to RabbitMQ")

    async def ensure_connection(self) -> None:
        if not self._connected:
            await self.connect()
        
        if not self._connection or self._connection.is_closed:
            await self.reconnect()

    async def declare_exchange(self, config: ExchangeConfig) -> None:
        await self.ensure_connection()
        
        async with self._lock:
            exchange_type = self._get_exchange_type(config.exchange_type)
            
            exchange = await self._channel.declare_exchange(
                name=config.name,
                type=exchange_type,
                durable=config.durable,
                auto_delete=config.auto_delete,
                internal=config.internal,
                arguments=config.arguments
            )
            
            self._exchanges[config.name] = exchange
            logger.info(f"Exchange declared: {config.name}")

    def _get_exchange_type(self, exchange_type: ExchangeType) -> aio_pika.ExchangeType:
        mapping = {
            ExchangeType.DIRECT: aio_pika.ExchangeType.DIRECT,
            ExchangeType.FANOUT: aio_pika.ExchangeType.FANOUT,
            ExchangeType.TOPIC: aio_pika.ExchangeType.TOPIC,
            ExchangeType.HEADERS: aio_pika.ExchangeType.HEADERS,
            ExchangeType.DELAYED: aio_pika.ExchangeType.X_DELAYED_MESSAGE
        }
        return mapping.get(exchange_type, aio_pika.ExchangeType.DIRECT)

    async def declare_queue(self, config: QueueConfig) -> None:
        await self.ensure_connection()
        
        async with self._lock:
            arguments = config.arguments.copy()
            
            if config.dead_letter_exchange:
                arguments["x-dead-letter-exchange"] = config.dead_letter_exchange
            
            if config.dead_letter_routing_key:
                arguments["x-dead-letter-routing-key"] = config.dead_letter_routing_key
            
            if config.max_length:
                arguments["x-max-length"] = config.max_length
            
            if config.max_length_bytes:
                arguments["x-max-length-bytes"] = config.max_length_bytes
            
            if config.message_ttl:
                arguments["x-message-ttl"] = config.message_ttl
            
            if config.expires:
                arguments["x-expires"] = config.expires
            
            queue = await self._channel.declare_queue(
                name=config.name,
                durable=config.durable,
                exclusive=config.exclusive,
                auto_delete=config.auto_delete,
                arguments=arguments
            )
            
            self._queues[config.name] = queue
            logger.info(f"Queue declared: {config.name}")

    async def bind_queue(self, config: BindingConfig) -> None:
        await self.ensure_connection()
        
        async with self._lock:
            if config.queue_name not in self._queues:
                raise ValueError(f"Queue not found: {config.queue_name}")
            
            if config.exchange_name not in self._exchanges:
                raise ValueError(f"Exchange not found: {config.exchange_name}")
            
            queue = self._queues[config.queue_name]
            exchange = self._exchanges[config.exchange_name]
            
            await queue.bind(
                exchange=exchange,
                routing_key=config.routing_key,
                arguments=config.arguments
            )
            
            self._bindings[config.queue_name].append(config)
            logger.info(f"Queue {config.queue_name} bound to exchange {config.exchange_name}")

    async def publish(
        self,
        exchange_name: str,
        routing_key: str,
        message: Message,
        mandatory: bool = False,
        immediate: bool = False
    ) -> Optional[str]:
        await self.ensure_connection()
        
        async with self._lock:
            if exchange_name not in self._exchanges:
                raise ValueError(f"Exchange not found: {exchange_name}")
            
            exchange = self._exchanges[exchange_name]
            
            try:
                body = self._serialize_message(message)
                
                priority = self._get_priority_value(message.priority)
                delivery_mode = DeliveryMode.PERSISTENT if message.delivery_mode == 2 else DeliveryMode.NOT_PERSISTENT
                
                aio_message = Message(
                    body=body,
                    delivery_mode=delivery_mode,
                    priority=priority,
                    correlation_id=message.correlation_id,
                    reply_to=message.reply_to,
                    expiration=str(message.expiration) if message.expiration else None,
                    user_id=message.user_id,
                    app_id=message.app_id,
                    content_type=message.content_type,
                    content_encoding=message.content_encoding,
                    headers={
                        "x-message-id": message.id,
                        "x-timestamp": str(message.timestamp),
                        "x-retry-count": str(message.retry_count),
                        "x-max-retries": str(message.max_retries),
                        **message.headers
                    }
                )
                
                await exchange.publish(
                    aio_message,
                    routing_key=routing_key,
                    mandatory=mandatory,
                    immediate=immediate
                )
                
                self._stats['messages_published'] += 1
                self._pending_messages[message.id] = {
                    "message": message,
                    "timestamp": time.time(),
                    "status": "published"
                }
                
                await self._notify_listeners("publish", message)
                
                return message.id
                
            except Exception as e:
                logger.error(f"Failed to publish message: {e}")
                self._stats['publish_errors'] += 1
                raise

    async def consume(
        self,
        queue_name: str,
        handler: Optional[Callable] = None,
        auto_ack: bool = False,
        prefetch_count: Optional[int] = None
    ) -> str:
        await self.ensure_connection()
        
        async with self._lock:
            if queue_name not in self._queues:
                raise ValueError(f"Queue not found: {queue_name}")
            
            queue = self._queues[queue_name]
            
            if handler:
                self._consumers[queue_name] = handler
            
            if prefetch_count:
                await self._channel.set_qos(prefetch_count=prefetch_count)
            
            consumer_tag = await queue.consume(
                self._message_callback,
                auto_ack=auto_ack,
                exclusive=False,
                consumer_timeout=self.config.consumer_timeout
            )
            
            self._consumer_tags[queue_name] = consumer_tag
            logger.info(f"Consumer started for queue: {queue_name}")
            
            return consumer_tag

    async def _message_callback(self, incoming_message: AbstractIncomingMessage) -> None:
        async with incoming_message.process(ignore_processed=True):
            try:
                body = incoming_message.body
                message = self._deserialize_message(body, incoming_message)
                
                await self._process_message(message, incoming_message)
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                self._stats['message_errors'] += 1
                
                if incoming_message.delivery_tag:
                    await incoming_message.reject(requeue=False)

    async def _process_message(
        self,
        message: Message,
        incoming_message: Optional[AbstractIncomingMessage] = None
    ) -> None:
        message.status = MessageStatus.PROCESSING
        self._pending_messages[message.id] = {
            "message": message,
            "timestamp": time.time(),
            "status": "processing"
        }
        
        await self._notify_listeners("processing", message)
        
        try:
            for middleware in self._middleware:
                await middleware("before", message)
            
            handler = self._message_handlers.get(
                message.headers.get("handler", "default"),
                self._message_handlers.get("default")
            )
            
            if handler:
                result = await handler(message)
                message.status = MessageStatus.COMPLETED
                
                for middleware in self._middleware:
                    await middleware("after", message)
                
                self._stats['messages_processed'] += 1
                await self._notify_listeners("completed", message, result)
                
                if incoming_message and not incoming_message.processed:
                    await incoming_message.ack()
            else:
                logger.warning(f"No handler for message: {message.id}")
                message.status = MessageStatus.FAILED
                
                if incoming_message and not incoming_message.processed:
                    await incoming_message.reject(requeue=False)
                
        except Exception as e:
            logger.error(f"Error processing message {message.id}: {e}")
            message.status = MessageStatus.FAILED
            self._stats['message_failures'] += 1
            
            await self._handle_message_failure(message, incoming_message, e)

    async def _handle_message_failure(
        self,
        message: Message,
        incoming_message: Optional[AbstractIncomingMessage],
        error: Exception
    ) -> None:
        if message.retry_count < message.max_retries:
            message.retry_count += 1
            message.status = MessageStatus.RETRY
            
            self._stats['message_retries'] += 1
            
            retry_delay = self.config.retry_delay * (2 ** message.retry_count)
            
            if incoming_message:
                if incoming_message.delivery_tag:
                    await incoming_message.reject(requeue=True)
                
                asyncio.create_task(self._publish_retry(message, retry_delay))
        else:
            error_handler = self._error_handlers.get(
                message.headers.get("error_handler", "default"),
                self._error_handlers.get("default")
            )
            
            if error_handler:
                await error_handler(message, error)
            
            if incoming_message and not incoming_message.processed:
                await incoming_message.reject(requeue=False)

    async def _publish_retry(self, message: Message, delay: float) -> None:
        await asyncio.sleep(delay)
        message.headers["x-retry-count"] = str(message.retry_count)
        
        await self.publish(
            exchange_name="",
            routing_key=message.reply_to or "retry",
            message=message
        )

    def register_handler(self, name: str, handler: Callable) -> None:
        self._message_handlers[name] = handler
        logger.info(f"Registered handler: {name}")

    def register_error_handler(self, name: str, handler: Callable) -> None:
        self._error_handlers[name] = handler
        logger.info(f"Registered error handler: {name}")

    def register_middleware(self, middleware: Callable) -> None:
        self._middleware.append(middleware)

    def register_listener(self, listener: Callable) -> None:
        self._listeners.append(listener)

    async def _notify_listeners(self, event: str, *args) -> None:
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, *args)
                else:
                    listener(event, *args)
            except Exception as e:
                logger.error(f"Error in listener: {e}")

    def _serialize_message(self, message: Message) -> bytes:
        data = {
            "id": message.id,
            "body": message.body,
            "priority": message.priority.value,
            "delivery_mode": message.delivery_mode,
            "headers": message.headers,
            "correlation_id": message.correlation_id,
            "reply_to": message.reply_to,
            "expiration": message.expiration,
            "user_id": message.user_id,
            "app_id": message.app_id,
            "content_type": message.content_type,
            "content_encoding": message.content_encoding,
            "timestamp": message.timestamp,
            "metadata": message.metadata,
            "retry_count": message.retry_count,
            "max_retries": message.max_retries,
            "status": message.status.value
        }
        
        json_data = json.dumps(data, default=str).encode('utf-8')
        
        if self.config.metadata.get("compression", True):
            compressed = zlib.compress(json_data)
            return base64.b64encode(compressed)
        
        return base64.b64encode(json_data)

    def _deserialize_message(
        self,
        body: bytes,
        incoming_message: Optional[AbstractIncomingMessage] = None
    ) -> Message:
        try:
            data = base64.b64decode(body)
            decompressed = zlib.decompress(data) if self.config.metadata.get("compression", True) else data
            parsed = json.loads(decompressed.decode('utf-8'))
        except:
            parsed = {
                "id": str(uuid.uuid4()),
                "body": body,
                "priority": "normal",
                "headers": {},
                "retry_count": 0,
                "max_retries": 3,
                "status": "pending"
            }
        
        message = Message(
            id=parsed.get("id", str(uuid.uuid4())),
            body=parsed.get("body", {}),
            priority=MessagePriority(parsed.get("priority", "normal")),
            delivery_mode=parsed.get("delivery_mode", 2),
            headers=parsed.get("headers", {}),
            correlation_id=parsed.get("correlation_id"),
            reply_to=parsed.get("reply_to"),
            expiration=parsed.get("expiration"),
            user_id=parsed.get("user_id"),
            app_id=parsed.get("app_id"),
            content_type=parsed.get("content_type", "application/json"),
            content_encoding=parsed.get("content_encoding", "utf-8"),
            timestamp=parsed.get("timestamp", time.time()),
            metadata=parsed.get("metadata", {}),
            retry_count=parsed.get("retry_count", 0),
            max_retries=parsed.get("max_retries", 3),
            status=MessageStatus(parsed.get("status", "pending"))
        )
        
        if incoming_message:
            if incoming_message.headers:
                message.headers.update(incoming_message.headers)
            
            if incoming_message.correlation_id:
                message.correlation_id = incoming_message.correlation_id
            
            if incoming_message.reply_to:
                message.reply_to = incoming_message.reply_to
        
        return message

    def _get_priority_value(self, priority: MessagePriority) -> int:
        mapping = {
            MessagePriority.LOW: 0,
            MessagePriority.NORMAL: 1,
            MessagePriority.MEDIUM: 3,
            MessagePriority.HIGH: 5,
            MessagePriority.CRITICAL: 9
        }
        return mapping.get(priority, 1)

    async def _default_message_handler(self, message: Message) -> Any:
        logger.info(f"Default handler processing message: {message.id}")
        return {"status": "processed"}

    async def _default_error_handler(self, message: Message, error: Exception) -> None:
        logger.error(f"Default error handler for message {message.id}: {error}")

    async def _processor_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Processor loop error: {e}")
                await asyncio.sleep(5)

    async def get_queue_info(self, queue_name: str) -> Optional[Dict[str, Any]]:
        if queue_name not in self._queues:
            return None
        
        async with self._lock:
            try:
                queue = self._queues[queue_name]
                
                if hasattr(queue, 'get_info'):
                    info = await queue.get_info()
                    
                    return {
                        "name": queue_name,
                        "messages": info.get("messages", 0),
                        "messages_ready": info.get("messages_ready", 0),
                        "messages_unacknowledged": info.get("messages_unacknowledged", 0),
                        "consumers": info.get("consumers", 0),
                        "memory": info.get("memory", 0)
                    }
                
            except Exception as e:
                logger.error(f"Error getting queue info: {e}")
        
        return {
            "name": queue_name,
            "messages": 0,
            "messages_ready": 0,
            "messages_unacknowledged": 0,
            "consumers": 0,
            "memory": 0
        }

    async def get_exchange_info(self, exchange_name: str) -> Optional[Dict[str, Any]]:
        if exchange_name not in self._exchanges:
            return None
        
        return {
            "name": exchange_name,
            "type": self._exchanges[exchange_name].type.value,
            "durable": self._exchanges[exchange_name].durable,
            "auto_delete": self._exchanges[exchange_name].auto_delete,
            "internal": self._exchanges[exchange_name].internal
        }

    async def purge_queue(self, queue_name: str) -> int:
        await self.ensure_connection()
        
        async with self._lock:
            if queue_name not in self._queues:
                raise ValueError(f"Queue not found: {queue_name}")
            
            try:
                count = await self._queues[queue_name].purge()
                logger.info(f"Purged {count} messages from queue: {queue_name}")
                return count
            except Exception as e:
                logger.error(f"Failed to purge queue: {e}")
                raise

    async def delete_queue(self, queue_name: str, if_unused: bool = False, if_empty: bool = False) -> bool:
        await self.ensure_connection()
        
        async with self._lock:
            if queue_name not in self._queues:
                return False
            
            try:
                if queue_name in self._consumer_tags:
                    await self._queues[queue_name].cancel(self._consumer_tags[queue_name])
                    del self._consumer_tags[queue_name]
                
                if queue_name in self._consumers:
                    del self._consumers[queue_name]
                
                await self._queues[queue_name].delete(if_unused=if_unused, if_empty=if_empty)
                del self._queues[queue_name]
                del self._bindings[queue_name]
                
                logger.info(f"Queue deleted: {queue_name}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to delete queue: {e}")
                return False

    async def delete_exchange(self, exchange_name: str, if_unused: bool = False) -> bool:
        await self.ensure_connection()
        
        async with self._lock:
            if exchange_name not in self._exchanges:
                return False
            
            try:
                await self._exchanges[exchange_name].delete(if_unused=if_unused)
                del self._exchanges[exchange_name]
                
                for queue_name in list(self._bindings.keys()):
                    self._bindings[queue_name] = [
                        b for b in self._bindings[queue_name]
                        if b.exchange_name != exchange_name
                    ]
                
                logger.info(f"Exchange deleted: {exchange_name}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to delete exchange: {e}")
                return False

    async def stop_consumer(self, queue_name: str) -> bool:
        async with self._lock:
            if queue_name not in self._consumer_tags:
                return False
            
            try:
                await self._queues[queue_name].cancel(self._consumer_tags[queue_name])
                del self._consumer_tags[queue_name]
                logger.info(f"Consumer stopped for queue: {queue_name}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to stop consumer: {e}")
                return False

    def get_stats(self) -> Dict[str, Any]:
        return {
            "connected": self._connected,
            "running": self._running,
            "exchanges": len(self._exchanges),
            "queues": len(self._queues),
            "bindings": sum(len(b) for b in self._bindings.values()),
            "consumers": len(self._consumers),
            "consumer_tags": len(self._consumer_tags),
            "pending_messages": len(self._pending_messages),
            "messages_published": self._stats['messages_published'],
            "messages_processed": self._stats['messages_processed'],
            "message_retries": self._stats['message_retries'],
            "message_failures": self._stats['message_failures'],
            "publish_errors": self._stats['publish_errors'],
            "message_errors": self._stats['message_errors'],
            "handlers": len(self._message_handlers),
            "error_handlers": len(self._error_handlers),
            "middleware": len(self._middleware),
            "listeners": len(self._listeners),
            "reconnecting": self._reconnecting
        }

    async def shutdown(self) -> None:
        self._running = False
        
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._processor_task = None
        
        for consumer_task in self._consumer_tasks.values():
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass
        self._consumer_tasks.clear()
        
        await self.disconnect()
        
        logger.info("RabbitMQ manager shutdown")


class RabbitMQBatchProcessor:
    
    def __init__(
        self,
        manager: RabbitMQManager,
        queue_name: str,
        batch_size: int = 10,
        batch_timeout: float = 1.0,
        max_batch_size_bytes: int = 1024 * 1024
    ):
        self.manager = manager
        self.queue_name = queue_name
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_batch_size_bytes = max_batch_size_bytes
        self._lock = asyncio.Lock()
        self._batch: List[Message] = []
        self._batch_timestamp = 0.0
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._stats = defaultdict(int)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._batch_loop())
        logger.info(f"Batch processor started for queue: {self.queue_name}")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        await self.flush()
        logger.info(f"Batch processor stopped for queue: {self.queue_name}")

    async def add_message(self, message: Message) -> None:
        async with self._lock:
            self._batch.append(message)
            
            if self._batch_timestamp == 0:
                self._batch_timestamp = time.time()
            
            if (len(self._batch) >= self.batch_size or
                self._get_batch_size() >= self.max_batch_size_bytes):
                await self.flush()

    def _get_batch_size(self) -> int:
        total = 0
        for msg in self._batch:
            try:
                total += len(json.dumps(msg.body).encode('utf-8'))
            except:
                total += 1024
        return total

    async def flush(self) -> None:
        async with self._lock:
            if not self._batch:
                return
            
            batch = self._batch
            self._batch = []
            self._batch_timestamp = 0
            
            await self._process_batch(batch)
            self._stats['batches_processed'] += 1
            self._stats['messages_batched'] += len(batch)

    async def _batch_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(0.1)
                
                if self._batch and time.time() - self._batch_timestamp >= self.batch_timeout:
                    await self.flush()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in batch loop: {e}")
                await asyncio.sleep(1)

    async def _process_batch(self, batch: List[Message]) -> None:
        if not batch:
            return
        
        try:
            first_message = batch[0]
            batch_id = str(uuid.uuid4())
            
            for message in batch:
                message.headers["x-batch-id"] = batch_id
                message.headers["x-batch-size"] = str(len(batch))
            
            for message in batch:
                await self.manager._process_message(message)
                
        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            self._stats['batch_errors'] += 1

    def get_stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "batch_size": self.batch_size,
            "batch_timeout": self.batch_timeout,
            "max_batch_size_bytes": self.max_batch_size_bytes,
            "current_batch_size": len(self._batch),
            "current_batch_bytes": self._get_batch_size(),
            "batches_processed": self._stats['batches_processed'],
            "messages_batched": self._stats['messages_batched'],
            "batch_errors": self._stats['batch_errors'],
            "queue_name": self.queue_name
        }


class RabbitMQRPCClient:
    
    def __init__(self, manager: RabbitMQManager, timeout: float = 30.0):
        self.manager = manager
        self.timeout = timeout
        self._lock = asyncio.Lock()
        self._callbacks: Dict[str, asyncio.Future] = {}
        self._consumer_tag: Optional[str] = None
        self._queue_name: Optional[str] = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        
        self._queue_name = f"rpc_reply_{uuid.uuid4().hex[:8]}"
        
        queue_config = QueueConfig(
            name=self._queue_name,
            durable=False,
            exclusive=True,
            auto_delete=True
        )
        
        await self.manager.declare_queue(queue_config)
        
        self._consumer_tag = await self.manager.consume(
            self._queue_name,
            self._handle_response,
            auto_ack=True
        )
        
        logger.info(f"RPC client started with reply queue: {self._queue_name}")

    async def stop(self) -> None:
        self._running = False
        
        if self._consumer_tag and self._queue_name:
            await self.manager.stop_consumer(self._queue_name)
            await self.manager.delete_queue(self._queue_name)
        
        for future in self._callbacks.values():
            if not future.done():
                future.cancel()
        
        logger.info("RPC client stopped")

    async def call(
        self,
        exchange_name: str,
        routing_key: str,
        request: Any,
        timeout: Optional[float] = None
    ) -> Any:
        if not self._running:
            raise RuntimeError("RPC client not started")
        
        message_id = str(uuid.uuid4())
        future = asyncio.Future()
        self._callbacks[message_id] = future
        
        message = Message(
            id=message_id,
            body=request,
            reply_to=self._queue_name,
            correlation_id=message_id,
            headers={"rpc": "true"}
        )
        
        await self.manager.publish(
            exchange_name=exchange_name,
            routing_key=routing_key,
            message=message
        )
        
        try:
            result = await asyncio.wait_for(future, timeout or self.timeout)
            return result
        except asyncio.TimeoutError:
            self._callbacks.pop(message_id, None)
            raise
        finally:
            self._callbacks.pop(message_id, None)

    async def _handle_response(self, message: Message) -> None:
        correlation_id = message.correlation_id
        
        if correlation_id in self._callbacks:
            future = self._callbacks[correlation_id]
            if not future.done():
                future.set_result(message.body)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "queue_name": self._queue_name,
            "pending_calls": len(self._callbacks),
            "timeout": self.timeout
        }


class RabbitMQRPCServer:
    
    def __init__(self, manager: RabbitMQManager, queue_name: str):
        self.manager = manager
        self.queue_name = queue_name
        self._lock = asyncio.Lock()
        self._handlers: Dict[str, Callable] = {}
        self._running = False

    async def start(self) -> None:
        self._running = True
        
        await self.manager.declare_queue(
            QueueConfig(name=self.queue_name, durable=True)
        )
        
        await self.manager.consume(
            self.queue_name,
            self._handle_request,
            auto_ack=False
        )
        
        logger.info(f"RPC server started on queue: {self.queue_name}")

    async def stop(self) -> None:
        self._running = False
        await self.manager.stop_consumer(self.queue_name)
        logger.info("RPC server stopped")

    def register_handler(self, name: str, handler: Callable) -> None:
        self._handlers[name] = handler

    async def _handle_request(self, message: Message) -> None:
        try:
            method = message.headers.get("rpc_method", "default")
            
            if method not in self._handlers:
                await self._send_error(message, f"Method not found: {method}")
                return
            
            handler = self._handlers[method]
            result = await handler(message.body)
            
            await self._send_response(message, result)
            
        except Exception as e:
            logger.error(f"Error handling RPC request: {e}")
            await self._send_error(message, str(e))

    async def _send_response(self, request: Message, result: Any) -> None:
        reply_queue = request.reply_to
        
        if not reply_queue:
            return
        
        response = Message(
            id=str(uuid.uuid4()),
            body=result,
            correlation_id=request.correlation_id,
            headers={"rpc_response": "true"}
        )
        
        await self.manager.publish(
            exchange_name="",
            routing_key=reply_queue,
            message=response
        )

    async def _send_error(self, request: Message, error: str) -> None:
        reply_queue = request.reply_to
        
        if not reply_queue:
            return
        
        response = Message(
            id=str(uuid.uuid4()),
            body={"error": error},
            correlation_id=request.correlation_id,
            headers={"rpc_response": "true", "rpc_error": "true"}
        )
        
        await self.manager.publish(
            exchange_name="",
            routing_key=reply_queue,
            message=response
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "queue_name": self.queue_name,
            "handlers": len(self._handlers),
            "handler_names": list(self._handlers.keys())
        }


__all__ = [
    "ExchangeType",
    "MessagePriority",
    "MessageStatus",
    "DeadLetterPolicy",
    "RabbitMQConfig",
    "ExchangeConfig",
    "QueueConfig",
    "BindingConfig",
    "Message",
    "MessageResult",
    "RabbitMQManager",
    "RabbitMQBatchProcessor",
    "RabbitMQRPCClient",
    "RabbitMQRPCServer"
]
