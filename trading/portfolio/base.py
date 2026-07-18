"""
NEXUS AI TRADING SYSTEM - Portfolio Base Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/portfolio/base.py
Description: Base portfolio management classes with full API integration
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
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
from shared.constants.trading_constants import (
    ORDER_TYPES,
    POSITION_DIRECTIONS,
    ASSET_CLASSES
)
from shared.helpers.trading_helpers import (
    calculate_position_size,
    calculate_risk_reward_ratio,
    calculate_drawdown
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.models import Position, Order, Trade
from backend.database.repositories.position_repository import PositionRepository
from backend.database.repositories.order_repository import OrderRepository
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.portfolio_repository import PortfolioRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class PortfolioStatus(str, Enum):
    """Portfolio operational status"""
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    DEGRADED = "degraded"


class PortfolioType(str, Enum):
    """Portfolio types"""
    STANDARD = "standard"
    ISOLATED = "isolated"
    CROSS_MARGIN = "cross_margin"
    PAPER = "paper"
    FUND = "fund"


class PortfolioRiskLevel(str, Enum):
    """Portfolio risk levels"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    VERY_AGGRESSIVE = "very_aggressive"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class PortfolioCreateRequest(BaseModel):
    """Request model for portfolio creation"""
    name: str
    type: PortfolioType = PortfolioType.STANDARD
    initial_capital: float = 10000.0
    currency: str = "USD"
    risk_level: PortfolioRiskLevel = PortfolioRiskLevel.MODERATE
    risk_per_trade: float = 0.02
    max_drawdown: float = 0.20
    max_position_pct: float = 0.10
    max_leverage: float = 2.0
    allowed_assets: List[str] = []
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('initial_capital')
    def validate_capital(cls, v):
        if v <= 0:
            raise ValueError("Initial capital must be positive")
        return v

    @validator('risk_per_trade')
    def validate_risk(cls, v):
        if not 0 < v <= 0.10:
            raise ValueError("Risk per trade must be between 0 and 10%")
        return v


class PortfolioResponse(BaseModel):
    """Response model for portfolio"""
    portfolio_id: str
    name: str
    type: PortfolioType
    status: PortfolioStatus
    initial_capital: float
    current_capital: float
    total_equity: float
    total_pnl: float
    total_pnl_pct: float
    risk_level: PortfolioRiskLevel
    risk_per_trade: float
    max_drawdown: float
    max_position_pct: float
    max_leverage: float
    positions_count: int
    orders_count: int
    trades_count: int
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PortfolioUpdateRequest(BaseModel):
    """Request model for portfolio update"""
    name: Optional[str] = None
    risk_level: Optional[PortfolioRiskLevel] = None
    risk_per_trade: Optional[float] = None
    max_drawdown: Optional[float] = None
    max_position_pct: Optional[float] = None
    max_leverage: Optional[float] = None
    allowed_assets: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PortfolioState:
    """Portfolio state"""
    portfolio_id: str
    status: PortfolioStatus
    capital: float
    equity: float
    positions: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]
    trades: List[Dict[str, Any]]
    pnl: float
    drawdown: float
    leverage: float
    timestamp: datetime


@dataclass
class PortfolioMetrics:
    """Portfolio metrics"""
    total_pnl: float
    total_pnl_pct: float
    daily_pnl: float
    weekly_pnl: float
    monthly_pnl: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    current_drawdown: float
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    total_trades: int
    winning_trades: int
    losing_trades: int


@dataclass
class PositionInfo:
    """Position information"""
    symbol: str
    size: float
    entry_price: float
    current_price: float
    pnl: float
    pnl_pct: float
    value: float
    leverage: float
    margin_used: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    entry_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# BASE PORTFOLIO MANAGER
# =============================================================================

