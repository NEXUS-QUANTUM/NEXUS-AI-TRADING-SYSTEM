"""
NEXUS AI TRADING SYSTEM - Paper Trading Slippage Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/paper-trading/paper_slippage.py
Description: Paper trading slippage simulation with full API integration
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
from shared.constants.trading_constants import TIME_FRAMES
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.cache_utils import cached

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class SlippageModel(str, Enum):
    """Slippage models"""
    FIXED = "fixed"  # Fixed percentage slippage
    VOLATILITY = "volatility"  # Based on volatility
    ORDER_SIZE = "order_size"  # Based on order size relative to volume
    HYBRID = "hybrid"  # Combined model
    MARKET_IMPACT = "market_impact"  # Market impact model
    ZERO = "zero"  # No slippage


class SlippageSeverity(str, Enum):
    """Slippage severity levels"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class SlippageConfig(BaseModel):
    """Slippage configuration"""
    model: SlippageModel = SlippageModel.HYBRID
    fixed_rate: float = 0.001  # 0.1%
    volatility_multiplier: float = 1.0
    order_size_multiplier: float = 1.0
    max_slippage: float = 0.05  # 5% max
    min_slippage: float = 0.0
    market_impact_factor: float = 0.01
    enable_randomness: bool = True
    randomness_std: float = 0.0005
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator('fixed_rate')
    def validate_rate(cls, v):
        if v < 0:
            raise ValueError("Fixed rate must be non-negative")
        return v

    @validator('max_slippage')
    def validate_max(cls, v, values):
        if 'min_slippage' in values and v < values['min_slippage']:
            raise ValueError("Max slippage must be greater than min slippage")
        return v


class SlippageRequest(BaseModel):
    """Request model for slippage calculation"""
    symbol: str
    side: str  # buy, sell
    size: float
    price: float
    order_type: str = "market"  # market, limit
    volatility: Optional[float] = None
    volume: Optional[float] = None
    spread: Optional[float] = None
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


class SlippageResponse(BaseModel):
    """Response model for slippage calculation"""
    symbol: str
    side: str
    order_type: str
    size: float
    price: float
    original_price: float
    slippage_amount: float
    slippage_percentage: float
    executed_price: float
    model: SlippageModel
    severity: SlippageSeverity
    components: Dict[str, float]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SlippageAnalyticsResponse(BaseModel):
    """Response model for slippage analytics"""
    total_slippage: float
    avg_slippage_per_trade: float
    max_slippage: float
    min_slippage: float
    slippage_by_side: Dict[str, float]
    slippage_by_order_type: Dict[str, float]
    slippage_by_symbol: Dict[str, float]
    slippage_impact: float
    slippage_efficiency: float
    recommendations: List[str]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SlippageContext:
    """Context for slippage calculation"""
    symbol: str
    side: str
    size: float
    price: float
    order_type: str
    volatility: float
    volume: float
    spread: float
    timestamp: datetime


@dataclass
class SlippageResult:
    """Result of slippage calculation"""
    slippage_amount: float
    slippage_percentage: float
    executed_price: float
    model: SlippageModel
    components: Dict[str, float]
    severity: SlippageSeverity


@dataclass
class SlippageRecord:
    """Slippage record"""
    timestamp: datetime
    symbol: str
    side: str
    size: float
    price: float
    slippage: float
    slippage_pct: float
    model: str
    order_type: str


# =============================================================================
# PAPER TRADING SLIPPAGE
# =============================================================================

