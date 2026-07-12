"""
NEXUS AI TRADING SYSTEM - Strategy Runner
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Version: 3.0.0
Status: Production Ready

Complete Strategy Runner system with:
- Strategy execution framework
- Multiple strategy types
- Order management
- Portfolio management
- Performance tracking
- Risk management
- Real-time execution
- Backtesting execution
- Health monitoring
- Configuration management
- Event handling
- Logging
- Metrics collection
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from uuid import uuid4

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.redis_client import get_redis
from backend.core.exceptions import StrategyError

logger = get_logger(__name__)


# ========================================
# TYPES & ENUMS
# ========================================

class StrategyType(str, Enum):
    """Strategy types"""
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    ARBITRAGE = "arbitrage"
    MARKET_MAKING = "market_making"
    BREAKOUT = "breakout"
    GRID = "grid"
    MARTINGALE = "martingale"
    PAIRS = "pairs"
    CUSTOM = "custom"


class OrderSide(str, Enum):
    """Order side"""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(str, Enum):
    """Order status"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class Order:
    """Order data"""
    id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str
    side: OrderSide
    type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    avg_price: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    """Position data"""
    symbol: str
    quantity: float
    avg_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    total_pnl: float
    opened_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Trade:
    """Trade data"""
    id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    commission: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    executed_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyResult:
    """Strategy execution result"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str
    type: StrategyType
    orders: List[Order] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)
    positions: List[Position] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    returns: List[float] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)


# ========================================
# STRATEGY BASE CLASS
# ========================================

class BaseStrategy:
    """
    Base class for all strategies.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize strategy"""
        self._initialized = True
        self.logger.info(f"Strategy {self.__class__.__name__} initialized")
    
    async def on_start(self) -> None:
        """Called when strategy starts"""
        pass
    
    async def on_stop(self) -> None:
        """Called when strategy stops"""
        pass
    
    async def on_tick(self, data: Dict[str, Any]) -> List[Order]:
        """
        Called on each tick.
        
        Args:
            data: Current market data
            
        Returns:
            List[Order]: Orders to execute
        """
        return []
    
    async def on_order_filled(self, order: Order) -> None:
        """
        Called when an order is filled.
        
        Args:
            order: Filled order
        """
        pass
    
    async def on_trade(self, trade: Trade) -> None:
        """
        Called when a trade is executed.
        
        Args:
            trade: Executed trade
        """
        pass
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get strategy parameters"""
        return self.config.get('parameters', {})
    
    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """Set strategy parameters"""
        self.config['parameters'] = parameters


# ========================================
# STRATEGY IMPLEMENTATIONS
# ========================================

