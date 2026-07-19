"""
NEXUS AI TRADING SYSTEM - Paper Trading Analytics Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/paper-trading/paper_analytics.py
Description: Comprehensive paper trading analytics with full API integration
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
from shared.configs.paper_trading_config import PaperTradingConfig
from shared.constants.trading_constants import TIME_FRAMES
from shared.helpers.trading_helpers import (
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_calmar_ratio,
    calculate_omega_ratio,
    calculate_drawdown
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.order_repository import OrderRepository
from backend.database.repositories.position_repository import PositionRepository

# Paper trading imports
from trading.paper_trading.paper_account import PaperTradingAccount

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class AnalyticsPeriod(str, Enum):
    """Analytics periods"""
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    ALL = "all"


class AnalyticsMetric(str, Enum):
    """Analytics metrics"""
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    OMEGA_RATIO = "omega_ratio"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    MAX_DRAWDOWN = "max_drawdown"
    EXPECTED_VALUE = "expected_value"
    TOTAL_PNL = "total_pnl"
    AVG_TRADE_PNL = "avg_trade_pnl"
    TOTAL_TRADES = "total_trades"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class AnalyticsRequest(BaseModel):
    """Request model for analytics"""
    account_id: str
    period: AnalyticsPeriod = AnalyticsPeriod.MONTH
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metrics: List[AnalyticsMetric] = []
    include_history: bool = True
    include_charts: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AnalyticsResponse(BaseModel):
    """Response model for analytics"""
    account_id: str
    period: AnalyticsPeriod
    timestamp: datetime
    summary: Dict[str, Any]
    metrics: Dict[str, Any]
    performance: Dict[str, Any]
    risk_metrics: Dict[str, Any]
    trade_stats: Dict[str, Any]
    position_stats: Dict[str, Any]
    order_stats: Dict[str, Any]
    equity_curve: List[Dict[str, Any]]
    insights: List[str]
    recommendations: List[str]


class TradeAnalyticsResponse(BaseModel):
    """Response model for trade analytics"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    best_trade: float
    worst_trade: float
    avg_trade_duration: float
    trade_frequency: float
    by_symbol: Dict[str, Any]
    by_strategy: Dict[str, Any]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class AnalyticsContext:
    """Context for analytics"""
    account_id: str
    period: AnalyticsPeriod
    start_date: datetime
    end_date: datetime
    trades: List[Any]
    orders: List[Any]
    positions: List[Any]
    equity: List[float]
    timestamps: List[datetime]
    initial_balance: float
    current_balance: float


@dataclass
class PerformanceSummary:
    """Performance summary"""
    total_pnl: float
    total_pnl_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    omega_ratio: float
    max_drawdown: float
    current_drawdown: float
    win_rate: float
    profit_factor: float
    avg_trade_pnl: float
    total_trades: int


# =============================================================================
# PAPER TRADING ANALYTICS
# =============================================================================

