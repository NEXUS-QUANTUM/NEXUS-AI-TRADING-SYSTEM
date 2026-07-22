# trading/bots/hedge_bot/monitoring/dashboard_api.py

"""
NEXUS HEDGE BOT - DASHBOARD API
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Real-time dashboard API with WebSocket support, providing live monitoring
data, metrics, and system status for the hedge bot.

Version: 3.0.0
"""

import asyncio
import json
import time
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union, Callable
from uuid import uuid4

import aiohttp
from aiohttp import web
import structlog
import yaml
import pandas as pd
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from pydantic import BaseModel, Field, validator
import uvicorn

# Import local modules
from .alert_manager import AlertManager, Alert, AlertSeverity, AlertCategory
from .health_checker import HealthChecker, HealthStatus
from .incident_manager import IncidentManager
from .log_analyzer import LogAnalyzer
from .metric_collector import MetricCollector
from ..core.hedge_engine import HedgeEngine
from ..core.portfolio_manager import PortfolioManager
from ..core.risk_manager import RiskManager

# Configure structlog
logger = structlog.get_logger(__name__)


# === DATA MODELS ===

class SystemStatus(str, Enum):
    """System status levels."""
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    UNKNOWN = "unknown"


class DashboardMetric(BaseModel):
    """Dashboard metric data point."""
    name: str
    value: float
    unit: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    labels: Dict[str, str] = Field(default_factory=dict)
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    status: str = "ok"

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DashboardData(BaseModel):
    """Complete dashboard data payload."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    system_status: SystemStatus = SystemStatus.OPERATIONAL
    uptime_seconds: float = 0.0
    metrics: List[DashboardMetric] = Field(default_factory=list)
    alerts: List[Dict[str, Any]] = Field(default_factory=list)
    performance: Dict[str, Any] = Field(default_factory=dict)
    portfolio: Dict[str, Any] = Field(default_factory=dict)
    risk: Dict[str, Any] = Field(default_factory=dict)
    trading: Dict[str, Any] = Field(default_factory=dict)
    system: Dict[str, Any] = Field(default_factory=dict)
    incidents: List[Dict[str, Any]] = Field(default_factory=list)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DashboardConfig(BaseModel):
    """Dashboard configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["*"]
    enable_websocket: bool = True
    update_interval_seconds: int = 5
    retention_hours: int = 24
    max_metrics_points: int = 10000
    auth_enabled: bool = False
    auth_tokens: List[str] = Field(default_factory=list)
    static_dir: Optional[str] = None
    template_dir: Optional[str] = None


# === DASHBOARD API ===

