"""
NEXUS AI TRADING SYSTEM - Coinbase Converter Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/coinbase/converter.py
Description: Coinbase data converters with full API integration
"""

import asyncio
import logging
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
from shared.constants.trading_constants import ORDER_TYPES, POSITION_DIRECTIONS, TIME_FRAMES
from shared.utilities.logger import get_logger

# Coinbase imports
from trading.exchanges.coinbase.base import CoinbaseCandle, CoinbaseOrderBook, CoinbaseTicker, CoinbaseTrade
from trading.exchanges.coinbase.account import CoinbaseOrderResponse, CoinbaseOrderStatus

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class CoinbaseToNexusOrderStatus(str, Enum):
    """Mapping Coinbase order status to Nexus order status"""
    pending = "pending"
    open = "open"
    filled = "filled"
    cancelled = "cancelled"
    expired = "expired"
    rejected = "rejected"
    partially_filled = "partially_filled"


class CoinbaseToNexusOrderType(str, Enum):
    """Mapping Coinbase order type to Nexus order type"""
    market = "market"
    limit = "limit"
    stop = "stop_loss"
    stop_limit = "stop_limit"


class CoinbaseToNexusTimeFrame(str, Enum):
    """Mapping Coinbase granularity to Nexus time frame"""
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"
    FOUR_HOURS = "4h"
    SIX_HOURS = "6h"
    EIGHT_HOURS = "8h"
    TWELVE_HOURS = "12h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class NexusCandle(BaseModel):
    """Nexus candle data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class NexusOrderBookLevel(BaseModel):
    """Nexus order book level"""
    price: float
    size: float
    order_count: int


class NexusOrderBook(BaseModel):
    """Nexus order book"""
    product_id: str
    bids: List[NexusOrderBookLevel]
    asks: List[NexusOrderBookLevel]
    timestamp: datetime
    sequence: int


class NexusTicker(BaseModel):
    """Nexus ticker data"""
    symbol: str
    price: float
    price_change: float
    price_change_pct: float
    volume: float
    high: float
    low: float
    open: float
    close: float
    bid: float
    ask: float
    timestamp: datetime


class NexusTrade(BaseModel):
    """Nexus trade data"""
    symbol: str
    price: float
    quantity: float
    trade_time: datetime
    side: str
    trade_id: int


class NexusOrder(BaseModel):
    """Nexus order data"""
    order_id: str
    product_id: str
    side: str
    order_type: str
    status: str
    price: float
    filled_size: float
    size: float
    funds: float
    filled_funds: float
    time_in_force: str
    stop_price: Optional[float] = None
    created_at: datetime
    done_at: Optional[datetime] = None


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ConversionStats:
    """Conversion statistics"""
    total_converted: int
    successful: int
    failed: int
    skipped: int
    timestamp: datetime


@dataclass
class ConversionMapping:
    """Conversion mapping"""
    source_type: str
    target_type: str
    field_mapping: Dict[str, str]
    value_transform: Dict[str, Any]


# =============================================================================
# COINBASE CONVERTER
# =============================================================================

class CoinbaseConverter:
    """
    Coinbase Data Converter with full API integration.
    
    Features:
    - Candle conversion
    - Order book conversion
    - Ticker conversion
    - Order conversion
    - Trade conversion
    - Time frame mapping
    - Status mapping
    - Type mapping
    - Batch conversion
    - Format conversion
    - Data validation
    """

    def __init__(self):
        """Initialize CoinbaseConverter."""
        # Status mappings
        self._order_status_mapping = {
            'pending': 'pending',
            'open': 'open',
            'filled': 'filled',
            'cancelled': 'cancelled',
            'expired': 'expired',
            'rejected': 'rejected',
            'partially_filled': 'partially_filled'
        }
        
        # Order type mappings
        self._order_type_mapping = {
            'market': 'market',
            'limit': 'limit',
            'stop': 'stop_loss',
            'stop_limit': 'stop_limit'
        }
        
        # Time frame mappings
        self._timeframe_mapping = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '1h': '1h',
            '2h': '2h',
            '4h': '4h',
            '6h': '6h',
            '8h': '8h',
            '12h': '12h',
            '1d': '1d',
            '7d': '1w',
            '1M': '1M'
        }
        
        # Reverse mappings
        self._nexus_to_coinbase_timeframe = {v: k for k, v in self._timeframe_mapping.items()}
        
        # Side mapping
        self._side_mapping = {
            'buy': 'buy',
            'sell': 'sell'
        }
        
        # Conversion statistics
        self._stats = ConversionStats(
            total_converted=0,
            successful=0,
            failed=0,
            skipped=0,
            timestamp=datetime.utcnow()
        )
        
        logger.info("CoinbaseConverter initialized")

    # =========================================================================
    # Candle Conversion
    # =========================================================================

    def convert_candle(
        self,
        coinbase_candle: CoinbaseCandle
    ) -> NexusCandle:
        """
        Convert a Coinbase candle to Nexus candle.
        
        Args:
            coinbase_candle: Coinbase candle
            
        Returns:
            NexusCandle: Nexus candle
        """
        try:
            return NexusCandle(
                timestamp=coinbase_candle.timestamp,
                open=coinbase_candle.open,
                high=coinbase_candle.high,
                low=coinbase_candle.low,
                close=coinbase_candle.close,
                volume=coinbase_candle.volume
            )
        except Exception as e:
            logger.error(f"Error converting candle: {e}")
            raise

    def convert_candles(
        self,
        coinbase_candles: List[CoinbaseCandle]
    ) -> List[NexusCandle]:
        """
        Convert multiple Coinbase candles.
        
        Args:
            coinbase_candles: List of Coinbase candles
            
        Returns:
            List[NexusCandle]: List of Nexus candles
        """
        nexus_candles = []
        for candle in coinbase_candles:
            try:
                nexus_candles.append(self.convert_candle(candle))
                self._stats.successful += 1
            except Exception as e:
                logger.error(f"Error converting candle: {e}")
                self._stats.failed += 1
        
        self._stats.total_converted += len(coinbase_candles)
        return nexus_candles

    # =========================================================================
    # Order Book Conversion
    # =========================================================================

    def convert_order_book(
        self,
        coinbase_order_book: CoinbaseOrderBook
    ) -> NexusOrderBook:
        """
        Convert a Coinbase order book to Nexus order book.
        
        Args:
            coinbase_order_book: Coinbase order book
            
        Returns:
            NexusOrderBook: Nexus order book
        """
        try:
            bids = [
                NexusOrderBookLevel(price=level.price, size=level.size, order_count=level.order_count)
                for level in coinbase_order_book.bids
            ]
            asks = [
                NexusOrderBookLevel(price=level.price, size=level.size, order_count=level.order_count)
                for level in coinbase_order_book.asks
            ]
            
            return NexusOrderBook(
                product_id=coinbase_order_book.product_id,
                bids=bids,
                asks=asks,
                timestamp=coinbase_order_book.timestamp,
                sequence=coinbase_order_book.sequence
            )
        except Exception as e:
            logger.error(f"Error converting order book: {e}")
            raise

    # =========================================================================
    # Ticker Conversion
    # =========================================================================

    def convert_ticker(
        self,
        coinbase_ticker: CoinbaseTicker
    ) -> NexusTicker:
        """
        Convert a Coinbase ticker to Nexus ticker.
        
        Args:
            coinbase_ticker: Coinbase ticker
            
        Returns:
            NexusTicker: Nexus ticker
        """
        try:
            return NexusTicker(
                symbol=coinbase_ticker.product_id,
                price=coinbase_ticker.price,
                price_change=coinbase_ticker.price_change,
                price_change_pct=coinbase_ticker.price_change_pct,
                volume=coinbase_ticker.volume,
                high=coinbase_ticker.high,
                low=coinbase_ticker.low,
                open=coinbase_ticker.open,
                close=coinbase_ticker.close,
                bid=coinbase_ticker.bid,
                ask=coinbase_ticker.ask,
                timestamp=coinbase_ticker.timestamp
            )
        except Exception as e:
            logger.error(f"Error converting ticker: {e}")
            raise

    # =========================================================================
    # Trade Conversion
    # =========================================================================

    def convert_trade(
        self,
        coinbase_trade: CoinbaseTrade
    ) -> NexusTrade:
        """
        Convert a Coinbase trade to Nexus trade.
        
        Args:
            coinbase_trade: Coinbase trade
            
        Returns:
            NexusTrade: Nexus trade
        """
        try:
            return NexusTrade(
                symbol=coinbase_trade.product_id,
                price=coinbase_trade.price,
                quantity=coinbase_trade.size,
                trade_time=coinbase_trade.trade_time,
                side=self._side_mapping.get(coinbase_trade.side, coinbase_trade.side),
                trade_id=coinbase_trade.trade_id
            )
        except Exception as e:
            logger.error(f"Error converting trade: {e}")
            raise

    def convert_trades(
        self,
        coinbase_trades: List[CoinbaseTrade]
    ) -> List[NexusTrade]:
        """
        Convert multiple Coinbase trades.
        
        Args:
            coinbase_trades: List of Coinbase trades
            
        Returns:
            List[NexusTrade]: List of Nexus trades
        """
        nexus_trades = []
        for trade in coinbase_trades:
            try:
                nexus_trades.append(self.convert_trade(trade))
                self._stats.successful += 1
            except Exception as e:
                logger.error(f"Error converting trade: {e}")
                self._stats.failed += 1
        
        self._stats.total_converted += len(coinbase_trades)
        return nexus_trades

    # =========================================================================
    # Order Conversion
    # =========================================================================

    def convert_order(
        self,
        coinbase_order: CoinbaseOrderResponse
    ) -> NexusOrder:
        """
        Convert a Coinbase order to Nexus order.
        
        Args:
            coinbase_order: Coinbase order
            
        Returns:
            NexusOrder: Nexus order
        """
        try:
            return NexusOrder(
                order_id=coinbase_order.order_id,
                product_id=coinbase_order.product_id,
                side=self._side_mapping.get(coinbase_order.side.value, coinbase_order.side.value),
                order_type=self._order_type_mapping.get(
                    coinbase_order.order_type.value,
                    coinbase_order.order_type.value
                ),
                status=self._order_status_mapping.get(
                    coinbase_order.status.value,
                    coinbase_order.status.value
                ),
                price=coinbase_order.price,
                filled_size=coinbase_order.filled_size,
                size=coinbase_order.size,
                funds=coinbase_order.funds,
                filled_funds=coinbase_order.filled_funds,
                time_in_force=coinbase_order.time_in_force.value,
                stop_price=coinbase_order.stop_price,
                created_at=coinbase_order.created_at,
                done_at=coinbase_order.done_at
            )
        except Exception as e:
            logger.error(f"Error converting order: {e}")
            raise

    def convert_orders(
        self,
        coinbase_orders: List[CoinbaseOrderResponse]
    ) -> List[NexusOrder]:
        """
        Convert multiple Coinbase orders.
        
        Args:
            coinbase_orders: List of Coinbase orders
            
        Returns:
            List[NexusOrder]: List of Nexus orders
        """
        nexus_orders = []
        for order in coinbase_orders:
            try:
                nexus_orders.append(self.convert_order(order))
                self._stats.successful += 1
            except Exception as e:
                logger.error(f"Error converting order: {e}")
                self._stats.failed += 1
        
        self._stats.total_converted += len(coinbase_orders)
        return nexus_orders

    # =========================================================================
    # Batch Conversion
    # =========================================================================

    def convert_batch(
        self,
        data: Dict[str, Any],
        data_type: str
    ) -> Dict[str, Any]:
        """
        Convert a batch of data.
        
        Args:
            data: Data to convert
            data_type: Type of data ('candles', 'orders', 'ticker', 'order_book', 'trades')
            
        Returns:
            Dict[str, Any]: Converted data
        """
        try:
            if data_type == 'candles':
                return {'candles': self.convert_candles(data.get('candles', []))}
            elif data_type == 'orders':
                return {'orders': self.convert_orders(data.get('orders', []))}
            elif data_type == 'ticker':
                return {'ticker': self.convert_ticker(data.get('ticker'))}
            elif data_type == 'order_book':
                return {'order_book': self.convert_order_book(data.get('order_book'))}
            elif data_type == 'trades':
                return {'trades': self.convert_trades(data.get('trades', []))}
            else:
                raise ValueError(f"Unsupported data type: {data_type}")
        except Exception as e:
            logger.error(f"Error converting batch: {e}")
            raise

    # =========================================================================
    # Time Frame Conversion
    # =========================================================================

    def convert_timeframe(
        self,
        coinbase_granularity: str
    ) -> str:
        """
        Convert Coinbase granularity to Nexus time frame.
        
        Args:
            coinbase_granularity: Coinbase granularity
            
        Returns:
            str: Nexus time frame
        """
        return self._timeframe_mapping.get(coinbase_granularity, coinbase_granularity)

    def convert_to_coinbase_granularity(
        self,
        nexus_timeframe: str
    ) -> str:
        """
        Convert Nexus time frame to Coinbase granularity.
        
        Args:
            nexus_timeframe: Nexus time frame
            
        Returns:
            str: Coinbase granularity
        """
        return self._nexus_to_coinbase_timeframe.get(
            nexus_timeframe,
            nexus_timeframe
        )

    # =========================================================================
    # Data Validation
    # =========================================================================

    def validate_candle(self, candle: CoinbaseCandle) -> bool:
        """
        Validate a Coinbase candle.
        
        Args:
            candle: Coinbase candle
            
        Returns:
            bool: Validation result
        """
        try:
            if candle.open <= 0 or candle.high <= 0 or candle.low <= 0 or candle.close <= 0:
                return False
            if candle.high < candle.low:
                return False
            if candle.volume < 0:
                return False
            return True
        except Exception as e:
            logger.error(f"Error validating candle: {e}")
            return False

    def validate_order_book(self, order_book: CoinbaseOrderBook) -> bool:
        """
        Validate a Coinbase order book.
        
        Args:
            order_book: Coinbase order book
            
        Returns:
            bool: Validation result
        """
        try:
            if not order_book.bids or not order_book.asks:
                return False
            if order_book.bids[0].price > order_book.asks[0].price:
                return False
            return True
        except Exception as e:
            logger.error(f"Error validating order book: {e}")
            return False

    # =========================================================================
    # Format Conversion
    # =========================================================================

    def to_dataframe(
        self,
        candles: List[CoinbaseCandle]
    ) -> pd.DataFrame:
        """
        Convert Coinbase candles to pandas DataFrame.
        
        Args:
            candles: List of Coinbase candles
            
        Returns:
            pd.DataFrame: DataFrame
        """
        data = []
        for candle in candles:
            data.append({
                'timestamp': candle.timestamp,
                'open': candle.open,
                'high': candle.high,
                'low': candle.low,
                'close': candle.close,
                'volume': candle.volume
            })
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df

    def to_dict(
        self,
        nexus_data: Any
    ) -> Dict[str, Any]:
        """
        Convert Nexus data to dictionary.
        
        Args:
            nexus_data: Nexus data
            
        Returns:
            Dict[str, Any]: Dictionary
        """
        if hasattr(nexus_data, 'dict'):
            return nexus_data.dict()
        elif hasattr(nexus_data, '__dict__'):
            return nexus_data.__dict__
        else:
            return nexus_data

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> ConversionStats:
        """
        Get conversion statistics.
        
        Returns:
            ConversionStats: Conversion statistics
        """
        return self._stats

    def reset_stats(self) -> None:
        """Reset conversion statistics"""
        self._stats = ConversionStats(
            total_converted=0,
            successful=0,
            failed=0,
            skipped=0,
            timestamp=datetime.utcnow()
        )

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the converter"""
        logger.info("CoinbaseConverter closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/coinbase/converter", tags=["Coinbase Converter"])


