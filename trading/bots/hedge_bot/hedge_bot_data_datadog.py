# trading/bots/hedge_bot/hedge_bot_data_datadog.py
# NEXUS AI TRADING SYSTEM - Hedge Bot DataDog Integration Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot DataDog Integration Module

This module provides comprehensive DataDog monitoring and observability
integration for the NEXUS Hedge Bot system. It sends metrics, traces,
and logs to DataDog for centralized monitoring.

The module covers:
- DataDog API Integration
- Metrics Submission
- Event Tracking
- Trace Collection
- Log Management
- Dashboard Integration
- Alert Configuration
- Performance Monitoring
"""

import os
import sys
import json
import logging
import time
import threading
from typing import Dict, Any, Optional, List, Union, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum

# Try to import DataDog libraries
try:
    from datadog_api_client import ApiClient, Configuration
    from datadog_api_client.v1.api.metrics_api import MetricsApi
    from datadog_api_client.v1.api.events_api import EventsApi
    from datadog_api_client.v2.api.logs_api import LogsApi
    from datadog_api_client.v1.model.event import Event
    from datadog_api_client.v1.model.event_alert_type import EventAlertType
    from datadog_api_client.v1.model.event_priority import EventPriority
    from datadog_api_client.v1.model.event_aggregation import EventAggregation
    from datadog_api_client.v1.model.event_create_response import EventCreateResponse
    HAS_DATADOG = True
except ImportError:
    HAS_DATADOG = False

try:
    from ddtrace import tracer, patch_all
    HAS_DDTRACE = True
except ImportError:
    HAS_DDTRACE = False

logger = logging.getLogger(__name__)


# ============================================================
# DATADOG ENUMS
# ============================================================

class MetricType(Enum):
    """Metric types"""
    COUNT = "count"
    GAUGE = "gauge"
    RATE = "rate"
    HISTOGRAM = "histogram"
    DISTRIBUTION = "distribution"


class EventType(Enum):
    """Event types"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


@dataclass
class DataDogConfig:
    """DataDog configuration"""
    api_key: str
    app_key: str
    site: str = "datadoghq.com"
    service: str = "nexus-hedge-bot"
    env: str = "production"
    version: str = "2.0.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "site": self.site,
            "service": self.service,
            "env": self.env,
            "version": self.version,
        }


@dataclass
class DataDogMetric:
    """DataDog metric"""
    name: str
    value: float
    type: MetricType
    tags: Dict[str, str]
    timestamp: datetime = field(default_factory=datetime.now)
    host: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "value": self.value,
            "type": self.type.value,
            "tags": self.tags,
            "timestamp": self.timestamp.isoformat(),
            "host": self.host,
        }


@dataclass
class DataDogEvent:
    """DataDog event"""
    title: str
    text: str
    event_type: EventType
    tags: Dict[str, str]
    timestamp: datetime = field(default_factory=datetime.now)
    host: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "title": self.title,
            "text": self.text,
            "event_type": self.event_type.value,
            "tags": self.tags,
            "timestamp": self.timestamp.isoformat(),
            "host": self.host,
        }


# ============================================================
# DATADOG ENGINE
# ============================================================

