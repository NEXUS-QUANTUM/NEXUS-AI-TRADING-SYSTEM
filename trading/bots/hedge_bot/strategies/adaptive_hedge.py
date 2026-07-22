# trading/bots/hedge_bot/strategies/adaptive_hedge.py

"""
NEXUS HEDGE BOT - ADAPTIVE HEDGE STRATEGY
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced adaptive hedging strategy that dynamically adjusts hedge parameters
based on market conditions, volatility regimes, and performance feedback.

Version: 3.0.0
"""

import asyncio
import json
import math
import numpy as np
import pandas as pd
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable

import structlog
from pydantic import BaseModel, Field, validator

from ..core.base_hedge import BaseHedgeStrategy
from ..core.hedge_types import HedgeType, HedgeDirection, HedgeSignal
from ..core.portfolio_manager import PortfolioManager
from ..core.risk_manager import RiskManager
from ..core.market_data import MarketDataProvider

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class AdaptiveMode(str, Enum):
    """Adaptive strategy modes."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    DYNAMIC = "dynamic"
    MACHINE_LEARNING = "machine_learning"


class VolatilityRegime(str, Enum):
    """Volatility regimes."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"
    CRASH = "crash"


class MarketPhase(str, Enum):
    """Market phases."""
    ACCUMULATION = "accumulation"
    MARKUP = "markup"
    DISTRIBUTION = "distribution"
    MARKDOWN = "markdown"
    RANGING = "ranging"
    BREAKOUT = "breakout"


class HedgeEffectiveness(str, Enum):
    """Hedge effectiveness ratings."""
    POOR = "poor"
    FAIR = "fair"
    GOOD = "good"
    EXCELLENT = "excellent"


# === DATA MODELS ===

@dataclass
class AdaptiveParameters:
    """Dynamic hedging parameters."""
    hedge_ratio: float = 0.75
    rebalance_threshold: float = 0.02
    max_position_size: float = 0.10
    min_position_size: float = 0.01
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.10
    trailing_stop_pct: float = 0.03
    delta_hedge_ratio: float = 0.50
    gamma_hedge_ratio: float = 0.30
    vega_hedge_ratio: float = 0.20
    volatility_scaling: float = 1.0
    correlation_threshold: float = 0.70
    beta_threshold: float = 1.20
    confidence_score: float = 0.50
    risk_appetite: float = 0.50
    leverage_factor: float = 1.0
    max_drawdown_limit: float = 0.05
    target_sharpe: float = 1.5
    recovery_factor: float = 0.75
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdaptiveParameters":
        return cls(**data)


@dataclass
class MarketState:
    """Current market state."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    volatility_regime: VolatilityRegime = VolatilityRegime.NORMAL
    market_phase: MarketPhase = MarketPhase.RANGING
    vix_level: float = 20.0
    volatility_30d: float = 0.25
    volatility_60d: float = 0.30
    volatility_90d: float = 0.28
    correlation_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    beta_values: Dict[str, float] = field(default_factory=dict)
    market_trend: float = 0.0
    market_momentum: float = 0.0
    market_strength: float = 0.5
    liquidity_score: float = 0.7
    sentiment_score: float = 0.5
    fear_greed_index: float = 50.0
    risk_reward_ratio: float = 1.5
    expected_volatility: float = 0.25
    realized_volatility: float = 0.22
    skewness: float = 0.0
    kurtosis: float = 3.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "volatility_regime": self.volatility_regime.value,
            "market_phase": self.market_phase.value,
        }


@dataclass
class HedgePerformance:
    """Hedge performance metrics."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_pnl: float = 0.0
    hedge_pnl: float = 0.0
    portfolio_pnl: float = 0.0
    hedge_effectiveness: float = 0.0
    hedge_ratio_actual: float = 0.0
    hedge_ratio_target: float = 0.0
    tracking_error: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_hedge_duration: float = 0.0
    num_hedges: int = 0
    successful_hedges: int = 0
    failed_hedges: int = 0
    avg_hedge_size: float = 0.0
    max_hedge_size: float = 0.0
    min_hedge_size: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
        }


