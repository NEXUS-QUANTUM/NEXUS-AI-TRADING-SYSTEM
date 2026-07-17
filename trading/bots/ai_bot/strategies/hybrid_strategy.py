# trading/bots/ai_bot/strategies/hybrid_strategy.py
# NEXUS AI TRADING SYSTEM - Hybrid Trading Strategy
# Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved.

"""
Hybrid Trading Strategy for NEXUS AI Trading Bot.
Combines multiple strategies and AI models for superior performance including:
- Multiple strategy fusion (trend, momentum, mean reversion, breakout)
- AI model ensemble (LSTM, Transformer, XGBoost)
- Dynamic strategy weighting
- Market regime detection
- Adaptive parameter optimization
- Risk-aware position sizing
- Multi-timeframe analysis
- Feature engineering and selection
"""

import asyncio
import logging
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler

# NEXUS Imports
from trading.bots.ai_bot.strategies.base_strategy import BaseStrategy, StrategyConfig, SignalType, SignalStrength
from trading.bots.ai_bot.strategies.breakout_strategy import BreakoutStrategy, BreakoutConfig
from trading.bots.ai_bot.strategies.momentum_strategy import MomentumStrategy, MomentumConfig
from trading.bots.ai_bot.strategies.mean_reversion_strategy import MeanReversionStrategy, MeanReversionConfig
from trading.bots.ai_bot.strategies.trend_following_strategy import TrendFollowingStrategy, TrendFollowingConfig
from trading.bots.ai_bot.strategies.risk_management import RiskManager
from trading.bots.ai_bot.execution.order_manager import OrderManager
from shared.utilities.logger import get_logger

logger = get_logger("nexus.trading.strategy.hybrid")


# ============================================================================
# Enums & Constants
# ============================================================================

