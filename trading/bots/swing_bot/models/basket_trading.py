"""
Swing Bot Basket Trading Model
================================

This module provides basket trading models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
from trading.bots.swing_bot.utils.validators import Validator


@dataclass
class BasketTrade:
    """Basket trade data structure."""
    basket_id: str
    assets: List[Dict[str, Any]]
    weights: Dict[str, float]
    entry_price: Dict[str, float]
    current_price: Dict[str, float]
    total_value: float
    pnl: float
    pnl_percent: float
    entry_time: datetime
    exit_time: Optional[datetime] = None
    status: str = 'open'  # 'open', 'closed', 'pending'


@dataclass
class BasketSignal:
    """Basket trading signal."""
    basket_id: str
    symbol: str
    timestamp: datetime
    signal_type: str  # 'buy', 'sell', 'short', 'cover'
    confidence: float
    price: float
    target: float
    stop_loss: float
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class BasketTradingModel:
    """
    Basket trading model for correlated assets.
    
    Implements strategies for trading baskets of correlated assets.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the basket trading model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.baskets: Dict[str, List[str]] = {}
        self.correlations: Dict[str, Dict[str, float]] = {}
        self.trades: List[BasketTrade] = []
        self.lookback_period = self.config.get('lookback_period', 50)
        self.correlation_threshold = self.config.get('correlation_threshold', 0.70)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        self.max_basket_size = self.config.get('max_basket_size', 10)
        
    def analyze(self, df_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Analyze basket trading opportunities.
        
        Args:
            df_dict: Dictionary of asset dataframes
            
        Returns:
            Basket analysis results
        """
        if not df_dict:
            return {'baskets': [], 'signals': [], 'correlations': {}}
        
        # Calculate correlations
        correlations = self._calculate_correlations(df_dict)
        
        # Detect baskets
        baskets = self._detect_baskets(df_dict, correlations)
        
        # Generate signals
        signals = self._generate_signals(df_dict, baskets)
        
        # Update current trades
        self._update_trades(df_dict)
        
        return {
            'baskets': baskets,
            'signals': signals,
            'correlations': correlations,
            'current_trades': self.get_open_trades(),
            'market_character': self._get_market_character(df_dict, baskets)
        }
    
    def _calculate_correlations(self, df_dict: Dict[str, pd.DataFrame]) -> Dict[str, Dict[str, float]]:
        """
        Calculate correlations between assets.
        
        Args:
            df_dict: Dictionary of asset dataframes
            
        Returns:
            Correlation matrix
        """
        # Get returns for each asset
        returns = {}
        for symbol, df in df_dict.items():
            if len(df) > 1:
                returns[symbol] = df['close'].pct_change().dropna().values[-self.lookback_period:]
            else:
                returns[symbol] = np.zeros(1)
        
        # Calculate correlations
        correlations = {}
        symbols = list(returns.keys())
        
        for i, symbol1 in enumerate(symbols):
            correlations[symbol1] = {}
            for j, symbol2 in enumerate(symbols):
                if i == j:
                    correlations[symbol1][symbol2] = 1.0
                else:
                    if len(returns[symbol1]) > 0 and len(returns[symbol2]) > 0:
                        corr = MathUtils.correlation(returns[symbol1], returns[symbol2])
                        correlations[symbol1][symbol2] = corr
                    else:
                        correlations[symbol1][symbol2] = 0.0
        
        self.correlations = correlations
        return correlations
    
    def _detect_baskets(self, df_dict: Dict[str, pd.DataFrame],
                       correlations: Dict[str, Dict[str, float]]) -> List[List[str]]:
        """
        Detect baskets of correlated assets.
        
        Args:
            df_dict: Dictionary of asset dataframes
            correlations: Correlation matrix
            
        Returns:
            List of baskets
        """
        baskets = []
        symbols = list(correlations.keys())
        
        # Find clusters of highly correlated assets
        for i, symbol1 in enumerate(symbols):
            basket = [symbol1]
            
            for j, symbol2 in enumerate(symbols):
                if i != j and symbol2 not in basket:
                    corr = correlations[symbol1].get(symbol2, 0)
                    if abs(corr) > self.correlation_threshold:
                        # Check if symbol2 is correlated with all assets in basket
                        is_related = True
                        for asset in basket:
                            if asset != symbol1:
                                corr2 = correlations[asset].get(symbol2, 0)
                                if abs(corr2) < self.correlation_threshold:
                                    is_related = False
                                    break
                        if is_related:
                            basket.append(symbol2)
            
            if len(basket) >= 2 and len(basket) <= self.max_basket_size:
                # Check if basket already exists
                is_duplicate = False
                for existing in baskets:
                    if set(existing) == set(basket):
                        is_duplicate = True
                        break
                if not is_duplicate:
                    baskets.append(basket)
        
        self.baskets = {f"basket_{i}": basket for i, basket in enumerate(baskets)}
        return baskets
    
    def _generate_signals(self, df_dict: Dict[str, pd.DataFrame],
                         baskets: List[List[str]]) -> List[BasketSignal]:
        """
        Generate trading signals from baskets.
        
        Args:
            df_dict: Dictionary of asset dataframes
            baskets: List of baskets
            
        Returns:
            List of BasketSignal objects
        """
        signals = []
        
        for basket in baskets:
            # Analyze basket
            basket_data = {asset: df_dict[asset] for asset in basket if asset in df_dict}
            
            if not basket_data:
                continue
            
            # Calculate basket metrics
            metrics = self._calculate_basket_metrics(basket_data)
            
            # Generate signal if conditions met
            if metrics['confidence'] > self.confidence_threshold:
                signal = BasketSignal(
                    basket_id=f"basket_{baskets.index(basket)}",
                    symbol=','.join(basket),
                    timestamp=datetime.now(),
                    signal_type=metrics['signal_type'],
                    confidence=metrics['confidence'],
                    price=metrics['price'],
                    target=metrics['target'],
                    stop_loss=metrics['stop_loss'],
                    reason=metrics['reason'],
                    indicators=metrics['indicators']
                )
                signals.append(signal)
        
        return signals
    
    def _calculate_basket_metrics(self, basket_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Calculate metrics for a basket of assets.
        
        Args:
            basket_data: Dictionary of asset dataframes
            
        Returns:
            Basket metrics
        """
        if not basket_data:
            return {'confidence': 0, 'signal_type': 'hold'}
        
        # Calculate average metrics
        avg_return = 0
        avg_volume = 0
        avg_volatility = 0
        count = 0
        
        for symbol, df in basket_data.items():
            if len(df) > 1:
                returns = df['close'].pct_change().dropna()
                if len(returns) > 0:
                    avg_return += np.mean(returns)
                    avg_volatility += np.std(returns)
                    avg_volume += df['volume'].iloc[-1] if not df['volume'].empty else 0
                    count += 1
        
        if count == 0:
            return {'confidence': 0, 'signal_type': 'hold'}
        
        avg_return /= count
        avg_volatility /= count
        avg_volume /= count
        
        # Determine signal
        signal_type = 'hold'
        confidence = 0.5
        price = next(iter(basket_data.values()))['close'].iloc[-1]
        
        if avg_return > 0.01 and avg_volatility < 0.02:
            signal_type = 'buy'
            confidence = min(abs(avg_return) / 0.05, 1.0)
            reason = "Positive average return with low volatility"
            target = price * (1 + confidence * 0.5)
            stop_loss = price * (1 - confidence * 0.25)
        elif avg_return < -0.01 and avg_volatility > 0.02:
            signal_type = 'sell'
            confidence = min(abs(avg_return) / 0.05, 1.0)
            reason = "Negative average return with high volatility"
            target = price * (1 - confidence * 0.5)
            stop_loss = price * (1 + confidence * 0.25)
        else:
            reason = "Neutral basket conditions"
            target = price
            stop_loss = price
        
        return {
            'confidence': confidence,
            'signal_type': signal_type,
            'price': price,
            'target': target,
            'stop_loss': stop_loss,
            'reason': reason,
            'indicators': {
                'avg_return': avg_return,
                'avg_volatility': avg_volatility,
                'avg_volume': avg_volume,
                'basket_size': count
            }
        }
    
    def _update_trades(self, df_dict: Dict[str, pd.DataFrame]) -> None:
        """
        Update current basket trades.
        
        Args:
            df_dict: Dictionary of asset dataframes
        """
        for trade in self.get_open_trades():
            # Update prices
            for asset, price in trade.current_price.items():
                if asset in df_dict and not df_dict[asset]['close'].empty:
                    trade.current_price[asset] = df_dict[asset]['close'].iloc[-1]
            
            # Update total value and PnL
            total_value = 0
            for asset, qty in trade.weights.items():
                if asset in trade.current_price:
                    total_value += qty * trade.current_price[asset]
            
            trade.total_value = total_value
            trade.pnl = total_value - trade.total_value
            trade.pnl_percent = trade.pnl / trade.total_value if trade.total_value != 0 else 0
    
    def create_basket_trade(self, basket_id: str,
                           weights: Dict[str, float],
                           entry_prices: Dict[str, float]) -> BasketTrade:
        """
        Create a new basket trade.
        
        Args:
            basket_id: Basket ID
            weights: Asset weights
            entry_prices: Entry prices
            
        Returns:
            BasketTrade object
        """
        # Validate basket
        if basket_id not in self.baskets:
            raise ValueError(f"Basket {basket_id} not found")
        
        # Create trade
        trade = BasketTrade(
            basket_id=basket_id,
            assets=[{'symbol': symbol, 'weight': weights.get(symbol, 0)} 
                   for symbol in self.baskets[basket_id]],
            weights=weights,
            entry_price=entry_prices,
            current_price=entry_prices.copy(),
            total_value=sum(weights.get(symbol, 0) * entry_prices.get(symbol, 0) 
                          for symbol in self.baskets[basket_id]),
            pnl=0.0,
            pnl_percent=0.0,
            entry_time=datetime.now(),
            status='open'
        )
        
        self.trades.append(trade)
        return trade
    
    def close_trade(self, trade_id: int, exit_prices: Dict[str, float]) -> Optional[BasketTrade]:
        """
        Close a basket trade.
        
        Args:
            trade_id: Trade index
            exit_prices: Exit prices
            
        Returns:
            Closed BasketTrade or None
        """
        if trade_id >= len(self.trades):
            return None
        
        trade = self.trades[trade_id]
        
        if trade.status != 'open':
            return None
        
        # Update with exit prices
        for asset, price in exit_prices.items():
            if asset in trade.current_price:
                trade.current_price[asset] = price
        
        # Calculate final PnL
        total_exit_value = 0
        total_entry_value = 0
        for asset, qty in trade.weights.items():
            if asset in exit_prices and asset in trade.entry_price:
                total_exit_value += qty * exit_prices[asset]
                total_entry_value += qty * trade.entry_price[asset]
        
        trade.total_value = total_exit_value
        trade.pnl = total_exit_value - total_entry_value
        trade.pnl_percent = (total_exit_value - total_entry_value) / total_entry_value if total_entry_value != 0 else 0
        trade.status = 'closed'
        trade.exit_time = datetime.now()
        
        return trade
    
    def get_open_trades(self) -> List[BasketTrade]:
        """
        Get all open basket trades.
        
        Returns:
            List of open BasketTrade objects
        """
        return [t for t in self.trades if t.status == 'open']
    
    def get_closed_trades(self) -> List[BasketTrade]:
        """
        Get all closed basket trades.
        
        Returns:
            List of closed BasketTrade objects
        """
        return [t for t in self.trades if t.status == 'closed']
    
    def get_basket_performance(self) -> Dict[str, Any]:
        """
        Get basket trading performance.
        
        Returns:
            Performance metrics
        """
        closed_trades = self.get_closed_trades()
        open_trades = self.get_open_trades()
        
        if not closed_trades:
            return {'total_trades': 0, 'win_rate': 0, 'avg_return': 0, 'total_pnl': 0}
        
        wins = [t for t in closed_trades if t.pnl > 0]
        losses = [t for t in closed_trades if t.pnl < 0]
        
        total_pnl = sum(t.pnl for t in closed_trades)
        win_rate = len(wins) / len(closed_trades) if closed_trades else 0
        avg_return = np.mean([t.pnl_percent for t in closed_trades]) if closed_trades else 0
        
        # Calculate open PnL
        open_pnl = sum(t.pnl for t in open_trades) if open_trades else 0
        
        return {
            'total_trades': len(closed_trades),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': win_rate,
            'avg_return': avg_return,
            'total_pnl': total_pnl,
            'open_pnl': open_pnl,
            'total_pnl_including_open': total_pnl + open_pnl,
            'best_trade': max(closed_trades, key=lambda t: t.pnl_percent) if closed_trades else None,
            'worst_trade': min(closed_trades, key=lambda t: t.pnl_percent) if closed_trades else None
        }
    
    def _get_market_character(self, df_dict: Dict[str, pd.DataFrame],
                             baskets: List[List[str]]) -> str:
        """
        Get market character description.
        
        Args:
            df_dict: Dictionary of asset dataframes
            baskets: List of baskets
            
        Returns:
            Market character description
        """
        if not baskets:
            return "No significant baskets detected"
        
        num_baskets = len(baskets)
        avg_size = np.mean([len(b) for b in baskets])
        
        return f"{num_baskets} baskets detected (avg size: {avg_size:.1f})"


def create_basket_trading_model(config: Optional[Dict[str, Any]] = None) -> BasketTradingModel:
    """
    Create a basket trading model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        BasketTradingModel instance
    """
    return BasketTradingModel(config)


__all__ = [
    'BasketTrade',
    'BasketSignal',
    'BasketTradingModel',
    'create_basket_trading_model'
]
