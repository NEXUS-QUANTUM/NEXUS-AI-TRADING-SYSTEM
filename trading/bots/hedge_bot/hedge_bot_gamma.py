# trading/bots/hedge_bot/hedge_bot_gamma.py

import asyncio
import logging
import time
import math
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union, Tuple, Callable
from decimal import Decimal
from collections import defaultdict

logger = logging.getLogger(__name__)


class GammaStrategyType(str, Enum):
    SCALPING = "scalping"
    HEDGING = "hedging"
    ARBITRAGE = "arbitrage"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY = "volatility"
    TREND = "trend"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"
    GRID = "grid"
    DCA = "dca"
    MARTINGALE = "martingale"
    KELLY = "kelly"
    PAIRS = "pairs"


class GammaPositionType(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"
    COVERED = "covered"
    NAKED = "naked"
    SPREAD = "spread"
    STRANGLE = "strangle"
    STRADDLE = "straddle"
    BUTTERFLY = "butterfly"
    CONDOR = "condor"


class GammaRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class GammaPosition:
    id: str
    symbol: str
    position_type: GammaPositionType
    entry_price: float
    current_price: float
    size: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    implied_volatility: float
    realized_volatility: float
    time_to_expiry: float
    strike_price: float
    premium: float
    pnl: float
    pnl_percent: float
    risk_level: GammaRiskLevel
    stop_loss: float
    take_profit: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class GammaSignal:
    id: str
    symbol: str
    strategy: GammaStrategyType
    position_type: GammaPositionType
    entry_price: float
    target_price: float
    stop_loss: float
    confidence: float
    risk_reward_ratio: float
    timestamp: float
    expiry: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GammaMetrics:
    total_delta: float
    total_gamma: float
    total_theta: float
    total_vega: float
    total_rho: float
    gamma_exposure: float
    delta_gamma_ratio: float
    vega_gamma_ratio: float
    theta_gamma_ratio: float
    implied_volatility: float
    realized_volatility: float
    volatility_skew: float
    risk_reversal: float
    butterfly: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class GammaOrder:
    id: str
    signal_id: str
    symbol: str
    side: str
    price: float
    quantity: float
    order_type: str
    status: str
    filled_quantity: float
    avg_price: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    executed_at: Optional[float] = None


class GammaTradingBot:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._positions: Dict[str, GammaPosition] = {}
        self._signals: Dict[str, GammaSignal] = {}
        self._orders: Dict[str, GammaOrder] = {}
        self._metrics: Dict[str, GammaMetrics] = {}
        self._strategies: Dict[GammaStrategyType, Callable] = {}
        self._risk_managers: List[Callable] = []
        self._observers: List[Callable] = []
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._executor_task: Optional[asyncio.Task] = None
        
        self._initialize_strategies()
        self._initialize_risk_managers()

    def _initialize_strategies(self) -> None:
        self.register_strategy(GammaStrategyType.SCALPING, self._strategy_scalping)
        self.register_strategy(GammaStrategyType.HEDGING, self._strategy_hedging)
        self.register_strategy(GammaStrategyType.ARBITRAGE, self._strategy_arbitrage)
        self.register_strategy(GammaStrategyType.MOMENTUM, self._strategy_momentum)
        self.register_strategy(GammaStrategyType.MEAN_REVERSION, self._strategy_mean_reversion)
        self.register_strategy(GammaStrategyType.VOLATILITY, self._strategy_volatility)
        self.register_strategy(GammaStrategyType.TREND, self._strategy_trend)
        self.register_strategy(GammaStrategyType.BREAKOUT, self._strategy_breakout)
        self.register_strategy(GammaStrategyType.REVERSAL, self._strategy_reversal)
        self.register_strategy(GammaStrategyType.GRID, self._strategy_grid)
        self.register_strategy(GammaStrategyType.DCA, self._strategy_dca)
        self.register_strategy(GammaStrategyType.PAIRS, self._strategy_pairs)

    def _initialize_risk_managers(self) -> None:
        self.register_risk_manager(self._risk_check_delta)
        self.register_risk_manager(self._risk_check_gamma)
        self.register_risk_manager(self._risk_check_vega)
        self.register_risk_manager(self._risk_check_theta)
        self.register_risk_manager(self._risk_check_volatility)

    def register_strategy(self, strategy_type: GammaStrategyType, strategy: Callable) -> None:
        self._strategies[strategy_type] = strategy

    def register_risk_manager(self, risk_manager: Callable) -> None:
        self._risk_managers.append(risk_manager)

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def generate_signal(
        self,
        symbol: str,
        strategy_type: GammaStrategyType,
        market_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[GammaSignal]:
        async with self._lock:
            if strategy_type not in self._strategies:
                return None
            
            strategy = self._strategies[strategy_type]
            signal_data = await strategy(symbol, market_data)
            
            if not signal_data:
                return None
            
            signal = GammaSignal(
                id=hashlib.md5(f"{symbol}_{time.time()}".encode()).hexdigest(),
                symbol=symbol,
                strategy=strategy_type,
                position_type=signal_data.get("position_type", GammaPositionType.NEUTRAL),
                entry_price=signal_data["entry_price"],
                target_price=signal_data["target_price"],
                stop_loss=signal_data["stop_loss"],
                confidence=signal_data.get("confidence", 0.5),
                risk_reward_ratio=signal_data.get("risk_reward_ratio", 1.0),
                timestamp=time.time(),
                expiry=signal_data.get("expiry"),
                metadata=metadata or {}
            )
            
            if not await self._validate_signal(signal):
                return None
            
            self._signals[signal.id] = signal
            await self._notify_observers("signal_generated", signal)
            return signal

    async def _validate_signal(self, signal: GammaSignal) -> bool:
        if signal.entry_price <= 0:
            return False
        
        if signal.target_price <= 0:
            return False
        
        if signal.stop_loss >= signal.entry_price and signal.position_type in [GammaPositionType.LONG, GammaPositionType.BUTTERFLY]:
            return False
        
        if signal.stop_loss <= signal.entry_price and signal.position_type == GammaPositionType.SHORT:
            return False
        
        if signal.confidence < 0.3:
            return False
        
        for risk_manager in self._risk_managers:
            if not await risk_manager(signal):
                return False
        
        return True

    async def execute_signal(self, signal_id: str) -> Optional[GammaOrder]:
        async with self._lock:
            if signal_id not in self._signals:
                return None
            
            signal = self._signals[signal_id]
            
            order = GammaOrder(
                id=hashlib.md5(f"{signal_id}_{time.time()}".encode()).hexdigest(),
                signal_id=signal_id,
                symbol=signal.symbol,
                side="buy" if signal.position_type in [GammaPositionType.LONG, GammaPositionType.COVERED] else "sell",
                price=signal.entry_price,
                quantity=1.0,
                order_type="limit",
                status="pending",
                filled_quantity=0,
                avg_price=0
            )
            
            self._orders[order.id] = order
            await self._notify_observers("order_created", order)
            
            return order

    async def update_position(
        self,
        position_id: str,
        current_price: float,
        implied_volatility: float,
        realized_volatility: float,
        time_to_expiry: float
    ) -> Optional[GammaPosition]:
        async with self._lock:
            if position_id not in self._positions:
                return None
            
            position = self._positions[position_id]
            position.current_price = current_price
            position.implied_volatility = implied_volatility
            position.realized_volatility = realized_volatility
            position.time_to_expiry = time_to_expiry
            position.updated_at = time.time()
            
            position.pnl = (position.current_price - position.entry_price) * position.size
            position.pnl_percent = (position.pnl / (position.entry_price * position.size)) * 100
            
            position.delta = await self._calculate_delta(position)
            position.gamma = await self._calculate_gamma(position)
            position.theta = await self._calculate_theta(position)
            position.vega = await self._calculate_vega(position)
            position.rho = await self._calculate_rho(position)
            
            await self._check_risk_limits(position)
            
            await self._notify_observers("position_updated", position)
            return position

    async def _calculate_delta(self, position: GammaPosition) -> float:
        d1 = self._calculate_d1(position)
        return self._normal_cdf(d1)

    async def _calculate_gamma(self, position: GammaPosition) -> float:
        d1 = self._calculate_d1(position)
        return self._normal_pdf(d1) / (position.current_price * position.implied_volatility * math.sqrt(position.time_to_expiry))

    async def _calculate_theta(self, position: GammaPosition) -> float:
        d1 = self._calculate_d1(position)
        d2 = d1 - position.implied_volatility * math.sqrt(position.time_to_expiry)
        
        theta = -position.current_price * position.implied_volatility * self._normal_pdf(d1) / (2 * math.sqrt(position.time_to_expiry))
        theta -= position.strike_price * position.implied_volatility * math.exp(-0.05 * position.time_to_expiry) * self._normal_cdf(d2)
        
        return theta / 365

    async def _calculate_vega(self, position: GammaPosition) -> float:
        d1 = self._calculate_d1(position)
        return position.current_price * self._normal_pdf(d1) * math.sqrt(position.time_to_expiry) / 100

    async def _calculate_rho(self, position: GammaPosition) -> float:
        d1 = self._calculate_d1(position)
        d2 = d1 - position.implied_volatility * math.sqrt(position.time_to_expiry)
        return position.strike_price * position.time_to_expiry * math.exp(-0.05 * position.time_to_expiry) * self._normal_cdf(d2) / 100

    def _calculate_d1(self, position: GammaPosition) -> float:
        if position.time_to_expiry <= 0 or position.implied_volatility <= 0:
            return 0
        
        return (math.log(position.current_price / position.strike_price) +
                0.05 * position.time_to_expiry) / (position.implied_volatility * math.sqrt(position.time_to_expiry))

    def _normal_cdf(self, x: float) -> float:
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _normal_pdf(self, x: float) -> float:
        return math.exp(-x*x/2) / math.sqrt(2 * math.pi)

    async def _check_risk_limits(self, position: GammaPosition) -> None:
        if abs(position.delta) > 0.9:
            position.risk_level = GammaRiskLevel.EXTREME
        elif abs(position.delta) > 0.7:
            position.risk_level = GammaRiskLevel.HIGH
        elif abs(position.delta) > 0.5:
            position.risk_level = GammaRiskLevel.MEDIUM
        else:
            position.risk_level = GammaRiskLevel.LOW
        
        if position.gamma > 0.1:
            position.risk_level = GammaRiskLevel.HIGH
        
        if abs(position.theta) > 0.5:
            position.risk_level = GammaRiskLevel.HIGH

    async def _risk_check_delta(self, signal: GammaSignal) -> bool:
        return abs(signal.target_price - signal.entry_price) / signal.entry_price < 0.2

    async def _risk_check_gamma(self, signal: GammaSignal) -> bool:
        return True

    async def _risk_check_vega(self, signal: GammaSignal) -> bool:
        return True

    async def _risk_check_theta(self, signal: GammaSignal) -> bool:
        return True

    async def _risk_check_volatility(self, signal: GammaSignal) -> bool:
        return True

    async def _strategy_scalping(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        return {
            "position_type": GammaPositionType.LONG,
            "entry_price": market_data.get("bid", 0),
            "target_price": market_data.get("bid", 0) * 1.005,
            "stop_loss": market_data.get("bid", 0) * 0.995,
            "confidence": 0.6,
            "risk_reward_ratio": 1.0
        }

    async def _strategy_hedging(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        return {
            "position_type": GammaPositionType.SHORT,
            "entry_price": market_data.get("ask", 0),
            "target_price": market_data.get("ask", 0) * 0.995,
            "stop_loss": market_data.get("ask", 0) * 1.005,
            "confidence": 0.7,
            "risk_reward_ratio": 1.0
        }

    async def _strategy_arbitrage(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        return {
            "position_type": GammaPositionType.SPREAD,
            "entry_price": market_data.get("bid", 0),
            "target_price": market_data.get("bid", 0) * 1.01,
            "stop_loss": market_data.get("bid", 0) * 0.99,
            "confidence": 0.8,
            "risk_reward_ratio": 1.0
        }

    async def _strategy_momentum(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        momentum = market_data.get("momentum", 0)
        direction = 1 if momentum > 0 else -1
        
        return {
            "position_type": GammaPositionType.LONG if direction > 0 else GammaPositionType.SHORT,
            "entry_price": market_data.get("close", 0),
            "target_price": market_data.get("close", 0) * (1 + direction * 0.02),
            "stop_loss": market_data.get("close", 0) * (1 - direction * 0.01),
            "confidence": 0.5 + abs(momentum) * 0.3,
            "risk_reward_ratio": 2.0
        }

    async def _strategy_mean_reversion(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        mean = market_data.get("mean", 0)
        price = market_data.get("close", 0)
        deviation = (price - mean) / mean if mean > 0 else 0
        
        return {
            "position_type": GammaPositionType.SHORT if deviation > 0 else GammaPositionType.LONG,
            "entry_price": price,
            "target_price": mean,
            "stop_loss": price * (1 + abs(deviation) * 0.5),
            "confidence": min(0.8, abs(deviation) * 2),
            "risk_reward_ratio": 1.5
        }

    async def _strategy_volatility(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        iv = market_data.get("implied_volatility", 0)
        rv = market_data.get("realized_volatility", 0)
        
        if iv > rv * 1.2:
            return {
                "position_type": GammaPositionType.SHORT,
                "entry_price": market_data.get("close", 0),
                "target_price": market_data.get("close", 0) * 0.99,
                "stop_loss": market_data.get("close", 0) * 1.01,
                "confidence": 0.7,
                "risk_reward_ratio": 1.0
            }
        elif rv > iv * 1.2:
            return {
                "position_type": GammaPositionType.LONG,
                "entry_price": market_data.get("close", 0),
                "target_price": market_data.get("close", 0) * 1.01,
                "stop_loss": market_data.get("close", 0) * 0.99,
                "confidence": 0.7,
                "risk_reward_ratio": 1.0
            }
        
        return None

    async def _strategy_trend(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        trend = market_data.get("trend", 0)
        direction = 1 if trend > 0 else -1
        
        return {
            "position_type": GammaPositionType.LONG if direction > 0 else GammaPositionType.SHORT,
            "entry_price": market_data.get("close", 0),
            "target_price": market_data.get("close", 0) * (1 + direction * 0.03),
            "stop_loss": market_data.get("close", 0) * (1 - direction * 0.015),
            "confidence": 0.5 + abs(trend) * 0.4,
            "risk_reward_ratio": 2.0
        }

    async def _strategy_breakout(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        high = market_data.get("high_24h", 0)
        low = market_data.get("low_24h", 0)
        price = market_data.get("close", 0)
        
        if price > high * 0.99:
            return {
                "position_type": GammaPositionType.LONG,
                "entry_price": price,
                "target_price": price * 1.02,
                "stop_loss": price * 0.99,
                "confidence": 0.6,
                "risk_reward_ratio": 2.0
            }
        elif price < low * 1.01:
            return {
                "position_type": GammaPositionType.SHORT,
                "entry_price": price,
                "target_price": price * 0.98,
                "stop_loss": price * 1.01,
                "confidence": 0.6,
                "risk_reward_ratio": 2.0
            }
        
        return None

    async def _strategy_reversal(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        rsi = market_data.get("rsi", 50)
        
        if rsi < 30:
            return {
                "position_type": GammaPositionType.LONG,
                "entry_price": market_data.get("close", 0),
                "target_price": market_data.get("close", 0) * 1.02,
                "stop_loss": market_data.get("close", 0) * 0.99,
                "confidence": 0.7,
                "risk_reward_ratio": 2.0
            }
        elif rsi > 70:
            return {
                "position_type": GammaPositionType.SHORT,
                "entry_price": market_data.get("close", 0),
                "target_price": market_data.get("close", 0) * 0.98,
                "stop_loss": market_data.get("close", 0) * 1.01,
                "confidence": 0.7,
                "risk_reward_ratio": 2.0
            }
        
        return None

    async def _strategy_grid(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        return {
            "position_type": GammaPositionType.NEUTRAL,
            "entry_price": market_data.get("close", 0),
            "target_price": market_data.get("close", 0) * 1.01,
            "stop_loss": market_data.get("close", 0) * 0.99,
            "confidence": 0.5,
            "risk_reward_ratio": 1.0
        }

    async def _strategy_dca(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        return {
            "position_type": GammaPositionType.LONG,
            "entry_price": market_data.get("close", 0) * 0.98,
            "target_price": market_data.get("close", 0) * 1.01,
            "stop_loss": market_data.get("close", 0) * 0.97,
            "confidence": 0.5,
            "risk_reward_ratio": 1.5
        }

    async def _strategy_pairs(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        spread = market_data.get("spread", 0)
        
        if spread > 0:
            return {
                "position_type": GammaPositionType.SPREAD,
                "entry_price": market_data.get("close", 0),
                "target_price": market_data.get("close", 0) * 0.99,
                "stop_loss": market_data.get("close", 0) * 1.01,
                "confidence": 0.6,
                "risk_reward_ratio": 1.0
            }
        
        return None

    async def compute_metrics(self) -> GammaMetrics:
        total_delta = sum(p.delta for p in self._positions.values())
        total_gamma = sum(p.gamma for p in self._positions.values())
        total_theta = sum(p.theta for p in self._positions.values())
        total_vega = sum(p.vega for p in self._positions.values())
        total_rho = sum(p.rho for p in self._positions.values())
        
        gamma_exposure = total_gamma * 100
        
        metrics = GammaMetrics(
            total_delta=total_delta,
            total_gamma=total_gamma,
            total_theta=total_theta,
            total_vega=total_vega,
            total_rho=total_rho,
            gamma_exposure=gamma_exposure,
            delta_gamma_ratio=total_delta / total_gamma if total_gamma != 0 else 0,
            vega_gamma_ratio=total_vega / total_gamma if total_gamma != 0 else 0,
            theta_gamma_ratio=total_theta / total_gamma if total_gamma != 0 else 0,
            implied_volatility=np.mean([p.implied_volatility for p in self._positions.values()]) if self._positions else 0,
            realized_volatility=np.mean([p.realized_volatility for p in self._positions.values()]) if self._positions else 0,
            volatility_skew=0,
            risk_reversal=0,
            butterfly=0
        )
        
        self._metrics[hashlib.md5(str(time.time()).encode()).hexdigest()] = metrics
        return metrics

    async def _notify_observers(self, event: str, *args) -> None:
        for observer in self._observers:
            try:
                if asyncio.iscoroutinefunction(observer):
                    await observer(event, *args)
                else:
                    observer(event, *args)
            except Exception as e:
                logger.error(f"Observer error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "positions": len(self._positions),
            "signals": len(self._signals),
            "orders": len(self._orders),
            "metrics": len(self._metrics),
            "strategies": len(self._strategies),
            "risk_managers": len(self._risk_managers),
            "running": self._running
        }


__all__ = [
    "GammaStrategyType",
    "GammaPositionType",
    "GammaRiskLevel",
    "GammaPosition",
    "GammaSignal",
    "GammaMetrics",
    "GammaOrder",
    "GammaTradingBot"
]
