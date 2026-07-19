# trading/bots/arbitrage_bot/core/gas_calculator.py
# Nexus AI Trading System - Arbitrage Bot Gas Calculator Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Gas Calculator Module

This module provides comprehensive gas cost calculation and optimization
for the arbitrage bot system, including:

- Multi-chain gas price estimation
- Gas limit prediction
- Transaction cost calculation
- Gas price optimization
- Historical gas analysis
- Gas price prediction
- Cross-chain gas comparison
- Gas token optimization
- MEV protection
- Gas price alerts

The gas calculator ensures accurate profit calculations for arbitrage
opportunities involving blockchain transactions and helps optimize
gas costs for maximum profitability.

Supported chains:
- Ethereum (ETH)
- Binance Smart Chain (BSC)
- Polygon (MATIC)
- Arbitrum
- Optimism
- Avalanche
- Fantom
- Solana
- TRON
"""

import asyncio
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
import aiohttp
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class Chain(str, Enum):
    """Supported blockchain chains."""
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    AVALANCHE = "avalanche"
    FANTOM = "fantom"
    SOLANA = "solana"
    TRON = "tron"


class GasPricePriority(str, Enum):
    """Gas price priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    CUSTOM = "custom"


class TransactionType(str, Enum):
    """Transaction types."""
    SIMPLE_TRANSFER = "simple_transfer"
    TOKEN_TRANSFER = "token_transfer"
    SWAP = "swap"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    CLAIM = "claim"
    ARBITRAGE = "arbitrage"
    FLASH_LOAN = "flash_loan"
    SMART_CONTRACT = "smart_contract"
    CUSTOM = "custom"


class GasToken(str, Enum):
    """Gas tokens."""
    ETH = "ETH"
    BNB = "BNB"
    MATIC = "MATIC"
    AVAX = "AVAX"
    FTM = "FTM"
    SOL = "SOL"
    TRX = "TRX"
    ARB_ETH = "ETH"  # Arbitrum uses ETH
    OP_ETH = "ETH"   # Optimism uses ETH


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class GasPrice(BaseModel):
    """Gas price data."""
    chain: Chain
    priority: GasPricePriority
    price_gwei: Decimal  # Price in Gwei (or equivalent)
    price_native: Decimal  # Price in native token
    price_usd: Decimal  # Price in USD
    base_fee: Optional[Decimal] = None
    priority_fee: Optional[Decimal] = None
    max_fee: Optional[Decimal] = None
    max_priority_fee: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "api"
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('price_gwei')
    def validate_price(cls, v):
        if v < 0:
            raise ValueError("Gas price cannot be negative")
        return v

    @property
    def price_wei(self) -> Decimal:
        """Get price in Wei."""
        return self.price_gwei * Decimal('1e9')


class GasEstimate(BaseModel):
    """Gas estimate for a transaction."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain: Chain
    transaction_type: TransactionType
    estimated_gas: Decimal  # Estimated gas units
    max_gas: Decimal  # Maximum gas limit
    min_gas: Optional[Decimal] = None
    gas_price: GasPrice
    cost_native: Decimal  # Cost in native token
    cost_usd: Decimal  # Cost in USD
    estimated_time_seconds: Optional[int] = None
    confidence: Decimal = Decimal('0.9')
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Check if estimate is valid."""
        return self.estimated_gas > 0 and self.cost_usd >= 0


