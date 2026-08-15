"""
Swing Bot Pair Trading Model
==============================

This module provides pair trading models for the Swing Bot trading system.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from trading.bots.swing_bot.utils.math_utils import MathUtils
from scipy import stats
import warnings
warnings.filterwarnings('ignore')


@dataclass
class Pair:
    """Trading pair data structure."""
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
    status: str = 'neutral'  # 'long', 'short', 'neutral'


@dataclass
class PairTrade:
    """Pair trade data structure."""
    pair_id: str
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
class PairSignal:
    """Pair trading signal."""
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


class PairTradingModel:
    """
    Pair trading model for statistical arbitrage.
    
    Identifies and trades pairs of cointegrated assets.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the pair trading model.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.pairs: Dict[str, Pair] = {}
        self.trades: List[PairTrade] = []
        self.lookback_period = self.config.get('lookback_period', 50)
        self.correlation_threshold = self.config.get('correlation_threshold', 0.70)
        self.cointegration_threshold = self.config.get('cointegration_threshold', 0.05)
        self.entry_zscore = self.config.get('entry_zscore', 2.0)
        self.exit_zscore = self.config.get('exit_zscore', 0.5)
        self.confidence_threshold = self.config.get('confidence_threshold', 0.60)
        
    def analyze(self, df1: pd.DataFrame, df2: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze pair relationship.
        
        Args:
            df1: Data for first asset
            df2: Data for second asset
            
        Returns:
            Pair analysis results
        """
        if len(df1) < self.lookback_period or len(df2) < self.lookback_period:
            return {'status': 'insufficient_data'}
        
        # Align data
        aligned = self._align_data(df1, df2)
        
        if len(aligned) < self.lookback_period:
            return {'status': 'insufficient_data'}
        
        # Calculate metrics
        correlation = self._calculate_correlation(aligned)
        cointegration = self._calculate_cointegration(aligned)
        hedge_ratio, spread_mean, spread_std = self._calculate_spread_stats(aligned)
        half_life = self._calculate_half_life(aligned, hedge_ratio)
        
        # Calculate current z-score
        current_spread = aligned['price1'].iloc[-1] - hedge_ratio * aligned['price2'].iloc[-1]
        zscore = (current_spread - spread_mean) / spread_std if spread_std > 0 else 0
        
        # Determine pair status
        status = 'neutral'
        if zscore > self.entry_zscore:
            status = 'short'  # Short spread (sell overvalued asset)
        elif zscore < -self.entry_zscore:
            status = 'long'   # Long spread (buy undervalued asset)
        
        return {
            'status': status,
            'correlation': correlation,
            'cointegration': cointegration,
            'hedge_ratio': hedge_ratio,
            'spread_mean': spread_mean,
            'spread_std': spread_std,
            'half_life': half_life,
            'zscore': zscore,
            'entry_zscore': self.entry_zscore,
            'exit_zscore': self.exit_zscore,
            'current_spread': current_spread,
            'price1': aligned['price1'].iloc[-1],
            'price2': aligned['price2'].iloc[-1]
        }
    
    def _align_data(self, df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
        """
        Align two dataframes by index.
        
        Args:
            df1: First dataframe
            df2: Second dataframe
            
        Returns:
            Aligned dataframe
        """
        # Get common dates
        dates = df1.index.intersection(df2.index)
        
        if len(dates) == 0:
            return pd.DataFrame()
        
        aligned = pd.DataFrame({
            'price1': df1.loc[dates, 'close'],
            'price2': df2.loc[dates, 'close']
        })
        
        return aligned
    
    def _calculate_correlation(self, data: pd.DataFrame) -> float:
        """
        Calculate correlation between two assets.
        
        Args:
            data: Aligned price data
            
        Returns:
            Correlation coefficient
        """
        if len(data) < 2:
            return 0.0
        
        return MathUtils.correlation(data['price1'].values, data['price2'].values)
    
    def _calculate_cointegration(self, data: pd.DataFrame) -> float:
        """
        Calculate cointegration between two assets.
        
        Args:
            data: Aligned price data
            
        Returns:
            Cointegration p-value
        """
        if len(data) < 30:
            return 1.0
        
        # Perform Engle-Granger cointegration test
        from statsmodels.tsa.stattools import coint
        
        price1 = data['price1'].values
        price2 = data['price2'].values
        
        try:
            score, p_value, _ = coint(price1, price2)
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
        
        # Calculate spread
        spread = data['price1'].values - hedge_ratio * data['price2'].values
        
        # Calculate half-life using OLS
        spread_lag = spread[:-1]
        spread_diff = np.diff(spread)
        
        slope, intercept = MathUtils.linear_regression(spread_lag, spread_diff)
        
        if slope >= 0:
            return float('inf')
        
        return -np.log(2) / slope
    
    def generate_signal(self, df1: pd.DataFrame, df2: pd.DataFrame) -> Optional[PairSignal]:
        """
        Generate trading signal for a pair.
        
        Args:
            df1: Data for first asset
            df2: Data for second asset
            
        Returns:
            PairSignal or None
        """
        analysis = self.analyze(df1, df2)
        
        if analysis['status'] == 'insufficient_data':
            return None
        
        # Check conditions
        if (abs(analysis['zscore']) < self.entry_zscore or
            analysis['correlation'] < self.correlation_threshold or
            analysis['cointegration'] > self.cointegration_threshold):
            return None
        
        confidence = min(abs(analysis['zscore']) / (self.entry_zscore * 2), 1.0)
        
        if confidence < self.confidence_threshold:
            return None
        
        # Determine signal type
        if analysis['zscore'] > self.entry_zscore:
            signal_type = 'short_spread'
            reason = f"Spread is overextended (z-score: {analysis['zscore']:.2f})"
            target = analysis['spread_mean'] + self.exit_zscore * analysis['spread_std']
            stop_loss = analysis['spread_mean'] + (self.entry_zscore + 0.5) * analysis['spread_std']
        else:
            signal_type = 'long_spread'
            reason = f"Spread is compressed (z-score: {analysis['zscore']:.2f})"
            target = analysis['spread_mean'] - self.exit_zscore * analysis['spread_std']
            stop_loss = analysis['spread_mean'] - (self.entry_zscore + 0.5) * analysis['spread_std']
        
        return PairSignal(
            symbol1=df1.get('symbol', [''])[0] if 'symbol' in df1.columns else '',
            symbol2=df2.get('symbol', [''])[0] if 'symbol' in df2.columns else '',
            timestamp=datetime.now(),
            signal_type=signal_type,
            confidence=confidence,
            price1=analysis['price1'],
            price2=analysis['price2'],
            spread=analysis['current_spread'],
            zscore=analysis['zscore'],
            target=target,
            stop_loss=stop_loss,
            reason=reason,
            indicators={
                'correlation': analysis['correlation'],
                'cointegration': analysis['cointegration'],
                'hedge_ratio': analysis['hedge_ratio'],
                'half_life': analysis['half_life']
            }
        )
    
    def execute_trade(self, signal: PairSignal, quantity1: float, quantity2: float) -> PairTrade:
        """
        Execute a pair trade.
        
        Args:
            signal: PairSignal object
            quantity1: Quantity of first asset
            quantity2: Quantity of second asset
            
        Returns:
            PairTrade object
        """
        trade = PairTrade(
            pair_id=f"{signal.symbol1}_{signal.symbol2}_{int(datetime.now().timestamp())}",
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
    
    def close_trade(self, trade_id: str, exit_spread: float) -> Optional[PairTrade]:
        """
        Close a pair trade.
        
        Args:
            trade_id: Trade ID
            exit_spread: Exit spread
            
        Returns:
            Closed PairTrade or None
        """
        for trade in self.trades:
            if trade.pair_id == trade_id and trade.status == 'open':
                trade.exit_time = datetime.now()
                trade.exit_spread = exit_spread
                trade.status = 'closed'
                
                # Calculate PnL
                spread_change = exit_spread - trade.entry_spread
                trade.pnl = spread_change * (trade.quantity1 + trade.quantity2)
                trade.pnl_percent = trade.pnl / (trade.quantity1 * trade.quantity1 + trade.quantity2 * trade.quantity2) if (trade.quantity1 + trade.quantity2) > 0 else 0
                
                return trade
        
        return None
    
    def get_open_trades(self) -> List[PairTrade]:
        """
        Get all open pair trades.
        
        Returns:
            List of open trades
        """
        return [t for t in self.trades if t.status == 'open']
    
    def get_closed_trades(self) -> List[PairTrade]:
        """
        Get all closed pair trades.
        
        Returns:
            List of closed trades
        """
        return [t for t in self.trades if t.status == 'closed']
    
    def get_pair_performance(self) -> Dict[str, Any]:
        """
        Get pair trading performance.
        
        Returns:
            Performance metrics
        """
        closed_trades = self.get_closed_trades()
        
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


def create_pair_trading_model(config: Optional[Dict[str, Any]] = None) -> PairTradingModel:
    """
    Create a pair trading model instance.
    
    Args:
        config: Model configuration
        
    Returns:
        PairTradingModel instance
    """
    return PairTradingModel(config)


__all__ = [
    'Pair',
    'PairTrade',
    'PairSignal',
    'PairTradingModel',
    'create_pair_trading_model'
]
