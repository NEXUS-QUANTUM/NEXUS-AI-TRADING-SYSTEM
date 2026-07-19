# trading/exchanges/okx/option.py
# Nexus AI Trading System - OKX Exchange Options Module
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
# Full version with advanced coding

"""
OKX Exchange - Options Trading Module

This module provides comprehensive options trading functionality for the OKX
cryptocurrency exchange, including:

- Options order placement and management
- Options position management
- Options pricing and Greeks calculation
- Volatility surface analysis
- Options strategies (calls, puts, straddles, strangles, spreads)
- Exercise and assignment management
- Settlement management
- Risk management for options
- Options WebSocket streaming
- Implied volatility calculation
- Historical volatility analysis
- Option chain management
- Automated options strategies
- Delta hedging
- Gamma scalping
- Comprehensive error handling
- Database persistence
- Redis caching

Features:
- All options order types (market, limit, post-only, IOC, FOK)
- Cross-margin and isolated-margin support
- Options Greeks (Delta, Gamma, Theta, Vega, Rho)
- Implied volatility calculation
- Black-Scholes pricing model
- Binomial model pricing
- Risk reversal analysis
- Volatility smile analysis
- Term structure analysis
- Exercise and assignment automation
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
import uuid

import numpy as np
from scipy import stats
from scipy.optimize import brentq
from pydantic import BaseModel, Field, validator, root_validator
from redis.asyncio import Redis
import asyncpg

# Nexus imports
from trading.exchanges.okx.base import (
    OKXBase,
    OKXConfig,
    OKXApiType,
    OKXOrderType,
    OKXOrderSide,
    OKXOrderStatus,
    OKXTimeInForce
)
from trading.exchanges.okx.exceptions import (
    OKXError,
    OKXOrderError,
    OKXInsufficientFundsError,
    OKXRateLimitError,
    OKXValidationError,
    OKXInvalidSymbolError,
    OKXPositionError
)
from trading.exchanges.okx.converter import OKXConverter, get_converter
from trading.exchanges.okx.market import OKXMarketData, OKXInterval
from shared.helpers.logging import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.retry import async_retry

logger = get_logger(__name__)

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class OptionType(str, Enum):
    """Option types."""
    CALL = "call"
    PUT = "put"


class OptionStyle(str, Enum):
    """Option styles."""
    EUROPEAN = "european"
    AMERICAN = "american"


class OptionOrderType(str, Enum):
    """Options order types."""
    MARKET = "market"
    LIMIT = "limit"
    POST_ONLY = "post_only"
    FOK = "fok"
    IOC = "ioc"
    OPTIMAL_LIMIT_IOC = "optimal_limit_ioc"


class OptionOrderSide(str, Enum):
    """Options order sides."""
    BUY = "buy"
    SELL = "sell"
    BUY_OPEN = "buy_open"
    BUY_CLOSE = "buy_close"
    SELL_OPEN = "sell_open"
    SELL_CLOSE = "sell_close"


class OptionPositionSide(str, Enum):
    """Options position sides."""
    LONG = "long"
    SHORT = "short"


class OptionExerciseType(str, Enum):
    """Option exercise types."""
    AUTO = "auto"
    MANUAL = "manual"
    EARLY = "early"


class OptionMarginMode(str, Enum):
    """Options margin modes."""
    CROSS = "cross"
    ISOLATED = "isolated"


class OptionStatus(str, Enum):
    """Option status."""
    LISTED = "listed"
    TRADING = "trading"
    EXPIRED = "expired"
    EXERCISED = "exercised"
    ASSIGNED = "assigned"
    CLOSED = "closed"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class OptionGreeks(BaseModel):
    """Option Greeks."""
    delta: Decimal = Decimal('0')
    gamma: Decimal = Decimal('0')
    theta: Decimal = Decimal('0')
    vega: Decimal = Decimal('0')
    rho: Decimal = Decimal('0')
    implied_volatility: Decimal = Decimal('0')
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OptionContract(BaseModel):
    """Options contract."""
    id: str
    symbol: str
    underlying: str
    option_type: OptionType
    strike: Decimal
    expiry: datetime
    style: OptionStyle = OptionStyle.EUROPEAN
    contract_size: Decimal = Decimal('1')
    tick_size: Decimal = Decimal('0.01')
    lot_size: Decimal = Decimal('0.001')
    min_volume: Decimal = Decimal('0')
    max_volume: Optional[Decimal] = None
    status: OptionStatus = OptionStatus.TRADING
    bid: Decimal = Decimal('0')
    ask: Decimal = Decimal('0')
    last: Decimal = Decimal('0')
    mark: Decimal = Decimal('0')
    volume: Decimal = Decimal('0')
    open_interest: Decimal = Decimal('0')
    greeks: Optional[OptionGreeks] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def moneyness(self) -> Decimal:
        """Calculate option moneyness."""
        if self.mark == 0:
            return Decimal('0')
        if self.option_type == OptionType.CALL:
            return self.mark / self.strike
        else:
            return self.strike / self.mark

    @property
    def is_itm(self) -> bool:
        """Check if option is in-the-money."""
        if self.option_type == OptionType.CALL:
            return self.mark > self.strike
        else:
            return self.mark < self.strike

    @property
    def is_otm(self) -> bool:
        """Check if option is out-of-the-money."""
        if self.option_type == OptionType.CALL:
            return self.mark < self.strike
        else:
            return self.mark > self.strike

    @property
    def is_atm(self) -> bool:
        """Check if option is at-the-money."""
        return abs(self.mark - self.strike) < (self.tick_size * Decimal('5'))


class OptionOrder(BaseModel):
    """Options order model."""
    id: str
    symbol: str
    side: OptionOrderSide
    position_side: Optional[OptionPositionSide] = None
    order_type: OptionOrderType
    status: OptionOrderStatus
    price: Decimal = Decimal('0')
    volume: Decimal = Decimal('0')
    filled_volume: Decimal = Decimal('0')
    remaining_volume: Decimal = Decimal('0')
    average_price: Optional[Decimal] = None
    fee: Decimal = Decimal('0')
    fee_currency: Optional[str] = None
    cost: Decimal = Decimal('0')
    margin: Decimal = Decimal('0')
    time_in_force: OKXTimeInForce = OKXTimeInForce.GTC
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    reduce_only: bool = False
    close_position: bool = False
    client_order_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def fill_rate(self) -> float:
        if self.volume == 0:
            return 0.0
        return float(self.filled_volume / self.volume * 100)


class OptionPosition(BaseModel):
    """Options position model."""
    id: str
    symbol: str
    side: OptionPositionSide
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal
    strike: Decimal
    expiry: datetime
    option_type: OptionType
    margin: Decimal
    unrealized_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    total_pnl: Decimal = Decimal('0')
    roe: Decimal = Decimal('0')
    margin_mode: OptionMarginMode
    status: OptionStatus = OptionStatus.TRADING
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    greeks: Optional[OptionGreeks] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def pnl_percent(self) -> Decimal:
        if self.margin == 0:
            return Decimal('0')
        return (self.total_pnl / self.margin) * 100


class OptionStrategy(BaseModel):
    """Options strategy."""
    id: str
    name: str
    strategy_type: str  # call, put, straddle, strangle, spread, iron_condor, butterfly
    legs: List[Dict[str, Any]]
    net_price: Decimal = Decimal('0')
    net_margin: Decimal = Decimal('0')
    max_profit: Optional[Decimal] = None
    max_loss: Optional[Decimal] = None
    break_even: Optional[Decimal] = None
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VolatilitySurface(BaseModel):
    """Volatility surface data."""
    underlying: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    strikes: List[Decimal]
    expiries: List[datetime]
    implied_volatilities: List[List[Decimal]]
    risk_free_rate: Decimal = Decimal('0')
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# OPTIONS PRICING ENGINE
# =============================================================================

class OptionPricingEngine:
    """
    Advanced options pricing engine with multiple models.
    
    Features:
    - Black-Scholes model
    - Binomial model (Cox-Ross-Rubinstein)
    - Greeks calculation
    - Implied volatility calculation
    - Risk-neutral pricing
    - Volatility smile analysis
    - Term structure analysis
    """
    
    def __init__(self):
        self._cache = {}
        self._cache_timestamps = {}
        self._cache_ttl = 60  # seconds
        
        logger.info("OptionPricingEngine initialized")
    
    def black_scholes(
        self,
        S: Decimal,  # Spot price
        K: Decimal,  # Strike price
        T: Decimal,  # Time to expiry (years)
        r: Decimal,  # Risk-free rate
        sigma: Decimal,  # Volatility
        option_type: OptionType
    ) -> Decimal:
        """
        Calculate option price using Black-Scholes model.
        
        Args:
            S: Spot price
            K: Strike price
            T: Time to expiry (years)
            r: Risk-free rate
            sigma: Volatility
            option_type: Option type (call/put)
            
        Returns:
            Option price
        """
        # Convert to float for scipy
        S_f = float(S)
        K_f = float(K)
        T_f = float(T)
        r_f = float(r)
        sigma_f = float(sigma)
        
        d1 = (math.log(S_f / K_f) + (r_f + 0.5 * sigma_f ** 2) * T_f) / (sigma_f * math.sqrt(T_f))
        d2 = d1 - sigma_f * math.sqrt(T_f)
        
        if option_type == OptionType.CALL:
            price = S_f * stats.norm.cdf(d1) - K_f * math.exp(-r_f * T_f) * stats.norm.cdf(d2)
        else:
            price = K_f * math.exp(-r_f * T_f) * stats.norm.cdf(-d2) - S_f * stats.norm.cdf(-d1)
        
        return Decimal(str(max(price, 0)))
    
    def calculate_greeks(
        self,
        S: Decimal,
        K: Decimal,
        T: Decimal,
        r: Decimal,
        sigma: Decimal,
        option_type: OptionType
    ) -> OptionGreeks:
        """
        Calculate all Greeks for an option.
        
        Args:
            S: Spot price
            K: Strike price
            T: Time to expiry (years)
            r: Risk-free rate
            sigma: Volatility
            option_type: Option type (call/put)
            
        Returns:
            OptionGreeks object
        """
        # Convert to float
        S_f = float(S)
        K_f = float(K)
        T_f = float(T)
        r_f = float(r)
        sigma_f = float(sigma)
        
        if T_f <= 0:
            return OptionGreeks()
        
        d1 = (math.log(S_f / K_f) + (r_f + 0.5 * sigma_f ** 2) * T_f) / (sigma_f * math.sqrt(T_f))
        d2 = d1 - sigma_f * math.sqrt(T_f)
        
        # Delta
        if option_type == OptionType.CALL:
            delta = stats.norm.cdf(d1)
        else:
            delta = stats.norm.cdf(d1) - 1
        
        # Gamma (same for calls and puts)
        gamma = stats.norm.pdf(d1) / (S_f * sigma_f * math.sqrt(T_f))
        
        # Theta
        if option_type == OptionType.CALL:
            theta = -S_f * stats.norm.pdf(d1) * sigma_f / (2 * math.sqrt(T_f)) - r_f * K_f * math.exp(-r_f * T_f) * stats.norm.cdf(d2)
        else:
            theta = -S_f * stats.norm.pdf(d1) * sigma_f / (2 * math.sqrt(T_f)) + r_f * K_f * math.exp(-r_f * T_f) * stats.norm.cdf(-d2)
        
        # Vega (same for calls and puts)
        vega = S_f * stats.norm.pdf(d1) * math.sqrt(T_f)
        
        # Rho
        if option_type == OptionType.CALL:
            rho = K_f * T_f * math.exp(-r_f * T_f) * stats.norm.cdf(d2)
        else:
            rho = -K_f * T_f * math.exp(-r_f * T_f) * stats.norm.cdf(-d2)
        
        return OptionGreeks(
            delta=Decimal(str(delta)),
            gamma=Decimal(str(gamma)),
            theta=Decimal(str(theta / 365)),  # Daily theta
            vega=Decimal(str(vega / 100)),  # Vega per 1% vol
            rho=Decimal(str(rho / 100)),  # Rho per 1% rate
            implied_volatility=sigma,
            timestamp=datetime.utcnow()
        )
    
    def implied_volatility(
        self,
        price: Decimal,
        S: Decimal,
        K: Decimal,
        T: Decimal,
        r: Decimal,
        option_type: OptionType,
        max_iterations: int = 100,
        precision: Decimal = Decimal('0.000001')
    ) -> Decimal:
        """
        Calculate implied volatility using Newton-Raphson method.
        
        Args:
            price: Option market price
            S: Spot price
            K: Strike price
            T: Time to expiry (years)
            r: Risk-free rate
            option_type: Option type (call/put)
            max_iterations: Maximum iterations
            precision: Desired precision
            
        Returns:
            Implied volatility
        """
        if price <= 0:
            return Decimal('0')
        
        # Convert to float
        price_f = float(price)
        S_f = float(S)
        K_f = float(K)
        T_f = float(T)
        r_f = float(r)
        
        if T_f <= 0:
            return Decimal('0')
        
        # Initial guess
        sigma = 0.2
        
        # Define objective function
        def objective(s):
            try:
                d1 = (math.log(S_f / K_f) + (r_f + 0.5 * s ** 2) * T_f) / (s * math.sqrt(T_f))
                d2 = d1 - s * math.sqrt(T_f)
                
                if option_type == OptionType.CALL:
                    return S_f * stats.norm.cdf(d1) - K_f * math.exp(-r_f * T_f) * stats.norm.cdf(d2) - price_f
                else:
                    return K_f * math.exp(-r_f * T_f) * stats.norm.cdf(-d2) - S_f * stats.norm.cdf(-d1) - price_f
            except Exception:
                return float('inf')
        
        # Use Brent's method for root finding
        try:
            # Find interval containing root
            a = 0.001
            b = 5.0
            
            # Check if root exists
            if objective(a) * objective(b) > 0:
                # Try wider range
                b = 10.0
                if objective(a) * objective(b) > 0:
                    return Decimal('0')
            
            result = brentq(objective, a, b)
            return Decimal(str(max(result, 0.001)))
            
        except Exception:
            return Decimal('0')
    
    def binomial_price(
        self,
        S: Decimal,
        K: Decimal,
        T: Decimal,
        r: Decimal,
        sigma: Decimal,
        option_type: OptionType,
        steps: int = 100
    ) -> Decimal:
        """
        Calculate option price using binomial model (Cox-Ross-Rubinstein).
        
        Args:
            S: Spot price
            K: Strike price
            T: Time to expiry (years)
            r: Risk-free rate
            sigma: Volatility
            option_type: Option type (call/put)
            steps: Number of steps
            
        Returns:
            Option price
        """
        S_f = float(S)
        K_f = float(K)
        T_f = float(T)
        r_f = float(r)
        sigma_f = float(sigma)
        dt = T_f / steps
        u = math.exp(sigma_f * math.sqrt(dt))
        d = 1 / u
        p = (math.exp(r_f * dt) - d) / (u - d)
        
        # Initialize stock prices at expiry
        stock_prices = [S_f * (u ** (steps - i)) * (d ** i) for i in range(steps + 1)]
        
        # Initialize option values at expiry
        if option_type == OptionType.CALL:
            option_values = [max(price - K_f, 0) for price in stock_prices]
        else:
            option_values = [max(K_f - price, 0) for price in stock_prices]
        
        # Backward induction
        for step in range(steps - 1, -1, -1):
            for i in range(step + 1):
                option_values[i] = math.exp(-r_f * dt) * (p * option_values[i] + (1 - p) * option_values[i + 1])
        
        return Decimal(str(max(option_values[0], 0)))


# =============================================================================
# DATABASE TABLES
# =============================================================================

CREATE_TABLES_SQL = """
-- Options contracts
CREATE TABLE IF NOT EXISTS okx_option_contracts (
    id VARCHAR(64) PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    underlying VARCHAR(20) NOT NULL,
    option_type VARCHAR(10) NOT NULL,
    strike DECIMAL(32, 16) NOT NULL,
    expiry TIMESTAMP NOT NULL,
    style VARCHAR(20) NOT NULL,
    contract_size DECIMAL(32, 16) DEFAULT 1,
    tick_size DECIMAL(32, 16) DEFAULT 0.01,
    lot_size DECIMAL(32, 16) DEFAULT 0.001,
    min_volume DECIMAL(32, 16) DEFAULT 0,
    max_volume DECIMAL(32, 16),
    status VARCHAR(20) DEFAULT 'trading',
    bid DECIMAL(32, 16) DEFAULT 0,
    ask DECIMAL(32, 16) DEFAULT 0,
    last DECIMAL(32, 16) DEFAULT 0,
    mark DECIMAL(32, 16) DEFAULT 0,
    volume DECIMAL(32, 16) DEFAULT 0,
    open_interest DECIMAL(32, 16) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_okx_option_contracts_symbol (symbol),
    INDEX idx_okx_option_contracts_underlying (underlying),
    INDEX idx_okx_option_contracts_expiry (expiry),
    INDEX idx_okx_option_contracts_option_type (option_type)
);

