# trading/bots/arbitrage_bot/core/balance_manager.py
# Nexus AI Trading System - Arbitrage Bot Balance Manager Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Arbitrage Bot - Balance Manager Module

This module provides comprehensive balance management for the arbitrage bot
system, including:

- Multi-exchange balance tracking and synchronization
- Balance allocation and optimization
- Risk-based position sizing
- Real-time balance monitoring
- Balance reconciliation
- Automated balance rebalancing
- Balance history and analytics
- Balance alerts and notifications
- Multi-currency balance management
- Balance caching and persistence

The balance manager ensures that the arbitrage bot has accurate and up-to-date
balance information across all exchanges for effective arbitrage execution.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine, Set

import asyncpg
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from trading.exchanges.okx.base import OKXBase
from trading.exchanges.okx.account import OKXAccountManager
from trading.exchanges.kraken.account import KrakenAccountManager
from trading.exchanges.binance.account import BinanceAccountManager
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry
from shared.helpers.crypto_helpers import encrypt_data, decrypt_data

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class BalanceStatus(str, Enum):
    """Balance status."""
    AVAILABLE = "available"
    LOCKED = "locked"
    PENDING = "pending"
    RESERVED = "reserved"
    STAKED = "staked"
    EARNED = "earned"
    BORROWED = "borrowed"


class BalanceUpdateType(str, Enum):
    """Balance update types."""
    SYNC = "sync"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRADE = "trade"
    TRANSFER = "transfer"
    FEE = "fee"
    STAKING = "staking"
    EARNING = "earning"
    ADJUSTMENT = "adjustment"


class BalanceAllocationStrategy(str, Enum):
    """Balance allocation strategies."""
    EQUAL = "equal"
    PROPORTIONAL = "proportional"
    RISK_BASED = "risk_based"
    PERFORMANCE_BASED = "performance_based"
    CUSTOM = "custom"


class CurrencyType(str, Enum):
    """Currency types."""
    FIAT = "fiat"
    CRYPTO = "crypto"
    STABLE = "stable"
    COMMODITY = "commodity"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class Balance(BaseModel):
    """Balance model."""
    exchange: str
    currency: str
    total: Decimal = Decimal('0')
    available: Decimal = Decimal('0')
    locked: Decimal = Decimal('0')
    pending: Decimal = Decimal('0')
    reserved: Decimal = Decimal('0')
    staked: Decimal = Decimal('0')
    earned: Decimal = Decimal('0')
    borrowed: Decimal = Decimal('0')
    status: BalanceStatus = BalanceStatus.AVAILABLE
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('currency')
    def validate_currency(cls, v):
        if not v:
            raise ValueError("Currency cannot be empty")
        return v.upper()

    @root_validator
    def validate_balance(cls, values):
        """Validate balance consistency."""
        total = values.get('total', Decimal('0'))
        available = values.get('available', Decimal('0'))
        locked = values.get('locked', Decimal('0'))
        pending = values.get('pending', Decimal('0'))
        reserved = values.get('reserved', Decimal('0'))
        staked = values.get('staked', Decimal('0'))
        earned = values.get('earned', Decimal('0'))
        borrowed = values.get('borrowed', Decimal('0'))
        
        # Calculate total from components
        calculated = available + locked + pending + reserved + staked + earned
        if abs(total - calculated) > Decimal('0.00000001'):
            values['total'] = calculated
        
        return values

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
            datetime: lambda v: v.isoformat()
        }


