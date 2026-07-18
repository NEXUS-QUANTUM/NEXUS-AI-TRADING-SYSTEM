# trading/brokers/broker_router.py
"""
NEXUS AI TRADING SYSTEM - Broker Router
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

This module provides intelligent routing of trading requests to appropriate
broker instances based on various criteria including symbol, market type,
performance, cost, and user preferences. It enables multi-broker strategies
with automatic failover and load balancing.

The router supports:
- Symbol-based routing
- Market type routing (crypto, forex, stocks)
- Performance-based routing
- Cost optimization
- Geographic routing
- Multi-broker strategies
"""

import asyncio
import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable, Awaitable
from collections import defaultdict, deque

from shared.utilities.logger import get_logger
from shared.types.common import OrderSide, OrderType
from .base import BaseBroker, BrokerName, AssetClass, BrokerException
from .broker_manager import BrokerManager, BrokerInstance, BrokerSelectionStrategy

logger = get_logger(__name__)


# ============================================================================
# ENUMS AND MODELS
# ============================================================================

class RoutingStrategy(str, Enum):
    """Routing strategies for broker selection"""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    FASTEST_LATENCY = "fastest_latency"
    LOWEST_COST = "lowest_cost"
    SYMBOL_PINNED = "symbol_pinned"
    MARKET_TYPE = "market_type"
    FAILOVER = "failover"
    GEOGRAPHIC = "geographic"
    SMART = "smart"
    RANDOM = "random"


class RoutingPreference(str, Enum):
    """Routing preferences"""
    PERFORMANCE = "performance"
    COST = "cost"
    RELIABILITY = "reliability"
    BALANCED = "balanced"


@dataclass
class BrokerCapability:
    """Capabilities of a broker"""
    supports_crypto: bool = False
    supports_forex: bool = False
    supports_stocks: bool = False
    supports_etfs: bool = False
    supports_futures: bool = False
    supports_options: bool = False
    supports_margin: bool = False
    supports_websocket: bool = False
    supports_market_orders: bool = True
    supports_limit_orders: bool = True
    supports_stop_orders: bool = True
    supports_trailing_stops: bool = False
    max_leverage: float = 1.0
    available_assets: List[str] = field(default_factory=list)
    restricted_assets: List[str] = field(default_factory=list)
    preferred_symbols: List[str] = field(default_factory=list)
    
    def can_trade(self, symbol: str, asset_class: Optional[AssetClass] = None) -> bool:
        """
        Check if the broker can trade a symbol.
        
        Args:
            symbol: Trading symbol
            asset_class: Optional asset class
            
        Returns:
            bool: True if the broker can trade the symbol
        """
        # Check restricted assets
        if symbol in self.restricted_assets:
            return False
        
        # Check if symbol is in preferred list or available assets
        if self.preferred_symbols and symbol in self.preferred_symbols:
            return True
        
        if self.available_assets and symbol not in self.available_assets:
            return False
        
        # Check asset class support
        if asset_class:
            if asset_class == AssetClass.CRYPTO and not self.supports_crypto:
                return False
            if asset_class == AssetClass.FOREX and not self.supports_forex:
                return False
            if asset_class == AssetClass.STOCK and not self.supports_stocks:
                return False
            if asset_class == AssetClass.ETF and not self.supports_etfs:
                return False
            if asset_class == AssetClass.FUTURES and not self.supports_futures:
                return False
            if asset_class == AssetClass.OPTIONS and not self.supports_options:
                return False
        
        return True
    
    def can_execute_order(self, order_type: OrderType) -> bool:
        """
        Check if the broker can execute a specific order type.
        
        Args:
            order_type: Order type
            
        Returns:
            bool: True if the broker can execute the order
        """
        if order_type == OrderType.MARKET:
            return self.supports_market_orders
        if order_type == OrderType.LIMIT:
            return self.supports_limit_orders
        if order_type == OrderType.STOP_LOSS:
            return self.supports_stop_orders
        if order_type == OrderType.TRAILING_STOP:
            return self.supports_trailing_stops
        return True


