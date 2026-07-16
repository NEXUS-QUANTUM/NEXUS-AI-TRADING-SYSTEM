"""
NEXUS AI TRADING SYSTEM - Real-time Monitor
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Advanced real-time monitoring with live performance tracking,
alerting, anomaly detection, and dashboard capabilities.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
from enum import Enum
import numpy as np
import pandas as pd
from collections import deque
import logging
from pathlib import Path
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import websockets
from websockets.server import WebSocketServerProtocol
import aiohttp
from aiohttp import web
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from nexus.shared.types.trading import Trade, TradeStatus, Position
from nexus.shared.types.market import MarketData, OHLCV
from nexus.shared.utilities.logger import Logger
from nexus.trading.analytics.metrics_calculator import MetricsCalculator
from nexus.trading.analytics.performance_analyzer import PerformanceAnalyzer

logger = Logger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts"""
    # Performance alerts
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    MAX_DRAWDOWN = "max_drawdown"
    SHARPE_RATIO = "sharpe_ratio"
    WIN_RATE = "win_rate"
    
    # Risk alerts
    VAR_BREACH = "var_breach"
    LEVERAGE_LIMIT = "leverage_limit"
    POSITION_LIMIT = "position_limit"
    CONCENTRATION_LIMIT = "concentration_limit"
    CORRELATION_LIMIT = "correlation_limit"
    
    # Market alerts
    PRICE_BREAKOUT = "price_breakout"
    VOLUME_SPIKE = "volume_spike"
    VOLATILITY_SPIKE = "volatility_spike"
    MARKET_REGIME_CHANGE = "market_regime_change"
    
    # System alerts
    BROKER_DISCONNECT = "broker_disconnect"
    API_ERROR = "api_error"
    LATENCY_HIGH = "latency_high"
    MEMORY_HIGH = "memory_high"
    
    # Trade alerts
    TRADE_EXECUTED = "trade_executed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"


@dataclass
class Alert:
    """Alert definition"""
    id: str = ""
    type: AlertType = AlertType.PROFIT_TARGET
    severity: AlertSeverity = AlertSeverity.INFO
    timestamp: datetime = field(default_factory=datetime.now)
    message: str = ""
    value: float = 0.0
    threshold: float = 0.0
    symbol: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "type": self.type.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "symbol": self.symbol,
            "data": self.data,
            "acknowledged": self.acknowledged,
            "resolved": self.resolved
        }


@dataclass
class RealTimeMetrics:
    """Real-time performance metrics"""
    # Time
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Performance
    pnl: float = 0.0
    pnl_percent: float = 0.0
    equity: float = 0.0
    total_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    
    # Risk
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    var_95: float = 0.0
    
    # Positions
    open_positions: int = 0
    total_exposure: float = 0.0
    leverage: float = 0.0
    
    # Market
    symbol: str = ""
    price: float = 0.0
    volume: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "equity": self.equity,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "current_drawdown": self.current_drawdown,
            "max_drawdown": self.max_drawdown,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "var_95": self.var_95,
            "open_positions": self.open_positions,
            "total_exposure": self.total_exposure,
            "leverage": self.leverage,
            "symbol": self.symbol,
            "price": self.price,
            "volume": self.volume
        }


@dataclass
class AlertConfiguration:
    """Alert configuration"""
    # Performance thresholds
    profit_target: float = 0.10
    stop_loss: float = -0.05
    max_drawdown: float = 0.20
    min_sharpe: float = 0.5
    min_win_rate: float = 0.4
    
    # Risk thresholds
    max_var_95: float = -0.02
    max_leverage: float = 10.0
    max_position_size: float = 0.25
    max_concentration: float = 0.4
    max_correlation: float = 0.8
    
    # Market thresholds
    price_breakout_pct: float = 0.03
    volume_spike_pct: float = 2.0
    volatility_spike_pct: float = 1.5
    
    # System thresholds
    max_latency: float = 0.5
    max_memory_mb: float = 1024
    
    # Alert cooldown
    min_interval_seconds: int = 60
    max_alerts_per_minute: int = 10


@dataclass
class DashboardData:
    """Dashboard data structure"""
    timestamp: datetime = field(default_factory=datetime.now)
    metrics: RealTimeMetrics = field(default_factory=RealTimeMetrics)
    positions: List[Position] = field(default_factory=list)
    recent_trades: List[Trade] = field(default_factory=list)
    alerts: List[Alert] = field(default_factory=list)
    market_data: Dict[str, MarketData] = field(default_factory=dict)
    performance_summary: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "metrics": self.metrics.to_dict(),
            "positions": [p.to_dict() for p in self.positions],
            "recent_trades": [t.to_dict() for t in self.recent_trades],
            "alerts": [a.to_dict() for a in self.alerts],
            "performance_summary": self.performance_summary
        }


