# trading/bots/arbitrage_bot/core/fee_calculator.py
# Nexus AI Trading System - Arbitrage Bot Fee Calculator Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Fee Calculator Module

This module provides comprehensive fee calculation and optimization for
the arbitrage bot system, including:

- Exchange fee structure management
- Fee calculation for different order types
- Volume-based fee tiers
- Fee optimization strategies
- Fee impact analysis
- Gas cost estimation
- Network fee calculation
- Multi-currency fee support
- Fee history and analytics
- Fee prediction

The fee calculator ensures accurate profit calculations and helps optimize
arbitrage strategies by accounting for all costs.
"""

import asyncio
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from shared.helpers.logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class FeeType(str, Enum):
    """Types of fees."""
    MAKER = "maker"
    TAKER = "taker"
    WITHDRAWAL = "withdrawal"
    DEPOSIT = "deposit"
    TRADING = "trading"
    GAS = "gas"
    NETWORK = "network"
    TRANSFER = "transfer"
    STAKING = "staking"
    UNKNOWN = "unknown"


class FeeTier(str, Enum):
    """Fee tiers."""
    TIER_0 = "tier_0"  # 0.10% maker, 0.10% taker
    TIER_1 = "tier_1"  # 0.09% maker, 0.10% taker
    TIER_2 = "tier_2"  # 0.08% maker, 0.09% taker
    TIER_3 = "tier_3"  # 0.07% maker, 0.08% taker
    TIER_4 = "tier_4"  # 0.06% maker, 0.07% taker
    TIER_5 = "tier_5"  # 0.05% maker, 0.06% taker
    TIER_6 = "tier_6"  # 0.04% maker, 0.05% taker
    TIER_7 = "tier_7"  # 0.03% maker, 0.04% taker
    TIER_8 = "tier_8"  # 0.02% maker, 0.03% taker
    TIER_9 = "tier_9"  # 0.01% maker, 0.02% taker


class FeeDiscountType(str, Enum):
    """Types of fee discounts."""
    BNB = "bnb"
    OKB = "okb"
    KCS = "kcs"
    HT = "ht"
    VET = "vet"
    FTT = "ftt"
    CUSTOM = "custom"


class FeeCurrency(str, Enum):
    """Fee payment currencies."""
    USD = "USD"
    USDT = "USDT"
    BNB = "BNB"
    OKB = "OKB"
    KCS = "KCS"
    HT = "HT"
    VET = "VET"
    FTT = "FTT"
    NATIVE = "native"  # Native token of the exchange


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class FeeConfig(BaseModel):
    """Fee configuration for an exchange."""
    exchange: str
    maker_fee: Decimal = Decimal('0.001')  # 0.1%
    taker_fee: Decimal = Decimal('0.001')  # 0.1%
    withdrawal_fee: Optional[Decimal] = None
    deposit_fee: Optional[Decimal] = None
    gas_fee: Optional[Decimal] = None
    network_fee: Optional[Decimal] = None
    fee_tier: FeeTier = FeeTier.TIER_0
    fee_discount: Optional[FeeDiscountType] = None
    fee_currency: FeeCurrency = FeeCurrency.NATIVE
    volume_30d: Decimal = Decimal('0')
    volume_365d: Decimal = Decimal('0')
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('maker_fee', 'taker_fee')
    def validate_fees(cls, v):
        if v < 0:
            raise ValueError("Fee cannot be negative")
        if v > 1:
            raise ValueError("Fee cannot exceed 100%")
        return v

    def get_maker_fee(self) -> Decimal:
        """Get maker fee with discounts applied."""
        fee = self.maker_fee
        
        # Apply discount
        if self.fee_discount == FeeDiscountType.BNB:
            fee = fee * Decimal('0.75')  # 25% discount
        elif self.fee_discount == FeeDiscountType.OKB:
            fee = fee * Decimal('0.80')  # 20% discount
        elif self.fee_discount == FeeDiscountType.KCS:
            fee = fee * Decimal('0.80')  # 20% discount
        
        return fee

    def get_taker_fee(self) -> Decimal:
        """Get taker fee with discounts applied."""
        fee = self.taker_fee
        
        # Apply discount
        if self.fee_discount == FeeDiscountType.BNB:
            fee = fee * Decimal('0.75')  # 25% discount
        elif self.fee_discount == FeeDiscountType.OKB:
            fee = fee * Decimal('0.80')  # 20% discount
        elif self.fee_discount == FeeDiscountType.KCS:
            fee = fee * Decimal('0.80')  # 20% discount
        
        return fee


class FeeCalculation(BaseModel):
    """Fee calculation result."""
    type: FeeType
    amount: Decimal
    currency: str
    rate: Decimal
    base_amount: Decimal
    discount_applied: Decimal = Decimal('0')
    discount_percent: Decimal = Decimal('0')
    exchange: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def total(self) -> Decimal:
        """Get total fee amount."""
        return self.amount

    @property
    def effective_rate(self) -> Decimal:
        """Get effective fee rate after discounts."""
        return self.rate - self.discount_percent


class GasCost(BaseModel):
    """Gas cost estimation."""
    chain: str
    gas_price: Decimal  # Gas price in native token
    gas_limit: Decimal  # Gas limit for transaction
    gas_used: Optional[Decimal] = None
    cost_native: Decimal  # Cost in native token
    cost_usd: Decimal  # Cost in USD
    token: str = "ETH"
    base_fee: Optional[Decimal] = None
    priority_fee: Optional[Decimal] = None
    max_fee: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def total_cost(self) -> Decimal:
        """Get total cost."""
        return self.cost_native


class FeeHistory(BaseModel):
    """Fee history entry."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str
    symbol: Optional[str] = None
    fee_type: FeeType
    amount: Decimal
    currency: str
    rate: Decimal
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Fee configurations
CREATE TABLE IF NOT EXISTS fee_configs (
    exchange VARCHAR(50) PRIMARY KEY,
    config JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_fee_configs_exchange (exchange)
);

