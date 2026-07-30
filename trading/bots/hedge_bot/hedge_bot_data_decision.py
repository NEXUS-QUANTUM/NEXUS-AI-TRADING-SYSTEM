# trading/bots/hedge_bot/hedge_bot_data_decision.py
# Advanced Data-Driven Decision Engine for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Data Decision Engine - Moteur de décision avancé basé sur les données pour le Hedge Bot.
Analyse en temps réel les données de marché, de portefeuille et de risque pour prendre des décisions
de hedging optimales avec des algorithmes d'IA et de machine learning.
"""

import asyncio
import json
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import (
    Any, Callable, Dict, List, Optional, Set, Tuple, Union, AsyncIterator, Coroutine
)
import uuid
import statistics
from collections import defaultdict, deque
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import joblib

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_data_decision")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataQuery, DistributedDataManager, DataConsistency
)
from trading.bots.hedge_bot.hedge_bot_risk_engine import (
    RiskMetrics, RiskLevel, RiskEngine
)


# ============== ENUMS & TYPES ==============

class DecisionType(Enum):
    """Types de décisions de hedging."""
    NONE = "none"
    ENTER_HEDGE = "enter_hedge"
    EXIT_HEDGE = "exit_hedge"
    ADJUST_HEDGE = "adjust_hedge"
    INCREASE_HEDGE = "increase_hedge"
    DECREASE_HEDGE = "decrease_hedge"
    REBALANCE = "rebalance"
    EMERGENCY_STOP = "emergency_stop"
    PAUSE = "pause"
    RESUME = "resume"


class DecisionPriority(Enum):
    """Priorités des décisions."""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


class DecisionConfidence(Enum):
    """Niveaux de confiance des décisions."""
    VERY_LOW = 0.0
    LOW = 0.25
    MEDIUM = 0.50
    HIGH = 0.75
    VERY_HIGH = 0.95
    CERTAIN = 1.0


class MarketRegime(Enum):
    """Régimes de marché."""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"
    CALM = "calm"
    CRASH = "crash"
    RALLY = "rally"
    UNKNOWN = "unknown"


class HedgeStrategy(Enum):
    """Stratégies de hedging disponibles."""
    NONE = "none"
    DELTA_HEDGE = "delta_hedge"
    GAMMA_HEDGE = "gamma_hedge"
    VEGA_HEDGE = "vega_hedge"
    THETA_HEDGE = "theta_hedge"
    CORRELATION_HEDGE = "correlation_hedge"
    VOLATILITY_HEDGE = "volatility_hedge"
    STATISTICAL_HEDGE = "statistical_hedge"
    DYNAMIC_HEDGE = "dynamic_hedge"
    PORTFOLIO_HEDGE = "portfolio_hedge"
    TAIL_HEDGE = "tail_hedge"
    CROSS_HEDGE = "cross_hedge"
    PAIR_HEDGE = "pair_hedge"
    BASKET_HEDGE = "basket_hedge"


# ============== DATA MODELS ==============

@dataclass
class Decision:
    """Modèle de décision de hedging."""
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_type: DecisionType = DecisionType.NONE
    priority: DecisionPriority = DecisionPriority.MEDIUM
    confidence: float = 0.0
    strategy: HedgeStrategy = HedgeStrategy.NONE
    target_asset: Optional[str] = None
    target_amount: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    executed: bool = False
    execution_result: Optional[Dict[str, Any]] = None
    parent_decision_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "decision_id": self.decision_id,
            "decision_type": self.decision_type.value,
            "priority": self.priority.value,
            "confidence": self.confidence,
            "strategy": self.strategy.value,
            "target_asset": self.target_asset,
            "target_amount": self.target_amount,
            "target_price": self.target_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "reason": self.reason,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "executed": self.executed,
            "execution_result": self.execution_result,
            "parent_decision_id": self.parent_decision_id
        }


@dataclass
class DecisionContext:
    """Contexte pour les décisions de hedging."""
    timestamp: datetime
    symbol: str
    current_price: float
    position: Optional[Dict[str, Any]] = None
    portfolio: Optional[Dict[str, Any]] = None
    risk_metrics: Optional[RiskMetrics] = None
    market_regime: MarketRegime = MarketRegime.UNKNOWN
    volatility: float = 0.0
    volume: float = 0.0
    open_interest: float = 0.0
    greeks: Dict[str, float] = field(default_factory=dict)
    correlations: Dict[str, float] = field(default_factory=dict)
    historical_data: Optional[pd.DataFrame] = None
    technical_indicators: Dict[str, float] = field(default_factory=dict)
    sentiment_score: float = 0.0
    order_book_imbalance: float = 0.0
    funding_rate: float = 0.0
    basis: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionResult:
    """Résultat d'une décision de hedging."""
    decision: Decision
    executed: bool = False
    execution_time: float = 0.0
    error: Optional[str] = None
    result_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ============== INTERFACES ==============

