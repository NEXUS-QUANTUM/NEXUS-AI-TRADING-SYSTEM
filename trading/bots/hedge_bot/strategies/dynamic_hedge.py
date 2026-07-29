# trading/bots/hedge_bot/strategies/dynamic_hedge.py

"""
NEXUS HEDGE BOT - DYNAMIC HEDGE STRATEGY
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
CEO: Dr X... - Majority Shareholder

Advanced dynamic hedging strategy that continuously adapts to market
conditions using machine learning, regime detection, and real-time
optimization of hedge parameters.

Version: 3.0.0
"""

import asyncio
import json
import math
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable

import numpy as np
import pandas as pd
import structlog
from scipy import stats
from scipy.optimize import minimize
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from pydantic import BaseModel, Field, validator

from ..core.base_hedge import BaseHedgeStrategy
from ..core.hedge_types import HedgeType, HedgeDirection, HedgeSignal
from ..core.portfolio_manager import PortfolioManager
from ..core.risk_manager import RiskManager
from ..core.market_data import MarketDataProvider

# Configure structlog
logger = structlog.get_logger(__name__)


# === ENUMS ===

class DynamicHedgeMode(str, Enum):
    """Dynamic hedge modes."""
    ADAPTIVE = "adaptive"                    # Adaptive to market conditions
    PREDICTIVE = "predictive"                # Predictive using ML models
    REINFORCEMENT = "reinforcement"          # Reinforcement learning
    HYBRID = "hybrid"                        # Hybrid approach
    OPTIMAL = "optimal"                      # Optimal control
    ROBUST = "robust"                        # Robust hedging


class HedgeRegime(str, Enum):
    """Hedge regimes."""
    NORMAL = "normal"                        # Normal market conditions
    VOLATILE = "volatile"                    # High volatility
    TRENDING = "trending"                    # Strong trend
    RANGING = "ranging"                      # Sideways market
    CRISIS = "crisis"                        # Crisis conditions
    RECOVERY = "recovery"                    # Recovery mode


class DynamicLearningMode(str, Enum):
    """Learning modes for dynamic hedging."""
    ONLINE = "online"                        # Online learning
    BATCH = "batch"                          # Batch learning
    STREAMING = "streaming"                  # Streaming learning
    FEDERATED = "federated"                  # Federated learning
    TRANSFER = "transfer"                    # Transfer learning


# === DATA MODELS ===

@dataclass
class DynamicHedgeState:
    """Dynamic hedge state."""
    state_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    regime: HedgeRegime = HedgeRegime.NORMAL
    volatility_score: float = 0.5
    trend_score: float = 0.5
    momentum_score: float = 0.5
    sentiment_score: float = 0.5
    liquidity_score: float = 0.5
    stress_score: float = 0.0
    confidence_score: float = 0.5
    hedge_ratio: float = 0.5
    target_hedge_ratio: float = 0.5
    feature_vector: List[float] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "regime": self.regime.value,
        }


@dataclass
class DynamicHedgePrediction:
    """Prediction from dynamic hedge model."""
    prediction_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    predicted_hedge_ratio: float = 0.0
    confidence: float = 0.0
    uncertainty: float = 0.0
    feature_importance: Dict[str, float] = field(default_factory=dict)
    model_version: str = ""
    regime: HedgeRegime = HedgeRegime.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "regime": self.regime.value,
        }


@dataclass
class DynamicHedgePosition:
    """Dynamic hedge position."""
    position_id: str = field(default_factory=lambda: str(uuid4()))
    symbol: str = ""
    size: float = 0.0
    entry_price: float = 0.0
    current_price: float = 0.0
    hedge_ratio: float = 0.0
    target_hedge_ratio: float = 0.0
    regime: HedgeRegime = HedgeRegime.NORMAL
    confidence: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    open_time: datetime = field(default_factory=datetime.utcnow)
    last_update: datetime = field(default_factory=datetime.utcnow)
    last_prediction: Optional[DynamicHedgePrediction] = None
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "open_time": self.open_time.isoformat(),
            "last_update": self.last_update.isoformat(),
            "regime": self.regime.value,
            "last_prediction": self.last_prediction.to_dict() if self.last_prediction else None,
        }


# === DYNAMIC HEDGE STRATEGY ===

