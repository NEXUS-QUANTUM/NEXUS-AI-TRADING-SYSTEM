# trading/bots/hedge_bot/hedge_bot_data_tracked.py

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


class TrackingType(str, Enum):
    PERFORMANCE = "performance"
    RISK = "risk"
    TRADING = "trading"
    POSITION = "position"
    ORDER = "order"
    PORTFOLIO = "portfolio"
    METRIC = "metric"
    EVENT = "event"
    BEHAVIOR = "behavior"
    COMPLIANCE = "compliance"
    AUDIT = "audit"
    SYSTEM = "system"
    USER = "user"


class TrackingStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING = "pending"


@dataclass
class TrackedItem:
    id: str
    type: TrackingType
    name: str
    value: Any
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    status: TrackingStatus = TrackingStatus.ACTIVE


@dataclass
class TrackedMetric:
    id: str
    name: str
    value: float
    unit: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class TrackedEvent:
    id: str
    type: TrackingType
    name: str
    data: Any
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    severity: str = "info"


@dataclass
class TrackedAggregation:
    id: str
    name: str
    type: str
    value: float
    count: int
    period: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrackingReport:
    id: str
    name: str
    items: List[TrackedItem]
    metrics: List[TrackedMetric]
    events: List[TrackedEvent]
    aggregations: List[TrackedAggregation]
    start_time: float
    end_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataTrackedManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._items: Dict[str, TrackedItem] = {}
        self._metrics: Dict[str, TrackedMetric] = {}
        self._events: Dict[str, TrackedEvent] = {}
        self._aggregations: Dict[str, TrackedAggregation] = {}
        self._reports: Dict[str, TrackingReport] = {}
        self._history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_default_tracking()

    def _initialize_default_tracking(self) -> None:
        pass

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def track_item(
        self,
        type: TrackingType,
        name: str,
        value: Any,
        source: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TrackedItem:
        async with self._lock:
            item_id = hashlib.md5(f"{type.value}_{name}_{time.time()}".encode()).hexdigest()
            
            item = TrackedItem(
                id=item_id,
                type=type,
                name=name,
                value=value,
                timestamp=time.time(),
                source=source,
                tags=tags or [],
                metadata=metadata or {}
            )
            
            self._items[item_id] = item
            self._history[type.value].append(item)
            
            await self._notify_observers("item_tracked", item)
            return item

    async def track_metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        source: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TrackedMetric:
        async with self._lock:
            metric_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            metric = TrackedMetric(
                id=metric_id,
                name=name,
                value=value,
                unit=unit,
                timestamp=time.time(),
                source=source,
                tags=tags or [],
                metadata=metadata or {}
            )
            
            self._metrics[metric_id] = metric
            self._history["metrics"].append(metric)
            
            await self._notify_observers("metric_tracked", metric)
            return metric

    async def track_event(
        self,
        type: TrackingType,
        name: str,
        data: Any,
        source: Optional[str] = None,
        severity: str = "info",
        metadata: Optional[Dict[str, Any]] = None
    ) -> TrackedEvent:
        async with self._lock:
            event_id = hashlib.md5(f"{type.value}_{name}_{time.time()}".encode()).hexdigest()
            
            event = TrackedEvent(
                id=event_id,
                type=type,
                name=name,
                data=data,
                timestamp=time.time(),
                source=source,
                severity=severity,
                metadata=metadata or {}
            )
            
            self._events[event_id] = event
            self._history["events"].append(event)
            
            await self._notify_observers("event_tracked", event)
            return event

    async def aggregate(
        self,
        name: str,
        type: str,
        value: float,
        count: int,
        period: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TrackedAggregation:
        async with self._lock:
            agg_id = hashlib.md5(f"{name}_{type}_{time.time()}".encode()).hexdigest()
            
            agg = TrackedAggregation(
                id=agg_id,
                name=name,
                type=type,
                value=value,
                count=count,
                period=period,
                timestamp=time.time(),
                metadata=metadata or {}
            )
            
            self._aggregations[agg_id] = agg
            await self._notify_observers("aggregation_created", agg)
            return agg

    async def get_item(self, item_id: str) -> Optional[TrackedItem]:
        return self._items.get(item_id)

    async def get_items(
        self,
        type: Optional[TrackingType] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100
    ) -> List[TrackedItem]:
        items = list(self._items.values())
        
        if type:
            items = [i for i in items if i.type == type]
        if start_time:
            items = [i for i in items if i.timestamp >= start_time]
        if end_time:
            items = [i for i in items if i.timestamp <= end_time]
        
        items.sort(key=lambda i: i.timestamp, reverse=True)
        return items[:limit]

    async def get_metric(self, metric_id: str) -> Optional[TrackedMetric]:
        return self._metrics.get(metric_id)

    async def get_metrics(
        self,
        name: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100
    ) -> List[TrackedMetric]:
        metrics = list(self._metrics.values())
        
        if name:
            metrics = [m for m in metrics if m.name == name]
        if start_time:
            metrics = [m for m in metrics if m.timestamp >= start_time]
        if end_time:
            metrics = [m for m in metrics if m.timestamp <= end_time]
        
        metrics.sort(key=lambda m: m.timestamp, reverse=True)
        return metrics[:limit]

    async def get_event(self, event_id: str) -> Optional[TrackedEvent]:
        return self._events.get(event_id)

    async def get_events(
        self,
        type: Optional[TrackingType] = None,
        severity: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: int = 100
    ) -> List[TrackedEvent]:
        events = list(self._events.values())
        
        if type:
            events = [e for e in events if e.type == type]
        if severity:
            events = [e for e in events if e.severity == severity]
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]
        
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    async def get_aggregation(self, agg_id: str) -> Optional[TrackedAggregation]:
        return self._aggregations.get(agg_id)

    async def get_aggregations(
        self,
        name: Optional[str] = None,
        period: Optional[str] = None,
        limit: int = 100
    ) -> List[TrackedAggregation]:
        aggs = list(self._aggregations.values())
        
        if name:
            aggs = [a for a in aggs if a.name == name]
        if period:
            aggs = [a for a in aggs if a.period == period]
        
        aggs.sort(key=lambda a: a.timestamp, reverse=True)
        return aggs[:limit]

    async def get_history(
        self,
        type: Optional[TrackingType] = None,
        limit: int = 100
    ) -> List[Any]:
        if type:
            return list(self._history[type.value])[-limit:]
        
        all_history = []
        for items in self._history.values():
            all_history.extend(items)
        all_history.sort(key=lambda x: x.timestamp, reverse=True)
        return all_history[:limit]

    async def create_report(
        self,
        name: str,
        start_time: float,
        end_time: float,
        types: Optional[List[TrackingType]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TrackingReport:
        async with self._lock:
            report_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            items = await self.get_items(start_time=start_time, end_time=end_time, limit=10000)
            metrics = await self.get_metrics(start_time=start_time, end_time=end_time, limit=10000)
            events = await self.get_events(start_time=start_time, end_time=end_time, limit=10000)
            
            if types:
                items = [i for i in items if i.type in types]
                events = [e for e in events if e.type in types]
            
            aggregations = []
            for metric in metrics:
                agg = await self.aggregate(
                    name=metric.name,
                    type="avg",
                    value=metric.value,
                    count=1,
                    period="report"
                )
                aggregations.append(agg)
            
            report = TrackingReport(
                id=report_id,
                name=name,
                items=items,
                metrics=metrics,
                events=events,
                aggregations=aggregations,
                start_time=start_time,
                end_time=end_time,
                metadata=metadata or {}
            )
            
            self._reports[report_id] = report
            await self._notify_observers("report_created", report)
            return report

    async def get_report(self, report_id: str) -> Optional[TrackingReport]:
        return self._reports.get(report_id)

    async def get_reports(self) -> List[TrackingReport]:
        return list(self._reports.values())

    async def compute_statistics(
        self,
        item_type: TrackingType,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> Dict[str, Any]:
        items = await self.get_items(type=item_type, start_time=start_time, end_time=end_time)
        
        if not items:
            return {}
        
        values = []
        for item in items:
            if isinstance(item.value, (int, float)):
                values.append(float(item.value))
        
        if not values:
            return {}
        
        stats = {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "sum": sum(values),
            "mean": sum(values) / len(values),
            "std": np.std(values) if len(values) > 1 else 0,
            "median": sorted(values)[len(values) // 2] if values else 0
        }
        
        return stats

    async def clear_old_data(self, days: int = 30) -> int:
        cutoff = time.time() - days * 86400
        count = 0
        
        for key, item in list(self._items.items()):
            if item.timestamp < cutoff:
                del self._items[key]
                count += 1
        
        for key, metric in list(self._metrics.items()):
            if metric.timestamp < cutoff:
                del self._metrics[key]
                count += 1
        
        for key, event in list(self._events.items()):
            if event.timestamp < cutoff:
                del self._events[key]
                count += 1
        
        return count

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
            "items": len(self._items),
            "metrics": len(self._metrics),
            "events": len(self._events),
            "aggregations": len(self._aggregations),
            "reports": len(self._reports),
            "history_size": sum(len(h) for h in self._history.values()),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "TrackingType",
    "TrackingStatus",
    "TrackedItem",
    "TrackedMetric",
    "TrackedEvent",
    "TrackedAggregation",
    "TrackingReport",
    "DataTrackedManager"
]
