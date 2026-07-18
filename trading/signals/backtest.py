# trading/signals/backtest.py
"""
NEXUS AI TRADING SYSTEM - Signal Backtesting
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides signal backtesting capabilities including:
- Historical signal simulation
- Performance analysis
- Signal quality assessment
- Strategy comparison
- Confidence calibration validation
- Filter effectiveness testing
"""

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable
from collections import defaultdict, deque

import numpy as np
import pandas as pd

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType
from shared.types.trading import MarketData, Trade
from .base import Signal, SignalType, SignalStrength, SignalSource
from .storage import SignalRecord, SignalStorage, SignalOutcome
from .confidence import ConfidenceScoringEngine, ConfidenceResult
from .filter import SignalFilter, FilterResult

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class BacktestMode(str, Enum):
    """Backtest execution modes"""
    WALK_FORWARD = "walk_forward"
    ROLLING = "rolling"
    EXPANDING = "expanding"
    FIXED = "fixed"


class SignalExecutionType(str, Enum):
    """Signal execution types for backtest"""
    MARKET_ORDER = "market_order"
    LIMIT_ORDER = "limit_order"
    VWAP = "vwap"
    TWAP = "twap"
    IMMEDIATE = "immediate"


@dataclass
class BacktestConfig:
    """Configuration for signal backtesting"""
    # General settings
    mode: BacktestMode = BacktestMode.FIXED
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    lookback_days: int = 365
    
    # Execution settings
    execution_type: SignalExecutionType = SignalExecutionType.MARKET_ORDER
    slippage_pct: float = 0.001  # 0.1%
    commission_pct: float = 0.001  # 0.1%
    min_position_size: float = 10.0
    max_position_size: float = 100000.0
    
    # Walk-forward settings
    train_size: int = 252  # days
    test_size: int = 63    # days
    step_size: int = 21    # days
    
    # Performance metrics
    include_metrics: List[str] = field(default_factory=lambda: [
        "total_return",
        "annualized_return",
        "sharpe_ratio",
        "max_drawdown",
        "win_rate",
        "profit_factor",
        "avg_win_loss_ratio",
    ])
    
    # Output
    save_results: bool = True
    output_dir: str = "data/backtest_results"


@dataclass
class BacktestResult:
    """Result of a backtest run"""
    name: str
    start_date: datetime
    end_date: datetime
    total_signals: int
    executed_signals: int
    successful_trades: int
    losing_trades: int
    win_rate: float
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    avg_win_loss_ratio: float
    total_commission: float
    total_slippage: float
    confidence_calibration: float
    signal_stats: Dict[str, Any] = field(default_factory=dict)
    trade_history: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "total_signals": self.total_signals,
            "executed_signals": self.executed_signals,
            "successful_trades": self.successful_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "profit_factor": self.profit_factor,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "avg_win_loss_ratio": self.avg_win_loss_ratio,
            "total_commission": self.total_commission,
            "total_slippage": self.total_slippage,
            "confidence_calibration": self.confidence_calibration,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================================
# SIGNAL BACKTEST ENGINE
# ============================================================================

