# trading/strategies/pairs_trading.py
"""
NEXUS AI TRADING SYSTEM - Pairs Trading Strategy
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements pairs trading strategies including:
- Cointegration-based pairs
- Correlation-based pairs
- Distance-based pairs
- Sector-based pairs
- Statistical arbitrage pairs

Pairs trading is a market-neutral strategy that involves trading
two correlated assets to profit from temporary divergences in
their price relationship.
"""

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from collections import deque

import numpy as np
from scipy import stats
from scipy.stats import pearsonr, spearmanr

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType
from shared.types.trading import MarketData, Signal, Position, Trade
from .base import BaseStrategy, StrategyConfig, SignalType, SignalStrength

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class PairSelectionMethod(str, Enum):
    """Methods for selecting trading pairs"""
    COINTEGRATION = "cointegration"
    CORRELATION = "correlation"
    DISTANCE = "distance"
    SECTOR = "sector"
    STATISTICAL = "statistical"
    COMBINED = "combined"


class PairTradingSignal(str, Enum):
    """Types of pairs trading signals"""
    SPREAD_BUY = "spread_buy"   # Buy leg1, Sell leg2 (spread narrows)
    SPREAD_SELL = "spread_sell" # Sell leg1, Buy leg2 (spread widens)
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"
    CLOSE_BOTH = "close_both"


@dataclass
class TradingPair:
    """A trading pair definition"""
    leg1: str
    leg2: str
    hedge_ratio: float = 1.0
    correlation: float = 0.0
    p_value: float = 0.0
    half_life: float = 0.0
    
    # Current state
    spread: float = 0.0
    spread_mean: float = 0.0
    spread_std: float = 0.0
    z_score: float = 0.0
    
    # Trading status
    is_active: bool = False
    entry_spread: float = 0.0
    entry_time: Optional[datetime] = None
    position_count: int = 0
    
    # Metadata
    sector: str = ""
    pair_type: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PairsConfig:
    """Configuration for pairs trading strategy"""
    # Pair selection
    selection_method: PairSelectionMethod = PairSelectionMethod.COIINTEGRATION
    lookback_period: int = 100
    min_correlation: float = 0.7
    max_correlation: float = 0.95
    cointegration_pvalue: float = 0.05
    min_half_life: int = 10
    max_half_life: int = 60
    
    # Trading parameters
    entry_zscore: float = 2.0
    exit_zscore: float = 0.5
    stop_loss_zscore: float = 3.5
    max_holding_period: int = 30  # bars
    
    # Position sizing
    position_size: float = 1000.0
    max_position_size: float = 10000.0
    capital_allocation: float = 0.1  # 10% per pair
    
    # Risk management
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.06
    max_open_pairs: int = 5
    max_exposure: float = 100000.0
    
    # Monitoring
    rebalance_interval: int = 10  # bars
    check_interval: int = 1  # bars
    min_data_points: int = 50
    
    # Execution
    order_type: OrderType = OrderType.LIMIT
    time_in_force: str = "GTC"
    slippage_tolerance: float = 0.005


@dataclass
class PairsState:
    """Current state of pairs trading strategy"""
    symbol: str
    pairs: List[TradingPair] = field(default_factory=list)
    active_pairs: List[TradingPair] = field(default_factory=list)
    closed_trades: List[Dict[str, Any]] = field(default_factory=list)
    
    # Statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_update: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# PAIRS TRADING STRATEGY
# ============================================================================

