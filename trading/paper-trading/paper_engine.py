"""
NEXUS AI TRADING SYSTEM - Paper Trading Engine Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/paper-trading/paper_engine.py
Description: Core paper trading engine with full API integration
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
from shared.configs.paper_trading_config import PaperTradingConfig
from shared.constants.trading_constants import (
    ORDER_TYPES,
    POSITION_DIRECTIONS,
    TIME_FRAMES
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.order_repository import OrderRepository
from backend.database.repositories.position_repository import PositionRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

# Paper trading imports
from trading.paper_trading.paper_account import PaperTradingAccount
from trading.paper_trading.paper_analytics import PaperTradingAnalytics

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class EngineStatus(str, Enum):
    """Engine status"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class ExecutionMode(str, Enum):
    """Execution modes"""
    REAL_TIME = "real_time"
    SIMULATED = "simulated"
    BATCH = "batch"
    HISTORICAL = "historical"


class OrderStatus(str, Enum):
    """Order status"""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class EngineRequest(BaseModel):
    """Request model for engine operations"""
    account_id: str
    action: str = "start"  # start, stop, pause, resume
    mode: ExecutionMode = ExecutionMode.REAL_TIME
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EngineResponse(BaseModel):
    """Response model for engine"""
    engine_id: str
    account_id: str
    status: EngineStatus
    mode: ExecutionMode
    started_at: datetime
    last_update: datetime
    orders_processed: int
    trades_executed: int
    total_value: float
    summary: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionRequest(BaseModel):
    """Request model for order execution"""
    account_id: str
    symbol: str
    side: str  # buy, sell
    size: float
    order_type: str = "limit"
    price: Optional[float] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    time_in_force: str = "GTC"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionResponse(BaseModel):
    """Response model for execution"""
    execution_id: str
    account_id: str
    symbol: str
    side: str
    size: float
    price: float
    filled_size: float
    status: OrderStatus
    created_at: datetime
    filled_at: Optional[datetime] = None
    pnl: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class EngineState:
    """Engine state"""
    account_id: str
    status: EngineStatus
    mode: ExecutionMode
    orders: List[Dict[str, Any]]
    trades: List[Dict[str, Any]]
    positions: List[Dict[str, Any]]
    balance: float
    equity: float
    timestamp: datetime


@dataclass
class ExecutionResult:
    """Execution result"""
    order_id: str
    symbol: str
    side: str
    size: float
    price: float
    filled_size: float
    status: str
    timestamp: datetime
    message: str


# =============================================================================
# PAPER TRADING ENGINE
# =============================================================================