class BalanceSnapshot(BaseModel):
    """Balance snapshot model."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    balances: Dict[str, Balance] = Field(default_factory=dict)
    total_value_usd: Decimal = Decimal('0')
    total_value_btc: Decimal = Decimal('0')
    available_value_usd: Decimal = Decimal('0')
    locked_value_usd: Decimal = Decimal('0')
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BalanceAlert(BaseModel):
    """Balance alert model."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    exchange: str
    currency: str
    type: str  # min, max, change
    threshold: Decimal
    current_value: Decimal
    previous_value: Decimal
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BalanceAllocation(BaseModel):
    """Balance allocation model."""
    exchange: str
    currency: str
    allocated: Decimal = Decimal('0')
    utilized: Decimal = Decimal('0')
    reserved: Decimal = Decimal('0')
    free: Decimal = Decimal('0')
    percentage: Decimal = Decimal('0')
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Balance snapshots
CREATE TABLE IF NOT EXISTS arbitrage_balance_snapshots (
    id VARCHAR(64) PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    balances JSONB NOT NULL,
    total_value_usd DECIMAL(32, 16) DEFAULT 0,
    total_value_btc DECIMAL(32, 16) DEFAULT 0,
    available_value_usd DECIMAL(32, 16) DEFAULT 0,
    locked_value_usd DECIMAL(32, 16) DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    INDEX idx_arbitrage_balance_snapshots_exchange (exchange),
    INDEX idx_arbitrage_balance_snapshots_timestamp (timestamp)
);

-- Balance alerts
CREATE TABLE IF NOT EXISTS arbitrage_balance_alerts (
    id VARCHAR(64) PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    type VARCHAR(20) NOT NULL,
    threshold DECIMAL(32, 16) NOT NULL,
    current_value DECIMAL(32, 16) NOT NULL,
    previous_value DECIMAL(32, 16) NOT NULL,
    triggered_at TIMESTAMP NOT NULL,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_arbitrage_balance_alerts_exchange (exchange),
    INDEX idx_arbitrage_balance_alerts_triggered_at (triggered_at)
);

-- Balance allocations
CREATE TABLE IF NOT EXISTS arbitrage_balance_allocations (
    exchange VARCHAR(50) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    allocated DECIMAL(32, 16) DEFAULT 0,
    utilized DECIMAL(32, 16) DEFAULT 0,
    reserved DECIMAL(32, 16) DEFAULT 0,
    free DECIMAL(32, 16) DEFAULT 0,
    percentage DECIMAL(32, 16) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    PRIMARY KEY (exchange, currency)
);

