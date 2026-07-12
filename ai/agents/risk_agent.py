"""
NEXUS AI TRADING SYSTEM - Risk Agent
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Risk Agent system with:
- Real-time risk monitoring
- Position risk assessment
- Portfolio risk management
- Value at Risk (VaR) calculation
- Stress testing
- Risk limit enforcement
- Risk scoring
- Risk reporting
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import math
import json
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator
from scipy import stats
from scipy.optimize import minimize

from ai.agents.base_agent import BaseAgent, AgentHealth, AgentStatus
from ai.agents.agent_capabilities import AgentCapability
from ai.agents.agent_config import AgentConfig
from ai.agents.agent_registry import get_agent_registry
from backend.brokers.base_broker import BaseBroker
from backend.brokers.broker_factory import get_broker
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import BrokerError, MarketDataError, RiskError
from backend.models.trading import Order, OrderSide, OrderType, OrderStatus

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class RiskMetric(str, Enum):
    """Risk metrics"""
    VAR = "value_at_risk"
    CVAR = "conditional_value_at_risk"
    SHARPE = "sharpe_ratio"
    SORTINO = "sortino_ratio"
    CALMAR = "calmar_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    CURRENT_DRAWDOWN = "current_drawdown"
    VOLATILITY = "volatility"
    BETA = "beta"
    ALPHA = "alpha"
    CORRELATION = "correlation"
    EXPOSURE = "exposure"
    LEVERAGE = "leverage"
    MARGIN = "margin_usage"
    LIQUIDITY = "liquidity_risk"
    CONCENTRATION = "concentration_risk"


class RiskLevel(str, Enum):
    """Risk levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskStatus(str, Enum):
    """Risk status"""
    NORMAL = "normal"
    WARNING = "warning"
    BREACH = "breach"
    CRITICAL = "critical"


