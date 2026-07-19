"""
NEXUS AI TRADING SYSTEM - Binance Converter Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/binance/converter.py
Description: Binance data converters with full API integration
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

# Binance imports
from trading.exchanges.binance.base import BinanceCandle, BinanceOrderBook, BinanceTicker
from trading.exchanges.binance.account import BinanceOrderResponse, BinanceOrderStatus

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class BinanceToNexusOrderStatus(str, Enum):
    """Mapping Binance order status to Nexus order status"""
    NEW = "pending"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    PENDING_CANCEL = "cancelling"


class BinanceToNexusOrderType(str, Enum):
    """Mapping Binance order type to Nexus order type"""
    LIMIT = "limit"
    MARKET = "market"
    STOP_LOSS = "stop_loss"
    STOP_LOSS_LIMIT = "stop_limit"
    TAKE_PROFIT = "take_profit"
    TAKE_PROFIT_LIMIT = "take_profit_limit"
    LIMIT_MAKER = "limit"


class BinanceToNexusTimeFrame(str, Enum):
    """Mapping Binance interval to Nexus time frame"""
    ONE_MINUTE = "1m"
    THREE_MINUTES = "3m"
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
    THREE_DAYS = "3d"
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
    quote_volume: float
    trades: int


class NexusOrderBookLevel(BaseModel):
    """Nexus order book level"""
    price: float
    size: float


class NexusOrderBook(BaseModel):
    """Nexus order book"""
    symbol: str
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
    quote_volume: float
    high: float
    low: float
    open: float
    close: float
    bid: float
    ask: float
    timestamp: datetime


class NexusOrder(BaseModel):
    """Nexus order data"""
    order_id: str
    symbol: str
    side: str
    order_type: str
    status: str
    price: float
    avg_price: float
    quantity: float
    executed_quantity: float
    stop_price: Optional[float] = None
    time_in_force: str
    created_at: datetime
    updated_at: datetime


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
# BINANCE CONVERTER
# =============================================================================

class BinanceConverter:
    """
    Binance Data Converter with full API integration.
    
    Features:
    - Candle conversion
    - Order book conversion
    - Ticker conversion
    - Order conversion
    - Time frame mapping
    - Status mapping
    - Type mapping
    - Batch conversion
    - Format conversion
    - Data validation
    """

    def __init__(self):
        """Initialize BinanceConverter."""
        # Status mappings
        self._order_status_mapping = {
            'NEW': 'pending',
            'PARTIALLY_FILLED': 'partially_filled',
            'FILLED': 'filled',
            'CANCELLED': 'cancelled',
            'REJECTED': 'rejected',
            'EXPIRED': 'expired',
            'PENDING_CANCEL': 'cancelling'
        }
        
        # Order type mappings
        self._order_type_mapping = {
            'LIMIT': 'limit',
            'MARKET': 'market',
            'STOP_LOSS': 'stop_loss',
            'STOP_LOSS_LIMIT': 'stop_limit',
            'TAKE_PROFIT': 'take_profit',
            'TAKE_PROFIT_LIMIT': 'take_profit_limit',
            'LIMIT_MAKER': 'limit'
        }
        
        # Time frame mappings
        self._timeframe_mapping = {
            '1m': '1m',
            '3m': '3m',
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
            '3d': '3d',
            '1w': '1w',
            '1M': '1M'
        }
        
        # Reverse mappings
        self._nexus_to_binance_timeframe = {v: k for k, v in self._timeframe_mapping.items()}
        
        # Conversion statistics
        self._stats = ConversionStats(
            total_converted=0,
            successful=0,
            failed=0,
            skipped=0,
            timestamp=datetime.utcnow()
        )
        
        logger.info("BinanceConverter initialized")

    # =========================================================================
    # Candle Conversion
    # =========================================================================

    def convert_candle(
        self,
        binance_candle: BinanceCandle
    ) -> NexusCandle:
        """
        Convert a Binance candle to Nexus candle.
        
        Args:
            binance_candle: Binance candle
            
        Returns:
            NexusCandle: Nexus candle
        """
        try:
            return NexusCandle(
                timestamp=binance_candle.timestamp,
                open=binance_candle.open,
                high=binance_candle.high,
                low=binance_candle.low,
                close=binance_candle.close,
                volume=binance_candle.volume,
                quote_volume=binance_candle.quote_volume,
                trades=binance_candle.trades
            )
        except Exception as e:
            logger.error(f"Error converting candle: {e}")
            raise

    def convert_candles(
        self,
        binance_candles: List[BinanceCandle]
    ) -> List[NexusCandle]:
        """
        Convert multiple Binance candles.
        
        Args:
            binance_candles: List of Binance candles
            
        Returns:
            List[NexusCandle]: List of Nexus candles
        """
        nexus_candles = []
        for candle in binance_candles:
            try:
                nexus_candles.append(self.convert_candle(candle))
                self._stats.successful += 1
            except Exception as e:
                logger.error(f"Error converting candle: {e}")
                self._stats.failed += 1
        
        self._stats.total_converted += len(binance_candles)
        return nexus_candles

    # =========================================================================
    # Order Book Conversion
    # =========================================================================

    def convert_order_book(
        self,
        binance_order_book: BinanceOrderBook
    ) -> NexusOrderBook:
        """
        Convert a Binance order book to Nexus order book.
        
        Args:
            binance_order_book: Binance order book
            
        Returns:
            NexusOrderBook: Nexus order book
        """
        try:
            bids = [
                NexusOrderBookLevel(price=level.price, size=level.size)
                for level in binance_order_book.bids
            ]
            asks = [
                NexusOrderBookLevel(price=level.price, size=level.size)
                for level in binance_order_book.asks
            ]
            
            return NexusOrderBook(
                symbol=binance_order_book.symbol,
                bids=bids,
                asks=asks,
                timestamp=binance_order_book.timestamp,
                sequence=binance_order_book.update_id
            )
        except Exception as e:
            logger.error(f"Error converting order book: {e}")
            raise

    # =========================================================================
    # Ticker Conversion
    # =========================================================================

    def convert_ticker(
        self,
        binance_ticker: BinanceTicker
    ) -> NexusTicker:
        """
        Convert a Binance ticker to Nexus ticker.
        
        Args:
            binance_ticker: Binance ticker
            
        Returns:
            NexusTicker: Nexus ticker
        """
        try:
            return NexusTicker(
                symbol=binance_ticker.symbol,
                price=binance_ticker.price,
                price_change=binance_ticker.price_change,
                price_change_pct=binance_ticker.price_change_pct,
                volume=binance_ticker.volume,
                quote_volume=binance_ticker.quote_volume,
                high=binance_ticker.high,
                low=binance_ticker.low,
                open=binance_ticker.open,
                close=binance_ticker.close,
                bid=binance_ticker.bid,
                ask=binance_ticker.ask,
                timestamp=binance_ticker.timestamp
            )
        except Exception as e:
            logger.error(f"Error converting ticker: {e}")
            raise

    # =========================================================================
    # Order Conversion
    # =========================================================================

    def convert_order(
        self,
        binance_order: BinanceOrderResponse
    ) -> NexusOrder:
        """
        Convert a Binance order to Nexus order.
        
        Args:
            binance_order: Binance order
            
        Returns:
            NexusOrder: Nexus order
        """
        try:
            return NexusOrder(
                order_id=str(binance_order.order_id),
                symbol=binance_order.symbol,
                side=binance_order.side.value.lower(),
                order_type=self._order_type_mapping.get(
                    binance_order.order_type.value,
                    binance_order.order_type.value.lower()
                ),
                status=self._order_status_mapping.get(
                    binance_order.status.value,
                    binance_order.status.value.lower()
                ),
                price=binance_order.price,
                avg_price=binance_order.avg_price,
                quantity=binance_order.quantity,
                executed_quantity=binance_order.executed_quantity,
                stop_price=binance_order.stop_price,
                time_in_force=binance_order.time_in_force.value,
                created_at=binance_order.created_at,
                updated_at=binance_order.updated_at
            )
        except Exception as e:
            logger.error(f"Error converting order: {e}")
            raise

    def convert_orders(
        self,
        binance_orders: List[BinanceOrderResponse]
    ) -> List[NexusOrder]:
        """
        Convert multiple Binance orders.
        
        Args:
            binance_orders: List of Binance orders
            
        Returns:
            List[NexusOrder]: List of Nexus orders
        """
        nexus_orders = []
        for order in binance_orders:
            try:
                nexus_orders.append(self.convert_order(order))
                self._stats.successful += 1
            except Exception as e:
                logger.error(f"Error converting order: {e}")
                self._stats.failed += 1
        
        self._stats.total_converted += len(binance_orders)
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
            data_type: Type of data ('candles', 'orders', 'ticker', 'order_book')
            
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
        binance_interval: str
    ) -> str:
        """
        Convert Binance interval to Nexus time frame.
        
        Args:
            binance_interval: Binance interval
            
        Returns:
            str: Nexus time frame
        """
        return self._timeframe_mapping.get(binance_interval, binance_interval)

    def convert_to_binance_interval(
        self,
        nexus_timeframe: str
    ) -> str:
        """
        Convert Nexus time frame to Binance interval.
        
        Args:
            nexus_timeframe: Nexus time frame
            
        Returns:
            str: Binance interval
        """
        return self._nexus_to_binance_timeframe.get(
            nexus_timeframe,
            nexus_timeframe
        )

    # =========================================================================
    # Data Validation
    # =========================================================================

    def validate_candle(self, candle: BinanceCandle) -> bool:
        """
        Validate a Binance candle.
        
        Args:
            candle: Binance candle
            
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

    def validate_order_book(self, order_book: BinanceOrderBook) -> bool:
        """
        Validate a Binance order book.
        
        Args:
            order_book: Binance order book
            
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
        candles: List[BinanceCandle]
    ) -> pd.DataFrame:
        """
        Convert Binance candles to pandas DataFrame.
        
        Args:
            candles: List of Binance candles
            
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
                'volume': candle.volume,
                'quote_volume': candle.quote_volume,
                'trades': candle.trades
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
        logger.info("BinanceConverter closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/binance/converter", tags=["Binance Converter"])