class PairsTradingStrategy(BaseStrategy):
    """
    Pairs trading strategy that trades correlated assets.
    
    The strategy identifies pairs of assets that move together and
    trades them when their spread deviates from the mean.
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        pairs_config: Optional[PairsConfig] = None,
    ):
        """
        Initialize the pairs trading strategy.
        
        Args:
            config: Strategy configuration
            pairs_config: Pairs trading configuration
        """
        super().__init__(config)
        self.pairs_config = pairs_config or PairsConfig()
        
        # State management
        self._state: Optional[PairsState] = None
        
        # Data storage
        self._price_history: Dict[str, deque] = {}
        self._returns_history: Dict[str, deque] = {}
        
        # Pair tracking
        self._pair_signals: Dict[str, PairTradingSignal] = {}
        self._active_positions: Dict[str, Dict[str, float]] = {}  # pair_id -> {leg1: qty, leg2: qty}
        
        # Performance tracking
        self._pairs_stats = {
            "total_pairs_evaluated": 0,
            "valid_pairs_found": 0,
            "active_pairs": 0,
            "trades_executed": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "avg_spread_reversion": 0.0,
            "avg_holding_period": 0.0,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        self.logger = logger
    
    # ========================================================================
    # PAIR SELECTION
    # ========================================================================
    
    def find_pairs(
        self,
        price_data: Dict[str, List[float]],
        symbols: Optional[List[str]] = None,
    ) -> List[TradingPair]:
        """
        Find trading pairs from price data.
        
        Args:
            price_data: Price data by symbol
            symbols: Optional list of symbols to consider
            
        Returns:
            List[TradingPair]: List of trading pairs
        """
        pairs = []
        symbols = symbols or list(price_data.keys())
        
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                leg1 = symbols[i]
                leg2 = symbols[j]
                
                # Get price series
                prices1 = price_data.get(leg1, [])
                prices2 = price_data.get(leg2, [])
                
                if len(prices1) < self.pairs_config.lookback_period:
                    continue
                if len(prices2) < self.pairs_config.lookback_period:
                    continue
                
                # Trim to same length
                min_len = min(len(prices1), len(prices2))
                prices1 = prices1[-min_len:]
                prices2 = prices2[-min_len:]
                
                # Evaluate pair
                pair = self._evaluate_pair(leg1, leg2, prices1, prices2)
                
                if pair:
                    pairs.append(pair)
                    self._pairs_stats["total_pairs_evaluated"] += 1
        
        # Sort by score
        pairs = self._rank_pairs(pairs)
        
        self._pairs_stats["valid_pairs_found"] = len(pairs)
        
        return pairs
    
    def _evaluate_pair(
        self,
        leg1: str,
        leg2: str,
        prices1: List[float],
        prices2: List[float],
    ) -> Optional[TradingPair]:
        """
        Evaluate a potential trading pair.
        
        Args:
            leg1: First leg symbol
            leg2: Second leg symbol
            prices1: Price series for leg1
            prices2: Price series for leg2
            
        Returns:
            Optional[TradingPair]: Trading pair if valid
        """
        selection_method = self.pairs_config.selection_method
        
        if selection_method == PairSelectionMethod.COIINTEGRATION:
            return self._evaluate_cointegration(leg1, leg2, prices1, prices2)
        
        elif selection_method == PairSelectionMethod.CORRELATION:
            return self._evaluate_correlation(leg1, leg2, prices1, prices2)
        
        elif selection_method == PairSelectionMethod.DISTANCE:
            return self._evaluate_distance(leg1, leg2, prices1, prices2)
        
        elif selection_method == PairSelectionMethod.COMBINED:
            return self._evaluate_combined(leg1, leg2, prices1, prices2)
        
        elif selection_method == PairSelectionMethod.SECTOR:
            # Sector-based selection requires sector data
            return self._evaluate_correlation(leg1, leg2, prices1, prices2)
        
        # Default to cointegration
        return self._evaluate_cointegration(leg1, leg2, prices1, prices2)
    
    def _evaluate_cointegration(
        self,
        leg1: str,
        leg2: str,
        prices1: List[float],
        prices2: List[float],
    ) -> Optional[TradingPair]:
        """
        Evaluate pair using cointegration test.
        
        Args:
            leg1: First leg symbol
            leg2: Second leg symbol
            prices1: Price series for leg1
            prices2: Price series for leg2
            
        Returns:
            Optional[TradingPair]: Trading pair if cointegrated
        """
        if len(prices1) < 30 or len(prices2) < 30:
            return None
        
        # Calculate correlation
        correlation, p_value = pearsonr(prices1, prices2)
        
        if correlation < self.pairs_config.min_correlation:
            return None
        if correlation > self.pairs_config.max_correlation:
            return None
        
        # Test for cointegration using linear regression
        x = np.array(prices1)
        y = np.array(prices2)
        
        # Linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        
        # Calculate spread
        spread = y - slope * x - intercept
        
        # Test for stationarity (ADF test - simplified)
        # Use Hurst exponent as proxy
        hurst = self._calculate_hurst(spread)
        
        # Cointegrated if Hurst < 0.5 (mean-reverting)
        if hurst >= 0.5:
            return None
        
        # Calculate half-life
        half_life = self._calculate_half_life(spread)
        
        if half_life < self.pairs_config.min_half_life:
            return None
        if half_life > self.pairs_config.max_half_life:
            return None
        
        # Create pair
        pair = TradingPair(
            leg1=leg1,
            leg2=leg2,
            hedge_ratio=slope,
            correlation=correlation,
            p_value=p_value,
            half_life=half_life,
            spread=spread[-1],
            spread_mean=np.mean(spread),
            spread_std=np.std(spread),
            z_score=(spread[-1] - np.mean(spread)) / np.std(spread) if np.std(spread) > 0 else 0,
            pair_type="cointegration",
            metadata={
                "slope": slope,
                "intercept": intercept,
                "hurst": hurst,
            },
        )
        
        return pair
    
    def _evaluate_correlation(
        self,
        leg1: str,
        leg2: str,
        prices1: List[float],
        prices2: List[float],
    ) -> Optional[TradingPair]:
        """
        Evaluate pair using correlation analysis.
        
        Args:
            leg1: First leg symbol
            leg2: Second leg symbol
            prices1: Price series for leg1
            prices2: Price series for leg2
            
        Returns:
            Optional[TradingPair]: Trading pair if correlated
        """
        if len(prices1) < 30:
            return None
        
        # Calculate correlation
        correlation, p_value = pearsonr(prices1, prices2)
        
        if correlation < self.pairs_config.min_correlation:
            return None
        if correlation > self.pairs_config.max_correlation:
            return None
        
        # Calculate spread
        normalized1 = (prices1 - np.mean(prices1)) / np.std(prices1)
        normalized2 = (prices2 - np.mean(prices2)) / np.std(prices2)
        spread = normalized1 - normalized2
        
        # Create pair
        pair = TradingPair(
            leg1=leg1,
            leg2=leg2,
            hedge_ratio=1.0,
            correlation=correlation,
            p_value=p_value,
            half_life=self._calculate_half_life(spread),
            spread=spread[-1],
            spread_mean=np.mean(spread),
            spread_std=np.std(spread),
            z_score=(spread[-1] - np.mean(spread)) / np.std(spread) if np.std(spread) > 0 else 0,
            pair_type="correlation",
        )
        
        return pair
    
    def _evaluate_distance(
        self,
        leg1: str,
        leg2: str,
        prices1: List[float],
        prices2: List[float],
    ) -> Optional[TradingPair]:
        """
        Evaluate pair using distance method.
        
        Args:
            leg1: First leg symbol
            leg2: Second leg symbol
            prices1: Price series for leg1
            prices2: Price series for leg2
            
        Returns:
            Optional[TradingPair]: Trading pair if distance is optimal
        """
        if len(prices1) < 30:
            return None
        
        # Calculate normalized distance
        normalized1 = (prices1 - np.mean(prices1)) / np.std(prices1)
        normalized2 = (prices2 - np.mean(prices2)) / np.std(prices2)
        
        # Sum of squared differences
        distance = np.sqrt(np.sum((normalized1 - normalized2) ** 2) / len(prices1))
        
        # Calculate correlation for confirmation
        correlation, _ = pearsonr(prices1, prices2)
        
        if correlation < self.pairs_config.min_correlation:
            return None
        
        # Distance should be small but not too small
        if distance < 0.1 or distance > 1.0:
            return None
        
        spread = normalized1 - normalized2
        
        pair = TradingPair(
            leg1=leg1,
            leg2=leg2,
            hedge_ratio=1.0,
            correlation=correlation,
            p_value=0.0,
            half_life=self._calculate_half_life(spread),
            spread=spread[-1],
            spread_mean=np.mean(spread),
            spread_std=np.std(spread),
            z_score=(spread[-1] - np.mean(spread)) / np.std(spread) if np.std(spread) > 0 else 0,
            pair_type="distance",
            metadata={"distance": distance},
        )
        
        return pair
    
    def _evaluate_combined(
        self,
        leg1: str,
        leg2: str,
        prices1: List[float],
        prices2: List[float],
    ) -> Optional[TradingPair]:
        """
        Evaluate pair using combined methods.
        
        Args:
            leg1: First leg symbol
            leg2: Second leg symbol
            prices1: Price series for leg1
            prices2: Price series for leg2
            
        Returns:
            Optional[TradingPair]: Trading pair if all criteria met
        """
        # Get cointegration evaluation
        coint_pair = self._evaluate_cointegration(leg1, leg2, prices1, prices2)
        
        if not coint_pair:
            return None
        
        # Check additional criteria
        if coint_pair.correlation < self.pairs_config.min_correlation:
            return None
        
        # Enhanced pair with additional metrics
        normalized1 = (prices1 - np.mean(prices1)) / np.std(prices1)
        normalized2 = (prices2 - np.mean(prices2)) / np.std(prices2)
        spread = normalized1 - normalized2
        
        coint_pair.spread = spread[-1]
        coint_pair.spread_mean = np.mean(spread)
        coint_pair.spread_std = np.std(spread)
        coint_pair.z_score = (spread[-1] - np.mean(spread)) / np.std(spread) if np.std(spread) > 0 else 0
        coint_pair.pair_type = "combined"
        
        return coint_pair
    
    def _rank_pairs(self, pairs: List[TradingPair]) -> List[TradingPair]:
        """
        Rank pairs by desirability.
        
        Args:
            pairs: List of trading pairs
            
        Returns:
            List[TradingPair]: Ranked pairs
        """
        for pair in pairs:
            # Calculate score based on multiple factors
            score = 0.0
            
            # Higher correlation is better (but not too high)
            if pair.correlation < 0.9:
                score += pair.correlation * 0.3
            
            # Lower p-value is better (more significant)
            if pair.p_value > 0:
                score += (1 - pair.p_value) * 0.3
            
            # Half-life should be optimal (not too short, not too long)
            if pair.half_life > 0:
                # Optimal half-life around 20-30 periods
                half_life_score = 1 - abs(pair.half_life - 25) / 50
                score += max(0, half_life_score) * 0.2
            
            # Add random factor for diversification
            score += (hash(pair.leg1 + pair.leg2) % 100) / 1000
            
            pair.metadata["score"] = score
        
        # Sort by score descending
        return sorted(pairs, key=lambda x: x.metadata.get("score", 0), reverse=True)
    
    # ========================================================================
    # STATISTICAL HELPERS
    # ========================================================================
    
    def _calculate_hurst(self, series: List[float]) -> float:
        """
        Calculate Hurst exponent for mean reversion detection.
        
        Args:
            series: Time series
            
        Returns:
            float: Hurst exponent (0-1)
        """
        if len(series) < 10:
            return 0.5
        
        series = np.array(series)
        lags = range(2, min(len(series) // 2, 20))
        
        tau = [np.sqrt(np.std(np.subtract(series[lag:], series[:-lag]))) for lag in lags]
        
        try:
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            return poly[0] * 2.0
        except:
            return 0.5
    
    def _calculate_half_life(self, series: List[float]) -> float:
        """
        Calculate half-life of mean reversion.
        
        Args:
            series: Time series
            
        Returns:
            float: Half-life in periods
        """
        if len(series) < 10:
            return 0.0
        
        series = np.array(series)
        lag = series[:-1]
        diff = np.diff(series)
        
        try:
            # Linear regression: diff = alpha * lag + beta
            x = lag.reshape(-1, 1)
            y = diff
            
            beta = np.linalg.lstsq(x, y, rcond=None)[0][0]
            
            if beta >= 0:
                return 0.0
            
            return -np.log(2) / beta
        except:
            return 0.0
    
    # ========================================================================
    # SIGNAL GENERATION
    # ========================================================================
    
    async def generate_signal(
        self,
        market_data: List[MarketData],
    ) -> Optional[Signal]:
        """
        Generate a trading signal based on pairs logic.
        
        Args:
            market_data: Market data
            
        Returns:
            Optional[Signal]: Trading signal
        """
        if not market_data:
            return None
        
        # Update price history
        for candle in market_data:
            if candle.symbol not in self._price_history:
                self._price_history[candle.symbol] = deque(maxlen=200)
            self._price_history[candle.symbol].append(candle.close)
        
        # Initialize state
        if not self._state:
            self._state = PairsState(symbol=self.config.symbol or "multi")
            
            # Find initial pairs
            price_data = {
                symbol: list(history) for symbol, history in self._price_history.items()
            }
            pairs = self.find_pairs(price_data)
            self._state.pairs = pairs
            self.logger.info(f"Found {len(pairs)} trading pairs")
        
        # Update pairs
        await self._update_pairs()
        
        # Check for trading signals
        signal = await self._check_pair_signals()
        
        return signal
    
    async def _update_pairs(self) -> None:
        """
        Update pair statistics and check for opportunities.
        """
        if not self._state:
            return
        
        price_data = {
            symbol: list(history) for symbol, history in self._price_history.items()
        }
        
        for pair in self._state.pairs:
            prices1 = price_data.get(pair.leg1, [])
            prices2 = price_data.get(pair.leg2, [])
            
            if len(prices1) < self.pairs_config.min_data_points:
                continue
            if len(prices2) < self.pairs_config.min_data_points:
                continue
            
            # Trim to same length
            min_len = min(len(prices1), len(prices2))
            prices1 = prices1[-min_len:]
            prices2 = prices2[-min_len:]
            
            # Update spread
            if pair.pair_type in ["cointegration", "combined"]:
                spread = np.array(prices2) - pair.hedge_ratio * np.array(prices1) - pair.metadata.get("intercept", 0)
            else:
                # Normalized spread
                norm1 = (np.array(prices1) - np.mean(prices1)) / np.std(prices1)
                norm2 = (np.array(prices2) - np.mean(prices2)) / np.std(prices2)
                spread = norm1 - norm2
            
            pair.spread = spread[-1]
            pair.spread_mean = np.mean(spread)
            pair.spread_std = np.std(spread)
            
            if pair.spread_std > 0:
                pair.z_score = (pair.spread - pair.spread_mean) / pair.spread_std
            else:
                pair.z_score = 0
    
    async def _check_pair_signals(self) -> Optional[Signal]:
        """
        Check all pairs for trading signals.
        
        Returns:
            Optional[Signal]: Trading signal if found
        """
        if not self._state:
            return None
        
        # Check active pairs for exit signals
        exit_signal = await self._check_exit_signals()
        if exit_signal:
            return exit_signal
        
        # Check for new entry signals
        entry_signal = await self._check_entry_signals()
        if entry_signal:
            return entry_signal
        
        return None
    
    async def _check_entry_signals(self) -> Optional[Signal]:
        """
        Check for entry signals.
        
        Returns:
            Optional[Signal]: Entry signal
        """
        if not self._state:
            return None
        
        # Check if we have too many active pairs
        if len(self._state.active_pairs) >= self.pairs_config.max_open_pairs:
            return None
        
        # Find best opportunity
        best_pair = None
        best_zscore = 0.0
        best_direction = ""
        
        for pair in self._state.pairs:
            if pair.is_active:
                continue
            
            # Check if pair has enough data
            if pair.spread_std == 0:
                continue
            
            # Entry condition: z-score exceeds threshold
            if abs(pair.z_score) > self.pairs_config.entry_zscore:
                # Determine direction
                direction = "long" if pair.z_score > 0 else "short"
                
                # Save if better
                if abs(pair.z_score) > abs(best_zscore):
                    best_pair = pair
                    best_zscore = pair.z_score
                    best_direction = direction
        
        if not best_pair:
            return None
        
        # Create signal
        pair = best_pair
        direction = "long" if pair.z_score > 0 else "short"
        
        # Calculate position sizes
        if direction == "long":
            # Buy leg1, Sell leg2 (spread will narrow)
            leg1_side = OrderSide.BUY
            leg2_side = OrderSide.SELL
            signal_type = SignalType.BUY
            reason = f"Spread {pair.z_score:.2f} - Long leg1, Short leg2"
        else:
            # Sell leg1, Buy leg2 (spread will widen)
            leg1_side = OrderSide.SELL
            leg2_side = OrderSide.BUY
            signal_type = SignalType.SELL
            reason = f"Spread {pair.z_score:.2f} - Short leg1, Long leg2"
        
        # Calculate position size
        position_size = self._calculate_pair_position_size(pair)
        
        # Update pair state
        pair.is_active = True
        pair.entry_spread = pair.spread
        pair.entry_time = datetime.utcnow()
        pair.position_count += 1
        self._state.active_pairs.append(pair)
        self._pairs_stats["active_pairs"] = len(self._state.active_pairs)
        
        self.logger.info(
            f"Pairs entry: {pair.leg1}/{pair.leg2} "
            f"z-score: {pair.z_score:.2f}, direction: {direction}"
        )
        
        # Create signal with pair metadata
        signal = Signal(
            symbol=f"{pair.leg1}/{pair.leg2}",
            signal_type=signal_type,
            strength=SignalStrength.MEDIUM,
            confidence=self._calculate_entry_confidence(pair),
            price=0,  # Not applicable for pairs
            position_size=position_size,
            timestamp=datetime.utcnow(),
            metadata={
                "pair": {
                    "leg1": pair.leg1,
                    "leg2": pair.leg2,
                    "hedge_ratio": pair.hedge_ratio,
                    "z_score": pair.z_score,
                    "spread": pair.spread,
                    "spread_mean": pair.spread_mean,
                    "half_life": pair.half_life,
                },
                "direction": direction,
                "reason": reason,
                "leg1_side": leg1_side.value,
                "leg2_side": leg2_side.value,
            },
        )
        
        return signal
    
    async def _check_exit_signals(self) -> Optional[Signal]:
        """
        Check for exit signals.
        
        Returns:
            Optional[Signal]: Exit signal
        """
        if not self._state:
            return None
        
        for pair in self._state.active_pairs[:]:
            # Check exit conditions
            
            # Exit 1: Z-score reverts to mean
            if abs(pair.z_score) <= self.pairs_config.exit_zscore:
                return await self._create_exit_signal(pair, "zscore_reverted")
            
            # Exit 2: Stop loss hit
            if abs(pair.z_score) > self.pairs_config.stop_loss_zscore:
                return await self._create_exit_signal(pair, "stop_loss")
            
            # Exit 3: Max holding period
            if pair.entry_time:
                holding_period = (datetime.utcnow() - pair.entry_time).total_seconds() / 60  # minutes
                if holding_period > self.pairs_config.max_holding_period * 5:  # Approximate
                    return await self._create_exit_signal(pair, "max_holding_period")
        
        return None
    
    async def _create_exit_signal(
        self,
        pair: TradingPair,
        reason: str,
    ) -> Signal:
        """
        Create an exit signal for a pair.
        
        Args:
            pair: Trading pair to exit
            reason: Exit reason
            
        Returns:
            Signal: Exit signal
        """
        # Determine if we were long or short
        direction = "long" if pair.z_score > 0 else "short"  # Based on entry
        
        pair.is_active = False
        self._state.active_pairs.remove(pair)
        self._pairs_stats["active_pairs"] = len(self._state.active_pairs)
        
        self.logger.info(
            f"Pairs exit: {pair.leg1}/{pair.leg2} "
            f"z-score: {pair.z_score:.2f}, reason: {reason}"
        )
        
        signal = Signal(
            symbol=f"{pair.leg1}/{pair.leg2}",
            signal_type=SignalType.CLOSE,
            strength=SignalStrength.MEDIUM,
            confidence=0.8,
            price=0,
            timestamp=datetime.utcnow(),
            metadata={
                "pair": {
                    "leg1": pair.leg1,
                    "leg2": pair.leg2,
                    "z_score": pair.z_score,
                    "spread": pair.spread,
                },
                "reason": reason,
                "exit_direction": direction,
            },
        )
        
        return signal
    
    def _calculate_entry_confidence(self, pair: TradingPair) -> float:
        """
        Calculate entry confidence for a pair.
        
        Args:
            pair: Trading pair
            
        Returns:
            float: Confidence level (0-1)
        """
        confidence = 0.6
        
        # Z-score strength
        zscore_abs = abs(pair.z_score)
        if zscore_abs > 3.0:
            confidence += 0.15
        elif zscore_abs > 2.5:
            confidence += 0.1
        
        # Half-life optimal
        if 15 <= pair.half_life <= 35:
            confidence += 0.1
        
        # Correlation strength
        if pair.correlation > 0.85:
            confidence += 0.1
        
        # Historical performance
        if pair.metadata.get("score", 0) > 0.7:
            confidence += 0.05
        
        return min(0.95, confidence)
    
    def _calculate_pair_position_size(self, pair: TradingPair) -> float:
        """
        Calculate position size for a pair.
        
        Args:
            pair: Trading pair
            
        Returns:
            float: Position size
        """
        base_size = self.pairs_config.position_size
        
        # Adjust based on confidence
        confidence = self._calculate_entry_confidence(pair)
        if confidence > 0.8:
            base_size *= 1.5
        elif confidence < 0.7:
            base_size *= 0.75
        
        # Adjust for exposure
        total_exposure = sum(
            p.metadata.get("position_size", 0) for p in self._state.active_pairs
        )
        if total_exposure > self.pairs_config.max_exposure * 0.8:
            base_size *= 0.5
        
        # Apply limits
        base_size = max(0, min(base_size, self.pairs_config.max_position_size))
        
        return base_size
    
    # ========================================================================
    # TRADE HANDLING
    # ========================================================================
    
    async def on_trade(self, trade: Trade) -> None:
        """
        Handle completed trade.
        
        Args:
            trade: Completed trade
        """
        await super().on_trade(trade)
        
        if not self._state:
            return
        
        pnl = trade.pnl or 0.0
        
        # Update statistics
        self._state.total_trades += 1
        self._pairs_stats["trades_executed"] += 1
        
        if pnl > 0:
            self._state.winning_trades += 1
            self._pairs_stats["winning_trades"] += 1
        else:
            self._state.losing_trades += 1
            self._pairs_stats["losing_trades"] += 1
        
        self._state.total_pnl += pnl
        
        # Record closed trade
        trade_record = {
            "symbol": trade.symbol,
            "side": trade.side.value,
            "quantity": trade.quantity,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "pnl": pnl,
            "pnl_pct": (pnl / (trade.entry_price * trade.quantity)) * 100 if trade.entry_price > 0 else 0,
            "timestamp": datetime.utcnow(),
        }
        self._state.closed_trades.append(trade_record)
        
        # Update win rate
        if self._state.total_trades > 0:
            win_rate = self._state.winning_trades / self._state.total_trades * 100
            self._pairs_stats["winning_trades"] = win_rate
        
        self.logger.info(
            f"Pairs trade closed: {trade.symbol} P&L: ${pnl:.2f} "
            f"(Win rate: {win_rate:.1f}%)"
        )
    
    # ========================================================================
    # PAIR MANAGEMENT
    # ========================================================================
    
    async def add_pair(self, leg1: str, leg2: str) -> bool:
        """
        Add a new trading pair.
        
        Args:
            leg1: First leg symbol
            leg2: Second leg symbol
            
        Returns:
            bool: True if pair was added
        """
        price1 = list(self._price_history.get(leg1, []))
        price2 = list(self._price_history.get(leg2, []))
        
        if len(price1) < self.pairs_config.lookback_period:
            return False
        if len(price2) < self.pairs_config.lookback_period:
            return False
        
        pair = self._evaluate_pair(leg1, leg2, price1, price2)
        if not pair:
            return False
        
        if not self._state:
            self._state = PairsState(symbol=self.config.symbol or "multi")
        
        self._state.pairs.append(pair)
        self.logger.info(f"Added pair: {leg1}/{leg2}")
        return True
    
    async def remove_pair(self, leg1: str, leg2: str) -> bool:
        """
        Remove a trading pair.
        
        Args:
            leg1: First leg symbol
            leg2: Second leg symbol
            
        Returns:
            bool: True if pair was removed
        """
        if not self._state:
            return False
        
        for i, pair in enumerate(self._state.pairs):
            if pair.leg1 == leg1 and pair.leg2 == leg2:
                if pair.is_active:
                    # Close position first
                    await self._create_exit_signal(pair, "pair_removed")
                self._state.pairs.pop(i)
                self.logger.info(f"Removed pair: {leg1}/{leg2}")
                return True
        
        return False
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    
    def get_pairs_stats(self) -> Dict[str, Any]:
        """
        Get pairs trading statistics.
        
        Returns:
            Dict[str, Any]: Pairs statistics
        """
        if not self._state:
            return {}
        
        active_pairs = self._state.active_pairs
        
        return {
            **self._pairs_stats,
            "state": {
                "total_pairs": len(self._state.pairs),
                "active_pairs": len(active_pairs),
                "total_trades": self._state.total_trades,
                "winning_trades": self._state.winning_trades,
                "losing_trades": self._state.losing_trades,
                "total_pnl": self._state.total_pnl,
                "win_rate": (
                    self._state.winning_trades / self._state.total_trades * 100
                    if self._state.total_trades > 0 else 0
                ),
            },
            "active_pair_details": [
                {
                    "leg1": p.leg1,
                    "leg2": p.leg2,
                    "z_score": p.z_score,
                    "spread": p.spread,
                    "half_life": p.half_life,
                    "entry_spread": p.entry_spread,
                }
                for p in active_pairs
            ],
            "config": {
                "selection_method": self.pairs_config.selection_method.value,
                "entry_zscore": self.pairs_config.entry_zscore,
                "exit_zscore": self.pairs_config.exit_zscore,
                "min_correlation": self.pairs_config.min_correlation,
            },
        }
    
    # ========================================================================
    # STRATEGY LIFECYCLE
    # ========================================================================
    
    async def on_start(self) -> None:
        """Called when the strategy starts."""
        await super().on_start()
        self.logger.info(
            f"Pairs trading strategy started "
            f"(selection: {self.pairs_config.selection_method.value})"
        )
    
    async def on_stop(self) -> None:
        """Called when the strategy stops."""
        # Close all active pairs
        if self._state:
            for pair in self._state.active_pairs[:]:
                await self._create_exit_signal(pair, "strategy_stopped")
        
        await super().on_stop()
        self.logger.info("Pairs trading strategy stopped")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "PairSelectionMethod",
    "PairTradingSignal",
    "TradingPair",
    "PairsConfig",
    "PairsState",
    "PairsTradingStrategy",
]
