# trading/bots/hedge_bot/hedge_bot_futures.py

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


class FuturesPositionType(str, Enum):
    LONG = "long"
    SHORT = "short"
    HEDGED = "hedged"
    SPREAD = "spread"
    CALENDAR = "calendar"
    INTER_COMMODITY = "inter_commodity"
    CRACK = "crack"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    BUTTERFLY = "butterfly"
    CONDOR = "condor"
    IRON_CONDOR = "iron_condor"
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    DIAGONAL = "diagonal"


class FuturesOrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    OCO = "oco"
    ICEBERG = "iceberg"
    TWAP = "twap"
    VWAP = "vwap"


class FuturesContractType(str, Enum):
    PERPETUAL = "perpetual"
    DELIVERY = "delivery"
    QUARTERLY = "quarterly"
    BI_QUARTERLY = "bi_quarterly"
    MONTHLY = "monthly"
    WEEKLY = "weekly"


class FuturesMarginMode(str, Enum):
    ISOLATED = "isolated"
    CROSS = "cross"
    PORTFOLIO = "portfolio"


@dataclass
class FuturesPosition:
    id: str
    symbol: str
    contract_type: FuturesContractType
    position_type: FuturesPositionType
    entry_price: float
    current_price: float
    size: float
    leverage: float
    margin: float
    liquidation_price: float
    unrealized_pnl: float
    realized_pnl: float
    funding_rate: float
    funding_accumulated: float
    mark_price: float
    index_price: float
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class FuturesOrder:
    id: str
    symbol: str
    order_type: FuturesOrderType
    side: str
    price: float
    quantity: float
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    trigger_price: Optional[float] = None
    status: str = "pending"
    filled_quantity: float = 0.0
    avg_price: float = 0.0
    reduce_only: bool = False
    post_only: bool = False
    time_in_force: str = "GTC"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    executed_at: Optional[float] = None


@dataclass
class FuturesSignal:
    id: str
    symbol: str
    position_type: FuturesPositionType
    entry_price: float
    target_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    risk_reward_ratio: float
    timestamp: float
    expiry: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FuturesMetrics:
    total_position_value: float
    total_margin: float
    total_unrealized_pnl: float
    total_realized_pnl: float
    total_funding: float
    average_leverage: float
    liquidation_distance: float
    exposure: float
    delta: float
    gamma: float
    vega: float
    theta: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class FundingRate:
    symbol: str
    rate: float
    next_funding_time: float
    predicted_rate: float
    interval: int = 480
    timestamp: float = field(default_factory=time.time)


@dataclass
class PositionRisk:
    symbol: str
    liquidation_price: float
    margin_ratio: float
    maintenance_margin: float
    initial_margin: float
    risk_score: float
    level: str = "medium"
    timestamp: float = field(default_factory=time.time)