@dataclass
class BrokerCost:
    """Cost metrics for a broker"""
    commission_rate: float = 0.0  # Percentage
    fixed_commission: float = 0.0  # Fixed per trade
    withdrawal_fee: float = 0.0
    deposit_fee: float = 0.0
    maker_fee: float = 0.0
    taker_fee: float = 0.0
    spread_avg: float = 0.0
    slippage_avg: float = 0.0
    
    @property
    def total_trading_cost(self) -> float:
        """Calculate total trading cost (maker + taker average)"""
        return (self.maker_fee + self.taker_fee) / 2 + self.spread_avg + self.slippage_avg


@dataclass
class BrokerRoute:
    """A routing decision for a broker"""
    broker_id: str
    broker_name: str
    score: float
    reason: str
    tags: Dict[str, Any] = field(default_factory=dict)
    estimated_cost: Optional[float] = None
    estimated_latency: Optional[float] = None


@dataclass
class RoutingDecision:
    """Complete routing decision"""
    symbol: str
    asset_class: Optional[AssetClass]
    order_type: OrderType
    selected_broker: BrokerRoute
    alternatives: List[BrokerRoute] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    strategy_used: RoutingStrategy = RoutingStrategy.SMART
    confidence: float = 1.0


# ============================================================================
# BROKER ROUTER
# ============================================================================