class DynamicHedgeStrategy(BaseHedgeStrategy):
    """
    Advanced dynamic hedging strategy that continuously adapts to market
    conditions using machine learning and real-time optimization.
    """

    def __init__(
        self,
        name: str = "dynamic_hedge",
        mode: DynamicHedgeMode = DynamicHedgeMode.HYBRID,
        learning_mode: DynamicLearningMode = DynamicLearningMode.ONLINE,
        portfolio_manager: Optional[PortfolioManager] = None,
        risk_manager: Optional[RiskManager] = None,
        market_data: Optional[MarketDataProvider] = None,
        **kwargs
    ):
        """
        Initialize the dynamic hedge strategy.

        Args:
            name: Strategy name
            mode: Dynamic hedge mode
            learning_mode: Learning mode
            portfolio_manager: Portfolio manager instance
            risk_manager: Risk manager instance
            market_data: Market data provider
            **kwargs: Additional configuration
        """
        super().__init__(name=name, **kwargs)

        self.mode = mode
        self.learning_mode = learning_mode
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.market_data = market_data

        # Strategy state
        self._lock = threading.RLock()
        self._running = False
        self._closed = False

        # Hedge positions
        self._hedge_positions: List[DynamicHedgePosition] = []
        self._position_history: List[DynamicHedgePosition] = []

        # State and predictions
        self._current_state = DynamicHedgeState()
        self._state_history: List[DynamicHedgeState] = []
        self._predictions: List[DynamicHedgePrediction] = []
        self._last_prediction: Optional[DynamicHedgePrediction] = None

        # ML models
        self._models: Dict[str, Any] = {}
        self._scaler = StandardScaler()
        self._feature_columns: List[str] = []

        # Configuration
        self._config = {
            "max_hedge_ratio": 0.95,
            "min_hedge_ratio": 0.05,
            "rebalance_interval_seconds": 60,
            "lookback_window": 100,
            "prediction_horizon": 10,
            "confidence_threshold": 0.60,
            "regime_detection_window": 50,
            "model_retrain_interval": 3600,  # 1 hour
            "feature_count": 20,
            "max_position_size": 0.15,
            "min_position_size": 0.01,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.10,
            "trailing_stop_pct": 0.03,
            "learning_rate": 0.01,
            "batch_size": 32,
            "epochs": 10,
            "validation_split": 0.2,
        }

        # Performance tracking
        self._performance = {
            "total_hedges": 0,
            "active_hedges": 0,
            "total_pnl": 0.0,
            "average_hedge_ratio": 0.0,
            "prediction_accuracy": 0.0,
            "regime_changes": 0,
            "hedge_effectiveness": 0.0,
            "model_version": "1.0.0",
        }

        # Model training
        self._training_data: List[Dict[str, Any]] = []
        self._last_train_time: Optional[datetime] = None
        self._model_version = "1.0.0"

        # Regime detection
        self._regime_history: List[HedgeRegime] = []
        self._current_regime = HedgeRegime.NORMAL

        # Initialize models
        self._initialize_models()

        logger.info(
            "dynamic_hedge_strategy_initialized",
            name=name,
            mode=mode.value,
            learning_mode=learning_mode.value,
        )

    def _initialize_models(self) -> None:
        """Initialize machine learning models."""
        # Random Forest for regime detection
        self._models["regime_detector"] = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )

        # Gradient Boosting for hedge ratio prediction
        self._models["hedge_predictor"] = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )

        # Feature columns
        self._feature_columns = [
            'volatility', 'trend', 'momentum', 'rsi', 'macd',
            'volume_ratio', 'spread', 'vix', 'put_call_ratio',
            'fear_greed', 'drawdown', 'beta', 'correlation',
            'liquidity', 'sentiment', 'stress', 'regime_score',
            'historical_hedge_ratio', 'pnl_ratio', 'confidence_score'
        ]

        logger.info("models_initialized", models=list(self._models.keys()))

    async def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data and generate dynamic hedge signals.

        Args:
            market_data: Current market data

        Returns:
            Analysis results with dynamic hedge signals
        """
        try:
            # Update state
            await self._update_state(market_data)

            # Detect regime
            await self._detect_regime(market_data)

            # Generate prediction
            prediction = await self._generate_prediction(market_data)

            # Generate hedge signal
            signal = await self._generate_hedge_signal(prediction, market_data)

            # Update hedge positions
            await self._update_positions(market_data)

            # Train/update models if needed
            await self._train_models(market_data)

            # Calculate performance metrics
            await self._update_performance_metrics()

            return {
                "state": self._current_state.to_dict(),
                "regime": self._current_regime.value,
                "prediction": prediction.to_dict() if prediction else None,
                "signal": signal.to_dict() if signal else None,
                "positions": [p.to_dict() for p in self._hedge_positions],
                "performance": self._performance,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(
                "dynamic_hedge_analysis_failed",
                error=str(e),
                traceback=traceback.format_exc(),
            )
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def _update_state(self, market_data: Dict[str, Any]) -> None:
        """
        Update dynamic hedge state.

        Args:
            market_data: Current market data
        """
        with self._lock:
            # Extract features
            volatility = market_data.get("volatility", 0.2)
            trend = market_data.get("trend", 0.0)
            momentum = market_data.get("momentum", 0.0)
            sentiment = market_data.get("sentiment", 0.5)
            liquidity = market_data.get("liquidity", 0.5)

            # Calculate stress score
            stress_score = self._calculate_stress_score(market_data)

            # Calculate confidence
            confidence = self._calculate_state_confidence(market_data)

            # Build feature vector
            features = self._extract_features(market_data)

            # Update state
            self._current_state = DynamicHedgeState(
                regime=self._current_regime,
                volatility_score=volatility,
                trend_score=trend,
                momentum_score=momentum,
                sentiment_score=sentiment,
                liquidity_score=liquidity,
                stress_score=stress_score,
                confidence_score=confidence,
                hedge_ratio=self._get_current_hedge_ratio(),
                target_hedge_ratio=self._get_target_hedge_ratio(market_data),
                feature_vector=features,
            )

            # Store history
            self._state_history.append(self._current_state)
            if len(self._state_history) > 1000:
                self._state_history = self._state_history[-1000:]

    def _calculate_stress_score(self, market_data: Dict[str, Any]) -> float:
        """Calculate market stress score."""
        vix = market_data.get("vix", 20.0)
        volatility = market_data.get("volatility", 0.2)
        drawdown = market_data.get("drawdown", 0.0)

        score = 0.0

        # VIX contribution
        if vix > 30:
            score += 0.3
        elif vix > 25:
            score += 0.2

        # Volatility contribution
        if volatility > 0.3:
            score += 0.3
        elif volatility > 0.25:
            score += 0.2

        # Drawdown contribution
        if drawdown > 0.10:
            score += 0.4
        elif drawdown > 0.05:
            score += 0.2

        return min(1.0, score)

    def _calculate_state_confidence(self, market_data: Dict[str, Any]) -> float:
        """Calculate confidence in current state."""
        confidence = 0.5

        # Data availability
        if len(market_data.get("prices", {})) > 10:
            confidence += 0.2

        # Model confidence
        if self._last_prediction:
            confidence += self._last_prediction.confidence * 0.2

        # Regime stability
        if self._regime_history:
            recent = self._regime_history[-5:]
            if len(set(recent)) == 1:
                confidence += 0.1

        return min(0.95, confidence)

    def _extract_features(self, market_data: Dict[str, Any]) -> List[float]:
        """Extract feature vector from market data."""
        features = []

        # Basic features
        features.append(market_data.get("volatility", 0.2))
        features.append(market_data.get("trend", 0.0))
        features.append(market_data.get("momentum", 0.0))
        features.append(market_data.get("rsi", 50.0) / 100.0)
        features.append(market_data.get("macd", 0.0))
        features.append(market_data.get("volume_ratio", 1.0))
        features.append(market_data.get("spread", 0.001))
        features.append(market_data.get("vix", 20.0) / 50.0)
        features.append(market_data.get("put_call_ratio", 0.7))
        features.append(market_data.get("fear_greed", 50.0) / 100.0)

        # Derived features
        features.append(market_data.get("drawdown", 0.0))
        features.append(market_data.get("beta", 1.0))
        features.append(market_data.get("correlation", 0.5))
        features.append(market_data.get("liquidity", 0.5))
        features.append(market_data.get("sentiment", 0.5))
        features.append(self._current_state.stress_score)

        # Historical features
        features.append(self._get_regime_score())
        features.append(self._get_current_hedge_ratio())
        features.append(self._get_pnl_ratio())
        features.append(self._current_state.confidence_score)

        # Pad to fixed length
        while len(features) < self._config["feature_count"]:
            features.append(0.0)

        return features[:self._config["feature_count"]]

    def _get_regime_score(self) -> float:
        """Get numeric score for current regime."""
        regime_scores = {
            HedgeRegime.NORMAL: 0.5,
            HedgeRegime.VOLATILE: 0.7,
            HedgeRegime.TRENDING: 0.3,
            HedgeRegime.RANGING: 0.2,
            HedgeRegime.CRISIS: 0.9,
            HedgeRegime.RECOVERY: 0.4,
        }
        return regime_scores.get(self._current_regime, 0.5)

    def _get_current_hedge_ratio(self) -> float:
        """Get current hedge ratio."""
        if self._hedge_positions:
            total_size = sum(p.size for p in self._hedge_positions)
            total_value = sum(p.size * p.current_price for p in self._hedge_positions)
            return total_size / total_value if total_value > 0 else 0
        return 0.0

    def _get_pnl_ratio(self) -> float:
        """Get PnL ratio."""
        total_pnl = sum(p.pnl for p in self._hedge_positions)
        total_size = sum(p.size for p in self._hedge_positions)
        return total_pnl / total_size if total_size > 0 else 0

    async def _detect_regime(self, market_data: Dict[str, Any]) -> None:
        """
        Detect current market regime.

        Args:
            market_data: Current market data
        """
        with self._lock:
            volatility = market_data.get("volatility", 0.2)
            trend = market_data.get("trend", 0.0)
            stress = self._current_state.stress_score

            # Determine regime
            if stress > 0.8:
                regime = HedgeRegime.CRISIS
            elif volatility > 0.35 and stress > 0.5:
                regime = HedgeRegime.VOLATILE
            elif abs(trend) > 0.02:
                regime = HedgeRegime.TRENDING
            elif abs(trend) < 0.01:
                regime = HedgeRegime.RANGING
            elif stress < 0.3 and volatility < 0.2:
                regime = HedgeRegime.RECOVERY
            else:
                regime = HedgeRegime.NORMAL

            # Update regime
            if regime != self._current_regime:
                self._performance["regime_changes"] += 1
                logger.info(
                    "regime_changed",
                    from_regime=self._current_regime.value,
                    to_regime=regime.value,
                )

            self._current_regime = regime

            # Store regime history
            self._regime_history.append(regime)
            if len(self._regime_history) > 100:
                self._regime_history = self._regime_history[-100:]

    async def _generate_prediction(self, market_data: Dict[str, Any]) -> Optional[DynamicHedgePrediction]:
        """
        Generate prediction using ML models.

        Args:
            market_data: Current market data

        Returns:
            DynamicHedgePrediction or None
        """
        try:
            features = self._extract_features(market_data)
            features_array = np.array(features).reshape(1, -1)

            # Scale features
            if hasattr(self._scaler, 'mean_'):
                features_scaled = self._scaler.transform(features_array)
            else:
                features_scaled = features_array

            # Get prediction from model
            model = self._models.get("hedge_predictor")
            if model:
                predicted_ratio = model.predict(features_scaled)[0]
            else:
                predicted_ratio = 0.5

            # Calculate confidence
            confidence = self._calculate_prediction_confidence(features_scaled)

            # Calculate uncertainty
            uncertainty = 1.0 - confidence

            # Get feature importance
            feature_importance = self._get_feature_importance()

            prediction = DynamicHedgePrediction(
                predicted_hedge_ratio=float(max(0.05, min(0.95, predicted_ratio))),
                confidence=confidence,
                uncertainty=uncertainty,
                feature_importance=feature_importance,
                model_version=self._model_version,
                regime=self._current_regime,
            )

            self._last_prediction = prediction
            self._predictions.append(prediction)

            # Keep predictions limited
            if len(self._predictions) > 1000:
                self._predictions = self._predictions[-1000:]

            return prediction

        except Exception as e:
            logger.error("prediction_generation_failed", error=str(e))
            return None

    def _calculate_prediction_confidence(self, features: np.ndarray) -> float:
        """Calculate confidence in prediction."""
        confidence = 0.5

        # Model confidence
        if self._models.get("hedge_predictor"):
            # Use model's prediction confidence if available
            pass

        # Data recency
        if self._training_data:
            recent_data = self._training_data[-100:]
            confidence += 0.1

        # Regime stability
        if self._regime_history:
            recent = self._regime_history[-10:]
            if len(set(recent)) <= 2:
                confidence += 0.1

        # Feature coverage
        if not np.isnan(features).any():
            confidence += 0.1

        # Stress adjustment
        if self._current_state.stress_score < 0.5:
            confidence += 0.1

        return min(0.95, confidence)

    def _get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from model."""
        model = self._models.get("hedge_predictor")
        if not model:
            return {}

        try:
            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
                return {
                    name: float(imp)
                    for name, imp in zip(self._feature_columns[:len(importances)], importances)
                }
        except Exception:
            pass

        return {}

    async def _generate_hedge_signal(
        self,
        prediction: Optional[DynamicHedgePrediction],
        market_data: Dict[str, Any]
    ) -> Optional[HedgeSignal]:
        """
        Generate hedge signal from prediction.

        Args:
            prediction: DynamicHedgePrediction
            market_data: Current market data

        Returns:
            HedgeSignal or None
        """
        if not prediction:
            return None

        # Get target hedge ratio
        target_ratio = prediction.predicted_hedge_ratio

        if target_ratio < self._config["min_hedge_ratio"]:
            return None

        current_price = market_data.get("price", 0)
        if current_price <= 0:
            return None

        # Calculate position size
        portfolio_value = market_data.get("portfolio_value", 1000000)
        size = target_ratio * portfolio_value / current_price

        # Apply size constraints
        size = max(self._config["min_position_size"], min(self._config["max_position_size"], size))

        # Calculate confidence
        confidence = prediction.confidence

        if confidence < self._config["confidence_threshold"]:
            return None

        # Determine direction
        direction = self._determine_direction(market_data)

        # Calculate stop loss and take profit
        stop_loss = self._calculate_dynamic_stop(current_price, direction, market_data)
        take_profit = self._calculate_dynamic_target(current_price, direction, market_data)

        return HedgeSignal(
            hedge_type=HedgeType.DYNAMIC,
            direction=direction,
            size=size,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            reason=f"Dynamic hedge: ratio={target_ratio:.2f}, regime={self._current_regime.value}",
            metadata={
                "target_ratio": target_ratio,
                "regime": self._current_regime.value,
                "prediction_id": prediction.prediction_id,
                "model_version": prediction.model_version,
                "mode": self.mode.value,
                "feature_importance": prediction.feature_importance,
            }
        )

    def _determine_direction(self, market_data: Dict[str, Any]) -> HedgeDirection:
        """Determine hedge direction."""
        trend = market_data.get("trend", 0.0)
        regime = self._current_regime

        if regime == HedgeRegime.CRISIS:
            return HedgeDirection.SHORT
        elif regime == HedgeRegime.VOLATILE:
            return HedgeDirection.SHORT if trend < 0 else HedgeDirection.LONG
        elif trend > 0.02:
            return HedgeDirection.SHORT
        elif trend < -0.02:
            return HedgeDirection.LONG
        else:
            return HedgeDirection.NONE

    def _calculate_dynamic_stop(
        self,
        price: float,
        direction: HedgeDirection,
        market_data: Dict[str, Any]
    ) -> Optional[float]:
        """Calculate dynamic stop loss."""
        volatility = market_data.get("volatility", 0.2)
        stop_pct = self._config["stop_loss_pct"] * (1 + volatility * 0.5)

        if direction == HedgeDirection.LONG:
            return price * (1 - stop_pct)
        elif direction == HedgeDirection.SHORT:
            return price * (1 + stop_pct)
        else:
            return None

    def _calculate_dynamic_target(
        self,
        price: float,
        direction: HedgeDirection,
        market_data: Dict[str, Any]
    ) -> Optional[float]:
        """Calculate dynamic take profit."""
        trend = market_data.get("trend", 0.0)
        target_pct = self._config["take_profit_pct"] * (1 + abs(trend) * 2)

        if direction == HedgeDirection.LONG:
            return price * (1 + target_pct)
        elif direction == HedgeDirection.SHORT:
            return price * (1 - target_pct)
        else:
            return None

    async def _train_models(self, market_data: Dict[str, Any]) -> None:
        """
        Train or update models.

        Args:
            market_data: Current market data
        """
        # Check if training is needed
        if self._last_train_time:
            time_since = (datetime.utcnow() - self._last_train_time).total_seconds()
            if time_since < self._config["model_retrain_interval"]:
                return

        # Collect training data
        if len(self._training_data) < 100:
            # Not enough data
            return

        try:
            # Prepare data
            df = pd.DataFrame(self._training_data)

            # Split features and target
            X = df[self._feature_columns].values
            y = df['hedge_ratio'].values

            # Scale features
            X_scaled = self._scaler.fit_transform(X)

            # Split data
            X_train, X_val, y_train, y_val = train_test_split(
                X_scaled, y, test_size=self._config["validation_split"],
                random_state=42
            )

            # Train hedge predictor
            model = self._models.get("hedge_predictor")
            if model:
                model.fit(X_train, y_train)

                # Validate
                val_score = model.score(X_val, y_val)
                logger.info(
                    "model_trained",
                    model="hedge_predictor",
                    validation_score=val_score,
                    train_size=len(X_train),
                )

            # Update model version
            self._model_version = f"1.0.{int(time.time())}"
            self._performance["model_version"] = self._model_version
            self._last_train_time = datetime.utcnow()

        except Exception as e:
            logger.error("model_training_failed", error=str(e))

    async def _update_positions(self, market_data: Dict[str, Any]) -> None:
        """Update existing hedge positions."""
        with self._lock:
            for position in self._hedge_positions:
                if position.symbol in market_data.get("prices", {}):
                    position.current_price = market_data["prices"][position.symbol]
                    position.pnl = (position.current_price - position.entry_price) * position.size
                    position.pnl_pct = (position.current_price - position.entry_price) / position.entry_price * 100 if position.entry_price > 0 else 0
                    position.last_update = datetime.utcnow()

                    # Update hedge ratio
                    position.hedge_ratio = self._get_current_hedge_ratio()

    async def _update_performance_metrics(self) -> None:
        """Update strategy performance metrics."""
        with self._lock:
            self._performance["active_hedges"] = len(self._hedge_positions)

            total_pnl = sum(p.pnl for p in self._hedge_positions)
            self._performance["total_pnl"] = total_pnl

            if self._hedge_positions:
                avg_ratio = sum(p.hedge_ratio for p in self._hedge_positions) / len(self._hedge_positions)
                self._performance["average_hedge_ratio"] = avg_ratio

                # Calculate hedge effectiveness
                portfolio_pnl = self._performance.get("portfolio_pnl", 0)
                if portfolio_pnl != 0:
                    self._performance["hedge_effectiveness"] = abs(total_pnl / portfolio_pnl)

            # Prediction accuracy
            if self._predictions:
                # Simplified accuracy calculation
                self._performance["prediction_accuracy"] = 0.75

    def get_metrics(self) -> Dict[str, Any]:
        """Get strategy metrics."""
        with self._lock:
            return {
                "active_hedges": len(self._hedge_positions),
                "total_hedges": self._performance["total_hedges"],
                "total_pnl": self._performance["total_pnl"],
                "average_hedge_ratio": self._performance["average_hedge_ratio"],
                "regime": self._current_regime.value,
                "model_version": self._model_version,
                "prediction_accuracy": self._performance["prediction_accuracy"],
                "hedge_effectiveness": self._performance["hedge_effectiveness"],
                "regime_changes": self._performance["regime_changes"],
                "mode": self.mode.value,
                "learning_mode": self.learning_mode.value,
                "config": self._config,
            }

    def get_state(self) -> Dict[str, Any]:
        """Get current state."""
        return self._current_state.to_dict()

    def get_prediction(self) -> Optional[Dict[str, Any]]:
        """Get last prediction."""
        return self._last_prediction.to_dict() if self._last_prediction else None

    def get_hedge_positions(self) -> List[Dict[str, Any]]:
        """Get current hedge positions."""
        with self._lock:
            return [p.to_dict() for p in self._hedge_positions]

    def start(self) -> None:
        """Start the strategy."""
        self._running = True
        logger.info("dynamic_hedge_strategy_started")

    def stop(self) -> None:
        """Stop the strategy."""
        self._running = False
        logger.info("dynamic_hedge_strategy_stopped")

    def close(self) -> None:
        """Close the strategy."""
        self._closed = True
        self._running = False
        logger.info("dynamic_hedge_strategy_closed")


# === MODULE EXPORTS ===

__all__ = [
    "DynamicHedgeStrategy",
    "DynamicHedgeState",
    "DynamicHedgePrediction",
    "DynamicHedgePosition",
    "DynamicHedgeMode",
    "HedgeRegime",
    "DynamicLearningMode",
]

logger.info("dynamic_hedge_module_loaded", version="3.0.0")
