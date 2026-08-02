# trading/bots/hedge_bot/hedge_bot_data_sigfox.py

import asyncio
import logging
import time
import json
import hashlib
import base64
import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict
import hmac
import urllib.parse

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

logger = logging.getLogger(__name__)


class SigfoxDeviceType(str, Enum):
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    GATEWAY = "gateway"
    MODULE = "module"
    TRACKER = "tracker"
    MONITOR = "monitor"


class SigfoxMessageType(str, Enum):
    UPLINK = "uplink"
    DOWNLINK = "downlink"
    BIDIRECTIONAL = "bidirectional"
    STATUS = "status"
    ACK = "ack"
    NACK = "nack"
    CONFIG = "config"


class SigfoxProtocol(str, Enum):
    TCP = "tcp"
    UDP = "udp"
    HTTP = "http"
    HTTPS = "https"
    MQTT = "mqtt"
    COAP = "coap"


@dataclass
class SigfoxDevice:
    id: str
    name: str
    device_type: SigfoxDeviceType
    device_id: str
    device_key: str
    protocol: SigfoxProtocol
    endpoint: str
    port: int
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_heartbeat: Optional[float] = None
    last_message: Optional[float] = None
    message_count: int = 0
    error_count: int = 0


@dataclass
class SigfoxMessage:
    id: str
    device_id: str
    message_type: SigfoxMessageType
    data: bytes
    hex_data: str
    timestamp: float
    rssi: float = 0.0
    snr: float = 0.0
    station: str = ""
    seq_number: int = 0
    acknowledged: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SigfoxCallback:
    id: str
    name: str
    url: str
    method: str
    headers: Dict[str, str]
    payload_template: str
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class SigfoxGroup:
    id: str
    name: str
    devices: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class SigfoxDataManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._devices: Dict[str, SigfoxDevice] = {}
        self._messages: Dict[str, SigfoxMessage] = {}
        self._callbacks: Dict[str, SigfoxCallback] = {}
        self._groups: Dict[str, SigfoxGroup] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._handlers: Dict[SigfoxMessageType, List[Callable]] = defaultdict(list)
        self._observers: List[Callable] = []
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None
        self._message_queue: asyncio.Queue = asyncio.Queue()
        
        self._initialize_default_devices()

    def _initialize_default_devices(self) -> None:
        default_devices = [
            SigfoxDevice(
                id="gateway_1",
                name="Main Gateway",
                device_type=SigfoxDeviceType.GATEWAY,
                device_id="GATEWAY001",
                device_key="key123",
                protocol=SigfoxProtocol.HTTPS,
                endpoint="https://api.sigfox.com",
                port=443
            ),
            SigfoxDevice(
                id="sensor_temp_1",
                name="Temperature Sensor 1",
                device_type=SigfoxDeviceType.SENSOR,
                device_id="TEMP001",
                device_key="tempkey123",
                protocol=SigfoxProtocol.HTTPS,
                endpoint="https://api.sigfox.com",
                port=443
            )
        ]
        
        for device in default_devices:
            self._devices[device.id] = device

    def register_handler(self, message_type: SigfoxMessageType, handler: Callable) -> None:
        self._handlers[message_type].append(handler)

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def _ensure_session(self) -> None:
        if self._session is None and AIOHTTP_AVAILABLE:
            self._session = aiohttp.ClientSession()

    async def add_device(
        self,
        name: str,
        device_type: SigfoxDeviceType,
        device_id: str,
        device_key: str,
        protocol: SigfoxProtocol,
        endpoint: str,
        port: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SigfoxDevice:
        async with self._lock:
            dev_id = hashlib.md5(f"{device_id}_{time.time()}".encode()).hexdigest()
            
            device = SigfoxDevice(
                id=dev_id,
                name=name,
                device_type=device_type,
                device_id=device_id,
                device_key=device_key,
                protocol=protocol,
                endpoint=endpoint,
                port=port,
                metadata=metadata or {}
            )
            
            self._devices[dev_id] = device
            await self._notify_observers("device_added", device)
            return device

    async def remove_device(self, device_id: str) -> bool:
        async with self._lock:
            if device_id in self._devices:
                del self._devices[device_id]
                await self._notify_observers("device_removed", device_id)
                return True
            return False

    async def send_message(
        self,
        device_id: str,
        data: bytes,
        message_type: SigfoxMessageType = SigfoxMessageType.UPLINK,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[SigfoxMessage]:
        async with self._lock:
            if device_id not in self._devices:
                return None
            
            device = self._devices[device_id]
            
            msg_id = hashlib.md5(f"{device_id}_{time.time()}".encode()).hexdigest()
            
            message = SigfoxMessage(
                id=msg_id,
                device_id=device_id,
                message_type=message_type,
                data=data,
                hex_data=data.hex(),
                timestamp=time.time(),
                metadata=metadata or {}
            )
            
            self._messages[msg_id] = message
            
            success = await self._transmit_message(device, message)
            
            if success:
                device.last_message = message.timestamp
                device.message_count += 1
                await self._notify_observers("message_sent", message)
                await self._process_message(message)
            else:
                device.error_count += 1
                await self._notify_observers("message_failed", message)
            
            return message if success else None

    async def _transmit_message(self, device: SigfoxDevice, message: SigfoxMessage) -> bool:
        try:
            await self._ensure_session()
            
            if device.protocol == SigfoxProtocol.HTTPS:
                return await self._transmit_https(device, message)
            elif device.protocol == SigfoxProtocol.HTTP:
                return await self._transmit_http(device, message)
            elif device.protocol == SigfoxProtocol.MQTT:
                return await self._transmit_mqtt(device, message)
            elif device.protocol == SigfoxProtocol.TCP:
                return await self._transmit_tcp(device, message)
            elif device.protocol == SigfoxProtocol.UDP:
                return await self._transmit_udp(device, message)
            else:
                logger.warning(f"Unsupported protocol: {device.protocol}")
                return False
                
        except Exception as e:
            logger.error(f"Error transmitting message: {e}")
            return False

    async def _transmit_https(self, device: SigfoxDevice, message: SigfoxMessage) -> bool:
        url = f"{device.endpoint}/api/v2/devices/{device.device_id}/messages"
        
        payload = {
            "data": message.hex_data,
            "time": int(message.timestamp),
            "seqNumber": message.seq_number
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {device.device_key}"
        }
        
        try:
            async with self._session.post(url, json=payload, headers=headers) as response:
                if response.status in [200, 201, 202]:
                    return True
                else:
                    logger.error(f"HTTPS error: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"HTTPS transmit error: {e}")
            return False

    async def _transmit_http(self, device: SigfoxDevice, message: SigfoxMessage) -> bool:
        url = f"{device.endpoint}:{device.port}/api/v2/devices/{device.device_id}/messages"
        
        payload = f"data={message.hex_data}&time={int(message.timestamp)}"
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        try:
            async with self._session.post(url, data=payload, headers=headers) as response:
                if response.status in [200, 201, 202]:
                    return True
                else:
                    logger.error(f"HTTP error: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"HTTP transmit error: {e}")
            return False

    async def _transmit_mqtt(self, device: SigfoxDevice, message: SigfoxMessage) -> bool:
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            logger.error("MQTT client not installed")
            return False
        
        client = mqtt.Client()
        client.username_pw_set(device.device_id, device.device_key)
        
        try:
            client.connect(device.endpoint, device.port, 60)
            client.publish(f"devices/{device.device_id}/messages", message.hex_data)
            client.disconnect()
            return True
        except Exception as e:
            logger.error(f"MQTT transmit error: {e}")
            return False

    async def _transmit_tcp(self, device: SigfoxDevice, message: SigfoxMessage) -> bool:
        try:
            reader, writer = await asyncio.open_connection(device.endpoint, device.port)
            
            writer.write(message.data)
            await writer.drain()
            
            response = await reader.read(1024)
            writer.close()
            await writer.wait_closed()
            
            return bool(response)
        except Exception as e:
            logger.error(f"TCP transmit error: {e}")
            return False

    async def _transmit_udp(self, device: SigfoxDevice, message: SigfoxMessage) -> bool:
        try:
            sock = await asyncio.open_connection(device.endpoint, device.port)
            
            writer = sock[1]
            writer.write(message.data)
            await writer.drain()
            
            writer.close()
            await writer.wait_closed()
            
            return True
        except Exception as e:
            logger.error(f"UDP transmit error: {e}")
            return False

    async def receive_message(
        self,
        device_id: str,
        data: bytes,
        rssi: float = 0.0,
        snr: float = 0.0,
        station: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[SigfoxMessage]:
        async with self._lock:
            if device_id not in self._devices:
                return None
            
            device = self._devices[device_id]
            
            msg_id = hashlib.md5(f"{device_id}_{time.time()}_{len(data)}".encode()).hexdigest()
            
            message = SigfoxMessage(
                id=msg_id,
                device_id=device_id,
                message_type=SigfoxMessageType.UPLINK,
                data=data,
                hex_data=data.hex(),
                timestamp=time.time(),
                rssi=rssi,
                snr=snr,
                station=station,
                metadata=metadata or {}
            )
            
            self._messages[msg_id] = message
            device.last_message = message.timestamp
            device.message_count += 1
            
            await self._notify_observers("message_received", message)
            await self._process_message(message)
            
            return message

    async def _process_message(self, message: SigfoxMessage) -> None:
        handlers = self._handlers.get(message.message_type, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"Handler error for {message.id}: {e}")

    async def decode_message(self, message: SigfoxMessage, format: str = "auto") -> Dict[str, Any]:
        if format == "auto":
            # Try to detect format
            if len(message.data) >= 4:
                return self._decode_sigfox_payload(message.data)
            else:
                return {"hex": message.hex_data}
        
        elif format == "hex":
            return {"hex": message.hex_data}
        
        elif format == "binary":
            return {"binary": ''.join(format(b, '08b') for b in message.data)}
        
        elif format == "struct":
            return self._decode_struct(message.data)
        
        elif format == "json":
            try:
                return json.loads(message.data.decode())
            except:
                return {"error": "Invalid JSON"}
        
        else:
            return {"raw": message.hex_data}

    def _decode_sigfox_payload(self, data: bytes) -> Dict[str, Any]:
        result = {}
        
        if len(data) >= 4:
            temperature = struct.unpack('>h', data[:2])[0] / 10.0
            result["temperature"] = temperature
            
            if len(data) >= 6:
                humidity = struct.unpack('>H', data[2:4])[0] / 10.0
                result["humidity"] = humidity
                
                if len(data) >= 8:
                    pressure = struct.unpack('>I', data[4:8])[0] / 100.0
                    result["pressure"] = pressure
        
        result["raw"] = data.hex()
        return result

    def _decode_struct(self, data: bytes) -> Dict[str, Any]:
        result = {}
        offset = 0
        
        while offset < len(data):
            if offset + 2 <= len(data):
                try:
                    value = struct.unpack_from('>H', data, offset)[0]
                    result[f"field_{offset}"] = value
                    offset += 2
                except:
                    offset += 1
            else:
                offset += 1
        
        return result

    async def create_callback(
        self,
        name: str,
        url: str,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        payload_template: str = "{{data}}",
        metadata: Optional[Dict[str, Any]] = None
    ) -> SigfoxCallback:
        callback_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
        
        callback = SigfoxCallback(
            id=callback_id,
            name=name,
            url=url,
            method=method,
            headers=headers or {},
            payload_template=payload_template,
            metadata=metadata or {}
        )
        
        self._callbacks[callback_id] = callback
        return callback

    async def trigger_callback(self, callback_id: str, data: Any) -> bool:
        if callback_id not in self._callbacks:
            return False
        
        callback = self._callbacks[callback_id]
        
        try:
            await self._ensure_session()
            
            headers = callback.headers.copy()
            headers["Content-Type"] = "application/json"
            
            payload = callback.payload_template
            if "{{data}}" in payload:
                payload = payload.replace("{{data}}", json.dumps(data))
            
            async with self._session.request(
                method=callback.method,
                url=callback.url,
                headers=headers,
                data=payload
            ) as response:
                return response.status in [200, 201, 202]
                
        except Exception as e:
            logger.error(f"Callback error: {e}")
            return False

    async def create_group(self, name: str, device_ids: List[str], metadata: Optional[Dict[str, Any]] = None) -> SigfoxGroup:
        group_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
        
        group = SigfoxGroup(
            id=group_id,
            name=name,
            devices=device_ids,
            metadata=metadata or {}
        )
        
        self._groups[group_id] = group
        return group

    async def get_device(self, device_id: str) -> Optional[SigfoxDevice]:
        return self._devices.get(device_id)

    async def get_devices(self) -> List[SigfoxDevice]:
        return list(self._devices.values())

    async def get_message(self, message_id: str) -> Optional[SigfoxMessage]:
        return self._messages.get(message_id)

    async def get_messages(self, device_id: str, limit: int = 100) -> List[SigfoxMessage]:
        return [m for m in self._messages.values() if m.device_id == device_id][-limit:]

    async def get_callback(self, callback_id: str) -> Optional[SigfoxCallback]:
        return self._callbacks.get(callback_id)

    async def get_callbacks(self) -> List[SigfoxCallback]:
        return list(self._callbacks.values())

    async def get_group(self, group_id: str) -> Optional[SigfoxGroup]:
        return self._groups.get(group_id)

    async def get_groups(self) -> List[SigfoxGroup]:
        return list(self._groups.values())

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    async def start(self) -> None:
        if self._running:
            return
        
        self._running = True
        await self._ensure_session()
        self._processor_task = asyncio.create_task(self._processor_loop())
        logger.info("Sigfox manager started")

    async def stop(self) -> None:
        self._running = False
        
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._processor_task = None
        
        if self._session:
            await self._session.close()
            self._session = None
        
        logger.info("Sigfox manager stopped")

    async def _processor_loop(self) -> None:
        while self._running:
            try:
                # Process queued messages
                try:
                    message = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
                    await self._process_message(message)
                    self._message_queue.task_done()
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Processor error: {e}")
                    await asyncio.sleep(0.1)
                    
            except asyncio.CancelledError:
                break

    def get_stats(self) -> Dict[str, Any]:
        return {
            "devices": len(self._devices),
            "messages": len(self._messages),
            "callbacks": len(self._callbacks),
            "groups": len(self._groups),
            "handlers": sum(len(h) for h in self._handlers.values()),
            "observers": len(self._observers),
            "running": self._running,
            "queue_size": self._message_queue.qsize()
        }


__all__ = [
    "SigfoxDeviceType",
    "SigfoxMessageType",
    "SigfoxProtocol",
    "SigfoxDevice",
    "SigfoxMessage",
    "SigfoxCallback",
    "SigfoxGroup",
    "SigfoxDataManager"
]
