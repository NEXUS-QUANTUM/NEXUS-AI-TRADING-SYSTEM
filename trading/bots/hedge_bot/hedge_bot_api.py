# trading/bots/hedge_bot/hedge_bot_api.py
# NEXUS AI TRADING SYSTEM - Hedge Bot API Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot API Module

This module provides the REST API and WebSocket interface for the
NEXUS Hedge Bot system. It exposes all bot functionality through
secure, documented endpoints.

The API covers:
- Authentication & Authorization
- Trading Operations
- Position Management
- Order Management
- Portfolio Management
- Strategy Management
- Risk Management
- Configuration Management
- Monitoring & Health
- WebSocket Real-time Updates
- Admin Operations
- Reporting
"""

import os
import sys
import json
import time
import asyncio
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field, validator
from contextlib import asynccontextmanager

# Import hedge bot
from .hedge_bot import HedgeBot, HedgeBotConfig
from .hedge_bot_accounting import AccountingEngine
from .hedge_bot_analytics import AnalyticsEngine
from .hedge_bot_analyzer import AnalyzerEngine

logger = logging.getLogger(__name__)

# ============================================================
# PYDANTIC MODELS
# ============================================================

class LoginRequest(BaseModel):
    """Login request"""
    username: str
    password: str
    two_factor_code: Optional[str] = None


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class OrderRequest(BaseModel):
    """Order request"""
    symbol: str
    side: str  # buy, sell
    type: str  # limit, market, stop_limit
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "GTC"
    client_order_id: Optional[str] = None


class OrderResponse(BaseModel):
    """Order response"""
    id: str
    symbol: str
    side: str
    type: str
    quantity: float
    price: Optional[float]
    filled_quantity: float
    status: str
    created_at: datetime
    updated_at: datetime


class PositionResponse(BaseModel):
    """Position response"""
    id: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    value: float
    status: str
    created_at: datetime
    updated_at: datetime


class PortfolioSummaryResponse(BaseModel):
    """Portfolio summary response"""
    total_value: float
    available_cash: float
    invested_value: float
    daily_pnl: float
    daily_pnl_percent: float
    total_pnl: float
    total_pnl_percent: float
    allocation: Dict[str, float]
    diversification_score: float
    updated_at: datetime


class StrategyStatusResponse(BaseModel):
    """Strategy status response"""
    name: str
    status: str
    is_running: bool
    metrics: Dict[str, Any]
    positions: Dict[str, Any]
    performance: Dict[str, Any]
    last_update: datetime


class RiskMetricsResponse(BaseModel):
    """Risk metrics response"""
    var_95: float
    var_99: float
    cvar_95: float
    expected_shortfall: float
    current_drawdown: float
    max_drawdown: float
    margin_utilization: float
    liquidation_risk: float
    risk_score: float
    timestamp: datetime


class HealthResponse(BaseModel):
    """Health response"""
    status: str
    version: str
    uptime: float
    components: Dict[str, Any]
    timestamp: datetime


# ============================================================
# API ROUTES
# ============================================================

class HedgeBotAPI:
    """
    Hedge Bot API Router
    
    Provides REST API endpoints for the hedge bot
    """
    
    def __init__(self, bot: HedgeBot):
        self.bot = bot
        self.app = FastAPI(
            title="NEXUS Hedge Bot API",
            description="Trading API for NEXUS Hedge Bot",
            version="2.0.0",
            lifespan=self._lifespan,
        )
        
        # Security
        self.security = HTTPBearer()
        
        # Setup middleware
        self._setup_middleware()
        
        # Setup routes
        self._setup_routes()
        
        # Setup WebSocket
        self._setup_websocket()
        
        logger.info("Hedge Bot API initialized")
    
    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        """Lifespan context manager"""
        logger.info("Starting up API...")
        yield
        logger.info("Shutting down API...")
    
    def _setup_middleware(self) -> None:
        """Setup middleware"""
        # CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # GZip compression
        self.app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    def _setup_routes(self) -> None:
        """Setup API routes"""
        
        # ============================================================
        # HEALTH & STATUS
        # ============================================================
        
        @self.app.get("/health", response_model=HealthResponse)
        async def health_check():
            """Health check endpoint"""
            health = self.bot.health_check()
            return HealthResponse(
                status=health["status"],
                version=self.bot.config.version,
                uptime=(datetime.now() - self.bot.start_time).total_seconds() if self.bot.start_time else 0,
                components=health.get("components", {}),
                timestamp=datetime.now(),
            )
        
        @self.app.get("/ready")
        async def readiness_check():
            """Readiness check endpoint"""
            return {"status": "ready" if self.bot.is_running else "not_ready"}
        
        @self.app.get("/live")
        async def liveness_check():
            """Liveness check endpoint"""
            return {"status": "alive"}
        
        # ============================================================
        # AUTHENTICATION
        # ============================================================
        
        @self.app.post("/auth/login", response_model=TokenResponse)
        async def login(request: LoginRequest):
            """Login endpoint"""
            # Authenticate user
            # (Implement actual authentication)
            return TokenResponse(
                access_token="mock_access_token",
                refresh_token="mock_refresh_token",
                expires_in=3600,
            )
        
        @self.app.post("/auth/refresh", response_model=TokenResponse)
        async def refresh_token(token: str):
            """Refresh token endpoint"""
            # (Implement token refresh)
            return TokenResponse(
                access_token="mock_access_token",
                refresh_token="mock_refresh_token",
                expires_in=3600,
            )
        
        @self.app.post("/auth/logout")
        async def logout():
            """Logout endpoint"""
            return {"message": "Logged out successfully"}
        
        # ============================================================
        # TRADING
        # ============================================================
        
        @self.app.get("/trading/positions", response_model=List[PositionResponse])
        async def get_positions():
            """Get all positions"""
            if not self.bot.portfolio_manager:
                raise HTTPException(status_code=503, detail="Portfolio manager not available")
            
            positions = self.bot.portfolio_manager.get_positions()
            return [PositionResponse(**p) for p in positions]
        
        @self.app.get("/trading/positions/{position_id}", response_model=PositionResponse)
        async def get_position(position_id: str):
            """Get position by ID"""
            if not self.bot.portfolio_manager:
                raise HTTPException(status_code=503, detail="Portfolio manager not available")
            
            position = self.bot.portfolio_manager.get_position(position_id)
            if not position:
                raise HTTPException(status_code=404, detail="Position not found")
            
            return PositionResponse(**position)
        
        @self.app.get("/trading/orders", response_model=List[OrderResponse])
        async def get_orders():
            """Get all orders"""
            if not self.bot.execution_engine:
                raise HTTPException(status_code=503, detail="Execution engine not available")
            
            orders = self.bot.execution_engine.get_orders()
            return [OrderResponse(**o) for o in orders]
        
        @self.app.post("/trading/orders", response_model=OrderResponse)
        async def place_order(request: OrderRequest):
            """Place an order"""
            if not self.bot.execution_engine:
                raise HTTPException(status_code=503, detail="Execution engine not available")
            
            # Check if bot is running
            if not self.bot.is_running:
                raise HTTPException(status_code=400, detail="Bot is not running")
            
            try:
                order = self.bot.execution_engine.place_order(request.dict())
                return OrderResponse(**order)
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.delete("/trading/orders/{order_id}")
        async def cancel_order(order_id: str):
            """Cancel an order"""
            if not self.bot.execution_engine:
                raise HTTPException(status_code=503, detail="Execution engine not available")
            
            try:
                result = self.bot.execution_engine.cancel_order(order_id)
                return {"message": "Order cancelled successfully", "order_id": order_id}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.get("/trading/history")
        async def get_trade_history(
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            symbol: Optional[str] = None,
            limit: int = 100
        ):
            """Get trade history"""
            if not self.bot.execution_engine:
                raise HTTPException(status_code=503, detail="Execution engine not available")
            
            trades = self.bot.execution_engine.get_trade_history(
                start_date=start_date,
                end_date=end_date,
                symbol=symbol,
                limit=limit,
            )
            return {"trades": trades, "total": len(trades), "limit": limit}
        
        # ============================================================
        # STRATEGY
        # ============================================================
        
        @self.app.get("/strategy/status", response_model=StrategyStatusResponse)
        async def get_strategy_status():
            """Get strategy status"""
            status = self.bot.get_status()
            return StrategyStatusResponse(
                name=self.bot.config.name,
                status=status["status"],
                is_running=status["is_running"],
                metrics=status.get("metrics", {}),
                positions=status.get("positions", {}),
                performance=status.get("performance", {}),
                last_update=datetime.now(),
            )
        
        @self.app.post("/strategy/start")
        async def start_strategy(strategy_name: str = "delta_hedging"):
            """Start a strategy"""
            if self.bot.is_running:
                raise HTTPException(status_code=400, detail="Bot is already running")
            
            try:
                self.bot.start()
                return {"message": f"Strategy {strategy_name} started successfully", "status": "running"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/strategy/stop")
        async def stop_strategy(emergency: bool = False):
            """Stop a strategy"""
            if not self.bot.is_running:
                raise HTTPException(status_code=400, detail="Bot is not running")
            
            try:
                self.bot.stop()
                return {"message": "Strategy stopped successfully", "status": "stopped"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/strategy/parameters")
        async def get_strategy_parameters():
            """Get strategy parameters"""
            return self.bot.config.strategy_params
        
        @self.app.patch("/strategy/parameters")
        async def update_strategy_parameters(parameters: Dict[str, Any]):
            """Update strategy parameters"""
            try:
                self.bot.config.strategy_params.update(parameters)
                self.bot.reload_config()
                return {"message": "Strategy parameters updated successfully"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.get("/strategy/performance")
        async def get_strategy_performance(period: str = "month"):
            """Get strategy performance"""
            performance = self.bot.get_performance_report()
            return performance
        
        # ============================================================
        # RISK
        # ============================================================
        
        @self.app.get("/risk/metrics", response_model=RiskMetricsResponse)
        async def get_risk_metrics():
            """Get risk metrics"""
            if not self.bot.risk_manager:
                raise HTTPException(status_code=503, detail="Risk manager not available")
            
            metrics = self.bot.risk_manager.get_summary()
            return RiskMetricsResponse(
                var_95=metrics.get("var_95", 0),
                var_99=metrics.get("var_99", 0),
                cvar_95=metrics.get("cvar_95", 0),
                expected_shortfall=metrics.get("expected_shortfall", 0),
                current_drawdown=metrics.get("current_drawdown", 0),
                max_drawdown=metrics.get("max_drawdown", 0),
                margin_utilization=metrics.get("margin_utilization", 0),
                liquidation_risk=metrics.get("liquidation_risk", 0),
                risk_score=metrics.get("risk_score", 0),
                timestamp=datetime.now(),
            )
        
        @self.app.get("/risk/limits")
        async def get_risk_limits():
            """Get risk limits"""
            return self.bot.config.__dict__
        
        @self.app.patch("/risk/limits")
        async def update_risk_limits(limits: Dict[str, Any]):
            """Update risk limits"""
            try:
                for key, value in limits.items():
                    if hasattr(self.bot.config, key):
                        setattr(self.bot.config, key, value)
                return {"message": "Risk limits updated successfully"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.post("/risk/stress-test")
        async def run_stress_test(scenario: Dict[str, Any]):
            """Run stress test"""
            # (Implement stress test)
            return {"message": "Stress test completed", "results": {}}
        
        # ============================================================
        # PORTFOLIO
        # ============================================================
        
        @self.app.get("/portfolio/summary", response_model=PortfolioSummaryResponse)
        async def get_portfolio_summary():
            """Get portfolio summary"""
            if not self.bot.portfolio_manager:
                raise HTTPException(status_code=503, detail="Portfolio manager not available")
            
            summary = self.bot.portfolio_manager.get_summary()
            return PortfolioSummaryResponse(**summary)
        
        @self.app.get("/portfolio/allocation")
        async def get_portfolio_allocation():
            """Get portfolio allocation"""
            if not self.bot.portfolio_manager:
                raise HTTPException(status_code=503, detail="Portfolio manager not available")
            
            return self.bot.portfolio_manager.get_allocation()
        
        @self.app.post("/portfolio/rebalance")
        async def rebalance_portfolio(target_allocation: Dict[str, float], execute: bool = True):
            """Rebalance portfolio"""
            if not self.bot.portfolio_manager:
                raise HTTPException(status_code=503, detail="Portfolio manager not available")
            
            if not self.bot.is_running:
                raise HTTPException(status_code=400, detail="Bot is not running")
            
            try:
                result = self.bot.portfolio_manager.rebalance(target_allocation, execute)
                return result
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        # ============================================================
        # CONFIGURATION
        # ============================================================
        
        @self.app.get("/config")
        async def get_config():
            """Get configuration"""
            return self.bot.config.__dict__
        
        @self.app.patch("/config")
        async def update_config(config: Dict[str, Any]):
            """Update configuration"""
            try:
                # Update config
                for key, value in config.items():
                    if hasattr(self.bot.config, key):
                        setattr(self.bot.config, key, value)
                
                # Reload
                self.bot.reload_config()
                return {"message": "Configuration updated successfully"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.post("/config/reload")
        async def reload_config():
            """Reload configuration"""
            try:
                self.bot.reload()
                return {"message": "Configuration reloaded successfully"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        # ============================================================
        # ACCOUNTING
        # ============================================================
        
        @self.app.get("/accounting/pnl")
        async def get_pnl_report(
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
        ):
            """Get PnL report"""
            # (Implement PnL report)
            return {"message": "PnL report generated"}
        
        @self.app.get("/accounting/performance")
        async def get_performance_report():
            """Get performance report"""
            # (Implement performance report)
            return {"message": "Performance report generated"}
        
        # ============================================================
        # WEBSOCKET
        # ============================================================
        
        self.websocket_manager = WebSocketManager()
    
    def _setup_websocket(self) -> None:
        """Setup WebSocket endpoint"""
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint"""
            await self.websocket_manager.connect(websocket)
            
            try:
                while True:
                    data = await websocket.receive_text()
                    await self.websocket_manager.handle_message(websocket, data)
            except WebSocketDisconnect:
                self.websocket_manager.disconnect(websocket)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.websocket_manager.disconnect(websocket)
    
    # ============================================================
    # ADMIN OPERATIONS
    # ============================================================
    
    @self.app.post("/admin/start")
    async def admin_start():
        """Admin: Start bot"""
        try:
            self.bot.start()
            return {"message": "Bot started successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @self.app.post("/admin/stop")
    async def admin_stop():
        """Admin: Stop bot"""
        try:
            self.bot.stop()
            return {"message": "Bot stopped successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @self.app.post("/admin/restart")
    async def admin_restart():
        """Admin: Restart bot"""
        try:
            self.bot.stop()
            self.bot.start()
            return {"message": "Bot restarted successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# WEBSOCKET MANAGER
# ============================================================

class WebSocketManager:
    """WebSocket connection manager"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[WebSocket, List[str]] = {}
    
    async def connect(self, websocket: WebSocket):
        """Accept WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = []
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
    
    async def handle_message(self, websocket: WebSocket, message: str):
        """Handle WebSocket message"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            if msg_type == "subscribe":
                channel = data.get("channel")
                if channel:
                    if channel not in self.subscriptions[websocket]:
                        self.subscriptions[websocket].append(channel)
                    await websocket.send_json({
                        "type": "subscribed",
                        "channel": channel,
                        "status": "success",
                    })
            
            elif msg_type == "unsubscribe":
                channel = data.get("channel")
                if channel and channel in self.subscriptions[websocket]:
                    self.subscriptions[websocket].remove(channel)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "channel": channel,
                        "status": "success",
                    })
            
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })
                
        except json.JSONDecodeError:
            await websocket.send_json({
                "type": "error",
                "message": "Invalid JSON",
            })
    
    async def broadcast(self, channel: str, data: Dict[str, Any]):
        """Broadcast message to all subscribers of a channel"""
        for websocket in self.active_connections:
            if websocket in self.subscriptions and channel in self.subscriptions[websocket]:
                try:
                    await websocket.send_json({
                        "channel": channel,
                        "data": data,
                        "timestamp": datetime.now().isoformat(),
                    })
                except Exception:
                    pass


# ============================================================
# FACTORY FUNCTION
# ============================================================

def create_api(bot: HedgeBot) -> FastAPI:
    """
    Create FastAPI application with all routes
    
    Args:
        bot: Hedge bot instance
        
    Returns:
        FastAPI application
    """
    api = HedgeBotAPI(bot)
    return api.app


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    "HedgeBotAPI",
    "WebSocketManager",
    "create_api",
]

# ============================================================
# END OF MODULE
# ============================================================
