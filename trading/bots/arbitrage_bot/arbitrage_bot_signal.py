"""
NEXUS AI TRADING SYSTEM - ARBITRAGE BOT SIGNAL MODULE
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

Module de génération et gestion de signaux pour le bot d'arbitrage.
Génération de signaux basée sur indicateurs techniques, prix, et opportunités.

Version: 3.0.0
CEO: Dr X... - Majority Shareholder
"""

import asyncio
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID, uuid4

import aiohttp
import numpy as np
import pandas as pd
from scipy import stats

from ..arbitrage_bot import (
    ArbitrageBot,
    ArbitrageOpportunity,
    ArbitrageConfig,
    ExchangeType,
    ArbitrageType,
    ArbitrageStatus
)

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS ET DATACLASSES
# ============================================================================

class SignalType(Enum):
    """Types de signaux."""
    BUY = "buy"
    SELL = "sell"
    STRONG_BUY = "strong_buy"
    STRONG_SELL = "strong_sell"
    NEUTRAL = "neutral"
    EXIT = "exit"
    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"


class SignalSource(Enum):
    """Sources de signaux."""
    TECHNICAL = "technical"
    PRICE_ACTION = "price_action"
    VOLUME = "volume"
    SENTIMENT = "sentiment"
    FUNDAMENTAL = "fundamental"
    NEWS = "news"
    SOCIAL = "social"
    ON_CHAIN = "on_chain"
    ARBITRAGE = "arbitrage"
    ML = "ml"


class SignalStrength(Enum):
    """Force du signal."""
    VERY_WEAK = 1
    WEAK = 2
    MODERATE = 3
    STRONG = 4
    VERY_STRONG = 5


@dataclass
class Signal:
    """Signal de trading."""
    signal_id: UUID
    bot_id: UUID
    symbol: str
    exchange: ExchangeType
    signal_type: SignalType
    source: SignalSource
    strength: SignalStrength
    price: Decimal
    confidence: float  # 0-1
    reason: str
    indicators: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    executed_price: Optional[Decimal] = None
    status: str = "pending"  # pending, executed, expired, cancelled

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "signal_id": str(self.signal_id),
            "bot_id": str(self.bot_id),
            "symbol": self.symbol,
            "exchange": self.exchange.value,
            "signal_type": self.signal_type.value,
            "source": self.source.value,
            "strength": self.strength.value,
            "price": str(self.price),
            "confidence": self.confidence,
            "reason": self.reason,
            "indicators": self.indicators,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "executed_price": str(self.executed_price) if self.executed_price else None,
            "status": self.status
        }


@dataclass
class IndicatorConfig:
    """Configuration d'indicateur."""
    name: str
    type: str  # "trend", "momentum", "volatility", "volume"
    params: Dict[str, Any] = field(default_factory=dict)
    threshold: Optional[float] = None
    weight: float = 1.0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SignalAggregation:
    """Agrégation de signaux."""
    aggregation_id: UUID
    bot_id: UUID
    symbol: str
    exchange: ExchangeType
    signals: List[Signal]
    aggregated_type: SignalType
    aggregated_strength: SignalStrength
    aggregated_confidence: float
    vote_counts: Dict[str, int]
    score: float
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "aggregation_id": str(self.aggregation_id),
            "bot_id": str(self.bot_id),
            "symbol": self.symbol,
            "exchange": self.exchange.value,
            "signals": [s.to_dict() for s in self.signals],
            "aggregated_type": self.aggregated_type.value,
            "aggregated_strength": self.aggregated_strength.value,
            "aggregated_confidence": self.aggregated_confidence,
            "vote_counts": self.vote_counts,
            "score": self.score,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }


# ============================================================================
# CLASSE SIGNAL GENERATOR
# ============================================================================

