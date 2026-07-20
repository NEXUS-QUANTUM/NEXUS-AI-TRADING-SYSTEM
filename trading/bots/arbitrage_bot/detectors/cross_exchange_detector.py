"""
NEXUS AI TRADING SYSTEM - Arbitrage Bot Cross-Exchange Detector
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced cross-exchange arbitrage detector with:
- Multi-exchange price monitoring
- Real-time arbitrage opportunity detection
- Triangular arbitrage detection
- Statistical arbitrage detection
- Fee-aware profit calculation
- Slippage estimation
- Volume-weighted analysis
- Opportunity ranking and filtering
"""

import asyncio
import json
import logging
import math
import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np

# Optional imports
try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    stats = None

try:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    LinearRegression = None
    StandardScaler = None

from .base_detector import BaseDetector, DetectionResult, DetectionType, DetectionPriority
from ..data.base import BaseDataManager
from ..data.price_manager import PriceManager, PriceSource, PriceSnapshot
from ..data.spread_manager import SpreadManager, SpreadData
from ..data.volume_manager import VolumeManager, VolumeData
from ..data.exceptions import DetectorError, DataNotFoundError

logger = logging.getLogger(__name__)


# ============================================================
# ENUMS
# ============================================================

class ArbitrageType(str, Enum):
    """Types of arbitrage."""
    TWO_WAY = "two_way"
    TRIANGULAR = "triangular"
    STATISTICAL = "statistical"
    CONVERGENCE = "convergence"
    CROSS_EXCHANGE = "cross_exchange"
    CROSS_MARKET = "cross_market"
    CROSS_ASSET = "cross_asset"
    FRONT_RUNNING = "front_running"
    LATENCY = "latency"
    SENTIMENT = "sentiment"


class ArbitrageStatus(str, Enum):
    """Status of arbitrage opportunity."""
    PENDING = "pending"
    ACTIVE = "active"
    EXECUTED = "executed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    FAILED = "failed"


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class ExchangePair:
    """Pair of exchanges for arbitrage."""
    
    exchange_1: str
    exchange_2: str
    symbol: str
    price_1: float
    price_2: float
    spread_pct: float
    fee_1: float
    fee_2: float
    volume_1: float
    volume_2: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'exchange_1': self.exchange_1,
            'exchange_2': self.exchange_2,
            'symbol': self.symbol,
            'price_1': self.price_1,
            'price_2': self.price_2,
            'spread_pct': self.spread_pct,
            'fee_1': self.fee_1,
            'fee_2': self.fee_2,
            'volume_1': self.volume_1,
            'volume_2': self.volume_2,
            'timestamp': self.timestamp.isoformat(),
            'confidence': self.confidence,
        }


@dataclass
class TriangularPath:
    """Path for triangular arbitrage."""
    
    symbol_1: str
    symbol_2: str
    symbol_3: str
    exchange: str
    rate_1: float
    rate_2: float
    rate_3: float
    combined_rate: float
    profit_pct: float
    fees: float
    volume: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol_1': self.symbol_1,
            'symbol_2': self.symbol_2,
            'symbol_3': self.symbol_3,
            'exchange': self.exchange,
            'rate_1': self.rate_1,
            'rate_2': self.rate_2,
            'rate_3': self.rate_3,
            'combined_rate': self.combined_rate,
            'profit_pct': self.profit_pct,
            'fees': self.fees,
            'volume': self.volume,
            'timestamp': self.timestamp.isoformat(),
            'confidence': self.confidence,
        }


@dataclass
class ArbitrageOpportunity:
    """Complete arbitrage opportunity."""
    
    opportunity_id: str = field(default_factory=lambda: f"arb_{int(time.time() * 1000)}")
    type: ArbitrageType
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    quantity: float
    gross_profit: float
    gross_profit_pct: float
    net_profit: float
    net_profit_pct: float
    fees: Dict[str, float]
    slippage_pct: float
    confidence: float
    status: ArbitrageStatus = ArbitrageStatus.PENDING
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    routes: List[Dict[str, Any]] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'opportunity_id': self.opportunity_id,
            'type': self.type.value if isinstance(self.type, ArbitrageType) else self.type,
            'symbol': self.symbol,
            'buy_exchange': self.buy_exchange,
            'sell_exchange': self.sell_exchange,
            'buy_price': self.buy_price,
            'sell_price': self.sell_price,
            'quantity': self.quantity,
            'gross_profit': self.gross_profit,
            'gross_profit_pct': self.gross_profit_pct,
            'net_profit': self.net_profit,
            'net_profit_pct': self.net_profit_pct,
            'fees': self.fees,
            'slippage_pct': self.slippage_pct,
            'confidence': self.confidence,
            'status': self.status.value if isinstance(self.status, ArbitrageStatus) else self.status,
            'timestamp': self.timestamp.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'routes': self.routes,
            'risks': self.risks,
            'metadata': self.metadata,
        }


