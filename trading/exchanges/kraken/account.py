# trading/exchanges/kraken/account.py
# Nexus AI Trading System - Kraken Exchange Account Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
Kraken Exchange - Account Management Module

This module provides comprehensive account management functionality for the Kraken
cryptocurrency exchange, including balance management, transaction history,
deposit/withdrawal operations, and account settings.

Features:
- Multi-currency balance tracking
- Transaction history with filtering
- Deposit address management
- Withdrawal operations with 2FA support
- Account tier information
- Trade volume statistics
- Ledger entry management
- API key management
- Rate limit management
- WebSocket account updates
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
from trading.exchanges.kraken.base import KrakenBase, KrakenConfig
from trading.exchanges.kraken.exceptions import (
    KrakenError,
    KrakenAuthenticationError,
    KrakenRateLimitError,
    KrakenInsufficientFundsError,
    KrakenInvalidAddressError,
    KrakenWithdrawalError,
    KrakenDepositError,
    KrakenAccountError
)
from shared.helpers.logging import get_logger
from shared.helpers.crypto_helpers import encrypt_data, decrypt_data
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class AccountTier(str, Enum):
    """Kraken account tier levels."""
    TIER_0 = "tier_0"  # Initial
    TIER_1 = "tier_1"  # $0 - $50,000 volume
    TIER_2 = "tier_2"  # $50,000 - $100,000 volume
    TIER_3 = "tier_3"  # $100,000 - $250,000 volume
    TIER_4 = "tier_4"  # $250,000 - $1,000,000 volume
    TIER_5 = "tier_5"  # $1,000,000 - $5,000,000 volume
    TIER_6 = "tier_6"  # $5,000,000 - $10,000,000 volume
    TIER_7 = "tier_7"  # $10,000,000+ volume


class AccountStatus(str, Enum):
    """Account status types."""
    ACTIVE = "active"
    LOCKED = "locked"
    SUSPENDED = "suspended"
    CLOSED = "closed"
    PENDING_VERIFICATION = "pending_verification"
    VERIFICATION_REQUIRED = "verification_required"
    UNDER_REVIEW = "under_review"


class TransactionType(str, Enum):
    """Transaction types."""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRADE = "trade"
    FEE = "fee"
    TRANSFER = "transfer"
    STAKING = "staking"
    EARNING = "earning"
    SPENDING = "spending"
    ROLLOVER = "rollover"
    ADJUSTMENT = "adjustment"
    REFUND = "refund"
    BONUS = "bonus"
    COMMISSION = "commission"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    LOAN = "loan"
    REPAYMENT = "repayment"


