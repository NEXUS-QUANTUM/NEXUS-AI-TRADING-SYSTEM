"""
NEXUS AI TRADING SYSTEM - Portfolio Risk Metrics Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/portfolio/risk_metrics.py
Description: Advanced portfolio risk metrics calculation with full API integration
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
from scipy.optimize import minimize
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
    calculate_burke_ratio,
    calculate_drawdown
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.repositories.position_repository import PositionRepository
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.portfolio_repository import PortfolioRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

# Risk management imports
from trading.risk_management.var_calculator import VaRCalculator
from trading.risk_management.risk_limits import RiskLimitsManager

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class RiskMetricType(str, Enum):
    """Types of risk metrics"""
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    OMEGA_RATIO = "omega_ratio"
    STERLING_RATIO = "sterling_ratio"
    BURKE_RATIO = "burke_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    CURRENT_DRAWDOWN = "current_drawdown"
    VAR_95 = "var_95"
    CVAR_95 = "cvar_95"
    VAR_99 = "var_99"
    CVAR_99 = "cvar_99"
    EXPECTED_RETURN = "expected_return"
    VOLATILITY = "volatility"
    BETA = "beta"
    ALPHA = "alpha"
    LEVERAGE = "leverage"
    CONCENTRATION = "concentration"
    DIVERSIFICATION = "diversification"
    CORRELATION = "correlation"
    TAIL_RISK = "tail_risk"
    LIQUIDITY_RISK = "liquidity_risk"
    STRESS_LOSS = "stress_loss"


class RiskLevel(str, Enum):
    """Risk levels"""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class RiskMetricsRequest(BaseModel):
    """Request model for risk metrics"""
    portfolio_id: str
    metrics: List[RiskMetricType] = []
    lookback_period: int = 252
    confidence_level: float = 0.95
    risk_free_rate: float = 0.03
    include_all: bool = False
    include_details: bool = True
    include_recommendations: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('confidence_level')
    def validate_confidence(cls, v):
        if not 0 < v < 1:
            raise ValueError('Confidence level must be between 0 and 1')
        return v


class RiskMetricsResponse(BaseModel):
    """Response model for risk metrics"""
    portfolio_id: str
    timestamp: datetime
    risk_level: RiskLevel
    metrics: Dict[str, Any]
    details: Dict[str, Any]
    recommendations: List[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskMetricsHistoryResponse(BaseModel):
    """Response model for risk metrics history"""
    portfolio_id: str
    metric: RiskMetricType
    history: List[Dict[str, Any]]
    trend: str
    volatility: float
    summary: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class RiskMetricsContext:
    """Context for risk metrics"""
    portfolio_id: str
    lookback_period: int
    returns: List[float]
    dates: List[datetime]
    trades: List[Any]
    positions: List[Any]
    portfolio_value: float
    risk_free_rate: float
    confidence_level: float
    timestamp: datetime


@dataclass
class RiskMetricsResult:
    """Result of risk metrics calculation"""
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    omega_ratio: float
    sterling_ratio: float
    burke_ratio: float
    max_drawdown: float
    current_drawdown: float
    var_95: float
    cvar_95: float
    var_99: float
    cvar_99: float
    expected_return: float
    volatility: float
    beta: float
    alpha: float
    leverage: float
    concentration: float
    diversification: float
    correlation: float
    tail_risk: float
    liquidity_risk: float
    stress_loss: float
    risk_level: RiskLevel
    details: Dict[str, Any]


# =============================================================================
# RISK METRICS
# =============================================================================

class PortfolioRiskMetrics:
    """
    Advanced Portfolio Risk Metrics with full API integration.
    
    Features:
    - Multiple risk metrics (Sharpe, Sortino, Calmar, Omega, Sterling, Burke)
    - Value at Risk (VaR) and Conditional VaR (CVaR)
    - Drawdown analysis
    - Beta and Alpha
    - Concentration and diversification
    - Correlation analysis
    - Tail risk assessment
    - Liquidity risk
    - Stress testing
    - Risk level classification
    """

    def __init__(
        self,
        config: Optional[PortfolioConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        position_repo: Optional[PositionRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        portfolio_repo: Optional[PortfolioRepository] = None,
        var_calculator: Optional[VaRCalculator] = None,
        risk_limits: Optional[RiskLimitsManager] = None
    ):
        """
        Initialize PortfolioRiskMetrics.
        
        Args:
            config: Portfolio configuration
            broker_factory: Factory for broker instances
            position_repo: Position repository
            trade_repo: Trade repository
            portfolio_repo: Portfolio repository
            var_calculator: VaR calculator
            risk_limits: Risk limits manager
        """
        self.config = config or PortfolioConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.position_repo = position_repo or PositionRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.portfolio_repo = portfolio_repo or PortfolioRepository()
        self.var_calculator = var_calculator or VaRCalculator()
        self.risk_limits = risk_limits or RiskLimitsManager()
        
        # Cache
        self._metrics_cache: Dict[str, Dict[str, Any]] = {}
        self._returns_cache: Dict[str, List[float]] = {}
        
        logger.info("PortfolioRiskMetrics initialized")

    # =========================================================================
    # Risk Metrics Calculation
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def calculate_risk_metrics(
        self,
        request: RiskMetricsRequest
    ) -> RiskMetricsResponse:
        """
        Calculate portfolio risk metrics.
        
        Args:
            request: Risk metrics request
            
        Returns:
            RiskMetricsResponse: Risk metrics results
        """
        try:
            # Build context
            context = await self._build_context(request)
            
            # Calculate all metrics if requested
            if request.include_all or not request.metrics:
                metrics_to_calc = list(RiskMetricType)
            else:
                metrics_to_calc = request.metrics
            
            # Calculate metrics
            result = await self._calculate_metrics(context, metrics_to_calc)
            
            # Determine risk level
            risk_level = self._determine_risk_level(result)
            
            # Generate recommendations
            recommendations = []
            if request.include_recommendations:
                recommendations = await self._generate_recommendations(result)
            
            # Create response
            response = RiskMetricsResponse(
                portfolio_id=request.portfolio_id,
                timestamp=datetime.utcnow(),
                risk_level=risk_level,
                metrics=result.__dict__,
                details=result.details,
                recommendations=recommendations,
                metadata=request.metadata
            )
            
            # Cache
            cache_key = f"{request.portfolio_id}_{request.lookback_period}"
            self._metrics_cache[cache_key] = {
                'response': response,
                'context': context,
                'timestamp': datetime.utcnow()
            }
            
            logger.info(f"Risk metrics calculated for {request.portfolio_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Risk metrics calculation failed: {str(e)}"
            )

    async def _build_context(
        self,
        request: RiskMetricsRequest
    ) -> RiskMetricsContext:
        """Build risk metrics context"""
        # Get trades
        trades = await self.trade_repo.get_by_portfolio_id(
            request.portfolio_id,
            limit=request.lookback_period * 2
        )
        
        # Get positions
        positions = await self.position_repo.get_by_portfolio_id(request.portfolio_id)
        
        # Get portfolio value
        portfolio = await self.portfolio_repo.get_by_id(request.portfolio_id)
        portfolio_value = float(portfolio.total_value) if portfolio else 0
        
        # Calculate returns
        returns, dates = self._calculate_returns(trades, request.lookback_period)
        
        return RiskMetricsContext(
            portfolio_id=request.portfolio_id,
            lookback_period=request.lookback_period,
            returns=returns,
            dates=dates,
            trades=trades,
            positions=positions,
            portfolio_value=portfolio_value,
            risk_free_rate=request.risk_free_rate,
            confidence_level=request.confidence_level,
            timestamp=datetime.utcnow()
        )

    def _calculate_returns(
        self,
        trades: List[Any],
        lookback_period: int
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

    # =========================================================================
    # Metric Calculations
    # =========================================================================

    async def _calculate_metrics(
        self,
        context: RiskMetricsContext,
        metrics_to_calc: List[RiskMetricType]
    ) -> RiskMetricsResult:
        """Calculate risk metrics"""
        result = RiskMetricsResult(
            sharpe_ratio=0,
            sortino_ratio=0,
            calmar_ratio=0,
            omega_ratio=0,
            sterling_ratio=0,
            burke_ratio=0,
            max_drawdown=0,
            current_drawdown=0,
            var_95=0,
            cvar_95=0,
            var_99=0,
            cvar_99=0,
            expected_return=0,
            volatility=0,
            beta=0,
            alpha=0,
            leverage=0,
            concentration=0,
            diversification=0,
            correlation=0,
            tail_risk=0,
            liquidity_risk=0,
            stress_loss=0,
            risk_level=RiskLevel.MODERATE,
            details={}
        )
        
        # Performance ratios
        if RiskMetricType.SHARPE_RATIO in metrics_to_calc:
            result.sharpe_ratio = self._calculate_sharpe_ratio(context)
        
        if RiskMetricType.SORTINO_RATIO in metrics_to_calc:
            result.sortino_ratio = self._calculate_sortino_ratio(context)
        
        if RiskMetricType.CALMAR_RATIO in metrics_to_calc:
            result.calmar_ratio = self._calculate_calmar_ratio(context)
        
        if RiskMetricType.OMEGA_RATIO in metrics_to_calc:
            result.omega_ratio = self._calculate_omega_ratio(context)
        
        if RiskMetricType.STERLING_RATIO in metrics_to_calc:
            result.sterling_ratio = self._calculate_sterling_ratio(context)
        
        if RiskMetricType.BURKE_RATIO in metrics_to_calc:
            result.burke_ratio = self._calculate_burke_ratio(context)
        
        # Drawdown metrics
        if RiskMetricType.MAX_DRAWDOWN in metrics_to_calc:
            result.max_drawdown = self._calculate_max_drawdown(context)
        
        if RiskMetricType.CURRENT_DRAWDOWN in metrics_to_calc:
            result.current_drawdown = self._calculate_current_drawdown(context)
        
        # VaR metrics
        if RiskMetricType.VAR_95 in metrics_to_calc:
            result.var_95 = self._calculate_var(context, 0.95)
        
        if RiskMetricType.CVAR_95 in metrics_to_calc:
            result.cvar_95 = self._calculate_cvar(context, 0.95)
        
        if RiskMetricType.VAR_99 in metrics_to_calc:
            result.var_99 = self._calculate_var(context, 0.99)
        
        if RiskMetricType.CVAR_99 in metrics_to_calc:
            result.cvar_99 = self._calculate_cvar(context, 0.99)
        
        # Return and volatility
        if RiskMetricType.EXPECTED_RETURN in metrics_to_calc:
            result.expected_return = self._calculate_expected_return(context)
        
        if RiskMetricType.VOLATILITY in metrics_to_calc:
            result.volatility = self._calculate_volatility(context)
        
        # Beta and Alpha
        if RiskMetricType.BETA in metrics_to_calc:
            result.beta = self._calculate_beta(context)
        
        if RiskMetricType.ALPHA in metrics_to_calc:
            result.alpha = self._calculate_alpha(context)
        
        # Portfolio metrics
        if RiskMetricType.LEVERAGE in metrics_to_calc:
            result.leverage = self._calculate_leverage(context)
        
        if RiskMetricType.CONCENTRATION in metrics_to_calc:
            result.concentration = self._calculate_concentration(context)
        
        if RiskMetricType.DIVERSIFICATION in metrics_to_calc:
            result.diversification = self._calculate_diversification(context)
        
        if RiskMetricType.CORRELATION in metrics_to_calc:
            result.correlation = self._calculate_correlation(context)
        
        # Advanced risk metrics
        if RiskMetricType.TAIL_RISK in metrics_to_calc:
            result.tail_risk = self._calculate_tail_risk(context)
        
        if RiskMetricType.LIQUIDITY_RISK in metrics_to_calc:
            result.liquidity_risk = self._calculate_liquidity_risk(context)
        
        if RiskMetricType.STRESS_LOSS in metrics_to_calc:
            result.stress_loss = self._calculate_stress_loss(context)
        
        # Details
        result.details = {
            'returns_count': len(context.returns),
            'dates_count': len(context.dates),
            'trades_count': len(context.trades),
            'positions_count': len(context.positions),
            'portfolio_value': context.portfolio_value
        }
        
        # Determine risk level
        result.risk_level = self._determine_risk_level(result)
        
        return result

    # -------------------------------------------------------------------------
    # Performance Ratios
    # -------------------------------------------------------------------------

    def _calculate_sharpe_ratio(self, context: RiskMetricsContext) -> float:
        """Calculate Sharpe ratio"""
        if not context.returns:
            return 0
        return calculate_sharpe_ratio(
            context.returns,
            context.risk_free_rate,
            annualize=True
        )

    def _calculate_sortino_ratio(self, context: RiskMetricsContext) -> float:
        """Calculate Sortino ratio"""
        if not context.returns:
            return 0
        return calculate_sortino_ratio(
            context.returns,
            context.risk_free_rate,
            annualize=True
        )

    def _calculate_calmar_ratio(self, context: RiskMetricsContext) -> float:
        """Calculate Calmar ratio"""
        if not context.returns:
            return 0
        return calculate_calmar_ratio(context.returns, annualize=True)

    def _calculate_omega_ratio(self, context: RiskMetricsContext) -> float:
        """Calculate Omega ratio"""
        if not context.returns:
            return 0
        return calculate_omega_ratio(context.returns, context.risk_free_rate)

    def _calculate_sterling_ratio(self, context: RiskMetricsContext) -> float:
        """Calculate Sterling ratio"""
        if not context.returns:
            return 0
        return calculate_sterling_ratio(context.returns, annualize=True)

    def _calculate_burke_ratio(self, context: RiskMetricsContext) -> float:
        """Calculate Burke ratio"""
        if not context.returns:
            return 0
        return calculate_burke_ratio(context.returns, annualize=True)

    # -------------------------------------------------------------------------
    # Drawdown Metrics
    # -------------------------------------------------------------------------

    def _calculate_max_drawdown(self, context: RiskMetricsContext) -> float:
        """Calculate maximum drawdown"""
        if not context.returns:
            return 0
        return calculate_drawdown(context.returns)

    def _calculate_current_drawdown(self, context: RiskMetricsContext) -> float:
        """Calculate current drawdown"""
        if not context.returns:
            return 0
        return calculate_drawdown(context.returns, current_only=True)

    # -------------------------------------------------------------------------
    # VaR Metrics
    # -------------------------------------------------------------------------

    def _calculate_var(self, context: RiskMetricsContext, confidence: float) -> float:
        """Calculate Value at Risk"""
        if len(context.returns) < 30:
            return 0
        
        var = np.percentile(context.returns, (1 - confidence) * 100)
        return abs(var) * context.portfolio_value

    def _calculate_cvar(self, context: RiskMetricsContext, confidence: float) -> float:
        """Calculate Conditional VaR"""
        if len(context.returns) < 30:
            return 0
        
        var = np.percentile(context.returns, (1 - confidence) * 100)
        losses_below_var = [r for r in context.returns if r <= var]
        if losses_below_var:
            cvar = np.mean(losses_below_var)
        else:
            cvar = var
        return abs(cvar) * context.portfolio_value

    # -------------------------------------------------------------------------
    # Return and Volatility
    # -------------------------------------------------------------------------

    def _calculate_expected_return(self, context: RiskMetricsContext) -> float:
        """Calculate expected return"""
        if not context.returns:
            return 0
        return np.mean(context.returns) * 252

    def _calculate_volatility(self, context: RiskMetricsContext) -> float:
        """Calculate volatility"""
        if not context.returns:
            return 0
        return np.std(context.returns) * np.sqrt(252)

    # -------------------------------------------------------------------------
    # Beta and Alpha
    # -------------------------------------------------------------------------

    def _calculate_beta(self, context: RiskMetricsContext) -> float:
        """Calculate beta"""
        # Simplified beta calculation
        if len(context.returns) < 30:
            return 1.0
        
        # Use returns as proxy for market returns
        market_returns = context.returns
        covariance = np.cov(context.returns, market_returns)[0, 1]
        variance = np.var(market_returns)
        
        if variance == 0:
            return 1.0
        
        beta = covariance / variance
        return beta

    def _calculate_alpha(self, context: RiskMetricsContext) -> float:
        """Calculate alpha"""
        beta = self._calculate_beta(context)
        expected_return = self._calculate_expected_return(context)
        market_return = 0.10  # Assumed market return
        
        return expected_return - (context.risk_free_rate + beta * (market_return - context.risk_free_rate))

    # -------------------------------------------------------------------------
    # Portfolio Metrics
    # -------------------------------------------------------------------------

    def _calculate_leverage(self, context: RiskMetricsContext) -> float:
        """Calculate leverage"""
        if not context.positions:
            return 1.0
        
        total_value = sum(float(p.size) * float(p.entry_price) for p in context.positions)
        if context.portfolio_value > 0:
            return total_value / context.portfolio_value
        return 1.0

    def _calculate_concentration(self, context: RiskMetricsContext) -> float:
        """Calculate concentration"""
        if not context.positions:
            return 0
        
        total_value = sum(float(p.size) * float(p.entry_price) for p in context.positions)
        if total_value == 0:
            return 0
        
        max_position = max(float(p.size) * float(p.entry_price) for p in context.positions)
        return max_position / total_value

    def _calculate_diversification(self, context: RiskMetricsContext) -> float:
        """Calculate diversification score"""
        if not context.positions:
            return 0
        
        # Calculate Herfindahl-Hirschman Index
        total_value = sum(float(p.size) * float(p.entry_price) for p in context.positions)
        if total_value == 0:
            return 0
        
        hhi = 0
        for pos in context.positions:
            weight = (float(pos.size) * float(pos.entry_price)) / total_value
            hhi += weight ** 2
        
        # Diversification = 1 - HHI (0 to 1, higher is better)
        return 1 - hhi

    def _calculate_correlation(self, context: RiskMetricsContext) -> float:
        """Calculate average correlation"""
        if len(context.positions) < 2:
            return 0
        
        # Simplified correlation calculation
        # Use returns as proxy
        returns = np.array(context.returns)
        if len(returns) < 30:
            return 0
        
        # Calculate correlation matrix
        corr_matrix = np.corrcoef(returns, returns)
        if corr_matrix.size > 1:
            # Average correlation excluding diagonal
            n = corr_matrix.shape[0]
            sum_corr = np.sum(corr_matrix) - n
            avg_corr = sum_corr / (n * (n - 1))
            return avg_corr
        return 0

    # -------------------------------------------------------------------------
    # Advanced Risk Metrics
    # -------------------------------------------------------------------------

    def _calculate_tail_risk(self, context: RiskMetricsContext) -> float:
        """Calculate tail risk"""
        if len(context.returns) < 30:
            return 0
        
        # Calculate tail risk as average of worst 5% returns
        sorted_returns = sorted(context.returns)
        tail_returns = sorted_returns[:int(len(sorted_returns) * 0.05)]
        if tail_returns:
            return abs(np.mean(tail_returns)) * np.sqrt(252)
        return 0

    def _calculate_liquidity_risk(self, context: RiskMetricsContext) -> float:
        """Calculate liquidity risk"""
        # Simplified liquidity risk based on position sizes
        if not context.positions:
            return 0
        
        total_value = sum(float(p.size) * float(p.entry_price) for p in context.positions)
        if total_value == 0:
            return 0
        
        # Average position size relative to portfolio
        avg_position = total_value / len(context.positions) if context.positions else 0
        liquidity_risk = avg_position / context.portfolio_value if context.portfolio_value > 0 else 0
        
        # Cap at 1
        return min(liquidity_risk, 1.0)

    def _calculate_stress_loss(self, context: RiskMetricsContext) -> float:
        """Calculate stress loss"""
        # Stress loss = 2x VaR (simplified)
        var_95 = self._calculate_var(context, 0.95)
        if var_95 > 0:
            return var_95 * 2
        return 0

    # =========================================================================
    # Risk Level Determination
    # =========================================================================

    def _determine_risk_level(self, result: RiskMetricsResult) -> RiskLevel:
        """Determine overall risk level"""
        score = 0
        
        # Sharpe ratio
        if result.sharpe_ratio < 0.5:
            score += 20
        elif result.sharpe_ratio < 1.0:
            score += 10
        
        # Max drawdown
        if result.max_drawdown > 0.20:
            score += 25
        elif result.max_drawdown > 0.10:
            score += 15
        
        # VaR
        if result.var_95 / result.portfolio_value > 0.05:
            score += 20
        elif result.var_95 / result.portfolio_value > 0.02:
            score += 10
        
        # Concentration
        if result.concentration > 0.40:
            score += 15
        elif result.concentration > 0.25:
            score += 10
        
        # Leverage
        if result.leverage > 2.0:
            score += 15
        elif result.leverage > 1.5:
            score += 10
        
        # Determine level
        if score >= 60:
            return RiskLevel.CRITICAL
        elif score >= 40:
            return RiskLevel.HIGH
        elif score >= 20:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.LOW

    # =========================================================================
    # Recommendations
    # =========================================================================

    async def _generate_recommendations(
        self,
        result: RiskMetricsResult
    ) -> List[str]:
        """Generate recommendations based on risk metrics"""
        recommendations = []
        
        if result.sharpe_ratio < 0.5:
            recommendations.append("Low Sharpe ratio. Consider improving risk-adjusted returns.")
        
        if result.sortino_ratio < 0.5:
            recommendations.append("Low Sortino ratio. Focus on reducing downside risk.")
        
        if result.calmar_ratio < 0.5:
            recommendations.append("Low Calmar ratio. Consider reducing drawdowns.")
        
        if result.max_drawdown > 0.20:
            recommendations.append("High max drawdown. Implement stricter risk controls.")
        
        if result.current_drawdown > 0.15:
            recommendations.append("Significant current drawdown. Consider reducing risk exposure.")
        
        if result.var_95 / result.portfolio_value > 0.05:
            recommendations.append("High VaR. Consider reducing position sizes.")
        
        if result.concentration > 0.40:
            recommendations.append("High concentration. Diversify across more assets.")
        
        if result.leverage > 2.0:
            recommendations.append("High leverage. Consider reducing leverage.")
        
        if result.correlation > 0.7:
            recommendations.append("High correlation between assets. Seek uncorrelated investments.")
        
        if result.tail_risk > 0.10:
            recommendations.append("Significant tail risk. Consider tail hedging strategies.")
        
        if result.liquidity_risk > 0.3:
            recommendations.append("Liquidity risk detected. Reduce position sizes in illiquid assets.")
        
        if not recommendations:
            recommendations.append("All risk metrics are within acceptable ranges.")
        
        return recommendations

    # =========================================================================
    # Risk Metrics History
    # =========================================================================

    async def get_metrics_history(
        self,
        portfolio_id: str,
        metric: RiskMetricType,
        period: str = "1y",
        window: int = 30
    ) -> RiskMetricsHistoryResponse:
        """
        Get risk metrics history.
        
        Args:
            portfolio_id: Portfolio ID
            metric: Risk metric type
            period: Time period
            window: Rolling window
            
        Returns:
            RiskMetricsHistoryResponse: Metrics history
        """
        try:
            # Get trades
            trades = await self.trade_repo.get_by_portfolio_id(
                portfolio_id,
                limit=1000
            )
            
            # Calculate returns
            returns, dates = self._calculate_returns(trades, 252)
            
            if not returns:
                return RiskMetricsHistoryResponse(
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
                value = self._calculate_single_metric(metric, window_returns)
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
            
            return RiskMetricsHistoryResponse(
                portfolio_id=portfolio_id,
                metric=metric,
                history=history,
                trend=trend,
                volatility=volatility,
                summary={
                    'current': values[-1] if values else 0,
                    'max': max(values) if values else 0,
                    'min': min(values) if values else 0,
                    'avg': np.mean(values) if values else 0
                }
            )
            
        except Exception as e:
            logger.error(f"Error getting metrics history: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Metrics history retrieval failed: {str(e)}"
            )

    def _calculate_single_metric(
        self,
        metric: RiskMetricType,
        returns: List[float]
    ) -> float:
        """Calculate single metric for rolling window"""
        if metric == RiskMetricType.SHARPE_RATIO:
            return calculate_sharpe_ratio(returns, annualize=True)
        elif metric == RiskMetricType.SORTINO_RATIO:
            return calculate_sortino_ratio(returns, annualize=True)
        elif metric == RiskMetricType.CALMAR_RATIO:
            return calculate_calmar_ratio(returns, annualize=True)
        elif metric == RiskMetricType.OMEGA_RATIO:
            return calculate_omega_ratio(returns, 0.03)
        elif metric == RiskMetricType.MAX_DRAWDOWN:
            return calculate_drawdown(returns)
        else:
            return 0

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the risk metrics module"""
        self._metrics_cache.clear()
        self._returns_cache.clear()
        logger.info("PortfolioRiskMetrics closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/api/v1/portfolio/risk-metrics", tags=["Portfolio Risk Metrics"])