async def get_converter() -> CoinbaseConverter:
    """Dependency to get CoinbaseConverter instance"""
    return CoinbaseConverter()


@router.post("/convert/candle")
async def convert_candle(
    candle: CoinbaseCandle,
    converter: CoinbaseConverter = Depends(get_converter)
):
    """Convert a Coinbase candle to Nexus format"""
    return converter.convert_candle(candle)


@router.post("/convert/candles")
async def convert_candles(
    candles: List[CoinbaseCandle],
    converter: CoinbaseConverter = Depends(get_converter)
):
    """Convert multiple Coinbase candles to Nexus format"""
    return converter.convert_candles(candles)


@router.post("/convert/order-book")
async def convert_order_book(
    order_book: CoinbaseOrderBook,
    converter: CoinbaseConverter = Depends(get_converter)
):
    """Convert a Coinbase order book to Nexus format"""
    return converter.convert_order_book(order_book)


@router.post("/convert/ticker")
async def convert_ticker(
    ticker: CoinbaseTicker,
    converter: CoinbaseConverter = Depends(get_converter)
):
    """Convert a Coinbase ticker to Nexus format"""
    return converter.convert_ticker(ticker)


@router.post("/convert/trade")
async def convert_trade(
    trade: CoinbaseTrade,
    converter: CoinbaseConverter = Depends(get_converter)
):
    """Convert a Coinbase trade to Nexus format"""
    return converter.convert_trade(trade)