# === ADAPTIVE HEDGE STRATEGY ===

class AdaptiveHedgeStrategy(BaseHedgeStrategy):
    """
    Advanced adaptive hedging strategy with dynamic parameter adjustment
    based on market conditions and performance feedback.
    """
    
    def __init__(
        self,
        name: str = "adaptive_hedge",
        mode: AdaptiveMode = AdaptiveMode.DYNAMIC,
        portfolio_manager: Optional[PortfolioManager] = None,
        risk_manager: Optional[RiskManager] = None,
        market_data: Optional[MarketDataProvider] = None,
        **kwargs
    ):
        """
        Initialize the adaptive hedge strategy.
        
        Args:
            name: Strategy name
            mode: Adaptive mode
            portfolio_manager: Portfolio manager instance
            risk_manager: Risk manager instance
            market_data: Market data provider
            **kwargs: Additional configuration
        """
        super().__init__(name=name, **kwargs)
        
        self.mode = mode
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.market_data = market_data
        
        # Strategy state
        self._lock = threading.RLock()
        self._running = False
        self._closed = False
        
        # Adaptive parameters
        self.parameters = AdaptiveParameters()
        self.base_parameters = AdaptiveParameters()
        
        # Market state
        self.market_state = MarketState()
        self.market_history: List[MarketState] = []
        self.performance_history: List[HedgePerformance] = []
        
        # Learning state
        self._learning_rate = 0.01
        self._momentum = 0.9
        self._gradient_history: Dict[str, List[float]] = {}
        self._performance_score = 0.0
        
        # Signal history
        self._signal_history: List[HedgeSignal] = []
        self._position_history: List[Dict[str, Any]] = []
        
        # Market indicators
        self._indicators: Dict[str, Any] = {}
        self._indicator_history: List[Dict[str, Any]] = []
        
        # Initialize base parameters based on mode
        self._init_parameters()
        
        logger.info(
            "adaptive_hedge_strategy_initialized",
            name=name,
            mode=mode.value,
        )
    
    def _init_parameters(self) -> None:
        """Initialize base parameters based on mode."""
        if self.mode == AdaptiveMode.CONSERVATIVE:
            self.base_parameters = AdaptiveParameters(
                hedge_ratio=0.50,
                rebalance_threshold=0.03,
                max_position_size=0.05,
                min_position_size=0.005,
                stop_loss_pct=0.03,
                take_profit_pct=0.06,
                trailing_stop_pct=0.02,
                delta_hedge_ratio=0.30,
                gamma_hedge_ratio=0.20,
                vega_hedge_ratio=0.10,
                volatility_scaling=0.75,
                correlation_threshold=0.80,
                beta_threshold=1.10,
                confidence_score=0.70,
                risk_appetite=0.30,
                leverage_factor=0.50,
                max_drawdown_limit=0.03,
                target_sharpe=2.0,
                recovery_factor=0.50,
            )
        elif self.mode == AdaptiveMode.AGGRESSIVE:
            self.base_parameters = AdaptiveParameters(
                hedge_ratio=1.20,
                rebalance_threshold=0.01,
                max_position_size=0.15,
                min_position_size=0.02,
                stop_loss_pct=0.08,
                take_profit_pct=0.20,
                trailing_stop_pct=0.05,
                delta_hedge_ratio=0.70,
                gamma_hedge_ratio=0.50,
                vega_hedge_ratio=0.40,
                volatility_scaling=1.50,
                correlation_threshold=0.60,
                beta_threshold=1.50,
                confidence_score=0.30,
                risk_appetite=0.70,
                leverage_factor=1.50,
                max_drawdown_limit=0.10,
                target_sharpe=1.0,
                recovery_factor=1.00,
            )
        elif self.mode == AdaptiveMode.MODERATE:
            self.base_parameters = AdaptiveParameters(
                hedge_ratio=0.75,
                rebalance_threshold=0.02,
                max_position_size=0.10,
                min_position_size=0.01,
                stop_loss_pct=0.05,
                take_profit_pct=0.12,
                trailing_stop_pct=0.03,
                delta_hedge_ratio=0.50,
                gamma_hedge_ratio=0.35,
                vega_hedge_ratio=0.25,
                volatility_scaling=1.00,
                correlation_threshold=0.70,
                beta_threshold=1.20,
                confidence_score=0.50,
                risk_appetite=0.50,
                leverage_factor=1.00,
                max_drawdown_limit=0.06,
                target_sharpe=1.5,
                recovery_factor=0.75,
            )
        else:  # DYNAMIC or MACHINE_LEARNING
            self.base_parameters = AdaptiveParameters()
        
        self.parameters = self.base_parameters
    
    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market conditions and generate trading signals.
        
        Args:
            market_data: Current market data
            
        Returns:
            Analysis results
        """
        try:
            # Update market state
            await self._update_market_state(market_data)
            
            # Calculate market indicators
            indicators = await self._calculate_indicators(market_data)
            self._indicators = indicators
            
            # Determine optimal parameters
            parameters = await self._optimize_parameters(market_data, indicators)
            self.parameters = parameters
            
            # Generate hedge signal
            signal = await self._generate_signal(market_data, indicators, parameters)
            
            # Record signal
            self._signal_history.append(signal)
            if len(self._signal_history) > 1000:
                self._signal_history = self._signal_history[-1000:]
            
            # Update performance tracking
            await self._update_performance(signal)
            
            return {
                "signal": signal.to_dict(),
                "parameters": parameters.to_dict(),
                "indicators": indicators,
                "market_state": self.market_state.to_dict(),
                "timestamp": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(
                "adaptive_hedge_analysis_failed",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    async def _update_market_state(self, market_data: Dict[str, Any]) -> None:
        """Update market state based on current data."""
        with self._lock:
            # Volatility regime
            vol_30d = market_data.get("volatility_30d", 0.25)
            vol_60d = market_data.get("volatility_60d", 0.30)
            
            if vol_30d > 0.50:
                regime = VolatilityRegime.EXTREME
            elif vol_30d > 0.35:
                regime = VolatilityRegime.HIGH
            elif vol_30d > 0.20:
                regime = VolatilityRegime.NORMAL
            else:
                regime = VolatilityRegime.LOW
            
            # Market phase
            trend = market_data.get("trend", 0.0)
            momentum = market_data.get("momentum", 0.0)
            volume = market_data.get("volume", 1.0)
            
            if trend > 0.05 and momentum > 0.03:
                phase = MarketPhase.MARKUP
            elif trend > 0.02 and momentum < -0.02:
                phase = MarketPhase.DISTRIBUTION
            elif trend < -0.05 and momentum < -0.03:
                phase = MarketPhase.MARKDOWN
            elif abs(trend) < 0.02 and abs(momentum) < 0.02:
                phase = MarketPhase.RANGING
            else:
                phase = MarketPhase.ACCUMULATION
            
            # Market sentiment
            vix = market_data.get("vix", 20.0)
            fear_greed = market_data.get("fear_greed_index", 50.0)
            
            sentiment_score = 0.5
            if fear_greed > 70:
                sentiment_score = 0.8  # Greed
            elif fear_greed < 30:
                sentiment_score = 0.2  # Fear
            
            # Update state
            self.market_state = MarketState(
                volatility_regime=regime,
                market_phase=phase,
                vix_level=vix,
                volatility_30d=vol_30d,
                volatility_60d=vol_60d,
                volatility_90d=market_data.get("volatility_90d", 0.28),
                correlation_matrix=market_data.get("correlation_matrix", {}),
                beta_values=market_data.get("beta_values", {}),
                market_trend=trend,
                market_momentum=momentum,
                market_strength=market_data.get("strength", 0.5),
                liquidity_score=market_data.get("liquidity", 0.7),
                sentiment_score=sentiment_score,
                fear_greed_index=fear_greed,
                risk_reward_ratio=market_data.get("risk_reward_ratio", 1.5),
                expected_volatility=market_data.get("expected_volatility", 0.25),
                realized_volatility=market_data.get("realized_volatility", 0.22),
                skewness=market_data.get("skewness", 0.0),
                kurtosis=market_data.get("kurtosis", 3.0),
            )
            
            # Store history
            self.market_history.append(self.market_state)
            if len(self.market_history) > 1000:
                self.market_history = self.market_history[-1000:]
    
    async def _calculate_indicators(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate market indicators."""
        indicators = {}
        
        try:
            # Technical indicators
            prices = market_data.get("price_history", [])
            if prices:
                df = pd.DataFrame(prices)
                
                # Moving averages
                if len(df) >= 20:
                    df['sma_20'] = df['close'].rolling(20).mean()
                    df['sma_50'] = df['close'].rolling(50).mean()
                    df['sma_200'] = df['close'].rolling(200).mean()
                    indicators['sma_20'] = df['sma_20'].iloc[-1] if not df['sma_20'].isna().iloc[-1] else 0
                    indicators['sma_50'] = df['sma_50'].iloc[-1] if not df['sma_50'].isna().iloc[-1] else 0
                    indicators['sma_200'] = df['sma_200'].iloc[-1] if not df['sma_200'].isna().iloc[-1] else 0
                    
                    # RSI
                    delta = df['close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rs = gain / loss
                    indicators['rsi'] = 100 - (100 / (1 + rs.iloc[-1])) if not rs.isna().iloc[-1] else 50
                    
                    # MACD
                    exp1 = df['close'].ewm(span=12, adjust=False).mean()
                    exp2 = df['close'].ewm(span=26, adjust=False).mean()
                    macd = exp1 - exp2
                    signal = macd.ewm(span=9, adjust=False).mean()
                    indicators['macd'] = macd.iloc[-1] if not macd.isna().iloc[-1] else 0
                    indicators['macd_signal'] = signal.iloc[-1] if not signal.isna().iloc[-1] else 0
                    
                    # Bollinger Bands
                    sma = df['close'].rolling(20).mean()
                    std = df['close'].rolling(20).std()
                    upper = sma + (std * 2)
                    lower = sma - (std * 2)
                    indicators['bb_upper'] = upper.iloc[-1] if not upper.isna().iloc[-1] else 0
                    indicators['bb_lower'] = lower.iloc[-1] if not lower.isna().iloc[-1] else 0
                    
                    # ATR
                    high_low = df['high'] - df['low']
                    high_close = (df['high'] - df['close'].shift()).abs()
                    low_close = (df['low'] - df['close'].shift()).abs()
                    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
                    indicators['atr'] = tr.rolling(14).mean().iloc[-1] if not tr.isna().iloc[-1] else 0
            
            # Volatility indicators
            indicators['volatility_regime'] = self.market_state.volatility_regime.value
            indicators['volatility_30d'] = self.market_state.volatility_30d
            indicators['vix'] = self.market_state.vix_level
            
            # Trend indicators
            indicators['trend'] = self.market_state.market_trend
            indicators['momentum'] = self.market_state.market_momentum
            indicators['market_phase'] = self.market_state.market_phase.value
            
            # Sentiment indicators
            indicators['sentiment'] = self.market_state.sentiment_score
            indicators['fear_greed'] = self.market_state.fear_greed_index
            
            # Risk indicators
            indicators['risk_reward'] = self.market_state.risk_reward_ratio
            indicators['liquidity'] = self.market_state.liquidity_score
            
            # Store history
            self._indicator_history.append(indicators)
            if len(self._indicator_history) > 1000:
                self._indicator_history = self._indicator_history[-1000:]
            
        except Exception as e:
            logger.error("indicator_calculation_error", error=str(e))
        
        return indicators
    
    async def _optimize_parameters(
        self,
        market_data: Dict[str, Any],
        indicators: Dict[str, Any],
    ) -> AdaptiveParameters:
        """
        Optimize hedging parameters based on current market conditions.
        
        Args:
            market_data: Current market data
            indicators: Market indicators
            
        Returns:
            Optimized parameters
        """
        params = AdaptiveParameters.from_dict(self.base_parameters.to_dict())
        
        try:
            # Volatility adjustment
            vol_regime = self.market_state.volatility_regime
            if vol_regime == VolatilityRegime.LOW:
                params.volatility_scaling = 0.7
                params.hedge_ratio = self.base_parameters.hedge_ratio * 0.8
                params.rebalance_threshold = self.base_parameters.rebalance_threshold * 1.5
            elif vol_regime == VolatilityRegime.HIGH:
                params.volatility_scaling = 1.5
                params.hedge_ratio = self.base_parameters.hedge_ratio * 1.3
                params.rebalance_threshold = self.base_parameters.rebalance_threshold * 0.6
            elif vol_regime == VolatilityRegime.EXTREME:
                params.volatility_scaling = 2.0
                params.hedge_ratio = self.base_parameters.hedge_ratio * 1.5
                params.rebalance_threshold = self.base_parameters.rebalance_threshold * 0.4
                params.stop_loss_pct = self.base_parameters.stop_loss_pct * 1.5
                params.max_position_size = self.base_parameters.max_position_size * 0.5
            
            # Trend adjustment
            trend = self.market_state.market_trend
            if trend > 0.05:
                # Strong uptrend - reduce hedges
                params.hedge_ratio = params.hedge_ratio * 0.7
                params.stop_loss_pct = params.stop_loss_pct * 1.2
            elif trend < -0.05:
                # Strong downtrend - increase hedges
                params.hedge_ratio = params.hedge_ratio * 1.3
                params.stop_loss_pct = params.stop_loss_pct * 0.8
            
            # Sentiment adjustment
            sentiment = self.market_state.sentiment_score
            if sentiment > 0.7:
                # Overbought - increase hedges
                params.hedge_ratio = params.hedge_ratio * 1.2
            elif sentiment < 0.3:
                # Oversold - reduce hedges
                params.hedge_ratio = params.hedge_ratio * 0.8
            
            # Performance feedback
            if self.performance_history:
                recent_perf = self.performance_history[-1]
                if recent_perf.hedge_effectiveness > 0.8:
                    # Good performance - maintain
                    pass
                elif recent_perf.hedge_effectiveness < 0.4:
                    # Poor performance - adjust
                    params.hedge_ratio = params.hedge_ratio * 1.1
                    params.rebalance_threshold = params.rebalance_threshold * 0.9
            
            # Machine learning mode
            if self.mode == AdaptiveMode.MACHINE_LEARNING:
                params = await self._ml_optimize(params, market_data, indicators)
            
            # Clamp values
            params.hedge_ratio = max(0.1, min(2.0, params.hedge_ratio))
            params.rebalance_threshold = max(0.005, min(0.05, params.rebalance_threshold))
            params.max_position_size = max(0.01, min(0.25, params.max_position_size))
            params.min_position_size = max(0.001, min(0.02, params.min_position_size))
            params.stop_loss_pct = max(0.01, min(0.15, params.stop_loss_pct))
            params.take_profit_pct = max(0.02, min(0.30, params.take_profit_pct))
            params.volatility_scaling = max(0.5, min(2.5, params.volatility_scaling))
            params.leverage_factor = max(0.5, min(2.0, params.leverage_factor))
            
        except Exception as e:
            logger.error("parameter_optimization_error", error=str(e))
        
        return params
    
    async def _ml_optimize(
        self,
        params: AdaptiveParameters,
        market_data: Dict[str, Any],
        indicators: Dict[str, Any],
    ) -> AdaptiveParameters:
        """
        Machine learning-based parameter optimization.
        
        Args:
            params: Current parameters
            market_data: Market data
            indicators: Market indicators
            
        Returns:
            Optimized parameters
        """
        try:
            # Simple gradient-based optimization
            features = [
                indicators.get('volatility_30d', 0.25),
                indicators.get('rsi', 50.0),
                indicators.get('trend', 0.0),
                indicators.get('sentiment', 0.5),
                indicators.get('fear_greed', 50.0),
                indicators.get('risk_reward', 1.5),
            ]
            
            # Normalize features
            norm_features = [f / max(1, abs(f)) for f in features]
            
            # Calculate adjustment factors
            vol_factor = 1.0 + (norm_features[0] - 0.25) * 0.5
            trend_factor = 1.0 + (norm_features[2]) * 0.3
            sentiment_factor = 1.0 - (norm_features[3] - 0.5) * 0.4
            
            # Apply adjustments
            params.hedge_ratio *= vol_factor * trend_factor * sentiment_factor
            params.volatility_scaling *= vol_factor
            params.rebalance_threshold /= vol_factor
            
            # Update gradient history
            for key, value in params.to_dict().items():
                if key not in self._gradient_history:
                    self._gradient_history[key] = []
                self._gradient_history[key].append(value)
                if len(self._gradient_history[key]) > 10:
                    self._gradient_history[key] = self._gradient_history[key][-10:]
            
        except Exception as e:
            logger.error("ml_optimization_error", error=str(e))
        
        return params
    
    async def _generate_signal(
        self,
        market_data: Dict[str, Any],
        indicators: Dict[str, Any],
        parameters: AdaptiveParameters,
    ) -> HedgeSignal:
        """
        Generate hedge signal based on analysis.
        
        Args:
            market_data: Current market data
            indicators: Market indicators
            parameters: Optimized parameters
            
        Returns:
            Hedge signal
        """
        try:
            # Determine signal type
            hedge_type = self._determine_hedge_type(indicators)
            direction = self._determine_direction(indicators)
            
            # Calculate confidence
            confidence = self._calculate_confidence(indicators, parameters)
            
            # Calculate size
            size = self._calculate_position_size(parameters, confidence)
            
            # Calculate price levels
            current_price = market_data.get('price', 0)
            entry_price = current_price
            stop_loss = self._calculate_stop_loss(current_price, direction, parameters)
            take_profit = self._calculate_take_profit(current_price, direction, parameters)
            
            # Create signal
            signal = HedgeSignal(
                hedge_type=hedge_type,
                direction=direction,
                size=size,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
                reason=f"Adaptive hedge triggered by {hedge_type.value} condition",
                metadata={
                    'parameters': parameters.to_dict(),
                    'indicators': indicators,
                    'market_state': self.market_state.to_dict(),
                    'mode': self.mode.value,
                }
            )
            
            return signal
            
        except Exception as e:
            logger.error("signal_generation_error", error=str(e))
            return HedgeSignal(
                hedge_type=HedgeType.DELTA,
                direction=HedgeDirection.NONE,
                size=0,
                confidence=0,
                reason=f"Error generating signal: {e}",
            )
    
    def _determine_hedge_type(self, indicators: Dict[str, Any]) -> HedgeType:
        """Determine the appropriate hedge type."""
        volatility = indicators.get('volatility_30d', 0.25)
        trend = indicators.get('trend', 0.0)
        rsi = indicators.get('rsi', 50.0)
        market_phase = indicators.get('market_phase', 'ranging')
        
        if volatility > 0.4:
            return HedgeType.VOLATILITY
        elif abs(trend) > 0.05:
            return HedgeType.DELTA
        elif market_phase in ['distribution', 'markdown']:
            return HedgeType.GAMMA
        elif 30 < rsi < 70:
            return HedgeType.CORRELATION
        else:
            return HedgeType.BETA
    
    def _determine_direction(self, indicators: Dict[str, Any]) -> HedgeDirection:
        """Determine hedge direction."""
        trend = indicators.get('trend', 0.0)
        rsi = indicators.get('rsi', 50.0)
        sentiment = indicators.get('sentiment', 0.5)
        
        if trend > 0.02 and rsi > 50 and sentiment > 0.5:
            return HedgeDirection.LONG
        elif trend < -0.02 and rsi < 50 and sentiment < 0.5:
            return HedgeDirection.SHORT
        else:
            return HedgeDirection.NONE
    
    def _calculate_confidence(
        self,
        indicators: Dict[str, Any],
        parameters: AdaptiveParameters,
    ) -> float:
        """Calculate signal confidence."""
        confidence = 0.5
        
        # Volatility confidence
        vol_regime = self.market_state.volatility_regime
        if vol_regime in [VolatilityRegime.NORMAL, VolatilityRegime.HIGH]:
            confidence += 0.15
        elif vol_regime == VolatilityRegime.EXTREME:
            confidence += 0.05
        else:
            confidence -= 0.10
        
        # Trend confidence
        trend = abs(indicators.get('trend', 0.0))
        if trend > 0.05:
            confidence += 0.15
        elif trend > 0.02:
            confidence += 0.05
        
        # Indicator confidence
        rsi = indicators.get('rsi', 50.0)
        if rsi < 30 or rsi > 70:
            confidence += 0.10
        
        # Market phase confidence
        market_phase = indicators.get('market_phase', 'ranging')
        if market_phase in ['markup', 'markdown']:
            confidence += 0.10
        
        # Performance confidence
        if self.performance_history:
            recent = self.performance_history[-1]
            if recent.hedge_effectiveness > 0.7:
                confidence += 0.10
            elif recent.hedge_effectiveness < 0.3:
                confidence -= 0.10
        
        # Clamp
        confidence = max(0.1, min(0.95, confidence))
        
        return confidence
    
    def _calculate_position_size(
        self,
        parameters: AdaptiveParameters,
        confidence: float,
    ) -> float:
        """Calculate position size based on parameters and confidence."""
        base_size = parameters.max_position_size
        size = base_size * confidence
        
        # Adjust for volatility
        vol_factor = 1.0 / parameters.volatility_scaling
        size *= vol_factor
        
        # Adjust for risk appetite
        size *= parameters.risk_appetite
        
        # Adjust for leverage
        size *= parameters.leverage_factor
        
        # Clamp
        size = max(parameters.min_position_size, min(parameters.max_position_size, size))
        
        return size
    
    def _calculate_stop_loss(
        self,
        price: float,
        direction: HedgeDirection,
        parameters: AdaptiveParameters,
    ) -> Optional[float]:
        """Calculate stop loss price."""
        if direction == HedgeDirection.NONE or price <= 0:
            return None
        
        stop_pct = parameters.stop_loss_pct
        
        if direction == HedgeDirection.LONG:
            return price * (1 - stop_pct)
        else:
            return price * (1 + stop_pct)
    
    def _calculate_take_profit(
        self,
        price: float,
        direction: HedgeDirection,
        parameters: AdaptiveParameters,
    ) -> Optional[float]:
        """Calculate take profit price."""
        if direction == HedgeDirection.NONE or price <= 0:
            return None
        
        profit_pct = parameters.take_profit_pct
        
        if direction == HedgeDirection.LONG:
            return price * (1 + profit_pct)
        else:
            return price * (1 - profit_pct)
    
    async def _update_performance(self, signal: HedgeSignal) -> None:
        """Update performance tracking."""
        try:
            # Calculate performance metrics
            if self.portfolio_manager:
                portfolio_pnl = self.portfolio_manager.get_total_pnl()
                hedge_pnl = self.portfolio_manager.get_hedge_pnl()
                
                performance = HedgePerformance(
                    total_pnl=portfolio_pnl,
                    hedge_pnl=hedge_pnl,
                    portfolio_pnl=portfolio_pnl - hedge_pnl,
                    hedge_effectiveness=self._calculate_effectiveness(),
                    hedge_ratio_actual=self._calculate_actual_ratio(),
                    hedge_ratio_target=self.parameters.hedge_ratio,
                    num_hedges=len(self._signal_history),
                    successful_hedges=sum(1 for s in self._signal_history if s.confidence > 0.5),
                    failed_hedges=sum(1 for s in self._signal_history if s.confidence < 0.3),
                )
                
                self.performance_history.append(performance)
                if len(self.performance_history) > 1000:
                    self.performance_history = self.performance_history[-1000:]
                
                # Update performance score
                if len(self.performance_history) > 10:
                    recent = self.performance_history[-10:]
                    avg_effectiveness = sum(p.hedge_effectiveness for p in recent) / len(recent)
                    self._performance_score = avg_effectiveness
                    
        except Exception as e:
            logger.error("performance_update_error", error=str(e))
    
    def _calculate_effectiveness(self) -> float:
        """Calculate hedge effectiveness."""
        if len(self._signal_history) < 2:
            return 0.5
        
        # Simple effectiveness calculation based on PnL
        try:
            recent_signals = self._signal_history[-10:]
            successful = sum(1 for s in recent_signals if s.confidence > 0.5)
            return successful / len(recent_signals) if recent_signals else 0.5
        except Exception:
            return 0.5
    
    def _calculate_actual_ratio(self) -> float:
        """Calculate actual hedge ratio."""
        if not self.portfolio_manager:
            return 0.5
        
        try:
            total_value = self.portfolio_manager.get_total_value()
            hedge_value = self.portfolio_manager.get_hedge_value()
            return hedge_value / total_value if total_value > 0 else 0
        except Exception:
            return 0.5
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get strategy metrics."""
        return {
            "mode": self.mode.value,
            "parameters": self.parameters.to_dict(),
            "market_state": self.market_state.to_dict(),
            "performance_score": self._performance_score,
            "signal_count": len(self._signal_history),
            "active_signal": self._signal_history[-1].to_dict() if self._signal_history else None,
            "indicators": self._indicators,
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if not self.performance_history:
            return {"status": "no_data"}
        
        latest = self.performance_history[-1]
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_pnl": latest.total_pnl,
            "hedge_pnl": latest.hedge_pnl,
            "portfolio_pnl": latest.portfolio_pnl,
            "hedge_effectiveness": latest.hedge_effectiveness,
            "hedge_ratio_actual": latest.hedge_ratio_actual,
            "hedge_ratio_target": latest.hedge_ratio_target,
            "tracking_error": latest.tracking_error,
            "sharpe_ratio": latest.sharpe_ratio,
            "sortino_ratio": latest.sortino_ratio,
            "max_drawdown": latest.max_drawdown,
            "win_rate": latest.win_rate,
            "num_hedges": latest.num_hedges,
            "performance_score": self._performance_score,
        }
    
    def start(self) -> None:
        """Start the strategy."""
        self._running = True
        logger.info("adaptive_hedge_strategy_started")
    
    def stop(self) -> None:
        """Stop the strategy."""
        self._running = False
        logger.info("adaptive_hedge_strategy_stopped")
    
    def close(self) -> None:
        """Close the strategy."""
        self._closed = True
        self._running = False
        logger.info("adaptive_hedge_strategy_closed")


# === MODULE EXPORTS ===

__all__ = [
    "AdaptiveHedgeStrategy",
    "AdaptiveMode",
    "VolatilityRegime",
    "MarketPhase",
    "AdaptiveParameters",
    "MarketState",
    "HedgePerformance",
]

logger.info("adaptive_hedge_module_loaded", version="3.0.0")
