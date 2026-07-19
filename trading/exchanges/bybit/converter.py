"""
NEXUS AI TRADING SYSTEM - Bybit Converter Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/bybit/converter.py
Description: Bybit data converters with full API integration
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

# Bybit imports
from trading.exchanges.bybit.base import BybitCandle, BybitOrderBook, BybitTicker, BybitTrade
from trading.exchanges.bybit.account import BybitOrderResponse, BybitOrderStatus

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class BybitToNexusOrderStatus(str, Enum):
    """Mapping Bybit order status to Nexus order status"""
    Created = "pending"
    New = "pending"
    PartiallyFilled = "partially_filled"
    Filled = "filled"
    Cancelled = "cancelled"
    Rejected = "rejected"
    PendingCancel = "cancelling"
    PartiallyFilledCancelled = "cancelled"


class BybitToNexusOrderType(str, Enum):
    """Mapping Bybit order type to Nexus order type"""
    Limit = "limit"
    Market = "market"
    Stop = "stop_loss"
    StopLimit = "stop_limit"
    TakeProfit = "take_profit"
    TakeProfitLimit = "take_profit_limit"
    TrailingStop = "trailing_stop"


class BybitToNexusTimeFrame(str, Enum):
    """Mapping Bybit interval to Nexus time frame"""
    ONE_MINUTE = "1m"
    THREE_MINUTES = "3m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"
    FOUR_HOURS = "4h"
    SIX_HOURS = "6h"
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
    turnover: float


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
    update_id: int


class NexusTicker(BaseModel):
    """Nexus ticker data"""
    symbol: str
    price: float
    price_change: float
    price_change_pct: float
    volume: float
    turnover: float
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
    trade_id: str


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
# BYBIT CONVERTER
# =============================================================================

class BybitConverter:
    """
    Bybit Data Converter with full API integration.
    
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
        """Initialize BybitConverter."""
        # Status mappings
        self._order_status_mapping = {
            'Created': 'pending',
            'New': 'pending',
            'PartiallyFilled': 'partially_filled',
            'Filled': 'filled',
            'Cancelled': 'cancelled',
            'Rejected': 'rejected',
            'PendingCancel': 'cancelling',
            'PartiallyFilledCancelled': 'cancelled'
        }
        
        # Order type mappings
        self._order_type_mapping = {
            'Limit': 'limit',
            'Market': 'market',
            'Stop': 'stop_loss',
            'StopLimit': 'stop_limit',
            'TakeProfit': 'take_profit',
            'TakeProfitLimit': 'take_profit_limit',
            'TrailingStop': 'trailing_stop'
        }
        
        # Time frame mappings
        self._timeframe_mapping = {
            '1': '1m',
            '3': '3m',
            '5': '5m',
            '15': '15m',
            '30': '30m',
            '60': '1h',
            '120': '2h',
            '240': '4h',
            '360': '6h',
            '720': '12h',
            'D': '1d',
            'W': '1w',
            'M': '1M'
        }
        
        # Reverse mappings
        self._nexus_to_bybit_timeframe = {v: k for k, v in self._timeframe_mapping.items()}
        
        # Side mapping
        self._side_mapping = {
            'Buy': 'buy',
            'Sell': 'sell'
        }
        
        # Conversion statistics
        self._stats = ConversionStats(
            total_converted=0,
            successful=0,
            failed=0,
            skipped=0,
            timestamp=datetime.utcnow()
        )
        
        logger.info("BybitConverter initialized")

    # =========================================================================
    # Candle Conversion
    # =========================================================================

    def convert_candle(
        self,
        bybit_candle: BybitCandle
    ) -> NexusCandle:
        """
        Convert a Bybit candle to Nexus candle.
        
        Args:
            bybit_candle: Bybit candle
            
        Returns:
            NexusCandle: Nexus candle
        """
        try:
            return NexusCandle(
                timestamp=bybit_candle.timestamp,
                open=bybit_candle.open,
                high=bybit_candle.high,
                low=bybit_candle.low,
                close=bybit_candle.close,
                volume=bybit_candle.volume,
                turnover=bybit_candle.turnover
            )
        except Exception as e:
            logger.error(f"Error converting candle: {e}")
            raise

    def convert_candles(
        self,
        bybit_candles: List[BybitCandle]
    ) -> List[NexusCandle]:
        """
        Convert multiple Bybit candles.
        
        Args:
            bybit_candles: List of Bybit candles
            
        Returns:
            List[NexusCandle]: List of Nexus candles
        """
        nexus_candles = []
        for candle in bybit_candles:
            try:
                nexus_candles.append(self.convert_candle(candle))
                self._stats.successful += 1
            except Exception as e:
                logger.error(f"Error converting candle: {e}")
                self._stats.failed += 1
        
        self._stats.total_converted += len(bybit_candles)
        return nexus_candles

    # =========================================================================
    # Order Book Conversion
    # =========================================================================

    def convert_order_book(
        self,
        bybit_order_book: BybitOrderBook
    ) -> NexusOrderBook:
        """
        Convert a Bybit order book to Nexus order book.
        
        Args:
            bybit_order_book: Bybit order book
            
        Returns:
            NexusOrderBook: Nexus order book
        """
        try:
            bids = [
                NexusOrderBookLevel(price=level.price, size=level.size)
                for level in bybit_order_book.bids
            ]
            asks = [
                NexusOrderBookLevel(price=level.price, size=level.size)
                for level in bybit_order_book.asks
            ]
            
            return NexusOrderBook(
                symbol=bybit_order_book.symbol,
                bids=bids,
                asks=asks,
                timestamp=bybit_order_book.timestamp,
                update_id=bybit_order_book.update_id
            )
        except Exception as e:
            logger.error(f"Error converting order book: {e}")
            raise

    # =========================================================================
    # Ticker Conversion
    # =========================================================================

    def convert_ticker(
        self,
        bybit_ticker: BybitTicker
    ) -> NexusTicker:
        """
        Convert a Bybit ticker to Nexus ticker.
        
        Args:
            bybit_ticker: Bybit ticker
            
        Returns:
            NexusTicker: Nexus ticker
        """
        try:
            return NexusTicker(
                symbol=bybit_ticker.symbol,
                price=bybit_ticker.price,
                price_change=bybit_ticker.price_change,
                price_change_pct=bybit_ticker.price_change_pct,
                volume=bybit_ticker.volume,
                turnover=bybit_ticker.turnover,
                high=bybit_ticker.high,
                low=bybit_ticker.low,
                open=bybit_ticker.open,
                close=bybit_ticker.close,
                bid=bybit_ticker.bid,
                ask=bybit_ticker.ask,
                timestamp=bybit_ticker.timestamp
            )
        except Exception as e:
            logger.error(f"Error converting ticker: {e}")
            raise

    # =========================================================================
    # Trade Conversion
    # =========================================================================

    def convert_trade(
        self,
        bybit_trade: BybitTrade
    ) -> NexusTrade:
        """
        Convert a Bybit trade to Nexus trade.
        
        Args:
            bybit_trade: Bybit trade
            
        Returns:
            NexusTrade: Nexus trade
        """
        try:
            return NexusTrade(
                symbol=bybit_trade.symbol,
                price=bybit_trade.price,
                quantity=bybit_trade.quantity,
                trade_time=bybit_trade.trade_time,
                side=self._side_mapping.get(bybit_trade.side, bybit_trade.side.lower()),
                trade_id=bybit_trade.trade_id
            )
        except Exception as e:
            logger.error(f"Error converting trade: {e}")
            raise

    def convert_trades(
        self,
        bybit_trades: List[BybitTrade]
    ) -> List[NexusTrade]:
        """
        Convert multiple Bybit trades.
        
        Args:
            bybit_trades: List of Bybit trades
            
        Returns:
            List[NexusTrade]: List of Nexus trades
        """
        nexus_trades = []
        for trade in bybit_trades:
            try:
                nexus_trades.append(self.convert_trade(trade))
                self._stats.successful += 1
            except Exception as e:
                logger.error(f"Error converting trade: {e}")
                self._stats.failed += 1
        
        self._stats.total_converted += len(bybit_trades)
        return nexus_trades

    # =========================================================================
    # Order Conversion
    # =========================================================================

    def convert_order(
        self,
        bybit_order: BybitOrderResponse
    ) -> NexusOrder:
        """
        Convert a Bybit order to Nexus order.
        
        Args:
            bybit_order: Bybit order
            
        Returns:
            NexusOrder: Nexus order
        """
        try:
            return NexusOrder(
                order_id=bybit_order.order_id,
                symbol=bybit_order.symbol,
                side=self._side_mapping.get(bybit_order.side.value, bybit_order.side.value.lower()),
                order_type=self._order_type_mapping.get(
                    bybit_order.order_type.value,
                    bybit_order.order_type.value.lower()
                ),
                status=self._order_status_mapping.get(
                    bybit_order.status.value,
                    bybit_order.status.value.lower()
                ),
                price=bybit_order.price,
                avg_price=bybit_order.avg_price,
                quantity=bybit_order.qty,
                executed_quantity=bybit_order.cum_exec_qty,
                stop_price=bybit_order.stop_price,
                time_in_force=bybit_order.time_in_force.value,
                created_at=bybit_order.created_at,
                updated_at=bybit_order.updated_at
            )
        except Exception as e:
            logger.error(f"Error converting order: {e}")
            raise

    def convert_orders(
        self,
        bybit_orders: List[BybitOrderResponse]
    ) -> List[NexusOrder]:
        """
        Convert multiple Bybit orders.
        
        Args:
            bybit_orders: List of Bybit orders
            
        Returns:
            List[NexusOrder]: List of Nexus orders
        """
        nexus_orders = []
        for order in bybit_orders:
            try:
                nexus_orders.append(self.convert_order(order))
                self._stats.successful += 1
            except Exception as e:
                logger.error(f"Error converting order: {e}")
                self._stats.failed += 1
        
        self._stats.total_converted += len(bybit_orders)
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
        bybit_interval: str
    ) -> str:
        """
        Convert Bybit interval to Nexus time frame.
        
        Args:
            bybit_interval: Bybit interval
            
        Returns:
            str: Nexus time frame
        """
        return self._timeframe_mapping.get(bybit_interval, bybit_interval)

    def convert_to_bybit_interval(
        self,
        nexus_timeframe: str
    ) -> str:
        """
        Convert Nexus time frame to Bybit interval.
        
        Args:
            nexus_timeframe: Nexus time frame
            
        Returns:
            str: Bybit interval
        """
        return self._nexus_to_bybit_timeframe.get(
            nexus_timeframe,
            nexus_timeframe
        )

    # =========================================================================
    # Data Validation
    # =========================================================================

    def validate_candle(self, candle: BybitCandle) -> bool:
        """
        Validate a Bybit candle.
        
        Args:
            candle: Bybit candle
            
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

    def validate_order_book(self, order_book: BybitOrderBook) -> bool:
        """
        Validate a Bybit order book.
        
        Args:
            order_book: Bybit order book
            
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
        candles: List[BybitCandle]
    ) -> pd.DataFrame:
        """
        Convert Bybit candles to pandas DataFrame.
        
        Args:
            candles: List of Bybit candles
            
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
                'turnover': candle.turnover
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
        logger.info("BybitConverter closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/bybit/converter", tags=["Bybit Converter"])


async def get_converter() -> BybitConverter:
    """Dependency to get BybitConverter instance"""
    return BybitConverter()


@router.post("/convert/candle")
async def convert_candle(
    candle: BybitCandle,
    converter: BybitConverter = Depends(get_converter)
):
    """Convert a Bybit candle to Nexus format"""
    return converter.convert_candle(candle)


@router.post("/convert/candles")
async def convert_candles(
    candles: List[BybitCandle],
    converter: BybitConverter = Depends(get_converter)
):
    """Convert multiple Bybit candles to Nexus format"""
    return converter.convert_candles(candles)


@router.post("/convert/order-book")
async def convert_order_book(
    order_book: BybitOrderBook,
    converter: BybitConverter = Depends(get_converter)
):
    """Convert a Bybit order book to Nexus format"""
    return converter.convert_order_book(order_book)


@router.post("/convert/ticker")
async def convert_ticker(
    ticker: BybitTicker,
    converter: BybitConverter = Depends(get_converter)
):
    """Convert a Bybit ticker to Nexus format"""
    return converter.convert_ticker(ticker)


@router.post("/convert/trade")
async def convert_trade(
    trade: BybitTrade,
    converter: BybitConverter = Depends(get_converter)
):
    """Convert a Bybit trade to Nexus format"""
    return converter.convert_trade(trade)


@router.post("/convert/trades")
async def convert_trades(
    trades: List[BybitTrade],
    converter: BybitConverter = Depends(get_converter)
):
    """Convert multiple Bybit trades to Nexus format"""
    return converter.convert_trades(trades)


@router.post("/convert/order")
async def convert_order(
    order: BybitOrderResponse,
    converter: BybitConverter = Depends(get_converter)
):
    """Convert a Bybit order to Nexus format"""
    return converter.convert_order(order)


@router.post("/convert/orders")
async def convert_orders(
    orders: List[BybitOrderResponse],
    converter: BybitConverter = Depends(get_converter)
):
    """Convert multiple Bybit orders to Nexus format"""
    return converter.convert_orders(orders)


@router.post("/convert/batch")
async def convert_batch(
    data: Dict[str, Any] = Body(..., embed=True),
    data_type: str = Query(..., description="Type of data to convert"),
    converter: BybitConverter = Depends(get_converter)
):
    """Convert a batch of data"""
    return converter.convert_batch(data, data_type)


@router.get("/timeframe/{bybit_interval}")
async def convert_timeframe(
    bybit_interval: str,
    converter: BybitConverter = Depends(get_converter)
):
    """Convert Bybit interval to Nexus time frame"""
    return {'nexus_timeframe': converter.convert_timeframe(bybit_interval)}


@router.post("/timeframe/to-bybit")
async def convert_to_bybit_interval(
    nexus_timeframe: str = Body(..., embed=True),
    converter: BybitConverter = Depends(get_converter)
):
    """Convert Nexus time frame to Bybit interval"""
    return {'bybit_interval': converter.convert_to_bybit_interval(nexus_timeframe)}


@router.get("/stats")
async def get_conversion_stats(
    converter: BybitConverter = Depends(get_converter)
):
    """Get conversion statistics"""
    return converter.get_stats()


@router.post("/stats/reset")
async def reset_conversion_stats(
    converter: BybitConverter = Depends(get_converter)
):
    """Reset conversion statistics"""
    converter.reset_stats()
    return {"success": True}


@router.post("/dataframe")
async def to_dataframe(
    candles: List[BybitCandle],
    converter: BybitConverter = Depends(get_converter)
):
    """Convert Bybit candles to pandas DataFrame"""
    return converter.to_dataframe(candles)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BybitConverter',
    'BybitToNexusOrderStatus',
    'BybitToNexusOrderType',
    'BybitToNexusTimeFrame',
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