@router.post("/convert/trades")
async def convert_trades(
    trades: List[CoinbaseTrade],
    converter: CoinbaseConverter = Depends(get_converter)
):
    """Convert multiple Coinbase trades to Nexus format"""
    return converter.convert_trades(trades)


@router.post("/convert/order")
async def convert_order(
    order: CoinbaseOrderResponse,
    converter: CoinbaseConverter = Depends(get_converter)
):
    """Convert a Coinbase order to Nexus format"""
    return converter.convert_order(order)


@router.post("/convert/orders")
async def convert_orders(
    orders: List[CoinbaseOrderResponse],
    converter: CoinbaseConverter = Depends(get_converter)
):
    """Convert multiple Coinbase orders to Nexus format"""
    return converter.convert_orders(orders)


@router.post("/convert/batch")
async def convert_batch(
    data: Dict[str, Any] = Body(..., embed=True),
    data_type: str = Query(..., description="Type of data to convert"),
    converter: CoinbaseConverter = Depends(get_converter)
):
    """Convert a batch of data"""
    return converter.convert_batch(data, data_type)


@router.get("/timeframe/{coinbase_granularity}")
async def convert_timeframe(
    coinbase_granularity: str,
    converter: CoinbaseConverter = Depends(get_converter)
):
    """Convert Coinbase granularity to Nexus time frame"""
    return {'nexus_timeframe': converter.convert_timeframe(coinbase_granularity)}