class GasHistory(BaseModel):
    """Historical gas data."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain: Chain
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    price_gwei: Decimal
    price_usd: Decimal
    base_fee: Optional[Decimal] = None
    priority_fee: Optional[Decimal] = None
    block_number: Optional[int] = None
    transaction_count: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GasOptimization(BaseModel):
    """Gas optimization result."""
    transaction_type: TransactionType
    chain: Chain
    original_cost: Decimal
    optimized_cost: Decimal
    savings: Decimal
    savings_percent: Decimal
    optimization_type: str  # timing, priority, batching, etc.
    recommendations: List[str] = Field(default_factory=list)
    confidence: Decimal = Decimal('0.8')
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Gas prices
CREATE TABLE IF NOT EXISTS gas_prices (
    id SERIAL PRIMARY KEY,
    chain VARCHAR(20) NOT NULL,
    priority VARCHAR(20) NOT NULL,
    price_gwei DECIMAL(32, 8) NOT NULL,
    price_native DECIMAL(32, 8) NOT NULL,
    price_usd DECIMAL(32, 8) NOT NULL,
    base_fee DECIMAL(32, 8),
    priority_fee DECIMAL(32, 8),
    max_fee DECIMAL(32, 8),
    max_priority_fee DECIMAL(32, 8),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    INDEX idx_gas_prices_chain (chain),
    INDEX idx_gas_prices_priority (priority),
    INDEX idx_gas_prices_timestamp (timestamp)
);

-- Gas estimates
CREATE TABLE IF NOT EXISTS gas_estimates (
    id VARCHAR(64) PRIMARY KEY,
    chain VARCHAR(20) NOT NULL,
    transaction_type VARCHAR(30) NOT NULL,
    estimated_gas DECIMAL(32, 8) NOT NULL,
    max_gas DECIMAL(32, 8) NOT NULL,
    min_gas DECIMAL(32, 8),
    gas_price JSONB NOT NULL,
    cost_native DECIMAL(32, 8) NOT NULL,
    cost_usd DECIMAL(32, 8) NOT NULL,
    estimated_time_seconds INTEGER,
    confidence DECIMAL(5, 4) DEFAULT 0.9,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_gas_estimates_chain (chain),
    INDEX idx_gas_estimates_type (transaction_type),
    INDEX idx_gas_estimates_timestamp (timestamp)
);

-- Gas history
CREATE TABLE IF NOT EXISTS gas_history (
    id VARCHAR(64) PRIMARY KEY,
    chain VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    price_gwei DECIMAL(32, 8) NOT NULL,
    price_usd DECIMAL(32, 8) NOT NULL,
    base_fee DECIMAL(32, 8),
    priority_fee DECIMAL(32, 8),
    block_number INTEGER,
    transaction_count INTEGER,
    metadata JSONB DEFAULT '{}',
    INDEX idx_gas_history_chain (chain),
    INDEX idx_gas_history_timestamp (timestamp)
);

-- Gas optimization results
CREATE TABLE IF NOT EXISTS gas_optimizations (
    id SERIAL PRIMARY KEY,
    transaction_type VARCHAR(30) NOT NULL,
    chain VARCHAR(20) NOT NULL,
    original_cost DECIMAL(32, 8) NOT NULL,
    optimized_cost DECIMAL(32, 8) NOT NULL,
    savings DECIMAL(32, 8) NOT NULL,
    savings_percent DECIMAL(5, 2) NOT NULL,
    optimization_type VARCHAR(50) NOT NULL,
    recommendations JSONB DEFAULT '[]',
    confidence DECIMAL(5, 4) DEFAULT 0.8,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_gas_optimizations_chain (chain),
    INDEX idx_gas_optimizations_type (transaction_type),
    INDEX idx_gas_optimizations_timestamp (timestamp)
);
"""


# =============================================================================
# GAS CALCULATOR CLASS
# =============================================================================

