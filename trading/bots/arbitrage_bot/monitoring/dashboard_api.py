# trading/bots/arbitrage_bot/monitoring/dashboard_api.py
# NEXUS AI TRADING SYSTEM - DASHBOARD API
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module provides the REST API endpoints for the monitoring dashboard,
# exposing real-time metrics, alerts, trades, and system status.
# ====================================================================================

"""
NEXUS Arbitrage Bot Dashboard API

This module provides comprehensive API endpoints for:
- Real-time system metrics and status
- Trade execution monitoring
- Opportunity detection and analysis
- Alert management and notifications
- Performance analytics and reporting
- Exchange connectivity status
- Portfolio and position tracking
- Configuration management
"""

import asyncio
import logging
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

# Web framework
try:
    from fastapi import FastAPI, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, StreamingResponse
    from pydantic import BaseModel, Field
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# NEXUS internal imports
from trading.bots.arbitrage_bot.core.metrics_collector import MetricsCollector
from trading.bots.arbitrage_bot.core.health_check import HealthCheck
from trading.bots.arbitrage_bot.models.alert import Alert, AlertSeverity, AlertStatus, AlertCategory
from trading.bots.arbitrage_bot.models.trade import Trade, TradeStatus
from trading.bots.arbitrage_bot.models.opportunity import ArbitrageOpportunity
from trading.bots.arbitrage_bot.models.portfolio import Portfolio
from trading.bots.arbitrage_bot.models.position import Position
from trading.bots.arbitrage_bot.models.balance import Balance
from trading.bots.arbitrage_bot.models.exchange import ExchangeHealth, ExchangeStatus
from trading.bots.arbitrage_bot.models.performance import PerformanceMetrics

logger = logging.getLogger("nexus.arbitrage.dashboard_api")


# ====================================================================================
# PYDANTIC MODELS
# ====================================================================================

if HAS_FASTAPI:
    class SystemStatusResponse(BaseModel):
        """System status response."""
        status: str
        uptime_seconds: float
        version: str
        environment: str
        timestamp: datetime
        
    class MetricsResponse(BaseModel):
        """Metrics response."""
        metrics: Dict[str, Any]
        timestamp: datetime
        
    class TradeResponse(BaseModel):
        """Trade response."""
        trade_id: str
        symbol: str
        exchange: str
        side: str
        quantity: float
        price: float
        value: float
        status: str
        profit: float
        profit_percentage: float
        timestamp: datetime
        
    class OpportunityResponse(BaseModel):
        """Opportunity response."""
        opportunity_id: str
        type: str
        strategy: str
        symbol: str
        profit_percentage: float
        confidence: float
        status: str
        timestamp: datetime
        
    class AlertResponse(BaseModel):
        """Alert response."""
        alert_id: str
        title: str
        description: str
        severity: str
        category: str
        status: str
        timestamp: datetime
        
    class ExchangeHealthResponse(BaseModel):
        """Exchange health response."""
        exchange: str
        status: str
        latency_ms: float
        success_rate: float
        connected: bool
        last_check: datetime
        
    class PortfolioSummaryResponse(BaseModel):
        """Portfolio summary response."""
        total_value: float
        total_profit: float
        profit_percentage: float
        asset_count: int
        exchange_count: int
        allocation: Dict[str, float]
        
    class PositionResponse(BaseModel):
        """Position response."""
        symbol: str
        exchange: str
        side: str
        size: float
        entry_price: float
        current_price: float
        unrealized_pnl: float
        pnl_percentage: float
        
    class PerformanceResponse(BaseModel):
        """Performance response."""
        total_trades: int
        win_rate: float
        total_profit: float
        avg_profit: float
        max_drawdown: float
        sharpe_ratio: float
        period_start: datetime
        period_end: datetime


# ====================================================================================
# DASHBOARD API
# ====================================================================================