@router.post("/timeframe/to-coinbase")
async def convert_to_coinbase_granularity(
    nexus_timeframe: str = Body(..., embed=True),
    converter: CoinbaseConverter = Depends(get_converter)
):
    """Convert Nexus time frame to Coinbase granularity"""
    return {'coinbase_granularity': converter.convert_to_coinbase_granularity(nexus_timeframe)}


@router.get("/stats")
async def get_conversion_stats(
    converter: CoinbaseConverter = Depends(get_converter)
):
    """Get conversion statistics"""
    return converter.get_stats()


@router.post("/stats/reset")
async def reset_conversion_stats(
    converter: CoinbaseConverter = Depends(get_converter)
):
    """Reset conversion statistics"""
    converter.reset_stats()
    return {"success": True}


@router.post("/dataframe")
async def to_dataframe(
    candles: List[CoinbaseCandle],
    converter: CoinbaseConverter = Depends(get_converter)
):
    """Convert Coinbase candles to pandas DataFrame"""
    return converter.to_dataframe(candles)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'CoinbaseConverter',
    'CoinbaseToNexusOrderStatus',
    'CoinbaseToNexusOrderType',
    'CoinbaseToNexusTimeFrame',
    'NexusCandle',
    'NexusOrderBookLevel',
    'NexusOrderBook',
    'NexusTicker',
    'NexusTrade',
    'NexusOrder',
    'ConversionStats',
    'ConversionMapping',
    'router'
]
