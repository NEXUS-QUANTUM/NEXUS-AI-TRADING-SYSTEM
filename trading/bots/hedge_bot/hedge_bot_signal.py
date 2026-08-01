# trading/bots/hedge_bot/hedge_bot_signal.py
# Advanced Signal Generation & Trading Signals Module for Hedge Bot
# NEXUS AI TRADING SYSTEM - Copyright © 2026 NEXUS QUANTUM LTD

"""
Hedge Bot Signal Module - Module avancé de génération de signaux et de trading pour le Hedge Bot.
Gère la génération de signaux de trading, l'analyse technique, l'agrégation de signaux,
la validation des signaux et la prise de décision pour les stratégies de hedging.
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
    Any, Dict, List, Optional, Set, Tuple, Union, Callable, AsyncIterator
)
import uuid
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import threading
import concurrent.futures

# Config du logging
from nexus.core.logging import get_logger
logger = get_logger("hedge_bot_signal")

# Import des types de données
from trading.bots.hedge_bot.hedge_bot_data_distributed import (
    DataType, DataRecord, DataStream, DistributedDataManager
)
from trading.bots.hedge_bot.hedge_bot_data_decision import (
    Decision, DecisionContext, DecisionType, HedgeStrategy
)


# ============== ENUMS & TYPES ==============

class SignalType(Enum):
    """Types de signaux."""
    BUY = "buy"
    SELL = "sell"
    NEUTRAL = "neutral"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"
    HEDGE = "hedge"
    UNWIND = "unwind"
    REBALANCE = "rebalance"
    EXIT = "exit"
    ENTER = "enter"


class SignalStrength(Enum):
    """Niveaux de force des signaux."""
    VERY_WEAK = 0.1
    WEAK = 0.25
    MODERATE = 0.5
    STRONG = 0.75
    VERY_STRONG = 0.9


class SignalSource(Enum):
    """Sources de signaux."""
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    SENTIMENT = "sentiment"
    AI = "ai"
    ML = "ml"
    PATTERN = "pattern"
    NEWSLETTER = "newsletter"
    SOCIAL = "social"
    ON_CHAIN = "on_chain"
    MACRO = "macro"
    CUSTOM = "custom"


class SignalAggregation(Enum):
    """Méthodes d'agrégation de signaux."""
    WEIGHTED = "weighted"
    VOTING = "voting"
    BAYESIAN = "bayesian"
    MAX = "max"
    MIN = "min"
    AVERAGE = "average"
    CONSENSUS = "consensus"


# ============== DATA MODELS ==============

@dataclass
class TradingSignal:
    """Signal de trading."""
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    signal_type: SignalType = SignalType.NEUTRAL
    strength: float = 0.0
    source: SignalSource = SignalSource.TECHNICAL
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    price: float = 0.0
    confidence: float = 0.0
    rationale: str = ""
    indicators: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    expiry: Optional[datetime] = None
    weight: float = 1.0
    validated: bool = False
    validation_score: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "strength": self.strength,
            "source": self.source.value,
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "indicators": self.indicators,
            "metadata": self.metadata,
            "tags": self.tags,
            "expiry": self.expiry.isoformat() if self.expiry else None,
            "weight": self.weight,
            "validated": self.validated,
            "validation_score": self.validation_score
        }


@dataclass
class SignalAggregator:
    """Agrégateur de signaux."""
    aggregator_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    method: SignalAggregation = SignalAggregation.WEIGHTED
    symbols: List[str] = field(default_factory=list)
    sources: List[SignalSource] = field(default_factory=list)
    min_signals: int = 2
    confidence_threshold: float = 0.5
    weights: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    active: bool = True


@dataclass
class SignalHistory:
    """Historique des signaux."""
    history_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    signals: List[TradingSignal] = field(default_factory=list)
    aggregated_signal: Optional[TradingSignal] = None
    accuracy: float = 0.0
    total_signals: int = 0
    correct_signals: int = 0
    period_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc) - timedelta(days=30))
    period_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============== INTERFACES ==============

class SignalEngineInterface(ABC):
    """Interface abstraite pour le moteur de signaux."""
    
    @abstractmethod
    async def generate_signal(self, symbol: str) -> TradingSignal:
        """Génère un signal de trading."""
        pass
    
    @abstractmethod
    async def aggregate_signals(self, signals: List[TradingSignal]) -> TradingSignal:
        """Agrège des signaux."""
        pass
    
    @abstractmethod
    async def validate_signal(self, signal: TradingSignal) -> float:
        """Valide un signal."""
        pass


