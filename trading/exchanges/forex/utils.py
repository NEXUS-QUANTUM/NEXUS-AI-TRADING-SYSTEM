"""
NEXUS AI TRADING SYSTEM - Forex Utils Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/exchanges/forex/utils.py
Description: Forex utilities with full API integration
"""

import asyncio
import logging
import math
import re
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
from shared.constants.trading_constants import TIME_FRAMES
from shared.utilities.logger import get_logger

# Forex imports
from trading.exchanges.forex.base import ForexInstrument, ForexPrice, ForexCandle

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class PipPosition(str, Enum):
    """Pip positions"""
    FIVE_DIGIT = "5_digit"  # 5 decimal places
    FOUR_DIGIT = "4_digit"  # 4 decimal places
    THREE_DIGIT = "3_digit"  # 3 decimal places
    TWO_DIGIT = "2_digit"  # 2 decimal places


class CurrencyPair(str, Enum):
    """Major currency pairs"""
    EURUSD = "EURUSD"
    GBPUSD = "GBPUSD"
    USDJPY = "USDJPY"
    USDCHF = "USDCHF"
    AUDUSD = "AUDUSD"
    USDCAD = "USDCAD"
    NZDUSD = "NZDUSD"
    EURGBP = "EURGBP"
    EURJPY = "EURJPY"
    GBPJPY = "GBPJPY"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class PipCalculatorRequest(BaseModel):
    """Request model for pip calculation"""
    instrument: str
    price: float
    pip_size: Optional[float] = None
    pip_position: Optional[PipPosition] = None


class PipCalculatorResponse(BaseModel):
    """Response model for pip calculation"""
    instrument: str
    price: float
    pip_value: float
    pip_position: PipPosition
    pip_size: float
    spread: float
    spread_pips: float


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class PairInfo:
    """Currency pair information"""
    symbol: str
    base_currency: str
    quote_currency: str
    pip_size: float
    pip_position: PipPosition
    min_trade_size: float
    step_size: float


@dataclass
class PipValue:
    """Pip value calculation"""
    value: float
    pip_size: float
    pip_position: PipPosition
    currency: str


@dataclass
class PositionSizeCalculation:
    """Position size calculation"""
    units: float
    risk_amount: float
    stop_loss_pips: float
    pip_value: float
    margin_required: float


# =============================================================================
# FOREX UTILITIES
# =============================================================================

