"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot API
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description API REST pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import json
import time
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path
import uuid

from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from pydantic import BaseModel, Field, validator
import uvicorn

# Imports internes
from .arbitrage_bot import ArbitrageBot
from .arbitrage_bot_analyzer import ArbitrageBotAnalyzer
from .core.arbitrage_engine import ArbitrageEngine
from .core.exchange_manager import ExchangeManager
from .core.strategy_manager import StrategyManager
from .core.risk_manager import RiskManager
from .core.execution_engine import ExecutionEngine
from .core.market_data import MarketData
from .core.notification_manager import NotificationManager
from .core.data_manager import DataManager
from .core.metrics_collector import MetricsCollector
from .core.health_check import HealthCheck
from .core.scheduler import Scheduler
from .config import ConfigLoader

from .utils import (
    NumberFormatter,
    DateTimeFormatter,
    JSONFormatter,
    get_lock_manager,
    get_cache_manager,
    get_queue_manager,
)

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# PYDANTIC MODELS
# ============================================================

class HealthResponse(BaseModel):
    """Réponse de health check"""
    status: str
    version: str
    timestamp: str
    uptime: float
    components: Dict[str, str]
    checks: Dict[str, Any]

class MetricsResponse(BaseModel):
    """Réponse de métriques"""
    timestamp: str
    metrics: Dict[str, Any]
    summary: Dict[str, Any]

class TradeRequest(BaseModel):
    """Requête de trade"""
    symbol: str
    side: str
    quantity: float
    order_type: str = "MARKET"
    price: Optional[float] = None
    stop_price: Optional[float] = None
    strategy: Optional[str] = None

class TradeResponse(BaseModel):
    """Réponse de trade"""
    id: str
    symbol: str
    side: str
    quantity: float
    price: float
    status: str
    timestamp: str

class StrategyRequest(BaseModel):
    """Requête de stratégie"""
    name: str
    type: str
    enabled: bool
    parameters: Dict[str, Any]

class ConfigUpdateRequest(BaseModel):
    """Requête de mise à jour de configuration"""
    section: str
    key: str
    value: Any

class NotificationRequest(BaseModel):
    """Requête de notification"""
    type: str
    severity: str
    title: str
    message: str
    channel: Optional[str] = None

# ============================================================
# API SERVER
# ============================================================