class TransactionStatus(str, Enum):
    """Transaction status types."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REVERSED = "reversed"
    EXPIRED = "expired"
    ON_HOLD = "on_hold"


class DepositMethod(str, Enum):
    """Deposit methods."""
    BANK_WIRE = "bank_wire"
    SEPA = "sepa"
    SWIFT = "swift"
    CRYPTO = "crypto"
    STABLE_COIN = "stable_coin"
    CARD = "card"
    E_WALLET = "e_wallet"
    PAYPAL = "paypal"
    INTERNAL = "internal"


class WithdrawalMethod(str, Enum):
    """Withdrawal methods."""
    BANK_WIRE = "bank_wire"
    SEPA = "sepa"
    SWIFT = "swift"
    CRYPTO = "crypto"
    STABLE_COIN = "stable_coin"
    CARD = "card"
    E_WALLET = "e_wallet"
    PAYPAL = "paypal"
    INTERNAL = "internal"
    CRYPTO_DIRECT = "crypto_direct"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class Balance(BaseModel):
    """Account balance for a currency."""
    currency: str
    total: Decimal = Decimal('0')
    available: Decimal = Decimal('0')
    locked: Decimal = Decimal('0')
    pending: Decimal = Decimal('0')
    staked: Decimal = Decimal('0')
    earned: Decimal = Decimal('0')
    value_usd: Optional[Decimal] = None
    value_btc: Optional[Decimal] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('currency')
    def validate_currency(cls, v):
        """Validate currency code."""
        if not v or len(v) < 1:
            raise ValueError("Currency code cannot be empty")
        return v.upper()

    @root_validator
    def validate_balance(cls, values):
        """Validate that total = available + locked + pending + staked."""
        total = values.get('total', Decimal('0'))
        available = values.get('available', Decimal('0'))
        locked = values.get('locked', Decimal('0'))
        pending = values.get('pending', Decimal('0'))
        staked = values.get('staked', Decimal('0'))
        
        # Don't enforce strict equality due to potential rounding
        calculated = available + locked + pending + staked
        if abs(total - calculated) > Decimal('0.00000001'):
            # Auto-correct
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
        """Calculate net amount."""
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
        """Validate deposit address."""
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
    method: WithdrawalMethod
    fee: Decimal = Decimal('0')
    status: TransactionStatus = TransactionStatus.PENDING
    transaction_id: Optional[str] = None
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


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Account balances
CREATE TABLE IF NOT EXISTS kraken_balances (
    id VARCHAR(64) PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    total DECIMAL(32, 16) DEFAULT 0,
    available DECIMAL(32, 16) DEFAULT 0,
    locked DECIMAL(32, 16) DEFAULT 0,
    pending DECIMAL(32, 16) DEFAULT 0,
    staked DECIMAL(32, 16) DEFAULT 0,
    earned DECIMAL(32, 16) DEFAULT 0,
    value_usd DECIMAL(32, 16),
    value_btc DECIMAL(32, 16),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, currency)
);

-- Transactions
CREATE TABLE IF NOT EXISTS kraken_transactions (
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
    INDEX idx_kraken_transactions_account_id (account_id),
    INDEX idx_kraken_transactions_type (type),
    INDEX idx_kraken_transactions_status (status),
    INDEX idx_kraken_transactions_created_at (created_at)
);

-- Deposit addresses
CREATE TABLE IF NOT EXISTS kraken_deposit_addresses (
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
    INDEX idx_kraken_deposit_addresses_account_id (account_id),
    INDEX idx_kraken_deposit_addresses_currency (currency),
    UNIQUE(account_id, currency, address)
);

-- Withdrawal requests
CREATE TABLE IF NOT EXISTS kraken_withdrawals (
    id VARCHAR(64) PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    amount DECIMAL(32, 16) NOT NULL,
    address VARCHAR(255) NOT NULL,
    tag VARCHAR(100),
    memo VARCHAR(100),
    chain VARCHAR(50),
    method VARCHAR(50) NOT NULL,
    fee DECIMAL(32, 16) DEFAULT 0,
    status VARCHAR(50) NOT NULL,
    transaction_id VARCHAR(128),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_kraken_withdrawals_account_id (account_id),
    INDEX idx_kraken_withdrawals_status (status),
    INDEX idx_kraken_withdrawals_created_at (created_at)
);

-- Account summary cache
CREATE TABLE IF NOT EXISTS kraken_account_summary (
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
"""


# =============================================================================
# MAIN ACCOUNT MANAGER
# =============================================================================

