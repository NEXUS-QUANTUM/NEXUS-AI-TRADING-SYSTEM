# trading/bots/hedge_bot/hedge_bot_diversification.py

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


class DiversificationType(str, Enum):
    ASSET = "asset"
    SECTOR = "sector"
    STRATEGY = "strategy"
    TIMEFRAME = "timeframe"
    GEOGRAPHIC = "geographic"
    CURRENCY = "currency"
    FACTOR = "factor"
    RISK = "risk"
    STYLE = "style"
    MANAGER = "manager"


class DiversificationStatus(str, Enum):
    OPTIMAL = "optimal"
    ADEQUATE = "adequate"
    INSUFFICIENT = "insufficient"
    EXCESSIVE = "excessive"
    IMBALANCED = "imbalanced"
    CONCENTRATED = "concentrated"


@dataclass
class DiversificationAsset:
    id: str
    symbol: str
    asset_type: str
    sector: str
    weight: float
    value: float
    returns: float
    volatility: float
    correlation: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiversificationMetrics:
    id: str
    total_assets: int
    total_value: float
    effective_assets: int
    herfindahl_index: float
    concentration_ratio: float
    diversification_ratio: float
    correlation_avg: float
    status: DiversificationStatus
    allocations: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class DiversificationConstraint:
    id: str
    type: DiversificationType
    min_weight: float = 0.0
    max_weight: float = 1.0
    min_assets: int = 0
    max_assets: int = 100
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DiversificationRecommendation:
    id: str
    type: DiversificationType
    action: str
    description: str
    target_weight: float
    current_weight: float
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class DiversificationManager:
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._lock = asyncio.Lock()
        self._assets: Dict[str, DiversificationAsset] = {}
        self._metrics: Dict[str, DiversificationMetrics] = {}
        self._constraints: Dict[str, DiversificationConstraint] = {}
        self._recommendations: Dict[str, DiversificationRecommendation] = {}
        self._observers: List[Callable] = []
        self._running = False
        
        self._initialize_default_constraints()

    def _initialize_default_constraints(self) -> None:
        default_constraints = [
            DiversificationConstraint(
                id="asset_max",
                type=DiversificationType.ASSET,
                max_weight=0.25,
                metadata={"description": "Maximum single asset weight"}
            ),
            DiversificationConstraint(
                id="sector_max",
                type=DiversificationType.SECTOR,
                max_weight=0.40,
                metadata={"description": "Maximum sector weight"}
            ),
            DiversificationConstraint(
                id="min_assets",
                type=DiversificationType.ASSET,
                min_assets=5,
                metadata={"description": "Minimum number of assets"}
            ),
            DiversificationConstraint(
                id="strategy_max",
                type=DiversificationType.STRATEGY,
                max_weight=0.50,
                metadata={"description": "Maximum strategy weight"}
            )
        ]
        
        for constraint in default_constraints:
            self._constraints[constraint.id] = constraint

    def register_observer(self, observer: Callable) -> None:
        self._observers.append(observer)

    async def add_asset(
        self,
        symbol: str,
        asset_type: str,
        sector: str,
        weight: float,
        value: float,
        returns: float,
        volatility: float,
        correlation: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DiversificationAsset:
        async with self._lock:
            asset_id = hashlib.md5(f"{symbol}_{time.time()}".encode()).hexdigest()
            
            asset = DiversificationAsset(
                id=asset_id,
                symbol=symbol,
                asset_type=asset_type,
                sector=sector,
                weight=weight,
                value=value,
                returns=returns,
                volatility=volatility,
                correlation=correlation,
                metadata=metadata or {}
            )
            
            self._assets[asset_id] = asset
            await self._notify_observers("asset_added", asset)
            return asset

    async def update_asset(
        self,
        asset_id: str,
        weight: Optional[float] = None,
        value: Optional[float] = None,
        returns: Optional[float] = None,
        volatility: Optional[float] = None,
        correlation: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DiversificationAsset]:
        async with self._lock:
            if asset_id not in self._assets:
                return None
            
            asset = self._assets[asset_id]
            
            if weight is not None:
                asset.weight = weight
            
            if value is not None:
                asset.value = value
            
            if returns is not None:
                asset.returns = returns
            
            if volatility is not None:
                asset.volatility = volatility
            
            if correlation is not None:
                asset.correlation = correlation
            
            if metadata:
                asset.metadata.update(metadata)
            
            await self._notify_observers("asset_updated", asset)
            return asset

    async def remove_asset(self, asset_id: str) -> bool:
        async with self._lock:
            if asset_id in self._assets:
                del self._assets[asset_id]
                await self._notify_observers("asset_removed", asset_id)
                return True
            return False

    async def compute_metrics(self) -> DiversificationMetrics:
        async with self._lock:
            assets = list(self._assets.values())
            
            if not assets:
                return DiversificationMetrics(
                    id=hashlib.md5(str(time.time()).encode()).hexdigest(),
                    total_assets=0,
                    total_value=0,
                    effective_assets=0,
                    herfindahl_index=0,
                    concentration_ratio=0,
                    diversification_ratio=0,
                    correlation_avg=0,
                    status=DiversificationStatus.INSUFFICIENT,
                    allocations={}
                )
            
            total_value = sum(a.value for a in assets)
            weights = np.array([a.weight for a in assets])
            
            herfindahl = np.sum(weights ** 2)
            effective_assets = 1 / herfindahl if herfindahl > 0 else 0
            
            sorted_weights = sorted(weights, reverse=True)
            concentration_ratio = sum(sorted_weights[:3]) if len(sorted_weights) >= 3 else sum(sorted_weights)
            
            diversification_ratio = 1 / herfindahl / len(assets) if len(assets) > 0 else 0
            
            correlations = np.array([a.correlation for a in assets])
            correlation_avg = np.mean(correlations) if len(correlations) > 0 else 0
            
            if len(assets) >= 5 and herfindahl < 0.2:
                status = DiversificationStatus.OPTIMAL
            elif len(assets) >= 3 and herfindahl < 0.3:
                status = DiversificationStatus.ADEQUATE
            elif len(assets) >= 2 and herfindahl < 0.5:
                status = DiversificationStatus.INSUFFICIENT
            elif herfindahl >= 0.5:
                status = DiversificationStatus.CONCENTRATED
            else:
                status = DiversificationStatus.IMBALANCED
            
            allocations = {a.symbol: a.weight for a in assets}
            
            metrics = DiversificationMetrics(
                id=hashlib.md5(str(time.time()).encode()).hexdigest(),
                total_assets=len(assets),
                total_value=total_value,
                effective_assets=effective_assets,
                herfindahl_index=herfindahl,
                concentration_ratio=concentration_ratio,
                diversification_ratio=diversification_ratio,
                correlation_avg=correlation_avg,
                status=status,
                allocations=allocations
            )
            
            self._metrics[metrics.id] = metrics
            
            await self._check_constraints(metrics)
            await self._generate_recommendations(metrics)
            
            await self._notify_observers("metrics_computed", metrics)
            return metrics

    async def _check_constraints(self, metrics: DiversificationMetrics) -> None:
        for constraint in self._constraints.values():
            if constraint.type == DiversificationType.ASSET:
                for asset in self._assets.values():
                    if asset.weight > constraint.max_weight:
                        await self._notify_observers(
                            "constraint_violated",
                            constraint,
                            asset,
                            f"Asset {asset.symbol} weight {asset.weight:.2%} exceeds {constraint.max_weight:.2%}"
                        )
            
            elif constraint.type == DiversificationType.SECTOR:
                sector_weights = defaultdict(float)
                for asset in self._assets.values():
                    sector_weights[asset.sector] += asset.weight
                
                for sector, weight in sector_weights.items():
                    if weight > constraint.max_weight:
                        await self._notify_observers(
                            "constraint_violated",
                            constraint,
                            sector,
                            f"Sector {sector} weight {weight:.2%} exceeds {constraint.max_weight:.2%}"
                        )

    async def _generate_recommendations(self, metrics: DiversificationMetrics) -> None:
        self._recommendations.clear()
        
        if metrics.total_assets < 5:
            rec = DiversificationRecommendation(
                id=hashlib.md5(f"add_assets_{time.time()}".encode()).hexdigest(),
                type=DiversificationType.ASSET,
                action="add_assets",
                description=f"Add {5 - metrics.total_assets} more assets for better diversification",
                target_weight=0.0,
                current_weight=float(metrics.total_assets) / 5,
                priority=10
            )
            self._recommendations[rec.id] = rec
        
        if metrics.herfindahl_index > 0.3:
            rec = DiversificationRecommendation(
                id=hashlib.md5(f"reduce_concentration_{time.time()}".encode()).hexdigest(),
                type=DiversificationType.ASSET,
                action="reduce_concentration",
                description=f"Reduce asset concentration (HHI: {metrics.herfindahl_index:.3f})",
                target_weight=0.0,
                current_weight=metrics.herfindahl_index,
                priority=5
            )
            self._recommendations[rec.id] = rec
        
        if metrics.correlation_avg > 0.7:
            rec = DiversificationRecommendation(
                id=hashlib.md5(f"add_uncorrelated_{time.time()}".encode()).hexdigest(),
                type=DiversificationType.ASSET,
                action="add_uncorrelated",
                description=f"Add assets with lower correlation (avg: {metrics.correlation_avg:.2f})",
                target_weight=0.0,
                current_weight=metrics.correlation_avg,
                priority=3
            )
            self._recommendations[rec.id] = rec

    async def add_constraint(
        self,
        type: DiversificationType,
        min_weight: float = 0.0,
        max_weight: float = 1.0,
        min_assets: int = 0,
        max_assets: int = 100,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DiversificationConstraint:
        async with self._lock:
            constraint_id = hashlib.md5(f"{type.value}_{time.time()}".encode()).hexdigest()
            
            constraint = DiversificationConstraint(
                id=constraint_id,
                type=type,
                min_weight=min_weight,
                max_weight=max_weight,
                min_assets=min_assets,
                max_assets=max_assets,
                metadata=metadata or {}
            )
            
            self._constraints[constraint_id] = constraint
            await self._notify_observers("constraint_added", constraint)
            return constraint

    async def update_constraint(
        self,
        constraint_id: str,
        min_weight: Optional[float] = None,
        max_weight: Optional[float] = None,
        min_assets: Optional[int] = None,
        max_assets: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[DiversificationConstraint]:
        async with self._lock:
            if constraint_id not in self._constraints:
                return None
            
            constraint = self._constraints[constraint_id]
            
            if min_weight is not None:
                constraint.min_weight = min_weight
            
            if max_weight is not None:
                constraint.max_weight = max_weight
            
            if min_assets is not None:
                constraint.min_assets = min_assets
            
            if max_assets is not None:
                constraint.max_assets = max_assets
            
            if metadata:
                constraint.metadata.update(metadata)
            
            await self._notify_observers("constraint_updated", constraint)
            return constraint

    async def remove_constraint(self, constraint_id: str) -> bool:
        async with self._lock:
            if constraint_id in self._constraints:
                del self._constraints[constraint_id]
                await self._notify_observers("constraint_removed", constraint_id)
                return True
            return False

    async def get_asset(self, asset_id: str) -> Optional[DiversificationAsset]:
        return self._assets.get(asset_id)

    async def get_assets(self) -> List[DiversificationAsset]:
        return list(self._assets.values())

    async def get_metrics(self) -> List[DiversificationMetrics]:
        return list(self._metrics.values())

    async def get_latest_metrics(self) -> Optional[DiversificationMetrics]:
        if self._metrics:
            return max(self._metrics.values(), key=lambda m: m.timestamp)
        return None

    async def get_constraint(self, constraint_id: str) -> Optional[DiversificationConstraint]:
        return self._constraints.get(constraint_id)

    async def get_constraints(self) -> List[DiversificationConstraint]:
        return list(self._constraints.values())

    async def get_recommendations(self) -> List[DiversificationRecommendation]:
        return list(self._recommendations.values())

    async def apply_recommendation(self, recommendation_id: str) -> bool:
        if recommendation_id not in self._recommendations:
            return False
        
        rec = self._recommendations[recommendation_id]
        await self._notify_observers("recommendation_applied", rec)
        return True

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
            "assets": len(self._assets),
            "metrics": len(self._metrics),
            "constraints": len(self._constraints),
            "recommendations": len(self._recommendations),
            "observers": len(self._observers),
            "running": self._running
        }


__all__ = [
    "DiversificationType",
    "DiversificationStatus",
    "DiversificationAsset",
    "DiversificationMetrics",
    "DiversificationConstraint",
    "DiversificationRecommendation",
    "DiversificationManager"
]