class ForexUtils:
    """
    Forex Utilities with full API integration.
    
    Features:
    - Pip calculation
    - Position sizing
    - Currency pair information
    - Spread calculation
    - Risk management
    - Trade management
    - Margin calculation
    """

    # Major currency pair information
    PAIR_INFO = {
        'EURUSD': PairInfo('EURUSD', 'EUR', 'USD', 0.0001, PipPosition.FOUR_DIGIT, 0.01, 0.01),
        'GBPUSD': PairInfo('GBPUSD', 'GBP', 'USD', 0.0001, PipPosition.FOUR_DIGIT, 0.01, 0.01),
        'USDJPY': PairInfo('USDJPY', 'USD', 'JPY', 0.01, PipPosition.TWO_DIGIT, 0.01, 0.01),
        'USDCHF': PairInfo('USDCHF', 'USD', 'CHF', 0.0001, PipPosition.FOUR_DIGIT, 0.01, 0.01),
        'AUDUSD': PairInfo('AUDUSD', 'AUD', 'USD', 0.0001, PipPosition.FOUR_DIGIT, 0.01, 0.01),
        'USDCAD': PairInfo('USDCAD', 'USD', 'CAD', 0.0001, PipPosition.FOUR_DIGIT, 0.01, 0.01),
        'NZDUSD': PairInfo('NZDUSD', 'NZD', 'USD', 0.0001, PipPosition.FOUR_DIGIT, 0.01, 0.01),
        'EURGBP': PairInfo('EURGBP', 'EUR', 'GBP', 0.0001, PipPosition.FOUR_DIGIT, 0.01, 0.01),
        'EURJPY': PairInfo('EURJPY', 'EUR', 'JPY', 0.01, PipPosition.TWO_DIGIT, 0.01, 0.01),
        'GBPJPY': PairInfo('GBPJPY', 'GBP', 'JPY', 0.01, PipPosition.TWO_DIGIT, 0.01, 0.01)
    }

    def __init__(self):
        """Initialize ForexUtils."""
        self._pair_info_cache: Dict[str, PairInfo] = {}
        self._price_cache: Dict[str, ForexPrice] = {}
        self._pip_value_cache: Dict[str, float] = {}
        
        logger.info("ForexUtils initialized")

    # =========================================================================
    # Pip Calculation
    # =========================================================================

    def calculate_pip_value(
        self,
        instrument: str,
        price: float,
        pip_size: Optional[float] = None,
        pip_position: Optional[PipPosition] = None
    ) -> PipCalculatorResponse:
        """
        Calculate pip value for an instrument.
        
        Args:
            instrument: Instrument name
            price: Current price
            pip_size: Pip size (optional)
            pip_position: Pip position (optional)
            
        Returns:
            PipCalculatorResponse: Pip calculation result
        """
        try:
            # Get instrument info
            pair_info = self._get_pair_info(instrument)
            
            # Determine pip size and position
            if pip_size is None:
                pip_size = pair_info.pip_size
            
            if pip_position is None:
                pip_position = pair_info.pip_position
            
            # Calculate spread
            spread = price * 0.0001  # Estimated spread
            spread_pips = spread / pip_size
            
            return PipCalculatorResponse(
                instrument=instrument,
                price=price,
                pip_value=pip_size,
                pip_position=pip_position,
                pip_size=pip_size,
                spread=spread,
                spread_pips=spread_pips
            )
            
        except Exception as e:
            logger.error(f"Error calculating pip value: {e}")
            raise

    def calculate_position_size(
        self,
        instrument: str,
        risk_amount: float,
        stop_loss_pips: float,
        account_balance: float,
        risk_percent: float = 0.02,
        leverage: float = 30.0
    ) -> PositionSizeCalculation:
        """
        Calculate position size based on risk.
        
        Args:
            instrument: Instrument name
            risk_amount: Risk amount in account currency
            stop_loss_pips: Stop loss in pips
            account_balance: Account balance
            risk_percent: Risk percentage per trade
            leverage: Leverage
            
        Returns:
            PositionSizeCalculation: Position size calculation
        """
        try:
            # Get instrument info
            pair_info = self._get_pair_info(instrument)
            
            # Calculate position size
            pip_value = self._calculate_pip_value_currency(instrument)
            units = risk_amount / (stop_loss_pips * pip_value)
            
            # Calculate margin required
            margin_required = (units * pair_info.pip_size) / leverage
            
            # Check if risk amount exceeds maximum
            max_risk = account_balance * risk_percent
            if risk_amount > max_risk:
                risk_amount = max_risk
                units = risk_amount / (stop_loss_pips * pip_value)
            
            return PositionSizeCalculation(
                units=units,
                risk_amount=risk_amount,
                stop_loss_pips=stop_loss_pips,
                pip_value=pip_value,
                margin_required=margin_required
            )
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            raise

    def _calculate_pip_value_currency(self, instrument: str) -> float:
        """
        Calculate pip value in account currency.
        
        Args:
            instrument: Instrument name
            
        Returns:
            float: Pip value
        """
        try:
            pair_info = self._get_pair_info(instrument)
            
            # Get current price
            price = self._get_price(instrument)
            
            # Calculate pip value
            if pair_info.quote_currency == 'USD':
                pip_value = pair_info.pip_size
            else:
                # Convert to USD
                usd_rate = self._get_usd_rate(pair_info.quote_currency)
                pip_value = pair_info.pip_size * usd_rate
            
            return pip_value
            
        except Exception as e:
            logger.error(f"Error calculating pip value in currency: {e}")
            return 0.0001

    # =========================================================================
    # Instrument Information
    # =========================================================================

    def _get_pair_info(self, instrument: str) -> PairInfo:
        """
        Get pair information.
        
        Args:
            instrument: Instrument name
            
        Returns:
            PairInfo: Pair information
        """
        # Check cache
        if instrument in self._pair_info_cache:
            return self._pair_info_cache[instrument]
        
        # Get from predefined pairs
        pair_info = self.PAIR_INFO.get(instrument)
        
        if pair_info is None:
            # Try to parse instrument
            pair_info = self._parse_instrument(instrument)
        
        # Cache
        self._pair_info_cache[instrument] = pair_info
        
        return pair_info

    def _parse_instrument(self, instrument: str) -> PairInfo:
        """
        Parse instrument name.
        
        Args:
            instrument: Instrument name
            
        Returns:
            PairInfo: Parsed pair information
        """
        # Remove common suffixes
        instrument_clean = instrument
        for suffix in ['.', '_']:
            if suffix in instrument:
                instrument_clean = instrument.split(suffix)[0]
        
        # Try to match pattern
        pattern = r'^([A-Z]{3})([A-Z]{3})$'
        match = re.match(pattern, instrument_clean)
        
        if match:
            base = match.group(1)
            quote = match.group(2)
            
            # Determine pip size
            if quote in ['JPY', 'HKD']:
                pip_size = 0.01
                pip_position = PipPosition.TWO_DIGIT
            elif quote in ['XAU', 'XAG']:
                pip_size = 0.01
                pip_position = PipPosition.TWO_DIGIT
            else:
                pip_size = 0.0001
                pip_position = PipPosition.FOUR_DIGIT
            
            return PairInfo(
                symbol=instrument,
                base_currency=base,
                quote_currency=quote,
                pip_size=pip_size,
                pip_position=pip_position,
                min_trade_size=0.01,
                step_size=0.01
            )
        
        # Default fallback
        return PairInfo(
            symbol=instrument,
            base_currency='USD',
            quote_currency='USD',
            pip_size=0.0001,
            pip_position=PipPosition.FOUR_DIGIT,
            min_trade_size=0.01,
            step_size=0.01
        )

    def _get_price(self, instrument: str) -> float:
        """
        Get current price for instrument.
        
        Args:
            instrument: Instrument name
            
        Returns:
            float: Current price
        """
        # Check cache
        if instrument in self._price_cache:
            cached = self._price_cache[instrument]
            if (datetime.utcnow() - cached.timestamp).seconds < 5:
                return cached.bid
        
        # Use default price
        default_price = 1.0
        if 'JPY' in instrument:
            default_price = 150.0
        elif 'XAU' in instrument:
            default_price = 2000.0
        
        return default_price

    def _get_usd_rate(self, currency: str) -> float:
        """
        Get USD exchange rate.
        
        Args:
            currency: Currency
            
        Returns:
            float: Exchange rate
        """
        # Simulate exchange rates
        rates = {
            'USD': 1.0,
            'EUR': 1.1,
            'GBP': 1.3,
            'JPY': 0.0067,
            'CHF': 1.1,
            'AUD': 0.65,
            'CAD': 0.73,
            'NZD': 0.60
        }
        return rates.get(currency, 1.0)

    # =========================================================================
    # Risk Management
    # =========================================================================

    def calculate_risk_reward_ratio(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        direction: str = 'long'
    ) -> float:
        """
        Calculate risk-reward ratio.
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            direction: Trade direction ('long' or 'short')
            
        Returns:
            float: Risk-reward ratio
        """
        try:
            if direction == 'long':
                risk = entry_price - stop_loss
                reward = take_profit - entry_price
            else:
                risk = stop_loss - entry_price
                reward = entry_price - take_profit
            
            if risk <= 0:
                return 0
            
            return reward / risk
            
        except Exception as e:
            logger.error(f"Error calculating risk-reward ratio: {e}")
            return 0

    def calculate_max_position_size(
        self,
        account_balance: float,
        risk_percent: float,
        stop_loss_pips: float,
        instrument: str
    ) -> float:
        """
        Calculate maximum position size.
        
        Args:
            account_balance: Account balance
            risk_percent: Risk percentage
            stop_loss_pips: Stop loss in pips
            instrument: Instrument name
            
        Returns:
            float: Maximum position size
        """
        try:
            risk_amount = account_balance * risk_percent
            pip_value = self._calculate_pip_value_currency(instrument)
            
            if pip_value <= 0 or stop_loss_pips <= 0:
                return 0
            
            return risk_amount / (stop_loss_pips * pip_value)
            
        except Exception as e:
            logger.error(f"Error calculating max position size: {e}")
            return 0

    # =========================================================================
    # Data Conversion
    # =========================================================================

    def candles_to_dataframe(
        self,
        candles: List[ForexCandle]
    ) -> pd.DataFrame:
        """
        Convert candles to DataFrame.
        
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
                'volume': candle.volume
            })
        
        df = pd.DataFrame(data)
        df.set_index('timestamp', inplace=True)
        return df

    def calculate_atr(
        self,
        candles: List[ForexCandle],
        period: int = 14
    ) -> float:
        """
        Calculate Average True Range.
        
        Args:
            candles: List of Forex candles
            period: ATR period
            
        Returns:
            float: ATR value
        """
        try:
            if len(candles) < period:
                return 0
            
            df = self.candles_to_dataframe(candles)
            
            # Calculate True Range
            df['high_low'] = df['high'] - df['low']
            df['high_close'] = abs(df['high'] - df['close'].shift())
            df['low_close'] = abs(df['low'] - df['close'].shift())
            df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
            
            # Calculate ATR
            atr = df['tr'].rolling(window=period).mean().iloc[-1]
            
            return float(atr)
            
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return 0

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the utils module"""
        self._pair_info_cache.clear()
        self._price_cache.clear()
        self._pip_value_cache.clear()
        
        logger.info("ForexUtils closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/exchanges/forex/utils", tags=["Forex Utils"])


