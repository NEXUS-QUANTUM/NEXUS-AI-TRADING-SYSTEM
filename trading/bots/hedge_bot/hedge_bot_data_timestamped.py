# trading/bots/hedge_bot/hedge_bot_data_timestamped.py

import asyncio
import logging
import time
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class TimestampPrecision(str, Enum):
    MILLISECOND = "ms"
    SECOND = "s"
    MINUTE = "m"
    HOUR = "h"
    DAY = "d"
    WEEK = "w"
    MONTH = "M"
    YEAR = "Y"


class TimestampStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    EXPIRED = "expired"
    CORRUPTED = "corrupted"


@dataclass
class TimestampedData:
    id: str
    data: Any
    timestamp: float
    precision: TimestampPrecision
    source: Optional[str] = None
    status: TimestampStatus = TimestampStatus.ACTIVE
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    version: int = 1


@dataclass
class TimestampedRange:
    id: str
    start_time: float
    end_time: float
    data: List[TimestampedData]
    count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TimestampedAggregation:
    id: str
    name: str
    timestamp: float
    precision: TimestampPrecision
    value: Any
    count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TimestampedSeries:
    id: str
    name: str
    data: List[TimestampedData]
    start_time: float
    end_time: float
    count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataTimestampedManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._data: Dict[str, TimestampedData] = {}
        self._ranges: Dict[str, TimestampedRange] = {}
        self._aggregations: Dict[str, TimestampedAggregation] = {}
        self._series: Dict[str, TimestampedSeries] = {}
        self._index: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_default_precision()

    def _initialize_default_precision(self) -> None:
        self._default_precision = TimestampPrecision.MILLISECOND

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def add_data(
        self,
        data: Any,
        timestamp: Optional[float] = None,
        precision: TimestampPrecision = TimestampPrecision.MILLISECOND,
        source: Optional[str] = None,
        expires_in: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TimestampedData:
        async with self._lock:
            if timestamp is None:
                timestamp = time.time()
            
            data_id = hashlib.md5(f"{str(data)}_{timestamp}_{time.time()}".encode()).hexdigest()
            
            ts_data = TimestampedData(
                id=data_id,
                data=data,
                timestamp=timestamp,
                precision=precision,
                source=source,
                metadata=metadata or {},
                expires_at=time.time() + expires_in if expires_in else None
            )
            
            self._data[data_id] = ts_data
            
            self._index["timestamp"][self._format_timestamp(timestamp, precision)].add(data_id)
            if source:
                self._index["source"][source].add(data_id)
            
            await self._notify_observers("data_added", ts_data)
            return ts_data

    async def get_data(
        self,
        data_id: str,
        include_expired: bool = False
    ) -> Optional[TimestampedData]:
        data = self._data.get(data_id)
        if data and not include_expired and data.expires_at and data.expires_at < time.time():
            return None
        return data

    async def get_data_by_time(
        self,
        start_time: float,
        end_time: float,
        precision: TimestampPrecision = TimestampPrecision.MILLISECOND,
        source: Optional[str] = None,
        limit: int = 1000
    ) -> List[TimestampedData]:
        start_key = self._format_timestamp(start_time, precision)
        end_key = self._format_timestamp(end_time, precision)
        
        data_ids = set()
        for key in self._index["timestamp"].keys():
            if start_key <= key <= end_key:
                data_ids.update(self._index["timestamp"][key])
        
        if source:
            source_ids = self._index["source"].get(source, set())
            data_ids = data_ids.intersection(source_ids)
        
        result = []
        for data_id in data_ids:
            if data_id in self._data:
                data = self._data[data_id]
                if data.expires_at and data.expires_at < time.time():
                    continue
                result.append(data)
        
        result.sort(key=lambda x: x.timestamp)
        return result[:limit]

    async def get_data_by_source(
        self,
        source: str,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 1000
    ) -> List[TimestampedData]:
        data_ids = self._index["source"].get(source, set())
        
        result = []
        for data_id in data_ids:
            if data_id in self._data:
                data = self._data[data_id]
                if data.expires_at and data.expires_at < time.time():
                    continue
                if start_time and data.timestamp < start_time:
                    continue
                if end_time and data.timestamp > end_time:
                    continue
                result.append(data)
        
        result.sort(key=lambda x: x.timestamp)
        return result[:limit]

    async def get_range(
        self,
        start_time: float,
        end_time: float,
        precision: TimestampPrecision = TimestampPrecision.MILLISECOND,
        source: Optional[str] = None
    ) -> TimestampedRange:
        async with self._lock:
            range_id = hashlib.md5(f"{start_time}_{end_time}_{time.time()}".encode()).hexdigest()
            
            data = await self.get_data_by_time(start_time, end_time, precision, source)
            
            range_data = TimestampedRange(
                id=range_id,
                start_time=start_time,
                end_time=end_time,
                data=data,
                count=len(data)
            )
            
            self._ranges[range_id] = range_data
            return range_data

    async def aggregate(
        self,
        data_ids: List[str],
        aggregation_type: str,
        precision: TimestampPrecision = TimestampPrecision.MILLISECOND,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[TimestampedAggregation]:
        async with self._lock:
            data_list = []
            for data_id in data_ids:
                if data_id in self._data:
                    data = self._data[data_id]
                    if not (data.expires_at and data.expires_at < time.time()):
                        data_list.append(data)
            
            if not data_list:
                return []
            
            aggregations = []
            
            if aggregation_type == "sum":
                grouped = defaultdict(float)
                for data in data_list:
                    key = self._format_timestamp(data.timestamp, precision)
                    if isinstance(data.data, (int, float)):
                        grouped[key] += data.data
                
                for key, value in grouped.items():
                    agg = TimestampedAggregation(
                        id=hashlib.md5(f"{key}_{time.time()}".encode()).hexdigest(),
                        name="sum",
                        timestamp=self._parse_timestamp(key, precision),
                        precision=precision,
                        value=value,
                        count=1,
                        metadata=metadata or {}
                    )
                    aggregations.append(agg)
            
            elif aggregation_type == "avg":
                grouped = defaultdict(list)
                for data in data_list:
                    key = self._format_timestamp(data.timestamp, precision)
                    if isinstance(data.data, (int, float)):
                        grouped[key].append(data.data)
                
                for key, values in grouped.items():
                    avg = sum(values) / len(values)
                    agg = TimestampedAggregation(
                        id=hashlib.md5(f"{key}_{time.time()}".encode()).hexdigest(),
                        name="avg",
                        timestamp=self._parse_timestamp(key, precision),
                        precision=precision,
                        value=avg,
                        count=len(values),
                        metadata=metadata or {}
                    )
                    aggregations.append(agg)
            
            elif aggregation_type == "count":
                grouped = defaultdict(int)
                for data in data_list:
                    key = self._format_timestamp(data.timestamp, precision)
                    grouped[key] += 1
                
                for key, value in grouped.items():
                    agg = TimestampedAggregation(
                        id=hashlib.md5(f"{key}_{time.time()}".encode()).hexdigest(),
                        name="count",
                        timestamp=self._parse_timestamp(key, precision),
                        precision=precision,
                        value=value,
                        count=value,
                        metadata=metadata or {}
                    )
                    aggregations.append(agg)
            
            elif aggregation_type == "min":
                grouped = defaultdict(float)
                for data in data_list:
                    key = self._format_timestamp(data.timestamp, precision)
                    if isinstance(data.data, (int, float)):
                        if key not in grouped or data.data < grouped[key]:
                            grouped[key] = data.data
                
                for key, value in grouped.items():
                    agg = TimestampedAggregation(
                        id=hashlib.md5(f"{key}_{time.time()}".encode()).hexdigest(),
                        name="min",
                        timestamp=self._parse_timestamp(key, precision),
                        precision=precision,
                        value=value,
                        count=1,
                        metadata=metadata or {}
                    )
                    aggregations.append(agg)
            
            elif aggregation_type == "max":
                grouped = defaultdict(float)
                for data in data_list:
                    key = self._format_timestamp(data.timestamp, precision)
                    if isinstance(data.data, (int, float)):
                        if key not in grouped or data.data > grouped[key]:
                            grouped[key] = data.data
                
                for key, value in grouped.items():
                    agg = TimestampedAggregation(
                        id=hashlib.md5(f"{key}_{time.time()}".encode()).hexdigest(),
                        name="max",
                        timestamp=self._parse_timestamp(key, precision),
                        precision=precision,
                        value=value,
                        count=1,
                        metadata=metadata or {}
                    )
                    aggregations.append(agg)
            
            self._aggregations.update({agg.id: agg for agg in aggregations})
            return aggregations

    async def create_series(
        self,
        name: str,
        data_ids: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[TimestampedSeries]:
        async with self._lock:
            data_list = []
            for data_id in data_ids:
                if data_id in self._data:
                    data = self._data[data_id]
                    if not (data.expires_at and data.expires_at < time.time()):
                        data_list.append(data)
            
            if not data_list:
                return None
            
            data_list.sort(key=lambda x: x.timestamp)
            
            series = TimestampedSeries(
                id=hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest(),
                name=name,
                data=data_list,
                start_time=data_list[0].timestamp,
                end_time=data_list[-1].timestamp,
                count=len(data_list),
                metadata=metadata or {}
            )
            
            self._series[series.id] = series
            return series

    async def get_series(self, series_id: str) -> Optional[TimestampedSeries]:
        return self._series.get(series_id)

    async def get_series_by_name(self, name: str) -> List[TimestampedSeries]:
        return [s for s in self._series.values() if s.name == name]

    async def get_aggregation(self, agg_id: str) -> Optional[TimestampedAggregation]:
        return self._aggregations.get(agg_id)

    async def get_aggregations(
        self,
        name: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100
    ) -> List[TimestampedAggregation]:
        aggs = list(self._aggregations.values())
        
        if name:
            aggs = [a for a in aggs if a.name == name]
        if start_time:
            aggs = [a for a in aggs if a.timestamp >= start_time]
        if end_time:
            aggs = [a for a in aggs if a.timestamp <= end_time]
        
        aggs.sort(key=lambda a: a.timestamp, reverse=True)
        return aggs[:limit]

    async def get_range(self, range_id: str) -> Optional[TimestampedRange]:
        return self._ranges.get(range_id)

    async def get_ranges(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100
    ) -> List[TimestampedRange]:
        ranges = list(self._ranges.values())
        
        if start_time:
            ranges = [r for r in ranges if r.start_time >= start_time]
        if end_time:
            ranges = [r for r in ranges if r.end_time <= end_time]
        
        ranges.sort(key=lambda r: r.start_time, reverse=True)
        return ranges[:limit]

    async def delete_expired(self) -> int:
        now = time.time()
        count = 0
        
        for data_id, data in list(self._data.items()):
            if data.expires_at and data.expires_at < now:
                del self._data[data_id]
                
                for index_type in self._index:
                    for key in list(self._index[index_type].keys()):
                        if data_id in self._index[index_type][key]:
                            self._index[index_type][key].remove(data_id)
                            if not self._index[index_type][key]:
                                del self._index[index_type][key]
                count += 1
        
        return count

    async def get_stats(self) -> Dict[str, Any]:
        return {
            "total_data": len(self._data),
            "ranges": len(self._ranges),
            "aggregations": len(self._aggregations),
            "series": len(self._series),
            "index_size": sum(len(v) for v in self._index["timestamp"].values()),
            "running": self._running
        }

    def _format_timestamp(self, timestamp: float, precision: TimestampPrecision) -> str:
        if precision == TimestampPrecision.MILLISECOND:
            return str(int(timestamp * 1000))
        elif precision == TimestampPrecision.SECOND:
            return str(int(timestamp))
        elif precision == TimestampPrecision.MINUTE:
            return str(int(timestamp / 60))
        elif precision == TimestampPrecision.HOUR:
            return str(int(timestamp / 3600))
        elif precision == TimestampPrecision.DAY:
            return str(int(timestamp / 86400))
        elif precision == TimestampPrecision.WEEK:
            return str(int(timestamp / 604800))
        elif precision == TimestampPrecision.MONTH:
            return str(int(timestamp / 2592000))
        elif precision == TimestampPrecision.YEAR:
            return str(int(timestamp / 31536000))
        else:
            return str(int(timestamp * 1000))

    def _parse_timestamp(self, key: str, precision: TimestampPrecision) -> float:
        value = int(key)
        if precision == TimestampPrecision.MILLISECOND:
            return value / 1000.0
        elif precision == TimestampPrecision.SECOND:
            return float(value)
        elif precision == TimestampPrecision.MINUTE:
            return value * 60.0
        elif precision == TimestampPrecision.HOUR:
            return value * 3600.0
        elif precision == TimestampPrecision.DAY:
            return value * 86400.0
        elif precision == TimestampPrecision.WEEK:
            return value * 604800.0
        elif precision == TimestampPrecision.MONTH:
            return value * 2592000.0
        elif precision == TimestampPrecision.YEAR:
            return value * 31536000.0
        else:
            return value / 1000.0

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")


__all__ = [
    "TimestampPrecision",
    "TimestampStatus",
    "TimestampedData",
    "TimestampedRange",
    "TimestampedAggregation",
    "TimestampedSeries",
    "DataTimestampedManager"
]