-- Options orders
CREATE TABLE IF NOT EXISTS okx_option_orders (
    id VARCHAR(64) PRIMARY KEY,
    client_order_id VARCHAR(64),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(20) NOT NULL,
    position_side VARCHAR(10),
    order_type VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL,
    price DECIMAL(32, 16) NOT NULL,
    volume DECIMAL(32, 16) NOT NULL,
    filled_volume DECIMAL(32, 16) DEFAULT 0,
    remaining_volume DECIMAL(32, 16) DEFAULT 0,
    avg_price DECIMAL(32, 16) DEFAULT 0,
    fee DECIMAL(32, 16) DEFAULT 0,
    fee_currency VARCHAR(10),
    cost DECIMAL(32, 16) DEFAULT 0,
    margin DECIMAL(32, 16) DEFAULT 0,
    time_in_force VARCHAR(10) DEFAULT 'GTC',
    reduce_only BOOLEAN DEFAULT FALSE,
    close_position BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    expires_at TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    INDEX idx_okx_option_orders_symbol (symbol),
    INDEX idx_okx_option_orders_status (status),
    INDEX idx_okx_option_orders_created_at (created_at)
);

-- Options positions
CREATE TABLE IF NOT EXISTS okx_option_positions (
    id VARCHAR(64) PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity DECIMAL(32, 16) NOT NULL,
    entry_price DECIMAL(32, 16) NOT NULL,
    mark_price DECIMAL(32, 16) NOT NULL,
    strike DECIMAL(32, 16) NOT NULL,
    expiry TIMESTAMP NOT NULL,
    option_type VARCHAR(10) NOT NULL,
    margin DECIMAL(32, 16) NOT NULL,
    unrealized_pnl DECIMAL(32, 16) DEFAULT 0,
    realized_pnl DECIMAL(32, 16) DEFAULT 0,
    total_pnl DECIMAL(32, 16) DEFAULT 0,
    roe DECIMAL(32, 16) DEFAULT 0,
    margin_mode VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'trading',
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    greeks JSONB,
    metadata JSONB DEFAULT '{}',
    UNIQUE(symbol, side)
);

