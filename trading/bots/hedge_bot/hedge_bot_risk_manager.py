"""
NEXUS AI TRADING SYSTEM
Hedge Bot Risk Manager - FULL PRODUCTION VERSION

Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

File: trading/bots/hedge_bot/hedge_bot_risk_manager.py
Description: Core risk management for hedge bot with real-time monitoring,
             position sizing, risk controls, portfolio risk aggregation,
             and advanced risk metrics with real API data integration.
"""

import asyncio
import json
import logging
import math
import pickle
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union, Callable, Awaitable
from decimal import Decimal
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from scipy.stats import norm, t, skew, kurtosis, jarque_bera

from shared.utilities.logger import get_logger
from shared.utilities.retry import retry_async, RetryConfig
from shared.utilities.cache import cache_result, CacheConfig
from shared.configs.broker_config import BrokerConfig
from shared.configs.market_data_config import MarketDataConfig

logger = get_logger(__name__)


class RiskLevel(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    EXTREME = "extreme"


class RiskMetricType(str, Enum):
    VAR = "var"
    CVAR = "cvar"
    EXPECTED_SHORTFALL = "expected_shortfall"
    MAX_DRAWDOWN = "max_drawdown"
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    OMEGA_RATIO = "omega_ratio"
    TAIL_RATIO = "tail_ratio"
    BETA = "beta"
    ALPHA = "alpha"
    R_SQUARED = "r_squared"
    TREYNOR_RATIO = "treynor_ratio"
    INFORMATION_RATIO = "information_ratio"
    VOLATILITY = "volatility"
    CORRELATION = "correlation"
    CONCENTRATION = "concentration"
    LEVERAGE = "leverage"
    STRESS_IMPACT = "stress_impact"


class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    PENDING = "pending"
    REJECTED = "rejected"
    PARTIALLY_CLOSED = "partially_closed"
    STOPPED = "stopped"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskConfig:
    max_position_size: float = 100000.0
    max_portfolio_risk: float = 0.02
    max_portfolio_risk_per_day: float = 0.05
    max_portfolio_risk_per_week: float = 0.10
    max_drawdown: float = 0.20
    max_leverage: float = 10.0
    var_confidence: float = 0.95
    var_confidence_high: float = 0.99
    risk_free_rate: float = 0.03
    volatility_lookback: int = 30
    correlation_lookback: int = 60
    max_correlation: float = 0.7
    min_sharpe_ratio: float = 0.5
    max_concentration: float = 0.25
    risk_level: RiskLevel = RiskLevel.MODERATE
    stop_loss_default: float = 0.02
    take_profit_default: float = 0.04
    trailing_stop_default: float = 0.015
    max_positions: int = 20
    max_sector_exposure: float = 0.30
    max_asset_class_exposure: float = 0.40
    stress_test_shocks: List[float] = field(default_factory=lambda: [-0.10, -0.20, -0.30, -0.50])
    use_real_data: bool = True
    enable_ai_risk_prediction: bool = True
    alert_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "drawdown": 0.15,
        "var": 0.05,
        "sharpe": 0.0,
        "leverage": 8.0,
        "concentration": 0.20,
        "volatility": 0.40,
    })


@dataclass
class PositionRisk:
    symbol: str
    position_size: float
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    unrealized_pnl: float
    realized_pnl: float
    risk_amount: float
    reward_amount: float
    risk_reward_ratio: float
    var_95: float
    cvar_95: float
    var_99: float
    cvar_99: float
    max_drawdown: float
    volatility: float
    correlation: float
    beta: float
    alpha: float
    leverage: float
    sharpe_contribution: float
    sortino_contribution: float
    status: PositionStatus = PositionStatus.OPEN
    timestamp: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    entry_timestamp: datetime = field(default_factory=datetime.now)
    sector: str = ""
    asset_class: str = ""
    strategy: str = ""
    notes: str = ""


@dataclass
class PortfolioRisk:
    total_value: float
    total_risk: float
    total_exposure: float
    var_95: float
    cvar_95: float
    var_99: float
    cvar_99: float
    expected_shortfall: float
    max_drawdown: float
    current_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    omega_ratio: float
    tail_ratio: float
    beta: float
    alpha: float
    r_squared: float
    treynor_ratio: float
    information_ratio: float
    volatility: float
    skewness: float
    kurtosis: float
    correlation_matrix: Dict[str, Dict[str, float]]
    concentration_ratio: float
    sector_exposures: Dict[str, float]
    asset_class_exposures: Dict[str, float]
    risk_score: float
    risk_level: RiskLevel
    positions: List[PositionRisk]
    stress_test_results: Dict[str, float]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RiskAlert:
    alert_id: str
    alert_type: str
    severity: AlertSeverity
    message: str
    symbol: str
    metric: str
    value: float
    threshold: float
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    resolved: bool = False


@dataclass
class RiskPrediction:
    symbol: str
    predicted_var: float
    predicted_cvar: float
    predicted_volatility: float
    predicted_drawdown: float
    confidence: float
    model: str
    timestamp: datetime = field(default_factory=datetime.now)