class FuturesTradingBot:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._positions: Dict[str, FuturesPosition] = {}
        self._orders: Dict[str, FuturesOrder] = {}
        self._signals: Dict[str, FuturesSignal] = {}
        self._metrics: Dict[str, FuturesMetrics] = {}
        self._funding_rates: Dict[str, FundingRate] = {}
        self._risks: Dict[str, PositionRisk] = {}
        self._strategies: Dict[str, Callable] = {}
        self._risk_managers: List[Callable] = []
        self._observers: List[Callable] = []
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._funding_task: Optional[asyncio.Task] = None
        self._executor_task: Optional[asyncio.Task] = None
        
        self._initialize_strategies()
        self._initialize_risk_managers()

    def _initialize_strategies(self) -> None:
        self.register_strategy("trend_following", self._strategy_trend_following)
        self.register_strategy("mean_reversion", self._strategy_mean_reversion)
        self.register_strategy("breakout", self._strategy_breakout)
        self.register_strategy("arbitrage", self._strategy_arbitrage)
        self.register_strategy("basis_trading", self._strategy_basis_trading)
        self.register_strategy("funding_rate", self._strategy_funding_rate)
        self.register_strategy("volatility", self._strategy_volatility)
        self.register_strategy("scalping", self._strategy_scalping)

    def _initialize_risk_managers(self) -> None:
        self.register_risk_manager(self._risk_check_liquidation)
        self.register_risk_manager(self._risk_check_margin)
        self.register_risk_manager(self._risk_check_drawdown)
        self.register_risk_manager(self._risk_check_funding)
        self.register_risk_manager(self._risk_check_exposure)

    def register_strategy(self, name: str, strategy: Callable) -> None:
        self._strategies[name] = strategy

    def register_risk_manager(self, risk_manager: Callable) -> None:
        self._risk_managers.append(risk_manager)

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def generate_signal(
        self,
        symbol: str,
        strategy_name: str,
        market_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[FuturesSignal]:
        async with self._lock:
            if strategy_name not in self._strategies:
                return None
            
            strategy = self._strategies[strategy_name]
            signal_data = await strategy(symbol, market_data)
            
            if not signal_data:
                return None
            
            signal = FuturesSignal(
                id=hashlib.md5(f"{symbol}_{time.time()}".encode()).hexdigest(),
                symbol=symbol,
                position_type=signal_data.get("position_type", FuturesPositionType.LONG),
                entry_price=signal_data["entry_price"],
                target_price=signal_data["target_price"],
                stop_loss=signal_data["stop_loss"],
                take_profit=signal_data["take_profit"],
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

    async def _validate_signal(self, signal: FuturesSignal) -> bool:
        if signal.entry_price <= 0:
            return False
        
        if signal.target_price <= 0:
            return False
        
        if signal.stop_loss >= signal.entry_price and signal.position_type == FuturesPositionType.LONG:
            return False
        
        if signal.stop_loss <= signal.entry_price and signal.position_type == FuturesPositionType.SHORT:
            return False
        
        if signal.take_profit <= signal.entry_price and signal.position_type == FuturesPositionType.LONG:
            return False
        
        if signal.take_profit >= signal.entry_price and signal.position_type == FuturesPositionType.SHORT:
            return False
        
        if signal.confidence < 0.3:
            return False
        
        for risk_manager in self._risk_managers:
            if not await risk_manager(signal):
                return False
        
        return True

    async def execute_order(self, signal_id: str, order_type: FuturesOrderType = FuturesOrderType.MARKET) -> Optional[FuturesOrder]:
        async with self._lock:
            if signal_id not in self._signals:
                return None
            
            signal = self._signals[signal_id]
            
            order = FuturesOrder(
                id=hashlib.md5(f"{signal_id}_{time.time()}".encode()).hexdigest(),
                symbol=signal.symbol,
                order_type=order_type,
                side="buy" if signal.position_type in [FuturesPositionType.LONG, FuturesPositionType.HEDGED] else "sell",
                price=signal.entry_price,
                quantity=1.0,
                stop_price=signal.stop_loss,
                take_profit_price=signal.take_profit,
                metadata=signal.metadata
            )
            
            self._orders[order.id] = order
            await self._notify_observers("order_created", order)
            
            return order

    async def update_position(
        self,
        position_id: str,
        current_price: float,
        mark_price: float,
        index_price: float,
        funding_rate: float
    ) -> Optional[FuturesPosition]:
        async with self._lock:
            if position_id not in self._positions:
                return None
            
            position = self._positions[position_id]
            position.current_price = current_price
            position.mark_price = mark_price
            position.index_price = index_price
            position.funding_rate = funding_rate
            position.updated_at = time.time()
            
            position.unrealized_pnl = (position.current_price - position.entry_price) * position.size
            if position.position_type == FuturesPositionType.SHORT:
                position.unrealized_pnl = (position.entry_price - position.current_price) * position.size
            
            position.funding_accumulated += funding_rate * position.size
            
            position.liquidation_price = await self._calculate_liquidation_price(position)
            
            position.margin = await self._calculate_margin(position)
            
            await self._check_risk_limits(position)
            
            await self._notify_observers("position_updated", position)
            return position

    async def _calculate_liquidation_price(self, position: FuturesPosition) -> float:
        if position.position_type == FuturesPositionType.LONG:
            return position.entry_price * (1 - 1 / position.leverage)
        else:
            return position.entry_price * (1 + 1 / position.leverage)

    async def _calculate_margin(self, position: FuturesPosition) -> float:
        return position.entry_price * position.size / position.leverage

    async def _check_risk_limits(self, position: FuturesPosition) -> None:
        margin_ratio = position.margin / (position.entry_price * position.size) if position.entry_price > 0 else 0
        
        if margin_ratio < 0.2:
            risk_level = "extreme"
        elif margin_ratio < 0.4:
            risk_level = "high"
        elif margin_ratio < 0.6:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        risk = PositionRisk(
            symbol=position.symbol,
            liquidation_price=position.liquidation_price,
            margin_ratio=margin_ratio,
            maintenance_margin=position.margin * 0.5,
            initial_margin=position.margin,
            risk_score=1 - margin_ratio,
            level=risk_level,
            timestamp=time.time()
        )
        
        self._risks[position.id] = risk

    async def _risk_check_liquidation(self, signal: FuturesSignal) -> bool:
        return True

    async def _risk_check_margin(self, signal: FuturesSignal) -> bool:
        return True

    async def _risk_check_drawdown(self, signal: FuturesSignal) -> bool:
        return True

    async def _risk_check_funding(self, signal: FuturesSignal) -> bool:
        return True

    async def _risk_check_exposure(self, signal: FuturesSignal) -> bool:
        return True

    async def _strategy_trend_following(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        trend = market_data.get("trend", 0)
        direction = 1 if trend > 0 else -1
        
        return {
            "position_type": FuturesPositionType.LONG if direction > 0 else FuturesPositionType.SHORT,
            "entry_price": market_data.get("close", 0),
            "target_price": market_data.get("close", 0) * (1 + direction * 0.03),
            "stop_loss": market_data.get("close", 0) * (1 - direction * 0.015),
            "take_profit": market_data.get("close", 0) * (1 + direction * 0.05),
            "confidence": 0.5 + abs(trend) * 0.4,
            "risk_reward_ratio": 3.0
        }

    async def _strategy_mean_reversion(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        mean = market_data.get("mean", 0)
        price = market_data.get("close", 0)
        deviation = (price - mean) / mean if mean > 0 else 0
        
        return {
            "position_type": FuturesPositionType.SHORT if deviation > 0 else FuturesPositionType.LONG,
            "entry_price": price,
            "target_price": mean,
            "stop_loss": price * (1 + abs(deviation) * 0.5),
            "take_profit": price * (1 - abs(deviation) * 0.5),
            "confidence": min(0.8, abs(deviation) * 2),
            "risk_reward_ratio": 1.5
        }

    async def _strategy_breakout(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        high = market_data.get("high_24h", 0)
        low = market_data.get("low_24h", 0)
        price = market_data.get("close", 0)
        
        if price > high * 0.99:
            return {
                "position_type": FuturesPositionType.LONG,
                "entry_price": price,
                "target_price": price * 1.02,
                "stop_loss": price * 0.99,
                "take_profit": price * 1.04,
                "confidence": 0.6,
                "risk_reward_ratio": 4.0
            }
        elif price < low * 1.01:
            return {
                "position_type": FuturesPositionType.SHORT,
                "entry_price": price,
                "target_price": price * 0.98,
                "stop_loss": price * 1.01,
                "take_profit": price * 0.96,
                "confidence": 0.6,
                "risk_reward_ratio": 4.0
            }
        
        return None

    async def _strategy_arbitrage(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        futures_price = market_data.get("futures_price", 0)
        spot_price = market_data.get("spot_price", 0)
        basis = futures_price - spot_price
        
        if basis > 0:
            return {
                "position_type": FuturesPositionType.SHORT,
                "entry_price": futures_price,
                "target_price": futures_price - basis * 0.5,
                "stop_loss": futures_price + basis * 0.1,
                "take_profit": futures_price - basis * 0.8,
                "confidence": 0.8,
                "risk_reward_ratio": 8.0
            }
        elif basis < 0:
            return {
                "position_type": FuturesPositionType.LONG,
                "entry_price": futures_price,
                "target_price": futures_price - basis * 0.5,
                "stop_loss": futures_price + basis * 0.1,
                "take_profit": futures_price - basis * 0.8,
                "confidence": 0.8,
                "risk_reward_ratio": 8.0
            }
        
        return None

    async def _strategy_basis_trading(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        basis = market_data.get("basis", 0)
        historical_basis = market_data.get("historical_basis", 0)
        
        if basis > historical_basis * 1.5:
            return {
                "position_type": FuturesPositionType.SHORT,
                "entry_price": market_data.get("futures_price", 0),
                "target_price": market_data.get("futures_price", 0) - basis * 0.5,
                "stop_loss": market_data.get("futures_price", 0) + basis * 0.1,
                "take_profit": market_data.get("futures_price", 0) - basis * 0.8,
                "confidence": 0.7,
                "risk_reward_ratio": 8.0
            }
        elif basis < historical_basis * 0.5:
            return {
                "position_type": FuturesPositionType.LONG,
                "entry_price": market_data.get("futures_price", 0),
                "target_price": market_data.get("futures_price", 0) - basis * 0.5,
                "stop_loss": market_data.get("futures_price", 0) + basis * 0.1,
                "take_profit": market_data.get("futures_price", 0) - basis * 0.8,
                "confidence": 0.7,
                "risk_reward_ratio": 8.0
            }
        
        return None

    async def _strategy_funding_rate(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        funding_rate = market_data.get("funding_rate", 0)
        threshold = market_data.get("funding_threshold", 0.01)
        
        if funding_rate > threshold:
            return {
                "position_type": FuturesPositionType.SHORT,
                "entry_price": market_data.get("close", 0),
                "target_price": market_data.get("close", 0) * 0.99,
                "stop_loss": market_data.get("close", 0) * 1.01,
                "take_profit": market_data.get("close", 0) * 0.98,
                "confidence": 0.6,
                "risk_reward_ratio": 2.0
            }
        elif funding_rate < -threshold:
            return {
                "position_type": FuturesPositionType.LONG,
                "entry_price": market_data.get("close", 0),
                "target_price": market_data.get("close", 0) * 1.01,
                "stop_loss": market_data.get("close", 0) * 0.99,
                "take_profit": market_data.get("close", 0) * 1.02,
                "confidence": 0.6,
                "risk_reward_ratio": 2.0
            }
        
        return None

    async def _strategy_volatility(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        iv = market_data.get("implied_volatility", 0)
        rv = market_data.get("realized_volatility", 0)
        
        if iv > rv * 1.3:
            return {
                "position_type": FuturesPositionType.SHORT,
                "entry_price": market_data.get("close", 0),
                "target_price": market_data.get("close", 0) * 0.99,
                "stop_loss": market_data.get("close", 0) * 1.01,
                "take_profit": market_data.get("close", 0) * 0.98,
                "confidence": 0.6,
                "risk_reward_ratio": 2.0
            }
        elif rv > iv * 1.3:
            return {
                "position_type": FuturesPositionType.LONG,
                "entry_price": market_data.get("close", 0),
                "target_price": market_data.get("close", 0) * 1.01,
                "stop_loss": market_data.get("close", 0) * 0.99,
                "take_profit": market_data.get("close", 0) * 1.02,
                "confidence": 0.6,
                "risk_reward_ratio": 2.0
            }
        
        return None

    async def _strategy_scalping(self, symbol: str, market_data: Dict[str, Any]) -> Dict:
        return {
            "position_type": FuturesPositionType.LONG,
            "entry_price": market_data.get("bid", 0),
            "target_price": market_data.get("bid", 0) * 1.005,
            "stop_loss": market_data.get("bid", 0) * 0.995,
            "take_profit": market_data.get("bid", 0) * 1.01,
            "confidence": 0.7,
            "risk_reward_ratio": 1.0
        }

    async def compute_metrics(self) -> FuturesMetrics:
        total_position_value = sum(p.current_price * p.size for p in self._positions.values())
        total_margin = sum(p.margin for p in self._positions.values())
        total_unrealized_pnl = sum(p.unrealized_pnl for p in self._positions.values())
        total_realized_pnl = sum(p.realized_pnl for p in self._positions.values())
        total_funding = sum(p.funding_accumulated for p in self._positions.values())
        avg_leverage = np.mean([p.leverage for p in self._positions.values()]) if self._positions else 0
        
        return FuturesMetrics(
            total_position_value=total_position_value,
            total_margin=total_margin,
            total_unrealized_pnl=total_unrealized_pnl,
            total_realized_pnl=total_realized_pnl,
            total_funding=total_funding,
            average_leverage=avg_leverage,
            liquidation_distance=0,
            exposure=total_position_value,
            delta=0,
            gamma=0,
            vega=0,
            theta=0,
            timestamp=time.time()
        )

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
            "orders": len(self._orders),
            "signals": len(self._signals),
            "metrics": len(self._metrics),
            "funding_rates": len(self._funding_rates),
            "risks": len(self._risks),
            "strategies": len(self._strategies),
            "risk_managers": len(self._risk_managers),
            "running": self._running
        }


__all__ = [
    "FuturesPositionType",
    "FuturesOrderType",
    "FuturesContractType",
    "FuturesMarginMode",
    "FuturesPosition",
    "FuturesOrder",
    "FuturesSignal",
    "FuturesMetrics",
    "FundingRate",
    "PositionRisk",
    "FuturesTradingBot"
]
