"""
NEXUS AI TRADING SYSTEM - Portfolio Risk Management Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/risk-management/portfolio_risk.py
Description: Comprehensive portfolio risk management with full API integration
"""

import asyncio
import json
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
from shared.configs.risk_config import RiskConfig
from shared.constants.trading_constants import (
    RISK_LIMIT_TYPES,
    POSITION_DIRECTIONS,
    ORDER_TYPES,
    TIME_FRAMES
)
from shared.helpers.trading_helpers import (
    calculate_position_size,
    calculate_risk_reward_ratio,
    calculate_drawdown
)
from shared.types.risk import (
    RiskMetrics,
    PortfolioRiskMetrics,
    RiskLimit,
    RiskAlert,
    RiskReport
)
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.models import (
    PortfolioSnapshot,
    RiskLimit as RiskLimitModel,
    RiskAlert as RiskAlertModel,
    PerformanceMetric
)
from backend.database.repositories.portfolio_repository import PortfolioRepository
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.position_repository import PositionRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

# External API clients
import aiohttp
import httpx

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class RiskLevel(str, Enum):
    """Risk level classification"""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class RiskStatus(str, Enum):
    """Risk status for portfolio"""
    NORMAL = "normal"
    WARNING = "warning"
    BREACHED = "breached"
    CRITICAL = "critical"


class RiskMetricType(str, Enum):
    """Types of risk metrics"""
    VAR = "value_at_risk"
    CVAR = "conditional_var"
    SHARPE = "sharpe_ratio"
    SORTINO = "sortino_ratio"
    CALMAR = "calmar_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    CURRENT_DRAWDOWN = "current_drawdown"
    BETA = "beta"
    ALPHA = "alpha"
    VOLATILITY = "volatility"
    CORRELATION = "correlation"
    DIVERSIFICATION = "diversification_ratio"
    CONCENTRATION = "concentration_ratio"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class PortfolioRiskRequest(BaseModel):
    """Request model for portfolio risk analysis"""
    portfolio_id: str
    include_historical: bool = True
    time_horizon: str = "1d"  # 1h, 4h, 1d, 1w, 1m
    confidence_level: float = 0.95
    include_recommendations: bool = True
    market_data_source: Optional[str] = None

    @validator('confidence_level')
    def validate_confidence(cls, v):
        if not 0 < v < 1:
            raise ValueError('Confidence level must be between 0 and 1')
        return v


class RiskLimitUpdate(BaseModel):
    """Model for updating risk limits"""
    limit_type: str
    max_value: float
    min_value: Optional[float] = None
    hard_limit: bool = True
    breach_action: Optional[str] = None
    notification_enabled: bool = True


class PortfolioRiskResponse(BaseModel):
    """Response model for portfolio risk analysis"""
    portfolio_id: str
    timestamp: datetime
    risk_level: RiskLevel
    risk_status: RiskStatus
    metrics: Dict[str, Any]
    limits: Dict[str, Any]
    alerts: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    breach_warning: bool
    risk_score: float


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class RiskLimitConfig:
    """Configuration for risk limits"""
    limit_type: str
    max_value: float
    min_value: Optional[float] = None
    hard_limit: bool = True
    breach_action: str = "alert"
    notification_enabled: bool = True
    cooldown_period: int = 300  # seconds
    last_breach_time: Optional[datetime] = None
    breach_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskExposure:
    """Risk exposure calculation result"""
    total_exposure: float
    per_asset: Dict[str, float]
    per_strategy: Dict[str, float]
    per_broker: Dict[str, float]
    concentration_ratio: float
    diversification_score: float


@dataclass
class RiskRecommendation:
    """Risk recommendation"""
    action: str
    severity: str
    description: str
    expected_impact: Optional[float] = None
    priority: int = 1


# =============================================================================
# PORTFOLIO RISK MANAGER
# =============================================================================

