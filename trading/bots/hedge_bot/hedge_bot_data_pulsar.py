# trading/bots/hedge_bot/hedge_bot_data_pulsar.py

import asyncio
import json
import logging
import time
import uuid
import hashlib
import base64
import zlib
import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict
import threading
import queue

try:
    import pulsar
    from pulsar import Client, Producer, Consumer, Reader, Message, AuthenticationToken, AuthenticationTLS
    from pulsar.schema import Schema, StringSchema, BytesSchema, JsonSchema, AvroSchema, ProtoBufSchema
    PULSAR_AVAILABLE = True
except ImportError:
    PULSAR_AVAILABLE = False
    print("pulsar-client not installed. Please install: pip install pulsar-client")

try:
    import avro
    from avro.schema import Parse
    AVRO_AVAILABLE = True
except ImportError:
    AVRO_AVAILABLE = False

try:
    import google.protobuf
    from google.protobuf import json_format, message
    PROTOBUF_AVAILABLE = True
except ImportError:
    PROTOBUF_AVAILABLE = False

logger = logging.getLogger(__name__)


class CompressionType(str, Enum):
    NONE = "none"
    ZLIB = "zlib"
    LZ4 = "lz4"
    ZSTD = "zstd"
    SNAPPY = "snappy"


class SubscriptionType(str, Enum):
    EXCLUSIVE = "exclusive"
    SHARED = "shared"
    FAILOVER = "failover"
    KEY_SHARED = "key_shared"


class MessageRoutingMode(str, Enum):
    ROUND_ROBIN = "round_robin"
    SINGLE_PARTITION = "single_partition"
    CUSTOM = "custom"
    KEY_BASED = "key_based"


class BatchMessageType(str, Enum):
    TRADE = "trade"
    ORDER = "order"
    POSITION = "position"
    SIGNAL = "signal"
    RISK = "risk"
    PERFORMANCE = "performance"
    MARKET_DATA = "market_data"
    ALERT = "alert"
    LOG = "log"
    METRIC = "metric"
    CONFIG = "config"
    STATE = "state"
    HEARTBEAT = "heartbeat"
    BACKTEST = "backtest"
    ANALYTICS = "analytics"
    HEDGE = "hedge"
    INVOICE = "invoice"
    PROVENANCE = "provenance"
    SYSTEM = "system"


@dataclass
class PulsarConfig:
    service_url: str
    tenant: str = "nexus"
    namespace: str = "trading"
    authentication_token: Optional[str] = None
    tls_enabled: bool = True
    tls_allow_insecure: bool = False
    tls_hostname_verification: bool = True
    operation_timeout: int = 30
    connection_timeout: int = 30
    io_threads: int = 4
    memory_limit: int = 100 * 1024 * 1024
    max_producer_queue_size: int = 1000
    max_consumer_queue_size: int = 1000


@dataclass
class TopicConfig:
    name: str
    partitions: int = 1
    retention_time: int = 604800
    retention_size: int = 10 * 1024 * 1024 * 1024
    deduplication_enabled: bool = True
    deduplication_snapshot_interval: int = 120
    compaction_threshold: int = 100000000
    message_ttl: int = 0
    max_producers: int = 100
    max_consumers: int = 100
    schema_type: Optional[str] = None
    schema_definition: Optional[str] = None
    auto_create: bool = True