async def get_converter() -> BinanceConverter:
    """Dependency to get BinanceConverter instance"""
    return BinanceConverter()


@router.post("/convert/candle")
async def convert_candle(
    candle: BinanceCandle,
    converter: BinanceConverter = Depends(get_converter)
):
    """Convert a Binance candle to Nexus format"""
    return converter.convert_candle(candle)


@router.post("/convert/candles")
async def convert_candles(
    candles: List[BinanceCandle],
    converter: BinanceConverter = Depends(get_converter)
):
    """Convert multiple Binance candles to Nexus format"""
    return converter.convert_candles(candles)


@router.post("/convert/order-book")
async def convert_order_book(
    order_book: BinanceOrderBook,
    converter: BinanceConverter = Depends(get_converter)
):
    """Convert a Binance order book to Nexus format"""
    return converter.convert_order_book(order_book)


@router.post("/convert/ticker")
async def convert_ticker(
    ticker: BinanceTicker,
    converter: BinanceConverter = Depends(get_converter)
):
    """Convert a Binance ticker to Nexus format"""
    return converter.convert_ticker(ticker)


@router.post("/convert/order")
async def convert_order(
    order: BinanceOrderResponse,
    converter: BinanceConverter = Depends(get_converter)
):
    """Convert a Binance order to Nexus format"""
    return converter.convert_order(order)