class ArbitrageBotAPI:
    """
    Serveur API pour le bot d'arbitrage
    """
    
    def __init__(
        self,
        bot: Optional[ArbitrageBot] = None,
        config_path: Optional[str] = None,
        host: str = "0.0.0.0",
        port: int = 8000,
        debug: bool = False
    ):
        """
        Initialise l'API
        
        Args:
            bot: Instance du bot
            config_path: Chemin de la configuration
            host: Hôte
            port: Port
            debug: Mode debug
        """
        self.bot = bot
        self.config_path = config_path or "config/arbitrage_config.yaml"
        self.host = host
        self.port = port
        self.debug = debug
        
        # Analyzer
        self.analyzer = None
        
        # FastAPI app
        self.app = FastAPI(
            title="NEXUS Arbitrage Bot API",
            description="API pour le bot d'arbitrage NEXUS",
            version="2.0.0",
            debug=debug
        )
        
        # Security
        self.security = HTTPBearer()
        
        # Setup
        self._setup_middleware()
        self._setup_routes()
        self._setup_websocket()
        self._setup_exception_handlers()
        
        logger.info(f"API initialized on {host}:{port}")
    
    def _setup_middleware(self):
        """Configure les middlewares"""
        # CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _setup_routes(self):
        """Configure les routes"""
        
        # ============================================================
        # ROUTES DE BASE
        # ============================================================
        
        @self.app.get("/", response_model=Dict[str, str])
        async def root():
            """Route racine"""
            return {
                "name": "NEXUS Arbitrage Bot API",
                "version": "2.0.0",
                "status": "running",
                "docs": "/docs"
            }
        
        @self.app.get("/health", response_model=HealthResponse)
        async def health_check():
            """Health check"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            health = self.bot.get_health()
            status = self.bot.get_status()
            
            return HealthResponse(
                status="healthy" if self.bot.is_running() else "unhealthy",
                version="2.0.0",
                timestamp=datetime.now().isoformat(),
                uptime=status.get('uptime', 0),
                components=status.get('components', {}),
                checks=health.get('checks', {})
            )
        
        # ============================================================
        # BOT ROUTES
        # ============================================================
        
        @self.app.post("/bot/start")
        async def start_bot():
            """Démarre le bot"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            if self.bot.is_running():
                return {"status": "already_running"}
            
            self.bot.start()
            return {"status": "started"}
        
        @self.app.post("/bot/stop")
        async def stop_bot():
            """Arrête le bot"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            if not self.bot.is_running():
                return {"status": "already_stopped"}
            
            self.bot.stop()
            return {"status": "stopped"}
        
        @self.app.post("/bot/restart")
        async def restart_bot():
            """Redémarre le bot"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            self.bot.restart()
            return {"status": "restarted"}
        
        @self.app.get("/bot/status")
        async def get_bot_status():
            """Récupère le statut du bot"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            return self.bot.get_status()
        
        @self.app.get("/bot/config")
        async def get_bot_config():
            """Récupère la configuration du bot"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            return self.bot.get_config()
        
        # ============================================================
        # METRICS ROUTES
        # ============================================================
        
        @self.app.get("/metrics", response_model=MetricsResponse)
        async def get_metrics():
            """Récupère les métriques"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            metrics = self.bot.get_metrics()
            
            return MetricsResponse(
                timestamp=datetime.now().isoformat(),
                metrics=metrics,
                summary=metrics.get('summary', {})
            )
        
        @self.app.get("/metrics/{metric_name}")
        async def get_metric(metric_name: str):
            """Récupère une métrique spécifique"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            metrics = self.bot.get_metrics()
            if metric_name not in metrics:
                raise HTTPException(status_code=404, detail=f"Metric '{metric_name}' not found")
            
            return {metric_name: metrics[metric_name]}
        
        # ============================================================
        # TRADING ROUTES
        # ============================================================
        
        @self.app.post("/trades", response_model=TradeResponse)
        async def create_trade(trade_request: TradeRequest):
            """Crée un trade"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            # Récupérer l'execution engine
            execution_engine = self.bot.get_component('execution_engine')
            if not execution_engine:
                raise HTTPException(status_code=503, detail="Execution engine not available")
            
            try:
                order = execution_engine.execute_order({
                    'symbol': trade_request.symbol,
                    'side': trade_request.side,
                    'type': trade_request.order_type,
                    'quantity': trade_request.quantity,
                    'price': trade_request.price,
                    'stop_price': trade_request.stop_price,
                    'strategy': trade_request.strategy,
                })
                
                return TradeResponse(
                    id=order.get('id', str(uuid.uuid4())),
                    symbol=trade_request.symbol,
                    side=trade_request.side,
                    quantity=trade_request.quantity,
                    price=order.get('price', 0),
                    status=order.get('status', 'NEW'),
                    timestamp=datetime.now().isoformat()
                )
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.get("/trades")
        async def get_trades(
            limit: int = 100,
            offset: int = 0,
            symbol: Optional[str] = None,
            status: Optional[str] = None
        ):
            """Récupère les trades"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            # Récupérer les trades
            data_manager = self.bot.get_component('data_manager')
            if not data_manager:
                return []
            
            trades = data_manager.get('trades', [])
            
            # Filtrer
            if symbol:
                trades = [t for t in trades if t.get('symbol') == symbol]
            if status:
                trades = [t for t in trades if t.get('status') == status]
            
            # Paginer
            trades = trades[offset:offset + limit]
            
            return trades
        
        @self.app.get("/trades/{trade_id}")
        async def get_trade(trade_id: str):
            """Récupère un trade spécifique"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            data_manager = self.bot.get_component('data_manager')
            if not data_manager:
                raise HTTPException(status_code=404, detail="Trade not found")
            
            trades = data_manager.get('trades', [])
            trade = next((t for t in trades if t.get('id') == trade_id), None)
            
            if not trade:
                raise HTTPException(status_code=404, detail="Trade not found")
            
            return trade
        
        # ============================================================
        # STRATEGY ROUTES
        # ============================================================
        
        @self.app.get("/strategies")
        async def get_strategies():
            """Récupère les stratégies"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            strategy_manager = self.bot.get_component('strategy_manager')
            if not strategy_manager:
                return []
            
            return strategy_manager.get_strategies()
        
        @self.app.get("/strategies/{strategy_id}")
        async def get_strategy(strategy_id: str):
            """Récupère une stratégie spécifique"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            strategy_manager = self.bot.get_component('strategy_manager')
            if not strategy_manager:
                raise HTTPException(status_code=404, detail="Strategy not found")
            
            strategy = strategy_manager.get_strategy(strategy_id)
            if not strategy:
                raise HTTPException(status_code=404, detail="Strategy not found")
            
            return strategy
        
        @self.app.post("/strategies")
        async def create_strategy(strategy_request: StrategyRequest):
            """Crée une stratégie"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            strategy_manager = self.bot.get_component('strategy_manager')
            if not strategy_manager:
                raise HTTPException(status_code=503, detail="Strategy manager not available")
            
            try:
                strategy = strategy_manager.create_strategy({
                    'name': strategy_request.name,
                    'type': strategy_request.type,
                    'enabled': strategy_request.enabled,
                    'parameters': strategy_request.parameters,
                })
                return strategy
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.put("/strategies/{strategy_id}")
        async def update_strategy(strategy_id: str, strategy_request: StrategyRequest):
            """Met à jour une stratégie"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            strategy_manager = self.bot.get_component('strategy_manager')
            if not strategy_manager:
                raise HTTPException(status_code=503, detail="Strategy manager not available")
            
            try:
                strategy = strategy_manager.update_strategy(strategy_id, {
                    'name': strategy_request.name,
                    'type': strategy_request.type,
                    'enabled': strategy_request.enabled,
                    'parameters': strategy_request.parameters,
                })
                return strategy
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.delete("/strategies/{strategy_id}")
        async def delete_strategy(strategy_id: str):
            """Supprime une stratégie"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            strategy_manager = self.bot.get_component('strategy_manager')
            if not strategy_manager:
                raise HTTPException(status_code=503, detail="Strategy manager not available")
            
            try:
                strategy_manager.delete_strategy(strategy_id)
                return {"status": "deleted"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        # ============================================================
        # EXCHANGE ROUTES
        # ============================================================
        
        @self.app.get("/exchanges")
        async def get_exchanges():
            """Récupère les exchanges"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            exchange_manager = self.bot.get_component('exchange_manager')
            if not exchange_manager:
                return []
            
            return exchange_manager.get_exchanges()
        
        @self.app.get("/exchanges/{exchange_id}")
        async def get_exchange(exchange_id: str):
            """Récupère un exchange spécifique"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            exchange_manager = self.bot.get_component('exchange_manager')
            if not exchange_manager:
                raise HTTPException(status_code=404, detail="Exchange not found")
            
            exchange = exchange_manager.get_exchange(exchange_id)
            if not exchange:
                raise HTTPException(status_code=404, detail="Exchange not found")
            
            return exchange
        
        @self.app.post("/exchanges/{exchange_id}/connect")
        async def connect_exchange(exchange_id: str):
            """Connecte un exchange"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            exchange_manager = self.bot.get_component('exchange_manager')
            if not exchange_manager:
                raise HTTPException(status_code=503, detail="Exchange manager not available")
            
            try:
                exchange_manager.connect_exchange(exchange_id)
                return {"status": "connected"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.post("/exchanges/{exchange_id}/disconnect")
        async def disconnect_exchange(exchange_id: str):
            """Déconnecte un exchange"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            exchange_manager = self.bot.get_component('exchange_manager')
            if not exchange_manager:
                raise HTTPException(status_code=503, detail="Exchange manager not available")
            
            try:
                exchange_manager.disconnect_exchange(exchange_id)
                return {"status": "disconnected"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        # ============================================================
        # RISK ROUTES
        # ============================================================
        
        @self.app.get("/risk")
        async def get_risk_metrics():
            """Récupère les métriques de risque"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            risk_manager = self.bot.get_component('risk_manager')
            if not risk_manager:
                return {}
            
            return risk_manager.get_metrics()
        
        @self.app.get("/risk/positions")
        async def get_positions():
            """Récupère les positions"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            risk_manager = self.bot.get_component('risk_manager')
            if not risk_manager:
                return []
            
            return risk_manager.get_positions()
        
        @self.app.get("/risk/drawdown")
        async def get_drawdown():
            """Récupère les métriques de drawdown"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            risk_manager = self.bot.get_component('risk_manager')
            if not risk_manager:
                return {}
            
            return risk_manager.get_drawdown_metrics()
        
        # ============================================================
        # NOTIFICATION ROUTES
        # ============================================================
        
        @self.app.post("/notifications")
        async def send_notification(notification: NotificationRequest):
            """Envoie une notification"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            notification_manager = self.bot.get_component('notification_manager')
            if not notification_manager:
                raise HTTPException(status_code=503, detail="Notification manager not available")
            
            try:
                notification_manager.send_notification({
                    'type': notification.type,
                    'severity': notification.severity,
                    'title': notification.title,
                    'message': notification.message,
                    'channel': notification.channel,
                    'timestamp': datetime.now().isoformat()
                })
                return {"status": "sent"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @self.app.get("/notifications")
        async def get_notifications(
            limit: int = 50,
            offset: int = 0,
            severity: Optional[str] = None
        ):
            """Récupère les notifications"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            notification_manager = self.bot.get_component('notification_manager')
            if not notification_manager:
                return []
            
            notifications = notification_manager.get_notifications()
            
            # Filtrer
            if severity:
                notifications = [n for n in notifications if n.get('severity') == severity]
            
            # Paginer
            notifications = notifications[offset:offset + limit]
            
            return notifications
        
        # ============================================================
        # CONFIGURATION ROUTES
        # ============================================================
        
        @self.app.get("/config")
        async def get_config():
            """Récupère la configuration complète"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            return self.bot.get_config()
        
        @self.app.put("/config")
        async def update_config(config_update: ConfigUpdateRequest):
            """Met à jour la configuration"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            try:
                self.bot.update_config(config_update.section, config_update.key, config_update.value)
                return {"status": "updated"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        # ============================================================
        # ANALYTICS ROUTES
        # ============================================================
        
        @self.app.get("/analytics/performance")
        async def get_performance(
            period: str = "day",
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
        ):
            """Récupère les performances"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            # Initialiser l'analyzer si nécessaire
            if not self.analyzer:
                self.analyzer = ArbitrageBotAnalyzer()
                self.analyzer.load_data(
                    start_date=start_date,
                    end_date=end_date
                )
                self.analyzer.analyze_performance()
            
            return self.analyzer.performance
        
        @self.app.get("/analytics/opportunities")
        async def get_opportunity_analytics(
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
        ):
            """Récupère les analyses d'opportunités"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            # Initialiser l'analyzer si nécessaire
            if not self.analyzer:
                self.analyzer = ArbitrageBotAnalyzer()
                self.analyzer.load_data(
                    start_date=start_date,
                    end_date=end_date
                )
                self.analyzer.analyze_opportunities()
            
            return self.analyzer.performance.get('opportunity_analysis', {})
        
        @self.app.get("/analytics/report")
        async def generate_report(
            format: str = "json",
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
        ):
            """Génère un rapport d'analyse"""
            if not self.bot:
                raise HTTPException(status_code=503, detail="Bot not initialized")
            
            # Initialiser l'analyzer si nécessaire
            if not self.analyzer:
                self.analyzer = ArbitrageBotAnalyzer()
                self.analyzer.load_data(
                    start_date=start_date,
                    end_date=end_date
                )
                self.analyzer.analyze_performance()
                self.analyzer.analyze_opportunities()
            
            # Générer le rapport
            report_path = self.analyzer.generate_report(format)
            
            return FileResponse(
                report_path,
                media_type="application/octet-stream",
                filename=report_path.name
            )
    
    def _setup_websocket(self):
        """Configure les WebSockets"""
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint"""
            await websocket.accept()
            
            client_id = str(uuid.uuid4())[:8]
            logger.info(f"WebSocket client connected: {client_id}")
            
            try:
                while True:
                    # Recevoir les messages
                    data = await websocket.receive_text()
                    
                    try:
                        message = json.loads(data)
                        message_type = message.get('type', 'unknown')
                        
                        # Traiter le message
                        if message_type == 'subscribe':
                            channel = message.get('channel', 'all')
                            await self._handle_websocket_subscribe(websocket, client_id, channel)
                        elif message_type == 'unsubscribe':
                            channel = message.get('channel', 'all')
                            await self._handle_websocket_unsubscribe(websocket, client_id, channel)
                        elif message_type == 'ping':
                            await websocket.send_text(json.dumps({
                                'type': 'pong',
                                'timestamp': datetime.now().isoformat()
                            }))
                        else:
                            await websocket.send_text(json.dumps({
                                'type': 'error',
                                'message': f'Unknown message type: {message_type}'
                            }))
                    
                    except json.JSONDecodeError:
                        await websocket.send_text(json.dumps({
                            'type': 'error',
                            'message': 'Invalid JSON'
                        }))
            
            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected: {client_id}")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                try:
                    await websocket.close()
                except:
                    pass
    
    async def _handle_websocket_subscribe(self, websocket: WebSocket, client_id: str, channel: str):
        """Gère l'abonnement WebSocket"""
        # Envoyer les données initiales
        if channel in ['all', 'metrics']:
            await websocket.send_text(json.dumps({
                'type': 'metrics',
                'data': self.bot.get_metrics() if self.bot else {},
                'timestamp': datetime.now().isoformat()
            }))
        
        if channel in ['all', 'status']:
            await websocket.send_text(json.dumps({
                'type': 'status',
                'data': self.bot.get_status() if self.bot else {},
                'timestamp': datetime.now().isoformat()
            }))
        
        # Démarrer le streaming
        asyncio.create_task(self._websocket_stream(websocket, client_id, channel))
    
    async def _handle_websocket_unsubscribe(self, websocket: WebSocket, client_id: str, channel: str):
        """Gère le désabonnement WebSocket"""
        # Arrêter le streaming
        pass
    
    async def _websocket_stream(self, websocket: WebSocket, client_id: str, channel: str):
        """Streaming WebSocket"""
        try:
            while True:
                # Envoyer des mises à jour
                if channel in ['all', 'metrics']:
                    await websocket.send_text(json.dumps({
                        'type': 'metrics_update',
                        'data': self.bot.get_metrics() if self.bot else {},
                        'timestamp': datetime.now().isoformat()
                    }))
                
                if channel in ['all', 'status']:
                    await websocket.send_text(json.dumps({
                        'type': 'status_update',
                        'data': self.bot.get_status() if self.bot else {},
                        'timestamp': datetime.now().isoformat()
                    }))
                
                await asyncio.sleep(1)
        
        except Exception as e:
            logger.warning(f"WebSocket stream error: {e}")
    
    def _setup_exception_handlers(self):
        """Configure les gestionnaires d'exceptions"""
        
        @self.app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": exc.detail,
                    "status_code": exc.status_code,
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        @self.app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            logger.error(f"Unhandled exception: {exc}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "timestamp": datetime.now().isoformat()
                }
            )
    
    def run(self):
        """Démarre le serveur API"""
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="debug" if self.debug else "info"
        )

# ============================================================
# API CLIENT
# ============================================================

class ArbitrageBotAPIClient:
    """
    Client API pour le bot d'arbitrage
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None
    ):
        """
        Initialise le client
        
        Args:
            base_url: URL de base
            api_key: Clé API
        """
        self.base_url = base_url
        self.api_key = api_key
        self.session = None
    
    async def __aenter__(self):
        """Context manager entry"""
        import aiohttp
        headers = {}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        self.session = aiohttp.ClientSession(headers=headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _request(self, method: str, path: str, **kwargs) -> Any:
        """Effectue une requête"""
        url = f"{self.base_url}{path}"
        
        async with self.session.request(method, url, **kwargs) as response:
            if response.status >= 400:
                error = await response.json()
                raise Exception(error.get('error', 'Unknown error'))
            
            return await response.json()
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check"""
        return await self._request('GET', '/health')
    
    async def start_bot(self) -> Dict[str, Any]:
        """Démarre le bot"""
        return await self._request('POST', '/bot/start')
    
    async def stop_bot(self) -> Dict[str, Any]:
        """Arrête le bot"""
        return await self._request('POST', '/bot/stop')
    
    async def get_status(self) -> Dict[str, Any]:
        """Récupère le statut"""
        return await self._request('GET', '/bot/status')
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Récupère les métriques"""
        return await self._request('GET', '/metrics')
    
    async def create_trade(self, trade: Dict[str, Any]) -> Dict[str, Any]:
        """Crée un trade"""
        return await self._request('POST', '/trades', json=trade)
    
    async def get_trades(self, **params) -> List[Dict[str, Any]]:
        """Récupère les trades"""
        return await self._request('GET', '/trades', params=params)
    
    async def get_strategies(self) -> List[Dict[str, Any]]:
        """Récupère les stratégies"""
        return await self._request('GET', '/strategies')
    
    async def create_strategy(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Crée une stratégie"""
        return await self._request('POST', '/strategies', json=strategy)
    
    async def get_exchanges(self) -> List[Dict[str, Any]]:
        """Récupère les exchanges"""
        return await self._request('GET', '/exchanges')
    
    async def get_risk_metrics(self) -> Dict[str, Any]:
        """Récupère les métriques de risque"""
        return await self._request('GET', '/risk')
    
    async def send_notification(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """Envoie une notification"""
        return await self._request('POST', '/notifications', json=notification)

# ============================================================
# MAIN
# ============================================================

def main():
    """Point d'entrée principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="NEXUS Arbitrage Bot API")
    parser.add_argument(
        "-c", "--config",
        help="Path to configuration file",
        default="config/arbitrage_config.yaml"
    )
    parser.add_argument(
        "-H", "--host",
        help="Host to bind",
        default="0.0.0.0"
    )
    parser.add_argument(
        "-p", "--port",
        help="Port to bind",
        type=int,
        default=8000
    )
    parser.add_argument(
        "-d", "--debug",
        help="Enable debug mode",
        action="store_true"
    )
    
    args = parser.parse_args()
    
    # Créer le bot
    bot = ArbitrageBot(
        config_path=args.config,
        debug=args.debug
    )
    
    # Démarrer le bot
    bot.start()
    
    # Créer et démarrer l'API
    api = ArbitrageBotAPI(
        bot=bot,
        config_path=args.config,
        host=args.host,
        port=args.port,
        debug=args.debug
    )
    
    api.run()

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'ArbitrageBotAPI',
    'ArbitrageBotAPIClient',
    'main',
]

# ============================================================
# INITIALIZATION
# ============================================================

if __name__ == "__main__":
    main()