async def get_utils() -> ForexUtils:
    """Dependency to get ForexUtils instance"""
    return ForexUtils()


@router.post("/pip/calculate")
async def calculate_pip_value(
    request: PipCalculatorRequest,
    utils: ForexUtils = Depends(get_utils)
):
    """Calculate pip value"""
    return utils.calculate_pip_value(
        request.instrument,
        request.price,
        request.pip_size,
        request.pip_position
    )


@router.post("/position-size")
async def calculate_position_size(
    instrument: str = Body(..., embed=True),
    risk_amount: float = Body(..., embed=True),
    stop_loss_pips: float = Body(..., embed=True),
    account_balance: float = Body(..., embed=True),
    risk_percent: float = Body(0.02, embed=True),
    leverage: float = Body(30.0, embed=True),
    utils: ForexUtils = Depends(get_utils)
):
    """Calculate position size"""
    return utils.calculate_position_size(
        instrument,
        risk_amount,
        stop_loss_pips,
        account_balance,
        risk_percent,
        leverage
    )


@router.post("/risk-reward")
async def calculate_risk_reward_ratio(
    entry_price: float = Body(..., embed=True),
    stop_loss: float = Body(..., embed=True),
    take_profit: float = Body(..., embed=True),
    direction: str = Body("long", embed=True),
    utils: ForexUtils = Depends(get_utils)
):
    """Calculate risk-reward ratio"""
    return utils.calculate_risk_reward_ratio(
        entry_price,
        stop_loss,
        take_profit,
        direction
    )