@dataclass
class ProducerConfig:
    topic: str
    producer_name: Optional[str] = None
    schema_type: Optional[str] = None
    schema_definition: Optional[str] = None
    send_timeout: int = 30
    compression_type: CompressionType = CompressionType.NONE
    max_pending_messages: int = 1000
    max_pending_messages_across_partitions: int = 50000
    batching_enabled: bool = True
    batching_max_messages: int = 1000
    batching_max_size: int = 128 * 1024
    batching_max_publish_delay: int = 10
    routing_mode: MessageRoutingMode = MessageRoutingMode.ROUND_ROBIN
    initial_sequence_id: Optional[int] = None
    chunking_enabled: bool = True
    encryption_key: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class ConsumerConfig:
    topic: str
    subscription: str
    subscription_type: SubscriptionType = SubscriptionType.SHARED
    consumer_name: Optional[str] = None
    schema_type: Optional[str] = None
    schema_definition: Optional[str] = None
    receiver_queue_size: int = 1000
    max_total_receiver_queue_size_across_partitions: int = 50000
    consumer_timeout: int = 0
    priority_level: int = 0
    read_compacted: bool = False
    negative_ack_redelivery_delay: int = 60
    batch_receive_policy: Optional[Dict[str, Any]] = None
    dead_letter_policy: Optional[Dict[str, Any]] = None
    retry_enable: bool = True
    ack_timeout: int = 60000
    subscription_initial_position: str = "Latest"
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class PulsarMessage:
    id: str
    topic: str
    data: Any
    type: BatchMessageType
    timestamp: float
    sequence_id: Optional[int] = None
    key: Optional[str] = None
    ordering_key: Optional[str] = None
    partition_key: Optional[str] = None
    properties: Dict[str, str] = field(default_factory=dict)
    compression_type: CompressionType = CompressionType.NONE
    redelivery_count: int = 0
    publish_time: float = field(default_factory=time.time)
    event_time: Optional[float] = None
    message_id: Optional[str] = None


@dataclass
class BatchMessage:
    id: str
    type: BatchMessageType
    messages: List[PulsarMessage]
    timestamp: float
    total_size: int
    batch_size: int
    compression_type: CompressionType
    metadata: Dict[str, Any] = field(default_factory=dict)


