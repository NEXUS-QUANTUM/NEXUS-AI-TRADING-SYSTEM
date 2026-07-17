# trading/bots/ai_bot/ai_bot_api.py
"""
NEXUS AI TRADING SYSTEM - AI Bot API Interface
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements the REST API interface for the AI Trading Bot.
Provides endpoints for:
    - Bot management (start, stop, pause, resume)
    - Configuration management
    - Status and health monitoring
    - Trade execution and management
    - Position management
    - Performance metrics
    - Strategy management
    - Model management
    - Alert and notification management
    - Data and analytics
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, validator
import uvicorn
import pandas as pd
import numpy as np

# Import bot components
from trading.bots.ai_bot.ai_bot import AIBot, BotConfig, BotStatus, BotMode, create_ai_bot
from trading.bots.ai_bot.config import load_config
from trading.bots.ai_bot.monitoring import MetricsCollector, HealthChecker, AlertManager
from trading.bots.ai_bot.execution import ExecutionEngine
from trading.bots.ai_bot.position_manager import PositionManager
from trading.bots.ai_bot.strategy_engine import StrategyEngine
from trading.bots.ai_bot.model_manager import ModelManager

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models
# =============================================================================

class BotConfigRequest(BaseModel):
    """Bot configuration request model."""
    name: Optional[str] = "NEXUS AI Bot"
    mode: str = "paper"
    symbols: List[str] = ["BTC-USD", "ETH-USD"]
    timeframes: List[str] = ["1h", "4h", "1d"]
    initial_capital: float = 100000.0
    max_positions: int = 5
    max_risk_per_trade: float = 0.02
    stop_loss: float = 0.02
    take_profit: float = 0.04
    risk_reward_ratio: float = 2.0
    model_config: Dict[str, Any] = Field(default_factory=dict)
    strategy_config: Dict[str, Any] = Field(default_factory=dict)
    risk_config: Dict[str, Any] = Field(default_factory=dict)
    execution_config: Dict[str, Any] = Field(default_factory=dict)
    data_config: Dict[str, Any] = Field(default_factory=dict)
    monitoring_config: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('mode')
    def validate_mode(cls, v):
        """Validate bot mode."""
        valid_modes = ['live', 'paper', 'backtest', 'simulation', 'demo']
        if v not in valid_modes:
            raise ValueError(f"Mode must be one of: {valid_modes}")
        return v
    
    @validator('symbols')
    def validate_symbols(cls, v):
        """Validate symbols."""
        if not v:
            raise ValueError("At least one symbol is required")
        return v
    
    @validator('initial_capital')
    def validate_initial_capital(cls, v):
        """Validate initial capital."""
        if v <= 0:
            raise ValueError("Initial capital must be greater than 0")
        return v
    
    @validator('max_positions')
    def validate_max_positions(cls, v):
        """Validate max positions."""
        if v < 1:
            raise ValueError("Max positions must be at least 1")
        return v


class BotStatusResponse(BaseModel):
    """Bot status response model."""
    bot_id: str
    status: str
    mode: str
    started_at: Optional[str] = None
    uptime: float
    components: Dict[str, str]
    metrics: Dict[str, Any]
    health: Dict[str, Any]


class TradeRequest(BaseModel):
    """Trade execution request model."""
    symbol: str
    side: str = Field(..., regex="^(buy|sell)$")
    quantity: float
    price: Optional[float] = None
    order_type: str = "market"
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    @validator('quantity')
    def validate_quantity(cls, v):
        """Validate quantity."""
        if v <= 0:
            raise ValueError("Quantity must be greater than 0")
        return v


class TradeResponse(BaseModel):
    """Trade execution response model."""
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    status: str
    filled_quantity: Optional[float] = None
    filled_price: Optional[float] = None
    timestamp: str
    message: Optional[str] = None


class PositionResponse(BaseModel):
    """Position response model."""
    symbol: str
    side: str
    entry_price: float
    current_price: float
    quantity: float
    pnl: float
    pnl_percent: float
    entry_time: str
    last_update: str
    status: str


class StrategyRequest(BaseModel):
    """Strategy configuration request."""
    name: str
    enabled: bool = True
    parameters: Dict[str, Any] = Field(default_factory=dict)


class PerformanceMetricsResponse(BaseModel):
    """Performance metrics response model."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_volume: float
    max_drawdown: float
    current_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    average_win: float
    average_loss: float
    timestamp: str


class AlertRequest(BaseModel):
    """Alert request model."""
    severity: str = Field(..., regex="^(info|warning|error|critical)$")
    message: str
    component: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


