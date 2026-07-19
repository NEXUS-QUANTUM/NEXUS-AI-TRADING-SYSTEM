"""
NEXUS AI TRADING SYSTEM - Forex Converter Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/forex/converter.py
Description: Forex data converters with full API integration
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

# Forex imports
from trading.exchanges.forex.base import (
    ForexPrice,
    ForexCandle,
    ForexPosition,
    ForexInstrument,
    ForexGranularity
)

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class ForexToNexusTimeFrame(str, Enum):
    """Mapping Forex granularity to Nexus time frame"""
    S5 = "5s"
    S10 = "10s"
    S15 = "15s"
    S30 = "30s"
    M1 = "1m"
    M2 = "2m"
    M3 = "3m"
    M4 = "4m"
    M5 = "5m"
    M10 = "10m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H2 = "2h"
    H3 = "3h"
    H4 = "4h"
    H6 = "6h"
    H8 = "8h"
    H12 = "12h"
    D = "1d"
    W = "1w"
    M = "1M"


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
    volume: int
    complete: bool


class NexusPrice(BaseModel):
    """Nexus price data"""
    symbol: str
    bid: float
    ask: float
    spread: float
    timestamp: datetime


class NexusPosition(BaseModel):
    """Nexus position data"""
    symbol: str
    side: str
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    timestamp: datetime


class NexusInstrument(BaseModel):
    """Nexus instrument data"""
    symbol: str
    name: str
    instrument_type: str
    pip_size: float
    min_size: float
    max_size: float
    step_size: float
    quote_currency: str
    tradeable: bool


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
# FOREX CONVERTER
# =============================================================================

class ForexConverter:
    """
    Forex Data Converter with full API integration.
    
    Features:
    - Price conversion
    - Candle conversion
    - Position conversion
    - Instrument conversion
    - Time frame mapping
    - Batch conversion
    - Format conversion
    - Data validation
    """

    def __init__(self):
        """Initialize ForexConverter."""
        # Time frame mappings
        self._timeframe_mapping = {
            'S5': '5s',
            'S10': '10s',
            'S15': '15s',
            'S30': '30s',
            'M1': '1m',
            'M2': '2m',
            'M3': '3m',
            'M4': '4m',
            'M5': '5m',
            'M10': '10m',
            'M15': '15m',
            'M30': '30m',
            'H1': '1h',
            'H2': '2h',
            'H3': '3h',
            'H4': '4h',
            'H6': '6h',
            'H8': '8h',
            'H12': '12h',
            'D': '1d',
            'W': '1w',
            'M': '1M'
        }
        
        # Reverse mappings
        self._nexus_to_forex_timeframe = {v: k for k, v in self._timeframe_mapping.items()}
        
        # Side mapping
        self._side_mapping = {
            'long': 'long',
            'short': 'short',
            'buy': 'long',
            'sell': 'short'
        }
        
        # Conversion statistics
        self._stats = ConversionStats(
            total_converted=0,
            successful=0,
            failed=0,
            skipped=0,
            timestamp=datetime.utcnow()
        )
        
        logger.info("ForexConverter initialized")

    # =========================================================================
    # Price Conversion
    # =========================================================================

    def convert_price(
        self,
        forex_price: ForexPrice
    ) -> NexusPrice:
        """
        Convert a Forex price to Nexus price.
        
        Args:
            forex_price: Forex price
            
        Returns:
            NexusPrice: Nexus price
        """
        try:
            return NexusPrice(
                symbol=forex_price.instrument,
                bid=forex_price.bid,
                ask=forex_price.ask,
                spread=forex_price.spread,
                timestamp=forex_price.timestamp
            )
        except Exception as e:
            logger.error(f"Error converting price: {e}")
            raise

    def convert_prices(
        self,
        forex_prices: List[ForexPrice]
    ) -> List[NexusPrice]:
        """
        Convert multiple Forex prices.
        
        Args:
            forex_prices: List of Forex prices
            
        Returns:
            List[NexusPrice]: List of Nexus prices
        """
        nexus_prices = []
        for price in forex_prices:
            try:
                nexus_prices.append(self.convert_price(price))
                self._stats.successful += 1
            except Exception as e:
                logger.error(f"Error converting price: {e}")
                self._stats.failed += 1
        
        self._stats.total_converted += len(forex_prices)
        return nexus_prices

    # =========================================================================
    # Candle Conversion
    # =========================================================================

    def convert_candle(
        self,
        forex_candle: ForexCandle
    ) -> NexusCandle:
        """
        Convert a Forex candle to Nexus candle.
        
        Args:
            forex_candle: Forex candle
            
        Returns:
            NexusCandle: Nexus candle
        """
        try:
            return NexusCandle(
                timestamp=forex_candle.timestamp,
                open=forex_candle.open,
                high=forex_candle.high,
                low=forex_candle.low,
                close=forex_candle.close,
                volume=forex_candle.volume,
                complete=forex_candle.complete
            )
        except Exception as e:
            logger.error(f"Error converting candle: {e}")
            raise

    def convert_candles(
        self,
        forex_candles: List[ForexCandle]
    ) -> List[NexusCandle]:
        """
        Convert multiple Forex candles.
        
        Args:
            forex_candles: List of Forex candles
            
        Returns:
            List[NexusCandle]: List of Nexus candles
        """
        nexus_candles = []
        for candle in forex_candles:
            try:
                nexus_candles.append(self.convert_candle(candle))
                self._stats.successful += 1
            except Exception as e:
                logger.error(f"Error converting candle: {e}")
                self._stats.failed += 1
        
        self._stats.total_converted += len(forex_candles)
        return nexus_candles

    # =========================================================================
    # Position Conversion
    # =========================================================================

    def convert_position(
        self,
        forex_position: ForexPosition
    ) -> NexusPosition:
        """
        Convert a Forex position to Nexus position.
        
        Args:
            forex_position: Forex position
            
        Returns:
            NexusPosition: Nexus position
        """
        try:
            return NexusPosition(
                symbol=forex_position.instrument,
                side=self._side_mapping.get(forex_position.side, forex_position.side),
                size=forex_position.units,
                entry_price=forex_position.average_price,
                current_price=forex_position.average_price + (forex_position.unrealized_pnl / forex_position.units if forex_position.units != 0 else 0),
                unrealized_pnl=forex_position.unrealized_pnl,
                realized_pnl=forex_position.realized_pnl,
                timestamp=forex_position.timestamp
            )
        except Exception as e:
            logger.error(f"Error converting position: {e}")
            raise

    def convert_positions(
        self,
        forex_positions: List[ForexPosition]
    ) -> List[NexusPosition]:
        """
        Convert multiple Forex positions.
        
        Args:
            forex_positions: List of Forex positions
            
        Returns:
            List[NexusPosition]: List of Nexus positions
        """
        nexus_positions = []
        for position in forex_positions:
            try:
                nexus_positions.append(self.convert_position(position))
                self._stats.successful += 1
            except Exception as e:
                logger.error(f"Error converting position: {e}")
                self._stats.failed += 1
        
        self._stats.total_converted += len(forex_positions)
        return nexus_positions

    # =========================================================================
    # Instrument Conversion
    # =========================================================================

    def convert_instrument(
        self,
        forex_instrument: ForexInstrument
    ) -> NexusInstrument:
        """
        Convert a Forex instrument to Nexus instrument.
        
        Args:
            forex_instrument: Forex instrument
            
        Returns:
            NexusInstrument: Nexus instrument
        """
        try:
            return NexusInstrument(
                symbol=forex_instrument.name,
                name=forex_instrument.display_name,
                instrument_type=forex_instrument.instrument_type.value,
                pip_size=forex_instrument.pip_size,
                min_size=forex_instrument.min_trade_size,
                max_size=forex_instrument.max_trade_size,
                step_size=forex_instrument.step_size,
                quote_currency=forex_instrument.quote_currency,
                tradeable=forex_instrument.tradeable
            )
        except Exception as e:
            logger.error(f"Error converting instrument: {e}")
            raise

    def convert_instruments(
        self,
        forex_instruments: List[ForexInstrument]
    ) -> List[NexusInstrument]:
        """
        Convert multiple Forex instruments.
        
        Args:
            forex_instruments: List of Forex instruments
            
        Returns:
            List[NexusInstrument]: List of Nexus instruments
        """
        nexus_instruments = []
        for instrument in forex_instruments:
            try:
                nexus_instruments.append(self.convert_instrument(instrument))
                self._stats.successful += 1
            except Exception as e:
                logger.error(f"Error converting instrument: {e}")
                self._stats.failed += 1
        
        self._stats.total_converted += len(forex_instruments)
        return nexus_instruments

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
            data_type: Type of data ('prices', 'candles', 'positions', 'instruments')
            
        Returns:
            Dict[str, Any]: Converted data
        """
        try:
            if data_type == 'prices':
                return {'prices': self.convert_prices(data.get('prices', []))}
            elif data_type == 'candles':
                return {'candles': self.convert_candles(data.get('candles', []))}
            elif data_type == 'positions':
                return {'positions': self.convert_positions(data.get('positions', []))}
            elif data_type == 'instruments':
                return {'instruments': self.convert_instruments(data.get('instruments', []))}
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
        forex_granularity: str
    ) -> str:
        """
        Convert Forex granularity to Nexus time frame.
        
        Args:
            forex_granularity: Forex granularity
            
        Returns:
            str: Nexus time frame
        """
        return self._timeframe_mapping.get(forex_granularity, forex_granularity)

    def convert_to_forex_granularity(
        self,
        nexus_timeframe: str
    ) -> str:
        """
        Convert Nexus time frame to Forex granularity.
        
        Args:
            nexus_timeframe: Nexus time frame
            
        Returns:
            str: Forex granularity
        """
        return self._nexus_to_forex_timeframe.get(
            nexus_timeframe,
            nexus_timeframe
        )

    # =========================================================================
    # Data Validation
    # =========================================================================

    def validate_price(self, price: ForexPrice) -> bool:
        """
        Validate a Forex price.
        
        Args:
            price: Forex price
            
        Returns:
            bool: Validation result
        """
        try:
            if price.bid <= 0 or price.ask <= 0:
                return False
            if price.bid > price.ask:
                return False
            return True
        except Exception as e:
            logger.error(f"Error validating price: {e}")
            return False

    def validate_candle(self, candle: ForexCandle) -> bool:
        """
        Validate a Forex candle.
        
        Args:
            candle: Forex candle
            
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

    # =========================================================================
    # Format Conversion
    # =========================================================================

    def to_dataframe(
        self,
        candles: List[ForexCandle]
    ) -> pd.DataFrame:
        """
        Convert Forex candles to pandas DataFrame.
        
        Args:
            candles: List of Forex candles
            
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
                'complete': candle.complete
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
        logger.info("ForexConverter closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/forex/converter", tags=["Forex Converter"])