@dataclass
class ArbitrageStats:
    """Statistics for arbitrage detection."""
    
    total_opportunities: int = 0
    executed_opportunities: int = 0
    failed_opportunities: int = 0
    total_profit: float = 0.0
    avg_profit_pct: float = 0.0
    success_rate: float = 0.0
    avg_confidence: float = 0.0
    type_distribution: Dict[str, int] = field(default_factory=dict)
    exchange_distribution: Dict[str, int] = field(default_factory=dict)
    last_opportunity: Optional[datetime] = None
    opportunities_per_minute: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_opportunities': self.total_opportunities,
            'executed_opportunities': self.executed_opportunities,
            'failed_opportunities': self.failed_opportunities,
            'total_profit': self.total_profit,
            'avg_profit_pct': self.avg_profit_pct,
            'success_rate': self.success_rate,
            'avg_confidence': self.avg_confidence,
            'type_distribution': self.type_distribution,
            'exchange_distribution': self.exchange_distribution,
            'last_opportunity': self.last_opportunity.isoformat() if self.last_opportunity else None,
            'opportunities_per_minute': self.opportunities_per_minute,
            'timestamp': self.timestamp.isoformat(),
        }


# ============================================================
# CROSS-EXCHANGE DETECTOR IMPLEMENTATION
# ============================================================