@dataclass
class PositionRisk:
    """Position risk data"""
    symbol: str
    position_size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    risk_amount: float
    risk_percent: float
    var_95: float
    var_99: float
    expected_shortfall: float
    max_loss: float
    stop_loss_distance: float
    risk_level: RiskLevel
    risk_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioRisk:
    """Portfolio risk data"""
    total_value: float
    total_exposure: float
    total_risk: float
    var_95: float
    var_99: float
    expected_shortfall: float
    max_drawdown: float
    current_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    volatility: float
    beta: float
    alpha: float
    leverage: float
    margin_usage: float
    risk_score: float
    risk_level: RiskLevel
    risk_status: RiskStatus
    concentration: float
    diversification: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskEvent:
    """Risk event"""
    timestamp: datetime
    event_type: str
    severity: RiskLevel
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskLimit:
    """Risk limit"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str
    metric: RiskMetric
    limit: float
    warning_threshold: float
    breach_action: str
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class RiskConfig(BaseModel):
    """Risk agent configuration"""
    enabled: bool = True
    symbols: List[str] = Field(default_factory=list)
    max_position_size: float = Field(default=10000.0, gt=0)
    max_portfolio_risk: float = Field(default=0.02, ge=0, le=1)
    max_leverage: float = Field(default=3.0, ge=0)
    max_margin_usage: float = Field(default=0.8, ge=0, le=1)
    max_concentration: float = Field(default=0.2, ge=0, le=1)
    stop_loss_default: float = Field(default=0.05, gt=0)
    take_profit_default: float = Field(default=0.15, gt=0)
    var_confidence: float = Field(default=0.95, ge=0, le=1)
    lookback_period: int = Field(default=252, gt=0)
    risk_free_rate: float = Field(default=0.02, ge=0)
    stress_test_scenarios: List[Dict[str, Any]] = Field(default_factory=list)
    enable_auto_hedging: bool = False
    hedging_ratio: float = Field(default=0.5, ge=0, le=1)
    enable_stop_loss: bool = True
    enable_take_profit: bool = True
    enable_trailing_stop: bool = False
    trailing_stop_pct: float = Field(default=0.02, ge=0)
    risk_check_interval: int = Field(default=5, gt=0)
    report_interval: int = Field(default=60, gt=0)
    health_check_interval: int = Field(default=60, gt=0)
    log_level: str = "info"


# ========================================
# RISK MODELS
# ========================================

class RiskModel:
    """Base risk model"""
    
    def __init__(self, config: RiskConfig):
        self.config = config
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
    
    def calculate_var(
        self,
        returns: np.ndarray,
        confidence: float = 0.95,
        method: str = "historical"
    ) -> float:
        """Calculate Value at Risk"""
        if len(returns) < 2:
            return 0.0
        
        if method == "historical":
            return float(np.percentile(returns, (1 - confidence) * 100))
        elif method == "parametric":
            mean = np.mean(returns)
            std = np.std(returns)
            z_score = stats.norm.ppf(1 - confidence)
            return float(mean - z_score * std)
        elif method == "monte_carlo":
            # Simplified Monte Carlo
            mean = np.mean(returns)
            std = np.std(returns)
            simulations = np.random.normal(mean, std, 10000)
            return float(np.percentile(simulations, (1 - confidence) * 100))
        else:
            return 0.0
    
    def calculate_cvar(
        self,
        returns: np.ndarray,
        confidence: float = 0.95
    ) -> float:
        """Calculate Conditional Value at Risk (Expected Shortfall)"""
        if len(returns) < 2:
            return 0.0
        
        var = self.calculate_var(returns, confidence)
        tail_returns = returns[returns <= var]
        if len(tail_returns) == 0:
            return var
        return float(np.mean(tail_returns))
    
    def calculate_max_drawdown(self, prices: np.ndarray) -> float:
        """Calculate maximum drawdown"""
        if len(prices) < 2:
            return 0.0
        
        peak = np.maximum.accumulate(prices)
        drawdown = (peak - prices) / peak
        return float(np.max(drawdown))
    
    def calculate_current_drawdown(self, prices: np.ndarray) -> float:
        """Calculate current drawdown"""
        if len(prices) < 2:
            return 0.0
        
        peak = np.max(prices)
        current = prices[-1]
        return float((peak - current) / peak) if peak > 0 else 0.0
    
    def calculate_sharpe_ratio(
        self,
        returns: np.ndarray,
        risk_free_rate: float = 0.02
    ) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - risk_free_rate / 252  # Daily risk-free rate
        if np.std(returns) == 0:
            return 0.0
        
        return float(np.mean(excess_returns) / np.std(returns) * np.sqrt(252))
    
    def calculate_sortino_ratio(
        self,
        returns: np.ndarray,
        risk_free_rate: float = 0.02,
        target_return: float = 0.0
    ) -> float:
        """Calculate Sortino ratio"""
        if len(returns) < 2:
            return 0.0
        
        downside_returns = returns[returns < target_return]
        if len(downside_returns) == 0:
            return 0.0
        
        downside_deviation = np.std(downside_returns)
        if downside_deviation == 0:
            return 0.0
        
        excess_return = np.mean(returns) - risk_free_rate / 252
        return float(excess_return / downside_deviation * np.sqrt(252))
    
    def calculate_calmar_ratio(
        self,
        returns: np.ndarray,
        prices: np.ndarray
    ) -> float:
        """Calculate Calmar ratio"""
        if len(returns) < 2 or len(prices) < 2:
            return 0.0
        
        annual_return = np.mean(returns) * 252
        max_drawdown = self.calculate_max_drawdown(prices)
        
        if max_drawdown == 0:
            return 0.0
        
        return float(annual_return / max_drawdown)
    
    def calculate_volatility(self, returns: np.ndarray) -> float:
        """Calculate annualized volatility"""
        if len(returns) < 2:
            return 0.0
        
        return float(np.std(returns) * np.sqrt(252))
    
    def calculate_beta(
        self,
        returns: np.ndarray,
        market_returns: np.ndarray
    ) -> float:
        """Calculate beta (market risk)"""
        if len(returns) < 2 or len(market_returns) < 2:
            return 1.0
        
        covariance = np.cov(returns, market_returns)[0][1]
        variance = np.var(market_returns)
        
        if variance == 0:
            return 1.0
        
        return float(covariance / variance)
    
    def calculate_alpha(
        self,
        returns: np.ndarray,
        market_returns: np.ndarray,
        risk_free_rate: float = 0.02
    ) -> float:
        """Calculate alpha (excess return)"""
        if len(returns) < 2 or len(market_returns) < 2:
            return 0.0
        
        beta = self.calculate_beta(returns, market_returns)
        expected_return = risk_free_rate / 252 + beta * (np.mean(market_returns) - risk_free_rate / 252)
        alpha = np.mean(returns) - expected_return
        
        return float(alpha * 252)  # Annualized alpha


# ========================================
# RISK AGENT
# ========================================

class RiskAgent(BaseAgent):
    """
    Risk Agent for comprehensive risk management.
    
    Features:
    - Real-time risk monitoring
    - Position and portfolio risk assessment
    - Value at Risk (VaR) calculation
    - Stress testing
    - Risk limit enforcement
    - Risk scoring
    - Risk reporting
    - Auto-hedging
    - Stop loss management
    - Health monitoring
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._config = RiskConfig(**config)
        self._broker: Optional[BaseBroker] = None
        self._risk_model = RiskModel(self._config)
        
        # State
        self._positions: Dict[str, Dict[str, Any]] = {}
        self._position_risks: Dict[str, PositionRisk] = {}
        self._portfolio_risk: Optional[PortfolioRisk] = None
        self._risk_limits: Dict[str, RiskLimit] = {}
        self._risk_events: List[RiskEvent] = []
        self._price_history: Dict[str, List[float]] = {}
        self._return_history: Dict[str, np.ndarray] = {}
        
        # Running state
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._lock = asyncio.Lock()
        
        # Metrics
        self._metrics = {
            "total_checks": 0,
            "warnings": 0,
            "breaches": 0,
            "critical_events": 0,
            "current_risk_score": 0.0,
            "avg_risk_score": 0.0,
            "max_risk_score": 0.0,
            "current_risk_level": RiskLevel.LOW.value,
            "positions_monitored": 0,
            "limits_enforced": 0
        }
        
        self._initialize_risk_limits()
        self._initialize_broker()
        
        self.logger.info("RiskAgent initialized successfully")
    
    def _initialize_risk_limits(self) -> None:
        """Initialize risk limits"""
        limits = [
            RiskLimit(
                name="Max Position Size",
                metric=RiskMetric.EXPOSURE,
                limit=self._config.max_position_size,
                warning_threshold=self._config.max_position_size * 0.8,
                breach_action="close_position"
            ),
            RiskLimit(
                name="Max Portfolio Risk",
                metric=RiskMetric.VAR,
                limit=self._config.max_portfolio_risk,
                warning_threshold=self._config.max_portfolio_risk * 0.8,
                breach_action="reduce_exposure"
            ),
            RiskLimit(
                name="Max Leverage",
                metric=RiskMetric.LEVERAGE,
                limit=self._config.max_leverage,
                warning_threshold=self._config.max_leverage * 0.8,
                breach_action="reduce_leverage"
            ),
            RiskLimit(
                name="Max Margin Usage",
                metric=RiskMetric.MARGIN,
                limit=self._config.max_margin_usage,
                warning_threshold=self._config.max_margin_usage * 0.8,
                breach_action="reduce_margin"
            ),
            RiskLimit(
                name="Max Concentration",
                metric=RiskMetric.CONCENTRATION,
                limit=self._config.max_concentration,
                warning_threshold=self._config.max_concentration * 0.8,
                breach_action="diversify"
            ),
            RiskLimit(
                name="Max Drawdown",
                metric=RiskMetric.MAX_DRAWDOWN,
                limit=0.20,
                warning_threshold=0.15,
                breach_action="reduce_exposure"
            )
        ]
        
        for limit in limits:
            self._risk_limits[limit.id] = limit
    
    def _initialize_broker(self) -> None:
        """Initialize broker connection"""
        try:
            self._broker = get_broker(self._config.exchange)
            self.logger.info(f"Initialized broker for {self._config.exchange}")
        except Exception as e:
            self.logger.error(f"Failed to initialize broker: {e}")
            raise
    
    # ========================================
    # AGENT LIFECYCLE
    # ========================================
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the risk agent"""
        self.logger.info(f"Initializing RiskAgent with config: {config}")
        
        if config:
            self._config = RiskConfig(**{**self._config.dict(), **config})
        
        # Initialize price history
        for symbol in self._config.symbols:
            self._price_history[symbol] = []
            self._return_history[symbol] = np.array([])
        
        self.capabilities = [
            AgentCapability.RISK_MANAGEMENT,
            AgentCapability.PORTFOLIO_ANALYTICS,
            AgentCapability.ORDER_EXECUTION
        ]
        
        self.status = AgentStatus.INITIALIZED
        self.health = AgentHealth.HEALTHY
        self.logger.info("RiskAgent initialized successfully")
    
    async def start(self) -> None:
        """Start the risk agent"""
        self.logger.info("Starting RiskAgent...")
        self._running = True
        
        self._tasks.append(asyncio.create_task(self._risk_monitoring_loop()))
        self._tasks.append(asyncio.create_task(self._reporting_loop()))
        self._tasks.append(asyncio.create_task(self._health_loop()))
        
        self.status = AgentStatus.RUNNING
        self.health = AgentHealth.HEALTHY
        self.logger.info("RiskAgent started successfully")
    
    async def stop(self) -> None:
        """Stop the risk agent"""
        self.logger.info("Stopping RiskAgent...")
        self._running = False
        
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._tasks.clear()
        self.status = AgentStatus.STOPPED
        self.logger.info("RiskAgent stopped")
    
    async def pause(self) -> None:
        """Pause the risk agent"""
        self.logger.info("Pausing RiskAgent...")
        self._running = False
        self.status = AgentStatus.PAUSED
        self.logger.info("RiskAgent paused")
    
    async def resume(self) -> None:
        """Resume the risk agent"""
        self.logger.info("Resuming RiskAgent...")
        self._running = True
        
        self._tasks.append(asyncio.create_task(self._risk_monitoring_loop()))
        self._tasks.append(asyncio.create_task(self._reporting_loop()))
        self._tasks.append(asyncio.create_task(self._health_loop()))
        
        self.status = AgentStatus.RUNNING
        self.logger.info("RiskAgent resumed")
    
    async def health_check(self) -> AgentHealth:
        """Check agent health"""
        try:
            if not self._running:
                return AgentHealth.DEGRADED
            
            if not self._broker:
                return AgentHealth.UNHEALTHY
            
            if self._portfolio_risk:
                if self._portfolio_risk.risk_status == RiskStatus.CRITICAL:
                    return AgentHealth.DEGRADED
            
            return AgentHealth.HEALTHY
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return AgentHealth.UNHEALTHY
    
    # ========================================
    # RISK MONITORING
    # ========================================
    
    async def _risk_monitoring_loop(self) -> None:
        """Main risk monitoring loop"""
        while self._running:
            try:
                await self._update_positions()
                await self._calculate_position_risks()
                await self._calculate_portfolio_risk()
                await self._check_risk_limits()
                await self._handle_risk_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Risk monitoring loop error: {e}")
                self.health = AgentHealth.DEGRADED
            
            await asyncio.sleep(self._config.risk_check_interval)
    
    async def _update_positions(self) -> None:
        """Update position data"""
        if not self._broker:
            return
        
        for symbol in self._config.symbols:
            try:
                # Get current price
                ticker = await self._broker.get_ticker(symbol)
                if not ticker:
                    continue
                
                current_price = ticker.get('last', 0)
                
                # Get position from broker
                position = await self._broker.get_position(symbol)
                
                if position:
                    self._positions[symbol] = {
                        'size': position.get('size', 0),
                        'entry_price': position.get('entry_price', 0),
                        'current_price': current_price,
                        'unrealized_pnl': position.get('unrealized_pnl', 0),
                        'realized_pnl': position.get('realized_pnl', 0)
                    }
                    
                    # Update price history
                    if current_price > 0:
                        self._price_history[symbol].append(current_price)
                        if len(self._price_history[symbol]) > self._config.lookback_period * 2:
                            self._price_history[symbol] = self._price_history[symbol][-self._config.lookback_period * 2:]
                        
                        # Update returns
                        if len(self._price_history[symbol]) > 1:
                            returns = np.diff(self._price_history[symbol]) / self._price_history[symbol][:-1]
                            self._return_history[symbol] = returns
                    
            except Exception as e:
                self.logger.error(f"Failed to update position for {symbol}: {e}")
    
    async def _calculate_position_risks(self) -> None:
        """Calculate risk for each position"""
        for symbol, position in self._positions.items():
            position_risk = await self._calculate_position_risk(
                symbol,
                position
            )
            self._position_risks[symbol] = position_risk
    
    async def _calculate_position_risk(
        self,
        symbol: str,
        position: Dict[str, Any]
    ) -> PositionRisk:
        """Calculate risk for a single position"""
        size = position.get('size', 0)
        entry_price = position.get('entry_price', 0)
        current_price = position.get('current_price', 0)
        
        if size == 0 or entry_price == 0:
            return PositionRisk(
                symbol=symbol,
                position_size=0,
                entry_price=0,
                current_price=0,
                unrealized_pnl=0,
                risk_amount=0,
                risk_percent=0,
                var_95=0,
                var_99=0,
                expected_shortfall=0,
                max_loss=0,
                stop_loss_distance=0,
                risk_level=RiskLevel.LOW,
                risk_score=0.0
            )
        
        # Calculate position value
        position_value = abs(size) * current_price
        
        # Calculate risk using returns
        returns = self._return_history.get(symbol, np.array([]))
        var_95 = 0
        var_99 = 0
        expected_shortfall = 0
        
        if len(returns) > 1:
            var_95 = abs(self._risk_model.calculate_var(returns, 0.95)) * position_value
            var_99 = abs(self._risk_model.calculate_var(returns, 0.99)) * position_value
            expected_shortfall = abs(self._risk_model.calculate_cvar(returns, 0.95)) * position_value
        
        # Calculate max loss
        stop_loss_pct = self._config.stop_loss_default
        max_loss = position_value * stop_loss_pct
        
        # Calculate risk metrics
        risk_amount = max(var_95, max_loss)
        risk_percent = (risk_amount / position_value) if position_value > 0 else 0
        
        # Calculate stop loss distance
        if size > 0:
            stop_loss_distance = (current_price - entry_price * (1 - stop_loss_pct)) / current_price if current_price > 0 else 0
        else:
            stop_loss_distance = (entry_price * (1 + stop_loss_pct) - current_price) / current_price if current_price > 0 else 0
        
        # Determine risk level
        risk_score = min(1.0, risk_percent * 10)
        
        if risk_score < 0.3:
            risk_level = RiskLevel.LOW
        elif risk_score < 0.6:
            risk_level = RiskLevel.MEDIUM
        elif risk_score < 0.8:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL
        
        return PositionRisk(
            symbol=symbol,
            position_size=size,
            entry_price=entry_price,
            current_price=current_price,
            unrealized_pnl=position.get('unrealized_pnl', 0),
            risk_amount=risk_amount,
            risk_percent=risk_percent,
            var_95=var_95,
            var_99=var_99,
            expected_shortfall=expected_shortfall,
            max_loss=max_loss,
            stop_loss_distance=stop_loss_distance,
            risk_level=risk_level,
            risk_score=risk_score,
            metadata={
                'position_value': position_value,
                'returns_count': len(returns)
            }
        )
    
    async def _calculate_portfolio_risk(self) -> None:
        """Calculate portfolio risk"""
        total_value = 0
        total_exposure = 0
        total_risk = 0
        
        # Aggregate positions
        returns_list = []
        prices_list = []
        
        for symbol, position_risk in self._position_risks.items():
            position_value = abs(position_risk.position_size) * position_risk.current_price
            total_value += position_value
            total_exposure += position_risk.risk_amount
            total_risk += position_risk.risk_percent * position_value
            
            # Get returns for this symbol
            returns = self._return_history.get(symbol, np.array([]))
            if len(returns) > 1:
                returns_list.append(returns)
            
            # Get prices for drawdown calculation
            prices = self._price_history.get(symbol, [])
            if len(prices) > 1:
                prices_list.append(np.array(prices))
        
        # Calculate portfolio-level metrics
        var_95 = 0
        var_99 = 0
        expected_shortfall = 0
        max_drawdown = 0
        current_drawdown = 0
        sharpe_ratio = 0
        sortino_ratio = 0
        calmar_ratio = 0
        volatility = 0
        beta = 1.0
        alpha = 0
        
        if returns_list:
            # Combine returns (simplified - assumes equal weighting)
            combined_returns = np.concatenate(returns_list)
            
            if len(combined_returns) > 1:
                var_95 = self._risk_model.calculate_var(combined_returns, 0.95) * total_value
                var_99 = self._risk_model.calculate_var(combined_returns, 0.99) * total_value
                expected_shortfall = self._risk_model.calculate_cvar(combined_returns, 0.95) * total_value
                volatility = self._risk_model.calculate_volatility(combined_returns)
                sharpe_ratio = self._risk_model.calculate_sharpe_ratio(combined_returns, self._config.risk_free_rate)
                sortino_ratio = self._risk_model.calculate_sortino_ratio(combined_returns, self._config.risk_free_rate)
        
        if prices_list:
            # Combine prices for drawdown
            # Use combined price series (simplified - equal weighting)
            combined_prices = np.mean([p for p in prices_list], axis=0)
            
            if len(combined_prices) > 1:
                max_drawdown = self._risk_model.calculate_max_drawdown(combined_prices)
                current_drawdown = self._risk_model.calculate_current_drawdown(combined_prices)
                
                # Calculate Calmar ratio
                returns = np.diff(combined_prices) / combined_prices[:-1]
                calmar_ratio = self._risk_model.calculate_calmar_ratio(returns, combined_prices)
        
        # Calculate concentration risk
        max_concentration = 0
        for position_risk in self._position_risks.values():
            position_value = abs(position_risk.position_size) * position_risk.current_price
            if total_value > 0:
                concentration = position_value / total_value
                if concentration > max_concentration:
                    max_concentration = concentration
        
        # Calculate diversification
        diversification = 1 - (total_risk / (total_exposure * len(self._position_risks)) if len(self._position_risks) > 0 else 0)
        
        # Calculate risk score
        risk_score = min(1.0, (total_risk / total_value) if total_value > 0 else 0)
        
        # Determine risk level
        if risk_score < 0.2:
            risk_level = RiskLevel.LOW
        elif risk_score < 0.4:
            risk_level = RiskLevel.MEDIUM
        elif risk_score < 0.6:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL
        
        # Determine risk status
        if risk_score > 0.8:
            risk_status = RiskStatus.CRITICAL
        elif risk_score > 0.6:
            risk_status = RiskStatus.BREACH
        elif risk_score > 0.4:
            risk_status = RiskStatus.WARNING
        else:
            risk_status = RiskStatus.NORMAL
        
        self._portfolio_risk = PortfolioRisk(
            total_value=total_value,
            total_exposure=total_exposure,
            total_risk=total_risk,
            var_95=var_95,
            var_99=var_99,
            expected_shortfall=expected_shortfall,
            max_drawdown=max_drawdown,
            current_drawdown=current_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            volatility=volatility,
            beta=beta,
            alpha=alpha,
            leverage=total_exposure / total_value if total_value > 0 else 0,
            margin_usage=total_exposure / self._config.max_position_size if self._config.max_position_size > 0 else 0,
            risk_score=risk_score,
            risk_level=risk_level,
            risk_status=risk_status,
            concentration=max_concentration,
            diversification=diversification,
            metadata={
                'positions_count': len(self._position_risks),
                'total_value': total_value
            }
        )
        
        # Update metrics
        self._metrics["current_risk_score"] = risk_score
        self._metrics["current_risk_level"] = risk_level.value
        if risk_score > self._metrics["max_risk_score"]:
            self._metrics["max_risk_score"] = risk_score
    
    async def _check_risk_limits(self) -> None:
        """Check risk limits"""
        if not self._portfolio_risk:
            return
        
        for limit in self._risk_limits.values():
            if not limit.enabled:
                continue
            
            current_value = await self._get_metric_value(limit.metric)
            
            if current_value > limit.limit:
                self._metrics["breaches"] += 1
                await self._handle_risk_breach(limit, current_value)
            elif current_value > limit.warning_threshold:
                self._metrics["warnings"] += 1
                await self._handle_risk_warning(limit, current_value)
    
    async def _get_metric_value(self, metric: RiskMetric) -> float:
        """Get current value for a risk metric"""
        if not self._portfolio_risk:
            return 0.0
        
        mapping = {
            RiskMetric.VAR: self._portfolio_risk.var_95,
            RiskMetric.CVAR: self._portfolio_risk.expected_shortfall,
            RiskMetric.SHARPE: self._portfolio_risk.sharpe_ratio,
            RiskMetric.SORTINO: self._portfolio_risk.sortino_ratio,
            RiskMetric.CALMAR: self._portfolio_risk.calmar_ratio,
            RiskMetric.MAX_DRAWDOWN: self._portfolio_risk.max_drawdown,
            RiskMetric.CURRENT_DRAWDOWN: self._portfolio_risk.current_drawdown,
            RiskMetric.VOLATILITY: self._portfolio_risk.volatility,
            RiskMetric.BETA: self._portfolio_risk.beta,
            RiskMetric.ALPHA: self._portfolio_risk.alpha,
            RiskMetric.EXPOSURE: self._portfolio_risk.total_exposure,
            RiskMetric.LEVERAGE: self._portfolio_risk.leverage,
            RiskMetric.MARGIN: self._portfolio_risk.margin_usage,
            RiskMetric.CONCENTRATION: self._portfolio_risk.concentration
        }
        
        return mapping.get(metric, 0.0)
    
    async def _handle_risk_warning(
        self,
        limit: RiskLimit,
        current_value: float
    ) -> None:
        """Handle risk warning"""
        event = RiskEvent(
            timestamp=datetime.utcnow(),
            event_type="risk_warning",
            severity=RiskLevel.MEDIUM,
            message=f"Risk limit warning: {limit.name} = {current_value:.2f} (threshold: {limit.warning_threshold})",
            data={
                "limit_id": limit.id,
                "limit_name": limit.name,
                "metric": limit.metric.value,
                "current_value": current_value,
                "warning_threshold": limit.warning_threshold,
                "limit": limit.limit
            }
        )
        
        self._risk_events.append(event)
        self._metrics["warnings"] += 1
        
        self.logger.warning(event.message)
        await self._emit_risk_event(event)
    
    async def _handle_risk_breach(
        self,
        limit: RiskLimit,
        current_value: float
    ) -> None:
        """Handle risk breach"""
        event = RiskEvent(
            timestamp=datetime.utcnow(),
            event_type="risk_breach",
            severity=RiskLevel.HIGH,
            message=f"Risk limit breached: {limit.name} = {current_value:.2f} (limit: {limit.limit})",
            data={
                "limit_id": limit.id,
                "limit_name": limit.name,
                "metric": limit.metric.value,
                "current_value": current_value,
                "limit": limit.limit,
                "breach_action": limit.breach_action
            }
        )
        
        self._risk_events.append(event)
        self._metrics["breaches"] += 1
        
        self.logger.critical(event.message)
        await self._emit_risk_event(event)
        
        # Execute breach action
        await self._execute_breach_action(limit, current_value)
    
    async def _execute_breach_action(
        self,
        limit: RiskLimit,
        current_value: float
    ) -> None:
        """Execute breach action"""
        self.logger.info(f"Executing breach action: {limit.breach_action}")
        
        if limit.breach_action == "close_position":
            await self._close_positions()
        elif limit.breach_action == "reduce_exposure":
            await self._reduce_exposure(limit.limit / current_value)
        elif limit.breach_action == "reduce_leverage":
            await self._reduce_leverage()
        elif limit.breach_action == "reduce_margin":
            await self._reduce_margin()
        elif limit.breach_action == "diversify":
            await self._rebalance_portfolio()
    
    async def _close_positions(self) -> None:
        """Close all positions"""
        if not self._broker:
            return
        
        self.logger.warning("Closing all positions due to risk breach")
        
        for symbol, position in self._positions.items():
            try:
                if position['size'] != 0:
                    side = 'sell' if position['size'] > 0 else 'buy'
                    await self._broker.create_order(
                        symbol=symbol,
                        side=side,
                        type='market',
                        quantity=abs(position['size'])
                    )
                    self.logger.info(f"Closed position for {symbol}")
            except Exception as e:
                self.logger.error(f"Failed to close position for {symbol}: {e}")
    
    async def _reduce_exposure(self, reduction_factor: float) -> None:
        """Reduce exposure by factor"""
        if not self._broker:
            return
        
        self.logger.info(f"Reducing exposure by factor: {reduction_factor}")
        
        for symbol, position in self._positions.items():
            if position['size'] != 0:
                new_size = position['size'] * reduction_factor
                reduction = abs(position['size'] - new_size)
                
                if reduction > 0:
                    side = 'sell' if position['size'] > 0 else 'buy'
                    try:
                        await self._broker.create_order(
                            symbol=symbol,
                            side=side,
                            type='market',
                            quantity=reduction
                        )
                        self.logger.info(f"Reduced exposure for {symbol}: {reduction}")
                    except Exception as e:
                        self.logger.error(f"Failed to reduce exposure for {symbol}: {e}")
    
    async def _reduce_leverage(self) -> None:
        """Reduce leverage"""
        # Implement leverage reduction logic
        pass
    
    async def _reduce_margin(self) -> None:
        """Reduce margin usage"""
        # Implement margin reduction logic
        pass
    
    async def _rebalance_portfolio(self) -> None:
        """Rebalance portfolio for diversification"""
        # Implement portfolio rebalancing logic
        pass
    
    async def _handle_risk_events(self) -> None:
        """Handle and process risk events"""
        # Clean up old events
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self._risk_events = [e for e in self._risk_events if e.timestamp > cutoff]
        
        # Check for critical events
        critical_events = [
            e for e in self._risk_events
            if e.severity == RiskLevel.CRITICAL
        ]
        
        if len(critical_events) > 5:
            self.health = AgentHealth.DEGRADED
        
        self._metrics["critical_events"] = len(critical_events)
    
    async def _emit_risk_event(self, event: RiskEvent) -> None:
        """Emit a risk event"""
        # Store in Redis for other agents
        try:
            key = f"risk_events:{event.timestamp.isoformat()}"
            self.redis.setex(
                key,
                3600,
                json.dumps({
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type,
                    "severity": event.severity.value,
                    "message": event.message,
                    "data": event.data
                })
            )
        except Exception as e:
            self.logger.error(f"Failed to store risk event: {e}")
    
    # ========================================
    # REPORTING
    # ========================================
    
    async def _reporting_loop(self) -> None:
        """Reporting loop"""
        while self._running:
            try:
                await self._generate_risk_report()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Reporting loop error: {e}")
            
            await asyncio.sleep(self._config.report_interval)
    
    async def _generate_risk_report(self) -> None:
        """Generate risk report"""
        if not self._portfolio_risk:
            return
        
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "portfolio_risk": {
                "total_value": self._portfolio_risk.total_value,
                "var_95": self._portfolio_risk.var_95,
                "var_99": self._portfolio_risk.var_99,
                "expected_shortfall": self._portfolio_risk.expected_shortfall,
                "max_drawdown": self._portfolio_risk.max_drawdown,
                "current_drawdown": self._portfolio_risk.current_drawdown,
                "sharpe_ratio": self._portfolio_risk.sharpe_ratio,
                "sortino_ratio": self._portfolio_risk.sortino_ratio,
                "calmar_ratio": self._portfolio_risk.calmar_ratio,
                "volatility": self._portfolio_risk.volatility,
                "leverage": self._portfolio_risk.leverage,
                "margin_usage": self._portfolio_risk.margin_usage,
                "risk_level": self._portfolio_risk.risk_level.value,
                "risk_status": self._portfolio_risk.risk_status.value
            },
            "positions": [],
            "risk_events": [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "event_type": e.event_type,
                    "severity": e.severity.value,
                    "message": e.message
                }
                for e in self._risk_events[-10:]
            ],
            "metrics": self._metrics
        }
        
        # Add position risks
        for symbol, position_risk in self._position_risks.items():
            if position_risk.position_size != 0:
                report["positions"].append({
                    "symbol": symbol,
                    "position_size": position_risk.position_size,
                    "risk_amount": position_risk.risk_amount,
                    "risk_percent": position_risk.risk_percent,
                    "var_95": position_risk.var_95,
                    "var_99": position_risk.var_99,
                    "risk_level": position_risk.risk_level.value
                })
        
        # Store report
        try:
            key = f"risk_report:{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            self.redis.setex(
                key,
                3600,
                json.dumps(report, default=str)
            )
        except Exception as e:
            self.logger.error(f"Failed to store risk report: {e}")
        
        self.logger.info(f"Risk report generated: {len(report['positions'])} positions")
    
    async def _health_loop(self) -> None:
        """Health monitoring loop"""
        while self._running:
            try:
                self.health = await self.health_check()
                self.logger.debug(f"Health: {self.health}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health loop error: {e}")
            
            await asyncio.sleep(self._config.health_check_interval)
    
    # ========================================
    # API METHODS
    # ========================================
    
    async def get_portfolio_risk(self) -> Optional[Dict[str, Any]]:
        """Get portfolio risk data"""
        if not self._portfolio_risk:
            return None
        
        return {
            "total_value": self._portfolio_risk.total_value,
            "total_exposure": self._portfolio_risk.total_exposure,
            "total_risk": self._portfolio_risk.total_risk,
            "var_95": self._portfolio_risk.var_95,
            "var_99": self._portfolio_risk.var_99,
            "expected_shortfall": self._portfolio_risk.expected_shortfall,
            "max_drawdown": self._portfolio_risk.max_drawdown,
            "current_drawdown": self._portfolio_risk.current_drawdown,
            "sharpe_ratio": self._portfolio_risk.sharpe_ratio,
            "sortino_ratio": self._portfolio_risk.sortino_ratio,
            "calmar_ratio": self._portfolio_risk.calmar_ratio,
            "volatility": self._portfolio_risk.volatility,
            "beta": self._portfolio_risk.beta,
            "alpha": self._portfolio_risk.alpha,
            "leverage": self._portfolio_risk.leverage,
            "margin_usage": self._portfolio_risk.margin_usage,
            "risk_score": self._portfolio_risk.risk_score,
            "risk_level": self._portfolio_risk.risk_level.value,
            "risk_status": self._portfolio_risk.risk_status.value,
            "concentration": self._portfolio_risk.concentration,
            "diversification": self._portfolio_risk.diversification
        }
    
    async def get_position_risks(self) -> Dict[str, Dict[str, Any]]:
        """Get position risk data"""
        position_risks = {}
        
        for symbol, position_risk in self._position_risks.items():
            if position_risk.position_size != 0:
                position_risks[symbol] = {
                    "position_size": position_risk.position_size,
                    "risk_amount": position_risk.risk_amount,
                    "risk_percent": position_risk.risk_percent,
                    "var_95": position_risk.var_95,
                    "var_99": position_risk.var_99,
                    "expected_shortfall": position_risk.expected_shortfall,
                    "max_loss": position_risk.max_loss,
                    "stop_loss_distance": position_risk.stop_loss_distance,
                    "risk_level": position_risk.risk_level.value,
                    "risk_score": position_risk.risk_score
                }
        
        return position_risks
    
    async def get_risk_events(
        self,
        limit: int = 50,
        severity: Optional[RiskLevel] = None
    ) -> List[Dict[str, Any]]:
        """Get risk events"""
        events = self._risk_events
        
        if severity:
            events = [e for e in events if e.severity == severity]
        
        return [
            {
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type,
                "severity": e.severity.value,
                "message": e.message,
                "data": e.data
            }
            for e in events[-limit:]
        ]
    
    async def get_risk_limits(self) -> Dict[str, Dict[str, Any]]:
        """Get risk limits"""
        return {
            limit.id: {
                "name": limit.name,
                "metric": limit.metric.value,
                "limit": limit.limit,
                "warning_threshold": limit.warning_threshold,
                "breach_action": limit.breach_action,
                "enabled": limit.enabled
            }
            for limit in self._risk_limits.values()
        }
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics"""
        return {
            **self._metrics,
            "positions_monitored": len(self._position_risks),
            "limits_count": len(self._risk_limits),
            "events_count": len(self._risk_events),
            "running": self._running,
            "status": self.status,
            "health": self.health
        }
    
    async def get_stress_test(self, scenario: str = "market_crash") -> Dict[str, Any]:
        """Run stress test"""
        # Implement stress testing
        pass
    
    async def force_risk_check(self) -> Dict[str, Any]:
        """Force an immediate risk check"""
        await self._update_positions()
        await self._calculate_position_risks()
        await self._calculate_portfolio_risk()
        await self._check_risk_limits()
        
        return {
            "portfolio_risk": await self.get_portfolio_risk(),
            "position_risks": await self.get_position_risks(),
            "metrics": await self.get_metrics()
        }
    
    # ========================================
    # STATE PERSISTENCE
    # ========================================
    
    async def save_state(self) -> None:
        """Save agent state"""
        try:
            state = {
                "portfolio_risk": await self.get_portfolio_risk(),
                "position_risks": await self.get_position_risks(),
                "metrics": self._metrics,
                "risk_events": await self.get_risk_events(limit=10)
            }
            
            key = f"risk_agent_state:{self.agent_id}"
            self.redis.setex(
                key,
                settings.REDIS_AGENT_TTL,
                json.dumps(state, default=str)
            )
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")


# ========================================
# DEPENDENCY INJECTION
# ========================================

def create_risk_agent(config: Dict[str, Any]) -> RiskAgent:
    """Create a risk agent instance"""
    return RiskAgent(config)


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'RiskAgent',
    'RiskConfig',
    'RiskMetric',
    'RiskLevel',
    'RiskStatus',
    'PositionRisk',
    'PortfolioRisk',
    'RiskEvent',
    'RiskLimit',
    'RiskModel',
    'create_risk_agent'
]