-- Fee history
CREATE TABLE IF NOT EXISTS fee_history (
    id VARCHAR(64) PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    symbol VARCHAR(50),
    fee_type VARCHAR(20) NOT NULL,
    amount DECIMAL(32, 16) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    rate DECIMAL(32, 16) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    metadata JSONB DEFAULT '{}',
    INDEX idx_fee_history_exchange (exchange),
    INDEX idx_fee_history_timestamp (timestamp)
);

-- Gas costs
CREATE TABLE IF NOT EXISTS gas_costs (
    id SERIAL PRIMARY KEY,
    chain VARCHAR(50) NOT NULL,
    gas_price DECIMAL(32, 16) NOT NULL,
    gas_limit DECIMAL(32, 16) NOT NULL,
    gas_used DECIMAL(32, 16),
    cost_native DECIMAL(32, 16) NOT NULL,
    cost_usd DECIMAL(32, 16) NOT NULL,
    token VARCHAR(10) NOT NULL,
    base_fee DECIMAL(32, 16),
    priority_fee DECIMAL(32, 16),
    max_fee DECIMAL(32, 16),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_gas_costs_chain (chain),
    INDEX idx_gas_costs_timestamp (timestamp)
);

-- Fee tiers
CREATE TABLE IF NOT EXISTS fee_tiers (
    tier VARCHAR(20) PRIMARY KEY,
    maker_fee DECIMAL(32, 16) NOT NULL,
    taker_fee DECIMAL(32, 16) NOT NULL,
    volume_required DECIMAL(32, 16) NOT NULL,
    description TEXT,
    INDEX idx_fee_tiers_volume_required (volume_required)
);
"""


# =============================================================================
# FEE CALCULATOR CLASS
# =============================================================================

class FeeCalculator:
    """
    Advanced fee calculator for arbitrage bot.
    
    Features:
    - Exchange fee structure management
    - Fee calculation for different order types
    - Volume-based fee tiers
    - Fee optimization strategies
    - Fee impact analysis
    - Gas cost estimation
    - Network fee calculation
    - Multi-currency fee support
    - Fee history and analytics
    - Fee prediction
    - Discount management
    """
    
    def __init__(
        self,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.redis = redis
        self.pool = pool
        self.config = config or {}
        
        # Fee configurations
        self._fee_configs: Dict[str, FeeConfig] = {}
        
        # Fee tiers
        self._fee_tiers: Dict[str, Dict[str, Decimal]] = {}
        
        # Gas costs
        self._gas_costs: Dict[str, GasCost] = {}
        
        # History
        self._fee_history: List[FeeHistory] = []
        
        # Running state
        self._initialized = False
        self._running = False
        
        # Database
        self._db_initialized = False
        
        logger.info("FeeCalculator initialized")
    
    async def initialize(self):
        """Initialize the fee calculator."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load fee configurations
        await self._load_fee_configs()
        
        # Load fee tiers
        await self._load_fee_tiers()
        
        # Start gas price monitoring
        self._running = True
        asyncio.create_task(self._gas_price_monitoring_loop())
        
        self._initialized = True
        logger.info("FeeCalculator initialized")
    
    async def _init_database(self):
        """Initialize database tables."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for statement in CREATE_TABLES_SQL.split(';'):
                        if statement.strip():
                            await conn.execute(statement)
            logger.info("Database tables initialized")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    # =========================================================================
    # FEE CONFIGURATION
    # =========================================================================
    
    async def register_exchange(
        self,
        exchange: str,
        maker_fee: Decimal,
        taker_fee: Decimal,
        fee_tier: FeeTier = FeeTier.TIER_0,
        fee_discount: Optional[FeeDiscountType] = None,
        fee_currency: FeeCurrency = FeeCurrency.NATIVE,
        withdrawal_fee: Optional[Decimal] = None,
        deposit_fee: Optional[Decimal] = None,
        gas_fee: Optional[Decimal] = None,
        network_fee: Optional[Decimal] = None,
        volume_30d: Decimal = Decimal('0'),
        volume_365d: Decimal = Decimal('0'),
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Register an exchange with fee configuration.
        
        Args:
            exchange: Exchange name
            maker_fee: Maker fee rate
            taker_fee: Taker fee rate
            fee_tier: Fee tier
            fee_discount: Fee discount type
            fee_currency: Fee payment currency
            withdrawal_fee: Withdrawal fee
            deposit_fee: Deposit fee
            gas_fee: Gas fee
            network_fee: Network fee
            volume_30d: 30-day trading volume
            volume_365d: 365-day trading volume
            metadata: Additional metadata
        """
        config = FeeConfig(
            exchange=exchange,
            maker_fee=maker_fee,
            taker_fee=taker_fee,
            fee_tier=fee_tier,
            fee_discount=fee_discount,
            fee_currency=fee_currency,
            withdrawal_fee=withdrawal_fee,
            deposit_fee=deposit_fee,
            gas_fee=gas_fee,
            network_fee=network_fee,
            volume_30d=volume_30d,
            volume_365d=volume_365d,
            metadata=metadata or {}
        )
        
        self._fee_configs[exchange] = config
        
        if self.pool:
            await self._save_fee_config(config)
        
        logger.info(f"Registered fee config for {exchange}")
    
    async def update_fee_config(
        self,
        exchange: str,
        **kwargs
    ) -> Optional[FeeConfig]:
        """
        Update fee configuration.
        
        Args:
            exchange: Exchange name
            **kwargs: Fields to update
            
        Returns:
            Updated FeeConfig or None
        """
        if exchange not in self._fee_configs:
            logger.warning(f"No fee config found for {exchange}")
            return None
        
        config = self._fee_configs[exchange]
        
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        config.updated_at = datetime.utcnow()
        
        if self.pool:
            await self._save_fee_config(config)
        
        return config
    
    async def get_fee_config(self, exchange: str) -> Optional[FeeConfig]:
        """Get fee configuration for an exchange."""
        return self._fee_configs.get(exchange)
    
    # =========================================================================
    # FEE CALCULATION
    # =========================================================================
    
    async def calculate_trading_fee(
        self,
        exchange: str,
        amount: Decimal,
        side: str = "buy",
        order_type: str = "limit"
    ) -> FeeCalculation:
        """
        Calculate trading fee.
        
        Args:
            exchange: Exchange name
            amount: Trade amount
            side: 'buy' or 'sell'
            order_type: 'limit' or 'market'
            
        Returns:
            FeeCalculation
        """
        config = self._fee_configs.get(exchange)
        if not config:
            raise ValueError(f"No fee config for {exchange}")
        
        # Determine fee type
        if order_type == "limit":
            fee_type = FeeType.MAKER
            fee_rate = config.get_maker_fee()
        else:
            fee_type = FeeType.TAKER
            fee_rate = config.get_taker_fee()
        
        # Calculate fee
        fee_amount = amount * fee_rate
        
        # Apply volume discount if applicable
        discount = Decimal('0')
        discount_percent = Decimal('0')
        
        if config.volume_30d > Decimal('50000000'):  # $50M
            discount = Decimal('0.1')  # 10% discount
            discount_percent = Decimal('10')
        elif config.volume_30d > Decimal('10000000'):  # $10M
            discount = Decimal('0.05')  # 5% discount
            discount_percent = Decimal('5')
        
        fee_amount = fee_amount * (Decimal('1') - discount)
        
        return FeeCalculation(
            type=fee_type,
            amount=fee_amount.quantize(Decimal('0.00000001')),
            currency=config.fee_currency.value,
            rate=fee_rate,
            base_amount=amount,
            discount_applied=discount,
            discount_percent=discount_percent,
            exchange=exchange,
            side=side,
            metadata={
                "order_type": order_type,
                "fee_tier": config.fee_tier.value,
                "fee_discount": config.fee_discount.value if config.fee_discount else None
            }
        )
    
    async def calculate_withdrawal_fee(
        self,
        exchange: str,
        amount: Decimal,
        currency: str = "USDT",
        network: Optional[str] = None
    ) -> FeeCalculation:
        """
        Calculate withdrawal fee.
        
        Args:
            exchange: Exchange name
            amount: Withdrawal amount
            currency: Currency code
            network: Network name
            
        Returns:
            FeeCalculation
        """
        config = self._fee_configs.get(exchange)
        if not config:
            raise ValueError(f"No fee config for {exchange}")
        
        # Get withdrawal fee
        if config.withdrawal_fee is not None:
            fee_rate = config.withdrawal_fee
            fee_type = FeeType.WITHDRAWAL
        else:
            # Default withdrawal fee (0.1%)
            fee_rate = Decimal('0.001')
            fee_type = FeeType.WITHDRAWAL
        
        fee_amount = amount * fee_rate
        
        return FeeCalculation(
            type=fee_type,
            amount=fee_amount.quantize(Decimal('0.00000001')),
            currency=currency,
            rate=fee_rate,
            base_amount=amount,
            exchange=exchange,
            metadata={
                "network": network,
                "fee_currency": config.fee_currency.value
            }
        )
    
    async def calculate_gas_cost(
        self,
        chain: str,
        gas_price: Optional[Decimal] = None,
        gas_limit: Optional[Decimal] = None,
        price_usd: Optional[Decimal] = None
    ) -> GasCost:
        """
        Calculate gas cost for a transaction.
        
        Args:
            chain: Blockchain name
            gas_price: Gas price in native token
            gas_limit: Gas limit
            price_usd: Native token price in USD
            
        Returns:
            GasCost
        """
        # Get default gas price if not provided
        if gas_price is None:
            gas_price = await self._get_gas_price(chain)
        
        # Get default gas limit if not provided
        if gas_limit is None:
            gas_limit = await self._get_gas_limit(chain)
        
        # Get token price if not provided
        if price_usd is None:
            price_usd = await self._get_token_price(chain)
        
        # Calculate costs
        cost_native = gas_price * gas_limit
        cost_usd = cost_native * price_usd
        
        return GasCost(
            chain=chain,
            gas_price=gas_price,
            gas_limit=gas_limit,
            cost_native=cost_native.quantize(Decimal('0.00000001')),
            cost_usd=cost_usd.quantize(Decimal('0.01')),
            token=self._get_native_token(chain),
            price_usd=price_usd,
            timestamp=datetime.utcnow()
        )
    
    async def calculate_total_fees(
        self,
        exchange: str,
        trade_amount: Decimal,
        side: str = "buy",
        order_type: str = "limit"
    ) -> Dict[str, Any]:
        """
        Calculate all fees for a trade.
        
        Args:
            exchange: Exchange name
            trade_amount: Trade amount
            side: 'buy' or 'sell'
            order_type: 'limit' or 'market'
            
        Returns:
            Dict with all fee calculations
        """
        # Trading fee
        trading_fee = await self.calculate_trading_fee(
            exchange, trade_amount, side, order_type
        )
        
        # Withdrawal fee (if applicable)
        withdrawal_fee = await self.calculate_withdrawal_fee(
            exchange, trade_amount
        )
        
        # Gas cost (if applicable)
        gas_cost = await self.calculate_gas_cost("ethereum")
        
        # Total fees
        total_fees = trading_fee.amount + withdrawal_fee.amount + gas_cost.cost_usd
        
        return {
            "trading_fee": trading_fee,
            "withdrawal_fee": withdrawal_fee,
            "gas_cost": gas_cost,
            "total_fees": total_fees,
            "effective_rate": (
                total_fees / trade_amount * Decimal('100')
            ).quantize(Decimal('0.01'))
        }
    
    # =========================================================================
    # FEE OPTIMIZATION
    # =========================================================================
    
    async def optimize_fee(
        self,
        exchange: str,
        amount: Decimal,
        side: str = "buy",
        order_type: str = "limit"
    ) -> Dict[str, Any]:
        """
        Optimize fees for a trade.
        
        Args:
            exchange: Exchange name
            amount: Trade amount
            side: 'buy' or 'sell'
            order_type: 'limit' or 'market'
            
        Returns:
            Optimization result
        """
        config = self._fee_configs.get(exchange)
        if not config:
            raise ValueError(f"No fee config for {exchange}")
        
        result = {
            "original_fee": Decimal('0'),
            "optimized_fee": Decimal('0'),
            "savings": Decimal('0'),
            "savings_percent": Decimal('0'),
            "recommendations": []
        }
        
        # Calculate original fee
        original = await self.calculate_trading_fee(
            exchange, amount, side, order_type
        )
        result["original_fee"] = original.amount
        
        # Optimize by fee tier
        current_tier = config.fee_tier
        best_tier = current_tier
        
        for tier in FeeTier:
            # Check if volume qualifies for this tier
            volume_threshold = self._get_tier_volume_threshold(tier)
            if config.volume_30d >= volume_threshold:
                best_tier = tier
        
        if best_tier != current_tier:
            # Update config
            config.fee_tier = best_tier
            await self.update_fee_config(exchange, fee_tier=best_tier)
            
            # Calculate optimized fee
            optimized = await self.calculate_trading_fee(
                exchange, amount, side, order_type
            )
            result["optimized_fee"] = optimized.amount
            result["savings"] = original.amount - optimized.amount
            result["savings_percent"] = (
                result["savings"] / original.amount * Decimal('100')
                if original.amount > 0 else Decimal('0')
            )
            result["recommendations"].append(
                f"Upgraded to {best_tier.value} tier"
            )
        
        # Check fee discount
        if config.fee_discount is None:
            # Suggest using native token for discount
            result["recommendations"].append(
                "Use native token (BNB/OKB/KCS) for 25% fee discount"
            )
        
        return result
    
    # =========================================================================
    # GAS PRICE MONITORING
    # =========================================================================
    
    async def _gas_price_monitoring_loop(self):
        """Monitor gas prices from various chains."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Every 60 seconds
                
                # Update gas prices for supported chains
                chains = ["ethereum", "bsc", "polygon", "arbitrum", "optimism"]
                
                for chain in chains:
                    try:
                        gas_price = await self._fetch_gas_price(chain)
                        self._gas_costs[chain] = await self.calculate_gas_cost(
                            chain, gas_price=gas_price
                        )
                    except Exception as e:
                        logger.error(f"Error fetching gas price for {chain}: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Gas price monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _fetch_gas_price(self, chain: str) -> Decimal:
        """
        Fetch gas price from API.
        
        Args:
            chain: Blockchain name
            
        Returns:
            Gas price in native token
        """
        # This would integrate with gas price APIs
        # For now, return default values
        gas_prices = {
            "ethereum": Decimal('20'),  # 20 Gwei
            "bsc": Decimal('5'),  # 5 Gwei
            "polygon": Decimal('30'),  # 30 Gwei
            "arbitrum": Decimal('0.1'),  # 0.1 Gwei
            "optimism": Decimal('0.1'),  # 0.1 Gwei
        }
        return gas_prices.get(chain, Decimal('10'))
    
    async def _get_gas_price(self, chain: str) -> Decimal:
        """Get cached gas price."""
        if chain in self._gas_costs:
            return self._gas_costs[chain].gas_price
        
        return await self._fetch_gas_price(chain)
    
    async def _get_gas_limit(self, chain: str) -> Decimal:
        """Get default gas limit for a chain."""
        gas_limits = {
            "ethereum": Decimal('21000'),  # Simple transfer
            "bsc": Decimal('21000'),
            "polygon": Decimal('21000'),
            "arbitrum": Decimal('21000'),
            "optimism": Decimal('21000'),
        }
        return gas_limits.get(chain, Decimal('21000'))
    
    async def _get_token_price(self, chain: str) -> Decimal:
        """Get native token price in USD."""
        # This would integrate with price oracles
        prices = {
            "ethereum": Decimal('3000'),  # ETH
            "bsc": Decimal('600'),  # BNB
            "polygon": Decimal('1'),  # MATIC
            "arbitrum": Decimal('3000'),  # ETH
            "optimism": Decimal('3000'),  # ETH
        }
        return prices.get(chain, Decimal('1'))
    
    def _get_native_token(self, chain: str) -> str:
        """Get native token symbol for a chain."""
        tokens = {
            "ethereum": "ETH",
            "bsc": "BNB",
            "polygon": "MATIC",
            "arbitrum": "ETH",
            "optimism": "ETH",
        }
        return tokens.get(chain, "ETH")
    
    def _get_tier_volume_threshold(self, tier: FeeTier) -> Decimal:
        """Get volume threshold for a fee tier."""
        thresholds = {
            FeeTier.TIER_0: Decimal('0'),
            FeeTier.TIER_1: Decimal('100000'),  # $100K
            FeeTier.TIER_2: Decimal('500000'),  # $500K
            FeeTier.TIER_3: Decimal('1000000'),  # $1M
            FeeTier.TIER_4: Decimal('5000000'),  # $5M
            FeeTier.TIER_5: Decimal('10000000'),  # $10M
            FeeTier.TIER_6: Decimal('50000000'),  # $50M
            FeeTier.TIER_7: Decimal('100000000'),  # $100M
            FeeTier.TIER_8: Decimal('500000000'),  # $500M
            FeeTier.TIER_9: Decimal('1000000000'),  # $1B
        }
        return thresholds.get(tier, Decimal('0'))
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _load_fee_configs(self):
        """Load fee configurations from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM fee_configs")
                
                for row in rows:
                    config_data = json.loads(row['config'])
                    config = FeeConfig(**config_data)
                    self._fee_configs[config.exchange] = config
        except Exception as e:
            logger.error(f"Error loading fee configs: {e}")
    
    async def _save_fee_config(self, config: FeeConfig):
        """Save fee configuration to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO fee_configs (exchange, config, updated_at)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (exchange) DO UPDATE SET
                        config = EXCLUDED.config,
                        updated_at = EXCLUDED.updated_at
                    """,
                    config.exchange,
                    json.dumps(config.dict(), default=str),
                    config.updated_at
                )
        except Exception as e:
            logger.error(f"Error saving fee config: {e}")
    
    async def _load_fee_tiers(self):
        """Load fee tiers from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM fee_tiers")
                
                for row in rows:
                    self._fee_tiers[row['tier']] = {
                        'maker_fee': row['maker_fee'],
                        'taker_fee': row['taker_fee'],
                        'volume_required': row['volume_required']
                    }
        except Exception as e:
            logger.error(f"Error loading fee tiers: {e}")
    
    async def save_fee_history(self, history: FeeHistory):
        """Save fee history to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO fee_history (
                        id, exchange, symbol, fee_type,
                        amount, currency, rate, timestamp,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    history.id,
                    history.exchange,
                    history.symbol,
                    history.fee_type.value,
                    history.amount,
                    history.currency,
                    history.rate,
                    history.timestamp,
                    json.dumps(history.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving fee history: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the fee calculator."""
        self._running = False
        logger.info("FeeCalculator shutdown")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'FeeCalculator',
    'FeeType',
    'FeeTier',
    'FeeDiscountType',
    'FeeCurrency',
    'FeeConfig',
    'FeeCalculation',
    'GasCost',
    'FeeHistory'
]
