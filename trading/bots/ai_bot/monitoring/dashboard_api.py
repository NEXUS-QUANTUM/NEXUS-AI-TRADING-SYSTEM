"""
NEXUS AI TRADING SYSTEM - Dashboard API
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced dashboard API for monitoring trading bots, models, and system health.
Provides real-time data endpoints for frontend visualization, analytics,
and system management.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import generate_latest

from shared.utilities.logger import get_logger
from shared.utilities.metrics import MetricsCollector
from shared.utilities.cache_utils import CacheManager

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class DashboardAPI:
    """
    Dashboard API for trading system monitoring and management.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        bot_manager: Optional[Any] = None,
        model_registry: Optional[Any] = None,
        alert_manager: Optional[Any] = None,
        cache_manager: Optional[CacheManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the dashboard API.

        Args:
            config: Configuration dictionary
            bot_manager: Bot manager instance
            model_registry: Model registry instance
            alert_manager: Alert manager instance
            cache_manager: Cache manager instance
            metrics_collector: Metrics collector instance
        """
        self.config = config or {}
        self.bot_manager = bot_manager
        self.model_registry = model_registry
        self.alert_manager = alert_manager
        self.cache_manager = cache_manager or CacheManager()
        self.metrics_collector = metrics_collector or MetricsCollector()
        self._websocket_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()
        self._broadcast_task: Optional[asyncio.Task] = None

        # Load configuration
        self.dashboard_config = self.config.get("dashboard", {})
        self.update_interval = self.dashboard_config.get("update_interval", 5)
        self.history_retention_days = self.dashboard_config.get("history_retention_days", 30)
        self.max_data_points = self.dashboard_config.get("max_data_points", 1000)

        # Start broadcast task
        self._start_broadcast_task()

        logger.info("DashboardAPI initialized")

    def _start_broadcast_task(self):
        """Start the broadcast task for WebSocket updates."""
        if self._broadcast_task is None:
            self._broadcast_task = asyncio.create_task(self._broadcast_loop())
            logger.info("Broadcast task started")

    async def _broadcast_loop(self):
        """Broadcast updates to all WebSocket connections."""
        while True:
            try:
                if self._websocket_connections:
                    # Gather dashboard data
                    data = await self.get_dashboard_data()

                    # Broadcast to all connections
                    to_remove = []
                    for ws in self._websocket_connections:
                        try:
                            await ws.send_json(data)
                        except WebSocketDisconnect:
                            to_remove.append(ws)
                        except Exception as e:
                            logger.error(f"Error broadcasting to WebSocket: {e}")
                            to_remove.append(ws)

                    # Remove disconnected clients
                    if to_remove:
                        async with self._lock:
                            for ws in to_remove:
                                if ws in self._websocket_connections:
                                    self._websocket_connections.remove(ws)

                await asyncio.sleep(self.update_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")
                await asyncio.sleep(5)

    @router.get("/overview")
    async def get_overview(
        self,
        timeframe: str = Query("1h", description="Timeframe for data aggregation"),
    ) -> JSONResponse:
        """
        Get system overview data.

        Args:
            timeframe: Timeframe for data aggregation

        Returns:
            System overview data
        """
        try:
            # Get bot status
            bots_status = await self._get_bots_status()

            # Get model status
            models_status = await self._get_models_status()

            # Get active alerts
            active_alerts = await self._get_active_alerts()

            # Get system metrics
            system_metrics = await self._get_system_metrics()

            # Get trading summary
            trading_summary = await self._get_trading_summary(timeframe)

            return JSONResponse({
                "status": "success",
                "data": {
                    "bots": bots_status,
                    "models": models_status,
                    "alerts": active_alerts,
                    "system": system_metrics,
                    "trading": trading_summary,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            })

        except Exception as e:
            logger.error(f"Error getting overview: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/bots")
    async def get_bots_status(
        self,
        bot_id: Optional[str] = Query(None, description="Filter by bot ID"),
    ) -> JSONResponse:
        """
        Get bot status information.

        Args:
            bot_id: Optional bot ID filter

        Returns:
            Bot status data
        """
        try:
            if self.bot_manager is None:
                return JSONResponse({
                    "status": "warning",
                    "message": "Bot manager not available",
                    "data": []
                })

            bots = await self.bot_manager.get_bots()

            if bot_id:
                bots = [b for b in bots if b["id"] == bot_id]

            # Enrich with additional data
            for bot in bots:
                # Get bot performance
                performance = await self.bot_manager.get_bot_performance(bot["id"])
                bot["performance"] = performance

                # Get bot metrics
                metrics = await self.bot_manager.get_bot_metrics(bot["id"])
                bot["metrics"] = metrics

            return JSONResponse({
                "status": "success",
                "data": bots,
                "count": len(bots),
                "timestamp": datetime.utcnow().isoformat(),
            })

        except Exception as e:
            logger.error(f"Error getting bots status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/bots/{bot_id}/performance")
    async def get_bot_performance(
        self,
        bot_id: str,
        timeframe: str = Query("24h", description="Timeframe for performance data"),
    ) -> JSONResponse:
        """
        Get performance data for a specific bot.

        Args:
            bot_id: Bot ID
            timeframe: Timeframe for data

        Returns:
            Bot performance data
        """
        try:
            if self.bot_manager is None:
                raise HTTPException(status_code=503, detail="Bot manager not available")

            performance = await self.bot_manager.get_bot_performance(
                bot_id,
                timeframe=timeframe,
            )

            return JSONResponse({
                "status": "success",
                "data": performance,
                "bot_id": bot_id,
                "timestamp": datetime.utcnow().isoformat(),
            })

        except Exception as e:
            logger.error(f"Error getting bot performance: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/models")
    async def get_models_status(
        self,
        model_type: Optional[str] = Query(None, description="Filter by model type"),
        status: Optional[str] = Query(None, description="Filter by status"),
    ) -> JSONResponse:
        """
        Get model status information.

        Args:
            model_type: Optional model type filter
            status: Optional status filter

        Returns:
            Model status data
        """
        try:
            if self.model_registry is None:
                return JSONResponse({
                    "status": "warning",
                    "message": "Model registry not available",
                    "data": []
                })

            models = await self.model_registry.list_models()

            if model_type:
                models = [m for m in models if m.model_type == model_type]

            if status:
                models = [
                    m for m in models
                    if any(v.status.value == status for v in m.versions.values())
                ]

            # Enrich with metrics
            for model in models:
                latest_version = model.versions.get(model.current_version or "")
                if latest_version:
                    model.metrics = latest_version.metrics
                    model.deployed_at = latest_version.deployed_at

            return JSONResponse({
                "status": "success",
                "data": [m.to_dict() for m in models],
                "count": len(models),
                "timestamp": datetime.utcnow().isoformat(),
            })

        except Exception as e:
            logger.error(f"Error getting models status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/models/{model_id}/versions")
    async def get_model_versions(
        self,
        model_id: str,
        limit: int = Query(10, description="Maximum number of versions"),
    ) -> JSONResponse:
        """
        Get version history for a model.

        Args:
            model_id: Model ID
            limit: Maximum number of versions

        Returns:
            Model version history
        """
        try:
            if self.model_registry is None:
                raise HTTPException(status_code=503, detail="Model registry not available")

            versions = await self.model_registry.list_versions(
                model_id,
                limit=limit,
            )

            return JSONResponse({
                "status": "success",
                "data": [v.to_dict() for v in versions],
                "model_id": model_id,
                "count": len(versions),
                "timestamp": datetime.utcnow().isoformat(),
            })

        except Exception as e:
            logger.error(f"Error getting model versions: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/alerts")
    async def get_alerts(
        self,
        severity: Optional[str] = Query(None, description="Filter by severity"),
        category: Optional[str] = Query(None, description="Filter by category"),
        status: Optional[str] = Query(None, description="Filter by status"),
        limit: int = Query(100, description="Maximum number of alerts"),
    ) -> JSONResponse:
        """
        Get alert history.

        Args:
            severity: Optional severity filter
            category: Optional category filter
            status: Optional status filter
            limit: Maximum number of alerts

        Returns:
            Alert data
        """
        try:
            if self.alert_manager is None:
                return JSONResponse({
                    "status": "warning",
                    "message": "Alert manager not available",
                    "data": []
                })

            alerts = await self.alert_manager.get_alert_history(
                limit=limit,
                severity=severity,
                category=category,
                status=status,
            )

            return JSONResponse({
                "status": "success",
                "data": [a.to_dict() for a in alerts],
                "count": len(alerts),
                "timestamp": datetime.utcnow().isoformat(),
            })

        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/alerts/active")
    async def get_active_alerts(
        self,
        severity: Optional[str] = Query(None, description="Filter by severity"),
    ) -> JSONResponse:
        """
        Get active alerts.

        Args:
            severity: Optional severity filter

        Returns:
            Active alerts
        """
        try:
            if self.alert_manager is None:
                return JSONResponse({
                    "status": "warning",
                    "message": "Alert manager not available",
                    "data": []
                })

            alerts = await self.alert_manager.get_active_alerts(
                severity=severity,
            )

            return JSONResponse({
                "status": "success",
                "data": [a.to_dict() for a in alerts],
                "count": len(alerts),
                "timestamp": datetime.utcnow().isoformat(),
            })

        except Exception as e:
            logger.error(f"Error getting active alerts: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/metrics")
    async def get_metrics(
        self,
        metric_names: Optional[str] = Query(None, description="Comma-separated metric names"),
        timeframe: str = Query("1h", description="Timeframe for metrics"),
    ) -> JSONResponse:
        """
        Get system metrics.

        Args:
            metric_names: Comma-separated metric names
            timeframe: Timeframe for data

        Returns:
            System metrics
        """
        try:
            if self.metrics_collector is None:
                return JSONResponse({
                    "status": "warning",
                    "message": "Metrics collector not available",
                    "data": {}
                })

            names = metric_names.split(",") if metric_names else None
            metrics = await self.metrics_collector.get_metrics(
                names=names,
                timeframe=timeframe,
            )

            return JSONResponse({
                "status": "success",
                "data": metrics,
                "timestamp": datetime.utcnow().isoformat(),
            })

        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/metrics/prometheus")
    async def get_prometheus_metrics(self) -> StreamingResponse:
        """
        Get Prometheus metrics for scraping.

        Returns:
            Prometheus metrics
        """
        try:
            metrics = generate_latest()
            return StreamingResponse(
                metrics,
                media_type="text/plain; version=0.0.4; charset=utf-8",
                headers={
                    "Content-Type": "text/plain; version=0.0.4; charset=utf-8",
                },
            )

        except Exception as e:
            logger.error(f"Error getting Prometheus metrics: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/trading/summary")
    async def get_trading_summary(
        self,
        timeframe: str = Query("24h", description="Timeframe for summary"),
    ) -> JSONResponse:
        """
        Get trading summary.

        Args:
            timeframe: Timeframe for summary

        Returns:
            Trading summary
        """
        try:
            summary = await self._get_trading_summary(timeframe)

            return JSONResponse({
                "status": "success",
                "data": summary,
                "timestamp": datetime.utcnow().isoformat(),
            })

        except Exception as e:
            logger.error(f"Error getting trading summary: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/trading/positions")
    async def get_positions(
        self,
        bot_id: Optional[str] = Query(None, description="Filter by bot ID"),
    ) -> JSONResponse:
        """
        Get current trading positions.

        Args:
            bot_id: Optional bot ID filter

        Returns:
            Current positions
        """
        try:
            if self.bot_manager is None:
                return JSONResponse({
                    "status": "warning",
                    "message": "Bot manager not available",
                    "data": []
                })

            positions = await self.bot_manager.get_positions(bot_id)

            return JSONResponse({
                "status": "success",
                "data": positions,
                "count": len(positions),
                "timestamp": datetime.utcnow().isoformat(),
            })

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/trading/history")
    async def get_trading_history(
        self,
        bot_id: Optional[str] = Query(None, description="Filter by bot ID"),
        symbol: Optional[str] = Query(None, description="Filter by symbol"),
        limit: int = Query(100, description="Maximum number of trades"),
        offset: int = Query(0, description="Offset for pagination"),
    ) -> JSONResponse:
        """
        Get trading history.

        Args:
            bot_id: Optional bot ID filter
            symbol: Optional symbol filter
            limit: Maximum number of trades
            offset: Offset for pagination

        Returns:
            Trading history
        """
        try:
            if self.bot_manager is None:
                return JSONResponse({
                    "status": "warning",
                    "message": "Bot manager not available",
                    "data": []
                })

            history = await self.bot_manager.get_trading_history(
                bot_id=bot_id,
                symbol=symbol,
                limit=limit,
                offset=offset,
            )

            return JSONResponse({
                "status": "success",
                "data": history,
                "count": len(history),
                "offset": offset,
                "timestamp": datetime.utcnow().isoformat(),
            })

        except Exception as e:
            logger.error(f"Error getting trading history: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/system/health")
    async def get_system_health(self) -> JSONResponse:
        """
        Get system health status.

        Returns:
            System health status
        """
        try:
            health = {
                "status": "healthy",
                "components": {},
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Check bot manager
            if self.bot_manager:
                try:
                    bot_status = await self.bot_manager.health_check()
                    health["components"]["bot_manager"] = bot_status
                    if bot_status.get("status") != "healthy":
                        health["status"] = "degraded"
                except Exception as e:
                    health["components"]["bot_manager"] = {"status": "unhealthy", "error": str(e)}
                    health["status"] = "unhealthy"

            # Check model registry
            if self.model_registry:
                try:
                    model_status = await self.model_registry.health_check()
                    health["components"]["model_registry"] = model_status
                    if model_status.get("status") != "healthy":
                        health["status"] = "degraded"
                except Exception as e:
                    health["components"]["model_registry"] = {"status": "unhealthy", "error": str(e)}
                    health["status"] = "unhealthy"

            # Check alert manager
            if self.alert_manager:
                try:
                    alert_status = await self.alert_manager.health_check()
                    health["components"]["alert_manager"] = alert_status
                    if alert_status.get("status") != "healthy":
                        health["status"] = "degraded"
                except Exception as e:
                    health["components"]["alert_manager"] = {"status": "unhealthy", "error": str(e)}
                    health["status"] = "unhealthy"

            # Check cache
            if self.cache_manager:
                try:
                    cache_status = await self.cache_manager.health_check()
                    health["components"]["cache"] = cache_status
                except Exception as e:
                    health["components"]["cache"] = {"status": "unhealthy", "error": str(e)}
                    health["status"] = "unhealthy"

            return JSONResponse(health)

        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/system/info")
    async def get_system_info(self) -> JSONResponse:
        """
        Get system information.

        Returns:
            System information
        """
        try:
            import platform
            import psutil

            info = {
                "system": {
                    "platform": platform.platform(),
                    "python_version": platform.python_version(),
                    "processor": platform.processor(),
                },
                "resources": {
                    "cpu_count": psutil.cpu_count(),
                    "cpu_percent": psutil.cpu_percent(interval=1),
                    "memory_total": psutil.virtual_memory().total,
                    "memory_available": psutil.virtual_memory().available,
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_usage": {
                        "total": psutil.disk_usage("/").total,
                        "used": psutil.disk_usage("/").used,
                        "free": psutil.disk_usage("/").free,
                        "percent": psutil.disk_usage("/").percent,
                    },
                },
                "uptime": time.time() - psutil.boot_time(),
                "timestamp": datetime.utcnow().isoformat(),
            }

            return JSONResponse({
                "status": "success",
                "data": info,
            })

        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @router.websocket("/ws")
    async def websocket_endpoint(
        self,
        websocket: WebSocket,
        token: str = Query(..., description="Authentication token"),
    ):
        """
        WebSocket endpoint for real-time dashboard updates.

        Args:
            websocket: WebSocket connection
            token: Authentication token
        """
        try:
            # Verify token
            # TODO: Implement proper token verification
            if not token:
                await websocket.close(code=4001, reason="Authentication required")
                return

            # Accept connection
            await websocket.accept()

            # Add to connections
            async with self._lock:
                self._websocket_connections.append(websocket)

            logger.info(f"WebSocket client connected: {websocket.client}")

            try:
                # Send initial data
                initial_data = await self.get_dashboard_data()
                await websocket.send_json(initial_data)

                # Handle messages from client
                while True:
                    try:
                        message = await websocket.receive_text()
                        # Process client messages
                        await self._handle_websocket_message(message, websocket)
                    except WebSocketDisconnect:
                        break
                    except Exception as e:
                        logger.error(f"Error handling WebSocket message: {e}")

            finally:
                # Remove connection
                async with self._lock:
                    if websocket in self._websocket_connections:
                        self._websocket_connections.remove(websocket)

                logger.info(f"WebSocket client disconnected: {websocket.client}")

        except Exception as e:
            logger.error(f"Error in WebSocket endpoint: {e}")
            try:
                await websocket.close(code=4000, reason=str(e))
            except Exception:
                pass

    async def _handle_websocket_message(self, message: str, websocket: WebSocket):
        """
        Handle WebSocket message from client.

        Args:
            message: Message from client
            websocket: WebSocket connection
        """
        try:
            data = json.loads(message)
            action = data.get("action")

            if action == "subscribe":
                channels = data.get("channels", [])
                # Handle subscription
                # Store subscription preferences
                pass

            elif action == "unsubscribe":
                channels = data.get("channels", [])
                # Handle unsubscription
                pass

            elif action == "ping":
                await websocket.send_json({"action": "pong"})

            elif action == "get_data":
                data_type = data.get("type", "overview")
                if data_type == "overview":
                    response = await self.get_overview()
                elif data_type == "metrics":
                    response = await self.get_metrics()
                elif data_type == "alerts":
                    response = await self.get_active_alerts()
                else:
                    response = {"status": "error", "message": f"Unknown data type: {data_type}"}
                await websocket.send_json(response)

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON message: {message}")

    async def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data.

        Returns:
            Dashboard data
        """
        try:
            return {
                "status": "success",
                "data": {
                    "overview": await self._get_overview_data(),
                    "bots": await self._get_bots_status(),
                    "models": await self._get_models_status(),
                    "alerts": await self._get_active_alerts(),
                    "metrics": await self._get_system_metrics(),
                    "trading": await self._get_trading_summary(),
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _get_overview_data(self) -> Dict[str, Any]:
        """Get overview data for dashboard."""
        return {
            "bots_total": await self._get_bots_count(),
            "bots_active": await self._get_bots_active_count(),
            "models_total": await self._get_models_count(),
            "models_production": await self._get_models_production_count(),
            "alerts_active": await self._get_active_alerts_count(),
            "alerts_critical": await self._get_critical_alerts_count(),
            "trading_pnl": await self._get_trading_pnl(),
            "trading_volume": await self._get_trading_volume(),
            "system_health": await self._get_system_health_status(),
            "updated_at": datetime.utcnow().isoformat(),
        }

    async def _get_bots_count(self) -> int:
        """Get total number of bots."""
        if self.bot_manager is None:
            return 0
        try:
            bots = await self.bot_manager.get_bots()
            return len(bots)
        except Exception:
            return 0

    async def _get_bots_active_count(self) -> int:
        """Get number of active bots."""
        if self.bot_manager is None:
            return 0
        try:
            bots = await self.bot_manager.get_bots()
            return sum(1 for b in bots if b.get("status") == "running")
        except Exception:
            return 0

    async def _get_models_count(self) -> int:
        """Get total number of models."""
        if self.model_registry is None:
            return 0
        try:
            models = await self.model_registry.list_models()
            return len(models)
        except Exception:
            return 0

    async def _get_models_production_count(self) -> int:
        """Get number of production models."""
        if self.model_registry is None:
            return 0
        try:
            models = await self.model_registry.list_models()
            return sum(1 for m in models if m.production_version)
        except Exception:
            return 0

    async def _get_active_alerts_count(self) -> int:
        """Get number of active alerts."""
        if self.alert_manager is None:
            return 0
        try:
            alerts = await self.alert_manager.get_active_alerts()
            return len(alerts)
        except Exception:
            return 0

    async def _get_critical_alerts_count(self) -> int:
        """Get number of critical alerts."""
        if self.alert_manager is None:
            return 0
        try:
            alerts = await self.alert_manager.get_active_alerts(
                severity="critical"
            )
            return len(alerts)
        except Exception:
            return 0

    async def _get_trading_pnl(self) -> float:
        """Get total trading PnL."""
        # TODO: Implement PnL calculation
        return 0.0

    async def _get_trading_volume(self) -> float:
        """Get total trading volume."""
        # TODO: Implement volume calculation
        return 0.0

    async def _get_system_health_status(self) -> str:
        """Get system health status."""
        health = await self.get_system_health()
        return health.get("status", "unknown")

    async def _get_system_metrics(self) -> Dict[str, Any]:
        """Get system metrics."""
        # TODO: Implement system metrics collection
        return {
            "cpu_usage": 0,
            "memory_usage": 0,
            "disk_usage": 0,
            "network_in": 0,
            "network_out": 0,
        }

    async def _get_trading_summary(self, timeframe: str = "24h") -> Dict[str, Any]:
        """
        Get trading summary.

        Args:
            timeframe: Timeframe for summary

        Returns:
            Trading summary
        """
        # TODO: Implement trading summary
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "total_volume": 0,
            "avg_profit": 0,
            "avg_loss": 0,
            "max_profit": 0,
            "max_loss": 0,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
            "timeframe": timeframe,
            "timestamp": datetime.utcnow().isoformat(),
        }


# Create API instance
dashboard_api = DashboardAPI()