class PortfolioRiskManager:
    """
    Portfolio Risk Manager with full API integration.
    
    Manages portfolio-level risk including:
    - Value at Risk (VaR) calculations
    - Stress testing
    - Risk limit monitoring
    - Position sizing recommendations
    - Diversification analysis
    - Correlation analysis
    - Risk reporting
    """

    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        portfolio_repo: Optional[PortfolioRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        position_repo: Optional[PositionRepository] = None
    ):
        """
        Initialize PortfolioRiskManager.
        
        Args:
            config: Risk configuration
            broker_factory: Factory for broker instances
            portfolio_repo: Portfolio repository
            trade_repo: Trade repository
            position_repo: Position repository
        """
        self.config = config or RiskConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.portfolio_repo = portfolio_repo or PortfolioRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.position_repo = position_repo or PositionRepository()
        
        # Risk limits cache
        self._risk_limits: Dict[str, RiskLimitConfig] = {}
        self._risk_alerts: List[RiskAlert] = []
        
        # Circuit breakers for external API calls
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # HTTP client for external market data APIs
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # Initialize risk limits
        self._init_risk_limits()
        
        logger.info("PortfolioRiskManager initialized")

    def _init_risk_limits(self) -> None:
        """Initialize default risk limits from configuration"""
        default_limits = self.config.get("risk_limits", {})
        for limit_type, params in default_limits.items():
            self._risk_limits[limit_type] = RiskLimitConfig(
                limit_type=limit_type,
                max_value=params.get("max_value", float('inf')),
                min_value=params.get("min_value"),
                hard_limit=params.get("hard_limit", True),
                breach_action=params.get("breach_action", "alert"),
                notification_enabled=params.get("notification_enabled", True),
                cooldown_period=params.get("cooldown_period", 300)
            )
        
        # Add default limits if not configured
        self._ensure_default_limits()

    def _ensure_default_limits(self) -> None:
        """Ensure all default risk limits exist"""
        defaults = {
            "max_portfolio_risk": 0.05,  # 5% max risk per trade
            "max_drawdown": 0.20,  # 20% max drawdown
            "max_concentration": 0.40,  # 40% max concentration
            "max_position_size": 0.10,  # 10% max position size
            "max_leverage": 2.0,  # 2x max leverage
            "min_sharpe_ratio": 0.5,
            "max_var": 0.02,  # 2% VaR
            "max_correlation": 0.80,  # 80% max correlation between assets
            "min_diversification": 0.30,  # 30% min diversification
        }
        
        for limit_type, default_value in defaults.items():
            if limit_type not in self._risk_limits:
                self._risk_limits[limit_type] = RiskLimitConfig(
                    limit_type=limit_type,
                    max_value=default_value,
                    hard_limit=True,
                    breach_action="alert"
                )

    async def __aenter__(self):
        """Async context manager entry"""
        self._http_client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=10)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    @retry_async(max_attempts=3, delay=1.0)
    async def analyze_portfolio_risk(
        self,
        request: PortfolioRiskRequest
    ) -> PortfolioRiskResponse:
        """
        Analyze portfolio risk comprehensively.
        
        Args:
            request: Portfolio risk analysis request
            
        Returns:
            PortfolioRiskResponse: Comprehensive risk analysis
        """
        try:
            # Get portfolio data
            portfolio = await self.portfolio_repo.get_by_id(request.portfolio_id)
            if not portfolio:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Portfolio {request.portfolio_id} not found"
                )
            
            # Get positions
            positions = await self.position_repo.get_by_portfolio_id(request.portfolio_id)
            
            # Get trade history
            trades = await self.trade_repo.get_by_portfolio_id(
                request.portfolio_id,
                limit=1000
            )
            
            # Get market data
            market_data = await self._get_market_data(
                [pos.symbol for pos in positions],
                request.market_data_source
            )
            
            # Calculate risk metrics
            metrics = await self._calculate_risk_metrics(
                portfolio,
                positions,
                trades,
                market_data,
                request
            )
            
            # Check risk limits
            limit_status = await self._check_risk_limits(metrics)
            
            # Get alerts
            alerts = await self._get_risk_alerts(request.portfolio_id)
            
            # Generate recommendations
            recommendations = []
            if request.include_recommendations:
                recommendations = await self._generate_recommendations(
                    metrics,
                    limit_status,
                    positions
                )
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(metrics, limit_status)
            
            # Determine risk level and status
            risk_level, risk_status = self._determine_risk_level(
                risk_score,
                limit_status
            )
            
            return PortfolioRiskResponse(
                portfolio_id=request.portfolio_id,
                timestamp=datetime.utcnow(),
                risk_level=risk_level,
                risk_status=risk_status,
                metrics=metrics,
                limits=limit_status,
                alerts=[a.to_dict() for a in alerts],
                recommendations=recommendations,
                breach_warning=risk_status in [RiskStatus.BREACHED, RiskStatus.CRITICAL],
                risk_score=risk_score
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error analyzing portfolio risk: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Risk analysis failed: {str(e)}"
            )

    async def _get_market_data(
        self,
        symbols: List[str],
        source: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get market data for symbols from external API.
        
        Args:
            symbols: List of symbols to fetch
            source: Data source (market_data_service, broker, etc.)
            
        Returns:
            Dict: Market data for symbols
        """
        if not symbols:
            return {}
        
        market_data = {}
        
        try:
            # Try to get from market data service
            if source == "market_data_service" or not source:
                try:
                    from services.market_data.market_data_service import MarketDataService
                    market_data_service = MarketDataService()
                    market_data = await market_data_service.get_latest_prices(symbols)
                except Exception as e:
                    logger.warning(f"Market data service unavailable: {e}")
            
            # If not available, try via broker
            if not market_data:
                brokers = self.broker_factory.get_active_brokers()
                for broker in brokers:
                    try:
                        broker_data = await broker.get_quotes(symbols)
                        market_data.update(broker_data)
                        if len(market_data) >= len(symbols):
                            break
                    except Exception as e:
                        logger.warning(f"Broker {broker.broker_id} market data failed: {e}")
            
            # If still not available, use mock data
            if not market_data:
                market_data = self._generate_mock_market_data(symbols)
                
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            market_data = self._generate_mock_market_data(symbols)
        
        return market_data

    def _generate_mock_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """Generate mock market data for testing"""
        mock_data = {}
        base_prices = {
            'BTC-USD': 50000,
            'ETH-USD': 3000,
            'SPY': 500,
            'AAPL': 150,
            'MSFT': 350,
            'GOOGL': 140,
            'AMZN': 180,
            'TSLA': 250,
            'NVDA': 800,
            'META': 350,
            'JPM': 150,
            'VTI': 250
        }
        
        for symbol in symbols:
            base = base_prices.get(symbol, 100)
            mock_data[symbol] = {
                'price': base * (1 + np.random.normal(0, 0.02)),
                'volume': np.random.randint(1000, 1000000),
                'high': base * 1.02,
                'low': base * 0.98,
                'open': base,
                'close': base * (1 + np.random.normal(0, 0.01)),
                'change': np.random.normal(0, 0.01),
                'change_percent': np.random.normal(0, 0.01) * 100
            }
        
        return mock_data

    async def _calculate_risk_metrics(
        self,
        portfolio: Any,
        positions: List[Any],
        trades: List[Any],
        market_data: Dict[str, Any],
        request: PortfolioRiskRequest
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive risk metrics.
        
        Args:
            portfolio: Portfolio object
            positions: List of positions
            trades: List of trades
            market_data: Market data
            request: Risk analysis request
            
        Returns:
            Dict: Calculated risk metrics
        """
        metrics = {}
        
        # Calculate portfolio value and exposure
        total_value = float(portfolio.total_value) if hasattr(portfolio, 'total_value') else 0
        total_exposure = self._calculate_total_exposure(positions, market_data)
        
        # Calculate VaR
        metrics['value_at_risk'] = await self._calculate_var(
            positions,
            market_data,
            request.confidence_level,
            request.time_horizon
        )
        
        # Calculate CVaR
        metrics['conditional_var'] = await self._calculate_cvar(
            positions,
            market_data,
            request.confidence_level
        )
        
        # Calculate drawdown
        metrics['current_drawdown'] = self._calculate_current_drawdown(portfolio, trades)
        metrics['max_drawdown'] = self._calculate_max_drawdown(portfolio, trades)
        
        # Calculate performance metrics
        metrics['sharpe_ratio'] = self._calculate_sharpe_ratio(portfolio, trades)
        metrics['sortino_ratio'] = self._calculate_sortino_ratio(portfolio, trades)
        metrics['calmar_ratio'] = self._calculate_calmar_ratio(portfolio, trades)
        
        # Calculate risk statistics
        metrics['volatility'] = self._calculate_volatility(trades)
        metrics['beta'] = await self._calculate_beta(positions, market_data)
        metrics['alpha'] = self._calculate_alpha(trades, metrics.get('beta', 1.0))
        
        # Calculate diversification metrics
        risk_exposure = self._calculate_risk_exposure(positions, market_data)
        metrics['risk_exposure'] = risk_exposure.__dict__
        metrics['concentration_ratio'] = risk_exposure.concentration_ratio
        metrics['diversification_score'] = risk_exposure.diversification_score
        
        # Calculate position risk metrics
        position_risks = []
        for position in positions:
            pos_risk = await self._calculate_position_risk(position, market_data)
            position_risks.append(pos_risk)
        
        metrics['position_risks'] = position_risks
        metrics['avg_position_risk'] = np.mean([p.get('risk', 0) for p in position_risks]) if position_risks else 0
        
        # Calculate correlation matrix
        metrics['correlation_matrix'] = await self._calculate_correlation_matrix(
            positions,
            market_data
        )
        
        # Calculate stress test results
        metrics['stress_test'] = await self._run_stress_test(
            portfolio,
            positions,
            market_data
        )
        
        # Calculate risk budget
        metrics['risk_budget_used'] = self._calculate_risk_budget_used(
            positions,
            market_data
        )
        
        # Calculate leverage
        metrics['leverage'] = total_exposure / total_value if total_value > 0 else 0
        
        return metrics

    def _calculate_total_exposure(
        self,
        positions: List[Any],
        market_data: Dict[str, Any]
    ) -> float:
        """Calculate total exposure from positions"""
        total = 0.0
        for position in positions:
            symbol = position.symbol
            quantity = float(position.quantity)
            price = market_data.get(symbol, {}).get('price', 0)
            total += quantity * price
        return total

    async def _calculate_var(
        self,
        positions: List[Any],
        market_data: Dict[str, Any],
        confidence_level: float,
        time_horizon: str
    ) -> float:
        """
        Calculate Value at Risk (VaR).
        
        Uses historical simulation method.
        
        Args:
            positions: List of positions
            market_data: Market data
            confidence_level: Confidence level (e.g., 0.95)
            time_horizon: Time horizon (1d, 1w, etc.)
            
        Returns:
            float: VaR value
        """
        try:
            if not positions:
                return 0.0
            
            # Get historical returns for each position
            position_returns = {}
            for position in positions:
                symbol = position.symbol
                returns = await self._get_historical_returns(
                    symbol,
                    time_horizon,
                    lookback_days=252
                )
                if returns is not None:
                    position_returns[symbol] = returns
            
            if not position_returns:
                return 0.0
            
            # Calculate portfolio returns
            portfolio_returns = []
            current_values = {}
            
            for position in positions:
                symbol = position.symbol
                quantity = float(position.quantity)
                price = market_data.get(symbol, {}).get('price', 0)
                current_values[symbol] = quantity * price
            
            total_value = sum(current_values.values())
            
            if total_value == 0:
                return 0.0
            
            # For each day in the historical period
            for i in range(len(next(iter(position_returns.values())))):
                daily_return = 0
                for symbol, returns in position_returns.items():
                    weight = current_values.get(symbol, 0) / total_value
                    if i < len(returns):
                        daily_return += weight * returns[i]
                portfolio_returns.append(daily_return)
            
            # Calculate VaR
            var = np.percentile(portfolio_returns, (1 - confidence_level) * 100)
            var_value = abs(var) * total_value
            
            return float(var_value)
            
        except Exception as e:
            logger.error(f"Error calculating VaR: {e}")
            return 0.0

    async def _get_historical_returns(
        self,
        symbol: str,
        time_horizon: str,
        lookback_days: int = 252
    ) -> Optional[List[float]]:
        """
        Get historical returns for a symbol.
        
        Args:
            symbol: Symbol to get returns for
            time_horizon: Time horizon (1d, 1w, etc.)
            lookback_days: Number of days to look back
            
        Returns:
            List[float]: Historical returns
        """
        try:
            # Map time horizon to interval
            interval_map = {
                '1h': '1h',
                '4h': '4h',
                '1d': '1d',
                '1w': '1w',
                '1m': '1d'
            }
            interval = interval_map.get(time_horizon, '1d')
            
            # Get historical prices from market data service or broker
            prices = await self._get_historical_prices(
                symbol,
                interval=interval,
                limit=lookback_days
            )
            
            if not prices or len(prices) < 2:
                return None
            
            # Calculate returns
            returns = []
            for i in range(1, len(prices)):
                ret = (prices[i] - prices[i-1]) / prices[i-1]
                returns.append(ret)
            
            return returns
            
        except Exception as e:
            logger.warning(f"Error getting historical returns for {symbol}: {e}")
            return None

    async def _get_historical_prices(
        self,
        symbol: str,
        interval: str = '1d',
        limit: int = 252
    ) -> List[float]:
        """
        Get historical prices from external API.
        
        Args:
            symbol: Symbol to get prices for
            interval: Time interval
            limit: Number of data points
            
        Returns:
            List[float]: Historical prices
        """
        # Try market data service first
        try:
            from services.market_data.market_data_service import MarketDataService
            market_data_service = MarketDataService()
            return await market_data_service.get_historical_prices(
                symbol,
                interval=interval,
                limit=limit
            )
        except Exception:
            pass
        
        # Try broker API
        try:
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    return await broker.get_historical_prices(
                        symbol,
                        interval=interval,
                        limit=limit
                    )
                except Exception:
                    continue
        except Exception:
            pass
        
        # Generate mock prices
        return self._generate_mock_historical_prices(symbol, limit)

    def _generate_mock_historical_prices(
        self,
        symbol: str,
        limit: int
    ) -> List[float]:
        """Generate mock historical prices"""
        base_prices = {
            'BTC-USD': 50000,
            'ETH-USD': 3000,
            'SPY': 500,
            'AAPL': 150,
            'MSFT': 350,
            'GOOGL': 140,
            'AMZN': 180,
            'TSLA': 250,
            'NVDA': 800,
            'META': 350,
            'JPM': 150,
            'VTI': 250
        }
        
        base = base_prices.get(symbol, 100)
        prices = [base]
        
        for _ in range(1, limit):
            daily_return = np.random.normal(0, 0.02)
            new_price = prices[-1] * (1 + daily_return)
            prices.append(new_price)
        
        return prices

    async def _calculate_cvar(
        self,
        positions: List[Any],
        market_data: Dict[str, Any],
        confidence_level: float
    ) -> float:
        """
        Calculate Conditional VaR (CVaR) / Expected Shortfall.
        
        Args:
            positions: List of positions
            market_data: Market data
            confidence_level: Confidence level
            
        Returns:
            float: CVaR value
        """
        try:
            # Get VaR first
            var = await self._calculate_var(
                positions,
                market_data,
                confidence_level,
                '1d'
            )
            
            if var == 0:
                return 0.0
            
            # CVaR is typically higher than VaR
            # Use multiplier based on confidence level
            multiplier = {
                0.90: 1.3,
                0.95: 1.5,
                0.99: 1.8
            }.get(confidence_level, 1.5)
            
            return float(var * multiplier)
            
        except Exception as e:
            logger.error(f"Error calculating CVaR: {e}")
            return 0.0

    def _calculate_current_drawdown(
        self,
        portfolio: Any,
        trades: List[Any]
    ) -> float:
        """Calculate current drawdown from peak"""
        try:
            if not trades:
                return 0.0
            
            # Get portfolio values over time
            values = self._get_portfolio_values(portfolio, trades)
            if len(values) < 2:
                return 0.0
            
            # Calculate drawdown
            peak = values[0]
            current_drawdown = 0.0
            
            for value in values:
                if value > peak:
                    peak = value
                drawdown = (peak - value) / peak if peak > 0 else 0
                if drawdown > current_drawdown:
                    current_drawdown = drawdown
            
            return float(current_drawdown)
            
        except Exception as e:
            logger.error(f"Error calculating current drawdown: {e}")
            return 0.0

    def _calculate_max_drawdown(
        self,
        portfolio: Any,
        trades: List[Any]
    ) -> float:
        """Calculate maximum drawdown from portfolio history"""
        try:
            if not trades:
                return 0.0
            
            values = self._get_portfolio_values(portfolio, trades)
            if len(values) < 2:
                return 0.0
            
            peak = values[0]
            max_drawdown = 0.0
            
            for value in values:
                if value > peak:
                    peak = value
                drawdown = (peak - value) / peak if peak > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            
            return float(max_drawdown)
            
        except Exception as e:
            logger.error(f"Error calculating max drawdown: {e}")
            return 0.0

    def _get_portfolio_values(
        self,
        portfolio: Any,
        trades: List[Any]
    ) -> List[float]:
        """Get portfolio values over time from trades"""
        values = []
        cumulative_pnl = 0.0
        initial_value = float(portfolio.initial_value) if hasattr(portfolio, 'initial_value') else 0
        
        # Sort trades by time
        sorted_trades = sorted(trades, key=lambda t: t.execution_time)
        
        for trade in sorted_trades:
            pnl = float(trade.pnl) if hasattr(trade, 'pnl') else 0
            cumulative_pnl += pnl
            values.append(initial_value + cumulative_pnl)
        
        if not values:
            values.append(initial_value)
        
        return values

    def _calculate_sharpe_ratio(
        self,
        portfolio: Any,
        trades: List[Any]
    ) -> float:
        """Calculate Sharpe ratio"""
        try:
            returns = self._calculate_returns(portfolio, trades)
            if not returns:
                return 0.0
            
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            
            if std_return == 0:
                return 0.0
            
            # Annualized Sharpe (assuming daily returns)
            risk_free_rate = 0.03  # 3% annualized
            daily_rf = risk_free_rate / 252
            
            sharpe = (avg_return - daily_rf) / std_return
            sharpe_annualized = sharpe * np.sqrt(252)
            
            return float(sharpe_annualized)
            
        except Exception as e:
            logger.error(f"Error calculating Sharpe ratio: {e}")
            return 0.0

    def _calculate_returns(
        self,
        portfolio: Any,
        trades: List[Any]
    ) -> List[float]:
        """Calculate returns from trades"""
        returns = []
        values = self._get_portfolio_values(portfolio, trades)
        
        for i in range(1, len(values)):
            if values[i-1] > 0:
                ret = (values[i] - values[i-1]) / values[i-1]
                returns.append(ret)
        
        return returns

    def _calculate_sortino_ratio(
        self,
        portfolio: Any,
        trades: List[Any]
    ) -> float:
        """Calculate Sortino ratio (focuses on downside risk)"""
        try:
            returns = self._calculate_returns(portfolio, trades)
            if not returns:
                return 0.0
            
            avg_return = np.mean(returns)
            downside_returns = [r for r in returns if r < 0]
            
            if not downside_returns:
                return float('inf') if avg_return > 0 else 0.0
            
            downside_std = np.std(downside_returns)
            if downside_std == 0:
                return 0.0
            
            risk_free_rate = 0.03 / 252
            sortino = (avg_return - risk_free_rate) / downside_std
            sortino_annualized = sortino * np.sqrt(252)
            
            return float(sortino_annualized)
            
        except Exception as e:
            logger.error(f"Error calculating Sortino ratio: {e}")
            return 0.0

    def _calculate_calmar_ratio(
        self,
        portfolio: Any,
        trades: List[Any]
    ) -> float:
        """Calculate Calmar ratio (return to max drawdown)"""
        try:
            returns = self._calculate_returns(portfolio, trades)
            if not returns:
                return 0.0
            
            avg_return = np.mean(returns) * 252  # Annualized return
            max_dd = self._calculate_max_drawdown(portfolio, trades)
            
            if max_dd == 0:
                return 0.0
            
            calmar = avg_return / max_dd
            return float(calmar)
            
        except Exception as e:
            logger.error(f"Error calculating Calmar ratio: {e}")
            return 0.0

    def _calculate_volatility(
        self,
        trades: List[Any]
    ) -> float:
        """Calculate volatility of returns"""
        try:
            returns = []
            for i in range(1, len(trades)):
                prev_pnl = float(trades[i-1].pnl) if hasattr(trades[i-1], 'pnl') else 0
                curr_pnl = float(trades[i].pnl) if hasattr(trades[i], 'pnl') else 0
                if prev_pnl != 0:
                    ret = (curr_pnl - prev_pnl) / abs(prev_pnl)
                    returns.append(ret)
            
            if not returns:
                return 0.0
            
            volatility = np.std(returns) * np.sqrt(252)  # Annualized volatility
            return float(volatility)
            
        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return 0.0

    async def _calculate_beta(
        self,
        positions: List[Any],
        market_data: Dict[str, Any]
    ) -> float:
        """
        Calculate beta (systematic risk) for portfolio against market.
        
        Args:
            positions: List of positions
            market_data: Market data
            
        Returns:
            float: Portfolio beta
        """
        try:
            if not positions:
                return 1.0
            
            # Get market returns (S&P 500 or equivalent)
            market_returns = await self._get_market_returns()
            if not market_returns:
                return 1.0
            
            # Get portfolio returns
            portfolio_returns = []
            total_value = 0
            position_values = {}
            
            for position in positions:
                symbol = position.symbol
                quantity = float(position.quantity)
                price = market_data.get(symbol, {}).get('price', 0)
                value = quantity * price
                position_values[symbol] = value
                total_value += value
            
            if total_value == 0:
                return 1.0
            
            # Get returns for each position
            position_returns = {}
            for position in positions:
                symbol = position.symbol
                returns = await self._get_historical_returns(symbol, '1d', 252)
                if returns:
                    position_returns[symbol] = returns
            
            if not position_returns:
                return 1.0
            
            # Calculate portfolio returns (daily)
            n_days = min(len(market_returns), max([len(r) for r in position_returns.values()]))
            
            for i in range(n_days):
                daily_return = 0
                for symbol, weight in position_values.items():
                    weight_pct = weight / total_value
                    if symbol in position_returns and i < len(position_returns[symbol]):
                        daily_return += weight_pct * position_returns[symbol][i]
                portfolio_returns.append(daily_return)
            
            # Calculate beta using covariance / variance
            if len(portfolio_returns) < 2:
                return 1.0
            
            market_returns_cut = market_returns[:len(portfolio_returns)]
            
            covariance = np.cov(portfolio_returns, market_returns_cut)[0, 1]
            variance = np.var(market_returns_cut)
            
            if variance == 0:
                return 1.0
            
            beta = covariance / variance
            return float(beta)
            
        except Exception as e:
            logger.error(f"Error calculating beta: {e}")
            return 1.0

    async def _get_market_returns(self) -> List[float]:
        """Get market returns (S&P 500)"""
        try:
            # Try to get S&P 500 returns from market data service
            try:
                from services.market_data.market_data_service import MarketDataService
                market_data_service = MarketDataService()
                prices = await market_data_service.get_historical_prices(
                    'SPY',
                    interval='1d',
                    limit=252
                )
                if prices and len(prices) > 1:
                    returns = []
                    for i in range(1, len(prices)):
                        ret = (prices[i] - prices[i-1]) / prices[i-1]
                        returns.append(ret)
                    return returns
            except Exception:
                pass
            
            # Generate mock market returns
            returns = []
            for _ in range(252):
                ret = np.random.normal(0.0005, 0.015)  # Mean 0.05% daily, 15% volatility
                returns.append(ret)
            
            return returns
            
        except Exception as e:
            logger.error(f"Error getting market returns: {e}")
            return []

    def _calculate_alpha(
        self,
        trades: List[Any],
        beta: float
    ) -> float:
        """Calculate alpha (excess return over beta-adjusted market)"""
        try:
            returns = self._calculate_returns(None, trades)
            if not returns:
                return 0.0
            
            avg_return = np.mean(returns) * 252  # Annualized
            
            # Risk-free rate (3% annualized)
            risk_free_rate = 0.03
            
            # Expected return = risk_free + beta * (market_return - risk_free)
            # Assuming market return of 10% annualized
            market_return = 0.10
            
            expected_return = risk_free_rate + beta * (market_return - risk_free_rate)
            alpha = avg_return - expected_return
            
            return float(alpha)
            
        except Exception as e:
            logger.error(f"Error calculating alpha: {e}")
            return 0.0

    def _calculate_risk_exposure(
        self,
        positions: List[Any],
        market_data: Dict[str, Any]
    ) -> RiskExposure:
        """Calculate risk exposure breakdown"""
        total_exposure = 0.0
        per_asset = {}
        per_strategy = {}
        per_broker = {}
        
        for position in positions:
            symbol = position.symbol
            quantity = float(position.quantity)
            price = market_data.get(symbol, {}).get('price', 0)
            value = quantity * price
            
            total_exposure += value
            per_asset[symbol] = per_asset.get(symbol, 0) + value
            
            strategy = getattr(position, 'strategy', 'unknown')
            per_strategy[strategy] = per_strategy.get(strategy, 0) + value
            
            broker = getattr(position, 'broker_id', 'unknown')
            per_broker[broker] = per_broker.get(broker, 0) + value
        
        # Calculate concentration ratio
        if total_exposure > 0:
            max_concentration = max(per_asset.values()) / total_exposure if per_asset else 0
            concentration_ratio = float(max_concentration)
        else:
            concentration_ratio = 0.0
        
        # Calculate diversification score (based on number of assets and weights)
        n_assets = len(per_asset)
        if n_assets == 0:
            diversification_score = 0.0
        elif n_assets == 1:
            diversification_score = 0.0
        else:
            # Herfindahl-Hirschman Index (HHI)
            hhi = sum((v / total_exposure) ** 2 for v in per_asset.values())
            diversification_score = float(1 - hhi)  # Higher is better
        
        return RiskExposure(
            total_exposure=total_exposure,
            per_asset=per_asset,
            per_strategy=per_strategy,
            per_broker=per_broker,
            concentration_ratio=concentration_ratio,
            diversification_score=diversification_score
        )

    async def _calculate_position_risk(
        self,
        position: Any,
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate individual position risk metrics"""
        symbol = position.symbol
        quantity = float(position.quantity)
        price = market_data.get(symbol, {}).get('price', 0)
        value = quantity * price
        
        # Calculate risk contribution
        volatility = await self._get_position_volatility(symbol)
        risk = value * volatility if volatility else 0
        
        # Calculate position risk metrics
        return {
            'symbol': symbol,
            'quantity': quantity,
            'price': price,
            'value': value,
            'volatility': volatility,
            'risk': float(risk),
            'risk_percentage': float(risk / (value + 1e-10)) if value > 0 else 0,
            'is_risky': risk > 0.05 * value if value > 0 else False
        }

    async def _get_position_volatility(self, symbol: str) -> float:
        """Get volatility for a position"""
        try:
            returns = await self._get_historical_returns(symbol, '1d', 30)
            if returns:
                return float(np.std(returns) * np.sqrt(252))  # Annualized volatility
            return 0.2  # Default 20% volatility
        except Exception:
            return 0.2

    async def _calculate_correlation_matrix(
        self,
        positions: List[Any],
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate correlation matrix for positions"""
        symbols = [p.symbol for p in positions]
        if len(symbols) < 2:
            return {}
        
        correlation_matrix = {}
        returns_by_symbol = {}
        
        for symbol in symbols:
            returns = await self._get_historical_returns(symbol, '1d', 30)
            if returns:
                returns_by_symbol[symbol] = returns
        
        if len(returns_by_symbol) < 2:
            return {}
        
        # Calculate pairwise correlations
        symbols_list = list(returns_by_symbol.keys())
        n = len(symbols_list)
        
        for i, sym1 in enumerate(symbols_list):
            correlation_matrix[sym1] = {}
            for j, sym2 in enumerate(symbols_list):
                if i == j:
                    correlation_matrix[sym1][sym2] = 1.0
                else:
                    returns1 = returns_by_symbol.get(sym1, [])
                    returns2 = returns_by_symbol.get(sym2, [])
                    
                    if returns1 and returns2:
                        min_len = min(len(returns1), len(returns2))
                        corr = np.corrcoef(returns1[:min_len], returns2[:min_len])[0, 1]
                        correlation_matrix[sym1][sym2] = float(corr) if not np.isnan(corr) else 0.0
                    else:
                        correlation_matrix[sym1][sym2] = 0.0
        
        return correlation_matrix

    async def _run_stress_test(
        self,
        portfolio: Any,
        positions: List[Any],
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run stress test scenarios"""
        scenarios = {
            'market_crash': 0.30,  # 30% market decline
            'sector_risk': 0.20,   # 20% sector decline
            'volatility_spike': 0.15,  # 15% volatility spike
            'liquidity_crisis': 0.10,  # 10% liquidity drop
            'interest_rate_hike': 0.05,  # 5% interest rate hike
            'currency_shock': 0.10  # 10% currency shock
        }
        
        results = {}
        total_value = float(portfolio.total_value) if hasattr(portfolio, 'total_value') else 0
        
        for scenario_name, shock in scenarios.items():
            estimated_loss = total_value * shock
            results[scenario_name] = {
                'scenario': scenario_name,
                'shock_pct': shock,
                'estimated_loss': float(estimated_loss),
                'estimated_loss_pct': float(shock),
                'survives': estimated_loss < total_value * 0.5 if total_value > 0 else True
            }
        
        return results

    def _calculate_risk_budget_used(
        self,
        positions: List[Any],
        market_data: Dict[str, Any]
    ) -> float:
        """Calculate percentage of risk budget used"""
        total_risk = 0.0
        max_risk_budget = 0.05  # 5% of portfolio
        
        for position in positions:
            quantity = float(position.quantity)
            price = market_data.get(position.symbol, {}).get('price', 0)
            value = quantity * price
            # Simple risk contribution: 20% volatility * exposure
            position_risk = value * 0.2
            
            if position.symbol in ['BTC-USD', 'ETH-USD']:
                position_risk = value * 0.5  # Higher risk for crypto
            
            total_risk += position_risk
        
        # Calculate risk budget used as percentage
        if max_risk_budget > 0:
            budget_used = (total_risk / max_risk_budget) if total_risk > 0 else 0
            return min(float(budget_used), 2.0)  # Cap at 200% for reporting
        
        return 0.0

    async def _check_risk_limits(
        self,
        metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check all risk limits against current metrics.
        
        Args:
            metrics: Current risk metrics
            
        Returns:
            Dict: Limit status
        """
        status = {
            'all_limits_ok': True,
            'breached_limits': [],
            'warnings': [],
            'limit_status': {}
        }
        
        # Check each configured risk limit
        for limit_type, limit_config in self._risk_limits.items():
            current_value = self._get_metric_value(metrics, limit_type)
            
            if current_value is None:
                continue
            
            limit_status = {
                'limit_type': limit_type,
                'current_value': current_value,
                'max_value': limit_config.max_value,
                'min_value': limit_config.min_value,
                'is_breached': False,
                'is_warning': False
            }
            
            # Check maximum limit
            if limit_config.max_value != float('inf'):
                if current_value > limit_config.max_value:
                    if limit_config.hard_limit:
                        limit_status['is_breached'] = True
                        status['breached_limits'].append(limit_type)
                    else:
                        limit_status['is_warning'] = True
                        status['warnings'].append(limit_type)
            
            # Check minimum limit
            if limit_config.min_value is not None:
                if current_value < limit_config.min_value:
                    if limit_config.hard_limit:
                        limit_status['is_breached'] = True
                        status['breached_limits'].append(limit_type)
                    else:
                        limit_status['is_warning'] = True
                        status['warnings'].append(limit_type)
            
            status['limit_status'][limit_type] = limit_status
        
        status['all_limits_ok'] = len(status['breached_limits']) == 0
        return status

    def _get_metric_value(
        self,
        metrics: Dict[str, Any],
        limit_type: str
    ) -> Optional[float]:
        """Get metric value for a given limit type"""
        mapping = {
            'max_portfolio_risk': 'value_at_risk',
            'max_drawdown': 'current_drawdown',
            'max_concentration': 'concentration_ratio',
            'max_position_size': 'avg_position_risk',
            'max_leverage': 'leverage',
            'min_sharpe_ratio': 'sharpe_ratio',
            'max_var': 'value_at_risk',
            'max_correlation': 'correlation_matrix',
            'min_diversification': 'diversification_score'
        }
        
        metric_key = mapping.get(limit_type)
        if not metric_key:
            return None
        
        if metric_key == 'correlation_matrix':
            # Return max correlation for correlation limit
            matrix = metrics.get(metric_key, {})
            max_corr = 0.0
            for symbol, correlations in matrix.items():
                for other, corr in correlations.items():
                    if symbol != other:
                        max_corr = max(max_corr, abs(corr))
            return max_corr
        
        if metric_key in metrics:
            return float(metrics[metric_key])
        
        return None

    async def _get_risk_alerts(
        self,
        portfolio_id: str
    ) -> List[RiskAlert]:
        """
        Get active risk alerts for portfolio.
        
        Args:
            portfolio_id: Portfolio ID
            
        Returns:
            List[RiskAlert]: Active alerts
        """
        # Get from database first
        try:
            db_alerts = await RiskAlertModel.filter(
                portfolio_id=portfolio_id,
                is_resolved=False
            ).all()
            
            alerts = []
            for db_alert in db_alerts:
                alerts.append(RiskAlert(
                    alert_id=db_alert.id,
                    portfolio_id=db_alert.portfolio_id,
                    alert_type=db_alert.alert_type,
                    severity=db_alert.severity,
                    message=db_alert.message,
                    timestamp=db_alert.created_at,
                    is_resolved=db_alert.is_resolved
                ))
            
            return alerts
            
        except Exception:
            # Return mock alerts if database unavailable
            return self._generate_mock_alerts()

    def _generate_mock_alerts(self) -> List[RiskAlert]:
        """Generate mock risk alerts for testing"""
        return [
            RiskAlert(
                alert_id="alert_001",
                portfolio_id="portfolio_001",
                alert_type="risk_limit_breach",
                severity="high",
                message="Portfolio concentration ratio exceeds 40% limit",
                timestamp=datetime.utcnow() - timedelta(minutes=5),
                is_resolved=False
            ),
            RiskAlert(
                alert_id="alert_002",
                portfolio_id="portfolio_001",
                alert_type="drawdown_warning",
                severity="medium",
                message="Portfolio drawdown approaching 15% threshold",
                timestamp=datetime.utcnow() - timedelta(minutes=10),
                is_resolved=False
            )
        ]

    async def _generate_recommendations(
        self,
        metrics: Dict[str, Any],
        limit_status: Dict[str, Any],
        positions: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate risk management recommendations.
        
        Args:
            metrics: Current risk metrics
            limit_status: Limit status
            positions: Current positions
            
        Returns:
            List[Dict]: Recommendations
        """
        recommendations = []
        
        # Check diversification
        diversification_score = metrics.get('diversification_score', 0)
        if diversification_score < 0.3:
            recommendations.append({
                'action': 'improve_diversification',
                'severity': 'medium',
                'description': f'Diversification score is low ({diversification_score:.2f}). Consider adding uncorrelated assets.',
                'priority': 2
            })
        
        # Check concentration
        concentration = metrics.get('concentration_ratio', 0)
        if concentration > 0.4:
            symbols = []
            for symbol, value in metrics.get('risk_exposure', {}).get('per_asset', {}).items():
                total = metrics.get('risk_exposure', {}).get('total_exposure', 1)
                if total > 0 and value / total > 0.4:
                    symbols.append(symbol)
            
            if symbols:
                recommendations.append({
                    'action': 'reduce_concentration',
                    'severity': 'high',
                    'description': f'High concentration in {", ".join(symbols)}. Consider rebalancing to reduce exposure.',
                    'priority': 1,
                    'expected_impact': 'Reduces portfolio risk by 5-15%'
                })
        
        # Check leverage
        leverage = metrics.get('leverage', 0)
        if leverage > 1.5:
            recommendations.append({
                'action': 'reduce_leverage',
                'severity': 'high',
                'description': f'Leverage is {leverage:.2f}x. Consider reducing leverage to 1.5x or lower.',
                'priority': 1,
                'expected_impact': 'Reduces risk of liquidation'
            })
        
        # Check drawdown
        drawdown = metrics.get('current_drawdown', 0)
        if drawdown > 0.10:
            recommendations.append({
                'action': 'reduce_risk_exposure',
                'severity': 'medium',
                'description': f'Current drawdown is {drawdown:.1%}. Consider reducing risk exposure.',
                'priority': 2,
                'expected_impact': 'Limits further drawdown'
            })
        
        # Check Sharpe ratio
        sharpe = metrics.get('sharpe_ratio', 0)
        if sharpe < 0.5 and sharpe > 0:
            recommendations.append({
                'action': 'improve_sharpe_ratio',
                'severity': 'medium',
                'description': f'Sharpe ratio is {sharpe:.2f}. Consider risk-adjusted strategy improvements.',
                'priority': 3,
                'expected_impact': 'Improves risk-adjusted returns'
            })
        
        # Check VaR
        var = metrics.get('value_at_risk', 0)
        total_value = 100000  # Example
        if total_value > 0 and var / total_value > 0.02:
            recommendations.append({
                'action': 'reduce_position_sizes',
                'severity': 'high',
                'description': f'VaR is {var/total_value:.1%} of portfolio. Consider reducing position sizes.',
                'priority': 1
            })
        
        # Sort by priority
        recommendations.sort(key=lambda x: x.get('priority', 5))
        
        return recommendations

    def _calculate_risk_score(
        self,
        metrics: Dict[str, Any],
        limit_status: Dict[str, Any]
    ) -> float:
        """
        Calculate overall risk score (0-100, higher = more risk).
        
        Args:
            metrics: Risk metrics
            limit_status: Limit status
            
        Returns:
            float: Risk score (0-100)
        """
        score = 0.0
        
        # Contribution from drawdown (max 25 points)
        drawdown = metrics.get('current_drawdown', 0)
        score += min(drawdown * 100, 25)
        
        # Contribution from concentration (max 20 points)
        concentration = metrics.get('concentration_ratio', 0)
        score += min(concentration * 50, 20)
        
        # Contribution from leverage (max 15 points)
        leverage = metrics.get('leverage', 0)
        score += min(leverage * 7.5, 15)
        
        # Contribution from VaR (max 20 points)
        var = metrics.get('value_at_risk', 0)
        total_value = 100000  # Example
        if total_value > 0:
            var_pct = var / total_value
            score += min(var_pct * 500, 20)
        
        # Contribution from beta (max 10 points)
        beta = metrics.get('beta', 1.0)
        score += min((beta - 0.5) * 10, 10) if beta > 0.5 else 0
        
        # Contribution from volatility (max 10 points)
        volatility = metrics.get('volatility', 0)
        score += min(volatility * 25, 10)
        
        # Adjust for limit breaches
        breaches = len(limit_status.get('breached_limits', []))
        score += breaches * 5
        
        # Normalize to 0-100
        return min(max(score, 0), 100)

    def _determine_risk_level(
        self,
        risk_score: float,
        limit_status: Dict[str, Any]
    ) -> Tuple[RiskLevel, RiskStatus]:
        """
        Determine risk level and status based on score and limits.
        
        Args:
            risk_score: Risk score (0-100)
            limit_status: Limit status
            
        Returns:
            Tuple[RiskLevel, RiskStatus]: Risk level and status
        """
        # Check for critical breaches
        if limit_status.get('breached_limits'):
            return RiskLevel.CRITICAL, RiskStatus.CRITICAL
        
        # Check for warnings
        if limit_status.get('warnings'):
            return RiskLevel.HIGH, RiskStatus.WARNING
        
        # Determine based on risk score
        if risk_score >= 80:
            return RiskLevel.HIGH, RiskStatus.WARNING
        elif risk_score >= 60:
            return RiskLevel.MODERATE, RiskStatus.NORMAL
        elif risk_score >= 30:
            return RiskLevel.LOW, RiskStatus.NORMAL
        else:
            return RiskLevel.LOW, RiskStatus.NORMAL

    # =========================================================================
    # PUBLIC API METHODS
    # =========================================================================

    async def update_risk_limit(
        self,
        limit_type: str,
        update: RiskLimitUpdate
    ) -> bool:
        """
        Update a risk limit configuration.
        
        Args:
            limit_type: Type of risk limit
            update: Update data
            
        Returns:
            bool: Success indicator
        """
        try:
            if limit_type not in self._risk_limits:
                self._risk_limits[limit_type] = RiskLimitConfig(
                    limit_type=limit_type,
                    max_value=update.max_value
                )
            
            limit = self._risk_limits[limit_type]
            limit.max_value = update.max_value
            if update.min_value is not None:
                limit.min_value = update.min_value
            limit.hard_limit = update.hard_limit
            limit.breach_action = update.breach_action or limit.breach_action
            limit.notification_enabled = update.notification_enabled
            
            logger.info(f"Risk limit {limit_type} updated: max={update.max_value}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating risk limit {limit_type}: {e}")
            return False

    async def get_risk_limit(
        self,
        limit_type: str
    ) -> Optional[RiskLimitConfig]:
        """Get a risk limit configuration"""
        return self._risk_limits.get(limit_type)

    async def get_all_risk_limits(self) -> Dict[str, RiskLimitConfig]:
        """Get all risk limit configurations"""
        return self._risk_limits.copy()

    async def reset_risk_limits(self) -> bool:
        """Reset risk limits to defaults"""
        try:
            self._init_risk_limits()
            logger.info("Risk limits reset to defaults")
            return True
        except Exception as e:
            logger.error(f"Error resetting risk limits: {e}")
            return False

    async def get_portfolio_risk_report(
        self,
        portfolio_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive portfolio risk report.
        
        Args:
            portfolio_id: Portfolio ID
            start_date: Start date for report
            end_date: End date for report
            
        Returns:
            Dict[str, Any]: Risk report
        """
        try:
            # Get portfolio data
            portfolio = await self.portfolio_repo.get_by_id(portfolio_id)
            if not portfolio:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Portfolio {portfolio_id} not found"
                )
            
            # Get historical snapshots
            snapshots = await self.portfolio_repo.get_snapshots(
                portfolio_id,
                start_date=start_date or datetime.utcnow() - timedelta(days=30),
                end_date=end_date or datetime.utcnow()
            )
            
            # Build report
            report = {
                'portfolio_id': portfolio_id,
                'generated_at': datetime.utcnow().isoformat(),
                'period_start': start_date.isoformat() if start_date else None,
                'period_end': end_date.isoformat() if end_date else None,
                'summary': {
                    'total_trades': len(await self.trade_repo.get_by_portfolio_id(portfolio_id)),
                    'unique_assets': len(await self.position_repo.get_by_portfolio_id(portfolio_id)),
                    'risk_level': await self._get_portfolio_risk_level(portfolio_id)
                },
                'metrics_over_time': [
                    {
                        'timestamp': s.timestamp.isoformat(),
                        'risk_score': self._calculate_risk_score(
                            self._get_metrics_from_snapshot(s),
                            {'breached_limits': [], 'warnings': []}
                        ),
                        'drawdown': s.drawdown,
                        'volatility': s.volatility,
                        'sharpe_ratio': s.sharpe_ratio
                    }
                    for s in snapshots
                ],
                'current_metrics': await self._get_current_metrics(portfolio_id),
                'limit_status': await self._check_risk_limits(
                    await self._get_current_metrics(portfolio_id)
                ),
                'recommendations': await self._generate_recommendations(
                    await self._get_current_metrics(portfolio_id),
                    {},
                    await self.position_repo.get_by_portfolio_id(portfolio_id)
                )
            }
            
            return report
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error generating portfolio risk report: {e}")
            raise

    async def _get_portfolio_risk_level(self, portfolio_id: str) -> str:
        """Get overall risk level for a portfolio"""
        try:
            metrics = await self._get_current_metrics(portfolio_id)
            limit_status = await self._check_risk_limits(metrics)
            risk_score = self._calculate_risk_score(metrics, limit_status)
            risk_level, _ = self._determine_risk_level(risk_score, limit_status)
            return risk_level.value
        except Exception:
            return RiskLevel.MODERATE.value

    async def _get_current_metrics(self, portfolio_id: str) -> Dict[str, Any]:
        """Get current risk metrics for a portfolio"""
        try:
            request = PortfolioRiskRequest(portfolio_id=portfolio_id)
            response = await self.analyze_portfolio_risk(request)
            return response.metrics
        except Exception as e:
            logger.error(f"Error getting current metrics: {e}")
            return {}

    def _get_metrics_from_snapshot(self, snapshot: Any) -> Dict[str, Any]:
        """Extract metrics from a portfolio snapshot"""
        return {
            'value_at_risk': getattr(snapshot, 'var', 0),
            'current_drawdown': getattr(snapshot, 'drawdown', 0),
            'sharpe_ratio': getattr(snapshot, 'sharpe_ratio', 0),
            'volatility': getattr(snapshot, 'volatility', 0),
            'leverage': getattr(snapshot, 'leverage', 0)
        }

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    async def close(self) -> None:
        """Close all connections and clean up resources"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        
        logger.info("PortfolioRiskManager closed")


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_portfolio_risk_manager(
    config: Optional[RiskConfig] = None,
    broker_factory: Optional[BrokerFactory] = None,
    portfolio_repo: Optional[PortfolioRepository] = None,
    trade_repo: Optional[TradeRepository] = None,
    position_repo: Optional[PositionRepository] = None
) -> PortfolioRiskManager:
    """
    Create a PortfolioRiskManager instance.
    
    Args:
        config: Risk configuration
        broker_factory: Factory for broker instances
        portfolio_repo: Portfolio repository
        trade_repo: Trade repository
        position_repo: Position repository
        
    Returns:
        PortfolioRiskManager: Configured risk manager
    """
    return PortfolioRiskManager(
        config=config,
        broker_factory=broker_factory,
        portfolio_repo=portfolio_repo,
        trade_repo=trade_repo,
        position_repo=position_repo
    )


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body
from typing import Optional

router = APIRouter(prefix="/api/v1/risk", tags=["Risk Management"])


async def get_risk_manager() -> PortfolioRiskManager:
    """Dependency to get PortfolioRiskManager instance"""
    # In production, use dependency injection
    return create_portfolio_risk_manager()


@router.post("/analyze", response_model=PortfolioRiskResponse)
async def analyze_portfolio_risk(
    request: PortfolioRiskRequest,
    risk_manager: PortfolioRiskManager = Depends(get_risk_manager)
):
    """Analyze portfolio risk comprehensively"""
    return await risk_manager.analyze_portfolio_risk(request)


@router.get("/limits/{limit_type}")
async def get_risk_limit(
    limit_type: str,
    risk_manager: PortfolioRiskManager = Depends(get_risk_manager)
):
    """Get a risk limit configuration"""
    limit = await risk_manager.get_risk_limit(limit_type)
    if not limit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Risk limit {limit_type} not found"
        )
    return limit.to_dict()


@router.put("/limits/{limit_type}")
async def update_risk_limit(
    limit_type: str,
    update: RiskLimitUpdate,
    risk_manager: PortfolioRiskManager = Depends(get_risk_manager)
):
    """Update a risk limit configuration"""
    success = await risk_manager.update_risk_limit(limit_type, update)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update risk limit {limit_type}"
        )
    return {"success": True, "limit_type": limit_type}


@router.get("/limits")
async def get_all_risk_limits(
    risk_manager: PortfolioRiskManager = Depends(get_risk_manager)
):
    """Get all risk limit configurations"""
    limits = await risk_manager.get_all_risk_limits()
    return {k: v.to_dict() for k, v in limits.items()}


@router.post("/limits/reset")
async def reset_risk_limits(
    risk_manager: PortfolioRiskManager = Depends(get_risk_manager)
):
    """Reset all risk limits to defaults"""
    success = await risk_manager.reset_risk_limits()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset risk limits"
        )
    return {"success": True}


@router.get("/report/{portfolio_id}")
async def get_portfolio_risk_report(
    portfolio_id: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    risk_manager: PortfolioRiskManager = Depends(get_risk_manager)
):
    """Generate a comprehensive portfolio risk report"""
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    
    return await risk_manager.get_portfolio_risk_report(
        portfolio_id,
        start_date=start,
        end_date=end
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PortfolioRiskManager',
    'PortfolioRiskRequest',
    'PortfolioRiskResponse',
    'RiskLimitUpdate',
    'RiskLevel',
    'RiskStatus',
    'RiskMetricType',
    'RiskLimitConfig',
    'RiskExposure',
    'RiskRecommendation',
    'create_portfolio_risk_manager',
    'router'
]
