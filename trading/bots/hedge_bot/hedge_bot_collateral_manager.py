# trading/bots/hedge_bot/hedge_bot_collateral_manager.py
# NEXUS AI TRADING SYSTEM - Hedge Bot Collateral Manager Module
# Version: 2.0.0
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

"""
NEXUS Hedge Bot Collateral Manager Module

This module provides comprehensive collateral management capabilities
for the NEXUS Hedge Bot system. It handles collateral allocation,
optimization, monitoring, and risk management.

The module covers:
- Collateral Allocation
- Collateral Optimization
- Collateral Monitoring
- Margin Management
- Haircut Management
- Collateral Valuation
- Collateral Movement
- Collateral Risk Assessment
- Collateral Reporting
"""

import os
import sys
import json
import logging
import math
import numpy as np
from typing import Dict, Any, Optional, List, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from decimal import Decimal, getcontext

logger = logging.getLogger(__name__)


# ============================================================
# COLLATERAL ENUMS
# ============================================================

class CollateralType(Enum):
    """Collateral types"""
    CASH = "cash"
    STABLE_COIN = "stable_coin"
    CRYPTO = "crypto"
    EQUITY = "equity"
    BOND = "bond"
    COMMODITY = "commodity"
    MIXED = "mixed"


class CollateralStatus(Enum):
    """Collateral status"""
    ACTIVE = "active"
    LOCKED = "locked"
    IN_USE = "in_use"
    AVAILABLE = "available"
    PENDING = "pending"
    RELEASED = "released"


class MarginLevel(Enum):
    """Margin levels"""
    SAFE = "safe"
    CAUTION = "caution"
    WARNING = "warning"
    CRITICAL = "critical"
    LIQUIDATION = "liquidation"


@dataclass
class CollateralAsset:
    """Collateral asset"""
    id: str
    symbol: str
    type: CollateralType
    quantity: float
    value: float
    haircut: float
    effective_value: float
    status: CollateralStatus
    locked_until: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "type": self.type.value,
            "quantity": self.quantity,
            "value": self.value,
            "haircut": self.haircut,
            "effective_value": self.effective_value,
            "status": self.status.value,
            "locked_until": self.locked_until.isoformat() if self.locked_until else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class CollateralPool:
    """Collateral pool"""
    id: str
    name: str
    assets: List[CollateralAsset]
    total_value: float
    total_effective_value: float
    used_value: float
    available_value: float
    utilization_rate: float
    margin_level: MarginLevel
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "assets": [a.to_dict() for a in self.assets],
            "total_value": self.total_value,
            "total_effective_value": self.total_effective_value,
            "used_value": self.used_value,
            "available_value": self.available_value,
            "utilization_rate": self.utilization_rate,
            "margin_level": self.margin_level.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class MarginMetrics:
    """Margin metrics"""
    initial_margin: float
    maintenance_margin: float
    variation_margin: float
    margin_balance: float
    margin_utilization: float
    margin_level: MarginLevel
    liquidation_price: Optional[float] = None
    collateral_required: float = 0.0
    excess_collateral: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "initial_margin": self.initial_margin,
            "maintenance_margin": self.maintenance_margin,
            "variation_margin": self.variation_margin,
            "margin_balance": self.margin_balance,
            "margin_utilization": self.margin_utilization,
            "margin_level": self.margin_level.value,
            "liquidation_price": self.liquidation_price,
            "collateral_required": self.collateral_required,
            "excess_collateral": self.excess_collateral,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================
# COLLATERAL MANAGER
# ============================================================