class ArbitrageBotSignalGenerator:
    """
    Générateur de signaux pour le bot d'arbitrage.
    """

    # Indicateurs techniques par défaut
    DEFAULT_INDICATORS = {
        "rsi": IndicatorConfig(
            name="rsi",
            type="momentum",
            params={"period": 14, "overbought": 70, "oversold": 30},
            weight=1.0
        ),
        "macd": IndicatorConfig(
            name="macd",
            type="momentum",
            params={"fast": 12, "slow": 26, "signal": 9},
            weight=1.0
        ),
        "bollinger": IndicatorConfig(
            name="bollinger",
            type="volatility",
            params={"period": 20, "std_dev": 2},
            weight=0.8
        ),
        "sma": IndicatorConfig(
            name="sma",
            type="trend",
            params={"short": 20, "long": 50},
            weight=0.8
        ),
        "ema": IndicatorConfig(
            name="ema",
            type="trend",
            params={"short": 12, "long": 26},
            weight=0.8
        ),
        "volume": IndicatorConfig(
            name="volume",
            type="volume",
            params={"period": 20, "threshold": 1.5},
            weight=0.7
        ),
        "stochastic": IndicatorConfig(
            name="stochastic",
            type="momentum",
            params={"k": 14, "d": 3},
            weight=0.6
        ),
        "ichimoku": IndicatorConfig(
            name="ichimoku",
            type="trend",
            params={"tenkan": 9, "kijun": 26, "senkou": 52},
            weight=0.6
        )
    }

    # Seuils de confiance
    CONFIDENCE_THRESHOLDS = {
        SignalStrength.VERY_WEAK: 0.2,
        SignalStrength.WEAK: 0.4,
        SignalStrength.MODERATE: 0.6,
        SignalStrength.STRONG: 0.8,
        SignalStrength.VERY_STRONG: 0.9
    }

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        api_keys: Optional[Dict[str, str]] = None,
        indicator_configs: Optional[Dict[str, IndicatorConfig]] = None
    ):
        """
        Initialise le générateur de signaux.

        Args:
            redis_client: Client Redis pour le cache
            api_keys: Clés API pour les services externes
            indicator_configs: Configurations des indicateurs
        """
        self.redis = redis_client
        self.api_keys = api_keys or {}
        self.indicator_configs = indicator_configs or self.DEFAULT_INDICATORS.copy()
        
        # Cache
        self._signal_cache: Dict[UUID, Signal] = {}
        self._aggregation_cache: Dict[UUID, SignalAggregation] = {}
        self._price_history: Dict[str, List[Decimal]] = {}
        self._indicator_cache: Dict[str, Dict[str, Any]] = {}
        
        # Métriques
        self._metrics = {
            "total_signals": 0,
            "total_aggregations": 0,
            "signals_by_type": {},
            "signals_by_source": {},
            "signals_by_strength": {},
            "executed_signals": 0,
            "accuracy_rate": 0.0,
            "last_signal": None
        }

        logger.info("ArbitrageBotSignalGenerator initialisé avec succès")

    # ========================================================================
    # GÉNÉRATION DE SIGNAUX
    # ========================================================================

    async def generate_signals(
        self,
        bot: ArbitrageBot,
        symbol: str,
        exchange: ExchangeType,
        price_data: List[Dict[str, Any]],
        use_indicators: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> List[Signal]:
        """
        Génère des signaux pour un symbole.

        Args:
            bot: Bot
            symbol: Symbole
            exchange: Exchange
            price_data: Données de prix
            use_indicators: Indicateurs à utiliser
            metadata: Métadonnées

        Returns:
            Liste des signaux générés
        """
        try:
            if len(price_data) < 50:
                logger.warning(f"Données insuffisantes pour {symbol}")
                return []

            # Conversion des données
            df = self._prepare_dataframe(price_data)
            
            # Calcul des indicateurs
            indicators = {}
            for name, config in self.indicator_configs.items():
                if use_indicators and name not in use_indicators:
                    continue
                if not config.enabled:
                    continue
                
                indicator_value = await self._calculate_indicator(df, config)
                if indicator_value is not None:
                    indicators[name] = indicator_value

            # Génération des signaux
            signals = []
            current_price = Decimal(str(df['close'].iloc[-1]))

            # Signaux techniques
            for name, value in indicators.items():
                signal = await self._generate_indicator_signal(
                    bot_id=bot.config.bot_id,
                    symbol=symbol,
                    exchange=exchange,
                    indicator_name=name,
                    indicator_value=value,
                    current_price=current_price,
                    indicator_config=self.indicator_configs.get(name),
                    metadata=metadata
                )
                if signal:
                    signals.append(signal)
                    self._metrics["total_signals"] += 1
                    self._metrics["last_signal"] = datetime.now().isoformat()

            # Signal d'arbitrage
            arbitrage_signal = await self._generate_arbitrage_signal(
                bot=bot,
                symbol=symbol,
                exchange=exchange,
                price_data=price_data,
                current_price=current_price
            )
            if arbitrage_signal:
                signals.append(arbitrage_signal)
                self._metrics["total_signals"] += 1

            # Signal de volume
            volume_signal = await self._generate_volume_signal(
                bot_id=bot.config.bot_id,
                symbol=symbol,
                exchange=exchange,
                df=df,
                current_price=current_price
            )
            if volume_signal:
                signals.append(volume_signal)
                self._metrics["total_signals"] += 1

            # Mise à jour des métriques
            for signal in signals:
                signal_type = signal.signal_type.value
                if signal_type not in self._metrics["signals_by_type"]:
                    self._metrics["signals_by_type"][signal_type] = 0
                self._metrics["signals_by_type"][signal_type] += 1

                source = signal.source.value
                if source not in self._metrics["signals_by_source"]:
                    self._metrics["signals_by_source"][source] = 0
                self._metrics["signals_by_source"][source] += 1

                strength = signal.strength.value
                if strength not in self._metrics["signals_by_strength"]:
                    self._metrics["signals_by_strength"][strength] = 0
                self._metrics["signals_by_strength"][strength] += 1

            # Mise en cache
            for signal in signals:
                self._signal_cache[signal.signal_id] = signal

            # Sauvegarde dans Redis
            if self.redis:
                await self._save_signals(signals)

            return signals

        except Exception as e:
            logger.error(f"Erreur lors de la génération des signaux: {e}")
            return []

    async def _generate_indicator_signal(
        self,
        bot_id: UUID,
        symbol: str,
        exchange: ExchangeType,
        indicator_name: str,
        indicator_value: Any,
        current_price: Decimal,
        indicator_config: Optional[IndicatorConfig] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[Signal]:
        """
        Génère un signal basé sur un indicateur.

        Args:
            bot_id: ID du bot
            symbol: Symbole
            exchange: Exchange
            indicator_name: Nom de l'indicateur
            indicator_value: Valeur de l'indicateur
            current_price: Prix actuel
            indicator_config: Configuration de l'indicateur
            metadata: Métadonnées

        Returns:
            Signal généré
        """
        try:
            if not indicator_config:
                return None

            signal_type = SignalType.NEUTRAL
            reason = ""
            confidence = 0.5

            if indicator_name == "rsi":
                rsi = indicator_value
                if rsi < 30:
                    signal_type = SignalType.BUY
                    reason = f"RSI en zone de survente ({rsi:.2f})"
                    confidence = 0.7
                elif rsi > 70:
                    signal_type = SignalType.SELL
                    reason = f"RSI en zone de surachat ({rsi:.2f})"
                    confidence = 0.7

            elif indicator_name == "macd":
                macd_line, signal_line, histogram = indicator_value
                if macd_line > signal_line and histogram > 0:
                    signal_type = SignalType.BUY
                    reason = "Crossing MACD haussier"
                    confidence = 0.6
                elif macd_line < signal_line and histogram < 0:
                    signal_type = SignalType.SELL
                    reason = "Crossing MACD baissier"
                    confidence = 0.6

            elif indicator_name == "bollinger":
                upper, middle, lower = indicator_value
                if current_price <= lower:
                    signal_type = SignalType.BUY
                    reason = "Prix en bas de la bande de Bollinger"
                    confidence = 0.65
                elif current_price >= upper:
                    signal_type = SignalType.SELL
                    reason = "Prix en haut de la bande de Bollinger"
                    confidence = 0.65

            elif indicator_name == "sma":
                short_sma, long_sma = indicator_value
                if short_sma > long_sma:
                    signal_type = SignalType.BUY
                    reason = "Croisement SMA haussier"
                    confidence = 0.55
                elif short_sma < long_sma:
                    signal_type = SignalType.SELL
                    reason = "Croisement SMA baissier"
                    confidence = 0.55

            elif indicator_name == "stochastic":
                k, d = indicator_value
                if k < 20 and d < 20:
                    signal_type = SignalType.BUY
                    reason = f"Stochastic en zone de survente (K={k:.2f}, D={d:.2f})"
                    confidence = 0.6
                elif k > 80 and d > 80:
                    signal_type = SignalType.SELL
                    reason = f"Stochastic en zone de surachat (K={k:.2f}, D={d:.2f})"
                    confidence = 0.6

            else:
                return None

            if signal_type == SignalType.NEUTRAL:
                return None

            # Ajustement de la confiance
            strength = self._calculate_strength(confidence)

            return Signal(
                signal_id=uuid4(),
                bot_id=bot_id,
                symbol=symbol,
                exchange=exchange,
                signal_type=signal_type,
                source=SignalSource.TECHNICAL,
                strength=strength,
                price=current_price,
                confidence=confidence,
                reason=reason,
                indicators={indicator_name: indicator_value},
                metadata=metadata or {},
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=1)
            )

        except Exception as e:
            logger.error(f"Erreur lors de la génération du signal indicateur: {e}")
            return None

    async def _generate_arbitrage_signal(
        self,
        bot: ArbitrageBot,
        symbol: str,
        exchange: ExchangeType,
        price_data: List[Dict[str, Any]],
        current_price: Decimal
    ) -> Optional[Signal]:
        """
        Génère un signal d'arbitrage.

        Args:
            bot: Bot
            symbol: Symbole
            exchange: Exchange
            price_data: Données de prix
            current_price: Prix actuel

        Returns:
            Signal d'arbitrage
        """
        try:
            # Récupération des opportunités
            opportunities = bot.find_arbitrage_opportunities(symbol)
            
            if not opportunities:
                return None

            # Meilleure opportunité
            best_opp = max(opportunities, key=lambda x: x.profit_percent)
            
            if best_opp.profit_percent < bot.config.min_profit_threshold:
                return None

            return Signal(
                signal_id=uuid4(),
                bot_id=bot.config.bot_id,
                symbol=symbol,
                exchange=exchange,
                signal_type=SignalType.BUY if best_opp.buy_exchange == exchange else SignalType.SELL,
                source=SignalSource.ARBITRAGE,
                strength=SignalStrength.STRONG,
                price=current_price,
                confidence=min(best_opp.profit_percent / 0.05, 1.0),
                reason=f"Opportunité d'arbitrage détectée: {best_opp.profit_percent*100:.2f}%",
                indicators={
                    "profit_percent": best_opp.profit_percent,
                    "buy_exchange": best_opp.buy_exchange.value,
                    "sell_exchange": best_opp.sell_exchange.value
                },
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=5)
            )

        except Exception as e:
            logger.error(f"Erreur lors de la génération du signal d'arbitrage: {e}")
            return None

    async def _generate_volume_signal(
        self,
        bot_id: UUID,
        symbol: str,
        exchange: ExchangeType,
        df: pd.DataFrame,
        current_price: Decimal
    ) -> Optional[Signal]:
        """
        Génère un signal basé sur le volume.

        Args:
            bot_id: ID du bot
            symbol: Symbole
            exchange: Exchange
            df: DataFrame des prix
            current_price: Prix actuel

        Returns:
            Signal de volume
        """
        try:
            volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].tail(20).mean()
            
            if volume > avg_volume * 1.5:
                return Signal(
                    signal_id=uuid4(),
                    bot_id=bot_id,
                    symbol=symbol,
                    exchange=exchange,
                    signal_type=SignalType.BUY if df['close'].iloc[-1] > df['close'].iloc[-2] else SignalType.SELL,
                    source=SignalSource.VOLUME,
                    strength=SignalStrength.MODERATE,
                    price=current_price,
                    confidence=0.6,
                    reason=f"Volume élevé: {volume/avg_volume:.2f}x la moyenne",
                    indicators={
                        "volume": volume,
                        "avg_volume": avg_volume,
                        "ratio": volume / avg_volume
                    },
                    created_at=datetime.now(),
                    expires_at=datetime.now() + timedelta(hours=1)
                )

            return None

        except Exception as e:
            logger.error(f"Erreur lors de la génération du signal de volume: {e}")
            return None

    # ========================================================================
    # CALCUL DES INDICATEURS
    # ========================================================================

    async def _calculate_indicator(
        self,
        df: pd.DataFrame,
        config: IndicatorConfig
    ) -> Optional[Any]:
        """
        Calcule un indicateur technique.

        Args:
            df: DataFrame des prix
            config: Configuration de l'indicateur

        Returns:
            Valeur de l'indicateur
        """
        try:
            if config.name == "rsi":
                return self._calculate_rsi(df, config.params.get("period", 14))
            elif config.name == "macd":
                return self._calculate_macd(df, config.params.get("fast", 12), config.params.get("slow", 26), config.params.get("signal", 9))
            elif config.name == "bollinger":
                return self._calculate_bollinger(df, config.params.get("period", 20), config.params.get("std_dev", 2))
            elif config.name == "sma":
                return self._calculate_sma(df, config.params.get("short", 20), config.params.get("long", 50))
            elif config.name == "ema":
                return self._calculate_ema(df, config.params.get("short", 12), config.params.get("long", 26))
            elif config.name == "stochastic":
                return self._calculate_stochastic(df, config.params.get("k", 14), config.params.get("d", 3))
            elif config.name == "ichimoku":
                return self._calculate_ichimoku(df, config.params.get("tenkan", 9), config.params.get("kijun", 26), config.params.get("senkou", 52))
            else:
                return None

        except Exception as e:
            logger.error(f"Erreur lors du calcul de l'indicateur {config.name}: {e}")
            return None

    def _calculate_rsi(self, df: pd.DataFrame, period: int) -> float:
        """Calcule le RSI."""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    def _calculate_macd(self, df: pd.DataFrame, fast: int, slow: int, signal: int) -> Tuple[float, float, float]:
        """Calcule le MACD."""
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]

    def _calculate_bollinger(self, df: pd.DataFrame, period: int, std_dev: int) -> Tuple[float, float, float]:
        """Calcule les bandes de Bollinger."""
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper.iloc[-1], sma.iloc[-1], lower.iloc[-1]

    def _calculate_sma(self, df: pd.DataFrame, short: int, long: int) -> Tuple[float, float]:
        """Calcule les SMA."""
        sma_short = df['close'].rolling(window=short).mean()
        sma_long = df['close'].rolling(window=long).mean()
        return sma_short.iloc[-1], sma_long.iloc[-1]

    def _calculate_ema(self, df: pd.DataFrame, short: int, long: int) -> Tuple[float, float]:
        """Calcule les EMA."""
        ema_short = df['close'].ewm(span=short, adjust=False).mean()
        ema_long = df['close'].ewm(span=long, adjust=False).mean()
        return ema_short.iloc[-1], ema_long.iloc[-1]

    def _calculate_stochastic(self, df: pd.DataFrame, k_period: int, d_period: int) -> Tuple[float, float]:
        """Calcule le Stochastic."""
        low_min = df['low'].rolling(window=k_period).min()
        high_max = df['high'].rolling(window=k_period).max()
        k = 100 * ((df['close'] - low_min) / (high_max - low_min))
        d = k.rolling(window=d_period).mean()
        return k.iloc[-1], d.iloc[-1]

    def _calculate_ichimoku(self, df: pd.DataFrame, tenkan: int, kijun: int, senkou: int) -> Dict[str, Any]:
        """Calcule l'Ichimoku."""
        tenkan_sen = (df['high'].rolling(window=tenkan).max() + df['low'].rolling(window=tenkan).min()) / 2
        kijun_sen = (df['high'].rolling(window=kijun).max() + df['low'].rolling(window=kijun).min()) / 2
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun)
        senkou_span_b = ((df['high'].rolling(window=senkou).max() + df['low'].rolling(window=senkou).min()) / 2).shift(kijun)
        
        return {
            "tenkan_sen": tenkan_sen.iloc[-1],
            "kijun_sen": kijun_sen.iloc[-1],
            "senkou_span_a": senkou_span_a.iloc[-1],
            "senkou_span_b": senkou_span_b.iloc[-1]
        }

    # ========================================================================
    # AGRÉGATION DE SIGNAUX
    # ========================================================================

    async def aggregate_signals(
        self,
        bot_id: UUID,
        symbol: str,
        exchange: ExchangeType,
        signals: List[Signal],
        metadata: Optional[Dict] = None
    ) -> SignalAggregation:
        """
        Agrège plusieurs signaux en un seul.

        Args:
            bot_id: ID du bot
            symbol: Symbole
            exchange: Exchange
            signals: Liste des signaux
            metadata: Métadonnées

        Returns:
            Agrégation de signaux
        """
        try:
            if not signals:
                raise ValueError("Aucun signal à agréger")

            # Comptage des votes
            votes = {}
            total_confidence = 0.0
            total_strength = 0.0

            for signal in signals:
                signal_type = signal.signal_type.value
                if signal_type not in votes:
                    votes[signal_type] = 0
                votes[signal_type] += 1
                
                total_confidence += signal.confidence
                total_strength += signal.strength.value

            # Détermination du type majoritaire
            aggregated_type = SignalType.NEUTRAL
            max_votes = 0
            
            for signal_type, count in votes.items():
                if count > max_votes:
                    max_votes = count
                    aggregated_type = SignalType(signal_type)

            # Calcul de la force et confiance agrégées
            avg_confidence = total_confidence / len(signals)
            avg_strength = total_strength / len(signals)
            
            aggregated_strength = self._calculate_strength(avg_confidence)
            
            # Calcul du score
            score = avg_confidence * (avg_strength / 5)

            # Création de l'agrégation
            aggregation = SignalAggregation(
                aggregation_id=uuid4(),
                bot_id=bot_id,
                symbol=symbol,
                exchange=exchange,
                signals=signals,
                aggregated_type=aggregated_type,
                aggregated_strength=aggregated_strength,
                aggregated_confidence=avg_confidence,
                vote_counts=votes,
                score=score,
                metadata=metadata or {}
            )

            self._aggregation_cache[aggregation.aggregation_id] = aggregation
            self._metrics["total_aggregations"] += 1

            return aggregation

        except Exception as e:
            logger.error(f"Erreur lors de l'agrégation des signaux: {e}")
            raise

    # ========================================================================
    # MÉTHODES UTILITAIRES
    # ========================================================================

    def _calculate_strength(self, confidence: float) -> SignalStrength:
        """
        Calcule la force du signal à partir de la confiance.

        Args:
            confidence: Niveau de confiance (0-1)

        Returns:
            Force du signal
        """
        if confidence >= 0.9:
            return SignalStrength.VERY_STRONG
        elif confidence >= 0.7:
            return SignalStrength.STRONG
        elif confidence >= 0.5:
            return SignalStrength.MODERATE
        elif confidence >= 0.3:
            return SignalStrength.WEAK
        else:
            return SignalStrength.VERY_WEAK

    def _prepare_dataframe(self, price_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Prépare un DataFrame à partir des données de prix.

        Args:
            price_data: Données de prix

        Returns:
            DataFrame
        """
        df = pd.DataFrame(price_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        # S'assurer que les colonnes nécessaires existent
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in df.columns:
                df[col] = df['close']  # Fallback
        
        return df

    # ========================================================================
    # MÉTHODES DE STOCKAGE
    # ========================================================================

    async def _save_signals(self, signals: List[Signal]) -> None:
        """
        Sauvegarde les signaux dans Redis.

        Args:
            signals: Liste des signaux
        """
        try:
            for signal in signals:
                key = f"signal:{signal.signal_id}"
                await self.redis.setex(
                    key,
                    86400 * 7,  # 7 jours
                    json.dumps(signal.to_dict())
                )

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des signaux: {e}")

    # ========================================================================
    # MÉTHODES DE RÉCUPÉRATION
    # ========================================================================

    async def get_signal(
        self,
        signal_id: UUID
    ) -> Optional[Signal]:
        """
        Récupère un signal.

        Args:
            signal_id: ID du signal

        Returns:
            Signal ou None
        """
        return self._signal_cache.get(signal_id)

    async def get_signals(
        self,
        bot_id: UUID,
        symbol: Optional[str] = None,
        exchange: Optional[ExchangeType] = None,
        signal_type: Optional[SignalType] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Signal]:
        """
        Récupère les signaux.

        Args:
            bot_id: ID du bot
            symbol: Filtrer par symbole
            exchange: Filtrer par exchange
            signal_type: Filtrer par type
            status: Filtrer par statut
            limit: Nombre de signaux
            offset: Décalage

        Returns:
            Liste des signaux
        """
        signals = list(self._signal_cache.values())
        
        signals = [s for s in signals if s.bot_id == bot_id]
        
        if symbol:
            signals = [s for s in signals if s.symbol == symbol]
        if exchange:
            signals = [s for s in signals if s.exchange == exchange]
        if signal_type:
            signals = [s for s in signals if s.signal_type == signal_type]
        if status:
            signals = [s for s in signals if s.status == status]
        
        signals.sort(key=lambda x: x.created_at, reverse=True)
        
        return signals[offset:offset + limit]

    # ========================================================================
    # MÉTHODES DE GESTION
    # ========================================================================

    async def get_health(self) -> Dict[str, Any]:
        """
        Vérifie la santé du service.

        Returns:
            État de santé
        """
        try:
            return {
                "status": "healthy",
                "total_signals": self._metrics["total_signals"],
                "total_aggregations": self._metrics["total_aggregations"],
                "signals_by_type": self._metrics["signals_by_type"],
                "signals_by_source": self._metrics["signals_by_source"],
                "signals_by_strength": self._metrics["signals_by_strength"],
                "executed_signals": self._metrics["executed_signals"],
                "accuracy_rate": self._metrics["accuracy_rate"],
                "last_signal": self._metrics["last_signal"],
                "cached_signals": len(self._signal_cache),
                "cached_aggregations": len(self._aggregation_cache),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def close(self) -> None:
        """Ferme proprement le service."""
        logger.info("Fermeture de ArbitrageBotSignalGenerator...")
        self._signal_cache.clear()
        self._aggregation_cache.clear()
        self._price_history.clear()
        self._indicator_cache.clear()
        logger.info("ArbitrageBotSignalGenerator fermé")


# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def create_arbitrage_bot_signal_generator(
    redis_url: str = "redis://localhost:6379/0",
    api_keys: Optional[Dict[str, str]] = None,
    indicator_configs: Optional[Dict[str, IndicatorConfig]] = None
) -> ArbitrageBotSignalGenerator:
    """
    Crée une instance du générateur de signaux.

    Args:
        redis_url: URL de connexion Redis
        api_keys: Clés API
        indicator_configs: Configurations des indicateurs

    Returns:
        Instance du générateur
    """
    import redis.asyncio as redis
    
    redis_client = redis.Redis.from_url(redis_url)
    
    return ArbitrageBotSignalGenerator(
        redis_client=redis_client,
        api_keys=api_keys,
        indicator_configs=indicator_configs
    )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "SignalType",
    "SignalSource",
    "SignalStrength",
    "Signal",
    "IndicatorConfig",
    "SignalAggregation",
    "ArbitrageBotSignalGenerator",
    "create_arbitrage_bot_signal_generator"
]


# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

async def example_usage():
    """Exemple d'utilisation du générateur de signaux."""
    print("=" * 60)
    print("NEXUS AI TRADING - ARBITRAGE BOT SIGNAL GENERATOR")
    print("=" * 60)

    # Création du générateur
    signal_generator = create_arbitrage_bot_signal_generator()

    # Création d'un bot exemple
    from ..arbitrage_bot import ArbitrageBot, ArbitrageConfig
    
    config = ArbitrageConfig(
        bot_id=uuid4(),
        name="Signal Bot",
        min_profit_threshold=0.005
    )
    
    bot = ArbitrageBot(
        config=config,
        exchange_clients={}
    )

    print(f"\n✅ Bot ID: {bot.config.bot_id}")

    # Données de prix simulées
    price_data = []
    current_price = 50000
    for i in range(100):
        current_price += random.randint(-200, 200)
        price_data.append({
            "timestamp": datetime.now() - timedelta(minutes=100-i),
            "open": current_price - 50,
            "high": current_price + 100,
            "low": current_price - 100,
            "close": current_price,
            "volume": random.randint(100, 1000)
        })

    # Génération de signaux
    print(f"\n📊 Génération de signaux...")
    signals = await signal_generator.generate_signals(
        bot=bot,
        symbol="BTC/USDT",
        exchange=ExchangeType.BINANCE,
        price_data=price_data
    )

    print(f"   {len(signals)} signaux générés")

    # Affichage des signaux
    print(f"\n📋 Signaux:")
    for signal in signals[:5]:
        print(f"   {signal.signal_type.value.upper()}: {signal.symbol} "
              f"(confiance: {signal.confidence:.2f}) - {signal.reason[:30]}...")

    # Agrégation des signaux
    if signals:
        print(f"\n🔄 Agrégation des signaux...")
        aggregation = await signal_generator.aggregate_signals(
            bot_id=bot.config.bot_id,
            symbol="BTC/USDT",
            exchange=ExchangeType.BINANCE,
            signals=signals
        )

        print(f"   Type agrégé: {aggregation.aggregated_type.value}")
        print(f"   Force: {aggregation.aggregated_strength.value}")
        print(f"   Confiance: {aggregation.aggregated_confidence:.2f}")
        print(f"   Score: {aggregation.score:.2f}")
        print(f"   Votes: {aggregation.vote_counts}")

    # Santé du service
    health = await signal_generator.get_health()
    print(f"\n❤️ Santé du service:")
    print(f"   Signaux: {health['total_signals']}")
    print(f"   Agrégations: {health['total_aggregations']}")
    print(f"   Dernier signal: {health['last_signal']}")

    # Fermeture
    await signal_generator.close()

    print("\n" + "=" * 60)
    print("ArbitrageBotSignalGenerator NEXUS opérationnel ✅")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    import random
    import numpy as np
    import pandas as pd
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(example_usage())
