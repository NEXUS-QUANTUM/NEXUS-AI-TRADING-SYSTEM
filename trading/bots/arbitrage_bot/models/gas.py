# trading/bots/arbitrage_bot/models/gas.py
# NEXUS AI TRADING SYSTEM - GAS MODELS
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Version: 3.0.0 - FULL PRODUCTION READY
# ====================================================================================
# This module defines the data models for gas costs, gas estimation, gas optimization,
# and gas tracking for blockchain transactions across multiple networks.
# ====================================================================================

"""
NEXUS Arbitrage Bot Gas Models

This module provides comprehensive data models for:
- Gas price estimation and tracking
- Gas cost calculation across multiple networks
- Gas optimization strategies
- Gas price history and analytics
- MEV (Miner Extractable Value) protection
- Gas token management
- Cross-chain gas optimization
- Gas price prediction and forecasting
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from uuid import UUID, uuid4
import json
import math
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

# ====================================================================================
# ENUMS AND CONSTANTS
# ====================================================================================

class GasNetwork(str, Enum):
    """Blockchain networks for gas calculations."""
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"
    AVALANCHE = "avalanche"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    FANTOM = "fantom"
    SOLANA = "solana"
    NEAR = "near"
    COSMOS = "cosmos"
    POLKADOT = "polkadot"
    KUSAMA = "kusama"
    CELO = "celo"
    HARMONY = "harmony"
    MOONBEAM = "moonbeam"
    MOONRIVER = "moonriver"
    GNOSIS = "gnosis"
    ZKSYNC = "zksync"
    STARKNET = "starknet"
    LINEA = "linea"
    BASE = "base"
    SCROLL = "scroll"
    MANTLE = "mantle"
    POLYGON_ZKEVM = "polygon_zkevm"
    METIS = "metis"
    KAVA = "kava"


class GasPriority(str, Enum):
    """Gas priority levels for transaction execution."""
    URGENT = "urgent"        # Maximum speed, high cost
    HIGH = "high"           # Fast confirmation, higher cost
    STANDARD = "standard"   # Normal confirmation, standard cost
    LOW = "low"            # Slow confirmation, lower cost
    ECONOMY = "economy"     # Minimum cost, slow confirmation
    CUSTOM = "custom"       # Custom gas parameters


class GasStrategy(str, Enum):
    """Gas optimization strategies."""
    SPEED = "speed"           # Optimize for speed (highest gas)
    COST = "cost"             # Optimize for cost (lowest gas)
    BALANCED = "balanced"     # Balanced between speed and cost
    DYNAMIC = "dynamic"       # Dynamic based on market conditions
    ADAPTIVE = "adaptive"     # Adaptive to network conditions
    MEV_PROTECTED = "mev_protected"  # MEV protection
    BUNDLE = "bundle"         # Bundle transactions for savings


class GasTokenType(str, Enum):
    """Types of gas tokens."""
    NATIVE = "native"        # Native network token (ETH, BNB, etc.)
    ERC20 = "erc20"          # ERC-20 gas token
    CHI = "chi"              # CHI gas token (1inch)
    GST = "gst"              # GST gas token
    CUSTOM = "custom"        # Custom gas token


class MEVProtectionLevel(str, Enum):
    """MEV protection levels."""
    NONE = "none"            # No protection
    BASIC = "basic"          # Basic protection
    STANDARD = "standard"    # Standard protection
    ADVANCED = "advanced"    # Advanced protection
    MAXIMUM = "maximum"      # Maximum protection


# ====================================================================================
# GAS CONFIGURATION MODELS
# ====================================================================================

@dataclass
class GasConfig:
    """
    Gas configuration for a specific network.
    """
    network: GasNetwork = GasNetwork.ETHEREUM
    chain_id: int = 1
    native_currency: str = "ETH"
    gas_token_address: str = ""
    gas_token_type: GasTokenType = GasTokenType.NATIVE
    
    # Default gas parameters
    default_gas_limit: int = 21000
    default_priority_fee: float = 1.0  # GWEI
    default_max_fee: float = 50.0      # GWEI
    max_gas_price: float = 500.0       # GWEI
    min_gas_price: float = 0.1         # GWEI
    
    # Optimization settings
    priority: GasPriority = GasPriority.STANDARD
    strategy: GasStrategy = GasStrategy.BALANCED
    mev_protection: MEVProtectionLevel = MEVProtectionLevel.STANDARD
    
    # Gas estimation
    estimation_method: str = "eth_gasPrice"  # eth_gasPrice, eth_feeHistory, custom
    fee_history_blocks: int = 10
    fee_history_percentiles: List[int] = field(default_factory=lambda: [25, 50, 75])
    
    # Cache settings
    cache_ttl: int = 60  # seconds
    max_cache_size: int = 100
    
    # MEV protection
    mev_protection_enabled: bool = True
    mev_blocklist: List[str] = field(default_factory=list)
    mev_allowlist: List[str] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "network": self.network.value if self.network else None,
            "chain_id": self.chain_id,
            "native_currency": self.native_currency,
            "gas_token_address": self.gas_token_address,
            "gas_token_type": self.gas_token_type.value if self.gas_token_type else None,
            "default_gas_limit": self.default_gas_limit,
            "default_priority_fee": self.default_priority_fee,
            "default_max_fee": self.default_max_fee,
            "max_gas_price": self.max_gas_price,
            "min_gas_price": self.min_gas_price,
            "priority": self.priority.value if self.priority else None,
            "strategy": self.strategy.value if self.strategy else None,
            "mev_protection": self.mev_protection.value if self.mev_protection else None,
            "estimation_method": self.estimation_method,
            "fee_history_blocks": self.fee_history_blocks,
            "fee_history_percentiles": self.fee_history_percentiles,
            "cache_ttl": self.cache_ttl,
            "max_cache_size": self.max_cache_size,
            "mev_protection_enabled": self.mev_protection_enabled,
            "mev_blocklist": self.mev_blocklist,
            "mev_allowlist": self.mev_allowlist,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GasConfig":
        """Create from dictionary."""
        config = cls(
            network=GasNetwork(data["network"]) if data.get("network") else GasNetwork.ETHEREUM,
            chain_id=data.get("chain_id", 1),
            native_currency=data.get("native_currency", "ETH"),
            gas_token_address=data.get("gas_token_address", ""),
            gas_token_type=GasTokenType(data["gas_token_type"]) if data.get("gas_token_type") else GasTokenType.NATIVE,
            default_gas_limit=data.get("default_gas_limit", 21000),
            default_priority_fee=data.get("default_priority_fee", 1.0),
            default_max_fee=data.get("default_max_fee", 50.0),
            max_gas_price=data.get("max_gas_price", 500.0),
            min_gas_price=data.get("min_gas_price", 0.1),
            priority=GasPriority(data["priority"]) if data.get("priority") else GasPriority.STANDARD,
            strategy=GasStrategy(data["strategy"]) if data.get("strategy") else GasStrategy.BALANCED,
            mev_protection=MEVProtectionLevel(data["mev_protection"]) if data.get("mev_protection") else MEVProtectionLevel.STANDARD,
            estimation_method=data.get("estimation_method", "eth_gasPrice"),
            fee_history_blocks=data.get("fee_history_blocks", 10),
            fee_history_percentiles=data.get("fee_history_percentiles", [25, 50, 75]),
            cache_ttl=data.get("cache_ttl", 60),
            max_cache_size=data.get("max_cache_size", 100),
            mev_protection_enabled=data.get("mev_protection_enabled", True),
            mev_blocklist=data.get("mev_blocklist", []),
            mev_allowlist=data.get("mev_allowlist", []),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("created_at"):
            config.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            config.updated_at = datetime.fromisoformat(data["updated_at"])
            
        return config


# ====================================================================================
# GAS PRICE MODELS
# ====================================================================================

@dataclass
class GasPrice:
    """
    Gas price information for a specific network.
    """
    network: GasNetwork = GasNetwork.ETHEREUM
    base_fee: float = 0.0      # GWEI
    priority_fee: float = 0.0  # GWEI
    max_fee: float = 0.0       # GWEI
    max_priority_fee: float = 0.0  # GWEI
    
    # Fee statistics
    min_fee: float = 0.0
    max_fee_history: float = 0.0
    avg_fee: float = 0.0
    median_fee: float = 0.0
    p25_fee: float = 0.0
    p75_fee: float = 0.0
    
    # Gas price components
    block_number: int = 0
    block_time: int = 0  # seconds
    
    # Market conditions
    network_utilization: float = 0.0  # 0-1
    congestion_level: str = "low"  # low, medium, high, very_high
    
    # Recommendations
    recommended_priority: GasPriority = GasPriority.STANDARD
    recommended_max_fee: float = 0.0
    recommended_priority_fee: float = 0.0
    
    # Timestamps
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=1))
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "network": self.network.value if self.network else None,
            "base_fee": self.base_fee,
            "priority_fee": self.priority_fee,
            "max_fee": self.max_fee,
            "max_priority_fee": self.max_priority_fee,
            "min_fee": self.min_fee,
            "max_fee_history": self.max_fee_history,
            "avg_fee": self.avg_fee,
            "median_fee": self.median_fee,
            "p25_fee": self.p25_fee,
            "p75_fee": self.p75_fee,
            "block_number": self.block_number,
            "block_time": self.block_time,
            "network_utilization": self.network_utilization,
            "congestion_level": self.congestion_level,
            "recommended_priority": self.recommended_priority.value if self.recommended_priority else None,
            "recommended_max_fee": self.recommended_max_fee,
            "recommended_priority_fee": self.recommended_priority_fee,
            "fetched_at": self.fetched_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GasPrice":
        """Create from dictionary."""
        price = cls(
            network=GasNetwork(data["network"]) if data.get("network") else GasNetwork.ETHEREUM,
            base_fee=data.get("base_fee", 0.0),
            priority_fee=data.get("priority_fee", 0.0),
            max_fee=data.get("max_fee", 0.0),
            max_priority_fee=data.get("max_priority_fee", 0.0),
            min_fee=data.get("min_fee", 0.0),
            max_fee_history=data.get("max_fee_history", 0.0),
            avg_fee=data.get("avg_fee", 0.0),
            median_fee=data.get("median_fee", 0.0),
            p25_fee=data.get("p25_fee", 0.0),
            p75_fee=data.get("p75_fee", 0.0),
            block_number=data.get("block_number", 0),
            block_time=data.get("block_time", 0),
            network_utilization=data.get("network_utilization", 0.0),
            congestion_level=data.get("congestion_level", "low"),
            recommended_priority=GasPriority(data["recommended_priority"]) if data.get("recommended_priority") else GasPriority.STANDARD,
            recommended_max_fee=data.get("recommended_max_fee", 0.0),
            recommended_priority_fee=data.get("recommended_priority_fee", 0.0),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("fetched_at"):
            price.fetched_at = datetime.fromisoformat(data["fetched_at"])
        if data.get("expires_at"):
            price.expires_at = datetime.fromisoformat(data["expires_at"])
            
        return price
        
    def is_expired(self) -> bool:
        """Check if gas price is expired."""
        return datetime.utcnow() >= self.expires_at
        
    def get_fee_for_priority(self, priority: GasPriority) -> float:
        """
        Get recommended fee for a specific priority.
        
        Args:
            priority: Gas priority
            
        Returns:
            Fee in GWEI
        """
        multipliers = {
            GasPriority.URGENT: 2.0,
            GasPriority.HIGH: 1.5,
            GasPriority.STANDARD: 1.0,
            GasPriority.LOW: 0.7,
            GasPriority.ECONOMY: 0.5
        }
        multiplier = multipliers.get(priority, 1.0)
        return self.median_fee * multiplier
        
    def get_transaction_cost(self, gas_limit: int, priority: Optional[GasPriority] = None) -> float:
        """
        Calculate estimated transaction cost.
        
        Args:
            gas_limit: Gas limit for transaction
            priority: Gas priority (defaults to recommended)
            
        Returns:
            Cost in native currency
        """
        if priority is None:
            priority = self.recommended_priority
            
        fee = self.get_fee_for_priority(priority)
        return (fee * gas_limit) / 1e9  # Convert to native


@dataclass
class GasPriceHistory:
    """
    Historical gas price data.
    """
    network: GasNetwork = GasNetwork.ETHEREUM
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    interval: str = "1h"  # 1m, 5m, 15m, 1h, 4h, 1d
    
    # Price data
    prices: List[Dict[str, Any]] = field(default_factory=list)
    
    # Statistics
    min_price: float = 0.0
    max_price: float = 0.0
    avg_price: float = 0.0
    median_price: float = 0.0
    
    # Trends
    trend: str = "stable"  # increasing, decreasing, stable
    trend_strength: float = 0.0  # -1 to 1
    
    # Volatility
    volatility: float = 0.0
    std_dev: float = 0.0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "network": self.network.value if self.network else None,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "interval": self.interval,
            "prices": self.prices,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "avg_price": self.avg_price,
            "median_price": self.median_price,
            "trend": self.trend,
            "trend_strength": self.trend_strength,
            "volatility": self.volatility,
            "std_dev": self.std_dev,
            "metadata": self.metadata
        }


# ====================================================================================
# GAS ESTIMATION MODELS
# ====================================================================================

@dataclass
class GasEstimate:
    """
    Gas estimation for a specific transaction.
    """
    # Core fields
    estimate_id: str = field(default_factory=lambda: str(uuid4()))
    network: GasNetwork = GasNetwork.ETHEREUM
    transaction_type: str = ""  # transfer, swap, bridge, approval, etc.
    
    # Gas parameters
    estimated_gas_limit: int = 0
    estimated_gas_used: int = 0
    estimated_priority_fee: float = 0.0  # GWEI
    estimated_max_fee: float = 0.0  # GWEI
    estimated_total_cost: float = 0.0  # Native currency
    
    # Best/worst case
    min_gas_limit: int = 0
    max_gas_limit: int = 0
    min_cost: float = 0.0
    max_cost: float = 0.0
    
    # Priority-based estimates
    estimates_by_priority: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Confidence
    confidence: float = 0.0  # 0-1
    confidence_level: str = "medium"  # low, medium, high
    
    # Execution time
    estimated_execution_time: int = 0  # seconds
    min_execution_time: int = 0
    max_execution_time: int = 0
    
    # MEV protection
    mev_protection_cost: float = 0.0
    mev_protection_benefit: float = 0.0
    
    # Validation
    is_valid: bool = False
    validation_message: str = ""
    
    # Timestamps
    estimated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default_factory=lambda: datetime.utcnow() + timedelta(minutes=5))
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "estimate_id": self.estimate_id,
            "network": self.network.value if self.network else None,
            "transaction_type": self.transaction_type,
            "estimated_gas_limit": self.estimated_gas_limit,
            "estimated_gas_used": self.estimated_gas_used,
            "estimated_priority_fee": self.estimated_priority_fee,
            "estimated_max_fee": self.estimated_max_fee,
            "estimated_total_cost": self.estimated_total_cost,
            "min_gas_limit": self.min_gas_limit,
            "max_gas_limit": self.max_gas_limit,
            "min_cost": self.min_cost,
            "max_cost": self.max_cost,
            "estimates_by_priority": self.estimates_by_priority,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level,
            "estimated_execution_time": self.estimated_execution_time,
            "min_execution_time": self.min_execution_time,
            "max_execution_time": self.max_execution_time,
            "mev_protection_cost": self.mev_protection_cost,
            "mev_protection_benefit": self.mev_protection_benefit,
            "is_valid": self.is_valid,
            "validation_message": self.validation_message,
            "estimated_at": self.estimated_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GasEstimate":
        """Create from dictionary."""
        estimate = cls(
            estimate_id=data.get("estimate_id", str(uuid4())),
            network=GasNetwork(data["network"]) if data.get("network") else GasNetwork.ETHEREUM,
            transaction_type=data.get("transaction_type", ""),
            estimated_gas_limit=data.get("estimated_gas_limit", 0),
            estimated_gas_used=data.get("estimated_gas_used", 0),
            estimated_priority_fee=data.get("estimated_priority_fee", 0.0),
            estimated_max_fee=data.get("estimated_max_fee", 0.0),
            estimated_total_cost=data.get("estimated_total_cost", 0.0),
            min_gas_limit=data.get("min_gas_limit", 0),
            max_gas_limit=data.get("max_gas_limit", 0),
            min_cost=data.get("min_cost", 0.0),
            max_cost=data.get("max_cost", 0.0),
            estimates_by_priority=data.get("estimates_by_priority", {}),
            confidence=data.get("confidence", 0.0),
            confidence_level=data.get("confidence_level", "medium"),
            estimated_execution_time=data.get("estimated_execution_time", 0),
            min_execution_time=data.get("min_execution_time", 0),
            max_execution_time=data.get("max_execution_time", 0),
            mev_protection_cost=data.get("mev_protection_cost", 0.0),
            mev_protection_benefit=data.get("mev_protection_benefit", 0.0),
            is_valid=data.get("is_valid", False),
            validation_message=data.get("validation_message", ""),
            metadata=data.get("metadata", {})
        )
        
        # Parse timestamps
        if data.get("estimated_at"):
            estimate.estimated_at = datetime.fromisoformat(data["estimated_at"])
        if data.get("expires_at"):
            estimate.expires_at = datetime.fromisoformat(data["expires_at"])
            
        return estimate
        
    def is_expired(self) -> bool:
        """Check if estimate is expired."""
        return datetime.utcnow() >= self.expires_at


@dataclass
class GasOptimization:
    """
    Gas optimization recommendations.
    """
    # Core fields
    optimization_id: str = field(default_factory=lambda: str(uuid4()))
    network: GasNetwork = GasNetwork.ETHEREUM
    transaction_hash: str = ""
    
    # Current vs optimal
    current_gas_used: int = 0
    optimal_gas_used: int = 0
    savings_gas: int = 0
    savings_percentage: float = 0.0
    savings_value: float = 0.0
    
    # Recommendations
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    optimization_opportunities: List[str] = field(default_factory=list)
    
    # Strategies
    used_strategies: List[str] = field(default_factory=list)
    potential_strategies: List[str] = field(default_factory=list)
    
    # Gas token optimization
    gas_token_used: bool = False
    gas_token_savings: float = 0.0
    
    # Bundle optimization
    bundle_used: bool = False
    bundle_savings: float = 0.0
    
    # Timestamps
    optimized_at: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "optimization_id": self.optimization_id,
            "network": self.network.value if self.network else None,
            "transaction_hash": self.transaction_hash,
            "current_gas_used": self.current_gas_used,
            "optimal_gas_used": self.optimal_gas_used,
            "savings_gas": self.savings_gas,
            "savings_percentage": self.savings_percentage,
            "savings_value": self.savings_value,
            "recommendations": self.recommendations,
            "optimization_opportunities": self.optimization_opportunities,
            "used_strategies": self.used_strategies,
            "potential_strategies": self.potential_strategies,
            "gas_token_used": self.gas_token_used,
            "gas_token_savings": self.gas_token_savings,
            "bundle_used": self.bundle_used,
            "bundle_savings": self.bundle_savings,
            "optimized_at": self.optimized_at.isoformat(),
            "metadata": self.metadata
        }


# ====================================================================================
# GAS TOKEN MODELS
# ====================================================================================

@dataclass
class GasToken:
    """
    Gas token information for gas optimization.
    """
    # Core fields
    token_address: str = ""
    token_name: str = ""
    token_symbol: str = ""
    network: GasNetwork = GasNetwork.ETHEREUM
    token_type: GasTokenType = GasTokenType.CHI
    
    # Economics
    current_price: float = 0.0  # USD
    gas_savings_ratio: float = 0.0  # 0-1
    break_even_gas_price: float = 0.0  # GWEI
    optimal_usage_gas: int = 0
    
    # Usage statistics
    total_minted: float = 0.0
    total_burned: float = 0.0
    circulating_supply: float = 0.0
    
    # Market data
    market_cap: float = 0.0
    volume_24h: float = 0.0
    price_change_24h: float = 0.0
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "token_address": self.token_address,
            "token_name": self.token_name,
            "token_symbol": self.token_symbol,
            "network": self.network.value if self.network else None,
            "token_type": self.token_type.value if self.token_type else None,
            "current_price": self.current_price,
            "gas_savings_ratio": self.gas_savings_ratio,
            "break_even_gas_price": self.break_even_gas_price,
            "optimal_usage_gas": self.optimal_usage_gas,
            "total_minted": self.total_minted,
            "total_burned": self.total_burned,
            "circulating_supply": self.circulating_supply,
            "market_cap": self.market_cap,
            "volume_24h": self.volume_24h,
            "price_change_24h": self.price_change_24h,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }


# ====================================================================================
# MEV MODELS
# ====================================================================================

@dataclass
class MEVProtection:
    """
    MEV protection configuration and status.
    """
    # Core fields
    protection_id: str = field(default_factory=lambda: str(uuid4()))
    network: GasNetwork = GasNetwork.ETHEREUM
    enabled: bool = True
    level: MEVProtectionLevel = MEVProtectionLevel.STANDARD
    
    # Protection methods
    methods: List[str] = field(default_factory=list)
    active_methods: List[str] = field(default_factory=list)
    
    # Blocklist/Allowlist
    blocklist: List[str] = field(default_factory=list)
    allowlist: List[str] = field(default_factory=list)
    
    # Protection metrics
    protected_transactions: int = 0
    protected_value: float = 0.0
    estimated_saved_value: float = 0.0
    protection_failure_count: int = 0
    
    # MEV detection
    mev_detected: int = 0
    mev_blocked: int = 0
    mev_mitigated: int = 0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_mev_detection: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "protection_id": self.protection_id,
            "network": self.network.value if self.network else None,
            "enabled": self.enabled,
            "level": self.level.value if self.level else None,
            "methods": self.methods,
            "active_methods": self.active_methods,
            "blocklist": self.blocklist,
            "allowlist": self.allowlist,
            "protected_transactions": self.protected_transactions,
            "protected_value": self.protected_value,
            "estimated_saved_value": self.estimated_saved_value,
            "protection_failure_count": self.protection_failure_count,
            "mev_detected": self.mev_detected,
            "mev_blocked": self.mev_blocked,
            "mev_mitigated": self.mev_mitigated,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_mev_detection": self.last_mev_detection.isoformat() if self.last_mev_detection else None,
            "metadata": self.metadata
        }


# ====================================================================================
# HELPER FUNCTIONS
# ====================================================================================

def calculate_optimal_gas_price(
    gas_price: GasPrice,
    urgency: float = 1.0,  # 0-1
    max_cost: Optional[float] = None
) -> float:
    """
    Calculate optimal gas price based on current market conditions.
    
    Args:
        gas_price: Current gas price data
        urgency: Urgency level (0-1)
        max_cost: Maximum acceptable cost in native currency
        
    Returns:
        Optimal gas price in GWEI
    """
    # Base price from median
    base_price = gas_price.median_fee
    
    # Adjust for urgency
    urgency_multiplier = 1.0 + (urgency * 0.5)  # 1.0 to 1.5
    
    # Adjust for congestion
    congestion_multiplier = 1.0 + (gas_price.network_utilization * 0.3)
    
    # Calculate final price
    optimal_price = base_price * urgency_multiplier * congestion_multiplier
    
    # Clamp to min/max
    if max_cost is not None:
        max_gas_price = (max_cost * 1e9) / gas_price.recommended_priority_fee
        optimal_price = min(optimal_price, max_gas_price)
        
    return optimal_price


def calculate_gas_savings(
    current_gas: int,
    optimized_gas: int,
    gas_price: float
) -> Dict[str, float]:
    """
    Calculate gas savings from optimization.
    
    Args:
        current_gas: Current gas usage
        optimized_gas: Optimized gas usage
        gas_price: Gas price in GWEI
        
    Returns:
        Savings metrics
    """
    savings_gas = current_gas - optimized_gas
    savings_value = (savings_gas * gas_price) / 1e9
    savings_percentage = (savings_gas / current_gas) * 100 if current_gas > 0 else 0
    
    return {
        "savings_gas": savings_gas,
        "savings_value": savings_value,
        "savings_percentage": savings_percentage,
        "optimized_gas": optimized_gas,
        "current_gas": current_gas
    }


def estimate_mev_risk(
    transaction_type: str,
    value: float,
    gas_price: float,
    network: GasNetwork = GasNetwork.ETHEREUM
) -> Dict[str, Any]:
    """
    Estimate MEV risk for a transaction.
    
    Args:
        transaction_type: Type of transaction
        value: Transaction value in native currency
        gas_price: Gas price in GWEI
        network: Blockchain network
        
    Returns:
        MEV risk assessment
    """
    # MEV risk factors
    risk_factors = {
        "swap": 0.7,
        "arbitrage": 0.9,
        "liquidate": 0.8,
        "transfer": 0.1,
        "approval": 0.1,
        "bridge": 0.5,
        "mint": 0.3,
        "burn": 0.3
    }
    
    base_risk = risk_factors.get(transaction_type, 0.5)
    
    # Value multiplier
    if value > 1000:
        value_multiplier = 1.5
    elif value > 100:
        value_multiplier = 1.2
    elif value > 10:
        value_multiplier = 1.0
    else:
        value_multiplier = 0.5
        
    # Gas price multiplier
    if gas_price > 100:
        gas_multiplier = 0.8  # Higher gas means less MEV opportunity
    elif gas_price > 50:
        gas_multiplier = 1.0
    else:
        gas_multiplier = 1.2
        
    risk_score = base_risk * value_multiplier * gas_multiplier
    risk_score = min(max(risk_score, 0.0), 1.0)
    
    risk_level = "low"
    if risk_score > 0.7:
        risk_level = "high"
    elif risk_score > 0.4:
        risk_level = "medium"
        
    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_factors": {
            "base_risk": base_risk,
            "value_multiplier": value_multiplier,
            "gas_multiplier": gas_multiplier
        },
        "recommendations": [
            "Use private mempool" if risk_score > 0.5 else None,
            "Increase gas price" if risk_score > 0.6 else None,
            "Bundle with flashbots" if risk_score > 0.7 else None
        ]
    }


# ====================================================================================
# EXPORTS
# ====================================================================================

__all__ = [
    # Enums
    'GasNetwork',
    'GasPriority',
    'GasStrategy',
    'GasTokenType',
    'MEVProtectionLevel',
    
    # Core Models
    'GasConfig',
    'GasPrice',
    'GasPriceHistory',
    'GasEstimate',
    'GasOptimization',
    'GasToken',
    'MEVProtection',
    
    # Helper Functions
    'calculate_optimal_gas_price',
    'calculate_gas_savings',
    'estimate_mev_risk',
]