class CollateralManager:
    """
    Comprehensive collateral manager for the hedge bot
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the collateral manager
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.default_haircut = self.config.get("default_haircut", 0.10)
        self.min_collateral_ratio = self.config.get("min_collateral_ratio", 1.2)
        self.liquidation_threshold = self.config.get("liquidation_threshold", 1.05)
        self.base_currency = self.config.get("base_currency", "USD")
        
        # State
        self.collateral_pools: Dict[str, CollateralPool] = {}
        self.collateral_assets: Dict[str, CollateralAsset] = {}
        self.margin_metrics: Dict[str, MarginMetrics] = {}
        
        logger.info("Collateral manager initialized")
    
    # ============================================================
    # COLLATERAL ASSET MANAGEMENT
    # ============================================================
    
    def add_collateral_asset(
        self,
        symbol: str,
        quantity: float,
        price: float,
        asset_type: CollateralType = CollateralType.CRYPTO,
        haircut: Optional[float] = None,
        pool_id: Optional[str] = None
    ) -> CollateralAsset:
        """
        Add a collateral asset
        
        Args:
            symbol: Asset symbol
            quantity: Asset quantity
            price: Asset price
            asset_type: Asset type
            haircut: Haircut percentage
            pool_id: Pool ID
            
        Returns:
            CollateralAsset
        """
        if haircut is None:
            haircut = self.default_haircut
        
        value = quantity * price
        effective_value = value * (1 - haircut)
        
        asset = CollateralAsset(
            id=f"col_{int(time.time())}_{len(self.collateral_assets)}",
            symbol=symbol,
            type=asset_type,
            quantity=quantity,
            value=value,
            haircut=haircut,
            effective_value=effective_value,
            status=CollateralStatus.AVAILABLE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        self.collateral_assets[asset.id] = asset
        
        # Add to pool
        if pool_id:
            self._add_to_pool(asset, pool_id)
        else:
            # Create or add to default pool
            default_pool = self._get_or_create_default_pool()
            self._add_to_pool(asset, default_pool.id)
        
        logger.info(f"Added collateral asset: {symbol} x {quantity} (haircut: {haircut:.1%})")
        return asset
    
    def remove_collateral_asset(self, asset_id: str) -> bool:
        """
        Remove a collateral asset
        
        Args:
            asset_id: Asset ID
            
        Returns:
            True if removed
        """
        asset = self.collateral_assets.get(asset_id)
        if not asset:
            return False
        
        # Remove from pool
        for pool in self.collateral_pools.values():
            if asset_id in [a.id for a in pool.assets]:
                pool.assets = [a for a in pool.assets if a.id != asset_id]
                self._update_pool_metrics(pool)
                break
        
        del self.collateral_assets[asset_id]
        logger.info(f"Removed collateral asset: {asset_id}")
        return True
    
    def update_collateral_value(
        self,
        asset_id: str,
        price: float
    ) -> Optional[CollateralAsset]:
        """
        Update collateral asset value
        
        Args:
            asset_id: Asset ID
            price: Current price
            
        Returns:
            Updated asset or None
        """
        asset = self.collateral_assets.get(asset_id)
        if not asset:
            return None
        
        # Update value
        asset.value = asset.quantity * price
        asset.effective_value = asset.value * (1 - asset.haircut)
        asset.updated_at = datetime.now()
        
        # Update pool
        for pool in self.collateral_pools.values():
            if asset_id in [a.id for a in pool.assets]:
                self._update_pool_metrics(pool)
                break
        
        return asset
    
    def lock_collateral(
        self,
        asset_id: str,
        duration_seconds: Optional[int] = None
    ) -> bool:
        """
        Lock collateral asset
        
        Args:
            asset_id: Asset ID
            duration_seconds: Lock duration
            
        Returns:
            True if locked
        """
        asset = self.collateral_assets.get(asset_id)
        if not asset:
            return False
        
        if asset.status != CollateralStatus.AVAILABLE:
            return False
        
        asset.status = CollateralStatus.LOCKED
        if duration_seconds:
            asset.locked_until = datetime.now() + timedelta(seconds=duration_seconds)
        asset.updated_at = datetime.now()
        
        return True
    
    def release_collateral(self, asset_id: str) -> bool:
        """
        Release collateral asset
        
        Args:
            asset_id: Asset ID
            
        Returns:
            True if released
        """
        asset = self.collateral_assets.get(asset_id)
        if not asset:
            return False
        
        asset.status = CollateralStatus.AVAILABLE
        asset.locked_until = None
        asset.updated_at = datetime.now()
        
        return True
    
    # ============================================================
    # COLLATERAL POOL MANAGEMENT
    # ============================================================
    
    def _get_or_create_default_pool(self) -> CollateralPool:
        """Get or create default collateral pool"""
        default_pools = [p for p in self.collateral_pools.values() if p.name == "Default Pool"]
        if default_pools:
            return default_pools[0]
        
        pool = self.create_collateral_pool("Default Pool")
        return pool
    
    def create_collateral_pool(self, name: str) -> CollateralPool:
        """
        Create a collateral pool
        
        Args:
            name: Pool name
            
        Returns:
            CollateralPool
        """
        pool = CollateralPool(
            id=f"pool_{int(time.time())}_{len(self.collateral_pools)}",
            name=name,
            assets=[],
            total_value=0.0,
            total_effective_value=0.0,
            used_value=0.0,
            available_value=0.0,
            utilization_rate=0.0,
            margin_level=MarginLevel.SAFE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        
        self.collateral_pools[pool.id] = pool
        logger.info(f"Created collateral pool: {name}")
        return pool
    
    def _add_to_pool(self, asset: CollateralAsset, pool_id: str) -> None:
        """Add asset to pool"""
        pool = self.collateral_pools.get(pool_id)
        if not pool:
            raise ValueError(f"Pool not found: {pool_id}")
        
        pool.assets.append(asset)
        self._update_pool_metrics(pool)
    
    def _update_pool_metrics(self, pool: CollateralPool) -> None:
        """Update pool metrics"""
        total_value = sum(a.value for a in pool.assets)
        total_effective = sum(a.effective_value for a in pool.assets)
        
        pool.total_value = total_value
        pool.total_effective_value = total_effective
        pool.available_value = total_effective - pool.used_value
        pool.utilization_rate = pool.used_value / total_effective if total_effective > 0 else 0
        pool.updated_at = datetime.now()
        
        # Update margin level
        if pool.utilization_rate < 0.5:
            pool.margin_level = MarginLevel.SAFE
        elif pool.utilization_rate < 0.7:
            pool.margin_level = MarginLevel.CAUTION
        elif pool.utilization_rate < 0.85:
            pool.margin_level = MarginLevel.WARNING
        elif pool.utilization_rate < 0.95:
            pool.margin_level = MarginLevel.CRITICAL
        else:
            pool.margin_level = MarginLevel.LIQUIDATION
    
    def get_collateral_pool(self, pool_id: str) -> Optional[CollateralPool]:
        """
        Get a collateral pool
        
        Args:
            pool_id: Pool ID
            
        Returns:
            CollateralPool or None
        """
        return self.collateral_pools.get(pool_id)
    
    def get_collateral_pools(self) -> List[CollateralPool]:
        """
        Get all collateral pools
        
        Returns:
            List of pools
        """
        return list(self.collateral_pools.values())
    
    # ============================================================
    # MARGIN MANAGEMENT
    # ============================================================
    
    def calculate_margin_metrics(
        self,
        position_value: float,
        collateral_effective: float,
        leverage: float = 1.0,
        position_side: str = "long"
    ) -> MarginMetrics:
        """
        Calculate margin metrics
        
        Args:
            position_value: Position value
            collateral_effective: Effective collateral value
            leverage: Leverage ratio
            position_side: Position side
            
        Returns:
            MarginMetrics
        """
        # Calculate margins
        initial_margin = position_value / leverage
        maintenance_margin = initial_margin * 0.5  # Simplified
        
        # Variation margin
        variation_margin = 0.0
        
        # Margin balance
        margin_balance = collateral_effective - initial_margin
        
        # Margin utilization
        margin_utilization = initial_margin / collateral_effective if collateral_effective > 0 else float('inf')
        
        # Determine margin level
        if margin_utilization < 0.5:
            margin_level = MarginLevel.SAFE
        elif margin_utilization < 0.7:
            margin_level = MarginLevel.CAUTION
        elif margin_utilization < 0.85:
            margin_level = MarginLevel.WARNING
        elif margin_utilization < 0.95:
            margin_level = MarginLevel.CRITICAL
        else:
            margin_level = MarginLevel.LIQUIDATION
        
        # Collateral required
        collateral_required = initial_margin
        
        # Excess collateral
        excess_collateral = collateral_effective - initial_margin
        
        # Liquidation price
        liquidation_price = None
        if position_side == "long":
            liquidation_price = position_value * (1 - 1 / (leverage * 0.8))
        else:
            liquidation_price = position_value * (1 + 1 / (leverage * 0.8))
        
        metrics = MarginMetrics(
            initial_margin=initial_margin,
            maintenance_margin=maintenance_margin,
            variation_margin=variation_margin,
            margin_balance=margin_balance,
            margin_utilization=margin_utilization,
            margin_level=margin_level,
            liquidation_price=liquidation_price,
            collateral_required=collateral_required,
            excess_collateral=excess_collateral,
        )
        
        # Store metrics
        self.margin_metrics[f"margin_{int(time.time())}"] = metrics
        return metrics
    
    def check_margin_call(
        self,
        margin_metrics: MarginMetrics,
        threshold: float = 0.85
    ) -> Dict[str, Any]:
        """
        Check if margin call is needed
        
        Args:
            margin_metrics: Margin metrics
            threshold: Margin call threshold
            
        Returns:
            Check result
        """
        is_margin_call = margin_metrics.margin_utilization > threshold
        
        result = {
            "is_margin_call": is_margin_call,
            "margin_utilization": margin_metrics.margin_utilization,
            "threshold": threshold,
            "level": margin_metrics.margin_level.value,
            "excess_collateral": margin_metrics.excess_collateral,
            "collateral_required": margin_metrics.collateral_required,
            "action": "none",
        }
        
        if is_margin_call:
            if margin_metrics.margin_level == MarginLevel.CRITICAL:
                result["action"] = "add_collateral"
            elif margin_metrics.margin_level == MarginLevel.LIQUIDATION:
                result["action"] = "liquidate_position"
            else:
                result["action"] = "monitor"
        
        return result
    
    # ============================================================
    # COLLATERAL OPTIMIZATION
    # ============================================================
    
    def optimize_collateral(
        self,
        pool_id: str,
        target_utilization: float = 0.6
    ) -> Dict[str, Any]:
        """
        Optimize collateral allocation
        
        Args:
            pool_id: Pool ID
            target_utilization: Target utilization rate
            
        Returns:
            Optimization results
        """
        pool = self.collateral_pools.get(pool_id)
        if not pool:
            return {"error": "Pool not found"}
        
        # Current state
        current_utilization = pool.utilization_rate
        current_effective = pool.total_effective_value
        
        # Calculate target
        if current_utilization > target_utilization:
            # Need to add collateral
            needed_value = current_effective * (current_utilization - target_utilization) / target_utilization
            recommendation = "add_collateral"
            amount = needed_value
        else:
            # Can release collateral
            excess = current_effective * (1 - current_utilization / target_utilization)
            recommendation = "release_collateral"
            amount = min(excess, current_effective * 0.1)  # Don't release more than 10%
        
        return {
            "pool_id": pool_id,
            "current_utilization": current_utilization,
            "target_utilization": target_utilization,
            "recommendation": recommendation,
            "amount": amount,
            "current_effective": current_effective,
            "timestamp": datetime.now().isoformat(),
        }
    
    # ============================================================
    # COLLATERAL VALUATION
    # ============================================================
    
    def get_collateral_summary(self) -> Dict[str, Any]:
        """
        Get collateral summary
        
        Returns:
            Summary data
        """
        total_value = sum(a.value for a in self.collateral_assets.values())
        total_effective = sum(a.effective_value for a in self.collateral_assets.values())
        total_used = sum(p.used_value for p in self.collateral_pools.values())
        total_available = total_effective - total_used
        
        # Calculate overall margin level
        total_utilization = total_used / total_effective if total_effective > 0 else 0
        if total_utilization < 0.5:
            overall_margin = MarginLevel.SAFE
        elif total_utilization < 0.7:
            overall_margin = MarginLevel.CAUTION
        elif total_utilization < 0.85:
            overall_margin = MarginLevel.WARNING
        elif total_utilization < 0.95:
            overall_margin = MarginLevel.CRITICAL
        else:
            overall_margin = MarginLevel.LIQUIDATION
        
        return {
            "total_value": total_value,
            "total_effective_value": total_effective,
            "total_used": total_used,
            "total_available": total_available,
            "overall_utilization": total_utilization,
            "overall_margin_level": overall_margin.value,
            "asset_count": len(self.collateral_assets),
            "pool_count": len(self.collateral_pools),
            "timestamp": datetime.now().isoformat(),
        }
    
    # ============================================================
    # REPORTING
    # ============================================================
    
    def generate_collateral_report(self) -> Dict[str, Any]:
        """
        Generate collateral report
        
        Returns:
            Report data
        """
        return {
            "summary": self.get_collateral_summary(),
            "pools": [p.to_dict() for p in self.collateral_pools.values()],
            "assets": [a.to_dict() for a in self.collateral_assets.values()],
            "margin_metrics": [m.to_dict() for m in self.margin_metrics.values()],
            "generated_at": datetime.now().isoformat(),
        }
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get collateral statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_assets": len(self.collateral_assets),
            "total_pools": len(self.collateral_pools),
            "total_margin_metrics": len(self.margin_metrics),
            "total_value": sum(a.value for a in self.collateral_assets.values()),
            "total_effective": sum(a.effective_value for a in self.collateral_assets.values()),
        }


# ============================================================
# MODULE EXPORTS
# ============================================================

__all__ = [
    # Enums
    "CollateralType",
    "CollateralStatus",
    "MarginLevel",
    
    # Dataclasses
    "CollateralAsset",
    "CollateralPool",
    "MarginMetrics",
    
    # Classes
    "CollateralManager",
]

# ============================================================
# END OF MODULE
# ============================================================