class DashboardAPI:
    """
    Dashboard API for monitoring and management.
    
    Features:
    - Real-time system metrics
    - Trade execution monitoring
    - Opportunity detection
    - Alert management
    - Performance analytics
    - Exchange health monitoring
    - Portfolio tracking
    - WebSocket real-time updates
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Dashboard API.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self._app = None
        self._ws_connections: Dict[str, List[WebSocket]] = {}
        self._metrics = MetricsCollector(name="nexus_dashboard_api")
        self._health_check = HealthCheck(name="dashboard_api")
        
        # Data sources (to be injected)
        self._trade_manager = None
        self._opportunity_manager = None
        self._alert_manager = None
        self._exchange_manager = None
        self._portfolio_manager = None
        self._position_manager = None
        self._balance_manager = None
        
        # Cache
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: Dict[str, float] = {}
        
        # State
        self._start_time = datetime.utcnow()
        self._running = False
        
        logger.info("DashboardAPI initialized (version=3.0.0)")
        
    def setup(
        self,
        trade_manager: Any,
        opportunity_manager: Any,
        alert_manager: Any,
        exchange_manager: Any,
        portfolio_manager: Any,
        position_manager: Any,
        balance_manager: Any
    ) -> None:
        """
        Setup data sources.
        
        Args:
            trade_manager: Trade manager instance
            opportunity_manager: Opportunity manager instance
            alert_manager: Alert manager instance
            exchange_manager: Exchange manager instance
            portfolio_manager: Portfolio manager instance
            position_manager: Position manager instance
            balance_manager: Balance manager instance
        """
        self._trade_manager = trade_manager
        self._opportunity_manager = opportunity_manager
        self._alert_manager = alert_manager
        self._exchange_manager = exchange_manager
        self._portfolio_manager = portfolio_manager
        self._position_manager = position_manager
        self._balance_manager = balance_manager
        
    def create_app(self) -> Any:
        """
        Create FastAPI application.
        
        Returns:
            FastAPI application
        """
        if not HAS_FASTAPI:
            raise ImportError("FastAPI is not installed")
            
        app = FastAPI(
            title="NEXUS Arbitrage Bot Dashboard API",
            description="Real-time monitoring and management API for the NEXUS arbitrage bot",
            version="3.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.get("cors_origins", ["*"]),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Add routes
        self._add_routes(app)
        
        self._app = app
        return app
        
    def _add_routes(self, app: Any) -> None:
        """
        Add routes to the application.
        
        Args:
            app: FastAPI application
        """
        # System routes
        app.get("/api/v1/status")(self.get_system_status)
        app.get("/api/v1/health")(self.get_health)
        app.get("/api/v1/metrics")(self.get_metrics)
        
        # Trade routes
        app.get("/api/v1/trades")(self.get_trades)
        app.get("/api/v1/trades/{trade_id}")(self.get_trade)
        app.get("/api/v1/trades/summary")(self.get_trade_summary)
        
        # Opportunity routes
        app.get("/api/v1/opportunities")(self.get_opportunities)
        app.get("/api/v1/opportunities/{opportunity_id}")(self.get_opportunity)
        app.get("/api/v1/opportunities/summary")(self.get_opportunity_summary)
        
        # Alert routes
        app.get("/api/v1/alerts")(self.get_alerts)
        app.get("/api/v1/alerts/{alert_id}")(self.get_alert)
        app.post("/api/v1/alerts/{alert_id}/acknowledge")(self.acknowledge_alert)
        app.post("/api/v1/alerts/{alert_id}/resolve")(self.resolve_alert)
        app.get("/api/v1/alerts/stats")(self.get_alert_stats)
        
        # Exchange routes
        app.get("/api/v1/exchanges")(self.get_exchanges)
        app.get("/api/v1/exchanges/{exchange}")(self.get_exchange)
        app.get("/api/v1/exchanges/health")(self.get_exchange_health)
        
        # Portfolio routes
        app.get("/api/v1/portfolio")(self.get_portfolio)
        app.get("/api/v1/portfolio/positions")(self.get_positions)
        app.get("/api/v1/portfolio/balances")(self.get_balances)
        
        # Performance routes
        app.get("/api/v1/performance")(self.get_performance)
        app.get("/api/v1/performance/daily")(self.get_daily_performance)
        app.get("/api/v1/performance/weekly")(self.get_weekly_performance)
        app.get("/api/v1/performance/monthly")(self.get_monthly_performance)
        
        # WebSocket route
        app.websocket("/ws")(self.websocket_endpoint)
        
    # ====================================================================
    # SYSTEM ENDPOINTS
    # ====================================================================
    
    async def get_system_status(self) -> Dict[str, Any]:
        """
        Get system status.
        
        Returns:
            System status
        """
        uptime = (datetime.utcnow() - self._start_time).total_seconds()
        
        return {
            "status": "running" if self._running else "stopped",
            "uptime_seconds": uptime,
            "uptime_formatted": self._format_uptime(uptime),
            "version": "3.0.0",
            "environment": self.config.get("environment", "production"),
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "trade_manager": self._trade_manager is not None,
                "opportunity_manager": self._opportunity_manager is not None,
                "alert_manager": self._alert_manager is not None,
                "exchange_manager": self._exchange_manager is not None,
                "portfolio_manager": self._portfolio_manager is not None,
                "position_manager": self._position_manager is not None,
                "balance_manager": self._balance_manager is not None
            }
        }
        
    async def get_health(self) -> Dict[str, Any]:
        """
        Get health status.
        
        Returns:
            Health status
        """
        health = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }
        
        # Check trade manager
        if self._trade_manager:
            try:
                # Get trade count as health check
                trades = await self._trade_manager.get_trades(limit=1)
                health["checks"]["trade_manager"] = {"status": "healthy"}
            except Exception as e:
                health["checks"]["trade_manager"] = {"status": "unhealthy", "error": str(e)}
                
        # Check exchange manager
        if self._exchange_manager:
            try:
                exchanges = await self._exchange_manager.get_exchanges()
                health["checks"]["exchange_manager"] = {
                    "status": "healthy",
                    "exchanges": len(exchanges)
                }
            except Exception as e:
                health["checks"]["exchange_manager"] = {"status": "unhealthy", "error": str(e)}
                
        # Determine overall status
        for check in health["checks"].values():
            if check.get("status") == "unhealthy":
                health["status"] = "degraded"
                break
                
        return health
        
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get system metrics.
        
        Returns:
            System metrics
        """
        return {
            "metrics": self._metrics.get_metrics(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    # ====================================================================
    # TRADE ENDPOINTS
    # ====================================================================
    
    async def get_trades(
        self,
        limit: int = 100,
        offset: int = 0,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
        status: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get trades with filters.
        
        Args:
            limit: Maximum number of trades
            offset: Offset for pagination
            symbol: Filter by symbol
            exchange: Filter by exchange
            status: Filter by status
            from_date: Filter from date
            to_date: Filter to date
            
        Returns:
            Trades with pagination
        """
        if not self._trade_manager:
            raise HTTPException(status_code=503, detail="Trade manager not available")
            
        try:
            trades = await self._trade_manager.get_trades(
                limit=limit,
                offset=offset,
                symbol=symbol,
                exchange=exchange,
                status=status,
                from_date=from_date,
                to_date=to_date
            )
            
            return {
                "trades": [self._format_trade(t) for t in trades],
                "total": len(trades),
                "limit": limit,
                "offset": offset,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_trade(self, trade_id: str) -> Dict[str, Any]:
        """
        Get trade by ID.
        
        Args:
            trade_id: Trade ID
            
        Returns:
            Trade details
        """
        if not self._trade_manager:
            raise HTTPException(status_code=503, detail="Trade manager not available")
            
        try:
            trade = await self._trade_manager.get_trade(trade_id)
            if not trade:
                raise HTTPException(status_code=404, detail="Trade not found")
                
            return self._format_trade(trade)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_trade_summary(self, period_days: int = 1) -> Dict[str, Any]:
        """
        Get trade summary.
        
        Args:
            period_days: Analysis period in days
            
        Returns:
            Trade summary
        """
        if not self._trade_manager:
            raise HTTPException(status_code=503, detail="Trade manager not available")
            
        try:
            summary = await self._trade_manager.get_summary(period_days=period_days)
            return {
                "total_trades": summary.total_trades,
                "winning_trades": summary.winning_trades,
                "losing_trades": summary.losing_trades,
                "win_rate": summary.win_rate,
                "total_profit": summary.total_profit,
                "avg_profit": summary.avg_profit,
                "largest_win": summary.largest_win,
                "largest_loss": summary.largest_loss,
                "profit_factor": summary.profit_factor,
                "period_start": summary.period_start.isoformat(),
                "period_end": summary.period_end.isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    def _format_trade(self, trade: Trade) -> Dict[str, Any]:
        """Format trade for response."""
        return {
            "trade_id": trade.trade_id,
            "symbol": trade.symbol,
            "exchange": trade.exchange,
            "side": trade.side.value if hasattr(trade.side, 'value') else trade.side,
            "quantity": trade.quantity,
            "price": trade.price,
            "value": trade.value,
            "status": trade.status.value if hasattr(trade.status, 'value') else trade.status,
            "profit": trade.net_profit,
            "profit_percentage": trade.profit_percentage,
            "created_at": trade.created_at.isoformat(),
            "executed_at": trade.executed_at.isoformat() if trade.executed_at else None
        }
        
    # ====================================================================
    # OPPORTUNITY ENDPOINTS
    # ====================================================================
    
    async def get_opportunities(
        self,
        limit: int = 100,
        offset: int = 0,
        type: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        min_profit: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Get opportunities with filters.
        
        Args:
            limit: Maximum number of opportunities
            offset: Offset for pagination
            type: Filter by type
            symbol: Filter by symbol
            status: Filter by status
            min_profit: Minimum profit percentage
            
        Returns:
            Opportunities with pagination
        """
        if not self._opportunity_manager:
            raise HTTPException(status_code=503, detail="Opportunity manager not available")
            
        try:
            opportunities = await self._opportunity_manager.get_opportunities(
                limit=limit,
                offset=offset,
                type=type,
                symbol=symbol,
                status=status,
                min_profit=min_profit
            )
            
            return {
                "opportunities": [self._format_opportunity(o) for o in opportunities],
                "total": len(opportunities),
                "limit": limit,
                "offset": offset,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_opportunity(self, opportunity_id: str) -> Dict[str, Any]:
        """
        Get opportunity by ID.
        
        Args:
            opportunity_id: Opportunity ID
            
        Returns:
            Opportunity details
        """
        if not self._opportunity_manager:
            raise HTTPException(status_code=503, detail="Opportunity manager not available")
            
        try:
            opportunity = await self._opportunity_manager.get_opportunity(opportunity_id)
            if not opportunity:
                raise HTTPException(status_code=404, detail="Opportunity not found")
                
            return self._format_opportunity(opportunity)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_opportunity_summary(self, period_days: int = 1) -> Dict[str, Any]:
        """
        Get opportunity summary.
        
        Args:
            period_days: Analysis period in days
            
        Returns:
            Opportunity summary
        """
        if not self._opportunity_manager:
            raise HTTPException(status_code=503, detail="Opportunity manager not available")
            
        try:
            summary = await self._opportunity_manager.get_summary(period_days=period_days)
            return {
                "total_detected": summary.total_detected,
                "total_executed": summary.total_executed,
                "total_failed": summary.total_failed,
                "success_rate": summary.success_rate,
                "total_profit": summary.total_profit,
                "avg_profit": summary.avg_profit,
                "profit_percentage": summary.profit_percentage,
                "by_type": summary.by_type,
                "by_symbol": summary.by_symbol,
                "period_start": summary.period_start.isoformat(),
                "period_end": summary.period_end.isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    def _format_opportunity(self, opportunity: ArbitrageOpportunity) -> Dict[str, Any]:
        """Format opportunity for response."""
        return {
            "opportunity_id": opportunity.opportunity_id,
            "type": opportunity.type.value if hasattr(opportunity.type, 'value') else str(opportunity.type),
            "strategy": opportunity.strategy,
            "symbol": opportunity.symbols[0] if opportunity.symbols else None,
            "profit_percentage": opportunity.profit_percentage,
            "confidence": opportunity.confidence_score,
            "status": opportunity.status.value if hasattr(opportunity.status, 'value') else str(opportunity.status),
            "net_profit": opportunity.net_profit,
            "gross_profit": opportunity.gross_profit,
            "detected_at": opportunity.detected_at.isoformat(),
            "expires_at": opportunity.expires_at.isoformat(),
            "executed_at": opportunity.executed_at.isoformat() if opportunity.executed_at else None
        }
        
    # ====================================================================
    # ALERT ENDPOINTS
    # ====================================================================
    
    async def get_alerts(
        self,
        limit: int = 100,
        offset: int = 0,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get alerts with filters.
        
        Args:
            limit: Maximum number of alerts
            offset: Offset for pagination
            severity: Filter by severity
            category: Filter by category
            status: Filter by status
            from_date: Filter from date
            to_date: Filter to date
            
        Returns:
            Alerts with pagination
        """
        if not self._alert_manager:
            raise HTTPException(status_code=503, detail="Alert manager not available")
            
        try:
            alerts = await self._alert_manager.get_alerts(
                limit=limit,
                offset=offset,
                severity=severity,
                category=category,
                status=status,
                from_date=from_date,
                to_date=to_date
            )
            
            return {
                "alerts": [self._format_alert(a) for a in alerts],
                "total": len(alerts),
                "limit": limit,
                "offset": offset,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_alert(self, alert_id: str) -> Dict[str, Any]:
        """
        Get alert by ID.
        
        Args:
            alert_id: Alert ID
            
        Returns:
            Alert details
        """
        if not self._alert_manager:
            raise HTTPException(status_code=503, detail="Alert manager not available")
            
        try:
            alert = await self._alert_manager.get_alert(alert_id)
            if not alert:
                raise HTTPException(status_code=404, detail="Alert not found")
                
            return self._format_alert(alert)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def acknowledge_alert(self, alert_id: str, user: str = "system") -> Dict[str, Any]:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: Alert ID
            user: User acknowledging
            
        Returns:
            Result
        """
        if not self._alert_manager:
            raise HTTPException(status_code=503, detail="Alert manager not available")
            
        try:
            result = await self._alert_manager.acknowledge_alert(alert_id, user)
            if not result:
                raise HTTPException(status_code=404, detail="Alert not found")
                
            return {"status": "acknowledged", "alert_id": alert_id, "user": user}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def resolve_alert(self, alert_id: str, user: str = "system") -> Dict[str, Any]:
        """
        Resolve an alert.
        
        Args:
            alert_id: Alert ID
            user: User resolving
            
        Returns:
            Result
        """
        if not self._alert_manager:
            raise HTTPException(status_code=503, detail="Alert manager not available")
            
        try:
            result = await self._alert_manager.resolve_alert(alert_id, user)
            if not result:
                raise HTTPException(status_code=404, detail="Alert not found")
                
            return {"status": "resolved", "alert_id": alert_id, "user": user}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_alert_stats(self, period_days: int = 1) -> Dict[str, Any]:
        """
        Get alert statistics.
        
        Args:
            period_days: Analysis period in days
            
        Returns:
            Alert statistics
        """
        if not self._alert_manager:
            raise HTTPException(status_code=503, detail="Alert manager not available")
            
        try:
            stats = await self._alert_manager.get_stats(period_days=period_days)
            return {
                "total": stats.total,
                "by_severity": stats.by_severity,
                "by_category": stats.by_category,
                "by_status": stats.by_status,
                "resolution_rate": stats.resolution_rate,
                "average_resolution_time": stats.average_resolution_time,
                "period_start": stats.period_start.isoformat(),
                "period_end": stats.period_end.isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    def _format_alert(self, alert: Alert) -> Dict[str, Any]:
        """Format alert for response."""
        return {
            "alert_id": alert.id,
            "title": alert.title,
            "description": alert.description,
            "severity": alert.severity.value if hasattr(alert.severity, 'value') else str(alert.severity),
            "category": alert.category.value if hasattr(alert.category, 'value') else str(alert.category),
            "status": alert.status.value if hasattr(alert.status, 'value') else str(alert.status),
            "timestamp": alert.created_at.isoformat(),
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            "assignee": alert.assignee,
            "source": alert.source.name if alert.source else None
        }
        
    # ====================================================================
    # EXCHANGE ENDPOINTS
    # ====================================================================
    
    async def get_exchanges(self) -> Dict[str, Any]:
        """
        Get all exchanges.
        
        Returns:
            List of exchanges
        """
        if not self._exchange_manager:
            raise HTTPException(status_code=503, detail="Exchange manager not available")
            
        try:
            exchanges = await self._exchange_manager.get_exchanges()
            return {
                "exchanges": [self._format_exchange(e) for e in exchanges],
                "total": len(exchanges),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_exchange(self, exchange: str) -> Dict[str, Any]:
        """
        Get exchange details.
        
        Args:
            exchange: Exchange name
            
        Returns:
            Exchange details
        """
        if not self._exchange_manager:
            raise HTTPException(status_code=503, detail="Exchange manager not available")
            
        try:
            exchange_data = await self._exchange_manager.get_exchange(exchange)
            if not exchange_data:
                raise HTTPException(status_code=404, detail="Exchange not found")
                
            return self._format_exchange(exchange_data)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_exchange_health(self) -> Dict[str, Any]:
        """
        Get exchange health summary.
        
        Returns:
            Exchange health summary
        """
        if not self._exchange_manager:
            raise HTTPException(status_code=503, detail="Exchange manager not available")
            
        try:
            health = await self._exchange_manager.get_health_all()
            return {
                "exchanges": health,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    def _format_exchange(self, exchange: Any) -> Dict[str, Any]:
        """Format exchange for response."""
        return {
            "name": exchange.name if hasattr(exchange, 'name') else str(exchange),
            "status": exchange.status.value if hasattr(exchange, 'status') and hasattr(exchange.status, 'value') else str(getattr(exchange, 'status', 'unknown')),
            "connected": getattr(exchange, 'connected', False),
            "latency_ms": getattr(exchange, 'latency_ms', 0.0),
            "success_rate": getattr(exchange, 'success_rate', 100.0),
            "symbols": getattr(exchange, 'symbols', [])
        }
        
    # ====================================================================
    # PORTFOLIO ENDPOINTS
    # ====================================================================
    
    async def get_portfolio(self) -> Dict[str, Any]:
        """
        Get portfolio summary.
        
        Returns:
            Portfolio summary
        """
        if not self._portfolio_manager:
            raise HTTPException(status_code=503, detail="Portfolio manager not available")
            
        try:
            portfolio = await self._portfolio_manager.get_portfolio()
            return {
                "total_value": portfolio.total_value,
                "total_profit": portfolio.total_profit,
                "profit_percentage": portfolio.profit_percentage,
                "asset_count": len(portfolio.assets),
                "exchange_count": len(portfolio.exchanges),
                "allocation": portfolio.allocation,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_positions(self) -> Dict[str, Any]:
        """
        Get all positions.
        
        Returns:
            List of positions
        """
        if not self._position_manager:
            raise HTTPException(status_code=503, detail="Position manager not available")
            
        try:
            positions = await self._position_manager.get_positions()
            return {
                "positions": [self._format_position(p) for p in positions],
                "total": len(positions),
                "total_value": sum(p.current_value for p in positions),
                "total_pnl": sum(p.unrealized_pnl for p in positions),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_balances(self) -> Dict[str, Any]:
        """
        Get balances.
        
        Returns:
            Balance summary
        """
        if not self._balance_manager:
            raise HTTPException(status_code=503, detail="Balance manager not available")
            
        try:
            balances = await self._balance_manager.get_balances()
            return {
                "balances": [self._format_balance(b) for b in balances],
                "total_value": sum(b.usd_value for b in balances),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    def _format_position(self, position: Position) -> Dict[str, Any]:
        """Format position for response."""
        return {
            "symbol": position.symbol,
            "exchange": position.exchange,
            "side": position.side.value if hasattr(position.side, 'value') else str(position.side),
            "size": position.size,
            "entry_price": position.entry_price,
            "current_price": position.current_price,
            "unrealized_pnl": position.unrealized_pnl,
            "pnl_percentage": position.pnl_percentage,
            "leverage": position.leverage,
            "liquidation_price": position.liquidation_price
        }
        
    def _format_balance(self, balance: Balance) -> Dict[str, Any]:
        """Format balance for response."""
        return {
            "asset": balance.asset,
            "free": balance.free,
            "locked": balance.locked,
            "total": balance.total,
            "usd_value": balance.usd_value,
            "exchange": balance.exchange
        }
        
    # ====================================================================
    # PERFORMANCE ENDPOINTS
    # ====================================================================
    
    async def get_performance(
        self,
        period_days: int = 7,
        metric: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get performance metrics.
        
        Args:
            period_days: Analysis period in days
            metric: Specific metric to return
            
        Returns:
            Performance metrics
        """
        if not self._trade_manager:
            raise HTTPException(status_code=503, detail="Trade manager not available")
            
        try:
            performance = await self._trade_manager.get_performance(
                period_days=period_days,
                metric=metric
            )
            
            return {
                "period_start": performance.period_start.isoformat(),
                "period_end": performance.period_end.isoformat(),
                "metrics": performance.metrics if metric else performance,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_daily_performance(self, days: int = 7) -> Dict[str, Any]:
        """
        Get daily performance.
        
        Args:
            days: Number of days
            
        Returns:
            Daily performance
        """
        if not self._trade_manager:
            raise HTTPException(status_code=503, detail="Trade manager not available")
            
        try:
            daily = await self._trade_manager.get_daily_performance(days=days)
            return {
                "daily": daily,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_weekly_performance(self, weeks: int = 4) -> Dict[str, Any]:
        """
        Get weekly performance.
        
        Args:
            weeks: Number of weeks
            
        Returns:
            Weekly performance
        """
        if not self._trade_manager:
            raise HTTPException(status_code=503, detail="Trade manager not available")
            
        try:
            weekly = await self._trade_manager.get_weekly_performance(weeks=weeks)
            return {
                "weekly": weekly,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    async def get_monthly_performance(self, months: int = 6) -> Dict[str, Any]:
        """
        Get monthly performance.
        
        Args:
            months: Number of months
            
        Returns:
            Monthly performance
        """
        if not self._trade_manager:
            raise HTTPException(status_code=503, detail="Trade manager not available")
            
        try:
            monthly = await self._trade_manager.get_monthly_performance(months=months)
            return {
                "monthly": monthly,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
            
    # ====================================================================
    # WEBSOCKET ENDPOINT
    # ====================================================================
    
    async def websocket_endpoint(self, websocket: WebSocket) -> None:
        """
        WebSocket endpoint for real-time updates.
        
        Args:
            websocket: WebSocket connection
        """
        await websocket.accept()
        connection_id = str(time.time())
        
        # Track connection
        self._ws_connections[connection_id] = []
        self._ws_connections[connection_id].append(websocket)
        
        try:
            # Send initial data
            await self._send_websocket_update(websocket, "connected", {
                "message": "Connected to NEXUS Dashboard WebSocket",
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Handle messages
            while True:
                try:
                    message = await websocket.receive_text()
                    data = json.loads(message)
                    action = data.get("action")
                    
                    if action == "subscribe":
                        await self._handle_websocket_subscription(websocket, data)
                    elif action == "unsubscribe":
                        await self._handle_websocket_unsubscription(websocket, data)
                    elif action == "ping":
                        await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
                        
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except WebSocketDisconnect:
                    break
                    
        except WebSocketDisconnect:
            pass
        finally:
            # Remove connection
            if connection_id in self._ws_connections:
                self._ws_connections[connection_id].remove(websocket)
                if not self._ws_connections[connection_id]:
                    del self._ws_connections[connection_id]
                    
    async def _handle_websocket_subscription(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Handle WebSocket subscription."""
        subscription = data.get("subscription", "all")
        
        # Subscribe to updates
        if subscription == "trades":
            await self._start_trade_stream(websocket)
        elif subscription == "opportunities":
            await self._start_opportunity_stream(websocket)
        elif subscription == "alerts":
            await self._start_alert_stream(websocket)
        elif subscription == "metrics":
            await self._start_metric_stream(websocket)
        else:
            await self._start_full_stream(websocket)
            
    async def _handle_websocket_unsubscription(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Handle WebSocket unsubscription."""
        subscription = data.get("subscription", "all")
        # Stop sending updates for this subscription type
        # Implementation depends on streaming system
        
    async def _send_websocket_update(self, websocket: WebSocket, type: str, data: Any) -> None:
        """Send WebSocket update."""
        try:
            await websocket.send_json({
                "type": type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            logger.error(f"WebSocket send error: {e}")
            
    async def _start_trade_stream(self, websocket: WebSocket) -> None:
        """Start trade stream."""
        # Send initial trades
        if self._trade_manager:
            trades = await self._trade_manager.get_trades(limit=20)
            for trade in trades:
                await self._send_websocket_update(websocket, "trade", self._format_trade(trade))
                
    async def _start_opportunity_stream(self, websocket: WebSocket) -> None:
        """Start opportunity stream."""
        if self._opportunity_manager:
            opportunities = await self._opportunity_manager.get_opportunities(limit=20)
            for opp in opportunities:
                await self._send_websocket_update(websocket, "opportunity", self._format_opportunity(opp))
                
    async def _start_alert_stream(self, websocket: WebSocket) -> None:
        """Start alert stream."""
        if self._alert_manager:
            alerts = await self._alert_manager.get_alerts(limit=20)
            for alert in alerts:
                await self._send_websocket_update(websocket, "alert", self._format_alert(alert))
                
    async def _start_metric_stream(self, websocket: WebSocket) -> None:
        """Start metric stream."""
        # Send initial metrics
        metrics = self._metrics.get_metrics()
        await self._send_websocket_update(websocket, "metrics", metrics)
        
        # Send updates periodically
        while True:
            try:
                await asyncio.sleep(1)
                metrics = self._metrics.get_metrics()
                await self._send_websocket_update(websocket, "metrics", metrics)
            except Exception:
                break
                
    async def _start_full_stream(self, websocket: WebSocket) -> None:
        """Start full stream."""
        await self._start_trade_stream(websocket)
        await self._start_opportunity_stream(websocket)
        await self._start_alert_stream(websocket)
        await self._start_metric_stream(websocket)
        
    # ====================================================================
    # UTILITY METHODS
    # ====================================================================
    
    def _format_uptime(self, seconds: float) -> str:
        """Format uptime."""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m {secs}s"
        elif hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
            
    async def broadcast(self, type: str, data: Any) -> None:
        """
        Broadcast data to all WebSocket connections.
        
        Args:
            type: Message type
            data: Message data
        """
        for connections in self._ws_connections.values():
            for ws in connections:
                try:
                    await self._send_websocket_update(ws, type, data)
                except Exception:
                    pass
                    
    async def start(self) -> None:
        """Start the dashboard API."""
        self._running = True
        logger.info("Dashboard API started")
        
    async def stop(self) -> None:
        """Stop the dashboard API."""
        self._running = False
        
        # Close WebSocket connections
        for connections in self._ws_connections.values():
            for ws in connections:
                try:
                    await ws.close()
                except Exception:
                    pass
                    
        self._ws_connections.clear()
        logger.info("Dashboard API stopped")


# ====================================================================================
# GLOBAL INSTANCE
# ====================================================================================

_global_dashboard_api: Optional[DashboardAPI] = None


def get_dashboard_api() -> DashboardAPI:
    """
    Get the global dashboard API instance.
    
    Returns:
        DashboardAPI instance
    """
    global _global_dashboard_api
    if _global_dashboard_api is None:
        _global_dashboard_api = DashboardAPI()
    return _global_dashboard_api


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    'DashboardAPI',
    'get_dashboard_api',
]
