"""
NEXUS AI TRADING SYSTEM - Paper Trading Portfolio Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/paper-trading/paper_portfolio.py
Description: Paper trading portfolio management with full API integration
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
from shared.constants.trading_constants import ASSET_CLASSES, POSITION_DIRECTIONS
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.repositories.position_repository import PositionRepository
from backend.database.repositories.trade_repository import TradeRepository

# Paper trading imports
from trading.paper_trading.paper_account import PaperTradingAccount
from trading.paper_trading.paper_market import PaperTradingMarket
from trading.paper_trading.paper_fees import PaperTradingFees

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class PortfolioStatus(str, Enum):
    """Portfolio status"""
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    LIQUIDATED = "liquidated"


class PositionSide(str, Enum):
    """Position side"""
    LONG = "long"
    SHORT = "short"


class PositionStatus(str, Enum):
    """Position status"""
    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class PortfolioRequest(BaseModel):
    """Request model for portfolio operations"""
    account_id: str
    action: str = "create"  # create, get, update, close
    parameters: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PortfolioResponse(BaseModel):
    """Response model for portfolio"""
    portfolio_id: str
    account_id: str
    status: PortfolioStatus
    total_value: float
    cash_balance: float
    positions_value: float
    total_pnl: float
    total_pnl_pct: float
    positions_count: int
    created_at: datetime
    updated_at: datetime
    summary: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PositionRequest(BaseModel):
    """Request model for position operations"""
    account_id: str
    symbol: str
    side: PositionSide
    size: float
    entry_price: float
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('size')
    def validate_size(cls, v):
        if v <= 0:
            raise ValueError("Size must be positive")
        return v

    @validator('entry_price')
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError("Entry price must be positive")
        return v


class PositionResponse(BaseModel):
    """Response model for position"""
    position_id: str
    account_id: str
    symbol: str
    side: PositionSide
    size: float
    entry_price: float
    current_price: float
    pnl: float
    pnl_pct: float
    value: float
    status: PositionStatus
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PortfolioMetricsResponse(BaseModel):
    """Response model for portfolio metrics"""
    portfolio_id: str
    account_id: str
    total_value: float
    cash_balance: float
    positions_value: float
    total_pnl: float
    total_pnl_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    current_drawdown: float
    win_rate: float
    profit_factor: float
    avg_trade_pnl: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PortfolioState:
    """Portfolio state"""
    portfolio_id: str
    account_id: str
    status: PortfolioStatus
    cash_balance: float
    positions: List[Dict[str, Any]]
    trades: List[Dict[str, Any]]
    total_value: float
    total_pnl: float
    total_pnl_pct: float
    timestamp: datetime


@dataclass
class PositionContext:
    """Position context"""
    position_id: str
    account_id: str
    symbol: str
    side: PositionSide
    size: float
    entry_price: float
    current_price: float
    pnl: float
    pnl_pct: float
    value: float
    status: PositionStatus
    created_at: datetime
    updated_at: datetime


# =============================================================================
# PAPER TRADING PORTFOLIO
# =============================================================================

class PaperTradingPortfolio:
    """
    Paper Trading Portfolio Management with full API integration.
    
    Features:
    - Portfolio creation and management
    - Position management
    - Balance tracking
    - PnL calculation
    - Performance metrics
    - Risk metrics
    - Portfolio analytics
    """

    def __init__(
        self,
        config: Optional[PaperTradingConfig] = None,
        position_repo: Optional[PositionRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        paper_account: Optional[PaperTradingAccount] = None,
        paper_market: Optional[PaperTradingMarket] = None,
        paper_fees: Optional[PaperTradingFees] = None
    ):
        """
        Initialize PaperTradingPortfolio.
        
        Args:
            config: Paper trading configuration
            position_repo: Position repository
            trade_repo: Trade repository
            paper_account: Paper trading account
            paper_market: Paper trading market
            paper_fees: Paper trading fees
        """
        self.config = config or PaperTradingConfig()
        self.position_repo = position_repo or PositionRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.paper_account = paper_account or PaperTradingAccount()
        self.paper_market = paper_market or PaperTradingMarket()
        self.paper_fees = paper_fees or PaperTradingFees()
        
        # Portfolio cache
        self._portfolios: Dict[str, PortfolioState] = {}
        self._portfolio_info: Dict[str, Dict[str, Any]] = {}
        
        # Position cache
        self._positions: Dict[str, PositionContext] = {}
        
        # Performance tracking
        self._performance_metrics: Dict[str, Dict[str, float]] = {}
        
        # Counter
        self._portfolio_counter: int = 0
        self._position_counter: int = 0
        
        logger.info("PaperTradingPortfolio initialized")

    # =========================================================================
    # Portfolio Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def create_portfolio(
        self,
        request: PortfolioRequest
    ) -> PortfolioResponse:
        """
        Create a paper trading portfolio.
        
        Args:
            request: Portfolio request
            
        Returns:
            PortfolioResponse: Created portfolio
        """
        try:
            # Get account
            account = await self.paper_account.get_account(request.account_id)
            if not account:
                raise ValueError(f"Account {request.account_id} not found")
            
            # Generate portfolio ID
            self._portfolio_counter += 1
            portfolio_id = f"port_{int(time.time() * 1000)}_{self._portfolio_counter:06d}"
            
            # Initialize portfolio state
            state = PortfolioState(
                portfolio_id=portfolio_id,
                account_id=request.account_id,
                status=PortfolioStatus.ACTIVE,
                cash_balance=account.balance,
                positions=[],
                trades=[],
                total_value=account.equity,
                total_pnl=0,
                total_pnl_pct=0,
                timestamp=datetime.utcnow()
            )
            
            # Store portfolio
            self._portfolios[portfolio_id] = state
            self._portfolio_info[portfolio_id] = {
                'account_id': request.account_id,
                'created_at': datetime.utcnow(),
                'metadata': request.metadata
            }
            
            logger.info(f"Portfolio {portfolio_id} created for account {request.account_id}")
            return self._to_portfolio_response(portfolio_id)
            
        except Exception as e:
            logger.error(f"Error creating portfolio: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Portfolio creation failed: {str(e)}"
            )

    async def get_portfolio(self, portfolio_id: str) -> PortfolioResponse:
        """
        Get portfolio details.
        
        Args:
            portfolio_id: Portfolio ID
            
        Returns:
            PortfolioResponse: Portfolio details
        """
        if portfolio_id not in self._portfolios:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Portfolio {portfolio_id} not found"
            )
        
        # Update portfolio
        await self._update_portfolio(portfolio_id)
        
        return self._to_portfolio_response(portfolio_id)

    async def get_all_portfolios(self) -> List[PortfolioResponse]:
        """Get all portfolios"""
        responses = []
        for portfolio_id in self._portfolios:
            try:
                response = await self.get_portfolio(portfolio_id)
                responses.append(response)
            except Exception as e:
                logger.error(f"Error getting portfolio {portfolio_id}: {e}")
        return responses

    async def close_portfolio(self, portfolio_id: str) -> Dict[str, Any]:
        """
        Close a portfolio.
        
        Args:
            portfolio_id: Portfolio ID
            
        Returns:
            Dict[str, Any]: Close result
        """
        if portfolio_id not in self._portfolios:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Portfolio {portfolio_id} not found"
            )
        
        state = self._portfolios[portfolio_id]
        state.status = PortfolioStatus.STOPPED
        
        # Liquidate all positions
        for position in state.positions:
            await self.close_position(position['position_id'])
        
        logger.info(f"Portfolio {portfolio_id} closed")
        
        return {
            'portfolio_id': portfolio_id,
            'status': 'closed',
            'timestamp': datetime.utcnow()
        }

    def _to_portfolio_response(self, portfolio_id: str) -> PortfolioResponse:
        """Convert portfolio to response"""
        state = self._portfolios[portfolio_id]
        info = self._portfolio_info[portfolio_id]
        
        return PortfolioResponse(
            portfolio_id=portfolio_id,
            account_id=state.account_id,
            status=state.status,
            total_value=state.total_value,
            cash_balance=state.cash_balance,
            positions_value=sum(p.get('value', 0) for p in state.positions),
            total_pnl=state.total_pnl,
            total_pnl_pct=state.total_pnl_pct,
            positions_count=len(state.positions),
            created_at=info['created_at'],
            updated_at=state.timestamp,
            summary={
                'positions': len(state.positions),
                'trades': len(state.trades)
            },
            metadata=info.get('metadata', {})
        )

    # =========================================================================
    # Position Management
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def open_position(
        self,
        request: PositionRequest
    ) -> PositionResponse:
        """
        Open a position.
        
        Args:
            request: Position request
            
        Returns:
            PositionResponse: Created position
        """
        try:
            # Get portfolio
            portfolio_id = await self._get_portfolio_for_account(request.account_id)
            if not portfolio_id:
                raise ValueError(f"No portfolio found for account {request.account_id}")
            
            state = self._portfolios[portfolio_id]
            
            # Check if position already exists
            existing_pos = None
            for pos in state.positions:
                if pos['symbol'] == request.symbol and pos['side'] == request.side.value:
                    existing_pos = pos
                    break
            
            # Calculate position value
            position_value = request.size * request.entry_price
            
            # Check sufficient balance
            if request.side == PositionSide.LONG:
                if state.cash_balance < position_value:
                    raise ValueError(f"Insufficient balance. Need {position_value:.2f}, have {state.cash_balance:.2f}")
            else:  # SHORT
                margin_required = position_value * 0.5
                if state.cash_balance < margin_required:
                    raise ValueError(f"Insufficient margin. Need {margin_required:.2f}, have {state.cash_balance:.2f}")
            
            # Generate position ID
            self._position_counter += 1
            position_id = f"pos_{int(time.time() * 1000)}_{self._position_counter:06d}"
            
            # Update cash balance
            if request.side == PositionSide.LONG:
                state.cash_balance -= position_value
            else:  # SHORT
                state.cash_balance -= position_value * 0.5  # Margin
            
            # Create or update position
            if existing_pos:
                # Update existing position
                total_size = existing_pos['size'] + request.size
                total_cost = existing_pos['size'] * existing_pos['entry_price'] + request.size * request.entry_price
                existing_pos['size'] = total_size
                existing_pos['entry_price'] = total_cost / total_size if total_size > 0 else 0
                existing_pos['updated_at'] = datetime.utcnow()
                position_id = existing_pos['position_id']
            else:
                # Create new position
                new_position = {
                    'position_id': position_id,
                    'symbol': request.symbol,
                    'side': request.side.value,
                    'size': request.size,
                    'entry_price': request.entry_price,
                    'current_price': request.entry_price,
                    'pnl': 0,
                    'pnl_pct': 0,
                    'value': position_value,
                    'status': PositionStatus.OPEN.value,
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                }
                state.positions.append(new_position)
            
            # Update portfolio
            state.total_value = state.cash_balance + sum(p.get('value', 0) for p in state.positions)
            state.timestamp = datetime.utcnow()
            
            # Create position context
            context = PositionContext(
                position_id=position_id,
                account_id=request.account_id,
                symbol=request.symbol,
                side=request.side,
                size=request.size,
                entry_price=request.entry_price,
                current_price=request.entry_price,
                pnl=0,
                pnl_pct=0,
                value=position_value,
                status=PositionStatus.OPEN,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            self._positions[position_id] = context
            
            logger.info(f"Position {position_id} opened for {request.symbol}")
            return self._to_position_response(position_id)
            
        except Exception as e:
            logger.error(f"Error opening position: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Position opening failed: {str(e)}"
            )

    async def close_position(
        self,
        position_id: str
    ) -> Dict[str, Any]:
        """
        Close a position.
        
        Args:
            position_id: Position ID
            
        Returns:
            Dict[str, Any]: Close result
        """
        try:
            if position_id not in self._positions:
                raise ValueError(f"Position {position_id} not found")
            
            context = self._positions[position_id]
            portfolio_id = await self._get_portfolio_for_account(context.account_id)
            state = self._portfolios[portfolio_id]
            
            # Get current price
            market_data = await self.paper_market.get_market_data(context.symbol)
            current_price = market_data.price
            
            # Calculate PnL
            if context.side == PositionSide.LONG:
                pnl = (current_price - context.entry_price) * context.size
            else:  # SHORT
                pnl = (context.entry_price - current_price) * context.size
            
            # Calculate fees
            fee_request = {
                'symbol': context.symbol,
                'side': 'sell' if context.side == PositionSide.LONG else 'buy',
                'size': context.size,
                'price': current_price,
                'order_type': 'market'
            }
            fee_response = await self.paper_fees.calculate_fee(fee_request)
            pnl -= fee_response.fee_amount
            
            # Update cash balance
            if context.side == PositionSide.LONG:
                state.cash_balance += (context.size * current_price - fee_response.fee_amount)
            else:  # SHORT
                state.cash_balance -= (context.size * current_price + fee_response.fee_amount)
            
            # Remove position
            state.positions = [p for p in state.positions if p['position_id'] != position_id]
            
            # Update portfolio
            state.total_pnl += pnl
            state.total_pnl_pct = state.total_pnl / (state.total_value - pnl) * 100 if state.total_value - pnl > 0 else 0
            state.total_value = state.cash_balance + sum(p.get('value', 0) for p in state.positions)
            state.timestamp = datetime.utcnow()
            
            # Update position status
            context.status = PositionStatus.CLOSED
            context.current_price = current_price
            context.pnl = pnl
            context.pnl_pct = pnl / (context.size * context.entry_price) * 100 if context.size * context.entry_price > 0 else 0
            context.updated_at = datetime.utcnow()
            
            # Update cache
            self._positions[position_id] = context
            
            logger.info(f"Position {position_id} closed with PnL: {pnl:.2f}")
            
            return {
                'position_id': position_id,
                'symbol': context.symbol,
                'side': context.side.value,
                'size': context.size,
                'entry_price': context.entry_price,
                'exit_price': current_price,
                'pnl': pnl,
                'pnl_pct': context.pnl_pct,
                'fee': fee_response.fee_amount,
                'timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error closing position: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Position closing failed: {str(e)}"
            )

    async def get_position(self, position_id: str) -> PositionResponse:
        """
        Get position by ID.
        
        Args:
            position_id: Position ID
            
        Returns:
            PositionResponse: Position details
        """
        if position_id not in self._positions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Position {position_id} not found"
            )
        
        # Update position
        await self._update_position(position_id)
        
        return self._to_position_response(position_id)

    async def get_positions(
        self,
        account_id: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[PositionResponse]:
        """
        Get positions with filters.
        
        Args:
            account_id: Filter by account
            symbol: Filter by symbol
            status: Filter by status
            
        Returns:
            List[PositionResponse]: Positions
        """
        positions = list(self._positions.values())
        
        if account_id:
            positions = [p for p in positions if p.account_id == account_id]
        
        if symbol:
            positions = [p for p in positions if p.symbol == symbol]
        
        if status:
            positions = [p for p in positions if p.status.value == status]
        
        # Update positions
        for position in positions:
            await self._update_position(position.position_id)
        
        return [self._to_position_response(p.position_id) for p in positions]

    def _to_position_response(self, position_id: str) -> PositionResponse:
        """Convert position to response"""
        context = self._positions[position_id]
        
        return PositionResponse(
            position_id=context.position_id,
            account_id=context.account_id,
            symbol=context.symbol,
            side=context.side,
            size=context.size,
            entry_price=context.entry_price,
            current_price=context.current_price,
            pnl=context.pnl,
            pnl_pct=context.pnl_pct,
            value=context.value,
            status=context.status,
            created_at=context.created_at,
            updated_at=context.updated_at,
            metadata=context.metadata if hasattr(context, 'metadata') else {}
        )

    # =========================================================================
    # Portfolio Metrics
    # =========================================================================

    async def get_metrics(
        self,
        portfolio_id: str
    ) -> PortfolioMetricsResponse:
        """
        Get portfolio metrics.
        
        Args:
            portfolio_id: Portfolio ID
            
        Returns:
            PortfolioMetricsResponse: Portfolio metrics
        """
        if portfolio_id not in self._portfolios:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Portfolio {portfolio_id} not found"
            )
        
        state = self._portfolios[portfolio_id]
        
        # Calculate metrics
        metrics = {}
        
        # Sharpe ratio
        if state.trades:
            pnls = [t.get('pnl', 0) for t in state.trades]
            if pnls:
                returns = [p / state.total_value for p in pnls if state.total_value > 0]
                metrics['sharpe_ratio'] = self._calculate_sharpe_ratio(returns)
                metrics['sortino_ratio'] = self._calculate_sortino_ratio(returns)
                metrics['calmar_ratio'] = self._calculate_calmar_ratio(returns)
                
                # Win rate
                wins = [p for p in pnls if p > 0]
                losses = [p for p in pnls if p < 0]
                metrics['win_rate'] = len(wins) / len(pnls) if pnls else 0
                metrics['winning_trades'] = len(wins)
                metrics['losing_trades'] = len(losses)
                metrics['total_trades'] = len(pnls)
                metrics['avg_trade_pnl'] = np.mean(pnls) if pnls else 0
                
                # Profit factor
                gross_profit = sum(wins)
                gross_loss = abs(sum(losses))
                metrics['profit_factor'] = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Drawdown
        if state.trades:
            equity = [state.total_value]
            for trade in state.trades:
                pnl = trade.get('pnl', 0)
                equity.append(equity[-1] + pnl)
            
            peak = max(equity)
            current_drawdown = (peak - equity[-1]) / peak if peak > 0 else 0
            metrics['current_drawdown'] = current_drawdown
            
            # Max drawdown
            max_dd = 0
            peak = equity[0]
            for value in equity:
                if value > peak:
                    peak = value
                dd = (peak - value) / peak if peak > 0 else 0
                max_dd = max(max_dd, dd)
            metrics['max_drawdown'] = max_dd
        else:
            metrics['current_drawdown'] = 0
            metrics['max_drawdown'] = 0
        
        return PortfolioMetricsResponse(
            portfolio_id=portfolio_id,
            account_id=state.account_id,
            total_value=state.total_value,
            cash_balance=state.cash_balance,
            positions_value=sum(p.get('value', 0) for p in state.positions),
            total_pnl=state.total_pnl,
            total_pnl_pct=state.total_pnl_pct,
            sharpe_ratio=metrics.get('sharpe_ratio', 0),
            sortino_ratio=metrics.get('sortino_ratio', 0),
            calmar_ratio=metrics.get('calmar_ratio', 0),
            max_drawdown=metrics.get('max_drawdown', 0),
            current_drawdown=metrics.get('current_drawdown', 0),
            win_rate=metrics.get('win_rate', 0),
            profit_factor=metrics.get('profit_factor', 0),
            avg_trade_pnl=metrics.get('avg_trade_pnl', 0),
            total_trades=metrics.get('total_trades', 0),
            winning_trades=metrics.get('winning_trades', 0),
            losing_trades=metrics.get('losing_trades', 0),
            metadata={}
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _update_portfolio(self, portfolio_id: str) -> None:
        """Update portfolio state"""
        if portfolio_id not in self._portfolios:
            return
        
        state = self._portfolios[portfolio_id]
        
        # Update positions
        for position in state.positions:
            try:
                market_data = await self.paper_market.get_market_data(position['symbol'])
                current_price = market_data.price
                position['current_price'] = current_price
                
                if position['side'] == 'long':
                    pnl = (current_price - position['entry_price']) * position['size']
                else:
                    pnl = (position['entry_price'] - current_price) * position['size']
                
                position['pnl'] = pnl
                position['pnl_pct'] = pnl / (position['size'] * position['entry_price']) * 100 if position['size'] * position['entry_price'] > 0 else 0
                position['value'] = position['size'] * current_price
            except Exception as e:
                logger.warning(f"Error updating position {position['symbol']}: {e}")
        
        # Update totals
        state.total_value = state.cash_balance + sum(p.get('value', 0) for p in state.positions)
        state.timestamp = datetime.utcnow()

    async def _update_position(self, position_id: str) -> None:
        """Update position state"""
        if position_id not in self._positions:
            return
        
        context = self._positions[position_id]
        
        try:
            market_data = await self.paper_market.get_market_data(context.symbol)
            current_price = market_data.price
            context.current_price = current_price
            
            if context.side == PositionSide.LONG:
                pnl = (current_price - context.entry_price) * context.size
            else:
                pnl = (context.entry_price - current_price) * context.size
            
            context.pnl = pnl
            context.pnl_pct = pnl / (context.size * context.entry_price) * 100 if context.size * context.entry_price > 0 else 0
            context.value = context.size * current_price
            context.updated_at = datetime.utcnow()
            
            self._positions[position_id] = context
        except Exception as e:
            logger.warning(f"Error updating position {position_id}: {e}")

    async def _get_portfolio_for_account(self, account_id: str) -> Optional[str]:
        """Get portfolio ID for account"""
        for portfolio_id, state in self._portfolios.items():
            if state.account_id == account_id:
                return portfolio_id
        return None

    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio"""
        if not returns:
            return 0
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        if std_return == 0:
            return 0
        return avg_return / std_return * np.sqrt(252)

    def _calculate_sortino_ratio(self, returns: List[float]) -> float:
        """Calculate Sortino ratio"""
        if not returns:
            return 0
        avg_return = np.mean(returns)
        downside_returns = [r for r in returns if r < 0]
        if not downside_returns:
            return 0
        downside_std = np.std(downside_returns)
        if downside_std == 0:
            return 0
        return avg_return / downside_std * np.sqrt(252)

    def _calculate_calmar_ratio(self, returns: List[float]) -> float:
        """Calculate Calmar ratio"""
        if not returns:
            return 0
        avg_return = np.mean(returns) * 252
        max_dd = self._calculate_max_drawdown(returns)
        if max_dd == 0:
            return 0
        return avg_return / max_dd

    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate max drawdown"""
        if not returns:
            return 0
        equity = [100]
        for r in returns:
            equity.append(equity[-1] * (1 + r))
        
        peak = equity[0]
        max_dd = 0
        for value in equity:
            if value > peak:
                peak = value
            dd = (peak - value) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        return max_dd

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the portfolio module"""
        # Close all portfolios
        for portfolio_id in list(self._portfolios.keys()):
            try:
                await self.close_portfolio(portfolio_id)
            except Exception as e:
                logger.error(f"Error closing portfolio {portfolio_id}: {e}")
        
        self._portfolios.clear()
        self._portfolio_info.clear()
        self._positions.clear()
        self._performance_metrics.clear()
        
        logger.info("PaperTradingPortfolio closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/paper-trading/portfolio", tags=["Paper Trading Portfolio"])