async def get_converter() -> ForexConverter:
    """Dependency to get ForexConverter instance"""
    return ForexConverter()


@router.post("/convert/price")
async def convert_price(
    price: ForexPrice,
    converter: ForexConverter = Depends(get_converter)
):
    """Convert a Forex price to Nexus format"""
    return converter.convert_price(price)


@router.post("/convert/prices")
async def convert_prices(
    prices: List[ForexPrice],
    converter: ForexConverter = Depends(get_converter)
):
    """Convert multiple Forex prices to Nexus format"""
    return converter.convert_prices(prices)


@router.post("/convert/candle")
async def convert_candle(
    candle: ForexCandle,
    converter: ForexConverter = Depends(get_converter)
):
    """Convert a Forex candle to Nexus format"""
    return converter.convert_candle(candle)


@router.post("/convert/candles")
async def convert_candles(
    candles: List[ForexCandle],
    converter: ForexConverter = Depends(get_converter)
):
    """Convert multiple Forex candles to Nexus format"""
    return converter.convert_candles(candles)


@router.post("/convert/position")
async def convert_position(
    position: ForexPosition,
    converter: ForexConverter = Depends(get_converter)
):
    """Convert a Forex position to Nexus format"""
    return converter.convert_position(position)


@router.post("/convert/positions")
async def convert_positions(
    positions: List[ForexPosition],
    converter: ForexConverter = Depends(get_converter)
):
    """Convert multiple Forex positions to Nexus format"""
    return converter.convert_positions(positions)


