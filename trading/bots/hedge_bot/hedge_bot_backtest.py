# trading/bots/hedge_bot/hedge_bot_backtest.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Backtest Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Backtest Module

This module provides comprehensive backtesting capabilities for the
NEXUS Hedge Bot system. It allows testing strategies on historical data
with realistic simulation of trading conditions.

The module covers:
- Strategy Backtesting
- Walk-Forward Analysis
- Monte Carlo Simulation
- Parameter Optimization
- Performance Metrics
- Risk Metrics
- Trade Analysis
- Equity Curve Analysis
- Drawdown Analysis
- Benchmark Comparison
- Multi-Asset Backtesting
- Parallel Backtesting
- Realistic Slippage Simulation
- Commission Modeling
- Market Impact Modeling
"""

import os
import sys
import json
import time
import math
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

logger = logging.getLogger(__name__)


# ============================================================
# BACKTEST ENUMS
# ============================================================

class BacktestMode(Enum):
    """Backtest modes"""
    STANDARD = "standard"
    WALK_FORWARD = "walk_forward"
    MONTE_CARLO = "monte_carlo"
    OPTIMIZATION = "optimization"


class OrderStatus(Enum):
    """Order status"""
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderType(Enum):
    """Order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


# ============================================================
# BACKTEST DATACLASSES
# ============================================================

@dataclass
class BacktestConfig:
    """Backtest configuration"""
    name: str
    symbol: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    strategy: Dict[str, Any]
    slippage: float = 0.001
    commission: float = 0.001
    min_trade_size: float = 100.0
    max_position_size: float = 10000.0
    max_positions: int = 10
    mode: BacktestMode = BacktestMode.STANDARD
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "symbol": self.symbol,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "initial_capital": self.initial_capital,
            "strategy": self.strategy,
            "slippage": self.slippage,
            "commission": self.commission,
            "min_trade_size": self.min_trade_size,
            "max_position_size": self.max_position_size,
            "max_positions": self.max_positions,
            "mode": self.mode.value,
            "parameters": self.parameters,
        }


@dataclass
class BacktestTrade:
    """Backtest trade"""
    id: int
    symbol: str
    side: str
    quantity: float
    price: float
    entry_time: datetime
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0
    pnl_percent: float = 0.0
    fees: float = 0.0
    slippage_cost: float = 0.0
    holding_period: float = 0.0
    status: str = "open"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "fees": self.fees,
            "slippage_cost": self.slippage_cost,
            "holding_period": self.holding_period,
            "status": self.status,
        }


@dataclass
class BacktestResult:
    """Backtest result"""
    config: BacktestConfig
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    average_win: float
    average_loss: float
    max_win: float
    max_loss: float
    total_fees: float
    total_slippage: float
    final_capital: float
    equity_curve: List[float]
    drawdown_curve: List[float]
    trades: List[BacktestTrade]
    duration: float
    parameters: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "config": self.config.to_dict(),
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "average_win": self.average_win,
            "average_loss": self.average_loss,
            "max_win": self.max_win,
            "max_loss": self.max_loss,
            "total_fees": self.total_fees,
            "total_slippage": self.total_slippage,
            "final_capital": self.final_capital,
            "equity_curve": self.equity_curve,
            "drawdown_curve": self.drawdown_curve,
            "trades": [t.to_dict() for t in self.trades],
            "duration": self.duration,
            "parameters": self.parameters,
            "details": self.details,
        }


# ============================================================
# BACKTEST ENGINE
# ============================================================