class BrokerRouter:
    """
    Intelligent router for broker selection.
    
    Features:
    - Multi-criteria routing decisions
    - Performance tracking and optimization
    - Cost-based routing
    - Symbol pinning for consistency
    - Market type routing
    - Geographic routing
    - Smart routing with machine learning capabilities
    """
    
    def __init__(
        self,
        broker_manager: BrokerManager,
        default_strategy: RoutingStrategy = RoutingStrategy.SMART,
        preference: RoutingPreference = RoutingPreference.BALANCED,
        symbol_pinning: bool = True,
    ):
        """
        Initialize the broker router.
        
        Args:
            broker_manager: Broker manager instance
            default_strategy: Default routing strategy
            preference: Routing preference
            symbol_pinning: Whether to pin symbols to specific brokers
        """
        self.broker_manager = broker_manager
        self.default_strategy = default_strategy
        self.preference = preference
        self.symbol_pinning = symbol_pinning
        
        # Symbol pinning cache
        self._symbol_pins: Dict[str, str] = {}  # symbol -> broker_id
        self._symbol_last_used: Dict[str, float] = {}  # symbol -> timestamp
        
        # Performance tracking
        self._broker_performance: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._broker_latency: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._broker_success_rate: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Cost tracking
        self._broker_costs: Dict[str, BrokerCost] = defaultdict(BrokerCost)
        
        # Capabilities cache
        self._broker_capabilities: Dict[str, BrokerCapability] = {}
        
        # Historical decisions
        self._decision_history: List[RoutingDecision] = deque(maxlen=10000)
        
        # Statistics
        self._stats = {
            "total_routes": 0,
            "strategy_usage": defaultdict(int),
            "broker_selection": defaultdict(int),
            "by_symbol": defaultdict(lambda: defaultdict(int)),
            "avg_routing_time_ms": 0.0,
            "routing_samples": 0,
        }
        
        self._lock = asyncio.Lock()
        self.logger = logger
    
    # ========================================================================
    # BROKER CAPABILITIES
    # ========================================================================
    
    def register_broker_capabilities(
        self,
        broker_id: str,
        capabilities: BrokerCapability,
    ) -> None:
        """
        Register capabilities for a broker.
        
        Args:
            broker_id: Broker identifier
            capabilities: Broker capabilities
        """
        self._broker_capabilities[broker_id] = capabilities
        self.logger.debug(f"Registered capabilities for broker {broker_id}")
    
    def get_broker_capabilities(self, broker_id: str) -> Optional[BrokerCapability]:
        """
        Get capabilities for a broker.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            Optional[BrokerCapability]: Broker capabilities or None
        """
        return self._broker_capabilities.get(broker_id)
    
    def detect_capabilities(self, broker: BaseBroker) -> BrokerCapability:
        """
        Detect capabilities from a broker instance.
        
        Args:
            broker: Broker instance
            
        Returns:
            BrokerCapability: Detected capabilities
        """
        capabilities = BrokerCapability()
        
        # Detect based on broker type
        broker_name = broker.name.value if broker.name else ""
        
        # Crypto exchanges
        if broker_name in [
            BrokerName.BINANCE.value,
            BrokerName.BYBIT.value,
            BrokerName.COINBASE.value,
            BrokerName.KRAKEN.value,
            BrokerName.KUCOIN.value,
        ]:
            capabilities.supports_crypto = True
            capabilities.supports_websocket = True
            capabilities.supports_margin = True
            capabilities.max_leverage = 5.0
        
        # Stock brokers
        if broker_name in [
            BrokerName.ALPACA.value,
            BrokerName.IBKR.value,
            BrokerName.TRADIER.value,
        ]:
            capabilities.supports_stocks = True
            capabilities.supports_etfs = True
            capabilities.supports_options = True
            capabilities.supports_margin = True
            capabilities.max_leverage = 2.0
        
        # Forex brokers
        if broker_name in [
            BrokerName.OANDA.value,
            BrokerName.FOREX.value,
        ]:
            capabilities.supports_forex = True
            capabilities.max_leverage = 50.0
        
        # All brokers support basic order types
        capabilities.supports_market_orders = True
        capabilities.supports_limit_orders = True
        capabilities.supports_stop_orders = True
        
        return capabilities
    
    # ========================================================================
    # ROUTING METHODS
    # ========================================================================
    
    async def route(
        self,
        symbol: str,
        order_type: OrderType,
        asset_class: Optional[AssetClass] = None,
        strategy: Optional[RoutingStrategy] = None,
        prefer_broker_id: Optional[str] = None,
        exclude_brokers: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> RoutingDecision:
        """
        Route a trading request to the appropriate broker.
        
        Args:
            symbol: Trading symbol
            order_type: Order type
            asset_class: Optional asset class
            strategy: Optional routing strategy (defaults to default_strategy)
            prefer_broker_id: Preferred broker ID
            exclude_brokers: Brokers to exclude from routing
            context: Additional context for routing
            
        Returns:
            RoutingDecision: Routing decision
        """
        start_time = time.time()
        
        # Use default strategy if not specified
        strategy = strategy or self.default_strategy
        
        # Get eligible brokers
        eligible = await self._get_eligible_brokers(
            symbol=symbol,
            order_type=order_type,
            asset_class=asset_class,
            exclude=exclude_brokers,
        )
        
        if not eligible:
            raise BrokerException(f"No eligible brokers found for symbol {symbol}")
        
        # Apply strategy
        strategy_methods = {
            RoutingStrategy.ROUND_ROBIN: self._route_round_robin,
            RoutingStrategy.LEAST_LOADED: self._route_least_loaded,
            RoutingStrategy.FASTEST_LATENCY: self._route_fastest,
            RoutingStrategy.LOWEST_COST: self._route_lowest_cost,
            RoutingStrategy.SYMBOL_PINNED: self._route_symbol_pinned,
            RoutingStrategy.MARKET_TYPE: self._route_market_type,
            RoutingStrategy.FAILOVER: self._route_failover,
            RoutingStrategy.GEOGRAPHIC: self._route_geographic,
            RoutingStrategy.SMART: self._route_smart,
            RoutingStrategy.RANDOM: self._route_random,
        }
        
        # Get routing method
        route_method = strategy_methods.get(strategy, self._route_smart)
        
        # Execute routing
        try:
            selected = await route_method(
                symbol=symbol,
                eligible=eligible,
                order_type=order_type,
                asset_class=asset_class,
                prefer_broker_id=prefer_broker_id,
                context=context or {},
            )
        except Exception as e:
            self.logger.error(f"Routing strategy {strategy} failed: {e}")
            # Fallback to first eligible
            selected = eligible[0]
        
        # Generate alternatives
        alternatives = [
            BrokerRoute(
                broker_id=broker_id,
                broker_name=self._get_broker_name(broker_id),
                score=0.0,
                reason="alternative",
            )
            for broker_id in eligible[:3]
            if broker_id != selected.broker_id
        ]
        
        # Update stats
        self._stats["total_routes"] += 1
        self._stats["strategy_usage"][strategy.value] += 1
        self._stats["broker_selection"][selected.broker_id] += 1
        self._stats["by_symbol"][symbol][selected.broker_id] += 1
        
        # Update routing time
        routing_time = (time.time() - start_time) * 1000
        self._stats["routing_samples"] += 1
        self._stats["avg_routing_time_ms"] = (
            (self._stats["avg_routing_time_ms"] * (self._stats["routing_samples"] - 1) + routing_time)
            / self._stats["routing_samples"]
        )
        
        # Create decision
        decision = RoutingDecision(
            symbol=symbol,
            asset_class=asset_class,
            order_type=order_type,
            selected_broker=selected,
            alternatives=alternatives,
            strategy_used=strategy,
            confidence=1.0,
        )
        
        # Store decision history
        self._decision_history.append(decision)
        
        # Update symbol pinning
        if self.symbol_pinning:
            self._symbol_pins[symbol] = selected.broker_id
            self._symbol_last_used[symbol] = time.time()
        
        self.logger.info(
            f"Routed {symbol} to {selected.broker_id} "
            f"(strategy={strategy.value}, score={selected.score:.2f})"
        )
        
        return decision
    
    async def _get_eligible_brokers(
        self,
        symbol: str,
        order_type: OrderType,
        asset_class: Optional[AssetClass] = None,
        exclude: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Get eligible brokers for a request.
        
        Args:
            symbol: Trading symbol
            order_type: Order type
            asset_class: Optional asset class
            exclude: Brokers to exclude
            
        Returns:
            List[str]: Eligible broker IDs
        """
        exclude = exclude or []
        eligible = []
        
        # Get all instances
        instances = self.broker_manager.get_all_instances()
        
        for instance in instances:
            # Skip if not connected or unhealthy
            if not instance.is_connected or not instance.is_healthy:
                continue
            
            # Skip excluded
            if instance.id in exclude:
                continue
            
            # Check capabilities
            capabilities = self._broker_capabilities.get(instance.id)
            if capabilities:
                if not capabilities.can_trade(symbol, asset_class):
                    continue
                if not capabilities.can_execute_order(order_type):
                    continue
            
            eligible.append(instance.id)
        
        # Try symbol pinning
        if self.symbol_pinning and symbol in self._symbol_pins:
            pinned = self._symbol_pins[symbol]
            if pinned in eligible:
                # Move pinned broker to front
                eligible.remove(pinned)
                eligible.insert(0, pinned)
        
        return eligible
    
    def _get_broker_name(self, broker_id: str) -> str:
        """
        Get broker name from ID.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            str: Broker name
        """
        instance = self.broker_manager.get_instance(broker_id)
        if instance:
            return instance.config.name.value
        return broker_id
    
    # ========================================================================
    # ROUTING STRATEGIES
    # ========================================================================
    
    async def _route_round_robin(
        self,
        symbol: str,
        eligible: List[str],
        order_type: OrderType,
        asset_class: Optional[AssetClass] = None,
        prefer_broker_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> BrokerRoute:
        """Round-robin routing strategy."""
        # Use a rotating index
        if not hasattr(self, "_round_robin_index"):
            self._round_robin_index = 0
        
        selected = eligible[self._round_robin_index % len(eligible)]
        self._round_robin_index += 1
        
        return BrokerRoute(
            broker_id=selected,
            broker_name=self._get_broker_name(selected),
            score=1.0,
            reason="round_robin",
        )
    
    async def _route_least_loaded(
        self,
        symbol: str,
        eligible: List[str],
        order_type: OrderType,
        asset_class: Optional[AssetClass] = None,
        prefer_broker_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> BrokerRoute:
        """Least loaded routing strategy."""
        def get_load(broker_id: str) -> float:
            instance = self.broker_manager.get_instance(broker_id)
            if not instance:
                return 999999
            
            # Combine usage count and error rate
            usage = instance.usage_count
            errors = instance.error_count
            total = max(usage + errors, 1)
            load = (usage / total) + (errors / max(total, 1)) * 2
            return load
        
        selected = min(eligible, key=get_load)
        
        return BrokerRoute(
            broker_id=selected,
            broker_name=self._get_broker_name(selected),
            score=1.0 / (get_load(selected) + 0.01),
            reason="least_loaded",
        )
    
    async def _route_fastest(
        self,
        symbol: str,
        eligible: List[str],
        order_type: OrderType,
        asset_class: Optional[AssetClass] = None,
        prefer_broker_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> BrokerRoute:
        """Fastest latency routing strategy."""
        def get_avg_latency(broker_id: str) -> float:
            samples = self._broker_latency.get(broker_id, deque())
            if not samples:
                return 100.0  # Default latency
            return sum(samples) / len(samples)
        
        selected = min(eligible, key=get_avg_latency)
        avg_latency = get_avg_latency(selected)
        
        return BrokerRoute(
            broker_id=selected,
            broker_name=self._get_broker_name(selected),
            score=100.0 / (avg_latency + 1),
            reason="fastest_latency",
            estimated_latency=avg_latency,
        )
    
    async def _route_lowest_cost(
        self,
        symbol: str,
        eligible: List[str],
        order_type: OrderType,
        asset_class: Optional[AssetClass] = None,
        prefer_broker_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> BrokerRoute:
        """Lowest cost routing strategy."""
        def get_cost(broker_id: str) -> float:
            cost = self._broker_costs.get(broker_id)
            if not cost:
                return 0.1  # Default cost
            return cost.total_trading_cost
        
        selected = min(eligible, key=get_cost)
        cost = get_cost(selected)
        
        return BrokerRoute(
            broker_id=selected,
            broker_name=self._get_broker_name(selected),
            score=1.0 / (cost + 0.0001),
            reason="lowest_cost",
            estimated_cost=cost,
        )
    
    async def _route_symbol_pinned(
        self,
        symbol: str,
        eligible: List[str],
        order_type: OrderType,
        asset_class: Optional[AssetClass] = None,
        prefer_broker_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> BrokerRoute:
        """Symbol pinning routing strategy."""
        # Check if symbol is pinned
        if symbol in self._symbol_pins:
            pinned = self._symbol_pins[symbol]
            if pinned in eligible:
                return BrokerRoute(
                    broker_id=pinned,
                    broker_name=self._get_broker_name(pinned),
                    score=1.0,
                    reason="symbol_pinned",
                )
        
        # Fallback to smart routing
        return await self._route_smart(
            symbol=symbol,
            eligible=eligible,
            order_type=order_type,
            asset_class=asset_class,
            prefer_broker_id=prefer_broker_id,
            context=context,
        )
    
    async def _route_market_type(
        self,
        symbol: str,
        eligible: List[str],
        order_type: OrderType,
        asset_class: Optional[AssetClass] = None,
        prefer_broker_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> BrokerRoute:
        """Market type routing strategy."""
        if asset_class:
            # Filter by asset class support
            for broker_id in eligible:
                capabilities = self._broker_capabilities.get(broker_id)
                if capabilities and capabilities.can_trade(symbol, asset_class):
                    return BrokerRoute(
                        broker_id=broker_id,
                        broker_name=self._get_broker_name(broker_id),
                        score=1.0,
                        reason=f"market_type_{asset_class.value}",
                    )
        
        # Fallback to first eligible
        selected = eligible[0]
        return BrokerRoute(
            broker_id=selected,
            broker_name=self._get_broker_name(selected),
            score=0.5,
            reason="market_type_fallback",
        )
    
    async def _route_failover(
        self,
        symbol: str,
        eligible: List[str],
        order_type: OrderType,
        asset_class: Optional[AssetClass] = None,
        prefer_broker_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> BrokerRoute:
        """Failover routing strategy."""
        # Try preferred first
        if prefer_broker_id and prefer_broker_id in eligible:
            selected = prefer_broker_id
            reason = "failover_preferred"
        else:
            # Try primary broker
            primary = self.broker_manager.get_primary()
            if primary and primary.id in eligible:
                selected = primary.id
                reason = "failover_primary"
            else:
                selected = eligible[0]
                reason = "failover_available"
        
        return BrokerRoute(
            broker_id=selected,
            broker_name=self._get_broker_name(selected),
            score=0.9 if reason == "failover_preferred" else 0.7,
            reason=reason,
        )
    
    async def _route_geographic(
        self,
        symbol: str,
        eligible: List[str],
        order_type: OrderType,
        asset_class: Optional[AssetClass] = None,
        prefer_broker_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> BrokerRoute:
        """Geographic routing strategy."""
        # Placeholder - can be extended with actual geography data
        # For now, use latency as proxy for geographic proximity
        return await self._route_fastest(
            symbol=symbol,
            eligible=eligible,
            order_type=order_type,
            asset_class=asset_class,
            prefer_broker_id=prefer_broker_id,
            context=context,
        )
    
    async def _route_smart(
        self,
        symbol: str,
        eligible: List[str],
        order_type: OrderType,
        asset_class: Optional[AssetClass] = None,
        prefer_broker_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> BrokerRoute:
        """
        Smart routing strategy considering multiple factors.
        
        Factors considered:
        - Latency (40% weight)
        - Success rate (30% weight)
        - Cost (20% weight)
        - Load (10% weight)
        """
        scores = {}
        
        for broker_id in eligible:
            score = 0.0
            
            # Latency score (lower is better)
            latency_samples = self._broker_latency.get(broker_id, deque())
            if latency_samples:
                avg_latency = sum(latency_samples) / len(latency_samples)
                latency_score = max(0, 100 - avg_latency) / 100
            else:
                latency_score = 0.5
            score += latency_score * 0.4
            
            # Success rate score
            success_samples = self._broker_success_rate.get(broker_id, deque())
            if success_samples:
                success_rate = sum(success_samples) / len(success_samples)
            else:
                success_rate = 0.95  # Default high success rate
            score += success_rate * 0.3
            
            # Cost score (lower is better)
            cost = self._broker_costs.get(broker_id)
            if cost:
                cost_score = max(0, 1 - cost.total_trading_cost)
            else:
                cost_score = 0.5
            score += cost_score * 0.2
            
            # Load score (lower is better)
            instance = self.broker_manager.get_instance(broker_id)
            if instance:
                load = instance.usage_count / max(instance.usage_count + instance.error_count, 1)
                load_score = 1 - load
            else:
                load_score = 0.5
            score += load_score * 0.1
            
            # Preference adjustment
            if prefer_broker_id and broker_id == prefer_broker_id:
                score += 0.2
            
            scores[broker_id] = score
        
        # Select best scoring broker
        selected = max(scores, key=scores.get)
        selected_score = scores[selected]
        
        # Get metrics for selected
        avg_latency = 0
        if selected in self._broker_latency and self._broker_latency[selected]:
            avg_latency = sum(self._broker_latency[selected]) / len(self._broker_latency[selected])
        
        cost = self._broker_costs.get(selected)
        estimated_cost = cost.total_trading_cost if cost else None
        
        return BrokerRoute(
            broker_id=selected,
            broker_name=self._get_broker_name(selected),
            score=selected_score,
            reason="smart_routing",
            estimated_cost=estimated_cost,
            estimated_latency=avg_latency or None,
            tags={
                "score_components": {
                    "latency": selected_score * 0.4,
                    "success_rate": selected_score * 0.3,
                    "cost": selected_score * 0.2,
                    "load": selected_score * 0.1,
                }
            },
        )
    
    async def _route_random(
        self,
        symbol: str,
        eligible: List[str],
        order_type: OrderType,
        asset_class: Optional[AssetClass] = None,
        prefer_broker_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> BrokerRoute:
        """Random routing strategy."""
        selected = random.choice(eligible)
        
        return BrokerRoute(
            broker_id=selected,
            broker_name=self._get_broker_name(selected),
            score=random.random(),
            reason="random",
        )
    
    # ========================================================================
    # PERFORMANCE TRACKING
    # ========================================================================
    
    def record_request(
        self,
        broker_id: str,
        success: bool,
        latency_ms: float,
        cost: Optional[float] = None,
    ) -> None:
        """
        Record a request for performance tracking.
        
        Args:
            broker_id: Broker identifier
            success: Whether the request was successful
            latency_ms: Request latency in milliseconds
            cost: Optional cost of the request
        """
        # Record latency
        self._broker_latency[broker_id].append(latency_ms)
        
        # Record success
        self._broker_success_rate[broker_id].append(1.0 if success else 0.0)
        
        # Update success rate average
        success_samples = self._broker_success_rate[broker_id]
        avg_success = sum(success_samples) / len(success_samples) if success_samples else 1.0
        self._broker_performance[broker_id]["success_rate"] = avg_success
        
        # Update latency average
        latency_samples = self._broker_latency[broker_id]
        avg_latency = sum(latency_samples) / len(latency_samples) if latency_samples else 0
        self._broker_performance[broker_id]["avg_latency"] = avg_latency
        
        # Update cost if provided
        if cost is not None:
            current_cost = self._broker_costs.get(broker_id)
            if current_cost:
                # Smooth update
                current_cost.total_trading_cost = current_cost.total_trading_cost * 0.9 + cost * 0.1
    
    def record_order_result(
        self,
        broker_id: str,
        success: bool,
        order_type: OrderType,
        execution_time_ms: float,
        slippage: Optional[float] = None,
        fees: Optional[float] = None,
    ) -> None:
        """
        Record an order result for performance tracking.
        
        Args:
            broker_id: Broker identifier
            success: Whether the order was successful
            order_type: Type of order
            execution_time_ms: Execution time in milliseconds
            slippage: Optional slippage
            fees: Optional fees
        """
        # Update success rate
        self._broker_success_rate[broker_id].append(1.0 if success else 0.0)
        
        # Update cost if fees provided
        if fees is not None:
            cost = self._broker_costs.get(broker_id)
            if cost:
                if order_type == OrderType.MARKET:
                    cost.taker_fee = cost.taker_fee * 0.9 + fees * 0.1
                else:
                    cost.maker_fee = cost.maker_fee * 0.9 + fees * 0.1
        
        # Update slippage
        if slippage is not None:
            cost = self._broker_costs.get(broker_id)
            if cost:
                cost.slippage_avg = cost.slippage_avg * 0.9 + abs(slippage) * 0.1
    
    def set_broker_cost(self, broker_id: str, cost: BrokerCost) -> None:
        """
        Set cost metrics for a broker.
        
        Args:
            broker_id: Broker identifier
            cost: Broker cost metrics
        """
        self._broker_costs[broker_id] = cost
    
    # ========================================================================
    # STATISTICS AND REPORTING
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get routing statistics.
        
        Returns:
            Dict: Routing statistics
        """
        return {
            **self._stats,
            "strategy_usage": dict(self._stats["strategy_usage"]),
            "broker_selection": dict(self._stats["broker_selection"]),
            "by_symbol": dict(self._stats["by_symbol"]),
            "performance": self._broker_performance,
            "broker_costs": {
                bid: {
                    "commission_rate": cost.commission_rate,
                    "maker_fee": cost.maker_fee,
                    "taker_fee": cost.taker_fee,
                    "spread_avg": cost.spread_avg,
                    "slippage_avg": cost.slippage_avg,
                    "total_cost": cost.total_trading_cost,
                }
                for bid, cost in self._broker_costs.items()
            },
            "symbol_pins": self._symbol_pins,
            "decision_history_count": len(self._decision_history),
            "active_brokers": len(self._broker_capabilities),
        }
    
    def get_broker_performance(self, broker_id: str) -> Dict[str, Any]:
        """
        Get performance for a specific broker.
        
        Args:
            broker_id: Broker identifier
            
        Returns:
            Dict: Performance metrics
        """
        performance = self._broker_performance.get(broker_id, {})
        latency_samples = self._broker_latency.get(broker_id, deque())
        success_samples = self._broker_success_rate.get(broker_id, deque())
        
        return {
            **performance,
            "latency_samples": len(latency_samples),
            "avg_latency_ms": sum(latency_samples) / len(latency_samples) if latency_samples else 0,
            "min_latency_ms": min(latency_samples) if latency_samples else 0,
            "max_latency_ms": max(latency_samples) if latency_samples else 0,
            "success_rate": sum(success_samples) / len(success_samples) if success_samples else 1.0,
            "success_samples": len(success_samples),
        }
    
    def get_recommendations(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Get routing recommendations for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            List[Dict]: Recommendations
        """
        recommendations = []
        
        for broker_id, capabilities in self._broker_capabilities.items():
            if not capabilities.can_trade(symbol):
                continue
            
            instance = self.broker_manager.get_instance(broker_id)
            if not instance or not instance.is_healthy:
                continue
            
            perf = self.get_broker_performance(broker_id)
            cost = self._broker_costs.get(broker_id)
            
            recommendations.append({
                "broker_id": broker_id,
                "broker_name": self._get_broker_name(broker_id),
                "success_rate": perf.get("success_rate", 1.0),
                "avg_latency_ms": perf.get("avg_latency_ms", 0),
                "total_cost": cost.total_trading_cost if cost else 0,
                "load": instance.usage_count,
                "score": perf.get("success_rate", 1.0) * 0.4
                        + (1 - perf.get("avg_latency_ms", 0) / 1000) * 0.3
                        + (1 - (cost.total_trading_cost if cost else 0)) * 0.2
                        + (1 - instance.usage_count / max(instance.usage_count + instance.error_count, 1)) * 0.1,
            })
        
        return sorted(recommendations, key=lambda x: x["score"], reverse=True)
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def clear_symbol_pin(self, symbol: str) -> None:
        """
        Clear symbol pinning for a symbol.
        
        Args:
            symbol: Trading symbol
        """
        if symbol in self._symbol_pins:
            del self._symbol_pins[symbol]
        if symbol in self._symbol_last_used:
            del self._symbol_last_used[symbol]
        self.logger.debug(f"Cleared symbol pin for {symbol}")
    
    def get_pinned_broker(self, symbol: str) -> Optional[str]:
        """
        Get the pinned broker for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Optional[str]: Pinned broker ID or None
        """
        return self._symbol_pins.get(symbol)
    
    def reset_stats(self) -> None:
        """Reset routing statistics."""
        self._stats = {
            "total_routes": 0,
            "strategy_usage": defaultdict(int),
            "broker_selection": defaultdict(int),
            "by_symbol": defaultdict(lambda: defaultdict(int)),
            "avg_routing_time_ms": 0.0,
            "routing_samples": 0,
        }
        self._decision_history.clear()
        self.logger.info("Reset routing statistics")
    
    def get_decision_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[RoutingDecision]:
        """
        Get routing decision history.
        
        Args:
            symbol: Optional symbol filter
            limit: Maximum number of decisions
            
        Returns:
            List[RoutingDecision]: Decision history
        """
        if symbol:
            return [
                d for d in self._decision_history
                if d.symbol == symbol
            ][-limit:]
        return list(self._decision_history)[-limit:]


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Enums
    "RoutingStrategy",
    "RoutingPreference",
    
    # Models
    "BrokerCapability",
    "BrokerCost",
    "BrokerRoute",
    "RoutingDecision",
    
    # Class
    "BrokerRouter",
]