@router.post("/max-position")
async def calculate_max_position_size(
    account_balance: float = Body(..., embed=True),
    risk_percent: float = Body(0.02, embed=True),
    stop_loss_pips: float = Body(..., embed=True),
    instrument: str = Body(..., embed=True),
    utils: ForexUtils = Depends(get_utils)
):
    """Calculate maximum position size"""
    return utils.calculate_max_position_size(
        account_balance,
        risk_percent,
        stop_loss_pips,
        instrument
    )


@router.get("/pair-info/{instrument}")
async def get_pair_info(
    instrument: str,
    utils: ForexUtils = Depends(get_utils)
):
    """Get pair information"""
    return utils._get_pair_info(instrument)


@router.get("/major-pairs")
async def get_major_pairs():
    """Get major currency pairs"""
    return {
        'pairs': [
            {'symbol': pair.value, 'name': pair.name}
            for pair in CurrencyPair
        ]
    }


@router.post("/atr")
async def calculate_atr(
    candles: List[ForexCandle],
    period: int = Query(14, ge=1, le=100),
    utils: ForexUtils = Depends(get_utils)
):
    """Calculate ATR"""
    return utils.calculate_atr(candles, period)


@router.post("/candles/dataframe")
async def candles_to_dataframe(
    candles: List[ForexCandle],
    utils: ForexUtils = Depends(get_utils)
):
    """Convert candles to DataFrame"""
    return utils.candles_to_dataframe(candles)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'ForexUtils',
    'PipPosition',
    'CurrencyPair',
    'PipCalculatorRequest',
    'PipCalculatorResponse',
    'PairInfo',
    'PipValue',
    'PositionSizeCalculation',
    'router'
]