@router.post("/convert/instrument")
async def convert_instrument(
    instrument: ForexInstrument,
    converter: ForexConverter = Depends(get_converter)
):
    """Convert a Forex instrument to Nexus format"""
    return converter.convert_instrument(instrument)


@router.post("/convert/instruments")
async def convert_instruments(
    instruments: List[ForexInstrument],
    converter: ForexConverter = Depends(get_converter)
):
    """Convert multiple Forex instruments to Nexus format"""
    return converter.convert_instruments(instruments)


@router.post("/convert/batch")
async def convert_batch(
    data: Dict[str, Any] = Body(..., embed=True),
    data_type: str = Query(..., description="Type of data to convert"),
    converter: ForexConverter = Depends(get_converter)
):
    """Convert a batch of data"""
    return converter.convert_batch(data, data_type)


@router.get("/timeframe/{forex_granularity}")
async def convert_timeframe(
    forex_granularity: str,
    converter: ForexConverter = Depends(get_converter)
):
    """Convert Forex granularity to Nexus time frame"""
    return {'nexus_timeframe': converter.convert_timeframe(forex_granularity)}


@router.post("/timeframe/to-forex")
async def convert_to_forex_granularity(
    nexus_timeframe: str = Body(..., embed=True),
    converter: ForexConverter = Depends(get_converter)
):
    """Convert Nexus time frame to Forex granularity"""
    return {'forex_granularity': converter.convert_to_forex_granularity(nexus_timeframe)}


@router.get("/stats")
async def get_conversion_stats(
    converter: ForexConverter = Depends(get_converter)
):
    """Get conversion statistics"""
    return converter.get_stats()


@router.post("/stats/reset")
async def reset_conversion_stats(
    converter: ForexConverter = Depends(get_converter)
):
    """Reset conversion statistics"""
    converter.reset_stats()
    return {"success": True}


@router.post("/dataframe")
async def to_dataframe(
    candles: List[ForexCandle],
    converter: ForexConverter = Depends(get_converter)
):
    """Convert Forex candles to pandas DataFrame"""
    return converter.to_dataframe(candles)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'ForexConverter',
    'ForexToNexusTimeFrame',
    'NexusCandle',
    'NexusPrice',
    'NexusPosition',
    'NexusInstrument',
    'ConversionStats',
    'ConversionMapping',
    'router'
]