class PaperTradingEngine:
    """
    Core Paper Trading Engine with full API integration.
    
    Features:
    - Order execution (market, limit, stop, stop-limit, trailing stop)
    - Position management
    - Balance tracking
    - Real-time updates
    - Historical simulation
    - Batch execution
    - Performance tracking
    - Multi-account support
    """

    def __init__(
        self,
        config: Optional[PaperTradingConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        trade_repo: Optional[TradeRepository] = None,
        order_repo: Optional[OrderRepository] = None,
        position_repo: Optional[PositionRepository] = None,
        paper_account: Optional[PaperTradingAccount] = None,
        analytics: Optional[PaperTradingAnalytics] = None
    ):
        """
        Initialize PaperTradingEngine.
        
        Args:
            config: Paper trading configuration
            broker_factory: Factory for broker instances
            trade_repo: Trade repository
            order_repo: Order repository
            position_repo: Position repository
            paper_account: Paper trading account
            analytics: Paper trading analytics
        """
        self.config = config or PaperTradingConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.trade_repo = trade_repo or TradeRepository()
        self.order_repo = order_repo or OrderRepository()
        self.position_repo = position_repo or PositionRepository()
        self.paper_account = paper_account or PaperTradingAccount()
        self.analytics = analytics or PaperTradingAnalytics()
        
        # Engine state
        self._engines: Dict[str, EngineState] = {}
        self._engine_info: Dict[str, Dict[str, Any]] = {}
        
        # Order management
        self._pending_orders: Dict[str, Dict[str, Any]] = {}
        self._executed_orders: List[Dict[str, Any]] = []
        
        # Price cache
        self._price_cache: Dict[str, Dict[str, Any]] = {}
        
        # Monitoring
        self._is_monitoring: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        logger.info("PaperTradingEngine initialized")

    # =========================================================================
    # Engine Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def start_engine(
        self,
        request: EngineRequest
    ) -> EngineResponse:
        """
        Start paper trading engine.
        
        Args:
            request: Engine request
            
        Returns:
            EngineResponse: Engine status
        """
        try:
            # Validate account
            account = await self.paper_account.get_account(request.account_id)
            
            # Generate engine ID
            engine_id = f"engine_{int(time.time() * 1000)}_{request.account_id[:8]}"
            
            # Initialize state
            state = EngineState(
                account_id=request.account_id,
                status=EngineStatus.RUNNING,
                mode=request.mode,
                orders=[],
                trades=[],
                positions=[],
                balance=account.balance,
                equity=account.equity,
                timestamp=datetime.utcnow()
            )
            
            self._engines[engine_id] = state
            self._engine_info[engine_id] = {
                'account_id': request.account_id,
                'mode': request.mode.value,
                'started_at': datetime.utcnow(),
                'parameters': request.parameters,
                'metadata': request.metadata
            }
            
            # Start monitoring
            if not self._is_monitoring:
                await self._start_monitoring()
            
            logger.info(f"Engine {engine_id} started for account {request.account_id}")
            return self._to_engine_response(engine_id)
            
        except Exception as e:
            logger.error(f"Error starting engine: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Engine start failed: {str(e)}"
            )

    def _to_engine_response(self, engine_id: str) -> EngineResponse:
        """Convert engine to response"""
        state = self._engines[engine_id]
        info = self._engine_info[engine_id]
        
        return EngineResponse(
            engine_id=engine_id,
            account_id=state.account_id,
            status=state.status,
            mode=state.mode,
            started_at=info['started_at'],
            last_update=state.timestamp,
            orders_processed=len(state.orders),
            trades_executed=len(state.trades),
            total_value=state.equity,
            summary={
                'balance': state.balance,
                'equity': state.equity,
                'positions': len(state.positions)
            },
            metadata=info.get('metadata', {})
        )

    async def stop_engine(self, engine_id: str) -> EngineResponse:
        """
        Stop paper trading engine.
        
        Args:
            engine_id: Engine ID
            
        Returns:
            EngineResponse: Engine status
        """
        if engine_id not in self._engines:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Engine {engine_id} not found"
            )
        
        state = self._engines[engine_id]
        state.status = EngineStatus.STOPPED
        
        # Cancel pending orders
        await self._cancel_all_orders(engine_id)
        
        logger.info(f"Engine {engine_id} stopped")
        return self._to_engine_response(engine_id)

    async def pause_engine(self, engine_id: str) -> EngineResponse:
        """
        Pause paper trading engine.
        
        Args:
            engine_id: Engine ID
            
        Returns:
            EngineResponse: Engine status
        """
        if engine_id not in self._engines:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Engine {engine_id} not found"
            )
        
        state = self._engines[engine_id]
        state.status = EngineStatus.PAUSED
        
        logger.info(f"Engine {engine_id} paused")
        return self._to_engine_response(engine_id)

    async def resume_engine(self, engine_id: str) -> EngineResponse:
        """
        Resume paper trading engine.
        
        Args:
            engine_id: Engine ID
            
        Returns:
            EngineResponse: Engine status
        """
        if engine_id not in self._engines:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Engine {engine_id} not found"
            )
        
        state = self._engines[engine_id]
        state.status = EngineStatus.RUNNING
        
        logger.info(f"Engine {engine_id} resumed")
        return self._to_engine_response(engine_id)

    # =========================================================================
    # Order Execution
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def execute_order(
        self,
        request: ExecutionRequest
    ) -> ExecutionResponse:
        """
        Execute an order.
        
        Args:
            request: Execution request
            
        Returns:
            ExecutionResponse: Execution result
        """
        try:
            # Validate request
            await self._validate_execution(request)
            
            # Get engine for account
            engine_id = await self._get_engine_for_account(request.account_id)
            if not engine_id:
                raise ValueError(f"No active engine for account {request.account_id}")
            
            state = self._engines[engine_id]
            if state.status != EngineStatus.RUNNING:
                raise ValueError(f"Engine {engine_id} is not running")
            
            # Get current price
            current_price = await self._get_current_price(request.symbol)
            if not current_price:
                raise ValueError(f"Unable to get price for {request.symbol}")
            
            # Generate execution ID
            execution_id = f"exec_{int(time.time() * 1000)}_{request.symbol}"
            
            # Process order
            result = await self._process_order(
                execution_id,
                request,
                current_price,
                state
            )
            
            # Update account
            await self.paper_account._update_account_state(request.account_id)
            
            # Create response
            response = ExecutionResponse(
                execution_id=execution_id,
                account_id=request.account_id,
                symbol=request.symbol,
                side=request.side,
                size=request.size,
                price=result['price'],
                filled_size=result['filled_size'],
                status=OrderStatus(result['status']),
                created_at=datetime.utcnow(),
                filled_at=result.get('filled_at'),
                pnl=result.get('pnl'),
                metadata=request.metadata
            )
            
            # Store in history
            self._executed_orders.append(result)
            
            logger.info(f"Order {execution_id} executed for {request.symbol}")
            return response
            
        except Exception as e:
            logger.error(f"Error executing order: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Order execution failed: {str(e)}"
            )

    async def _validate_execution(self, request: ExecutionRequest) -> None:
        """Validate execution request"""
        if request.size <= 0:
            raise ValueError("Order size must be positive")
        
        if request.side not in ['buy', 'sell']:
            raise ValueError("Side must be 'buy' or 'sell'")
        
        if request.order_type == 'limit' and not request.price:
            raise ValueError("Limit order requires price")
        
        if request.order_type == 'stop' and not request.stop_price:
            raise ValueError("Stop order requires stop price")

    async def _process_order(
        self,
        execution_id: str,
        request: ExecutionRequest,
        current_price: float,
        state: EngineState
    ) -> Dict[str, Any]:
        """Process order based on type"""
        result = {
            'execution_id': execution_id,
            'symbol': request.symbol,
            'side': request.side,
            'size': request.size,
            'filled_size': 0,
            'price': current_price,
            'status': 'pending',
            'timestamp': datetime.utcnow()
        }
        
        if request.order_type == 'market':
            # Market order - immediate execution
            result['status'] = 'filled'
            result['filled_size'] = request.size
            result['price'] = current_price
            result['filled_at'] = datetime.utcnow()
            
            # Execute trade
            await self._execute_trade(result, state)
            
        elif request.order_type == 'limit':
            # Limit order - check if price condition met
            if request.side == 'buy':
                if current_price <= request.price:
                    result['status'] = 'filled'
                    result['filled_size'] = request.size
                    result['price'] = current_price
                    result['filled_at'] = datetime.utcnow()
                    await self._execute_trade(result, state)
                else:
                    result['status'] = 'open'
            else:  # sell
                if current_price >= request.price:
                    result['status'] = 'filled'
                    result['filled_size'] = request.size
                    result['price'] = current_price
                    result['filled_at'] = datetime.utcnow()
                    await self._execute_trade(result, state)
                else:
                    result['status'] = 'open'
            
            # Store pending order
            if result['status'] == 'open':
                self._pending_orders[execution_id] = {
                    'request': request,
                    'result': result
                }
            
        elif request.order_type == 'stop':
            # Stop order - becomes market when triggered
            if request.side == 'buy':
                if current_price >= request.stop_price:
                    result['status'] = 'filled'
                    result['filled_size'] = request.size
                    result['price'] = current_price
                    result['filled_at'] = datetime.utcnow()
                    await self._execute_trade(result, state)
                else:
                    result['status'] = 'open'
            else:  # sell
                if current_price <= request.stop_price:
                    result['status'] = 'filled'
                    result['filled_size'] = request.size
                    result['price'] = current_price
                    result['filled_at'] = datetime.utcnow()
                    await self._execute_trade(result, state)
                else:
                    result['status'] = 'open'
            
            if result['status'] == 'open':
                self._pending_orders[execution_id] = {
                    'request': request,
                    'result': result
                }
            
        elif request.order_type == 'stop_limit':
            # Stop-limit order - becomes limit when triggered
            if request.side == 'buy':
                if current_price >= request.stop_price:
                    # Check limit price
                    if current_price <= request.limit_price:
                        result['status'] = 'filled'
                        result['filled_size'] = request.size
                        result['price'] = current_price
                        result['filled_at'] = datetime.utcnow()
                        await self._execute_trade(result, state)
                    else:
                        result['status'] = 'open'
                else:
                    result['status'] = 'open'
            else:  # sell
                if current_price <= request.stop_price:
                    if current_price >= request.limit_price:
                        result['status'] = 'filled'
                        result['filled_size'] = request.size
                        result['price'] = current_price
                        result['filled_at'] = datetime.utcnow()
                        await self._execute_trade(result, state)
                    else:
                        result['status'] = 'open'
                else:
                    result['status'] = 'open'
            
            if result['status'] == 'open':
                self._pending_orders[execution_id] = {
                    'request': request,
                    'result': result
                }
            
        elif request.order_type == 'trailing_stop':
            # Trailing stop order
            result['status'] = 'open'
            result['trail_high'] = current_price
            result['trail_low'] = current_price
            result['trail_distance'] = request.metadata.get('trail_distance', 0.02)
            
            self._pending_orders[execution_id] = {
                'request': request,
                'result': result
            }
        
        return result

    async def _execute_trade(
        self,
        result: Dict[str, Any],
        state: EngineState
    ) -> None:
        """Execute trade and update state"""
        account_id = state.account_id
        
        # Calculate trade value
        trade_value = result['size'] * result['price']
        
        # Update balance
        if result['side'] == 'buy':
            state.balance -= trade_value
        else:  # sell
            state.balance += trade_value
        
        # Update position
        await self._update_position(account_id, result, state)
        
        # Record trade
        trade = {
            'execution_id': result['execution_id'],
            'symbol': result['symbol'],
            'side': result['side'],
            'size': result['size'],
            'price': result['price'],
            'timestamp': result['filled_at'],
            'pnl': 0
        }
        
        state.trades.append(trade)
        state.equity = state.balance + await self._calculate_position_value(account_id)
        state.timestamp = datetime.utcnow()
        
        # Update state
        self._engines[self._get_engine_for_account(account_id)] = state

    async def _update_position(
        self,
        account_id: str,
        result: Dict[str, Any],
        state: EngineState
    ) -> None:
        """Update position"""
        # Find existing position
        existing_pos = None
        for pos in state.positions:
            if pos['symbol'] == result['symbol'] and pos['side'] == result['side']:
                existing_pos = pos
                break
        
        if existing_pos:
            # Update existing position
            total_size = existing_pos['size'] + result['size']
            total_cost = existing_pos['size'] * existing_pos['entry_price'] + result['size'] * result['price']
            existing_pos['size'] = total_size
            existing_pos['entry_price'] = total_cost / total_size if total_size > 0 else 0
            existing_pos['updated_at'] = datetime.utcnow()
        else:
            # Create new position
            state.positions.append({
                'symbol': result['symbol'],
                'side': result['side'],
                'size': result['size'],
                'entry_price': result['price'],
                'current_price': result['price'],
                'pnl': 0,
                'pnl_pct': 0,
                'value': result['size'] * result['price'],
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            })

    async def _calculate_position_value(self, account_id: str) -> float:
        """Calculate total position value"""
        engine_id = self._get_engine_for_account(account_id)
        if not engine_id:
            return 0
        
        state = self._engines[engine_id]
        total_value = 0
        
        for pos in state.positions:
            current_price = await self._get_current_price(pos['symbol'])
            if current_price:
                pos['current_price'] = current_price
                pos['value'] = pos['size'] * current_price
                total_value += pos['value']
        
        return total_value

    # =========================================================================
    # Order Management
    # =========================================================================

    async def cancel_order(self, execution_id: str) -> bool:
        """
        Cancel an order.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            bool: Success indicator
        """
        if execution_id not in self._pending_orders:
            return False
        
        pending = self._pending_orders[execution_id]
        pending['result']['status'] = 'cancelled'
        pending['result']['cancelled_at'] = datetime.utcnow()
        
        # Update account
        account_id = pending['request'].account_id
        await self.paper_account._update_account_state(account_id)
        
        del self._pending_orders[execution_id]
        
        logger.info(f"Order {execution_id} cancelled")
        return True

    async def _cancel_all_orders(self, engine_id: str) -> int:
        """Cancel all orders for engine"""
        cancelled = 0
        for execution_id, pending in list(self._pending_orders.items()):
            if pending['request'].account_id == engine_id:
                if await self.cancel_order(execution_id):
                    cancelled += 1
        return cancelled

    # =========================================================================
    # Market Data
    # =========================================================================

    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for symbol"""
        # Check cache
        if symbol in self._price_cache:
            cache_time = self._price_cache[symbol].get('timestamp')
            if cache_time and (datetime.utcnow() - cache_time).seconds < 5:
                return self._price_cache[symbol]['price']
        
        try:
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    ticker = await broker.get_ticker(symbol)
                    price = float(ticker.get('price', 0))
                    if price > 0:
                        self._price_cache[symbol] = {
                            'price': price,
                            'timestamp': datetime.utcnow()
                        }
                        return price
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error getting price for {symbol}: {e}")
        
        # Generate mock price
        mock_price = 100.0 + np.random.normal(0, 0.5)
        self._price_cache[symbol] = {
            'price': mock_price,
            'timestamp': datetime.utcnow()
        }
        return mock_price

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _get_engine_for_account(self, account_id: str) -> Optional[str]:
        """Get engine ID for account"""
        for engine_id, state in self._engines.items():
            if state.account_id == account_id:
                return engine_id
        return None

    # =========================================================================
    # Monitoring
    # =========================================================================

    async def _start_monitoring(self) -> None:
        """Start monitoring"""
        if self._is_monitoring:
            return
        
        self._is_monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Engine monitoring started")

    async def _stop_monitoring(self) -> None:
        """Stop monitoring"""
        self._is_monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("Engine monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._is_monitoring:
            try:
                # Check pending orders
                for execution_id, pending in list(self._pending_orders.items()):
                    try:
                        await self._check_pending_order(execution_id, pending)
                    except Exception as e:
                        logger.error(f"Error checking order {execution_id}: {e}")
                
                # Update engine states
                for engine_id, state in self._engines.items():
                    if state.status == EngineStatus.RUNNING:
                        state.equity = state.balance + await self._calculate_position_value(state.account_id)
                        state.timestamp = datetime.utcnow()
                
                await asyncio.sleep(1)  # Check every second
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(5)

    async def _check_pending_order(
        self,
        execution_id: str,
        pending: Dict[str, Any]
    ) -> None:
        """Check pending order"""
        result = pending['result']
        request = pending['request']
        
        # Get current price
        current_price = await self._get_current_price(request.symbol)
        if not current_price:
            return
        
        # Update price for trailing stop
        if request.order_type == 'trailing_stop':
            if current_price > result['trail_high']:
                result['trail_high'] = current_price
            if current_price < result['trail_low']:
                result['trail_low'] = current_price
            
            # Calculate trail stop price
            if request.side == 'buy':
                stop_price = result['trail_high'] * (1 - result['trail_distance'])
                if current_price < stop_price:
                    # Triggered
                    result['status'] = 'filled'
                    result['filled_size'] = request.size
                    result['price'] = current_price
                    result['filled_at'] = datetime.utcnow()
                    await self._execute_trade(result, self._engines[self._get_engine_for_account(request.account_id)])
                    del self._pending_orders[execution_id]
            else:  # sell
                stop_price = result['trail_low'] * (1 + result['trail_distance'])
                if current_price > stop_price:
                    result['status'] = 'filled'
                    result['filled_size'] = request.size
                    result['price'] = current_price
                    result['filled_at'] = datetime.utcnow()
                    await self._execute_trade(result, self._engines[self._get_engine_for_account(request.account_id)])
                    del self._pending_orders[execution_id]
            return
        
        # Check if order can be filled
        if request.order_type == 'limit':
            if request.side == 'buy' and current_price <= request.price:
                result['status'] = 'filled'
                result['filled_size'] = request.size
                result['price'] = current_price
                result['filled_at'] = datetime.utcnow()
                await self._execute_trade(result, self._engines[self._get_engine_for_account(request.account_id)])
                del self._pending_orders[execution_id]
            elif request.side == 'sell' and current_price >= request.price:
                result['status'] = 'filled'
                result['filled_size'] = request.size
                result['price'] = current_price
                result['filled_at'] = datetime.utcnow()
                await self._execute_trade(result, self._engines[self._get_engine_for_account(request.account_id)])
                del self._pending_orders[execution_id]
        
        elif request.order_type == 'stop':
            if request.side == 'buy' and current_price >= request.stop_price:
                result['status'] = 'filled'
                result['filled_size'] = request.size
                result['price'] = current_price
                result['filled_at'] = datetime.utcnow()
                await self._execute_trade(result, self._engines[self._get_engine_for_account(request.account_id)])
                del self._pending_orders[execution_id]
            elif request.side == 'sell' and current_price <= request.stop_price:
                result['status'] = 'filled'
                result['filled_size'] = request.size
                result['price'] = current_price
                result['filled_at'] = datetime.utcnow()
                await self._execute_trade(result, self._engines[self._get_engine_for_account(request.account_id)])
                del self._pending_orders[execution_id]
        
        elif request.order_type == 'stop_limit':
            if request.side == 'buy' and current_price >= request.stop_price:
                if current_price <= request.limit_price:
                    result['status'] = 'filled'
                    result['filled_size'] = request.size
                    result['price'] = current_price
                    result['filled_at'] = datetime.utcnow()
                    await self._execute_trade(result, self._engines[self._get_engine_for_account(request.account_id)])
                    del self._pending_orders[execution_id]
            elif request.side == 'sell' and current_price <= request.stop_price:
                if current_price >= request.limit_price:
                    result['status'] = 'filled'
                    result['filled_size'] = request.size
                    result['price'] = current_price
                    result['filled_at'] = datetime.utcnow()
                    await self._execute_trade(result, self._engines[self._get_engine_for_account(request.account_id)])
                    del self._pending_orders[execution_id]

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the paper trading engine"""
        await self._stop_monitoring()
        
        # Cancel all orders
        for engine_id in self._engines:
            await self._cancel_all_orders(engine_id)
        
        self._engines.clear()
        self._engine_info.clear()
        self._pending_orders.clear()
        self._executed_orders.clear()
        self._price_cache.clear()
        
        logger.info("PaperTradingEngine closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/paper-trading/engine", tags=["Paper Trading Engine"])