class DataDogEngine:
    """
    Comprehensive DataDog integration engine
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the DataDog engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        
        if not HAS_DATADOG:
            logger.warning("DataDog libraries not installed")
        
        # Load configuration
        self.datadog_config = DataDogConfig(
            api_key=self.config.get("api_key", ""),
            app_key=self.config.get("app_key", ""),
            site=self.config.get("site", "datadoghq.com"),
            service=self.config.get("service", "nexus-hedge-bot"),
            env=self.config.get("env", "production"),
        )
        
        # API client
        self.api_client = None
        self.metrics_api = None
        self.events_api = None
        self.logs_api = None
        
        # Initialize client
        self._init_client()
        
        # Initialize ddtrace
        if HAS_DDTRACE:
            self._init_ddtrace()
        
        # State
        self.metrics_buffer: List[DataDogMetric] = []
        self.events_buffer: List[DataDogEvent] = []
        self.buffer_size = self.config.get("buffer_size", 100)
        self.flush_interval = self.config.get("flush_interval", 60)  # seconds
        
        # Background flush thread
        self.is_running = False
        self.flush_thread: Optional[threading.Thread] = None
        
        logger.info("DataDog engine initialized")
    
    # ============================================================
    # INITIALIZATION
    # ============================================================
    
    def _init_client(self) -> None:
        """Initialize DataDog client"""
        if not HAS_DATADOG:
            return
        
        try:
            configuration = Configuration()
            configuration.api_key["apiKeyAuth"] = self.datadog_config.api_key
            configuration.api_key["appKeyAuth"] = self.datadog_config.app_key
            configuration.server_variables["site"] = self.datadog_config.site
            
            self.api_client = ApiClient(configuration)
            self.metrics_api = MetricsApi(self.api_client)
            self.events_api = EventsApi(self.api_client)
            self.logs_api = LogsApi(self.api_client)
            
            logger.info("DataDog client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize DataDog client: {e}")
    
    def _init_ddtrace(self) -> None:
        """Initialize ddtrace"""
        if not HAS_DDTRACE:
            return
        
        try:
            tracer.configure(
                hostname="localhost",
                port=8126,
                env=self.datadog_config.env,
                service=self.datadog_config.service,
                version=self.datadog_config.version,
            )
            patch_all()
            logger.info("ddtrace initialized")
        except Exception as e:
            logger.error(f"Failed to initialize ddtrace: {e}")
    
    # ============================================================
    # METRICS
    # ============================================================
    
    def send_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        tags: Optional[Dict[str, str]] = None,
        host: Optional[str] = None
    ) -> bool:
        """
        Send a metric to DataDog
        
        Args:
            name: Metric name
            value: Metric value
            metric_type: Metric type
            tags: Metric tags
            host: Host name
            
        Returns:
            True if sent
        """
        if not self.metrics_api:
            logger.warning("DataDog client not initialized")
            return False
        
        try:
            # Prepare tags
            tag_list = []
            if tags:
                tag_list = [f"{k}:{v}" for k, v in tags.items()]
            
            # Add default tags
            tag_list.append(f"service:{self.datadog_config.service}")
            tag_list.append(f"env:{self.datadog_config.env}")
            
            # Send metric
            self.metrics_api.submit_metrics(
                body={
                    "series": [{
                        "metric": name,
                        "points": [{
                            "timestamp": int(time.time()),
                            "value": value,
                        }],
                        "type": metric_type.value,
                        "tags": tag_list,
                        "host": host or "nexus-bot",
                    }]
                }
            )
            
            logger.debug(f"Sent metric: {name}={value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send metric: {e}")
            return False
    
    def send_metrics(
        self,
        metrics: List[DataDogMetric]
    ) -> bool:
        """
        Send multiple metrics
        
        Args:
            metrics: List of metrics
            
        Returns:
            True if sent
        """
        if not self.metrics_api:
            logger.warning("DataDog client not initialized")
            return False
        
        if not metrics:
            return True
        
        try:
            series = []
            for metric in metrics:
                tag_list = [f"{k}:{v}" for k, v in metric.tags.items()]
                tag_list.append(f"service:{self.datadog_config.service}")
                tag_list.append(f"env:{self.datadog_config.env}")
                
                series.append({
                    "metric": metric.name,
                    "points": [{
                        "timestamp": int(metric.timestamp.timestamp()),
                        "value": metric.value,
                    }],
                    "type": metric.type.value,
                    "tags": tag_list,
                    "host": metric.host or "nexus-bot",
                })
            
            self.metrics_api.submit_metrics(body={"series": series})
            logger.debug(f"Sent {len(metrics)} metrics")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send metrics: {e}")
            return False
    
    # ============================================================
    # EVENTS
    # ============================================================
    
    def send_event(
        self,
        title: str,
        text: str,
        event_type: EventType = EventType.INFO,
        tags: Optional[Dict[str, str]] = None,
        host: Optional[str] = None,
        aggregation_key: Optional[str] = None
    ) -> bool:
        """
        Send an event to DataDog
        
        Args:
            title: Event title
            text: Event text
            event_type: Event type
            tags: Event tags
            host: Host name
            aggregation_key: Aggregation key
            
        Returns:
            True if sent
        """
        if not self.events_api:
            logger.warning("DataDog client not initialized")
            return False
        
        try:
            # Prepare tags
            tag_list = []
            if tags:
                tag_list = [f"{k}:{v}" for k, v in tags.items()]
            
            # Add default tags
            tag_list.append(f"service:{self.datadog_config.service}")
            tag_list.append(f"env:{self.datadog_config.env}")
            
            # Map event type to alert type
            alert_type = {
                EventType.INFO: "info",
                EventType.WARNING: "warning",
                EventType.ERROR: "error",
                EventType.SUCCESS: "success",
            }.get(event_type, "info")
            
            event = Event(
                title=title,
                text=text,
                alert_type=EventAlertType(alert_type),
                priority=EventPriority.NORMAL,
                tags=tag_list,
                host=host or "nexus-bot",
            )
            
            if aggregation_key:
                event.aggregation_key = aggregation_key
            
            response = self.events_api.create_event(body=event)
            logger.debug(f"Sent event: {title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send event: {e}")
            return False
    
    # ============================================================
    # LOGS
    # ============================================================
    
    def send_log(
        self,
        message: str,
        level: str = "INFO",
        tags: Optional[Dict[str, str]] = None,
        host: Optional[str] = None,
        service: Optional[str] = None
    ) -> bool:
        """
        Send a log to DataDog
        
        Args:
            message: Log message
            level: Log level
            tags: Log tags
            host: Host name
            service: Service name
            
        Returns:
            True if sent
        """
        if not self.logs_api:
            logger.warning("DataDog client not initialized")
            return False
        
        try:
            # Prepare tags
            tag_list = []
            if tags:
                tag_list = [f"{k}:{v}" for k, v in tags.items()]
            
            # Add default tags
            tag_list.append(f"service:{service or self.datadog_config.service}")
            tag_list.append(f"env:{self.datadog_config.env}")
            
            log_data = {
                "message": message,
                "status": level,
                "hostname": host or "nexus-bot",
                "tags": ",".join(tag_list),
                "timestamp": int(time.time() * 1000),
            }
            
            self.logs_api.submit_log(body=[log_data])
            logger.debug(f"Sent log: {message[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send log: {e}")
            return False
    
    # ============================================================
    # TRACING
    # ============================================================
    
    def trace_function(
        self,
        name: str,
        resource: Optional[str] = None
    ) -> Any:
        """
        Create a trace span
        
        Args:
            name: Span name
            resource: Resource name
            
        Returns:
            Span context
        """
        if not HAS_DDTRACE:
            return None
        
        try:
            return tracer.trace(name, resource=resource or name)
        except Exception as e:
            logger.error(f"Failed to create trace: {e}")
            return None
    
    # ============================================================
    # BUFFERING AND FLUSHING
    # ============================================================
    
    def buffer_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        tags: Optional[Dict[str, str]] = None,
        host: Optional[str] = None
    ) -> None:
        """
        Buffer a metric for batch sending
        
        Args:
            name: Metric name
            value: Metric value
            metric_type: Metric type
            tags: Metric tags
            host: Host name
        """
        metric = DataDogMetric(
            name=name,
            value=value,
            type=metric_type,
            tags=tags or {},
            host=host,
        )
        
        self.metrics_buffer.append(metric)
        
        if len(self.metrics_buffer) >= self.buffer_size:
            self.flush_metrics()
    
    def buffer_event(
        self,
        title: str,
        text: str,
        event_type: EventType = EventType.INFO,
        tags: Optional[Dict[str, str]] = None,
        host: Optional[str] = None
    ) -> None:
        """
        Buffer an event for batch sending
        
        Args:
            title: Event title
            text: Event text
            event_type: Event type
            tags: Event tags
            host: Host name
        """
        event = DataDogEvent(
            title=title,
            text=text,
            event_type=event_type,
            tags=tags or {},
            host=host,
        )
        
        self.events_buffer.append(event)
        
        if len(self.events_buffer) >= self.buffer_size:
            self.flush_events()
    
    def flush_metrics(self) -> None:
        """Flush buffered metrics"""
        if not self.metrics_buffer:
            return
        
        metrics = self.metrics_buffer.copy()
        self.metrics_buffer.clear()
        self.send_metrics(metrics)
    
    def flush_events(self) -> None:
        """Flush buffered events"""
        if not self.events_buffer:
            return
        
        events = self.events_buffer.copy()
        self.events_buffer.clear()
        for event in events:
            self.send_event(
                title=event.title,
                text=event.text,
                event_type=event.event_type,
                tags=event.tags,
                host=event.host,
            )
    
    def flush_all(self) -> None:
        """Flush all buffered data"""
        self.flush_metrics()
        self.flush_events()
    
    # ============================================================
    # BACKGROUND FLUSH
    # ============================================================
    
    def start(self) -> None:
        """Start background flushing"""
        if self.is_running:
            return
        
        self.is_running = True
        self.flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self.flush_thread.start()
        logger.info("DataDog background flush started")
    
    def stop(self) -> None:
        """Stop background flushing"""
        self.is_running = False
        if self.flush_thread:
            self.flush_thread.join(timeout=5)
        self.flush_all()
        logger.info("DataDog background flush stopped")
    
    def _flush_loop(self) -> None:
        """Background flush loop"""
        while self.is_running:
            try:
                time.sleep(self.flush_interval)
                self.flush_all()
            except Exception as e:
                logger.error(f"Flush loop error: {e}")
                time.sleep(10)
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get DataDog statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "connected": bool(self.api_client),
            "metrics_buffered": len(self.metrics_buffer),
            "events_buffered": len(self.events_buffer),
            "service": self.datadog_config.service,
            "env": self.datadog_config.env,
            "version": self.datadog_config.version,
            "datadog_libraries": {
                "datadog_api_client": HAS_DATADOG,
                "ddtrace": HAS_DDTRACE,
            },
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "MetricType",
    "EventType",
    
    # Dataclasses
    "DataDogConfig",
    "DataDogMetric",
    "DataDogEvent",
    
    # Classes
    "DataDogEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
