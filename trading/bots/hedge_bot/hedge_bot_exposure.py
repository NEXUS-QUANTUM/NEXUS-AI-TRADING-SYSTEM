# trading/bots/hedge_bot/hedge_bot_exposure.py

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


class ExposureType(str, Enum):
    DELTA = "delta"
    GAMMA = "gamma"
    VEGA = "vega"
    THETA = "theta"
    RHO = "rho"
    BETA = "beta"
    VOLATILITY = "volatility"
    CORRELATION = "correlation"
    CONCENTRATION = "concentration"
    SECTOR = "sector"
    GEOGRAPHIC = "geographic"
    CURRENCY = "currency"
    INTEREST_RATE = "interest_rate"
    LIQUIDITY = "liquidity"
    COUNTERPARTY = "counterparty"
    OPERATIONAL = "operational"
    REGULATORY = "regulatory"
    SYSTEMIC = "systemic"


class ExposureLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"
    CRITICAL = "critical"


class ExposureDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    NEGATIVE = "negative"


@dataclass
class ExposurePosition:
    id: str
    symbol: str
    exposure_type: ExposureType
    direction: ExposureDirection
    value: float
    weight: float
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    rho: float = 0.0
    beta: float = 0.0
    correlation: float = 0.0
    volatility: float = 0.0
    market_value: float = 0.0
    notional_value: float = 0.0
    risk_weight: float = 1.0
    level: ExposureLevel = ExposureLevel.MEDIUM
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class ExposureMetrics:
    id: str
    total_exposure: float
    net_exposure: float
    gross_exposure: float
    long_exposure: float
    short_exposure: float
    weighted_delta: float
    weighted_gamma: float
    weighted_vega: float
    weighted_theta: float
    weighted_rho: float
    concentration_ratio: float
    diversification_score: float
    risk_score: float
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExposureLimit:
    id: str
    name: str
    exposure_type: ExposureType
    max_value: float
    min_value: float
    current_value: float
    utilization: float
    breached: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class ExposureAlert:
    id: str
    exposure_id: str
    limit_id: str
    type: str
    message: str
    severity: str
    current_value: float
    threshold: float
    timestamp: float
    acknowledged: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExposureManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._positions: Dict[str, ExposurePosition] = {}
        self._metrics: Dict[str, ExposureMetrics] = {}
        self._limits: Dict[str, ExposureLimit] = {}
        self._alerts: Dict[str, ExposureAlert] = {}
        self._observers: List[Callable] = []
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        self._initialize_default_limits()

    def _initialize_default_limits(self) -> None:
        default_limits = [
            ExposureLimit(
                id="delta_limit",
                name="Delta Exposure Limit",
                exposure_type=ExposureType.DELTA,
                max_value=1000000,
                min_value=-1000000,
                current_value=0
            ),
            ExposureLimit(
                id="gamma_limit",
                name="Gamma Exposure Limit",
                exposure_type=ExposureType.GAMMA,
                max_value=100000,
                min_value=-100000,
                current_value=0
            ),
            ExposureLimit(
                id="concentration_limit",
                name="Concentration Limit",
                exposure_type=ExposureType.CONCENTRATION,
                max_value=0.25,
                min_value=0,
                current_value=0
            ),
            ExposureLimit(
                id="volatility_limit",
                name="Volatility Exposure Limit",
                exposure_type=ExposureType.VOLATILITY,
                max_value=0.5,
                min_value=0,
                current_value=0
            )
        ]
        
        for limit in default_limits:
            self._limits[limit.id] = limit

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def add_position(
        self,
        symbol: str,
        exposure_type: ExposureType,
        direction: ExposureDirection,
        value: float,
        delta: float = 0.0,
        gamma: float = 0.0,
        vega: float = 0.0,
        theta: float = 0.0,
        rho: float = 0.0,
        beta: float = 0.0,
        correlation: float = 0.0,
        volatility: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExposurePosition:
        async with self._lock:
            position_id = hashlib.md5(f"{symbol}_{exposure_type.value}_{time.time()}".encode()).hexdigest()
            
            position = ExposurePosition(
                id=position_id,
                symbol=symbol,
                exposure_type=exposure_type,
                direction=direction,
                value=value,
                weight=1.0,
                delta=delta,
                gamma=gamma,
                vega=vega,
                theta=theta,
                rho=rho,
                beta=beta,
                correlation=correlation,
                volatility=volatility,
                market_value=value,
                notional_value=value,
                level=ExposureLevel.MEDIUM,
                metadata=metadata or {}
            )
            
            self._positions[position_id] = position
            await self._update_risk_level(position)
            await self._notify_observers("position_added", position)
            return position

    async def update_position(
        self,
        position_id: str,
        value: Optional[float] = None,
        delta: Optional[float] = None,
        gamma: Optional[float] = None,
        vega: Optional[float] = None,
        theta: Optional[float] = None,
        rho: Optional[float] = None,
        beta: Optional[float] = None,
        correlation: Optional[float] = None,
        volatility: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ExposurePosition]:
        async with self._lock:
            if position_id not in self._positions:
                return None
            
            position = self._positions[position_id]
            
            if value is not None:
                position.value = value
                position.market_value = value
                position.notional_value = value
            
            if delta is not None:
                position.delta = delta
            
            if gamma is not None:
                position.gamma = gamma
            
            if vega is not None:
                position.vega = vega
            
            if theta is not None:
                position.theta = theta
            
            if rho is not None:
                position.rho = rho
            
            if beta is not None:
                position.beta = beta
            
            if correlation is not None:
                position.correlation = correlation
            
            if volatility is not None:
                position.volatility = volatility
            
            if metadata:
                position.metadata.update(metadata)
            
            position.updated_at = time.time()
            await self._update_risk_level(position)
            await self._notify_observers("position_updated", position)
            return position

    async def remove_position(self, position_id: str) -> bool:
        async with self._lock:
            if position_id in self._positions:
                del self._positions[position_id]
                await self._notify_observers("position_removed", position_id)
                return True
            return False

    async def _update_risk_level(self, position: ExposurePosition) -> None:
        risk_score = abs(position.value) * position.risk_weight
        
        if risk_score > 1000000:
            position.level = ExposureLevel.CRITICAL
        elif risk_score > 500000:
            position.level = ExposureLevel.EXTREME
        elif risk_score > 100000:
            position.level = ExposureLevel.HIGH
        elif risk_score > 10000:
            position.level = ExposureLevel.MEDIUM
        elif risk_score > 1000:
            position.level = ExposureLevel.LOW
        else:
            position.level = ExposureLevel.NONE

    async def compute_metrics(self) -> ExposureMetrics:
        async with self._lock:
            total_exposure = sum(p.value for p in self._positions.values())
            long_exposure = sum(p.value for p in self._positions.values() if p.direction in [ExposureDirection.LONG, ExposureDirection.POSITIVE])
            short_exposure = sum(p.value for p in self._positions.values() if p.direction in [ExposureDirection.SHORT, ExposureDirection.NEGATIVE])
            net_exposure = long_exposure + short_exposure
            gross_exposure = abs(long_exposure) + abs(short_exposure)
            
            weighted_delta = sum(p.delta * p.value for p in self._positions.values()) / max(1, len(self._positions))
            weighted_gamma = sum(p.gamma * p.value for p in self._positions.values()) / max(1, len(self._positions))
            weighted_vega = sum(p.vega * p.value for p in self._positions.values()) / max(1, len(self._positions))
            weighted_theta = sum(p.theta * p.value for p in self._positions.values()) / max(1, len(self._positions))
            weighted_rho = sum(p.rho * p.value for p in self._positions.values()) / max(1, len(self._positions))
            
            total_abs = sum(abs(p.value) for p in self._positions.values())
            concentration_ratio = 0
            if total_abs > 0:
                max_value = max(abs(p.value) for p in self._positions.values()) if self._positions else 0
                concentration_ratio = max_value / total_abs
            
            diversity_count = len(set(p.symbol for p in self._positions.values()))
            diversification_score = min(1.0, diversity_count / 10)
            
            risk_score = concentration_ratio * (1 - diversification_score)
            
            metrics = ExposureMetrics(
                id=hashlib.md5(str(time.time()).encode()).hexdigest(),
                total_exposure=total_exposure,
                net_exposure=net_exposure,
                gross_exposure=gross_exposure,
                long_exposure=long_exposure,
                short_exposure=short_exposure,
                weighted_delta=weighted_delta,
                weighted_gamma=weighted_gamma,
                weighted_vega=weighted_vega,
                weighted_theta=weighted_theta,
                weighted_rho=weighted_rho,
                concentration_ratio=concentration_ratio,
                diversification_score=diversification_score,
                risk_score=risk_score,
                metadata={}
            )
            
            self._metrics[metrics.id] = metrics
            
            await self._check_limits(metrics)
            await self._notify_observers("metrics_computed", metrics)
            
            return metrics

    async def _check_limits(self, metrics: ExposureMetrics) -> None:
        for limit in self._limits.values():
            current_value = await self._get_limit_value(limit, metrics)
            limit.current_value = current_value
            limit.utilization = abs(current_value) / max(1, abs(limit.max_value)) if limit.max_value != 0 else 0
            
            if abs(current_value) > abs(limit.max_value):
                limit.breached = True
                await self._create_alert(limit, current_value)
            else:
                limit.breached = False
            
            limit.updated_at = time.time()

    async def _get_limit_value(self, limit: ExposureLimit, metrics: ExposureMetrics) -> float:
        if limit.exposure_type == ExposureType.DELTA:
            return metrics.weighted_delta
        elif limit.exposure_type == ExposureType.GAMMA:
            return metrics.weighted_gamma
        elif limit.exposure_type == ExposureType.VEGA:
            return metrics.weighted_vega
        elif limit.exposure_type == ExposureType.THETA:
            return metrics.weighted_theta
        elif limit.exposure_type == ExposureType.RHO:
            return metrics.weighted_rho
        elif limit.exposure_type == ExposureType.CONCENTRATION:
            return metrics.concentration_ratio
        elif limit.exposure_type == ExposureType.VOLATILITY:
            return 0
        else:
            return 0

    async def _create_alert(self, limit: ExposureLimit, current_value: float) -> None:
        alert = ExposureAlert(
            id=hashlib.md5(f"{limit.id}_{time.time()}".encode()).hexdigest(),
            exposure_id="",
            limit_id=limit.id,
            type="limit_breach",
            message=f"Exposure limit breached: {limit.name}",
            severity="high" if limit.utilization > 1.5 else "medium",
            current_value=current_value,
            threshold=limit.max_value,
            timestamp=time.time()
        )
        
        self._alerts[alert.id] = alert
        await self._notify_observers("alert_created", alert)

    async def add_limit(
        self,
        name: str,
        exposure_type: ExposureType,
        max_value: float,
        min_value: float = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ExposureLimit:
        async with self._lock:
            limit_id = hashlib.md5(f"{name}_{time.time()}".encode()).hexdigest()
            
            limit = ExposureLimit(
                id=limit_id,
                name=name,
                exposure_type=exposure_type,
                max_value=max_value,
                min_value=min_value,
                current_value=0,
                utilization=0,
                metadata=metadata or {}
            )
            
            self._limits[limit_id] = limit
            await self._notify_observers("limit_added", limit)
            return limit

    async def update_limit(
        self,
        limit_id: str,
        max_value: Optional[float] = None,
        min_value: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ExposureLimit]:
        async with self._lock:
            if limit_id not in self._limits:
                return None
            
            limit = self._limits[limit_id]
            
            if max_value is not None:
                limit.max_value = max_value
            
            if min_value is not None:
                limit.min_value = min_value
            
            if metadata:
                limit.metadata.update(metadata)
            
            limit.updated_at = time.time()
            await self._notify_observers("limit_updated", limit)
            return limit

    async def remove_limit(self, limit_id: str) -> bool:
        async with self._lock:
            if limit_id in self._limits:
                del self._limits[limit_id]
                await self._notify_observers("limit_removed", limit_id)
                return True
            return False

    async def get_position(self, position_id: str) -> Optional[ExposurePosition]:
        return self._positions.get(position_id)

    async def get_positions(self) -> List[ExposurePosition]:
        return list(self._positions.values())

    async def get_metrics(self) -> List[ExposureMetrics]:
        return list(self._metrics.values())

    async def get_latest_metrics(self) -> Optional[ExposureMetrics]:
        if self._metrics:
            return max(self._metrics.values(), key=lambda m: m.timestamp)
        return None

    async def get_limit(self, limit_id: str) -> Optional[ExposureLimit]:
        return self._limits.get(limit_id)

    async def get_limits(self) -> List[ExposureLimit]:
        return list(self._limits.values())

    async def get_alerts(
        self,
        acknowledged: bool = False,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[ExposureAlert]:
        alerts = list(self._alerts.values())
        alerts = [a for a in alerts if a.acknowledged == acknowledged]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        alerts.sort(key=lambda a: a.timestamp, reverse=True)
        return alerts[:limit]

    async def acknowledge_alert(self, alert_id: str) -> bool:
        if alert_id in self._alerts:
            self._alerts[alert_id].acknowledged = True
            await self._notify_observers("alert_acknowledged", alert_id)
            return True
        return False

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
            "metrics": len(self._metrics),
            "limits": len(self._limits),
            "alerts": len(self._alerts),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "ExposureType",
    "ExposureLevel",
    "ExposureDirection",
    "ExposurePosition",
    "ExposureMetrics",
    "ExposureLimit",
    "ExposureAlert",
    "ExposureManager"
]
