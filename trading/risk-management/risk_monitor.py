"""
NEXUS AI TRADING SYSTEM - Risk Monitor Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/risk-management/risk_monitor.py
Description: Real-time risk monitoring with full API integration
"""

import asyncio
import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status, WebSocket, WebSocketDisconnect

# NEXUS Internal Imports
from shared.configs.risk_config import RiskConfig
from shared.constants.trading_constants import (
    RISK_LEVELS,
    ORDER_TYPES,
    POSITION_DIRECTIONS,
    TIME_FRAMES
)
from shared.types.risk import (
    RiskMetrics,
    PortfolioRiskMetrics,
    RiskAlert,
    RiskEvent
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached
from shared.utilities.websocket_manager import WebSocketManager

# Database imports
from backend.database.models import (
    Position,
    Order,
    Trade,
    RiskAlert as RiskAlertModel,
    RiskEvent as RiskEventModel,
    SystemHealth
)
from backend.database.repositories.position_repository import PositionRepository
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.portfolio_repository import PortfolioRepository
from backend.database.repositories.risk_repository import RiskRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

# Risk management imports
from trading.risk_engine.risk_manager import RiskManager
from trading.risk_management.risk_limits import RiskLimitsManager
from trading.risk_management.portfolio_risk import PortfolioRiskManager
from trading.risk_management.position_sizer import PositionSizer

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class MonitorStatus(str, Enum):
    """Status of the risk monitor"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    DEGRADED = "degraded"


class AlertSeverity(str, Enum):
    """Severity levels for alerts"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertCategory(str, Enum):
    """Categories of alerts"""
    POSITION = "position"
    RISK = "risk"
    LIMIT = "limit"
    SYSTEM = "system"
    MARKET = "market"
    PERFORMANCE = "performance"
    SECURITY = "security"
    COMPLIANCE = "compliance"


class RiskEventType(str, Enum):
    """Types of risk events"""
    LIMIT_BREACH = "limit_breach"
    DRAWDOWN_WARNING = "drawdown_warning"
    VAR_EXCEEDED = "var_exceeded"
    LEVERAGE_WARNING = "leverage_warning"
    CONCENTRATION_WARNING = "concentration_warning"
    CORRELATION_WARNING = "correlation_warning"
    VOLATILITY_SPIKE = "volatility_spike"
    POSITION_LIQUIDATION = "position_liquidation"
    ORDER_REJECTED = "order_rejected"
    BROKER_ERROR = "broker_error"
    SYSTEM_ERROR = "system_error"
    MARKET_CRASH = "market_crash"
    GAP_RISK = "gap_risk"
    LIQUIDITY_RISK = "liquidity_risk"
    COUNTERPARTY_RISK = "counterparty_risk"
    REGULATORY_RISK = "regulatory_risk"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class RiskMonitorConfig(BaseModel):
    """Configuration for risk monitor"""
    enabled: bool = True
    check_interval_seconds: int = 5
    alert_cooldown_seconds: int = 60
    max_alerts_per_minute: int = 10
    enable_websocket: bool = True
    enable_dashboard: bool = True
    enable_audit_log: bool = True
    alert_channels: List[str] = ["email", "telegram", "slack", "webhook"]
    monitor_components: List[str] = [
        "positions",
        "orders",
        "portfolio",
        "market_data",
        "system_health",
        "performance"
    ]
    thresholds: Dict[str, float] = Field(default_factory=dict)
    notification_settings: Dict[str, Any] = Field(default_factory=dict)


class RiskAlertCreate(BaseModel):
    """Request model for creating an alert"""
    category: AlertCategory
    severity: AlertSeverity
    title: str
    message: str
    source: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskAlertResponse(BaseModel):
    """Response model for alerts"""
    id: str
    category: AlertCategory
    severity: AlertSeverity
    title: str
    message: str
    source: str
    timestamp: datetime
    acknowledged: bool
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved: bool
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskMonitorStatusResponse(BaseModel):
    """Response model for monitor status"""
    status: MonitorStatus
    started_at: datetime
    last_check: datetime
    checks_performed: int
    alerts_generated: int
    alerts_pending: int
    components_healthy: List[str]
    components_unhealthy: List[str]
    active_limits: int
    breached_limits: int
    warning_limits: int
    critical_limits: int
    uptime_seconds: float


class RiskMonitorSummaryResponse(BaseModel):
    """Summary response for risk monitor"""
    timestamp: datetime
    overall_health: str  # healthy, warning, critical
    risk_score: float
    total_exposure: float
    current_drawdown: float
    active_positions: int
    pending_orders: int
    recent_alerts: List[RiskAlertResponse]
    performance_summary: Dict[str, Any]
    system_status: Dict[str, Any]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MonitorCheck:
    """Record of a monitor check"""
    timestamp: datetime
    component: str
    status: str
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class RiskSnapshot:
    """Snapshot of risk metrics at a point in time"""
    timestamp: datetime
    portfolio_id: str
    total_value: float
    total_exposure: float
    drawdown: float
    var_95: float
    leverage: float
    concentration: float
    diversification: float
    risk_score: float
    position_count: int
    daily_pnl: float
    weekly_pnl: float
    monthly_pnl: float


@dataclass
class PerformanceMetric:
    """Performance metric for monitoring"""
    timestamp: datetime
    metric_name: str
    value: float
    threshold: float
    status: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# RISK MONITOR
# =============================================================================

class RiskMonitor:
    """
    Real-time Risk Monitor with full API integration.
    
    Continuously monitors:
    - Position risks
    - Portfolio risks
    - Limit breaches
    - Market conditions
    - System health
    - Performance metrics
    - Security events
    
    Features:
    - Real-time alerts
    - WebSocket streaming
    - Historical tracking
    - Automatic actions
    - Integration with all risk components
    """

    def __init__(
        self,
        config: Optional[RiskMonitorConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        risk_repo: Optional[RiskRepository] = None,
        position_repo: Optional[PositionRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        portfolio_repo: Optional[PortfolioRepository] = None
    ):
        """
        Initialize RiskMonitor.
        
        Args:
            config: Monitor configuration
            broker_factory: Factory for broker instances
            risk_repo: Risk repository
            position_repo: Position repository
            trade_repo: Trade repository
            portfolio_repo: Portfolio repository
        """
        self.config = config or RiskMonitorConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.risk_repo = risk_repo or RiskRepository()
        self.position_repo = position_repo or PositionRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.portfolio_repo = portfolio_repo or PortfolioRepository()
        
        # Risk components
        self.risk_limits = RiskLimitsManager()
        self.portfolio_risk = PortfolioRiskManager()
        self.position_sizer = PositionSizer()
        self.risk_manager = RiskManager()
        
        # Monitor state
        self._status = MonitorStatus.INITIALIZING
        self._started_at: Optional[datetime] = None
        self._last_check: Optional[datetime] = None
        self._check_count: int = 0
        self._alert_count: int = 0
        
        # Data structures
        self._checks: deque = deque(maxlen=10000)
        self._alerts: Dict[str, RiskAlertResponse] = {}
        self._snapshots: deque = deque(maxlen=1000)
        self._metrics: Dict[str, List[PerformanceMetric]] = {}
        self._events: deque = deque(maxlen=10000)
        
        # Monitoring loop
        self._is_running: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        # WebSocket manager
        self._ws_manager = WebSocketManager()
        
        # Callbacks
        self._alert_callbacks: List[Callable] = []
        self._event_callbacks: List[Callable] = []
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        logger.info("RiskMonitor initialized")

    # =========================================================================
    # Lifecycle Management
    # =========================================================================

    async def start(self) -> None:
        """Start the risk monitor"""
        if self._is_running:
            logger.warning("RiskMonitor already running")
            return
        
        self._status = MonitorStatus.RUNNING
        self._started_at = datetime.utcnow()
        self._is_running = True
        
        # Start monitoring loop
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        
        logger.info("RiskMonitor started")

    async def stop(self) -> None:
        """Stop the risk monitor"""
        self._is_running = False
        self._status = MonitorStatus.STOPPED
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        
        # Clean up WebSocket connections
        await self._ws_manager.close_all()
        
        logger.info("RiskMonitor stopped")

    async def pause(self) -> None:
        """Pause the risk monitor"""
        self._status = MonitorStatus.PAUSED
        logger.info("RiskMonitor paused")

    async def resume(self) -> None:
        """Resume the risk monitor"""
        self._status = MonitorStatus.RUNNING
        logger.info("RiskMonitor resumed")

    # =========================================================================
    # Main Monitoring Loop
    # =========================================================================

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._is_running:
            try:
                if self._status == MonitorStatus.PAUSED:
                    await asyncio.sleep(1)
                    continue
                
                start_time = time.time()
                
                # Run all monitor checks
                await self._run_checks()
                
                # Update status
                self._last_check = datetime.utcnow()
                self._check_count += 1
                
                # Calculate duration
                duration = (time.time() - start_time) * 1000
                
                # Record check
                self._checks.append(MonitorCheck(
                    timestamp=datetime.utcnow(),
                    component="monitor_loop",
                    status="success",
                    duration_ms=duration
                ))
                
                # Wait for next check
                await asyncio.sleep(self.config.check_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                self._status = MonitorStatus.ERROR
                await asyncio.sleep(5)

    async def _run_checks(self) -> None:
        """Run all monitor checks"""
        checks = []
        
        # Run component checks
        if "positions" in self.config.monitor_components:
            checks.append(self._check_positions())
        
        if "orders" in self.config.monitor_components:
            checks.append(self._check_orders())
        
        if "portfolio" in self.config.monitor_components:
            checks.append(self._check_portfolio())
        
        if "market_data" in self.config.monitor_components:
            checks.append(self._check_market_data())
        
        if "system_health" in self.config.monitor_components:
            checks.append(self._check_system_health())
        
        if "performance" in self.config.monitor_components:
            checks.append(self._check_performance())
        
        # Run all checks concurrently
        await asyncio.gather(*checks, return_exceptions=True)

    # =========================================================================
    # Component Checks
    # =========================================================================

    async def _check_positions(self) -> None:
        """Check all positions for risk issues"""
        try:
            positions = await self.position_repo.get_all_active()
            
            for position in positions:
                # Check position size limits
                await self._check_position_limits(position)
                
                # Check stop loss
                await self._check_stop_loss(position)
                
                # Check drawdown
                await self._check_position_drawdown(position)
                
                # Check liquidation risk
                await self._check_liquidation_risk(position)
                
        except Exception as e:
            logger.error(f"Error checking positions: {e}")

    async def _check_position_limits(self, position: Any) -> None:
        """Check position against limits"""
        # Get position value
        value = position.size * position.entry_price
        
        # Check max position value
        if value > self.config.thresholds.get('max_position_value', 10000):
            await self._create_alert(
                category=AlertCategory.POSITION,
                severity=AlertSeverity.HIGH,
                title=f"Large position detected: {position.symbol}",
                message=f"Position value {value:.2f} exceeds threshold",
                source="position_check",
                metadata={
                    'symbol': position.symbol,
                    'value': value,
                    'threshold': self.config.thresholds.get('max_position_value', 10000)
                }
            )

    async def _check_stop_loss(self, position: Any) -> None:
        """Check if stop loss is properly set"""
        if not position.stop_loss:
            await self._create_alert(
                category=AlertCategory.POSITION,
                severity=AlertSeverity.MEDIUM,
                title=f"Missing stop loss: {position.symbol}",
                message=f"Position {position.symbol} has no stop loss set",
                source="stop_loss_check",
                metadata={'symbol': position.symbol}
            )

    async def _check_position_drawdown(self, position: Any) -> None:
        """Check position drawdown"""
        if position.pnl and position.pnl < 0:
            drawdown = abs(position.pnl) / (position.size * position.entry_price)
            
            if drawdown > self.config.thresholds.get('max_position_drawdown', 0.05):
                await self._create_alert(
                    category=AlertCategory.POSITION,
                    severity=AlertSeverity.HIGH,
                    title=f"High drawdown: {position.symbol}",
                    message=f"Position drawdown {drawdown*100:.1f}% exceeds threshold",
                    source="drawdown_check",
                    metadata={
                        'symbol': position.symbol,
                        'drawdown': drawdown,
                        'threshold': self.config.thresholds.get('max_position_drawdown', 0.05)
                    }
                )

    async def _check_liquidation_risk(self, position: Any) -> None:
        """Check liquidation risk for leveraged positions"""
        if position.leverage and position.leverage > 1:
            # Calculate liquidation distance
            liquidation_price = position.liquidation_price if hasattr(position, 'liquidation_price') else None
            if liquidation_price:
                distance = abs(position.entry_price - liquidation_price) / position.entry_price
                
                if distance < self.config.thresholds.get('min_liquidation_distance', 0.05):
                    await self._create_alert(
                        category=AlertCategory.POSITION,
                        severity=AlertSeverity.CRITICAL,
                        title=f"Liquidation risk: {position.symbol}",
                        message=f"Position {position.symbol} is close to liquidation (distance: {distance*100:.1f}%)",
                        source="liquidation_check",
                        metadata={
                            'symbol': position.symbol,
                            'distance': distance,
                            'liquidation_price': liquidation_price,
                            'leverage': position.leverage
                        }
                    )

    async def _check_orders(self) -> None:
        """Check orders for issues"""
        try:
            orders = await self._get_pending_orders()
            
            for order in orders:
                # Check order size limits
                await self._check_order_limits(order)
                
                # Check stale orders
                await self._check_stale_orders(order)
                
        except Exception as e:
            logger.error(f"Error checking orders: {e}")

    async def _check_order_limits(self, order: Any) -> None:
        """Check order against size limits"""
        if order.size > self.config.thresholds.get('max_order_size', 1000):
            await self._create_alert(
                category=AlertCategory.LIMIT,
                severity=AlertSeverity.MEDIUM,
                title=f"Large order: {order.symbol}",
                message=f"Order size {order.size} exceeds threshold",
                source="order_check",
                metadata={
                    'symbol': order.symbol,
                    'size': order.size,
                    'threshold': self.config.thresholds.get('max_order_size', 1000)
                }
            )

    async def _check_stale_orders(self, order: Any) -> None:
        """Check for stale orders"""
        if order.created_at:
            age = (datetime.utcnow() - order.created_at).seconds / 60
            
            if age > self.config.thresholds.get('max_order_age_minutes', 60):
                await self._create_alert(
                    category=AlertCategory.SYSTEM,
                    severity=AlertSeverity.MEDIUM,
                    title=f"Stale order: {order.symbol}",
                    message=f"Order {order.id} has been pending for {age:.0f} minutes",
                    source="stale_order_check",
                    metadata={
                        'order_id': order.id,
                        'symbol': order.symbol,
                        'age_minutes': age
                    }
                )

    async def _check_portfolio(self) -> None:
        """Check portfolio risk metrics"""
        try:
            portfolios = await self.portfolio_repo.get_all()
            
            for portfolio in portfolios:
                # Get portfolio risk metrics
                metrics = await self.portfolio_risk.analyze_portfolio_risk(
                    portfolio.id
                )
                
                # Create snapshot
                snapshot = RiskSnapshot(
                    timestamp=datetime.utcnow(),
                    portfolio_id=portfolio.id,
                    total_value=metrics.total_value,
                    total_exposure=metrics.total_exposure,
                    drawdown=metrics.drawdown,
                    var_95=metrics.var_95,
                    leverage=metrics.leverage,
                    concentration=metrics.concentration,
                    diversification=metrics.diversification,
                    risk_score=metrics.risk_score,
                    position_count=metrics.position_count,
                    daily_pnl=metrics.daily_pnl,
                    weekly_pnl=metrics.weekly_pnl,
                    monthly_pnl=metrics.monthly_pnl
                )
                self._snapshots.append(snapshot)
                
                # Check drawdown threshold
                if metrics.drawdown > self.config.thresholds.get('max_portfolio_drawdown', 0.15):
                    await self._create_alert(
                        category=AlertCategory.RISK,
                        severity=AlertSeverity.CRITICAL,
                        title=f"High portfolio drawdown: {portfolio.id}",
                        message=f"Portfolio drawdown {metrics.drawdown*100:.1f}% exceeds threshold",
                        source="portfolio_check",
                        metadata={
                            'portfolio_id': portfolio.id,
                            'drawdown': metrics.drawdown,
                            'threshold': self.config.thresholds.get('max_portfolio_drawdown', 0.15)
                        }
                    )
                
                # Check VaR
                if metrics.var_95 > self.config.thresholds.get('max_var', 0.05):
                    await self._create_alert(
                        category=AlertCategory.RISK,
                        severity=AlertSeverity.HIGH,
                        title=f"High VaR: {portfolio.id}",
                        message=f"Portfolio VaR {metrics.var_95*100:.1f}% exceeds threshold",
                        source="var_check",
                        metadata={
                            'portfolio_id': portfolio.id,
                            'var': metrics.var_95,
                            'threshold': self.config.thresholds.get('max_var', 0.05)
                        }
                    )
                
                # Check concentration
                if metrics.concentration > self.config.thresholds.get('max_concentration', 0.40):
                    await self._create_alert(
                        category=AlertCategory.RISK,
                        severity=AlertSeverity.HIGH,
                        title=f"High concentration: {portfolio.id}",
                        message=f"Portfolio concentration {metrics.concentration*100:.1f}% exceeds threshold",
                        source="concentration_check",
                        metadata={
                            'portfolio_id': portfolio.id,
                            'concentration': metrics.concentration,
                            'threshold': self.config.thresholds.get('max_concentration', 0.40)
                        }
                    )
                
                # Check leverage
                if metrics.leverage > self.config.thresholds.get('max_leverage', 2.0):
                    await self._create_alert(
                        category=AlertCategory.RISK,
                        severity=AlertSeverity.HIGH,
                        title=f"High leverage: {portfolio.id}",
                        message=f"Portfolio leverage {metrics.leverage:.1f}x exceeds threshold",
                        source="leverage_check",
                        metadata={
                            'portfolio_id': portfolio.id,
                            'leverage': metrics.leverage,
                            'threshold': self.config.thresholds.get('max_leverage', 2.0)
                        }
                    )
                
        except Exception as e:
            logger.error(f"Error checking portfolio: {e}")

    async def _check_market_data(self) -> None:
        """Check market data for anomalies"""
        try:
            brokers = self.broker_factory.get_active_brokers()
            
            for broker in brokers:
                # Get market data
                market_data = await broker.get_market_data()
                
                # Check for extreme moves
                for symbol, data in market_data.items():
                    # Check volatility spike
                    volatility = data.get('volatility', 0)
                    if volatility > self.config.thresholds.get('max_volatility', 0.05):
                        await self._create_alert(
                            category=AlertCategory.MARKET,
                            severity=AlertSeverity.MEDIUM,
                            title=f"High volatility: {symbol}",
                            message=f"Volatility {volatility*100:.1f}% exceeds threshold",
                            source="volatility_check",
                            metadata={
                                'symbol': symbol,
                                'volatility': volatility,
                                'threshold': self.config.thresholds.get('max_volatility', 0.05)
                            }
                        )
                    
                    # Check price gap
                    price = data.get('price', 0)
                    open_price = data.get('open', price)
                    gap = abs(price - open_price) / open_price if open_price > 0 else 0
                    
                    if gap > self.config.thresholds.get('max_gap', 0.01):
                        await self._create_alert(
                            category=AlertCategory.MARKET,
                            severity=AlertSeverity.MEDIUM,
                            title=f"Price gap detected: {symbol}",
                            message=f"Price gap {gap*100:.1f}% exceeds threshold",
                            source="gap_check",
                            metadata={
                                'symbol': symbol,
                                'gap': gap,
                                'threshold': self.config.thresholds.get('max_gap', 0.01)
                            }
                        )
                
        except Exception as e:
            logger.error(f"Error checking market data: {e}")

    async def _check_system_health(self) -> None:
        """Check system health"""
        try:
            # Check database connectivity
            db_health = await self._check_database_health()
            
            # Check broker connectivity
            broker_health = await self._check_broker_health()
            
            # Check Redis connectivity
            redis_health = await self._check_redis_health()
            
            # Check task queue
            queue_health = await self._check_queue_health()
            
            # Aggregate health
            all_healthy = all([
                db_health['status'] == 'healthy',
                broker_health['status'] == 'healthy',
                redis_health['status'] == 'healthy',
                queue_health['status'] == 'healthy'
            ])
            
            if not all_healthy:
                unhealthy_components = []
                if db_health['status'] != 'healthy':
                    unhealthy_components.append('database')
                if broker_health['status'] != 'healthy':
                    unhealthy_components.append('broker')
                if redis_health['status'] != 'healthy':
                    unhealthy_components.append('redis')
                if queue_health['status'] != 'healthy':
                    unhealthy_components.append('queue')
                
                await self._create_alert(
                    category=AlertCategory.SYSTEM,
                    severity=AlertSeverity.CRITICAL,
                    title="System health degraded",
                    message=f"Unhealthy components: {', '.join(unhealthy_components)}",
                    source="health_check",
                    metadata={'unhealthy_components': unhealthy_components}
                )
                
        except Exception as e:
            logger.error(f"Error checking system health: {e}")

    async def _check_database_health(self) -> Dict[str, Any]:
        """Check database health"""
        try:
            # Simple health check
            await self.risk_repo.check_health()
            return {'status': 'healthy', 'message': 'Database is healthy'}
        except Exception as e:
            return {'status': 'unhealthy', 'message': str(e)}

    async def _check_broker_health(self) -> Dict[str, Any]:
        """Check broker health"""
        try:
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                await broker.check_health()
            return {'status': 'healthy', 'message': 'All brokers healthy'}
        except Exception as e:
            return {'status': 'unhealthy', 'message': str(e)}

    async def _check_redis_health(self) -> Dict[str, Any]:
        """Check Redis health"""
        try:
            # Simple health check
            await self._check_redis_connection()
            return {'status': 'healthy', 'message': 'Redis is healthy'}
        except Exception as e:
            return {'status': 'unhealthy', 'message': str(e)}

    async def _check_queue_health(self) -> Dict[str, Any]:
        """Check task queue health"""
        try:
            # Simple health check
            await self._check_queue_connection()
            return {'status': 'healthy', 'message': 'Queue is healthy'}
        except Exception as e:
            return {'status': 'unhealthy', 'message': str(e)}

    async def _check_performance(self) -> None:
        """Check performance metrics"""
        try:
            # Get performance metrics
            metrics = await self._get_performance_metrics()
            
            for metric_name, metric_value in metrics.items():
                # Check against threshold
                threshold = self.config.thresholds.get(f'performance_{metric_name}', 0)
                if threshold and metric_value > threshold:
                    await self._create_alert(
                        category=AlertCategory.PERFORMANCE,
                        severity=AlertSeverity.MEDIUM,
                        title=f"Performance alert: {metric_name}",
                        message=f"{metric_name} {metric_value:.2f} exceeds threshold {threshold:.2f}",
                        source="performance_check",
                        metadata={
                            'metric': metric_name,
                            'value': metric_value,
                            'threshold': threshold
                        }
                    )
                    
        except Exception as e:
            logger.error(f"Error checking performance: {e}")

    # =========================================================================
    # Alert Management
    # =========================================================================

    async def _create_alert(
        self,
        category: AlertCategory,
        severity: AlertSeverity,
        title: str,
        message: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Create and process a new alert.
        
        Args:
            category: Alert category
            severity: Alert severity
            title: Alert title
            message: Alert message
            source: Source of the alert
            metadata: Additional metadata
            
        Returns:
            Optional[str]: Alert ID if created
        """
        # Check cooldown for similar alerts
        alert_key = f"{category.value}:{source}:{title[:50]}"
        if alert_key in self._alert_cooldown:
            if (datetime.utcnow() - self._alert_cooldown[alert_key]).seconds < self.config.alert_cooldown_seconds:
                return None
        
        # Check rate limit
        if self._alert_count > self.config.max_alerts_per_minute:
            logger.warning("Alert rate limit exceeded")
            return None
        
        try:
            alert = RiskAlertResponse(
                id=f"alert_{int(time.time() * 1000)}_{self._alert_count}",
                category=category,
                severity=severity,
                title=title,
                message=message,
                source=source,
                timestamp=datetime.utcnow(),
                acknowledged=False,
                resolved=False,
                metadata=metadata or {}
            )
            
            # Store alert
            self._alerts[alert.id] = alert
            self._alert_count += 1
            
            # Set cooldown
            self._alert_cooldown[alert_key] = datetime.utcnow()
            
            # Save to database
            await self._save_alert_to_db(alert)
            
            # Send notifications
            await self._send_alert_notifications(alert)
            
            # Broadcast via WebSocket
            await self._broadcast_alert(alert)
            
            # Execute callbacks
            for callback in self._alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")
            
            logger.info(f"Alert created: {severity.value} - {title}")
            return alert.id
            
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            return None

    async def _save_alert_to_db(self, alert: RiskAlertResponse) -> None:
        """Save alert to database"""
        try:
            await self.risk_repo.save_alert({
                'id': alert.id,
                'category': alert.category.value,
                'severity': alert.severity.value,
                'title': alert.title,
                'message': alert.message,
                'source': alert.source,
                'timestamp': alert.timestamp,
                'acknowledged': alert.acknowledged,
                'resolved': alert.resolved,
                'metadata': alert.metadata
            })
        except Exception as e:
            logger.error(f"Error saving alert to database: {e}")

    async def _send_alert_notifications(self, alert: RiskAlertResponse) -> None:
        """Send alert notifications via configured channels"""
        # Skip low severity alerts unless configured
        if alert.severity == AlertSeverity.INFO or alert.severity == AlertSeverity.LOW:
            if not self.config.thresholds.get('notify_low_severity', False):
                return
        
        for channel in self.config.alert_channels:
            try:
                if channel == "email":
                    await self._send_email_alert(alert)
                elif channel == "telegram":
                    await self._send_telegram_alert(alert)
                elif channel == "slack":
                    await self._send_slack_alert(alert)
                elif channel == "webhook":
                    await self._send_webhook_alert(alert)
            except Exception as e:
                logger.error(f"Error sending alert via {channel}: {e}")

    async def _send_email_alert(self, alert: RiskAlertResponse) -> None:
        """Send alert via email"""
        # Implementation would use email service
        pass

    async def _send_telegram_alert(self, alert: RiskAlertResponse) -> None:
        """Send alert via Telegram"""
        # Implementation would use Telegram service
        pass

    async def _send_slack_alert(self, alert: RiskAlertResponse) -> None:
        """Send alert via Slack"""
        # Implementation would use Slack service
        pass

    async def _send_webhook_alert(self, alert: RiskAlertResponse) -> None:
        """Send alert via webhook"""
        # Implementation would use webhook service
        pass

    async def _broadcast_alert(self, alert: RiskAlertResponse) -> None:
        """Broadcast alert via WebSocket"""
        if self.config.enable_websocket:
            await self._ws_manager.broadcast(
                'risk_alert',
                alert.dict()
            )

    async def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str
    ) -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: Alert ID
            acknowledged_by: Who acknowledged the alert
            
        Returns:
            bool: Success indicator
        """
        if alert_id not in self._alerts:
            return False
        
        alert = self._alerts[alert_id]
        alert.acknowledged = True
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.utcnow()
        
        # Update in database
        await self._update_alert_in_db(alert)
        
        logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
        return True

    async def resolve_alert(self, alert_id: str) -> bool:
        """
        Resolve an alert.
        
        Args:
            alert_id: Alert ID
            
        Returns:
            bool: Success indicator
        """
        if alert_id not in self._alerts:
            return False
        
        alert = self._alerts[alert_id]
        alert.resolved = True
        alert.resolved_at = datetime.utcnow()
        
        # Update in database
        await self._update_alert_in_db(alert)
        
        logger.info(f"Alert {alert_id} resolved")
        return True

    async def _update_alert_in_db(self, alert: RiskAlertResponse) -> None:
        """Update alert in database"""
        try:
            await self.risk_repo.update_alert({
                'id': alert.id,
                'acknowledged': alert.acknowledged,
                'acknowledged_by': alert.acknowledged_by,
                'acknowledged_at': alert.acknowledged_at,
                'resolved': alert.resolved,
                'resolved_at': alert.resolved_at
            })
        except Exception as e:
            logger.error(f"Error updating alert in database: {e}")

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _get_pending_orders(self) -> List[Any]:
        """Get pending orders"""
        # Implementation would get from order repository
        return []

    async def _get_performance_metrics(self) -> Dict[str, float]:
        """Get performance metrics"""
        return {
            'sharpe_ratio': 0.5,
            'sortino_ratio': 0.4,
            'calmar_ratio': 0.3,
            'win_rate': 0.55,
            'profit_factor': 1.2,
            'avg_return': 0.01,
            'std_dev': 0.02
        }

    async def _check_redis_connection(self) -> None:
        """Check Redis connection"""
        # Implementation would check Redis
        pass

    async def _check_queue_connection(self) -> None:
        """Check task queue connection"""
        # Implementation would check queue
        pass

    # =========================================================================
    # Public API Methods
    # =========================================================================

    async def get_alerts(
        self,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get alerts with optional filters.
        
        Args:
            category: Filter by category
            severity: Filter by severity
            resolved: Filter by resolved status
            limit: Maximum number of alerts
            
        Returns:
            List[Dict]: List of alerts
        """
        alerts = list(self._alerts.values())
        
        if category:
            alerts = [a for a in alerts if a.category.value == category]
        
        if severity:
            alerts = [a for a in alerts if a.severity.value == severity]
        
        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]
        
        # Sort by timestamp (newest first)
        alerts.sort(key=lambda a: a.timestamp, reverse=True)
        
        return [a.dict() for a in alerts[:limit]]

    async def get_snapshots(
        self,
        portfolio_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get risk snapshots.
        
        Args:
            portfolio_id: Filter by portfolio ID
            limit: Maximum number of snapshots
            
        Returns:
            List[Dict]: List of snapshots
        """
        snapshots = list(self._snapshots)
        
        if portfolio_id:
            snapshots = [s for s in snapshots if s.portfolio_id == portfolio_id]
        
        # Sort by timestamp (newest first)
        snapshots.sort(key=lambda s: s.timestamp, reverse=True)
        
        return [s.__dict__ for s in snapshots[:limit]]

    async def get_events(
        self,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get risk events.
        
        Args:
            event_type: Filter by event type
            limit: Maximum number of events
            
        Returns:
            List[Dict]: List of events
        """
        events = list(self._events)
        
        if event_type:
            events = [e for e in events if e.get('type') == event_type]
        
        # Sort by timestamp (newest first)
        events.sort(key=lambda e: e.get('timestamp', datetime.min), reverse=True)
        
        return events[:limit]

    async def get_status(self) -> RiskMonitorStatusResponse:
        """
        Get current monitor status.
        
        Returns:
            RiskMonitorStatusResponse: Monitor status
        """
        # Calculate uptime
        uptime = 0
        if self._started_at:
            uptime = (datetime.utcnow() - self._started_at).total_seconds()
        
        # Get limit status
        limit_status = await self.risk_limits.get_all_limits_status()
        
        return RiskMonitorStatusResponse(
            status=self._status,
            started_at=self._started_at or datetime.utcnow(),
            last_check=self._last_check or datetime.utcnow(),
            checks_performed=self._check_count,
            alerts_generated=self._alert_count,
            alerts_pending=len([a for a in self._alerts.values() if not a.resolved]),
            components_healthy=['monitor'],
            components_unhealthy=[],
            active_limits=limit_status.total_limits,
            breached_limits=len(limit_status.breached_limits),
            warning_limits=len(limit_status.warning_limits),
            critical_limits=len(limit_status.critical_limits),
            uptime_seconds=uptime
        )

    async def get_summary(self) -> RiskMonitorSummaryResponse:
        """
        Get summary of risk monitor.
        
        Returns:
            RiskMonitorSummaryResponse: Monitor summary
        """
        # Get latest snapshot
        latest_snapshot = self._snapshots[-1] if self._snapshots else None
        
        # Get recent alerts
        recent_alerts = list(self._alerts.values())[-10:]
        
        # Calculate overall health
        health = "healthy"
        if self._status == MonitorStatus.ERROR:
            health = "critical"
        elif self._status == MonitorStatus.DEGRADED:
            health = "warning"
        
        return RiskMonitorSummaryResponse(
            timestamp=datetime.utcnow(),
            overall_health=health,
            risk_score=latest_snapshot.risk_score if latest_snapshot else 0.0,
            total_exposure=latest_snapshot.total_exposure if latest_snapshot else 0.0,
            current_drawdown=latest_snapshot.drawdown if latest_snapshot else 0.0,
            active_positions=latest_snapshot.position_count if latest_snapshot else 0,
            pending_orders=0,  # Would be fetched from order repository
            recent_alerts=[self._alert_to_response(a) for a in recent_alerts],
            performance_summary={},  # Would be calculated
            system_status={}  # Would be collected from system
        )

    def _alert_to_response(self, alert: RiskAlertResponse) -> RiskAlertResponse:
        """Convert alert to response format"""
        return alert

    # =========================================================================
    # WebSocket Support
    # =========================================================================

    async def handle_websocket(self, websocket: WebSocket) -> None:
        """
        Handle WebSocket connections for real-time monitoring.
        
        Args:
            websocket: WebSocket connection
        """
        await self._ws_manager.connect(websocket)
        
        try:
            # Send initial status
            await self._ws_manager.send_json({
                'type': 'status',
                'data': (await self.get_status()).dict()
            })
            
            # Send recent alerts
            recent_alerts = await self.get_alerts(limit=20)
            await self._ws_manager.send_json({
                'type': 'alerts',
                'data': recent_alerts
            })
            
            # Keep connection alive
            while True:
                # Wait for messages
                try:
                    data = await websocket.receive_text()
                    if data == 'ping':
                        await websocket.send_text('pong')
                except WebSocketDisconnect:
                    break
                
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            await self._ws_manager.disconnect(websocket)

    # =========================================================================
    # Callback Management
    # =========================================================================

    def add_alert_callback(self, callback: Callable) -> None:
        """Add a callback for alerts"""
        self._alert_callbacks.append(callback)

    def remove_alert_callback(self, callback: Callable) -> None:
        """Remove a callback"""
        if callback in self._alert_callbacks:
            self._alert_callbacks.remove(callback)

    def add_event_callback(self, callback: Callable) -> None:
        """Add a callback for events"""
        self._event_callbacks.append(callback)

    def remove_event_callback(self, callback: Callable) -> None:
        """Remove a callback"""
        if callback in self._event_callbacks:
            self._event_callbacks.remove(callback)

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the risk monitor"""
        await self.stop()
        
        # Close all components
        await self.risk_limits.close()
        await self.portfolio_risk.close()
        await self.position_sizer.close()
        
        # Clean up executor
        self._executor.shutdown(wait=True)
        
        logger.info("RiskMonitor closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/v1/risk-monitor", tags=["Risk Monitor"])


async def get_monitor() -> RiskMonitor:
    """Dependency to get RiskMonitor instance"""
    # In production, use dependency injection
    return RiskMonitor()


@router.post("/start")
async def start_monitor(
    monitor: RiskMonitor = Depends(get_monitor)
):
    """Start the risk monitor"""
    await monitor.start()
    return {"status": "started"}


@router.post("/stop")
async def stop_monitor(
    monitor: RiskMonitor = Depends(get_monitor)
):
    """Stop the risk monitor"""
    await monitor.stop()
    return {"status": "stopped"}


@router.post("/pause")
async def pause_monitor(
    monitor: RiskMonitor = Depends(get_monitor)
):
    """Pause the risk monitor"""
    await monitor.pause()
    return {"status": "paused"}


@router.post("/resume")
async def resume_monitor(
    monitor: RiskMonitor = Depends(get_monitor)
):
    """Resume the risk monitor"""
    await monitor.resume()
    return {"status": "resumed"}


@router.get("/status", response_model=RiskMonitorStatusResponse)
async def get_monitor_status(
    monitor: RiskMonitor = Depends(get_monitor)
):
    """Get current monitor status"""
    return await monitor.get_status()


@router.get("/summary", response_model=RiskMonitorSummaryResponse)
async def get_monitor_summary(
    monitor: RiskMonitor = Depends(get_monitor)
):
    """Get monitor summary"""
    return await monitor.get_summary()


@router.get("/alerts")
async def get_alerts(
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    resolved: Optional[bool] = Query(None),
    limit: int = Query(100, le=1000),
    monitor: RiskMonitor = Depends(get_monitor)
):
    """Get alerts with filters"""
    return await monitor.get_alerts(category, severity, resolved, limit)


@router.get("/snapshots")
async def get_snapshots(
    portfolio_id: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    monitor: RiskMonitor = Depends(get_monitor)
):
    """Get risk snapshots"""
    return await monitor.get_snapshots(portfolio_id, limit)


@router.get("/events")
async def get_events(
    event_type: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    monitor: RiskMonitor = Depends(get_monitor)
):
    """Get risk events"""
    return await monitor.get_events(event_type, limit)


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str = Query(..., min_length=1),
    monitor: RiskMonitor = Depends(get_monitor)
):
    """Acknowledge an alert"""
    success = await monitor.acknowledge_alert(alert_id, acknowledged_by)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found"
        )
    return {"success": True}


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    monitor: RiskMonitor = Depends(get_monitor)
):
    """Resolve an alert"""
    success = await monitor.resolve_alert(alert_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found"
        )
    return {"success": True}


@router.websocket("/ws")
async def risk_monitor_websocket(
    websocket: WebSocket,
    monitor: RiskMonitor = Depends(get_monitor)
):
    """WebSocket endpoint for real-time risk monitoring"""
    await monitor.handle_websocket(websocket)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'RiskMonitor',
    'MonitorStatus',
    'AlertSeverity',
    'AlertCategory',
    'RiskEventType',
    'RiskMonitorConfig',
    'RiskAlertCreate',
    'RiskAlertResponse',
    'RiskMonitorStatusResponse',
    'RiskMonitorSummaryResponse',
    'MonitorCheck',
    'RiskSnapshot',
    'PerformanceMetric',
    'router'
]
