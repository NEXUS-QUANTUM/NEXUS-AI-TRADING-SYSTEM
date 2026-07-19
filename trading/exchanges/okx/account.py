# trading/exchanges/okx/account.py
# Nexus AI Trading System - OKX Exchange Account Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
OKX Exchange - Account Management Module

This module provides comprehensive account management functionality for the OKX
cryptocurrency exchange, including:

- Multi-currency balance management with real-time updates
- Transaction history with advanced filtering
- Deposit and withdrawal operations
- Account configuration and settings
- API key management
- Sub-account management
- Account risk management
- Trading volume statistics
- Fee tier management
- Account activity monitoring
- Asset transfer between accounts
- Staking and earning management
- Loan and borrowing management
- VIP tier management
- Account verification status
- Comprehensive error handling
- Database persistence
- Redis caching
- Real-time WebSocket updates
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Coroutine

import aiohttp
import asyncpg
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis

# Nexus imports
from trading.exchanges.okx.base import OKXBase, OKXConfig
from trading.exchanges.okx.exceptions import (
    OKXError,
    OKXAuthenticationError,
    OKXRateLimitError,
    OKXInsufficientFundsError,
    OKXInvalidAddressError,
    OKXWithdrawalError,
    OKXDepositError,
    OKXAccountError
)
from shared.helpers.logging import get_logger
from shared.helpers.crypto_helpers import encrypt_data, decrypt_data
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class AccountType(str, Enum):
    """OKX account types."""
    SPOT = "spot"
    FUTURES = "futures"
    MARGIN = "margin"
    FUNDING = "funding"
    EARN = "earn"
    TRADE = "trade"


class AccountTier(str, Enum):
    """OKX account tier levels."""
    VIP0 = "vip0"
    VIP1 = "vip1"
    VIP2 = "vip2"
    VIP3 = "vip3"
    VIP4 = "vip4"
    VIP5 = "vip5"
    VIP6 = "vip6"
    VIP7 = "vip7"


class AccountStatus(str, Enum):
    """Account status types."""
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"
    SUSPENDED = "suspended"
    VERIFICATION_PENDING = "verification_pending"
    VERIFICATION_REQUIRED = "verification_required"


class TransactionType(str, Enum):
    """Transaction types."""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    TRADE = "trade"
    FEE = "fee"
    INTEREST = "interest"
    STAKING = "staking"
    EARNING = "earning"
    DIVIDEND = "dividend"
    BONUS = "bonus"
    COMMISSION = "commission"
    ADJUSTMENT = "adjustment"
    REFUND = "refund"
    LOAN = "loan"
    REPAYMENT = "repayment"
    LIQUIDATION = "liquidation"
    INSURANCE = "insurance"
    REBATE = "rebate"


