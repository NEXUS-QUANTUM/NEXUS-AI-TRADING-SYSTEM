"""
NEXUS AI TRADING SYSTEM - Paper Trading Fees Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/paper-trading/paper_fees.py
Description: Comprehensive paper trading fee management with full API integration
"""

import asyncio
import logging
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.paper_trading_config import PaperTradingConfig
from shared.constants.trading_constants import ASSET_CLASSES
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class FeeType(str, Enum):
    """Types of fees"""
    COMMISSION = "commission"
    SPREAD = "spread"
    SLIPPAGE = "slippage"
    EXCHANGE = "exchange"
    CLEARING = "clearing"
    REGULATORY = "regulatory"
    DATA = "data"
    WITHDRAWAL = "withdrawal"
    DEPOSIT = "deposit"
    INACTIVITY = "inactivity"


class FeeStructure(str, Enum):
    """Fee structures"""
    PERCENTAGE = "percentage"  # Percentage of trade value
    FIXED = "fixed"  # Fixed per trade
    TIERED = "tiered"  # Tiered based on volume
    HYBRID = "hybrid"  # Combination of percentage and fixed
    CUSTOM = "custom"  # Custom fee structure


class FeeSchedule(str, Enum):
    """Fee schedules"""
    MAKER = "maker"  # Maker fees (providing liquidity)
    TAKER = "taker"  # Taker fees (taking liquidity)
    BOTH = "both"  # Both maker and taker


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class FeeConfig(BaseModel):
    """Fee configuration"""
    symbol: str
    asset_class: str = "equity"
    fee_type: FeeType = FeeType.COMMISSION
    structure: FeeStructure = FeeStructure.PERCENTAGE
    schedule: FeeSchedule = FeeSchedule.BOTH
    maker_rate: float = 0.001  # 0.1%
    taker_rate: float = 0.002  # 0.2%
    fixed_fee: float = 0.0
    min_fee: float = 0.0
    max_fee: float = float('inf')
    volume_tiers: List[Dict[str, float]] = []
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('maker_rate')
    def validate_maker(cls, v):
        if v < 0:
            raise ValueError("Maker rate must be non-negative")
        return v

    @validator('taker_rate')
    def validate_taker(cls, v):
        if v < 0:
            raise ValueError("Taker rate must be non-negative")
        return v


class FeeRequest(BaseModel):
    """Request model for fee calculation"""
    symbol: str
    side: str  # buy, sell
    size: float
    price: float
    order_type: str = "limit"  # market, limit
    volume_30d: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('size')
    def validate_size(cls, v):
        if v <= 0:
            raise ValueError("Size must be positive")
        return v

    @validator('price')
    def validate_price(cls, v):
        if v <= 0:
            raise ValueError("Price must be positive")
        return v


class FeeResponse(BaseModel):
    """Response model for fee calculation"""
    symbol: str
    side: str
    order_type: str
    size: float
    price: float
    trade_value: float
    fee_amount: float
    fee_percentage: float
    fee_type: FeeType
    structure: FeeStructure
    schedule: FeeSchedule
    rate_applied: float
    breakdown: Dict[str, float]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FeeAnalyticsResponse(BaseModel):
    """Response model for fee analytics"""
    total_fees: float
    avg_fee_per_trade: float
    max_fee: float
    min_fee: float
    fees_by_type: Dict[str, float]
    fees_by_symbol: Dict[str, float]
    fee_impact: float  # Fees as percentage of PnL
    fee_efficiency: float
    recommendations: List[str]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class FeeContext:
    """Context for fee calculation"""
    symbol: str
    side: str
    order_type: str
    size: float
    price: float
    trade_value: float
    fee_config: FeeConfig
    volume_30d: float = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FeeResult:
    """Result of fee calculation"""
    fee_amount: float
    fee_percentage: float
    rate_applied: float
    fee_type: FeeType
    structure: FeeStructure
    schedule: FeeSchedule
    breakdown: Dict[str, float]


@dataclass
class FeeTier:
    """Fee tier configuration"""
    min_volume: float
    max_volume: float
    rate: float
    fixed_fee: float = 0


# =============================================================================
# PAPER TRADING FEES
# =============================================================================