async def get_risk_metrics() -> PortfolioRiskMetrics:
    """Dependency to get PortfolioRiskMetrics instance"""
    return PortfolioRiskMetrics()


@router.post("/", response_model=RiskMetricsResponse)
async def calculate_risk_metrics(
    request: RiskMetricsRequest,
    risk_metrics: PortfolioRiskMetrics = Depends(get_risk_metrics)
):
    """Calculate portfolio risk metrics"""
    return await risk_metrics.calculate_risk_metrics(request)


@router.get("/{portfolio_id}/history")
async def get_metrics_history(
    portfolio_id: str,
    metric: RiskMetricType = Query(RiskMetricType.SHARPE_RATIO),
    period: str = Query("1y"),
    window: int = Query(30, ge=5, le=100),
    risk_metrics: PortfolioRiskMetrics = Depends(get_risk_metrics)
):
    """Get risk metrics history"""
    return await risk_metrics.get_metrics_history(portfolio_id, metric, period, window)


@router.get("/metrics")
async def get_risk_metric_types():
    """Get available risk metric types"""
    return {
        'metrics': [
            {'name': m.value, 'description': m.name.replace('_', ' ').title()}
            for m in RiskMetricType
        ]
    }


@router.get("/levels")
async def get_risk_levels():
    """Get risk levels"""
    return {
        'levels': [
            {'name': l.value, 'description': l.name.title()}
            for l in RiskLevel
        ]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PortfolioRiskMetrics',
    'RiskMetricType',
    'RiskLevel',
    'RiskMetricsRequest',
    'RiskMetricsResponse',
    'RiskMetricsHistoryResponse',
    'RiskMetricsContext',
    'RiskMetricsResult',
    'router'
]