class PulsarMessageHandler:
    
    def __init__(self, config: PulsarConfig):
        self.config = config
        self._client: Optional[Client] = None
        self._producers: Dict[str, Producer] = {}
        self._consumers: Dict[str, Consumer] = {}
        self._readers: Dict[str, Reader] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
        self._topics: Dict[str, TopicConfig] = {}
        self._handlers: Dict[BatchMessageType, List[Callable]] = defaultdict(list)
        self._async_handlers: Dict[BatchMessageType, List[Callable]] = defaultdict(list)
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._processing = False
        self._processor_task: Optional[asyncio.Task] = None
        self._stats = defaultdict(int)
        self._active = False
        self._pending_acks: Dict[str, Any] = {}
        self._schema_registry: Dict[str, Any] = {}

    async def initialize(self) -> None:
        if not PULSAR_AVAILABLE:
            raise ImportError("pulsar-client not available")

        async with self._lock:
            if self._initialized:
                return

            client_config = {}
            if self.config.authentication_token:
                auth = AuthenticationToken(self.config.authentication_token)
                client_config['authentication'] = auth

            if self.config.tls_enabled:
                client_config['tls_enable'] = True
                client_config['tls_allow_insecure'] = self.config.tls_allow_insecure
                client_config['tls_hostname_verification'] = self.config.tls_hostname_verification

            self._client = pulsar.Client(
                self.config.service_url,
                operation_timeout_seconds=self.config.operation_timeout,
                connection_timeout_seconds=self.config.connection_timeout,
                io_threads=self.config.io_threads,
                memory_limit_bytes=self.config.memory_limit,
                **client_config
            )

            self._initialized = True
            self._active = True
            self._processor_task = asyncio.create_task(self._processor_loop())
            logger.info(f"Pulsar client initialized for {self.config.service_url}")

    async def close(self) -> None:
        async with self._lock:
            self._active = False
            self._initialized = False

            if self._processor_task:
                self._processor_task.cancel()
                try:
                    await self._processor_task
                except asyncio.CancelledError:
                    pass
                self._processor_task = None

            for producer in self._producers.values():
                try:
                    producer.close()
                except:
                    pass
            self._producers.clear()

            for consumer in self._consumers.values():
                try:
                    consumer.close()
                except:
                    pass
            self._consumers.clear()

            for reader in self._readers.values():
                try:
                    reader.close()
                except:
                    pass
            self._readers.clear()

            if self._client:
                self._client.close()
                self._client = None

            logger.info("Pulsar client closed")

    async def create_topic(self, config: TopicConfig) -> bool:
        async with self._lock:
            if not self._initialized:
                raise RuntimeError("Pulsar client not initialized")

            topic_name = self._get_topic_name(config.name)
            self._topics[config.name] = config

            if not config.auto_create:
                admin = self._client.admin()
                try:
                    admin.topics().create(
                        topic_name,
                        partitions=config.partitions,
                        retention_time=config.retention_time,
                        retention_size=config.retention_size
                    )
                except Exception as e:
                    logger.warning(f"Topic {topic_name} may already exist: {e}")

            return True

    async def create_producer(self, config: ProducerConfig) -> str:
        async with self._lock:
            if not self._initialized:
                raise RuntimeError("Pulsar client not initialized")

            topic_name = self._get_topic_name(config.topic)
            producer_key = f"{topic_name}:{config.producer_name or 'default'}"

            if producer_key in self._producers:
                return producer_key

            producer_config = {
                'topic': topic_name,
                'send_timeout_millis': config.send_timeout * 1000,
                'max_pending_messages': config.max_pending_messages,
                'max_pending_messages_across_partitions': config.max_pending_messages_across_partitions,
                'batching_enabled': config.batching_enabled,
                'batching_max_messages': config.batching_max_messages,
                'batching_max_bytes': config.batching_max_size,
                'batching_max_publish_delay_ms': config.batching_max_publish_delay * 1000,
                'compression_type': self._get_compression_type(config.compression_type),
                'chunking_enabled': config.chunking_enabled,
                'initial_sequence_id': config.initial_sequence_id or -1,
                'routing_mode': self._get_routing_mode(config.routing_mode),
                'properties': config.metadata
            }

            if config.producer_name:
                producer_config['producer_name'] = config.producer_name

            if config.encryption_key:
                producer_config['encryption_key'] = config.encryption_key

            schema = self._get_schema(config.schema_type, config.schema_definition)
            if schema:
                producer_config['schema'] = schema

            producer = self._client.create_producer(**producer_config)
            self._producers[producer_key] = producer

            logger.info(f"Producer created: {producer_key}")
            return producer_key

    async def create_consumer(self, config: ConsumerConfig) -> str:
        async with self._lock:
            if not self._initialized:
                raise RuntimeError("Pulsar client not initialized")

            topic_name = self._get_topic_name(config.topic)
            consumer_key = f"{topic_name}:{config.subscription}:{config.consumer_name or 'default'}"

            if consumer_key in self._consumers:
                return consumer_key

            consumer_config = {
                'topic': topic_name,
                'subscription_name': config.subscription,
                'subscription_type': self._get_subscription_type(config.subscription_type),
                'receiver_queue_size': config.receiver_queue_size,
                'max_total_receiver_queue_size_across_partitions': config.max_total_receiver_queue_size_across_partitions,
                'consumer_timeout_millis': config.consumer_timeout,
                'priority_level': config.priority_level,
                'read_compacted': config.read_compacted,
                'negative_ack_redelivery_delay_ms': config.negative_ack_redelivery_delay * 1000,
                'ack_timeout_millis': config.ack_timeout,
                'subscription_initial_position': config.subscription_initial_position,
                'properties': config.metadata
            }

            if config.consumer_name:
                consumer_config['consumer_name'] = config.consumer_name

            if config.dead_letter_policy:
                consumer_config['dead_letter_policy'] = config.dead_letter_policy

            if config.batch_receive_policy:
                consumer_config['batch_receive_policy'] = config.batch_receive_policy

            schema = self._get_schema(config.schema_type, config.schema_definition)
            if schema:
                consumer_config['schema'] = schema

            consumer = self._client.subscribe(**consumer_config)
            self._consumers[consumer_key] = consumer

            logger.info(f"Consumer created: {consumer_key}")
            return consumer_key

    async def send_message(
        self,
        producer_key: str,
        message: PulsarMessage,
        use_compression: bool = True
    ) -> Optional[str]:
        async with self._lock:
            if producer_key not in self._producers:
                raise ValueError(f"Producer {producer_key} not found")

            producer = self._producers[producer_key]

            try:
                data = self._serialize_message(message)

                if use_compression and message.compression_type != CompressionType.NONE:
                    data = self._compress_data(data, message.compression_type)

                msg_config = {
                    'data': data,
                    'properties': message.properties
                }

                if message.key:
                    msg_config['key'] = message.key

                if message.ordering_key:
                    msg_config['ordering_key'] = message.ordering_key

                if message.partition_key:
                    msg_config['partition_key'] = message.partition_key

                if message.event_time:
                    msg_config['event_timestamp'] = int(message.event_time * 1000)

                if message.sequence_id is not None:
                    msg_config['sequence_id'] = message.sequence_id

                msg_id = producer.send(**msg_config)

                self._stats['messages_sent'] += 1
                self._stats['bytes_sent'] += len(data)

                message.message_id = str(msg_id)
                return str(msg_id)

            except Exception as e:
                logger.error(f"Error sending message: {e}")
                self._stats['send_errors'] += 1
                raise

    async def receive_message(
        self,
        consumer_key: str,
        timeout: Optional[float] = None
    ) -> Optional[PulsarMessage]:
        async with self._lock:
            if consumer_key not in self._consumers:
                raise ValueError(f"Consumer {consumer_key} not found")

            consumer = self._consumers[consumer_key]

            try:
                if timeout:
                    msg = consumer.receive(timeout_millis=int(timeout * 1000))
                else:
                    msg = consumer.receive()

                if not msg:
                    return None

                data = msg.data()

                if msg.properties.get('compressed', '').lower() == 'true':
                    data = self._decompress_data(data, CompressionType(msg.properties.get('compression_type', 'zlib')))

                pulsar_msg = self._deserialize_message(data, msg)

                self._pending_acks[pulsar_msg.id] = (consumer, msg)
                self._stats['messages_received'] += 1
                self._stats['bytes_received'] += len(data)

                return pulsar_msg

            except Exception as e:
                if "Timeout" not in str(e):
                    logger.error(f"Error receiving message: {e}")
                    self._stats['receive_errors'] += 1
                return None

    async def acknowledge(self, message_id: str) -> bool:
        async with self._lock:
            if message_id not in self._pending_acks:
                logger.warning(f"Message {message_id} not found in pending acks")
                return False

            consumer, msg = self._pending_acks[message_id]
            try:
                consumer.acknowledge(msg)
                del self._pending_acks[message_id]
                self._stats['messages_acknowledged'] += 1
                return True
            except Exception as e:
                logger.error(f"Error acknowledging message: {e}")
                self._stats['ack_errors'] += 1
                return False

    async def negative_acknowledge(self, message_id: str, delay: float = 60.0) -> bool:
        async with self._lock:
            if message_id not in self._pending_acks:
                return False

            consumer, msg = self._pending_acks[message_id]
            try:
                consumer.negative_acknowledge(msg)
                del self._pending_acks[message_id]
                self._stats['messages_nack'] += 1
                return True
            except Exception as e:
                logger.error(f"Error negative acknowledging message: {e}")
                return False

    async def redelivery_acknowledge(self, message_id: str) -> bool:
        async with self._lock:
            if message_id not in self._pending_acks:
                return False

            consumer, msg = self._pending_acks[message_id]
            try:
                consumer.redelivery_acknowledge(msg)
                del self._pending_acks[message_id]
                self._stats['messages_redelivered'] += 1
                return True
            except Exception as e:
                logger.error(f"Error redelivery acknowledging message: {e}")
                return False

    async def register_handler(
        self,
        message_type: BatchMessageType,
        handler: Callable,
        async_handler: bool = False
    ) -> None:
        if async_handler:
            self._async_handlers[message_type].append(handler)
        else:
            self._handlers[message_type].append(handler)
        logger.info(f"Registered handler for {message_type.value}")

    async def process_message(self, message: PulsarMessage) -> Any:
        handlers = self._handlers.get(message.type, [])
        async_handlers = self._async_handlers.get(message.type, [])

        results = []

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(message)
                else:
                    result = handler(message)
                results.append(result)
            except Exception as e:
                logger.error(f"Error in handler for {message.type.value}: {e}")
                self._stats['handler_errors'] += 1

        for handler in async_handlers:
            try:
                result = await handler(message)
                results.append(result)
            except Exception as e:
                logger.error(f"Error in async handler for {message.type.value}: {e}")
                self._stats['handler_errors'] += 1

        self._stats['messages_processed'] += 1
        return results

    async def _processor_loop(self) -> None:
        self._processing = True
        while self._active:
            try:
                try:
                    message = await asyncio.wait_for(
                        self._message_queue.get(),
                        timeout=0.1
                    )
                    await self.process_message(message)
                    self._message_queue.task_done()
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in processor loop: {e}")
                    await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                break

        self._processing = False

    def _get_topic_name(self, topic: str) -> str:
        if topic.startswith('persistent://') or topic.startswith('non-persistent://'):
            return topic
        return f"persistent://{self.config.tenant}/{self.config.namespace}/{topic}"

    def _get_compression_type(self, compression: CompressionType) -> int:
        if compression == CompressionType.ZLIB:
            return pulsar.CompressionType.ZLIB
        elif compression == CompressionType.LZ4:
            return pulsar.CompressionType.LZ4
        elif compression == CompressionType.ZSTD:
            return pulsar.CompressionType.ZSTD
        elif compression == CompressionType.SNAPPY:
            return pulsar.CompressionType.SNAPPY
        else:
            return pulsar.CompressionType.NONE

    def _get_subscription_type(self, sub_type: SubscriptionType) -> int:
        if sub_type == SubscriptionType.EXCLUSIVE:
            return pulsar.SubscriptionType.Exclusive
        elif sub_type == SubscriptionType.SHARED:
            return pulsar.SubscriptionType.Shared
        elif sub_type == SubscriptionType.FAILOVER:
            return pulsar.SubscriptionType.Failover
        elif sub_type == SubscriptionType.KEY_SHARED:
            return pulsar.SubscriptionType.Key_Shared
        else:
            return pulsar.SubscriptionType.Shared

    def _get_routing_mode(self, mode: MessageRoutingMode) -> int:
        if mode == MessageRoutingMode.ROUND_ROBIN:
            return pulsar.RoutingMode.RoundRobinPartition
        elif mode == MessageRoutingMode.SINGLE_PARTITION:
            return pulsar.RoutingMode.SinglePartition
        elif mode == MessageRoutingMode.KEY_BASED:
            return pulsar.RoutingMode.RoundRobinPartition
        else:
            return pulsar.RoutingMode.RoundRobinPartition

    def _get_schema(self, schema_type: Optional[str], schema_definition: Optional[str]) -> Optional[Any]:
        if not schema_type:
            return None

        if schema_type == 'string':
            return StringSchema()
        elif schema_type == 'bytes':
            return BytesSchema()
        elif schema_type == 'json':
            if schema_definition:
                return JsonSchema(schema_definition)
            return JsonSchema()
        elif schema_type == 'avro':
            if not AVRO_AVAILABLE:
                raise ImportError("avro not available")
            if schema_definition:
                schema = Parse(schema_definition)
                return AvroSchema(schema)
            return None
        elif schema_type == 'protobuf':
            if not PROTOBUF_AVAILABLE:
                raise ImportError("protobuf not available")
            if schema_definition:
                return ProtoBufSchema(schema_definition)
            return None
        else:
            return None

    def _serialize_message(self, message: PulsarMessage) -> bytes:
        data = {
            'id': message.id,
            'type': message.type.value,
            'timestamp': message.timestamp,
            'data': message.data
        }

        if message.key:
            data['key'] = message.key
        if message.ordering_key:
            data['ordering_key'] = message.ordering_key
        if message.partition_key:
            data['partition_key'] = message.partition_key
        if message.properties:
            data['properties'] = message.properties
        if message.sequence_id is not None:
            data['sequence_id'] = message.sequence_id
        if message.publish_time:
            data['publish_time'] = message.publish_time
        if message.event_time:
            data['event_time'] = message.event_time

        return json.dumps(data).encode('utf-8')

    def _deserialize_message(self, data: bytes, pulsar_msg: Any) -> PulsarMessage:
        try:
            parsed = json.loads(data)
        except:
            parsed = {'data': data, 'type': 'system'}

        return PulsarMessage(
            id=parsed.get('id', str(uuid.uuid4())),
            topic=pulsar_msg.topic_name(),
            data=parsed.get('data', data),
            type=BatchMessageType(parsed.get('type', 'system')),
            timestamp=parsed.get('timestamp', time.time()),
            sequence_id=parsed.get('sequence_id'),
            key=parsed.get('key'),
            ordering_key=parsed.get('ordering_key'),
            partition_key=parsed.get('partition_key'),
            properties=parsed.get('properties', {}),
            redelivery_count=pulsar_msg.redelivery_count(),
            publish_time=pulsar_msg.publish_timestamp() / 1000.0 if pulsar_msg.publish_timestamp() else time.time(),
            event_time=parsed.get('event_time'),
            message_id=str(pulsar_msg.message_id())
        )

    def _compress_data(self, data: bytes, compression: CompressionType) -> bytes:
        if compression == CompressionType.ZLIB:
            return zlib.compress(data)
        elif compression == CompressionType.LZ4:
            try:
                import lz4.frame
                return lz4.frame.compress(data)
            except:
                return zlib.compress(data)
        elif compression == CompressionType.ZSTD:
            try:
                import zstandard as zstd
                compressor = zstd.ZstdCompressor(level=3)
                return compressor.compress(data)
            except:
                return zlib.compress(data)
        elif compression == CompressionType.SNAPPY:
            try:
                import snappy
                return snappy.compress(data)
            except:
                return zlib.compress(data)
        else:
            return data

    def _decompress_data(self, data: bytes, compression: CompressionType) -> bytes:
        if compression == CompressionType.ZLIB:
            return zlib.decompress(data)
        elif compression == CompressionType.LZ4:
            try:
                import lz4.frame
                return lz4.frame.decompress(data)
            except:
                return zlib.decompress(data)
        elif compression == CompressionType.ZSTD:
            try:
                import zstandard as zstd
                decompressor = zstd.ZstdDecompressor()
                return decompressor.decompress(data)
            except:
                return zlib.decompress(data)
        elif compression == CompressionType.SNAPPY:
            try:
                import snappy
                return snappy.decompress(data)
            except:
                return zlib.decompress(data)
        else:
            return data

    async def create_reader(
        self,
        topic: str,
        start_message_id: Optional[str] = None,
        start_time: Optional[float] = None,
        reader_name: Optional[str] = None
    ) -> str:
        async with self._lock:
            if not self._initialized:
                raise RuntimeError("Pulsar client not initialized")

            topic_name = self._get_topic_name(topic)
            reader_key = f"{topic_name}:{reader_name or 'default'}"

            if reader_key in self._readers:
                return reader_key

            config = {'topic': topic_name}

            if start_message_id:
                config['start_message_id'] = start_message_id
            elif start_time:
                config['start_time'] = int(start_time * 1000)

            if reader_name:
                config['reader_name'] = reader_name

            reader = self._client.create_reader(**config)
            self._readers[reader_key] = reader

            logger.info(f"Reader created: {reader_key}")
            return reader_key

    async def read_message(self, reader_key: str, timeout: Optional[float] = None) -> Optional[PulsarMessage]:
        async with self._lock:
            if reader_key not in self._readers:
                raise ValueError(f"Reader {reader_key} not found")

            reader = self._readers[reader_key]

            try:
                if timeout:
                    msg = reader.read_next(timeout_millis=int(timeout * 1000))
                else:
                    msg = reader.read_next()

                if not msg:
                    return None

                data = msg.data()
                return self._deserialize_message(data, msg)

            except Exception as e:
                if "Timeout" not in str(e):
                    logger.error(f"Error reading message: {e}")
                return None

    async def close_reader(self, reader_key: str) -> bool:
        async with self._lock:
            if reader_key not in self._readers:
                return False

            try:
                self._readers[reader_key].close()
                del self._readers[reader_key]
                return True
            except Exception as e:
                logger.error(f"Error closing reader: {e}")
                return False

    def get_stats(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "active": self._active,
            "producers": len(self._producers),
            "consumers": len(self._consumers),
            "readers": len(self._readers),
            "topics": len(self._topics),
            "pending_acks": len(self._pending_acks),
            "queue_size": self._message_queue.qsize(),
            "messages_sent": self._stats['messages_sent'],
            "messages_received": self._stats['messages_received'],
            "messages_processed": self._stats['messages_processed'],
            "messages_acknowledged": self._stats['messages_acknowledged'],
            "bytes_sent": self._stats['bytes_sent'],
            "bytes_received": self._stats['bytes_received'],
            "send_errors": self._stats['send_errors'],
            "receive_errors": self._stats['receive_errors'],
            "ack_errors": self._stats['ack_errors'],
            "handler_errors": self._stats['handler_errors'],
            "messages_nack": self._stats['messages_nack'],
            "messages_redelivered": self._stats['messages_redelivered'],
            "processing": self._processing
        }