class PaperTradingAnalytics:
    """
    Comprehensive Paper Trading Analytics with full API integration.
    
    Features:
    - Performance metrics (Sharpe, Sortino, Calmar, Omega)
    - Trade statistics
    - Risk metrics
    - Equity curve analysis
    - Drawdown analysis
    - Position analysis
    - Order analysis
    - Insights generation
    """

    def __init__(
        self,
        config: Optional[PaperTradingConfig] = None,
        trade_repo: Optional[TradeRepository] = None,
        order_repo: Optional[OrderRepository] = None,
        position_repo: Optional[PositionRepository] = None,
        paper_account: Optional[PaperTradingAccount] = None
    ):
        """
        Initialize PaperTradingAnalytics.
        
        Args:
            config: Paper trading configuration
            trade_repo: Trade repository
            order_repo: Order repository
            position_repo: Position repository
            paper_account: Paper trading account
        """
        self.config = config or PaperTradingConfig()
        self.trade_repo = trade_repo or TradeRepository()
        self.order_repo = order_repo or OrderRepository()
        self.position_repo = position_repo or PositionRepository()
        self.paper_account = paper_account or PaperTradingAccount()
        
        # Cache
        self._analytics_cache: Dict[str, Dict[str, Any]] = {}
        self._equity_cache: Dict[str, List[float]] = {}
        
        logger.info("PaperTradingAnalytics initialized")

    # =========================================================================
    # Analytics Calculation
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_analytics(
        self,
        request: AnalyticsRequest
    ) -> AnalyticsResponse:
        """
        Get comprehensive analytics.
        
        Args:
            request: Analytics request
            
        Returns:
            AnalyticsResponse: Analytics results
        """
        try:
            # Build context
            context = await self._build_context(request)
            
            # Calculate metrics
            metrics = await self._calculate_metrics(context)
            
            # Calculate performance
            performance = await self._calculate_performance(context)
            
            # Calculate risk metrics
            risk_metrics = await self._calculate_risk_metrics(context)
            
            # Calculate trade stats
            trade_stats = await self._calculate_trade_stats(context)
            
            # Calculate position stats
            position_stats = await self._calculate_position_stats(context)
            
            # Calculate order stats
            order_stats = await self._calculate_order_stats(context)
            
            # Generate insights
            insights = await self._generate_insights(
                metrics,
                performance,
                risk_metrics
            )
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(
                metrics,
                performance,
                risk_metrics
            )
            
            # Create response
            response = AnalyticsResponse(
                account_id=request.account_id,
                period=request.period,
                timestamp=datetime.utcnow(),
                summary=metrics.get('summary', {}),
                metrics=metrics,
                performance=performance,
                risk_metrics=risk_metrics,
                trade_stats=trade_stats,
                position_stats=position_stats,
                order_stats=order_stats,
                equity_curve=await self._get_equity_curve(context),
                insights=insights,
                recommendations=recommendations
            )
            
            # Cache
            cache_key = f"{request.account_id}_{request.period.value}"
            self._analytics_cache[cache_key] = {
                'response': response,
                'context': context,
                'timestamp': datetime.utcnow()
            }
            
            logger.info(f"Analytics calculated for {request.account_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error calculating analytics: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Analytics calculation failed: {str(e)}"
            )

    async def _build_context(self, request: AnalyticsRequest) -> AnalyticsContext:
        """Build analytics context"""
        # Set date range
        end_date = request.end_date or datetime.utcnow()
        start_date = request.start_date
        
        if not start_date:
            # Map period to timedelta
            period_map = {
                AnalyticsPeriod.DAY: timedelta(days=1),
                AnalyticsPeriod.WEEK: timedelta(days=7),
                AnalyticsPeriod.MONTH: timedelta(days=30),
                AnalyticsPeriod.QUARTER: timedelta(days=90),
                AnalyticsPeriod.YEAR: timedelta(days=365)
            }
            
            if request.period == AnalyticsPeriod.DAY:
                start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                delta = period_map.get(request.period, timedelta(days=30))
                start_date = end_date - delta
        
        # Get account
        account = await self.paper_account.get_account(request.account_id)
        
        # Get trades
        trades = await self.trade_repo.get_by_account_id(
            request.account_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Get orders
        orders = await self.order_repo.get_by_account_id(
            request.account_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Get positions
        positions = await self.position_repo.get_by_account_id(request.account_id)
        
        # Get equity curve
        equity, timestamps = await self._get_equity_history(request.account_id)
        
        return AnalyticsContext(
            account_id=request.account_id,
            period=request.period,
            start_date=start_date,
            end_date=end_date,
            trades=trades,
            orders=orders,
            positions=positions,
            equity=equity,
            timestamps=timestamps,
            initial_balance=account.balance if account else 0,
            current_balance=account.balance if account else 0
        )

    # =========================================================================
    # Metrics Calculation
    # =========================================================================

    async def _calculate_metrics(
        self,
        context: AnalyticsContext
    ) -> Dict[str, Any]:
        """Calculate metrics"""
        metrics = {
            'summary': {},
            'performance': {},
            'risk': {},
            'trades': {},
            'positions': {},
            'orders': {}
        }
        
        # Performance metrics
        if context.trades:
            pnls = [float(t.pnl) for t in context.trades if hasattr(t, 'pnl')]
            
            if pnls:
                metrics['summary']['total_trades'] = len(pnls)
                metrics['summary']['total_pnl'] = sum(pnls)
                metrics['summary']['avg_pnl'] = np.mean(pnls)
                metrics['summary']['max_pnl'] = max(pnls)
                metrics['summary']['min_pnl'] = min(pnls)
                
                # Win rate
                wins = [p for p in pnls if p > 0]
                losses = [p for p in pnls if p < 0]
                metrics['summary']['win_rate'] = len(wins) / len(pnls) if pnls else 0
                metrics['summary']['winning_trades'] = len(wins)
                metrics['summary']['losing_trades'] = len(losses)
                
                # Profit factor
                gross_profit = sum(wins)
                gross_loss = abs(sum(losses))
                metrics['summary']['profit_factor'] = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                
                # Average win/loss
                metrics['summary']['avg_win'] = np.mean(wins) if wins else 0
                metrics['summary']['avg_loss'] = np.mean(losses) if losses else 0
        
        # Position metrics
        if context.positions:
            metrics['summary']['total_positions'] = len(context.positions)
            metrics['summary']['open_positions'] = len([p for p in context.positions if p.status == 'open'])
            metrics['summary']['closed_positions'] = len([p for p in context.positions if p.status == 'closed'])
        
        # Order metrics
        if context.orders:
            metrics['summary']['total_orders'] = len(context.orders)
            metrics['summary']['filled_orders'] = len([o for o in context.orders if o.status == 'filled'])
            metrics['summary']['cancelled_orders'] = len([o for o in context.orders if o.status == 'cancelled'])
            metrics['summary']['fill_rate'] = metrics['summary']['filled_orders'] / len(context.orders) if context.orders else 0
        
        return metrics

    # =========================================================================
    # Performance Calculation
    # =========================================================================

    async def _calculate_performance(
        self,
        context: AnalyticsContext
    ) -> Dict[str, Any]:
        """Calculate performance metrics"""
        performance = {}
        
        if context.trades:
            pnls = [float(t.pnl) for t in context.trades if hasattr(t, 'pnl')]
            
            if pnls:
                # Returns
                returns = []
                for i in range(1, len(pnls)):
                    if pnls[i-1] != 0:
                        returns.append((pnls[i] - pnls[i-1]) / abs(pnls[i-1]))
                
                if returns:
                    # Sharpe ratio
                    performance['sharpe_ratio'] = calculate_sharpe_ratio(returns, annualize=True)
                    
                    # Sortino ratio
                    performance['sortino_ratio'] = calculate_sortino_ratio(returns, annualize=True)
                    
                    # Calmar ratio
                    performance['calmar_ratio'] = calculate_calmar_ratio(returns, annualize=True)
                    
                    # Omega ratio
                    performance['omega_ratio'] = calculate_omega_ratio(returns, 0.03)
                    
                    # Volatility
                    performance['volatility'] = np.std(returns) * np.sqrt(252)
                
                # Total performance
                total_pnl = sum(pnls)
                performance['total_pnl'] = total_pnl
                performance['total_pnl_pct'] = total_pnl / context.initial_balance * 100 if context.initial_balance > 0 else 0
                
                # Daily performance
                if context.equity:
                    performance['avg_daily_return'] = np.mean(returns) if returns else 0
                    performance['max_daily_return'] = max(returns) if returns else 0
                    performance['min_daily_return'] = min(returns) if returns else 0
        
        return performance

    # =========================================================================
    # Risk Metrics
    # =========================================================================

    async def _calculate_risk_metrics(
        self,
        context: AnalyticsContext
    ) -> Dict[str, Any]:
        """Calculate risk metrics"""
        risk_metrics = {}
        
        if context.trades:
            pnls = [float(t.pnl) for t in context.trades if hasattr(t, 'pnl')]
            
            if pnls:
                # Drawdown
                if context.equity:
                    risk_metrics['max_drawdown'] = calculate_drawdown(context.equity)
                    risk_metrics['current_drawdown'] = calculate_drawdown(context.equity, current_only=True)
                
                # VaR and CVaR
                if len(pnls) > 30:
                    risk_metrics['var_95'] = np.percentile(pnls, 5)
                    risk_metrics['cvar_95'] = np.mean([p for p in pnls if p <= risk_metrics['var_95']])
                    risk_metrics['var_99'] = np.percentile(pnls, 1)
                    risk_metrics['cvar_99'] = np.mean([p for p in pnls if p <= risk_metrics['var_99']])
                
                # Tail risk
                sorted_pnls = sorted(pnls)
                tail_pnls = sorted_pnls[:int(len(sorted_pnls) * 0.05)]
                if tail_pnls:
                    risk_metrics['tail_risk'] = abs(np.mean(tail_pnls))
                
                # Risk-adjusted metrics
                if 'sharpe_ratio' in risk_metrics:
                    risk_metrics['risk_adjusted_return'] = risk_metrics['sharpe_ratio'] * 100
        
        return risk_metrics

    # =========================================================================
    # Trade Statistics
    # =========================================================================

    async def _calculate_trade_stats(
        self,
        context: AnalyticsContext
    ) -> Dict[str, Any]:
        """Calculate trade statistics"""
        stats = {}
        
        if context.trades:
            total_trades = len(context.trades)
            
            # Basic stats
            stats['total_trades'] = total_trades
            
            # PnL stats
            pnls = [float(t.pnl) for t in context.trades if hasattr(t, 'pnl')]
            if pnls:
                stats['total_pnl'] = sum(pnls)
                stats['avg_pnl'] = np.mean(pnls)
                stats['median_pnl'] = np.median(pnls)
                stats['std_pnl'] = np.std(pnls)
                
                wins = [p for p in pnls if p > 0]
                losses = [p for p in pnls if p < 0]
                
                stats['winning_trades'] = len(wins)
                stats['losing_trades'] = len(losses)
                stats['win_rate'] = len(wins) / total_trades if total_trades > 0 else 0
                
                stats['avg_win'] = np.mean(wins) if wins else 0
                stats['avg_loss'] = np.mean(losses) if losses else 0
                stats['max_win'] = max(wins) if wins else 0
                stats['max_loss'] = min(losses) if losses else 0
                
                gross_profit = sum(wins)
                gross_loss = abs(sum(losses))
                stats['profit_factor'] = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                
                # Trade duration
                durations = []
                for trade in context.trades:
                    if hasattr(trade, 'created_at') and hasattr(trade, 'filled_at'):
                        duration = (trade.filled_at - trade.created_at).total_seconds()
                        durations.append(duration)
                
                if durations:
                    stats['avg_trade_duration'] = np.mean(durations)
                    stats['max_trade_duration'] = max(durations)
                    stats['min_trade_duration'] = min(durations)
            
            # By symbol
            by_symbol = {}
            for trade in context.trades:
                symbol = trade.symbol
                pnl = float(trade.pnl) if hasattr(trade, 'pnl') else 0
                if symbol not in by_symbol:
                    by_symbol[symbol] = {'count': 0, 'pnl': 0, 'wins': 0}
                by_symbol[symbol]['count'] += 1
                by_symbol[symbol]['pnl'] += pnl
                if pnl > 0:
                    by_symbol[symbol]['wins'] += 1
            
            stats['by_symbol'] = by_symbol
        
        return stats

    # =========================================================================
    # Position Statistics
    # =========================================================================

    async def _calculate_position_stats(
        self,
        context: AnalyticsContext
    ) -> Dict[str, Any]:
        """Calculate position statistics"""
        stats = {}
        
        if context.positions:
            stats['total_positions'] = len(context.positions)
            stats['open_positions'] = len([p for p in context.positions if p.status == 'open'])
            stats['closed_positions'] = len([p for p in context.positions if p.status == 'closed'])
            
            # Position size stats
            sizes = [float(p.size) for p in context.positions if hasattr(p, 'size')]
            if sizes:
                stats['avg_position_size'] = np.mean(sizes)
                stats['max_position_size'] = max(sizes)
                stats['min_position_size'] = min(sizes)
            
            # Position PnL
            pnls = [float(p.pnl) for p in context.positions if hasattr(p, 'pnl')]
            if pnls:
                stats['total_pnl'] = sum(pnls)
                stats['avg_pnl'] = np.mean(pnls)
                stats['max_pnl'] = max(pnls)
                stats['min_pnl'] = min(pnls)
            
            # Holding periods
            holding_periods = []
            for pos in context.positions:
                if hasattr(pos, 'created_at') and hasattr(pos, 'closed_at'):
                    if pos.closed_at:
                        period = (pos.closed_at - pos.created_at).total_seconds()
                        holding_periods.append(period)
            
            if holding_periods:
                stats['avg_holding_period'] = np.mean(holding_periods)
                stats['max_holding_period'] = max(holding_periods)
        
        return stats

    # =========================================================================
    # Order Statistics
    # =========================================================================

    async def _calculate_order_stats(
        self,
        context: AnalyticsContext
    ) -> Dict[str, Any]:
        """Calculate order statistics"""
        stats = {}
        
        if context.orders:
            stats['total_orders'] = len(context.orders)
            
            # Order status
            status_counts = {}
            for order in context.orders:
                status = order.status if hasattr(order, 'status') else 'unknown'
                status_counts[status] = status_counts.get(status, 0) + 1
            
            stats['status_counts'] = status_counts
            
            # Order types
            type_counts = {}
            for order in context.orders:
                order_type = order.order_type if hasattr(order, 'order_type') else 'unknown'
                type_counts[order_type] = type_counts.get(order_type, 0) + 1
            
            stats['type_counts'] = type_counts
            
            # Fill rate
            filled = len([o for o in context.orders if o.status == 'filled'])
            stats['fill_rate'] = filled / len(context.orders) if context.orders else 0
            
            # Order sizes
            sizes = [float(o.size) for o in context.orders if hasattr(o, 'size')]
            if sizes:
                stats['avg_order_size'] = np.mean(sizes)
                stats['max_order_size'] = max(sizes)
                stats['min_order_size'] = min(sizes)
            
            # Cancellation rate
            cancelled = len([o for o in context.orders if o.status == 'cancelled'])
            stats['cancellation_rate'] = cancelled / len(context.orders) if context.orders else 0
        
        return stats

    # =========================================================================
    # Equity Curve
    # =========================================================================

    async def _get_equity_curve(
        self,
        context: AnalyticsContext
    ) -> List[Dict[str, Any]]:
        """Get equity curve data"""
        equity_curve = []
        
        if context.equity and context.timestamps:
            for i, (equity, timestamp) in enumerate(zip(context.equity, context.timestamps)):
                equity_curve.append({
                    'timestamp': timestamp.isoformat(),
                    'equity': equity,
                    'return': context.equity[i] / context.equity[0] - 1 if context.equity[0] > 0 else 0
                })
        
        return equity_curve

    async def _get_equity_history(
        self,
        account_id: str
    ) -> Tuple[List[float], List[datetime]]:
        """Get equity history"""
        # Check cache
        if account_id in self._equity_cache:
            return self._equity_cache[account_id], []
        
        # Get account
        account = await self.paper_account.get_account(account_id)
        
        # Get trades
        trades = await self.trade_repo.get_by_account_id(account_id)
        
        if not trades:
            return [account.balance], [datetime.utcnow()]
        
        # Calculate equity curve
        equity = [account.balance]
        timestamps = [datetime.utcnow()]
        
        for trade in sorted(trades, key=lambda t: t.created_at):
            pnl = float(trade.pnl) if hasattr(trade, 'pnl') else 0
            equity.append(equity[-1] + pnl)
            timestamps.append(trade.created_at)
        
        # Cache
        self._equity_cache[account_id] = (equity, timestamps)
        
        return equity, timestamps

    # =========================================================================
    # Insights and Recommendations
    # =========================================================================

    async def _generate_insights(
        self,
        metrics: Dict[str, Any],
        performance: Dict[str, Any],
        risk_metrics: Dict[str, Any]
    ) -> List[str]:
        """Generate insights"""
        insights = []
        
        # Performance insights
        if performance.get('total_pnl', 0) > 0:
            insights.append("Positive total PnL over the period")
        else:
            insights.append("Negative total PnL over the period")
        
        # Sharpe ratio insights
        sharpe = performance.get('sharpe_ratio', 0)
        if sharpe > 1.5:
            insights.append("Excellent risk-adjusted returns")
        elif sharpe > 0.8:
            insights.append("Good risk-adjusted returns")
        elif sharpe > 0:
            insights.append("Moderate risk-adjusted returns")
        else:
            insights.append("Negative risk-adjusted returns")
        
        # Win rate insights
        win_rate = metrics.get('summary', {}).get('win_rate', 0)
        if win_rate > 0.6:
            insights.append("High win rate")
        elif win_rate > 0.4:
            insights.append("Moderate win rate")
        else:
            insights.append("Low win rate")
        
        # Drawdown insights
        max_drawdown = risk_metrics.get('max_drawdown', 0)
        if max_drawdown > 0.20:
            insights.append("High maximum drawdown - consider risk management")
        elif max_drawdown > 0.10:
            insights.append("Moderate maximum drawdown")
        else:
            insights.append("Low maximum drawdown")
        
        # Profit factor insights
        profit_factor = metrics.get('summary', {}).get('profit_factor', 0)
        if profit_factor > 2:
            insights.append("Excellent profit factor")
        elif profit_factor > 1.5:
            insights.append("Good profit factor")
        elif profit_factor > 1:
            insights.append("Moderate profit factor")
        else:
            insights.append("Profit factor below 1 - review strategy")
        
        # Trade frequency insights
        total_trades = metrics.get('summary', {}).get('total_trades', 0)
        if total_trades > 100:
            insights.append("High trading frequency")
        elif total_trades > 20:
            insights.append("Moderate trading frequency")
        else:
            insights.append("Low trading frequency")
        
        return insights

    async def _generate_recommendations(
        self,
        metrics: Dict[str, Any],
        performance: Dict[str, Any],
        risk_metrics: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations"""
        recommendations = []
        
        # Sharpe ratio recommendations
        sharpe = performance.get('sharpe_ratio', 0)
        if sharpe < 0.5 and sharpe > 0:
            recommendations.append("Low Sharpe ratio. Consider improving risk-adjusted returns.")
        elif sharpe < 0:
            recommendations.append("Negative Sharpe ratio. Review strategy.")
        
        # Drawdown recommendations
        max_drawdown = risk_metrics.get('max_drawdown', 0)
        if max_drawdown > 0.20:
            recommendations.append("High drawdown. Implement stricter risk controls.")
        elif max_drawdown > 0.10:
            recommendations.append("Moderate drawdown. Monitor risk exposure.")
        
        # Win rate recommendations
        win_rate = metrics.get('summary', {}).get('win_rate', 0)
        if win_rate < 0.4 and win_rate > 0:
            recommendations.append("Low win rate. Review trade entry criteria.")
        
        # Profit factor recommendations
        profit_factor = metrics.get('summary', {}).get('profit_factor', 0)
        if profit_factor < 1:
            recommendations.append("Profit factor below 1. Strategy needs improvement.")
        elif profit_factor < 1.5:
            recommendations.append("Moderate profit factor. Look for optimization opportunities.")
        
        # Total PnL recommendations
        total_pnl = performance.get('total_pnl', 0)
        if total_pnl < 0:
            recommendations.append("Negative PnL. Consider pausing trading for review.")
        
        # Trade frequency recommendations
        total_trades = metrics.get('summary', {}).get('total_trades', 0)
        if total_trades > 200:
            recommendations.append("High trade frequency may incur significant costs.")
        elif total_trades < 5 and total_trades > 0:
            recommendations.append("Low trade frequency. Consider more active trading.")
        
        if not recommendations:
            recommendations.append("All metrics are within acceptable ranges. Continue current strategy.")
        
        return recommendations

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the analytics module"""
        self._analytics_cache.clear()
        self._equity_cache.clear()
        logger.info("PaperTradingAnalytics closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/api/v1/paper-trading/analytics", tags=["Paper Trading Analytics"])


async def get_analytics() -> PaperTradingAnalytics:
    """Dependency to get PaperTradingAnalytics instance"""
    return PaperTradingAnalytics()


@router.post("/", response_model=AnalyticsResponse)
async def get_analytics(
    request: AnalyticsRequest,
    analytics: PaperTradingAnalytics = Depends(get_analytics)
):
    """Get comprehensive analytics"""
    return await analytics.get_analytics(request)


@router.get("/{account_id}/trades")
async def get_trade_analytics(
    account_id: str,
    period: AnalyticsPeriod = Query(AnalyticsPeriod.MONTH),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    analytics: PaperTradingAnalytics = Depends(get_analytics)
):
    """Get trade analytics"""
    request = AnalyticsRequest(
        account_id=account_id,
        period=period,
        start_date=start_date,
        end_date=end_date
    )
    response = await analytics.get_analytics(request)
    return response.trade_stats


@router.get("/{account_id}/performance")
async def get_performance(
    account_id: str,
    period: AnalyticsPeriod = Query(AnalyticsPeriod.MONTH),
    analytics: PaperTradingAnalytics = Depends(get_analytics)
):
    """Get performance metrics"""
    request = AnalyticsRequest(
        account_id=account_id,
        period=period
    )
    response = await analytics.get_analytics(request)
    return response.performance


@router.get("/{account_id}/risk")
async def get_risk_metrics(
    account_id: str,
    period: AnalyticsPeriod = Query(AnalyticsPeriod.MONTH),
    analytics: PaperTradingAnalytics = Depends(get_analytics)
):
    """Get risk metrics"""
    request = AnalyticsRequest(
        account_id=account_id,
        period=period
    )
    response = await analytics.get_analytics(request)
    return response.risk_metrics


@router.get("/{account_id}/equity")
async def get_equity_curve(
    account_id: str,
    period: AnalyticsPeriod = Query(AnalyticsPeriod.MONTH),
    analytics: PaperTradingAnalytics = Depends(get_analytics)
):
    """Get equity curve"""
    request = AnalyticsRequest(
        account_id=account_id,
        period=period
    )
    response = await analytics.get_analytics(request)
    return response.equity_curve


@router.get("/metrics")
async def get_available_metrics():
    """Get available analytics metrics"""
    return {
        'metrics': [
            {'name': m.value, 'description': m.name.replace('_', ' ').title()}
            for m in AnalyticsMetric
        ]
    }


@router.get("/periods")
async def get_analytics_periods():
    """Get available analytics periods"""
    return {
        'periods': [
            {'name': p.value, 'description': p.name.title()}
            for p in AnalyticsPeriod
        ]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PaperTradingAnalytics',
    'AnalyticsPeriod',
    'AnalyticsMetric',
    'AnalyticsRequest',
    'AnalyticsResponse',
    'TradeAnalyticsResponse',
    'AnalyticsContext',
    'PerformanceSummary',
    'router'
]
