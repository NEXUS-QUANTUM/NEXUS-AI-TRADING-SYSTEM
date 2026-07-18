# trading/strategies/arbitrage.py
"""
NEXUS AI TRADING SYSTEM - Arbitrage Strategy
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module implements various arbitrage trading strategies including:
- Triangular arbitrage (crypto/fiat)
- Statistical arbitrage (pairs trading)
- Cross-exchange arbitrage
- Futures-spot arbitrage
- Latency arbitrage

The strategy monitors multiple markets and exchanges to identify
and execute arbitrage opportunities with minimal risk.
"""

import asyncio
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable, Awaitable
from collections import deque, defaultdict
import numpy as np
from scipy import stats

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType, TimeInForce
from shared.types.trading import Order, Position, Trade, MarketData, OrderBook
from .base import BaseStrategy, StrategyConfig, Signal, SignalType, SignalStrength

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class ArbitrageType(str, Enum):
    """Types of arbitrage strategies"""
    TRIANGULAR = "triangular"
    STATISTICAL = "statistical"
    CROSS_EXCHANGE = "cross_exchange"
    FUTURES_SPOT = "futures_spot"
    LATENCY = "latency"
    DEX_CEX = "dex_cex"
    INTERNAL = "internal"


class StatisticalArbitrageMethod(str, Enum):
    """Methods for statistical arbitrage"""
    COINTEGRATION = "cointegration"
    CORRELATION = "correlation"
    DISTANCE = "distance"
    GARCH = "garch"
    COPULA = "copula"


@dataclass
class ArbitrageOpportunity:
    """An arbitrage opportunity"""
    id: str
    arbitrage_type: ArbitrageType
    symbol: str
    entry_price: float
    exit_price: float
    profit_pct: float
    profit_abs: float
    confidence: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    executed: bool = False
    execution_time: Optional[datetime] = None


@dataclass
class ArbitrageConfig:
    """Configuration for arbitrage strategy"""
    # General settings
    enabled_types: List[ArbitrageType] = field(default_factory=lambda: [
        ArbitrageType.TRIANGULAR,
        ArbitrageType.STATISTICAL,
        ArbitrageType.CROSS_EXCHANGE,
    ])
    min_profit_percent: float = 0.5
    min_profit_abs: float = 10.0
    max_position_size: float = 10000.0
    max_risk_per_trade: float = 0.01  # 1%
    max_drawdown: float = 0.05  # 5%
    
    # Triangular arbitrage
    triangular_min_profit: float = 0.3
    triangular_max_path_length: int = 3
    triangular_max_slippage: float = 0.01
    
    # Statistical arbitrage
    statistical_lookback: int = 100
    statistical_zscore_threshold: float = 2.0
    statistical_half_life: int = 30
    statistical_max_holding_period: int = 50
    statistical_correlation_threshold: float = 0.7
    statistical_cointegration_pvalue: float = 0.05
    
    # Cross-exchange arbitrage
    cross_exchange_min_spread: float = 0.1
    cross_exchange_max_latency: float = 100  # ms
    cross_exchange_required_liquidity: float = 1000.0
    
    # Futures-spot arbitrage
    futures_spot_min_basis: float = 0.5
    futures_spot_max_basis: float = 5.0
    futures_spot_funding_rate: float = 0.01
    futures_spot_min_days_to_expiry: int = 1
    
    # Latency arbitrage
    latency_min_advantage: float = 5  # ms
    latency_max_distance: float = 100  # km
    
    # Execution settings
    execution_timeout: float = 5.0
    max_slippage: float = 0.02
    retry_attempts: int = 3
    
    # Monitoring
    check_interval: float = 0.5  # seconds
    monitor_window: int = 100


# ============================================================================
# ARBITRAGE STRATEGY BASE
# ============================================================================