class TrendFollowingStrategy(BaseStrategy):
    """Trend following strategy"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.fast_period = config.get('fast_period', 10)
        self.slow_period = config.get('slow_period', 30)
        self.atr_period = config.get('atr_period', 14)
        self.atr_multiplier = config.get('atr_multiplier', 2.0)
    
    async def on_tick(self, data: Dict[str, Any]) -> List[Order]:
        """Generate orders based on trend following"""
        orders = []
        
        # Get price data
        prices = data.get('prices', [])
        if len(prices) < self.slow_period:
            return orders
        
        # Calculate moving averages
        fast_ma = np.mean(prices[-self.fast_period:])
        slow_ma = np.mean(prices[-self.slow_period:])
        
        # Calculate ATR for position sizing
        atr = self._calculate_atr(prices, self.atr_period)
        
        # Generate signals
        current_price = prices[-1]
        
        if fast_ma > slow_ma:
            # Buy signal
            order = Order(
                symbol=data.get('symbol', ''),
                side=OrderSide.BUY,
                type=OrderType.MARKET,
                quantity=self._calculate_position_size(current_price, atr)
            )
            orders.append(order)
        elif fast_ma < slow_ma:
            # Sell signal
            order = Order(
                symbol=data.get('symbol', ''),
                side=OrderSide.SELL,
                type=OrderType.MARKET,
                quantity=self._calculate_position_size(current_price, atr)
            )
            orders.append(order)
        
        return orders
    
    def _calculate_atr(self, prices: List[float], period: int) -> float:
        """Calculate Average True Range"""
        if len(prices) < period + 1:
            return 0.0
        
        # Simplified ATR calculation
        true_ranges = []
        for i in range(1, len(prices)):
            high = prices[i]
            low = prices[i]
            prev_close = prices[i-1]
            true_range = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(true_range)
        
        return np.mean(true_ranges[-period:])
    
    def _calculate_position_size(self, price: float, atr: float) -> float:
        """Calculate position size based on risk"""
        risk_amount = self.config.get('risk_amount', 1000)
        if atr == 0:
            return risk_amount / price
        
        position_size = risk_amount / atr
        max_position = self.config.get('max_position', 10000)
        
        return min(position_size, max_position / price)


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.lookback = config.get('lookback', 20)
        self.entry_zscore = config.get('entry_zscore', 2.0)
        self.exit_zscore = config.get('exit_zscore', 0.5)
    
    async def on_tick(self, data: Dict[str, Any]) -> List[Order]:
        """Generate orders based on mean reversion"""
        orders = []
        
        # Get price data
        prices = data.get('prices', [])
        if len(prices) < self.lookback:
            return orders
        
        # Calculate z-score
        current_price = prices[-1]
        mean = np.mean(prices[-self.lookback:])
        std = np.std(prices[-self.lookback:])
        
        if std == 0:
            return orders
        
        zscore = (current_price - mean) / std
        
        # Generate signals
        if zscore < -self.entry_zscore:
            # Buy signal (oversold)
            order = Order(
                symbol=data.get('symbol', ''),
                side=OrderSide.BUY,
                type=OrderType.MARKET,
                quantity=self._calculate_position_size(current_price)
            )
            orders.append(order)
        elif zscore > self.entry_zscore:
            # Sell signal (overbought)
            order = Order(
                symbol=data.get('symbol', ''),
                side=OrderSide.SELL,
                type=OrderType.MARKET,
                quantity=self._calculate_position_size(current_price)
            )
            orders.append(order)
        elif abs(zscore) < self.exit_zscore:
            # Exit signal
            order = Order(
                symbol=data.get('symbol', ''),
                side=OrderSide.BUY if data.get('position', 0) < 0 else OrderSide.SELL,
                type=OrderType.MARKET,
                quantity=abs(data.get('position', 0))
            )
            orders.append(order)
        
        return orders
    
    def _calculate_position_size(self, price: float) -> float:
        """Calculate position size"""
        risk_amount = self.config.get('risk_amount', 1000)
        stop_loss = self.config.get('stop_loss', 0.02)
        
        if price == 0 or stop_loss == 0:
            return risk_amount / price
        
        position_size = risk_amount / (price * stop_loss)
        max_position = self.config.get('max_position', 10000)
        
        return min(position_size, max_position / price)


class MomentumStrategy(BaseStrategy):
    """Momentum strategy"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.lookback = config.get('lookback', 30)
        self.rsi_period = config.get('rsi_period', 14)
        self.oversold = config.get('oversold', 30)
        self.overbought = config.get('overbought', 70)
    
    async def on_tick(self, data: Dict[str, Any]) -> List[Order]:
        """Generate orders based on momentum"""
        orders = []
        
        # Get price data
        prices = data.get('prices', [])
        if len(prices) < self.lookback:
            return orders
        
        # Calculate RSI
        rsi = self._calculate_rsi(prices, self.rsi_period)
        
        # Calculate momentum
        momentum = (prices[-1] - prices[-self.lookback]) / prices[-self.lookback]
        
        # Generate signals
        current_price = prices[-1]
        
        if rsi < self.oversold and momentum > 0:
            # Buy signal
            order = Order(
                symbol=data.get('symbol', ''),
                side=OrderSide.BUY,
                type=OrderType.MARKET,
                quantity=self._calculate_position_size(current_price)
            )
            orders.append(order)
        elif rsi > self.overbought and momentum < 0:
            # Sell signal
            order = Order(
                symbol=data.get('symbol', ''),
                side=OrderSide.SELL,
                type=OrderType.MARKET,
                quantity=self._calculate_position_size(current_price)
            )
            orders.append(order)
        
        return orders
    
    def _calculate_rsi(self, prices: List[float], period: int) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_position_size(self, price: float) -> float:
        """Calculate position size"""
        risk_amount = self.config.get('risk_amount', 1000)
        return risk_amount / price


# ========================================
# STRATEGY RUNNER
# ========================================