# ============== IMPLÉMENTATION ==============

class SignalEngine(SignalEngineInterface):
    """
    Moteur de signaux avancé pour le Hedge Bot.
    Gère la génération de signaux, l'agrégation et la validation.
    """
    
    def __init__(
        self,
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.data_manager = data_manager
        self.config = config or self._default_config()
        
        # Gestion des signaux
        self._signals: Dict[str, TradingSignal] = {}
        self._signals_lock = threading.RLock()
        
        # Gestion des agrégateurs
        self._aggregators: Dict[str, SignalAggregator] = {}
        self._aggregators_lock = threading.RLock()
        
        # Gestion de l'historique
        self._history: Dict[str, SignalHistory] = {}
        self._history_lock = threading.RLock()
        
        # Cache des signaux
        self._signal_cache: Dict[str, TradingSignal] = {}
        self._cache_lock = threading.RLock()
        
        # Statistiques
        self._stats: Dict[str, Any] = {
            "signals_generated": 0,
            "signals_validated": 0,
            "signals_aggregated": 0,
            "buy_signals": 0,
            "sell_signals": 0,
            "neutral_signals": 0,
            "avg_confidence": 0.0,
            "accuracy": 0.0
        }
        
        # Thread pool
        self._compute_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.get("workers", 4)
        )
        
        # État
        self._is_running = False
        
        logger.info("SignalEngine initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "workers": 4,
            "min_confidence": 0.3,
            "default_source": SignalSource.TECHNICAL,
            "signal_expiry_hours": 24,
            "aggregation_threshold": 0.5,
            "validation_window": 10,
            "cache_size": 1000,
            "cache_ttl": 3600,
            "enable_cache": True,
            "auto_validate": True,
            "min_signals_for_aggregation": 2
        }
    
    async def start(self) -> None:
        """Démarre le moteur de signaux."""
        logger.info("SignalEngine starting...")
        self._is_running = True
        
        # Démarrage des tâches de fond
        asyncio.create_task(self._signal_expiry_loop())
        asyncio.create_task(self._cache_cleaner())
        asyncio.create_task(self._metrics_collector())
        
        logger.info("SignalEngine started")
    
    async def stop(self) -> None:
        """Arrête le moteur de signaux."""
        logger.info("SignalEngine stopping...")
        self._is_running = False
        self._compute_pool.shutdown(wait=True)
        logger.info("SignalEngine stopped")
    
    # ========== MÉTHODES PRINCIPALES ==========
    
    async def generate_signal(self, symbol: str) -> TradingSignal:
        """Génère un signal de trading."""
        self._stats["signals_generated"] += 1
        
        try:
            # Récupération des données de marché
            market_data = await self._get_market_data(symbol)
            
            # Analyse technique
            technical_signal = await self._analyze_technical(symbol, market_data)
            
            # Analyse de sentiment (simulée)
            sentiment_signal = await self._analyze_sentiment(symbol, market_data)
            
            # Analyse IA (simulée)
            ai_signal = await self._analyze_ai(symbol, market_data)
            
            # Agrégation des signaux
            signals = [technical_signal, sentiment_signal, ai_signal]
            aggregated = await self.aggregate_signals(signals)
            
            # Validation
            if self.config["auto_validate"]:
                aggregated.validation_score = await self.validate_signal(aggregated)
                aggregated.validated = aggregated.validation_score > 0.5
            
            # Stockage du signal
            with self._signals_lock:
                self._signals[aggregated.signal_id] = aggregated
                self._stats["avg_confidence"] = (
                    self._stats["avg_confidence"] * 0.9 + aggregated.confidence * 0.1
                )
            
            # Mise en cache
            if self.config["enable_cache"]:
                with self._cache_lock:
                    if len(self._signal_cache) < self.config["cache_size"]:
                        self._signal_cache[symbol] = aggregated
            
            logger.info(f"Signal generated for {symbol}: {aggregated.signal_type.value} "
                       f"confidence={aggregated.confidence:.2f}")
            
            return aggregated
            
        except Exception as e:
            logger.error(f"Signal generation error: {e}")
            raise
    
    async def aggregate_signals(self, signals: List[TradingSignal]) -> TradingSignal:
        """Agrège des signaux."""
        self._stats["signals_aggregated"] += 1
        
        if not signals:
            return TradingSignal(signal_type=SignalType.NEUTRAL, confidence=0)
        
        # Méthode de pondération
        weighted_sum = 0
        total_weight = 0
        
        for signal in signals:
            weight = signal.weight
            # Conversion du signal en valeur numérique
            signal_value = self._signal_to_value(signal.signal_type)
            weighted_sum += signal_value * weight * signal.confidence
            total_weight += weight * signal.confidence
        
        # Signal agrégé
        if total_weight > 0:
            avg_value = weighted_sum / total_weight
            signal_type = self._value_to_signal(avg_value)
            confidence = min(1.0, total_weight / len(signals))
        else:
            signal_type = SignalType.NEUTRAL
            confidence = 0
        
        # Création du signal agrégé
        aggregated = TradingSignal(
            symbol=signals[0].symbol if signals else "",
            signal_type=signal_type,
            strength=abs(avg_value) if total_weight > 0 else 0,
            source=SignalSource.CUSTOM,
            confidence=confidence,
            rationale="Aggregated from multiple sources",
            indicators={"num_signals": len(signals)},
            weight=1.0,
            tags=["aggregated"]
        )
        
        return aggregated
    
    async def validate_signal(self, signal: TradingSignal) -> float:
        """Valide un signal."""
        self._stats["signals_validated"] += 1
        
        # Simulation de validation
        # Dans un système réel, on comparerait avec les prix futurs
        
        # Validation basée sur la confiance
        base_score = signal.confidence
        
        # Validation basée sur les indicateurs
        indicator_score = 0.5
        if signal.indicators:
            indicator_score = sum(signal.indicators.values()) / len(signal.indicators)
        
        # Validation basée sur l'historique
        historical_score = await self._get_historical_accuracy(signal.symbol)
        
        # Score final
        validation_score = (base_score * 0.4 + indicator_score * 0.3 + historical_score * 0.3)
        
        return min(1.0, validation_score)
    
    # ========== MÉTHODES PRIVÉES - ANALYSE ==========
    
    async def _analyze_technical(self, symbol: str, data: pd.DataFrame) -> TradingSignal:
        """Analyse technique."""
        # Calcul des indicateurs
        rsi = self._calculate_rsi(data)
        macd = self._calculate_macd(data)
        bollinger = self._calculate_bollinger(data)
        volume = self._calculate_volume_signal(data)
        trend = self._calculate_trend(data)
        
        # Agrégation des indicateurs
        signals = []
        weights = []
        
        # RSI
        if rsi < 30:
            signals.append(1)
            weights.append(0.3)
        elif rsi > 70:
            signals.append(-1)
            weights.append(0.3)
        
        # MACD
        if macd > 0:
            signals.append(1)
            weights.append(0.2)
        else:
            signals.append(-1)
            weights.append(0.2)
        
        # Bollinger Bands
        if bollinger < -1:
            signals.append(1)
            weights.append(0.2)
        elif bollinger > 1:
            signals.append(-1)
            weights.append(0.2)
        
        # Volume
        signals.append(volume)
        weights.append(0.15)
        
        # Trend
        signals.append(trend)
        weights.append(0.15)
        
        # Signal final
        if signals:
            weighted_signal = sum(s * w for s, w in zip(signals, weights)) / sum(weights)
            signal_type = self._value_to_signal(weighted_signal)
            confidence = min(1.0, abs(weighted_signal) * 0.8 + 0.2)
        else:
            signal_type = SignalType.NEUTRAL
            confidence = 0.5
        
        return TradingSignal(
            symbol=symbol,
            signal_type=signal_type,
            strength=abs(weighted_signal) if signals else 0,
            source=SignalSource.TECHNICAL,
            price=data.iloc[-1].get("close", 0),
            confidence=confidence,
            rationale="Technical analysis",
            indicators={
                "rsi": rsi,
                "macd": macd,
                "bollinger": bollinger,
                "volume": volume,
                "trend": trend
            },
            tags=["technical"]
        )
    
    async def _analyze_sentiment(self, symbol: str, data: pd.DataFrame) -> TradingSignal:
        """Analyse de sentiment."""
        # Simulation de sentiment
        sentiment_score = np.random.uniform(-1, 1)
        
        signal_type = self._value_to_signal(sentiment_score)
        confidence = min(1.0, abs(sentiment_score) * 0.7 + 0.3)
        
        return TradingSignal(
            symbol=symbol,
            signal_type=signal_type,
            strength=abs(sentiment_score),
            source=SignalSource.SENTIMENT,
            price=data.iloc[-1].get("close", 0),
            confidence=confidence,
            rationale="Sentiment analysis",
            indicators={"sentiment_score": sentiment_score},
            tags=["sentiment"]
        )
    
    async def _analyze_ai(self, symbol: str, data: pd.DataFrame) -> TradingSignal:
        """Analyse IA."""
        # Simulation d'analyse IA
        ai_score = np.random.uniform(-1, 1)
        
        signal_type = self._value_to_signal(ai_score)
        confidence = min(1.0, abs(ai_score) * 0.6 + 0.4)
        
        return TradingSignal(
            symbol=symbol,
            signal_type=signal_type,
            strength=abs(ai_score),
            source=SignalSource.AI,
            price=data.iloc[-1].get("close", 0),
            confidence=confidence,
            rationale="AI model prediction",
            indicators={"ai_score": ai_score},
            tags=["ai"]
        )
    
    # ========== MÉTHODES PRIVÉES - INDICATEURS ==========
    
    def _calculate_rsi(self, data: pd.DataFrame, period: int = 14) -> float:
        """Calcule le RSI."""
        if len(data) < period + 1:
            return 50
        
        close = data["close"]
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        if loss.iloc[-1] == 0:
            return 100
        
        rs = gain.iloc[-1] / loss.iloc[-1]
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_macd(self, data: pd.DataFrame) -> float:
        """Calcule le MACD."""
        if len(data) < 26:
            return 0
        
        close = data["close"]
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        
        return macd.iloc[-1]
    
    def _calculate_bollinger(self, data: pd.DataFrame, period: int = 20) -> float:
        """Calcule la position Bollinger."""
        if len(data) < period:
            return 0
        
        close = data["close"]
        sma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        
        if upper.iloc[-1] == lower.iloc[-1]:
            return 0
        
        position = (close.iloc[-1] - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1])
        return (position - 0.5) * 2  # -1 à 1
    
    def _calculate_volume_signal(self, data: pd.DataFrame, period: int = 20) -> float:
        """Calcule le signal de volume."""
        if len(data) < period + 1:
            return 0
        
        volume = data["volume"]
        avg_volume = volume.rolling(window=period).mean()
        
        if avg_volume.iloc[-1] == 0:
            return 0
        
        volume_ratio = volume.iloc[-1] / avg_volume.iloc[-1]
        
        if volume_ratio > 2:
            return 0.5
        elif volume_ratio > 1.5:
            return 0.3
        elif volume_ratio < 0.5:
            return -0.5
        elif volume_ratio < 0.75:
            return -0.3
        else:
            return 0
    
    def _calculate_trend(self, data: pd.DataFrame, period: int = 50) -> float:
        """Calcule le signal de tendance."""
        if len(data) < period:
            return 0
        
        close = data["close"]
        sma = close.rolling(window=period).mean()
        
        if sma.iloc[-1] == 0:
            return 0
        
        trend = (close.iloc[-1] - sma.iloc[-1]) / sma.iloc[-1]
        return max(-1, min(1, trend * 10))
    
    # ========== MÉTHODES PRIVÉES - UTILITAIRES ==========
    
    def _signal_to_value(self, signal_type: SignalType) -> float:
        """Convertit un signal en valeur numérique."""
        values = {
            SignalType.STRONG_BUY: 1.0,
            SignalType.BUY: 0.7,
            SignalType.ENTER: 0.6,
            SignalType.HEDGE: 0.5,
            SignalType.REBALANCE: 0.3,
            SignalType.NEUTRAL: 0.0,
            SignalType.UNWIND: -0.3,
            SignalType.EXIT: -0.6,
            SignalType.SELL: -0.7,
            SignalType.STRONG_SELL: -1.0
        }
        return values.get(signal_type, 0)
    
    def _value_to_signal(self, value: float) -> SignalType:
        """Convertit une valeur en signal."""
        if value >= 0.8:
            return SignalType.STRONG_BUY
        elif value >= 0.6:
            return SignalType.BUY
        elif value >= 0.3:
            return SignalType.ENTER
        elif value >= 0.1:
            return SignalType.HEDGE
        elif value > -0.1:
            return SignalType.NEUTRAL
        elif value > -0.3:
            return SignalType.UNWIND
        elif value > -0.6:
            return SignalType.EXIT
        elif value > -0.8:
            return SignalType.SELL
        else:
            return SignalType.STRONG_SELL
    
    async def _get_market_data(self, symbol: str) -> pd.DataFrame:
        """Récupère les données de marché."""
        if self.data_manager:
            data = await self.data_manager.retrieve(
                f"market:{symbol}:history",
                DataType.HISTORICAL
            )
            if data:
                return pd.DataFrame(data)
        
        # Données par défaut
        dates = pd.date_range(end=datetime.now(timezone.utc), periods=100, freq="1H")
        prices = 100 + np.cumsum(np.random.randn(100))
        volumes = np.random.randint(100, 1000, 100)
        
        return pd.DataFrame({
            "timestamp": dates,
            "close": prices,
            "volume": volumes
        })
    
    async def _get_historical_accuracy(self, symbol: str) -> float:
        """Récupère l'exactitude historique des signaux."""
        with self._history_lock:
            history = self._history.get(symbol)
            if history:
                return history.accuracy
        
        return 0.5  # Valeur par défaut
    
    async def _signal_expiry_loop(self) -> None:
        """Boucle de gestion de l'expiration des signaux."""
        while self._is_running:
            await asyncio.sleep(3600)  # 1 heure
            
            try:
                now = datetime.now(timezone.utc)
                with self._signals_lock:
                    expired = [
                        sid for sid, signal in self._signals.items()
                        if signal.expiry and signal.expiry < now
                    ]
                    for sid in expired:
                        del self._signals[sid]
                
                if expired:
                    logger.debug(f"Cleaned up {len(expired)} expired signals")
                
            except Exception as e:
                logger.error(f"Signal expiry error: {e}")
    
    async def _cache_cleaner(self) -> None:
        """Nettoie le cache périodiquement."""
        while self._is_running:
            await asyncio.sleep(300)  # 5 minutes
            
            try:
                with self._cache_lock:
                    if len(self._signal_cache) > self.config["cache_size"]:
                        keys = list(self._signal_cache.keys())
                        for key in keys[:len(self._signal_cache) - self.config["cache_size"]]:
                            del self._signal_cache[key]
                
            except Exception as e:
                logger.error(f"Cache cleaner error: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collecte les métriques."""
        while self._is_running:
            await asyncio.sleep(60)
            
            try:
                # Mise à jour des statistiques
                with self._signals_lock:
                    self._stats["total_signals"] = len(self._signals)
                    buy_count = len([s for s in self._signals.values() if s.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]])
                    sell_count = len([s for s in self._signals.values() if s.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]])
                    neutral_count = len([s for s in self._signals.values() if s.signal_type == SignalType.NEUTRAL])
                    
                    self._stats["buy_signals"] = buy_count
                    self._stats["sell_signals"] = sell_count
                    self._stats["neutral_signals"] = neutral_count
                
                # Stockage des métriques
                if self.data_manager:
                    await self.data_manager.store(
                        "signal:metrics",
                        self._stats,
                        DataType.METRICS
                    )
                
            except Exception as e:
                logger.error(f"Metrics collector error: {e}")
    
    # ========== MÉTHODES PUBLIQUES ==========
    
    async def get_signal(self, signal_id: str) -> Optional[TradingSignal]:
        """Récupère un signal."""
        with self._signals_lock:
            return self._signals.get(signal_id)
    
    async def get_signals(
        self,
        symbol: Optional[str] = None,
        signal_type: Optional[SignalType] = None
    ) -> List[TradingSignal]:
        """Récupère les signaux."""
        with self._signals_lock:
            signals = list(self._signals.values())
            if symbol:
                signals = [s for s in signals if s.symbol == symbol]
            if signal_type:
                signals = [s for s in signals if s.signal_type == signal_type]
            return sorted(signals, key=lambda s: s.timestamp, reverse=True)
    
    async def create_aggregator(self, config: Dict[str, Any]) -> SignalAggregator:
        """Crée un agrégateur de signaux."""
        aggregator = SignalAggregator(
            name=config.get("name", f"Aggregator_{uuid.uuid4().hex[:8]}"),
            method=SignalAggregation(config.get("method", "weighted")),
            symbols=config.get("symbols", []),
            sources=[SignalSource(s) for s in config.get("sources", [])],
            min_signals=config.get("min_signals", 2),
            confidence_threshold=config.get("confidence_threshold", 0.5),
            weights=config.get("weights", {}),
            metadata=config.get("metadata", {}),
            tags=config.get("tags", [])
        )
        
        with self._aggregators_lock:
            self._aggregators[aggregator.aggregator_id] = aggregator
        
        logger.info(f"Signal aggregator created: {aggregator.name}")
        return aggregator
    
    async def get_aggregator(self, aggregator_id: str) -> Optional[SignalAggregator]:
        """Récupère un agrégateur."""
        with self._aggregators_lock:
            return self._aggregators.get(aggregator_id)
    
    async def get_aggregators(self) -> List[SignalAggregator]:
        """Récupère les agrégateurs."""
        with self._aggregators_lock:
            return list(self._aggregators.values())
    
    async def aggregate_with_config(
        self,
        aggregator_id: str,
        signals: List[TradingSignal]
    ) -> Optional[TradingSignal]:
        """Agrège des signaux avec un agrégateur configuré."""
        aggregator = await self.get_aggregator(aggregator_id)
        if not aggregator:
            return None
        
        # Filtrage des signaux
        filtered = [
            s for s in signals
            if not aggregator.symbols or s.symbol in aggregator.symbols
            if not aggregator.sources or s.source in aggregator.sources
            if s.confidence >= aggregator.confidence_threshold
        ]
        
        if len(filtered) < aggregator.min_signals:
            return None
        
        # Agrégation
        return await self.aggregate_signals(filtered)
    
    def get_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques."""
        with self._signals_lock:
            self._stats["total_signals"] = len(self._signals)
        with self._aggregators_lock:
            self._stats["total_aggregators"] = len(self._aggregators)
        
        return self._stats.copy()


# ============== SIGNAL CONFIRMATION ==============

class SignalConfirmer:
    """
    Confirmateur de signaux.
    Valide et confirme les signaux avant exécution.
    """
    
    def __init__(self, engine: SignalEngine, config: Optional[Dict[str, Any]] = None):
        self.engine = engine
        self.config = config or self._default_config()
        self._confirmed_signals: Dict[str, Dict[str, Any]] = {}
        self._confirm_lock = threading.RLock()
        
        logger.info("SignalConfirmer initialized")
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "confirmation_count": 2,
            "time_window": 300,  # 5 minutes
            "min_confidence": 0.6,
            "require_trend_confirmation": True,
            "require_volume_confirmation": True
        }
    
    async def confirm_signal(self, signal: TradingSignal) -> bool:
        """Confirme un signal."""
        # Vérification de la confiance
        if signal.confidence < self.config["min_confidence"]:
            return False
        
        # Récupération des signaux récents
        recent_signals = await self.engine.get_signals(
            symbol=signal.symbol,
            signal_type=signal.signal_type
        )
        
        # Filtrage par fenêtre temporelle
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.config["time_window"])
        recent = [s for s in recent_signals if s.timestamp > cutoff]
        
        # Vérification du nombre de confirmations
        if len(recent) < self.config["confirmation_count"]:
            return False
        
        # Stockage de la confirmation
        with self._confirm_lock:
            self._confirmed_signals[signal.signal_id] = {
                "signal": signal,
                "confirmed_at": datetime.now(timezone.utc),
                "confirmation_count": len(recent)
            }
        
        return True
    
    async def get_confirmed(self, signal_id: str) -> Optional[Dict[str, Any]]:
        """Récupère une confirmation."""
        with self._confirm_lock:
            return self._confirmed_signals.get(signal_id)


# ============== FACTORY ==============

class SignalFactory:
    """Factory pour créer des composants de signaux."""
    
    @staticmethod
    async def create_engine(
        data_manager: Optional[DistributedDataManager] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> SignalEngine:
        """Crée un moteur de signaux."""
        engine = SignalEngine(
            data_manager=data_manager,
            config=config
        )
        await engine.start()
        return engine
    
    @staticmethod
    def create_confirmer(engine: SignalEngine) -> SignalConfirmer:
        """Crée un confirmateur de signaux."""
        return SignalConfirmer(engine)


# ============== EXPORT ==============

__all__ = [
    "SignalType",
    "SignalStrength",
    "SignalSource",
    "SignalAggregation",
    "TradingSignal",
    "SignalAggregator",
    "SignalHistory",
    "SignalEngineInterface",
    "SignalEngine",
    "SignalConfirmer",
    "SignalFactory"
]
