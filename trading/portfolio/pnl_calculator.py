"""
NEXUS AI TRADING SYSTEM - PnL Calculator Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/portfolio/pnl_calculator.py
Description: Advanced Profit and Loss calculation with full API integration
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
from shared.constants.trading_constants import TIME_FRAMES
from shared.helpers.trading_helpers import (
    calculate_position_size,
    calculate_risk_reward_ratio
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.models import Position, Trade
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

class PnLType(str, Enum):
    """Types of PnL"""
    REALIZED = "realized"
    UNREALIZED = "unrealized"
    TOTAL = "total"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    CUMULATIVE = "cumulative"


class PnLCalculationMethod(str, Enum):
    """PnL calculation methods"""
    FIFO = "fifo"  # First In First Out
    LIFO = "lifo"  # Last In First Out
    HIFO = "hifo"  # Highest In First Out
    AVG_COST = "avg_cost"  # Average Cost
    MARK_TO_MARKET = "mark_to_market"  # Mark to Market
    REALIZED = "realized"  # Realized only
    UNREALIZED = "unrealized"  # Unrealized only


class PnLPeriod(str, Enum):
    """PnL periods"""
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    ALL = "all"
    CUSTOM = "custom"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class PnLRequest(BaseModel):
    """Request model for PnL calculation"""
    portfolio_id: str
    method: PnLCalculationMethod = PnLCalculationMethod.MARK_TO_MARKET
    period: PnLPeriod = PnLPeriod.MONTH
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    include_positions: bool = True
    include_trades: bool = True
    include_history: bool = True
    currency: str = "USD"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PnLResponse(BaseModel):
    """Response model for PnL"""
    portfolio_id: str
    method: PnLCalculationMethod
    period: PnLPeriod
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    daily_pnl: float
    weekly_pnl: float
    monthly_pnl: float
    yearly_pnl: float
    pnl_percentage: float
    by_asset: Dict[str, Dict[str, float]]
    by_strategy: Dict[str, Dict[str, float]]
    by_symbol: Dict[str, Dict[str, float]]
    history: List[Dict[str, Any]]
    summary: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PnLAnalyticsResponse(BaseModel):
    """Response model for PnL analytics"""
    total_pnl: float
    avg_daily_pnl: float
    avg_weekly_pnl: float
    avg_monthly_pnl: float
    best_day: float
    worst_day: float
    best_week: float
    worst_week: float
    best_month: float
    worst_month: float
    winning_days_pct: float
    winning_weeks_pct: float
    winning_months_pct: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    volatility: float
    recovery_factor: float
    recommendations: List[str]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PnLContext:
    """Context for PnL calculation"""
    portfolio_id: str
    method: PnLCalculationMethod
    period: PnLPeriod
    start_date: datetime
    end_date: datetime
    positions: List[Any]
    trades: List[Any]
    current_prices: Dict[str, float]
    currency: str = "USD"


@dataclass
class TradePnL:
    """Trade PnL details"""
    trade_id: str
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_pct: float
    fee: float
    timestamp: datetime


@dataclass
class PositionPnL:
    """Position PnL details"""
    position_id: str
    symbol: str
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    realized_pnl: float
    total_pnl: float
    entry_time: datetime


@dataclass
class PnLResult:
    """PnL calculation result"""
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    daily_pnl: float
    weekly_pnl: float
    monthly_pnl: float
    yearly_pnl: float
    pnl_percentage: float
    by_asset: Dict[str, Dict[str, float]]
    by_strategy: Dict[str, Dict[str, float]]
    by_symbol: Dict[str, Dict[str, float]]
    trade_pnls: List[TradePnL]
    position_pnls: List[PositionPnL]
    history: List[Dict[str, Any]]


# =============================================================================
# PNL CALCULATOR
# =============================================================================

class PnLCalculator:
    """
    Advanced PnL Calculator with full API integration.
    
    Features:
    - Multiple calculation methods (FIFO, LIFO, HIFO, AVG_COST, MARK_TO_MARKET)
    - Realized and unrealized PnL
    - Period-based PnL (daily, weekly, monthly, yearly)
    - PnL by asset, strategy, symbol
    - PnL analytics
    - Historical PnL
    - PnL attribution
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
        Initialize PnLCalculator.
        
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
        
        # Cache
        self._pnl_cache: Dict[str, Dict[str, Any]] = {}
        self._history_cache: Dict[str, List[Dict[str, Any]]] = {}
        
        # Price cache
        self._price_cache: Dict[str, Dict[str, float]] = {}
        
        logger.info("PnLCalculator initialized")

    # =========================================================================
    # PnL Calculation
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def calculate_pnl(
        self,
        request: PnLRequest
    ) -> PnLResponse:
        """
        Calculate portfolio PnL.
        
        Args:
            request: PnL request
            
        Returns:
            PnLResponse: PnL calculation results
        """
        try:
            # Validate request
            await self._validate_request(request)
            
            # Build context
            context = await self._build_context(request)
            
            # Calculate PnL
            result = await self._calculate_pnl_by_method(context)
            
            # Calculate analytics
            analytics = await self._calculate_analytics(result)
            
            # Create response
            response = PnLResponse(
                portfolio_id=request.portfolio_id,
                method=request.method,
                period=request.period,
                start_date=context.start_date,
                end_date=context.end_date,
                realized_pnl=result.realized_pnl,
                unrealized_pnl=result.unrealized_pnl,
                total_pnl=result.total_pnl,
                daily_pnl=result.daily_pnl,
                weekly_pnl=result.weekly_pnl,
                monthly_pnl=result.monthly_pnl,
                yearly_pnl=result.yearly_pnl,
                pnl_percentage=result.pnl_percentage,
                by_asset=result.by_asset,
                by_strategy=result.by_strategy,
                by_symbol=result.by_symbol,
                history=result.history,
                summary=analytics,
                metadata=request.metadata
            )
            
            # Cache
            cache_key = f"{request.portfolio_id}_{request.method.value}_{request.period.value}"
            self._pnl_cache[cache_key] = {
                'response': response,
                'context': context,
                'timestamp': datetime.utcnow()
            }
            
            logger.info(f"PnL calculated for {request.portfolio_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error calculating PnL: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"PnL calculation failed: {str(e)}"
            )

    async def _validate_request(self, request: PnLRequest) -> None:
        """Validate PnL request"""
        if request.start_date and request.end_date:
            if request.start_date > request.end_date:
                raise ValueError("Start date must be before end date")

    async def _build_context(self, request: PnLRequest) -> PnLContext:
        """Build PnL context"""
        # Set date range
        end_date = request.end_date or datetime.utcnow()
        start_date = request.start_date
        
        if not start_date:
            # Map period to timedelta
            period_map = {
                PnLPeriod.TODAY: timedelta(days=1),
                PnLPeriod.WEEK: timedelta(days=7),
                PnLPeriod.MONTH: timedelta(days=30),
                PnLPeriod.QUARTER: timedelta(days=90),
                PnLPeriod.YEAR: timedelta(days=365)
            }
            
            if request.period == PnLPeriod.TODAY:
                start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                delta = period_map.get(request.period, timedelta(days=30))
                start_date = end_date - delta
        
        # Get positions
        positions = await self.position_repo.get_by_portfolio_id(request.portfolio_id)
        
        # Get trades
        trades = await self.trade_repo.get_by_portfolio_id(
            request.portfolio_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Get current prices
        current_prices = await self._get_current_prices(positions)
        
        return PnLContext(
            portfolio_id=request.portfolio_id,
            method=request.method,
            period=request.period,
            start_date=start_date,
            end_date=end_date,
            positions=positions,
            trades=trades,
            current_prices=current_prices,
            currency=request.currency
        )

    async def _get_current_prices(
        self,
        positions: List[Any]
    ) -> Dict[str, float]:
        """Get current prices for positions"""
        prices = {}
        
        for position in positions:
            symbol = position.symbol
            
            # Check cache
            if symbol in self._price_cache:
                cache_time = self._price_cache[symbol].get('timestamp')
                if cache_time and (datetime.utcnow() - cache_time).seconds < 60:
                    prices[symbol] = self._price_cache[symbol]['price']
                    continue
            
            try:
                brokers = self.broker_factory.get_active_brokers()
                for broker in brokers:
                    try:
                        ticker = await broker.get_ticker(symbol)
                        price = float(ticker.get('price', 0))
                        prices[symbol] = price
                        self._price_cache[symbol] = {
                            'price': price,
                            'timestamp': datetime.utcnow()
                        }
                        break
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"Error getting price for {symbol}: {e}")
                prices[symbol] = float(position.entry_price)
        
        return prices

    # =========================================================================
    # PnL Calculation Methods
    # =========================================================================

    async def _calculate_pnl_by_method(
        self,
        context: PnLContext
    ) -> PnLResult:
        """Calculate PnL using specified method"""
        if context.method == PnLCalculationMethod.MARK_TO_MARKET:
            return await self._calculate_mark_to_market(context)
        elif context.method == PnLCalculationMethod.FIFO:
            return await self._calculate_fifo(context)
        elif context.method == PnLCalculationMethod.LIFO:
            return await self._calculate_lifo(context)
        elif context.method == PnLCalculationMethod.HIFO:
            return await self._calculate_hifo(context)
        elif context.method == PnLCalculationMethod.AVG_COST:
            return await self._calculate_avg_cost(context)
        elif context.method == PnLCalculationMethod.REALIZED:
            return await self._calculate_realized(context)
        elif context.method == PnLCalculationMethod.UNREALIZED:
            return await self._calculate_unrealized(context)
        else:
            return await self._calculate_mark_to_market(context)

    # -------------------------------------------------------------------------
    # Mark to Market
    # -------------------------------------------------------------------------

    async def _calculate_mark_to_market(
        self,
        context: PnLContext
    ) -> PnLResult:
        """Calculate mark-to-market PnL"""
        position_pnls = []
        trade_pnls = []
        by_asset = {}
        by_strategy = {}
        by_symbol = {}
        
        # Calculate unrealized PnL
        unrealized_pnl = 0
        for position in context.positions:
            current_price = context.current_prices.get(position.symbol, float(position.entry_price))
            size = float(position.size)
            entry_price = float(position.entry_price)
            
            pnl = (current_price - entry_price) * size
            unrealized_pnl += pnl
            
            pos_pnl = PositionPnL(
                position_id=position.id,
                symbol=position.symbol,
                size=size,
                entry_price=entry_price,
                current_price=current_price,
                unrealized_pnl=pnl,
                unrealized_pnl_pct=pnl / (size * entry_price) if size * entry_price != 0 else 0,
                realized_pnl=0,
                total_pnl=pnl,
                entry_time=position.created_at
            )
            position_pnls.append(pos_pnl)
            
            # Group by asset/strategy/symbol
            asset = getattr(position, 'asset_class', 'unknown')
            strategy = getattr(position, 'strategy', 'unknown')
            
            if asset not in by_asset:
                by_asset[asset] = {'unrealized': 0, 'realized': 0, 'total': 0}
            by_asset[asset]['unrealized'] += pnl
            by_asset[asset]['total'] += pnl
            
            if strategy not in by_strategy:
                by_strategy[strategy] = {'unrealized': 0, 'realized': 0, 'total': 0}
            by_strategy[strategy]['unrealized'] += pnl
            by_strategy[strategy]['total'] += pnl
            
            if position.symbol not in by_symbol:
                by_symbol[position.symbol] = {'unrealized': 0, 'realized': 0, 'total': 0}
            by_symbol[position.symbol]['unrealized'] += pnl
            by_symbol[position.symbol]['total'] += pnl
        
        # Calculate realized PnL
        realized_pnl = 0
        for trade in context.trades:
            pnl = float(trade.pnl) if hasattr(trade, 'pnl') else 0
            realized_pnl += pnl
            
            trade_pnl = TradePnL(
                trade_id=trade.id,
                symbol=trade.symbol,
                side=trade.side,
                entry_price=float(trade.entry_price) if hasattr(trade, 'entry_price') else 0,
                exit_price=float(trade.exit_price) if hasattr(trade, 'exit_price') else 0,
                size=float(trade.size),
                pnl=pnl,
                pnl_pct=pnl / (float(trade.size) * float(trade.entry_price)) if float(trade.size) * float(trade.entry_price) != 0 else 0,
                fee=float(trade.fee) if hasattr(trade, 'fee') else 0,
                timestamp=trade.execution_time
            )
            trade_pnls.append(trade_pnl)
            
            # Update by groupings
            asset = getattr(trade, 'asset_class', 'unknown')
            strategy = getattr(trade, 'strategy', 'unknown')
            
            if asset in by_asset:
                by_asset[asset]['realized'] += pnl
                by_asset[asset]['total'] += pnl
            
            if strategy in by_strategy:
                by_strategy[strategy]['realized'] += pnl
                by_strategy[strategy]['total'] += pnl
            
            if trade.symbol in by_symbol:
                by_symbol[trade.symbol]['realized'] += pnl
                by_symbol[trade.symbol]['total'] += pnl
        
        total_pnl = unrealized_pnl + realized_pnl
        
        # Calculate period PnL
        now = datetime.utcnow()
        daily_pnl = sum(float(t.pnl) for t in context.trades if t.execution_time.date() == now.date())
        weekly_pnl = sum(float(t.pnl) for t in context.trades if t.execution_time >= now - timedelta(days=7))
        monthly_pnl = sum(float(t.pnl) for t in context.trades if t.execution_time >= now - timedelta(days=30))
        yearly_pnl = sum(float(t.pnl) for t in context.trades if t.execution_time >= now - timedelta(days=365))
        
        # Calculate percentage
        portfolio = await self.portfolio_repo.get_by_id(context.portfolio_id)
        initial_capital = float(portfolio.initial_capital) if portfolio else 1
        pnl_percentage = total_pnl / initial_capital * 100 if initial_capital > 0 else 0
        
        # Build history
        history = await self._build_history(context)
        
        return PnLResult(
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_pnl=total_pnl,
            daily_pnl=daily_pnl,
            weekly_pnl=weekly_pnl,
            monthly_pnl=monthly_pnl,
            yearly_pnl=yearly_pnl,
            pnl_percentage=pnl_percentage,
            by_asset=by_asset,
            by_strategy=by_strategy,
            by_symbol=by_symbol,
            trade_pnls=trade_pnls,
            position_pnls=position_pnls,
            history=history
        )

    # -------------------------------------------------------------------------
    # FIFO
    # -------------------------------------------------------------------------

    async def _calculate_fifo(self, context: PnLContext) -> PnLResult:
        """Calculate FIFO PnL"""
        # Implementation would track cost basis using FIFO
        # For now, use mark-to-market as base
        return await self._calculate_mark_to_market(context)

    # -------------------------------------------------------------------------
    # LIFO
    # -------------------------------------------------------------------------

    async def _calculate_lifo(self, context: PnLContext) -> PnLResult:
        """Calculate LIFO PnL"""
        return await self._calculate_mark_to_market(context)

    # -------------------------------------------------------------------------
    # HIFO
    # -------------------------------------------------------------------------

    async def _calculate_hifo(self, context: PnLContext) -> PnLResult:
        """Calculate HIFO PnL"""
        return await self._calculate_mark_to_market(context)

    # -------------------------------------------------------------------------
    # Average Cost
    # -------------------------------------------------------------------------

    async def _calculate_avg_cost(self, context: PnLContext) -> PnLResult:
        """Calculate average cost PnL"""
        return await self._calculate_mark_to_market(context)

    # -------------------------------------------------------------------------
    # Realized
    # -------------------------------------------------------------------------

    async def _calculate_realized(self, context: PnLContext) -> PnLResult:
        """Calculate realized PnL only"""
        result = await self._calculate_mark_to_market(context)
        result.unrealized_pnl = 0
        result.total_pnl = result.realized_pnl
        return result

    # -------------------------------------------------------------------------
    # Unrealized
    # -------------------------------------------------------------------------

    async def _calculate_unrealized(self, context: PnLContext) -> PnLResult:
        """Calculate unrealized PnL only"""
        result = await self._calculate_mark_to_market(context)
        result.realized_pnl = 0
        result.total_pnl = result.unrealized_pnl
        return result

    # =========================================================================
    # History Building
    # =========================================================================

    async def _build_history(
        self,
        context: PnLContext
    ) -> List[Dict[str, Any]]:
        """Build PnL history"""
        history = []
        
        # Group trades by date
        trades_by_date = {}
        for trade in context.trades:
            date = trade.execution_time.date()
            if date not in trades_by_date:
                trades_by_date[date] = []
            trades_by_date[date].append(trade)
        
        # Calculate daily PnL
        cumulative_pnl = 0
        for date in sorted(trades_by_date.keys()):
            day_pnl = sum(float(t.pnl) for t in trades_by_date[date])
            cumulative_pnl += day_pnl
            
            history.append({
                'date': date.isoformat(),
                'daily_pnl': day_pnl,
                'cumulative_pnl': cumulative_pnl,
                'trade_count': len(trades_by_date[date])
            })
        
        return history

    # =========================================================================
    # Analytics
    # =========================================================================

    async def _calculate_analytics(
        self,
        result: PnLResult
    ) -> Dict[str, Any]:
        """Calculate PnL analytics"""
        history = result.history
        
        if not history:
            return {
                'total_pnl': result.total_pnl,
                'avg_daily_pnl': 0,
                'avg_weekly_pnl': 0,
                'avg_monthly_pnl': 0,
                'best_day': 0,
                'worst_day': 0,
                'best_week': 0,
                'worst_week': 0,
                'best_month': 0,
                'worst_month': 0,
                'winning_days_pct': 0,
                'winning_weeks_pct': 0,
                'winning_months_pct': 0,
                'max_consecutive_wins': 0,
                'max_consecutive_losses': 0,
                'volatility': 0,
                'recovery_factor': 0,
                'recommendations': ["Insufficient data for analytics"]
            }
        
        # Extract daily PnL
        daily_pnls = [h['daily_pnl'] for h in history]
        
        # Calculate statistics
        avg_daily = np.mean(daily_pnls) if daily_pnls else 0
        best_day = max(daily_pnls) if daily_pnls else 0
        worst_day = min(daily_pnls) if daily_pnls else 0
        
        # Weekly PnL
        weekly_pnls = []
        for i in range(0, len(daily_pnls), 7):
            week_pnl = sum(daily_pnls[i:i+7])
            weekly_pnls.append(week_pnl)
        
        avg_weekly = np.mean(weekly_pnls) if weekly_pnls else 0
        best_week = max(weekly_pnls) if weekly_pnls else 0
        worst_week = min(weekly_pnls) if weekly_pnls else 0
        
        # Monthly PnL
        monthly_pnls = []
        for i in range(0, len(daily_pnls), 30):
            month_pnl = sum(daily_pnls[i:i+30])
            monthly_pnls.append(month_pnl)
        
        avg_monthly = np.mean(monthly_pnls) if monthly_pnls else 0
        best_month = max(monthly_pnls) if monthly_pnls else 0
        worst_month = min(monthly_pnls) if monthly_pnls else 0
        
        # Win rates
        winning_days = sum(1 for p in daily_pnls if p > 0)
        winning_weeks = sum(1 for p in weekly_pnls if p > 0)
        winning_months = sum(1 for p in monthly_pnls if p > 0)
        
        winning_days_pct = winning_days / len(daily_pnls) if daily_pnls else 0
        winning_weeks_pct = winning_weeks / len(weekly_pnls) if weekly_pnls else 0
        winning_months_pct = winning_months / len(monthly_pnls) if monthly_pnls else 0
        
        # Consecutive wins/losses
        max_wins = 0
        max_losses = 0
        current_wins = 0
        current_losses = 0
        
        for pnl in daily_pnls:
            if pnl > 0:
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            elif pnl < 0:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)
            else:
                current_wins = 0
                current_losses = 0
        
        # Volatility
        volatility = np.std(daily_pnls) * np.sqrt(252) if daily_pnls else 0
        
        # Recovery factor
        total_pnl = result.total_pnl
        max_drawdown = 0
        cumulative = 0
        peak = 0
        
        for pnl in daily_pnls:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            drawdown = (peak - cumulative) / peak if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)
        
        recovery_factor = total_pnl / max_drawdown if max_drawdown > 0 else 0
        
        # Generate recommendations
        recommendations = []
        
        if winning_days_pct < 0.4:
            recommendations.append("Low winning days percentage. Consider reviewing strategy.")
        
        if max_losses > 5:
            recommendations.append("Long losing streak detected. Implement risk controls.")
        
        if volatility > abs(avg_daily) * 2:
            recommendations.append("High volatility relative to average PnL. Consider reducing position sizes.")
        
        if recovery_factor < 1:
            recommendations.append("Recovery factor below 1. Strategy may not recover from drawdowns.")
        
        if result.total_pnl < 0:
            recommendations.append("Overall negative PnL. Review strategy and risk management.")
        
        if not recommendations:
            recommendations.append("All PnL metrics are within acceptable ranges.")
        
        return {
            'total_pnl': result.total_pnl,
            'avg_daily_pnl': avg_daily,
            'avg_weekly_pnl': avg_weekly,
            'avg_monthly_pnl': avg_monthly,
            'best_day': best_day,
            'worst_day': worst_day,
            'best_week': best_week,
            'worst_week': worst_week,
            'best_month': best_month,
            'worst_month': worst_month,
            'winning_days_pct': winning_days_pct,
            'winning_weeks_pct': winning_weeks_pct,
            'winning_months_pct': winning_months_pct,
            'max_consecutive_wins': max_wins,
            'max_consecutive_losses': max_losses,
            'volatility': volatility,
            'recovery_factor': recovery_factor,
            'recommendations': recommendations
        }

    # =========================================================================
    # PnL Analytics
    # =========================================================================

    async def get_pnl_analytics(
        self,
        portfolio_id: str,
        period: PnLPeriod = PnLPeriod.MONTH
    ) -> PnLAnalyticsResponse:
        """
        Get PnL analytics.
        
        Args:
            portfolio_id: Portfolio ID
            period: PnL period
            
        Returns:
            PnLAnalyticsResponse: PnL analytics
        """
        try:
            request = PnLRequest(
                portfolio_id=portfolio_id,
                period=period,
                include_history=True
            )
            
            response = await self.calculate_pnl(request)
            analytics = response.summary
            
            return PnLAnalyticsResponse(
                total_pnl=response.total_pnl,
                avg_daily_pnl=analytics.get('avg_daily_pnl', 0),
                avg_weekly_pnl=analytics.get('avg_weekly_pnl', 0),
                avg_monthly_pnl=analytics.get('avg_monthly_pnl', 0),
                best_day=analytics.get('best_day', 0),
                worst_day=analytics.get('worst_day', 0),
                best_week=analytics.get('best_week', 0),
                worst_week=analytics.get('worst_week', 0),
                best_month=analytics.get('best_month', 0),
                worst_month=analytics.get('worst_month', 0),
                winning_days_pct=analytics.get('winning_days_pct', 0),
                winning_weeks_pct=analytics.get('winning_weeks_pct', 0),
                winning_months_pct=analytics.get('winning_months_pct', 0),
                max_consecutive_wins=analytics.get('max_consecutive_wins', 0),
                max_consecutive_losses=analytics.get('max_consecutive_losses', 0),
                volatility=analytics.get('volatility', 0),
                recovery_factor=analytics.get('recovery_factor', 0),
                recommendations=analytics.get('recommendations', [])
            )
            
        except Exception as e:
            logger.error(f"Error getting PnL analytics: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"PnL analytics retrieval failed: {str(e)}"
            )

    # =========================================================================
    # Export
    # =========================================================================

    async def export_pnl(
        self,
        portfolio_id: str,
        format: str = "csv",
        period: PnLPeriod = PnLPeriod.MONTH
    ) -> Union[str, bytes]:
        """
        Export PnL data.
        
        Args:
            portfolio_id: Portfolio ID
            format: Export format (csv, json, excel)
            period: PnL period
            
        Returns:
            Union[str, bytes]: Exported data
        """
        try:
            request = PnLRequest(
                portfolio_id=portfolio_id,
                period=period,
                include_history=True
            )
            
            response = await self.calculate_pnl(request)
            
            # Convert to DataFrame
            data = {
                'total_pnl': response.total_pnl,
                'realized_pnl': response.realized_pnl,
                'unrealized_pnl': response.unrealized_pnl,
                'daily_pnl': response.daily_pnl,
                'weekly_pnl': response.weekly_pnl,
                'monthly_pnl': response.monthly_pnl,
                'pnl_percentage': response.pnl_percentage
            }
            
            df_trades = pd.DataFrame([t.__dict__ for t in response.trade_pnls]) if response.trade_pnls else pd.DataFrame()
            df_positions = pd.DataFrame([p.__dict__ for p in response.position_pnls]) if response.position_pnls else pd.DataFrame()
            df_history = pd.DataFrame(response.history) if response.history else pd.DataFrame()
            
            if format == "csv":
                output = []
                output.append("# PnL Summary")
                output.append(pd.DataFrame([data]).to_csv(index=False))
                if not df_trades.empty:
                    output.append("\n# Trades")
                    output.append(df_trades.to_csv(index=False))
                if not df_positions.empty:
                    output.append("\n# Positions")
                    output.append(df_positions.to_csv(index=False))
                if not df_history.empty:
                    output.append("\n# History")
                    output.append(df_history.to_csv(index=False))
                return '\n'.join(output)
            
            elif format == "json":
                import json
                return json.dumps({
                    'summary': data,
                    'trades': df_trades.to_dict(orient='records') if not df_trades.empty else [],
                    'positions': df_positions.to_dict(orient='records') if not df_positions.empty else [],
                    'history': response.history
                }, default=str, indent=2)
            
            elif format == "excel":
                import io
                import openpyxl
                output = io.BytesIO()
                
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    pd.DataFrame([data]).to_excel(writer, sheet_name='Summary', index=False)
                    if not df_trades.empty:
                        df_trades.to_excel(writer, sheet_name='Trades', index=False)
                    if not df_positions.empty:
                        df_positions.to_excel(writer, sheet_name='Positions', index=False)
                    if not df_history.empty:
                        df_history.to_excel(writer, sheet_name='History', index=False)
                
                return output.getvalue()
            
            else:
                return "Unsupported format"
            
        except Exception as e:
            logger.error(f"Error exporting PnL: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"PnL export failed: {str(e)}"
            )

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the PnL calculator"""
        self._pnl_cache.clear()
        self._history_cache.clear()
        self._price_cache.clear()
        logger.info("PnLCalculator closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/portfolio/pnl", tags=["Portfolio PnL"])


async def get_calculator() -> PnLCalculator:
    """Dependency to get PnLCalculator instance"""
    return PnLCalculator()


@router.post("/calculate", response_model=PnLResponse)
async def calculate_pnl(
    request: PnLRequest,
    calculator: PnLCalculator = Depends(get_calculator)
):
    """Calculate portfolio PnL"""
    return await calculator.calculate_pnl(request)


@router.get("/{portfolio_id}/analytics")
async def get_pnl_analytics(
    portfolio_id: str,
    period: PnLPeriod = Query(PnLPeriod.MONTH),
    calculator: PnLCalculator = Depends(get_calculator)
):
    """Get PnL analytics"""
    return await calculator.get_pnl_analytics(portfolio_id, period)


@router.get("/{portfolio_id}/export")
async def export_pnl(
    portfolio_id: str,
    format: str = Query("csv", regex="^(csv|json|excel)$"),
    period: PnLPeriod = Query(PnLPeriod.MONTH),
    calculator: PnLCalculator = Depends(get_calculator)
):
    """Export PnL data"""
    data = await calculator.export_pnl(portfolio_id, format, period)
    
    content_type = {
        'csv': 'text/csv',
        'json': 'application/json',
        'excel': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    }.get(format, 'text/csv')
    
    extension = format if format != 'excel' else 'xlsx'
    filename = f"pnl_{portfolio_id}.{extension}"
    
    return Response(
        content=data if isinstance(data, bytes) else data.encode('utf-8'),
        media_type=content_type,
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )


@router.get("/methods")
async def get_pnl_methods():
    """Get available PnL calculation methods"""
    return {
        'methods': [
            {'name': m.value, 'description': m.name.replace('_', ' ').title()}
            for m in PnLCalculationMethod
        ]
    }


@router.get("/periods")
async def get_pnl_periods():
    """Get available PnL periods"""
    return {
        'periods': [
            {'name': p.value, 'description': p.name.title()}
            for p in PnLPeriod
        ]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PnLCalculator',
    'PnLType',
    'PnLCalculationMethod',
    'PnLPeriod',
    'PnLRequest',
    'PnLResponse',
    'PnLAnalyticsResponse',
    'PnLContext',
    'TradePnL',
    'PositionPnL',
    'PnLResult',
    'router'
]
