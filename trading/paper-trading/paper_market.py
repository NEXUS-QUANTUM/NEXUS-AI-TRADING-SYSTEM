"""
NEXUS AI TRADING SYSTEM - Paper Trading Market Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/paper-trading/paper_market.py
Description: Paper trading market simulation with full API integration
"""

import asyncio
import logging
import math
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.paper_trading_config import PaperTradingConfig
from shared.constants.trading_constants import TIME_FRAMES, ASSET_CLASSES
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class MarketStatus(str, Enum):
    """Market status"""
    OPEN = "open"
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    AFTER_HOURS = "after_hours"
    HOLIDAY = "holiday"
    CIRCUIT_BREAKER = "circuit_breaker"


class MarketCondition(str, Enum):
    """Market conditions"""
    NORMAL = "normal"
    VOLATILE = "volatile"
    HIGH_VOLATILITY = "high_volatility"
    EXTREME_VOLATILITY = "extreme_volatility"
    TRENDING = "trending"
    RANGING = "ranging"
    BREAKOUT = "breakout"


class OrderBookDepth(str, Enum):
    """Order book depth levels"""
    LEVEL_1 = "level_1"  # Best bid/ask only
    LEVEL_2 = "level_2"  # Top 10 levels
    LEVEL_3 = "level_3"  # Full order book


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class MarketDataRequest(BaseModel):
    """Request model for market data"""
    symbol: str
    depth: OrderBookDepth = OrderBookDepth.LEVEL_1
    include_order_book: bool = True
    include_trades: bool = True
    include_indicators: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MarketDataResponse(BaseModel):
    """Response model for market data"""
    symbol: str
    timestamp: datetime
    price: float
    bid: float
    ask: float
    spread: float
    volume: float
    high: float
    low: float
    open: float
    close: float
    change: float
    change_pct: float
    market_status: MarketStatus
    market_condition: MarketCondition
    order_book: Dict[str, Any]
    indicators: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrderBookResponse(BaseModel):
    """Response model for order book"""
    symbol: str
    timestamp: datetime
    bids: List[List[float]]  # [[price, size], ...]
    asks: List[List[float]]  # [[price, size], ...]
    depth: int
    imbalance: float
    spread: float
    mid_price: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TradeDataResponse(BaseModel):
    """Response model for trade data"""
    symbol: str
    timestamp: datetime
    price: float
    size: float
    side: str  # buy, sell
    volume: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MarketContext:
    """Context for market simulation"""
    symbol: str
    price: float
    bid: float
    ask: float
    spread: float
    volume: float
    volatility: float
    market_status: MarketStatus
    market_condition: MarketCondition
    order_book: Dict[str, Any]
    timestamp: datetime
    history: List[Dict[str, Any]]