class ArbitrageStrategy(BaseStrategy):
    """
    Arbitrage trading strategy that identifies and executes arbitrage opportunities.
    """
    
    def __init__(
        self,
        config: StrategyConfig,
        arbitrage_config: Optional[ArbitrageConfig] = None,
        broker_manager: Optional[Any] = None,
    ):
        """
        Initialize the arbitrage strategy.
        
        Args:
            config: Strategy configuration
            arbitrage_config: Arbitrage-specific configuration
            broker_manager: Broker manager for execution
        """
        super().__init__(config)
        self.arbitrage_config = arbitrage_config or ArbitrageConfig()
        self.broker_manager = broker_manager
        
        # Opportunity tracking
        self._opportunities: List[ArbitrageOpportunity] = []
        self._executed_opportunities: List[ArbitrageOpportunity] = []
        self._failed_opportunities: List[ArbitrageOpportunity] = []
        
        # Market data cache
        self._market_cache: Dict[str, Dict[str, Any]] = {}
        self._orderbook_cache: Dict[str, Dict[str, OrderBook]] = {}
        
        # Statistical arbitrage data
        self._price_series: Dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
        self._spread_series: Dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
        self._zscore_series: Dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
        
        # Triangular arbitrage
        self._exchange_rates: Dict[str, Dict[str, float]] = {}
        
        # Performance tracking
        self._performance = {
            "opportunities_found": 0,
            "opportunities_executed": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "total_profit": 0.0,
            "total_loss": 0.0,
            "net_profit": 0.0,
            "win_rate": 0.0,
            "avg_profit_pct": 0.0,
            "max_profit_pct": 0.0,
            "max_loss_pct": 0.0,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Running flag
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        self.logger = logger
    
    # ========================================================================
    # OPPORTUNITY DETECTION
    # ========================================================================
    
    async def detect_opportunities(
        self,
        market_data: Dict[str, List[MarketData]],
        orderbooks: Optional[Dict[str, OrderBook]] = None,
    ) -> List[ArbitrageOpportunity]:
        """
        Detect arbitrage opportunities.
        
        Args:
            market_data: Market data by symbol
            orderbooks: Order books by symbol
            
        Returns:
            List[ArbitrageOpportunity]: Detected opportunities
        """
        opportunities = []
        
        # Update caches
        if orderbooks:
            self._orderbook_cache.update(orderbooks)
        
        for symbol, data in market_data.items():
            if data:
                self._market_cache[symbol] = data[-1]
                self._price_series[symbol].append(data[-1].last)
        
        # Detect different types of arbitrage
        enabled_types = self.arbitrage_config.enabled_types
        
        if ArbitrageType.TRIANGULAR in enabled_types:
            tri_opps = await self._detect_triangular_arbitrage()
            opportunities.extend(tri_opps)
        
        if ArbitrageType.STATISTICAL in enabled_types:
            stat_opps = await self._detect_statistical_arbitrage()
            opportunities.extend(stat_opps)
        
        if ArbitrageType.CROSS_EXCHANGE in enabled_types:
            cross_opps = await self._detect_cross_exchange_arbitrage()
            opportunities.extend(cross_opps)
        
        if ArbitrageType.FUTURES_SPOT in enabled_types:
            futures_opps = await self._detect_futures_spot_arbitrage()
            opportunities.extend(futures_opps)
        
        if ArbitrageType.LATENCY in enabled_types:
            latency_opps = await self._detect_latency_arbitrage()
            opportunities.extend(latency_opps)
        
        # Filter and rank opportunities
        opportunities = self._filter_opportunities(opportunities)
        opportunities = self._rank_opportunities(opportunities)
        
        # Store opportunities
        for opp in opportunities:
            self._opportunities.append(opp)
        
        self._performance["opportunities_found"] += len(opportunities)
        
        return opportunities
    
    # ========================================================================
    # TRIANGULAR ARBITRAGE
    # ========================================================================
    
    async def _detect_triangular_arbitrage(self) -> List[ArbitrageOpportunity]:
        """
        Detect triangular arbitrage opportunities.
        
        Returns:
            List[ArbitrageOpportunity]: Triangular arbitrage opportunities
        """
        opportunities = []
        
        # Get exchange rates
        rates = await self._get_exchange_rates()
        
        if not rates:
            return opportunities
        
        # Check all triangular paths
        symbols = list(rates.keys())
        for i in range(len(symbols)):
            for j in range(len(symbols)):
                for k in range(len(symbols)):
                    if i == j or j == k or i == k:
                        continue
                    
                    # Check path: symbol_i -> symbol_j -> symbol_k -> symbol_i
                    path = [symbols[i], symbols[j], symbols[k]]
                    
                    # Calculate arbitrage profit
                    profit, confidence = self._calculate_triangular_profit(
                        rates, path
                    )
                    
                    if profit > self.arbitrage_config.triangular_min_profit:
                        opportunity = ArbitrageOpportunity(
                            id=f"tri_{path[0]}_{path[1]}_{path[2]}_{int(datetime.utcnow().timestamp())}",
                            arbitrage_type=ArbitrageType.TRIANGULAR,
                            symbol=" / ".join(path),
                            entry_price=0.0,  # Not applicable
                            exit_price=0.0,
                            profit_pct=profit,
                            profit_abs=0.0,  # Calculated later
                            confidence=confidence,
                            steps=[
                                {"from": path[0], "to": path[1]},
                                {"from": path[1], "to": path[2]},
                                {"from": path[2], "to": path[0]},
                            ],
                            metadata={"path": path},
                        )
                        opportunities.append(opportunity)
        
        return opportunities
    
    async def _get_exchange_rates(self) -> Dict[str, Dict[str, float]]:
        """
        Get current exchange rates.
        
        Returns:
            Dict[str, Dict[str, float]]: Exchange rates matrix
        """
        rates = {}
        
        # Build rates from market data
        for symbol, data in self._market_cache.items():
            base, quote, _ = self._parse_symbol(symbol)
            if base in rates:
                rates[base][quote] = data.get("last", 0)
            else:
                rates[base] = {quote: data.get("last", 0)}
            
            # Also add reverse rate
            if quote in rates:
                rates[quote][base] = 1.0 / data.get("last", 1) if data.get("last", 0) > 0 else 0
            else:
                rates[quote] = {base: 1.0 / data.get("last", 1) if data.get("last", 0) > 0 else 0}
        
        return rates
    
    def _parse_symbol(self, symbol: str) -> Tuple[str, str]:
        """
        Parse symbol into base and quote.
        
        Args:
            symbol: Symbol string
            
        Returns:
            Tuple[str, str]: Base and quote assets
        """
        separators = ["/", "_", "-", ":"]
        for sep in separators:
            if sep in symbol:
                parts = symbol.split(sep)
                if len(parts) == 2:
                    return parts[0], parts[1]
        
        # Try to parse without separator
        common_quotes = ["USDT", "USD", "USDC", "BUSD", "EUR", "GBP", "JPY", "CHF"]
        for quote in sorted(common_quotes, key=len, reverse=True):
            if symbol.endswith(quote):
                return symbol[:-len(quote)], quote
        
        return symbol, ""
    
    def _calculate_triangular_profit(
        self,
        rates: Dict[str, Dict[str, float]],
        path: List[str],
    ) -> Tuple[float, float]:
        """
        Calculate triangular arbitrage profit.
        
        Args:
            rates: Exchange rates matrix
            path: Trading path
            
        Returns:
            Tuple[float, float]: (profit_percent, confidence)
        """
        if len(path) < 3:
            return 0.0, 0.0
        
        profit = 1.0
        
        # Calculate profit along the path
        for i in range(len(path)):
            from_asset = path[i]
            to_asset = path[(i + 1) % len(path)]
            
            rate = rates.get(from_asset, {}).get(to_asset, 0)
            if rate == 0:
                return 0.0, 0.0
            
            profit *= rate
        
        # Profit percent
        profit_pct = (profit - 1) * 100
        
        # Confidence based on path stability
        confidence = 0.8 if profit_pct > 0.5 else 0.6
        
        return profit_pct, confidence
    
    # ========================================================================
    # STATISTICAL ARBITRAGE
    # ========================================================================
    
    async def _detect_statistical_arbitrage(self) -> List[ArbitrageOpportunity]:
        """
        Detect statistical arbitrage opportunities using cointegration.
        
        Returns:
            List[ArbitrageOpportunity]: Statistical arbitrage opportunities
        """
        opportunities = []
        
        # Get price series for pairs
        symbols = list(self._price_series.keys())
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                pair = (symbols[i], symbols[j])
                
                # Get price series
                prices_i = list(self._price_series[symbols[i]])
                prices_j = list(self._price_series[symbols[j]])
                
                if len(prices_i) < self.arbitrage_config.statistical_lookback:
                    continue
                
                if len(prices_j) < self.arbitrage_config.statistical_lookback:
                    continue
                
                # Calculate spread
                spread, zscore = self._calculate_statistical_spread(prices_i, prices_j)
                
                # Update spread series
                spread_key = f"{symbols[i]}_{symbols[j]}"
                self._spread_series[spread_key].append(spread)
                self._zscore_series[spread_key].append(zscore)
                
                # Check for arbitrage opportunity
                if abs(zscore) > self.arbitrage_config.statistical_zscore_threshold:
                    # Determine direction
                    if zscore > 0:
                        # Short spread (sell overvalued, buy undervalued)
                        signal_type = SignalType.SELL
                        entry_description = f"Short {symbols[i]}, Long {symbols[j]}"
                    else:
                        # Long spread (buy undervalued, sell overvalued)
                        signal_type = SignalType.BUY
                        entry_description = f"Long {symbols[i]}, Short {symbols[j]}"
                    
                    profit_pct = abs(zscore) * 0.5  # Approximate profit
                    confidence = min(1.0, abs(zscore) / 4.0)
                    
                    opportunity = ArbitrageOpportunity(
                        id=f"stat_{symbols[i]}_{symbols[j]}_{int(datetime.utcnow().timestamp())}",
                        arbitrage_type=ArbitrageType.STATISTICAL,
                        symbol=f"{symbols[i]}/{symbols[j]}",
                        entry_price=0.0,  # Not applicable
                        exit_price=0.0,
                        profit_pct=profit_pct,
                        profit_abs=0.0,
                        confidence=confidence,
                        steps=[
                            {"action": entry_description, "zscore": zscore}
                        ],
                        metadata={
                            "pair": pair,
                            "zscore": zscore,
                            "spread": spread,
                            "half_life": self._calculate_half_life(spread_series),
                        },
                    )
                    opportunities.append(opportunity)
        
        return opportunities
    
    def _calculate_statistical_spread(
        self,
        prices_i: List[float],
        prices_j: List[float],
    ) -> Tuple[float, float]:
        """
        Calculate statistical spread between two price series.
        
        Args:
            prices_i: Price series for asset i
            prices_j: Price series for asset j
            
        Returns:
            Tuple[float, float]: (spread, zscore)
        """
        # Ensure equal lengths
        min_len = min(len(prices_i), len(prices_j))
        prices_i = prices_i[-min_len:]
        prices_j = prices_j[-min_len:]
        
        # Calculate hedge ratio using linear regression
        x = np.array(prices_i)
        y = np.array(prices_j)
        
        # Simple linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        
        # Check cointegration
        if p_value > self.arbitrage_config.statistical_cointegration_pvalue:
            return 0.0, 0.0
        
        # Calculate spread
        spread = y - slope * x - intercept
        
        # Calculate z-score
        spread_mean = np.mean(spread)
        spread_std = np.std(spread)
        
        if spread_std == 0:
            return spread[-1], 0.0
        
        zscore = (spread[-1] - spread_mean) / spread_std
        
        return spread[-1], zscore
    
    def _calculate_half_life(self, spread_series: List[float]) -> float:
        """
        Calculate half-life of mean reversion.
        
        Args:
            spread_series: Spread time series
            
        Returns:
            float: Half-life in periods
        """
        if len(spread_series) < 10:
            return 0.0
        
        # Use Ornstein-Uhlenbeck process
        spread_series = np.array(spread_series)
        
        # Calculate lag and diff
        lag = spread_series[:-1]
        diff = np.diff(spread_series)
        
        # Linear regression: diff = alpha * lag + beta
        x = lag.reshape(-1, 1)
        y = diff
        
        try:
            beta = np.linalg.lstsq(x, y, rcond=None)[0][0]
            
            if beta >= 0:
                return 0.0
            
            # Half-life = -ln(2) / beta
            half_life = -np.log(2) / beta
            return half_life
            
        except Exception:
            return 0.0
    
    # ========================================================================
    # CROSS-EXCHANGE ARBITRAGE
    # ========================================================================
    
    async def _detect_cross_exchange_arbitrage(self) -> List[ArbitrageOpportunity]:
        """
        Detect cross-exchange arbitrage opportunities.
        
        Returns:
            List[ArbitrageOpportunity]: Cross-exchange opportunities
        """
        opportunities = []
        
        # Group market data by symbol
        symbol_data: Dict[str, Dict[str, Any]] = {}
        for symbol, data in self._market_cache.items():
            if symbol not in symbol_data:
                symbol_data[symbol] = {}
            
            # Assuming data has exchange info
            exchange = data.get("exchange", "unknown")
            symbol_data[symbol][exchange] = data
        
        # Check price differences across exchanges
        for symbol, exchanges in symbol_data.items():
            if len(exchanges) < 2:
                continue
            
            prices = []
            exchange_names = []
            for exchange, data in exchanges.items():
                prices.append(data.get("last", 0))
                exchange_names.append(exchange)
            
            # Find min and max prices
            min_price = min(prices)
            max_price = max(prices)
            min_idx = prices.index(min_price)
            max_idx = prices.index(max_price)
            
            if min_price > 0 and max_price > 0:
                spread_pct = (max_price - min_price) / min_price * 100
                
                if spread_pct > self.arbitrage_config.cross_exchange_min_spread:
                    # Check liquidity
                    if await self._check_liquidity(symbol, min_price, max_price):
                        opportunity = ArbitrageOpportunity(
                            id=f"cross_{symbol}_{int(datetime.utcnow().timestamp())}",
                            arbitrage_type=ArbitrageType.CROSS_EXCHANGE,
                            symbol=symbol,
                            entry_price=min_price,
                            exit_price=max_price,
                            profit_pct=spread_pct,
                            profit_abs=0.0,
                            confidence=0.7,
                            steps=[
                                {"exchange": exchange_names[min_idx], "action": "buy", "price": min_price},
                                {"exchange": exchange_names[max_idx], "action": "sell", "price": max_price},
                            ],
                            metadata={
                                "buy_exchange": exchange_names[min_idx],
                                "sell_exchange": exchange_names[max_idx],
                                "spread_pct": spread_pct,
                            },
                        )
                        opportunities.append(opportunity)
        
        return opportunities
    
    async def _check_liquidity(
        self,
        symbol: str,
        buy_price: float,
        sell_price: float,
    ) -> bool:
        """
        Check if there is sufficient liquidity for arbitrage.
        
        Args:
            symbol: Trading symbol
            buy_price: Buy price
            sell_price: Sell price
            
        Returns:
            bool: True if sufficient liquidity
        """
        # Check order book depth if available
        if symbol in self._orderbook_cache:
            orderbook = self._orderbook_cache[symbol]
            if hasattr(orderbook, "bids") and hasattr(orderbook, "asks"):
                # Check depth at prices
                buy_depth = sum(0.001 for _ in orderbook.bids)  # Simplified
                sell_depth = sum(0.001 for _ in orderbook.asks)
                min_depth = min(buy_depth, sell_depth)
                return min_depth > self.arbitrage_config.cross_exchange_required_liquidity
        
        return True  # Assume sufficient if no orderbook data
    
    # ========================================================================
    # FUTURES-SPOT ARBITRAGE
    # ========================================================================
    
    async def _detect_futures_spot_arbitrage(self) -> List[ArbitrageOpportunity]:
        """
        Detect futures-spot arbitrage opportunities.
        
        Returns:
            List[ArbitrageOpportunity]: Futures-spot opportunities
        """
        opportunities = []
        
        # Need both spot and futures data
        for symbol, data in self._market_cache.items():
            if "futures" not in symbol.lower():
                continue
            
            # Get spot price
            spot_symbol = symbol.replace("_PERP", "").replace("_", "/")
            if spot_symbol not in self._market_cache:
                continue
            
            spot_price = self._market_cache[spot_symbol].get("last", 0)
            futures_price = data.get("last", 0)
            
            if spot_price == 0 or futures_price == 0:
                continue
            
            # Calculate basis
            basis = (futures_price - spot_price) / spot_price * 100
            
            # Check if arbitrage opportunity
            if basis > self.arbitrage_config.futures_spot_min_basis:
                # Cash and carry arbitrage
                opportunity = ArbitrageOpportunity(
                    id=f"futspot_{symbol}_{int(datetime.utcnow().timestamp())}",
                    arbitrage_type=ArbitrageType.FUTURES_SPOT,
                    symbol=f"{symbol}/SPOT",
                    entry_price=spot_price,
                    exit_price=futures_price,
                    profit_pct=basis,
                    profit_abs=0.0,
                    confidence=0.75,
                    steps=[
                        {"action": "Buy spot", "price": spot_price},
                        {"action": "Sell futures", "price": futures_price},
                    ],
                    metadata={
                        "spot_symbol": spot_symbol,
                        "futures_symbol": symbol,
                        "basis": basis,
                        "days_to_expiry": 30,  # Default
                        "funding_rate": self.arbitrage_config.futures_spot_funding_rate,
                    },
                )
                opportunities.append(opportunity)
            
            elif basis < -self.arbitrage_config.futures_spot_min_basis:
                # Reverse cash and carry
                opportunity = ArbitrageOpportunity(
                    id=f"futspot_rev_{symbol}_{int(datetime.utcnow().timestamp())}",
                    arbitrage_type=ArbitrageType.FUTURES_SPOT,
                    symbol=f"{symbol}/SPOT",
                    entry_price=futures_price,
                    exit_price=spot_price,
                    profit_pct=-basis,
                    profit_abs=0.0,
                    confidence=0.7,
                    steps=[
                        {"action": "Sell spot", "price": spot_price},
                        {"action": "Buy futures", "price": futures_price},
                    ],
                    metadata={
                        "spot_symbol": spot_symbol,
                        "futures_symbol": symbol,
                        "basis": basis,
                        "days_to_expiry": 30,
                        "funding_rate": self.arbitrage_config.futures_spot_funding_rate,
                    },
                )
                opportunities.append(opportunity)
        
        return opportunities
    
    # ========================================================================
    # LATENCY ARBITRAGE
    # ========================================================================
    
    async def _detect_latency_arbitrage(self) -> List[ArbitrageOpportunity]:
        """
        Detect latency arbitrage opportunities.
        
        Returns:
            List[ArbitrageOpportunity]: Latency arbitrage opportunities
        """
        # This is a simplified version - real latency arbitrage requires
        # low-latency market data and execution infrastructure
        opportunities = []
        
        # Group by symbol and check for delayed updates
        for symbol, data in self._market_cache.items():
            # Check if we have multiple data sources with different timestamps
            # This requires data with timestamps
            pass
        
        return opportunities
    
    # ========================================================================
    # OPPORTUNITY FILTERING AND RANKING
    # ========================================================================
    
    def _filter_opportunities(
        self,
        opportunities: List[ArbitrageOpportunity],
    ) -> List[ArbitrageOpportunity]:
        """
        Filter opportunities based on criteria.
        
        Args:
            opportunities: Raw opportunities
            
        Returns:
            List[ArbitrageOpportunity]: Filtered opportunities
        """
        filtered = []
        
        for opp in opportunities:
            # Check minimum profit
            if opp.profit_pct < self.arbitrage_config.min_profit_percent:
                continue
            
            # Check confidence
            if opp.confidence < 0.4:
                continue
            
            filtered.append(opp)
        
        return filtered
    
    def _rank_opportunities(
        self,
        opportunities: List[ArbitrageOpportunity],
    ) -> List[ArbitrageOpportunity]:
        """
        Rank opportunities by desirability.
        
        Args:
            opportunities: Filtered opportunities
            
        Returns:
            List[ArbitrageOpportunity]: Ranked opportunities
        """
        # Calculate score for each opportunity
        for opp in opportunities:
            score = (
                opp.profit_pct * 0.4 +
                opp.confidence * 0.3 +
                (1 - abs(opp.profit_pct) / 100) * 0.2 +
                (1 / (len(self._executed_opportunities) + 1)) * 0.1
            )
            opp.metadata["score"] = score
        
        # Sort by score descending
        return sorted(opportunities, key=lambda x: x.metadata.get("score", 0), reverse=True)
    
    # ========================================================================
    # OPPORTUNITY EXECUTION
    # ========================================================================
    
    async def execute_opportunity(
        self,
        opportunity: ArbitrageOpportunity,
    ) -> bool:
        """
        Execute an arbitrage opportunity.
        
        Args:
            opportunity: Opportunity to execute
            
        Returns:
            bool: True if executed successfully
        """
        if not self.broker_manager:
            self.logger.error("No broker manager configured")
            return False
        
        if opportunity.executed:
            self.logger.warning(f"Opportunity {opportunity.id} already executed")
            return False
        
        try:
            self.logger.info(f"Executing arbitrage opportunity: {opportunity.id}")
            
            # Calculate position size
            position_size = self._calculate_position_size(opportunity)
            
            # Execute based on arbitrage type
            if opportunity.arbitrage_type == ArbitrageType.TRIANGULAR:
                success = await self._execute_triangular(opportunity, position_size)
            elif opportunity.arbitrage_type == ArbitrageType.STATISTICAL:
                success = await self._execute_statistical(opportunity, position_size)
            elif opportunity.arbitrage_type == ArbitrageType.CROSS_EXCHANGE:
                success = await self._execute_cross_exchange(opportunity, position_size)
            elif opportunity.arbitrage_type == ArbitrageType.FUTURES_SPOT:
                success = await self._execute_futures_spot(opportunity, position_size)
            else:
                success = await self._execute_generic(opportunity, position_size)
            
            if success:
                opportunity.executed = True
                opportunity.execution_time = datetime.utcnow()
                self._executed_opportunities.append(opportunity)
                self._performance["opportunities_executed"] += 1
                self._performance["successful_trades"] += 1
                self._performance["total_profit"] += opportunity.profit_abs
                self.logger.info(f"Successfully executed opportunity {opportunity.id}")
            else:
                self._failed_opportunities.append(opportunity)
                self._performance["failed_trades"] += 1
                self.logger.error(f"Failed to execute opportunity {opportunity.id}")
            
            # Update performance metrics
            self._update_performance_metrics()
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error executing opportunity {opportunity.id}: {e}")
            self._failed_opportunities.append(opportunity)
            self._performance["failed_trades"] += 1
            return False
    
    def _calculate_position_size(
        self,
        opportunity: ArbitrageOpportunity,
    ) -> float:
        """
        Calculate position size for an opportunity.
        
        Args:
            opportunity: Arbitrage opportunity
            
        Returns:
            float: Position size
        """
        # Base size from configuration
        base_size = self.arbitrage_config.max_position_size
        
        # Adjust based on confidence
        confidence_multiplier = max(0.5, min(1.0, opportunity.confidence))
        
        # Adjust based on profit potential
        profit_multiplier = min(1.0, opportunity.profit_pct / 2.0)
        
        # Calculate final size
        size = base_size * confidence_multiplier * profit_multiplier
        
        # Apply min/max
        min_size = 10.0
        size = max(min_size, size)
        size = min(size, self.arbitrage_config.max_position_size)
        
        return size
    
    async def _execute_triangular(
        self,
        opportunity: ArbitrageOpportunity,
        size: float,
    ) -> bool:
        """
        Execute triangular arbitrage.
        
        Args:
            opportunity: Opportunity to execute
            size: Position size
            
        Returns:
            bool: True if executed successfully
        """
        # Execute triangular arbitrage
        # Steps: asset1 -> asset2 -> asset3 -> asset1
        steps = opportunity.steps
        
        try:
            for step in steps:
                from_asset = step.get("from")
                to_asset = step.get("to")
                
                # Place order
                # This is simplified - actual implementation would need
                # to handle multiple exchanges and order types
                order = Order(
                    symbol=f"{from_asset}/{to_asset}",
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=size,
                )
                
                # Execute order
                result = await self.broker_manager.place_order(order)
                if not result:
                    return False
                
                # Update size for next step
                size = result.filled_quantity
            
            return True
            
        except Exception as e:
            self.logger.error(f"Triangular arbitrage execution failed: {e}")
            return False
    
    async def _execute_statistical(
        self,
        opportunity: ArbitrageOpportunity,
        size: float,
    ) -> bool:
        """
        Execute statistical arbitrage.
        
        Args:
            opportunity: Opportunity to execute
            size: Position size
            
        Returns:
            bool: True if executed successfully
        """
        # Execute statistical arbitrage (pairs trade)
        pair = opportunity.metadata.get("pair", [])
        if len(pair) != 2:
            return False
        
        symbol_i, symbol_j = pair
        zscore = opportunity.metadata.get("zscore", 0)
        
        try:
            if zscore > 0:
                # Short overvalued, long undervalued
                order1 = Order(
                    symbol=symbol_i,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=size / 2,
                )
                order2 = Order(
                    symbol=symbol_j,
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=size / 2,
                )
            else:
                # Long undervalued, short overvalued
                order1 = Order(
                    symbol=symbol_i,
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=size / 2,
                )
                order2 = Order(
                    symbol=symbol_j,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=size / 2,
                )
            
            result1 = await self.broker_manager.place_order(order1)
            result2 = await self.broker_manager.place_order(order2)
            
            return result1 and result2
            
        except Exception as e:
            self.logger.error(f"Statistical arbitrage execution failed: {e}")
            return False
    
    async def _execute_cross_exchange(
        self,
        opportunity: ArbitrageOpportunity,
        size: float,
    ) -> bool:
        """
        Execute cross-exchange arbitrage.
        
        Args:
            opportunity: Opportunity to execute
            size: Position size
            
        Returns:
            bool: True if executed successfully
        """
        # Execute cross-exchange arbitrage
        buy_exchange = opportunity.metadata.get("buy_exchange")
        sell_exchange = opportunity.metadata.get("sell_exchange")
        
        if not buy_exchange or not sell_exchange:
            return False
        
        try:
            # Buy on one exchange, sell on another
            # This requires multiple broker connections
            # Simplified version
            order = Order(
                symbol=opportunity.symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=size / 2,
            )
            
            result = await self.broker_manager.place_order(order)
            return bool(result)
            
        except Exception as e:
            self.logger.error(f"Cross-exchange arbitrage execution failed: {e}")
            return False
    
    async def _execute_futures_spot(
        self,
        opportunity: ArbitrageOpportunity,
        size: float,
    ) -> bool:
        """
        Execute futures-spot arbitrage.
        
        Args:
            opportunity: Opportunity to execute
            size: Position size
            
        Returns:
            bool: True if executed successfully
        """
        # Execute futures-spot arbitrage
        spot_symbol = opportunity.metadata.get("spot_symbol")
        futures_symbol = opportunity.metadata.get("futures_symbol")
        
        if not spot_symbol or not futures_symbol:
            return False
        
        try:
            # Buy spot, sell futures (cash and carry)
            spot_order = Order(
                symbol=spot_symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=size,
            )
            futures_order = Order(
                symbol=futures_symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=size,
            )
            
            result1 = await self.broker_manager.place_order(spot_order)
            result2 = await self.broker_manager.place_order(futures_order)
            
            return result1 and result2
            
        except Exception as e:
            self.logger.error(f"Futures-spot arbitrage execution failed: {e}")
            return False
    
    async def _execute_generic(
        self,
        opportunity: ArbitrageOpportunity,
        size: float,
    ) -> bool:
        """
        Execute a generic arbitrage opportunity.
        
        Args:
            opportunity: Opportunity to execute
            size: Position size
            
        Returns:
            bool: True if executed successfully
        """
        try:
            # Generic execution based on steps
            for step in opportunity.steps:
                action = step.get("action", "")
                price = step.get("price", 0)
                
                if "buy" in action.lower():
                    order = Order(
                        symbol=opportunity.symbol,
                        side=OrderSide.BUY,
                        order_type=OrderType.LIMIT,
                        quantity=size / 2,
                        price=price,
                    )
                else:
                    order = Order(
                        symbol=opportunity.symbol,
                        side=OrderSide.SELL,
                        order_type=OrderType.LIMIT,
                        quantity=size / 2,
                        price=price,
                    )
                
                result = await self.broker_manager.place_order(order)
                if not result:
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Generic arbitrage execution failed: {e}")
            return False
    
    # ========================================================================
    # PERFORMANCE METRICS
    # ========================================================================
    
    def _update_performance_metrics(self) -> None:
        """Update performance metrics."""
        total_trades = self._performance["successful_trades"] + self._performance["failed_trades"]
        
        if total_trades > 0:
            self._performance["win_rate"] = (
                self._performance["successful_trades"] / total_trades * 100
            )
            
            self._performance["net_profit"] = (
                self._performance["total_profit"] - self._performance["total_loss"]
            )
            
            # Calculate average profit percentage
            total_pnl = self._performance["total_profit"] + self._performance["total_loss"]
            if total_trades > 0 and total_pnl > 0:
                self._performance["avg_profit_pct"] = total_pnl / total_trades
    
    def get_performance(self) -> Dict[str, Any]:
        """
        Get performance metrics.
        
        Returns:
            Dict: Performance metrics
        """
        return {
            **self._performance,
            "total_opportunities": len(self._opportunities),
            "executed": len(self._executed_opportunities),
            "failed": len(self._failed_opportunities),
            "pending": len([o for o in self._opportunities if not o.executed]),
            "recent_opportunities": [
                {
                    "id": o.id,
                    "type": o.arbitrage_type.value,
                    "profit_pct": o.profit_pct,
                    "confidence": o.confidence,
                    "timestamp": o.timestamp.isoformat(),
                    "executed": o.executed,
                }
                for o in self._opportunities[-10:]
            ],
        }
    
    # ========================================================================
    # STRATEGY LIFE CYCLE
    # ========================================================================
    
    async def on_start(self) -> None:
        """Called when the strategy starts."""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self.logger.info("Arbitrage strategy started")
    
    async def on_stop(self) -> None:
        """Called when the strategy stops."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Arbitrage strategy stopped")
    
    async def _monitor_loop(self) -> None:
        """Monitor loop for continuous opportunity detection."""
        while self._running:
            try:
                # This would be driven by market data updates in practice
                await asyncio.sleep(self.arbitrage_config.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}")
    
    async def generate_signal(self, market_data: List[MarketData]) -> Optional[Signal]:
        """
        Generate a trading signal.
        
        Args:
            market_data: Market data
            
        Returns:
            Optional[Signal]: Trading signal
        """
        # Arbitrage opportunities are detected separately
        # This method returns signals based on detected opportunities
        if self._opportunities:
            best_opp = self._opportunities[0]
            if best_opp.profit_pct > self.arbitrage_config.min_profit_percent:
                return Signal(
                    symbol=best_opp.symbol,
                    signal_type=SignalType.BUY,
                    strength=SignalStrength.MEDIUM,
                    confidence=best_opp.confidence,
                    price=best_opp.entry_price,
                    timestamp=datetime.utcnow(),
                    metadata={"opportunity_id": best_opp.id},
                )
        
        return None


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "ArbitrageType",
    "StatisticalArbitrageMethod",
    "ArbitrageOpportunity",
    "ArbitrageConfig",
    "ArbitrageStrategy",
]