class StrategyRunner:
    """
    Strategy runner for executing trading strategies.
    
    Features:
    - Strategy execution framework
    - Multiple strategy types
    - Order management
    - Portfolio management
    - Performance tracking
    - Risk management
    - Real-time execution
    - Backtesting execution
    - Health monitoring
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.redis = get_redis()
        
        # Strategy registry
        self._strategies: Dict[str, BaseStrategy] = {}
        self._strategy_types = {
            StrategyType.TREND_FOLLOWING: TrendFollowingStrategy,
            StrategyType.MEAN_REVERSION: MeanReversionStrategy,
            StrategyType.MOMENTUM: MomentumStrategy
        }
        
        # State
        self._results: Dict[str, StrategyResult] = {}
        self._running_strategies: Dict[str, asyncio.Task] = {}
        
        # Running state
        self._running = False
        self._lock = asyncio.Lock()
        
        # Metrics
        self._metrics = {
            "total_strategies": 0,
            "active_strategies": 0,
            "completed_strategies": 0,
            "failed_strategies": 0,
            "total_trades": 0
        }
        
        self.logger = get_logger(f"{__name__}.StrategyRunner")
        self.logger.info("StrategyRunner initialized")
    
    # ========================================
    # STRATEGY MANAGEMENT
    # ========================================
    
    async def register_strategy(
        self,
        name: str,
        strategy_type: StrategyType,
        config: Dict[str, Any]
    ) -> str:
        """
        Register a strategy.
        
        Args:
            name: Strategy name
            strategy_type: Strategy type
            config: Strategy configuration
            
        Returns:
            str: Strategy ID
        """
        strategy_id = str(uuid4())
        
        # Get strategy class
        strategy_class = self._strategy_types.get(strategy_type)
        if not strategy_class:
            raise StrategyError(f"Unknown strategy type: {strategy_type}")
        
        # Create strategy instance
        strategy = strategy_class(config)
        await strategy.initialize()
        
        # Store strategy
        self._strategies[strategy_id] = strategy
        
        self._metrics["total_strategies"] += 1
        
        self.logger.info(f"Strategy registered: {name} ({strategy_id})")
        return strategy_id
    
    async def unregister_strategy(self, strategy_id: str) -> bool:
        """Unregister a strategy"""
        if strategy_id in self._strategies:
            # Stop if running
            if strategy_id in self._running_strategies:
                await self.stop_strategy(strategy_id)
            
            del self._strategies[strategy_id]
            self.logger.info(f"Strategy unregistered: {strategy_id}")
            return True
        
        return False
    
    async def start_strategy(
        self,
        strategy_id: str,
        data_provider: Callable
    ) -> None:
        """
        Start a strategy.
        
        Args:
            strategy_id: Strategy ID
            data_provider: Function that provides data
        """
        if strategy_id not in self._strategies:
            raise StrategyError(f"Strategy {strategy_id} not found")
        
        if strategy_id in self._running_strategies:
            return
        
        strategy = self._strategies[strategy_id]
        
        # Create result
        result = StrategyResult(
            name=strategy_id,
            type=strategy.config.get('type', StrategyType.CUSTOM)
        )
        self._results[strategy_id] = result
        
        # Start strategy
        task = asyncio.create_task(
            self._run_strategy(strategy_id, strategy, data_provider)
        )
        self._running_strategies[strategy_id] = task
        self._metrics["active_strategies"] += 1
        
        await strategy.on_start()
        
        self.logger.info(f"Strategy started: {strategy_id}")
    
    async def stop_strategy(self, strategy_id: str) -> None:
        """Stop a strategy"""
        if strategy_id not in self._running_strategies:
            return
        
        task = self._running_strategies[strategy_id]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        del self._running_strategies[strategy_id]
        self._metrics["active_strategies"] -= 1
        
        # Update result
        if strategy_id in self._results:
            self._results[strategy_id].execution_time = time.time() - self._results[strategy_id].execution_time
        
        strategy = self._strategies.get(strategy_id)
        if strategy:
            await strategy.on_stop()
        
        self.logger.info(f"Strategy stopped: {strategy_id}")
    
    async def _run_strategy(
        self,
        strategy_id: str,
        strategy: BaseStrategy,
        data_provider: Callable
    ) -> None:
        """Run strategy execution loop"""
        result = self._results[strategy_id]
        start_time = time.time()
        
        try:
            while True:
                # Get data
                data = await data_provider()
                
                if not data:
                    await asyncio.sleep(1)
                    continue
                
                # Execute strategy
                orders = await strategy.on_tick(data)
                
                # Process orders
                for order in orders:
                    await self._process_order(strategy_id, order, data)
                
                # Update result
                result.orders.extend(orders)
                
                # Update equity curve
                if data.get('portfolio_value'):
                    result.equity_curve.append(data['portfolio_value'])
                
                # Wait for next tick
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.error(f"Strategy {strategy_id} error: {e}")
            self._metrics["failed_strategies"] += 1
            raise
    
    async def _process_order(
        self,
        strategy_id: str,
        order: Order,
        data: Dict[str, Any]
    ) -> None:
        """Process an order"""
        try:
            # Execute order
            trade = await self._execute_order(order, data)
            
            if trade:
                # Notify strategy
                strategy = self._strategies.get(strategy_id)
                if strategy:
                    await strategy.on_trade(trade)
                
                # Update result
                if strategy_id in self._results:
                    self._results[strategy_id].trades.append(trade)
                    self._metrics["total_trades"] += 1
                
        except Exception as e:
            self.logger.error(f"Order processing error: {e}")
            order.status = OrderStatus.REJECTED
    
    async def _execute_order(
        self,
        order: Order,
        data: Dict[str, Any]
    ) -> Optional[Trade]:
        """Execute an order"""
        # Get current price
        price = data.get('price', 0)
        if price == 0:
            return None
        
        # Calculate commission
        commission_rate = self.config.get('commission', 0.001)
        commission = order.quantity * price * commission_rate
        
        # Create trade
        trade = Trade(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=price,
            commission=commission
        )
        
        # Update order
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_price = price
        
        return trade
    
    # ========================================
    # BACKTESTING
    # ========================================
    
    async def run_backtest(
        self,
        strategy_id: str,
        historical_data: pd.DataFrame,
        initial_capital: float = 100000.0
    ) -> StrategyResult:
        """
        Run backtest on historical data.
        
        Args:
            strategy_id: Strategy ID
            historical_data: Historical data
            initial_capital: Initial capital
            
        Returns:
            StrategyResult: Backtest result
        """
        if strategy_id not in self._strategies:
            raise StrategyError(f"Strategy {strategy_id} not found")
        
        strategy = self._strategies[strategy_id]
        result = StrategyResult(
            name=strategy_id,
            type=strategy.config.get('type', StrategyType.CUSTOM)
        )
        
        # Initialize portfolio
        portfolio_value = initial_capital
        equity_curve = [initial_capital]
        positions = {}
        
        # Iterate through data
        for index, row in historical_data.iterrows():
            data = {
                'symbol': row.get('symbol', ''),
                'price': row['close'],
                'prices': historical_data['close'].values[:index+1].tolist(),
                'portfolio_value': portfolio_value,
                'position': positions.get(row.get('symbol', ''), {}).get('quantity', 0)
            }
            
            # Get orders
            orders = await strategy.on_tick(data)
            
            # Process orders
            for order in orders:
                trade = await self._execute_order(order, data)
                if trade:
                    # Update portfolio
                    if order.side == OrderSide.BUY:
                        portfolio_value -= trade.quantity * trade.price + trade.commission
                        positions[order.symbol] = {
                            'quantity': positions.get(order.symbol, {}).get('quantity', 0) + trade.quantity,
                            'avg_price': trade.price
                        }
                    else:
                        portfolio_value += trade.quantity * trade.price - trade.commission
                        positions[order.symbol] = {
                            'quantity': positions.get(order.symbol, {}).get('quantity', 0) - trade.quantity,
                            'avg_price': trade.price
                        }
                    
                    result.trades.append(trade)
                    self._metrics["total_trades"] += 1
            
            # Update equity
            # Simplified: add unrealized P&L
            total_position_value = 0
            for symbol, position in positions.items():
                total_position_value += position['quantity'] * data['price']
            
            equity_curve.append(portfolio_value + total_position_value)
        
        # Finalize result
        result.equity_curve = equity_curve
        result.orders = []
        result.execution_time = time.time()
        result.metrics = await self._calculate_metrics(equity_curve, result.trades)
        
        self._results[strategy_id] = result
        self._metrics["completed_strategies"] += 1
        
        self.logger.info(f"Backtest completed: {strategy_id}")
        return result
    
    async def _calculate_metrics(
        self,
        equity_curve: List[float],
        trades: List[Trade]
    ) -> Dict[str, Any]:
        """Calculate performance metrics"""
        if len(equity_curve) < 2:
            return {}
        
        # Calculate returns
        returns = []
        for i in range(1, len(equity_curve)):
            if equity_curve[i-1] != 0:
                ret = (equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]
                returns.append(ret)
            else:
                returns.append(0.0)
        
        # Calculate metrics
        total_return = (equity_curve[-1] - equity_curve[0]) / equity_curve[0]
        
        # Annualized return (assuming daily data)
        n_periods = len(returns)
        annual_return = (1 + total_return) ** (252 / n_periods) - 1 if n_periods > 0 else 0
        
        # Volatility
        volatility = np.std(returns) * np.sqrt(252) if returns else 0
        
        # Sharpe ratio
        risk_free_rate = 0.02
        excess_returns = [r - risk_free_rate / 252 for r in returns]
        sharpe = (np.mean(excess_returns) / (np.std(returns) + 0.001)) * np.sqrt(252) if returns else 0
        
        # Max drawdown
        peak = equity_curve[0]
        max_drawdown = 0
        for value in equity_curve:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak != 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # Trade metrics
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]
        
        win_rate = len(winning_trades) / len(trades) if trades else 0
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([abs(t.pnl) for t in losing_trades]) if losing_trades else 0
        profit_factor = avg_win / avg_loss if avg_loss > 0 else 0
        
        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor
        }
    
    # ========================================
    # STRATEGY OPTIMIZATION
    # ========================================
    
    async def optimize_strategy(
        self,
        strategy_id: str,
        historical_data: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
        objective: str = 'sharpe_ratio'
    ) -> Dict[str, Any]:
        """
        Optimize strategy parameters.
        
        Args:
            strategy_id: Strategy ID
            historical_data: Historical data
            param_grid: Parameter grid
            objective: Objective metric
            
        Returns:
            Dict[str, Any]: Best parameters and results
        """
        if strategy_id not in self._strategies:
            raise StrategyError(f"Strategy {strategy_id} not found")
        
        strategy = self._strategies[strategy_id]
        
        # Generate parameter combinations
        param_combinations = self._generate_param_combinations(param_grid)
        
        best_score = -float('inf')
        best_params = None
        best_result = None
        
        # Test each combination
        for params in param_combinations:
            # Set parameters
            strategy.set_parameters(params)
            
            # Run backtest
            result = await self.run_backtest(strategy_id, historical_data)
            
            # Get score
            score = result.metrics.get(objective, 0)
            
            if score > best_score:
                best_score = score
                best_params = params
                best_result = result
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'result': best_result
        }
    
    def _generate_param_combinations(
        self,
        param_grid: Dict[str, List[Any]]
    ) -> List[Dict[str, Any]]:
        """Generate parameter combinations"""
        import itertools
        
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        
        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))
        
        return combinations
    
    # ========================================
    # API METHODS
    # ========================================
    
    async def get_strategy(self, strategy_id: str) -> Optional[BaseStrategy]:
        """Get strategy instance"""
        return self._strategies.get(strategy_id)
    
    async def get_result(self, strategy_id: str) -> Optional[StrategyResult]:
        """Get strategy result"""
        return self._results.get(strategy_id)
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get runner metrics"""
        return {
            **self._metrics,
            "strategy_count": len(self._strategies),
            "result_count": len(self._results)
        }
    
    async def list_strategies(self) -> List[Dict[str, Any]]:
        """List all strategies"""
        strategies = []
        for strategy_id, strategy in self._strategies.items():
            strategies.append({
                'id': strategy_id,
                'type': strategy.config.get('type', 'unknown'),
                'running': strategy_id in self._running_strategies
            })
        return strategies
    
    # ========================================
    # LIFECYCLE MANAGEMENT
    # ========================================
    
    async def start(self) -> None:
        """Start the strategy runner"""
        self._running = True
        self.logger.info("StrategyRunner started")
    
    async def stop(self) -> None:
        """Stop the strategy runner"""
        self._running = False
        
        # Stop all running strategies
        for strategy_id in list(self._running_strategies.keys()):
            await self.stop_strategy(strategy_id)
        
        self.logger.info("StrategyRunner stopped")
    
    async def health_check(self) -> bool:
        """Check runner health"""
        try:
            self.redis.ping()
            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False


# ========================================
# DEPENDENCY INJECTION
# ========================================

_strategy_runner: Optional[StrategyRunner] = None


def get_strategy_runner() -> StrategyRunner:
    """Get singleton instance of StrategyRunner"""
    global _strategy_runner
    if _strategy_runner is None:
        _strategy_runner = StrategyRunner()
    return _strategy_runner


def reset_strategy_runner() -> None:
    """Reset the strategy runner (for testing)"""
    global _strategy_runner
    if _strategy_runner:
        asyncio.create_task(_strategy_runner.stop())
    _strategy_runner = None


# ========================================
# EXPORTS
# ========================================

__all__ = [
    'StrategyRunner',
    'BaseStrategy',
    'TrendFollowingStrategy',
    'MeanReversionStrategy',
    'MomentumStrategy',
    'StrategyType',
    'OrderSide',
    'OrderType',
    'OrderStatus',
    'Order',
    'Position',
    'Trade',
    'StrategyResult',
    'get_strategy_runner',
    'reset_strategy_runner'
]
