# trading/bots/hedge_bot/hedge_bot_data_thingworx.py

import asyncio
import logging
import time
import json
import hashlib
import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    from thingworx import ThingWorxClient
    THINGWORX_AVAILABLE = True
except ImportError:
    THINGWORX_AVAILABLE = False

logger = logging.getLogger(__name__)


class ThingWorxType(str, Enum):
    THING = "thing"
    THING_TEMPLATE = "thing_template"
    THING_SHAPE = "thing_shape"
    DATA_SHAPE = "data_shape"
    STREAM = "stream"
    VALUE_STREAM = "value_stream"
    PROPERTY = "property"
    EVENT = "event"
    SERVICE = "service"
    ALERT = "alert"


class ThingWorxQuality(str, Enum):
    GOOD = "good"
    BAD = "bad"
    UNKNOWN = "unknown"
    QUESTIONABLE = "questionable"


@dataclass
class ThingWorxConfig:
    host: str
    port: int = 8080
    app_key: str
    use_ssl: bool = False
    timeout: int = 30
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThingWorxProperty:
    name: str
    value: Any
    type: str
    quality: ThingWorxQuality = ThingWorxQuality.GOOD
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThingWorxEvent:
    id: str
    name: str
    data: Any
    source: str
    timestamp: float
    quality: ThingWorxQuality = ThingWorxQuality.GOOD
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThingWorxThing:
    name: str
    thing_type: ThingWorxType
    properties: Dict[str, ThingWorxProperty]
    events: List[ThingWorxEvent]
    services: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class ThingWorxManager:
    
    def __init__(self, config: Optional[ThingWorxConfig] = None):
        self.config = config or ThingWorxConfig(
            host="localhost",
            app_key="default_key"
        )
        self._lock = asyncio.Lock()
        self._session: Optional[aiohttp.ClientSession] = None
        self._client: Optional[Any] = None
        self._things: Dict[str, ThingWorxThing] = {}
        self._properties: Dict[str, Dict[str, ThingWorxProperty]] = defaultdict(dict)
        self._events: Dict[str, ThingWorxEvent] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_client()

    def _initialize_client(self) -> None:
        if THINGWORX_AVAILABLE:
            self._client = ThingWorxClient(
                host=self.config.host,
                port=self.config.port,
                app_key=self.config.app_key,
                use_ssl=self.config.use_ssl
            )
        else:
            logger.warning("ThingWorx SDK not available")

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def _ensure_session(self) -> None:
        if self._session is None and AIOHTTP_AVAILABLE:
            self._session = aiohttp.ClientSession()

    async def connect(self) -> bool:
        try:
            if self._client:
                return await self._client.connect()
            
            await self._ensure_session()
            url = f"{'https' if self.config.use_ssl else 'http'}://{self.config.host}:{self.config.port}/Thingworx"
            
            async with self._session.get(
                url,
                headers={"appKey": self.config.app_key}
            ) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    async def create_thing(
        self,
        name: str,
        thing_type: ThingWorxType,
        properties: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ThingWorxThing]:
        async with self._lock:
            thing_properties = {}
            if properties:
                for prop_name, prop_value in properties.items():
                    thing_properties[prop_name] = ThingWorxProperty(
                        name=prop_name,
                        value=prop_value,
                        type=type(prop_value).__name__
                    )
            
            thing = ThingWorxThing(
                name=name,
                thing_type=thing_type,
                properties=thing_properties,
                events=[],
                services=[],
                metadata=metadata or {}
            )
            
            if self._client:
                try:
                    result = await self._client.create_thing(name, thing_type.value)
                    if result:
                        self._things[name] = thing
                        return thing
                except Exception as e:
                    logger.error(f"Error creating thing: {e}")
                    return None
            
            self._things[name] = thing
            return thing

    async def set_property(
        self,
        thing_name: str,
        property_name: str,
        value: Any,
        quality: ThingWorxQuality = ThingWorxQuality.GOOD
    ) -> bool:
        async with self._lock:
            if thing_name not in self._things:
                return False
            
            property_data = ThingWorxProperty(
                name=property_name,
                value=value,
                type=type(value).__name__,
                quality=quality
            )
            
            self._properties[thing_name][property_name] = property_data
            
            if self._client:
                try:
                    await self._client.set_property(thing_name, property_name, value)
                    return True
                except Exception as e:
                    logger.error(f"Error setting property: {e}")
                    return False
            
            return True

    async def get_property(
        self,
        thing_name: str,
        property_name: str
    ) -> Optional[ThingWorxProperty]:
        if thing_name not in self._properties:
            return None
        
        return self._properties[thing_name].get(property_name)

    async def get_properties(self, thing_name: str) -> Dict[str, ThingWorxProperty]:
        return self._properties.get(thing_name, {})

    async def send_event(
        self,
        thing_name: str,
        event_name: str,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ThingWorxEvent]:
        async with self._lock:
            if thing_name not in self._things:
                return None
            
            event = ThingWorxEvent(
                id=hashlib.md5(f"{thing_name}_{event_name}_{time.time()}".encode()).hexdigest(),
                name=event_name,
                data=data,
                source=thing_name,
                timestamp=time.time(),
                metadata=metadata or {}
            )
            
            self._events[event.id] = event
            
            if self._client:
                try:
                    await self._client.send_event(thing_name, event_name, data)
                except Exception as e:
                    logger.error(f"Error sending event: {e}")
            
            await self._notify_observers("event_sent", event)
            return event

    async def invoke_service(
        self,
        thing_name: str,
        service_name: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        if thing_name not in self._things:
            return None
        
        if self._client:
            try:
                result = await self._client.invoke_service(thing_name, service_name, parameters or {})
                return result
            except Exception as e:
                logger.error(f"Error invoking service: {e}")
                return None
        
        return None

    async def get_thing(self, thing_name: str) -> Optional[ThingWorxThing]:
        return self._things.get(thing_name)

    async def get_things(self) -> List[ThingWorxThing]:
        return list(self._things.values())

    async def get_event(self, event_id: str) -> Optional[ThingWorxEvent]:
        return self._events.get(event_id)

    async def get_events(
        self,
        thing_name: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100
    ) -> List[ThingWorxEvent]:
        events = list(self._events.values())
        
        if thing_name:
            events = [e for e in events if e.source == thing_name]
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]
        
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    async def create_subscription(
        self,
        thing_name: str,
        property_name: str,
        callback: Callable
    ) -> bool:
        if thing_name not in self._things:
            return False
        
        await self._notify_observers("subscription_created", thing_name, property_name)
        return True

    async def get_subscription_status(self, thing_name: str, property_name: str) -> bool:
        return True

    async def get_thing_status(self, thing_name: str) -> Optional[Dict[str, Any]]:
        if thing_name not in self._things:
            return None
        
        thing = self._things[thing_name]
        
        return {
            "name": thing.name,
            "type": thing.thing_type.value,
            "properties": len(thing.properties),
            "events": len(thing.events),
            "services": len(thing.services),
            "created_at": thing.created_at,
            "updated_at": thing.updated_at
        }

    async def get_system_status(self) -> Dict[str, Any]:
        try:
            if self._client:
                return await self._client.get_system_status()
            
            await self._ensure_session()
            url = f"{'https' if self.config.use_ssl else 'http'}://{self.config.host}:{self.config.port}/Thingworx/System/Status"
            
            async with self._session.get(
                url,
                headers={"appKey": self.config.app_key}
            ) as response:
                if response.status == 200:
                    return await response.json()
                return {"status": "error", "code": response.status}
                
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {"status": "error", "message": str(e)}

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "things": len(self._things),
            "properties": sum(len(p) for p in self._properties.values()),
            "events": len(self._events),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "ThingWorxType",
    "ThingWorxQuality",
    "ThingWorxConfig",
    "ThingWorxProperty",
    "ThingWorxEvent",
    "ThingWorxThing",
    "ThingWorxManager"
]
