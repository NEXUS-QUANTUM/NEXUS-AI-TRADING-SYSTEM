# trading/bots/hedge_bot/hedge_bot_data_splunk.py/

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
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    from splunklib import client as splunk_client
    from splunklib import results as splunk_results
    from splunklib.binding import HTTPError
    SPLUNK_AVAILABLE = True
except ImportError:
    SPLUNK_AVAILABLE = False

logger = logging.getLogger(__name__)


class SplunkIndex(str, Enum):
    TRADING = "trading"
    ORDERS = "orders"
    POSITIONS = "positions"
    RISK = "risk"
    PERFORMANCE = "performance"
    LOGS = "logs"
    METRICS = "metrics"
    ALERTS = "alerts"
    AUDIT = "audit"
    SYSTEM = "system"
    SECURITY = "security"
    CUSTOM = "custom"


class SplunkSearchMode(str, Enum):
    NORMAL = "normal"
    REAL_TIME = "realtime"
    HISTORICAL = "historical"
    SCHEDULED = "scheduled"
    ALERT = "alert"


class SplunkOutputMode(str, Enum):
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    RAW = "raw"
    TABLE = "table"


@dataclass
class SplunkConfig:
    host: str
    port: int = 8089
    username: str
    password: str
    scheme: str = "https"
    verify_ssl: bool = True
    timeout: int = 30
    max_retries: int = 3
    index: str = "main"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SplunkEvent:
    id: str
    index: SplunkIndex
    sourcetype: str
    source: str
    host: str
    data: Dict[str, Any]
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SplunkQuery:
    id: str
    query: str
    mode: SplunkSearchMode
    earliest_time: Optional[str] = None
    latest_time: Optional[str] = None
    limit: int = 10000
    output_mode: SplunkOutputMode = SplunkOutputMode.JSON
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SplunkResult:
    id: str
    query_id: str
    data: Any
    count: int
    execution_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SplunkAlert:
    id: str
    name: str
    query: str
    condition: str
    severity: str
    enabled: bool = True
    last_triggered: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DataSplunkManager:
    
    def __init__(self, config: Optional[SplunkConfig] = None):
        self.config = config or SplunkConfig(
            host="localhost",
            username="admin",
            password="changeme"
        )
        self._lock = asyncio.Lock()
        self._service: Optional[splunk_client.Service] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._events: Dict[str, SplunkEvent] = {}
        self._queries: Dict[str, SplunkQuery] = {}
        self._results: Dict[str, SplunkResult] = {}
        self._alerts: Dict[str, SplunkAlert] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_client()
        self._initialize_default_alerts()

    def _initialize_client(self) -> None:
        if not SPLUNK_AVAILABLE:
            logger.warning("Splunk SDK not available")
            return
        
        self._service = splunk_client.connect(
            host=self.config.host,
            port=self.config.port,
            username=self.config.username,
            password=self.config.password,
            scheme=self.config.scheme,
            verify=self.config.verify_ssl
        )

    def _initialize_default_alerts(self) -> None:
        default_alerts = [
            SplunkAlert(
                id="high_pnl_drop",
                name="High PnL Drop Alert",
                query='index="trading" | stats sum(pnl) as total_pnl | where total_pnl < -1000',
                condition="total_pnl < -1000",
                severity="critical"
            ),
            SplunkAlert(
                id="unusual_volume",
                name="Unusual Volume Alert",
                query='index="trading" | stats sum(volume) as total_volume | where total_volume > 1000000',
                condition="total_volume > 1000000",
                severity="warning"
            ),
            SplunkAlert(
                id="position_threshold",
                name="Position Threshold Alert",
                query='index="positions" | stats count(*) as position_count | where position_count > 100',
                condition="position_count > 100",
                severity="warning"
            )
        ]
        
        for alert in default_alerts:
            self._alerts[alert.id] = alert

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def _ensure_session(self) -> None:
        if self._session is None and AIOHTTP_AVAILABLE:
            self._session = aiohttp.ClientSession()

    async def send_event(
        self,
        index: SplunkIndex,
        sourcetype: str,
        data: Dict[str, Any],
        source: Optional[str] = None,
        host: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[SplunkEvent]:
        async with self._lock:
            event_id = hashlib.md5(f"{index.value}_{time.time()}".encode()).hexdigest()
            
            event = SplunkEvent(
                id=event_id,
                index=index,
                sourcetype=sourcetype,
                source=source or "hedge_bot",
                host=host or self.config.host,
                data=data,
                timestamp=time.time(),
                metadata=metadata or {}
            )
            
            self._events[event_id] = event
            
            success = await self._send_to_splunk(event)
            
            if success:
                await self._notify_observers("event_sent", event)
            else:
                await self._notify_observers("event_failed", event)
            
            return event if success else None

    async def _send_to_splunk(self, event: SplunkEvent) -> bool:
        try:
            if not self._service:
                return False
            
            try:
                self._service.indexes[event.index.value].submit(
                    json.dumps(event.data),
                    sourcetype=event.sourcetype,
                    source=event.source,
                    host=event.host
                )
                return True
            except Exception as e:
                logger.error(f"Splunk client error: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Error sending to Splunk: {e}")
            return False

    async def search(
        self,
        query: str,
        mode: SplunkSearchMode = SplunkSearchMode.NORMAL,
        earliest_time: Optional[str] = None,
        latest_time: Optional[str] = None,
        limit: int = 10000,
        output_mode: SplunkOutputMode = SplunkOutputMode.JSON,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[SplunkResult]:
        async with self._lock:
            query_id = hashlib.md5(f"{query}_{time.time()}".encode()).hexdigest()
            
            splunk_query = SplunkQuery(
                id=query_id,
                query=query,
                mode=mode,
                earliest_time=earliest_time,
                latest_time=latest_time,
                limit=limit,
                output_mode=output_mode,
                metadata=metadata or {}
            )
            
            self._queries[query_id] = splunk_query
            
            start_time = time.time()
            
            try:
                result_data = await self._execute_search(splunk_query)
                
                result = SplunkResult(
                    id=hashlib.md5(f"{query_id}_{time.time()}".encode()).hexdigest(),
                    query_id=query_id,
                    data=result_data,
                    count=len(result_data) if isinstance(result_data, list) else 0,
                    execution_time=time.time() - start_time,
                    metadata=metadata or {}
                )
                
                self._results[result.id] = result
                await self._notify_observers("search_completed", result)
                return result
                
            except Exception as e:
                logger.error(f"Search error: {e}")
                await self._notify_observers("search_failed", query_id, str(e))
                return None

    async def _execute_search(self, query: SplunkQuery) -> Any:
        if not self._service:
            raise RuntimeError("Splunk service not initialized")
        
        search_kwargs = {
            "search": query.query,
            "output_mode": query.output_mode.value,
            "earliest_time": query.earliest_time or "-24h",
            "latest_time": query.latest_time or "now",
            "limit": query.limit
        }
        
        if query.mode == SplunkSearchMode.REAL_TIME:
            search_kwargs["real_time"] = "true"
        
        try:
            job = self._service.jobs.create(**search_kwargs)
            
            while True:
                job.refresh()
                if job["isDone"] == "1":
                    break
                await asyncio.sleep(0.5)
            
            results = splunk_results.ResultsReader(job.results())
            
            if query.output_mode == SplunkOutputMode.JSON:
                return [r for r in results]
            else:
                return results
            
        except Exception as e:
            logger.error(f"Search execution error: {e}")
            raise

    async def create_saved_search(
        self,
        name: str,
        query: str,
        enabled: bool = True,
        schedule: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        try:
            if not self._service:
                return False
            
            saved_search = self._service.saved_searches.create(
                name,
                search=query,
                is_scheduled=bool(schedule),
                cron_schedule=schedule,
                enabled=enabled
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating saved search: {e}")
            return False

    async def create_alert(
        self,
        name: str,
        query: str,
        condition: str,
        severity: str = "warning",
        enabled: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SplunkAlert:
        alert_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
        
        alert = SplunkAlert(
            id=alert_id,
            name=name,
            query=query,
            condition=condition,
            severity=severity,
            enabled=enabled,
            metadata=metadata or {}
        )
        
        self._alerts[alert_id] = alert
        await self._notify_observers("alert_created", alert)
        return alert

    async def trigger_alert(self, alert_id: str) -> bool:
        if alert_id not in self._alerts:
            return False
        
        alert = self._alerts[alert_id]
        
        if not alert.enabled:
            return False
        
        try:
            result = await self.search(alert.query, limit=1)
            
            if result and result.count > 0:
                await self._evaluate_condition(alert, result)
                alert.last_triggered = time.time()
                await self._notify_observers("alert_triggered", alert)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error triggering alert: {e}")
            return False

    async def _evaluate_condition(self, alert: SplunkAlert, result: SplunkResult) -> None:
        try:
            if alert.condition:
                import re
                
                condition = alert.condition
                if re.match(r'^[\w\.]+\s*[<>=!]+\s*[\d\.]+$', condition):
                    field, op, value = re.split(r'\s*([<>=!]+)\s*', condition)
                    
                    if isinstance(result.data, list) and len(result.data) > 0:
                        if field in result.data[0]:
                            actual_value = result.data[0][field]
                            if eval(f"{actual_value} {op} {value}"):
                                logger.info(f"Alert triggered: {alert.name}")
                else:
                    logger.info(f"Alert condition evaluated: {alert.name}")
                    
        except Exception as e:
            logger.error(f"Error evaluating condition: {e}")

    async def get_event(self, event_id: str) -> Optional[SplunkEvent]:
        return self._events.get(event_id)

    async def get_events(self, index: Optional[SplunkIndex] = None) -> List[SplunkEvent]:
        if index:
            return [e for e in self._events.values() if e.index == index]
        return list(self._events.values())

    async def get_query(self, query_id: str) -> Optional[SplunkQuery]:
        return self._queries.get(query_id)

    async def get_result(self, result_id: str) -> Optional[SplunkResult]:
        return self._results.get(result_id)

    async def get_alert(self, alert_id: str) -> Optional[SplunkAlert]:
        return self._alerts.get(alert_id)

    async def get_alerts(self, enabled: Optional[bool] = None) -> List[SplunkAlert]:
        if enabled is not None:
            return [a for a in self._alerts.values() if a.enabled == enabled]
        return list(self._alerts.values())

    async def enable_alert(self, alert_id: str) -> bool:
        if alert_id in self._alerts:
            self._alerts[alert_id].enabled = True
            return True
        return False

    async def disable_alert(self, alert_id: str) -> bool:
        if alert_id in self._alerts:
            self._alerts[alert_id].enabled = False
            return True
        return False

    async def delete_alert(self, alert_id: str) -> bool:
        if alert_id in self._alerts:
            del self._alerts[alert_id]
            return True
        return False

    async def get_metrics(self, metric_name: str, time_range: str = "-1h") -> Optional[Dict[str, Any]]:
        query = f'index="metrics" | stats avg({metric_name}) as avg_metric, max({metric_name}) as max_metric, min({metric_name}) as min_metric, count(*) as count | eval time_range="{time_range}"'
        
        result = await self.search(query, earliest_time=time_range)
        
        if result and result.data:
            if isinstance(result.data, list) and len(result.data) > 0:
                return result.data[0]
        
        return None

    async def get_system_health(self) -> Dict[str, Any]:
        metrics = {}
        
        for metric in ["cpu_usage", "memory_usage", "disk_usage", "connections"]:
            value = await self.get_metrics(metric)
            if value:
                metrics[metric] = value
        
        query = 'index="system" | stats count(*) as events | eval status="online"'
        result = await self.search(query)
        
        if result and result.data:
            if isinstance(result.data, list) and len(result.data) > 0:
                metrics.update(result.data[0])
        
        return metrics

    async def get_performance_report(self, time_range: str = "-24h") -> Dict[str, Any]:
        queries = {
            "total_pnl": f'index="trading" | stats sum(pnl) as total_pnl | eval time_range="{time_range}"',
            "win_rate": f'index="trading" | stats count(eval(pnl>0)) as wins, count(eval(pnl<0)) as losses | eval win_rate=wins/(wins+losses)*100',
            "total_trades": f'index="trading" | stats count(*) as total_trades | eval time_range="{time_range}"',
            "avg_pnl": f'index="trading" | stats avg(pnl) as avg_pnl | eval time_range="{time_range}"',
            "max_drawdown": f'index="positions" | stats min(pnl) as max_drawdown | eval time_range="{time_range}"'
        }
        
        report = {}
        for key, query in queries.items():
            result = await self.search(query, earliest_time=time_range)
            if result and result.data:
                if isinstance(result.data, list) and len(result.data) > 0:
                    report[key] = result.data[0].get(key, result.data[0].get("total_pnl", 0))
                else:
                    report[key] = 0
            else:
                report[key] = 0
        
        return report

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    def get_stats(self) -> Dict[str, Any]:
        return {
            "events": len(self._events),
            "queries": len(self._queries),
            "results": len(self._results),
            "alerts": len(self._alerts),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "SplunkIndex",
    "SplunkSearchMode",
    "SplunkOutputMode",
    "SplunkConfig",
    "SplunkEvent",
    "SplunkQuery",
    "SplunkResult",
    "SplunkAlert",
    "DataSplunkManager"
]