# =============================================================================
# API Class
# =============================================================================

class AIBotAPI:
    """
    REST API interface for AI Trading Bot.
    
    This class provides a FastAPI-based REST API for managing and monitoring
    the AI trading bot. It includes endpoints for bot lifecycle management,
    configuration, trading, and monitoring.
    
    Usage:
        # Create API instance
        api = AIBotAPI(config)
        
        # Run the API server
        api.run(host="0.0.0.0", port=8000)
    """
    
    def __init__(
        self,
        config: Union[Dict[str, Any], str, Path] = None,
        bot: Optional[AIBot] = None,
        auto_start: bool = False
    ):
        """
        Initialize the AI Bot API.
        
        Args:
            config: Bot configuration (dict, file path, or None)
            bot: Existing AIBot instance (if None, creates new)
            auto_start: Whether to auto-start the bot
        """
        self.config = config
        self.bot = bot
        self.auto_start = auto_start
        self.app = FastAPI(
            title="NEXUS AI Trading Bot API",
            version="3.0.0",
            description="REST API for NEXUS AI Trading Bot Management",
            docs_url="/api/docs",
            redoc_url="/api/redoc",
            openapi_url="/api/openapi.json"
        )
        
        # Setup CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Security
        self.security = HTTPBearer()
        
        # WebSocket connections
        self.websocket_connections = []
        
        # Setup routes
        self._setup_routes()
        
        # Initialize bot if needed
        self._initialize_bot()
        
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.info("AI Bot API initialized")
    
    def _initialize_bot(self) -> None:
        """Initialize or get existing bot."""
        if self.bot is None:
            if self.config:
                self.bot = create_ai_bot(self.config, auto_start=self.auto_start)
            else:
                self.bot = create_ai_bot({}, auto_start=self.auto_start)
        
        self.logger.info(f"Bot initialized: {self.bot.bot_id}")
    
    def _setup_routes(self) -> None:
        """Setup all API routes."""
        
        # =====================================================================
        # Health and Status Endpoints
        # =====================================================================
        
        @self.app.get("/api/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "bot_id": self.bot.bot_id if self.bot else None,
                "version": "3.0.0"
            }
        
        @self.app.get("/api/status", response_model=BotStatusResponse)
        async def get_status():
            """Get bot status."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            status = self.bot.get_status()
            return status
        
        @self.app.get("/api/metrics", response_model=PerformanceMetricsResponse)
        async def get_metrics():
            """Get bot performance metrics."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            metrics = self.bot.get_metrics()
            return {
                **metrics,
                "timestamp": datetime.now().isoformat()
            }
        
        @self.app.get("/api/balance")
        async def get_balance():
            """Get account balance."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            return self.bot.get_balance()
        
        # =====================================================================
        # Bot Management Endpoints
        # =====================================================================
        
        @self.app.post("/api/bot/start")
        async def start_bot(background_tasks: BackgroundTasks):
            """Start the bot."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            if self.bot.status == BotStatus.RUNNING:
                return {"status": "already_running", "message": "Bot is already running"}
            
            background_tasks.add_task(self._start_bot_async)
            return {"status": "starting", "message": "Bot start initiated"}
        
        async def _start_bot_async():
            """Async bot start task."""
            try:
                await self.bot.start()
                await self._broadcast_status_update()
            except Exception as e:
                self.logger.error(f"Failed to start bot: {e}")
        
        @self.app.post("/api/bot/stop")
        async def stop_bot(background_tasks: BackgroundTasks):
            """Stop the bot."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            if self.bot.status == BotStatus.STOPPED:
                return {"status": "already_stopped", "message": "Bot is already stopped"}
            
            background_tasks.add_task(self._stop_bot_async)
            return {"status": "stopping", "message": "Bot stop initiated"}
        
        async def _stop_bot_async():
            """Async bot stop task."""
            try:
                await self.bot.stop()
                await self._broadcast_status_update()
            except Exception as e:
                self.logger.error(f"Failed to stop bot: {e}")
        
        @self.app.post("/api/bot/pause")
        async def pause_bot():
            """Pause the bot."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            result = await self.bot.pause()
            if result:
                await self._broadcast_status_update()
                return {"status": "paused", "message": "Bot paused successfully"}
            else:
                raise HTTPException(status_code=400, detail="Failed to pause bot")
        
        @self.app.post("/api/bot/resume")
        async def resume_bot():
            """Resume the bot."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            result = await self.bot.resume()
            if result:
                await self._broadcast_status_update()
                return {"status": "running", "message": "Bot resumed successfully"}
            else:
                raise HTTPException(status_code=400, detail="Failed to resume bot")
        
        @self.app.post("/api/bot/trade")
        async def execute_trade(trade_request: TradeRequest):
            """Execute a trade."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            if self.bot.status != BotStatus.RUNNING:
                raise HTTPException(status_code=400, detail="Bot is not running")
            
            # Convert request to signal
            signal = {
                'symbol': trade_request.symbol,
                'side': trade_request.side,
                'quantity': trade_request.quantity,
                'price': trade_request.price,
                'order_type': trade_request.order_type,
                'stop_loss': trade_request.stop_loss,
                'take_profit': trade_request.take_profit
            }
            
            # Execute trade
            try:
                result = await self.bot._execute_trade(signal)
                if result:
                    return result
                else:
                    raise HTTPException(status_code=400, detail="Trade execution failed")
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        # =====================================================================
        # Position Management Endpoints
        # =====================================================================
        
        @self.app.get("/api/positions", response_model=List[PositionResponse])
        async def get_positions():
            """Get all positions."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            positions = self.bot.get_positions()
            return positions
        
        @self.app.get("/api/positions/{symbol}")
        async def get_position(symbol: str):
            """Get position by symbol."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            positions = self.bot.get_positions()
            for pos in positions:
                if pos.get('symbol') == symbol:
                    return pos
            
            raise HTTPException(status_code=404, detail=f"Position not found for {symbol}")
        
        @self.app.delete("/api/positions/{symbol}")
        async def close_position(symbol: str):
            """Close a position."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            position_manager = self.bot.get_component('position_manager')
            if not position_manager:
                raise HTTPException(status_code=500, detail="Position manager not available")
            
            result = await position_manager.close_position(symbol)
            if result:
                await self._broadcast_position_update(symbol)
                return {"status": "closed", "message": f"Position {symbol} closed"}
            else:
                raise HTTPException(status_code=400, detail=f"Failed to close position {symbol}")
        
        # =====================================================================
        # Configuration Endpoints
        # =====================================================================
        
        @self.app.get("/api/config")
        async def get_config():
            """Get bot configuration."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            return self.bot.config.to_dict()
        
        @self.app.put("/api/config")
        async def update_config(config_request: BotConfigRequest):
            """Update bot configuration."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            config_dict = config_request.dict(exclude_unset=True)
            result = self.bot.update_config(config_dict)
            
            if result:
                return {"status": "updated", "config": self.bot.config.to_dict()}
            else:
                raise HTTPException(status_code=400, detail="Failed to update configuration")
        
        @self.app.post("/api/config/load")
        async def load_config_from_file(file_path: str):
            """Load configuration from file."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            try:
                config = AIBot.load_config_from_file(file_path)
                result = self.bot.update_config(config)
                if result:
                    return {"status": "loaded", "config": self.bot.config.to_dict()}
                else:
                    raise HTTPException(status_code=400, detail="Failed to load configuration")
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail=f"Config file not found: {file_path}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/config/save")
        async def save_config_to_file(file_path: str):
            """Save configuration to file."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            try:
                AIBot.save_config_to_file(self.bot.config.to_dict(), file_path)
                return {"status": "saved", "path": file_path}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        # =====================================================================
        # Strategy Management Endpoints
        # =====================================================================
        
        @self.app.get("/api/strategies")
        async def get_strategies():
            """Get all strategies."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            strategy_engine = self.bot.get_component('strategy_engine')
            if not strategy_engine:
                raise HTTPException(status_code=500, detail="Strategy engine not available")
            
            return strategy_engine.get_strategies()
        
        @self.app.post("/api/strategies")
        async def create_strategy(strategy_request: StrategyRequest):
            """Create a new strategy."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            strategy_engine = self.bot.get_component('strategy_engine')
            if not strategy_engine:
                raise HTTPException(status_code=500, detail="Strategy engine not available")
            
            result = await strategy_engine.create_strategy(
                strategy_request.name,
                strategy_request.parameters
            )
            
            if result:
                return {"status": "created", "strategy": strategy_request.name}
            else:
                raise HTTPException(status_code=400, detail="Failed to create strategy")
        
        @self.app.put("/api/strategies/{strategy_name}")
        async def update_strategy(strategy_name: str, strategy_request: StrategyRequest):
            """Update a strategy."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            strategy_engine = self.bot.get_component('strategy_engine')
            if not strategy_engine:
                raise HTTPException(status_code=500, detail="Strategy engine not available")
            
            result = await strategy_engine.update_strategy(
                strategy_name,
                strategy_request.parameters,
                strategy_request.enabled
            )
            
            if result:
                return {"status": "updated", "strategy": strategy_name}
            else:
                raise HTTPException(status_code=400, detail=f"Failed to update strategy {strategy_name}")
        
        @self.app.delete("/api/strategies/{strategy_name}")
        async def delete_strategy(strategy_name: str):
            """Delete a strategy."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            strategy_engine = self.bot.get_component('strategy_engine')
            if not strategy_engine:
                raise HTTPException(status_code=500, detail="Strategy engine not available")
            
            result = await strategy_engine.delete_strategy(strategy_name)
            if result:
                return {"status": "deleted", "strategy": strategy_name}
            else:
                raise HTTPException(status_code=400, detail=f"Failed to delete strategy {strategy_name}")
        
        # =====================================================================
        # Model Management Endpoints
        # =====================================================================
        
        @self.app.get("/api/models")
        async def get_models():
            """Get all models."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            model_manager = self.bot.get_component('model_manager')
            if not model_manager:
                raise HTTPException(status_code=500, detail="Model manager not available")
            
            return model_manager.get_models()
        
        @self.app.post("/api/models/load")
        async def load_model(model_path: str):
            """Load a model."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            model_manager = self.bot.get_component('model_manager')
            if not model_manager:
                raise HTTPException(status_code=500, detail="Model manager not available")
            
            result = await model_manager.load_model(model_path)
            if result:
                return {"status": "loaded", "path": model_path}
            else:
                raise HTTPException(status_code=400, detail=f"Failed to load model: {model_path}")
        
        @self.app.get("/api/models/predict")
        async def predict(symbol: str, features: Optional[str] = None):
            """Get prediction for a symbol."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            if self.bot.status != BotStatus.RUNNING:
                raise HTTPException(status_code=400, detail="Bot is not running")
            
            # Get market data
            market_data = await self.bot._get_market_data(symbol)
            if market_data is None:
                raise HTTPException(status_code=404, detail=f"No data available for {symbol}")
            
            # Extract features
            features_data = await self.bot._extract_features(market_data)
            if features_data is None:
                raise HTTPException(status_code=500, detail="Failed to extract features")
            
            # Get prediction
            prediction = await self.bot._predict(features_data)
            if prediction is None:
                raise HTTPException(status_code=500, detail="Failed to generate prediction")
            
            return {
                "symbol": symbol,
                "prediction": prediction,
                "timestamp": datetime.now().isoformat()
            }
        
        # =====================================================================
        # Trade History Endpoints
        # =====================================================================
        
        @self.app.get("/api/trades")
        async def get_trade_history(
            limit: int = Query(100, ge=1, le=1000),
            symbol: Optional[str] = None
        ):
            """Get trade history."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            trades = self.bot.get_trade_history(limit)
            
            # Filter by symbol if provided
            if symbol:
                trades = [t for t in trades if t.get('symbol') == symbol]
            
            return trades
        
        @self.app.get("/api/trades/{order_id}")
        async def get_trade(order_id: str):
            """Get trade by ID."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            trades = self.bot.get_trade_history()
            for trade in trades:
                if trade.get('order_id') == order_id:
                    return trade
            
            raise HTTPException(status_code=404, detail=f"Trade not found: {order_id}")
        
        # =====================================================================
        # Alert Management Endpoints
        # =====================================================================
        
        @self.app.post("/api/alerts")
        async def create_alert(alert_request: AlertRequest):
            """Create an alert."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            alert = alert_request.dict()
            await self.bot._send_alert(alert)
            
            return {"status": "sent", "alert": alert}
        
        @self.app.get("/api/alerts")
        async def get_alerts(
            limit: int = Query(50, ge=1, le=500),
            severity: Optional[str] = None
        ):
            """Get recent alerts."""
            if not self.bot:
                raise HTTPException(status_code=404, detail="Bot not initialized")
            
            alerts = self.bot.alerts[-limit:] if self.bot.alerts else []
            
            # Filter by severity if provided
            if severity:
                alerts = [a for a in alerts if a.get('severity') == severity]
            
            return alerts
        
        # =====================================================================
        # WebSocket Endpoints
        # =====================================================================
        
        @self.app.websocket("/api/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await websocket.accept()
            self.websocket_connections.append(websocket)
            
            try:
                # Send initial status
                await websocket.send_json({
                    "type": "status",
                    "data": self.bot.get_status() if self.bot else {"status": "no_bot"}
                })
                
                # Keep connection alive
                while True:
                    # Receive messages (ping/pong)
                    data = await websocket.receive_text()
                    if data == "ping":
                        await websocket.send_text("pong")
                    else:
                        await websocket.send_json({
                            "type": "echo",
                            "data": data
                        })
                        
            except WebSocketDisconnect:
                self.websocket_connections.remove(websocket)
            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")
                if websocket in self.websocket_connections:
                    self.websocket_connections.remove(websocket)
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    async def _broadcast_status_update(self) -> None:
        """Broadcast status update to all WebSocket connections."""
        if not self.websocket_connections:
            return
        
        status = self.bot.get_status() if self.bot else {"status": "no_bot"}
        message = {
            "type": "status_update",
            "data": status,
            "timestamp": datetime.now().isoformat()
        }
        
        for connection in self.websocket_connections[:]:
            try:
                await connection.send_json(message)
            except Exception as e:
                self.logger.error(f"Failed to send WebSocket message: {e}")
                if connection in self.websocket_connections:
                    self.websocket_connections.remove(connection)
    
    async def _broadcast_position_update(self, symbol: str) -> None:
        """Broadcast position update to all WebSocket connections."""
        if not self.websocket_connections:
            return
        
        positions = self.bot.get_positions() if self.bot else []
        message = {
            "type": "position_update",
            "symbol": symbol,
            "data": positions,
            "timestamp": datetime.now().isoformat()
        }
        
        for connection in self.websocket_connections[:]:
            try:
                await connection.send_json(message)
            except Exception as e:
                self.logger.error(f"Failed to send WebSocket message: {e}")
                if connection in self.websocket_connections:
                    self.websocket_connections.remove(connection)
    
    # =========================================================================
    # Run Methods
    # =========================================================================
    
    def run(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        reload: bool = False,
        log_level: str = "info"
    ) -> None:
        """
        Run the API server.
        
        Args:
            host: Host to bind to
            port: Port to bind to
            reload: Enable auto-reload
            log_level: Logging level
        """
        self.logger.info(f"Starting API server on {host}:{port}")
        
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            reload=reload,
            log_level=log_level
        )
    
    def run_async(self) -> None:
        """Run the API server asynchronously."""
        import asyncio
        import uvicorn
        
        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        loop = asyncio.get_event_loop()
        loop.run_until_complete(server.serve())


# =============================================================================
# Factory Function
# =============================================================================

def create_ai_bot_api(
    config: Union[Dict[str, Any], str, Path] = None,
    bot: Optional[AIBot] = None,
    auto_start: bool = False,
    host: str = "0.0.0.0",
    port: int = 8000
) -> AIBotAPI:
    """
    Factory function to create and run AI Bot API.
    
    Args:
        config: Bot configuration
        bot: Existing bot instance
        auto_start: Auto-start bot
        host: Host to bind to
        port: Port to bind to
        
    Returns:
        AIBotAPI instance
    """
    api = AIBotAPI(config, bot, auto_start)
    api.run(host=host, port=port)
    return api


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    'AIBotAPI',
    'BotConfigRequest',
    'BotStatusResponse',
    'TradeRequest',
    'TradeResponse',
    'PositionResponse',
    'StrategyRequest',
    'PerformanceMetricsResponse',
    'AlertRequest',
    'create_ai_bot_api'
]


# =============================================================================
# Module Docstring
# =============================================================================

__doc__ = f"""
{__name__} - NEXUS AI Trading Bot API Interface

This module provides a REST API interface for the NEXUS AI Trading Bot,
allowing external applications and services to manage and monitor the bot.

Copyright: {__copyright__}
CEO: {__author__}
Version: {__version__}

Endpoints:
    - GET /api/health - Health check
    - GET /api/status - Bot status
    - GET /api/metrics - Performance metrics
    - POST /api/bot/start - Start bot
    - POST /api/bot/stop - Stop bot
    - POST /api/bot/pause - Pause bot
    - POST /api/bot/resume - Resume bot
    - POST /api/bot/trade - Execute trade
    - GET /api/positions - Get positions
    - GET /api/config - Get configuration
    - PUT /api/config - Update configuration
    - GET /api/trades - Get trade history
    - WebSocket /api/ws - Real-time updates
"""

# Log module initialization
logger.info(f"AI Bot API module loaded (version {__version__})")
