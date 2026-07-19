"""
NEXUS AI TRADING SYSTEM - Portfolio Manager Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/portfolio/portfolio_manager.py
Description: Core portfolio management engine with full API integration
"""

import asyncio
import logging
import time
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
    ASSET_CLASSES,
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
from backend.database.repositories.portfolio_repository import PortfolioRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

# Portfolio imports
from trading.portfolio.base import BasePortfolioManager, PortfolioState, PortfolioMetrics
from trading.portfolio.allocation import PortfolioAllocation, AllocationRequest, AllocationResponse
from trading.portfolio.balance_tracker import BalanceTracker, BalanceRequest, BalanceResponse
from trading.portfolio.history import PortfolioHistory, HistoryRequest, HistoryResponse
from trading.portfolio.performance import PortfolioPerformance, PerformanceRequest, PerformanceResponse
from trading.portfolio.pnl_calculator import PnLCalculator, PnLRequest, PnLResponse

# Risk management imports
from trading.risk_management.risk_limits import RiskLimitsManager
from trading.risk_management.position_sizer import PositionSizer, PositionSizingRequest

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class PortfolioManagerStatus(str, Enum):
    """Portfolio manager status"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    DEGRADED = "degraded"


class OrderExecutionStyle(str, Enum):
    """Order execution styles"""
    MARKET = "market"
    LIMIT = "limit"
    SMART = "smart"
    TWAP = "twap"
    VWAP = "vwap"
    POV = "pov"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class PortfolioManagerRequest(BaseModel):
    """Request model for portfolio manager"""
    portfolio_id: str
    action: str = "start"  # start, stop, pause, resume
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PortfolioManagerResponse(BaseModel):
    """Response model for portfolio manager"""
    portfolio_id: str
    status: PortfolioManagerStatus
    timestamp: datetime
    summary: Dict[str, Any]
    metrics: Dict[str, Any]
    positions: List[Dict[str, Any]]
    orders: List[Dict[str, Any]]
    recommendations: List[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderRequest(BaseModel):
    """Request model for placing order"""
    portfolio_id: str
    symbol: str
    side: str
    size: float
    order_type: OrderExecutionStyle = OrderExecutionStyle.LIMIT
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    leverage: float = 1.0
    reduce_only: bool = False
    post_only: bool = False
    time_in_force: str = "GTC"
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('size')
    def validate_size(cls, v):
        if v <= 0:
            raise ValueError("Size must be positive")
        return v


class OrderResponse(BaseModel):
    """Response model for order"""
    order_id: str
    portfolio_id: str
    symbol: str
    side: str
    size: float
    filled_size: float
    price: float
    avg_price: float
    status: str
    created_at: datetime
    filled_at: Optional[datetime] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PortfolioManagerContext:
    """Context for portfolio manager"""
    portfolio_id: str
    status: PortfolioManagerStatus
    capital: float
    equity: float
    positions: List[Any]
    orders: List[Any]
    trades: List[Any]
    metrics: PortfolioMetrics
    timestamp: datetime


@dataclass
class ExecutionResult:
    """Result of order execution"""
    order_id: str
    symbol: str
    side: str
    size: float
    filled_size: float
    avg_price: float
    status: str
    timestamp: datetime
    message: str


# =============================================================================
# PORTFOLIO MANAGER
# =============================================================================

class PortfolioManager:
    """
    Core Portfolio Manager for NEXUS AI Trading System.
    
    Features:
    - Portfolio management
    - Order execution
    - Position management
    - Risk management
    - Performance tracking
    - Rebalancing
    - Multi-asset support
    - Real-time monitoring
    - Integration with all portfolio modules
    """

    def __init__(
        self,
        config: Optional[PortfolioConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        position_repo: Optional[PositionRepository] = None,
        order_repo: Optional[OrderRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        portfolio_repo: Optional[PortfolioRepository] = None
    ):
        """
        Initialize PortfolioManager.
        
        Args:
            config: Portfolio configuration
            broker_factory: Factory for broker instances
            position_repo: Position repository
            order_repo: Order repository
            trade_repo: Trade repository
            portfolio_repo: Portfolio repository
        """
        self.config = config or PortfolioConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.position_repo = position_repo or PositionRepository()
        self.order_repo = order_repo or OrderRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.portfolio_repo = portfolio_repo or PortfolioRepository()
        
        # Portfolio components
        self.base_manager = BasePortfolioManager(config)
        self.allocation = PortfolioAllocation(config)
        self.balance_tracker = BalanceTracker(config)
        self.history = PortfolioHistory(config)
        self.performance = PortfolioPerformance(config)
        self.pnl_calculator = PnLCalculator(config)
        self.risk_limits = RiskLimitsManager()
        self.position_sizer = PositionSizer()
        
        # Active portfolios
        self._portfolios: Dict[str, Dict[str, Any]] = {}
        self._portfolio_states: Dict[str, PortfolioState] = {}
        
        # Order management
        self._pending_orders: Dict[str, OrderRequest] = {}
        self._executed_orders: List[OrderResponse] = []
        
        # Monitoring
        self._is_running: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        logger.info("PortfolioManager initialized")

    # =========================================================================
    # Portfolio Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def manage_portfolio(
        self,
        request: PortfolioManagerRequest
    ) -> PortfolioManagerResponse:
        """
        Manage portfolio operations.
        
        Args:
            request: Portfolio manager request
            
        Returns:
            PortfolioManagerResponse: Management results
        """
        try:
            if request.action == "start":
                return await self._start_portfolio(request)
            elif request.action == "stop":
                return await self._stop_portfolio(request)
            elif request.action == "pause":
                return await self._pause_portfolio(request)
            elif request.action == "resume":
                return await self._resume_portfolio(request)
            elif request.action == "status":
                return await self._get_portfolio_status(request)
            else:
                raise ValueError(f"Unknown action: {request.action}")
                
        except Exception as e:
            logger.error(f"Error managing portfolio: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Portfolio management failed: {str(e)}"
            )

    async def _start_portfolio(
        self,
        request: PortfolioManagerRequest
    ) -> PortfolioManagerResponse:
        """Start portfolio"""
        portfolio_id = request.portfolio_id
        
        # Get portfolio
        portfolio = await self.portfolio_repo.get_by_id(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        
        # Initialize state
        state = PortfolioState(
            portfolio_id=portfolio_id,
            status=PortfolioManagerStatus.RUNNING,
            capital=float(portfolio.current_capital),
            equity=float(portfolio.total_equity),
            positions=[],
            orders=[],
            trades=[],
            pnl=float(portfolio.total_pnl),
            drawdown=0,
            leverage=1.0,
            timestamp=datetime.utcnow()
        )
        
        self._portfolio_states[portfolio_id] = state
        
        # Start monitoring
        if not self._is_running:
            await self._start_monitoring()
        
        logger.info(f"Portfolio {portfolio_id} started")
        return await self._get_portfolio_status(request)

    async def _stop_portfolio(
        self,
        request: PortfolioManagerRequest
    ) -> PortfolioManagerResponse:
        """Stop portfolio"""
        portfolio_id = request.portfolio_id
        
        if portfolio_id in self._portfolio_states:
            self._portfolio_states[portfolio_id].status = PortfolioManagerStatus.STOPPED
        
        # Cancel all orders
        await self._cancel_all_orders(portfolio_id)
        
        logger.info(f"Portfolio {portfolio_id} stopped")
        return await self._get_portfolio_status(request)

    async def _pause_portfolio(
        self,
        request: PortfolioManagerRequest
    ) -> PortfolioManagerResponse:
        """Pause portfolio"""
        portfolio_id = request.portfolio_id
        
        if portfolio_id in self._portfolio_states:
            self._portfolio_states[portfolio_id].status = PortfolioManagerStatus.PAUSED
        
        # Cancel pending orders
        await self._cancel_pending_orders(portfolio_id)
        
        logger.info(f"Portfolio {portfolio_id} paused")
        return await self._get_portfolio_status(request)

    async def _resume_portfolio(
        self,
        request: PortfolioManagerRequest
    ) -> PortfolioManagerResponse:
        """Resume portfolio"""
        portfolio_id = request.portfolio_id
        
        if portfolio_id in self._portfolio_states:
            self._portfolio_states[portfolio_id].status = PortfolioManagerStatus.RUNNING
        
        logger.info(f"Portfolio {portfolio_id} resumed")
        return await self._get_portfolio_status(request)

    async def _get_portfolio_status(
        self,
        request: PortfolioManagerRequest
    ) -> PortfolioManagerResponse:
        """Get portfolio status"""
        portfolio_id = request.portfolio_id
        
        # Get portfolio
        portfolio = await self.portfolio_repo.get_by_id(portfolio_id)
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")
        
        # Get positions
        positions = await self.position_repo.get_by_portfolio_id(portfolio_id)
        
        # Get orders
        orders = await self.order_repo.get_by_portfolio_id(portfolio_id)
        
        # Get state
        state = self._portfolio_states.get(portfolio_id)
        
        # Get metrics
        metrics = await self.base_manager.get_metrics()
        
        # Generate recommendations
        recommendations = await self._generate_recommendations(portfolio_id)
        
        return PortfolioManagerResponse(
            portfolio_id=portfolio_id,
            status=state.status if state else PortfolioManagerStatus.STOPPED,
            timestamp=datetime.utcnow(),
            summary={
                'capital': portfolio.current_capital,
                'equity': portfolio.total_equity,
                'pnl': portfolio.total_pnl,
                'pnl_pct': portfolio.total_pnl_pct
            },
            metrics=metrics.__dict__,
            positions=[p.__dict__ for p in positions],
            orders=[o.__dict__ for o in orders],
            recommendations=recommendations,
            metadata=request.metadata
        )

    # =========================================================================
    # Order Execution
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def place_order(
        self,
        request: OrderRequest
    ) -> OrderResponse:
        """
        Place an order.
        
        Args:
            request: Order request
            
        Returns:
            OrderResponse: Order result
        """
        try:
            # Validate request
            await self._validate_order(request)
            
            # Check portfolio status
            state = self._portfolio_states.get(request.portfolio_id)
            if not state or state.status != PortfolioManagerStatus.RUNNING:
                raise ValueError(f"Portfolio {request.portfolio_id} is not running")
            
            # Calculate position size if needed
            if request.size <= 0:
                sizing_request = PositionSizingRequest(
                    symbol=request.symbol,
                    portfolio_id=request.portfolio_id,
                    risk_per_trade=self.config.risk_per_trade
                )
                sizing_result = await self.position_sizer.calculate_position_size(sizing_request)
                request.size = sizing_result.position_size
            
            # Check risk limits
            risk_check = await self.risk_limits.check_limit(
                'max_position_size',
                request.size
            )
            if not risk_check.passed:
                raise ValueError(f"Risk limit breached: {risk_check.message}")
            
            # Get broker
            broker = self.broker_factory.get_broker_for_symbol(request.symbol)
            if not broker:
                raise ValueError(f"No broker available for {request.symbol}")
            
            # Place order
            order_data = {
                'symbol': request.symbol,
                'side': request.side,
                'size': request.size,
                'order_type': request.order_type.value if request.order_type else 'limit',
                'price': request.price,
                'stop_loss': request.stop_loss,
                'take_profit': request.take_profit,
                'leverage': request.leverage,
                'reduce_only': request.reduce_only,
                'post_only': request.post_only,
                'time_in_force': request.time_in_force
            }
            
            result = await broker.place_order(order_data)
            
            # Create response
            response = OrderResponse(
                order_id=result.get('order_id'),
                portfolio_id=request.portfolio_id,
                symbol=request.symbol,
                side=request.side,
                size=request.size,
                filled_size=result.get('filled_size', 0),
                price=result.get('price', request.price or 0),
                avg_price=result.get('avg_price', request.price or 0),
                status=result.get('status', 'pending'),
                created_at=datetime.utcnow(),
                filled_at=datetime.utcnow() if result.get('status') == 'filled' else None,
                stop_loss=request.stop_loss,
                take_profit=request.take_profit,
                metadata=request.metadata
            )
            
            # Store order
            self._pending_orders[response.order_id] = request
            self._executed_orders.append(response)
            
            logger.info(f"Order placed: {response.order_id} for {request.symbol}")
            return response
            
        except Exception as e:
            logger.error(f"Error placing order: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Order placement failed: {str(e)}"
            )

    async def _validate_order(self, request: OrderRequest) -> None:
        """Validate order request"""
        if request.side not in ['buy', 'sell']:
            raise ValueError("Side must be 'buy' or 'sell'")
        
        if request.size <= 0:
            raise ValueError("Size must be positive")
        
        if request.leverage < 1 or request.leverage > self.config.max_leverage:
            raise ValueError(f"Leverage must be between 1 and {self.config.max_leverage}")

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            order_id: Order ID
            
        Returns:
            bool: Success indicator
        """
        try:
            if order_id not in self._pending_orders:
                return False
            
            request = self._pending_orders[order_id]
            
            # Get broker
            broker = self.broker_factory.get_broker_for_symbol(request.symbol)
            if not broker:
                return False
            
            success = await broker.cancel_order(order_id)
            
            if success:
                del self._pending_orders[order_id]
                logger.info(f"Order {order_id} cancelled")
            
            return success
            
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    async def _cancel_all_orders(self, portfolio_id: str) -> int:
        """Cancel all orders for portfolio"""
        cancelled = 0
        
        for order_id, request in list(self._pending_orders.items()):
            if request.portfolio_id == portfolio_id:
                if await self.cancel_order(order_id):
                    cancelled += 1
        
        return cancelled

    async def _cancel_pending_orders(self, portfolio_id: str) -> int:
        """Cancel pending orders for portfolio"""
        return await self._cancel_all_orders(portfolio_id)

    # =========================================================================
    # Position Management
    # =========================================================================

    async def get_positions(
        self,
        portfolio_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all positions for portfolio.
        
        Args:
            portfolio_id: Portfolio ID
            
        Returns:
            List[Dict[str, Any]]: Positions
        """
        positions = await self.position_repo.get_by_portfolio_id(portfolio_id)
        return [p.__dict__ for p in positions]

    async def close_position(
        self,
        position_id: str,
        price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Close a position.
        
        Args:
            position_id: Position ID
            price: Exit price (market if not specified)
            
        Returns:
            Dict[str, Any]: Trade result
        """
        try:
            # Get position
            position = await self.position_repo.get_by_id(position_id)
            if not position:
                raise ValueError(f"Position {position_id} not found")
            
            # Get broker
            broker = self.broker_factory.get_broker_for_symbol(position.symbol)
            if not broker:
                raise ValueError(f"No broker available for {position.symbol}")
            
            # Close position
            result = await broker.close_position(position_id, price)
            
            logger.info(f"Position {position_id} closed")
            return result
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            raise

    # =========================================================================
    # Rebalancing
    # =========================================================================

    async def rebalance_portfolio(
        self,
        portfolio_id: str,
        target_weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Rebalance portfolio to target weights.
        
        Args:
            portfolio_id: Portfolio ID
            target_weights: Target weights by symbol
            
        Returns:
            Dict[str, Any]: Rebalance results
        """
        try:
            # Get current positions
            positions = await self.position_repo.get_by_portfolio_id(portfolio_id)
            
            # Calculate current weights
            total_value = sum(float(p.size) * float(p.entry_price) for p in positions)
            current_weights = {}
            for pos in positions:
                if total_value > 0:
                    current_weights[pos.symbol] = (float(pos.size) * float(pos.entry_price)) / total_value
                else:
                    current_weights[pos.symbol] = 0
            
            # Get target weights
            if not target_weights:
                # Calculate from allocation
                allocation_request = AllocationRequest(
                    portfolio_id=portfolio_id,
                    assets=[p.symbol for p in positions]
                )
                allocation = await self.allocation.allocate(allocation_request)
                target_weights = allocation.weights
            
            # Calculate trades needed
            trades = []
            for symbol, target_weight in target_weights.items():
                current_weight = current_weights.get(symbol, 0)
                diff = target_weight - current_weight
                
                if abs(diff) > 0.01:  # 1% threshold
                    size = diff * total_value / self._get_current_price(symbol)
                    side = 'buy' if diff > 0 else 'sell'
                    
                    trades.append({
                        'symbol': symbol,
                        'side': side,
                        'size': abs(size),
                        'target_weight': target_weight,
                        'current_weight': current_weight
                    })
            
            # Execute rebalance
            results = []
            for trade in trades:
                order_request = OrderRequest(
                    portfolio_id=portfolio_id,
                    symbol=trade['symbol'],
                    side=trade['side'],
                    size=trade['size']
                )
                result = await self.place_order(order_request)
                results.append(result)
            
            return {
                'rebalanced': True,
                'trades': results,
                'target_weights': target_weights,
                'current_weights': current_weights
            }
            
        except Exception as e:
            logger.error(f"Error rebalancing portfolio: {e}")
            raise

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
        
        return 0

    # =========================================================================
    # Performance Tracking
    # =========================================================================

    async def get_portfolio_performance(
        self,
        portfolio_id: str,
        metric: str = "sharpe_ratio",
        period: str = "1y"
    ) -> Dict[str, Any]:
        """
        Get portfolio performance.
        
        Args:
            portfolio_id: Portfolio ID
            metric: Performance metric
            period: Time period
            
        Returns:
            Dict[str, Any]: Performance results
        """
        try:
            request = PerformanceRequest(
                portfolio_id=portfolio_id,
                metric=metric,
                period=period
            )
            return await self.performance.calculate_performance(request)
            
        except Exception as e:
            logger.error(f"Error getting performance: {e}")
            raise

    async def get_portfolio_pnl(
        self,
        portfolio_id: str,
        period: str = "month"
    ) -> Dict[str, Any]:
        """
        Get portfolio PnL.
        
        Args:
            portfolio_id: Portfolio ID
            period: Time period
            
        Returns:
            Dict[str, Any]: PnL results
        """
        try:
            request = PnLRequest(
                portfolio_id=portfolio_id,
                period=period
            )
            return await self.pnl_calculator.calculate_pnl(request)
            
        except Exception as e:
            logger.error(f"Error getting PnL: {e}")
            raise

    # =========================================================================
    # Recommendations
    # =========================================================================

    async def _generate_recommendations(
        self,
        portfolio_id: str
    ) -> List[str]:
        """Generate portfolio recommendations"""
        recommendations = []
        
        try:
            # Get portfolio status
            status = await self._get_portfolio_status(
                PortfolioManagerRequest(portfolio_id=portfolio_id, action="status")
            )
            
            # Check metrics
            metrics = status.metrics
            
            # Performance recommendations
            if metrics.get('sharpe_ratio', 0) < 0.5:
                recommendations.append("Low Sharpe ratio. Consider adjusting strategy.")
            
            if metrics.get('max_drawdown', 0) > 0.15:
                recommendations.append("High drawdown. Consider implementing stricter risk controls.")
            
            if metrics.get('win_rate', 0) < 0.4:
                recommendations.append("Low win rate. Review trade entry criteria.")
            
            # Position recommendations
            positions = status.positions
            if len(positions) > 0:
                total_value = sum(p.get('value', 0) for p in positions)
                for pos in positions:
                    if total_value > 0:
                        concentration = pos.get('value', 0) / total_value
                        if concentration > 0.3:
                            recommendations.append(f"High concentration in {pos.get('symbol')}. Consider diversifying.")
            
            # Risk recommendations
            risk_status = await self.risk_limits.get_all_limits_status()
            if risk_status.breached_limits:
                recommendations.append(f"Risk limits breached: {', '.join(risk_status.breached_limits)}")
            
            if not recommendations:
                recommendations.append("All metrics are within acceptable ranges.")
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            recommendations.append("Unable to generate recommendations.")
        
        return recommendations

    # =========================================================================
    # Monitoring
    # =========================================================================

    async def _start_monitoring(self) -> None:
        """Start portfolio monitoring"""
        if self._is_running:
            return
        
        self._is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Portfolio monitoring started")

    async def _stop_monitoring(self) -> None:
        """Stop portfolio monitoring"""
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("Portfolio monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._is_running:
            try:
                # Monitor each portfolio
                for portfolio_id, state in self._portfolio_states.items():
                    if state.status == PortfolioManagerStatus.RUNNING:
                        try:
                            # Update positions
                            positions = await self.position_repo.get_by_portfolio_id(portfolio_id)
                            state.positions = [p.__dict__ for p in positions]
                            
                            # Check risk limits
                            risk_status = await self.risk_limits.get_all_limits_status()
                            if risk_status.breached_limits:
                                logger.warning(f"Risk limits breached for {portfolio_id}: {risk_status.breached_limits}")
                            
                            # Update state
                            state.timestamp = datetime.utcnow()
                            
                        except Exception as e:
                            logger.error(f"Error monitoring portfolio {portfolio_id}: {e}")
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the portfolio manager"""
        await self._stop_monitoring()
        
        # Close all portfolios
        for portfolio_id in list(self._portfolio_states.keys()):
            await self._stop_portfolio(
                PortfolioManagerRequest(portfolio_id=portfolio_id, action="stop")
            )
        
        self._portfolio_states.clear()
        self._pending_orders.clear()
        self._executed_orders.clear()
        
        logger.info("PortfolioManager closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/portfolio", tags=["Portfolio"])


async def get_manager() -> PortfolioManager:
    """Dependency to get PortfolioManager instance"""
    return PortfolioManager()


@router.post("/manage", response_model=PortfolioManagerResponse)
async def manage_portfolio(
    request: PortfolioManagerRequest,
    manager: PortfolioManager = Depends(get_manager)
):
    """Manage portfolio operations"""
    return await manager.manage_portfolio(request)


@router.post("/order", response_model=OrderResponse)
async def place_order(
    request: OrderRequest,
    manager: PortfolioManager = Depends(get_manager)
):
    """Place an order"""
    return await manager.place_order(request)


@router.post("/order/{order_id}/cancel")
async def cancel_order(
    order_id: str,
    manager: PortfolioManager = Depends(get_manager)
):
    """Cancel an order"""
    success = await manager.cancel_order(order_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {order_id} not found"
        )
    return {"success": True}


@router.get("/{portfolio_id}/positions")
async def get_positions(
    portfolio_id: str,
    manager: PortfolioManager = Depends(get_manager)
):
    """Get portfolio positions"""
    return await manager.get_positions(portfolio_id)


@router.post("/{portfolio_id}/position/{position_id}/close")
async def close_position(
    portfolio_id: str,
    position_id: str,
    price: Optional[float] = Body(None, embed=True),
    manager: PortfolioManager = Depends(get_manager)
):
    """Close a position"""
    return await manager.close_position(position_id, price)


@router.post("/{portfolio_id}/rebalance")
async def rebalance_portfolio(
    portfolio_id: str,
    target_weights: Optional[Dict[str, float]] = Body(None, embed=True),
    manager: PortfolioManager = Depends(get_manager)
):
    """Rebalance portfolio"""
    return await manager.rebalance_portfolio(portfolio_id, target_weights)


@router.get("/{portfolio_id}/performance")
async def get_performance(
    portfolio_id: str,
    metric: str = Query("sharpe_ratio"),
    period: str = Query("1y"),
    manager: PortfolioManager = Depends(get_manager)
):
    """Get portfolio performance"""
    return await manager.get_portfolio_performance(portfolio_id, metric, period)


@router.get("/{portfolio_id}/pnl")
async def get_pnl(
    portfolio_id: str,
    period: str = Query("month"),
    manager: PortfolioManager = Depends(get_manager)
):
    """Get portfolio PnL"""
    return await manager.get_portfolio_pnl(portfolio_id, period)


@router.post("/{portfolio_id}/rebalance")
async def rebalance_portfolio(
    portfolio_id: str,
    target_weights: Optional[Dict[str, float]] = Body(None, embed=True),
    manager: PortfolioManager = Depends(get_manager)
):
    """Rebalance portfolio"""
    return await manager.rebalance_portfolio(portfolio_id, target_weights)


@router.get("/{portfolio_id}/recommendations")
async def get_recommendations(
    portfolio_id: str,
    manager: PortfolioManager = Depends(get_manager)
):
    """Get portfolio recommendations"""
    return await manager._generate_recommendations(portfolio_id)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PortfolioManager',
    'PortfolioManagerStatus',
    'OrderExecutionStyle',
    'PortfolioManagerRequest',
    'PortfolioManagerResponse',
    'OrderRequest',
    'OrderResponse',
    'PortfolioManagerContext',
    'ExecutionResult',
    'router'
]