class BasePortfolioManager(ABC):
    """
    Base Portfolio Manager for NEXUS AI Trading System.
    
    Provides core portfolio management functionality:
    - Portfolio creation and management
    - Position management
    - Risk management
    - Performance tracking
    - Capital allocation
    - Risk limit enforcement
    """

    def __init__(
        self,
        portfolio_id: str,
        config: Optional[PortfolioConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        position_repo: Optional[PositionRepository] = None,
        order_repo: Optional[OrderRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        portfolio_repo: Optional[PortfolioRepository] = None
    ):
        """
        Initialize BasePortfolioManager.
        
        Args:
            portfolio_id: Portfolio ID
            config: Portfolio configuration
            broker_factory: Factory for broker instances
            position_repo: Position repository
            order_repo: Order repository
            trade_repo: Trade repository
            portfolio_repo: Portfolio repository
        """
        self.portfolio_id = portfolio_id
        self.config = config or PortfolioConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.position_repo = position_repo or PositionRepository()
        self.order_repo = order_repo or OrderRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.portfolio_repo = portfolio_repo or PortfolioRepository()
        
        # Portfolio state
        self._state: Optional[PortfolioState] = None
        self._metrics: Optional[PortfolioMetrics] = None
        
        # Risk limits
        self._risk_limits = {
            'max_position_size': 0.10,
            'max_drawdown': 0.20,
            'max_leverage': 2.0,
            'risk_per_trade': 0.02
        }
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Monitoring
        self._is_monitoring: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Load portfolio
        self._load_portfolio()
        
        logger.info(f"BasePortfolioManager initialized for {portfolio_id}")

    def _load_portfolio(self) -> None:
        """Load portfolio data"""
        try:
            portfolio = self.portfolio_repo.get_by_id(self.portfolio_id)
            if portfolio:
                # Initialize state
                self._state = PortfolioState(
                    portfolio_id=self.portfolio_id,
                    status=PortfolioStatus.ACTIVE,
                    capital=float(portfolio.current_capital),
                    equity=float(portfolio.total_equity),
                    positions=[],
                    orders=[],
                    trades=[],
                    pnl=float(portfolio.total_pnl),
                    drawdown=0.0,
                    leverage=1.0,
                    timestamp=datetime.utcnow()
                )
                
                # Load positions
                positions = self.position_repo.get_by_portfolio_id(self.portfolio_id)
                self._state.positions = [p.__dict__ for p in positions]
                
                # Load orders
                orders = self.order_repo.get_by_portfolio_id(self.portfolio_id)
                self._state.orders = [o.__dict__ for o in orders]
                
                # Load trades
                trades = self.trade_repo.get_by_portfolio_id(self.portfolio_id)
                self._state.trades = [t.__dict__ for t in trades]
                
                logger.info(f"Portfolio {self.portfolio_id} loaded successfully")
            else:
                logger.warning(f"Portfolio {self.portfolio_id} not found")
        except Exception as e:
            logger.error(f"Error loading portfolio: {e}")

    # =========================================================================
    # Portfolio Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def create_portfolio(
        self,
        request: PortfolioCreateRequest
    ) -> PortfolioResponse:
        """
        Create a new portfolio.
        
        Args:
            request: Portfolio creation request
            
        Returns:
            PortfolioResponse: Created portfolio
        """
        try:
            # Validate request
            await self._validate_create_request(request)
            
            # Create portfolio
            portfolio_data = {
                'name': request.name,
                'type': request.type.value,
                'initial_capital': request.initial_capital,
                'current_capital': request.initial_capital,
                'total_equity': request.initial_capital,
                'total_pnl': 0,
                'total_pnl_pct': 0,
                'risk_level': request.risk_level.value,
                'risk_per_trade': request.risk_per_trade,
                'max_drawdown': request.max_drawdown,
                'max_position_pct': request.max_position_pct,
                'max_leverage': request.max_leverage,
                'allowed_assets': request.allowed_assets,
                'status': PortfolioStatus.ACTIVE.value,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'metadata': request.metadata
            }
            
            portfolio = await self.portfolio_repo.create(portfolio_data)
            
            # Initialize state
            self._state = PortfolioState(
                portfolio_id=portfolio.id,
                status=PortfolioStatus.ACTIVE,
                capital=float(portfolio.current_capital),
                equity=float(portfolio.total_equity),
                positions=[],
                orders=[],
                trades=[],
                pnl=0,
                drawdown=0,
                leverage=1.0,
                timestamp=datetime.utcnow()
            )
            
            logger.info(f"Portfolio {portfolio.id} created successfully")
            return self._to_response(portfolio)
            
        except Exception as e:
            logger.error(f"Error creating portfolio: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Portfolio creation failed: {str(e)}"
            )

    async def _validate_create_request(
        self,
        request: PortfolioCreateRequest
    ) -> None:
        """Validate portfolio creation request"""
        # Check name uniqueness
        existing = await self.portfolio_repo.get_by_name(request.name)
        if existing:
            raise ValueError(f"Portfolio name '{request.name}' already exists")
        
        # Validate risk parameters
        if request.risk_per_trade > request.max_drawdown:
            raise ValueError("Risk per trade cannot exceed max drawdown")
        
        if request.max_position_pct > 1.0:
            raise ValueError("Max position percentage must be less than 100%")

    def _to_response(self, portfolio: Any) -> PortfolioResponse:
        """Convert portfolio to response"""
        return PortfolioResponse(
            portfolio_id=portfolio.id,
            name=portfolio.name,
            type=PortfolioType(portfolio.type),
            status=PortfolioStatus(portfolio.status),
            initial_capital=float(portfolio.initial_capital),
            current_capital=float(portfolio.current_capital),
            total_equity=float(portfolio.total_equity),
            total_pnl=float(portfolio.total_pnl),
            total_pnl_pct=float(portfolio.total_pnl_pct),
            risk_level=PortfolioRiskLevel(portfolio.risk_level),
            risk_per_trade=float(portfolio.risk_per_trade),
            max_drawdown=float(portfolio.max_drawdown),
            max_position_pct=float(portfolio.max_position_pct),
            max_leverage=float(portfolio.max_leverage),
            positions_count=len(self._state.positions) if self._state else 0,
            orders_count=len(self._state.orders) if self._state else 0,
            trades_count=len(self._state.trades) if self._state else 0,
            created_at=portfolio.created_at,
            updated_at=portfolio.updated_at,
            metadata=portfolio.metadata
        )

    async def update_portfolio(
        self,
        request: PortfolioUpdateRequest
    ) -> PortfolioResponse:
        """
        Update portfolio parameters.
        
        Args:
            request: Portfolio update request
            
        Returns:
            PortfolioResponse: Updated portfolio
        """
        try:
            portfolio = await self.portfolio_repo.get_by_id(self.portfolio_id)
            if not portfolio:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Portfolio {self.portfolio_id} not found"
                )
            
            # Update fields
            if request.name is not None:
                portfolio.name = request.name
            if request.risk_level is not None:
                portfolio.risk_level = request.risk_level.value
            if request.risk_per_trade is not None:
                portfolio.risk_per_trade = request.risk_per_trade
            if request.max_drawdown is not None:
                portfolio.max_drawdown = request.max_drawdown
            if request.max_position_pct is not None:
                portfolio.max_position_pct = request.max_position_pct
            if request.max_leverage is not None:
                portfolio.max_leverage = request.max_leverage
            if request.allowed_assets is not None:
                portfolio.allowed_assets = request.allowed_assets
            if request.metadata is not None:
                portfolio.metadata = request.metadata
            
            portfolio.updated_at = datetime.utcnow()
            
            await self.portfolio_repo.update(portfolio)
            
            logger.info(f"Portfolio {self.portfolio_id} updated")
            return self._to_response(portfolio)
            
        except Exception as e:
            logger.error(f"Error updating portfolio: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Portfolio update failed: {str(e)}"
            )

    async def get_portfolio(self) -> PortfolioResponse:
        """
        Get portfolio details.
        
        Returns:
            PortfolioResponse: Portfolio details
        """
        try:
            portfolio = await self.portfolio_repo.get_by_id(self.portfolio_id)
            if not portfolio:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Portfolio {self.portfolio_id} not found"
                )
            
            # Update state
            await self._refresh_state()
            
            return self._to_response(portfolio)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting portfolio: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Portfolio retrieval failed: {str(e)}"
            )

    async def _refresh_state(self) -> None:
        """Refresh portfolio state from database"""
        try:
            # Get positions
            positions = await self.position_repo.get_by_portfolio_id(self.portfolio_id)
            
            # Get orders
            orders = await self.order_repo.get_by_portfolio_id(self.portfolio_id)
            
            # Get trades
            trades = await self.trade_repo.get_by_portfolio_id(self.portfolio_id)
            
            if self._state:
                self._state.positions = [p.__dict__ for p in positions]
                self._state.orders = [o.__dict__ for o in orders]
                self._state.trades = [t.__dict__ for t in trades]
                self._state.timestamp = datetime.utcnow()
                
        except Exception as e:
            logger.error(f"Error refreshing state: {e}")

    # =========================================================================
    # Position Management
    # =========================================================================

    @abstractmethod
    async def open_position(
        self,
        symbol: str,
        side: str,
        size: float,
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> PositionInfo:
        """
        Open a new position.
        
        Args:
            symbol: Trading symbol
            side: Buy or sell
            size: Position size
            price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            
        Returns:
            PositionInfo: Position information
        """
        pass

    @abstractmethod
    async def close_position(
        self,
        position_id: str,
        price: float
    ) -> Dict[str, Any]:
        """
        Close an existing position.
        
        Args:
            position_id: Position ID
            price: Exit price
            
        Returns:
            Dict[str, Any]: Trade result
        """
        pass

    async def get_positions(self) -> List[PositionInfo]:
        """
        Get all positions.
        
        Returns:
            List[PositionInfo]: Position information
        """
        try:
            positions = await self.position_repo.get_by_portfolio_id(self.portfolio_id)
            
            position_infos = []
            for position in positions:
                current_price = await self._get_current_price(position.symbol)
                pnl = (current_price - float(position.entry_price)) * float(position.size)
                
                position_infos.append(PositionInfo(
                    symbol=position.symbol,
                    size=float(position.size),
                    entry_price=float(position.entry_price),
                    current_price=current_price,
                    pnl=pnl,
                    pnl_pct=pnl / (float(position.size) * float(position.entry_price)) if float(position.size) * float(position.entry_price) != 0 else 0,
                    value=float(position.size) * current_price,
                    leverage=1.0,  # Will be calculated
                    margin_used=float(position.size) * current_price * 0.5,  # Example margin
                    stop_loss=float(position.stop_loss) if hasattr(position, 'stop_loss') else None,
                    take_profit=float(position.take_profit) if hasattr(position, 'take_profit') else None,
                    entry_time=position.created_at
                ))
            
            return position_infos
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    async def _get_current_price(self, symbol: str) -> float:
        """Get current price for symbol"""
        try:
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    ticker = await broker.get_ticker(symbol)
                    return float(ticker.get('price', 0))
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error getting price for {symbol}: {e}")
        
        return 0.0

    # =========================================================================
    # Risk Management
    # =========================================================================

    async def check_risk_limits(self) -> Dict[str, Any]:
        """
        Check portfolio risk limits.
        
        Returns:
            Dict[str, Any]: Risk limit status
        """
        try:
            # Get current metrics
            metrics = await self.get_metrics()
            
            risk_status = {
                'overall': 'ok',
                'checks': []
            }
            
            # Check drawdown
            if metrics.current_drawdown > self._risk_limits['max_drawdown'] * 0.8:
                risk_status['checks'].append({
                    'type': 'drawdown',
                    'status': 'warning',
                    'message': f"Drawdown at {metrics.current_drawdown*100:.1f}%",
                    'threshold': self._risk_limits['max_drawdown'] * 100
                })
                risk_status['overall'] = 'warning'
            
            # Check leverage
            if self._state:
                leverage = self._state.leverage
                if leverage > self._risk_limits['max_leverage'] * 0.8:
                    risk_status['checks'].append({
                        'type': 'leverage',
                        'status': 'warning',
                        'message': f"Leverage at {leverage:.1f}x",
                        'threshold': self._risk_limits['max_leverage']
                    })
                    risk_status['overall'] = 'warning'
            
            # Check position concentration
            if self._state and self._state.positions:
                total_value = sum(float(p['value']) for p in self._state.positions)
                if total_value > 0:
                    max_position = max(float(p['value']) for p in self._state.positions)
                    concentration = max_position / total_value
                    if concentration > 0.4:
                        risk_status['checks'].append({
                            'type': 'concentration',
                            'status': 'warning',
                            'message': f"Position concentration at {concentration*100:.1f}%",
                            'threshold': 40
                        })
                        risk_status['overall'] = 'warning'
            
            return risk_status
            
        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")
            return {'overall': 'error', 'checks': []}

    async def update_risk_limits(
        self,
        limits: Dict[str, float]
    ) -> bool:
        """
        Update risk limits.
        
        Args:
            limits: New risk limits
            
        Returns:
            bool: Success indicator
        """
        try:
            for key, value in limits.items():
                if key in self._risk_limits:
                    self._risk_limits[key] = value
            
            logger.info(f"Risk limits updated for {self.portfolio_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating risk limits: {e}")
            return False

    # =========================================================================
    # Performance Metrics
    # =========================================================================

    async def get_metrics(self) -> PortfolioMetrics:
        """
        Get portfolio metrics.
        
        Returns:
            PortfolioMetrics: Portfolio metrics
        """
        try:
            # Get trades
            trades = await self.trade_repo.get_by_portfolio_id(self.portfolio_id)
            
            if not trades:
                return PortfolioMetrics(
                    total_pnl=0,
                    total_pnl_pct=0,
                    daily_pnl=0,
                    weekly_pnl=0,
                    monthly_pnl=0,
                    sharpe_ratio=0,
                    sortino_ratio=0,
                    calmar_ratio=0,
                    max_drawdown=0,
                    current_drawdown=0,
                    win_rate=0,
                    profit_factor=0,
                    avg_win=0,
                    avg_loss=0,
                    total_trades=0,
                    winning_trades=0,
                    losing_trades=0
                )
            
            # Calculate PnL
            total_pnl = sum(float(t.pnl) for t in trades)
            
            # Win/loss stats
            winning_trades = [t for t in trades if float(t.pnl) > 0]
            losing_trades = [t for t in trades if float(t.pnl) < 0]
            
            win_rate = len(winning_trades) / len(trades) if trades else 0
            
            gross_profit = sum(float(t.pnl) for t in winning_trades)
            gross_loss = abs(sum(float(t.pnl) for t in losing_trades))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            avg_win = np.mean([float(t.pnl) for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([abs(float(t.pnl)) for t in losing_trades]) if losing_trades else 0
            
            # Drawdown
            equity = [0]
            for trade in trades:
                equity.append(equity[-1] + float(trade.pnl))
            
            peak = max(equity)
            current_drawdown = (peak - equity[-1]) / peak if peak > 0 else 0
            
            # Max drawdown
            max_drawdown = 0
            peak = equity[0]
            for value in equity:
                if value > peak:
                    peak = value
                drawdown = (peak - value) / peak if peak > 0 else 0
                max_drawdown = max(max_drawdown, drawdown)
            
            # Sharpe ratio
            returns = []
            for i in range(1, len(equity)):
                if equity[i-1] > 0:
                    returns.append((equity[i] - equity[i-1]) / equity[i-1])
            
            if returns:
                sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
            else:
                sharpe_ratio = 0
            
            # Sortino ratio
            downside_returns = [r for r in returns if r < 0]
            if downside_returns:
                sortino_ratio = np.mean(returns) / np.std(downside_returns) * np.sqrt(252) if np.std(downside_returns) > 0 else 0
            else:
                sortino_ratio = 0
            
            # Calmar ratio
            calmar_ratio = np.mean(returns) * 252 / max_drawdown if max_drawdown > 0 else 0
            
            # Period PnL
            now = datetime.utcnow()
            daily_pnl = sum(float(t.pnl) for t in trades if t.execution_time.date() == now.date())
            weekly_pnl = sum(float(t.pnl) for t in trades if t.execution_time >= now - timedelta(days=7))
            monthly_pnl = sum(float(t.pnl) for t in trades if t.execution_time >= now - timedelta(days=30))
            
            return PortfolioMetrics(
                total_pnl=total_pnl,
                total_pnl_pct=total_pnl / self._state.capital if self._state and self._state.capital > 0 else 0,
                daily_pnl=daily_pnl,
                weekly_pnl=weekly_pnl,
                monthly_pnl=monthly_pnl,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=calmar_ratio,
                max_drawdown=max_drawdown,
                current_drawdown=current_drawdown,
                win_rate=win_rate,
                profit_factor=profit_factor,
                avg_win=avg_win,
                avg_loss=avg_loss,
                total_trades=len(trades),
                winning_trades=len(winning_trades),
                losing_trades=len(losing_trades)
            )
            
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return PortfolioMetrics(
                total_pnl=0,
                total_pnl_pct=0,
                daily_pnl=0,
                weekly_pnl=0,
                monthly_pnl=0,
                sharpe_ratio=0,
                sortino_ratio=0,
                calmar_ratio=0,
                max_drawdown=0,
                current_drawdown=0,
                win_rate=0,
                profit_factor=0,
                avg_win=0,
                avg_loss=0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0
            )

    # =========================================================================
    # Monitoring
    # =========================================================================

    async def start_monitoring(self) -> None:
        """Start portfolio monitoring"""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Portfolio {self.portfolio_id} monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop portfolio monitoring"""
        self._is_monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info(f"Portfolio {self.portfolio_id} monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._is_monitoring:
            try:
                # Refresh state
                await self._refresh_state()
                
                # Check risk limits
                risk_status = await self.check_risk_limits()
                
                if risk_status['overall'] == 'warning':
                    logger.warning(f"Portfolio {self.portfolio_id} risk warning")
                elif risk_status['overall'] == 'error':
                    logger.error(f"Portfolio {self.portfolio_id} risk error")
                    
                    # Automatic actions
                    await self._handle_risk_breach(risk_status)
                
                # Update metrics
                self._metrics = await self.get_metrics()
                
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(60)

    async def _handle_risk_breach(self, risk_status: Dict[str, Any]) -> None:
        """Handle risk breach"""
        # Implementation would handle risk breach
        # e.g., reduce positions, pause trading, etc.
        pass

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close portfolio manager"""
        await self.stop_monitoring()
        
        # Clear state
        self._state = None
        self._metrics = None
        
        logger.info(f"Portfolio {self.portfolio_id} closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/api/v1/portfolio", tags=["Portfolio"])


async def get_portfolio_manager(
    portfolio_id: str = Query(..., description="Portfolio ID")
) -> BasePortfolioManager:
    """Dependency to get portfolio manager"""
    # In production, use dependency injection
    return BasePortfolioManager(portfolio_id)


@router.post("/create")
async def create_portfolio(
    request: PortfolioCreateRequest,
    manager: BasePortfolioManager = Depends(lambda: BasePortfolioManager("temp"))
):
    """Create a new portfolio"""
    # This would be handled by a factory
    return await manager.create_portfolio(request)


@router.get("/{portfolio_id}")
async def get_portfolio(
    portfolio_id: str,
    manager: BasePortfolioManager = Depends(
        lambda: BasePortfolioManager("temp")
    )
):
    """Get portfolio details"""
    # This would get the specific portfolio
    pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BasePortfolioManager',
    'PortfolioStatus',
    'PortfolioType',
    'PortfolioRiskLevel',
    'PortfolioCreateRequest',
    'PortfolioResponse',
    'PortfolioUpdateRequest',
    'PortfolioState',
    'PortfolioMetrics',
    'PositionInfo',
    'router'
]
