"""
NEXUS AI TRADING SYSTEM - Risk Monitor
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced real-time risk monitoring system for tracking trading risks,
generating alerts, and providing comprehensive risk dashboards.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd
from prometheus_client import Counter, Gauge, Histogram

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Prometheus metrics
RISK_MONITOR_COUNTER = Counter(
    "nexus_risk_monitor_checks_total",
    "Total number of risk monitor checks",
    ["monitor_type", "status"],
)
RISK_MONITOR_DURATION = Histogram(
    "nexus_risk_monitor_duration_seconds",
    "Duration of risk monitor checks",
    ["monitor_type"],
)
RISK_EVENT_COUNTER = Counter(
    "nexus_risk_events_total",
    "Total number of risk events",
    ["event_type", "severity"],
)
RISK_SCORE_GAUGE = Gauge(
    "nexus_risk_score",
    "Current risk score",
    ["portfolio"],
)
ACTIVE_RISK_EVENTS = Gauge(
    "nexus_active_risk_events",
    "Number of active risk events",
    ["severity"],
)


class RiskEventType(Enum):
    """Types of risk events."""

    # Portfolio events
    PORTFOLIO_VAR_BREACH = "portfolio_var_breach"
    PORTFOLIO_CVAR_BREACH = "portfolio_cvar_breach"
    PORTFOLIO_DRAWDOWN_BREACH = "portfolio_drawdown_breach"
    PORTFOLIO_LOSS_BREACH = "portfolio_loss_breach"

    # Position events
    POSITION_SIZE_BREACH = "position_size_breach"
    POSITION_CONCENTRATION_BREACH = "position_concentration_breach"
    POSITION_LOSS_BREACH = "position_loss_breach"
    POSITION_SLIPPAGE_BREACH = "position_slippage_breach"

    # Market events
    MARKET_VOLATILITY_SPIKE = "market_volatility_spike"
    MARKET_CORRELATION_BREACH = "market_correlation_breach"
    MARKET_GAP = "market_gap"
    MARKET_FLASH_CRASH = "market_flash_crash"

    # System events
    SYSTEM_CPU_BREACH = "system_cpu_breach"
    SYSTEM_MEMORY_BREACH = "system_memory_breach"
    SYSTEM_LATENCY_BREACH = "system_latency_breach"
    SYSTEM_DISK_BREACH = "system_disk_breach"

    # Trading events
    TRADING_VOLUME_SPIKE = "trading_volume_spike"
    TRADING_SLIPPAGE_SPIKE = "trading_slippage_spike"
    TRADING_FILL_RATE_BREACH = "trading_fill_rate_breach"
    TRADING_ORDER_REJECTION = "trading_order_rejection"


class RiskEventSeverity(Enum):
    """Severity levels for risk events."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskEventStatus(Enum):
    """Status of risk events."""

    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class RiskEvent:
    """Risk event record."""

    id: str
    event_type: RiskEventType
    severity: RiskEventSeverity
    title: str
    description: str
    status: RiskEventStatus = RiskEventStatus.NEW
    timestamp: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    related_events: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "metadata": self.metadata,
            "recommendations": self.recommendations,
            "related_events": self.related_events,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskEvent":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            event_type=RiskEventType(data["event_type"]),
            severity=RiskEventSeverity(data["severity"]),
            title=data["title"],
            description=data["description"],
            status=RiskEventStatus(data.get("status", "new")),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            acknowledged_at=datetime.fromisoformat(data["acknowledged_at"]) if data.get("acknowledged_at") else None,
            metadata=data.get("metadata", {}),
            recommendations=data.get("recommendations", []),
            related_events=data.get("related_events", []),
        )


@dataclass
class RiskSummary:
    """Summary of current risk status."""

    overall_risk_score: float = 0.0
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    cvar_99: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    position_concentration: float = 0.0
    leverage_ratio: float = 0.0
    active_events: int = 0
    critical_events: int = 0
    total_exposure: float = 0.0
    daily_pnl: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "overall_risk_score": self.overall_risk_score,
            "var_95": self.var_95,
            "var_99": self.var_99,
            "cvar_95": self.cvar_95,
            "cvar_99": self.cvar_99,
            "max_drawdown": self.max_drawdown,
            "current_drawdown": self.current_drawdown,
            "position_concentration": self.position_concentration,
            "leverage_ratio": self.leverage_ratio,
            "active_events": self.active_events,
            "critical_events": self.critical_events,
            "total_exposure": self.total_exposure,
            "daily_pnl": self.daily_pnl,
            "timestamp": self.timestamp.isoformat(),
        }


