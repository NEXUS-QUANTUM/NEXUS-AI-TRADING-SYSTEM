"""
NEXUS AI TRADING SYSTEM - Position Manager Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/portfolio/position_manager.py
Description: Advanced position management with full API integration
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
from shared.constants.trading_constants import (
    ORDER_TYPES,
    POSITION_DIRECTIONS,
    TIME_FRAMES
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

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

# Risk management imports
from trading.risk_management.risk_limits import RiskLimitsManager
from trading.risk_management.position_sizer import PositionSizer
from trading.risk_management.stop_loss import StopLossManager
from trading.risk_management.take_profit import TakeProfitManager

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class PositionStatus(str, Enum):
    """Position status"""
    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"
    LIQUIDATED = "liquidated"
    EXPIRED = "expired"


class PositionType(str, Enum):
    """Position types"""
    LONG = "long"
    SHORT = "short"
    HEDGE = "hedge"
    PAPER = "paper"


class PositionRiskLevel(str, Enum):
    """Position risk levels"""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class PositionRequest(BaseModel):
    """Request model for position operations"""
    portfolio_id: str
    symbol: str
    side: str  # long, short
    size: float
    entry_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    leverage: float = 1.0
    position_type: PositionType = PositionType.LONG
    strategy: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('size')
    def validate_size(cls, v):
        if v <= 0:
            raise ValueError("Size must be positive")
        return v

    @validator('leverage')
    def validate_leverage(cls, v):
        if v < 1:
            raise ValueError("Leverage must be at least 1")
        return v


class PositionResponse(BaseModel):
    """Response model for position"""
    position_id: str
    portfolio_id: str
    symbol: str
    side: str
    size: float
    entry_price: float
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    leverage: float
    position_type: PositionType
    status: PositionStatus
    pnl: float
    pnl_pct: float
    value: float
    margin_used: float
    risk_level: PositionRiskLevel
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PositionUpdateRequest(BaseModel):
    """Request model for position update"""
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    leverage: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class PositionCloseRequest(BaseModel):
    """Request model for closing position"""
    position_id: str
    exit_price: Optional[float] = None
    size: Optional[float] = None  # Partial close
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PositionBatchRequest(BaseModel):
    """Request model for batch position operations"""
    portfolio_id: str
    positions: List[PositionRequest]
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PositionContext:
    """Context for position management"""
    position_id: str
    portfolio_id: str
    symbol: str
    side: str
    size: float
    entry_price: float
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    leverage: float = 1.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    value: float = 0.0
    margin_used: float = 0.0
    risk_level: PositionRiskLevel = PositionRiskLevel.MODERATE
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PositionAnalytics:
    """Position analytics"""
    total_positions: int
    open_positions: int
    closed_positions: int
    total_pnl: float
    avg_pnl: float
    avg_holding_period: float
    win_rate: float
    profit_factor: float
    by_symbol: Dict[str, Any]
    by_strategy: Dict[str, Any]


# =============================================================================
# POSITION MANAGER
# =============================================================================

class PositionManager:
    """
    Advanced Position Manager with full API integration.
    
    Features:
    - Position creation and management
    - Risk management integration
    - Stop loss and take profit management
    - Position sizing
    - Position analytics
    - Batch operations
    - Real-time monitoring
    - Position reporting
    """

    def __init__(
        self,
        config: Optional[PortfolioConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        position_repo: Optional[PositionRepository] = None,
        order_repo: Optional[OrderRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        risk_limits: Optional[RiskLimitsManager] = None,
        position_sizer: Optional[PositionSizer] = None,
        stop_loss_manager: Optional[StopLossManager] = None,
        take_profit_manager: Optional[TakeProfitManager] = None
    ):
        """
        Initialize PositionManager.
        
        Args:
            config: Portfolio configuration
            broker_factory: Factory for broker instances
            position_repo: Position repository
            order_repo: Order repository
            trade_repo: Trade repository
            risk_limits: Risk limits manager
            position_sizer: Position sizer
            stop_loss_manager: Stop loss manager
            take_profit_manager: Take profit manager
        """
        self.config = config or PortfolioConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.position_repo = position_repo or PositionRepository()
        self.order_repo = order_repo or OrderRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.risk_limits = risk_limits or RiskLimitsManager()
        self.position_sizer = position_sizer or PositionSizer()
        self.stop_loss_manager = stop_loss_manager or StopLossManager()
        self.take_profit_manager = take_profit_manager or TakeProfitManager()
        
        # Position cache
        self._positions_cache: Dict[str, PositionResponse] = {}
        self._position_contexts: Dict[str, PositionContext] = {}
        
        # Analytics cache
        self._analytics_cache: Dict[str, PositionAnalytics] = {}
        
        # Monitoring
        self._is_monitoring: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        logger.info("PositionManager initialized")

    # =========================================================================
    # Position Operations
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def open_position(
        self,
        request: PositionRequest
    ) -> PositionResponse:
        """
        Open a new position.
        
        Args:
            request: Position request
            
        Returns:
            PositionResponse: Created position
        """
        try:
            # Validate request
            await self._validate_request(request)
            
            # Check risk limits
            await self._check_risk_limits(request)
            
            # Get current price
            current_price = await self._get_current_price(request.symbol)
            if not current_price:
                current_price = request.entry_price
            
            # Create position
            position_data = {
                'portfolio_id': request.portfolio_id,
                'symbol': request.symbol,
                'side': request.side,
                'size': request.size,
                'entry_price': request.entry_price,
                'current_price': current_price,
                'stop_loss': request.stop_loss,
                'take_profit': request.take_profit,
                'leverage': request.leverage,
                'position_type': request.position_type.value,
                'status': PositionStatus.OPEN.value,
                'strategy': request.strategy,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'metadata': request.metadata
            }
            
            position = await self.position_repo.create(position_data)
            
            # Create stop loss if specified
            if request.stop_loss:
                await self.stop_loss_manager.create_stop_loss({
                    'position_id': position.id,
                    'stop_price': request.stop_loss,
                    'stop_type': 'fixed'
                })
            
            # Create take profit if specified
            if request.take_profit:
                await self.take_profit_manager.create_take_profit({
                    'position_id': position.id,
                    'tp_price': request.take_profit,
                    'tp_type': 'fixed'
                })
            
            # Build response
            response = self._to_response(position)
            
            # Cache
            self._positions_cache[response.position_id] = response
            self._position_contexts[response.position_id] = self._build_context(response)
            
            logger.info(f"Position opened: {response.position_id} for {request.symbol}")
            return response
            
        except Exception as e:
            logger.error(f"Error opening position: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Position opening failed: {str(e)}"
            )

    async def _validate_request(self, request: PositionRequest) -> None:
        """Validate position request"""
        if request.side not in ['long', 'short']:
            raise ValueError("Side must be 'long' or 'short'")
        
        if request.size <= 0:
            raise ValueError("Size must be positive")
        
        if request.leverage < 1:
            raise ValueError("Leverage must be at least 1")

    async def _check_risk_limits(self, request: PositionRequest) -> None:
        """Check risk limits"""
        # Check position size
        risk_check = await self.risk_limits.check_limit(
            'max_position_size',
            request.size
        )
        if not risk_check.passed:
            raise ValueError(f"Risk limit breached: {risk_check.message}")
        
        # Check leverage
        if request.leverage > self.config.max_leverage:
            raise ValueError(f"Leverage {request.leverage} exceeds max {self.config.max_leverage}")

    async def _get_current_price(self, symbol: str) -> Optional[float]:
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
        
        return None

    def _to_response(self, position: Any) -> PositionResponse:
        """Convert position to response"""
        return PositionResponse(
            position_id=position.id,
            portfolio_id=position.portfolio_id,
            symbol=position.symbol,
            side=position.side,
            size=float(position.size),
            entry_price=float(position.entry_price),
            current_price=float(position.current_price or position.entry_price),
            stop_loss=float(position.stop_loss) if position.stop_loss else None,
            take_profit=float(position.take_profit) if position.take_profit else None,
            leverage=float(position.leverage) if hasattr(position, 'leverage') else 1.0,
            position_type=PositionType(position.position_type) if hasattr(position, 'position_type') else PositionType.LONG,
            status=PositionStatus(position.status) if hasattr(position, 'status') else PositionStatus.OPEN,
            pnl=float(position.pnl) if hasattr(position, 'pnl') else 0,
            pnl_pct=float(position.pnl_pct) if hasattr(position, 'pnl_pct') else 0,
            value=float(position.size) * float(position.current_price or position.entry_price),
            margin_used=float(position.size) * float(position.current_price or position.entry_price) * 0.5,
            risk_level=self._calculate_risk_level(position),
            created_at=position.created_at,
            updated_at=position.updated_at,
            metadata=position.metadata
        )

    def _build_context(self, response: PositionResponse) -> PositionContext:
        """Build position context"""
        return PositionContext(
            position_id=response.position_id,
            portfolio_id=response.portfolio_id,
            symbol=response.symbol,
            side=response.side,
            size=response.size,
            entry_price=response.entry_price,
            current_price=response.current_price,
            stop_loss=response.stop_loss,
            take_profit=response.take_profit,
            leverage=response.leverage,
            pnl=response.pnl,
            pnl_pct=response.pnl_pct,
            value=response.value,
            margin_used=response.margin_used,
            risk_level=response.risk_level,
            timestamp=datetime.utcnow()
        )

    def _calculate_risk_level(self, position: Any) -> PositionRiskLevel:
        """Calculate position risk level"""
        # Calculate risk based on position size relative to portfolio
        portfolio_value = 100000  # Default, would get from portfolio
        position_value = float(position.size) * float(position.entry_price)
        risk_ratio = position_value / portfolio_value if portfolio_value > 0 else 0
        
        if risk_ratio < 0.05:
            return PositionRiskLevel.LOW
        elif risk_ratio < 0.15:
            return PositionRiskLevel.MODERATE
        elif risk_ratio < 0.30:
            return PositionRiskLevel.HIGH
        else:
            return PositionRiskLevel.CRITICAL

    # =========================================================================
    # Position Updates
    # =========================================================================

    async def update_position(
        self,
        position_id: str,
        request: PositionUpdateRequest
    ) -> PositionResponse:
        """
        Update position parameters.
        
        Args:
            position_id: Position ID
            request: Update request
            
        Returns:
            PositionResponse: Updated position
        """
        try:
            # Get position
            position = await self.position_repo.get_by_id(position_id)
            if not position:
                raise ValueError(f"Position {position_id} not found")
            
            # Update fields
            if request.stop_loss is not None:
                position.stop_loss = request.stop_loss
                # Update stop loss
                await self.stop_loss_manager.update_stop_loss(
                    position_id,
                    request.stop_loss
                )
            
            if request.take_profit is not None:
                position.take_profit = request.take_profit
                # Update take profit
                await self.take_profit_manager.update_take_profit(
                    position_id,
                    request.take_profit
                )
            
            if request.leverage is not None:
                position.leverage = request.leverage
            
            if request.metadata is not None:
                position.metadata = request.metadata
            
            position.updated_at = datetime.utcnow()
            
            await self.position_repo.update(position)
            
            # Update cache
            response = self._to_response(position)
            self._positions_cache[position_id] = response
            self._position_contexts[position_id] = self._build_context(response)
            
            logger.info(f"Position {position_id} updated")
            return response
            
        except Exception as e:
            logger.error(f"Error updating position: {e}")
            raise

    async def close_position(
        self,
        request: PositionCloseRequest
    ) -> Dict[str, Any]:
        """
        Close a position.
        
        Args:
            request: Close request
            
        Returns:
            Dict[str, Any]: Close result
        """
        try:
            # Get position
            position = await self.position_repo.get_by_id(request.position_id)
            if not position:
                raise ValueError(f"Position {request.position_id} not found")
            
            # Get exit price
            exit_price = request.exit_price or await self._get_current_price(position.symbol)
            if not exit_price:
                exit_price = float(position.current_price or position.entry_price)
            
            # Calculate PnL
            size = request.size or float(position.size)
            entry_price = float(position.entry_price)
            
            if position.side == 'long':
                pnl = (exit_price - entry_price) * size
            else:
                pnl = (entry_price - exit_price) * size
            
            # Update position
            position.status = PositionStatus.CLOSED.value
            position.current_price = exit_price
            position.pnl = pnl
            position.pnl_pct = pnl / (size * entry_price) if size * entry_price != 0 else 0
            position.updated_at = datetime.utcnow()
            
            await self.position_repo.update(position)
            
            # Cancel stop loss and take profit
            await self.stop_loss_manager.cancel_stop_loss(request.position_id)
            await self.take_profit_manager.cancel_take_profit(request.position_id)
            
            # Remove from cache
            if request.position_id in self._positions_cache:
                del self._positions_cache[request.position_id]
            if request.position_id in self._position_contexts:
                del self._position_contexts[request.position_id]
            
            logger.info(f"Position {request.position_id} closed with PnL: {pnl:.2f}")
            
            return {
                'position_id': request.position_id,
                'symbol': position.symbol,
                'side': position.side,
                'size': size,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl': pnl,
                'pnl_pct': pnl / (size * entry_price) if size * entry_price != 0 else 0,
                'status': 'closed',
                'timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            raise

    # =========================================================================
    # Position Retrieval
    # =========================================================================

    async def get_position(self, position_id: str) -> PositionResponse:
        """
        Get position by ID.
        
        Args:
            position_id: Position ID
            
        Returns:
            PositionResponse: Position details
        """
        try:
            # Check cache
            if position_id in self._positions_cache:
                return self._positions_cache[position_id]
            
            # Get from database
            position = await self.position_repo.get_by_id(position_id)
            if not position:
                raise ValueError(f"Position {position_id} not found")
            
            response = self._to_response(position)
            self._positions_cache[position_id] = response
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting position: {e}")
            raise

    async def get_positions(
        self,
        portfolio_id: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[PositionResponse]:
        """
        Get positions with filters.
        
        Args:
            portfolio_id: Filter by portfolio
            symbol: Filter by symbol
            status: Filter by status
            
        Returns:
            List[PositionResponse]: Positions
        """
        try:
            positions = await self.position_repo.get_all()
            
            if portfolio_id:
                positions = [p for p in positions if p.portfolio_id == portfolio_id]
            
            if symbol:
                positions = [p for p in positions if p.symbol == symbol]
            
            if status:
                positions = [p for p in positions if p.status == status]
            
            return [self._to_response(p) for p in positions]
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    async def get_open_positions(self, portfolio_id: str) -> List[PositionResponse]:
        """
        Get open positions for portfolio.
        
        Args:
            portfolio_id: Portfolio ID
            
        Returns:
            List[PositionResponse]: Open positions
        """
        return await self.get_positions(
            portfolio_id=portfolio_id,
            status=PositionStatus.OPEN.value
        )

    # =========================================================================
    # Position Analytics
    # =========================================================================

    async def get_analytics(
        self,
        portfolio_id: str
    ) -> PositionAnalytics:
        """
        Get position analytics.
        
        Args:
            portfolio_id: Portfolio ID
            
        Returns:
            PositionAnalytics: Analytics data
        """
        try:
            # Check cache
            if portfolio_id in self._analytics_cache:
                return self._analytics_cache[portfolio_id]
            
            # Get positions
            positions = await self.get_positions(portfolio_id=portfolio_id)
            
            if not positions:
                return PositionAnalytics(
                    total_positions=0,
                    open_positions=0,
                    closed_positions=0,
                    total_pnl=0,
                    avg_pnl=0,
                    avg_holding_period=0,
                    win_rate=0,
                    profit_factor=0,
                    by_symbol={},
                    by_strategy={}
                )
            
            # Calculate analytics
            total_positions = len(positions)
            open_positions = sum(1 for p in positions if p.status == PositionStatus.OPEN)
            closed_positions = sum(1 for p in positions if p.status == PositionStatus.CLOSED)
            
            total_pnl = sum(p.pnl for p in positions)
            avg_pnl = total_pnl / total_positions if total_positions > 0 else 0
            
            # Win rate
            winning_positions = [p for p in positions if p.pnl > 0]
            win_rate = len(winning_positions) / total_positions if total_positions > 0 else 0
            
            # Profit factor
            gross_profit = sum(p.pnl for p in positions if p.pnl > 0)
            gross_loss = abs(sum(p.pnl for p in positions if p.pnl < 0))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            
            # By symbol
            by_symbol = {}
            for pos in positions:
                if pos.symbol not in by_symbol:
                    by_symbol[pos.symbol] = {'count': 0, 'pnl': 0}
                by_symbol[pos.symbol]['count'] += 1
                by_symbol[pos.symbol]['pnl'] += pos.pnl
            
            # By strategy
            by_strategy = {}
            for pos in positions:
                strategy = pos.metadata.get('strategy', 'unknown')
                if strategy not in by_strategy:
                    by_strategy[strategy] = {'count': 0, 'pnl': 0}
                by_strategy[strategy]['count'] += 1
                by_strategy[strategy]['pnl'] += pos.pnl
            
            analytics = PositionAnalytics(
                total_positions=total_positions,
                open_positions=open_positions,
                closed_positions=closed_positions,
                total_pnl=total_pnl,
                avg_pnl=avg_pnl,
                avg_holding_period=0,  # Would calculate from timestamps
                win_rate=win_rate,
                profit_factor=profit_factor,
                by_symbol=by_symbol,
                by_strategy=by_strategy
            )
            
            # Cache
            self._analytics_cache[portfolio_id] = analytics
            
            return analytics
            
        except Exception as e:
            logger.error(f"Error getting analytics: {e}")
            return PositionAnalytics(
                total_positions=0,
                open_positions=0,
                closed_positions=0,
                total_pnl=0,
                avg_pnl=0,
                avg_holding_period=0,
                win_rate=0,
                profit_factor=0,
                by_symbol={},
                by_strategy={}
            )

    # =========================================================================
    # Batch Operations
    # =========================================================================

    async def batch_open_positions(
        self,
        request: PositionBatchRequest
    ) -> List[PositionResponse]:
        """
        Open multiple positions.
        
        Args:
            request: Batch request
            
        Returns:
            List[PositionResponse]: Created positions
        """
        results = []
        
        for position_request in request.positions:
            try:
                result = await self.open_position(position_request)
                results.append(result)
            except Exception as e:
                logger.error(f"Error opening position {position_request.symbol}: {e}")
                # Continue with next position
        
        return results

    async def batch_close_positions(
        self,
        portfolio_id: str,
        symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Close multiple positions.
        
        Args:
            portfolio_id: Portfolio ID
            symbols: Symbols to close (all if None)
            
        Returns:
            Dict[str, Any]: Batch results
        """
        try:
            positions = await self.get_open_positions(portfolio_id)
            
            if symbols:
                positions = [p for p in positions if p.symbol in symbols]
            
            results = []
            for position in positions:
                try:
                    result = await self.close_position(
                        PositionCloseRequest(position_id=position.position_id)
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error closing position {position.position_id}: {e}")
            
            return {
                'total': len(positions),
                'closed': len(results),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error batch closing positions: {e}")
            raise

    # =========================================================================
    # Monitoring
    # =========================================================================

    async def start_monitoring(self) -> None:
        """Start position monitoring"""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Position monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop position monitoring"""
        self._is_monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("Position monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._is_monitoring:
            try:
                # Update positions
                for position_id, context in list(self._position_contexts.items()):
                    try:
                        # Get current price
                        current_price = await self._get_current_price(context.symbol)
                        if current_price:
                            # Update context
                            context.current_price = current_price
                            
                            # Update PnL
                            if context.side == 'long':
                                context.pnl = (current_price - context.entry_price) * context.size
                            else:
                                context.pnl = (context.entry_price - current_price) * context.size
                            
                            context.pnl_pct = context.pnl / (context.size * context.entry_price) if context.size * context.entry_price != 0 else 0
                            context.value = context.size * current_price
                            
                            # Update risk level
                            context.risk_level = self._calculate_risk_level_from_context(context)
                            
                            # Check stop loss
                            if context.stop_loss:
                                if context.side == 'long' and current_price <= context.stop_loss:
                                    await self._trigger_stop_loss(context)
                                elif context.side == 'short' and current_price >= context.stop_loss:
                                    await self._trigger_stop_loss(context)
                            
                            # Check take profit
                            if context.take_profit:
                                if context.side == 'long' and current_price >= context.take_profit:
                                    await self._trigger_take_profit(context)
                                elif context.side == 'short' and current_price <= context.take_profit:
                                    await self._trigger_take_profit(context)
                            
                            # Update cache
                            self._position_contexts[position_id] = context
                            
                    except Exception as e:
                        logger.error(f"Error monitoring position {position_id}: {e}")
                
                await asyncio.sleep(1)  # Check every second
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)

    def _calculate_risk_level_from_context(
        self,
        context: PositionContext
    ) -> PositionRiskLevel:
        """Calculate risk level from context"""
        # Simple risk calculation based on PnL percentage
        if abs(context.pnl_pct) < 0.05:
            return PositionRiskLevel.LOW
        elif abs(context.pnl_pct) < 0.15:
            return PositionRiskLevel.MODERATE
        elif abs(context.pnl_pct) < 0.30:
            return PositionRiskLevel.HIGH
        else:
            return PositionRiskLevel.CRITICAL

    async def _trigger_stop_loss(self, context: PositionContext) -> None:
        """Trigger stop loss"""
        logger.info(f"Stop loss triggered for position {context.position_id}")
        
        # Close position
        request = PositionCloseRequest(
            position_id=context.position_id,
            exit_price=context.current_price
        )
        await self.close_position(request)

    async def _trigger_take_profit(self, context: PositionContext) -> None:
        """Trigger take profit"""
        logger.info(f"Take profit triggered for position {context.position_id}")
        
        # Close position
        request = PositionCloseRequest(
            position_id=context.position_id,
            exit_price=context.current_price
        )
        await self.close_position(request)

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the position manager"""
        await self.stop_monitoring()
        
        # Clear caches
        self._positions_cache.clear()
        self._position_contexts.clear()
        self._analytics_cache.clear()
        
        logger.info("PositionManager closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/portfolio/positions", tags=["Portfolio Positions"])


async def get_manager() -> PositionManager:
    """Dependency to get PositionManager instance"""
    return PositionManager()


@router.post("/open", response_model=PositionResponse)
async def open_position(
    request: PositionRequest,
    manager: PositionManager = Depends(get_manager)
):
    """Open a new position"""
    return await manager.open_position(request)


@router.put("/{position_id}", response_model=PositionResponse)
async def update_position(
    position_id: str,
    request: PositionUpdateRequest,
    manager: PositionManager = Depends(get_manager)
):
    """Update position parameters"""
    return await manager.update_position(position_id, request)


@router.post("/close")
async def close_position(
    request: PositionCloseRequest,
    manager: PositionManager = Depends(get_manager)
):
    """Close a position"""
    return await manager.close_position(request)


@router.get("/{position_id}", response_model=PositionResponse)
async def get_position(
    position_id: str,
    manager: PositionManager = Depends(get_manager)
):
    """Get position by ID"""
    return await manager.get_position(position_id)


@router.get("/")
async def get_positions(
    portfolio_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    manager: PositionManager = Depends(get_manager)
):
    """Get positions with filters"""
    return await manager.get_positions(portfolio_id, symbol, status)


@router.get("/{portfolio_id}/open")
async def get_open_positions(
    portfolio_id: str,
    manager: PositionManager = Depends(get_manager)
):
    """Get open positions for portfolio"""
    return await manager.get_open_positions(portfolio_id)


@router.get("/{portfolio_id}/analytics")
async def get_position_analytics(
    portfolio_id: str,
    manager: PositionManager = Depends(get_manager)
):
    """Get position analytics"""
    return await manager.get_analytics(portfolio_id)


@router.post("/batch/open")
async def batch_open_positions(
    request: PositionBatchRequest,
    manager: PositionManager = Depends(get_manager)
):
    """Open multiple positions"""
    return await manager.batch_open_positions(request)


@router.post("/{portfolio_id}/batch/close")
async def batch_close_positions(
    portfolio_id: str,
    symbols: Optional[List[str]] = Body(None, embed=True),
    manager: PositionManager = Depends(get_manager)
):
    """Close multiple positions"""
    return await manager.batch_close_positions(portfolio_id, symbols)


@router.post("/monitor/start")
async def start_position_monitoring(
    manager: PositionManager = Depends(get_manager)
):
    """Start position monitoring"""
    await manager.start_monitoring()
    return {"status": "started"}


@router.post("/monitor/stop")
async def stop_position_monitoring(
    manager: PositionManager = Depends(get_manager)
):
    """Stop position monitoring"""
    await manager.stop_monitoring()
    return {"status": "stopped"}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PositionManager',
    'PositionStatus',
    'PositionType',
    'PositionRiskLevel',
    'PositionRequest',
    'PositionResponse',
    'PositionUpdateRequest',
    'PositionCloseRequest',
    'PositionBatchRequest',
    'PositionContext',
    'PositionAnalytics',
    'router'
]