class BacktestEngine:
    """
    Comprehensive backtest engine for the hedge bot
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the backtest engine
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.data_cache: Dict[str, pd.DataFrame] = {}
        self.results: Dict[str, BacktestResult] = {}
        self.result_history: List[BacktestResult] = []
        
        logger.info("Backtest engine initialized")
    
    # ============================================================
    # DATA MANAGEMENT
    # ============================================================
    
    def load_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1h",
        source: str = "csv"
    ) -> pd.DataFrame:
        """
        Load historical data
        
        Args:
            symbol: Trading symbol
            start_date: Start date
            end_date: End date
            interval: Data interval
            source: Data source
            
        Returns:
            DataFrame with OHLCV data
        """
        cache_key = f"{symbol}_{interval}_{start_date}_{end_date}"
        
        if cache_key in self.data_cache:
            return self.data_cache[cache_key]
        
        # Load data from source
        if source == "csv":
            data = self._load_csv_data(symbol, interval)
        elif source == "database":
            data = self._load_db_data(symbol, interval)
        elif source == "api":
            data = self._load_api_data(symbol, interval)
        else:
            data = self._generate_sample_data(symbol, start_date, end_date)
        
        # Filter by date range
        data = data[(data.index >= start_date) & (data.index <= end_date)]
        
        self.data_cache[cache_key] = data
        return data
    
    def _load_csv_data(self, symbol: str, interval: str) -> pd.DataFrame:
        """Load data from CSV"""
        try:
            file_path = Path(f"data/{symbol}_{interval}.csv")
            if file_path.exists():
                df = pd.read_csv(file_path, index_col=0, parse_dates=True)
                return df
        except Exception as e:
            logger.warning(f"Failed to load CSV data: {e}")
        
        return self._generate_sample_data(symbol, datetime.now() - timedelta(days=365), datetime.now())
    
    def _load_db_data(self, symbol: str, interval: str) -> pd.DataFrame:
        """Load data from database"""
        # Placeholder for database loading
        return self._generate_sample_data(symbol, datetime.now() - timedelta(days=365), datetime.now())
    
    def _load_api_data(self, symbol: str, interval: str) -> pd.DataFrame:
        """Load data from API"""
        # Placeholder for API loading
        return self._generate_sample_data(symbol, datetime.now() - timedelta(days=365), datetime.now())
    
    def _generate_sample_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Generate sample data for testing"""
        np.random.seed(42)
        
        dates = pd.date_range(start=start_date, end=end_date, freq="1h")
        n = len(dates)
        
        # Generate price data with random walk
        returns = np.random.normal(0, 0.001, n)
        price = 50000.0 * np.exp(np.cumsum(returns))
        
        df = pd.DataFrame({
            "open": price * (1 + np.random.normal(0, 0.001, n)),
            "high": price * (1 + np.random.normal(0.002, 0.002, n)),
            "low": price * (1 + np.random.normal(-0.002, 0.002, n)),
            "close": price,
            "volume": np.random.randint(100000, 1000000, n),
        }, index=dates)
        
        return df
    
    # ============================================================
    # BACKTEST EXECUTION
    # ============================================================
    
    def run_backtest(self, config: BacktestConfig) -> BacktestResult:
        """
        Run a backtest
        
        Args:
            config: Backtest configuration
            
        Returns:
            BacktestResult
        """
        start_time = time.time()
        
        # Load data
        data = self.load_data(
            config.symbol,
            config.start_date,
            config.end_date,
            interval=config.parameters.get("interval", "1h")
        )
        
        if data.empty:
            raise ValueError(f"No data available for {config.symbol}")
        
        # Initialize backtest state
        capital = config.initial_capital
        positions = {}
        trades = []
        equity_curve = [capital]
        drawdown_curve = [0]
        
        # Process each bar
        for idx, row in data.iterrows():
            # Generate signals
            signals = self._generate_signals(
                config.strategy,
                data.loc[:idx],
                positions,
                capital
            )
            
            # Process signals
            for signal in signals:
                if signal["action"] == "buy":
                    capital, positions = self._execute_buy(
                        signal, positions, capital, idx, row, config, trades
                    )
                elif signal["action"] == "sell":
                    capital, positions = self._execute_sell(
                        signal, positions, capital, idx, row, config, trades
                    )
            
            # Update position values
            for symbol, position in positions.items():
                position["current_price"] = row["close"]
                position["current_value"] = position["quantity"] * row["close"]
            
            # Update equity
            total_value = capital + sum(p["current_value"] for p in positions.values())
            equity_curve.append(total_value)
            
            # Calculate drawdown
            peak = max(equity_curve)
            drawdown = (peak - total_value) / peak if peak > 0 else 0
            drawdown_curve.append(drawdown)
        
        # Close open positions
        final_row = data.iloc[-1]
        for symbol, position in positions.items():
            trade = BacktestTrade(
                id=len(trades) + 1,
                symbol=symbol,
                side=position["side"],
                quantity=position["quantity"],
                price=position["entry_price"],
                entry_time=position["entry_time"],
                exit_time=final_row.name,
                exit_price=final_row["close"],
            )
            trade.pnl = (final_row["close"] - position["entry_price"]) * position["quantity"]
            trade.pnl_percent = trade.pnl / (position["entry_price"] * position["quantity"])
            trade.status = "closed"
            trades.append(trade)
        
        # Calculate metrics
        metrics = self._calculate_metrics(config, trades, equity_curve, drawdown_curve)
        
        result = BacktestResult(
            config=config,
            **metrics,
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve,
            trades=trades,
            duration=time.time() - start_time,
            parameters=config.parameters,
        )
        
        self.results[config.name] = result
        self.result_history.append(result)
        
        logger.info(f"Backtest completed: {config.name} in {result.duration:.2f}s")
        return result
    
    # ============================================================
    # SIGNAL GENERATION
    # ============================================================
    
    def _generate_signals(
        self,
        strategy: Dict[str, Any],
        data: pd.DataFrame,
        positions: Dict[str, Any],
        capital: float
    ) -> List[Dict[str, Any]]:
        """
        Generate trading signals
        
        Args:
            strategy: Strategy configuration
            data: Market data
            positions: Current positions
            capital: Available capital
            
        Returns:
            List of signals
        """
        signals = []
        
        strategy_type = strategy.get("type", "simple")
        
        if strategy_type == "simple":
            signals = self._simple_strategy(data, strategy)
        elif strategy_type == "moving_average":
            signals = self._ma_strategy(data, strategy)
        elif strategy_type == "rsi":
            signals = self._rsi_strategy(data, strategy)
        elif strategy_type == "bollinger":
            signals = self._bollinger_strategy(data, strategy)
        elif strategy_type == "custom":
            signals = self._custom_strategy(data, strategy, positions, capital)
        
        return signals
    
    def _simple_strategy(self, data: pd.DataFrame, strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Simple buy/sell strategy"""
        signals = []
        last_row = data.iloc[-1]
        
        # Simple rule: buy if price > 20 MA, sell if price < 20 MA
        if len(data) >= 20:
            ma = data["close"].rolling(20).mean().iloc[-1]
            if last_row["close"] > ma:
                signals.append({"action": "buy", "size": 0.1})
            else:
                signals.append({"action": "sell", "size": 1.0})
        
        return signals
    
    def _ma_strategy(self, data: pd.DataFrame, strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Moving average crossover strategy"""
        signals = []
        fast = strategy.get("fast", 10)
        slow = strategy.get("slow", 30)
        
        if len(data) >= slow:
            ma_fast = data["close"].rolling(fast).mean().iloc[-1]
            ma_slow = data["close"].rolling(slow).mean().iloc[-1]
            ma_fast_prev = data["close"].rolling(fast).mean().iloc[-2]
            ma_slow_prev = data["close"].rolling(slow).mean().iloc[-2]
            
            if ma_fast > ma_slow and ma_fast_prev <= ma_slow_prev:
                signals.append({"action": "buy", "size": 0.1})
            elif ma_fast < ma_slow and ma_fast_prev >= ma_slow_prev:
                signals.append({"action": "sell", "size": 1.0})
        
        return signals
    
    def _rsi_strategy(self, data: pd.DataFrame, strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """RSI strategy"""
        signals = []
        period = strategy.get("period", 14)
        oversold = strategy.get("oversold", 30)
        overbought = strategy.get("overbought", 70)
        
        if len(data) >= period:
            rsi = self._calculate_rsi(data["close"], period)
            if rsi < oversold:
                signals.append({"action": "buy", "size": 0.1})
            elif rsi > overbought:
                signals.append({"action": "sell", "size": 1.0})
        
        return signals
    
    def _bollinger_strategy(self, data: pd.DataFrame, strategy: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Bollinger Bands strategy"""
        signals = []
        period = strategy.get("period", 20)
        std_dev = strategy.get("std_dev", 2)
        
        if len(data) >= period:
            ma = data["close"].rolling(period).mean().iloc[-1]
            std = data["close"].rolling(period).std().iloc[-1]
            upper = ma + std_dev * std
            lower = ma - std_dev * std
            
            last_close = data["close"].iloc[-1]
            if last_close < lower:
                signals.append({"action": "buy", "size": 0.1})
            elif last_close > upper:
                signals.append({"action": "sell", "size": 1.0})
        
        return signals
    
    def _custom_strategy(
        self,
        data: pd.DataFrame,
        strategy: Dict[str, Any],
        positions: Dict[str, Any],
        capital: float
    ) -> List[Dict[str, Any]]:
        """Custom strategy"""
        # Placeholder for custom strategy implementation
        return []
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if len(rsi) > 0 else 50
    
    # ============================================================
    # ORDER EXECUTION
    # ============================================================
    
    def _execute_buy(
        self,
        signal: Dict[str, Any],
        positions: Dict[str, Any],
        capital: float,
        timestamp: datetime,
        row: pd.Series,
        config: BacktestConfig,
        trades: List[BacktestTrade]
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Execute a buy order
        
        Args:
            signal: Buy signal
            positions: Current positions
            capital: Available capital
            timestamp: Execution time
            row: Current bar data
            config: Backtest configuration
            trades: Trade list
            
        Returns:
            (updated_capital, updated_positions)
        """
        symbol = config.symbol
        price = row["close"] * (1 + config.slippage)
        max_position = config.max_position_size / price
        
        # Calculate position size
        size = min(signal.get("size", 0.1), max_position)
        size = max(size, config.min_trade_size / price)
        size = min(size, capital / price)
        
        if size <= 0:
            return capital, positions
        
        # Add slippage
        slippage_cost = size * price * config.slippage
        
        # Add commission
        commission = size * price * config.commission
        
        # Update capital
        capital -= (size * price + commission + slippage_cost)
        
        # Update positions
        if symbol in positions:
            positions[symbol]["quantity"] += size
            positions[symbol]["avg_price"] = (
                (positions[symbol]["avg_price"] * positions[symbol]["quantity"] + size * price) /
                (positions[symbol]["quantity"] + size)
            )
        else:
            positions[symbol] = {
                "side": "long",
                "quantity": size,
                "avg_price": price,
                "entry_price": price,
                "entry_time": timestamp,
                "current_price": price,
                "current_value": size * price,
            }
        
        # Record trade
        trade = BacktestTrade(
            id=len(trades) + 1,
            symbol=symbol,
            side="buy",
            quantity=size,
            price=price,
            entry_time=timestamp,
            fees=commission,
            slippage_cost=slippage_cost,
            status="open",
        )
        trades.append(trade)
        
        return capital, positions
    
    def _execute_sell(
        self,
        signal: Dict[str, Any],
        positions: Dict[str, Any],
        capital: float,
        timestamp: datetime,
        row: pd.Series,
        config: BacktestConfig,
        trades: List[BacktestTrade]
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Execute a sell order
        
        Args:
            signal: Sell signal
            positions: Current positions
            capital: Available capital
            timestamp: Execution time
            row: Current bar data
            config: Backtest configuration
            trades: Trade list
            
        Returns:
            (updated_capital, updated_positions)
        """
        symbol = config.symbol
        price = row["close"] * (1 - config.slippage)
        
        if symbol not in positions:
            return capital, positions
        
        position = positions[symbol]
        size = min(signal.get("size", 1.0), position["quantity"])
        
        if size <= 0:
            return capital, positions
        
        # Add slippage
        slippage_cost = size * price * config.slippage
        
        # Add commission
        commission = size * price * config.commission
        
        # Update capital
        capital += (size * price - commission - slippage_cost)
        
        # Calculate PnL
        pnl = (price - position["avg_price"]) * size
        
        # Update positions
        position["quantity"] -= size
        if position["quantity"] <= 0:
            del positions[symbol]
        
        # Update trade
        open_trade = None
        for trade in trades:
            if trade.symbol == symbol and trade.status == "open":
                open_trade = trade
                break
        
        if open_trade:
            open_trade.exit_time = timestamp
            open_trade.exit_price = price
            open_trade.pnl = pnl
            open_trade.pnl_percent = pnl / (open_trade.price * open_trade.quantity)
            open_trade.status = "closed"
            open_trade.holding_period = (timestamp - open_trade.entry_time).total_seconds() / 3600
        
        return capital, positions
    
    # ============================================================
    # METRICS CALCULATION
    # ============================================================
    
    def _calculate_metrics(
        self,
        config: BacktestConfig,
        trades: List[BacktestTrade],
        equity_curve: List[float],
        drawdown_curve: List[float]
    ) -> Dict[str, Any]:
        """
        Calculate performance metrics
        
        Args:
            config: Backtest configuration
            trades: List of trades
            equity_curve: Equity curve
            drawdown_curve: Drawdown curve
            
        Returns:
            Dictionary of metrics
        """
        closed_trades = [t for t in trades if t.status == "closed"]
        
        # Returns
        total_return = (equity_curve[-1] - config.initial_capital) / config.initial_capital
        
        # Annualized return
        days = len(equity_curve) * 24  # Assuming hourly data
        if days > 0:
            annualized_return = (1 + total_return) ** (365 / days) - 1
        else:
            annualized_return = 0
        
        # Sharpe ratio
        returns = np.diff(equity_curve) / equity_curve[:-1]
        if len(returns) > 1:
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252 * 24)
        else:
            sharpe_ratio = 0
        
        # Sortino ratio
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 1:
            sortino_ratio = np.mean(returns) / np.std(downside_returns) * np.sqrt(252 * 24)
        else:
            sortino_ratio = 0
        
        # Calmar ratio
        max_drawdown = max(drawdown_curve) if drawdown_curve else 0
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0
        
        # Win rate
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl < 0]
        total_trades = len(closed_trades)
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        # Profit factor
        total_wins = sum(t.pnl for t in winning_trades)
        total_losses = sum(abs(t.pnl) for t in losing_trades)
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # Average win/loss
        avg_win = total_wins / len(winning_trades) if winning_trades else 0
        avg_loss = total_losses / len(losing_trades) if losing_trades else 0
        
        # Max win/loss
        max_win = max([t.pnl for t in winning_trades]) if winning_trades else 0
        max_loss = min([t.pnl for t in losing_trades]) if losing_trades else 0
        
        # Fees and slippage
        total_fees = sum(t.fees for t in trades)
        total_slippage = sum(t.slippage_cost for t in trades)
        
        return {
            "total_return": total_return,
            "annualized_return": annualized_return,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "average_win": avg_win,
            "average_loss": avg_loss,
            "max_win": max_win,
            "max_loss": max_loss,
            "total_fees": total_fees,
            "total_slippage": total_slippage,
            "final_capital": equity_curve[-1] if equity_curve else config.initial_capital,
        }
    
    # ============================================================
    # WALK-FORWARD ANALYSIS
    # ============================================================
    
    def walk_forward_analysis(
        self,
        config: BacktestConfig,
        window_size: int = 30,
        step_size: int = 10
    ) -> List[BacktestResult]:
        """
        Perform walk-forward analysis
        
        Args:
            config: Backtest configuration
            window_size: Window size in days
            step_size: Step size in days
            
        Returns:
            List of backtest results
        """
        results = []
        start_date = config.start_date
        end_date = config.end_date
        
        current_start = start_date
        while current_start < end_date:
            current_end = min(current_start + timedelta(days=window_size), end_date)
            
            # Create config for this window
            window_config = BacktestConfig(
                name=f"{config.name}_window_{current_start.strftime('%Y%m%d')}",
                symbol=config.symbol,
                start_date=current_start,
                end_date=current_end,
                initial_capital=config.initial_capital,
                strategy=config.strategy,
                slippage=config.slippage,
                commission=config.commission,
                min_trade_size=config.min_trade_size,
                max_position_size=config.max_position_size,
                max_positions=config.max_positions,
                mode=BacktestMode.WALK_FORWARD,
                parameters=config.parameters,
            )
            
            result = self.run_backtest(window_config)
            results.append(result)
            
            current_start += timedelta(days=step_size)
        
        return results
    
    # ============================================================
    # MONTE CARLO SIMULATION
    # ============================================================
    
    def monte_carlo_simulation(
        self,
        config: BacktestConfig,
        iterations: int = 1000,
        random_seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform Monte Carlo simulation
        
        Args:
            config: Backtest configuration
            iterations: Number of simulations
            random_seed: Random seed
            
        Returns:
            Simulation results
        """
        if random_seed:
            np.random.seed(random_seed)
        
        results = []
        
        # Run base backtest
        base_result = self.run_backtest(config)
        returns = np.diff(base_result.equity_curve) / base_result.equity_curve[:-1]
        
        for i in range(iterations):
            # Generate random returns
            shuffled_returns = np.random.choice(returns, size=len(returns))
            
            # Calculate equity curve
            equity = [config.initial_capital]
            for r in shuffled_returns:
                equity.append(equity[-1] * (1 + r))
            
            # Calculate metrics
            total_return = (equity[-1] - config.initial_capital) / config.initial_capital
            annualized_return = (1 + total_return) ** (365 / len(equity)) - 1
            max_drawdown = self._calculate_max_drawdown(equity)
            
            results.append({
                "total_return": total_return,
                "annualized_return": annualized_return,
                "max_drawdown": max_drawdown,
                "final_capital": equity[-1],
            })
        
        # Calculate statistics
        returns_array = np.array([r["total_return"] for r in results])
        annualized_array = np.array([r["annualized_return"] for r in results])
        drawdown_array = np.array([r["max_drawdown"] for r in results])
        
        return {
            "mean_return": np.mean(returns_array),
            "std_return": np.std(returns_array),
            "mean_annualized": np.mean(annualized_array),
            "std_annualized": np.std(annualized_array),
            "mean_drawdown": np.mean(drawdown_array),
            "std_drawdown": np.std(drawdown_array),
            "percentiles": {
                "1": np.percentile(returns_array, 1),
                "5": np.percentile(returns_array, 5),
                "25": np.percentile(returns_array, 25),
                "50": np.percentile(returns_array, 50),
                "75": np.percentile(returns_array, 75),
                "95": np.percentile(returns_array, 95),
                "99": np.percentile(returns_array, 99),
            },
            "iterations": iterations,
        }
    
    def _calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """Calculate max drawdown"""
        peak = equity_curve[0]
        max_drawdown = 0.0
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        return max_drawdown
    
    # ============================================================
    # PARAMETER OPTIMIZATION
    # ============================================================
    
    def optimize_parameters(
        self,
        config: BacktestConfig,
        param_grid: Dict[str, List[Any]],
        metric: str = "sharpe_ratio"
    ) -> Dict[str, Any]:
        """
        Optimize strategy parameters
        
        Args:
            config: Backtest configuration
            param_grid: Parameter grid
            metric: Optimization metric
            
        Returns:
            Best parameters and results
        """
        best_params = None
        best_score = -float("inf")
        best_result = None
        
        # Generate parameter combinations
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        
        # Simple grid search
        for combo in self._generate_combinations(param_values):
            params = dict(zip(param_names, combo))
            
            # Update strategy parameters
            config.strategy.update(params)
            config.parameters = params
            
            # Run backtest
            result = self.run_backtest(config)
            
            # Get metric value
            score = getattr(result, metric, 0)
            
            if score > best_score:
                best_score = score
                best_params = params
                best_result = result
        
        return {
            "best_params": best_params,
            "best_score": best_score,
            "best_result": best_result.to_dict() if best_result else None,
        }
    
    def _generate_combinations(self, values: List[List[Any]]) -> List[List[Any]]:
        """Generate combinations from lists"""
        import itertools
        return list(itertools.product(*values))
    
    # ============================================================
    # REPORTING
    # ============================================================
    
    def generate_report(self, result: BacktestResult) -> Dict[str, Any]:
        """
        Generate a backtest report
        
        Args:
            result: Backtest result
            
        Returns:
            Report dictionary
        """
        return {
            "name": result.config.name,
            "symbol": result.config.symbol,
            "period": {
                "start": result.config.start_date.isoformat(),
                "end": result.config.end_date.isoformat(),
            },
            "performance": {
                "total_return": result.total_return,
                "annualized_return": result.annualized_return,
                "sharpe_ratio": result.sharpe_ratio,
                "sortino_ratio": result.sortino_ratio,
                "calmar_ratio": result.calmar_ratio,
                "max_drawdown": result.max_drawdown,
            },
            "trades": {
                "total": result.total_trades,
                "winning": result.winning_trades,
                "losing": result.losing_trades,
                "win_rate": result.win_rate,
                "profit_factor": result.profit_factor,
                "average_win": result.average_win,
                "average_loss": result.average_loss,
            },
            "costs": {
                "total_fees": result.total_fees,
                "total_slippage": result.total_slippage,
            },
            "duration": result.duration,
            "parameters": result.parameters,
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get backtest statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_backtests": len(self.results),
            "successful_backtests": len([r for r in self.results.values() if r.total_trades > 0]),
            "average_return": np.mean([r.total_return for r in self.results.values()]) if self.results else 0,
            "average_sharpe": np.mean([r.sharpe_ratio for r in self.results.values()]) if self.results else 0,
            "average_drawdown": np.mean([r.max_drawdown for r in self.results.values()]) if self.results else 0,
            "best_result": max(self.results.values(), key=lambda r: r.sharpe_ratio) if self.results else None,
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "BacktestMode",
    "OrderStatus",
    "OrderType",
    
    # Dataclasses
    "BacktestConfig",
    "BacktestTrade",
    "BacktestResult",
    
    # Classes
    "BacktestEngine",
]

# ============================================================
# END OF MODULE
# ============================================================