class SignalBacktestEngine:
    """
    Engine for backtesting signals and strategies.
    
    Features:
    - Historical signal simulation
    - Walk-forward analysis
    - Performance metrics calculation
    - Confidence validation
    - Filter effectiveness testing
    - Strategy comparison
    """
    
    def __init__(
        self,
        config: Optional[BacktestConfig] = None,
        signal_storage: Optional[SignalStorage] = None,
        confidence_engine: Optional[ConfidenceScoringEngine] = None,
        signal_filter: Optional[SignalFilter] = None,
    ):
        """
        Initialize the backtest engine.
        
        Args:
            config: Backtest configuration
            signal_storage: Signal storage instance
            confidence_engine: Confidence scoring engine
            signal_filter: Signal filter
        """
        self.config = config or BacktestConfig()
        self.signal_storage = signal_storage or SignalStorage()
        self.confidence_engine = confidence_engine or ConfidenceScoringEngine()
        self.signal_filter = signal_filter or SignalFilter()
        
        # Results storage
        self._results: List[BacktestResult] = []
        self._current_result: Optional[BacktestResult] = None
        
        # Statistics
        self._stats = {
            "backtests_run": 0,
            "total_signals_tested": 0,
            "avg_win_rate": 0.0,
            "avg_sharpe": 0.0,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        self.logger = logger
    
    # ========================================================================
    # BACKTEST EXECUTION
    # ========================================================================
    
    async def run_backtest(
        self,
        name: str,
        signals: List[Signal],
        market_data: Dict[str, List[MarketData]],
        **kwargs,
    ) -> BacktestResult:
        """
        Run a backtest on signals.
        
        Args:
            name: Backtest name
            signals: List of signals to test
            market_data: Market data by symbol
            **kwargs: Additional parameters
            
        Returns:
            BacktestResult: Backtest result
        """
        start_time = time.time()
        
        if not signals:
            logger.warning("No signals provided for backtest")
            return self._create_empty_result(name)
        
        # Filter signals
        filtered_signals = await self._filter_signals(signals)
        
        if not filtered_signals:
            logger.warning("No signals passed filtering")
            return self._create_empty_result(name)
        
        # Execute signals
        trades = await self._execute_signals(filtered_signals, market_data)
        
        if not trades:
            logger.warning("No trades executed")
            return self._create_empty_result(name)
        
        # Calculate metrics
        result = await self._calculate_metrics(name, filtered_signals, trades, market_data)
        
        # Store result
        self._results.append(result)
        self._stats["backtests_run"] += 1
        self._stats["total_signals_tested"] += len(signals)
        
        # Update averages
        total = self._stats["backtests_run"]
        self._stats["avg_win_rate"] = (
            (self._stats["avg_win_rate"] * (total - 1) + result.win_rate) / total
        )
        self._stats["avg_sharpe"] = (
            (self._stats["avg_sharpe"] * (total - 1) + result.sharpe_ratio) / total
        )
        
        processing_time = (time.time() - start_time) * 1000
        result.metadata["processing_time_ms"] = processing_time
        
        self.logger.info(
            f"Backtest '{name}' completed: "
            f"{result.total_signals} signals, {result.executed_signals} executed, "
            f"win rate: {result.win_rate:.1f}%, return: {result.total_return:.2f}%"
        )
        
        return result
    
    async def run_walk_forward(
        self,
        name: str,
        signals: List[Signal],
        market_data: Dict[str, List[MarketData]],
        **kwargs,
    ) -> List[BacktestResult]:
        """
        Run walk-forward backtest.
        
        Args:
            name: Backtest name
            signals: List of signals
            market_data: Market data by symbol
            **kwargs: Additional parameters
            
        Returns:
            List[BacktestResult]: Results for each window
        """
        if len(signals) < self.config.train_size + self.config.test_size:
            logger.warning("Insufficient signals for walk-forward")
            return []
        
        results = []
        
        # Sort signals by timestamp
        sorted_signals = sorted(signals, key=lambda x: x.timestamp)
        
        # Walk forward
        for i in range(0, len(sorted_signals) - self.config.test_size, self.config.step_size):
            # Split train/test
            train_end = i + self.config.train_size
            test_end = train_end + self.config.test_size
            
            if test_end > len(sorted_signals):
                break
            
            train_signals = sorted_signals[i:train_end]
            test_signals = sorted_signals[train_end:test_end]
            
            # Train on train set (update confidence engine)
            for signal in train_signals:
                if signal.metadata.get("outcome"):
                    await self.confidence_engine.update_performance(
                        signal,
                        signal.metadata.get("success", False),
                        signal.metadata.get("pnl", 0),
                    )
            
            # Test on test set
            result = await self.run_backtest(
                f"{name}_window_{i}",
                test_signals,
                market_data,
                **kwargs,
            )
            results.append(result)
            
            self.logger.info(
                f"Walk-forward window {i//self.config.step_size + 1}: "
                f"win rate: {result.win_rate:.1f}%, return: {result.total_return:.2f}%"
            )
        
        return results
    
    # ========================================================================
    # SIGNAL FILTERING
    # ========================================================================
    
    async def _filter_signals(self, signals: List[Signal]) -> List[Signal]:
        """
        Filter signals for backtest.
        
        Args:
            signals: Signals to filter
            
        Returns:
            List[Signal]: Filtered signals
        """
        filtered = []
        
        for signal in signals:
            # Apply confidence filter
            if signal.confidence < 0.3:
                continue
            
            # Apply signal filter if configured
            if self.signal_filter:
                result = await self.signal_filter.filter_signal(signal)
                if not result.passed:
                    continue
            
            # Apply date filter
            if self.config.start_date and signal.timestamp < self.config.start_date:
                continue
            if self.config.end_date and signal.timestamp > self.config.end_date:
                continue
            
            # Skip neutral/hold signals
            if signal.signal_type in [SignalType.NEUTRAL, SignalType.HOLD]:
                continue
            
            filtered.append(signal)
        
        return filtered
    
    # ========================================================================
    # SIGNAL EXECUTION
    # ========================================================================
    
    async def _execute_signals(
        self,
        signals: List[Signal],
        market_data: Dict[str, List[MarketData]],
    ) -> List[Trade]:
        """
        Execute signals in backtest.
        
        Args:
            signals: Signals to execute
            market_data: Market data
            
        Returns:
            List[Trade]: Executed trades
        """
        trades = []
        positions = {}  # symbol -> (entry_price, quantity, entry_time)
        
        # Group signals by symbol and sort by time
        signal_groups = defaultdict(list)
        for signal in signals:
            signal_groups[signal.symbol].append(signal)
        
        for symbol, symbol_signals in signal_groups.items():
            # Sort signals by time
            sorted_signals = sorted(symbol_signals, key=lambda x: x.timestamp)
            
            # Get market data for symbol
            symbol_data = market_data.get(symbol, [])
            if not symbol_data:
                logger.warning(f"No market data for {symbol}")
                continue
            
            # Create price lookup for timestamps
            price_lookup = {d.timestamp: d.close for d in symbol_data}
            
            for signal in sorted_signals:
                # Get execution price
                price = await self._get_execution_price(signal, price_lookup)
                if price is None:
                    continue
                
                # Calculate position size
                position_size = self._calculate_position_size(signal, price)
                
                if signal.signal_type == SignalType.BUY:
                    # Enter long position
                    if symbol in positions:
                        # Close existing position first
                        old_pos = positions[symbol]
                        trade = self._create_trade(
                            symbol=symbol,
                            side=OrderSide.SELL,
                            quantity=old_pos["quantity"],
                            entry_price=old_pos["price"],
                            exit_price=price,
                            entry_time=old_pos["time"],
                            exit_time=signal.timestamp,
                            commission=old_pos["quantity"] * price * self.config.commission_pct,
                            slippage=old_pos["quantity"] * price * self.config.slippage_pct,
                        )
                        trades.append(trade)
                    
                    positions[symbol] = {
                        "price": price,
                        "quantity": position_size,
                        "time": signal.timestamp,
                    }
                
                elif signal.signal_type == SignalType.SELL:
                    # Enter short position
                    if symbol in positions:
                        old_pos = positions[symbol]
                        trade = self._create_trade(
                            symbol=symbol,
                            side=OrderSide.BUY,
                            quantity=old_pos["quantity"],
                            entry_price=old_pos["price"],
                            exit_price=price,
                            entry_time=old_pos["time"],
                            exit_time=signal.timestamp,
                            commission=old_pos["quantity"] * price * self.config.commission_pct,
                            slippage=old_pos["quantity"] * price * self.config.slippage_pct,
                        )
                        trades.append(trade)
                        del positions[symbol]
                    else:
                        positions[symbol] = {
                            "price": price,
                            "quantity": position_size,
                            "time": signal.timestamp,
                        }
                
                elif signal.signal_type == SignalType.CLOSE:
                    # Close existing position
                    if symbol in positions:
                        old_pos = positions[symbol]
                        trade = self._create_trade(
                            symbol=symbol,
                            side=OrderSide.SELL if old_pos["side"] == OrderSide.BUY else OrderSide.BUY,
                            quantity=old_pos["quantity"],
                            entry_price=old_pos["price"],
                            exit_price=price,
                            entry_time=old_pos["time"],
                            exit_time=signal.timestamp,
                            commission=old_pos["quantity"] * price * self.config.commission_pct,
                            slippage=old_pos["quantity"] * price * self.config.slippage_pct,
                        )
                        trades.append(trade)
                        del positions[symbol]
        
        # Close any remaining positions at end
        for symbol, pos in positions.items():
            # Use last available price
            if symbol_data:
                last_price = symbol_data[-1].close
                trade = self._create_trade(
                    symbol=symbol,
                    side=OrderSide.SELL if pos["side"] == OrderSide.BUY else OrderSide.BUY,
                    quantity=pos["quantity"],
                    entry_price=pos["price"],
                    exit_price=last_price,
                    entry_time=pos["time"],
                    exit_time=datetime.utcnow(),
                    commission=pos["quantity"] * last_price * self.config.commission_pct,
                    slippage=pos["quantity"] * last_price * self.config.slippage_pct,
                )
                trades.append(trade)
        
        return trades
    
    async def _get_execution_price(
        self,
        signal: Signal,
        price_lookup: Dict[datetime, float],
    ) -> Optional[float]:
        """
        Get execution price for a signal.
        
        Args:
            signal: Signal
            price_lookup: Price lookup by timestamp
            
        Returns:
            Optional[float]: Execution price
        """
        # Find closest timestamp
        closest_time = None
        min_diff = float('inf')
        
        for ts in price_lookup.keys():
            diff = abs((signal.timestamp - ts).total_seconds())
            if diff < min_diff:
                min_diff = diff
                closest_time = ts
        
        if closest_time is None:
            return None
        
        base_price = price_lookup[closest_time]
        
        # Apply slippage
        if self.config.execution_type == SignalExecutionType.MARKET_ORDER:
            slippage = base_price * self.config.slippage_pct
            if signal.signal_type == SignalType.BUY:
                price = base_price + slippage
            else:
                price = base_price - slippage
        else:
            price = base_price
        
        return price
    
    def _calculate_position_size(self, signal: Signal, price: float) -> float:
        """
        Calculate position size for a signal.
        
        Args:
            signal: Signal
            price: Execution price
            
        Returns:
            float: Position size
        """
        # Use signal position size if provided
        if signal.position_size:
            size = signal.position_size
        else:
            # Calculate based on confidence and price
            base_size = 1000.0
            confidence_multiplier = 0.5 + signal.confidence * 0.5
            size = base_size * confidence_multiplier / price
        
        # Apply limits
        size = max(size, self.config.min_position_size)
        size = min(size, self.config.max_position_size)
        
        return size
    
    def _create_trade(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        entry_price: float,
        exit_price: float,
        entry_time: datetime,
        exit_time: datetime,
        commission: float = 0.0,
        slippage: float = 0.0,
    ) -> Trade:
        """
        Create a trade from signal execution.
        
        Args:
            symbol: Trading symbol
            side: Trade side
            quantity: Trade quantity
            entry_price: Entry price
            exit_price: Exit price
            entry_time: Entry time
            exit_time: Exit time
            commission: Commission paid
            slippage: Slippage incurred
            
        Returns:
            Trade: Created trade
        """
        pnl = (exit_price - entry_price) * quantity
        if side == OrderSide.SELL:
            pnl = -pnl
        
        # Deduct commission and slippage
        pnl -= commission + slippage
        
        return Trade(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=entry_price,
            exit_price=exit_price,
            entry_time=entry_time,
            exit_time=exit_time,
            pnl=pnl,
            commission=commission,
            slippage=slippage,
            metadata={
                "backtest": True,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "entry_time": entry_time.isoformat(),
                "exit_time": exit_time.isoformat(),
            },
        )
    
    # ========================================================================
    # METRICS CALCULATION
    # ========================================================================
    
    async def _calculate_metrics(
        self,
        name: str,
        signals: List[Signal],
        trades: List[Trade],
        market_data: Dict[str, List[MarketData]],
    ) -> BacktestResult:
        """
        Calculate backtest metrics.
        
        Args:
            name: Backtest name
            signals: Signals tested
            trades: Trades executed
            market_data: Market data
            
        Returns:
            BacktestResult: Calculated result
        """
        start_date = signals[0].timestamp if signals else datetime.utcnow()
        end_date = signals[-1].timestamp if signals else datetime.utcnow()
        
        # Calculate trade stats
        successful_trades = sum(1 for t in trades if (t.pnl or 0) > 0)
        losing_trades = sum(1 for t in trades if (t.pnl or 0) < 0)
        win_rate = (successful_trades / len(trades) * 100) if trades else 0
        
        # Calculate P&L
        winning_pnls = [t.pnl for t in trades if (t.pnl or 0) > 0]
        losing_pnls = [abs(t.pnl) for t in trades if (t.pnl or 0) < 0]
        
        avg_win = sum(winning_pnls) / len(winning_pnls) if winning_pnls else 0
        avg_loss = sum(losing_pnls) / len(losing_pnls) if losing_pnls else 0
        avg_win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        
        total_pnl = sum(t.pnl or 0 for t in trades)
        total_commission = sum(t.commission or 0 for t in trades)
        total_slippage = sum(t.slippage or 0 for t in trades)
        
        # Calculate return
        initial_capital = 10000.0
        final_capital = initial_capital + total_pnl
        total_return = (final_capital - initial_capital) / initial_capital * 100
        
        # Calculate annualized return
        days = (end_date - start_date).days or 1
        annualized_return = ((1 + total_return / 100) ** (365 / days) - 1) * 100
        
        # Calculate Sharpe ratio
        daily_returns = self._calculate_daily_returns(trades, start_date, end_date)
        sharpe_ratio = self._calculate_sharpe_ratio(daily_returns)
        
        # Calculate max drawdown
        equity_curve = self._calculate_equity_curve(trades, start_date, end_date)
        max_drawdown = self._calculate_max_drawdown(equity_curve)
        
        # Calculate profit factor
        gross_profit = sum(winning_pnls) if winning_pnls else 0
        gross_loss = sum(losing_pnls) if losing_pnls else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Calculate confidence calibration
        confidence_calibration = await self._calculate_confidence_calibration(signals)
        
        # Signal statistics
        signal_stats = {
            "by_type": defaultdict(int),
            "by_strength": defaultdict(int),
            "avg_confidence": sum(s.confidence for s in signals) / len(signals) if signals else 0,
            "execution_rate": len(trades) / len(signals) * 100 if signals else 0,
        }
        
        for signal in signals:
            signal_stats["by_type"][signal.signal_type.value] += 1
            signal_stats["by_strength"][signal.strength.value] += 1
        
        return BacktestResult(
            name=name,
            start_date=start_date,
            end_date=end_date,
            total_signals=len(signals),
            executed_signals=len(trades),
            successful_trades=successful_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_win_loss_ratio=avg_win_loss_ratio,
            total_commission=total_commission,
            total_slippage=total_slippage,
            confidence_calibration=confidence_calibration,
            signal_stats=signal_stats,
            trade_history=trades,
            equity_curve=equity_curve,
        )
    
    def _calculate_daily_returns(
        self,
        trades: List[Trade],
        start_date: datetime,
        end_date: datetime,
    ) -> List[float]:
        """Calculate daily returns from trades."""
        if not trades:
            return [0.0]
        
        daily_pnl = defaultdict(float)
        for trade in trades:
            date = trade.exit_time.date() if trade.exit_time else datetime.utcnow().date()
            daily_pnl[date] += trade.pnl or 0
        
        # Calculate returns relative to initial capital
        initial_capital = 10000.0
        returns = []
        cumulative_pnl = 0.0
        
        for date in sorted(daily_pnl.keys()):
            cumulative_pnl += daily_pnl[date]
            if cumulative_pnl + initial_capital > 0:
                daily_return = daily_pnl[date] / (initial_capital + cumulative_pnl - daily_pnl[date])
                returns.append(daily_return)
        
        return returns if returns else [0.0]
    
    def _calculate_sharpe_ratio(self, daily_returns: List[float]) -> float:
        """Calculate Sharpe ratio."""
        if not daily_returns or len(daily_returns) < 2:
            return 0.0
        
        avg_return = np.mean(daily_returns)
        std_return = np.std(daily_returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualize (assuming 252 trading days)
        annualized_return = avg_return * 252
        annualized_std = std_return * np.sqrt(252)
        
        return annualized_return / annualized_std if annualized_std > 0 else 0.0
    
    def _calculate_equity_curve(
        self,
        trades: List[Trade],
        start_date: datetime,
        end_date: datetime,
    ) -> List[float]:
        """Calculate equity curve."""
        if not trades:
            return [10000.0]
        
        curve = [10000.0]
        cumulative_pnl = 0.0
        
        for trade in trades:
            cumulative_pnl += trade.pnl or 0
            curve.append(10000.0 + cumulative_pnl)
        
        return curve
    
    def _calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """Calculate maximum drawdown."""
        if not equity_curve or len(equity_curve) < 2:
            return 0.0
        
        max_drawdown = 0.0
        peak = equity_curve[0]
        
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown * 100
    
    async def _calculate_confidence_calibration(self, signals: List[Signal]) -> float:
        """Calculate confidence calibration score."""
        if not signals:
            return 1.0
        
        # Group signals by confidence bins
        bins = np.linspace(0, 1, 11)
        bin_indices = np.digitize([s.confidence for s in signals], bins)
        
        bin_success = {}
        bin_counts = {}
        
        for i, signal in enumerate(signals):
            bin_idx = bin_indices[i]
            if bin_idx not in bin_counts:
                bin_counts[bin_idx] = 0
                bin_success[bin_idx] = 0
            bin_counts[bin_idx] += 1
            if signal.metadata.get("success", False):
                bin_success[bin_idx] += 1
        
        # Calculate calibration error
        calibration_error = 0.0
        total = 0
        
        for bin_idx in bin_counts:
            if bin_counts[bin_idx] >= 5:
                avg_confidence = np.mean([s.confidence for i, s in enumerate(signals) if bin_indices[i] == bin_idx])
                success_rate = bin_success[bin_idx] / bin_counts[bin_idx]
                calibration_error += abs(avg_confidence - success_rate) * bin_counts[bin_idx]
                total += bin_counts[bin_idx]
        
        if total > 0:
            return 1.0 - (calibration_error / total)
        
        return 1.0
    
    def _create_empty_result(self, name: str) -> BacktestResult:
        """Create an empty backtest result."""
        now = datetime.utcnow()
        return BacktestResult(
            name=name,
            start_date=now,
            end_date=now,
            total_signals=0,
            executed_signals=0,
            successful_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_return=0.0,
            annualized_return=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            profit_factor=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            avg_win_loss_ratio=0.0,
            total_commission=0.0,
            total_slippage=0.0,
            confidence_calibration=1.0,
        )
    
    # ========================================================================
    # RESULTS MANAGEMENT
    # ========================================================================
    
    def get_results(self) -> List[BacktestResult]:
        """Get all backtest results."""
        return self._results
    
    def get_best_result(self, metric: str = "sharpe_ratio") -> Optional[BacktestResult]:
        """Get the best result by metric."""
        if not self._results:
            return None
        
        return max(self._results, key=lambda x: getattr(x, metric, 0))
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get backtest engine metrics.
        
        Returns:
            Dict[str, Any]: Metrics
        """
        return {
            **self._stats,
            "results_count": len(self._results),
            "config": {
                "mode": self.config.mode.value,
                "lookback_days": self.config.lookback_days,
                "slippage_pct": self.config.slippage_pct,
                "commission_pct": self.config.commission_pct,
            },
        }
    
    def clear_results(self) -> None:
        """Clear all backtest results."""
        self._results.clear()
        self._stats = {
            "backtests_run": 0,
            "total_signals_tested": 0,
            "avg_win_rate": 0.0,
            "avg_sharpe": 0.0,
        }
        self.logger.info("Backtest results cleared")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "BacktestMode",
    "SignalExecutionType",
    
    # Models
    "BacktestConfig",
    "BacktestResult",
    
    # Engine
    "SignalBacktestEngine",
]
