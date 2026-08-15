"""
Swing Bot Portfolio Model
===========================

This module provides portfolio management models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils


@dataclass
class Position:
    """Position data structure."""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    entry_time: datetime
    pnl: float
    pnl_percent: float
    status: str  # 'open', 'closed'


@dataclass
class PortfolioStats:
    """Portfolio statistics."""
    total_value: float
    cash: float
    invested: float
    pnl: float
    pnl_percent: float
    num_positions: int
    max_position: float
    concentration: float
    diversification: float
    sharpe_ratio: float
    volatility: float
    max_drawdown: float


@dataclass
class PortfolioSignal:
    """Portfolio trading signal."""
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    portfolio_stats: PortfolioStats
    indicators: Dict[str, Any] = field(default_factory=dict)


class PortfolioModel:
    """
    Portfolio management model for position sizing and risk management.
    
    Implements portfolio optimization and risk management.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the portfolio model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.initial_capital = self.config.get('initial_capital', 100000)
        self.max_positions = self.config.get('max_positions', 20)
        self.max_position_size = self.config.get('max_position_size', 0.10)
        self.max_sector_exposure = self.config.get('max_sector_exposure', 0.30)
        self.max_drawdown = self.config.get('max_drawdown', 0.15)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
        self.positions: Dict[str, Position] = {}
        self.cash = self.initial_capital
        self.total_value = self.initial_capital
        self.history: List[PortfolioStats] = []
        
    def update_prices(self, prices: Dict[str, float]) -> None:
        """
        Update current prices for all positions.
        
        Args:
            prices: Dictionary of current prices
        """
        for symbol, price in prices.items():
            if symbol in self.positions:
                position = self.positions[symbol]
                position.current_price = price
                position.pnl = (price - position.entry_price) * position.quantity
                position.pnl_percent = (price - position.entry_price) / position.entry_price
        
        self._update_portfolio_stats()
    
    def add_position(self, symbol: str, quantity: float, price: float) -> bool:
        """
        Add a new position.
        
        Args:
            symbol: Asset symbol
            quantity: Quantity to buy
            price: Entry price
            
        Returns:
            True if added, False otherwise
        """
        if len(self.positions) >= self.max_positions:
            return False
        
        # Check if enough cash
        cost = quantity * price
        if cost > self.cash:
            return False
        
        # Check position size limit
        position_value = quantity * price
        if position_value / self.total_value > self.max_position_size:
            return False
        
        # Create position
        position = Position(
            symbol=symbol,
            quantity=quantity,
            entry_price=price,
            current_price=price,
            entry_time=datetime.now(),
            pnl=0.0,
            pnl_percent=0.0,
            status='open'
        )
        
        self.positions[symbol] = position
        self.cash -= cost
        self._update_portfolio_stats()
        
        return True
    
    def remove_position(self, symbol: str, price: float) -> bool:
        """
        Remove a position.
        
        Args:
            symbol: Asset symbol
            price: Exit price
            
        Returns:
            True if removed, False otherwise
        """
        if symbol not in self.positions:
            return False
        
        position = self.positions[symbol]
        value = position.quantity * price
        self.cash += value
        position.status = 'closed'
        
        del self.positions[symbol]
        self._update_portfolio_stats()
        
        return True
    
    def _update_portfolio_stats(self) -> None:
        """Update portfolio statistics."""
        total_position_value = sum(p.quantity * p.current_price for p in self.positions.values())
        self.total_value = self.cash + total_position_value
        
        # Calculate PnL
        total_pnl = sum(p.pnl for p in self.positions.values())
        pnl_percent = (self.total_value - self.initial_capital) / self.initial_capital
        
        # Calculate concentration
        if self.positions:
            position_values = [p.quantity * p.current_price for p in self.positions.values()]
            concentration = max(position_values) / self.total_value if position_values else 0
            diversification = 1 - sum((v / self.total_value) ** 2 for v in position_values) if position_values else 0
        else:
            concentration = 0
            diversification = 0
        
        stats = PortfolioStats(
            total_value=self.total_value,
            cash=self.cash,
            invested=total_position_value,
            pnl=total_pnl,
            pnl_percent=pnl_percent,
            num_positions=len(self.positions),
            max_position=max([p.quantity * p.current_price for p in self.positions.values()]) if self.positions else 0,
            concentration=concentration,
            diversification=diversification,
            sharpe_ratio=0.0,
            volatility=0.0,
            max_drawdown=0.0
        )
        
        self.history.append(stats)
    
    def analyze(self, df_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Analyze portfolio and generate signals.
        
        Args:
            df_dict: Dictionary of asset dataframes
            
        Returns:
            Analysis results
        """
        # Update prices
        prices = {}
        for symbol, df in df_dict.items():
            if len(df) > 0:
                prices[symbol] = df['close'].iloc[-1]
        
        self.update_prices(prices)
        
        # Generate signals
        signals = self._generate_signals(df_dict)
        
        # Calculate risk metrics
        risk_metrics = self._calculate_risk_metrics()
        
        return {
            'signals': signals,
            'portfolio_stats': self.history[-1] if self.history else None,
            'risk_metrics': risk_metrics,
            'positions': self.positions
        }
    
    def _generate_signals(self, df_dict: Dict[str, pd.DataFrame]) -> List[PortfolioSignal]:
        """
        Generate portfolio signals.
        
        Args:
            df_dict: Dictionary of asset dataframes
            
        Returns:
            List of PortfolioSignal objects
        """
        signals = []
        
        # Check if any positions need to be closed
        for symbol, position in self.positions.items():
            if symbol in df_dict:
                df = df_dict[symbol]
                if len(df) > 0:
                    signal = self._check_position_signal(df, position)
                    if signal:
                        signals.append(signal)
        
        # Check for new positions
        for symbol, df in df_dict.items():
            if symbol not in self.positions and len(df) > 0:
                signal = self._check_entry_signal(df, symbol)
                if signal:
                    signals.append(signal)
        
        return signals
    
    def _check_position_signal(self, df: pd.DataFrame, position: Position) -> Optional[PortfolioSignal]:
        """
        Check if a position should be closed.
        
        Args:
            df: OHLCV data
            position: Position object
            
        Returns:
            PortfolioSignal or None
        """
        current_price = df['close'].iloc[-1]
        
        # Check stop loss
        stop_loss = position.entry_price * 0.95
        if current_price <= stop_loss:
            return PortfolioSignal(
                symbol=position.symbol,
                timestamp=datetime.now(),
                signal_type='sell',
                confidence=0.9,
                price=current_price,
                target=current_price * 0.98,
                stop_loss=current_price * 1.02,
                reason="Stop loss triggered",
                portfolio_stats=self.history[-1] if self.history else None,
                indicators={'position_pnl': position.pnl}
            )
        
        # Check take profit
        take_profit = position.entry_price * 1.10
        if current_price >= take_profit:
            return PortfolioSignal(
                symbol=position.symbol,
                timestamp=datetime.now(),
                signal_type='sell',
                confidence=0.8,
                price=current_price,
                target=current_price * 1.05,
                stop_loss=current_price * 0.98,
                reason="Take profit triggered",
                portfolio_stats=self.history[-1] if self.history else None,
                indicators={'position_pnl': position.pnl}
            )
        
        return None
    
    def _check_entry_signal(self, df: pd.DataFrame, symbol: str) -> Optional[PortfolioSignal]:
        """
        Check if a new position should be opened.
        
        Args:
            df: OHLCV data
            symbol: Asset symbol
            
        Returns:
            PortfolioSignal or None
        """
        if len(df) < 20:
            return None
        
        # Check if we can add a position
        if len(self.positions) >= self.max_positions:
            return None
        
        # Calculate signal strength
        close = df['close'].values
        
        # Simple moving average crossover
        ma20 = np.mean(close[-20:])
        ma50 = np.mean(close[-50:]) if len(close) >= 50 else ma20
        
        if ma20 > ma50:
            signal_type = 'buy'
            reason = "Moving average crossover bullish"
            confidence = min((ma20 - ma50) / ma50 * 10, 1.0)
        else:
            return None
        
        if confidence < self.confidence_threshold:
            return None
        
        current_price = close[-1]
        
        return PortfolioSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price=current_price,
            target=current_price * 1.05,
            stop_loss=current_price * 0.95,
            reason=reason,
            portfolio_stats=self.history[-1] if self.history else None,
            indicators={
                'ma20': ma20,
                'ma50': ma50,
                'crossover': ma20 - ma50
            }
        )
    
    def _calculate_risk_metrics(self) -> Dict[str, float]:
        """
        Calculate risk metrics.
        
        Returns:
            Risk metrics dictionary
        """
        metrics = {
            'var_95': 0.0,
            'expected_shortfall': 0.0,
            'max_drawdown': 0.0,
            'volatility': 0.0,
            'sharpe_ratio': 0.0,
            'calmar_ratio': 0.0
        }
        
        if len(self.history) < 2:
            return metrics
        
        # Calculate returns
        returns = []
        for i in range(1, len(self.history)):
            if self.history[i-1].total_value > 0:
                ret = (self.history[i].total_value - self.history[i-1].total_value) / self.history[i-1].total_value
                returns.append(ret)
        
        if not returns:
            return metrics
        
        # Value at Risk
        metrics['var_95'] = np.percentile(returns, 5) * np.sqrt(252)
        
        # Expected Shortfall
        tail_returns = [r for r in returns if r < metrics['var_95']]
        metrics['expected_shortfall'] = np.mean(tail_returns) * np.sqrt(252) if tail_returns else 0
        
        # Volatility
        metrics['volatility'] = np.std(returns) * np.sqrt(252)
        
        # Sharpe Ratio
        metrics['sharpe_ratio'] = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        
        # Maximum Drawdown
        cumulative = np.cumprod(1 + np.array(returns))
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        metrics['max_drawdown'] = np.min(drawdown)
        
        # Calmar Ratio
        if abs(metrics['max_drawdown']) > 0:
            metrics['calmar_ratio'] = np.mean(returns) * 252 / abs(metrics['max_drawdown'])
        else:
            metrics['calmar_ratio'] = 0
        
        return metrics
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get portfolio summary.
        
        Returns:
            Portfolio summary
        """
        return {
            'total_value': self.total_value,
            'cash': self.cash,
            'invested': self.total_value - self.cash,
            'num_positions': len(self.positions),
            'positions': {
                symbol: {
                    'quantity': pos.quantity,
                    'entry_price': pos.entry_price,
                    'current_price': pos.current_price,
                    'pnl': pos.pnl,
                    'pnl_percent': pos.pnl_percent,
                    'entry_time': pos.entry_time.isoformat()
                }
                for symbol, pos in self.positions.items()
            },
            'history_length': len(self.history)
        }


def create_portfolio_model(config: Optional[Dict[str, Any]] = None) -> PortfolioModel:
    """
    Create a portfolio model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        PortfolioModel instance
    """
    return PortfolioModel(config)


__all__ = [
    'Position',
    'PortfolioStats',
    'PortfolioSignal',
    'PortfolioModel',
    'create_portfolio_model'
]
