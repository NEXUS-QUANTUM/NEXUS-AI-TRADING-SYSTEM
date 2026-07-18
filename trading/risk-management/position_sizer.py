"""
NEXUS AI TRADING SYSTEM - Position Sizer Module
Copyright © 2026 NEXUS QUANTUM LTD
CEO: Dr X... - Majority Shareholder

Module: trading/risk-management/position_sizer.py
Description: Advanced position sizing with full API integration
"""

import asyncio
import logging
import math
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

import numpy as np
from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

# NEXUS Internal Imports
from shared.configs.risk_config import RiskConfig
from shared.constants.trading_constants import (
    POSITION_SIZING_METHODS,
    ORDER_TYPES,
    RISK_LEVELS
)
from shared.helpers.trading_helpers import (
    calculate_position_size,
    calculate_risk_reward_ratio,
    calculate_stop_loss_distance,
    calculate_take_profit_distance
)
from shared.types.risk import PositionSizingConfig, PositionSizingResult
from shared.utilities.retry import retry_async
from shared.utilities.logger import get_logger
from shared.utilities.circuit_breaker import CircuitBreaker
from shared.utilities.cache_utils import cached

# Database imports
from backend.database.models import Position, Order
from backend.database.repositories.position_repository import PositionRepository
from backend.database.repositories.trade_repository import TradeRepository
from backend.database.repositories.portfolio_repository import PortfolioRepository

# Broker imports
from trading.brokers.base import BaseBroker
from trading.brokers.broker_factory import BrokerFactory

# Risk management imports
from trading.risk_engine.position_sizer import PositionSizerEngine
from trading.risk_engine.risk_manager import RiskManager

logger = get_logger(__name__)


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class SizingMethod(str, Enum):
    """Position sizing methods"""
    FIXED = "fixed"  # Fixed percentage of portfolio
    KELLY = "kelly"  # Kelly Criterion
    OPTIMAL_F = "optimal_f"  # Optimal F
    RISK_BASED = "risk_based"  # Risk-based sizing
    VOLATILITY_BASED = "volatility_based"  # Volatility-adjusted
    PYRAMID = "pyramid"  # Pyramid scaling
    MARTINGALE = "martingale"  # Martingale (inverse)
    ANTI_MARTINGALE = "anti_martingale"  # Anti-Martingale
    FIXED_RISK = "fixed_risk"  # Fixed risk per trade
    PERCENTAGE = "percentage"  # Percentage of portfolio
    ATR = "atr"  # Average True Range based
    KELLY_FRACTIONAL = "kelly_fractional"  # Fractional Kelly
    OPTIMAL_F_SAFE = "optimal_f_safe"  # Safe Optimal F
    MONTE_CARLO = "monte_carlo"  # Monte Carlo optimized
    BAYESIAN = "bayesian"  # Bayesian adaptive