class PaperTradingSlippage:
    """
    Paper Trading Slippage Simulation with full API integration.
    
    Features:
    - Multiple slippage models (fixed, volatility, order size, hybrid, market impact)
    - Realistic slippage simulation
    - Severity classification
    - Slippage analytics
    - Configurable parameters
    - Historical tracking
    """

    def __init__(
        self,
        config: Optional[PaperTradingConfig] = None
    ):
        """
        Initialize PaperTradingSlippage.
        
        Args:
            config: Paper trading configuration
        """
        self.config = config or PaperTradingConfig()
        
        # Default configuration
        self._default_config = SlippageConfig()
        
        # Symbol-specific configurations
        self._symbol_configs: Dict[str, SlippageConfig] = {}
        
        # Slippage history
        self._slippage_history: List[SlippageRecord] = []
        
        # Analytics cache
        self._analytics_cache: Dict[str, Any] = {}
        
        logger.info("PaperTradingSlippage initialized")

    # =========================================================================
    # Slippage Calculation
    # =========================================================================

    @retry_async(max_attempts=3, delay=0.5)
    async def calculate_slippage(
        self,
        request: SlippageRequest
    ) -> SlippageResponse:
        """
        Calculate slippage for a trade.
        
        Args:
            request: Slippage request
            
        Returns:
            SlippageResponse: Slippage calculation results
        """
        try:
            # Get configuration
            config = self._symbol_configs.get(request.symbol, self._default_config)
            
            # Build context
            context = await self._build_context(request, config)
            
            # Calculate slippage
            result = await self._calculate_slippage(context, config)
            
            # Record slippage
            self._record_slippage(request, result)
            
            # Create response
            response = SlippageResponse(
                symbol=request.symbol,
                side=request.side,
                order_type=request.order_type,
                size=request.size,
                price=request.price,
                original_price=request.price,
                slippage_amount=result.slippage_amount,
                slippage_percentage=result.slippage_percentage,
                executed_price=result.executed_price,
                model=result.model,
                severity=result.severity,
                components=result.components,
                metadata=request.metadata
            )
            
            logger.info(f"Slippage calculated for {request.symbol}: {result.slippage_percentage:.4f}%")
            return response
            
        except Exception as e:
            logger.error(f"Error calculating slippage: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Slippage calculation failed: {str(e)}"
            )

    async def _build_context(
        self,
        request: SlippageRequest,
        config: SlippageConfig
    ) -> SlippageContext:
        """Build slippage context"""
        # Get market data if not provided
        volatility = request.volatility or 0.02
        volume = request.volume or 1000000
        spread = request.spread or 0.001
        
        return SlippageContext(
            symbol=request.symbol,
            side=request.side,
            size=request.size,
            price=request.price,
            order_type=request.order_type,
            volatility=volatility,
            volume=volume,
            spread=spread,
            timestamp=datetime.utcnow()
        )

    async def _calculate_slippage(
        self,
        context: SlippageContext,
        config: SlippageConfig
    ) -> SlippageResult:
        """Calculate slippage based on model"""
        components = {}
        slippage_pct = 0.0
        
        if config.model == SlippageModel.ZERO:
            slippage_pct = 0.0
            model = SlippageModel.ZERO
            
        elif config.model == SlippageModel.FIXED:
            slippage_pct = config.fixed_rate
            model = SlippageModel.FIXED
            components['fixed'] = slippage_pct
            
        elif config.model == SlippageModel.VOLATILITY:
            slippage_pct = self._calculate_volatility_slippage(context, config)
            model = SlippageModel.VOLATILITY
            components['volatility'] = slippage_pct
            
        elif config.model == SlippageModel.ORDER_SIZE:
            slippage_pct = self._calculate_order_size_slippage(context, config)
            model = SlippageModel.ORDER_SIZE
            components['order_size'] = slippage_pct
            
        elif config.model == SlippageModel.MARKET_IMPACT:
            slippage_pct = self._calculate_market_impact_slippage(context, config)
            model = SlippageModel.MARKET_IMPACT
            components['market_impact'] = slippage_pct
            
        else:  # HYBRID
            # Combine multiple models
            vol_slippage = self._calculate_volatility_slippage(context, config)
            size_slippage = self._calculate_order_size_slippage(context, config)
            impact_slippage = self._calculate_market_impact_slippage(context, config)
            
            # Weighted combination
            slippage_pct = (
                vol_slippage * 0.4 +
                size_slippage * 0.3 +
                impact_slippage * 0.3
            )
            
            model = SlippageModel.HYBRID
            components.update({
                'volatility': vol_slippage,
                'order_size': size_slippage,
                'market_impact': impact_slippage
            })
        
        # Add randomness if enabled
        if config.enable_randomness:
            random_component = np.random.normal(0, config.randomness_std)
            slippage_pct = max(0, slippage_pct + random_component)
            components['random'] = random_component
        
        # Apply min/max
        slippage_pct = max(config.min_slippage, min(slippage_pct, config.max_slippage))
        
        # Calculate amounts
        slippage_amount = slippage_pct * context.price
        if context.side == 'buy':
            executed_price = context.price + slippage_amount
        else:  # sell
            executed_price = context.price - slippage_amount
        
        # Determine severity
        severity = self._determine_severity(slippage_pct)
        
        return SlippageResult(
            slippage_amount=slippage_amount,
            slippage_percentage=slippage_pct,
            executed_price=executed_price,
            model=model,
            components=components,
            severity=severity
        )

    def _calculate_volatility_slippage(
        self,
        context: SlippageContext,
        config: SlippageConfig
    ) -> float:
        """Calculate volatility-based slippage"""
        # Base volatility
        volatility = context.volatility
        
        # Adjust for order type
        if context.order_type == 'market':
            volatility *= 1.5
        elif context.order_type == 'limit':
            volatility *= 0.5
        
        # Apply multiplier
        slippage = volatility * config.volatility_multiplier * 0.5
        
        return min(slippage, config.max_slippage)

    def _calculate_order_size_slippage(
        self,
        context: SlippageContext,
        config: SlippageConfig
    ) -> float:
        """Calculate order size-based slippage"""
        # Order size relative to volume
        size_ratio = context.size / context.volume
        
        # Base slippage from size
        slippage = size_ratio * config.order_size_multiplier
        
        # Adjust for order type
        if context.order_type == 'market':
            slippage *= 1.2
        
        return min(slippage, config.max_slippage)

    def _calculate_market_impact_slippage(
        self,
        context: SlippageContext,
        config: SlippageConfig
    ) -> float:
        """Calculate market impact slippage"""
        # Size relative to volume
        size_ratio = context.size / context.volume
        
        # Volatility factor
        vol_factor = context.volatility / 0.02
        
        # Market impact formula
        impact = (size_ratio ** 0.5) * vol_factor * config.market_impact_factor
        
        return min(impact, config.max_slippage)

    def _determine_severity(self, slippage_pct: float) -> SlippageSeverity:
        """Determine slippage severity"""
        if slippage_pct < 0.001:
            return SlippageSeverity.NONE
        elif slippage_pct < 0.005:
            return SlippageSeverity.LOW
        elif slippage_pct < 0.01:
            return SlippageSeverity.MEDIUM
        elif slippage_pct < 0.02:
            return SlippageSeverity.HIGH
        else:
            return SlippageSeverity.EXTREME

    def _record_slippage(
        self,
        request: SlippageRequest,
        result: SlippageResult
    ) -> None:
        """Record slippage for analytics"""
        record = SlippageRecord(
            timestamp=datetime.utcnow(),
            symbol=request.symbol,
            side=request.side,
            size=request.size,
            price=request.price,
            slippage=result.slippage_amount,
            slippage_pct=result.slippage_percentage,
            model=result.model.value,
            order_type=request.order_type
        )
        self._slippage_history.append(record)

    # =========================================================================
    # Configuration Management
    # =========================================================================

    async def set_config(
        self,
        symbol: str,
        config: SlippageConfig
    ) -> SlippageConfig:
        """
        Set slippage configuration for a symbol.
        
        Args:
            symbol: Symbol
            config: Slippage configuration
            
        Returns:
            SlippageConfig: Updated configuration
        """
        self._symbol_configs[symbol] = config
        logger.info(f"Slippage config set for {symbol}")
        return config

    async def get_config(self, symbol: str) -> SlippageConfig:
        """
        Get slippage configuration for a symbol.
        
        Args:
            symbol: Symbol
            
        Returns:
            SlippageConfig: Slippage configuration
        """
        return self._symbol_configs.get(symbol, self._default_config)

    async def reset_config(self, symbol: str) -> bool:
        """
        Reset slippage configuration to default.
        
        Args:
            symbol: Symbol
            
        Returns:
            bool: Success indicator
        """
        if symbol in self._symbol_configs:
            del self._symbol_configs[symbol]
            return True
        return False

    # =========================================================================
    # Analytics
    # =========================================================================

    async def get_analytics(
        self,
        period: str = "30d"
    ) -> SlippageAnalyticsResponse:
        """
        Get slippage analytics.
        
        Args:
            period: Analysis period
            
        Returns:
            SlippageAnalyticsResponse: Slippage analytics
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
            
            history = [h for h in self._slippage_history if h.timestamp >= cutoff]
            
            if not history:
                return SlippageAnalyticsResponse(
                    total_slippage=0,
                    avg_slippage_per_trade=0,
                    max_slippage=0,
                    min_slippage=0,
                    slippage_by_side={},
                    slippage_by_order_type={},
                    slippage_by_symbol={},
                    slippage_impact=0,
                    slippage_efficiency=0,
                    recommendations=["Insufficient data for analytics"]
                )
            
            # Calculate metrics
            slippages = [h.slippage for h in history]
            total_slippage = sum(slippages)
            avg_slippage = np.mean(slippages) if slippages else 0
            max_slippage = max(slippages) if slippages else 0
            min_slippage = min(slippages) if slippages else 0
            
            # By side
            by_side = {}
            for h in history:
                by_side[h.side] = by_side.get(h.side, 0) + h.slippage
            
            # By order type
            by_order_type = {}
            for h in history:
                by_order_type[h.order_type] = by_order_type.get(h.order_type, 0) + h.slippage
            
            # By symbol
            by_symbol = {}
            for h in history:
                by_symbol[h.symbol] = by_symbol.get(h.symbol, 0) + h.slippage
            
            # Slippage impact
            total_value = sum(h.size * h.price for h in history)
            slippage_impact = total_slippage / total_value if total_value > 0 else 0
            
            # Slippage efficiency
            slippage_efficiency = 1 - slippage_impact if slippage_impact < 1 else 0
            
            # Generate recommendations
            recommendations = []
            
            if slippage_impact > 0.01:
                recommendations.append("High slippage impact. Consider using limit orders.")
            
            if by_side.get('buy', 0) > by_side.get('sell', 0) * 1.5:
                recommendations.append("Higher slippage on buy orders. Consider adjusting timing.")
            
            if by_order_type.get('market', 0) > by_order_type.get('limit', 0) * 2:
                recommendations.append("High market order slippage. Use limit orders when possible.")
            
            if max_slippage > 0.02:
                recommendations.append("Extreme slippage detected. Review order sizing.")
            
            if not recommendations:
                recommendations.append("Slippage levels are within acceptable ranges.")
            
            return SlippageAnalyticsResponse(
                total_slippage=total_slippage,
                avg_slippage_per_trade=avg_slippage,
                max_slippage=max_slippage,
                min_slippage=min_slippage,
                slippage_by_side=by_side,
                slippage_by_order_type=by_order_type,
                slippage_by_symbol=by_symbol,
                slippage_impact=slippage_impact,
                slippage_efficiency=slippage_efficiency,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error getting slippage analytics: {e}")
            return SlippageAnalyticsResponse(
                total_slippage=0,
                avg_slippage_per_trade=0,
                max_slippage=0,
                min_slippage=0,
                slippage_by_side={},
                slippage_by_order_type={},
                slippage_by_symbol={},
                slippage_impact=0,
                slippage_efficiency=0,
                recommendations=["Error calculating slippage analytics"]
            )

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    async def bulk_calculate_slippage(
        self,
        requests: List[SlippageRequest]
    ) -> List[SlippageResponse]:
        """
        Calculate slippage for multiple trades.
        
        Args:
            requests: List of slippage requests
            
        Returns:
            List[SlippageResponse]: Slippage calculation results
        """
        results = []
        
        for request in requests:
            try:
                result = await self.calculate_slippage(request)
                results.append(result)
            except Exception as e:
                logger.error(f"Error calculating slippage for {request.symbol}: {e}")
                # Continue with next request
        
        return results

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def close(self) -> None:
        """Close the slippage module"""
        self._symbol_configs.clear()
        self._slippage_history.clear()
        self._analytics_cache.clear()
        logger.info("PaperTradingSlippage closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/paper-trading/slippage", tags=["Paper Trading Slippage"])


async def get_slippage() -> PaperTradingSlippage:
    """Dependency to get PaperTradingSlippage instance"""
    return PaperTradingSlippage()


@router.post("/calculate", response_model=SlippageResponse)
async def calculate_slippage(
    request: SlippageRequest,
    slippage: PaperTradingSlippage = Depends(get_slippage)
):
    """Calculate slippage for a trade"""
    return await slippage.calculate_slippage(request)


@router.post("/config/{symbol}")
async def set_slippage_config(
    symbol: str,
    config: SlippageConfig,
    slippage: PaperTradingSlippage = Depends(get_slippage)
):
    """Set slippage configuration for a symbol"""
    return await slippage.set_config(symbol, config)


@router.get("/config/{symbol}")
async def get_slippage_config(
    symbol: str,
    slippage: PaperTradingSlippage = Depends(get_slippage)
):
    """Get slippage configuration for a symbol"""
    return await slippage.get_config(symbol)


@router.delete("/config/{symbol}")
async def reset_slippage_config(
    symbol: str,
    slippage: PaperTradingSlippage = Depends(get_slippage)
):
    """Reset slippage configuration"""
    success = await slippage.reset_config(symbol)
    return {"success": success}


@router.get("/analytics")
async def get_slippage_analytics(
    period: str = Query("30d"),
    slippage: PaperTradingSlippage = Depends(get_slippage)
):
    """Get slippage analytics"""
    return await slippage.get_analytics(period)


@router.post("/bulk")
async def bulk_calculate_slippage(
    requests: List[SlippageRequest] = Body(..., embed=True),
    slippage: PaperTradingSlippage = Depends(get_slippage)
):
    """Calculate slippage for multiple trades"""
    return await slippage.bulk_calculate_slippage(requests)


@router.get("/models")
async def get_slippage_models():
    """Get available slippage models"""
    return {
        'models': [
            {'name': m.value, 'description': m.name.replace('_', ' ').title()}
            for m in SlippageModel
        ]
    }


@router.get("/severity-levels")
async def get_severity_levels():
    """Get severity levels"""
    return {
        'levels': [
            {'name': s.value, 'description': s.name.title()}
            for s in SlippageSeverity
        ]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PaperTradingSlippage',
    'SlippageModel',
    'SlippageSeverity',
    'SlippageConfig',
    'SlippageRequest',
    'SlippageResponse',
    'SlippageAnalyticsResponse',
    'SlippageContext',
    'SlippageResult',
    'SlippageRecord',
    'router'
]