class PulsarBatchProcessor:
    
    def __init__(
        self,
        handler: PulsarMessageHandler,
        batch_size: int = 100,
        batch_timeout: float = 1.0,
        max_batch_size_bytes: int = 1024 * 1024
    ):
        self.handler = handler
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_batch_size_bytes = max_batch_size_bytes
        self._batches: Dict[BatchMessageType, List[PulsarMessage]] = defaultdict(list)
        self._batch_timestamps: Dict[BatchMessageType, float] = {}
        self._lock = asyncio.Lock()
        self._active = False
        self._task: Optional[asyncio.Task] = None
        self._stats = defaultdict(int)

    async def start(self) -> None:
        self._active = True
        self._task = asyncio.create_task(self._batch_loop())
        logger.info("Batch processor started")

    async def stop(self) -> None:
        self._active = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        await self.flush_all()
        logger.info("Batch processor stopped")

    async def add_message(self, message: PulsarMessage) -> None:
        async with self._lock:
            self._batches[message.type].append(message)
            if message.type not in self._batch_timestamps:
                self._batch_timestamps[message.type] = time.time()

            size = len(json.dumps(message.data).encode('utf-8'))
            if (len(self._batches[message.type]) >= self.batch_size or
                self._get_batch_size(message.type) + size > self.max_batch_size_bytes):
                await self._flush_batch(message.type)

    async def _batch_loop(self) -> None:
        while self._active:
            try:
                await asyncio.sleep(0.1)

                now = time.time()
                to_flush = []

                async with self._lock:
                    for msg_type, timestamp in self._batch_timestamps.items():
                        if now - timestamp >= self.batch_timeout:
                            to_flush.append(msg_type)

                for msg_type in to_flush:
                    await self._flush_batch(msg_type)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in batch loop: {e}")
                await asyncio.sleep(1)

    async def _flush_batch(self, msg_type: BatchMessageType) -> None:
        async with self._lock:
            if msg_type not in self._batches or not self._batches[msg_type]:
                return

            messages = self._batches[msg_type]
            self._batches[msg_type] = []
            self._batch_timestamps.pop(msg_type, None)

            if not messages:
                return

            batch = BatchMessage(
                id=str(uuid.uuid4()),
                type=msg_type,
                messages=messages,
                timestamp=time.time(),
                total_size=self._get_batch_size(msg_type),
                batch_size=len(messages),
                compression_type=CompressionType.ZLIB
            )

            await self._process_batch(batch)
            self._stats['batches_processed'] += 1
            self._stats['messages_batched'] += len(messages)

    def _get_batch_size(self, msg_type: BatchMessageType) -> int:
        total = 0
        for msg in self._batches.get(msg_type, []):
            try:
                total += len(json.dumps(msg.data).encode('utf-8'))
            except:
                total += 1024
        return total

    async def _process_batch(self, batch: BatchMessage) -> None:
        for message in batch.messages:
            await self.handler.process_message(message)

    async def flush_all(self) -> None:
        async with self._lock:
            msg_types = list(self._batches.keys())
            for msg_type in msg_types:
                await self._flush_batch(msg_type)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "active": self._active,
            "batch_size": self.batch_size,
            "batch_timeout": self.batch_timeout,
            "max_batch_size_bytes": self.max_batch_size_bytes,
            "batches_processed": self._stats['batches_processed'],
            "messages_batched": self._stats['messages_batched'],
            "pending_batches": len(self._batches),
            "pending_messages": sum(len(m) for m in self._batches.values())
        }


__all__ = [
    "CompressionType",
    "SubscriptionType",
    "MessageRoutingMode",
    "BatchMessageType",
    "PulsarConfig",
    "TopicConfig",
    "ProducerConfig",
    "ConsumerConfig",
    "PulsarMessage",
    "BatchMessage",
    "PulsarMessageHandler",
    "PulsarBatchProcessor"
]