@dataclass
class PriceBar:
    """Price bar data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int


@dataclass
class OrderBookLevel:
    """Order book level"""
    price: float
    size: float
    order_count: int


# =============================================================================
# PAPER TRADING MARKET
# =============================================================================

class PaperTradingMarket:
    """
    Paper Trading Market Simulation with full API integration.
    
    Features:
    - Realistic market simulation
    - Order book management
    - Price generation
    - Volume simulation
    - Market conditions
    - Historical data
    - Indicator calculation
    - Multiple symbols support
    """

    def __init__(
        self,
        config: Optional[PaperTradingConfig] = None,
        broker_factory: Optional[BrokerFactory] = None
    ):
        """
        Initialize PaperTradingMarket.
        
        Args:
            config: Paper trading configuration
            broker_factory: Factory for broker instances
        """
        self.config = config or PaperTradingConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        
        # Market data
        self._market_data: Dict[str, MarketContext] = {}
        self._price_history: Dict[str, List[PriceBar]] = {}
        self._order_books: Dict[str, Dict[str, Any]] = {}
        
        # Market configuration
        self._symbol_configs: Dict[str, Dict[str, Any]] = {}
        
        # Price cache
        self._price_cache: Dict[str, Dict[str, Any]] = {}
        
        # Monitoring
        self._is_running: bool = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Default symbols
        self._default_symbols = ['BTC-USD', 'ETH-USD', 'SPY', 'AAPL', 'MSFT', 'GOOGL', 'AMZN']
        
        # Initialize default symbols
        self._init_default_symbols()
        
        logger.info("PaperTradingMarket initialized")

    def _init_default_symbols(self) -> None:
        """Initialize default symbols"""
        for symbol in self._default_symbols:
            self._symbol_configs[symbol] = {
                'base_price': self._get_base_price(symbol),
                'volatility': self._get_volatility(symbol),
                'volume': self._get_volume(symbol),
                'spread': self._get_spread(symbol),
                'asset_class': self._get_asset_class(symbol)
            }
            self._price_history[symbol] = []
            self._order_books[symbol] = self._create_order_book(symbol)

    def _get_base_price(self, symbol: str) -> float:
        """Get base price for symbol"""
        base_prices = {
            'BTC-USD': 50000,
            'ETH-USD': 3000,
            'SPY': 500,
            'AAPL': 150,
            'MSFT': 350,
            'GOOGL': 140,
            'AMZN': 180
        }
        return base_prices.get(symbol, 100)

    def _get_volatility(self, symbol: str) -> float:
        """Get volatility for symbol"""
        volatilities = {
            'BTC-USD': 0.02,
            'ETH-USD': 0.025,
            'SPY': 0.01,
            'AAPL': 0.015,
            'MSFT': 0.012,
            'GOOGL': 0.013,
            'AMZN': 0.016
        }
        return volatilities.get(symbol, 0.015)

    def _get_volume(self, symbol: str) -> float:
        """Get volume for symbol"""
        volumes = {
            'BTC-USD': 1000000,
            'ETH-USD': 500000,
            'SPY': 10000000,
            'AAPL': 5000000,
            'MSFT': 3000000,
            'GOOGL': 2000000,
            'AMZN': 2500000
        }
        return volumes.get(symbol, 1000000)

    def _get_spread(self, symbol: str) -> float:
        """Get spread for symbol"""
        spreads = {
            'BTC-USD': 0.001,
            'ETH-USD': 0.0015,
            'SPY': 0.0005,
            'AAPL': 0.0005,
            'MSFT': 0.0005,
            'GOOGL': 0.0005,
            'AMZN': 0.0005
        }
        return spreads.get(symbol, 0.001)

    def _get_asset_class(self, symbol: str) -> str:
        """Get asset class for symbol"""
        crypto = ['BTC-USD', 'ETH-USD']
        equity = ['SPY', 'AAPL', 'MSFT', 'GOOGL', 'AMZN']
        
        if symbol in crypto:
            return 'crypto'
        elif symbol in equity:
            return 'equity'
        else:
            return 'equity'

    # =========================================================================
    # Market Data
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def get_market_data(
        self,
        request: MarketDataRequest
    ) -> MarketDataResponse:
        """
        Get market data for a symbol.
        
        Args:
            request: Market data request
            
        Returns:
            MarketDataResponse: Market data
        """
        try:
            # Get or create market context
            context = await self._get_market_context(request.symbol)
            
            # Get order book
            order_book = {}
            if request.include_order_book:
                order_book = self._get_order_book(request.symbol, request.depth)
            
            # Get indicators
            indicators = {}
            if request.include_indicators:
                indicators = await self._calculate_indicators(request.symbol)
            
            # Create response
            response = MarketDataResponse(
                symbol=request.symbol,
                timestamp=context.timestamp,
                price=context.price,
                bid=context.bid,
                ask=context.ask,
                spread=context.spread,
                volume=context.volume,
                high=context.price * 1.01,
                low=context.price * 0.99,
                open=context.price,
                close=context.price,
                change=0,
                change_pct=0,
                market_status=context.market_status,
                market_condition=context.market_condition,
                order_book=order_book,
                indicators=indicators,
                metadata=request.metadata
            )
            
            # Cache
            self._price_cache[request.symbol] = {
                'data': response,
                'timestamp': datetime.utcnow()
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting market data: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Market data retrieval failed: {str(e)}"
            )

    async def _get_market_context(self, symbol: str) -> MarketContext:
        """Get or create market context"""
        if symbol in self._market_data:
            # Update price
            context = self._market_data[symbol]
            new_price = self._generate_price(context)
            context.price = new_price
            context.bid = new_price * (1 - context.spread / 2)
            context.ask = new_price * (1 + context.spread / 2)
            context.timestamp = datetime.utcnow()
            
            # Update history
            self._update_history(symbol, context)
            
            return context
        
        # Create new context
        config = self._symbol_configs.get(symbol, {})
        base_price = config.get('base_price', 100)
        volatility = config.get('volatility', 0.015)
        volume = config.get('volume', 1000000)
        spread = config.get('spread', 0.001)
        
        context = MarketContext(
            symbol=symbol,
            price=base_price,
            bid=base_price * (1 - spread / 2),
            ask=base_price * (1 + spread / 2),
            spread=spread,
            volume=volume,
            volatility=volatility,
            market_status=MarketStatus.OPEN,
            market_condition=MarketCondition.NORMAL,
            order_book=self._create_order_book(symbol, base_price),
            timestamp=datetime.utcnow(),
            history=[]
        )
        
        self._market_data[symbol] = context
        
        # Initialize history
        self._price_history[symbol] = []
        
        return context

    def _generate_price(self, context: MarketContext) -> float:
        """Generate new price"""
        # Random walk with volatility
        returns = np.random.normal(0, context.volatility)
        new_price = context.price * (1 + returns)
        
        # Apply market condition adjustments
        if context.market_condition == MarketCondition.VOLATILE:
            new_price *= (1 + np.random.normal(0, context.volatility * 0.5))
        elif context.market_condition == MarketCondition.HIGH_VOLATILITY:
            new_price *= (1 + np.random.normal(0, context.volatility))
        elif context.market_condition == MarketCondition.EXTREME_VOLATILITY:
            new_price *= (1 + np.random.normal(0, context.volatility * 1.5))
        
        # Ensure price is positive
        return max(new_price, 0.01)

    def _update_history(self, symbol: str, context: MarketContext) -> None:
        """Update price history"""
        bar = PriceBar(
            timestamp=context.timestamp,
            open=context.price,
            high=context.price * 1.005,
            low=context.price * 0.995,
            close=context.price,
            volume=context.volume * np.random.uniform(0.5, 1.5),
            trades=int(np.random.uniform(10, 100))
        )
        
        if symbol not in self._price_history:
            self._price_history[symbol] = []
        
        self._price_history[symbol].append(bar)
        
        # Keep history manageable
        if len(self._price_history[symbol]) > 10000:
            self._price_history[symbol] = self._price_history[symbol][-5000:]

    # =========================================================================
    # Order Book
    # =========================================================================

    def _create_order_book(self, symbol: str, price: float = None) -> Dict[str, Any]:
        """Create order book"""
        if price is None:
            price = self._get_base_price(symbol)
        
        spread = self._get_spread(symbol)
        bid = price * (1 - spread / 2)
        ask = price * (1 + spread / 2)
        
        # Create bid levels
        bids = []
        for i in range(10):
            level_price = bid - (i * 0.01)
            level_size = np.random.uniform(10, 100) * 100
            bids.append([level_price, level_size])
        
        # Create ask levels
        asks = []
        for i in range(10):
            level_price = ask + (i * 0.01)
            level_size = np.random.uniform(10, 100) * 100
            asks.append([level_price, level_size])
        
        return {
            'bids': bids,
            'asks': asks,
            'timestamp': datetime.utcnow()
        }

    def _get_order_book(
        self,
        symbol: str,
        depth: OrderBookDepth = OrderBookDepth.LEVEL_1
    ) -> Dict[str, Any]:
        """Get order book"""
        if symbol not in self._order_books:
            self._order_books[symbol] = self._create_order_book(symbol)
        
        order_book = self._order_books[symbol]
        
        # Update order book based on market activity
        context = self._market_data.get(symbol)
        if context:
            # Update prices
            bids = order_book['bids']
            asks = order_book['asks']
            
            # Update bid levels
            for i, level in enumerate(bids):
                if i == 0:
                    level[0] = context.bid
                else:
                    level[0] = context.bid - (i * 0.01)
                level[1] = np.random.uniform(10, 100) * 100
            
            # Update ask levels
            for i, level in enumerate(asks):
                if i == 0:
                    level[0] = context.ask
                else:
                    level[0] = context.ask + (i * 0.01)
                level[1] = np.random.uniform(10, 100) * 100
        
        # Filter by depth
        if depth == OrderBookDepth.LEVEL_1:
            return {
                'bids': order_book['bids'][:1],
                'asks': order_book['asks'][:1]
            }
        elif depth == OrderBookDepth.LEVEL_2:
            return {
                'bids': order_book['bids'][:10],
                'asks': order_book['asks'][:10]
            }
        else:
            return order_book

    async def get_order_book(
        self,
        symbol: str,
        depth: OrderBookDepth = OrderBookDepth.LEVEL_1
    ) -> OrderBookResponse:
        """
        Get order book for a symbol.
        
        Args:
            symbol: Symbol
            depth: Order book depth
            
        Returns:
            OrderBookResponse: Order book data
        """
        try:
            order_book = self._get_order_book(symbol, depth)
            
            # Calculate mid price and spread
            bids = order_book['bids']
            asks = order_book['asks']
            best_bid = bids[0][0] if bids else 0
            best_ask = asks[0][0] if asks else 0
            mid_price = (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else 0
            spread = best_ask - best_bid if best_ask > best_bid else 0
            
            # Calculate imbalance
            bid_volume = sum(level[1] for level in bids)
            ask_volume = sum(level[1] for level in asks)
            total_volume = bid_volume + ask_volume
            imbalance = (bid_volume - ask_volume) / total_volume if total_volume > 0 else 0
            
            return OrderBookResponse(
                symbol=symbol,
                timestamp=datetime.utcnow(),
                bids=order_book['bids'],
                asks=order_book['asks'],
                depth=len(order_book['bids']),
                imbalance=imbalance,
                spread=spread,
                mid_price=mid_price,
                metadata={}
            )
            
        except Exception as e:
            logger.error(f"Error getting order book: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Order book retrieval failed: {str(e)}"
            )

    # =========================================================================
    # Trade Simulation
    # =========================================================================

    async def simulate_trade(
        self,
        symbol: str,
        side: str,
        size: float
    ) -> Dict[str, Any]:
        """
        Simulate a trade.
        
        Args:
            symbol: Symbol
            side: Buy or sell
            size: Trade size
            
        Returns:
            Dict[str, Any]: Trade result
        """
        try:
            # Get market context
            context = await self._get_market_context(symbol)
            
            # Determine price based on side
            if side == 'buy':
                price = context.ask
            else:
                price = context.bid
            
            # Apply slippage for large orders
            slippage = size / context.volume * 0.01
            slippage = min(slippage, 0.01)
            
            if side == 'buy':
                price *= (1 + slippage)
            else:
                price *= (1 - slippage)
            
            # Update order book
            self._update_order_book(symbol, side, size, price)
            
            # Create trade result
            trade = {
                'symbol': symbol,
                'side': side,
                'size': size,
                'price': price,
                'value': size * price,
                'timestamp': datetime.utcnow()
            }
            
            # Update volume
            context.volume += size
            
            logger.info(f"Trade simulated for {symbol}: {side} {size} @ {price}")
            return trade
            
        except Exception as e:
            logger.error(f"Error simulating trade: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Trade simulation failed: {str(e)}"
            )

    def _update_order_book(
        self,
        symbol: str,
        side: str,
        size: float,
        price: float
    ) -> None:
        """Update order book after trade"""
        if symbol not in self._order_books:
            return
        
        order_book = self._order_books[symbol]
        
        if side == 'buy':
            # Remove from bids
            for level in order_book['bids']:
                if level[0] <= price:
                    reduction = min(level[1], size)
                    level[1] -= reduction
                    size -= reduction
                    if size <= 0:
                        break
        else:
            # Remove from asks
            for level in order_book['asks']:
                if level[0] >= price:
                    reduction = min(level[1], size)
                    level[1] -= reduction
                    size -= reduction
                    if size <= 0:
                        break
        
        # Regenerate if order book gets too thin
        if sum(level[1] for level in order_book['bids']) < 100:
            order_book['bids'] = self._regenerate_bids(symbol)
        if sum(level[1] for level in order_book['asks']) < 100:
            order_book['asks'] = self._regenerate_asks(symbol)

    def _regenerate_bids(self, symbol: str) -> List[List[float]]:
        """Regenerate bid levels"""
        context = self._market_data.get(symbol)
        if not context:
            return []
        
        bids = []
        for i in range(10):
            level_price = context.bid - (i * 0.01)
            level_size = np.random.uniform(10, 100) * 100
            bids.append([level_price, level_size])
        
        return bids

    def _regenerate_asks(self, symbol: str) -> List[List[float]]:
        """Regenerate ask levels"""
        context = self._market_data.get(symbol)
        if not context:
            return []
        
        asks = []
        for i in range(10):
            level_price = context.ask + (i * 0.01)
            level_size = np.random.uniform(10, 100) * 100
            asks.append([level_price, level_size])
        
        return asks

    # =========================================================================
    # Indicators
    # =========================================================================

    async def _calculate_indicators(self, symbol: str) -> Dict[str, Any]:
        """Calculate technical indicators"""
        indicators = {}
        
        # Get price history
        history = self._price_history.get(symbol, [])
        if len(history) < 20:
            return indicators
        
        prices = [bar.close for bar in history[-100:]]
        
        # Simple Moving Average
        if len(prices) >= 20:
            indicators['sma_20'] = np.mean(prices[-20:])
            indicators['sma_50'] = np.mean(prices[-50:]) if len(prices) >= 50 else 0
        
        # RSI
        if len(prices) >= 14:
            indicators['rsi'] = self._calculate_rsi(prices)
        
        # Volatility
        if len(prices) >= 20:
            indicators['volatility'] = np.std(prices[-20:]) / np.mean(prices[-20:])
        
        # Volume
        volumes = [bar.volume for bar in history[-100:]]
        if volumes:
            indicators['avg_volume'] = np.mean(volumes)
        
        return indicators

    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change >= 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = np.mean(gains[-period:]) if gains else 0
        avg_loss = np.mean(losses[-period:]) if losses else 0
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi

    # =========================================================================
    # Market Conditions
    # =========================================================================

    async def set_market_condition(
        self,
        symbol: str,
        condition: MarketCondition
    ) -> Dict[str, Any]:
        """
        Set market condition for a symbol.
        
        Args:
            symbol: Symbol
            condition: Market condition
            
        Returns:
            Dict[str, Any]: Update result
        """
        if symbol not in self._market_data:
            await self._get_market_context(symbol)
        
        self._market_data[symbol].market_condition = condition
        
        logger.info(f"Market condition for {symbol} set to {condition.value}")
        return {
            'symbol': symbol,
            'condition': condition.value,
            'timestamp': datetime.utcnow()
        }

    async def set_market_status(
        self,
        symbol: str,
        status: MarketStatus
    ) -> Dict[str, Any]:
        """
        Set market status for a symbol.
        
        Args:
            symbol: Symbol
            status: Market status
            
        Returns:
            Dict[str, Any]: Update result
        """
        if symbol not in self._market_data:
            await self._get_market_context(symbol)
        
        self._market_data[symbol].market_status = status
        
        logger.info(f"Market status for {symbol} set to {status.value}")
        return {
            'symbol': symbol,
            'status': status.value,
            'timestamp': datetime.utcnow()
        }

    # =========================================================================
    # Monitoring
    # =========================================================================

    async def start_market(self) -> None:
        """Start market simulation"""
        if self._is_running:
            return
        
        self._is_running = True
        self._monitor_task = asyncio.create_task(self._market_loop())
        logger.info("Market simulation started")

    async def stop_market(self) -> None:
        """Stop market simulation"""
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("Market simulation stopped")

    async def _market_loop(self) -> None:
        """Main market loop"""
        while self._is_running:
            try:
                # Update all symbols
                for symbol in self._market_data.keys():
                    await self._get_market_context(symbol)
                
                await asyncio.sleep(0.1)  # Update every 100ms
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in market loop: {e}")
                await asyncio.sleep(1)

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the market simulation"""
        await self.stop_market()
        self._market_data.clear()
        self._price_history.clear()
        self._order_books.clear()
        self._price_cache.clear()
        logger.info("PaperTradingMarket closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query

router = APIRouter(prefix="/api/v1/paper-trading/market", tags=["Paper Trading Market"])


async def get_market() -> PaperTradingMarket:
    """Dependency to get PaperTradingMarket instance"""
    return PaperTradingMarket()


@router.post("/data", response_model=MarketDataResponse)
async def get_market_data(
    request: MarketDataRequest,
    market: PaperTradingMarket = Depends(get_market)
):
    """Get market data"""
    return await market.get_market_data(request)


@router.get("/order-book/{symbol}")
async def get_order_book(
    symbol: str,
    depth: OrderBookDepth = Query(OrderBookDepth.LEVEL_1),
    market: PaperTradingMarket = Depends(get_market)
):
    """Get order book"""
    return await market.get_order_book(symbol, depth)


@router.post("/trade/{symbol}")
async def simulate_trade(
    symbol: str,
    side: str = Query(..., description="buy or sell"),
    size: float = Query(..., gt=0),
    market: PaperTradingMarket = Depends(get_market)
):
    """Simulate a trade"""
    return await market.simulate_trade(symbol, side, size)


@router.post("/condition/{symbol}")
async def set_market_condition(
    symbol: str,
    condition: MarketCondition = Query(...),
    market: PaperTradingMarket = Depends(get_market)
):
    """Set market condition"""
    return await market.set_market_condition(symbol, condition)


@router.post("/status/{symbol}")
async def set_market_status(
    symbol: str,
    status: MarketStatus = Query(...),
    market: PaperTradingMarket = Depends(get_market)
):
    """Set market status"""
    return await market.set_market_status(symbol, status)


@router.get("/symbols")
async def get_symbols(
    market: PaperTradingMarket = Depends(get_market)
):
    """Get available symbols"""
    return {'symbols': list(market._symbol_configs.keys())}


@router.post("/start")
async def start_market(
    market: PaperTradingMarket = Depends(get_market)
):
    """Start market simulation"""
    await market.start_market()
    return {"status": "started"}


@router.post("/stop")
async def stop_market(
    market: PaperTradingMarket = Depends(get_market)
):
    """Stop market simulation"""
    await market.stop_market()
    return {"status": "stopped"}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PaperTradingMarket',
    'MarketStatus',
    'MarketCondition',
    'OrderBookDepth',
    'MarketDataRequest',
    'MarketDataResponse',
    'OrderBookResponse',
    'TradeDataResponse',
    'MarketContext',
    'PriceBar',
    'OrderBookLevel',
    'router'
]