class MarketRegime(str, Enum):
    """Market regime types."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    CHOPPY = "choppy"
    BREAKOUT = "breakout"
    REVERSAL = "reversal"
    UNKNOWN = "unknown"


class WeightingMethod(str, Enum):
    """Weighting methods for ensemble."""
    UNIFORM = "uniform"
    PERFORMANCE = "performance"
    DYNAMIC = "dynamic"
    REGIME = "regime"
    OPTIMIZED = "optimized"


@dataclass
class HybridConfig(StrategyConfig):
    """Hybrid strategy configuration."""
    # Sub-strategies
    enable_trend_following: bool = True
    enable_momentum: bool = True
    enable_mean_reversion: bool = True
    enable_breakout: bool = True
    enable_ai_models: bool = True

    # Ensemble configuration
    weighting_method: WeightingMethod = WeightingMethod.PERFORMANCE
    min_confidence_threshold: float = 0.6
    consensus_threshold: float = 0.6
    max_strategies: int = 3

    # Market regime detection
    enable_regime_detection: bool = True
    regime_lookback_periods: int = 100
    regime_update_frequency: int = 10

    # AI Models
    ai_model_paths: Dict[str, str] = field(default_factory=dict)
    ai_models: List[str] = field(default_factory=lambda: ["lstm", "transformer", "xgboost"])
    ai_weight: float = 0.3

    # Optimization
    enable_adaptive_weights: bool = True
    weight_update_frequency: int = 50
    performance_lookback: int = 100
    reoptimization_frequency: int = 200

    # Risk
    max_strategy_risk: float = 0.02
    correlation_penalty: float = 0.3
    volatility_adjustment: bool = True


@dataclass
class StrategyWeight:
    """Strategy weight data."""
    strategy_name: str
    weight: float
    performance_score: float
    confidence: float
    last_updated: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnsembleSignal:
    """Ensemble signal data."""
    signals: List[Signal]
    consensus_type: SignalType
    consensus_strength: SignalStrength
    weighted_confidence: float
    strategy_weights: Dict[str, float]
    regime: MarketRegime
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Hybrid Strategy
# ============================================================================

class HybridStrategy(BaseStrategy):
    """
    Advanced Hybrid Trading Strategy.
    Combines multiple strategies and AI models for superior performance.
    """

    def __init__(
        self,
        config: HybridConfig,
        risk_manager: RiskManager,
        order_manager: OrderManager,
        market_data_provider: Any,
        ai_models: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize hybrid strategy.

        Args:
            config: Strategy configuration
            risk_manager: Risk management instance
            order_manager: Order management instance
            market_data_provider: Market data provider
            ai_models: AI models for predictions
        """
        super().__init__(config, risk_manager, order_manager)

        self.config = config
        self.market_data = market_data_provider
        self.ai_models = ai_models or {}

        # Sub-strategies
        self._strategies: Dict[str, BaseStrategy] = {}
        self._strategy_weights: Dict[str, StrategyWeight] = {}
        self._strategy_performance: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Ensemble data
        self._ensemble_signals: List[EnsembleSignal] = []
        self._signal_history: List[Signal] = []

        # Market regime detection
        self._current_regime: MarketRegime = MarketRegime.UNKNOWN
        self._regime_history: List[MarketRegime] = []
        self._regime_features: Dict[str, Any] = {}

        # Feature data
        self._feature_cache: Dict[str, np.ndarray] = {}
        self._feature_importance: Dict[str, float] = {}

        # Performance metrics
        self._performance = {
            "ensemble_signals": 0,
            "executed_signals": 0,
            "failed_signals": 0,
            "regime_changes": 0,
            "strategy_contributions": defaultdict(lambda: {
                "signals": 0,
                "executed": 0,
                "profit": 0.0,
                "win_rate": 0.0,
            }),
            "by_regime": defaultdict(lambda: {
                "signals": 0,
                "executed": 0,
                "profit": 0.0,
            }),
        }

        # Lock for thread safety
        self._lock = asyncio.Lock()

        # Initialize sub-strategies
        self._initialize_strategies()

        logger.info(
            "HybridStrategy initialized",
            extra={
                "strategies": list(self._strategies.keys()),
                "ai_models": list(self.ai_models.keys()),
                "weighting": self.config.weighting_method.value,
            }
        )

    # ========================================================================
    # Strategy Initialization
    # ========================================================================

    def _initialize_strategies(self) -> None:
        """Initialize sub-strategies."""
        try:
            # Trend Following Strategy
            if self.config.enable_trend_following:
                trend_config = TrendFollowingConfig(
                    name=f"{self.config.name}_trend",
                    type=StrategyType.TRENDING,
                    symbols=self.config.symbols,
                    timeframe=self.config.timeframe,
                    initial_capital=self.config.initial_capital,
                    max_position_size=self.config.max_position_size,
                    max_positions=self.config.max_positions,
                    min_confidence=self.config.min_confidence,
                    risk_per_trade=self.config.risk_per_trade,
                    max_drawdown=self.config.max_drawdown,
                )
                self._strategies["trend"] = TrendFollowingStrategy(
                    config=trend_config,
                    risk_manager=self.risk_manager,
                    order_manager=self.order_manager,
                    market_data_provider=self.market_data,
                )

            # Momentum Strategy
            if self.config.enable_momentum:
                momentum_config = MomentumConfig(
                    name=f"{self.config.name}_momentum",
                    type=StrategyType.MOMENTUM,
                    symbols=self.config.symbols,
                    timeframe=self.config.timeframe,
                    initial_capital=self.config.initial_capital,
                    max_position_size=self.config.max_position_size,
                    max_positions=self.config.max_positions,
                    min_confidence=self.config.min_confidence,
                    risk_per_trade=self.config.risk_per_trade,
                    max_drawdown=self.config.max_drawdown,
                )
                self._strategies["momentum"] = MomentumStrategy(
                    config=momentum_config,
                    risk_manager=self.risk_manager,
                    order_manager=self.order_manager,
                    market_data_provider=self.market_data,
                )

            # Mean Reversion Strategy
            if self.config.enable_mean_reversion:
                meanrev_config = MeanReversionConfig(
                    name=f"{self.config.name}_meanrev",
                    type=StrategyType.MEAN_REVERSION,
                    symbols=self.config.symbols,
                    timeframe=self.config.timeframe,
                    initial_capital=self.config.initial_capital,
                    max_position_size=self.config.max_position_size,
                    max_positions=self.config.max_positions,
                    min_confidence=self.config.min_confidence,
                    risk_per_trade=self.config.risk_per_trade,
                    max_drawdown=self.config.max_drawdown,
                )
                self._strategies["mean_reversion"] = MeanReversionStrategy(
                    config=meanrev_config,
                    risk_manager=self.risk_manager,
                    order_manager=self.order_manager,
                    market_data_provider=self.market_data,
                )

            # Breakout Strategy
            if self.config.enable_breakout:
                breakout_config = BreakoutConfig(
                    name=f"{self.config.name}_breakout",
                    type=StrategyType.SCALPING,
                    symbols=self.config.symbols,
                    timeframe=self.config.timeframe,
                    initial_capital=self.config.initial_capital,
                    max_position_size=self.config.max_position_size,
                    max_positions=self.config.max_positions,
                    min_confidence=self.config.min_confidence,
                    risk_per_trade=self.config.risk_per_trade,
                    max_drawdown=self.config.max_drawdown,
                )
                self._strategies["breakout"] = BreakoutStrategy(
                    config=breakout_config,
                    risk_manager=self.risk_manager,
                    order_manager=self.order_manager,
                    market_data_provider=self.market_data,
                )

            # Initialize weights
            for name in self._strategies:
                self._strategy_weights[name] = StrategyWeight(
                    strategy_name=name,
                    weight=1.0 / len(self._strategies),
                    performance_score=0.5,
                    confidence=0.5,
                    last_updated=datetime.utcnow(),
                )

            logger.info(f"Initialized {len(self._strategies)} sub-strategies")

        except Exception as e:
            logger.error(f"Error initializing strategies: {e}")
            raise

    # ========================================================================
    # Main Strategy Methods
    # ========================================================================

    async def analyze(self) -> Dict[str, Any]:
        """
        Analyze market data using ensemble of strategies.

        Returns:
            Analysis results with ensemble signals
        """
        try:
            # Detect market regime
            if self.config.enable_regime_detection:
                regime = await self._detect_regime()
                if regime != self._current_regime:
                    self._current_regime = regime
                    self._performance["regime_changes"] += 1
                    logger.info(f"Regime changed to: {regime.value}")

            # Update strategy weights
            if self.config.enable_adaptive_weights:
                await self._update_weights()

            # Get signals from all strategies
            strategy_signals = await self._collect_strategy_signals()

            # Get AI model predictions
            ai_signals = await self._get_ai_predictions()

            # Ensemble signals
            ensemble = await self._ensemble_signals(strategy_signals, ai_signals)

            # Generate final signals
            final_signals = await self._generate_final_signals(ensemble)

            return {
                "signals": final_signals,
                "ensemble": ensemble,
                "regime": self._current_regime.value,
                "weights": {
                    name: w.weight for name, w in self._strategy_weights.items()
                },
                "strategy_signals": len(strategy_signals),
                "ai_signals": len(ai_signals),
            }

        except Exception as e:
            logger.error(f"Error in hybrid analysis: {e}")
            return {"signals": [], "error": str(e)}

    async def execute(self, signal: Signal) -> Dict[str, Any]:
        """
        Execute a signal from the ensemble.

        Args:
            signal: Trading signal

        Returns:
            Execution results
        """
        try:
            # Validate signal
            if not await self._validate_ensemble_signal(signal):
                return {"success": False, "error": "Signal validation failed"}

            # Execute order
            result = await self.order_manager.place_order(
                symbol=signal.symbol,
                side="buy" if signal.type in [SignalType.BUY, SignalType.STRONG_BUY] else "sell",
                quantity=signal.quantity,
                order_type="limit",
                price=signal.price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
            )

            if result.get("success"):
                self._performance["executed_signals"] += 1

                # Update strategy contributions
                if signal.metadata and "strategy" in signal.metadata:
                    strategy = signal.metadata["strategy"]
                    self._performance["strategy_contributions"][strategy]["executed"] += 1
                    if result.get("pnl", 0) > 0:
                        self._performance["strategy_contributions"][strategy]["profit"] += result["pnl"]

                return result

            self._performance["failed_signals"] += 1
            return result

        except Exception as e:
            logger.error(f"Error executing ensemble signal: {e}")
            return {"success": False, "error": str(e)}

    # ========================================================================
    # Strategy Signal Collection
    # ========================================================================

    async def _collect_strategy_signals(self) -> Dict[str, List[Signal]]:
        """
        Collect signals from all sub-strategies.

        Returns:
            Dictionary of strategy -> signals
        """
        signals = {}

        for name, strategy in self._strategies.items():
            try:
                result = await strategy.analyze()
                strategy_signals = result.get("signals", [])

                if strategy_signals:
                    # Add strategy metadata
                    for signal in strategy_signals:
                        signal.metadata["strategy"] = name

                    signals[name] = strategy_signals
                    self._performance["strategy_contributions"][name]["signals"] += len(strategy_signals)

            except Exception as e:
                logger.error(f"Error collecting signals from {name}: {e}")

        return signals

    # ========================================================================
    # AI Model Integration
    # ========================================================================

    async def _get_ai_predictions(self) -> List[Signal]:
        """
        Get predictions from AI models.

        Returns:
            List of AI signals
        """
        if not self.config.enable_ai_models or not self.ai_models:
            return []

        ai_signals = []

        try:
            # Get features for all symbols
            for symbol in self.config.symbols:
                features = await self._extract_features(symbol)

                if features is None:
                    continue

                # Get predictions from each AI model
                predictions = {}

                for name, model in self.ai_models.items():
                    try:
                        pred = model.predict(features)
                        predictions[name] = pred
                    except Exception as e:
                        logger.error(f"Error in AI model {name}: {e}")

                if not predictions:
                    continue

                # Aggregate AI predictions
                aggregated = await self._aggregate_ai_predictions(predictions, symbol)

                if aggregated:
                    ai_signals.append(aggregated)

            return ai_signals

        except Exception as e:
            logger.error(f"Error getting AI predictions: {e}")
            return []

    async def _extract_features(self, symbol: str) -> Optional[np.ndarray]:
        """
        Extract features for AI models.

        Args:
            symbol: Trading symbol

        Returns:
            Feature array or None
        """
        try:
            # Get market data
            data = await self._get_market_data(symbol)

            if data is None or len(data) < 100:
                return None

            # Technical indicators
            close = data['close'].values
            high = data['high'].values
            low = data['low'].values
            volume = data['volume'].values

            features = []

            # Price features
            features.append(close[-1])
            features.append(close[-1] / close[-20] - 1)
            features.append(close[-1] / close[-50] - 1)

            # Volatility features
            returns = np.diff(np.log(close))
            features.append(np.std(returns[-20:]))
            features.append(np.std(returns[-50:]))

            # Volume features
            features.append(volume[-1] / np.mean(volume[-20:]))
            features.append(volume[-1] / np.mean(volume[-50:]))

            # RSI
            rsi = talib.RSI(close, timeperiod=14)
            features.append(rsi[-1] if rsi[-1] is not None else 50)

            # MACD
            macd, signal, hist = talib.MACD(close)
            features.append(macd[-1] if macd[-1] is not None else 0)
            features.append(hist[-1] if hist[-1] is not None else 0)

            # Bollinger Bands
            upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
            bb_width = (upper[-1] - lower[-1]) / middle[-1] if upper[-1] is not None else 0
            features.append(bb_width)

            # ATR
            atr = talib.ATR(high, low, close, timeperiod=14)
            features.append(atr[-1] / close[-1] if atr[-1] is not None else 0)

            return np.array(features).reshape(1, -1)

        except Exception as e:
            logger.error(f"Error extracting features for {symbol}: {e}")
            return None

    async def _aggregate_ai_predictions(
        self,
        predictions: Dict[str, Any],
        symbol: str,
    ) -> Optional[Signal]:
        """
        Aggregate AI model predictions.

        Args:
            predictions: Predictions from models
            symbol: Trading symbol

        Returns:
            Aggregated Signal or None
        """
        try:
            # Average predictions
            buy_probs = []
            sell_probs = []

            for name, pred in predictions.items():
                if isinstance(pred, dict):
                    buy_probs.append(pred.get('buy', 0))
                    sell_probs.append(pred.get('sell', 0))
                elif isinstance(pred, float):
                    if pred > 0.5:
                        buy_probs.append(pred)
                    else:
                        sell_probs.append(1 - pred)

            if not buy_probs and not sell_probs:
                return None

            avg_buy = np.mean(buy_probs) if buy_probs else 0
            avg_sell = np.mean(sell_probs) if sell_probs else 0

            confidence = max(avg_buy, avg_sell)

            if confidence < self.config.min_confidence_threshold:
                return None

            # Determine signal type
            if avg_buy > avg_sell:
                signal_type = SignalType.BUY
            else:
                signal_type = SignalType.SELL

            # Get current price
            ticker = await self.market_data.get_ticker(symbol)
            price = ticker.get('last', 0)

            if price <= 0:
                return None

            return Signal(
                symbol=symbol,
                type=signal_type,
                strength=SignalStrength.STRONG if confidence > 0.8 else SignalStrength.MODERATE,
                confidence=confidence,
                price=price,
                quantity=self._calculate_position_size(price),
                reason="AI ensemble prediction",
                timestamp=datetime.utcnow(),
                metadata={
                    "strategy": "ai_ensemble",
                    "predictions": predictions,
                    "avg_buy": avg_buy,
                    "avg_sell": avg_sell,
                    "models": len(predictions),
                },
            )

        except Exception as e:
            logger.error(f"Error aggregating AI predictions: {e}")
            return None

    # ========================================================================
    # Signal Ensemble
    # ========================================================================

    async def _ensemble_signals(
        self,
        strategy_signals: Dict[str, List[Signal]],
        ai_signals: List[Signal],
    ) -> Optional[EnsembleSignal]:
        """
        Ensemble signals from strategies and AI.

        Args:
            strategy_signals: Signals from strategies
            ai_signals: Signals from AI models

        Returns:
            EnsembleSignal or None
        """
        # Collect all signals
        all_signals = []

        for strategy, signals in strategy_signals.items():
            for signal in signals[:1]:  # Take best signal per strategy
                all_signals.append(signal)

        all_signals.extend(ai_signals)

        if not all_signals:
            return None

        # Group signals by type
        signal_counts = defaultdict(int)
        signal_weights = defaultdict(float)
        signal_confidences = defaultdict(float)

        for signal in all_signals:
            signal_type = signal.type
            if signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
                key = "buy"
            elif signal_type in [SignalType.SELL, SignalType.STRONG_SELL]:
                key = "sell"
            else:
                key = "hold"

            signal_counts[key] += 1

            # Weighted confidence
            weight = self._strategy_weights.get(
                signal.metadata.get("strategy", ""),
                StrategyWeight("default", 0.5, 0.5, 0.5, datetime.utcnow())
            ).weight

            signal_weights[key] += weight
            signal_confidences[key] += signal.confidence * weight

        # Determine consensus
        total_weights = sum(signal_weights.values())
        if total_weights == 0:
            return None

        buy_ratio = signal_weights.get("buy", 0) / total_weights
        sell_ratio = signal_weights.get("sell", 0) / total_weights

        if buy_ratio > self.config.consensus_threshold and buy_ratio > sell_ratio:
            consensus_type = SignalType.BUY
            confidence = signal_confidences.get("buy", 0) / max(signal_weights.get("buy", 1), 0.001)
        elif sell_ratio > self.config.consensus_threshold:
            consensus_type = SignalType.SELL
            confidence = signal_confidences.get("sell", 0) / max(signal_weights.get("sell", 1), 0.001)
        else:
            consensus_type = SignalType.HOLD
            confidence = 0.0

        if confidence < self.config.min_confidence_threshold:
            return None

        # Determine strength
        if confidence > 0.8:
            strength = SignalStrength.STRONG
        elif confidence > 0.7:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK

        # Create ensemble signal
        ensemble = EnsembleSignal(
            signals=all_signals,
            consensus_type=consensus_type,
            consensus_strength=strength,
            weighted_confidence=confidence,
            strategy_weights={k: v.weight for k, v in self._strategy_weights.items()},
            regime=self._current_regime,
            timestamp=datetime.utcnow(),
            metadata={
                "buy_ratio": buy_ratio,
                "sell_ratio": sell_ratio,
                "total_signals": len(all_signals),
                "strategy_count": len(strategy_signals),
                "ai_count": len(ai_signals),
            },
        )

        self._ensemble_signals.append(ensemble)
        self._performance["ensemble_signals"] += 1

        return ensemble

    async def _generate_final_signals(
        self,
        ensemble: Optional[EnsembleSignal],
    ) -> List[Signal]:
        """
        Generate final trading signals from ensemble.

        Args:
            ensemble: Ensemble signal

        Returns:
            List of final signals
        """
        if not ensemble or ensemble.consensus_type == SignalType.HOLD:
            return []

        # Get symbol from ensemble signals
        symbols = set()
        for signal in ensemble.signals:
            symbols.add(signal.symbol)

        final_signals = []

        for symbol in symbols:
            # Get price data
            ticker = await self.market_data.get_ticker(symbol)
            price = ticker.get('last', 0)

            if price <= 0:
                continue

            # Calculate position size with risk adjustment
            position_size = await self._calculate_risk_adjusted_size(
                symbol,
                price,
                ensemble.weighted_confidence,
            )

            # Create signal
            signal = Signal(
                symbol=symbol,
                type=ensemble.consensus_type,
                strength=ensemble.consensus_strength,
                confidence=ensemble.weighted_confidence,
                price=price,
                quantity=position_size,
                stop_loss=price * (1 - self.config.stop_loss_percent),
                take_profit=price * (1 + self.config.take_profit_percent),
                reason=f"Ensemble signal from {len(ensemble.signals)} strategies",
                timestamp=datetime.utcnow(),
                metadata={
                    "ensemble": ensemble.metadata,
                    "regime": self._current_regime.value,
                    "strategy_weights": ensemble.strategy_weights,
                    "consensus_type": ensemble.consensus_type.value,
                    "consensus_strength": ensemble.consensus_strength.value,
                },
            )

            final_signals.append(signal)

        return final_signals

    # ========================================================================
    # Market Regime Detection
    # ========================================================================

    async def _detect_regime(self) -> MarketRegime:
        """
        Detect current market regime.

        Returns:
            MarketRegime
        """
        try:
            # Get data for all symbols
            all_data = {}
            for symbol in self.config.symbols:
                data = await self._get_market_data(symbol)
                if data is not None:
                    all_data[symbol] = data

            if not all_data:
                return MarketRegime.UNKNOWN

            # Analyze regime based on aggregate data
            features = await self._extract_regime_features(all_data)

            # Determine regime
            # Trending up/down
            trend_score = features.get('trend_score', 0)
            volatility = features.get('volatility', 0)
            range_width = features.get('range_width', 0)
            volume_trend = features.get('volume_trend', 0)

            if abs(trend_score) > 0.3 and volatility < 0.02:
                if trend_score > 0:
                    return MarketRegime.TRENDING_UP
                else:
                    return MarketRegime.TRENDING_DOWN

            if volatility > 0.03:
                if range_width > 0.02:
                    return MarketRegime.BREAKOUT
                else:
                    return MarketRegime.VOLATILE

            if range_width < 0.01 and volatility < 0.015:
                return MarketRegime.RANGING

            if volume_trend > 1.2 and abs(trend_score) < 0.2:
                return MarketRegime.CHOPPY

            return MarketRegime.UNKNOWN

        except Exception as e:
            logger.error(f"Error detecting regime: {e}")
            return MarketRegime.UNKNOWN

    async def _extract_regime_features(self, all_data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """
        Extract regime features.

        Args:
            all_data: Market data for all symbols

        Returns:
            Regime features
        """
        features = {}

        try:
            # Aggregate across symbols
            trend_scores = []
            volatilities = []
            range_widths = []
            volume_trends = []

            for symbol, data in all_data.items():
                close = data['close'].values

                if len(close) < 50:
                    continue

                # Trend score (slope of linear regression)
                x = np.arange(len(close))
                slope, _ = np.polyfit(x, close, 1)
                trend_score = slope / close[-1]
                trend_scores.append(trend_score)

                # Volatility
                returns = np.diff(np.log(close))
                volatility = np.std(returns) * np.sqrt(252)
                volatilities.append(volatility)

                # Range width
                high = data['high'].values
                low = data['low'].values
                range_width = np.mean(high[-20:] - low[-20:]) / close[-1]
                range_widths.append(range_width)

                # Volume trend
                volume = data['volume'].values
                volume_trend = np.mean(volume[-10:]) / np.mean(volume[-50:])
                volume_trends.append(volume_trend)

            features['trend_score'] = np.mean(trend_scores) if trend_scores else 0
            features['volatility'] = np.mean(volatilities) if volatilities else 0
            features['range_width'] = np.mean(range_widths) if range_widths else 0
            features['volume_trend'] = np.mean(volume_trends) if volume_trends else 0

        except Exception as e:
            logger.error(f"Error extracting regime features: {e}")

        return features

    # ========================================================================
    # Weight Management
    # ========================================================================

    async def _update_weights(self) -> None:
        """
        Update strategy weights based on performance.
        """
        try:
            # Count signals since last update
            total_signals = 0
            strategy_performance = {}

            for name, strategy in self._strategies.items():
                metrics = strategy.get_metrics()
                win_rate = metrics.win_rate if metrics else 0.5
                total_pnl = metrics.total_pnl if metrics else 0

                strategy_performance[name] = {
                    'win_rate': win_rate,
                    'pnl': total_pnl,
                    'signals': metrics.total_trades if metrics else 0,
                }

                total_signals += strategy_performance[name]['signals']

            if total_signals < self.config.weight_update_frequency:
                return

            # Calculate performance scores
            scores = {}
            for name, perf in strategy_performance.items():
                score = (perf['win_rate'] * 0.6 + (perf['pnl'] > 0) * 0.4)
                scores[name] = score

            # Update weights
            total_score = sum(scores.values()) if scores else 1

            for name in self._strategy_weights:
                if total_score > 0:
                    weight = scores.get(name, 0.5) / total_score
                else:
                    weight = 1.0 / len(self._strategies)

                # Apply correlation penalty
                weight *= (1 - self.config.correlation_penalty * 0.1)

                # Clamp weights
                weight = max(0.05, min(0.5, weight))

                self._strategy_weights[name].weight = weight
                self._strategy_weights[name].performance_score = scores.get(name, 0.5)
                self._strategy_weights[name].last_updated = datetime.utcnow()

            # Normalize weights
            total_weight = sum(w.weight for w in self._strategy_weights.values())
            if total_weight > 0:
                for w in self._strategy_weights.values():
                    w.weight /= total_weight

        except Exception as e:
            logger.error(f"Error updating weights: {e}")

    # ========================================================================
    # Risk Management
    # ========================================================================

    async def _calculate_risk_adjusted_size(
        self,
        symbol: str,
        price: float,
        confidence: float,
    ) -> float:
        """
        Calculate risk-adjusted position size.

        Args:
            symbol: Trading symbol
            price: Entry price
            confidence: Signal confidence

        Returns:
            Position size
        """
        # Base position size
        base_size = self._calculate_position_size(price)

        # Adjust for confidence
        confidence_adj = 0.5 + confidence * 0.5

        # Adjust for market regime
        regime_adj = self._get_regime_adjustment()

        # Adjust for volatility
        vol_adj = await self._get_volatility_adjustment(symbol)

        # Adjust for current risk
        risk_adj = await self._get_risk_adjustment()

        # Calculate final size
        final_size = base_size * confidence_adj * regime_adj * vol_adj * risk_adj

        # Apply limits
        min_size = self.config.min_position_size if hasattr(self.config, 'min_position_size') else 0.01
        max_size = self.config.max_position_size

        return max(min_size, min(final_size, max_size))

    def _get_regime_adjustment(self) -> float:
        """
        Get regime-based position adjustment.

        Returns:
            Adjustment factor
        """
        adjustments = {
            MarketRegime.TRENDING_UP: 1.2,
            MarketRegime.TRENDING_DOWN: 0.8,
            MarketRegime.RANGING: 0.7,
            MarketRegime.VOLATILE: 0.5,
            MarketRegime.CHOPPY: 0.6,
            MarketRegime.BREAKOUT: 1.3,
            MarketRegime.REVERSAL: 0.9,
            MarketRegime.UNKNOWN: 1.0,
        }
        return adjustments.get(self._current_regime, 1.0)

    async def _get_volatility_adjustment(self, symbol: str) -> float:
        """
        Get volatility-based position adjustment.

        Args:
            symbol: Trading symbol

        Returns:
            Adjustment factor
        """
        if not self.config.volatility_adjustment:
            return 1.0

        try:
            data = await self._get_market_data(symbol)
            if data is None:
                return 1.0

            close = data['close'].values
            returns = np.diff(np.log(close))
            current_vol = np.std(returns[-20:]) * np.sqrt(252)
            avg_vol = np.std(returns) * np.sqrt(252)

            if avg_vol > 0:
                vol_ratio = current_vol / avg_vol
                return 1.0 / (1 + 0.5 * (vol_ratio - 1))

            return 1.0

        except Exception:
            return 1.0

    async def _get_risk_adjustment(self) -> float:
        """
        Get risk-based position adjustment.

        Returns:
            Adjustment factor
        """
        try:
            # Get current risk metrics
            total_risk = await self.risk_manager.get_total_risk()
            max_risk = self.config.max_drawdown

            if max_risk > 0:
                risk_ratio = total_risk / max_risk
                if risk_ratio > 1.0:
                    return max(0.1, 1.0 / risk_ratio)

            return 1.0

        except Exception:
            return 1.0

    # ========================================================================
    # Utility Methods
    # ========================================================================

    async def _validate_ensemble_signal(self, signal: Signal) -> bool:
        """
        Validate ensemble signal.

        Args:
            signal: Signal to validate

        Returns:
            True if valid
        """
        # Check confidence
        if signal.confidence < self.config.min_confidence_threshold:
            return False

        # Check risk limits
        if not await self.risk_manager.check_order_limits(
            symbol=signal.symbol,
            side="buy" if signal.type in [SignalType.BUY, SignalType.STRONG_BUY] else "sell",
            quantity=signal.quantity,
            price=signal.price,
        ):
            return False

        return True

    async def _get_market_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Get market data for symbol.

        Args:
            symbol: Trading symbol

        Returns:
            DataFrame with price data
        """
        try:
            return await self.market_data.get_historical_data(
                symbol=symbol,
                timeframe=self.config.timeframe,
                limit=self.config.lookback_periods or 200,
            )
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}")
            return None

    def _calculate_position_size(self, price: float) -> float:
        """
        Calculate position size.

        Args:
            price: Entry price

        Returns:
            Position size
        """
        risk_amount = self.config.initial_capital * self.config.risk_per_trade
        stop_loss_amount = price * self.config.stop_loss_percent

        if stop_loss_amount > 0:
            return risk_amount / stop_loss_amount

        return self.config.max_position_size

    # ========================================================================
    # Performance Management
    # ========================================================================

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics.

        Returns:
            Performance metrics
        """
        return {
            **self._performance,
            "strategy_weights": {
                name: {
                    "weight": w.weight,
                    "performance": w.performance_score,
                    "confidence": w.confidence,
                }
                for name, w in self._strategy_weights.items()
            },
            "current_regime": self._current_regime.value,
            "regime_history": [r.value for r in self._regime_history[-10:]],
            "ensemble_signals_total": len(self._ensemble_signals),
            "strategy_contributions": dict(self._performance["strategy_contributions"]),
            "by_regime": dict(self._performance["by_regime"]),
        }

    # ========================================================================
    # Lifecycle Management
    # ========================================================================

    async def start(self) -> None:
        """Start the strategy and all sub-strategies."""
        if self._running:
            return

        self._running = True

        # Start sub-strategies
        for name, strategy in self._strategies.items():
            try:
                await strategy.start()
                logger.info(f"Started sub-strategy: {name}")
            except Exception as e:
                logger.error(f"Error starting sub-strategy {name}: {e}")

        logger.info("HybridStrategy started")

    async def stop(self) -> None:
        """Stop the strategy and all sub-strategies."""
        self._running = False

        # Stop sub-strategies
        for name, strategy in self._strategies.items():
            try:
                await strategy.stop()
                logger.info(f"Stopped sub-strategy: {name}")
            except Exception as e:
                logger.error(f"Error stopping sub-strategy {name}: {e}")

        # Clean up
        async with self._lock:
            self._ensemble_signals.clear()
            self._signal_history.clear()
            self._regime_history.clear()

        logger.info("HybridStrategy stopped")


# ============================================================================
# Factory Function
# ============================================================================

def create_hybrid_strategy(
    config: HybridConfig,
    risk_manager: RiskManager,
    order_manager: OrderManager,
    market_data_provider: Any,
    ai_models: Optional[Dict[str, Any]] = None,
) -> HybridStrategy:
    """
    Factory function to create a HybridStrategy instance.

    Args:
        config: Strategy configuration
        risk_manager: Risk management instance
        order_manager: Order management instance
        market_data_provider: Market data provider
        ai_models: AI models for predictions

    Returns:
        HybridStrategy instance
    """
    return HybridStrategy(
        config=config,
        risk_manager=risk_manager,
        order_manager=order_manager,
        market_data_provider=market_data_provider,
        ai_models=ai_models,
    )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example of how to use the hybrid strategy
    pass