class DecisionEngineInterface(ABC):
    """Interface abstraite pour le moteur de décision."""
    
    @abstractmethod
    async def analyze(self, context: DecisionContext) -> Decision:
        """Analyse le contexte et retourne une décision."""
        pass
    
    @abstractmethod
    async def evaluate(self, decision: Decision) -> DecisionResult:
        """Évalue et exécute une décision."""
        pass
    
    @abstractmethod
    async def get_history(self, limit: int = 100) -> List[Decision]:
        """Récupère l'historique des décisions."""
        pass


# ============== IMPLÉMENTATIONS ==============

class HedgeDecisionEngine(DecisionEngineInterface):
    """
    Moteur de décision de hedging avancé.
    Combine analyse technique, fondamentale, de risque et d'IA.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        risk_engine: Optional[RiskEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.risk_engine = risk_engine
        self.config = config or self._default_config()
        
        # Modèles ML
        self._models: Dict[str, Any] = {}
        self._scaler = StandardScaler()
        self._model_loaded = False
        
        # Historique des décisions
        self._decision_history: deque = deque(maxlen=1000)
        self._decision_cache: Dict[str, Decision] = {}
        
        # Métriques de performance
        self._performance_metrics: Dict[str, Any] = {
            "total_decisions": 0,
            "successful_decisions": 0,
            "failed_decisions": 0,
            "avg_confidence": 0.0,
            "decision_types": defaultdict(int),
            "strategies": defaultdict(int),
            "errors": []
        }
        
        # Seuils et paramètres
        self._thresholds = self.config.get("thresholds", {})
        self._weights = self.config.get("weights", {})
        
        # Thread pools
        self._compute_executor = ThreadPoolExecutor(max_workers=4)
        
        logger.info("HedgeDecisionEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "thresholds": {
                "min_confidence": 0.4,
                "high_confidence": 0.7,
                "critical_risk_threshold": 0.8,
                "volatility_threshold": 0.3,
                "drawdown_threshold": 0.1,
                "correlation_threshold": 0.7,
                "sentiment_threshold": 0.6,
                "volume_spike_threshold": 2.0
            },
            "weights": {
                "risk_score": 0.30,
                "market_regime": 0.20,
                "volatility": 0.15,
                "technical_signals": 0.15,
                "sentiment": 0.10,
                "momentum": 0.10
            },
            "ml": {
                "enabled": True,
                "model_path": "models/hedge_decision_model.pkl",
                "retrain_interval": 3600,  # 1 heure
                "features": [
                    "volatility", "drawdown", "var", "sharpe",
                    "momentum", "rsi", "macd", "bollinger",
                    "volume_ratio", "sentiment", "funding_rate"
                ]
            },
            "strategies": {
                "default": HedgeStrategy.DYNAMIC_HEDGE,
                "bull": HedgeStrategy.DELTA_HEDGE,
                "bear": HedgeStrategy.PORTFOLIO_HEDGE,
                "volatile": HedgeStrategy.VOLATILITY_HEDGE,
                "crash": HedgeStrategy.TAIL_HEDGE
            }
        }
    
    async def start(self) -> None:
        """Démarre le moteur de décision."""
        logger.info("HedgeDecisionEngine starting...")
        
        # Chargement des modèles ML
        if self.config["ml"]["enabled"]:
            await self._load_models()
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._model_update_loop())
        asyncio.create_task(self._performance_monitor_loop())
        
        logger.info("HedgeDecisionEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de décision."""
        logger.info("HedgeDecisionEngine stopping...")
        self._compute_executor.shutdown(wait=True)
        logger.info("HedgeDecisionEngine stopped")
    
    async def analyze(self, context: DecisionContext) -> Decision:
        """Analyse le contexte et retourne une décision optimale."""
        start_time = time.time()
        
        try:
            # 1. Collecte des données
            data = await self._collect_data(context)
            
            # 2. Analyse du risque
            risk_analysis = await self._analyze_risk(data)
            
            # 3. Analyse du marché
            market_analysis = await self._analyze_market(data)
            
            # 4. Analyse technique
            technical_analysis = await self._analyze_technical(data)
            
            # 5. Analyse du sentiment
            sentiment_analysis = await self._analyze_sentiment(data)
            
            # 6. Sélection de la stratégie
            strategy = await self._select_strategy(
                risk_analysis, market_analysis, technical_analysis, sentiment_analysis
            )
            
            # 7. Détermination des paramètres
            params = await self._determine_parameters(
                strategy, risk_analysis, market_analysis, data
            )
            
            # 8. Calcul de la confiance
            confidence = await self._calculate_confidence(
                risk_analysis, market_analysis, technical_analysis, sentiment_analysis
            )
            
            # 9. Création de la décision
            decision = Decision(
                decision_type=self._determine_decision_type(risk_analysis),
                priority=self._determine_priority(risk_analysis, confidence),
                confidence=confidence,
                strategy=strategy,
                target_asset=context.symbol,
                target_amount=params.get("amount"),
                target_price=params.get("price"),
                stop_loss=params.get("stop_loss"),
                take_profit=params.get("take_profit"),
                reason=self._generate_reason(
                    risk_analysis, market_analysis, technical_analysis, sentiment_analysis
                ),
                metadata={
                    "context": context.metadata,
                    "risk_score": risk_analysis.get("score", 0.0),
                    "market_regime": market_analysis.get("regime", "unknown"),
                    "confidence_components": {
                        "risk": risk_analysis.get("confidence", 0.0),
                        "market": market_analysis.get("confidence", 0.0),
                        "technical": technical_analysis.get("confidence", 0.0),
                        "sentiment": sentiment_analysis.get("confidence", 0.0)
                    }
                }
            )
            
            # 10. Validation avec ML
            if self.config["ml"]["enabled"] and self._model_loaded:
                ml_decision = await self._ml_predict(data)
                decision = await self._merge_decisions(decision, ml_decision)
            
            # Cache et historique
            self._decision_cache[decision.decision_id] = decision
            self._decision_history.append(decision)
            self._performance_metrics["total_decisions"] += 1
            self._performance_metrics["decision_types"][decision.decision_type.value] += 1
            self._performance_metrics["strategies"][decision.strategy.value] += 1
            
            execution_time = time.time() - start_time
            logger.info(f"Decision generated: {decision.decision_type.value} "
                       f"confidence={decision.confidence:.2f} "
                       f"strategy={decision.strategy.value} "
                       f"time={execution_time:.3f}s")
            
            return decision
            
        except Exception as e:
            logger.error(f"Error in analyze: {e}", exc_info=True)
            self._performance_metrics["errors"].append(str(e))
            
            # Décision par défaut en cas d'erreur
            return Decision(
                decision_type=DecisionType.NONE,
                reason=f"Error in analysis: {str(e)}",
                confidence=0.0
            )
    
    async def evaluate(self, decision: Decision) -> DecisionResult:
        """Évalue et exécute une décision."""
        start_time = time.time()
        
        try:
            # Vérification de la validité
            if not await self._validate_decision(decision):
                return DecisionResult(
                    decision=decision,
                    executed=False,
                    error="Decision validation failed",
                    execution_time=time.time() - start_time
                )
            
            # Simulation des résultats
            simulation_result = await self._simulate_decision(decision)
            
            if not simulation_result.get("viable", False):
                return DecisionResult(
                    decision=decision,
                    executed=False,
                    error="Decision not viable according to simulation",
                    result_data=simulation_result,
                    execution_time=time.time() - start_time
                )
            
            # Exécution
            execution_result = await self._execute_decision(decision)
            
            # Mise à jour du statut
            decision.executed = execution_result.get("success", False)
            decision.execution_result = execution_result
            
            # Métriques
            if decision.executed:
                self._performance_metrics["successful_decisions"] += 1
            else:
                self._performance_metrics["failed_decisions"] += 1
            
            result = DecisionResult(
                decision=decision,
                executed=decision.executed,
                execution_time=time.time() - start_time,
                result_data=execution_result,
                error=execution_result.get("error")
            )
            
            logger.info(f"Decision evaluated: {decision.decision_id} "
                       f"executed={result.executed} "
                       f"time={result.execution_time:.3f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in evaluate: {e}", exc_info=True)
            return DecisionResult(
                decision=decision,
                executed=False,
                error=str(e),
                execution_time=time.time() - start_time
            )
    
    async def get_history(self, limit: int = 100) -> List[Decision]:
        """Récupère l'historique des décisions."""
        return list(self._decision_history)[-limit:]
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Récupère les métriques de performance."""
        total = self._performance_metrics["total_decisions"]
        if total > 0:
            self._performance_metrics["success_rate"] = (
                self._performance_metrics["successful_decisions"] / total
            )
            self._performance_metrics["failure_rate"] = (
                self._performance_metrics["failed_decisions"] / total
            )
        return self._performance_metrics
    
    # ========== MÉTHODES D'ANALYSE ==========
    
    async def _collect_data(self, context: DecisionContext) -> Dict[str, Any]:
        """Collecte toutes les données nécessaires."""
        data = {
            "context": context,
            "market_data": {},
            "portfolio_data": {},
            "historical_data": None,
            "technical_data": {},
            "sentiment_data": {},
            "risk_data": {}
        }
        
        # Données de marché
        if self.data_manager:
            # Prix actuels
            price_record = await self.data_manager.retrieve(
                f"{context.symbol}:price", DataType.MARKET
            )
            if price_record:
                data["market_data"]["price"] = price_record
            
            # Données historiques
            hist_query = DataQuery(
                query_id=f"hist_{context.symbol}_{int(time.time())}",
                data_type=DataType.HISTORICAL,
                keys=[f"{context.symbol}:history"],
                limit=1000
            )
            hist_result = await self.data_manager.query(hist_query)
            if hist_result.records:
                data["historical_data"] = hist_result.records
            
            # Données techniques
            tech_query = DataQuery(
                query_id=f"tech_{context.symbol}_{int(time.time())}",
                data_type=DataType.DERIVED,
                keys=[f"{context.symbol}:indicators"]
            )
            tech_result = await self.data_manager.query(tech_query)
            if tech_result.records:
                data["technical_data"] = tech_result.records[0].value
        
        # Données de portefeuille
        if context.portfolio:
            data["portfolio_data"] = context.portfolio
        
        # Données de risque
        if context.risk_metrics:
            data["risk_data"] = context.risk_metrics.to_dict()
        
        return data
    
    async def _analyze_risk(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyse les risques."""
        context = data["context"]
        risk_data = data.get("risk_data", {})
        
        # Calcul des métriques de risque
        risk_score = risk_data.get("var", 0.0) * 0.3 + \
                     risk_data.get("drawdown", 0.0) * 0.3 + \
                     risk_data.get("volatility", 0.0) * 0.2 + \
                     (1 - risk_data.get("sharpe", 0.0)) * 0.2
        
        # Niveau de risque
        if risk_score > 0.8:
            risk_level = "critical"
            confidence = 0.9
        elif risk_score > 0.6:
            risk_level = "high"
            confidence = 0.7
        elif risk_score > 0.4:
            risk_level = "medium"
            confidence = 0.5
        elif risk_score > 0.2:
            risk_level = "low"
            confidence = 0.3
        else:
            risk_level = "minimal"
            confidence = 0.1
        
        return {
            "score": risk_score,
            "level": risk_level,
            "confidence": confidence,
            "metrics": risk_data
        }
    
    async def _analyze_market(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyse les conditions de marché."""
        context = data["context"]
        
        # Détermination du régime de marché
        regime = context.market_regime
        
        if regime == MarketRegime.UNKNOWN:
            # Détection automatique
            vol = context.volatility
            trend = context.technical_indicators.get("trend", 0.0)
            
            if vol > 0.5:
                regime = MarketRegime.VOLATILE
            elif vol < 0.15:
                regime = MarketRegime.CALM
            elif trend > 0.2:
                regime = MarketRegime.BULL
            elif trend < -0.2:
                regime = MarketRegime.BEAR
            else:
                regime = MarketRegime.SIDEWAYS
        
        # Confiance de l'analyse de marché
        confidence = 0.5
        if context.volume > 0:
            confidence += 0.1
        if context.volatility < 0.5:
            confidence += 0.1
        if context.order_book_imbalance != 0:
            confidence += 0.1
        
        return {
            "regime": regime.value,
            "confidence": min(confidence, 1.0),
            "volatility": context.volatility,
            "volume": context.volume,
            "order_book_imbalance": context.order_book_imbalance,
            "funding_rate": context.funding_rate,
            "basis": context.basis
        }
    
    async def _analyze_technical(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyse technique."""
        context = data["context"]
        indicators = context.technical_indicators
        
        # Calcul du signal technique global
        signals = []
        weights = []
        
        for indicator, value in indicators.items():
            if "rsi" in indicator.lower():
                # RSI: <30 oversold, >70 overbought
                if value < 30:
                    signals.append(1)  # Signal d'achat
                elif value > 70:
                    signals.append(-1)  # Signal de vente
                else:
                    signals.append(0)
                weights.append(0.2)
            
            elif "macd" in indicator.lower():
                # MACD
                if "histogram" in indicator.lower():
                    if value > 0:
                        signals.append(1)
                    else:
                        signals.append(-1)
                    weights.append(0.2)
            
            elif "bollinger" in indicator.lower():
                # Bollinger Bands
                if "position" in indicator.lower():
                    if value < -1:
                        signals.append(1)
                    elif value > 1:
                        signals.append(-1)
                    else:
                        signals.append(0)
                    weights.append(0.15)
            
            elif "momentum" in indicator.lower():
                if value > 0:
                    signals.append(1)
                else:
                    signals.append(-1)
                weights.append(0.15)
            
            elif "volume" in indicator.lower():
                if value > 2.0:  # Volume spike
                    signals.append(1)
                    weights.append(0.1)
        
        # Signal global pondéré
        if signals and weights:
            global_signal = sum(s * w for s, w in zip(signals, weights)) / sum(weights)
            confidence = abs(global_signal)
        else:
            global_signal = 0.0
            confidence = 0.0
        
        return {
            "signal": global_signal,
            "confidence": min(confidence, 1.0),
            "indicators": indicators,
            "signals": signals
        }
    
    async def _analyze_sentiment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyse du sentiment."""
        context = data["context"]
        sentiment_score = context.sentiment_score
        
        # Normalisation du sentiment
        normalized_sentiment = max(-1.0, min(1.0, sentiment_score))
        
        # Confiance basée sur la magnitude
        confidence = abs(normalized_sentiment)
        
        # Détection d'extremums
        if normalized_sentiment > 0.8:
            sentiment_label = "very_bullish"
        elif normalized_sentiment > 0.4:
            sentiment_label = "bullish"
        elif normalized_sentiment > -0.4:
            sentiment_label = "neutral"
        elif normalized_sentiment > -0.8:
            sentiment_label = "bearish"
        else:
            sentiment_label = "very_bearish"
        
        return {
            "score": normalized_sentiment,
            "label": sentiment_label,
            "confidence": min(confidence, 1.0)
        }
    
    async def _select_strategy(
        self,
        risk_analysis: Dict[str, Any],
        market_analysis: Dict[str, Any],
        technical_analysis: Dict[str, Any],
        sentiment_analysis: Dict[str, Any]
    ) -> HedgeStrategy:
        """Sélectionne la stratégie de hedging optimale."""
        
        # Récupération du régime de marché
        regime = market_analysis.get("regime", MarketRegime.UNKNOWN.value)
        risk_level = risk_analysis.get("level", "medium")
        
        # Sélection basée sur le risque et le marché
        if risk_level == "critical":
            return HedgeStrategy.EMERGENCY_STOP
        
        if risk_level == "high":
            if regime == MarketRegime.BULL.value:
                return HedgeStrategy.DELTA_HEDGE
            elif regime == MarketRegime.BEAR.value:
                return HedgeStrategy.PORTFOLIO_HEDGE
            elif regime == MarketRegime.VOLATILE.value:
                return HedgeStrategy.VOLATILITY_HEDGE
            else:
                return HedgeStrategy.DYNAMIC_HEDGE
        
        # Sélection basée sur les signaux techniques
        tech_signal = technical_analysis.get("signal", 0.0)
        sentiment_score = sentiment_analysis.get("score", 0.0)
        
        if abs(tech_signal) > 0.5:
            if tech_signal > 0:
                return HedgeStrategy.DELTA_HEDGE
            else:
                return HedgeStrategy.CORRELATION_HEDGE
        
        if abs(sentiment_score) > 0.6:
            if sentiment_score > 0:
                return HedgeStrategy.PAIR_HEDGE
            else:
                return HedgeStrategy.CROSS_HEDGE
        
        # Stratégie par défaut
        default_strategy = self.config["strategies"].get("default", HedgeStrategy.DYNAMIC_HEDGE)
        regime_strategy = self.config["strategies"].get(regime)
        
        if regime_strategy:
            return HedgeStrategy(regime_strategy)
        
        return default_strategy
    
    async def _determine_parameters(
        self,
        strategy: HedgeStrategy,
        risk_analysis: Dict[str, Any],
        market_analysis: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Détermine les paramètres de la stratégie."""
        context = data["context"]
        params = {
            "amount": 0.0,
            "price": context.current_price,
            "stop_loss": None,
            "take_profit": None
        }
        
        risk_score = risk_analysis.get("score", 0.0)
        volatility = market_analysis.get("volatility", 0.2)
        
        # Calcul du montant optimal basé sur le risque
        max_position = context.portfolio.get("total_value", 1000000) * 0.1
        risk_adjusted = max_position * (1 - risk_score) * (1 - volatility)
        
        # Ajustement selon la stratégie
        if strategy == HedgeStrategy.EMERGENCY_STOP:
            params["amount"] = 0.0
            params["stop_loss"] = context.current_price * 0.95
        
        elif strategy == HedgeStrategy.DELTA_HEDGE:
            # Delta hedging: montant proportionnel au delta
            delta = context.greeks.get("delta", 0.5)
            params["amount"] = risk_adjusted * abs(delta)
            params["stop_loss"] = context.current_price * 0.97
        
        elif strategy == HedgeStrategy.VOLATILITY_HEDGE:
            # Volatility hedge: montant proportionnel à la volatilité
            params["amount"] = risk_adjusted * volatility * 2
            params["stop_loss"] = context.current_price * 0.95
        
        elif strategy == HedgeStrategy.PORTFOLIO_HEDGE:
            # Portfolio hedge: couverture complète
            params["amount"] = risk_adjusted
            params["stop_loss"] = context.current_price * 0.95
        
        else:  # DYNAMIC_HEDGE ou autre
            params["amount"] = risk_adjusted * 0.5
            params["stop_loss"] = context.current_price * 0.97
        
        # Take profit basé sur le risque
        if params["stop_loss"]:
            stop_loss_pct = abs(params["stop_loss"] - context.current_price) / context.current_price
            params["take_profit"] = context.current_price * (1 + stop_loss_pct * 2)
        
        # Sécurité: montant maximum
        params["amount"] = min(params["amount"], max_position)
        
        return params
    
    async def _calculate_confidence(
        self,
        risk_analysis: Dict[str, Any],
        market_analysis: Dict[str, Any],
        technical_analysis: Dict[str, Any],
        sentiment_analysis: Dict[str, Any]
    ) -> float:
        """Calcule le niveau de confiance de la décision."""
        
        weights = self._weights
        
        # Confiance par composant
        risk_confidence = risk_analysis.get("confidence", 0.0)
        market_confidence = market_analysis.get("confidence", 0.0)
        tech_confidence = technical_analysis.get("confidence", 0.0)
        sent_confidence = sentiment_analysis.get("confidence", 0.0)
        
        # Confiance pondérée
        weighted_confidence = (
            risk_confidence * weights.get("risk_score", 0.30) +
            market_confidence * weights.get("market_regime", 0.20) +
            tech_confidence * weights.get("technical_signals", 0.15) +
            sent_confidence * weights.get("sentiment", 0.10)
        )
        
        # Ajustement par la volatilité
        volatility = market_analysis.get("volatility", 0.2)
        volatility_adjustment = 1 - min(volatility, 1.0) * 0.3
        
        # Ajustement par le risque
        risk_score = risk_analysis.get("score", 0.0)
        risk_adjustment = 1 - risk_score * 0.5
        
        # Confiance finale
        final_confidence = weighted_confidence * volatility_adjustment * risk_adjustment
        
        # Normalisation
        return max(0.0, min(1.0, final_confidence))
    
    def _determine_decision_type(self, risk_analysis: Dict[str, Any]) -> DecisionType:
        """Détermine le type de décision basé sur l'analyse de risque."""
        risk_level = risk_analysis.get("level", "medium")
        risk_score = risk_analysis.get("score", 0.0)
        
        if risk_level == "critical":
            return DecisionType.EMERGENCY_STOP
        
        if risk_level == "high":
            return DecisionType.ENTER_HEDGE
        
        if risk_level == "medium":
            if risk_score > 0.5:
                return DecisionType.INCREASE_HEDGE
            else:
                return DecisionType.ADJUST_HEDGE
        
        if risk_level == "low":
            return DecisionType.DECREASE_HEDGE
        
        if risk_level == "minimal":
            return DecisionType.EXIT_HEDGE
        
        return DecisionType.NONE
    
    def _determine_priority(
        self,
        risk_analysis: Dict[str, Any],
        confidence: float
    ) -> DecisionPriority:
        """Détermine la priorité de la décision."""
        risk_level = risk_analysis.get("level", "medium")
        risk_score = risk_analysis.get("score", 0.0)
        
        if risk_level == "critical":
            return DecisionPriority.CRITICAL
        
        if risk_level == "high" and confidence > 0.6:
            return DecisionPriority.HIGH
        
        if risk_level == "medium" and confidence > 0.5:
            return DecisionPriority.MEDIUM
        
        if risk_level == "low" and confidence > 0.4:
            return DecisionPriority.LOW
        
        return DecisionPriority.BACKGROUND
    
    def _generate_reason(
        self,
        risk_analysis: Dict[str, Any],
        market_analysis: Dict[str, Any],
        technical_analysis: Dict[str, Any],
        sentiment_analysis: Dict[str, Any]
    ) -> str:
        """Génère une raison lisible pour la décision."""
        reasons = []
        
        # Risque
        risk_level = risk_analysis.get("level", "medium")
        risk_score = risk_analysis.get("score", 0.0)
        reasons.append(f"Risk level: {risk_level.upper()} (score: {risk_score:.2f})")
        
        # Marché
        regime = market_analysis.get("regime", "unknown")
        reasons.append(f"Market regime: {regime.upper()}")
        
        # Technique
        tech_signal = technical_analysis.get("signal", 0.0)
        if abs(tech_signal) > 0.3:
            signal_text = "BULLISH" if tech_signal > 0 else "BEARISH"
            reasons.append(f"Technical signal: {signal_text} ({tech_signal:.2f})")
        
        # Sentiment
        sentiment_score = sentiment_analysis.get("score", 0.0)
        if abs(sentiment_score) > 0.3:
            sent_text = "POSITIVE" if sentiment_score > 0 else "NEGATIVE"
            reasons.append(f"Sentiment: {sent_text} ({sentiment_score:.2f})")
        
        return " | ".join(reasons)
    
    # ========== MÉTHODES ML ==========
    
    async def _load_models(self) -> None:
        """Charge les modèles ML."""
        try:
            model_path = self.config["ml"]["model_path"]
            self._models["classifier"] = joblib.load(model_path)
            self._model_loaded = True
            logger.info("ML models loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load ML models: {e}")
            self._model_loaded = False
    
    async def _ml_predict(self, data: Dict[str, Any]) -> Optional[Decision]:
        """Prédiction ML pour la décision."""
        if not self._model_loaded:
            return None
        
        try:
            # Extraction des features
            features = self._extract_features(data)
            
            # Prédiction
            prediction = self._models["classifier"].predict_proba([features])[0]
            
            # Création d'une décision ML
            ml_decision = Decision(
                decision_type=DecisionType.ADJUST_HEDGE,
                confidence=float(max(prediction)),
                strategy=HedgeStrategy.DYNAMIC_HEDGE,
                reason="ML-based decision",
                metadata={"ml_prediction": prediction.tolist()}
            )
            
            return ml_decision
            
        except Exception as e:
            logger.error(f"Error in ML prediction: {e}")
            return None
    
    def _extract_features(self, data: Dict[str, Any]) -> List[float]:
        """Extrait les features pour le modèle ML."""
        context = data.get("context")
        features = []
        
        for feature_name in self.config["ml"]["features"]:
            if feature_name == "volatility":
                features.append(context.volatility if context else 0.0)
            elif feature_name == "drawdown":
                features.append(context.risk_metrics.drawdown if context and context.risk_metrics else 0.0)
            elif feature_name == "var":
                features.append(context.risk_metrics.var if context and context.risk_metrics else 0.0)
            elif feature_name == "sharpe":
                features.append(context.risk_metrics.sharpe_ratio if context and context.risk_metrics else 0.0)
            elif feature_name == "momentum":
                features.append(context.technical_indicators.get("momentum", 0.0))
            elif feature_name == "rsi":
                features.append(context.technical_indicators.get("rsi", 50.0))
            elif feature_name == "macd":
                features.append(context.technical_indicators.get("macd", 0.0))
            elif feature_name == "bollinger":
                features.append(context.technical_indicators.get("bollinger_position", 0.0))
            elif feature_name == "volume_ratio":
                features.append(context.technical_indicators.get("volume_ratio", 1.0))
            elif feature_name == "sentiment":
                features.append(context.sentiment_score)
            elif feature_name == "funding_rate":
                features.append(context.funding_rate)
            else:
                features.append(0.0)
        
        return features
    
    async def _merge_decisions(self, primary: Decision, secondary: Optional[Decision]) -> Decision:
        """Fusionne deux décisions."""
        if not secondary:
            return primary
        
        # Si la décision secondaire a une confiance plus élevée
        if secondary.confidence > primary.confidence:
            # Fusionner les métadonnées
            merged_metadata = {
                **primary.metadata,
                "ml_merged": True,
                "primary_confidence": primary.confidence,
                "secondary_confidence": secondary.confidence
            }
            
            return Decision(
                decision_type=primary.decision_type if primary.confidence > 0.3 else secondary.decision_type,
                priority=primary.priority,
                confidence=max(primary.confidence, secondary.confidence),
                strategy=primary.strategy if primary.confidence > 0.3 else secondary.strategy,
                target_asset=primary.target_asset,
                target_amount=primary.target_amount,
                target_price=primary.target_price,
                stop_loss=primary.stop_loss,
                take_profit=primary.take_profit,
                reason=f"{primary.reason} [Merged with ML]",
                metadata=merged_metadata
            )
        
        return primary
    
    # ========== MÉTHODES DE VALIDATION ET EXÉCUTION ==========
    
    async def _validate_decision(self, decision: Decision) -> bool:
        """Valide une décision."""
        # Vérification de base
        if decision.decision_type == DecisionType.NONE:
            return False
        
        if decision.confidence < self._thresholds["min_confidence"]:
            return False
        
        # Vérification des paramètres
        if decision.target_amount is not None and decision.target_amount <= 0:
            return False
        
        if decision.target_price is not None and decision.target_price <= 0:
            return False
        
        if decision.stop_loss is not None and decision.stop_loss >= decision.target_price:
            return False
        
        if decision.take_profit is not None and decision.take_profit <= decision.target_price:
            return False
        
        # Vérification d'expiration
        if decision.expires_at and datetime.now(timezone.utc) > decision.expires_at:
            return False
        
        return True
    
    async def _simulate_decision(self, decision: Decision) -> Dict[str, Any]:
        """Simule les résultats d'une décision."""
        try:
            # Simulation basique de Monte Carlo
            num_simulations = 1000
            current_price = decision.target_price or 100.0
            volatility = 0.2
            
            # Génération des prix simulés
            returns = np.random.normal(0, volatility / np.sqrt(252), num_simulations)
            simulated_prices = current_price * np.exp(returns.cumsum())
            
            # Calcul du PnL simulé
            amount = decision.target_amount or 1000.0
            pnl = (simulated_prices - current_price) / current_price * amount
            
            # Métriques
            mean_pnl = np.mean(pnl)
            std_pnl = np.std(pnl)
            win_rate = np.mean(pnl > 0)
            max_loss = np.min(pnl)
            max_gain = np.max(pnl)
            
            # Viability
            viable = mean_pnl > 0 and win_rate > 0.4 and max_loss > -amount * 0.5
            
            return {
                "viable": viable,
                "mean_pnl": float(mean_pnl),
                "std_pnl": float(std_pnl),
                "win_rate": float(win_rate),
                "max_loss": float(max_loss),
                "max_gain": float(max_gain),
                "num_simulations": num_simulations,
                "simulated_prices": simulated_prices.tolist()[:100]  # Échantillon
            }
            
        except Exception as e:
            logger.error(f"Error in simulation: {e}")
            return {"viable": False, "error": str(e)}
    
    async def _execute_decision(self, decision: Decision) -> Dict[str, Any]:
        """Exécute une décision de hedging."""
        try:
            # Logique d'exécution
            # Dans un système réel, cela interagirait avec les brokers
            execution_result = {
                "success": True,
                "decision_id": decision.decision_id,
                "execution_time": time.time(),
                "details": {
                    "type": decision.decision_type.value,
                    "strategy": decision.strategy.value,
                    "asset": decision.target_asset,
                    "amount": decision.target_amount,
                    "price": decision.target_price,
                    "stop_loss": decision.stop_loss,
                    "take_profit": decision.take_profit
                }
            }
            
            logger.info(f"Decision executed: {decision.decision_id}")
            
            return execution_result
            
        except Exception as e:
            logger.error(f"Error in execution: {e}")
            return {"success": False, "error": str(e)}
    
    # ========== BOUCLES DE FOND ==========
    
    async def _model_update_loop(self) -> None:
        """Boucle de mise à jour des modèles ML."""
        while True:
            await asyncio.sleep(self.config["ml"]["retrain_interval"])
            
            if not self.config["ml"]["enabled"]:
                continue
            
            try:
                # Réentraînement incrémental
                await self._retrain_models()
                logger.info("ML models retrained")
            except Exception as e:
                logger.error(f"Error retraining models: {e}")
    
    async def _retrain_models(self) -> None:
        """Réentraîne les modèles ML incrémentalement."""
        # Placeholder pour l'entraînement
        pass
    
    async def _performance_monitor_loop(self) -> None:
        """Boucle de monitoring des performances."""
        while True:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des métriques
                total = self._performance_metrics["total_decisions"]
                if total > 0:
                    self._performance_metrics["avg_confidence"] = (
                        self._performance_metrics.get("avg_confidence", 0.0) * 0.9 +
                        statistics.mean([d.confidence for d in self._decision_history]) * 0.1
                    )
                
                # Nettoyage du cache
                current_time = datetime.now(timezone.utc)
                expired = []
                for key, decision in self._decision_cache.items():
                    if decision.expires_at and current_time > decision.expires_at:
                        expired.append(key)
                
                for key in expired:
                    del self._decision_cache[key]
                
            except Exception as e:
                logger.error(f"Error in performance monitor: {e}")


# ============== FACTORY ==============

class HedgeDecisionEngineFactory:
    """Factory pour créer des moteurs de décision de hedging."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        risk_engine: Optional[RiskEngine] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> HedgeDecisionEngine:
        """Crée un moteur de décision de hedging."""
        engine = HedgeDecisionEngine(
            data_manager=data_manager,
            risk_engine=risk_engine,
            config=config
        )
        await engine.start()
        return engine


# ============== EXPORT ==============

__all__ = [
    "DecisionType",
    "DecisionPriority",
    "DecisionConfidence",
    "MarketRegime",
    "HedgeStrategy",
    "Decision",
    "DecisionContext",
    "DecisionResult",
    "DecisionEngineInterface",
    "HedgeDecisionEngine",
    "HedgeDecisionEngineFactory"
]