class RiskTolerance(str, Enum):
    """Risk tolerance levels"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    VERY_AGGRESSIVE = "very_aggressive"


class MarketCondition(str, Enum):
    """Market condition for adaptive sizing"""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    BREAKOUT = "breakout"
    RETRACEMENT = "retracement"


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class PositionSizingRequest(BaseModel):
    """Request model for position sizing"""
    symbol: str
    portfolio_id: str
    method: SizingMethod = SizingMethod.RISK_BASED
    risk_per_trade: float = 0.02  # 2% risk per trade (0.01 = 1%)
    max_position_pct: float = 0.10  # 10% max position of portfolio
    stop_loss_distance: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_distance: Optional[float] = None
    take_profit_pct: Optional[float] = None
    risk_reward_ratio: float = 2.0
    entry_price: Optional[float] = None
    current_price: Optional[float] = None
    volatility: Optional[float] = None
    confidence_score: Optional[float] = None
    market_condition: Optional[MarketCondition] = None
    account_balance: Optional[float] = None
    max_leverage: Optional[float] = None
    use_adaptive_sizing: bool = True
    include_slippage: bool = True

    @validator('risk_per_trade')
    def validate_risk_pct(cls, v):
        if not 0 < v <= 0.10:
            raise ValueError('Risk per trade must be between 0 and 10%')
        return v

    @validator('max_position_pct')
    def validate_max_position(cls, v):
        if not 0 < v <= 1.0:
            raise ValueError('Max position percentage must be between 0 and 100%')
        return v

    @validator('risk_reward_ratio')
    def validate_rr_ratio(cls, v):
        if v < 0.5:
            raise ValueError('Risk-reward ratio must be at least 0.5')
        return v


class PositionSizingResponse(BaseModel):
    """Response model for position sizing"""
    symbol: str
    portfolio_id: str
    method: str
    timestamp: datetime
    position_size: float
    position_value: float
    position_pct: float
    risk_amount: float
    risk_pct: float
    stop_loss_price: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_price: Optional[float] = None
    take_profit_pct: Optional[float] = None
    risk_reward_ratio: float
    confidence_score: Optional[float] = None
    max_position_size: float
    min_position_size: float
    adjusted_for_volatility: bool
    adjusted_for_market_condition: bool
    warnings: List[str] = []
    recommendations: List[str] = []


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SizingContext:
    """Context for position sizing calculations"""
    symbol: str
    portfolio_id: str
    method: SizingMethod
    risk_per_trade: float
    max_position_pct: float
    current_price: float
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    volatility: float = 0.02  # 2% default volatility
    confidence: float = 0.5
    market_condition: MarketCondition = MarketCondition.SIDEWAYS
    account_balance: float = 10000
    leverage: float = 1.0
    max_leverage: float = 2.0
    win_rate: float = 0.5
    avg_win: float = 0.05
    avg_loss: float = 0.02
    trade_count: int = 0
    consecutive_losses: int = 0
    consecutive_wins: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SizingResult:
    """Result of position sizing calculation"""
    size: float
    size_pct: float
    value: float
    risk: float
    risk_pct: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: float = 0.5
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class SizingHistory:
    """History of position sizing decisions"""
    timestamp: datetime
    symbol: str
    method: str
    size: float
    risk: float
    outcome: Optional[float] = None
    pnl: Optional[float] = None


# =============================================================================
# POSITION SIZER
# =============================================================================

class PositionSizer:
    """
    Advanced Position Sizer with full API integration.
    
    Supports multiple position sizing methods:
    - Kelly Criterion (full and fractional)
    - Optimal F
    - Risk-based sizing
    - Volatility-based sizing
    - Fixed percentage
    - Pyramid scaling
    - Adaptive sizing based on market conditions
    - Monte Carlo optimization
    - Bayesian adaptive sizing
    """

    def __init__(
        self,
        config: Optional[RiskConfig] = None,
        broker_factory: Optional[BrokerFactory] = None,
        position_repo: Optional[PositionRepository] = None,
        trade_repo: Optional[TradeRepository] = None,
        portfolio_repo: Optional[PortfolioRepository] = None
    ):
        """
        Initialize PositionSizer.
        
        Args:
            config: Risk configuration
            broker_factory: Factory for broker instances
            position_repo: Position repository
            trade_repo: Trade repository
            portfolio_repo: Portfolio repository
        """
        self.config = config or RiskConfig()
        self.broker_factory = broker_factory or BrokerFactory()
        self.position_repo = position_repo or PositionRepository()
        self.trade_repo = trade_repo or TradeRepository()
        self.portfolio_repo = portfolio_repo or PortfolioRepository()
        
        # Risk manager for risk calculations
        self.risk_manager = RiskManager(config)
        
        # Position sizing history
        self._sizing_history: List[SizingHistory] = []
        
        # Market data cache
        self._market_data_cache: Dict[str, Any] = {}
        
        # Performance tracking for adaptive sizing
        self._performance_tracker: Dict[str, Dict[str, Any]] = {}
        
        logger.info("PositionSizer initialized")

    @retry_async(max_attempts=3, delay=0.5)
    async def calculate_position_size(
        self,
        request: PositionSizingRequest
    ) -> PositionSizingResponse:
        """
        Calculate optimal position size based on request parameters.
        
        Args:
            request: Position sizing request
            
        Returns:
            PositionSizingResponse: Calculated position size
        """
        try:
            # Validate request
            await self._validate_request(request)
            
            # Build sizing context
            context = await self._build_sizing_context(request)
            
            # Get portfolio balance
            portfolio = await self.portfolio_repo.get_by_id(request.portfolio_id)
            if not portfolio:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Portfolio {request.portfolio_id} not found"
                )
            
            balance = request.account_balance or float(portfolio.total_value)
            context.account_balance = balance
            
            # Get market data
            market_data = await self._get_market_data(request.symbol)
            context.current_price = request.current_price or market_data.get('price', 100)
            context.volatility = request.volatility or market_data.get('volatility', 0.02)
            
            # Get historical performance for adaptive sizing
            if request.use_adaptive_sizing:
                await self._update_performance_context(context)
            
            # Calculate position size based on method
            result = await self._calculate_by_method(context, request.method)
            
            # Adjust for slippage if requested
            if request.include_slippage:
                result = await self._adjust_for_slippage(result, market_data)
            
            # Validate against limits
            result = await self._validate_sizing_result(result, context)
            
            # Record sizing decision
            await self._record_sizing_decision(context, result)
            
            # Build response
            return self._build_response(request, context, result)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error calculating position size: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Position sizing failed: {str(e)}"
            )

    async def _validate_request(self, request: PositionSizingRequest) -> None:
        """Validate position sizing request"""
        if request.risk_per_trade <= 0:
            raise ValueError("Risk per trade must be positive")
        
        if request.max_position_pct <= 0 or request.max_position_pct > 1:
            raise ValueError("Max position percentage must be between 0 and 1")
        
        if request.risk_reward_ratio < 0.5:
            raise ValueError("Risk-reward ratio must be at least 0.5")
        
        if request.stop_loss_distance is not None and request.stop_loss_distance <= 0:
            raise ValueError("Stop loss distance must be positive")
        
        if request.take_profit_distance is not None and request.take_profit_distance <= 0:
            raise ValueError("Take profit distance must be positive")
        
        if request.confidence_score is not None:
            if not 0 <= request.confidence_score <= 1:
                raise ValueError("Confidence score must be between 0 and 1")

    async def _build_sizing_context(
        self,
        request: PositionSizingRequest
    ) -> SizingContext:
        """Build sizing context from request"""
        return SizingContext(
            symbol=request.symbol,
            portfolio_id=request.portfolio_id,
            method=request.method,
            risk_per_trade=request.risk_per_trade,
            max_position_pct=request.max_position_pct,
            current_price=request.current_price or 0,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss_distance,
            take_profit=request.take_profit_distance,
            volatility=request.volatility or 0.02,
            confidence=request.confidence_score or 0.5,
            market_condition=request.market_condition or MarketCondition.SIDEWAYS,
            max_leverage=request.max_leverage or 2.0,
            leverage=1.0
        )

    async def _get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get market data for symbol"""
        # Check cache first
        if symbol in self._market_data_cache:
            cache_time = self._market_data_cache[symbol].get('timestamp')
            if cache_time and (datetime.utcnow() - cache_time).seconds < 60:
                return self._market_data_cache[symbol]['data']
        
        market_data = {}
        
        try:
            # Try broker API
            brokers = self.broker_factory.get_active_brokers()
            for broker in brokers:
                try:
                    ticker = await broker.get_ticker(symbol)
                    market_data = {
                        'price': float(ticker.get('price', 0)),
                        'high': float(ticker.get('high', 0)),
                        'low': float(ticker.get('low', 0)),
                        'volume': float(ticker.get('volume', 0)),
                        'change': float(ticker.get('change', 0)),
                        'change_pct': float(ticker.get('change_pct', 0))
                    }
                    
                    # Calculate volatility from recent data
                    try:
                        candles = await broker.get_historical_candles(
                            symbol,
                            timeframe='1h',
                            limit=24
                        )
                        if candles and len(candles) > 1:
                            prices = [c['close'] for c in candles]
                            returns = [(prices[i] - prices[i-1]) / prices[i-1] 
                                      for i in range(1, len(prices))]
                            market_data['volatility'] = float(np.std(returns) * np.sqrt(252))
                    except Exception:
                        market_data['volatility'] = 0.02
                    
                    break
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error getting market data for {symbol}: {e}")
        
        # Fallback to mock data
        if not market_data:
            market_data = self._generate_mock_market_data(symbol)
        
        # Cache data
        self._market_data_cache[symbol] = {
            'data': market_data,
            'timestamp': datetime.utcnow()
        }
        
        return market_data

    def _generate_mock_market_data(self, symbol: str) -> Dict[str, Any]:
        """Generate mock market data"""
        base_price = {
            'BTC-USD': 50000,
            'ETH-USD': 3000,
            'SPY': 500,
            'AAPL': 150,
            'MSFT': 350,
            'GOOGL': 140,
            'AMZN': 180,
            'TSLA': 250,
            'NVDA': 800
        }.get(symbol, 100)
        
        price = base_price * (1 + np.random.normal(0, 0.01))
        
        return {
            'price': float(price),
            'high': float(price * 1.02),
            'low': float(price * 0.98),
            'volume': float(np.random.randint(1000, 1000000)),
            'change': float(np.random.normal(0, 0.01)),
            'change_pct': float(np.random.normal(0, 0.01) * 100),
            'volatility': float(np.random.uniform(0.01, 0.05))
        }

    async def _update_performance_context(self, context: SizingContext) -> None:
        """Update context with performance data for adaptive sizing"""
        try:
            # Get recent trades
            trades = await self.trade_repo.get_by_symbol(
                context.symbol,
                limit=50
            )
            
            if not trades:
                return
            
            # Calculate win rate
            wins = [t for t in trades if float(t.pnl) > 0]
            context.win_rate = len(wins) / len(trades) if trades else 0.5
            
            # Calculate average win/loss
            win_pnls = [float(t.pnl) for t in trades if float(t.pnl) > 0]
            loss_pnls = [float(t.pnl) for t in trades if float(t.pnl) < 0]
            
            context.avg_win = np.mean(win_pnls) if win_pnls else 0.05
            context.avg_loss = abs(np.mean(loss_pnls)) if loss_pnls else 0.02
            
            # Count consecutive wins/losses
            if trades:
                last_trades = trades[-10:]
                consecutive_wins = 0
                consecutive_losses = 0
                
                for t in reversed(last_trades):
                    if float(t.pnl) > 0:
                        consecutive_wins += 1
                        consecutive_losses = 0
                    else:
                        consecutive_losses += 1
                        consecutive_wins = 0
                
                context.consecutive_wins = consecutive_wins
                context.consecutive_losses = consecutive_losses
            
            context.trade_count = len(trades)
            
        except Exception as e:
            logger.warning(f"Error updating performance context: {e}")

    async def _calculate_by_method(
        self,
        context: SizingContext,
        method: SizingMethod
    ) -> SizingResult:
        """
        Calculate position size using specified method.
        
        Args:
            context: Sizing context
            method: Sizing method
            
        Returns:
            SizingResult: Calculated sizing result
        """
        result = None
        
        if method == SizingMethod.KELLY:
            result = await self._calculate_kelly(context)
        elif method == SizingMethod.KELLY_FRACTIONAL:
            result = await self._calculate_kelly_fractional(context)
        elif method == SizingMethod.OPTIMAL_F:
            result = await self._calculate_optimal_f(context)
        elif method == SizingMethod.OPTIMAL_F_SAFE:
            result = await self._calculate_optimal_f_safe(context)
        elif method == SizingMethod.RISK_BASED:
            result = await self._calculate_risk_based(context)
        elif method == SizingMethod.VOLATILITY_BASED:
            result = await self._calculate_volatility_based(context)
        elif method == SizingMethod.FIXED:
            result = await self._calculate_fixed(context)
        elif method == SizingMethod.PYRAMID:
            result = await self._calculate_pyramid(context)
        elif method == SizingMethod.MARTINGALE:
            result = await self._calculate_martingale(context)
        elif method == SizingMethod.ANTI_MARTINGALE:
            result = await self._calculate_anti_martingale(context)
        elif method == SizingMethod.FIXED_RISK:
            result = await self._calculate_fixed_risk(context)
        elif method == SizingMethod.PERCENTAGE:
            result = await self._calculate_percentage(context)
        elif method == SizingMethod.ATR:
            result = await self._calculate_atr_based(context)
        elif method == SizingMethod.MONTE_CARLO:
            result = await self._calculate_monte_carlo(context)
        elif method == SizingMethod.BAYESIAN:
            result = await self._calculate_bayesian(context)
        else:
            result = await self._calculate_risk_based(context)
        
        # Apply adaptive adjustments
        if context.market_condition and context.confidence:
            result = await self._apply_adaptive_adjustments(result, context)
        
        return result

    # -------------------------------------------------------------------------
    # Sizing Method Implementations
    # -------------------------------------------------------------------------

    async def _calculate_kelly(self, context: SizingContext) -> SizingResult:
        """
        Calculate position size using Full Kelly Criterion.
        
        Kelly fraction = (win_rate - (1 - win_rate) / (avg_win / avg_loss))
        
        WARNING: Full Kelly can be aggressive.
        """
        try:
            win_rate = context.win_rate
            avg_win = context.avg_win or 0.05
            avg_loss = context.avg_loss or 0.02
            
            if avg_loss <= 0:
                return await self._calculate_risk_based(context)
            
            # Kelly fraction
            kelly = (win_rate - (1 - win_rate) * (avg_loss / avg_win))
            
            # Limit Kelly to reasonable range
            kelly = max(0, min(kelly, 0.25))  # Max 25% of portfolio
            
            # Calculate position size
            size_pct = kelly
            size = size_pct * context.account_balance / context.current_price
            
            # Calculate risk
            risk_pct = size_pct * context.risk_per_trade
            risk = risk_pct * context.account_balance
            
            # Determine stop loss
            stop_loss = context.stop_loss or (context.current_price * (1 - 0.02))
            if not context.stop_loss:
                stop_loss = await self._calculate_stop_loss_from_risk(
                    context,
                    risk
                )
            
            return SizingResult(
                size=float(size),
                size_pct=float(size_pct),
                value=float(size * context.current_price),
                risk=float(risk),
                risk_pct=float(risk_pct),
                stop_loss=float(stop_loss) if stop_loss else None,
                confidence=float(context.confidence),
                warnings=[
                    "Full Kelly can be aggressive. Consider using fractional Kelly."
                ] if kelly > 0.15 else []
            )
            
        except Exception as e:
            logger.error(f"Kelly calculation error: {e}")
            return await self._calculate_risk_based(context)

    async def _calculate_kelly_fractional(
        self,
        context: SizingContext
    ) -> SizingResult:
        """
        Calculate position size using Fractional Kelly Criterion.
        
        Uses a fraction (default 0.5) of the full Kelly to reduce risk.
        """
        try:
            # Get full Kelly result
            kelly_result = await self._calculate_kelly(context)
            
            # Apply fraction (0.25 to 0.75 depending on confidence)
            fraction = 0.25 + (0.5 * context.confidence)
            
            size_pct = kelly_result.size_pct * fraction
            size = size_pct * context.account_balance / context.current_price
            
            # Calculate risk
            risk_pct = size_pct * context.risk_per_trade
            risk = risk_pct * context.account_balance
            
            return SizingResult(
                size=float(size),
                size_pct=float(size_pct),
                value=float(size * context.current_price),
                risk=float(risk),
                risk_pct=float(risk_pct),
                stop_loss=kelly_result.stop_loss,
                confidence=float(context.confidence),
                warnings=[]
            )
            
        except Exception as e:
            logger.error(f"Fractional Kelly calculation error: {e}")
            return await self._calculate_risk_based(context)

    async def _calculate_optimal_f(self, context: SizingContext) -> SizingResult:
        """
        Calculate position size using Optimal F (Ralph Vince).
        
        Optimal F maximizes geometric growth by finding the optimal
        fraction to risk per trade based on historical outcomes.
        """
        try:
            # Get historical trades
            trades = await self.trade_repo.get_by_symbol(
                context.symbol,
                limit=100
            )
            
            if not trades or len(trades) < 10:
                return await self._calculate_risk_based(context)
            
            # Calculate trade outcomes as percentages
            outcomes = []
            for trade in trades:
                pnl = float(trade.pnl)
                if pnl != 0:
                    # Calculate percentage return relative to trade size
                    size = float(trade.size) if hasattr(trade, 'size') else 1
                    outcome = pnl / (size * context.current_price) if size > 0 else 0
                    outcomes.append(outcome)
            
            if not outcomes:
                return await self._calculate_risk_based(context)
            
            # Find optimal f using Brent's method or grid search
            optimal_f = self._find_optimal_f(outcomes)
            
            # Apply safety factor
            optimal_f = min(optimal_f, 0.25)  # Cap at 25% of portfolio
            
            size_pct = optimal_f
            size = size_pct * context.account_balance / context.current_price
            
            # Calculate risk
            risk_pct = size_pct * context.risk_per_trade
            risk = risk_pct * context.account_balance
            
            return SizingResult(
                size=float(size),
                size_pct=float(size_pct),
                value=float(size * context.current_price),
                risk=float(risk),
                risk_pct=float(risk_pct),
                confidence=float(context.confidence)
            )
            
        except Exception as e:
            logger.error(f"Optimal F calculation error: {e}")
            return await self._calculate_risk_based(context)

    def _find_optimal_f(self, outcomes: List[float]) -> float:
        """
        Find optimal f using grid search.
        
        Args:
            outcomes: List of outcome percentages
            
        Returns:
            float: Optimal f
        """
        try:
            best_f = 0.0
            best_geometric = 0.0
            
            # Grid search from 0.001 to 0.5
            for f in np.arange(0.001, 0.5, 0.005):
                # Calculate geometric growth
                g = 1.0
                for outcome in outcomes:
                    g *= (1 + f * outcome)
                
                if g > best_geometric and g > 0:
                    best_geometric = g
                    best_f = f
            
            return float(best_f)
            
        except Exception:
            return 0.05  # Default to 5%

    async def _calculate_optimal_f_safe(
        self,
        context: SizingContext
    ) -> SizingResult:
        """
        Calculate position size using Safe Optimal F.
        
        Uses a more conservative fraction of Optimal F.
        """
        try:
            # Get Optimal F result
            optimal_result = await self._calculate_optimal_f(context)
            
            # Use 0.5 of optimal f for safety
            safe_factor = 0.5
            size_pct = optimal_result.size_pct * safe_factor
            
            size = size_pct * context.account_balance / context.current_price
            
            # Calculate risk
            risk_pct = size_pct * context.risk_per_trade
            risk = risk_pct * context.account_balance
            
            return SizingResult(
                size=float(size),
                size_pct=float(size_pct),
                value=float(size * context.current_price),
                risk=float(risk),
                risk_pct=float(risk_pct),
                stop_loss=optimal_result.stop_loss,
                confidence=float(context.confidence)
            )
            
        except Exception as e:
            logger.error(f"Safe Optimal F calculation error: {e}")
            return await self._calculate_risk_based(context)

    async def _calculate_risk_based(self, context: SizingContext) -> SizingResult:
        """
        Calculate position size based on risk per trade.
        
        This is the most common professional approach.
        """
        try:
            # Determine stop loss distance
            stop_loss_pct = context.stop_loss
            if not stop_loss_pct:
                # Calculate from ATR or fixed percentage
                stop_loss_pct = await self._calculate_stop_loss_pct(context)
            
            # Calculate position size based on risk
            risk_amount = context.risk_per_trade * context.account_balance
            size = risk_amount / (stop_loss_pct * context.current_price)
            
            # Cap by max position percentage
            max_size = context.max_position_pct * context.account_balance / context.current_price
            size = min(size, max_size)
            
            # Calculate actual risk
            actual_risk = size * context.current_price * stop_loss_pct
            actual_risk_pct = actual_risk / context.account_balance
            
            size_pct = size * context.current_price / context.account_balance
            
            # Calculate stop loss price
            stop_loss_price = context.current_price * (1 - stop_loss_pct)
            
            # Calculate take profit if risk-reward ratio is set
            take_profit_price = None
            if context.risk_reward_ratio:
                take_profit_pct = stop_loss_pct * context.risk_reward_ratio
                take_profit_price = context.current_price * (1 + take_profit_pct)
            
            return SizingResult(
                size=float(size),
                size_pct=float(size_pct),
                value=float(size * context.current_price),
                risk=float(actual_risk),
                risk_pct=float(actual_risk_pct),
                stop_loss=float(stop_loss_price) if stop_loss_price else None,
                take_profit=float(take_profit_price) if take_profit_price else None,
                confidence=float(context.confidence)
            )
            
        except Exception as e:
            logger.error(f"Risk-based calculation error: {e}")
            return SizingResult(
                size=0.0,
                size_pct=0.0,
                value=0.0,
                risk=0.0,
                risk_pct=0.0,
                warnings=["Risk-based sizing failed"]
            )

    async def _calculate_volatility_based(
        self,
        context: SizingContext
    ) -> SizingResult:
        """
        Calculate position size adjusted for volatility.
        
        Inverse relationship: higher volatility = smaller position.
        """
        try:
            # Base size from risk-based sizing
            risk_result = await self._calculate_risk_based(context)
            
            # Adjust for volatility
            volatility = context.volatility or 0.02
            
            # Normalize volatility (20% annualized volatility = 1.0)
            normalized_vol = volatility / 0.20
            vol_adjustment = 1.0 / (1.0 + normalized_vol)
            
            # Apply adjustment
            size_pct = risk_result.size_pct * vol_adjustment
            size = size_pct * context.account_balance / context.current_price
            
            # Limit to max position
            max_size = context.max_position_pct * context.account_balance / context.current_price
            size = min(size, max_size)
            
            # Recalculate risk
            stop_loss_pct = await self._calculate_stop_loss_pct(context)
            risk = size * context.current_price * stop_loss_pct
            risk_pct = risk / context.account_balance
            
            return SizingResult(
                size=float(size),
                size_pct=float(size_pct),
                value=float(size * context.current_price),
                risk=float(risk),
                risk_pct=float(risk_pct),
                stop_loss=risk_result.stop_loss,
                take_profit=risk_result.take_profit,
                confidence=float(context.confidence * vol_adjustment),
                warnings=[
                    f"Position size reduced by {((1 - vol_adjustment) * 100):.1f}% due to volatility"
                ] if vol_adjustment < 0.8 else []
            )
            
        except Exception as e:
            logger.error(f"Volatility-based calculation error: {e}")
            return await self._calculate_risk_based(context)

    async def _calculate_fixed(self, context: SizingContext) -> SizingResult:
        """Calculate position size using fixed percentage of portfolio"""
        try:
            fixed_pct = 0.02  # 2% fixed position
            
            size_pct = fixed_pct
            size = size_pct * context.account_balance / context.current_price
            
            # Calculate risk
            stop_loss_pct = await self._calculate_stop_loss_pct(context)
            risk = size * context.current_price * stop_loss_pct
            risk_pct = risk / context.account_balance
            
            return SizingResult(
                size=float(size),
                size_pct=float(size_pct),
                value=float(size * context.current_price),
                risk=float(risk),
                risk_pct=float(risk_pct),
                confidence=float(context.confidence),
                warnings=["Fixed sizing doesn't adapt to market conditions"]
            )
            
        except Exception as e:
            logger.error(f"Fixed calculation error: {e}")
            return await self._calculate_risk_based(context)

    async def _calculate_pyramid(self, context: SizingContext) -> SizingResult:
        """
        Calculate position size for pyramid scaling.
        
        Adds to positions as they move in your favor.
        """
        try:
            # Base size (reduced for pyramid entry)
            base_size_pct = context.risk_per_trade * 0.5
            base_size = base_size_pct * context.account_balance / context.current_price
            
            # Additional layers (up to 3)
            total_size_pct = base_size_pct * 2  # Max 2x base size
            
            # Determine if we're adding to an existing position
            # Get current positions
            positions = await self.position_repo.get_by_symbol(
                context.symbol,
                portfolio_id=context.portfolio_id
            )
            
            if positions:
                # Check if we're in profit
                avg_price = sum(p.entry_price for p in positions) / len(positions)
                if context.current_price > avg_price:
                    # Add additional size
                    add_size_pct = base_size_pct * 0.5
                    total_size_pct = min(total_size_pct + add_size_pct, 
                                        context.max_position_pct)
            
            size_pct = min(total_size_pct, context.max_position_pct)
            size = size_pct * context.account_balance / context.current_price
            
            # Calculate risk
            stop_loss_pct = await self._calculate_stop_loss_pct(context)
            risk = size * context.current_price * stop_loss_pct
            risk_pct = risk / context.account_balance
            
            return SizingResult(
                size=float(size),
                size_pct=float(size_pct),
                value=float(size * context.current_price),
                risk=float(risk),
                risk_pct=float(risk_pct),
                confidence=float(context.confidence),
                recommendations=[
                    "Consider scaling in with multiple entries",
                    "Use trailing stop for pyramid positions"
                ]
            )
            
        except Exception as e:
            logger.error(f"Pyramid calculation error: {e}")
            return await self._calculate_risk_based(context)

    async def _calculate_martingale(self, context: SizingContext) -> SizingResult:
        """
        Calculate position size using Martingale.
        
        WARNING: Doubles position size after losses.
        High risk strategy - use with caution.
        """
        try:
            # Base size
            base_size_pct = context.risk_per_trade * 0.5
            base_size = base_size_pct * context.account_balance / context.current_price
            
            # Double size for each consecutive loss
            multiplier = 2 ** context.consecutive_losses
            size_pct = min(base_size_pct * multiplier, context.max_position_pct)
            size = size_pct * context.account_balance / context.current_price
            
            # Calculate risk
            stop_loss_pct = await self._calculate_stop_loss_pct(context)
            risk = size * context.current_price * stop_loss_pct
            risk_pct = risk / context.account_balance
            
            return SizingResult(
                size=float(size),
                size_pct=float(size_pct),
                value=float(size * context.current_price),
                risk=float(risk),
                risk_pct=float(risk_pct),
                confidence=float(context.confidence * 0.5),
                warnings=[
                    "Martingale is high risk!",
                    f"Size increased {multiplier}x due to {context.consecutive_losses} consecutive losses",
                    "Consider using Anti-Martingale instead"
                ]
            )
            
        except Exception as e:
            logger.error(f"Martingale calculation error: {e}")
            return await self._calculate_risk_based(context)

    async def _calculate_anti_martingale(
        self,
        context: SizingContext
    ) -> SizingResult:
        """
        Calculate position size using Anti-Martingale.
        
        Increases position size after wins (momentum-based).
        """
        try:
            # Base size
            base_size_pct = context.risk_per_trade * 0.5
            base_size = base_size_pct * context.account_balance / context.current_price
            
            # Increase size for consecutive wins
            multiplier = 1 + (context.consecutive_wins * 0.1)  # 10% increase per win
            size_pct = min(base_size_pct * multiplier, context.max_position_pct)
            size = size_pct * context.account_balance / context.current_price
            
            # Calculate risk
            stop_loss_pct = await self._calculate_stop_loss_pct(context)
            risk = size * context.current_price * stop_loss_pct
            risk_pct = risk / context.account_balance
            
            return SizingResult(
                size=float(size),
                size_pct=float(size_pct),
                value=float(size * context.current_price),
                risk=float(risk),
                risk_pct=float(risk_pct),
                confidence=float(context.confidence * (1 + context.consecutive_wins * 0.05)),
                recommendations=[
                    f"Increased size by {((multiplier - 1) * 100):.1f}% due to {context.consecutive_wins} consecutive wins",
                    "Use trailing stop to protect gains"
                ]
            )
            
        except Exception as e:
            logger.error(f"Anti-Martingale calculation error: {e}")
            return await self._calculate_risk_based(context)

    async def _calculate_fixed_risk(self, context: SizingContext) -> SizingResult:
        """Calculate position size with fixed risk amount"""
        try:
            # Fixed risk amount (e.g., $200)
            fixed_risk = context.risk_per_trade * context.account_balance
            stop_loss_pct = await self._calculate_stop_loss_pct(context)
            
            size = fixed_risk / (stop_loss_pct * context.current_price)
            size_pct = size * context.current_price / context.account_balance
            
            # Cap by max position
            max_size = context.max_position_pct * context.account_balance / context.current_price
            size = min(size, max_size)
            
            # Recalculate risk
            actual_risk = size * context.current_price * stop_loss_pct
            actual_risk_pct = actual_risk / context.account_balance
            
            return SizingResult(
                size=float(size),
                size_pct=float(size_pct),
                value=float(size * context.current_price),
                risk=float(actual_risk),
                risk_pct=float(actual_risk_pct),
                confidence=float(context.confidence)
            )
            
        except Exception as e:
            logger.error(f"Fixed risk calculation error: {e}")
            return await self._calculate_risk_based(context)

    async def _calculate_percentage(self, context: SizingContext) -> SizingResult:
        """Calculate position size as percentage of portfolio"""
        try:
            # Use the risk per trade as the percentage
            size_pct = context.risk_per_trade
            size = size_pct * context.account_balance / context.current_price
            
            # Calculate risk
            stop_loss_pct = await self._calculate_stop_loss_pct(context)
            risk = size * context.current_price * stop_loss_pct
            risk_pct = risk / context.account_balance
            
            return SizingResult(
                size=float(size),
                size_pct=float(size_pct),
                value=float(size * context.current_price),
                risk=float(risk),
                risk_pct=float(risk_pct),
                confidence=float(context.confidence)
            )
            
        except Exception as e:
            logger.error(f"Percentage calculation error: {e}")
            return await self._calculate_risk_based(context)

    async def _calculate_atr_based(self, context: SizingContext) -> SizingResult:
        """Calculate position size based on Average True Range"""
        try:
            # Get ATR from market data
            atr = context.volatility * context.current_price
            
            # Stop loss distance = N * ATR (N = 1-3)
            atr_multiplier = 2
            stop_loss_distance = atr * atr_multiplier
            
            # Calculate position size
            risk_amount = context.risk_per_trade * context.account_balance
            size = risk_amount / stop_loss_distance
            
            # Cap by max position
            max_size = context.max_position_pct * context.account_balance / context.current_price
            size = min(size, max_size)
            
            size_pct = size * context.current_price / context.account_balance
            
            # Calculate stop loss price
            stop_loss_price = context.current_price - stop_loss_distance
            
            # Take profit based on risk-reward ratio
            take_profit_price = None
            if context.risk_reward_ratio:
                take_profit_pct = stop_loss_distance / context.current_price * context.risk_reward_ratio
                take_profit_price = context.current_price + (take_profit_pct * context.current_price)
            
            # Calculate actual risk
            actual_risk = size * stop_loss_distance
            actual_risk_pct = actual_risk / context.account_balance
            
            return SizingResult(
                size=float(size),
                size_pct=float(size_pct),
                value=float(size * context.current_price),
                risk=float(actual_risk),
                risk_pct=float(actual_risk_pct),
                stop_loss=float(stop_loss_price) if stop_loss_price else None,
                take_profit=float(take_profit_price) if take_profit_price else None,
                confidence=float(context.confidence),
                warnings=["ATR-based sizing can be sensitive to volatility spikes"]
            )
            
        except Exception as e:
            logger.error(f"ATR-based calculation error: {e}")
            return await self._calculate_risk_based(context)

    async def _calculate_monte_carlo(self, context: SizingContext) -> SizingResult:
        """
        Calculate position size using Monte Carlo simulation.
        
        Simulates thousands of scenarios to find optimal size.
        """
        try:
            # Parameters for simulation
            n_simulations = 10000
            expected_return = context.win_rate * context.avg_win - (1 - context.win_rate) * context.avg_loss
            volatility = context.volatility
            
            # Find optimal size through simulation
            best_size = 0.0
            best_sharpe = -float('inf')
            
            # Test different size percentages
            for size_pct in np.arange(0.001, context.max_position_pct, 0.005):
                results = []
                
                for _ in range(n_simulations):
                    # Simulate returns
                    returns = []
                    capital = context.account_balance
                    
                    for _ in range(20):  # 20 periods
                        # Generate random return
                        ret = np.random.normal(expected_return, volatility)
                        pnl = size_pct * capital * ret
                        capital += pnl
                        returns.append(ret)
                    
                    # Calculate Sharpe ratio
                    if len(returns) > 1 and np.std(returns) > 0:
                        sharpe = np.mean(returns) / np.std(returns)
                        results.append(sharpe)
                
                if results:
                    avg_sharpe = np.mean(results)
                    if avg_sharpe > best_sharpe:
                        best_sharpe = avg_sharpe
                        best_size = size_pct
            
            # Use optimal size
            size_pct = min(best_size, context.max_position_pct)
            size = size_pct * context.account_balance / context.current_price
            
            # Calculate risk
            stop_loss_pct = await self._calculate_stop_loss_pct(context)
            risk = size * context.current_price * stop_loss_pct
            risk_pct = risk / context.account_balance
            
            return SizingResult(
                size=float(size),
                size_pct=float(size_pct),
                value=float(size * context.current_price),
                risk=float(risk),
                risk_pct=float(risk_pct),
                confidence=float(context.confidence),
                warnings=["Monte Carlo sizing requires sufficient historical data"]
            )
            
        except Exception as e:
            logger.error(f"Monte Carlo calculation error: {e}")
            return await self._calculate_risk_based(context)

    async def _calculate_bayesian(self, context: SizingContext) -> SizingResult:
        """
        Calculate position size using Bayesian adaptive method.
        
        Updates beliefs about optimal size based on outcomes.
        """
        try:
            # Get historical sizing performance
            history = [h for h in self._sizing_history 
                      if h.symbol == context.symbol]
            
            # Prior belief: use risk-based sizing
            prior_result = await self._calculate_risk_based(context)
            
            if len(history) < 10:
                return prior_result
            
            # Calculate posterior
            outcomes = []
            sizes = []
            
            for h in history[-50:]:
                if h.outcome is not None:
                    outcomes.append(h.outcome)
                    sizes.append(h.size)
            
            if not outcomes:
                return prior_result
            
            # Fit a Bayesian model
            # Simple approach: adjust based on average outcome
            avg_outcome = np.mean(outcomes)
            
            # Bayesian adjustment factor
            if avg_outcome > 0:
                adjustment = 1 + (avg_outcome * 0.5)
            else:
                adjustment = 1 / (1 + abs(avg_outcome))
            
            # Apply adjustment to prior
            size_pct = min(prior_result.size_pct * adjustment, context.max_position_pct)
            size = size_pct * context.account_balance / context.current_price
            
            # Calculate risk
            stop_loss_pct = await self._calculate_stop_loss_pct(context)
            risk = size * context.current_price * stop_loss_pct
            risk_pct = risk / context.account_balance
            
            return SizingResult(
                size=float(size),
                size_pct=float(size_pct),
                value=float(size * context.current_price),
                risk=float(risk),
                risk_pct=float(risk_pct),
                confidence=float(context.confidence * (1 + abs(avg_outcome) * 0.5)),
                recommendations=[
                    f"Bayesian adjustment: {adjustment:.2f}x based on historical performance"
                ]
            )
            
        except Exception as e:
            logger.error(f"Bayesian calculation error: {e}")
            return await self._calculate_risk_based(context)

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    async def _calculate_stop_loss_pct(self, context: SizingContext) -> float:
        """Calculate stop loss percentage"""
        if context.stop_loss:
            return float(context.stop_loss)
        
        # Default: use volatility-based stop loss
        volatility = context.volatility or 0.02
        return float(min(volatility * 2, 0.10))  # Cap at 10%

    async def _calculate_stop_loss_from_risk(
        self,
        context: SizingContext,
        risk_amount: float
    ) -> Optional[float]:
        """Calculate stop loss price from risk amount"""
        if not context.current_price or risk_amount <= 0:
            return None
        
        # Risk as percentage of price
        risk_pct = risk_amount / (context.size or 1)
        stop_loss_pct = min(risk_pct / context.current_price, 0.10)
        
        return context.current_price * (1 - stop_loss_pct)

    async def _apply_adaptive_adjustments(
        self,
        result: SizingResult,
        context: SizingContext
    ) -> SizingResult:
        """Apply adaptive adjustments based on market conditions"""
        adjustments = []
        
        # Market condition adjustments
        if context.market_condition == MarketCondition.BULL:
            # Increase size in bull market
            multiplier = 1.1
            adjustments.append("Bull market: +10% size adjustment")
            
        elif context.market_condition == MarketCondition.BEAR:
            # Decrease size in bear market
            multiplier = 0.7
            adjustments.append("Bear market: -30% size adjustment")
            
        elif context.market_condition == MarketCondition.HIGH_VOLATILITY:
            # Decrease size in high volatility
            multiplier = 0.5
            adjustments.append("High volatility: -50% size adjustment")
            
        elif context.market_condition == MarketCondition.LOW_VOLATILITY:
            # Increase size in low volatility
            multiplier = 1.2
            adjustments.append("Low volatility: +20% size adjustment")
            
        elif context.market_condition == MarketCondition.BREAKOUT:
            # Moderate increase in breakouts
            multiplier = 1.15
            adjustments.append("Breakout: +15% size adjustment")
            
        elif context.market_condition == MarketCondition.RETRACEMENT:
            # Conservative in retracements
            multiplier = 0.8
            adjustments.append("Retracement: -20% size adjustment")
            
        else:
            multiplier = 1.0
        
        # Apply multiplier
        result.size *= multiplier
        result.size_pct *= multiplier
        result.value *= multiplier
        result.risk *= multiplier
        result.risk_pct *= multiplier
        result.warnings.extend(adjustments)
        
        return result

    async def _adjust_for_slippage(
        self,
        result: SizingResult,
        market_data: Dict[str, Any]
    ) -> SizingResult:
        """Adjust position size for slippage"""
        # Estimate slippage based on volume and volatility
        volume = market_data.get('volume', 1000000)
        volatility = market_data.get('volatility', 0.02)
        
        # Slippage estimation
        slippage = 0.0005 + (volatility * 0.01)  # 0.05% base + volatility adjustment
        slippage = min(slippage, 0.01)  # Cap at 1%
        
        # Apply slippage adjustment
        result.size *= (1 - slippage)
        result.value *= (1 - slippage)
        
        return result

    async def _validate_sizing_result(
        self,
        result: SizingResult,
        context: SizingContext
    ) -> SizingResult:
        """Validate and cap position sizing result"""
        # Cap by max position
        max_size = context.max_position_pct * context.account_balance / context.current_price
        if result.size > max_size:
            result.size = max_size
            result.size_pct = context.max_position_pct
            result.value = result.size * context.current_price
            result.risk = result.value * (result.stop_loss or 0.02)
            result.risk_pct = result.risk / context.account_balance
            result.warnings.append(f"Capped at max position size ({context.max_position_pct*100:.1f}%)")
        
        # Ensure minimum position (if applicable)
        min_size = 0.0001  # Minimum trade size
        if result.size < min_size and result.size > 0:
            result.size = min_size
            result.value = result.size * context.current_price
            result.warnings.append(f"Position size increased to minimum trade size")
        
        return result

    async def _record_sizing_decision(
        self,
        context: SizingContext,
        result: SizingResult
    ) -> None:
        """Record sizing decision for future learning"""
        history = SizingHistory(
            timestamp=datetime.utcnow(),
            symbol=context.symbol,
            method=context.method.value if context.method else "unknown",
            size=result.size,
            risk=result.risk
        )
        
        self._sizing_history.append(history)
        
        # Keep history manageable
        if len(self._sizing_history) > 10000:
            self._sizing_history = self._sizing_history[-1000:]

    def _build_response(
        self,
        request: PositionSizingRequest,
        context: SizingContext,
        result: SizingResult
    ) -> PositionSizingResponse:
        """Build position sizing response"""
        return PositionSizingResponse(
            symbol=request.symbol,
            portfolio_id=request.portfolio_id,
            method=request.method.value,
            timestamp=datetime.utcnow(),
            position_size=round(result.size, 8),
            position_value=round(result.value, 2),
            position_pct=round(result.size_pct * 100, 2),
            risk_amount=round(result.risk, 2),
            risk_pct=round(result.risk_pct * 100, 2),
            stop_loss_price=round(result.stop_loss, 2) if result.stop_loss else None,
            stop_loss_pct=round(((context.current_price - result.stop_loss) / context.current_price * 100), 2) if result.stop_loss else None,
            take_profit_price=round(result.take_profit, 2) if result.take_profit else None,
            take_profit_pct=round(((result.take_profit - context.current_price) / context.current_price * 100), 2) if result.take_profit else None,
            risk_reward_ratio=request.risk_reward_ratio,
            confidence_score=result.confidence,
            max_position_size=round(context.max_position_pct * context.account_balance / context.current_price, 8),
            min_position_size=0.0001,  # Minimum trade size
            adjusted_for_volatility=context.volatility is not None,
            adjusted_for_market_condition=context.market_condition is not None,
            warnings=result.warnings,
            recommendations=result.recommendations
        )

    # -------------------------------------------------------------------------
    # Public API Methods
    # -------------------------------------------------------------------------

    async def get_sizing_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[SizingHistory]:
        """Get position sizing history"""
        history = self._sizing_history
        
        if symbol:
            history = [h for h in history if h.symbol == symbol]
        
        return history[-limit:]

    async def get_sizing_performance(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """Get performance metrics for sizing decisions"""
        try:
            history = [h for h in self._sizing_history if h.symbol == symbol]
            
            if not history:
                return {'status': 'no_data'}
            
            # Calculate metrics
            total_trades = len(history)
            successful = sum(1 for h in history if h.outcome is not None and h.outcome > 0)
            avg_risk = np.mean([h.risk for h in history])
            avg_size = np.mean([h.size for h in history])
            
            return {
                'symbol': symbol,
                'total_decisions': total_trades,
                'success_rate': successful / total_trades if total_trades > 0 else 0,
                'avg_risk_per_trade': avg_risk,
                'avg_position_size': avg_size,
                'current_risk': history[-1].risk if history else 0,
                'trend': 'increasing' if successful / total_trades > 0.5 else 'decreasing'
            }
            
        except Exception as e:
            logger.error(f"Error getting sizing performance: {e}")
            return {'status': 'error', 'message': str(e)}

    async def reset_history(self, symbol: Optional[str] = None) -> bool:
        """Reset sizing history"""
        try:
            if symbol:
                self._sizing_history = [h for h in self._sizing_history 
                                      if h.symbol != symbol]
            else:
                self._sizing_history = []
            
            logger.info(f"Sizing history reset for {symbol or 'all'}")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting history: {e}")
            return False

    async def close(self) -> None:
        """Close connections and clean up resources"""
        self._market_data_cache.clear()
        logger.info("PositionSizer closed")


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

from fastapi import APIRouter, Depends, Query, Body

router = APIRouter(prefix="/api/v1/position-sizing", tags=["Position Sizing"])


async def get_sizer() -> PositionSizer:
    """Dependency to get PositionSizer instance"""
    return PositionSizer()


@router.post("/calculate", response_model=PositionSizingResponse)
async def calculate_position_size(
    request: PositionSizingRequest,
    sizer: PositionSizer = Depends(get_sizer)
):
    """Calculate optimal position size"""
    return await sizer.calculate_position_size(request)


@router.get("/history")
async def get_sizing_history(
    symbol: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    sizer: PositionSizer = Depends(get_sizer)
):
    """Get position sizing history"""
    return await sizer.get_sizing_history(symbol, limit)


@router.get("/performance/{symbol}")
async def get_sizing_performance(
    symbol: str,
    sizer: PositionSizer = Depends(get_sizer)
):
    """Get performance metrics for sizing decisions"""
    return await sizer.get_sizing_performance(symbol)


@router.post("/reset-history")
async def reset_sizing_history(
    symbol: Optional[str] = Query(None),
    sizer: PositionSizer = Depends(get_sizer)
):
    """Reset sizing history"""
    success = await sizer.reset_history(symbol)
    return {'success': success}


@router.get("/methods")
async def get_sizing_methods():
    """Get available sizing methods"""
    return {
        'methods': [
            {'name': m.value, 'description': m.name.replace('_', ' ').title()}
            for m in SizingMethod
        ]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'PositionSizer',
    'PositionSizingRequest',
    'PositionSizingResponse',
    'SizingMethod',
    'RiskTolerance',
    'MarketCondition',
    'SizingContext',
    'SizingResult',
    'SizingHistory',
    'router'
]