class CrossExchangeDetector(BaseDetector):
    """
    Advanced cross-exchange arbitrage detector.
    
    Features:
    - Multi-exchange price monitoring
    - Two-way arbitrage detection
    - Triangular arbitrage detection
    - Statistical arbitrage detection
    - Fee-aware profit calculation
    - Slippage estimation
    - Volume-weighted analysis
    - Opportunity ranking and filtering
    """

    def __init__(
        self,
        price_manager: PriceManager,
        spread_manager: Optional[SpreadManager] = None,
        volume_manager: Optional[VolumeManager] = None,
        config: Optional[Dict[str, Any]] = None,
        redis_client: Optional[Any] = None,
    ):
        """
        Initialize cross-exchange detector.

        Args:
            price_manager: PriceManager instance
            spread_manager: SpreadManager instance (optional)
            volume_manager: VolumeManager instance (optional)
            config: Configuration dictionary
            redis_client: Redis client for caching
        """
        super().__init__(config, name="CrossExchangeDetector")
        
        self.price_manager = price_manager
        self.spread_manager = spread_manager
        self.volume_manager = volume_manager
        self.redis = redis_client
        
        # Exchanges to monitor
        self._exchanges: Set[str] = set()
        self._symbols: Set[str] = set()
        
        # Price history
        self._price_history: Dict[str, Dict[str, deque]] = {}  # exchange -> symbol -> deque
        
        # Opportunities
        self._opportunities: List[ArbitrageOpportunity] = []
        self._opportunity_history: Dict[str, deque] = {}  # symbol -> deque
        
        # Statistics
        self._stats = ArbitrageStats()
        
        # Fee rates
        self._fee_rates: Dict[str, float] = {
            'binance': 0.001,
            'bybit': 0.001,
            'coinbase': 0.005,
            'kraken': 0.0026,
            'okx': 0.001,
            'gateio': 0.002,
            'kucoin': 0.001,
            'mexc': 0.001,
            'bitget': 0.001,
        }
        
        # Thresholds
        self._min_profit_pct = 0.1
        self._min_confidence = 0.5
        self._max_slippage_pct = 1.0
        self._min_volume_usd = 1000
        
        # Triangular arbitrage symbols
        self._triangular_symbols: List[List[str]] = []
        
        # Cache
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 5
        
        # Background tasks
        self._background_tasks: Set[asyncio.Task] = set()
        
        logger.info("CrossExchangeDetector initialized")

    # ============================================================
    # PUBLIC METHODS
    # ============================================================

    async def detect(self, data: Dict[str, Any]) -> Optional[DetectionResult]:
        """
        Detect cross-exchange arbitrage opportunities.

        Args:
            data: Input data containing exchanges and symbols

        Returns:
            DetectionResult or None
        """
        try:
            exchanges = data.get('exchanges', list(self._exchanges))
            symbols = data.get('symbols', list(self._symbols))
            
            if not exchanges or not symbols:
                return None
            
            # Get price snapshot
            best_opportunity = None
            best_score = -float('inf')
            
            # Check two-way arbitrage
            two_way_opp = await self._detect_two_way_arbitrage(exchanges, symbols)
            if two_way_opp:
                score = self._score_opportunity(two_way_opp)
                if score > best_score:
                    best_score = score
                    best_opportunity = two_way_opp
            
            # Check triangular arbitrage
            if self._triangular_symbols:
                triangular_opp = await self._detect_triangular_arbitrage(exchanges)
                if triangular_opp:
                    score = self._score_opportunity(triangular_opp)
                    if score > best_score:
                        best_score = score
                        best_opportunity = triangular_opp
            
            # Check statistical arbitrage
            stat_opp = await self._detect_statistical_arbitrage(exchanges, symbols)
            if stat_opp:
                score = self._score_opportunity(stat_opp)
                if score > best_score:
                    best_score = score
                    best_opportunity = stat_opp
            
            if best_opportunity:
                # Store opportunity
                await self._store_opportunity(best_opportunity)
                
                # Create detection result
                return DetectionResult(
                    type=DetectionType.OPPORTUNITY,
                    priority=DetectionPriority.HIGH,
                    score=best_opportunity.net_profit_pct,
                    confidence=best_opportunity.confidence,
                    data=best_opportunity.to_dict(),
                    description=(
                        f"{best_opportunity.type.value} arbitrage: "
                        f"{best_opportunity.symbol} {best_opportunity.buy_exchange} -> "
                        f"{best_opportunity.sell_exchange} "
                        f"Profit: {best_opportunity.net_profit_pct:.2f}%"
                    ),
                    source="cross_exchange_detector",
                )
            
            return None

        except Exception as e:
            logger.error(f"Cross-exchange detection failed: {e}")
            return None

    async def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate input data."""
        return 'exchanges' in data or 'symbols' in data

    async def get_required_fields(self) -> List[str]:
        """Get required fields."""
        return ['exchanges', 'symbols']

    async def add_exchange(self, exchange: str) -> None:
        """
        Add an exchange to monitor.

        Args:
            exchange: Exchange name
        """
        self._exchanges.add(exchange)
        self._price_history[exchange] = {}
        
        logger.info(f"Added exchange: {exchange}")

    async def add_symbol(self, symbol: str) -> None:
        """
        Add a symbol to monitor.

        Args:
            symbol: Trading pair symbol
        """
        self._symbols.add(symbol)
        self._opportunity_history[symbol] = deque(maxlen=1000)
        
        logger.info(f"Added symbol: {symbol}")

    async def add_triangular_path(
        self,
        symbols: List[str],
        exchange: Optional[str] = None,
    ) -> None:
        """
        Add a triangular arbitrage path.

        Args:
            symbols: List of symbols in the path
            exchange: Exchange to use (all if None)
        """
        if len(symbols) != 3:
            raise ValueError("Triangular path requires exactly 3 symbols")
        
        self._triangular_symbols.append(symbols)
        logger.info(f"Added triangular path: {' -> '.join(symbols)}")

    async def update_fee_rate(self, exchange: str, fee_rate: float) -> None:
        """
        Update fee rate for an exchange.

        Args:
            exchange: Exchange name
            fee_rate: Fee rate (e.g., 0.001 for 0.1%)
        """
        self._fee_rates[exchange] = fee_rate
        logger.info(f"Updated fee rate for {exchange}: {fee_rate:.4f}%")

    async def get_opportunities(
        self,
        symbol: Optional[str] = None,
        exchange: Optional[str] = None,
        min_profit_pct: float = 0.0,
        limit: int = 100,
    ) -> List[ArbitrageOpportunity]:
        """
        Get arbitrage opportunities.

        Args:
            symbol: Symbol filter
            exchange: Exchange filter
            min_profit_pct: Minimum profit percentage
            limit: Maximum number of opportunities

        Returns:
            List of ArbitrageOpportunity
        """
        opportunities = self._opportunities.copy()
        
        if symbol:
            opportunities = [o for o in opportunities if o.symbol == symbol]
        if exchange:
            opportunities = [o for o in opportunities if 
                           o.buy_exchange == exchange or o.sell_exchange == exchange]
        if min_profit_pct > 0:
            opportunities = [o for o in opportunities if o.net_profit_pct >= min_profit_pct]
        
        opportunities.sort(key=lambda o: o.net_profit_pct, reverse=True)
        return opportunities[:limit]

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get arbitrage statistics.

        Returns:
            Dictionary with statistics
        """
        return self._stats.to_dict()

    async def execute_opportunity(
        self,
        opportunity_id: str,
        quantity: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Execute an arbitrage opportunity.

        Args:
            opportunity_id: Opportunity ID
            quantity: Trade quantity (optional)

        Returns:
            Execution result
        """
        # Find opportunity
        opportunity = None
        for opp in self._opportunities:
            if opp.opportunity_id == opportunity_id:
                opportunity = opp
                break
        
        if not opportunity:
            return {'success': False, 'error': 'Opportunity not found'}
        
        # Check if still valid
        if opportunity.status != ArbitrageStatus.PENDING:
            return {'success': False, 'error': f'Opportunity status: {opportunity.status}'}
        
        if opportunity.expires_at and datetime.utcnow() > opportunity.expires_at:
            opportunity.status = ArbitrageStatus.EXPIRED
            return {'success': False, 'error': 'Opportunity expired'}
        
        # Use specified quantity or default
        trade_quantity = quantity or opportunity.quantity
        
        # Execute trade
        try:
            # Place buy order
            buy_result = await self._execute_order(
                exchange=opportunity.buy_exchange,
                symbol=opportunity.symbol,
                side='buy',
                quantity=trade_quantity,
                price=opportunity.buy_price,
            )
            
            if not buy_result['success']:
                opportunity.status = ArbitrageStatus.FAILED
                return {'success': False, 'error': f'Buy order failed: {buy_result.get("error")}'}
            
            # Place sell order
            sell_result = await self._execute_order(
                exchange=opportunity.sell_exchange,
                symbol=opportunity.symbol,
                side='sell',
                quantity=trade_quantity,
                price=opportunity.sell_price,
            )
            
            if not sell_result['success']:
                # Try to cancel buy order
                await self._cancel_order(
                    exchange=opportunity.buy_exchange,
                    order_id=buy_result.get('order_id'),
                )
                opportunity.status = ArbitrageStatus.FAILED
                return {'success': False, 'error': f'Sell order failed: {sell_result.get("error")}'}
            
            # Update opportunity
            opportunity.status = ArbitrageStatus.EXECUTED
            
            # Update statistics
            self._stats.executed_opportunities += 1
            self._stats.total_profit += opportunity.net_profit
            
            return {
                'success': True,
                'buy_order': buy_result,
                'sell_order': sell_result,
                'profit': opportunity.net_profit,
                'profit_pct': opportunity.net_profit_pct,
            }
            
        except Exception as e:
            opportunity.status = ArbitrageStatus.FAILED
            self._stats.failed_opportunities += 1
            return {'success': False, 'error': str(e)}

    # ============================================================
    # PRIVATE METHODS - DETECTION
    # ============================================================

    async def _detect_two_way_arbitrage(
        self,
        exchanges: List[str],
        symbols: List[str],
    ) -> Optional[ArbitrageOpportunity]:
        """Detect two-way arbitrage opportunities."""
        best_opportunity = None
        best_profit = -float('inf')
        
        for symbol in symbols:
            # Get prices for symbol across exchanges
            prices = {}
            for exchange in exchanges:
                price = await self._get_price(exchange, symbol)
                if price is not None:
                    prices[exchange] = price
            
            if len(prices) < 2:
                continue
            
            # Check each pair of exchanges
            exchange_list = list(prices.keys())
            for i in range(len(exchange_list)):
                for j in range(i + 1, len(exchange_list)):
                    buy_exchange = exchange_list[i]
                    sell_exchange = exchange_list[j]
                    buy_price = prices[buy_exchange]
                    sell_price = prices[sell_exchange]
                    
                    # Calculate arbitrage
                    opportunity = await self._calculate_arbitrage(
                        buy_exchange=buy_exchange,
                        sell_exchange=sell_exchange,
                        symbol=symbol,
                        buy_price=buy_price,
                        sell_price=sell_price,
                        arbitrage_type=ArbitrageType.TWO_WAY,
                    )
                    
                    if opportunity and opportunity.net_profit_pct > best_profit:
                        best_profit = opportunity.net_profit_pct
                        best_opportunity = opportunity
        
        return best_opportunity

    async def _detect_triangular_arbitrage(
        self,
        exchanges: List[str],
    ) -> Optional[ArbitrageOpportunity]:
        """Detect triangular arbitrage opportunities."""
        best_opportunity = None
        best_profit = -float('inf')
        
        for exchange in exchanges:
            for path in self._triangular_symbols:
                # Get prices for all symbols in path
                rates = []
                for symbol in path:
                    price = await self._get_price(exchange, symbol)
                    if price is None:
                        break
                    rates.append(price)
                
                if len(rates) < 3:
                    continue
                
                # Calculate triangular arbitrage
                opportunity = await self._calculate_triangular_arbitrage(
                    exchange=exchange,
                    symbol_1=path[0],
                    symbol_2=path[1],
                    symbol_3=path[2],
                    rate_1=rates[0],
                    rate_2=rates[1],
                    rate_3=rates[2],
                )
                
                if opportunity and opportunity.net_profit_pct > best_profit:
                    best_profit = opportunity.net_profit_pct
                    best_opportunity = opportunity
        
        return best_opportunity

    async def _detect_statistical_arbitrage(
        self,
        exchanges: List[str],
        symbols: List[str],
    ) -> Optional[ArbitrageOpportunity]:
        """Detect statistical arbitrage opportunities."""
        if not SCIPY_AVAILABLE:
            return None
        
        best_opportunity = None
        best_score = -float('inf')
        
        for symbol in symbols:
            # Get historical price differences
            spreads = await self._get_spread_history(symbol, exchanges, limit=100)
            
            if len(spreads) < 20:
                continue
            
            # Calculate z-score of current spread
            mean_spread = statistics.mean(spreads)
            std_spread = statistics.stdev(spreads) if len(spreads) > 1 else 1
            
            current_spread = spreads[-1]
            zscore = (current_spread - mean_spread) / std_spread if std_spread > 0 else 0
            
            # Check if spread is extreme
            if abs(zscore) > 2:
                # Find best pair
                for i in range(len(exchanges)):
                    for j in range(i + 1, len(exchanges)):
                        exchange_1 = exchanges[i]
                        exchange_2 = exchanges[j]
                        
                        price_1 = await self._get_price(exchange_1, symbol)
                        price_2 = await self._get_price(exchange_2, symbol)
                        
                        if price_1 is None or price_2 is None:
                            continue
                        
                        # Determine direction
                        if zscore > 0:
                            # Spread is high, expect mean reversion
                            # Buy on exchange_2 (cheaper), sell on exchange_1 (more expensive)
                            buy_exchange = exchange_2
                            sell_exchange = exchange_1
                            buy_price = price_2
                            sell_price = price_1
                        else:
                            buy_exchange = exchange_1
                            sell_exchange = exchange_2
                            buy_price = price_1
                            sell_price = price_2
                        
                        opportunity = await self._calculate_arbitrage(
                            buy_exchange=buy_exchange,
                            sell_exchange=sell_exchange,
                            symbol=symbol,
                            buy_price=buy_price,
                            sell_price=sell_price,
                            arbitrage_type=ArbitrageType.STATISTICAL,
                            extra_data={'zscore': zscore, 'mean_spread': mean_spread},
                        )
                        
                        if opportunity:
                            score = opportunity.net_profit_pct * abs(zscore)
                            if score > best_score:
                                best_score = score
                                best_opportunity = opportunity
        
        return best_opportunity

    # ============================================================
    # PRIVATE METHODS - CALCULATIONS
    # ============================================================

    async def _calculate_arbitrage(
        self,
        buy_exchange: str,
        sell_exchange: str,
        symbol: str,
        buy_price: float,
        sell_price: float,
        arbitrage_type: ArbitrageType,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[ArbitrageOpportunity]:
        """Calculate arbitrage opportunity details."""
        if buy_price <= 0 or sell_price <= 0:
            return None
        
        # Calculate gross spread
        gross_spread_pct = ((sell_price - buy_price) / buy_price) * 100
        
        if gross_spread_pct <= 0:
            return None
        
        # Get fee rates
        fee_buy = self._fee_rates.get(buy_exchange, 0.001)
        fee_sell = self._fee_rates.get(sell_exchange, 0.001)
        total_fee_pct = (fee_buy + fee_sell) * 100
        
        # Calculate net profit
        net_profit_pct = gross_spread_pct - total_fee_pct
        
        if net_profit_pct < self._min_profit_pct:
            return None
        
        # Calculate optimal quantity
        volume = await self._get_volume(buy_exchange, symbol)
        optimal_quantity = await self._calculate_optimal_quantity(
            buy_exchange, sell_exchange, symbol, buy_price, volume
        )
        
        if optimal_quantity <= 0:
            return None
        
        # Calculate profit amounts
        gross_profit = (sell_price - buy_price) * optimal_quantity
        fees = {
            'buy_fee': buy_price * optimal_quantity * fee_buy,
            'sell_fee': sell_price * optimal_quantity * fee_sell,
            'total_fee': (buy_price + sell_price) * optimal_quantity * (fee_buy + fee_sell) / 2,
        }
        net_profit = gross_profit - fees['total_fee']
        
        # Estimate slippage
        slippage_pct = await self._estimate_slippage(
            buy_exchange, sell_exchange, symbol, optimal_quantity
        )
        
        # Calculate confidence
        confidence = await self._calculate_confidence(
            buy_exchange, sell_exchange, symbol,
            net_profit_pct, gross_spread_pct, volume
        )
        
        if confidence < self._min_confidence:
            return None
        
        # Identify risks
        risks = await self._identify_risks(
            buy_exchange, sell_exchange, symbol,
            net_profit_pct, confidence, volume
        )
        
        # Create opportunity
        return ArbitrageOpportunity(
            type=arbitrage_type,
            symbol=symbol,
            buy_exchange=buy_exchange,
            sell_exchange=sell_exchange,
            buy_price=buy_price,
            sell_price=sell_price,
            quantity=optimal_quantity,
            gross_profit=gross_profit,
            gross_profit_pct=gross_spread_pct,
            net_profit=net_profit,
            net_profit_pct=net_profit_pct,
            fees=fees,
            slippage_pct=slippage_pct,
            confidence=confidence,
            expires_at=datetime.utcnow() + timedelta(seconds=30),
            risks=risks,
            metadata=extra_data or {},
        )

    async def _calculate_triangular_arbitrage(
        self,
        exchange: str,
        symbol_1: str,
        symbol_2: str,
        symbol_3: str,
        rate_1: float,
        rate_2: float,
        rate_3: float,
    ) -> Optional[ArbitrageOpportunity]:
        """Calculate triangular arbitrage opportunity."""
        # For triangular arbitrage, we need 3 symbols forming a cycle
        # Example: BTC-USDT, ETH-BTC, ETH-USDT
        
        # Calculate combined rate
        # Starting with USDT -> BTC -> ETH -> USDT
        rate_cycle = 1 / rate_1 * rate_2 * rate_3
        
        # Calculate profit
        gross_profit_pct = (rate_cycle - 1) * 100
        
        if gross_profit_pct < self._min_profit_pct:
            return None
        
        # Fees for each trade
        fee_rate = self._fee_rates.get(exchange, 0.001)
        total_fee_pct = fee_rate * 3 * 100
        
        net_profit_pct = gross_profit_pct - total_fee_pct
        
        if net_profit_pct < self._min_profit_pct:
            return None
        
        # Determine optimal amount
        optimal_amount = await self._calculate_optimal_quantity(
            exchange, exchange, symbol_1, rate_1, 10000
        )
        
        # Create opportunity
        return ArbitrageOpportunity(
            type=ArbitrageType.TRIANGULAR,
            symbol=f"{symbol_1}/{symbol_2}/{symbol_3}",
            buy_exchange=exchange,
            sell_exchange=exchange,
            buy_price=rate_1,
            sell_price=rate_3,
            quantity=optimal_amount,
            gross_profit=optimal_amount * gross_profit_pct / 100,
            gross_profit_pct=gross_profit_pct,
            net_profit=optimal_amount * net_profit_pct / 100,
            net_profit_pct=net_profit_pct,
            fees={
                'trade_1': optimal_amount * fee_rate,
                'trade_2': optimal_amount * fee_rate,
                'trade_3': optimal_amount * fee_rate,
                'total_fee': optimal_amount * fee_rate * 3,
            },
            slippage_pct=0.1,
            confidence=0.7,
            expires_at=datetime.utcnow() + timedelta(seconds=15),
            risks=["Triangular arbitrage has higher execution risk"],
            metadata={
                'rate_1': rate_1,
                'rate_2': rate_2,
                'rate_3': rate_3,
                'rate_cycle': rate_cycle,
            },
        )

    # ============================================================
    # PRIVATE METHODS - HELPERS
    # ============================================================

    async def _get_price(self, exchange: str, symbol: str) -> Optional[float]:
        """Get price for an exchange-symbol pair."""
        price_source = await self.price_manager.get_price(exchange, symbol)
        if price_source:
            return float(price_source.price)
        return None

    async def _get_volume(self, exchange: str, symbol: str) -> float:
        """Get volume for an exchange-symbol pair."""
        if self.volume_manager:
            volume_data = await self.volume_manager.get_volume(exchange, symbol)
            if volume_data:
                return float(volume_data.volume)
        return 0

    async def _get_spread_history(
        self,
        symbol: str,
        exchanges: List[str],
        limit: int = 100,
    ) -> List[float]:
        """Get historical spreads for a symbol."""
        spreads = []
        
        if self.spread_manager:
            for exchange in exchanges:
                history = await self.spread_manager.get_spread_history(
                    exchange, symbol, limit
                )
                for spread in history:
                    spreads.append(spread.spread_pct)
        
        return spreads

    async def _calculate_optimal_quantity(
        self,
        buy_exchange: str,
        sell_exchange: str,
        symbol: str,
        price: float,
        volume: float,
    ) -> float:
        """Calculate optimal trade quantity."""
        if volume == 0:
            return 100  # Default
        
        # Limit to 1% of volume or 0.5% of liquidity
        optimal = volume * 0.01
        
        # Cap at reasonable amount
        return min(max(10, optimal), 10000)

    async def _estimate_slippage(
        self,
        buy_exchange: str,
        sell_exchange: str,
        symbol: str,
        quantity: float,
    ) -> float:
        """Estimate slippage for a trade."""
        # Get liquidity
        liquidity = await self._get_volume(buy_exchange, symbol)
        if liquidity == 0:
            return 0.5  # Default 0.5%
        
        # Calculate slippage based on quantity vs liquidity
        ratio = quantity / liquidity
        slippage = min(2.0, ratio * 10)
        
        return max(0.01, slippage)

    async def _calculate_confidence(
        self,
        buy_exchange: str,
        sell_exchange: str,
        symbol: str,
        profit_pct: float,
        spread_pct: float,
        volume: float,
    ) -> float:
        """Calculate confidence score."""
        confidence = 0.5
        
        # Higher profit = higher confidence
        confidence += min(0.3, profit_pct / 10)
        
        # Higher spread = higher confidence
        confidence += min(0.2, spread_pct / 20)
        
        # Higher volume = higher confidence
        if volume > 10000:
            confidence += 0.1
        elif volume > 1000:
            confidence += 0.05
        
        # Exchange reliability
        reliable_exchanges = ['binance', 'bybit', 'coinbase']
        if buy_exchange in reliable_exchanges and sell_exchange in reliable_exchanges:
            confidence += 0.1
        
        return min(1.0, confidence)

    async def _identify_risks(
        self,
        buy_exchange: str,
        sell_exchange: str,
        symbol: str,
        profit_pct: float,
        confidence: float,
        volume: float,
    ) -> List[str]:
        """Identify risks for an opportunity."""
        risks = []
        
        if profit_pct < 1:
            risks.append("Low profit margin")
        
        if confidence < 0.6:
            risks.append("Low confidence")
        
        if volume < 1000:
            risks.append("Low liquidity")
        
        if buy_exchange == sell_exchange:
            risks.append("Same exchange arbitrage has execution risk")
        
        return risks

    def _score_opportunity(self, opportunity: ArbitrageOpportunity) -> float:
        """Score an opportunity."""
        return (
            opportunity.net_profit_pct * 0.5 +
            opportunity.confidence * 0.3 -
            opportunity.slippage_pct * 0.1 -
            len(opportunity.risks) * 0.05
        )

    async def _store_opportunity(self, opportunity: ArbitrageOpportunity) -> None:
        """Store an opportunity."""
        self._opportunities.append(opportunity)
        self._opportunity_history[opportunity.symbol].append(opportunity)
        
        # Update statistics
        self._stats.total_opportunities += 1
        self._stats.total_profit += opportunity.net_profit
        
        total_ops = self._stats.total_opportunities
        self._stats.avg_profit_pct = (
            (self._stats.avg_profit_pct * (total_ops - 1) + opportunity.net_profit_pct) / total_ops
        )
        self._stats.avg_confidence = (
            (self._stats.avg_confidence * (total_ops - 1) + opportunity.confidence) / total_ops
        )
        self._stats.last_opportunity = datetime.utcnow()
        
        # Update distributions
        type_key = opportunity.type.value
        self._stats.type_distribution[type_key] = self._stats.type_distribution.get(type_key, 0) + 1
        
        exchange_key = f"{opportunity.buy_exchange}->{opportunity.sell_exchange}"
        self._stats.exchange_distribution[exchange_key] = \
            self._stats.exchange_distribution.get(exchange_key, 0) + 1
        
        # Calculate rate
        if self._stats.last_opportunity:
            minutes = (datetime.utcnow() - self._stats.last_opportunity).total_seconds() / 60
            if minutes > 0:
                self._stats.opportunities_per_minute = self._stats.total_opportunities / minutes
        
        # Keep only recent opportunities
        if len(self._opportunities) > 1000:
            self._opportunities = self._opportunities[-1000:]

    # ============================================================
    # PRIVATE METHODS - EXECUTION
    # ============================================================

    async def _execute_order(
        self,
        exchange: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> Dict[str, Any]:
        """Execute an order."""
        # This would call the actual exchange API
        # For now, simulate execution
        await asyncio.sleep(0.01)
        
        return {
            'success': True,
            'order_id': f"order_{int(time.time() * 1000)}",
            'exchange': exchange,
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
        }

    async def _cancel_order(
        self,
        exchange: str,
        order_id: str,
    ) -> bool:
        """Cancel an order."""
        # This would call the actual exchange API
        await asyncio.sleep(0.01)
        return True

    # ============================================================
    # CONTEXT MANAGER METHODS
    # ============================================================

    async def start(self) -> None:
        """Start the detector."""
        await super().start()
        
        # Start background tasks
        self._background_tasks.add(
            asyncio.create_task(self._continuous_detection_loop())
        )
        
        logger.info("CrossExchangeDetector started")

    async def stop(self) -> None:
        """Stop the detector."""
        await super().stop()
        
        # Cancel background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        logger.info("CrossExchangeDetector stopped")

    async def _continuous_detection_loop(self) -> None:
        """Continuous detection loop."""
        while self._running:
            try:
                # Detect opportunities
                result = await self.detect({
                    'exchanges': list(self._exchanges),
                    'symbols': list(self._symbols),
                })
                
                if result:
                    logger.info(f"New opportunity detected: {result.description}")
                
                await asyncio.sleep(1)  # Check every second
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Detection loop error: {e}")
                await asyncio.sleep(5)

    async def clear(self) -> None:
        """Clear detector data."""
        await super().clear()
        self._opportunities.clear()
        self._opportunity_history.clear()
        self._stats = ArbitrageStats()
        logger.info("CrossExchangeDetector cleared")


# ============================================================
# FACTORY FUNCTIONS
# ============================================================

def create_cross_exchange_detector(
    price_manager: PriceManager,
    spread_manager: Optional[SpreadManager] = None,
    volume_manager: Optional[VolumeManager] = None,
    config: Optional[Dict[str, Any]] = None,
    redis_client: Optional[Any] = None,
) -> CrossExchangeDetector:
    """
    Create a cross-exchange detector instance.

    Args:
        price_manager: PriceManager instance
        spread_manager: SpreadManager instance (optional)
        volume_manager: VolumeManager instance (optional)
        config: Configuration dictionary
        redis_client: Redis client for caching

    Returns:
        CrossExchangeDetector instance
    """
    return CrossExchangeDetector(
        price_manager=price_manager,
        spread_manager=spread_manager,
        volume_manager=volume_manager,
        config=config,
        redis_client=redis_client,
    )


# ============================================================
# USAGE EXAMPLE
# ============================================================

if __name__ == "__main__":
    """
    Example usage of the cross-exchange detector.
    """
    import asyncio
    import json

    async def main():
        # Setup logging
        logging.basicConfig(level=logging.DEBUG)

        # Initialize managers
        from ..data.price_manager import create_price_manager
        from ..data.spread_manager import create_spread_manager
        from ..data.volume_manager import create_volume_manager

        price_manager = create_price_manager()
        spread_manager = create_spread_manager(price_manager)
        volume_manager = create_volume_manager(price_manager)

        # Create cross-exchange detector
        detector = create_cross_exchange_detector(
            price_manager=price_manager,
            spread_manager=spread_manager,
            volume_manager=volume_manager,
        )

        # Add exchanges and symbols
        exchanges = ['binance', 'bybit', 'coinbase', 'kraken']
        symbols = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT']

        for exchange in exchanges:
            await detector.add_exchange(exchange)

        for symbol in symbols:
            await detector.add_symbol(symbol)

        # Add triangular paths
        await detector.add_triangular_path(['BTC-USDT', 'ETH-BTC', 'ETH-USDT'])

        # Update prices
        await price_manager.update_price(
            exchange="binance",
            symbol="BTC-USDT",
            price=45000.0,
            bid=44990.0,
            ask=45010.0,
            volume=123.45,
        )

        await price_manager.update_price(
            exchange="bybit",
            symbol="BTC-USDT",
            price=45020.0,
            bid=45010.0,
            ask=45030.0,
            volume=67.89,
        )

        await price_manager.update_price(
            exchange="coinbase",
            symbol="BTC-USDT",
            price=44980.0,
            bid=44970.0,
            ask=44990.0,
            volume=45.67,
        )

        # Detect opportunities
        detector._running = True
        result = await detector.detect({
            'exchanges': exchanges,
            'symbols': ['BTC-USDT'],
        })

        if result:
            print(f"Arbitrage opportunity detected: {result.description}")
            print(f"Details: {json.dumps(result.data, indent=2, default=str)}")

        # Get all opportunities
        opportunities = await detector.get_opportunities(min_profit_pct=0.1)
        for opp in opportunities:
            print(f"\nOpportunity: {opp.symbol}")
            print(f"  {opp.buy_exchange} -> {opp.sell_exchange}")
            print(f"  Profit: {opp.net_profit_pct:.2f}%")
            print(f"  Confidence: {opp.confidence:.2f}")

        # Get statistics
        stats = await detector.get_stats()
        print(f"\nStatistics: {json.dumps(stats, indent=2, default=str)}")

        # Cleanup
        await detector.stop()
        await price_manager.stop()

    asyncio.run(main())
