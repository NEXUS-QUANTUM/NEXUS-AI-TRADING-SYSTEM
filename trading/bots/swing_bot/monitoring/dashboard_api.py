"""
Swing Bot Dashboard API
=========================

This module provides a dashboard API for the Swing Bot trading system.
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from trading.bots.swing_bot.core import Engine
from trading.bots.swing_bot.monitoring import (
    MetricCollector,
    HealthChecker,
    IncidentManager,
    NotificationService,
    PerformanceMonitor
)


class DashboardAPI:
    """
    Dashboard API for the Swing Bot trading system.
    """
    
    def __init__(
        self,
        engine: Engine,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the dashboard API.
        
        Args:
            engine: Trading engine instance
            config: API configuration
        """
        self.engine = engine
        self.config = config or {}
        self.host = self.config.get('host', '0.0.0.0')
        self.port = self.config.get('port', 8080)
        
        # Initialize components
        self.metric_collector = MetricCollector(self.config.get('metrics', {}))
        self.health_checker = HealthChecker(self.config.get('health', {}))
        self.incident_manager = IncidentManager(self.config.get('incidents', {}))
        self.notification_service = NotificationService(self.config.get('notification', {}))
        self.performance_monitor = PerformanceMonitor(self.config.get('performance', {}))
        
        # WebSocket connections
        self.websocket_connections: List[WebSocket] = []
        
        # Create FastAPI app
        self.app = FastAPI(
            title="NEXUS Trading Dashboard API",
            description="API for the Swing Bot trading dashboard",
            version="3.0.0"
        )
        
        # Register routes
        self._register_routes()
        
        # Start background tasks
        self._start_background_tasks()
    
    def _register_routes(self) -> None:
        """Register API routes."""
        
        @self.app.get("/")
        async def root():
            return {
                "name": "NEXUS Trading Dashboard API",
                "version": "3.0.0",
                "status": "running",
                "endpoints": [
                    "/metrics",
                    "/health",
                    "/status",
                    "/incidents",
                    "/performance",
                    "/logs",
                    "/trades",
                    "/positions",
                    "/portfolio",
                    "/ws"
                ]
            }
        
        @self.app.get("/metrics")
        async def get_metrics(
            name: Optional[str] = None,
            limit: int = Query(100, ge=1, le=1000)
        ):
            """Get metrics data."""
            if name:
                data = self.metric_collector.get_metric(name, limit)
                return {"metric": name, "data": data}
            else:
                data = self.metric_collector.get_all_summaries()
                return {"metrics": data}
        
        @self.app.get("/health")
        async def get_health():
            """Get health status."""
            report = self.health_checker.get_report()
            return {
                "status": report.status.value,
                "timestamp": report.timestamp.isoformat(),
                "summary": report.summary,
                "checks": report.checks
            }
        
        @self.app.get("/status")
        async def get_status():
            """Get system status."""
            return {
                "status": "running",
                "timestamp": datetime.now().isoformat(),
                "engine": {
                    "is_running": self.engine.is_running,
                    "strategies": len(self.engine.strategies),
                    "trades": len(getattr(self.engine, 'trades', [])),
                    "positions": len(getattr(self.engine, 'positions', []))
                },
                "performance": self.performance_monitor.get_all_metrics(),
                "health": self.health_checker.get_status().value
            }
        
        @self.app.get("/incidents")
        async def get_incidents(
            status: Optional[str] = None,
            severity: Optional[str] = None,
            limit: int = Query(50, ge=1, le=200)
        ):
            """Get incidents."""
            incidents = list(self.incident_manager.incidents.values())
            
            if status:
                incidents = [i for i in incidents if i.status.value == status.lower()]
            if severity:
                incidents = [i for i in incidents if i.severity.value == severity.lower()]
            
            # Sort by creation time, newest first
            incidents.sort(key=lambda x: x.created_at, reverse=True)
            incidents = incidents[:limit]
            
            return {
                "total": len(self.incident_manager.incidents),
                "active": len(self.incident_manager.active_incidents),
                "incidents": [
                    {
                        "id": i.id,
                        "title": i.title,
                        "severity": i.severity.value,
                        "status": i.status.value,
                        "type": i.type.value,
                        "created_at": i.created_at.isoformat(),
                        "assigned_to": i.assigned_to,
                        "resolution": i.resolution
                    }
                    for i in incidents
                ]
            }
        
        @self.app.get("/performance")
        async def get_performance():
            """Get performance metrics."""
            return {
                "timestamp": datetime.now().isoformat(),
                "metrics": self.performance_monitor.get_all_metrics(),
                "system": self.performance_monitor.get_system_health()
            }
        
        @self.app.get("/logs")
        async def get_logs(
            level: Optional[str] = None,
            limit: int = Query(100, ge=1, le=1000),
            source: Optional[str] = None
        ):
            """Get recent logs."""
            # This is a placeholder - implement actual log retrieval
            return {
                "message": "Log retrieval not implemented",
                "level": level,
                "limit": limit,
                "source": source
            }
        
        @self.app.get("/trades")
        async def get_trades(
            symbol: Optional[str] = None,
            limit: int = Query(100, ge=1, le=1000)
        ):
            """Get recent trades."""
            trades = getattr(self.engine, 'trades', [])
            
            if symbol:
                trades = [t for t in trades if t.symbol == symbol]
            
            trades = trades[-limit:]
            
            return {
                "total": len(getattr(self.engine, 'trades', [])),
                "trades": [
                    {
                        "order_id": t.order_id,
                        "symbol": t.symbol,
                        "side": t.side.value,
                        "quantity": t.quantity,
                        "price": t.price,
                        "executed_at": t.executed_at.isoformat() if t.executed_at else None,
                        "commission": t.commission
                    }
                    for t in trades
                ]
            }
        
        @self.app.get("/positions")
        async def get_positions():
            """Get current positions."""
            positions = getattr(self.engine, 'positions', [])
            
            return {
                "total": len(positions),
                "positions": [
                    {
                        "symbol": p.symbol,
                        "quantity": p.quantity,
                        "entry_price": p.entry_price,
                        "current_price": p.current_price,
                        "pnl": p.calculate_pnl(),
                        "pnl_percent": p.calculate_pnl_percent(),
                        "entry_time": p.entry_time.isoformat() if p.entry_time else None
                    }
                    for p in positions
                ]
            }
        
        @self.app.get("/portfolio")
        async def get_portfolio():
            """Get portfolio summary."""
            portfolio = getattr(self.engine, 'portfolio', None)
            if not portfolio:
                return {"error": "Portfolio not available"}
            
            return {
                "account_id": portfolio.account_id,
                "cash": portfolio.cash,
                "total_value": portfolio.calculate_total_value(),
                "total_pnl": portfolio.calculate_total_pnl(),
                "positions": len(portfolio.positions)
            }
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await websocket.accept()
            self.websocket_connections.append(websocket)
            
            try:
                while True:
                    # Receive messages
                    data = await websocket.receive_text()
                    await self._handle_websocket_message(websocket, data)
            except WebSocketDisconnect:
                self.websocket_connections.remove(websocket)
            except Exception as e:
                logging.error(f"WebSocket error: {e}")
                if websocket in self.websocket_connections:
                    self.websocket_connections.remove(websocket)
    
    async def _handle_websocket_message(self, websocket: WebSocket, data: str) -> None:
        """
        Handle WebSocket messages.
        
        Args:
            websocket: WebSocket connection
            data: Message data
        """
        try:
            message = json.loads(data)
            action = message.get('action')
            
            if action == 'subscribe':
                channel = message.get('channel')
                if channel:
                    # Add to subscription tracking
                    pass
            elif action == 'get_metrics':
                data = self.metric_collector.get_all_summaries()
                await websocket.send_json({
                    'type': 'metrics',
                    'data': data
                })
            elif action == 'get_status':
                status = await self.get_status()
                await websocket.send_json({
                    'type': 'status',
                    'data': status
                })
            else:
                await websocket.send_json({
                    'type': 'error',
                    'message': f"Unknown action: {action}"
                })
        except json.JSONDecodeError:
            await websocket.send_json({
                'type': 'error',
                'message': 'Invalid JSON'
            })
    
    async def broadcast_update(self, update_type: str, data: Dict[str, Any]) -> None:
        """
        Broadcast an update to all WebSocket connections.
        
        Args:
            update_type: Type of update
            data: Update data
        """
        if not self.websocket_connections:
            return
        
        message = {
            'type': update_type,
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
        
        for websocket in self.websocket_connections[:]:
            try:
                await websocket.send_json(message)
            except Exception:
                # Remove failed connections
                if websocket in self.websocket_connections:
                    self.websocket_connections.remove(websocket)
    
    def _start_background_tasks(self) -> None:
        """Start background tasks."""
        # Start health checker
        self.health_checker.start()
        
        # Start performance monitor
        self.performance_monitor.start()
        
        # Start metric collector
        self.metric_collector.start()
    
    def run(self) -> None:
        """Run the dashboard API server."""
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
    
    async def run_async(self) -> None:
        """Run the dashboard API server asynchronously."""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    def stop(self) -> None:
        """Stop the dashboard API."""
        self.health_checker.stop()
        self.performance_monitor.stop()
        self.metric_collector.stop()


def create_dashboard_app(
    engine: Engine,
    config: Optional[Dict[str, Any]] = None
) -> DashboardAPI:
    """
    Create a dashboard API instance.
    
    Args:
        engine: Trading engine instance
        config: API configuration
    
    Returns:
        DashboardAPI instance
    """
    return DashboardAPI(engine, config)


if __name__ == "__main__":
    # Example usage
    engine = Engine()
    dashboard = create_dashboard_app(engine)
    dashboard.run()
