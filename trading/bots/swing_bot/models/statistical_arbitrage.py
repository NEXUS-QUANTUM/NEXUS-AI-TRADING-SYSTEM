"""
Swing Bot Statistical Arbitrage Model
=======================================

This module provides statistical arbitrage models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
from scipy import stats
from statsmodels.tsa.stattools import coint
import warnings
warnings.filterwarnings('ignore')


@dataclass
class StatArbPair:
    """Statistical arbitrage pair data structure."""
    symbol1: str
    symbol2: str
    correlation: float
    cointegration: float
    spread_mean: float
    spread_std: float
    hedge_ratio: float
    half_life: float
    zscore: float
    entry_zscore: float
    exit_zscore: float
    spread: float
    status: str = 'neutral'  # 'long', 'short', 'neutral'


@dataclass
class StatArbTrade:
    """Statistical arbitrage trade data structure."""
    trade_id: str
    symbol1: str
    symbol2: str
    entry_time: datetime
    exit_time: Optional[datetime] = None
    entry_spread: float = 0.0
    exit_spread: float = 0.0
    quantity1: float = 0.0
    quantity2: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0
    status: str = 'open'  # 'open', 'closed'


@dataclass
class StatArbSignal:
    """Statistical arbitrage trading signal."""
    symbol1: str
    symbol2: str
    timestamp: datetime
    signal_type: str  # 'long_spread', 'short_spread'
    confidence: float
    price1: float
    price2: float
    spread: float
    zscore: float
    target: float
    stop_loss: float
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)


class StatisticalArbitrageModel:
    """
    Statistical arbitrage model for quantitative trading.
    
    Implements cointegration-based pair trading strategies.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the statistical arbitrage model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.pairs: Dict[str, StatArbPair] = {}
        self.trades: List[StatArbTrade] = []
        self.lookback_period = self.config.get('lookback_period', 100)
        self.correlation_threshold = self.config.get('correlation_threshold', 0.70)
        self.cointegration_threshold = self.config.get('cointegration_threshold', 0.05)
        self.entry_zscore = self.config.get('entry_zscore', 2.0)
        self.exit_zscore = self.config.get('exit_zscore', 0.5)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
    def analyze(self, df_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Analyze statistical arbitrage opportunities.
        
        Args:
            df_dict: Dictionary of asset dataframes
            
        Returns:
            Analysis results
        """
        if len(df_dict) < 2:
            return {'status': 'insufficient_assets'}
        
        # Calculate correlations and cointegration
        pairs = self._find_pairs(df_dict)
        
        # Generate signals
        signals = self._generate_signals(df_dict, pairs)
        
        return {
            'pairs': pairs,
            'signals': signals,
            'active_trades': self.get_open_trades(),
            'market_character': self._get_market_character(pairs)
        }
    
    def _find_pairs(self, df_dict: Dict[str, pd.DataFrame]) -> List[StatArbPair]:
        """
        Find cointegrated pairs.
        
        Args:
            df_dict: Dictionary of asset dataframes
            
        Returns:
            List of StatArbPair objects
        """
        pairs = []
        symbols = list(df_dict.keys())
        
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                symbol1 = symbols[i]
                symbol2 = symbols[j]
                
                df1 = df_dict[symbol1]
                df2 = df_dict[symbol2]
                
                if len(df1) < self.lookback_period or len(df2) < self.lookback_period:
                    continue
                
                # Align data
                aligned = self._align_data(df1, df2)
                
                if len(aligned) < self.lookback_period:
                    continue
                
                # Calculate metrics
                correlation = MathUtils.correlation(aligned['price1'].values, aligned['price2'].values)
                
                if abs(correlation) < self.correlation_threshold:
                    continue
                
                # Calculate cointegration
                p_value = self._calculate_cointegration(aligned)
                
                if p_value > self.cointegration_threshold:
                    continue
                
                # Calculate spread statistics
                hedge_ratio, spread_mean, spread_std = self._calculate_spread_stats(aligned)
                
                # Calculate half-life
                half_life = self._calculate_half_life(aligned, hedge_ratio)
                
                # Calculate current z-score
                current_spread = aligned['price1'].iloc[-1] - hedge_ratio * aligned['price2'].iloc[-1]
                zscore = (current_spread - spread_mean) / spread_std if spread_std > 0 else 0
                
                # Determine status
                status = 'neutral'
                if zscore > self.entry_zscore:
                    status = 'short'
                elif zscore < -self.entry_zscore:
                    status = 'long'
                
                pair = StatArbPair(
                    symbol1=symbol1,
                    symbol2=symbol2,
                    correlation=correlation,
                    cointegration=p_value,
                    spread_mean=spread_mean,
                    spread_std=spread_std,
                    hedge_ratio=hedge_ratio,
                    half_life=half_life,
                    zscore=zscore,
                    entry_zscore=self.entry_zscore,
                    exit_zscore=self.exit_zscore,
                    spread=current_spread,
                    status=status
                )
                
                pairs.append(pair)
                self.pairs[f"{symbol1}_{symbol2}"] = pair
        
        return pairs
    
    def _align_data(self, df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
        """
        Align two dataframes.
        
        Args:
            df1: First dataframe
            df2: Second dataframe
            
        Returns:
            Aligned dataframe
        """
        dates = df1.index.intersection(df2.index)
        
        if len(dates) == 0:
            return pd.DataFrame()
        
        aligned = pd.DataFrame({
            'price1': df1.loc[dates, 'close'],
            'price2': df2.loc[dates, 'close']
        })
        
        return aligned
    
    def _calculate_cointegration(self, data: pd.DataFrame) -> float:
        """
        Calculate cointegration p-value.
        
        Args:
            data: Aligned price data
            
        Returns:
            Cointegration p-value
        """
        if len(data) < 30:
            return 1.0
        
        price1 = data['price1'].values
        price2 = data['price2'].values
        
        try:
            _, p_value, _ = coint(price1, price2)
            return p_value
        except:
            return 1.0
    
    def _calculate_spread_stats(self, data: pd.DataFrame) -> Tuple[float, float, float]:
        """
        Calculate spread statistics.
        
        Args:
            data: Aligned price data
            
        Returns:
            Tuple of (hedge_ratio, spread_mean, spread_std)
        """
        if len(data) < 2:
            return 1.0, 0.0, 1.0
        
        # Calculate hedge ratio using linear regression
        slope, intercept = MathUtils.linear_regression(
            data['price2'].values,
            data['price1'].values
        )
        
        # Calculate spread
        spread = data['price1'].values - slope * data['price2'].values
        spread_mean = np.mean(spread)
        spread_std = np.std(spread)
        
        return slope, spread_mean, spread_std
    
    def _calculate_half_life(self, data: pd.DataFrame, hedge_ratio: float) -> float:
        """
        Calculate half-life of mean reversion.
        
        Args:
            data: Aligned price data
            hedge_ratio: Hedge ratio
            
        Returns:
            Half-life in periods
        """
        if len(data) < 3:
            return float('inf')
        
        spread = data['price1'].values - hedge_ratio * data['price2'].values
        spread_lag = spread[:-1]
        spread_diff = np.diff(spread)
        
        slope, intercept = MathUtils.linear_regression(spread_lag, spread_diff)
        
        if slope >= 0:
            return float('inf')
        
        return -np.log(2) / slope
    
    def _generate_signals(self, df_dict: Dict[str, pd.DataFrame],
                         pairs: List[StatArbPair]) -> List[StatArbSignal]:
        """
        Generate trading signals for statistical arbitrage.
        
        Args:
            df_dict: Dictionary of asset dataframes
            pairs: List of StatArbPair objects
            
        Returns:
            List of StatArbSignal objects
        """
        signals = []
        
        for pair in pairs:
            if abs(pair.zscore) < self.entry_zscore:
                continue
            
            if pair.cointegration > self.cointegration_threshold:
                continue
            
            confidence = min(abs(pair.zscore) / (self.entry_zscore * 2), 1.0)
            
            if confidence < self.confidence_threshold:
                continue
            
            df1 = df_dict[pair.symbol1]
            df2 = df_dict[pair.symbol2]
            
            current_price1 = df1['close'].iloc[-1]
            current_price2 = df2['close'].iloc[-1]
            
            # Determine signal type
            if pair.zscore > self.entry_zscore:
                signal_type = 'short_spread'
                reason = f"Spread is overextended (z-score: {pair.zscore:.2f})"
                target = pair.spread_mean + self.exit_zscore * pair.spread_std
                stop_loss = pair.spread_mean + (self.entry_zscore + 0.5) * pair.spread_std
            else:
                signal_type = 'long_spread'
                reason = f"Spread is compressed (z-score: {pair.zscore:.2f})"
                target = pair.spread_mean - self.exit_zscore * pair.spread_std
                stop_loss = pair.spread_mean - (self.entry_zscore + 0.5) * pair.spread_std
            
            signal = StatArbSignal(
                symbol1=pair.symbol1,
                symbol2=pair.symbol2,
                timestamp=datetime.now(),
                signal_type=signal_type,
                confidence=confidence,
                price1=current_price1,
                price2=current_price2,
                spread=pair.spread,
                zscore=pair.zscore,
                target=target,
                stop_loss=stop_loss,
                reason=reason,
                indicators={
                    'correlation': pair.correlation,
                    'cointegration': pair.cointegration,
                    'hedge_ratio': pair.hedge_ratio,
                    'half_life': pair.half_life
                }
            )
            signals.append(signal)
        
        return signals
    
    def execute_trade(self, signal: StatArbSignal, quantity1: float, quantity2: float) -> StatArbTrade:
        """
        Execute a statistical arbitrage trade.
        
        Args:
            signal: StatArbSignal object
            quantity1: Quantity of first asset
            quantity2: Quantity of second asset
            
        Returns:
            StatArbTrade object
        """
        trade = StatArbTrade(
            trade_id=f"statarb_{int(datetime.now().timestamp())}",
            symbol1=signal.symbol1,
            symbol2=signal.symbol2,
            entry_time=datetime.now(),
            entry_spread=signal.spread,
            quantity1=quantity1,
            quantity2=quantity2,
            status='open'
        )
        
        self.trades.append(trade)
        return trade
    
    def close_trade(self, trade_id: str, exit_spread: float) -> Optional[StatArbTrade]:
        """
        Close a statistical arbitrage trade.
        
        Args:
            trade_id: Trade ID
            exit_spread: Exit spread
            
        Returns:
            Closed StatArbTrade or None
        """
        for trade in self.trades:
            if trade.trade_id == trade_id and trade.status == 'open':
                trade.exit_time = datetime.now()
                trade.exit_spread = exit_spread
                trade.status = 'closed'
                
                # Calculate PnL
                spread_change = exit_spread - trade.entry_spread
                trade.pnl = spread_change * (trade.quantity1 + trade.quantity2)
                trade.pnl_percent = trade.pnl / (trade.quantity1 * trade.quantity1 + trade.quantity2 * trade.quantity2) if (trade.quantity1 + trade.quantity2) > 0 else 0
                
                return trade
        
        return None
    
    def get_open_trades(self) -> List[StatArbTrade]:
        """
        Get open statistical arbitrage trades.
        
        Returns:
            List of open trades
        """
        return [t for t in self.trades if t.status == 'open']
    
    def get_trade_performance(self) -> Dict[str, Any]:
        """
        Get statistical arbitrage performance.
        
        Returns:
            Performance metrics
        """
        closed_trades = [t for t in self.trades if t.status == 'closed']
        
        if not closed_trades:
            return {'total_trades': 0, 'win_rate': 0, 'avg_return': 0, 'total_pnl': 0}
        
        wins = [t for t in closed_trades if t.pnl > 0]
        losses = [t for t in closed_trades if t.pnl < 0]
        
        total_pnl = sum(t.pnl for t in closed_trades)
        win_rate = len(wins) / len(closed_trades) if closed_trades else 0
        avg_return = np.mean([t.pnl_percent for t in closed_trades]) if closed_trades else 0
        
        return {
            'total_trades': len(closed_trades),
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate': win_rate,
            'avg_return': avg_return,
            'total_pnl': total_pnl,
            'best_trade': max(closed_trades, key=lambda t: t.pnl_percent) if closed_trades else None,
            'worst_trade': min(closed_trades, key=lambda t: t.pnl_percent) if closed_trades else None
        }
    
    def _get_market_character(self, pairs: List[StatArbPair]) -> str:
        """
        Get market character description.
        
        Args:
            pairs: List of StatArbPair objects
            
        Returns:
            Market character description
        """
        if not pairs:
            return "No cointegrated pairs found"
        
        num_pairs = len(pairs)
        avg_correlation = np.mean([p.correlation for p in pairs])
        
        return f"{num_pairs} cointegrated pairs found (avg corr: {avg_correlation:.2f})"


def create_statistical_arbitrage_model(config: Optional[Dict[str, Any]] = None) -> StatisticalArbitrageModel:
    """
    Create a statistical arbitrage model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        StatisticalArbitrageModel instance
    """
    return StatisticalArbitrageModel(config)


__all__ = [
    'StatArbPair',
    'StatArbTrade',
    'StatArbSignal',
    'StatisticalArbitrageModel',
    'create_statistical_arbitrage_model'
]