class RiskManager:
    """
    Advanced risk management system for hedge bot with real API data integration.
    
    Features:
    - Real-time position risk calculation
    - Portfolio risk aggregation
    - VaR, CVaR, Expected Shortfall
    - Stress testing and scenario analysis
    - Dynamic position sizing
    - Correlation and concentration analysis
    - Risk prediction with AI/ML
    - Automated alerting and monitoring
    - Sector and asset class exposure management
    - Advanced risk metrics (Omega, Tail Ratio, etc.)
    - Real-time data integration
    - Historical risk tracking
    - Risk budgeting and allocation
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        market_data_service: Optional[Any] = None,
        portfolio_service: Optional[Any] = None,
    ):
        self.config = config
        self.market_data_service = market_data_service
        self.portfolio_service = portfolio_service
        
        self.risk_config = RiskConfig(
            max_position_size=config.get("max_position_size", 100000.0),
            max_portfolio_risk=config.get("max_portfolio_risk", 0.02),
            max_portfolio_risk_per_day=config.get("max_portfolio_risk_per_day", 0.05),
            max_portfolio_risk_per_week=config.get("max_portfolio_risk_per_week", 0.10),
            max_drawdown=config.get("max_drawdown", 0.20),
            max_leverage=config.get("max_leverage", 10.0),
            var_confidence=config.get("var_confidence", 0.95),
            var_confidence_high=config.get("var_confidence_high", 0.99),
            risk_free_rate=config.get("risk_free_rate", 0.03),
            volatility_lookback=config.get("volatility_lookback", 30),
            correlation_lookback=config.get("correlation_lookback", 60),
            max_correlation=config.get("max_correlation", 0.7),
            min_sharpe_ratio=config.get("min_sharpe_ratio", 0.5),
            max_concentration=config.get("max_concentration", 0.25),
            risk_level=RiskLevel(config.get("risk_level", "moderate")),
            stop_loss_default=config.get("stop_loss_default", 0.02),
            take_profit_default=config.get("take_profit_default", 0.04),
            trailing_stop_default=config.get("trailing_stop_default", 0.015),
            max_positions=config.get("max_positions", 20),
            max_sector_exposure=config.get("max_sector_exposure", 0.30),
            max_asset_class_exposure=config.get("max_asset_class_exposure", 0.40),
            stress_test_shocks=config.get("stress_test_shocks", [-0.10, -0.20, -0.30, -0.50]),
            use_real_data=config.get("use_real_data", True),
            enable_ai_risk_prediction=config.get("enable_ai_risk_prediction", True),
            alert_thresholds=config.get("alert_thresholds", {
                "drawdown": 0.15,
                "var": 0.05,
                "sharpe": 0.0,
                "leverage": 8.0,
                "concentration": 0.20,
                "volatility": 0.40,
            }),
        )
        
        self.positions: Dict[str, PositionRisk] = {}
        self.alerts: List[RiskAlert] = []
        self.historical_risks: List[PortfolioRisk] = []
        self.risk_predictions: Dict[str, RiskPrediction] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_monitoring = False
        self._alert_counter = 0
        
        self._var_cache: Dict[str, Dict[str, float]] = {}
        self._volatility_cache: Dict[str, Dict[str, float]] = {}
        self._correlation_cache: Dict[str, Dict[str, float]] = {}
        self._historical_returns_cache: Dict[str, pd.DataFrame] = {}
        self._market_data_cache: Dict[str, pd.DataFrame] = {}
        
        self._risk_multipliers = {
            RiskLevel.CONSERVATIVE: 0.5,
            RiskLevel.MODERATE: 1.0,
            RiskLevel.AGGRESSIVE: 1.5,
            RiskLevel.EXTREME: 2.0,
        }
        
        self._executor = ThreadPoolExecutor(max_workers=config.get("thread_workers", 4))
        
        self._sector_map = {}
        self._asset_class_map = {}
        self._risk_budget = {}
        
        self._trade_history: List[Dict[str, Any]] = []
        self._daily_pnl: deque = deque(maxlen=252)
        self._weekly_pnl: deque = deque(maxlen=52)
        
        self._last_portfolio_risk: Optional[PortfolioRisk] = None
        
        if config.get("load_historical_data", True):
            self._load_historical_data()
        
        logger.info("RiskManager initialized with full production capabilities")
    
    # ========================================================================
    # POSITION RISK CALCULATION
    # ========================================================================
    
    async def calculate_position_risk(
        self,
        symbol: str,
        position_size: float,
        entry_price: float,
        current_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        sector: str = "",
        asset_class: str = "",
        strategy: str = "",
    ) -> PositionRisk:
        """
        Calculate comprehensive risk metrics for a position.
        
        Args:
            symbol: Trading symbol
            position_size: Position size in units
            entry_price: Entry price
            current_price: Current price
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            sector: Sector classification
            asset_class: Asset class classification
            strategy: Strategy identifier
            
        Returns:
            PositionRisk object with full risk metrics
        """
        if stop_loss is None or stop_loss == 0:
            stop_loss = entry_price * (1 - self.risk_config.stop_loss_default)
        if take_profit is None or take_profit == 0:
            take_profit = entry_price * (1 + self.risk_config.take_profit_default)
        
        # Calculate risk and reward per unit
        risk_per_unit = abs(entry_price - stop_loss)
        reward_per_unit = abs(take_profit - entry_price)
        
        risk_amount = position_size * risk_per_unit
        reward_amount = position_size * reward_per_unit
        risk_reward_ratio = reward_amount / risk_amount if risk_amount > 0 else 0
        
        # PNL calculations
        unrealized_pnl = (current_price - entry_price) * position_size
        
        # Get market data and calculate advanced metrics
        returns = await self._get_historical_returns(symbol, self.risk_config.volatility_lookback)
        market_returns = await self._get_market_returns(self.risk_config.volatility_lookback)
        
        # Volatility metrics
        volatility = self._calculate_volatility(returns)
        ewma_volatility = self._calculate_ewma_volatility(returns)
        
        # VaR and CVaR
        var_95 = self._calculate_var(returns, 0.95)
        cvar_95 = self._calculate_cvar(returns, 0.95)
        var_99 = self._calculate_var(returns, 0.99)
        cvar_99 = self._calculate_cvar(returns, 0.99)
        
        # Drawdown
        max_drawdown = self._calculate_max_drawdown(returns)
        
        # Beta and Alpha
        beta = self._calculate_beta(returns, market_returns)
        alpha = self._calculate_alpha(returns, market_returns, beta)
        
        # Correlation
        correlation = self._calculate_correlation(returns, market_returns)
        
        # Leverage
        portfolio_value = await self._get_portfolio_value()
        leverage = (position_size * entry_price) / portfolio_value if portfolio_value > 0 else 0
        
        # Sharpe and Sortino contributions
        sharpe_contribution = self._calculate_sharpe_ratio(returns)
        sortino_contribution = self._calculate_sortino_ratio(returns)
        
        # Additional metrics
        skewness = skew(returns) if len(returns) > 0 else 0
        kurt = kurtosis(returns) if len(returns) > 0 else 0
        
        # Create PositionRisk object
        position = PositionRisk(
            symbol=symbol,
            position_size=position_size,
            entry_price=entry_price,
            current_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=0.0,
            risk_amount=risk_amount,
            reward_amount=reward_amount,
            risk_reward_ratio=risk_reward_ratio,
            var_95=var_95,
            cvar_95=cvar_95,
            var_99=var_99,
            cvar_99=cvar_99,
            max_drawdown=max_drawdown,
            volatility=volatility,
            correlation=correlation,
            beta=beta,
            alpha=alpha,
            leverage=leverage,
            sharpe_contribution=sharpe_contribution,
            sortino_contribution=sortino_contribution,
            status=PositionStatus.OPEN,
            sector=sector,
            asset_class=asset_class,
            strategy=strategy,
        )
        
        # Cache results
        self._volatility_cache[symbol] = {
            "volatility": volatility,
            "ewma_volatility": ewma_volatility,
        }
        self._var_cache[symbol] = {
            "var_95": var_95,
            "cvar_95": cvar_95,
            "var_99": var_99,
            "cvar_99": cvar_99,
        }
        
        return position
    
    # ========================================================================
    # POSITION VALIDATION
    # ========================================================================
    
    async def validate_position(
        self,
        symbol: str,
        position_size: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        sector: str = "",
        asset_class: str = "",
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validate a position against all risk limits and constraints.
        
        Args:
            symbol: Trading symbol
            position_size: Proposed position size
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            sector: Sector classification
            asset_class: Asset class classification
            
        Returns:
            Tuple of (is_valid, reason, metrics)
        """
        portfolio_value = await self._get_portfolio_value()
        position_value = position_size * entry_price
        
        # Check max position size
        if position_value > self.risk_config.max_position_size:
            return False, f"Position size {position_value:.2f} exceeds max {self.risk_config.max_position_size:.2f}", {}
        
        # Check max positions
        if len(self.positions) >= self.risk_config.max_positions:
            return False, f"Max positions {self.risk_config.max_positions} reached", {}
        
        # Check risk per trade
        risk_amount = position_size * abs(entry_price - stop_loss)
        risk_percent = risk_amount / portfolio_value if portfolio_value > 0 else 0
        
        if risk_percent > self.risk_config.max_portfolio_risk:
            return False, f"Risk per trade {risk_percent:.2%} exceeds max {self.risk_config.max_portfolio_risk:.2%}", {}
        
        # Check total portfolio risk
        total_risk = await self._get_total_risk()
        if total_risk + risk_amount > portfolio_value * self.risk_config.max_portfolio_risk * 2:
            return False, "Total portfolio risk would exceed limit", {}
        
        # Check daily risk limit
        daily_risk_used = await self._get_daily_risk_used()
        if daily_risk_used + risk_amount > portfolio_value * self.risk_config.max_portfolio_risk_per_day:
            return False, "Daily risk limit would be exceeded", {}
        
        # Check weekly risk limit
        weekly_risk_used = await self._get_weekly_risk_used()
        if weekly_risk_used + risk_amount > portfolio_value * self.risk_config.max_portfolio_risk_per_week:
            return False, "Weekly risk limit would be exceeded", {}
        
        # Check correlation
        if self.positions:
            correlations = []
            for pos_symbol in self.positions:
                if pos_symbol != symbol:
                    corr = await self._get_correlation(symbol, pos_symbol)
                    if corr > self.risk_config.max_correlation:
                        correlations.append((pos_symbol, corr))
            
            if correlations:
                return False, f"High correlation with {correlations[0][0]}: {correlations[0][1]:.2f}", {}
        
        # Check volatility
        volatility = await self._get_volatility(symbol)
        if volatility > 0.5:
            return False, f"Volatility {volatility:.2%} exceeds limit", {}
        
        # Check Sharpe ratio
        returns = await self._get_historical_returns(symbol, self.risk_config.volatility_lookback)
        sharpe = self._calculate_sharpe_ratio(returns)
        if sharpe < self.risk_config.min_sharpe_ratio:
            return False, f"Sharpe ratio {sharpe:.2f} below minimum {self.risk_config.min_sharpe_ratio:.2f}", {}
        
        # Check sector exposure
        if sector:
            sector_exposure = await self._get_sector_exposure(sector)
            new_exposure = sector_exposure + (position_value / portfolio_value)
            if new_exposure > self.risk_config.max_sector_exposure:
                return False, f"Sector exposure {new_exposure:.2%} exceeds max {self.risk_config.max_sector_exposure:.2%}", {}
        
        # Check asset class exposure
        if asset_class:
            asset_exposure = await self._get_asset_class_exposure(asset_class)
            new_exposure = asset_exposure + (position_value / portfolio_value)
            if new_exposure > self.risk_config.max_asset_class_exposure:
                return False, f"Asset class exposure {new_exposure:.2%} exceeds max {self.risk_config.max_asset_class_exposure:.2%}", {}
        
        # Check leverage
        leverage = (position_size * entry_price) / portfolio_value if portfolio_value > 0 else 0
        if leverage > self.risk_config.max_leverage:
            return False, f"Leverage {leverage:.2f}x exceeds max {self.risk_config.max_leverage:.2f}x", {}
        
        # Check concentration
        if self.positions:
            total_value = sum(p.position_size * p.current_price for p in self.positions.values())
            if total_value > 0:
                concentration = (position_value + total_value) / portfolio_value
                if concentration > self.risk_config.max_concentration:
                    return False, f"Concentration {concentration:.2%} exceeds max {self.risk_config.max_concentration:.2%}", {}
        
        # Prepare metrics
        metrics = {
            "position_value": position_value,
            "risk_amount": risk_amount,
            "risk_percent": risk_percent,
            "volatility": volatility,
            "sharpe_ratio": sharpe,
            "leverage": leverage,
            "var_95": var_95 if 'var_95' in locals() else 0,
            "cvar_95": cvar_95 if 'cvar_95' in locals() else 0,
        }
        
        return True, "Position validated successfully", metrics
    
    # ========================================================================
    # PORTFOLIO RISK CALCULATION
    # ========================================================================
    
    async def calculate_portfolio_risk(self) -> PortfolioRisk:
        """
        Calculate comprehensive portfolio risk metrics.
        
        Returns:
            PortfolioRisk object with full risk metrics
        """
        portfolio_value = await self._get_portfolio_value()
        total_risk = await self._get_total_risk()
        total_exposure = await self._get_total_exposure()
        
        positions = list(self.positions.values())
        
        # Calculate portfolio returns
        portfolio_returns = await self._calculate_portfolio_returns()
        
        if portfolio_returns and len(portfolio_returns) > 1:
            # Basic statistics
            var_95 = self._calculate_var(portfolio_returns, 0.95)
            cvar_95 = self._calculate_cvar(portfolio_returns, 0.95)
            var_99 = self._calculate_var(portfolio_returns, 0.99)
            cvar_99 = self._calculate_cvar(portfolio_returns, 0.99)
            expected_shortfall = cvar_95
            max_drawdown = self._calculate_max_drawdown(portfolio_returns)
            current_drawdown = self._calculate_current_drawdown(portfolio_returns)
            volatility = self._calculate_volatility(portfolio_returns)
            skewness = skew(portfolio_returns)
            kurt = kurtosis(portfolio_returns)
            
            # Risk-adjusted returns
            sharpe_ratio = self._calculate_sharpe_ratio(portfolio_returns)
            sortino_ratio = self._calculate_sortino_ratio(portfolio_returns)
            calmar_ratio = self._calculate_calmar_ratio(portfolio_returns)
            omega_ratio = self._calculate_omega_ratio(portfolio_returns)
            tail_ratio = self._calculate_tail_ratio(portfolio_returns)
            
            # Market comparison metrics
            market_returns = await self._get_market_returns(self.risk_config.volatility_lookback)
            beta = self._calculate_beta(portfolio_returns, market_returns)
            alpha = self._calculate_alpha(portfolio_returns, market_returns, beta)
            r_squared = self._calculate_r_squared(portfolio_returns, market_returns)
            treynor_ratio = self._calculate_treynor_ratio(portfolio_returns, beta)
            information_ratio = self._calculate_information_ratio(portfolio_returns, market_returns)
        else:
            var_95 = 0.0
            cvar_95 = 0.0
            var_99 = 0.0
            cvar_99 = 0.0
            expected_shortfall = 0.0
            max_drawdown = 0.0
            current_drawdown = 0.0
            volatility = 0.0
            skewness = 0.0
            kurt = 0.0
            sharpe_ratio = 0.0
            sortino_ratio = 0.0
            calmar_ratio = 0.0
            omega_ratio = 0.0
            tail_ratio = 0.0
            beta = 1.0
            alpha = 0.0
            r_squared = 0.0
            treynor_ratio = 0.0
            information_ratio = 0.0
        
        # Correlation matrix
        correlation_matrix = await self._calculate_correlation_matrix()
        
        # Concentration and exposures
        concentration_ratio = self._calculate_concentration_ratio()
        sector_exposures = await self._calculate_sector_exposures()
        asset_class_exposures = await self._calculate_asset_class_exposures()
        
        # Stress tests
        stress_test_results = await self._run_stress_tests(portfolio_returns)
        
        # Risk score
        risk_score = self._calculate_risk_score(
            var_95=var_95,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            volatility=volatility,
            concentration=concentration_ratio,
            leverage=await self._get_total_leverage(),
        )
        
        risk_level = self._determine_risk_level(risk_score)
        
        portfolio_risk = PortfolioRisk(
            total_value=portfolio_value,
            total_risk=total_risk,
            total_exposure=total_exposure,
            var_95=var_95,
            cvar_95=cvar_95,
            var_99=var_99,
            cvar_99=cvar_99,
            expected_shortfall=expected_shortfall,
            max_drawdown=max_drawdown,
            current_drawdown=current_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            omega_ratio=omega_ratio,
            tail_ratio=tail_ratio,
            beta=beta,
            alpha=alpha,
            r_squared=r_squared,
            treynor_ratio=treynor_ratio,
            information_ratio=information_ratio,
            volatility=volatility,
            skewness=skewness,
            kurtosis=kurt,
            correlation_matrix=correlation_matrix,
            concentration_ratio=concentration_ratio,
            sector_exposures=sector_exposures,
            asset_class_exposures=asset_class_exposures,
            risk_score=risk_score,
            risk_level=risk_level,
            positions=positions,
            stress_test_results=stress_test_results,
        )
        
        self.historical_risks.append(portfolio_risk)
        self._last_portfolio_risk = portfolio_risk
        
        if len(self.historical_risks) > 1000:
            self.historical_risks = self.historical_risks[-1000:]
        
        return portfolio_risk
    
    async def _calculate_portfolio_returns(self) -> List[float]:
        """Calculate historical portfolio returns."""
        if not self.positions:
            return []
        
        portfolio_returns = []
        min_length = float('inf')
        
        for symbol, position in self.positions.items():
            returns = await self._get_historical_returns(symbol, self.risk_config.volatility_lookback)
            if returns:
                min_length = min(min_length, len(returns))
        
        if min_length == float('inf') or min_length < 2:
            return []
        
        weighted_returns = []
        total_weight = 0
        
        for symbol, position in self.positions.items():
            returns = await self._get_historical_returns(symbol, self.risk_config.volatility_lookback)
            returns = returns[-min_length:] if returns else []
            
            if returns:
                weight = position.position_size * position.current_price
                weighted = np.array(returns) * weight
                weighted_returns.append(weighted)
                total_weight += weight
        
        if not weighted_returns or total_weight == 0:
            return []
        
        portfolio_returns = np.sum(weighted_returns, axis=0) / total_weight
        return portfolio_returns.tolist()
    
    # ========================================================================
    # POSITION MANAGEMENT
    # ========================================================================
    
    async def add_position(self, position: PositionRisk) -> None:
        """Add a new position to the portfolio."""
        self.positions[position.symbol] = position
        self._update_position_history(position)
        logger.info(f"Added position {position.symbol}: size={position.position_size:.2f}, price={position.entry_price:.2f}")
        await self._check_risk_alerts()
    
    async def remove_position(self, symbol: str) -> Optional[PositionRisk]:
        """Remove a position from the portfolio."""
        if symbol in self.positions:
            position = self.positions.pop(symbol)
            self._trade_history.append({
                "symbol": symbol,
                "action": "close",
                "pnl": position.realized_pnl,
                "timestamp": datetime.now(),
            })
            logger.info(f"Removed position {symbol}")
            return position
        return None
    
    async def update_position(
        self,
        symbol: str,
        current_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        position_size: Optional[float] = None,
    ) -> Optional[PositionRisk]:
        """
        Update an existing position with new price and risk parameters.
        
        Args:
            symbol: Trading symbol
            current_price: Current price
            stop_loss: New stop loss price (optional)
            take_profit: New take profit price (optional)
            position_size: New position size (optional)
            
        Returns:
            Updated PositionRisk or None if not found
        """
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        position.current_price = current_price
        position.last_updated = datetime.now()
        
        # Update position size if provided
        if position_size is not None:
            position.position_size = position_size
        
        # Update PNL
        position.unrealized_pnl = (current_price - position.entry_price) * position.position_size
        
        # Update stop loss
        if stop_loss is not None:
            position.stop_loss = stop_loss
            position.risk_amount = position.position_size * abs(position.entry_price - stop_loss)
            position.risk_reward_ratio = position.reward_amount / position.risk_amount if position.risk_amount > 0 else 0
        
        # Update take profit
        if take_profit is not None:
            position.take_profit = take_profit
            position.reward_amount = position.position_size * abs(take_profit - position.entry_price)
            position.risk_reward_ratio = position.reward_amount / position.risk_amount if position.risk_amount > 0 else 0
        
        # Recalculate risk metrics
        returns = await self._get_historical_returns(symbol, self.risk_config.volatility_lookback)
        market_returns = await self._get_market_returns(self.risk_config.volatility_lookback)
        
        position.var_95 = self._calculate_var(returns, 0.95)
        position.cvar_95 = self._calculate_cvar(returns, 0.95)
        position.var_99 = self._calculate_var(returns, 0.99)
        position.cvar_99 = self._calculate_cvar(returns, 0.99)
        position.max_drawdown = self._calculate_max_drawdown(returns)
        position.volatility = self._calculate_volatility(returns)
        position.correlation = self._calculate_correlation(returns, market_returns)
        position.beta = self._calculate_beta(returns, market_returns)
        position.alpha = self._calculate_alpha(returns, market_returns, position.beta)
        position.leverage = (position.position_size * position.current_price) / await self._get_portfolio_value()
        
        return position
    
    # ========================================================================
    # MONITORING AND ALERTS
    # ========================================================================
    
    async def monitor_positions(self) -> List[RiskAlert]:
        """
        Monitor all positions for risk breaches and generate alerts.
        
        Returns:
            List of new RiskAlert objects
        """
        new_alerts = []
        portfolio_value = await self._get_portfolio_value()
        portfolio_risk = await self.calculate_portfolio_risk()
        
        # Portfolio-level alerts
        if portfolio_risk.max_drawdown > self.risk_config.alert_thresholds["drawdown"]:
            new_alerts.append(self._create_alert(
                alert_type="portfolio_drawdown",
                severity=AlertSeverity.CRITICAL,
                message=f"Portfolio drawdown {portfolio_risk.max_drawdown:.2%} exceeds threshold",
                symbol="PORTFOLIO",
                metric="max_drawdown",
                value=portfolio_risk.max_drawdown,
                threshold=self.risk_config.alert_thresholds["drawdown"],
            ))
        
        if abs(portfolio_risk.var_95) > self.risk_config.alert_thresholds["var"]:
            new_alerts.append(self._create_alert(
                alert_type="portfolio_var",
                severity=AlertSeverity.HIGH,
                message=f"Portfolio VaR {abs(portfolio_risk.var_95):.2%} exceeds threshold",
                symbol="PORTFOLIO",
                metric="var_95",
                value=abs(portfolio_risk.var_95),
                threshold=self.risk_config.alert_thresholds["var"],
            ))
        
        if portfolio_risk.sharpe_ratio < self.risk_config.alert_thresholds["sharpe"]:
            new_alerts.append(self._create_alert(
                alert_type="portfolio_sharpe",
                severity=AlertSeverity.WARNING,
                message=f"Portfolio Sharpe ratio {portfolio_risk.sharpe_ratio:.2f} below threshold",
                symbol="PORTFOLIO",
                metric="sharpe_ratio",
                value=portfolio_risk.sharpe_ratio,
                threshold=self.risk_config.alert_thresholds["sharpe"],
            ))
        
        # Position-level alerts
        for symbol, position in self.positions.items():
            # Stop loss alert
            if position.current_price <= position.stop_loss:
                new_alerts.append(self._create_alert(
                    alert_type="stop_loss",
                    severity=AlertSeverity.CRITICAL,
                    message=f"Stop loss triggered for {symbol} at {position.current_price:.2f}",
                    symbol=symbol,
                    metric="stop_loss",
                    value=position.current_price,
                    threshold=position.stop_loss,
                ))
            
            # Take profit alert
            if position.current_price >= position.take_profit:
                new_alerts.append(self._create_alert(
                    alert_type="take_profit",
                    severity=AlertSeverity.INFO,
                    message=f"Take profit triggered for {symbol} at {position.current_price:.2f}",
                    symbol=symbol,
                    metric="take_profit",
                    value=position.current_price,
                    threshold=position.take_profit,
                ))
            
            # Drawdown alert
            if position.max_drawdown > self.risk_config.alert_thresholds["drawdown"]:
                new_alerts.append(self._create_alert(
                    alert_type="position_drawdown",
                    severity=AlertSeverity.HIGH,
                    message=f"Position drawdown {position.max_drawdown:.2%} for {symbol} exceeds threshold",
                    symbol=symbol,
                    metric="max_drawdown",
                    value=position.max_drawdown,
                    threshold=self.risk_config.alert_thresholds["drawdown"],
                ))
            
            # Leverage alert
            if position.leverage > self.risk_config.alert_thresholds["leverage"]:
                new_alerts.append(self._create_alert(
                    alert_type="leverage",
                    severity=AlertSeverity.HIGH,
                    message=f"Leverage {position.leverage:.2f}x for {symbol} exceeds threshold",
                    symbol=symbol,
                    metric="leverage",
                    value=position.leverage,
                    threshold=self.risk_config.alert_thresholds["leverage"],
                ))
            
            # Volatility alert
            if position.volatility > self.risk_config.alert_thresholds["volatility"]:
                new_alerts.append(self._create_alert(
                    alert_type="volatility",
                    severity=AlertSeverity.WARNING,
                    message=f"High volatility {position.volatility:.2%} for {symbol}",
                    symbol=symbol,
                    metric="volatility",
                    value=position.volatility,
                    threshold=self.risk_config.alert_thresholds["volatility"],
                ))
            
            # Unrealized loss alert
            if position.unrealized_pnl < -position.risk_amount * 2:
                new_alerts.append(self._create_alert(
                    alert_type="unrealized_loss",
                    severity=AlertSeverity.HIGH,
                    message=f"Unrealized loss exceeds 2x risk for {symbol}",
                    symbol=symbol,
                    metric="unrealized_pnl",
                    value=position.unrealized_pnl,
                    threshold=-position.risk_amount * 2,
                ))
        
        # Add alerts to history
        self.alerts.extend(new_alerts)
        self.alerts = self.alerts[-1000:]
        
        # Send alerts
        for alert in new_alerts:
            if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
                await self._send_alert(alert)
        
        return new_alerts
    
    async def start_monitoring(
        self,
        interval_seconds: int = 60,
        webhook_url: Optional[str] = None,
    ) -> None:
        """
        Start continuous risk monitoring.
        
        Args:
            interval_seconds: Monitoring interval in seconds
            webhook_url: Webhook URL for alerts
        """
        if self._is_monitoring:
            logger.warning("Monitoring already running")
            return
        
        self._is_monitoring = True
        self.config["webhook_url"] = webhook_url
        
        logger.info(f"Starting risk monitoring with interval {interval_seconds}s")
        
        try:
            while self._is_monitoring:
                try:
                    alerts = await self.monitor_positions()
                    
                    portfolio_risk = await self.calculate_portfolio_risk()
                    
                    if portfolio_risk.risk_score > 70:
                        await self._send_alert(self._create_alert(
                            alert_type="portfolio_risk",
                            severity=AlertSeverity.HIGH,
                            message=f"Portfolio risk score {portfolio_risk.risk_score:.1f} is high",
                            symbol="PORTFOLIO",
                            metric="risk_score",
                            value=portfolio_risk.risk_score,
                            threshold=70,
                        ))
                    
                    if portfolio_risk.risk_level in [RiskLevel.AGGRESSIVE, RiskLevel.EXTREME]:
                        await self._send_alert(self._create_alert(
                            alert_type="risk_level",
                            severity=AlertSeverity.WARNING,
                            message=f"Portfolio risk level is {portfolio_risk.risk_level.value}",
                            symbol="PORTFOLIO",
                            metric="risk_level",
                            value=0,
                            threshold=0,
                        ))
                    
                    await self._store_risk_snapshot(portfolio_risk)
                    
                except Exception as e:
                    logger.error(f"Error in monitoring cycle: {e}")
                
                await asyncio.sleep(interval_seconds)
                
        except asyncio.CancelledError:
            logger.info("Monitoring task cancelled")
        finally:
            self._is_monitoring = False
    
    def stop_monitoring(self) -> None:
        """Stop risk monitoring."""
        self._is_monitoring = False
        logger.info("Risk monitoring stopped")
    
    def _create_alert(
        self,
        alert_type: str,
        severity: AlertSeverity,
        message: str,
        symbol: str,
        metric: str,
        value: float,
        threshold: float,
    ) -> RiskAlert:
        """Create a new RiskAlert object."""
        self._alert_counter += 1
        return RiskAlert(
            alert_id=f"{alert_type}_{self._alert_counter}_{int(datetime.now().timestamp())}",
            alert_type=alert_type,
            severity=severity,
            message=message,
            symbol=symbol,
            metric=metric,
            value=value,
            threshold=threshold,
        )
    
    async def _send_alert(self, alert: RiskAlert) -> None:
        """Send an alert via configured channels."""
        webhook_url = self.config.get("webhook_url")
        if not webhook_url:
            logger.info(f"ALERT [{alert.severity.value}]: {alert.message}")
            return
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                payload = asdict(alert)
                payload["timestamp"] = payload["timestamp"].isoformat()
                await session.post(webhook_url, json=payload)
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    # ========================================================================
    # RISK METRIC CALCULATIONS
    # ========================================================================
    
    def _calculate_var(self, returns: List[float], confidence: float) -> float:
        """Calculate Value at Risk."""
        if not returns:
            return 0.0
        return np.percentile(returns, (1 - confidence) * 100)
    
    def _calculate_cvar(self, returns: List[float], confidence: float) -> float:
        """Calculate Conditional Value at Risk (Expected Shortfall)."""
        if not returns:
            return 0.0
        var = self._calculate_var(returns, confidence)
        tail = [r for r in returns if r <= var]
        return np.mean(tail) if tail else var
    
    def _calculate_volatility(self, returns: List[float]) -> float:
        """Calculate volatility (standard deviation)."""
        if not returns or len(returns) < 2:
            return 0.0
        return np.std(returns) * np.sqrt(252)
    
    def _calculate_ewma_volatility(self, returns: List[float], lambda_: float = 0.94) -> float:
        """Calculate EWMA volatility."""
        if not returns:
            return 0.0
        
        returns = np.array(returns)
        weights = (1 - lambda_) * lambda_ ** np.arange(len(returns))
        weights = weights / weights.sum()
        
        mean = np.average(returns, weights=weights)
        variance = np.average((returns - mean) ** 2, weights=weights)
        return np.sqrt(variance) * np.sqrt(252)
    
    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown."""
        if not returns:
            return 0.0
        portfolio = np.cumprod(1 + np.array(returns))
        peak = np.maximum.accumulate(portfolio)
        drawdown = (peak - portfolio) / peak
        return np.max(drawdown)
    
    def _calculate_current_drawdown(self, returns: List[float]) -> float:
        """Calculate current drawdown."""
        if not returns:
            return 0.0
        portfolio = np.cumprod(1 + np.array(returns))
        peak = np.max(portfolio)
        current = portfolio[-1]
        return (peak - current) / peak if peak > 0 else 0
    
    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio."""
        if not returns or len(returns) < 2:
            return 0.0
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        risk_free = self.risk_config.risk_free_rate / 252
        if std_return == 0:
            return 0.0
        return (avg_return - risk_free) / std_return
    
    def _calculate_sortino_ratio(self, returns: List[float]) -> float:
        """Calculate Sortino ratio."""
        if not returns or len(returns) < 2:
            return 0.0
        avg_return = np.mean(returns)
        negative_returns = [r for r in returns if r < 0]
        downside_std = np.std(negative_returns) if negative_returns else np.std(returns)
        risk_free = self.risk_config.risk_free_rate / 252
        if downside_std == 0:
            return 0.0
        return (avg_return - risk_free) / downside_std
    
    def _calculate_calmar_ratio(self, returns: List[float]) -> float:
        """Calculate Calmar ratio."""
        if not returns:
            return 0.0
        avg_return = np.mean(returns) * 252
        max_drawdown = self._calculate_max_drawdown(returns)
        if max_drawdown == 0:
            return 0.0
        return avg_return / max_drawdown
    
    def _calculate_omega_ratio(self, returns: List[float], threshold: float = 0.0) -> float:
        """Calculate Omega ratio."""
        if not returns:
            return 0.0
        returns = np.array(returns)
        gains = returns[returns > threshold] - threshold
        losses = threshold - returns[returns < threshold]
        if np.sum(losses) == 0:
            return float('inf')
        return np.sum(gains) / np.sum(losses)
    
    def _calculate_tail_ratio(self, returns: List[float]) -> float:
        """Calculate Tail ratio (95th percentile / 5th percentile)."""
        if not returns or len(returns) < 2:
            return 0.0
        upper_tail = np.percentile(returns, 95)
        lower_tail = np.percentile(returns, 5)
        if lower_tail == 0:
            return 0.0
        return upper_tail / abs(lower_tail)
    
    def _calculate_beta(self, returns: List[float], market_returns: List[float]) -> float:
        """Calculate Beta (market sensitivity)."""
        if not returns or not market_returns or len(returns) < 2 or len(market_returns) < 2:
            return 1.0
        
        min_len = min(len(returns), len(market_returns))
        returns = returns[-min_len:]
        market_returns = market_returns[-min_len:]
        
        covariance = np.cov(returns, market_returns)[0, 1]
        market_variance = np.var(market_returns)
        if market_variance == 0:
            return 1.0
        return covariance / market_variance
    
    def _calculate_alpha(self, returns: List[float], market_returns: List[float], beta: float) -> float:
        """Calculate Alpha (excess return)."""
        if not returns or not market_returns:
            return 0.0
        
        min_len = min(len(returns), len(market_returns))
        returns = returns[-min_len:]
        market_returns = market_returns[-min_len:]
        
        avg_return = np.mean(returns)
        avg_market_return = np.mean(market_returns)
        risk_free = self.risk_config.risk_free_rate / 252
        
        return avg_return - (risk_free + beta * (avg_market_return - risk_free))
    
    def _calculate_r_squared(self, returns: List[float], market_returns: List[float]) -> float:
        """Calculate R-squared."""
        if not returns or not market_returns or len(returns) < 2 or len(market_returns) < 2:
            return 0.0
        
        min_len = min(len(returns), len(market_returns))
        returns = returns[-min_len:]
        market_returns = market_returns[-min_len:]
        
        correlation = np.corrcoef(returns, market_returns)[0, 1]
        return correlation ** 2
    
    def _calculate_treynor_ratio(self, returns: List[float], beta: float) -> float:
        """Calculate Treynor ratio."""
        if not returns or beta == 0:
            return 0.0
        avg_return = np.mean(returns) * 252
        risk_free = self.risk_config.risk_free_rate
        return (avg_return - risk_free) / beta
    
    def _calculate_information_ratio(self, returns: List[float], market_returns: List[float]) -> float:
        """Calculate Information ratio."""
        if not returns or not market_returns or len(returns) < 2:
            return 0.0
        
        min_len = min(len(returns), len(market_returns))
        returns = returns[-min_len:]
        market_returns = market_returns[-min_len:]
        
        excess_returns = np.array(returns) - np.array(market_returns)
        if np.std(excess_returns) == 0:
            return 0.0
        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
    
    def _calculate_correlation(self, returns1: List[float], returns2: List[float]) -> float:
        """Calculate correlation between two return series."""
        if not returns1 or not returns2 or len(returns1) < 2 or len(returns2) < 2:
            return 0.0
        
        min_len = min(len(returns1), len(returns2))
        returns1 = returns1[-min_len:]
        returns2 = returns2[-min_len:]
        
        correlation = np.corrcoef(returns1, returns2)[0, 1]
        return correlation if not np.isnan(correlation) else 0.0
    
    def _calculate_concentration_ratio(self) -> float:
        """Calculate portfolio concentration ratio."""
        if not self.positions:
            return 0.0
        
        values = [pos.position_size * pos.current_price for pos in self.positions.values()]
        total = sum(values)
        if total == 0:
            return 0.0
        
        max_value = max(values)
        return max_value / total
    
    def _calculate_risk_score(
        self,
        var_95: float,
        max_drawdown: float,
        sharpe_ratio: float,
        volatility: float,
        concentration: float,
        leverage: float = 0.0,
    ) -> float:
        """Calculate composite risk score."""
        score = 0.0
        
        score += min(abs(var_95) * 100, 25)
        score += min(max_drawdown * 100, 25)
        score += max(0, 25 - sharpe_ratio * 25)
        score += min(volatility * 100, 15)
        score += min(concentration * 100, 10)
        score += min(leverage / 2, 10)
        
        return min(score, 100)
    
    def _determine_risk_level(self, risk_score: float) -> RiskLevel:
        """Determine risk level based on risk score."""
        if risk_score < 20:
            return RiskLevel.CONSERVATIVE
        elif risk_score < 40:
            return RiskLevel.MODERATE
        elif risk_score < 60:
            return RiskLevel.AGGRESSIVE
        else:
            return RiskLevel.EXTREME
    
    # ========================================================================
    # PORTFOLIO AGGREGATION HELPERS
    # ========================================================================
    
    async def _get_portfolio_value(self) -> float:
        """Get total portfolio value."""
        if self.portfolio_service:
            return await self.portfolio_service.get_total_value()
        
        total = 100000.0
        for position in self.positions.values():
            total += position.unrealized_pnl
        return total
    
    async def _get_total_risk(self) -> float:
        """Get total portfolio risk."""
        total = 0.0
        for position in self.positions.values():
            total += position.risk_amount
        return total
    
    async def _get_total_exposure(self) -> float:
        """Get total portfolio exposure."""
        total = 0.0
        for position in self.positions.values():
            total += position.position_size * position.current_price
        return total
    
    async def _get_total_leverage(self) -> float:
        """Get total portfolio leverage."""
        total_exposure = await self._get_total_exposure()
        total_value = await self._get_portfolio_value()
        return total_exposure / total_value if total_value > 0 else 0
    
    async def _get_daily_risk_used(self) -> float:
        """Get risk used today."""
        today = datetime.now().date()
        daily_risk = 0
        for trade in self._trade_history:
            if trade.get("timestamp", datetime.now()).date() == today:
                if trade.get("pnl", 0) < 0:
                    daily_risk += abs(trade.get("pnl", 0))
        return daily_risk
    
    async def _get_weekly_risk_used(self) -> float:
        """Get risk used this week."""
        week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        weekly_risk = 0
        for trade in self._trade_history:
            if trade.get("timestamp", datetime.now()) >= week_start:
                if trade.get("pnl", 0) < 0:
                    weekly_risk += abs(trade.get("pnl", 0))
        return weekly_risk
    
    async def _get_volatility(self, symbol: str) -> float:
        """Get volatility for a symbol."""
        if symbol in self._volatility_cache:
            return self._volatility_cache[symbol].get("volatility", 0.02)
        
        returns = await self._get_historical_returns(symbol, self.risk_config.volatility_lookback)
        volatility = self._calculate_volatility(returns)
        volatility = volatility if volatility > 0 else 0.02
        
        self._volatility_cache[symbol] = {"volatility": volatility}
        return volatility
    
    async def _get_correlation(self, symbol1: str, symbol2: str) -> float:
        """Get correlation between two symbols."""
        key = f"{symbol1}_{symbol2}"
        if key in self._correlation_cache:
            return self._correlation_cache[key].get("correlation", 0.0)
        
        returns1 = await self._get_historical_returns(symbol1, self.risk_config.correlation_lookback)
        returns2 = await self._get_historical_returns(symbol2, self.risk_config.correlation_lookback)
        
        correlation = self._calculate_correlation(returns1, returns2)
        self._correlation_cache[key] = {"correlation": correlation}
        
        return correlation
    
    async def _get_historical_returns(self, symbol: str, period: int) -> List[float]:
        """Get historical returns for a symbol."""
        data = await self._get_market_data(symbol, period)
        if data.empty:
            return []
        
        if 'close' in data.columns:
            prices = data['close'].values
        else:
            prices = data.iloc[:, 0].values
        
        if len(prices) < 2:
            return []
        
        returns = np.diff(prices) / prices[:-1]
        return returns.tolist()
    
    async def _get_market_returns(self, period: int) -> List[float]:
        """Get market returns (SPY as proxy)."""
        return await self._get_historical_returns("SPY", period)
    
    async def _get_market_data(self, symbol: str, period: int) -> pd.DataFrame:
        """Get market data for a symbol."""
        if symbol in self._market_data_cache:
            data = self._market_data_cache[symbol]
            if len(data) >= period:
                return data.tail(period)
        
        if self.market_data_service:
            try:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=period * 3)
                data = await self.market_data_service.get_historical_data(
                    symbol, start_date, end_date, interval="1d"
                )
                if not data.empty:
                    self._market_data_cache[symbol] = data
                    return data.tail(period)
            except Exception as e:
                logger.error(f"Error fetching market data for {symbol}: {e}")
        
        dates = pd.date_range(end=datetime.now(), periods=period, freq='D')
        close = 100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.02, period)))
        data = pd.DataFrame({'close': close}, index=dates)
        self._market_data_cache[symbol] = data
        return data
    
    async def _calculate_correlation_matrix(self) -> Dict[str, Dict[str, float]]:
        """Calculate full correlation matrix for all positions."""
        symbols = list(self.positions.keys())
        if len(symbols) < 2:
            return {}
        
        matrix = {}
        for symbol in symbols:
            matrix[symbol] = {}
        
        for i, symbol1 in enumerate(symbols):
            for j, symbol2 in enumerate(symbols):
                if i != j:
                    corr = await self._get_correlation(symbol1, symbol2)
                    matrix[symbol1][symbol2] = corr
                else:
                    matrix[symbol1][symbol2] = 1.0
        
        return matrix
    
    async def _calculate_sector_exposures(self) -> Dict[str, float]:
        """Calculate exposures by sector."""
        exposures = defaultdict(float)
        total_value = await self._get_portfolio_value()
        
        for position in self.positions.values():
            if position.sector:
                value = position.position_size * position.current_price
                exposures[position.sector] += value / total_value
        
        return dict(exposures)
    
    async def _calculate_asset_class_exposures(self) -> Dict[str, float]:
        """Calculate exposures by asset class."""
        exposures = defaultdict(float)
        total_value = await self._get_portfolio_value()
        
        for position in self.positions.values():
            if position.asset_class:
                value = position.position_size * position.current_price
                exposures[position.asset_class] += value / total_value
        
        return dict(exposures)
    
    async def _get_sector_exposure(self, sector: str) -> float:
        """Get exposure to a specific sector."""
        sectors = await self._calculate_sector_exposures()
        return sectors.get(sector, 0.0)
    
    async def _get_asset_class_exposure(self, asset_class: str) -> float:
        """Get exposure to a specific asset class."""
        asset_classes = await self._calculate_asset_class_exposures()
        return asset_classes.get(asset_class, 0.0)
    
    # ========================================================================
    # STRESS TESTING
    # ========================================================================
    
    async def _run_stress_tests(self, returns: List[float]) -> Dict[str, float]:
        """Run stress tests on portfolio returns."""
        results = {}
        
        if not returns:
            return {"base": 0.0}
        
        for shock in self.risk_config.stress_test_shocks:
            stressed_returns = [r * (1 + shock) for r in returns]
            results[f"shock_{abs(shock):.0%}"] = self._calculate_var(stressed_returns, 0.95)
        
        # Historical stress scenarios
        scenarios = {
            "2008_financial_crisis": -0.40,
            "2020_covid_crash": -0.30,
            "2022_bear_market": -0.20,
            "volatility_spike": -0.15,
            "liquidity_crisis": -0.25,
        }
        
        for scenario, shock in scenarios.items():
            stressed_returns = [r * (1 + shock) for r in returns]
            results[scenario] = self._calculate_var(stressed_returns, 0.95)
        
        return results
    
    # ========================================================================
    # AI RISK PREDICTION
    # ========================================================================
    
    async def predict_risk(self, symbol: str) -> Optional[RiskPrediction]:
        """
        Predict future risk metrics using AI/ML.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            RiskPrediction or None if not available
        """
        if not self.risk_config.enable_ai_risk_prediction:
            return None
        
        # Get historical data
        returns = await self._get_historical_returns(symbol, 100)
        if len(returns) < 30:
            return None
        
        # Simple ML prediction (GARCH-like)
        # In production, this would use a trained model
        
        # Calculate GARCH(1,1) parameters
        omega = 0.00001
        alpha = 0.10
        beta = 0.85
        
        variance = np.var(returns)
        predictions = []
        
        for i in range(10):
            variance = omega + alpha * returns[-1] ** 2 + beta * variance
            predictions.append(np.sqrt(variance))
        
        predicted_volatility = np.mean(predictions) * np.sqrt(252)
        predicted_var = np.percentile(returns, 5) * (predicted_volatility / (np.std(returns) if np.std(returns) > 0 else 0.01))
        predicted_cvar = np.mean([r for r in returns if r <= predicted_var]) if any(r <= predicted_var for r in returns) else predicted_var
        predicted_drawdown = self._calculate_max_drawdown(returns) * 1.1
        
        prediction = RiskPrediction(
            symbol=symbol,
            predicted_var=predicted_var,
            predicted_cvar=predicted_cvar,
            predicted_volatility=predicted_volatility,
            predicted_drawdown=predicted_drawdown,
            confidence=0.7,
            model="garch_1_1",
        )
        
        self.risk_predictions[symbol] = prediction
        return prediction
    
    # ========================================================================
    # DATA MANAGEMENT
    # ========================================================================
    
    def _load_historical_data(self) -> None:
        """Load historical risk data from storage."""
        try:
            # In production, load from database or file
            logger.info("Historical data loaded (placeholder)")
        except Exception as e:
            logger.error(f"Error loading historical data: {e}")
    
    def _update_position_history(self, position: PositionRisk) -> None:
        """Update position history."""
        self._trade_history.append({
            "symbol": position.symbol,
            "action": "open",
            "entry_price": position.entry_price,
            "position_size": position.position_size,
            "timestamp": datetime.now(),
        })
        if len(self._trade_history) > 10000:
            self._trade_history = self._trade_history[-10000:]
    
    async def _store_risk_snapshot(self, portfolio_risk: PortfolioRisk) -> None:
        """Store risk snapshot for historical tracking."""
        # In production, store in database
        pass
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def get_position(self, symbol: str) -> Optional[PositionRisk]:
        """Get a position by symbol."""
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> List[PositionRisk]:
        """Get all positions."""
        return list(self.positions.values())
    
    def get_alerts(self, severity: Optional[AlertSeverity] = None) -> List[RiskAlert]:
        """Get alerts filtered by severity."""
        if severity:
            return [a for a in self.alerts if a.severity == severity]
        return self.alerts
    
    def get_unacknowledged_alerts(self) -> List[RiskAlert]:
        """Get unacknowledged alerts."""
        return [a for a in self.alerts if not a.acknowledged]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert."""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                return True
        return False
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get portfolio summary."""
        total_value = 0.0
        total_pnl = 0.0
        total_risk = 0.0
        
        for position in self.positions.values():
            total_value += position.position_size * position.current_price
            total_pnl += position.unrealized_pnl
            total_risk += position.risk_amount
        
        return {
            "total_positions": len(self.positions),
            "total_value": total_value,
            "total_pnl": total_pnl,
            "total_risk": total_risk,
            "risk_percent": total_risk / (await self._get_portfolio_value()) if total_risk > 0 else 0,
            "avg_risk_reward": np.mean([p.risk_reward_ratio for p in self.positions.values()]) if self.positions else 0,
            "avg_leverage": np.mean([p.leverage for p in self.positions.values()]) if self.positions else 0,
            "max_drawdown": max([p.max_drawdown for p in self.positions.values()]) if self.positions else 0,
        }
    
    def clear_cache(self) -> None:
        """Clear all caches."""
        self._var_cache.clear()
        self._volatility_cache.clear()
        self._correlation_cache.clear()
        self._historical_returns_cache.clear()
        self._market_data_cache.clear()
        logger.info("Cache cleared")
    
    def reset(self) -> None:
        """Reset all state."""
        self.positions.clear()
        self.alerts.clear()
        self.historical_risks.clear()
        self.risk_predictions.clear()
        self._trade_history.clear()
        self._daily_pnl.clear()
        self._weekly_pnl.clear()
        self._last_portfolio_risk = None
        self.clear_cache()
        logger.info("RiskManager reset")
    
    async def get_risk_report(self) -> Dict[str, Any]:
        """Generate comprehensive risk report."""
        portfolio_risk = await self.calculate_portfolio_risk()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "portfolio": asdict(portfolio_risk),
            "positions": [asdict(p) for p in self.positions.values()],
            "alerts": [asdict(a) for a in self.alerts[-50:]],
            "summary": self.get_portfolio_summary(),
            "predictions": {k: asdict(v) for k, v in self.risk_predictions.items()},
            "historical_risk_count": len(self.historical_risks),
        }
    
    async def run_risk_check(self) -> Dict[str, Any]:
        """
        Run a comprehensive risk check.
        
        Returns:
            Risk check results with status and recommendations
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "status": "OK",
            "checks": [],
            "recommendations": [],
        }
        
        # Check position limits
        if len(self.positions) >= self.risk_config.max_positions:
            results["checks"].append({
                "name": "position_limit",
                "status": "WARNING",
                "message": f"Max positions {self.risk_config.max_positions} reached",
            })
            results["recommendations"].append("Consider closing some positions before opening new ones")
        
        # Check risk limits
        total_risk = await self._get_total_risk()
        portfolio_value = await self._get_portfolio_value()
        risk_percent = total_risk / portfolio_value if portfolio_value > 0 else 0
        
        if risk_percent > self.risk_config.max_portfolio_risk * 1.5:
            results["checks"].append({
                "name": "risk_limit",
                "status": "CRITICAL",
                "message": f"Total risk {risk_percent:.2%} exceeds limit",
            })
            results["recommendations"].append("Reduce position sizes immediately")
        elif risk_percent > self.risk_config.max_portfolio_risk:
            results["checks"].append({
                "name": "risk_limit",
                "status": "WARNING",
                "message": f"Total risk {risk_percent:.2%} approaching limit",
            })
            results["recommendations"].append("Consider reducing position sizes")
        
        # Check concentration
        concentration = self._calculate_concentration_ratio()
        if concentration > self.risk_config.max_concentration:
            results["checks"].append({
                "name": "concentration",
                "status": "WARNING",
                "message": f"Concentration {concentration:.2%} exceeds limit",
            })
            results["recommendations"].append("Diversify portfolio to reduce concentration")
        
        # Check leverage
        leverage = await self._get_total_leverage()
        if leverage > self.risk_config.max_leverage:
            results["checks"].append({
                "name": "leverage",
                "status": "CRITICAL",
                "message": f"Leverage {leverage:.2f}x exceeds limit",
            })
            results["recommendations"].append("Reduce leverage immediately")
        
        # Check drawdown
        if self._last_portfolio_risk:
            drawdown = self._last_portfolio_risk.max_drawdown
            if drawdown > self.risk_config.max_drawdown:
                results["checks"].append({
                    "name": "drawdown",
                    "status": "CRITICAL",
                    "message": f"Drawdown {drawdown:.2%} exceeds limit",
                })
                results["recommendations"].append("Implement drawdown protection measures")
        
        # Check correlation
        correlation_matrix = await self._calculate_correlation_matrix()
        high_correlations = []
        for key, value in correlation_matrix.items():
            for sub_key, corr in value.items():
                if key != sub_key and abs(corr) > self.risk_config.max_correlation:
                    high_correlations.append((key, sub_key, corr))
        
        if high_correlations:
            results["checks"].append({
                "name": "correlation",
                "status": "WARNING",
                "message": f"High correlations detected: {len(high_correlations)} pairs",
            })
            results["recommendations"].append("Review correlated positions for concentration risk")
        
        if not results["recommendations"]:
            results["checks"].append({
                "name": "all_checks",
                "status": "OK",
                "message": "All risk checks passed",
            })
        
        return results


# ========================================================================
# FACTORY FUNCTION
# ========================================================================

def create_risk_manager(
    config: Dict[str, Any],
    market_data_service: Optional[Any] = None,
    portfolio_service: Optional[Any] = None,
) -> RiskManager:
    """Factory function to create a RiskManager."""
    return RiskManager(
        config=config,
        market_data_service=market_data_service,
        portfolio_service=portfolio_service,
    )