class PaperTradingFees:
    """
    Comprehensive Paper Trading Fee Management with full API integration.
    
    Features:
    - Multiple fee types (commission, spread, slippage, exchange, etc.)
    - Multiple fee structures (percentage, fixed, tiered, hybrid)
    - Maker/taker fee schedules
    - Volume-based tiering
    - Real-time fee calculation
    - Fee analytics
    - Fee optimization
    - Custom fee configurations
    """

    def __init__(
        self,
        config: Optional[PaperTradingConfig] = None
    ):
        """
        Initialize PaperTradingFees.
        
        Args:
            config: Paper trading configuration
        """
        self.config = config or PaperTradingConfig()
        
        # Fee configurations
        self._fee_configs: Dict[str, FeeConfig] = {}
        self._default_fee_configs: Dict[str, FeeConfig] = {}
        
        # Fee history
        self._fee_history: List[FeeResult] = []
        
        # Analytics cache
        self._analytics_cache: Dict[str, Any] = {}
        
        # Initialize default fee configurations
        self._init_default_fees()
        
        logger.info("PaperTradingFees initialized")

    def _init_default_fees(self) -> None:
        """Initialize default fee configurations"""
        # Default fee configs by asset class
        default_configs = {
            'equity': FeeConfig(
                symbol='*',
                asset_class='equity',
                fee_type=FeeType.COMMISSION,
                structure=FeeStructure.PERCENTAGE,
                schedule=FeeSchedule.BOTH,
                maker_rate=0.001,
                taker_rate=0.002,
                min_fee=0.01
            ),
            'crypto': FeeConfig(
                symbol='*',
                asset_class='crypto',
                fee_type=FeeType.COMMISSION,
                structure=FeeStructure.PERCENTAGE,
                schedule=FeeSchedule.BOTH,
                maker_rate=0.0005,
                taker_rate=0.001,
                min_fee=0.001
            ),
            'forex': FeeConfig(
                symbol='*',
                asset_class='forex',
                fee_type=FeeType.SPREAD,
                structure=FeeStructure.PERCENTAGE,
                schedule=FeeSchedule.BOTH,
                maker_rate=0.0001,
                taker_rate=0.0002
            ),
            'commodity': FeeConfig(
                symbol='*',
                asset_class='commodity',
                fee_type=FeeType.COMMISSION,
                structure=FeeStructure.PERCENTAGE,
                schedule=FeeSchedule.BOTH,
                maker_rate=0.001,
                taker_rate=0.002
            ),
            'fixed_income': FeeConfig(
                symbol='*',
                asset_class='fixed_income',
                fee_type=FeeType.COMMISSION,
                structure=FeeStructure.PERCENTAGE,
                schedule=FeeSchedule.BOTH,
                maker_rate=0.0005,
                taker_rate=0.001
            )
        }
        
        self._default_fee_configs = default_configs
        
        # Set default configs for symbols
        for asset_class, config in default_configs.items():
            self._fee_configs[f"default_{asset_class}"] = config

    # =========================================================================
    # Fee Configuration
    # =========================================================================

    async def configure_fee(
        self,
        config: FeeConfig
    ) -> FeeConfig:
        """
        Configure fee for a symbol.
        
        Args:
            config: Fee configuration
            
        Returns:
            FeeConfig: Updated configuration
        """
        try:
            # Validate config
            await self._validate_fee_config(config)
            
            # Store config
            key = f"{config.symbol}_{config.fee_type.value}"
            self._fee_configs[key] = config
            
            logger.info(f"Fee configured for {config.symbol}")
            return config
            
        except Exception as e:
            logger.error(f"Error configuring fee: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Fee configuration failed: {str(e)}"
            )

    async def _validate_fee_config(self, config: FeeConfig) -> None:
        """Validate fee configuration"""
        if config.maker_rate < 0:
            raise ValueError("Maker rate must be non-negative")
        
        if config.taker_rate < 0:
            raise ValueError("Taker rate must be non-negative")
        
        if config.fixed_fee < 0:
            raise ValueError("Fixed fee must be non-negative")
        
        if config.min_fee < 0:
            raise ValueError("Minimum fee must be non-negative")
        
        if config.max_fee < 0:
            raise ValueError("Maximum fee must be non-negative")
        
        if config.min_fee > config.max_fee:
            raise ValueError("Minimum fee cannot exceed maximum fee")

    async def get_fee_config(
        self,
        symbol: str,
        asset_class: Optional[str] = None
    ) -> Optional[FeeConfig]:
        """
        Get fee configuration for a symbol.
        
        Args:
            symbol: Symbol
            asset_class: Asset class
            
        Returns:
            Optional[FeeConfig]: Fee configuration
        """
        # Check specific symbol config
        for key, config in self._fee_configs.items():
            if config.symbol == symbol or config.symbol == '*':
                return config
        
        # Check asset class config
        if asset_class and f"default_{asset_class}" in self._fee_configs:
            return self._fee_configs[f"default_{asset_class}"]
        
        # Return default equity config
        return self._default_fee_configs.get('equity')

    # =========================================================================
    # Fee Calculation
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def calculate_fee(
        self,
        request: FeeRequest
    ) -> FeeResponse:
        """
        Calculate fee for a trade.
        
        Args:
            request: Fee request
            
        Returns:
            FeeResponse: Fee calculation results
        """
        try:
            # Get fee configuration
            fee_config = await self.get_fee_config(request.symbol)
            if not fee_config:
                # Use default
                fee_config = self._default_fee_configs.get('equity')
            
            # Build context
            context = FeeContext(
                symbol=request.symbol,
                side=request.side,
                order_type=request.order_type,
                size=request.size,
                price=request.price,
                trade_value=request.size * request.price,
                fee_config=fee_config,
                volume_30d=request.volume_30d or 0
            )
            
            # Calculate fee
            result = await self._calculate_fee(context)
            
            # Store history
            self._fee_history.append(result)
            
            # Create response
            response = FeeResponse(
                symbol=request.symbol,
                side=request.side,
                order_type=request.order_type,
                size=request.size,
                price=request.price,
                trade_value=context.trade_value,
                fee_amount=result.fee_amount,
                fee_percentage=result.fee_percentage,
                fee_type=result.fee_type,
                structure=result.structure,
                schedule=result.schedule,
                rate_applied=result.rate_applied,
                breakdown=result.breakdown,
                metadata=request.metadata
            )
            
            logger.info(f"Fee calculated for {request.symbol}: {result.fee_amount}")
            return response
            
        except Exception as e:
            logger.error(f"Error calculating fee: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Fee calculation failed: {str(e)}"
            )

    async def _calculate_fee(
        self,
        context: FeeContext
    ) -> FeeResult:
        """
        Calculate fee based on configuration.
        
        Args:
            context: Fee context
            
        Returns:
            FeeResult: Fee calculation result
        """
        config = context.fee_config
        trade_value = context.trade_value
        
        # Determine schedule (maker/taker)
        schedule = config.schedule
        if schedule == FeeSchedule.MAKER:
            rate = config.maker_rate
        elif schedule == FeeSchedule.TAKER:
            rate = config.taker_rate
        else:  # BOTH
            # Use maker rate for limit orders, taker rate for market orders
            if context.order_type == 'limit':
                rate = config.maker_rate
            else:
                rate = config.taker_rate
        
        # Apply volume tiers if applicable
        if config.structure == FeeStructure.TIERED and config.volume_tiers:
            for tier in config.volume_tiers:
                if tier.get('min_volume', 0) <= context.volume_30d <= tier.get('max_volume', float('inf')):
                    rate = tier.get('rate', rate)
                    break
        
        # Calculate base fee
        if config.structure == FeeStructure.FIXED:
            fee_amount = config.fixed_fee
        elif config.structure == FeeStructure.PERCENTAGE:
            fee_amount = trade_value * rate
        elif config.structure == FeeStructure.HYBRID:
            fee_amount = trade_value * rate + config.fixed_fee
        else:
            fee_amount = trade_value * rate
        
        # Apply min/max
        fee_amount = max(fee_amount, config.min_fee)
        fee_amount = min(fee_amount, config.max_fee)
        
        # Calculate percentage
        fee_percentage = fee_amount / trade_value if trade_value > 0 else 0
        
        # Build breakdown
        breakdown = {
            'base': trade_value * rate,
            'fixed': config.fixed_fee,
            'min': config.min_fee,
            'max': config.max_fee
        }
        
        return FeeResult(
            fee_amount=fee_amount,
            fee_percentage=fee_percentage,
            rate_applied=rate,
            fee_type=config.fee_type,
            structure=config.structure,
            schedule=config.schedule,
            breakdown=breakdown
        )

    # =========================================================================
    # Fee Analytics
    # =========================================================================

    async def get_fee_analytics(
        self,
        period: str = "30d"
    ) -> FeeAnalyticsResponse:
        """
        Get fee analytics.
        
        Args:
            period: Analysis period
            
        Returns:
            FeeAnalyticsResponse: Fee analytics
        """
        try:
            # Filter by period
            now = datetime.utcnow()
            if period == "30d":
                cutoff = now - timedelta(days=30)
            elif period == "7d":
                cutoff = now - timedelta(days=7)
            elif period == "1d":
                cutoff = now - timedelta(days=1)
            else:
                cutoff = now - timedelta(days=30)
            
            history = [h for h in self._fee_history if h.timestamp >= cutoff]
            
            if not history:
                return FeeAnalyticsResponse(
                    total_fees=0,
                    avg_fee_per_trade=0,
                    max_fee=0,
                    min_fee=0,
                    fees_by_type={},
                    fees_by_symbol={},
                    fee_impact=0,
                    fee_efficiency=0,
                    recommendations=["Insufficient data for analytics"]
                )
            
            # Calculate metrics
            fees = [h.fee_amount for h in history]
            total_fees = sum(fees)
            avg_fee = np.mean(fees) if fees else 0
            max_fee = max(fees) if fees else 0
            min_fee = min(fees) if fees else 0
            
            # Fees by type
            fees_by_type = {}
            for h in history:
                fee_type = h.fee_type.value
                fees_by_type[fee_type] = fees_by_type.get(fee_type, 0) + h.fee_amount
            
            # Fees by symbol (would need symbol in history)
            fees_by_symbol = {}
            
            # Fee impact (fees as percentage of total value)
            total_value = sum(h.trade_value for h in history if hasattr(h, 'trade_value'))
            fee_impact = total_fees / total_value if total_value > 0 else 0
            
            # Fee efficiency
            fee_efficiency = 1 - fee_impact if fee_impact < 1 else 0
            
            # Generate recommendations
            recommendations = []
            
            if fee_impact > 0.01:
                recommendations.append("High fee impact. Consider using limit orders to reduce fees.")
            
            if avg_fee > 10:
                recommendations.append("High average fee per trade. Consider reducing trade frequency.")
            
            if len(fees_by_type) > 3:
                recommendations.append("Multiple fee types detected. Consider consolidating to reduce costs.")
            
            if not recommendations:
                recommendations.append("Fee structure is optimal for current trading patterns.")
            
            return FeeAnalyticsResponse(
                total_fees=total_fees,
                avg_fee_per_trade=avg_fee,
                max_fee=max_fee,
                min_fee=min_fee,
                fees_by_type=fees_by_type,
                fees_by_symbol=fees_by_symbol,
                fee_impact=fee_impact,
                fee_efficiency=fee_efficiency,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error getting fee analytics: {e}")
            return FeeAnalyticsResponse(
                total_fees=0,
                avg_fee_per_trade=0,
                max_fee=0,
                min_fee=0,
                fees_by_type={},
                fees_by_symbol={},
                fee_impact=0,
                fee_efficiency=0,
                recommendations=["Error calculating fee analytics"]
            )

    # =========================================================================
    # Fee Optimization
    # =========================================================================

    async def optimize_fee(
        self,
        symbol: str,
        volume_30d: float = 0
    ) -> Dict[str, Any]:
        """
        Optimize fee structure for a symbol.
        
        Args:
            symbol: Symbol
            volume_30d: 30-day trading volume
            
        Returns:
            Dict[str, Any]: Optimization results
        """
        try:
            # Get current config
            config = await self.get_fee_config(symbol)
            if not config:
                config = self._default_fee_configs.get('equity')
            
            # Calculate optimal rate based on volume
            if volume_30d > 1000000:
                optimal_maker = config.maker_rate * 0.7
                optimal_taker = config.taker_rate * 0.7
            elif volume_30d > 100000:
                optimal_maker = config.maker_rate * 0.85
                optimal_taker = config.taker_rate * 0.85
            else:
                optimal_maker = config.maker_rate
                optimal_taker = config.taker_rate
            
            # Calculate savings
            current_cost = volume_30d * (config.maker_rate + config.taker_rate) / 2
            optimal_cost = volume_30d * (optimal_maker + optimal_taker) / 2
            savings = current_cost - optimal_cost
            
            return {
                'symbol': symbol,
                'current_volume': volume_30d,
                'current_maker_rate': config.maker_rate,
                'current_taker_rate': config.taker_rate,
                'optimal_maker_rate': optimal_maker,
                'optimal_taker_rate': optimal_taker,
                'current_cost': current_cost,
                'optimal_cost': optimal_cost,
                'potential_savings': savings,
                'savings_percentage': savings / current_cost if current_cost > 0 else 0,
                'recommendations': [
                    f"Consider negotiating lower fees with {int(volume_30d)} volume",
                    f"Potential savings: ${savings:.2f}"
                ] if savings > 0 else ["Current fee structure is optimal"]
            }
            
        except Exception as e:
            logger.error(f"Error optimizing fee: {e}")
            return {'error': str(e)}

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    async def bulk_calculate_fees(
        self,
        requests: List[FeeRequest]
    ) -> List[FeeResponse]:
        """
        Calculate fees for multiple trades.
        
        Args:
            requests: List of fee requests
            
        Returns:
            List[FeeResponse]: Fee calculation results
        """
        results = []
        
        for request in requests:
            try:
                result = await self.calculate_fee(request)
                results.append(result)
            except Exception as e:
                logger.error(f"Error calculating fee for {request.symbol}: {e}")
                # Continue with next request
        
        return results

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the fees module"""
        self._fee_configs.clear()
        self._fee_history.clear()
        self._analytics_cache.clear()
        logger.info("PaperTradingFees closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/paper-trading/fees", tags=["Paper Trading Fees"])


async def get_fees() -> PaperTradingFees:
    """Dependency to get PaperTradingFees instance"""
    return PaperTradingFees()


@router.post("/calculate", response_model=FeeResponse)
async def calculate_fee(
    request: FeeRequest,
    fees: PaperTradingFees = Depends(get_fees)
):
    """Calculate fee for a trade"""
    return await fees.calculate_fee(request)


@router.post("/configure")
async def configure_fee(
    config: FeeConfig,
    fees: PaperTradingFees = Depends(get_fees)
):
    """Configure fee for a symbol"""
    return await fees.configure_fee(config)


@router.get("/config/{symbol}")
async def get_fee_config(
    symbol: str,
    asset_class: Optional[str] = Query(None),
    fees: PaperTradingFees = Depends(get_fees)
):
    """Get fee configuration for a symbol"""
    config = await fees.get_fee_config(symbol, asset_class)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No fee configuration found for {symbol}"
        )
    return config


@router.get("/analytics")
async def get_fee_analytics(
    period: str = Query("30d"),
    fees: PaperTradingFees = Depends(get_fees)
):
    """Get fee analytics"""
    return await fees.get_fee_analytics(period)


@router.post("/optimize")
async def optimize_fee(
    symbol: str = Body(..., embed=True),
    volume_30d: float = Body(0, embed=True),
    fees: PaperTradingFees = Depends(get_fees)
):
    """Optimize fee structure"""
    return await fees.optimize_fee(symbol, volume_30d)


@router.post("/bulk")
async def bulk_calculate_fees(
    requests: List[FeeRequest] = Body(..., embed=True),
    fees: PaperTradingFees = Depends(get_fees)
):
    """Calculate fees for multiple trades"""
    return await fees.bulk_calculate_fees(requests)


@router.get("/types")
async def get_fee_types():
    """Get available fee types"""
    return {
        'types': [
            {'name': t.value, 'description': t.name.replace('_', ' ').title()}
            for t in FeeType
        ]
    }


@router.get("/structures")
async def get_fee_structures():
    """Get available fee structures"""
    return {
        'structures': [
            {'name': s.value, 'description': s.name.replace('_', ' ').title()}
            for s in FeeStructure
        ]
    }


@router.get("/schedules")
async def get_fee_schedules():
    """Get available fee schedules"""
    return {
        'schedules': [
            {'name': s.value, 'description': s.name.title()}
            for s in FeeSchedule
        ]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PaperTradingFees',
    'FeeType',
    'FeeStructure',
    'FeeSchedule',
    'FeeConfig',
    'FeeRequest',
    'FeeResponse',
    'FeeAnalyticsResponse',
    'FeeContext',
    'FeeResult',
    'FeeTier',
    'router'
]