class DashboardAPI:
    """
    Real-time dashboard API with WebSocket support for the hedge bot.
    """

    def __init__(
        self,
        config: Union[DashboardConfig, Dict[str, Any], str],
        alert_manager: Optional[AlertManager] = None,
        health_checker: Optional[HealthChecker] = None,
        incident_manager: Optional[IncidentManager] = None,
        log_analyzer: Optional[LogAnalyzer] = None,
        metric_collector: Optional[MetricCollector] = None,
        hedge_engine: Optional[HedgeEngine] = None,
        portfolio_manager: Optional[PortfolioManager] = None,
        risk_manager: Optional[RiskManager] = None,
    ):
        """
        Initialize the Dashboard API.

        Args:
            config: Configuration object, dict, or path to config file
            alert_manager: Alert manager instance
            health_checker: Health checker instance
            incident_manager: Incident manager instance
            log_analyzer: Log analyzer instance
            metric_collector: Metric collector instance
            hedge_engine: Hedge engine instance
            portfolio_manager: Portfolio manager instance
            risk_manager: Risk manager instance
        """
        if isinstance(config, str):
            with open(config, "r") as f:
                config_data = yaml.safe_load(f)
            self.config = DashboardConfig(**config_data)
        elif isinstance(config, dict):
            self.config = DashboardConfig(**config)
        else:
            self.config = config

        self.alert_manager = alert_manager
        self.health_checker = health_checker
        self.incident_manager = incident_manager
        self.log_analyzer = log_analyzer
        self.metric_collector = metric_collector
        self.hedge_engine = hedge_engine
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager

        self._app = FastAPI(
            title="NEXUS Hedge Bot Dashboard API",
            description="Real-time monitoring and control dashboard",
            version="3.0.0",
            docs_url="/api/docs",
            redoc_url="/api/redoc",
        )
        self._setup_routes()
        self._setup_cors()
        self._setup_static()

        self._websocket_connections: Set[WebSocket] = set()
        self._websocket_lock = threading.RLock()
        self._background_tasks: Set[asyncio.Task] = set()
        self._running = False
        self._shutdown = False

        self._metric_history: List[DashboardMetric] = []
        self._history_lock = threading.RLock()

        # Start background tasks
        self._start_background_tasks()

        logger.info(
            "dashboard_api_initialized",
            host=self.config.host,
            port=self.config.port,
            websocket_enabled=self.config.enable_websocket,
        )

    def _setup_cors(self) -> None:
        """Set up CORS middleware."""
        self._app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_static(self) -> None:
        """Set up static file serving."""
        if self.config.static_dir:
            from fastapi.staticfiles import StaticFiles
            static_path = Path(self.config.static_dir)
            if static_path.exists():
                self._app.mount(
                    "/static",
                    StaticFiles(directory=str(static_path)),
                    name="static",
                )

    def _setup_routes(self) -> None:
        """Set up API routes."""

        # Health endpoint
        @self._app.get("/api/health")
        async def health_check():
            """Health check endpoint."""
            if self.health_checker:
                status = self.health_checker.check()
                return {
                    "status": status.value,
                    "timestamp": datetime.utcnow().isoformat(),
                    "components": self.health_checker.get_component_statuses(),
                }
            return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

        # Dashboard data endpoint
        @self._app.get("/api/dashboard")
        async def get_dashboard():
            """Get complete dashboard data."""
            return await self._get_dashboard_data()

        # Metrics endpoint
        @self._app.get("/api/metrics")
        async def get_metrics(
            name: Optional[str] = None,
            limit: int = 100,
            offset: int = 0,
        ):
            """Get metrics data."""
            metrics = await self._get_metrics(name, limit, offset)
            return {
                "metrics": [m.dict() for m in metrics],
                "total": len(metrics),
                "limit": limit,
                "offset": offset,
            }

        # Alert endpoint
        @self._app.get("/api/alerts")
        async def get_alerts(
            status: Optional[str] = None,
            severity: Optional[str] = None,
            limit: int = 100,
            offset: int = 0,
        ):
            """Get alerts."""
            if not self.alert_manager:
                return {"alerts": [], "total": 0}

            alerts = self.alert_manager.get_alert_history(
                limit=limit,
                offset=offset,
                severity=severity,
                status=status,
            )
            return {
                "alerts": [a.to_dict() for a in alerts],
                "total": len(alerts),
                "limit": limit,
                "offset": offset,
            }

        # Alert action endpoints
        @self._app.post("/api/alerts/{alert_id}/acknowledge")
        async def acknowledge_alert(alert_id: str, user: str = "dashboard"):
            """Acknowledge an alert."""
            if not self.alert_manager:
                raise HTTPException(status_code=503, detail="Alert manager not available")

            success = self.alert_manager.acknowledge_alert(alert_id, user)
            if not success:
                raise HTTPException(status_code=404, detail="Alert not found")

            return {"success": True, "alert_id": alert_id}

        @self._app.post("/api/alerts/{alert_id}/resolve")
        async def resolve_alert(alert_id: str, user: str = "dashboard"):
            """Resolve an alert."""
            if not self.alert_manager:
                raise HTTPException(status_code=503, detail="Alert manager not available")

            success = self.alert_manager.resolve_alert(alert_id, user)
            if not success:
                raise HTTPException(status_code=404, detail="Alert not found")

            return {"success": True, "alert_id": alert_id}

        # Performance endpoint
        @self._app.get("/api/performance")
        async def get_performance():
            """Get performance data."""
            return await self._get_performance_data()

        # Portfolio endpoint
        @self._app.get("/api/portfolio")
        async def get_portfolio():
            """Get portfolio data."""
            return await self._get_portfolio_data()

        # Risk endpoint
        @self._app.get("/api/risk")
        async def get_risk():
            """Get risk data."""
            return await self._get_risk_data()

        # Trading endpoint
        @self._app.get("/api/trading")
        async def get_trading():
            """Get trading data."""
            return await self._get_trading_data()

        # System endpoint
        @self._app.get("/api/system")
        async def get_system():
            """Get system data."""
            return await self._get_system_data()

        # Incident endpoints
        @self._app.get("/api/incidents")
        async def get_incidents(
            status: Optional[str] = None,
            severity: Optional[str] = None,
            limit: int = 50,
            offset: int = 0,
        ):
            """Get incidents."""
            if not self.incident_manager:
                return {"incidents": [], "total": 0}

            incidents = self.incident_manager.get_incidents(
                status=status,
                severity=severity,
                limit=limit,
                offset=offset,
            )
            return {
                "incidents": [i.to_dict() for i in incidents],
                "total": len(incidents),
                "limit": limit,
                "offset": offset,
            }

        # Websocket endpoint
        if self.config.enable_websocket:
            @self._app.websocket("/api/ws")
            async def websocket_endpoint(websocket: WebSocket):
                await self._handle_websocket(websocket)

        # Root endpoint
        @self._app.get("/")
        async def root():
            """Root endpoint."""
            return {
                "name": "NEXUS Hedge Bot Dashboard API",
                "version": "3.0.0",
                "status": "operational",
                "endpoints": [
                    "/api/health",
                    "/api/dashboard",
                    "/api/metrics",
                    "/api/alerts",
                    "/api/performance",
                    "/api/portfolio",
                    "/api/risk",
                    "/api/trading",
                    "/api/system",
                    "/api/incidents",
                    "/api/ws",
                    "/api/docs",
                    "/api/redoc",
                ],
            }

        # Authentication middleware
        if self.config.auth_enabled:
            @self._app.middleware("http")
            async def auth_middleware(request, call_next):
                """Authentication middleware."""
                auth_header = request.headers.get("Authorization")
                if not auth_header:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Missing Authorization header"}
                    )

                token = auth_header.replace("Bearer ", "")
                if token not in self.config.auth_tokens:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Invalid token"}
                    )

                return await call_next(request)

    def _start_background_tasks(self) -> None:
        """Start background tasks."""
        try:
            loop = asyncio.get_event_loop()

            # Data update task
            self._background_tasks.add(
                loop.create_task(self._update_loop())
            )

            # WebSocket broadcast task
            if self.config.enable_websocket:
                self._background_tasks.add(
                    loop.create_task(self._broadcast_loop())
                )

            logger.info("background_tasks_started")
        except RuntimeError:
            logger.warning("no_event_loop_available_background_tasks_disabled")

    async def _update_loop(self) -> None:
        """Background task for updating dashboard data."""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.config.update_interval_seconds)
                data = await self._get_dashboard_data()
                await self._update_metrics_history(data)
            except Exception as e:
                logger.error("update_loop_error", error=str(e))

    async def _broadcast_loop(self) -> None:
        """Background task for broadcasting data to WebSocket clients."""
        while not self._shutdown:
            try:
                await asyncio.sleep(self.config.update_interval_seconds)
                if self._websocket_connections:
                    data = await self._get_dashboard_data()
                    await self._broadcast_to_websockets(data)
            except Exception as e:
                logger.error("broadcast_loop_error", error=str(e))

    async def _handle_websocket(self, websocket: WebSocket) -> None:
        """Handle WebSocket connections."""
        await websocket.accept()

        with self._websocket_lock:
            self._websocket_connections.add(websocket)

        logger.info(
            "websocket_connected",
            client=websocket.client,
            total_connections=len(self._websocket_connections),
        )

        try:
            # Send initial data
            initial_data = await self._get_dashboard_data()
            await websocket.send_json(initial_data.dict())

            # Handle messages
            while True:
                try:
                    message = await websocket.receive_text()
                    await self._handle_websocket_message(websocket, message)
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error("websocket_message_error", error=str(e))

        finally:
            with self._websocket_lock:
                self._websocket_connections.discard(websocket)

            logger.info(
                "websocket_disconnected",
                total_connections=len(self._websocket_connections),
            )

    async def _handle_websocket_message(self, websocket: WebSocket, message: str) -> None:
        """Handle WebSocket messages."""
        try:
            data = json.loads(message)
            action = data.get("action")

            if action == "subscribe":
                # Subscribe to specific data channels
                channels = data.get("channels", ["all"])
                await websocket.send_json({
                    "type": "subscription_ack",
                    "channels": channels,
                    "timestamp": datetime.utcnow().isoformat(),
                })

            elif action == "acknowledge_alert":
                alert_id = data.get("alert_id")
                user = data.get("user", "websocket")
                if self.alert_manager:
                    success = self.alert_manager.acknowledge_alert(alert_id, user)
                    await websocket.send_json({
                        "type": "acknowledge_response",
                        "alert_id": alert_id,
                        "success": success,
                    })

            elif action == "resolve_alert":
                alert_id = data.get("alert_id")
                user = data.get("user", "websocket")
                if self.alert_manager:
                    success = self.alert_manager.resolve_alert(alert_id, user)
                    await websocket.send_json({
                        "type": "resolve_response",
                        "alert_id": alert_id,
                        "success": success,
                    })

            elif action == "get_metrics":
                name = data.get("name")
                limit = data.get("limit", 100)
                offset = data.get("offset", 0)
                metrics = await self._get_metrics(name, limit, offset)
                await websocket.send_json({
                    "type": "metrics_response",
                    "metrics": [m.dict() for m in metrics],
                    "limit": limit,
                    "offset": offset,
                })

            else:
                logger.warning("unknown_websocket_action", action=action)

        except json.JSONDecodeError:
            logger.warning("invalid_websocket_message", message=message[:100])
        except Exception as e:
            logger.error("websocket_message_handling_error", error=str(e))
            await websocket.send_json({
                "type": "error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            })

    async def _broadcast_to_websockets(self, data: DashboardData) -> None:
        """Broadcast data to all connected WebSocket clients."""
        if not self._websocket_connections:
            return

        message = data.dict()
        to_remove = set()

        with self._websocket_lock:
            for websocket in self._websocket_connections:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error("websocket_broadcast_error", error=str(e))
                    to_remove.add(websocket)

            # Remove failed connections
            for websocket in to_remove:
                self._websocket_connections.discard(websocket)

    async def _update_metrics_history(self, data: DashboardData) -> None:
        """Update the metrics history."""
        with self._history_lock:
            # Add new metrics
            for metric in data.metrics:
                self._metric_history.append(metric)

            # Trim history
            max_points = self.config.max_metrics_points
            if len(self._metric_history) > max_points:
                self._metric_history = self._metric_history[-max_points:]

    async def _get_dashboard_data(self) -> DashboardData:
        """Get complete dashboard data."""
        start_time = time.time()

        # Collect data from all sources
        metrics = await self._get_all_metrics()
        alerts = await self._get_active_alerts()
        performance = await self._get_performance_data()
        portfolio = await self._get_portfolio_data()
        risk = await self._get_risk_data()
        trading = await self._get_trading_data()
        system = await self._get_system_data()
        incidents = await self._get_active_incidents()
        status = await self._get_system_status()
        uptime = await self._get_uptime()

        return DashboardData(
            timestamp=datetime.utcnow(),
            system_status=status,
            uptime_seconds=uptime,
            metrics=metrics,
            alerts=alerts,
            performance=performance,
            portfolio=portfolio,
            risk=risk,
            trading=trading,
            system=system,
            incidents=incidents,
        )

    async def _get_all_metrics(self) -> List[DashboardMetric]:
        """Get all metrics."""
        metrics = []

        # System metrics
        if self.metric_collector:
            sys_metrics = self.metric_collector.get_system_metrics()
            for name, value in sys_metrics.items():
                metrics.append(DashboardMetric(
                    name=name,
                    value=value,
                    unit="%",
                    labels={"source": "system"},
                ))

        # Performance metrics
        if self.hedge_engine:
            perf_metrics = self.hedge_engine.get_performance_metrics()
            for name, value in perf_metrics.items():
                metrics.append(DashboardMetric(
                    name=name,
                    value=value,
                    labels={"source": "hedge_engine"},
                ))

        # Risk metrics
        if self.risk_manager:
            risk_metrics = self.risk_manager.get_metrics()
            for name, value in risk_metrics.items():
                if isinstance(value, (int, float)):
                    metrics.append(DashboardMetric(
                        name=name,
                        value=value,
                        labels={"source": "risk_manager"},
                    ))

        return metrics

    async def _get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active alerts."""
        if not self.alert_manager:
            return []

        alerts = self.alert_manager.get_active_alerts()
        return [a.to_dict() for a in alerts]

    async def _get_performance_data(self) -> Dict[str, Any]:
        """Get performance data."""
        data = {
            "total_pnl": 0.0,
            "total_return": 0.0,
            "daily_pnl": 0.0,
            "weekly_pnl": 0.0,
            "monthly_pnl": 0.0,
            "sharpe_ratio": 0.0,
            "win_rate": 0.0,
            "total_trades": 0,
            "max_drawdown": 0.0,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if self.hedge_engine:
            engine_data = self.hedge_engine.get_performance_summary()
            data.update(engine_data)

        return data

    async def _get_portfolio_data(self) -> Dict[str, Any]:
        """Get portfolio data."""
        data = {
            "total_value": 0.0,
            "cash_balance": 0.0,
            "invested_value": 0.0,
            "positions": [],
            "allocations": {},
            "num_positions": 0,
            "concentration_ratio": 0.0,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if self.portfolio_manager:
            portfolio_data = self.portfolio_manager.get_portfolio_summary()
            data.update(portfolio_data)

        return data

    async def _get_risk_data(self) -> Dict[str, Any]:
        """Get risk data."""
        data = {
            "var_95": 0.0,
            "var_99": 0.0,
            "cvar_95": 0.0,
            "cvar_99": 0.0,
            "current_exposure": 0.0,
            "current_leverage": 0.0,
            "max_drawdown": 0.0,
            "risk_score": 0.0,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if self.risk_manager:
            risk_data = self.risk_manager.get_risk_summary()
            data.update(risk_data)

        return data

    async def _get_trading_data(self) -> Dict[str, Any]:
        """Get trading data."""
        data = {
            "total_trades": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "total_volume": 0.0,
            "avg_execution_time_ms": 0.0,
            "active_orders": 0,
            "pending_orders": 0,
            "order_history": [],
            "timestamp": datetime.utcnow().isoformat(),
        }

        if self.hedge_engine:
            trading_data = self.hedge_engine.get_trading_summary()
            data.update(trading_data)

        return data

    async def _get_system_data(self) -> Dict[str, Any]:
        """Get system data."""
        import psutil

        data = {
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "memory_used_gb": psutil.virtual_memory().used / (1024**3),
            "memory_total_gb": psutil.virtual_memory().total / (1024**3),
            "disk_usage": psutil.disk_usage("/").percent,
            "connections": 0,
            "threads": 0,
            "uptime_seconds": time.time() - psutil.boot_time(),
            "version": "3.0.0",
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Get connection count
        if self._websocket_connections:
            data["connections"] = len(self._websocket_connections)

        # Get thread count
        data["threads"] = threading.active_count()

        return data

    async def _get_active_incidents(self) -> List[Dict[str, Any]]:
        """Get active incidents."""
        if not self.incident_manager:
            return []

        incidents = self.incident_manager.get_active_incidents()
        return [i.to_dict() for i in incidents]

    async def _get_system_status(self) -> SystemStatus:
        """Get system status."""
        if self.health_checker:
            health = self.health_checker.check()
            if health == HealthStatus.HEALTHY:
                return SystemStatus.OPERATIONAL
            elif health == HealthStatus.DEGRADED:
                return SystemStatus.DEGRADED
            elif health == HealthStatus.UNHEALTHY:
                return SystemStatus.PARTIAL_OUTAGE
            else:
                return SystemStatus.UNKNOWN

        return SystemStatus.OPERATIONAL

    async def _get_uptime(self) -> float:
        """Get system uptime."""
        if self.hedge_engine:
            return self.hedge_engine.get_uptime()
        return time.time() - psutil.boot_time()

    async def _get_metrics(
        self,
        name: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DashboardMetric]:
        """Get metrics with optional filtering."""
        with self._history_lock:
            metrics = self._metric_history

            if name:
                metrics = [m for m in metrics if m.name == name]

            # Sort by timestamp descending
            metrics = sorted(metrics, key=lambda m: m.timestamp, reverse=True)

            # Apply pagination
            total = len(metrics)
            metrics = metrics[offset:offset + limit]

            return metrics

    def get_app(self) -> FastAPI:
        """Get the FastAPI application."""
        return self._app

    async def start(self) -> None:
        """Start the dashboard API server."""
        self._running = True
        self._shutdown = False

        config = uvicorn.Config(
            self._app,
            host=self.config.host,
            port=self.config.port,
            log_level="info",
        )
        server = uvicorn.Server(config)

        logger.info(
            "dashboard_api_starting",
            host=self.config.host,
            port=self.config.port,
        )

        try:
            await server.serve()
        except KeyboardInterrupt:
            await self.stop()
        except Exception as e:
            logger.error("dashboard_api_start_error", error=str(e))
            await self.stop()

    async def stop(self) -> None:
        """Stop the dashboard API server."""
        self._shutdown = True
        self._running = False

        # Close all WebSocket connections
        with self._websocket_lock:
            for websocket in self._websocket_connections:
                try:
                    await websocket.close()
                except Exception:
                    pass
            self._websocket_connections.clear()

        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()

        logger.info("dashboard_api_stopped")

    def run_sync(self) -> None:
        """Run the dashboard API server synchronously."""
        asyncio.run(self.start())

    def __enter__(self) -> "DashboardAPI":
        return self

    def __exit__(self, *args) -> None:
        asyncio.run(self.stop())


# === FACTORY FUNCTION ===

def create_dashboard_api(
    config: Union[DashboardConfig, Dict[str, Any], str],
    **kwargs
) -> DashboardAPI:
    """Create a DashboardAPI instance with optional dependencies."""
    return DashboardAPI(config, **kwargs)


# === MODULE EXPORTS ===

__all__ = [
    "DashboardAPI",
    "DashboardConfig",
    "DashboardData",
    "DashboardMetric",
    "SystemStatus",
    "create_dashboard_api",
]

logger.info("dashboard_api_module_loaded", version="3.0.0")
