# trading/bots/arbitrage_bot/models/profit.py
# NEXUS AI TRADING SYSTEM - PROFIT MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for profit calculation, tracking,
# analysis, and reporting across trades, strategies, and portfolios.
# ====================================================================================

"""
NEXUS Arbitrage Bot Profit Models

This module provides comprehensive data models for:
- Profit and loss (PnL) calculation
- Profit tracking and analytics
- Performance metrics and KPIs
- Profit attribution analysis
- Strategy profitability
- Trade-level profit calculation
- Realized and unrealized PnL
- Profit forecasting and projection
- Tax-related profit tracking
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from uuid import UUID, uuid4
import json
import math
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class ProfitType(str, Enum):
    """Types of profit calculations."""
    GROSS = "gross"                      # Gross profit (before fees)
    NET = "net"                          # Net profit (after fees)
    REALIZED = "realized"                # Realized profit
    UNREALIZED = "unrealized"            # Unrealized profit
    TOTAL = "total"                      # Total profit (realized + unrealized)
    DAILY = "daily"                      # Daily profit
    WEEKLY = "weekly"                    # Weekly profit
    MONTHLY = "monthly"                  # Monthly profit
    YEARLY = "yearly"                    # Yearly profit
    RUNNING = "running"                  # Running profit
    CUMULATIVE = "cumulative"            # Cumulative profit


class ProfitCurrency(str, Enum):
    """Currencies for profit calculation."""
    USDT = "USDT"
    USDC = "USDC"
    BUSD = "BUSD"
    DAI = "DAI"
    BTC = "BTC"
    ETH = "ETH"
    BNB = "BNB"
    NATIVE = "native"                    # Exchange native currency


class ProfitAttributionType(str, Enum):
    """Types of profit attribution."""
    STRATEGY = "strategy"                # Profit by strategy
    EXCHANGE = "exchange"                # Profit by exchange
    SYMBOL = "symbol"                    # Profit by symbol
    TRADE = "trade"                      # Profit by trade
    POSITION = "position"                # Profit by position
    PORTFOLIO = "portfolio"              # Profit by portfolio
    DAY = "day"                          # Profit by day
    HOUR = "hour"                        # Profit by hour


class PerformanceMetric(str, Enum):
    """Performance metrics for evaluation."""
    SHARPE_RATIO = "sharpe_ratio"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"
    OMEGA_RATIO = "omega_ratio"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    EXPECTED_VALUE = "expected_value"
    AVERAGE_WIN = "average_win"
    AVERAGE_LOSS = "average_loss"
    MAX_DRAWDOWN = "max_drawdown"
    RECOVERY_FACTOR = "recovery_factor"
    RETURN_ON_INVESTMENT = "roi"
    RETURN_ON_EQUITY = "roe"
    ANNUALIZED_RETURN = "annualized_return"


# ====================================================================================
# PROFIT CALCULATION MODELS
# ====================================================================================

@dataclass
class ProfitCalculation:
    """
    Profit calculation for a single trade or position.
    """
    # Core fields
    calculation_id: str = field(default_factory=lambda: str(uuid4()))
    reference_id: str = ""               # Trade ID, Position ID, etc.
    reference_type: str = ""             # trade, position, strategy
    
    # Input values
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: float = 0.0
    side: str = "long"                   # long, short
    
    # Costs
    entry_fee: float = 0.0
    exit_fee: float = 0.0
    funding_cost: float = 0.0
    gas_cost: float = 0.0
    slippage_cost: float = 0.0
    other_costs: float = 0.0
    total_costs: float = 0.0
    
    # Profit
    gross_profit: float = 0.0
    net_profit: float = 0.0
    profit_percentage: float = 0.0
    profit_percentage_annualized: float = 0.0
    
    # Returns
    return_on_investment: float = 0.0
    return_on_equity: float = 0.0
    
    # Margin/leverage
    margin_used: float = 0.0
    leverage: int = 1
    
    # Timestamps
    entry_time: datetime = field(default_factory=datetime.utcnow)
    exit_time: Optional[datetime] = None
    calculated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Currency
    currency: ProfitCurrency = ProfitCurrency.USDT
    
    # Attribution
    strategy: str = ""
    exchange: str = ""
    symbol: str = ""
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate profit metrics."""
        self._calculate_profit()
        
    def _calculate_profit(self) -> None:
        """Calculate all profit metrics."""
        # Gross profit
        if self.side == "long":
            self.gross_profit = (self.exit_price - self.entry_price) * self.quantity
        else:
            self.gross_profit = (self.entry_price - self.exit_price) * self.quantity
            
        # Total costs
        self.total_costs = self.entry_fee + self.exit_fee + self.funding_cost + self.gas_cost + self.slippage_cost + self.other_costs
        
        # Net profit
        self.net_profit = self.gross_profit - self.total_costs
        
        # Profit percentage
        entry_value = self.entry_price * self.quantity
        if entry_value > 0:
            self.profit_percentage = (self.net_profit / entry_value) * 100
            
        # Annualized profit percentage
        if self.entry_time and self.exit_time:
            days = (self.exit_time - self.entry_time).total_seconds() / (24 * 3600)
            if days > 0:
                self.profit_percentage_annualized = self.profit_percentage * (365 / days)
                
        # ROI (Return on Investment)
        total_invested = entry_value + self.total_costs
        if total_invested > 0:
            self.return_on_investment = (self.net_profit / total_invested) * 100
            
        # ROE (Return on Equity) - for leveraged trades
        if self.margin_used > 0:
            self.return_on_equity = (self.net_profit / self.margin_used) * 100
        else:
            self.return_on_equity = self.return_on_investment
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "calculation_id": self.calculation_id,
            "reference_id": self.reference_id,
            "reference_type": self.reference_type,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "side": self.side,
            "entry_fee": self.entry_fee,
            "exit_fee": self.exit_fee,
            "funding_cost": self.funding_cost,
            "gas_cost": self.gas_cost,
            "slippage_cost": self.slippage_cost,
            "other_costs": self.other_costs,
            "total_costs": self.total_costs,
            "gross_profit": self.gross_profit,
            "net_profit": self.net_profit,
            "profit_percentage": self.profit_percentage,
            "profit_percentage_annualized": self.profit_percentage_annualized,
            "return_on_investment": self.return_on_investment,
            "return_on_equity": self.return_on_equity,
            "margin_used": self.margin_used,
            "leverage": self.leverage,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "calculated_at": self.calculated_at.isoformat(),
            "currency": self.currency.value if self.currency else None,
            "strategy": self.strategy,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfitCalculation":
        """Create from dictionary."""
        calc = cls(
            calculation_id=data.get("calculation_id", str(uuid4())),
            reference_id=data.get("reference_id", ""),
            reference_type=data.get("reference_type", ""),
            entry_price=data.get("entry_price", 0.0),
            exit_price=data.get("exit_price", 0.0),
            quantity=data.get("quantity", 0.0),
            side=data.get("side", "long"),
            entry_fee=data.get("entry_fee", 0.0),
            exit_fee=data.get("exit_fee", 0.0),
            funding_cost=data.get("funding_cost", 0.0),
            gas_cost=data.get("gas_cost", 0.0),
            slippage_cost=data.get("slippage_cost", 0.0),
            other_costs=data.get("other_costs", 0.0),
            total_costs=data.get("total_costs", 0.0),
            gross_profit=data.get("gross_profit", 0.0),
            net_profit=data.get("net_profit", 0.0),
            profit_percentage=data.get("profit_percentage", 0.0),
            profit_percentage_annualized=data.get("profit_percentage_annualized", 0.0),
            return_on_investment=data.get("return_on_investment", 0.0),
            return_on_equity=data.get("return_on_equity", 0.0),
            margin_used=data.get("margin_used", 0.0),
            leverage=data.get("leverage", 1),
            currency=ProfitCurrency(data["currency"]) if data.get("currency") else ProfitCurrency.USDT,
            strategy=data.get("strategy", ""),
            exchange=data.get("exchange", ""),
            symbol=data.get("symbol", ""),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("entry_time"):
            calc.entry_time = datetime.fromisoformat(data["entry_time"])
        if data.get("exit_time"):
            calc.exit_time = datetime.fromisoformat(data["exit_time"])
        if data.get("calculated_at"):
            calc.calculated_at = datetime.fromisoformat(data["calculated_at"])
            
        calc.__post_init__()
        return calc
        
    def is_profitable(self) -> bool:
        """Check if profit is positive."""
        return self.net_profit > 0
        
    def get_risk_reward_ratio(self) -> float:
        """
        Calculate risk-reward ratio.
        
        Returns:
            Risk-reward ratio
        """
        if self.total_costs == 0:
            return 0.0
        return self.net_profit / self.total_costs


# ====================================================================================
# PROFIT SUMMARY MODELS
# ====================================================================================

@dataclass
class ProfitSummary:
    """
    Summary of profits across trades, strategies, or time periods.
    """
    # Core fields
    summary_id: str = field(default_factory=lambda: str(uuid4()))
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    
    # Profit totals
    total_gross_profit: float = 0.0
    total_net_profit: float = 0.0
    total_realized_profit: float = 0.0
    total_unrealized_profit: float = 0.0
    total_fees: float = 0.0
    total_costs: float = 0.0
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    
    # Performance metrics
    profit_factor: float = 0.0
    expected_value: float = 0.0
    average_return: float = 0.0
    total_return: float = 0.0
    
    # Attribution
    profit_by_strategy: Dict[str, float] = field(default_factory=dict)
    profit_by_exchange: Dict[str, float] = field(default_factory=dict)
    profit_by_symbol: Dict[str, float] = field(default_factory=dict)
    profit_by_day: Dict[str, float] = field(default_factory=dict)
    
    # Consecutive streaks
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    current_consecutive_wins: int = 0
    current_consecutive_losses: int = 0
    
    # Drawdown
    max_drawdown: float = 0.0
    max_drawdown_percentage: float = 0.0
    max_drawdown_duration_days: int = 0
    current_drawdown: float = 0.0
    current_drawdown_percentage: float = 0.0
    
    # Currency
    currency: ProfitCurrency = ProfitCurrency.USDT
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate derived metrics."""
        self._calculate_metrics()
        
    def _calculate_metrics(self) -> None:
        """Calculate all derived metrics."""
        # Win rate
        if self.total_trades > 0:
            self.win_rate = (self.winning_trades / self.total_trades) * 100
            
        # Average win/loss
        if self.winning_trades > 0:
            self.avg_win = self.total_gross_profit / self.winning_trades
        if self.losing_trades > 0:
            self.avg_loss = abs(self.total_net_profit - self.total_gross_profit) / self.losing_trades
            
        # Profit factor
        gross_loss = self.total_gross_profit - self.total_net_profit
        if gross_loss > 0:
            self.profit_factor = self.total_gross_profit / gross_loss
        else:
            self.profit_factor = float('inf')
            
        # Expected value
        if self.total_trades > 0:
            self.expected_value = self.total_net_profit / self.total_trades
            
        # Total return
        if self.total_trades > 0:
            self.total_return = (self.total_net_profit / self.total_trades) * 100
            
        # Max drawdown percentage
        if self.max_drawdown > 0 and self.total_gross_profit > 0:
            self.max_drawdown_percentage = (self.max_drawdown / self.total_gross_profit) * 100
            
        # Current drawdown
        peak = max(self.profit_by_day.values()) if self.profit_by_day else 0
        if peak > 0:
            self.current_drawdown = peak - self.total_net_profit
            self.current_drawdown_percentage = (self.current_drawdown / peak) * 100
            
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "summary_id": self.summary_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_gross_profit": self.total_gross_profit,
            "total_net_profit": self.total_net_profit,
            "total_realized_profit": self.total_realized_profit,
            "total_unrealized_profit": self.total_unrealized_profit,
            "total_fees": self.total_fees,
            "total_costs": self.total_costs,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "largest_win": self.largest_win,
            "largest_loss": self.largest_loss,
            "profit_factor": self.profit_factor,
            "expected_value": self.expected_value,
            "average_return": self.average_return,
            "total_return": self.total_return,
            "profit_by_strategy": self.profit_by_strategy,
            "profit_by_exchange": self.profit_by_exchange,
            "profit_by_symbol": self.profit_by_symbol,
            "profit_by_day": self.profit_by_day,
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "current_consecutive_wins": self.current_consecutive_wins,
            "current_consecutive_losses": self.current_consecutive_losses,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_percentage": self.max_drawdown_percentage,
            "max_drawdown_duration_days": self.max_drawdown_duration_days,
            "current_drawdown": self.current_drawdown,
            "current_drawdown_percentage": self.current_drawdown_percentage,
            "currency": self.currency.value if self.currency else None,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfitSummary":
        """Create from dictionary."""
        summary = cls(
            summary_id=data.get("summary_id", str(uuid4())),
            period_start=datetime.fromisoformat(data["period_start"]) if data.get("period_start") else datetime.utcnow(),
            period_end=datetime.fromisoformat(data["period_end"]) if data.get("period_end") else datetime.utcnow(),
            total_gross_profit=data.get("total_gross_profit", 0.0),
            total_net_profit=data.get("total_net_profit", 0.0),
            total_realized_profit=data.get("total_realized_profit", 0.0),
            total_unrealized_profit=data.get("total_unrealized_profit", 0.0),
            total_fees=data.get("total_fees", 0.0),
            total_costs=data.get("total_costs", 0.0),
            total_trades=data.get("total_trades", 0),
            winning_trades=data.get("winning_trades", 0),
            losing_trades=data.get("losing_trades", 0),
            largest_win=data.get("largest_win", 0.0),
            largest_loss=data.get("largest_loss", 0.0),
            profit_by_strategy=data.get("profit_by_strategy", {}),
            profit_by_exchange=data.get("profit_by_exchange", {}),
            profit_by_symbol=data.get("profit_by_symbol", {}),
            profit_by_day=data.get("profit_by_day", {}),
            max_consecutive_wins=data.get("max_consecutive_wins", 0),
            max_consecutive_losses=data.get("max_consecutive_losses", 0),
            current_consecutive_wins=data.get("current_consecutive_wins", 0),
            current_consecutive_losses=data.get("current_consecutive_losses", 0),
            max_drawdown=data.get("max_drawdown", 0.0),
            max_drawdown_duration_days=data.get("max_drawdown_duration_days", 0),
            current_drawdown=data.get("current_drawdown", 0.0),
            currency=ProfitCurrency(data["currency"]) if data.get("currency") else ProfitCurrency.USDT,
            metadata=data.get("metadata", {})
        )
        
        summary.__post_init__()
        return summary
        
    def add_profit(self, profit: ProfitCalculation) -> None:
        """
        Add profit to summary.
        
        Args:
            profit: Profit calculation to add
        """
        self.total_trades += 1
        self.total_gross_profit += profit.gross_profit
        self.total_net_profit += profit.net_profit
        self.total_fees += profit.total_costs
        self.total_costs += profit.total_costs + profit.other_costs
        
        if profit.is_profitable():
            self.winning_trades += 1
            if profit.net_profit > self.largest_win:
                self.largest_win = profit.net_profit
        else:
            self.losing_trades += 1
            if abs(profit.net_profit) > self.largest_loss:
                self.largest_loss = abs(profit.net_profit)
                
        # Update attribution
        if profit.strategy:
            self.profit_by_strategy[profit.strategy] = self.profit_by_strategy.get(profit.strategy, 0) + profit.net_profit
        if profit.exchange:
            self.profit_by_exchange[profit.exchange] = self.profit_by_exchange.get(profit.exchange, 0) + profit.net_profit
        if profit.symbol:
            self.profit_by_symbol[profit.symbol] = self.profit_by_symbol.get(profit.symbol, 0) + profit.net_profit
            
        # Update day
        day_key = profit.exit_time.strftime("%Y-%m-%d") if profit.exit_time else datetime.utcnow().strftime("%Y-%m-%d")
        self.profit_by_day[day_key] = self.profit_by_day.get(day_key, 0) + profit.net_profit
        
        self._calculate_metrics()


# ====================================================================================
# PROFIT PERFORMANCE MODELS
# ====================================================================================

@dataclass
class ProfitPerformance:
    """
    Performance metrics for profit evaluation.
    """
    # Core fields
    performance_id: str = field(default_factory=lambda: str(uuid4()))
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    
    # Risk-adjusted returns
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    omega_ratio: float = 0.0
    treynor_ratio: float = 0.0
    
    # Returns
    total_return: float = 0.0
    annualized_return: float = 0.0
    cumulative_return: float = 0.0
    rolling_returns: List[float] = field(default_factory=list)
    
    # Risk metrics
    volatility: float = 0.0
    downside_volatility: float = 0.0
    maximum_drawdown: float = 0.0
    current_drawdown: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0
    beta: float = 0.0
    alpha: float = 0.0
    
    # Efficiency metrics
    profit_factor: float = 0.0
    recovery_factor: float = 0.0
    ulcer_index: float = 0.0
    
    # Benchmark
    benchmark_return: float = 0.0
    benchmark_volatility: float = 0.0
    information_ratio: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "performance_id": self.performance_id,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "omega_ratio": self.omega_ratio,
            "treynor_ratio": self.treynor_ratio,
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "cumulative_return": self.cumulative_return,
            "rolling_returns": self.rolling_returns,
            "volatility": self.volatility,
            "downside_volatility": self.downside_volatility,
            "maximum_drawdown": self.maximum_drawdown,
            "current_drawdown": self.current_drawdown,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "beta": self.beta,
            "alpha": self.alpha,
            "profit_factor": self.profit_factor,
            "recovery_factor": self.recovery_factor,
            "ulcer_index": self.ulcer_index,
            "benchmark_return": self.benchmark_return,
            "benchmark_volatility": self.benchmark_volatility,
            "information_ratio": self.information_ratio,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_profits(cls, profits: List[ProfitCalculation]) -> "ProfitPerformance":
        """Create performance from list of profits."""
        performance = cls()
        
        if not profits:
            return performance
            
        # Extract net profits
        net_profits = [p.net_profit for p in profits]
        returns = [p.profit_percentage for p in profits]
        
        # Total return
        performance.total_return = sum(net_profits)
        
        # Volatility
        if len(net_profits) > 1:
            performance.volatility = statistics.stdev(net_profits)
            
        # Sharpe ratio (assuming risk-free rate of 2%)
        risk_free_rate = 0.02
        if performance.volatility > 0:
            performance.sharpe_ratio = (performance.total_return - risk_free_rate) / performance.volatility
            
        # Win rate and profit factor
        winning = [p for p in profits if p.is_profitable()]
        losing = [p for p in profits if not p.is_profitable()]
        
        if winning:
            performance.profit_factor = sum(p.net_profit for p in winning) / abs(sum(p.net_profit for p in losing)) if losing else float('inf')
            
        # Max drawdown
        cumulative = 0
        peak = 0
        max_drawdown = 0
        for profit in profits:
            cumulative += profit.net_profit
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        performance.maximum_drawdown = max_drawdown
        performance.current_drawdown = peak - cumulative
        
        # Recovery factor
        if performance.maximum_drawdown > 0:
            performance.recovery_factor = performance.total_return / performance.maximum_drawdown
            
        # Calmar ratio
        if performance.maximum_drawdown > 0:
            performance.calmar_ratio = performance.total_return / performance.maximum_drawdown
            
        # Annualized return
        days = (performance.period_end - performance.period_start).total_seconds() / (24 * 3600)
        if days > 0:
            performance.annualized_return = performance.total_return * (365 / days)
            
        return performance


# ====================================================================================
# PROFIT FORECAST MODELS
# ====================================================================================

@dataclass
class ProfitForecast:
    """
    Profit forecast and projection.
    """
    forecast_id: str = field(default_factory=lambda: str(uuid4()))
    forecast_time: datetime = field(default_factory=datetime.utcnow)
    horizon_days: int = 30
    
    # Forecast values
    expected_profit: float = 0.0
    lower_bound: float = 0.0
    upper_bound: float = 0.0
    confidence: float = 0.0
    
    # Scenario analysis
    bullish_scenario: float = 0.0
    bearish_scenario: float = 0.0
    base_scenario: float = 0.0
    
    # Projections
    daily_projection: List[float] = field(default_factory=list)
    weekly_projection: List[float] = field(default_factory=list)
    monthly_projection: List[float] = field(default_factory=list)
    
    # Probability
    probability_positive: float = 0.0
    probability_target: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "forecast_id": self.forecast_id,
            "forecast_time": self.forecast_time.isoformat(),
            "horizon_days": self.horizon_days,
            "expected_profit": self.expected_profit,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "confidence": self.confidence,
            "bullish_scenario": self.bullish_scenario,
            "bearish_scenario": self.bearish_scenario,
            "base_scenario": self.base_scenario,
            "daily_projection": self.daily_projection,
            "weekly_projection": self.weekly_projection,
            "monthly_projection": self.monthly_projection,
            "probability_positive": self.probability_positive,
            "probability_target": self.probability_target,
            "metadata": self.metadata
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def calculate_profit_percentage(
    entry_price: float,
    exit_price: float,
    side: str = "long"
) -> float:
    """
    Calculate profit percentage.
    
    Args:
        entry_price: Entry price
        exit_price: Exit price
        side: "long" or "short"
        
    Returns:
        Profit percentage
    """
    if entry_price == 0:
        return 0.0
        
    if side == "long":
        return ((exit_price - entry_price) / entry_price) * 100
    else:
        return ((entry_price - exit_price) / entry_price) * 100


def calculate_profit_factor(
    profits: List[float],
    losses: List[float]
) -> float:
    """
    Calculate profit factor.
    
    Args:
        profits: List of positive profits
        losses: List of losses (positive values)
        
    Returns:
        Profit factor
    """
    total_profit = sum(profits)
    total_loss = sum(losses)
    
    if total_loss == 0:
        return float('inf')
        
    return total_profit / total_loss


def calculate_expected_value(
    profits: List[float],
    probabilities: Optional[List[float]] = None
) -> float:
    """
    Calculate expected value.
    
    Args:
        profits: List of profits
        probabilities: List of probabilities (optional)
        
    Returns:
        Expected value
    """
    if not profits:
        return 0.0
        
    if probabilities and len(profits) == len(probabilities):
        return sum(p * prob for p, prob in zip(profits, probabilities))
    else:
        return sum(profits) / len(profits)


def calculate_sharpe_ratio(
    returns: List[float],
    risk_free_rate: float = 0.02
) -> float:
    """
    Calculate Sharpe ratio.
    
    Args:
        returns: List of returns
        risk_free_rate: Risk-free rate
        
    Returns:
        Sharpe ratio
    """
    if not returns:
        return 0.0
        
    avg_return = sum(returns) / len(returns)
    
    if len(returns) > 1:
        std_dev = statistics.stdev(returns)
    else:
        std_dev = 0
        
    if std_dev == 0:
        return 0.0
        
    return (avg_return - risk_free_rate) / std_dev


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'ProfitType',
    'ProfitCurrency',
    'ProfitAttributionType',
    'PerformanceMetric',
    
    # Core Models
    'ProfitCalculation',
    'ProfitSummary',
    'ProfitPerformance',
    'ProfitForecast',
    
    # Helper Functions
    'calculate_profit_percentage',
    'calculate_profit_factor',
    'calculate_expected_value',
    'calculate_sharpe_ratio',
]