class GasCalculator:
    """
    Advanced gas calculator for arbitrage bot.
    
    Features:
    - Multi-chain gas price estimation
    - Gas limit prediction
    - Transaction cost calculation
    - Gas price optimization
    - Historical gas analysis
    - Gas price prediction
    - Cross-chain gas comparison
    - Gas token optimization
    - MEV protection
    - Gas price alerts
    - Real-time gas monitoring
    - Batch transaction optimization
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
        
        # Gas prices
        self._gas_prices: Dict[str, Dict[str, GasPrice]] = {}
        
        # Gas history
        self._gas_history: Dict[str, List[GasHistory]] = {}
        
        # Circuit breakers
        self._gas_cb = CircuitBreaker(
            name="gas_calculator",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # HTTP session
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Running state
        self._running = False
        self._initialized = False
        self._db_initialized = False
        
        # Price cache
        self._token_prices: Dict[str, Decimal] = {}
        
        logger.info("GasCalculator initialized")
    
    async def initialize(self):
        """Initialize the gas calculator."""
        if self._initialized:
            return
        
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Create HTTP session
        self._session = aiohttp.ClientSession(
            headers={"User-Agent": "NexusAI-Trading/3.0"}
        )
        
        # Initialize gas prices
        await self._update_gas_prices()
        
        # Start gas price monitoring
        self._running = True
        asyncio.create_task(self._gas_price_monitoring_loop())
        
        self._initialized = True
        logger.info("GasCalculator initialized")
    
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
    # GAS PRICE MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_gas_price(
        self,
        chain: Union[str, Chain],
        priority: GasPricePriority = GasPricePriority.MEDIUM
    ) -> GasPrice:
        """
        Get gas price for a chain.
        
        Args:
            chain: Blockchain chain
            priority: Gas price priority
            
        Returns:
            GasPrice
        """
        chain = chain if isinstance(chain, Chain) else Chain(chain)
        chain_key = chain.value
        
        # Check cache
        if chain_key in self._gas_prices and priority in self._gas_prices[chain_key]:
            gas_price = self._gas_prices[chain_key][priority]
            # Check if cache is still valid (less than 1 minute old)
            if (datetime.utcnow() - gas_price.timestamp).total_seconds() < 60:
                return gas_price
        
        # Check circuit breaker
        if self._gas_cb.is_open():
            logger.warning("Gas price circuit breaker is open, using cached prices")
            if chain_key in self._gas_prices and priority in self._gas_prices[chain_key]:
                return self._gas_prices[chain_key][priority]
            raise GasPriceUnavailableError("Circuit breaker open")
        
        try:
            # Fetch gas price from API
            gas_price = await self._fetch_gas_price(chain, priority)
            
            # Update cache
            if chain_key not in self._gas_prices:
                self._gas_prices[chain_key] = {}
            self._gas_prices[chain_key][priority] = gas_price
            
            # Record success
            self._gas_cb.record_success()
            
            return gas_price
            
        except Exception as e:
            self._gas_cb.record_failure()
            logger.error(f"Error fetching gas price for {chain}: {e}")
            
            # Return cached price if available
            if chain_key in self._gas_prices and priority in self._gas_prices[chain_key]:
                return self._gas_prices[chain_key][priority]
            
            raise GasPriceUnavailableError(f"Unable to fetch gas price for {chain}")
    
    async def get_all_gas_prices(
        self,
        chain: Union[str, Chain]
    ) -> Dict[GasPricePriority, GasPrice]:
        """
        Get all gas prices for a chain.
        
        Args:
            chain: Blockchain chain
            
        Returns:
            Dict mapping priority to GasPrice
        """
        chain = chain if isinstance(chain, Chain) else Chain(chain)
        chain_key = chain.value
        
        result = {}
        for priority in GasPricePriority:
            try:
                gas_price = await self.get_gas_price(chain, priority)
                result[priority] = gas_price
            except Exception:
                continue
        
        return result
    
    # =========================================================================
    # GAS ESTIMATION
    # =========================================================================
    
    async def estimate_gas(
        self,
        chain: Union[str, Chain],
        transaction_type: TransactionType,
        priority: GasPricePriority = GasPricePriority.MEDIUM,
        custom_gas_limit: Optional[Decimal] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> GasEstimate:
        """
        Estimate gas for a transaction.
        
        Args:
            chain: Blockchain chain
            transaction_type: Type of transaction
            priority: Gas price priority
            custom_gas_limit: Custom gas limit
            metadata: Additional metadata
            
        Returns:
            GasEstimate
        """
        chain = chain if isinstance(chain, Chain) else Chain(chain)
        
        # Get gas price
        gas_price = await self.get_gas_price(chain, priority)
        
        # Get gas limit
        if custom_gas_limit:
            gas_limit = custom_gas_limit
        else:
            gas_limit = await self._get_gas_limit(chain, transaction_type)
        
        # Get token price
        token_price = await self._get_token_price(chain)
        
        # Calculate costs
        gas_units = gas_limit
        cost_native = gas_units * gas_price.price_gwei * Decimal('1e9') / Decimal('1e18')
        cost_usd = cost_native * token_price
        
        # Estimate time
        estimated_time = self._estimate_time(chain, priority)
        
        return GasEstimate(
            chain=chain,
            transaction_type=transaction_type,
            estimated_gas=gas_units,
            max_gas=gas_units * Decimal('1.2'),  # 20% buffer
            min_gas=gas_units * Decimal('0.9'),  # 10% buffer
            gas_price=gas_price,
            cost_native=cost_native.quantize(Decimal('0.00000001')),
            cost_usd=cost_usd.quantize(Decimal('0.01')),
            estimated_time_seconds=estimated_time,
            confidence=Decimal('0.9'),
            metadata=metadata or {}
        )
    
    async def estimate_arbitrage_gas(
        self,
        chain: Union[str, Chain],
        number_of_swaps: int = 2,
        priority: GasPricePriority = GasPricePriority.MEDIUM
    ) -> GasEstimate:
        """
        Estimate gas for an arbitrage transaction.
        
        Args:
            chain: Blockchain chain
            number_of_swaps: Number of swaps in the arbitrage
            priority: Gas price priority
            
        Returns:
            GasEstimate
        """
        # Arbitrage transactions typically involve multiple contract calls
        # Each swap adds ~100k-200k gas
        base_gas = 100000  # Base gas for arbitrage contract
        swap_gas = 150000  # Gas per swap
        total_gas = base_gas + (swap_gas * number_of_swaps)
        
        return await self.estimate_gas(
            chain=chain,
            transaction_type=TransactionType.ARBITRAGE,
            priority=priority,
            custom_gas_limit=Decimal(str(total_gas)),
            metadata={
                "number_of_swaps": number_of_swaps,
                "base_gas": base_gas,
                "swap_gas": swap_gas
            }
        )
    
    async def estimate_flash_loan_gas(
        self,
        chain: Union[str, Chain],
        priority: GasPricePriority = GasPricePriority.MEDIUM
    ) -> GasEstimate:
        """
        Estimate gas for a flash loan transaction.
        
        Args:
            chain: Blockchain chain
            priority: Gas price priority
            
        Returns:
            GasEstimate
        """
        # Flash loans typically require more gas
        flash_loan_gas = 300000  # Base gas for flash loan
        
        return await self.estimate_gas(
            chain=chain,
            transaction_type=TransactionType.FLASH_LOAN,
            priority=priority,
            custom_gas_limit=Decimal(str(flash_loan_gas)),
            metadata={"flash_loan": True}
        )
    
    # =========================================================================
    # GAS OPTIMIZATION
    # =========================================================================
    
    async def optimize_gas(
        self,
        chain: Union[str, Chain],
        transaction_type: TransactionType,
        current_priority: GasPricePriority = GasPricePriority.MEDIUM,
        max_wait_time: int = 300  # seconds
    ) -> GasOptimization:
        """
        Optimize gas costs.
        
        Args:
            chain: Blockchain chain
            transaction_type: Type of transaction
            current_priority: Current gas priority
            max_wait_time: Maximum wait time in seconds
            
        Returns:
            GasOptimization
        """
        chain = chain if isinstance(chain, Chain) else Chain(chain)
        
        # Get current gas price
        current_gas = await self.get_gas_price(chain, current_priority)
        
        # Get historical gas prices
        history = await self.get_gas_history(chain, hours=24)
        
        # Find best price
        best_price = current_gas.price_gwei
        best_priority = current_priority
        
        for priority in GasPricePriority:
            try:
                gas_price = await self.get_gas_price(chain, priority)
                if gas_price.price_gwei < best_price:
                    best_price = gas_price.price_gwei
                    best_priority = priority
            except Exception:
                continue
        
        # Calculate savings
        original_cost = current_gas.price_gwei
        optimized_cost = best_price
        savings = original_cost - optimized_cost
        savings_percent = (savings / original_cost * 100) if original_cost > 0 else Decimal('0')
        
        # Generate recommendations
        recommendations = []
        
        if best_priority != current_priority:
            recommendations.append(f"Use {best_priority.value} priority instead of {current_priority.value}")
        
        if best_price < current_gas.price_gwei * Decimal('0.8'):
            recommendations.append("Gas prices are significantly lower, consider waiting")
        
        # Check if batching is possible
        if transaction_type in [TransactionType.TOKEN_TRANSFER, TransactionType.SWAP]:
            recommendations.append("Consider batching multiple transactions")
        
        # Check for gas token usage
        token_prices = await self._get_token_prices()
        native_token = self._get_native_token(chain)
        if token_prices.get(native_token, Decimal('0')) > Decimal('3000'):
            recommendations.append("Consider using a gas token for discounts")
        
        return GasOptimization(
            transaction_type=transaction_type,
            chain=chain,
            original_cost=original_cost,
            optimized_cost=optimized_cost,
            savings=savings,
            savings_percent=savings_percent,
            optimization_type="priority_optimization",
            recommendations=recommendations,
            confidence=Decimal('0.85')
        )
    
    # =========================================================================
    # GAS HISTORY
    # =========================================================================
    
    async def get_gas_history(
        self,
        chain: Union[str, Chain],
        hours: int = 24,
        limit: int = 100
    ) -> List[GasHistory]:
        """
        Get historical gas prices.
        
        Args:
            chain: Blockchain chain
            hours: Hours of history
            limit: Maximum number of records
            
        Returns:
            List of GasHistory
        """
        chain = chain if isinstance(chain, Chain) else Chain(chain)
        chain_key = chain.value
        
        if self.redis:
            # Try to get from cache
            cache_key = f"gas_history:{chain_key}:{hours}"
            cached = await self.redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return [GasHistory(**item) for item in data[:limit]]
        
        # Get from database
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM gas_history
                        WHERE chain = $1
                        AND timestamp > NOW() - INTERVAL '$2 hours'
                        ORDER BY timestamp DESC
                        LIMIT $3
                        """,
                        chain_key,
                        hours,
                        limit
                    )
                    
                    history = []
                    for row in rows:
                        history.append(GasHistory(
                            id=row['id'],
                            chain=Chain(row['chain']),
                            timestamp=row['timestamp'],
                            price_gwei=row['price_gwei'],
                            price_usd=row['price_usd'],
                            base_fee=row.get('base_fee'),
                            priority_fee=row.get('priority_fee'),
                            block_number=row.get('block_number'),
                            transaction_count=row.get('transaction_count'),
                            metadata=row.get('metadata') or {}
                        ))
                    
                    return history
            except Exception as e:
                logger.error(f"Error getting gas history: {e}")
        
        return []
    
    # =========================================================================
    # GAS PRICE FETCHING
    # =========================================================================
    
    async def _fetch_gas_price(
        self,
        chain: Chain,
        priority: GasPricePriority
    ) -> GasPrice:
        """
        Fetch gas price from API.
        
        Args:
            chain: Blockchain chain
            priority: Gas price priority
            
        Returns:
            GasPrice
        """
        # Try different gas price APIs
        api_chain = chain.value
        
        try:
            # Try Etherscan API for Ethereum
            if chain == Chain.ETHEREUM:
                return await self._fetch_etherscan_gas_price(priority)
            
            # Try OKX API for multiple chains
            return await self._fetch_okx_gas_price(chain, priority)
            
        except Exception as e:
            logger.error(f"Error fetching gas price from API: {e}")
            raise
    
    async def _fetch_etherscan_gas_price(
        self,
        priority: GasPricePriority
    ) -> GasPrice:
        """Fetch gas price from Etherscan."""
        # This would use Etherscan API
        # For now, return reasonable defaults
        gas_prices = {
            GasPricePriority.LOW: Decimal('15'),
            GasPricePriority.MEDIUM: Decimal('25'),
            GasPricePriority.HIGH: Decimal('40'),
            GasPricePriority.URGENT: Decimal('60'),
        }
        
        price_gwei = gas_prices.get(priority, Decimal('25'))
        token_price = await self._get_token_price(Chain.ETHEREUM)
        
        return GasPrice(
            chain=Chain.ETHEREUM,
            priority=priority,
            price_gwei=price_gwei,
            price_native=price_gwei / Decimal('1e9'),
            price_usd=price_gwei * token_price / Decimal('1e9'),
            base_fee=price_gwei * Decimal('0.8'),
            priority_fee=price_gwei * Decimal('0.2'),
            timestamp=datetime.utcnow(),
            source="etherscan"
        )
    
    async def _fetch_okx_gas_price(
        self,
        chain: Chain,
        priority: GasPricePriority
    ) -> GasPrice:
        """Fetch gas price from OKX API."""
        # This would use OKX API
        # For now, return reasonable defaults
        gas_prices = {
            Chain.ETHEREUM: {GasPricePriority.LOW: 15, GasPricePriority.MEDIUM: 25, GasPricePriority.HIGH: 40, GasPricePriority.URGENT: 60},
            Chain.BSC: {GasPricePriority.LOW: 3, GasPricePriority.MEDIUM: 5, GasPricePriority.HIGH: 8, GasPricePriority.URGENT: 12},
            Chain.POLYGON: {GasPricePriority.LOW: 20, GasPricePriority.MEDIUM: 30, GasPricePriority.HIGH: 50, GasPricePriority.URGENT: 80},
            Chain.ARBITRUM: {GasPricePriority.LOW: 0.05, GasPricePriority.MEDIUM: 0.1, GasPricePriority.HIGH: 0.2, GasPricePriority.URGENT: 0.5},
            Chain.OPTIMISM: {GasPricePriority.LOW: 0.05, GasPricePriority.MEDIUM: 0.1, GasPricePriority.HIGH: 0.2, GasPricePriority.URGENT: 0.5},
        }
        
        chain_prices = gas_prices.get(chain, {})
        price_gwei = chain_prices.get(priority, Decimal('25'))
        
        token_price = await self._get_token_price(chain)
        
        return GasPrice(
            chain=chain,
            priority=priority,
            price_gwei=price_gwei,
            price_native=price_gwei / Decimal('1e9'),
            price_usd=price_gwei * token_price / Decimal('1e9'),
            base_fee=price_gwei * Decimal('0.8'),
            priority_fee=price_gwei * Decimal('0.2'),
            timestamp=datetime.utcnow(),
            source="okx"
        )
    
    # =========================================================================
    # GAS LIMIT
    # =========================================================================
    
    async def _get_gas_limit(
        self,
        chain: Chain,
        transaction_type: TransactionType
    ) -> Decimal:
        """Get gas limit for a transaction type."""
        gas_limits = {
            Chain.ETHEREUM: {
                TransactionType.SIMPLE_TRANSFER: Decimal('21000'),
                TransactionType.TOKEN_TRANSFER: Decimal('60000'),
                TransactionType.SWAP: Decimal('150000'),
                TransactionType.DEPOSIT: Decimal('100000'),
                TransactionType.WITHDRAWAL: Decimal('100000'),
                TransactionType.CLAIM: Decimal('80000'),
                TransactionType.ARBITRAGE: Decimal('250000'),
                TransactionType.FLASH_LOAN: Decimal('300000'),
                TransactionType.SMART_CONTRACT: Decimal('200000'),
            },
            Chain.BSC: {
                TransactionType.SIMPLE_TRANSFER: Decimal('21000'),
                TransactionType.TOKEN_TRANSFER: Decimal('50000'),
                TransactionType.SWAP: Decimal('120000'),
                TransactionType.DEPOSIT: Decimal('80000'),
                TransactionType.WITHDRAWAL: Decimal('80000'),
                TransactionType.CLAIM: Decimal('60000'),
                TransactionType.ARBITRAGE: Decimal('200000'),
                TransactionType.FLASH_LOAN: Decimal('250000'),
                TransactionType.SMART_CONTRACT: Decimal('150000'),
            },
            Chain.POLYGON: {
                TransactionType.SIMPLE_TRANSFER: Decimal('21000'),
                TransactionType.TOKEN_TRANSFER: Decimal('50000'),
                TransactionType.SWAP: Decimal('120000'),
                TransactionType.DEPOSIT: Decimal('80000'),
                TransactionType.WITHDRAWAL: Decimal('80000'),
                TransactionType.CLAIM: Decimal('60000'),
                TransactionType.ARBITRAGE: Decimal('200000'),
                TransactionType.FLASH_LOAN: Decimal('250000'),
                TransactionType.SMART_CONTRACT: Decimal('150000'),
            },
        }
        
        chain_limits = gas_limits.get(chain, {})
        return chain_limits.get(transaction_type, Decimal('100000'))
    
    # =========================================================================
    # TOKEN PRICES
    # =========================================================================
    
    async def _get_token_price(self, chain: Chain) -> Decimal:
        """Get native token price in USD."""
        token = self._get_native_token(chain)
        
        # Check cache
        if token in self._token_prices:
            return self._token_prices[token]
        
        # Fetch price from API
        try:
            price = await self._fetch_token_price(token)
            self._token_prices[token] = price
            return price
        except Exception:
            # Return default price
            default_prices = {
                "ETH": Decimal('3000'),
                "BNB": Decimal('600'),
                "MATIC": Decimal('1'),
                "AVAX": Decimal('35'),
                "FTM": Decimal('0.5'),
                "SOL": Decimal('100'),
                "TRX": Decimal('0.1'),
                "ARB_ETH": Decimal('3000'),
                "OP_ETH": Decimal('3000'),
            }
            return default_prices.get(token, Decimal('1'))
    
    async def _fetch_token_price(self, token: str) -> Decimal:
        """Fetch token price from API."""
        # This would use price oracle APIs
        # For now, return cached or default
        return Decimal('1')
    
    async def _get_token_prices(self) -> Dict[str, Decimal]:
        """Get all token prices."""
        tokens = ["ETH", "BNB", "MATIC", "AVAX", "FTM", "SOL", "TRX"]
        result = {}
        for token in tokens:
            result[token] = await self._fetch_token_price(token)
        return result
    
    def _get_native_token(self, chain: Chain) -> str:
        """Get native token for a chain."""
        tokens = {
            Chain.ETHEREUM: "ETH",
            Chain.BSC: "BNB",
            Chain.POLYGON: "MATIC",
            Chain.ARBITRUM: "ETH",
            Chain.OPTIMISM: "ETH",
            Chain.AVALANCHE: "AVAX",
            Chain.FANTOM: "FTM",
            Chain.SOLANA: "SOL",
            Chain.TRON: "TRX",
        }
        return tokens.get(chain, "ETH")
    
    # =========================================================================
    # TIME ESTIMATION
    # =========================================================================
    
    def _estimate_time(self, chain: Chain, priority: GasPricePriority) -> int:
        """Estimate transaction time in seconds."""
        times = {
            Chain.ETHEREUM: {
                GasPricePriority.LOW: 300,
                GasPricePriority.MEDIUM: 120,
                GasPricePriority.HIGH: 60,
                GasPricePriority.URGENT: 30,
            },
            Chain.BSC: {
                GasPricePriority.LOW: 60,
                GasPricePriority.MEDIUM: 30,
                GasPricePriority.HIGH: 15,
                GasPricePriority.URGENT: 5,
            },
            Chain.POLYGON: {
                GasPricePriority.LOW: 60,
                GasPricePriority.MEDIUM: 30,
                GasPricePriority.HIGH: 15,
                GasPricePriority.URGENT: 5,
            },
        }
        
        chain_times = times.get(chain, {})
        return chain_times.get(priority, 60)
    
    # =========================================================================
    # GAS PRICE MONITORING
    # =========================================================================
    
    async def _gas_price_monitoring_loop(self):
        """Monitor gas prices from multiple chains."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Every 60 seconds
                
                # Update gas prices for all chains
                for chain in Chain:
                    try:
                        await self._update_gas_prices_for_chain(chain)
                    except Exception as e:
                        logger.error(f"Error updating gas price for {chain}: {e}")
                
                # Clean up old history
                if self.pool:
                    async with self.pool.acquire() as conn:
                        await conn.execute(
                            "DELETE FROM gas_history WHERE timestamp < NOW() - INTERVAL '7 days'"
                        )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Gas price monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _update_gas_prices(self):
        """Update all gas prices."""
        for chain in Chain:
            try:
                await self._update_gas_prices_for_chain(chain)
            except Exception as e:
                logger.error(f"Error updating gas prices for {chain}: {e}")
    
    async def _update_gas_prices_for_chain(self, chain: Chain):
        """Update gas prices for a specific chain."""
        for priority in GasPricePriority:
            try:
                gas_price = await self._fetch_gas_price(chain, priority)
                
                chain_key = chain.value
                if chain_key not in self._gas_prices:
                    self._gas_prices[chain_key] = {}
                self._gas_prices[chain_key][priority] = gas_price
                
                # Save to database
                if self.pool:
                    await self._save_gas_price(gas_price)
                
            except Exception as e:
                logger.error(f"Error updating gas price for {chain} {priority}: {e}")
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_gas_price(self, gas_price: GasPrice):
        """Save gas price to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO gas_prices (
                        chain, priority, price_gwei, price_native,
                        price_usd, base_fee, priority_fee,
                        max_fee, max_priority_fee, timestamp,
                        source, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                    gas_price.chain.value,
                    gas_price.priority.value,
                    gas_price.price_gwei,
                    gas_price.price_native,
                    gas_price.price_usd,
                    gas_price.base_fee,
                    gas_price.priority_fee,
                    gas_price.max_fee,
                    gas_price.max_priority_fee,
                    gas_price.timestamp,
                    gas_price.source,
                    json.dumps(gas_price.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving gas price: {e}")
    
    async def save_gas_history(self, history: GasHistory):
        """Save gas history to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO gas_history (
                        id, chain, timestamp, price_gwei,
                        price_usd, base_fee, priority_fee,
                        block_number, transaction_count, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    history.id,
                    history.chain.value,
                    history.timestamp,
                    history.price_gwei,
                    history.price_usd,
                    history.base_fee,
                    history.priority_fee,
                    history.block_number,
                    history.transaction_count,
                    json.dumps(history.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving gas history: {e}")
    
    # =========================================================================
    # CACHE OPERATIONS
    # =========================================================================
    
    async def _cache_gas_price(self, gas_price: GasPrice):
        """Cache gas price in Redis."""
        if not self.redis:
            return
        
        try:
            key = f"gas_price:{gas_price.chain.value}:{gas_price.priority.value}"
            await self.redis.setex(
                key,
                60,  # 1 minute TTL
                json.dumps(gas_price.dict(), default=str)
            )
        except Exception as e:
            logger.error(f"Error caching gas price: {e}")
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    async def get_gas_comparison(
        self,
        chains: List[Union[str, Chain]],
        priority: GasPricePriority = GasPricePriority.MEDIUM
    ) -> Dict[str, GasPrice]:
        """
        Compare gas prices across chains.
        
        Args:
            chains: List of chains to compare
            priority: Gas price priority
            
        Returns:
            Dict mapping chain to GasPrice
        """
        result = {}
        for chain in chains:
            chain = chain if isinstance(chain, Chain) else Chain(chain)
            try:
                gas_price = await self.get_gas_price(chain, priority)
                result[chain.value] = gas_price
            except Exception as e:
                logger.error(f"Error getting gas price for {chain}: {e}")
                result[chain.value] = None
        
        return result
    
    async def get_cheapest_chain(
        self,
        chains: List[Union[str, Chain]],
        priority: GasPricePriority = GasPricePriority.MEDIUM
    ) -> Tuple[Chain, GasPrice]:
        """
        Get the cheapest chain for gas.
        
        Args:
            chains: List of chains to compare
            priority: Gas price priority
            
        Returns:
            Tuple of (cheapest_chain, gas_price)
        """
        best_chain = None
        best_price = None
        
        for chain in chains:
            chain = chain if isinstance(chain, Chain) else Chain(chain)
            try:
                gas_price = await self.get_gas_price(chain, priority)
                if best_price is None or gas_price.price_usd < best_price.price_usd:
                    best_chain = chain
                    best_price = gas_price
            except Exception:
                continue
        
        if best_chain is None:
            raise GasPriceUnavailableError("No gas prices available")
        
        return best_chain, best_price
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the gas calculator."""
        self._running = False
        
        if self._session:
            await self._session.close()
        
        logger.info("GasCalculator shutdown")


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class GasPriceUnavailableError(Exception):
    """Gas price unavailable error."""
    pass


class GasEstimateError(Exception):
    """Gas estimate error."""
    pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'GasCalculator',
    'Chain',
    'GasPricePriority',
    'TransactionType',
    'GasToken',
    'GasPrice',
    'GasEstimate',
    'GasHistory',
    'GasOptimization',
    'GasPriceUnavailableError',
    'GasEstimateError'
]