class RiskMonitor:
    """
    Advanced real-time risk monitoring system.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        alert_manager: Optional[Any] = None,
        risk_analyzer: Optional[Any] = None,
    ):
        """
        Initialize the risk monitor.

        Args:
            config: Configuration dictionary
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
            alert_manager: Alert manager instance
            risk_analyzer: Risk analyzer instance
        """
        self.config = config or {}
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.alert_manager = alert_manager
        self.risk_analyzer = risk_analyzer
        self._lock = asyncio.Lock()
        self._events: Dict[str, RiskEvent] = {}
        self._monitors: Dict[str, Callable] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._event_handlers: Dict[RiskEventType, List[Callable]] = {}

        # Load configuration
        self.monitor_config = self.config.get("risk_monitor", {})
        self.monitor_interval = self.monitor_config.get("monitor_interval", 30)
        self.max_events = self.monitor_config.get("max_events", 1000)
        self.auto_resolve_timeout = self.monitor_config.get("auto_resolve_timeout", 3600)

        # Register default monitors
        self._register_default_monitors()

        # Start monitoring
        self._start_monitoring()

        logger.info("RiskMonitor initialized")

    def _register_default_monitors(self):
        """Register default risk monitors."""
        self.register_monitor("portfolio_risk", self._monitor_portfolio_risk)
        self.register_monitor("position_risk", self._monitor_position_risk)
        self.register_monitor("market_risk", self._monitor_market_risk)
        self.register_monitor("system_risk", self._monitor_system_risk)
        self.register_monitor("trading_risk", self._monitor_trading_risk)

    def register_monitor(self, name: str, monitor_func: Callable):
        """
        Register a risk monitor.

        Args:
            name: Monitor name
            monitor_func: Async function that checks risks
        """
        self._monitors[name] = monitor_func
        logger.info(f"Registered risk monitor: {name}")

    def register_event_handler(self, event_type: RiskEventType, handler: Callable):
        """
        Register an event handler.

        Args:
            event_type: Event type
            handler: Handler function
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        logger.info(f"Registered event handler for: {event_type.value}")

    def _start_monitoring(self):
        """Start the monitoring task."""
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def _monitor_loop(self):
        """Background loop for risk monitoring."""
        while True:
            try:
                await self._run_monitors()
                await self._cleanup_old_events()
                await self._update_risk_summary()
                await asyncio.sleep(self.monitor_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)

    async def _run_monitors(self):
        """Run all registered monitors."""
        for name, monitor in self._monitors.items():
            try:
                start_time = time.time()

                if asyncio.iscoroutinefunction(monitor):
                    events = await monitor()
                else:
                    events = monitor()

                if events:
                    await self._process_events(events, name)

                RISK_MONITOR_COUNTER.labels(
                    monitor_type=name,
                    status="success",
                ).inc()
                RISK_MONITOR_DURATION.labels(
                    monitor_type=name,
                ).observe(time.time() - start_time)

            except Exception as e:
                RISK_MONITOR_COUNTER.labels(
                    monitor_type=name,
                    status="error",
                ).inc()
                logger.error(f"Error in monitor {name}: {e}")

    async def _process_events(self, events: List[RiskEvent], source: str):
        """
        Process risk events.

        Args:
            events: List of risk events
            source: Event source
        """
        for event in events:
            # Check for duplicates
            duplicate = await self._is_duplicate_event(event)
            if duplicate:
                continue

            # Store event
            async with self._lock:
                self._events[event.id] = event

                # Limit events
                if len(self._events) > self.max_events:
                    oldest = sorted(
                        self._events.keys(),
                        key=lambda x: self._events[x].timestamp,
                    )[0]
                    del self._events[oldest]

            # Update metrics
            RISK_EVENT_COUNTER.labels(
                event_type=event.event_type.value,
                severity=event.severity.value,
            ).inc()

            if event.status == RiskEventStatus.NEW:
                ACTIVE_RISK_EVENTS.labels(
                    severity=event.severity.value
                ).inc()

            # Trigger handlers
            await self._trigger_event_handlers(event)

            # Send alert
            if event.severity in [RiskEventSeverity.HIGH, RiskEventSeverity.CRITICAL]:
                await self._send_alert(event)

            logger.info(
                f"Risk event: {event.event_type.value} - {event.title} "
                f"(severity: {event.severity.value})"
            )

    async def _is_duplicate_event(self, event: RiskEvent) -> bool:
        """
        Check if event is a duplicate.

        Args:
            event: Event to check

        Returns:
            True if duplicate
        """
        async with self._lock:
            for existing in self._events.values():
                if (
                    existing.event_type == event.event_type and
                    existing.metadata.get("key") == event.metadata.get("key") and
                    (event.timestamp - existing.timestamp).total_seconds() < 300  # 5 minutes
                ):
                    return True
            return False

    async def _trigger_event_handlers(self, event: RiskEvent):
        """Trigger event handlers."""
        handlers = self._event_handlers.get(event.event_type, [])

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")

    async def _send_alert(self, event: RiskEvent):
        """Send alert for risk event."""
        if self.alert_manager:
            await self.alert_manager.evaluate_rules({
                "event_type": event.event_type.value,
                "severity": event.severity.value,
                "title": event.title,
                "description": event.description,
                "metadata": event.metadata,
                "timestamp": event.timestamp.isoformat(),
            }, source="risk_monitor")

    async def _cleanup_old_events(self):
        """Clean up old resolved events."""
        cutoff = datetime.utcnow() - timedelta(seconds=self.auto_resolve_timeout)

        async with self._lock:
            for event_id, event in list(self._events.items()):
                if event.status == RiskEventStatus.RESOLVED:
                    if event.resolved_at and event.resolved_at < cutoff:
                        del self._events[event_id]

    async def _update_risk_summary(self):
        """Update risk summary."""
        if self.risk_analyzer:
            try:
                # Get latest risk metrics
                history = await self.risk_analyzer.get_risk_history(limit=1)
                if history:
                    metrics = history[0]

                    summary = RiskSummary(
                        overall_risk_score=metrics.overall_risk_score,
                        var_95=metrics.var_95,
                        var_99=metrics.var_99,
                        cvar_95=metrics.cvar_95,
                        cvar_99=metrics.cvar_99,
                        max_drawdown=metrics.max_drawdown,
                        current_drawdown=metrics.current_drawdown,
                        position_concentration=metrics.position_concentration,
                        leverage_ratio=metrics.leverage_risk,
                    )

                    # Get active events count
                    async with self._lock:
                        summary.active_events = sum(
                            1 for e in self._events.values()
                            if e.status in [RiskEventStatus.NEW, RiskEventStatus.ACKNOWLEDGED]
                        )
                        summary.critical_events = sum(
                            1 for e in self._events.values()
                            if e.severity in [RiskEventSeverity.HIGH, RiskEventSeverity.CRITICAL]
                            and e.status in [RiskEventStatus.NEW, RiskEventStatus.ACKNOWLEDGED]
                        )

                    # Cache summary
                    await self.cache_manager.set(
                        "risk_summary",
                        summary.to_dict(),
                        60,
                    )

                    # Update gauge
                    RISK_SCORE_GAUGE.labels(portfolio="default").set(
                        summary.overall_risk_score
                    )

            except Exception as e:
                logger.error(f"Error updating risk summary: {e}")

    # Default Monitors

    async def _monitor_portfolio_risk(self) -> List[RiskEvent]:
        """Monitor portfolio risk."""
        events = []

        if not self.risk_analyzer:
            return events

        try:
            history = await self.risk_analyzer.get_risk_history(limit=1)
            if not history:
                return events

            metrics = history[0]

            # Check VaR breaches
            var_95_threshold = 0.05
            if metrics.var_95 > var_95_threshold:
                events.append(RiskEvent(
                    id=f"var_breach_{int(time.time())}",
                    event_type=RiskEventType.PORTFOLIO_VAR_BREACH,
                    severity=RiskEventSeverity.HIGH,
                    title="VaR 95% Breach",
                    description=f"VaR 95% exceeded threshold: {metrics.var_95:.4f} > {var_95_threshold:.4f}",
                    metadata={
                        "var_95": metrics.var_95,
                        "threshold": var_95_threshold,
                        "confidence": 0.95,
                    },
                    recommendations=["Reduce position sizes", "Hedge existing positions"],
                ))

            # Check drawdown breach
            if metrics.current_drawdown > 0.15:
                events.append(RiskEvent(
                    id=f"drawdown_breach_{int(time.time())}",
                    event_type=RiskEventType.PORTFOLIO_DRAWDOWN_BREACH,
                    severity=RiskEventSeverity.HIGH,
                    title="Drawdown Breach",
                    description=f"Current drawdown exceeded: {metrics.current_drawdown:.2%} > 15%",
                    metadata={
                        "current_drawdown": metrics.current_drawdown,
                        "max_drawdown": metrics.max_drawdown,
                    },
                    recommendations=["Reduce position sizes", "Review strategy performance"],
                ))

            # Check portfolio loss breach
            if metrics.daily_pnl < -10000:
                events.append(RiskEvent(
                    id=f"loss_breach_{int(time.time())}",
                    event_type=RiskEventType.PORTFOLIO_LOSS_BREACH,
                    severity=RiskEventSeverity.CRITICAL,
                    title="Portfolio Loss Breach",
                    description=f"Daily loss exceeded: ${metrics.daily_pnl:,.2f}",
                    metadata={"daily_pnl": metrics.daily_pnl},
                    recommendations=["Halt trading", "Review strategy performance"],
                ))

        except Exception as e:
            logger.error(f"Error monitoring portfolio risk: {e}")

        return events

    async def _monitor_position_risk(self) -> List[RiskEvent]:
        """Monitor position risk."""
        events = []

        try:
            # Get positions from cache
            positions = await self.cache_manager.get("positions")

            if not positions:
                return events

            # Check concentration
            total_value = sum(p.get("value", 0) for p in positions)
            if total_value > 0:
                for pos in positions:
                    value = pos.get("value", 0)
                    concentration = value / total_value

                    if concentration > 0.25:  # 25% concentration limit
                        events.append(RiskEvent(
                            id=f"concentration_{pos.get('symbol', 'unknown')}_{int(time.time())}",
                            event_type=RiskEventType.POSITION_CONCENTRATION_BREACH,
                            severity=RiskEventSeverity.MEDIUM,
                            title=f"Position Concentration Breach: {pos.get('symbol', 'unknown')}",
                            description=f"Position concentration: {concentration:.2%} > 25%",
                            metadata={
                                "symbol": pos.get("symbol"),
                                "concentration": concentration,
                                "value": value,
                                "total_value": total_value,
                            },
                            recommendations=["Reduce position in this symbol", "Diversify portfolio"],
                        ))

            # Check position loss
            for pos in positions:
                pnl = pos.get("pnl", 0)
                if pnl < -5000:
                    events.append(RiskEvent(
                        id=f"position_loss_{pos.get('symbol', 'unknown')}_{int(time.time())}",
                        event_type=RiskEventType.POSITION_LOSS_BREACH,
                        severity=RiskEventSeverity.HIGH,
                        title=f"Position Loss Breach: {pos.get('symbol', 'unknown')}",
                        description=f"Position loss: ${pnl:,.2f}",
                        metadata={
                            "symbol": pos.get("symbol"),
                            "pnl": pnl,
                            "size": pos.get("size", 0),
                            "entry_price": pos.get("entry_price", 0),
                        },
                        recommendations=["Set stop-loss", "Reduce position size"],
                    ))

        except Exception as e:
            logger.error(f"Error monitoring position risk: {e}")

        return events

    async def _monitor_market_risk(self) -> List[RiskEvent]:
        """Monitor market risk."""
        events = []

        try:
            # Get market data from cache
            market_data = await self.cache_manager.get("market_data")

            if not market_data:
                return events

            # Check volatility
            volatility = market_data.get("volatility", 0)
            if volatility > 0.03:  # 3% volatility threshold
                events.append(RiskEvent(
                    id=f"volatility_spike_{int(time.time())}",
                    event_type=RiskEventType.MARKET_VOLATILITY_SPIKE,
                    severity=RiskEventSeverity.MEDIUM,
                    title="Market Volatility Spike",
                    description=f"Volatility: {volatility:.2%} > 3%",
                    metadata={"volatility": volatility},
                    recommendations=["Reduce position sizes", "Increase hedging"],
                ))

            # Check market gap
            gap = market_data.get("gap", 0)
            if abs(gap) > 0.02:  # 2% gap threshold
                events.append(RiskEvent(
                    id=f"market_gap_{int(time.time())}",
                    event_type=RiskEventType.MARKET_GAP,
                    severity=RiskEventSeverity.MEDIUM,
                    title="Market Gap Detected",
                    description=f"Market gap: {gap:.2%}",
                    metadata={"gap": gap},
                    recommendations=["Review positions", "Adjust stop-losses"],
                ))

        except Exception as e:
            logger.error(f"Error monitoring market risk: {e}")

        return events

    async def _monitor_system_risk(self) -> List[RiskEvent]:
        """Monitor system risk."""
        events = []

        try:
            import psutil

            # CPU usage
            cpu = psutil.cpu_percent()
            if cpu > 80:
                events.append(RiskEvent(
                    id=f"cpu_high_{int(time.time())}",
                    event_type=RiskEventType.SYSTEM_CPU_BREACH,
                    severity=RiskEventSeverity.MEDIUM,
                    title="High CPU Usage",
                    description=f"CPU usage: {cpu:.1f}% > 80%",
                    metadata={"cpu_usage": cpu},
                    recommendations=["Scale down operations", "Optimize code"],
                ))

            # Memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 85:
                events.append(RiskEvent(
                    id=f"memory_high_{int(time.time())}",
                    event_type=RiskEventType.SYSTEM_MEMORY_BREACH,
                    severity=RiskEventSeverity.MEDIUM,
                    title="High Memory Usage",
                    description=f"Memory usage: {memory.percent:.1f}% > 85%",
                    metadata={"memory_usage": memory.percent},
                    recommendations=["Clear cache", "Restart services"],
                ))

            # Disk usage
            disk = psutil.disk_usage("/")
            if disk.percent > 90:
                events.append(RiskEvent(
                    id=f"disk_high_{int(time.time())}",
                    event_type=RiskEventType.SYSTEM_DISK_BREACH,
                    severity=RiskEventSeverity.HIGH,
                    title="High Disk Usage",
                    description=f"Disk usage: {disk.percent:.1f}% > 90%",
                    metadata={"disk_usage": disk.percent},
                    recommendations=["Clean logs", "Archive old data"],
                ))

        except Exception as e:
            logger.error(f"Error monitoring system risk: {e}")

        return events

    async def _monitor_trading_risk(self) -> List[RiskEvent]:
        """Monitor trading risk."""
        events = []

        try:
            # Get trading stats from cache
            trading_stats = await self.cache_manager.get("trading_stats")

            if not trading_stats:
                return events

            # Check fill rate
            fill_rate = trading_stats.get("fill_rate", 1.0)
            if fill_rate < 0.8:  # 80% fill rate threshold
                events.append(RiskEvent(
                    id=f"fill_rate_{int(time.time())}",
                    event_type=RiskEventType.TRADING_FILL_RATE_BREACH,
                    severity=RiskEventSeverity.MEDIUM,
                    title="Low Fill Rate",
                    description=f"Fill rate: {fill_rate:.2%} < 80%",
                    metadata={"fill_rate": fill_rate},
                    recommendations=["Check broker connectivity", "Adjust order types"],
                ))

            # Check order rejections
            rejections = trading_stats.get("order_rejections", 0)
            if rejections > 10:
                events.append(RiskEvent(
                    id=f"rejections_{int(time.time())}",
                    event_type=RiskEventType.TRADING_ORDER_REJECTION,
                    severity=RiskEventSeverity.HIGH,
                    title="High Order Rejection Rate",
                    description=f"Order rejections: {rejections}",
                    metadata={"rejections": rejections},
                    recommendations=["Check order parameters", "Verify account balance"],
                ))

            # Check slippage
            slippage = trading_stats.get("slippage", 0)
            if slippage > 0.01:  # 1% slippage threshold
                events.append(RiskEvent(
                    id=f"slippage_{int(time.time())}",
                    event_type=RiskEventType.TRADING_SLIPPAGE_SPIKE,
                    severity=RiskEventSeverity.MEDIUM,
                    title="High Slippage",
                    description=f"Slippage: {slippage:.2%} > 1%",
                    metadata={"slippage": slippage},
                    recommendations=["Use limit orders", "Reduce order size"],
                ))

        except Exception as e:
            logger.error(f"Error monitoring trading risk: {e}")

        return events

    async def acknowledge_event(self, event_id: str, metadata: Optional[Dict] = None):
        """
        Acknowledge a risk event.

        Args:
            event_id: Event ID
            metadata: Additional metadata
        """
        async with self._lock:
            event = self._events.get(event_id)

            if not event:
                return False

            event.status = RiskEventStatus.ACKNOWLEDGED
            event.acknowledged_at = datetime.utcnow()
            if metadata:
                event.metadata.update(metadata)

            ACTIVE_RISK_EVENTS.labels(severity=event.severity.value).dec()

            logger.info(f"Risk event {event_id} acknowledged")
            return True

    async def resolve_event(
        self,
        event_id: str,
        resolution_note: Optional[str] = None,
    ):
        """
        Resolve a risk event.

        Args:
            event_id: Event ID
            resolution_note: Resolution note
        """
        async with self._lock:
            event = self._events.get(event_id)

            if not event:
                return False

            event.status = RiskEventStatus.RESOLVED
            event.resolved_at = datetime.utcnow()
            if resolution_note:
                event.metadata["resolution_note"] = resolution_note

            ACTIVE_RISK_EVENTS.labels(severity=event.severity.value).dec()

            logger.info(f"Risk event {event_id} resolved")
            return True

    async def get_events(
        self,
        event_type: Optional[Union[RiskEventType, str]] = None,
        severity: Optional[Union[RiskEventSeverity, str]] = None,
        status: Optional[Union[RiskEventStatus, str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RiskEvent]:
        """
        Get risk events.

        Args:
            event_type: Filter by event type
            severity: Filter by severity
            status: Filter by status
            limit: Maximum number of events
            offset: Offset for pagination

        Returns:
            List of risk events
        """
        async with self._lock:
            events = list(self._events.values())

            if event_type:
                if isinstance(event_type, str):
                    event_type = RiskEventType(event_type)
                events = [e for e in events if e.event_type == event_type]

            if severity:
                if isinstance(severity, str):
                    severity = RiskEventSeverity(severity)
                events = [e for e in events if e.severity == severity]

            if status:
                if isinstance(status, str):
                    status = RiskEventStatus(status)
                events = [e for e in events if e.status == status]

            events.sort(key=lambda x: x.timestamp, reverse=True)
            return events[offset:offset + limit]

    async def get_risk_summary(self) -> Optional[RiskSummary]:
        """
        Get current risk summary.

        Returns:
            Risk summary or None
        """
        summary_data = await self.cache_manager.get("risk_summary")

        if summary_data:
            return RiskSummary(**summary_data)

        return None

    async def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get risk dashboard data.

        Returns:
            Risk dashboard data
        """
        summary = await self.get_risk_summary()

        async with self._lock:
            active_events = [
                e for e in self._events.values()
                if e.status in [RiskEventStatus.NEW, RiskEventStatus.ACKNOWLEDGED]
            ]

        return {
            "summary": summary.to_dict() if summary else {},
            "active_events": {
                "total": len(active_events),
                "critical": sum(1 for e in active_events if e.severity == RiskEventSeverity.CRITICAL),
                "high": sum(1 for e in active_events if e.severity == RiskEventSeverity.HIGH),
                "medium": sum(1 for e in active_events if e.severity == RiskEventSeverity.MEDIUM),
                "low": sum(1 for e in active_events if e.severity == RiskEventSeverity.LOW),
                "events": [e.to_dict() for e in active_events[:10]],
            },
            "event_stats": {
                "total_events": len(self._events),
                "by_type": {
                    event_type.value: sum(1 for e in self._events.values() if e.event_type == event_type)
                    for event_type in RiskEventType
                },
                "by_severity": {
                    severity.value: sum(1 for e in self._events.values() if e.severity == severity)
                    for severity in RiskEventSeverity
                },
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def shutdown(self):
        """Shutdown the risk monitor."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("RiskMonitor shut down")


# Export singleton
risk_monitor = RiskMonitor()