class RealTimeMonitor:
    """
    Advanced real-time monitoring system with live performance tracking,
    alerting, anomaly detection, and web dashboard capabilities.
    """
    
    def __init__(
        self,
        alert_config: Optional[AlertConfiguration] = None,
        update_interval: float = 1.0,
        history_length: int = 1000,
        port: int = 8080
    ):
        """
        Initialize the real-time monitor.
        
        Args:
            alert_config: Alert configuration
            update_interval: Update interval in seconds
            history_length: Maximum history length
            port: WebSocket server port
        """
        self.alert_config = alert_config or AlertConfiguration()
        self.update_interval = update_interval
        self.history_length = history_length
        self.port = port
        
        # Data storage
        self._metrics_history = deque(maxlen=history_length)
        self._alerts: List[Alert] = []
        self._acknowledged_alerts: List[str] = []
        self._trade_history = deque(maxlen=history_length)
        self._position_history = deque(maxlen=history_length)
        self._price_history: Dict[str, deque] = {}
        self._anomaly_scores: deque = deque(maxlen=100)
        
        # Performance tracking
        self._initial_equity = 0.0
        self._current_equity = 0.0
        self._peak_equity = 0.0
        self._total_pnl = 0.0
        self._total_trades = 0
        self._winning_trades = 0
        self._losing_trades = 0
        
        # Alert tracking
        self._last_alert_time: Dict[str, datetime] = {}
        self._alert_count_last_minute = 0
        self._alert_reset_time = datetime.now()
        
        # Websocket clients
        self._clients: List[WebSocketServerProtocol] = []
        self._running = False
        self._ws_server = None
        self._http_server = None
        
        # Components
        self._metrics_calculator = MetricsCalculator()
        self._performance_analyzer = PerformanceAnalyzer()
        self._logger = Logger(__name__)
        
        # Callbacks
        self._alert_callbacks: List[Callable] = []
        self._update_callbacks: List[Callable] = []
        
        # Threading
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._monitor_thread = None
        self._ws_thread = None
        self._http_thread = None
        
    async def start_monitoring(self):
        """Start real-time monitoring."""
        self._running = True
        
        # Start monitor loop
        self._monitor_thread = threading.Thread(target=self._monitor_loop)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        
        # Start WebSocket server
        self._ws_thread = threading.Thread(target=self._start_websocket_server)
        self._ws_thread.daemon = True
        self._ws_thread.start()
        
        # Start HTTP server
        self._http_thread = threading.Thread(target=self._start_http_server)
        self._http_thread.daemon = True
        self._http_thread.start()
        
        self._logger.info(f"Real-time monitor started on port {self.port}")
        
    async def stop_monitoring(self):
        """Stop real-time monitoring."""
        self._running = False
        
        if self._ws_server:
            self._ws_server.close()
            
        if self._http_server:
            await self._http_server.shutdown()
            
        self._logger.info("Real-time monitor stopped")
        
    def update_metrics(
        self,
        trades: List[Trade],
        positions: List[Position],
        market_data: Dict[str, MarketData],
        equity: float,
        initial_equity: float
    ):
        """
        Update real-time metrics.
        
        Args:
            trades: List of trades
            positions: List of positions
            market_data: Market data
            equity: Current equity
            initial_equity: Initial equity
        """
        self._initial_equity = initial_equity
        self._current_equity = equity
        
        # Update trade statistics
        completed_trades = [t for t in trades if t.status == TradeStatus.COMPLETED]
        self._total_trades = len(completed_trades)
        self._winning_trades = len([t for t in completed_trades if t.pnl and t.pnl > 0])
        self._losing_trades = len([t for t in completed_trades if t.pnl and t.pnl < 0])
        self._total_pnl = sum([t.pnl for t in completed_trades if t.pnl])
        
        # Update trade history
        for trade in trades[-10:]:
            self._trade_history.append(trade)
        
        # Update position history
        for position in positions:
            self._position_history.append(position)
        
        # Update price history
        for symbol, data in market_data.items():
            if symbol not in self._price_history:
                self._price_history[symbol] = deque(maxlen=self.history_length)
            self._price_history[symbol].append(data.price)
        
        # Update peak equity
        if equity > self._peak_equity:
            self._peak_equity = equity
        
        # Calculate metrics
        metrics = self._calculate_metrics(trades, positions, market_data, equity)
        self._metrics_history.append(metrics)
        
        # Check alerts
        self._check_alerts(metrics, trades, positions, market_data)
        
        # Broadcast updates
        asyncio.create_task(self._broadcast_update(metrics, positions, trades))
        
        # Call update callbacks
        for callback in self._update_callbacks:
            try:
                callback(metrics, positions, trades)
            except Exception as e:
                self._logger.error(f"Error in update callback: {str(e)}")
        
    def subscribe_alerts(self, callback: Callable):
        """Subscribe to alert events."""
        self._alert_callbacks.append(callback)
        
    def subscribe_updates(self, callback: Callable):
        """Subscribe to update events."""
        self._update_callbacks.append(callback)
        
    def get_current_metrics(self) -> Optional[RealTimeMetrics]:
        """Get current real-time metrics."""
        if self._metrics_history:
            return self._metrics_history[-1]
        return None
    
    def get_recent_alerts(self, limit: int = 50) -> List[Alert]:
        """Get recent alerts."""
        return self._alerts[-limit:]
    
    def acknowledge_alert(self, alert_id: str):
        """Acknowledge an alert."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                self._acknowledged_alerts.append(alert_id)
                break
                
    def resolve_alert(self, alert_id: str):
        """Resolve an alert."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.resolved = True
                break
                
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                # Generate periodic update
                if self._metrics_history:
                    metrics = self._metrics_history[-1]
                    
                    # Check for anomalies
                    self._detect_anomalies(metrics)
                    
                    # Update dashboard
                    asyncio.run(self._update_dashboard(metrics))
                    
            except Exception as e:
                self._logger.error(f"Error in monitor loop: {str(e)}")
                
            time.sleep(self.update_interval)
            
    def _calculate_metrics(
        self,
        trades: List[Trade],
        positions: List[Position],
        market_data: Dict[str, MarketData],
        equity: float
    ) -> RealTimeMetrics:
        """Calculate real-time metrics."""
        metrics = RealTimeMetrics()
        metrics.timestamp = datetime.now()
        metrics.equity = equity
        metrics.pnl = equity - self._initial_equity
        metrics.pnl_percent = (equity / self._initial_equity - 1) if self._initial_equity > 0 else 0
        
        # Trade metrics
        metrics.total_trades = self._total_trades
        metrics.win_rate = self._winning_trades / self._total_trades if self._total_trades > 0 else 0
        
        # Profit factor
        gross_profit = sum([t.pnl for t in trades if t.pnl and t.pnl > 0])
        gross_loss = abs(sum([t.pnl for t in trades if t.pnl and t.pnl < 0]))
        metrics.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Risk metrics
        if self._metrics_history:
            returns = [m.pnl_percent for m in self._metrics_history]
            metrics.volatility = np.std(returns) if returns else 0
            
            if len(returns) > 1:
                # Sharpe ratio
                returns_array = np.array(returns)
                excess_returns = returns_array - 0.02 / 252
                metrics.sharpe_ratio = np.mean(excess_returns) / np.std(returns_array) * np.sqrt(252) if np.std(returns_array) > 0 else 0
                
                # VaR
                metrics.var_95 = np.percentile(returns_array, 5)
        
        # Drawdown
        if self._peak_equity > 0:
            metrics.current_drawdown = (self._peak_equity - equity) / self._peak_equity
            metrics.max_drawdown = max(metrics.current_drawdown, 
                                      max([m.max_drawdown for m in self._metrics_history]) if self._metrics_history else 0)
        
        # Positions
        metrics.open_positions = len(positions)
        metrics.total_exposure = sum([p.volume * p.current_price for p in positions])
        metrics.leverage = metrics.total_exposure / equity if equity > 0 else 0
        
        # Market data
        if market_data:
            first_symbol = list(market_data.keys())[0]
            metrics.symbol = first_symbol
            metrics.price = market_data[first_symbol].price
            metrics.volume = market_data[first_symbol].volume
        
        return metrics
    
    def _check_alerts(
        self,
        metrics: RealTimeMetrics,
        trades: List[Trade],
        positions: List[Position],
        market_data: Dict[str, MarketData]
    ):
        """Check for alert conditions."""
        now = datetime.now()
        
        # Rate limiting
        if (now - self._alert_reset_time).seconds > 60:
            self._alert_reset_time = now
            self._alert_count_last_minute = 0
            
        if self._alert_count_last_minute >= self.alert_config.max_alerts_per_minute:
            return
        
        alerts = []
        
        # Performance alerts
        if metrics.pnl_percent >= self.alert_config.profit_target:
            alerts.append(self._create_alert(
                AlertType.PROFIT_TARGET,
                AlertSeverity.INFO,
                f"Profit target reached: {metrics.pnl_percent:.2%}",
                metrics.pnl_percent,
                self.alert_config.profit_target
            ))
            
        if metrics.pnl_percent <= self.alert_config.stop_loss:
            alerts.append(self._create_alert(
                AlertType.STOP_LOSS,
                AlertSeverity.ERROR,
                f"Stop loss triggered: {metrics.pnl_percent:.2%}",
                metrics.pnl_percent,
                self.alert_config.stop_loss
            ))
            
        if metrics.current_drawdown >= self.alert_config.max_drawdown:
            alerts.append(self._create_alert(
                AlertType.MAX_DRAWDOWN,
                AlertSeverity.WARNING,
                f"Maximum drawdown exceeded: {metrics.current_drawdown:.2%}",
                metrics.current_drawdown,
                self.alert_config.max_drawdown
            ))
            
        if metrics.sharpe_ratio < self.alert_config.min_sharpe:
            alerts.append(self._create_alert(
                AlertType.SHARPE_RATIO,
                AlertSeverity.WARNING,
                f"Sharpe ratio below minimum: {metrics.sharpe_ratio:.2f}",
                metrics.sharpe_ratio,
                self.alert_config.min_sharpe
            ))
            
        # Risk alerts
        if metrics.var_95 < self.alert_config.max_var_95:
            alerts.append(self._create_alert(
                AlertType.VAR_BREACH,
                AlertSeverity.WARNING,
                f"VaR threshold breached: {metrics.var_95:.2%}",
                metrics.var_95,
                self.alert_config.max_var_95
            ))
            
        if metrics.leverage > self.alert_config.max_leverage:
            alerts.append(self._create_alert(
                AlertType.LEVERAGE_LIMIT,
                AlertSeverity.ERROR,
                f"Leverage limit exceeded: {metrics.leverage:.1f}x",
                metrics.leverage,
                self.alert_config.max_leverage
            ))
            
        # Position concentration
        if positions and self._initial_equity > 0:
            for position in positions:
                position_value = position.volume * position.current_price
                concentration = position_value / self._initial_equity
                if concentration > self.alert_config.max_position_size:
                    alerts.append(self._create_alert(
                        AlertType.POSITION_LIMIT,
                        AlertSeverity.WARNING,
                        f"Position size limit exceeded for {position.symbol}: {concentration:.2%}",
                        concentration,
                        self.alert_config.max_position_size,
                        symbol=position.symbol
                    ))
                    
        # Market alerts
        for symbol, data in market_data.items():
            price_history = self._price_history.get(symbol, [])
            if len(price_history) > 20:
                price_array = np.array(price_history)
                price_change = (price_array[-1] / price_array[-20] - 1)
                
                if abs(price_change) > self.alert_config.price_breakout_pct:
                    alerts.append(self._create_alert(
                        AlertType.PRICE_BREAKOUT,
                        AlertSeverity.INFO,
                        f"Price breakout for {symbol}: {price_change:.2%}",
                        price_change,
                        self.alert_config.price_breakout_pct,
                        symbol=symbol
                    ))
                    
                # Volume spike
                if hasattr(data, 'volume') and data.volume:
                    avg_volume = np.mean([m.volume for m in market_data.values() if hasattr(m, 'volume')]) if market_data else 0
                    if avg_volume > 0 and data.volume / avg_volume > self.alert_config.volume_spike_pct:
                        alerts.append(self._create_alert(
                            AlertType.VOLUME_SPIKE,
                            AlertSeverity.INFO,
                            f"Volume spike for {symbol}: {data.volume / avg_volume:.1f}x average",
                            data.volume / avg_volume,
                            self.alert_config.volume_spike_pct,
                            symbol=symbol
                        ))
                        
        # Add alerts
        for alert in alerts:
            if not self._should_skip_alert(alert):
                self._alerts.append(alert)
                self._alert_count_last_minute += 1
                
                # Trigger callbacks
                for callback in self._alert_callbacks:
                    try:
                        callback(alert)
                    except Exception as e:
                        self._logger.error(f"Error in alert callback: {str(e)}")
                        
                # Broadcast alert
                asyncio.create_task(self._broadcast_alert(alert))
                
    def _create_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        value: float,
        threshold: float,
        symbol: str = ""
    ) -> Alert:
        """Create a new alert."""
        return Alert(
            id=f"{alert_type.value}_{datetime.now().timestamp()}",
            type=alert_type,
            severity=severity,
            timestamp=datetime.now(),
            message=message,
            value=value,
            threshold=threshold,
            symbol=symbol
        )
        
    def _should_skip_alert(self, alert: Alert) -> bool:
        """Check if alert should be skipped due to cooldown."""
        if alert.id in self._acknowledged_alerts:
            return True
            
        key = f"{alert.type.value}_{alert.symbol}"
        last_time = self._last_alert_time.get(key)
        
        if last_time:
            cooldown_seconds = self.alert_config.min_interval_seconds
            if (datetime.now() - last_time).seconds < cooldown_seconds:
                return True
                
        self._last_alert_time[key] = datetime.now()
        return False
        
    def _detect_anomalies(self, metrics: RealTimeMetrics):
        """Detect anomalies in metrics."""
        # Simple anomaly detection using z-score
        if len(self._metrics_history) > 20:
            recent_values = [m.pnl_percent for m in self._metrics_history][-20:]
            mean = np.mean(recent_values)
            std = np.std(recent_values)
            
            if std > 0:
                z_score = (metrics.pnl_percent - mean) / std
                self._anomaly_scores.append(z_score)
                
                if abs(z_score) > 3:
                    severity = AlertSeverity.WARNING if abs(z_score) > 4 else AlertSeverity.INFO
                    self._create_alert(
                        AlertType.ANOMALY_DETECTED if hasattr(AlertType, 'ANOMALY_DETECTED') else AlertType.ERROR,
                        severity,
                        f"Anomaly detected: PnL {z_score:.2f} standard deviations from mean",
                        z_score,
                        3.0
                    )
                    
    async def _broadcast_update(
        self,
        metrics: RealTimeMetrics,
        positions: List[Position],
        trades: List[Trade]
    ):
        """Broadcast update to WebSocket clients."""
        if not self._clients:
            return
            
        data = DashboardData(
            timestamp=datetime.now(),
            metrics=metrics,
            positions=positions,
            recent_trades=list(trades)[-10:],
            alerts=self._alerts[-10:],
            performance_summary=self._generate_performance_summary()
        )
        
        message = json.dumps({
            "type": "update",
            "data": data.to_dict()
        })
        
        # Broadcast to all clients
        for client in self._clients[:]:
            try:
                await client.send(message)
            except Exception as e:
                self._logger.error(f"Error broadcasting to client: {str(e)}")
                self._clients.remove(client)
                
    async def _broadcast_alert(self, alert: Alert):
        """Broadcast alert to WebSocket clients."""
        if not self._clients:
            return
            
        message = json.dumps({
            "type": "alert",
            "data": alert.to_dict()
        })
        
        for client in self._clients[:]:
            try:
                await client.send(message)
            except Exception:
                # Client might be closed
                pass
                
    def _generate_performance_summary(self) -> Dict[str, Any]:
        """Generate performance summary."""
        if not self._metrics_history:
            return {}
            
        metrics_list = list(self._metrics_history)
        
        return {
            "total_trades": self._total_trades,
            "winning_trades": self._winning_trades,
            "losing_trades": self._losing_trades,
            "win_rate": self._winning_trades / self._total_trades if self._total_trades > 0 else 0,
            "total_pnl": self._total_pnl,
            "current_equity": self._current_equity,
            "peak_equity": self._peak_equity,
            "current_drawdown": (self._peak_equity - self._current_equity) / self._peak_equity if self._peak_equity > 0 else 0,
            "max_drawdown": max([m.max_drawdown for m in metrics_list]) if metrics_list else 0,
            "avg_sharpe": np.mean([m.sharpe_ratio for m in metrics_list if m.sharpe_ratio != 0]) if metrics_list else 0,
            "alerts_count": len(self._alerts),
            "active_alerts": len([a for a in self._alerts if not a.resolved and not a.acknowledged])
        }
        
    async def _update_dashboard(self, metrics: RealTimeMetrics):
        """Update dashboard with latest metrics."""
        # Update dashboard in real-time
        # This could be extended to push to external dashboards
        pass
        
    def _start_websocket_server(self):
        """Start WebSocket server in separate thread."""
        asyncio.run(self._websocket_server())
        
    async def _websocket_server(self):
        """WebSocket server handler."""
        async with websockets.serve(self._handle_websocket, "0.0.0.0", self.port + 1):
            self._logger.info(f"WebSocket server started on port {self.port + 1}")
            await asyncio.Future()  # Run forever
            
    async def _handle_websocket(self, websocket: WebSocketServerProtocol):
        """Handle WebSocket connection."""
        self._clients.append(websocket)
        self._logger.info(f"WebSocket client connected: {websocket.remote_address}")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    if data.get("type") == "subscribe":
                        # Send initial data
                        await self._send_initial_data(websocket)
                    elif data.get("type") == "acknowledge_alert":
                        alert_id = data.get("alert_id")
                        if alert_id:
                            self.acknowledge_alert(alert_id)
                except json.JSONDecodeError:
                    self._logger.error(f"Invalid JSON message: {message}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            if websocket in self._clients:
                self._clients.remove(websocket)
            self._logger.info(f"WebSocket client disconnected: {websocket.remote_address}")
            
    async def _send_initial_data(self, websocket: WebSocketServerProtocol):
        """Send initial data to new client."""
        data = {
            "type": "init",
            "data": {
                "metrics": self.get_current_metrics().to_dict() if self.get_current_metrics() else None,
                "alerts": [a.to_dict() for a in self._alerts[-50:]],
                "performance_summary": self._generate_performance_summary()
            }
        }
        await websocket.send(json.dumps(data))
        
    def _start_http_server(self):
        """Start HTTP server in separate thread."""
        asyncio.run(self._http_server())
        
    async def _http_server(self):
        """HTTP server handler."""
        app = web.Application()
        app.router.add_get('/', self._handle_dashboard)
        app.router.add_get('/api/metrics', self._handle_metrics_api)
        app.router.add_get('/api/alerts', self._handle_alerts_api)
        app.router.add_get('/api/dashboard', self._handle_dashboard_api)
        
        runner = web.AppRunner(app)
        await runner.setup()
        self._http_server = web.TCPSite(runner, "0.0.0.0", self.port)
        await self._http_server.start()
        
        self._logger.info(f"HTTP server started on port {self.port}")
        await asyncio.Future()  # Run forever
        
    async def _handle_dashboard(self, request: web.Request) -> web.Response:
        """Handle dashboard request."""
        html = self._generate_dashboard_html()
        return web.Response(text=html, content_type="text/html")
        
    async def _handle_metrics_api(self, request: web.Request) -> web.Response:
        """Handle metrics API request."""
        metrics = self.get_current_metrics()
        if metrics:
            return web.json_response(metrics.to_dict())
        return web.json_response({"error": "No metrics available"}, status=404)
        
    async def _handle_alerts_api(self, request: web.Request) -> web.Response:
        """Handle alerts API request."""
        limit = int(request.query.get("limit", 50))
        alerts = self.get_recent_alerts(limit)
        return web.json_response([a.to_dict() for a in alerts])
        
    async def _handle_dashboard_api(self, request: web.Request) -> web.Response:
        """Handle dashboard API request."""
        data = DashboardData(
            timestamp=datetime.now(),
            metrics=self.get_current_metrics() or RealTimeMetrics(),
            alerts=self._alerts[-10:],
            performance_summary=self._generate_performance_summary()
        )
        return web.json_response(data.to_dict())
        
    def _generate_dashboard_html(self) -> str:
        """Generate HTML dashboard."""
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>NEXUS Real-Time Monitor</title>
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background: #0a0e1a;
                    color: #e0e0e0;
                }
                .dashboard {
                    max-width: 1400px;
                    margin: 0 auto;
                }
                .header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 20px;
                    background: linear-gradient(135deg, #1a1f3a, #2a1f4a);
                    border-radius: 12px;
                    margin-bottom: 20px;
                    border: 1px solid #2a3a6a;
                }
                .header h1 {
                    margin: 0;
                    color: #00d4ff;
                    font-weight: 300;
                    letter-spacing: 2px;
                }
                .header .status {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }
                .status-dot {
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    background: #00ff88;
                    animation: pulse 1.5s ease-in-out infinite;
                }
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.3; }
                }
                .metrics-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                    margin-bottom: 20px;
                }
                .metric-card {
                    background: #141b2d;
                    padding: 15px 20px;
                    border-radius: 10px;
                    border: 1px solid #1a2a4a;
                    transition: all 0.3s ease;
                }
                .metric-card:hover {
                    border-color: #00d4ff;
                    transform: translateY(-2px);
                }
                .metric-value {
                    font-size: 28px;
                    font-weight: 600;
                    color: #00d4ff;
                }
                .metric-value.positive { color: #00ff88; }
                .metric-value.negative { color: #ff4466; }
                .metric-label {
                    font-size: 12px;
                    color: #8899bb;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    margin-top: 5px;
                }
                .chart-container {
                    background: #141b2d;
                    border-radius: 10px;
                    padding: 20px;
                    border: 1px solid #1a2a4a;
                    margin-bottom: 20px;
                }
                .chart-container h3 {
                    color: #8899bb;
                    margin: 0 0 15px 0;
                    font-weight: 300;
                    letter-spacing: 1px;
                }
                .alerts-panel {
                    background: #141b2d;
                    border-radius: 10px;
                    padding: 20px;
                    border: 1px solid #1a2a4a;
                    max-height: 400px;
                    overflow-y: auto;
                }
                .alert-item {
                    padding: 10px 15px;
                    border-radius: 6px;
                    margin-bottom: 8px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    border-left: 4px solid #8899bb;
                }
                .alert-item.info { border-color: #00d4ff; background: rgba(0, 212, 255, 0.05); }
                .alert-item.warning { border-color: #ffaa00; background: rgba(255, 170, 0, 0.05); }
                .alert-item.error { border-color: #ff4466; background: rgba(255, 68, 102, 0.05); }
                .alert-item.critical { border-color: #ff0044; background: rgba(255, 0, 68, 0.1); }
                .alert-message { flex: 1; }
                .alert-time { font-size: 12px; color: #8899bb; margin-left: 15px; }
                .alert-badge {
                    padding: 2px 10px;
                    border-radius: 12px;
                    font-size: 10px;
                    text-transform: uppercase;
                    font-weight: 600;
                }
                .alert-badge.info { background: #00d4ff22; color: #00d4ff; }
                .alert-badge.warning { background: #ffaa0022; color: #ffaa00; }
                .alert-badge.error { background: #ff446622; color: #ff4466; }
                .alert-badge.critical { background: #ff004422; color: #ff0044; }
                .status-bar {
                    display: flex;
                    justify-content: space-between;
                    padding: 10px 20px;
                    background: #141b2d;
                    border-radius: 8px;
                    border: 1px solid #1a2a4a;
                    margin-top: 20px;
                    font-size: 12px;
                    color: #8899bb;
                }
                #chart {
                    width: 100%;
                    height: 300px;
                }
                ::-webkit-scrollbar {
                    width: 8px;
                }
                ::-webkit-scrollbar-track {
                    background: #0a0e1a;
                }
                ::-webkit-scrollbar-thumb {
                    background: #1a2a4a;
                    border-radius: 4px;
                }
                ::-webkit-scrollbar-thumb:hover {
                    background: #2a3a6a;
                }
            </style>
        </head>
        <body>
            <div class="dashboard">
                <div class="header">
                    <h1>⚡ NEXUS Real-Time Monitor</h1>
                    <div class="status">
                        <span id="timestamp">Loading...</span>
                        <div class="status-dot"></div>
                        <span style="color: #8899bb;">Live</span>
                    </div>
                </div>
                
                <div class="metrics-grid" id="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-value" id="equity">-</div>
                        <div class="metric-label">Equity</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value" id="pnl">-</div>
                        <div class="metric-label">PnL</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value" id="drawdown">-</div>
                        <div class="metric-label">Drawdown</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value" id="win-rate">-</div>
                        <div class="metric-label">Win Rate</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value" id="sharpe">-</div>
                        <div class="metric-label">Sharpe Ratio</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value" id="trades">-</div>
                        <div class="metric-label">Total Trades</div>
                    </div>
                </div>
                
                <div class="chart-container">
                    <h3>📈 Equity Curve</h3>
                    <div id="chart"></div>
                </div>
                
                <div class="alerts-panel" id="alerts-panel">
                    <h3 style="color: #8899bb; margin: 0 0 15px 0; font-weight: 300; letter-spacing: 1px;">
                        🔔 Recent Alerts
                    </h3>
                    <div id="alerts-list">
                        <div style="text-align: center; color: #8899bb; padding: 20px;">
                            No alerts
                        </div>
                    </div>
                </div>
                
                <div class="status-bar">
                    <span>🟢 System: Online</span>
                    <span id="alert-count">Alerts: 0</span>
                    <span id="connection-status">WebSocket: Connected</span>
                    <span id="update-time">Last Update: -</span>
                </div>
            </div>
            
            <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
            <script>
                let ws = null;
                let equityData = [];
                let timeData = [];
                let chart = null;
                
                function connectWebSocket() {
                    const wsPort = window.location.port ? parseInt(window.location.port) + 1 : 8081;
                    ws = new WebSocket(`ws://${window.location.hostname}:${wsPort}`);
                    
                    ws.onopen = function() {
                        document.getElementById('connection-status').textContent = 'WebSocket: Connected';
                        ws.send(JSON.stringify({type: 'subscribe'}));
                    };
                    
                    ws.onclose = function() {
                        document.getElementById('connection-status').textContent = 'WebSocket: Disconnected';
                        setTimeout(connectWebSocket, 5000);
                    };
                    
                    ws.onerror = function(error) {
                        console.error('WebSocket error:', error);
                    };
                    
                    ws.onmessage = function(event) {
                        try {
                            const data = JSON.parse(event.data);
                            if (data.type === 'update') {
                                updateDashboard(data.data);
                            } else if (data.type === 'alert') {
                                addAlert(data.data);
                            } else if (data.type === 'init') {
                                if (data.data.metrics) {
                                    updateMetrics(data.data.metrics);
                                }
                                if (data.data.alerts) {
                                    data.data.alerts.forEach(addAlert);
                                }
                            }
                        } catch (e) {
                            console.error('Error processing message:', e);
                        }
                    };
                }
                
                function updateDashboard(data) {
                    document.getElementById('timestamp').textContent = new Date(data.timestamp).toLocaleTimeString();
                    document.getElementById('update-time').textContent = `Last Update: ${new Date(data.timestamp).toLocaleTimeString()}`;
                    
                    if (data.metrics) {
                        updateMetrics(data.metrics);
                        
                        // Update equity chart
                        equityData.push(data.metrics.equity);
                        timeData.push(new Date(data.timestamp).toLocaleTimeString());
                        
                        if (equityData.length > 100) {
                            equityData.shift();
                            timeData.shift();
                        }
                        
                        updateChart();
                    }
                    
                    if (data.performance_summary) {
                        document.getElementById('alert-count').textContent = `Alerts: ${data.performance_summary.alerts_count || 0}`;
                    }
                }
                
                function updateMetrics(metrics) {
                    document.getElementById('equity').textContent = `$${metrics.equity ? metrics.equity.toFixed(2) : '0.00'}`;
                    
                    const pnlElement = document.getElementById('pnl');
                    const pnl = metrics.pnl || 0;
                    pnlElement.textContent = `$${pnl.toFixed(2)} (${(metrics.pnl_percent || 0) * 100}%)`;
                    pnlElement.className = 'metric-value ' + (pnl >= 0 ? 'positive' : 'negative');
                    
                    const drawdownElement = document.getElementById('drawdown');
                    const drawdown = (metrics.current_drawdown || 0) * 100;
                    drawdownElement.textContent = `${drawdown.toFixed(2)}%`;
                    drawdownElement.className = 'metric-value ' + (drawdown < 10 ? 'positive' : 'negative');
                    
                    document.getElementById('win-rate').textContent = `${((metrics.win_rate || 0) * 100).toFixed(2)}%`;
                    document.getElementById('sharpe').textContent = (metrics.sharpe_ratio || 0).toFixed(2);
                    document.getElementById('trades').textContent = metrics.total_trades || 0;
                }
                
                function updateChart() {
                    if (chart === null) {
                        chart = Plotly.newPlot('chart', [{
                            x: timeData,
                            y: equityData,
                            type: 'scatter',
                            mode: 'lines+markers',
                            line: {color: '#00d4ff', width: 2},
                            marker: {color: '#00d4ff', size: 4},
                            name: 'Equity'
                        }], {
                            paper_bgcolor: 'transparent',
                            plot_bgcolor: 'transparent',
                            font: {color: '#8899bb'},
                            margin: {l: 50, r: 20, t: 20, b: 40},
                            xaxis: {gridcolor: '#1a2a4a', title: 'Time'},
                            yaxis: {gridcolor: '#1a2a4a', title: 'Equity ($)'}
                        });
                    } else {
                        Plotly.update('chart', {
                            x: [timeData],
                            y: [equityData]
                        });
                    }
                }
                
                function addAlert(alert) {
                    const list = document.getElementById('alerts-list');
                    
                    // Remove "No alerts" message
                    if (list.children.length === 1 && list.children[0].textContent.trim() === 'No alerts') {
                        list.innerHTML = '';
                    }
                    
                    const alertDiv = document.createElement('div');
                    alertDiv.className = `alert-item ${alert.severity}`;
                    
                    const time = new Date(alert.timestamp).toLocaleTimeString();
                    
                    alertDiv.innerHTML = `
                        <span class="alert-message">${alert.message}</span>
                        <span class="alert-badge ${alert.severity}">${alert.severity}</span>
                        <span class="alert-time">${time}</span>
                    `;
                    
                    list.prepend(alertDiv);
                    
                    // Keep only last 50 alerts
                    while (list.children.length > 50) {
                        list.removeChild(list.lastChild);
                    }
                }
                
                // Initialize
                connectWebSocket();
                
                // Refresh metrics every 5 seconds as fallback
                setInterval(() => {
                    fetch('/api/metrics')
                        .then(res => res.json())
                        .then(data => {
                            if (data && data.equity) {
                                updateMetrics(data);
                            }
                        })
                        .catch(err => console.error('Error fetching metrics:', err));
                }, 5000);
            </script>
        </body>
        </html>
        """
        
    def get_dashboard_html(self) -> str:
        """Get dashboard HTML content."""
        return self._generate_dashboard_html()


# Factory function
def create_realtime_monitor(
    update_interval: float = 1.0,
    port: int = 8080,
    profit_target: float = 0.10,
    stop_loss: float = -0.05,
    max_drawdown: float = 0.20
) -> RealTimeMonitor:
    """
    Create a real-time monitor with default configuration.
    
    Args:
        update_interval: Update interval in seconds
        port: HTTP server port
        profit_target: Profit target for alerts
        stop_loss: Stop loss for alerts
        max_drawdown: Maximum drawdown for alerts
        
    Returns:
        Configured RealTimeMonitor instance
    """
    config = AlertConfiguration(
        profit_target=profit_target,
        stop_loss=stop_loss,
        max_drawdown=max_drawdown
    )
    return RealTimeMonitor(
        alert_config=config,
        update_interval=update_interval,
        port=port
    )