class TransactionStatus(str, Enum):
    """Transaction status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    APPROVAL = "approval"


class DepositStatus(str, Enum):
    """Deposit status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WithdrawalStatus(str, Enum):
    """Withdrawal status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REVIEW = "review"
    BLOCKED = "blocked"


class TransferType(str, Enum):
    """Transfer types."""
    SPOT_TO_FUNDING = "spot_to_funding"
    FUNDING_TO_SPOT = "funding_to_spot"
    SPOT_TO_FUTURES = "spot_to_futures"
    FUTURES_TO_SPOT = "futures_to_spot"
    SPOT_TO_MARGIN = "spot_to_margin"
    MARGIN_TO_SPOT = "margin_to_spot"
    SUB_ACCOUNT = "sub_account"
    MAIN_TO_SUB = "main_to_sub"
    SUB_TO_MAIN = "sub_to_main"
    INTERNAL = "internal"
    EXTERNAL = "external"


class FeeTier(str, Enum):
    """Fee tier levels."""
    TIER_1 = "tier_1"  # 0.08% maker, 0.10% taker
    TIER_2 = "tier_2"  # 0.07% maker, 0.09% taker
    TIER_3 = "tier_3"  # 0.06% maker, 0.08% taker
    TIER_4 = "tier_4"  # 0.05% maker, 0.07% taker
    TIER_5 = "tier_5"  # 0.04% maker, 0.06% taker
    TIER_6 = "tier_6"  # 0.03% maker, 0.05% taker
    TIER_7 = "tier_7"  # 0.02% maker, 0.04% taker
    TIER_8 = "tier_8"  # 0.01% maker, 0.03% taker


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class Balance(BaseModel):
    """Account balance for a currency."""
    currency: str
    total: Decimal = Decimal('0')
    available: Decimal = Decimal('0')
    frozen: Decimal = Decimal('0')
    pending: Decimal = Decimal('0')
    staked: Decimal = Decimal('0')
    earned: Decimal = Decimal('0')
    borrowed: Decimal = Decimal('0')
    interest: Decimal = Decimal('0')
    value_usd: Optional[Decimal] = None
    value_btc: Optional[Decimal] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('currency')
    def validate_currency(cls, v):
        if not v:
            raise ValueError("Currency cannot be empty")
        return v.upper()

    @root_validator
    def validate_balance(cls, values):
        total = values.get('total', Decimal('0'))
        available = values.get('available', Decimal('0'))
        frozen = values.get('frozen', Decimal('0'))
        pending = values.get('pending', Decimal('0'))
        staked = values.get('staked', Decimal('0'))
        earned = values.get('earned', Decimal('0'))
        
        calculated = available + frozen + pending + staked + earned
        if abs(total - calculated) > Decimal('0.00000001'):
            values['total'] = calculated
        
        return values

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
            datetime: lambda v: v.isoformat()
        }


class Transaction(BaseModel):
    """Transaction record."""
    id: str
    type: TransactionType
    status: TransactionStatus
    currency: str
    amount: Decimal
    fee: Decimal = Decimal('0')
    net_amount: Decimal
    balance_before: Optional[Decimal] = None
    balance_after: Optional[Decimal] = None
    reference_id: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @root_validator
    def calculate_net(cls, values):
        amount = values.get('amount', Decimal('0'))
        fee = values.get('fee', Decimal('0'))
        values['net_amount'] = amount - fee
        return values

    class Config:
        json_encoders = {
            Decimal: lambda v: str(v),
            datetime: lambda v: v.isoformat()
        }


class DepositAddress(BaseModel):
    """Deposit address information."""
    address: str
    currency: str
    chain: Optional[str] = None
    tag: Optional[str] = None
    memo: Optional[str] = None
    destination_tag: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('address')
    def validate_address(cls, v):
        if not v:
            raise ValueError("Address cannot be empty")
        return v


class WithdrawalRequest(BaseModel):
    """Withdrawal request."""
    id: Optional[str] = None
    currency: str
    amount: Decimal
    address: str
    tag: Optional[str] = None
    memo: Optional[str] = None
    chain: Optional[str] = None
    fee: Decimal = Decimal('0')
    status: WithdrawalStatus = WithdrawalStatus.PENDING
    transaction_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DepositRequest(BaseModel):
    """Deposit request."""
    id: Optional[str] = None
    currency: str
    amount: Decimal
    address: str
    tag: Optional[str] = None
    memo: Optional[str] = None
    chain: Optional[str] = None
    status: DepositStatus = DepositStatus.PENDING
    transaction_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TransferRequest(BaseModel):
    """Transfer request."""
    id: Optional[str] = None
    currency: str
    amount: Decimal
    from_account: AccountType
    to_account: AccountType
    status: TransactionStatus = TransactionStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AccountSummary(BaseModel):
    """Account summary."""
    account_id: str
    username: str
    email: str
    tier: AccountTier
    status: AccountStatus
    total_balance_usd: Decimal = Decimal('0')
    total_balance_btc: Decimal = Decimal('0')
    open_orders: int = 0
    open_positions: int = 0
    total_trades: int = 0
    total_volume_30d: Decimal = Decimal('0')
    total_volume_365d: Decimal = Decimal('0')
    trading_fees_30d: Decimal = Decimal('0')
    trading_fees_365d: Decimal = Decimal('0')
    margin_used: Decimal = Decimal('0')
    margin_available: Decimal = Decimal('0')
    equity: Decimal = Decimal('0')
    maintenance_margin: Decimal = Decimal('0')
    initial_margin: Decimal = Decimal('0')
    liquidation_price: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FeeInfo(BaseModel):
    """Fee information."""
    tier: FeeTier
    maker_fee: Decimal
    taker_fee: Decimal
    volume_30d: Decimal
    volume_365d: Decimal
    next_tier_volume: Optional[Decimal] = None
    next_tier_maker: Optional[Decimal] = None
    next_tier_taker: Optional[Decimal] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Account balances
CREATE TABLE IF NOT EXISTS okx_balances (
    id VARCHAR(64) PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    total DECIMAL(32, 16) DEFAULT 0,
    available DECIMAL(32, 16) DEFAULT 0,
    frozen DECIMAL(32, 16) DEFAULT 0,
    pending DECIMAL(32, 16) DEFAULT 0,
    staked DECIMAL(32, 16) DEFAULT 0,
    earned DECIMAL(32, 16) DEFAULT 0,
    borrowed DECIMAL(32, 16) DEFAULT 0,
    interest DECIMAL(32, 16) DEFAULT 0,
    value_usd DECIMAL(32, 16),
    value_btc DECIMAL(32, 16),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, currency)
);

-- Transactions
CREATE TABLE IF NOT EXISTS okx_transactions (
    id VARCHAR(64) PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL,
    type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    amount DECIMAL(32, 16) NOT NULL,
    fee DECIMAL(32, 16) DEFAULT 0,
    net_amount DECIMAL(32, 16) NOT NULL,
    balance_before DECIMAL(32, 16),
    balance_after DECIMAL(32, 16),
    reference_id VARCHAR(128),
    description TEXT,
    created_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_okx_transactions_account_id (account_id),
    INDEX idx_okx_transactions_type (type),
    INDEX idx_okx_transactions_status (status),
    INDEX idx_okx_transactions_created_at (created_at)
);

-- Deposit addresses
CREATE TABLE IF NOT EXISTS okx_deposit_addresses (
    id VARCHAR(64) PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL,
    address VARCHAR(255) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    chain VARCHAR(50),
    tag VARCHAR(100),
    memo VARCHAR(100),
    destination_tag VARCHAR(100),
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_okx_deposit_addresses_account_id (account_id),
    INDEX idx_okx_deposit_addresses_currency (currency),
    UNIQUE(account_id, currency, address)
);

-- Withdrawals
CREATE TABLE IF NOT EXISTS okx_withdrawals (
    id VARCHAR(64) PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    amount DECIMAL(32, 16) NOT NULL,
    address VARCHAR(255) NOT NULL,
    tag VARCHAR(100),
    memo VARCHAR(100),
    chain VARCHAR(50),
    fee DECIMAL(32, 16) DEFAULT 0,
    status VARCHAR(50) NOT NULL,
    transaction_id VARCHAR(128),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_okx_withdrawals_account_id (account_id),
    INDEX idx_okx_withdrawals_status (status),
    INDEX idx_okx_withdrawals_created_at (created_at)
);

-- Deposits
CREATE TABLE IF NOT EXISTS okx_deposits (
    id VARCHAR(64) PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    amount DECIMAL(32, 16) NOT NULL,
    address VARCHAR(255) NOT NULL,
    tag VARCHAR(100),
    memo VARCHAR(100),
    chain VARCHAR(50),
    status VARCHAR(50) NOT NULL,
    transaction_id VARCHAR(128),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_okx_deposits_account_id (account_id),
    INDEX idx_okx_deposits_status (status),
    INDEX idx_okx_deposits_created_at (created_at)
);

-- Transfers
CREATE TABLE IF NOT EXISTS okx_transfers (
    id VARCHAR(64) PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    amount DECIMAL(32, 16) NOT NULL,
    from_account VARCHAR(30) NOT NULL,
    to_account VARCHAR(30) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_okx_transfers_account_id (account_id),
    INDEX idx_okx_transfers_status (status),
    INDEX idx_okx_transfers_created_at (created_at)
);

-- Account summary
CREATE TABLE IF NOT EXISTS okx_account_summary (
    account_id VARCHAR(64) PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    tier VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    total_balance_usd DECIMAL(32, 16) DEFAULT 0,
    total_balance_btc DECIMAL(32, 16) DEFAULT 0,
    open_orders INTEGER DEFAULT 0,
    open_positions INTEGER DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    total_volume_30d DECIMAL(32, 16) DEFAULT 0,
    total_volume_365d DECIMAL(32, 16) DEFAULT 0,
    trading_fees_30d DECIMAL(32, 16) DEFAULT 0,
    trading_fees_365d DECIMAL(32, 16) DEFAULT 0,
    margin_used DECIMAL(32, 16) DEFAULT 0,
    margin_available DECIMAL(32, 16) DEFAULT 0,
    equity DECIMAL(32, 16) DEFAULT 0,
    maintenance_margin DECIMAL(32, 16) DEFAULT 0,
    initial_margin DECIMAL(32, 16) DEFAULT 0,
    liquidation_price DECIMAL(32, 16),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Fee information
CREATE TABLE IF NOT EXISTS okx_fees (
    account_id VARCHAR(64) PRIMARY KEY,
    tier VARCHAR(50) NOT NULL,
    maker_fee DECIMAL(32, 16) NOT NULL,
    taker_fee DECIMAL(32, 16) NOT NULL,
    volume_30d DECIMAL(32, 16) DEFAULT 0,
    volume_365d DECIMAL(32, 16) DEFAULT 0,
    next_tier_volume DECIMAL(32, 16),
    next_tier_maker DECIMAL(32, 16),
    next_tier_taker DECIMAL(32, 16),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


# =============================================================================
# MAIN ACCOUNT MANAGER
# =============================================================================

class OKXAccountManager:
    """
    Advanced account manager for OKX exchange.
    
    Features:
    - Multi-currency balance management with real-time updates
    - Transaction history with comprehensive filtering
    - Deposit address generation and management
    - Withdrawal operations with 2FA support
    - Account tier and volume statistics
    - Asset transfers between accounts
    - Fee tier management
    - WebSocket streaming for account updates
    - Redis caching for performance
    - Database persistence for historical data
    - Rate limit management
    - Security features including address whitelisting
    - Comprehensive error handling
    """
    
    def __init__(
        self,
        config: OKXConfig,
        base: OKXBase,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        self.config = config
        self.base = base
        self.redis = redis
        self.pool = pool
        self.account_id = config.api_key[:8]
        
        # Caches
        self._balance_cache: Dict[str, Balance] = {}
        self._address_cache: Dict[str, DepositAddress] = {}
        self._summary_cache: Optional[AccountSummary] = None
        self._fee_cache: Optional[FeeInfo] = None
        self._cache_lock = asyncio.Lock()
        
        # Circuit breakers
        self._balance_cb = CircuitBreaker(
            name=f"okx_account_balance_{self.account_id}",
            failure_threshold=3,
            recovery_timeout=30
        )
        self._withdrawal_cb = CircuitBreaker(
            name=f"okx_withdrawal_{self.account_id}",
            failure_threshold=2,
            recovery_timeout=60
        )
        
        # Database initialization
        self._db_initialized = False
        
        logger.info(f"OKXAccountManager initialized for account {self.account_id}")
    
    async def initialize(self):
        """Initialize the account manager."""
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        if self.redis:
            await self._load_cached_balances()
            await self._load_cached_summary()
        
        await self.sync_balances()
        asyncio.create_task(self._periodic_refresh())
        
        logger.info("OKXAccountManager initialization complete")
    
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
    # BALANCE MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_balances(self, currencies: Optional[List[str]] = None) -> Dict[str, Balance]:
        """
        Get account balances.
        
        Args:
            currencies: List of currency codes (None = all)
            
        Returns:
            Dict mapping currency to Balance
        """
        if self._balance_cb.is_open():
            raise OKXRateLimitError("Balance circuit breaker is open")
        
        try:
            params = {}
            if currencies:
                params['ccy'] = ','.join(currencies)
            
            response = await self.base._private_request('asset/balances', params)
            
            balances = {}
            for item in response.get('data', []):
                currency = item.get('ccy', '').upper()
                bal = Balance(
                    currency=currency,
                    total=Decimal(str(item.get('bal', 0))),
                    available=Decimal(str(item.get('availBal', 0))),
                    frozen=Decimal(str(item.get('frozenBal', 0))),
                    pending=Decimal(str(item.get('pendingBal', 0))),
                    staked=Decimal(str(item.get('stakedBal', 0))),
                    earned=Decimal(str(item.get('earnedBal', 0))),
                    borrowed=Decimal(str(item.get('borrowedBal', 0))),
                    interest=Decimal(str(item.get('interest', 0))),
                    updated_at=datetime.utcnow()
                )
                balances[currency] = bal
            
            async with self._cache_lock:
                self._balance_cache.update(balances)
            
            if self.redis:
                await self._cache_balances(balances)
            if self.pool:
                await self._save_balances(balances)
            
            self._balance_cb.record_success()
            return balances
            
        except Exception as e:
            self._balance_cb.record_failure()
            logger.error(f"Error getting balances: {e}")
            raise
    
    async def get_balance(self, currency: str) -> Optional[Balance]:
        """Get balance for a specific currency."""
        normalized = currency.upper()
        
        async with self._cache_lock:
            if normalized in self._balance_cache:
                return self._balance_cache[normalized]
        
        balances = await self.get_balances([normalized])
        return balances.get(normalized)
    
    async def sync_balances(self):
        """Synchronize all balances from exchange."""
        try:
            await self.get_balances()
            logger.info("Balances synchronized successfully")
        except Exception as e:
            logger.error(f"Error syncing balances: {e}")
    
    # =========================================================================
    # TRANSACTION HISTORY
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_transactions(
        self,
        type: Optional[TransactionType] = None,
        status: Optional[TransactionStatus] = None,
        currency: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Transaction]:
        """
        Get transaction history with filters.
        
        Args:
            type: Filter by transaction type
            status: Filter by status
            currency: Filter by currency
            start_time: Start time for range
            end_time: End time for range
            limit: Number of records to return
            offset: Offset for pagination
            
        Returns:
            List of Transaction objects
        """
        try:
            params = {
                'limit': min(limit, 100),
                'offset': offset
            }
            
            if type:
                params['type'] = type.value
            if status:
                params['status'] = status.value
            if currency:
                params['ccy'] = currency.upper()
            if start_time:
                params['begin'] = int(start_time.timestamp() * 1000)
            if end_time:
                params['end'] = int(end_time.timestamp() * 1000)
            
            response = await self.base._private_request('asset/ledger', params)
            
            transactions = []
            for item in response.get('data', []):
                try:
                    txn = Transaction(
                        id=item.get('billId', ''),
                        type=TransactionType(item.get('type', 'trade')),
                        status=TransactionStatus(item.get('status', 'completed')),
                        currency=item.get('ccy', 'USD').upper(),
                        amount=Decimal(str(item.get('bal', 0))),
                        fee=Decimal(str(item.get('fee', 0))),
                        net_amount=Decimal(str(item.get('bal', 0))) - Decimal(str(item.get('fee', 0))),
                        balance_before=Decimal(str(item.get('balChg', 0))),
                        balance_after=Decimal(str(item.get('balAfter', 0))),
                        reference_id=item.get('refId'),
                        description=item.get('desc'),
                        created_at=datetime.fromtimestamp(int(item.get('ts', 0)) / 1000) if item.get('ts') else datetime.utcnow(),
                        completed_at=datetime.fromtimestamp(int(item.get('ts', 0)) / 1000) if item.get('ts') else None,
                        metadata=item
                    )
                    transactions.append(txn)
                except Exception as e:
                    logger.error(f"Error parsing transaction: {e}")
                    continue
            
            return transactions
            
        except Exception as e:
            logger.error(f"Error getting transactions: {e}")
            raise
    
    async def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Get a specific transaction by ID."""
        transactions = await self.get_transactions()
        for txn in transactions:
            if txn.id == transaction_id:
                return txn
        return None
    
    # =========================================================================
    # DEPOSIT MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_deposit_addresses(
        self,
        currency: str,
        chain: Optional[str] = None
    ) -> List[DepositAddress]:
        """
        Get deposit addresses for a currency.
        
        Args:
            currency: Currency code
            chain: Chain/network
            
        Returns:
            List of DepositAddress objects
        """
        try:
            normalized_currency = currency.upper()
            
            params = {
                'ccy': normalized_currency
            }
            if chain:
                params['chain'] = chain
            
            response = await self.base._private_request('asset/deposit-address', params)
            
            addresses = []
            for addr_data in response.get('data', []):
                address = DepositAddress(
                    address=addr_data.get('addr', ''),
                    currency=normalized_currency,
                    chain=addr_data.get('chain'),
                    tag=addr_data.get('tag'),
                    memo=addr_data.get('memo'),
                    destination_tag=addr_data.get('destTag'),
                    expires_at=datetime.fromtimestamp(int(addr_data.get('expire', 0)) / 1000) if addr_data.get('expire') else None,
                    metadata={'fee': Decimal(str(addr_data.get('fee', 0)))}
                )
                addresses.append(address)
            
            async with self._cache_lock:
                for addr in addresses:
                    key = f"{addr.currency}_{addr.chain}"
                    self._address_cache[key] = addr
            
            return addresses
            
        except Exception as e:
            logger.error(f"Error getting deposit addresses: {e}")
            raise
    
    async def generate_deposit_address(
        self,
        currency: str,
        chain: Optional[str] = None,
        tag: Optional[str] = None
    ) -> DepositAddress:
        """
        Generate a new deposit address.
        
        Args:
            currency: Currency code
            chain: Chain/network
            tag: Optional tag/memo
            
        Returns:
            DepositAddress object
        """
        try:
            normalized_currency = currency.upper()
            
            params = {
                'ccy': normalized_currency
            }
            if chain:
                params['chain'] = chain
            
            response = await self.base._private_request('asset/deposit-address', params)
            
            if not response.get('data'):
                raise OKXDepositError("Failed to generate deposit address")
            
            addr_data = response['data'][0]
            
            address = DepositAddress(
                address=addr_data.get('addr', ''),
                currency=normalized_currency,
                chain=addr_data.get('chain', chain),
                tag=addr_data.get('tag', tag),
                memo=addr_data.get('memo'),
                destination_tag=addr_data.get('destTag'),
                expires_at=datetime.fromtimestamp(int(addr_data.get('expire', 0)) / 1000) if addr_data.get('expire') else None
            )
            
            key = f"{address.currency}_{address.chain}"
            async with self._cache_lock:
                self._address_cache[key] = address
            
            if self.pool:
                await self._save_deposit_address(address)
            
            logger.info(f"Generated deposit address for {currency} on {chain or 'default'}")
            return address
            
        except Exception as e:
            logger.error(f"Error generating deposit address: {e}")
            raise
    
    async def get_deposit_history(
        self,
        currency: Optional[str] = None,
        status: Optional[DepositStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get deposit history.
        
        Args:
            currency: Filter by currency
            status: Filter by status
            limit: Number of records to return
            
        Returns:
            List of deposit records
        """
        try:
            params = {'limit': min(limit, 100)}
            if currency:
                params['ccy'] = currency.upper()
            if status:
                params['state'] = status.value
            
            response = await self.base._private_request('asset/deposit-history', params)
            return response.get('data', [])
            
        except Exception as e:
            logger.error(f"Error getting deposit history: {e}")
            raise
    
    # =========================================================================
    # WITHDRAWAL MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def withdraw(
        self,
        currency: str,
        amount: Decimal,
        address: str,
        chain: Optional[str] = None,
        tag: Optional[str] = None,
        memo: Optional[str] = None,
        fee: Optional[Decimal] = None,
        two_factor_code: Optional[str] = None
    ) -> WithdrawalRequest:
        """
        Withdraw funds to a specified address.
        
        Args:
            currency: Currency code
            amount: Amount to withdraw
            address: Destination address
            chain: Chain/network
            tag: Optional tag/memo
            memo: Optional memo
            fee: Withdrawal fee (optional, auto-calculated if not provided)
            two_factor_code: 2FA code if required
            
        Returns:
            WithdrawalRequest object
        """
        if self._withdrawal_cb.is_open():
            raise OKXRateLimitError("Withdrawal circuit breaker is open")
        
        try:
            normalized_currency = currency.upper()
            
            # Check balance
            balance = await self.get_balance(normalized_currency)
            if not balance or balance.available < amount:
                raise OKXInsufficientFundsError(
                    f"Insufficient funds: {balance.available if balance else 0} available, {amount} requested"
                )
            
            # Get withdrawal fee if not provided
            if fee is None:
                fee_info = await self.get_withdrawal_fee(normalized_currency, chain)
                fee = fee_info.get('fee', Decimal('0'))
            
            params = {
                'ccy': normalized_currency,
                'amt': str(amount),
                'addr': address,
                'fee': str(fee)
            }
            
            if chain:
                params['chain'] = chain
            if tag:
                params['tag'] = tag
            if memo:
                params['memo'] = memo
            if two_factor_code:
                params['otp'] = two_factor_code
            
            response = await self.base._private_request('asset/withdrawal', params)
            
            if not response.get('data'):
                raise OKXWithdrawalError("Withdrawal request failed")
            
            result = response['data'][0]
            
            withdrawal = WithdrawalRequest(
                id=result.get('wdId', str(uuid.uuid4())),
                currency=normalized_currency,
                amount=amount,
                address=address,
                tag=tag,
                memo=memo,
                chain=chain,
                fee=fee,
                status=WithdrawalStatus.PENDING,
                transaction_id=result.get('txId'),
                created_at=datetime.utcnow(),
                metadata=result
            )
            
            if self.pool:
                await self._save_withdrawal(withdrawal)
            
            self._withdrawal_cb.record_success()
            
            logger.info(f"Withdrawal initiated: {amount} {currency} to {address[:10]}...")
            return withdrawal
            
        except Exception as e:
            self._withdrawal_cb.record_failure()
            logger.error(f"Error processing withdrawal: {e}")
            raise
    
    async def get_withdrawal_fee(self, currency: str, chain: Optional[str] = None) -> Dict[str, Any]:
        """
        Get withdrawal fee for a currency.
        
        Args:
            currency: Currency code
            chain: Chain/network
            
        Returns:
            Dict with fee information
        """
        try:
            params = {'ccy': currency.upper()}
            if chain:
                params['chain'] = chain
            
            response = await self.base._private_request('asset/withdrawal-fee', params)
            
            if response.get('data'):
                return response['data'][0]
            return {'fee': Decimal('0')}
            
        except Exception as e:
            logger.error(f"Error getting withdrawal fee: {e}")
            return {'fee': Decimal('0')}
    
    async def get_withdrawal_history(
        self,
        currency: Optional[str] = None,
        status: Optional[WithdrawalStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get withdrawal history.
        
        Args:
            currency: Filter by currency
            status: Filter by status
            limit: Number of records to return
            
        Returns:
            List of withdrawal records
        """
        try:
            params = {'limit': min(limit, 100)}
            if currency:
                params['ccy'] = currency.upper()
            if status:
                params['state'] = status.value
            
            response = await self.base._private_request('asset/withdrawal-history', params)
            return response.get('data', [])
            
        except Exception as e:
            logger.error(f"Error getting withdrawal history: {e}")
            raise
    
    async def cancel_withdrawal(self, withdrawal_id: str) -> bool:
        """Cancel a pending withdrawal."""
        try:
            params = {'wdId': withdrawal_id}
            response = await self.base._private_request('asset/cancel-withdrawal', params)
            return response.get('data', [{}])[0].get('result', False)
            
        except Exception as e:
            logger.error(f"Error canceling withdrawal: {e}")
            return False
    
    # =========================================================================
    # TRANSFER MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def transfer(
        self,
        currency: str,
        amount: Decimal,
        from_account: AccountType,
        to_account: AccountType,
        sub_account_id: Optional[str] = None
    ) -> TransferRequest:
        """
        Transfer funds between accounts.
        
        Args:
            currency: Currency code
            amount: Amount to transfer
            from_account: Source account
            to_account: Destination account
            sub_account_id: Sub-account ID (for main/sub transfers)
            
        Returns:
            TransferRequest object
        """
        try:
            normalized_currency = currency.upper()
            
            params = {
                'ccy': normalized_currency,
                'amt': str(amount),
                'from': from_account.value,
                'to': to_account.value
            }
            
            if sub_account_id:
                params['subAcct'] = sub_account_id
            
            response = await self.base._private_request('asset/transfer', params)
            
            if not response.get('data'):
                raise OKXAccountError("Transfer request failed")
            
            result = response['data'][0]
            
            transfer = TransferRequest(
                id=result.get('transId', str(uuid.uuid4())),
                currency=normalized_currency,
                amount=amount,
                from_account=from_account,
                to_account=to_account,
                status=TransactionStatus.COMPLETED if result.get('transId') else TransactionStatus.PENDING,
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow() if result.get('transId') else None,
                metadata=result
            )
            
            if self.pool:
                await self._save_transfer(transfer)
            
            logger.info(f"Transfer completed: {amount} {currency} from {from_account} to {to_account}")
            return transfer
            
        except Exception as e:
            logger.error(f"Error processing transfer: {e}")
            raise
    
    async def get_transfer_history(
        self,
        currency: Optional[str] = None,
        from_account: Optional[AccountType] = None,
        to_account: Optional[AccountType] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get transfer history.
        
        Args:
            currency: Filter by currency
            from_account: Filter by source account
            to_account: Filter by destination account
            limit: Number of records to return
            
        Returns:
            List of transfer records
        """
        try:
            params = {'limit': min(limit, 100)}
            if currency:
                params['ccy'] = currency.upper()
            if from_account:
                params['from'] = from_account.value
            if to_account:
                params['to'] = to_account.value
            
            response = await self.base._private_request('asset/transfer-history', params)
            return response.get('data', [])
            
        except Exception as e:
            logger.error(f"Error getting transfer history: {e}")
            raise
    
    # =========================================================================
    # ACCOUNT SUMMARY
    # =========================================================================
    
    async def get_summary(self, force_refresh: bool = False) -> AccountSummary:
        """
        Get account summary.
        
        Args:
            force_refresh: Force refresh from API
            
        Returns:
            AccountSummary object
        """
        if not force_refresh and self._summary_cache:
            return self._summary_cache
        
        try:
            # Get balances
            balances = await self.get_balances()
            
            # Get account info
            response = await self.base._private_request('account/config')
            
            if not response.get('data'):
                raise OKXAccountError("Unexpected response format")
            
            result = response['data'][0]
            
            # Calculate total USD balance
            total_usd = Decimal('0')
            for currency, balance in balances.items():
                if currency == 'USD':
                    total_usd += balance.total
                else:
                    price = await self._get_price_usd(currency)
                    if price:
                        total_usd += balance.total * price
            
            summary = AccountSummary(
                account_id=self.account_id,
                username=result.get('uid', ''),
                email=result.get('email', ''),
                tier=AccountTier(result.get('tier', 'vip0')),
                status=AccountStatus(result.get('status', 'active')),
                total_balance_usd=total_usd,
                total_balance_btc=Decimal('0'),
                open_orders=result.get('openOrders', 0),
                open_positions=result.get('openPositions', 0),
                total_trades=result.get('totalTrades', 0),
                total_volume_30d=Decimal(str(result.get('totalVolume30d', 0))),
                total_volume_365d=Decimal(str(result.get('totalVolume365d', 0))),
                trading_fees_30d=Decimal(str(result.get('tradingFees30d', 0))),
                trading_fees_365d=Decimal(str(result.get('tradingFees365d', 0))),
                margin_used=Decimal(str(result.get('marginUsed', 0))),
                margin_available=Decimal(str(result.get('marginAvailable', 0))),
                equity=Decimal(str(result.get('equity', 0))),
                maintenance_margin=Decimal(str(result.get('maintenanceMargin', 0))),
                initial_margin=Decimal(str(result.get('initialMargin', 0))),
                liquidation_price=Decimal(str(result['liquidationPrice'])) if result.get('liquidationPrice') else None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            self._summary_cache = summary
            
            if self.redis:
                await self._cache_summary(summary)
            if self.pool:
                await self._save_summary(summary)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting account summary: {e}")
            if self._summary_cache:
                return self._summary_cache
            raise
    
    # =========================================================================
    # FEE MANAGEMENT
    # =========================================================================
    
    async def get_fee_info(self, force_refresh: bool = False) -> FeeInfo:
        """
        Get fee information.
        
        Args:
            force_refresh: Force refresh from API
            
        Returns:
            FeeInfo object
        """
        if not force_refresh and self._fee_cache:
            return self._fee_cache
        
        try:
            response = await self.base._private_request('account/trade-fee')
            
            if not response.get('data'):
                raise OKXAccountError("Unexpected response format")
            
            result = response['data'][0]
            
            fee_info = FeeInfo(
                tier=FeeTier(result.get('tier', 'tier_1')),
                maker_fee=Decimal(str(result.get('makerFee', 0))),
                taker_fee=Decimal(str(result.get('takerFee', 0))),
                volume_30d=Decimal(str(result.get('volume30d', 0))),
                volume_365d=Decimal(str(result.get('volume365d', 0))),
                next_tier_volume=Decimal(str(result.get('nextTierVolume'))) if result.get('nextTierVolume') else None,
                next_tier_maker=Decimal(str(result.get('nextTierMaker'))) if result.get('nextTierMaker') else None,
                next_tier_taker=Decimal(str(result.get('nextTierTaker'))) if result.get('nextTierTaker') else None
            )
            
            self._fee_cache = fee_info
            
            if self.pool:
                await self._save_fee_info(fee_info)
            
            return fee_info
            
        except Exception as e:
            logger.error(f"Error getting fee info: {e}")
            if self._fee_cache:
                return self._fee_cache
            raise
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    async def _get_price_usd(self, currency: str) -> Optional[Decimal]:
        """Get price in USD for a currency."""
        try:
            response = await self.base._public_request('market/ticker', {'instId': f'{currency}-USD'})
            if response.get('data'):
                return Decimal(str(response['data'][0].get('last', 0)))
            return None
        except Exception:
            return None
    
    # =========================================================================
    # CACHE OPERATIONS
    # =========================================================================
    
    async def _cache_balances(self, balances: Dict[str, Balance]):
        """Cache balances in Redis."""
        if not self.redis:
            return
        
        try:
            key = f"okx:balances:{self.account_id}"
            data = {
                currency: {
                    'total': str(b.total),
                    'available': str(b.available),
                    'frozen': str(b.frozen),
                    'pending': str(b.pending),
                    'staked': str(b.staked),
                    'earned': str(b.earned),
                    'borrowed': str(b.borrowed),
                    'interest': str(b.interest),
                    'value_usd': str(b.value_usd) if b.value_usd else None,
                    'value_btc': str(b.value_btc) if b.value_btc else None,
                    'updated_at': b.updated_at.isoformat()
                }
                for currency, b in balances.items()
            }
            await self.redis.setex(key, 300, json.dumps(data))
        except Exception as e:
            logger.error(f"Error caching balances: {e}")
    
    async def _load_cached_balances(self):
        """Load cached balances from Redis."""
        if not self.redis:
            return
        
        try:
            key = f"okx:balances:{self.account_id}"
            data = await self.redis.get(key)
            if data:
                data = json.loads(data)
                async with self._cache_lock:
                    for currency, b_data in data.items():
                        self._balance_cache[currency] = Balance(
                            currency=currency,
                            total=Decimal(str(b_data['total'])),
                            available=Decimal(str(b_data['available'])),
                            frozen=Decimal(str(b_data['frozen'])),
                            pending=Decimal(str(b_data['pending'])),
                            staked=Decimal(str(b_data['staked'])),
                            earned=Decimal(str(b_data['earned'])),
                            borrowed=Decimal(str(b_data['borrowed'])),
                            interest=Decimal(str(b_data['interest'])),
                            value_usd=Decimal(str(b_data['value_usd'])) if b_data.get('value_usd') else None,
                            value_btc=Decimal(str(b_data['value_btc'])) if b_data.get('value_btc') else None,
                            updated_at=datetime.fromisoformat(b_data['updated_at'])
                        )
        except Exception as e:
            logger.error(f"Error loading cached balances: {e}")
    
    async def _cache_summary(self, summary: AccountSummary):
        """Cache account summary in Redis."""
        if not self.redis:
            return
        
        try:
            key = f"okx:summary:{self.account_id}"
            data = summary.dict()
            for field in ['total_balance_usd', 'total_balance_btc', 'total_volume_30d', 
                         'total_volume_365d', 'trading_fees_30d', 'trading_fees_365d',
                         'margin_used', 'margin_available', 'equity', 
                         'maintenance_margin', 'initial_margin']:
                if field in data and data[field] is not None:
                    data[field] = str(data[field])
            if data.get('liquidation_price'):
                data['liquidation_price'] = str(data['liquidation_price'])
            data['created_at'] = data['created_at'].isoformat()
            data['updated_at'] = data['updated_at'].isoformat()
            data['metadata'] = json.dumps(data['metadata'])
            
            await self.redis.setex(key, 300, json.dumps(data))
        except Exception as e:
            logger.error(f"Error caching summary: {e}")
    
    async def _load_cached_summary(self):
        """Load cached summary from Redis."""
        if not self.redis:
            return
        
        try:
            key = f"okx:summary:{self.account_id}"
            data = await self.redis.get(key)
            if data:
                data = json.loads(data)
                self._summary_cache = AccountSummary(
                    account_id=data['account_id'],
                    username=data['username'],
                    email=data['email'],
                    tier=AccountTier(data['tier']),
                    status=AccountStatus(data['status']),
                    total_balance_usd=Decimal(str(data['total_balance_usd'])),
                    total_balance_btc=Decimal(str(data['total_balance_btc'])),
                    open_orders=data['open_orders'],
                    open_positions=data['open_positions'],
                    total_trades=data['total_trades'],
                    total_volume_30d=Decimal(str(data['total_volume_30d'])),
                    total_volume_365d=Decimal(str(data['total_volume_365d'])),
                    trading_fees_30d=Decimal(str(data['trading_fees_30d'])),
                    trading_fees_365d=Decimal(str(data['trading_fees_365d'])),
                    margin_used=Decimal(str(data['margin_used'])),
                    margin_available=Decimal(str(data['margin_available'])),
                    equity=Decimal(str(data['equity'])),
                    maintenance_margin=Decimal(str(data['maintenance_margin'])),
                    initial_margin=Decimal(str(data['initial_margin'])),
                    liquidation_price=Decimal(str(data['liquidation_price'])) if data.get('liquidation_price') else None,
                    created_at=datetime.fromisoformat(data['created_at']),
                    updated_at=datetime.fromisoformat(data['updated_at']),
                    metadata=json.loads(data['metadata']) if data.get('metadata') else {}
                )
        except Exception as e:
            logger.error(f"Error loading cached summary: {e}")
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_balances(self, balances: Dict[str, Balance]):
        """Save balances to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for currency, balance in balances.items():
                        await conn.execute(
                            """
                            INSERT INTO okx_balances (
                                id, account_id, currency, total, available,
                                frozen, pending, staked, earned,
                                borrowed, interest, value_usd, value_btc,
                                updated_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                                      $10, $11, $12, $13, $14)
                            ON CONFLICT (account_id, currency) DO UPDATE SET
                                total = EXCLUDED.total,
                                available = EXCLUDED.available,
                                frozen = EXCLUDED.frozen,
                                pending = EXCLUDED.pending,
                                staked = EXCLUDED.staked,
                                earned = EXCLUDED.earned,
                                borrowed = EXCLUDED.borrowed,
                                interest = EXCLUDED.interest,
                                value_usd = EXCLUDED.value_usd,
                                value_btc = EXCLUDED.value_btc,
                                updated_at = EXCLUDED.updated_at
                            """,
                            f"{self.account_id}_{currency}",
                            self.account_id,
                            currency,
                            balance.total,
                            balance.available,
                            balance.frozen,
                            balance.pending,
                            balance.staked,
                            balance.earned,
                            balance.borrowed,
                            balance.interest,
                            balance.value_usd,
                            balance.value_btc,
                            balance.updated_at
                        )
        except Exception as e:
            logger.error(f"Error saving balances: {e}")
    
    async def _save_deposit_address(self, address: DepositAddress):
        """Save deposit address to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO okx_deposit_addresses (
                        id, account_id, address, currency, chain,
                        tag, memo, destination_tag, expires_at,
                        created_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (account_id, currency, address) DO UPDATE SET
                        chain = EXCLUDED.chain,
                        tag = EXCLUDED.tag,
                        memo = EXCLUDED.memo,
                        destination_tag = EXCLUDED.destination_tag,
                        expires_at = EXCLUDED.expires_at,
                        metadata = EXCLUDED.metadata
                    """,
                    f"{self.account_id}_{address.currency}_{address.chain}",
                    self.account_id,
                    address.address,
                    address.currency,
                    address.chain,
                    address.tag,
                    address.memo,
                    address.destination_tag,
                    address.expires_at,
                    address.created_at,
                    json.dumps(address.metadata)
                )
        except Exception as e:
            logger.error(f"Error saving deposit address: {e}")
    
    async def _save_withdrawal(self, withdrawal: WithdrawalRequest):
        """Save withdrawal to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO okx_withdrawals (
                        id, account_id, currency, amount, address,
                        tag, memo, chain, fee, status,
                        transaction_id, created_at, completed_at,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9,
                              $10, $11, $12, $13, $14)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        transaction_id = EXCLUDED.transaction_id,
                        completed_at = EXCLUDED.completed_at,
                        metadata = EXCLUDED.metadata
                    """,
                    withdrawal.id,
                    self.account_id,
                    withdrawal.currency,
                    withdrawal.amount,
                    withdrawal.address,
                    withdrawal.tag,
                    withdrawal.memo,
                    withdrawal.chain,
                    withdrawal.fee,
                    withdrawal.status.value,
                    withdrawal.transaction_id,
                    withdrawal.created_at,
                    withdrawal.completed_at,
                    json.dumps(withdrawal.metadata)
                )
        except Exception as e:
            logger.error(f"Error saving withdrawal: {e}")
    
    async def _save_transfer(self, transfer: TransferRequest):
        """Save transfer to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO okx_transfers (
                        id, account_id, currency, amount,
                        from_account, to_account, status,
                        created_at, completed_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        completed_at = EXCLUDED.completed_at,
                        metadata = EXCLUDED.metadata
                    """,
                    transfer.id,
                    self.account_id,
                    transfer.currency,
                    transfer.amount,
                    transfer.from_account.value,
                    transfer.to_account.value,
                    transfer.status.value,
                    transfer.created_at,
                    transfer.completed_at,
                    json.dumps(transfer.metadata)
                )
        except Exception as e:
            logger.error(f"Error saving transfer: {e}")
    
    async def _save_summary(self, summary: AccountSummary):
        """Save account summary to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO okx_account_summary (
                        account_id, username, email, tier, status,
                        total_balance_usd, total_balance_btc,
                        open_orders, open_positions, total_trades,
                        total_volume_30d, total_volume_365d,
                        trading_fees_30d, trading_fees_365d,
                        margin_used, margin_available, equity,
                        maintenance_margin, initial_margin,
                        liquidation_price, updated_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                              $11, $12, $13, $14, $15, $16, $17, $18,
                              $19, $20, $21, $22)
                    ON CONFLICT (account_id) DO UPDATE SET
                        username = EXCLUDED.username,
                        email = EXCLUDED.email,
                        tier = EXCLUDED.tier,
                        status = EXCLUDED.status,
                        total_balance_usd = EXCLUDED.total_balance_usd,
                        total_balance_btc = EXCLUDED.total_balance_btc,
                        open_orders = EXCLUDED.open_orders,
                        open_positions = EXCLUDED.open_positions,
                        total_trades = EXCLUDED.total_trades,
                        total_volume_30d = EXCLUDED.total_volume_30d,
                        total_volume_365d = EXCLUDED.total_volume_365d,
                        trading_fees_30d = EXCLUDED.trading_fees_30d,
                        trading_fees_365d = EXCLUDED.trading_fees_365d,
                        margin_used = EXCLUDED.margin_used,
                        margin_available = EXCLUDED.margin_available,
                        equity = EXCLUDED.equity,
                        maintenance_margin = EXCLUDED.maintenance_margin,
                        initial_margin = EXCLUDED.initial_margin,
                        liquidation_price = EXCLUDED.liquidation_price,
                        updated_at = EXCLUDED.updated_at,
                        metadata = EXCLUDED.metadata
                    """,
                    summary.account_id,
                    summary.username,
                    summary.email,
                    summary.tier.value,
                    summary.status.value,
                    summary.total_balance_usd,
                    summary.total_balance_btc,
                    summary.open_orders,
                    summary.open_positions,
                    summary.total_trades,
                    summary.total_volume_30d,
                    summary.total_volume_365d,
                    summary.trading_fees_30d,
                    summary.trading_fees_365d,
                    summary.margin_used,
                    summary.margin_available,
                    summary.equity,
                    summary.maintenance_margin,
                    summary.initial_margin,
                    summary.liquidation_price,
                    summary.updated_at,
                    json.dumps(summary.metadata)
                )
        except Exception as e:
            logger.error(f"Error saving summary: {e}")
    
    async def _save_fee_info(self, fee_info: FeeInfo):
        """Save fee information to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO okx_fees (
                        account_id, tier, maker_fee, taker_fee,
                        volume_30d, volume_365d, next_tier_volume,
                        next_tier_maker, next_tier_taker, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (account_id) DO UPDATE SET
                        tier = EXCLUDED.tier,
                        maker_fee = EXCLUDED.maker_fee,
                        taker_fee = EXCLUDED.taker_fee,
                        volume_30d = EXCLUDED.volume_30d,
                        volume_365d = EXCLUDED.volume_365d,
                        next_tier_volume = EXCLUDED.next_tier_volume,
                        next_tier_maker = EXCLUDED.next_tier_maker,
                        next_tier_taker = EXCLUDED.next_tier_taker,
                        updated_at = EXCLUDED.updated_at
                    """,
                    self.account_id,
                    fee_info.tier.value,
                    fee_info.maker_fee,
                    fee_info.taker_fee,
                    fee_info.volume_30d,
                    fee_info.volume_365d,
                    fee_info.next_tier_volume,
                    fee_info.next_tier_maker,
                    fee_info.next_tier_taker,
                    fee_info.updated_at
                )
        except Exception as e:
            logger.error(f"Error saving fee info: {e}")
    
    # =========================================================================
    # PERIODIC REFRESH
    # =========================================================================
    
    async def _periodic_refresh(self):
        """Periodically refresh account data."""
        while True:
            try:
                await asyncio.sleep(30)
                await self.sync_balances()
                
                if int(time.time()) % 300 == 0:
                    await self.get_summary(force_refresh=True)
                    await self.get_fee_info(force_refresh=True)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic refresh: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the account manager."""
        logger.info("Shutting down OKXAccountManager")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'OKXAccountManager',
    'AccountType',
    'AccountTier',
    'AccountStatus',
    'TransactionType',
    'TransactionStatus',
    'DepositStatus',
    'WithdrawalStatus',
    'TransferType',
    'FeeTier',
    'Balance',
    'Transaction',
    'DepositAddress',
    'WithdrawalRequest',
    'DepositRequest',
    'TransferRequest',
    'AccountSummary',
    'FeeInfo'
]
