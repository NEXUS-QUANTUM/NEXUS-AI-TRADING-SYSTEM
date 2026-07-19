"""
NEXUS AI TRADING SYSTEM - Portfolio Performance Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/portfolio/performance.py
Description: Advanced portfolio performance analytics with full API integration
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
from scipy import stats
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.portfolio_config import PortfolioConfig
from shared.constants.trading_constants import TIME_FRAMES
from shared.helpers.trading_helpers import (
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_calmar_ratio,
    calculate_omega_ratio,
    calculate_sterling_ratio,
    calculate_burke_ratio
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.cache_utils import cached

# Database imports
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

class PerformanceMetric(str, Enum):
    """Performance metrics"""
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    OMEGA_RATIO = "omega_ratio"
    STERLING_RATIO = "sterling_ratio"
    BURKE_RATIO = "burke_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    CURRENT_DRAWDOWN = "current_drawdown"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    EXPECTED_VALUE = "expected_value"
    RISK_ADJUSTED_RETURN = "risk_adjusted_return"
    RECOVERY_FACTOR = "recovery_factor"
    K_RATIO = "k_ratio"


class ComparisonType(str, Enum):
    """Comparison types"""
    BENCHMARK = "benchmark"
    PERIOD = "period"
    STRATEGY = "strategy"
    PORTFOLIO = "portfolio"


class AttributionType(str, Enum):
    """Attribution types"""
    ASSET = "asset"
    SECTOR = "sector"
    STRATEGY = "strategy"
    TIMING = "timing"
    SELECTION = "selection"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class PerformanceRequest(BaseModel):
    """Request model for performance"""
    portfolio_id: str
    metric: PerformanceMetric = PerformanceMetric.SHARPE_RATIO
    period: str = "1y"  # 1d, 1w, 1m, 3m, 6m, 1y, all
    benchmark: Optional[str] = None
    risk_free_rate: float = 0.03
    confidence_level: float = 0.95
    include_details: bool = True
    include_attribution: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('confidence_level')
    def validate_confidence(cls, v):
        if not 0 < v < 1:
            raise ValueError('Confidence level must be between 0 and 1')
        return v


class PerformanceResponse(BaseModel):
    """Response model for performance"""
    portfolio_id: str
    metric: PerformanceMetric
    value: float
    confidence_interval: Tuple[float, float]
    benchmark_value: Optional[float] = None
    benchmark_comparison: Optional[float] = None
    period: str
    risk_free_rate: float
    attribution: Dict[str, Any]
    details: Dict[str, Any]
    recommendations: List[str]
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PerformanceHistoryResponse(BaseModel):
    """Response model for performance history"""
    portfolio_id: str
    metric: PerformanceMetric
    history: List[Dict[str, Any]]
    trend: str
    volatility: float
    summary: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ComparisonResponse(BaseModel):
    """Response model for comparison"""
    portfolio_id: str
    comparison_type: ComparisonType
    target: str
    metrics: Dict[str, float]
    differences: Dict[str, float]
    percentages: Dict[str, float]
    rank: int
    total_compared: int
    summary: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PerformanceContext:
    """Context for performance calculations"""
    portfolio_id: str
    metric: PerformanceMetric
    period: str
    returns: List[float]
    dates: List[datetime]
    trades: List[Any]
    positions: List[Any]
    benchmark_returns: Optional[List[float]] = None
    risk_free_rate: float = 0.03
    confidence_level: float = 0.95


@dataclass
class PerformanceResult:
    """Result of performance calculation"""
    metric: PerformanceMetric
    value: float
    confidence_interval: Tuple[float, float]
    details: Dict[str, Any]
    status: str
    message: str


@dataclass
class AttributionResult:
    """Result of attribution analysis"""
    total_return: float
    allocation_effect: float
    selection_effect: float
    interaction_effect: float
    by_asset: Dict[str, Dict[str, float]]
    by_sector: Dict[str, Dict[str, float]]
    by_strategy: Dict[str, Dict[str, float]]


# =============================================================================
# PORTFOLIO PERFORMANCE
# =============================================================================

class PortfolioPerformance:
    """
    Advanced Portfolio Performance Analytics with full API integration.
    
    Features:
    - Multiple performance metrics
    - Rolling calculations
    - Benchmark comparison
    - Attribution analysis
    - Performance history
    - Confidence intervals
    - Period analysis
    - Risk-adjusted metrics
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
        Initialize PortfolioPerformance.
        
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
        self._performance_cache: Dict[str, Dict[str, Any]] = {}
        self._returns_cache: Dict[str, List[float]] = {}
        
        # Benchmarks
        self._benchmarks: Dict[str, str] = {
            'S&P 500': 'SPY',
            'NASDAQ': 'QQQ',
            'Global': 'VT',
            'Bonds': 'AGG',
            'Commodities': 'DBC'
        }
        
        logger.info("PortfolioPerformance initialized")

    # =========================================================================
    # Performance Calculation
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def calculate_performance(
        self,
        request: PerformanceRequest
    ) -> PerformanceResponse:
        """
        Calculate portfolio performance metric.
        
        Args:
            request: Performance request
            
        Returns:
            PerformanceResponse: Performance results
        """
        try:
            # Build context
            context = await self._build_context(request)
            
            # Calculate metric
            result = await self._calculate_metric(context)
            
            # Calculate attribution if requested
            attribution = {}
            if request.include_attribution:
                attribution = await self._calculate_attribution(context)
            
            # Get benchmark value
            benchmark_value = None
            benchmark_comparison = None
            if request.benchmark:
                benchmark_metrics = await self._get_benchmark_metrics(
                    request.benchmark,
                    context.period
                )
                if benchmark_metrics:
                    benchmark_value = benchmark_metrics.get(request.metric.value)
                    if benchmark_value is not None:
                        benchmark_comparison = result.value - benchmark_value
            
            # Generate recommendations
            recommendations = await self._generate_recommendations(
                request,
                context,
                result,
                benchmark_value
            )
            
            # Create response
            response = PerformanceResponse(
                portfolio_id=request.portfolio_id,
                metric=request.metric,
                value=result.value,
                confidence_interval=result.confidence_interval,
                benchmark_value=benchmark_value,
                benchmark_comparison=benchmark_comparison,
                period=request.period,
                risk_free_rate=context.risk_free_rate,
                attribution=attribution,
                details=result.details,
                recommendations=recommendations,
                timestamp=datetime.utcnow(),
                metadata=request.metadata
            )
            
            # Cache
            cache_key = f"{request.portfolio_id}_{request.metric.value}_{request.period}"
            self._performance_cache[cache_key] = {
                'response': response,
                'context': context,
                'timestamp': datetime.utcnow()
            }
            
            logger.info(f"Performance calculated for {request.portfolio_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error calculating performance: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Performance calculation failed: {str(e)}"
            )

    async def _build_context(self, request: PerformanceRequest) -> PerformanceContext:
        """Build performance context"""
        # Get trades
        trades = await self.trade_repo.get_by_portfolio_id(request.portfolio_id)
        
        # Get positions
        positions = await self.position_repo.get_by_portfolio_id(request.portfolio_id)
        
        # Calculate returns
        returns, dates = self._calculate_returns(trades, request.period)
        
        # Get benchmark returns
        benchmark_returns = None
        if request.benchmark:
            benchmark_returns = await self._get_benchmark_returns(
                request.benchmark,
                request.period
            )
        
        return PerformanceContext(
            portfolio_id=request.portfolio_id,
            metric=request.metric,
            period=request.period,
            returns=returns,
            dates=dates,
            trades=trades,
            positions=positions,
            benchmark_returns=benchmark_returns,
            risk_free_rate=request.risk_free_rate,
            confidence_level=request.confidence_level
        )

    def _calculate_returns(
        self,
        trades: List[Any],
        period: str
    ) -> Tuple[List[float], List[datetime]]:
        """Calculate returns from trades"""
        if not trades:
            return [], []
        
        # Group trades by date
        trades_by_date = {}
        for trade in trades:
            date = trade.execution_time.date()
            if date not in trades_by_date:
                trades_by_date[date] = []
            trades_by_date[date].append(trade)
        
        # Calculate daily PnL
        dates = sorted(trades_by_date.keys())
        daily_pnl = []
        
        cumulative_pnl = 0
        for date in dates:
            day_pnl = sum(float(t.pnl) for t in trades_by_date[date])
            cumulative_pnl += day_pnl
            daily_pnl.append(cumulative_pnl)
        
        # Calculate returns
        returns = []
        if len(daily_pnl) > 1:
            for i in range(1, len(daily_pnl)):
                if daily_pnl[i-1] != 0:
                    ret = (daily_pnl[i] - daily_pnl[i-1]) / abs(daily_pnl[i-1])
                    returns.append(ret)
                else:
                    returns.append(0)
        
        return returns, dates[1:] if len(dates) > 1 else []

    async def _get_benchmark_returns(
        self,
        benchmark: str,
        period: str
    ) -> Optional[List[float]]:
        """Get benchmark returns"""
        try:
            # Map benchmark to symbol
            symbol = self._benchmarks.get(benchmark, benchmark)
            
            # Get historical data
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    candles = await broker.get_historical_candles(
                        symbol,
                        timeframe='1d',
                        limit=self._get_period_days(period)
                    )
                    if candles and len(candles) > 1:
                        prices = [float(c['close']) for c in candles]
                        returns = [(prices[i] - prices[i-1]) / prices[i-1] 
                                  for i in range(1, len(prices))]
                        return returns
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error getting benchmark returns: {e}")
        
        return None

    def _get_period_days(self, period: str) -> int:
        """Get number of days for period"""
        mapping = {
            '1d': 1,
            '1w': 7,
            '1m': 30,
            '3m': 90,
            '6m': 180,
            '1y': 365,
            'all': 3650
        }
        return mapping.get(period, 365)

    # =========================================================================
    # Metric Calculations
    # =========================================================================

    async def _calculate_metric(
        self,
        context: PerformanceContext
    ) -> PerformanceResult:
        """Calculate performance metric"""
        if context.metric == PerformanceMetric.SHARPE_RATIO:
            return await self._calculate_sharpe(context)
        elif context.metric == PerformanceMetric.SORTINO_RATIO:
            return await self._calculate_sortino(context)
        elif context.metric == PerformanceMetric.CALMAR_RATIO:
            return await self._calculate_calmar(context)
        elif context.metric == PerformanceMetric.OMEGA_RATIO:
            return await self._calculate_omega(context)
        elif context.metric == PerformanceMetric.STERLING_RATIO:
            return await self._calculate_sterling(context)
        elif context.metric == PerformanceMetric.BURKE_RATIO:
            return await self._calculate_burke(context)
        elif context.metric == PerformanceMetric.MAX_DRAWDOWN:
            return await self._calculate_max_drawdown(context)
        elif context.metric == PerformanceMetric.CURRENT_DRAWDOWN:
            return await self._calculate_current_drawdown(context)
        elif context.metric == PerformanceMetric.WIN_RATE:
            return await self._calculate_win_rate(context)
        elif context.metric == PerformanceMetric.PROFIT_FACTOR:
            return await self._calculate_profit_factor(context)
        elif context.metric == PerformanceMetric.EXPECTED_VALUE:
            return await self._calculate_expected_value(context)
        elif context.metric == PerformanceMetric.RISK_ADJUSTED_RETURN:
            return await self._calculate_risk_adjusted_return(context)
        elif context.metric == PerformanceMetric.RECOVERY_FACTOR:
            return await self._calculate_recovery_factor(context)
        elif context.metric == PerformanceMetric.K_RATIO:
            return await self._calculate_k_ratio(context)
        else:
            return await self._calculate_sharpe(context)

    # -------------------------------------------------------------------------
    # Sharpe Ratio
    # -------------------------------------------------------------------------

    async def _calculate_sharpe(
        self,
        context: PerformanceContext
    ) -> PerformanceResult:
        """Calculate Sharpe ratio"""
        if not context.returns:
            return PerformanceResult(
                metric=PerformanceMetric.SHARPE_RATIO,
                value=0,
                confidence_interval=(0, 0),
                details={},
                status='error',
                message='Insufficient data'
            )
        
        value = calculate_sharpe_ratio(
            context.returns,
            context.risk_free_rate,
            annualize=True
        )
        
        # Confidence interval
        n = len(context.returns)
        if n > 1:
            std_error = np.std(context.returns) / np.sqrt(n)
            z_score = stats.norm.ppf(context.confidence_level)
            margin = z_score * std_error * np.sqrt(252)
            ci = (value - margin, value + margin)
        else:
            ci = (value, value)
        
        return PerformanceResult(
            metric=PerformanceMetric.SHARPE_RATIO,
            value=value,
            confidence_interval=ci,
            details={
                'n_observations': n,
                'avg_return': np.mean(context.returns) * 252,
                'std_return': np.std(context.returns) * np.sqrt(252),
                'risk_free_rate': context.risk_free_rate
            },
            status='success',
            message='Sharpe ratio calculated'
        )

    # -------------------------------------------------------------------------
    # Sortino Ratio
    # -------------------------------------------------------------------------

    async def _calculate_sortino(
        self,
        context: PerformanceContext
    ) -> PerformanceResult:
        """Calculate Sortino ratio"""
        if not context.returns:
            return self._empty_result(PerformanceMetric.SORTINO_RATIO)
        
        value = calculate_sortino_ratio(
            context.returns,
            context.risk_free_rate,
            annualize=True
        )
        
        ci = self._calculate_confidence_interval(context, value)
        
        return PerformanceResult(
            metric=PerformanceMetric.SORTINO_RATIO,
            value=value,
            confidence_interval=ci,
            details={
                'downside_std': np.std([r for r in context.returns if r < 0]) * np.sqrt(252),
                'avg_return': np.mean(context.returns) * 252,
                'risk_free_rate': context.risk_free_rate
            },
            status='success',
            message='Sortino ratio calculated'
        )

    # -------------------------------------------------------------------------
    # Calmar Ratio
    # -------------------------------------------------------------------------

    async def _calculate_calmar(
        self,
        context: PerformanceContext
    ) -> PerformanceResult:
        """Calculate Calmar ratio"""
        if not context.returns:
            return self._empty_result(PerformanceMetric.CALMAR_RATIO)
        
        value = calculate_calmar_ratio(
            context.returns,
            annualize=True
        )
        
        ci = self._calculate_confidence_interval(context, value)
        
        return PerformanceResult(
            metric=PerformanceMetric.CALMAR_RATIO,
            value=value,
            confidence_interval=ci,
            details={
                'annual_return': np.mean(context.returns) * 252,
                'max_drawdown': calculate_drawdown(context.returns)
            },
            status='success',
            message='Calmar ratio calculated'
        )

    # -------------------------------------------------------------------------
    # Omega Ratio
    # -------------------------------------------------------------------------

    async def _calculate_omega(
        self,
        context: PerformanceContext
    ) -> PerformanceResult:
        """Calculate Omega ratio"""
        if not context.returns:
            return self._empty_result(PerformanceMetric.OMEGA_RATIO)
        
        value = calculate_omega_ratio(context.returns, context.risk_free_rate)
        
        ci = self._calculate_confidence_interval(context, value)
        
        return PerformanceResult(
            metric=PerformanceMetric.OMEGA_RATIO,
            value=value,
            confidence_interval=ci,
            details={
                'threshold': context.risk_free_rate / 252,
                'positive_sum': sum(r for r in context.returns if r > 0),
                'negative_sum': abs(sum(r for r in context.returns if r < 0))
            },
            status='success',
            message='Omega ratio calculated'
        )

    # -------------------------------------------------------------------------
    # Sterling Ratio
    # -------------------------------------------------------------------------

    async def _calculate_sterling(
        self,
        context: PerformanceContext
    ) -> PerformanceResult:
        """Calculate Sterling ratio"""
        if not context.returns:
            return self._empty_result(PerformanceMetric.STERLING_RATIO)
        
        value = calculate_sterling_ratio(context.returns, annualize=True)
        
        ci = self._calculate_confidence_interval(context, value)
        
        return PerformanceResult(
            metric=PerformanceMetric.STERLING_RATIO,
            value=value,
            confidence_interval=ci,
            details={
                'annual_return': np.mean(context.returns) * 252,
                'avg_drawdown': 0.05  # Would calculate actual
            },
            status='success',
            message='Sterling ratio calculated'
        )

    # -------------------------------------------------------------------------
    # Burke Ratio
    # -------------------------------------------------------------------------

    async def _calculate_burke(
        self,
        context: PerformanceContext
    ) -> PerformanceResult:
        """Calculate Burke ratio"""
        if not context.returns:
            return self._empty_result(PerformanceMetric.BURKE_RATIO)
        
        value = calculate_burke_ratio(context.returns, annualize=True)
        
        ci = self._calculate_confidence_interval(context, value)
        
        return PerformanceResult(
            metric=PerformanceMetric.BURKE_RATIO,
            value=value,
            confidence_interval=ci,
            details={
                'annual_return': np.mean(context.returns) * 252,
                'drawdown_sse': 0.01  # Would calculate actual
            },
            status='success',
            message='Burke ratio calculated'
        )

    # -------------------------------------------------------------------------
    # Max Drawdown
    # -------------------------------------------------------------------------

    async def _calculate_max_drawdown(
        self,
        context: PerformanceContext
    ) -> PerformanceResult:
        """Calculate maximum drawdown"""
        if not context.returns:
            return self._empty_result(PerformanceMetric.MAX_DRAWDOWN)
        
        value = calculate_drawdown(context.returns)
        
        ci = self._calculate_confidence_interval(context, value)
        
        return PerformanceResult(
            metric=PerformanceMetric.MAX_DRAWDOWN,
            value=value,
            confidence_interval=ci,
            details={
                'peak': self._find_peak(context.returns),
                'trough': self._find_trough(context.returns),
                'duration': self._calculate_drawdown_duration(context.returns)
            },
            status='success',
            message='Maximum drawdown calculated'
        )

    # -------------------------------------------------------------------------
    # Current Drawdown
    # -------------------------------------------------------------------------

    async def _calculate_current_drawdown(
        self,
        context: PerformanceContext
    ) -> PerformanceResult:
        """Calculate current drawdown"""
        if not context.returns:
            return self._empty_result(PerformanceMetric.CURRENT_DRAWDOWN)
        
        value = calculate_drawdown(context.returns, current_only=True)
        
        ci = self._calculate_confidence_interval(context, value)
        
        return PerformanceResult(
            metric=PerformanceMetric.CURRENT_DRAWDOWN,
            value=value,
            confidence_interval=ci,
            details={
                'current_peak': max(context.returns),
                'current_value': context.returns[-1] if context.returns else 0
            },
            status='success',
            message='Current drawdown calculated'
        )

    # -------------------------------------------------------------------------
    # Win Rate
    # -------------------------------------------------------------------------

    async def _calculate_win_rate(
        self,
        context: PerformanceContext
    ) -> PerformanceResult:
        """Calculate win rate"""
        if not context.trades:
            return self._empty_result(PerformanceMetric.WIN_RATE)
        
        winning_trades = [t for t in context.trades if float(t.pnl) > 0]
        value = len(winning_trades) / len(context.trades) if context.trades else 0
        
        # Confidence interval for binomial proportion
        n = len(context.trades)
        if n > 0:
            se = np.sqrt(value * (1 - value) / n)
            z = stats.norm.ppf(context.confidence_level)
            ci = (max(0, value - z * se), min(1, value + z * se))
        else:
            ci = (0, 0)
        
        return PerformanceResult(
            metric=PerformanceMetric.WIN_RATE,
            value=value,
            confidence_interval=ci,
            details={
                'total_trades': n,
                'winning_trades': len(winning_trades),
                'losing_trades': n - len(winning_trades)
            },
            status='success',
            message='Win rate calculated'
        )

    # -------------------------------------------------------------------------
    # Profit Factor
    # -------------------------------------------------------------------------

    async def _calculate_profit_factor(
        self,
        context: PerformanceContext
    ) -> PerformanceResult:
        """Calculate profit factor"""
        if not context.trades:
            return self._empty_result(PerformanceMetric.PROFIT_FACTOR)
        
        gross_profit = sum(float(t.pnl) for t in context.trades if float(t.pnl) > 0)
        gross_loss = abs(sum(float(t.pnl) for t in context.trades if float(t.pnl) < 0))
        value = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        ci = self._calculate_confidence_interval(context, value)
        
        return PerformanceResult(
            metric=PerformanceMetric.PROFIT_FACTOR,
            value=value,
            confidence_interval=ci,
            details={
                'gross_profit': gross_profit,
                'gross_loss': gross_loss,
                'total_trades': len(context.trades)
            },
            status='success',
            message='Profit factor calculated'
        )

    # -------------------------------------------------------------------------
    # Expected Value
    # -------------------------------------------------------------------------

    async def _calculate_expected_value(
        self,
        context: PerformanceContext
    ) -> PerformanceResult:
        """Calculate expected value"""
        if not context.trades:
            return self._empty_result(PerformanceMetric.EXPECTED_VALUE)
        
        pnls = [float(t.pnl) for t in context.trades]
        value = np.mean(pnls)
        
        ci = self._calculate_confidence_interval(context, value)
        
        return PerformanceResult(
            metric=PerformanceMetric.EXPECTED_VALUE,
            value=value,
            confidence_interval=ci,
            details={
                'total_trades': len(pnls),
                'std_pnl': np.std(pnls),
                'min_pnl': min(pnls),
                'max_pnl': max(pnls)
            },
            status='success',
            message='Expected value calculated'
        )

    # -------------------------------------------------------------------------
    # Risk Adjusted Return
    # -------------------------------------------------------------------------

    async def _calculate_risk_adjusted_return(
        self,
        context: PerformanceContext
    ) -> PerformanceResult:
        """Calculate risk-adjusted return"""
        if not context.returns:
            return self._empty_result(PerformanceMetric.RISK_ADJUSTED_RETURN)
        
        avg_return = np.mean(context.returns) * 252
        std_return = np.std(context.returns) * np.sqrt(252)
        value = avg_return / std_return if std_return > 0 else 0
        
        ci = self._calculate_confidence_interval(context, value)
        
        return PerformanceResult(
            metric=PerformanceMetric.RISK_ADJUSTED_RETURN,
            value=value,
            confidence_interval=ci,
            details={
                'avg_return': avg_return,
                'std_return': std_return,
                'risk_free_rate': context.risk_free_rate
            },
            status='success',
            message='Risk-adjusted return calculated'
        )

    # -------------------------------------------------------------------------
    # Recovery Factor
    # -------------------------------------------------------------------------

    async def _calculate_recovery_factor(
        self,
        context: PerformanceContext
    ) -> PerformanceResult:
        """Calculate recovery factor"""
        if not context.returns:
            return self._empty_result(PerformanceMetric.RECOVERY_FACTOR)
        
        total_return = context.returns[-1] if context.returns else 0
        max_dd = calculate_drawdown(context.returns)
        value = total_return / max_dd if max_dd > 0 else float('inf')
        
        ci = self._calculate_confidence_interval(context, value)
        
        return PerformanceResult(
            metric=PerformanceMetric.RECOVERY_FACTOR,
            value=value,
            confidence_interval=ci,
            details={
                'total_return': total_return,
                'max_drawdown': max_dd
            },
            status='success',
            message='Recovery factor calculated'
        )

    # -------------------------------------------------------------------------
    # K-Ratio
    # -------------------------------------------------------------------------

    async def _calculate_k_ratio(
        self,
        context: PerformanceContext
    ) -> PerformanceResult:
        """Calculate K-ratio"""
        if not context.returns or len(context.returns) < 2:
            return self._empty_result(PerformanceMetric.K_RATIO)
        
        # Calculate cumulative returns
        cumulative = np.cumprod(1 + np.array(context.returns))
        
        # Linear regression on log returns
        x = np.arange(len(cumulative))
        y = np.log(cumulative)
        slope, intercept = np.polyfit(x, y, 1)
        
        # K-ratio = slope / (std of residuals)
        residuals = y - (slope * x + intercept)
        std_residuals = np.std(residuals)
        value = slope / std_residuals if std_residuals > 0 else 0
        
        ci = self._calculate_confidence_interval(context, value)
        
        return PerformanceResult(
            metric=PerformanceMetric.K_RATIO,
            value=value,
            confidence_interval=ci,
            details={
                'slope': slope,
                'r_squared': np.corrcoef(x, y)[0, 1] ** 2,
                'n_points': len(x)
            },
            status='success',
            message='K-ratio calculated'
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _empty_result(self, metric: PerformanceMetric) -> PerformanceResult:
        """Return empty result"""
        return PerformanceResult(
            metric=metric,
            value=0,
            confidence_interval=(0, 0),
            details={},
            status='error',
            message='Insufficient data'
        )

    def _calculate_confidence_interval(
        self,
        context: PerformanceContext,
        value: float
    ) -> Tuple[float, float]:
        """Calculate confidence interval"""
        if len(context.returns) > 1:
            std_error = np.std(context.returns) / np.sqrt(len(context.returns))
            z_score = stats.norm.ppf(context.confidence_level)
            margin = z_score * std_error
            return (value - margin, value + margin)
        return (value, value)

    def _find_peak(self, returns: List[float]) -> float:
        """Find peak in returns"""
        cumulative = np.cumprod(1 + np.array(returns))
        return float(np.max(cumulative)) if len(cumulative) > 0 else 0

    def _find_trough(self, returns: List[float]) -> float:
        """Find trough in returns"""
        cumulative = np.cumprod(1 + np.array(returns))
        return float(np.min(cumulative)) if len(cumulative) > 0 else 0

    def _calculate_drawdown_duration(self, returns: List[float]) -> int:
        """Calculate drawdown duration in days"""
        cumulative = np.cumprod(1 + np.array(returns))
        
        max_duration = 0
        current_duration = 0
        peak = cumulative[0] if len(cumulative) > 0 else 0
        
        for value in cumulative:
            if value > peak:
                peak = value
                current_duration = 0
            else:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
        
        return max_duration

    # =========================================================================
    # Benchmark Metrics
    # =========================================================================

    async def _get_benchmark_metrics(
        self,
        benchmark: str,
        period: str
    ) -> Dict[str, float]:
        """Get benchmark performance metrics"""
        try:
            benchmark_returns = await self._get_benchmark_returns(benchmark, period)
            if not benchmark_returns:
                return {}
            
            metrics = {}
            
            # Sharpe ratio
            metrics['sharpe_ratio'] = calculate_sharpe_ratio(
                benchmark_returns,
                annualize=True
            )
            
            # Sortino ratio
            metrics['sortino_ratio'] = calculate_sortino_ratio(
                benchmark_returns,
                annualize=True
            )
            
            # Calmar ratio
            metrics['calmar_ratio'] = calculate_calmar_ratio(
                benchmark_returns,
                annualize=True
            )
            
            # Max drawdown
            metrics['max_drawdown'] = calculate_drawdown(benchmark_returns)
            
            return metrics
            
        except Exception as e:
            logger.warning(f"Error getting benchmark metrics: {e}")
            return {}

    # =========================================================================
    # Attribution Analysis
    # =========================================================================

    async def _calculate_attribution(
        self,
        context: PerformanceContext
    ) -> Dict[str, Any]:
        """Calculate performance attribution"""
        if not context.trades or not context.positions:
            return {}
        
        attribution = {
            'total_return': 0,
            'allocation_effect': 0,
            'selection_effect': 0,
            'interaction_effect': 0,
            'by_asset': {},
            'by_sector': {},
            'by_strategy': {}
        }
        
        try:
            # Group by asset
            asset_weights = {}
            asset_returns = {}
            
            for position in context.positions:
                symbol = position.symbol
                value = float(position.size) * float(position.entry_price)
                asset_weights[symbol] = asset_weights.get(symbol, 0) + value
            
            total_value = sum(asset_weights.values())
            if total_value > 0:
                asset_weights = {k: v / total_value for k, v in asset_weights.items()}
            
            # Calculate asset returns
            for trade in context.trades:
                symbol = trade.symbol
                pnl = float(trade.pnl)
                if symbol not in asset_returns:
                    asset_returns[symbol] = 0
                asset_returns[symbol] += pnl
            
            # Calculate attribution
            total_return = sum(asset_returns.values()) / total_value if total_value > 0 else 0
            attribution['total_return'] = total_return
            
            # Calculate allocation effect
            benchmark_weights = {k: 1/len(asset_weights) for k in asset_weights}
            for asset, weight in asset_weights.items():
                bench_weight = benchmark_weights.get(asset, 0)
                asset_return = asset_returns.get(asset, 0) / (asset_weights.get(asset, 1) * total_value) if total_value > 0 else 0
                allocation_effect = (weight - bench_weight) * asset_return
                attribution['allocation_effect'] += allocation_effect
            
            # Calculate selection effect
            for asset, weight in asset_weights.items():
                asset_return = asset_returns.get(asset, 0) / (weight * total_value) if total_value > 0 else 0
                benchmark_return = total_return
                selection_effect = weight * (asset_return - benchmark_return)
                attribution['selection_effect'] += selection_effect
            
            # Calculate by asset
            for asset in asset_weights:
                attribution['by_asset'][asset] = {
                    'weight': asset_weights.get(asset, 0),
                    'return': asset_returns.get(asset, 0) / (asset_weights.get(asset, 1) * total_value) if total_value > 0 else 0,
                    'contribution': (asset_weights.get(asset, 0) * asset_returns.get(asset, 0)) / total_value if total_value > 0 else 0
                }
            
        except Exception as e:
            logger.error(f"Error calculating attribution: {e}")
        
        return attribution

    # =========================================================================
    # Performance History
    # =========================================================================

    async def get_performance_history(
        self,
        portfolio_id: str,
        metric: PerformanceMetric,
        period: str = "1y",
        window: int = 30
    ) -> PerformanceHistoryResponse:
        """
        Get performance history.
        
        Args:
            portfolio_id: Portfolio ID
            metric: Performance metric
            period: Time period
            window: Rolling window
            
        Returns:
            PerformanceHistoryResponse: Performance history
        """
        try:
            # Get returns
            trades = await self.trade_repo.get_by_portfolio_id(portfolio_id)
            returns, dates = self._calculate_returns(trades, period)
            
            if not returns:
                return PerformanceHistoryResponse(
                    portfolio_id=portfolio_id,
                    metric=metric,
                    history=[],
                    trend='stable',
                    volatility=0,
                    summary={}
                )
            
            # Calculate rolling metric
            history = []
            for i in range(window, len(returns)):
                window_returns = returns[i-window:i]
                value = await self._calculate_metric_value(metric, window_returns)
                history.append({
                    'date': dates[i] if i < len(dates) else datetime.utcnow(),
                    'value': value
                })
            
            # Calculate trend
            values = [h['value'] for h in history]
            if len(values) > 1:
                slope, _ = np.polyfit(range(len(values)), values, 1)
                if slope > 0.01:
                    trend = 'increasing'
                elif slope < -0.01:
                    trend = 'decreasing'
                else:
                    trend = 'stable'
            else:
                trend = 'stable'
            
            # Calculate volatility
            volatility = np.std(values) if values else 0
            
            return PerformanceHistoryResponse(
                portfolio_id=portfolio_id,
                metric=metric,
                history=history,
                trend=trend,
                volatility=volatility,
                summary={
                    'current': values[-1] if values else 0,
                    'max': max(values) if values else 0,
                    'min': min(values) if values else 0,
                    'avg': np.mean(values) if values else 0,
                    'std': volatility
                }
            )
            
        except Exception as e:
            logger.error(f"Error getting performance history: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Performance history retrieval failed: {str(e)}"
            )

    async def _calculate_metric_value(
        self,
        metric: PerformanceMetric,
        returns: List[float]
    ) -> float:
        """Calculate metric value for a window"""
        if metric == PerformanceMetric.SHARPE_RATIO:
            return calculate_sharpe_ratio(returns, annualize=True)
        elif metric == PerformanceMetric.SORTINO_RATIO:
            return calculate_sortino_ratio(returns, annualize=True)
        elif metric == PerformanceMetric.CALMAR_RATIO:
            return calculate_calmar_ratio(returns, annualize=True)
        elif metric == PerformanceMetric.MAX_DRAWDOWN:
            return calculate_drawdown(returns)
        else:
            return 0

    # =========================================================================
    # Recommendations
    # =========================================================================

    async def _generate_recommendations(
        self,
        request: PerformanceRequest,
        context: PerformanceContext,
        result: PerformanceResult,
        benchmark_value: Optional[float]
    ) -> List[str]:
        """Generate recommendations"""
        recommendations = []
        
        # Check metric value
        if request.metric == PerformanceMetric.SHARPE_RATIO:
            if result.value < 0.5:
                recommendations.append("Low Sharpe ratio. Consider reducing risk or improving returns.")
            elif result.value > 1.5:
                recommendations.append("Excellent Sharpe ratio. Maintain current risk management.")
            
            if benchmark_value and result.value < benchmark_value:
                recommendations.append(f"Sharpe ratio ({result.value:.2f}) below benchmark ({benchmark_value:.2f}). Consider adjusting strategy.")
        
        elif request.metric == PerformanceMetric.MAX_DRAWDOWN:
            if result.value > 0.20:
                recommendations.append("High max drawdown. Consider implementing stricter risk controls.")
            elif result.value > 0.10:
                recommendations.append("Moderate drawdown. Monitor risk exposure.")
        
        elif request.metric == PerformanceMetric.WIN_RATE:
            if result.value < 0.40:
                recommendations.append("Low win rate. Consider reviewing trade entry criteria.")
            elif result.value > 0.70:
                recommendations.append("High win rate. Ensure this is sustainable.")
        
        elif request.metric == PerformanceMetric.PROFIT_FACTOR:
            if result.value < 1.0:
                recommendations.append("Profit factor below 1. Strategy needs improvement.")
            elif result.value < 1.5:
                recommendations.append("Moderate profit factor. Look for optimization opportunities.")
        
        # General recommendations
        if len(context.returns) < 30:
            recommendations.append("Limited historical data. Results may not be statistically significant.")
        
        if not recommendations:
            recommendations.append("All performance metrics are within acceptable ranges.")
        
        return recommendations

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the performance module"""
        self._performance_cache.clear()
        self._returns_cache.clear()
        logger.info("PortfolioPerformance closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/api/v1/portfolio/performance", tags=["Portfolio Performance"])


async def get_performance() -> PortfolioPerformance:
    """Dependency to get PortfolioPerformance instance"""
    return PortfolioPerformance()


@router.post("/", response_model=PerformanceResponse)
async def calculate_performance(
    request: PerformanceRequest,
    performance: PortfolioPerformance = Depends(get_performance)
):
    """Calculate portfolio performance metric"""
    return await performance.calculate_performance(request)


@router.get("/{portfolio_id}/history")
async def get_performance_history(
    portfolio_id: str,
    metric: PerformanceMetric = Query(PerformanceMetric.SHARPE_RATIO),
    period: str = Query("1y"),
    window: int = Query(30, ge=5, le=100),
    performance: PortfolioPerformance = Depends(get_performance)
):
    """Get performance history"""
    return await performance.get_performance_history(portfolio_id, metric, period, window)


@router.get("/metrics")
async def get_performance_metrics():
    """Get available performance metrics"""
    return {
        'metrics': [
            {'name': m.value, 'description': m.name.replace('_', ' ').title()}
            for m in PerformanceMetric
        ]
    }


@router.get("/benchmarks")
async def get_benchmarks():
    """Get available benchmarks"""
    return {
        'benchmarks': [
            {'name': name, 'symbol': symbol}
            for name, symbol in PortfolioPerformance(None)._benchmarks.items()
        ]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PortfolioPerformance',
    'PerformanceMetric',
    'ComparisonType',
    'AttributionType',
    'PerformanceRequest',
    'PerformanceResponse',
    'PerformanceHistoryResponse',
    'ComparisonResponse',
    'PerformanceContext',
    'PerformanceResult',
    'AttributionResult',
    'router'
]
