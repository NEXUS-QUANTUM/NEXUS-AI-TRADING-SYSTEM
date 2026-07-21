"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Dashboard
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
====================================================================
@version 2.0.0
@author NEXUS QUANTUM TEAM
@description Tableau de bord pour le bot d'arbitrage
"""

# ============================================================
# IMPORTS
# ============================================================
import asyncio
import logging
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import threading
import webbrowser

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# ============================================================
# LOGGING
# ============================================================
logger = logging.getLogger(__name__)

# ============================================================
# DASHBOARD
# ============================================================

class ArbitrageBotDashboard:
    """
    Tableau de bord pour le bot d'arbitrage
    
    Interface web pour surveiller et contrôler le bot
    """
    
    def __init__(
        self,
        bot=None,
        config_path: Optional[str] = None,
        host: str = "0.0.0.0",
        port: int = 8500,
        debug: bool = False,
        static_dir: Optional[str] = None,
        template_dir: Optional[str] = None
    ):
        """
        Initialise le tableau de bord
        
        Args:
            bot: Instance du bot
            config_path: Chemin de la configuration
            host: Hôte
            port: Port
            debug: Mode debug
            static_dir: Répertoire des fichiers statiques
            template_dir: Répertoire des templates
        """
        self.bot = bot
        self.config_path = config_path or "config/arbitrage_config.yaml"
        self.host = host
        self.port = port
        self.debug = debug
        
        # Répertoires
        self.static_dir = Path(static_dir) if static_dir else Path(__file__).parent / "static"
        self.template_dir = Path(template_dir) if template_dir else Path(__file__).parent / "templates"
        
        # FastAPI app
        self.app = FastAPI(
            title="NEXUS Arbitrage Bot Dashboard",
            description="Tableau de bord pour le bot d'arbitrage",
            version="2.0.0",
            debug=debug
        )
        
        # Templates
        self.templates = Jinja2Templates(directory=str(self.template_dir))
        
        # WebSocket connections
        self.websocket_connections: List[WebSocket] = []
        
        # Setup
        self._setup_routes()
        self._setup_websocket()
        self._setup_static()
        
        # Data stream
        self._streaming = False
        self._stream_task = None
        
        logger.info(f"Dashboard initialized on {host}:{port}")
    
    def _setup_static(self):
        """Configure les fichiers statiques"""
        if self.static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(self.static_dir)), name="static")
            logger.info(f"Static files served from {self.static_dir}")
    
    def _setup_routes(self):
        """Configure les routes"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request):
            """Page principale du tableau de bord"""
            return self.templates.TemplateResponse(
                "dashboard.html",
                {
                    "request": request,
                    "title": "NEXUS Arbitrage Bot Dashboard",
                    "version": "2.0.0",
                    "env": self.bot.env if self.bot else "unknown",
                }
            )
        
        @self.app.get("/api/status")
        async def get_status():
            """Récupère le statut du bot"""
            if not self.bot:
                return JSONResponse(
                    status_code=503,
                    content={"status": "error", "message": "Bot not initialized"}
                )
            
            return self.bot.get_status()
        
        @self.app.get("/api/metrics")
        async def get_metrics():
            """Récupère les métriques"""
            if not self.bot:
                return JSONResponse(
                    status_code=503,
                    content={"status": "error", "message": "Bot not initialized"}
                )
            
            return self.bot.get_metrics()
        
        @self.app.get("/api/health")
        async def get_health():
            """Récupère le health check"""
            if not self.bot:
                return JSONResponse(
                    status_code=503,
                    content={"status": "error", "message": "Bot not initialized"}
                )
            
            return self.bot.get_health()
        
        @self.app.get("/api/trades")
        async def get_trades(limit: int = 100, offset: int = 0):
            """Récupère les trades"""
            if not self.bot:
                return JSONResponse(
                    status_code=503,
                    content={"status": "error", "message": "Bot not initialized"}
                )
            
            data_manager = self.bot.get_component('data_manager')
            if not data_manager:
                return []
            
            trades = data_manager.get('trades', [])
            return trades[offset:offset + limit]
        
        @self.app.get("/api/positions")
        async def get_positions():
            """Récupère les positions"""
            if not self.bot:
                return JSONResponse(
                    status_code=503,
                    content={"status": "error", "message": "Bot not initialized"}
                )
            
            risk_manager = self.bot.get_component('risk_manager')
            if not risk_manager:
                return []
            
            return risk_manager.get_positions()
        
        @self.app.get("/api/opportunities")
        async def get_opportunities(limit: int = 50):
            """Récupère les opportunités"""
            if not self.bot:
                return JSONResponse(
                    status_code=503,
                    content={"status": "error", "message": "Bot not initialized"}
                )
            
            data_manager = self.bot.get_component('data_manager')
            if not data_manager:
                return []
            
            opportunities = data_manager.get('opportunities', [])
            return opportunities[-limit:]
        
        @self.app.get("/api/exchanges")
        async def get_exchanges():
            """Récupère les exchanges"""
            if not self.bot:
                return JSONResponse(
                    status_code=503,
                    content={"status": "error", "message": "Bot not initialized"}
                )
            
            exchange_manager = self.bot.get_component('exchange_manager')
            if not exchange_manager:
                return []
            
            return exchange_manager.get_exchanges()
        
        @self.app.get("/api/strategies")
        async def get_strategies():
            """Récupère les stratégies"""
            if not self.bot:
                return JSONResponse(
                    status_code=503,
                    content={"status": "error", "message": "Bot not initialized"}
                )
            
            strategy_manager = self.bot.get_component('strategy_manager')
            if not strategy_manager:
                return []
            
            return strategy_manager.get_strategies()
        
        @self.app.post("/api/bot/start")
        async def start_bot():
            """Démarre le bot"""
            if not self.bot:
                return JSONResponse(
                    status_code=503,
                    content={"status": "error", "message": "Bot not initialized"}
                )
            
            if self.bot.is_running():
                return {"status": "already_running"}
            
            self.bot.start()
            return {"status": "started"}
        
        @self.app.post("/api/bot/stop")
        async def stop_bot():
            """Arrête le bot"""
            if not self.bot:
                return JSONResponse(
                    status_code=503,
                    content={"status": "error", "message": "Bot not initialized"}
                )
            
            if not self.bot.is_running():
                return {"status": "already_stopped"}
            
            self.bot.stop()
            return {"status": "stopped"}
        
        @self.app.post("/api/bot/restart")
        async def restart_bot():
            """Redémarre le bot"""
            if not self.bot:
                return JSONResponse(
                    status_code=503,
                    content={"status": "error", "message": "Bot not initialized"}
                )
            
            self.bot.restart()
            return {"status": "restarted"}
    
    def _setup_websocket(self):
        """Configure les WebSockets"""
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint"""
            await websocket.accept()
            self.websocket_connections.append(websocket)
            
            client_id = id(websocket)
            logger.info(f"WebSocket client connected: {client_id}")
            
            try:
                # Envoyer les données initiales
                await self._send_initial_data(websocket)
                
                # Démarrer le streaming si nécessaire
                if not self._streaming:
                    self._start_streaming()
                
                while True:
                    # Recevoir les messages
                    data = await websocket.receive_text()
                    await self._handle_websocket_message(websocket, data)
            
            except WebSocketDisconnect:
                self.websocket_connections.remove(websocket)
                logger.info(f"WebSocket client disconnected: {client_id}")
                
                # Arrêter le streaming si plus de clients
                if not self.websocket_connections:
                    self._stop_streaming()
            
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                if websocket in self.websocket_connections:
                    self.websocket_connections.remove(websocket)
    
    async def _send_initial_data(self, websocket: WebSocket):
        """Envoie les données initiales"""
        if not self.bot:
            return
        
        data = {
            'type': 'initial',
            'data': {
                'status': self.bot.get_status(),
                'metrics': self.bot.get_metrics(),
                'health': self.bot.get_health(),
            }
        }
        
        try:
            await websocket.send_text(json.dumps(data, default=str))
        except Exception as e:
            logger.error(f"Failed to send initial data: {e}")
    
    async def _handle_websocket_message(self, websocket: WebSocket, data: str):
        """Gère les messages WebSocket"""
        try:
            message = json.loads(data)
            message_type = message.get('type', 'unknown')
            
            if message_type == 'ping':
                await websocket.send_text(json.dumps({
                    'type': 'pong',
                    'timestamp': datetime.now().isoformat()
                }))
            
            elif message_type == 'subscribe':
                channel = message.get('channel', 'all')
                await websocket.send_text(json.dumps({
                    'type': 'subscribed',
                    'channel': channel,
                    'timestamp': datetime.now().isoformat()
                }))
            
            elif message_type == 'get_status':
                await websocket.send_text(json.dumps({
                    'type': 'status',
                    'data': self.bot.get_status() if self.bot else {},
                    'timestamp': datetime.now().isoformat()
                }))
            
            elif message_type == 'get_metrics':
                await websocket.send_text(json.dumps({
                    'type': 'metrics',
                    'data': self.bot.get_metrics() if self.bot else {},
                    'timestamp': datetime.now().isoformat()
                }))
        
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON: {data}")
        except Exception as e:
            logger.error(f"WebSocket message error: {e}")
    
    def _start_streaming(self):
        """Démarre le streaming de données"""
        if self._streaming:
            return
        
        self._streaming = True
        self._stream_task = asyncio.create_task(self._stream_data())
        logger.info("Data streaming started")
    
    def _stop_streaming(self):
        """Arrête le streaming de données"""
        self._streaming = False
        
        if self._stream_task:
            self._stream_task.cancel()
            self._stream_task = None
        
        logger.info("Data streaming stopped")
    
    async def _stream_data(self):
        """Streaming des données en temps réel"""
        while self._streaming:
            try:
                if not self.bot or not self.websocket_connections:
                    await asyncio.sleep(1)
                    continue
                
                # Collecter les données
                data = {
                    'type': 'update',
                    'data': {
                        'status': self.bot.get_status(),
                        'metrics': self.bot.get_metrics(),
                        'health': self.bot.get_health(),
                        'timestamp': datetime.now().isoformat()
                    }
                }
                
                # Envoyer à tous les clients
                for websocket in self.websocket_connections[:]:
                    try:
                        await websocket.send_text(json.dumps(data, default=str))
                    except Exception as e:
                        logger.error(f"Failed to send data to client: {e}")
                        if websocket in self.websocket_connections:
                            self.websocket_connections.remove(websocket)
                
                await asyncio.sleep(1)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stream error: {e}")
                await asyncio.sleep(5)
    
    # ============================================================
    # SERVER CONTROL
    # ============================================================
    
    def run(self, open_browser: bool = True):
        """
        Démarre le serveur
        
        Args:
            open_browser: Ouvrir le navigateur
        """
        if open_browser:
            url = f"http://{self.host if self.host != '0.0.0.0' else 'localhost'}:{self.port}"
            webbrowser.open(url)
        
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="debug" if self.debug else "info"
        )
    
    def stop(self):
        """Arrête le serveur"""
        self._stop_streaming()
        
        for ws in self.websocket_connections[:]:
            try:
                asyncio.create_task(ws.close())
            except:
                pass
        
        self.websocket_connections.clear()
        logger.info("Dashboard stopped")

# ============================================================
# DASHBOARD CLIENT
# ============================================================

class DashboardClient:
    """
    Client pour le tableau de bord
    
    Permet de se connecter au tableau de bord via WebSocket
    """
    
    def __init__(self, url: str = "ws://localhost:8500/ws"):
        """
        Initialise le client
        
        Args:
            url: URL WebSocket
        """
        self.url = url
        self.websocket = None
        self.connected = False
        self.callbacks = []
    
    async def connect(self):
        """Connecte le client"""
        import websockets
        
        try:
            self.websocket = await websockets.connect(self.url)
            self.connected = True
            logger.info(f"Connected to dashboard: {self.url}")
            
            # Démarrer l'écoute
            asyncio.create_task(self._listen())
            
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
    
    async def disconnect(self):
        """Déconnecte le client"""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            logger.info("Disconnected from dashboard")
    
    async def _listen(self):
        """Écoute les messages"""
        while self.connected:
            try:
                message = await self.websocket.recv()
                data = json.loads(message)
                
                for callback in self.callbacks:
                    try:
                        await callback(data)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
            
            except Exception as e:
                logger.error(f"Listen error: {e}")
                self.connected = False
                break
    
    async def send(self, data: Dict[str, Any]):
        """
        Envoie un message
        
        Args:
            data: Données à envoyer
        """
        if not self.connected:
            raise Exception("Not connected")
        
        await self.websocket.send(json.dumps(data))
    
    def on_message(self, callback):
        """
        Enregistre un callback pour les messages
        
        Args:
            callback: Fonction de callback
        """
        self.callbacks.append(callback)
    
    async def ping(self):
        """Envoie un ping"""
        await self.send({'type': 'ping'})
    
    async def get_status(self):
        """Demande le statut"""
        await self.send({'type': 'get_status'})
    
    async def get_metrics(self):
        """Demande les métriques"""
        await self.send({'type': 'get_metrics'})

# ============================================================
# MAIN
# ============================================================

def main():
    """Point d'entrée principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="NEXUS Arbitrage Bot Dashboard")
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
        default=8500
    )
    parser.add_argument(
        "-d", "--debug",
        help="Enable debug mode",
        action="store_true"
    )
    parser.add_argument(
        "--no-browser",
        help="Don't open browser",
        action="store_true"
    )
    
    args = parser.parse_args()
    
    # Créer le bot
    from .arbitrage_bot import ArbitrageBot
    bot = ArbitrageBot(
        config_path=args.config,
        debug=args.debug
    )
    
    # Démarrer le bot
    bot.start()
    
    # Créer et démarrer le tableau de bord
    dashboard = ArbitrageBotDashboard(
        bot=bot,
        config_path=args.config,
        host=args.host,
        port=args.port,
        debug=args.debug
    )
    
    dashboard.run(open_browser=not args.no_browser)

# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'ArbitrageBotDashboard',
    'DashboardClient',
    'main',
]

# ============================================================
# INITIALIZATION
# ============================================================

if __name__ == "__main__":
    main()