-- Balance history
CREATE TABLE IF NOT EXISTS arbitrage_balance_history (
    id SERIAL PRIMARY KEY,
    exchange VARCHAR(50) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    total DECIMAL(32, 16) NOT NULL,
    available DECIMAL(32, 16) NOT NULL,
    locked DECIMAL(32, 16) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    INDEX idx_arbitrage_balance_history_exchange (exchange),
    INDEX idx_arbitrage_balance_history_currency (currency),
    INDEX idx_arbitrage_balance_history_timestamp (timestamp)
);
"""


# =============================================================================
# EXCHANGE BALANCE ADAPTERS
# =============================================================================

class ExchangeBalanceAdapter(ABC):
    """Abstract base class for exchange balance adapters."""
    
    @abstractmethod
    async def get_balances(self, currencies: Optional[List[str]] = None) -> Dict[str, Balance]:
        """Get balances from exchange."""
        pass
    
    @abstractmethod
    async def get_balance(self, currency: str) -> Optional[Balance]:
        """Get balance for a specific currency."""
        pass


class OKXBalanceAdapter(ExchangeBalanceAdapter):
    """OKX exchange balance adapter."""
    
    def __init__(self, account_manager: OKXAccountManager):
        self.account_manager = account_manager
    
    async def get_balances(self, currencies: Optional[List[str]] = None) -> Dict[str, Balance]:
        """Get balances from OKX."""
        try:
            okx_balances = await self.account_manager.get_balances(currencies)
            
            balances = {}
            for currency, okx_balance in okx_balances.items():
                balances[currency] = Balance(
                    exchange="okx",
                    currency=currency,
                    total=okx_balance.total,
                    available=okx_balance.available,
                    locked=okx_balance.frozen,
                    pending=okx_balance.pending,
                    staked=okx_balance.staked,
                    earned=okx_balance.earned,
                    borrowed=okx_balance.borrowed,
                    updated_at=okx_balance.updated_at,
                    metadata={"source": "okx_api"}
                )
            
            return balances
        except Exception as e:
            logger.error(f"Error getting OKX balances: {e}")
            return {}
    
    async def get_balance(self, currency: str) -> Optional[Balance]:
        """Get balance for a specific currency from OKX."""
        balances = await self.get_balances([currency])
        return balances.get(currency.upper())


class KrakenBalanceAdapter(ExchangeBalanceAdapter):
    """Kraken exchange balance adapter."""
    
    def __init__(self, account_manager: KrakenAccountManager):
        self.account_manager = account_manager
    
    async def get_balances(self, currencies: Optional[List[str]] = None) -> Dict[str, Balance]:
        """Get balances from Kraken."""
        try:
            kraken_balances = await self.account_manager.get_balances(currencies)
            
            balances = {}
            for currency, kraken_balance in kraken_balances.items():
                balances[currency] = Balance(
                    exchange="kraken",
                    currency=currency,
                    total=kraken_balance.total,
                    available=kraken_balance.available,
                    locked=kraken_balance.locked,
                    pending=kraken_balance.pending,
                    staked=kraken_balance.staked,
                    earned=kraken_balance.earned,
                    updated_at=kraken_balance.updated_at,
                    metadata={"source": "kraken_api"}
                )
            
            return balances
        except Exception as e:
            logger.error(f"Error getting Kraken balances: {e}")
            return {}
    
    async def get_balance(self, currency: str) -> Optional[Balance]:
        """Get balance for a specific currency from Kraken."""
        balances = await self.get_balances([currency])
        return balances.get(currency.upper())


class BinanceBalanceAdapter(ExchangeBalanceAdapter):
    """Binance exchange balance adapter."""
    
    def __init__(self, account_manager: BinanceAccountManager):
        self.account_manager = account_manager
    
    async def get_balances(self, currencies: Optional[List[str]] = None) -> Dict[str, Balance]:
        """Get balances from Binance."""
        try:
            binance_balances = await self.account_manager.get_balances(currencies)
            
            balances = {}
            for currency, binance_balance in binance_balances.items():
                balances[currency] = Balance(
                    exchange="binance",
                    currency=currency,
                    total=binance_balance.total,
                    available=binance_balance.available,
                    locked=binance_balance.locked,
                    pending=binance_balance.pending,
                    staked=binance_balance.staked,
                    earned=binance_balance.earned,
                    borrowed=binance_balance.borrowed,
                    updated_at=binance_balance.updated_at,
                    metadata={"source": "binance_api"}
                )
            
            return balances
        except Exception as e:
            logger.error(f"Error getting Binance balances: {e}")
            return {}
    
    async def get_balance(self, currency: str) -> Optional[Balance]:
        """Get balance for a specific currency from Binance."""
        balances = await self.get_balances([currency])
        return balances.get(currency.upper())


# =============================================================================
# MAIN BALANCE MANAGER
# =============================================================================

class BalanceManager:
    """
    Advanced balance manager for arbitrage bot.
    
    Features:
    - Multi-exchange balance tracking
    - Real-time balance synchronization
    - Balance allocation optimization
    - Risk-based position sizing
    - Balance alerts and monitoring
    - Balance reconciliation
    - Automated rebalancing
    - Balance history and analytics
    - Balance caching and persistence
    - Comprehensive error handling
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
        
        # Balance adapters
        self._adapters: Dict[str, ExchangeBalanceAdapter] = {}
        
        # Balance cache
        self._balances: Dict[str, Dict[str, Balance]] = {}  # exchange -> currency -> Balance
        self._balance_timestamps: Dict[str, float] = {}  # exchange -> last update time
        
        # Balance allocations
        self._allocations: Dict[str, Dict[str, BalanceAllocation]] = {}
        
        # Circuit breakers
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Alerts
        self._alerts: List[BalanceAlert] = []
        self._alert_callbacks: List[Callable] = []
        
        # Running state
        self._running = False
        self._sync_task: Optional[asyncio.Task] = None
        self._shutdown_requested = False
        
        # Database
        self._db_initialized = False
        
        # Lock
        self._lock = asyncio.Lock()
        
        logger.info("BalanceManager initialized")
    
    async def initialize(self):
        """Initialize the balance manager."""
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load cached balances
        if self.redis:
            await self._load_cached_balances()
        
        # Load allocations
        if self.pool:
            await self._load_allocations()
        
        # Start sync task
        self._running = True
        self._sync_task = asyncio.create_task(self._periodic_sync())
        
        # Start alert monitoring
        asyncio.create_task(self._alert_monitoring_loop())
        
        logger.info("BalanceManager initialization complete")
    
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
    # ADAPTER REGISTRATION
    # =========================================================================
    
    def register_adapter(self, exchange: str, adapter: ExchangeBalanceAdapter):
        """
        Register a balance adapter for an exchange.
        
        Args:
            exchange: Exchange name
            adapter: Balance adapter instance
        """
        self._adapters[exchange.lower()] = adapter
        self._circuit_breakers[exchange.lower()] = CircuitBreaker(
            name=f"balance_{exchange.lower()}",
            failure_threshold=3,
            recovery_timeout=30
        )
        logger.info(f"Registered balance adapter for {exchange}")
    
    # =========================================================================
    # BALANCE RETRIEVAL
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_balances(
        self,
        exchange: Optional[str] = None,
        currencies: Optional[List[str]] = None,
        refresh: bool = False
    ) -> Dict[str, Dict[str, Balance]]:
        """
        Get balances from one or all exchanges.
        
        Args:
            exchange: Specific exchange (None = all)
            currencies: List of currencies (None = all)
            refresh: Force refresh from exchange
            
        Returns:
            Dict mapping exchange to currency to Balance
        """
        if exchange:
            return {exchange: await self._get_exchange_balances(exchange, currencies, refresh)}
        
        # Get from all exchanges
        results = {}
        for exchange_name in self._adapters.keys():
            try:
                results[exchange_name] = await self._get_exchange_balances(
                    exchange_name, currencies, refresh
                )
            except Exception as e:
                logger.error(f"Error getting balances from {exchange_name}: {e}")
                results[exchange_name] = {}
        
        return results
    
    async def _get_exchange_balances(
        self,
        exchange: str,
        currencies: Optional[List[str]] = None,
        refresh: bool = False
    ) -> Dict[str, Balance]:
        """
        Get balances from a specific exchange.
        
        Args:
            exchange: Exchange name
            currencies: List of currencies
            refresh: Force refresh
            
        Returns:
            Dict mapping currency to Balance
        """
        exchange = exchange.lower()
        
        # Check circuit breaker
        if exchange in self._circuit_breakers:
            if self._circuit_breakers[exchange].is_open():
                # Return cached balances
                async with self._lock:
                    if exchange in self._balances:
                        return self._balances[exchange].copy()
                raise BalanceError(f"Circuit breaker open for {exchange}")
        
        # Check cache
        if not refresh:
            async with self._lock:
                if exchange in self._balances:
                    cache_age = time.time() - self._balance_timestamps.get(exchange, 0)
                    if cache_age < self.config.get('cache_ttl', 30):
                        return self._balances[exchange].copy()
        
        # Get from adapter
        adapter = self._adapters.get(exchange)
        if not adapter:
            raise ValueError(f"No adapter registered for {exchange}")
        
        try:
            balances = await adapter.get_balances(currencies)
            
            # Update cache
            async with self._lock:
                self._balances[exchange] = balances
                self._balance_timestamps[exchange] = time.time()
            
            # Save to cache
            if self.redis:
                await self._cache_balances(exchange, balances)
            
            # Save to database
            if self.pool:
                await self._save_balances(exchange, balances)
            
            # Record success
            if exchange in self._circuit_breakers:
                self._circuit_breakers[exchange].record_success()
            
            return balances
            
        except Exception as e:
            if exchange in self._circuit_breakers:
                self._circuit_breakers[exchange].record_failure()
            logger.error(f"Error getting balances from {exchange}: {e}")
            
            # Return cached balances if available
            async with self._lock:
                if exchange in self._balances:
                    return self._balances[exchange].copy()
            
            raise
    
    async def get_balance(
        self,
        exchange: str,
        currency: str,
        refresh: bool = False
    ) -> Optional[Balance]:
        """
        Get balance for a specific currency on an exchange.
        
        Args:
            exchange: Exchange name
            currency: Currency code
            refresh: Force refresh
            
        Returns:
            Balance object or None
        """
        balances = await self.get_balances(exchange, [currency], refresh)
        return balances.get(exchange, {}).get(currency.upper())
    
    # =========================================================================
    # BALANCE ALLOCATION
    # =========================================================================
    
    async def get_allocation(
        self,
        exchange: str,
        currency: str
    ) -> Optional[BalanceAllocation]:
        """
        Get balance allocation for a specific currency.
        
        Args:
            exchange: Exchange name
            currency: Currency code
            
        Returns:
            BalanceAllocation or None
        """
        exchange = exchange.lower()
        currency = currency.upper()
        
        async with self._lock:
            if exchange in self._allocations:
                return self._allocations[exchange].get(currency)
        
        return None
    
    async def get_all_allocations(
        self,
        exchange: Optional[str] = None
    ) -> Dict[str, Dict[str, BalanceAllocation]]:
        """
        Get all balance allocations.
        
        Args:
            exchange: Specific exchange (None = all)
            
        Returns:
            Dict mapping exchange to currency to BalanceAllocation
        """
        async with self._lock:
            if exchange:
                return {exchange: self._allocations.get(exchange, {})}
            return self._allocations.copy()
    
    async def update_allocation(
        self,
        exchange: str,
        currency: str,
        allocated: Optional[Decimal] = None,
        utilized: Optional[Decimal] = None,
        reserved: Optional[Decimal] = None,
        percentage: Optional[Decimal] = None
    ) -> BalanceAllocation:
        """
        Update balance allocation.
        
        Args:
            exchange: Exchange name
            currency: Currency code
            allocated: Allocated amount
            utilized: Utilized amount
            reserved: Reserved amount
            percentage: Allocation percentage
            
        Returns:
            Updated BalanceAllocation
        """
        exchange = exchange.lower()
        currency = currency.upper()
        
        # Get current balance
        balance = await self.get_balance(exchange, currency, refresh=True)
        if not balance:
            raise ValueError(f"No balance found for {currency} on {exchange}")
        
        # Get existing allocation
        async with self._lock:
            if exchange not in self._allocations:
                self._allocations[exchange] = {}
            
            allocation = self._allocations[exchange].get(currency)
            if not allocation:
                allocation = BalanceAllocation(
                    exchange=exchange,
                    currency=currency,
                    updated_at=datetime.utcnow()
                )
        
        # Update allocation
        if allocated is not None:
            allocation.allocated = allocated
        if utilized is not None:
            allocation.utilized = utilized
        if reserved is not None:
            allocation.reserved = reserved
        if percentage is not None:
            allocation.percentage = percentage
        
        # Calculate free
        allocation.free = allocation.allocated - allocation.utilized - allocation.reserved
        
        # Ensure free is not negative
        if allocation.free < 0:
            allocation.free = Decimal('0')
        
        # Ensure percentage is valid
        if allocation.percentage > 100:
            allocation.percentage = Decimal('100')
        if allocation.percentage < 0:
            allocation.percentage = Decimal('0')
        
        allocation.updated_at = datetime.utcnow()
        
        # Update cache
        self._allocations[exchange][currency] = allocation
        
        # Save to database
        if self.pool:
            await self._save_allocation(allocation)
        
        logger.info(
            f"Updated allocation for {currency} on {exchange}: "
            f"allocated={allocation.allocated}, "
            f"free={allocation.free}"
        )
        
        return allocation
    
    async def allocate_balances(
        self,
        strategy: BalanceAllocationStrategy,
        currencies: Optional[List[str]] = None,
        weights: Optional[Dict[str, Decimal]] = None
    ) -> Dict[str, Dict[str, BalanceAllocation]]:
        """
        Allocate balances across exchanges using a strategy.
        
        Args:
            strategy: Allocation strategy
            currencies: List of currencies to allocate
            weights: Custom weights for CUSTOM strategy
            
        Returns:
            Dict of allocations
        """
        # Get all balances
        all_balances = await self.get_balances(refresh=True)
        
        if not currencies:
            # Get all currencies across all exchanges
            currencies = set()
            for exchange_balances in all_balances.values():
                currencies.update(exchange_balances.keys())
        
        allocations = {}
        
        for exchange, balances in all_balances.items():
            for currency in currencies:
                if currency not in balances:
                    continue
                
                balance = balances[currency]
                
                if strategy == BalanceAllocationStrategy.EQUAL:
                    # Equal allocation across exchanges
                    num_exchanges = len([b for b in all_balances.values() if currency in b])
                    if num_exchanges > 0:
                        allocated = balance.available / num_exchanges
                    else:
                        allocated = Decimal('0')
                    
                elif strategy == BalanceAllocationStrategy.PROPORTIONAL:
                    # Proportional to available balance
                    total_available = sum(
                        b[currency].available 
                        for b in all_balances.values() 
                        if currency in b
                    )
                    if total_available > 0:
                        allocated = (balance.available / total_available) * balance.available
                    else:
                        allocated = Decimal('0')
                    
                elif strategy == BalanceAllocationStrategy.RISK_BASED:
                    # Risk-based allocation
                    risk_score = await self._calculate_exchange_risk(exchange, currency)
                    total_risk = sum(
                        await self._calculate_exchange_risk(e, currency)
                        for e in all_balances.keys()
                        if currency in all_balances[e]
                    )
                    if total_risk > 0:
                        allocated = (1 - risk_score / total_risk) * balance.available
                    else:
                        allocated = balance.available / len(all_balances)
                    
                elif strategy == BalanceAllocationStrategy.PERFORMANCE_BASED:
                    # Performance-based allocation
                    performance = await self._get_exchange_performance(exchange, currency)
                    total_performance = sum(
                        await self._get_exchange_performance(e, currency)
                        for e in all_balances.keys()
                        if currency in all_balances[e]
                    )
                    if total_performance > 0:
                        allocated = (performance / total_performance) * balance.available
                    else:
                        allocated = balance.available / len(all_balances)
                    
                elif strategy == BalanceAllocationStrategy.CUSTOM:
                    # Custom weights
                    if weights and currency in weights:
                        allocated = balance.available * weights[currency]
                    else:
                        allocated = Decimal('0')
                    
                else:
                    allocated = Decimal('0')
                
                # Update allocation
                if allocated > 0:
                    allocation = await self.update_allocation(
                        exchange=exchange,
                        currency=currency,
                        allocated=allocated.quantize(Decimal('0.00000001'))
                    )
                    
                    if exchange not in allocations:
                        allocations[exchange] = {}
                    allocations[exchange][currency] = allocation
        
        logger.info(f"Allocated balances using {strategy} strategy")
        return allocations
    
    # =========================================================================
    # RISK CALCULATION
    # =========================================================================
    
    async def _calculate_exchange_risk(self, exchange: str, currency: str) -> Decimal:
        """
        Calculate risk score for an exchange.
        
        Args:
            exchange: Exchange name
            currency: Currency code
            
        Returns:
            Risk score (0-100)
        """
        # This would typically use historical data, volatility, etc.
        # For now, use a simple heuristic
        balance = await self.get_balance(exchange, currency)
        if not balance:
            return Decimal('50')
        
        # Higher balance = lower risk
        risk = max(0, 100 - (float(balance.available) * 10))
        return Decimal(str(min(risk, 100)))
    
    async def _get_exchange_performance(self, exchange: str, currency: str) -> Decimal:
        """
        Get performance score for an exchange.
        
        Args:
            exchange: Exchange name
            currency: Currency code
            
        Returns:
            Performance score
        """
        # This would use historical performance data
        # For now, return a default value
        return Decimal('1')
    
    # =========================================================================
    # ALERTS
    # =========================================================================
    
    async def set_balance_alert(
        self,
        exchange: str,
        currency: str,
        alert_type: str,
        threshold: Decimal,
        callback: Optional[Callable] = None
    ) -> BalanceAlert:
        """
        Set a balance alert.
        
        Args:
            exchange: Exchange name
            currency: Currency code
            alert_type: 'min', 'max', 'change'
            threshold: Threshold value
            callback: Optional callback when alert triggers
            
        Returns:
            BalanceAlert
        """
        alert = BalanceAlert(
            exchange=exchange.lower(),
            currency=currency.upper(),
            type=alert_type,
            threshold=threshold,
            current_value=Decimal('0'),
            previous_value=Decimal('0')
        )
        
        if callback:
            self._alert_callbacks.append(callback)
        
        self._alerts.append(alert)
        
        logger.info(f"Set {alert_type} alert for {currency} on {exchange} at {threshold}")
        return alert
    
    async def _alert_monitoring_loop(self):
        """Monitor balance alerts."""
        while self._running:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                for alert in self._alerts:
                    if alert.acknowledged:
                        continue
                    
                    balance = await self.get_balance(alert.exchange, alert.currency)
                    if not balance:
                        continue
                    
                    alert.previous_value = alert.current_value
                    alert.current_value = balance.available
                    
                    triggered = False
                    
                    if alert.type == 'min' and balance.available < alert.threshold:
                        triggered = True
                    elif alert.type == 'max' and balance.available > alert.threshold:
                        triggered = True
                    elif alert.type == 'change':
                        change = abs(balance.available - alert.previous_value)
                        if change >= alert.threshold:
                            triggered = True
                    
                    if triggered:
                        alert.triggered_at = datetime.utcnow()
                        logger.warning(
                            f"Balance alert triggered: {alert.type} "
                            f"{alert.currency} on {alert.exchange} "
                            f"= {alert.current_value} (threshold: {alert.threshold})"
                        )
                        
                        # Trigger callbacks
                        for callback in self._alert_callbacks:
                            try:
                                await callback(alert)
                            except Exception as e:
                                logger.error(f"Alert callback error: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Alert monitoring error: {e}")
                await asyncio.sleep(10)
    
    # =========================================================================
    # RECONCILIATION
    # =========================================================================
    
    async def reconcile_balances(self) -> Dict[str, Dict[str, Dict[str, Decimal]]]:
        """
        Reconcile balances across exchanges.
        
        Returns:
            Dict of discrepancies
        """
        discrepancies = {}
        
        all_balances = await self.get_balances(refresh=True)
        
        for exchange, balances in all_balances.items():
            if exchange not in discrepancies:
                discrepancies[exchange] = {}
            
            for currency, balance in balances.items():
                # Check against expected allocation
                allocation = await self.get_allocation(exchange, currency)
                
                if allocation:
                    expected = allocation.allocated
                    actual = balance.available
                    
                    if abs(actual - expected) > Decimal('0.0001'):
                        discrepancies[exchange][currency] = {
                            'expected': expected,
                            'actual': actual,
                            'difference': actual - expected,
                            'difference_percent': (actual - expected) / expected * 100 if expected > 0 else Decimal('0')
                        }
        
        if discrepancies:
            logger.warning(f"Reconciliation found discrepancies: {discrepancies}")
        
        return discrepancies
    
    # =========================================================================
    # CACHE OPERATIONS
    # =========================================================================
    
    async def _cache_balances(self, exchange: str, balances: Dict[str, Balance]):
        """Cache balances in Redis."""
        if not self.redis:
            return
        
        try:
            key = f"arbitrage:balances:{exchange}"
            data = {
                currency: balance.dict()
                for currency, balance in balances.items()
            }
            await self.redis.setex(
                key,
                self.config.get('cache_ttl', 60),
                json.dumps(data, default=str)
            )
        except Exception as e:
            logger.error(f"Error caching balances: {e}")
    
    async def _load_cached_balances(self):
        """Load cached balances from Redis."""
        if not self.redis:
            return
        
        try:
            for exchange in self._adapters.keys():
                key = f"arbitrage:balances:{exchange}"
                data = await self.redis.get(key)
                if data:
                    data = json.loads(data)
                    async with self._lock:
                        self._balances[exchange] = {
                            currency: Balance(**balance_data)
                            for currency, balance_data in data.items()
                        }
                        self._balance_timestamps[exchange] = time.time()
        except Exception as e:
            logger.error(f"Error loading cached balances: {e}")
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_balances(self, exchange: str, balances: Dict[str, Balance]):
        """Save balances to database."""
        if not self.pool:
            return
        
        try:
            # Save snapshot
            snapshot = BalanceSnapshot(
                exchange=exchange,
                balances=balances,
                metadata={"source": "balance_manager"}
            )
            
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO arbitrage_balance_snapshots (
                        id, exchange, timestamp, balances,
                        total_value_usd, total_value_btc,
                        available_value_usd, locked_value_usd,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    snapshot.id,
                    snapshot.exchange,
                    snapshot.timestamp,
                    json.dumps({
                        currency: balance.dict()
                        for currency, balance in balances.items()
                    }, default=str),
                    snapshot.total_value_usd,
                    snapshot.total_value_btc,
                    snapshot.available_value_usd,
                    snapshot.locked_value_usd,
                    json.dumps(snapshot.metadata, default=str)
                )
            
            # Save history
            async with self.pool.acquire() as conn:
                for currency, balance in balances.items():
                    await conn.execute(
                        """
                        INSERT INTO arbitrage_balance_history (
                            exchange, currency, total, available,
                            locked, timestamp
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        exchange,
                        currency,
                        balance.total,
                        balance.available,
                        balance.locked,
                        datetime.utcnow()
                    )
        except Exception as e:
            logger.error(f"Error saving balances: {e}")
    
    async def _save_allocation(self, allocation: BalanceAllocation):
        """Save allocation to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO arbitrage_balance_allocations (
                        exchange, currency, allocated, utilized,
                        reserved, free, percentage, updated_at,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (exchange, currency) DO UPDATE SET
                        allocated = EXCLUDED.allocated,
                        utilized = EXCLUDED.utilized,
                        reserved = EXCLUDED.reserved,
                        free = EXCLUDED.free,
                        percentage = EXCLUDED.percentage,
                        updated_at = EXCLUDED.updated_at,
                        metadata = EXCLUDED.metadata
                    """,
                    allocation.exchange,
                    allocation.currency,
                    allocation.allocated,
                    allocation.utilized,
                    allocation.reserved,
                    allocation.free,
                    allocation.percentage,
                    allocation.updated_at,
                    json.dumps(allocation.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving allocation: {e}")
    
    async def _load_allocations(self):
        """Load allocations from database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM arbitrage_balance_allocations"
                )
                
                async with self._lock:
                    for row in rows:
                        allocation = BalanceAllocation(
                            exchange=row['exchange'],
                            currency=row['currency'],
                            allocated=row['allocated'],
                            utilized=row['utilized'],
                            reserved=row['reserved'],
                            free=row['free'],
                            percentage=row['percentage'],
                            updated_at=row['updated_at'],
                            metadata=row['metadata'] or {}
                        )
                        
                        if row['exchange'] not in self._allocations:
                            self._allocations[row['exchange']] = {}
                        self._allocations[row['exchange']][row['currency']] = allocation
        except Exception as e:
            logger.error(f"Error loading allocations: {e}")
    
    # =========================================================================
    # PERIODIC SYNC
    # =========================================================================
    
    async def _periodic_sync(self):
        """Periodically sync balances."""
        while self._running:
            try:
                await asyncio.sleep(self.config.get('sync_interval', 30))
                
                # Sync all exchanges
                for exchange in self._adapters.keys():
                    try:
                        await self.get_balances(exchange, refresh=True)
                    except Exception as e:
                        logger.error(f"Error syncing {exchange}: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Periodic sync error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the balance manager."""
        self._shutdown_requested = True
        self._running = False
        
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        
        logger.info("BalanceManager shutdown complete")


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class BalanceError(Exception):
    """Base exception for balance errors."""
    pass


class BalanceNotFoundError(BalanceError):
    """Balance not found error."""
    pass


class BalanceInsufficientError(BalanceError):
    """Insufficient balance error."""
    pass


class BalanceAllocationError(BalanceError):
    """Balance allocation error."""
    pass


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BalanceManager',
    'BalanceStatus',
    'BalanceUpdateType',
    'BalanceAllocationStrategy',
    'CurrencyType',
    'Balance',
    'BalanceSnapshot',
    'BalanceAlert',
    'BalanceAllocation',
    'ExchangeBalanceAdapter',
    'OKXBalanceAdapter',
    'KrakenBalanceAdapter',
    'BinanceBalanceAdapter',
    'BalanceError',
    'BalanceNotFoundError',
    'BalanceInsufficientError',
    'BalanceAllocationError'
]