@router.post("/convert/orders")
async def convert_orders(
    orders: List[BinanceOrderResponse],
    converter: BinanceConverter = Depends(get_converter)
):
    """Convert multiple Binance orders to Nexus format"""
    return converter.convert_orders(orders)


@router.post("/convert/batch")
async def convert_batch(
    data: Dict[str, Any] = Body(..., embed=True),
    data_type: str = Query(..., description="Type of data to convert"),
    converter: BinanceConverter = Depends(get_converter)
):
    """Convert a batch of data"""
    return converter.convert_batch(data, data_type)


@router.get("/timeframe/{binance_interval}")
async def convert_timeframe(
    binance_interval: str,
    converter: BinanceConverter = Depends(get_converter)
):
    """Convert Binance interval to Nexus time frame"""
    return {'nexus_timeframe': converter.convert_timeframe(binance_interval)}


@router.post("/timeframe/to-binance")
async def convert_to_binance_interval(
    nexus_timeframe: str = Body(..., embed=True),
    converter: BinanceConverter = Depends(get_converter)
):
    """Convert Nexus time frame to Binance interval"""
    return {'binance_interval': converter.convert_to_binance_interval(nexus_timeframe)}


@router.get("/stats")
async def get_conversion_stats(
    converter: BinanceConverter = Depends(get_converter)
):
    """Get conversion statistics"""
    return converter.get_stats()


@router.post("/stats/reset")
async def reset_conversion_stats(
    converter: BinanceConverter = Depends(get_converter)
):
    """Reset conversion statistics"""
    converter.reset_stats()
    return {"success": True}


@router.post("/dataframe")
async def to_dataframe(
    candles: List[BinanceCandle],
    converter: BinanceConverter = Depends(get_converter)
):
    """Convert Binance candles to pandas DataFrame"""
    return converter.to_dataframe(candles)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BinanceConverter',
    'BinanceToNexusOrderStatus',
    'BinanceToNexusOrderType',
    'BinanceToNexusTimeFrame',
    'NexusCandle',
    'NexusOrderBookLevel',
    'NexusOrderBook',
    'NexusTicker',
    'NexusOrder',
    'ConversionStats',
    'ConversionMapping',
    'router'
]