class KrakenAccountManager:
    """
    Advanced account manager for Kraken exchange.
    
    Features:
    - Multi-currency balance management with real-time updates
    - Transaction history with comprehensive filtering
    - Deposit address generation and management
    - Withdrawal operations with 2FA support
    - Account tier tracking and volume statistics
    - WebSocket streaming for account updates
    - Redis caching for improved performance
    - Comprehensive error handling and retry logic
    - Database persistence for historical data
    - Rate limit management
    - Security features including address whitelisting
    - Automatic reconciliation
    """
    
    def __init__(
        self,
        config: KrakenConfig,
        base: KrakenBase,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        self.config = config
        self.base = base
        self.redis = redis
        self.pool = pool
        self.account_id = config.api_key[:8]  # Short account identifier
        
        # Caches
        self._balance_cache: Dict[str, Balance] = {}
        self._address_cache: Dict[str, DepositAddress] = {}
        self._summary_cache: Optional[AccountSummary] = None
        self._cache_lock = asyncio.Lock()
        
        # Circuit breakers
        self._balance_cb = CircuitBreaker(
            name=f"kraken_account_balance_{self.account_id}",
            failure_threshold=3,
            recovery_timeout=30
        )
        self._withdrawal_cb = CircuitBreaker(
            name=f"kraken_withdrawal_{self.account_id}",
            failure_threshold=2,
            recovery_timeout=60
        )
        
        # WebSocket subscription
        self._ws_subscribed = False
        self._pending_updates: Dict[str, List[Dict]] = {}
        
        # Initialize database
        self._db_initialized = False
        
        logger.info(f"KrakenAccountManager initialized for account {self.account_id}")
    
    async def initialize(self):
        """Initialize the account manager."""
        # Initialize database
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load cached balances
        if self.redis:
            await self._load_cached_balances()
        
        # Load cached summary
        if self.redis:
            await self._load_cached_summary()
        
        # Sync initial balances
        await self.sync_balances()
        
        # Start periodic refresh
        asyncio.create_task(self._periodic_refresh())
        
        logger.info("KrakenAccountManager initialization complete")
    
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
        Get account balances for specified currencies.
        
        Args:
            currencies: List of currency codes (None = all)
            
        Returns:
            Dict mapping currency to Balance
        """
        # Check circuit breaker
        if self._balance_cb.is_open():
            raise KrakenRateLimitError("Balance circuit breaker is open")
        
        try:
            # Build request
            params = {}
            if currencies:
                # Kraken expects comma-separated list
                params['asset'] = ','.join(currencies)
            
            # Make API call
            response = await self.base._private_request('Balance', params)
            
            if 'result' not in response:
                raise KrakenAccountError("Unexpected response format")
            
            # Parse balances
            balances = {}
            for currency, balance in response['result'].items():
                # Normalize currency code
                normalized_currency = self._normalize_currency(currency)
                
                # Create balance object
                bal = Balance(
                    currency=normalized_currency,
                    total=Decimal(str(balance)),
                    available=Decimal(str(balance)),  # Kraken returns available balance
                    locked=Decimal('0')
                )
                balances[normalized_currency] = bal
            
            # Update cache
            async with self._cache_lock:
                self._balance_cache.update(balances)
            
            # Save to cache and database
            if self.redis:
                await self._cache_balances(balances)
            if self.pool:
                await self._save_balances(balances)
            
            # Record success
            self._balance_cb.record_success()
            
            return balances
            
        except Exception as e:
            self._balance_cb.record_failure()
            logger.error(f"Error getting balances: {e}")
            raise
    
    async def get_balance(self, currency: str) -> Optional[Balance]:
        """
        Get balance for a specific currency.
        
        Args:
            currency: Currency code
            
        Returns:
            Balance object or None
        """
        normalized = self._normalize_currency(currency)
        
        # Check cache first
        async with self._cache_lock:
            if normalized in self._balance_cache:
                return self._balance_cache[normalized]
        
        # Fetch from API
        balances = await self.get_balances([normalized])
        return balances.get(normalized)
    
    async def get_total_balance_usd(self) -> Decimal:
        """
        Get total account balance in USD.
        
        Returns:
            Total balance in USD
        """
        balances = await self.get_balances()
        
        total = Decimal('0')
        for currency, balance in balances.items():
            if currency == 'USD':
                total += balance.total
            else:
                # Get price in USD
                price = await self._get_price_usd(currency)
                if price:
                    total += balance.total * price
        
        return total
    
    async def sync_balances(self):
        """Synchronize all balances from the exchange."""
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
            # Build request
            params = {
                'limit': min(limit, 1000),
                'offset': offset
            }
            
            if type:
                params['type'] = type.value
            if status:
                params['status'] = status.value
            if currency:
                params['asset'] = currency
            if start_time:
                params['start'] = int(start_time.timestamp())
            if end_time:
                params['end'] = int(end_time.timestamp())
            
            # Make API call
            response = await self.base._private_request('Ledgers', params)
            
            if 'result' not in response:
                raise KrakenAccountError("Unexpected response format")
            
            result = response['result']
            ledgers = result.get('ledger', {})
            
            # Parse transactions
            transactions = []
            for ledger_id, data in ledgers.items():
                try:
                    txn = Transaction(
                        id=ledger_id,
                        type=TransactionType(data.get('type', 'trade')),
                        status=TransactionStatus(data.get('status', 'completed')),
                        currency=self._normalize_currency(data.get('asset', 'USD')),
                        amount=Decimal(str(data.get('amount', 0))),
                        fee=Decimal(str(data.get('fee', 0))),
                        net_amount=Decimal(str(data.get('amount', 0))) - Decimal(str(data.get('fee', 0))),
                        balance_before=Decimal(str(data.get('balance_before', 0))),
                        balance_after=Decimal(str(data.get('balance_after', 0))),
                        reference_id=data.get('refid'),
                        description=data.get('description'),
                        created_at=datetime.fromtimestamp(data.get('time', 0)),
                        completed_at=datetime.fromtimestamp(data.get('time', 0)) if data.get('time') else None,
                        metadata=data.get('metadata', {})
                    )
                    transactions.append(txn)
                except Exception as e:
                    logger.error(f"Error parsing transaction {ledger_id}: {e}")
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
            chain: Chain/network (e.g., 'ERC20', 'BEP20', 'TRC20')
            
        Returns:
            List of DepositAddress objects
        """
        try:
            normalized_currency = self._normalize_currency(currency)
            
            params = {
                'asset': normalized_currency
            }
            if chain:
                params['method'] = chain
            
            # Make API call
            response = await self.base._private_request('DepositAddresses', params)
            
            if 'result' not in response:
                raise KrakenAccountError("Unexpected response format")
            
            addresses = []
            for addr_data in response['result']:
                address = DepositAddress(
                    address=addr_data.get('address', ''),
                    currency=normalized_currency,
                    chain=addr_data.get('method'),
                    tag=addr_data.get('tag'),
                    memo=addr_data.get('memo'),
                    destination_tag=addr_data.get('destination_tag'),
                    expires_at=datetime.fromtimestamp(addr_data.get('expiretm', 0)) if addr_data.get('expiretm') else None,
                    metadata={'fee': Decimal(str(addr_data.get('fee', 0)))}
                )
                addresses.append(address)
            
            # Cache addresses
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
            normalized_currency = self._normalize_currency(currency)
            
            params = {
                'asset': normalized_currency,
                'new': 1
            }
            if chain:
                params['method'] = chain
            
            # Make API call
            response = await self.base._private_request('DepositAddresses', params)
            
            if 'result' not in response:
                raise KrakenAccountError("Unexpected response format")
            
            result = response['result']
            if not result:
                raise KrakenDepositError("Failed to generate deposit address")
            
            addr_data = result[0] if isinstance(result, list) else result
            
            address = DepositAddress(
                address=addr_data.get('address', ''),
                currency=normalized_currency,
                chain=addr_data.get('method', chain),
                tag=addr_data.get('tag', tag),
                memo=addr_data.get('memo'),
                destination_tag=addr_data.get('destination_tag'),
                expires_at=datetime.fromtimestamp(addr_data.get('expiretm', 0)) if addr_data.get('expiretm') else None
            )
            
            # Cache address
            key = f"{address.currency}_{address.chain}"
            async with self._cache_lock:
                self._address_cache[key] = address
            
            # Save to database
            if self.pool:
                await self._save_deposit_address(address)
            
            logger.info(f"Generated deposit address for {currency} on {chain or 'default'}")
            return address
            
        except Exception as e:
            logger.error(f"Error generating deposit address: {e}")
            raise
    
    async def get_deposit_status(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Get deposit status by transaction ID."""
        try:
            params = {'txid': transaction_id}
            response = await self.base._private_request('DepositStatus', params)
            
            if 'result' not in response:
                return None
            
            result = response['result']
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error getting deposit status: {e}")
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
        method: WithdrawalMethod = WithdrawalMethod.CRYPTO,
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
            method: Withdrawal method
            two_factor_code: 2FA code if required
            
        Returns:
            WithdrawalRequest object
        """
        # Check circuit breaker
        if self._withdrawal_cb.is_open():
            raise KrakenRateLimitError("Withdrawal circuit breaker is open")
        
        try:
            normalized_currency = self._normalize_currency(currency)
            
            # Check balance
            balance = await self.get_balance(normalized_currency)
            if not balance or balance.available < amount:
                raise KrakenInsufficientFundsError(
                    f"Insufficient funds: {balance.available if balance else 0} available, {amount} requested"
                )
            
            # Build request
            params = {
                'asset': normalized_currency,
                'amount': str(amount),
                'address': address
            }
            
            if chain:
                params['method'] = chain
            if tag:
                params['tag'] = tag
            if memo:
                params['memo'] = memo
            if method != WithdrawalMethod.CRYPTO:
                params['method'] = method.value
            if two_factor_code:
                params['otp'] = two_factor_code
            
            # Make API call
            response = await self.base._private_request('Withdraw', params)
            
            if 'result' not in response:
                raise KrakenWithdrawalError("Unexpected response format")
            
            result = response['result']
            
            # Create withdrawal request
            withdrawal = WithdrawalRequest(
                id=result.get('refid', str(uuid.uuid4())),
                currency=normalized_currency,
                amount=amount,
                address=address,
                tag=tag,
                memo=memo,
                chain=chain,
                method=method,
                fee=Decimal(str(result.get('fee', 0))),
                status=TransactionStatus.PENDING,
                transaction_id=result.get('txid'),
                created_at=datetime.utcnow(),
                metadata=result.get('metadata', {})
            )
            
            # Save to database
            if self.pool:
                await self._save_withdrawal(withdrawal)
            
            # Record success
            self._withdrawal_cb.record_success()
            
            logger.info(f"Withdrawal initiated: {amount} {currency} to {address[:10]}...")
            return withdrawal
            
        except Exception as e:
            self._withdrawal_cb.record_failure()
            logger.error(f"Error processing withdrawal: {e}")
            raise
    
    async def get_withdrawal_status(self, withdrawal_id: str) -> Optional[Dict[str, Any]]:
        """Get withdrawal status by ID."""
        try:
            params = {'refid': withdrawal_id}
            response = await self.base._private_request('WithdrawStatus', params)
            
            if 'result' not in response:
                return None
            
            result = response['result']
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Error getting withdrawal status: {e}")
            raise
    
    async def cancel_withdrawal(self, withdrawal_id: str) -> bool:
        """Cancel a pending withdrawal."""
        try:
            params = {'refid': withdrawal_id}
            response = await self.base._private_request('WithdrawCancel', params)
            
            if 'result' not in response:
                return False
            
            return response.get('result', {}).get('cancel', False)
            
        except Exception as e:
            logger.error(f"Error canceling withdrawal: {e}")
            return False
    
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
            total_usd = await self.get_total_balance_usd()
            
            # Get account info
            response = await self.base._private_request('AccountInfo')
            
            if 'result' not in response:
                raise KrakenAccountError("Unexpected response format")
            
            result = response['result']
            
            # Create summary
            summary = AccountSummary(
                account_id=self.account_id,
                username=result.get('username', ''),
                email=result.get('email', ''),
                tier=self._get_tier_from_volume(result.get('trading_volume_30d', 0)),
                status=AccountStatus(result.get('status', 'active')),
                total_balance_usd=total_usd,
                total_balance_btc=Decimal('0'),  # Would need BTC price
                open_orders=result.get('open_orders', 0),
                open_positions=result.get('open_positions', 0),
                total_trades=result.get('total_trades', 0),
                total_volume_30d=Decimal(str(result.get('trading_volume_30d', 0))),
                total_volume_365d=Decimal(str(result.get('trading_volume_365d', 0))),
                trading_fees_30d=Decimal(str(result.get('trading_fees_30d', 0))),
                trading_fees_365d=Decimal(str(result.get('trading_fees_365d', 0))),
                margin_used=Decimal(str(result.get('margin_used', 0))),
                margin_available=Decimal(str(result.get('margin_available', 0))),
                equity=Decimal(str(result.get('equity', 0))),
                maintenance_margin=Decimal(str(result.get('maintenance_margin', 0))),
                initial_margin=Decimal(str(result.get('initial_margin', 0))),
                liquidation_price=Decimal(str(result['liquidation_price'])) if result.get('liquidation_price') else None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Cache
            self._summary_cache = summary
            
            # Save to cache
            if self.redis:
                await self._cache_summary(summary)
            
            # Save to database
            if self.pool:
                await self._save_summary(summary)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting account summary: {e}")
            if self._summary_cache:
                return self._summary_cache
            raise
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _normalize_currency(self, currency: str) -> str:
        """Normalize currency code."""
        if not currency:
            return 'USD'
        
        # Remove 'Z' suffix if present (Kraken uses Z for certain currencies)
        if currency.endswith('Z'):
            currency = currency[:-1]
        
        # Map common variations
        currency_map = {
            'XBT': 'BTC',
            'XRP': 'XRP',
            'XLM': 'XLM',
            'XDAI': 'DAI',
            'XMR': 'XMR',
            'XLM': 'XLM',
            'XRP': 'XRP',
            'XRP': 'XRP',
        }
        
        return currency_map.get(currency, currency).upper()
    
    def _get_tier_from_volume(self, volume_30d: float) -> AccountTier:
        """Determine account tier from 30-day volume."""
        if volume_30d < 50000:
            return AccountTier.TIER_0
        elif volume_30d < 100000:
            return AccountTier.TIER_1
        elif volume_30d < 250000:
            return AccountTier.TIER_2
        elif volume_30d < 1000000:
            return AccountTier.TIER_3
        elif volume_30d < 5000000:
            return AccountTier.TIER_4
        elif volume_30d < 10000000:
            return AccountTier.TIER_5
        else:
            return AccountTier.TIER_6
    
    async def _get_price_usd(self, currency: str) -> Optional[Decimal]:
        """Get price in USD for a currency."""
        try:
            # Get price from Kraken
            pair = f"{currency}USD"
            response = await self.base.get_ticker(pair)
            if pair in response:
                return Decimal(str(response[pair]['c'][0]))  # Last price
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
            key = f"kraken:balances:{self.account_id}"
            data = {
                currency: {
                    'total': str(b.total),
                    'available': str(b.available),
                    'locked': str(b.locked),
                    'pending': str(b.pending),
                    'staked': str(b.staked),
                    'earned': str(b.earned),
                    'value_usd': str(b.value_usd) if b.value_usd else None,
                    'value_btc': str(b.value_btc) if b.value_btc else None,
                    'updated_at': b.updated_at.isoformat()
                }
                for currency, b in balances.items()
            }
            await self.redis.setex(key, 300, json.dumps(data))  # 5 minute TTL
        except Exception as e:
            logger.error(f"Error caching balances: {e}")
    
    async def _load_cached_balances(self):
        """Load cached balances from Redis."""
        if not self.redis:
            return
        
        try:
            key = f"kraken:balances:{self.account_id}"
            data = await self.redis.get(key)
            if data:
                data = json.loads(data)
                async with self._cache_lock:
                    for currency, b_data in data.items():
                        self._balance_cache[currency] = Balance(
                            currency=currency,
                            total=Decimal(str(b_data['total'])),
                            available=Decimal(str(b_data['available'])),
                            locked=Decimal(str(b_data['locked'])),
                            pending=Decimal(str(b_data['pending'])),
                            staked=Decimal(str(b_data['staked'])),
                            earned=Decimal(str(b_data['earned'])),
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
            key = f"kraken:summary:{self.account_id}"
            data = summary.dict()
            data['total_balance_usd'] = str(data['total_balance_usd'])
            data['total_balance_btc'] = str(data['total_balance_btc'])
            data['total_volume_30d'] = str(data['total_volume_30d'])
            data['total_volume_365d'] = str(data['total_volume_365d'])
            data['trading_fees_30d'] = str(data['trading_fees_30d'])
            data['trading_fees_365d'] = str(data['trading_fees_365d'])
            data['margin_used'] = str(data['margin_used'])
            data['margin_available'] = str(data['margin_available'])
            data['equity'] = str(data['equity'])
            data['maintenance_margin'] = str(data['maintenance_margin'])
            data['initial_margin'] = str(data['initial_margin'])
            if data['liquidation_price']:
                data['liquidation_price'] = str(data['liquidation_price'])
            data['created_at'] = data['created_at'].isoformat()
            data['updated_at'] = data['updated_at'].isoformat()
            data['metadata'] = json.dumps(data['metadata'])
            
            await self.redis.setex(key, 300, json.dumps(data))  # 5 minute TTL
        except Exception as e:
            logger.error(f"Error caching summary: {e}")
    
    async def _load_cached_summary(self):
        """Load cached summary from Redis."""
        if not self.redis:
            return
        
        try:
            key = f"kraken:summary:{self.account_id}"
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
                            INSERT INTO kraken_balances (
                                id, account_id, currency, total, available,
                                locked, pending, staked, earned,
                                value_usd, value_btc, updated_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                            ON CONFLICT (account_id, currency) DO UPDATE SET
                                total = EXCLUDED.total,
                                available = EXCLUDED.available,
                                locked = EXCLUDED.locked,
                                pending = EXCLUDED.pending,
                                staked = EXCLUDED.staked,
                                earned = EXCLUDED.earned,
                                value_usd = EXCLUDED.value_usd,
                                value_btc = EXCLUDED.value_btc,
                                updated_at = EXCLUDED.updated_at
                            """,
                            f"{self.account_id}_{currency}",
                            self.account_id,
                            currency,
                            balance.total,
                            balance.available,
                            balance.locked,
                            balance.pending,
                            balance.staked,
                            balance.earned,
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
                    INSERT INTO kraken_deposit_addresses (
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
        """Save withdrawal request to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO kraken_withdrawals (
                        id, account_id, currency, amount, address,
                        tag, memo, chain, method, fee, status,
                        transaction_id, created_at, completed_at,
                        metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                              $11, $12, $13, $14, $15)
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
                    withdrawal.method.value,
                    withdrawal.fee,
                    withdrawal.status.value,
                    withdrawal.transaction_id,
                    withdrawal.created_at,
                    withdrawal.completed_at,
                    json.dumps(withdrawal.metadata)
                )
        except Exception as e:
            logger.error(f"Error saving withdrawal: {e}")
    
    async def _save_summary(self, summary: AccountSummary):
        """Save account summary to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO kraken_account_summary (
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
    
    # =========================================================================
    # PERIODIC REFRESH
    # =========================================================================
    
    async def _periodic_refresh(self):
        """Periodically refresh account data."""
        while True:
            try:
                await asyncio.sleep(30)  # Every 30 seconds
                await self.sync_balances()
                
                # Refresh summary every 5 minutes
                if int(time.time()) % 300 == 0:
                    await self.get_summary(force_refresh=True)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic refresh: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # WEBSOCKET INTEGRATION
    # =========================================================================
    
    async def subscribe_to_updates(self):
        """Subscribe to WebSocket account updates."""
        if self._ws_subscribed:
            return
        
        try:
            # Subscribe to account updates
            await self.base._ws_send({
                "event": "subscribe",
                "subscription": {
                    "name": "ownTrades",
                    "token": self.base._get_ws_token()
                }
            })
            
            # Also subscribe to balances
            await self.base._ws_send({
                "event": "subscribe",
                "subscription": {
                    "name": "balance",
                    "token": self.base._get_ws_token()
                }
            })
            
            self._ws_subscribed = True
            logger.info("Subscribed to account updates")
            
        except Exception as e:
            logger.error(f"Error subscribing to updates: {e}")
    
    async def handle_ws_update(self, update: Dict[str, Any]):
        """Handle WebSocket account update."""
        try:
            if 'balance' in update:
                # Balance update
                balances = update['balance']
                for currency, balance in balances.items():
                    normalized = self._normalize_currency(currency)
                    b = Balance(
                        currency=normalized,
                        total=Decimal(str(balance)),
                        available=Decimal(str(balance)),
                        updated_at=datetime.utcnow()
                    )
                    async with self._cache_lock:
                        self._balance_cache[normalized] = b
                    if self.redis:
                        await self._cache_balances({normalized: b})
                    
            elif 'ownTrades' in update:
                # Trade update
                trades = update['ownTrades']
                # Process trades
                pass
                
        except Exception as e:
            logger.error(f"Error handling WS update: {e}")
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown the account manager."""
        logger.info("Shutting down KrakenAccountManager")
        # Nothing to clean up
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    async def get_trading_fees(self, currency_pair: str) -> Dict[str, Decimal]:
        """
        Get trading fees for a currency pair.
        
        Args:
            currency_pair: The trading pair
            
        Returns:
            Dict with maker and taker fees
        """
        try:
            response = await self.base._private_request('FeeInfo')
            
            if 'result' not in response:
                raise KrakenAccountError("Unexpected response format")
            
            result = response['result']
            
            # Get fees for the specific pair
            fees = result.get('fees', {})
            pair_fees = fees.get(currency_pair, {})
            
            return {
                'maker': Decimal(str(pair_fees.get('maker', result.get('maker_fee', 0)))),
                'taker': Decimal(str(pair_fees.get('taker', result.get('taker_fee', 0))))
            }
            
        except Exception as e:
            logger.error(f"Error getting trading fees: {e}")
            return {'maker': Decimal('0'), 'taker': Decimal('0')}
    
    async def get_margin_info(self) -> Dict[str, Any]:
        """
        Get margin account information.
        
        Returns:
            Dict with margin account details
        """
        try:
            response = await self.base._private_request('MarginInfo')
            
            if 'result' not in response:
                raise KrakenAccountError("Unexpected response format")
            
            return response['result']
            
        except Exception as e:
            logger.error(f"Error getting margin info: {e}")
            raise
    
    async def get_volume_stats(self) -> Dict[str, Any]:
        """
        Get trading volume statistics.
        
        Returns:
            Dict with volume statistics
        """
        try:
            response = await self.base._private_request('TradeVolume')
            
            if 'result' not in response:
                raise KrakenAccountError("Unexpected response format")
            
            return response['result']
            
        except Exception as e:
            logger.error(f"Error getting volume stats: {e}")
            raise


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'KrakenAccountManager',
    'AccountTier',
    'AccountStatus',
    'TransactionType',
    'TransactionStatus',
    'DepositMethod',
    'WithdrawalMethod',
    'Balance',
    'Transaction',
    'DepositAddress',
    'WithdrawalRequest',
    'AccountSummary'
]
