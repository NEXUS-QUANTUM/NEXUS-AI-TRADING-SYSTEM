"""
NEXUS AI TRADING SYSTEM - Portfolio Balance Tracker Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/portfolio/balance_tracker.py
Description: Advanced portfolio balance tracking with full API integration
"""

import asyncio
import logging
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.portfolio_config import PortfolioConfig
from shared.constants.trading_constants import ASSET_CLASSES
from shared.helpers.trading_helpers import (
    calculate_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_calmar_ratio
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.models import Position, Trade, PortfolioSnapshot
from backend.database.repositories.position_repository import PositionRepository
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.portfolio_repository import PortfolioRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class BalanceStatus(str, Enum):
    """Balance status"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    MARGIN_CALL = "margin_call"
    LIQUIDATION = "liquidation"


class BalanceMetricType(str, Enum):
    """Balance metric types"""
    EQUITY = "equity"
    CASH = "cash"
    MARGIN = "margin"
    LEVERAGE = "leverage"
    DRAW_DOWN = "draw_down"
    PNL = "pnl"
    UNREALIZED_PNL = "unrealized_pnl"
    REALIZED_PNL = "realized_pnl"
    UTILIZATION = "utilization"


class TimeFrame(str, Enum):
    """Time frames for balance history"""
    MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    HOUR = "1h"
    FOUR_HOURS = "4h"
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1m"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class BalanceRequest(BaseModel):
    """Request model for balance tracking"""
    portfolio_id: str
    include_unrealized: bool = True
    include_realized: bool = True
    include_margin: bool = True
    include_positions: bool = True
    include_history: bool = False
    history_days: int = 30
    time_frame: TimeFrame = TimeFrame.DAY


class BalanceResponse(BaseModel):
    """Response model for balance"""
    portfolio_id: str
    timestamp: datetime
    total_equity: float
    cash_balance: float
    margin_used: float
    margin_available: float
    margin_ratio: float
    leverage: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    drawdown: float
    utilization: float
    status: BalanceStatus
    positions_count: int
    positions_value: float
    metrics: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BalanceHistoryResponse(BaseModel):
    """Response model for balance history"""
    portfolio_id: str
    start_date: datetime
    end_date: datetime
    time_frame: TimeFrame
    history: List[Dict[str, Any]]
    summary: Dict[str, Any]
    metrics: Dict[str, Any]


class BalanceAlertRequest(BaseModel):
    """Request model for balance alerts"""
    portfolio_id: str
    alert_type: str
    threshold: float
    condition: str  # above, below, equals
    notification_channels: List[str] = ["email", "telegram"]
    enabled: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BalanceAlertResponse(BaseModel):
    """Response model for balance alerts"""
    alert_id: str
    portfolio_id: str
    alert_type: str
    threshold: float
    condition: str
    current_value: float
    triggered: bool
    triggered_at: Optional[datetime] = None
    notification_channels: List[str]
    enabled: bool
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class BalanceContext:
    """Context for balance calculations"""
    portfolio_id: str
    positions: List[Any]
    trades: List[Any]
    snapshots: List[Any]
    current_prices: Dict[str, float]
    cash_balance: float
    total_equity: float
    margin_used: float
    margin_available: float
    timestamp: datetime


@dataclass
class BalanceSnapshot:
    """Balance snapshot"""
    timestamp: datetime
    total_equity: float
    cash_balance: float
    margin_used: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    drawdown: float
    leverage: float
    positions_count: int
    positions_value: float


# =============================================================================
# BALANCE TRACKER
# =============================================================================

class BalanceTracker:
    """
    Advanced Portfolio Balance Tracker with full API integration.
    
    Features:
    - Real-time balance tracking
    - Equity calculation
    - Margin management
    - Leverage monitoring
    - PnL tracking
    - Drawdown analysis
    - Balance history
    - Alert system
    - Performance metrics
    """

    def __init__(
        self,
        config: Optional[PortfolioConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        position_repo: Optional[PositionRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        portfolio_repo: Optional[PortfolioRepository] = None
    ):
        """
        Initialize BalanceTracker.
        
        Args:
            config: Portfolio configuration
            broker_factory: Factory for broker instances
            position_repo: Position repository
            trade_repo: Trade repository
            portfolio_repo: Portfolio repository
        """
        self.config = config or PortfolioConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.position_repo = position_repo or PositionRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.portfolio_repo = portfolio_repo or PortfolioRepository()
        
        # Balance cache
        self._balance_cache: Dict[str, Dict[str, Any]] = {}
        self._balance_history: Dict[str, List[BalanceSnapshot]] = {}
        
        # Alerts
        self._alerts: Dict[str, List[BalanceAlertResponse]] = {}
        
        # Performance tracking
        self._performance_metrics: Dict[str, Dict[str, float]] = {}
        
        # Monitoring
        self._is_monitoring: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        logger.info("BalanceTracker initialized")

    # =========================================================================
    # Balance Tracking
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_balance(
        self,
        request: BalanceRequest
    ) -> BalanceResponse:
        """
        Get current portfolio balance.
        
        Args:
            request: Balance request
            
        Returns:
            BalanceResponse: Balance data
        """
        try:
            # Build context
            context = await self._build_context(request)
            
            # Calculate balances
            balance = await self._calculate_balances(context)
            
            # Calculate metrics
            metrics = await self._calculate_metrics(context, balance)
            
            # Determine status
            status = self._determine_status(balance, metrics)
            
            # Create response
            response = BalanceResponse(
                portfolio_id=request.portfolio_id,
                timestamp=datetime.utcnow(),
                total_equity=balance.total_equity,
                cash_balance=balance.cash_balance,
                margin_used=balance.margin_used,
                margin_available=balance.margin_available,
                margin_ratio=balance.margin_used / balance.total_equity if balance.total_equity > 0 else 0,
                leverage=balance.total_equity / balance.cash_balance if balance.cash_balance > 0 else 0,
                unrealized_pnl=balance.unrealized_pnl,
                realized_pnl=balance.realized_pnl,
                total_pnl=balance.total_pnl,
                drawdown=balance.drawdown,
                utilization=balance.margin_used / balance.total_equity if balance.total_equity > 0 else 0,
                status=status,
                positions_count=len(context.positions),
                positions_value=sum(p.size * p.entry_price for p in context.positions),
                metrics=metrics,
                metadata=request.metadata
            )
            
            # Cache balance
            self._balance_cache[request.portfolio_id] = {
                'response': response,
                'context': context,
                'timestamp': datetime.utcnow()
            }
            
            # Store snapshot
            self._store_snapshot(request.portfolio_id, balance)
            
            # Check alerts
            await self._check_alerts(request.portfolio_id, response)
            
            logger.info(f"Balance retrieved for {request.portfolio_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error getting balance: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Balance retrieval failed: {str(e)}"
            )

    async def _build_context(self, request: BalanceRequest) -> BalanceContext:
        """Build balance context"""
        # Get portfolio
        portfolio = await self.portfolio_repo.get_by_id(request.portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {request.portfolio_id} not found")
        
        # Get positions
        positions = await self.position_repo.get_by_portfolio_id(request.portfolio_id)
        
        # Get trades
        trades = await self.trade_repo.get_by_portfolio_id(request.portfolio_id)
        
        # Get snapshots
        snapshots = []
        if request.include_history:
            snapshots = await self.portfolio_repo.get_snapshots(
                request.portfolio_id,
                limit=request.history_days
            )
        
        # Get current prices
        current_prices = await self._get_current_prices(positions)
        
        # Calculate cash balance
        cash_balance = await self._calculate_cash_balance(portfolio, trades)
        
        # Calculate total equity
        total_equity = await self._calculate_total_equity(
            positions,
            current_prices,
            cash_balance
        )
        
        # Calculate margin
        margin_used = await self._calculate_margin_used(positions, current_prices)
        margin_available = total_equity - margin_used if total_equity > margin_used else 0
        
        return BalanceContext(
            portfolio_id=request.portfolio_id,
            positions=positions,
            trades=trades,
            snapshots=snapshots,
            current_prices=current_prices,
            cash_balance=cash_balance,
            total_equity=total_equity,
            margin_used=margin_used,
            margin_available=margin_available,
            timestamp=datetime.utcnow()
        )

    async def _get_current_prices(
        self,
        positions: List[Any]
    ) -> Dict[str, float]:
        """Get current prices for positions"""
        prices = {}
        
        for position in positions:
            symbol = position.symbol
            try:
                brokers = self.broker_factory.get_active_brokers()
                for broker in brokers:
                    try:
                        ticker = await broker.get_ticker(symbol)
                        prices[symbol] = float(ticker.get('price', 0))
                        break
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"Error getting price for {symbol}: {e}")
                # Use entry price as fallback
                prices[symbol] = float(position.entry_price)
        
        return prices

    async def _calculate_cash_balance(
        self,
        portfolio: Any,
        trades: List[Any]
    ) -> float:
        """Calculate cash balance"""
        # Start with initial capital
        cash = float(portfolio.initial_capital) if hasattr(portfolio, 'initial_capital') else 0
        
        # Add deposits, subtract withdrawals
        # (Implementation would get from transaction history)
        
        # Add realized PnL
        realized_pnl = 0
        for trade in trades:
            if hasattr(trade, 'pnl'):
                realized_pnl += float(trade.pnl)
        
        cash += realized_pnl
        
        # Subtract fees
        for trade in trades:
            if hasattr(trade, 'fee'):
                cash -= float(trade.fee)
        
        return cash

    async def _calculate_total_equity(
        self,
        positions: List[Any],
        prices: Dict[str, float],
        cash_balance: float
    ) -> float:
        """Calculate total equity"""
        # Position value
        position_value = 0
        for position in positions:
            price = prices.get(position.symbol, float(position.entry_price))
            position_value += float(position.size) * price
        
        return cash_balance + position_value

    async def _calculate_margin_used(
        self,
        positions: List[Any],
        prices: Dict[str, float]
    ) -> float:
        """Calculate margin used"""
        margin = 0
        
        for position in positions:
            price = prices.get(position.symbol, float(position.entry_price))
            value = float(position.size) * price
            
            # Different margin requirements per asset class
            margin_rate = self._get_margin_rate(position)
            margin += abs(value) * margin_rate
        
        return margin

    def _get_margin_rate(self, position: Any) -> float:
        """Get margin rate for position"""
        # Different rates for different assets
        asset_class = getattr(position, 'asset_class', 'equity')
        rates = {
            'equity': 0.50,  # 50% margin
            'crypto': 0.60,  # 60% margin
            'forex': 0.02,  # 2% margin
            'commodity': 0.10,  # 10% margin
            'fixed_income': 0.05  # 5% margin
        }
        return rates.get(asset_class, 0.50)

    # =========================================================================
    # Balance Calculations
    # =========================================================================

    async def _calculate_balances(
        self,
        context: BalanceContext
    ) -> BalanceSnapshot:
        """Calculate balance snapshot"""
        # Unrealized PnL
        unrealized_pnl = 0
        for position in context.positions:
            current_price = context.current_prices.get(
                position.symbol,
                float(position.entry_price)
            )
            pnl = (current_price - float(position.entry_price)) * float(position.size)
            unrealized_pnl += pnl
        
        # Realized PnL
        realized_pnl = 0
        for trade in context.trades:
            if hasattr(trade, 'pnl'):
                realized_pnl += float(trade.pnl)
        
        # Total PnL
        total_pnl = unrealized_pnl + realized_pnl
        
        # Drawdown
        drawdown = 0
        if context.snapshots:
            values = [float(s.total_value) for s in context.snapshots]
            values.append(context.total_equity)
            drawdown = calculate_drawdown(values)
        
        # Leverage
        leverage = context.total_equity / context.cash_balance if context.cash_balance > 0 else 0
        
        # Positions count and value
        positions_count = len(context.positions)
        positions_value = sum(float(p.size) * context.current_prices.get(p.symbol, float(p.entry_price)) 
                             for p in context.positions)
        
        return BalanceSnapshot(
            timestamp=datetime.utcnow(),
            total_equity=context.total_equity,
            cash_balance=context.cash_balance,
            margin_used=context.margin_used,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=realized_pnl,
            total_pnl=total_pnl,
            drawdown=drawdown,
            leverage=leverage,
            positions_count=positions_count,
            positions_value=positions_value
        )

    async def _calculate_metrics(
        self,
        context: BalanceContext,
        balance: BalanceSnapshot
    ) -> Dict[str, Any]:
        """Calculate additional metrics"""
        metrics = {}
        
        # Sharpe ratio
        if context.snapshots and len(context.snapshots) > 1:
            values = [float(s.total_value) for s in context.snapshots]
            returns = [(values[i] - values[i-1]) / values[i-1] 
                      for i in range(1, len(values))]
            metrics['sharpe_ratio'] = calculate_sharpe_ratio(returns)
            metrics['sortino_ratio'] = calculate_sortino_ratio(returns)
            metrics['calmar_ratio'] = calculate_calmar_ratio(returns, balance.drawdown)
        
        # Win rate
        if context.trades:
            winning_trades = [t for t in context.trades if float(t.pnl) > 0]
            metrics['win_rate'] = len(winning_trades) / len(context.trades) if context.trades else 0
        
        # Profit factor
        gross_profit = sum(float(t.pnl) for t in context.trades if float(t.pnl) > 0)
        gross_loss = abs(sum(float(t.pnl) for t in context.trades if float(t.pnl) < 0))
        metrics['profit_factor'] = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Average trade
        if context.trades:
            metrics['avg_trade_pnl'] = balance.total_pnl / len(context.trades) if context.trades else 0
        
        return metrics

    def _determine_status(
        self,
        balance: BalanceSnapshot,
        metrics: Dict[str, Any]
    ) -> BalanceStatus:
        """Determine balance status"""
        # Check margin call
        if balance.margin_used > balance.total_equity * 0.9:
            return BalanceStatus.MARGIN_CALL
        
        # Check liquidation
        if balance.margin_used > balance.total_equity:
            return BalanceStatus.LIQUIDATION
        
        # Check drawdown
        if balance.drawdown > 0.20:
            return BalanceStatus.CRITICAL
        
        # Check leverage
        if balance.leverage > 2.0:
            return BalanceStatus.WARNING
        
        return BalanceStatus.NORMAL

    def _store_snapshot(
        self,
        portfolio_id: str,
        snapshot: BalanceSnapshot
    ) -> None:
        """Store balance snapshot"""
        if portfolio_id not in self._balance_history:
            self._balance_history[portfolio_id] = []
        
        self._balance_history[portfolio_id].append(snapshot)
        
        # Keep history manageable
        if len(self._balance_history[portfolio_id]) > 10000:
            self._balance_history[portfolio_id] = self._balance_history[portfolio_id][-1000:]

    # =========================================================================
    # Balance History
    # =========================================================================

    async def get_balance_history(
        self,
        portfolio_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        time_frame: TimeFrame = TimeFrame.DAY,
        limit: int = 100
    ) -> BalanceHistoryResponse:
        """
        Get balance history.
        
        Args:
            portfolio_id: Portfolio ID
            start_date: Start date
            end_date: End date
            time_frame: Time frame
            limit: Maximum number of records
            
        Returns:
            BalanceHistoryResponse: Balance history
        """
        try:
            # Get snapshots from repository
            snapshots = await self.portfolio_repo.get_snapshots(
                portfolio_id,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )
            
            if not snapshots:
                # Use cached history
                snapshots = self._balance_history.get(portfolio_id, [])[-limit:]
            
            # Convert to dict
            history = []
            for snapshot in snapshots:
                if hasattr(snapshot, 'to_dict'):
                    history.append(snapshot.to_dict())
                elif isinstance(snapshot, BalanceSnapshot):
                    history.append(asdict(snapshot))
                else:
                    history.append({
                        'timestamp': snapshot.timestamp,
                        'total_equity': snapshot.total_value,
                        'cash_balance': snapshot.cash_balance,
                        'unrealized_pnl': snapshot.unrealized_pnl,
                        'drawdown': snapshot.drawdown
                    })
            
            # Calculate summary
            if history:
                summary = {
                    'start_equity': history[0].get('total_equity', 0),
                    'end_equity': history[-1].get('total_equity', 0),
                    'max_equity': max(h.get('total_equity', 0) for h in history),
                    'min_equity': min(h.get('total_equity', 0) for h in history),
                    'avg_equity': np.mean([h.get('total_equity', 0) for h in history]),
                    'total_change': history[-1].get('total_equity', 0) - history[0].get('total_equity', 0),
                    'total_change_pct': (history[-1].get('total_equity', 0) - history[0].get('total_equity', 0)) / history[0].get('total_equity', 1) * 100
                }
            else:
                summary = {}
            
            # Calculate metrics
            metrics = await self._calculate_history_metrics(history)
            
            return BalanceHistoryResponse(
                portfolio_id=portfolio_id,
                start_date=start_date or datetime.utcnow() - timedelta(days=30),
                end_date=end_date or datetime.utcnow(),
                time_frame=time_frame,
                history=history,
                summary=summary,
                metrics=metrics
            )
            
        except Exception as e:
            logger.error(f"Error getting balance history: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Balance history retrieval failed: {str(e)}"
            )

    async def _calculate_history_metrics(
        self,
        history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate metrics from history"""
        metrics = {}
        
        if not history:
            return metrics
        
        equity_values = [h.get('total_equity', 0) for h in history]
        
        # Volatility
        if len(equity_values) > 1:
            returns = [(equity_values[i] - equity_values[i-1]) / equity_values[i-1] 
                      for i in range(1, len(equity_values))]
            metrics['volatility'] = np.std(returns) * np.sqrt(252) if returns else 0
        
        # Max drawdown
        metrics['max_drawdown'] = 0
        peak = equity_values[0]
        for value in equity_values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            metrics['max_drawdown'] = max(metrics['max_drawdown'], drawdown)
        
        # Recovery factor
        if metrics['max_drawdown'] > 0:
            metrics['recovery_factor'] = (equity_values[-1] - equity_values[0]) / (metrics['max_drawdown'] * peak) if peak > 0 else 0
        
        return metrics

    # =========================================================================
    # Balance Alerts
    # =========================================================================

    async def create_alert(
        self,
        request: BalanceAlertRequest
    ) -> BalanceAlertResponse:
        """
        Create a balance alert.
        
        Args:
            request: Alert request
            
        Returns:
            BalanceAlertResponse: Created alert
        """
        try:
            # Get current balance
            balance_request = BalanceRequest(portfolio_id=request.portfolio_id)
            balance = await self.get_balance(balance_request)
            
            # Get current value
            current_value = self._get_metric_value(balance, request.alert_type)
            
            # Check if triggered
            triggered = self._check_condition(
                current_value,
                request.threshold,
                request.condition
            )
            
            alert = BalanceAlertResponse(
                alert_id=f"alert_{int(time.time() * 1000)}",
                portfolio_id=request.portfolio_id,
                alert_type=request.alert_type,
                threshold=request.threshold,
                condition=request.condition,
                current_value=current_value,
                triggered=triggered,
                triggered_at=datetime.utcnow() if triggered else None,
                notification_channels=request.notification_channels,
                enabled=request.enabled,
                metadata=request.metadata
            )
            
            # Store alert
            if request.portfolio_id not in self._alerts:
                self._alerts[request.portfolio_id] = []
            self._alerts[request.portfolio_id].append(alert)
            
            # Send notification if triggered
            if triggered:
                await self._send_alert_notification(alert)
            
            logger.info(f"Alert created for {request.portfolio_id}")
            return alert
            
        except Exception as e:
            logger.error(f"Error creating alert: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Alert creation failed: {str(e)}"
            )

    def _get_metric_value(
        self,
        balance: BalanceResponse,
        metric_type: str
    ) -> float:
        """Get metric value for alert"""
        mapping = {
            'equity': balance.total_equity,
            'cash': balance.cash_balance,
            'margin': balance.margin_used,
            'leverage': balance.leverage,
            'drawdown': balance.drawdown,
            'total_pnl': balance.total_pnl,
            'unrealized_pnl': balance.unrealized_pnl,
            'realized_pnl': balance.realized_pnl,
            'utilization': balance.utilization
        }
        return mapping.get(metric_type, 0)

    def _check_condition(
        self,
        current_value: float,
        threshold: float,
        condition: str
    ) -> bool:
        """Check alert condition"""
        if condition == "above":
            return current_value > threshold
        elif condition == "below":
            return current_value < threshold
        elif condition == "equals":
            return abs(current_value - threshold) < 0.0001
        return False

    async def _check_alerts(
        self,
        portfolio_id: str,
        balance: BalanceResponse
    ) -> None:
        """Check all alerts for portfolio"""
        if portfolio_id not in self._alerts:
            return
        
        for alert in self._alerts[portfolio_id]:
            if not alert.enabled:
                continue
            
            current_value = self._get_metric_value(balance, alert.alert_type)
            triggered = self._check_condition(
                current_value,
                alert.threshold,
                alert.condition
            )
            
            if triggered and not alert.triggered:
                alert.triggered = True
                alert.triggered_at = datetime.utcnow()
                alert.current_value = current_value
                await self._send_alert_notification(alert)

    async def _send_alert_notification(
        self,
        alert: BalanceAlertResponse
    ) -> None:
        """Send alert notification"""
        message = (
            f"⚠️ Balance Alert\n"
            f"Portfolio: {alert.portfolio_id}\n"
            f"Type: {alert.alert_type}\n"
            f"Current Value: {alert.current_value:.2f}\n"
            f"Threshold: {alert.threshold:.2f}\n"
            f"Condition: {alert.condition}\n"
            f"Time: {datetime.utcnow().isoformat()}"
        )
        
        for channel in alert.notification_channels:
            try:
                if channel == "email":
                    # Send email
                    pass
                elif channel == "telegram":
                    # Send Telegram
                    pass
                elif channel == "slack":
                    # Send Slack
                    pass
                elif channel == "webhook":
                    # Send webhook
                    pass
            except Exception as e:
                logger.error(f"Error sending notification via {channel}: {e}")

    async def get_alerts(
        self,
        portfolio_id: str
    ) -> List[BalanceAlertResponse]:
        """Get all alerts for portfolio"""
        return self._alerts.get(portfolio_id, [])

    async def update_alert(
        self,
        alert_id: str,
        updates: Dict[str, Any]
    ) -> Optional[BalanceAlertResponse]:
        """Update an alert"""
        for portfolio_alerts in self._alerts.values():
            for alert in portfolio_alerts:
                if alert.alert_id == alert_id:
                    for key, value in updates.items():
                        if hasattr(alert, key):
                            setattr(alert, key, value)
                    return alert
        return None

    async def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert"""
        for portfolio_id, alerts in self._alerts.items():
            for i, alert in enumerate(alerts):
                if alert.alert_id == alert_id:
                    alerts.pop(i)
                    return True
        return False

    # =========================================================================
    # Monitoring
    # =========================================================================

    async def start_monitoring(self) -> None:
        """Start balance monitoring"""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Balance monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop balance monitoring"""
        self._is_monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("Balance monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._is_monitoring:
            try:
                # Get all portfolios
                portfolios = await self.portfolio_repo.get_all()
                
                for portfolio in portfolios:
                    try:
                        request = BalanceRequest(portfolio_id=portfolio.id)
                        await self.get_balance(request)
                    except Exception as e:
                        logger.error(f"Error monitoring {portfolio.id}: {e}")
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(60)

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the balance tracker"""
        await self.stop_monitoring()
        self._balance_cache.clear()
        self._balance_history.clear()
        self._alerts.clear()
        self._performance_metrics.clear()
        logger.info("BalanceTracker closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/portfolio/balance", tags=["Portfolio Balance"])


async def get_tracker() -> BalanceTracker:
    """Dependency to get BalanceTracker instance"""
    return BalanceTracker()


@router.post("/", response_model=BalanceResponse)
async def get_balance(
    request: BalanceRequest,
    tracker: BalanceTracker = Depends(get_tracker)
):
    """Get portfolio balance"""
    return await tracker.get_balance(request)


@router.get("/{portfolio_id}/history")
async def get_balance_history(
    portfolio_id: str,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    time_frame: TimeFrame = Query(TimeFrame.DAY),
    limit: int = Query(100, le=1000),
    tracker: BalanceTracker = Depends(get_tracker)
):
    """Get balance history"""
    return await tracker.get_balance_history(
        portfolio_id,
        start_date,
        end_date,
        time_frame,
        limit
    )


@router.post("/alerts")
async def create_alert(
    request: BalanceAlertRequest,
    tracker: BalanceTracker = Depends(get_tracker)
):
    """Create a balance alert"""
    return await tracker.create_alert(request)


@router.get("/{portfolio_id}/alerts")
async def get_alerts(
    portfolio_id: str,
    tracker: BalanceTracker = Depends(get_tracker)
):
    """Get all alerts for portfolio"""
    return await tracker.get_alerts(portfolio_id)


@router.put("/alerts/{alert_id}")
async def update_alert(
    alert_id: str,
    updates: Dict[str, Any] = Body(..., embed=True),
    tracker: BalanceTracker = Depends(get_tracker)
):
    """Update an alert"""
    alert = await tracker.update_alert(alert_id, updates)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found"
        )
    return alert


@router.delete("/alerts/{alert_id}")
async def delete_alert(
    alert_id: str,
    tracker: BalanceTracker = Depends(get_tracker)
):
    """Delete an alert"""
    success = await tracker.delete_alert(alert_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found"
        )
    return {"success": True}


@router.post("/monitor/start")
async def start_monitoring(
    tracker: BalanceTracker = Depends(get_tracker)
):
    """Start balance monitoring"""
    await tracker.start_monitoring()
    return {"status": "started"}


@router.post("/monitor/stop")
async def stop_monitoring(
    tracker: BalanceTracker = Depends(get_tracker)
):
    """Stop balance monitoring"""
    await tracker.stop_monitoring()
    return {"status": "stopped"}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BalanceTracker',
    'BalanceStatus',
    'BalanceMetricType',
    'TimeFrame',
    'BalanceRequest',
    'BalanceResponse',
    'BalanceHistoryResponse',
    'BalanceAlertRequest',
    'BalanceAlertResponse',
    'BalanceContext',
    'BalanceSnapshot',
    'router'
]