async def get_portfolio() -> PaperTradingPortfolio:
    """Dependency to get PaperTradingPortfolio instance"""
    return PaperTradingPortfolio()


@router.post("/create", response_model=PortfolioResponse)
async def create_portfolio(
    request: PortfolioRequest,
    portfolio: PaperTradingPortfolio = Depends(get_portfolio)
):
    """Create a paper trading portfolio"""
    return await portfolio.create_portfolio(request)


@router.get("/{portfolio_id}", response_model=PortfolioResponse)
async def get_portfolio(
    portfolio_id: str,
    portfolio: PaperTradingPortfolio = Depends(get_portfolio)
):
    """Get portfolio details"""
    return await portfolio.get_portfolio(portfolio_id)


@router.get("/")
async def get_all_portfolios(
    portfolio: PaperTradingPortfolio = Depends(get_portfolio)
):
    """Get all portfolios"""
    return await portfolio.get_all_portfolios()


@router.post("/{portfolio_id}/close")
async def close_portfolio(
    portfolio_id: str,
    portfolio: PaperTradingPortfolio = Depends(get_portfolio)
):
    """Close a portfolio"""
    return await portfolio.close_portfolio(portfolio_id)


@router.post("/position/open", response_model=PositionResponse)
async def open_position(
    request: PositionRequest,
    portfolio: PaperTradingPortfolio = Depends(get_portfolio)
):
    """Open a position"""
    return await portfolio.open_position(request)


@router.get("/position/{position_id}", response_model=PositionResponse)
async def get_position(
    position_id: str,
    portfolio: PaperTradingPortfolio = Depends(get_portfolio)
):
    """Get position by ID"""
    return await portfolio.get_position(position_id)


@router.post("/position/{position_id}/close")
async def close_position(
    position_id: str,
    portfolio: PaperTradingPortfolio = Depends(get_portfolio)
):
    """Close a position"""
    return await portfolio.close_position(position_id)


@router.get("/{portfolio_id}/metrics")
async def get_portfolio_metrics(
    portfolio_id: str,
    portfolio: PaperTradingPortfolio = Depends(get_portfolio)
):
    """Get portfolio metrics"""
    return await portfolio.get_metrics(portfolio_id)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PaperTradingPortfolio',
    'PortfolioStatus',
    'PositionSide',
    'PositionStatus',
    'PortfolioRequest',
    'PortfolioResponse',
    'PositionRequest',
    'PositionResponse',
    'PortfolioMetricsResponse',
    'PortfolioState',
    'PositionContext',
    'router'
]
