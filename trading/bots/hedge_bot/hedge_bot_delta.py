# trading/bots/hedge_bot/hedge_bot_delta.py

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


class DeltaType(str, Enum):
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    HEDGED = "hedged"
    UNHEDGED = "unhedged"
    DYNAMIC = "dynamic"


class DeltaPositionType(str, Enum):
    LONG = "long"
    SHORT = "short"
    COVERED = "covered"
    NAKED = "naked"


@dataclass
class DeltaPosition:
    id: str
    symbol: str
    position_type: DeltaPositionType
    quantity: float
    entry_price: float
    current_price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    pnl: float
    pnl_percent: float
    time_to_expiry: float
    strike_price: float
    implied_volatility: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class DeltaMetrics:
    total_delta: float
    net_delta: float
    gross_delta: float
    weighted_delta: float
    delta_gamma_ratio: float
    delta_vega_ratio: float
    delta_theta_ratio: float
    delta_rho_ratio: float
    implied_volatility: float
    realized_volatility: float
    volatility_skew: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class DeltaSignal:
    id: str
    symbol: str
    action: str
    delta_target: float
    current_delta: float
    quantity: float
    confidence: float
    timestamp: float
    expiry: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeltaHedge:
    id: str
    symbol: str
    hedge_ratio: float
    hedge_amount: float
    direction: str
    status: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    executed_at: Optional[float] = None


class DeltaManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._positions: Dict[str, DeltaPosition] = {}
        self._signals: Dict[str, DeltaSignal] = {}
        self._hedges: Dict[str, DeltaHedge] = {}
        self._metrics: Dict[str, DeltaMetrics] = {}
        self._observers: List[Callable] = []
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._hedge_task: Optional[asyncio.Task] = None
        
        self._initialize_default_hedges()

    def _initialize_default_hedges(self) -> None:
        pass

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def add_position(
        self,
        symbol: str,
        position_type: DeltaPositionType,
        quantity: float,
        entry_price: float,
        strike_price: float = 0.0,
        time_to_expiry: float = 0.0,
        implied_volatility: float = 0.3,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DeltaPosition:
        async with self._lock:
            position_id = hashlib.md5(f"{symbol}_{time.time()}".encode()).hexdigest()
            
            position = DeltaPosition(
                id=position_id,
                symbol=symbol,
                position_type=position_type,
                quantity=quantity,
                entry_price=entry_price,
                current_price=entry_price,
                delta=0.0,
                gamma=0.0,
                theta=0.0,
                vega=0.0,
                rho=0.0,
                pnl=0.0,
                pnl_percent=0.0,
                time_to_expiry=time_to_expiry,
                strike_price=strike_price,
                implied_volatility=implied_volatility,
                metadata=metadata or {}
            )
            
            await self._update_greeks(position)
            self._positions[position_id] = position
            await self._notify_observers("position_added", position)
            return position

    async def update_position(
        self,
        position_id: str,
        current_price: float,
        implied_volatility: Optional[float] = None,
        time_to_expiry: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DeltaPosition]:
        async with self._lock:
            if position_id not in self._positions:
                return None
            
            position = self._positions[position_id]
            position.current_price = current_price
            
            if implied_volatility:
                position.implied_volatility = implied_volatility
            
            if time_to_expiry:
                position.time_to_expiry = time_to_expiry
            
            await self._update_greeks(position)
            await self._update_pnl(position)
            
            if metadata:
                position.metadata.update(metadata)
            
            position.updated_at = time.time()
            await self._notify_observers("position_updated", position)
            return position

    async def _update_greeks(self, position: DeltaPosition) -> None:
        if position.time_to_expiry <= 0:
            position.delta = 0.5
            position.gamma = 0.0
            position.theta = 0.0
            position.vega = 0.0
            position.rho = 0.0
            return
        
        d1 = self._calculate_d1(position)
        d2 = d1 - position.implied_volatility * math.sqrt(position.time_to_expiry)
        
        if position.position_type == DeltaPositionType.LONG:
            position.delta = self._normal_cdf(d1)
            position.gamma = self._normal_pdf(d1) / (position.current_price * position.implied_volatility * math.sqrt(position.time_to_expiry))
            position.theta = -position.current_price * position.implied_volatility * self._normal_pdf(d1) / (2 * math.sqrt(position.time_to_expiry))
            position.theta -= position.strike_price * position.implied_volatility * math.exp(-0.05 * position.time_to_expiry) * self._normal_cdf(d2)
            position.theta /= 365
            position.vega = position.current_price * self._normal_pdf(d1) * math.sqrt(position.time_to_expiry) / 100
            position.rho = position.strike_price * position.time_to_expiry * math.exp(-0.05 * position.time_to_expiry) * self._normal_cdf(d2) / 100
        
        elif position.position_type == DeltaPositionType.SHORT:
            position.delta = -self._normal_cdf(-d1)
            position.gamma = self._normal_pdf(d1) / (position.current_price * position.implied_volatility * math.sqrt(position.time_to_expiry))
            position.theta = position.current_price * position.implied_volatility * self._normal_pdf(d1) / (2 * math.sqrt(position.time_to_expiry))
            position.theta -= position.strike_price * position.implied_volatility * math.exp(-0.05 * position.time_to_expiry) * self._normal_cdf(-d2)
            position.theta /= 365
            position.vega = position.current_price * self._normal_pdf(d1) * math.sqrt(position.time_to_expiry) / 100
            position.rho = -position.strike_price * position.time_to_expiry * math.exp(-0.05 * position.time_to_expiry) * self._normal_cdf(-d2) / 100

    def _calculate_d1(self, position: DeltaPosition) -> float:
        if position.time_to_expiry <= 0 or position.implied_volatility <= 0:
            return 0
        
        return (math.log(position.current_price / position.strike_price) + 0.05 * position.time_to_expiry) / (position.implied_volatility * math.sqrt(position.time_to_expiry))

    def _normal_cdf(self, x: float) -> float:
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def _normal_pdf(self, x: float) -> float:
        return math.exp(-x*x/2) / math.sqrt(2 * math.pi)

    async def _update_pnl(self, position: DeltaPosition) -> None:
        position.pnl = (position.current_price - position.entry_price) * position.quantity
        position.pnl_percent = (position.pnl / (position.entry_price * position.quantity)) * 100

    async def remove_position(self, position_id: str) -> bool:
        async with self._lock:
            if position_id in self._positions:
                del self._positions[position_id]
                await self._notify_observers("position_removed", position_id)
                return True
            return False

    async def compute_metrics(self) -> DeltaMetrics:
        async with self._lock:
            total_delta = sum(p.delta * p.quantity for p in self._positions.values())
            net_delta = total_delta
            gross_delta = sum(abs(p.delta * p.quantity) for p in self._positions.values())
            weighted_delta = total_delta / len(self._positions) if self._positions else 0
            
            total_gamma = sum(p.gamma * p.quantity for p in self._positions.values())
            total_vega = sum(p.vega * p.quantity for p in self._positions.values())
            total_theta = sum(p.theta * p.quantity for p in self._positions.values())
            total_rho = sum(p.rho * p.quantity for p in self._positions.values())
            
            delta_gamma_ratio = total_delta / total_gamma if total_gamma != 0 else 0
            delta_vega_ratio = total_delta / total_vega if total_vega != 0 else 0
            delta_theta_ratio = total_delta / total_theta if total_theta != 0 else 0
            delta_rho_ratio = total_delta / total_rho if total_rho != 0 else 0
            
            implied_volatility = np.mean([p.implied_volatility for p in self._positions.values()]) if self._positions else 0
            
            metrics = DeltaMetrics(
                total_delta=total_delta,
                net_delta=net_delta,
                gross_delta=gross_delta,
                weighted_delta=weighted_delta,
                delta_gamma_ratio=delta_gamma_ratio,
                delta_vega_ratio=delta_vega_ratio,
                delta_theta_ratio=delta_theta_ratio,
                delta_rho_ratio=delta_rho_ratio,
                implied_volatility=implied_volatility,
                realized_volatility=0,
                volatility_skew=0,
                timestamp=time.time()
            )
            
            metrics_id = hashlib.md5(str(time.time()).encode()).hexdigest()
            self._metrics[metrics_id] = metrics
            await self._notify_observers("metrics_computed", metrics)
            return metrics

    async def generate_signal(
        self,
        symbol: str,
        action: str,
        delta_target: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DeltaSignal]:
        async with self._lock:
            current_delta = sum(p.delta * p.quantity for p in self._positions.values() if p.symbol == symbol)
            
            signal = DeltaSignal(
                id=hashlib.md5(f"{symbol}_{time.time()}".encode()).hexdigest(),
                symbol=symbol,
                action=action,
                delta_target=delta_target,
                current_delta=current_delta,
                quantity=abs(current_delta - delta_target),
                confidence=0.8,
                timestamp=time.time(),
                metadata=metadata or {}
            )
            
            self._signals[signal.id] = signal
            await self._notify_observers("signal_generated", signal)
            return signal

    async def execute_hedge(
        self,
        signal_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DeltaHedge]:
        async with self._lock:
            if signal_id not in self._signals:
                return None
            
            signal = self._signals[signal_id]
            
            hedge = DeltaHedge(
                id=hashlib.md5(f"{signal_id}_{time.time()}".encode()).hexdigest(),
                symbol=signal.symbol,
                hedge_ratio=signal.delta_target / signal.current_delta if signal.current_delta != 0 else 0,
                hedge_amount=signal.quantity,
                direction="buy" if signal.delta_target > signal.current_delta else "sell",
                status="executed",
                metadata=metadata or {},
                executed_at=time.time()
            )
            
            self._hedges[hedge.id] = hedge
            await self._notify_observers("hedge_executed", hedge)
            return hedge

    async def get_position(self, position_id: str) -> Optional[DeltaPosition]:
        return self._positions.get(position_id)

    async def get_positions(self) -> List[DeltaPosition]:
        return list(self._positions.values())

    async def get_metrics(self) -> List[DeltaMetrics]:
        return list(self._metrics.values())

    async def get_latest_metrics(self) -> Optional[DeltaMetrics]:
        if self._metrics:
            return max(self._metrics.values(), key=lambda m: m.timestamp)
        return None

    async def get_signal(self, signal_id: str) -> Optional[DeltaSignal]:
        return self._signals.get(signal_id)

    async def get_signals(self) -> List[DeltaSignal]:
        return list(self._signals.values())

    async def get_hedge(self, hedge_id: str) -> Optional[DeltaHedge]:
        return self._hedges.get(hedge_id)

    async def get_hedges(self) -> List[DeltaHedge]:
        return list(self._hedges.values())

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
            "hedges": len(self._hedges),
            "metrics": len(self._metrics),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "DeltaType",
    "DeltaPositionType",
    "DeltaPosition",
    "DeltaMetrics",
    "DeltaSignal",
    "DeltaHedge",
    "DeltaManager"
]