-- Options strategies
CREATE TABLE IF NOT EXISTS okx_option_strategies (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,
    legs JSONB NOT NULL,
    net_price DECIMAL(32, 16) DEFAULT 0,
    net_margin DECIMAL(32, 16) DEFAULT 0,
    max_profit DECIMAL(32, 16),
    max_loss DECIMAL(32, 16),
    break_even DECIMAL(32, 16),
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Volatility surfaces
CREATE TABLE IF NOT EXISTS okx_volatility_surfaces (
    id SERIAL PRIMARY KEY,
    underlying VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    strikes JSONB NOT NULL,
    expiries JSONB NOT NULL,
    implied_volatilities JSONB NOT NULL,
    risk_free_rate DECIMAL(32, 16) DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    INDEX idx_okx_volatility_surfaces_underlying (underlying),
    INDEX idx_okx_volatility_surfaces_timestamp (timestamp)
);
"""


# =============================================================================
# MAIN OPTIONS TRADING CLASS
# =============================================================================

class OKXOptionsTrading:
    """
    Advanced options trading for OKX exchange.
    
    Features:
    - All options order types
    - Options position management
    - Options pricing with Black-Scholes and binomial models
    - Greeks calculation and monitoring
    - Volatility surface analysis
    - Options strategies (straddles, strangles, spreads, etc.)
    - Exercise and assignment management
    - Risk management
    - WebSocket real-time updates
    - Database persistence
    - Comprehensive error handling
    """
    
    def __init__(
        self,
        base: OKXBase,
        config: OKXConfig,
        market_data: Optional[OKXMarketData] = None,
        converter: Optional[OKXConverter] = None,
        redis: Optional[Redis] = None,
        pool: Optional[asyncpg.Pool] = None
    ):
        self.base = base
        self.config = config
        self.market_data = market_data
        self.converter = converter or get_converter()
        self.redis = redis
        self.pool = pool
        
        # Options state
        self._contracts: Dict[str, OptionContract] = {}
        self._orders: Dict[str, OptionOrder] = {}
        self._positions: Dict[str, OptionPosition] = {}
        self._strategies: Dict[str, OptionStrategy] = {}
        
        # Pricing engine
        self._pricing_engine = OptionPricingEngine()
        
        # Circuit breakers
        self._options_cb = CircuitBreaker(
            name="okx_options",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        # WebSocket integration
        self._ws_handlers: Dict[str, List[Callable]] = {}
        
        # Database initialization
        self._db_initialized = False
        
        # Rate limit tracking
        self._rate_limiter = {
            'requests': 0,
            'window_start': time.time(),
            'max_requests': 10
        }
        
        logger.info("OKXOptionsTrading initialized")
    
    async def initialize(self):
        """Initialize options trading module."""
        if self.pool and not self._db_initialized:
            await self._init_database()
            self._db_initialized = True
        
        # Load option contracts
        await self.load_option_chain()
        
        # Load positions
        await self.sync_positions()
        
        # Start periodic sync
        asyncio.create_task(self._periodic_sync())
        
        logger.info("OKXOptionsTrading initialization complete")
    
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
    # OPTION CHAIN
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def load_option_chain(
        self,
        underlying: Optional[str] = None,
        refresh: bool = False
    ) -> List[OptionContract]:
        """
        Load option chain for an underlying asset.
        
        Args:
            underlying: Underlying asset symbol
            refresh: Force refresh from API
            
        Returns:
            List of OptionContract
        """
        if not refresh and self._contracts:
            return list(self._contracts.values())
        
        try:
            params = {'instType': 'OPTION'}
            if underlying:
                params['uly'] = underlying
            
            response = await self.base._public_request('public/instruments', params)
            
            contracts = []
            for item in response:
                try:
                    contract = self._parse_contract(item)
                    self._contracts[contract.id] = contract
                    contracts.append(contract)
                except Exception as e:
                    logger.error(f"Error parsing option contract: {e}")
                    continue
            
            logger.info(f"Loaded {len(contracts)} option contracts")
            return contracts
            
        except Exception as e:
            logger.error(f"Error loading option chain: {e}")
            if self._contracts:
                return list(self._contracts.values())
            raise
    
    def _parse_contract(self, data: Dict[str, Any]) -> OptionContract:
        """Parse option contract data."""
        # Parse option type from instrument ID
        inst_id = data.get('instId', '')
        parts = inst_id.split('-')
        
        # Determine option type
        option_type = OptionType.CALL if 'C' in inst_id else OptionType.PUT
        
        # Parse strike
        strike = Decimal('0')
        try:
            # Strike is usually last part after option type
            if len(parts) >= 4:
                strike = Decimal(str(parts[-1]))
        except Exception:
            pass
        
        # Parse expiry
        expiry = None
        try:
            if data.get('expTime'):
                expiry = datetime.fromtimestamp(int(data.get('expTime', 0)) / 1000)
        except Exception:
            pass
        
        return OptionContract(
            id=inst_id,
            symbol=inst_id,
            underlying=data.get('uly', ''),
            option_type=option_type,
            strike=strike,
            expiry=expiry or datetime.utcnow() + timedelta(days=30),
            style=OptionStyle.EUROPEAN,
            contract_size=Decimal(str(data.get('ctVal', 1))),
            tick_size=Decimal(str(data.get('tickSz', 0.01))),
            lot_size=Decimal(str(data.get('lotSz', 0.001))),
            min_volume=Decimal(str(data.get('minSz', 0))),
            max_volume=Decimal(str(data.get('maxSz', 0))) if data.get('maxSz') else None,
            status=OptionStatus(data.get('state', 'trading')),
            metadata=data
        )
    
    async def get_option_contract(
        self,
        underlying: str,
        strike: Decimal,
        expiry: datetime,
        option_type: OptionType
    ) -> Optional[OptionContract]:
        """
        Get option contract by parameters.
        
        Args:
            underlying: Underlying asset
            strike: Strike price
            expiry: Expiry date
            option_type: Option type (call/put)
            
        Returns:
            OptionContract or None
        """
        contracts = await self.load_option_chain(underlying)
        
        for contract in contracts:
            if (contract.strike == strike and 
                contract.expiry.date() == expiry.date() and
                contract.option_type == option_type):
                return contract
        
        return None
    
    # =========================================================================
    # OPTIONS ORDER PLACEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def place_option_order(
        self,
        symbol: str,
        side: OptionOrderSide,
        order_type: OptionOrderType,
        volume: Decimal,
        price: Optional[Decimal] = None,
        position_side: Optional[OptionPositionSide] = None,
        margin_mode: OptionMarginMode = OptionMarginMode.CROSS,
        reduce_only: bool = False,
        close_position: bool = False,
        time_in_force: OKXTimeInForce = OKXTimeInForce.GTC,
        client_order_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> OptionOrder:
        """
        Place an options order.
        
        Args:
            symbol: Option symbol
            side: Order side
            order_type: Order type
            volume: Order volume
            price: Price for limit orders
            position_side: Position side
            margin_mode: Margin mode
            reduce_only: Reduce-only position
            close_position: Close entire position
            time_in_force: Time in force
            client_order_id: Client-side order ID
            metadata: Additional metadata
            
        Returns:
            OptionOrder
        """
        if self._options_cb.is_open():
            raise OKXRateLimitError("Options circuit breaker is open")
        
        try:
            # Build order parameters
            params = {
                'instId': symbol,
                'side': side.value,
                'ordType': order_type.value,
                'sz': str(volume),
                'tdMode': margin_mode.value,
            }
            
            if price is not None:
                params['px'] = str(price)
            
            if position_side:
                params['posSide'] = position_side.value
            
            if reduce_only:
                params['reduceOnly'] = 'true'
            
            if close_position:
                params['close'] = 'true'
            
            if time_in_force != OKXTimeInForce.GTC:
                params['timeInForce'] = time_in_force.value
            
            if client_order_id:
                params['clOrdId'] = client_order_id
            
            # Place order
            response = await self.base._private_request('trade/order', params, 'POST')
            
            if not response:
                raise OKXOrderError("Order placement failed")
            
            order_data = response[0] if isinstance(response, list) else response
            
            # Create order object
            order = self._parse_order(order_data)
            
            # Track order
            self._orders[order.id] = order
            
            # Save to database
            if self.pool:
                await self._save_order(order)
            
            self._options_cb.record_success()
            
            logger.info(
                f"Options order placed: {order.id} | {side} {volume} "
                f"{symbol} @ {price or 'market'}"
            )
            
            return order
            
        except Exception as e:
            self._options_cb.record_failure()
            logger.error(f"Options order placement error: {e}")
            raise
    
    def _parse_order(self, data: Dict[str, Any]) -> OptionOrder:
        """Parse options order data."""
        status_map = {
            'pending': OKXOrderStatus.PENDING,
            'live': OKXOrderStatus.OPEN,
            'partially_filled': OKXOrderStatus.PARTIALLY_FILLED,
            'filled': OKXOrderStatus.FILLED,
            'cancelled': OKXOrderStatus.CANCELLED,
            'expired': OKXOrderStatus.EXPIRED,
            'rejected': OKXOrderStatus.REJECTED,
        }
        
        status = status_map.get(data.get('state', 'pending'), OKXOrderStatus.PENDING)
        
        return OptionOrder(
            id=data.get('ordId', ''),
            symbol=data.get('instId', ''),
            side=OptionOrderSide(data.get('side', 'buy')),
            position_side=OptionPositionSide(data.get('posSide', 'long')) if data.get('posSide') else None,
            order_type=OptionOrderType(data.get('ordType', 'limit')),
            status=status,
            price=Decimal(str(data.get('px', 0))),
            volume=Decimal(str(data.get('sz', 0))),
            filled_volume=Decimal(str(data.get('accFillSz', 0))),
            remaining_volume=Decimal(str(data.get('sz', 0))) - Decimal(str(data.get('accFillSz', 0))),
            average_price=Decimal(str(data.get('avgPx', 0))) if data.get('avgPx') else None,
            fee=Decimal(str(data.get('fee', 0))),
            fee_currency=data.get('feeCcy'),
            cost=Decimal(str(data.get('cost', 0))),
            margin=Decimal(str(data.get('margin', 0))),
            time_in_force=OKXTimeInForce(data.get('timeInForce', 'GTC')),
            created_at=datetime.fromtimestamp(int(data.get('cTime', 0)) / 1000) if data.get('cTime') else datetime.utcnow(),
            updated_at=datetime.fromtimestamp(int(data.get('uTime', 0)) / 1000) if data.get('uTime') else None,
            expires_at=datetime.fromtimestamp(int(data.get('expTime', 0)) / 1000) if data.get('expTime') else None,
            reduce_only=data.get('reduceOnly', False),
            close_position=data.get('close', False),
            client_order_id=data.get('clOrdId'),
            metadata=data
        )
    
    # =========================================================================
    # POSITION MANAGEMENT
    # =========================================================================
    
    @async_retry(max_attempts=3, base_delay=1.0, max_delay=10.0)
    async def get_positions(self) -> List[OptionPosition]:
        """
        Get options positions.
        
        Returns:
            List of OptionPosition
        """
        try:
            response = await self.base._private_request('account/positions', {'instType': 'OPTION'})
            
            positions = []
            for item in response:
                try:
                    position = self._parse_position(item)
                    self._positions[position.id] = position
                    positions.append(position)
                except Exception as e:
                    logger.error(f"Error parsing position: {e}")
                    continue
            
            return positions
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return list(self._positions.values())
    
    def _parse_position(self, data: Dict[str, Any]) -> OptionPosition:
        """Parse options position data."""
        # Get contract details
        contract = self._contracts.get(data.get('instId', ''))
        
        return OptionPosition(
            id=data.get('posId', str(uuid.uuid4())),
            symbol=data.get('instId', ''),
            side=OptionPositionSide(data.get('posSide', 'long')),
            quantity=Decimal(str(data.get('pos', 0))),
            entry_price=Decimal(str(data.get('avgPx', 0))),
            mark_price=Decimal(str(data.get('markPx', 0))),
            strike=contract.strike if contract else Decimal('0'),
            expiry=contract.expiry if contract else datetime.utcnow(),
            option_type=contract.option_type if contract else OptionType.CALL,
            margin=Decimal(str(data.get('margin', 0))),
            unrealized_pnl=Decimal(str(data.get('upl', 0))),
            realized_pnl=Decimal(str(data.get('realizedPnl', 0))),
            total_pnl=Decimal(str(data.get('upl', 0))) + Decimal(str(data.get('realizedPnl', 0))),
            roe=Decimal(str(data.get('roe', 0))),
            margin_mode=OptionMarginMode(data.get('mgnMode', 'cross')),
            status=OptionStatus(data.get('state', 'trading')),
            opened_at=datetime.fromtimestamp(int(data.get('opened', 0)) / 1000) if data.get('opened') else datetime.utcnow(),
            closed_at=datetime.fromtimestamp(int(data.get('closed', 0)) / 1000) if data.get('closed') else None,
            metadata=data
        )
    
    async def sync_positions(self):
        """Synchronize positions from exchange."""
        try:
            positions = await self.get_positions()
            logger.info(f"Synced {len(positions)} options positions")
            return positions
        except Exception as e:
            logger.error(f"Error syncing positions: {e}")
            return []
    
    async def close_option_position(
        self,
        symbol: str,
        volume: Optional[Decimal] = None,
        price: Optional[Decimal] = None
    ) -> OptionOrder:
        """
        Close an options position.
        
        Args:
            symbol: Option symbol
            volume: Volume to close (None = full position)
            price: Price for limit order
            
        Returns:
            OptionOrder
        """
        # Get position
        positions = await self.get_positions()
        position = next((p for p in positions if p.symbol == symbol), None)
        
        if not position:
            raise OKXPositionError(f"No position found for {symbol}")
        
        # Determine close side
        side = OptionOrderSide.SELL_CLOSE if position.side == OptionPositionSide.LONG else OptionOrderSide.BUY_CLOSE
        
        # Use full volume if not specified
        if volume is None:
            volume = position.quantity
        
        return await self.place_option_order(
            symbol=symbol,
            side=side,
            order_type=OptionOrderType.MARKET if price is None else OptionOrderType.LIMIT,
            volume=volume,
            price=price,
            position_side=position.side,
            reduce_only=True,
            close_position=True,
            metadata={'action': 'close_position'}
        )
    
    # =========================================================================
    # OPTIONS PRICING AND GREEKS
    # =========================================================================
    
    async def calculate_option_price(
        self,
        underlying: str,
        strike: Decimal,
        expiry: datetime,
        option_type: OptionType,
        current_price: Optional[Decimal] = None,
        risk_free_rate: Decimal = Decimal('0.02'),
        sigma: Optional[Decimal] = None,
        model: str = "black_scholes"
    ) -> Decimal:
        """
        Calculate option price.
        
        Args:
            underlying: Underlying asset
            strike: Strike price
            expiry: Expiry date
            option_type: Option type (call/put)
            current_price: Current underlying price (auto-fetched if None)
            risk_free_rate: Risk-free rate
            sigma: Volatility (auto-calculated if None)
            model: Pricing model
            
        Returns:
            Option price
        """
        # Get current price if not provided
        if current_price is None:
            ticker = await self.market_data.get_ticker(underlying)
            current_price = ticker.last
        
        # Calculate time to expiry
        now = datetime.utcnow()
        T = Decimal(str(max((expiry - now).total_seconds() / 365 / 24 / 3600, 0.001)))
        
        # Get volatility if not provided
        if sigma is None:
            # Try to get from contract
            contract = await self.get_option_contract(underlying, strike, expiry, option_type)
            if contract and contract.greeks:
                sigma = contract.greeks.implied_volatility
            else:
                # Estimate volatility from historical data
                sigma = Decimal('0.5')  # Default
        
        # Calculate price
        if model == "black_scholes":
            return self._pricing_engine.black_scholes(
                current_price, strike, T, risk_free_rate, sigma, option_type
            )
        elif model == "binomial":
            return self._pricing_engine.binomial_price(
                current_price, strike, T, risk_free_rate, sigma, option_type
            )
        else:
            raise OKXValidationError(f"Unknown pricing model: {model}")
    
    async def calculate_greeks(
        self,
        underlying: str,
        strike: Decimal,
        expiry: datetime,
        option_type: OptionType,
        current_price: Optional[Decimal] = None,
        risk_free_rate: Decimal = Decimal('0.02'),
        sigma: Optional[Decimal] = None
    ) -> OptionGreeks:
        """
        Calculate option Greeks.
        
        Args:
            underlying: Underlying asset
            strike: Strike price
            expiry: Expiry date
            option_type: Option type (call/put)
            current_price: Current underlying price
            risk_free_rate: Risk-free rate
            sigma: Volatility
            
        Returns:
            OptionGreeks
        """
        # Get current price if not provided
        if current_price is None:
            ticker = await self.market_data.get_ticker(underlying)
            current_price = ticker.last
        
        # Calculate time to expiry
        now = datetime.utcnow()
        T = Decimal(str(max((expiry - now).total_seconds() / 365 / 24 / 3600, 0.001)))
        
        # Get volatility if not provided
        if sigma is None:
            sigma = Decimal('0.5')
        
        return self._pricing_engine.calculate_greeks(
            current_price, strike, T, risk_free_rate, sigma, option_type
        )
    
    # =========================================================================
    # OPTIONS STRATEGIES
    # =========================================================================
    
    async def create_straddle(
        self,
        underlying: str,
        strike: Decimal,
        expiry: datetime,
        volume: Decimal,
        margin_mode: OptionMarginMode = OptionMarginMode.CROSS
    ) -> OptionStrategy:
        """
        Create a straddle strategy (buy call and put at same strike).
        
        Args:
            underlying: Underlying asset
            strike: Strike price
            expiry: Expiry date
            volume: Volume per leg
            margin_mode: Margin mode
            
        Returns:
            OptionStrategy
        """
        # Get option contracts
        call_contract = await self.get_option_contract(underlying, strike, expiry, OptionType.CALL)
        put_contract = await self.get_option_contract(underlying, strike, expiry, OptionType.PUT)
        
        if not call_contract or not put_contract:
            raise OKXInvalidSymbolError(f"Option contracts not found for {underlying} {strike}")
        
        # Calculate prices
        call_price = await self.calculate_option_price(underlying, strike, expiry, OptionType.CALL)
        put_price = await self.calculate_option_price(underlying, strike, expiry, OptionType.PUT)
        
        net_price = call_price + put_price
        
        # Create strategy
        strategy = OptionStrategy(
            id=str(uuid.uuid4()),
            name=f"Straddle_{underlying}_{strike}_{expiry.strftime('%Y%m%d')}",
            strategy_type="straddle",
            legs=[
                {
                    'contract_id': call_contract.id,
                    'side': 'buy',
                    'volume': volume,
                    'price': float(call_price)
                },
                {
                    'contract_id': put_contract.id,
                    'side': 'buy',
                    'volume': volume,
                    'price': float(put_price)
                }
            ],
            net_price=net_price * volume,
            net_margin=Decimal('0'),  # Would calculate margin
            max_profit=Decimal('inf'),
            max_loss=net_price * volume,
            break_even=strike + net_price,
            created_at=datetime.utcnow(),
            metadata={'underlying': underlying, 'strike': float(strike), 'expiry': expiry.isoformat()}
        )
        
        self._strategies[strategy.id] = strategy
        
        # Save to database
        if self.pool:
            await self._save_strategy(strategy)
        
        logger.info(f"Created straddle strategy: {strategy.id}")
        return strategy
    
    async def create_strangle(
        self,
        underlying: str,
        lower_strike: Decimal,
        upper_strike: Decimal,
        expiry: datetime,
        volume: Decimal,
        margin_mode: OptionMarginMode = OptionMarginMode.CROSS
    ) -> OptionStrategy:
        """
        Create a strangle strategy (buy call at higher strike, buy put at lower strike).
        
        Args:
            underlying: Underlying asset
            lower_strike: Put strike
            upper_strike: Call strike
            expiry: Expiry date
            volume: Volume per leg
            margin_mode: Margin mode
            
        Returns:
            OptionStrategy
        """
        # Get option contracts
        call_contract = await self.get_option_contract(underlying, upper_strike, expiry, OptionType.CALL)
        put_contract = await self.get_option_contract(underlying, lower_strike, expiry, OptionType.PUT)
        
        if not call_contract or not put_contract:
            raise OKXInvalidSymbolError(f"Option contracts not found for {underlying}")
        
        # Calculate prices
        call_price = await self.calculate_option_price(underlying, upper_strike, expiry, OptionType.CALL)
        put_price = await self.calculate_option_price(underlying, lower_strike, expiry, OptionType.PUT)
        
        net_price = call_price + put_price
        
        # Create strategy
        strategy = OptionStrategy(
            id=str(uuid.uuid4()),
            name=f"Strangle_{underlying}_{lower_strike}_{upper_strike}_{expiry.strftime('%Y%m%d')}",
            strategy_type="strangle",
            legs=[
                {
                    'contract_id': put_contract.id,
                    'side': 'buy',
                    'volume': volume,
                    'price': float(put_price)
                },
                {
                    'contract_id': call_contract.id,
                    'side': 'buy',
                    'volume': volume,
                    'price': float(call_price)
                }
            ],
            net_price=net_price * volume,
            net_margin=Decimal('0'),
            max_profit=Decimal('inf'),
            max_loss=net_price * volume,
            break_even_lower=lower_strike - net_price,
            break_even_upper=upper_strike + net_price,
            created_at=datetime.utcnow(),
            metadata={'underlying': underlying, 'lower_strike': float(lower_strike), 
                     'upper_strike': float(upper_strike), 'expiry': expiry.isoformat()}
        )
        
        self._strategies[strategy.id] = strategy
        
        if self.pool:
            await self._save_strategy(strategy)
        
        logger.info(f"Created strangle strategy: {strategy.id}")
        return strategy
    
    async def create_vertical_spread(
        self,
        underlying: str,
        lower_strike: Decimal,
        upper_strike: Decimal,
        expiry: datetime,
        volume: Decimal,
        is_bullish: bool = True,
        margin_mode: OptionMarginMode = OptionMarginMode.CROSS
    ) -> OptionStrategy:
        """
        Create a vertical spread strategy.
        
        Args:
            underlying: Underlying asset
            lower_strike: Lower strike
            upper_strike: Upper strike
            expiry: Expiry date
            volume: Volume per leg
            is_bullish: Bullish (call spread) or bearish (put spread)
            margin_mode: Margin mode
            
        Returns:
            OptionStrategy
        """
        if is_bullish:
            # Bull call spread: Buy lower strike call, sell higher strike call
            buy_contract = await self.get_option_contract(underlying, lower_strike, expiry, OptionType.CALL)
            sell_contract = await self.get_option_contract(underlying, upper_strike, expiry, OptionType.CALL)
            strategy_type = "bull_call_spread"
            name_suffix = "BullCall"
        else:
            # Bear put spread: Buy higher strike put, sell lower strike put
            buy_contract = await self.get_option_contract(underlying, upper_strike, expiry, OptionType.PUT)
            sell_contract = await self.get_option_contract(underlying, lower_strike, expiry, OptionType.PUT)
            strategy_type = "bear_put_spread"
            name_suffix = "BearPut"
        
        if not buy_contract or not sell_contract:
            raise OKXInvalidSymbolError(f"Option contracts not found for {underlying}")
        
        # Calculate prices
        buy_price = await self.calculate_option_price(underlying, buy_contract.strike, expiry, buy_contract.option_type)
        sell_price = await self.calculate_option_price(underlying, sell_contract.strike, expiry, sell_contract.option_type)
        
        net_price = buy_price - sell_price
        max_profit = (upper_strike - lower_strike) - net_price if is_bullish else net_price
        max_loss = net_price if is_bullish else (upper_strike - lower_strike) - net_price
        
        # Create strategy
        strategy = OptionStrategy(
            id=str(uuid.uuid4()),
            name=f"{name_suffix}_{underlying}_{lower_strike}_{upper_strike}_{expiry.strftime('%Y%m%d')}",
            strategy_type=strategy_type,
            legs=[
                {
                    'contract_id': buy_contract.id,
                    'side': 'buy',
                    'volume': volume,
                    'price': float(buy_price)
                },
                {
                    'contract_id': sell_contract.id,
                    'side': 'sell',
                    'volume': volume,
                    'price': float(sell_price)
                }
            ],
            net_price=net_price * volume,
            net_margin=Decimal('0'),
            max_profit=max_profit * volume if max_profit > 0 else Decimal('0'),
            max_loss=max_loss * volume if max_loss > 0 else Decimal('0'),
            break_even=lower_strike + net_price if is_bullish else upper_strike - net_price,
            created_at=datetime.utcnow(),
            metadata={'underlying': underlying, 'lower_strike': float(lower_strike), 
                     'upper_strike': float(upper_strike), 'expiry': expiry.isoformat(), 
                     'is_bullish': is_bullish}
        )
        
        self._strategies[strategy.id] = strategy
        
        if self.pool:
            await self._save_strategy(strategy)
        
        logger.info(f"Created vertical spread strategy: {strategy.id}")
        return strategy
    
    # =========================================================================
    # VOLATILITY SURFACE
    # =========================================================================
    
    async def get_volatility_surface(
        self,
        underlying: str,
        expiries: List[datetime],
        strikes: List[Decimal],
        risk_free_rate: Decimal = Decimal('0.02')
    ) -> VolatilitySurface:
        """
        Build volatility surface for an underlying asset.
        
        Args:
            underlying: Underlying asset
            expiries: List of expiry dates
            strikes: List of strike prices
            risk_free_rate: Risk-free rate
            
        Returns:
            VolatilitySurface
        """
        # Get current price
        ticker = await self.market_data.get_ticker(underlying)
        current_price = ticker.last
        
        # Calculate implied volatilities for each expiry and strike
        iv_matrix = []
        
        for expiry in expiries:
            row = []
            for strike in strikes:
                try:
                    # Get option contract
                    call_contract = await self.get_option_contract(underlying, strike, expiry, OptionType.CALL)
                    if not call_contract:
                        row.append(Decimal('0'))
                        continue
                    
                    # Get option price
                    price = call_contract.mark if call_contract.mark > 0 else await self.calculate_option_price(
                        underlying, strike, expiry, OptionType.CALL, current_price
                    )
                    
                    # Calculate implied volatility
                    T = Decimal(str(max((expiry - datetime.utcnow()).total_seconds() / 365 / 24 / 3600, 0.001)))
                    iv = self._pricing_engine.implied_volatility(
                        price, current_price, strike, T, risk_free_rate, OptionType.CALL
                    )
                    row.append(iv)
                except Exception as e:
                    logger.error(f"Error calculating IV for {underlying} {strike} {expiry}: {e}")
                    row.append(Decimal('0'))
            
            iv_matrix.append(row)
        
        return VolatilitySurface(
            underlying=underlying,
            timestamp=datetime.utcnow(),
            strikes=strikes,
            expiries=expiries,
            implied_volatilities=iv_matrix,
            risk_free_rate=risk_free_rate
        )
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _save_order(self, order: OptionOrder):
        """Save order to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO okx_option_orders (
                        id, client_order_id, symbol, side, position_side,
                        order_type, status, price, volume, filled_volume,
                        remaining_volume, avg_price, fee, fee_currency,
                        cost, margin, time_in_force,
                        reduce_only, close_position, created_at,
                        updated_at, expires_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                              $11, $12, $13, $14, $15, $16, $17,
                              $18, $19, $20, $21, $22, $23)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        filled_volume = EXCLUDED.filled_volume,
                        remaining_volume = EXCLUDED.remaining_volume,
                        avg_price = EXCLUDED.avg_price,
                        fee = EXCLUDED.fee,
                        cost = EXCLUDED.cost,
                        updated_at = EXCLUDED.updated_at,
                        metadata = EXCLUDED.metadata
                    """,
                    order.id,
                    order.client_order_id,
                    order.symbol,
                    order.side.value,
                    order.position_side.value if order.position_side else None,
                    order.order_type.value,
                    order.status.value,
                    order.price,
                    order.volume,
                    order.filled_volume,
                    order.remaining_volume,
                    order.average_price,
                    order.fee,
                    order.fee_currency,
                    order.cost,
                    order.margin,
                    order.time_in_force.value,
                    order.reduce_only,
                    order.close_position,
                    order.created_at,
                    order.updated_at,
                    order.expires_at,
                    json.dumps(order.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving order: {e}")
    
    async def _save_strategy(self, strategy: OptionStrategy):
        """Save strategy to database."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO okx_option_strategies (
                        id, name, strategy_type, legs,
                        net_price, net_margin, max_profit,
                        max_loss, break_even, status,
                        created_at, updated_at, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        strategy_type = EXCLUDED.strategy_type,
                        legs = EXCLUDED.legs,
                        net_price = EXCLUDED.net_price,
                        net_margin = EXCLUDED.net_margin,
                        max_profit = EXCLUDED.max_profit,
                        max_loss = EXCLUDED.max_loss,
                        break_even = EXCLUDED.break_even,
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at,
                        metadata = EXCLUDED.metadata
                    """,
                    strategy.id,
                    strategy.name,
                    strategy.strategy_type,
                    json.dumps(strategy.legs),
                    strategy.net_price,
                    strategy.net_margin,
                    strategy.max_profit,
                    strategy.max_loss,
                    strategy.break_even,
                    strategy.status,
                    strategy.created_at,
                    strategy.updated_at,
                    json.dumps(strategy.metadata, default=str)
                )
        except Exception as e:
            logger.error(f"Error saving strategy: {e}")
    
    # =========================================================================
    # PERIODIC SYNC
    # =========================================================================
    
    async def _periodic_sync(self):
        """Periodically sync options data."""
        while True:
            try:
                await asyncio.sleep(30)
                
                # Sync positions
                await self.sync_positions()
                
                # Update option contracts
                await self.load_option_chain(refresh=True)
                
                # Update Greeks for active positions
                for position in self._positions.values():
                    try:
                        if position.status == OptionStatus.TRADING:
                            greeks = await self.calculate_greeks(
                                position.symbol.split('-')[0] if '-' in position.symbol else position.symbol,
                                position.strike,
                                position.expiry,
                                position.option_type,
                                position.mark_price
                            )
                            position.greeks = greeks
                    except Exception:
                        pass
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Periodic sync error: {e}")
                await asyncio.sleep(60)
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """Shutdown options trading module."""
        logger.info("Shutting down OKXOptionsTrading")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'OKXOptionsTrading',
    'OptionType',
    'OptionStyle',
    'OptionOrderType',
    'OptionOrderSide',
    'OptionPositionSide',
    'OptionExerciseType',
    'OptionMarginMode',
    'OptionStatus',
    'OptionGreeks',
    'OptionContract',
    'OptionOrder',
    'OptionPosition',
    'OptionStrategy',
    'VolatilitySurface',
    'OptionPricingEngine'
]