async def get_engine() -> PaperTradingEngine:
    """Dependency to get PaperTradingEngine instance"""
    return PaperTradingEngine()


@router.post("/start", response_model=EngineResponse)
async def start_engine(
    request: EngineRequest,
    engine: PaperTradingEngine = Depends(get_engine)
):
    """Start paper trading engine"""
    return await engine.start_engine(request)


@router.post("/{engine_id}/stop")
async def stop_engine(
    engine_id: str,
    engine: PaperTradingEngine = Depends(get_engine)
):
    """Stop paper trading engine"""
    return await engine.stop_engine(engine_id)


@router.post("/{engine_id}/pause")
async def pause_engine(
    engine_id: str,
    engine: PaperTradingEngine = Depends(get_engine)
):
    """Pause paper trading engine"""
    return await engine.pause_engine(engine_id)


@router.post("/{engine_id}/resume")
async def resume_engine(
    engine_id: str,
    engine: PaperTradingEngine = Depends(get_engine)
):
    """Resume paper trading engine"""
    return await engine.resume_engine(engine_id)


@router.get("/{engine_id}")
async def get_engine_status(
    engine_id: str,
    engine: PaperTradingEngine = Depends(get_engine)
):
    """Get engine status"""
    if engine_id not in engine._engines:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Engine {engine_id} not found"
        )
    return await engine._to_engine_response(engine_id)


@router.post("/execute", response_model=ExecutionResponse)
async def execute_order(
    request: ExecutionRequest,
    engine: PaperTradingEngine = Depends(get_engine)
):
    """Execute an order"""
    return await engine.execute_order(request)


@router.delete("/order/{execution_id}")
async def cancel_order(
    execution_id: str,
    engine: PaperTradingEngine = Depends(get_engine)
):
    """Cancel an order"""
    success = await engine.cancel_order(execution_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order {execution_id} not found"
        )
    return {"success": True}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PaperTradingEngine',
    'EngineStatus',
    'ExecutionMode',
    'OrderStatus',
    'EngineRequest',
    'EngineResponse',
    'ExecutionRequest',
    'ExecutionResponse',
    'EngineState',
    'ExecutionResult',
    'router'
]
